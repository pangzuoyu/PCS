/**
 * 签署流程 + ADMIN 的 MSW handlers（P9B-2 · T10）。
 *
 * ⚠️ 这些端点**全都在 OpenAPI 契约里** ⇒ mock 形状必须与契约一致 ⇒
 * 响应体取 `components['schemas'][...]`（bug-2040 的教训：mock 与真端点
 * 不同源 ⇒ 漂移被藏住 ⇒ 生产构建才炸）。
 *
 * ⚠️ **有状态**：签发 / 签署 / 代录 / 停用 / 批注都会**真的改**内存里的
 * 种子 ⇒ 页面上点「签发」后能看到版本变化 ⇒ 人工验收不会误判「按钮没用」。
 */
import { http, HttpResponse } from 'msw';

import type { components } from '../types/api';

import { bindRecordMatrix } from './signatureMatrices';

import {
  seedAdminUsers,
  seedDeliverableActions,
  seedDeliverableProgress,
  seedDeliverableSnapshot,
  seedRecordComments,
  seedRecordEdits,
} from './seed/signFlow';

type CommentResponse = components['schemas']['CommentResponse'];
type ProgressItem = components['schemas']['WorkflowProgressItemResponse'];
type ProgressSection = components['schemas']['WorkflowProgressSection'];
type DeliverableProgress = components['schemas']['DeliverableProgressResponse'];
type RecordActionResponse = components['schemas']['RecordActionResponse'];
type SubmitApprovalResponse = components['schemas']['SubmitApprovalResponse'];
type ApprovalStepResponse = components['schemas']['ApprovalStepResponse'];
type UserDisabledOut = components['schemas']['UserDisabledOut'];
type AdSyncResultOut = components['schemas']['AdSyncResultOut'];
type ProjectCreate = components['schemas']['ProjectCreate'];
type ProjectOut = components['schemas']['ProjectOut'];

function isAuthed(request: Request): boolean {
  return request.headers.get('Authorization') !== null;
}

/** 批注（内存态 —— 发一条就多一条）。 */
const comments = [...seedRecordComments.items];

/**
 * mock 的**可变**签署状态（模块级 ⇒ 跨请求保持 ⇒ dev 里点「签署」能看到进度变）。
 *
 * ⚠️ 语义**照抄后端** `DeliverableService.sign_step`：
 * ① 本步行终态（COMPLETED / FAILED / SKIPPED）；
 * ② **下一步**行 IN_PROGRESS（最后一步不写；RETURN 也不写）；
 * ③ 最后一步 SIGN ⇒ 交付物 APPROVED；RETURN ⇒ 交付物回 DRAFT（ADR-0008）。
 * ⚠️ **越步签 ⇒ 409** `SIGN_STEP_OUT_OF_ORDER`（矩阵的职责分离：复核人不能
 *    在设计人没签时先签复核）。
 */
let mockSignSteps: ProgressItem[] = [];
let mockDeliverableSignStatus = 'PENDING';

/** 重置 mock 的签署状态（测试之间隔离用；页面刷新不会重置）。 */
export function resetMockSignState(): void {
  mockSignSteps = (
    seedDeliverableProgress.sections.find((s) => s.workflow_type === 'SIGN')?.items ?? []
  ).map((i) => ({ ...i }));
  mockDeliverableSignStatus = 'PENDING';
}
resetMockSignState();

/** SIGN 段（按当前状态现算 —— 计数与后端同口径）。 */
function currentSignSection(): ProgressSection {
  const items = mockSignSteps;
  const count = (s: string) => items.filter((i) => i.step_status === s).length;
  return {
    workflow_type: 'SIGN',
    workflow_id: 'v-2',
    available: true,
    reason: null,
    total: items.length,
    pending: count('PENDING'),
    in_progress: count('IN_PROGRESS'),
    completed: count('COMPLETED'),
    skipped: count('SKIPPED'),
    failed: count('FAILED'),
    items,
  };
}

