/**
 * P7-6B CoolingWaterPage 端到端测试 (Playwright / R1 §7.2 9 类水).
 *
 * 覆盖:
 *  - SPA 菜单导航 /util/cooling-water + PageHeader 渲染
 *  - 9 类水 (FRESH_WATER / CIRCULATING_WATER / ...) Select 可选
 *  - CRUD form 提交: 设备位号 + 水类 + 小时消耗 + 年操作
 *  - 9 类水分类聚合 Table 渲染 (medium_type != STEAM 过滤)
 *
 * 导航约定: zustand auth store 是内存态 (防 XSS), page.goto() 整页刷新
 * 会清 session → 登录后走 SPA 菜单点击 (共享 loggedInPage fixture).
 *
 * 依赖: vite dev server (npm run dev) + MSW worker.
 */
import { test, expect, type Page } from './fixtures';

async function gotoCoolingWater(page: Page): Promise<void> {
  await page.getByRole('menuitem', { name: '冷却水子表' }).click();
  await expect(page).toHaveURL(/\/util\/cooling-water$/);
}

test.describe('CoolingWaterPage (P7-6B / R1 §7.2 9 类水)', () => {
  test('SPA 导航 /util/cooling-water + PageHeader 渲染', async ({
    loggedInPage: page,
  }) => {
    await gotoCoolingWater(page);
    await expect(page.getByTestId('page-header-title')).toContainText(
      /冷却水/,
    );
  });

  test('4 个 Statistic Card 渲染 (水类覆盖 / 年总消耗 / 年折标油 / 年折标煤)', async ({
    loggedInPage: page,
  }) => {
    await gotoCoolingWater(page);
    await expect(page.getByText('水类覆盖')).toBeVisible();
    await expect(page.getByText('年总消耗')).toBeVisible();
    await expect(page.getByText('年折标油')).toBeVisible();
    await expect(page.getByText('年折标煤')).toBeVisible();
  });

  test('9 类水 Select 可选 (循环水 / 新鲜水 options 出现)', async ({
    loggedInPage: page,
  }) => {
    await gotoCoolingWater(page);
    await page.waitForLoadState('networkidle');

    const waterSelect = page.locator('select, [role="combobox"]').first();
    await waterSelect.click();

    // 验证 9 类水 options (MOCK seed 含 CW-001 + FW-001, 与 MSW 列表返回一致)
    await expect(page.getByText('循环水').first()).toBeVisible();
    await expect(page.getByText('新鲜水').first()).toBeVisible();
  });

  test('CRUD form: 填设备位号 + 选水类 + 小时消耗 → POST /util/heat-exchange-items', async ({
    loggedInPage: page,
  }) => {
    await gotoCoolingWater(page);
    await page.waitForLoadState('networkidle');

    // 填设备位号
    await page.getByPlaceholder('CW-001').fill('CW-E2E-001');

    // 选水类 (CIRCULATING_WATER → 循环水)。antd dropdown portal 在 headless
    // 下定位异常 (viewport 外 + 虚拟列表 unstable) → 键盘流绕过几何依赖:
    // WATER_TYPE_OPTIONS 顺序 FRESH_WATER(1) → CIRCULATING_WATER(2)
    const select = page.locator('.ant-select').first();
    await select.scrollIntoViewIfNeeded();
    await select.click();
    await page.keyboard.press('ArrowDown'); // 高亮 新鲜水
    await page.keyboard.press('ArrowDown'); // 高亮 循环水
    await page.keyboard.press('Enter'); // 选中

    // 填小时消耗 5.5 t/h
    const consumptionInput = page.getByLabel(/小时消耗/);
    await consumptionInput.fill('5.5');

    // 提交
    await page.getByRole('button', { name: '新 增' }).click();

    // 验证 success Alert (MSW POST handler 返回 201)
    await expect(page.getByText(/已创建.*CW-E2E-001/)).toBeVisible({
      timeout: 5000,
    });
  });

  test('9 类水分类聚合 Table (medium_type != STEAM 过滤)', async ({
    loggedInPage: page,
  }) => {
    await gotoCoolingWater(page);
    await page.waitForLoadState('networkidle');

    // MSW seed 含 CW-001 (CIRCULATING_WATER) + ST-MP-001 (STEAM)
    // Page 应只显示 CW-001 (ST-MP-001 被 9 类水过滤剔除)
    await expect(page.getByText('CW-001').first()).toBeVisible();
    // ST-MP-001 不在冷却水列表
    await expect(page.locator('text=ST-MP-001')).toHaveCount(0);
  });
});