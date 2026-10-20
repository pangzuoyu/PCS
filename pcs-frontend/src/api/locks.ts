/**
 * 编辑锁 API 客户端（P9B-1 · SPEC §6.21 · ADR-0048）。
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
 *
 * ⚠️ **类型全部来自生成的 `api.d.ts`，不手写**（`src/api/reportBuilder.ts`
 * 的规矩）：手写的 `src/types/*.ts` 已经漂移过一次
 * （6 个 `*UpdateRequest` 缺 `expected_hash`）。
 */
import { api } from './client';
import type { components } from '../types/api';

export type LockResponse = components['schemas']['LockResponse'];
export type LockHolderResponse = components['schemas']['LockHolderResponse'];
export type ConflictEnvelope = components['schemas']['ConflictEnvelope'];

/**
 * 6 张有编辑路径的表 —— 与后端 `edit_guard.TABLE_CAPABILITIES` 同源。
 *
 * ⚠️ **这份清单是「写进 URL 的那一份」**：后端 `TABLE_CAPABILITIES` 是判定依据，
 * 这里是给调用方选值用的。⚠️ 两者不同步时**后端会 404**（不是静默错锁），
 * 且 `tests/api/edit_lock_api.test.ts` 会红。
 */
export const EDITABLE_RECORD_TYPES = [
  'CostEstResult',
  'FiltrationResult',
  'OpenChannelResult',
  'cooling_tower_result',
  'flare_system_result',
  'psychro_result',
] as const;

export type EditableRecordTypeName = (typeof EDITABLE_RECORD_TYPES)[number];

/** 判断一个值是不是合法的 `record_type`（后端不接受时**提前**拦，别等 404）。 */
export function isEditableRecordType(value: string): value is EditableRecordTypeName {
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

/**
 * 6 类结果记录的 PATCH —— **必须带并发基线**。
 *
 * ⚠️ 这个模块只先落 `cost_est`（本批 Task F0/F1 的验证对象）；其余 5 类
 * 在 Task F2 建页面时按同一形状补齐（`patchCoolingTower` 等）。
 * ⚠️ **签名里 `expected_hash` 必填**（不是可选）：漏了就是 409，而症状是
 * 「保存总是失败」，不指向漏传 ⇒ 用类型把它变成编译期错误。
 */
export interface PatchBaseline {
  /** 客户端看到的 record_hash（SPEC §6.21 P9A-LCK-006）。 */
  expected_hash: string;
  /** 无 hash 令牌时的第二档基线（cost_est 没有 updated_at ⇒ 不需要）。 */
  expected_updated_at?: string;
}

export const editRecordApi = {
  patchCostEst: (
    resultId: string,
    body: components['schemas']['CostEstUpdateRequest'] & PatchBaseline,
  ) =>
    api
      .patch<components['schemas']['CostEstResultResponse']>(
        `/cost-est/results/${resultId}`,
        body,
      )
      .then((r) => r.data),
};
