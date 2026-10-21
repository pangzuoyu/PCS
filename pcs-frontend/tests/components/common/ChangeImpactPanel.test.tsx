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
import { render, screen, fireEvent, waitFor } from '@testing-library/react';

import { ChangeImpactPanel } from '../../../src/components/common/ChangeImpactPanel';

const source = {
  description: '物流 S-101 · 流量 50 → 60 m³/h',
  changed_by: '张三',
  changed_at: '2026-09-15 14:32',
};

/**
 * ⚠️ **`record_type` 用 `RECORD_TYPE_REGISTRY` 的键**（RF-11）——
 * 分类词（`PIPE` / `PUMP` / `UTIL`）后端 `/change-impact` **不认** ⇒ 404。
 *
 * - `PipingResult` / `PumpResult` —— **不在**本批的 6 键映射表里 ⇒ 走 fallback
 *   （默认图标 + **原始键文本**）
 * - `CostEstResult` —— **在**映射表里 ⇒ 显示「成本估算结果」
 */
const records = [
  { record_id: 'r1', record_type: 'PipingResult', tag_number: 'P-101', result_label: '压降结果' },
  { record_id: 'r2', record_type: 'PumpResult', tag_number: 'PU-101', result_label: '扬程结果' },
  { record_id: 'r3', record_type: 'CostEstResult', tag_number: 'CE-001', result_label: '成本估算结果' },
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
    expect(items[0].getAttribute('data-record-type')).toBe('PipingResult');
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

describe('ChangeImpactPanel — record_type 用注册表键（RF-11）', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('未登记在本批映射表的键 ⇒ **默认图标 + 原始键文本**（不崩、不空白、不是「默认分类」）', () => {
    const { container } = render(
      <ChangeImpactPanel changeSource={source} affectedRecords={records} />,
    );
    const types = container.querySelectorAll('[data-testid="affected-type"]');
    expect(types[0].textContent).toContain('PipingResult');
    expect(types[1].textContent).toContain('PumpResult');
    // ⚠️ 不得塌成某个「默认分类」文案
    expect(types[0].textContent).not.toContain('默认');
    expect(types[0].textContent).not.toBe('');
  });

  it('本批映射表里的键 ⇒ 显示**显示名**（不是原始键）', () => {
    const { container } = render(
      <ChangeImpactPanel changeSource={source} affectedRecords={records} />,
    );
    const types = container.querySelectorAll('[data-testid="affected-type"]');
    expect(types[2].textContent).toContain('成本估算结果');
    expect(types[2].textContent).not.toContain('CostEstResult');
  });
});

describe('ChangeImpactPanel — 系统判定 / 人工判定（SPEC §6.7.1）', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('系统判定：NO_CHANGE ⇒ 按钮文案「确认：结果未变」', async () => {
    const onConfirmSystem = vi.fn().mockResolvedValue({
      decision: 'NO_CHANGE',
      requires_re_approval: false,
      message: '结果未变',
    });
    const { container } = render(
      <ChangeImpactPanel
        changeSource={source}
        affectedRecords={records}
        onConfirmSystem={onConfirmSystem}
      />,
    );
    fireEvent.click(container.querySelector('[data-testid="confirm-system"]')!);
    await waitFor(() =>
      expect(screen.getByTestId('confirm-system-r1').textContent).toContain('结果未变'),
    );
    expect(screen.getByTestId('confirm-system-r1').textContent).not.toContain('须重新签署');
  });

  it('系统判定：CHANGED ⇒ 「确认：结果已变」+ 提示「须重新签署」', async () => {
    const onConfirmSystem = vi.fn().mockResolvedValue({
      decision: 'CHANGED',
      requires_re_approval: true,
      message: '结果已变',
    });
    const { container } = render(
      <ChangeImpactPanel
        changeSource={source}
        affectedRecords={records}
        onConfirmSystem={onConfirmSystem}
      />,
    );
    fireEvent.click(container.querySelector('[data-testid="confirm-system"]')!);
    await waitFor(() =>
      expect(screen.getByTestId('confirm-system-r1').textContent).toContain('结果已变'),
    );
    expect(screen.getByTestId('confirm-system-reapproval').textContent).toContain('须重新签署');
  });

  it('⚠️ 人工判定：**reason 为空 ⇒ 不发请求**（后端 422）', async () => {
    const onManualAdjust = vi.fn();
    render(
      <ChangeImpactPanel
        changeSource={source}
        affectedRecords={records}
        onManualAdjust={onManualAdjust}
      />,
    );
    fireEvent.click(screen.getByTestId('manual-adjust-r1'));
    // 确认按钮此时**禁用**（reason 为空）
    await waitFor(() =>
      expect(screen.getByTestId('manual-adjust-ok')).toBeTruthy(),
    );
    expect((screen.getByTestId('manual-adjust-ok') as HTMLButtonElement).disabled).toBe(true);
    expect(onManualAdjust).not.toHaveBeenCalled();
  });

  it('人工判定与系统判定是**两个**端点，不合并', async () => {
    const onConfirmSystem = vi.fn().mockResolvedValue({
      decision: 'NO_CHANGE',
      requires_re_approval: false,
      message: '结果未变',
    });
    const onManualAdjust = vi.fn();
    render(
      <ChangeImpactPanel
        changeSource={source}
        affectedRecords={records}
        onConfirmSystem={onConfirmSystem}
        onManualAdjust={onManualAdjust}
      />,
    );
    // 点人工判定 ⇒ **不**触发系统判定
    fireEvent.click(screen.getByTestId('manual-adjust-r1'));
    expect(onConfirmSystem).not.toHaveBeenCalled();
    expect(onManualAdjust).not.toHaveBeenCalled();
  });
});
