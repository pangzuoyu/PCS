/**
 * 健康检查客户端（P9B-1 · SPEC §6.23 / P9A-NOT-006）。
 *
 * ## 只取 `realtime` / `realtime_reason`
 *
 * `GET /health` 的 `status` / `database` 是**服务端运维视角**（liveness /
 * readiness）⇒ 前端**不**据此渲染任何东西。
 *
 * ⚠️ `realtime` 检测的是 **pub/sub 通道可达性**，**不是** Redis 整体健康
 * ⇒ 前端只把它当「通知推送是否即时」的提示，**不**当「服务挂了」。
 *
 * ⚠️ `realtime` **不得**纳入 liveness / readiness 判定（后端注释明写）：
 * Redis 挂了会触发**服务重启循环**。
 */
import { api } from './client';
import type { components } from '../types/api';

export type HealthResponse = components['schemas']['HealthResponse'];

export const healthApi = {
  get: (): Promise<HealthResponse> => api.get<HealthResponse>('/health').then((r) => r.data),
};
