/**
 * 工作流类型 tab 的**词表**（P9B-1 · SPEC §6.24）。
 *
 * 刻意独立于 `WorkflowProgressPanel.tsx`：eslint 的
 * `react-refresh/only-export-components` **不允许组件文件导出非组件**
 * （仓库既有先例：`src/pages/report/definitionBody.ts`）。
 *
 * ## ⚠️ 类型必须是**后端枚举三值**
 *
 * `WorkflowType` = `SIGN` / `CHANGE_NOTICE` / `CUSTOMER_APPROVAL_PROXY`
 * ⚠️ **没有 `DOC_PROXY`** —— 「代录」的后端键是 `CUSTOMER_APPROVAL_PROXY`
 * （SPEC §6.24 / 后端 `WorkflowType` 枚举）。
 *
 * ## tab **可配置**
 *
 * - `SIGN` / `CUSTOMER_APPROVAL_PROXY`：**已启用**（P9B-2 起，聚合端点
 *   （TODO-065）一次返回这两类工作流的进度）。
 * - `CHANGE_NOTICE`：**仍然禁用** —— R-13 把这一段从聚合端点**删掉**了
 *   （变更单**本身就是交付物** ⇒ 它在进度页上自己一行、自有 SIGN 进度；
 *   而 `Deliverable.parent_deliverable_id` 全仓从未被写 ⇒ 靠它反查变更单
 *   **永远查不到** ⇒ 留着一个**永远为假**的段比没有更坏）。
 */
export type WorkflowType = 'SIGN' | 'CHANGE_NOTICE' | 'CUSTOMER_APPROVAL_PROXY';

export interface WorkflowTab {
  type: WorkflowType;
  label: string;
  /** 本批是否启用。 */
  enabled: boolean;
}

export const WORKFLOW_TABS: readonly WorkflowTab[] = [
  { type: 'SIGN', label: '签署', enabled: true },
  // ⚠️ **仍然禁用**（R-13）：变更单自己就是交付物 ⇒ 不作为聚合段出现
  { type: 'CHANGE_NOTICE', label: '变更单', enabled: false },
  { type: 'CUSTOMER_APPROVAL_PROXY', label: '代录', enabled: true },
];
