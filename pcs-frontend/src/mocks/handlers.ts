/**
 * MSW handlers — 离线 mock server（P45-0-5 + QA 2026-09-16）
 *
 * `handlers` = OpenAPI 契约端点（meta 5 端点，OpenAPI drift 校验覆盖）
 * `devOnlyMockHandlers` = dev-only mock（mock-login + 10 个 seed 数据端点，
 *                          不参与 OpenAPI drift 校验，仅 dev 环境可见）
 *
 * seed 数据覆盖：QA 11 组件实例化所需的所有列表端点
 * （streams / assets / pipe-classes / pms / bedd / materials / pipe-line /
 *  workspaces / checklist 等）。详见 docs/qa-report-per-batch-2026-09-16.md。
 */
import { http, HttpResponse } from "msw";

import { heatHandlers } from "./heat";
import { metaSeed, MOCK_TOKEN } from "./seed/meta";
import { seedAssets } from "./seed/config";
import { seedAllowableStress, seedMaterials, seedToxicityClasses } from "./seed/common";
import { seedPipeClasses } from "./seed/pipe-classes";
import { seedPipeLineRows } from "./seed/pipe-line";
import { seedBeddSections, seedPmsItems } from "./seed/pms";
import {
  buildStreamDetail,
  seedStreams,
} from "./seed/streams";
import { seedChecklist, seedWorkspaces } from "./seed/workspaces";
import type { RevVersion } from "../components/common/RevTimeline";
import type { Notification } from "../components/common/NotificationCenter";

/** JWT 守卫 — 无 token → 401 */
function isAuthed(req: Request): boolean {
  const auth = req.headers.get("Authorization");
  return !!auth && auth.startsWith("Bearer ") && auth !== "Bearer ";
}

const ROLE_BY_USER: Record<string, string> = {
  alice: "DESIGNER",
  bob: "CHECKER",
  carol: "APPROVER",
  dan: "SYSTEM_ADMIN",
};

/** V1 mock-only 端点：仅 dev 环境使用，不在 OpenAPI 中（QA fix / ISSUE-001 + 11 组件实例化） */
// P7-7+ actor 上下文一致性: mock-login + /auth/me 返回 user_id (与 backend
// 派生一致), 让 LoginPage setSession 拿到权威 actor id.
const MOCK_USER_IDS: Record<string, string> = {
  alice: '00000000-0000-0000-0000-0000000a11ce',
  bob: '00000000-0000-0000-0000-0000000b0b01',
  carol: '00000000-0000-0000-0000-0000000ca201',
  dan: '00000000-0000-0000-0000-0000000da0001',
};

