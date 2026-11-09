/**
 * 「校核记录」Tab 测试（TODO-112 · P9B-4 紧急批次 T6）。
 *
 * 守三件事：
 * 1. mock 端点返回三条 ⇒ 表格出现 **3 行**；
 * 2. mock 返回空数组 ⇒ 显示「（无校核记录）」；
 * 3. mock 返回 404 ⇒ 显示**错误条**（跨项目 ⇒ 与「不存在」同形 ⇒ 404）。
 *
 * ⚠️ **过滤在后端**：端点只返回 SUBMIT_FOR_CHECK / PASS_CHECK / REJECT_CHECK
 * 三条 ⇒ 前端**不得**再过滤一遍（两处过滤 = 两个口径 = 迟早漂移）。
 */
import { describe, it, expect, beforeAll, afterAll } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';

import { StreamReviewLogTab } from '../../../../src/pages/sim/tabs/StreamReviewLogTab';

const server = setupServer(
  http.get('/api/v1/streams/:stream_id/review-log', () =>
    HttpResponse.json([
      {
        transition: 'SUBMIT_FOR_CHECK',
        operator: 'u-1',
        occurred_at: '2026-09-15T14:00:00+08:00',
        detail: null,
      },
      {
        transition: 'PASS_CHECK',
        operator: 'u-2',
        occurred_at: '2026-09-15T15:00:00+08:00',
        detail: null,
      },
      {
        transition: 'REJECT_CHECK',
        operator: 'u-3',
        occurred_at: '2026-09-15T16:00:00+08:00',
        detail: '组成超差',
      },
    ]),
  ),
);

describe('StreamReviewLogTab（TODO-112）', () => {
  beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
  afterAll(() => server.close());

  it('mock 返回三条 ⇒ 表格出现 3 行', async () => {
    render(<StreamReviewLogTab streamId="s-1" />);

    await waitFor(() => expect(screen.getByTestId('stream-tab-review-log')).toBeTruthy());
    // ⚠️ 三条都在（中文标签）
    expect(document.body.textContent).toContain('提交校对');
    expect(document.body.textContent).toContain('校对通过');
    expect(document.body.textContent).toContain('校对驳回');
    // ⚠️ 说明列（驳回理由）也在
    expect(document.body.textContent).toContain('组成超差');
    // ⚠️ 表格正文 3 行
    expect(document.querySelectorAll('.ant-table-tbody tr.ant-table-row')).toHaveLength(3);
  });

  it('mock 返回空数组 ⇒ 显示「（无校核记录）」', async () => {
    server.resetHandlers();
    server.use(
      http.get('/api/v1/streams/:stream_id/review-log', () => HttpResponse.json([])),
    );

    render(<StreamReviewLogTab streamId="s-1" />);

    await waitFor(() =>
      expect(document.body.textContent).toContain('（无校核记录）'),
    );
    expect(screen.queryByTestId('stream-review-log-error')).toBeNull();
  });

  it('mock 返回 404 ⇒ 显示错误条', async () => {
    server.resetHandlers();
    server.use(
      http.get('/api/v1/streams/:stream_id/review-log', () =>
        HttpResponse.json(
          { code: 'SIM_STREAM_NOT_FOUND', message: 'Stream s-1 不存在' },
          { status: 404 },
        ),
      ),
    );

    render(<StreamReviewLogTab streamId="s-1" />);

    await waitFor(() => expect(screen.getByTestId('stream-review-log-error')).toBeTruthy());
  });
});
