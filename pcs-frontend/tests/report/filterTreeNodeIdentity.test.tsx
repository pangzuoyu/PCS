/**
 * 过滤条件行必须有**稳定身份**，不能拿数组下标当 React key（评审 #26）。
 *
 * ## 缺陷
 *
 * `FilterTreeEditor` 三处都是 `<Space key={i}>`，而同一行右边就摆着
 * ↑↓ 移动按钮。React 按 key 复用组件实例，于是：
 *
 *   行 A（我正在这一行的输入框里打字） → 点 ↑ → 数据里 A 挪到第二行
 *   → key 仍是 0，**第 0 行的 DOM 实例被复用**（焦点、选区、滚动位置、
 *     打开着的下拉）→ 那一行现在显示的是**原来 B 的内容**
 *
 * 用户看到的是「我明明在编辑 A，A 却自己变成了 B 的字段，值还粘在上面」。
 *
 * ## 为什么断言**焦点**而不是数据
 *
 * 值是受控的（`value={node.value}`），所以**显示的值永远跟着数据走**，
 * 下标 key 也不会让它显示错 —— 只有实例级状态（焦点/选区/滚动/下拉）
 * 会留在错误的行上。断言输入框的值区分不出两种实现；
 * **焦点能**，而且它正是用户真正在意的东西：
 * 「我正在编辑的这一行，被移动后应该仍是那一行」。
 */
import type { JSX } from 'react';

import { describe, it, expect } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { useState } from 'react';

import { FilterTreeEditor } from '../../src/pages/report/FilterTreeEditor';
import {
  newNodeId,
  type FilterNode,
} from '../../src/pages/report/definitionBody';

const FIELDS = [
  { value: 'tag_number', label: '位号', source: 'EQUIP_LIST' },
  { value: 'vendor', label: '制造商', source: 'EQUIP_LIST' },
];

// ⚠️ 必须真的给 id。生产节点由 `toFilterTree` / `addLeaf` 造，都带 id；
// 这里第一版用 `as FilterNode` 断言绕过类型检查造出**无 id** 节点，
// 两行的 key 都是 `undefined` ⇒ React 视作同一 key ⇒ 测试照样红，
// 但症状（focus 掉回 body）与 #26 一模一样 —— **看起来像修复没生效，
// 其实是 fixture 不合法**。`id` 是必填字段，类型系统本该拦住它。
const leaf = (field: string, value: string): FilterNode => ({
  kind: 'leaf', id: newNodeId(),
  source: 'EQUIP_LIST', field, operator: 'EQ', value,
});

/** 受控外壳：每次 onChange 都把新数组喂回去，复刻父组件的受控行为。 */
function Harness({ initial }: { initial: () => FilterNode[] }): JSX.Element {
  const [nodes, setNodes] = useState<FilterNode[]>(initial);
  return <FilterTreeEditor nodes={nodes} onChange={setNodes} fields={FIELDS} />;
}

/** 每一行的「值」输入框（按行序）。 */
function valueInputs(): HTMLInputElement[] {
  return Array.from(
    document.querySelectorAll<HTMLInputElement>('input[placeholder="值"]'),
  );
}

describe('#26 移动条件行后，正在编辑的那一行仍是那一行', () => {
  it('焦点跟着被移动的行走，不留在原下标上', () => {
    render(<Harness initial={() => [
      leaf('tag_number', 'A的值'), leaf('vendor', 'B的值'),
    ]} />);

    const inputs = valueInputs();
    expect(inputs).toHaveLength(2);

    // 焦点在第 0 行（值 A 的值）
    inputs[0].focus();
    expect(document.activeElement).toBe(inputs[0]);

    // 点第 0 行的 **↓**。
    // ⚠️ 不能点 ↑：第 0 行已在顶部，`move(0, -1)` 直接 return ——
    // 第一版就这么写的，症状是「数据没动」（`after[0].value` 仍是 A），
    // 看起来像 key 有问题，其实是按钮选错了行/方向。
    fireEvent.click(screen.getAllByRole('button', { name: '↓' })[0]);

    const after = valueInputs();
    // 数据确实移上去了
    expect(after[0].value).toBe('B的值');
    expect(after[1].value).toBe('A的值');

    // 焦点必须跟着 A 走 —— 现在是第 1 行。
    // 下标 key 的话焦点会留在第 0 行（那个 DOM 实例被复用了），
    // 于是用户还在「编辑」B，内容却跳成了 A。
    expect(document.activeElement).toBe(after[1]);
  });

  it('两行内容完全相同时，移动仍不该错认行', () => {
    // 下标 key 在这里同样出问题；内容派生的 key 也会（两行 key 相同）。
    // ⇒ key 必须来自**节点自身的身份**，不能来自内容、不能来自下标。
    render(<Harness initial={() => [
      leaf('tag_number', '同一个值'), leaf('tag_number', '同一个值'),
    ]} />);
    const inputs = valueInputs();
    inputs[1].focus();
    fireEvent.click(screen.getAllByRole('button', { name: '↑' })[1]);
    // 两行内容相同 ⇒ 数据上看不出有没有动，只能靠焦点所在的下标

    const after = valueInputs();
    expect(after).toHaveLength(2);
    expect(document.activeElement).toBe(after[0]);
  });

  it('删除一行后，其余行的身份不受影响', () => {
    // 删第 0 行 → 后两行上移。
    // 删除按钮只有图标没有可访问名（`<DeleteOutlined/>`），只能按 class 找 ——
    // 这本身是 #26 之外的一条可访问性观察，记在这里备查。
    const { container } = render(<Harness initial={() => [
      leaf('tag_number', 'A'), leaf('vendor', 'B'), leaf('tag_number', 'C'),
    ]} />);
    const delBtns = Array.from(
      container.querySelectorAll<HTMLButtonElement>('button.ant-btn-dangerous'),
    );
    expect(delBtns).toHaveLength(3);
    // 先把焦点放在**第 2 行**（值 C）：删掉第 0 行后它上移到第 1 行，
    // 焦点必须跟着它 —— 下标 key 下这个 DOM 实例会被卸载，焦点掉回 body。
    valueInputs()[2].focus();
    expect(document.activeElement).toBe(valueInputs()[2]);

    fireEvent.click(delBtns[0]);
    const after = valueInputs();
    expect(after.map((i) => i.value)).toEqual(['B', 'C']);
    expect(document.activeElement).toBe(after[1]);
  });
});
