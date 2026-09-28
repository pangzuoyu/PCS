# PCS — 工艺专用综合计算软件

Web 版工艺计算平台：模拟数据导入 → 工艺计算 → 校审签章 → 计算书自动生成。

工艺室场景下的管道、泵、安全阀、闪蒸等工艺计算全流程系统，按两层模型组织：**计算记录**（数据正确性门禁）与**交付物**（发布签署）。术语集见 [`CONTEXT.md`](./CONTEXT.md)。

## 技术栈

| 层 | 选型 |
|---|---|
| 前端 | React 18 + TypeScript + Vite + Ant Design 5 + Zustand |
| 后端 | FastAPI 0.115 + SQLAlchemy 2.0 (async) + Alembic + Pydantic v2 |
| 数据库 | PostgreSQL 16 + Redis 7 |
| 鉴权 | LDAP（authlib + ldap3 + PyJWT） |
| 工艺计算 | `chemicals` / `fluids` / `thermo`（ChEDL 生态，本地 vendored） |
| 工程规范 | HG/T 20570.6 / ASME B31.3 / Crane TP-410 / Idelchik Handbook |
| 包管理 | `uv`（Python 3.12+）/ `npm` |
| 容器 | Docker Compose（postgres / redis / openldap） |

## 仓库结构

```
PCS/
├── pcs-backend/              # FastAPI 后端
│   ├── app/
│   │   ├── api/v1/           # REST 端点
│   │   ├── services/         # 业务逻辑（flash/pipe/pipe_net/...）
│   │   ├── models/           # SQLAlchemy ORM
│   │   ├── core/             # 配置、异常基类、门禁
│   │   └── db/               # 会话、引擎
│   ├── alembic/versions/     # 数据库迁移
│   ├── tests/                # pytest（单测 + 集成）
│   ├── vendor/               # ChEDL 本地副本（fluids/thermo/chemicals）
│   └── pyproject.toml
├── pcs-frontend/             # React + TS 前端
│   └── src/
├── docs/
│   ├── adr/                  # 架构决策记录
│   ├── PCS-PLAN-*.md         # 实施计划
│   └── PCS-P*-CLOSE-REPORT.md
├── spec/                     # 需求规格 / 数据字典
├── sample/                   # PRO/II 工程实例（不入 git）
├── infra/                    # 部署相关
├── docker-compose.yml
├── CONTEXT.md                # 项目术语表（ubiquitous language）
└── CLAUDE.md                 # 开发规约
```

## 快速开始

### 1. 启动基础设施

```bash
docker compose up -d              # postgres + redis + openldap
```

### 2. 后端

```bash
cd pcs-backend
uv sync
uv run alembic upgrade head       # 应用数据库迁移
uv run uvicorn app.main:app --reload --port 8000
```

### 3. 前端

```bash
cd pcs-frontend
npm install
npm run dev                       # 默认 http://localhost:5173
```

### 4. 测试

```bash
# 后端（pcs_test 库需先对齐迁移，见 CLAUDE.md）
cd pcs-backend
DATABASE_URL=postgresql+psycopg://pcs:pcs_dev@localhost:5432/pcs_test \
    uv run alembic upgrade head
DATABASE_URL=postgresql+psycopg://pcs:pcs_dev@localhost:5432/pcs_test \
    uv run pytest -q                # baseline 3269 passed / 74 skipped
uv run ruff check .               # 0 错为目标

# 前端（pcs-frontend/）
npx vitest run                     # baseline 548 passed / 54 files
npx tsc --noEmit                   # 0 错为目标
npx eslint src/ tests/            # 0 错为目标

# OpenAPI 契约门禁（G-08，每批末必跑）
bash pcs-backend/scripts/gate_08_openapi_contract.sh --check-baseline
```

## 当前进度

### ✅ 已闭环批次

