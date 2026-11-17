import { test, expect, gotoViaMenu, loginViaUi } from './fixtures';
import { FLOW_PROJECT_ID } from './channel-config';

/**
 * 真后端通道的 **5 条 UI 流**（P10-B · Task T7）。
 *
 * ## ⚠️ 三条硬约束（不遵守就是假绿）
 *
 * 1. **导航必须走 SPA 菜单点击**（`gotoViaMenu`）——
 *    本仓 zustand auth store 是**内存态**（防 XSS，不落 localStorage）
 *    ⇒ 整页刷新会清 session ⇒ `RequireAuth` 弹回 `/login` ⇒ 表格永远没有行。
 * 2. **每个用例自己走 UI 登录** —— token 只在 zustand 内存里
 *    ⇒ 没有 `window` 上的注入点 ⇒ 只能点「登 录」。
 * 3. **断言具体行内容**，不是「页面没报错」——
 *    mock 登录**不落 users 表**、`/auth/me` 允许缺行、axios 只对 401 报错
 *    ⇒ 后端对所有项目级端点回 404 也**不会**产生控制台 error
 *    ⇒ 「页面渲染了」**证明不了**后端连的是被 seed 的那个库。
 *
 * ## ⚠️ 数据在哪个房间
 *
 * 后端 E2E 车道的数据在**隔离 schema**（自己的小房间）⇒
 * 真后端通道的后端连的是 **public schema**（大房间）⇒ **两个房间不通**
 * ⇒ ⇒ `scripts/seed_e2e_flows.py` **也**在 public 跑一遍
 * （compose 的 `seed` 服务已串上两个脚本 ⇒ 无手动步骤）。
 *
 * ## ⚠️ `PROJECT_ID` 是**前端常量**（`VITE_PROJECT_ID`）
 *
 * 物流/交付物/签署矩阵页都用 `constants/env.ts::PROJECT_ID` ⇒
 * ⇒ 真后端通道必须 `VITE_PROJECT_ID=<flows 项目 id>` 起 vite
 * ⇒ 否则页面查的是**另一个项目** ⇒ 空表 ⇒ 看着「页面正常」实则没数据。
 * ⇒ ⇒ `playwright.config.ts` 的 webServer env **默认**就是 flows 项目 id
 * （P10-B 评审 #23）⇒ 不用手工 export ⇒ ⇒ 也不会「忘了设」。
 */

/** 种子物流名（`scripts/seed_e2e_flows.py::FLOW_STREAM_NAMES`）。 */
const STREAM_NAME = 'E2E-FLOW-S-001';

/** 种子交付物标题（`_ensure_deliverable`）。 */
const DELIVERABLE_TITLE = 'E2E 流程级种子计算书';

/**
 * 种子签署矩阵名（`_ensure_matrix`）。
 *
 * ⚠️ **不是** `DEFAULT_RECORD_3_LEVEL` —— 那是迁移 `p9_013` 建的**全局内置**
 * 矩阵（**任何**迁移过的库都有）⇒ ⇒ 断它 ⇒ 「种子没灌进去 / matrix_name 漂了
 * / 项目绑定没生效」这条用例**照样绿** ⇒ ⇒ 断**种子那张**才有验证力。
 */
const MATRIX_NAME = 'E2E_FLOWS_RECORD_3_LEVEL';

/** **压根不存在**的项目 id（用来与「存在但无授权」比形状）。 */
const NONEXISTENT_PROJECT_ID = '99999999-9999-9999-9999-999999999999';

/**
 * 把消息里的项目 id **归一化** ⇒ 两个 404 的 **message 模板**才能逐字比。
 *
 * ⚠️ 后端的 404 消息是 `Project not found: <project_id>` ⇒ **带着 id**
 * ⇒ ⇒ 两个响应的消息**本该不同**（id 不同）⇒ ⇒ 比「模板」（归一化后）
 * ⇒ ⇒ 这才是「同形」的正确断法（不泄露存在性 = 连 id 都不该有差别之外的信息）。
 */
function normalizeProjectId(message: unknown, projectId: string): string {
  return String(message ?? '').replaceAll(projectId, '<PROJECT_ID>');
}

/**
 * 走 UI 登录。
 *
 * ⚠️ **实现在 `e2e/fixtures.ts::loginViaUi`** —— 路由扫描那条也要用
 * ⇒ ⇒ 一处真相源（antd 下拉那套坑只写一遍）。
 */

