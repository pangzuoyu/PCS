/**
 * Workspace 类型定义（V1 极简版）。
 *
 * 三种工作区类型：
 * - FORMAL：正式项目绑定
 * - PERSONAL：个人草稿
 * - TEMPORARY：临时试用（带 retention_days 自动清理）
 */

export type WorkspaceType = 'FORMAL' | 'PERSONAL' | 'TEMPORARY';

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

export interface WorkspaceCreate {
  workspace_type: WorkspaceType;
  name: string;
  project_id?: string | null;
  retention_days?: number | null;
}

export interface WorkspaceImportResponse {
  workspace_id: string;
  imported: boolean;
  record_count: number;
}