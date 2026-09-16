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

export type HazardLevel = 'LOW' | 'MEDIUM' | 'HIGH';

export interface PmsItem {
  item_id: string;
  pms_no: string;
  description: string;
  pms_class: string;
  hazard_level: HazardLevel;
  sign_status: RecordSignStatus;
}

export interface BeddSection {
  section_id: string;
  title: string;
  content: string;
  sign_status: RecordSignStatus;
  /** 签名记录（key by step_index） */
  signatures?: Array<{ step_index: number; signer: string; signed_at: string }>;
}

export interface WizardStep {
  step_index: number;
  title: string;
  description?: string;
  done: boolean;
}

export interface ProjectWizard {
  project_name: string;
  steps: WizardStep[];
}