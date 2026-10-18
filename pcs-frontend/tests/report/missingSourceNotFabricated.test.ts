/**
 * 缺 `source` 的条件**不得被伪造**成 `EQUIP_LIST` —— 评审 #30。
 *
 * ## 缺陷与它比「丢弃」更坏在哪
 *
 * 旧代码：`source: typeof n.source === 'string' ? n.source : 'EQUIP_LIST'`。
 *
 * 丢字段名 `field` 的节点，页面显示成「字段不存在」（很明显丢了）。
 * 丢 `source` 的节点，页面把它显示为**属于设备清单** —— 一个看起来
 * 完全正常、指向**另一张表**的条件。用户据此编辑并保存，
 * `'EQUIP_LIST'` 被写回定义体。**一次无声的语义改写**：
 * 这个过滤现在指向别的表，而用户完全不知道。
 *
 * 触发面不止手改的 payload：旧的已存定义、部分迁移的记录。
 *
 * ## 为什么选「丢弃」而不是「标记为非法节点」
 *
 * 与本模块既有防御一致 —— 缺 `field` / 缺 `operator` / 非对象
 * 全都 `return []`，评审 #25 也已把「静默丢弃」升级为
 * 「丢弃 + `countUnparsedFilterNodes` 计数 + 编辑器 Alert 提示」。
 * 少一条分支就不引入第二种处理风格。
 *
 * ⚠️ **代价**：计数器必须同步数它，否则「丢弃」退化为真正的静默丢失
 * —— 那正是 #25 已经修过的东西。本文件最后一条测试就钉这个一致性。
 */
import { describe, it, expect } from 'vitest';

import {
  asSingleFilter,
  countUnparsedFilterNodes,
  toFilterTree,
} from '../../src/pages/report/definitionBody';

/** 合法条件，只有 source 缺失。 */
const noSource = { field: 'tag_number', operator: 'EQ', value: 'E-101' };

describe('#30 缺 source 的条件不得被伪造', () => {
  it('toFilterTree 丢弃它，而不是塞成 EQUIP_LIST', () => {
    expect(toFilterTree([noSource])).toHaveLength(0);
  });

  it('不伪造 —— 树里一个 EQUIP_LIST 都不该出现', () => {
    const leaves: { source?: string }[] = [];
    const walk = (ns: ReturnType<typeof toFilterTree>): void => {
      ns.forEach((n) => {
        if (n.kind === 'group') walk(n.conditions);
        else leaves.push({ source: (n as { source?: string }).source });
      });
    };
    walk(toFilterTree([noSource]));
    expect(leaves.filter((l) => l.source === 'EQUIP_LIST')).toHaveLength(0);
  });

  it('嵌套在 AND 分组里的同样丢弃', () => {
    const raw = [{ operator: 'AND', conditions: [noSource] }];
    const tree = toFilterTree(raw);
    expect(tree).toHaveLength(1);
    expect((tree[0] as any).conditions).toHaveLength(0);
  });

  it('合法条件不受影响 —— 别把修复做过头', () => {
    const ok = { source: 'HEAT_RESULTS', field: 'duty', operator: 'GT', value: 100 };
    const tree = toFilterTree([ok]);
    expect(tree).toHaveLength(1);
    expect(tree[0]).toMatchObject({ kind: 'leaf', source: 'HEAT_RESULTS', field: 'duty' });
  });

  it('asSingleFilter 同样不伪造（同一兜底出现在两处）', () => {
    expect(asSingleFilter(noSource)).toBeNull();
  });

  it('asSingleFilter 对合法条件照常工作', () => {
    const ok = { source: 'HEAT_RESULTS', field: 'duty', operator: 'GT', value: 100 };
    expect(asSingleFilter(ok)).toMatchObject({ source: 'HEAT_RESULTS', field: 'duty' });
  });

  it('计数器同步数它 —— 否则「丢弃」就是真正的静默丢失（#25 已修过那个）', () => {
    // 编辑器靠这个数字渲染「本定义含 N 条本页无法识别的条件」。
    // 它若漏数 source 缺失，用户看不到任何提示就把它丢了。
    expect(countUnparsedFilterNodes([noSource])).toBe(1);
    expect(countUnparsedFilterNodes([
      { operator: 'AND', conditions: [noSource] },
    ])).toBe(1);
    expect(countUnparsedFilterNodes([
      { source: 'HEAT_RESULTS', field: 'duty', operator: 'GT', value: 1 },
    ])).toBe(0);
  });
});
