/**
 * 签署矩阵的 seed + MSW handlers（TODO-079 · P9A-DLV-011 T3 的前端）。
 *
 * ⚠️ 响应体一律取**契约类型**（`components['schemas'][...]`）——
 * 手写自由 dict 就是 bug-2040 的根源（mock 与真端点不同源 ⇒ 漂移被藏住）。
 *
 * ## 为什么这组 mock 是**有状态**的
 *
 * 页面上「新建矩阵 → 编辑步骤 → 绑定到项目 → 解绑」是一条**连贯操作**⇒
 * mock 若每次返回固定数据，用户点「保存」后**看不到任何变化** ⇒ 测试与
 * 人工验收都会误判「按钮没用」⇒ 这里维护一份**内存态**（create/update/bind
 * 真的改它）。
 *
 * ⚠️ 这是 **dev-only mock**（不进 OpenAPI drift 校验）—— 因为它带的
 * `/signature-matrices` 路径**已经在契约里**（P9A-DLV-011 交付）⇒ 真端点
 * 与 mock 的形状必须一致 ⇒ 形状取契约类型。
 */
import { http, HttpResponse } from 'msw';

import type { components } from '../types/api';

type SignatureMatrix = components['schemas']['SignatureMatrixResponse'];
type MatrixStepInput = components['schemas']['MatrixStepInput'];

const PROJECT_ID = '00000000-0000-0000-0000-000000000001';

export const seedSignatureMatrices: SignatureMatrix[] = [
  {
    matrix_id: 'm-1',
    matrix_name: '变更单 3 级矩阵',
    module: 'CHANGE_NOTICE',
    doc_type: 'CHANGE_NOTICE',
    version_purpose: 'ISSUED_FOR_CHANGE',
    status: 'ACTIVE',
    steps: [
      { step_order: 1, sign_role: 'CHECKER', required: true, can_self_check: false, can_skip: false },
      { step_order: 2, sign_role: 'REVIEWER', required: true, can_self_check: false, can_skip: false },
      { step_order: 3, sign_role: 'APPROVER', required: true, can_self_check: false, can_skip: false },
    ],
    created_at: '2026-10-26T00:00:00Z',
    updated_at: '2026-10-26T00:00:00Z',
  },
  {
    matrix_id: 'm-2',
    matrix_name: '计算书 2 级矩阵',
    module: 'RECORD',
    doc_type: 'CALCULATION_BOOK',
    version_purpose: 'ISSUED_FOR_CONSTRUCTION',
    status: 'DRAFT',
    steps: [
      { step_order: 1, sign_role: 'CHECKER', required: true, can_self_check: true, can_skip: false },
      { step_order: 2, sign_role: 'APPROVER', required: true, can_self_check: false, can_skip: false },
    ],
    created_at: '2026-10-26T00:00:00Z',
    updated_at: '2026-10-26T00:00:00Z',
  },
];

/** 项目 × 模块 → 矩阵（换绑 = 改同一行）。 */
const bindings = new Map<string, string>([[`${PROJECT_ID}:RECORD`, 'm-2']]);

let counter = 100;

function isAuthed(request: Request): boolean {
  return request.headers.get('Authorization') !== null;
}