const devOnlyMockHandlers = [
  // === 认证 ===
  // P7-7+ actor 上下文一致性: mock-login 返回 user_id (与 backend /auth/me
  // 派生一致), 让 LoginPage setSession 拿到权威 actor id.
  http.post("/api/v1/auth/mock-login", async ({ request }) => {
    const body = (await request.json()) as { username?: string };
    const username = body.username ?? "alice";
    const role = ROLE_BY_USER[username] ?? "DESIGNER";
    const user_id = MOCK_USER_IDS[username] ?? '00000000-0000-0000-0000-000000000001';
    return HttpResponse.json({
      access_token: MOCK_TOKEN,
      refresh_token: `${MOCK_TOKEN}.refresh`,
      token_type: "bearer",
      role,
      username,
      user_id,
    });
  }),
  http.get("/api/v1/auth/me", ({ request }) => {
    if (!isAuthed(request)) {
      return HttpResponse.json({ code: "MISSING_BEARER" }, { status: 401 });
    }
    // dev-mode: 从 mock token 解析 username (token 简化用 'mock-user' 标记)
    const username = "alice"; // 简化: dev mode 默认 alice
    const role = ROLE_BY_USER[username] ?? "DESIGNER";
    const user_id = MOCK_USER_IDS[username] ?? '00000000-0000-0000-0000-000000000001';
    return HttpResponse.json({ username, role, user_id });
  }),

  // === 物流 SIM ===
  http.get("/api/v1/projects/:project_id/streams", ({ request }) => {
    if (!isAuthed(request)) return HttpResponse.json({ code: "MISSING_BEARER" }, { status: 401 });
    return HttpResponse.json(seedStreams);
  }),
  http.get("/api/v1/streams/:stream_id", ({ request, params }) => {
    if (!isAuthed(request)) return HttpResponse.json({ code: "MISSING_BEARER" }, { status: 401 });
    // 返回详情页所需的完整 payload（stream + 矩阵 + 签署 + 审批 + 冲突 + 血缘 + 变更影响 + UiSchema）
    const payload = buildStreamDetail(String(params.stream_id));
    return payload
      ? HttpResponse.json(payload)
      : HttpResponse.json({ code: "NOT_FOUND", message: `stream ${params.stream_id} not found` }, { status: 404 });
  }),

  // === CONFIG 资产 ===
  http.get("/api/v1/config/assets", ({ request }) => {
    if (!isAuthed(request)) return HttpResponse.json({ code: "MISSING_BEARER" }, { status: 401 });
    return HttpResponse.json(seedAssets);
  }),

  // === 管道等级 ===
  http.get("/api/v1/pipe-classes", ({ request }) => {
    if (!isAuthed(request)) return HttpResponse.json({ code: "MISSING_BEARER" }, { status: 401 });
    return HttpResponse.json(seedPipeClasses);
  }),

  // === PMS / BEDD ===
  http.get("/api/v1/projects/:project_id/pms", ({ request }) => {
    if (!isAuthed(request)) return HttpResponse.json({ code: "MISSING_BEARER" }, { status: 401 });
    return HttpResponse.json(seedPmsItems);
  }),
  http.get("/api/v1/projects/:project_id/bedd", ({ request }) => {
    if (!isAuthed(request)) return HttpResponse.json({ code: "MISSING_BEARER" }, { status: 401 });
    return HttpResponse.json(seedBeddSections);
  }),

  // === 物性 / 许用应力 / 毒性爆炸 ===
  http.get("/api/v1/common/materials/search", ({ request }) => {
    if (!isAuthed(request)) return HttpResponse.json({ code: "MISSING_BEARER" }, { status: 401 });
    return HttpResponse.json(seedMaterials);
  }),
  http.get("/api/v1/common/allowable-stress", ({ request }) => {
    if (!isAuthed(request)) return HttpResponse.json({ code: "MISSING_BEARER" }, { status: 401 });
    return HttpResponse.json(seedAllowableStress);
  }),
  http.get("/api/v1/common/safety", ({ request }) => {
    if (!isAuthed(request)) return HttpResponse.json({ code: "MISSING_BEARER" }, { status: 401 });
    return HttpResponse.json(seedToxicityClasses);
  }),

  // === 管道一览表 ===
  http.get("/api/v1/projects/:project_id/pipe-line-list", ({ request }) => {
    if (!isAuthed(request)) return HttpResponse.json({ code: "MISSING_BEARER" }, { status: 401 });
    return HttpResponse.json(seedPipeLineRows);
  }),

  // === 工作区 / 清单 ===
  http.get("/api/v1/workspaces", ({ request }) => {
    if (!isAuthed(request)) return HttpResponse.json({ code: "MISSING_BEARER" }, { status: 401 });
    return HttpResponse.json(seedWorkspaces);
  }),
  http.get("/api/v1/checklist/projects/:project_id", ({ request, params }) => {
    if (!isAuthed(request)) return HttpResponse.json({ code: "MISSING_BEARER" }, { status: 401 });
    return HttpResponse.json(seedChecklist.filter((c) => c.project_id === params.project_id));
  }),
  http.get("/api/v1/checklist/projects/:project_id/completeness", ({ request, params }) => {
    if (!isAuthed(request)) return HttpResponse.json({ code: "MISSING_BEARER" }, { status: 401 });
    const items = seedChecklist.filter((c) => c.project_id === params.project_id);
    const completed = items.filter((i) => i.status === "VERIFIED").length;
    return HttpResponse.json({
      total: items.length,
      completed,
      percent: items.length > 0 ? Math.round((completed / items.length) * 100) : 0,
    });
  }),

  // === 通知中心 ===
  http.get("/api/v1/notifications", ({ request }) => {
    if (!isAuthed(request)) return HttpResponse.json({ code: "MISSING_BEARER" }, { status: 401 });
    return HttpResponse.json(seedNotifications);
  }),

  // === 资产版本历史（RevTimeline）===
  http.get("/api/v1/config/assets/:asset_id/revisions", ({ request, params }) => {
    if (!isAuthed(request)) return HttpResponse.json({ code: "MISSING_BEARER" }, { status: 401 });
    return HttpResponse.json(seedRevisions.filter((r) => r.asset_id === params.asset_id));
  }),

  // === P5-3 PSV 计算 ===
  http.post("/api/v1/psv/calculate", ({ request }) => {
    if (!isAuthed(request)) return HttpResponse.json({ code: "MISSING_BEARER" }, { status: 401 });
    return HttpResponse.json(mockPsvCalculateResult, { status: 201 });
  }),

  // === P5-3 PSV 项目标准配置 GET ===
  http.get("/api/v1/projects/:project_id/psv/standard-profile", ({ request }) => {
    if (!isAuthed(request)) return HttpResponse.json({ code: "MISSING_BEARER" }, { status: 401 });
    return HttpResponse.json(mockPsvStandardProfile);
  }),

  // === P5-3 PSV 项目标准配置 POST ===
  http.post("/api/v1/projects/:project_id/psv/standard-profile", async ({ request }) => {
    if (!isAuthed(request)) return HttpResponse.json({ code: "MISSING_BEARER" }, { status: 401 });
    const body = (await request.json()) as {
      profile_code?: string;
      approval_json?: Record<string, unknown>;
      approved_by?: string;
    };
    if (body.profile_code === "CUSTOM" && (!body.approval_json || !body.approved_by)) {
      return HttpResponse.json(
        { code: "PSV_INPUT_ERROR", message: "CUSTOM 必须填 approval_json + approved_by", detail: null, trace_id: "" },
        { status: 422 },
      );
    }
    return HttpResponse.json(
      {
        ...mockPsvStandardProfile,
        profile_code: body.profile_code ?? "API",
      },
      { status: 201 },
    );
  }),

  // === P5-4 HEAT handlers（import + detail + weight-estimate）===
  //    单一来源：src/mocks/heat.ts（防 P5c MEDIUM 双份维护漂移）
  ...heatHandlers,

  // === MSW-VESSEL-SEPEQUIP-MISSING — HIGH P5-3 fe — 补 vessel/sep-equip
  // mock 让前端 MSW 模式与后端契约对齐，避免 per-batch QA 假阴性 ===
  http.post("/api/v1/vessel/calculate", async ({ request }) => {
    if (!isAuthed(request)) return HttpResponse.json({ code: "MISSING_BEARER" }, { status: 401 });
    const body = (await request.json().catch(() => ({}))) as {
      project_id?: string;
      tag_number?: string;
    };
    return HttpResponse.json(
      {
        vessel_id: "00000000-0000-0000-0000-000000000000",
        project_id: body.project_id ?? "00000000-0000-0000-0000-000000000000",
        tag_number: body.tag_number ?? "V-001",
        design_stage: "BASIC",
        output_json: { mock: true, source: "msw" },
        record_hash: "msw-vessel-hash",
        created_at: new Date().toISOString(),
      },
      { status: 201 },
    );
  }),

  http.post("/api/v1/sep-equip/calculate", async ({ request }) => {
    if (!isAuthed(request)) return HttpResponse.json({ code: "MISSING_BEARER" }, { status: 401 });
    const body = (await request.json().catch(() => ({}))) as {
      project_id?: string;
      tag_number?: string;
    };
    return HttpResponse.json(
      {
        sep_id: "00000000-0000-0000-0000-000000000000",
        project_id: body.project_id ?? "00000000-0000-0000-0000-000000000000",
        tag_number: body.tag_number ?? "S-001",
        output_json: { mock: true, source: "msw" },
        record_hash: "msw-sep-hash",
        created_at: new Date().toISOString(),
      },
      { status: 201 },
    );
  }),

  // === P6-5 前端补课：3 计算端点（heating-value / saturation-water-content / cv）===
  //    固定 demo 输出（与 vessel/calculate 同模式），页面测试用 vi.mock 不走这里。
  http.post("/api/v1/common/heating-value/calculate", async ({ request }) => {
    if (!isAuthed(request)) return HttpResponse.json({ code: "MISSING_BEARER" }, { status: 401 });
    return HttpResponse.json(
      {
        feed_mw_kg_per_kmol: 17.4,
        hhv_mj_per_sm3: 41.6,
        hhv_btu_per_scf: 1116,
        lhv_mj_per_sm3: 37.5,
        lhv_btu_per_scf: 1006,
        stoichiometric_air_sm3_per_sm3: 9.85,
        flue_gas_sm3_per_sm3: 10.6,
        flue_gas_composition: { CO2: 0.087, H2O: 0.173, N2: 0.73, O2: 0.0 },
        flue_gas_mw_kg_per_kmol: 27.6,
        formula_ref: { "74-82-8": "GPSA_23-2", mock: true },
      },
      { status: 200 },
    );
  }),

  http.post("/api/v1/psychro/saturation-water-content/calculate", async ({ request }) => {
    if (!isAuthed(request)) return HttpResponse.json({ code: "MISSING_BEARER" }, { status: 401 });
    return HttpResponse.json(
      {
        saturation_w_kg_kg: 0.0201,
        saturation_w_mg_sm3: 24700,
        saturation_w_lb_per_mmscf: 1310,
        saturation_T_c: 25.0,
        temperature_out_of_range: false,
        warning_message: null,
        acidic_gas_correction_applied: false,
        acidic_gas_correction_factor: 1.0,
        formula_ref: "ASHRAE_RP-1845_CoolProp",
      },
      { status: 200 },
    );
  }),

  http.post("/api/v1/cv/calculate", async ({ request }) => {
    if (!isAuthed(request)) return HttpResponse.json({ code: "MISSING_BEARER" }, { status: 401 });
    const body = (await request.json().catch(() => ({}))) as {
      fluid_phase?: string;
    };
    const isLiquid = body.fluid_phase === "LIQUID" || body.fluid_phase === "TWO_PHASE";
    return HttpResponse.json(
      {
        cv_result_id: "00000000-0000-0000-0000-0000000000c7",
        tag_number: "CV-0001",
        fluid_phase: body.fluid_phase ?? "LIQUID",
        Cv_calculated: 42.5,
        Cv_selected: 50,
        choked: false,
        cavitation: false,
        flashing: isLiquid,
        noise_sil_db: 72.4,
        // P6-4 C-24 三新字段：仅 LIQUID 路径填充（GAS 保持 null）
        fl: isLiquid ? 0.85 : null,
        flash_steam_rate_kg_s: isLiquid ? 0.0042 : null,
        masonelian_model: isLiquid ? "MASONELIAN_1973" : null,
        standard_profile_code: "IEC_60534",
        design_stage: "BASIC",
        record_hash: "msw-cv-hash",
        outlet_stream_id: "00000000-0000-0000-0000-0000000000c8",
      },
      { status: 201 },
    );
  }),
];

