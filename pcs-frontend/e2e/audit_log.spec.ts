/**
 * AuditLogPage e2e (F-P2-009 Sprint 3 / Issue 7).
 *
 * 覆盖:
 * - SPA 菜单导航到 /audit/logs + 3 tab 渲染
 * - 默认 config-audit tab 拉 MSW seed (含 CONFIG_R1_BACKFILL action)
 * - asset_id 过滤 (MSW handler 按 asset_id 过滤)
 * - equipment-deletion tab 不传 project_id → error alert
 * - audit-logs tab (DESIGNER 角色可见但 mock 不强制 RBAC)
 *
 * 导航约定: zustand auth store 是内存态 (防 XSS, 不落 localStorage),
 * page.goto() 整页刷新会清 session → RequireAuth 弹回 /login。
 * 登录后必须走 SPA 菜单点击 (无刷新) 到达目标页。
 *
 * 依赖: vite dev server (npm run dev) + MSW worker.
 */
import { test, expect, type Page } from './fixtures';

/** SPA 菜单导航到 audit 页 (避免整页刷新丢 session). */
async function gotoAuditViaMenu(page: Page): Promise<void> {
  await page.getByRole('menuitem', { name: 'Audit Query (F-P2-009)' }).click();
  await expect(page).toHaveURL(/\/audit\/logs$/);
}

test.describe('AuditLogPage (F-P2-009 Sprint 3)', () => {
  test('SPA 导航到 /audit/logs + 3 tab 渲染', async ({ loggedInPage: page }) => {
    await gotoAuditViaMenu(page);
    await expect(page.getByTestId('page-header-title')).toHaveText(
      /Audit Query/,
    );
    await expect(page.getByRole('tab', { name: /CONFIG R1 修订痕迹/ })).toBeVisible();
    await expect(page.getByRole('tab', { name: /设备删除审计/ })).toBeVisible();
    await expect(page.getByRole('tab', { name: /通用 audit/ })).toBeVisible();
  });

  test('默认 config-audit tab 拉 MSW seed 含 CONFIG_R1_BACKFILL', async ({
    loggedInPage: page,
  }) => {
    await gotoAuditViaMenu(page);
    // MSW seed 返回 2 条 CONFIG_R1_BACKFILL (asset_id=42 + asset_id=99)
    await expect(page.getByText('CONFIG_R1_BACKFILL').first()).toBeVisible({
      timeout: 5000,
    });
    // 资源类型 tag
    await expect(
      page.getByText('config_energy_conversion_factors').first(),
    ).toBeVisible();
  });

  test('config-audit tab 输入 asset_id=42 过滤', async ({ loggedInPage: page }) => {
    await gotoAuditViaMenu(page);
    // 输入 asset_id = 42
    await page.getByRole('spinbutton').fill('42');
    // 点查询 (config-audit tab 的查询按钮)
    await page.getByRole('button', { name: '查 询' }).first().click();
    // MSW handler 过滤后只有 1 条 (asset_id=42)
    await expect(page.getByText(/共 1 条/)).toBeVisible({ timeout: 5000 });
    await expect(page.getByText('CONFIG_R1_BACKFILL').first()).toBeVisible();
  });

  test('equipment-deletion tab 不传 project_id → 403 error alert', async ({
    loggedInPage: page,
  }) => {
    await gotoAuditViaMenu(page);
    // 切到 equipment-deletion tab
    await page.getByRole('tab', { name: /设备删除审计/ }).click();
    // 切 tab 触发 loadEquipmentDeletionAudit → setErrorMsg (project_id 必填)
    await expect(page.getByText(/project_id 必填/)).toBeVisible({ timeout: 5000 });
  });

  test('DESIGNER 角色: audit-logs tab disabled (RBAC 感知 UI)', async ({
    loggedInPage: page,
  }) => {
    await gotoAuditViaMenu(page);
    // alice=DESIGNER 非 SYSTEM_ADMIN → 通用 audit tab 应 disabled (页面 RBAC 感知)
    const tab = page.getByRole('tab', { name: /通用 audit/ });
    await expect(tab).toBeVisible();
    await expect(tab).toBeDisabled();
  });
});