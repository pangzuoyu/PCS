/**
 * VesselComputePage 测试（P5-1-4 / Task 5）。
 *
 * 覆盖 SPEC §7.11.3：
 * - PageHeader + 输入表单 + 结果占位
 * - 容器类型 Radio：3 选项（VERTICAL / HORIZONTAL / WITH_DEMISTER）
 * - 计算按钮触发（未选物流 → 错误）
 */
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';

import { VesselComputePage } from '../../../src/pages/vessel/VesselComputePage';

// mock vesselApi + streamApi（OPEN-4-1：Props 注入 OR 自取两条路都覆盖）
vi.mock('../../../src/api/vessel', () => ({
  vesselApi: {
    calculate: vi.fn().mockResolvedValue({
      calc_id: 'v-1',
      calc_type: 'VESSEL',
      record_hash: 'rh-1',
      stream_id: 's-1',
      lineage_ids: [],
      result: {
        V_max_ms: 0.45,
        D_min_m: 1.2,
        liquid_volume_m3: 0.5,
        check_result: 'PASS',
        confidence: 'HIGH',
        Q_orifice_m3_s: 0.04,
        Q_overflow_m3_s: 0.02,
        t_drainage_min: 0.5,
      },
      outlet_stream_id: 'out-v',
      outlet_stream_name: 'OUT-VESSEL-201',
    }),
  },
}));

vi.mock('../../../src/api/stream', () => ({
  streamApi: {
    listByProject: vi.fn().mockResolvedValue([
      { stream_id: 's-1', tag_number: 'FEED-101', stream_name: '进料' },
    ]),
  },
}));

const streams = [
  { stream_id: 's-1', tag_number: 'FEED-101', sign_status: 'CHECKED' },
  { stream_id: 's-2', tag_number: 'PROD-201', sign_status: 'DRAFT' },
];

describe('VesselComputePage — 渲染 (P5-1-4)', () => {
  it('渲染 PageHeader + 输入表单 + 结果占位', () => {
    render(<VesselComputePage streams={streams} />);
    expect(screen.getByTestId('vessel-compute-page')).toBeTruthy();
    expect(screen.getByTestId('vessel-stream-select')).toBeTruthy();
    expect(screen.getByTestId('vessel-type')).toBeTruthy();
    expect(screen.getByTestId('vessel-result-card')).toBeTruthy();
  });

  it('容器类型 Radio：3 选项', () => {
    render(<VesselComputePage streams={streams} />);
    expect(document.body.textContent).toContain('立式容器');
    expect(document.body.textContent).toContain('卧式容器');
    expect(document.body.textContent).toContain('带除沫器');
  });

  it('默认 vessel_type=VERTICAL 时 ρ/流量/K 输入可见', () => {
    render(<VesselComputePage streams={streams} />);
    expect(screen.getByTestId('vessel-rho-L')).toBeTruthy();
    expect(screen.getByTestId('vessel-rho-V')).toBeTruthy();
    expect(screen.getByTestId('vessel-q-L')).toBeTruthy();
    expect(screen.getByTestId('vessel-q-V')).toBeTruthy();
    expect(screen.getByTestId('vessel-K')).toBeTruthy();
  });
});

describe('VesselComputePage — 错误路径 (P5-1-4)', () => {
  it('未选物流 → 点计算 → 显示「请选择物流」', () => {
    render(<VesselComputePage streams={streams} />);
    fireEvent.click(screen.getByTestId('vessel-calculate'));
    expect(screen.getByTestId('vessel-error')).toBeTruthy();
    expect(screen.getByTestId('vessel-error').textContent).toContain('请选择物流');
  });
});

describe('VesselComputePage — OPEN-4-1: 无 Props 时自取 streams + vesselApi', () => {
  it('未传 streams：渲染后 streamApi.listByProject 触发，Select 显示流', async () => {
    render(<VesselComputePage />);
    // 等 streamApi 解析 + 打开下拉验证 option 文本（仿 WorkspaceSwitcher）
    await waitFor(() => {
      expect(document.querySelector('.ant-select-selector')).toBeTruthy();
    });
    const selector = document.querySelector('.ant-select-selector') as HTMLElement;
    fireEvent.mouseDown(selector);
    await waitFor(() => {
      expect(document.querySelector('.ant-select-dropdown')).toBeTruthy();
    });
    const dropdown = document.querySelector('.ant-select-dropdown') as HTMLElement;
    expect(within(dropdown).getByText('FEED-101')).toBeTruthy();
  });

  it('未传 onCalculate：点计算触发 vesselApi.calculate（异步）', async () => {
    render(<VesselComputePage streams={streams} />);
    // antd Select：mouseDown 内层 .ant-select-selector + 等待 dropdown 出现（仿 WorkspaceSwitcher 测试）
    const selector = document.querySelector('.ant-select-selector') as HTMLElement;
    fireEvent.mouseDown(selector);
    await waitFor(() => {
      expect(document.querySelector('.ant-select-dropdown')).toBeTruthy();
    });
    const dropdown = document.querySelector('.ant-select-dropdown') as HTMLElement;
    const option = within(dropdown).getByText('FEED-101').closest('.ant-select-item') as HTMLElement;
    fireEvent.click(option);
    fireEvent.click(screen.getByTestId('vessel-calculate'));
    await waitFor(() => {
      expect(screen.getByTestId('vessel-v-max')).toBeTruthy();
    });
  });
});