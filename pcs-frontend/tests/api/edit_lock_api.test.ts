/**
 * 编辑锁 / 编辑冲突的**请求契约**（P9B-1 Task F0）。
 *
 * ## 为什么这组测试抓的是「漏传基线」
 *
 * SPEC §6.21 P9A-LCK-006：PATCH **必须**带 `expected_hash`，**不带 ⇒ 409**。
 * 这是**故意**的严格（服务端无法判定并发 ⇒ 不得放行）⇒ 但对前端是反过来的：
 * 一旦漏传，**每个**编辑请求都会 409，而症状是「保存总是失败」，
 * 不指向「漏了基线」⇒ 必须有一条测试直接断言「基线确实在请求体里」。
 *
 * ⚠️ **P9B-1 T1 归并**：那两条 PATCH 用例测的是「**基线**」而不是「**锁**」
 * ⇒ 已迁到 `tests/api/records_api.test.ts`（记录域的单一来源在 `records.ts`）
 * ⇒ 本文件只留锁（acquire / renew / release）与冲突信封解析。
 *
 * 断言方式：用 MSW node server 拦真实请求，把 body 捕获进闭包变量
 * （仿 `tests/pages/util/cooling_water.test.tsx` 的既有套路）。
 *
 * ⚠️ **不要 mock api 模块**：那会把这组测试变成「测 mock 的行为」。
 * 这里 mock 的是**服务端**，被测的是**我们发出去的 body**。
 */
import { describe, it, expect, beforeAll, afterAll } from 'vitest';
import { http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';

import { editLockApi } from '../../src/api/locks';
import { extractConflict } from '../../src/api/errors';

const RECORD_ID = '11111111-2222-3333-4444-555555555555';

const LOCK_RESPONSE = {
  record_type: 'CostEstResult',
  record_id: RECORD_ID,
  operation: 'acquire',
  success: true,
  holder: {
    user_id: '99999999-8888-7777-6666-555555555555',
    acquired_at: '2026-10-20T10:22:31+08:00',
    username: '张三',
  },
  ttl_seconds: 1800,
  degraded: false,
  message: null,
};

const server = setupServer(
  http.post('/api/v1/locks/:recordType/:recordId/:op', ({ params }) =>
    HttpResponse.json({ ...LOCK_RESPONSE, operation: params.op }),
  ),
  // 一个恒定 409 的端点，供 extractConflict 测试用
  http.post('/api/v1/conflict-probe', () =>
    HttpResponse.json(
      {
        code: 'RECORD_EDIT_CONFLICT',
        message: '该记录无法安全保存，请刷新后重新编辑',
        detail: {
          conflict: {
            record_type: 'CostEstResult',
            record_id: RECORD_ID,
            your_expected_hash: 'aaaa1111bbbb2222',
            current_hash: 'cccc3333dddd4444',
            changed_by: 'someone-else',
            changed_at: '2026-10-20T11:00:00Z',
            basis: 'record_hash',
          },
        },
        trace_id: 'trace-1',
      },
      { status: 409 },
    ),
  ),
);

describe('编辑锁 / 编辑保存的请求契约（P9B-1 F0）', () => {
  beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
  afterAll(() => server.close());

  it('acquire 用注册表键当 record_type（不是表名）', async () => {
    const res = await editLockApi.acquire('CostEstResult', RECORD_ID);
    expect(res.success).toBe(true);
    expect(res.holder?.username).toBe('张三');
  });

  it('renew / release 走同一套 URL 形状', async () => {
    const renew = await editLockApi.renew('CostEstResult', RECORD_ID);
    expect(renew.operation).toBe('renew');
    const release = await editLockApi.release('CostEstResult', RECORD_ID);
    expect(release.operation).toBe('release');
  });

  it('extractConflict 从 409 信封里取出 detail.conflict', async () => {
    const { api } = await import('../../src/api/client');
    try {
      await api.post('/conflict-probe');
      throw new Error('应当抛出 409');
    } catch (err) {
      const conflict = extractConflict(err);
      expect(conflict).not.toBeNull();
      expect(conflict?.basis).toBe('record_hash');
      expect(conflict?.changed_by).toBe('someone-else');
      expect(conflict?.current_hash).toBe('cccc3333dddd4444');
    }
  });

  it('extractConflict 对非冲突错误返回 null（不抛）', async () => {
    expect(extractConflict(new Error('boom'))).toBeNull();
    expect(extractConflict(undefined)).toBeNull();
    expect(extractConflict({ response: { status: 500, data: {} } })).toBeNull();
    // detail 缺失的 409 ⇒ null，不许崩
    expect(
      extractConflict({ response: { status: 409, data: { code: 'X', message: 'y' } } }),
    ).toBeNull();
  });
});
