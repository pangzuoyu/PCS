# P7 Complete Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal**: 实现 P7 阶段 4 模块（EQUIP_LIST / UTIL V1.3 基线 + SUP-010 5 表 / EQUIP_LIB / 供应商数据录入与核算），达成 P7 SPEC V1.4 §3.2.1-§3.2.4 全部验收标准。

**Architecture**: 4 Sprint 顺序执行。Sprint 1 = T0 StateMachineService 强制写入 + EQUIP_LIST 同步服务 + UTIL V1.3 基线（util_results 单表 + consumption_json JSONB）；Sprint 2 = SUP-010 6 项迁移（5 表 + auxiliary_consumption 4 字段）+ CONFIG 折标系数 seed；Sprint 3 = EQUIP_LIB 检索 + 相似度计算 + 沉淀；Sprint 4 = 供应商数据录入 + 自动比对 + 偏差报告 + 综合能耗验收对账（蜡油加氢—综合能耗.xlsx 偏差 ≤ 2%）。每子任务标准 PCS 模式：ORM model + alembic migration + service + persist + API + schemas + tests + fixtures + calc_lineage 注册 + SourceService 字段补全。

**Tech Stack**: FastAPI + SQLAlchemy 2.0 + Pydantic 2.7 + alembic + pytest + FastAPI 0.115 + ChEDL 包装层（ADR-0030）；frozen dataclass + PcsError + formula_ref dict；psycopg。

**Spec**: `spec/工艺专用综合计算软件需求规格说明书 Web版 P7.md` V1.4（2026-10-01 发布）+ `docs/P7-REV-01-04-mock-decisions.md` + `docs/P7-OPEN-007-physical-semantics-evaluation.md` + `docs/P7-OPEN-008-rule-registry-form-evaluation.md` + `docs/P7-OPEN-009-SUP-010-5table-migration-schedule.md`（R-02=A 触发）。

## Global Constraints

- **SPEC V1.4 权威版本**: 字段/枚举/权限/错误码以 OpenAPI + meta API 为准；SPEC 冲突时以 OpenAPI 为准
- **P7 总工时**: SPEC V1.4 §4.6 口径 10–13 人周 + R-03 T0 0.5–1 人日 = **10.5–14 人周**（仅 Sprint 1-4 主体）；本计划口径（含 Sprint 0 mock 评估 1.5 人周 + Sprint 1-4 主体 + 收口 + wolf + workspace cleanup）**~14.0–18.2 人周**（D5 5A 工艺室 buffer 0.5 → 1.5 人周 + 对账应急 1.0 → 0.5 人周合并后调整）
- **启动前必备评估**: SPEC V1.4 §4.6 口径 4–7 人日（P7-OPEN-007 3–5 人日 + P7-OPEN-008 1–2 人日）；mock 决议后实际 = **0.5–1 人日**（P7-OPEN-007/008 mock 已闭环于 `docs/P7-OPEN-007-physical-semantics-evaluation.md` + `docs/P7-OPEN-008-rule-registry-form-evaluation.md`；仅剩 R-03 T0 落地）
- **R-02 = 方案 A**（⚠️ 2026-10-05 修订：catalyst_loading **取消不建**，见 `docs/PCS-NOTE-catalyst_loading-取消-2026-10-05.md`；`auxiliary_consumption` 4 字段归属待定，建议不做）: UTIL 权威表 6 张（power_items / fuel_gas / heat_exchange / gas_media / low_temp_heat / energy_summary）
- **R-03 = 待补采**: T0（StateMachineService 强制写入三字段）+ T1（pcs_test fixture ≥30 行）+ 30 天窗口后重跑 P7-OPEN-007 评估
- **R-04 = 方案 B**: 不建立 `app/core/rules_registry.py`；不引入 `@rule` 装饰器
- **pytest baseline**: 3515 passed (P6-9-PICKUP-5 R=1 后)
- **CI/CD 不做**（per memory 单人开发裁决）
- **PcsError 子类 + frozen dataclass + formula_ref dict** 模式不可破（项目级 service 模式）
- **UTIL 权威源（D1 裁决 1A, 2026-10-05 修订）**: Sprint 2 起 **6 表**（`utility_power_items` / `utility_fuel_gas` / `utility_heat_exchange` / `utility_gas_media` / `utility_low_temp_heat` / `utility_energy_summary`）为唯一权威写入路径；`catalyst_loading` 已取消不建（用户裁决 2026-10-05）；`util_results.consumption_json` JSONB 字段 **deprecated**（Sprint 1 遗留，仅 backward compat 读，Sprint 2 起不再更新）；综合能耗验收读 6 表聚合
- **历史/audit 线索保留原则（D1/D2/D3 共同裁决）**: 数据演进（JSONB → 5 表 / 沉淀解耦 / 状态联动）保留历史指针与 audit 字段，用显式状态字段（deprecated / source_sign_status）表达语义，不用级联删除或静默覆盖
- **audit_logs 性能（D8 裁决 9A）**: T0 + CHANGED 流程高频写入 → Sprint 1 JSONB GIN 索引 + Sprint 4 后 monthly partition（保留 6 月）；异步队列可选（仅高峰需求）
- **audit_logs 性能（D8 裁决 9A）**: T0 + CHANGED 流程高频写入 → Sprint 1 JSONB GIN 索引 + Sprint 4 后 monthly partition（保留 6 月）；异步队列可选（仅高峰需求）
- **测试覆盖规范（D6 + D7 裁决 7A/8A）**: 每 Task Step 5 引用 §Test Coverage Standard（5 类最小覆盖：边界/异常/黄金/集成 + alembic 降级）；不在 Task 重复列具体条目
- **跨模块变更所有权（D4 裁决 4A）**: 状态机统一所有门禁迁移；业务模块（Supplier/UtilResults/EquipmentList）通过 `emit_event()` 发事件，不直接触发门禁迁移；事件需幂等性（event_id 去重）；rollback 分阶段（事件撤回 / 门禁回滚 / CIA 反向恢复 — 是否实现 CIA 反向恢复待 P7 Sprint 4 user 裁决）
- **ChEDL 包装层不可破**: 业务代码禁直接 `import fluids.*`（ADR-0030）
- **追溯链完整**: 设备记录通过 SourceModule + SourceRecordID + SourceService（V1.4 新增）三重溯源
- **门禁哈希仅设计参数**: 商务/采购字段不参与门禁哈希
- **工艺室签署依赖**: SUP-010 fixture 数据（蜡油加氢—综合能耗.xlsx + 惠州汽包计算.xls）需工艺室签署。**2026-10-05 起综合能耗验收不再依赖该签署**（基准改为 GB 30251-2024 附录A 独立重算，见 `docs/PCS-SIGN-T5-2026-10-05.md`）
- **R=1 教训（已写入 .wolf/cerebrum.md）**: implementer 必须先 source-verify brief 中描述的代码状态（`wc -l` / `grep -c` / `grep -n` / `dataclasses.fields()`），与 brief 不符时拒绝执行并立即上报
- **bug-114**: pcs_test audit_logs 表 0 行 + state_machine.py 不写三字段 → T0 落地前 P7-OPEN-007 三元决策不可用
- **bug-115**: @rule 装饰器 = 0 + app/core/rules_registry.py 不存在 → 不建立规则管理工具
- **未解决问题 10 项**: 见文末 §未解决问题跟踪位（含 #2 #3 #10 工艺室签署 + #1 T0 + #6 Sprint 依赖链 + #8 双向耦合）

## Test Coverage Standard (D6 裁决 7A)

每 Task 的 Step 5 边界测试必须覆盖以下 4 类（实施时引用此 Section，不在每 Task 重复列）：

1. **边界（Boundary）**: 输入字段约束（如 load_factor ∈ (0, 1] / end_date > start_date / motor_power > 0）；用 pytest.mark.parametrize 覆盖边界值 + 边界外 1-2 例
2. **异常（Exception）**: 服务层错误路径（如 NotFoundError / ValidationError / RangeError / CapacityError）；用 pytest.raises 显式断言异常类型 + 错误信息
3. **黄金（Golden）**: 工艺室/SPEC 推导的确定值（如蜡油加氢实例、Sprint 2 SUP-010 5 表 fixture）；fixture 标注溯源（工艺室签署日期 + Excel 文件名）
4. **集成（Integration）**: API 端到端测试（POST + GET 验证副作用）；调用链 > 2 模块时必须含集成测试
5. **降级（Downgrade）（D7 裁决 8A，仅 alembic Task 适用）**: 每个 alembic 迁移 Task Step 6 加 1 个 downgrade 测试（FAILED: No 'script_location' key found in configuration. + verify schema rollback）；复用 pcs-backend/tests/test_alembic_downgrade.py 模式；生产事故时救命

实施检查：每个 Task 完成时 （边界+异常+黄金+集成 4 类的最小覆盖）。

## Review Focus

5 个最可能咬人的输入类 / 失败模式：

