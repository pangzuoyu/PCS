/**
 * ResultEditDrawer —— 通用编辑抽屉（P9B-1 · SPEC §6.21 P9A-LCK-001~006）。
 *
 * ## 它管什么
 *
 * 取锁 → 心跳 → 三档基线 → 表单 → 保存 → 409 分流 → 关闭释放。
 * **6 个模块共用这一份**（差异全在 `module` 描述符里）。
 *
 * ## 三条最容易漏的
 *
 * 1. **基线三档**（RF-8）：`record_hash` 空 ⇒ 退到 `expected_updated_at`；
 *    两档皆无 ⇒ **该行不可编辑**（联系管理员），不是「保存时才发现」。
 * 2. **时间戳原样透传**（RF-9）：基线里的 `updated_at` **不过 `new Date()`**
 *    （PG 是微秒、JS `Date` 只到毫秒 ⇒ 过一次就**每次假 409**）。
 * 3. **保存后刷新基线**（RF-1）：保存会重算 `record_hash` ⇒ 不刷新的话
 *    **下一次保存必 409**（假冲突）。
 */
import { useEffect, useState } from 'react';
import {
  Alert,
  Button,
  Drawer,
  Form,
  Input,
  InputNumber,
  Modal,
  Space,
  Tooltip,
  Typography,
  message,
} from 'antd';

import { EditLockIndicator } from '../../components/common/EditLockIndicator';
import { EditConflictModal } from '../../components/common/EditConflictModal';
import { recordsApi } from '../../api/records';
import { extractConflict, extractPcsError, type ConflictDetail } from '../../api/errors';
import { useEditBaseline, isRowEditable } from '../../hooks/useEditBaseline';
import { useEditLock } from '../../hooks/useEditLock';
import { useDegradation } from '../../store/degradation';
import { useAuth } from '../../store/auth';
import {
  editableFieldDefs,
  type CommonResultRow,
  type ResultModule,
} from './resultModules';

interface Props {
  open: boolean;
  module: ResultModule;
  record: CommonResultRow & Record<string, unknown>;
  onClose: () => void;
  /** 保存成功后把**新的** `record_hash` 交回父级（父级就地更新列表，**不重拉**）。 */
  onSaved: (updated: { record_hash: string }) => void;
}

/** 表单初值：只取**可编辑字段**（`*_json` 与计算字段不进表单）。 */
function initialForm(
  module: ResultModule,
  record: CommonResultRow & Record<string, unknown>,
): Record<string, unknown> {
  const initial: Record<string, unknown> = {};
  for (const field of editableFieldDefs(module)) {
    const raw = record[field.key];
    initial[field.key] = raw === undefined || raw === null ? undefined : raw;
  }
  return initial;
}

