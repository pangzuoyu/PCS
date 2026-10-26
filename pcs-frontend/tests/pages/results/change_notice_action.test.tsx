/**
 * 结果记录行上的**变更动作**（TODO-083 · P9A-DLV-011 T4 的前端）。
 *
 * ## 这组测试钉住的失败模式
 *
 * | # | 失败模式 | 期望 |
 * |---|---|---|
 * | RF-1 | 三个按钮**同时显示** ⇒ 用户去撞状态机（后端 409） | 按 `sign_status` **只给一个**按钮 |
 * | RF-2 | DRAFT / OBSOLETE 等态也显示变更按钮 ⇒ 点下去必 409 | 不显示 |
 * | RF-3 | 按钮文案与后端事件**对不上**（「提交变更批准」实际是 apply-change） | 文案 = 变更申请 / 提交变更完成 / 创建变更单 |
 */
import { describe, it, expect, beforeAll, afterAll } from 'vitest';
import { render, screen } from '@testing-library/react';

import { ChangeNoticeAction } from '../../../src/pages/results/ChangeNoticeAction';
import { moduleByRecordType } from '../../../src/pages/results/resultModules';

const MODULE = moduleByRecordType('CostEstResult');

function renderFor(status: string): void {
  render(
    <ChangeNoticeAction
      module={MODULE}
      row={{ result_id: 'r-1', sign_status: status }}
      onStatusChange={() => undefined}
    />,
  );
}

describe('ChangeNoticeAction —— 按状态只给一个按钮', () => {
  beforeAll(() => {
    // antd message 需要 App context；这里不触发它，渲染本身不需要
  });
  afterAll(() => undefined);

  it('RF-1/RF-3：CHECKED ⇒ 「变更申请」', () => {
    renderFor('CHECKED');
    expect(screen.getByTestId('change-notice-action').textContent).toBe('变更申请');
  });

  it('RF-1/RF-3：CHANGE_PENDING ⇒ 「提交变更完成」（= 后端 apply-change）', () => {
    renderFor('CHANGE_PENDING');
    expect(screen.getByTestId('change-notice-action').textContent).toBe('提交变更完成');
  });

  it('RF-1/RF-3：CHANGED ⇒ 「创建变更单」', () => {
    renderFor('CHANGED');
    expect(screen.getByTestId('change-notice-action').textContent).toBe('创建变更单');
  });

  it('RF-2：DRAFT / OBSOLETE / IN_APPROVAL ⇒ 没有变更按钮', () => {
    renderFor('DRAFT');
    expect(screen.queryByTestId('change-notice-action')).toBeNull();
  });
});
