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
    uv run pytest -q
uv run ruff check .               # 0 错为目标
```

## 当前进度

### ✅ 已闭环批次

| 批 | 范围 | 状态 |
|---|---|---|
| 批 0 | P4-0-1/0-2/0-3 数据层 + 审计字段 + 计算入口守卫 | CLOSED |
| 批 1 | P4-1 FLASH（thermo 封装 + 8 calc + API + 落库 + 状态点联动 + SIM 反向写入） | CLOSED |
| 批 2 | P4-2 PIPE（sizing + wall_thickness + 单相压降 + 两相压降 + 链式管道 + outlet_stream） | CLOSED |
| 批 3 | P4-3 PIPE_NET（拓扑模型 + Hardy-Cross 求解器 + API + 落库） | CLOSED |

### ⏳ 待启动批次

- **批 4**：P4-4 PUMP（泵选型 + NPSHa + 泵曲线插值 + PUMP 链 + 出口物流）
- **P4-TASK0**：本体论（@lineage、RECORD_TYPE_REGISTRY 完整化、physical_semantics、importlinter、CI 三方比对）— **P4 验收前必须关闭**

### 已落地工艺能力

- **闪蒸（FLASH）**：PT/PH/PS_FLASH + BUBBLE_P/T + DEW_P/T + SATURATION（4 thermo 体系：PRMIX / SRKMIX / NRTL / CoolProp iapws95）
- **管道**：预定流速法 / 设定压力降法（HG/T 20570.6-95）+ ASME B31.3 壁厚 + 18 OD 档 Sch 表 + 单相 Darcy-Weisbach + 两相 Lockhart-Martinelli-Baker
- **管网**：拓扑校验 + Hardy-Cross 流量分配 + 节点压力回推
- **精度护栏**：3 流态分支（LAMINAR / TRANSITION 2000–4000 强制 WARNING / TURBULENT）+ confidence HIGH/MEDIUM/LOW + Crane TP-410 K 表 reynolds_applicable 标注 + get_fitting_k Re 参数预留（P5+ Hooper 2-K / Darby 3-K 接入）
- **血缘与哈希**：record_hash 数值规范化 16 hex + DataLineage 只追加 + finalize_calc_record 统一收口

### Backlog（P5+）

- Hooper 2-K / Darby 3-K 低 Re K 值修正
- `fluids.two_phase` Beggs-Brill 交叉校核
- `fluids.fittings` K_from_f 交叉校核
- P4-TASK0：record_hash 扩展至 two_phase_results + formula_version 列
- ChEDL 版本锁定 ADR（fluids / thermo / chemicals 频繁更新，需复现性）
- P4-2-6：热损失 + 混合黏度
- 控制阀 / PSV（独立批次，不在 P4 范围）

详细收口报告见 `docs/PCS-P*-CLOSE-REPORT.md`。

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
