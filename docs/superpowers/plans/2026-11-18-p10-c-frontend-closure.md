# P10-C 子批「前端收口」：P10-B 扫描留下的四条缺口 · 2026-11-18

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 关掉 P10-B 的真后端路由扫描撞出来的四条缺口 ⇒ **TODO-160**（三页首屏 422）· **TODO-159**（三个页面调了不存在的端点）· **TODO-157**（前端没有设备台账页）· **TODO-156**（PRO/II 解析器不抽组成 ⇒ 导入的物流进不了计算链）。

**为什么单开子批**：这四条原本挂 **P10-C**，而 P10-C 主体是「**部署与可观测性**」（exporters · 监控栈 · 状态页 · 备份演练）⇒ ⇒ 四条塞进去会让它的验收清单失焦 ⇒ ⇒ **人裁决（2026-11-18）：单开「前端收口」子批**。
⇒ ⇒ ⚠️ **本子批不依赖 P10-C 的部署物**（不需要镜像 / 监控栈 / PG 车道）⇒ ⇒ **现在就能开** ⇒ ⇒ 与 P10-C 主体**并行**（P10-C 主体 + F4 仍被「有没有可扫的部署物」卡着）。

**Tech Stack:** React 18 · antd 5 · TypeScript · FastAPI · pytest（asyncio_mode=auto）· Playwright（真后端通道）

**Spec:** `docs/PCS-UI-SPEC.md`（V1.0 冻结 · 前端唯一编码依据）· 字段/枚举/权限/错误码以 **OpenAPI + meta API** 为准（与 SPEC 冲突时以 OpenAPI 为准并登记 SPEC 修订）· 批次地图 `docs/superpowers/plans/2026-11-04-p10-master-plan.md` §二

---

## 任务清单（开工时把每个任务写成 TDD 步骤）

### T1 · TODO-160 —— 物性 / 许用应力 / 毒性三页**首屏 422** 🟡

`/common/properties` · `/common/stress` · `/common/toxicity` 首屏就发**空查询** ⇒
`GET /api/v1/common/materials/search` · `/api/v1/common/allowable-stress` · `/api/v1/common/safety` 全 **422**。

⇒ ⇒ **两条修法**：① 前端首屏**不发请求**（等用户填条件）② 前端按契约补参数 ⇒ ⇒ **先对 OpenAPI**（契约说哪些必填）。

- [x] 对 OpenAPI 确认三个端点的必填参数与 422 的触发条件
      ⇒ `keyword` / `material`+`temp_c` / `cas`（**都必填**）⇒ ⇒ 走 ①
- [x] 裁决走 ① 还是 ② ⇒ ⇒ **走 ①**（首屏不发请求）⇒ ⇒ 不改契约
      ⇒ ⇒ 但**顺带发现两处形状错**（`allowable-stress` / `safety` 返**单个对象**
      ⇒ ⇒ 前端当数组用）⇒ ⇒ 已纠正
- [x] 改前端 + 补一条断言（首屏**不发请求**）
      ⇒ ⇒ 三页改「**填条件才查**」（300ms 防抖）+ 页面自取（axios 通道）
      ⇒ ⇒ MSW mock **同步收紧**（缺参数 ⇒ 422 · 命中不到 ⇒ 404）
      ⇒ ⇒ 断言写在**调用参数**上 ⇒ ⇒ 漏参数必红
- [ ] 真后端通道回归（`npm run e2e:real`）⇒ 三页首屏**无错误态**
      （**批末统一跑** · 白名单已删 ⇒ 任何 4xx/5xx 都会红）

### T2 · TODO-159 —— 三个页面调了**不存在的端点** 🟠

管道一览表 `/pipe/line-list` → `GET /projects/{id}/pipe-line-list` · PMS 规格 `/pms` → `GET /projects/{id}/pms` ·
BEDD 文档 `/bedd` → `GET /projects/{id}/bedd` ⇒ ⇒ **全 404**。
⚠️ **既有缺口**（不是 P10-B 引入）⇒ mock 通道里 **MSW 有 handler** ⇒ 一路绿灯 ⇒ **只有真后端通道能抓到**。

⇒ ⇒ **先查契约**（`docs/openapi.json` 里有没有等价端点）⇒ ⇒ 有 ⇒ **改前端指向**；没有 ⇒ **补后端端点**（或明确「这三页是占位」并在前端说明）。

- [x] 查契约 ⇒ ⇒ 定「改前端指向」还是「补端点」
      ⇒ ⇒ **三个端点都不存在** ⇒ ⇒ 「改前端指向」走不通
      （`GET /records/piping` 只返 5 字段 ⇒ 一览表要 43 列）
      ⇒ ⇒ **分两种处置**：管道一览表**补端点** · PMS/BEDD**明确占位**
