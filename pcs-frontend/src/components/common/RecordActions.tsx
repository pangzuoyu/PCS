/**
 * RecordActions —— 记录操作按钮组（P9B-2 · T4 · SPEC §6.3）。
 *
 * ## 按钮从哪来
 *
 * ⚠️ **不是**前端硬编码的「状态 → 按钮」表 —— 而是
 * `GET /meta/state-machine` 的 `allowed[状态]`（后端从 `ALLOWED_TRANSITIONS`
 * 生成）+ 每条迁移的 `allowed_roles`（SPEC §5.5.1：前端不得自行推导能力）。
 *
 * ⇒ 后端加一个迁移，前端自动跟上；前端**不会**出现「注定 409」的按钮。
 *
 * ## 禁用优先于报错（SPEC §5.1「门禁前置」）
 *
 * - 角色不在 `allowed_roles` ⇒ 禁用 + Tooltip 写明「当前角色不可执行此操作」
 * - 理由必填的动作（弃用 / 发起撤销 / 退回 / 撤销驳回）理由为空 ⇒ **确认按钮禁用**
 * - 矩阵第 1 步的角色 == 当前用户 ⇒ 送审禁用 + Tooltip（替代「选角色」）
 *
 * ## 变更类动作**也**在这张表里（R-12）
 *
 * `INITIATE_CHANGE` / `APPLY_CHANGE` / `ABANDON_CHANGE` 本来就在
 * `ALLOWED_TRANSITIONS` 里 ⇒ meta 驱动会**自动**包含它们 ⇒ 端点**都有**
 * ⇒ 渲染成**可用**按钮。
 * ⚠️ **R-6 已失效**（2026-10-27）—— 旧文说这三个按钮「没有后端端点 ⇒ 禁用」，
 * **那是被推翻的旧文**，别照它写。
 *
 * ⚠️ **但 `change-notice`（建单）/ `change-notice/cancel`（作废）不是状态机
 * 事件** ⇒ meta 驱动**不会**渲染它们 ⇒ 它们归 `ChangeNoticeAction`（R-12b）。
 */
import { useEffect, useMemo, useState } from 'react';
import { Button, Input, Modal, Skeleton, Space, Tooltip, Typography } from 'antd';

import { metaApi, type StateMachineResponse } from '../../api/meta';
import { recordActionsApi } from '../../api/recordActions';
import { signatureMatricesApi } from '../../api/signatureMatrices';
import { extractPcsError } from '../../api/errors';
import { useAuth } from '../../store/auth';
import type { EditableRecordType } from '../../api/records';

export interface RecordActionsProps {
  module: EditableRecordType;
  recordId: string;
  /** `null` = 该模块**没有 9 态列** ⇒ 不渲染操作栏（RF-4）。 */
  signStatus: string | null;
  /** 项目 id —— 读项目绑定的 RECORD 矩阵（第 1 步该谁签）。 */
  projectId?: string;
  /** 动作成功后由宿主页刷新。 */
  onDone: () => void;
}

/** 状态机事件 → 按钮与端点（**前端唯一的映射**，不是 ACL）。 */
interface ActionSpec {
  label: string;
  /** 理由**必填** ⇒ 弹窗，且为空时**确认按钮禁用**。 */
  reasonRequired: boolean;
  run: (reason: string) => Promise<unknown>;
}

function buildSpecs(
  module: EditableRecordType,
  recordId: string,
): Record<string, ActionSpec> {
  return {
    SUBMIT_FOR_CHECK: {
      label: '提交批准',
      reasonRequired: false,
      // ⚠️ **R-17**：不再传 approval_role / approval_depth（后端从矩阵推导）
      run: (reason) =>
        recordActionsApi.submitApproval(module, recordId, reason || undefined),
    },
    PASS_CHECK: {
      label: '通过',
      reasonRequired: false,
      run: (reason) => recordActionsApi.approvalStep(module, recordId, 'PASS', reason),
    },
    REJECT_CHECK: {
      label: '退回',
      // ⚠️ 后端允许空理由 ⇒ 前端**加严**：事后「为什么退回」无从追溯
      reasonRequired: true,
      run: (reason) => recordActionsApi.approvalStep(module, recordId, 'REJECT', reason),
    },
    OBSOLETE: {
      label: '弃用',
      reasonRequired: true,
      run: (reason) => recordActionsApi.obsolete(module, recordId, reason),
    },
    REQUEST_REVERSAL: {
      label: '发起撤销',
      reasonRequired: true,
      run: (reason) => recordActionsApi.requestReversal(module, recordId, reason),
    },
    APPROVE_REVERSAL: {
      label: '撤销批准',
      reasonRequired: false,
      run: (reason) =>
        recordActionsApi.reversalDecision(module, recordId, 'APPROVE', reason),
    },
    REJECT_REVERSAL: {
      label: '撤销驳回',
      reasonRequired: true,
      run: (reason) =>
        recordActionsApi.reversalDecision(module, recordId, 'REJECT', reason),
    },
    ABANDON_CHANGE: {
      label: '放弃变更',
      // ⚠️ **理由必填**（后端 `ChangeActionRequest.reason` = `min_length=1`）
      //    ⇒ 空理由直接 **422** ⇒ 此前 `reasonRequired: false` ⇒ 按钮**永远
      //    点不动**（且「放弃变更」是变更单唯一的退出路径 ⇒ 卡死）。
      reasonRequired: true,
      run: (reason) => recordActionsApi.abandonChange(module, recordId, reason),
    },
    INITIATE_CHANGE: {
      label: '变更申请',
      reasonRequired: true,
      run: (reason) => recordActionsApi.initiateChange(module, recordId, reason),
    },
    APPLY_CHANGE: {
      label: '提交变更完成',
      reasonRequired: true,
      run: (reason) => recordActionsApi.applyChange(module, recordId, reason),
    },
  };
}

