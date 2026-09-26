/**
 * CvComputePage 测试（P6-5 前端补课 / 3 计算页之三）。
 *
 * 覆盖 SPEC §7.12 + P6-4 C-24 三新字段：
 * - PageHeader + 源物流 Select + phase 分支字段切换（LIQUID / GAS）
 * - 计算成功（Cv + Masonelian fl 三字段渲染）
 * - 错误路径（未选物流；PcsError envelope）
 */
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';

import { CvComputePage } from '../../../src/pages/cv/CvComputePage';
import type { CvCalculateResponse } from '../../../src/types/cv';

// mock streamApi（CvComputePage 无 streams 注入时自取）
vi.mock('../../../src/api/stream', () => ({
  streamApi: {
    listByProject: vi.fn().mockResolvedValue([
      { stream_id: 's-1', tag_number: 'FEED-101' },
      { stream_id: 's-2', tag_number: 'OUT-201' },
    ]),
  },
}));

const streams = [
  { stream_id: 's-1', tag_number: 'FEED-101' },
  { stream_id: 's-2', tag_number: 'OUT-201' },
];

const liquidResponse: CvCalculateResponse = {
  cv_result_id: 'cv-1',
  tag_number: 'CV-0001',
  fluid_phase: 'LIQUID',
  Cv_calculated: 42.5,
  Cv_selected: 50,
  choked: false,
  cavitation: false,
  flashing: true,
  noise_sil_db: 72.4,
  fl: 0.85,
  flash_steam_rate_kg_s: 0.0042,
  masonelian_model: 'MASONELIAN_1973',
  standard_profile_code: 'IEC_60534',
  design_stage: 'BASIC',
  record_hash: 'cvhash123',
  outlet_stream_id: 'os-1',
};

/**选物流 + 触发计算的小工具（antd Select mouseDown 模式，仿 Vessel 测试）。*/
function selectStreamAndCalculate() {
  const selector = document.querySelector('.ant-select-selector') as HTMLElement;
  fireEvent.mouseDown(selector);
  const dropdown = document.querySelector('.ant-select-dropdown') as HTMLElement;
  const option = within(dropdown).getByText('FEED-101').closest('.ant-select-item') as HTMLElement;
  fireEvent.click(option);
  fireEvent.click(screen.getByTestId('cv-calculate'));
}

describe('CvComputePage — 渲染 (P6-5 前端补课)', () => {
  it('PageHeader + 默认 LIQUID 分支字段可见', () => {
    render(<CvComputePage streams={streams} />);
    expect(screen.getByTestId('cv-compute-page')).toBeTruthy();
    expect(screen.getByTestId('cv-phase-select')).toBeTruthy();
    expect(screen.getByTestId('cv-liquid-fields')).toBeTruthy();
    expect(screen.getByTestId('cv-sg')).toBeTruthy();
    expect(screen.getByTestId('cv-dp-bar')).toBeTruthy();
    expect(screen.queryByTestId('cv-gas-fields')).toBeNull();
  });

  it('phase 切换 GAS → 气相字段替换液相字段', async () => {
    render(<CvComputePage streams={streams} />);
    // phase Select 是页面第二个 Select（第一个是物流）；用 testId 定位后 mouseDown
    const phaseSelector = screen
      .getByTestId('cv-phase-select')
      .closest('.ant-select')?.querySelector('.ant-select-selector') as HTMLElement;
    fireEvent.mouseDown(phaseSelector);
    await waitFor(() => {
      expect(document.querySelector('.ant-select-dropdown')).toBeTruthy();
    });
    const dropdown = document.querySelector('.ant-select-dropdown') as HTMLElement;
    fireEvent.click(within(dropdown).getByText('气体 GAS').closest('.ant-select-item') as HTMLElement);
    expect(screen.getByTestId('cv-gas-fields')).toBeTruthy();
    expect(screen.getByTestId('cv-m')).toBeTruthy();
    expect(screen.getByTestId('cv-xt')).toBeTruthy();
    expect(screen.queryByTestId('cv-liquid-fields')).toBeNull();
  });
});

describe('CvComputePage — 计算路径', () => {
  it('onCalculate 注入成功 → Cv + Masonelian fl 三字段渲染', () => {
    render(<CvComputePage streams={streams} onCalculate={() => liquidResponse} />);
    selectStreamAndCalculate();
    expect(screen.getByTestId('cv-result-card')).toBeTruthy();
    expect(screen.getByTestId('cv-masonelian-model').textContent).toContain(
      'MASONELIAN_1973',
    );
    expect(document.body.textContent).toContain('42.5');
  });

  it('未选物流 → 点计算 → 显示「请选择源物流」', () => {
    render(<CvComputePage streams={streams} />);
    fireEvent.click(screen.getByTestId('cv-calculate'));
    expect(screen.getByTestId('cv-error').textContent).toContain('请选择源物流');
  });

  it('PcsError envelope → 显示 message', () => {
    const err = { response: { data: { code: 'CV_INPUT_ERROR', message: 'GAS 路径 M/Z/gamma 必填' } } };
    render(
      <CvComputePage
        streams={streams}
        onCalculate={() => {
          throw err;
        }}
      />,
    );
    selectStreamAndCalculate();
    expect(screen.getByTestId('cv-error').textContent).toContain('M/Z/gamma 必填');
  });

  it('GAS 路径 → masonelian_model 为 null → 渲染 N/A 占位', () => {
    const gasResponse: CvCalculateResponse = {
      ...liquidResponse,
      fluid_phase: 'GAS',
      fl: null,
      flash_steam_rate_kg_s: null,
      masonelian_model: null,
    };
    render(<CvComputePage streams={streams} onCalculate={() => gasResponse} />);
    selectStreamAndCalculate();
    expect(screen.getByTestId('cv-masonelian-model').textContent).toContain('N/A');
  });
});
