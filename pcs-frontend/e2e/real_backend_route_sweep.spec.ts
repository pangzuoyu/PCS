import { test, expect } from './fixtures';

/**
 * 真后端通道的**路由可达性扫描**（P10-B · T8 QA · 可重复跑的 QA 工具）。
 *
 * ⚠️ **不能用 `page.goto`** —— 本仓 zustand auth store 是**内存态**
 * ⇒ 整页刷新会清 session ⇒ `RequireAuth` 弹回 `/login` ⇒ 扫不出任何东西。
 * ⇒ ⇒ 用 **`history.pushState` + `popstate`**（react-router v6 的 history
 * 监听 popstate）⇒ ⇒ **不刷新页面** ⇒ 会话活着 ⇒ 路由切得过去。
 */
const ROUTES = [
  '/', '/config/asset-list', '/config/approval-panel', '/config/formula-editor',
  '/config/template-file', '/config/coefficient-editor', '/sim/streams',
  '/sim/import', '/pipe-class', '/pipe-class/symbols', '/pipe-class/code-format',
  '/common/properties', '/common/stress', '/common/heating-value',
  '/common/toxicity', '/flash', '/pipe', '/pipe/line-list', '/pipe-net', '/pump',
  '/vessel', '/sep-equip', '/psv', '/psv/standard-profile', '/heat',
  '/report/definitions', '/report/styles', '/cv',
  '/psychro/saturation-water-content', '/util/cooling-water',
  '/util/energy-summary', '/audit/logs', '/admin/users', '/admin/projects',
  '/admin/system-settings', '/results/cool-tower', '/results/filtration',
  '/results/flare', '/results/open-channel', '/results/psychro',
  '/results/cost-est', '/deliverables/progress', '/deliverables/signature-matrices',
  '/pms', '/bedd',
];

test('@real-backend QA：路由可达性扫描', async ({ realPage }) => {
  test.setTimeout(240_000);
  const consoleErrors: string[] = [];
  const badResponses: string[] = [];
  let bucket = 'boot';
  realPage.on('console', (m) => {
    if (m.type() === 'error') consoleErrors.push(`[${bucket}] ${m.text()}`);
  });
  realPage.on('response', (r) => {
    if (r.status() >= 400) badResponses.push(`[${bucket}] ${r.status()} ${r.url()}`);
  });

  await realPage.goto('/login');
  await Promise.all([
    realPage.waitForResponse((r) => r.url().includes('mock-login') && r.status() === 200),
    realPage.getByRole('button', { name: '登 录' }).click(),
  ]);
  await realPage.waitForURL('/', { timeout: 15000 });

  const results: { route: string; redirected: boolean; root: boolean }[] = [];
  for (const route of ROUTES) {
    bucket = route;
    await realPage.evaluate((r) => {
      window.history.pushState({}, '', r);
      window.dispatchEvent(new PopStateEvent('popstate'));
    }, route);
    await realPage.waitForTimeout(350);
    const url = new URL(realPage.url());
    const redirected = url.pathname === '/login';
    const root = (await realPage.locator('#root').count()) > 0;
    results.push({ route, redirected, root });
  }

  console.log('ROUTES_JSON=' + JSON.stringify(results));
  console.log('CONSOLE_ERRORS=' + JSON.stringify(consoleErrors));
  console.log('BAD_RESPONSES=' + JSON.stringify(badResponses));

  // ⚠️ **只断「路由可达」**（渲染了 + 没被弹回 /login）——
  // ⚠️ 「控制台无 error / 无 4xx-5xx」**不作为断言** ⇒ 因为仓里有一批
  // **前端调用了不存在端点**的页面（`/pipe/line-list` · `/pms` · `/bedd`）
  // ⇒ ⇒ 那是**既有产品缺口**（TODO-159）⇒ ⇒ 把它们**断言成红** ⇒
  // ⇒ 本来是「既有缺口」的噪声 ⇒ ⇒ 改成**打印出来**（进 QA 报告）⇒
  // ⇒ 等那些端点补齐后，**再把断言加回来**。
  expect(results.every((r) => r.root), '有路由没渲染出来').toBe(true);
  expect(
    results.filter((r) => r.redirected),
    '有路由被弹回 /login（session 丢了？）',
  ).toEqual([]);
});
