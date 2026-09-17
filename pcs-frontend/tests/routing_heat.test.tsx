/**
 * HEAT 路由 + 菜单注册测试（P5-4 frontend / Task 5）。
 *
 * 覆盖：
 * 1. App.tsx 路由表注册 `/heat` → HeatRoute（静态 import + 字符串匹配配置源）
 * 2. MainLayout 菜单"换热器"项配置（菜单数组断言）
 *
 * 思路：直接静态 import 路由/菜单配置，不渲染含 Outlet 的全组件树；
 * 渲染 Outlets 上下文缺失易触发连锁错误。
 */
import { describe, it, expect } from 'vitest';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

import App from '../src/App';

const APP_TSX = readFileSync(resolve(__dirname, '../src/App.tsx'), 'utf8');
const MAIN_LAYOUT_TSX = readFileSync(
  resolve(__dirname, '../src/layouts/MainLayout.tsx'),
  'utf8',
);
const ROUTE_WRAPPERS_TSX = readFileSync(
  resolve(__dirname, '../src/pages/routeWrappers.tsx'),
  'utf8',
);

describe('HEAT 路由 + 菜单注册 (P5-4 frontend / Task 5)', () => {
  it('App.tsx 模块加载无报错', () => {
    expect(App).toBeDefined();
  });

  it("App.tsx 路由表注册 path: 'heat' → HeatRoute", () => {
    expect(APP_TSX).toMatch(/path:\s*['"]heat['"]/);
    expect(APP_TSX).toMatch(/HeatRoute/);
    expect(APP_TSX).toMatch(/element:\s*<HeatRoute\s*\/>/);
  });

  it("routeWrappers.tsx 定义并 export HeatRoute", () => {
    expect(ROUTE_WRAPPERS_TSX).toMatch(/export\s+function\s+HeatRoute/);
    expect(ROUTE_WRAPPERS_TSX).toMatch(/import\s+\{[^}]*HeatComputePage[^}]*\}\s+from\s+['"]\.\/heat\/HeatComputePage['"]/);
  });

  it('MainLayout 菜单注册 key: /heat label: 换热器', () => {
    expect(MAIN_LAYOUT_TSX).toMatch(/key:\s*['"]\/heat['"]/);
    expect(MAIN_LAYOUT_TSX).toMatch(/label:\s*['"]换热器['"]/);
  });
});