/**
 * ChangeNoticeAction —— 结果记录行上的**变更动作**（TODO-083 · P9A-DLV-011 T4 的前端）。
 *
 * ## 为什么是「按状态只给一个按钮」
 *
 * 变更是一条**状态机**，不是三个并列的按钮：
 *
 * ```
 * CHECKED --变更申请--> CHANGE_PENDING --提交变更完成--> CHANGED --创建变更单--> 变更单
 * ```
 *
 * ⚠️ 三个端点对**非当前态**都返 409（`RECORD_INVALID_TRANSITION`）⇒
 * 把三个按钮同时显示出来 = 让用户去撞状态机。
 * ⇒ **按 `sign_status` 只渲染当前那一步**的按钮（UI-SPEC §6.3 的状态→按钮表）。
 *
 * ⚠️ **建变更单要 FORMAL 工作区**（后端 403 `WORKSPACE_TYPE_NOT_ALLOWED`）⇒
 * 个人草稿区里这一步会被拒 ⇒ 错误消息**原样展示**（后端已经说清楚了）。
 *
 * ## CHANGED 态为什么还要能「作废」
 *
 * 记录状态**看不出来**有没有开着的变更单（两种情况记录都是 CHANGED）⇒
 * 打开弹窗时先查一次「这张记录当前开着的变更单」（`GET .../change-notice`）：
 * · 没有 ⇒ 照常**创建**；
 * · 有 ⇒ **不能**再建一张（后端会 409 `CHANGE_NOTICE_ALREADY_EXISTS`）⇒ 弹窗
 *   改成「作废这张变更单」的表单（理由必填）⇒ 作废后记录**不动**（保持
 *   CHANGED）⇒ 用户可以另起一张。
 *
 * ⚠️ 查询**只在打开弹窗时**发（不是每行渲染时发）⇒ 列表页不会有 N+1 请求。
 *
 * ## 为什么成功后要回调更新列表
 *
 * 记录状态变了（CHECKED → CHANGE_PENDING …）⇒ 不更新列表的话，按钮**还停在
 * 旧状态** ⇒ 用户能对同一条记录连点两次 ⇒ 第二次 409。
 */
import { useState } from 'react';
import { Button, Form, Input, Modal, Select, Tooltip, message } from 'antd';

import { extractPcsError } from '../../api/errors';
import { useAuth } from '../../store/auth';
import {
  CHANGE_TYPE_LABELS,
  CHANGE_TYPES,
  changeNoticesApi,
} from '../../api/changeNotices';
import type { ChangeNoticeOpenResponse } from '../../api/changeNotices';
import type { ResultModule } from './resultModules';

export type ChangeRow = Record<string, unknown> & { sign_status?: string | null };

interface Props {
  module: ResultModule;
  row: ChangeRow;
  /**
   * 允许执行「建单 / 作废」的**全局角色**（来自 `meta/state-machine` 的
   * `INITIATE_CHANGE` 转移）。
   *
   * ⚠️ `null` = **还不知道**（meta 没拉到）⇒ **不禁用**（不猜）⇒ 后端 403 兜底。
   * ⚠️ 页面**取一次** meta 传下来 ⇒ 不是每行一次 ⇒ 无 N+1。
   */
  allowedRoles?: string[] | null;
  /** 成功后把新状态回传（列表就地更新，不重拉）。 */
  onStatusChange: (recordId: string, nextStatus: string) => void;
}

interface NoticeFormValue {
  change_type: string;
  reason: string;
}

interface ReasonFormValue {
  reason: string;
}

/**
 * 行内按钮的文案（**只**剩 CHANGED 态）。
 *
 * ⚠️ **R-12b**：`CHECKED → 变更申请` 与 `CHANGE_PENDING → 提交变更完成` 是
 * **状态机事件** ⇒ 归 `RecordActions`（meta 驱动、详情抽屉里）⇒ 行内**不再**
 * 渲染 ⇒ 同一状态**不会有两个入口**（两份映射 = 用户不知道该点哪个）。
 * ⇒ 行内只留**两个非状态机动作**：`change-notice`（建单）/ `change-notice/cancel`
 * （作废）—— 它们都发生在 **CHANGED** 态。
 */
const ACTION_TEXT: Record<string, string> = {
  CHANGED: '创建变更单',
};

