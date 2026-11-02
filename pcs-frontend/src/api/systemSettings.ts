/**
 * 系统参数客户端（§7.20.1 · P9B-3）。
 *
 * ⚠️ 类型**契约派生**（`components['schemas'][...]`）—— 不手写 union
 * （手写 = 与后端脱钩 = bug-2040 那类漂移根因）。
 *
 * ⚠️ `save()` **一次 PUT 提交全部改动**（委员会硬约束 1）—— 不做逐键 PATCH
 * （那会让「保存」变成 N 个请求，且中途失败留半改状态）。
 */
import { api } from './client';
import type { components } from '../types/api';

export type SystemSettingOut = components['schemas']['SystemSettingOut'];
export type SystemSettingBatchOut = components['schemas']['SystemSettingBatchOut'];
/** `setting_key → 新值` 的映射（值是 JSONB，形态随键而异）。 */
export type SystemSettingValueMap = components['schemas']['SystemSettingValueMap'];

export const systemSettingsApi = {
  list: (): Promise<SystemSettingOut[]> =>
    api.get<SystemSettingOut[]>('/system-settings').then((r) => r.data),

  save: (settings: SystemSettingValueMap): Promise<SystemSettingBatchOut> =>
    api.put<SystemSettingBatchOut>('/system-settings', { settings }).then((r) => r.data),
};
