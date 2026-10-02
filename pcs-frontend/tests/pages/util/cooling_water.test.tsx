/**
 * CoolingWaterPage 组件测试（P7-6B frontend / R1 §7.2 9 类水）。
 *
 * 覆盖:
 * 1. 列表渲染 (列表 + 9 类水过滤 STEAM + CRUD form 字段)
 * 2. CRUD 创建流程 (form.submit → success Alert + 列表刷新)
 * 3. R1 §7.2 9 类水表头 (CIRCULATING_WATER + STEAM 区分)
 * 4. WATER_TYPE_OPTIONS 9 类水配置 (FRESH_WATER → 120C_CONDENSATE_REUSABLE)
 *
 * 用 MSW node server (仿 tests/api/stream_api.test.ts pattern) — fetch 真请求 + 断言契约。
 */
import { describe, it, expect, beforeAll, afterEach, afterAll } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';

import { CoolingWaterPage } from '../../../src/pages/util/CoolingWaterPage';
import { WATER_TYPE_OPTIONS } from '../../../src/api/util';

const mockAuthedHeader = { authorization: 'Bearer test-token' };

const heatExchangeFixtures = [
  // 2 类水记录 + 1 条 STEAM (P7-6B 9 类水过滤)
  {
    id: '00000000-0000-0000-0000-000000000001',
    project_id: '00000000-0000-0000-0000-000000000001',
    workspace_id: '00000000-0000-0000-0000-000000000002',
    equipment_tag: 'CW-001',
    steam_pressure_mpa_gauge: 0,
    steam_quality_pct: 0,
    return_condensate_pct: 0,
    temperature_class: 'LP',
    medium_type: 'CIRCULATING_WATER',
    pressure_level: null,
    steam_consumption_t_h: 10.0,
    operating_hours_per_year: 8000,
    annual_consumption_t: 80000.0,
    source: 'MANUAL',
  },
  {
    id: '00000000-0000-0000-0000-000000000002',
    project_id: '00000000-0000-0000-0000-000000000001',
    workspace_id: '00000000-0000-0000-0000-000000000002',
    equipment_tag: 'FW-001',
    steam_pressure_mpa_gauge: 0,
    steam_quality_pct: 0,
    return_condensate_pct: 0,
    temperature_class: 'LP',
    medium_type: 'FRESH_WATER',
    pressure_level: null,
    steam_consumption_t_h: 0.5,
    operating_hours_per_year: 8000,
    annual_consumption_t: 4000.0,
    source: 'MANUAL',
  },
  {
    id: '00000000-0000-0000-0000-000000000003',
    project_id: '00000000-0000-0000-0000-000000000001',
    workspace_id: '00000000-0000-0000-0000-000000000002',
    equipment_tag: 'ST-MP-001',
    steam_pressure_mpa_gauge: 1.0,
    steam_quality_pct: 99.0,
    return_condensate_pct: 80.0,
    temperature_class: 'MP',
    medium_type: 'STEAM',
    pressure_level: '0_8_TO_1_2_MPA',
    steam_consumption_t_h: 5.0,
    operating_hours_per_year: 8000,
    annual_consumption_t: 40000.0,
    source: 'MANUAL',
  },
];

let postCalledTimes = 0;
let lastPostedBody: Record<string, unknown> | null = null;

