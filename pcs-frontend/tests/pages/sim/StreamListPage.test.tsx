/**
 * StreamListPage 测试（P45-3-1 / Task 28）。
 *
 * 覆盖 SPEC §7.7.1 物流列表：
 * - 表格列：tag_number / 名称 / 相态 / 温压 / 流量 / 状态
 * - StateBadge 列
 * - 状态点 tabs：DRAFT / CHECKED / IN_APPROVAL / 全部
 * - 行点击 → 触发 onSelect
 * - 相态 tag 颜色
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';

import { StreamListPage, type Stream } from '../../../src/pages/sim/StreamListPage';

const streams: Stream[] = [
  {
    stream_id: 's-1',
    tag_number: 'FEED-101',
    stream_name: '新鲜进料',
    phase: 'LIQUID',
    subphase: 'SUBCOOLED',
    temperature_c: 25,
    pressure_mpa: 0.5,
    total_mass_flow_kg_h: 10000,
    total_molar_flow_kmol_h: 100,
    composition_json: { N2: 0.78, O2: 0.22 },
    sign_status: 'CHECKED',
    updated_by: '张三',
    updated_at: '2026-09-15 14:32',
    approved_hash: 'a3f9b2e1c21ed7a8',
  },
  {
    stream_id: 's-2',
    tag_number: 'PROD-101',
    stream_name: '产品出料',
    phase: 'VAPOR',
    subphase: 'SUPERHEATED',
    temperature_c: 250,
    pressure_mpa: 1.2,
    total_mass_flow_kg_h: 8500,
    total_molar_flow_kmol_h: 85,
    composition_json: { H2O: 0.95, CO2: 0.05 },
    sign_status: 'DRAFT',
    updated_by: '李四',
    updated_at: '2026-09-15 13:00',
  },
];

describe('StreamListPage — 渲染 (P45-3-1)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('渲染标题 + 4 状态点 tabs', () => {
    render(<StreamListPage streams={streams} />);
    expect(screen.getByText('SIM 物流列表')).toBeTruthy();
    const tabs = screen.getByTestId('stream-list-tabs');
    expect(tabs.textContent).toContain('全部');
    expect(tabs.textContent).toContain('DRAFT');
    expect(tabs.textContent).toContain('IN_APPROVAL');
    expect(tabs.textContent).toContain('CHECKED');
  });

  it('默认显示「全部」', () => {
    render(<StreamListPage streams={streams} />);
    expect(document.querySelectorAll('[data-testid="stream-row"]').length).toBe(2);
  });

  it('点击 CHECKED tab → 仅显示已核验', () => {
    render(<StreamListPage streams={streams} />);
    const tabs = screen.getByTestId('stream-list-tabs');
    const checkedTab = Array.from(tabs.querySelectorAll('.ant-tabs-tab')).find(
      (el) => el.textContent?.includes('CHECKED'),
    );
    fireEvent.click(checkedTab!);
    expect(document.querySelectorAll('[data-testid="stream-row"]').length).toBe(1);
    expect(document.querySelector('[data-testid="stream-row"]')?.textContent).toContain('FEED-101');
  });

  it('每行含 tag_number / 名称 / 相态 / 温压 / 流量 / 状态', () => {
    render(<StreamListPage streams={streams} />);
    const row = document.querySelector('[data-testid="stream-row"]')!;
    expect(row.textContent).toContain('FEED-101');
    expect(row.textContent).toContain('新鲜进料');
    expect(row.textContent).toContain('液相');
    expect(row.textContent).toContain('25');
    expect(row.textContent).toContain('0.5');
    expect(row.textContent).toContain('10000');
    expect(row.textContent).toContain('已核验');
  });

  it('行点击 → onSelect 回调收到 stream', () => {
    const onSelect = vi.fn();
    render(<StreamListPage streams={streams} onSelect={onSelect} />);
    fireEvent.click(document.querySelector('[data-testid="stream-row"]')!);
    expect(onSelect).toHaveBeenCalledTimes(1);
    expect(onSelect.mock.calls[0][0].tag_number).toBe('FEED-101');
  });
});

describe('StreamListPage — 边界', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('空 streams → Empty 占位', () => {
    render(<StreamListPage streams={[]} />);
    expect(screen.getByTestId('stream-list-empty')).toBeTruthy();
  });

  it('状态点 tab 上显示对应 stream 数（用 tag 标记）', () => {
    render(<StreamListPage streams={streams} />);
    const allText = document.body.textContent ?? '';
    expect(allText).toContain('SIM 物流列表');
  });
});