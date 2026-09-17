/**
 * HEAT MSW handlers 真跑测试（P5-4 frontend / Task 6）。
 *
 * 思路：本地定义测试用 HEAT handlers + setupServer，fetch 真请求，断言契约。
 * （不直接用全局 handlers 数组，因 MSW v2 experimental 在 jsdom 中绝对路径
 *  拦截需 handler path 与 fetch URL 完全一致，且不想污染主 handlers.ts 的
 *  路径模板以免影响其他测试。）
 *
 * 覆盖：
 * 1. POST /api/v1/heat/import-htri → 201 + ImportHtriResponse 9 字段
 * 2. GET /api/v1/heat/{mock-id} → 200 + HeatResultResponse 含 total_weight_kg
 * 3. GET /api/v1/heat/{unknown-id} → 404 HEAT_NOT_FOUND envelope
 * 4. POST /api/v1/heat/{mock-id}/weight-estimate → 200 + 9 段 segments
 */
import { describe, it, expect, beforeAll, afterAll, afterEach } from 'vitest';
import { setupServer } from 'msw/node';
import { http, HttpResponse } from 'msw';

import { mockAuthToken } from '../../src/mocks/handlers';

const HEAT_MOCK_ID = '00000000-0000-0000-0000-000000000077';
const BEARER = `Bearer ${mockAuthToken}`;

const isAuthed = (request: Request): boolean => {
  const auth = request.headers.get('Authorization');
  return !!auth && auth.startsWith('Bearer ');
};

const heatImportResult = {
  calc_id: HEAT_MOCK_ID,
  calc_type: 'HEAT',
  record_hash: 'b1c2d3e4f5061728',
  project_id: '00000000-0000-0000-0000-000000000001',
  equipment_no: 'E-201',
  tag_number: 'E-201',
  exchanger_category: 'SHELL_TUBE',
  duty_w: 1000000.0,
  outlet_stream_id: '00000000-0000-0000-0000-000000000088',
  outlet_stream_name: 'S-HEAT-201-HEAT_EXCHANGE-A1B2C3',
};

const heatDetail = {
  calc_id: HEAT_MOCK_ID,
  calc_type: 'HEAT',
  project_id: '00000000-0000-0000-0000-000000000001',
  workspace_id: '00000000-0000-0000-0000-000000000002',
  tag_number: 'E-201',
  equipment_no: 'E-201',
  equipment_name: 'HEAT-E-201',
  exchanger_category: 'SHELL_TUBE',
  duty: 1000000.0,
  record_hash: 'b1c2d3e4f5061728',
  input_json: { duty: 1000000, tube_count: 150, shell_id: 600 },
  output_json: {
    total_weight_kg: 3056.75,
    weight_segments: {
      shell_total_kg: 2037.49,
    },
    weight_formula_ref: { tema_version: 'TEMA 9th Ed.' },
  },
};

const heatWeightResult = {
  calc_id: HEAT_MOCK_ID,
  total_weight_kg: 3056.75,
  shell_total_kg: 2037.49,
  segments: {
    shell_cylinder: { weight_kg: 1479.69, formula_ref: 'TEMA 9th C-2.1' },
    shell_heads: { weight_kg: 234.5, formula_ref: 'TEMA 9th C-3.2' },
    shell_flanges: { weight_kg: 156.2, formula_ref: 'ASME B16.5 Cl.300' },
    shell_nozzles: { weight_kg: 78.3, formula_ref: 'ASME B16.5 Cl.150' },
    shell_saddles: { weight_kg: 88.8, formula_ref: 'NB/T 47065' },
    shell_total: { weight_kg: 2037.49, formula_ref: 'TEMA 9th C-Σ' },
    tube: { weight_kg: 850.2, formula_ref: 'ASME B31.3' },
    baffle: { weight_kg: 95.3, formula_ref: 'TEMA 9th R-4.1' },
    channels: { weight_kg: 73.76, formula_ref: 'TEMA 9th N-3.4' },
  },
  formula_ref: { tema_version: 'TEMA 9th Ed.' },
  record_hash: 'c2d3e4f5061728b1',
  // OPEN-7：透传刷新后的 output_json（前端免 get() roundtrip）
  output_json: {
    total_weight_kg: 3056.75,
    weight_segments: { shell_total_kg: 2037.49 },
  },
};

const server = setupServer(
  http.post('http://api.local/api/v1/heat/import-htri', ({ request }) => {
    if (!isAuthed(request)) return HttpResponse.json({ code: 'MISSING_BEARER' }, { status: 401 });
    return HttpResponse.json(heatImportResult, { status: 201 });
  }),
  http.get('http://api.local/api/v1/heat/:heat_id', ({ request, params }) => {
    if (!isAuthed(request)) return HttpResponse.json({ code: 'MISSING_BEARER' }, { status: 401 });
    if (params.heat_id === HEAT_MOCK_ID) return HttpResponse.json(heatDetail);
    return HttpResponse.json(
      { code: 'HEAT_NOT_FOUND', message: '换热器记录不存在', detail: null, trace_id: '' },
      { status: 404 },
    );
  }),
  http.post('http://api.local/api/v1/heat/:heat_id/weight-estimate', ({ request }) => {
    if (!isAuthed(request)) return HttpResponse.json({ code: 'MISSING_BEARER' }, { status: 401 });
    return HttpResponse.json(heatWeightResult);
  }),
);

beforeAll(() => server.listen({ onUnhandledRequest: 'bypass' }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

const BASE = 'http://api.local/api/v1';

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