/**
 * 通用结果页 + 编辑抽屉的守卫（P9B-1 Task T3 · SPEC §6.21）。
 *
 * ## 这组测试钉住的是「**静默失效**」型失败模式
 *
 * | # | 失败模式 | 症状 |
 * |---|---|---|
 * | RF-1 | 保存后不刷新基线 | 第二次保存**必 409**（假冲突） |
 * | RF-2 | 请求体漏 `expected_hash` | 「保存总是失败」，**不指向漏传** |
 * | RF-7 | 锁定态仍显示可编辑 | 用户进了编辑态才发现不能改 |
 * | RF-10 | 抽屉关闭白占锁 30min | 同事看到「张三 正在编辑」而张三 已走 |
 * | RF-12 | 禁用原因不分类 | 用户以为是自己没权限（其实是没基线） |
 * | RF-13 | 基线字段名漂成 camelCase | 编译绿、运行时**每次保存 409** |
 *
 * ⚠️ 断言**请求体**（不是 hook 返回值）—— RF-13 只有这样抓得到。
 */
import { describe, it, expect, vi, beforeAll, afterAll, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';

import { ResultListPage } from '../../../src/pages/results/ResultListPage';
import { moduleByRecordType } from '../../../src/pages/results/resultModules';
import { useAuth } from '../../../src/store/auth';
import type { components } from '../../../src/types/api';

type CoolTowerRow = components['schemas']['CoolTowerResultResponse'];

const MODULE = moduleByRecordType('cooling_tower_result');

const PROJECT_ID = '00000000-0000-0000-0000-000000000001';
const WORKSPACE_ID = '00000000-0000-0000-0000-000000000002';
const CURRENT_HASH = 'a3f9c21d8b7e6f50';
const NEW_HASH = 'ffffffffffffffff';
const RAW_UPDATED_AT = '2026-10-20T10:22:31.123456+08:00';

function row(overrides: Partial<CoolTowerRow> & { id: string }): CoolTowerRow {
  return {
    project_id: PROJECT_ID,
    workspace_id: WORKSPACE_ID,
    tag_number: 'CT-001',
    standard_profile_code: 'GB-500',
    calc_type: 'EVAPORATIVE',
    sign_status: 'DRAFT',
    tower_type: 'COUNTERFLOW',
    duty_kw: 100,
    water_flow_m3h: 50,
    makeup_water_m3h: 1,
    fan_power_kw: 5,
    merkel_integral: 0.5,
    data_sheet_json: null,
    input_json: null,
    output_json: null,
    created_at: '2026-10-20T10:22:31Z',
    updated_at: RAW_UPDATED_AT,
    record_hash: CURRENT_HASH,
    ...overrides,
  };
}

const ROW_DRAFT = row({ id: '11111111-1111-1111-1111-111111111111', tag_number: 'CT-DRAFT' });
const ROW_CHECKED = row({
  id: '22222222-2222-2222-2222-222222222222',
  tag_number: 'CT-CHECKED',
  sign_status: 'CHECKED',
});
/** ⚠️ 两档皆无（hash 空 + 无 updated_at）⇒ 后端永远 409 ⇒ 前端必须提前禁用。 */
const ROW_NO_BASELINE = row({
  id: '33333333-3333-3333-3333-333333333333',
  tag_number: 'CT-NOBASE',
  record_hash: null,
  updated_at: null,
});
const ROW_LOCKED = row({ id: '44444444-4444-4444-4444-444444444444', tag_number: 'CT-LOCKED' });
const ROW_CONFLICT_HASH = row({
  id: '55555555-5555-5555-5555-555555555555',
  tag_number: 'CT-CONFLICT-HASH',
});
const ROW_CONFLICT_UPDATED = row({
  id: '66666666-6666-6666-6666-666666666666',
  tag_number: 'CT-CONFLICT-UPD',
});
const ROW_CONFLICT_NO_BASELINE = row({
  id: '77777777-7777-7777-7777-777777777777',
  tag_number: 'CT-CONFLICT-NOBASE',
});

/**
 * ⚠️ **可变的行集合**：多数用例只需要 4 行；冲突用例各只要 1 行。
 *
 * 原因：antd Table + Drawer 在 **jsdom** 里的渲染/卸载**随行数线性变慢**
 * （实测 7 行时关抽屉要 4.2s、4 行 2.8s、1 行 1.9s —— 这是 jsdom + rc-motion
 * 的**测试环境**开销，不是产品缺陷：真浏览器里走 CSS 过渡，不阻塞交互）。
 * ⇒ 行数越少，单测越快 ⇒ 用例按需取行。
 */
let ROWS: CoolTowerRow[] = [ROW_DRAFT, ROW_CHECKED, ROW_NO_BASELINE, ROW_LOCKED];

/** 另一个模块的行（主键名是 `result_id`）—— 用于跨模块切换的守卫。 */
const ROW_FILTER = {
  ...ROW_DRAFT,
  id: undefined,
  result_id: '33333333-3333-3333-3333-333333333333',
  tag_number: 'F-001',
} as unknown as CoolTowerRow & { result_id: string };

let lastBody: Record<string, unknown> | null = null;
let releaseCalls = 0;
let acquireCalls = 0;
let lockBlocked = false;

function conflictEnvelope(basis: 'record_hash' | 'updated_at' | 'no_baseline') {
  return {
    code: 'RECORD_EDIT_CONFLICT',
    message: '该记录无法安全保存，请刷新后重新编辑',
    detail: {
      conflict: {
        record_type: 'cooling_tower_result',
        record_id: 'r1',
        your_expected_hash: CURRENT_HASH,
        current_hash: NEW_HASH,
        changed_by: '李四',
        changed_at: '2026-10-20T11:00:00Z',
        basis,
      },
    },
    trace_id: 'trace-1',
  };
}

const server = setupServer(
  http.get('/api/v1/cool-tower/results', () =>
    HttpResponse.json({ items: ROWS, total: ROWS.length, offset: 0, limit: 50 }),
  ),
  // 另一个模块的列表端点（主键名 `result_id`）—— 跨模块切换的守卫用
  http.get('/api/v1/filtration/results', () =>
    HttpResponse.json({ items: ROWS, total: ROWS.length, skip: 0, limit: 50 }),
  ),
  // ⚠️ **详情**端点（`recordsApi.get`）—— 409 后的「放弃并刷新」用它取服务端新值。
  // 此刻**没有**它 ⇒ `onUnhandledRequest: 'error'` 会让刷新静默失败
  // （抽屉的 catch 吞掉）⇒ 列表的 hash 永远不更新（Important ② 的根因之一）。
  http.get('/api/v1/cool-tower/results/:id', ({ params }) => {
    const found = ROWS.find((r) => r.id === params.id);
    if (!found) return HttpResponse.json({ detail: 'not found' }, { status: 404 });
    // 服务端此刻的哈希（与 PATCH 成功后的响应一致）
    return HttpResponse.json({ ...found, record_hash: NEW_HASH });
  }),
  http.patch('/api/v1/cool-tower/results/:id', async ({ request, params }) => {
    lastBody = (await request.json()) as Record<string, unknown>;
    if (params.id === ROW_CONFLICT_HASH.id) {
      return HttpResponse.json(conflictEnvelope('record_hash'), { status: 409 });
    }
    if (params.id === ROW_CONFLICT_UPDATED.id) {
      return HttpResponse.json(conflictEnvelope('updated_at'), { status: 409 });
    }
    if (params.id === ROW_CONFLICT_NO_BASELINE.id) {
      return HttpResponse.json(conflictEnvelope('no_baseline'), { status: 409 });
    }
    return HttpResponse.json({ ...ROW_DRAFT, record_hash: NEW_HASH });
  }),
  http.post('/api/v1/locks/:recordType/:recordId/:op', ({ params }) => {
    if (params.op === 'release') releaseCalls += 1;
    if (params.op === 'acquire') acquireCalls += 1;
    if (params.op === 'acquire' && (lockBlocked || params.recordId === ROW_LOCKED.id)) {
      return HttpResponse.json(
        {
          record_type: 'cooling_tower_result',
          record_id: params.recordId,
          operation: 'acquire',
          success: false,
          holder: {
            user_id: '99999999-8888-7777-6666-555555555555',
            acquired_at: '2026-10-20T10:22:31+08:00',
            username: '张三',
          },
          ttl_seconds: 1800,
          degraded: false,
          message: null,
        },
        { status: 409 },
      );
    }
    return HttpResponse.json({
      record_type: 'cooling_tower_result',
      record_id: params.recordId,
      operation: params.op,
      success: true,
      holder: {
        user_id: 'me',
        acquired_at: '2026-10-20T10:22:31+08:00',
        username: '我',
      },
      ttl_seconds: 1800,
      degraded: false,
      message: null,
    });
  }),
);

/** 打开第 n 行的编辑抽屉（行序 = ROWS 序）。 */
async function openEditor(index: number): Promise<void> {
  render(<ResultListPage module={MODULE} />);
  await waitFor(() => expect(screen.getAllByTestId('result-edit-button').length).toBe(ROWS.length));
  fireEvent.click(screen.getAllByTestId('result-edit-button')[index]);
  await waitFor(() => expect(screen.getByTestId('result-edit-drawer')).toBeTruthy());
}

/**
 * ⚠️ **超时提到 20s**：antd Drawer / Table 在 **jsdom** 里的挂载与卸载
 * 随行数线性变慢（实测关一次抽屉 1.9~4.2s）⇒ 这是**测试环境**开销
 * （真浏览器走 CSS 过渡，不阻塞交互）⇒ 不该让单测因此假红。
 */
const SLOW_TIMEOUT = 20_000;

describe('ResultListPage —— 列表渲染与编辑入口', () => {
  beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
  afterAll(() => server.close());
  beforeEach(() => {
    lastBody = null;
    releaseCalls = 0;
    acquireCalls = 0;
    lockBlocked = false;
    ROWS = [ROW_DRAFT, ROW_CHECKED, ROW_NO_BASELINE, ROW_LOCKED];
  });

  it('列表渲染：位号 + record_hash + 状态徽章', async () => {
    render(<ResultListPage module={MODULE} />);
    await waitFor(() => expect(screen.getByText('CT-DRAFT')).toBeTruthy());
    // ⚠️ antd Table 会渲染一个隐藏的 measure row ⇒ 表头文本出现**两次**
    expect(screen.getAllByText('位号').length).toBeGreaterThan(0);
    expect(screen.getAllByText('记录哈希').length).toBeGreaterThan(0);
    expect(screen.getAllByText('状态').length).toBeGreaterThan(0);
  }, SLOW_TIMEOUT);

  it('⚠️ sign_status=CHECKED ⇒ 编辑按钮禁用（RF-7）', async () => {
    render(<ResultListPage module={MODULE} />);
    await waitFor(() => expect(screen.getAllByTestId('result-edit-button').length).toBe(ROWS.length));
    const buttons = screen.getAllByTestId('result-edit-button') as HTMLButtonElement[];
    expect(buttons[1].disabled).toBe(true); // CHECKED
    expect(buttons[0].disabled).toBe(false); // DRAFT
  }, SLOW_TIMEOUT);

  it('⚠️ 两档皆无 ⇒ 编辑按钮禁用 + Tooltip 说「联系管理员」（RF-12）', async () => {
    render(<ResultListPage module={MODULE} />);
    await waitFor(() => expect(screen.getAllByTestId('result-edit-button').length).toBe(ROWS.length));
    const buttons = screen.getAllByTestId('result-edit-button') as HTMLButtonElement[];
    expect(buttons[2].disabled).toBe(true); // 无基线

    // ⚠️ Tooltip 必须能弹出来（禁用按钮不派发鼠标事件 ⇒ 必须套 span）
    fireEvent.mouseEnter(buttons[2].parentElement as Element);
    await waitFor(() => expect(screen.getByText(/联系管理员/)).toBeTruthy());
  }, SLOW_TIMEOUT);

  it('⚠️ 状态锁定 ⇒ Tooltip 说「当前状态 X 不可编辑」（与「无基线」**可区分**，RF-12）', async () => {
    render(<ResultListPage module={MODULE} />);
    await waitFor(() => expect(screen.getAllByTestId('result-edit-button').length).toBe(ROWS.length));
    const buttons = screen.getAllByTestId('result-edit-button') as HTMLButtonElement[];
    expect(buttons[1].disabled).toBe(true); // CHECKED
    fireEvent.mouseEnter(buttons[1].parentElement as Element);
    await waitFor(() => expect(screen.getByText(/当前状态 CHECKED 不可编辑/)).toBeTruthy());
  }, SLOW_TIMEOUT);
});

describe('ResultEditDrawer —— 保存 / 基线 / 409', () => {
  beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
  afterAll(() => server.close());
  beforeEach(() => {
    lastBody = null;
    releaseCalls = 0;
    acquireCalls = 0;
    lockBlocked = false;
    ROWS = [ROW_DRAFT, ROW_CHECKED, ROW_NO_BASELINE, ROW_LOCKED];
  });

  it('⚠️ 打开编辑 ⇒ 请求体带 expected_hash（取自记录的 record_hash）（RF-2）', async () => {
    await openEditor(0);
    fireEvent.click(screen.getByTestId('result-save'));
    await waitFor(() => expect(lastBody).not.toBeNull());
    expect(lastBody!.expected_hash).toBe(CURRENT_HASH);
    // ⚠️ RF-13：字段名必须是 snake_case
    expect(lastBody!.expectedHash).toBeUndefined();
  }, SLOW_TIMEOUT);

  it('⚠️ 保存成功 ⇒ 基线刷新为**响应里的新 record_hash**（RF-1）', async () => {
    await openEditor(0);
    fireEvent.click(screen.getByTestId('result-save'));
    await waitFor(() => expect(lastBody!.expected_hash).toBe(CURRENT_HASH));

    // ⚠️ **必须等第一次保存「完成」**再点第二次：
    // antd 的 Button 在 loading 时不响应点击 ⇒ 请求还在飞时点第二下会被吞掉；
    // 而「请求已发出」≠「响应已落地、基线已刷新」⇒ 这里等**基线显示**。
    await waitFor(() =>
      expect(screen.getByTestId('result-baseline').textContent).toContain(NEW_HASH),
    );

    fireEvent.click(screen.getByTestId('result-save'));
    await waitFor(() => expect(lastBody!.expected_hash).toBe(NEW_HASH));
  }, SLOW_TIMEOUT);

  it('409（record_hash）⇒ 弹窗说「谁于何时改了这条记录」', async () => {
    ROWS = [ROW_CONFLICT_HASH];
    await openEditor(0);
    fireEvent.click(screen.getByTestId('result-save'));
    await waitFor(() => expect(screen.getByTestId('edit-conflict-modal')).toBeTruthy());
    const text = screen.getByTestId('edit-conflict-modal').textContent ?? '';
    expect(text).toContain('李四');
    expect(text).toContain('修改了这条记录');
  }, SLOW_TIMEOUT);

  it('409（no_baseline）⇒ **不得**显示「已被他人修改」（两者原因不同）', async () => {
    ROWS = [ROW_CONFLICT_NO_BASELINE];
    await openEditor(0);
    fireEvent.click(screen.getByTestId('result-save'));
    await waitFor(() => expect(screen.getByTestId('edit-conflict-modal')).toBeTruthy());
    const text = screen.getByTestId('edit-conflict-modal').textContent ?? '';
    expect(text).toContain('基线');
    expect(text).not.toContain('修改了这条记录');
  }, SLOW_TIMEOUT);

  it('⚠️ 他人持锁 ⇒ **只禁保存**，浏览 / 复制 / 查看哈希仍可用（RF-3）', async () => {
    ROWS = [ROW_LOCKED];
    await openEditor(0); // ROW_LOCKED
    await waitFor(() => expect(screen.getByTestId('edit-lock-indicator')).toBeTruthy());
    expect(screen.getByTestId('edit-lock-indicator').textContent).toContain('张三');
    // 保存被禁
    expect((screen.getByTestId('result-save') as HTMLButtonElement).disabled).toBe(true);
    // ⚠️ 但抽屉还在、表单字段还在（浏览不被阻断）
    expect(screen.getByTestId('field-duty_kw')).toBeTruthy();
  }, SLOW_TIMEOUT);
});

describe('ResultEditDrawer —— 关闭与释放锁（RF-10）', () => {
  beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
  afterAll(() => server.close());
  beforeEach(() => {
    lastBody = null;
    releaseCalls = 0;
    acquireCalls = 0;
    lockBlocked = false;
    ROWS = [ROW_DRAFT, ROW_CHECKED, ROW_NO_BASELINE, ROW_LOCKED];
  });

  it('抽屉关闭 ⇒ 调 release', async () => {
    await openEditor(0);
    fireEvent.click(screen.getByRole('button', { name: /关\s*闭/ }));
    await waitFor(() => expect(releaseCalls).toBeGreaterThan(0));
  }, SLOW_TIMEOUT);

  it('有未保存修改时关闭 ⇒ 弹确认；取消 ⇒ 抽屉保持打开', async () => {
    await openEditor(0);
    fireEvent.change(screen.getByTestId('field-duty_kw'), { target: { value: '123' } });
    fireEvent.click(screen.getByRole('button', { name: /关\s*闭/ }));

    await waitFor(() => expect(screen.getByText('有未保存的修改')).toBeTruthy());
    fireEvent.click(screen.getByRole('button', { name: /继续编辑/ }));
    // 取消 ⇒ 抽屉保持打开
    await waitFor(() => expect(screen.getByTestId('result-edit-drawer')).toBeTruthy());
  }, SLOW_TIMEOUT);

  it('⚠️ 页面卸载 ⇒ 用 keepalive fetch 发 release（**不是** sendBeacon）', async () => {
    // ⚠️ 释放请求要带 Authorization 头 ⇒ 必须先有 token（否则 handler 直接 return）
    useAuth.setState({ accessToken: 'test-token' });
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response('{}'));
    try {
      await openEditor(0);
      window.dispatchEvent(new Event('pagehide'));

      await waitFor(() => expect(fetchSpy).toHaveBeenCalled());
      const [url, init] = fetchSpy.mock.calls[0] as [string, RequestInit];
      expect(String(url)).toContain('/api/v1/locks/cooling_tower_result/');
      expect(String(url)).toContain('/release');
      // ⚠️ sendBeacon **带不了** Authorization 头 ⇒ 必然 401 ⇒ 不能用
      expect(init.keepalive).toBe(true);
      expect((init.headers as Record<string, string>).Authorization).toContain('Bearer');
    } finally {
      fetchSpy.mockRestore();
    }
  }, SLOW_TIMEOUT);
});


