/**
 * MSW 的 `/report-builder/definitions` 必须**遵守 `status` 查询参数**。
 *
 * ## 为什么这条测试存在
 *
 * 后端评审 #27：`list_definitions` 的签名里没有任何查询参数，而前端
 * `ReportDefinitionListPage` 一直把 `status` 发过去（该文件 docstring 明写
 * 「它作为查询参数发给后端，不在本地裁剪」）。参数被**静默丢弃** ——
 * 200 + 全量，用户选「已发布」列表纹丝不动，**零报错**。
 *
 * 后端修好后出现一个新的漂移方向：mock 若继续无视 `status`，
 * dev 的「执行」页会列出 DRAFT、真后端下不会。
 * 这次 mock 比后端**宽松** —— 与评审 #24 查出的那批方向相反，
 * 但危害一样：所有 dev 验证都建立在错误前提上。
 *
 * 因此 mock 的**行为**也要钉住，不能只钉它的**形状**
 * （#24 那批标注管形状，这里管行为）。
 *
 * ## 观测点：`setupServer` + 真 fetch
 *
 * 不用「直接 import handler 调 `.run()`」——
 * 第一版试过，MSW v2 的 handler 对象没有可用的 `toString()`/`.run()` 入口，
 * 四个用例全部以「definitions handler 未注册」失败 —— **报错而非失败**，
 * 看不出是测试写错还是行为不对。
 * `setupServer` + `fetch` 是 MSW 自己的执行路径，与浏览器里 dev 的
 * 行为一致（`tests/mocks/heat_handlers.test.ts` 同款）。
 */
import { describe, it, expect, beforeAll, afterAll, afterEach } from 'vitest';
import { setupServer } from 'msw/node';

import { reportBuilderHandlers } from '../../src/mocks/reportBuilder';
import { mockAuthToken } from '../../src/mocks/handlers';

const BEARER = `Bearer ${mockAuthToken}`;

const server = setupServer(...reportBuilderHandlers);

beforeAll(() => server.listen({ onUnhandledRequest: 'bypass' }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

type DefinitionRow = { def_id: string; status: string };

async function listDefinitions(status?: string): Promise<DefinitionRow[]> {
  const qs = status ? `?status=${encodeURIComponent(status)}` : '';
  const res = await fetch(`/api/v1/report-builder/definitions${qs}`, {
    headers: { Authorization: BEARER },
  });
  expect(res.status).toBe(200);
  const body = (await res.json()) as { items: DefinitionRow[]; total: number };
  // total 必须跟 items 一致 —— 两者脱节会让前端分页显示错总数
  expect(body.total).toBe(body.items.length);
  return body.items;
}

describe('MSW definitions —— status 查询参数（配套后端 #27）', () => {
  it('不带 status 时返回全部（不过滤）', async () => {
    const items = await listDefinitions();
    expect(items).toHaveLength(2);
    expect(new Set(items.map((d) => d.status))).toEqual(
      new Set(['DRAFT', 'PUBLISHED']),
    );
  });

  it('?status=DRAFT 只回 DRAFT', async () => {
    const items = await listDefinitions('DRAFT');
    expect(items.length).toBeGreaterThan(0);
    expect(items.every((d) => d.status === 'DRAFT')).toBe(true);
  });

  it('?status=PUBLISHED 只回 PUBLISHED —— 「执行」页依赖这条', async () => {
    const items = await listDefinitions('PUBLISHED');
    expect(items.length).toBeGreaterThan(0);
    expect(items.every((d) => d.status === 'PUBLISHED')).toBe(true);
  });

  it('未知状态回空数组（真后端是 400，mock 不重复造错误信封）', async () => {
    const items = await listDefinitions('NOT_A_STATUS');
    expect(items).toHaveLength(0);
  });
});
