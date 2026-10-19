/**
 * COMMON 模块类型（P45-3-3 / Task 30）。
 *
 * SPEC §7.8：
 * - ComponentProperty：组分物性（组分库）
 * - AllowableStress：许用应力（材料 + 温度 + 标准）
 * - ToxicityClass：毒性 / 爆炸极限（hazard_class 三档）
 *
 * TODO(api-migration): AllowableStressResult 已在 api.d.ts 存在
 * （§AllowableStressResult）。ComponentProperty / ToxicityClass 后端
 * 端点未在 P5-1 前冻结，V1 沿用前端 mock props shape。P5-1 完成后
 * 由 api.d.ts 替换。
 *
 * 见 docs/superpowers/plans/2026-09-16-p45-frontend-sprint-batch3.md
 * §"P5 契约冻结点"
 */

/**
 * 材料搜索结果（GET /common/materials/search → `MaterialSearchResult`）。
 *
 * ⚠️ 2026-10-19 对齐契约：契约只有 **5 个字段**（cas / name / formula /
 * mw / source）。此前手写的是「搜索结果 + 物性详情」的**合并体**
 * —— `component_id` 与 `cas_number` 契约里没有，临界参数 `tc_k`/`pc_mpa`/
 * `omega` 属于另一个 schema `MaterialDetail`。
 * 页面读它们 ⇒ 真后端下恒为 undefined。
 *
 * `cas_number` → `cas`；`component_id` 无对应，用 `cas` 当行标识。
 * 临界参数按用户裁决**砍列**（不做 N+1；详见 PropertySearchPage 的注释）。
 */
export interface ComponentProperty {
  cas: string;
  name: string;
  formula?: string | null;
  mw?: number | null;
  source?: string;
}

/** 许用应力表（材料 × 温度 × 标准）：指定材料在指定温度下的许用应力 MPa（ASME/GB/DIN 等）。 */
/**
 * 材料许用应力（GET /common/allowable-stress → `AllowableStressResult`）。
 *
 * 字段名 2026-10-19 对齐契约（TODO-039 审计发现的三处漂移）：
 * `temperature_c`→`temp_c`、`allowable_stress_mpa`→`stress_mpa`、
 * `standard`→`source`。方向经 `common_service.py:213-231` 的实现确认 ——
 * 契约对、前端错，所以改前端而不是把后端改名迁就前端。
 *
 * ⚠️ 这里**只**对齐了本类型自身的字段，整体仍是手写副本。
 * 完整契约还有 `interpolated: boolean`（是否插值），本页暂不用。
 */
export interface AllowableStress {
  material: string;
  /** 温度 °C（契约 temp_c）。 */
  temp_c: number;
  /** 许用应力 MPa（契约 stress_mpa）。 */
  stress_mpa: number;
  /** 数据来源标记，如 `ASME_B31.3_TABLE_A1`（契约 source）。 */
  source: string;
  /** 是否插值（节点间取值而非正好命中表节点）。契约有，本页暂不用。 */
  interpolated?: boolean;
}

/**
 * 介质毒性（GET /common/safety → `SafetyResult`）。
 *
 * ⚠️ 2026-10-19 对齐契约。
 *
 * 砍掉的字段与依据（用户裁决「先查后端有没有这些数据，���没有就砍列」）：
 * 后端 `common_service.py::_SAFETY_DATA` 是**内置内存字典**（~15 种介质），
 * 每条只有 `{name, tox, lfl, ufl}` —— **LD50 / PEL / 危险等级一律没有，
 * 也没有对应的 DB 表**。页面此前读它们，读的是**幽灵数据**。
 *
 * `explosive_limit_json: {lel, uel}` → 契约拍平成 `lel_vol_pct` / `uel_vol_pct`。
 * `component_id` 无对应 → 用 `cas` 当行标识。
 */
export interface ToxicityClass {
  cas: string;
  name?: string | null;
  /** 毒性等级，后端 `tox` 字段：NONE / LOW / MEDIUM / HIGH。 */
  toxicity_class: string;
  /** 爆炸下限 %vol（后端 `lfl`）。 */
  lel_vol_pct?: number | null;
  /** 爆炸上限 %vol（后端 `ufl`）。 */
  uel_vol_pct?: number | null;
  source?: string;
}

/** 毒性等级词表（后端 `_SAFETY_DATA[...]["tox"]` 的取值）。
 *  ⚠️ 与旧的 `HazardClass`（LOW/MEDIUM/HIGH）**不是一回事** ——
 *  后端还有 `NONE`。分组用这个，别用旧的。 */
export type ToxicityClassLevel = 'NONE' | 'LOW' | 'MEDIUM' | 'HIGH';

// ---------------------------------------------------------------------------
// 气体热值（C-06 / P6-4 T1；POST /common/heating-value/calculate）
// ---------------------------------------------------------------------------

import type { components } from './api';

/** 气体热值计算请求：compositions [{cas, mol_frac}]（不要求和 1，service 归一化）+ excess_air_pct。 */
export type HeatingValueCalcRequest = components['schemas']['HeatingValueCalcRequest'];

/** 气体热值计算响应：HHV/LHV 双单位 + 化学计量空气 + 烟气组成/MW + formula_ref 溯源。 */
export type HeatingValueCalcResponse = components['schemas']['HeatingValueCalcResponse'];