/** P5-3 PSV 计算 mock 响应 — 固定 FIRE 场景输出（V1.2 SPEC §7.11.5 字段对齐） */
const mockPsvCalculateResult = {
  calc_id: '00000000-0000-0000-0000-000000000099',
  calc_type: 'PSV',
  record_hash: 'a1b2c3d4e5f60718',
  stream_id: '00000000-0000-0000-0000-000000000001',
  lineage_ids: ['00000000-0000-0000-0000-000000000050'],
  outlet_stream_id: '00000000-0000-0000-0000-000000000088',
  outlet_stream_name: 'S-PSV-301-PSV-OUT',
  result: {
    relief_scenario: 'FIRE',
    aggregate: { dominant_scenario: 'FIRE', case_count: 1, per_scenario_json: {} },
    relief_area: {
      area_required_m2: 0.001234,
      medium: 'GAS',
      formula_ref: { standard: 'API_520', version: '7th', clause: '§5.6.3' },
    },
    orifice: {
      selected_size: 'D',
      actual_area_m2: 0.00171,
      inlet_size: '4 inch',
      outlet_size: '6 inch',
    },
    set_pressure_pa: 200000.0,
    blowdown_fraction: 0.05,
    standard_profile_code: 'API',
    standard_refs_json: {
      fire_case: { standard: 'API_521', version: '7th', clause: '§5.15.2.2.1' },
      relief_area: { standard: 'API_520', version: '7th', clause: '§5.6.3' },
      orifice: { standard: 'API_526', version: '7th', clause: 'Table 1' },
    },
    formula_ref_json: {
      dominant_scenario: 'FIRE',
      fire_case_or_other: { standard: 'API_521', version: '7th', clause: '§5.15.2.2.1' },
      relief_area: { standard: 'API_520', version: '7th', clause: '§5.6.3' },
      orifice: { standard: 'API_526', version: '7th', clause: 'Table 1' },
    },
  },
};

