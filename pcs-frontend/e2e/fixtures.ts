/**
 * Playwright e2e fixtures (F-P2-009 Sprint 3 / Issue 7).
 *
 * 共享 loggedInPage fixture — 复用 cooling_water/energy_summary.spec.ts 的 4-step auth dance.
 * 现有 specs 重构为用 loggedInPage (DRY).
 *
 * 用法:
 *   import { test, expect } from './fixtures';
 *   test('...', async ({ loggedInPage: page }) => { ... });
 *
 * ## P10-A 新增：`realPage`（真后端通道）
 *
 * `real-backend` 项目里 MSW **不挂**（`VITE_ENABLE_MOCK=false`）⇒ 请求打到
 * 真后端 ⇒ 拿到**真 token**。
 *
 * ⚠️ **登录必须走 UI**（`goto('/login')` → 点「登 录」）：
 * 本仓 zustand auth store 是**内存态**（防 XSS，不落 localStorage），
 * 且**没有**暴露到 `window` ⇒ 用 `page.evaluate` 把 token 塞进 store 这条路
 * **根本不存在** ⇒ 只能走 UI。
 *
 * ⚠️ **页面导航必须走 SPA 菜单点击**（`gotoViaMenu`）：整页刷新会清 session
 * ⇒ `RequireAuth` 弹回 `/login` ⇒ 表格永远没有行。
 */
import { test as base, expect } from '@playwright/test';
import type { Page } from '@playwright/test';

export const test = base.extend<{ loggedInPage: Page; realPage: Page }>({
  loggedInPage: async ({ page }, use) => {
    // mock-login via LoginPage (alice/DESIGNER 默认 mock)
    await page.goto('/login');
    // 等 MSW worker ready (避免 login POST 没拦截到)
    await page
      .waitForResponse(
        (res) =>
          res.url().includes('/api/v1/auth/mock-login') && res.status() === 200,
        { timeout: 10000 },
      )
      .catch(() => undefined); // 第一次请求可能命中网络, 跳过
    await page.getByRole('button', { name: '登 录' }).click();
    // 等 mock-login 响应 + 跳转
    await page.waitForURL('/', { timeout: 15000 });
    await use(page);
  },
  // ⚠️ 真后端通道的页面：**登录由各 spec 自己做**（走 UI，见上），
  //    这里只提供「没挂 MSW 的那个浏览器上下文」。
  realPage: async ({ page }, use) => {
    await use(page);
  },
});

/**
 * **真后端通道的 UI 登录** —— 选一个 mock 账号再点「登 录」⇒ 返回 access token。
 *
 * ⚠️ **账号选择器**（`LoginPage` 的 antd `Select`）⇒ 选人再点「登 录」。
 * ⚠️ 按钮的可访问名是 **「登 录」**（antd 给两个汉字的按钮插空格）。
 *
 * ⚠️ **用键盘展开下拉，不要点 `role=combobox` 的 input** ——
 * antd 的 combobox input 被已选项的 span 盖住 ⇒ 点它 ⇒
 * 「intercepts pointer events」⇒ 永远点不动；
 * 而点 `.ant-select-selector` / `.ant-select` 也不稳（选项在动画里
 * 「not stable / not visible」）⇒ ⇒ 点已选项的 title 最稳。
 * ⚠️ **别用 `getByRole('option')`** —— antd/rc-select 给无障碍留了一份
 * `role="option"` 的**隐藏副本**（宽 0）⇒ Playwright 判它「不可见」
 * ⇒ ⇒ 永远等不到 ⇒ ⇒ 用**可见的选项项**（`.ant-select-item-option`）。
 * ⚠️ 下拉是**动画**展开的 ⇒ 选项此刻还没稳定 ⇒ 先等它可见。
 */
export async function loginViaUi(
  page: Page,
  mockUser: 'alice' | 'bob' | 'carol' | 'dan' | 'erin' = 'alice',
): Promise<string> {
  await page.goto('/login');
  if (mockUser !== 'alice') {
    await page.getByTitle('alice (DESIGNER)').click();
    const option = page.locator('.ant-select-item-option', { hasText: mockUser });
    await option.waitFor({ state: 'visible' });
    await option.click();
  }
  const [loginResponse] = await Promise.all([
    page.waitForResponse(
      (res) => res.url().includes('mock-login') && res.status() === 200,
      // ⚠️ **30s**（不是 15s）—— vite **冷启动**（改了 config ⇒ 依赖重新优化）
      // ⇒ 首次页面加载可能十几秒 ⇒ ⇒ 15s 会让**整条通道**（并行 7 个 worker
      // ⇒ 同时超时）**假红** ⇒ ⇒ 冷启动那一次要留够余量。
      { timeout: 30000 },
    ),
    page.getByRole('button', { name: '登 录' }).click(),
  ]);
  expect(loginResponse.status(), 'mock 登录失败 ⇒ 通道没通').toBe(200);
  await page.waitForURL('/', { timeout: 15000 });
  const { access_token: accessToken } = await loginResponse.json();
  return accessToken;
}

/**
 * **SPA 菜单导航** —— 不用 `page.goto`。
 *
 * ⚠️ 本仓 zustand auth store 是**内存态**（防 XSS，不落 localStorage）⇒
 * 整页刷新会清 session ⇒ `RequireAuth` 弹回 `/login` ⇒ 表格永远没有行。
 */
export async function gotoViaMenu(page: Page, menuName: string): Promise<void> {
  await page.getByRole('menuitem', { name: menuName }).click();
}

export { expect };
