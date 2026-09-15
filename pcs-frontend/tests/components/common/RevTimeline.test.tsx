/**
 * RevTimeline 测试（P45-1-11 / Task 16）。
 *
 * 覆盖（SPEC §6.18 + plan P45-1-11）：
 * - 渲染 Rev 列表（最新 Rev 在顶）
 * - 状态 tag：ISSUED_FOR_DESIGN / _REVIEW / _CONSTRUCTION / _USE
 * - AFFECTED 红色 tag + 红 dot
 * - 签署行：角色 + 签署人 + ✓
 * - 快照 hash（前 4+…+后 4）+ [查看] 按钮 → onVersionClick
 * - 空 versions：占位「无 Rev 记录」
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';

import { RevTimeline, type RevVersion } from '../../../src/components/common/RevTimeline';

const versions: RevVersion[] = [
  {
    version_id: 'v-c',
    rev_letter: 'C',
    issued_at: '2026-09-15T14:30:00Z',
    status: 'ISSUED_FOR_CONSTRUCTION',
    signatures: [
      { role: '校核', signer_name: '李四', signed_at: '2026-09-15 14:00' },
      { role: '审核', signer_name: '王五', signed_at: '2026-09-15 14:10' },
      { role: '审定', signer_name: '赵六', signed_at: '2026-09-15 14:20' },
    ],
    snapshot_hash: 'a3f9b2e1c21ed7a8',
    snapshot_hash_full: 'a3f9b2e1c21ed7a8',
  },
  {
    version_id: 'v-b',
    rev_letter: 'B',
    issued_at: '2026-09-10T09:15:00Z',
    status: 'ISSUED_FOR_REVIEW',
    affected: true,
    snapshot_hash: 'b2e1c21ed7a8a3f9',
  },
  {
    version_id: 'v-a',
    rev_letter: 'A',
    issued_at: '2026-09-01T10:00:00Z',
    status: 'ISSUED_FOR_DESIGN',
  },
];

describe('RevTimeline — 渲染 (P45-1-11)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('空 versions 显示「无 Rev 记录」', () => {
    render(<RevTimeline versions={[]} />);
    expect(screen.getByText('无 Rev 记录')).toBeTruthy();
  });

  it('3 Rev 项渲染', () => {
    const { container } = render(<RevTimeline versions={versions} />);
    expect(container.querySelectorAll('[data-testid="rev-item"]').length).toBe(3);
  });

  it('最新 Rev 在顶（C → B → A）', () => {
    const { container } = render(<RevTimeline versions={versions} />);
    const items = container.querySelectorAll('[data-testid="rev-item"]');
    expect(items[0].getAttribute('data-version-id')).toBe('v-c');
    expect(items[1].getAttribute('data-version-id')).toBe('v-b');
    expect(items[2].getAttribute('data-version-id')).toBe('v-a');
  });

  it('状态 tag 颜色：CONSTRUCTION green / REVIEW cyan / DESIGN blue', () => {
    const { container } = render(<RevTimeline versions={versions} />);
    const tags = container.querySelectorAll('[data-testid="rev-status"]');
    expect(tags[0].getAttribute('class') || '').toMatch(/ant-tag-green/); // CONSTRUCTION
    expect(tags[1].getAttribute('class') || '').toMatch(/ant-tag-cyan/); // REVIEW
    expect(tags[2].getAttribute('class') || '').toMatch(/ant-tag-blue/); // DESIGN
  });

  it('AFFECTED 红色 tag + 红 dot', () => {
    const { container } = render(<RevTimeline versions={versions} />);
    expect(container.querySelector('[data-testid="rev-affected"]')).toBeTruthy();
    expect(container.querySelector('[data-testid="rev-affected-dot"]')).toBeTruthy();
  });
});

describe('RevTimeline — 签署行', () => {
  it('签署行渲染「角色 + 签署人 + ✓」', () => {
    const { container } = render(<RevTimeline versions={versions} />);
    const sigs = container.querySelectorAll('[data-testid="rev-signature"]');
    expect(sigs.length).toBe(3);
    expect(sigs[0].textContent).toBe('校核 李四 ✓');
    expect(sigs[1].textContent).toBe('审核 王五 ✓');
    expect(sigs[2].textContent).toBe('审定 赵六 ✓');
  });
});

describe('RevTimeline — 快照 hash', () => {
  it('short hash：前 4 + … + 后 4', () => {
    const { container } = render(<RevTimeline versions={versions} />);
    const hashEl = container.querySelector('[data-testid="rev-snapshot-hash"]');
    // hash 'a3f9b2e1c21ed7a8' → 'a3f9…d7a8'
    expect(hashEl?.textContent).toBe('a3f9…d7a8');
  });

  it('[查看] 按钮 → onVersionClick(version_id)', () => {
    const onVersionClick = vi.fn();
    const { container } = render(
      <RevTimeline versions={versions} onVersionClick={onVersionClick} />,
    );
    const btns = container.querySelectorAll('[data-testid="rev-snapshot-view"]');
    fireEvent.click(btns[0]);
    expect(onVersionClick).toHaveBeenCalledWith('v-c');
    fireEvent.click(btns[1]);
    expect(onVersionClick).toHaveBeenCalledWith('v-b');
  });

  it('不传 onVersionClick 不报错', () => {
    const { container } = render(<RevTimeline versions={versions} />);
    expect(() =>
      fireEvent.click(container.querySelector('[data-testid="rev-snapshot-view"]')!),
    ).not.toThrow();
  });
});

describe('RevTimeline — 边界', () => {
  it('snapshot_hash 太短（≤12）：完整显示', () => {
    const v: RevVersion[] = [
      {
        version_id: 'v-x',
        rev_letter: 'X',
        issued_at: '2026-01-01T00:00:00Z',
        status: 'ISSUED_FOR_DESIGN',
        snapshot_hash: 'short',
      },
    ];
    const { container } = render(<RevTimeline versions={v} />);
    expect(container.querySelector('[data-testid="rev-snapshot-hash"]')?.textContent)
      .toBe('short');
  });
});