/**
 * `useProjectScope` —— 当前**项目作用域**（P10-C · T2 · TODO-159）。
 *
 * ## 为什么需要它
 *
 * 前端此前到处拿**占位** project id（`PLACEHOLDER_PROJECT_ID` =
 * `00000000-0000-0000-0000-000000000001`）去调端点 ⇒ ⇒ 那**不是真项目**
 * ⇒ ⇒ 真后端下必然 404（TODO-159 / TODO-167 同族）。
 *
 * ⇒ ⇒ 真 id 从**服务端**拿：`GET /workspaces` 的每一行都带 `project_id`
 * （FORMAL 工作区 ⇒ ⇒ 必然有项目）⇒ ⇒ 取**第一个有 project_id 的工作区**。
 *
 * ## 两种身份 ⇒ 两种取法
 *
 * | 身份 | `GET /workspaces`（不传 owner_id） | 本 hook 的取法 |
 * |---|---|---|
 * | SYSTEM_ADMIN | **200**（全量） | 直接用 |
 * | 普通用户 | **403**（`owner_id` 不传即 admin 视图） | 退到 `?owner_id={我自己}` |
 *
 * ⚠️ 退到 `owner_id=自己` 时拿到的是**我自己的**工作区 ⇒ ⇒ 别人建的、
 * 我有授权的项目**看不到** ⇒ ⇒ 那时要靠「项目选择器」（还没有）⇒
 * ⇒ 本 hook 只保证「**有一个**可用的项目作用域」，不保证是哪一个。
 */
import { useEffect, useState } from 'react';

import { api } from '../api/client';
import { errorText } from '../api/errors';
import { useAuth } from '../store/auth';

/** `GET /workspaces` 的一行（只取本 hook 要用的字段）。 */
interface WorkspaceRow {
  workspace_id: string;
  workspace_type: string;
  project_id: string | null;
}

export interface ProjectScope {
  /** 真项目 id（`null` ⇒ 没解析出来 ⇒ 页面要给出说明，别去请求端点）。 */
  projectId: string | null;
  /** 对应的工作区 id（工作区作用域的端点用它）。 */
  workspaceId: string | null;
  loading: boolean;
  error: string | null;
}

export function useProjectScope(): ProjectScope {
  const [scope, setScope] = useState<ProjectScope>({
    projectId: null,
    workspaceId: null,
    loading: true,
    error: null,
  });

  useEffect(() => {
    let cancelled = false;

    const run = async (): Promise<void> => {
      try {
        let rows: WorkspaceRow[];
        try {
          rows = (await api.get<WorkspaceRow[]>('/workspaces')).data;
        } catch (err) {
          // ⚠️ **只有 403 才退**（= 「不传 owner_id 需要 SYSTEM_ADMIN」）
          // ⇒ ⇒ 其它错误（401 / 网络 / 500）**原样抛** ⇒ ⇒ 不被误吞。
          const status = (err as { response?: { status?: number } })?.response?.status;
          if (status !== 403) throw err;
          const myId = useAuth.getState().userId;
          if (!myId) throw err;
          rows = (await api.get<WorkspaceRow[]>('/workspaces', { params: { owner_id: myId } })).data;
        }
        if (cancelled) return;
        // ⚠️ **取第一个「有项目」的工作区**（FORMAL ⇒ 必然有项目）。
        const scoped = rows.find((w) => w.project_id);
        setScope({
          projectId: scoped?.project_id ?? null,
          workspaceId: scoped?.workspace_id ?? null,
          loading: false,
          error: scoped ? null : '当前身份没有可用的项目作用域（工作区没有挂项目）',
        });
      } catch (err) {
        if (cancelled) return;
        setScope({
          projectId: null,
          workspaceId: null,
          loading: false,
          error: errorText(err, '解析项目作用域失败'),
        });
      }
    };

    void run();
    return () => {
      cancelled = true;
    };
  }, []);

  return scope;
}
