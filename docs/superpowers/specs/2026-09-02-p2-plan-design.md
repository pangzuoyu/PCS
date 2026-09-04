# P2 Plan Design

**日期**：2026-09-02
**作者**：Claude Code
**基准 spec**：PCS-SPEC-P2 V1.0 + PCS-SPEC-P2-SUP-001 V1.0 + PCS-DICT-ALL-003 V3.4 + ADR-0023~0025 + P1-MVP 交付报告
**规划粒度**：P2 全周期（单 plan，覆盖 Sprint 1~4）
**已闭合**：P2 Sprint 1 Step 0（配置层 8 表 ORM 对齐 DICT V3.4 + audit_logs/data_lineage V3.4 重写 + 21 处命名偏差裁决 + 13/13 表零漂移）

## 1. 已裁决的关键决策（D-question 记录）

| ID | 问题 | 裁决 |
|---|---|---|
| D14 | P2 Sprint 1 启动顺序 | **A 横向骨架优先** — 先建 ConfigAsset/ConfigVersion/ConfigApproval CRUD + 配置状态机 + AuditAction 8 项枚举（~3 天），再依次接公式/系数/模板 |
| D15 | 配置层 ACL 策略 | **LDAP 角色 + 项目组成员** — DRAFT 任意 DESIGNER；PUBLISH 需 PROCESS_CONTROLLER + SYSTEM_ADMIN；复用现有 `workspaces` 表定义项目组成员关系 |
| D16 | `formula_definitions` schema（unit_tests_json + parameters_json） | 见 §3.2 锁定 — unit_tests_json 为对象数组 `{params, expected, tolerance}`；parameters_json 为 `{parameters: [{name, unit, description, min, max, default}]}` |
| D17 | 热更新策略 + pass rate 门槛 | **无缓存设计 + 100% pass 硬门槛** — 不引入进程级/Redis 缓存；公式每次计算从 DB 加载（天然热更新）；PUBLISH 强制 100% pass，否则拒绝进 PUBLISHED |
| ~~D18~~ | （不存在，已删除） | — |

## 2. 架构总览

### 2.1 Sprint 拆分 + 依赖图

```
P2 Sprint 1 ─ 配置层主体 ────────────────────────────────────┐
  1.1 基础设施 ─ ConfigAsset/Version/Approval + 状态机骨架   │
  1.2 公式引擎 ─ SymPy + AST + 热更新 + unit_tests_json      │ ~3 周
  1.3 系数库   ─ CRUD + 批量修改                              │
  1.4 模板管理 ─ 文件上传 + 占位符解析                         │
  1.5 编号模板 ─ segments_json + 并发自增（UQ 保护）          │
                                                              │
P2 Sprint 2 ─ equipment_list 42 字段对齐 ───────────────────┤
  3 个 alembic migration + ORM 同步 + DICT V3.5              │ ~3h
                                                              │
P2 Sprint 3 ─ 集成层 ────────────────────────────────────────┤
  CIA 双模式传播（config_version_id → 下游 STALE）           │ ~1 周
  audit_logs.action 接入 8 项新枚举                            │
  workspace 边界声明（CONFIG 全局，无需 require_formal_workspace）│
                                                              │
P2 Sprint 4 ─ 报表 + 导出 ───────────────────────────────────┘
  配置资产状态分布 + 编号模板用量报表 / openpyxl 导出         ~3 天
```

### 2.2 复用矩阵（来自 SUP-001 §4）

| P1 组件 | P2 使用 | 备注 |
|---|---|---|
| `AuditService(session).write()` | 公式/系数/模板修改审计 | 直接复用 |
| `AuditAction` 枚举 | 追加 8 项 CONFIG_*（SUP-001 §6） | `app/models/enums.py` |
| `StateMachineService` | **不复用**（5 态 vs 9 态语义不同） | 新建 `config_state_machine.py` |
| 双引擎 sync+async | 配置 API 全部 async | 复用 P1 基础设施 |
| `commit_or_rollback` | 配置写操作 | 复用 P1 端点模板 |
| `require_formal_workspace` | **不适用**（CONFIG 全局非项目级） | 文档化于 CLAUDE.md |

### 2.3 数据流

```
用户操作 → API endpoint (async) → ConfigStateMachine.transition()
  → ConfigAsset.status 变更 → audit_logs (action=CONFIG_ASSET_*)
  → 公式 CATEGORY_2 时触发 formula_engine.evaluate()
  → unit_tests_json 跑批（100% pass 才允许 PUBLISHED）
  → 公式/系数 PUBLISHED 时通过 data_lineage.source_ref_* 触发下游 STALE
```

