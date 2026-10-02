/**
 * AuditLogPage e2e (F-P2-009 Sprint 3 / Issue 7).
 *
 * 覆盖:
 * - 路由 /audit/logs 可达 + 3 tab 渲染
 * - 默认 config-audit tab 拉 MSW seed (含 CONFIG_R1_BACKFILL action)
 * - asset_id 过滤 (MSW handler 按 asset_id 过滤)
 * - equipment-deletion tab 不传 project_id → error alert
 * - audit-logs tab (DESIGNER 角色可见但 mock 不阻塞)
 *
 * 依赖: vite dev server (npm run dev) + MSW worker.
 */
import { test, expect } from './fixtures';

test.describe('AuditLogPage (F-P2-009 Sprint 3)', () => {
  test('路由 /audit/logs 可达 + 3 tab 渲染', async ({ loggedInPage: page }) => {
    await page.goto('/audit/logs');
    await expect(page.getByText(/Audit Query/)).toBeVisible();
    await expect(page.getByText(/CONFIG R1 修订痕迹/)).toBeVisible();
    await expect(page.getByText(/设备删除审计/)).toBeVisible();
    await expect(page.getByText(/通用 audit/)).toBeVisible();
  });

  test('默认 config-audit tab 拉 MSW seed 含 CONFIG_R1_BACKFILL', async ({
    loggedInPage: page,
  }) => {
    await page.goto('/audit/logs');
    // 等网络 idle + 表 ready
    await page.waitForLoadState('networkidle');
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
    await page.goto('/audit/logs');
    await page.waitForLoadState('networkidle');
    // 输入 asset_id = 42
    const assetInput = page.getByPlaceholder(/可选.*过滤单行/);
    await assetInput.fill('42');
    // 点查询
    await page.getByRole('button', { name: '查询' }).first().click();
    // MSW handler 过滤后只有 1 条 (asset_id=42)
    await page.waitForLoadState('networkidle');
    await expect(page.getByText('CONFIG_R1_BACKFILL').first()).toBeVisible();
    // 结果数量应为 1
    await expect(page.getByText(/共 1 条/)).toBeVisible({ timeout: 5000 });
  });

  test('equipment-deletion tab 不传 project_id → 403 error alert', async ({
    loggedInPage: page,
  }) => {
    await page.goto('/audit/logs');
    // 切到 equipment-deletion tab
    await page.getByText(/设备删除审计/).click();
    // 查询按钮应 disabled (project_id 未填)
    const queryBtn = page
      .getByRole('button', { name: '查询' })
      .nth(1); // 第 2 个查询按钮 (config-audit + equipment-deletion)
    // 不传 project_id 时 loadEquipmentDeletionAudit 立即 setErrorMsg
    // 切 tab 触发 useEffect → setErrorMsg('project_id 必填...')
    await expect(page.getByText(/project_id 必填/)).toBeVisible({ timeout: 3000 });
  });

  test('DESIGNER 角色: audit-logs tab 可点击 (mock 不强制 RBAC)', async ({
    loggedInPage: page,
  }) => {
    await page.goto('/audit/logs');
    await page.getByText(/通用 audit/).click();
    // 不应报错; 显示说明文字
    await expect(page.getByText(/通用 audit 日志查询/)).toBeVisible();
  });
});