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
export type UserProjectResponse = components['schemas']['UserProjectResponse'];

/** 「我能对它执行**报表**」的项目 —— 公司级模板执行时要选一个。 */
export interface ExecutableProject {
  project_id: string;
  project_name: string;
}

export const projectsApi = {
  /** 建项目（SYSTEM_ADMIN；后端同事务绑默认 RECORD 矩阵）。 */
  create: (body: ProjectCreate): Promise<ProjectOut> =>
    api.post<ProjectOut>('/projects', body).then((r) => r.data),

  /**
   * 列工作区（建项目要选一个**已存在**的 FORMAL 工作区 ⇒ 后端不建孤儿项目）。
   *
   * ⚠️ 只取 FORMAL（评审 #4 落实）：`projects.workspace_id` 指向 FORMAL 工作区
   * ⇒ 选了别的类型 ⇒ 后端 422 `WORKSPACE_NOT_FORMAL`（非 FORMAL 项目永远
   * 送不了审）⇒ 下拉里干脆不给选。
   */
  listWorkspaces: (): Promise<WorkspaceOut[]> =>
    api
      .get<WorkspaceOut[]>('/workspaces')
      .then((r) => r.data.filter((w) => w.workspace_type === 'FORMAL')),

  /**
   * 列「我**能对它执行**报表」的项目 —— 公司级模板执行时要选一个
   * （P10-J-T1 · 公司级模板「执行时选项目」）。
   *
   * ⚠️ **为什么不复用 `useProjectScope().projects`**：那个列表是
   * 「授权 ∪ 工作区挂的项目」（`src/store/projectScope.ts` 的
   * `fetchCandidateIds`）⇒ ⇒ **工作区那条腿是按*所有权*过滤的** ⇒ ⇒
   * ⇒ 授权被撤销的项目**仍在里面** ⇒ ⇒ ⇒ 用户会选到一个**无权执行**
   * ⇒ ⇒ ⇒ 的项目 ⇒ ⇒ ⇒ 点了才吃 404 —— **正是这批要消灭的「点了才知道」**。
   *
   * ⚠️ **SYSTEM_ADMIN 为什么单独一条腿**：admin 靠**全局 bypass**、通常
   * **没有授权行** ⇒ ⇒ 只用授权行 ⇒ ⇒ admin 的下拉会是**空的** ⇒ ⇒
   * ⇒ ⇒ 而 admin 恰恰是创建公司级模板的人 ⇒ ⇒ ⇒ ⇒ 用工作区那条腿
   * ⇒ ⇒ ⇒（`/workspaces` 对 SYSTEM_ADMIN 返回全部）。
   *
   * ⚠️ **名字从哪来**：`/user-projects/me` 与 `/workspaces` 都**不返项目名**
   * ⇒ ⇒ ⇒ 逐个 `GET /projects/{id}` 取（拿不到就退回 id 前 8 位 · 不致命）
   * ⇒ ⇒ ⇒ 与 `useProjectScope` 的 `fetchNames` 同一手法。
   */
  executableProjects: (isAdmin: boolean): Promise<ExecutableProject[]> => {
    const ids = new Set<string>();
    const load = async () => {
      if (!isAdmin) {
        // 普通用户：只要**自己的授权行**（后端已排除被撤销的）
        const { data } = await api.get<UserProjectResponse[]>('/user-projects/me');
        for (const row of data ?? []) ids.add(row.project_id);
      } else {
        // SYSTEM_ADMIN：工作区挂的项目（admin 看得到全部）
        const { data } = await api.get<{ project_id: string | null }[]>('/workspaces');
        for (const row of data ?? []) if (row.project_id) ids.add(row.project_id);
      }
      const list = await Promise.all(
        [...ids].map(async (id) => {
          try {
            const { data } = await api.get<ProjectOut>(`/projects/${id}`);
            return { project_id: id, project_name: data.project_name || id.slice(0, 8) };
          } catch {
            return { project_id: id, project_name: id.slice(0, 8) };
          }
        }),
      );
      return list;
    };
    return load();
  },
};
