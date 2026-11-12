import { defineConfig, devices } from '@playwright/test';

/**
 * Playwright E2E 配置 (P7-6B frontend / R1 §7 闭环).
 *
 * 用 MSW (vitest 阶段已加 MSW handler) + Playwright dev mode 联动:
 * - 跑 vite dev server (`npm run dev`) 同时跑 Playwright
 * - MSW handler 在浏览器层拦截 /api/v1/* 调用 (setupWorker from mocks/browser.ts)
 *
 * ## 两个项目（通道）—— **通道由项目决定，不由 env 决定**
 *
 * - `chromium` —— 默认通道，跑在 **MSW mock** 上（5173）。
 * - `real-backend` —— **真后端**通道（5174）：那个 server 是**显式**用
 *   `VITE_ENABLE_MOCK=false` 起的 ⇒ **不挂 MSW** ⇒ 请求打到真后端
 *   ⇒ 需要「后端 + 库 + 种子数据」在跑。
 *
 * ⚠️⚠️ **为什么不能靠 env 开关**（2026-11-12 评审 H-3）：
 * 之前用 `process.env.VITE_ENABLE_MOCK === 'false'` 决定通道 ⇒
 * **与 `--project=real-backend` 无关** ⇒ `npx playwright test --project=real-backend`
 * （**不带** env）⇒ 起的是带 MSW 的 server ⇒ 「真后端」用例**打到 MSW**
 * ⇒ **假绿**（看着通过，实则从没碰过真后端）。
 * ⇒ 现在**两个 server 各起各的**（`webServer` 数组）+ **每个 project 各自的
 * `baseURL`** ⇒ 「真后端」在结构上**不可能**是 mock。
 *
 * ⚠️ `grep` 匹配**测试标题** ⇒ 标题里必须有 `@real-backend`
 *    （或用 `test('…', { tag: '@real-backend' })`）⇒ 否则收集到 0 个测试
 *    （看起来「全绿」实则什么都没跑）。
 * ⇒ `chromium` 项目用 `grepInvert` **排除** `@real-backend`
 *    ⇒ 同一批用例不在 mock 通道里重复跑（重复 = 假覆盖）。
 *
 * ⚠️ **真后端通道固定用 5174 且 `reuseExistingServer: false`**
 * ⇒ 复用别人起的 server = 复用错配置 ⇒ 宁可**硬失败**。
 *
 * 跑法：
 *   npm run e2e        # mock 通道（无需后端）
 *   npm run e2e:real   # 真后端通道（需后端 + 种子数据）
 */
const MOCK_PORT = 5173;
const REAL_PORT = 5174;

export default defineConfig({
  testDir: './e2e',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: 'list',
  projects: [
    {
      name: 'chromium',
      // ⚠️ 排除 `@real-backend` ⇒ 真后端用例**不在** mock 通道里重复跑。
      grepInvert: /@real-backend/,
      use: { ...devices['Desktop Chrome'], baseURL: `http://localhost:${MOCK_PORT}` },
    },
    {
      name: 'real-backend',
      use: { ...devices['Desktop Chrome'], baseURL: `http://localhost:${REAL_PORT}` },
      grep: /@real-backend/,
    },
  ],
  webServer: [
    {
      command: `npm run dev -- --port ${MOCK_PORT}`,
      url: `http://localhost:${MOCK_PORT}`,
      reuseExistingServer: !process.env.CI,
      timeout: 120_000,
    },
    {
      // ⚠️ **显式**关 MSW ⇒ 这个 server 一定是真后端通道。
      command: `VITE_ENABLE_MOCK=false npm run dev -- --port ${REAL_PORT}`,
      url: `http://localhost:${REAL_PORT}`,
      // ⚠️ **不复用** ⇒ 复用别人起的 server = 复用错配置（评审 H-3 的根因）。
      reuseExistingServer: false,
      timeout: 120_000,
    },
  ],
});
