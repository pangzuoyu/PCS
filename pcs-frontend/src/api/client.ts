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
 *
 * ⚠️ **`USER_DISABLED`（P9B-4 评审 #1）** —— T0-B 把账号状态判定挪到 **actor 层**
 * （后端每请求查 `users.status`）⇒ 账号被停用后，**在手 access token 的下一次
 * 请求**就得到 401 + body 带 `code="USER_DISABLED"`。
 * ⚠️ 它**带 code** ⇒ 旧逻辑的 `!code` 分支不成立 ⇒ **不在白名单就等于不登出**
 * ⇒ 停用用户带着在手 token 卡在任意业务页、之后每个请求都 401、**永远回不到
 * 登录页**，也永远不知道自己被停用了。
 * ⇒ SPEC §7.1（V2.12）承诺「前端按**普通 401** 处理（跳登录页）」⇒ 这里补上。
 *
 * ⚠️ **`REFRESH_REVOKED`** —— ADR-0046 §5 的 token_version 闸，同形状的既有缺口
 * （refresh 路径会返回它）⇒ 一并补上。
 *
 * ⚠️ **为什么没有「账号已停用」的提示**：跳转是 `window.location.href`（整页导航）
 * ⇒ 任何 toast 都会在跳转瞬间消失 ⇒ 真要提示得改跳转机制（另议）。
 */
const SESSION_OVER_CODES = new Set([
  'MISSING_BEARER',
  'INVALID_TOKEN',
  'EXPIRED_TOKEN',
  'WRONG_TOKEN_TYPE',
  'INVALID_REFRESH',
  'EXPIRED_REFRESH',
  // ⚠️ 账号被停用 ⇒ actor 层每次请求都判 ⇒ 在手 token 下一次请求即失效
  'USER_DISABLED',
  // ⚠️ ADR-0046 §5 的 token_version 闸（refresh 路径）
  'REFRESH_REVOKED',
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
