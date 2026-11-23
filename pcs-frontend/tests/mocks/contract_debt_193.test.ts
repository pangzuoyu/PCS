/**
 * **14 条 mock ↔ 契约欠账已还**（TODO-193 · P10-H · T3）。
 *
 * ## 这批欠账是怎么来的
 *
 * P10-C · T2 发现：漂移棘轮「devOnly ∩ 契约」**直接拿 MSW 的 `:param` 路径**去比
 * 契约的 `{param}` 路径 ⇒ ⇒ **永远不相等** ⇒ ⇒ 凡是用 `:param` 写的 mock 端点，
 * 棘轮**根本看不见它** ⇒ ⇒ 「有契约可漂移却没校验」的洞一直敞着
 * （管道一览表那个端点就靠这个躲了三年）。
 *
 * 路径**归一化**后 ⇒ ⇒ 洞被看见 ⇒ ⇒ 多出 **14 条**欠账 ⇒ ⇒ **本文件还债**。
 *
 * ## 本文件钉的规则
 *
 * 每条端点一条断言：**mock 的响应体** ⇒ ⇒ **过契约 schema 的 ajv 校验**
 * ⇒ ⇒ 漂移（字段改名 / 少字段 / 形状变了）⇒ ⇒ **红**。
 *
 * ⚠️ **「替身比被测物更宽容」是老毛病**（本仓第三次撞上）⇒ ⇒ mock 必须和
 * 契约一样严 ⇒ ⇒ 所以这些断言不是形式主义：**它们曾经真的抓到过漂移**
 * （见各条注释）。
 */
import { describe, it, expect } from 'vitest';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import Ajv, { type AnySchema } from 'ajv';

import {
  buildLineageGraph,
  buildReviewLog,
  mockPsvStandardProfile,
} from '../../src/mocks/handlers';
import { mockHeatDetail, mockHeatWeightResult } from '../../src/mocks/heat';
import { seedChecklist } from '../../src/mocks/seed/workspaces';
import { seedStreams } from '../../src/mocks/seed/streams';

const openapiPath = resolve(__dirname, '../../openapi.snapshot.json');
const openapi = JSON.parse(readFileSync(openapiPath, 'utf8'));

const ajv = new Ajv({ strict: false, allErrors: true });

function resolveRef(root: unknown, ref: string): unknown {
  return ref
    .replace('#/', '')
    .split('/')
    .reduce((acc: any, p) => (acc == null ? acc : acc[p]), root as any);
}

function inlineRefs(node: any, root: any, seen = new Set<string>()): any {
  if (Array.isArray(node)) return node.map((n) => inlineRefs(n, root, seen));
  if (!node || typeof node !== 'object') return node;
  if (node.$ref && typeof node.$ref === 'string') {
    if (seen.has(node.$ref)) return {};
    const next = new Set(seen);
    next.add(node.$ref);
    return inlineRefs(resolveRef(root, node.$ref), root, next);
  }
  const out: any = {};
  for (const [k, v] of Object.entries(node)) out[k] = inlineRefs(v, root, seen);
  return out;
}

/** 取某端点某状态码的 JSON schema（已解 $ref）。 */
function schemaFor(
  path: string,
  method: 'get' | 'post',
  statusCode = '200',
): unknown {
  const op = (openapi.paths as any)[path]?.[method];
  if (!op) throw new Error(`契约里没有 ${method.toUpperCase()} ${path}`);
  const schemaJson = op.responses?.[statusCode]?.content?.['application/json']?.schema;
  if (!schemaJson) throw new Error(`${method.toUpperCase()} ${path} 的 ${statusCode} 没有 schema`);
  return schemaJson.$ref
    ? inlineRefs(resolveRef(openapi, schemaJson.$ref), openapi)
    : inlineRefs(schemaJson, openapi);
}

/** 校验一条 mock 响应体 ⇒ ⇒ 形状不符就抛（错误信息带字段路径）。 */
function expectContract(path: string, method: 'get' | 'post', data: unknown): void {
  const validate = ajv.compile(schemaFor(path, method) as AnySchema);
  const ok = validate(data);
  expect(ok, `${method.toUpperCase()} ${path} 形状不符: ${JSON.stringify(validate.errors)}`).toBe(true);
}

// ---------------------------------------------------------------------------
// ① checklist（2 条）
// ---------------------------------------------------------------------------

describe('mock ↔ 契约 · checklist', () => {
  it('GET /api/v1/checklist/projects/{project_id} ⇒ ChecklistItemOut[]', () => {
    expectContract('/api/v1/checklist/projects/{project_id}', 'get', seedChecklist);
  });

  it('GET /api/v1/checklist/projects/{project_id}/completeness ⇒ ChecklistCompleteness', () => {
    // ⚠️ 照抄 mock handler 的算法（`checklist_service.py::completeness` 口径）
    const items = seedChecklist;
    const required = items.filter(
      (i) => i.input_category === 'REQUIRED' || (i.required && !i.input_category),
    );
    const body = {
      project_id: '00000000-0000-0000-0000-000000000001',
      total: items.length,
      required_total: required.length,
      required_verified: required.filter((i) => i.status === 'VERIFIED').length,
      required_assumed: required.filter((i) => i.status === 'ASSUMED').length,
      required_blocked: required.filter(
        (i) => i.status === 'NOT_STARTED' || i.status === 'IN_PROGRESS',
      ).length,
      completeness_pct: 100,
    };
    expectContract(
      '/api/v1/checklist/projects/{project_id}/completeness',
      'get',
      body,
    );
  });
});

