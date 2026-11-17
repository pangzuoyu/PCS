/**
 * Playwright `globalSetup` —— 真后端通道的 **fail-fast**（P10-B 评审 #23）。
 *
 * ## 为什么要有它
 *
 * `src/constants/env.ts::PROJECT_ID` 的默认值是**占位 id**
 * （`00000000-0000-0000-0000-000000000001`）⇒ 真后端通道若带着它 ⇒
 * 前端查的是**一个不存在的项目** ⇒ ⇒
 *
 * - 表格永远没行 ⇒ 「页面渲染了」**证明不了**任何事；
 * - axios 只对 401 报错 ⇒ 404 **不产生**控制台 error ⇒ **没有红**；
 * - ⇒ ⇒ **整条通道全绿，而它从没碰过被 seed 的数据** ⇒ **假绿**。
 *
 * ⇒ ⇒ 在**跑之前**就断言「项目 id 不是占位 id」⇒ 假绿**没有机会发生**。
 */
import {
  FLOW_PROJECT_ID,
  PLACEHOLDER_PROJECT_ID,
} from './channel-config';

/**
 * 生效的项目 id —— 与 `playwright.config.ts` 的 webServer env **同一口径**
 * （env 优先 ⇒ 没显式设就用 flows 项目的派生 id）。
 */
function effectiveProjectId(): string {
  return process.env.VITE_PROJECT_ID ?? FLOW_PROJECT_ID;
}

export default async function globalSetup(): Promise<void> {
  const projectId = effectiveProjectId();
  if (projectId !== PLACEHOLDER_PROJECT_ID) {
    return;
  }
  throw new Error(
    [
      'VITE_PROJECT_ID 是**占位 id** ⇒ 真后端通道查的是一个不存在的项目',
      '⇒ 表格永远没行、axios 也不报错 ⇒ **绿灯是假的**。',
      '',
      '跑法（两个终端）：',
      '  ① cd pcs-backend && bash scripts/serve_e2e_backend.sh',
      '  ② cd pcs-frontend && npm run e2e:real',
      '',
      '（不需要显式设 VITE_PROJECT_ID —— playwright.config.ts 的 webServer env',
      '  默认就是 flows 项目 id；只有要覆盖时才设。）',
    ].join('\n'),
  );
}
