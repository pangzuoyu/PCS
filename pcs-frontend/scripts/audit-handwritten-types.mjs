#!/usr/bin/env node
/**
 * 手写类型 vs 生成契约的漂移审计（2026-10-19，TODO-039 审计）
 *
 * ## 为什么要有这个脚本
 *
 * bug-180 是这样活下来的：`types/pipeClass.ts` 手写了一份
 * `pipe_class_id`/`code`/`material`…，而契约 `PipeClassResponse` 是
 * `class_id`/`class_name`/`material_standard`… —— **字段名整组不同**。
 * `PipeClassListPage` 真连 `/api/v1/pipe-classes`，所以生产上整页空白；
 * 而 `mocks/seed/pipe-classes.ts` 返的是手写形状，**替它遮着**，
 * 6 条组件测试全绿（fixture 与被测对象共用同一份错误类型，互不设防）。
 *
 * 本脚本把那次手工排查变成可复跑的：**列出每个「被当接口响应用」的手写类型，
 * 它的字段名有多少在契约里根本不存在。**
 *
 * ## 它查什么、不查什么
 *
 * 查：**类型声明的字段名** vs **契约该端点响应的 properties**。
 *
 * 不查：字段**类型**是否兼容、嵌套结构、必填性。
 * —— 那些留给「类型改成契约类型后 `tsc` 说了算」，本脚本只负责
 * 找出**还需要人来决定**的那些（哪些是纯改名、哪些是端点根本不返）。
 *
 * ## 「契约里没有这个端点」也是结果
 *
 * `GET /api/v1/config/assets` 在契约里**不存在**（该路径只有 `post`），
 * 而 `AssetListPage` 用 `useFetch<ConfigAsset[]>('/api/v1/config/assets')`
 * 去取 —— 生产上 404。这类问题比字段漂移更硬，必须报出来。
 *
 * 用法：`node scripts/audit-handwritten-types.mjs`（人读；退出码恒 0）
 *      `node scripts/audit-handwritten-types.mjs --json`（机读）
 */
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const api = JSON.parse(readFileSync(resolve(ROOT, 'openapi.snapshot.json'), 'utf8'));

