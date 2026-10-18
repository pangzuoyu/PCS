/**
 * 管子等级 `sch_series_json`（DN → Sch 映射）的展示摘要。
 *
 * 契约 `PipeClassResponse.sch_series_json` 是**每个 DN 对应一个 Sch**的映射
 * —— 它是一个**函数**，不是一个可选集合。（这个区别决定了摘要怎么写：
 * 不能说「3 档可选」，要说「哪段 DN 用哪个 Sch」。）
 *
 * ## 为什么不写在页面里
 *
 * 「这个等级在其 DN 范围内壁厚是否统一」是**领域问题**。三个消费者：
 * 管子等级列表页（现在）、将来的 Excel 导出、将来按壁厚搜索/过滤。
 * 写在页面里的后果很具体：页面显示「按 DN 分档」而导出写「Sch 40」。
 *
 * ## 三种摘要
 *
 * | kind | 何时 | 页面显示 |
 * |---|---|---|
 * | `EMPTY` | 映射为空 / 缺字段 | `—` |
 * | `UNIFORM` | 所有 DN 同一个 Sch | 那个值（如 `Sch 40`） |
 * | `VARIED` | 两个以上不同的 Sch | `按 DN 分档` + Tooltip 列区间 |
 *
 * ⚠️ `EMPTY` 必须与 `VARIED` 分开：朴素写法 `new Set(values).size === 1`
 * 对空映射为假，会把「一个档位都没有」说成「按 DN 分档」。
 *
 * ⚠️ **刻意不归一化大小写/空白**：`{"50":"Sch 40","100":"sch 40"}` 判为
 * `VARIED`。混用大小写是数据质量问题，归一化会把它掩盖成「统一」——
 * 用户就永远不知道要去查数据了。宁可显示「按 DN 分档」。
 */

/** `[dn_from, dn_to, sch]` —— dn_from === dn_to 表示单一口径。 */
export type SchRange = [string, string, string];

export type SchSummary =
  | { kind: 'EMPTY'; count: 0; uniformValue: null; ranges: null }
  | { kind: 'UNIFORM'; count: number; uniformValue: string; ranges: null }
  | { kind: 'VARIED'; count: number; uniformValue: null; ranges: SchRange[] };

/** DN 键排序用的数值；非数字键返回 `null`（排在数字之后）。 */
function dnNumeric(dn: string): number | null {
  const n = Number(dn);
  return Number.isFinite(n) ? n : null;
}

/**
 * 把 `{DN: Sch}` 压成 `SchSummary`。
 *
 * 契约里 `sch_series_json` 是可选字段，所以入参允许 `null` / `undefined`
 * / 非对象 —— 都归为 `EMPTY`，页面据此显示 `—`，不必各自判一次。
 */
export function summarizeSchSeries(
  schSeries: Record<string, string> | null | undefined,
): SchSummary {
  if (!schSeries || typeof schSeries !== 'object') {
    return { kind: 'EMPTY', count: 0, uniformValue: null, ranges: null };
  }

  const entries = Object.entries(schSeries);
  if (entries.length === 0) {
    return { kind: 'EMPTY', count: 0, uniformValue: null, ranges: null };
  }

  // 同值判断只看**值的集合**，与键顺序无关。
  // ⚠️ 刻意不做 trim / toLowerCase —— 见文件头「不归一化」一节。
  const distinct = new Set(entries.map(([, sch]) => sch));
  if (distinct.size === 1) {
    const [first] = distinct;
    return {
      kind: 'UNIFORM',
      count: entries.length,
      uniformValue: first,
      ranges: null,
    };
  }

  // 按 DN 数值排序（DN 是数字，字符串排序会把 '100' 排在 '50' 前）。
  // 非数字键排在数字**之后**，彼此保持 Object.entries 的相对顺序 —— 不丢数据。
  const numeric = entries
    .filter(([dn]) => dnNumeric(dn) !== null)
    .sort((a, b) => (dnNumeric(a[0]) as number) - (dnNumeric(b[0]) as number));
  const nonNumeric = entries.filter(([dn]) => dnNumeric(dn) === null);
  const sorted = [...numeric, ...nonNumeric];

  // 合并**连续同值**的 DN 段。非连续同值**不**合并 ——
  // 「DN50 和 DN150 都是 Sch 40，中间是 Sch 80」不是一段。
  const ranges: SchRange[] = [];
  sorted.forEach(([dn, sch], i) => {
    const prev = ranges[ranges.length - 1];
    if (prev && prev[2] === sch && i > 0) {
      prev[1] = dn;               // 延长当前段
    } else {
      ranges.push([dn, dn, sch]); // 开新段
    }
  });

  return { kind: 'VARIED', count: entries.length, uniformValue: null, ranges };
}

/** 摘要的单元格文案。`EMPTY` 走 `—`，与本仓 `_cell_text` 的 NULL 约定一致。 */
export function schSummaryText(s: SchSummary): string {
  if (s.kind === 'EMPTY') return '—';
  if (s.kind === 'UNIFORM') return s.uniformValue;
  return '按 DN 分档';
}

/**
 * 供**搜索**用的可匹配文本：把映射里所有 Sch 值拼起来。
 *
 * 为什么不复用 `schSummaryText` / `schSummaryTooltip`：
 * 列表页的搜索框要能按 `Sch 40` 命中 `{"50":"Sch 40","150":"Sch 80"}` ——
 * 单元格显示的是「按 DN 分档」，拿它去 `includes('Sch 40')` 什么也搜不到。
 * 搜的是**数据**（任意一档的 Sch），不是**摘要**。
 */
export function schSummarySearchText(
  schSeries: Record<string, string> | null | undefined,
): string {
  if (!schSeries || typeof schSeries !== 'object') return '';
  return Object.values(schSeries).join(' ');
}

/**
 * `VARIED` 时的 Tooltip 文本：**按区间**而不是逐条映射。
 *
 * 逐条（`DN50→Sch 40 / DN100→Sch 80 / …`）要用户自己在脑子里拼出区间；
 * 区间（`Sch 40 (DN50–100) / Sch 80 (DN150–300)`）直接回答
 * 「哪段 DN 用哪个 Sch」。
 *
 * 截断规则（用户裁决）：≤3 段全列；>3 段显示**前 2 段** + `…` + 总档数。
 * ⚠️ 「显示几条」与「什么时候截断」是两个数（2 / 3），
 * 第一版用同一个参数 `maxRanges` 兼两者，于是 >3 段时显示了 3 段才截断。
 */
export function schSummaryTooltip(
  s: SchSummary,
  opts: { maxToShow?: number; truncateAbove?: number } = {},
): string {
  if (s.kind !== 'VARIED' || !s.ranges || s.ranges.length === 0) return '';
  const maxToShow = opts.maxToShow ?? 2;
  const truncateAbove = opts.truncateAbove ?? 3;
  const fmt = ([from, to, sch]: SchRange): string => (
    from === to ? `${sch} (DN${from})` : `${sch} (DN${from}–${to})`
  );
  if (s.ranges.length <= truncateAbove) return s.ranges.map(fmt).join(' / ');
  return `${s.ranges.slice(0, maxToShow).map(fmt).join(' / ')} / … 共 ${s.count} 档`;
}
