/**
 * `summarizeSchSeries` —— 把 `sch_series_json`（DN → Sch 映射）压成
 * 列表页能直接显示的摘要。**用户裁决（2026-10-19）**，配套 bug-180。
 *
 * ## 为什么是共享模块而不是页面里的一行
 *
 * 「这个等级的壁厚在 DN 范围内统一吗」是**领域问题**，不是展示问题。
 * 三个消费者：列表页（现在）、将来的 Excel 导出、将来按壁厚搜索。
 * 写在页面里的后果很具体：页面显示「按 DN 分档」而导出写「Sch 40」。
 * 边界（空映射 / 单条 / 大小写不一致）也只该写一次。
 *
 * ## 四个边界（用户逐条点名）
 *
 * 1. **空映射** `{}` → `EMPTY`。朴素写法 `set().size === 1` 为假，
 *    会落到「有多个档位」分支 —— 但实际上**一个档位都没有**。
 *    空必须与「多档」区分开：页面显示 `—`，不是「按 DN 分档」。
 * 2. **单条目** `{"50":"Sch 40"}` → `UNIFORM` 显示 `Sch 40`。
 *    语义上它也是分档，但只有一档时具体值比「按 DN 分档」更有信息量。
 * 3. **键顺序无关** → 用 `Set(values)`，天然满足。
 * 4. **大小写/空白不归一**：`{"50":"Sch 40","100":"sch 40"}` 判为 `VARIED`。
 *    这**不是** bug，是刻意的：混用大小写是数据质量问题，
 *    归一化会把它掩盖成「统一」。宁可显示「按 DN 分档」让用户去查。
 */
import { describe, it, expect } from 'vitest';

import {
  schSummaryText,
  schSummaryTooltip,
  summarizeSchSeries,
} from '../../src/lib/pipeClassSch';

describe('summarizeSchSeries — 边界', () => {
  it('空映射 → EMPTY（不是「按 DN 分档」）', () => {
    const s = summarizeSchSeries({});
    expect(s.kind).toBe('EMPTY');
    expect(s.count).toBe(0);
    expect(s.uniformValue).toBeNull();
    expect(s.ranges).toBeNull();
  });

  it('null / undefined / 非对象 → EMPTY（契约标 optional，别让页面炸）', () => {
    expect(summarizeSchSeries(null).kind).toBe('EMPTY');
    expect(summarizeSchSeries(undefined).kind).toBe('EMPTY');
    expect(summarizeSchSeries('x' as unknown as Record<string, string>).kind).toBe('EMPTY');
  });

  it('单条目 → UNIFORM 且带值', () => {
    const s = summarizeSchSeries({ '50': 'Sch 40' });
    expect(s.kind).toBe('UNIFORM');
    expect(s.uniformValue).toBe('Sch 40');
    expect(s.count).toBe(1);
  });

  it('多 DN 同值 → UNIFORM（与键顺序无关）', () => {
    expect(summarizeSchSeries({ '50': 'Sch 40', '100': 'Sch 40' }).kind).toBe('UNIFORM');
    expect(summarizeSchSeries({ '100': 'Sch 40', '50': 'Sch 40' }).kind).toBe('UNIFORM');
  });

  it('多值 → VARIED，且**不归一化大小写/空白**', () => {
    // 混用大小写是数据质量问题 —— 归一化会把它掩盖成「统一」
    const mixed = summarizeSchSeries({ '50': 'Sch 40', '100': 'sch 40' });
    expect(mixed.kind).toBe('VARIED');
    expect(summarizeSchSeries({ '50': 'Sch 40', '100': ' Sch 40' }).kind).toBe('VARIED');
  });
});

