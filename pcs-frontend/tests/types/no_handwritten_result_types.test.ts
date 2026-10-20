/**
 * 防漂移：`src/types/` 的手写类型 vs 生成的契约（P9B-1 Task F0）。
 *
 * ## 背景（2026-10-20 实测）
 *
 * ① 6 个可编辑结果模块里手写了 **18 个** interface（`CostEstUpdateRequest` 等），
 *    **全部零消费方**，且已漂移：
 *    - `*UpdateRequest` **缺 `expected_hash` / `expected_updated_at`**
 *      （P9A-4 D2 之后后端**必填** ⇒ 按手写类型发请求必然 409）
 *    - `CostEstResultResponse` 注释写「不含 record_hash」，契约里**有**
 *      `record_hash`（D0 补）与 `project_id`（Task B 补）
 *    ⇒ **已删**（本批），本文件钉住它们不会回来。
 *
 * ② 但全仓还有 **57 个**手写 interface 与生成 schema **同名**（清单见
 *    `TODOS.md` TODO-064）。它们大多**有消费方**（`src/api/heat.ts` 等），
 *    改它们要连带核对页面与 mocks ⇒ **不在本 lane 范围**。
 *
 * ⚠️ `npm run api:audit-types` 抓不到这两类：它维护的是一份**手写清单**
 * （10 个类型），结果模块**不在清单里** ⇒ 「清单外的漂移」没有任何自动化会红。
 *
 * ## 三条断言，各管一件事
 *
 * 1. **定点**：本批删掉的 18 个名字**不许回来**。
 * 2. **棘轮**：同名手写类型的数量**只许减不许增**（现在是 57）——
 *    新写一个同名 interface 会红；修掉一个旧债会让计数下降（可接受）。
 * 3. **零消费方 + 同名 ⇒ 直接判死**：这类类型在骗人（看起来是该契约，
 *    实际少几个字段，且没有任何东西会红）⇒ 除非登记例外。
 */
import { describe, it, expect } from 'vitest';
import { readdirSync, readFileSync, statSync } from 'node:fs';
import { join, relative } from 'node:path';

const ROOT = process.cwd();
const TYPES_DIR = join(ROOT, 'src', 'types');
const SRC_DIR = join(ROOT, 'src');

/** 本批删掉的 18 个（6 模块 × UpdateRequest / ResultResponse / ListResponse）。 */
const REMOVED_IN_F0 = [
  'CoolTowerResultUpdateRequest',
  'CoolingTowerResultUpdateRequest',
  'CoolingTowerResultResponse',
  'CoolingTowerResultListResponse',
  'CostEstUpdateRequest',
  'CostEstResultResponse',
  'CostEstListResponse',
  'FiltrationUpdateRequest',
  'FiltrationResultResponse',
  'FiltrationListResponse',
  'FlareResultUpdateRequest',
  'FlareResultResponse',
  'FlareResultListResponse',
  'OpenChannelUpdateRequest',
  'OpenChannelResultResponse',
  'OpenChannelListResponse',
  'PsychroResultUpdateRequest',
  'PsychroResultResponse',
];

/** 已知例外：**有消费方**的手写同名类型（TODO-064 逐个迁）。 */
const ALLOWED_EXCEPTIONS: Record<string, string> = {
  HeatResultResponse: 'TODO-064：heat 模块仍用手写同名类型（src/api/heat.ts + mocks 在 import）',
};

/** 2026-10-20 实测的同名手写类型数量（棘轮基线）。 */
const SAME_NAME_BASELINE = 57;

function walk(dir: string, filter: (f: string) => boolean): string[] {
  const out: string[] = [];
  for (const entry of readdirSync(dir)) {
    const full = join(dir, entry);
    if (statSync(full).isDirectory()) out.push(...walk(full, filter));
    else if (filter(full)) out.push(full);
  }
  return out;
}

const typeFiles = walk(TYPES_DIR, (f) => f.endsWith('.ts') && !f.endsWith('api.d.ts'));
const srcFiles = walk(SRC_DIR, (f) => /\.(ts|tsx)$/.test(f));

function generatedSchemaNames(): Set<string> {
  const snapshot = JSON.parse(readFileSync(join(ROOT, 'openapi.snapshot.json'), 'utf8'));
  return new Set(Object.keys(snapshot.components?.schemas ?? {}));
}

/** 手写 interface 名 → 定义文件 */
function handwrittenInterfaces(): Map<string, string> {
  const out = new Map<string, string>();
  for (const file of typeFiles) {
    const src = readFileSync(file, 'utf8');
    for (const m of src.matchAll(/export\s+interface\s+([A-Za-z0-9_]+)/g)) {
      out.set(m[1], file);
    }
  }
  return out;
}

/** 该名字在 `src/` 下（**定义文件之外**）还有几处引用 ⇒ 是否被消费。 */
function consumerCount(name: string, defFile: string): number {
  const re = new RegExp(`\\b${name}\\b`, 'g');
  let n = 0;
  for (const file of srcFiles) {
    if (file === defFile) continue;
    n += (readFileSync(file, 'utf8').match(re) ?? []).length;
  }
  return n;
}

describe('src/types 手写类型 vs 生成契约（P9B-1 F0）', () => {
  const generated = generatedSchemaNames();
  const handwritten = handwrittenInterfaces();

  it('守卫本身没空转（路径与数据源都要真的读到东西）', () => {
    expect(typeFiles.length).toBeGreaterThan(5);
    expect(generated.size).toBeGreaterThan(100);
    expect(generated.has('CostEstUpdateRequest')).toBe(true);
  });

  it('① 本批删掉的 18 个手写类型不许回来', () => {
    const back = REMOVED_IN_F0.filter((n) => handwritten.has(n));
    expect(back).toEqual([]);
  });

  it('② 同名手写类型的数量只许减不许增（棘轮）', () => {
    const sameName = [...handwritten.keys()].filter(
      (n) => generated.has(n) && !ALLOWED_EXCEPTIONS[n],
    );
    expect(sameName.length).toBeLessThanOrEqual(SAME_NAME_BASELINE);
  });

  it('③ 零消费方且同名 ⇒ 判死（除非登记例外）', () => {
    const dead: string[] = [];
    for (const [name, file] of handwritten) {
      if (!generated.has(name)) continue;
      if (ALLOWED_EXCEPTIONS[name]) continue;
      if (consumerCount(name, file) === 0) {
        dead.push(`${relative(ROOT, file)}: ${name}`);
      }
    }
    expect(dead).toEqual([]);
  });

  it('登记的例外都仍然存在（别让例外表变成一潭死水）', () => {
    for (const name of Object.keys(ALLOWED_EXCEPTIONS)) {
      expect(handwritten.has(name), `${name} 已不存在 ⇒ 请删掉它的例外登记`).toBe(true);
    }
  });

  it('⚠️ 6 个 UpdateRequest 都带并发基线（SPEC §6.21 P9A-LCK-006）', () => {
    const names = [
      'CoolTowerResultUpdateRequest',
      'CostEstUpdateRequest',
      'FiltrationUpdateRequest',
      'FlareResultUpdateRequest',
      'OpenChannelUpdateRequest',
      'PsychroResultUpdateRequest',
    ];
    for (const n of names) expect(generated.has(n)).toBe(true);
    const api = readFileSync(join(TYPES_DIR, 'api.d.ts'), 'utf8');
    expect((api.match(/expected_hash\??:/g) ?? []).length).toBeGreaterThanOrEqual(6);
  });
});
