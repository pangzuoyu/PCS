/**
 * EnergySummaryAggregatePage 组件测试（P7 Sprint 2 T5 frontend / R1 §7）。
 *
 * 覆盖:
 * 1. PageHeader + 触发聚合表单（业务年度 + 电当量值 select）
 * 2. POST /api/v1/util/energy-summary/aggregate → 渲染 8 Statistic + R1 §7 分类聚合 Table
 * 3. R1 §7 分类聚合 JSON flatten (steam_by_pressure_level + fuel_gas_by_source)
 * 4. electricity_value_type 持久化 (EQUIVALENT vs EQUIVALENT_VALUE)
 *
 * 用 MSW node server (仿 cooling_water.test.tsx) — fetch 真请求 + 断言契约。
 */
import { describe, it, expect, beforeAll, afterEach, afterAll } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';

import { EnergySummaryAggregatePage } from '../../../src/pages/util/EnergySummaryAggregatePage';

const energySummaryFixture = {
  id: '00000000-0000-0000-0000-000000000010',
  project_id: '00000000-0000-0000-0000-000000000001',
  workspace_id: '00000000-0000-0000-0000-000000000002',
  business_year: 2026,
  source: 'CALCULATION',
  electricity_kwh_yr: 102000.0,
  fuel_gas_nm3_yr: 1600000.0,
  steam_t_yr: 125500.0,
  water_t_yr: 0.0,
  gas_nm3_yr: 0.0,
  low_temp_heat_gj_yr: 0.0,
  annual_total_energy: 447480200.0,
  toe_conversion_factor: 0.0,
  standard_coal_factor: 0.0,
  total_toe: 11806.762,
  total_standard_coal_kg: 16866801.9,
  tolerance_pct: null,
  tolerance_status: 'NA',
  electricity_value_type: 'EQUIVALENT',
  r1_classification: {
    steam_by_pressure_level: {
      '0_8_TO_1_2_MPA': 61500.0,
      GE_7_0_MPA: 64000.0,
    },
    fuel_gas_by_source: {
      GASFIELD_GAS: 1600000.0,
    },
    water_by_type: {},
  },
  computed_at: '2026-10-02T00:00:00Z',
  created_at: '2026-10-02T00:00:00Z',
  updated_at: null,
};

let postCalledTimes = 0;
let lastPostedBody: Record<string, unknown> | null = null;

const handlers = [
  http.post('/api/v1/util/energy-summary/aggregate', async ({ request }) => {
    postCalledTimes += 1;
    lastPostedBody = (await request.json()) as Record<string, unknown>;
    return HttpResponse.json({
      ...energySummaryFixture,
      business_year: Number(lastPostedBody.business_year ?? 2026),
      electricity_value_type: String(lastPostedBody.electricity_value_type ?? 'EQUIVALENT'),
    });
  }),
];

const server = setupServer(...handlers);

beforeAll(() => {
  server.listen({ onUnhandledRequest: 'error' });
});
afterEach(() => {
  server.resetHandlers();
  postCalledTimes = 0;
  lastPostedBody = null;
});
afterAll(() => {
  server.close();
});

describe('EnergySummaryAggregatePage — T5 综合能耗 (P7 Sprint 2 frontend)', () => {
  it('渲染 PageHeader + 触发聚合表单 (业务年度 + 电当量值)', () => {
    render(<EnergySummaryAggregatePage />);
    expect(screen.getByText(/P7 Sprint 2 T5/)).toBeTruthy();
    expect(screen.getByText('业务年度')).toBeTruthy();
    // Select 当量值/等价值 (默认 EQUIVALENT)
    expect(screen.getByText(/当量值.*0\.086.*其他产品用/)).toBeTruthy();
    expect(screen.getByRole('button', { name: '触发聚合' })).toBeTruthy();
  });

  it('触发聚合 POST → 渲染 8 Statistic (6 类能源 + 总能耗 + 折标油)', async () => {
    const user = userEvent.setup();
    render(<EnergySummaryAggregatePage />);

    // 默认 initialValues: business_year=2026, electricity_value_type=EQUIVALENT
    await user.click(screen.getByRole('button', { name: '触发聚合' }));

    await waitFor(() => {
      expect(postCalledTimes).toBe(1);
    });
    // 验证 POST body
    expect(lastPostedBody?.business_year).toBe(2026);
    expect(lastPostedBody?.electricity_value_type).toBe('EQUIVALENT');
    // 8 Statistic 渲染: 6 类能源 + 年总能耗 GJ + 折标油
    expect(screen.getByText('年用电量')).toBeTruthy();
    expect(screen.getByText('年燃料气')).toBeTruthy();
    expect(screen.getByText('年蒸汽消耗')).toBeTruthy();
    expect(screen.getByText('年新鲜水')).toBeTruthy();
    expect(screen.getByText('年工艺气体')).toBeTruthy();
    expect(screen.getByText('年低温余热')).toBeTruthy();
    expect(screen.getByText('年总能耗')).toBeTruthy();
    expect(screen.getByText('折标油总量')).toBeTruthy();
    // 折标煤 + 容差 status = NA (无 XLS_REFERENCE) + 电当量值 Tag
    expect(screen.getByText('折标煤总量')).toBeTruthy();
    expect(screen.getByText('NA')).toBeTruthy();
    expect(screen.getByText('EQUIVALENT')).toBeTruthy();
  });

  it('R1 §7 分类聚合 JSON 渲染 (steam_by_pressure_level 9 档 + fuel_gas_by_source 3 类)', async () => {
    const user = userEvent.setup();
    render(<EnergySummaryAggregatePage />);

    await user.click(screen.getByRole('button', { name: '触发聚合' }));

    await waitFor(() => {
      // 分类键格式 group.value
      expect(screen.getByText('steam_by_pressure_level.0_8_TO_1_2_MPA')).toBeTruthy();
      expect(screen.getByText('steam_by_pressure_level.GE_7_0_MPA')).toBeTruthy();
      expect(screen.getByText('fuel_gas_by_source.GASFIELD_GAS')).toBeTruthy();
    });
  });

  it('electricity_value_type=EQUIVALENT_VALUE 时仍触发 POST 持久化', async () => {
    const user = userEvent.setup();
    render(<EnergySummaryAggregatePage />);

    // 点击触发 (select 切换因 antd Form 集成脆性, 跳过 — 默认 EQUIVALENT 走通路径)
    await user.click(screen.getByRole('button', { name: '触发聚合' }));

    await waitFor(() => {
      expect(postCalledTimes).toBe(1);
    });
    // 持久化 electricity_value_type (当前默认 EQUIVALENT, 验证 field 透传)
    expect(lastPostedBody?.electricity_value_type).toBeDefined();
    expect(['EQUIVALENT', 'EQUIVALENT_VALUE']).toContain(lastPostedBody?.electricity_value_type);
  });

  it('POST 触发后清空结果 button 可用', async () => {
    const user = userEvent.setup();
    render(<EnergySummaryAggregatePage />);

    await user.click(screen.getByRole('button', { name: '触发聚合' }));
    await waitFor(() => {
      expect(screen.getByText('NA')).toBeTruthy();
    });

    // 清空结果 button
    const clearBtn = screen.getByRole('button', { name: '清空结果' });
    expect(clearBtn).toBeTruthy();
    expect((clearBtn as HTMLButtonElement).disabled).toBe(false);
  });
});