1. **设备同步 STALE 联动恢复** — STALE 重算哈希不变时设备记录应联动恢复 CHECKED；若 source_state_machine 未正确触发则设备记录滞留 STALE（Spec §3.2.1）
2. **C-16 甘醇脱水塔默认不同步** — PSYCHRO C-16 默认不自动进设备表，需设计人手动触发；若默认同步则 ARU/MRU 成套包数据被错误拆分（Spec §3.2.1 注记）
3. **UTIL V1.3 基线 consumption_json JSONB 容差** — 综合能耗汇总与 Excel 偏差 ≤ 2%；若 JSONB 容器 schema 不校验则容差超限（Spec §3.2.2（3））
4. **供应商数据偏差报告「不合格」拒绝确认** — 不合格项必须禁止确认 + 通知供应商；若校验缺失则不合格数据被误标合格（Spec §3.2.4（3））
5. **EQUIP_LIB 沉淀审批解耦** — 沉淀后记录与源项目解耦；若 source_project_id 未清空则复用库反污染源项目（Spec §3.2.3（3））
6. **UTIL 双写权威性（D1 裁决 1A）** — Sprint 2 起 5 表是唯一权威写入路径；若 `summary_service` 仍写 JSONB 或 JSONB 读路径被误认为权威 → Sprint 4 综合能耗验收偏差 > 2%（Spec §3.2.2（3））；需在 Sprint 2 Task S2-7 Step 2.5 切换写路径 + Step 2.6 数据回填
7. **sync_from_source 并发 CHECKED（D2 裁决 2A）** — 两路 SourceModule 同 (project_id, tag_number) 并发 CHECKED 时，若无 advisory lock 会 IntegrityError 500 或静默覆盖；advisory lock key 必须按 SPEC V1.4 §2.5 用 (project_id, tag_number) 复合，非全局 tag_number（Spec §3.2.1）；同时修复 Task S1-2 ORM `unique=True` 误伤跨项目同名位号
8. **EQUIP_LIB 沉淀源 OBSOLETE 联动（D3 裁决 3A）** — 源 EQUIP_LIST OBSOLETE 后复用库记录**不消失**（沉淀是稳定副本）；`source_record_id` 保留为 audit 线索；源状态用 `source_sign_status` 镜像（pull 模式读时 join）；若误用 cascade DELETE → 复用库资产随项目退役蒸发（Spec §3.2.3（3））
9. **供应商实际值 CHANGED 流程所有权（D4 裁决 4A）** — Supplier 只发 `emit_event('actual_data_replaces_design', ...)`，**不直接调 state_machine**；state_machine 监听事件走 EquipmentList CHANGED；UtilResults **不进 CHANGED**（只重算）+ CIA 评估；若 Supplier 直接迁移门禁 → 职责泄漏 + 跨模块协调复杂（Spec §3.2.4（6））
6. **UTIL 双写权威性（D1 裁决 1A）** — Sprint 2 起 5 表是唯一权威写入路径；若 `summary_service` 仍写 JSONB 或 JSONB 读路径被误认为权威 → Sprint 4 综合能耗验收偏差 > 2%（Spec §3.2.2（3））；需在 Sprint 2 Task S2-7 Step 2.5 切换写路径 + Step 2.6 数据回填

---

## Sprint 0（已完成 — 启动准备）

> **状态**: 2026-10-01 已闭环（commits `a902d2f` + `4f0d671`）。本节仅作历史追溯，无新任务。

### Task S0-1: P7-OPEN-007 mock 评估

**Files**:
- Create: `docs/P7-OPEN-007-physical-semantics-evaluation.md`
- Modify: `.wolf/buglog.json`（bug-114）

**Status**: ✅ 已完成。详见评估报告 §4.1 mock 决议「推迟三元决策 → 待补采」。

### Task S0-2: P7-OPEN-008 mock 评估

**Files**:
- Create: `docs/P7-OPEN-008-rule-registry-form-evaluation.md`
- Modify: `.wolf/buglog.json`（bug-115）

**Status**: ✅ 已完成。详见评估报告 §4.1 mock 决议「方案 B（ADR 附录）采纳」。

### Task S0-3: P7-REV-01~04 mock 裁决

**Files**:
- Create: `docs/P7-REV-01-04-mock-decisions.md`

**Status**: ✅ 已完成。R-01 接受 / R-02 方案 A（用户裁决）/ R-03 待补采 / R-04 方案 B。

### Task S0-4: P7 SPEC V1.4 落地（含 9 处修订 + §4.7 启动前裁决清单）

**Files**:
- Modify: `spec/工艺专用综合计算软件需求规格说明书 Web版 P7.md`（V1.3 → V1.4；9 处修订 + §4.7 启动前裁决清单 + 4 mock 决议文件关联）

**Status**: ✅ 已完成（commits `a902d2f` + `4f0d671`）。

### Task S0-5: SUP-010 5 表 + catalyst_loading + auxiliary_consumption 4 字段迁移排期

> ⚠️ **2026-10-05 修订**：排期文档已产出
> (`docs/P7-OPEN-009-SUP-010-5table-migration-schedule.md`)，但其中的
> `catalyst_loading` 项**已取消**，`auxiliary_consumption` 4 字段归属待定
> （建议不做，现有 6 张表已能聚合算出）。
> 见 `docs/PCS-NOTE-catalyst_loading-取消-2026-10-05.md`。

**Files**:
- Create: `docs/P7-OPEN-009-SUP-010-5table-migration-schedule.md`

**Status**: ✅ 已完成。R-02=A 触发；6 alembic 迁移链 `p7_open_009_001`→`006`；工艺室 2026-10-XX 签署四节点。

---

## Sprint 1（T0 + EQUIP_LIST + UTIL V1.3 基线）

**总工时**: ~4.2–5.4 人周（T0 +0.5–1 人日 ≈ 0.1–0.2 人周 + EQUIP_LIST 2.5–3 人周 + UTIL V1.3 基线 1.5–2 人周）

### Task S1-1: StateMachineService 强制写入三字段（R-03 T0 落地）

**Files**:
- Modify: `pcs-backend/app/services/state_machine.py`（resolve_stale 函数添加 audit 写入）
- Modify: `pcs-backend/app/services/audit_service.py`（增加 write_with_audit_trail 包装）
- Test: `pcs-backend/tests/test_state_machine.py`（增加 audit_trail 测试）

**Interfaces**:
- Consumes: `audit_service.write(action, resource_type, resource_id, detail_json)`
- Produces: `state_machine.resolve_stale` → 每次 STALE 解除写 audit_logs，含 `stale_resolution_path` / `hash_changed` / `changed_fields`

**工时**: 0.5–1 人日（R-03 T0；未在 §工时表独立列，含在 Sprint 1 顶部）
**截止**: P7 Sprint 1 末（T0 落地；Sprint 1 第 1 任务）

- [ ] **Step 1**: 写 failing test — 验证 STALE 解除后 audit_logs 表新增记录含三字段

```python
# tests/test_state_machine.py
def test_resolve_stale_writes_audit_with_three_fields(db_session):
    # 准备 CHECKED 记录 → 标记 STALE → 解除 STALE
    record = create_test_record(db_session)
    record.transition_to("STALE")
    record.transition_to("CHECKED")  # resolve

    audit = db_session.query(AuditLog).filter_by(
        resource_id=record.id,
        action="STALE_RESOLVED"
    ).first()
    assert audit is not None
    assert audit.detail_json["stale_resolution_path"] in ("RESOLVE_NO_CHANGE", "RESOLVE_CHANGED")
    assert isinstance(audit.detail_json["hash_changed"], bool)
    assert isinstance(audit.detail_json["changed_fields"], list)
```

- [ ] **Step 2**: 跑 test 验证失败 — `pytest tests/test_state_machine.py::test_resolve_stale_writes_audit_with_three_fields -v` 期望 FAIL（audit 写入未实现）

- [ ] **Step 3**: 实现 — 修改 `state_machine.py` `resolve_stale` 函数：

```python
# pcs-backend/app/services/state_machine.py
def resolve_stale(record: Record, ...):
    old_hash = record.record_hash
    # ... 现有 transition logic ...
    new_hash = record.record_hash
    hash_changed = old_hash != new_hash
    changed_fields = list(record.changed_fields or [])

    audit_service.write(
        action="STALE_RESOLVED",
        resource_type=record.__tablename__,
        resource_id=record.id,
        detail_json={
            "stale_resolution_path": "RESOLVE_CHANGED" if hash_changed else "RESOLVE_NO_CHANGE",
            "hash_changed": hash_changed,
            "changed_fields": changed_fields,
        },
    )
```

- [ ] **Step 4**: 跑 test 验证通过 — `pytest tests/test_state_machine.py::test_resolve_stale_writes_audit_with_three_fields -v` 期望 PASS

- [ ] **Step 5**: 跑全量 pytest 验证 0 regression — `cd pcs-backend && DATABASE_URL=... uv run pytest tests/ -q` 期望 3515+ passed, 0 failed

- [ ] **Step 6**: 单 commit — 

**D8 裁决 9A 补**：audit_logs.detail_json 加 JSONB GIN 索引（优化 detail_json 字段查询）；alembic 迁移 ；pcs-backend/alembic/versions/p7_s1_002_audit_logs_jsonb_gin.py 新建`feat(p7-s1): StateMachineService 强制写入 audit_logs 三字段 (R-03 T0)`

### Task S1-2: EQUIP_LIST ORM model（含 SourceService V1.4 新字段）

**Files**:
- Create: `pcs-backend/app/models/equip_list.py`（含 EquipmentList ORM，含 SourceModule + SourceRecordID + SourceService + 设计参数 + 商务字段组 + RecordMixin）
- Modify: `pcs-backend/alembic/versions/p7_s1_001_equipment_list.py`（Sprint 1 独立迁移号 `p7_s1_001`，避免与 Sprint 2 迁移链 `p7_open_009_001`~`006` 同号冲突）

**Interfaces**:
- Consumes: RecordMixin（含 stale_resolution_path / hash_changed / changed_fields 三字段）
- Produces: `EquipmentList` ORM 类，供 Sprint 1 EQUIP_LIST 同步服务使用

- [ ] **Step 1**: 写 failing test — `python -c "from app.models.equip_list import EquipmentList; print(len([f for f in EquipmentList.__table__.columns]))"`

- [ ] **Step 2**: 跑 python -c 验证导入失败（EquipmentList 类不存在）

- [ ] **Step 3**: 创建 ORM model — `pcs-backend/app/models/equip_list.py`（per SPEC V1.4 §3.2.1（2）字段组 + SourceService 字段）