/** P5-3 PSV 项目标准配置 mock seed — API/7th 默认 */
const mockPsvStandardProfile = {
  profile_id: '00000000-0000-0000-0000-000000000200',
  project_id: '00000000-0000-0000-0000-000000000001',
  discipline: 'PSV',
  profile_code: 'API',
  standard_refs_json: {
    fire_case: { standard: 'API_521', version: '7th', clause: '§5.15.2.2.1' },
    relief_area: { standard: 'API_520', version: '7th', clause: '§5.6.3' },
    orifice: { standard: 'API_526', version: '7th', clause: 'Table 1' },
  },
  approval_json: null,
  is_default: true,
  migrated_default: false,
  effective_from: '2026-09-17T00:00:00Z',
  effective_to: null,
  approved_by: null,
  created_at: '2026-09-17T00:00:00Z',
  updated_at: '2026-09-17T00:00:00Z',
};

/** 通知 seed — 5 条覆盖 3 类（todo/change/system）+ 2 条未读 */
const seedNotifications: Notification[] = [
  { notification_id: 'n-001', category: 'todo', kind: 'TODO', title: 'S-101 待你校核', summary: 'alice 已提交物流 S-101 的校核请求', issued_at: '2026-09-16T04:00:00Z', unread: true },
  { notification_id: 'n-002', category: 'todo', kind: 'TODO', title: 'P-2001 管道设计校核', summary: '管道计算结果等待复核', issued_at: '2026-09-16T03:30:00Z', unread: true },
  { notification_id: 'n-003', category: 'change', kind: 'CHANGE', title: 'S-101 流量变更', summary: '流量 1000 → 1100 kg/h，影响 3 条计算', issued_at: '2026-09-16T04:30:00Z' },
  { notification_id: 'n-004', category: 'change', kind: 'CHANGE', title: '上游 HAZOP 报告更新', summary: 'SAFE-001 假设数据需重审', issued_at: '2026-09-15T22:00:00Z' },
  { notification_id: 'n-005', category: 'system', kind: 'SYSTEM', title: '系统维护通知', summary: '今晚 22:00 数据库例行维护', issued_at: '2026-09-15T18:00:00Z' },
];

