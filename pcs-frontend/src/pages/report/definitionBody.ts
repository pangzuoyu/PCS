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
import type {
  ReportBuilderDatasource,
  ReportBuilderField,
  ReportDefinitionBody,
} from '../../api/reportBuilder';

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

/** 第一批的过滤条件：至多一条 EQ。 */
export interface SingleFilter {
  source: string;
  field: string;
  operator: string;
  value: string;
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
export function buildBody(input: {
  rows: FieldRow[];
  level: string;
  maxRows: number;
  outputFormat: string;
  filter: SingleFilter | null;
}): ReportDefinitionBody {
  const sources = [...new Set(input.rows.map((r) => r.source))]
    .map((source) => ({ source }));
  const conditions = input.filter
    ? [{
        source: input.filter.source,
        field: input.filter.field,
        operator: input.filter.operator,
        value: input.filter.value,
      }]
    : [];
  return {
    DataSources: sources,
    SelectedFields: input.rows.map((r, i) => ({
      source: r.source,
      field: r.field,
      alias: r.alias,
      order: r.order ?? i,
      visible: r.visible,
    })),
    FilterConditions: conditions,
    SortBy: [],
    MaxRows: input.maxRows,
    OutputFormat: input.outputFormat,
    detailLevel: input.level === 'DETAIL' ? 'DETAIL' : 'BASIC',
  } as unknown as ReportDefinitionBody;
}

/**
 * 定义体里那一项是不是**叶子条件**（而不是 AND/OR 分组）。
 *
 * 第一批不渲染分组 —— 遇到分组返回 `null`，调用方保持 filter 为 `null`。
 *
 * ⚠️ 这是本批的**已知局限**：一份含条件组的定义在编辑器里会显示成
 * 「无过滤条件」，而保存会把它抹掉。这比默默显示一条假条件安全，
 * 但仍是数据丢失 —— 已登记为第二批必须修的第一项。
 * 在此之前**不要**拿这个页面编辑含分组的旧定义。
 */
export function asSingleFilter(node: unknown): SingleFilter | null {
  if (!node || typeof node !== 'object') return null;
  const n = node as Record<string, unknown>;
  if (Array.isArray(n.children)) return null;      // 分组：第二批才处理
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
