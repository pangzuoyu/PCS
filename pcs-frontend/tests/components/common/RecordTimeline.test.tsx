/**
 * 记录状态时间线（P9B-2 · T5 · SPEC §7.19.1）。
 *
 * 守三件事（RF-5 / R-10）：
 * 1. 数据源是**编辑审计**（`/records/{m}/{id}/edits`），**不是** workflow_progress
 *    —— 混用会把「查过一眼」也算成活动；
 * 2. `changed_fields` 为空 ⇒ 显示「（未记录字段）」而不是空白；
 * 3. 空态文案是「尚无编辑记录」⇒ **不得**写成「尚无动作记录」（那是交付物
 *    动作时间线的文案，两个数据源必须可分辨）。
 */
import { describe, it, expect, beforeAll, afterAll, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';

import { RecordTimeline } from '../../../src/components/common/RecordTimeline';

const MODULE = 'cooling_tower_result';
const RECORD_ID = '11111111-2222-3333-4444-555555555555';

let items: { audit_id: string; changed_fields: string[]; user_id?: string | null; occurred_at: string }[] = [];

const server = setupServer(
  http.get('/api/v1/records/:module/:recordId/edits', () =>
    HttpResponse.json({
      record_type: MODULE,
      record_id: RECORD_ID,
      items,
      total: items.length,
    }),
  ),
  // ⚠️ 观测层端点 —— **不得**被时间线当数据源（RF-5）
  http.get('/api/v1/workflow-progress/:type/:id', () =>
    HttpResponse.json({ items: [], total: 0 }),
  ),
);

describe('RecordTimeline —— 编辑历史', () => {
  beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
  afterAll(() => server.close());
  beforeEach(() => {
    items = [];
  });

  it('渲染编辑审计的 changed_fields（字段名列表）', async () => {
    items = [
      {
        audit_id: 'a-1',
        changed_fields: ['duty_kw', 'tower_type'],
        user_id: 'u-1',
        occurred_at: '2026-10-20T10:00:00Z',
      },
    ];
    render(<RecordTimeline module={MODULE} recordId={RECORD_ID} />);

    await waitFor(() => expect(screen.getByTestId('record-timeline-item-a-1')).toBeTruthy());
    expect(screen.getByTestId('record-timeline-item-a-1').textContent).toContain('duty_kw');
    expect(screen.getByTestId('record-timeline-item-a-1').textContent).toContain('tower_type');
  });

  it('⚠️ changed_fields 为空 ⇒ 显示「（未记录字段）」而不是空白', async () => {
    items = [
      {
        audit_id: 'a-2',
        changed_fields: [],
        user_id: 'u-1',
        occurred_at: '2026-10-20T10:00:00Z',
      },
    ];
    render(<RecordTimeline module={MODULE} recordId={RECORD_ID} />);

    await waitFor(() => expect(screen.getByTestId('record-timeline-item-a-2')).toBeTruthy());
    expect(screen.getByTestId('record-timeline-item-a-2').textContent).toContain('（未记录字段）');
  });

  it('⚠️ 空态文案是「尚无编辑记录」—— **不得**是「尚无动作记录」（R-10）', async () => {
    render(<RecordTimeline module={MODULE} recordId={RECORD_ID} />);

    await waitFor(() => expect(screen.getByTestId('record-timeline-empty')).toBeTruthy());
    const text = screen.getByTestId('record-timeline-empty').textContent ?? '';
    expect(text).toContain('编辑记录');
    expect(text).not.toContain('动作记录');
  });
});
