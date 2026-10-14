/**
 * 定义体 ⇄ 编辑态的纯函数转换。
 *
 * 刻意独立于页面组件文件：① eslint 的 `react-refresh/only-export-components`
 * 不允许组件文件导出非组件；② 这两个函数是**纯函数**，单测不必渲染组件。
 *
 * ## 为什么转换要单独一层
 *
 * 定义体（`definition_json`）里 `SelectedFields` 只有 `source`/`field` 这样的
 * **键**，而用户在页面上看到的是**中文标签**（`field: "shell_tube_count"`
 * ↔ 标签「管程数」）。转换时从数据源字段树回填标签，保存时又把标签丢掉。
 *
 * 直接在组件里来回塞标签是个常见的坑：标签会**跟着请求体一起发回后端**，
 * 而 `ReportDefSelectedField` 是 `extra="forbid"` → 422。看起来像
 * 「后端坏了」，实际是前端多传了字段。
 */
import type { components } from '../../types/api';
import type {
  ReportBuilderDatasource,
  ReportBuilderField,
  ReportDefinitionBody,
} from '../../api/reportBuilder';

/** 后端的条件节点联合（**直接取自 OpenAPI**，不手写）。
 *
 * 刻意用生成类型而不是自定义 interface：手写的话，「组里少个 conditions」
 * 这类结构性错误要到运行时才发现，而这里会在编译期就红。
 */
export type DefCondition = components['schemas']['ReportDefCondition'];
// ⚠️ 自引用递归联合让 openapi-typescript 生成了 `-Input` / `-Output`
// **两个变体**（同一个 schema 的输入侧与输出侧）。请求体用 `-Input`，
// 响应体用 `-Output`。选错一个的表现是「类型不兼容」，不会静默错。
export type DefFilterGroupIn = components['schemas']['ReportDefFilterGroup-Input'];
export type DefNode = DefCondition | DefFilterGroupIn;

/** 一条已选字段的编辑态（定义体里 `SelectedFields` 的一项 + 显示标签）。
 *
 * ⚠️ `key` 是**客户端行标识**，不进请求体。
 * 用它而不是数组下标当 `rowKey`：antd 已废弃「rowKey 函数取 index」，
 * 而下标在**上下移动行**时会跟着变 —— React 会认为那一行被替换，
 * 正在输入的「显示名」会串到别的字段上。症状是「我改的是管程数，
 * 结果改成了热负荷」，且只在调整顺序后才出现。
 */
export interface FieldRow {
  /** 客户端唯一键，仅用于 React 列表渲染 */
  key: string;
  source: string;
  field: string;
  label: string;
  alias: string;
  order: number;
  visible: boolean;
  level: string | null;
}

/** 第一批的过滤条件：至多一条 EQ。保留给旧的单条调用点。 */
export interface SingleFilter {
  source: string;
  field: string;
  operator: string;
  value: string;
}

/** 可编辑条件的叶子节点。 */
export interface FilterLeaf {
  kind: 'leaf';
  source: string;
  field: string;
  operator: string;
  /** 与后端 `ReportDefCondition.value` 逐字对齐：
   *  `str | float | int | bool | list[str|float|int|bool|None] | None`。
   *  写窄一点（比如 list 只收 string|number）会让「用户勾了布尔字段
   *  再选 IN」在类型上报错，而那个用法是合法的。 */
  value: FilterValue;
}

export type FilterValue =
  | string | number | boolean
  | (string | number | boolean | null)[]
  | null;

/** AND/OR 分组，`conditions` 里可再放组（任意嵌套）。 */
export interface FilterGroup {
  kind: 'group';
  operator: 'AND' | 'OR';
  conditions: FilterNode[];
}

export type FilterNode = FilterLeaf | FilterGroup;

/** 字段选择项：多带一个 `source`，选中字段时能一并定下来源。 */
export interface FieldNodeOption {
  value: string;
  label: string;
  source: string;
}

/** 定义体 → 编辑态行。标签从字段树回填（定义体里没有）。 */
export function toRows(
  body: ReportDefinitionBody,
  sources: ReportBuilderDatasource[],
): FieldRow[] {
  const byKey = new Map(sources.map((s) => [s.key, s.fields]));
  return (body.SelectedFields ?? []).map((sel, i) => {
    const spec = byKey.get(sel.source)?.find((f) => f.name === sel.field);
    return {
      key: `row-${i}-${sel.source}.${sel.field}`,
      source: sel.source,
      field: sel.field,
      label: spec?.label ?? sel.field,
      alias: sel.alias ?? '',
      order: sel.order ?? 0,
      visible: sel.visible ?? true,
      level: spec?.level ?? null,
    };
  });
}

