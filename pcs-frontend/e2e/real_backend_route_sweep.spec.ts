import { test, expect, loginViaUi } from './fixtures';

/**
 * 真后端通道的**路由可达性扫描**（P10-B · T8 QA · 可重复跑的 QA 工具）。
 *
 * ⚠️ **不能用 `page.goto`** —— 本仓 zustand auth store 是**内存态**
 * ⇒ 整页刷新会清 session ⇒ `RequireAuth` 弹回 `/login` ⇒ 扫不出任何东西。
 * ⇒ ⇒ 用 **`history.pushState` + `popstate`**（react-router v6 的 history
 * 监听 popstate）⇒ ⇒ **不刷新页面** ⇒ 会话活着 ⇒ 路由切得过去。
 *
 * ## ⚠️ 三条断言（评审 #7）——「只断 `#root` 存在」是**确定空转**
 *
 * ① **页面标记**（`data-testid`）⇒ 证明切到的**是这一页**（不是上一页的残留）
 * ② **种子专有值** ⇒ 有种子的页面断**具体值**（比「非白屏」强得多）
 * ③ **控制台 error / 4xx-5xx** ⇒ **白名单之外必须为空**（白名单 = 已知缺口，
 *    逐条写「页面 + 端点 + TODO 号」⇒ 端点补齐后**删条目**）
 *
 * ⚠️ **身份 = `dan`（SYSTEM_ADMIN）** ⇒ admin 页不该 403
 * ⇒ ⇒ 白名单里**只有**「前端调了不存在端点」那几条已知缺口。
 */

/** 一条路由的期望（`testId` / `seedText` 至少给一个）。 */
type RouteCase = {
  path: string;
  /** 页面**自己的** `data-testid` ⇒ 断它 ⇒ 证明「切到了这一页」。 */
  testId?: string;
  /** 种子专有值 ⇒ 有就断它（比「非白屏」强得多）。 */
  seedText?: string;
};

/**
 * 44 条路由 ⇒ 各自的页面标记。
 *
 * ⚠️ **结果页共用一个 `result-list-page`**（用 `data-module` 区分模块）
 * ⇒ ⇒ 断 testid 即可（模块差异由那条 testid 自己的属性管）。
 */
const ROUTES: RouteCase[] = [
  { path: '/' },
  { path: '/config/asset-list', testId: 'config-asset-page' },
  { path: '/config/approval-panel', testId: 'approval-page' },
  { path: '/config/formula-editor', testId: 'formula-editor-page' },
  { path: '/config/template-file', testId: 'template-page' },
  { path: '/config/coefficient-editor', testId: 'coefficient-page' },
  { path: '/sim/streams', testId: 'stream-list-page', seedText: 'E2E-FLOW-S-001' },
  { path: '/sim/import', testId: 'import-wizard-page' },
  // ⚠️ **设备台账**（P10-C · T3 · TODO-157）⇒ ⇒ 断**种子设备的位号**
  //    （`132-P-101A/B` —— 与后端种子 `FLOW_EQUIPMENT_TAG` 逐字一致）
  //    ⇒ ⇒ 这条同时验了：真端点 + 项目作用域解析 + 页面渲染。
  { path: '/equipment-list', testId: 'equipment-list-page', seedText: '132-P-101A/B' },
  { path: '/pipe-class', testId: 'pipe-class-list-page' },
  { path: '/pipe-class/symbols', testId: 'symbol-table-page' },
  { path: '/pipe-class/code-format', testId: 'code-format-designer-page' },
  { path: '/common/properties', testId: 'property-search-page' },
  { path: '/common/stress', testId: 'allowable-stress-page' },
  { path: '/common/heating-value', testId: 'heating-value-page' },
  { path: '/common/toxicity', testId: 'toxicity-explosivity-page' },
  { path: '/flash', testId: 'flash-compute-page' },
  { path: '/pipe', testId: 'pipe-compute-page' },
  { path: '/pipe/line-list', testId: 'pipe-line-list-page' },
  { path: '/pipe-net', testId: 'pipe-net-topology-page' },
  { path: '/pump', testId: 'pump-compute-page' },
  { path: '/vessel', testId: 'vessel-compute-page' },
  { path: '/sep-equip', testId: 'sep-equip-compute-page' },
  { path: '/psv', testId: 'psv-compute-page' },
  { path: '/psv/standard-profile', testId: 'psv-standard-profile-page' },
  { path: '/heat', testId: 'heat-compute-page' },
  { path: '/report/definitions' },
  { path: '/report/styles' },
  { path: '/cv', testId: 'cv-compute-page' },
  { path: '/psychro/saturation-water-content', testId: 'saturation-w-page' },
  { path: '/util/cooling-water' },
  { path: '/util/energy-summary' },
  { path: '/audit/logs' },
  { path: '/admin/users', testId: 'user-admin-page' },
  { path: '/admin/projects', testId: 'project-admin-page' },
  { path: '/admin/system-settings', testId: 'system-settings-page' },
  { path: '/results/cool-tower', testId: 'result-list-page' },
  { path: '/results/filtration', testId: 'result-list-page' },
  { path: '/results/flare', testId: 'result-list-page' },
  { path: '/results/open-channel', testId: 'result-list-page' },
  { path: '/results/psychro', testId: 'result-list-page' },
  { path: '/results/cost-est', testId: 'result-list-page' },
  {
    path: '/deliverables/progress',
    testId: 'deliverable-progress-page',
    seedText: 'E2E 流程级种子计算书',
  },
  {
    path: '/deliverables/signature-matrices',
    testId: 'signature-matrix-page',
    seedText: 'E2E_FLOWS_RECORD_3_LEVEL',
  },
  { path: '/pms', testId: 'pms-page' },
  { path: '/bedd', testId: 'bedd-page' },
  // ⚠️ **项目向导**（P10-K · W-14）—— 扫达即止 ⇒ ⇒ ⇒ **不做**专用 e2e
  //   ⇒ ⇒ ⇒ 理由：向导 happy path **每次跑都消耗一个 FORMAL 工作区**
  //   ⇒ ⇒ ⇒ ⇒（一个工作区只能挂一个项目 ⇒ ⇒ ⇒ 第二次跑必然 409）
  //   ⇒ ⇒ ⇒ ⇒ ⇒ 要幂等就得引入「每次跑新建一个工作区」⇒ ⇒ ⇒ ⇒
  //   ⇒ ⇒ ⇒ ⇒ ⇒ ⇒ 流程本身改由 **vitest** 覆盖（`tests/pages/wizard/`）
  //   ⇒ ⇒ ⇒ ⇒ ⇒ ⇒ 而 e2e 只验「**路由可达 + 页面渲染**」。
  { path: '/wizard', testId: 'project-wizard-page' },
];

