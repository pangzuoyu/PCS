/**
 * 变更单闭环的 MSW handlers（TODO-083 · P9A-DLV-011 T4 的前端）。
 *
 * ## 为什么要 mock 这三个端点
 *
 * 结果记录页的「变更申请 / 提交变更完成 / 创建变更单」三个按钮要能**真的点得
 * 动**（人工验收 + 组件测试）⇒ 需要 3 个端点的 mock。
 *
 * ⚠️ 这三个端点**已在 OpenAPI 契约里**（P9A-DLV-011 交付）⇒ mock 的响应体
 * 取**契约类型**（`components['schemas'][...]`）⇒ 形状漂移会被 drift 校验抓住。
 *
 * ## 状态机必须在 mock 里**真的走**
 *
 * 三个端点是**一条链**：CHECKED → CHANGE_PENDING → CHANGED。
 * ⇒ mock 维护每个记录的状态；状态不对 ⇒ 返 409
 * `RECORD_INVALID_TRANSITION`（与后端一致）⇒ 前端的「按状态只给一个按钮」
 * 才有意义（否则测试里点按钮永远成功，测不出状态机）。
 */
import { http, HttpResponse } from 'msw';

import type { components } from '../types/api';

type RecordActionResponse = components['schemas']['RecordActionResponse'];
type ChangeNoticeResponse = components['schemas']['ChangeNoticeResponse'];
type ChangeNoticeOpenResponse = components['schemas']['ChangeNoticeOpenResponse'];
type ChangeNoticeCancelResponse = components['schemas']['ChangeNoticeCancelResponse'];

/** 记录主键 → 当前状态（mock 内存态）。 */
const statuses = new Map<string, string>();

/** 记录主键 → 已开着的变更单（mock 内存态；作废后删掉）。 */
const openNotices = new Map<string, ChangeNoticeOpenResponse>();

const PROJECT_ID = '00000000-0000-0000-0000-000000000001';

function isAuthed(request: Request): boolean {
  return request.headers.get('Authorization') !== null;
}

function currentStatus(recordType: string, recordId: string): string {
  return statuses.get(`${recordType}:${recordId}`) ?? 'CHECKED';
}

function action(
  recordType: string,
  recordId: string,
  from: string,
  to: string,
): RecordActionResponse {
  return { record_type: recordType, record_id: recordId, from_status: from, to_status: to };
}

