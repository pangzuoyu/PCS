/**
 * 交付物的 seed（P9B-1 · SPEC §6.24 · 交付物进度页）。
 *
 * ⚠️ 响应体取**契约类型**（`satisfies components['schemas'][...]`）——
 * 手写自由 dict 就是 bug-2040 的根源（mock 与真端点不同源 ⇒ 漂移被藏住）。
 *
 * ⚠️ `current_version_id` 由 **T0** 新增（`DeliverableResponse`）⇒
 * SIGN 的 `workflow_id` 用它（**不是** rev 匹配 —— rev 是自由文本）。
 */
import type { components } from '../../types/api';

type Deliverable = components['schemas']['DeliverableResponse'];

const PROJECT_ID = '00000000-0000-0000-0000-000000000001';

export const seedDeliverables: Deliverable[] = [
  {
    deliverable_id: 'd-1',
    project_id: PROJECT_ID,
    deliverable_type: 'CALCULATION_BOOK',
    scope_type: 'PROJECT_ALL',
    scope_value: null,
    doc_no: 'CB-001',
    doc_no_mode: 'MANUAL',
    title: '泵计算书',
    current_rev: 'A',
    // ⚠️ 无版本 ⇒ 进度页空态 ①
    current_version_id: null,
    version_purpose: 'ISSUED_FOR_CONSTRUCTION',
    sign_status: 'DRAFT',
    matrix_id: null,
    parent_deliverable_id: null,
    customer_approval_date: null,
    customer_approver_name: null,
    created_at: '2026-10-20T10:00:00Z',
  },
  {
    deliverable_id: 'd-2',
    project_id: PROJECT_ID,
    deliverable_type: 'CALCULATION_BOOK',
    scope_type: 'PROJECT_ALL',
    scope_value: 'PUMP',
    doc_no: 'CB-002',
    doc_no_mode: 'MANUAL',
    title: '换热器计算书',
    current_rev: 'B',
    // ⚠️ SIGN 的 workflow_id = **版本 ID**
    current_version_id: 'v-2',
    version_purpose: 'ISSUED_FOR_CONSTRUCTION',
    sign_status: 'CHANGE_PENDING',
    matrix_id: null,
    parent_deliverable_id: null,
    customer_approval_date: null,
    customer_approver_name: null,
    created_at: '2026-10-20T10:00:00Z',
  },
];

/** 签署进度的 mock 响应（契约形状）。 */
export const seedWorkflowProgress = {
  workflow_type: 'SIGN',
  workflow_id: 'v-2',
  project_id: PROJECT_ID,
  total: 2,
  pending: 1,
  in_progress: 1,
  completed: 0,
  skipped: 0,
  failed: 0,
  items: [
    {
      progress_id: 'p-1',
      step_order: 1,
      step_role: 'DESIGNER',
      step_status: 'COMPLETED',
      started_at: '2026-10-20T10:00:00Z',
      completed_at: '2026-10-20T10:30:00Z',
      assignee: 'alice',
      result_hash: 'a3f9c21d8b7e6f50',
    },
    {
      progress_id: 'p-2',
      step_order: 2,
      step_role: 'CHECKER',
      step_status: 'IN_PROGRESS',
      started_at: '2026-10-20T11:00:00Z',
      completed_at: null,
      assignee: 'bob',
      result_hash: null,
    },
  ],
} satisfies components['schemas']['WorkflowProgressResponse'];
