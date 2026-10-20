# P9B-1 实施计划：结果记录页 + 编辑锁前端（SPEC §6.21 / §6.7.1 / §6.22~§6.24）

> **For agentic workers:** REQUIRED SUB-SKILL: `superpowers:executing-plans`
> （或 `superpowers:subagent-driven-development`）。
> ledger: `.superpowers/sdd/PCS-PLAN-P9B-1-结果记录页与编辑锁/progress.md`

**Goal:** 兑现 SPEC §6.21（编辑锁 P9A-LCK-001~006）、§6.7.1（CIA 确认 P9A-CIA-001/002）、
§6.22~§6.24（待办 / 实时状态 / 观测进度）的**前端**，并让 6 个可编辑结果表真正可编辑。

**Architecture:** 「**一个通用结果页 + 6 个类型化模块描述符**」，不是 6 份页面。
差异只有四处（record_type / 路径 / 主键名 / 字段清单），其余（列表 / 编辑抽屉 / 取锁 /
心跳 / 保存 / 409 弹窗）全部共用。字段清单用 **`keyof ResponseType` 约束** ⇒
字段改名 = **编译期错误**，不是运行时静默漂移。

**Tech Stack:** React 18 + TypeScript 5.5 + antd 5 + axios + zustand + vitest + MSW。

**Spec:**
- `docs/PCS-UI-SPEC.md` **V2.1** —— §6.21 / §6.7.1 / §6.20 / §6.22 / §6.23 / §6.24 / §3.2 / §5.2
- `spec/PCS-REQ-2026-002-SPEC-P9 …` **V2.1** §7.2（P9B 验收）、§4.2（前端纪律）
- `docs/adr/0048-edit-lock-storage.md`（两层锁）、`0047`（观测层）、`0049`（通知/待办）

---

## Global Constraints

1. **类型全部来自生成的 `src/types/api.d.ts`**（`components['schemas'][...]`），
   **不手写**（TODO-064 已删 18 个漂移手写类型）。⚠️ `src/types/*.ts` 还有 57 个
   同名手写类型（TODO-064），**本批不碰**（除非要 import）。
2. **mock 必须与真端点同形**：契约端点的 mock 响应体用 **ajv 对着 OpenAPI 校验**
   （`tests/mocks/handlers.test.ts` 已有此模式 + 棘轮清单）。⚠️ mock 与真端点不同源
   ⇒ 漂移被藏住 ⇒ **只有生产构建才炸**（bug-2040，2026-10-21 实测）。
3. **`record_type` 用 `RECORD_TYPE_REGISTRY` 的键**：`CostEstResult` / `FiltrationResult` /
   `OpenChannelResult` / `cooling_tower_result` / `flare_system_result` / `psychro_result`
   —— **不是表名**（3 个是 snake_case）。⚠️ `/locks` **校验**，传错 ⇒ 404。
4. **PATCH 必须带并发基线** `expected_hash`（16 hex，取自响应里的 `record_hash`）。
   不带 ⇒ **409 `basis=no_baseline`**。`cost_est` 无 `updated_at` ⇒ 只有一档基线。
5. **不得自动重试**任何 409（锁续期、保存冲突）—— 重试仍是 409，且把「失效」掩盖成
   「网络抖动」。
6. **失败方向**：拿不到就明说（`unknown` basis、空态、403），**不得**静默降级成
   「无冲突」。
7. 提交约定：conventional commits，**无 attribution 行**。长 commit message 写文件后
   `git commit -F <file>`（`!` `（）` 会被 shell 吃掉）。
8. ⚠️ **不要建 worktree**（本仓历史事故，见 `.wolf/STATUS.md`）。

## Review Focus

以下五条是 SPEC 蕴含、但**任何任务的测试若不专门写就不会覆盖**的输入类/失败模式。
每条都指派给了拥有该代码的任务。

| # | 失败模式 | 期望行为 | 归属 |
|---|---|---|---|
| RF-1 | **保存成功后不刷新基线** —— 编辑会重算 `record_hash`，基线不刷新 ⇒ 下一次保存**必 409**（假冲突） | 保存成功后用响应里的新 `record_hash` 覆盖基线 | T3 |
| RF-2 | **`expected_hash` 漏传** ⇒ 409 `basis=no_baseline`，症状是「保存总是失败」且**不指向漏传** | 请求体必须断言带基线；弹窗按 `no_baseline` 给「刷新后重试」出口 | T1 / T2 |
| RF-3 | **他人持锁** ⇒ 误写成「无权限」 | 只**禁用保存**，浏览 / 复制 / 查看哈希**不阻断**；禁用原因写「谁在改」 | T2 |
| RF-4 | **锁失效（renew 409）** ⇒ 自动重试 | **不重试**，表单转只读，提示「编辑锁已失效，请重新进入编辑」 | T2 |
| RF-5 | **`changed_by` / `changed_at` 为 null** ⇒ 用 `updated_at` 冒充 | 弹窗文案显示「未知」；**不得**拿 `updated_at` 顶替 | T2 |

另有两个 SPEC 明写、但容易被实现者忽略的：

| # | 失败模式 | 期望行为 | 归属 |
|---|---|---|---|
| RF-6 | Redis 降级（`degraded=true`）⇒ 横幅**阻断**编辑 | 横幅**不阻断**（放行的是体验，拦住并发的是 DB 层）；文案取后端 `message` 原文 | T4 |
| RF-7 | `sign_status` 锁定态（CHECKED / IN_APPROVAL …）⇒ 仍显示可编辑 | 编辑按钮**禁用**（前端不等后端 422 才报错） | T3 |

---

## P9B 全景与本批边界

P9 SPEC §4.3/§4.4 的 P9B 共 8 个工作项（7.5–10 人周）。**本计划只做并发控制 +
变更影响确认 + 结果页 + 观测/待办面板**这 4 项（它们互为一套：都吃 P9A-4 D0~D3
的契约）。

| P9B 工作项 | 本批 | 去向 |
|---|---|---|
| 并发控制前端（§6.21 + P9A-LCK-001~006） | ✅ **T2/T3/T4** | — |
| 变更影响分析前端（§6.7.1 确认动作） | ✅ **T4**（组件扩展 + 接线） | 高亮 / 对比另批 |
| 6 类结果记录页 | ✅ **T3** | — |
| workflow_progress 可视化 + 待办 + 实时状态（§6.22~§6.24） | ✅ **T5** | — |
| 签署流程前端（操作栏 / 批注 / 状态时间线） | ❌ | P9B-2（后端 `/records/{module}/{id}/comments` 等已就绪） |
| ADMIN 用户管理前端（`/admin/users` 3 端点已交付） | ❌ | P9B-2 |
| ADMIN 审计日志前端 | ❌ | P9B-2（`AuditLogPage` 已有雏形） |
| ADMIN 系统参数前端 | ❌ | P9B-3 |
| 物流手动创建向导 + 校对 UI | ❌ | P9B-3 |