describe('summarizeSchSeries — VARIED 的区间合并', () => {
  it('连续同 Sch 的 DN 合并成一段', () => {
    const s = summarizeSchSeries({
      '50': 'Sch 40', '100': 'Sch 40', '150': 'Sch 80',
    });
    expect(s.kind).toBe('VARIED');
    expect(s.ranges).toEqual([
      ['50', '100', 'Sch 40'],
      ['150', '150', 'Sch 80'],
    ]);
  });

  it('**非**连续的同值不合并（中间隔了别的档）', () => {
    const s = summarizeSchSeries({
      '50': 'Sch 40', '100': 'Sch 80', '150': 'Sch 40',
    });
    expect(s.ranges).toEqual([
      ['50', '50', 'Sch 40'],
      ['100', '100', 'Sch 80'],
      ['150', '150', 'Sch 40'],
    ]);
  });

  it('按 DN **数值**排序，不是字符串字典序', () => {
    // 字符串排序会把 '100' 排在 '50' 前面 —— DN 是数字
    const s = summarizeSchSeries({
      '100': 'Sch 80', '50': 'Sch 40', '25': 'Sch 40',
    });
    expect(s.ranges).toEqual([
      ['25', '50', 'Sch 40'],
      ['100', '100', 'Sch 80'],
    ]);
  });

  it('非数字 DN 键排在数字之后，保持相对顺序（不丢数据）', () => {
    const s = summarizeSchSeries({
      'X': 'Sch 80', '50': 'Sch 40', 'abc': 'Sch 90',
    });
    expect(s.kind).toBe('VARIED');
    expect(s.ranges).toEqual([
      ['50', '50', 'Sch 40'],
      ['X', 'X', 'Sch 80'],
      ['abc', 'abc', 'Sch 90'],
    ]);
  });

  it('count 是总档数，不是区间数', () => {
    const s = summarizeSchSeries({
      '50': 'Sch 40', '100': 'Sch 40', '150': 'Sch 80', '200': 'Sch 80',
    });
    expect(s.count).toBe(4);
    expect(s.ranges).toHaveLength(2);
  });
});

describe('schSummaryText —— 单元格文案（用户裁决的措辞）', () => {
  it('EMPTY → 「—」', () => {
    expect(schSummaryText(summarizeSchSeries({}))).toBe('—');
  });

  it('UNIFORM → 具体值', () => {
    expect(schSummaryText(summarizeSchSeries({ '50': 'Sch 40', '100': 'Sch 40' })))
      .toBe('Sch 40');
  });

  it('VARIED → 「按 DN 分档」，**不是**「多档」', () => {
    // 「多档」在中文里会被读成「多个可选档位」——
    // 而 sch_series_json 是「每个 DN 对应一个 Sch」的函数，不是可选集合。
    // 用户裁决改成「按 DN 分档」：它暗示分档依据是 DN，
    // 与 Tooltip 的 DN50→Sch 40 自然衔接。
    const text = schSummaryText(summarizeSchSeries({ '50': 'Sch 40', '100': 'Sch 80' }));
    expect(text).toBe('按 DN 分档');
    expect(text).not.toContain('多档');
  });
});

describe('schSummaryTooltip —— 按区间，不是逐条映射', () => {
  it('单段不写重复的 DN 范围', () => {
    const s = summarizeSchSeries({ '50': 'Sch 40', '100': 'Sch 80', '150': 'Sch 80' });
    expect(schSummaryTooltip(s)).toBe('Sch 40 (DN50) / Sch 80 (DN100–150)');
  });

  it('≤3 段全列', () => {
    const s = summarizeSchSeries({
      '10': 'Sch 10', '25': 'Sch 40', '50': 'Sch 40', '100': 'Sch 80',
    });
    const tip = schSummaryTooltip(s);
    expect(tip).not.toContain('…');
    expect(tip.split(' / ')).toHaveLength(3);   // 合并后 3 段，未超阈值
  });

  it('>3 段截断为前 2 段 + 总档数', () => {
    const s = summarizeSchSeries({
      '10': 'Sch 10', '25': 'Sch 20', '50': 'Sch 30', '100': 'Sch 40', '150': 'Sch 50',
    });
    const tip = schSummaryTooltip(s);
    expect(tip).toBe('Sch 10 (DN10) / Sch 20 (DN25) / … 共 5 档');
  });

  it('总档数用 count（DN 条目数），不是区间数', () => {
    const s = summarizeSchSeries({
      '10': 'Sch 10', '25': 'Sch 10', '50': 'Sch 10',
      '100': 'Sch 20', '150': 'Sch 20', '200': 'Sch 20', '300': 'Sch 30',
    });
    expect(s.count).toBe(7);
    expect(s.ranges).toHaveLength(3);
    // 3 段刚好不触发默认截断（阈值 3），故显式压低阈值来观察 count
    const tip = schSummaryTooltip(s, { maxToShow: 1, truncateAbove: 2 });
    expect(tip).toContain('共 7 档');   // 7 个 DN 条目，不是 3 个区间
    expect(tip).not.toContain('共 3 档');
  });

  it('非 VARIED 无 Tooltip', () => {
    expect(schSummaryTooltip(summarizeSchSeries({}))).toBe('');
    expect(schSummaryTooltip(summarizeSchSeries({ '50': 'Sch 40' }))).toBe('');
  });
});
