/**
 * MSW handlers — 离线 mock server（P45-0-5）
 *
 * 覆盖 meta 4 端点 + permissions.csv；其他端点（streams / workspaces / records）
 * 在 Task 5.x 增量补。前端 13 组件 + SchemaForm 离线开发可用。
 */
import { http, HttpResponse } from "msw";

import { metaSeed, MOCK_TOKEN } from "./seed/meta";

/** JWT 守卫 — 无 token → 401 */
function isAuthed(req: Request): boolean {
  const auth = req.headers.get("Authorization");
  return !!auth && auth.startsWith("Bearer ") && auth !== "Bearer ";
}

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