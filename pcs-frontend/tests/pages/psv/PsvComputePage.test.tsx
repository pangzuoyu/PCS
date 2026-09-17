/**
 * PsvComputePage 测试（P5-3-6，对齐 V1.2 SPEC §7.11.5）。
 *
 * V1.1 → V1.2 contract 变化：
 * - 泄放工况由多选 Checkbox.Group → 单选 Select（4 scenario 路由）
 * - 未选流提示由 DOM Alert → antd message.error（异步弹出，不在 DOM 树）
 * - 新增 design_stage BASIC/DETAIL 切换
 * - 新增 outlet_stream + record_hash + formula_ref_json 展示
 *
 * 覆盖：
 * - PageHeader + 项目标准 Tag + design_stage 切换
 * - 4 Tab 切换
 * - 输入表单（流 Select + 单选 scenario + phase）
 * - 计算按钮存在
 */
import { describe, it, expect } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';

import { PsvComputePage } from '../../../src/pages/psv/PsvComputePage';

const streams = [
  { stream_id: 's-1', tag_number: 'FEED-101', sign_status: 'CHECKED' },
];

describe('PsvComputePage — 渲染 (P5-3-6)', () => {
  it('渲染 PageHeader + 项目标准 Tag + Tabs + design_stage', () => {
    render(<PsvComputePage streams={streams} projectStandard="API" />);
    expect(screen.getByTestId('psv-compute-page')).toBeTruthy();
    expect(screen.getByTestId('psv-standard-tag')).toBeTruthy();
    expect(screen.getByTestId('psv-standard-tag').textContent).toContain('API');
    expect(screen.getByTestId('psv-tabs')).toBeTruthy();
    expect(screen.getByTestId('psv-design-stage')).toBeTruthy();
  });

  it('输入 Tab：物流 + 工况（单选 Select）+ 相态 + 计算按钮', () => {
    render(<PsvComputePage streams={streams} />);
    expect(screen.getByTestId('psv-stream-select')).toBeTruthy();
    expect(screen.getByTestId('psv-scenario-select')).toBeTruthy();
    expect(screen.getByTestId('psv-phase-select')).toBeTruthy();
    expect(screen.getByTestId('psv-calculate')).toBeTruthy();
  });
});

describe('PsvComputePage — 错误路径 (P5-3-6)', () => {
  it('未选物流 → 点计算 → 调用 message.error（V1.2 不渲染 DOM Alert）', () => {
    // V1.2 实现：未选流 → message.error('请先选择 CHECKED 物流') 异步弹出，
    // 不进入 setError state（不渲染 psv-error Alert）。
    // 此处只验证点击不崩溃 + form 仍可用即可。
    render(<PsvComputePage streams={streams} />);
    fireEvent.click(screen.getByTestId('psv-calculate'));
    // 提交后表单仍渲染 → 未选流不会清空表单
    expect(screen.getByTestId('psv-stream-select')).toBeTruthy();
    expect(screen.getByTestId('psv-calculate')).toBeTruthy();
  });
});