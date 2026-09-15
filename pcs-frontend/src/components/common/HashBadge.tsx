/**
 * HashBadge — 记录哈希徽章（P45-1-3 / Task 8）。
 *
 * 与 SPEC §6.4 + plan P45-1-3 扩展 status 一致：
 *   `hash: a3f9…c21e  [复制]`
 *
 * 视觉：
 * - 等宽字体（var(--font-mono, monospace)）
 * - 短哈希：前 4 + … + 后 4
 * - 悬浮 title 显示完整 hash
 * - 复制按钮（默认 on）：点击后写 navigator.clipboard + 视觉反馈「✓ 已复制」
 * - status 着色：
 *   - match    → var(--state-checked)
 *   - mismatch → var(--state-check-rejected)
 *   - affected → var(--state-change-pending)
 *   - 未指定    → var(--text-secondary)
 */
import { useState } from 'react';
import type { CSSProperties, MouseEvent } from 'react';

export type HashBadgeStatus = 'match' | 'mismatch' | 'affected';

export interface HashBadgeProps {
  hash: string;
  label?: string;
  copyable?: boolean;
  status?: HashBadgeStatus;
}

const STATUS_COLOR: Record<HashBadgeStatus | 'none', string> = {
  match: 'var(--state-checked)',
  mismatch: 'var(--state-check-rejected)',
  affected: 'var(--state-change-pending)',
  none: 'var(--text-secondary, #6B7681)',
};

function shortHash(hash: string): string {
  if (hash.length <= 8) return hash;
  return `${hash.slice(0, 4)}…${hash.slice(-4)}`;
}

export function HashBadge({
  hash,
  label,
  copyable = true,
  status,
}: HashBadgeProps): JSX.Element {
  const [copied, setCopied] = useState(false);
  const colorKey = status ?? 'none';
  const color = STATUS_COLOR[colorKey];

  async function handleCopy(e: MouseEvent<HTMLButtonElement>): Promise<void> {
    e.preventDefault();
    e.stopPropagation();
    if (typeof navigator === 'undefined' || !navigator.clipboard) {
      return;
    }
    try {
      await navigator.clipboard.writeText(hash);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1500);
    } catch {
      // 静默：复制失败不抛（permission denied / insecure context）
    }
  }

  const containerStyle: CSSProperties = {
    display: 'inline-flex',
    alignItems: 'center',
    gap: 'var(--space-2, 8px)',
    padding: '2px 6px',
    borderRadius: 'var(--radius-sm, 2px)',
    border: `1px solid ${color}`,
    color,
    background: 'var(--color-bg-container, transparent)',
    fontFamily: 'var(--font-mono, ui-monospace, Menlo, Consolas, monospace)',
    fontSize: 12,
    lineHeight: '18px',
  };

  const hashStyle: CSSProperties = {
    fontFamily: 'inherit',
    color,
  };

  return (
    <span
      data-testid="hash-badge"
      data-status={status ?? 'none'}
      data-copied={String(copied)}
      data-hash={hash}
      style={containerStyle}
    >
      {label && (
        <span data-testid="hash-badge-label" style={{ opacity: 0.7 }}>
          {label}:
        </span>
      )}
      <span
        data-testid="hash-badge-short"
        title={hash}
        style={hashStyle}
      >
        {shortHash(hash)}
      </span>
      {copyable && (
        <button
          type="button"
          data-testid="hash-badge-copy"
          onClick={handleCopy}
          aria-label="复制 hash"
          style={{
            background: 'transparent',
            border: 'none',
            color,
            cursor: 'pointer',
            fontSize: 11,
            padding: '0 4px',
            fontFamily: 'inherit',
          }}
        >
          {copied ? '✓ 已复制' : '复制'}
        </button>
      )}
    </span>
  );
}

export default HashBadge;