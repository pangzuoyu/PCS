/**
 * ReportExecutePage 的**轮询**行为 —— 评审 P1 #7 / #8。
 *
 * ## 为什么这两条要写
 *
 * 此前 `tests/pages/report/` **整个目录不存在**：报表执行页零组件测试。
 * 两处缺陷都发生在**时序**上（重跑、await 在飞、终态），
 * 而这类行为恰恰是最容易被「看起来能跑」掩盖的。
 *
 * ## 观测点
 *
 * 用**请求次数**而不是 UI 文案作主要断言。理由：两个缺陷的可见症状
 * （下载按钮指向旧文件 / 报假超时）都要等好几轮才出现，
 * 而「旧循环还活着」这件事在**第一次它多发一个请求**时就暴露了 ——
 * 那才是缺陷本身，文案只是后果。
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, act } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';

const execute = vi.fn();
const executionStatus = vi.fn();
const datasources = vi.fn();
const get = vi.fn();
const list = vi.fn();

vi.mock('../../../src/api/reportBuilder', () => ({
  reportBuilderApi: {
    execute: (...a: unknown[]) => execute(...a),
    executionStatus: (...a: unknown[]) => executionStatus(...a),
    datasources: (...a: unknown[]) => datasources(...a),
    get: (...a: unknown[]) => get(...a),
    list: (...a: unknown[]) => list(...a),
  },
}));

vi.mock('antd', async () => {
  const real = await vi.importActual<typeof import('antd')>('antd');
  return real;
});

/** 页面用 useParams/useNavigate —— 没有 Router 直接渲染会抛 invariant。 */
function renderPage() {
  return render(
    <MemoryRouter initialEntries={['/report-builder/executions/d1']}>
      <Routes>
        <Route path="/report-builder/executions/:defId"
               element={<ReportExecutePage />} />
      </Routes>
    </MemoryRouter>,
  );
}

import { ReportExecutePage } from '../../../src/pages/report/ReportExecutePage';

// 必须与页面里的 POLL_INTERVAL_MS 一致（ReportExecutePage.tsx:59）。
// 写成 1500 时 advance(1510) 打不到定时器，症状是
// 「executionStatus 计数为 0」—— 看着像没发起轮询，其实是差 500ms。
const POLL_INTERVAL = 2000;

/** 让所有定时器推进 n 毫秒，并放行微任务队列。 */
async function advance(ms: number) {
  await act(async () => {
    vi.advanceTimersByTime(ms);
    // ⚠️ 定时器回调里是一个 async IIFE：它先 `await executionStatus`，
    // 再 setState / 递归。只推进定时器不冲刷微任务的话，断言会跑在
    // 「请求已发出但状态还没落地」的中间态上（第一版就这么错，症状是
    // `executionStatus` 计数为 0 —— 断言跑得比回调快）。
    for (let i = 0; i < 8; i += 1) {
      await Promise.resolve();
    }
  });
}

beforeEach(() => {
  vi.useFakeTimers();
  execute.mockReset(); executionStatus.mockReset();
  datasources.mockReset(); list.mockReset(); get.mockReset();
  datasources.mockResolvedValue({ datasources: [] });
  list.mockResolvedValue({
    items: [{ def_id: 'd1', name: '泵数据表', version: '0.1.0', status: 'PUBLISHED' }],
  });
  get.mockResolvedValue({
    def_id: 'd1', name: '泵数据表', version: '0.1.0', status: 'PUBLISHED',
    output_format: 'pdf', max_rows: 10000, definition_json: {
      DataSources: [{ source: 'PUMP_RESULTS' }],
      SelectedFields: [{ source: 'PUMP_RESULTS', field: 'tag_number',
                         alias: '位号', order: 0, visible: true }],
      FilterConditions: [], SortBy: [], MaxRows: 10000,
      OutputFormat: 'pdf', detailLevel: 'BASIC',
    },
  });
  execute.mockResolvedValue({ task_id: 'task-1' });
});

afterEach(() => { vi.useRealTimers(); });

/**
 * 渲染并点「执行」。
 *
 * ⚠️ `selected` 由**路由参数** `defId` 播种（页面 :69 `useState(defId)`，
 * 另有 effect 取 `defId ?? items[0]`），所以**不需要**去驱动 antd Select ——
 * 那是 antd 私有 DOM，最脆的一环，与本组要验的时序无关。
 *
 * ⚠️ 用 `act` 冲刷而不是 `waitFor`：fake timers 下 `waitFor` 的内部定时器
 * 与 `vi.advanceTimersByTime` 互相等，直接死锁到超时（踩过一次）。
 */
async function flush() {
  for (let i = 0; i < 5; i += 1) {
    await act(async () => { await Promise.resolve(); });
  }
}

