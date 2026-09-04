export type ChecklistStatus =
  | 'NOT_STARTED'
  | 'IN_PROGRESS'
  | 'VERIFIED'
  | 'ASSUMED'
  | 'NOT_APPLICABLE';

export type ChecklistCategory = 'REQUIRED' | 'CONDITIONAL' | 'OPTIONAL';

export interface ChecklistItem {
  checklist_id: string;
  project_id: string;
  item_key: string;
  item_label: string;
  module: string | null;
  input_category: ChecklistCategory | null;
  required: boolean;
  input_value_json: Record<string, unknown> | null;
  source_type: string | null;
  status: ChecklistStatus;
  verified_by: string | null;
  verified_at: string | null;
  assumption_reason: string | null;
  note: string | null;
}

export interface ChecklistItemPut {
  status: ChecklistStatus;
  input_value_json?: Record<string, unknown> | null;
  source_type?: string | null;
  assumption_reason?: string | null;
}

export interface ChecklistItemCreate {
  item_key: string;
  item_label: string;
  module?: string | null;
  input_category?: ChecklistCategory;
  required?: boolean;
  note?: string | null;
}

export interface ChecklistCompleteness {
  project_id: string;
  total: number;
  required_total: number;
  required_verified: number;
  required_assumed: number;
  required_blocked: number;
  completeness_pct: number;
}