# P5-3 前端 PSV UI 实施计划（V1.2 对齐）

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans。Steps 用 checkbox（`- [ ]`）追踪。
>
> **Plan scope**：P5-3 前端 UI 闭环，对齐 SPEC V1.2 §7.11.5 + 后端 OpenAPI（commit 93627a7）。包含 6 改动点 + 3 测试验证。

**Goal:** 把 V1.1 占位 `PsvComputePage`（574 行 mock）升级为 V1.2 SPEC 完整 PSV 计算 Page（4 scenario 路由 + design_stage 切换 + 项目标准配置独立 Page + MSW handler 补齐）。

**Architecture:** 严格按 SPEC V1.2 §7.11.5 + 后端 `app/api/v1/psv.py` + `psv_standard_profiles.py` 契约。前端 4 类组件：(1) `api/psv.ts` API 客户端（axios + token + 错误 envelope 解析）；(2) `types/psv.ts` 重写对齐 V1.2 单次 `relief_scenario` 调用契约；(3) `PsvComputePage.tsx` 大幅扩展（4 scenario 路由 + design_stage BASIC/DETAIL + 真 API 调用 + outlet_stream 展示）；(4) 新建 `PsvStandardProfilePage.tsx`（项目级 PSV 标准配置 GET/POST + CUSTOM approval_json 校验）。mock 层补齐 6 个 P5 端点 handler 让 MSW 闭环。

**Tech Stack:** React 18 / TypeScript / Ant Design 5 / axios / zustand / MSW（dev mock）/ vite / vitest。

**Spec:** `docs/PCS-UI-SPEC.md` V1.2 §7.11.5（commit 7db5ea5）+ 后端 OpenAPI schema（`app/api/v1/psv.py` 93627a7）+ SUP-P5-PSV-001 + ADR-0028 V1.1。

---

## Global Constraints

- **全程中文**；"继续" = 驱动下一 task 不重议
- **每 task 一 commit + 约定式提交 + Co-Authored-By: Claude Code <noreply@anthropic.com>**
- **前端编码依据**：SPEC V1.0 → V1.2 冻结；与后端 OpenAPI 冲突时以 OpenAPI 为准并登记 SPEC §12.4 修订
- **字段/枚举/权限/错误码** 以 OpenAPI + meta API 为准
- **不动 SPEC V1.2 §7.11.5 已锁定字段**：4 scenario enum、design_stage BASIC/DETAIL、relief_area 公式溯源 3 段、record_hash 16 hex、CUSTOM approval_json 必填
- **不动后端**（commit 93627a7 已闭环）：仅前端 + mock 补齐
- **不引新依赖**：复用现有 `api/client.ts`（46 行 axios + token + 401 兜底）+ `api/sprint1.ts` 模板
- **不动 MSW core**：复用 `mocks/handlers.ts` 现有 5 OpenAPI + 17 dev-only handler 模式
- **PROJECT_ID 硬编码**：保持 `routeWrappers.tsx:71` UUID 字面量（OPEN-2 已记录）
- **DEV_BEARER 硬编码**：保持 `'Bearer mock-jwt-token'`（OPEN-3 已记录）

---

## File Structure

### 修改（本批次 5 个）
```
pcs-frontend/src/types/psv.ts                                  # 重写（V1.1 132 行 → V1.2 ~150 行对齐 OpenAPI）
pcs-frontend/src/api/psv.ts                                    # 新建（按 sprint1.ts 56 行模板）
pcs-frontend/src/pages/psv/PsvComputePage.tsx                  # 大幅扩展（575 行 → ~750 行，scenario 路由 + design_stage + outlet 展示 + 错误 envelope）
pcs-frontend/src/mocks/handlers.ts                             # 补 6 handler（psv/calculate + psv/standard-profile × 2 端点 + 1 mock seed）
pcs-frontend/src/pages/routeWrappers.tsx                       # 2 行修改（增加 useFetch 调用 + projectStandard 路由参数）
```