/**
 * ⚠️ **白名单 = 已知的产品缺口**（不是「已知的正常」）——
 * 每条写「页面 + 端点（路径片段）+ TODO 号」⇒ 端点补齐后**删条目并加回断言**。
 *
 * ⚠️ **只列 4xx/5xx**（控制台错误另有一张表，见下）。
 *
 * ⚠️ **TODO-159 的三条已在 P10-C · T2 删掉**（2026-11-19）：
 * - `/pipe/line-list` ⇒ ⇒ 端点**补上了**（`GET /projects/{id}/pipe-line-list`
 *   ⇒ 数据源 = `piping_results`）⇒ ⇒ 前端改用**真** project id
 *   （走 `GET /workspaces` 解析）⇒ ⇒ 不再 404。
 * - `/pms` · `/bedd` ⇒ ⇒ 后端**确实没有**那两个实体 ⇒ ⇒ 前端**不发请求**，
 *   页面明说「数据源尚未接入」（占位页）⇒ ⇒ 不再 404。
 *
 * ⚠️ **TODO-160 的三条已在 P10-C · T1 删掉**（2026-11-19）——
 * 物性 / 许用应力 / 毒性三页改成「**填条件才查**」（契约的 `keyword` /
 * `material`+`temp_c` / `cas` 都必填 ⇒ 首屏发空查询必 422）
 * ⇒ ⇒ 首屏**零请求** ⇒ ⇒ 现在这三页**任何 4xx/5xx 都会红**。
 *
 * ⇒ ⇒ **白名单现在是空的** ⇒ ⇒ 本扫描里**任何** 4xx/5xx 都会红。
 */
const ALLOWED_BAD_RESPONSES: { page: string; pathFragment: string; todo: string }[] = [];

/** ⚠️ 控制台 error 的白名单（每条写「页面 + 文本片段 + TODO 号」）。 */
/**
 * ⚠️ **控制台 error 的白名单** —— 现在**是空的**。
 *
 * ⚠️ 原先有一条（TODO-162：公式编辑器的参数表用了 antd `rowKey` 回调的
 * **index** 参数 ⇒ antd 5.29 起**弃用告警**，控制台 error 级）
 * ⇒ ⇒ **已修**（P10-F · F2-T4）：`rowKey` 改成**只收一个参数**的回调
 * ⇒ ⇒ 行自带稳定 key ⇒ ⇒ 告警消失 ⇒ ⇒ **条目删除**（白名单外必须为空）。
 */
const ALLOWED_CONSOLE_ERRORS: { page: string; textFragment: string; todo: string }[] = [];

/** 命中的白名单条目（用于打印「哪些是已知缺口」）。 */
function matchAllowlist<T extends { page: string }>(
  entries: T[],
  page: string,
  matches: (entry: T) => boolean,
): T | undefined {
  return entries.find((entry) => entry.page === page && matches(entry));
}

