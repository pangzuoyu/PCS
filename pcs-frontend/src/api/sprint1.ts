import { api } from './client';
import type {
  ChecklistCompleteness,
  ChecklistItem,
  ChecklistItemCreate,
  ChecklistItemPut,
} from '../types/checklist';
import type {
  Workspace,
  WorkspaceCreate,
  WorkspaceImportResponse,
} from '../types/workspace';

export const workspaceApi = {
  list: (ownerId?: string) =>
    api.get<Workspace[]>('/workspaces', { params: ownerId ? { owner_id: ownerId } : {} }).then((r) => r.data),
  create: (ownerId: string, body: WorkspaceCreate) =>
    api
      .post<Workspace>('/workspaces', body, { params: { owner_id: ownerId } })
      .then((r) => r.data),
  get: (workspaceId: string) =>
    api.get<Workspace>(`/workspaces/${workspaceId}`).then((r) => r.data),
  import: (userId: string, workspaceId: string, projectId: string) =>
    api
      .post<WorkspaceImportResponse>(
        '/workspaces/import',
        { workspace_id: workspaceId, project_id: projectId },
        { params: { user_id: userId } },
      )
      .then((r) => r.data),
};

export const checklistApi = {
  list: (projectId: string) =>
    api.get<ChecklistItem[]>(`/checklist/projects/${projectId}`).then((r) => r.data),
  completeness: (projectId: string) =>
    api
      .get<ChecklistCompleteness>(`/checklist/projects/${projectId}/completeness`)
      .then((r) => r.data),
  seed: (projectId: string, userId: string, items: ChecklistItemCreate[]) =>
    api
      .post<ChecklistItem[]>(
        `/checklist/projects/${projectId}/seed`,
        { items },
        { params: { user_id: userId } },
      )
      .then((r) => r.data),
  update: (checklistId: string, userId: string, payload: ChecklistItemPut) =>
    api
      .put<ChecklistItem>(
        `/checklist/items/${checklistId}`,
        payload,
        { params: { user_id: userId } },
      )
      .then((r) => r.data),
};