/**
 * P7-6B CoolingWaterPage 端到端测试 (Playwright / R1 §7.2 9 类水).
 *
 * 覆盖:
 *  - 路由 /util/cooling-water 可达 + PageHeader 渲染
 *  - 9 类水 (FRESH_WATER / CIRCULATING_WATER / ...) Select 可选
 *  - CRUD form 提交: 设备位号 + 水类 + 小时消耗 + 年操作
 *  - 9 类水分类聚合 Table 渲染 (medium_type != STEAM 过滤)
 *
 * 依赖: vite dev server (npm run dev) + MSW worker (setupWorker in mocks/browser.ts)
 * 启动: npx playwright test cooling_water.spec.ts (需 vite 端口 5173 已监听)
 */
import { test, expect } from '@playwright/test';

test.describe('CoolingWaterPage (P7-6B / R1 §7.2 9 类水)', () => {
  test.beforeEach(async ({ page }) => {
    // mock-login via LoginPage (alice/DESIGNER 默认 mock)
    await page.goto('/login');
    // 等 MSW worker ready (避免 login POST 没拦截到)
    await page.waitForResponse(
      (res) => res.url().includes('/api/v1/auth/mock-login') && res.status() === 200,
      { timeout: 10000 }
    ).catch(() => undefined);  // 第一次请求可能命中网络, 跳过
    await page.getByRole('button', { name: '登 录' }).click();
    // 等 mock-login 响应 + 跳转
    await page.waitForURL('/', { timeout: 15000 });
  });

  test('路由 /util/cooling-water 可达 + PageHeader 渲染', async ({ page }) => {
    await page.goto('/util/cooling-water');
    await expect(page.getByText(/冷却水子表/)).toBeVisible();
    await expect(page.getByText(/R1.*7\.2.*9 类水/)).toBeVisible();
  });

  test('4 个 Statistic Card 渲染 (水类覆盖 / 年总消耗 / 年折标油 / 年折标煤)', async ({ page }) => {
    await page.goto('/util/cooling-water');
    await expect(page.getByText('水类覆盖')).toBeVisible();
    await expect(page.getByText('年总消耗')).toBeVisible();
    await expect(page.getByText('年折标油')).toBeVisible();
    await expect(page.getByText('年折标煤')).toBeVisible();
  });

  test('9 类水 Select 可选 (FRESH_WATER / CIRCULATING_WATER / SOFTENED_WATER / ...)', async ({ page }) => {
    await page.goto('/util/cooling-water');
    // 等列表 ready
    await page.waitForLoadState('networkidle');

    const waterSelect = page.locator('select, [role="combobox"]').first();
    await waterSelect.click();

    // 验证 9 类水 options (MOCK seed 含 CW-001 + FW-001, 与 MSW 列表返回一致)
    await expect(page.getByText('循环水')).toBeVisible();
    await expect(page.getByText('新鲜水')).toBeVisible();
  });

  test('CRUD form: 填设备位号 + 选水类 + 小时消耗 → POST /util/heat-exchange-items', async ({ page }) => {
    await page.goto('/util/cooling-water');
    await page.waitForLoadState('networkidle');

    // 填设备位号
    await page.getByPlaceholder('CW-001').fill('CW-E2E-001');

    // 选水类 (CIRCULATING_WATER → 循环水)
    await page.locator('select, [role="combobox"]').first().click();
    await page.getByText('循环水').click();

    // 填小时消耗 5.5 t/h
    const consumptionInput = page.getByLabel(/小时消耗/);
    await consumptionInput.fill('5.5');

    // 提交
    await page.getByRole('button', { name: '新增' }).click();

    // 验证 success Alert (MSW POST handler 返回 201)
    await expect(page.getByText(/已创建.*CW-E2E-001/)).toBeVisible({ timeout: 5000 });
  });

  test('9 类水分类聚合 Table (medium_type != STEAM 过滤)', async ({ page }) => {
    await page.goto('/util/cooling-water');
    await page.waitForLoadState('networkidle');

    // MSW seed 含 CW-001 (CIRCULATING_WATER) + ST-MP-001 (STEAM)
    // Page 应只显示 CW-001 (ST-MP-001 被 9 类水过滤剔除)
    await expect(page.getByText('CW-001')).toBeVisible();
    // ST-MP-001 不在冷却水列表
    await expect(page.locator('text=ST-MP-001')).toHaveCount(0);
  });
});