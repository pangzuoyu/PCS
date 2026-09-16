# P4.5 批 3：P3/P4 计算页面 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** P4.5 批 3 落地 SPEC §7.11 / §7.13 / §7.7 / §7.8 / §7.9 共 8 模块前端页面，与 P5 后端 calculate 入口同步开发（前端可 MSW mock，后端接口就绪即切真实 API）。

**Architecture:**
- 严格遵循 PCS-UI-SPEC §7（每模块字段）+ §6（共享组件）+ §8（SchemaForm 驱动）
- 复用 P45-1 共享组件库（StateBadge / HashBadge / SchemaForm / NumericCell / LineageGraph / RevTimeline / SignatureMatrix / ConflictResolver / ChangeImpactPanel）
- 计算类页面（FLASH / PIPE / PUMP / PIPE_NET）走统一布局：`PageHeader + SchemaForm 输入 + 计算按钮 + 结果卡片 + 血缘图 + 同步设备表`
- 数据层：本批 3 先用 in-memory mock 数组（与现有 CONFIG 批 2 风格一致），P5 calculate 端点稳定后由 metaApi 替换

**Tech Stack:** React 19 + antd v5 + TypeScript + vitest + @testing-library/react + MSW（可选）+ React Flow（仅 PIPE_NET）

**Spec:** `docs/PCS-UI-SPEC.md` §7.7（SIM）/ §7.8（COMMON）/ §7.9（PIPE_CLASS）/ §7.11（FLASH / PIPE / PIPE_NET / PUMP）/ §7.13（EQUIP_LIST）

**上游依赖：** P45-1 全 13 共享组件（已闭环）；P45-2-1 SchemaForm（已闭环）；P45-2-3 CONFIG 资产列表（已闭环）
**下游解锁：** P8 REPORT（依赖 PIPE 一览表）/ P6 工时统计（依赖 EQUIP_LIST）/ P7 交付包（依赖所有 P3/P4 模块详情）

---

## 全局约束

1. **每 task 一 commit**；约定式提交（`feat(p45-3-N): <标题>`）；`Co-Authored-By: Claude Code <noreply@anthropic.com>`
2. **复用优先**：先查 P45-1 组件库；新组件仅在 SPEC §6 之外时新增
3. **类型驱动**：计算结果用 §7.11 列出的字段；不发明新字段名（与 OpenAPI 一致优先）
4. **测试 ≥10 条 / 任务**（共享组件 / 集成测试 ≥15 条）
5. **ruff 0 / eslint 0 / tsc 0 / vitest 全绿** 才提交
6. **mock-first**：本批 3 用 in-memory 数组驱动；P5 接口就绪后由 `metaApi.calculate` 替换（解耦点保留）
7. **不动现有 P45-1 / P45-2 代码**，仅依赖
8. **路径深度**：页面在 `pcs-frontend/src/pages/<module>/`；测试在 `pcs-frontend/tests/pages/<module>/`；类型在 `src/types/<module>.ts`
9. **SPEC 冲突**：与 OpenAPI 不一致时以 OpenAPI 为准 + 登记 SPEC 修订（项目根 CLAUDE.md 准则）
10. **JSX 真值断言**：用 `screen.getByTestId` 或 `toBeTruthy()`；antd 组件 portal / Checkbox data-testid / Collapse destroyInactivePanel 等已踩坑规范遵守

---

## 任务分解

### Task 27 (P45-3-0)：共享 Shell 组件（PageHeader + ModuleLayout）

**Files:**
- Create: `pcs-frontend/src/components/common/PageHeader.tsx`
- Create: `pcs-frontend/src/components/common/ModuleLayout.tsx`
- Test: `pcs-frontend/tests/components/common/PageHeader.test.tsx`
- Test: `pcs-frontend/tests/components/common/ModuleLayout.test.tsx`

**Interfaces:**
- Consumes: StateBadge（§6.1）, HashBadge（§6.4）, ApprovalStepBar（§6.2）
- Produces:
  ```ts
  // PageHeader：统一页面头部
  interface PageHeaderProps {
    title: string;
    status?: RecordSignStatus;
    module?: StateBadgeModule;
    version?: { hash: string; label?: string };
    actions: ReactNode;          // 操作按钮区（提交批准 / 弃用 / 同步）
    extra?: ReactNode;           // 自定义右侧（步骤条等）
  }
  // ModuleLayout：统一计算模块布局（输入 + 结果 + 血缘 + 设备表）
  interface ModuleLayoutProps {
    input: ReactNode;
    result: ReactNode;
    lineage?: ReactNode;
    syncDevices?: ReactNode;
  }
  ```