test('@real-backend 物流一览：种子物流行可见', async ({ realPage }) => {
  await loginViaUi(realPage);
  await gotoViaMenu(realPage, '物流一览');

  await expect(realPage.getByTestId('stream-list-page')).toBeVisible();
  // ⚠️ **具体行内容** —— 不是「页面渲染了」
  await expect(realPage.getByTestId('stream-name').filter({ hasText: STREAM_NAME })).toBeVisible();
});

test('@real-backend 物流详情：种子物流的标题与状态徽标可见', async ({ realPage }) => {
  await loginViaUi(realPage);
  await gotoViaMenu(realPage, '物流一览');

  const nameCell = realPage.getByTestId('stream-name').filter({ hasText: STREAM_NAME });
  await expect(nameCell).toBeVisible();
  await nameCell.click();

  await expect(realPage.getByTestId('stream-detail-page')).toBeVisible();
  await expect(realPage.getByRole('heading', { name: STREAM_NAME })).toBeVisible();
  // ⚠️ 种子的物流是 **CHECKED**（计算链的入口守卫要求 CHECKED）
  // ⇒ ⚠️ **徽标上写的是中文「已核验」**（`StateBadge` 的状态词表）
  // ⇒ ⇒ 断「已核验」而不是「CHECKED」⇒ 否则永远红
  await expect(realPage.getByTestId('stream-detail-page')).toContainText('已核验');
});

test('@real-backend 签署进度：种子交付物行可见', async ({ realPage }) => {
  await loginViaUi(realPage);
  await gotoViaMenu(realPage, '签署进度');

  await expect(realPage.getByTestId('deliverable-progress-page')).toBeVisible();
  // ⚠️ **具体行内容**（标题列）
  await expect(realPage.getByText(DELIVERABLE_TITLE, { exact: false })).toBeVisible();
});

test('@real-backend 签署矩阵：项目绑定的矩阵与三级链可见', async ({ realPage }) => {
  await loginViaUi(realPage);
  await gotoViaMenu(realPage, '签署矩阵');

  await expect(realPage.getByTestId('signature-matrix-page')).toBeVisible();
  await expect(realPage.getByText(MATRIX_NAME, { exact: false })).toBeVisible();
  // ⚠️ 矩阵链是 **CHECKER → REVIEWER → APPROVER**（种子写死的三级）
  await expect(realPage.getByTestId('signature-matrix-page')).toContainText('CHECKER');
  await expect(realPage.getByTestId('signature-matrix-page')).toContainText('REVIEWER');
  await expect(realPage.getByTestId('signature-matrix-page')).toContainText('APPROVER');
});

test('@real-backend 权限：角色够但无授权的用户看到的是「与不存在同形」的 404', async ({
  realPage,
}) => {
  // ⚠️ **身份 = 角色够、授权缺**（`erin` · P10-B 评审 #5）——
  //    ⇒ 请求**能过角色闸**（DESIGNER）⇒ ⇒ 真正落到**项目守卫**
  //    （`check_project_access_or_404`）⇒ ⇒ 断的**就是那条分支**。
  //
  // ⚠️ **为什么不能用 `bob`**（CHECKER）—— 物流列表端点先跑角色闸
  //    （`require_roles(user, "DESIGNER", "PROCESS_CONTROLLER", "SYSTEM_ADMIN")`）
  //    ⇒ bob **在项目守卫之前**就被 403 ⇒ ⇒ 两个请求都是**角色闸**给的 403
  //    ⇒ ⇒ 断言退化成 `403 === 403` ⇒ ⇒ **把项目守卫整段删掉也照样绿**
  //    ⇒ ⇒ 那条用例对它命名的缺陷**不敏感**（零覆盖）。
  const token = await loginViaUi(realPage, 'erin');

  const auth = { headers: { Authorization: `Bearer ${token}` } };
  const unauthorized = await realPage.request.get(
    `/api/v1/projects/${FLOW_PROJECT_ID}/streams`,
    auth,
  );
  const nonexistent = await realPage.request.get(
    `/api/v1/projects/${NONEXISTENT_PROJECT_ID}/streams`,
    auth,
  );

  // ⚠️ **存在但无授权 ⇒ 404**（不是 403 —— 403 会泄露存在性）
  expect(
    unauthorized.status(),
    `跨项目访问返回 ${unauthorized.status()}（应为 404）`
      + ' ⇒ 403 会泄露资源存在性',
  ).toBe(404);
  expect(
    unauthorized.status(),
    `跨项目(${unauthorized.status()}) 与 真不存在(${nonexistent.status()}) 不同形`
      + ' ⇒ 泄露了别人的项目存在性',
  ).toBe(nonexistent.status());

  // ⚠️ **code 逐字相同 + message 模板逐字相同** —— 只断状态码 ⇒
  //    「换个原因」也照样绿（hermes 断言形状病 #3）
  const unauthorizedBody = await unauthorized.json();
  const nonexistentBody = await nonexistent.json();
  expect(unauthorizedBody.code, '两个 404 的 code 不同形').toBe(nonexistentBody.code);
  expect(
    normalizeProjectId(unauthorizedBody.message, FLOW_PROJECT_ID),
    '两个 404 的 message 模板不同形 ⇒ 消息里泄露了项目存在性',
  ).toBe(normalizeProjectId(nonexistentBody.message, NONEXISTENT_PROJECT_ID));

  // UI：越权用户**看不到**种子物流（页面渲染了，但表格里没有那行）
  await gotoViaMenu(realPage, '物流一览');
  await expect(realPage.getByTestId('stream-list-page')).toBeVisible();
  await expect(realPage.getByText(STREAM_NAME, { exact: false })).toHaveCount(0);
});

