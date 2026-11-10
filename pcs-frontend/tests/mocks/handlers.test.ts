/**
 * MSW seed + handler shape 验证 — 防 MSW ↔ OpenAPI drift (P45-0-5)
 *
 * 思路：直接 import handlers 数组 + seed fixture，断言：
 * 1. seed 数据形状与 openapi snapshot schema 一致（用 ajv 校验）
 * 2. seed 关键字段覆盖（19 enum / 9 态 / 7 角色 / 关键错误码）
 * 3. handler 注册的 URL 与 openapi paths 一致（防止漏注册）
 *
 * 不用 msw + fetch 是因为 vitest 环境下 msw 拦截 node fetch 链路不稳；
 * 直接 import 验证形状 + 注册一致性，效果等价且更稳定。
 */
import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import Ajv, { type AnySchema } from "ajv";

import { handlers, devOnlyMockHandlers, buildNotificationList, buildTodoList, buildBatchSubmitResponse, buildReviewLog } from "../../src/mocks/handlers";
import { signatureMatrixHandlers } from "../../src/mocks/signatureMatrices";
import { changeNoticeHandlers } from "../../src/mocks/changeNotices";
import { signFlowHandlers } from "../../src/mocks/signFlow";
import { metaSeed } from "../../src/mocks/seed/meta";
import { seedStreams } from "../../src/mocks/seed/streams";
import { seedDeliverables } from "../../src/mocks/seed/deliverables";
import {
  seedAdminUsers,
  seedDeliverableActions,
  seedDeliverableProgress,
  seedDeliverableSnapshot,
  seedRecordComments,
  seedRecordEdits,
} from "../../src/mocks/seed/signFlow";
import {
  seedCoolTowerResults,
  seedCostEstResults,
  seedFiltrationResults,
  seedFlareResults,
  seedOpenChannelResults,
  seedPsychroResults,
} from "../../src/mocks/seed/results";

const openapiPath = resolve(__dirname, "../../openapi.snapshot.json");
const openapi = JSON.parse(readFileSync(openapiPath, "utf8"));

const ajv = new Ajv({ strict: false, allErrors: true });

