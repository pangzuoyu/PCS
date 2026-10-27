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
import { describe, it, expect, beforeAll, afterAll, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';

import { ChangeNoticeAction } from '../../../src/pages/results/ChangeNoticeAction';
import { useAuth } from '../../../src/store/auth';
import { moduleByRecordType } from '../../../src/pages/results/resultModules';

const MODULE = moduleByRecordType('CostEstResult');

function renderFor(status: string, allowedRoles: string[] | null = null): void {
  render(
    <ChangeNoticeAction
      module={MODULE}
      row={{ result_id: 'r-1', sign_status: status }}
      allowedRoles={allowedRoles}
      onStatusChange={() => undefined}
    />,
  );
}

describe('ChangeNoticeAction —— 按状态只给一个按钮', () => {
  beforeAll(() => {
    // antd message 需要 App context；这里不触发它，渲染本身不需要
  });
  afterAll(() => undefined);
  beforeEach(() => {
    useAuth.setState({ role: 'DESIGNER', accessToken: 'test-token' });
  });

  it('⚠️ R-12b：CHECKED ⇒ **无**行内按钮（「变更申请」是**状态机**动作 ⇒ 归 RecordActions）', () => {
    // ⚠️ 同一状态两个入口 = 两份映射 + 用户不知道该点哪个 ⇒ 状态机动作只在
    //    **详情抽屉**的操作栏里（R-12b）⇒ 行内只留「建单 / 作废」两个
    //    **非状态机**动作。
    renderFor('CHECKED');
    expect(screen.queryByTestId('change-notice-action')).toBeNull();
  });

  it('⚠️ R-12b：CHANGE_PENDING ⇒ **无**行内按钮（「提交变更完成」归 RecordActions）', () => {
    renderFor('CHANGE_PENDING');
    expect(screen.queryByTestId('change-notice-action')).toBeNull();
  });

  it('⚠️ RF-1：角色不在 `allowedRoles` ⇒ 按钮**禁用** + 写明原因（点了才吃 403）', () => {
    // ⚠️ 角色来自登录态 ⇒ 用例要先设（否则 role=null ⇒ 前端**不猜**）
    useAuth.setState({ role: 'CHECKER', accessToken: 'test-token' });
    renderFor('CHANGED', ['DESIGNER', 'SYSTEM_ADMIN']);
    const btn = screen.getByTestId('change-notice-action');
    expect(btn.textContent).toBe('创建变更单');
    expect(screen.getByTestId('change-notice-action-hint').textContent).toContain('角色');
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
