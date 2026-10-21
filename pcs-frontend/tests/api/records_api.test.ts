/**
 * 记录域 API 客户端的**请求契约**（P9B-1 Task T1）。
 *
 * ## 这组测试抓的是三件事
 *
 * 1. **漏传并发基线**（SPEC §6.21 P9A-LCK-006）：PATCH 必须带 `expected_hash`，
 *    不带 ⇒ 后端一律 409，而症状是「保存总是失败」，**不指向漏传**。
 * 2. **时间戳被 `new Date()` 削过**（RF-9）：PG `TIMESTAMPTZ` 是**微秒**，
 *    JS `Date` 只到**毫秒** ⇒ 过一次 `Date` 就**每次假 409**。
 * 3. **基线字段名漂成 camelCase**（RF-13）：`expectedHash` ⇒ **TypeScript 不报错**
 *    （实测 2026-10-21 编译通过）⇒ 请求体里没有 `expected_hash` ⇒ 后端
 *    `expected_hash is None` ⇒ **每次保存 409 `no_baseline`**。
 *    ⇒ 这条只能靠**断言请求体**抓（断言 hook 返回值抓不到）。
 *
 * 断言方式：MSW node server 拦真实请求，把 body 捕获进闭包变量
 * （仿 `tests/api/edit_lock_api.test.ts` 的既有套路）。
 *
 * ⚠️ **不要 mock api 模块**：那会把这组测试变成「测 mock 的行为」。
 * 这里 mock 的是**服务端**，被测的是**我们发出去的 body**。
 */
