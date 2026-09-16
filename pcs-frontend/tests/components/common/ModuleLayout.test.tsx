/**
 * ModuleLayout 测试（P45-3-0 / Task 27）。
 *
 * 覆盖：
 * - 4 象限 slot：input / result / lineage / syncDevices
 * - 仅 input + result 最小布局
 * - lineage / syncDevices 可选
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';

import { ModuleLayout } from '../../../src/components/common/ModuleLayout';

describe('ModuleLayout — 渲染 (P45-3-0)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('渲染容器 + 4 个 slot', () => {
    render(
      <ModuleLayout
        input={<div data-testid="slot-input">input</div>}
        result={<div data-testid="slot-result">result</div>}
        lineage={<div data-testid="slot-lineage">lineage</div>}
        syncDevices={<div data-testid="slot-sync">sync</div>}
      />,
    );
    expect(screen.getByTestId('module-layout')).toBeTruthy();
    expect(screen.getByTestId('slot-input')).toBeTruthy();
    expect(screen.getByTestId('slot-result')).toBeTruthy();
    expect(screen.getByTestId('slot-lineage')).toBeTruthy();
    expect(screen.getByTestId('slot-sync')).toBeTruthy();
  });

  it('不传 lineage / syncDevices 仍可用', () => {
    render(
      <ModuleLayout
        input={<div data-testid="slot-input">i</div>}
        result={<div data-testid="slot-result">r</div>}
      />,
    );
    expect(screen.getByTestId('slot-input')).toBeTruthy();
    expect(screen.getByTestId('slot-result')).toBeTruthy();
    expect(screen.queryByTestId('slot-lineage')).toBeNull();
    expect(screen.queryByTestId('slot-sync')).toBeNull();
  });
});