/**
 * RecordActions —— 记录操作按钮组（P9B-2 · T4 · SPEC §6.3）。
 *
 * ## 这组测试守的是「**点了才发现不行**」那族失败
 *
 * | 失败模式 | 期望行为 |
 * |---|---|
 * | 按钮只看状态、不看角色 | 角色不在 `allowed_roles` ⇒ **禁用 + Tooltip** |
 * | 必填理由被空理由提交 | 理由为空 ⇒ **提交按钮禁用** |
 * | 9 态动作发给没有 9 态列的模块 | `signStatus=null` ⇒ **不渲染、不发请求** |
 * | 矩阵第 1 步 == 我 ⇒ 送审必吃 403 | **禁用 + Tooltip**（门禁前置） |
 * | 双击提交 ⇒ 发两次 | pending 期间禁用 ⇒ **只发一次** |
 *
 * ⚠️ **按钮来自 `GET /meta/state-machine`**（后端从 `ALLOWED_TRANSITIONS` 生成），
 * **不是**前端硬编码的按钮表 ⇒ 后端加一个迁移，前端自动跟上。
 */
import { describe, it, expect, vi, beforeAll, afterAll, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';

import { RecordActions } from '../../../src/components/common/RecordActions';
import { useAuth } from '../../../src/store/auth';

const MODULE = 'cooling_tower_result';
const RECORD_ID = '11111111-2222-3333-4444-555555555555';

let recordCalls = 0;
let lastBody: unknown = null;
let lastAction = '';
let metaStatus = 200;
let matrixStatus = 200;
/** 项目绑定的 RECORD 矩阵的**步骤角色**（null = 项目**没绑**矩阵）。 */
let matrixRoles: string[] | null = ['CHECKER'];

const STATE_MACHINE = {
  transitions: [
    {
      from: 'DRAFT',
      action: 'SUBMIT_FOR_CHECK',
      to: 'IN_APPROVAL',
      allowed_roles: ['DESIGNER', 'CHECKER', 'APPROVER', 'SYSTEM_ADMIN'],
      preconditions: [],
      side_effects: [],
    },
    {
      from: 'DRAFT',
      action: 'OBSOLETE',
      to: 'OBSOLETE',
      allowed_roles: ['DESIGNER', 'CHECKER', 'APPROVER', 'SYSTEM_ADMIN'],
      preconditions: [],
      side_effects: [],
    },
    {
      from: 'IN_APPROVAL',
      action: 'PASS_CHECK',
      to: 'CHECKED',
      allowed_roles: ['CHECKER', 'REVIEWER', 'APPROVER', 'SYSTEM_ADMIN'],
      preconditions: [],
      side_effects: [],
    },
    {
      from: 'IN_APPROVAL',
      action: 'REJECT_CHECK',
      to: 'CHECK_REJECTED',
      allowed_roles: ['CHECKER', 'REVIEWER', 'APPROVER', 'SYSTEM_ADMIN'],
      preconditions: [],
      side_effects: [],
    },
    {
      from: 'CHECKED',
      action: 'INITIATE_CHANGE',
      to: 'CHANGE_PENDING',
      allowed_roles: ['DESIGNER', 'SYSTEM_ADMIN'],
      preconditions: [],
      side_effects: [],
    },
    {
      from: 'CHANGE_PENDING',
      action: 'APPLY_CHANGE',
      to: 'CHANGED',
      allowed_roles: ['DESIGNER', 'CHECKER', 'SYSTEM_ADMIN'],
      preconditions: [],
      side_effects: [],
    },
  ],
  allowed: {
    DRAFT: ['SUBMIT_FOR_CHECK', 'OBSOLETE'],
    IN_APPROVAL: ['PASS_CHECK', 'REJECT_CHECK'],
    CHECKED: ['INITIATE_CHANGE'],
    CHANGE_PENDING: ['APPLY_CHANGE'],
  },
};

const server = setupServer(
  http.get('/api/v1/meta/state-machine', () => {
    if (metaStatus !== 200) {
      return HttpResponse.json({ code: 'BOOM', message: 'meta 挂了' }, { status: 500 });
    }
    return HttpResponse.json(STATE_MACHINE);
  }),
  http.get('/api/v1/projects/:projectId/signature-matrices', () => {
    if (matrixStatus !== 200) {
      return HttpResponse.json({ code: 'BOOM', message: '矩阵挂了' }, { status: 500 });
    }
    if (matrixRoles === null) return HttpResponse.json([]);
    return HttpResponse.json([
      {
        module: 'RECORD',
        matrix_id: 'm-1',
        matrix_name: '默认记录矩阵',
        status: 'ACTIVE',
        steps: matrixRoles.map((role, i) => ({
          step_order: i + 1,
          sign_role: role,
          required: true,
          can_self_check: true,
          can_skip: false,
        })),
      },
    ]);
  }),
  http.post('/api/v1/records/:module/:recordId/:action', async ({ request, params }) => {
    recordCalls += 1;
    lastAction = String(params['action']);
    lastBody = await request.json();
    return HttpResponse.json({
      record_type: MODULE,
      record_id: RECORD_ID,
      from_status: 'DRAFT',
      to_status: 'IN_APPROVAL',
    });
  }),
);

/**
 * 各用例仍用不同的 projectId（历史惯例：曾有模块级链缓存跨用例污染，
 * 评审 #1 后改为**挂载级**拉取 —— 见「重绑后重新挂载」用例）。
 */
let projectSeq = 0;

function renderActions(signStatus: string | null, projectId = `project-${++projectSeq}`) {
  return render(
    <RecordActions
      module={MODULE}
      recordId={RECORD_ID}
      signStatus={signStatus}
      projectId={projectId}
      onDone={vi.fn()}
    />,
  );
}

describe('RecordActions —— 按状态渲染（meta 驱动）', () => {
  beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
  afterAll(() => server.close());
  beforeEach(() => {
    recordCalls = 0;
    lastBody = null;
    lastAction = '';
    metaStatus = 200;
    matrixStatus = 200;
    matrixRoles = ['CHECKER'];
    useAuth.setState({ role: 'DESIGNER', accessToken: 'test-token' });
  });

  it('⚠️ signStatus=null ⇒ **不渲染任何按钮**且**不发** /records/… 请求（RF-4）', async () => {
    renderActions(null);
    await waitFor(() => expect(screen.queryByTestId('record-actions')).toBeNull());
    expect(recordCalls).toBe(0);
  });

  it('DRAFT ⇒ 有「提交批准」「弃用」；**没有**「通过 / 退回」', async () => {
    renderActions('DRAFT');
    await waitFor(() => expect(screen.getByTestId('record-action-SUBMIT_FOR_CHECK')).toBeTruthy());
    expect(screen.getByTestId('record-action-OBSOLETE')).toBeTruthy();
    expect(screen.queryByTestId('record-action-PASS_CHECK')).toBeNull();
    expect(screen.queryByTestId('record-action-REJECT_CHECK')).toBeNull();
  });

  it('IN_APPROVAL ⇒ 有「通过」「退回」；**没有**「提交批准」', async () => {
    renderActions('IN_APPROVAL');
    await waitFor(() => expect(screen.getByTestId('record-action-PASS_CHECK')).toBeTruthy());
    expect(screen.getByTestId('record-action-REJECT_CHECK')).toBeTruthy();
    expect(screen.queryByTestId('record-action-SUBMIT_FOR_CHECK')).toBeNull();
  });

  it('⚠️ 变更类动作**存在且可用**（R-12 + R-6 失效）', async () => {
    renderActions('CHECKED');
    await waitFor(() => expect(screen.getByTestId('record-action-INITIATE_CHANGE')).toBeTruthy());
    const btn = screen.getByTestId('record-action-INITIATE_CHANGE');
    expect((btn as HTMLButtonElement).disabled).toBe(false);
  });

  it('⚠️ 角色不够 ⇒ 按钮**禁用** + Tooltip 写明原因（RF-1）', async () => {
    useAuth.setState({ role: 'DESIGNER' });
    renderActions('IN_APPROVAL');
    await waitFor(() => expect(screen.getByTestId('record-action-PASS_CHECK')).toBeTruthy());
    const btn = screen.getByTestId('record-action-PASS_CHECK') as HTMLButtonElement;
    // ⚠️ antd 的 disabled 按钮包在 <span> 里 ⇒ 断言 aria-disabled 更稳
    expect(btn.disabled || btn.getAttribute('aria-disabled') === 'true').toBe(true);
    expect(screen.getByTestId('record-action-PASS_CHECK-hint').textContent).toContain(
      '角色',
    );
  });

  it('⚠️ R-17：送审**没有角色选择器** ⇒ 提交体只有 {reason?}', async () => {
    renderActions('DRAFT');
    await waitFor(() => expect(screen.getByTestId('record-action-SUBMIT_FOR_CHECK')).toBeTruthy());
    fireEvent.click(screen.getByTestId('record-action-SUBMIT_FOR_CHECK'));
    await waitFor(() => expect(recordCalls).toBe(1));
    expect(lastAction).toBe('submit-approval');
    expect(Object.keys(lastBody as object)).not.toContain('approval_role');
    expect(Object.keys(lastBody as object)).not.toContain('approval_depth');
    // ⚠️ **不得**出现角色下拉框
    expect(screen.queryByTestId('record-action-approval-role')).toBeNull();
  });

  it('⚠️ 理由为空 ⇒ 弃用的**确认按钮禁用**（RF-3）', async () => {
    renderActions('DRAFT');
    await waitFor(() => expect(screen.getByTestId('record-action-OBSOLETE')).toBeTruthy());
    fireEvent.click(screen.getByTestId('record-action-OBSOLETE'));
    const ok = await screen.findByTestId('record-action-reason-ok');
    expect((ok as HTMLButtonElement).disabled).toBe(true);
    fireEvent.change(screen.getByTestId('record-action-reason-input'), {
      target: { value: '数据已过期' },
    });
    await waitFor(() =>
      expect((screen.getByTestId('record-action-reason-ok') as HTMLButtonElement).disabled).toBe(false),
    );
  });

  it('⚠️ 矩阵第 1 步的角色 == 当前用户 ⇒ 送审**禁用** + Tooltip（RF-2 / RF-16）', async () => {
    useAuth.setState({ role: 'CHECKER' });
    matrixRoles = ['CHECKER'];
    renderActions('DRAFT');
    await waitFor(() => expect(screen.getByTestId('record-action-SUBMIT_FOR_CHECK')).toBeTruthy());
    await waitFor(() =>
      expect(screen.getByTestId('record-action-SUBMIT_FOR_CHECK-hint').textContent).toContain(
        '自己',
      ),
    );
    const btn = screen.getByTestId('record-action-SUBMIT_FOR_CHECK') as HTMLButtonElement;
    expect(btn.disabled || btn.getAttribute('aria-disabled') === 'true').toBe(true);
  });

  it('⚠️ 项目**没绑** RECORD 矩阵 ⇒ 送审**禁用** + Tooltip（SPEC V2.2 · RF-16）', async () => {
    // ⚠️ **前端知道**（它刚拉过 `GET /projects/{id}/signature-matrices` ⇒ 返回 []
    //    ⇒ 没绑）⇒ 门禁前置（SPEC V2.2）⇒ 后端 422 只是兜底。
    matrixRoles = null;
    renderActions('DRAFT');
    await waitFor(() => expect(screen.getByTestId('record-action-SUBMIT_FOR_CHECK')).toBeTruthy());
    await waitFor(() =>
      expect(screen.getByTestId('record-action-SUBMIT_FOR_CHECK-hint').textContent).toContain(
        '未绑定记录级签署矩阵',
      ),
    );
    const btn = screen.getByTestId('record-action-SUBMIT_FOR_CHECK') as HTMLButtonElement;
    expect(btn.disabled || btn.getAttribute('aria-disabled') === 'true').toBe(true);
  });

  it('⚠️ 角色出现在链里**任一步** ⇒ 送审**禁用**（后端判据是「链里任何一步」）', async () => {
    // ⚠️ 后端 `APPROVAL_SELF_REVIEW_FORBIDDEN` 判的是「提交人自己的角色出现在
    //    链里**任何一步**」⇒ 前端只挡第 1 步 ⇒ APPROVER/REVIEWER 类用户点了
    //    必吃 403（前端与后端判据不一致 ⇒ 门禁失效）。
    // ⚠️ 用 **APPROVER**（链的**第 3 步**）—— REVIEWER 连粗闸都过不了
    //    （`SUBMIT_FOR_CHECK` 的 allowed_roles 不含 REVIEWER）⇒ 不是这条路径。
    useAuth.setState({ role: 'APPROVER' });
    matrixRoles = ['CHECKER', 'REVIEWER', 'APPROVER'];
    renderActions('DRAFT');
    await waitFor(() => expect(screen.getByTestId('record-action-SUBMIT_FOR_CHECK')).toBeTruthy());
    await waitFor(() =>
      expect(screen.getByTestId('record-action-SUBMIT_FOR_CHECK-hint').textContent).toContain(
        '自己',
      ),
    );
    const btn = screen.getByTestId('record-action-SUBMIT_FOR_CHECK') as HTMLButtonElement;
    expect(btn.disabled || btn.getAttribute('aria-disabled') === 'true').toBe(true);
  });

  it('⚠️ 角色**不在**链里 ⇒ 送审可用（DESIGNER 不在 CHECKER/REVIEWER/APPROVER 链上）', async () => {
    useAuth.setState({ role: 'DESIGNER' });
    matrixRoles = ['CHECKER', 'REVIEWER', 'APPROVER'];
    renderActions('DRAFT');
    await waitFor(() => expect(screen.getByTestId('record-action-SUBMIT_FOR_CHECK')).toBeTruthy());
    const btn = screen.getByTestId('record-action-SUBMIT_FOR_CHECK') as HTMLButtonElement;
    expect(btn.disabled || btn.getAttribute('aria-disabled') === 'true').toBe(false);
  });

  it('⚠️ 变更类动作 ⇒ **必须填理由**（后端 `ChangeActionRequest.reason` min_length=1 ⇒ 空理由必 422）', async () => {
    // ⚠️ 此前这三个动作 `reasonRequired: false` ⇒ 前端发 `{"reason": ""}` ⇒
    //    FastAPI 直接 **422** ⇒ 「放弃变更」在 UI 上**永远点不动**。
    renderActions('CHECKED');
    await waitFor(() => expect(screen.getByTestId('record-action-INITIATE_CHANGE')).toBeTruthy());
    fireEvent.click(screen.getByTestId('record-action-INITIATE_CHANGE'));
    const ok = await screen.findByTestId('record-action-reason-ok');
    // ⚠️ 理由为空 ⇒ 确认按钮禁用（前端拦）
    expect((ok as HTMLButtonElement).disabled).toBe(true);
    fireEvent.change(screen.getByTestId('record-action-reason-input'), {
      target: { value: '塔径由 3.0 改为 3.5m' },
    });
    await waitFor(() =>
      expect((screen.getByTestId('record-action-reason-ok') as HTMLButtonElement).disabled).toBe(false),
    );
    fireEvent.click(screen.getByTestId('record-action-reason-ok'));
    await waitFor(() => expect(recordCalls).toBe(1));
    expect(lastAction).toBe('initiate-change');
    // ⚠️ 理由**非空**（后端 min_length=1）
    expect((lastBody as { reason?: string }).reason).toBe('塔径由 3.0 改为 3.5m');
  });

  it('⚠️ meta 请求失败 ⇒ 显示「无法读取状态机定义」（**不是**空白按钮组）', async () => {
    metaStatus = 500;
    renderActions('DRAFT');
    await waitFor(() =>
      expect(screen.getByTestId('record-actions-error').textContent).toContain(
        '无法读取状态机定义',
      ),
    );
  });

  it('⚠️ 双击提交 ⇒ 只发**一次**请求（pending 期间禁用）', async () => {
    renderActions('DRAFT');
    await waitFor(() => expect(screen.getByTestId('record-action-SUBMIT_FOR_CHECK')).toBeTruthy());
    const btn = screen.getByTestId('record-action-SUBMIT_FOR_CHECK');
    fireEvent.click(btn);
    fireEvent.click(btn);
    await waitFor(() => expect(recordCalls).toBe(1));
    await new Promise((r) => setTimeout(r, 50));
    expect(recordCalls).toBe(1);
  });

  it('⚠️ 评审清理：理由弹窗**开着**时动作失败 ⇒ 错误渲染在弹窗**内**（不被遮罩盖住）', async () => {
    server.use(
      http.post('/api/v1/records/:module/:recordId/:action', () =>
        HttpResponse.json(
          { code: 'APPROVAL_SELF_REVIEW_FORBIDDEN', message: '不允许自审' },
          { status: 403 },
        ),
      ),
    );
    renderActions('CHECKED');
    await waitFor(() => expect(screen.getByTestId('record-action-INITIATE_CHANGE')).toBeTruthy());
    fireEvent.click(screen.getByTestId('record-action-INITIATE_CHANGE'));
    const modal = await waitFor(() => document.querySelector('.ant-modal-content'));
    expect(modal).toBeTruthy();
    fireEvent.change(screen.getByTestId('record-action-reason-input'), {
      target: { value: '塔径调整' },
    });
    fireEvent.click(screen.getByTestId('record-action-reason-ok'));
    await waitFor(() =>
      expect(screen.getByTestId('record-actions-error').textContent).toContain(
        'APPROVAL_SELF_REVIEW_FORBIDDEN',
      ),
    );
    // ⚠️ 错误必须**在弹窗里**（外面那份被 Modal 遮罩盖住 ⇒ 用户看不见）
    expect(modal?.contains(screen.getByTestId('record-actions-error'))).toBe(true);
  });

  it('⚠️ 失败**明说**（错误码 + 原文），不静默', async () => {
    server.use(
      http.post('/api/v1/records/:module/:recordId/:action', () =>
        HttpResponse.json(
          { code: 'APPROVAL_SELF_REVIEW_FORBIDDEN', message: '不允许自审' },
          { status: 403 },
        ),
      ),
    );
    renderActions('DRAFT');
    await waitFor(() => expect(screen.getByTestId('record-action-SUBMIT_FOR_CHECK')).toBeTruthy());
    fireEvent.click(screen.getByTestId('record-action-SUBMIT_FOR_CHECK'));
    await waitFor(() =>
      expect(screen.getByTestId('record-actions-error').textContent).toContain(
        'APPROVAL_SELF_REVIEW_FORBIDDEN',
      ),
    );
    expect(screen.getByTestId('record-actions-error').textContent).toContain('不允许自审');
  });

  it('⚠️ 重绑矩阵后**重新挂载**（重开抽屉）⇒ 读到**新链**（评审 #1：链缓存不跨挂载）', async () => {
    // 场景：管理员把项目 RECORD 矩阵重绑成「含当前用户角色」的链 ⇒
    // 已挂载的 SPA 若用模块级永生缓存 ⇒ 重开抽屉仍拿旧链 ⇒ 送审门禁
    // 与后端实际判据不一致（自审 403 变成「前端说能点」）。
    useAuth.setState({ role: 'DESIGNER' });
    matrixRoles = ['CHECKER'];
    const projectId = `project-same-${++projectSeq}`;
    const first = renderActions('DRAFT', projectId);
    await waitFor(() =>
      expect(screen.getByTestId('record-action-SUBMIT_FOR_CHECK')).toBeTruthy(),
    );
    await waitFor(() => {
      const btn = screen.getByTestId('record-action-SUBMIT_FOR_CHECK') as HTMLButtonElement;
      expect(btn.disabled || btn.getAttribute('aria-disabled') === 'true').toBe(false);
    });
    first.unmount();

    // 管理员重绑：DESIGNER 进链 ⇒ 重开（新挂载，同 projectId）必须看到新链
    matrixRoles = ['CHECKER', 'DESIGNER'];
    renderActions('DRAFT', projectId);
    await waitFor(() =>
      expect(screen.getByTestId('record-action-SUBMIT_FOR_CHECK-hint').textContent).toContain(
        '自己',
      ),
    );
    const btn = screen.getByTestId('record-action-SUBMIT_FOR_CHECK') as HTMLButtonElement;
    expect(btn.disabled || btn.getAttribute('aria-disabled') === 'true').toBe(true);
  });
});
