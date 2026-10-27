/**
 * 签署流程 + ADMIN 的 seed（P9B-2 · T10）。
 *
 * ⚠️ 响应体一律取**契约类型**（`satisfies components['schemas'][...]`）——
 * 手写自由 dict 就是 bug-2040 的根源（mock 与真端点不同源 ⇒ 漂移被藏住）。
 *
 * ⚠️ **不要在这里造「前端合成的形状」** —— 契约里没有的层就是 bug-189 的
 * 形态（`payload.stream` 那种）。
 */
import type { components } from '../../types/api';

type DeliverableProgress = components['schemas']['DeliverableProgressResponse'];
type DeliverableActions = components['schemas']['DeliverableActionsListResponse'];
type DeliverableSnapshot = components['schemas']['DeliverableSnapshotResponse'];
type RecordEdits = components['schemas']['RecordEditsResponse'];
type CommentList = components['schemas']['CommentListResponse'];
type AdminUser = components['schemas']['AdminUserOut'];

const PROJECT_ID = '00000000-0000-0000-0000-000000000001';

/**
 * 交付物的**聚合**进度（TODO-065 · R-13）。
 *
 * ⚠️ 两段：SIGN（`workflow_id` = **版本 id**）+
 * CUSTOMER_APPROVAL_PROXY（`workflow_id` = **交付物 id**）。
 * ⚠️ **没有 CHANGE_NOTICE 段**（R-13）—— 变更单本身就是交付物。
 */
export const seedDeliverableProgress: DeliverableProgress = {
  deliverable_id: 'd-2',
  sections: [
    {
      workflow_type: 'SIGN',
      workflow_id: 'v-2',
      available: true,
      reason: null,
      // ⚠️ **第 1 步是当前该签的那一步**（IN_PROGRESS）——
      //    「下一步」= 第一个**没有**终态（COMPLETED / SKIPPED）的步骤
      //    ⇒ 前端算出来的下一步 = 第 1 步（CHECKER）⇒ dev 里用 bob(CHECKER)
      //    登录就能真的签下去（e2e 断言「步骤推进」）。
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
          step_role: 'CHECKER',
          step_status: 'IN_PROGRESS',
          started_at: '2026-10-20T10:00:00Z',
          completed_at: null,
          assignee: 'bob',
          result_hash: null,
        },
        {
          progress_id: 'p-2',
          step_order: 2,
          step_role: 'REVIEWER',
          step_status: 'PENDING',
          started_at: null,
          completed_at: null,
          assignee: null,
          result_hash: null,
        },
      ],
    },
    {
      // ⚠️ **代录段恒为 available**（后端 `progress_sections`：PROXY 段的
      //    workflow_id = **交付物 id** ⇒ 永远可解析）⇒ 「尚未签发版本，无签署
      //    流程」是 **SIGN 段**（且只在**没有版本**时）的不可用原因 ⇒ 挂错段了。
      workflow_type: 'CUSTOMER_APPROVAL_PROXY',
      workflow_id: 'd-2',
      available: true,
      reason: null,
      total: 0,
      pending: 0,
      in_progress: 0,
      completed: 0,
      skipped: 0,
      failed: 0,
      items: [],
    },
  ],
};

/** 交付物动作时间线（数据源 = 审计，**不是**观测层）。 */
export const seedDeliverableActions: DeliverableActions = {
  deliverable_id: 'd-2',
  items: [
    {
      action: 'DELIVERABLE_ISSUED',
      resource_type: 'deliverable',
      resource_id: 'd-2',
      actor_user_id: 'alice',
      detail_json: '{"rev":"2","version_purpose":"ISSUED_FOR_CONSTRUCTION"}',
      created_at: '2026-10-20T10:00:00Z',
    },
  ],
  total: 1,
};

/** 版本快照（**含冻结的签署步骤** —— 前端算「下一步」就靠它）。 */
export const seedDeliverableSnapshot: DeliverableSnapshot = {
  deliverable_id: 'd-2',
  rev: 'B',
  version_purpose: 'ISSUED_FOR_CONSTRUCTION',
  description: '第 2 版',
  doc_no: 'CB-002',
  sign_status: 'PENDING',
  record_snapshot_json: { record_count: 0 },
  signature_summary_json: {
    matrix_id: 'm-2',
    steps: [
      {
        step_order: 1,
        sign_role: 'CHECKER',
        required: true,
        can_self_check: true,
        can_skip: false,
      },
      {
        step_order: 2,
        sign_role: 'REVIEWER',
        required: true,
        can_self_check: true,
        can_skip: false,
      },
    ],
    signatures: [],
  },
  bindings: [],
};

/** 记录编辑历史（TODO-066 · 按项目守卫的读端点）。 */
export const seedRecordEdits: RecordEdits = {
  record_type: 'cooling_tower_result',
  record_id: 'r-1',
  items: [
    {
      audit_id: 'a-1',
      changed_fields: ['duty_kw'],
      overwrote_stale_baseline: false,
      user_id: 'alice',
      occurred_at: '2026-10-20T10:00:00Z',
    },
  ],
  total: 1,
};

/** 记录批注。 */
export const seedRecordComments: CommentList = {
  items: [
    {
      comment_id: 'c-1',
      record_type: 'cooling_tower_result',
      record_id: 'r-1',
      body: '冷却水量取 50 m3/h 是否含补水？',
      author_id: 'bob',
      created_at: '2026-10-20T11:00:00Z',
    },
  ],
  total: 1,
};

/** ADMIN 用户列表（P9A-ADM-001）。 */
export const seedAdminUsers: AdminUser[] = [
  {
    user_id: 'u-1',
    username: 'alice',
    display_name: '爱丽丝',
    email: 'alice@example.com',
    department: '工艺',
    roles: ['DESIGNER'],
    status: 'ACTIVE',
    token_version: 3,
    last_login_at: '2026-10-20T09:00:00Z',
  },
  {
    user_id: 'u-2',
    username: 'bob',
    display_name: '鲍勃',
    email: 'bob@example.com',
    department: '校核',
    roles: ['CHECKER'],
    status: 'ACTIVE',
    token_version: 1,
    last_login_at: '2026-10-20T08:00:00Z',
  },
];

export const MOCK_PROJECT_ID = PROJECT_ID;
