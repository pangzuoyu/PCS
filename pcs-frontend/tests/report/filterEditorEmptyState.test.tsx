/**
 * 临时过滤编辑器的**空态文案**必须区分「继承定义」与「用户删光」（评审 #11）。
 *
 * ## 这条文案曾经说谎
 *
 * `tempFilters` 为 `null`（继承）与 `[]`（删光）时，`nodes` 都是 `[]`，
 * 于是编辑器渲染同一句「无过滤条件 —— 执行时将导出全量」。
 * 但继承状态下执行时用的是**定义里的条件**，不是全量 ——
 * 界面在骗人，且**没有任何提示**。
 *
 * 这是 #11 的三处一致性里最容易被漏的一处：
 * 载荷构造（`buildTempFilterPayload`）对了、提示文字对了，
 * 只要编辑器这一处没改，界面照样说谎。
 */
import { describe, it, expect } from 'vitest';
import { render } from '@testing-library/react';

import { FilterTreeEditor } from '../../src/pages/report/FilterTreeEditor';

const FIELDS = [{ value: 'tag_number', source: 'EQUIP_LIST', label: 'EQUIP_LIST · 位号' }];

describe('FilterTreeEditor 空态文案', () => {
  it('inherited=true → 说「使用定义里的原条件」，**不**说导出全量', () => {
    const { container } = render(
      <FilterTreeEditor nodes={[]} inherited onChange={() => {}} fields={FIELDS} />,
    );
    const text = container.textContent ?? '';
    expect(text).toContain('定义里的原条件');
    expect(text).not.toContain('导出全量');
  });

  it('inherited=false → 说「导出全量」（用户确实删光了条件）', () => {
    const { container } = render(
      <FilterTreeEditor nodes={[]} onChange={() => {}} fields={FIELDS} />,
    );
    expect(container.textContent ?? '').toContain('导出全量');
  });

  it('两者的文案**不同** —— 这就是整条裁决的落点', () => {
    const inherited = render(
      <FilterTreeEditor nodes={[]} inherited onChange={() => {}} fields={FIELDS} />,
    ).container.textContent;
    const cleared = render(
      <FilterTreeEditor nodes={[]} onChange={() => {}} fields={FIELDS} />,
    ).container.textContent;
    expect(inherited).not.toBe(cleared);
  });
});