### 不动（本批次 scope 外）
- `App.tsx`（L80 psv 路由已注册）
- `MainLayout.tsx`（L48 psv 菜单已注册）
- `api/client.ts` / `store/auth.ts` / `components/common/*`
- `types/api.d.ts`（openapi-typescript 自动生成；V1.3 阶段再 regen）

---

## Task 1: 重写 `types/psv.ts` 对齐 V1.2 SPEC 单次调用契约

**Files:**
- Modify: `pcs-frontend/src/types/psv.ts`（132 行 → ~150 行）

**Step 1: 类型对齐 V1.2 SPEC §7.11.5 + 后端 OpenAPI**

V1.2 SPEC 单次调用契约（替换 V1.1 扁平 `scenarios[]`）：

```ts
// ====== PsvCalculateRequest（POST /psv/calculate 输入）======
export interface PsvCalculateRequest {
  source_stream_id: string;                    // UUID
  relief_scenario: ReliefScenario;              // 4 种枚举：FIRE / CLOSED_VALVE / REACTION_RUNAWAY / THERMAL_EXPANSION
  scenario_params: ScenarioParams;             // 4 种路由联合类型
  sizing_params: SizingParams;                 // sizing + standard_code/version
  design_stage?: DesignStage;                  // BASIC ≤25 列 / DETAIL 完整（默认 DETAIL）
  blowdown_fraction?: number;                  // 默认 0.05（API 526 §4.4.2）
  inlet_size?: string;                         // e.g. "4 inch"
  outlet_size?: string;                        // e.g. "6 inch"
}

// 4 种 scenario_params 路由联合
export type ScenarioParams =
  | { kind: 'FIRE'; D_m: number; H_m: number; liquid_level_fraction: number; environment_factor_F: number; h_fg_j_per_kg: number }
  | { kind: 'CLOSED_VALVE'; V_pipe_m3: number; rho_L_kg_m3: number; t_isolation_s: number }
  | { kind: 'REACTION_RUNAWAY'; Q_rxn_w: number; fraction_to_valve: number }
  | { kind: 'THERMAL_EXPANSION'; V_L_m3: number; rho_L_kg_m3: number; beta_per_k: number; delta_T_k: number; t_heat_s: number };

export type DesignStage = 'BASIC' | 'DETAIL';

export interface SizingParams {
  relief_mass_flow_kgs: number;
  phase: 'GAS' | 'LIQUID' | 'TWO_PHASE';
  P_back_pa: number;
  P_set_pa: number;
  // GAS / TWO_PHASE 路径
  T_k?: number;
  M_kg_per_mol?: number;
  Z?: number;
  k_cp_ratio?: number;
  // LIQUID 路径
  rho_L_kg_m3?: number;
}

// ====== PsvCalculateResponse（POST /psv/calculate 输出）======
export interface PsvCalculateResponse {
  calc_id: string;                             // UUID
  calc_type: 'PSV';
  record_hash: string;                         // 16 hex
  stream_id: string;
  lineage_ids: string[];
  outlet_stream_id: string | null;
  outlet_stream_name: string | null;
  result: {
    relief_scenario: ReliefScenario;
    aggregate: {
      dominant_scenario: ReliefScenario;
      case_count: number;
      per_scenario_json: Record<string, unknown>;
    };
    relief_area: {
      area_required_m2: number;
      medium: 'GAS' | 'LIQUID' | 'TWO_PHASE';
      formula_ref: { standard: string; version: string; clause: string };
      omega_method?: 'ω';
      orifice_table_status?: 'incomplete_fallback';
    };
    orifice: {
      selected_size: 'D' | 'E' | 'F' | 'G' | 'H' | 'J' | 'K' | 'L' | 'M' | 'N' | 'P' | 'Q' | 'R' | 'T';
      actual_area_m2: number;
      inlet_size: string;
      outlet_size: string;
    };
    set_pressure_pa: number;
    blowdown_fraction: number;
    standard_profile_code: 'API' | 'GB' | 'CUSTOM';
    standard_refs_json: Record<string, { standard: string; version: string; clause: string }>;
    formula_ref_json: {
      dominant_scenario: string;
      fire_case_or_other: { standard: string; version: string; clause: string };
      relief_area: { standard: string; version: string; clause: string };
      orifice: { standard: string; version: string; clause: string };
    };
  };
}

// ====== 项目标准配置（GET/POST /projects/{pid}/psv/standard-profile）======
export interface PsvStandardProfile {
  profile_id: string;
  project_id: string;
  discipline: 'PSV';
  profile_code: 'API' | 'GB' | 'CUSTOM';
  standard_refs_json: Record<string, { standard: string; version: string; clause: string }>;
  approval_json: Record<string, unknown> | null;
  is_default: boolean;
  migrated_default: boolean;
  effective_from: string;
  effective_to: string | null;
  approved_by: string | null;
  created_at: string;
  updated_at: string;
}

export interface UpsertPsvStandardProfileRequest {
  profile_code: 'API' | 'GB' | 'CUSTOM';
  standard_refs_json: Record<string, { standard: string; version: string; clause: string }>;
  approval_json?: Record<string, unknown>;     // CUSTOM 必填
  approved_by?: string;                         // CUSTOM 必填
}
```

