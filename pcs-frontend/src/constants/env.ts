/**
 * 前端常量统一来源（P5 frontend 收口 checklist 收口项 #1）。
 *
 * 替换前：
 * - PROJECT_ID 硬编码于 `routeWrappers.tsx:72`
 * - DEV_BEARER 硬编码 3 处：`routeWrappers.tsx:75`、`MainLayout.tsx:82`、`AssetListPage.tsx:174`
 *
 * vite env vars 通过 `.env.development` / `.env.production` 注入；
 * 未注入时回退到既有默认值（保证 dev / prod 都能跑）。
 */

/**
 * **占位**项目 id（⚠️ **不是**真项目）。
 *
 * ⚠️ **为什么单独命名**（P10-F · 评审 #24）：原名叫 `PROJECT_ID` ⇒ ⇒ 读起来
 * 像「这个项目」⇒ ⇒ 于是被**当成真值**用（仪表盘拿它去取清单 ⇒ 两条 404；
 * `routeWrappers.tsx` 的 4 处也拿它当真 id ⇒ 那是 TODO-159/160 的根因之一）
 * ⇒ ⇒ 名字必须**说清它是什么**。
 */
export const PLACEHOLDER_PROJECT_ID: string =
  import.meta.env.VITE_PROJECT_ID ?? '00000000-0000-0000-0000-000000000001';

/**
 * ⚠️ **旧名**（`PROJECT_ID`）⇒ 语义 = **占位 id** ⇒ ⇒ 别把它当真项目用。
 *
 * ⚠️ 仍有 4 处引用（`routeWrappers.tsx` 的 3 个页面 + 1 处）⇒ ⇒ 那是
 * TODO-159 / TODO-160 的**既有白名单项** ⇒ ⇒ 本批不顺手改（改了就白名单失效），
 * 已登记 TODO（见 `TODOS.md`）。
 */
export const PROJECT_ID: string = PLACEHOLDER_PROJECT_ID;

export const DEV_BEARER: string = `Bearer ${
  import.meta.env.VITE_DEV_TOKEN ?? 'mock-jwt-token'
}`;