| 批 | 范围 | 状态 |
|---|---|---|
| 批 0 | P4-0-1/0-2/0-3 数据层 + 审计字段 + 计算入口守卫 | CLOSED |
| 批 1 | P4-1 FLASH（thermo 封装 + 8 calc + API + 落库 + 状态点联动 + SIM 反向写入） | CLOSED |
| 批 2 | P4-2 PIPE（sizing + wall_thickness + 单相压降 + 两相压降 + 链式管道 + outlet_stream） | CLOSED |
| 批 3 | P4-3 PIPE_NET（拓扑模型 + Hardy-Cross 求解器 + API + 落库） | CLOSED |
| 批 4 | P4-4 PUMP（选型 + NPSHa + 曲线插值 + PUMP 链 + 出口物流） | CLOSED |
| P4-TASK0 | 本体论（@lineage D4/D5 + RECORD_TYPE_REGISTRY 完整化 + physical_semantics + importlinter D8 + CI 三方比对基础） | CLOSED |
| **P4.5 批 3** | **前端计算模块 + 项目向导（SIM 物流详情/导入向导、PIPE_CLASS 等级/符号表、COMMON 物性查询/许用应力/毒性爆炸、FLASH/PIPE/PUMP 计算界面、PIPE_NET 拓扑 V1、PMS/BEDD/项目向导；前端测试 ~131 项）** | **CLOSED 2026-09-16** |
| **P5 (a)** | P0 MEDIUM 5 项收口（sync dispose + trace_id 传播 + bug-098 修复） | CLOSED |
| **P5 (b)** | MEDIUM 滚动首批 4 项（proii_parser / PsvPilotOperated / PsvRuptureDisc / alembic backfill / ACHE EnthalpyTable 校验） | CLOSED |
| **P5 (c)** | MEDIUM 滚动次批 5 项（APP ErrorBoundary / VESSEL/SEP PROJECT_ID / VESSEL NaN 兜底 / VESSEL/SEP sign_status 去伪造） | CLOSED |
| **P5 (d)~(g)** | MEDIUM 滚动第三~六批 共 33 项（累计 MEDIUM 48 项全部收口） | CLOSED |
| **P5 (h)** | **LOW/INFO 滚动首批 105 项**（38 个 `docs(p5c-low)` commit，覆盖 7 api/v1 + 7 service + 1 core 文件、11 schema 文件 159 字段中文 description、alembic E501 修复；全栈 ruff 0 错 + pytest 2225 passed） | **CLOSED 2026-09-18** |
| **P6-0/1/2/3** | **工艺覆盖增补（COMMON 加热值 C-06 + VESSEL 重量 C-08 + 部分体积 C-12 + PSYCHRO 饱和 W C-17 + CV Masonelian fl C-24 + 4 张 CONFIG 表 + 6 个新 API）**；pytest 1976+ → 2418 baseline + 3208 after P6-5 | **CLOSED** |
| **P6-4** | **P6-0/1/2/3 增补 5 项 🔴 必做**（COMMON 加热值 CONFIG 表 + VESSEL 重量 service + VESSEL 部分体积 + PSYCHRO 饱和 W + CV Masonelian fl；4 alembic 迁移 + 6 service + 6 API + 24 测试 + GPSA/API 黄金 fixture） | **CLOSED** |
| **P6-5** | **PSYCHRO 增补 3 项**（C-16 甘醇脱水 TEG-only v3 + C-17 显式水含量 + C-18 Hammerschmidt 水合物抑制；V1.3 → V1.5 → V1.6 SPEC 修订 + Hammerschmidt K 标度 OPEN-P6-6A-3 fix + Nielsen 缺口登记 OPEN-P6-6A-11） | **CLOSED 2026-09-23** |
| **P6-6A** | **Worley C-21/C-19/C-16 全栈交付**（15 commits：OPEN-P6-6A-3 K scale fix + OPEN-P6-6A-4 Cd/Y_cr^0.5 + OPEN-P6-6A-7 Y_cr@r_c + 11 Rulings 闭环；C-21 PSV fire coeff API 521 §3.4 + AS 1210 §4.4 path (a) + Ruling 14 ΔH_vap + Ruling 15 fire_case coeff/exp；C-19 排污孔板 sizing inverse POST API；C-16 glycol dehydration v4 Ruling 5 OUT_OF_SCOPE 12 fields + ADR-0045 Rev A K=7.1187 单点标定 + Day-0 Gate 形式决策 + brentq 逆 dewpoint + Linear placeholder 三铁律 + JSON 启动期加载；post-merge spot-check 376 psv + 11 glycol integration tests PASS） | **CLOSED 2026-09-28** |
| **P6-6B** | **数据源替换批（13 commits）**：9 张 CONFIG 表 metadata 闭环（compound_heating_values T1 64 行 / pipe_E_modulus T3 8 行 / pasquill_sigma T4 6 行 / api521_thresholds T5 2 行 / iso9613 T6 4 行 / hammerschmidt_K T7 5 行 / nielsen_1988_params T8 7 行 + service 备选 path / glycol_dehydration_full_system T9 10 行 + OUT_OF_SCOPE docs 引用 / delta_h_vap_natural_gas T12 2 行 + service 双字段切换 / drain_orifice_Cd_Y_cr T13 6 行 + service feature flag + R=1 fix 集成）；OPEN-P6-4-1 关闭 + OPEN-P6-6A-4/5 形式关闭 + OPEN-P6-6A-6 部分关闭；T2 _VALVE_LIBRARY 真实 Kb 推迟到上线后（OPEN-P6-4-2）；T10/T11 service 集成路径决策待工程团队；G-08 phase 1-4 全过、pytest 各模块 0 break、ruff 0 errors on touched files、pcs_test head `p6_6b_013_drain_orifice_Cd_Y_cr` | **CLOSED 2026-09-28** |
| **P6-7** | **服务集成批（10 commits active，T5 + T2 partial）**：工艺室 3 批交付物服务代码集成 + ADR-0045 Rev B 实施；C-08 V1.2 redesign 路径（A）→ 两相分离器 sizing imperial 测试；C-18 Nielsen 1988 完整方程组 + gas_composition + brine（OPEN-P6-6A-11 闭环）；C-24 CV Masonelian 3-model + 24 厂商库（OPEN-P6-4-4 部分关闭）；T10 字段名 `_c` → `_f` + 派生（OPEN-P6-6A-3 真正关闭）；T11 fire_case 分 path + 放弃 2.457（OPEN-P6-6A-5 真正关闭）；Bukacek 1990 T<60°F 延伸（OPEN-P6-6A-9.4 闭环）；C-16 Behr baseline 选择（OPEN-P6-6A-9.3 + 9.5 部分关闭）；AS 1210 path (b) + Jet fire（OPEN-P6-6A-10 代码侧就位）；pytest 386+ psv / 35+ psychro 各模块 0 break / ruff touched files 0 errors / vitest 548/548 / schema sync test_table_count 88 → 93 | **CLOSED 2026-10-31** |
| **P6-8** | **glycol dehydration service 集成批（5 commits active）**：工艺室 2026-10-31 4 子模块计算逻辑服务集成 + ADR-0045 Rev B 实施；Reboiler Duty 完整焓平衡 + WARNING `TEG_CIRCULATION_RATE_UNVERIFIED` + Stripping Gas Rate GPSA §20.4 Eq.20-5 + v5 plan Antoine + Full Column Diameter K=7.1121 6 工况标定 + Lean Glycol Concentration GPSA Fig 20-4 4 数据点插值；API 端点 4 outputs + WARNING 字段 + OpenAPI regen drift=0；OPEN-P6-6A-6 代码侧闭环；3 项 limitation 待工艺室 2026-11-15 对账（Reboiler Duty TEG 循环量 / Antoine 系数 DIPPR 验证 / Lean Glycol 完整曲线） | **CLOSED 2026-11-15** |

