/**
 * HashBadge 测试（P45-1-3 / Task 8）。
 *
 * 覆盖（SPEC §6.4 + plan P45-1-3 status 扩展）：
 * - 短哈希：前 4 + … + 后 4（hash>8 字符时）
 * - 短哈希全显（hash≤8 字符时）
 * - label 前缀显示
 * - 等宽字体（style.fontFamily 含 monospace）
 * - 完整 hash 通过 title 属性悬浮显示
 * - 复制按钮点击 → navigator.clipboard.writeText + 视觉反馈
 * - copyable=false 不渲染按钮
 * - status=match/mismatch/affected/未指定 → 对应 token 颜色
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';

import { HashBadge } from '../../../src/components/common/HashBadge';

const SAMPLE_HASH_64 =
  'a3f9c1b2d4e5f67890abcdef1234567890fedcba0987654321abcdef0123456789';

describe('HashBadge — 短哈希 + label + 字体 (P45-1-3)', () => {
  it('64 字符 hash：前 4 + … + 后 4', () => {
    render(<HashBadge hash={SAMPLE_HASH_64} />);
    const short = screen.getByTestId('hash-badge-short');
    expect(short.textContent).toBe('a3f9…6789');
  });

  it('≤8 字符 hash：全显无省略', () => {
    render(<HashBadge hash="abcd1234" />);
    expect(screen.getByTestId('hash-badge-short').textContent).toBe('abcd1234');
  });

  it('完整 hash 通过 title 属性悬浮显示', () => {
    render(<HashBadge hash={SAMPLE_HASH_64} />);
    expect(screen.getByTestId('hash-badge-short').getAttribute('title')).toBe(SAMPLE_HASH_64);
  });

  it('data-hash 持有完整值（测试 / debug 钩子）', () => {
    render(<HashBadge hash={SAMPLE_HASH_64} />);
    expect(screen.getByTestId('hash-badge').getAttribute('data-hash')).toBe(SAMPLE_HASH_64);
  });

  it('label 前缀显示', () => {
    render(<HashBadge hash={SAMPLE_HASH_64} label="current" />);
    const label = screen.getByTestId('hash-badge-label');
    expect(label.textContent).toBe('current:');
  });

  it('无 label 时不渲染 hash-badge-label', () => {
    render(<HashBadge hash={SAMPLE_HASH_64} />);
    expect(screen.queryByTestId('hash-badge-label')).toBeNull();
  });

  it('等宽字体（fontFamily 含 monospace）', () => {
    render(<HashBadge hash={SAMPLE_HASH_64} />);
    const containerStyle = screen.getByTestId('hash-badge').getAttribute('style') || '';
    expect(containerStyle).toContain('var(--font-mono');
    expect(containerStyle).toContain('monospace');
  });
});

describe('HashBadge — 复制按钮', () => {
  beforeEach(() => {
    if (!navigator.clipboard) {
      Object.defineProperty(navigator, 'clipboard', {
        value: { writeText: vi.fn().mockResolvedValue(undefined) },
        configurable: true,
      });
    } else {
      vi.spyOn(navigator.clipboard, 'writeText').mockResolvedValue(undefined);
    }
  });

  it('copyable 默认 true → 渲染「复制」按钮', () => {
    render(<HashBadge hash={SAMPLE_HASH_64} />);
    const btn = screen.getByTestId('hash-badge-copy');
    expect(btn.textContent).toBe('复制');
  });

  it('点击复制 → 调用 clipboard.writeText(完整 hash)', async () => {
    render(<HashBadge hash={SAMPLE_HASH_64} />);
    fireEvent.click(screen.getByTestId('hash-badge-copy'));
    await waitFor(() => {
      expect(navigator.clipboard.writeText).toHaveBeenCalledWith(SAMPLE_HASH_64);
    });
  });

  it('点击后视觉反馈「✓ 已复制」', async () => {
    render(<HashBadge hash={SAMPLE_HASH_64} />);
    fireEvent.click(screen.getByTestId('hash-badge-copy'));
    await waitFor(() => {
      expect(screen.getByTestId('hash-badge').getAttribute('data-copied')).toBe('true');
    });
    expect(screen.getByTestId('hash-badge-copy').textContent).toBe('✓ 已复制');
  });

  it('copyable=false → 不渲染复制按钮', () => {
    render(<HashBadge hash={SAMPLE_HASH_64} copyable={false} />);
    expect(screen.queryByTestId('hash-badge-copy')).toBeNull();
  });
});

describe('HashBadge — status 着色', () => {
  it('match → var(--state-checked)', () => {
    render(<HashBadge hash={SAMPLE_HASH_64} status="match" />);
    expect(screen.getByTestId('hash-badge').getAttribute('data-status')).toBe('match');
    const style = screen.getByTestId('hash-badge').getAttribute('style') || '';
    expect(style).toContain('var(--state-checked)');
  });

  it('mismatch → var(--state-check-rejected)', () => {
    render(<HashBadge hash={SAMPLE_HASH_64} status="mismatch" />);
    const style = screen.getByTestId('hash-badge').getAttribute('style') || '';
    expect(style).toContain('var(--state-check-rejected)');
  });

  it('affected → var(--state-change-pending)', () => {
    render(<HashBadge hash={SAMPLE_HASH_64} status="affected" />);
    const style = screen.getByTestId('hash-badge').getAttribute('style') || '';
    expect(style).toContain('var(--state-change-pending)');
  });

  it('未指定 status → 中性色 var(--text-secondary)', () => {
    render(<HashBadge hash={SAMPLE_HASH_64} />);
    expect(screen.getByTestId('hash-badge').getAttribute('data-status')).toBe('none');
    const style = screen.getByTestId('hash-badge').getAttribute('style') || '';
    expect(style).toContain('var(--text-secondary');
  });
});