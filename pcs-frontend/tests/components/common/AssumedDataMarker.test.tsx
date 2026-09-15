/**
 * AssumedDataMarker 测试（P45-1-5 / Task 10）。
 *
 * 覆盖（SPEC §6.11 + plan P45-1-5）：
 * - assumed=false → null（不渲染）
 * - assumed=true → 橙色三角 △
 * - Tooltip 文本拼接：reason / value / source（缺省跳过）
 * - 颜色 var(--state-change-pending)
 * - data 属性钩子（reason / source / value）
 */
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';

import { AssumedDataMarker } from '../../../src/components/common/AssumedDataMarker';

describe('AssumedDataMarker (P45-1-5)', () => {
  it('assumed=false → null（不渲染）', () => {
    const { container } = render(<AssumedDataMarker assumed={false} reason="x" />);
    expect(container.querySelector('[data-testid="assumed-data-marker"]')).toBeNull();
  });

  it('assumed=true 渲染 △ + 橙色', () => {
    render(<AssumedDataMarker assumed />);
    const marker = screen.getByTestId('assumed-data-marker');
    expect(marker.textContent).toBe('△');
    const style = marker.getAttribute('style') || '';
    expect(style).toContain('var(--state-change-pending)');
  });

  it('Tooltip 文本：reason + value + source 三段拼接', () => {
    render(
      <AssumedDataMarker
        assumed
        reason="该结果基于假设输入"
        value="17.2 °C"
        source="默认值"
      />,
    );
    // antd Tooltip 在 jsdom 不会渲染 title portal；断言 data-* 与 marker 存在即可
    const marker = screen.getByTestId('assumed-data-marker');
    expect(marker.getAttribute('data-reason')).toBe('该结果基于假设输入');
    expect(marker.getAttribute('data-value')).toBe('17.2 °C');
    expect(marker.getAttribute('data-source')).toBe('默认值');
  });

  it('部分缺省：仅 reason 显示', () => {
    render(<AssumedDataMarker assumed reason="仅原因" />);
    const marker = screen.getByTestId('assumed-data-marker');
    expect(marker.getAttribute('data-reason')).toBe('仅原因');
    expect(marker.getAttribute('data-value')).toBe('');
    expect(marker.getAttribute('data-source')).toBe('');
  });

  it('全部缺省：marker 仍渲染（只是 tooltip 空）', () => {
    render(<AssumedDataMarker assumed />);
    const marker = screen.getByTestId('assumed-data-marker');
    expect(marker).toBeTruthy();
    expect(marker.textContent).toBe('△');
  });

  it('cursor: help 提示可悬浮', () => {
    render(<AssumedDataMarker assumed />);
    const style = screen.getByTestId('assumed-data-marker').getAttribute('style') || '';
    expect(style).toContain('cursor: help');
  });
});