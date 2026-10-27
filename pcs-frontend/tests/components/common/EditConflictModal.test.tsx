/**
 * 409 冲突弹窗的守卫（P9B-1 Task T2 · SPEC §6.21 P9A-LCK-005）。
 *
 * ## 为什么必须按 `basis` 分流
 *
 * 三个 basis 的**原因不同** ⇒ **文案不同、动作也不同**：
 *
 * | basis | 原因 | 出口 |
 * |---|---|---|
 * | `record_hash` | 别人改过这条记录 | [查看差异] / [放弃我的修改并刷新] |
 * | `updated_at` | 别人改过这条记录（只知道行被改过） | [查看差异] / [放弃我的修改并刷新] |
 * | `no_baseline` | **这条记录压根没法校验并发** | [刷新后重试] / [联系管理员] |
 *
 * ⚠️ **`no_baseline` 绝不能显示成「已被他人修改」** —— 那是**两回事**：
 * 一个是「有人改过」，一个是「没法知道有没有人改过」。
 *
 * ⚠️ **不得自动重试**（ADR-0048 §⑦）：重试仍是 409，且会把「冲突」掩盖成「抖动」。
 *
 * ## P9B-2 · R-14：「查看差异」换了数据源
 *
 * 原先打 `/audit-logs`（**限 SYSTEM_ADMIN**）⇒ 普通 DESIGNER 拿到 409 弹窗
 * 却**点不开差异** ⇒ 现在打**按项目守卫**的
 * `GET /records/{module}/{record_id}/edits`（TODO-066）⇒ **普通用户点得开**。
 * ⇒ `changed_fields` 也在**顶层**（不是 `detail_json` 里）。
 */