/**
 * 跨模块切换的守卫（P9B-1 · 浏览器 QA 实测发现的 bug）。
 *
 * ## 症状
 *
 * 从「冷却塔结果」切到「过滤结果」⇒ 表格里**留着冷却塔的行**，
 * 且它们的 `data-row-key` 是 **undefined** ⇒ React 报
 * 「two children with the same key」**18 次**（一排 undefined 主键）。
 *
 * ## 根因
 *
 * React Router **复用同类型的组件实例** ⇒ `records` state 留着上一页的行；
 * 而新模块的 `module.pk`（主键名）不同（`id` vs `result_id`）⇒
 * 旧行取不到主键 ⇒ undefined ⇒ 重复 key。
 *
 * ⇒ 修法：`routeWrappers` 里给 `<ResultListPage key={module} …>`（换模块 =
 * 整页重建）+ 页面在换模块时先清空 + `rowKey` 兜底。
 */
describe('ResultListPage —— 跨模块切换', () => {
  beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
  afterAll(() => server.close());
  beforeEach(() => {
    lastBody = null;
    releaseCalls = 0;
    acquireCalls = 0;
    lockBlocked = false;
    ROWS = [ROW_DRAFT, ROW_CHECKED, ROW_NO_BASELINE, ROW_LOCKED];
  });

  it('换模块 ⇒ 不残留上一模块的行、且不产生重复 React key', async () => {
    const keyErrors: string[] = [];
    const spy = vi.spyOn(console, 'error').mockImplementation((...args: unknown[]) => {
      keyErrors.push(String(args[0]));
    });
    try {
      const { rerender } = render(
        <ResultListPage module={moduleByRecordType('cooling_tower_result')} />,
      );
      await waitFor(() =>
        expect(screen.getAllByTestId('result-edit-button').length).toBe(ROWS.length),
      );

      // 切到另一个模块（主键名不同：id → result_id）
      ROWS = [ROW_FILTER];
      rerender(<ResultListPage module={moduleByRecordType('FiltrationResult')} />);

      await waitFor(() =>
        expect(screen.getAllByTestId('result-edit-button').length).toBe(1),
      );
      // ⚠️ 表格里**只有**新模块的行（旧的冷却塔行不得残留）
      const rowKeys = Array.from(document.querySelectorAll('tbody tr[data-row-key]')).map(
        (el) => el.getAttribute('data-row-key'),
      );
      expect(rowKeys).toEqual([ROW_FILTER.result_id]);
      // ⚠️ 一个重复 key 都不能有
      expect(keyErrors.filter((e) => e.includes('same key'))).toEqual([]);
    } finally {
      spy.mockRestore();
    }
  }, SLOW_TIMEOUT);
});

