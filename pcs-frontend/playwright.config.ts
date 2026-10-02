import { defineConfig, devices } from '@playwright/test';

/**
 * Playwright E2E 配置 (P7-6B frontend / R1 §7 闭环).
 *
 * 用 MSW (vitest 阶段已加 MSW handler) + Playwright dev mode 联动:
 * - 跑 vite dev server (`npm run dev`) 同时跑 Playwright
 * - MSW handler 在浏览器层拦截 /api/v1/* 调用 (setupWorker from mocks/browser.ts)
 * - 当前 batch 只跑 vitest; e2e/ 是 scafffold 阶段, 后续 sprint 激活
 *
 * 依赖: npx playwright install chromium (一次性 114MB 下载)
 */
export default defineConfig({
  testDir: './e2e',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: 'list',
  use: {
    baseURL: 'http://localhost:5173',
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
  webServer: {
    command: 'npm run dev',
    url: 'http://localhost:5173',
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
  },
});