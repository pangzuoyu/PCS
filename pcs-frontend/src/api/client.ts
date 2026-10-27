import axios, { AxiosError } from 'axios';
import { useAuth } from '../store/auth';

const baseURL = '/api/v1';

export const api = axios.create({ baseURL });

api.interceptors.request.use((config) => {
  const token = useAuth.getState().accessToken;
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

/**
 * 401 里**表示会话结束**的错误码。
 *
 * ⚠️ **不是所有 401 都是会话过期** —— 代录客户批准的**二次认证**失败
 * （AD 密码打错）也是 401（`SECONDARY_AUTH_FAILED`）⇒ 一律登出会把用户**踢回
 * 登录页**、填好的凭证/客户批准人/日期**全丢**，而且**看不到**「用户名或密码
 * 错误」⇒ 只有**会话码**才清 session。
 */
const SESSION_OVER_CODES = new Set([
  'MISSING_BEARER',
  'INVALID_TOKEN',
  'EXPIRED_TOKEN',
  'WRONG_TOKEN_TYPE',
  'INVALID_REFRESH',
  'EXPIRED_REFRESH',
]);

api.interceptors.response.use(
  (r) => r,
  (err: AxiosError) => {
    if (err.response?.status === 401) {
      const code = (err.response.data as { code?: string } | undefined)?.code;
      // ⚠️ **没有 code** ⇒ 不知道是什么 401 ⇒ 按会话过期处理（旧行为）
      if (!code || SESSION_OVER_CODES.has(code)) {
        useAuth.getState().clearSession();
        if (window.location.pathname !== '/login') {
          window.location.href = '/login';
        }
      }
    }
    return Promise.reject(err);
  },
);

/** `/auth/login` 与 `/auth/refresh` 响应（access + refresh 双 token + 用户信息）。 */
export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  role: string;
  username: string;
}

/** P7-7+ actor 上下文: /auth/me 响应 (username + role + user_id).
 * 后端优先级: JWT user_id 声明 > uuid5(NAMESPACE_DNS, sub). */
export interface MeResponse {
  username: string;
  role: string;
  user_id: string;
}

export const authApi = {
  login: (username: string, password: string) =>
    api.post<TokenResponse>('/auth/login', { username, password }).then((r) => r.data),
  mockLogin: (username: string) =>
    api
      .post<TokenResponse>('/auth/mock-login', { username })
      .then((r) => r.data),
  me: () => api.get<MeResponse>('/auth/me').then((r) => r.data),
};
