import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { ConfigProvider } from 'antd';

import { ProjectWizardPage } from '../../../src/pages/wizard/ProjectWizardPage';
import type { WizardStep } from '../../../src/types/pms';

function renderPage(
  initialSteps: WizardStep[],
  initialProjectName = '',
  onStepDone?: (idx: number, done: boolean) => void,
  onFinish?: (name: string) => void,
) {
  return render(
    <ConfigProvider>
      <ProjectWizardPage
        initialSteps={initialSteps}
        initialProjectName={initialProjectName}
        onStepDone={onStepDone}
        onFinish={onFinish}
      />
    </ConfigProvider>,
  );
}

const STEPS: WizardStep[] = [
  { step_index: 0, title: '项目', description: '基础信息', done: false },
  { step_index: 1, title: 'PMS', description: '材料规格', done: false },
  { step_index: 2, title: 'BEDD', done: false },
];

describe('ProjectWizardPage', () => {
  it('renders page header and steps', () => {
    renderPage(STEPS);
    expect(screen.getByTestId('project-wizard-page')).toBeInTheDocument();
    expect(screen.getByText('新建项目向导')).toBeInTheDocument();
    expect(screen.getByTestId('wizard-steps')).toBeInTheDocument();
  });

  it('shows project name input on first step', () => {
    renderPage(STEPS);
    expect(screen.getByTestId('wizard-step-project-name')).toBeInTheDocument();
    expect(screen.getByTestId('wizard-project-name-input')).toBeInTheDocument();
  });

  it('navigates forward with next button', () => {
    renderPage(STEPS);
    expect(screen.getByText(/步骤 1 \/ 3/)).toBeInTheDocument();
    fireEvent.click(screen.getByTestId('wizard-next'));
    expect(screen.getByText(/步骤 2 \/ 3/)).toBeInTheDocument();
  });

  it('disables prev on first step', () => {
    renderPage(STEPS);
    expect(screen.getByTestId('wizard-prev')).toBeDisabled();
  });

  it('navigates back with prev button', () => {
    renderPage(STEPS);
    fireEvent.click(screen.getByTestId('wizard-next'));
    fireEvent.click(screen.getByTestId('wizard-prev'));
    expect(screen.getByText(/步骤 1 \/ 3/)).toBeInTheDocument();
  });

  it('toggles done checkbox and fires onStepDone', () => {
    const onStepDone = vi.fn();
    renderPage(STEPS, '', onStepDone);
    const cb = screen.getByTestId('wizard-step-done');
    fireEvent.click(cb);
    expect(onStepDone).toHaveBeenCalledWith(0, true);
  });

  it('shows finish button on last step', () => {
    const doneSteps: WizardStep[] = STEPS.map((s) => ({ ...s, done: true }));
    renderPage(doneSteps, 'demo-project');
    fireEvent.click(screen.getByTestId('wizard-next'));
    fireEvent.click(screen.getByTestId('wizard-next'));
    expect(screen.getByTestId('wizard-finish')).toBeInTheDocument();
    expect(screen.queryByTestId('wizard-next')).not.toBeInTheDocument();
  });

  it('disables finish when not all steps done', () => {
    const mixedSteps: WizardStep[] = [
      { ...STEPS[0], done: true },
      { ...STEPS[1], done: true },
      STEPS[2],
    ];
    renderPage(mixedSteps, 'demo-project');
    fireEvent.click(screen.getByTestId('wizard-next'));
    fireEvent.click(screen.getByTestId('wizard-next'));
    expect(screen.getByTestId('wizard-finish')).toBeDisabled();
  });

  it('disables finish when project name empty', () => {
    const doneSteps: WizardStep[] = STEPS.map((s) => ({ ...s, done: true }));
    renderPage(doneSteps, '');
    fireEvent.click(screen.getByTestId('wizard-next'));
    fireEvent.click(screen.getByTestId('wizard-next'));
    expect(screen.getByTestId('wizard-finish')).toBeDisabled();
  });

  it('fires onFinish when finish clicked with valid state', () => {
    const onFinish = vi.fn();
    const doneSteps: WizardStep[] = STEPS.map((s) => ({ ...s, done: true }));
    renderPage(doneSteps, 'my-project', undefined, onFinish);
    fireEvent.click(screen.getByTestId('wizard-next'));
    fireEvent.click(screen.getByTestId('wizard-next'));
    fireEvent.click(screen.getByTestId('wizard-finish'));
    expect(onFinish).toHaveBeenCalledWith('my-project');
  });

  it('updates project name on input change', () => {
    renderPage(STEPS);
    const input = screen.getByTestId('wizard-project-name-input') as HTMLInputElement;
    fireEvent.change(input, { target: { value: 'new-name' } });
    expect(input.value).toBe('new-name');
  });

  it('shows empty state when no steps', () => {
    renderPage([]);
    expect(screen.getByText('无步骤')).toBeInTheDocument();
  });

  it('renders step title in card title', () => {
    renderPage(STEPS);
    expect(screen.getByText(/步骤 1 \/ 3 · 项目/)).toBeInTheDocument();
  });

  it('uses initial project name on mount', () => {
    renderPage(STEPS, 'preset-name');
    const input = screen.getByTestId('wizard-project-name-input') as HTMLInputElement;
    expect(input.value).toBe('preset-name');
  });
});