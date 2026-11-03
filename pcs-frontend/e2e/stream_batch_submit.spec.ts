/**
 * 批量提交校对的 e2e（P9B-3b · D6-A）。
 *
 * ⚠️ **本 spec 不进批末闸门**（CLAUDE.md §发布前检查）—— 与现有 6 个 spec 一致，
 * 因为它们依赖 playwright 浏览器（本地未装时无法运行）。
 *
 * **本 spec 的价值**：
 * - 覆盖 vitest 结构上测不到的接线：「antd rowSelection → ids → 请求体」；
 * - 断言**报文内容**（不只是 UI 变化）—— vitest 只能测「弹窗出现」，
 *   测不到「请求里带了哪几个 id」。
 *
 * **跑法**：
 *   cd pcs-frontend && npm run e2e:install   # 首次（下载 chromium）
 *   cd pcs-frontend && npm run e2e            # 手动跑（不是批末闸门）
 *
 * **已知腐化风险**：不进闸门 ⇒ 没有自动化强制跑 ⇒ 需要靠人记得。
 * 登记为 TODO-120（触发条件：连续 3 批 QA 阶段发现 e2e 相关 bug / 有 CI /
 * 主动发起「e2e 腐化」专项）。
 */
import { test, expect, type Page } from './fixtures';

/**
 * SPA 菜单导航到物流一览页。
 *
 * ⚠️ **不能用 `page.goto('/sim/streams')`** —— zustand auth store 是**内存态**
 * （防 XSS，不落 localStorage）⇒ 整页刷新会清 session ⇒ `RequireAuth`
 * 弹回 `/login` ⇒ 页面永远没有表格行。
 * ⇒ 必须走**菜单点击**（无刷新），与既有 6 个 spec 的约定一致。
 */
async function gotoStreamsViaMenu(page: Page): Promise<void> {
  await page.getByRole('menuitem', { name: '物流一览' }).click();
  await expect(page).toHaveURL(/\/sim\/streams$/);
}

test.describe('批量提交校对 —— 勾选 ⇒ 报文的接线', () => {
  test('勾选 2 行 ⇒ 报文带这 2 个 id（顺序一致）', async ({ loggedInPage: page }) => {
    await gotoStreamsViaMenu(page);
    await expect(page.locator('tr.ant-table-row').first()).toBeVisible();

    // ⚠️ **勾选行**（不是表头全选）⇒ 断言的是「勾了哪几行」
    const rows = page.locator('tr.ant-table-row');
    await rows.nth(0).locator('input[type="checkbox"]').check();
    await rows.nth(1).locator('input[type="checkbox"]').check();

    const button = page.getByTestId('stream-batch-submit');
    await expect(button).toBeEnabled();

    // ⚠️ 核心断言：**报文**带哪几个 id（不是只断言 UI 变化）
    const [request] = await Promise.all([
      page.waitForRequest((r) => r.url().includes('/streams/batch-submit')),
      button.click(),
    ]);

    expect(request.method()).toBe('POST');
    const body = request.postDataJSON() as {
      stream_ids: string[];
      dry_run: boolean;
    };
    // ⚠️ 断言的是**这两行的 id**（不是「长度是 2」）—— 行 id 从行内的
    //    「查看」按钮 testid 里读（`stream-view-<id>`）⇒ 断言的是
    //    **页面上真正被勾中的那两行**，不是碰巧长度对。
    const expectedIds = await Promise.all(
      [rows.nth(0), rows.nth(1)].map((row) =>
        row.getByTestId(/^stream-view-/).getAttribute('data-testid'),
      ),
    );
    expect(body.stream_ids).toEqual(
      expectedIds.map((t) => t!.replace('stream-view-', '')),
    );
    expect(body.dry_run).toBe(false);

    // 摘要弹窗出现（「成功 N · 失败 M」）
    await expect(page.getByTestId('stream-batch-summary')).toBeVisible();
    await expect(page.getByTestId('stream-batch-summary')).toContainText('成功');
  });

  test('没选中 ⇒ 按钮禁用（点不动 ⇒ 没有空批次请求）', async ({ loggedInPage: page }) => {
    await gotoStreamsViaMenu(page);
    await expect(page.locator('tr.ant-table-row').first()).toBeVisible();

    await expect(page.getByTestId('stream-batch-submit')).toBeDisabled();
  });
});
