/**
 * DeliverableSignDialog —— 交付物级签署**写面**（P9B-2 · T8 · SPEC §7.19）。
 *
 * ## 三种模式（一个组件）
 *
 * | mode | 动作 | 端点 |
 * |---|---|---|
 * | `issue` | 签发（送审） | `POST /deliverables/{id}/issue` |
 * | `sign` | 推进签署矩阵的一步（签 / 退 / 跳） | `POST /deliverables/{id}/sign-step` |
 * | `proxy` | 代录客户在系统外的批准 | `POST /deliverables/{id}/customer-approval/proxy` |
 *
 * ## 四条纪律
 *
 * 1. ⚠️ **下一步由后端的数据算出**，不硬编码步骤表 —— 步骤取**版本冻结快照**
 *    （`signature_summary_json.steps`）⇒ 与后端 `_steps_for_version` **同源**
 *    （bug-2063：读活矩阵会让在飞版本与模板分叉 ⇒ 永久卡在 PENDING）。
 * 2. ⚠️ **当前角色不在该步的 `sign_role` ⇒ 按钮禁用 + 写明原因** ——
 *    不是让用户点了吃 403（SPEC §5.1「不误导」）。
 * 3. ⚠️ **退回必须填理由**（前端拦）—— 退回是签署流程里唯一能纠错的路径；
 *    没有理由，作者无从知道要改什么。
 * 4. ⚠️ **失败显示后端 `message` 原文** —— 前端不自造错误文案（用户要找的人
 *    在原文里）。
 */
import { useEffect, useState } from 'react';
import type { JSX } from 'react';
import { Alert, Button, Input, Modal, Select, Space, Typography } from 'antd';

import {
  CUSTOMER_APPROVAL_METHODS,
  CREDENTIAL_FILE_TYPES,
  VERSION_PURPOSES,
  deliverablesApi,
  type CustomerApprovalProxyRequest,
  type DeliverableIssueRequest,
  type SignStepRequest,
  type VersionPurpose,
} from '../../api/deliverables';

export type SignDialogMode = 'issue' | 'sign' | 'proxy';

/** 矩阵的一步（版本冻结快照里的形状）。 */
export interface SignDialogStep {
  step_order: number;
  sign_role: string;
  can_skip?: boolean;
}

/** 「当前该签哪一步」（`step_index` = 矩阵步骤列表里的 1-based 位置）。 */
export interface SignNextStep {
  step_index: number;
  step_order: number;
  sign_role: string;
  can_skip: boolean;
}

export interface DeliverableSignDialogProps {
  open: boolean;
  mode: SignDialogMode;
  deliverable: {
    deliverable_id: string;
    doc_no: string;
    title: string;
    current_rev?: string | null;
    current_version_id?: string | null;
  };
  /** 签署模式：下一步（无 ⇒ 没有可签的步骤）。 */
  nextStep?: SignNextStep | null;
  /** 当前用户角色（= token 的 role claim，与矩阵 `sign_role` 同口径）。 */
  role?: string | null;
  /**
   * 宿主读取签署上下文时出的错（网络 / 403 / 404）。
   *
   * ⚠️ **必须与「没有待签的步骤」区分开** —— 后者让用户以为签完了，
   * 前者让用户以为**没有步骤** ⇒ 找错人、也找不到人。
   */
  contextError?: string | null;
  onClose: () => void;
  /** 成功后由宿主**重新拉数据**（不乐观更新）。 */
  onDone: () => void;
}

const TITLES: Record<SignDialogMode, string> = {
  issue: '签发交付物',
  sign: '签署',
  proxy: '代录客户批准',
};

/** 取后端错误原文（`{code, message}` 信封）。 */
function errorText(err: unknown, fallback: string): string {
  if (err && typeof err === 'object' && 'response' in err) {
    const data = (err as { response?: { data?: { code?: string; message?: string } } }).response
      ?.data;
    if (data?.message) {
      return data.code ? `${data.code}: ${data.message}` : data.message;
    }
  }
  return fallback;
}

