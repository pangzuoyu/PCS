import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

/**
 * `/api` 代理目标 —— **可用 env 覆盖**（`VITE_API_PROXY_TARGET`）。
 *
 * ⚠️ 默认仍是 `http://localhost:8000`（既有开发流程不变）。
 * 真后端 E2E 需要它是因为 **8000 端口未必空着**（本机就有一个别的服务占着）
 * ⇒ 后端可以起在别的端口，代理指过去即可，不必改代码。
 */
const apiProxyTarget = process.env.VITE_API_PROXY_TARGET || 'http://localhost:8000';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      // ⚠️ **必须排在 `/api` 前面** —— vite 按**插入顺序**取第一个前缀匹配。
      //
      // mock-login 的**真实路径是 `/auth/mock-login`**（ADR-0046 · 它挂在
      // main.py 而不是 `api_router` ⇒ 没有 `/api/v1` 前缀），
      // 而前端 axios 的 baseURL 是 `/api/v1` ⇒ 请求落在 `/api/v1/auth/mock-login`。
      // ⇒ MSW 通道下 MSW 自己应答（不经过代理）⇒ 一直没人发现这个不一致；
      // ⇒ **真后端通道**下它会 404 ⇒ 症状是「登录失败」，真因是路径不匹配。
      // ⇒ 在代理这层改写（dev-only 端点、不在 OpenAPI 里 ⇒ 无契约可漂移）。
      '/api/v1/auth/mock-login': {
        target: apiProxyTarget,
        changeOrigin: true,
        rewrite: (path: string) => path.replace(/^\/api\/v1\/auth/, '/auth'),
      },
      '/api': {
        target: apiProxyTarget,
        changeOrigin: true,
      },
    },
  },
});
