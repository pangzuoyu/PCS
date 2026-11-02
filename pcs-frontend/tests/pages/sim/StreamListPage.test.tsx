/**
 * SIM 物流列表页测试（SPEC §7.7.1 · P9B-3 · T6）。
 *
 * 守五件事：
 * 1. 工具栏有 **导入 / 新建物流 / 导出**，**没有**「批量提交校对」（⏳ P9B-3b）
 * 2. 筛选 **工况 / 相态 / 状态 / 来源** 四项，改一项 ⇒ **重新请求后端**
 *    （带 query 参数；后端按 AND 组合）
 * 3. 行操作有 **查看 / 校对 / 变更**
 * 4. 「校对」⇒ `POST /streams/{id}/submit` ⇒ 成功后徽章变 IN_APPROVAL；
 *    失败（403）⇒ 显示错误且**状态不变**
 * 5. ⚠️ **未知 `sign_status`** ⇒ 列表**照常渲染**（不是整页崩）
 *
 * ⚠️ 页面**自己取数**（T6 改成自取）⇒ 测试用 MSW 拦请求并**记录 URL**，
 * 这样「筛选有没有真的带上 query 参数」是可断言的（前端过滤做不到这个口径）。
 */
import { describe, it, expect, beforeAll, afterAll, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';
import { MemoryRouter } from 'react-router-dom';

import { StreamListPage } from '../../../src/pages/sim/StreamListPage';
import type { components } from '../../../src/types/api';

type Stream = components['schemas']['StreamResponse'];

function makeStream(over: Partial<Stream> = {}): Stream {
  return {
    stream_id: 's-1',
    stream_name: '新鲜进料',
    phase: 'LIQUID',
    temp: 25,
    press: 0.5,
    mass_flow: 10000,
    molar_flow: 100,
    composition_json: { N2: 0.78, O2: 0.22 },
    sign_status: 'DRAFT',
    record_hash: 'a3f9b2e1c21ed7a8',
    case_type: 'NORMAL',
    data_mode: 'CHEMICAL',
    source_type: 'MANUAL_ENTRY',
    source: 'MANUAL',
    approval_depth: 2,
    created_at: '2026-09-15 14:00',
    updated_at: '2026-09-15 14:32',
    ...over,
  };
}

/** 当前列表（mock 的内存态）。 */
let rows: Stream[] = [makeStream()];
/** 每次列表请求的 URL（用来断言筛选的 query 参数）。 */
let listUrls: string[] = [];
/** 提交校对的 HTTP 状态（200 = 成功；403 = 无权）。 */
let submitStatus = 200;
/** 提交校对是否改内存态（模拟后端把 DRAFT 推进 IN_APPROVAL）。 */
let submitMutates = true;

const server = setupServer(
  http.get('/api/v1/projects/:project_id/streams', ({ request }) => {
    listUrls.push(request.url);
    return HttpResponse.json(rows);
  }),
  http.post('/api/v1/streams/:stream_id/submit', ({ params }) => {
    if (submitStatus !== 200) {
      return HttpResponse.json(
        {
          code: 'HTTP_403',
          message: "需要角色 ['DESIGNER', 'SYSTEM_ADMIN']",
          detail: null,
          trace_id: 't-403',
        },
        { status: 403 },
      );
    }
    const id = String(params['stream_id']);
    if (submitMutates) {
      rows = rows.map((r) =>
        r.stream_id === id ? { ...r, sign_status: 'IN_APPROVAL' } : r,
      );
    }
    return HttpResponse.json({ stream_id: id, sign_status: 'IN_APPROVAL' });
  }),
);

/**
 * antd 的 Button 会在**两个中文字之间插空格**（`autoInsertSpace`）⇒
 * 「导入」在 DOM 里是「导 入」⇒ 断言前先去掉空格。
 */
function btnText(testId: string): string {
  return (screen.getByTestId(testId).textContent ?? '').replace(/\s/g, '');
}

function renderPage() {
  return render(
    <MemoryRouter>
      <StreamListPage projectId="00000000-0000-0000-0000-000000000001" />
    </MemoryRouter>,
  );
}

describe('StreamListPage —— SPEC §7.7.1 物流列表（T6）', () => {
  beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
  afterAll(() => server.close());
  beforeEach(() => {
    rows = [makeStream()];
    listUrls = [];
    submitStatus = 200;
    submitMutates = true;
  });

  it('工具栏有 导入 / 新建物流 / 导出，**没有**「批量提交校对」', async () => {
    renderPage();
    await waitFor(() => expect(screen.getByTestId('stream-import')).toBeTruthy());

    expect(btnText('stream-import')).toBe('导入');
    expect(btnText('stream-create')).toBe('新建物流');
    expect(btnText('stream-export')).toBe('导出');
    // ⚠️ 批量提交校对在 P9B-3b ⇒ **不得**出现（SPEC §7.7.1 标 ⏳）
    expect(screen.queryByText('批量提交校对')).toBeNull();
  });

  it('筛选有 工况 / 相态 / 状态 / 来源 四项', async () => {
    renderPage();
    await waitFor(() => expect(screen.getByTestId('stream-filter-source')).toBeTruthy());

    expect(screen.getByTestId('stream-filter-case-type')).toBeTruthy();
    expect(screen.getByTestId('stream-filter-phase')).toBeTruthy();
    expect(screen.getByTestId('stream-filter-sign-status')).toBeTruthy();
    expect(screen.getByTestId('stream-filter-source')).toBeTruthy();
  });

  it('⚠️ 改「来源」筛选 ⇒ **重新请求后端**且带 `source=` 参数', async () => {
    renderPage();
    await waitFor(() => expect(listUrls.length).toBe(1));

    const box = screen.getByTestId('stream-filter-source');
    const selector = box.querySelector('.ant-select-selector') as HTMLElement;
    fireEvent.mouseDown(selector);
    await waitFor(() => expect(document.querySelector('.ant-select-dropdown')).toBeTruthy());
    const dropdown = document.querySelector('.ant-select-dropdown') as HTMLElement;
    const option = within(dropdown).getByText('模拟软件').closest('.ant-select-item') as HTMLElement;
    fireEvent.click(option);

    await waitFor(() => expect(listUrls.length).toBe(2));
    // ⚠️ 参数名与值必须是 `source=SIM_IMPORT`（4 值 · 录入通道，**不是** source_type）
    expect(listUrls[1]).toContain('source=SIM_IMPORT');
  });

  it('行操作有 查看 / 校对 / 变更 三个入口', async () => {
    renderPage();
    await waitFor(() => expect(screen.getByTestId('stream-row')).toBeTruthy());

    expect(btnText('stream-view-s-1')).toBe('查看');
    expect(btnText('stream-submit-s-1')).toBe('校对');
    expect(btnText('stream-change-s-1')).toBe('变更');
  });

  it('⚠️ 点「校对」⇒ 提交校对 ⇒ 该行状态徽章变 IN_APPROVAL', async () => {
    renderPage();
    await waitFor(() => expect(screen.getByTestId('stream-row')).toBeTruthy());
    expect(screen.getByTestId('stream-row').getAttribute('data-status')).toBe('DRAFT');

    fireEvent.click(screen.getByTestId('stream-submit-s-1'));

    await waitFor(() =>
      expect(screen.getByTestId('stream-row').getAttribute('data-status')).toBe('IN_APPROVAL'),
    );
    expect(screen.getByTestId('state-badge-label').textContent).toBe('审批中');
  });

  it('⚠️ 校对失败（403）⇒ 显示错误且**状态不变**', async () => {
    submitStatus = 403;
    renderPage();
    await waitFor(() => expect(screen.getByTestId('stream-row')).toBeTruthy());

    fireEvent.click(screen.getByTestId('stream-submit-s-1'));

    await waitFor(() => expect(screen.getByTestId('stream-row-error')).toBeTruthy());
    expect(screen.getByTestId('stream-row-error').textContent).toContain('无权');
    // ⚠️ 状态**不变**（后端事务回滚）—— 徽章不能变成「审批中」
    expect(screen.getByTestId('stream-row').getAttribute('data-status')).toBe('DRAFT');
  });

  it('⚠️ 未知 sign_status ⇒ 列表**照常渲染**（不是整页崩）', async () => {
    // ⚠️ 后端新增一个状态时，前端的词表必然落后 ⇒ 页面必须**照常渲染**。
    //    这里模拟「契约词表之外」的值（运行时真值，类型上只能靠断言绕过）。
    rows = [
      makeStream({
        sign_status: 'SOMETHING_NEW' as unknown as Stream['sign_status'],
      }),
    ];
    renderPage();

    await waitFor(() => expect(screen.getByTestId('stream-row')).toBeTruthy());
    expect(screen.getByText('新鲜进料')).toBeTruthy();
    expect(screen.getByTestId('state-badge-label').textContent).toContain('SOMETHING_NEW');
  });
});
