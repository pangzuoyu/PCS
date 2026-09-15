/**
 * StateBadge 测试（P45-1-1 / Task 6）。
 *
 * 覆盖（plan Step 2）：
 * - 9 态渲染（每个状态 1 例）
 * - P3 模块（SIM）只显 4 态 active（其他 opacity 0.4）
 * - IN_APPROVAL + showStep 显示 "Step N/3"
 * - 颜色取自 tokens.css（断言 inline style 含 `var(--state-<kebab>)`；
 *   jsdom 不解析 CSS var，所以走 inline style 字符串 + data-* 属性断言）
 * - size sm/md 字号差异
 * - showIcon 占位字符
 * - depth v0.2 占位（不渲染）
 */
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';

import { StateBadge } from '../../../src/components/common/StateBadge';
import type { RecordSignStatus } from '../../../src/types/records';

const ALL_NINE: RecordSignStatus[] = [
  'DRAFT', 'IN_APPROVAL', 'CHECKED', 'CHECK_REJECTED', 'STALE',
  'CHANGE_PENDING', 'CHANGED', 'REVERSAL_PENDING', 'OBSOLETE',
];

const FOUR_STATE: RecordSignStatus[] = [
  'DRAFT', 'IN_APPROVAL', 'CHECKED', 'CHECK_REJECTED',
];

describe('StateBadge — 9 态全集 (P45-1-1)', () => {
  it.each(ALL_NINE)('renders %s with token + bg + border', (status) => {
    render(<StateBadge status={status} />);
    const el = screen.getByTestId('state-badge');
    const kebab = status.toLowerCase().replace(/_/g, '-');
    expect(el.getAttribute('data-status')).toBe(status);
    expect(el.getAttribute('data-kebab')).toBe(kebab);
    const style = el.getAttribute('style') || '';
    expect(style).toContain(`var(--state-${kebab})`);
    expect(style).toContain(`var(--state-badge-bg-${status}`);
    expect(style).toContain(`var(--state-${kebab})`);
    expect(screen.getByTestId('state-badge-label').textContent).toBeTruthy();
  });
});

describe('StateBadge — 模块激活子集', () => {
  it('SIM module: 4 态 active + 5 态半透明', () => {
    for (const s of FOUR_STATE) {
      const { unmount } = render(<StateBadge status={s} module="SIM" />);
      const el = screen.getByTestId('state-badge');
      expect(el.getAttribute('data-active')).toBe('true');
      const style = el.getAttribute('style') || '';
      expect(style).toMatch(/opacity:\s*1\b/);
      unmount();
    }
    const inactive: RecordSignStatus[] = [
      'STALE', 'CHANGE_PENDING', 'CHANGED', 'REVERSAL_PENDING', 'OBSOLETE',
    ];
    for (const s of inactive) {
      const { unmount } = render(<StateBadge status={s} module="SIM" />);
      const el = screen.getByTestId('state-badge');
      expect(el.getAttribute('data-active')).toBe('false');
      const style = el.getAttribute('style') || '';
      expect(style).toMatch(/opacity:\s*0\.4/);
      unmount();
    }
  });

  it('PIPE/PUMP/PIPE_NET/FLASH 模块同样 4 态子集', () => {
    for (const mod of ['PIPE', 'PUMP', 'PIPE_NET', 'FLASH'] as const) {
      const { unmount } = render(<StateBadge status="STALE" module={mod} />);
      expect(screen.getByTestId('state-badge').getAttribute('data-active')).toBe('false');
      unmount();
    }
  });

  it('CONFIG/DELIVERABLE 模块 9 态全集 active', () => {
    for (const mod of ['CONFIG', 'DELIVERABLE'] as const) {
      for (const s of ['STALE', 'CHANGE_PENDING', 'CHANGED', 'REVERSAL_PENDING', 'OBSOLETE'] as const) {
        const { unmount } = render(<StateBadge status={s} module={mod} />);
        expect(screen.getByTestId('state-badge').getAttribute('data-active')).toBe('true');
        unmount();
      }
    }
  });
});

describe('StateBadge — showStep', () => {
  it('IN_APPROVAL + showStep + step=2 显示 "Step 2/3"', () => {
    render(<StateBadge status="IN_APPROVAL" showStep step={2} />);
    expect(screen.getByTestId('state-badge-label').textContent).toContain('Step 2/3');
  });

  it('IN_APPROVAL + showStep 无 step → 默认 Step 1/3', () => {
    render(<StateBadge status="IN_APPROVAL" showStep />);
    expect(screen.getByTestId('state-badge-label').textContent).toContain('Step 1/3');
  });

  it('CHECKED + showStep 不显示 Step 后缀（非 IN_APPROVAL）', () => {
    render(<StateBadge status="CHECKED" showStep step={2} />);
    expect(screen.getByTestId('state-badge-label').textContent).not.toContain('Step');
  });
});

describe('StateBadge — size / icon / depth', () => {
  it('size=sm → 11px', () => {
    render(<StateBadge status="DRAFT" size="sm" />);
    const style = screen.getByTestId('state-badge').getAttribute('style') || '';
    expect(style).toMatch(/font-size:\s*11px/);
  });

  it('size=md → 12px', () => {
    render(<StateBadge status="DRAFT" size="md" />);
    const style = screen.getByTestId('state-badge').getAttribute('style') || '';
    expect(style).toMatch(/font-size:\s*12px/);
  });

  it('showIcon 渲染占位字符', () => {
    render(<StateBadge status="DRAFT" showIcon />);
    expect(screen.getByTestId('state-badge-icon').textContent).toBe('✎');
  });

  it('depth 接受但不渲染（v0.2 占位）', () => {
    const { container } = render(<StateBadge status="DRAFT" depth={3} />);
    expect(container.querySelector('[data-depth]')).toBeNull();
  });
});