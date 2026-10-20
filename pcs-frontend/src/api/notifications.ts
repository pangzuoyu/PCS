/**
 * 通知 API 客户端（P9A Z 收口 · SPEC §6.20 · ADR-0049 §①）。
 *
 * ⚠️ **类型全部来自生成的 `api.d.ts`，不手写**（`src/api/reportBuilder.ts`
 * 的规矩）：手写的 `src/types/*.ts` 已经漂移过一次
 * （本文件接手前，前端把 `GET /notifications` 的响应当**自造数组**用 ⇒
 * 生产构建下 `MainLayout` 整个壳崩，详见 TODO-065）。
 *
 * 端点（后端 `app/api/v1/notifications.py`）：
 * - `GET  /notifications`                    —— 我的通知（断线兜底路径）
 * - `PUT  /notifications/{notification_id}/read` —— 标记已读（幂等）
 */
import { api } from './client';
import type { components } from '../types/api';

export type NotificationItem = components['schemas']['NotificationItemResponse'];
export type NotificationList = components['schemas']['NotificationListResponse'];
export type NotificationDetail = components['schemas']['NotificationDetail'];

export const notificationsApi = {
  /**
   * 拉通知列表。
   *
   * @param after 断线前最后见到的时刻（ISO）—— 只取比它新的。
   * @param limit 服务端上限 200。
   */
  list: (params?: { after?: string; limit?: number }): Promise<NotificationList> =>
    api.get<NotificationList>('/notifications', { params }).then((r) => r.data),

  /**
   * 标记已读（**幂等** —— 重复调用不改 `read_at`）。
   *
   * ⚠️ 服务端对「不存在」与「是别人的」返**同一个** code（不泄露存在性），
   * 所以前端**不得**靠错误码区分「已不存在」与「无权限」。
   */
  markRead: (notificationId: string): Promise<NotificationItem> =>
    api
      .put<NotificationItem>(`/notifications/${notificationId}/read`)
      .then((r) => r.data),
};

/**
 * `kind` 的**呈现**映射（标签 + 配色）。
 *
 * ⚠️ **这四值是后端的 `NotificationKind` 全集**（`SIGN_COMPLETED` /
 * `STEP_RETURNED` / `PROXY_RECORDED` / `CHANGE_NOTICE_APPROVED`），
 * 前端**不得**另造分类词表（SPEC §6.20）。呈现层可自由，**词表不行**。
 */
export const NOTIFICATION_KIND_LABEL: Record<string, string> = {
  SIGN_COMPLETED: '签署完成',
  STEP_RETURNED: '退回',
  PROXY_RECORDED: '代录已录',
  CHANGE_NOTICE_APPROVED: '变更已批准',
};

export const NOTIFICATION_KIND_COLOR: Record<string, string> = {
  SIGN_COMPLETED: 'green',
  STEP_RETURNED: 'orange',
  PROXY_RECORDED: 'blue',
  CHANGE_NOTICE_APPROVED: 'cyan',
};

/** 「变更」分组的唯一判据（SPEC §6.20 的分组来源表）。 */
export const CHANGE_NOTICE_KIND = 'CHANGE_NOTICE_APPROVED';

/** 未读判定 = **`read_at` 为 null**（不是自造的 `unread` 布尔）。 */
export function isUnread(item: NotificationItem): boolean {
  return item.read_at === null || item.read_at === undefined;
}
