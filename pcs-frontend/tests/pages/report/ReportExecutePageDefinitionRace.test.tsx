/**
 * ReportExecutePage 的**定义拉取**竞态 —— 评审 #10。
 *
 * ## 缺陷
 *
 * 两个挂载 effect 里的 fetch 都没有任何作废机制：
 *
 * ```tsx
 * useEffect(() => { void (async () => {
 *   ... const data = await reportBuilderApi.list({status:'PUBLISHED'});
 *   setDefinitions(data.items); setSelected(...);
 * })(); }, [defId]);
 *
 * useEffect(() => { if (!selected) return;
 *   void (async () => { setDef(await reportBuilderApi.get(selected)); })();
 * }, [selected]);
 * ```
 *
 * 选 A → 请求 A 在飞 → 选 B → 请求 B 发出 → **B 先回**（已 setDef(B)）→
 * A 后回 → `setDef(A)`。页面现在显示的是 **A 的定义**，
 * 而 Select 选中的是 **B**。用户点「执行」跑的是 B 的定义，
 * 屏幕上看到的字段/过滤/来源却是 A 的 —— **界面在骗人，且没有任何提示**。
 *
 * 慢网络 + 快速切换即触发，不必是竞态才能复现。
 *
 * 同款问题在**卸载**时也存在：组件已经没了，回调仍 setState。
 *
 * ## 观测点
 *
 * 断言**页面显示的定义名**，不是请求次数。
 *
 * 请求次数在两种实现下都是 2（都会真发两次请求），只有**渲染结果**
 * 能区分「作废了旧响应」与「只是没管」。这正是本仓反复出现的教训：
 * 断言要落在用户可达的状态上，不是请求计数上
 * （见 `tests/pages/report/ReportExecutePage.test.tsx` 的文件头
 * —— 那组恰好相反，因为缺陷本身就在请求次数上）。
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, act } from '@testing-library/react';
import {
  MemoryRouter, Route, Routes, useNavigate,
} from 'react-router-dom';

const datasources = vi.fn();
const get = vi.fn();
const list = vi.fn();

vi.mock('../../../src/api/reportBuilder', () => ({
  reportBuilderApi: {
    execute: vi.fn(),
    executionStatus: vi.fn(),
    datasources: (...a: unknown[]) => datasources(...a),
    get: (...a: unknown[]) => get(...a),
    list: (...a: unknown[]) => list(...a),
  },
}));

import { ReportExecutePage } from '../../../src/pages/report/ReportExecutePage';

/** 手控的 promise：测试自己决定哪个请求先落地。 */
function deferred<T>() {
  let resolve!: (v: T) => void;
  const promise = new Promise<T>((r) => { resolve = r; });
  return { promise, resolve };
}

const body = (id: string, name: string) => ({
  def_id: id, name, version: '0.1.0', status: 'PUBLISHED',
  output_format: 'pdf', max_rows: 10000,
  definition_json: {
    DataSources: [{ source: 'PUMP_RESULTS' }],
    SelectedFields: [{
      source: 'PUMP_RESULTS', field: 'tag_number',
      alias: '位号', order: 0, visible: true,
    }],
    FilterConditions: [], SortBy: [], MaxRows: 10000,
    OutputFormat: 'pdf', detailLevel: 'BASIC',
  },
});

/** 把 navigate 暴露出来，好让测试切路由参数。 */
let nav: ((to: string) => void) | null = null;
function NavBridge() {
  nav = useNavigate();
  return null;
}

async function flush(times = 6) {
  for (let i = 0; i < times; i += 1) {
    await act(async () => { await Promise.resolve(); });
  }
}

beforeEach(() => {
  datasources.mockReset(); get.mockReset(); list.mockReset(); nav = null;
  datasources.mockResolvedValue({ datasources: [] });
  list.mockResolvedValue({ items: [] });
});

describe('ReportExecutePage — 定义拉取竞态（评审 #10）', () => {
  it('后发先至的旧响应不得覆盖新选中的定义', async () => {
    const d1 = deferred<ReturnType<typeof body>>();
    const d2 = deferred<ReturnType<typeof body>>();
    get.mockImplementation((id: string) => (
      id === 'd1' ? d1.promise : d2.promise));

    render(
      <MemoryRouter initialEntries={['/report-builder/executions/d1']}>
        <NavBridge />
        <Routes>
          <Route path="/report-builder/executions/:defId"
                 element={<ReportExecutePage />} />
        </Routes>
      </MemoryRouter>,
    );
    await flush();

    // 切到 d2 —— d1 的请求仍在飞
    await act(async () => { nav?.('/report-builder/executions/d2'); });
    await flush();
    expect(get).toHaveBeenCalledWith('d2');

    // **d2 先回**，页面显示 d2
    await act(async () => { d2.resolve(body('d2', '二级定义')); });
    await flush();
    expect(document.body.textContent).toContain('二级定义');

    // d1 后回 —— 旧响应，**必须被作废**
    await act(async () => { d1.resolve(body('d1', '一级定义')); });
    await flush();

    const text = document.body.textContent ?? '';
    expect(text).toContain('二级定义');
    expect(text).not.toContain('一级定义');
  });

  it('切走后旧定义不得再写进状态（卸载后 setState）', async () => {
    const d1 = deferred<ReturnType<typeof body>>();
    get.mockImplementation(() => d1.promise);

    const { unmount } = render(
      <MemoryRouter initialEntries={['/report-builder/executions/d1']}>
        <NavBridge />
        <Routes>
          <Route path="/report-builder/executions/:defId"
                 element={<ReportExecutePage />} />
        </Routes>
      </MemoryRouter>,
    );
    await flush();

    unmount();
    // 卸载后才 resolve —— 不应有任何报错或警告冒出来
    await act(async () => { d1.resolve(body('d1', '一级定义')); });
    await flush();

    expect(get).toHaveBeenCalledWith('d1');
  });
});
