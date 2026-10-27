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
import { recordEditsApi } from '../../api/audit';

interface Props {
  open: boolean;
  conflict: ConflictDetail | null;
  /** 「放弃我的修改并刷新」/「刷新后重试」—— 两种 basis 的动作相同、文案不同。 */
  onRefresh: () => void;
  /** 「联系管理员」出口（只有 `no_baseline` 有）。 */
  onContactAdmin?: () => void;
}

/** 403 = 无权（这条记录不在你的项目里）。 */
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
      // ⚠️ **按项目守卫**的端点（P9B-2 · R-14）⇒ **普通用户点得开**
      //    （原先打 SYSTEM_ADMIN-only 的 `/audit-logs` ⇒ 普通用户 403）。
      const res = await recordEditsApi.list(
        conflict.record_type,
        conflict.record_id,
      );
      // ⚠️ `changed_fields` 在**顶层**（新端点已把 `detail_json` 摊平）。
      const fields = res.items.flatMap((item) =>
        Array.isArray(item.changed_fields) ? item.changed_fields : [],
      );
      setDiff(fields);
    } catch (err) {
      // 优雅降级，但**保留** [放弃我的修改并刷新] 出口（不能把人堵死）。
      setDiffError(isForbidden(err) ? '无权查看差异' : '暂时无法查看差异');
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
          {kind === 'no_baseline' &&
            (onContactAdmin ? (
              <Button
                data-testid="conflict-contact-admin"
                onClick={() => onContactAdmin()}
              >
                联系管理员
              </Button>
            ) : (
              // ⚠️ **不渲染死按钮**（TODO-067 #1）：`onContactAdmin` 可选 ⇒
              //    宿主没传时点了**什么都不会发生** ⇒ 用户以为功能坏了。
              //    ⇒ 改成一条**真实**的出路文案。
              <Typography.Text
                type="secondary"
                data-testid="conflict-contact-admin-hint"
              >
                请联系管理员补齐该记录的并发基线后重试
              </Typography.Text>
            ))}
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
