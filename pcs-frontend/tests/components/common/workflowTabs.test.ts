import { describe, it, expect } from 'vitest';
import { WORKFLOW_TABS, WORKFLOW_LABELS, type WorkflowType } from '../../../src/components/common/workflowTabs';

describe('workflowTabs —— 词表唯一真相源（评审 A-3）', () => {
  it('每个 tab 类型在 WORKFLOW_LABELS 里有段标题（新增类型漏改 ⇒ 编译红 + 此处红）', () => {
    for (const tab of WORKFLOW_TABS) {
      expect(WORKFLOW_LABELS[tab.type as WorkflowType].tab).toBe(tab.label);
      expect(WORKFLOW_LABELS[tab.type as WorkflowType].section.length).toBeGreaterThan(0);
    }
  });
});
