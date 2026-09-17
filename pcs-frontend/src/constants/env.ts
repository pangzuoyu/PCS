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

export const PROJECT_ID: string =
  import.meta.env.VITE_PROJECT_ID ?? '00000000-0000-0000-0000-000000000001';

export const DEV_BEARER: string = `Bearer ${
  import.meta.env.VITE_DEV_TOKEN ?? 'mock-jwt-token'
}`;