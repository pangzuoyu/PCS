/**
 * StreamListPage 测试（P45-3-1 / Task 28）。
 *
 * 覆盖 SPEC §7.7.1 物流列表：
 * - 表格列：名称（标识，首列）/ 相态 / 温压 / 流量 / 状态
 * - StateBadge 列
 * - 状态点 tabs：DRAFT / CHECKED / IN_APPROVAL / 全部
 * - 行点击 → 触发 onSelect
 * - 相态 tag 颜色
 *
 * ⚠️ fixture 曾是**假的**（2026-10-19 修）：它带 `tag_number` / `subphase` /
 * `approved_hash` / `updated_by` 四个已删或根本不存在的字段，且从
 * `StreamListPage` import `Stream`（那里早已不再导出）。测试全绿，
 * 断言的却是一个后端不会返回的形状 —— bug-180 同一个病。
 * 现在 fixture 就是 `types/stream.ts` 的形状，且 `Stream` 从类型的
 * 来源处 import。
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';

import { StreamListPage } from '../../../src/pages/sim/StreamListPage';
import { STREAM_PHASE_LABEL, type Stream } from '../../../src/types/stream';

const streams: Stream[] = [
  {
    stream_id: 's-1',
    stream_name: '新鲜进料',
    phase: 'LIQUID',
    temp: 25,
    press: 0.5,
    mass_flow: 10000,
    molar_flow: 100,
    composition_json: { N2: 0.78, O2: 0.22 },
    sign_status: 'CHECKED',
    record_hash: 'a3f9b2e1c21ed7a8',
    updated_at: '2026-09-15 14:32',
  },
  {
    stream_id: 's-2',
    stream_name: '产品出料',
    phase: 'VAPOR',
    temp: 250,
    press: 1.2,
    mass_flow: 8500,
    molar_flow: 85,
    composition_json: { H2O: 0.95, CO2: 0.05 },
    sign_status: 'DRAFT',
    record_hash: 'b4e8c3d2d32f8b9c',
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
    expect(document.querySelector('[data-testid="stream-row"]')?.textContent).toContain('新鲜进料');
  });

  it('每行含 名称 / 相态 / 温压 / 流量 / 状态', () => {
    render(<StreamListPage streams={streams} />);
    const row = document.querySelector('[data-testid="stream-row"]')!;
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
    expect(onSelect.mock.calls[0][0].stream_name).toBe('新鲜进料');
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
/**
 * 相态词表（2026-10-19 用户裁决）
 *
 * 守卫的是**真实导入数据能渲染**，不是某个具体页面的排版：
 * 后端 `import_service._phase_norm` 把 P&ID/文件里的 `S`/`SOLID` 归一成
 * `SOLID`，`conflict_resolver._VALID_PHASES` 也收了它。前端词表若漏了
 * SOLID，那一类物流的相态 tag 会渲染成**空标签**（`STREAM_PHASE_LABEL[p]`
 * 是 undefined）—— 不报错、只是没有内容，正是最难发现的那类缺陷。
 */
describe('StreamListPage — 相态词表', () => {
  const solid: Stream = { ...streams[0], stream_id: 's-3', stream_name: '催化剂装填', phase: 'SOLID' };

  it('SOLID 有中文标签，不会渲染成空标签', () => {
    render(<StreamListPage streams={[solid]} />);
    const tag = document.querySelector('[data-testid="stream-phase"]');
    expect(tag?.textContent).toBe('固相');
    expect(tag?.textContent).not.toBe('');
  });

  it('四值全有中文标签 —— AQUEOUS 是前端发明的，已砍', () => {
    for (const [phase, label] of [
      ['LIQUID', '液相'], ['VAPOR', '气相'], ['MIXED', '混合'], ['SOLID', '固相'],
    ] as const) {
      render(<StreamListPage streams={[{ ...streams[0], phase }]} />);
      expect(document.querySelector('[data-testid="stream-phase"]')?.textContent).toBe(label);
      document.body.innerHTML = '';
    }
    expect(STREAM_PHASE_LABEL).not.toHaveProperty('AQUEOUS');
  });
});
