/**
 * EditConflictModal —— 409 保存冲突弹窗（P9B-1 · SPEC §6.21 P9A-LCK-005）。
 *
 * ## 按 `basis` 三值分流
 *
 * | basis | 原因 | 出口 |
 * |---|---|---|
 * | `record_hash` | 别人改过这条记录 | [查看差异] / [放弃我的修改并刷新] |
 * | `updated_at` | 别人改过这条记录（只知道行被改过） | [查看差异] / [放弃我的修改并刷新] |
 * | `no_baseline` | **这条记录压根没法校验并发** | [刷新后重试] / [联系管理员] |
 * | `unknown` | 说不清 | [刷新后重试] |
 *
 * ⚠️ **`no_baseline` 绝不能显示成「已被他人修改」** —— 那是**两回事**：
 * 一个是「有人改过」，一个是「没法知道有没有人改过」。
 *
 * ⚠️ **不得自动重试**（ADR-0048 §⑦）：重试仍是 409，且会把「冲突」
 * 掩盖成「网络抖动」。
 *
 * ⚠️ **`changed_by` / `changed_at` 为 null ⇒ 显示「未知」**，**不得**拿
 * `updated_at` 冒充（ADR-0048 §⑦）。
 */
import { useState } from 'react';
import { Button, Modal, Space, Typography } from 'antd';

import { conflictKind, type ConflictDetail } from '../../api/errors';
import { listRecordEdits } from '../../api/audit';

interface Props {
  open: boolean;
  conflict: ConflictDetail | null;
  /** 「放弃我的修改并刷新」/「刷新后重试」—— 两种 basis 的动作相同、文案不同。 */
  onRefresh: () => void;
  /** 「联系管理员」出口（只有 `no_baseline` 有）。 */
  onContactAdmin?: () => void;
}

/** 403 = 无权（编辑审计限 SYSTEM_ADMIN）。 */
function isForbidden(err: unknown): boolean {
  if (typeof err !== 'object' || err === null) return false;
  const response = (err as { response?: { status?: number } }).response;
  return response?.status === 403;
}

export function EditConflictModal({
  open,
  conflict,
  onRefresh,
  onContactAdmin,
}: Props): JSX.Element {
  const [diff, setDiff] = useState<string[] | null>(null);
  const [diffError, setDiffError] = useState<string | null>(null);

  const kind = conflictKind(conflict?.basis);
  const canViewDiff = kind === 'record_hash' || kind === 'updated_at';

  let message: string;
  if (kind === 'no_baseline') {
    message = '该记录缺少并发校验基线，无法安全保存';
  } else if (kind === 'unknown') {
    message = '说不清是否冲突';
  } else {
    const who = conflict?.changed_by || '未知';
    const when = conflict?.changed_at || '未知';
    message = `${who} 于 ${when} 修改了这条记录`;
  }

  async function showDiff() {
    if (!conflict) return;
    setDiffError(null);
    try {
      const res = await listRecordEdits({
        resource_type: conflict.record_type,
        resource_id: conflict.record_id,
      });
      const fields = res.items.flatMap((item) => {
        const raw = item.detail_json?.changed_fields;
        return Array.isArray(raw) ? (raw as string[]) : [];
      });
      setDiff(fields);
    } catch (err) {
      // ⚠️ 编辑审计限 SYSTEM_ADMIN ⇒ 普通用户 403 ⇒ 优雅降级，
      // 但**保留** [放弃我的修改并刷新] 出口（不能把人堵死）。
      setDiffError(
        isForbidden(err) ? '无权查看差异（需系统管理员）' : '暂时无法查看差异',
      );
    }
  }

  return (
    <Modal
      open={open}
      title="保存冲突"
      onCancel={onRefresh}
      footer={
        <Space>
          {canViewDiff && (
            <Button data-testid="conflict-view-diff" onClick={() => void showDiff()}>
              查看差异
            </Button>
          )}
          {kind === 'no_baseline' && (
            <Button
              data-testid="conflict-contact-admin"
              onClick={() => onContactAdmin?.()}
            >
              联系管理员
            </Button>
          )}
          <Button
            type="primary"
            data-testid="conflict-refresh"
            onClick={onRefresh}
          >
            {canViewDiff ? '放弃我的修改并刷新' : '刷新后重试'}
          </Button>
        </Space>
      }
    >
      <div data-testid="edit-conflict-modal">
        <Typography.Paragraph>{message}</Typography.Paragraph>
        {diffError && (
          <Typography.Text type="secondary" data-testid="conflict-diff-error">
            {diffError}
          </Typography.Text>
        )}
        {diff && (
          <Typography.Text data-testid="conflict-diff">
            变更字段：{diff.length > 0 ? diff.join('、') : '（无字段级记录）'}
          </Typography.Text>
        )}
      </div>
    </Modal>
  );
}
