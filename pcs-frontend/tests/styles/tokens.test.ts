import { describe, it, expect, beforeAll } from 'vitest';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

/**
 * 校验 tokens.css 完整性：
 * - 9 态色齐全（--state-*）
 * - 关键 semantic token 存在
 * - component token 层（StateBadge 9 态 + Button + Input + Table + Panel）
 * - disabled 态 token（--text-disabled / --bg-disabled / --opacity-disabled）
 */

let tokensCss = '';
beforeAll(() => {
  tokensCss = readFileSync(resolve(__dirname, '../../src/styles/tokens.css'), 'utf-8');
});

const TOKEN_NAMES = [
  /* primitive */
  '--state-draft',
  '--state-in-approval',
  '--state-checked',
  '--state-check-rejected',
  '--state-stale',
  '--state-change-pending',
  '--state-changed',
  '--state-reversal-pending',
  '--state-obsolete',
  '--semantic-success',
  '--semantic-warning',
  '--semantic-danger',
  '--semantic-info',
  /* semantic */
  '--bg-canvas',
  '--bg-panel',
  '--bg-elevated',
  '--bg-inset',
  '--bg-hover',
  '--bg-active',
  '--border-subtle',
  '--border-default',
  '--border-strong',
  '--border-focus',
  '--text-primary',
  '--text-secondary',
  '--text-tertiary',
  '--accent-primary',
  '--accent-hover',
  '--accent-active',
  '--font-ui',
  '--font-mono',
  '--font-cn',
  /* spacing */
  '--space-1',
  '--space-2',
  '--space-3',
  '--space-4',
  '--space-5',
  '--space-6',
  /* radius */
  '--radius-sm',
  '--radius-md',
  '--radius-lg',
  /* shadow */
  '--shadow-focus',
  /* disabled (UI-UX-Pro-Max D-1 Gap 2) */
  '--text-disabled',
  '--bg-disabled',
  '--opacity-disabled',
  /* component StateBadge 9 态 (UI-UX-Pro-Max D-1 Gap 1) */
  '--state-badge-bg-DRAFT',
  '--state-badge-fg-DRAFT',
  '--state-badge-bg-IN_APPROVAL',
  '--state-badge-fg-IN_APPROVAL',
  '--state-badge-bg-CHECKED',
  '--state-badge-fg-CHECKED',
  '--state-badge-bg-CHECK_REJECTED',
  '--state-badge-fg-CHECK_REJECTED',
  '--state-badge-bg-STALE',
  '--state-badge-fg-STALE',
  '--state-badge-bg-CHANGE_PENDING',
  '--state-badge-fg-CHANGE_PENDING',
  '--state-badge-bg-CHANGED',
  '--state-badge-fg-CHANGED',
  '--state-badge-bg-REVERSAL_PENDING',
  '--state-badge-fg-REVERSAL_PENDING',
  '--state-badge-bg-OBSOLETE',
  '--state-badge-fg-OBSOLETE',
  /* component Button */
  '--btn-primary-bg',
  '--btn-primary-bg-hover',
  '--btn-primary-bg-active',
  '--btn-danger-bg',
  /* component Input */
  '--input-bg',
  '--input-border',
  '--input-border-focus',
  /* component Table */
  '--table-header-bg',
  '--table-row-hover-bg',
  /* component Panel */
  '--panel-bg',
  '--panel-border',
];

describe('tokens.css 完整性', () => {
  it.each(TOKEN_NAMES)('定义 token %s', (name) => {
    expect(tokensCss).toMatch(new RegExp(`${name.replace(/[-]/g, '\\-')}\\s*:`));
  });
});

describe('9 态色 hex 格式', () => {
  const NINE_STATES = [
    'draft',
    'in-approval',
    'checked',
    'check-rejected',
    'stale',
    'change-pending',
    'changed',
    'reversal-pending',
    'obsolete',
  ];
  it.each(NINE_STATES)('--state-%s 是 #RRGGBB', (name) => {
    const re = new RegExp(`--state-${name.replace(/[-]/g, '\\-')}\\s*:\\s*(#[0-9A-Fa-f]{6})`);
    expect(tokensCss).toMatch(re);
  });
});

describe('无 TBD / 占位符', () => {
  it('不含 TBD/TODO/FIXME', () => {
    expect(tokensCss).not.toMatch(/\b(TBD|TODO|FIXME|XXX)\b/);
  });
});