/**
 * **最终评审（2026-10-21）抓到的 Critical + 两条 Important**。
 *
 * ## Critical：抽屉里的输入框**显示的不是抽屉的值**
 *
 * `Form.Item` 带 `name={field.key}` ⇒ antd/rc-field-form 会用**表单 store 的值**
 * 覆盖子元素自己的 `value` prop（`rc-field-form/lib/Field.js`：
 * `valueProps = { value: storeValue }`；`antd/lib/form/FormItem`：
 * `childProps = { ...mergedChildren.props, ...mergedControl }`）。
 *
 * 而抽屉**从不**调 `form.setFieldsValue(...)`（没有 form 实例、没有
 * `initialValues`）⇒ store 是空的 ⇒ `storeValue === undefined`
 * ⇒ **每个可编辑输入框都渲染成空白**，哪怕记录里有值。
 *
 * ⚠️ **为什么浏览器 QA 没抓到**：QA 断言的是**请求体**
 * （`{"tower_type":"COUNTERFLOW","duty_kw":123,…}`）—— 而 antd 仍会把
 * `onChange` 串起来 ⇒ 手工改过的值能进请求体 ⇒ **体对、界面空**。
 * ⇒ 断言必须落在**渲染出来的值**上。
 */
describe('ResultEditDrawer —— 输入框显示记录里的值（最终评审 Critical）', () => {
  beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
  afterAll(() => server.close());
  beforeEach(() => {
    lastBody = null;
    releaseCalls = 0;
    acquireCalls = 0;
    lockBlocked = false;
    ROWS = [ROW_DRAFT];
  });

  it('打开抽屉 ⇒ 每个可编辑字段显示记录里的值（不是空白）', async () => {
    await openEditor(0);
    await waitFor(() =>
      expect((screen.getByTestId('field-duty_kw') as HTMLInputElement).value).toBe('100'),
    );
    expect((screen.getByTestId('field-tower_type') as HTMLInputElement).value).toBe(
      'COUNTERFLOW',
    );
  }, SLOW_TIMEOUT);

  it('409 ⇒ [放弃我的修改并刷新] ⇒ 输入框回到**服务端**的值', async () => {
    ROWS = [ROW_CONFLICT_HASH];
    await openEditor(0);
    // 先改一个值（模拟用户输入）
    fireEvent.change(screen.getByTestId('field-duty_kw'), { target: { value: '123' } });
    fireEvent.click(screen.getByTestId('result-save'));
    await waitFor(() => expect(screen.getByTestId('edit-conflict-modal')).toBeTruthy());
    fireEvent.click(screen.getByTestId('conflict-refresh'));
    // 服务端返回的是 ROW_CONFLICT_HASH 原值 100（handler 见下）
    await waitFor(() =>
      expect((screen.getByTestId('field-duty_kw') as HTMLInputElement).value).toBe('100'),
    );
  }, SLOW_TIMEOUT);
});