**Steps:**
- [ ] Step 1：写 PageHeader 测试（标题 / 状态徽章 / hash / 操作 / extra slot）
- [ ] Step 2：跑测试 → RED（File not found）
- [ ] Step 3：实现 PageHeader（antd PageHeader + StateBadge + HashBadge + actions slot）
- [ ] Step 4：写 ModuleLayout 测试（四象限 slot 渲染）
- [ ] Step 5：实现 ModuleLayout（CSS Grid 2×2，桌面端 input/result 上排，lineage/syncDevices 下排）
- [ ] Step 6：跑 lint + tsc + 单测 → GREEN
- [ ] Step 7：`git add` + `git commit -m "feat(p45-3-0): PageHeader + ModuleLayout 共享 Shell"`

---

### Task 28 (P45-3-1)：SIM 物流（列表 / 详情 / 状态点 / 导入向导）

**Files:**
- Create: `pcs-frontend/src/pages/sim/StreamListPage.tsx`
- Create: `pcs-frontend/src/pages/sim/StreamDetailPage.tsx`
- Create: `pcs-frontend/src/pages/sim/ImportWizardPage.tsx`
- Create: `pcs-frontend/src/types/stream.ts`
- Test: `pcs-frontend/tests/pages/sim/StreamListPage.test.tsx`
- Test: `pcs-frontend/tests/pages/sim/StreamDetailPage.test.tsx`

**Interfaces（SPEC §7.7）：**
```ts
export type StreamPhase = 'LIQUID' | 'VAPOR' | 'MIXED' | 'AQUEOUS';
export type StreamSubphase = 'SUBCOOLED' | 'SAT_LIQUID' | 'SAT_VAPOR' | 'SUPERHEATED';
export interface Stream {
  stream_id: string;
  tag_number: string;          // StreamServiceMixin 必填
  stream_name: string;
  phase: StreamPhase;
  subphase?: StreamSubphase;
  temperature_c: number;
  pressure_mpa: number;
  total_mass_flow_kg_h: number;
  total_molar_flow_kmol_h: number;
  composition_json: Record<string, number>;  // 组分→摩尔分率
  sign_status: RecordSignStatus;
  approved_hash?: string;
}
```

**Steps:**
- [ ] Step 1：写 StreamListPage 测试（表格列：tag_number / 相态 / 温压 / 流量 / 状态；StateBadge 列；状态点 tabs：DRAFT / CHECKED / IN_APPROVAL；行点击 → StreamDetailPage）
- [ ] Step 2：跑测试 → RED
- [ ] Step 3：实现 StreamListPage（antd Table + Tabs 状态点过滤 + StateBadge + 行点击路由 `/sim/stream/:id`）
- [ ] Step 4：写 StreamDetailPage 测试（Descriptions 详情 + 组成 JSON 表格 + 签署步骤 + 历史 hash）
- [ ] Step 5：实现 StreamDetailPage（PageHeader + Descriptions + NumericCell + SignatureMatrix）
- [ ] Step 6：实现 ImportWizardPage（4 步骤：上传 → 字段映射 → 预览 → 确认）+ ms Upload
- [ ] Step 7：lint + tsc + 测试全绿
- [ ] Step 8：`git add` + `git commit -m "feat(p45-3-1): SIM 物流列表/详情/导入向导（§7.7）"`

---

### Task 29 (P45-3-2)：PIPE_CLASS 等级 / 符号表 / 代码格式设计器

**Files:**
- Create: `pcs-frontend/src/pages/pipe_class/PipeClassListPage.tsx`
- Create: `pcs-frontend/src/pages/pipe_class/CodeFormatDesignerPage.tsx`
- Create: `pcs-frontend/src/pages/pipe_class/SymbolTablePage.tsx`
- Create: `pcs-frontend/src/types/pipeClass.ts`
- Test: 三个对应 .test.tsx