**Step 2: 验证对齐**

对比 V1.2 SPEC §7.11.5 + 后端 `app/api/v1/psv.py:StandardProfileResponse` / `UpsertStandardProfileRequest` / `app/services/psv/__init__.py:ReliefScenario` enum。4 种 scenario 必须严格匹配后端 `_dispatch_scenario_calc` 入参 shape。

**Step 3: Commit**

```bash
cd pcs-frontend && git add src/types/psv.ts
git commit -m "refactor(p5-3): types/psv.ts 对齐 V1.2 SPEC §7.11.5 单次调用契约"
```

---

## Task 2: 新建 `api/psv.ts`（按 sprint1.ts 模板）

**Files:**
- Create: `pcs-frontend/src/api/psv.ts`（按 sprint1.ts 56 行模板）

**Step 1: 仿 sprint1.ts 模式**

```ts
/**P5-3 PSV 计算 + 项目标准配置 API 客户端（V1.2 SPEC §7.11.5）。

按 SPEC V1.2 + 后端 OpenAPI（commit 93627a7）：
- POST /api/v1/psv/calculate → PsvCalculateResponse
- GET /api/v1/projects/{pid}/psv/standard-profile → PsvStandardProfile | null
- POST /api/v1/projects/{pid}/psv/standard-profile → PsvStandardProfile（创建/激活）

错误通过 PcsError envelope 抛出（code/message/detail/trace_id），
前端 message.error 显示 message 字段，特殊 code 触发定制 UI（PSV_INPUT_ERROR → 表单高亮）。
*/
import { client } from './client';
import type {
  PsvCalculateRequest,
  PsvCalculateResponse,
  PsvStandardProfile,
  UpsertPsvStandardProfileRequest,
} from '../types/psv';

export const psvApi = {
  calculate: async (req: PsvCalculateRequest): Promise<PsvCalculateResponse> => {
    const { data } = await client.post('/api/v1/psv/calculate', req);
    return data;
  },

  getStandardProfile: async (
    projectId: string,
  ): Promise<PsvStandardProfile | null> => {
    const { data } = await client.get(
      `/api/v1/projects/${projectId}/psv/standard-profile`,
    );
    return data;
  },

  upsertStandardProfile: async (
    projectId: string,
    req: UpsertPsvStandardProfileRequest,
  ): Promise<PsvStandardProfile> => {
    const { data } = await client.post(
      `/api/v1/projects/${projectId}/psv/standard-profile`,
      req,
    );
    return data;
  },
};
```

**Step 2: 验证 import**

`api/client.ts` 已 export `client` 实例（46 行）。错误 envelope 解析在 `api/client.ts:401` 兜底（401 跳登录）；其他 envelope 错误由 axios interceptor 抛出，业务层 try/catch。

**Step 3: Commit**

```bash
cd pcs-frontend && git add src/api/psv.ts
git commit -m "feat(p5-3): api/psv.ts PSV 计算 + 标准配置 API 客户端（对齐 V1.2 SPEC）"
```