⚠️ **本批不做签署流程前端** ⇒ T5 的 `WorkflowProgressPanel` **没有宿主页面**
（`/workflow-progress/{type}/{id}` 要挂在交付物/版本页上，而那页属 P9B-2）。
⇒ 本批交付**组件 + 测试**，宿主接线留 P9B-2。**不为此新建空页面。**

---

## 事实基础（2026-10-21 实测，非推断）

**后端契约**（`pcs-backend`，OpenAPI 已冻结在 `p9_007`）：

| 模块 | 列表路径 | 主键 | record_type | PATCH 请求体 | 响应 |
|---|---|---|---|---|---|
| cool_tower | `/cool-tower/results` | `id` | `cooling_tower_result` | `CoolTowerResultUpdateRequest` | `CoolTowerResultResponse` |
| filtration | `/filtration/results` | `result_id` | `FiltrationResult` | `FiltrationUpdateRequest` | `FiltrationResultResponse` |
| flare | `/flare/results` | `id` | `flare_system_result` | `FlareResultUpdateRequest` | `FlareResultResponse` |
| open_channel | `/open-channel/results` | `result_id` | `OpenChannelResult` | `OpenChannelUpdateRequest` | `OpenChannelResultResponse` |
| psychro | `/psychro/results` | `id` | `psychro_result` | `PsychroResultUpdateRequest` | `PsychroResultResponse` |
| cost_est | `/cost-est/results` | `result_id` | `CostEstResult` | `CostEstUpdateRequest` | `CostEstResultResponse` |

- 6 个 `*UpdateRequest` **都有** `expected_hash` + `expected_updated_at`。
- 6 个响应**都有** `record_hash`（16 hex）；**只有 `cost_est` 没有 `updated_at`**。
- 列表：`GET ?project_id=`（**必填**）+ 分页。返回信封有**两种**：
  `{items,total,limit,offset}`（cool-tower / flare / psychro）与
  `{items,total,skip,limit}`（filtration / open-channel / cost-est）⇒
  **只读 `items` + `total`**，分页字段名差异不消费。
- 列表项 = 详情响应（同 schema），所以**不需要单独的 GET 详情**也能拿到 `record_hash`；
  详情用 `GET /{base}/{id}`（存在）。
- **可编辑状态只有 `DRAFT` / `CHANGE_PENDING`**（后端
  `*_PERSIST_SIGN_STATUS_LOCKED`），其余 7 态后端拒改。
- 409 响应体 = 仓库统一信封 `{code, message, detail, trace_id}`，冲突对象在
  `detail.conflict`，`basis` ∈ `record_hash` / `updated_at` / `no_baseline`。
- `/locks/{rt}/{id}/acquire|renew|release`：`200 + success` / `409`（**他人持锁**，
  响应体仍是 `LockResponse`，带 `holder`）/ `200 + degraded=true`（Redis 挂了）。
  ⚠️ `/locks` **校验** `record_type` ⇒ 传表名 **404**。

**前端现状**：

- 已有：`src/api/locks.ts`（`editLockApi` + `EDITABLE_RECORD_TYPES`）、
  `src/api/changeImpact.ts`、`src/api/errors.ts`（`extractConflict` / `conflictKind`）、
  `src/api/notifications.ts`、`src/api/todos.ts`（2026-10-21 新增）。
  ⚠️ `locks.ts` 里**只有** `editRecordApi.patchCostEst` 一个 PATCH。
- **6 个结果页一个都没有**：无路由、无 Page、无列表调用；`src/` 里 **0 个 PATCH 调用**。
- 可复用：`useAuth`（`userId` 由后端 `/auth/me` 给，**不得**前端派生）、
  `api` 实例、`PageHeader` / `HashBadge` / `StateBadge` / `NumericCell` / `ModuleLayout` /
  `ChangeImpactPanel` / `PageHeader`。
- 既有范式：请求契约测试用 MSW `setupServer` + 闭包捕获（`tests/api/edit_lock_api.test.ts`）。
- ⚠️ `tsconfig.json` 把 `tests/` 纳入类型检查 ⇒ 测试 fixture 也必须类型正确。

---

## 文件结构

**新建**（8 个）：

| 文件 | 职责 |
|---|---|
| `src/api/records.ts` | 6 模块的 list / get / patch（**patch 必带 `expected_hash`**） |
| `src/hooks/useEditLock.ts` | 取锁 → 60s 心跳 → 失效转只读 |
| `src/components/common/EditLockIndicator.tsx` | 锁状态三态（可编辑 / 他人持锁 / 降级） |
| `src/components/common/EditConflictModal.tsx` | 409 弹窗，按 `basis` 三值分流 |
| `src/pages/results/resultModules.ts` | 6 个模块的**类型化描述符**（唯一字段清单来源） |
| `src/pages/results/ResultListPage.tsx` | 通用列表页（描述符驱动） |
| `src/pages/results/ResultEditDrawer.tsx` | 通用编辑抽屉（锁 + 表单 + 保存 + 409） |
| `src/components/common/WorkflowProgressPanel.tsx` | §6.24 观测进度面板 |

**修改**（5 个）：

| 文件 | 改什么 |
|---|---|
| `src/api/audit.ts` | 加 `listRecordEdits`（`changed_fields` 来自编辑审计） |
| `src/components/common/ChangeImpactPanel.tsx` | 扩展 props：系统判定 `confirm` + 人工判定 `manual-adjust` |
| `src/store/degradation.ts`（新，zustand） | 降级横幅的全局状态（跨组件：顶栏 + 编辑抽屉） |
| `src/layouts/MainLayout.tsx` | 顶栏降级横幅 + 6 条新菜单项 |
| `src/App.tsx` | 6 条新路由 |
| `src/mocks/handlers.ts` | 6 模块的 list/detail/patch mock（契约形状）+ `/todos`（已有） |

---

## Task T1：记录 api 层（6 模块 list / get / patch）+ 编辑审计

**Files:**
- Create: `pcs-frontend/src/api/records.ts`
- Modify: `pcs-frontend/src/api/audit.ts`
- Test: `pcs-frontend/tests/api/records_api.test.ts`

**Interfaces:**
- Consumes: `components['schemas'][...]`（生成的契约类型）
- Produces:
  ```ts
  export type EditableRecordType = 'CostEstResult' | 'FiltrationResult'
    | 'OpenChannelResult' | 'cooling_tower_result' | 'flare_system_result'
    | 'psychro_result';

  /** 并发基线（SPEC §6.21 P9A-LCK-006）。expected_hash 必填。 */
  export interface PatchBaseline {
    expected_hash: string;
    expected_updated_at?: string;
  }

  export const recordsApi: {
    list<TList>(base: string, params: { project_id: string; limit?: number; offset?: number }): Promise<TList>;
    get<TRes>(base: string, id: string): Promise<TRes>;
    patch<TRes>(base: string, id: string, body: PatchBaseline & Record<string, unknown>): Promise<TRes>;
  };
  ```
  `base` 取 6 个基址之一：`'/cool-tower/results'` 等（**含 `/results` 后缀**）。

