/**
 * 临时过滤条件的**载荷构造**：`null` 与 `[]` 必须区分（评审 #11，用户裁决）。
 *
 * ## 裁决
 *
 * - `null`   = 用户没做临时调整 ⇒ **继承定义里的原条件**
 * - `[]`     = 用户进编辑器、然后**把所有条件删光** ⇒ **不筛选**（导出全量）
 *
 * ## 原缺陷
 *
 * `ReportExecutePage.run()` 里是 `!tempFilters?.length ? undefined : ...` ——
 * `null` 与 `[]` 被**压成同一个值**，于是「显式删光」静默退化成
 * 「继承定义」。用户看着编辑器里一条条件都没有，导出却仍带着定义的条件 ——
 * 界面在骗人，且没有任何提示。
 *
 * 「删光」必须能表达「不筛选」，因为**临时调整的整个用意就是能覆盖定义**
 * （SPEC §3.2.2(5)）。一个只能加条件、不能减条件的临时面板是残废的。
 *
 * ## 为什么把逻辑抽成纯函数
 *
 * 原先它是 `run()` 里的一段内联表达式，要测就得驱动整页 + antd 的
 * 条件编辑器（删一个节点要点嵌套里的删除按钮）。抽出来之后
 * 三种输入各一行断言 —— 精确，且不再依赖 antd 的内部 DOM。
 */
import { describe, it, expect } from 'vitest';

import { buildTempFilterPayload } from '../../src/pages/report/definitionBody';
import type { FilterNode } from '../../src/pages/report/definitionBody';

const LEAF: FilterNode = {
  kind: 'leaf',
  source: 'EQUIP_LIST',
  field: 'tag_number',
  operator: 'EQ',
  value: 'P-1001',
} as FilterNode;

describe('buildTempFilterPayload — null 与 [] 必须区分', () => {
  it('null → undefined（继承定义里的原条件，不下发 filters）', () => {
    expect(buildTempFilterPayload(null)).toBeUndefined();
  });

  it('[] → 空的 AND 组（显式「不筛选」）', () => {
    // ⚠️ 不是 undefined。后端 `apply_filters` 对空条件组返回 `sa.true()`
    // （query_engine.py docstring 明写「空过滤器 = 不筛，不是报错」），
    // 所以空组就是「不筛选」的正确表达。
    const got = buildTempFilterPayload([]);
    expect(got).toEqual({ operator: 'AND', conditions: [] });
    expect(got).not.toBeUndefined();
  });

  it('单叶子节点 → 该叶子本身（与原有行为一致）', () => {
    expect(buildTempFilterPayload([LEAF])).toMatchObject({ field: 'tag_number' });
  });

  it('多节点 → AND 组', () => {
    const got = buildTempFilterPayload([LEAF, LEAF]);
    expect(got).toMatchObject({ operator: 'AND' });
    expect((got as { conditions: unknown[] }).conditions).toHaveLength(2);
  });

  it('⚠️ 最关键的一条：[] 与 null 的结果**不同**', () => {
    // 把这一条单独列出来，因为整条裁决就压在这一行上。
    // 若哪天有人「简化」成 `!tempFilters?.length ? undefined : ...`，
    // 这条立刻变红。
    expect(buildTempFilterPayload([])).not.toBe(buildTempFilterPayload(null));
  });
});
