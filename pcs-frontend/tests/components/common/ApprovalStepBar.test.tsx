/**
 * ApprovalStepBar 测试（P45-1-2 / Task 7）。
 *
 * 覆盖（SPEC §6.2）：
 * - 3 步渲染（结构 + marker + label + connector）
 * - 当前步骤高亮（kind=current + 脉冲动画 + 蓝色 background）
 * - 已完成（decision=APPROVED → kind=approved + 绿色 border）
 * - 未开始（无 decision + step>currentStep → kind=pending + 灰色 border）
 * - 退回（decision=REJECTED → kind=rejected + 红色 border）
 * - roleLabel / approver / decision 文案
 * - 连接线只在非最后一步
 * - 空 steps 边界（不崩）
 * - totalSteps/role props 接受不消费
 */
import { describe, it, expect } from 'vitest';
import { render, screen, within } from '@testing-library/react';

import { ApprovalStepBar } from '../../../src/components/common/ApprovalStepBar';
import type { ApprovalStep } from '../../../src/components/common/ApprovalStepBar';

const SAMPLE_3_STEPS: ApprovalStep[] = [
  { step: 1, role: 'CHECKER', roleLabel: '①校核' },
  { step: 2, role: 'REVIEWER', roleLabel: '②审核', approver: '李四' },
  { step: 3, role: 'APPROVER', roleLabel: '③审定' },
];

const SAMPLE_WITH_DECISIONS: ApprovalStep[] = [
  { step: 1, role: 'CHECKER', roleLabel: '①校核', approver: '张三', decision: 'APPROVED' },
  { step: 2, role: 'REVIEWER', roleLabel: '②审核' },  // current
  { step: 3, role: 'APPROVER', roleLabel: '③审定' },  // pending
];

const REJECTED_STEPS: ApprovalStep[] = [
  { step: 1, role: 'CHECKER', roleLabel: '①校核', approver: '张三', decision: 'APPROVED' },
  { step: 2, role: 'REVIEWER', roleLabel: '②审核', approver: '李四', decision: 'REJECTED' },
];

describe('ApprovalStepBar — 结构 (P45-1-2)', () => {
  it('3 步渲染：3 个 approval-step + 2 个 connector + 3 个 marker', () => {
    render(<ApprovalStepBar currentStep={1} totalSteps={3} role="CHECKER" steps={SAMPLE_3_STEPS} />);
    expect(screen.getAllByTestId('approval-step')).toHaveLength(3);
    expect(screen.getAllByTestId('approval-step-marker')).toHaveLength(3);
    expect(screen.getAllByTestId('approval-step-label')).toHaveLength(3);
    // 3 步 → 2 个 connector（最后一步无）
    expect(screen.getAllByTestId('approval-step-connector')).toHaveLength(2);
    // 容器 data 属性
    const bar = screen.getByTestId('approval-step-bar');
    expect(bar.getAttribute('data-current-step')).toBe('1');
    expect(bar.getAttribute('data-total-steps')).toBe('3');
  });

  it('roleLabel 中文显示', () => {
    render(<ApprovalStepBar currentStep={1} totalSteps={3} role="CHECKER" steps={SAMPLE_3_STEPS} />);
    expect(screen.getByText('①校核')).toBeTruthy();
    expect(screen.getByText('②审核')).toBeTruthy();
    expect(screen.getByText('③审定')).toBeTruthy();
  });

  it('approver 在 label 块显示', () => {
    render(<ApprovalStepBar currentStep={1} totalSteps={3} role="CHECKER" steps={SAMPLE_3_STEPS} />);
    expect(screen.getByText('李四')).toBeTruthy();
  });

  it('空 steps 不崩（0 步渲染）', () => {
    const { container } = render(
      <ApprovalStepBar currentStep={1} totalSteps={0} role="CHECKER" steps={[]} />,
    );
    expect(container.querySelectorAll('[data-testid="approval-step"]')).toHaveLength(0);
    expect(container.querySelector('[data-testid="approval-step-marker"]')).toBeNull();
  });
});