export const signatureMatrixHandlers = [
  http.get('/api/v1/signature-matrices', ({ request }) => {
    if (!isAuthed(request)) return HttpResponse.json({ code: 'MISSING_BEARER' }, { status: 401 });
    const url = new URL(request.url);
    const module = url.searchParams.get('module');
    const status = url.searchParams.get('status');
    const items = seedSignatureMatrices.filter(
      (m) => (module === null || m.module === module) && (status === null || m.status === status),
    );
    return HttpResponse.json({ items, total: items.length });
  }),

  http.get('/api/v1/signature-matrices/:matrix_id', ({ request, params }) => {
    if (!isAuthed(request)) return HttpResponse.json({ code: 'MISSING_BEARER' }, { status: 401 });
    const found = seedSignatureMatrices.find((m) => m.matrix_id === params['matrix_id']);
    if (!found) {
      return HttpResponse.json(
        { code: 'SIGNATURE_MATRIX_NOT_FOUND', message: '矩阵不存在' },
        { status: 404 },
      );
    }
    return HttpResponse.json(found);
  }),

  http.post('/api/v1/signature-matrices', async ({ request }) => {
    if (!isAuthed(request)) return HttpResponse.json({ code: 'MISSING_BEARER' }, { status: 401 });
    const body = (await request.json()) as {
      matrix_name: string;
      module: string;
      doc_type: string;
      version_purpose: string;
      status: string;
      steps: MatrixStepInput[];
    };
    // ⚠️ 与后端一致：任一步不合法 ⇒ 422，**不部分入库**
    if (!body.steps || body.steps.length === 0) {
      return HttpResponse.json(
        { code: 'SIGNATURE_MATRIX_INVALID', message: '矩阵至少要有一步' },
        { status: 422 },
      );
    }
    const created: SignatureMatrix = {
      matrix_id: `m-${counter++}`,
      matrix_name: body.matrix_name,
      module: body.module,
      doc_type: body.doc_type,
      version_purpose: body.version_purpose,
      status: body.status,
      steps: [...body.steps].sort((a, b) => a.step_order - b.step_order),
      created_at: '2026-10-26T00:00:00Z',
      updated_at: '2026-10-26T00:00:00Z',
    };
    seedSignatureMatrices.push(created);
    return HttpResponse.json(created, { status: 201 });
  }),

  http.put('/api/v1/signature-matrices/:matrix_id', async ({ request, params }) => {
    if (!isAuthed(request)) return HttpResponse.json({ code: 'MISSING_BEARER' }, { status: 401 });
    const found = seedSignatureMatrices.find((m) => m.matrix_id === params['matrix_id']);
    if (!found) {
      return HttpResponse.json(
        { code: 'SIGNATURE_MATRIX_NOT_FOUND', message: '矩阵不存在' },
        { status: 404 },
      );
    }
    const body = (await request.json()) as Partial<SignatureMatrix>;
    if (body.steps) {
      found.steps = [...body.steps].sort((a, b) => a.step_order - b.step_order);
    }
    if (body.matrix_name !== undefined) found.matrix_name = body.matrix_name;
    if (body.status !== undefined) found.status = body.status;
    found.updated_at = '2026-10-26T00:00:00Z';
    return HttpResponse.json(found);
  }),

  http.post('/api/v1/projects/:project_id/signature-matrices', async ({ request, params }) => {
    if (!isAuthed(request)) return HttpResponse.json({ code: 'MISSING_BEARER' }, { status: 401 });
    const body = (await request.json()) as { module: string; matrix_id: string };
    const matrix = seedSignatureMatrices.find((m) => m.matrix_id === body.matrix_id);
    if (!matrix) {
      return HttpResponse.json(
        { code: 'SIGNATURE_MATRIX_NOT_FOUND', message: '矩阵不存在' },
        { status: 404 },
      );
    }
    if (matrix.status !== 'ACTIVE') {
      return HttpResponse.json(
        {
          code: 'SIGNATURE_MATRIX_NOT_ACTIVE',
          message: `矩阵 ${matrix.matrix_name} 当前 ${matrix.status}，只有 ACTIVE 的矩阵可以绑定到项目`,
        },
        { status: 422 },
      );
    }
    const projectId = String(params['project_id']);
    bindings.set(`${projectId}:${body.module}`, matrix.matrix_id);
    return HttpResponse.json({
      project_id: projectId,
      module: body.module,
      matrix_id: matrix.matrix_id,
      matrix_name: matrix.matrix_name,
    });
  }),

  http.delete('/api/v1/projects/:project_id/signature-matrices/:module', ({ request, params }) => {
    if (!isAuthed(request)) return HttpResponse.json({ code: 'MISSING_BEARER' }, { status: 401 });
    const projectId = String(params['project_id']);
    const module = String(params['module']);
    const key = `${projectId}:${module}`;
    const unbound = bindings.delete(key);
    return HttpResponse.json({ project_id: projectId, module, unbound });
  }),
];
