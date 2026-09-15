/**
 * ConflictResolver 测试（P45-1-9 / Task 14）。
 *
 * 覆盖（SPEC §6.10 + plan P45-1-9）：
 * - 渲染 conflicts 卡片（level / 用户值 / 计算值 / 偏差 / 优先级）
 * - 三级颜色 tag：BLOCK red / WARN orange / INFO blue
 * - 字段优先级：molecular_weight → 计算值优先；其他 → 用户值优先
 * - [采用用户值] / [采用计算值] → onResolve(field, choice)
 * - 空 conflicts：「无冲突」占位
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';

import { ConflictResolver, type Conflict } from '../../../src/components/common/ConflictResolver';

const conflicts: Conflict[] = [
  {
    field: 'molecular_weight',
    field_label: '分子量冲突',
    level: 'BLOCK',
    user_value: 58.12,
    calc_value: 58.08,
    user_unit: 'kg/kmol',
    deviation_pct: '0.07%',
  },
  {
    field: 'density',
    field_label: '密度冲突',
    level: 'WARN',
    user_value: 850,
    calc_value: 845,
    user_unit: 'kg/m³',
    deviation_pct: '0.59%',
  },
  {
    field: 'bp',
    field_label: '沸点冲突',
    level: 'INFO',
    user_value: 350,
    calc_value: 348,
    user_unit: '°C',
  },
];

describe('ConflictResolver — 渲染 (P45-1-9)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('空 conflicts 显示「无冲突」', () => {
    render(<ConflictResolver conflicts={[]} />);
    expect(screen.getByText('无冲突')).toBeTruthy();
  });

  it('3 卡片渲染', () => {
    const { container } = render(<ConflictResolver conflicts={conflicts} />);
    const cards = container.querySelectorAll('[data-testid="conflict-card"]');
    expect(cards.length).toBe(3);
  });

  it('卡片含级别 tag + 字段标签 + 用户/计算值/偏差', () => {
    const { container } = render(<ConflictResolver conflicts={[conflicts[0]]} />);
    const card = container.querySelector('[data-testid="conflict-card"]');
    expect(card?.getAttribute('data-conflict-level')).toBe('BLOCK');
    expect(card?.getAttribute('data-conflict-field')).toBe('molecular_weight');
    expect(screen.getByText('分子量冲突')).toBeTruthy();
    expect(container.querySelector('[data-testid="conflict-user"]')?.textContent)
      .toContain('58.12');
    expect(container.querySelector('[data-testid="conflict-calc"]')?.textContent)
      .toContain('58.08');
    expect(container.querySelector('[data-testid="conflict-deviation"]')?.textContent)
      .toContain('0.07%');
  });

  it('三级 tag 颜色：BLOCK red / WARN orange / INFO blue', () => {
    const { container } = render(<ConflictResolver conflicts={conflicts} />);
    const tags = container.querySelectorAll('[data-testid="conflict-level"]');
    expect(tags[0].getAttribute('class') || '').toMatch(/ant-tag-red/);
    expect(tags[1].getAttribute('class') || '').toMatch(/ant-tag-orange/);
    expect(tags[2].getAttribute('class') || '').toMatch(/ant-tag-blue/);
  });
});

describe('ConflictResolver — 字段优先级', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('molecular_weight → 计算值优先（hint: 计算值优先 + 计算值按钮 primary）', () => {
    const { container } = render(<ConflictResolver conflicts={[conflicts[0]]} />);
    expect(container.querySelector('[data-testid="conflict-priority-hint"]')?.textContent)
      .toContain('计算值优先');
    // type="primary" 给 calc
    const calcBtn = container.querySelector('[data-testid="choose-calc"]');
    expect(calcBtn?.getAttribute('class') || '').toMatch(/ant-btn-primary/);
    const userBtn = container.querySelector('[data-testid="choose-user"]');
    expect(userBtn?.getAttribute('class') || '').not.toMatch(/ant-btn-primary/);
  });

  it('density（其他字段）→ 用户值优先（hint: 用户值优先 + 用户按钮 primary）', () => {
    const { container } = render(<ConflictResolver conflicts={[conflicts[1]]} />);
    expect(container.querySelector('[data-testid="conflict-priority-hint"]')?.textContent)
      .toContain('用户值优先');
    const userBtn = container.querySelector('[data-testid="choose-user"]');
    expect(userBtn?.getAttribute('class') || '').toMatch(/ant-btn-primary/);
  });
});

describe('ConflictResolver — 联动', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('[采用用户值] → onResolve(field, "USER")', () => {
    const onResolve = vi.fn();
    const { container } = render(
      <ConflictResolver conflicts={conflicts} onResolve={onResolve} />,
    );
    // 第一个卡是分子量 conflict → 采用用户值
    const btns = container.querySelectorAll('[data-testid="choose-user"]');
    fireEvent.click(btns[0]);
    expect(onResolve).toHaveBeenCalledWith('molecular_weight', 'USER');
  });

  it('[采用计算值] → onResolve(field, "CALC")', () => {
    const onResolve = vi.fn();
    const { container } = render(
      <ConflictResolver conflicts={[conflicts[1]]} onResolve={onResolve} />,
    );
    const calcBtn = container.querySelector('[data-testid="choose-calc"]');
    fireEvent.click(calcBtn!);
    expect(onResolve).toHaveBeenCalledWith('density', 'CALC');
  });

  it('不传 onResolve 不报错', () => {
    const { container } = render(<ConflictResolver conflicts={conflicts} />);
    expect(() =>
      fireEvent.click(container.querySelector('[data-testid="choose-user"]')!),
    ).not.toThrow();
  });
});

describe('ConflictResolver — total_mass_flow/molar_flow 计算值优先', () => {
  it('total_mass_flow → 计算值优先', () => {
    const c: Conflict = {
      field: 'total_mass_flow',
      level: 'WARN',
      user_value: 100,
      calc_value: 100.5,
    };
    const { container } = render(<ConflictResolver conflicts={[c]} />);
    expect(container.querySelector('[data-testid="conflict-priority-hint"]')?.textContent)
      .toContain('计算值优先');
  });

  it('total_molar_flow → 计算值优先', () => {
    const c: Conflict = {
      field: 'total_molar_flow',
      level: 'WARN',
      user_value: 5,
      calc_value: 5.1,
    };
    const { container } = render(<ConflictResolver conflicts={[c]} />);
    expect(container.querySelector('[data-testid="conflict-priority-hint"]')?.textContent)
      .toContain('计算值优先');
  });
});