**Interfaces（SPEC §7.9.1~5）：**
```ts
export interface PipeClass {
  pipe_class_id: string;
  code: string;                // 例如 "ASME B31.3"
  material: string;            // 例如 "A106-B"
  schedule: string;            // 例如 "Sch 40"
  size_range_json: { min_dn: number; max_dn: number };
  design_pressure_mpa: number;
  design_temperature_c: number;
  corrosion_allowance_mm: number;
  sign_status: string;
}

export interface CodeFormatSegment {
  order: number;
  field: 'material' | 'schedule' | 'size' | 'service' | 'insulation' | 'custom';
  value?: string;
  separator?: string;
}

export interface SymbolMapping {
  symbol: string;              // 例如 "W"
  meaning: string;             // 例如 "Water"
  category: 'fluid' | 'service' | 'phase' | 'toxicity';
}
```

**Steps:**
- [ ] Step 1：PipeClassListPage 测试（按 code / material / schedule 过滤 + design_stage=BASIC 简化列）
- [ ] Step 2：CodeFormatDesignerPage 测试（拖拽 segment 排序 + 实时预览管道号）
- [ ] Step 3：SymbolTablePage 测试（按类别分组 + 添加/编辑/删除映射 + 批量导入）
- [ ] Step 4：实现三个页面（ListPage = Table + 过滤；DesignerPage = SortableList + 实时预览；SymbolTable = Collapse 分组 + Table）
- [ ] Step 5：lint + tsc + 测试全绿
- [ ] Step 6：`git add` + `git commit -m "feat(p45-3-2): PIPE_CLASS 等级/符号表/代码格式设计器（§7.9）"`

---

### Task 30 (P45-3-3)：COMMON 物性查询 / 许用应力 / 毒性爆炸

**Files:**
- Create: `pcs-frontend/src/pages/common/PropertySearchPage.tsx`
- Create: `pcs-frontend/src/pages/common/AllowableStressPage.tsx`
- Create: `pcs-frontend/src/pages/common/ToxicityExplosivityPage.tsx`
- Create: `pcs-frontend/src/types/common.ts`
- Test: 三个对应 .test.tsx

**Interfaces（SPEC §7.8）：**
```ts
export interface ComponentProperty {
  component_id: string;
  name: string;
  formula: string;
  cas_number?: string;
  mw: number;                  // 分子量
  tc_k: number;                // 临界温度
  pc_mpa: number;              // 临界压力
  omega: number;               // 偏心因子
}

export interface AllowableStress {
  material: string;
  temperature_c: number;
  allowable_stress_mpa: number;
  standard: string;            // ASME / GB / DIN
}

export interface ToxicityClass {
  component_id: string;
  name: string;
  ld50_mg_kg?: number;
  pel_ppm?: number;            // 允许暴露限值
  explosive_limit_json?: { lel: number; uel: number };
  hazard_class: 'LOW' | 'MEDIUM' | 'HIGH';
}
```

**Steps:**
- [ ] Step 1：PropertySearchPage 测试（按 name/formula/CAS 模糊查询 + 物性卡片 + 收藏）
- [ ] Step 2：AllowableStressPage 测试（材料过滤 + 温度范围 + 应力曲线图占位 + 标准来源 tag）
- [ ] Step 3：ToxicityExplosivityPage 测试（按 hazard_class 分组 + 爆炸极限表格 + 红色警告标签）
- [ ] Step 4：实现三个页面
- [ ] Step 5：lint + tsc + 测试全绿
- [ ] Step 6：`git add` + `git commit -m "feat(p45-3-3): COMMON 物性/许用应力/毒性爆炸（§7.8）"`

---

### Task 31 (P45-3-4)：FLASH 计算界面

**Files:**
- Create: `pcs-frontend/src/pages/flash/FlashComputePage.tsx`
- Create: `pcs-frontend/src/types/flash.ts`
- Test: `pcs-frontend/tests/pages/flash/FlashComputePage.test.tsx`

