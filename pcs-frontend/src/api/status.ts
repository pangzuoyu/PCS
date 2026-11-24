/**
 * 系统状态客户端（P10-C · T1b · SPEC §7.22）。
 *
 * ## 为什么**不用** `/health`
 *
 * `/health` 是 **liveness probe**（给 K8s / compose healthcheck 用）⇒ ⇒ ⇒
 * 恒 200 且**故意**只探 DB ⇒ ⇒ ⇒ 前端据此渲染会**误导**（Redis 挂了在
 * `/health` 里看不出来）⇒ ⇒ ⇒ ⇒ 而且 ADR-0049 §⑥ 明写：往 `/health` 上
 * 叠阻塞依赖 ⇒ ⇒ ⇒ Redis 抖动 ⇒ ⇒ ⇒ **服务重启循环**。
 *
 * ⇒ ⇒ ⇒ `/status` 是**独立端点**（恒 200 + 五个组件的明细）⇒ ⇒ ⇒ 给页面用。
 *
 * ## ⚠️ **不含敏感值**
 *
 * 后端只报「通不通 / 有多深 / 什么时候心跳」⇒ ⇒ ⇒
 * **不报** LDAP bind 密码 / DB 口令 / Redis URL ⇒ ⇒ ⇒ 前端也不许拼进去。
 */
import { api } from './client';
import type { components } from '../types/api';

export type StatusResponse = components['schemas']['StatusResponse'];
export type ComponentStatus = components['schemas']['ComponentStatus'];
export type QueueStatus = components['schemas']['QueueStatus'];

/** 组件状态 → antd Tag 的颜色（枚举固定 ⇒ ⇒ 前端能可靠判断）。 */
export const STATUS_COLOR: Record<ComponentStatus['status'], string> = {
  ok: 'green',
  degraded: 'orange',
  down: 'red',
  unknown: 'default',
};

/** 组件状态 → 中文标签。 */
export const STATUS_LABEL: Record<ComponentStatus['status'], string> = {
  ok: '正常',
  degraded: '降级',
  down: '不可用',
  unknown: '未知',
};

export const statusApi = {
  get: (): Promise<StatusResponse> => api.get<StatusResponse>('/status').then((r) => r.data),
};
