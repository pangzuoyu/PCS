/**
 * 项目作用域 store（P10-H · T1 · TODO-194）。
 *
 * ## 为什么要有它
 *
 * P10-C 的 `useProjectScope` 从 `GET /workspaces` 里取**第一个**有项目的工作区
 * ⇒ ⇒ 一个身份有多个项目时是**猜一个**（真后端通道的种子库里就有两个）
 * ⇒ ⇒ 页面查的是「别的项目」⇒ ⇒ 看着有数据实则不是它。
 *
 * ⇒ ⇒ 真解法：**我能选**。
 *
 * ## 候选项目从哪来（两个来源取并集）
 *
 * | 来源 | 覆盖 | 端点 |
 * |---|---|---|
 * | **我的授权** | 别人建的、我被授权的项目 | `GET /user-projects/me` |
 * | **工作区挂的项目** | 我自己建的（授权行可能是后加的）· **admin** 则是**全部** | `GET /workspaces`（admin 全量）/ `?owner_id={我}`（普通用户） |
 *
 * ⚠️ **为什么 admin 要额外走工作区**：`/user-projects/me` 只返**授权行**
 * ⇒ ⇒ admin 若没有授权行 ⇒ 选择器是空的 ⇒ ⇒ admin 连自己的项目都选不了
 * ⇒ ⇒ 那是**功能回退**（P10-C 的旧口径就是「admin 走工作区全量」）。
 *
 * ## 为什么名字要单独拉
 *
 * `/user-projects/me` 只给 `project_id`（**没有名字**）⇒ ⇒ 名字在
 * `GET /projects/{id}` 的 `ProjectOut.project_name` ⇒ ⇒ 并行拉一次。
 * ⚠️ 拉不到名字**不致命** ⇒ ⇒ 退回 id 前 8 位 ⇒ ⇒ 选择器照常可用。
 *
 * ## 并发
 *
 * `ensureLoaded` **幂等** ⇒ ⇒ 多个组件同时挂载（顶栏 + 页面）只发**一轮**请求。
 */
import { create } from 'zustand';

import { api } from '../api/client';
import { errorText } from '../api/errors';
import { useAuth } from './auth';
import type { components } from '../types/api';

type UserProjectResponse = components['schemas']['UserProjectResponse'];
type ProjectOut = components['schemas']['ProjectOut'];

/** 选择器里的一项（`project_id` + 显示名 + 我在项目里的角色）。 */
export interface ProjectOption {
  projectId: string;
  name: string;
  roleInProject: string | null;
}

interface ProjectScopeState {
  projects: ProjectOption[];
  currentProjectId: string | null;
  loading: boolean;
  error: string | null;
  /** 拉一次（幂等 ⇒ 并发调用只发一轮请求）。 */
  ensureLoaded: () => Promise<void>;
  /** 换项目（用户操作）。 */
  selectProject: (projectId: string) => void;
  /** 登出 / 换身份 ⇒ 清干净。 */
  reset: () => void;
}

/** 正在飞的那一轮请求 ⇒ ⇒ 幂等的实现抓手。 */
let inflight: Promise<void> | null = null;

function httpStatus(err: unknown): number | undefined {
  return (err as { response?: { status?: number } })?.response?.status;
}

/** 候选项目 id（授权 ∪ 工作区挂的项目），带我在项目里的角色。 */
async function fetchCandidateIds(): Promise<Map<string, string | null>> {
  const { userId, role } = useAuth.getState();
  const out = new Map<string, string | null>();

  // ① 我的授权
  try {
    const { data } = await api.get<UserProjectResponse[]>('/user-projects/me');
    for (const row of data ?? []) {
      if (!out.has(row.project_id)) out.set(row.project_id, row.role_in_project ?? null);
    }
  } catch (err) {
    // ⚠️ **403 不吞成「空」**：那是「这个身份读不了授权列表」
    //    （角色闸只放 DESIGNER+）⇒ ⇒ 后面没有候选时才报出来。
    if (httpStatus(err) !== 403) throw err;
  }

  // ② 工作区挂的项目（admin 全量 / 普通用户只看自己的）
  try {
    const { data } =
      role === 'SYSTEM_ADMIN' || !userId
        ? await api.get<{ project_id: string | null }[]>('/workspaces')
        : await api.get<{ project_id: string | null }[]>('/workspaces', {
            params: { owner_id: userId },
          });
    for (const row of data ?? []) {
      if (row.project_id && !out.has(row.project_id)) out.set(row.project_id, null);
    }
  } catch (err) {
    // ⚠️ **只有 403 才退**（= 「不传 owner_id 需要 SYSTEM_ADMIN」）
    // ⇒ ⇒ 其它错误（401 / 网络 / 500）**原样抛** ⇒ ⇒ 不被误吞。
    if (httpStatus(err) !== 403) throw err;
  }

  return out;
}

/** 并行拉项目名（拉不到 ⇒ 退回 id 前 8 位，不致命）。 */
async function fetchNames(ids: string[]): Promise<Map<string, string>> {
  const names = new Map<string, string>();
  await Promise.all(
    ids.map(async (id) => {
      try {
        const { data } = await api.get<ProjectOut>(`/projects/${id}`);
        names.set(id, data.project_name || id.slice(0, 8));
      } catch {
        names.set(id, id.slice(0, 8));
      }
    }),
  );
  return names;
}

export const useProjectScopeStore = create<ProjectScopeState>((set, get) => ({
  projects: [],
  currentProjectId: null,
  loading: false,
  error: null,

  ensureLoaded: async () => {
    if (inflight) return inflight;
    const run = async (): Promise<void> => {
      set({ loading: true, error: null });
      try {
        const candidates = await fetchCandidateIds();
        const ids = [...candidates.keys()];
        if (ids.length === 0) {
          set({
            projects: [],
            currentProjectId: null,
            loading: false,
            error: '当前身份没有可用的项目作用域',
          });
          return;
        }
        const names = await fetchNames(ids);
        const projects: ProjectOption[] = ids.map((id) => ({
          projectId: id,
          name: names.get(id) ?? id.slice(0, 8),
          roleInProject: candidates.get(id) ?? null,
        }));

        // ⚠️ **选中项的优先级**：已选（还在列表里）> env hint > 第一个
        const hint = import.meta.env.VITE_PROJECT_ID;
        const current = get().currentProjectId;
        const next =
          (current && projects.some((p) => p.projectId === current) ? current : null) ??
          (hint && projects.some((p) => p.projectId === hint) ? hint : null) ??
          projects[0].projectId;

        set({ projects, currentProjectId: next, loading: false, error: null });
      } catch (err) {
        set({
          projects: [],
          currentProjectId: null,
          loading: false,
          error: errorText(err, '解析项目作用域失败'),
        });
      }
    };
    inflight = run().finally(() => {
      inflight = null;
    });
    return inflight;
  },

  selectProject: (projectId: string) => {
    set({ currentProjectId: projectId });
  },

  reset: () => {
    inflight = null;
    set({ projects: [], currentProjectId: null, loading: false, error: null });
  },
}));
