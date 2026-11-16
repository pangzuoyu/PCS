import { test, expect, gotoViaMenu } from './fixtures';
import type { Page } from '@playwright/test';

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
 */
const FLOW_PROJECT_ID = '2488b011-14fc-584b-966e-1e2dfaeb9eb7';

/** 种子物流名（`scripts/seed_e2e_flows.py::FLOW_STREAM_NAMES`）。 */
const STREAM_NAME = 'E2E-FLOW-S-001';

/** 种子交付物标题（`_ensure_deliverable`）。 */
const DELIVERABLE_TITLE = 'E2E 流程级种子计算书';

/** 种子签署矩阵名（`_ensure_matrix`）。 */
const MATRIX_NAME = 'DEFAULT_RECORD_3_LEVEL';

/**
 * 走 UI 登录。
 *
 * ⚠️ **账号选择器**（`LoginPage` 的 antd `Select`）⇒ 选人再点「登 录」。
 * ⚠️ 按钮的可访问名是 **「登 录」**（antd 给两个汉字的按钮插空格）。
 */
async function loginViaUi(page: Page, mockUser: 'alice' | 'bob' = 'alice'): Promise<string> {
  await page.goto('/login');
  if (mockUser !== 'alice') {
    // ⚠️ **用键盘展开下拉，不要点 `role=combobox` 的 input** ——
    // antd 的 combobox input 被已选项的 span 盖住 ⇒ 点它 ⇒
    // 「intercepts pointer events」⇒ 永远点不动；
    // 而点 `.ant-select-selector` / `.ant-select` 也不稳（选项在动画里
    // 「not stable / not visible」）⇒ ⇒ 点已选项的 title 最稳。
    await page.getByTitle('alice (DESIGNER)').click();
    // ⚠️ **别用 `getByRole('option')`** —— antd/rc-select 给无障碍留了一份
    // `role="option"` 的**隐藏副本**（宽 0）⇒ Playwright 判它「不可见」
    // ⇒ ⇒ 永远等不到 ⇒ ⇒ 用**可见的选项项**（`.ant-select-item-option`）。
    // ⚠️ 下拉是**动画**展开的 ⇒ 选项此刻还没稳定 ⇒ 先等它可见。
    const option = page.locator('.ant-select-item-option', { hasText: mockUser });
    await option.waitFor({ state: 'visible' });
    await option.click();
  }
  const [loginResponse] = await Promise.all([
    page.waitForResponse(
      (res) => res.url().includes('mock-login') && res.status() === 200,
      { timeout: 15000 },
    ),
    page.getByRole('button', { name: '登 录' }).click(),
  ]);
  expect(loginResponse.status(), 'mock 登录失败 ⇒ 通道没通').toBe(200);
  await page.waitForURL('/', { timeout: 15000 });
  const { access_token: accessToken } = await loginResponse.json();
  return accessToken;
}

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

test('@real-backend 权限：越权用户看不到别人的项目', async ({ realPage }) => {
  // ⚠️ `bob` **故意没有** flows 项目的授权行（种子里的「局外人」）
  const token = await loginViaUi(realPage, 'bob');

  // ⚠️ **断「同形」，不是断某个具体码** —— 「空表」有**两种**来源：
  //   ① 跨项目（没授权行）· ② 有授权但角色不够
  // ⇒ ⇒ 「存在但没授权」与「压根不存在」必须**同形**（同状态码）
  //    ⇒ 否则枚举得出别人的项目 id ⇒ ⇒ 这才是要断的那件事。
  // ⚠️ **具体码取决于闸门顺序**（物流列表端点先过**角色闸** ⇒ CHECKER ⇒ 403）
  // ⇒ ⇒ 断「两个码相等」⇒ 既不钉死实现细节，又抓住「泄露存在性」。
  const auth = { headers: { Authorization: `Bearer ${token}` } };
  const unauthorized = await realPage.request.get(
    `/api/v1/projects/${FLOW_PROJECT_ID}/streams`,
    auth,
  );
  const nonexistent = await realPage.request.get(
    `/api/v1/projects/99999999-9999-9999-9999-999999999999/streams`,
    auth,
  );
  expect(
    unauthorized.status(),
    `跨项目(${unauthorized.status()}) 与 真不存在(${nonexistent.status()}) 不同形`
      + ' ⇒ 泄露了别人的项目存在性',
  ).toBe(nonexistent.status());

  await gotoViaMenu(realPage, '物流一览');
  await expect(realPage.getByTestId('stream-list-page')).toBeVisible();
  await expect(realPage.getByTestId('stream-name')).toHaveCount(0);
  await expect(realPage.getByText(STREAM_NAME, { exact: false })).toHaveCount(0);
});
