/**
 * **前端 mock 的 BEDD uiSchema ↔ 后端字段表**的漂移守卫（P10-H · T2 · TODO-195）。
 *
 * ## 为什么需要它
 *
 * BEDD 的字段表在**后端**（`app/schemas/bedd.py::BEDD_FIELDS`）⇒ ⇒ 前端 mock
 * 通道要**照抄**一份 ⇒ ⇒ 两份必然漂 ⇒ ⇒ 而漂移的后果是
 * 「mock 通道渲染的表单比真后端少几个字段」⇒ ⇒ **替身比被测物更宽容**
 * ⇒ ⇒ 前端漏字段在 mock 通道里**看不出来**（本仓的老毛病）。
 *
 * ⇒ ⇒ 本文件**读后端源文件**（`pcs-backend/app/schemas/bedd.py`）⇒ ⇒
 * 逐条比对字段路径（`分组.字段`）⇒ ⇒ 漂移即红。
 *
 * ⚠️ **为什么读源文件而不是 OpenAPI**：uiSchema 的**字段清单**不在契约里
 * （契约只规定 `UiSchemaResponse` 的**形状**）⇒ ⇒ 内容漂移只有比对源文件
 * 才抓得到。
 */
import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

import { seedBeddUiSchema } from '../../src/mocks/seed/pms';

const BACKEND_SCHEMA = resolve(
  __dirname,
  '../../../pcs-backend/app/schemas/bedd.py',
);

/** 从后端源文件里抠出 `BEDD_FIELDS` 的 (分组, 字段) 对。 */
function backendFieldPaths(): string[] {
  const src = readFileSync(BACKEND_SCHEMA, 'utf8');
  const block = src.slice(
    src.indexOf('BEDD_FIELDS: dict'),
    src.indexOf('#: 分组 key → 中文 Tab 名'),
  );
  // ⇒ ⇒ **按分组切块**（否则字段正则会扫到别的分组去）
  const groupStarts: Array<{ group: string; start: number }> = [];
  const groupRe = /^\s{4}"([a-z_]+)": \($/gm;
  let groupMatch: RegExpExecArray | null;
  while ((groupMatch = groupRe.exec(block)) !== null) {
    groupStarts.push({ group: groupMatch[1], start: groupMatch.index });
  }
  const paths: string[] = [];
  groupStarts.forEach(({ group, start }, i) => {
    const end = i + 1 < groupStarts.length ? groupStarts[i + 1].start : block.length;
    const groupBlock = block.slice(start, end);
    const fieldRe = /\("([a-z_]+)",\s*"[^"]*",\s*"[A-Za-z]+",\s*"(number|text)"\)/g;
    let fieldMatch: RegExpExecArray | null;
    while ((fieldMatch = fieldRe.exec(groupBlock)) !== null) {
      paths.push(`${group}.${fieldMatch[1]}`);
    }
  });
  return paths.sort();
}

describe('BEDD uiSchema · 前端 mock ↔ 后端字段表', () => {
  it('后端源文件可解析（**别让守卫自己悄悄失效**）', () => {
    expect(backendFieldPaths().length).toBeGreaterThan(30);
  });

  it('⚠️ **字段路径逐条一致**（漂移即红）', () => {
    const backend = backendFieldPaths();
    const mock = seedBeddUiSchema.fields.map((f) => f.path).sort();
    expect(mock).toEqual(backend);
  });

  it('⚠️ **分组集合一致**（后端 9 个分组）', () => {
    const backendGroups = new Set(backendFieldPaths().map((p) => p.split('.')[0]));
    const mockGroups = new Set(seedBeddUiSchema.fields.map((f) => f.path.split('.')[0]));
    expect([...mockGroups].sort()).toEqual([...backendGroups].sort());
    expect(mockGroups.size).toBe(9);
  });
});
