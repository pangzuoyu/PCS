import { defineConfig } from 'vitest/config';

export default defineConfig({
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./tests/setup.ts'],
    css: true,
    // P7-6B e2e/ 是 Playwright spec, 不归 vitest 跑
    exclude: ['node_modules', 'dist', 'e2e/**'],
    /**
     * 全局单测超时放宽到 20s（2026-10-21 · P9B-1 批中实测）。
     *
     * ⚠️ **默认 5s 在本仓不够**：有一批用例是**真时钟轮询**类
     * （`ReportExecutePage` 推进 `POLL_INTERVAL * 10` 的虚拟时间、
     * `ReportStylePage` 的版本历史渲染…），实测真实耗时 **3.8~8.5s**
     * —— **恰好卡在 5s 线上下** ⇒ 单独跑恒绿、**整 suite 跑时偶发假红**
     * （实测一次失败落在 `ReportExecutePage`，一次落在
     * `EnergySummaryAggregatePage` / `VesselComputePage` —— 不同文件 ⇒
     * 是**负载**问题，不是某几个用例的问题）。
     *
     * ⇒ 统一放宽到 20s（仍是有界），别让 CPU 忙时把 QA 闸门挡成假红。
     */
    testTimeout: 20_000,
    coverage: {
      provider: 'v8',
      reporter: ['text', 'html'],
      include: ['src/**/*.{ts,tsx}'],
      exclude: ['src/types/**', 'src/main.tsx'],
    },
  },
});