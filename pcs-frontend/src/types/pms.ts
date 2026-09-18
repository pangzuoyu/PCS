/**
 * PMS / BEDD 模块类型（P45-3-8 / Task 35）。
 *
 * SPEC §7.5：
 * - PmsItem：管道材料规格（PMS = Pipe Material Specification）
 * - BeddSection：BEDD 文档章节（Basic Engineering Design Data）
 * - WizardStep：项目向导步骤
 *
 * TODO(api-migration): V1 极简版前端 mock props shape；P5-1 PMS / BEDD
 * 端点冻结后由 src/types/api.d.ts 替换。
 */

import type { RecordSignStatus } from './records';

/** 危险等级（管道材料规格 PMS）：低 LOW / 中 MEDIUM / 高 HIGH（驱动审批层级）。 */
export type HazardLevel = 'LOW' | 'MEDIUM' | 'HIGH';

/** PMS 管道材料规格条目：物料 ID + PMS 编号 + 描述 + 类别 + 危险等级 + 5 态机签名状态。 */
export interface PmsItem {
  item_id: string;
  pms_no: string;
  description: string;
  pms_class: string;
  hazard_level: HazardLevel;
  sign_status: RecordSignStatus;
}

/** BEDD（基础工程设计数据表）章节：章节 ID + 标题 + 正文内容。 */
export interface BeddSection {
  section_id: string;
  title: string;
  content: string;
  sign_status: RecordSignStatus;
  /** 签名记录（key by step_index） */
  signatures?: Array<{ step_index: number; signer: string; signed_at: string }>;
}

/** 项目向导步骤：步骤序号 + 标题 + 描述 + 完成标志（驱动 Wizard 进度条渲染）。 */
export interface WizardStep {
  step_index: number;
  title: string;
  description?: string;
  done: boolean;
}

/** 项目向导配置：项目名 + 步骤列表（顺序由 step_index 决定）。 */
export interface ProjectWizard {
  project_name: string;
  steps: WizardStep[];
}