import { describe, it, expect, beforeAll, afterAll, beforeEach } from 'vitest';
import { http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';

import { recordsApi, RESULT_BASES, EDITABLE_RECORD_TYPES } from '../../src/api/records';
import type { components } from '../../src/types/api';

const RECORD_ID = '11111111-2222-3333-4444-555555555555';
const CURRENT_HASH = 'a3f9c21d8b7e6f50';
const NEW_HASH = 'ffffffffffffffff';

let lastBody: unknown = null;
let lastListUrl = '';

/**
 * mock 的响应体**用生成的类型标注**（Global Constraint 2）。
 *
 * ⚠️ 这正是 bug-2040 的正确修法：mock 与真端点**不同源** ⇒ 契约漂移被藏住
 * ⇒ 只有生产构建才炸。手写自由 dict 就会重新引入同一个洞。
 */
const MOCK_COST_EST = {
  result_id: RECORD_ID,
  equipment_id: '99999999-8888-7777-6666-555555555555',
  estimated_cost: 35,
  currency: 'USD',
  cost_index_year: 2019,
  record_hash: CURRENT_HASH,
  project_id: '00000000-0000-0000-0000-000000000001',
  created_at: '2026-10-20T10:22:31Z',
} satisfies components['schemas']['CostEstResultResponse'];

const server = setupServer(
  http.get('/api/v1/cost-est/results', ({ request }) => {
    lastListUrl = request.url;
    return HttpResponse.json({ items: [MOCK_COST_EST], total: 1, skip: 0, limit: 50 });
  }),
  http.get('/api/v1/filtration/results', ({ request }) => {
    lastListUrl = request.url;
    return HttpResponse.json({ items: [], total: 0, skip: 0, limit: 50 });
  }),
  http.get('/api/v1/cool-tower/results', ({ request }) => {
    lastListUrl = request.url;
    return HttpResponse.json({ items: [], total: 0, offset: 0, limit: 100 });
  }),
  http.patch('/api/v1/cost-est/results/:id', async ({ request }) => {
    lastBody = await request.json();
    // 保存成功后返回**新的** record_hash ⇒ 前端靠它刷新基线（RF-1）
    return HttpResponse.json({ ...MOCK_COST_EST, record_hash: NEW_HASH });
  }),
);

describe('recordsApi —— PATCH 必须带并发基线（P9B-1 T1）', () => {
  beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
  afterAll(() => server.close());
  beforeEach(() => {
    lastBody = null;
    lastListUrl = '';
  });

  it('PATCH 必须带 expected_hash —— 漏了后端一律 409，而症状是「保存总是失败」', async () => {
    await recordsApi.patch('/cost-est/results', RECORD_ID, {
      estimated_cost: 35,
      expected_hash: CURRENT_HASH,
    });
    expect(lastBody).not.toBeNull();
    const body = lastBody as Record<string, unknown>;
    // ⚠️ 这条断言就是整组测试存在的理由
    expect(body.expected_hash).toBe(CURRENT_HASH);
  });

  it('基线的 expected_updated_at **原样透传**（不落 new Date()）—— 微秒被截成毫秒 ⇒ 每次假 409', async () => {
    const raw = '2026-10-20T10:22:31.123456+08:00';
    await recordsApi.patch('/cost-est/results', RECORD_ID, { expected_updated_at: raw });
    expect((lastBody as Record<string, unknown>).expected_updated_at).toBe(raw);
    // ⚠️ 断言**逐字相等**（不是 toEqual(new Date(raw).toISOString())）
  });

  it('⚠️ 基线字段名是 snake_case（RF-13）—— expectedHash 会被后端当成「没传基线」', async () => {
    await recordsApi.patch('/cost-est/results', RECORD_ID, {
      estimated_cost: 35,
      expected_hash: CURRENT_HASH,
    });
    const body = lastBody as Record<string, unknown>;
    expect(body.expected_hash).toBe(CURRENT_HASH);
    expect(body.expectedHash).toBeUndefined();
  });

  it('PATCH 的业务字段与基线字段**不混**（基线不落进业务 payload）', async () => {
    await recordsApi.patch('/cost-est/results', RECORD_ID, {
      estimated_cost: 35,
      currency: 'EUR',
      expected_hash: CURRENT_HASH,
    });
    const body = lastBody as Record<string, unknown>;
    expect(body).toMatchObject({ estimated_cost: 35, currency: 'EUR' });
    // 基线字段是独立的顶层字段（ADR-0048 §⑥ 的契约）
    expect(body.expected_updated_at).toBeUndefined();
  });

  it('PATCH 成功返回**更新后的记录**（含新的 record_hash）⇒ 基线靠它刷新（RF-1）', async () => {
    const res = await recordsApi.patch('/cost-est/results', RECORD_ID, {
      expected_hash: CURRENT_HASH,
    });
    expect((res as { record_hash: string }).record_hash).toBe(NEW_HASH);
  });

  it('列表必须带 project_id（类型层必填 + URL 上可见）', async () => {
    await recordsApi.list('/cost-est/results', { project_id: 'p1' });
    expect(lastListUrl).toContain('project_id=p1');
  });

  it('列表返回只约束 {items, total} —— 两种信封的分页字段名差异不消费', async () => {
    const res = await recordsApi.list('/cost-est/results', { project_id: 'p1' });
    expect(Array.isArray(res.items)).toBe(true);
    expect(typeof res.total).toBe('number');
  });

  it('⚠️ 偏移参数名逐模块不同 —— 传错**不会报错**，只会静默停在第一页', async () => {
    // 后端 6 个列表端点两种拼法各 3 个：
    //   `offset` —— cool-tower / flare / psychro
    //   `skip`   —— filtration / open-channel / cost-est
    // ⇒ 调用方一律传 `offset`，由 api 层按模块翻译。
    await recordsApi.list('/filtration/results', { project_id: 'p1', limit: 50, offset: 20 });
    expect(lastListUrl).toContain('skip=20');
    expect(lastListUrl).not.toContain('offset=');

    await recordsApi.list('/cool-tower/results', { project_id: 'p1', limit: 100, offset: 20 });
    expect(lastListUrl).toContain('offset=20');
    expect(lastListUrl).not.toContain('skip=');
  });
});

describe('recordsApi —— 词表与路径的单一来源', () => {
  it('RESULT_BASES 覆盖全部 6 个注册表键（键名与 EDITABLE_RECORD_TYPES 逐字一致）', () => {
    expect(Object.keys(RESULT_BASES).sort()).toEqual([...EDITABLE_RECORD_TYPES].sort());
  });

  it('RESULT_BASES 的值是**列表路径**（不是表名、不是分类词）', () => {
    // ⚠️ 后端按路径找资源 ⇒ 路径写错 ⇒ 404。
    expect(RESULT_BASES.CostEstResult).toBe('/cost-est/results');
    expect(RESULT_BASES.FiltrationResult).toBe('/filtration/results');
    expect(RESULT_BASES.OpenChannelResult).toBe('/open-channel/results');
    expect(RESULT_BASES.cooling_tower_result).toBe('/cool-tower/results');
    expect(RESULT_BASES.flare_system_result).toBe('/flare/results');
    expect(RESULT_BASES.psychro_result).toBe('/psychro/results');
  });
});
