/**
 * REPORT_BUILDER 前端客户端（b10–b12 + c6）。
 *
 * 类型**全部来自 `./api`**（OpenAPI 生成），不手写 interface。
 * 理由与 TODO-039/041 的教训一致：手写类型与后端各写一份，字段名与
 * **单位**都会悄悄分叉（`p_mpa` ↔ `P_Pa`），而 TypeScript 查不出来 ——
 * 传错单位的数字一样编译通过。
 *
 * ## 分批说明（2026-10-13 用户裁决）
 *
 * 本轮（第一批）只做 **EQ 单条过滤**，不嵌套、不做 15 操作符全集。
 * 理由不是缩范围，是把「202 + task_id + 轮询」这条**前后端唯一需要
 * 对齐的时序契约**提前暴露。它跨 5 个组件（定义 CRUD / 发布 / ARQ /
 * 状态轮询 / 下载），任一环不通，其余 UI 都是空转。
 *
 * ⚠️ 第二批要做的是：15 操作符全量、AND/OR 嵌套、5 对 JOIN 白名单选择、
 * 临时调整过滤条件。过滤 UI 里留了 `// TODO(BATCH-2)` 标记 ——
 * **看到「只有一个 EQ」是有意分批，不是 bug**。
 */
import { api } from './client';
import type { components } from '../types/api';

export type ReportBuilderDatasource = components['schemas']['ReportBuilderDatasource'];
export type ReportBuilderField = components['schemas']['ReportBuilderField'];
export type ReportBuilderJoin = components['schemas']['ReportBuilderJoin'];
export type ReportBuilderDatasourceList =
  components['schemas']['ReportBuilderDatasourceList'];
export type ReportDefinitionOut = components['schemas']['ReportDefinitionOut'];
export type ReportDefinitionList = components['schemas']['ReportDefinitionList'];
export type ReportDefinitionUpsert = components['schemas']['ReportDefinitionUpsert'];
export type ReportDefinitionBody =
  components['schemas']['ReportDefinitionBody-Input'];
export type ReportExecuteAccepted = components['schemas']['ReportExecuteAccepted'];
export type ReportExecuteRequest = components['schemas']['ReportExecuteRequest'];
export type ReportFileStatusResponse = components['schemas']['ReportFileStatusResponse'];
export type ReportStyleSummary = components['schemas']['ReportStyleSummary'];
export type ReportStyleListResponse = components['schemas']['ReportStyleListResponse'];
export type ReportStyleCreate = components['schemas']['ReportStyleCreate'];
export type ReportExecutionStatus = components['schemas']['ReportExecutionStatus'];
export type ReportStyleRevise = components['schemas']['ReportStyleRevise'];
export type StylePatch = components['schemas']['StylePatch'];

/** 过滤器操作符全集（SPEC §3.2.2(4)，15 个）。
 *
 * ⚠️ **第一批只发 `EQ`**，其余枚举出来是为了让第二批接的时候
 * 不用回头改类型 —— 也为了让「为什么只有 EQ」在代码里看得见。
 */
export const FILTER_OPERATORS = [
  'EQ', 'NEQ', 'GT', 'GTE', 'LT', 'LTE', 'IN', 'NOT_IN',
  'CONTAINS', 'STARTS_WITH', 'ENDS_WITH', 'IS_NULL', 'IS_NOT_NULL',
  'BETWEEN', 'LIKE',
] as const;
export type FilterOperator = (typeof FILTER_OPERATORS)[number];

/** 本批开放的过滤操作符。见文件头「分批说明」。 */
export const OPERATORS_BATCH_1: readonly FilterOperator[] = ['EQ'];

/** 需要两个值（区间端点）的操作符 —— UI 据此渲染两个输入框。 */
export const BINARY_OPERATORS: ReadonlySet<FilterOperator> = new Set<FilterOperator>([
  'BETWEEN', 'NOT_IN', 'IN',
]);

/** 不需要值的操作符 —— UI 据此隐藏值输入框。 */
export const VALUELESS_OPERATORS: ReadonlySet<FilterOperator> = new Set<FilterOperator>([
  'IS_NULL', 'IS_NOT_NULL',
]);