/**
 * Important ②：409 刷新后**不把新 hash 交回列表** ⇒ 下一次编辑必 409（假冲突）。
 *
 * `discardAndRefresh` 只更新了抽屉内部的 `currentHash`，**没调** `onSaved`
 * ⇒ 列表里的 `record_hash` 还是冲突前那个 ⇒ 关闭抽屉再打开同一条 ⇒
 * 用旧基线保存 ⇒ 后端 409 `record_hash` —— 用户什么都没做错。
 */
describe('ResultListPage —— 409 刷新后列表的 hash 必须更新（Important ②）', () => {
  beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
  afterAll(() => server.close());
  beforeEach(() => {
    lastBody = null;
    releaseCalls = 0;
    acquireCalls = 0;
    lockBlocked = false;
    ROWS = [ROW_CONFLICT_HASH];
  });

  it('409 ⇒ [放弃我的修改并刷新] ⇒ 列表那一行的哈希变成服务端的新值', async () => {
    await openEditor(0);
    fireEvent.click(screen.getByTestId('result-save'));
    await waitFor(() => expect(screen.getByTestId('edit-conflict-modal')).toBeTruthy());
    fireEvent.click(screen.getByTestId('conflict-refresh'));
    // 列表单元格里的短哈希必须换成新值（ffff…ffff）
    await waitFor(() =>
      expect(screen.getByText(/ffff…ffff/)).toBeTruthy(),
    );
  }, SLOW_TIMEOUT);
});

