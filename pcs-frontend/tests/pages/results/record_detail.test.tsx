/**
 * 记录详情抽屉（P9B-2 · T5 · SPEC §7.19.1）。
 *
 * ⚠️ 守的是 P9B-1 的 bug-2043 同形复发（RF-13）：**换记录**（同一抽屉，
 * `recordId` 变）⇒ 内容必须**整体重建**，不得残留上一条。
 * ⇒ 宿主页给抽屉的 `key` 必须带 `recordType + recordId`。
 */
import { describe, it, expect, beforeAll, afterAll, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';

import { RecordDetailDrawer } from '../../../src/pages/results/RecordDetailDrawer';
import { useAuth } from '../../../src/store/auth';

const MODULE = 'cooling_tower_result';
const ID_A = '11111111-2222-3333-4444-555555555555';
const ID_B = '99999999-8888-7777-6666-555555555555';

let commentBodyById: Record<string, string> = {};

const server = setupServer(
  http.get('/api/v1/meta/state-machine', () =>
    HttpResponse.json({ transitions: [], allowed: {} }),
  ),
  http.get('/api/v1/projects/:projectId/signature-matrices', () => HttpResponse.json([])),
  http.get('/api/v1/records/:module/:recordId/comments', ({ params }) =>
    HttpResponse.json({
      items: [
        {
          comment_id: `c-${params['recordId']}`,
          record_type: MODULE,
          record_id: String(params['recordId']),
          body: commentBodyById[String(params['recordId'])] ?? '',
          author_id: 'u-1',
          created_at: '2026-10-20T10:00:00Z',
        },
      ],
      total: 1,
    }),
  ),
  http.get('/api/v1/records/:module/:recordId/edits', ({ params }) =>
    HttpResponse.json({
      record_type: MODULE,
      record_id: String(params['recordId']),
      items: [
        {
          audit_id: `a-${params['recordId']}`,
          changed_fields: [`field-${params['recordId']}`],
          user_id: 'u-1',
          occurred_at: '2026-10-20T10:00:00Z',
        },
      ],
      total: 1,
    }),
  ),
);

const RECORD_A = {
  project_id: 'project-1',
  record_hash: 'a3f9c21d8b7e6f50',
  sign_status: 'DRAFT',
};

describe('RecordDetailDrawer —— 换记录必须整体重建（RF-13）', () => {
  beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
  afterAll(() => server.close());
  beforeEach(() => {
    commentBodyById = { [ID_A]: 'A 记录的批注', [ID_B]: 'B 记录的批注' };
    useAuth.setState({ role: 'DESIGNER', accessToken: 'test-token' });
  });

  it('抽屉渲染状态 + 哈希 + 批注 + 时间线', async () => {
    render(
      <RecordDetailDrawer
        key={`${MODULE}:${ID_A}`}
        module={MODULE}
        recordId={ID_A}
        record={RECORD_A}
      />,
    );

    await waitFor(() => expect(screen.getByTestId('record-detail-drawer')).toBeTruthy());
    expect(screen.getByTestId('record-detail-drawer').getAttribute('data-record-id')).toBe(ID_A);
    await waitFor(() => expect(screen.getByTestId('comment-item-c-' + ID_A)).toBeTruthy());
  });

  it('⚠️ 换记录（key 变）⇒ 抽屉**整体重建**，不残留上一条的内容', async () => {
    const { rerender } = render(
      <RecordDetailDrawer
        key={`${MODULE}:${ID_A}`}
        module={MODULE}
        recordId={ID_A}
        record={RECORD_A}
      />,
    );
    await waitFor(() => expect(screen.getByTestId('comment-item-c-' + ID_A)).toBeTruthy());
    expect(screen.getByTestId('comment-item-c-' + ID_A).textContent).toContain('A 记录的批注');

    rerender(
      <RecordDetailDrawer
        key={`${MODULE}:${ID_B}`}
        module={MODULE}
        recordId={ID_B}
        record={RECORD_A}
      />,
    );

    await waitFor(() =>
      expect(screen.getByTestId('record-detail-drawer').getAttribute('data-record-id')).toBe(ID_B),
    );
    // ⚠️ 旧记录的行**必须消失**（重建 ⇒ 不残留）
    await waitFor(() => expect(screen.queryByTestId('comment-item-c-' + ID_A)).toBeNull());
    await waitFor(() => expect(screen.getByTestId('comment-item-c-' + ID_B)).toBeTruthy());
    expect(screen.getByTestId('comment-item-c-' + ID_B).textContent).toContain('B 记录的批注');
    // ⚠️ 时间线同样重建
    await waitFor(() => expect(screen.getByTestId('record-timeline-item-a-' + ID_B)).toBeTruthy());
    expect(screen.queryByTestId('record-timeline-item-a-' + ID_A)).toBeNull();
  });
});