---

## Task 3: `PsvComputePage.tsx` 大幅扩展（4 scenario + design_stage + outlet + error）

**Files:**
- Modify: `pcs-frontend/src/pages/psv/PsvComputePage.tsx`（575 行 → ~750 行）

**Step 1: 设计要点**

| 子模块 | 当前 V1.1 | V1.2 升级 |
|---|---|---|
| **Tab 结构** | ReliefTab / AreaTab / OrificeTab（3 个 mock） | 加 `StandardTab` 引用项目标准 + `ResultTab` 展示 result.outlet_stream + lineage + record_hash |
| **Scenario 路由** | 只有 FIRE 实现，CLOSED_VALVE/REACTION_RUNAWAY/THERMAL_EXPANSION UI 有但 mock 返回同 FIRE | 真 API 4 scenario 路由 + 4 scenario_params 联合类型校验 |
| **Design Stage** | 无 | BASIC ≤25 列 / DETAIL 完整切换（默认 DETAIL） |
| **API 调用** | 3 mock 函数（mockFireCase/mockArea/mockOrifice） | `psvApi.calculate` 真调用 + 错误 envelope 解析 + loading/disabled 状态 |
| **Outlet Stream** | 无展示 | ResultTab 展示 outlet_stream_id / outlet_stream_name + 命名约定（继承源流名前缀） |
| **错误处理** | 无 | PcsError envelope → message.error 显示 message；STREAM_NOT_CHECKED → 提示流未签收；PSV_INPUT_ERROR → 表单高亮字段 |
| **Record Hash** | 无 | 展示 record_hash（16 hex）+ lineage_ids 数量 |

**Step 2: 关键代码片段（仅 outline，详细实现按现有 PsvComputePage.tsx 风格）**

```tsx
// 4 scenario 路由（核心 dispatcher）
const buildRequestBody = (
  scenario: ReliefScenario,
  scenarioForm: Record<string, number>,
  sizingForm: SizingFormValues,
  designStage: DesignStage,
): PsvCalculateRequest => {
  const base = {
    source_stream_id: checkedStream!.stream_id,
    relief_scenario: scenario,
    sizing_params: { ... },
    design_stage: designStage,
    blowdown_fraction: 0.05,
    inlet_size: '4 inch',
    outlet_size: '6 inch',
  };
  switch (scenario) {
    case 'FIRE':
      return { ...base, scenario_params: { kind: 'FIRE', ...scenarioForm } };
    case 'CLOSED_VALVE':
      return { ...base, scenario_params: { kind: 'CLOSED_VALVE', ...scenarioForm } };
    case 'REACTION_RUNAWAY':
      return { ...base, scenario_params: { kind: 'REACTION_RUNAWAY', ...scenarioForm } };
    case 'THERMAL_EXPANSION':
      return { ...base, scenario_params: { kind: 'THERMAL_EXPANSION', ...scenarioForm } };
  }
};

// 真 API 调用 + 错误 envelope 解析
const onCalculate = async (scenario: ReliefScenario) => {
  setLoading(true);
  try {
    const resp = await psvApi.calculate(buildRequestBody(scenario, ...));
    setResult(resp);
    setActiveTab('result');
    message.success(`PSV 计算完成：record_hash=${resp.record_hash}`);
  } catch (err) {
    const code = (err as any)?.response?.data?.code;
    const msg = (err as any)?.response?.data?.message ?? '计算失败';
    if (code === 'STREAM_NOT_CHECKED') {
      message.error('源流未签收，请先在物流一览完成 CHECKED 流程');
    } else if (code === 'SIM_STREAM_NOT_FOUND') {
      message.error('源流不存在，请重新选择');
    } else if (code === 'PSV_INPUT_ERROR') {
      message.error(`输入参数不合法：${msg}`);
      form.setFields(getInvalidFields(msg));  // 高亮字段
    } else {
      message.error(msg);
    }
  } finally {
    setLoading(false);
  }
};
```

**Step 3: Design Stage 切换（BASIC ≤25 列 / DETAIL 完整）**

