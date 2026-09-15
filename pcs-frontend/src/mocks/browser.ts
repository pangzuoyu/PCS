/**
 * MSW browser worker — dev 环境挂载（P45-0-5）
 * 生产构建时不挂（main.tsx 用 import.meta.env.DEV 判断）。
 */
import { setupWorker } from "msw/browser";

import { handlers } from "./handlers";

export const worker = setupWorker(...handlers);