/**
 * 编辑态 → 定义体。
 *
 * ⚠️ **只发一条 EQ**（2026-10-13 用户裁决的分批）。
 * 第二批补：15 操作符全集、AND/OR 嵌套、多条条件、临时调整（不落库）。
 *
 * ⚠️ `label` / `level` **不发给后端** —— 它们是回显用的，
 * 而 `ReportDefSelectedField` 是 `extra="forbid"`。
 */
/**
 * 当前**可选**的 JOIN —— 白名单里两端数据源都已被选中的那些。
 *
 * ⚠️ 只列两端都在的：列了别的，执行时才撞
 * `REPORT_BUILDER_JOIN_NOT_SUPPORTED`（400），用户填完整个报表才被拒。
 * b1 把白名单随字段树一起下发，正是为了「选得了就跑得了」。
 */
export function availableJoins(
  sources: { source: string }[],
  joins: JoinWhitelistEntry[],
): JoinWhitelistEntry[] {
  const chosen = new Set(sources.map((s) => s.source));
  return joins.filter((j) => chosen.has(j.a) && chosen.has(j.b));
}

/**
 * 一对关联的稳定标识。
 *
 * ⚠️ 用**无序对**（排序后拼接）—— `datasource_registry.join_key_for`
 * 的顺序是对称的（A→B 与 B→A 是同一件事）。若用 `"a|b"` 的原始顺序，
 * 用户从 A 勾到 B、再从 B 勾到 A 就会产生两条「不同」的关联，
 * 而执行时它们等价 —— 结果是关联被应用两次。
 */
export const pairKey = (a: string, b: string): string => [a, b].sort().join('↔');

export interface JoinWhitelistEntry {
  a: string;
  a_field: string;
  b: string;
  b_field: string;
  degrade_warn?: string | null;
}

export function buildBody(input: {
  rows: FieldRow[];
  level: string;
  maxRows: number;
  outputFormat: string;
  filter?: SingleFilter | null;
  joins?: JoinWhitelistEntry[];
  /** 条件树。与 `filter` 二选一；同时给时以 `filterTree` 为准
   *  （`filter` 只是单条时的便捷写法）。 */
  filterTree?: FilterNode[];
}): ReportDefinitionBody {
  const chosen = [...new Set(input.rows.map((r) => r.source))];
  // ⚠️ `join_to` 只挂在**发起方**那一行，且**两端都在**时才写。
  // 两端各写一遍会形成互相指向（执行引擎只读 join_to）；只写一半则
  // 会关联一个没被选中的源 → 400。
  const joinMap = new Map<string, string>();
  for (const j of availableJoins(
    chosen.map((source) => ({ source })), input.joins ?? [])) {
    joinMap.set(j.a, j.b);
  }
  const sources = chosen.map((source) => {
    const to = joinMap.get(source);
    return to ? { source, join_to: to } : { source, join_to: null };
  });
  const tree = input.filterTree
    ?? (input.filter
      ? [{ kind: 'leaf' as const, source: input.filter.source,
        field: input.filter.field, operator: input.filter.operator,
        value: input.filter.value } as FilterNode]
      : []);
  const conditions = fromFilterTree(tree);
  return {
    DataSources: sources,
    SelectedFields: input.rows.map((r, i) => ({
      source: r.source,
      field: r.field,
      alias: r.alias,
      order: r.order ?? i,
      visible: r.visible,
    })),
    FilterConditions: conditions as never,
    SortBy: [],
    MaxRows: input.maxRows,
    OutputFormat: input.outputFormat,
    detailLevel: input.level === 'DETAIL' ? 'DETAIL' : 'BASIC',
  } as unknown as ReportDefinitionBody;
}

/**
 * 「有没有 `conditions` 键」= 组的判据。
 *
 * ⚠️ **不是**「operator 是不是 AND/OR」—— `query_engine._build_condition`
 * 专门注释了这个选择：否则 AND 既是分组连接符又是叶子算子，两种身份
 * 混在一个键上，SPEC 哪天加一个叫 AND 的算子就彻底乱。
 *
 * 第一版的 `asSingleFilter` 查的是 `children`，而那个键后端**从不产生**
 * —— 分组检测是**死代码**，返回 null 靠的是后面「没有 field 字段」的检查。
 * 结果照样丢数据，但理由是错的：换个键名就会静默变成「当成叶子条件」。
 */
