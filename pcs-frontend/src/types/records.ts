/**
 * 记录签收状态机 + 状态转移类型定义（V1 极简版）。
 *
 * 9 态签收状态机（RecordSignStatus）：
 * DRAFT / IN_APPROVAL / CHECKED / CHECK_REJECTED / STALE /
 * CHANGE_PENDING / CHANGED / REVERSAL_PENDING / OBSOLETE
 *
 * 状态转移枚举（StateTransitionName）：13 种合法转移名
 * —— SUBMIT_FOR_CHECK / PASS_CHECK / REJECT_CHECK / REQUEST_REVERSAL /
 * APPROVE_REVERSAL / REJECT_REVERSAL / CONFIRM_CHANGE_PENDING /
 * APPLY_CHANGE / ABANDON_CHANGE / MARK_STALE /
 * RESOLVE_STALE_NO_CHANGE / RESOLVE_STALE_CHANGED / OBSOLETE
 */

/** 记录签收状态（9 态机）：DRAFT / IN_APPROVAL / CHECKED / CHECK_REJECTED / STALE / CHANGE_PENDING / CHANGED / REVERSAL_PENDING / OBSOLETE。 */
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

/** 状态转移名（13 种合法转移）：提交校核/通过/驳回 + 申请反审/批准/驳回 + 确认变更/应用/放弃 + 标记陈旧/陈旧无变更/陈旧已变更 + 废弃。 */
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

/** 记录状态转移请求：转移名 + 可选原因。 */
export interface RecordTransitionRequest {
  transition: StateTransitionName;
  reason?: string | null;
}

/** 记录响应：业务 ID（pipe_id 或 record_id，按记录类型区分）+ 当前签收状态 + 当前审批步 + 是否被可交付件锁定。 */
export interface RecordResponse {
  pipe_id?: string;
  record_id?: string;
  sign_status: RecordSignStatus;
  approval_step?: number | null;
  locked_by_deliverable?: boolean;
}