**Interfaces（SPEC §7.11.1）：**
```ts
export type ThermoMethod = 'PR' | 'SRK' | 'NRTL' | 'IAPWS_IF97';
export type FlashCalcType = 'PT' | 'PH' | 'PS' | 'BUBBLE_POINT' | 'DEW_POINT';
export interface FlashInput {
  stream_id: string;
  thermo_method: ThermoMethod;
  calc_type: FlashCalcType;
  t_k?: number;
  p_mpa?: number;
  h_kj_kg?: number;
  s_kj_kg_k?: number;
}
export interface FlashResult {
  vapor_fraction: number;
  liquid_composition: Record<string, number>;
  vapor_composition: Record<string, number>;
  h_kj_kg: number;
  s_kj_kg_k: number;
  k_values: Record<string, number>;
  converged: boolean;
}
```

**Steps:**
- [ ] Step 1：FlashComputePage 测试
  - 物流选择 Select（仅 CHECKED）
  - 热力学方法 Radio.Group（4 选项）
  - 计算类型 Radio.Group + T/P 或 H/S 条件输入
  - 计算按钮触发结果（mock 走 in-memory）
  - 结果卡片：汽化分率（大数字）+ 组成双 Table + 焓熵 + K 值表
  - 不收敛红色警告 + 建议切换方法
- [ ] Step 2：实现 FlashComputePage（ModuleLayout + PageHeader + SchemaForm 输入 + 结果卡片 + LineageGraph 下游影响）
- [ ] Step 3：lint + tsc + 测试全绿
- [ ] Step 4：`git commit -m "feat(p45-3-4): FLASH 计算界面（§7.11.1）"`

---

### Task 32 (P45-3-5)：PIPE 计算界面 + 管道一览表

**Files:**
- Create: `pcs-frontend/src/pages/pipe/PipeComputePage.tsx`
- Create: `pcs-frontend/src/pages/pipe/PipeLineListPage.tsx`
- Create: `pcs-frontend/src/types/pipe.ts`
- Test: 两个对应 .test.tsx

**Interfaces（SPEC §7.11.2）：**
```ts
export type PipeDesignStage = 'BASIC' | 'DETAIL';
export interface PipeInput {
  stream_id: string;
  pipe_no: string;
  length_m: number;
  start_point: string;
  end_point: string;
  pid_ref?: string;
  fittings: Array<{ type: string; quantity: number; size: string }>;
  design_pressure_mpa: number;
  design_temperature_c: number;
  corrosion_allowance_mm: number;
  pipe_class_id: string;
  insulation_code?: string;
  insulation_thickness_mm?: number;
  heat_trace?: boolean;
  roughness_mm: number;        // PIPE 默认 0.046
  allowable_dp_kpa: number;
}
export interface PipeResult {
  diameter_mm: number;
  wall_thickness_mm: number;
  dp_kpa: number;
  velocity_m_s: number;
  flow_pattern: string;
  two_phase?: TwoPhaseResult;
}
export interface TwoPhaseResult {
  pattern: 'STRATIFIED' | 'WAVE' | 'ANNULAR' | 'SLUG' | 'MIST';
  liquid_holdup: number;
}
```

**管道一览表列（SPEC §7.11.2 完整 41 列，§7.11.2 design_stage 切换器）：**
```ts
export interface PipeLineListRow {
  seq: number;
  pipe_no: string;
  size: string;
  material: string;
  fluid_code: string;
  fluid_name: string;
  phase: string;
  fluid_class: string;
  toxicity: string;
  pipe_class: string;
  // ... 31 字段省略
}
```

**Steps:**
- [ ] Step 1：PipeComputePage 测试
  - 表单分组：物流 / 管道 / 管件 / 设计条件 / 等级 / 绝热 / 其他
  - 计算 Tab：管径 / 壁厚 / 压降 / 流速 + 两相流子表（如有）
  - 写回状态点按钮
- [ ] Step 2：PipeLineListPage 测试（design_stage 切换器 BASIC/DETAIL；列数；筛选：流体分类/管道级别）
- [ ] Step 3：实现两页（PipeComputePage = ModuleLayout + 分组 SchemaForm + 计算结果 Tab；PipeLineListPage = Table + 切换器 + 列渲染）
- [ ] Step 4：lint + tsc + 测试全绿
- [ ] Step 5：`git commit -m "feat(p45-3-5): PIPE 计算界面 + 管道一览表（§7.11.2）"`

---

### Task 33 (P45-3-6)：PIPE_NET 拓扑编辑器