```tsx
<Radio.Group value={designStage} onChange={(e) => setDesignStage(e.target.value)}>
  <Radio.Button value="BASIC">BASIC（≤25 列）</Radio.Button>
  <Radio.Button value="DETAIL">DETAIL（完整）</Radio.Button>
</Radio.Group>
```

BASIC 模式隐藏 ResultTab 的 standard_refs_json / formula_ref_json 详情，DETAIL 显示完整溯源。

**Step 4: Outlet Stream 展示（ResultTab 新增）**

```tsx
<Card title="出口流（PSV_CALCULATED）">
  {result.outlet_stream_id ? (
    <Space direction="vertical">
      <div>Stream ID: <code>{result.outlet_stream_id}</code></div>
      <div>Name: {result.outlet_stream_name}</div>
      <Tag color="default">DRAFT</Tag>
      <Tag color="blue">source_type: PSV_CALCULATED</Tag>
    </Space>
  ) : (
    <Empty description="未生成出口流" />
  )}
</Card>
```

**Step 5: 验证**

- 4 scenario 全部走通（CLI 调用 `psvApi.calculate` × 4）
- Design Stage 切换可逆（不污染 form 状态）
- Outlet Stream 在 result 返回后展示正确 stream_name 前缀
- 错误 envelope（403/404/422）触发对应 message

**Step 6: Commit**

```bash
cd pcs-frontend && git add src/pages/psv/PsvComputePage.tsx
git commit -m "feat(p5-3): PsvComputePage 对齐 V1.2 SPEC（4 scenario + design_stage + outlet + error）"
```

---

## Task 4: 新建 `PsvStandardProfilePage.tsx`（项目级标准配置）

**Files:**
- Create: `pcs-frontend/src/pages/psv/PsvStandardProfilePage.tsx`（~200 行）
- Modify: `pcs-frontend/src/pages/routeWrappers.tsx`（2 行：增加 `PsvStandardProfileRoute` + 注册 useFetch 调用）

**Step 1: Page 设计要点**

- 表头：`<PageHeader title="项目 PSV 标准配置" status={DRAFT} actions={[<刷新> + <编辑>]} />`
- 主区：
  - 顶部卡片：当前 profile（GET 查到后展示 `PsvStandardProfile`）
  - 未配置 → `<Empty description="项目未配置 PSV 标准配置（按全局默认 API/7th）" />`
  - 已配置 → 表格（standard / version / clause 3 列）+ approval_json（CUSTOM 时展开）
- 编辑 Drawer：
  - profile_code radio：API / GB / CUSTOM
  - standard_refs_json 动态表单（4 个子项：fire_case / relief_area / orifice / breathing_valve）
  - **CUSTOM 时 approval_json JSON 编辑器必填 + approved_by 输入**
  - 提交按钮：POST `/psv/standard-profile`（PROCESS_CONTROLLER / SYSTEM_ADMIN 角色；DESIGNER 禁用）
- 错误处理：422 PSV_INPUT_ERROR（CUSTOM 缺 approval_json）→ 表单高亮；403 → 角色不足提示

**Step 2: 关键代码片段**

```tsx
import { psvApi } from '../../api/psv';
import type { PsvStandardProfile, UpsertPsvStandardProfileRequest } from '../../types/psv';

export function PsvStandardProfilePage({ projectId }: { projectId: string }): JSX.Element {
  const [profile, setProfile] = useState<PsvStandardProfile | null>(null);
  const [loading, setLoading] = useState(false);
  const [editing, setEditing] = useState(false);

  const refresh = async () => {
    setLoading(true);
    try {
      const p = await psvApi.getStandardProfile(projectId);
      setProfile(p);
    } catch (err) {
      message.error('查询项目标准配置失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { void refresh(); }, [projectId]);

  const onSubmit = async (req: UpsertPsvStandardProfileRequest) => {
    try {
      const p = await psvApi.upsertStandardProfile(projectId, req);
      setProfile(p);
      setEditing(false);
      message.success(`PSV 标准配置已激活：${req.profile_code}`);
    } catch (err: any) {
      const code = err?.response?.data?.code;
      if (code === 'PSV_INPUT_ERROR') {
        message.error('CUSTOM 必须填 approval_json + approved_by');
      } else {
        message.error(err?.response?.data?.message ?? '保存失败');
      }
    }
  };

  // ... render with PageHeader + Spin + Card + Drawer
}
```

