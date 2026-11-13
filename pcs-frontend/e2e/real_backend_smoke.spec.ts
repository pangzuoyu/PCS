import { test, expect } from './fixtures';

/**
 * 真后端通道的**冒烟**（P10-A · Task T3 · 评审 #8 改过）。
 *
 * ⚠️ 这条 spec 只验证**通道本身**（真后端可达 + 登录成功 + 页面渲染），
 * 业务场景在 P10-B（18 个场景）。
 *
 * ⚠️ **标题必须带 `@real-backend`** —— Playwright 的 `grep` 匹配的是
 * **测试标题**（不是文件路径）⇒ 不带 tag ⇒ `--project=real-backend`
 * 收集到 **0 个测试** ⇒ 看起来「全绿」实则什么都没跑。
 */

/**
 * 种子项目 id —— `uuid5(NAMESPACE_DNS, 'pcs-e2e-project')`，
 * 与 `pcs-backend/scripts/seed_e2e_data.py::SEED_PROJECT_ID` **同源**
 * （⚠️ 改那边 ⇒ 改这里）。
 */
const SEED_PROJECT_ID = 'b563e3e8-ebde-52db-8b1b-87fd9b69c8dc';

test('@real-backend 真后端通道：登录 ⇒ 仪表盘渲染 ⇒ 种子数据可见 ⇒ 无控制台错误', async ({
  realPage,
}) => {
  const errors: string[] = [];
  realPage.on('console', (m) => {
    if (m.type() === 'error') errors.push(m.text());
  });
  await realPage.goto('/login');
  // ⚠️ **抓登录响应** —— token 只在 zustand 内存里（不落 localStorage）
  // ⇒ 只能从响应里取（前端读的是 `access_token`）。
  const [loginResponse] = await Promise.all([
    realPage.waitForResponse(
      (res) => res.url().includes('mock-login') && res.status() === 200,
      { timeout: 15000 },
    ),
    realPage.getByRole('button', { name: '登 录' }).click(),
  ]);
  const { access_token: accessToken } = await loginResponse.json();
  await realPage.waitForURL('/', { timeout: 15000 });
  // ⚠️ 用 **heading** 定位而不是 getByText('仪表盘') —— 侧边菜单里也有一个
  // 「仪表盘」⇒ getByText 命中 2 个 ⇒ strict mode violation。
  await expect(realPage.getByRole('heading', { name: '仪表盘' })).toBeVisible();

  // ⚠️⚠️ **数据级断言**（评审 #8）—— 旧版只断言「登录 + 仪表盘标题 +
  // 控制台无 error」⇒ **后端连的不是被 seed 的那个库**时照样绿：
  // mock 登录**不落 users 表**、`/auth/me` 允许缺行、axios 只对 401 报错
  // ⇒ 后端对所有项目级端点回 404 也**不会**产生控制台 error。
  //
  // ⇒ 这里直接读**种子项目**：它要 200 就必须同时满足
  //   ① 后端连的是**被 seed 的那个库**（pcs_pgtest）
  //   ② 种子造的 `UserProject` 授权行在位（项目守卫的判据）
  // 任一不满足 ⇒ **404** ⇒ 通道**红**（而不是假绿）。
  const projectResponse = await realPage.request.get(
    `/api/v1/projects/${SEED_PROJECT_ID}`,
    { headers: { Authorization: `Bearer ${accessToken}` } },
  );
  expect(
    projectResponse.status(),
    '种子项目不可见 ⇒ 后端没连被 seed 的那个库（或授权行缺失）⇒ 真后端通道是假绿',
  ).toBe(200);
  const project = await projectResponse.json();
  expect(project.project_name).toBe('E2E Seed Project');

  expect(errors).toEqual([]);
});