/**
 * 项目绑定的 RECORD 矩阵的**整条链**（每一步的角色）缓存。
 *
 * ⚠️ 同一项目只拉一次 ⇒ 不是每行一次 ⇒ 不是 N+1。
 * ⚠️ **只缓存成功的结果** ⇒ 拉失败不缓存（下次重试）。
 *
 * ## 为什么是「整条链」而不是「第 1 步」
 *
 * 后端 `APPROVAL_SELF_REVIEW_FORBIDDEN` 的判据是「提交人自己的角色出现在链里
 * **任何一步**」（不是只挡第 1 步 —— 只挡第 1 步会留下「在第 2 步自己批自己」
 * 的洞）⇒ 前端只挡第 1 步 ⇒ APPROVER 之类的角色点了必吃 403
 * ⇒ **前端与后端判据不一致 ⇒ 门禁失效**。
 *
 * ## 为什么把「没绑矩阵」与「拉失败」分开
 *
 * 「没绑」⇒ 前端**知道**（绑定列表里没有 RECORD）⇒ 门禁前置（SPEC V2.2）
 * ⇒ 禁用 + Tooltip；「拉失败」⇒ 前端**不知道** ⇒ **不猜**（不禁用）⇒ 后端
 * 422 兜底。两者混成同一个 `null` ⇒ 「没绑」也变成了「不猜」。
 */
type ChainState =
  | { kind: 'loading' }
  | { kind: 'bound'; roles: string[] }
  | { kind: 'unbound' }
  | { kind: 'failed' };

const chainCache = new Map<string, ChainState>();

async function loadChain(projectId: string): Promise<ChainState> {
  const cached = chainCache.get(projectId);
  if (cached) return cached;
  try {
    const bindings = await signatureMatricesApi.listProjectBindings(projectId);
    const recordBinding = bindings.find((b) => b.module === 'RECORD');
    const state: ChainState = recordBinding
      ? { kind: 'bound', roles: (recordBinding.steps ?? []).map((s) => s.sign_role) }
      : { kind: 'unbound' };
    chainCache.set(projectId, state);
    return state;
  } catch {
    // ⚠️ 拉失败 ⇒ **不禁用**（前端不知道 ⇒ 不猜）⇒ 后端 422/403 兜底
    return { kind: 'failed' };
  }
}

