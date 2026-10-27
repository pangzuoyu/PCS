/**
 * mock 保真度（P9B-2 · 延后的 minor · Batch D）。
 *
 * ⚠️ **为什么 mock 也要测**：mock 与真端点**不同源** ⇒ 契约漂移被藏住 ⇒
 *    dev 里**复现不出真实形态** ⇒ 用户以为「后端就这样」⇒ 上线才发现是 mock 的锅。
 *    ⇒ 这里把 mock 的**关键行为**钉死：状态会变、分页会切、枚举合法、段可用性
 *    与后端一致。
 *
 * ⚠️ 语义**照抄后端**（`DeliverableService.sign_step` / `progress_sections`），
 *    不是照抄「页面看起来对不对」。
 */
import { describe, it, expect, beforeAll, afterAll, beforeEach } from 'vitest';
import { setupServer } from 'msw/node';

import { api } from '../../src/api/client';
import { useAuth } from '../../src/store/auth';
import { signFlowHandlers, resetMockSignState } from '../../src/mocks/signFlow';
import { devOnlyMockHandlers } from '../../src/mocks/handlers';
import { signatureMatrixHandlers } from '../../src/mocks/signatureMatrices';
import { metaSeed } from '../../src/mocks/seed/meta';
import { seedDeliverables } from '../../src/mocks/seed/deliverables';
import { seedDeliverableSnapshot } from '../../src/mocks/seed/signFlow';

type ProgressResponse = {
  sections: {
    workflow_type: string;
    workflow_id: string | null;
    available: boolean;
    reason: string | null;
    total: number;
    pending: number;
    in_progress: number;
    completed: number;
    skipped: number;
    failed: number;
    items: {
      step_order: number;
      step_role: string;
      step_status: string;
    }[];
  }[];
};

const server = setupServer(...signFlowHandlers, ...devOnlyMockHandlers, ...signatureMatrixHandlers);

async function postSignStep(body: unknown): Promise<{ status: number; data: Record<string, unknown> }> {
  try {
    const r = await api.post('/deliverables/d-2/sign-step', body);
    return { status: r.status, data: r.data as Record<string, unknown> };
  } catch (err) {
    const e = err as { response?: { status: number; data: Record<string, unknown> } };
    return { status: e.response?.status ?? 0, data: e.response?.data ?? {} };
  }
}

async function getProgress(): Promise<ProgressResponse> {
  const r = await api.get('/deliverables/d-2/progress');
  return r.data as ProgressResponse;
}

function signSection(res: ProgressResponse) {
  const s = res.sections.find((x) => x.workflow_type === 'SIGN');
  if (!s) throw new Error('SIGN 段缺失');
  return s;
}

describe('mock 保真度 —— 签署流程', () => {
  beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
  afterAll(() => server.close());
  beforeEach(() => {
    resetMockSignState();
    useAuth.setState({ role: 'CHECKER', accessToken: 'test-token' });
  });

  it('⚠️ sign-step **真的改状态** ⇒ 之后 progress 显示这一步已完成', async () => {
    const res = await postSignStep({
      version_id: 'v-2',
      step_index: 1,
      decision: 'SIGN',
    });
    expect(res.status).toBe(200);

    const section = signSection(await getProgress());
    // ⚠️ 第 1 步 ⇒ COMPLETED；**下一步 ⇒ IN_PROGRESS**（后端同口径）
    expect(section.items[0]?.step_status).toBe('COMPLETED');
    expect(section.items[1]?.step_status).toBe('IN_PROGRESS');
    expect(section.completed).toBe(1);
    expect(section.in_progress).toBe(1);
    expect(section.pending).toBe(0);
  });

  it('⚠️ 签完**最后一步** ⇒ 交付物 sign_status = APPROVED', async () => {
    await postSignStep({ version_id: 'v-2', step_index: 1, decision: 'SIGN' });
    const res = await postSignStep({ version_id: 'v-2', step_index: 2, decision: 'SIGN' });
    expect(res.status).toBe(200);
    // ⚠️ 最后一步 SIGN ⇒ APPROVED（后端 `sign_step` 同口径）
    expect(res.data['deliverable_sign_status']).toBe('APPROVED');

    const section = signSection(await getProgress());
    expect(section.completed).toBe(2);
    expect(section.in_progress).toBe(0);
  });

  it('⚠️ **越步签** ⇒ 409（后端 409 SIGN_STEP_OUT_OF_ORDER）', async () => {
    // ⚠️ 矩阵的职责分离：复核人不能在设计人没签时先签复核。
    const res = await postSignStep({ version_id: 'v-2', step_index: 2, decision: 'SIGN' });
    expect(res.status).toBe(409);
    expect(res.data['code']).toBe('SIGN_STEP_OUT_OF_ORDER');
  });

  it('⚠️ **退回** ⇒ 交付物回 DRAFT（ADR-0008）', async () => {
    const res = await postSignStep({
      version_id: 'v-2',
      step_index: 1,
      decision: 'RETURN',
      reason: '数据不对',
    });
    expect(res.status).toBe(200);
    expect(res.data['state']).toBe('FAILED');
    expect(res.data['deliverable_sign_status']).toBe('DRAFT');
  });
});

