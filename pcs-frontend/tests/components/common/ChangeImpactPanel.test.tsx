/**
 * ChangeImpactPanel 测试（P45-1-8 / Task 13）。
 *
 * 覆盖（SPEC §6.7 + plan P45-1-8）：
 * - 渲染 changeSource 描述 + 变更人/时间
 * - 渲染 affectedRecords 列表 + 橙色左边框
 * - 单行 checkbox + 全选 checkbox
 * - 单行 [确认重算] → onConfirmRecalc([record_id])
 * - 批量确认重算 → onConfirmRecalc(选中 ids)
 * - 全部暂不处理 → onDefer()
 * - 空 records：底部批量按钮 disabled
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';

import { ChangeImpactPanel } from '../../../src/components/common/ChangeImpactPanel';

const source = {
  description: '物流 S-101 · 流量 50 → 60 m³/h',
  changed_by: '张三',
  changed_at: '2026-09-15 14:32',
};

const records = [
  { record_id: 'r1', record_type: 'PIPE', tag_number: 'P-101', result_label: '压降结果' },
  { record_id: 'r2', record_type: 'PUMP', tag_number: 'PU-101', result_label: '扬程结果' },
  { record_id: 'r3', record_type: 'UTIL', tag_number: 'UTIL-001', result_label: '电耗汇总' },
];

describe('ChangeImpactPanel — 渲染 (P45-1-8)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('渲染面板', () => {
    const { container } = render(
      <ChangeImpactPanel changeSource={source} affectedRecords={records} />,
    );
    expect(container.querySelector('[data-testid="change-impact-panel"]')).toBeTruthy();
  });

  it('渲染 changeSource 描述 + 变更人/时间', () => {
    render(<ChangeImpactPanel changeSource={source} affectedRecords={records} />);
    expect(screen.getByTestId('change-source-description').textContent)
      .toContain('物流 S-101 · 流量 50 → 60 m³/h');
    const meta = screen.getByTestId('change-source-meta').textContent || '';
    expect(meta).toContain('张三');
    expect(meta).toContain('2026-09-15 14:32');
  });

  it('受影响记录数显示', () => {
    render(<ChangeImpactPanel changeSource={source} affectedRecords={records} />);
    expect(screen.getByTestId('affected-count').textContent).toContain('（3）');
  });

  it('每行渲染 type/tag/result', () => {
    const { container } = render(
      <ChangeImpactPanel changeSource={source} affectedRecords={records} />,
    );
    const items = container.querySelectorAll('[data-testid="affected-item"]');
    expect(items.length).toBe(3);
    expect(items[0].getAttribute('data-record-type')).toBe('PIPE');
    expect(items[0].textContent).toContain('P-101');
    expect(items[0].textContent).toContain('压降结果');
  });

  it('行带橙色左边框', () => {
    const { container } = render(
      <ChangeImpactPanel changeSource={source} affectedRecords={records} />,
    );
    const item = container.querySelector('[data-testid="affected-item"]') as HTMLElement;
    const style = item.getAttribute('style') || '';
    expect(style).toMatch(/border-left:\s*4px solid/);
    expect(style).toMatch(/var\(--state-stale/);
  });
});

describe('ChangeImpactPanel — 选择', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('单行 checkbox 切换', () => {
    const { container } = render(
      <ChangeImpactPanel changeSource={source} affectedRecords={records} />,
    );
    // antd Checkbox 把 data-testid 转发到原生 <input> 上
    const checkboxes = container.querySelectorAll(
      'input[data-testid="affected-checkbox"]',
    );
    expect(checkboxes.length).toBe(3);
    fireEvent.click(checkboxes[0]);
    fireEvent.click(checkboxes[1]);
    // batch-confirm 按钮文字应反映选中数
    expect(screen.getByTestId('batch-confirm').textContent).toContain('（2）');
  });

  it('全选 checkbox → 全部勾选', () => {
    const { container } = render(
      <ChangeImpactPanel changeSource={source} affectedRecords={records} />,
    );
    const selectAll = container.querySelector(
      'input[data-testid="select-all"]',
    );
    expect(selectAll).toBeTruthy();
    fireEvent.click(selectAll!);
    expect(screen.getByTestId('batch-confirm').textContent).toContain('（3）');
  });
});

describe('ChangeImpactPanel — 联动', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('单行 [确认重算] → onConfirmRecalc([id])', () => {
    const onConfirmRecalc = vi.fn();
    const { container } = render(
      <ChangeImpactPanel
        changeSource={source}
        affectedRecords={records}
        onConfirmRecalc={onConfirmRecalc}
      />,
    );
    const confirmBtns = container.querySelectorAll('[data-testid="confirm-single"]');
    fireEvent.click(confirmBtns[0]);
    expect(onConfirmRecalc).toHaveBeenCalledWith(['r1']);
  });

  it('批量确认重算 → 传入选中 ids', () => {
    const onConfirmRecalc = vi.fn();
    const { container } = render(
      <ChangeImpactPanel
        changeSource={source}
        affectedRecords={records}
        onConfirmRecalc={onConfirmRecalc}
      />,
    );
    const checkboxes = container.querySelectorAll(
      'input[data-testid="affected-checkbox"]',
    );
    fireEvent.click(checkboxes[0]);
    fireEvent.click(checkboxes[2]);
    fireEvent.click(screen.getByTestId('batch-confirm'));
    expect(onConfirmRecalc).toHaveBeenCalledWith(['r1', 'r3']);
  });

  it('全部暂不处理 → onDefer()', () => {
    const onDefer = vi.fn();
    render(
      <ChangeImpactPanel
        changeSource={source}
        affectedRecords={records}
        onDefer={onDefer}
      />,
    );
    fireEvent.click(screen.getByTestId('defer-all'));
    expect(onDefer).toHaveBeenCalledTimes(1);
  });

  it('不传 onConfirmRecalc / onDefer 不报错', () => {
    const { container } = render(
      <ChangeImpactPanel changeSource={source} affectedRecords={records} />,
    );
    expect(() =>
      fireEvent.click(
        container.querySelector('[data-testid="confirm-single"]')!,
      ),
    ).not.toThrow();
    expect(() => fireEvent.click(screen.getByTestId('defer-all'))).not.toThrow();
  });
});

describe('ChangeImpactPanel — 空数据', () => {
  it('records=[]：受影响记录数=0，批量按钮 disabled', () => {
    render(<ChangeImpactPanel changeSource={source} affectedRecords={[]} />);
    expect(screen.getByTestId('affected-count').textContent).toContain('（0）');
    const btn = screen.getByTestId('batch-confirm') as HTMLButtonElement;
    expect(btn.disabled).toBe(true);
  });
});