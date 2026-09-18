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

export const authApi = {
  login: (username: string, password: string) =>
    api.post<TokenResponse>('/auth/login', { username, password }).then((r) => r.data),
  mockLogin: (username: string) =>
    api
      .post<TokenResponse>('/auth/mock-login', { username })
      .then((r) => r.data),
  me: () => api.get<{ username: string; role: string }>('/auth/me').then((r) => r.data),
};