**Files:**
- Create: `pcs-frontend/src/pages/pipe_net/PipeNetTopologyPage.tsx`
- Create: `pcs-frontend/src/types/pipeNet.ts`
- Test: `pcs-frontend/tests/pages/pipe_net/PipeNetTopologyPage.test.tsx`

**Interfaces（SPEC §7.11.3）：**
```ts
export interface PipeNetNode {
  node_id: string;
  type: 'EQUIPMENT' | 'BRANCH';
  label: string;
  equipment_id?: string;
  position: { x: number; y: number };
}
export interface PipeNetSegment {
  segment_id: string;
  pipe_no: string;
  from_node_id: string;
  to_node_id: string;
  diameter_mm: number;
  length_m: number;
  fittings_json: Record<string, number>;
}
export interface PipeNetResult {
  converged: boolean;
  iterations: number;
  flow_distribution: Array<{ segment_id: string; flow_kmol_h: number }>;
  dp_per_segment_kpa: Array<{ segment_id: string; dp_kpa: number }>;
  last_iteration_log?: string;
}
```

**Steps:**
- [ ] Step 1：测试（节点添加 / 管段连接 / 从 EQUIP_LIST 自动生成按钮 / 收敛日志显示）
- [ ] Step 2：安装 reactflow 依赖（`pnpm add reactflow @types/reactflow`）+ canvas mock
- [ ] Step 3：实现 PipeNetTopologyPage（ReactFlow + Controls + Background + 自定义 node/edge 类型 + 右侧侧栏：节点列表/收敛日志/压降表）
- [ ] Step 4：lint + tsc + 测试全绿
- [ ] Step 5：`git commit -m "feat(p45-3-6): PIPE_NET 拓扑编辑器（§7.11.3 reactflow）"`

---

### Task 34 (P45-3-7)：PUMP 计算界面

**Files:**
- Create: `pcs-frontend/src/pages/pump/PumpComputePage.tsx`
- Create: `pcs-frontend/src/types/pump.ts`
- Test: `pcs-frontend/tests/pages/pump/PumpComputePage.test.tsx`

**Interfaces（SPEC §7.11.4）：**
```ts
export interface PumpInput {
  suction: {
    vessel_pressure_mpa: number;
    liquid_level_m: number;
    pipe_dn: number;
    fittings_json: Record<string, number>;
  };
  discharge: {
    vessel_pressure_mpa: number;
    static_head_m: number;
    pipe_dn: number;
    fittings_json: Record<string, number>;
  };
  flow: { normal: number; min: number; design: number };
  efficiency: { pump: number; motor: number };
  control_valve_dp_kpa: number;
}
export interface PumpResult {
  head_m: number;
  npsh_m: number;
  power_kw: number;
  design_pressure_mpa: number;
  control_valve_kv: number;
  equivalent_length_m: number;
  dp_breakdown: Array<{ segment: string; dp_kpa: number }>;
}
```

**Steps:**
- [ ] Step 1：PumpComputePage 测试（输入分组 4 块 + 流量 3 值 + 效率 2 值 + 计算 + 结果 5 卡 + 压降明细表 + 出口物流创建提示）
- [ ] Step 2：实现 PumpComputePage（ModuleLayout + SchemaForm 分组输入 + 5 结果卡 + 压降明细 Table + 出口物流创建 toast）
- [ ] Step 3：lint + tsc + 测试全绿
- [ ] Step 4：`git commit -m "feat(p45-3-7): PUMP 计算界面（§7.11.4）"`

---

### Task 35 (P45-3-8)：PMS / BEDD / 项目向导

**Files:**
- Create: `pcs-frontend/src/pages/pms/PmsPage.tsx`
- Create: `pcs-frontend/src/pages/bedd/BeddPage.tsx`
- Create: `pcs-frontend/src/pages/wizard/ProjectWizardPage.tsx`
- Create: `pcs-frontend/src/types/pms.ts`
- Test: 三个对应 .test.tsx

**Interfaces（SPEC §7.5）：**
```ts
export interface PmsItem {
  item_id: string;
  pms_no: string;
  description: string;
  pms_class: string;
  hazard_level: 'LOW' | 'MEDIUM' | 'HIGH';
  sign_status: RecordSignStatus;
}
export interface BeddSection {
  section_id: string;
  title: string;
  content: string;
  sign_status: RecordSignStatus;
  signatures: SignatureEntry[];
}
```