**Step 3: routeWrappers.tsx 路由注册**

```tsx
// 在 routeWrappers.tsx 增加（约 L213 后）：
export function PsvStandardProfileRoute(): JSX.Element {
  return <PsvStandardProfilePage projectId={PROJECT_ID} />;
}
```

App.tsx 新增路由：

```tsx
{ path: 'psv/standard-profile', element: <PsvStandardProfileRoute /> },
```

菜单可选：暂不加入 MainLayout（V1 简化入口；后续可加）。

**Step 4: Commit**

```bash
cd pcs-frontend && git add src/pages/psv/PsvStandardProfilePage.tsx src/pages/routeWrappers.tsx src/App.tsx
git commit -m "feat(p5-3): PsvStandardProfilePage 项目级 PSV 标准配置（GET/POST + CUSTOM 校验）"
```

---

## Task 5: `mocks/handlers.ts` 补 P5 端点（6 handler）

**Files:**
- Modify: `pcs-frontend/src/mocks/handlers.ts`（211 行 → ~280 行）

**Step 1: 新增 6 handler**

| Method | Path | 返回 | 来源 |
|---|---|---|---|
| POST | `/api/v1/psv/calculate` | 201 + 模拟 PsvCalculateResponse | 内联 mock（按 4 scenario enum 路由） |
| GET | `/api/v1/projects/:project_id/psv/standard-profile` | 200 + 模拟 PsvStandardProfile | 内联 mock seed |
| POST | `/api/v1/projects/:project_id/psv/standard-profile` | 201 + 模拟 PsvStandardProfile | 内联 mock seed |
| GET | `/api/v1/projects/:project_id/streams`（已有 L58） | 已有 | seedStreams |
| GET | `/api/v1/streams/:stream_id`（已有 L62） | 已有 | buildStreamDetail |

**Step 2: 关键 handler 代码**

```ts
// ====== P5-3 PSV handlers（mock）=====

const mockPsvResult = {
  calc_id: '00000000-0000-0000-0000-000000000099',
  calc_type: 'PSV',
  record_hash: 'a1b2c3d4e5f60718',
  stream_id: '00000000-0000-0000-0000-000000000001',
  lineage_ids: ['00000000-0000-0000-0000-000000000050'],
  outlet_stream_id: '00000000-0000-0000-0000-000000000088',
  outlet_stream_name: 'S-PSV-301-PSV-OUT',
  result: {
    relief_scenario: 'FIRE',
    aggregate: { dominant_scenario: 'FIRE', case_count: 1, per_scenario_json: {} },
    relief_area: { area_required_m2: 0.001234, medium: 'GAS', formula_ref: { standard: 'API_520', version: '7th', clause: '§5.6.3' } },
    orifice: { selected_size: 'D', actual_area_m2: 0.00171, inlet_size: '4 inch', outlet_size: '6 inch' },
    set_pressure_pa: 200000.0,
    blowdown_fraction: 0.05,
    standard_profile_code: 'API',
    standard_refs_json: {
      fire_case: { standard: 'API_521', version: '7th', clause: '§5.15.2.2.1' },
      relief_area: { standard: 'API_520', version: '7th', clause: '§5.6.3' },
      orifice: { standard: 'API_526', version: '7th', clause: 'Table 1' },
    },
    formula_ref_json: {
      dominant_scenario: 'FIRE',
      fire_case_or_other: { standard: 'API_521', version: '7th', clause: '§5.15.2.2.1' },
      relief_area: { standard: 'API_520', version: '7th', clause: '§5.6.3' },
      orifice: { standard: 'API_526', version: '7th', clause: 'Table 1' },
    },
  },
};

http.post('/api/v1/psv/calculate', async () => HttpResponse.json(mockPsvResult, { status: 201 })),

http.get('/api/v1/projects/:project_id/psv/standard-profile', async () =>
  HttpResponse.json(mockPsvStandardProfile, { status: 200 }),
),

http.post('/api/v1/projects/:project_id/psv/standard-profile', async ({ request }) => {
  const body = await request.json() as any;
  if (body.profile_code === 'CUSTOM' && !body.approval_json) {
    return HttpResponse.json(
      { code: 'PSV_INPUT_ERROR', message: 'CUSTOM 必须填 approval_json', detail: null, trace_id: '' },
      { status: 422 },
    );
  }
  return HttpResponse.json({ ...mockPsvStandardProfile, profile_code: body.profile_code }, { status: 201 });
}),
```

