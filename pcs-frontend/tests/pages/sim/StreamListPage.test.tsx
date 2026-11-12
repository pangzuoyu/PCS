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
    // ⚠️ **被引用数**（P9B-4 · TODO-108）：契约里它带默认值 ⇒ openapi-typescript
    //    生成的类型**是必填** ⇒ fixture 漏了就会 `tsc` 红（这是好事）。
    reference_count: 0,
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

/** 批量提交的请求记录（断言 body）。 */
let batchRequests: { ids: string[]; dryRun: boolean }[] = [];
/** 批量端点的 HTTP 状态（207 = 正常；422 = 超限）。 */
let batchStatus = 207;

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
  http.post('/api/v1/streams/batch-submit', async ({ request }) => {
    const body = (await request.json()) as {
      stream_ids: string[];
      dry_run?: boolean;
    };
    batchRequests.push({ ids: body.stream_ids, dryRun: body.dry_run === true });
    if (batchStatus !== 207) {
      return HttpResponse.json(
        {
          code: 'SIM_STREAM_BATCH_LIMIT_EXCEEDED',
          message: '批量提交 150 条，超过上限 100 条',
          detail: null,
          trace_id: 't-batch',
        },
        { status: batchStatus },
      );
    }
    const succeeded = body.stream_ids.map((id) => ({
      status: 'succeeded',
      stream_id: id,
      from_status: 'DRAFT',
      to_status: 'IN_APPROVAL',
      note: null,
    }));
    // ⚠️ mock 要**改内存态**（模拟后端把 DRAFT 推进 IN_APPROVAL）⇒
    //    否则「成功后列表刷新」那条测试验不到真东西。
    rows = rows.map((r) =>
      body.stream_ids.includes(r.stream_id)
        ? { ...r, sign_status: 'IN_APPROVAL' }
        : r,
    );
    return HttpResponse.json(
      {
        batch_id: 'b-1',
        total: succeeded.length,
        succeeded,
        failed: [],
        dry_run: body.dry_run === true,
        warning: null,
      },
      { status: 207 },
    );
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
    batchRequests = [];
    batchStatus = 207;
    // ⚠️ 必须 resetHandlers() —— 下面「部分失败」那条用 server.use() 临时
    //    覆盖了批量端点 ⇒ 不重置的话它会**泄漏**到后面的用例
    //    （下一条要测 422，不重置就会拿到 207 ⇒ 假红）。
    server.resetHandlers();
  });

  it('工具栏有 导入 / 新建物流 / 导出 / **批量提交校对**', async () => {
    renderPage();
    await waitFor(() => expect(screen.getByTestId('stream-import')).toBeTruthy());

    expect(btnText('stream-import')).toBe('导入');
    expect(btnText('stream-create')).toBe('新建物流');
    expect(btnText('stream-export')).toBe('导出');
    // ✅ P9B-3b：批量提交校对**已实现**（SPEC §7.7.1 ⏳ → ✅）
    expect(btnText('stream-batch-submit')).toBe('批量提交校对');
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

  it('⚠️ 改筛选条件 ⇒ **清掉行选择**（不许提交「看不见的行」）', async () => {
    // ⚠️ TODO-123 的形状：勾了 2 行 → 换筛选（列表变了）→ 旧选择**还在**
    //   ⇒ 点「批量提交校对」会提交**已经不在视野里**的那些行。
    //   ⇒ 用户无从判断自己提交了多少（按钮上也没显示「已选 N 条」）。
    rows = [makeStream(), makeStream({ stream_id: 's-2', stream_name: '塔顶气' })];
    renderPage();
    await waitFor(() => expect(screen.getAllByTestId('stream-row').length).toBe(2));

    // 勾选 2 行
    const cbs = document.querySelectorAll(
      '.ant-table-selection-column input[type="checkbox"]',
    ) as NodeListOf<HTMLInputElement>;
    fireEvent.click(cbs[1]!);
    fireEvent.click(cbs[2]!);
    await waitFor(() =>
      expect(screen.getByTestId('stream-batch-submit')).not.toBeDisabled(),
    );

    // 换筛选 ⇒ 列表重新加载 ⇒ **选择必须被清掉**
    const box = screen.getByTestId('stream-filter-source');
    const selector = box.querySelector('.ant-select-selector') as HTMLElement;
    fireEvent.mouseDown(selector);
    await waitFor(() => expect(document.querySelector('.ant-select-dropdown')).toBeTruthy());
    const dropdown = document.querySelector('.ant-select-dropdown') as HTMLElement;
    const option = within(dropdown).getByText('模拟软件').closest('.ant-select-item') as HTMLElement;
    fireEvent.click(option);
    await waitFor(() => expect(listUrls.length).toBe(2));

    // ⚠️ 换了筛选 ⇒ 旧的选择**必须**清掉（否则会提交看不见的行）
    await waitFor(() =>
      expect(screen.getByTestId('stream-batch-submit')).toBeDisabled(),
    );
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

  it('⚠️ 没选中行 ⇒ 「批量提交校对」**禁用**', async () => {
    renderPage();
    await waitFor(() => expect(screen.getByTestId('stream-row')).toBeTruthy());

    expect(screen.getByTestId('stream-batch-submit')).toBeDisabled();
  });

  it('⚠️ 选中行 ⇒ 点「批量提交校对」⇒ POST 选中的 id 列表', async () => {
    rows = [makeStream(), makeStream({ stream_id: 's-2', stream_name: '塔顶气' })];
    renderPage();
    await waitFor(() => expect(screen.getAllByTestId('stream-row').length).toBe(2));

    // ⚠️ antd 的行选择框在表格的选择列里（`.ant-table-selection-column`）
    const headerCheckbox = document.querySelector(
      '.ant-table-selection-column .ant-checkbox-input',
    ) as HTMLInputElement;
    fireEvent.click(headerCheckbox);

    await waitFor(() =>
      expect(screen.getByTestId('stream-batch-submit')).not.toBeDisabled(),
    );
    fireEvent.click(screen.getByTestId('stream-batch-submit'));

    await waitFor(() => expect(batchRequests.length).toBe(1));
    expect(batchRequests[0].ids.sort()).toEqual(['s-1', 's-2']);
    expect(batchRequests[0].dryRun).toBe(false);
  });

  it('⚠️ 批量结果 ⇒ 弹窗显示「成功 N · 失败 M」', async () => {
    renderPage();
    await waitFor(() => expect(screen.getByTestId('stream-row')).toBeTruthy());

    const headerCheckbox = document.querySelector(
      '.ant-table-selection-column .ant-checkbox-input',
    ) as HTMLInputElement;
    fireEvent.click(headerCheckbox);
    await waitFor(() =>
      expect(screen.getByTestId('stream-batch-submit')).not.toBeDisabled(),
    );
    fireEvent.click(screen.getByTestId('stream-batch-submit'));

    await waitFor(() => expect(screen.getByTestId('stream-batch-summary')).toBeTruthy());
    expect(screen.getByTestId('stream-batch-summary').textContent).toContain('成功 1');
    expect(screen.getByTestId('stream-batch-summary').textContent).toContain('失败 0');
  });

  it('⚠️ 批量部分失败 ⇒ 摘要显示失败数 + 每条原因', async () => {
    // ⚠️ 207 是 2xx ⇒ axios **不抛异常** ⇒ 前端必须自己看 `failed`
    server.use(
      http.post('/api/v1/streams/batch-submit', async ({ request }) => {
        const body = (await request.json()) as { stream_ids: string[] };
        return HttpResponse.json(
          {
            batch_id: 'b-2',
            total: body.stream_ids.length,
            succeeded: [
              {
                status: 'succeeded',
                stream_id: body.stream_ids[0],
                from_status: 'DRAFT',
                to_status: 'IN_APPROVAL',
                note: null,
              },
            ],
            failed: [
              {
                status: 'failed',
                stream_id: body.stream_ids[1] ?? 's-2',
                reason: 'SIM_STREAM_COMPOSITION_OUT_OF_RANGE',
                detail: '组成摩尔分率合计 98.70%，不在 100±0.5% 内',
              },
            ],
            dry_run: false,
            warning: null,
          },
          { status: 207 },
        );
      }),
    );
    rows = [makeStream(), makeStream({ stream_id: 's-2', stream_name: '塔顶气' })];
    renderPage();
    await waitFor(() => expect(screen.getAllByTestId('stream-row').length).toBe(2));

    const headerCheckbox = document.querySelector(
      '.ant-table-selection-column .ant-checkbox-input',
    ) as HTMLInputElement;
    fireEvent.click(headerCheckbox);
    await waitFor(() =>
      expect(screen.getByTestId('stream-batch-submit')).not.toBeDisabled(),
    );
    fireEvent.click(screen.getByTestId('stream-batch-submit'));

    await waitFor(() => expect(screen.getByTestId('stream-batch-summary')).toBeTruthy());
    const summary = screen.getByTestId('stream-batch-summary').textContent ?? '';
    expect(summary).toContain('成功 1');
    expect(summary).toContain('失败 1');
    // ⚠️ 每条失败**带原因**（用户要知道为什么失败）
    const failures = screen.getByTestId('stream-batch-failures').textContent ?? '';
    expect(failures).toContain('SIM_STREAM_COMPOSITION_OUT_OF_RANGE');
    // ⚠️ **关闭提示**（P9B-4 · TODO-116 落地后改写）：失败清单**不再**随弹窗关闭
    //    而丢 ⇒ 提示改成「关掉也能重试」。
    expect(screen.getByTestId('stream-batch-close-hint').textContent).toContain(
      '关闭弹窗后仍可用上方「只重试失败项」重试这 1 条',
    );
  });

  it('⚠️ 批量部分失败 ⇒ 关闭弹窗后仍能「只重试失败项」（TODO-116）', async () => {
    // ⚠️ 这是 TODO-116 的核心：失败清单**不随弹窗关闭而丢** ⇒ 用户能一键重试。
    const sent: string[][] = [];
    server.use(
      http.post('/api/v1/streams/batch-submit', async ({ request }) => {
        const body = (await request.json()) as { stream_ids: string[] };
        sent.push(body.stream_ids);
        return HttpResponse.json(
          {
            batch_id: 'b-retry',
            total: body.stream_ids.length,
            succeeded: [
              {
                status: 'succeeded',
                stream_id: body.stream_ids[0],
                from_status: 'DRAFT',
                to_status: 'IN_APPROVAL',
                note: null,
              },
            ],
            failed: [
              {
                status: 'failed',
                stream_id: body.stream_ids[1] ?? 's-2',
                reason: 'SIM_STREAM_COMPOSITION_OUT_OF_RANGE',
                detail: '组成摩尔分率合计 98.70%，不在 100±0.5% 内',
              },
            ],
            dry_run: false,
            warning: null,
          },
          { status: 207 },
        );
      }),
    );
    rows = [makeStream(), makeStream({ stream_id: 's-2', stream_name: '塔顶气' })];
    renderPage();
    await waitFor(() => expect(screen.getAllByTestId('stream-row').length).toBe(2));

    const headerCheckbox = document.querySelector(
      '.ant-table-selection-column .ant-checkbox-input',
    ) as HTMLInputElement;
    fireEvent.click(headerCheckbox);
    await waitFor(() =>
      expect(screen.getByTestId('stream-batch-submit')).not.toBeDisabled(),
    );
    fireEvent.click(screen.getByTestId('stream-batch-submit'));
    await waitFor(() => expect(screen.getByTestId('stream-batch-summary')).toBeTruthy());

    // ⚠️ 关闭弹窗
    fireEvent.click(screen.getByTestId('stream-batch-close'));

    // ⚠️ **失败清单条仍在**（不在弹窗里）
    await waitFor(() => expect(screen.getByTestId('stream-batch-failure-bar')).toBeTruthy());
    expect(screen.getByTestId('stream-batch-failure-bar').textContent).toContain('失败 1 条');

    // ⚠️ 点「只重试失败项」⇒ **只发失败的那条**
    fireEvent.click(screen.getByTestId('stream-batch-retry-failed'));
    await waitFor(() => expect(sent.length).toBe(2));
    expect(sent[0]).toHaveLength(2);
    expect(sent[1]).toEqual(['s-2']);
  });

  it('失败清单条可「清除」', async () => {
    server.use(
      http.post('/api/v1/streams/batch-submit', async ({ request }) => {
        const body = (await request.json()) as { stream_ids: string[] };
        return HttpResponse.json(
          {
            batch_id: 'b-clear',
            total: body.stream_ids.length,
            succeeded: [],
            failed: [
              {
                status: 'failed',
                stream_id: body.stream_ids[0] ?? 's-1',
                reason: 'SIM_STREAM_COMPOSITION_OUT_OF_RANGE',
                detail: null,
              },
            ],
            dry_run: false,
            warning: null,
          },
          { status: 207 },
        );
      }),
    );
    rows = [makeStream()];
    renderPage();
    await waitFor(() => expect(screen.getByTestId('stream-row')).toBeTruthy());

    const cbs = document.querySelectorAll(
      '.ant-table-selection-column input[type="checkbox"]',
    ) as NodeListOf<HTMLInputElement>;
    fireEvent.click(cbs[1]!);
    await waitFor(() =>
      expect(screen.getByTestId('stream-batch-submit')).not.toBeDisabled(),
    );
    fireEvent.click(screen.getByTestId('stream-batch-submit'));
    await waitFor(() => expect(screen.getByTestId('stream-batch-summary')).toBeTruthy());
    fireEvent.click(screen.getByTestId('stream-batch-close'));

    await waitFor(() => expect(screen.getByTestId('stream-batch-failure-bar')).toBeTruthy());
    fireEvent.click(screen.getByTestId('stream-batch-clear-failures'));
    // ⚠️ 清单条**消失**
    await waitFor(() => expect(screen.queryByTestId('stream-batch-failure-bar')).toBeNull());
  });

  it('⚠️ 403 ⇒ 文案说「无权**提交**」（不是「无权查看」）', async () => {
    // ⚠️ TODO-127 的形状：`describePcsError` 的 403 分支一律说「无权查看」
    //   ⇒ 但批量提交是**写**操作 ⇒ 用户看到「无权查看：需要角色 [...]」
    //   ⇒ 他刚才在提交，不是��看 ⇒ 困惑。
    server.use(
      http.post('/api/v1/streams/batch-submit', () =>
        HttpResponse.json(
          { code: 'HTTP_403', message: '需要角色 [DESIGNER]', detail: null, trace_id: 't-403' },
          { status: 403 },
        ),
      ),
    );
    renderPage();
    await waitFor(() => expect(screen.getByTestId('stream-row')).toBeTruthy());

    const cbs = document.querySelectorAll(
      '.ant-table-selection-column input[type="checkbox"]',
    ) as NodeListOf<HTMLInputElement>;
    fireEvent.click(cbs[1]!);
    await waitFor(() =>
      expect(screen.getByTestId('stream-batch-submit')).not.toBeDisabled(),
    );
    fireEvent.click(screen.getByTestId('stream-batch-submit'));

    await waitFor(() => expect(screen.getByTestId('stream-batch-error')).toBeTruthy());
    const err = screen.getByTestId('stream-batch-error').textContent ?? '';
    // ⚠️ 写操作 ⇒ 「无权提交」，**不是**「无权查看」
    expect(err).toContain('无权提交');
    expect(err).not.toContain('无权查看');
  });

  it('⚠️ 批量请求本身失败（422 超限）⇒ 显示错误，**不**显示结果摘要', async () => {
    batchStatus = 422;
    renderPage();
    await waitFor(() => expect(screen.getByTestId('stream-row')).toBeTruthy());

    const headerCheckbox = document.querySelector(
      '.ant-table-selection-column .ant-checkbox-input',
    ) as HTMLInputElement;
    fireEvent.click(headerCheckbox);
    await waitFor(() =>
      expect(screen.getByTestId('stream-batch-submit')).not.toBeDisabled(),
    );
    fireEvent.click(screen.getByTestId('stream-batch-submit'));

    await waitFor(() => expect(screen.getByTestId('stream-batch-error')).toBeTruthy());
    expect(screen.getByTestId('stream-batch-error').textContent).toContain('上限');
    expect(screen.queryByTestId('stream-batch-summary')).toBeNull();
    // ⚠️ 请求失败 ⇒ **状态不变**（后端没执行）
    expect(screen.getByTestId('stream-row').getAttribute('data-status')).toBe('DRAFT');
  });

  it('「引用」列渲染 📎N（0 ⇒ —）', async () => {
    // ⚠️ **口径**（P9B-4 · TODO-108）：下游物流数 + 闪蒸结果数；
    //    **不含**状态点（子表）⇒ 每条物流都有的东西**不画** 📎。
    rows = [
      makeStream({ reference_count: 3 }),
      makeStream({ stream_id: 's-2', stream_name: '塔顶气', reference_count: 0 }),
    ];
    renderPage();
    await waitFor(() => expect(screen.getAllByTestId('stream-row').length).toBe(2));

    // ⚠️ 只有**非零**的那条画 📎（0 ⇒ 「—」⇒ 不噪声）
    const refs = screen.getAllByTestId('stream-reference-count');
    expect(refs.length).toBe(1);
    expect(refs[0].textContent).toContain('📎3');
    const cells = document.querySelectorAll('.ant-table-tbody tr.ant-table-row');
    expect(cells[1].textContent).toContain('—');
  });

  it('⚠️ 批量成功后 ⇒ **列表刷新**（那一行的徽章变 IN_APPROVAL）', async () => {
    renderPage();
    await waitFor(() => expect(screen.getByTestId('stream-row')).toBeTruthy());

    const headerCheckbox = document.querySelector(
      '.ant-table-selection-column .ant-checkbox-input',
    ) as HTMLInputElement;
    fireEvent.click(headerCheckbox);
    await waitFor(() =>
      expect(screen.getByTestId('stream-batch-submit')).not.toBeDisabled(),
    );
    fireEvent.click(screen.getByTestId('stream-batch-submit'));

    // ⚠️ 后端返回的**最新态**才是真相 ⇒ 前端必须重新拉列表
    await waitFor(() =>
      expect(screen.getByTestId('stream-row').getAttribute('data-status')).toBe(
        'IN_APPROVAL',
      ),
    );
    expect(screen.getByTestId('state-badge-label').textContent).toBe('审批中');
  });

  it('⚠️ 摘要要**区分**「真提交」与「幂等命中」（本来就在审批中的）', async () => {
    // ⚠️ TODO-124 的形状：契约的 `note` 有 `already_in_approval`
    //   （那条**本来就在审批中**、这次**并没有真的提交**）⇒
    //   但摘要只显示「成功 N · 失败 M」⇒ N **包含**幂等命中
    //   ⇒ 用户以为提交了 N 条。
    server.use(
      http.post('/api/v1/streams/batch-submit', async () =>
        HttpResponse.json(
          {
            batch_id: 'b-idem',
            total: 2,
            succeeded: [
              {
                status: 'succeeded',
                stream_id: 's-1',
                from_status: 'DRAFT',
                to_status: 'IN_APPROVAL',
                note: null,
              },
              {
                status: 'succeeded',
                stream_id: 's-2',
                from_status: 'IN_APPROVAL',
                to_status: 'IN_APPROVAL',
                note: 'already_in_approval',
              },
            ],
            failed: [],
            dry_run: false,
            warning: null,
          },
          { status: 207 },
        ),
      ),
    );
    rows = [makeStream(), makeStream({ stream_id: 's-2', stream_name: '塔顶气' })];
    renderPage();
    await waitFor(() => expect(screen.getAllByTestId('stream-row').length).toBe(2));

    const cbs = document.querySelectorAll(
      '.ant-table-selection-column input[type="checkbox"]',
    ) as NodeListOf<HTMLInputElement>;
    fireEvent.click(cbs[1]!);
    fireEvent.click(cbs[2]!);
    await waitFor(() =>
      expect(screen.getByTestId('stream-batch-submit')).not.toBeDisabled(),
    );
    fireEvent.click(screen.getByTestId('stream-batch-submit'));

    await waitFor(() => expect(screen.getByTestId('stream-batch-summary')).toBeTruthy());
    // ⚠️ 「成功 2」里**含**了那条幂等命中 ⇒ 必须**另外**说明它没被真提交
    const summary = screen.getByTestId('stream-batch-summary').textContent ?? '';
    expect(summary).toContain('成功 2');
    // ⚠️ 幂等提示单独一行（契约的 `note === 'already_in_approval'`）
    const hint = await screen.findByTestId('stream-batch-idempotent-hint');
    expect(hint.textContent).toContain('1');
    expect(hint.textContent).toMatch(/本来就在审批中|已在审批中|幂等/);
  });

  it('⚠️ 连点两次「批量提交校对」⇒ **只发一次请求**', async () => {
    renderPage();
    await waitFor(() => expect(screen.getByTestId('stream-row')).toBeTruthy());

    const headerCheckbox = document.querySelector(
      '.ant-table-selection-column .ant-checkbox-input',
    ) as HTMLInputElement;
    fireEvent.click(headerCheckbox);
    await waitFor(() =>
      expect(screen.getByTestId('stream-batch-submit')).not.toBeDisabled(),
    );

    const btn = screen.getByTestId('stream-batch-submit');
    fireEvent.click(btn);
    fireEvent.click(btn); // ⚠️ 连点

    await waitFor(() => expect(batchRequests.length).toBeGreaterThan(0));
    // ⚠️ 提交进行中按钮**禁用** ⇒ 第二次点击不该再发一次
    expect(batchRequests.length).toBe(1);
  });

  it('⚠️ 批次级 `warning`（如批次记录写失败）⇒ 摘要里**如实显示**', async () => {
    server.use(
      http.post('/api/v1/streams/batch-submit', async ({ request }) => {
        const body = (await request.json()) as { stream_ids: string[] };
        return HttpResponse.json(
          {
            batch_id: 'b-3',
            total: body.stream_ids.length,
            succeeded: [
              {
                status: 'succeeded',
                stream_id: body.stream_ids[0],
                from_status: 'DRAFT',
                to_status: 'IN_APPROVAL',
                note: null,
              },
            ],
            failed: [],
            dry_run: false,
            // ⚠️ 批次审计写失败 ⇒ 条目**已提交**，但批次记录没写成
            warning: '已提交 1 条，但批次记录写入失败，请联系管理员',
          },
          { status: 207 },
        );
      }),
    );
    renderPage();
    await waitFor(() => expect(screen.getByTestId('stream-row')).toBeTruthy());

    const headerCheckbox = document.querySelector(
      '.ant-table-selection-column .ant-checkbox-input',
    ) as HTMLInputElement;
    fireEvent.click(headerCheckbox);
    await waitFor(() =>
      expect(screen.getByTestId('stream-batch-submit')).not.toBeDisabled(),
    );
    fireEvent.click(screen.getByTestId('stream-batch-submit'));

    await waitFor(() => expect(screen.getByTestId('stream-batch-warning')).toBeTruthy());
    expect(screen.getByTestId('stream-batch-warning').textContent).toContain(
      '批次记录写入失败',
    );
  });

  // -------------------------------------------------------------------------
  // CSV 导出（评审 #27）
  // -------------------------------------------------------------------------

  it('⚠️ CSV 导出**含「引用」列**（评审 #27）—— 导出内容与屏幕所见一致', async () => {
    // ⚠️ **导出的数据必须与用户看到的表一致** —— SPEC §7.7.1 把「引用」定成
    //    一列**正式列**（表上渲染了）⇒ 导出却不含它 ⇒ 导出件**静默缺列**
    //    ⇒ 用户拿导出件做统计 ⇒ 漏掉「这条物流被引用」这个关键信息。
    rows = [makeStream({ reference_count: 3 })];

    const blobs: Blob[] = [];
    const origCreate = URL.createObjectURL;
    const origRevoke = URL.revokeObjectURL;
    URL.createObjectURL = ((b: Blob) => {
      blobs.push(b);
      return 'blob:mock';
    }) as unknown as typeof URL.createObjectURL;
    URL.revokeObjectURL = (() => undefined) as unknown as typeof URL.revokeObjectURL;

    try {
      renderPage();
      await waitFor(() => expect(screen.getByTestId('stream-row')).toBeTruthy());
      fireEvent.click(screen.getByTestId('stream-export'));

      await waitFor(() => expect(blobs.length).toBe(1));
      // ⚠️ jsdom 的 `Blob` **没有** `.text()` ⇒ 用 `FileReader` 读
      const csv = await new Promise<string>((resolve, reject) => {
        const fr = new FileReader();
        fr.onload = () => resolve(String(fr.result));
        fr.onerror = () => reject(fr.error);
        fr.readAsText(blobs[0]);
      });
      // ⚠️ BOM 在最前 ⇒ 断言用「包含」而不是「相等」
      expect(csv).toContain('引用');
      // ⚠️ 表头与数据行的列数必须一致 ⇒ 不一致 ⇒ 表格错位
      const lines = csv.split('\r\n').filter((l) => l.length > 0);
      expect(lines[0].split(',')).toContain('引用');
      expect(lines[1].split(',')).toContain('3');
    } finally {
      URL.createObjectURL = origCreate;
      URL.revokeObjectURL = origRevoke;
    }
  });
});
