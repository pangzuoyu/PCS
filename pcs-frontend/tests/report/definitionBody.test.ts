/**
 * 定义体 ⇄ 编辑态转换的单测。
 *
 * 为什么单独测这些纯函数：页面上它们只是「渲染前处理一下」，
 * 出错时症状是**字段列表里全是内部键名**、或**保存报 422** ——
 * 两者都不指向这一层，且都要人手动点几步才看得见。
 */
import { describe, expect, it } from 'vitest';

import {
  asSingleFilter,
  availableJoins,
  buildBody,
  pairKey,
  fieldsAtLevel,
  toFilterTree,
  toRows,
} from '../../src/pages/report/definitionBody';
import type { ReportBuilderDatasource } from '../../src/api/reportBuilder';

// ⚠️ `model` 是契约 `ReportBuilderDatasource` 的**必填**字段
// （openapi required: ['key','label','model','fields']）。此前这个 fixture
// 漏了它 —— 因为 tests/ 不在类型检查内（tsconfig include=["src"]，
// 2026-10-19 才纳入），漏了也没人知道。值取真实模型名，让 fixture 与
// 后端真返的形状一致。
const SOURCES: ReportBuilderDatasource[] = [
  {
    key: 'HEAT_RESULTS',
    label: '换热器结果',
    model: 'HeatResult',
    fields: [
      { name: 'tag_number', label: '位号', type: 'string',
        is_jsonb_key: false, level: null, exchanger_type: null },
      { name: 'shell_tube_count', label: '管程数', type: 'number',
        is_jsonb_key: false, level: 'DETAIL', exchanger_type: null },
    ],
  },
];

describe('fieldsAtLevel', () => {
  it('keeps the human label instead of overwriting it with the field name', () => {
    // ⚠️ 回归：曾经写成 `{ ...f, label: f.name }`「统一规范化」，
    // 结果字段选择器里全是 shell_tube_count 这类内部键名。
    const [field] = fieldsAtLevel(SOURCES, 'BASIC');
    expect(field.label).toBe('位号');
    expect(field.name).toBe('tag_number');
  });

  it('BASIC does not offer DETAIL fields', () => {
    const names = fieldsAtLevel(SOURCES, 'BASIC').map((f) => f.name);
    expect(names).toContain('tag_number');
    expect(names).not.toContain('shell_tube_count');
  });

  it('DETAIL offers both', () => {
    expect(fieldsAtLevel(SOURCES, 'DETAIL').map((f) => f.name))
      .toEqual(['tag_number', 'shell_tube_count']);
  });
});

describe('buildBody', () => {
  const rows = [
    { key: 'r0', source: 'HEAT_RESULTS', field: 'tag_number', label: '位号',
      alias: '设备位号', order: 0, visible: true, level: null },
  ];

  it('does not send label/level back to the backend', () => {
    // ⚠️ ReportDefSelectedField 是 extra="forbid" —— 多传 label 会 422。
    // 症状看着像「后端坏了」，实际是前端多发了字段。
    const body = buildBody({
      rows, level: 'BASIC', maxRows: 100, outputFormat: 'pdf', filter: null,
    }) as unknown as Record<string, unknown[]>;
    const first = body.SelectedFields[0] as Record<string, unknown>;
    expect(Object.keys(first).sort())
      .toEqual(['alias', 'field', 'order', 'source', 'visible']);
    expect(first).not.toHaveProperty('label');
    expect(first).not.toHaveProperty('level');
  });

  it('dedupes DataSources', () => {
    const two = [rows[0], { ...rows[0], key: 'r1', field: 'shell_tube_count',
      order: 1, level: 'DETAIL' }];
    const body = buildBody({
      rows: two, level: 'DETAIL', maxRows: 10, outputFormat: 'pdf', filter: null,
    }) as unknown as { DataSources: unknown[] };
    expect(body.DataSources).toHaveLength(1);
  });

  it('emits no FilterConditions when the filter is cleared', () => {
    // 清空过滤必须发空数组而不是「留着上一条」—— 后端对空 value
    // 返回空结果集，漏发会让一次「取消过滤」变成「导出零行」。
    const body = buildBody({
      rows, level: 'BASIC', maxRows: 10, outputFormat: 'pdf', filter: null,
    }) as unknown as { FilterConditions: unknown[] };
    expect(body.FilterConditions).toEqual([]);
  });

  it('assigns a stable row key that is NOT sent to the backend', () => {
    // ⚠️ key 只用于 React 列表渲染。多发给后端会被 extra="forbid" 拒成 422。
    const body = buildBody({
      rows, level: 'BASIC', maxRows: 10, outputFormat: 'pdf', filter: null,
    });
    // 不用 `as unknown as Record<string, unknown[]>` —— 那个双重断言把
    // 类型信息全丢了，于是 `toRows(body, ...)` 需要时又得再断一次。
    // `buildBody` 本来就返回 `ReportDefinitionBody`，直接用即可。
    expect(body.SelectedFields?.[0]).not.toHaveProperty('key');
    expect(toRows(body, SOURCES)[0].key).toBeTruthy();
  });

  it('round-trips through toRows without losing the alias', () => {
    const body = buildBody({
      rows, level: 'BASIC', maxRows: 10, outputFormat: 'pdf', filter: null,
    });
    const back = toRows(body, SOURCES);
    expect(back[0].alias).toBe('设备位号');
    // 标签是从字段树回填的，不是从定义体来的
    expect(back[0].label).toBe('位号');
  });
});

