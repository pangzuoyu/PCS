import { test, expect } from './fixtures';

/**
 * 真后端通道的**冒烟**（P10-A · Task T3）。
 *
 * ⚠️ 这条 spec 只验证**通道本身**（真后端可达 + 登录成功 + 页面渲染），
 * 业务场景在 P10-B（18 个场景）。
 *
 * ⚠️ **标题必须带 `@real-backend`** —— Playwright 的 `grep` 匹配的是
 * **测试标题**（不是文件路径）⇒ 不带 tag ⇒ `--project=real-backend`
 * 收集到 **0 个测试** ⇒ 看起来「全绿」实则什么都没跑。
 */
test('@real-backend 真后端通道：登录 ⇒ 仪表盘渲染 ⇒ 无控制台错误', async ({ realPage }) => {
  const errors: string[] = [];
  realPage.on('console', (m) => {
    if (m.type() === 'error') errors.push(m.text());
  });
  await realPage.goto('/login');
  await realPage.getByRole('button', { name: '登 录' }).click();
  await realPage.waitForURL('/', { timeout: 15000 });
  // ⚠️ 用 **heading** 定位而不是 getByText('仪表盘') —— 侧边菜单里也有一个
  // 「仪表盘」⇒ getByText 命中 2 个 ⇒ strict mode violation。
  await expect(realPage.getByRole('heading', { name: '仪表盘' })).toBeVisible();
  expect(errors).toEqual([]);
});
