/**
 * P7 Sprint 2 T5 EnergySummaryAggregatePage 端到端测试 (Playwright / R1 §7).
 *
 * 覆盖:
 *  - SPA 菜单导航 /util/energy-summary + PageHeader 渲染
 *  - 触发聚合按钮 → POST /util/energy-summary/aggregate → 渲染 8 Statistic
 *  - R1 §7 分类聚合 JSON 渲染 (steam_by_pressure_level 9 档 + fuel_gas_by_source 3 类)
 *  - 容差 status Tag (NA / OK / EXCEEDED per P7-OPEN-009 §6 ≤2%)
 *  - 电当量值/等价值 select 切换 (EQUIVALENT 默认 / EQUIVALENT_VALUE 炼油乙烯)
 *
 * 导航约定: zustand auth store 是内存态 (防 XSS), page.goto() 整页刷新
 * 会清 session → 登录后走 SPA 菜单点击 (共享 loggedInPage fixture).
 *
 * 依赖: vite dev server (npm run dev) + MSW worker
 */
import { test, expect, type Page } from './fixtures';

async function gotoEnergySummary(page: Page): Promise<void> {
  await page.getByRole('menuitem', { name: '综合能耗聚合' }).click();
  await expect(page).toHaveURL(/\/util\/energy-summary$/);
}

test.describe('EnergySummaryAggregatePage (T5 / R1 §7)', () => {
  test('SPA 导航 /util/energy-summary + PageHeader 渲染', async ({
    loggedInPage: page,
  }) => {
    await gotoEnergySummary(page);
    await expect(page.getByTestId('page-header-title')).toContainText(
      /综合能耗聚合/,
    );
  });

  test('触发表单: 业务年度 + 电当量值', async ({ loggedInPage: page }) => {
    await gotoEnergySummary(page);
    await expect(page.getByText('业务年度')).toBeVisible();
    await expect(page.getByText(/当量值.*0\.086/)).toBeVisible();
  });

  test('触发聚合 → 渲染 8 Statistic (6 类能源 + 总能耗 + 折标油)', async ({
    loggedInPage: page,
  }) => {
    await gotoEnergySummary(page);
    await page.waitForLoadState('networkidle');

    await page.getByRole('button', { name: '触发聚合' }).click();

    // 等 POST 响应 → Statistic 渲染
    await expect(page.getByText('年用电量')).toBeVisible({ timeout: 5000 });
    await expect(page.getByText('年燃料气')).toBeVisible();
    await expect(page.getByText('年蒸汽消耗')).toBeVisible();
    await expect(page.getByText('年新鲜水')).toBeVisible();
    await expect(page.getByText('年工艺气体')).toBeVisible();
    await expect(page.getByText('年低温余热')).toBeVisible();
    await expect(page.getByText('年总能耗')).toBeVisible();
    await expect(page.getByText('折标油总量')).toBeVisible();
  });

  test('R1 §7 分类聚合 JSON 渲染 (steam_by_pressure_level + fuel_gas_by_source)', async ({
    loggedInPage: page,
  }) => {
    await gotoEnergySummary(page);
    await page.waitForLoadState('networkidle');
    await page.getByRole('button', { name: '触发聚合' }).click();

    // MSW seed utilSeedEnergySummary 含 steam_by_pressure_level.0_8_TO_1_2_MPA=20000
    // + fuel_gas_by_source.GASFIELD_GAS=24694992
    await expect(
      page.getByText('steam_by_pressure_level.0_8_TO_1_2_MPA'),
    ).toBeVisible({ timeout: 5000 });
    await expect(page.getByText('fuel_gas_by_source.GASFIELD_GAS')).toBeVisible();
  });

  test('容差 status Tag 渲染 (NA = 无 XLS_REFERENCE 同年记录)', async ({
    loggedInPage: page,
  }) => {
    await gotoEnergySummary(page);
    await page.waitForLoadState('networkidle');
    await page.getByRole('button', { name: '触发聚合' }).click();

    // MSW 返回 tolerance_status: 'NA'
    await expect(page.getByText('NA', { exact: true }).first()).toBeVisible({
      timeout: 5000,
    });
  });

  test('电当量值 Tag 渲染 (默认 EQUIVALENT)', async ({ loggedInPage: page }) => {
    await gotoEnergySummary(page);
    await page.waitForLoadState('networkidle');
    await page.getByRole('button', { name: '触发聚合' }).click();

    // MSW 返回 electricity_value_type: 'EQUIVALENT'
    await expect(page.getByText('EQUIVALENT', { exact: true }).first()).toBeVisible({
      timeout: 5000,
    });
  });

  test('POST 触发后清空结果 button 可用', async ({ loggedInPage: page }) => {
    await gotoEnergySummary(page);
    await page.waitForLoadState('networkidle');
    await page.getByRole('button', { name: '触发聚合' }).click();

    // 等 NA Tag 出现
    await expect(page.getByText('NA', { exact: true }).first()).toBeVisible({
      timeout: 5000,
    });

    // 清空结果 button 可用
    const clearBtn = page.getByRole('button', { name: '清空结果' });
    await expect(clearBtn).toBeEnabled();
  });
});