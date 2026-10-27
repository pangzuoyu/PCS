/**
 * 批注面板（P9B-2 · T5 · SPEC §7.19.1）。
 *
 * 守三件事：
 * 1. **纯空白不是内容**（RF-7）—— 后端也拒，但前端先拦 ⇒ 发送按钮禁用；
 * 2. **分页按 `total`**（RF-8）—— 「加载更多直到空」会漏条/重复；
 * 3. **403 不得渲染成空列表**（RF-12）—— 空列表会被读成「还没有人留言」。
 */
import { describe, it, expect, beforeAll, afterAll, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';

import { CommentPanel } from '../../../src/components/common/CommentPanel';

const MODULE = 'cooling_tower_result';
const RECORD_ID = '11111111-2222-3333-4444-555555555555';

let listStatus = 200;
let created: { comment_id: string; body: string; author_id: string; created_at: string }[] = [];
let listTotal = 0;
/** ⚠️ 服务端返回的**升序**列表（后端 `ORDER BY created_at, comment_id`）。 */
let listItems: { comment_id: string; body: string; author_id: string; created_at: string }[] = [];

const server = setupServer(
  http.get('/api/v1/records/:module/:recordId/comments', () => {
    if (listStatus === 403) {
      return HttpResponse.json({ code: 'HTTP_403', message: '无权' }, { status: 403 });
    }
    return HttpResponse.json({ items: listItems, total: listTotal });
  }),
  http.post('/api/v1/records/:module/:recordId/comments', async ({ request }) => {
    const body = (await request.json()) as { body: string };
    const item = {
      // ⚠️ id 接在**服务端列表**之后（升序 ⇒ 新批注在末尾）
      comment_id: `c-${listItems.length + created.length + 1}`,
      body: body.body,
      author_id: 'u-1',
      created_at: '2026-10-20T10:00:00Z',
    };
    created = [item, ...created];
    listTotal += 1;
    return HttpResponse.json(item);
  }),
);

describe('CommentPanel —— 批注', () => {
  beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
  afterAll(() => server.close());
  beforeEach(() => {
    listStatus = 200;
    created = [];
    listTotal = 0;
    listItems = [];
  });

  it('⚠️ 纯空白 ⇒ 发送按钮**禁用**（RF-7）', async () => {
    render(<CommentPanel module={MODULE} recordId={RECORD_ID} />);
    await waitFor(() => expect(screen.getByTestId('comment-send')).toBeTruthy());

    expect((screen.getByTestId('comment-send') as HTMLButtonElement).disabled).toBe(true);

    fireEvent.change(screen.getByTestId('comment-input'), { target: { value: '   ' } });
    await waitFor(() =>
      expect((screen.getByTestId('comment-send') as HTMLButtonElement).disabled).toBe(true),
    );

    fireEvent.change(screen.getByTestId('comment-input'), { target: { value: ' 看着不对 ' } });
    await waitFor(() =>
      expect((screen.getByTestId('comment-send') as HTMLButtonElement).disabled).toBe(false),
    );
  });

  it('发送成功 ⇒ 列表**追加**新批注且输入框清空', async () => {
    render(<CommentPanel module={MODULE} recordId={RECORD_ID} />);
    await waitFor(() => expect(screen.getByTestId('comment-send')).toBeTruthy());

    fireEvent.change(screen.getByTestId('comment-input'), {
      target: { value: '这里的数据要再核对一遍' },
    });
    fireEvent.click(screen.getByTestId('comment-send'));

    await waitFor(() => expect(screen.getByTestId('comment-item-c-1')).toBeTruthy());
    expect(screen.getByTestId('comment-item-c-1').textContent).toContain('这里的数据要再核对一遍');
    expect((screen.getByTestId('comment-input') as HTMLTextAreaElement).value).toBe('');
  });

  it('⚠️ 新批注**追加到末尾**（与后端升序一致）⇒ 刷新后位置不变', async () => {
    // ⚠️ 后端按 `created_at ASC` 返回 ⇒ 前端若 prepend ⇒ 发送后新批注跳到
    //    **顶部**，一刷新又回到**末尾** ⇒ 用户以为「批注丢了」。
    listItems = [
      { comment_id: 'c-1', body: '最早的一条', author_id: 'u-1', created_at: '2026-10-20T10:00:00Z' },
      { comment_id: 'c-2', body: '第二条', author_id: 'u-1', created_at: '2026-10-20T11:00:00Z' },
    ];
    listTotal = listItems.length;
    render(<CommentPanel module={MODULE} recordId={RECORD_ID} />);
    await waitFor(() => expect(screen.getByTestId('comment-item-c-1')).toBeTruthy());

    fireEvent.change(screen.getByTestId('comment-input'), {
      target: { value: '新批注' },
    });
    fireEvent.click(screen.getByTestId('comment-send'));

    await waitFor(() => expect(screen.getByTestId('comment-item-c-3')).toBeTruthy());
    const order = screen
      .getAllByTestId(/^comment-item-/)
      .map((el) => el.getAttribute('data-testid'));
    expect(order).toEqual(['comment-item-c-1', 'comment-item-c-2', 'comment-item-c-3']);
  });

  it('⚠️ total=2、limit=1 ⇒ 渲染**分页**（不是「加载更多」）（RF-8）', async () => {
    // ⚠️ 页数 = ceil(total / limit) ⇒ total > 一页容量才出分页控件
    listTotal = 21;
    render(<CommentPanel module={MODULE} recordId={RECORD_ID} />);
    await waitFor(() => expect(screen.getByTestId('comment-pagination')).toBeTruthy());
  });

  it('⚠️ 403 ⇒ 显示「无权查看」**而不是**空列表（RF-12）', async () => {
    listStatus = 403;
    render(<CommentPanel module={MODULE} recordId={RECORD_ID} />);
    await waitFor(() => expect(screen.getByTestId('comment-error')).toBeTruthy());
    expect(screen.getByTestId('comment-error').textContent).toContain('无权查看');
    // ⚠️ **不得**同时渲染空态（空列表会被读成「还没有人留言」）
    expect(screen.queryByTestId('comment-empty')).toBeNull();
  });
});
