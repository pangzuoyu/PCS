export type RecordSignStatus =
  | 'DRAFT'
  | 'IN_APPROVAL'
  | 'CHECKED'
  | 'CHECK_REJECTED'
  | 'STALE'
  | 'CHANGE_PENDING'
  | 'CHANGED'
  | 'REVERSAL_PENDING'
  | 'OBSOLETE';

export type StateTransitionName =
  | 'SUBMIT_FOR_CHECK'
  | 'PASS_CHECK'
  | 'REJECT_CHECK'
  | 'REQUEST_REVERSAL'
  | 'APPROVE_REVERSAL'
  | 'REJECT_REVERSAL'
  | 'CONFIRM_CHANGE_PENDING'
  | 'APPLY_CHANGE'
  | 'ABANDON_CHANGE'
  | 'MARK_STALE'
  | 'RESOLVE_STALE_NO_CHANGE'
  | 'RESOLVE_STALE_CHANGED'
  | 'OBSOLETE';

export interface RecordTransitionRequest {
  transition: StateTransitionName;
  reason?: string | null;
}

export interface RecordResponse {
  pipe_id?: string;
  record_id?: string;
  sign_status: RecordSignStatus;
  approval_step?: number | null;
  locked_by_deliverable?: boolean;
}