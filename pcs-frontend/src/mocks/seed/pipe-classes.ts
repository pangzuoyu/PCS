/**
 * PipeClass seed — 4 条（QA 11 组件实例化 P1）
 *
 * 覆盖 4 态（草稿/审批/已签/作废）+ 数值字段差异触发 NumericCell。
 */
import type { PipeClass } from '../../types/pipeClass';

export const seedPipeClasses: PipeClass[] = [
  {
    pipe_class_id: 'pc-001',
    code: 'ASME B31.3',
    material: 'A106-B',
    schedule: 'Sch 40',
    size_range_json: { min_dn: 15, max_dn: 600 },
    design_pressure_mpa: 2.5,
    design_temperature_c: 250.0,
    corrosion_allowance_mm: 1.5,
    sign_status: 'CHECKED',
  },
  {
    pipe_class_id: 'pc-002',
    code: 'ASME B31.3',
    material: 'A312-TP304',
    schedule: 'Sch 80',
    size_range_json: { min_dn: 15, max_dn: 300 },
    design_pressure_mpa: 4.0,
    design_temperature_c: 400.0,
    corrosion_allowance_mm: 2.0,
    sign_status: 'IN_APPROVAL',
  },
  {
    pipe_class_id: 'pc-003',
    code: 'GB/T 20801',
    material: '20#',
    schedule: 'Sch 40',
    size_range_json: { min_dn: 20, max_dn: 500 },
    design_pressure_mpa: 1.6,
    design_temperature_c: 200.0,
    corrosion_allowance_mm: 1.0,
    sign_status: 'DRAFT',
  },
  {
    pipe_class_id: 'pc-004',
    code: 'ASME B31.1',
    material: 'A335-P11',
    schedule: 'Sch 160',
    size_range_json: { min_dn: 50, max_dn: 400 },
    design_pressure_mpa: 10.0,
    design_temperature_c: 575.0,
    corrosion_allowance_mm: 3.0,
    sign_status: 'OBSOLETE',
  },
];

/* ⚠️ 已知契约不一致（2026-10-18 由评审 #24 的标注工作查出）——
 *
 * 本文件返 `{pipe_class_id, code, ...}`，而 `GET /api/v1/pipe-classes` 的
 * 契约 `PipeClassResponse` 是 `{class_id, class_name, material_standard,
 * corrosion_allowance, design_pressure, design_temperature, ...}`。
 * **字段名整组不同。**
 *
 * 后果比 mock 漂移更重：`PipeClassListPage` 读 `record.pipe_class_id`
 * （`rowKey` 也用它），`PipeComputePage` 的下拉用
 * `{value: p.pipe_class_id, label: p.code}` —— 真后端下两者全是
 * `undefined`。**管道等级页在生产上就是坏的，是这份 mock 一直在替它遮着。**
 *
 * 本轮不并（改它要动页面与 `types/pipeClass.ts` = TODO-039 前端类型唯一性）。
 * 已登记为新发现，见 TODO 与本轮提交信息。
 */
