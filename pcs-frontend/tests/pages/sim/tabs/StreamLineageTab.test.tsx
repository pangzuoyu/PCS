/**
 * 「血缘」Tab 测试（P9B-4 T0-D · TODO-136）。
 *
 * 守两件事：
 * 1. **两套词表要区分** —— 根行（合成节点）的 `source` 是**物流来源**
 *    （`MANUAL`）⇒ 必须带 tooltip 说清「这是物流来源（录入通道）」；
 * 2. 下游行（真实血缘行）的 `source` 是**计算来源**（`CALC`）⇒ 不带那个
 *    tooltip（否则 tooltip 就在撒谎）。
 */
import { describe, it, expect, beforeAll, afterAll } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';

import { StreamLineageTab } from '../../../../src/pages/sim/tabs/StreamLineageTab';

const server = setupServer(
  http.get('/api/v1/lineage/:record_type/:record_id/graph', () =>
    HttpResponse.json({
      root: {
        lineage_id: '00000000-0000-4000-8000-000000000001',
        record_type: 'streams',
        record_id: 's-1',
        parent_lineage_id: null,
        source: 'MANUAL',
        source_ref_type: null,
        source_ref_id: null,
        actor_user_id: null,
        change_summary: '物流本身（合成根节点）',
        occurred_at: '2026-09-15T14:00:00+00:00',
      },
      upstream: [],
      downstream: [
        {
          lineage_id: '00000000-0000-4000-8000-000000000002',
          record_type: 'PipingResult',
          record_id: 'pipe-1',
          parent_lineage_id: null,
          source: 'CALC',
          source_ref_type: 'Stream',
          source_ref_id: 's-1',
          actor_user_id: null,
          change_summary: 'calc finalize',
          occurred_at: '2026-09-16T10:00:00+00:00',
        },
      ],
    }),
  ),
);

describe('StreamLineageTab（P9B-4 T0-D）', () => {
  beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
  afterAll(() => server.close());

  it('根行显示物流来源 + tooltip 标明「录入通道」', async () => {
    render(<StreamLineageTab streamId="s-1" />);

    await waitFor(() => expect(screen.getByTestId('stream-tab-lineage')).toBeTruthy());
    // ⚠️ 根行的来源值 = **物流来源**（4 值词表）
    expect(screen.getByText('MANUAL')).toBeTruthy();
    // ⚠️ 下游行显示**计算来源**
    expect(screen.getByText('CALC')).toBeTruthy();

    // ⚠️ 悬停根行 ⇒ tooltip 出现（两套词表的区分）
    fireEvent.mouseEnter(screen.getByText('MANUAL'));
    await waitFor(() => expect(document.body.textContent).toContain('物流来源'));
    expect(document.body.textContent).toContain('手动创建');
  });

  it('下游行不带「物流来源」tooltip（它显示的是计算来源）', async () => {
    render(<StreamLineageTab streamId="s-1" />);
    await waitFor(() => expect(screen.getByTestId('stream-tab-lineage')).toBeTruthy());

    fireEvent.mouseEnter(screen.getByText('CALC'));
    // ⚠️ 等一会儿，tooltip 不该出现（tooltip 有延迟 ⇒ 必须等）
    await new Promise((resolve) => setTimeout(resolve, 300));
    expect(document.body.textContent).not.toContain('物流来源（录入通道）');
  });
});