// ---------------------------------------------------------------------------
// 仪表盘的守卫条件（P10-F · F2-T2 · 评审 #24）
// ---------------------------------------------------------------------------

/**
 * ⚠️ **身份必须是 `alice`** —— 工作区的 `owner_id` 是 alice 的**派生 id**
 * ⇒ ⇒ 前端**永远**带 `owner_id` 取列表 ⇒ ⇒ 别人的工作区**看不见**
 * ⇒ ⇒ 用 `dan` 会**连列表都空** ⇒ ⇒ 用 `dan` 测不出任何东西。
 */
const WORKSPACE_OWNER = 'alice';

/** 打开仪表盘上的工作区切换器并选中某个工作区（按文本片段）。 */
async function selectWorkspace(
  page: import('@playwright/test').Page,
  textFragment: string,
): Promise<void> {
  // ⚠️ antd 的 `role="option"` 是**隐藏副本** ⇒ 用可见的选项项
  await page.locator('[data-testid="workspace-switcher"] .ant-select-selector').click();
  const option = page.locator('.ant-select-item-option', { hasText: textFragment });
  await option.waitFor({ state: 'visible' });
  await option.click();
}

test('@real-backend 真后端：选「无项目的工作区」⇒ 清单面板不渲染且无 404 / 无 console error', async ({
  realPage,
}) => {
  const consoleErrors: string[] = [];
  const badResponses: string[] = [];
  realPage.on('console', (m) => {
    if (m.type() === 'error') consoleErrors.push(m.text());
  });
  realPage.on('response', (r) => {
    if (r.status() >= 400) badResponses.push(`${r.status()} ${r.url()}`);
  });

  await loginViaUi(realPage, WORKSPACE_OWNER);
  await selectWorkspace(realPage, '无项目');

  // ⇒ 面板**不渲染** ⇒ ⇒ 一个请求都不该发 ⇒ ⇒ 没有 404
  await expect(realPage.getByTestId('input-checklist-panel')).toHaveCount(0);
  expect(badResponses, '选无项目工作区不该有 4xx/5xx').toEqual([]);
  expect(
    consoleErrors.filter((t) => !t.includes('Failed to load resource')),
    '选无项目工作区不该有 console error',
  ).toEqual([]);
});

test('@real-backend 真后端：选有项目的工作区 ⇒ 面板渲染且请求带**真项目 id**', async ({
  realPage,
}) => {
  const checklistRequests: string[] = [];
  realPage.on('request', (req) => {
    if (req.url().includes('/checklist/projects/')) checklistRequests.push(req.url());
  });

  await loginViaUi(realPage, WORKSPACE_OWNER);
  await selectWorkspace(realPage, 'E2E Flows Workspace');

  await expect(realPage.getByTestId('input-checklist-panel')).toBeVisible();
  // ⚠️ **断「带的是真项目 id」** ⇒ 不是断「渲染了」那种烟测 ⇒ ⇒
  // ⇒ 也钉住「占位常量被当真值用」这个病根。
  expect(
    checklistRequests.some((u) => u.includes(FLOW_PROJECT_ID)),
    `清单请求没带真项目 id ${FLOW_PROJECT_ID}：${checklistRequests.join(' | ')}`,
  ).toBe(true);
});