- [ ] **Step 1：写失败测试** `tests/api/records_api.test.ts`（MSW `setupServer`）

  ```ts
  const server = setupServer(
    http.get('/api/v1/cost-est/results', () => HttpResponse.json({
      items: [{ result_id: 'r1', record_hash: 'a3f9c21d8b7e6f50' }],
      total: 1, skip: 0, limit: 50,
    })),
    http.patch('/api/v1/cost-est/results/:id', async ({ request }) => {
      lastBody = await request.json();
      return HttpResponse.json({ result_id: 'r1', record_hash: 'ffffffffffffffff' });
    }),
  );

  it('PATCH 必须带 expected_hash —— 漏了后端一律 409，而症状是「保存总是失败」', async () => {
    await recordsApi.patch('/cost-est/results', 'r1', {
      expected_hash: 'a3f9c21d8b7e6f50', estimated_cost: 35,
    } as never);
    expect((lastBody as { expected_hash: string }).expected_hash).toBe('a3f9c21d8b7e6f50');
  });

  it('列表必须带 project_id（后端 422；前端类型层也强制必填）', async () => {
    await recordsApi.list('/cost-est/results', { project_id: 'p1' });
    expect(lastListUrl).toContain('project_id=p1');
    // ⚠️ 漏传是**编译期**错误（params 的 project_id 必填）⇒ 不写运行时断言
  });
  ```

- [ ] **Step 2：跑测试确认失败**
  `npx vitest run tests/api/records_api.test.ts` ⇒ **FAIL**：`recordsApi` 不存在。

- [ ] **Step 3：实现 `src/api/records.ts`**

  ```ts
  import { api } from './client';
  import { EDITABLE_RECORD_TYPES } from './locks';

  /** ⚠️ **不新造词表** —— `record_type` 的唯一清单在 `locks.ts`
   * （`EDITABLE_RECORD_TYPES`）。本仓已因「同一概念两份清单」付过多次代价
   * （TODO-055 / 058 / 060 / 062）⇒ 这里只**派生**。 */
  export type EditableRecordType = (typeof EDITABLE_RECORD_TYPES)[number];

  export interface PatchBaseline { expected_hash: string; expected_updated_at?: string; }

  /** 6 个基址（**含 /results 后缀**；不是表名）。
   *  ⚠️ 类型是 `Record<EditableRecordType, string>` ⇒ 少一个 = **编译期错误**。 */
  export const RESULT_BASES: Record<EditableRecordType, string> = {
    CostEstResult: '/cost-est/results',
    FiltrationResult: '/filtration/results',
    OpenChannelResult: '/open-channel/results',
    cooling_tower_result: '/cool-tower/results',
    flare_system_result: '/flare/results',
    psychro_result: '/psychro/results',
  };

  export const recordsApi = {
    list: <TList>(base: string, params: { project_id: string; limit?: number; offset?: number }) =>
      api.get<TList>(base, { params }).then((r) => r.data),
    get: <TRes>(base: string, id: string) =>
      api.get<TRes>(`${base}/${id}`).then((r) => r.data),
    patch: <TRes>(base: string, id: string, body: PatchBaseline & Record<string, unknown>) =>
      api.patch<TRes>(`${base}/${id}`, body).then((r) => r.data),
  };
  ```

  ⚠️ **`patch` 的返回类型是「更新后的记录」**（含**新的** `record_hash`）⇒
  T3 保存成功后必须用它刷新基线（RF-1）。
  ⚠️ `list` 的 `project_id` 是**类型必填**（后端 422）⇒ 漏传是编译期错误，
  不靠运行时校验。

- [ ] **Step 4：`src/api/audit.ts` 加编辑审计查询**

  ```ts
  /** 编辑审计（SPEC §6.21 P9A-LCK-006「查看差异」的来源）。 */
  export function listRecordEdits(params: { resource_type: string; resource_id: string; limit?: number }) {
    return api.get<AuditLogListResponse>('/audit-logs', { params }).then((r) => r.data);
  }
  ```
  ⚠️ **`/audit-logs` 是 SYSTEM_ADMIN only**（后端 `app/api/v1/audit.py:58`
  `require_roles(user, "SYSTEM_ADMIN")`）⇒ 非管理员 **403**。
  ⇒ T2 的弹窗必须**优雅降级**（见 T2 Step 4），本批**不新增后端端点**
  （登记 TODO，见「尚未解决」）。

- [ ] **Step 5：跑测试确认通过** ⇒ **PASS**（≥3 例）

- [ ] **Step 6：提交**
  ```bash
  git add pcs-frontend/src/api/records.ts pcs-frontend/src/api/audit.ts pcs-frontend/tests/api/records_api.test.ts
  git commit -m "feat(P9B): 6 个结果模块的 list/get/patch api 层（patch 必带 expected_hash）"
  ```

---

## Task T2：编辑锁 hook + 锁指示器 + 409 弹窗

**Files:**
- Create: `pcs-frontend/src/hooks/useEditLock.ts`
- Create: `pcs-frontend/src/components/common/EditLockIndicator.tsx`
- Create: `pcs-frontend/src/components/common/EditConflictModal.tsx`
- Test: `pcs-frontend/tests/hooks/useEditLock.test.tsx`、`tests/components/common/EditLockIndicator.test.tsx`、`tests/components/common/EditConflictModal.test.tsx`

**Interfaces:**
- Consumes: `editLockApi`（`src/api/locks.ts`）、`extractConflict` / `conflictKind`
  （`src/api/errors.ts`）、`listRecordEdits`（T1）
- Produces:
  ```ts
  export type EditLockState =
    | { status: 'idle' }
    | { status: 'held'; ttlSeconds: number }
    | { status: 'blocked'; holder: LockHolderResponse }   // 他人持锁 ⇒ 只读
    | { status: 'expired' }                                // renew 409 ⇒ 只读
    | { status: 'degraded'; message: string | null };      // Redis 挂了 ⇒ 可编辑

  export function useEditLock(args: {
    recordType: EditableRecordType;
    recordId: string;
    enabled: boolean;                 // 进入编辑态才取锁
    onDegraded?: (message: string | null) => void;
  }): {
    state: EditLockState;
    readOnly: boolean;                // blocked / expired ⇒ true
    release: () => Promise<void>;
  };
  ```