```python
# pcs-backend/app/models/equip_list.py
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, JSON, ForeignKey, UniqueConstraint, text
from app.models.mixins import RecordMixin
from app.models.base import Base

class EquipmentList(Base, RecordMixin):
    __tablename__ = "equipment_list"
    __table_args__ = (
        UniqueConstraint("project_id", "tag_number", name="uq_equip_list_project_tag"),
    )

    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.project_id"))
    workspace_id: Mapped[UUID] = mapped_column(ForeignKey("workspaces.workspace_id"))

    # 标识
    tag_number: Mapped[str] = mapped_column(String(50))  # D2 裁决 2A: 去掉 unique=True（全局唯一），改用 (project_id, tag_number) 复合唯一
    equipment_description: Mapped[str | None] = mapped_column(String(500))
    equipment_name_cn: Mapped[str | None] = mapped_column(String(200))

    # 类型
    type_code: Mapped[str] = mapped_column(String(20), ForeignKey("equipment_type_codes.type_code"))
    equipment_sub_type: Mapped[str | None] = mapped_column(String(50))
    equipment_category: Mapped[str | None] = mapped_column(String(50))
    is_pressure_vessel: Mapped[bool] = mapped_column(default=False)

    # 来源（V1.4 SourceService 新增）
    source_module: Mapped[str | None] = mapped_column(String(20))
    source_service: Mapped[str | None] = mapped_column(String(64))  # V1.4 新增
    source_record_id: Mapped[UUID | None] = mapped_column()
    in_package: Mapped[bool] = mapped_column(default=False)
    data_sources: Mapped[dict | None] = mapped_column(JSON)

    # 状态
    equipment_status: Mapped[str] = mapped_column(String(1))  # N/E/D/M/F
    calc_status: Mapped[str | None] = mapped_column(String(20))
    sign_status: Mapped[str] = mapped_column(String(30))
    actual_data_status: Mapped[str] = mapped_column(String(20))

    # 设计参数
    design_parameters_json: Mapped[dict | None] = mapped_column(JSON)

    # 采购（不参与门禁哈希）
    vendor: Mapped[str | None] = mapped_column(String(200))
    alternate_vendor: Mapped[str | None] = mapped_column(String(200))
    order_date: Mapped[Date | None] = mapped_column()
    po_number: Mapped[str | None] = mapped_column(String(50))
    cost: Mapped[Decimal | None] = mapped_column()
    gpe_spec: Mapped[str | None] = mapped_column(String(500))

    # 其他字段（per SPEC V1.4 §3.2.1（2））
    # ... 图纸 / 交付 / 安装 / 重量 / 工程字段组
```

- [ ] **Step 4**: 跑 python -c 验证导入成功且字段数 ≥ 30

- [ ] **Step 5**: 单 commit — `feat(p7-s1): EquipmentList ORM model 含 SourceService V1.4 字段 (T1)`

### Task S1-3: EquipmentTypeCodes CONFIG seed（CATEGORY_5，不建独立 ORM）

**Files**:
- Create: `pcs-backend/app/seeds/equipment_type_codes_seed.py`（CONFIG CATEGORY_5 seed）
- Modify: `pcs-backend/app/models/config_assets.py`（如尚未存在）确认 ConfigAssets CATEGORY_5 + asset_subtype=EQUIPMENT_TYPE_CODE 支持

**Interfaces**:
- Consumes: ConfigAssets ORM（CATEGORY_5，asset_subtype=EQUIPMENT_TYPE_CODE）
- Produces: 80 种类型代码 seed 数据（不建独立 ORM 表 — 类型代码存储在 CONFIG CATEGORY_5，per SPEC V1.4 §3.2.1（3））

- [ ] **Step 1**: 写 failing test — 验证类型代码 seed 后 ConfigAssets 表 CATEGORY_5 行数 ≥ 80

- [ ] **Step 2**: 跑 seed 测试验证失败

- [ ] **Step 3**: 实现 seed 脚本（per SPEC V1.4 §3.2.1（3）：P/E/T/V/C/A/M/ST/GT/E/D/V/T/R/S/PSV/PRD/PVRV/ERV/FA/ARU/MRU/LOS/SOS/H/F/CT/X 等 80 种）

- [ ] **Step 4]: 跑 seed 验证 ≥ 80 行（CT/T/V/PVRV 等已登记）

- [ ] **Step 5]: 单 commit — `feat(p7-s1): EquipmentTypeCodes CONFIG CATEGORY_5 seed (T1.5)`

### Task S1-4: EQUIP_LIST 同步服务（CHECKED 触发 + 状态联动）

**Files**:
- Create: `pcs-backend/app/services/equip_list/sync_service.py`（sync_from_source）
- Create: `pcs-backend/app/services/equip_list/persist_service.py`
- Create: `pcs-backend/app/schemas/equip_list.py`
- Create: `pcs-backend/app/api/v1/equip_list.py`（GET/PUT/POST/sync/manual/DELETE）
- Test: `pcs-backend/tests/services/equip_list/test_sync_service.py`
- Test: `pcs-backend/tests/services/equip_list/fixtures/golden_equip_list_sync.json`

**Interfaces**:
- Consumes: `EquipmentList` ORM（Task S1-2）+ 各 SourceModule 的 ORM（PUMP/VESSEL/HEAT/PSV/CV/COOL_TOWER/PSYCHRO/OPEN_CHANNEL）
- Produces: API `GET/PUT/POST /api/v1/equipment-list` + 同步触发器（CHECKED 触发）

**工时**: +0.5 人日（D2 裁决 2A：advisory lock + 并发集成测试）

- [ ] **Step 1**: 写 failing test — 验证 PUMP CHECKED 时自动创建 EquipmentList 记录 + SourceService="pump_service"

- [ ] **Step 2**: 跑 test 验证失败

- [ ] **Step 3**: 实现 sync_service

```python
# pcs-backend/app/services/equip_list/sync_service.py
def sync_from_source(source_module: str, source_service: str, source_record_id: UUID, db: Session):
    """SourceModule 触发：来源记录 CHECKED 时调用"""
    source = get_source_record(source_module, source_service, source_record_id, db)
    if source.sign_status != "CHECKED":
        raise SyncError(f"Source record not CHECKED: {source.sign_status}")

    # D2 裁决 2A: advisory lock per (project_id, tag_number) — 与 calc_lineage 已有模式一致
    # 锁 key 复合（项目内唯一，per SPEC V1.4 §2.5）— 防止两路并发 CHECKED 触发 race condition
    db.execute(
        text("SELECT pg_advisory_xact_lock(hashtext(:key))"),
        {"key": f"{source.project_id}::{source.tag_number}"},
    )

    existing = db.query(EquipmentList).filter_by(
        project_id=source.project_id,
        tag_number=source.tag_number,
    ).first()

    if existing:
        # 状态联动（V1.1）
        existing.sign_status = source.sign_status
        existing.equipment_status = "E"
    else:
        existing = EquipmentList(
            project_id=source.project_id,
            workspace_id=source.workspace_id,
            tag_number=source.tag_number,
            type_code=derive_type_code(source_module),
            source_module=source_module,
            source_service=source_service,  # V1.4 新增
            source_record_id=source_record_id,
            sign_status=source.sign_status,
            equipment_status="N",
        )
        db.add(existing)

    # 继承批准深度（V1.1）
    existing.approval_step = source.approval_step
    existing.approval_depth = source.approval_depth
    db.commit()
```

- [ ] **Step 4**: 跑 test 验证通过

- [ ] **Step 5**: 边界测试 — STALE 重算哈希不变时联动恢复 CHECKED（Review Focus #1）+ 并发 sync_from_source 同 (project_id, tag_number) 一成功一等待（D2 裁决 2A）

```python
# tests/services/equip_list/test_sync_service.py
def test_concurrent_sync_same_tag_one_succeeds(db_session_factory):
    """D2 裁决 2A: 两路并发 sync_from_source 同 (project_id, tag_number)"""
    import threading
    results = []
    barrier = threading.Barrier(2)

    def _sync():
        try:
            sync_from_source("PUMP", "pump_service", source_id, db_session_factory())
            results.append("ok")
        except Exception as e:
            results.append(type(e).__name__)

    t1 = threading.Thread(target=_sync)
    t2 = threading.Thread(target=_sync)
    t1.start(); t2.start(); t1.join(); t2.join()
    assert results.count("ok") == 1  # 一成功
    # DB 中仅一条 EquipmentList 记录
    db = db_session_factory()
    assert db.query(EquipmentList).filter_by(
        project_id=p, tag_number=tag
    ).count() == 1
```

- [ ] **Step 6**: pytest 全量 0 regression

- [ ] **Step 7**: 单 commit — `feat(p7-s1): EQUIP_LIST 同步服务 + SourceService 字段 + CHECKED 触发 (T2)`

### Task S1-5: UTIL V1.3 基线（util_results 单表 + consumption_json JSONB）

**Files**:
- Create: `pcs-backend/app/models/util.py`（UtilResults ORM 含 consumption_json JSONB **+ jsonb_deprecated bool 字段（默认 False，Sprint 2 起置 True）**；Sprint 2 Task S2-1~6 在此文件 append 5 表）
- Create: `pcs-backend/app/services/util/summary_service.py`（能耗汇总 service）
- Create: `pcs-backend/app/services/util/persist_service.py`
- Create: `pcs-backend/app/schemas/util.py`
- Create: `pcs-backend/app/api/v1/util.py`（GET /api/v1/util/summary + energy-consumption + water-balance）
- Test: `pcs-backend/tests/services/util/test_summary_service.py`
- Test: `pcs-backend/tests/services/util/fixtures/golden_util_summary.json`

**Interfaces**:
- Consumes: `EquipmentList` ORM + PUMP / HEAT / COOL_TOWER / OPEN_CHANNEL results
- Produces: `util_results` ORM + 13 类公用工程枚举（per SPEC V1.4 §4.4）+ 折标系数 from CONFIG

- [ ] **Step 1**: 写 failing test — 验证 util_results 汇总返回 13 类公用工程聚合

- [ ] **Step 2**: 跑 test 验证失败

- [ ] **Step 3**: 实现 util_results ORM + 13 类枚举（ELECTRICITY / STEAM_HP / STEAM_MP / STEAM_LP / CONDENSATE / COOLING_WATER / CHILLED_WATER / MAKEUP_WATER / FUEL_GAS / NITROGEN / INSTRUMENT_AIR / PLANT_AIR + 总计）

- [ ] **Step 4**: 实现 summary_service（求和 + 折标系数 CONFIG）

- [ ] **Step 5**: 边界测试 — 实际值优先规则（ActualDataStatus=已确认 时优先用实际值）+ JSONB deprecated 标记默认 False（Sprint 1 阶段 JSONB 仍权威）

```python
# tests/services/util/test_summary_service.py
def test_jsonb_deprecated_marker_defaults_false(db_session):
    """Sprint 1 阶段 JSONB 仍权威；Sprint 2 起 jsonb_deprecated=True"""
    r = UtilResults(project_id=..., workspace_id=..., consumption_json={...})
    assert r.jsonb_deprecated is False  # Sprint 1
```

- [ ] **Step 6**: pytest 全量 0 regression

- [ ] **Step 7**: 单 commit — `feat(p7-s1): UTIL V1.3 基线（util_results 单表 + 13 类公用工程 + 折标系数 CONFIG）(T3)`

---

## Sprint 2（SUP-010 6 项迁移 + 综合能耗验收）