/**
 * Important ③：**SPA 导航**（点菜单换页）会让抽屉所在页面静默卸载
 * ⇒ 只清了心跳定时器、**没释放锁** ⇒ 同事看到「张三 正在编辑」**30 分钟**。
 *
 * ⚠️ `pagehide` 只在**文档**卸载时触发 ⇒ 覆盖不到 SPA 路由切换。
 */
describe('ResultEditDrawer —— 页面卸载（SPA 导航）也要释放锁（Important ③）', () => {
  beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
  afterAll(() => server.close());
  beforeEach(() => {
    lastBody = null;
    releaseCalls = 0;
    acquireCalls = 0;
    lockBlocked = false;
    ROWS = [ROW_DRAFT];
  });

  it('组件卸载 ⇒ 调 release（不是只清心跳）', async () => {
    const { unmount } = render(<ResultListPage module={MODULE} />);
    await waitFor(() =>
      expect(screen.getAllByTestId('result-edit-button').length).toBe(ROWS.length),
    );
    fireEvent.click(screen.getAllByTestId('result-edit-button')[0]);
    await waitFor(() => expect(screen.getByTestId('result-edit-drawer')).toBeTruthy());
    // ⚠️ **必须等锁真的拿到**（acquire 的响应被客户端处理完）⇒ 否则卸载时
    // 还没持锁 ⇒ 无从释放（那正是「只在持锁时释放」这条守卫的用意）。
    await waitFor(() => expect(acquireCalls).toBeGreaterThan(0));
    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 10));
    });

    unmount();
    await waitFor(() => expect(releaseCalls).toBeGreaterThan(0));
  }, SLOW_TIMEOUT);
});