test('@real-backend QA：路由可达性扫描', async ({ realPage }) => {
  test.setTimeout(240_000);
  const consoleErrors: string[] = [];
  const badResponses: string[] = [];
  let bucket = 'boot';
  // ⚠️ **按「请求发起时」的页面归属**（不是「响应到达时」）——
  // ⇒ 响应可能**晚于**切页才到 ⇒ 按到达时间归属 ⇒ 会被记到**下一页**头上
  // ⇒ ⇒ 白名单按「页面 + 端点」匹配就会**误判**（实测过）。
  realPage.on('request', (req) => {
    (req as unknown as { __bucket?: string }).__bucket = bucket;
  });
  realPage.on('console', (m) => {
    if (m.type() === 'error') consoleErrors.push(`[${bucket}] ${m.text()}`);
  });
  realPage.on('response', (r) => {
    if (r.status() >= 400) {
      const owner = (r.request() as unknown as { __bucket?: string }).__bucket ?? bucket;
      badResponses.push(`[${owner}] ${r.status()} ${r.url()}`);
    }
  });

  // ⚠️ **dan（SYSTEM_ADMIN）** ⇒ admin 页**不该** 403 ⇒
  // ⇒ 白名单里只剩「前端调了不存在端点」那几条已知缺口。
  await loginViaUi(realPage, 'dan');

  const results: { route: string; redirected: boolean }[] = [];
  for (const route of ROUTES) {
    bucket = route.path;
    await realPage.evaluate((r) => {
      window.history.pushState({}, '', r);
      window.dispatchEvent(new PopStateEvent('popstate'));
    }, route.path);

    const url = new URL(realPage.url());
    const redirected = url.pathname === '/login';
    results.push({ route: route.path, redirected });

    // ① 页面标记 ⇒ 证明切到的**是这一页**（不是上一页的残留）
    if (route.testId) {
      await expect(
        realPage.getByTestId(route.testId),
        `[${route.path}] 页面没渲染出来（testid=${route.testId}）`,
      ).toBeVisible({ timeout: 15_000 });
    }
    // ② 种子专有值 ⇒ 有就断它
    if (route.seedText) {
      await expect(
        realPage.getByText(route.seedText, { exact: false }).first(),
        `[${route.path}] 看不到种子专有值「${route.seedText}」`
          + ' ⇒ 查的不是被 seed 的那个库（或种子没灌进去）',
      ).toBeVisible({ timeout: 15_000 });
    }
    // ③ 没有专有值的页面 ⇒ 断「**非白屏**」（页面有文字，不是空的）
    if (!route.testId) {
      await expect
        .poll(
          async () => (await realPage.locator('#root').innerText()).trim().length,
          { timeout: 15_000, message: `[${route.path}] 页面是白屏（#root 没有文字）` },
        )
        .toBeGreaterThan(0);
    }

    // ⚠️ **等这一页的网络静下来** ⇒ 否则它的响应**落到下一页的桶里**
    // ⇒ ⇒ 白名单按「页面 + 端点」匹配就会**误判**（实测：/common/properties
    // ⇒ ⇒ 的 422 被记到 /common/stress 头上 ⇒ 白名单对不上 ⇒ 假红）。
    await realPage.waitForLoadState('networkidle', { timeout: 5000 }).catch(() => undefined);
  }

  console.log('ROUTES_JSON=' + JSON.stringify(results));
  console.log('CONSOLE_ERRORS=' + JSON.stringify(consoleErrors));
  console.log('BAD_RESPONSES=' + JSON.stringify(badResponses));

  // ⚠️ **没被弹回 /login**（session 还在）
  expect(
    results.filter((r) => r.redirected),
    '有路由被弹回 /login（session 丢了？）',
  ).toEqual([]);

  // ⚠️ **白名单外的 4xx/5xx 必须为空**（评审 #7）
  const unexpectedResponses = badResponses.filter((entry) => {
    const page = entry.slice(1, entry.indexOf(']'));
    return !matchAllowlist(
      ALLOWED_BAD_RESPONSES,
      page,
      (allow) => entry.includes(allow.pathFragment),
    );
  });
  expect(
    unexpectedResponses,
    '白名单外的 4xx/5xx（白名单 = 已知缺口，逐条带 TODO 号 ⇒ 端点补齐后删条目）',
  ).toEqual([]);

  // ⚠️ **白名单外的控制台 error 必须为空**（评审 #7）
  // ⚠️ **「Failed to load resource」由上面那条 4xx 断言覆盖** ⇒ 这里滤掉
  // ⇒ ⇒ 免得同一个缺陷在两处各判一次（且控制台那条**没有端点**可匹配）。
  const unexpectedConsole = consoleErrors.filter((entry) => {
    if (entry.includes('Failed to load resource')) return false;
    const page = entry.slice(1, entry.indexOf(']'));
    return !matchAllowlist(
      ALLOWED_CONSOLE_ERRORS,
      page,
      (allow) => entry.includes(allow.textFragment),
    );
  });
  expect(unexpectedConsole, '白名单外的控制台 error').toEqual([]);
});
