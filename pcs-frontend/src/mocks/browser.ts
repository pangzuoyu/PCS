/**
 * MSW browser worker — dev 环境挂载（P45-0-5）
 * 生产构建时不挂（main.tsx 用 import.meta.env.DEV 判断）。
 */
import { setupWorker } from "msw/browser";

import { handlers, devOnlyMockHandlers } from "./handlers";
import { reportBuilderHandlers } from "./reportBuilder";
import { signatureMatrixHandlers } from "./signatureMatrices";
import { changeNoticeHandlers } from "./changeNotices";

export const worker = setupWorker(
  ...handlers,
  ...devOnlyMockHandlers,
  // TODO-079 / TODO-083（P9A-DLV-011 的前端面）：签署矩阵管理 + 变更单三端点。
  // ⚠️ 这两组端点**已在 OpenAPI 契约里**（P9A-DLV-011 交付）⇒ 放**契约组**
  // （参与 drift 校验），不是 dev-only。
  ...signatureMatrixHandlers,
  ...changeNoticeHandlers,
  // REPORT_BUILDER（b10-b12 / c6）：真 client 打真后端会 401 ——
  // dev 的 mock-login 返回的是假 token。详见 reportBuilder.ts 头注。
  ...reportBuilderHandlers,
);