/**
 * HEAT MSW handlers 真跑测试（P5-4 frontend / Task 6）。
 *
 * 思路：复用 src/mocks/heat 的单一来源 fixtures + handlers，
 * 本地 setupServer，fetch 真请求，断言契约。
 *
 * 覆盖：
 * 1. POST /api/v1/heat/import-htri → 201 + ImportHtriResponse 9 字段
 * 2. GET /api/v1/heat/{mock-id} → 200 + HeatResultResponse 含 total_weight_kg
 * 3. GET /api/v1/heat/{unknown-id} → 404 HEAT_NOT_FOUND envelope
 * 4. POST /api/v1/heat/{mock-id}/weight-estimate → 200 + 9 段 segments
 *
 * P5c MEDIUM 收口：fixtures + handlers 从 src/mocks/heat.ts 单一来源导入，
 * 不再本地维护副本（防 contract drift）。
 */
import { describe, it, expect, beforeAll, afterAll, afterEach } from 'vitest';
import { setupServer } from 'msw/node';

import {
  HEAT_MOCK_ID,
  heatHandlers,
  mockHeatDetail,
  mockHeatImportResult,
  mockHeatWeightResult,
} from '../../src/mocks/heat';
import { mockAuthToken } from '../../src/mocks/handlers';

const BEARER = `Bearer ${mockAuthToken}`;

const server = setupServer(...heatHandlers);

beforeAll(() => server.listen({ onUnhandledRequest: 'bypass' }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

const BASE = '/api/v1';

describe('MSW HEAT handlers (P5-4 frontend / Task 6)', () => {
  it('POST /api/v1/heat/import-htri → 201 + 9 字段 ImportHtriResponse', async () => {
    const fd = new FormData();
    fd.append('file', new File(['htri'], 'htri.txt', { type: 'text/plain' }));
    fd.append('project_id', '00000000-0000-0000-0000-000000000001');
    fd.append('workspace_id', '00000000-0000-0000-0000-000000000002');
    fd.append('equipment_no', 'E-201');
    fd.append('tag_number', 'E-201');
    fd.append('exchanger_category', 'SHELL_TUBE');

    const res = await fetch(`${BASE}/heat/import-htri`, {
      method: 'POST',
      body: fd,
      headers: { Authorization: BEARER },
    });
    expect(res.status).toBe(201);
    const body = await res.json();
    expect(body).toEqual(mockHeatImportResult);
    expect(body.calc_type).toBe('HEAT');
    expect(body.calc_id).toBe(HEAT_MOCK_ID);
    expect(body.record_hash).toMatch(/^[0-9a-f]{16}$/);
    expect(body.equipment_no).toBe('E-201');
    expect(body.tag_number).toBe('E-201');
    expect(body.exchanger_category).toBe('SHELL_TUBE');
    expect(body.duty_w).toBe(1000000);
    expect(body.outlet_stream_id).toBeTruthy();
    expect(body.outlet_stream_name).toContain('HEAT_EXCHANGE');
  });

  it('GET /api/v1/heat/{mock-id} → 200 + HeatResultResponse 含 total_weight_kg', async () => {
    const res = await fetch(`${BASE}/heat/${HEAT_MOCK_ID}`, {
      headers: { Authorization: BEARER },
    });
    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body).toEqual(mockHeatDetail);
    expect(body.calc_id).toBe(HEAT_MOCK_ID);
    expect(body.exchanger_category).toBe('SHELL_TUBE');
    expect(body.duty).toBe(1000000);
    expect(body.output_json.total_weight_kg).toBeCloseTo(3056.75);
    expect(body.output_json.weight_segments.shell_total_kg).toBeCloseTo(2037.49);
  });

  it('GET /api/v1/heat/{unknown-id} → 404 HEAT_NOT_FOUND envelope', async () => {
    const res = await fetch(`${BASE}/heat/00000000-0000-0000-0000-000000000999`, {
      headers: { Authorization: BEARER },
    });
    expect(res.status).toBe(404);
    const body = await res.json();
    expect(body.code).toBe('HEAT_NOT_FOUND');
    expect(body.message).toBeTruthy();
  });

  it('POST /api/v1/heat/{mock-id}/weight-estimate → 200 + 9 段 segments', async () => {
    const res = await fetch(`${BASE}/heat/${HEAT_MOCK_ID}/weight-estimate`, {
      method: 'POST',
      headers: {
        Authorization: BEARER,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        tema_type: 'BEM',
        shell_id_m: 1.0,
        shell_length_m: 5.0,
        shell_thickness_m: 0.012,
      }),
    });
    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body).toEqual(mockHeatWeightResult);
    expect(body.calc_id).toBe(HEAT_MOCK_ID);
    expect(body.total_weight_kg).toBeCloseTo(3056.75);
    expect(body.shell_total_kg).toBeCloseTo(2037.49);
    const expected = [
      'shell_cylinder', 'shell_heads', 'shell_flanges',
      'shell_nozzles', 'shell_saddles', 'shell_total',
      'tube', 'baffle', 'channels',
    ];
    for (const k of expected) {
      expect(body.segments[k]).toBeDefined();
      expect(body.segments[k].weight_kg).toBeGreaterThan(0);
      expect(body.segments[k].formula_ref).toBeTruthy();
    }
    expect(body.formula_ref.tema_version).toBe('TEMA 9th Ed.');
    expect(body.record_hash).toMatch(/^[0-9a-f]{16}$/);
    // OPEN-7：output_json 透传 total_weight_kg（前端免 get() roundtrip）
    expect(body.output_json.total_weight_kg).toBeCloseTo(3056.75);
    expect(body.output_json.weight_segments.shell_total_kg).toBeCloseTo(2037.49);
  });
});
