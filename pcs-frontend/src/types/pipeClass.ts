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

/** 管子等级条目：压力/温度/尺寸范围/腐蚀余量/设计阶段 + 5 态机签名状态（与 5 态机 DRAFT/IN_APPROVAL/CHECKED/OBSOLETE 对齐）。 */
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

/** 管架代号片段字段（6 类）：material / schedule / size / service / insulation / custom。 */
export type CodeSegmentField =
  | 'material'
  | 'schedule'
  | 'size'
  | 'service'
  | 'insulation'
  | 'custom';

/** 管架代号格式片段：顺序 + 字段 + 自定义值 + 分隔符。 */
export interface CodeFormatSegment {
  order: number;
  field: CodeSegmentField;
  value?: string;              // 'custom' 时必填；其余可由 props 注入或留空
  separator?: string;          // 前置分隔符（如 '-'）
}

/** 流代号符号分类：流体 fluid / 服务 service / 相态 phase / 毒性 toxicity。 */
export type SymbolCategory = 'fluid' | 'service' | 'phase' | 'toxicity';

/** 流代号符号映射：符号 + 含义 + 分类（如 "W" → "Water" → fluid）。 */
export interface SymbolMapping {
  symbol: string;              // 例如 "W"
  meaning: string;             // 例如 "Water"
  category: SymbolCategory;
}