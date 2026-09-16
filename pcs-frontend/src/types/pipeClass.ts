/**
 * PIPE_CLASS 模块类型（P45-3-2 / Task 29）。
 *
 * SPEC §7.9：
 * - 管子等级（PipeClass）：压力 / 温度 / 尺寸 / 腐蚀余量 / 设计阶段
 * - 代码格式段（CodeFormatSegment）：管道号拼接规则
 * - 符号映射（SymbolMapping）：管路符号 ↔ 介质/服务/相态/毒性
 *
 * TODO(api-migration): PipeClassResponse 已在 api.d.ts 存在（§PipeClassResponse
 * 字段名 code/material/schedule 已对齐）；但 size_range_json /
 * design_pressure_mpa 等扩展字段由前端 V1 mock 注入。P5-1 完成 OpenAPI
 * 冻结后由 api.d.ts 替换本页 PipeClass / CodeFormatSegment / SymbolMapping。
 *
 * 见 docs/superpowers/plans/2026-09-16-p45-frontend-sprint-batch3.md
 * §"P5 契约冻结点"
 */

export type PipeClassStatus = 'DRAFT' | 'IN_APPROVAL' | 'CHECKED' | 'OBSOLETE';

export interface PipeClass {
  pipe_class_id: string;
  code: string;                // 例如 "ASME B31.3"
  material: string;            // 例如 "A106-B"
  schedule: string;            // 例如 "Sch 40"
  size_range_json: { min_dn: number; max_dn: number };
  design_pressure_mpa: number;
  design_temperature_c: number;
  corrosion_allowance_mm: number;
  sign_status: PipeClassStatus;
}

export type CodeSegmentField =
  | 'material'
  | 'schedule'
  | 'size'
  | 'service'
  | 'insulation'
  | 'custom';

export interface CodeFormatSegment {
  order: number;
  field: CodeSegmentField;
  value?: string;              // 'custom' 时必填；其余可由 props 注入或留空
  separator?: string;          // 前置分隔符（如 '-'）
}

export type SymbolCategory = 'fluid' | 'service' | 'phase' | 'toxicity';

export interface SymbolMapping {
  symbol: string;              // 例如 "W"
  meaning: string;             // 例如 "Water"
  category: SymbolCategory;
}