async function mountAndRun() {
  renderPage();
  await flush();                       // datasources + list + get 都 resolve
  fireEvent.click(screen.getByRole('button', { name: /执行/ }));
  await flush();                       // execute resolve → 进入 polling
}

describe('ReportExecutePage — 轮询终态（评审 P1 #8）', () => {
  it('status=FAILED 时立刻停下并报错，不空转到超时', async () => {
    executionStatus.mockResolvedValue({
      task_id: 'task-1', def_id: 'd1', status: 'FAILED', report_file_id: null,
    });
    await mountAndRun();
    await advance(POLL_INTERVAL + 10);

    // FAILED 是终态：**不该**出现「已提交，正在后台生成」这种继续等待的文案
    expect(document.body.textContent).not.toContain('正在后台生成');
    expect(document.body.textContent).toContain('执行失败');

    // 关键：**只问了一次**。若仍按「没有 report_file_id 就继续轮询」，
    // 第二次定时器会照常装上，这里就会 >= 2。
    await advance(POLL_INTERVAL * 10);
    expect(executionStatus).toHaveBeenCalledTimes(1);
  });

  it('FAILED 优先于 report_file_id —— 两者都有时也要报失败', async () => {
    // 回收器改判的行既可能有 report_file_id 也可能是 FAILED；
    // 若先判 file 就又会把「已完成」误报成成功，而库里已是 FAILED。
    executionStatus.mockResolvedValue({
      task_id: 'task-1', def_id: 'd1', status: 'FAILED', report_file_id: 'f1',
    });
    await mountAndRun();
    await advance(POLL_INTERVAL + 10);
    expect(document.body.textContent).toContain('执行失败');
  });

  it('RUNNING 时继续轮询，直到拿到 file 才停', async () => {
    executionStatus
      .mockResolvedValueOnce({ task_id: 'task-1', def_id: 'd1', status: 'RUNNING', report_file_id: null })
      .mockResolvedValueOnce({ task_id: 'task-1', def_id: 'd1', status: 'FINISHED', report_file_id: 'f1' });
    await mountAndRun();
    await advance(POLL_INTERVAL + 10);
    expect(executionStatus).toHaveBeenCalledTimes(1);
    await advance(POLL_INTERVAL + 10);
    expect(executionStatus).toHaveBeenCalledTimes(2);
    await advance(POLL_INTERVAL * 5);
    expect(executionStatus).toHaveBeenCalledTimes(2);   // 拿到 file 后不再问
  });
});

/**
 * ## #7 修完之后，什么还可达、什么不可达
 *
 * 原缺陷是「重跑或卸载会复活孤儿循环」。两条入口的现状不一样：
 *
 * - **重跑**：执行按钮在 polling 期间已 `disabled` ⇒ **UI 上不可达**。
 *   这是主防线，由「按钮禁用」那条钉住。
 *   （实测：强行 `removeAttribute('disabled')` 再点，antd 依然吞掉点击 ——
 *   所以这条也不适合靠 hack DOM 来测，测了就是测 antd 的内部实现。）
 * - **卸载**：`stopPolling` 会让在飞回调作废 ⇒ 由「卸载后旧回调不得再发请求」
 *   那条钉住。世代守卫机制本身在这里被覆盖。
 *
 * 两条入口共用同一个 `stopPolling`，所以世代守卫只需验一次。
 */
describe('ReportExecutePage — 旧轮询循环不得复活（评审 P1 #7）', () => {
  it('轮询期间执行按钮是禁用的（重跑的触发器本身就是它）', async () => {
    executionStatus.mockResolvedValue({
      task_id: 'task-1', def_id: 'd1', status: 'RUNNING', report_file_id: null,
    });
    await mountAndRun();
    await advance(POLL_INTERVAL + 10);
    expect(screen.getByRole('button', { name: /执行/ })).toBeDisabled();
  });

  it('卸载后旧回调不得再发请求', async () => {
    let releaseFirst!: (v: unknown) => void;
    const stuck = new Promise((res) => { releaseFirst = res; });
    executionStatus.mockReturnValueOnce(stuck);

    const { unmount } = renderPage();
    await flush();
    fireEvent.click(screen.getByRole('button', { name: /执行/ }));
    await flush();
    await advance(POLL_INTERVAL + 10);

    unmount();
    await act(async () => {
      releaseFirst({ task_id: 'task-1', def_id: 'd1', status: 'RUNNING', report_file_id: null });
      await stuck;
    });
    await advance(POLL_INTERVAL * 5);

    expect(executionStatus).toHaveBeenCalledTimes(1);   // 没有第二个循环被武装
  });
});