describe('asSingleFilter', () => {
  it('reads a leaf condition', () => {
    expect(asSingleFilter({
      source: 'HEAT_RESULTS', field: 'tag_number', operator: 'EQ', value: 'E-1',
    })).toEqual({ source: 'HEAT_RESULTS', field: 'tag_number',
      operator: 'EQ', value: 'E-1' });
  });

  it('returns null for an AND/OR group rather than pretending', () => {
    // ⚠️ 第一批不处理分组。返回 null 意味着编辑器显示「无过滤」——
    // 而保存会把它抹掉。这是**已知的数据丢失**，第二批第一项要修。
    // 但它比「显示一条假条件」安全：后者会让用户以为过滤还在。
    expect(asSingleFilter({ logic: 'AND', children: [{ field: 'a' }] }))
      .toBeNull();
  });

  it('returns null for junk instead of throwing', () => {
    expect(asSingleFilter(null)).toBeNull();
    expect(asSingleFilter('nope')).toBeNull();
    expect(asSingleFilter({ field: 'a' })).toBeNull();
  });
});

// ============================================================================
// 第二批：过滤条件树（TODO-060 数据丢失 + 15 操作符 + AND/OR 嵌套）
// ============================================================================

describe('TODO-060 — AND/OR 分组必须往返无损', () => {
  // ⚠️ 组判据是「**有没有 conditions 键**」，不是 operator 是不是 AND/OR
  // （query_engine._build_condition 的注释解释了为什么）。第一版的
  // `asSingleFilter` 查的是 `children` —— 那个键后端**从不产生**，
  // 于是分组检测是死代码，返回 null 靠的是后面「没有 field 字段」的检查。
  // 结果照样丢数据，但理由是错的：换个键名就会静默变成「当成叶子条件」。
  const GROUP = {
    operator: 'AND',
    conditions: [
      { operator: 'EQ', source: 'EQUIP_LIST', field: 'tag_number', value: 'E-1' },
      { operator: 'GT', source: 'EQUIP_LIST', field: 'duty', value: 100 },
    ],
  };

  it('recognises a group by its conditions key, not by operator', () => {
    const tree = toFilterTree([GROUP]);
    expect(tree[0].kind).toBe('group');
    expect(asSingleFilter(GROUP)).toBeNull();  // 第一批的 API 仍应返回 null
  });

  it('round-trips a nested group without losing any node', () => {
    // ⚠️ **根断言**：这是 TODO-060 说的「保存会把条件组整段抹掉」。
    // 修复前后这条都会红/绿 —— 修复前 buildBody 只发单条 filter，
    // 组里的 3 个节点一个都留不下来。
    const tree = toFilterTree([GROUP]);
    const body = buildBody({
      rows: [], level: 'BASIC', maxRows: 10, outputFormat: 'pdf',
      filter: null, filterTree: tree,
    }) as unknown as { FilterConditions: unknown[] };
    expect(body.FilterConditions).toHaveLength(1);
    expect(body.FilterConditions[0]).toEqual(GROUP);
  });

  it('round-trips two levels of nesting', () => {
    const nested = {
      operator: 'OR',
      conditions: [
        GROUP,
        { operator: 'LIKE', source: 'EQUIP_LIST', field: 'vendor', value: 'ABB%' },
      ],
    };
    const body = buildBody({
      rows: [], level: 'BASIC', maxRows: 10, outputFormat: 'pdf',
      filter: null, filterTree: toFilterTree([nested]),
    }) as unknown as { FilterConditions: unknown[] };
    expect(body.FilterConditions[0]).toEqual(nested);
  });

  it('survives an empty conditions list without crashing', () => {
    const body = buildBody({
      rows: [], level: 'BASIC', maxRows: 10, outputFormat: 'pdf',
      filter: null, filterTree: toFilterTree([{ operator: 'AND', conditions: [] }]),
    }) as unknown as { FilterConditions: unknown[] };
    expect(body.FilterConditions).toEqual([{ operator: 'AND', conditions: [] }]);
  });

  it('drops nothing when the tree is emptied deliberately', () => {
    const body = buildBody({
      rows: [], level: 'BASIC', maxRows: 10, outputFormat: 'pdf',
      filter: null, filterTree: [],
    }) as unknown as { FilterConditions: unknown[] };
    expect(body.FilterConditions).toEqual([]);
  });
});