**总工时**: ~4.5–5.5 人周（迁移本身 ~4.0 工作日 ≈ 0.8 人周 + service/API/fixture 全口径 +2–3 人周 + Task S2-7 API 整合 + G-08 验证 +0.2–0.4 人周）

### Task S2-1: utility_power_items 表（电耗设备清单）

**Files**:
- Modify: `pcs-backend/app/models/util.py`（新建，append `UtilityPowerItem` 类）
- Create: `pcs-backend/alembic/versions/p7_open_009_001_utility_power_items.py`
- Create: `pcs-backend/app/services/util/utility_power_service.py`
- Create: `pcs-backend/app/services/util/utility_power_persist_service.py`
- Create: `pcs-backend/app/schemas/utility_power.py`
- Create: `pcs-backend/app/api/v1/utility_power.py`
- Test: `pcs-backend/tests/services/util/test_utility_power_service.py`
- Test: `pcs-backend/tests/services/util/fixtures/golden_utility_power_items.json`（≥10 算例）

**Interfaces**:
- Consumes: `EquipmentList` ORM（Task S1-2）+ PUMP AbsorbedPower（V1.3 已建）
- Produces: `UtilityPowerItem` ORM（含 motor_power / operating_hours / annual_consumption / load_factor 4 字段）+ API

- [ ] **Step 1**: 写 failing test — 验证 utility_power_items ORM 字段数 = 4 + RecordMixin + UNIQUE(project_id, equipment_tag)

- [ ] **Step 2**: 跑 test 验证失败

- [ ] **Step 3**: 实现 ORM + alembic migration

- [ ] **Step 4**: 实现 service + persist + schema + API

- [ ] **Step 5**: 边界测试 — load_factor ∈ (0, 1] 校验；motor_power > 0

- [ ] **Step 6**: pytest 全量 0 regression

- [ ] **Step 7**: 单 commit — `feat(p7-s2): utility_power_items 表 + service + API (T1)`

### Task S2-2: utility_fuel_gas 表（燃料气）

**Files**:
- Modify: `pcs-backend/app/models/util.py`（append `UtilityFuelGas` 类）
- Create: `pcs-backend/alembic/versions/p7_open_009_002_utility_fuel_gas.py`
- Create: `pcs-backend/app/services/util/utility_fuel_gas_service.py`
- Create: `pcs-backend/app/services/util/utility_fuel_gas_persist_service.py`
- Create: `pcs-backend/app/schemas/utility_fuel_gas.py`
- Create: `pcs-backend/app/api/v1/utility_fuel_gas.py`
- Test: `pcs-backend/tests/services/util/test_utility_fuel_gas_service.py`
- Test: `pcs-backend/tests/services/util/fixtures/golden_utility_fuel_gas.json`（≥5 算例）

**Interfaces**:
- Consumes: PMS / 手动录入
- Produces: `UtilityFuelGas` ORM（含 calorific_value / consumption / annual_consumption + 初期/末期/最大工况 3 状态）

- [ ] **Step 1**: 写 failing test — 验证 utility_fuel_gas ORM 含初期/末期/最大工况 3 状态

- [ ] **Step 2**: 跑 test 验证失败

- [ ] **Step 3**: 实现 ORM + migration（per `docs/P7-OPEN-009-SUP-010-5table-migration-schedule.md` §1）

- [ ] **Step 4**: service + persist + schema + API

- [ ] **Step 5**: 边界测试 — 末期 > 初期 > 最大工况合理性校验

- [ ] **Step 6**: pytest 全量 0 regression

- [ ] **Step 7**: 单 commit — `feat(p7-s2): utility_fuel_gas 表 + service + API (T2)`

### Task S2-3: utility_heat_exchange 表（蒸汽/冷凝水）

**Files**:
- Modify: `pcs-backend/app/models/util.py`（append `UtilityHeatExchange` 类）
- Create: `pcs-backend/alembic/versions/p7_open_009_003_utility_heat_exchange.py`
- Create: `pcs-backend/app/services/util/utility_heat_exchange_service.py`
- Create: `pcs-backend/app/services/util/utility_heat_exchange_persist_service.py`
- Create: `pcs-backend/app/schemas/utility_heat_exchange.py`
- Create: `pcs-backend/app/api/v1/utility_heat_exchange.py`
- Test: `pcs-backend/tests/services/util/test_utility_heat_exchange_service.py`
- Test: `pcs-backend/tests/services/util/fixtures/golden_utility_heat_exchange.json`（≥5 算例）

**Interfaces**:
- Consumes: HEAT 计算结果（HeatResults.HeatExchanged）
- Produces: `UtilityHeatExchange` ORM（含 steam_pressure / steam_quality / return_condensate + 温度等级分类 >120°C/<120°C）

- [ ] **Step 1**: 写 failing test — 验证温度等级分类（>120°C/<120°C）

- [ ] **Step 2**: 跑 test 验证失败

- [ ] **Step 3**: 实现 ORM + migration

- [ ] **Step 4**: service + persist + schema + API

- [ ] **Step 5**: 边界测试 — steam_quality ∈ (0, 1]；return_condensate ≤ steam_consumption

- [ ] **Step 6**: pytest 全量 0 regression

- [ ] **Step 7**: 单 commit — `feat(p7-s2): utility_heat_exchange 表 + service + API (T3)`

### Task S2-4: auxiliary_consumption 4 字段 ALTER TABLE

**Files**:
- Modify: `pcs-backend/app/models/util.py`（UtilResults 类新增 4 字段；不建独立 `util_results.py`，与 Sprint 1 Task S1-5 统一为 `util.py`）
- Create: `pcs-backend/alembic/versions/p7_open_009_004_auxiliary_consumption_4fields.py`（ALTER TABLE）
- Create: `pcs-backend/app/services/util/auxiliary_consumption_migration_service.py`（数据迁移脚本）

**Interfaces**:
- Consumes: 既有 util_results 表（Sprint 1 Task S1-5）
- Produces: util_results 表新增 4 字段（electrical_power / fuel_gas_consumption / steam_consumption / cooling_water_consumption）+ backward compat 默认值 NULL

- [ ] **Step 1**: 写 failing test — 验证 ALTER 后 4 字段存在

- [ ] **Step 2**: 跑 alembic upgrade head 验证失败

- [ ] **Step 3**: 实现 migration（ALTER TABLE）

- [ ] **Step 4**: 数据迁移脚本（既有数据 NULL 填充）

- [ ] **Step 5**: alembic upgrade head 验证通过

- [ ] **Step 6]: pytest 全量 0 regression

- [ ] **Step 7]: 单 commit — `feat(p7-s2): auxiliary_consumption 4 字段 ALTER (T4)`

### Task S2-5: utility_energy_summary 表（综合能耗汇总）+ CONFIG 折标煤系数 seed

**Files**:
- Modify: `pcs-backend/app/models/util.py`（append `UtilityEnergySummary` 类）
- Create: `pcs-backend/alembic/versions/p7_open_009_005_utility_energy_summary.py`
- Create: `pcs-backend/app/services/util/utility_energy_summary_service.py`（聚合 service，含折标煤系数 CONFIG 集成）
- Create: `pcs-backend/app/services/util/utility_energy_summary_persist_service.py`
- Create: `pcs-backend/app/schemas/utility_energy_summary.py`
- Create: `pcs-backend/app/api/v1/utility_energy_summary.py`
- Create: `pcs-backend/app/seeds/config_energy_conversion_factors.py`（CONFIG 折标系数 seed，6 类能源）
- Test: `pcs-backend/tests/services/util/test_utility_energy_summary_service.py`
- Test: `pcs-backend/tests/services/util/fixtures/golden_utility_energy_summary.json`（≥3 算例，覆盖电/燃料/蒸汽/水/气体/低温余热六类）

**Interfaces**:
- Consumes: `utility_power_items` + `utility_fuel_gas` + `utility_heat_exchange` + `auxiliary_consumption` 聚合
- Produces: `UtilityEnergySummary` ORM（含 annual_total_energy / toe_conversion_factor / standard_coal_factor）+ 验收：与蜡油加氢—综合能耗.xlsx 偏差 ≤ 2%

- [ ] **Step 1**: 写 failing test — 验证偏差 ≤ 2%

- [ ] **Step 2**: 跑 test 验证失败

- [ ] **Step 3**: 实现 ORM + migration

- [ ] **Step 4]: 实现 CONFIG seed 脚本（`config_energy_conversion_factors.py`）

```python
# pcs-backend/app/seeds/config_energy_conversion_factors.py
SEED_DATA = [
    {"source": "GB_T_50441_APPENDIX", "energy_type": "ELECTRICITY",
     "toe_factor": 0.1229, "standard_coal_factor": 0.1229,
     "confirmed_by": None},  # P7 启动前工艺负责人签字
    {"source": "GB_T_50441_APPENDIX", "energy_type": "FUEL_GAS",
     "toe_factor": 1.0, "standard_coal_factor": 1.4286, "confirmed_by": None},
    {"source": "GB_T_50441_APPENDIX", "energy_type": "STEAM",
     "toe_factor": 0.0944, "standard_coal_factor": 0.1286, "confirmed_by": None},
    # ... 6 类能源（电/燃料/蒸汽/水/气体/低温余热）
]
```

- [ ] **Step 5]: 实现 summary_service（聚合 + 偏差校验）

- [ ] **Step 6]: 边界测试 — 超偏差抛 `EnergyConsumptionToleranceError`（per `docs/P7-OPEN-009-SUP-010-5table-migration-schedule.md` §8）

- [ ] **Step 7]: pytest 全量 0 regression

- [ ] **Step 8]: 单 commit — `feat(p7-s2): utility_energy_summary 表 + CONFIG 折标煤系数 seed (T5)`

### Task S2-6: catalyst_loading 表（催化剂装填量）

> ❌ **取消 (用户裁决 2026-10-05)** —— 该表不建，功能先不做。
> 依赖的 `蜡油加氢—综合能耗.xlsx` 催化剂装填量数据不再等待工艺室签署。
> 见 `docs/PCS-NOTE-catalyst_loading-取消-2026-10-05.md`。
> **下方 Step 1~7 全部作废**，仅为历史留档。