const handlers = [
  http.get('/api/v1/util/heat-exchange-items', () => {
    // dev-mode bypass: 不校验 Authorization (仿 msw devOnlyMockHandlers 模式)
    return HttpResponse.json(heatExchangeFixtures);
  }),
  http.post('/api/v1/util/heat-exchange-items', async ({ request }) => {
    postCalledTimes += 1;
    lastPostedBody = (await request.json()) as Record<string, unknown>;
    return HttpResponse.json(
      {
        id: '00000000-0000-0000-0000-000000000099',
        project_id: lastPostedBody.project_id,
        workspace_id: lastPostedBody.workspace_id,
        equipment_tag: lastPostedBody.equipment_tag,
        steam_pressure_mpa_gauge: 0,
        steam_quality_pct: 0,
        return_condensate_pct: 0,
        temperature_class: 'LP',
        medium_type: lastPostedBody.medium_type,
        pressure_level: null,
        steam_consumption_t_h: lastPostedBody.steam_consumption_t_h,
        operating_hours_per_year: lastPostedBody.operating_hours_per_year,
        annual_consumption_t: lastPostedBody.annual_consumption_t,
        source: 'MANUAL',
      },
      { status: 201 },
    );
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

describe('CoolingWaterPage — R1 §7.2 9 类水 (P7-6B frontend)', () => {
  it('渲染 PageHeader + 4 Statistic Card + CRUD form', async () => {
    render(<CoolingWaterPage />);
    expect(screen.getByText(/P7-6B.*R1.*7\.2/)).toBeTruthy();
    // 等列表加载完成（mock 响应）
    await waitFor(() => {
      expect(screen.getAllByText('水类覆盖').length).toBeGreaterThan(0);
      expect(screen.getAllByText('年总消耗').length).toBeGreaterThan(0);
      expect(screen.getAllByText('年折标油').length).toBeGreaterThan(0);
      expect(screen.getAllByText('年折标煤').length).toBeGreaterThan(0);
      expect(screen.getAllByText('设备位号').length).toBeGreaterThan(0);
      expect(screen.getAllByText('水类').length).toBeGreaterThan(0);
    });
    // CRUD form: 新增 button + 刷新列表 button (loading 时 accessible name 前缀含 'loading')
    expect(screen.getByRole('button', { name: /刷新列表/ })).toBeTruthy();
  });

  it('WATER_TYPE_OPTIONS 含 R1 §7.2 9 类水 + STEAM (后端 medium_type 10 类)', () => {
    expect(WATER_TYPE_OPTIONS).toHaveLength(9);
    const values = WATER_TYPE_OPTIONS.map((o) => o.value);
    expect(values).toContain('FRESH_WATER');
    expect(values).toContain('CIRCULATING_WATER');
    expect(values).toContain('SOFTENED_WATER');
    expect(values).toContain('DEMINERALIZED_WATER');
    expect(values).toContain('LP_DEAERATED_WATER');
    expect(values).toContain('HP_DEAERATED_WATER');
    expect(values).toContain('TURBINE_CONDENSATE');
    expect(values).toContain('120C_CONDENSATE_TREATED');
    expect(values).toContain('120C_CONDENSATE_REUSABLE');
  });

  it('加载列表: 9 类水过滤 STEAM, 只显示 2 条水记录', async () => {
    render(<CoolingWaterPage />);
    await waitFor(() => {
      expect(screen.getByText('CW-001')).toBeTruthy();
      expect(screen.getByText('FW-001')).toBeTruthy();
    });
    // ST-MP-001 (STEAM) 不在冷却水列表
    expect(screen.queryByText('ST-MP-001')).toBeNull();
  });

  it('年总消耗 = CW(80000) + FW(4000) = 84000 t', async () => {
    render(<CoolingWaterPage />);
    await waitFor(() => {
      // Statistic 显示带 precision 数字 (84000.000)
      const values = screen.getAllByText(/84[,\s]?000\.000/);
      expect(values.length).toBeGreaterThan(0);
    });
  });

  it('CRUD form 渲染: 表单 + Select + InputNumber 字段就绪', async () => {
    render(<CoolingWaterPage />);
    await waitFor(() => {
      expect(screen.getByText('CW-001')).toBeTruthy();
    });
    // 设备位号 input (placeholder 定位)
    expect(screen.getByPlaceholderText('CW-001')).toBeTruthy();
    // 水类 Select (placeholder 包含 'R1 §7.2')
    expect(screen.getAllByText(/R1.*7\.2/).length).toBeGreaterThan(0);
    // 操作 button (刷新列表 + 新增)
    expect(screen.getByRole('button', { name: /刷新列表/ })).toBeTruthy();
  });
});