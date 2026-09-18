/** P5-4 HEAT MSW handlers + fixtures — 单一来源（防 P5c MEDIUM 双份维护漂移）。
 *
 * 此前 handlers.ts + tests/mocks/heat_handlers.test.ts 各自维护一份 fixture
 * → 改一处忘改另一处，contract drift 风险高。本模块统一导出：
 *   - HEAT_MOCK_ID / mockHeatImportResult / mockHeatDetail / mockHeatWeightResult
 *   - heatHandlers：3 个 MSW handler（import-htri / detail / weight-estimate）
 *
 * 生产 handlers.ts 与测试 heat_handlers.test.ts 都从这里 import。
 */
import { http, HttpResponse } from "msw";

export const HEAT_MOCK_ID = "00000000-0000-0000-0000-000000000077";

/** HEAT 导入 mock — 9 字段 ImportHtriResponse（V1.3 SPEC §7.11.6 字段对齐） */
export const mockHeatImportResult = {
  calc_id: HEAT_MOCK_ID,
  calc_type: "HEAT",
  record_hash: "b1c2d3e4f5061728",
  project_id: "00000000-0000-0000-0000-000000000001",
  equipment_no: "E-201",
  tag_number: "E-201",
  exchanger_category: "SHELL_TUBE",
  duty_w: 1000000.0,
  outlet_stream_id: "00000000-0000-0000-0000-000000000088",
  outlet_stream_name: "S-HEAT-201-HEAT_EXCHANGE-A1B2C3",
};

/** HEAT 详情 mock — 详情 GET 200 响应 */
export const mockHeatDetail = {
  calc_id: HEAT_MOCK_ID,
  calc_type: "HEAT",
  project_id: "00000000-0000-0000-0000-000000000001",
  workspace_id: "00000000-0000-0000-0000-000000000002",
  tag_number: "E-201",
  equipment_no: "E-201",
  equipment_name: "HEAT-E-201",
  exchanger_category: "SHELL_TUBE",
  duty: 1000000.0,
  record_hash: "b1c2d3e4f5061728",
  input_json: { duty: 1000000, tube_count: 150, shell_id: 600 },
  output_json: {
    total_weight_kg: 3056.75,
    weight_segments: {
      shell_cylinder_kg: 1479.69,
      shell_heads_kg: 234.5,
      shell_flanges_kg: 156.2,
      shell_nozzles_kg: 78.3,
      shell_sadd_kg: 88.8,
      shell_total_kg: 2037.49,
      tube_kg: 850.2,
      baffle_kg: 95.3,
      channels_kg: 73.76,
    },
    weight_formula_ref: { tema_version: "TEMA 9th Ed." },
  },
};

/** HEAT 重量估算 mock — weight-estimate POST 200 响应 */
export const mockHeatWeightResult = {
  calc_id: HEAT_MOCK_ID,
  total_weight_kg: 3056.75,
  shell_total_kg: 2037.49,
  segments: {
    shell_cylinder: { weight_kg: 1479.69, formula_ref: "TEMA 9th C-2.1" },
    shell_heads: { weight_kg: 234.5, formula_ref: "TEMA 9th C-3.2" },
    shell_flanges: { weight_kg: 156.2, formula_ref: "ASME B16.5 Cl.300" },
    shell_nozzles: { weight_kg: 78.3, formula_ref: "ASME B16.5 Cl.150" },
    shell_saddles: { weight_kg: 88.8, formula_ref: "NB/T 47065" },
    shell_total: { weight_kg: 2037.49, formula_ref: "TEMA 9th C-Σ" },
    tube: { weight_kg: 850.2, formula_ref: "ASME B31.3" },
    baffle: { weight_kg: 95.3, formula_ref: "TEMA 9th R-4.1" },
    channels: { weight_kg: 73.76, formula_ref: "TEMA 9th N-3.4" },
  },
  formula_ref: {
    tema_version: "TEMA 9th Ed.",
    cylinder: "TEMA 9th C-2.1",
    heads: "TEMA 9th C-3.2",
    flanges: "ASME B16.5 Cl.300",
    nozzles: "ASME B16.5 Cl.150",
    saddles: "NB/T 47065",
    tube: "ASME B31.3",
    baffle: "TEMA 9th R-4.1",
    channels: "TEMA 9th N-3.4",
  },
  record_hash: "c2d3e4f5061728b1",
  // OPEN-7 闭环：透传刷新后的 output_json，前端免去 get() roundtrip
  output_json: {
    total_weight_kg: 3056.75,
    weight_segments: {
      shell_total_kg: 2037.49,
      tube_kg: 850.2,
      baffle_kg: 95.3,
      channels_kg: 73.76,
    },
  },
};

/** 守卫：无 Authorization Bearer → 401 */
function isAuthed(request: Request): boolean {
  const auth = request.headers.get("Authorization");
  return !!auth && auth.startsWith("Bearer ") && auth !== "Bearer ";
}

/** HEAT MSW handlers — handlers.ts 与 heat_handlers.test.ts 都导入 */
export const heatHandlers = [
  // P5-4 HEAT 导入 HTRI（multipart）
  http.post("/api/v1/heat/import-htri", ({ request }) => {
    if (!isAuthed(request)) return HttpResponse.json({ code: "MISSING_BEARER" }, { status: 401 });
    return HttpResponse.json(mockHeatImportResult, { status: 201 });
  }),

  // P5-4 HEAT 详情 GET
  http.get("/api/v1/heat/:heat_id", ({ request, params }) => {
    if (!isAuthed(request)) return HttpResponse.json({ code: "MISSING_BEARER" }, { status: 401 });
    if (params.heat_id === HEAT_MOCK_ID) {
      return HttpResponse.json(mockHeatDetail);
    }
    return HttpResponse.json(
      { code: "HEAT_NOT_FOUND", message: "换热器记录不存在", detail: null, trace_id: "" },
      { status: 404 },
    );
  }),

  // P5-4 HEAT 重量估算
  http.post("/api/v1/heat/:heat_id/weight-estimate", ({ request }) => {
    if (!isAuthed(request)) return HttpResponse.json({ code: "MISSING_BEARER" }, { status: 401 });
    return HttpResponse.json(mockHeatWeightResult);
  }),
];