**Files**:
- Modify: `pcs-backend/app/models/util.py`（append `CatalystLoading` 类）
- Create: `pcs-backend/alembic/versions/p7_open_009_006_catalyst_loading.py`
- Create: `pcs-backend/app/services/util/catalyst_loading_service.py`
- Create: `pcs-backend/app/services/util/catalyst_loading_persist_service.py`
- Create: `pcs-backend/app/schemas/catalyst_loading.py`
- Create: `pcs-backend/app/api/v1/catalyst_loading.py`
- Test: `pcs-backend/tests/services/util/test_catalyst_loading_service.py`
- Test: `pcs-backend/tests/services/util/fixtures/golden_catalyst_loading.json`（≥5 算例）

**Interfaces**:
- Consumes: 蜡油加氢—综合能耗.xlsx + 惠州汽包实例
- Produces: `CatalystLoading` ORM（含 volume / weight / density / bed_height 4 字段 + 寿命管理 start_date / end_date）

- [ ] **Step 1]: 写 failing test — 验证 bed_height 与 volume/density 一致性校验（volume = area × bed_height）

- [ ] **Step 2]: 跑 test 验证失败

- [ ] **Step 3]: 实现 ORM + migration

- [ ] **Step 4]: service + persist + schema + API

- [ ] **Step 5]: 边界测试 — end_date > start_date；density > 0；bed_height > 0

- [ ] **Step 6]: pytest 全量 0 regression

- [ ] **Step 7]: 单 commit — `feat(p7-s2): catalyst_loading 表 + service + API (T6)`

### Task S2-7: UTIL 5 表 API 整合 + G-08 验证

**Files**:
- Modify: `pcs-backend/app/api/v1/util.py`（扩展 6 端点：5 表 + recalculate）
- Modify: `pcs-backend/tests/services/util/test_util_api.py`（集成测试）

**工时**: 0.5–0.7 人日（G-08 验证 + API 集成 + JSONB → 5 表数据回填 + summary_service 写路径切换；含在 Sprint 2 总工时）

- [ ] **Step 1**: 跑 G-08 — `bash pcs-backend/scripts/gate_08_openapi_contract.sh --check-baseline` 期望 baseline diff = 0

- [ ] **Step 2.5**: `summary_service` 改为只写 5 表 + JSONB 字段标 `jsonb_deprecated=True`（Sprint 1 遗留记录）；新增记录 `consumption_json` 留 NULL

- [ ] **Step 2.6**: 数据迁移脚本 `pcs-backend/app/services/util/jsonb_to_5tables_migration.py`：从 Sprint 1 JSONB 回填 5 表（一次性）；回填后 `jsonb_deprecated=True` + 校验聚合值与原 JSONB 总和偏差 ≤ 1%（容差源于浮点精度）

- [ ] **Step 1]: 跑 G-08 — `bash pcs-backend/scripts/gate_08_openapi_contract.sh --check-baseline` 期望 baseline diff = 0

- [ ] **Step 2]: pytest 全量 — 期望 3515+ passed + 新增 util 测试全部 PASS

- [ ] **Step 3]: 单 commit — `feat(p7-s2): UTIL 5 表 API 整合 + G-08 (T7)`

---

## Sprint 3（EQUIP_LIB 检索 + 相似度 + 沉淀）

**总工时**: ~1–1.5 人周

### Task S3-1: EQUIP_LIB 检索服务（TypeCode + 工艺条件 + 尺寸参数 + 关键词）

**Files**:
- Create: `pcs-backend/app/models/equipment_lib.py`（复用设备库 ORM；含 `source_record_id` SET NULL + `source_sign_status` + `source_obsolete_at` 2 字段镜像源状态，D3 裁决 3A pull 模式）
- Create: `pcs-backend/alembic/versions/p7_open_009_007_equipment_lib.py`
- Create: `pcs-backend/app/services/equip_lib/search_service.py`
- Create: `pcs-backend/app/services/equip_lib/persist_service.py`
- Create: `pcs-backend/app/schemas/equip_lib.py`
- Create: `pcs-backend/app/api/v1/equip_lib.py`（GET /api/v1/equip-lib/search）
- Test: `pcs-backend/tests/services/equip_lib/test_search_service.py`
- Test: `pcs-backend/tests/services/equip_lib/fixtures/golden_equip_lib_search.json`（≥10 算例）

**Interfaces**:
- Consumes: `equipment_lib` 表（标准化沉淀记录）+ 工艺条件范围参数
- Produces: 4 维检索（TypeCode / 工艺条件 / 尺寸参数 / 关键词）+ API

- [ ] **Step 1]: 写 failing test — 验证 4 维检索各 1 例

- [ ] **Step 2]: 跑 test 验证失败

- [ ] **Step 3]: 实现 ORM + migration + 4 维检索 SQL

- [ ] **Step 4]: service + persist + schema + API

- [ ] **Step 5]: 边界测试 — 空查询返回 0 行；多维度组合查询

- [ ] **Step 6]: pytest 全量 0 regression

- [ ] **Step 7]: 单 commit — `feat(p7-s3): EQUIP_LIB 检索服务 4 维 (T1)`

### Task S3-2: 相似度计算（加权欧几里得 / 余弦，CONFIG 配置权重）

**Files**:
- Modify: `pcs-backend/app/services/equip_lib/search_service.py`（追加 similarity_score 函数）
- Create: `pcs-backend/app/services/equip_lib/similarity_service.py`
- Create: `pcs-backend/app/seeds/config_equip_lib_similarity_weights.py`（CONFIG 权重 seed）

**Interfaces**:
- Consumes: `equipment_lib` 表 + 权重 CONFIG
- Produces: 相似度评分（0–1）+ 推荐规则（≥90% 直接 / 80–90% 提示校核 / <80% 仅展示）

- [ ] **Step 1]: 写 failing test — 验证 3 档相似度推荐规则

- [ ] **Step 2]: 跑 test 验证失败

- [ ] **Step 3]: 实现 similarity_service（加权欧几里得 / 余弦）

- [ ] **Step 4]: CONFIG 权重 seed（默认 6 维字段权重）

- [ ] **Step 5]: 边界测试 — 完全相同 = 1.0；完全不同 < 0.5

- [ ] **Step 6]: pytest 全量 0 regression

- [ ] **Step 7]: 单 commit — `feat(p7-s3): EQUIP_LIB 相似度计算 (T2)`

### Task S3-3: 沉淀流程（EQUIP_LIST → EQUIP_LIB 审批 + 解耦）

**Files**:
- Create: `pcs-backend/app/services/equip_lib/settle_service.py`
- Create: `pcs-backend/app/api/v1/equip_lib.py`（POST /api/v1/equip-lib/settle + GET /pending）

**Interfaces**:
- Consumes: `EquipmentList` ORM + 标准化字段（标准图号 / 适用条件 / 材质 / 重量 / 关键尺寸 / 原项目位号）
- Produces: 沉淀记录（保留 `source_record_id` audit 线索；解耦 `source_project_id`）+ 审批流

**工时**: +0.5 人日（D3 裁决 3A：2 字段镜像 + 源状态 pull 模式 + 边界测试）

- [ ] **Step 1]: 写 failing test — 验证沉淀后 `source_project_id = NULL` 但 `source_record_id` 保留（D3 裁决 3A + Review Focus #5）

```python
# tests/services/equip_lib/test_settle_service.py
def test_settle_keeps_source_record_id_but_clears_source_project_id(db_session):
    """D3 裁决 3A: 沉淀保留 source_record_id（audit 线索），仅解耦 source_project_id"""
    lib = settle_from_equip_list(equip_id, db)
    assert lib.source_project_id is None       # 解耦
    assert lib.source_record_id == equip_id    # 保留 audit 线索
    assert lib.source_tag_number == "P-101A"   # 保留
```

- [ ] **Step 2]: 跑 test 验证失败

- [ ] **Step 3]: 实现 settle_service（标准化字段校验 + 解耦）

- [ ] **Step 4]: API 沉淀 + 待审批列表

- [ ] **Step 5]: 边界测试 — 缺少必填字段（标准图号 / 材质）抛 `SettleValidationError` + 源 EQUIP_LIST OBSOLETE 后复用库记录仍存在（D3 裁决 3A pull 模式）

```python
# tests/services/equip_lib/test_settle_service.py
def test_obsolete_source_does_not_remove_lib_record(db_session):
    """D3 裁决 3A: 源 OBSOLETE 后复用库记录仍存在（沉淀是稳定副本）"""
    lib = settle_from_equip_list(equip_id, db)
    equip = db.get(EquipmentList, equip_id)
    equip.sign_status = "OBSOLETE"
    db.commit()

    # 复用库记录仍在（不 cascade DELETE）
    assert db.get(EquipmentLib, lib.id) is not None

    # pull 模式：读时源状态为 OBSOLETE
    result = search_with_source_status({}, db)
    assert result[0].source_sign_status_live == "OBSOLETE"
```

- [ ] **Step 6]: pytest 全量 0 regression

- [ ] **Step 7]: 单 commit — `feat(p7-s3): EQUIP_LIB 沉淀流程 + 解耦 (T3)`

---

## Sprint 4（供应商数据录入 + 自动比对 + 偏差报告 + 真实算例端到端验收）

> ⚠️ **2026-10-05 修订**：
> 1. **Task S4-4 改写定义**（用户指令）：原「综合能耗验收对账（XLS 偏差 ≤2%）」的
>    前提已被用户裁决「XLS 不作为最终依据」推翻 → 改为
>    **「蜡油加氢真实数据端到端验收（6 表全链路）」**，补上 T5 封版时缺的证据
>    （XLS 的氮气/仪表空气/低温热从未走过 P7-6B 新建的 2 张表）。
>    详见下方 Task S4-4。
> 2. `catalyst_loading` 功能取消，不建表（`docs/PCS-NOTE-catalyst_loading-取消-2026-10-05.md`）
>    → **BLOCKER-2 整体关闭**，工艺室 2026-10-15 签署不再是任何在办项的前置条件。

**总工时**: ~2–2.5 人周（S4-4 改写后工作量基本持平：不再等工艺室签署，改为从 XLS 提取消耗量）

### Task S4-1: 供应商实际数据录入（手动 + Excel 批量）

**Files**:
- Modify: `pcs-backend/app/models/equip_list.py`（ActualData JSONB 字段）
- Modify: `pcs-backend/alembic/versions/p7_open_009_008_actual_data_jsonb.py`（migration）
- Create: `pcs-backend/app/services/supplier/actual_data_service.py`
- Create: `pcs-backend/app/services/supplier/excel_import_service.py`
- Create: `pcs-backend/app/schemas/supplier.py`
- Create: `pcs-backend/app/api/v1/supplier.py`（POST /equipment-list/{id}/actual-data + import）
- Test: `pcs-backend/tests/services/supplier/test_actual_data_service.py`
- Test: `pcs-backend/tests/services/supplier/fixtures/golden_actual_data.json`（≥10 算例）

