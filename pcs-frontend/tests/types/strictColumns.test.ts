/**
 * `dataIndex` 闸的自检（2026-10-19，TODO-041）。
 *
 * ## 为什么这类「类型闸」需要自检
 *
 * 闸本身是**代码**，不是运行时检查 —— 写错了会静默失效（`any` 泄漏、
 * 泛型推断落空、或直接被 `as` 拆掉）。而 bug-180 正是「一道本该
 * 拦住它的东西没拦住」：6 条测试全绿，页面生产上是空的。
 *
 * ⇒ 本文件不测页面，只测闸。它必须证明：**该红的一定红**。
 *
 * 本文件里的 `@ts-expect-error` 是**断言的一部分** —— 若闸失效，那行不再
 * 报错，`@ts-expect-error` 自己就会变成「未使用的抑制」，`tsc` 报 TS2578。
 * 所以这些用例同时钉住了「闸有效」与「错误信息确实存在」。
 */
import { describe, it, expect } from 'vitest';
import type { ColumnsType } from 'antd/es/table';

import { strictColumns, type StrictColumns } from '../../src/types/strictColumns';
import type { PipeClass } from '../../src/types/pipeClass';
import type { Stream } from '../../src/types/stream';

interface Row {
  class_id: string;
  class_name: string;
  status: string;
  result: {
    relief_scenario: string;
    orifice: { selected_size: number };
  };
}

describe('StrictColumns —— dataIndex 收窄到 key', () => {
  it('合法字段名通过', () => {
    const cols: StrictColumns<Row> = [{ dataIndex: 'class_id', title: '编号' }];
    expect(cols[0].dataIndex).toBe('class_id');
  });

  it('不写 dataIndex（只用 key + render）也通过', () => {
    const cols: StrictColumns<Row> = [{ key: 'x', title: 'X', render: () => null }];
    expect(cols).toHaveLength(1);
  });

  it('bug-180 的形态：拼错的字段名被编译期拒绝', () => {
    const cols: StrictColumns<Row> = [
      // @ts-expect-error 'pipe_class_id' 不在 Row 上
      { dataIndex: 'pipe_class_id', title: '编号' },
    ];
    // 运行期这行当然存在（类型是编译期的）—— 断言的是「tsc 会红」。
    expect(cols[0].dataIndex).toBe('pipe_class_id');
  });

  it('嵌套路径通过（antd 的 dataIndex: [a, b] 形态）', () => {
    const cols: StrictColumns<Row> = [
      { dataIndex: ['result', 'relief_scenario'], title: '场景' },
      { dataIndex: ['result', 'orifice', 'selected_size'], title: '口径' },
    ];
    expect(cols).toHaveLength(2);
  });

  it('嵌套路径里拼错的段也被拒', () => {
    const cols: StrictColumns<Row> = [
      // @ts-expect-error 'typo' 不在 Row 的任何一层
      { dataIndex: ['result', 'typo'], title: 'x' },
    ];
    expect(cols).toHaveLength(1);
  });

  it('⚠️ 已知边界：段间路径不存在时**抓不住**', () => {
    // ['result', 'orifice', 'selected_size'] 是真实路径；
    // 若把它写成 ['class_id', 'class_name']（两个都是合法 key，但不是一条路径），
    // 本闸**不会**报 —— 因为数组形式只校验「每段都是某层的 key」，
    // 不校验「这些段能串成一条路」。
    //
    // 这是有意的取舍：改成严格路径需要 `as const`（4 处），而 `as const`
    // 那种写法一旦为了「让闸闭嘴」而加回 `as`，闸就没了。
    // 真实的书写错误（段名拼错）仍然会被抓住。
    const cols: StrictColumns<Row> = [
      { dataIndex: ['class_id', 'class_name'], title: '不是一条路径' },
    ];
    expect(cols).toHaveLength(1);
  });
});

describe('StrictColumns 与 antd 的兼容性', () => {
  it('⚠️ 可赋值给 antd 的 ColumnsType —— 否则闸会变成障碍，人就会去绕它', () => {
    // 这条是整个设计的前提：换类型后 `<Table columns={cols} />` 必须照常工作。
    // 若 antd 将来把 dataIndex 改成 readonly，这里会红 —— 那时要重新设计，
    // 而不是加 `as any` 绕过。
    const cols: StrictColumns<Row> = [{ dataIndex: 'class_name' }];
    const asAntd: ColumnsType<Row> = cols;
    // 赋过去之后 antd 的类型是 `ColumnType | ColumnGroupType` 联合，
    // 读 dataIndex 需要收窄；这里只关心「赋得进去」，用长度断言。
    expect(asAntd).toHaveLength(1);
  });

  it('strictColumns() 推断出 T', () => {
    const cols = strictColumns<Row>([{ dataIndex: 'status' }]);
    expect(cols[0]?.dataIndex).toBe('status');
  });
});

/**
 * ⚠️ 这条测试钉住一个**曾经让闸完全失效**的坑（2026-10-19）。
 *
 * `DeepKeys<T>` 若递归进索引签名类型（`{ [key: string]: number }`），
 * `keyof` 会塌成 `string | number`，并集里混进 `string`，于是
 * `DeepKeys<T>` **整体塌成 `string`** —— 任何 dataIndex 都合法，闸等于没装。
 *
 * 而契约类型里**几乎每张表都有 JSONB 列**（`allowable_stress_json`、
 * `sch_series_json`…），openapi-typescript 把它们生成为索引签名类型。
 * 实测：`PipeClassResponse.allowable_stress_json` 一个字段就足以让
 * bug-180 的 `dataIndex: 'pipe_class_id'` 通过类型检查。
 *
 * ⇒ 用**真实的契约类型**（不是干净的 interface）测这条，否则测的是
 * 一个比生产环境宽容得多的假类型 —— 那正是本仓反复踩的「fixture 比被测物
 * 干净」陷阱。
 */
describe('DeepKeys 不会被索引签名毒化', () => {
  interface WithJsonb {
    class_name: string;
    /** 契约里 JSONB 列的真实形状 */
    allowable_stress_json: { [key: string]: number };
  }

  it('JSONB 列存在时，拼错的 dataIndex 仍被拒', () => {
    const cols: StrictColumns<WithJsonb> = [
      { dataIndex: 'class_name' },
      // @ts-expect-error 'pipe_class_id' 不在 WithJsonb 上
      { dataIndex: 'pipe_class_id' },
    ];
    expect(cols).toHaveLength(2);
  });

  it('对真实契约类型 PipeClass 同样有效', () => {
    const cols: StrictColumns<PipeClass> = [
      { dataIndex: 'class_name' },
      // @ts-expect-error bug-180 的形态：pipe_class_id 不在契约里
      { dataIndex: 'pipe_class_id' },
    ];
    expect(cols).toHaveLength(2);
  });

  it('真实的 Stream 类型（含多个 JSONB 列）同样有效', () => {
    const cols: StrictColumns<Stream> = [
      { dataIndex: 'stream_name' },
      // @ts-expect-error tag_number 是前端编的字段（bug-189）
      { dataIndex: 'tag_number' },
    ];
    expect(cols).toHaveLength(2);
  });
});
