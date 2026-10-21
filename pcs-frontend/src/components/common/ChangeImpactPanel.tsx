/**
 * ChangeImpactPanel — 变更影响分析面板（P45-1-8 / Task 13）。
 *
 * SPEC §6.7 + plan P45-1-8：
 * - 顶部 ⚠ 提示 + 变更源描述 + 变更人/时间
 * - 受影响记录列表：橙色左边框 + 警告图标 + tag/result
 * - 单行 [确认重算] + 多选 + 底部 [批量确认重算] / [全部暂不处理]
 *
 * ## `record_type` 用**注册表键**（P9B-1 · RF-11）
 *
 * ⚠️ 分类词（`PIPE` / `PUMP` / `UTIL`）是**第 7 套词表** —— 后端
 * `/change-impact` 对未登记的词 **404**（`change_impact.py:134`）
 * ⇒ 数据层只放 `RECORD_TYPE_REGISTRY` 的键。
 *
 * ⚠️ **「注册表键 → UI 表示」映射表的 value 不得是分类词**
 * （⛔ `{ PipingResult: 'PIPE' }` 就是**第 8 套词表**，与 TODO-060 相反）
 * ⇒ value 是**图标 / 颜色 / 显示名**。
 *
 * ⚠️ **必须带 fallback**：后端注册表新增类型时，前端映射表不可能实时同步
 * ⇒ 失败模式应是「显示不完美」，**不是**「面板崩溃」⇒ 未登记的键
 * **默认图标 + 原始键文本**（不塌成某个「默认分类」）。
 *
 * Props（SPEC 锁定）：
 *   changeSource: { description, changed_by, changed_at }
 *   affectedRecords: AffectedRecord[]
 *   onConfirmRecalc?: (recordIds: string[]) => void
 *   onDefer?: () => void
 *   onConfirmSystem?: (recordType, recordId) => Promise<ImpactConfirmResponse>
 *   onManualAdjust?: (recordType, recordId, decision, reason) => Promise<ImpactConfirmResponse>
 */
import { useMemo, useState } from 'react';
import { Alert, Button, Card, Checkbox, Input, List, Modal, Select, Space, Tag, Typography } from 'antd';
import { WarningOutlined } from '@ant-design/icons';

import type { ImpactConfirmResponse } from '../../api/changeImpact';
import { extractPcsError } from '../../api/errors';

/**
 * 从异常里取出**可给人看的**一句话。
 *
 * ⚠️ 取后端 `message` **原文**（不自己拼）⇒ 与仓库的错误信封一致
 * （`{code, message, detail, trace_id}`）。
 */
function errorMessage(err: unknown): string {
  const envelope = extractPcsError(err);
  if (envelope?.message) return envelope.message;
  if (envelope?.code) return envelope.code;
  return '操作失败，请重试';
}

export interface ChangeSource {
  /** 变更源描述（如「物流 S-101 · 流量 50 → 60 m³/h」） */
  description: string;
  /** 变更人 */
  changed_by: string;
  /** 变更时间（ISO 字符串或可格式化日期） */
  changed_at: string;
}

export interface AffectedRecord {
  record_id: string;
  /**
   * 记录类型 = **`RECORD_TYPE_REGISTRY` 的键**（`PipingResult` /
   * `CostEstResult` / `cooling_tower_result` …）。
   *
   * ⚠️ **不是**分类词（`PIPE` / `PUMP` / `UTIL`）—— 那是第 7 套词表，
   * 后端 `/change-impact` 对未登记的词 **404**。
   */
  record_type: string;
  /** 装置/记录位号 */
  tag_number: string;
  /** 影响的计算结果（如「压降结果」「扬程结果」「电耗汇总」） */
  result_label: string;
}

/** 一个注册表键的 UI 表示。 */
interface RecordTypePresentation {
  /** 显示名（空 ⇒ 用**原始键文本**）。 */
  label: string;
  /** 图标字符。 */
  icon: string;
  /** 左边框颜色（spec 灰色统一，仅左边框与图标传达警告）。 */
  color: string;
}