/** Rev seed — 4 个 Rev 字母覆盖 ISSUED_FOR_DESIGN/REVIEW/CONSTRUCTION/USE */
const seedRevisions: (RevVersion & { asset_id: string })[] = [
  // a-formula-001（Antoine 方程）— 4 Rev
  { asset_id: 'a-formula-001', version_id: 'v-a-formula-001-A', rev_letter: 'A', issued_at: '2026-08-01T09:00:00Z', status: 'ISSUED_FOR_DESIGN', signatures: [{ role: '设计', signer_name: 'alice', signed_at: '2026-08-01T10:00:00Z' }], snapshot_hash: 'a1b2c3d4', snapshot_hash_full: 'a1b2c3d4e5f6789012345' },
  { asset_id: 'a-formula-001', version_id: 'v-a-formula-001-B', rev_letter: 'B', issued_at: '2026-08-15T09:00:00Z', status: 'ISSUED_FOR_REVIEW', signatures: [{ role: '设计', signer_name: 'alice', signed_at: '2026-08-15T10:00:00Z' }, { role: '校核', signer_name: 'bob', signed_at: '2026-08-15T15:00:00Z' }], snapshot_hash: 'b2c3d4e5', snapshot_hash_full: 'b2c3d4e5f6789012345a' },
  { asset_id: 'a-formula-001', version_id: 'v-a-formula-001-C', rev_letter: 'C', issued_at: '2026-09-05T09:00:00Z', status: 'ISSUED_FOR_CONSTRUCTION', affected: true, signatures: [{ role: '设计', signer_name: 'alice' }, { role: '校核', signer_name: 'bob' }, { role: '审核', signer_name: 'carol', signed_at: '2026-09-05T16:00:00Z' }], snapshot_hash: 'c3d4e5f6', snapshot_hash_full: 'c3d4e5f6789012345abc' },
  { asset_id: 'a-formula-001', version_id: 'v-a-formula-001-D', rev_letter: 'D', issued_at: '2026-09-10T09:00:00Z', status: 'ISSUED_FOR_USE', signatures: [], snapshot_hash: 'f7a8b9c0', snapshot_hash_full: 'f7a8b9c0d1e2f3a4b5c6d' },
  // 其他资产 — 简化给 2 Rev
  { asset_id: 'a-coeff-002', version_id: 'v-a-coeff-002-A', rev_letter: 'A', issued_at: '2026-08-20T09:00:00Z', status: 'ISSUED_FOR_REVIEW', signatures: [{ role: '设计', signer_name: 'bob', signed_at: '2026-08-20T10:00:00Z' }], snapshot_hash: 'a1b2c3d4', snapshot_hash_full: 'a1b2c3d4e5f67890abcde' },
  { asset_id: 'a-coeff-002', version_id: 'v-a-coeff-002-B', rev_letter: 'B', issued_at: '2026-09-12T14:30:00Z', status: 'ISSUED_FOR_USE', signatures: [], snapshot_hash: 'a1b2c3d4', snapshot_hash_full: 'a1b2c3d4e5f6789012345' },
  { asset_id: 'a-tmpl-003', version_id: 'v-a-tmpl-003-A', rev_letter: 'A', issued_at: '2026-09-15T16:45:00Z', status: 'ISSUED_FOR_REVIEW', signatures: [], snapshot_hash: 'b2c3d4e5', snapshot_hash_full: 'b2c3d4e5f67890abc1234' },
  { asset_id: 'a-proj-004', version_id: 'v-a-proj-004-A', rev_letter: 'A', issued_at: '2026-09-16T01:20:00Z', status: 'ISSUED_FOR_DESIGN', signatures: [], snapshot_hash: 'c3d4e5f6', snapshot_hash_full: 'c3d4e5f67890abcdef1234' },
  { asset_id: 'a-std-005', version_id: 'v-a-std-005-A', rev_letter: 'A', issued_at: '2026-07-01T09:00:00Z', status: 'ISSUED_FOR_CONSTRUCTION', affected: true, signatures: [{ role: '设计', signer_name: 'dan' }, { role: '校核', signer_name: 'dan' }, { role: '审核', signer_name: 'dan' }], snapshot_hash: 'd4e5f678', snapshot_hash_full: 'd4e5f67890abcdef12345' },
  { asset_id: 'a-std-005', version_id: 'v-a-std-005-B', rev_letter: 'B', issued_at: '2026-08-15T09:00:00Z', status: 'ISSUED_FOR_USE', signatures: [], snapshot_hash: 'd4e5f678', snapshot_hash_full: 'd4e5f67890abcdef1234b' },
  { asset_id: 'a-std-005', version_id: 'v-a-std-005-C', rev_letter: 'C', issued_at: '2026-08-30T10:15:00Z', status: 'ISSUED_FOR_USE', affected: true, signatures: [], snapshot_hash: 'd4e5f678', snapshot_hash_full: 'd4e5f67890abcdef1234c' },
];