### ⏳ 待启动批次

- **P6-7**（OPEN-P6-6A-6 后续）：glycol dehydration service 4 子模块扩展（reboiler / stripping / full column / lean glycol）+ T9 CONFIG 典型工况范围已就位
- **OPEN-P6-6A-9.1~9.4**（P6-6B 工程团队接管）：C-16 glycol 工程任务（30× 差异根因完整验证 / K=7.1187 多工况标定 / 真 Wichert-Aziz 非线性形式 / brentq low-T Bukacek 1990 extension）
- **OPEN-P6-6A-10**（P6-6B 工程团队接管）：PSV C-21 AS 1210 §4.4 path (b) gas/vapor m·Y_p + Jet fire 110,000 W/m²（V1.12 docs 主题预留）
- **OPEN-P6-6A-11**（P6-6B 工程团队接管）：C-18 Nielsen 方程覆盖缺口（MeOH ≤50 wt% 切 Nielsen + WARNING，~1.0 天，**P6-6B T8 已部分落地 Nielsen 备选 path，A/B/C 精度待工艺工程师二次核对**）
- **P6-6B T10/T11 决策路径**（工程团队接管）：Hammerschmidt K_F→K_C service 集成 + API 521 → AS 1210 service 集成

### 已落地工艺能力

- **闪蒸（FLASH）**：PT/PH/PS_FLASH + BUBBLE_P/T + DEW_P/T + SATURATION（4 thermo 体系：PRMIX / SRKMIX / NRTL / CoolProp iapws95）
- **管道**：预定流速法 / 设定压力降法（HG/T 20570.6-95）+ ASME B31.3 壁厚 + 18 OD 档 Sch 表 + 单相 Darcy-Weisbach + 两相 Lockhart-Martinelli-Baker
- **管网**：拓扑校验 + Hardy-Cross 流量分配 + 节点压力回推
- **精度护栏**：3 流态分支（LAMINAR / TRANSITION 2000–4000 强制 WARNING / TURBULENT）+ confidence HIGH/MEDIUM/LOW + Crane TP-410 K 表 reynolds_applicable 标注 + get_fitting_k Re 参数预留（P5+ Hooper 2-K / Darby 3-K 接入）
- **COMMON 物性 + 加热值**（P6-4 C-06）：GPSA FIG. 23-2 化合物热值 HHV/LHV 双单位 + 化学计量空气 + 烟气组成（CO₂/H₂O/N₂/SO₂）+ Mendeleev 自研 fallback；64 种化合物 seed + `compound_heating_values` CONFIG 表
- **VESSEL 重量 + 部分体积**（P6-4 C-08/C-12）：立/卧/球 × 4 封头 5 段累加（shell cylinder + heads + nozzles + skirt/saddle）+ 4 封头部分体积 + 润湿面积 + 质量 iteration Newton/bisection
- **PSYCHRO 饱和 W + 甘醇脱水 + 水合物抑制**（P6-4/5/6A C-17/C-16/C-18）：
  - 饱和水含量 = RH=1.0 直调 CoolProp HAPropsSI（ASHRAE RP-1845 溯源）
  - FULL 甘醇脱水系统（`POST /psychro/glycol-dehydration/calculate`）：TEG only + 12 OUT_OF_SCOPE fields（water_dewpoint_f / adjusted_dewpoint_f / lean_glycol_concentration / stripping_gas_scf_per_gal_teg / column_diameter_full_in / column_height_ft / number_of_transfer_units / mass_h2o_removed_lb_s / reboiler_duty_btu_hr / column_csa_ft2 / dewpoint_unavailable_reason / acid_gas_corrected）+ Behr 逆算 + ADR-0045 Rev A K=7.1187 + Linear placeholder 三铁律
  - 水合物抑制 Hammerschmidt 1934 温降公式（MeOH ≤25 wt% / EG ≤60-70 wt%）；Nielsen 方程待 OPEN-P6-6A-11 补
