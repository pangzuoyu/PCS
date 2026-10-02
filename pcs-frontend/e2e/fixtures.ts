/**
 * Playwright e2e fixtures (F-P2-009 Sprint 3 / Issue 7).
 *
 * 共享 loggedInPage fixture — 复用 cooling_water/energy_summary.spec.ts 的 4-step auth dance.
 * 现有 2 specs 重构为用 loggedInPage (DRY).
 *
 * 用法:
 *   import { test, expect } from './fixtures';
 *   test('...', async ({ loggedInPage: page }) => { ... });
 */
import { test as base, expect } from '@playwright/test';
import type { Page } from '@playwright/test';

export const test = base.extend<{ loggedInPage: Page }>({
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
});

export { expect };