- [ ] **Step 1：写失败测试 —— hook**（`vi.useFakeTimers()`）

  ```ts
  it('取锁成功后每 60s 续期一次', async () => {
    vi.useFakeTimers();
    const renew = vi.spyOn(editLockApi, 'renew');
    renderHook(() => useEditLock({ recordType: 'CostEstResult', recordId: 'r1', enabled: true }));
    await act(async () => { await vi.advanceTimersByTimeAsync(60_000); });
    expect(renew).toHaveBeenCalledTimes(1);
  });

  it('续期 409 ⇒ 转只读，且**不重试**（重试仍是 409，且掩盖失效事实）', async () => {
    vi.useFakeTimers();
    vi.spyOn(editLockApi, 'renew').mockResolvedValue({ ...LOCK_409 } as never);
    const { result } = renderHook(() => useEditLock({
      recordType: 'CostEstResult', recordId: 'r1', enabled: true }));
    await act(async () => { await vi.advanceTimersByTimeAsync(60_000); });
    expect(result.current.state.status).toBe('expired');
    expect(result.current.readOnly).toBe(true);
    expect(editLockApi.renew).toHaveBeenCalledTimes(1);   // ← 关键：没有第二次
  });

  it('取锁 409（他人持锁）⇒ blocked + readOnly，holder 取后端原文', async () => {
    vi.spyOn(editLockApi, 'acquire').mockResolvedValue({ success: false, holder: { user_id: 'u2', username: '张三', acquired_at: '...' } } as never);
    const { result } = renderHook(() => useEditLock({
      recordType: 'CostEstResult', recordId: 'r1', enabled: true }));
    await waitFor(() => expect(result.current.state.status).toBe('blocked'));
    expect(result.current.readOnly).toBe(true);
  });

  it('degraded=true ⇒ 可编辑（体验层失效，不是保护层）', async () => {
    vi.spyOn(editLockApi, 'acquire').mockResolvedValue({ success: true, degraded: true, message: '锁服务不可用，保存时可能冲突；本次编辑无冲突检测' } as never);
    const { result } = renderHook(() => useEditLock({
      recordType: 'CostEstResult', recordId: 'r1', enabled: true }));
    await waitFor(() => expect(result.current.state.status).toBe('degraded'));
    expect(result.current.readOnly).toBe(false);
  });
  ```

- [ ] **Step 2：跑测试确认失败** ⇒ **FAIL**：`useEditLock` 不存在。

- [ ] **Step 3：实现 `src/hooks/useEditLock.ts`**

  ```ts
  export function useEditLock({ recordType, recordId, enabled, onDegraded }: Args) {
    const [state, setState] = useState<EditLockState>({ status: 'idle' });

    useEffect(() => {
      if (!enabled) return;
      let cancelled = false;
      void editLockApi.acquire(recordType, recordId).then((res) => {
        if (cancelled) return;
        if (res.degraded) { setState({ status: 'degraded', message: res.message ?? null }); onDegraded?.(res.message ?? null); return; }
        if (!res.success && res.holder) { setState({ status: 'blocked', holder: res.holder }); return; }
        setState({ status: 'held', ttlSeconds: res.ttl_seconds });
      }).catch(() => { if (!cancelled) setState({ status: 'degraded', message: null }); });

      const timer = setInterval(() => {
        void editLockApi.renew(recordType, recordId).then((res) => {
          if (cancelled) return;
          if (!res.success) { setState({ status: 'expired' }); return; }   // ⚠️ 不重试
          if (res.degraded) { setState({ status: 'degraded', message: res.message ?? null }); onDegraded?.(res.message ?? null); }
        }).catch(() => { if (!cancelled) setState({ status: 'expired' }); });
      }, 60_000);                                                   // ⚠️ 60s，不是 55s

      return () => { cancelled = true; clearInterval(timer); };
    }, [recordType, recordId, enabled]);

    // ⚠️ **不自动 release**：30min TTL 会回收；页面关闭不要求显式释放（SPEC §6.21 P9A-LCK-002）。
    // 正常离开（抽屉关闭）可调 release —— 由调用方决定。
    const release = async () => {
      await editLockApi.release(recordType, recordId).catch(() => {/* 非持有者 409，忽略 */});
    };

    return {
      state,
      readOnly: state.status === 'blocked' || state.status === 'expired',
      release,
    };
  }
  ```

- [ ] **Step 4：实现 `EditLockIndicator.tsx`**（三态）

  ```tsx
  interface Props { state: EditLockState; }
  ```
  - `held` ⇒ 不渲染（或渲染一个「已锁定编辑」的灰字）
  - `blocked` ⇒ **「{holder.username || holder.user_id} 正在编辑（{相对时间}）」**
    ⚠️ **禁用原因写「谁在改」，不写「无权限」**（RF-3）；holder 取后端原文，不猜不缓存。
  - `expired` ⇒ 「编辑锁已失效，请重新进入编辑」
  - `degraded` ⇒ 不在指示器里显示（横幅在顶栏，T4）

- [ ] **Step 5：实现 `EditConflictModal.tsx`**（按 `basis` 三值分流）

  | basis | 文案 | 出口 |
  |---|---|---|
  | `record_hash` | 「{changed_by} 于 {changed_at} 修改了这条记录」 | [查看差异] / [放弃我的修改并刷新] |
  | `updated_at` | 同上（只知道行被改过） | 同上 |
  | `no_baseline` | 「无法校验这条记录是否被他人修改」 | [刷新后重试] / [联系管理员] |
  | `unknown`（`conflictKind` 兜底） | 「说不清是否冲突」 | [刷新后重试] |

  ⚠️ **RF-5**：`changed_by` / `changed_at` 为 null ⇒ 显示「未知」，**不得**用 `updated_at` 冒充。
  ⚠️ **不得自动重试**（不轮询、不重发）。
  ⚠️ [查看差异] ⇒ 调 `listRecordEdits`；**403 时**（非 SYSTEM_ADMIN）显示
  「无权查看差异（需系统管理员）」并**保留** [放弃我的修改并刷新] 出口。

- [ ] **Step 6：跑测试确认通过** ⇒ hook 4 例 + 指示器 3 例 + 弹窗 5 例 **PASS**

- [ ] **Step 7：提交**
  ```bash
  git commit -m "feat(P9B): 编辑锁 hook + 锁指示器 + 409 冲突弹窗（按 basis 三值分流）"
  ```

---

## Task T3：通用结果页 + 6 个模块描述符 + 6 条路由

**Files:**
- Create: `src/pages/results/resultModules.ts`、`ResultListPage.tsx`、`ResultEditDrawer.tsx`
- Modify: `src/App.tsx`、`src/layouts/MainLayout.tsx`（菜单）、`src/mocks/handlers.ts`
- Test: `tests/pages/results/result_page.test.tsx`、`tests/mocks/handlers.test.ts`

**Interfaces:**
- Consumes: `recordsApi` + `RESULT_BASES`（T1）、`useEditLock` / `EditLockIndicator` /
  `EditConflictModal`（T2）