**Steps:**
- [ ] Step 1：PmsPage 测试（PMS 列表 + 状态 + 校核 + 提交）
- [ ] Step 2：BeddPage 测试（章节 Collapse + 签署矩阵 + 状态）
- [ ] Step 3：ProjectWizardPage 测试（5 步骤向导：基本信息 → 模块选择 → 等级绑定 → 默认单位 → 完成）
- [ ] Step 4：实现三个页面
- [ ] Step 5：lint + tsc + 测试全绿
- [ ] Step 6：`git commit -m "feat(p45-3-8): PMS / BEDD / 项目向导（§7.5）"`

---

## Acceptance

| 项 | 标准 |
|---|---|
| 8 个 P3/P4 模块页面 | Task 28 / 29 / 30 / 31 / 32 / 33 / 34 / 35 全部闭环 |
| PageHeader + ModuleLayout | Task 27 共享 Shell 复用，FLASH / PIPE / PUMP 全部使用 |
| SchemaForm 驱动 | 计算类页面（FLASH / PIPE / PUMP）输入走 SchemaForm，非手动 columns |
| 数据来源 | 全部 in-memory mock；P5 calculate 端点稳定后由 metaApi 替换（解耦点保留） |
| 测试覆盖 | ≥10 条 / 任务；总计 ≥80 条 |
| CI 硬门 | tsc / eslint / vitest 全绿 |
| SPEC §7.11.2 PIPE 设计 | design_stage=BASIC 默认 + 切换器在工具栏；列数切换 |
| SPEC §7.11.3 PIPE_NET | React Flow 已安装；拓扑画布 + 节点 + 管段 |

---

## Self-Review

**1. Spec 覆盖：**
- §7.7 SIM（Task 28）✓
- §7.8 COMMON（Task 30）✓
- §7.9 PIPE_CLASS（Task 29）✓
- §7.11.1 FLASH（Task 31）✓
- §7.11.2 PIPE（Task 32）✓
- §7.11.3 PIPE_NET（Task 33）✓
- §7.11.4 PUMP（Task 34）✓
- §7.5 PMS / BEDD / 项目向导（Task 35）✓

**2. Placeholder 扫描：**
- "拖拽 segment" → Task 29 CodeFormatDesignerPage 暂用 Select 排序而非 react-dnd（V1.1 backlog）
- "实时预览管道号" → 实现极简：拼接 segments value；与 OpenAPI 字段映射完整再升级

**3. 类型一致性：**
- `RecordSignStatus` 来自 P45-1-1（已闭环）
- `SignatureEntry` 来自 P45-1-12（已闭环）
- `LineageGraph data` 来自 P45-1-15（已闭环）

**4. 裁决传递：**
- 裁决 #5 reactflow → Task 33 ✓
- 裁决 #7 SchemaForm 驱动 → Task 31/32/34 ✓
- 裁决 #10 mock-first → 全 task ✓
- 裁决 #11 契约冻结 → 等 P5 calculate 端点后切真实 API（注册于交接）

---

## 执行顺序与资源

| 顺序 | Task | 估时 | 并行 |
|---|---|---|---|
| 1 | Task 27 P45-3-0 共享 Shell | 0.5d | — |
| 2 | Task 28 P45-3-1 SIM | 1d | — |
| 3 | Task 30 P45-3-3 COMMON | 1d | Task 29 可并行 |
| 4 | Task 29 P45-3-2 PIPE_CLASS | 1d | 与 Task 30 并行 |
| 5 | Task 35 P45-3-8 PMS / BEDD / 向导 | 1d | 与 Task 31 并行 |
| 6 | Task 31 P45-3-4 FLASH | 1d | 与 Task 35 并行 |
| 7 | Task 34 P45-3-7 PUMP | 1d | — |
| 8 | Task 32 P45-3-5 PIPE | 1.5d | 依赖 Task 27 + PIPE_CLASS |
| 9 | Task 33 P45-3-6 PIPE_NET | 1.5d | 依赖 Task 27（最后一项） |
| **合计** | | **~9d** | |