**Step 3: devOnlyMockHandlers 数组追加 3 条**

把上面 3 个 handler 加到 `devOnlyMockHandlers`（`handlers.ts:42-144`），位置在 L140 后。

**Step 4: Commit**

```bash
cd pcs-frontend && git add src/mocks/handlers.ts
git commit -m "feat(p5-3): MSW handlers 补 P5 端点（psv/calculate + standard-profile）"
```

---

## Task 6: 全栈基线验证

**Files:** 无新增

**Step 1: tsc + eslint + vitest**

```bash
cd pcs-frontend
npx tsc --noEmit                                          # 期望 clean
npx eslint src/ tests/                                    # 期望 clean
npx vitest run                                            # 期望 ≥ 上批 baseline（无新增测试）
```

**Step 2: 手测 dev server**

```bash
cd pcs-frontend && npm run dev   # vite 启动 → http://localhost:5173
```

- 浏览器登录 → 菜单"工艺计算" → "安全阀" → 4 scenario 切换 → 提交 → result 展示 record_hash + outlet_stream
- 浏览器 → `/psv/standard-profile` → 查看空状态 → 编辑 → 提交 → 看到标准配置激活
- MSW console 无 404

**Step 3: ruff baseline（不动后端）**

```bash
cd pcs-backend && uv run ruff check .   # 0 errors（不动后端）
```

**Step 4: 全栈 pytest（不动后端）**

```bash
cd pcs-backend && uv run pytest -q   # 现有 baseline 不变
```

**Step 5: Commit（如有 lint 自动修复）**

```bash
cd pcs-frontend && git add -u
git diff --cached --quiet || git commit -m "style(p5-3): lint 自动修复"
```

---

## Verification 端到端验证清单

| # | 项 | 命令 / 操作 | 期望 |
|---|---|---|---|
| 1 | types/psv.ts 对齐 | `grep "scenarios\[\]" src/types/psv.ts` | 无匹配（V1.1 扁平数组已移除） |
| 2 | api/psv.ts 存在 | `ls src/api/psv.ts` | ✅ |
| 3 | PsvComputePage 4 scenario | `grep "RELIEF_SCENARIO_OPTIONS" src/pages/psv/PsvComputePage.tsx` | ✅ 4 项 |
| 4 | PsvStandardProfilePage 存在 | `ls src/pages/psv/PsvStandardProfilePage.tsx` | ✅ |
| 5 | 路由注册 | `grep "psv/standard-profile" src/App.tsx` | ✅ |
| 6 | MSW handlers 补齐 | `grep "psv/calculate\|psv/standard-profile" src/mocks/handlers.ts` | ✅ 3 匹配 |
| 7 | tsc clean | `npx tsc --noEmit` | 0 errors |
| 8 | eslint clean | `npx eslint src/ tests/` | 0 errors |
| 9 | vitest baseline | `npx vitest run` | ≥ 上批 baseline |
| 10 | 浏览器手测 | login → psv → 4 scenario → submit → result 展示 | ✅ |
| 11 | 标准配置手测 | login → /psv/standard-profile → 编辑 → submit | ✅ |
| 12 | MSW console | 浏览器 console 无 404/500 | ✅ |
| 13 | 后端 ruff baseline | `uv run ruff check .` | 0 errors |
| 14 | 后端 pytest baseline | `uv run pytest -q` | ≥ 1919 baseline |

