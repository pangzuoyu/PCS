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
  buildBody,
  fieldsAtLevel,
  toRows,
} from '../../src/pages/report/definitionBody';
import type { ReportBuilderDatasource } from '../../src/api/reportBuilder';

const SOURCES: ReportBuilderDatasource[] = [
  {
    key: 'HEAT_RESULTS',
    label: '换热器结果',
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
    }) as unknown as Record<string, unknown[]>;
    expect(body.SelectedFields[0]).not.toHaveProperty('key');
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
