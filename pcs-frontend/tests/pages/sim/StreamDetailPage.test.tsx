/**
 * StreamDetailPage 测试（P45-3-1 / Task 28 下半）。
 *
 * 覆盖 SPEC §7.7.2 物流详情：
 * - PageHeader 复用：状态徽章 + 版本 hash + 操作区
 * - 基础信息 Descriptions
 * - 组成 JSON 表格（组分 + 摩尔分率）
 * - 签署步骤 SignatureMatrix
 * - 操作：返回 / 提交批准 / 弃用
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';

import { StreamDetailPage } from '../../../src/pages/sim/StreamDetailPage';
import type { Stream } from '../../../src/types/stream';

const stream: Stream = {
  stream_id: 's-1',
  tag_number: 'FEED-101',
  stream_name: '新鲜进料',
  phase: 'LIQUID',
  subphase: 'SUBCOOLED',
  temperature_c: 25,
  pressure_mpa: 0.5,
  total_mass_flow_kg_h: 10000,
  total_molar_flow_kmol_h: 100,
  composition_json: { N2: 0.78, O2: 0.21, H2O: 0.01 },
  sign_status: 'CHECKED',
  approved_hash: 'a3f9b2e1c21ed7a8',
  updated_by: '张三',
  updated_at: '2026-09-15 14:32',
};

describe('StreamDetailPage — 渲染 (P45-3-1)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('渲染 PageHeader + tag + 名称', () => {
    render(<StreamDetailPage stream={stream} />);
    expect(screen.getByTestId('page-header')).toBeTruthy();
    expect(document.body.textContent).toContain('FEED-101');
    expect(document.body.textContent).toContain('新鲜进料');
  });

  it('PageHeader 显示状态 + hash', () => {
    render(<StreamDetailPage stream={stream} />);
    const status = document.querySelector('[data-testid="page-header-status"]');
    expect(status?.getAttribute('data-status')).toBe('CHECKED');
    const version = document.querySelector('[data-testid="page-header-version"]');
    expect(version).toBeTruthy();
  });

  it('Descriptions 基础信息：相态/温压/流量', () => {
    render(<StreamDetailPage stream={stream} />);
    const details = screen.getByTestId('stream-detail-descriptions');
    expect(details.textContent).toContain('LIQUID');
    expect(details.textContent).toContain('25');
    expect(details.textContent).toContain('0.5');
    expect(details.textContent).toContain('10000');
  });

  it('组成 JSON 表格：3 组分', () => {
    render(<StreamDetailPage stream={stream} />);
    const compRows = document.querySelectorAll('[data-testid="stream-composition-row"]');
    expect(compRows.length).toBe(3);
    expect(compRows[0].textContent).toContain('N2');
    expect(compRows[0].textContent).toContain('0.78');
  });
});

describe('StreamDetailPage — 操作', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('点击「返回」→ onBack 回调', () => {
    const onBack = vi.fn();
    render(<StreamDetailPage stream={stream} onBack={onBack} />);
    fireEvent.click(screen.getByTestId('stream-detail-back'));
    expect(onBack).toHaveBeenCalledTimes(1);
  });

  it('点击「提交批准」→ onSubmit 回调', () => {
    const onSubmit = vi.fn();
    render(<StreamDetailPage stream={{ ...stream, sign_status: 'DRAFT' }} onSubmit={onSubmit} />);
    fireEvent.click(screen.getByTestId('stream-detail-submit'));
    expect(onSubmit).toHaveBeenCalledTimes(1);
  });
});