export function isGroup(node: unknown): boolean {
  return !!node && typeof node === 'object'
    && Array.isArray((node as Record<string, unknown>).conditions);
}

/**
 * 把后端返回的 value 收敛成前端模型的类型。
 *
 * ⚠️ **不改变值本身**，只改类型：数字保持数字、列表保持列表。
 * 擅自把 `"100"` 转成 `100` 会让「用户输入的字符串」与「数字」不可区分，
 * 而 `EQ "100"` 与 `EQ 100` 在 Postgres 里对数值列结果相同、对文本列不同。
 * 类型收敛是必要的（`unknown` 不能进模型），语义转换不是。
 */
function normalizeValue(raw: unknown): FilterValue {
  if (raw === null || raw === undefined) return '';
  if (typeof raw === 'string' || typeof raw === 'number'
    || typeof raw === 'boolean') return raw;
  if (Array.isArray(raw)) {
    return raw.filter((v): v is string | number | boolean | null =>
      v === null || typeof v === 'string' || typeof v === 'number'
      || typeof v === 'boolean');
  }
  return String(raw);
}

/** 不需要 value 的算子（后端 `query_engine._VALUELESS`）。 */
export const VALUELESS_OPERATORS: ReadonlySet<string> =
  new Set(['IS_NULL', 'IS_NOT_NULL']);

/** value 是**列表**的算子（后端 `_LIST_OPS` + BETWEEN）。 */
export const LIST_OPERATORS: ReadonlySet<string> =
  new Set(['IN', 'NOT_IN', 'BETWEEN']);

/**
 * 定义体 → 可编辑的过滤条件树。
 *
 * **递归**：`conditions` 里可以再放组，所以嵌套任意层都读得出来。
 * 往返无损是硬要求（TODO-060）—— 第一批的单条 `filter` 模型读不了组，
 * 保存时把整棵子树丢掉，用户改个别字就把别人的筛选规则抹了。
 */
/**
 * 构造**临时过滤**的请求载荷（评审 #11，用户 2026-10-14 裁决）。
 *
 * ## `null` 与 `[]` 是两件事，绝不可合并
 *
 * - `null`（或 undefined）= 用户没做临时调整 ⇒ **继承定义里的原条件**，
 *   于是**不下发** `filters` 字段。
 * - `[]` = 用户进了编辑器、然后**把所有条件删光** ⇒ **不筛选**（导出全量）。
 *
 * 原实现是 `!tempFilters?.length ? undefined : ...`，两者被压成同一个值：
 * 「显式删光」静默退化成「继承定义」。用户看着编辑器里一条条件都没有，
 * 导出却仍带着定义的条件 —— **界面在骗人，且没有任何提示**。
 *
 * 「删光」必须能表达「不筛选」：临时调整的整个用意就是**能覆盖**定义
 * （SPEC §3.2.2(5)）。一个只能加条件、不能减条件的临时面板是残废的。
 *
 * ## 为什么空数组映射成「空 AND 组」而不是别的
 *
 * 后端 `query_engine.apply_filters` 的 docstring 明写
 * 「空条件组 → `sa.true()`（空过滤器 = 不筛，不是报错）」，
 * 所以 `{operator:'AND', conditions: []}` 就是「不筛选」的正确表达，
 * 且是**已有契约**，不需要后端配合。
 */
export function buildTempFilterPayload(
  tempFilters: FilterNode[] | null | undefined,
): DefNode | undefined {
  if (tempFilters === null || tempFilters === undefined) return undefined;
  if (tempFilters.length === 0) return { operator: 'AND', conditions: [] };
  if (tempFilters.length === 1 && tempFilters[0].kind === 'leaf') {
    return fromFilterTree(tempFilters)[0];
  }
  return { operator: 'AND', conditions: fromFilterTree(tempFilters) };
}

