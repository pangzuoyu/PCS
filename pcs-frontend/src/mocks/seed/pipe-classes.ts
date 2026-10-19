/**
 * PipeClass seed — 4 条（QA 11 组件实例化 P1）
 *
 * 覆盖 4 个状态 + 数值字段差异触发 NumericCell。
 *
 * ## 形状以**契约**为准（2026-10-19，bug-180）
 *
 * 本文件此前返 `{pipe_class_id, code, material, schedule, size_range_json,
 * sign_status}`，而 `GET /api/v1/pipe-classes` 的契约 `PipeClassResponse`
 * 是 `{class_id, class_name, material_standard, sch_series_json,
 * dn_series_json, status}` —— **字段名整组不同**。
 *
 * 后果不是 mock 脏，是**生产缺陷**：`PipeClassListPage` 读
 * `record.pipe_class_id`（`rowKey` 也用它），`PipeComputePage` 的下拉用
 * `{value: p.pipe_class_id, label: p.code}` —— 真后端下两者全是
 * `undefined`。**管道等级页在生产上就是坏的，是这份 mock 一直在替它遮着。**
 *
 * 现已随 `types/pipeClass.ts` 一并并到契约类型，且末尾保留编译期
 * 一致性断言 —— 契约再加字段/改字段名，`tsc` 立刻红。
 *
 * ## 壁厚刻意做出三档形态（供 `summarizeSchSeries` 覆盖）
 *
 * - `pc-001` 全范围同 Sch → 单元格显示 `Sch 40`
 * - `pc-002` 前半 Sch 80 / 后半 Sch 160 → 显示「按 DN 分档」+ Tooltip
 * - `pc-003` 空映射 → 显示 `—`（EMPTY 与 VARIED 必须分开，见 pipeClassSch.ts）
 */
import type { PipeClass } from '../../types/pipeClass';

export const seedPipeClasses: PipeClass[] = [
  {
    class_id: 'pc-001',
    class_name: 'ASME B31.3',
    material_standard: 'A106-B',
    base_material: 'A106-B',
    corrosion_allowance: 1.5,
    design_pressure: 2.5,
    design_temperature: 250.0,
    fluid_service: 'STEAM',
    allowable_stress_json: { '250': 138.0 },
    dn_series_json: { min: 15, max: 600 },
    sch_series_json: { '15': 'Sch 40', '50': 'Sch 40', '300': 'Sch 40', '600': 'Sch 40' },
    flange_class: '150#',
    fitting_type: 'ELBOW',
    branch_table_json: undefined,
    source: 'COMPANY_STD',
    version: '1.0',
    status: 'PUBLISHED',
  },
  {
    // ⚠️ 壁厚在 DN 范围内**不统一** —— 覆盖 VARIED 分支
    class_id: 'pc-002',
    class_name: 'ASME B31.3',
    material_standard: 'A312-TP304',
    base_material: 'A312-TP304',
    corrosion_allowance: 2.0,
    design_pressure: 4.0,
    design_temperature: 400.0,
    fluid_service: 'PROCESS',
    allowable_stress_json: { '400': 105.0 },
    dn_series_json: { min: 15, max: 300 },
    sch_series_json: { '15': 'Sch 80', '50': 'Sch 80', '100': 'Sch 160', '300': 'Sch 160' },
    flange_class: '300#',
    fitting_type: 'TEE',
    branch_table_json: undefined,
    source: 'PROJECT',
    version: '1.0',
    status: 'PUBLISHED',
  },
  {
    // ⚠️ 空映射 —— 覆盖 EMPTY 分支（不得显示成「按 DN 分档」）
    class_id: 'pc-003',
    class_name: 'GB/T 20801',
    material_standard: '20#',
    base_material: '20#',
    corrosion_allowance: 1.0,
    design_pressure: 1.6,
    design_temperature: 200.0,
    fluid_service: 'WATER',
    allowable_stress_json: {},
    dn_series_json: { min: 20, max: 500 },
    sch_series_json: {},
    flange_class: 'PN16',
    fitting_type: null,
    branch_table_json: undefined,
    source: 'COMPANY_STD',
    version: '1.0',
    status: 'PENDING',
  },
  {
    class_id: 'pc-004',
    class_name: 'ASME B31.1',
    material_standard: 'A335-P11',
    base_material: 'A335-P11',
    corrosion_allowance: 3.0,
    design_pressure: 10.0,
    design_temperature: 575.0,
    fluid_service: 'OIL',
    allowable_stress_json: { '575': 43.0 },
    dn_series_json: { min: 50, max: 400 },
    sch_series_json: { '50': 'Sch 160', '150': 'Sch 160', '400': 'Sch 160' },
    flange_class: '600#',
    fitting_type: 'REDUCER',
    branch_table_json: undefined,
    source: 'COMPANY_STD',
    version: '1.0',
    status: 'APPROVED',
  },
];

/* 契约一致性断言（2026-10-18 由评审 #24 的标注工作加回，2026-10-19 首次成立）。
 *
 * `PipeClass` 现在**就是**契约类型，所以这条断言是恒真的类型检查 ——
 * 它的价值不在此刻，而在**未来**：有人再往 `types/pipeClass.ts` 里
 * 加一个手写字段、或把 `PipeClass` 改回 interface，这条会立刻红。
 *
 * 2026-10-18 时它红过 —— 那正是 bug-180 的发现路径：
 * 一次 `tsc` 跑出 5 处真漂移（见评审 README「#24 引出的新发现」）。
 */
const _conforms: PipeClass[] = seedPipeClasses;
void _conforms;
