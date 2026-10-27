/**
 * 项目 API 客户端（P9B-2 · 延后的 minor · Batch F）。
 *
 * ⚠️ **为什么现在才有它**：T-1 只交付了**后端**的 `POST /projects` ⇒ 前端
 *    **没有建项目的入口** ⇒ 项目建不出来 ⇒ 签署流程的对象（记录 / 交付物）
 *    全都挂在项目下 ⇒ 真实 UI 上根本走不通（只能靠 mock 验证）。
 *
 * ⚠️ **建项目 ≠ 建完就能用**：后端在**同一事务**里给新项目绑一份 ACTIVE 的
 *    RECORD 签署矩阵（R-17）⇒ 建完**当场就能送审**。
 *
 * ⚠️ 响应体取**契约类型**（`components['schemas'][...]`）—— 手写自由 dict
 *    就是 bug-2040 的根源（mock 与真端点不同源 ⇒ 漂移被藏住）。
 */
import { api } from './client';
import type { components } from '../types/api';

export type ProjectCreate = components['schemas']['ProjectCreate'];
export type ProjectOut = components['schemas']['ProjectOut'];
export type WorkspaceOut = components['schemas']['WorkspaceOut'];

export const projectsApi = {
  /** 建项目（SYSTEM_ADMIN；后端同事务绑默认 RECORD 矩阵）。 */
  create: (body: ProjectCreate): Promise<ProjectOut> =>
    api.post<ProjectOut>('/projects', body).then((r) => r.data),

  /**
   * 列工作区（建项目要选一个**已存在**的 FORMAL 工作区 ⇒ 后端不建孤儿项目）。
   *
   * ⚠️ 只取 FORMAL：`projects.workspace_id` 指向 FORMAL 工作区 ⇒ 选了别的
   *    类型 ⇒ 后端 404。
   */
  listWorkspaces: (): Promise<WorkspaceOut[]> =>
    api.get<WorkspaceOut[]>('/workspaces').then((r) => r.data),
};
