/**
 * EditLockIndicator —— 编辑锁状态提示（P9B-1 · SPEC §6.21 P9A-LCK-003）。
 *
 * ## 只在两种状态下渲染
 *
 * - `blocked` —— **他人持锁** ⇒ 「{holder} 正在编辑（{相对时间}）」
 * - `expired` —— 锁已失效 ⇒ 「编辑锁已失效，请重新进入编辑」
 *
 * `held` / `degraded` / `idle` **不渲染**（降级横幅在顶栏，见 §6.21 P9A-LCK-004）。
 *
 * ## ⚠️ 禁用原因写「谁在改」，**不写「无权限」**
 *
 * 这是**并发提示**，不是权限问题 —— 把两者混同会让用户去找管理员，
 * 而真正该做的是**等一下**（SPEC §6.21 P9A-LCK-003）。
 *
 * ⚠️ holder 取**后端原文**，前端不猜、不缓存。
 */
import { Alert } from 'antd';

import type { EditLockState } from '../../hooks/useEditLock';

/**
 * 相对时间（展示用）。
 *
 * ⚠️ **只用于展示**：基线里的时间戳**必须原样透传**（不过 `new Date()`）——
 * PG `TIMESTAMPTZ` 是微秒、JS `Date` 只到毫秒 ⇒ 过一次 `Date` 就每次假 409。
 * 这里解析的是**锁的持有时刻**（不参与任何比对），与基线无关。
 */
function relativeTime(iso: string): string {
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return iso;
  const diff = Date.now() - then;
  if (diff < 0) return '刚刚';
  if (diff < 60_000) return '刚刚';
  const minutes = Math.floor(diff / 60_000);
  if (minutes < 60) return `${minutes} 分钟前`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours} 小时前`;
  return `${Math.floor(hours / 24)} 天前`;
}

interface Props {
  state: EditLockState;
}

export function EditLockIndicator({ state }: Props): JSX.Element | null {
  if (state.status === 'blocked') {
    const who = state.holder?.username || state.holder?.user_id || '他人';
    const when = state.holder?.acquired_at ? relativeTime(state.holder.acquired_at) : '';
    return (
      <Alert
        type="warning"
        showIcon
        data-testid="edit-lock-indicator"
        message={`${who} 正在编辑${when ? `（${when}）` : ''}`}
      />
    );
  }
  if (state.status === 'expired') {
    return (
      <Alert
        type="error"
        showIcon
        data-testid="edit-lock-indicator"
        message="编辑锁已失效，请重新进入编辑"
      />
    );
  }
  return null;
}