**与 P5 后端同步窗口：**
- 批 3 前端可在 P5 calculate 端点未就绪时跑通（mock）
- P5 calculate 端点（计算 + 缓存 + 9 态扩展）就绪后由 PageHeader/ModuleLayout 的 `data-source` 切换
- HEAT 模块（PSV HTRI 导入）依赖 P5 异步任务端点（`task_id` + 轮询），不在本批范围，留 P5-HEAT 计划

---

## 尚未解决的问题

1. **P5 calculate 端点的契约冻结时机**：Task 31/32/34 的 mock 在 P5 接口就绪前是 in-memory；切换 metaApi 时需要逐字段对照。建议 P5-1（calculate 入口）落地后开 1d 把批 3 mock 替换为真实 API 调用。
2. **React Flow 体积与许可证**：Task 33 安装 `reactflow` ~ 200KB gzipped；MIT 协议，可接受。如果体积不可接受可改用自研 SVG（LineageGraph 已示范）；裁决由实施时定。
3. **drag-sort 库选择**：Task 29 CodeFormatDesignerPage 的 segment 排序暂用 antd Select 顺序数组，不引入 react-dnd；如 SPEC 强化要求视觉拖拽再装。
4. **PIPE 一览表 BASIC 30 列 vs DETAIL 41 列**：Task 32 需要明确 SPEC 列字段映射，避免「≤30 列」解读差异。已记录于 §7.11.2，等 SPEC 维护者确认。
5. **PIPE_NET 从 EQUIP_LIST 自动生成**：依赖 EQUIP_LIST 接口；本批 3 用 mock 数组，P5 EQUIP_LIST 端点就绪后接入。
6. **前端类型来源唯一性**：批 3 期间手写 `types/stream.ts` / `pipeClass.ts` / `common.ts` / `flash.ts` 等作为 Page-level mock props shape（已加 `TODO(api-migration)` 注释）。P5-1 契约冻结后必须由 `src/types/api.d.ts` 的 OpenAPI 生成类型替换前端所有手写类型（详见下方"## P5 契约冻结点"）。
7. **HEAT 计算（PSV / HTRI 导入）依赖 P5 异步任务契约**：不在本批范围；建议另开 P5-HEAT 前端计划文档，1 task / 半天评估后编。
8. **P3 / P4 模块未覆盖部分**：§7.12 设备计算（HEAT/PSV 等） / §7.13 EQUIP_LIST 详情 Tab / §7.14 供应商数据 / §7.15 UTIL — 本批 3 暂不展开，留 P4.6+ 后续批。

---

## ModuleLayout 注册（§6.21 新增章节）

批 3 Task 27 引入 `ModuleLayout` 共享 Shell（2×2 网格：input/result/lineage/syncDevices 槽位）。审查（见问题 5）指出 SPEC §6 未注册该概念，违反「不发明新概念」原则。

**注册位置**：`docs/PCS-UI-SPEC.md` §6.21 ModuleLayout（新增章节）

**章节草案**：

> **§6.21 ModuleLayout** — 2×2 网格共享 Shell，槽位 `input` / `result` / `lineage` / `syncDevices`。
> - 上行：`input`（输入卡）+ `result`（结果卡）必须存在
> - 下行：`lineage`（谱系/签署）+ `syncDevices`（同步设备）按需启用；无内容时不渲染
> - 行间间距：16px；列等宽（无主次）
> - 适用：FLASH / PIPE / PUMP 等计算密集型模块
> - 槽位传入 `ReactNode`，由各 Page 自由填充
>
> 共享约束：UI 元素布局遵循本节；颜色 / 圆角 / 间距用 tokens.css 现有 `--surface-bg-*` / `--radius-md` / `--gap-md`

P4.5 收口报告（commit 3234012 后）需补充该章节后再纳入 SPEC 正式版本。

---

## P5 契约冻结点

批 3 所有计算页面（FLASH / PIPE / PUMP / PIPE_NET）的 V1 mock props shape 由前端手写 type 支撑（已加 `TODO(api-migration)`）。当 P5-1 后端交付时，按下列节点冻结契约：

