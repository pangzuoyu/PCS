/**
 * PageHeader 测试（P45-3-0 / Task 27）。
 *
 * 覆盖（SPEC §6.1 / §7）：
 * - 标题渲染
 * - 状态徽章 slot（StateBadge）
 * - 版本 hash slot（HashBadge）
 * - 操作区 slot（actions）
 * - 右侧 extra slot（步骤条等）
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { Button } from 'antd';

import { PageHeader } from '../../../src/components/common/PageHeader';

describe('PageHeader — 渲染 (P45-3-0)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('渲染标题', () => {
    render(<PageHeader title="FLASH 计算" actions={<Button>操作</Button>} />);
    expect(screen.getByTestId('page-header')).toBeTruthy();
    expect(screen.getByText('FLASH 计算')).toBeTruthy();
  });

  it('状态徽章 slot（status + module）', () => {
    render(
      <PageHeader
        title="X"
        status="DRAFT"
        module="FLASH"
        actions={<span data-testid="action-slot">actions</span>}
      />,
    );
    const badge = document.querySelector('[data-testid="page-header-status"]');
    expect(badge).toBeTruthy();
    expect(badge?.getAttribute('data-status')).toBe('DRAFT');
    expect(badge?.getAttribute('data-module')).toBe('FLASH');
  });

  it('版本 hash slot', () => {
    render(
      <PageHeader
        title="X"
        version={{ hash: 'a3f9b2e1c21ed7a8', label: 'v3.1' }}
        actions={<span>actions</span>}
      />,
    );
    expect(document.querySelector('[data-testid="page-header-version"]')).toBeTruthy();
    expect(document.body.textContent).toContain('v3.1');
    expect(document.body.textContent).toContain('a3f9…d7a8');
  });

  it('不传 status / version 仍渲染', () => {
    render(<PageHeader title="X" actions={<span>actions</span>} />);
    expect(document.querySelector('[data-testid="page-header-status"]')).toBeNull();
    expect(document.querySelector('[data-testid="page-header-version"]')).toBeNull();
  });

  it('操作区 + extra 右侧 slot', () => {
    render(
      <PageHeader
        title="X"
        actions={
          <Button data-testid="action-approve" type="primary">
            提交批准
          </Button>
        }
        extra={<span data-testid="extra-step">Step 2/3</span>}
      />,
    );
    expect(screen.getByTestId('action-approve')).toBeTruthy();
    expect(screen.getByTestId('extra-step')).toBeTruthy();
  });
});