/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_PROJECT_ID?: string;
  readonly VITE_DEV_TOKEN?: string;
  /**
   * 是否挂 MSW（评审 #23 · 2026-11-12）。
   *
   * ⚠️ **必须声明成字面量联合** —— 否则 `import.meta.env.VITE_ENABLE_MOCK`
   * 落到 Vite 自带的 `[key: string]: any` ⇒ 写成 `'FALSE'` / `'0'` / `'no'`
   * **类型检查照样过**，而运行时 `!== 'false'` 成立 ⇒ **MSW 静默挂着**
   * ⇒ 真后端 E2E 通道测的是 mock（这正是本批要消灭的假绿）。
   *
   * ⚠️ 语义：只有**恰好** `'false'` 才关 MSW ⇒ 其余（含未设置）都开。
   */
  readonly VITE_ENABLE_MOCK?: 'true' | 'false';
  /** 真后端 E2E 用的 vite proxy 目标（默认 http://localhost:8000）。 */
  readonly VITE_API_PROXY_TARGET?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}