describe('mock 保真度 —— 聚合进度段', () => {
  beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
  afterAll(() => server.close());
  beforeEach(() => {
    resetMockSignState();
    useAuth.setState({ role: 'CHECKER', accessToken: 'test-token' });
  });

  it('⚠️ **代录段恒为 available**（后端：PROXY 段永远可用，SIGN 段才可能不可用）', async () => {
    // ⚠️ 后端 `progress_sections`：PROXY 段的 workflow_id = 交付物 id ⇒
    //    **永远 available=True**；「尚未签发版本，无签署流程」是 **SIGN 段**的
    //    不可用原因（且只在**没有版本**时）⇒ mock 把它挂在 PROXY 段上是错的。
    const res = await getProgress();
    const proxy = res.sections.find((s) => s.workflow_type === 'CUSTOMER_APPROVAL_PROXY');
    expect(proxy).toBeTruthy();
    expect(proxy?.available).toBe(true);
    expect(proxy?.reason).toBeNull();
  });
});

describe('mock 保真度 —— 审计列表分页', () => {
  beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
  afterAll(() => server.close());
  beforeEach(() => {
    useAuth.setState({ role: 'SYSTEM_ADMIN', accessToken: 'test-token' });
  });

  it('⚠️ `/audit-logs` mock **认 limit / offset**（此前恒返回全部 + limit=50）', async () => {
    const all = await api.get('/audit-logs', { params: { limit: 100, offset: 0 } });
    const first = await api.get('/audit-logs', { params: { limit: 1, offset: 0 } });
    const second = await api.get('/audit-logs', { params: { limit: 1, offset: 1 } });

    const allItems = (all.data as { items: unknown[] }).items;
    expect(allItems.length).toBeGreaterThan(1);
    // ⚠️ limit=1 ⇒ **只回 1 条**
    expect((first.data as { items: unknown[] }).items.length).toBe(1);
    // ⚠️ offset=1 ⇒ 第 2 条（**不是**第 1 条）
    expect((second.data as { items: unknown[] }).items[0]).toEqual(allItems[1]);
    // ⚠️ 回显**真实**的 limit / offset（此前恒回 limit=50 offset=0）
    expect((first.data as { limit: number }).limit).toBe(1);
    expect((second.data as { offset: number }).offset).toBe(1);
  });
});

describe('mock 保真度 —— 交付物的矩阵绑定', () => {
  beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
  afterAll(() => server.close());
  beforeEach(() => {
    useAuth.setState({ role: 'SYSTEM_ADMIN', accessToken: 'test-token' });
  });

  it('⚠️ 交付物的 matrix_id 必须是**项目已绑定的**矩阵（否则「签发」永远禁用）', async () => {
    // ⚠️ 前端闸：`boundMatrixIds`（项目绑定）∋ `row.matrix_id` ⇒ matrix_id 为
    //    null ⇒ 「签发」**永远禁用** ⇒ dev 里根本走不到签发流程。
    //    后端 `_assert_matrix_bound` 同口径（按 project_id + matrix_id 查绑定）。
    const r = await api.get('/projects/00000000-0000-0000-0000-000000000001/signature-matrices');
    const boundIds = new Set(
      (r.data as { matrix_id: string }[]).map((i) => i.matrix_id),
    );
    expect(boundIds.size).toBeGreaterThan(0);
    for (const d of seedDeliverables) {
      expect(d.matrix_id).toBeTruthy();
      expect(boundIds.has(d.matrix_id as string)).toBe(true);
    }
  });
});

describe('mock 保真度 —— 枚举合法', () => {
  it('⚠️ seed 的 `sign_status` 必须是**合法枚举**（不是记录的 CHANGE_PENDING）', () => {
    // ⚠️ `DeliverableSignStatus` = DRAFT / PENDING / APPROVED / OBSOLETE（4 态）
    //    ⇒ `CHANGE_PENDING` 是**记录**状态，套到交付物上 ⇒ 前端按 4 态判断时会走错分支。
    const legal = metaSeed.enums.DeliverableSignStatus.map((e) => e.value);
    expect(legal).toEqual(['DRAFT', 'PENDING', 'APPROVED', 'OBSOLETE']);
    for (const d of seedDeliverables) {
      expect(legal).toContain(d.sign_status);
    }
    expect(legal).toContain(seedDeliverableSnapshot.sign_status);
  });
});