/**
 * 「注册表键 → UI 表示」映射表。
 *
 * ⚠️ **只含本批涉及的 6 个键** —— 其余 15 个走 fallback。
 * 理由：本批只做这 6 个结果页；其余键的 UI 表示在**它们自己的批次**做
 * （一次填 21 个 = 本批不需要的工作量，且那 15 个键的显示名没人核对过）。
 */
const RECORD_TYPE_PRESENTATION: Record<string, RecordTypePresentation> = {
  CostEstResult: { label: '成本估算结果', icon: '¥', color: 'var(--state-stale, #D29922)' },
  FiltrationResult: { label: '过滤结果', icon: '⌗', color: 'var(--state-stale, #D29922)' },
  OpenChannelResult: { label: '明渠结果', icon: '≈', color: 'var(--state-stale, #D29922)' },
  cooling_tower_result: { label: '冷却塔结果', icon: '☂', color: 'var(--state-stale, #D29922)' },
  flare_system_result: { label: '火炬系统结果', icon: '✦', color: 'var(--state-stale, #D29922)' },
  psychro_result: { label: '湿空气结果', icon: '◐', color: 'var(--state-stale, #D29922)' },
};

/** fallback：默认图标 + **原始键文本**（label 为空 ⇒ 渲染时用键本身）。 */
const DEFAULT_PRESENTATION: RecordTypePresentation = {
  label: '',
  icon: '●',
  color: 'var(--state-stale, #D29922)',
};

function presentationOf(recordType: string): RecordTypePresentation {
  return RECORD_TYPE_PRESENTATION[recordType] ?? DEFAULT_PRESENTATION;
}

interface Props {
  changeSource: ChangeSource;
  affectedRecords: AffectedRecord[];
  onConfirmRecalc?: (recordIds: string[]) => void;
  onDefer?: () => void;
  /**
   * **系统判定**（SPEC §6.7.1 P9A-CIA-001）—— 端点
   * `POST /change-impact/{rt}/{id}/confirm`。
   *
   * ⚠️ 与 `onManualAdjust` 是**两个端点**，不可合并。
   * ⚠️ 返回**响应**（不是 void）⇒ 按钮文案随响应的 `decision` 分流
   * （**不得**前端自己先判）。
   */
  onConfirmSystem?: (recordType: string, recordId: string) => Promise<ImpactConfirmResponse>;
  /**
   * **人工判定**（SPEC §6.7.1 P9A-CIA-002）—— 端点
   * `POST /change-impact/{rt}/{id}/manual-adjust`。
   *
   * ⚠️ `reason` **必填**（后端 `min_length=1`，空 ⇒ 422）⇒ 前端先校验。
   */
  onManualAdjust?: (
    recordType: string,
    recordId: string,
    decision: 'NO_CHANGE' | 'CHANGED',
    reason: string,
  ) => Promise<ImpactConfirmResponse>;
}

