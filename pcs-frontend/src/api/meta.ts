/**
 * Meta API 客户端（状态机 + 权限矩阵）—— P9B-2 · T4 的数据源。
 *
 * ## 为什么操作栏的数据源是 meta 而不是前端表
 *
 * SPEC §6.3 给了一张「状态 → 按钮」的冻结表，但**前端硬编码它 = 第二份真相源**：
 * 后端加一个状态迁移（`app/services/state_machine.py` 的 `ALLOWED_TRANSITIONS`），
 * 前端的按钮表不会跟着变 ⇒ 用户看到一个**注定 409** 的按钮。
 *
 * ⇒ 按钮渲染由 `GET /meta/state-machine` 驱动（后端从 `ALLOWED_TRANSITIONS` 生成），
 * 角色门禁用同一条迁移的 `allowed_roles`（SPEC §5.5.1：**前端不得自行推导能力**）。
 *
 * ⚠️ 契约里的 schema 名是 **`StateTransition-Output`** —— 后端 `meta.py` 的
 * `StateTransition` 与 `models/enums.py` 的同名枚举撞名，FastAPI 给前者加了
 * `-Output` 后缀。
 */
import { api } from './client';
import type { components } from '../types/api';

export type StateMachineResponse = components['schemas']['StateMachineResponse'];
export type StateTransition = components['schemas']['StateTransition-Output'];
export type PermissionItem = components['schemas']['PermissionItem'];

export const metaApi = {
  stateMachine: (): Promise<StateMachineResponse> =>
    api.get<StateMachineResponse>('/meta/state-machine').then((r) => r.data),
  permissions: (): Promise<PermissionItem[]> =>
    api.get<PermissionItem[]>('/meta/permissions').then((r) => r.data),
};
