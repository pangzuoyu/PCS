/**
 * 结果模块描述符的**守卫测试**（P9B-2 · T4 · TODO-067 #2）。
 *
 * ## 为什么需要守卫
 *
 * `hasSignStatus` 是**显式布尔**（显式 > 隐式）⇒ 但它与 `columns` **必须一致**：
 * 将来给某模块**加/删** `sign_status` 列而忘了改这个布尔 ⇒
 * 操作栏会给一个**没有 9 态列**的模块发请求 ⇒ 后端 422
 * `RECORD_MODULE_UNSUPPORTED` ⇒ 用户点一下吃一个后端错误。
 * ⇒ 一条守卫测试把它变成**编译期/测试期**的红。
 *
 * ⚠️ 同源的第二条（TODO-067 #2）：`editableFields` 是**从 `columns` 派生**的
 * （`editableFieldDefs`）⇒ `editableFields` 里漏掉的字段会**静默**从表单消失
 * ⇒ 守卫：`editableFields ⊆ columns`。
 */
import { describe, it, expect } from 'vitest';

import { RESULT_MODULES, editableFieldDefs } from '../../../src/pages/results/resultModules';

describe('结果模块描述符 —— 守卫', () => {
  it('hasSignStatus ⇔ columns 里有 sign_status', () => {
    for (const m of RESULT_MODULES) {
      const hasColumn = m.columns.some((c) => c.key === 'sign_status');
      expect(m.hasSignStatus).toBe(hasColumn);
    }
  });

  it('⚠️ cost_est 没有 9 态列（无操作栏、但可批注）', () => {
    const costEst = RESULT_MODULES.find((m) => m.recordType === 'CostEstResult');
    expect(costEst).toBeTruthy();
    expect(costEst!.hasSignStatus).toBe(false);
    expect(costEst!.columns.some((c) => c.key === 'sign_status')).toBe(false);
  });

  it('TODO-067 #2：editableFields ⊆ columns（漏了 ⇒ 静默从表单消失）', () => {
    for (const m of RESULT_MODULES) {
      const columnKeys = new Set(m.columns.map((c) => c.key));
      for (const f of editableFieldDefs(m)) {
        expect(columnKeys.has(f.key)).toBe(true);
      }
    }
  });

  it('每个模块的 editableFields 都不为空（空 ⇒ 表单什么都不渲染）', () => {
    for (const m of RESULT_MODULES) {
      expect(editableFieldDefs(m).length).toBeGreaterThan(0);
    }
  });
});