- Produces:
  ```ts
  // src/pages/results/resultModules.ts
  import type { components } from '../../types/api';

  /** 6 个响应**共有**的字段（实测：project_id / workspace_id / tag_number /
   *  sign_status / record_hash / created_at 全有；updated_at 只有 cost_est 没有）。 */
  export interface CommonResultRow {
    project_id: string;
    workspace_id: string;
    tag_number: string | null;
    sign_status: string;
    record_hash: string;
    created_at: string;
    updated_at?: string | null;
  }

  export interface ResultFieldDef { key: string; label: string; unit?: string; precision?: number; }

  export interface ResultModuleDef<TRes extends CommonResultRow> {
    recordType: EditableRecordType;
    base: string;                        // = RESULT_BASES[recordType]
    pk: 'id' | 'result_id';              // ⚠️ 各不相同（实测）
    route: string;
    title: string;
    columns: ResultFieldDef[];
    /** ⚠️ **只放标量业务字段**：`*_json` 与后端计算字段（`pass`）**不进表单**
     *  （后端仍接受，但前端不给「编辑计算产物」的入口）。 */
    editableFields: readonly (keyof TRes & string)[];
  }

  /** 6 个模块各自带**自己的**响应类型 ⇒ `editableFields` 里拼错字段 = 编译期错误。
   *  （各模块的完整定义见下方 Step 3 的表 + 示例） */
  export const COST_EST_MODULE: ResultModuleDef<components['schemas']['CostEstResultResponse']>;
  export const FILTRATION_MODULE: ResultModuleDef<components['schemas']['FiltrationResultResponse']>;
  export const FLARE_MODULE: ResultModuleDef<components['schemas']['FlareResultResponse']>;
  export const OPEN_CHANNEL_MODULE: ResultModuleDef<components['schemas']['OpenChannelResultResponse']>;
  export const PSYCHRO_MODULE: ResultModuleDef<components['schemas']['PsychroResultResponse']>;
  export const COOLING_TOWER_MODULE: ResultModuleDef<components['schemas']['CoolTowerResultResponse']>;

  export const RESULT_MODULES = [
    COST_EST_MODULE, FILTRATION_MODULE, FLARE_MODULE,
    OPEN_CHANNEL_MODULE, PSYCHRO_MODULE, COOLING_TOWER_MODULE,
  ] as const;
  export type ResultModule = (typeof RESULT_MODULES)[number];
  ```

- [ ] **Step 1：写失败测试** `tests/pages/results/result_page.test.tsx`

  ```ts
  it('列表渲染：位号 + record_hash + 状态徽章', async () => {
    render(<ResultListPage module={COST_EST_MODULE} />);
    expect(await screen.findByText('P-101')).toBeTruthy();
    expect((await screen.findByTestId('result-hash-cell')).textContent).toContain('a3f9');
    expect((await screen.findByTestId('result-status-cell')).textContent).toContain('DRAFT');
  });

  it('打开编辑 ⇒ 请求体带 expected_hash（取自列表里的 record_hash）', async () => {
    render(<ResultListPage module={COST_EST_MODULE} />);
    fireEvent.click(await screen.findByTestId('result-edit-btn'));
    fireEvent.change(await screen.findByTestId('field-estimated_cost'), { target: { value: '35' } });
    fireEvent.click(screen.getByTestId('result-save-btn'));
    await waitFor(() => expect(lastPostedBody).toBeTruthy());
    expect(lastPostedBody.expected_hash).toBe('a3f9c21d8b7e6f50');   // ← RF-2 的核心断言
  });

  it('保存成功 ⇒ 基线刷新为**响应里的新 record_hash**（RF-1）', async () => {
    // PATCH mock 返回 record_hash='ffffffffffffffff'
    render(<ResultListPage module={COST_EST_MODULE} />);
    fireEvent.click(await screen.findByTestId('result-edit-btn'));
    fireEvent.click(screen.getByTestId('result-save-btn'));
    await waitFor(() => expect(lastPostedBody).toBeTruthy());
    fireEvent.click(screen.getByTestId('result-save-btn'));      // 再存一次
    await waitFor(() => expect(lastPostedBody.expected_hash).toBe('ffffffffffffffff'));
    // ⚠️ 不刷新基线 ⇒ 第二次仍发旧 hash ⇒ 必 409（假冲突）
  });

  it('409 ⇒ 弹窗按 basis 分流（三种 basis 三套文案 + 出口）', async () => {
    for (const [basis, expected] of [
      ['record_hash', '修改了这条记录'],
      ['updated_at', '修改了这条记录'],
      ['no_baseline', '无法校验这条记录是否被他人修改'],
    ] as const) {
      server.use(http.patch('/api/v1/cost-est/results/:id', () =>
        HttpResponse.json({ code: 'RECORD_EDIT_CONFLICT', message: '该记录无法安全保存，请刷新后重新编辑',
          detail: { conflict: { record_type: 'CostEstResult', record_id: 'r1', basis,
            your_expected_hash: 'a3f9c21d8b7e6f50', current_hash: 'bbbbbbbbbbbbbbbb',
            changed_by: 'u2', changed_at: '2026-10-20T10:00:00Z' } }, trace_id: 't1' },
          { status: 409 })));
      render(<ResultListPage module={COST_EST_MODULE} />);
      fireEvent.click(await screen.findByTestId('result-edit-btn'));
      fireEvent.click(screen.getByTestId('result-save-btn'));
      expect(await screen.findByTestId('edit-conflict-modal')).toBeTruthy();
      expect(screen.getByTestId('edit-conflict-modal').textContent).toContain(expected);
    }
    // ⚠️ no_baseline 的出口是「刷新后重试」，record_hash 的是「查看差异」
  });

  it('sign_status=CHECKED ⇒ 编辑按钮禁用（RF-7）', async () => {
    render(<ResultListPage module={COST_EST_MODULE} />);   // mock 返回 sign_status=CHECKED
    const btn = await screen.findByTestId('result-edit-btn');
    expect((btn as HTMLButtonElement).disabled).toBe(true);
  });

  it('他人持锁 ⇒ 只禁用保存，浏览 / 复制 / 查看哈希仍可用（RF-3）', async () => {
    // /locks/acquire 返回 409 + holder
    render(<ResultListPage module={COST_EST_MODULE} />);
    fireEvent.click(await screen.findByTestId('result-edit-btn'));
    expect(await screen.findByTestId('edit-lock-indicator')).toHaveTextContent('张三 正在编辑');
    expect((screen.getByTestId('result-save-btn') as HTMLButtonElement).disabled).toBe(true);
    // ⚠️ 哈希仍可读、可复制（不阻断浏览）
    expect(screen.getByTestId('result-hash-cell')).toBeTruthy();
  });
  ```

- [ ] **Step 2：跑测试确认失败** ⇒ **FAIL**：页面不存在。

