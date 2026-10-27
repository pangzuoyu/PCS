/**
 * 记录级写面客户端（9 态动作 + 批注）—— P9B-2 · SPEC §6.3 / §7.19.1。
 *
 * ⚠️ **`{module}` 是 `RECORD_TYPE_REGISTRY` 的键**（`CostEstResult` /
 * `cooling_tower_result` …），**不是表名** —— 后端 `resolve_record_model`
 * 查的就是那个注册表，传错 ⇒ 422 `RECORD_MODULE_UNKNOWN`。
 * ⇒ 复用 `src/api/records.ts` 的 `EditableRecordType`，**不另起词表**。
 *
 * ⚠️ **请求体字段名逐字取后端 schema**（`decision` / `reason`）—— 中间层改名
 * ⇒ TS 不报错 ⇒ 后端 422（RF-13 同形坑）。
 */
import { api } from './client';
import type { components } from '../types/api';
import type { EditableRecordType } from './records';

export type RecordActionResponse = components['schemas']['RecordActionResponse'];
export type SubmitApprovalResponse = components['schemas']['SubmitApprovalResponse'];
export type ApprovalStepResponse = components['schemas']['ApprovalStepResponse'];
export type CommentResponse = components['schemas']['CommentResponse'];
export type CommentListResponse = components['schemas']['CommentListResponse'];

/**
 * 待批角色词表（7 值，后端 `ApprovalRole`）。
 *
 * ⚠️ **R-17 之后前端不再「选」角色** —— 批准链由后端从项目 `RECORD` 矩阵推导。
 * ⇒ 这个类型只用于**读**矩阵步骤的 `sign_role`（签署弹窗要显示
 * 「这一步该谁签」）⇒ **保留**，但**不再**有「选择器」。
 */
export type ApprovalRole =
  | 'DESIGNER'
  | 'CHECKER'
  | 'REVIEWER'
  | 'APPROVER'
  | 'SYSTEM_ADMIN'
  | 'PROCESS_CONTROLLER'
  | 'DATA_ADMIN';

export const recordActionsApi = {
  obsolete: (module: EditableRecordType, recordId: string, reason: string) =>
    api
      .post<RecordActionResponse>(`/records/${module}/${recordId}/obsolete`, { reason })
      .then((r) => r.data),

  requestReversal: (module: EditableRecordType, recordId: string, reason: string) =>
    api
      .post<RecordActionResponse>(`/records/${module}/${recordId}/request-reversal`, {
        reason,
      })
      .then((r) => r.data),

  reversalDecision: (
    module: EditableRecordType,
    recordId: string,
    decision: 'APPROVE' | 'REJECT',
    reason: string,
  ) =>
    api
      .post<RecordActionResponse>(`/records/${module}/${recordId}/reversal-decision`, {
        decision,
        reason,
      })
      .then((r) => r.data),

  // ⚠️ **R-17**：批准链由**后端**从项目绑定的 `module='RECORD'` 矩阵推导 ⇒
  //    前端**不再**传 `approval_role` / `approval_depth`（客户端说了不算）。
  submitApproval: (
    module: EditableRecordType,
    recordId: string,
    reason?: string,
  ) =>
    api
      .post<SubmitApprovalResponse>(`/records/${module}/${recordId}/submit-approval`, {
        reason,
      })
      .then((r) => r.data),

  approvalStep: (
    module: EditableRecordType,
    recordId: string,
    decision: 'PASS' | 'REJECT',
    reason: string,
  ) =>
    api
      .post<ApprovalStepResponse>(`/records/${module}/${recordId}/approval-step`, {
        decision,
        reason,
      })
      .then((r) => r.data),

  abandonChange: (module: EditableRecordType, recordId: string, reason: string) =>
    api
      .post<RecordActionResponse>(`/records/${module}/${recordId}/abandon-change`, {
        reason,
      })
      .then((r) => r.data),

  // ⚠️ **R-12**：变更类动作**也**在状态机事件表里（`INITIATE_CHANGE` /
  //    `APPLY_CHANGE`）⇒ meta 驱动的操作栏会**自动**包含它们 ⇒ 端点**都有**
  //    ⇒ 渲染成**可用**按钮（旧的 R-6「这三个按钮没有端点 ⇒ 禁用」已被推翻）。
  //    ⚠️ 「建变更单 / 作废变更单」**不是**状态机事件 ⇒ 不在这里（归
  //    `ChangeNoticeAction`）。
  initiateChange: (module: EditableRecordType, recordId: string, reason: string) =>
    api
      .post<RecordActionResponse>(`/records/${module}/${recordId}/initiate-change`, {
        reason,
      })
      .then((r) => r.data),

  applyChange: (module: EditableRecordType, recordId: string, reason: string) =>
    api
      .post<RecordActionResponse>(`/records/${module}/${recordId}/apply-change`, {
        reason,
      })
      .then((r) => r.data),
};

export const commentsApi = {
  list: (
    module: EditableRecordType,
    recordId: string,
    params?: { limit?: number; offset?: number },
  ) =>
    api
      .get<CommentListResponse>(`/records/${module}/${recordId}/comments`, { params })
      .then((r) => r.data),
  create: (module: EditableRecordType, recordId: string, body: string) =>
    api
      .post<CommentResponse>(`/records/${module}/${recordId}/comments`, { body })
      .then((r) => r.data),
};