export const changeNoticeHandlers = [
  http.post('/api/v1/records/:module/:record_id/initiate-change', async ({ request, params }) => {
    if (!isAuthed(request)) return HttpResponse.json({ code: 'MISSING_BEARER' }, { status: 401 });
    // ⚠️ 路径参数名与后端路由**逐字一致**（`{module}`）⇒
    // MSW 的 `:module` 才能和 OpenAPI 的 `{module}` 对上（drift 测试要比路径）
    const recordType = String(params['module']);
    const recordId = String(params['record_id']);
    const key = `${recordType}:${recordId}`;
    const from = currentStatus(recordType, recordId);
    if (from !== 'CHECKED') {
      return HttpResponse.json(
        { code: 'RECORD_INVALID_TRANSITION', message: `${from} 不能执行 INITIATE_CHANGE` },
        { status: 409 },
      );
    }
    statuses.set(key, 'CHANGE_PENDING');
    return HttpResponse.json(action(recordType, recordId, from, 'CHANGE_PENDING'));
  }),

  http.post('/api/v1/records/:module/:record_id/apply-change', async ({ request, params }) => {
    if (!isAuthed(request)) return HttpResponse.json({ code: 'MISSING_BEARER' }, { status: 401 });
    // ⚠️ 路径参数名与后端路由**逐字一致**（`{module}`）⇒
    // MSW 的 `:module` 才能和 OpenAPI 的 `{module}` 对上（drift 测试要比路径）
    const recordType = String(params['module']);
    const recordId = String(params['record_id']);
    const key = `${recordType}:${recordId}`;
    const from = currentStatus(recordType, recordId);
    if (from !== 'CHANGE_PENDING') {
      return HttpResponse.json(
        { code: 'RECORD_INVALID_TRANSITION', message: `${from} 不能执行 APPLY_CHANGE` },
        { status: 409 },
      );
    }
    statuses.set(key, 'CHANGED');
    return HttpResponse.json(action(recordType, recordId, from, 'CHANGED'));
  }),

  http.get('/api/v1/records/:module/:record_id/change-notice', async ({ request, params }) => {
    if (!isAuthed(request)) return HttpResponse.json({ code: 'MISSING_BEARER' }, { status: 401 });
    const recordType = String(params['module']);
    const recordId = String(params['record_id']);
    const existing = openNotices.get(`${recordType}:${recordId}`);
    if (existing) return HttpResponse.json(existing);
    const empty: ChangeNoticeOpenResponse = {
      record_type: recordType,
      record_id: recordId,
      has_open_notice: false,
      deliverable_id: null,
      version_id: null,
      doc_no: null,
      sign_status: null,
      title: null,
    };
    return HttpResponse.json(empty);
  }),

  http.post('/api/v1/records/:module/:record_id/change-notice/cancel', async ({ request, params }) => {
    if (!isAuthed(request)) return HttpResponse.json({ code: 'MISSING_BEARER' }, { status: 401 });
    const recordType = String(params['module']);
    const recordId = String(params['record_id']);
    const key = `${recordType}:${recordId}`;
    const existing = openNotices.get(key);
    if (!existing) {
      return HttpResponse.json(
        { code: 'CHANGE_NOTICE_NOT_FOUND', message: '该记录没有开着的变更单' },
        { status: 404 },
      );
    }
    const body = (await request.json()) as { reason: string };
    if (!body.reason || !body.reason.trim()) {
      return HttpResponse.json(
        { code: 'CHANGE_NOTICE_CANCEL_REASON_REQUIRED', message: '作废变更单必须填写理由' },
        { status: 422 },
      );
    }
    openNotices.delete(key);
    const cancelled: ChangeNoticeCancelResponse = {
      deliverable_id: existing.deliverable_id ?? '',
      doc_no: existing.doc_no ?? '',
      record_type: recordType,
      record_id: recordId,
      sign_status: 'OBSOLETE',
    };
    return HttpResponse.json(cancelled);
  }),

  http.post('/api/v1/records/:module/:record_id/change-notice', async ({ request, params }) => {
    if (!isAuthed(request)) return HttpResponse.json({ code: 'MISSING_BEARER' }, { status: 401 });
    // ⚠️ 路径参数名与后端路由**逐字一致**（`{module}`）⇒
    // MSW 的 `:module` 才能和 OpenAPI 的 `{module}` 对上（drift 测试要比路径）
    const recordType = String(params['module']);
    const recordId = String(params['record_id']);
    const from = currentStatus(recordType, recordId);
    if (from !== 'CHANGED') {
      return HttpResponse.json(
        { code: 'CHANGE_NOTICE_BAD_STATE', message: `记录当前 ${from}，建变更单要求 CHANGED` },
        { status: 422 },
      );
    }
    const body = (await request.json()) as { change_type: string; reason: string };
    const notice: ChangeNoticeResponse = {
      deliverable_id: `cn-${recordId}`,
      version_id: `cnv-${recordId}`,
      workflow_id: `cn-${recordId}`,
      matrix_id: 'm-1',
      project_id: PROJECT_ID,
      doc_no: `CN-${recordId.slice(0, 8).toUpperCase()}`,
      title: `${recordType} 变更单`,
      sign_status: 'PENDING',
      detail: {
        detail_id: `cnd-${recordId}`,
        change_type: body.change_type,
        reason: body.reason,
        triggered_by: 'MANUAL',
        source_record_type: recordType,
      },
    };
    const open: ChangeNoticeOpenResponse = {
      record_type: recordType,
      record_id: recordId,
      has_open_notice: true,
      deliverable_id: notice.deliverable_id,
      version_id: notice.version_id,
      doc_no: notice.doc_no,
      sign_status: notice.sign_status,
      title: notice.title,
    };
    openNotices.set(`${recordType}:${recordId}`, open);
    return HttpResponse.json(notice);
  }),
];