- [ ] **Step 3：实现 `resultModules.ts`（唯一字段清单来源）**

  6 个模块的 `editableFields`（**逐字取自各模块 `*UpdateRequest` 的标量字段**，
  已排除 `expected_hash` / `expected_updated_at` / `*_json` / 计算字段 `pass`）：

  | 模块 | `pk` | `editableFields` |
  |---|---|---|
  | CostEstResult | `result_id` | `estimated_cost` `currency` `cost_index_year` `base_cost` `base_year` `cepci_index_base` `cepci_index_target` `correlation_source` `scaling_exponent` |
  | FiltrationResult | `result_id` | `filter_type` `media_type` `area` `cycle_time` `pressure_drop` `cake_resistance_alpha` `specific_resistance_r0` `permeability_k` `porosity_eps` `filter_velocity` |
  | FlareSystemResult | `id` | `calc_type` `total_relief_load_kg_h` `header_diameter_mm` `header_mach` `header_pressure_drop_kpa` `kod_diameter_mm` `water_seal_height_mm` `stack_height_m` `stack_diameter_m` `radiation_at_grade_kw_m2` `radiation_limit_kw_m2` `flare_tip_diameter_mm` `steam_for_smokeless_kg_h` |
  | OpenChannelResult | `result_id` | `channel_type` `flow_rate` `depth` `velocity` `slope` `critical_depth` `froude_number` `manning_n` `hydraulic_radius` `jump_type` `conjugate_depth` `energy_loss` |
  | PsychroResult | `id` | `humidity_ratio_kg_kg` `dew_point_c` `wet_bulb_c` `enthalpy_kj_kg` `specific_volume_m3_kg` `sensible_heat_kw` `latent_heat_kw` `saturation_w_kg_kg` `saturation_w_mg_sm3` `saturation_w_lb_per_mmscf` `saturation_T_c` |
  | CoolingTowerResult | `id` | `tower_type` `duty_kw` `water_flow_m3h` `makeup_water_m3h` `fan_power_kw` `merkel_integral` |

  ```ts
  export const COST_EST_MODULE: ResultModuleDef<components['schemas']['CostEstResultResponse']> = {
    recordType: 'CostEstResult',
    base: RESULT_BASES.CostEstResult,
    pk: 'result_id',
    route: '/results/cost-est',
    title: '造价估算结果',
    columns: [
      { key: 'tag_number', label: '位号' },
      { key: 'estimated_cost', label: '估算造价', unit: '万元' },
      { key: 'currency', label: '币种' },
    ],
    editableFields: ['estimated_cost', 'currency', 'cost_index_year', 'base_cost', 'base_year',
                      'cepci_index_base', 'cepci_index_target', 'correlation_source', 'scaling_exponent'],
  };
  ```
  ⚠️ **每个模块单独一个 const、各带自己的响应类型** ⇒ `editableFields` 里
  拼错字段 = **编译期错误**。
  ⚠️ `columns` / `editableFields` **只在这里写一次**；页面不硬编码字段。

- [ ] **Step 4：实现 `ResultListPage.tsx`（描述符驱动）**

  - `useState` 列表 + `useEffect` 拉 `recordsApi.list(base, { project_id: PROJECT_ID })`
    （`PROJECT_ID` 取 `src/constants/env.ts`）
  - antd `Table`：`columns` 由描述符生成；`record_hash` 列用 `HashBadge`；
    `sign_status` 列用 `StateBadge`；数值列用 `NumericCell`
  - 每行 [编辑] 按钮 ⇒ 打开 `ResultEditDrawer`
  - ⚠️ **只消费 `items` + `total`**（分页字段名两种，信封不统一）

- [ ] **Step 5：实现 `ResultEditDrawer.tsx`**

  ```tsx
  interface Props {
    open: boolean;
    module: ResultModule;
    record: CommonResultRow & Record<string, unknown>;
    onClose: () => void;
    onSaved: (updated: { record_hash: string }) => void;   // ⚠️ 父级用它刷新基线
  }
  ```
  流程：
  1. `const lock = useEditLock({ recordType: module.recordType, recordId: rowId, enabled: open })`
  2. 顶部 `<EditLockIndicator state={lock.state} />`
  3. 表单：字段由 `module.editableFields` 渲染（`InputNumber` / `Input`）
  4. 保存：`recordsApi.patch(base, id, { ...changed, expected_hash: baseline })`
     ⇒ `baseline` 来自 `record.record_hash`
  5. 成功 ⇒ `onSaved({ record_hash: res.record_hash })`（**RF-1**）+ `message.success`
  6. 409 ⇒ `extractConflict(err)` ⇒ 打开 `EditConflictModal`
     ⇒ ⚠️ **不自动重试**
  7. `lock.readOnly` ⇒ 禁用「保存」按钮（**只禁保存**，不禁浏览）

- [ ] **Step 6：接 6 条路由 + 菜单**

  `src/App.tsx`：
  ```tsx
  { path: 'results/cool-tower', element: <ResultListRoute module="cooling_tower_result" /> },
  { path: 'results/filtration', element: <ResultListRoute module="FiltrationResult" /> },
  { path: 'results/flare', element: <ResultListRoute module="flare_system_result" /> },
  { path: 'results/open-channel', element: <ResultListRoute module="OpenChannelResult" /> },
  { path: 'results/psychro', element: <ResultListRoute module="psychro_result" /> },
  { path: 'results/cost-est', element: <ResultListRoute module="CostEstResult" /> },
  ```
  `src/layouts/MainLayout.tsx`：菜单加一组「结果记录」（6 项）。

- [ ] **Step 7：mock（契约形状 + ajv 校验）**

  `src/mocks/handlers.ts` 加 6 个 `GET /{base}`（返回 `{items, total, limit, offset}` 或
  `{items, total, skip, limit}`（按各模块真实信封），条目用
  **契约 Response 的字段**，含 `record_hash`）+ 6 个 `PATCH /{base}/:id`（回
  `record_hash` 新的值）。
  ⚠️ `tests/mocks/handlers.test.ts` 的**棘轮清单**（`devOnly ∩ 契约`）必须同步更新
  —— 新增即红是**预期**（照着红更新清单 + 加 ajv 校验）。

- [ ] **Step 8：跑测试确认通过** ⇒ **PASS**（≥6 例）+ `tests/mocks/handlers.test.ts` 绿

- [ ] **Step 9：提交**
  ```bash
  git commit -m "feat(P9B): 通用结果页 + 6 个类型化模块描述符 + 6 条路由（编辑带基线）"
  ```

---

## Task T4：降级横幅 + ChangeImpactPanel 的「确认」动作

**Files:**
- Create: `src/store/degradation.ts`
- Modify: `src/layouts/MainLayout.tsx`、`src/components/common/ChangeImpactPanel.tsx`、
  `src/pages/sim/StreamDetailPage.tsx`
- Test: `tests/components/common/ChangeImpactPanel.test.tsx`、`tests/layouts/MainLayout.test.tsx`

**Interfaces:**
- Consumes: `changeImpactApi.confirm` / `.manualAdjust`（`src/api/changeImpact.ts`）、
  `useEditLock` 的 `onDegraded`（T2）
- Produces:
  ```ts
  // src/store/degradation.ts（zustand）
  export const useDegradation = create<{
    message: string | null;
    setMessage: (m: string | null) => void;
  }>(() => ({ message: null, setMessage: () => {} }));
  ```
  ```ts
  // ChangeImpactPanel 新增 props（**旧的 onConfirmRecalc 保留不动**）
  interface Props {
    changeSource: ChangeSource;                        // 既有，不动
    affectedRecords: AffectedRecord[];                 // 既有，不动
    onConfirmRecalc?: (recordIds: string[]) => void;   // ⚠️ 指向**另一个端点** confirm-recalc
    onConfirmSystem?: (recordType: string, recordId: string) => Promise<void>;  // 系统判定
    onManualAdjust?: (recordType: string, recordId: string,
                      decision: 'NO_CHANGE' | 'CHANGED', reason: string) => Promise<void>;
  }
  ```

