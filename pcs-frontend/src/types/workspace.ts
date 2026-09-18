/**
 * Workspace 类型定义（V1 极简版）。
 *
 * 三种工作区类型：
 * - FORMAL：正式项目绑定
 * - PERSONAL：个人草稿
 * - TEMPORARY：临时试用（带 retention_days 自动清理）
 */

export type WorkspaceType = 'FORMAL' | 'PERSONAL' | 'TEMPORARY';

/** 工作区：UUID + 类型 + 名称 + 关联项目 ID + 拥有者 ID + 创建/最近活跃时间 + 保留天数（仅 TEMPORARY）。 */
export interface Workspace {
  workspace_id: string;
  workspace_type: WorkspaceType;
  name: string;
  project_id: string | null;
  owner_id: string | null;
  created_at: string;
  last_active_at: string | null;
  retention_days: number | null;
}

/** 创建工作区请求：类型 + 名称 + 可选项目 ID + 可选保留天数。 */
export interface WorkspaceCreate {
  workspace_type: WorkspaceType;
  name: string;
  project_id?: string | null;
  retention_days?: number | null;
}

/** 工作区导入响应：UUID + 是否成功 + 导入记录数。 */
export interface WorkspaceImportResponse {
  workspace_id: string;
  imported: boolean;
  record_count: number;
}