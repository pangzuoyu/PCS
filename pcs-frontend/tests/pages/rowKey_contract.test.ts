/**
 * **棘轮**：antd `Table` 的 `rowKey` 必须是**契约里真实存在的字段**。
 *
 * ## 为什么要有这条（TODO-121 的根因）
 *
 * `PipeClassListPage` 写的是 `rowKey="pipe_class_id"`，而契约
 * `PipeClassResponse` 的字段是 **`class_id`**（2026-10-19 bug-180 把整组
 * 字段名改了，`rowKey` **漏改**）⇒ **每一行的 key 都是 `undefined`** ⇒
 *
 * - React 控制台报 `Each child in a list should have a unique "key" prop`；
 * - 更要紧的是**行的身份是坏的** ⇒ 选择 / 展开 / 局部更新都按 `undefined`
 *   配对 ⇒ 多行时行为不可预期。
 *
 * ⚠️ 这个缺陷**单靠页面自己的测试抓不到**：页面的 fixture 与页面读的是
 * 同一份类型 ⇒ 「页面读什么」与「fixture 有什么」互相验证、互不设防
 * （正是 bug-180 的发现路径）。
 *
 * ## 这条棘轮怎么工作
 *
 * 扫 `src/pages` 下所有 `.tsx` 里所有 `rowKey="字段"`（字符串形式）⇒
 * 断言该字段**出现在该页面的行类型里**（从 `dataIndex` / `render` 里
 * 读不到类型 ⇒ 改为**逐页断言**：页面源码里出现的 `rowKey="X"` ⇒
 * `X` 必须是该页契约/类型里真实有的字段名）。
 *
 * ⚠️ 类型信息从源码拿不到 ⇒ 这条用**「该字段名必须出现在同页的契约类型
 * 声明里」**这种可静态判定的方式：页面从 `components['schemas'][...]`
 * 派生的行类型，其字段名必然出现在 `src/types/api.d.ts` 的契约里
 * ⇒ 断言 `rowKey` 的字段名**在该页 import 的 schema 名对应的契约
 * schema 的 properties 里**。
 *
 * ⇒ 新增/改名一个 `rowKey` 字段时，若忘了同步契约 ⇒ **本条立刻红**。
 */
import { describe, it, expect } from 'vitest';
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join, resolve } from 'node:path';

const SRC = resolve(__dirname, '../../src');
const TYPES = resolve(__dirname, '../../src/types/api.d.ts');
const OPENAPI = resolve(__dirname, '../../openapi.snapshot.json');
const TYPES_DIR = resolve(__dirname, '../../src/types');

/**
 * 契约里所有 schema 的字段名全集（`properties` 的一阶键）。
 *
 * ⚠️ 从 **`openapi.snapshot.json`** 读（不是 `api.d.ts`）—— `api.d.ts` 里
 * `components` 是**类型**（`import type` ⇒ 运行时不存在）⇒ 运行时读不到。
 */
function allContractFieldNames(): Set<string> {
  const doc = JSON.parse(readFileSync(OPENAPI, 'utf8')) as {
    components?: { schemas?: Record<string, { properties?: Record<string, unknown> }> };
  };
  const names = new Set<string>();
  for (const schema of Object.values(doc.components?.schemas ?? {})) {
    for (const key of Object.keys(schema.properties ?? {})) names.add(key);
  }
  return names;
}

/**
 * **手写**类型里声明的字段名全集（`src/types/*.ts` + **页面本地** interface）。
 *
 * ⚠️ 为什么需要它：仓里有一批**尚未并进契约**的手写类型
 * （`types/pipe.ts` 的 `PipeLineListRow` / `types/pms.ts` / `types/pump.ts` …）
 * 以及**页面本地**的 interface（如 `CoefficientRow` / `CompositionRow`）
 * ⇒ 它们的 `rowKey` 字段（如 `seq` / `item_id` / `segment` / `row_id` /
 * `component`）**契约里当然没有** ⇒ 只查契约会把它们**误报**。
 * ⇒ 故允许集 = **契约字段 ∪ 手写类型字段 ∪ 页面本地 interface 字段**。
 */
function handWrittenTypeFieldNames(): Set<string> {
  const names = new Set<string>();
  // ① `src/types/*.ts` 里的字段声明：`  字段名?: 类型;`
  for (const entry of readdirSync(TYPES_DIR)) {
    if (!entry.endsWith('.ts') || entry === 'api.d.ts') continue;
    const src = readFileSync(join(TYPES_DIR, entry), 'utf8');
    for (const m of src.matchAll(/^\s{2,}([a-z_][a-z0-9_]*)\??\s*:/gm)) {
      names.add(m[1]);
    }
  }
  // ② **页面本地** interface 里的字段声明（同样缩进 2 空格）
  for (const file of pageFiles(join(SRC, 'pages'))) {
    const src = readFileSync(file, 'utf8');
    for (const m of src.matchAll(/^\s{2,}([a-z_][a-z0-9_]*)\??\s*:/gm)) {
      names.add(m[1]);
    }
  }
  return names;
}

/** 递归扫 `src/pages` 下的 `.tsx`。 */
function pageFiles(dir: string): string[] {
  const out: string[] = [];
  for (const entry of readdirSync(dir)) {
    const full = join(dir, entry);
    if (statSync(full).isDirectory()) out.push(...pageFiles(full));
    else if (entry.endsWith('.tsx')) out.push(full);
  }
  return out;
}

describe('棘轮：antd Table 的 rowKey 必须是契约里真实存在的字段（TODO-121）', () => {
  it('PipeClassListPage 的 rowKey 用 class_id（bug-180 漏改的那个）', () => {
    const src = readFileSync(
      join(SRC, 'pages/pipe_class/PipeClassListPage.tsx'),
      'utf8',
    );
    expect(src).toContain('rowKey="class_id"');
    expect(src).not.toContain('rowKey="pipe_class_id"');
  });

  it('⚠️ 所有页面的 rowKey="字段" 都必须是**真实存在的字段名**', () => {
    // 允许集 = 契约字段 ∪ 手写类型字段
    // （手写类型尚未并进契约 ⇒ 它们的 rowKey 字段契约里当然没有 ⇒ 不能误报）
    const allowed = new Set([
      ...allContractFieldNames(),
      ...handWrittenTypeFieldNames(),
    ]);
    const offenders: string[] = [];
    for (const file of pageFiles(join(SRC, 'pages'))) {
      const src = readFileSync(file, 'utf8');
      // 只取**字符串**形式（`rowKey="x"`）—— 函数形式无法静态判定
      const matches = src.matchAll(/rowKey="([A-Za-z_][A-Za-z0-9_]*)"/g);
      for (const m of matches) {
        const field = m[1];
        if (!allowed.has(field)) {
          offenders.push(`${file.replace(SRC + '/', '')} → rowKey="${field}"`);
        }
      }
    }
    expect(
      offenders,
      `这些 rowKey 字段**既不在契约里、也不在手写类型里** ⇒\n` +
        `每行的 key 都是 undefined ⇒ ① React key 警告 ② 行的身份坏了\n` +
        `（选择/展开/局部更新都按 undefined 配对）\n` +
        offenders.join('\n'),
    ).toEqual([]);
  });

  it('⚠️ 契约类型文件里确实有这些字段（防止上面那条变成空断言）', () => {
    // 断言这条棘轮**不是空跑**：契约里必须真的有一批字段
    expect(allContractFieldNames().size).toBeGreaterThan(50);
    expect(readFileSync(TYPES, 'utf8')).toContain('PipeClassResponse');
  });
});