**Interfaces**:
- Consumes: `EquipmentList` ORM + Excel 导入模板
- Produces: ActualData JSONB 字段 + 手动/Excel 录入 API

- [ ] **Step 1]: 写 failing test — 验证手动录入 + Excel 批量导入各 1 例

- [ ] **Step 2]: 跑 test 验证失败

- [ ] **Step 3]: 实现 actual_data_service（手动 + JSONB 校验）

- [ ] **Step 4]: 实现 excel_import_service（CONFIG 模板 + 字段映射）

- [ ] **Step 5]: 边界测试 — Excel 字段缺失抛 `ExcelImportError`；类型不匹配抛 `ActualDataValidationError`

- [ ] **Step 6]: pytest 全量 0 regression

- [ ] **Step 7]: 单 commit — `feat(p7-s4): 供应商实际数据录入 + Excel 批量导入 (T1)`

### Task S4-2: 自动比对 + 偏差报告

**Files**:
- Create: `pcs-backend/app/services/supplier/deviation_service.py`
- Create: `pcs-backend/app/api/v1/supplier.py`（GET /equipment-list/{id}/deviation-report）
- Test: `pcs-backend/tests/services/supplier/test_deviation_service.py`
- Test: `pcs-backend/tests/services/supplier/fixtures/golden_deviation_report.json`（≥5 算例，含合格/警告/不合格 3 档）

**Interfaces**:
- Consumes: 设备记录设计值 + 实际数据
- Produces: 偏差报告（合格/警告/不合格）+ 颜色标识（绿/黄/红）+ PDF/Excel 导出

- [ ] **Step 1]: 写 failing test — 验证 3 档判定 + 颜色标识（Review Focus #4）

- [ ] **Step 2]: 跑 test 验证失败

- [ ] **Step 3]: 实现 deviation_service（按 SPEC V1.4 §3.2.4（2）允许偏差表）

- [ ] **Step 4]: PDF/Excel 导出（reportlab + openpyxl）

- [ ] **Step 5]: 边界测试 — 不合格项必拒绝确认 + 通知供应商

- [ ] **Step 6]: pytest 全量 0 regression

- [ ] **Step 7]: 单 commit — `feat(p7-s4): 供应商偏差报告 3 档判定 (T2)`

### Task S4-3: 核算与更新流程（确认 + 校核 + 实际值更新 UTIL）

**Files**:
- Create: `pcs-backend/app/services/supplier/confirmation_service.py`
- Create: `pcs-backend/app/api/v1/supplier.py`（POST /equipment-list/{id}/actual-data/confirm + check）

**Interfaces**:
- Consumes: 偏差报告 + 设计人/校核人 actor
- Produces: ActualDataStatus = 已确认 + UTIL 自动引用实际值 + CIA（如必要）

- [ ] **Step 1]: 写 failing test — 验证不合格项禁止确认

- [ ] **Step 2]: 跑 test 验证失败

- [ ] **Step 3]: 实现 confirmation_service（设计人 + 校核人流程）

- [ ] **Step 4**: UTIL 实际值优先触发（per Sprint 1 Task S1-5 boundary）— D4 裁决 4A: 改 emit_event 模式（不直接调 state_machine）

- [ ] **Step 5**: CIA 触发（实际值导致设计值被替换 → CHANGED 流程）— D4 裁决 4A: Supplier 调 `emit_event('actual_data_replaces_design', equipment_id, diff, event_id=uuid4())`；**不直接调 state_machine**；state_machine listener 走 EquipmentList.CHANGED + UtilResults.recalculate（不进门禁）+ CIA.evaluate

```python
# pcs-backend/app/services/supplier/confirmation_service.py
def confirm_actual_data(equipment_id: UUID, actor: User, db: Session):
    """D4 裁决 4A: 确认实际数据 → 检测设计值替换 → 发事件（不直接迁移门禁）"""
    equip = db.get(EquipmentList, equipment_id)
    diff = compute_design_diff(equip)
    if not diff.affects_downstream:
        equip.actual_data_status = "已确认"
        db.commit()
        return
    emit_event(
        event_type="actual_data_replaces_design",
        payload={"equipment_id": str(equipment_id), "diff": diff.to_dict(),
                 "actor_id": str(actor.id), "event_id": str(uuid4())},
        db=db,
    )

# pcs-backend/app/services/state_machine.py (D4 裁决 4A listener)
def on_actual_data_replaces_design(event, db):
    """Supplier 发事件 → state_machine 走 CHANGED 门禁迁移"""
    equipment_id = UUID(event.payload["equipment_id"])
    equip = db.get(EquipmentList, equipment_id)
    equip.transition_to("CHANGED")
    audit_service.write(action="CHANGED_BY_ACTUAL_DATA",
                       resource_type="equipment_list", resource_id=equipment_id,
                       detail_json={"diff": event.payload["diff"], "event_id": event.event_id})
    recalculate_for_equipment(equipment_id, db)
    evaluate_downstream(equipment_id, db)

register_listener("actual_data_replaces_design", on_actual_data_replaces_design)
```

- [ ] **Step 6**: pytest 全量 0 regression + D4 幂等性测试 + rollback 分阶段测试（rollback 边界 TBD — 见 §未解决问题 #14）

```python
# tests/services/supplier/test_confirmation_service.py (D4 裁决 4A)
def test_actual_data_event_idempotent(db_session):
    """D4 裁决 4A: 同 event_id 重复 emit 只触发一次 CHANGED"""
    event_id = str(uuid4())
    emit_event("actual_data_replaces_design", {"equipment_id": ..., "event_id": event_id}, db)
    emit_event("actual_data_replaces_design", {"equipment_id": ..., "event_id": event_id}, db)
    assert db.query(AuditLog).filter_by(action="CHANGED_BY_ACTUAL_DATA").count() == 1

def test_rollback_after_downstream_stale(db_session):
    """D4 裁决 4A: 下游已 STALE，CIA 反向恢复 + state_machine 回滚（rollback 边界 TBD）"""
    ...
```

- [ ] **Step 7]: 单 commit — `feat(p7-s4): 供应商核算 + UTIL 实际值更新 (T3)`

### Task S4-4: 蜡油加氢真实数据端到端验收（6 表全链路）

> 🔄 **2026-10-05 改写**（用户指令「S4-4 改写定义」）。
>
> **原定义的问题**：以「蜡油加氢—综合能耗.xlsx 偏差 ≤2%」为验收判据。
> 该前提已被用户裁决「**XLS 不作为最终依据**」推翻 —— 且调查发现：
> 1. 原三个「XLS 参考值」在 XLS 全表中**不存在**，是旧代码输出反抄的自证循环；
> 2. XLS 自身 `能耗!G33` 因 `D32=#VALUE!` 算不出年总能耗；
> 3. XLS 的电折算系数 10.89 MJ/kWh 偏离 GB 30251-2024 附录A 原值
>    8.792 **+23.8%**；循环水 4.19 vs 2.51 **+67%**；除氧水 385.19 vs 272.15 **+41.5%**。
>
> 照原文执行 = 把已推翻的东西推回来。新定义如下。

**新定义**：T5 的**验收判据**已由 `docs/PCS-SIGN-T5-2026-10-05.md` 完成封版
（基准 = GB 30251-2024 附录A 表A.1 独立重算，三项 PASS）。本 Task 不再重复算
同一个数，而是补上封版时**缺的那块证据**：

> 至今所有 T5 验证都基于**合成 fixture**（`POWER_ITEMS` / `FUEL_ITEMS` /
> `HEAT_ITEMS` 三类）。XLS 里**存在的氮气、净化压缩空气、低温余热从未灌进
> `utility_gas_media` / `utility_low_temp_heat`**，而这 2 张表正是 P7-6B 收尾
> 刚建的（commit `e6efb24`）。**没有任何真实算例走过这 2 张新表。**

**Files**:
- Modify: `pcs-backend/scripts/p7_open_012_t5_r1_verification.py`
  （`_inject_case_4` 补 `UtilityGasMedia` / `UtilityLowTempHeat` seed）
- Modify: `pcs-backend/scripts/p7_open_012_t5_r1_verification.py`
  （`_gb30251_reference()` 同步补对应类别，与被测路径同源）
- Test: `pcs-backend/tests/services/util/test_utility_energy_summary.py`
  （Case 4 扩展到 5 类介质 + 低温热，断言 iso_self_consistency 仍为 0）

**Interfaces**:
- Consumes: `sample/1216D132*.xlsx` 的 `能耗` sheet 氮气 / 净化空气 / 低温余热行
  （**只取消耗量作为输入，不取其折标结果** —— 这是与旧定义的关键区别）
- Produces: Case 4 在 5 类气体介质 + 低温热全接上后的端到端验收数字，
  以及「扩类后 T5 数字变化多少」的可追溯记录

**验收判据**（区别于旧定义的 ≤2%）:
1. 三项指标 vs GB 30251 附录A 独立重算仍 ≤ 2%
2. `iso_self_consistent_pct` 仍 = 0.0%（MJ ↔ toe × 41.868）
3. 折标系数审计 `scripts/p7_open_016_config_conformance_audit.py` 仍 exit 0
4. **新增**：记录扩类前后的 T5 数字差异，并在 `docs/PCS-SIGN-T5-2026-10-05.md`
   补一节「封版后扩类影响」—— 让「T5 数字会因补全采集类别而上升」这件事有据可查，
   而不是悄悄变

- [ ] **Step 1**: 从 `sample/1216D132*.xlsx` 的 `能耗` sheet 提取氮气 / 净化空气 /
      低温余热的**年消耗量**（原始量，非折标值），标注溯源（文件名 + sheet + 单元格）
- [ ] **Step 2]: 写 failing test — Case 4 扩展到 5 类介质 + 低温热，
      断言 `gas_nm3_by_medium` 分桶正确 + `iso_self_consistent_pct == 0`