export function RecordActions({
  module,
  recordId,
  signStatus,
  projectId,
  onDone,
}: RecordActionsProps): JSX.Element | null {
  const role = useAuth((s) => s.role);
  const [sm, setSm] = useState<StateMachineResponse | null>(null);
  const [metaError, setMetaError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [pending, setPending] = useState<string | null>(null);
  const [chain, setChain] = useState<ChainState>({ kind: 'loading' });
  const [reasonFor, setReasonFor] = useState<string | null>(null);
  const [reason, setReason] = useState('');

  const specs = useMemo(() => buildSpecs(module, recordId), [module, recordId]);

  useEffect(() => {
    // ⚠️ 无 9 态列 ⇒ **不发任何请求**（不发注定失败的请求，RF-4）
    if (!signStatus) return;
    let cancelled = false;
    void metaApi
      .stateMachine()
      .then((r) => {
        if (!cancelled) setSm(r);
      })
      .catch(() => {
        if (!cancelled) setMetaError('无法读取状态机定义');
      });
    return () => {
      cancelled = true;
    };
  }, [signStatus]);

  useEffect(() => {
    if (!signStatus || !projectId) return;
    let cancelled = false;
    void loadChain(projectId).then((c) => {
      if (!cancelled) setChain(c);
    });
    return () => {
      cancelled = true;
    };
  }, [signStatus, projectId]);

  if (!signStatus) return null;

  if (metaError) {
    return (
      <Typography.Text type="danger" data-testid="record-actions-error">
        {metaError}
      </Typography.Text>
    );
  }
  if (!sm) return <Skeleton active />;

  // ⚠️ **可选链要两层**：`sm.allowed?.[signStatus]` —— 只写 `sm.allowed[signStatus]`
  //    在 `sm.allowed` 本身缺失时（schema 变更 / 200 但体不符）会 TypeError。
  const actions = sm.allowed?.[signStatus] ?? [];

  async function run(action: string, reasonText: string) {
    const spec = specs[action];
    if (!spec) return;
    setPending(action);
    setActionError(null);
    try {
      await spec.run(reasonText);
      setReasonFor(null);
      setReason('');
      onDone();
    } catch (err) {
      // ⚠️ **失败明说**（错误码 + 原文）—— 不静默降级成「成功」或「没有」
      const envelope = extractPcsError(err);
      setActionError(
        envelope?.code
          ? `${envelope.code}：${envelope.message ?? ''}`
          : '操作失败，请稍后再试',
      );
    } finally {
      setPending(null);
    }
  }

  const reasonSpec = reasonFor ? specs[reasonFor] : null;
  const reasonDisabled = Boolean(reasonSpec?.reasonRequired && !reason.trim());

  return (
    <Space wrap data-testid="record-actions">
      {actions.map((action) => {
        const spec = specs[action];
        if (!spec) return null;
        const transition = sm.transitions.find(
          (t) => t.from === signStatus && t.action === action,
        );
        const allowedRoles = transition?.allowed_roles ?? [];
        const roleOk = !role || allowedRoles.length === 0 || allowedRoles.includes(role);
        // ⚠️ **链里有你自己的角色** ⇒ 送审必吃 403 ⇒ 门禁前置（判据与后端
        //    `APPROVAL_SELF_REVIEW_FORBIDDEN` **同口径**：链里**任何一步**）。
        const selfReview =
          action === 'SUBMIT_FOR_CHECK' &&
          chain.kind === 'bound' &&
          Boolean(role) &&
          chain.roles.includes(role as string);
        // ⚠️ **项目没绑 RECORD 矩阵** ⇒ 无法推导批准链 ⇒ 后端必 422
        //    ⇒ 前端**知道**（绑定列表里没有 RECORD）⇒ 门禁前置（SPEC V2.2）。
        const chainUnbound = action === 'SUBMIT_FOR_CHECK' && chain.kind === 'unbound';
        const disabled = !roleOk || selfReview || chainUnbound || pending === action;
        const hint = chainUnbound
          ? '项目未绑定记录级签署矩阵 ⇒ 无法推导批准链'
          : selfReview
            ? '批准链里有你自己的角色 ⇒ 不能自己送自己审'
            : !roleOk
              ? `当前角色（${role ?? '未知'}）不可执行此操作`
              : '';
        const button = (
          <Button
            key={action}
            data-testid={`record-action-${action}`}
            disabled={disabled}
            danger={action === 'OBSOLETE'}
            onClick={() => {
              // ⚠️ **理由必填**的动作 ⇒ 弹窗（为空时确认按钮禁用）；
              //    理由可选的动作 ⇒ 直接发（不制造「为了填个可选理由」的摩擦）。
              if (spec.reasonRequired) {
                setReason('');
                setReasonFor(action);
              } else {
                void run(action, '');
              }
            }}
          >
            {spec.label}
          </Button>
        );
        return (
          <Tooltip key={`tip-${action}`} title={hint}>
            {disabled ? <span>{button}</span> : button}
            {/* ⚠️ antd 的 Tooltip **不把 props 转发到 DOM** ⇒ 禁用原因
                另外渲染一个节点（视觉隐藏）⇒ 断言能读到「为什么禁用」。 */}
            {hint && (
              <span
                style={{ display: 'none' }}
                data-testid={`record-action-${action}-hint`}
              >
                {hint}
              </span>
            )}
          </Tooltip>
        );
      })}
      {actionError && (
        <Typography.Text type="danger" data-testid="record-actions-error">
          {actionError}
        </Typography.Text>
      )}
      <Modal
        open={reasonFor !== null}
        title={reasonSpec?.label ?? ''}
        onCancel={() => setReasonFor(null)}
        onOk={() => {
          if (reasonFor) void run(reasonFor, reason.trim());
        }}
        okButtonProps={{
          disabled: reasonDisabled,
          'data-testid': 'record-action-reason-ok',
        }}
        cancelButtonProps={{ 'data-testid': 'record-action-reason-cancel' }}
      >
        <Input.TextArea
          data-testid="record-action-reason-input"
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          placeholder={
            reasonSpec?.reasonRequired
              ? '理由必填（事后无从追溯）'
              : '理由（可选）'
          }
          rows={3}
        />
      </Modal>
    </Space>
  );
}
