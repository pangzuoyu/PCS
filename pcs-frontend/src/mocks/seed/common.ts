/**
 * 物性 / 许用应力 / 毒性爆炸 seed — 各 3 条（QA 11 组件实例化 P1）
 *
 * 数值差异触发 NumericCell 等宽对齐 + 精度格式（significant / decimal）。
 */
import type { ComponentProperty, AllowableStress, ToxicityClass } from '../../types/common';

/**
 * 材料搜索结果（`MaterialSearchResult` 只有 5 个字段）。
 *
 * ⚠️ 临界参数 `tc_k`/`pc_mpa`/`omega` 已砍（用户裁决：不做 N+1）。
 * 它们属于**另一个 schema** `MaterialDetail`，search 端点根本不返 ——
 * 此前 seed 编造这些值，让页面在 dev 里「看起来有数据」，
 * 于是没人发现生产上恒为空。**mock 编造字段 = 把契约缺陷也遮掉。**
 */
export const seedMaterials: ComponentProperty[] = [
  {
    name: '水',
    formula: 'H2O',
    cas: '7732-18-5',
    mw: 18.015,
  },
  {
    name: '乙醇',
    formula: 'C2H6O',
    cas: '64-17-5',
    mw: 46.068,
  },
  {
    name: '苯',
    formula: 'C6H6',
    cas: '71-43-2',
    mw: 78.114,
  },
  {
    name: '乙烯',
    formula: 'C2H4',
    cas: '74-85-1',
    mw: 28.054,
  },
];

// ⚠️ `source` 的取值照抄后端 `common_service.py` 的实现
// （`ASME_B31.3_TABLE_A1`），不是前端自己编的 `'ASME'` ——
// 契约里就是这一串，编个短名等于又造一份不一致。
export const seedAllowableStress: AllowableStress[] = [
  { material: 'A106-B', temp_c: 38, stress_mpa: 137.9,
    source: 'ASME_B31.3_TABLE_A1', interpolated: false },
  { material: 'A106-B', temp_c: 200, stress_mpa: 117.2,
    source: 'ASME_B31.3_TABLE_A1', interpolated: true },
  { material: 'A312-TP304', temp_c: 38, stress_mpa: 137.9,
    source: 'ASME_B31.3_TABLE_A1', interpolated: false },
  { material: 'A312-TP304', temp_c: 400, stress_mpa: 103.4,
    source: 'ASME_B31.3_TABLE_A1', interpolated: true },
];

// ⚠️ 逐条照抄后端 `common_service.py::_SAFETY_DATA` 的真实条目
// （CAS / name / tox / lfl / ufl），不再用前端编的 `m-00x` 与危害等级。
//
// LD50 / PEL 已砍（用户裁决：先查后端有没有这些数据）。
// `_SAFETY_DATA` 每条只有 `{name, tox, lfl, ufl}` —— 没有 LD50、没有 PEL，
// 也没有对应的 DB 表。页面此前读的是**幽灵数据**。
export const seedToxicityClasses: ToxicityClass[] = [
  { cas: '67-56-1', name: '甲醇', toxicity_class: 'MEDIUM',
    lel_vol_pct: 6.0, uel_vol_pct: 36.5, source: 'INTERNAL_SAFETY_DB' },
  { cas: '64-17-5', name: '乙醇', toxicity_class: 'LOW',
    lel_vol_pct: 3.3, uel_vol_pct: 19.0, source: 'INTERNAL_SAFETY_DB' },
  { cas: '71-43-2', name: '苯', toxicity_class: 'HIGH',
    lel_vol_pct: 1.2, uel_vol_pct: 7.8, source: 'INTERNAL_SAFETY_DB' },
  // 水：后端 lfl/ufl 就是 None —— 用来覆盖「无爆炸极限」那一栏的「—」分支
  { cas: '7732-18-5', name: '水', toxicity_class: 'NONE',
    lel_vol_pct: null, uel_vol_pct: null, source: 'INTERNAL_SAFETY_DB' },
];