---

## 复用清单（按 Explore agent 调研）

| 文件 | 用途 | 用法 |
|---|---|---|
| `api/client.ts:46` axios 实例 | 复用 | `import { client } from './client'` |
| `api/sprint1.ts:56` 模板 | 仿 | psvApi 同结构（3 方法） |
| `components/common/PageHeader.tsx` | 复用 | `<PageHeader title="..." actions={...} />` |
| `components/common/StateBadge.tsx` | 复用 | `<StateBadge module="PSV" status="DRAFT" />` |
| `types/vessel.ts:24-50` | 仿 | VesselSizing/SizingParams 模式 |
| `types/sepEquip.ts:53-69` | 仿 | SepEquipCalculateRequest/Response 模式 |
| `mocks/handlers.ts:42-144 devOnlyMockHandlers` | 仿 | 现有 17 handler 模式（HTTP method + 路径 + JSON 返回） |
| `pages/routeWrappers.tsx:71 PROJECT_ID` | 复用 | `const PROJECT_ID = '00000000-0000-0000-0000-000000000001'` |
| `pages/routeWrappers.tsx:76 useFetch` | 参考 | 不用（直接 useEffect + psvApi 调用） |

---

## 未解决问题（OPEN 列表）

- **OPEN-1**：types/psv.ts 与 V1.2 SPEC 单次调用契约对齐（**本 task Task 1 解决**）
- **OPEN-2**：PROJECT_ID 硬编码（`routeWrappers.tsx:71`）—— **本批次不动**；已登记 `docs/PCS-P5-PLAN.md §"P5 frontend 收口 checklist 收口项 #1"`，由 P5 frontend 全栈闭环后统一抽 `src/constants/env.ts`
- **OPEN-3**：DEV_BEARER 硬编码 3 处重复（`routeWrappers.tsx:74` + `MainLayout.tsx:82` + `mocks/handlers.ts:14`）—— **本批次不动**；同上登记 P5 frontend 收口 checklist
- **OPEN-4**：mocks/handlers.ts 缺失 P5 端点（**本 task Task 5 解决**：6 handler 中 3 个）
- **OPEN-5**：VESSEL / SEP_EQUIP mock handlers 仍缺失 —— 本批次不动；后续 P5-1/P5-2 前端批次各自补
- **OPEN-6**：PsvStandardProfilePage 暂未加入 MainLayout 菜单 —— 本批次接受；后续如需入口再加
- **OPEN-7**：types/api.d.ts 未自动生成 V1.3 SPEC 端点契约 —— 本批次不动；openapi-typescript regen 在 P5 全部闭环后
- **OPEN-8**：psv.calculate 错误 envelope 解析（Task 3 Step 2 中 axios interceptor 401 兜底已知，其他 code 解析依赖 `err.response.data.code`）—— 后端 commit 93627a7 已用 `install_exception_handlers` 统一 envelope
- **OPEN-9**：gstack-qa 浏览器回归（CLAUDE.md Per-Batch QA Gate）—— 本批次末按需跑；若 CRITICAL/HIGH 必修，登记 `.gstack/qa-reports/qa-report-pcs-frontend-YYYY-MM-DD-p5-3-frontend.md`

---

## 工时估算（参考）

| Task | 复杂度 | 预估耗时 |
|---|---|---|
| Task 1: types/psv.ts 重写 | 低 | 15 min |
| Task 2: api/psv.ts 新建 | 低 | 10 min |
| Task 3: PsvComputePage 大幅扩展 | 中 | 50-60 min |
| Task 4: PsvStandardProfilePage 新建 + 路由 | 中 | 30-40 min |
| Task 5: mocks/handlers.ts 补 3 handler | 低 | 15 min |
| Task 6: 全栈验证 | 低 | 10 min |
| **总计** | — | **~2.5 hours** |

---

**Plan 终止**：P5-3 前端 UI 闭环 6 task 完成。
**下一步**：用户批准后实施 + gstack-qa 浏览器回归。