// === P7-6B 冷却水 / 综合能耗 mock（V1 dev-only, 走 devOnlyMockHandlers）===
const utilSeedHeatExchange = [
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

const utilSeedEnergySummary = {
  id: '00000000-0000-0000-0000-000000000010',
  project_id: '00000000-0000-0000-0000-000000000001',
  workspace_id: '00000000-0000-0000-0000-000000000002',
  business_year: 2026,
  source: 'CALCULATION',
  electricity_kwh_yr: 102000.0,
  fuel_gas_nm3_yr: 0.0,
  steam_t_yr: 20000.0,
  water_t_yr: 0.0,
  gas_nm3_yr: 0.0,
  low_temp_heat_gj_yr: 0.0,
  annual_total_energy: 55927200.0,
  toe_conversion_factor: 0.0,
  standard_coal_factor: 0.0,
  total_toe: 1528.772,
  total_standard_coal_kg: 2183960.0,
  tolerance_pct: null,
  tolerance_status: 'NA',
  electricity_value_type: 'EQUIVALENT',
  r1_classification: {
    steam_by_pressure_level: { '0_8_TO_1_2_MPA': 20000.0 },
    // e2e energy_summary.spec 断言 GASFIELD_GAS 行 (与 vitest 独立 seed 对齐)
    fuel_gas_by_source: { GASFIELD_GAS: 24694992.0 },
    water_by_type: {},
  },
  computed_at: '2026-10-02T00:00:00Z',
  created_at: '2026-10-02T00:00:00Z',
  updated_at: null,
};

devOnlyMockHandlers.push(
  // === P7-6B 冷却水子表 (R1 §7.2 9 类水) ===
  http.get('/api/v1/util/heat-exchange-items', ({ request }) => {
    if (!isAuthed(request)) {
      return HttpResponse.json({ code: 'MISSING_BEARER' }, { status: 401 });
    }
    return HttpResponse.json(utilSeedHeatExchange);
  }),
  http.post('/api/v1/util/heat-exchange-items', async ({ request }) => {
    if (!isAuthed(request)) {
      return HttpResponse.json({ code: 'MISSING_BEARER' }, { status: 401 });
    }
    const body = (await request.json()) as Record<string, unknown>;
    const created = {
      id: '00000000-0000-0000-0000-000000000099',
      project_id: String(body.project_id ?? ''),
      workspace_id: String(body.workspace_id ?? ''),
      equipment_tag: String(body.equipment_tag ?? 'CW-XXX'),
      steam_pressure_mpa_gauge: 0,
      steam_quality_pct: 0,
      return_condensate_pct: 0,
      temperature_class: 'LP',
      medium_type: body.medium_type ?? 'CIRCULATING_WATER',
      pressure_level: null,
      steam_consumption_t_h: Number(body.steam_consumption_t_h ?? 0),
      operating_hours_per_year: Number(body.operating_hours_per_year ?? 8000),
      annual_consumption_t: Number(body.annual_consumption_t ?? 0),
      source: 'MANUAL',
    };
    return HttpResponse.json(created, { status: 201 });
  }),
  // === P7 Sprint 2 T5 综合能耗聚合 ===
  http.post('/api/v1/util/energy-summary/aggregate', async ({ request }) => {
    if (!isAuthed(request)) {
      return HttpResponse.json({ code: 'MISSING_BEARER' }, { status: 401 });
    }
    const body = (await request.json()) as Record<string, unknown>;
    return HttpResponse.json({
      ...utilSeedEnergySummary,
      business_year: Number(body.business_year ?? 2026),
      electricity_value_type: String(body.electricity_value_type ?? 'EQUIVALENT'),
    });
  }),

  // === F-P2-009 Sprint 3 / Issue 7 Audit Query (3 endpoints) ===

  // /config-audit: DESIGNER+ 可查 (公司级全局, 无 project 隔离).
  http.get('/api/v1/config-audit', ({ request }) => {
    if (!isAuthed(request)) {
      return HttpResponse.json({ code: 'MISSING_BEARER' }, { status: 401 });
    }
    const url = new URL(request.url);
    const assetId = url.searchParams.get('asset_id');
    const seed = [
      {
        audit_id: '11111111-1111-1111-1111-111111111111',
        user_id: '00000000-0000-0000-0000-000000000001',
        action: 'CONFIG_R1_BACKFILL',
        resource_type: 'config_energy_conversion_factors',
        resource_id: '42',
        detail_json: {
          energy_type: 'ELECTRICITY',
          value_type: 'EQUIVALENT',
          toe_factor: 0.086,
          standard_coal_factor: 0.1229,
          reason: 'F-P0-001 R1 backfill (Sprint 3 Issue 6)',
        },
        occurred_at: '2026-10-03T08:00:00+00:00',
      },
      {
        audit_id: '22222222-2222-2222-2222-222222222222',
        user_id: '00000000-0000-0000-0000-000000000001',
        action: 'CONFIG_R1_BACKFILL',
        resource_type: 'config_energy_conversion_factors',
        resource_id: '99',
        detail_json: { energy_type: 'STEAM', pressure_level: 'GE_7_0_MPA' },
        occurred_at: '2026-10-03T08:01:00+00:00',
      },
    ];
    const filtered = assetId
      ? seed.filter((s) => s.resource_id === String(assetId))
      : seed;
    return HttpResponse.json({
      items: filtered,
      total: filtered.length,
      limit: 50,
      offset: 0,
    });
  }),

  // /equipment-deletion-audit: DESIGNER+ + project_id 必传.
  http.get('/api/v1/equipment-deletion-audit', ({ request }) => {
    if (!isAuthed(request)) {
      return HttpResponse.json({ code: 'MISSING_BEARER' }, { status: 401 });
    }
    const url = new URL(request.url);
    const projectId = url.searchParams.get('project_id');
    if (!projectId) {
      return HttpResponse.json(
        { code: 'FORBIDDEN', message: 'project_id required for non-system-admin' },
        { status: 403 },
      );
    }
    return HttpResponse.json({
      items: [
        {
          audit_id: '33333333-3333-3333-3333-333333333333',
          equipment_id: '44444444-4444-4444-4444-444444444444',
          project_id: projectId,
          workspace_id: '55555555-5555-5555-5555-555555555555',
          equipment_tag: 'E-001',
          deleted_by: '00000000-0000-0000-0000-000000000001',
          orphan_records: { power_items: [], fuel_gas: [], heat_exchange: [] },
          occurred_at: '2026-10-03T07:00:00+00:00',
          reason: 'mock deletion',
        },
      ],
      total: 1,
      limit: 50,
      offset: 0,
    });
  }),

  // /audit-logs: SYSTEM_ADMIN only (403 if non-admin).
  http.get('/api/v1/audit-logs', ({ request }) => {
    if (!isAuthed(request)) {
      return HttpResponse.json({ code: 'MISSING_BEARER' }, { status: 401 });
    }
    // dev mode: 永远返回 (简化 — 实际后端会做 SYSTEM_ADMIN gate)
    return HttpResponse.json({
      items: [
        {
          audit_id: '66666666-6666-6666-6666-666666666666',
          user_id: '00000000-0000-0000-0000-000000000001',
          action: 'RECORD_CREATED',
          resource_type: 'config_energy_conversion_factors',
          resource_id: '42',
          detail_json: {},
          occurred_at: '2026-10-03T09:00:00+00:00',
        },
      ],
      total: 1,
      limit: 50,
      offset: 0,
    });
  }),
);

/** 后端 OpenAPI 契约端点（meta 5 端点）。handlers 数组统一导出；test 端 OpenAPI drift
 * 校验只针对这一组，devOnlyMockHandlers 通过拼接传入 setupWorker。 */
export const handlers = [
  http.get("/api/v1/meta/enums", ({ request }) => {
    if (!isAuthed(request)) return HttpResponse.json({ code: "MISSING_BEARER", message: "..." }, { status: 401 });
    return HttpResponse.json(metaSeed.enums);
  }),

  http.get("/api/v1/meta/state-machine", ({ request }) => {
    if (!isAuthed(request)) return HttpResponse.json({ code: "MISSING_BEARER" }, { status: 401 });
    return HttpResponse.json(metaSeed.stateMachine);
  }),

  http.get("/api/v1/meta/permissions", ({ request }) => {
    if (!isAuthed(request)) return HttpResponse.json({ code: "MISSING_BEARER" }, { status: 401 });
    return HttpResponse.json(metaSeed.permissions);
  }),

  http.get("/api/v1/meta/permissions.csv", ({ request }) => {
    if (!isAuthed(request)) return HttpResponse.json({ code: "MISSING_BEARER" }, { status: 401 });
    const lines = ["role,resource,action,permission_code,frontend_behavior"];
    for (const p of metaSeed.permissions) {
      lines.push([p.role, p.resource, p.action, p.permission_code, p.frontend_behavior].join(","));
    }
    return new HttpResponse(lines.join("\n") + "\n", {
      headers: {
        "Content-Type": "text/csv",
        "Content-Disposition": "attachment; filename=permissions.csv",
      },
    });
  }),

  http.get("/api/v1/meta/error-codes", ({ request }) => {
    if (!isAuthed(request)) return HttpResponse.json({ code: "MISSING_BEARER" }, { status: 401 });
    return HttpResponse.json(metaSeed.errorCodes);
  }),
];

export const mockAuthToken = MOCK_TOKEN;
export { devOnlyMockHandlers };