## 3. Sprint 1 详细设计

### 3.1 基础设施（1.1）| 项 | 文件 | 内容 | 验收 |
|---|---|---|---|
| 1.1.1 AuditAction | `app/models/enums.py` | 追加 8 项 CONFIG_* | enum 全量测试 pass |
| 1.1.2 ConfigStateMachine | `app/services/config_state_machine.py` | 5 态（DRAFT/PENDING/APPROVED/PUBLISHED/OBSOLETE），transitions 表 | 单测覆盖 SUP-001 §3.2 全部流转（含驳回、作废、双段签回 DRAFT） |
| 1.1.3 双重审批适配 | `app/services/config_state_machine.py` | CATEGORY_2 公式保持 5 态不变；双重审批通过 `config_approvals` 表的两行记录表达：第 1 行 `approver_role=PROCESS_CONTROLLER`，第 2 行 `approver_role=SYSTEM_ADMIN`。两行均 APPROVED → config_asset 状态进 APPROVED；任一 REJECT → 状态回 DRAFT（须创建新 ConfigVersion 重启流程） | 双段签 e2e：APPROVE/REJECT/PARTIAL_REJECT 三路径 |

API 端点（1.6）：
```
POST   /api/v1/config/assets                 # 创建 config_asset (DRAFT)
POST   /api/v1/config/assets/{id}/versions   # 新版本（DRAFT）
POST   /api/v1/config/assets/{id}/submit     # DRAFT→PENDING
POST   /api/v1/config/assets/{id}/approve    # PENDING→APPROVED（CATEGORY_2 走双段签）
POST   /api/v1/config/assets/{id}/publish    # APPROVED→PUBLISHED（含公式 unit_tests 100% pass 校验）
POST   /api/v1/config/assets/{id}/obsolete   # →OBSOLETE
GET    /api/v1/config/assets/{id}/diff?v1&v2 # 版本对比
```

### 3.2 公式引擎（1.2）

**核心组件**：

```python
# app/services/formula_engine.py
class FormulaEngine:
    """公式解析 + 受限执行 + 热更新 + 单测运行器"""

    ALLOWED_NODES = {  # AST 白名单
        # 算术: BinOp, UnaryOp, Num, Name, Constant, Add, Sub, Mult, Div, Pow
        # 函数调用: math.sin/cos/tan/log/exp/sqrt/pow (白名单函数名)
    }

    def parse(self, expression: str, parameters: dict) -> Callable:
        """SymPy 解析 + parameters 命名空间绑定，返回可调用对象"""

    def evaluate(self, expression: str, parameters: dict) -> float:
        """parse + 调用 + 返回 float"""

    def run_unit_tests(self, formula_def: FormulaDefinition) -> TestResult:
        """跑 unit_tests_json（对象数组 [{params, expected, tolerance}]），返回 pass/total"""
```

**安全审计**：
- 拒绝 `import`/`__`/`open`/`eval`/`exec` AST 节点
- fuzz 测试 100 次（随机恶意输入）无 RCE
- `parameters` 命名空间白名单（仅 SymPy 已知符号 + 用户参数 dict keys）

**热更新（D17）**：
- **无缓存设计**：不引入进程级/Redis 缓存；公式每次计算时从 DB 加载
- DRAFT→PUBLISHED 后新公式自动生效（每个请求的 Session 是新的，从 DB 读最新数据）
- 不调用 `session.expire_all()`（无意义：发布事务结束后 Session 关闭，下个请求新 Session 天然从 DB 加载）

**单测运行（D16 + D17）**：
- unit_tests_json schema（D16 锁定）：**对象数组**
  ```json
  "unit_tests": [
    {"params": {"f": 0.02}, "expected": 16000, "tolerance": 0.01}
  ]
  ```
- `run_unit_tests()` 遍历数组，代入 params 调用公式，与 expected 比对（容差 tolerance）→ 返回 `TestResult(passed=int, total=int)`
- PUBLISH 端点断言 `passed == total`，否则 422

### 3.3 系数库（1.3）

```python
# data_json schema
{
    "headers": ["row_label", "value1", "value2", "unit"],
    "rows": [
        ["condition_A", 1.0, 2.0, "MPa"],
        ["condition_B", 1.5, 2.5, "MPa"]
    ],
    "applicable_range": "0<T<200°C"  # 与 applicable_range 列对齐
}
```

API：
```
GET   /api/v1/config/coefficients/{table_id}
POST  /api/v1/config/coefficients/{table_id}/rows
POST  /api/v1/config/coefficients/{table_id}/bulk_update  # 事务一次性
```