export function ResultEditDrawer({
  open,
  module,
  record,
  onClose,
  onSaved,
}: Props): JSX.Element {
  const id = String(record[module.pk] ?? '');
  const [form, setForm] = useState<Record<string, unknown>>({});
  const [dirty, setDirty] = useState(false);
  const [saving, setSaving] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [conflict, setConflict] = useState<ConflictDetail | null>(null);
  const [confirmOpen, setConfirmOpen] = useState(false);
  // ⚠️ 保存成功后**刷新基线**（RF-1）：编辑会重算 `record_hash`，
  // 不刷新 ⇒ 下一次保存**必 409**（假冲突）。
  const [currentHash, setCurrentHash] = useState(record.record_hash ?? '');
  const setDegradation = useDegradation((s) => s.setMessage);

  useEffect(() => {
    if (!open) return;
    setForm(initialForm(module, record));
    setDirty(false);
    setErrorMsg(null);
    setCurrentHash(record.record_hash ?? '');
  }, [open, module, record]);

  const baseline = useEditBaseline({
    record_hash: currentHash,
    updated_at: record.updated_at,
    canEdit: isRowEditable(record.sign_status),
  });

  const lock = useEditLock({
    recordType: module.recordType,
    recordId: id,
    enabled: open,
    onDegraded: (m) => setDegradation(m),
  });

  // ⚠️ **页面卸载**时释放锁（RF-10）：否则同事会看到「张三 正在编辑」
  // 而张三 已经走了（锁要等 30min TTL 才回收）。
  //
  // ⚠️ 用 **`fetch(keepalive)`** 而不是 `navigator.sendBeacon`：
  // 后端 release 端点只认 **`Authorization: Bearer` 头**（`current_actor`），
  // 而 `sendBeacon` **无法带自定义头** ⇒ 必然 401 ⇒ 这条路径永远不生效。
  // `keepalive` 正是浏览器为「卸载期间发请求」提供的机制（卸载**不取消**它）。
  useEffect(() => {
    if (!open) return;
    const onPageHide = () => {
      const token = useAuth.getState().accessToken;
      if (!token) return;
      void fetch(`/api/v1/locks/${module.recordType}/${id}/release`, {
        method: 'POST',
        keepalive: true,
        headers: { Authorization: `Bearer ${token}` },
      }).catch(() => {
        // best-effort：失败一律忽略（锁靠 30min TTL 回收）
      });
    };
    window.addEventListener('pagehide', onPageHide);
    return () => window.removeEventListener('pagehide', onPageHide);
  }, [open, module.recordType, id]);

  function setField(key: string, value: unknown): void {
    setForm((prev) => ({ ...prev, [key]: value }));
    setDirty(true);
  }

  async function save(): Promise<void> {
    setSaving(true);
    setErrorMsg(null);
    try {
      // ⚠️ **显式**构造请求体（**不要** `{...changed, ...baseline}`）：
      // 展开会把 `disabled` / `reason` 也塞进去（后端 `extra="ignore"` 会
      // 静默丢弃，但那依赖后端策略）⇒ 显式构造是**不依赖**策略的做法。
      const body: Record<string, unknown> = {};
      for (const field of editableFieldDefs(module)) {
        const value = form[field.key];
        if (value !== undefined) body[field.key] = value;
      }
      // ⚠️ **只带判定出来的那一档**，且**原样透传**（RF-9）。
      if (baseline.expected_hash !== undefined) {
        body.expected_hash = baseline.expected_hash;
      }
      if (baseline.expected_updated_at !== undefined) {
        body.expected_updated_at = baseline.expected_updated_at;
      }

      const res = await recordsApi.patch<
        { record_hash?: string | null },
        Record<string, unknown>
      >(module.base, id, body);

      // ⚠️ 基线刷新（RF-1）：用响应里的**新** `record_hash`。
      setCurrentHash(res.record_hash ?? '');
      setDirty(false);
      message.success('已保存');
      onSaved({ record_hash: res.record_hash ?? '' });
    } catch (err) {
      const detail = extractConflict(err);
      if (detail) {
        // ⚠️ **不自动重试**（约束 5）：重试仍是 409，且把「冲突」掩盖成「抖动」。
        setConflict(detail);
        return;
      }
      setErrorMsg(extractPcsError(err)?.message ?? '保存失败');
    } finally {
      setSaving(false);
    }
  }

  async function discardAndRefresh(): Promise<void> {
    setConflict(null);
    try {
      const fresh = await recordsApi.get<CommonResultRow & { record_hash?: string | null }>(
        module.base,
        id,
      );
      setCurrentHash(fresh.record_hash ?? '');
      setForm(initialForm(module, fresh as CommonResultRow & Record<string, unknown>));
      setDirty(false);
    } catch {
      // 拿不到就保持原样（不静默清空用户的输入）
    }
  }

  async function closeNow(): Promise<void> {
    // ⚠️ release 是 **best-effort**：失败**一律忽略**（不弹窗、不阻断关闭）。
    await lock.release();
    onClose();
  }

  function requestClose(): void {
    if (dirty) {
      // ⚠️ 用**受控** `<Modal>` 而不是静态 `Modal.confirm(...)`：
      // 静态 API 走 `import()` 懒加载确认框实现 ⇒ 首次调用**慢到秒级**
      // （实测 4.2s）⇒ 交互像卡住。
      setConfirmOpen(true);
      return;
    }
    void closeNow();
  }

  const saveDisabledReason =
    baseline.reason === 'no-permission'
      ? `当前状态 ${record.sign_status ?? '未知'} 不可编辑`
      : baseline.reason === 'no-baseline'
        ? '该记录缺少并发校验基线，无法安全编辑，请联系管理员'
        : lock.readOnly
          ? '编辑锁不可用（他人正在编辑或锁已失效）'
          : undefined;

  return (
    <Drawer
      open={open}
      title={`${module.title} · 编辑`}
      onClose={requestClose}
      width={640}
      data-testid="result-edit-drawer"
      extra={
        <Space>
          <Button onClick={requestClose}>关闭</Button>
          <Tooltip title={saveDisabledReason}>
            {/* ⚠️ 套 `<span>`：Tooltip 挂在**禁用**按钮上不会弹出（禁用元素
             * 不派发鼠标事件）⇒ 用户看不到禁用原因。 */}
            <span>
              <Button
                type="primary"
                loading={saving}
                disabled={baseline.disabled || lock.readOnly}
                data-testid="result-save"
                onClick={() => void save()}
              >
                保存
              </Button>
            </span>
          </Tooltip>
        </Space>
      }
    >
      <EditLockIndicator state={lock.state} />
      {errorMsg && (
        <Alert type="error" showIcon message={errorMsg} data-testid="result-save-error" />
      )}
      <Form layout="vertical" style={{ marginTop: 16 }}>
        {editableFieldDefs(module).map((field) => (
          <Form.Item key={field.key} label={field.label} name={field.key}>
            {field.kind === 'number' ? (
              <InputNumber
                data-testid={`field-${field.key}`}
                value={form[field.key] as number | undefined}
                onChange={(v) => setField(field.key, v)}
                style={{ width: '100%' }}
              />
            ) : (
              <Input
                data-testid={`field-${field.key}`}
                value={(form[field.key] as string | undefined) ?? ''}
                onChange={(e) => setField(field.key, e.target.value)}
              />
            )}
          </Form.Item>
        ))}
      </Form>
      <Typography.Text type="secondary" data-testid="result-baseline">
        基线：{baseline.expected_hash ?? baseline.expected_updated_at ?? '（无）'}
      </Typography.Text>
      <EditConflictModal
        open={conflict !== null}
        conflict={conflict}
        onRefresh={() => void discardAndRefresh()}
      />
      <Modal
        open={confirmOpen}
        title="有未保存的修改"
        okText="放弃并关闭"
        cancelText="继续编辑"
        onCancel={() => setConfirmOpen(false)}
        onOk={() => {
          setConfirmOpen(false);
          void closeNow();
        }}
      >
        确认关闭将放弃修改并释放编辑锁。
      </Modal>
    </Drawer>
  );
}
