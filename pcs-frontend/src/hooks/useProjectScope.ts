/**
 * `useProjectScope` —— 当前**项目作用域**（P10-H · T1 · TODO-194）。
 *
 * ## 它现在做什么
 *
 * ① 拉「我能看的项目」清单（`GET /user-projects/me` ∪ `GET /workspaces` 挂的项目）
 * ② 拉每个项目的名字（`GET /projects/{id}`）
 * ③ 把**选中的**项目 id 交给页面 ⇒ ⇒ **不再猜「第一个」**
 *
 * ## 与旧版的差别
 *
 * | | 旧（P10-C · T2） | 新（P10-H · T1） |
 * |---|---|---|
 * 候选来源 | `GET /workspaces` 的**第一个**有项目的工作区 | 授权 ∪ 工作区（**全部**候选） |
 * 选择 | **猜**（env hint > 第一个） | **用户选**（hint 只作首次默认值） |
 * 名字 | 没有 | 有（`ProjectOut.project_name`） |
 * `workspaceId` | 返回 | **删掉**（无人消费 ⇒ ⇒ 留着就是误导） |
 *
 * ⚠️ **状态在 store 里**（`src/store/projectScope.ts`）⇒ ⇒ 换页不丢选择
 * ⇒ ⇒ 顶栏的选择器与页面读的是**同一份**真相源。
 */
import { useEffect } from 'react';

import { useProjectScopeStore, type ProjectOption } from '../store/projectScope';

export interface ProjectScope {
  /** 当前选中的真项目 id（`null` ⇒ 没解析出来 ⇒ 页面要给出说明，别去请求端点）。 */
  projectId: string | null;
  /** 候选项目清单（选择器渲染用）。 */
  projects: ProjectOption[];
  loading: boolean;
  error: string | null;
  /** 换项目。 */
  selectProject: (projectId: string) => void;
}

export function useProjectScope(): ProjectScope {
  const projects = useProjectScopeStore((s) => s.projects);
  const currentProjectId = useProjectScopeStore((s) => s.currentProjectId);
  const loading = useProjectScopeStore((s) => s.loading);
  const error = useProjectScopeStore((s) => s.error);
  const selectProject = useProjectScopeStore((s) => s.selectProject);
  const ensureLoaded = useProjectScopeStore((s) => s.ensureLoaded);

  // ⚠️ **幂等** ⇒ ⇒ 顶栏 + 多个页面同时挂载也只发**一轮**请求。
  useEffect(() => {
    void ensureLoaded();
  }, [ensureLoaded]);

  return { projectId: currentProjectId, projects, loading, error, selectProject };
}
