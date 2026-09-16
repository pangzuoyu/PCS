/**
 * CodeFormatDesignerPage 测试（P45-3-2 / Task 29）。
 *
 * 覆盖 SPEC §7.9.4：
 * - 段渲染：separator + value 输入
 * - 上下移动按钮改变顺序
 * - 删除按钮移除段
 * - 添加按钮新增段
 * - 实时预览拼接结果
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';

import { CodeFormatDesignerPage } from '../../../src/pages/pipe_class/CodeFormatDesignerPage';
import type { CodeFormatSegment } from '../../../src/types/pipeClass';

const baseSegments: CodeFormatSegment[] = [
  { order: 0, field: 'material', separator: '-' },
  { order: 1, field: 'size', separator: '-' },
  { order: 2, field: 'schedule', separator: '-' },
];

describe('CodeFormatDesignerPage — 渲染 (P45-3-2)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('渲染 3 段 + 预览', () => {
    render(
      <CodeFormatDesignerPage
        segments={baseSegments}
        sample={{ material: 'A106-B', size: 'DN50', schedule: 'Sch 40' }}
      />,
    );
    const rows = document.querySelectorAll('[data-testid="code-format-segment-row"]');
    expect(rows.length).toBe(3);
    const preview = screen.getByTestId('code-format-preview');
    expect(preview.textContent).toContain('A106-B');
    expect(preview.textContent).toContain('DN50');
    expect(preview.textContent).toContain('Sch 40');
  });

  it('空 segments → 显示「暂无段」', () => {
    render(<CodeFormatDesignerPage segments={[]} />);
    expect(document.body.textContent).toContain('暂无段');
  });
});

describe('CodeFormatDesignerPage — 操作', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('点击「添加段」→ onChange 新增 1 段', () => {
    const onChange = vi.fn();
    render(<CodeFormatDesignerPage segments={baseSegments} onChange={onChange} />);
    fireEvent.click(screen.getByTestId('code-format-segment-add'));
    expect(onChange).toHaveBeenCalledTimes(1);
    expect(onChange.mock.calls[0][0].length).toBe(4);
  });

  it('点击「删除」→ onChange 减少 1 段', () => {
    const onChange = vi.fn();
    render(<CodeFormatDesignerPage segments={baseSegments} onChange={onChange} />);
    const delButtons = document.querySelectorAll('[data-testid="code-format-segment-delete"]');
    fireEvent.click(delButtons[0]);
    expect(onChange).toHaveBeenCalledTimes(1);
    expect(onChange.mock.calls[0][0].length).toBe(2);
  });

  it('点击「上移」→ 第 0 段与第 1 段交换', () => {
    const onChange = vi.fn();
    render(<CodeFormatDesignerPage segments={baseSegments} onChange={onChange} />);
    const upButtons = document.querySelectorAll('[data-testid="code-format-segment-up"]');
    fireEvent.click(upButtons[1]); // 段 1 上移
    expect(onChange).toHaveBeenCalledTimes(1);
    const newOrder = onChange.mock.calls[0][0] as CodeFormatSegment[];
    expect(newOrder[0].field).toBe('size');
    expect(newOrder[1].field).toBe('material');
  });

  it('点击「下移」→ 第 0 段与第 1 段交换', () => {
    const onChange = vi.fn();
    render(<CodeFormatDesignerPage segments={baseSegments} onChange={onChange} />);
    const downButtons = document.querySelectorAll('[data-testid="code-format-segment-down"]');
    fireEvent.click(downButtons[0]); // 段 0 下移
    expect(onChange).toHaveBeenCalledTimes(1);
    const newOrder = onChange.mock.calls[0][0] as CodeFormatSegment[];
    expect(newOrder[0].field).toBe('size');
    expect(newOrder[1].field).toBe('material');
  });

  it('修改 separator → 预览立即更新', () => {
    const onChange = vi.fn();
    render(
      <CodeFormatDesignerPage
        segments={baseSegments}
        sample={{ material: 'A106-B' }}
        onChange={onChange}
      />,
    );
    const sepInputs = document.querySelectorAll('[data-testid="code-format-segment-separator"]');
    fireEvent.change(sepInputs[0], { target: { value: '/' } });
    expect(onChange).toHaveBeenCalledTimes(1);
    expect((onChange.mock.calls[0][0][0] as CodeFormatSegment).separator).toBe('/');
  });
});