- **CV Masonelian fl + 阀门厂库**（P6-4 C-24）：3 模型并存（Masonelian 1973 Eq.5 + Chapman-Jans + Tong）+ 24 阀门厂组合 GL/BALL × MASONELIAN/FISHER/CROSBY/IMO/DRESSER + flash_steam_rate
- **PSV 火灾泄放**（P6-6A-5 C-21）：API 521 §3.4 default 43192 + AS 1210 §4.4 path (a) 7.2×10⁴ 液化 + fire_case coeff/exp 双字段（Ruling 15 闭环）；path (b) gas/vapor + Jet fire 110,000 W/m² 待 OPEN-P6-6A-10
- **限制孔板（Restriction）**（P6-6A-4/7 C-19）：Cd/Y_cr^0.5 + Newton/bisection sizing inverse POST API + Y_cr@r_c 物理修正（bug-105）
- **血缘与哈希**：record_hash 数值规范化 16 hex + DataLineage 只追加 + finalize_calc_record 统一收口
- **前端模块**（P4.5 批 3 + P6-5 补课）：SIM 物流导入向导 + 详情页 / PIPE_CLASS 等级 + 符号表 + 代码格式设计器 / COMMON 物性查询 + 许用应力 + 毒性爆炸 + 加热值（`HeatingValuePage`）/ FLASH/PIPE/PUMP 计算界面 / PIPE_NET 拓扑 V1（手写 SVG）/ PMS 管道材料规格 + BEDD 文档 + 项目向导 / PSYCHRO 饱和水含量（`SaturationWaterContentPage`）/ CV 控制阀（`CvComputePage`，含 Masonelian fl 3 字段）；StateBadge 9 态 + SignatureMatrix 共享组件 + ModuleLayout 2×2 网格；vitest 548 passed / 54 files
- **状态机双轨**：记录级 9 态机（DRAFT/IN_APPROVAL/CHECKED/CHECK_REJECTED/STALE/CHANGE_PENDING/CHANGED/REVERSAL_PENDING/OBSOLETE，StateMachineService.transition 驱动）+ 资源级 5 态机（DRAFT/PENDING/APPROVED/PUBLISHED/OBSOLETE，ConfigStateMachine 驱动公司模板 + 项目级轻量状态机）
- **配置资产**：公司管号模板 / 管架 / 流股符号三资源均挂 ConfigAsset（V1.4 §0.5 INT-OPEN-01），走 fork → project → 5 态机全流程；FMT-9 条规则验证 + PSV-22 字段完整闭环
- **OpenAPI 契约门禁 G-08**：3 阶段 regen + 1 阶段 baseline 一致性（`pcs-backend/scripts/gate_08_openapi_contract.sh`），163 paths / 207 schemas / 0 drift；pre-commit 自动跑
- **文档完整度**（P5 批 h LOW/INFO 滚动 + P6-6A SPEC V1.11→V1.12 wording-only 6 修订）：38 个 `docs(p5c-low)` commit 闭环 105 项公共 API docstring；V1.12 wording 增补 C-16 12 result fields + C-19 Rulings 12/13 闭环链 + C-17 OPEN ID fix + C-21 OPEN-P6-6A-10 新立 + ATT-02 标题同步