export function ChangeImpactPanel({
  changeSource,
  affectedRecords,
  onConfirmRecalc,
  onDefer,
  onConfirmSystem,
  onManualAdjust,
}: Props): JSX.Element {
  const [selected, setSelected] = useState<Set<string>>(new Set());
  // ⚠️ **系统判定的结论**（NO_CHANGE / CHANGED）—— 按钮文案随**响应**分流。
  const [decisions, setDecisions] = useState<Record<string, 'NO_CHANGE' | 'CHANGED'>>({});
  // 人工判定弹窗的目标行。
  const [manualTarget, setManualTarget] = useState<{ recordType: string; recordId: string } | null>(null);
  const [manualDecision, setManualDecision] = useState<'NO_CHANGE' | 'CHANGED'>('NO_CHANGE');
  const [manualReason, setManualReason] = useState('');
  // ⚠️ **判定失败要说出口**（最终评审 Important ⑥）。
  // 此前没有它 ⇒ 403/409/500 时界面毫无变化 + 未捕获的 promise rejection。
  const [actionError, setActionError] = useState<string | null>(null);

  const allSelected = useMemo(
    () =>
      affectedRecords.length > 0 &&
      affectedRecords.every((r) => selected.has(r.record_id)),
    [selected, affectedRecords],
  );

  function toggle(recordId: string): void {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(recordId)) next.delete(recordId);
      else next.add(recordId);
      return next;
    });
  }

  function toggleAll(): void {
    setSelected(() => {
      if (allSelected) return new Set();
      return new Set(affectedRecords.map((r) => r.record_id));
    });
  }

  function handleBatchConfirm(): void {
    const ids = allSelected
      ? affectedRecords.map((r) => r.record_id)
      : Array.from(selected);
    if (ids.length > 0) onConfirmRecalc?.(ids);
  }

  function handleDefer(): void {
    onDefer?.();
  }

  /** 系统判定 —— **不自动重试**（会无限循环覆盖）。 */
  async function handleConfirmSystem(recordType: string, recordId: string): Promise<void> {
    if (!onConfirmSystem) return;
    setActionError(null);
    try {
      const res = await onConfirmSystem(recordType, recordId);
      // ⚠️ 文案随**响应**的 decision 分流（前端不自己先判）。
      if (res?.decision === 'NO_CHANGE' || res?.decision === 'CHANGED') {
        setDecisions((prev) => ({ ...prev, [recordId]: res.decision }));
      }
    } catch (err: unknown) {
      // ⚠️ **失败必须说出口**（最终评审 Important ⑥）：403（DESIGNER 调
      // manual-adjust 是设计如此）/ 409 / 500 时，界面毫无变化 ⇒ 用户以为
      // 「点了没反应」，而控制台还多一条**未捕获的 promise rejection**。
      setActionError(errorMessage(err));
    }
  }

  function openManualAdjust(recordType: string, recordId: string): void {
    setManualTarget({ recordType, recordId });
    setManualDecision('NO_CHANGE');
    setManualReason('');
  }

  /** 人工判定 —— ⚠️ `reason` 为空**不发请求**（后端 422）。 */
  async function submitManualAdjust(): Promise<void> {
    if (!manualTarget || !onManualAdjust) return;
    if (manualReason.trim() === '') return;
    setActionError(null);
    try {
      const res = await onManualAdjust(
        manualTarget.recordType,
        manualTarget.recordId,
        manualDecision,
        manualReason.trim(),
      );
      if (res?.decision === 'NO_CHANGE' || res?.decision === 'CHANGED') {
        setDecisions((prev) => ({ ...prev, [manualTarget.recordId]: res.decision }));
      }
      setManualTarget(null);
    } catch (err: unknown) {
      // ⚠️ **失败时弹窗不关**（用户刚填的理由不该被吞掉）⇒ 只显示错误。
      setActionError(errorMessage(err));
    }
  }

  return (
    <>
    <Card
      data-testid="change-impact-panel"
      title={
        <Space>
          <WarningOutlined style={{ color: 'var(--state-stale, #D29922)' }} />
          <Typography.Text strong>上游数据已变更</Typography.Text>
        </Space>
      }
      style={{ marginTop: 16 }}
    >
      <Alert
        type="warning"
        showIcon
        data-testid="change-impact-source"
        message={
          <Space direction="vertical" size={2}>
            <span data-testid="change-source-description">
              变更源：{changeSource.description}
            </span>
            <Typography.Text type="secondary" data-testid="change-source-meta">
              变更人：{changeSource.changed_by} ·{' '}
              {changeSource.changed_at}
            </Typography.Text>
          </Space>
        }
        style={{ marginBottom: 16 }}
      />

      {/* ⚠️ **判定失败的提示**（Important ⑥）—— 失败必须说出口，
          否则用户只看到「点了没反应」。文案取后端 `message` 原文。 */}
      {actionError && (
        <Alert
          type="error"
          showIcon
          closable
          data-testid="change-impact-error"
          message={actionError}
          onClose={() => setActionError(null)}
          style={{ marginBottom: 16 }}
        />
      )}

      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          marginBottom: 8,
        }}
      >
        <Typography.Text strong data-testid="affected-count">
          受影响记录（{affectedRecords.length}）
        </Typography.Text>
        {affectedRecords.length > 0 && (
          <Checkbox
            data-testid="select-all"
            checked={allSelected}
            onChange={toggleAll}
          >
            全选
          </Checkbox>
        )}
      </div>

      <List
        data-testid="affected-list"
        size="small"
        dataSource={affectedRecords}
        renderItem={(r) => {
          const p = presentationOf(r.record_type);
          const color = p.color;
          const decision = decisions[r.record_id];
          return (
            <List.Item
              data-testid="affected-item"
              data-record-id={r.record_id}
              data-record-type={r.record_type}
              style={{
                borderLeft: `4px solid ${color}`,
                paddingLeft: 12,
              }}
            >
              <Space style={{ flex: 1 }}>
                <Checkbox
                  data-testid="affected-checkbox"
                  checked={selected.has(r.record_id)}
                  onChange={() => toggle(r.record_id)}
                />
                <span
                  data-testid="affected-type"
                  style={{ fontFamily: 'var(--font-mono, monospace)' }}
                >
                  {/* ⚠️ 未登记的键 ⇒ **原始键文本**（不塌成「默认分类」） */}
                  {p.icon} {p.label || r.record_type}
                </span>
                <span style={{ fontFamily: 'var(--font-mono, monospace)' }}>
                  {r.tag_number}
                </span>
                <span style={{ color: 'var(--text-secondary, #656D76)' }}>
                  {r.result_label}
                </span>
              </Space>
              <Button
                type="link"
                data-testid="confirm-single"
                data-record-id={r.record_id}
                onClick={() => onConfirmRecalc?.([r.record_id])}
              >
                确认重算
              </Button>
              {onConfirmSystem && (
                <Button
                  type="link"
                  data-testid="confirm-system"
                  data-record-id={r.record_id}
                  onClick={() => void handleConfirmSystem(r.record_type, r.record_id)}
                >
                  <span data-testid={`confirm-system-${r.record_id}`}>
                    {decision === 'NO_CHANGE'
                      ? '确认：结果未变'
                      : decision === 'CHANGED'
                        ? '确认：结果已变'
                        : '系统判定'}
                  </span>
                  {decision === 'CHANGED' && (
                    <Tag color="warning" data-testid="confirm-system-reapproval">
                      须重新签署
                    </Tag>
                  )}
                </Button>
              )}
              {onManualAdjust && (
                <Button
                  type="link"
                  data-testid={`manual-adjust-${r.record_id}`}
                  data-record-id={r.record_id}
                  onClick={() => openManualAdjust(r.record_type, r.record_id)}
                >
                  人工判定
                </Button>
              )}
            </List.Item>
          );
        }}
      />

      <Space style={{ marginTop: 16 }}>
        <Button
          type="primary"
          data-testid="batch-confirm"
          disabled={selected.size === 0 && !allSelected}
          onClick={handleBatchConfirm}
        >
          批量确认重算（{allSelected ? affectedRecords.length : selected.size}）
        </Button>
        <Button data-testid="defer-all" onClick={handleDefer}>
          全部暂不处理
        </Button>
      </Space>
    </Card>

    <Modal
      open={manualTarget !== null}
      title="人工判定"
      okText="提交"
      cancelText="取消"
      onCancel={() => setManualTarget(null)}
      okButtonProps={{
        'data-testid': 'manual-adjust-ok',
        // ⚠️ **reason 为空 ⇒ 按钮禁用 ⇒ 根本不会发请求**（后端 422）。
        disabled: manualReason.trim() === '',
      }}
      onOk={() => void submitManualAdjust()}
    >
      <Space direction="vertical" size={8} style={{ width: '100%' }}>
        <Select
          data-testid="manual-adjust-decision"
          value={manualDecision}
          onChange={(v) => setManualDecision(v)}
          options={[
            { value: 'NO_CHANGE', label: '结果未变（免凭证）' },
            { value: 'CHANGED', label: '结果已变（须重新签署）' },
          ]}
          style={{ width: '100%' }}
        />
        <Input.TextArea
          data-testid="manual-adjust-reason"
          value={manualReason}
          onChange={(e) => setManualReason(e.target.value)}
          placeholder="判定理由（必填）"
          rows={3}
        />
      </Space>
    </Modal>
    </>
  );
}

export default ChangeImpactPanel;