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
 * 本批只启用 `SIGN`；其余两个在 **P9B-2** 开（`CHANGE_NOTICE` 的写入点
 * `change_notice_service` 当前抛 `NotImplementedError`，待 P9A-DLV-007）。
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
  { type: 'CHANGE_NOTICE', label: '变更单', enabled: false }, // P9B-2
  { type: 'CUSTOMER_APPROVAL_PROXY', label: '代录', enabled: false }, // P9B-2
];