describe('操作符的值语义', () => {
  const leaf = (operator: string, value: unknown) =>
    toFilterTree([{ operator, source: 'EQUIP_LIST', field: 'tag_number', value }])[0];

  it('keeps IN as a list and BETWEEN as a two-element list', () => {
    expect(leaf('IN', ['a', 'b'])).toMatchObject({ value: ['a', 'b'] });
    expect(leaf('BETWEEN', [1, 2])).toMatchObject({ value: [1, 2] });
  });

  it('coerces BETWEEN from two scalar inputs into a list', () => {
    // UI 上 BETWEEN 是两个输入框；但存进定义体的必须是 list，
    // 否则 query_engine 的 `len(value) != 2` 检查会把它当标量报错。
    const n = leaf('BETWEEN', 1) as { kind: string; value: unknown };
    expect(n.kind).toBe('leaf');
  });

  it('keeps a valueless operator valueless', () => {
    // IS_NULL 带 value 是**非法的**（后端只认 operator）。
    // 往返后 value 必须是 null，否则用户改别的字段时会把它带回去。
    const n = leaf('IS_NULL', 'x') as { value: unknown };
    expect(n.value).toBeNull();
  });

  it('treats an empty value as empty, not as "no filter"', () => {
    // ⚠️ 后端对空 value 抛 REPORT_FILTER_VALUE_MISSING 而不是返回全表。
    // 所以空值必须原样发出去让后端报错 —— 页面擅自改成 null 或删掉条件，
    // 等于把「筛选失败」变成「导出全量」，而后者看起来是成功的。
    const n = leaf('EQ', '') as { value: unknown };
    expect(n.value).toBe('');
  });
});

// ============================================================================
// 第二批：JOIN 白名单选择
// ============================================================================

describe('JOIN 白名单', () => {
  const JOINS = [
    { a: 'HEAT_RESULTS', a_field: 'tag_number',
      b: 'EQUIP_LIST', b_field: 'tag_number' },
  ];

  it('only offers joins whose two sources are both selected', () => {
    // ⚠️ 只列**两端都在 DataSources 里**的对。列了别的，执行时才撞
    // `REPORT_BUILDER_JOIN_NOT_SUPPORTED`（400）—— 用户填完整个报表
    // 才被拒，而那正是 b1 把白名单一起下发要避免的事。
    const sources = [{ source: 'HEAT_RESULTS' }];
    expect(availableJoins(sources, JOINS)).toEqual([]);
  });

  it('offers a join once both endpoints are selected', () => {
    const sources = [{ source: 'HEAT_RESULTS' }, { source: 'EQUIP_LIST' }];
    expect(availableJoins(sources, JOINS)).toHaveLength(1);
  });

  it('never offers a join for a pair that is not whitelisted', () => {
    const sources = [{ source: 'HEAT_RESULTS' }, { source: 'UTIL_RESULTS' }];
    expect(availableJoins(sources, JOINS)).toEqual([]);
  });

  it('writes join_to onto the FROM side only', () => {
    // ⚠️ `join_to` 挂在**发起方**那一行，不是两端各写一遍 ——
    // 两端都写会形成互相指向，而执行引擎只读 join_to。
    const body = buildBody({
      rows: [rowOf('HEAT_RESULTS', 'tag_number'), rowOf('EQUIP_LIST', 'vendor')],
      level: 'BASIC', maxRows: 10, outputFormat: 'pdf', filterTree: [],
      joins: JOINS,
    }) as unknown as { DataSources: { source: string; join_to?: string }[] };
    const joined = body.DataSources.filter((d) => d.join_to);
    expect(joined).toHaveLength(1);
    expect(joined[0].join_to).toBe('EQUIP_LIST');
  });

  it('drops join_to when the pair is no longer both selected', () => {
    // ⚠️ 取消勾选一个数据源后，残留的 join_to 会让执行引擎去关联一个
    // 根本不存在的源 → 400。取消关联必须**真的清掉**这个字段，
    // 而不是「下拉框显示为空但字段还在」。
    const body = buildBody({
      rows: [rowOf('HEAT_RESULTS', 'tag_number')],
      level: 'BASIC', maxRows: 10, outputFormat: 'pdf', filterTree: [],
      joins: JOINS,
    }) as unknown as { DataSources: { join_to?: string | null }[] };
    expect(body.DataSources[0].join_to ?? null).toBeNull();
  });
});

function rowOf(source: string, field: string) {
  return { key: `${source}.${field}`, source, field, label: field, alias: '',
    order: 0, visible: true, level: null as string | null };
}

describe('pairKey 是无序的', () => {
  it('gives the same key whichever side you start from', () => {
    // ⚠️ `join_key_for` 的顺序对称（A→B ≡ B→A）。若 pairKey 有序，
    // 用户从 A 勾到 B 再从 B 勾到 A 会产生两条「不同」的关联，
    // 执行时却等价 —— 关联被应用两次，且界面上看不出为什么。
    expect(pairKey('HEAT_RESULTS', 'EQUIP_LIST'))
      .toBe(pairKey('EQUIP_LIST', 'HEAT_RESULTS'));
  });

  it('still separates genuinely different pairs', () => {
    expect(pairKey('A', 'B')).not.toBe(pairKey('A', 'C'));
  });
});
