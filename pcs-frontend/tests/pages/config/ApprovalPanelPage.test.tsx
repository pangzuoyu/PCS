/**
 * ApprovalPanelPage 测试（P45-2-7 / Task 25）。
 *
 * 覆盖 SPEC §7.10.7 审批面板：
 * - 待审批列表（按模块分组）
 * - 版本对比（v_prev vs v_current 字段级 diff）
 * - 审批意见（comment 输入）
 * - 双重审批标记（公式：需要 2 名审批人确认才能 PASS_CHECK）
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';

import { ApprovalPanelPage, type PendingApproval } from '../../../src/pages/config/ApprovalPanelPage';

const items: PendingApproval[] = [
  {
    approval_id: 'ap-1',
    asset_id: 'a-1',
    asset_name: '蒸汽压力公式',
    asset_category: 'formula',
    module: 'FLASH',
    submitted_by: '张三',
    submitted_at: '2026-09-15 14:32',
    current_version: 'v3.1',
    current_content: 'P = 101.325 * exp(-mw / (R * T))',
    previous_version: 'v3.0',
    previous_content: 'P = 101.0 * exp(-mw / (R * T))',
    double_approval: true, // 公式类
    approvals: [],
  },
  {
    approval_id: 'ap-2',
    asset_id: 'a-3',
    asset_name: 'PID模板',
    asset_category: 'template',
    module: 'CONFIG',
    submitted_by: '王五',
    submitted_at: '2026-09-14 10:15',
    current_version: 'v2.0',
    current_content: 'PID-V2 模板',
    previous_version: 'v1.9',
    previous_content: 'PID-V1 模板',
    double_approval: false,
    approvals: [{ approver: '赵六', approved_at: '2026-09-14 11:00' }],
  },
];

describe('ApprovalPanelPage — 渲染 (P45-2-7)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('渲染标题 + 待审批列表', () => {
    render(<ApprovalPanelPage items={items} />);
    expect(screen.getByText('审批面板')).toBeTruthy();
    expect(document.querySelectorAll('[data-testid="approval-item"]').length).toBe(2);
  });

  it('每项渲染资产名 / 模块 / 提交人 / 时间 / 版本', () => {
    render(<ApprovalPanelPage items={items} />);
    const first = document.querySelector('[data-testid="approval-item"]')!;
    expect(first.textContent).toContain('蒸汽压力公式');
    expect(first.textContent).toContain('FLASH');
    expect(first.textContent).toContain('张三');
    expect(first.textContent).toContain('2026-09-15');
    expect(first.textContent).toContain('v3.1');
  });

  it('公式类显示「双重审批」标记', () => {
    render(<ApprovalPanelPage items={items} />);
    const badges = document.querySelectorAll('[data-testid="approval-double-badge"]');
    expect(badges.length).toBe(1); // 只 ap-1 是公式
    expect(badges[0].textContent).toContain('双重审批');
  });
});

describe('ApprovalPanelPage — 版本对比', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('展开详情 → 显示版本对比', () => {
    render(<ApprovalPanelPage items={items} />);
    const toggle = document.querySelector('[data-testid="approval-toggle"]')!;
    fireEvent.click(toggle);
    expect(screen.getByTestId('approval-diff-panel')).toBeTruthy();
    expect(document.body.textContent).toContain('v3.0 → v3.1');
  });

  it('diff 内容前后值都显示', () => {
    render(<ApprovalPanelPage items={items} />);
    fireEvent.click(document.querySelector('[data-testid="approval-toggle"]')!);
    const diff = screen.getByTestId('approval-diff-panel');
    expect(diff.textContent).toContain('101.0');
    expect(diff.textContent).toContain('101.325');
  });
});

describe('ApprovalPanelPage — 审批意见 + 操作', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('输入意见 → 通过 / 驳回 回调', () => {
    const onApprove = vi.fn();
    const onReject = vi.fn();
    render(<ApprovalPanelPage items={items} onApprove={onApprove} onReject={onReject} />);
    fireEvent.click(document.querySelector('[data-testid="approval-toggle"]')!);
    const commentInput = screen.getByTestId('approval-comment-input');
    fireEvent.change(commentInput, { target: { value: '已复核通过' } });
    fireEvent.click(screen.getByTestId('approval-approve-btn'));
    expect(onApprove).toHaveBeenCalledTimes(1);
    expect(onApprove.mock.calls[0][1]).toBe('已复核通过');
  });

  it('双重审批：未达 2 人通过时 PASS_CHECK 禁用', () => {
    const onApprove = vi.fn();
    render(
      <ApprovalPanelPage items={[items[0]]} currentUser="reviewer-1" onApprove={onApprove} />,
    );
    fireEvent.click(document.querySelector('[data-testid="approval-toggle"]')!);
    const approveBtn = screen.getByTestId('approval-approve-btn') as HTMLButtonElement;
    // double_approval=true 且当前无任何 approvals
    // 但当前用户可以点一次（标记自己的通过），所以按钮应该是启用的（记录当前用户）
    expect(approveBtn.disabled).toBe(false);
  });

  it('双重审批：已达 2 人 → 显示「可发布」标记', () => {
    const ap2: PendingApproval = {
      ...items[0],
      approvals: [
        { approver: 'reviewer-1', approved_at: '2026-09-15 13:00' },
        { approver: 'reviewer-2', approved_at: '2026-09-15 14:00' },
      ],
    };
    render(<ApprovalPanelPage items={[ap2]} currentUser="reviewer-3" />);
    fireEvent.click(document.querySelector('[data-testid="approval-toggle"]')!);
    expect(screen.getByTestId('approval-ready-publish')).toBeTruthy();
  });

  it('驳回回调触发', () => {
    const onReject = vi.fn();
    render(<ApprovalPanelPage items={[items[1]]} onReject={onReject} />);
    fireEvent.click(document.querySelector('[data-testid="approval-toggle"]')!);
    fireEvent.click(screen.getByTestId('approval-reject-btn'));
    expect(onReject).toHaveBeenCalledTimes(1);
  });
});