export const reportBuilderApi = {
  // --- 字段树（b10）---------------------------------------------------------
  datasources: () =>
    api.get<ReportBuilderDatasourceList>('/report-builder/datasources')
      .then((r) => r.data),

  // --- 定义 CRUD（b10 / b12）------------------------------------------------
  list: (params?: { report_type?: string; status?: string }) =>
    api.get<ReportDefinitionList>('/report-builder/definitions', { params })
      .then((r) => r.data),

  get: (defId: string) =>
    api.get<ReportDefinitionOut>(`/report-builder/definitions/${defId}`)
      .then((r) => r.data),

  create: (body: ReportDefinitionUpsert) =>
    api.post<ReportDefinitionOut>('/report-builder/definitions', body)
      .then((r) => r.data),

  update: (defId: string, body: ReportDefinitionUpsert) =>
    api.put<ReportDefinitionOut>(`/report-builder/definitions/${defId}`, body)
      .then((r) => r.data),

  publish: (defId: string) =>
    api.post<ReportDefinitionOut>(`/report-builder/definitions/${defId}/publish`)
      .then((r) => r.data),

  obsolete: (defId: string) =>
    api.post<ReportDefinitionOut>(`/report-builder/definitions/${defId}/obsolete`)
      .then((r) => r.data),

  // --- 执行（b11）-----------------------------------------------------------
  /** 202 + task_id，**不出文件**。文件要轮询 status 再下载。 */
  execute: (defId: string, body?: ReportExecuteRequest) =>
    api.post<ReportExecuteAccepted>(
      `/report-builder/definitions/${defId}/execute`, body ?? {})
      .then((r) => r.data),

  /**
   * **按 `task_id` 查执行进度** —— 202 与文件之间唯一的桥。
   *
   * ⚠️ `/execute` 给的是 `task_id`，`/report/{id}/status` 只认
   * `report_file_id`，两者之间的映射由本端点提供（2026-10-13 补的
   * `report_execution_logs.task_id` / `report_file_id` 两列）。
   * 查不到就是 404 —— 前端据此**立刻停止轮询**，而不是转圈到超时。
   */
  executionStatus: (taskId: string) =>
    api.get<ReportExecutionStatus>(`/report-builder/executions/${taskId}`)
      .then((r) => r.data),

  fileStatus: (reportFileId: string) =>
    api.get<ReportFileStatusResponse>(`/report/${reportFileId}/status`)
      .then((r) => r.data),

  /**
   * 下载。
   *
   * ⚠️ **不能走 axios**：响应是二进制，用 `responseType: 'blob'` 会让
   * 401 的 JSON 错误体也变成 blob，拦截器看不到 `err.response.status`
   * 就不会跳登录，用户只会看到「下载下来一个打不开的文件」。
   * 所以这里用裸 fetch + 手动判状态码。
   */
  async download(reportFileId: string, filename: string): Promise<void> {
    const token = (await import('../store/auth')).useAuth.getState().accessToken;
    const res = await fetch(`/api/v1/report/${reportFileId}/download`, {
      headers: token ? { Authorization: `Bearer ${token}` } : undefined,
    });
    if (!res.ok) throw new Error(`下载失败（HTTP ${res.status}）`);
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  },

  // --- 样式（c6）-----------------------------------------------------------
  listStyles: (params?: { report_type?: string; project_id?: string }) =>
    api.get<ReportStyleListResponse>('/report/styles', { params })
      .then((r) => r.data),

  getStyle: (styleId: string) =>
    api.get<ReportStyleSummary>(`/report/styles/${styleId}`).then((r) => r.data),

  createStyle: (body: ReportStyleCreate) =>
    api.post<ReportStyleSummary>('/report/styles', body).then((r) => r.data),

  /** 改 = **新增一版本**（version+1），旧行保留为 SUPERSEDED。 */
  reviseStyle: (styleId: string, body: ReportStyleRevise) =>
    api.post<ReportStyleSummary>(`/report/styles/${styleId}/revise`, body)
      .then((r) => r.data),

  /** 回滚 = 把历史版本重新置为 ACTIVE，不删数据。 */
  activateStyle: (styleId: string) =>
    api.post<ReportStyleSummary>(`/report/styles/${styleId}/activate`)
      .then((r) => r.data),
};

/**
 * 从 axios 错误里取出**用户能看懂**的话。
 *
 * ⚠️ 不直接用 `err.message`：axios 的默认文案是
 * "Request failed with status code 409"，用户看不出是自己选重了。
 * 后端统一走 PcsError envelope（`code`/`message`），有 message 就用它。
 */
export function errorMessage(err: unknown): string {
  const anyErr = err as { response?: { data?: { message?: string; code?: string } } };
  const data = anyErr?.response?.data;
  if (data?.message) return data.message;
  if (data?.code) return data.code;
  return err instanceof Error ? err.message : '未知错误';
}
