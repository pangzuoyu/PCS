/**
 * 待办 API 客户端（P9A Z 收口 · SPEC §6.22 · ADR-0049 §②）。
 *
 * ⚠️ **待办不落库** —— 每次查询由「签署矩阵的当前步骤 × 当前用户角色」
 * **实时计算**（后端 `app/api/v1/deliverables.py::list_todos`）。
 * ⇒ 前端**不得**缓存待办列表，也**不得**假设待办会「变少」——
 * 别人签了、你刷新，才会消失。
 *
 * ⚠️ **越权过滤在服务端完成**（后端按 `project_id` 收窄）⇒
 * 前端**不得**自行按项目过滤 —— 那会把「无权限」显示成「无待办」。
 */
import { api } from './client';
import type { components } from '../types/api';

export type TodoItem = components['schemas']['TodoResponse'];
export type TodoList = components['schemas']['TodoListResponse'];

export const todosApi = {
  list: (): Promise<TodoList> =>
    api.get<TodoList>('/todos').then((r) => r.data),
};