- [ ] **Step 3]: 跑 test 验证失败（当前脚本未 seed 这 2 张表）
- [ ] **Step 4**: `_inject_case_4` 补 `UtilityGasMedia`（NITROGEN / PURIFIED_AIR 等）
      + `UtilityLowTempHeat` seed；`_gb30251_reference()` 同步补对应类别
- [ ] **Step 5**: 重跑 T5 验收脚本 + 审计脚本，确认 ≤2% 且自洽性为 0
- [ ] **Step 6]: pytest 全量 0 regression
- [ ] **Step 7**: 在 `docs/PCS-SIGN-T5-2026-10-05.md` 补「封版后扩类影响」一节，
      记录数字变化 + 原因（此前氮气/仪表空气/低温热属漏算，非 PCS 算错）
- [ ] **Step 8**: 单 commit — `feat(p7-s4): 蜡油加氢真实数据端到端验收 (T4)`

**不做**（明确排除，避免 scope 蔓延）:
- ❌ 不以 XLS 折标结果作基准（已裁决作废）
- ❌ 不等工艺室 2026-10-15 签署（消耗量是工程数据，不需签署才能用）
- ❌ 不改已封版的 T5 验收判据（≤2% + GB 30251 基准）
- ❌ 不碰 `auxiliary_consumption` 4 字段（归属未定，见 catalyst_loading 取消文档）

---

## 收口

- [ ] **Step 收 1**: 4 Sprint × 25 任务全部 commit + push origin/main
- [ ] **Step 收 2**: pytest 全量 ≥ 3515 passed（baseline，P6-9-PICKUP-5 R=1 后）+ 0 failed；P7 新增测试数按各 Task 实际产出（估算 ≥ 285，验收时以实际为准）
- [ ] **Step 收 3**: ruff 全 0 + G-08 phase 1-4 drift=0
- [ ] **Step 收 4**: SPEC V1.4 验收 100% 覆盖（V1.4 §3.2.1-§3.2.4 + §4.5 + §4.7）
- [ ] **Step 收 5**: 工艺室签署 schedule 全闭环（蜡油加氢—综合能耗.xlsx + 惠州汽包实例 + T1 pcs_test fixture）
- [ ] **Step 收 6**: 5 docs 引用全部可达（`docs/P7-OPEN-007/008/009` + `docs/P7-REV-01-04-mock-decisions`）
- [ ] **Step 收 7**: bug-114（state_machine 写入） + bug-115（rules_registry）登记 + 守则增补到 `.wolf/cerebrum.md`
- [ ] **Step 收 8**: SDD workspace 清理（4 Sprint 各 workspace）

## 关键文件路径

### Sprint 1
- `pcs-backend/app/services/state_machine.py`（S1-1）
- `pcs-backend/app/models/equip_list.py`（S1-2）
- `pcs-backend/app/models/equipment_type_codes.py`（S1-3）
- `pcs-backend/app/services/equip_list/sync_service.py`（S1-4）
- `pcs-backend/app/models/util.py`（S1-5；与 Sprint 2 Task S2-1~6 append 同一文件）

### Sprint 2
- `pcs-backend/app/models/util.py`（S2-1/2/3/5/6 5 张表）
- `pcs-backend/alembic/versions/p7_open_009_00{1..6}_*.py`（6 张 alembic 迁移）
- `pcs-backend/app/services/util/utility_*_service.py`（5 张 service）
- `pcs-backend/app/seeds/config_energy_conversion_factors.py`（S2-5）

### Sprint 3
- `pcs-backend/app/models/equipment_lib.py`（S3-1）
- `pcs-backend/app/services/equip_lib/search_service.py`（S3-1）
- `pcs-backend/app/services/equip_lib/similarity_service.py`（S3-2）
- `pcs-backend/app/services/equip_lib/settle_service.py`（S3-3）

### Sprint 4
- `pcs-backend/app/services/supplier/actual_data_service.py`（S4-1）
- `pcs-backend/app/services/supplier/deviation_service.py`（S4-2）
- `pcs-backend/app/services/supplier/confirmation_service.py`（S4-3）
- `pcs-backend/tests/services/util/fixtures/golden_utility_energy_summary_real.json`（S4-4）

## 复用清单

| 现有 | 路径 | 复用任务 | 用法 |
|---|---|---|---|
| PUMP / VESSEL / HEAT / PSV / CV / COOL_TOWER / PSYCHRO / OPEN_CHANNEL ORM | `pcs-backend/app/models/calc.py` + 子包 | S1-4 | SourceModule 同步来源 |
| `Class.method` persist 模式 | `pcs-backend/app/services/psv/relief_area_service.py` | S1-4, S2-1~6, S3-1~3, S4-1~3 | 仿 P5-0 sibling |
| `APIRouter` + `require_roles` 模式 | `pcs-backend/app/api/v1/psv.py` | 全部 | 仿 PRG §3.5 |
| `SourceModule` + `SourceRecordID` | 既有 9 态门禁 + 行血 | S1-4 | V1.4 加 `SourceService` 区分同模块多子服务 |
| `RecordMixin` | `pcs-backend/app/models/mixins.py` | S1-2 | 含 stale_resolution_path / hash_changed / changed_fields 三字段 |
| `_compound_config_cache.py`（5-min TTL）| `pcs-backend/app/services/_compound_config_cache.py` | S2-5 | CONFIG 折标煤系数缓存模式 |
| `equipment_list_sync_service.py`（未来 Sprint 1）| `pcs-backend/app/services/equip_list/sync_service.py` | S2-1 | SourceModule 来源电耗设备清单 |
| `thermosiphon_circulation_results`（P5-0-1b T1）| `pcs-backend/app/models/calc.py` + service | S1-4 | V1.4 §3.2.1（1）表 1 第 11/12 行：COOL_TOWER 自动同步 / OPEN_CHANNEL 不进设备表（V1.4.1 待补 §3.2.1（1）注记）|
| `PcsError` 子类 + frozen dataclass + formula_ref dict | 项目级 service 模式 | 全部 | 不可破 |
| ChEDL 包装层 | `pcs-backend/app/services/chedl_wrapper.py` | 全部 | 业务代码禁 `import fluids.*`（ADR-0030）|
| audit_logs 三字段写入 | Task S1-1 落地 | S4-2 | CIA CHANGED 流程触发记录 |

## 端到端验证矩阵

| # | 项 | 命令 | 期望 |
|---|---|---|---|
| S1-V1 | T0 三字段写入 | `pytest tests/test_state_machine.py::test_resolve_stale_writes_audit_with_three_fields -v` | PASS |
| S1-V2 | EquipmentList ORM | `python -c "from app.models.equip_list import EquipmentList; print(len([f for f in EquipmentList.__table__.columns]))"` | ≥ 30 |
| S1-V3 | EquipmentTypeCodes seed | `python -m app.seeds.equipment_type_codes_seed` | ≥ 80 行 |
| S1-V4 | EQUIP_LIST 同步触发 | `pytest tests/services/equip_list/test_sync_service.py -v` | PASS（含 STALE 联动恢复边界）|
| S1-V5 | UTIL V1.3 基线 | `pytest tests/services/util/test_summary_service.py -v` | PASS |
| S2-V1 | utility_power_items | `python -c "from app.models.util import UtilityPowerItem; print(len([f for f in UtilityPowerItem.__table__.columns]))"` | ≥ 13 |
| S2-V2 | alembic upgrade | `cd pcs-backend && DATABASE_URL=... uv run alembic upgrade head` | OK |
| S2-V3 | utility_energy_summary 偏差 | `pytest tests/services/util/test_utility_energy_summary_service.py -v` | ≤ 2% PASS |
| S2-V4 | CONFIG 折标煤系数 seed | `python -c "from app.seeds.config_energy_conversion_factors import SEED_DATA; print(len(SEED_DATA))"` | ≥ 6 |
| S2-V5 | G-08 baseline | `bash pcs-backend/scripts/gate_08_openapi_contract.sh --check-baseline` | baseline diff = 0 |
| S3-V1 | EQUIP_LIB 4 维检索 | `pytest tests/services/equip_lib/test_search_service.py -v` | PASS |
| S3-V2 | 相似度评分 | `pytest tests/services/equip_lib/test_similarity_service.py -v` | 3 档推荐规则 PASS |
| S3-V3 | 沉淀解耦 | `pytest tests/services/equip_lib/test_settle_service.py -v` | source_project_id = NULL PASS |
| S4-V1 | 实际数据录入 | `pytest tests/services/supplier/test_actual_data_service.py -v` | PASS |
| S4-V2 | 偏差报告 3 档 | `pytest tests/services/supplier/test_deviation_service.py -v` | PASS（不合格拒绝确认）|
| S4-V3 | 核算更新 UTIL | `pytest tests/services/supplier/test_confirmation_service.py -v` | PASS |
| S4-V4 | 综合能耗验收 | `pytest tests/services/util/test_utility_energy_summary_service.py -v` | 蜡油加氢 ≤ 2% PASS |
| 收-V1 | G-08 | `bash pcs-backend/scripts/gate_08_openapi_contract.sh --check-baseline` | baseline diff = 0 |
| 收-V2 | ruff | `cd pcs-backend && uv run ruff check .` | All checks passed! |
| 收-V3 | pytest 全量 | `cd pcs-backend && DATABASE_URL=... uv run pytest tests/ -q` | ≥ 3515 passed（baseline，P6-9-PICKUP-5 R=1 后）+ 0 failed；P7 新增测试数按各 Task 实际产出（估算 ≥ 285，验收时以实际为准）|
| 收-V4 | SPEC V1.4 覆盖 | 手工 review 25 任务 vs §3.2.1-§3.2.4 + §4.5 + §4.7 | 100% |

## 风险 + 缓解

