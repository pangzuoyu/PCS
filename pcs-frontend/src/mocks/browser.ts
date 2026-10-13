/**
 * MSW browser worker — dev 环境挂载（P45-0-5）
 * 生产构建时不挂（main.tsx 用 import.meta.env.DEV 判断）。
 */
import { setupWorker } from "msw/browser";

import { handlers, devOnlyMockHandlers } from "./handlers";
import { reportBuilderHandlers } from "./reportBuilder";

export const worker = setupWorker(
  ...handlers,
  ...devOnlyMockHandlers,
  // REPORT_BUILDER（b10-b12 / c6）：真 client 打真后端会 401 ——
  // dev 的 mock-login 返回的是假 token。详见 reportBuilder.ts 头注。
  ...reportBuilderHandlers,
);