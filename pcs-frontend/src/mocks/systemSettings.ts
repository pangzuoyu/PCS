/**
 * 系统参数的 seed + MSW handlers（P9B-3 · T5）。
 *
 * ⚠️ 响应体一律取**契约类型**（`components['schemas'][...]`）—— 手写自由 dict
 * 就是 bug-2040 的根源（mock 与真端点不同源 ⇒ 漂移被藏住）。
 *
 * ⚠️ **有状态**：PUT 真的改内存里的种子 ⇒ 页面上点「保存」后能看到值变了 ⇒
 * 人工验收不会误判「按钮没用」。
 *
 * ⚠️ 这组端点**已在 OpenAPI 契约里**（P9B-3 T4 交付）⇒ 形状必须与真端点一致。
 */
import { http, HttpResponse } from 'msw';

import type { components } from '../types/api';

type SystemSettingOut = components['schemas']['SystemSettingOut'];
type SystemSettingBatchOut = components['schemas']['SystemSettingBatchOut'];
type SystemSettingBatchIn = components['schemas']['SystemSettingBatchIn'];

/** 默认 7 键的**定义**（与后端 `DEFAULT_SETTINGS` 同清单）。 */
const DEFAULT_SEED: Omit<SystemSettingOut, 'updated_at'>[] = [
  { setting_key: 'session.timeout_minutes', setting_value_json: 30, description: '会话超时（分钟）' },
  { setting_key: 'notification.retention_days', setting_value_json: 30, description: '已读通知保留天数' },
  { setting_key: 'edit_lock.ttl_minutes', setting_value_json: 30, description: '编辑锁有效期（分钟）' },
  { setting_key: 'edit_lock.renew_enabled', setting_value_json: true, description: '编辑锁自动续期' },
  { setting_key: 'record.self_check_allowed', setting_value_json: false, description: '是否允许设计兼任校核' },
  { setting_key: 'equip_list.auto_sync_enabled', setting_value_json: true, description: 'CHECKED 触发设备表同步' },
  { setting_key: 'stream.batch_submit_limit', setting_value_json: 100, description: '物流批量提交上限（P9B-3b 用）' },
];

const SEED_UPDATED_AT = '2026-11-03T01:00:00Z';

/** 内存态（**有状态** ⇒ dev 里点「保存」能看到值变了）。 */
export const seedSystemSettings: SystemSettingOut[] = DEFAULT_SEED.map((row) => ({
  ...row,
  updated_at: SEED_UPDATED_AT,
}));

function isAuthed(request: Request): boolean {
  return request.headers.get('Authorization') !== null;
}

/** 把 mock 状态复位（测试与 HMR 用）。 */
export function resetMockSystemSettings(): void {
  seedSystemSettings.splice(
    0,
    seedSystemSettings.length,
    ...DEFAULT_SEED.map((row) => ({ ...row, updated_at: SEED_UPDATED_AT })),
  );
}

export const systemSettingsHandlers = [
  http.get('/api/v1/system-settings', ({ request }) => {
    if (!isAuthed(request)) {
      return HttpResponse.json({ code: 'MISSING_BEARER' }, { status: 401 });
    }
    return HttpResponse.json(seedSystemSettings);
  }),

  http.put('/api/v1/system-settings', async ({ request }) => {
    if (!isAuthed(request)) {
      return HttpResponse.json({ code: 'MISSING_BEARER' }, { status: 401 });
    }
    const body = (await request.json()) as SystemSettingBatchIn;
    const settings = body.settings ?? {};
    const updated: SystemSettingOut[] = [];
    for (const [key, value] of Object.entries(settings)) {
      const row = seedSystemSettings.find((s) => s.setting_key === key);
      // ⚠️ 照抄后端语义：键不存在 ⇒ 404 且**一个键都不改**（原子）。
      if (!row) {
        return HttpResponse.json(
          {
            code: 'SYSTEM_SETTING_NOT_FOUND',
            message: `系统参数不存在：${key}`,
            detail: { missing: [key] },
            trace_id: 'mock',
          },
          { status: 404 },
        );
      }
      row.setting_value_json = value;
      row.updated_at = new Date().toISOString();
      updated.push(row);
    }
    const out: SystemSettingBatchOut = { updated };
    return HttpResponse.json(out);
  }),
];
