/**
 * 变更单的「**作废**」入口（TODO-085 之后的前端接线项）。
 *
 * ## 为什么需要它
 *
 * 变更单的**取消路径**（后端 `POST .../change-notice/cancel`，TODO-080 落地）
 * **前端没有入口** ⇒ 用户只能拿 curl 作废自己建错的单。
 *
 * ## 这组测试钉住的失败模式
 *
 * | # | 失败模式 | 期望 |
 * |---|---|---|
 * | RF-1 | 前端**看不出来**记录有没有开着的变更单（两种情况记录都是 CHANGED）⇒ 建单按钮永远在 | 打开弹窗时先查 `GET .../change-notice` |
 * | RF-2 | 已经有开着的变更单时还让用户「再建一张」⇒ 后端 409 | 弹窗改成「作废这张变更单」 |
 * | RF-3 | 作废**不动记录**（作废的是单据）⇒ 前端却把记录状态改了 | 记录状态**不变**（仍 CHANGED） |
 * | RF-4 | 作废**没填理由**就发出去 ⇒ 后端 422 | 理由必填 |
 */
import { describe, it, expect, beforeAll, afterAll, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';

import { ChangeNoticeAction } from '../../../src/pages/results/ChangeNoticeAction';
import { moduleByRecordType } from '../../../src/pages/results/resultModules';
import { useAuth } from '../../../src/store/auth';

const MODULE = moduleByRecordType('CostEstResult');

/** mock 内存态：这张记录有没有开着的变更单。 */
let openNotice: {
  record_type: string;
  record_id: string;
  has_open_notice: boolean;
  deliverable_id: string | null;
  version_id: string | null;
  doc_no: string | null;
  sign_status: string | null;
  title: string | null;
} | null = null;

/** 收到的作废请求（断言「发了什么」）。 */
let cancelCalls: { reason: string }[] = [];

const server = setupServer(
  http.get('/api/v1/records/:module/:record_id/change-notice', ({ params }) => {
    if (openNotice) return HttpResponse.json(openNotice);
    return HttpResponse.json({
      record_type: String(params['module']),
      record_id: String(params['record_id']),
      has_open_notice: false,
      deliverable_id: null,
      version_id: null,
      doc_no: null,
      sign_status: null,
      title: null,
    });
  }),
  http.post('/api/v1/records/:module/:record_id/change-notice/cancel', async ({ request }) => {
    const body = (await request.json()) as { reason: string };
    cancelCalls.push(body);
    if (!body.reason || !body.reason.trim()) {
      return HttpResponse.json(
        { code: 'CHANGE_NOTICE_CANCEL_REASON_REQUIRED', message: '作废变更单必须填写理由' },
        { status: 422 },
      );
    }
    openNotice = null;
    return HttpResponse.json({
      deliverable_id: 'cn-1',
      doc_no: 'CN-0001',
      record_type: MODULE.recordType,
      record_id: 'r-1',
      sign_status: 'OBSOLETE',
    });
  }),
);

function renderChanged(onStatusChange = () => undefined): void {
  render(
    <ChangeNoticeAction
      module={MODULE}
      row={{ result_id: 'r-1', sign_status: 'CHANGED' }}
      onStatusChange={onStatusChange}
    />,
  );
}

describe('ChangeNoticeAction —— 变更单的作废入口', () => {
  beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
  afterAll(() => server.close());
  beforeEach(() => {
    cancelCalls = [];
    openNotice = null;
    useAuth.getState().setSession({
      access_token: 'test-token',
      refresh_token: 'r',
      username: 'u',
      role: 'DESIGNER',
      user_id: 'u',
    });
  });

  it('RF-1：没有开着的变更单 ⇒ 弹窗仍是「创建变更单」的表单', async () => {
    const user = userEvent.setup();
    renderChanged();
    await user.click(screen.getByTestId('change-notice-action'));

    await waitFor(() => expect(screen.getByText('变更类型')).toBeTruthy());
    expect(screen.queryByTestId('change-notice-open-hint')).toBeNull();
  });

  it('RF-2：已经有开着的变更单 ⇒ 弹窗改成「作废这张变更单」', async () => {
    const user = userEvent.setup();
    openNotice = {
      record_type: MODULE.recordType,
      record_id: 'r-1',
      has_open_notice: true,
      deliverable_id: 'cn-1',
      version_id: 'cnv-1',
      doc_no: 'CN-0001',
      sign_status: 'PENDING',
      title: '变更单',
    };
    renderChanged();
    await user.click(screen.getByTestId('change-notice-action'));

    await waitFor(() => expect(screen.getByTestId('change-notice-open-hint')).toBeTruthy());
    expect(screen.getByTestId('change-notice-open-hint').textContent).toContain('CN-0001');
    // 创建表单**不**出现（再建一张会被后端 409）
    expect(screen.queryByText('变更类型')).toBeNull();
  });

  it('RF-3/RF-4：填理由 ⇒ 调作废端点；记录状态**不变**', async () => {
    const user = userEvent.setup();
    const changes: string[] = [];
    openNotice = {
      record_type: MODULE.recordType,
      record_id: 'r-1',
      has_open_notice: true,
      deliverable_id: 'cn-1',
      version_id: 'cnv-1',
      doc_no: 'CN-0001',
      sign_status: 'PENDING',
      title: '变更单',
    };
    renderChanged((_id, next) => changes.push(next));
    await user.click(screen.getByTestId('change-notice-action'));
    await waitFor(() => expect(screen.getByTestId('change-notice-open-hint')).toBeTruthy());

    // 弹窗里只有一个输入框（作废理由）
    await user.type(screen.getByRole('textbox'), '这张单建错了');
    await user.click(screen.getByRole('button', { name: '作废变更单' }));

    await waitFor(() => expect(cancelCalls).toHaveLength(1));
    expect(cancelCalls[0].reason).toBe('这张单建错了');
    // ⚠️ 作废的是**单据** ⇒ 记录仍 CHANGED
    expect(changes).toEqual(['CHANGED']);
  });
});
