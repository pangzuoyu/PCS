/**
 * 统一错误信封的解析（P9B-1 · SPEC §6.21 P9A-LCK-006）。
 *
 * ## 为什么不放在 axios 响应拦截器里直接弹窗
 *
 * 规格要求 409 **按 `basis` 三值分流**：不同 basis 文案不同、**动作也不同**
 * （「放弃我的修改并刷新」vs 「联系管理员」）⇒ 分流必须发生在**组件状态**里，
 * 而不是拦截器里弹一个框。拦截器只保留它该管的事（401 清会话）。
 *
 * ## 为什么页面级的 `extractPcsError` 不够
 *
 * 既有 10+ 个页面各自抄了一份扁平版（只取 `code` / `message`）。
 * 而冲突对象在 **`detail.conflict`**（嵌套），扁平版**取不到 `basis`**
 * ⇒ 分流无从谈起。
 *
 * ⚠️ 本仓的信封是 `{code, message, detail, trace_id}`
 * （后端 `app/core/errors.py::ErrorResponse` 全局异常处理器产出）。
 */
import type { components } from '../types/api';

/** 409 冲突详情（生成类型，见后端 `ConflictDetail`）。 */
export type ConflictDetail = components['schemas']['ConflictDetail'];

/** 后端统一错误信封。 */
export interface PcsErrorEnvelope {
  code?: string;
  message?: string;
  detail?: unknown;
  trace_id?: string;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null;
}

/**
 * 取 axios 错误里的信封（`err.response.data`）。
 *
 * 返回 `null` 而不是抛：调用点常在错误分支里，不能让解析器再抛一次。
 */
export function extractPcsError(err: unknown): PcsErrorEnvelope | null {
  if (!isRecord(err)) return null;
  const response = err['response'];
  if (!isRecord(response)) return null;
  const data = response['data'];
  if (!isRecord(data)) return null;
  return data as PcsErrorEnvelope;
}

/**
 * 取 409 编辑冲突的详情（`detail.conflict`）。
 *
 * - 非冲突错误（404 / 500 / 网络错误）⇒ `null`
 * - 是 409 但 `detail` 缺失或形状不对 ⇒ `null`（**不抛**）
 * - `basis` 不在约定的三值里 ⇒ **仍返回**，但 `basis` 原样透传
 *   ⇒ 组件层按「未知 basis」的兜底文案处理，不静默当成「无冲突」
 */
export function extractConflict(err: unknown): ConflictDetail | null {
  const envelope = extractPcsError(err);
  if (!envelope) return null;
  if (envelope.code !== 'RECORD_EDIT_CONFLICT') return null;
  const detail = envelope.detail;
  if (!isRecord(detail)) return null;
  const conflict = detail['conflict'];
  if (!isRecord(conflict)) return null;
  return conflict as unknown as ConflictDetail;
}

/** 409 弹窗按 `basis` 分流的三种情形（SPEC §6.21 P9A-LCK-006 的表）。 */
export type ConflictKind = 'record_hash' | 'updated_at' | 'no_baseline' | 'unknown';

/**
 * 把 `basis` 归成三值 + 兜底。
 *
 * ⚠️ `unknown` 这一档是**故意**的：后端若新增第四个 basis，前端必须显示
 * 「说不清」而不是**误报成「无冲突」**。
 */
export function conflictKind(basis: string | null | undefined): ConflictKind {
  switch (basis) {
    case 'record_hash':
    case 'updated_at':
    case 'no_baseline':
      return basis;
    default:
      return 'unknown';
  }
}