describe('ApprovalStepBar — marker kind 与 token', () => {
  it('currentStep=2：第 2 步 current（蓝色 + 脉冲 animation），其他 pending', () => {
    render(<ApprovalStepBar currentStep={2} totalSteps={3} role="REVIEWER" steps={SAMPLE_3_STEPS} />);
    const steps = screen.getAllByTestId('approval-step');
    // step 1 pending
    expect(steps[0].getAttribute('data-kind')).toBe('pending');
    // step 2 current
    expect(steps[1].getAttribute('data-kind')).toBe('current');
    // step 3 pending
    expect(steps[2].getAttribute('data-kind')).toBe('pending');

    const markers = screen.getAllByTestId('approval-step-marker');
    // current marker inline style：background=blue + animation
    const currentStyle = markers[1].getAttribute('style') || '';
    expect(currentStyle).toContain('var(--state-in-approval)');
    expect(currentStyle).toMatch(/animation:\s*pcs-pulse/);
    // pending marker：border=gray + background=transparent
    const pendingStyle = markers[0].getAttribute('style') || '';
    expect(pendingStyle).toContain('var(--text-tertiary)');
    expect(pendingStyle).toContain('background: transparent');
  });

  it('已批准步骤 kind=approved（绿色 border）', () => {
    render(<ApprovalStepBar currentStep={2} totalSteps={3} role="REVIEWER" steps={SAMPLE_WITH_DECISIONS} />);
    const steps = screen.getAllByTestId('approval-step');
    expect(steps[0].getAttribute('data-kind')).toBe('approved');
    const marker = screen.getAllByTestId('approval-step-marker')[0];
    expect(marker.getAttribute('style') || '').toContain('var(--state-checked)');
    expect(screen.getByText('已批准')).toBeTruthy();
  });

  it('退回步骤 kind=rejected（红色 border + "已退回" 文案）', () => {
    render(<ApprovalStepBar currentStep={2} totalSteps={3} role="REVIEWER" steps={REJECTED_STEPS} />);
    const steps = screen.getAllByTestId('approval-step');
    // step 1 approved, step 2 rejected（即使 currentStep=2 也被 REJECTED 覆盖）
    expect(steps[0].getAttribute('data-kind')).toBe('approved');
    expect(steps[1].getAttribute('data-kind')).toBe('rejected');
    const marker = screen.getAllByTestId('approval-step-marker')[1];
    expect(marker.getAttribute('style') || '').toContain('var(--state-check-rejected)');
    expect(screen.getByText('已退回')).toBeTruthy();
  });

  it('marker 文本：approved=✓ / current=● / pending=○ / rejected=✕', () => {
    render(<ApprovalStepBar currentStep={2} totalSteps={3} role="REVIEWER" steps={REJECTED_STEPS} />);
    const markers = screen.getAllByTestId('approval-step-marker');
    expect(markers[0].textContent).toBe('✓');
    expect(markers[1].textContent).toBe('✕');
  });
});

describe('ApprovalStepBar — 连接线 / 边界', () => {
  it('连接线只出现在非最后一步', () => {
    render(<ApprovalStepBar currentStep={2} totalSteps={3} role="REVIEWER" steps={SAMPLE_3_STEPS} />);
    const steps = screen.getAllByTestId('approval-step');
    // step 0/1 容器内含 connector（到下一步），step 2 是最后一步无 connector
    expect(within(steps[0]).queryByTestId('approval-step-connector')).toBeTruthy();
    expect(within(steps[1]).queryByTestId('approval-step-connector')).toBeTruthy();
    expect(within(steps[2]).queryByTestId('approval-step-connector')).toBeNull();
    expect(screen.getAllByTestId('approval-step-connector')).toHaveLength(2);
  });

  it('1 步（无 connector）', () => {
    render(
      <ApprovalStepBar
        currentStep={1}
        totalSteps={1}
        role="CHECKER"
        steps={[{ step: 1, role: 'CHECKER', roleLabel: '①校核' }]}
      />,
    );
    expect(screen.getAllByTestId('approval-step')).toHaveLength(1);
    expect(screen.queryByTestId('approval-step-connector')).toBeNull();
  });
});

describe('ApprovalStepBar — data 属性', () => {
  it('data-step / data-role / data-kind 三件套', () => {
    render(<ApprovalStepBar currentStep={1} totalSteps={3} role="CHECKER" steps={SAMPLE_3_STEPS} />);
    const steps = screen.getAllByTestId('approval-step');
    expect(steps[0].getAttribute('data-step')).toBe('1');
    expect(steps[0].getAttribute('data-role')).toBe('CHECKER');
    // currentStep=1 → step 1 是 current（markerKind 逻辑：s.step === currentStep）
    expect(steps[0].getAttribute('data-kind')).toBe('current');
    expect(steps[1].getAttribute('data-step')).toBe('2');
    expect(steps[1].getAttribute('data-role')).toBe('REVIEWER');
    // step 2 在 currentStep=1 时是 pending
    expect(steps[1].getAttribute('data-kind')).toBe('pending');
  });
});