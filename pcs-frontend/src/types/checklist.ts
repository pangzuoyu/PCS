/**
 * Checklist（项目输入清单）类型定义（V1 极简版）。
 *
 * 三类清单状态：
 * - ChecklistStatus 5 态：未开始/进行中/已校核/已假设/不适用
 * - ChecklistCategory 3 类：必填/条件必填/可选
 * - ChecklistCompleteness：项目级完整度汇总（required_total / required_verified / required_assumed / required_blocked）
 */

/** Checklist 条目状态：未开始 NOT_STARTED / 进行中 IN_PROGRESS / 已校核 VERIFIED / 已假设 ASSUMED / 不适用 NOT_APPLICABLE。 */
export type ChecklistStatus =
  | 'NOT_STARTED'
  | 'IN_PROGRESS'
  | 'VERIFIED'
  | 'ASSUMED'
  | 'NOT_APPLICABLE';

/** Checklist 条目类别：必填 REQUIRED / 条件必填 CONDITIONAL / 可选 OPTIONAL。 */
export type ChecklistCategory = 'REQUIRED' | 'CONDITIONAL' | 'OPTIONAL';

/** Checklist 单条记录：项目下条目（key + label + module + 类别 + 是否必填 + 输入值 JSON + 状态 + 校核者/时间/假设原因 + 备注）。 */
export interface ChecklistItem {
  checklist_id: string;
  project_id: string;
  item_key: string;
  item_label: string;
  module: string | null;
  input_category: ChecklistCategory | null;
  required: boolean;
  input_value_json: Record<string, unknown> | null;
  source_type: string | null;
  status: ChecklistStatus;
  verified_by: string | null;
  verified_at: string | null;
  assumption_reason: string | null;
  note: string | null;
}

/** Checklist 更新请求：状态 + 可选输入值/来源/假设原因。 */
export interface ChecklistItemPut {
  status: ChecklistStatus;
  input_value_json?: Record<string, unknown> | null;
  source_type?: string | null;
  assumption_reason?: string | null;
}

/** Checklist 新建请求：key + label + 可选 module/类别/必填/备注。 */
export interface ChecklistItemCreate {
  item_key: string;
  item_label: string;
  module?: string | null;
  input_category?: ChecklistCategory;
  required?: boolean;
  note?: string | null;
}

/** 项目 Checklist 完整度汇总：总数 + 必填总数/已校核/已假设/阻塞数 + 完整度百分比。 */
export interface ChecklistCompleteness {
  project_id: string;
  total: number;
  required_total: number;
  required_verified: number;
  required_assumed: number;
  required_blocked: number;
  completeness_pct: number;
}