### 3.4 模板管理（1.4）

- `template_files.file_path` → 本地存储（`/var/lib/pcs/templates/`），sha256 入库
- `placeholders_json` → Jinja2 渲染，P1.2 编号分配消费
- `project_templates.checklist_json` → 项目模板默认清单（CHECKLIST_AUDIT 用）

### 3.5 编号模板（1.5）

- `segments_json`：模板分段定义（如 `["project_no", "-", "doc_type", "-", "seq"]`）
- `deliverable_mappings_json`：交付物 → 模板映射
- `doc_no_sequences.current_value++` 在事务内；`UNIQUE(project_id, template_id, scope_key)` 防止并发重复
- 并发测试：10 并发同一 (project, template, scope) 全部得唯一序号

## 4. Sprint 2 详细设计（equipment_list 42 字段）

依据 `spec/P2 Sprint 2 执行依据）.md` 分 3 个 migration：

| Migration | 处理项 | 数量 |
|---|---|---|
| `p2_sprint2_equipment_naming_fix.py` | 7 个命名修正 | 7 |
| `p2_sprint2_equipment_procurement_delivery.py` | 采购 12 + 图纸 3 + 交付 5 + 安装 6 + 重量 4 | 30 |
| `p2_sprint2_equipment_engineering.py` | 工程 9 + 标识 6 + 类型 5 + 来源 4 + 涂装 1 | 25（注：实际 26 字段，与执行依据差异以 V3.3 实际为准） |

**命名修正清单（7 项，DICT→ORM 改名）**：
- `description` → `equipment_description`
- `install_location` → `installation_location`
- `weight_kg` → `net_weight`
- `paint_spec` → `paint`
- `drawing_no` → `flowsheet_drawing_number`
- `engineering_notes` → `process_engineering_remarks`
- `vendor_id` (FK) → `vendor` (string 200) — 此项特殊：原 ORM 用 FK，DICT 改 string。需保留 vendor_id 兼容列或迁移数据后删除 FK

**验收**：alembic upgrade head ✅ + ruff ✅ + mypy ✅ + 结构化 diff DICT V3.5 vs ORM 0 漂移

## 5. Sprint 3 详细设计（CIA 集成 + workspace 边界）

### 5.1 config_version_id 传播（基于 D6 双模式）

```python
# app/services/cia_engine.py 新增
class CIAEngine:
    def propagate_from_source(self, source_type: str, source_id: UUID):
        """配置 PUBLISHED 时调用，反向标记下游 STALE"""
        # 1. 反查 data_lineage WHERE source_ref_type=source_type AND source_ref_id=source_id
        # 2. 对每个 (record_type, record_id) 标 STALE
        # 3. 递归传播（带访问集防环 + 深度限制 ≤8）
```

### 5.2 audit_logs.action 接入

8 项 CONFIG_* 枚举经 `AuditService.write()` 写入 audit_logs（直接复用 P1 基础设施）：
- `CONFIG_ASSET_CREATED` / `CONFIG_VERSION_CREATED`
- `CONFIG_ASSET_SUBMITTED` / `CONFIG_ASSET_APPROVED` / `CONFIG_ASSET_PUBLISHED`
- `CONFIG_ASSET_OBSOLETED` / `CONFIG_ASSET_REJECTED` / `CONFIG_VERSION_DIFF_VIEWED`

### 5.3 workspace 边界声明

CONFIG 是全局配置（公式/系数/模板均不属于项目级）。CLAUDE.md 补文档：
> 配置层 API 不调用 `require_formal_workspace`。所有登录用户可读；写操作需 D15 规定的 LDAP 角色。

## 6. Sprint 4 详细设计（报表 + 导出）

| 报表 | SQL | 验收 |
|---|---|---|
| 配置资产状态分布 | `SELECT category, status, COUNT(*) FROM config_assets JOIN config_versions ...` | pytest |
| 编号模板用量 | `doc_no_sequences.current_value` 求和 + 趋势 | pytest |

> **公式覆盖率报表推迟到 P4 之后**：P2 阶段无计算模块引用数据；P4 计算模块开发完成后才有覆盖率口径。Sprint 4 仅交付上述 2 个报表。

**导出**：openpyxl，CSV/Excel 双格式。授权走 D15 ACL。

## 7. 质量门