- [ ] **Step 1：写失败测试**

  ```ts
  it('degraded ⇒ 顶栏出现橙色横幅，且**不阻断**编辑（RF-6）', async () => {
    // /locks/acquire 返回 degraded=true
    render(<MemoryRouter><MainLayout /></MemoryRouter>);
    expect(await screen.findByTestId('degradation-banner')).toBeTruthy();
    // ⚠️ 横幅**不阻断**：编辑按钮仍可用
    expect((await screen.findByTestId('result-edit-btn') as HTMLButtonElement).disabled).toBe(false);
  });

  it('横幅文案取后端 message 原文（前端不拼接）', async () => {
    // 后端 message = '锁服务不可用，保存时可能冲突；本次编辑无冲突检测'
    render(<MemoryRouter><MainLayout /></MemoryRouter>);
    expect((await screen.findByTestId('degradation-banner')).textContent)
      .toContain('本次编辑无冲突检测');
    // ⚠️ 「；本次编辑无冲突检测」这半句由后端按表决定 ⇒ 前端不得自行拼接
  });

  it('系统判定：按钮文案随响应 decision 分流', async () => {
    // confirm 返回 {decision:'NO_CHANGE'} ⇒ 文案「确认：结果未变」
    // confirm 返回 {decision:'CHANGED'} ⇒ 文案「确认：结果已变」+「须重新签署」
    render(<ChangeImpactPanel changeSource={SOURCE} affectedRecords={RECORDS}
      onConfirmSystem={async () => {}} />);
    fireEvent.click(await screen.findByTestId('confirm-system-btn'));
    expect((await screen.findByTestId('confirm-system-result')).textContent).toContain('确认：结果未变');
  });

  it('人工判定：reason 为空 ⇒ **不发请求**（后端 422）', async () => {
    const onManualAdjust = vi.fn();
    render(<ChangeImpactPanel changeSource={SOURCE} affectedRecords={RECORDS}
      onManualAdjust={onManualAdjust} />);
    fireEvent.click(await screen.findByTestId('manual-adjust-btn'));
    fireEvent.click(screen.getByTestId('manual-adjust-submit'));
    expect(onManualAdjust).not.toHaveBeenCalled();
    expect(await screen.findByTestId('manual-adjust-error')).toBeTruthy();   // 「人工判定必须有据可查」
  });

  it('人工判定与系统判定是**两个**端点，不合并', async () => {
    // 断言：点「系统判定」只打 confirm；点「人工判定」只打 manual-adjust
    expect(confirmCalls).toBe(1);
    expect(manualAdjustCalls).toBe(0);
  });
  ```

- [ ] **Step 2：跑测试确认失败** ⇒ **FAIL**

- [ ] **Step 3：实现降级横幅**

  - `src/store/degradation.ts`（zustand，全局）
  - `useEditLock` 的 `onDegraded` ⇒ `setMessage(res.message)`
  - `MainLayout` 顶部：`<Alert type="warning" message={degradation.message} />`
    ⚠️ 文案**原样渲染**后端 `message`；⚠️ **不阻断**任何操作；⚠️ 后端 `message` 为 null
    ⇒ 不渲染横幅（不是渲染一句自造全局提示）

- [ ] **Step 4：扩展 `ChangeImpactPanel`**

  - 现有 [确认重算] / [批量确认重算] ⇒ 指向 `confirm-recalc`（**另一个端点**，不动）
  - 新增 [系统判定] ⇒ `POST /change-impact/{rt}/{id}/confirm`
    ⇒ 响应 `decision` 决定文案：
    `NO_CHANGE` ⇒「确认：结果未变（免凭证）」；`CHANGED` ⇒「确认：结果已变（须重新签署）」
  - 新增 [人工判定] ⇒ `POST /change-impact/{rt}/{id}/manual-adjust`
    ⇒ body `{decision, reason}`；⚠️ **`reason` 必填**（空 ⇒ 422）⇒ 前端先校验
  - ⚠️ **不得自动重试**（会无限循环覆盖）

- [ ] **Step 5：跑测试确认通过** ⇒ **PASS**

- [ ] **Step 6：提交**
  ```bash
  git commit -m "feat(P9B): 锁降级横幅 + ChangeImpactPanel 的系统判定 / 人工判定"
  ```

---

## Task T5：观测进度面板（§6.24）+ 待办面板（§6.22）+ 实时状态（§6.23）

**Files:**
- Create: `src/components/common/WorkflowProgressPanel.tsx`、
  `src/components/common/TodoPanel.tsx`、`src/components/common/RealtimeStatusBanner.tsx`
- Modify: `src/components/common/NotificationCenter.tsx`（待办 tab 换成 `TodoPanel`）
- Test: `tests/components/common/WorkflowProgressPanel.test.tsx`、
  `tests/components/common/TodoPanel.test.tsx`

**Interfaces:**
- Consumes: `GET /workflow-progress/{workflow_type}/{workflow_id}`、
  `GET /todos`（`src/api/todos.ts` 已有）、`GET /health` 的 `realtime` / `realtime_reason`
- Produces:
  ```ts
  // WorkflowProgressPanel
  interface Props {
    workflowType: 'SIGN' | 'CHANGE_NOTICE' | 'CUSTOMER_APPROVAL_PROXY';
    workflowId: string;
  }
  // TodoPanel
  interface Props { items: TodoItem[]; compact?: boolean; onOpen?: (t: TodoItem) => void; }
  // RealtimeStatusBanner
  interface Props { realtime: 'ok' | 'degraded'; reason: string | null; }
  ```

- [ ] **Step 1：写失败测试**

  ```ts
  it('五态分色，PENDING 与 SKIPPED **不合并**', async () => {
    render(<WorkflowProgressPanel workflowType="SIGN" workflowId="w1" />);
    const nodes = await screen.findAllByTestId('progress-node');
    expect(nodes.find((n) => n.getAttribute('data-status') === 'PENDING')).toBeTruthy();
    expect(nodes.find((n) => n.getAttribute('data-status') === 'SKIPPED')).toBeTruthy();
    // ⚠️ 两者都存在 ⇒ 没被归并成同一个「未完成」
  });

  it('不显示百分比（total 是节点数不是工作量）', async () => {
    render(<WorkflowProgressPanel workflowType="SIGN" workflowId="w1" />);
    await screen.findAllByTestId('progress-node');
    expect(document.querySelector('[data-testid="workflow-progress-panel"]')?.textContent).not.toContain('%');
  });

  it('items 为空 ⇒ 空态「该工作流暂无步骤记录」，不是「0 步已完成」', async () => {
    render(<WorkflowProgressPanel workflowType="SIGN" workflowId="w1" />);
    expect((await screen.findByTestId('workflow-progress-empty')).textContent)
      .toContain('暂无步骤记录');
  });

  it('CHANGE_NOTICE 面板为空 ⇒ 不显示成「流程异常」', async () => {
    render(<WorkflowProgressPanel workflowType="CHANGE_NOTICE" workflowId="w1" />);
    expect((await screen.findByTestId('workflow-progress-empty')).textContent)
      .not.toContain('异常');
  });

  it('TodoPanel：空态不得断言「你没有待办」', () => {
    render(<TodoPanel items={[]} />);
    // ⚠️ 空态只能说「暂无待办」；说「你没有待办」会把「无签署职责」说成「没活干」
    expect(screen.getByTestId('todo-empty').textContent).not.toContain('你没有');
  });

  it('RealtimeStatusBanner：degraded ⇒ 文案含「仍可收到通知」且**不阻断**', () => {
    render(<RealtimeStatusBanner realtime="degraded" reason="redis_unavailable" />);
    expect(screen.getByTestId('realtime-status-banner').textContent).toContain('仍可收到通知');
    expect(screen.queryByTestId('realtime-blocking-overlay')).toBeNull();
  });
  ```