export const signFlowHandlers = [
  // === 项目创建（P9B-2 · T-1）—— **自动绑一份 ACTIVE 的 RECORD 矩阵** ===
  http.post('/api/v1/projects', async ({ request }) => {
    if (!isAuthed(request)) {
      return HttpResponse.json({ code: 'MISSING_BEARER' }, { status: 401 });
    }
    const body = (await request.json()) as Partial<ProjectCreate>;
    // ⚠️ **8 个必填字段全都要有**（后端 `ProjectCreate`）⇒ mock 少校验一个
    //    ⇒ dev 里「漏填业主」也能建出来 ⇒ 真后端 422 ⇒ dev 与生产不一致。
    const required = [
      'project_no',
      'project_name',
      'owner_company',
      'location',
      'project_type',
      'design_phase',
      'unit_system',
      'workspace_id',
    ] as const;
    const missing = required.filter((k) => !body[k]);
    if (missing.length > 0) {
      return HttpResponse.json(
        {
          code: 'VALIDATION_ERROR',
          message: `缺少必填字段：${missing.join(' / ')}`,
        },
        { status: 422 },
      );
    }
    const projectId = `p-${Date.now()}`;
    // ⚠️ 建项目 ⇒ **自动绑一份 RECORD 矩阵**（后端同事务）⇒ 建完当场能送审。
    bindRecordMatrix(projectId);
    const projectOut: ProjectOut = {
      project_id: projectId,
      project_no: body.project_no as string,
      project_name: body.project_name as string,
      project_type: body.project_type as string,
      product_category: body.product_category ?? 'OTHER',
      // ⚠️ 电折标口径是 `product_category` 的**派生态**（后端
      //    `derive_electricity_value_type`）⇒ REFINING / ETHYLENE 用等价值。
      electricity_value_type:
        body.product_category === 'REFINING' || body.product_category === 'ETHYLENE'
          ? 'AC_380V_EQUIVALENT'
          : 'AC_380V',
    };
    return HttpResponse.json(projectOut, { status: 201 });
  }),

  // === 交付物：聚合进度（TODO-065）===
  http.get('/api/v1/deliverables/:deliverable_id/progress', ({ request }) => {
    if (!isAuthed(request)) {
      return HttpResponse.json({ code: 'MISSING_BEARER' }, { status: 401 });
    }
    // ⚠️ SIGN 段**现算**（签过之后状态要变 ⇒ 否则 dev 里「点了没反应」）。
    const proxy = seedDeliverableProgress.sections.find(
      (s) => s.workflow_type === 'CUSTOMER_APPROVAL_PROXY',
    );
    const body: DeliverableProgress = {
      deliverable_id: seedDeliverableProgress.deliverable_id,
      sections: [currentSignSection(), ...(proxy ? [proxy] : [])],
    };
    return HttpResponse.json(body);
  }),

  // === 交付物：动作时间线（审计，**不是**观测层）===
  http.get('/api/v1/deliverables/:deliverable_id/actions', ({ request }) => {
    if (!isAuthed(request)) {
      return HttpResponse.json({ code: 'MISSING_BEARER' }, { status: 401 });
    }
    return HttpResponse.json(seedDeliverableActions);
  }),

  // === 交付物：版本快照（含**冻结的签署步骤**）===
  http.get('/api/v1/deliverables/:deliverable_id/versions/:rev/snapshot', ({ request }) => {
    if (!isAuthed(request)) {
      return HttpResponse.json({ code: 'MISSING_BEARER' }, { status: 401 });
    }
    return HttpResponse.json(seedDeliverableSnapshot);
  }),

  // === 交付物：签发 ===
  http.post('/api/v1/deliverables/:deliverable_id/issue', async ({ request, params }) => {
    if (!isAuthed(request)) {
      return HttpResponse.json({ code: 'MISSING_BEARER' }, { status: 401 });
    }
    const body = (await request.json()) as { version_purpose?: string; description?: string };
    if (!body.version_purpose) {
      return HttpResponse.json(
        { code: 'VALIDATION_ERROR', message: 'version_purpose 必填' },
        { status: 422 },
      );
    }
    return HttpResponse.json({
      deliverable_id: String(params['deliverable_id']),
      version_id: `v-${Date.now()}`,
      rev: 'C',
      doc_no: 'CB-002',
      version_purpose: body.version_purpose,
      sign_status: 'PENDING',
      issued_at: new Date().toISOString(),
    });
  }),

  // === 交付物：推进签署的一步 ===
  http.post('/api/v1/deliverables/:deliverable_id/sign-step', async ({ request, params }) => {
    if (!isAuthed(request)) {
      return HttpResponse.json({ code: 'MISSING_BEARER' }, { status: 401 });
    }
    const body = (await request.json()) as {
      version_id?: string;
      step_index?: number;
      decision?: string;
      reason?: string;
    };
    const stepIndex = body.step_index ?? 1;
    const decision = body.decision ?? 'SIGN';
    const step = mockSignSteps[stepIndex - 1];
    if (!step) {
      return HttpResponse.json(
        {
          code: 'SIGN_STEP_NOT_FOUND',
          message: `签署矩阵只有 ${mockSignSteps.length} 步，第 ${stepIndex} 步不存在`,
        },
        { status: 404 },
      );
    }
    // ⚠️ **越步签 ⇒ 409**（后端 `_assert_step_order`）：只能顺序推进。
    if (step.step_status !== 'IN_PROGRESS') {
      return HttpResponse.json(
        {
          code: 'SIGN_STEP_OUT_OF_ORDER',
          message: `第 ${stepIndex} 步当前是 ${step.step_status}，不是待签状态`,
        },
        { status: 409 },
      );
    }
    // ⚠️ 评审 B-1：**矩阵未允许跳过 ⇒ 409**（后端同码 `SIGN_STEP_SKIP_FORBIDDEN`）。
    //    与后端**同源**：读的是版本快照里**冻结的矩阵步骤**
    //    （`seedDeliverableSnapshot.signature_summary_json.steps`，对应后端
    //    `_steps_for_version`）⇒ dev 的「跳过」分支与生产同响。
    const frozenSteps = (
      seedDeliverableSnapshot.signature_summary_json as
        | { steps?: { can_skip?: boolean }[] }
        | undefined
    )?.steps;
    const frozenStep = frozenSteps?.[stepIndex - 1];
    if (decision === 'SKIP' && frozenStep && frozenStep.can_skip === false) {
      return HttpResponse.json(
        {
          code: 'SIGN_STEP_SKIP_FORBIDDEN',
          message: `签署矩阵未允许跳过第 ${stepIndex} 步（can_skip=false）`,
        },
        { status: 409 },
      );
    }
    // ⚠️ 评审 B-1 已知边界：sign_role 403 / can_self_check 403 在 dev mock 里
    //    **不可复现** —— mock 的 token 是固定共享串（MOCK_TOKEN），请求侧没有
    //    角色身份可判（前端 UI 门禁已挡这两个分支；后端 403 由
    //    test_deliverable_sign_step.py 30 条真单测覆盖）。
    const now = new Date().toISOString();
    const state = decision === 'SIGN' ? 'COMPLETED' : decision === 'RETURN' ? 'FAILED' : 'SKIPPED';
    step.step_status = state;
    step.completed_at = now;
    const next = mockSignSteps[stepIndex];
    if (next && decision !== 'RETURN') {
      next.step_status = 'IN_PROGRESS';
      next.started_at = now;
    }
    // ⚠️ 最后一步 SIGN ⇒ APPROVED；RETURN ⇒ 回 DRAFT（ADR-0008）。
    if (decision === 'RETURN') {
      mockDeliverableSignStatus = 'DRAFT';
    } else if (!next) {
      mockDeliverableSignStatus = 'APPROVED';
    }
    return HttpResponse.json({
      deliverable_id: String(params['deliverable_id']),
      version_id: body.version_id ?? 'v-2',
      step_index: stepIndex,
      step_role: step.step_role,
      decision,
      state,
      deliverable_sign_status: mockDeliverableSignStatus,
      signed_at: now,
    });
  }),

  // === 交付物：代录客户批准 ===
  http.post(
    '/api/v1/deliverables/:deliverable_id/customer-approval/proxy',
    async ({ request, params }) => {
      if (!isAuthed(request)) {
        return HttpResponse.json({ code: 'MISSING_BEARER' }, { status: 401 });
      }
      const body = (await request.json()) as {
        version_id?: string;
        approver_name?: string;
        approval_date?: string;
        approval_method?: string;
      };
      return HttpResponse.json({
        deliverable_id: String(params['deliverable_id']),
        version_id: body.version_id ?? 'v-2',
        attachment_id: 'att-1',
        customer_approver_name: body.approver_name ?? '',
        approval_date: body.approval_date ?? '2026-10-20',
        approval_method: body.approval_method ?? 'EMAIL',
        is_proxy: true,
        proxied_at: new Date().toISOString(),
      });
    },
  ),

  // === 记录：编辑历史（TODO-066）===
  http.get('/api/v1/records/:module/:record_id/edits', ({ request, params }) => {
    if (!isAuthed(request)) {
      return HttpResponse.json({ code: 'MISSING_BEARER' }, { status: 401 });
    }
    return HttpResponse.json({
      ...seedRecordEdits,
      record_type: String(params['module']),
      record_id: String(params['record_id']),
    });
  }),

  // === 记录：批注 ===
  http.get('/api/v1/records/:module/:record_id/comments', ({ request }) => {
    if (!isAuthed(request)) {
      return HttpResponse.json({ code: 'MISSING_BEARER' }, { status: 401 });
    }
    const url = new URL(request.url);
    const limit = Number(url.searchParams.get('limit') ?? '20');
    const offset = Number(url.searchParams.get('offset') ?? '0');
    return HttpResponse.json({
      items: comments.slice(offset, offset + limit),
      total: comments.length,
    });
  }),

  http.post('/api/v1/records/:module/:record_id/comments', async ({ request, params }) => {
    if (!isAuthed(request)) {
      return HttpResponse.json({ code: 'MISSING_BEARER' }, { status: 401 });
    }
    const body = (await request.json()) as { body?: string };
    const created: CommentResponse = {
      comment_id: `c-${comments.length + 1}`,
      record_type: String(params['module']),
      record_id: String(params['record_id']),
      body: body.body ?? '',
      author_id: 'alice',
      created_at: new Date().toISOString(),
    };
    comments.push(created);
    return HttpResponse.json(created, { status: 201 });
  }),

  // === 记录：写动作（统一结果形状）===
  ...(
    [
      'obsolete',
      'request-reversal',
      'reversal-decision',
      'initiate-change',
      'apply-change',
      'abandon-change',
    ] as const
  ).map((action) =>
    http.post(`/api/v1/records/:module/:record_id/${action}`, ({ request, params }) => {
      if (!isAuthed(request)) {
        return HttpResponse.json({ code: 'MISSING_BEARER' }, { status: 401 });
      }
      const body: RecordActionResponse = {
        record_type: String(params['module']),
        record_id: String(params['record_id']),
        from_status: 'DRAFT',
        to_status: action === 'obsolete' ? 'OBSOLETE' : 'CHANGE_PENDING',
      };
      return HttpResponse.json(body);
    }),
  ),

  // === 记录：送审（R-17：批准链从项目矩阵推导 ⇒ 响应带链信息）===
  http.post('/api/v1/records/:module/:record_id/submit-approval', ({ request, params }) => {
    if (!isAuthed(request)) {
      return HttpResponse.json({ code: 'MISSING_BEARER' }, { status: 401 });
    }
    const body: SubmitApprovalResponse = {
      record_type: String(params['module']),
      record_id: String(params['record_id']),
      from_status: 'DRAFT',
      to_status: 'IN_APPROVAL',
      approval_step: 1,
      approval_depth: 2,
      approval_role: 'CHECKER',
    };
    return HttpResponse.json(body);
  }),

  // === 记录：推进批准链的一步 ===
  http.post('/api/v1/records/:module/:record_id/approval-step', ({ request, params }) => {
    if (!isAuthed(request)) {
      return HttpResponse.json({ code: 'MISSING_BEARER' }, { status: 401 });
    }
    const body: ApprovalStepResponse = {
      record_type: String(params['module']),
      record_id: String(params['record_id']),
      from_status: 'IN_APPROVAL',
      to_status: 'IN_APPROVAL',
      approval_step: 2,
      approval_depth: 2,
    };
    return HttpResponse.json(body);
  }),

  // === ADMIN：用户列表 ===
  http.get('/api/v1/admin/users', ({ request }) => {
    if (!isAuthed(request)) {
      return HttpResponse.json({ code: 'MISSING_BEARER' }, { status: 401 });
    }
    return HttpResponse.json(seedAdminUsers);
  }),

  // === ADMIN：停用（回显新的 token_version）===
  http.put('/api/v1/admin/users/:user_id/disable', ({ request, params }) => {
    if (!isAuthed(request)) {
      return HttpResponse.json({ code: 'MISSING_BEARER' }, { status: 401 });
    }
    const userId = String(params['user_id']);
    const user = seedAdminUsers.find((u) => u.user_id === userId);
    if (!user) {
      return HttpResponse.json(
        { code: 'USER_NOT_FOUND', message: '用户不存在' },
        { status: 404 },
      );
    }
    user.status = 'DISABLED';
    user.token_version += 1;
    const body: UserDisabledOut = {
      user_id: user.user_id,
      username: user.username,
      status: user.status,
      token_version: user.token_version,
    };
    return HttpResponse.json(body);
  }),

  // === ADMIN：AD 同步 ===
  http.post('/api/v1/admin/users/sync', ({ request }) => {
    if (!isAuthed(request)) {
      return HttpResponse.json({ code: 'MISSING_BEARER' }, { status: 401 });
    }
    const body: AdSyncResultOut = {
      ok: true,
      created: 1,
      updated: 0,
      departed: 0,
      unmapped: 0,
      skipped_empty: false,
      error: null,
    };
    return HttpResponse.json(body);
  }),
];
