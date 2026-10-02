import { create } from 'zustand';

/** Zustand auth store 形状（双 token + 用户身份 + setSession 写入 + clear 清理）。

P7-7+ actor 上下文一致性: userId 不再前端派生 (deterministicUuid 自实现
vs backend uuid5 分叉), 而是由 login → /auth/me 拿到权威 user_id.
前后端 user_id 必须 100% 一致, 否则 BLOCKER-3 endpoint guard 校验失败.
 */
export interface AuthState {
  accessToken: string | null;
  refreshToken: string | null;
  username: string | null;
  role: string | null;
  userId: string | null;
  setSession: (s: {
    access_token: string;
    refresh_token: string;
    username: string;
    role: string;
    user_id: string;
  }) => void;
  clearSession: () => void;
}

/**
 * token 仅存内存（zustand store 不持久化）。
 * 刷新即丢失 → 重新登录；防 XSS / 第三方脚本读取 localStorage。
 */
export const useAuth = create<AuthState>((set) => ({
  accessToken: null,
  refreshToken: null,
  username: null,
  role: null,
  userId: null,
  setSession: (s) =>
    set({
      accessToken: s.access_token,
      refreshToken: s.refresh_token,
      username: s.username,
      role: s.role,
      userId: s.user_id,
    }),
  clearSession: () =>
    set({
      accessToken: null,
      refreshToken: null,
      username: null,
      role: null,
      userId: null,
    }),
}));