- [ ] **Step 2：跑测试确认失败** ⇒ **FAIL**

- [ ] **Step 3：实现三个组件**（逐条对着 SPEC §6.22 / §6.23 / §6.24）

  - `WorkflowProgressPanel`：拉 `GET /workflow-progress/{type}/{id}`；顶部五计数；
    节点条按 `step_order` 升序；五态配色（PENDING 灰 / IN_PROGRESS 蓝脉冲 /
    COMPLETED 绿 / SKIPPED 灰虚线 / FAILED 红）；`result_hash` 用 `HashBadge`
  - `TodoPanel`：列（交付物 / 版本 / 步骤 / 签署职责 / 标题 / 操作）；
    `compact` 时只渲染标题 + 职责（抽屉用）
  - `RealtimeStatusBanner`：读 `/health` 的 `realtime` / `realtime_reason`；
    ⚠️ `realtime` **不得**用于 liveness/readiness；⚠️ 降级文案说「及时性降级，
      通知**仍可达**」；⚠️ `realtime_reason` 走**枚举**映射，不自造

- [ ] **Step 4：`NotificationCenter` 的待办 tab 换成 `TodoPanel`**
  （SPEC §6.20 的分组来源：待办 ← `GET /todos`，**不是**通知）

- [ ] **Step 5：跑测试确认通过** ⇒ **PASS**

- [ ] **Step 6：提交**
  ```bash
  git commit -m "feat(P9B): 观测进度 / 待办 / 实时状态面板（SPEC §6.22~§6.24）"
  ```

---

## Task T6：QA gate + 收口

**Files:**
- Report: `.gstack/qa-reports/qa-report-pcs-frontend-YYYY-MM-DD-p9b-1.md`（已 gitignore）
- Modify: `TODOS.md`、`.wolf/{STATUS,cerebrum,buglog}`

- [ ] **Step 1：静态门禁**
  ```bash
  cd pcs-frontend
  npm run typecheck        # exit 0
  npm run lint             # exit 0（自带 --max-warnings 0）
  npm run test             # ≥ 本批 baseline（716）
  ```

- [ ] **Step 2：浏览器回归**（`~/.claude/skills/gstack/browse/dist/browse`，`CI=1`）
  - login 200 → dashboard 渲染
  - **6 条新路由可达**，每条列表有数据
  - 点「编辑」⇒ 抽屉打开 + **请求体带 `expected_hash`**（network 面板核对）
  - 锁指示器三态可见（可编辑 / 他人持锁 / 失效）
  - 409 弹窗按 basis 三种文案各出现一次
  - 控制台无 antd / React / TS error；核心 mock 端点无 404
  - ⚠️ **本批改了 MSW 契约形状 ⇒ 必须再跑一次**（2026-10-21 实测：mock 不同源
    ⇒ 浏览器 QA 看不见漂移）

- [ ] **Step 3：报告落盘**（`.gstack/qa-reports/`）

- [ ] **Step 4：收口**
  - `TODOS.md`：新增/更新条目（见「尚未解决」）
  - `.wolf/STATUS.md`（`/handoff`）、`.wolf/cerebrum.md`、`.wolf/buglog.json`
  - SPEC 若与实现有偏差 ⇒ **登记修订**（不静默偏离）

- [ ] **Step 5：提交**
  ```bash
  git commit -m "docs(P9B): P9B-1 收口 —— QA 报告 + TODOS + wolf 状态"
  ```

---

## 验收（全 lane）

- `npm run typecheck` exit 0 · `npm run lint` exit 0 · `npm run test` ≥ baseline 全绿
- **6 个 PATCH 在前端确实被调用，且每次都带 `expected_hash`**（断言请求体，不靠症状）
- **409 弹窗不得自动重试**（测试断言调用次数 == 1）
- **保存成功后基线刷新**（RF-1，否则第二次保存必假 409）
- 6 条新路由可达 + 浏览器回归无 error
- `tests/` 纳入类型检查 ⇒ fixture 也必须类型正确

---

## 尚未解决的问题

1. **「查看差异」只对 SYSTEM_ADMIN 可用** —— SPEC §6.21 P9A-LCK-006 说「查看差异」
   靠审计里的 `changed_fields`，而编辑审计只能从 `/audit-logs` 读，后端**限
   SYSTEM_ADMIN** ⇒ 普通 DESIGNER 拿到 409 弹窗却**看不到差异**。
   ⇒ 本批：前端优雅降级（403 ⇒ 「无权查看差异（需系统管理员）」）。
   ⇒ **建议**：后端补一个**按项目守卫**的 `GET /records/{module}/{id}/edits`
   （只回 `changed_fields` 字段名列表，不回值）⇒ 登记 TODO。
2. **6 个模块的字段清单仍是手写的**（但在 `resultModules.ts` 一处，且**类型约束**
   到 `keyof ResponseType`）⇒ 改名 = 编译期错误。⚠️ 若后端给这些表出 **uiSchema**，
   应改走 `SchemaForm`（SPEC 的既有方向）—— 本批不做。
3. **`WorkflowProgressPanel` 本批没有宿主页面**（签署流程前端属 P9B-2）
   ⇒ 组件交付但不可达 ⇒ P9B-2 必须接线，否则是死代码。
4. **`realTime` 降级**：后端 `/health` 的 `realtime` 已就位，但**没有 WebSocket
   客户端**（`WS /api/v1/ws/notifications`）⇒ 本批的 `RealtimeStatusBanner` 只
   读 `realtime` 并**切轮询**；真正的 WS 订阅属 P9B-2。
5. **`expected_updated_at` 第二档基线前端暂不消费** —— 6 个响应里 5 个有
   `updated_at`，但 `record_hash` 一档已足够 ⇒ **第二档是兜底，不是常态**。
6. **`project_id` 来自 `src/constants/env.ts` 的 `PROJECT_ID` 常量**（单项目假设）
   ⇒ 多项目切换属 P9B-2（`WorkspaceSwitcher` 已存在但未接结果页）。
7. **P9 SPEC §4.2 的「7 个 mock type 文件改 import 自 ./api」不成立**（该节自己
   已注明：28/31 个导出 interface 在 OpenAPI 里无对应 schema）⇒ 本批**不执行**
   那条，只遵守「类型从 `components['schemas']` 来」。