/**
 * 数出 `toFilterTree` 会**丢弃**的节点数（评审 #25，用户裁决：警告）。
 *
 * ## 为什么必须存在
 *
 * `toFilterTree` 对它不认识的节点静默返回 `[]`，而 `buildBody` 随后把
 * 幸存者持久化 —— 打开一个含无法识别条件的定义、改一个无关字段、保存，
 * 那条条件就没了且无任何提示。这正是本模块 :256 声明为硬要求要防的
 * TODO-060 失败形态（「往返无损是硬要求」）。
 *
 * 与 `FilterTreeEditor` 放行空值的取向一致：**丢弃必须可见** ——
 * 那边让后端报 `REPORT_FILTER_VALUE_MISSING`，这里让用户在保存前看到
 * 「本定义含 N 条本页无法识别的条件，保存时会丢弃」。
 *
 * ## 与 toFilterTree 的判据必须逐字一致
 *
 * 判据分叉的话（这里数 1、那里没丢，或反之），警告就会说谎。
 * 所以两边用同一套分支：isGroup → 递归；非对象 / 缺 field / 缺 operator → 丢。
 */
export function countUnparsedFilterNodes(raw: unknown): number {
  if (!Array.isArray(raw)) return 0;   // 顶层非法：没有「节点」可数
  return raw.reduce((acc, node): number => {
    if (!node || typeof node !== 'object') return acc + 1;
    const n = node as Record<string, unknown>;
    if (isGroup(n)) return acc + countUnparsedFilterNodes(n.conditions);
    if (typeof n.field !== 'string' || typeof n.operator !== 'string') return acc + 1;
    return acc;
  }, 0);
}

export function toFilterTree(raw: unknown): FilterNode[] {
  if (!Array.isArray(raw)) return [];
  return raw.flatMap((node): FilterNode[] => {
    if (!node || typeof node !== 'object') return [];
    const n = node as Record<string, unknown>;
    if (isGroup(n)) {
      return [{
        kind: 'group',
        operator: n.operator === 'OR' ? 'OR' : 'AND',
        conditions: toFilterTree(n.conditions),
      }];
    }
    if (typeof n.field !== 'string' || typeof n.operator !== 'string') return [];
    return [{
      kind: 'leaf',
      source: typeof n.source === 'string' ? n.source : 'EQUIP_LIST',
      field: n.field,
      operator: n.operator,
      value: VALUELESS_OPERATORS.has(n.operator)
        ? null
        : normalizeValue(n.value),
    }];
  });
}

/** 可编辑条件树 → 定义体。**与 `toFilterTree` 严格互逆。**
 *
 * ⚠️ 组判据与 `isGroup` 一致（看有没有原样保留 `conditions`），
 * 而不是「operator === 'AND'/'OR'」—— 见 `isGroup` 的注释。
 */
export function fromFilterTree(tree: FilterNode[]): DefNode[] {
  return tree.map((node): DefNode => {
    if (node.kind === 'group') {
      return { operator: node.operator,
        conditions: fromFilterTree(node.conditions) };
    }
    return { operator: node.operator, source: node.source,
      field: node.field, value: node.value };
  });
}

/**
 * 定义体里那一项是不是**叶子条件**（而不是 AND/OR 分组）。
 *
 * 保留给只需要单条的旧调用点；**新代码用 `toFilterTree`** ——
 * 这个函数对分组返回 `null`，用它保存会丢数据（TODO-060 的成因）。
 */
export function asSingleFilter(node: unknown): SingleFilter | null {
  if (!node || typeof node !== 'object' || isGroup(node)) return null;
  const n = node as Record<string, unknown>;
  if (typeof n.field !== 'string' || typeof n.operator !== 'string') return null;
  return {
    source: typeof n.source === 'string' ? n.source : 'EQUIP_LIST',
    field: n.field,
    operator: n.operator,
    value: typeof n.value === 'string' ? n.value : '',
  };
}

/**
 * 该分级下可见的字段（BASIC 看不到 DETAIL 字段）。
 *
 * ⚠️ **不覆盖 `label`**。注册表给的中文标签（`管程数`）是页面上唯一
 * 用户看得懂的东西；用字段名（`shell_tube_count`）覆盖它之后，
 * 整个字段选择器里全是内部键名，用户得逐个猜含义。
 * （这个错误真的犯过一次 —— 覆盖发生在「统一成 `{...f, label: f.name}`」
 * 那一行，看起来像是在做规范化。）
 */
export function fieldsAtLevel(
  sources: ReportBuilderDatasource[],
  level: string,
): ReportBuilderField[] {
  const out: ReportBuilderField[] = [];
  for (const ds of sources) {
    for (const f of ds.fields) {
      if (level === 'BASIC' && f.level === 'DETAIL') continue;
      out.push(f);
    }
  }
  return out;
}
