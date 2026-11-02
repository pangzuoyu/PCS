/**
 * 系统参数 MSW handlers 真跑测试（P9B-3 · T5 · 评审 I-2）。
 *
 * 守一条：**批量 PUT 是原子的** —— 缺任何一个键 ⇒ 404 且**一个键都不改**。
 *
 * ⚠️ 为什么需要这个文件：dev mock 此前是「边遍历边写」⇒ 缺键时**前面的键已经
 * 改了** ⇒ dev 里演示的是**半改状态**（真后端先全量校验再写 ⇒ 绝不这样）
 * ⇒ 而浏览器 QA 跑的就是这个 mock ⇒ mock 把本批的**头号硬约束**演示反了。
 *
 * 思路（仿 `heat_handlers.test.ts`）：复用 `src/mocks/systemSettings.ts` 的
 * 单一来源 fixtures + handlers，本地 setupServer，fetch 真请求。
 */
import { describe, it, expect, beforeAll, afterAll, beforeEach } from 'vitest';
import { setupServer } from 'msw/node';

import {
  resetMockSystemSettings,
  seedSystemSettings,
  systemSettingsHandlers,
} from '../../src/mocks/systemSettings';

const BASE = '/api/v1';
const BEARER = 'Bearer mock-token';

const server = setupServer(...systemSettingsHandlers);

describe('systemSettings mock —— 批量 PUT 的原子性（I-2）', () => {
  beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
  afterAll(() => server.close());
  beforeEach(() => {
    resetMockSystemSettings();
  });

  it('GET ⇒ 200 + 全部默认键', async () => {
    const res = await fetch(`${BASE}/system-settings`, { headers: { Authorization: BEARER } });
    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body.length).toBe(seedSystemSettings.length);
    expect(body.map((s: { setting_key: string }) => s.setting_key)).toContain(
      'session.timeout_minutes',
    );
  });

  it('PUT 全部存在的键 ⇒ 200 + 值被改', async () => {
    const res = await fetch(`${BASE}/system-settings`, {
      method: 'PUT',
      headers: { Authorization: BEARER, 'Content-Type': 'application/json' },
      body: JSON.stringify({ settings: { 'session.timeout_minutes': 45 } }),
    });
    expect(res.status).toBe(200);
    const row = seedSystemSettings.find((s) => s.setting_key === 'session.timeout_minutes');
    expect(row?.setting_value_json).toBe(45);
  });

  it('⚠️ PUT 含**不存在的键** ⇒ 404 且**另一个合法键的值没变**（原子）', async () => {
    const before = seedSystemSettings.find(
      (s) => s.setting_key === 'session.timeout_minutes',
    )?.setting_value_json;

    const res = await fetch(`${BASE}/system-settings`, {
      method: 'PUT',
      headers: { Authorization: BEARER, 'Content-Type': 'application/json' },
      body: JSON.stringify({
        settings: { 'session.timeout_minutes': 45, 'no.such.key': 1 },
      }),
    });

    expect(res.status).toBe(404);
    const body = await res.json();
    expect(body.code).toBe('SYSTEM_SETTING_NOT_FOUND');
    // ⚠️ **一个键都不改**（此前 mock 是边遍历边写 ⇒ 这里会是 45）
    const after = seedSystemSettings.find(
      (s) => s.setting_key === 'session.timeout_minutes',
    )?.setting_value_json;
    expect(after).toBe(before);
  });
});
