/**
 * 编辑锁**操作**客户端（P9B-1 · SPEC §6.21 · ADR-0048）。
 *
 * 端点（后端 `app/api/v1/locks.py`）：
 * - `POST /locks/{record_type}/{record_id}/acquire` —— 取锁
 * - `POST /locks/{record_type}/{record_id}/renew`   —— 续期（心跳 60s）
 * - `POST /locks/{record_type}/{record_id}/release` —— 释放（仅持有者）
 *
 * ⚠️ **`record_type` 用 `RECORD_TYPE_REGISTRY` 的键**（`CostEstResult` /
 * `cooling_tower_result` …），**不是表名**（`cost_est_results`）。全仓只有
 * 这一套词表（P9A-5 Task A / SPEC V2.0）；后端会校验，传表名 ⇒ 404。
 * 键不总是类名：注册表 21 键里 5 个是 snake_case。
 * ⚠️ 词表与基线类型**住在 `records.ts`**（记录域的单一来源）⇒ 本文件
 * 只管「锁操作」，依赖方向 **locks → records**（单向，无循环）。
 *
 * ⚠️ **类型全部来自生成的 `api.d.ts`，不手写**（`src/api/reportBuilder.ts`
 * 的规矩）：手写的 `src/types/*.ts` 已经漂移过一次
 * （6 个 `*UpdateRequest` 缺 `expected_hash`）。
 */
import { api } from './client';
import { EDITABLE_RECORD_TYPES, type EditableRecordType } from './records';
import type { components } from '../types/api';

export type LockResponse = components['schemas']['LockResponse'];
export type LockHolderResponse = components['schemas']['LockHolderResponse'];
export type ConflictEnvelope = components['schemas']['ConflictEnvelope'];

export { EDITABLE_RECORD_TYPES };
export type { EditableRecordType };

/** 判断一个值是不是合法的 `record_type`（后端不接受时**提前**拦，别等 404）。 */
export function isEditableRecordType(value: string): value is EditableRecordType {
  return (EDITABLE_RECORD_TYPES as readonly string[]).includes(value);
}

export const editLockApi = {
  /**
   * 取锁。
   *
   * ⚠️ **不抛 409**：他人持锁时后端返回 409 + `holder`，而那**不是**异常
   * 路径 —— 它是「表单转只读」的正常输入 ⇒ 在这里 catch 掉并原样返回，
   * 让调用方按 `success` 分流（抛出去的话每个调用点都要 try/catch 同一段，
   * 而漏掉一个就变成未处理的 rejection）。
   */
  acquire: async (recordType: string, recordId: string): Promise<LockResponse> => {
    try {
      const r = await api.post<LockResponse>(
        `/locks/${recordType}/${recordId}/acquire`,
      );
      return r.data;
    } catch (err) {
      const locked = await readLock409(err);
      if (locked) return locked;
      throw err;
    }
  },

  /** 续期（60s 心跳）。⚠️ 409 = 锁已失效 ⇒ 调用方转只读，**不得**自动重试。 */
  renew: async (recordType: string, recordId: string): Promise<LockResponse> => {
    try {
      const r = await api.post<LockResponse>(
        `/locks/${recordType}/${recordId}/renew`,
      );
      return r.data;
    } catch (err) {
      const locked = await readLock409(err);
      if (locked) return locked;
      throw err;
    }
  },

  /** 释放（仅持有者成功；非持有者 409）。页面关闭**不要求**调用（30min TTL 回收）。 */
  release: async (recordType: string, recordId: string): Promise<LockResponse> => {
    try {
      const r = await api.post<LockResponse>(
        `/locks/${recordType}/${recordId}/release`,
      );
      return r.data;
    } catch (err) {
      const locked = await readLock409(err);
      if (locked) return locked;
      throw err;
    }
  },
};

/** 409 的响应体本身就是 `LockResponse`（后端 `responses={409: {model: LockResponse}}`）。 */
async function readLock409(err: unknown): Promise<LockResponse | null> {
  if (typeof err !== 'object' || err === null) return null;
  const response = (err as { response?: { status?: number; data?: unknown } }).response;
  if (!response || response.status !== 409) return null;
  const data = response.data;
  if (typeof data !== 'object' || data === null) return null;
  return data as LockResponse;
}

