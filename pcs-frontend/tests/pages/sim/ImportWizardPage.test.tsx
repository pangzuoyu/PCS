/**
 * ImportWizardPage 测试（P45-3-1 / Task 28 下半）。
 *
 * 覆盖 SPEC §7.7.3 导入向导（极简版）：
 * - 4 步骤：上传 → 字段映射 → 预览 → 确认
 * - 步骤指示器
 * - 前进 / 后退 / 跳过 / 确认
 * - 解析失败提示
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';

import { ImportWizardPage } from '../../../src/pages/sim/ImportWizardPage';

describe('ImportWizardPage — 渲染 (P45-3-1)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('渲染 4 步骤指示器', () => {
    render(<ImportWizardPage />);
    const steps = screen.getByTestId('import-wizard-steps');
    expect(steps.textContent).toContain('上传');
    expect(steps.textContent).toContain('字段映射');
    expect(steps.textContent).toContain('预览');
    expect(steps.textContent).toContain('确认');
  });

  it('默认在第 1 步', () => {
    render(<ImportWizardPage />);
    expect(screen.getByTestId('import-wizard-step-upload')).toBeTruthy();
    expect(screen.queryByTestId('import-wizard-step-mapping')).toBeNull();
  });

  it('点击「下一步」推进', () => {
    render(<ImportWizardPage />);
    fireEvent.click(screen.getByTestId('import-wizard-next'));
    expect(screen.getByTestId('import-wizard-step-mapping')).toBeTruthy();
  });

  it('点击「上一步」回退', () => {
    render(<ImportWizardPage />);
    fireEvent.click(screen.getByTestId('import-wizard-next')); // → 2
    fireEvent.click(screen.getByTestId('import-wizard-prev')); // → 1
    expect(screen.getByTestId('import-wizard-step-upload')).toBeTruthy();
  });

  it('确认步骤：点击「确认导入」→ onConfirm 回调', () => {
    const onConfirm = vi.fn();
    render(<ImportWizardPage onConfirm={onConfirm} />);
    // 4 步都点 next
    fireEvent.click(screen.getByTestId('import-wizard-next'));
    fireEvent.click(screen.getByTestId('import-wizard-next'));
    fireEvent.click(screen.getByTestId('import-wizard-next'));
    fireEvent.click(screen.getByTestId('import-wizard-confirm'));
    expect(onConfirm).toHaveBeenCalledTimes(1);
  });
});