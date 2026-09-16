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

import { metaSeed, MOCK_TOKEN } from "./seed/meta";
import { seedAssets } from "./seed/config";
import { seedAllowableStress, seedMaterials, seedToxicityClasses } from "./seed/common";
import { seedPipeClasses } from "./seed/pipe-classes";
import { seedPipeLineRows } from "./seed/pipe-line";
import { seedBeddSections, seedPmsItems } from "./seed/pms";
import { seedStreams } from "./seed/streams";
import { seedChecklist, seedWorkspaces } from "./seed/workspaces";

/** JWT 守卫 — 无 token → 401 */
function isAuthed(req: Request): boolean {
  const auth = req.headers.get("Authorization");
  return !!auth && auth.startsWith("Bearer ") && auth !== "Bearer ";
}

const ROLE_BY_USER: Record<string, string> = {
  alice: "DESIGNER",
  bob: "CHECKER",
  carol: "APPROVER",
  dan: "SYSADMIN",
};

/** V1 mock-only 端点：仅 dev 环境使用，不在 OpenAPI 中（QA fix / ISSUE-001 + 11 组件实例化） */
const devOnlyMockHandlers = [
  // === 认证 ===
  http.post("/api/v1/auth/mock-login", async ({ request }) => {
    const body = (await request.json()) as { username?: string };
    const username = body.username ?? "alice";
    const role = ROLE_BY_USER[username] ?? "DESIGNER";
    return HttpResponse.json({
      access_token: MOCK_TOKEN,
      refresh_token: `${MOCK_TOKEN}.refresh`,
      token_type: "bearer",
      role,
      username,
    });
  }),

  // === 物流 SIM ===
  http.get("/api/v1/projects/:project_id/streams", ({ request }) => {
    if (!isAuthed(request)) return HttpResponse.json({ code: "MISSING_BEARER" }, { status: 401 });
    return HttpResponse.json(seedStreams);
  }),
  http.get("/api/v1/streams/:stream_id", ({ request, params }) => {
    if (!isAuthed(request)) return HttpResponse.json({ code: "MISSING_BEARER" }, { status: 401 });
    const s = seedStreams.find((x) => x.stream_id === params.stream_id);
    return s
      ? HttpResponse.json(s)
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
];

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