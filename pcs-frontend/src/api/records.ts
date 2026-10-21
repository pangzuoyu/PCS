/**
 * 记录域 API 客户端（P9B-1 · SPEC §6.21 · ADR-0048）。
 *
 * ## 为什么这里是「记录域的单一来源」
 *
 * 6 类可编辑结果记录共用同一套形状：列表 / 详情 / PATCH（带并发基线）。
 * 差异只有几处：**record_type / 路径 / 主键名 / 字段清单 / 偏移参数名**
 * ⇒ 差异写在**模块描述符**里（`src/pages/results/resultModules.ts`），
 * 通用部分（取锁 / 心跳 / 基线 / 保存 / 409）写在**共用组件**里。
 *
 * ⚠️ **词表只有这一套**：`record_type` 用 `RECORD_TYPE_REGISTRY` 的**键**
 * （`CostEstResult` / `cooling_tower_result` …），**不是表名**
 * （`cost_est_results`）⇒ 后端 `/locks` **会校验** `record_type`，传错 ⇒ 404。
 */
import { api } from './client';

/**
 * 6 张有编辑路径的表 —— 与后端 `edit_guard.TABLE_CAPABILITIES` 同源。
 *
 * ⚠️ **这份清单是「写进 URL 的那一份」**：后端 `TABLE_CAPABILITIES` 是判定依据，
 * 这里是给调用方选值用的。⚠️ 两者不同步时**后端会 404**（不是静默错锁），
 * 且 `tests/api/records_api.test.ts` 会红。
 */
export const EDITABLE_RECORD_TYPES = [
  'CostEstResult',
  'FiltrationResult',
  'OpenChannelResult',
  'cooling_tower_result',
  'flare_system_result',
  'psychro_result',
] as const;

export type EditableRecordType = (typeof EDITABLE_RECORD_TYPES)[number];

/**
 * 并发基线（SPEC §6.21 P9A-LCK-006）。
 *
 * ⚠️ **字段名必须是 snake_case**（与后端请求体逐字一致）——
 * 中间层（`EditBaseline`）也用**同一套名字** ⇒ 展开即兼容，无需转换。
 *
 * ⚠️ 可选性（两个都可选）**类型层表达不了**「至少一档」⇒ 由**运行时**保证
 * （`useEditBaseline` 的 `disabled === false` ⇒ 至少一档有值，见 T2）。
 *
 * ⚠️ **`expected_updated_at` 必须原样透传**（**不过 `new Date()`**）：
 * PG `TIMESTAMPTZ` 是**微秒**，JS `Date` 只到**毫秒** ⇒ 过一次 `Date`
 * 就**每次假 409**。
 */
export interface PatchBaseline {
  /** 一档基线：客户端看到的 `record_hash`（16 hex 小写）。 */
  expected_hash?: string;
  /** 二档基线：`updated_at` **原样**（不过 `new Date()`）。 */
  expected_updated_at?: string;
}

/** 6 个模块的列表 / PATCH 路径（= `GET {base}`）。 */
export const RESULT_BASES: Record<EditableRecordType, string> = {
  CostEstResult: '/cost-est/results',
  FiltrationResult: '/filtration/results',
  OpenChannelResult: '/open-channel/results',
  cooling_tower_result: '/cool-tower/results',
  flare_system_result: '/flare/results',
  psychro_result: '/psychro/results',
};

/**
 * 各模块列表端点的**偏移参数名** —— 后端两种拼法各 3 个：
 *
 * - `offset` —— cool-tower / flare / psychro
 * - `skip` —— filtration / open-channel / cost-est
 *
 * ⚠️ **传错不会报错**，后端会忽略不认识的 query 参数 ⇒ 结果是
 * **静默停在第一页**（翻页看起来「没反应」）。
 * ⇒ 调用方一律传 `offset`，由 `recordsApi.list` 按模块翻译。
 */
export const RESULT_OFFSET_PARAMS: Record<EditableRecordType, 'offset' | 'skip'> = {
  CostEstResult: 'skip',
  FiltrationResult: 'skip',
  OpenChannelResult: 'skip',
  cooling_tower_result: 'offset',
  flare_system_result: 'offset',
  psychro_result: 'offset',
};

/** base → 偏移参数名（由上面两张表派生 ⇒ 不会与 `RESULT_BASES` 漂移）。 */
const OFFSET_PARAM_BY_BASE: Record<string, 'offset' | 'skip'> = Object.fromEntries(
  EDITABLE_RECORD_TYPES.map((rt) => [RESULT_BASES[rt], RESULT_OFFSET_PARAMS[rt]]),
);

/** 列表查询参数（`offset` 是**统一的**入参 ⇒ 出参名由 api 层翻译）。 */
export interface RecordListParams {
  project_id: string;
  limit?: number;
  offset?: number;
}

export const recordsApi = {
  /**
   * 列记录。
   *
   * ⚠️ 返回类型只约束**信封的公共部分** `{items, total}` ——
   * 6 个模块的分页字段名**不同**（`limit/offset` vs `skip/limit`）
   * ⇒ **不消费分页字段**，偏移自己算。
   */
  list: <T>(base: string, params: RecordListParams) => {
    const { offset, ...rest } = params;
    const offsetParam = OFFSET_PARAM_BY_BASE[base] ?? 'offset';
    return api
      .get<{ items: T[]; total: number } & Record<string, unknown>>(base, {
        params: { ...rest, [offsetParam]: offset },
      })
      .then((r) => r.data);
  },

  get: <TRes>(base: string, id: string) =>
    api.get<TRes>(`${base}/${id}`).then((r) => r.data),

  /**
   * PATCH（**必须带并发基线**）。
   *
   * ⚠️ 6 个模块**同构**（OpenAPI 实测：6 个 `*UpdateRequest` 都带基线字段）
   * ⇒ 统一签名。基线字段由调用方按三档判定填入。
   */
  patch: <TRes, TBody extends object>(
    base: string,
    id: string,
    body: TBody & PatchBaseline,
  ) => api.patch<TRes>(`${base}/${id}`, body).then((r) => r.data),
};
