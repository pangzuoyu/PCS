/**
 * **向导**类型（P45-3-8 / Task 35）。
 *
 * ⚠️ **PMS / BEDD 的类型已经进契约**（P10-H · T2 · TODO-195）⇒ ⇒
 * `PmsItem` / `BeddSection` 这两份**手写**类型已删 ⇒ ⇒ 改用
 * `src/types/api.d.ts` 的生成类型（`PmsItemResponse` / `BeddDocument` …）
 * ⇒ ⇒ 前端手写类型漂移的那一类缺陷（bug-180）从根上没了。
 *
 * ⚠️ **向导的步骤类型仍是手写** ⇒ ⇒ 它**不在契约里**（后端没有向导端点）
 * ⇒ ⇒ 暂时保留（向导本身还是占位页）。
 */

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
