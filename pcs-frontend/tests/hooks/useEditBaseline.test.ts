/**
 * 三档基线判定的守卫（P9B-1 Task T2）。
 *
 * ## 为什么是「三档」而不是「一档」
 *
 * 后端 `check_conflict` 的实际语义（ADR-0048 §⑥）：
 *
 * ```
 * 当前 record_hash 非空   ⇒ 比 hash：不等 ⇒ 409 (basis=record_hash)
 * 当前 record_hash 为空   ⇒ 比 updated_at：不等 ⇒ 409 (basis=updated_at)
 *                         → 无 updated_at / 客户端没给基线 ⇒ 409 (basis=no_baseline)
 * ```
 *
 * ⇒ 前端必须**自己**按同一阶梯判定（客户端拿得到的是「我看到的 hash」，
 * 后端拿得到的是「DB 里的 hash」——两端只有都判出同一档才对得上）。
 *
 * ⚠️ **第三档是防御性代码**：6 张可编辑结果表里 **5 张**有 `updated_at`，
 * 只有 `cost_est_results` 没有 ⇒ 它的行若 hash 为空 ⇒ **两档皆无**
 * ⇒ 永远 409 ⇒ 前端必须**提前**禁用编辑并说「联系管理员」。
 *
 * ## RF-13 —— 这组测试存在的第二个理由
 *
 * `{...changed, ...baseline}` 里的字段名若漂成 `expectedHash`，
 * **TypeScript 编译通过**（实测 2026-10-21）⇒ 请求体缺 `expected_hash`
 * ⇒ 后端 `expected_hash is None` ⇒ **每次保存 409 `no_baseline`**。
 * ⇒ 类型系统不拦 ⇒ 只能靠**断言请求体**的测试兜底。
 */
import { describe, it, expect } from 'vitest';
import { http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';

import {
  useEditBaseline,
  isEditableSignStatus,
  isRowEditable,
} from '../../src/hooks/useEditBaseline';
import { recordsApi } from '../../src/api/records';

const CURRENT_HASH = 'a3f9c21d8b7e6f50';

let lastBody: unknown = null;
const server = setupServer(
  http.patch('/api/v1/cost-est/results/:id', async ({ request }) => {
    lastBody = await request.json();
    return HttpResponse.json({ record_hash: 'ffffffffffffffff' });
  }),
);

describe('useEditBaseline —— 三档基线判定', () => {
  it('hash 非空 ⇒ expected_hash', () => {
    const b = useEditBaseline({ record_hash: CURRENT_HASH, canEdit: true });
    expect(b.expected_hash).toBe(CURRENT_HASH);
    expect(b.disabled).toBe(false);
    expect(b.reason).toBe('ok');
  });

  it('hash 空 + 有 updated_at ⇒ 退到第二档（expected_updated_at）', () => {
    const raw = '2026-10-20T10:22:31.123456+08:00';
    const b = useEditBaseline({ record_hash: '', updated_at: raw, canEdit: true });
    expect(b.expected_updated_at).toBe(raw); // ⚠️ 逐字（RF-9）
    expect(b.expected_hash).toBeUndefined();
    expect(b.disabled).toBe(false);
  });

  it('两档皆无 ⇒ disabled + reason=no-baseline（**不是** no-permission）', () => {
    const b = useEditBaseline({ record_hash: '', updated_at: null, canEdit: true });
    expect(b.disabled).toBe(true);
    expect(b.reason).toBe('no-baseline');
  });

  it('canEdit=false ⇒ disabled + reason=no-permission（与 no-baseline **可区分**）', () => {
    const b = useEditBaseline({ record_hash: CURRENT_HASH, canEdit: false });
    expect(b.reason).toBe('no-permission');
    expect(b.disabled).toBe(true);
  });

  it('**disabled=false ⇒ 至少一档基线存在**（运行时保证，类型层表达不了）', () => {
    const b = useEditBaseline({ record_hash: CURRENT_HASH, canEdit: true });
    expect(b.disabled).toBe(false);
    expect(b.expected_hash || b.expected_updated_at).toBeTruthy();
  });

  it('hash 只有空白 ⇒ 当作「无 hash」（退到第二档）', () => {
    const b = useEditBaseline({
      record_hash: '   ',
      updated_at: '2026-10-20T10:22:31+08:00',
      canEdit: true,
    });
    expect(b.expected_hash).toBeUndefined();
    expect(b.expected_updated_at).toBe('2026-10-20T10:22:31+08:00');
  });
});

describe('useEditBaseline —— RF-13：基线字段名穿过展开后仍是 expected_hash', () => {
  it('断言**请求体**（不是 hook 的返回值）', async () => {
    server.listen({ onUnhandledRequest: 'error' });
    try {
      const b = useEditBaseline({ record_hash: CURRENT_HASH, canEdit: true });
      await recordsApi.patch('/cost-est/results', 'r1', {
        ...{ estimated_cost: 35 },
        ...b,
      });
      const body = lastBody as Record<string, unknown>;
      expect(body.expected_hash).toBe(CURRENT_HASH);
      expect(body.expectedHash).toBeUndefined();
    } finally {
      server.close();
    }
  });
});

describe('可编辑判据 —— sign_status', () => {
  it('只有 DRAFT / CHANGE_PENDING 可编辑（后端 *_PERSIST_SIGN_STATUS_LOCKED 的口径）', () => {
    expect(isEditableSignStatus('DRAFT')).toBe(true);
    expect(isEditableSignStatus('CHANGE_PENDING')).toBe(true);
    for (const s of [
      'IN_APPROVAL',
      'CHECKED',
      'CHECK_REJECTED',
      'STALE',
      'CHANGED',
      'REVERSAL_PENDING',
      'OBSOLETE',
    ]) {
      expect(isEditableSignStatus(s), `${s} 不该可编辑`).toBe(false);
    }
  });

  it('⚠️ 无 sign_status 列的模块（cost_est）⇒ **可编辑**（后端也没有状态门禁）', () => {
    // cost_est_results 没有 sign_status 列（后端「1:1 跟随设备、状态跟设备」）
    // ⇒ 没有状态可判 ⇒ 不能因为「判不出」就禁编辑（那会把可编辑的行全锁死）。
    expect(isRowEditable(null)).toBe(true);
    expect(isRowEditable(undefined)).toBe(true);
    expect(isRowEditable('DRAFT')).toBe(true);
    expect(isRowEditable('CHECKED')).toBe(false);
  });
});