export function ChangeNoticeAction({
  module,
  row,
  allowedRoles,
  onStatusChange,
}: Props): JSX.Element | null {
  const [open, setOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  /** 该记录当前**开着**的变更单（null = 还没查 / 没有）。 */
  const [openNotice, setOpenNotice] = useState<ChangeNoticeOpenResponse | null>(null);
  const [reasonForm] = Form.useForm<ReasonFormValue>();
  const [noticeForm] = Form.useForm<NoticeFormValue>();

  // ⚠️ **hook 必须在 early return 之前**（React Hooks 规则）
  const role = useAuth((s) => s.role);
  const status = row.sign_status ?? '';
  const actionText = ACTION_TEXT[status];
  if (!actionText) return null;

  const recordId = String(row[module.pk] ?? '');

  /** 打开弹窗 ⇒ 查一次「这张记录当前开着的变更单」（只有 CHANGED 态需要）。 */
  async function openModal(): Promise<void> {
    setError(null);
    setOpen(true);
    if (status !== 'CHANGED') return;
    try {
      const summary = await changeNoticesApi.open(module.recordType, recordId);
      setOpenNotice(summary);
    } catch (err) {
      const env = extractPcsError(err);
      setError(env?.message ?? '读取变更单失败');
    }
  }

  async function submit(): Promise<void> {
    setSaving(true);
    setError(null);
    try {
      if (status === 'CHECKED') {
        const values = await reasonForm.validateFields();
        const res = await changeNoticesApi.initiate(module.recordType, recordId, values.reason);
        onStatusChange(recordId, res.to_status);
      } else if (status === 'CHANGE_PENDING') {
        const values = await reasonForm.validateFields();
        const res = await changeNoticesApi.apply(module.recordType, recordId, values.reason);
        onStatusChange(recordId, res.to_status);
      } else if (openNotice?.has_open_notice) {
        // ⚠️ 已经有开着的变更单 ⇒ 只能**作废**它（再建一张会被后端 409 挡掉）
        const values = await reasonForm.validateFields();
        const res = await changeNoticesApi.cancel(
          module.recordType,
          recordId,
          values.reason,
        );
        message.success(`变更单已作废：${res.doc_no}`);
        setOpenNotice(null);
        // ⚠️ 作废的是**单据**，记录**不动**（仍 CHANGED）⇒ 状态不变
        onStatusChange(recordId, 'CHANGED');
      } else {
        const values = await noticeForm.validateFields();
        const res = await changeNoticesApi.create(module.recordType, recordId, {
          change_type: values.change_type as (typeof CHANGE_TYPES)[number],
          reason: values.reason,
          triggered_by: 'MANUAL',
        });
        message.success(`变更单已创建：${res.doc_no}`);
        onStatusChange(recordId, 'CHANGED');
      }
      setOpen(false);
      reasonForm.resetFields();
      noticeForm.resetFields();
    } catch (err) {
      const env = extractPcsError(err);
      // ⚠️ 校验错误（本地表单）不该被当成后端错误展示
      if (!env) {
        setError('操作失败');
        return;
      }
      setError(env.message ?? '操作失败');
    } finally {
      setSaving(false);
    }
  }

  // ⚠️ **角色闸**（RF-1）：后端 `change-notice` 的 ACL = `INITIATE_CHANGE` 的
  //    `allowed_roles` ⇒ 角色不够就别让用户点了 403。
  const roleOk = !allowedRoles || !role || allowedRoles.includes(role);
  const roleHint = roleOk
    ? ''
    : `当前角色（${role ?? '未知'}）不可执行此操作（需 ${allowedRoles?.join(' / ')}）`;

  return (
    <>
      <Tooltip title={roleHint}>
        {/* ⚠️ Tooltip 包 **span**：disabled 的 Button 不派发鼠标事件 */}
        <span>
          <Button
            size="small"
            onClick={() => void openModal()}
            disabled={!roleOk}
            data-testid="change-notice-action"
          >
            {actionText}
          </Button>
        </span>
      </Tooltip>
      {/* ⚠️ antd 的 Tooltip **不把 props 转发到 DOM** ⇒ 禁用原因另外渲染一个
          节点（视觉隐藏）⇒ 断言能读到「为什么禁用」。 */}
      {roleHint && (
        <span style={{ display: 'none' }} data-testid="change-notice-action-hint">
          {roleHint}
        </span>
      )}
      <Modal
        title={openNotice?.has_open_notice ? `作废变更单（${openNotice.doc_no ?? ''}）` : actionText}
        open={open}
        onCancel={() => setOpen(false)}
        onOk={() => void submit()}
        okText={openNotice?.has_open_notice ? '作废变更单' : undefined}
        confirmLoading={saving}
        // ⚠️ antd 5.29 起 `destroyOnClose` 已弃用（控制台报错）⇒ 用 `destroyOnHidden`
        destroyOnHidden
      >
        {error && (
          <p style={{ color: 'var(--pcs-danger, #cf1322)' }} data-testid="change-notice-error">
            {error}
          </p>
        )}
        {status === 'CHANGED' && openNotice?.has_open_notice ? (
          <>
            <p data-testid="change-notice-open-hint">
              这张记录已有一张开着的变更单（{openNotice.doc_no ?? ''}）⇒ 不能再建一张
              （后端会 409）；要换一张请先**作废**它（作废**不**动记录本身）。
            </p>
            <Form form={reasonForm} layout="vertical">
              <Form.Item
                name="reason"
                label="作废理由"
                rules={[{ required: true, message: '请填作废理由' }]}
              >
                <Input.TextArea rows={3} maxLength={2000} showCount />
              </Form.Item>
            </Form>
          </>
        ) : status === 'CHANGED' ? (
          <Form form={noticeForm} layout="vertical">
            <Form.Item
              name="change_type"
              label="变更类型"
              initialValue="DATA_CORRECTION"
              rules={[{ required: true, message: '请选变更类型' }]}
            >
              <Select
                options={CHANGE_TYPES.map((t) => ({ value: t, label: CHANGE_TYPE_LABELS[t] ?? t }))}
              />
            </Form.Item>
            <Form.Item
              name="reason"
              label="变更原因"
              rules={[{ required: true, message: '请填变更原因' }]}
            >
              <Input.TextArea rows={3} maxLength={2000} showCount />
            </Form.Item>
          </Form>
        ) : (
          <Form form={reasonForm} layout="vertical">
            <Form.Item
              name="reason"
              label="原因"
              rules={[{ required: true, message: '请填原因' }]}
            >
              <Input.TextArea rows={3} maxLength={2000} showCount />
            </Form.Item>
          </Form>
        )}
      </Modal>
    </>
  );
}

export default ChangeNoticeAction;