/** 解 $ref（可多层，可指向 components/responses 与 components/schemas）。 */
function deref(node, depth = 0) {
  if (!node || depth > 6) return null;
  if (node.$ref) {
    let cur = api;
    for (const k of node.$ref.replace(/^#\//, '').split('/')) cur = cur?.[k];
    return deref(cur, depth + 1);
  }
  return node;
}

/** 端点 2xx 响应的 schema：解引用后取 properties 与 required。 */
function jsonSchema(path, method) {
  const op = api.paths?.[path]?.[method];
  if (!op) return null;
  for (const [code, r] of Object.entries(op.responses ?? {})) {
    if (!/^2\d\d$/.test(code)) continue;
    const sch = deref(r)?.content?.['application/json']?.schema;
    if (!sch) continue;
    const inner = deref(sch.type === 'array' ? sch.items : sch) ?? {};
    return {
      kind: sch.type === 'array' ? 'array' : 'object',
      name: sch.$ref ? sch.$ref.split('/').pop()
        : sch.items?.$ref ? sch.items.$ref.split('/').pop() : '(inline)',
      props: Object.keys(inner.properties ?? {}),
      required: inner.required ?? [],
    };
  }
  return null;
}

/** 从手写 .ts 的 interface 里抽字段名（含可选的 `foo?:`）。 */
function tsFields(file, iface) {
  const src = readFileSync(resolve(ROOT, file), 'utf8');
  const m = src.match(new RegExp(`export interface ${iface} \\{([\\s\\S]*?)\\n\\}`, 'm'));
  if (!m) return null;
  return [...m[1].matchAll(/^\s{2}([a-z_][a-z0-9_]*)\??\s*:/gm)].map((x) => x[1]);
}

/** 页面源码里真正引用到的字段（用于区分「活的缺陷」与「类型里的陈旧字段」）。 */
function pageUses(page, fields) {
  let src;
  try { src = readFileSync(resolve(ROOT, page), 'utf8'); } catch { return null; }
  return fields.filter((f) => new RegExp(`\\b${f}\\b`).test(src));
}

/**
 * 审计清单：手写类型 → 契约端点。
 * `note` 记的是**不能靠改名解决**的部分（端点根本不返该字段）。
 */
const AUDIT = [
  { type: 'ConfigAsset',     ts: 'src/types/configAsset.ts', iface: 'ConfigAsset',
    path: '/api/v1/config/assets', method: 'get',
    page: 'src/pages/config/AssetListPage.tsx',
    note: '该路径在契约里只有 post，没有 get —— 生产上 404' },
  { type: 'Stream',          ts: 'src/types/stream.ts',      iface: 'Stream',
    path: '/api/v1/projects/{project_id}/streams', method: 'get',
    page: 'src/pages/sim/StreamListPage.tsx' },
  { type: 'StreamDetailPayload', ts: 'src/types/stream.ts',  iface: 'StreamDetailPayload',
    path: '/api/v1/streams/{stream_id}', method: 'get',
    page: 'src/pages/sim/StreamListPage.tsx',
    note: '手写侧是「物流 + 矩阵 + 签署 + 审批 + 冲突 + 血缘 + UiSchema」的合成体，契约侧是单个 StreamResponse' },
  { type: 'ComponentProperty', ts: 'src/types/common.ts',   iface: 'ComponentProperty',
    path: '/api/v1/common/materials/search', method: 'get',
    page: 'src/pages/common/PropertySearchPage.tsx',
    note: '手写侧把「搜索结果」与「物性详情」两个契约 schema 合并了；tc_k/pc_mpa/omega 在 search 端点根本不返（属 MaterialDetail）' },
  { type: 'AllowableStress', ts: 'src/types/common.ts',      iface: 'AllowableStress',
    path: '/api/v1/common/allowable-stress', method: 'get',
    page: 'src/pages/common/AllowableStressPage.tsx' },
  { type: 'ToxicityClass',   ts: 'src/types/common.ts',      iface: 'ToxicityClass',
    path: '/api/v1/common/safety', method: 'get',
    page: 'src/pages/common/ToxicityExplosivityPage.tsx',
    note: 'ld50_mg_kg / pel_ppm / explosive_limit_json / hazard_class 不在 SafetyResult 里' },
  { type: 'ChecklistItem',   ts: 'src/types/checklist.ts',   iface: 'ChecklistItem',
    path: '/api/v1/checklist/projects/{project_id}', method: 'get',
    page: null },
  { type: 'Workspace',       ts: 'src/types/workspace.ts',   iface: 'Workspace',
    path: '/api/v1/workspaces', method: 'get',
    page: null },
];

const results = AUDIT.map((a) => {
  const mine = tsFields(a.ts, a.iface);
  const base = { type: a.type, path: a.path, method: a.method.toUpperCase(), note: a.note };
  if (!mine) return { ...base, status: 'NO_TS_TYPE' };
  const available = api.paths?.[a.path]?.[a.method];
  if (!api.paths?.[a.path]) return { ...base, status: 'NO_SUCH_PATH', fields: mine.length };
  if (!available) {
    return { ...base, status: 'NO_SUCH_METHOD',
             methods: Object.keys(api.paths[a.path]).filter((k) => k !== 'parameters'),
             fields: mine.length };
  }
  const s = jsonSchema(a.path, a.method);
  if (!s) return { ...base, status: 'NO_JSON_SCHEMA', fields: mine.length };
  const unknown = mine.filter((f) => !s.props.includes(f));
  const used = a.page ? pageUses(a.page, unknown) : null;
  return { ...base, status: unknown.length ? 'DRIFT' : 'OK', contract: s.name,
           contractFields: s.props.length, fields: mine.length,
           unknown, unknownNotRequired: unknown.filter((f) => !s.required.includes(f)),
           readByPage: used, liveCount: used ? used.length : null };
});

if (process.argv.includes('--json')) {
  console.log(JSON.stringify(results, null, 2));
  process.exit(0);
}

let live = 0;
for (const r of results) {
  const flag = r.status === 'OK' ? '✅' : r.status === 'DRIFT'
    ? (r.liveCount ? '🔴' : '⚠ ') : '❌';
  console.log(`\n${flag} ${r.type}  →  ${r.method} ${r.path}`);
  switch (r.status) {
    case 'OK':
      console.log(`   字段名与 ${r.contract} 完全一致（${r.fields} 个）`);
      break;
    case 'NO_SUCH_PATH':
      console.log('   ❌ 契约里没有这个路径 —— 页面会 404');
      break;
    case 'NO_SUCH_METHOD':
      console.log(`   ❌ 契约里该路径没有 ${r.method}（只有 ${r.methods.join(',')}）—— 页面会 404`);
      break;
    case 'NO_JSON_SCHEMA':
      console.log('   ⚠  该端点没有 JSON 响应');
      break;
    case 'NO_TS_TYPE':
      console.log('   ⚠  抽不出同名手写 interface（可能已改名）');
      break;
    default: {
      if (r.liveCount) live += r.liveCount;
      console.log(`   契约 ${r.contract}：${r.contractFields} 字段；手写 ${r.fields} 字段`);
      console.log(`   ❌ 手写有、契约无（${r.unknown.length}）: ${r.unknown.join(', ')}`);
      if (r.readByPage) {
        console.log(`   ${r.liveCount ? '🔴 页面真的在读' : '页面没读（仅类型里陈旧）'}: `
          + r.readByPage.join(', '));
      }
    }
  }
  if (r.note) console.log(`   ℹ  ${r.note}`);
}
console.log(`\n${'='.repeat(60)}`);
console.log(live
  ? `合计 ${live} 处「页面在读、契约里没有」的字段 —— 生产上显示为空`
  : '没有「页面在读、契约里没有」的字段');
