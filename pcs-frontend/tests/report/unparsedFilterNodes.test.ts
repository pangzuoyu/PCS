/**
 * `toFilterTree` 会静默丢弃它不认识的节点 —— 保存时丢的就没了（评审 #25）。
 *
 * ## TODO-060 的失败形态（用户裁决：**警告**，不静默）
 *
 * 打开一个含有一条当前前端无法识别的条件（旧定义、手工改过的 payload、
 * 部分迁移的记录）的定义，改一个无关字段，保存 —— 那条条件就没了，
 * 且无任何提示。`definitionBody.ts` 自己声明「往返无损是硬要求」，
 * 而 `FilterTreeEditor` 刻意放行空值好让后端报错，都不是静默。
 *
 * ## 修法
 *
 * `countUnparsedFilterNodes(raw)`：数出 `toFilterTree` 会丢多少节点。
 * 编辑器据此渲染 Alert「本定义含 N 条本页无法识别的条件，保存时会丢弃」，
 * 保存前确认。
 */
import { describe, it, expect } from 'vitest';

import { countUnparsedFilterNodes, toFilterTree } from '../../src/pages/report/definitionBody';

describe('countUnparsedFilterNodes — 与 toFilterTree 的丢弃保持一致', () => {
  it('合法载荷 → 0', () => {
    const raw = [
      { source: 'EQUIP_LIST', field: 'tag_number', operator: 'EQ', value: 'P-1' },
      { operator: 'AND', conditions: [
        { source: 'EQUIP_LIST', field: 'tag_number', operator: 'EQ', value: 'P-2' },
      ] },
    ];
    expect(countUnparsedFilterNodes(raw)).toBe(0);
    expect(toFilterTree(raw)).toHaveLength(2);
  });

  it('缺 field / 缺 operator 的叶子 → 各计 1', () => {
    const raw = [
      { source: 'EQUIP_LIST', operator: 'EQ', value: 'x' },   // 缺 field
      { source: 'EQUIP_LIST', field: 'tag_number', value: 'y' }, // 缺 operator
    ];
    expect(countUnparsedFilterNodes(raw)).toBe(2);
    expect(toFilterTree(raw)).toHaveLength(0);
  });

  it('非对象节点 → 计 1', () => {
    expect(countUnparsedFilterNodes([null, 42, 'x'])).toBe(3);
  });

  it('嵌套组里的丢弃也要数到 —— 丢一整棵子树数它的**直接子节点数**', () => {
    const raw = [
      { operator: 'AND', conditions: [
        { source: 'A', operator: 'EQ', value: 1 },          // 缺 field → 丢
        { source: 'A', field: 'f', operator: 'EQ', value: 2 }, // 合法
      ] },
    ];
    expect(countUnparsedFilterNodes(raw)).toBe(1);
  });

  it('conditions 非数组 → 不是组，整节点按叶子判 → 丢弃并计 1', () => {
    // isGroup 要求 conditions 是数组；不是的话落到叶子分支，
    // 而它没有 field → 整个节点被丢。
    const raw = [{ operator: 'AND', conditions: 'not-an-array' }];
    expect(toFilterTree(raw)).toHaveLength(0);
    expect(countUnparsedFilterNodes(raw)).toBe(1);
  });

  it('整包不是数组 → 0（顶层就没有「节点」可数）', () => {
    expect(countUnparsedFilterNodes(undefined)).toBe(0);
    expect(countUnparsedFilterNodes({})).toBe(0);
    expect(countUnparsedFilterNodes('x')).toBe(0);
  });

  it('⚠️ 一致性根断言：计出的数量 + toFilterTree 保住的数量 === 总节点数', () => {
    const raw = [
      { source: 'A', field: 'f', operator: 'EQ', value: 1 },
      { nope: true },
      { operator: 'AND', conditions: [
        { field: 'f', operator: 'EQ', value: 2 },
        { field: 'g' },
      ] },
    ];
    const kept = toFilterTree(raw);
    const keptLeaves = countLeaves(kept);
    // 数原始叶子（含嵌套）
    const totalLeaves = countRawLeaves(raw);
    expect(countUnparsedFilterNodes(raw) + keptLeaves).toBe(totalLeaves);
  });
});

function countLeaves(nodes: unknown[]): number {
  return nodes.reduce((acc: number, n) => {
    const node = n as { kind: string; conditions?: unknown[] };
    if (node.kind === 'group') return acc + countLeaves(node.conditions ?? []);
    return acc + 1;
  }, 0);
}

function countRawLeaves(raw: unknown[]): number {
  return raw.reduce((acc: number, n) => {
    if (!n || typeof n !== 'object') return acc + 1;   // 非对象本身算一个被丢的
    const node = n as { conditions?: unknown; field?: unknown };
    if (Array.isArray(node.conditions)) {
      const kids = countRawLeaves(node.conditions);
      return acc + kids;
    }
    return acc + 1;
  }, 0);
}