import { describe, it, expect, vi, beforeAll, afterAll, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';

import { EditConflictModal } from '../../../src/components/common/EditConflictModal';
import type { ConflictDetail } from '../../../src/api/errors';

let editCalls = 0;
let editStatus = 200;
let auditLogCalls = 0;

const server = setupServer(
  // ⚠️ 新端点（按项目守卫）—— 普通 DESIGNER **点得开**
  http.get('/api/v1/records/:module/:recordId/edits', () => {
    editCalls += 1;
    if (editStatus === 403) {
      return HttpResponse.json(
        { code: 'HTTP_404', message: 'Project not found' },
        { status: 403 },
      );
    }
    return HttpResponse.json({
      record_type: 'CostEstResult',
      record_id: '11111111-2222-3333-4444-555555555555',
      items: [
        {
          audit_id: 'a-1',
          // ⚠️ `changed_fields` 在**顶层**（新端点已把 `detail_json` 摊平）
          changed_fields: ['duty_kw', 'tower_type'],
          overwrote_stale_baseline: false,
          user_id: 'u-1',
          occurred_at: '2026-10-20T11:00:00Z',
        },
      ],
      total: 1,
    });
  }),
  // ⚠️ 旧端点（SYSTEM_ADMIN-only）—— **不得**再被「查看差异」打到
  http.get('/api/v1/audit-logs', () => {
    auditLogCalls += 1;
    return HttpResponse.json({ items: [], total: 0, limit: 50, offset: 0 });
  }),
);

const CONFLICT: ConflictDetail = {
  record_type: 'CostEstResult',
  record_id: '11111111-2222-3333-4444-555555555555',
  your_expected_hash: 'aaaa1111bbbb2222',
  current_hash: 'cccc3333dddd4444',
  changed_by: '李四',
  changed_at: '2026-10-20T11:00:00Z',
  basis: 'record_hash',
};

describe('EditConflictModal —— 按 basis 分流', () => {
  beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
  afterAll(() => server.close());
  beforeEach(() => {
    editCalls = 0;
    auditLogCalls = 0;
    editStatus = 200;
  });

  it('basis=record_hash ⇒ 「谁于何时改了这条记录」+ [查看差异] / [放弃我的修改并刷新]', () => {
    const onRefresh = vi.fn();
    render(
      <EditConflictModal open conflict={CONFLICT} onRefresh={onRefresh} />,
    );

    const body = screen.getByTestId('edit-conflict-modal');
    expect(body.textContent).toContain('李四');
    expect(body.textContent).toContain('修改了这条记录');
    expect(screen.getByTestId('conflict-view-diff')).toBeTruthy();
    expect(screen.getByTestId('conflict-refresh')).toBeTruthy();
  });

  it('⚠️ changed_by / changed_at 为 null ⇒ 显示「未知」，**不得**拿别的字段顶替（RF-5）', () => {
    render(
      <EditConflictModal
        open
        conflict={{ ...CONFLICT, changed_by: null, changed_at: null }}
        onRefresh={vi.fn()}
      />,
    );
    const body = screen.getByTestId('edit-conflict-modal');
    expect(body.textContent).toContain('未知');
    expect(body.textContent).not.toContain('2026-10-20T11:00:00Z');
  });

  it('⚠️ basis=no_baseline ⇒ 文案**不得**说「已被他人修改」+ [刷新后重试] / [联系管理员]', () => {
    render(
      <EditConflictModal
        open
        conflict={{ ...CONFLICT, basis: 'no_baseline' }}
        onRefresh={vi.fn()}
        onContactAdmin={vi.fn()}
      />,
    );
    const body = screen.getByTestId('edit-conflict-modal');
    expect(body.textContent).toContain('基线');
    expect(body.textContent).not.toContain('修改了这条记录');
    expect(screen.getByTestId('conflict-refresh')).toBeTruthy();
    expect(screen.getByTestId('conflict-contact-admin')).toBeTruthy();
    // ⚠️ no_baseline **没有**「查看差异」（没有冲突就没有差异可看）
    expect(screen.queryByTestId('conflict-view-diff')).toBeNull();
  });

  it('⚠️ TODO-067 #1：宿主没给 `onContactAdmin` ⇒ **不渲染死按钮**，改给真实出路', () => {
    render(
      <EditConflictModal
        open
        conflict={{ ...CONFLICT, basis: 'no_baseline' }}
        onRefresh={vi.fn()}
      />,
    );
    // ⚠️ 死按钮 = `onContactAdmin?.()` 在宿主没传时**点了什么都不会发生**
    expect(screen.queryByTestId('conflict-contact-admin')).toBeNull();
    expect(screen.getByTestId('conflict-contact-admin-hint').textContent).toContain(
      '管理员',
    );
  });

  it('basis 未知 ⇒ 「说不清是否冲突」+ [刷新后重试]（**不误报成「无冲突」**）', () => {
    render(
      <EditConflictModal
        open
        conflict={{ ...CONFLICT, basis: 'future_basis' as never }}
        onRefresh={vi.fn()}
      />,
    );
    const body = screen.getByTestId('edit-conflict-modal');
    expect(body.textContent).toContain('说不清');
    expect(screen.getByTestId('conflict-refresh')).toBeTruthy();
  });

  it('[查看差异] ⇒ 拉**按项目守卫**的编辑审计并展示 changed_fields（字段名列表）', async () => {
    render(
      <EditConflictModal open conflict={CONFLICT} onRefresh={vi.fn()} />,
    );
    fireEvent.click(screen.getByTestId('conflict-view-diff'));

    await waitFor(() => expect(screen.getByTestId('conflict-diff').textContent).toContain('duty_kw'));
    expect(screen.getByTestId('conflict-diff').textContent).toContain('tower_type');
  });

  it('⚠️ R-14：**不得**再打 SYSTEM_ADMIN-only 的 `/audit-logs`（普通用户点得开）', async () => {
    render(
      <EditConflictModal open conflict={CONFLICT} onRefresh={vi.fn()} />,
    );
    fireEvent.click(screen.getByTestId('conflict-view-diff'));

    await waitFor(() => expect(editCalls).toBe(1));
    expect(auditLogCalls).toBe(0);
  });

  it('⚠️ **不得自动重试** —— 点一次只请求一次', async () => {
    render(
      <EditConflictModal open conflict={CONFLICT} onRefresh={vi.fn()} />,
    );
    fireEvent.click(screen.getByTestId('conflict-view-diff'));
    await waitFor(() => expect(editCalls).toBe(1));

    await new Promise((r) => setTimeout(r, 50));
    expect(editCalls).toBe(1);
  });

  it('[刷新后重试] ⇒ 调 onRefresh 一次', () => {
    const onRefresh = vi.fn();
    render(
      <EditConflictModal open conflict={CONFLICT} onRefresh={onRefresh} />,
    );
    fireEvent.click(screen.getByTestId('conflict-refresh'));
    expect(onRefresh).toHaveBeenCalledTimes(1);
  });

  it('⚠️ [查看差异] 403 ⇒ 「无权查看差异」且**保留**刷新出口', async () => {
    editStatus = 403;
    render(
      <EditConflictModal open conflict={CONFLICT} onRefresh={vi.fn()} />,
    );
    fireEvent.click(screen.getByTestId('conflict-view-diff'));

    await waitFor(() =>
      expect(screen.getByTestId('conflict-diff-error').textContent).toContain(
        '无权查看差异',
      ),
    );
    // ⚠️ 不能把人堵死 ⇒ 刷新出口必须还在
    expect(screen.getByTestId('conflict-refresh')).toBeTruthy();
  });
});
