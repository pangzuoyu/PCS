import { create } from 'zustand';

function uuidFromUsername(username: string): string {
  // 稳定派生：同一 username 同一 UUID，避免用户切换时混乱
  // Sprint 1 占位；P1.2 后端会从 /me 返回真 user_id
  const NAMESPACE = '6ba7b810-9dad-11d1-80b4-00c04fd430c8';
  return deterministicUuid(NAMESPACE, username);
}

function deterministicUuid(namespace: string, name: string): string {
  const ns = namespace.replace(/-/g, '');
  const data = `${ns}${name}`;
  let h1 = 0x811c9dc5;
  let h2 = 0xdeadbeef;
  for (let i = 0; i < data.length; i++) {
    const c = data.charCodeAt(i);
    h1 = Math.imul(h1 ^ c, 16777619) >>> 0;
    h2 = Math.imul(h2 ^ c, 2246822507) >>> 0;
  }
  const hex = (n: number, len: number) => n.toString(16).padStart(len, '0');
  const p1 = hex(h1, 8);
  const p2 = hex(h2, 8);
  const p3 = hex((h1 ^ h2) >>> 0, 8);
  const p4 = hex((h2 ^ h1) >>> 0, 8);
  return `${p1.slice(0, 8)}-${p2.slice(0, 4)}-4${p2.slice(4, 7)}-${(parseInt(p3.slice(0, 2), 16) & 0x3f | 0x80).toString(16)}${p3.slice(2, 7)}-${p4}${hex(h1 ^ 0xabcd, 4).slice(0, 4)}`;
}

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
      userId: uuidFromUsername(s.username),
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