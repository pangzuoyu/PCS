/**
 * `dataIndex` 的编译期闸（2026-10-19，TODO-041）。
 *
 * ## 要防的失效形态
 *
 * bug-180：管道等级页在生产上整页空白。根因不是断言写错，是
 * `PipeClassListPage` 的列定义读 `dataIndex: 'pipe_class_id'`（手写类型的
 * 字段名），而契约 `PipeClassResponse` 里是 `class_id`。**整列在生产上是空的。**
 *
 * 而这个洞的类型层面成因是：antd 把 `ColumnType<T>['dataIndex']` 定成
 * `string | string[]` —— **不是 `keyof T`**。于是
 * ```ts
 * const columns: ColumnsType<PipeClass> = [{ dataIndex: 'pipe_class_id' }]
 * ```
 * **完全通过类型检查**，而 6 条组件测试全绿（fixture 与被测对象共用同一份
 * 手写类型，互相验证、互不设防）。
 *
 * ⇒ 属性访问（`row.class_name`）是**抓得住**的，`dataIndex` 抓不住 ——
 * 而没有 `render` 的列，值的唯一来源就是 `dataIndex`。
 *
 * ## 为什么用「深 key 路径」而不是只收 `keyof T`
 *
 * antd 支持 `dataIndex: ['result', 'relief_scenario']` 这样的嵌套路径
 * （本仓 `PsvComputePage` 有 4 处）。只用 `keyof T` 会把那 4 处全打红，
 * 于是人很自然地去加 `as` —— 而 `as` 就是把闸拆掉。
 *
 * `DeepKeys<T>` 递归收集整棵树的 key，数组形式要求**每一段都是树中某层的 key**。
 * 它抓不住「段间路径不存在」（`['result','orifice','nope']` 会过，因为 `nope`
 * 若在别层出现过），但能抓住真正的书写错误 —— 而那才是 bug-180 的形态。
 * 已用探针实测：`dataIndex: 'nope'` 与 `['result','nope']` 都红。
 *
 * ## 为什么不写 `readonly`
 *
 * antd 的 `dataIndex` 是**可变**数组（`string[]`）。写成 `readonly DeepKeys<T>[]`
 * 会让 `StrictColumns<T>` 不再可赋值给 `ColumnsType<T>`，`Table` 直接报错 ——
 * 那是把闸变成了障碍，人就会去绕它。可赋值性是这套设计的前提，不是巧合。
 */
import type { ColumnType } from 'antd/es/table';

/**
 * 递归收集 T 的所有层级的 key（含嵌套对象）。
 *
 * ⚠️ **`string extends keyof T` 那一支不能省**（2026-10-19，加它之前闸是失效的）。
 *
 * 契约类型里几乎每张表都有 JSONB 列，openapi-typescript 把它们生成为
 * `{ [key: string]: number }` 之类的**索引签名类型**。而索引签名类型的
 * `keyof` 是 `string | number` —— 递归进去之后并集里就混进了一个 `string`，
 * 于是 `DeepKeys<T>` **塌成 `string`，任何 dataIndex 都合法**。
 *
 * 实测：`PipeClassResponse.allowable_stress_json` 一个字段就足以让
 * `dataIndex: 'pipe_class_id'`（bug-180 的形态）通过类型检查。
 *
 * ⇒ 索引签名容器**不贡献任何 key**（`never`）。代价：无法对 JSONB 列的
 * 子键做路径检查（`['allowable_stress_json', '250']` 会红）—— 那本来就不该
 * 出现在表格 dataIndex 里，需要时用 `render` 显式取。
 */
export type DeepKeys<T> = T extends object
  ? string extends keyof T
    ? never
    : keyof T | { [K in keyof T]-?: DeepKeys<T[K]> }[keyof T]
  : never;

/** `dataIndex` 收窄到「行类型的 key 或由 key 组成的路径」的列定义。 */
export type StrictColumn<T> = Omit<ColumnType<T>, 'dataIndex'> & {
  dataIndex?: DeepKeys<T> | DeepKeys<T>[];
};

/**
 * 列定义数组。**可赋值给 antd 的 `ColumnsType<T>`**，所以
 * `<Table<T> columns={cols} />` 照常工作 —— 换这个类型不需要改任何调用处。
 */
export type StrictColumns<T> = StrictColumn<T>[];

/**
 * 便于在页面里写 `strictColumns<Foo>([...])` 的形式（不写泛型参数时
 * 由实参推断 T）。
 *
 * 本仓页面一律用 `const columns: StrictColumns<Row> = [...]` 的显式形式，
 * 因为**泛型必须显式写出**才能在列数组里引用行类型的成员 ——
 * `columns.map(c => c.dataIndex)` 这类写法在推断出来的 T 上拿不到精确类型。
 */
export function strictColumns<T>(cols: StrictColumns<T>): StrictColumns<T> {
  return cols;
}