- [x] 落改（补后端端点 `GET /projects/{project_id}/pipe-line-list` + OpenAPI 快照同步）
      ⇒ ⇒ 新增 `app/api/v1/pipe_line_list.py` + `app/schemas/pipe_line_list.py`
      ⇒ ⇒ 列 = **SPEC §7.11.2 的 43 列**逐条对应 `piping_results`
      ⇒ ⇒ 前端新增 `useProjectScope` hook（**不再用占位 project id**）
      ⇒ ⇒ `PipeLineListRow` 改成**契约类型**（作废 4 个幽灵列）
- [x] **把断言加回** `pcs-frontend/e2e/real_backend_route_sweep.spec.ts`
      ⇒ ⇒ 白名单的 **TODO-159 三条已删** ⇒ ⇒ **白名单现在是空的**
      ⇒ ⇒ 任何 4xx/5xx 都会红
- [x] ⇒ ⇒ 顺带核对 **MSW mock handler 与契约是否一致**
      ⇒ ⇒ **mock 的形状改成契约形状**（此前是前端手写的 25 列）
      ⇒ ⇒ 并给这个端点补了 **ajv 校验**
      ⇒ ⇒ ⚠️ **顺带挖出一个三年的洞**：棘轮拿 MSW 的 `:param` 路径比契约的
      `{param}` 路径 ⇒ ⇒ **永远不相等** ⇒ ⇒ `:param` 写的端点它全看不见
      ⇒ ⇒ 归一化后**多出 14 条**欠账 ⇒ ⇒ 登记 **TODO-193**

### T3 · TODO-157 —— 前端**没有设备台账页** 🟡

后端有 `GET /api/v1/equipment-list`（`app/api/v1/equip_list.py`）· 种子也造了设备 ⇒ ⇒ **前端无对应页面**
⇒ ⇒ `src/types/api.d.ts` 里有生成的类型、**没有任何组件消费它** ⇒ ⇒ 「设备一览」页列的是 **`ConfigAsset`**（配置资产），
**不是 `EquipmentList`（设备台账）** ⇒ ⇒ 两条「设备」概念在 UI 上**只有一条可见**。

⚠️ **要人裁**：① 补一页设备台账 ② 明确「设备一览 = ConfigAsset」且设备台账**只走 API**。
若补 ⇒ ⇒ 要定：列表字段（位号 / 类型 / 厂家）· 项目作用域（`equipment_type_project_id`）· 与「冷却水子表」「换热器」里手填 `equipment_tag` 的关系。

- [x] 人裁 ①/②（**产品语义 ⇒ 不由执行者代裁**）
      ⇒ ⇒ **2026-11-19 人裁决：① 补一页设备台账**
- [x] 若 ①：建页 + 路由 + 契约类型消费 + 一条断言（种子设备 `132-P-101A/B` 可见）
      ⇒ ⇒ 新页 `/equipment-list`（菜单「设备台账」**独立成组**）
      ⇒ ⇒ 列 = **契约 `EquipListResponse`** 的字段（SPEC §7.13 的「包号/单元/
      计算状态」契约里没有 ⇒ ⇒ **不编** ⇒ ⇒ 登记 SPEC 修订）
      ⇒ ⇒ 真后端扫描加了「**种子设备 `132-P-101A/B` 可见**」的断言
      ⇒ ⇒ ⚠️⚠️ **顺带补上两个跨项目洞**（建页时撞出来的）：
      ① **读**：`GET /equipment-list` 此前**只有角色闸** ⇒ ⇒ 任何 DESIGNER
      都能列**全部项目**的设备台账 ⇒ ⇒ 现在传 `project_id` ⇒ 查授权（无权 404）
      · 不传 ⇒ 只返回**我被授权的项目**的设备（SYSTEM_ADMIN bypass）
      ② ⚠️⚠️ **写**（**更严重**）：**sync** 的写入落在**源记录的 `project_id`**
      上 ⇒ ⇒ 单条 sync 此前**只**查了 equipment 行的项目 ⇒ ⇒ **跨项目写**
      （与 TODO-180 同形）⇒ ⇒ bulk-sync **完全没查** ⇒ ⇒ 现在：单条 ⇒ 无权 ⇒
      **404**；bulk ⇒ ⇒ 逐条预检 ⇒ 无权 ⇒ 标 `failed` 且**不写**
      ⇒ ⇒ 8 例新测试（含**三处变异自证**）
      ⇒ ⇒ **教训**：写面守卫要判「**行实际落到哪儿**」

### T4 · TODO-156 —— PRO/II 解析器**不抽组成** ⇒ 导入的物流进不了计算链 🟡

