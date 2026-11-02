/**
 * 交付物读面客户端 —— P9B-2 · SPEC §6.24 / §7.19。
 *
 * ⚠️ `progress` 打的是**聚合端点** `GET /deliverables/{id}/progress`
 * （TODO-065），**不是** `GET /workflow-progress/SIGN/{version_id}` ——
 * 两类工作流的 `workflow_id` 语义各不相同（SIGN = 版本 id，
 * CUSTOMER_APPROVAL_PROXY = **交付物 id**），关联规则归后端（R-2 / R-13）。
 */
import { api } from './client';
import type { components } from '../types/api';
import type { WorkflowType } from '../components/common/workflowTabs';

export type DeliverableProgressResponse = Omit<
  components['schemas']['DeliverableProgressResponse'],
  'sections'
> & { sections: WorkflowProgressSection[] };

/**
 * 交付物签审 4 态 —— **契约派生**（评审 #6）。
 *
 * ⚠️ 此前是**手写**的 union（`'DRAFT' | 'PENDING' | ...`），而后端把该字段
 * 声明成裸 `str` ⇒ 契约里**没有词表** ⇒ 任何漂移检查都抓不到回归，
 * 而前端这份手写词表与后端**完全脱钩**（bug-2040 记的那类漂移根因：
 * 「响应体取契约类型；手写自由 dict 是根因」）。
 *
 * ⇒ 后端 schema 改成 `DeliverableSignStatus` 枚举后，契约里带 `enum` 词表
 * ⇒ 这里直接取契约类型，**不再手写**。
 */
export type DeliverableSignStatus = components['schemas']['DeliverableSignStatus'];

/** 列表/详情行（`sign_status` 的词表由契约给 ⇒ 整个行类型直接用契约）。 */
export type Deliverable = components['schemas']['DeliverableResponse'];
/**
 * ⚠️ 评审 #20：契约把 `workflow_type` 生成为裸 `string`，后端实际返回的是
 * `WorkflowType` 三值枚举 ⇒ 在 **api 边界**收窄（消费方不再 `as never`）。
 */
export type WorkflowProgressSection = Omit<
  components['schemas']['WorkflowProgressSection'],
  'workflow_type'
> & { workflow_type: WorkflowType };
export type DeliverableActionsListResponse =
  components['schemas']['DeliverableActionsListResponse'];

// === P9B-2 · T8：交付物级签署**写面** ===
export type DeliverableIssueRequest = components['schemas']['DeliverableIssueRequest'];
export type SignStepRequest = components['schemas']['SignStepRequest'];
export type CustomerApprovalProxyRequest =
  components['schemas']['CustomerApprovalProxyRequest'];
export type DeliverableIssueResult = components['schemas']['DeliverableIssueResponse'];
export type SignStepResult = components['schemas']['SignStepResponse'];
export type CustomerApprovalProxyResult =
  components['schemas']['CustomerApprovalProxyResponse'];
export type DeliverableSnapshotResponse =
  components['schemas']['DeliverableSnapshotResponse'];

/** 版本目的 13 值（后端 `VersionPurpose` Literal · 合并数据字典）。 */
export type VersionPurpose = DeliverableIssueRequest['version_purpose'];

/**
 * ⚠️ **运行期**词表（生成的类型只能在编译期用）⇒ 值取自后端 Literal，
 * `satisfies` 让**编译期**校对它仍是合法取值（打错 ⇒ 编译不过）。
 */
export const VERSION_PURPOSES = [
  'INTER_DISCIPLINE_CHECK',
  'INTERNAL_REVIEW',
  'CUSTOMER_REVIEW',
  'RE_CUSTOMER_REVIEW',
  'ISSUED_FOR_DESIGN',
  'ISSUED_FOR_PURCHASE',
  'ISSUED_FOR_CONSTRUCTION',
  'ISSUED_FOR_USE',
  'ISSUED_FOR_BID',
  'ISSUED_FOR_CHANGE',
  'AS_BUILT',
  'INFORMATION_ONLY',
  'VOID',
] as const satisfies readonly VersionPurpose[];

/** 签署决策 3 值（后端 `SignDecision` Literal）。 */
export const SIGN_DECISIONS = ['SIGN', 'RETURN', 'SKIP'] as const;

/** 客户批准方式 4 值（后端 `CustomerApprovalMethod` Literal · ADR-0007）。 */
export const CUSTOMER_APPROVAL_METHODS = [
  'EMAIL',
  'LETTER',
  'EDMS',
  'SIGNED_DOC',
] as const;

/** 凭证附件类型 4 值（后端 `CredentialFileType` Literal）。 */
export const CREDENTIAL_FILE_TYPES = ['PDF', 'JPG', 'PNG', 'EML'] as const;

export const deliverablesApi = {
  progress: (deliverableId: string): Promise<DeliverableProgressResponse> =>
    api
      .get<DeliverableProgressResponse>(`/deliverables/${deliverableId}/progress`)
      .then((r) => r.data),

  actions: (
    deliverableId: string,
    params?: { limit?: number; offset?: number },
  ): Promise<DeliverableActionsListResponse> =>
    api
      .get<DeliverableActionsListResponse>(`/deliverables/${deliverableId}/actions`, {
        params,
      })
      .then((r) => r.data),

  /**
   * 取某 Rev 的快照（含**版本冻结的签署步骤**）。
   *
   * ⚠️ 前端算「下一步该谁签」必须用**版本快照**（`signature_summary_json.steps`），
   * **不是**活矩阵 —— 后端 `_steps_for_version` 读的也是快照（bug-2063：
   * 模板中途改小会把在飞版本永久卡在 PENDING）⇒ 两端**同源**。
   */
  versionSnapshot: (
    deliverableId: string,
    rev: string,
  ): Promise<DeliverableSnapshotResponse> =>
    api
      .get<DeliverableSnapshotResponse>(
        `/deliverables/${deliverableId}/versions/${rev}/snapshot`,
      )
      .then((r) => r.data),

  /** 签发（送审）：建版本行 + 定 doc_no + DRAFT → PENDING。 */
  issue: (
    deliverableId: string,
    body: DeliverableIssueRequest,
  ): Promise<DeliverableIssueResult> =>
    api
      .post<DeliverableIssueResult>(`/deliverables/${deliverableId}/issue`, body)
      .then((r) => r.data),

  /** 推进签署矩阵的一步（签 / 退 / 跳）。 */
  signStep: (
    deliverableId: string,
    body: SignStepRequest,
  ): Promise<SignStepResult> =>
    api
      .post<SignStepResult>(`/deliverables/${deliverableId}/sign-step`, body)
      .then((r) => r.data),

  /** 代录客户在系统外的批准（凭证 + 二次认证）。 */
  customerApprovalProxy: (
    deliverableId: string,
    body: CustomerApprovalProxyRequest,
  ): Promise<CustomerApprovalProxyResult> =>
    api
      .post<CustomerApprovalProxyResult>(
        `/deliverables/${deliverableId}/customer-approval/proxy`,
        body,
      )
      .then((r) => r.data),
};
