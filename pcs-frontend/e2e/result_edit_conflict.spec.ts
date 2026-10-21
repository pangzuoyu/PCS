/**
 * 编辑冲突 409 分流（Playwright e2e · P9B-1 T7）。
 *
 * ## 为什么只做这一条
 *
 * E2E 的价值是**跨组件集成**（列表 → 抽屉 → 弹窗 → 审计）⇒ 一条够；
 * 三条 = 三个 flaky 源。
 *
 * ## 流程
 *
 * 登录 → 结果页 → 打开记录编辑 → 修改并保存 → 模拟 409（他人先保存）
 * → 断言 409 弹窗按 `basis` 分流 → 点「查看差异」→ 断言展示
 * → 点「放弃我的修改并刷新」→ 断言弹窗关闭。
 *
 * ⚠️ 409 由 **mock 的场景记录**驱动（记录 id = `scenario-conflict-hash`
 * ⇒ PATCH 返 `basis=record_hash`）⇒ 不用在测试里拦截网络。
 *
 * 依赖：vite dev server（`npm run dev`）+ MSW worker。
 */
import { test, expect, type Page } from './fixtures';

async function gotoCoolTower(page: Page): Promise<void> {
  await page.getByRole('menuitem', { name: '冷却塔结果' }).click();
  await expect(page).toHaveURL(/\/results\/cool-tower$/);
}

test.describe('结果记录编辑 —— 409 冲突分流（P9B-1）', () => {
  test('保存冲突 ⇒ 弹窗按 basis 分流 + [查看差异] / [放弃并刷新] 两个出口', async ({
    loggedInPage: page,
  }) => {
    await gotoCoolTower(page);

    // 场景记录（mock 按 id 驱动 409）
    const row = page.locator('tr', { hasText: 'CT-CONFLICT-HASH' });
    await expect(row).toBeVisible();
    // ⚠️ antd 的 Button 对**两个汉字**的标签会插空格（"编 辑"）⇒ 用正则
    await row.getByRole('button', { name: /编\s*辑/ }).click();

    // 抽屉打开 ⇒ 改一个字段 ⇒ 保存
    const drawer = page.getByTestId('result-edit-drawer');
    await expect(drawer).toBeVisible();
    await page.getByTestId('field-duty_kw').fill('999');
    await page.getByTestId('result-save').click();

    // 409 弹窗 ⇒ 文案按 basis（record_hash）分流
    const modal = page.getByTestId('edit-conflict-modal');
    await expect(modal).toBeVisible();
    await expect(modal).toContainText('修改了这条记录');
    await expect(modal).not.toContainText('缺少并发校验基线');

    // [查看差异] ⇒ 拉编辑审计并展示
    await page.getByTestId('conflict-view-diff').click();
    await expect(page.getByTestId('conflict-diff')).toBeVisible();

    // [放弃我的修改并刷新] ⇒ 弹窗关闭（表单复位）
    await page.getByTestId('conflict-refresh').click();
    await expect(modal).toBeHidden();
  });
});