⚠️ **本条是后端项**（`app/services/import_service.py:135` 明写「PRO/II parser 当前不提取 composition」）⇒ ⇒ **搭车收口**（用户裁决把四条放同一批）⇒ ⇒ 批的验收里它单列。

⚠️ **门禁**：组成门禁（`app/api/v1/streams.py::_composition_gate`）要求 **100±0.5%** ⇒ ⇒ 解析出的摩尔分率**必须归一** ⇒ ⇒ 否则送审直接 422。

- [x] 解析 `.inp` 的**组分表** ⇒ 写进 `composition_json`（摩尔分率）⇒ ⇒ **归一**
      ⇒ ⇒ ⚠️ **基准（M/W）必须保留**（`COMPOSITION(M)` 摩尔 · `(W)` 质量）
      ⇒ ⇒ 数值是**百分数** ⇒ ⇒ `/100`
      ⇒ ⇒ 新增 `component_cas.py`（规范名 → CAS · **域数据**）+
      `proii_composition.py`（换算 · 归一 · **fail-closed**）
- [x] 一条断言：导入带组成的 PRO/II ⇒ `composition_json` 非空且**摩尔分率和 = 100±0.5%**
      ⇒ ⇒ 新 fixture `sample6_composition`（M 流 / W 流 / 认不出的组分流）
      ⇒ ⇒ 6 例新测试 + **三条变异自证**（丢基准 / 不落组成 / 去掉 fail-closed）
- [x] SPEC §3.2.2 的 E2E-002「导入 ⇒ 物性补全」**中间那一环**被覆盖
      ⇒ ⇒ ⚠️ **CAS 号待工艺室确认** ⇒ ⇒ 登记 **TODO-196**

### T5 · 闸门与证据

- [x] 前端 `npm run typecheck` clean · `npm run lint` clean · `npm run test`（vitest）≥ 上批 baseline
      ⇒ ⇒ typecheck clean · lint clean · vitest **1091/1091**（上批 1089）
- [x] **真后端通道**（`bash pcs-backend/scripts/serve_e2e_backend.sh` + `npm run e2e:real`）⇒ ⇒ T1/T2/T3 三处**断言**绿（不是「只打印」）
      ⇒ ⇒ **白名单现在是空的** ⇒ ⇒ 任何 4xx/5xx 都会红
      ⇒ ⇒ **批末实跑：9/9 passed**（`BAD_RESPONSES=[]` · `CONSOLE_ERRORS=[]` · 46 条路由全可达）
      ⇒ ⇒ `/equipment-list` 断的是**种子设备的位号 `132-P-101A/B`** ⇒ ⇒ 一条断言同时验了
      真端点 + 项目作用域解析（`VITE_PROJECT_ID` → `FLOW_PROJECT_ID`）+ 页面渲染
- [x] 后端默认车道（`uv run pytest`）exit 0（T4 动了 `import_service`）
      ⇒ ⇒ **5923 passed · 139 skipped · EXIT=0**（T3/T4 落地前 5906）
- [x] 契约门禁 `gate_08_openapi_contract.sh --check-baseline` RC 0（基线已滚动）
      · 迁移幂等 `check_migration_idempotency.py` RC 0（49 个迁移 0 违反）
- [x] `TODOS.md` 四条**逐条**标「已关闭 · `<commit>`」
      ⇒ ⇒ TODO-156 / 157 / 159 / 160 **逐条**已标
      ⇒ ⇒ 连带登记 **TODO-193 / 194 / 195 / 196**

---

## 候选（**未获裁决** ⇒ 本批不做 ⇒ 只登记）

- **TODO-167** 🟡 前端还有别处把**占位常量**当真项目 id 用（归属 P10-F · 与 TODO-159 同族）⇒ ⇒ **建议并入 T2**（同一类「mock 绿灯 / 真后端 404」）。
- **TODO-115** 🟢 多数物流在 `data_lineage` 里**没有行** ⇒ 血缘 Tab 显示 404（归属「下一批 · 血缘 Tab 收口」）。
- **TODO-109/110/111** 🟡 契约面统一收口（手写轻量子集 / 裸 object / 裸 dict）⇒ ⇒ **量太大 ⇒ 不塞本批**。

## 未解决的问题

1. **TODO-157 的 ①/② 是产品语义** ⇒ ⇒ **等人裁**（执行者不代裁）。
2. **TODO-159 若选「补后端端点」** ⇒ ⇒ 那是**新端点**（属新功能）⇒ ⇒ 需另立契约变更记录 + SPEC 修订登记 ⇒ ⇒ 本批的体量会变。
3. **TODO-156 与「PROII 解析补组成」** 是否同一件事 ⇒ ⇒ 前者是**后端解析器**，后者在 SPEC 的 E2E-002 描述里 ⇒ ⇒ 若另有批次承接，**本批只做解析器**。