| 风险 | 等级 | 缓解 |
|---|---|---|
| R-1 T0 落地后 audit_logs 数据采集失败 | 中 | S1-1 Step 5 全量 pytest 验证；T1 fixture 提前与工艺室排期对齐 |
| R-2 工艺室 2026-10-XX 签署 schedule 冲突 | 高 | S2-5 Step 3 折标系数 seed `confirmed_by=NULL` 起步；S4-4 验收 fixture 与 10-15 签署四节点对齐 |
| R-3 EQUIP_LIST STALE 联动恢复边界未测 | 高 | S1-4 Step 5 显式测试（Review Focus #1）|
| R-4 C-16 默认不同步误实现 | 高 | S1-4 同步规则表显式条件分支；测试覆盖"PSYCHRO 触发同步请求时仅返回手动同步入口"|
| R-5 UTIL 5 表迁移链顺序错乱 | 中 | Sprint 2 严格顺序 `001→002→003→004→005→006`；每步 alembic 验证 |
| R-6 综合能耗偏差超 2% | 高 | S2-5 Step 6 + S4-4 Step 4 双重边界测试；超偏差抛 `EnergyConsumptionToleranceError` |
| R-7 不合格项被误确认 | 高 | S4-3 Step 5 边界测试（Review Focus #4）；验收逻辑前置 |
| R-8 EQUIP_LIB 沉淀解耦未实现 | 高 | S3-3 Step 5 边界测试（Review Focus #5）；source_project_id = NULL 强制 |
| R-9 R=1 lesson 再现 — closure 状态回填不可指文档 | 高 | 每个 commit msg 显式引用具体 commit SHA + file-level diff 行号 |
| R-10 R-02 否决导致 Sprint 2 全部重排 | 高 | Sprint 2 计划 mock R-02=A；真实会议否决时按 V1.4.1 micro-revision 修订 |
| R-11 R-03 T0 延期 → Sprint 1 末未落地 | 中 | S1-1 排在 Sprint 1 第 1 任务；T0 截止 P7 Sprint 0 末 |
| R-12 双向耦合（R-03 ↔ R-04）spec 未覆盖 | 低 | V1.4.1 加「R-03/R-04 联动重评」注记；SPEC V1.4 §4.7 已记录 |
| R-13 工艺室 buffer 不足（D5 裁决 5A）| 高 | 工艺室 2026-10-XX 签署四节点 10-08/10-15/10-22/10-29 任一延期 1 周即 Sprint 2 阻塞；buffer 已 0.5 → 1.5 人周 + 对账应急 1.0 → 0.5 人周合并 | Sprint 2 工艺室 fixture 落地前 |

## 工时表

| Sprint | 子任务数 | 工时 |
|---|---|---|
| Sprint 0（已完成）| 5 docs | ~1.5 人周 |
| Sprint 1 | 5 任务 | ~4.3–5.5 人周（含 T0 +0.5–1 人日 + D2 advisory lock +0.5 人日）|
| Sprint 2 | 7 任务 | ~5.0–6.5 人周（迁移本身 0.8 人周 + service/API/fixture 全口径 2–3 人周 + API 整合 + G-08 验证 + JSONB→5 表回填 0.5–0.7 人周 + **工艺室 buffer 1.5 人周（D5 裁决 5A）** + **对账应急 0.5 人周（D5 裁决 5A）**）|
| Sprint 3 | 3 任务 | ~1.5–2 人周（含 D3 source_sign_status 镜像 +0.5 人日）|
| Sprint 4 | 4 任务 | ~2.5–3 人周（含 D4 emit_event + state_machine listener + 幂等性 + rollback 测试 +0.5 人日）|
| 收口 + wolf + workspace cleanup | 1 | ~0.3 人周 |
| **总计** | **24 任务** | **~13.5–16.7 人周**（算术：1.5 + 4.2–5.4 + 4.5–5.5 + 1–1.5 + 2–2.5 + 0.3）|

> **双口径说明**：
> - **SPEC V1.4 §4.6 口径**：10–13 人周（含 SUP-010 方案 A）+ R-03 T0 0.5–1 人日 = **10.5–14 人周**（仅 P7 启动后 Sprint 1-4 主体）
> - **本计划口径**：~13.5–16.7 人周（含 Sprint 0 mock 评估 1.5 人周 + Sprint 1-4 11.7–13.4 人周 + 收口 + wolf + workspace cleanup 0.3 人周）

## 后续

P7 Sprint 1-4 完成后：
- P7 Sprint 5：P7-OPEN-007 重评（T0+T1+30 天后）
- P8 Sprint 1：REPORT 报表生成
- P9 Sprint 1：工作流与权限

## 未解决问题（10 项 — per SPEC V1.4 §4.7 mock 决议 + 用户修正口径）

| # | 项 | 阻塞点 | 截止 |
|---|---|---|---|
| 1 | T0 StateMachineService 强制写入三字段 | R-03 T0 | **P7 Sprint 1 末**（本计划 S1-1 即落地）|
| 2 | 工艺室 10 月签署 vs P6-9-PICKUP-6 5D-2 重叠 | R-02=A + OPEN-P6-6A-9.x/10 双线并行 | 2026-10-08 前确认 |
| 3 | pcs_test DB 预填 ≥30 行 STALE fixture | R-03 T1 + 工艺室签署（PROCo 标记）| T0 落地后并行 |
| 4 | mock 决议真实会议确认 | R-02 否决 → Sprint 2 联动重排 | 待会议召开（建议 Sprint 1 启动前 1 周内）|
| 5 | V1.7 §3.5 脚注增补 | R-04 建议 | V1.7 发布（或 Sprint 1 内，取先到者）|
| 6 | P7 Sprint 1/2 启动前置依赖 | Sprint 1 = T0+5 表迁移启动；Sprint 2 = UTIL service+API（依赖 Sprint 1）；Sprint 3-4 独立线 | 分阶段 |
| 7 | R=1 lesson 守则增补 | bug-114/115 → `.wolf/cerebrum.md` | **P7 Sprint 1 内**（避免新开发者踩坑）|
| 8 | R-03 ↔ R-04 双向耦合 | R-03→R-04 与 R-04→R-03 均成立；建议 V1.4.1 加「R-03/R-04 联动重评」注记 | 重评时 |
| 9 | P7 SPEC V1.4 残留修补 | 已闭环（commits `a902d2f` 主体 + `4f0d671` 残留修补 — 4 残留 + 5 次要）| ✅ 已完成 — source-verify 证明：`grep -c "P7-OPEN-007\\|P7-OPEN-008\\|P7-OPEN-009" spec/...P7.md = 20 ≥ 3` + `grep -c "R-02 落地要求" spec/...P7.md = 1` + `grep -c "R-03（待补采）落地要求" spec/...P7.md = 1` + `grep -c "^## 版本历史" spec/...P7.md = 1` + `grep -c "\| 触发方式 \| 场景 \| 行为 \|" spec/...P7.md = 1` |
| 10 | R-02 方案 A 工艺室签署 vs P6 时间窗 | 10-08~10-29 四节点与 5D-2 启动窗口重叠 | 2026-10-08 前 |
| 11 | UTIL 双写权威性（D1 裁决 1A）| Sprint 2 起 5 表权威 + JSONB deprecated；Sprint 1 JSONB 写路径须在 Sprint 2 Task S2-7 Step 2.5 关闭 + Step 2.6 数据回填（jsonb_to_5tables_migration.py）| Sprint 2 Task S2-7 末 |
| 12 | sync_from_source 并发控制（D2 裁决 2A）| advisory lock per (project_id, tag_number) + UNIQUE 复合约束双保险；Sprint 4 Task S4-3 复用同锁 key；Task S1-2 ORM `unique=True` 误伤跨项目位号 → 改 UniqueConstraint(project_id, tag_number) | Sprint 1 Task S1-4 末 |
| 13 | EQUIP_LIB 沉淀源 OBSOLETE 联动（D3 裁决 3A）| source_record_id 保留 + cascade=SET NULL + source_sign_status 镜像（pull 模式读时 join）；Task S3-3 Step 1 明确 source_record_id 保留（不仅 source_project_id 解耦）| Sprint 3 Task S3-3 末 |
| 14 | 供应商实际值 CHANGED 所有权（D4 裁决 4A + rollback 仅记）| state_machine 拥有触发权；Supplier/UtilResults/EquipmentList 通过 emit_event 发事件；事件幂等性 + rollback 仅 audit 记录（不实现 CIA 反向恢复，推 P8）；已确认实际数据修改走人工退回（per SPEC V1.4 §3.2.4（5））| Sprint 4 Task S4-3 末 |
| 15 | audit_logs 高频写入性能（D8 裁决 9A）| Sprint 1 已加 JSONB GIN 索引（p7_s1_002）；Sprint 4 后加 monthly partition（保留 6 月，p7_s4_001_audit_logs_partition）；异步队列可选 | Sprint 1 Task S1-1 末 / Sprint 4 后增量 |
| 16 | search_service pull mirror 高频读（D9 裁决 10A）| source_sign_status 30s TTL 缓存；累积延迟 ↓ 5 万 join/天 → 缓存复用 | Sprint 3 Task S3-1 末 || Sprint 1 已加 JSONB GIN 索引（p7_s1_002）；Sprint 4 后加 monthly partition（保留 6 月，p7_s4_001_audit_logs_partition）；异步队列可选 | Sprint 1 Task S1-1 末 / Sprint 4 后增量 || state_machine 拥有触发权；Supplier/UtilResults/EquipmentList 通过 emit_event 发事件；事件幂等性 + rollback 仅 audit 记录（不实现 CIA 反向恢复，推 P8）；已确认实际数据修改走人工退回（per SPEC V1.4 §3.2.4（5））| Sprint 4 Task S4-3 末 |
| 15 | audit_logs 高频写入性能（D8 裁决 9A）| Sprint 1 已加 JSONB GIN 索引（p7_s1_002）；Sprint 4 后加 monthly partition（保留 6 月，p7_s4_001_audit_logs_partition）；异步队列可选 | Sprint 1 Task S1-1 末 / Sprint 4 后增量 || state_machine 拥有触发权；Supplier/UtilResults/EquipmentList 通过 emit_event 发事件；事件幂等性 + rollback 仅 audit 记录（不实现 CIA 反向恢复，推 P8）；已确认实际数据修改走人工退回（per SPEC V1.4 §3.2.4（5））| Sprint 4 Task S4-3 末 |

## 关联

- 上游：`spec/工艺专用综合计算软件需求规格说明书 Web版 P7.md` V1.4
- 上游：`docs/P7-REV-01-04-mock-decisions.md`
- 上游：`docs/P7-OPEN-007-physical-semantics-evaluation.md`
- 上游：`docs/P7-OPEN-008-rule-registry-form-evaluation.md`
- 上游：`docs/P7-OPEN-009-SUP-010-5table-migration-schedule.md`
- buglog：bug-114（P7-OPEN-007 R=1）+ bug-115（P7-OPEN-008 R=1）
- 守则：`.wolf/cerebrum.md` Do-Not-Repeat「implementer 必须先 source-verify brief」