### Backlog（OPEN 队列）

- **OPEN-P6-4-2**（P6-6B 入批）：Kb 厂商真实数据（LESER / Consolidated / AG），PSV C-08 Kb 替换
- **OPEN-P6-4-3**（P6-6B 入批）：C-08 vessel 模块 Imperial 单位（lb/ft³）支持范围
- **OPEN-P6-4-4**（P6-6B 入批）：C-24 CV Masonelian fl / Chapman-Jans / Tong 模型与商业软件（Masonelian 官方）正式对账
- **OPEN-P6-6A-6**（待 P6-7）：T8 full glycol dehydration system as new PCS service 扩展
- **OPEN-P6-6A-9.1~9.4**（P6-6B 工程团队接管）：C-16 glycol 工程任务 4 子项（30× 根因 / K 多工况标定 / 真 Wichert-Aziz / brentq low-T）
- **OPEN-P6-6A-10**（P6-6B 入批）：PSV C-21 AS 1210 §4.4 path (b) gas/vapor + Jet fire
- **OPEN-P6-6A-11**（P6-6B 入批）：C-18 Nielsen 方程覆盖缺口，~1.0 天
- **历史 backlog**：Hooper 2-K / Darby 3-K 低 Re K 值修正（get_fitting_k Re 参数预留位）；`fluids.two_phase` Beggs-Brill 交叉校核；`fluids.fittings` K_from_f 交叉校核；ChEDL 版本锁定 ADR（fluids / thermo / chemicals 频繁更新，需复现性）；P4-2-6 热损失 + 混合黏度；PIPE_NET 完整版（reactflow 拖拽 / 自动布局 / 环路检测 / 序列化）

详细收口报告见 `docs/PCS-P*-CLOSE-REPORT.md`；延后项见 [`TODOS.md`](./TODOS.md)。

## 核心约定

- **两层模型**（ADR-0001）：计算记录（数据门禁 9 态：DRAFT / IN_APPROVAL / CHECKED / CHECK_REJECTED / STALE / CHANGE_PENDING / CHANGED / REVERSAL_PENDING / OBSOLETE）+ 交付物（签署矩阵）
- **物流与设备连接**（ADR-0019~0022）：设备是物流间的转换函数，不是一条物流的内部环节；出口物流由设备计算自动创建（`source_type=DEVICE_CALCULATED`，`sign_status=DRAFT`）
- **位号终身唯一**：管道号 / 设备位号一旦分配终身占用（含 OBSOLETE），永不释放复用
- **实质变更**：以重算后 record_hash 是否变化为准，不以上游数据是否变动为准
- **三处历史**：变更前快照 / 交付物版本绑定 / 审计日志（废除 xxx_History 快照流水表）

详见 [`CONTEXT.md`](./CONTEXT.md) 与 [`docs/adr/`](./docs/adr/)。

## 开发规约

- 全程中文注释与报错；枚举值 / 代码标识英文
- 提交约定式（`feat/fix/refactor/test/docs/chore`）
- ruff 0 错为合并前置
- 单人开发直提 main，无 worktree（用户长期裁决）
- 每个 task 一 commit；每批一收口报告

详见 [`CLAUDE.md`](./CLAUDE.md) 与项目内 `.claude/rules/`。

## 许可证

仓库代码仅供学习与个人研究使用。PRO/II 工程实例位于 `sample/`（不入 git）。