| 门 | 命令 | 通过条件 |
|---|---|---|
| Lint | `ruff check .` | 0 error |
| Type | `mypy app/` | 0 error |
| Test | `pytest` | 140 (基线) + Sprint 新增 ≥ 30 pass |
| Coverage | `pytest --cov=app` | 新代码 ≥ 80% |
| Migration | `alembic upgrade head` | ✅ |
| Schema 一致性 | 结构化 diff DICT V3.5 vs ORM | 0 漂移 |
| Fuzz | `tests/fuzz/test_formula_engine.py` | 100 次无 RCE |

## 8. 风险 + Mitigations

| 风险 | 概率 | 影响 | Mitigation |
|---|---|---|---|
| SymPy `lambdify` 安全绕过 | 低 | 高 | AST 白名单 + fuzz 100 次 + 命名空间冻结 |
| 状态机与记录层双 StateMachineService 命名混淆 | 中 | 中 | 命名空间分离（config_state_machine.py vs state_machine.py）+ ruff 自定义规则禁止跨文件 import |
| P1.2 编号分配消费时机错位 | 低 | 低 | Sprint 1.5 独立可运行 + 测试覆盖 |
| equipment_list 42 字段缺数据迁移 | 中 | 中 | 全部 nullable=true，旧数据用默认值；vendor_id → vendor 兼容方案单独 E2E 测试 |
| CIA 递归传播爆栈 | 低 | 中 | 深度限制 ≤8（D6 已锁）+ 访问集防环 |

## 9. 与既有 TODO 的关系

| TODO | 状态 | 与 P2 关系 |
|---|---|---|
| TODO-001~023 | P0/P1 延后 | 按原节奏，不阻塞 P2 |
| TODO-024 equipment_list | P2 Sprint 2 | 本计划已覆盖 |
| TODO-025 pump_results 6 列 | P4 Task 0 | **不在 P2 范围** |
| TODO-026 P5 平铺字段 | P5 | 不在 P2 范围 |
| TODO-027 cost_est_results | P7 | 不在 P2 范围 |
| TODO-028 计算表主键 rename | 各模块开发时 | 不在 P2 范围 |

## 10. 工时估算

| Sprint | 工作量 | 主要成本 |
|---|---|---|
| Sprint 1 | ~3 周 | 1.1 骨架 + 1.2 公式引擎（SymPy + AST + 热更新 + 单测）+ 双段签状态机 |
| Sprint 2 | ~3h | 3 个 alembic migration + ORM 同步 + DICT V3.5 |
| Sprint 3 | ~1 周 | CIA 双模式传播 + audit_logs + workspace 文档 |
| Sprint 4 | ~3 天 | 报表 SQL + openpyxl 导出 |
| **合计** | **~5 周** | 单人开发 |

## 11. Spec Self-Review

**Placeholder 扫描**：✅ 无 TBD/TODO。
**内部一致性**：
- §2.1 Sprint 1 描述 vs §3 详细设计：✅ 一致
- D14 横向骨架优先 vs §3.1 顺序：✅ 一致（先 1.1 基础设施再接公式）
- D15 LDAP 角色 vs §3.1 ACL：✅ 一致
- D17 无缓存设计 vs §3.2 热更新：✅ 一致
- §6 Sprint 4 vs §2.1 依赖图：✅ 一致

**Scope 检查**：单 plan P2 全周期，~5 周工作。writing-plans 阶段可拆 4 个 phase 实施。

**Ambiguity 扫描**：
- §3.1 1.1.3 双段签流程明确（双行 config_approvals + 任一驳回回 DRAFT）
- §3.2 unit_tests_json + parameters_json schema 明确（D16 对象数组 + 参数对象数组）
- §3.2 pass rate 硬门槛明确（D17 100% pass）
- §6 Sprint 4 "授权走 D15 ACL" — 引用 D15 裁决，无歧义

## 12. 尚未解决问题（待 writing-plans 阶段裁决）

1. **equipment_list vendor_id (FK) → vendor (string) 迁移数据策略**（合并原问题1+7）：保留双列兼容 OR 删除 FK 列？现存数据非空时需导出映射 → 导入新 string 列；TODO 等 Sprint 2 启动时定
2. **公式 unit_tests_json 在 DICT 中的具体示例**：需补 1~2 条样例
3. **模板文件存储路径**：当前 `/var/lib/pcs/templates/` 是建议值；生产部署时由 IT 提供
4. **P3 起跳时机**：P2 完成后立即进 P3 还是先发版 v1.0？
5. **公式表达式版本管理粒度**：DICT 说保存当前版本到 `formula_definitions`，历史到 `config_versions`。但 SymPy 表达式变更检测（hash）算法未定义 — 需 P2 Sprint 1.2 启动时定