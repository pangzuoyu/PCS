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