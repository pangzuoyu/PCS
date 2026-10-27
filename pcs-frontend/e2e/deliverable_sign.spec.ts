/**
 * 交付物级签署写面（Playwright e2e · P9B-2 · T8 / T10）。
 *
 * ## 这条 e2e 抓的是「**矩阵是装饰品**」
 *
 * 签署推进的每一步都由**签署矩阵**决定（`steps_json.sign_role` / 顺序）。
 * ⇒ 断言两件事：
 *
 * 1. **步骤来自矩阵**（不是前端硬编码的步骤表）—— 弹窗里显示的「第 N 步 ·
 *    角色」必须等于矩阵里那一步的 `sign_role`；
 * 2. **步骤推进**（签完之后请求体里的 `step_index` 落在矩阵的**那一步**上）。
 *
 * ⚠️ **角色要选对**：mock 的项目绑定矩阵（`m-2`）第 1 步是 **CHECKER**
 * ⇒ 用 bob(CHECKER) 登录 ⇒ 前端不把按钮禁用（禁用就点不动了）。
 *
 * ## 依赖
 *
 * vite dev server（`npm run dev`）+ MSW worker。
 */
import { test, expect, type Page } from './fixtures';

async function loginAs(page: Page, username: string): Promise<void> {
  await page.goto('/login');
  // ⚠️ dev 下 app **等 MSW service worker 就绪才渲染**（main.tsx 的 bootstrap）
  // ⇒ 首次注册慢时页面是**空白**的 ⇒ 必须等选择器出现（不是盲点）。
  await page.waitForSelector('.ant-select-selector', { timeout: 60_000 });
  await page.locator('.ant-select-selector').first().click();
  await page.locator('.ant-select-item-option', { hasText: username }).click();
  await page.getByRole('button', { name: '登 录' }).click();
  await page.waitForURL('/', { timeout: 15000 });
}

test.describe('交付物级签署写面（T8）', () => {
  // ⚠️ dev 下首屏要等 service worker 注册 ⇒ 默认 30s 不够
  test.setTimeout(90_000);

  test('签署下一步：步骤来自矩阵 + 签完步骤推进', async ({ page }) => {
    await loginAs(page, 'bob');

    await page.getByRole('menuitem', { name: '签署进度' }).click();
    await expect(page).toHaveURL(/\/deliverables\/progress$/);

    const row = page.locator('tr', { hasText: '换热器计算书' });
    await expect(row).toBeVisible();

    // ⚠️ 「签发」对**已有版本**的交付物**禁用**（后端会 409）
    await expect(row.getByTestId('deliverable-issue-d-2')).toBeDisabled();

    // 「签署」⇒ 弹窗显示**矩阵的下一步**
    await row.getByTestId('deliverable-sign-d-2').click();
    const nextStep = page.getByTestId('sign-next-step');
    await expect(nextStep).toBeVisible();
    // ⚠️ 矩阵（版本冻结快照）的第 1 步 = CHECKER ⇒ 显示的必须是它
    await expect(nextStep).toContainText('CHECKER');
    await expect(nextStep).toContainText('第 1 步');

    // 签下去 ⇒ 请求体的 step_index 落在矩阵的**那一步**
    const [request] = await Promise.all([
      page.waitForRequest((r) => r.url().includes('/sign-step')),
      page.getByTestId('sign-submit').click(),
    ]);
    const body = request.postDataJSON() as Record<string, unknown>;
    expect(body.step_index).toBe(1);
    expect(body.decision).toBe('SIGN');
    expect(body.version_id).toBe('v-2');
  });

  test('签发：无版本的交付物可签发（有版本的禁用）', async ({ page }) => {
    // ⚠️ **角色要选对**：签发（`INITIATE_CHANGE`）的允许角色 = **DESIGNER /
    //    SYSTEM_ADMIN**（后端 `_ISSUE_ROLES` 从 meta 派生）⇒ bob(CHECKER)
    //    **不能**签发 ⇒ 按钮会被正确地禁用 ⇒ 用 alice(DESIGNER)。
    await loginAs(page, 'alice');

    await page.getByRole('menuitem', { name: '签署进度' }).click();
    const row = page.locator('tr', { hasText: '泵计算书' });
    await expect(row).toBeVisible();

    const issueButton = row.getByTestId('deliverable-issue-d-1');
    await expect(issueButton).toBeEnabled();

    await issueButton.click();
    await expect(page.getByTestId('issue-submit')).toBeVisible();

    const [request] = await Promise.all([
      page.waitForRequest((r) => r.url().includes('/issue')),
      page.getByTestId('issue-submit').click(),
    ]);
    const body = request.postDataJSON() as Record<string, unknown>;
    // ⚠️ 字段名**逐字**（后端 Pydantic 默认**丢弃**多余字段 ⇒ 传错名不报错、
    //    存进去是空的）
    expect(body.version_purpose).toBe('ISSUED_FOR_CONSTRUCTION');
  });
});
