import { create } from 'zustand';

export interface AuthState {
  accessToken: string | null;
  refreshToken: string | null;
  username: string | null;
  role: string | null;
  setSession: (s: {
    access_token: string;
    refresh_token: string;
    username: string;
    role: string;
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
  setSession: (s) =>
    set({
      accessToken: s.access_token,
      refreshToken: s.refresh_token,
      username: s.username,
      role: s.role,
    }),
  clearSession: () =>
    set({ accessToken: null, refreshToken: null, username: null, role: null }),
}));
