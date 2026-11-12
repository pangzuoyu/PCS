import { defineConfig, devices } from '@playwright/test';

/**
 * Playwright E2E 配置 (P7-6B frontend / R1 §7 闭环).
 *
 * 用 MSW (vitest 阶段已加 MSW handler) + Playwright dev mode 联动:
 * - 跑 vite dev server (`npm run dev`) 同时跑 Playwright
 * - MSW handler 在浏览器层拦截 /api/v1/* 调用 (setupWorker from mocks/browser.ts)
 *
 * ## 两个项目（通道）
 *
 * - `chromium` —— 默认通道，跑在 **MSW mock** 上（vite dev 挂了 MSW worker）。
 * - `real-backend` —— **真后端**通道：`VITE_ENABLE_MOCK=false` ⇒ **不挂 MSW**
 *   ⇒ 请求打到真后端 ⇒ 需要「后端 + 库 + 种子数据」在跑。
 *
 * ⚠️ **真后端通道用独立端口 5174**（不是 5173）：
 * `webServer.reuseExistingServer` 会**复用已在跑的 dev server** ⇒ 若那个
 * server 是带 MSW 起的，请求会被 mock 拦截 ⇒ 症状是「登录失败」，
 * 而真因是「复用了一个 MSW 开的 server」。
 * ⇒ 真后端通道**固定新起一个**（`reuseExistingServer: false`）+ 关 MSW。
 *
 * ⚠️ `grep` 匹配**测试标题** ⇒ 标题里必须有 `@real-backend`
 *    （或用 `test('…', { tag: '@real-backend' })`）⇒ 否则收集到 0 个测试
 *    （看起来「全绿」实则什么都没跑）。
 *
 * 跑法：
 *   VITE_ENABLE_MOCK=false VITE_API_PROXY_TARGET=http://localhost:8001 \
 *     npx playwright test --project=real-backend
 */
const realBackend = process.env.VITE_ENABLE_MOCK === 'false';
const port = realBackend ? 5174 : 5173;
const baseURL = `http://localhost:${port}`;

export default defineConfig({
  testDir: './e2e',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: 'list',
  use: {
    baseURL,
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'], baseURL },
    },
    {
      name: 'real-backend',
      use: { ...devices['Desktop Chrome'], baseURL },
      grep: /@real-backend/,
    },
  ],
  webServer: {
    // ⚠️ 真后端通道**显式**写 `VITE_ENABLE_MOCK=false`（不靠继承环境变量）
    // ⇒ 「只跑 --project=real-backend」也不会误用带 MSW 的 server。
    command: realBackend
      ? 'VITE_ENABLE_MOCK=false npm run dev -- --port 5174'
      : 'npm run dev -- --port 5173',
    url: baseURL,
    // ⚠️ 真后端通道**不复用**已在跑的 server（理由见上）。
    reuseExistingServer: realBackend ? false : !process.env.CI,
    timeout: 120_000,
  },
});
