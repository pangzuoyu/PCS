/**
 * PIPE_CLASS 模块类型（P45-3-2 / Task 29）。
 *
 * SPEC §7.9：
 * - 管子等级（PipeClass）：压力 / 温度 / 尺寸 / 腐蚀余量 / 设计阶段
 * - 代码格式段（CodeFormatSegment）：管道号拼接规则
 * - 符号映射（SymbolMapping）：管路符号 ↔ 介质/服务/相态/毒性
 *
 * ## `PipeClass` = **契约类型**，不再是手写副本（2026-10-19，bug-180）
 *
 * 此前这里手写了一份 `pipe_class_id` / `code` / `material` / `schedule` /
 * `size_range_json` / `sign_status`…，而契约 `PipeClassResponse` 返的是
 * `class_id` / `class_name` / `material_standard` / `sch_series_json` /
 * `dn_series_json` / `status`… —— **字段名整组不同**。
 *
 * `PipeClassListPage` 真连 `GET /api/v1/pipe-classes`，所以生产上
 * `record.pipe_class_id`（连 `rowKey` 也用它）与 `row.code` 都是
 * `undefined` —— **管道等级页在生产上是坏的**。而
 * `src/mocks/seed/pipe-classes.ts` 返的是手写形状，
 * 于是**这份 mock 一直在替页面遮着**，让缺陷在 dev 里不可见。
 *
 * 本文件原先的注释写着「PipeClassResponse 已在 api.d.ts 存在
 * （字段名 code/material/schedule 已对齐）」—— **那句是错的**，
 * 本仓「注释比代码乐观」的又一例。
 *
 * 现在直接 re-export 生成的类型：契约变 ⇒ `tsc` 立刻红，不会再有第二份。
 *
 * `CodeFormatSegment` / `SymbolMapping` **仍是手写**：
 * `SymbolTableRoute` / `CodeFormatRoute` 目前传的是空数组，
 * 既无契约也无数据来源，等接上 API 时再并。
 */
import type { components } from './api';

/** 管子等级出参。字段名以 `api.d.ts` 为准（见文件头）。 */
export type PipeClass = components['schemas']['PipeClassResponse'];

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