export function DeliverableSignDialog({
  open,
  mode,
  deliverable,
  nextStep,
  role,
  contextError,
  onClose,
  onDone,
}: DeliverableSignDialogProps): JSX.Element {
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  // —— 签发 ——
  const [purpose, setPurpose] = useState<VersionPurpose>('ISSUED_FOR_CONSTRUCTION');
  const [description, setDescription] = useState('');
  // —— 签署 ——
  const [showReason, setShowReason] = useState(false);
  const [reason, setReason] = useState('');
  const [reasonRequired, setReasonRequired] = useState(false);
  // —— 代录 ——
  const [proxyForm, setProxyForm] = useState({
    file_path: '',
    file_name: '',
    file_type: 'PDF' as (typeof CREDENTIAL_FILE_TYPES)[number],
    approver_name: '',
    approval_date: '',
    approval_method: 'EMAIL' as (typeof CUSTOMER_APPROVAL_METHODS)[number],
    secondary_username: '',
    secondary_password: '',
  });

  // ⚠️ 每次打开都**重置**（否则上一次的理由/错误留在下一次里）
  useEffect(() => {
    if (!open) return;
    setError(null);
    setSubmitting(false);
    setShowReason(false);
    setReason('');
    setReasonRequired(false);
  }, [open]);

  const versionId = deliverable.current_version_id ?? '';
  // ⚠️ **角色不符 ⇒ 禁用**（不是点了吃 403）
  const roleMismatch = Boolean(
    nextStep && role && nextStep.sign_role && role !== nextStep.sign_role,
  );

  async function submitIssue(): Promise<void> {
    setSubmitting(true);
    setError(null);
    try {
      const body: DeliverableIssueRequest = {
        version_purpose: purpose,
        description,
      };
      await deliverablesApi.issue(deliverable.deliverable_id, body);
      onDone();
      onClose();
    } catch (err: unknown) {
      setError(errorText(err, '签发失败'));
    } finally {
      setSubmitting(false);
    }
  }

  async function submitSign(decision: 'SIGN' | 'RETURN' | 'SKIP'): Promise<void> {
    if (!nextStep) return;
    // ⚠️ **退回必须填理由**（前端拦）—— 没有理由的退回等于没告诉作者要改什么
    if (decision === 'RETURN' && !reason.trim()) {
      setReasonRequired(true);
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      const body: SignStepRequest = {
        version_id: versionId,
        step_index: nextStep.step_index,
        decision,
        // ⚠️ 契约里 `reason` 有 `default` ⇒ 生成类型是**必填** ⇒ 显式给值
        //    （签 / 跳给空串；退回给理由）。
        reason: decision === 'RETURN' ? reason.trim() : '',
      };
      await deliverablesApi.signStep(deliverable.deliverable_id, body);
      onDone();
      onClose();
    } catch (err: unknown) {
      setError(errorText(err, '签署失败'));
    } finally {
      setSubmitting(false);
    }
  }

  async function submitProxy(): Promise<void> {
    const missing = (
      [
        ['凭证路径', proxyForm.file_path],
        ['凭证文件名', proxyForm.file_name],
        ['客户批准人', proxyForm.approver_name],
        ['批准日期', proxyForm.approval_date],
        ['代录人 AD 用户名', proxyForm.secondary_username],
        ['代录人 AD 密码', proxyForm.secondary_password],
      ] as const
    )
      .filter(([, v]) => !v.trim())
      .map(([label]) => label);
    if (missing.length > 0) {
      setError(`代录失败：以下字段必填 —— ${missing.join('、')}`);
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      const body: CustomerApprovalProxyRequest = {
        version_id: versionId,
        file_path: proxyForm.file_path,
        file_name: proxyForm.file_name,
        file_type: proxyForm.file_type,
        approver_name: proxyForm.approver_name,
        approval_date: proxyForm.approval_date,
        approval_method: proxyForm.approval_method,
        secondary_username: proxyForm.secondary_username,
        secondary_password: proxyForm.secondary_password,
      };
      await deliverablesApi.customerApprovalProxy(deliverable.deliverable_id, body);
      onDone();
      onClose();
    } catch (err: unknown) {
      setError(errorText(err, '代录失败'));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Modal
      open={open}
      title={`${TITLES[mode]} —— ${deliverable.doc_no} ${deliverable.title}`}
      onCancel={onClose}
      footer={null}
      // ⚠️ antd 5.29 起 `destroyOnClose` 已弃用（**控制台报错**）⇒ 用 `destroyOnHidden`
      destroyOnHidden
      data-testid="deliverable-sign-dialog"
    >
      {error && (
        <Alert
          type="error"
          showIcon
          message={error}
          data-testid="sign-dialog-error"
          style={{ marginBottom: 12 }}
        />
      )}

      {mode === 'issue' && (
        <Space direction="vertical" style={{ width: '100%' }}>
          <div>
            <Typography.Text strong>版本目的</Typography.Text>
            <Select<VersionPurpose>
              data-testid="issue-purpose"
              value={purpose}
              onChange={(v) => setPurpose(v)}
              options={VERSION_PURPOSES.map((p) => ({ value: p, label: p }))}
              style={{ width: '100%', marginTop: 4 }}
            />
          </div>
          <div>
            <Typography.Text strong>版本说明</Typography.Text>
            <Input.TextArea
              data-testid="issue-description"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="可选 —— 留空则用默认文案"
              rows={3}
            />
          </div>
          <Button
            type="primary"
            data-testid="issue-submit"
            loading={submitting}
            onClick={() => void submitIssue()}
          >
            签发
          </Button>
        </Space>
      )}

      {mode === 'sign' && (
        <Space direction="vertical" style={{ width: '100%' }}>
          {nextStep ? (
            <>
              <Typography.Text strong data-testid="sign-next-step">
                第 {nextStep.step_index} 步 · {nextStep.sign_role}
              </Typography.Text>
              {roleMismatch && (
                <Typography.Text type="danger" data-testid="sign-role-hint">
                  当前角色 {role} 不是这一步要求的 {nextStep.sign_role} ⇒ 不能签署
                </Typography.Text>
              )}
              <Space>
                <Button
                  type="primary"
                  data-testid="sign-submit"
                  disabled={roleMismatch}
                  loading={submitting}
                  onClick={() => void submitSign('SIGN')}
                >
                  签署
                </Button>
                <Button
                  data-testid="sign-return"
                  disabled={roleMismatch}
                  onClick={() => setShowReason(true)}
                >
                  退回
                </Button>
                {nextStep.can_skip && (
                  <Button
                    data-testid="sign-skip"
                    disabled={roleMismatch}
                    loading={submitting}
                    onClick={() => void submitSign('SKIP')}
                  >
                    跳过
                  </Button>
                )}
              </Space>
              {showReason && (
                <>
                  <Input.TextArea
                    data-testid="sign-return-reason"
                    value={reason}
                    onChange={(e) => {
                      setReason(e.target.value);
                      if (e.target.value.trim()) setReasonRequired(false);
                    }}
                    placeholder="退回理由（必填）"
                    rows={3}
                  />
                  {reasonRequired && (
                    <Typography.Text type="danger" data-testid="sign-reason-required">
                      退回必须填写理由 —— 作者要知道该改什么
                    </Typography.Text>
                  )}
                  <Button
                    danger
                    data-testid="sign-return-submit"
                    loading={submitting}
                    onClick={() => void submitSign('RETURN')}
                  >
                    确认退回
                  </Button>
                </>
              )}
            </>
          ) : contextError ? (
            // ⚠️ **读不到步骤 ≠ 没有步骤** —— 分开说，否则用户以为签完了
            <Typography.Text type="danger" data-testid="sign-context-error">
              {contextError}
            </Typography.Text>
          ) : (
            <Typography.Text data-testid="sign-no-step">
              该交付物没有待签的步骤（矩阵未绑 / 步骤已全部完成）
            </Typography.Text>
          )}
        </Space>
      )}

      {mode === 'proxy' && (
        <Space direction="vertical" style={{ width: '100%' }}>
          <Input
            data-testid="proxy-file-path"
            value={proxyForm.file_path}
            onChange={(e) => setProxyForm((f) => ({ ...f, file_path: e.target.value }))}
            placeholder="凭证相对存储根的路径"
          />
          <Input
            data-testid="proxy-file-name"
            value={proxyForm.file_name}
            onChange={(e) => setProxyForm((f) => ({ ...f, file_name: e.target.value }))}
            placeholder="凭证文件名"
          />
          <Select
            data-testid="proxy-file-type"
            value={proxyForm.file_type}
            onChange={(v) => setProxyForm((f) => ({ ...f, file_type: v }))}
            options={CREDENTIAL_FILE_TYPES.map((t) => ({ value: t, label: t }))}
            style={{ width: '100%' }}
          />
          <Input
            data-testid="proxy-approver-name"
            value={proxyForm.approver_name}
            onChange={(e) => setProxyForm((f) => ({ ...f, approver_name: e.target.value }))}
            placeholder="客户方批准人姓名"
          />
          <Input
            data-testid="proxy-approval-date"
            type="date"
            value={proxyForm.approval_date}
            onChange={(e) => setProxyForm((f) => ({ ...f, approval_date: e.target.value }))}
          />
          <Select
            data-testid="proxy-approval-method"
            value={proxyForm.approval_method}
            onChange={(v) => setProxyForm((f) => ({ ...f, approval_method: v }))}
            options={CUSTOMER_APPROVAL_METHODS.map((m) => ({ value: m, label: m }))}
            style={{ width: '100%' }}
          />
          <Input
            data-testid="proxy-secondary-username"
            value={proxyForm.secondary_username}
            onChange={(e) =>
              setProxyForm((f) => ({ ...f, secondary_username: e.target.value }))
            }
            placeholder="代录人 AD 用户名（二次认证）"
          />
          <Input.Password
            data-testid="proxy-secondary-password"
            value={proxyForm.secondary_password}
            onChange={(e) =>
              setProxyForm((f) => ({ ...f, secondary_password: e.target.value }))
            }
            placeholder="代录人 AD 密码（二次认证）"
          />
          <Button
            type="primary"
            data-testid="proxy-submit"
            loading={submitting}
            onClick={() => void submitProxy()}
          >
            提交代录
          </Button>
        </Space>
      )}
    </Modal>
  );
}

export default DeliverableSignDialog;