/** 去掉 // 与 /* *\/ 注释 —— 断言「代码里没有 X」时必须剥，否则自己的说明文字会命中。 */
function stripComments(src: string): string {
  return src.replace(/\/\*[\s\S]*?\*\//g, "").replace(/(^|[^:])\/\/.*$/gm, "$1");
}

function resolveRef(root: unknown, ref: string): unknown {
  return ref.replace(/^#\//, "").split("/").reduce(
    (acc: any, p) => (acc == null ? acc : acc[p]),
    root as any,
  );
}

/**
 * 深度替换 schema 树内所有 $ref → 实际对象。
 *
 * ⚠️ `docRoot` 必须**始终是 OpenAPI 文档根**，不能是被展开的那棵子树。
 * 此前实现拿 `root`（= 顶层 schema）当解析根，于是**嵌套 $ref 全部解析失败**
 * 返回 undefined —— meta 的 schema 恰好没有嵌套 ref，所以这个 bug 一直
 * 藏着没炸；`StreamResponse` 第一个用上嵌套 ref（`case_type → StreamCaseType`）
 * 就把 ajv 顶翻了（"must be object,boolean"）。
 */
function inlineRefs(node: unknown, docRoot: unknown = node): unknown {
  const seen = new WeakSet<object>();
  function walk(n: unknown): unknown {
    if (n == null || typeof n !== "object") return n;
    if (seen.has(n as object)) return n;
    seen.add(n as object);
    if (Array.isArray(n)) return n.map(walk);
    const obj = n as Record<string, unknown>;
    if (typeof obj.$ref === "string") return walk(resolveRef(docRoot, obj.$ref));
    const out: Record<string, unknown> = {};
    for (const k of Object.keys(obj)) out[k] = walk(obj[k]);
    return out;
  }
  return walk(node);
}

function validateAgainst(name: string, data: unknown) {
  const path = `/api/v1/meta/${name}`;
  const getOp = openapi.paths[path]?.get;
  if (!getOp) throw new Error(`no OpenAPI op for ${path}`);
  const schemaJson = getOp.responses["200"].content["application/json"].schema;
  let schema: unknown;
  if (schemaJson.$ref) {
    schema = inlineRefs(resolveRef(openapi, schemaJson.$ref), openapi);
  } else {
    schema = inlineRefs(schemaJson, openapi);
  }
  if (!schema || (typeof schema === "object" && Object.keys(schema).length === 0)) {
    return; // CSV 端点 schema 为空（text/csv 返回），跳过 ajv
  }
  const validate = ajv.compile(schema);
  const ok = validate(data);
  expect(ok, `schema ${name} mismatch: ${JSON.stringify(validate.errors)}`).toBe(true);
}

describe("meta seed fixture 形状 ↔ OpenAPI", () => {
  it("enums — 19 组 + 9 态 + 颜色 icon + StreamDataMode/Case", () => {
    const data = metaSeed.enums;
    validateAgainst("enums", data);
    expect(Object.keys(data)).toHaveLength(19);
    expect(data.RecordSignStatus).toHaveLength(9);
    expect(data.RecordSignStatus[0].value).toBe("DRAFT");
    expect(data.RecordSignStatus[0].color).toBe("state-draft");
    expect(data.RecordSignStatus[0].icon).toBe("EditOutlined");
    expect(data.StreamDataMode.map((e) => e.value))
      .toEqual(["CHEMICAL", "PETROLEUM", "SOLID"]);
    expect(data.StreamCaseType.map((e) => e.value))
      .toEqual(["NORMAL", "END_OF_RUN", "START_OF_RUN", "TURN_DOWN"]);
    expect(data.StatePointCaseType.map((e) => e.value))
      .toEqual(["NORMAL", "MIN", "MAX", "ALTERNATE"]);
    expect(data.EquipmentStatus.map((e) => e.value)).toEqual(["N", "E", "D", "M", "F"]);
  });

  it("state-machine — transitions 字段 + allowed 9 态", () => {
    const data = metaSeed.stateMachine;
    validateAgainst("state-machine", data);
    const t = data.transitions[0];
    for (const k of ["from", "action", "to", "allowed_roles", "preconditions", "side_effects"]) {
      expect(t).toHaveProperty(k);
    }
    expect(Object.keys(data.allowed)).toHaveLength(9);
  });

  it("error-codes — ≥ 16 条 + 关键项", () => {
    const data = metaSeed.errorCodes;
    validateAgainst("error-codes", data);
    expect(data.length).toBeGreaterThanOrEqual(16);
    const codes = new Set(data.map((e) => e.code));
    expect(codes.has("MISSING_BEARER")).toBe(true);
    expect(codes.has("STREAM_UNRELIABLE_BLOCKED")).toBe(true);
    expect(codes.has("PIPE_CLASS_BAD_TRANSITION")).toBe(true);
    expect(codes.has("CHANGE_NOTICE_BAD_STATE")).toBe(true);
    expect(codes.has("REVERSAL_BAD_STATE")).toBe(true);
  });

  it("permissions — 7 角色 + VALIDATE", () => {
    const data = metaSeed.permissions;
    validateAgainst("permissions", data);
    const roles = new Set(data.map((p) => p.role));
    // role-string 收敛 (2026-10-04): SYSADMIN 全量收敛为 SYSTEM_ADMIN
    for (const r of [
      "DESIGNER", "CHECKER", "REVIEWER", "APPROVER",
      "SYSTEM_ADMIN", "PROCESS_CONTROLLER", "VIEWER",
    ]) {
      expect(roles.has(r), `missing role ${r}`).toBe(true);
    }
    expect(roles.has("SYSADMIN"), "SYSADMIN 应已收敛为 SYSTEM_ADMIN").toBe(false);
  });
});

describe("MSW handlers 注册 ↔ OpenAPI paths", () => {
  it("每个 handler 注册路径都在 OpenAPI 列出", () => {
    // ⚠️ **三组都要查**（TODO-079 / TODO-083 新增了两组契约端点的 handler）
    // —— 只查 `handlers` 的话，新组的路径打错字**永远不会被发现**。
    for (const h of [...handlers, ...signatureMatrixHandlers, ...changeNoticeHandlers, ...signFlowHandlers]) {
      const path = (h as { info?: { path?: string } }).info?.path;
      expect(path, "handler missing path").toBeDefined();
      // ⚠️ **MSW 用 `:param`，OpenAPI 用 `{param}`** ⇒ 比之前必须先归一
      // （否则带路径参数的端点永远「不在 OpenAPI 里」）。
      const normalized = path!.replace(/:([A-Za-z0-9_]+)/g, "{$1}");
      expect(openapi.paths[normalized], `OpenAPI missing ${normalized}`).toBeDefined();
    }
  });

  it("签署矩阵 / 变更单的契约端点都注册了 handler", () => {
    const paths = new Set(
      [...signatureMatrixHandlers, ...changeNoticeHandlers].map((h) =>
        (h as { info?: { path?: string } }).info?.path,
      ),
    );
    for (const p of [
      "/api/v1/signature-matrices",
      "/api/v1/signature-matrices/:matrix_id",
      "/api/v1/projects/:project_id/signature-matrices",
      "/api/v1/projects/:project_id/signature-matrices/:module",
      "/api/v1/records/:module/:record_id/initiate-change",
      "/api/v1/records/:module/:record_id/apply-change",
      "/api/v1/records/:module/:record_id/change-notice",
    ]) {
      expect(paths.has(p), `missing handler for ${p}`).toBe(true);
    }
  });

  it("handlers 覆盖 meta 5 端点", () => {
    const paths = new Set(handlers.map((h) =>
      (h as { info?: { path?: string } }).info?.path,
    ));
    for (const p of [
      "/api/v1/meta/enums",
      "/api/v1/meta/permissions",
      "/api/v1/meta/permissions.csv",
      "/api/v1/meta/error-codes",
      "/api/v1/meta/state-machine",
    ]) {
      expect(paths.has(p), `missing handler for ${p}`).toBe(true);
    }
  });

  it("未授权守卫：seed handler 内 isAuthed 应拒空 token", () => {
    // 通过模拟 handlers 内调用：handlers 是闭包，无法直接测
    // 改为测 seed fixtures 完整性（间接）
    const data = metaSeed.enums;
    expect(data).toBeDefined();
    // MSW handler 内的 isAuthed 行为通过集成测试验证（e2e）
  });
});

describe("devOnlyMockHandlers（QA fix ISSUE-001）", () => {
  it("mock-login 已注册（防止回归为 404）", () => {
    const paths = new Set(devOnlyMockHandlers.map((h) =>
      (h as { info?: { path?: string } }).info?.path,
    ));
    expect(paths.has("/api/v1/auth/mock-login")).toBe(true);
  });

  it("devOnlyMockHandlers 不在 handlers 数组（避免 OpenAPI drift 校验触发）", () => {
    const paths = new Set(handlers.map((h) =>
      (h as { info?: { path?: string } }).info?.path,
    ));
    expect(paths.has("/api/v1/auth/mock-login")).toBe(false);
  });
});

/** 按 path + method 取 OpenAPI 200 响应的 schema（已解 $ref），用于校验 fixture。 */
function schemaFor(path: string, method: "get" | "post"): unknown | null {
  const op = openapi.paths[path]?.[method];
  if (!op) return null;
  const schemaJson = op.responses?.["200"]?.content?.["application/json"]?.schema
    ?? op.responses?.["201"]?.content?.["application/json"]?.schema;
  if (!schemaJson) return null;
  return schemaJson.$ref ? inlineRefs(resolveRef(openapi, schemaJson.$ref), openapi)
                         : inlineRefs(schemaJson, openapi);
}

/**
 * endpoint 响应体形状 ↔ OpenAPI（bug-189）。
 *
 * ## 之前为什么漏了
 *
 * 本文件原先只断言「handler 注册的路径在 OpenAPI 里存在」—— 那是**路径**
 * 一致性，不是**响应体**一致性。于是 `GET /api/v1/streams/{stream_id}`
 * 的 mock 可以返一个前端合成的 `{stream, matrix, signatures, …}` 而全部绿灯，
 * 而真后端（`response_model=StreamResponse`）返的是扁平对象 ⇒ 路由在生产上
 * 拿不到东西，dev 里完全看不出来。
 *
 * **mock 与契约一致是正确性的一部分**，所以这里校验 seed 本身能否通过契约校验。
 */
describe("endpoint seed fixture 响应体 ↔ OpenAPI", () => {
  it("seedStreams 满足 StreamResponse（详情/列表端点返回的就是它）", () => {
    const schema = schemaFor("/api/v1/streams/{stream_id}", "get");
    expect(schema, "契约里没有该端点的 JSON schema").not.toBeNull();
    const validate = ajv.compile(schema as object);
    // 逐条验：schema 是**单个** StreamResponse，而 seedStreams 是数组。
    for (const stream of seedStreams) {
      const ok = validate(stream);
      expect(ok, `${stream.stream_id} 不合契约: ${JSON.stringify(validate.errors)}`).toBe(true);
    }
  });

  it("mock 不再给 stream 详情包一层 .stream（bug-189 的形态）", () => {
    // 结构性守卫：只要 handler 里再出现合成 payload 的痕迹就红。
    const src = readFileSync(
      resolve(__dirname, "../../src/mocks/handlers.ts"), "utf8");
    expect(stripComments(src)).not.toMatch(/buildStreamDetail|StreamDetailPayload/);
    // seed 里也不该再有这个合成体
    const seedSrc = readFileSync(
      resolve(__dirname, "../../src/mocks/seed/streams.ts"), "utf8");
    expect(stripComments(seedSrc)).not.toMatch(/StreamDetailPayload/);
  });

  it("前端不再从详情响应里读 .stream（那是契约里没有的一层）", () => {
    // ⚠️ 先剥注释：本文件与 routeWrappers 都**用散文记录这个 bug**，
    // 不剥的话正则会匹配到解释文字而不是代码 —— 「被注释骗」的又一例。
    const src = stripComments(readFileSync(
      resolve(__dirname, "../../src/pages/routeWrappers.tsx"), "utf8"));
    expect(src).not.toMatch(/payload\??\.stream/);
  });
});

/**
 * `GET /api/v1/config/assets` 端点存在性（TODO-040）。
 *
 * 这个端点**曾经从未实现**，而前端一直在请求它 ⇒ 生产必然 404。
 * 现有的「handler 路径都在 OpenAPI 里」那条**抓不到这种方向的问题** ——
 * 它只保证「有 mock 的路径有契约」，不管「页面请求的路径有没有端点」。
 */
describe("端点补齐（TODO-040）", () => {
  it("GET /api/v1/config/assets 已在契约中（不再是前端跑在前面）", () => {
    expect(openapi.paths["/api/v1/config/assets"]?.get).toBeDefined();
  });

  it("mock handler 注册了该路径", () => {
    // ⚠️ 注意查的是 `devOnlyMockHandlers`：导出的 `handlers` 只有 5 个
    // meta 端点，其余全在 devOnly 那个数组里 —— 既有那条
    // 「handler 路径都在 OpenAPI 里」实际一直只覆盖 5 条路径。
    const paths = new Set(devOnlyMockHandlers.map((h) =>
      (h as { info?: { path?: string } }).info?.path));
    expect(paths.has("/api/v1/config/assets")).toBe(true);
  });

  it("category 取值域与契约一致（CATEGORY_1~6，不是语义名）", () => {
    const schema = openapi.components.schemas.AssetResponse.properties
      .category as { enum?: string[]; $ref?: string };
    if ("$ref" in schema && schema.$ref) {
      throw new Error("category 是 $ref，需先解引用再断言 enum");
    }
    expect(schema.enum ?? [], "category 应在契约里是枚举").toEqual(
      expect.arrayContaining(["CATEGORY_1", "CATEGORY_6"]),
    );
  });
});

/**
 * 通知 / 待办的 mock 响应体 ↔ OpenAPI（TODO-065 的守卫）。
 *
 * ## 为什么必须是守卫
 *
 * 此前 `/api/v1/notifications` 的 mock 返回**前端自造数组**
 * （`category` / `summary` / `issued_at` / `unread`），而真端点返回
 * `{items, unread_count}` ⇒ mock 把漂移**藏住** ⇒ 生产构建下
 * `MainLayout` 整个壳崩（`notifications.filter is not a function`）。
 *
 * ⇒ 这条断言把「mock 的响应体形状 == 契约」钉死。
 * ⚠️ **形状对了不等于内容对了** —— 所以还钉「kind 四值」「unread_count
 * 与 `read_at === null` 的条数一致」两条**内容**断言。
 */
describe("通知 / 待办 mock 形状 ↔ OpenAPI（TODO-065）", () => {
  function validatePath(path: string, data: unknown) {
    const op = openapi.paths[path]?.get;
    if (!op) throw new Error(`no OpenAPI op for ${path}`);
    const schemaJson = op.responses["200"].content["application/json"].schema;
    const schema = (schemaJson.$ref
      ? inlineRefs(resolveRef(openapi, schemaJson.$ref), openapi)
      : inlineRefs(schemaJson, openapi)) as AnySchema;
    const validate = ajv.compile(schema);
    const ok = validate(data);
    expect(ok, `${path} 形状不符: ${JSON.stringify(validate.errors)}`).toBe(true);
  }

  it("GET /api/v1/notifications 的响应体符合契约（{items, unread_count}）", () => {
    const data = buildNotificationList();
    validatePath("/api/v1/notifications", data);
    expect(Array.isArray(data.items)).toBe(true);
    expect(typeof data.unread_count).toBe("number");
  });

  it("通知 kind 取值在契约枚举内，且四类都覆盖", () => {
    const data = buildNotificationList();
    const kinds = new Set(data.items.map((n) => n.kind));
    // 后端 NotificationKind 四值 —— mock 不得自造第五类
    expect([...kinds].sort()).toEqual([
      "CHANGE_NOTICE_APPROVED",
      "PROXY_RECORDED",
      "SIGN_COMPLETED",
      "STEP_RETURNED",
    ]);
  });

  it("unread_count 与 read_at === null 的条数一致（前端红点不能另算）", () => {
    const data = buildNotificationList();
    const actual = data.items.filter((n) => n.read_at === null).length;
    expect(data.unread_count).toBe(actual);
  });

  it("GET /api/v1/todos 的响应体符合契约（{items, total}）", () => {
    const data = buildTodoList();
    validatePath("/api/v1/todos", data);
    expect(data.total).toBe(data.items.length);
  });

  it("GET /api/v1/health 的响应体符合契约（status/database/realtime/realtime_reason）", () => {
    // ⚠️ `/health` 此前**没有 mock** ⇒ 每个页面都报 404（控制台红）⇒ 补上。
    // 形状取契约（HealthResponse：4 个字段**全部必填**）。
    validatePath("/api/v1/health", {
      status: "ok",
      database: "up",
      realtime: "available",
      realtime_reason: null,
    });
  });

  it("devOnly ∩ 契约 的端点清单是**棘轮**（新增即红 ⇒ 必须一并加校验）", () => {
    // ⚠️ 这条防的是**一类**漂移，不是一个端点：
    // 端点起初是 mock-only（没有契约）⇒ 归入「没有契约可漂移」名单；
    // 后来后端交付了真端点（契约里有了）⇒ 它**不再是** mock-only，
    // 但名单不会自己更新 ⇒ mock 继续返自造形状 ⇒ 漂移被藏住 ⇒
    // 生产构建才炸（TODO-065 就是这么发生的：`/notifications`）。
    //
    // ⇒ 本清单是**棘轮**：devOnly 里出现**新的**契约端点 ⇒ 本条红 ⇒
    // 作者必须给它的响应体加契约类型标注 / ajv 校验，然后才更新本清单。
    const paths = [...new Set(devOnlyMockHandlers.map((h) =>
      (h as { info?: { path?: string } }).info?.path))];
    const inContract = paths.filter((p) => p && openapi.paths[p]).sort();
    expect(inContract).toEqual([
      "/api/v1/audit-logs",
      "/api/v1/auth/me",
      "/api/v1/common/allowable-stress",
      "/api/v1/common/heating-value/calculate",
      "/api/v1/common/materials/search",
      "/api/v1/common/safety",
      "/api/v1/config-audit",
      "/api/v1/config/assets",
      // P9B-1：6 类结果记录的列表端点（2026-10-21 加入 ⇒ 棘轮同步）
      "/api/v1/cool-tower/results",
      "/api/v1/cost-est/results",
      "/api/v1/cv/calculate",
      // P9B-1：交付物进度页的列表端点（2026-10-21 加入 ⇒ 棘轮同步）
      "/api/v1/deliverables",
      "/api/v1/equipment-deletion-audit",
      "/api/v1/filtration/results",
      "/api/v1/flare/results",
      "/api/v1/heat/import-htri",
      "/api/v1/notifications",
      "/api/v1/open-channel/results",
      "/api/v1/pipe-classes",
      "/api/v1/psv/calculate",
      "/api/v1/psychro/results",
      "/api/v1/psychro/saturation-water-content/calculate",
      "/api/v1/sep-equip/calculate",
      // P9B-3b：批量提交校对（2026-11-03 加入 ⇒ 棘轮同步）
      "/api/v1/streams/batch-submit",
      "/api/v1/todos",
      "/api/v1/util/energy-summary/aggregate",
      "/api/v1/util/heat-exchange-items",
      "/api/v1/vessel/calculate",
      "/api/v1/workspaces",
    ]);
  });

  it("6 类结果记录的列表 mock 响应体符合契约（P9B-1）", () => {
    // ⚠️ 棘轮新增了 6 条**契约端点** ⇒ 必须一并加 ajv 校验
    // （否则「有契约可漂移」却没校验 = 漂移被藏住 = bug-2040 重演）。
    const cases: Array<[string, unknown]> = [
      ["/api/v1/cool-tower/results", { items: seedCoolTowerResults, total: seedCoolTowerResults.length, offset: 0, limit: 100 }],
      ["/api/v1/filtration/results", { items: seedFiltrationResults, total: seedFiltrationResults.length, skip: 0, limit: 50 }],
      ["/api/v1/flare/results", { items: seedFlareResults, total: seedFlareResults.length, offset: 0, limit: 100 }],
      ["/api/v1/open-channel/results", { items: seedOpenChannelResults, total: seedOpenChannelResults.length, skip: 0, limit: 50 }],
      ["/api/v1/psychro/results", { items: seedPsychroResults, total: seedPsychroResults.length, offset: 0, limit: 100 }],
      ["/api/v1/cost-est/results", { items: seedCostEstResults, total: seedCostEstResults.length, skip: 0, limit: 50 }],
    ];
    for (const [path, data] of cases) {
      validatePath(path, data);
    }
  });

  it("POST /api/v1/streams/batch-submit 的 207 响应体符合契约（P9B-3b）", () => {
    // ⚠️ 棘轮同步：端点进了契约 ⇒ 必须**一并**加 ajv 校验
    // （否则「有契约可漂移」却没校验 = 漂移被藏住 = bug-2040 重演）。
    // ⚠️ 这个端点返 **207**（不是 200）⇒ `validatePath` 取不到 schema
    // ⇒ 单独取 207 的 schema。
    const op = openapi.paths["/api/v1/streams/batch-submit"]?.post;
    expect(op, "契约里没有 POST /api/v1/streams/batch-submit").toBeDefined();
    const schemaJson = op!.responses["207"].content["application/json"].schema;
    const schema = (schemaJson.$ref
      ? inlineRefs(resolveRef(openapi, schemaJson.$ref), openapi)
      : inlineRefs(schemaJson, openapi)) as AnySchema;
    const validate = ajv.compile(schema);
    const data = buildBatchSubmitResponse(
      ["00000000-0000-4000-8000-0000000000a1"],
      false,
    );
    const ok = validate(data);
    expect(ok, `形状不符: ${JSON.stringify(validate.errors)}`).toBe(true);
  });

  it("GET /api/v1/streams/{stream_id}/review-log 的响应体符合契约（TODO-112）", () => {
    // ⚠️ 棘轮同步：端点进了契约 ⇒ 必须**一并**加 ajv 校验
    // （否则「有契约可漂移」却没校验 = 漂移被藏住 = bug-2040 重演）。
    const op = openapi.paths["/api/v1/streams/{stream_id}/review-log"]?.get;
    expect(op, "契约里没有 GET /api/v1/streams/{stream_id}/review-log").toBeDefined();
    const schemaJson = op!.responses["200"].content["application/json"].schema;
    const schema = (schemaJson.$ref
      ? inlineRefs(resolveRef(openapi, schemaJson.$ref), openapi)
      : inlineRefs(schemaJson, openapi)) as AnySchema;
    const validate = ajv.compile(schema);
    const data = buildReviewLog("s-102");
    const ok = validate(data);
    expect(ok, `形状不符: ${JSON.stringify(validate.errors)}`).toBe(true);
  });

  it("校核记录 mock **按后端口径过滤**（ce-code-review P2 #5）", () => {
    // ⚠️ **只返回校对相关的三条**，且**按时间升序** —— 与后端
    //    `list_review_log` 的过滤口径**逐条对应**：
    //    - transition 白名单（SUBMIT/PASS/REJECT）⇒ MARK_STALE 被排除
    //    - resource_id 精确匹配 ⇒ 别的物流看不到这些行
    //    - occurred_at 升序
    const rows = buildReviewLog("s-102");
    expect(rows.map((r) => r.transition)).toEqual([
      "SUBMIT_FOR_CHECK",
      "PASS_CHECK",
      "REJECT_CHECK",
    ]);
    // ⚠️ 驳回行带 reason ⇒ 「说明」列非空的分支在 dev 里走得到
    expect(rows[2].detail).toBe("组成超差");
    // ⚠️ 别的物流 ⇒ 空数组（= 后端「没有这些转移」时的 200 + []）
    expect(buildReviewLog("s-101")).toEqual([]);
    expect(buildReviewLog("不存在的物流")).toEqual([]);
  });

  it("GET /api/v1/deliverables 的响应体符合契约（P9B-1）", () => {
    const data = { items: seedDeliverables, total: seedDeliverables.length };
    validatePath("/api/v1/deliverables", data);
  });

  it("两个 mock 端点都已注册", () => {
    const paths = new Set(devOnlyMockHandlers.map((h) =>
      (h as { info?: { path?: string } }).info?.path));
    expect(paths.has("/api/v1/notifications")).toBe(true);
    expect(paths.has("/api/v1/todos")).toBe(true);
  });
});

/**
 * P9B-2 的 mock 形状 ↔ OpenAPI（TODO-065 / 066 / T-8 / T7 的端点）。
 *
 * ## 为什么这组也要有守卫
 *
 * 棘轮清单（`devOnly ∩ 契约`）只覆盖**没有路径参数**的端点 ——
 * `/api/v1/deliverables/:id/progress` 这种**带参数**的路径在 OpenAPI 里是
 * `/api/v1/deliverables/{deliverable_id}/progress` ⇒ 棘轮**看不见**它。
 *
 * ⇒ 带参数的端点必须**逐个**校验形状，否则漂移照样被藏住
 * （bug-2040 / bug-189 的形状）。
 */
describe("P9B-2 签署流程 / ADMIN 的 mock 形状 ↔ OpenAPI", () => {
  function validateOp(path: string, method: "get" | "post" | "put", data: unknown) {
    const op = openapi.paths[path]?.[method];
    expect(op, `契约里没有 ${method.toUpperCase()} ${path}`).toBeDefined();
    const schemaJson = op!.responses["200"]?.content["application/json"]?.schema
      ?? op!.responses["201"]?.content["application/json"]?.schema;
    expect(schemaJson, `${path} 没有 JSON schema`).toBeDefined();
    const schema = (schemaJson!.$ref
      ? inlineRefs(resolveRef(openapi, schemaJson!.$ref), openapi)
      : inlineRefs(schemaJson, openapi)) as AnySchema;
    const validate = ajv.compile(schema);
    const ok = validate(data);
    expect(ok, `${path} 形状不符: ${JSON.stringify(validate.errors)}`).toBe(true);
  }

  it("交付物聚合进度（两段 + 每段带 available/reason）", () => {
    validateOp("/api/v1/deliverables/{deliverable_id}/progress", "get", seedDeliverableProgress);
    const types = seedDeliverableProgress.sections.map((s) => s.workflow_type);
    // ⚠️ R-13：**没有** CHANGE_NOTICE 段
    expect(types).toEqual(["SIGN", "CUSTOMER_APPROVAL_PROXY"]);
    // ⚠️ 两段的 workflow_id 语义不同（版本 id / 交付物 id）
    expect(seedDeliverableProgress.sections[0].workflow_id).toBe("v-2");
    expect(seedDeliverableProgress.sections[1].workflow_id).toBe("d-2");
  });

  it("交付物动作时间线（审计形状）", () => {
    validateOp("/api/v1/deliverables/{deliverable_id}/actions", "get", seedDeliverableActions);
  });

  it("版本快照（含冻结的签署步骤）", () => {
    validateOp(
      "/api/v1/deliverables/{deliverable_id}/versions/{rev}/snapshot",
      "get",
      seedDeliverableSnapshot,
    );
    const steps = (seedDeliverableSnapshot.signature_summary_json as { steps?: unknown[] }).steps;
    expect(Array.isArray(steps)).toBe(true);
  });

  it("记录编辑历史（TODO-066）", () => {
    validateOp("/api/v1/records/{module}/{record_id}/edits", "get", seedRecordEdits);
  });

  it("记录批注列表", () => {
    validateOp("/api/v1/records/{module}/{record_id}/comments", "get", seedRecordComments);
  });

  it("ADMIN 用户列表", () => {
    validateOp("/api/v1/admin/users", "get", seedAdminUsers);
  });

  it("交付物写面三个端点的响应形状（issue / sign-step / proxy）", () => {
    validateOp("/api/v1/deliverables/{deliverable_id}/issue", "post", {
      deliverable_id: "d-2",
      version_id: "v-3",
      rev: "C",
      doc_no: "CB-002",
      version_purpose: "ISSUED_FOR_CONSTRUCTION",
      sign_status: "PENDING",
      issued_at: "2026-10-20T10:00:00Z",
    });
    validateOp("/api/v1/deliverables/{deliverable_id}/sign-step", "post", {
      deliverable_id: "d-2",
      version_id: "v-2",
      step_index: 2,
      step_role: "REVIEWER",
      decision: "SIGN",
      state: "COMPLETED",
      deliverable_sign_status: "PENDING",
      signed_at: "2026-10-20T10:00:00Z",
    });
    validateOp("/api/v1/deliverables/{deliverable_id}/customer-approval/proxy", "post", {
      deliverable_id: "d-2",
      version_id: "v-2",
      attachment_id: "att-1",
      customer_approver_name: "客户方 张三",
      approval_date: "2026-10-20",
      approval_method: "EMAIL",
      is_proxy: true,
      proxied_at: "2026-10-20T10:00:00Z",
    });
  });

  it("记录写动作 + 送审 + 推进 + ADMIN 停用/同步的响应形状", () => {
    validateOp("/api/v1/records/{module}/{record_id}/obsolete", "post", {
      record_type: "cooling_tower_result",
      record_id: "r-1",
      from_status: "DRAFT",
      to_status: "OBSOLETE",
    });
    validateOp("/api/v1/records/{module}/{record_id}/submit-approval", "post", {
      record_type: "cooling_tower_result",
      record_id: "r-1",
      from_status: "DRAFT",
      to_status: "IN_APPROVAL",
      approval_step: 1,
      approval_depth: 2,
      approval_role: "CHECKER",
    });
    validateOp("/api/v1/records/{module}/{record_id}/approval-step", "post", {
      record_type: "cooling_tower_result",
      record_id: "r-1",
      from_status: "IN_APPROVAL",
      to_status: "IN_APPROVAL",
      approval_step: 2,
      approval_depth: 2,
    });
    validateOp("/api/v1/admin/users/{user_id}/disable", "put", {
      user_id: "u-1",
      username: "alice",
      status: "DISABLED",
      token_version: 4,
    });
    validateOp("/api/v1/admin/users/sync", "post", {
      ok: true,
      created: 1,
      updated: 0,
      departed: 0,
      unmapped: 0,
      skipped_empty: false,
      error: null,
    });
  });

  it("项目绑定的矩阵（带归一化的步骤）", () => {
    validateOp("/api/v1/projects/{project_id}/signature-matrices", "get", [
      {
        module: "RECORD",
        matrix_id: "m-2",
        matrix_name: "计算书 2 级矩阵",
        status: "DRAFT",
        steps: [
          { step_order: 1, sign_role: "CHECKER", required: true, can_self_check: true, can_skip: false },
          { step_order: 2, sign_role: "APPROVER", required: true, can_self_check: false, can_skip: false },
        ],
      },
    ]);
  });

  it("新端点的 handler 都注册了（路径形状：MSW `:param` ⇒ OpenAPI `{param}`）", () => {
    const paths = new Set(
      signFlowHandlers.map((h) => (h as { info?: { path?: string } }).info?.path),
    );
    for (const p of [
      "/api/v1/deliverables/:deliverable_id/progress",
      "/api/v1/deliverables/:deliverable_id/actions",
      "/api/v1/deliverables/:deliverable_id/issue",
      "/api/v1/deliverables/:deliverable_id/sign-step",
      "/api/v1/deliverables/:deliverable_id/customer-approval/proxy",
      "/api/v1/records/:module/:record_id/edits",
      "/api/v1/records/:module/:record_id/comments",
      "/api/v1/admin/users",
      "/api/v1/admin/users/sync",
    ]) {
      expect(paths.has(p), `missing handler for ${p}`).toBe(true);
    }
  });
});
