/**
 * 记录操作栏（Playwright e2e · P9B-2 · T10）。
 *
 * ## 为什么这条 e2e 抓的是**契约破坏性变更**
 *
 * **R-17**：送审批准链改成由**后端**从项目绑定的 `module='RECORD'` 矩阵推导
 * ⇒ 请求体**不再收** `approval_role` / `approval_depth`
 * （`SubmitApprovalRequest` 是 `extra="forbid"` ⇒ 多传就 **422**）。
 *
 * ⇒ 断言**请求体**：不是「按钮能点」，而是「点出去的报文长什么样」。
 * 前端多传一个字段 ⇒ 后端 422 ⇒ 用户看到「提交失败」而不知道为什么。
 *
 * ## 依赖
 *
 * vite dev server（`npm run dev`）+ MSW worker（浏览器层拦截 `/api/v1/*`）。
 */
import { test, expect } from './fixtures';

test.describe('记录操作栏 —— 送审批准链来自项目矩阵（R-17）', () => {
  test('提交批准的请求体**不含** approval_role / approval_depth', async ({
    loggedInPage: page,
  }) => {
    // ⚠️ 登录的是 alice(DESIGNER) —— 矩阵第 1 步是 **CHECKER** ⇒ 不是
    //    「自己送自己审」⇒ 按钮**可点**（用 bob 登录反而会被前端禁用）。
    await page.getByRole('menuitem', { name: '冷却塔结果' }).click();
    await expect(page).toHaveURL(/\/results\/cool-tower$/);

    const row = page.locator('tr', { hasText: 'CT-DEGRADED' });
    await expect(row).toBeVisible();
    await row.getByTestId('result-detail-button').click();

    const drawer = page.getByTestId('record-detail-drawer');
    await expect(drawer).toBeVisible();

    const submitButton = drawer.getByTestId('record-action-SUBMIT_FOR_CHECK');
    await expect(submitButton).toBeVisible();
    await expect(submitButton).toBeEnabled();

    // ⚠️ 断言**请求体**：多传 approval_role / approval_depth ⇒ 后端 422
    const [request] = await Promise.all([
      page.waitForRequest((r) => r.url().includes('/submit-approval')),
      submitButton.click(),
    ]);

    expect(request.method()).toBe('POST');
    const body = request.postDataJSON() as Record<string, unknown>;
    expect(body.approval_role).toBeUndefined();
    expect(body.approval_depth).toBeUndefined();
    // ⚠️ 请求体只允许有 `reason`（R-17 之后**没有别的字段**）
    expect(Object.keys(body).filter((k) => k !== 'reason')).toEqual([]);
  });
});