// ---------------------------------------------------------------------------
// ② heat（2 条）
// ---------------------------------------------------------------------------

describe('mock ↔ 契约 · heat', () => {
  it('GET /api/v1/heat/{heat_id} ⇒ HeatResultResponse', () => {
    expectContract('/api/v1/heat/{heat_id}', 'get', mockHeatDetail);
  });

  it('POST /api/v1/heat/{heat_id}/weight-estimate ⇒ WeightEstimateResponse', () => {
    expectContract('/api/v1/heat/{heat_id}/weight-estimate', 'post', mockHeatWeightResult);
  });
});

// ---------------------------------------------------------------------------
// ③ lineage（1 条）
// ---------------------------------------------------------------------------

describe('mock ↔ 契约 · lineage', () => {
  it('GET /api/v1/lineage/{record_type}/{record_id}/graph ⇒ LineageGraphResponse', () => {
    expectContract(
      '/api/v1/lineage/{record_type}/{record_id}/graph',
      'get',
      buildLineageGraph('streams', 's-1'),
    );
  });
});

// ---------------------------------------------------------------------------
// ④ psv standard-profile（1 条）
// ---------------------------------------------------------------------------

describe('mock ↔ 契约 · psv', () => {
  it('GET /api/v1/projects/{project_id}/psv/standard-profile ⇒ StandardProfileResponse', () => {
    expectContract(
      '/api/v1/projects/{project_id}/psv/standard-profile',
      'get',
      mockPsvStandardProfile,
    );
  });
});

// ---------------------------------------------------------------------------
// ⑤ streams：项目列表 / 校验（2 条）
// ---------------------------------------------------------------------------

describe('mock ↔ 契约 · streams（项目面）', () => {
  it('GET /api/v1/projects/{project_id}/streams ⇒ StreamResponse[]', () => {
    expectContract('/api/v1/projects/{project_id}/streams', 'get', seedStreams);
  });

  it('POST /api/v1/projects/{project_id}/streams/validate ⇒ ValidateStreamResponse', () => {
    expectContract('/api/v1/projects/{project_id}/streams/validate', 'post', {
      valid: true,
      blocks: [],
      warnings: [],
      infos: [],
      stats: { BLOCK: 0, WARN: 0, INFO: 0, TOTAL: 0 },
    });
  });
});

// ---------------------------------------------------------------------------
// ⑥ streams：详情与三个 Tab + 送审（6 条）
// ---------------------------------------------------------------------------

describe('mock ↔ 契约 · streams（记录面）', () => {
  it('GET /api/v1/streams/{stream_id} ⇒ StreamResponse（**单个**，不是包一层）', () => {
    // ⚠️ bug-189 的形状：mock 曾返 `{stream, matrix, signatures}` ⇒ ⇒
    // 真后端下路由读不到东西 ⇒ ⇒ 现在是**扁平的 StreamResponse**。
    expectContract('/api/v1/streams/{stream_id}', 'get', seedStreams[0]);
  });

  it('GET /api/v1/streams/{stream_id}/properties ⇒ 契约的裸 object', () => {
    expectContract('/api/v1/streams/{stream_id}/properties', 'get', {
      stream_id: 's-1',
      user_provided: { molecular_weight: 28.01 },
      calculated: { molecular_weight: 28.0 },
      effective: { molecular_weight: 28.01 },
      conflict_resolutions: {},
    });
  });

  it('POST /api/v1/streams/{stream_id}/properties/estimate ⇒ **具名** StreamPropertiesEstimateResponse', () => {
    expectContract('/api/v1/streams/{stream_id}/properties/estimate', 'post', {
      results: [{ cas: '7732-18-5', mw: 28.01, estimated: false }],
    });
  });

  it('GET /api/v1/streams/{stream_id}/review-log ⇒ ReviewLogItem[]', () => {
    expectContract('/api/v1/streams/{stream_id}/review-log', 'get', buildReviewLog('s-1'));
  });

  it('GET /api/v1/streams/{stream_id}/state-points ⇒ **具名** StreamStatePointResponse[]', () => {
    // ⚠️ **P10-H · TODO-199 后**：契约不再是裸 object ⇒ ⇒ 这条从「证明是个
    //    object」升级成「**逐字段**对得上」（少一个必填字段 ⇒ ⇒ 红）。
    expectContract('/api/v1/streams/{stream_id}/state-points', 'get', [
      {
        state_point_id: 'sp-mock-1',
        stream_id: 's-1',
        state_label: '设计工况',
        case_type: 'NORMAL',
        temp: 25,
        press: 0.5,
        phase: 'LIQUID',
        vapor_fraction: null,
        mass_flow: 10000,
        composition_json: {},
        vapor_composition_json: null,
        liquid_composition_json: null,
        density: null,
        viscosity_dynamic: null,
        enthalpy: null,
        entropy: null,
        record_hash: '0000000000000000',
        estimated_flags_json: null,
        profile_json: null,
        source_type: 'MANUAL_ENTRY',
        created_at: '2026-09-10T10:00:00Z',
      },
    ]);
  });

  it('POST /api/v1/streams/{stream_id}/submit ⇒ 契约的裸 object', () => {
    expectContract('/api/v1/streams/{stream_id}/submit', 'post', {
      stream_id: 's-new-mock',
      sign_status: 'IN_APPROVAL',
    });
  });
});
