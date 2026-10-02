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

api.interceptors.response.use(
  (r) => r,
  (err: AxiosError) => {
    if (err.response?.status === 401) {
      useAuth.getState().clearSession();
      if (window.location.pathname !== '/login') {
        window.location.href = '/login';
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