| 阶段 | 节点 | 负责方 | 持续时间 | 交付物 |
|---|---|---|---|---|
| 1 | P5-1 calculate 入口交付 | 后端 | T0 | `POST /api/calculate/{module}` OpenAPI 已签入 |
| 2 | 前端 type 重新生成 | 前端 | T0 + 1d | `npm run api:gen` → `src/types/api.d.ts` 更新 |
| 3 | 手写 type 替换 | 前端 | T0 + 1~2d | `types/stream.ts` 等删除；Page-level props 改用 `api.d.ts` DTO |
| 4 | MSW handler 重写 | 前端 | T0 + 1~2d | `mocks/handlers.ts` 按新 OpenAPI schema 改 response shape |
| 5 | 联调 | 前端 + 后端 | T0 + 3d | 6 Page 端到端走真实 API |

**冻结触发**：P5-1 PR 合并到 main 后开 issue "批 3 mock → API 迁移"（T0）。

**未冻结的边界 case**：
- HEAT 模块（PSV / HTRI）独立 P5-HEAT 计划，详见未解决问题 7。
- Stream tag_number / stream_id 等路径参数不进 OpenAPI body schema，需前端 mock 自维护直到 P5-1 加 query schema。

---

## 任务顺序（修订版）

按审查问题 7 调整（考虑 PUMP 依赖 PIPE 压降；PIPE_NET 依赖 PIPE）：

| # | Task | 模块 | 工期 | 依赖 |
|---|---|---|---|---|
| 1 | Task 27 P45-3-0 | Shell | 0.5d | — |
| 2 | Task 28 P45-3-1 | SIM 物流 | 1d | — |
| 3 | Task 30 P45-3-3 | COMMON | 1d | — |
| 4 | Task 29 P45-3-2 | PIPE_CLASS | 1d | — |
| 5 | Task 35 P45-3-8 | PMS/BEDD/项目向导 | 1d | Task 27 |
| 6 | Task 31 P45-3-4 | FLASH | 1d | Task 30（物性） |
| 7 | Task 32 P45-3-5 | PIPE 计算 + 一览表 | 1.5d | Task 27 + Task 29 |
| 8 | Task 34 P45-3-7 | PUMP | 1d | Task 32（PIPE 压降） |
| 9 | Task 33 P45-3-6 | PIPE_NET | 1.5d | Task 32 + Task 35 |

总工期 ~9d，4 个任务可与 PMS/BEDD 并行（详见 Execution Handoff）。

---

## 测试数量基线（修订版）

按审查问题 9 修订：基础页面 ≥10 测试；列表 / 表格类 ≥12；计算 / 拓扑类 ≥15；PIPE 一览表 / PIPE_NET 拓扑 ≥20。

| 任务 | 测试基线 | 备注 |
|---|---|---|
| Task 27 Shell | 10 | PageHeader / ModuleLayout 各自独立 |
| Task 28 SIM | 18 | 列表 7 + 详情 6 + 导入向导 5 |
| Task 29 PIPE_CLASS | 16 | 列表 6 + 设计器 7 + 符号表 3 |
| Task 30 COMMON | 13 | PropertySearch 5 + AllowableStress 3 + ToxicityExplosivity 5 |
| Task 31 FLASH | ≥10 | 计算路径 + 不收敛分支 + 4 种热力学方法 |
| Task 32 PIPE | ≥20 | 一览表 41 列 + 计算结果卡 + 多工况分支 |
| Task 33 PIPE_NET | ≥20 | 拓扑节点 / 边 / 校验 / 序列化 |
| Task 34 PUMP | ≥15 | 多结果卡（NPSHr / 扬程 / 功率 / 汽蚀） |
| Task 35 PMS/BEDD | ≥15 | 单位制切换 / 设计条件表单 / 项目向导步骤 |

总计 ≥127 条。

---

## Execution Handoff

**计划完成。** 保存于 `docs/superpowers/plans/2026-09-16-p45-frontend-sprint-batch3.md`。

**两种执行方式：**

1. **Subagent-Driven（推荐）** — 每 task 派新 agent（fresh context），两阶段（实施 → 审查）
2. **Inline Execution** — 本 session 用 `superpowers:executing-plans` 批量，checkpoints 暂停

**关键提醒：**
- 复用 P45-1 / P45-2 组件库，不发明新组件
- 每 task 一 commit；约定式提交 + Co-Authored-By
- ruff 0 / eslint 0 / tsc 0 / vitest 全绿 才提交
- mock-first；P5 接口就绪后切换 metaApi（解耦点保留）