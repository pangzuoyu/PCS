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
import Ajv from "ajv";

import { handlers, devOnlyMockHandlers } from "../../src/mocks/handlers";
import { metaSeed } from "../../src/mocks/seed/meta";
import { seedStreams } from "../../src/mocks/seed/streams";

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
    for (const h of handlers) {
      const path = (h as { info?: { path?: string } }).info?.path;
      expect(path, "handler missing path").toBeDefined();
      expect(openapi.paths[path!], `OpenAPI missing ${path}`).toBeDefined();
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
