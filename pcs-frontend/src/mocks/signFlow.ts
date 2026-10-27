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

import {
  seedAdminUsers,
  seedDeliverableActions,
  seedDeliverableProgress,
  seedDeliverableSnapshot,
  seedRecordComments,
  seedRecordEdits,
} from './seed/signFlow';

type CommentResponse = components['schemas']['CommentResponse'];
type RecordActionResponse = components['schemas']['RecordActionResponse'];
type SubmitApprovalResponse = components['schemas']['SubmitApprovalResponse'];
type ApprovalStepResponse = components['schemas']['ApprovalStepResponse'];
type UserDisabledOut = components['schemas']['UserDisabledOut'];
type AdSyncResultOut = components['schemas']['AdSyncResultOut'];

function isAuthed(request: Request): boolean {
  return request.headers.get('Authorization') !== null;
}

/** 批注（内存态 —— 发一条就多一条）。 */
const comments = [...seedRecordComments.items];

export const signFlowHandlers = [
  // === 项目创建（P9B-2 · T-1）—— **自动绑一份 ACTIVE 的 RECORD 矩阵** ===
  http.post('/api/v1/projects', async ({ request }) => {
    if (!isAuthed(request)) {
      return HttpResponse.json({ code: 'MISSING_BEARER' }, { status: 401 });
    }
    const body = (await request.json()) as { project_no?: string; project_name?: string };
    if (!body.project_no || !body.project_name) {
      return HttpResponse.json(
        { code: 'VALIDATION_ERROR', message: 'project_no / project_name 必填' },
        { status: 422 },
      );
    }
    return HttpResponse.json(
      {
        project_id: `p-${Date.now()}`,
        project_no: body.project_no,
        project_name: body.project_name,
        project_type: 'ENGINEERING',
        product_category: 'OTHER',
        electricity_value_type: 'AC_380V',
      },
      { status: 201 },
    );
  }),

  // === 交付物：聚合进度（TODO-065）===
  http.get('/api/v1/deliverables/:deliverable_id/progress', ({ request }) => {
    if (!isAuthed(request)) {
      return HttpResponse.json({ code: 'MISSING_BEARER' }, { status: 401 });
    }
    return HttpResponse.json(seedDeliverableProgress);
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
    return HttpResponse.json({
      deliverable_id: String(params['deliverable_id']),
      version_id: body.version_id ?? 'v-2',
      step_index: stepIndex,
      step_role: stepIndex === 1 ? 'CHECKER' : 'REVIEWER',
      decision,
      state: decision === 'SIGN' ? 'COMPLETED' : decision === 'RETURN' ? 'FAILED' : 'SKIPPED',
      deliverable_sign_status: decision === 'SIGN' ? 'PENDING' : 'DRAFT',
      signed_at: new Date().toISOString(),
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
