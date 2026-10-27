/**
 * ADMIN 用户管理客户端 —— P9B-2 · SPEC §7.20 / P9A-ADM-001/002。
 *
 * ⚠️ 三个端点**全部限 SYSTEM_ADMIN**（`admin_users.py` 的 `_ADMIN_ROLES`）
 * ⇒ 前端按角色隐藏入口，但**鉴权在后端**（前端隐藏是体验，后端 403 是边界）。
 */
import { api } from './client';
import type { components } from '../types/api';

export type AdminUser = components['schemas']['AdminUserOut'];
export type UserDisabled = components['schemas']['UserDisabledOut'];
export type AdSyncResult = components['schemas']['AdSyncResultOut'];

export const adminApi = {
  listUsers: (): Promise<AdminUser[]> =>
    api.get<AdminUser[]>('/admin/users').then((r) => r.data),

  disableUser: (userId: string): Promise<UserDisabled> =>
    api.put<UserDisabled>(`/admin/users/${userId}/disable`).then((r) => r.data),

  syncAdUsers: (): Promise<AdSyncResult> =>
    api.post<AdSyncResult>('/admin/users/sync').then((r) => r.data),
};
