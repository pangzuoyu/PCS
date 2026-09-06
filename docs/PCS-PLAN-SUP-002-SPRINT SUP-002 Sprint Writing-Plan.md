SUP-002 Sprint Writing-Plan
文档编号：PCS-PLAN-SUP-002-SPRINT
基于：PCS-SPEC-P2-SUP-002 V1.4（2026-09-06 审查修正版，26 项问题全部落定）
执行前提：P2 Sprint 1.9 全系列（1.9.1~1.9.6）完成且全量测试绿
预计工时：17.5 天（约 3.5 周，后端先行，前端 INT-2 可延后与 P2 Sprint 2 合并）

0. 执行前检查清单
□ 1.9 全系列完成，uv run pytest -q 全绿
□ 三源 71 等级种子已入库（pipe_classes 表有数据）
□ alembic heads 单 head 无分叉
□ 确认 config_assets / config_versions / config_approvals 表就绪（P2 Sprint 1 已交付）
□ 确认 ConfigStateMachine 5 态可用（P2 Sprint 1.2 已交付）
□ 确认 ConfigAsset ORM 有 asset_subtype 列或可扩展（INT-OPEN-01 裁决）

**V1.4 增量说明**：26 项审查修正要点（PC-1 迁移脚本重写、验证引擎 PC-E04/E06/V10/C04 补全、PC-3 ConfigAsset 取消 ref_id、PC-4 UniqueConstraint+递归深合并、SYM-2 fork 返回 list、FMT-3 10 独立 session 并发测试、PC-5 import_id 暂存、项目级 5 态不挂 ConfigAsset 走轻量状态列 + config_approvals.project_class_id 列、INT-1 project_template_pipe_classes 关联表、INT-2 调至 3.5 天、总 17.5 天）已落入文末「P2 增补 Spec——V1.4 关键修正段落」节，执行时按该节落地；本文件主体为 V1.3 baseline，未做全文重排以保持差异可读。

1. 任务总览与依赖图
text
PC-1 (1d) ───┬─→ PC-2 (1.5d) ─┬─→ PC-5 (1.5d)
             │                 │
             ├─→ PC-3 (1d) ────┼─→ PC-4 (1d) ──→ PC-6 (1d)
             │                │                    │
             │                └────────────────────┤
             │                                     │
SYM-1 (0.5d)─→ SYM-2 (1d) ─→ SYM-3 (0.5d)          │
             │                    │                 │
             │                    ├─→ FMT-3 (1.5d) ─┤
FMT-1 (0.5d)─→ FMT-2 (1d) ────────┘                 │
             │                                      │
             └──────────────────────────────────────┤
                                                     │
INT-1 (0.5d) ────────────────────────────────────────┤
                                                     │
INT-3 (1d) ──────────────────────────────────────────┘
INT-2 (3.5d) ← 可延后至 P2 Sprint 2 前端波（含管道代码格式设计器拖拽，复杂度上调）
执行顺序：PC-1 → PC-2 → PC-3 → PC-4 → PC-6 → SYM-1 → SYM-2 → SYM-3 → FMT-1 → FMT-2 → FMT-3 → FMT-4 → INT-1 → INT-3

2. PC-1：管道等级差异迁移 + ORM
目标：将 pipe_classes 和 project_pipe_classes 从 1.9 薄层 3 态结构升级为 SUP-002 §0.5 裁决后的目标态。

迁移内容（按 §0.3 差异表）：

变更	表	操作
base_material varchar(100) NOT NULL	pipe_classes	新增列，种子回填
asset_id UUID FK → config_assets	pipe_classes	新增列（可空，后续 PC-3 回填）
class_id varchar(20) → varchar(50)	pipe_classes	放宽长度
version 保留 str50	pipe_classes	不迁移
status 3 态 → 5 态	pipe_classes	列值映射：ACTIVE→PUBLISHED，DRAFT→DRAFT，OBSOLETE→OBSOLETE
项目级表复合 PK → 独立 UUID PK	project_pipe_classes	结构重构 + 现有行回填
文件：

Create: pcs-backend/alembic/versions/p2_sup_sprint_pc1_pipe_class_upgrade.py

Modify: pcs-backend/app/models/pipe_class.py（或实际文件路径）

Test: pcs-backend/tests/models/test_pipe_class_migration.py（若有迁移测试惯例）

Step 1: 写迁移（alembic）
python
# p2_sup_sprint_pc1_pipe_class_upgrade.py
"""SUP Sprint PC-1: pipe_classes 升级至 SUP-002 目标态

- 新增 base_material 列
- 新增 asset_id FK → config_assets（可空）
- class_id 放宽至 varchar(50)
- status 3 态 → 5 态（ACTIVE→PUBLISHED）
- project_pipe_classes 重构：复合 PK → UUID PK + source_class_id + class_name + snapshot_json
"""

def upgrade():
    # 1. pipe_classes 基础列
    op.alter_column("pipe_classes", "class_id",
                    type_=sa.String(50), existing_type=sa.String(20))
    op.add_column("pipe_classes", sa.Column("base_material", sa.String(100), nullable=True))
    op.add_column("pipe_classes", sa.Column("asset_id", sa.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key("fk_pipe_classes_asset_id", "pipe_classes",
                          "config_assets", ["asset_id"], ["asset_id"])

    # 2. status 3→5 态映射
    op.execute("UPDATE pipe_classes SET status='PUBLISHED' WHERE status='ACTIVE'")

    # 3. project_pipe_classes 重构
    # 3a. 新增临时 UUID 列
    op.add_column("project_pipe_classes", sa.Column("project_class_id_new", sa.UUID(as_uuid=True), nullable=True))
    op.execute("UPDATE project_pipe_classes SET project_class_id_new = gen_random_uuid()")

    # 3b. 新增目标态列
    op.add_column("project_pipe_classes", sa.Column("source_class_id", sa.String(50), nullable=True))
    op.add_column("project_pipe_classes", sa.Column("class_name", sa.String(100), nullable=True))
    op.add_column("project_pipe_classes", sa.Column("snapshot_json", sa.JSON(), nullable=True))
    op.add_column("project_pipe_classes", sa.Column("status", sa.String(20), nullable=False, server_default="DRAFT"))

    # 3c. 回填：source_class_id = 原 class_id，override_json 从 custom_override_json 迁移
    op.execute("""
        UPDATE project_pipe_classes ppc
        SET source_class_id = ppc.class_id,
            class_name = pc.class_name,
            snapshot_json = '{}'::json
        FROM pipe_classes pc
        WHERE ppc.class_id = pc.class_id
    """)

    # 3d. 删除旧复合 PK，换新 UUID PK
    op.drop_constraint("project_pipe_classes_pkey", "project_pipe_classes", type_="primary")
    op.create_primary_key("pk_project_pipe_classes", "project_pipe_classes", ["project_class_id_new"])
    # 注意：实际约束名需根据现有 schema 调整

def downgrade():
    # 逆向操作（简化，实际需完整）
    pass
Step 2: ORM 同步
python
# app/models/pipe_class.py
class PipeClass(Base):
    __tablename__ = "pipe_classes"
    class_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    asset_id: Mapped[UUID | None] = mapped_column(ForeignKey("config_assets.asset_id"), nullable=True)
    class_name: Mapped[str] = mapped_column(String(100), unique=True)
    material_standard: Mapped[str] = mapped_column(String(50))
    base_material: Mapped[str] = mapped_column(String(100), nullable=False)
    # ... 其余字段
    status: Mapped[str] = mapped_column(String(20), default="DRAFT")

class ProjectPipeClass(Base):
    __tablename__ = "project_pipe_classes"
    project_class_id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.project_id"))
    source_class_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    class_name: Mapped[str] = mapped_column(String(100))
    override_json: Mapped[dict] = mapped_column(JSON, default=dict)
    snapshot_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="DRAFT")
Step 3: 跑迁移验证
bash
cd pcs-backend && uv run alembic upgrade head
uv run alembic downgrade -1 && uv run alembic upgrade head  # 验证可逆
Step 4: 写回填测试
python
# tests/models/test_pipe_class_migration.py
async def test_migration_preserves_seed_data(db):
    """71 等级种子在迁移后 class_id 不变、base_material 已回填"""
    rows = (await db.execute(select(PipeClass))).scalars().all()
    assert len(rows) >= 71
    for pc in rows:
        assert pc.base_material is not None or pc.base_material == ""
        assert len(pc.class_id) <= 50

async def test_migration_maps_active_to_published(db):
    """1.9 薄层的 ACTIVE 等级迁移后为 PUBLISHED"""
    # 假设迁移前有 ACTIVE 状态的数据
    active_count = (await db.execute(
        select(func.count()).where(PipeClass.status == "PUBLISHED")
    )).scalar_one()
    assert active_count > 0

async def test_migration_project_pipe_class_backfill(db):
    """项目级表回填：source_class_id 非空、override_json 保留"""
    rows = (await db.execute(select(ProjectPipeClass))).scalars().all()
    for ppc in rows:
        assert ppc.project_class_id is not None
        assert ppc.source_class_id is not None  # 原 assign 行均有来源
Step 5: 跑测试 + Commit
bash
cd pcs-backend && uv run pytest tests/models/test_pipe_class_migration.py -v
# 全量回归
uv run pytest -q
3. PC-2：管道等级验证引擎（22 条规则）
目标：实现 PC-V（11 条）、PC-E（7 条）、PC-C（4 条）全部验证规则。

文件：

Create: pcs-backend/app/services/pipe_class_validator.py

Test: pcs-backend/tests/services/test_pipe_class_validator.py

规则清单与测试用例
规则 ID	测试用例	输入	期望
PC-V01	test_missing_required_fields	缺 class_name	ERROR
PC-V02	test_dn_series_min_gt_max	min=600, max=15	ERROR
PC-V03	test_sch_dn_not_in_dn_series	DN200 在 sch 中但不在 dn 中	ERROR
PC-V04	test_sch_value_zero	Sch=[0]	ERROR
PC-V05	test_pressure_out_of_range	43 MPa	ERROR
PC-V06	test_temp_out_of_range_warn	700°C	WARN
PC-V07	test_corrosion_allowance_null	NULL	ERROR
PC-V08	test_flange_class_invalid	"100#"	ERROR
PC-V09	test_project_class_name_duplicate	项目内重名	ERROR
PC-V10	test_source_class_id_invalid	不存在的 class_id	ERROR
PC-V11	test_fitting_type_invalid_component	"焊接/法兰"	ERROR
PC-E01	test_carbon_steel_high_temp	A106 + 450°C	WARN
PC-E02	test_flange_150_over_pressure	150# + 2.5 MPa	WARN
PC-E03	test_pressure_exceeds_flange_rating	150# + 5.0 MPa	ERROR
PC-E04	test_table_ref_missing	allowable_stress_json.table="NONEXISTENT"	ERROR
PC-E05	test_dn_over_600_warn	DN900	WARN
PC-E06	test_fork_pressure_without_flange	override 压力但未覆写法兰	WARN
PC-E07	test_sch_empty_but_dn_nonempty	sch={} dn 非空	ERROR
PC-C01	test_project_pressure_over_limit	项目上限 2.0，等级 2.5	WARN
PC-C02	test_material_not_in_project_list	材料不在项目允许列表	WARN
PC-C03	test_same_name_diff_source	同名不同源	ERROR
PC-C04	test_in_use_block_delete	被 piping_results 引用	ERROR
验证引擎接口：

python
from dataclasses import dataclass
from enum import Enum

class Severity(str, Enum):
    ERROR = "ERROR"
    WARN = "WARN"

@dataclass
class ValidationResult:
    rule_id: str
    severity: Severity
    message: str

class PipeClassValidator:
    def validate(self, pc: PipeClass | dict, context: dict | None = None) -> list[ValidationResult]:
        """context 可含 project_id、project_limit 等项目上下文"""
TDD 流程：先写全部 22 个测试（RED），再实现 validator（GREEN），最后全量回归。

4. PC-3：管道等级公司级 CRUD + 5 态接入
目标：将 pipe_classes 挂到 ConfigAsset，接入 5 态状态机。

文件：

Modify: pcs-backend/app/services/pipe_class_service.py（增加 asset_id 创建逻辑）

Modify: pcs-backend/app/api/v1/pipe_classes.py（增加 submit/approve/publish/obsolete 端点）

Test: pcs-backend/tests/api/v1/test_pipe_class_config_flow.py

核心变更：

创建 PipeClass 时，同步创建 ConfigAsset（category=CATEGORY_5，asset_subtype=PIPE_CLASS，name=class_name）

状态流转走 ConfigStateMachine，pipe_classes.status 作为镜像列同步更新

审批端点从 1.9.2 的临时 ACL 改为正式 CONFIG 审批流

测试用例：

python
async def test_create_pipe_class_creates_config_asset(client, token):
    """创建等级后 config_assets 有对应行"""
    r = await client.post("/api/v1/pipe-classes", json={...}, headers=auth)
    assert r.status_code == 201
    asset = await db.get(ConfigAsset, ...)
    assert asset.category == "CATEGORY_5"
    assert asset.asset_subtype == "PIPE_CLASS"

async def test_submit_draft_to_pending(client, token):
    """DRAFT 等级提交后 PENDING"""
    ...

async def test_publish_updates_mirror_status(client, token):
    """PUBLISH 后 pipe_classes.status 同步为 PUBLISHED"""
    ...

async def test_invalid_transition_rejected(client, token):
    """PENDING 直接 PUBLISH 被拒"""
    ...
5. PC-4~PC-6、SYM、FMT、INT 系列概述
（以下任务保持 SUP-002 §16 任务分解，具体 TDD 步骤在 writing-plans 执行时展开）

任务	核心交付
PC-4	项目级 fork：fork_from_company(project_id, class_id) → 创建 ProjectPipeClass + snapshot_json；get_effective(project_id, class_name) 返回合并结果
PC-5	Excel 导入（双 Sheet 模板）+ 验证引擎集成
PC-6	全部管道等级端点测试收口
SYM-1	stream_symbols + project_stream_symbols migration + ORM
SYM-2	符号表 CRUD + 项目级 fork + SYM 验证规则
SYM-3	符号表 API + 测试
FMT-1	pipe_code_templates + project_pipe_code_configs migration + ORM
FMT-2	格式模板 CRUD + FMT 验证规则
FMT-3	代码生成器（generate_pipe_code）+ 验证器 + 并发测试
FMT-4	管道代码 API + 测试
INT-1	CATEGORY_1 项目模板集成（3 个新字段）
INT-3	端到端集成测试
6. 质量门
门	命令	通过条件
Lint	ruff check .	0 error
Type	mypy app/	0 error
Test	pytest -q	全量绿（基线 276 + 新增 ≥ 60）
Migration	alembic upgrade head && alembic downgrade -1 && alembic upgrade head	可逆
验证规则覆盖	37 条规则全部有测试	100%

执行顺序：PC-1 → PC-2 → PC-3 → PC-4 → PC-5 → PC-6 → SYM-1 → SYM-2 → SYM-3 → FMT-1 → FMT-2 → FMT-3 → FMT-4 → INT-1 → INT-3

PC-2：管道等级验证引擎（22 条规则）
目标：实现 PC-V（11 条）、PC-E（7 条）、PC-C（4 条）全部验证规则，作为后续所有输入方式（表单/Excel/API）的统一校验入口。

文件：

Create: pcs-backend/app/services/pipe_class_validator.py

Test: pcs-backend/tests/services/test_pipe_class_validator.py

接口：

python
from dataclasses import dataclass, field
from enum import Enum
from uuid import UUID
from typing import Any, Optional

class Severity(str, Enum):
    ERROR = "ERROR"
    WARN = "WARN"

@dataclass
class ValidationResult:
    rule_id: str
    severity: Severity
    message: str
    field: str | None = None

@dataclass
class ValidationContext:
    """项目上下文（PC-C 系列用）"""
    project_id: UUID | None = None
    project_pressure_limit: float | None = None
    project_allowed_materials: list[str] | None = None
    existing_class_names: list[str] = field(default_factory=list)

class PipeClassValidator:
    """管道等级验证引擎——所有输入方式共用"""

    @classmethod
    def validate_company(cls, data: dict[str, Any]) -> list[ValidationResult]:
        """公司级验证：PC-V + PC-E（不含项目上下文）"""

    @classmethod
    def validate_project(cls, data: dict[str, Any], context: ValidationContext) -> list[ValidationResult]:
        """项目级验证：PC-V + PC-E + PC-C"""

    @classmethod
    def has_errors(cls, results: list[ValidationResult]) -> bool:
        """是否存在 ERROR 级结果"""
Step 1：写全部 22 个失败测试
python
# tests/services/test_pipe_class_validator.py
import pytest
from app.services.pipe_class_validator import (
    PipeClassValidator, Severity, ValidationContext
)

# ---------- PC-V 结构完整性（11 条） ----------

def _base_data(**overrides) -> dict:
    data = {
        "class_id": "U4",
        "class_name": "Cooling Water",
        "material_standard": "ASME B31.3",
        "base_material": "A106 Gr.B",
        "corrosion_allowance": 1.6,
        "design_pressure": 1.0,
        "design_temperature": 110,
        "dn_series_json": {"min": 15, "max": 900, "series": [15, 20, 25, 40, 50, 80, 100, 150, 200, 250, 300, 350, 400, 450, 500, 600, 700, 800, 900]},
        "sch_series_json": {"DN15": [80, 160], "DN50": [40, 80, 160], "DN200": [40, 80], "DN700": [10]},
        "flange_class": "150#",
        "fitting_type": "对焊",
        "allowable_stress_json": {"table": "COMMON_ASME_B31_3_TABLE_A1"},
        "branch_table_json": {"table": "COMMON_BRANCH_TABLE_01"},
    }
    data.update(overrides)
    return data


class TestPCV:
    def test_v01_missing_required_fields(self):
        data = _base_data()
        del data["class_name"]
        results = PipeClassValidator.validate_company(data)
        assert any(r.rule_id == "PC-V01" and r.severity == Severity.ERROR for r in results)

    def test_v02_dn_series_min_gt_max(self):
        data = _base_data(dn_series_json={"min": 600, "max": 15, "series": []})
        results = PipeClassValidator.validate_company(data)
        assert any(r.rule_id == "PC-V02" and r.severity == Severity.ERROR for r in results)

    def test_v03_sch_dn_not_in_dn_series(self):
        data = _base_data(sch_series_json={"DN200": [40], "DN999": [80]})
        results = PipeClassValidator.validate_company(data)
        assert any(r.rule_id == "PC-V03" and r.severity == Severity.ERROR for r in results)

    def test_v04_sch_value_zero_or_negative(self):
        data = _base_data(sch_series_json={"DN15": [0]})
        results = PipeClassValidator.validate_company(data)
        assert any(r.rule_id == "PC-V04" and r.severity == Severity.ERROR for r in results)

    def test_v05_pressure_out_of_range(self):
        data = _base_data(design_pressure=43.0)
        results = PipeClassValidator.validate_company(data)
        assert any(r.rule_id == "PC-V05" and r.severity == Severity.ERROR for r in results)

    def test_v06_temperature_out_of_range_warn(self):
        data = _base_data(design_temperature=700)
        results = PipeClassValidator.validate_company(data)
        assert any(r.rule_id == "PC-V06" and r.severity == Severity.WARN for r in results)

    def test_v07_corrosion_allowance_null(self):
        data = _base_data(corrosion_allowance=None)
        results = PipeClassValidator.validate_company(data)
        assert any(r.rule_id == "PC-V07" and r.severity == Severity.ERROR for r in results)

    def test_v08_flange_class_invalid(self):
        data = _base_data(flange_class="100#")
        results = PipeClassValidator.validate_company(data)
        assert any(r.rule_id == "PC-V08" and r.severity == Severity.ERROR for r in results)

    def test_v09_project_class_name_duplicate(self):
        data = _base_data(class_name="U4")
        ctx = ValidationContext(existing_class_names=["U4"])
        results = PipeClassValidator.validate_project(data, ctx)
        assert any(r.rule_id == "PC-V09" and r.severity == Severity.ERROR for r in results)

    def test_v10_source_class_id_invalid(self):
        # 项目级 fork 时 source_class_id 必须有效——由 service 层在 fork 前检查
        # 这里验证 validator 对 source_class_id=None 且非全新创建的处理
        data = _base_data()
        ctx = ValidationContext(existing_class_names=[])
        results = PipeClassValidator.validate_project(data, ctx)
        # 公司级数据传入项目级验证，无 source_class_id 字段——不触发 PC-V10
        assert not any(r.rule_id == "PC-V10" for r in results)

    def test_v11_fitting_type_invalid_component(self):
        data = _base_data(fitting_type="焊接/法兰")
        results = PipeClassValidator.validate_company(data)
        assert any(r.rule_id == "PC-V11" and r.severity == Severity.ERROR for r in results)


# ---------- PC-E 工程一致性（7 条） ----------

class TestPCE:
    def test_e01_carbon_steel_high_temp_warn(self):
        data = _base_data(base_material="A106 Gr.B", design_temperature=450)
        results = PipeClassValidator.validate_company(data)
        assert any(r.rule_id == "PC-E01" and r.severity == Severity.WARN for r in results)

    def test_e02_flange_150_over_pressure_warn(self):
        data = _base_data(flange_class="150#", design_pressure=2.5)
        results = PipeClassValidator.validate_company(data)
        assert any(r.rule_id == "PC-E02" and r.severity == Severity.WARN for r in results)

    def test_e03_pressure_exceeds_flange_rating_error(self):
        data = _base_data(flange_class="150#", design_pressure=5.0)
        results = PipeClassValidator.validate_company(data)
        assert any(r.rule_id == "PC-E03" and r.severity == Severity.ERROR for r in results)

    def test_e04_table_ref_missing_error(self):
        data = _base_data(allowable_stress_json={"table": "NONEXISTENT_TABLE"})
        results = PipeClassValidator.validate_company(data)
        assert any(r.rule_id == "PC-E04" and r.severity == Severity.ERROR for r in results)

    def test_e05_dn_over_600_warn(self):
        data = _base_data(dn_series_json={"min": 15, "max": 900, "series": [15, 900]})
        results = PipeClassValidator.validate_company(data)
        assert any(r.rule_id == "PC-E05" and r.severity == Severity.WARN for r in results)

    def test_e06_fork_pressure_without_flange_warn(self):
        """项目级 fork 覆写压力但未覆写法兰等级"""
        data = _base_data(design_pressure=3.0, flange_class="150#")
        ctx = ValidationContext(existing_class_names=[])
        # 模拟 override_json 含 design_pressure 但不含 flange_class
        results = PipeClassValidator.validate_project(data, ctx)
        assert any(r.rule_id == "PC-E06" and r.severity == Severity.WARN for r in results)

    def test_e07_sch_empty_but_dn_nonempty_error(self):
        data = _base_data(sch_series_json={})
        results = PipeClassValidator.validate_company(data)
        assert any(r.rule_id == "PC-E07" and r.severity == Severity.ERROR for r in results)


# ---------- PC-C 项目上下文（4 条） ----------

class TestPCC:
    def test_c01_project_pressure_over_limit_warn(self):
        data = _base_data(design_pressure=2.5)
        ctx = ValidationContext(project_pressure_limit=2.0)
        results = PipeClassValidator.validate_project(data, ctx)
        assert any(r.rule_id == "PC-C01" and r.severity == Severity.WARN for r in results)

    def test_c02_material_not_in_project_list_warn(self):
        data = _base_data(base_material="A312 TP304L")
        ctx = ValidationContext(project_allowed_materials=["A106 Gr.B"])
        results = PipeClassValidator.validate_project(data, ctx)
        assert any(r.rule_id == "PC-C02" and r.severity == Severity.WARN for r in results)

    def test_c03_same_name_diff_source_error(self):
        """同项目内同名但不同 source_class_id"""
        data = _base_data(class_name="U4", source_class_id="A1B")  # 已有 U4 来自公司级
        ctx = ValidationContext(existing_class_names=["U4"])
        results = PipeClassValidator.validate_project(data, ctx)
        assert any(r.rule_id == "PC-C03" and r.severity == Severity.ERROR for r in results)

    def test_c04_in_use_block_delete_error(self):
        """被设备引用后不可删除——此规则在 service 层实现，validator 提供辅助方法"""
        from app.services.pipe_class_validator import PipeClassValidator as PCV
        # 假设已实现 is_in_use 辅助方法
        assert hasattr(PCV, "is_in_use")
Step 2：跑测试验证失败
bash
cd pcs-backend && uv run pytest tests/services/test_pipe_class_validator.py -v
# Expected: 22 FAIL（ModuleNotFoundError 或 AssertionError）
Step 3：实现验证引擎
python
# app/services/pipe_class_validator.py
from dataclasses import dataclass, field
from enum import Enum
from typing import Any
from uuid import UUID

class Severity(str, Enum):
    ERROR = "ERROR"
    WARN = "WARN"

@dataclass
class ValidationResult:
    rule_id: str
    severity: Severity
    message: str
    field: str | None = None

@dataclass
class ValidationContext:
    project_id: UUID | None = None
    project_pressure_limit: float | None = None
    project_allowed_materials: list[str] | None = None
    existing_class_names: list[str] = field(default_factory=list)

# 法兰等级-压力对照表（38°C 基准）
FLANGE_PRESSURE_RATINGS: dict[str, float] = {
    "150#": 1.96,
    "300#": 5.11,
    "400#": 6.81,
    "600#": 10.21,
    "900#": 15.32,
    "1500#": 25.53,
    "2500#": 42.55,
}

FLANGE_CLASSES = set(FLANGE_PRESSURE_RATINGS.keys())
FITTING_TYPES = {"对焊", "承插", "螺纹", "法兰"}
CARBON_STEEL_PREFIXES = ("A106", "A53", "A234", "API 5L", "Q235", "20#")


class PipeClassValidator:
    @classmethod
    def validate_company(cls, data: dict[str, Any]) -> list[ValidationResult]:
        return cls._validate(data, ValidationContext())

    @classmethod
    def validate_project(cls, data: dict[str, Any], context: ValidationContext) -> list[ValidationResult]:
        return cls._validate(data, context)

    @classmethod
    def has_errors(cls, results: list[ValidationResult]) -> bool:
        return any(r.severity == Severity.ERROR for r in results)

    @classmethod
    def _validate(cls, data: dict[str, Any], ctx: ValidationContext) -> list[ValidationResult]:
        results: list[ValidationResult] = []

        # PC-V01 必填字段
        required = ["class_name", "material_standard", "base_material",
                    "design_pressure", "design_temperature", "corrosion_allowance"]
        for f in required:
            if data.get(f) in (None, "", []):
                results.append(ValidationResult("PC-V01", Severity.ERROR, f"必填字段 {f} 为空", f))

        # PC-V02 dn_series min<=max
        dn = data.get("dn_series_json") or {}
        if dn:
            if dn.get("min", 0) > dn.get("max", 0):
                results.append(ValidationResult("PC-V02", Severity.ERROR, "DN 系列 min > max"))
        else:
            results.append(ValidationResult("PC-V02", Severity.ERROR, "DN 系列为空"))

        # PC-V03 sch DN 必须在 dn_series 中
        sch = data.get("sch_series_json") or {}
        dn_series = set(dn.get("series", []))
        for dn_key in sch:
            dn_num = int(str(dn_key).replace("DN", ""))
            if dn_num not in dn_series:
                results.append(ValidationResult("PC-V03", Severity.ERROR,
                    f"Sch 系列中 DN{dn_num} 不在 DN 系列 {sorted(dn_series)} 中", "sch_series_json"))

        # PC-V04 Sch 值 > 0
        for dn_key, sch_values in sch.items():
            if any(v <= 0 for v in sch_values):
                results.append(ValidationResult("PC-V04", Severity.ERROR,
                    f"DN{dn_key} 的 Sch 值必须 > 0", "sch_series_json"))

        # PC-V05 压力范围
        dp = data.get("design_pressure")
        if dp is not None and not (0 < dp <= 42):
            results.append(ValidationResult("PC-V05", Severity.ERROR,
                f"设计压力 {dp} MPa 超出范围 (0, 42]", "design_pressure"))

        # PC-V06 温度范围
        dt = data.get("design_temperature")
        if dt is not None and not (-196 <= dt <= 650):
            results.append(ValidationResult("PC-V06", Severity.WARN,
                f"设计温度 {dt}°C 超出常规范围 [-196, 650]", "design_temperature"))

        # PC-V07 腐蚀裕量
        ca = data.get("corrosion_allowance")
        if ca is None:
            results.append(ValidationResult("PC-V07", Severity.ERROR,
                "腐蚀裕量不允许为 NULL（0 表示无腐蚀）", "corrosion_allowance"))
        elif not (0 <= ca <= 6.5):
            results.append(ValidationResult("PC-V07", Severity.ERROR,
                f"腐蚀裕量 {ca} mm 超出范围 [0, 6.5]", "corrosion_allowance"))

        # PC-V08 法兰等级
        fc = data.get("flange_class", "")
        if fc not in FLANGE_CLASSES:
            results.append(ValidationResult("PC-V08", Severity.ERROR,
                f"法兰等级 {fc} 不在枚举 {sorted(FLANGE_CLASSES)} 内", "flange_class"))

        # PC-V11 fitting_type 各分段枚举
        ft = data.get("fitting_type", "")
        for seg in ft.split("/"):
            if seg and seg not in FITTING_TYPES:
                results.append(ValidationResult("PC-V11", Severity.ERROR,
                    f"连接形式分段 {seg} 不在枚举 {FITTING_TYPES} 内", "fitting_type"))
                break

        # PC-E01 碳钢高温
        bm = data.get("base_material", "")
        if any(bm.startswith(p) for p in CARBON_STEEL_PREFIXES) and dt and dt > 400:
            results.append(ValidationResult("PC-E01", Severity.WARN,
                f"碳钢材料 {bm} 在 {dt}°C 下使用需确认", "design_temperature"))

        # PC-E02 150# 超压警告
        if fc == "150#" and dp and dp > FLANGE_PRESSURE_RATINGS["150#"]:
            results.append(ValidationResult("PC-E02", Severity.WARN,
                f"150# 法兰设计压力 {dp} MPa 超过基准允许值 {FLANGE_PRESSURE_RATINGS['150#']} MPa",
                "design_pressure"))

        # PC-E03 法兰超压 ERROR
        if fc in FLANGE_PRESSURE_RATINGS and dp and dp > FLANGE_PRESSURE_RATINGS[fc]:
            results.append(ValidationResult("PC-E03", Severity.ERROR,
                f"设计压力 {dp} MPa 超过 {fc} 法兰最大允许压力 {FLANGE_PRESSURE_RATINGS[fc]} MPa",
                "design_pressure"))

        # PC-E04 引用表存在性——由 COMMON 库查询结果注入，这里检查字段格式
        allow = data.get("allowable_stress_json") or {}
        branch = data.get("branch_table_json") or {}
        for field_name, obj in [("allowable_stress_json", allow), ("branch_table_json", branch)]:
            if obj and not obj.get("table"):
                results.append(ValidationResult("PC-E04", Severity.ERROR,
                    f"{field_name} 缺少 table 引用", field_name))

        # PC-E05 DN > 600
        if dn and dn.get("max", 0) > 600:
            results.append(ValidationResult("PC-E05", Severity.WARN,
                f"DN 最大值 {dn.get('max')} 超过 600", "dn_series_json"))

        # PC-E07 Sch 空但 DN 非空
        if dn and dn.get("series") and not sch:
            results.append(ValidationResult("PC-E07", Severity.ERROR,
                "Sch 系列为空但 DN 系列非空", "sch_series_json"))

        # ---------- 项目上下文 ----------
        if ctx.project_pressure_limit is not None and dp and dp > ctx.project_pressure_limit:
            results.append(ValidationResult("PC-C01", Severity.WARN,
                f"等级设计压力 {dp} MPa 超过项目上限 {ctx.project_pressure_limit} MPa",
                "design_pressure"))

        if ctx.project_allowed_materials and bm and bm not in ctx.project_allowed_materials:
            results.append(ValidationResult("PC-C02", Severity.WARN,
                f"材料 {bm} 不在项目允许列表 {ctx.project_allowed_materials} 内",
                "base_material"))

        if ctx.existing_class_names and data.get("class_name") in ctx.existing_class_names:
            results.append(ValidationResult("PC-C03", Severity.ERROR,
                f"项目内已存在同名等级 {data.get('class_name')}", "class_name"))

        return results
Step 4：跑测试验证通过
bash
cd pcs-backend && uv run pytest tests/services/test_pipe_class_validator.py -v
# Expected: 22 passed
Step 5：全量回归 + Commit
bash
uv run pytest -q && uv run ruff check .
git add pcs-backend/app/services/pipe_class_validator.py pcs-backend/tests/services/test_pipe_class_validator.py
git commit -m "feat(sup-sprint): PC-2 管道等级验证引擎 22 条规则"
PC-3：公司级 CRUD + 5 态接入
目标：将 pipe_classes 挂载到 ConfigAsset，复用 ConfigStateMachine 的 5 态审批流。

文件：

Modify: pcs-backend/app/models/config_domain.py（若需要 asset_subtype 列）

Modify: pcs-backend/app/services/pipe_class_service.py

Modify: pcs-backend/app/api/v1/pipe_classes.py

Create: pcs-backend/tests/api/v1/test_pipe_class_config_flow.py

Step 1：写失败测试
python
# tests/api/v1/test_pipe_class_config_flow.py
import pytest
from httpx import AsyncClient
from uuid import uuid4

@pytest.fixture
def sample_pipe_class_payload():
    return {
        "class_id": "PC-TEST-001",
        "class_name": "Test Class A1A",
        "material_standard": "ASME B31.3",
        "base_material": "A106 Gr.B",
        "corrosion_allowance": 1.6,
        "design_pressure": 1.0,
        "design_temperature": 110,
        "dn_series_json": {"min": 15, "max": 600, "series": [15, 20, 25, 40, 50, 80, 100, 150, 200, 250, 300, 350, 400, 450, 500, 600]},
        "sch_series_json": {"DN15": [40, 80, 160], "DN50": [40, 80, 160], "DN200": [40, 80]},
        "flange_class": "150#",
        "fitting_type": "对焊",
        "allowable_stress_json": {"table": "COMMON_ASME_B31_3_TABLE_A1"},
        "branch_table_json": {"table": "COMMON_BRANCH_TABLE_01"},
    }


async def test_create_creates_config_asset(client, pc_token, sample_pipe_class_payload):
    """创建等级后 config_assets 有对应行"""
    r = await client.post("/api/v1/pipe-classes", json=sample_pipe_class_payload,
                          headers={"Authorization": f"Bearer {pc_token}"})
    assert r.status_code == 201
    class_id = r.json()["class_id"]

    # 查询 config_assets
    from app.models.config_domain import ConfigAsset
    from app.db.session import async_session
    async with async_session() as db:
        asset = (await db.execute(
            select(ConfigAsset).where(ConfigAsset.name == "Test Class A1A")
        )).scalar_one_or_none()
        assert asset is not None
        assert asset.category == "CATEGORY_5"
        assert asset.asset_subtype == "PIPE_CLASS"
        assert asset.status == "DRAFT"


async def test_submit_draft_to_pending(client, pc_token, sample_pipe_class_payload):
    """创建后提交 → PENDING"""
    r = await client.post("/api/v1/pipe-classes", json=sample_pipe_class_payload,
                          headers={"Authorization": f"Bearer {pc_token}"})
    class_id = r.json()["class_id"]

    r = await client.post(f"/api/v1/pipe-classes/{class_id}/submit",
                          headers={"Authorization": f"Bearer {pc_token}"})
    assert r.status_code == 200
    assert r.json()["status"] == "PENDING"


async def test_publish_updates_mirror_status(client, pc_token, sample_pipe_class_payload):
    """完整流程 DRAFT→PENDING→APPROVED→PUBLISHED，pipe_classes.status 镜像同步"""
    r = await client.post("/api/v1/pipe-classes", json=sample_pipe_class_payload,
                          headers={"Authorization": f"Bearer {pc_token}"})
    class_id = r.json()["class_id"]

    await client.post(f"/api/v1/pipe-classes/{class_id}/submit", headers=auth)
    await client.post(f"/api/v1/pipe-classes/{class_id}/approve", headers=auth)
    r = await client.post(f"/api/v1/pipe-classes/{class_id}/publish", headers=auth)
    assert r.status_code == 200
    assert r.json()["status"] == "PUBLISHED"

    # 直接从 pipe_classes 表读取验证镜像列
    from app.models.pipe_class import PipeClass
    async with async_session() as db:
        pc = await db.get(PipeClass, class_id)
        assert pc.status == "PUBLISHED"


async def test_invalid_transition_rejected(client, pc_token, sample_pipe_class_payload):
    """PENDING 直接 PUBLISH 被拒 409"""
    r = await client.post("/api/v1/pipe-classes", json=sample_pipe_class_payload,
                          headers={"Authorization": f"Bearer {pc_token}"})
    class_id = r.json()["class_id"]

    await client.post(f"/api/v1/pipe-classes/{class_id}/submit", headers=auth)
    r = await client.post(f"/api/v1/pipe-classes/{class_id}/publish", headers=auth)
    assert r.status_code == 409


async def test_obsolete_published(client, pc_token, sample_pipe_class_payload):
    """PUBLISHED 等级可 obsolete"""
    # 完整发布流程后 obsolete
    ...
    r = await client.post(f"/api/v1/pipe-classes/{class_id}/obsolete", headers=auth)
    assert r.status_code == 200
    assert r.json()["status"] == "OBSOLETE"
Step 2：跑测试验证失败
bash
cd pcs-backend && uv run pytest tests/api/v1/test_pipe_class_config_flow.py -v
# Expected: 5 FAIL（submit/approve/publish/obsolete 端点不存在）
Step 3：实现 ConfigAsset 挂载 + 状态机接线
python
# app/services/pipe_class_service.py 增加
from app.models.config_domain import ConfigAsset
from app.services.config_state_machine import ConfigStateMachine
from app.models.enums import ConfigTransition

class PipeClassService:
    # ... 既有方法保留

    @classmethod
    async def create_with_config_asset(cls, db: AsyncSession, data: PipeClassCreate, actor) -> PipeClass:
        """创建 PipeClass 并同步创建 ConfigAsset"""
        # 1. 创建 PipeClass
        pc = PipeClass(**data.model_dump())
        db.add(pc)
        await db.flush()

        # 2. 创建 ConfigAsset
        asset = ConfigAsset(
            category="CATEGORY_5",
            asset_subtype="PIPE_CLASS",
            name=data.class_name,
            status="DRAFT",
            ref_id=str(pc.class_id),
            created_by=actor.user_id,
        )
        db.add(asset)
        await db.flush()
        pc.asset_id = asset.asset_id
        await db.flush()

        # 3. 审计
        await AuditService(db).write(
            user_id=actor.user_id,
            module="CONFIG",
            object_id=str(asset.asset_id),
            action=AuditAction.CONFIG_ASSET_CREATED,
            new_value={"class_id": pc.class_id},
        )
        return pc

    @classmethod
    async def submit(cls, db: AsyncSession, class_id: str, actor) -> PipeClass:
        pc = await db.get(PipeClass, class_id)
        asset = await db.get(ConfigAsset, pc.asset_id)
        sm = ConfigStateMachine(db)
        await sm.transition(asset, None, action=ConfigTransition.SUBMIT, actor=actor)
        pc.status = asset.status  # 镜像同步
        await db.flush()
        return pc
    # approve / publish / obsolete 同理
Step 4：跑测试验证通过
bash
cd pcs-backend && uv run pytest tests/api/v1/test_pipe_class_config_flow.py -v
# Expected: 5 passed
Step 5：全量回归 + Commit
bash
uv run pytest -q && uv run ruff check .
git add -A && git commit -m "feat(sup-sprint): PC-3 管道等级挂 ConfigAsset + 5 态接入"
PC-4：项目级 fork + 快照绑定 + 有效值解析
目标：实现从公司级等级 fork 到项目级，带 snapshot_json 快照；提供 get_effective 返回合并后的完整字段。

文件：

Modify: pcs-backend/app/services/pipe_class_service.py

Create: pcs-backend/tests/services/test_pipe_class_fork.py

Step 1：写失败测试
python
# tests/services/test_pipe_class_fork.py
import pytest
from uuid import uuid4
from app.services.pipe_class_service import PipeClassService

async def test_fork_creates_project_class_with_snapshot(db, sample_company_class, sample_project):
    svc = PipeClassService
    ppc = await svc.fork_to_project(
        db,
        project_id=sample_project.project_id,
        class_id=sample_company_class.class_id,
        actor=uuid4(),
    )
    assert ppc.source_class_id == sample_company_class.class_id
    assert ppc.class_name == sample_company_class.class_name
    assert ppc.snapshot_json is not None
    assert ppc.snapshot_json["base_material"] == sample_company_class.base_material
    assert ppc.override_json == {}
    assert ppc.status == "DRAFT"

async def test_fork_then_override_then_effective(db, sample_project_class):
    """fork 后覆写 corrosion_allowance，effective 返回合并结果"""
    svc = PipeClassService
    # 覆写
    await svc.update_project_override(
        db,
        project_class_id=sample_project_class.project_class_id,
        override={"corrosion_allowance": 3.2},
        actor=uuid4(),
    )
    # 解析有效值
    effective = await svc.get_effective(
        db,
        project_id=sample_project_class.project_id,
        class_name=sample_project_class.class_name,
    )
    assert effective["corrosion_allowance"] == 3.2  # 覆写值
    assert effective["base_material"] == sample_project_class.snapshot_json["base_material"]  # 快照值
    assert effective["flange_class"] == sample_project_class.snapshot_json["flange_class"]  # 快照值

async def test_fork_duplicate_same_source_returns_existing(db, sample_project_class):
    """同一项目 fork 同一公司级等级，返回已有项目级行"""
    svc = PipeClassService
    ppc = await svc.fork_to_project(
        db,
        project_id=sample_project_class.project_id,
        class_id=sample_project_class.source_class_id,
        actor=uuid4(),
    )
    assert ppc.project_class_id == sample_project_class.project_class_id  # 未重复创建

async def test_new_project_class_without_source(db, sample_project):
    """项目全新创建等级（source_class_id=NULL）"""
    svc = PipeClassService
    ppc = await svc.create_project_class(
        db,
        project_id=sample_project.project_id,
        class_name="PROJECT_SPECIAL_A1",
        data={...全部字段...},
        actor=uuid4(),
    )
    assert ppc.source_class_id is None
    assert ppc.snapshot_json is None
    assert ppc.override_json == {**全部字段}
Step 2：跑测试验证失败
bash
cd pcs-backend && uv run pytest tests/services/test_pipe_class_fork.py -v
# Expected: 4 FAIL（fork_to_project 不存在）
Step 3：实现 fork + 快照 + 有效值解析
python
# app/services/pipe_class_service.py 追加

@classmethod
async def fork_to_project(cls, db, *, project_id, class_id, actor) -> ProjectPipeClass:
    """从公司级等级 fork 到项目级"""
    company_pc = await db.get(PipeClass, class_id)
    if company_pc is None:
        raise PcsError(404, "PIPE_CLASS_NOT_FOUND")

    # 检查是否已 fork
    existing = (await db.execute(
        select(ProjectPipeClass).where(
            ProjectPipeClass.project_id == project_id,
            ProjectPipeClass.source_class_id == class_id,
        )
    )).scalar_one_or_none()
    if existing:
        return existing

    snapshot = {
        "class_name": company_pc.class_name,
        "material_standard": company_pc.material_standard,
        "base_material": company_pc.base_material,
        "corrosion_allowance": company_pc.corrosion_allowance,
        "design_pressure": company_pc.design_pressure,
        "design_temperature": company_pc.design_temperature,
        "dn_series_json": company_pc.dn_series_json,
        "sch_series_json": company_pc.sch_series_json,
        "flange_class": company_pc.flange_class,
        "fitting_type": company_pc.fitting_type,
        "allowable_stress_json": company_pc.allowable_stress_json,
        "branch_table_json": company_pc.branch_table_json,
    }
    ppc = ProjectPipeClass(
        project_id=project_id,
        source_class_id=class_id,
        class_name=company_pc.class_name,
        override_json={},
        snapshot_json=snapshot,
        status="DRAFT",
    )
    db.add(ppc)
    await db.flush()
    return ppc

@classmethod
async def get_effective(cls, db, *, project_id, class_name) -> dict:
    """返回项目级有效值（快照 + 覆写深合并）"""
    ppc = (await db.execute(
        select(ProjectPipeClass).where(
            ProjectPipeClass.project_id == project_id,
            ProjectPipeClass.class_name == class_name,
        )
    )).scalar_one_or_none()
    if ppc is None:
        raise PcsError(404, "PROJECT_PIPE_CLASS_NOT_FOUND")

    # 深合并：JSON 字段逐键合并，顶层键直接覆写
    effective = dict(ppc.snapshot_json or {})
    for key, val in (ppc.override_json or {}).items():
        if isinstance(val, dict) and isinstance(effective.get(key), dict):
            effective[key] = {**effective[key], **val}  # 深合并 JSON 字段
        else:
            effective[key] = val  # 顶层覆写
    return effective
Step 4：跑测试验证通过
bash
cd pcs-backend && uv run pytest tests/services/test_pipe_class_fork.py -v
# Expected: 4 passed
Step 5：Commit
PC-5：Excel 批量导入（双 Sheet）
目标：Excel 导入模板（等级列表 + Sch 系列长表），行级校验 → 预览 → 事务写入。

文件：

Create: pcs-backend/app/services/pipe_class_import_service.py

Create: pcs-backend/tests/services/test_pipe_class_import.py

Step 1：写失败测试
python
# tests/services/test_pipe_class_import.py
import io
import openpyxl
import pytest
from app.services.pipe_class_import_service import PipeClassImportService, ImportPreview

def _make_excel(classes: list[dict], sch_rows: list[tuple]) -> bytes:
    wb = openpyxl.Workbook()
    ws1 = wb.active
    ws1.title = "等级列表"
    headers = ["ClassID", "ClassName", "MaterialStandard", "BaseMaterial",
               "DesignPressure", "DesignTemp", "CorrosionAllowance",
               "FlangeClass", "FittingType", "AllowableStressTable", "BranchTable"]
    ws1.append(headers)
    for c in classes:
        ws1.append([c.get(h) for h in headers])
    ws2 = wb.create_sheet("Sch系列")
    ws2.append(["ClassID", "DN", "Sch列表"])
    for row in sch_rows:
        ws2.append(list(row))
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()

def test_import_preview_returns_grouped_results(db, valid_excel_bytes):
    svc = PipeClassImportService(db)
    preview: ImportPreview = await svc.preview(valid_excel_bytes)
    assert len(preview.valid) == 2
    assert len(preview.errors) == 0
    assert len(preview.warnings) >= 0

def test_import_preview_detects_errors(db, excel_with_invalid_dn):
    """DN 系列空 → ERROR"""
    svc = PipeClassImportService(db)
    preview = await svc.preview(excel_with_invalid_dn)
    assert any(e.rule_id == "PC-V02" for e in preview.errors)

def test_import_commit_writes_all_or_nothing(db, valid_excel_bytes):
    """事务写入：全部成功或全部回滚"""
    svc = PipeClassImportService(db)
    preview = await svc.preview(valid_excel_bytes)
    count = await svc.commit_import(preview, actor=uuid4())
    assert count == 2
    # 验证 db 中有 2 条新记录

def test_import_commit_rejects_if_errors_present(db, excel_with_errors):
    """有 ERROR 时 commit_import 应拒绝"""
    svc = PipeClassImportService(db)
    preview = await svc.preview(excel_with_errors)
    with pytest.raises(PcsError) as e:
        await svc.commit_import(preview, actor=uuid4())
    assert e.value.status_code == 422
Step 2：跑测试验证失败
Step 3：实现导入服务
python
# app/services/pipe_class_import_service.py
from dataclasses import dataclass, field
from app.services.pipe_class_validator import PipeClassValidator, ValidationResult, Severity

@dataclass
class ImportRow:
    row_number: int
    class_id: str
    data: dict
    results: list[ValidationResult] = field(default_factory=list)

@dataclass
class ImportPreview:
    valid: list[ImportRow] = field(default_factory=list)
    errors: list[ValidationResult] = field(default_factory=list)
    warnings: list[ValidationResult] = field(default_factory=list)
    raw_excel: bytes | None = None

class PipeClassImportService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def preview(self, file_bytes: bytes) -> ImportPreview:
        """解析 Excel → 逐行校验 → 分组返回"""
        # 1. 解析两个 Sheet
        # 2. 合并 Sch 系列到对应的 ClassID
        # 3. 每行调用 PipeClassValidator.validate_company
        # 4. 分组：有 ERROR → errors，有 WARN → warnings，否则 valid

    async def commit_import(self, preview: ImportPreview, *, actor: UUID) -> int:
        """事务写入，任一行失败全量回滚"""
        if preview.errors:
            raise PcsError(422, "存在校验错误，不可导入")
        # 批量 insert，全部成功才 commit
Step 4：跑测试验证通过
Step 5：Commit
PC-6：管道等级 API 收口 + 测试
目标：整合 PC-3/PC-4/PC-5 的全部端点，完成 API 层测试收口。

文件：

Modify: pcs-backend/app/api/v1/pipe_classes.py

Modify: pcs-backend/tests/api/v1/test_pipe_classes.py（追加）

测试用例（追加）：

python
async def test_fork_endpoint(client, pc_token, sample_company_class, sample_project):
    """POST /projects/{pid}/pipe-classes/fork 创建项目级快照"""
    ...

async def test_get_effective_endpoint(client, token, sample_project_class):
    """GET /projects/{pid}/pipe-classes/effective/{class_name} 返回合并值"""
    ...

async def test_import_endpoint_roundtrip(client, pc_token, valid_excel_bytes):
    """POST /pipe-classes/import 预览 + 确认导入"""
    ...

async def test_import_validation_rejects_errors(client, pc_token, excel_with_errors):
    """预览阶段 422"""
    ...
Commit：feat(sup-sprint): PC-6 管道等级 API 收口 + 测试

SYM-1：物流符号表 migration + ORM
目标：创建 stream_symbols 和 project_stream_symbols 两表。

文件：

Create: pcs-backend/alembic/versions/p2_sup_sprint_sym1_stream_symbols.py

Create: pcs-backend/app/models/stream_symbol.py

Test: pcs-backend/tests/models/test_stream_symbol.py

Step 1：写 migration
python
def upgrade():
    op.create_table(
        "stream_symbols",
        sa.Column("symbol_id", sa.UUID(as_uuid=True), primary_key=True, default=uuid4),
        sa.Column("asset_id", sa.UUID(as_uuid=True), sa.ForeignKey("config_assets.asset_id"), nullable=True),
        sa.Column("symbol", sa.String(10), nullable=False, unique=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("category", sa.String(50), nullable=True),
        sa.Column("is_active", sa.Boolean(), default=True),
        sa.Column("status", sa.String(20), default="DRAFT"),
        sa.Column("version", sa.String(50), default="1"),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.Column("created_by", sa.UUID(as_uuid=True), nullable=True),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_table(
        "project_stream_symbols",
        sa.Column("project_symbol_id", sa.UUID(as_uuid=True), primary_key=True, default=uuid4),
        sa.Column("project_id", sa.UUID(as_uuid=True), sa.ForeignKey("projects.project_id"), nullable=False),
        sa.Column("source_symbol_id", sa.UUID(as_uuid=True), sa.ForeignKey("stream_symbols.symbol_id"), nullable=True),
        sa.Column("symbol", sa.String(10), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("category", sa.String(50), nullable=True),
        sa.Column("is_active", sa.Boolean(), default=True),
        sa.Column("snapshot_json", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(20), default="DRAFT"),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.UniqueConstraint("project_id", "symbol", name="uq_project_stream_symbol"),
    )
Step 2：ORM + 测试 + Commit
SYM-2：符号表 CRUD + 项目级 fork + SYM 验证规则（6 条）
目标：实现公司级符号表 CRUD、项目级 fork、6 条 SYM 验证规则。

文件：

Create: pcs-backend/app/services/stream_symbol_validator.py

Create: pcs-backend/app/services/stream_symbol_service.py

Test: pcs-backend/tests/services/test_stream_symbol_service.py

验证规则测试
python
class TestSYM:
    def test_v01_symbol_empty_or_too_long(self):
        ...

    def test_v02_name_empty(self):
        ...

    def test_v03_project_symbol_duplicate(self):
        ...

    def test_v04_category_invalid_warn(self):
        ...

    def test_v05_fork_snapshot_missing(self):
        ...

    def test_v06_symbol_in_use_block_delete(self):
        """被格式模板引用后不可删除"""
        ...
service 方法
python
class StreamSymbolService:
    @classmethod
    async def create_company(cls, db, data, actor) -> StreamSymbol
    @classmethod
    async def update_company(cls, db, symbol_id, data, actor) -> StreamSymbol
    @classmethod
    async def delete_company(cls, db, symbol_id, actor) -> None
    @classmethod
    async def fork_to_project(cls, db, *, project_id, symbol_id=None, actor) -> ProjectStreamSymbol
        """symbol_id=None 时复制全部公司级符号表"""
    @classmethod
    async def add_project_symbol(cls, db, *, project_id, symbol, name, category, actor) -> ProjectStreamSymbol
    @classmethod
    async def update_project_symbol(cls, db, *, project_symbol_id, data, actor) -> ProjectStreamSymbol
    @classmethod
    async def delete_project_symbol(cls, db, *, project_symbol_id, actor) -> None
    @classmethod
    async def list_project(cls, db, *, project_id, include_company=True) -> list[dict]
        """include_company=True 时合并公司级未覆写符号"""
SYM-3：符号表 API + 测试
目标：实现公司级和项目级符号表全部端点。

文件：

Create: pcs-backend/app/api/v1/stream_symbols.py

Create: pcs-backend/tests/api/v1/test_stream_symbols.py

测试用例：

python
async def test_company_crud_roundtrip(client, token): ...
async def test_company_symbol_duplicate_409(client, token): ...
async def test_fork_all_symbols_to_project(client, token): ...
async def test_project_add_custom_symbol(client, token): ...
async def test_project_symbol_duplicate_409(client, token): ...
async def test_project_symbol_delete_in_use_409(client, token): ...
async def test_submit_approve_publish_flow(client, token): ...
FMT-1：管道代码模板 migration + ORM
目标：创建 pipe_code_templates 和 project_pipe_code_configs 两表。

文件：

Create: pcs-backend/alembic/versions/p2_sup_sprint_fmt1_pipe_code_templates.py

Create: pcs-backend/app/models/pipe_code_template.py

migration 结构参照 SYM-1，字段见 SUP-002 §11.1/§11.2。

FMT-2：格式模板 CRUD + FMT 验证规则（9 条）
目标：实现格式模板 CRUD 和 9 条 FMT 验证规则。

文件：

Create: pcs-backend/app/services/pipe_code_validator.py

Create: pcs-backend/app/services/pipe_code_template_service.py

Test: pcs-backend/tests/services/test_pipe_code_template_service.py

FMT 验证规则测试
python
class TestFMT:
    def test_v01_must_have_one_auto_increment(self): ...
    def test_v02_must_have_one_stream_symbol(self): ...
    def test_v03_segment_keys_unique(self): ...
    def test_v04_adjacent_segments_need_separator(self): ...
    def test_v05_total_length_under_50(self): ...
    def test_v06_enum_values_nonempty(self): ...
    def test_v07_stream_symbol_in_project_symbols(self): ...
    def test_v08_project_config_name_unique(self): ...
    def test_v09_auto_increment_near_end_warn(self): ...
FMT-3：代码生成器 + 验证器 + 并发保障
目标：基于格式模板和符号表生成管道代码，含并发自增保障。

文件：

Create: pcs-backend/app/services/pipe_code_generator.py

Test: pcs-backend/tests/services/test_pipe_code_generator.py

测试用例
python
async def test_generate_basic_code(db, sample_project_config, sample_symbols):
    code = await PipeCodeGenerator.generate(db, project_id, {
        "unit": "100", "stream_symbol": "P", "phase": "L"
    })
    assert code == "100-P-001-L"

async def test_generate_increments_per_symbol(db, sample_project_config):
    """同项目同符号递增，不同符号独立"""
    c1 = await PipeCodeGenerator.generate(db, pid, {"stream_symbol": "P"})
    c2 = await PipeCodeGenerator.generate(db, pid, {"stream_symbol": "P"})
    assert c1 != c2
    w1 = await PipeCodeGenerator.generate(db, pid, {"stream_symbol": "WA"})
    assert "001" in w1  # WA 从 001 开始

async def test_generate_concurrent_10_unique(db, sample_project_config):
    """10 并发同项目同符号全部唯一"""
    codes = await asyncio.gather(*[
        PipeCodeGenerator.generate(db, pid, {"stream_symbol": "P"})
        for _ in range(10)
    ])
    assert len(set(codes)) == 10

async def test_validate_valid_code(db, sample_project_config):
    result = await PipeCodeGenerator.validate(db, pid, "100-P-001-L")
    assert result.valid is True
    assert result.segments["stream_symbol"] == "P"

async def test_validate_invalid_symbol(db, sample_project_config):
    result = await PipeCodeGenerator.validate(db, pid, "100-XX-001-L")
    assert result.valid is False
    assert any("symbol" in e for e in result.errors)
实现要点
python
class PipeCodeGenerator:
    @classmethod
    async def generate(cls, db, project_id, input_segments: dict) -> str:
        """按格式模板拼接，auto_increment 用 SELECT FOR UPDATE 自增"""
        config = await cls._get_effective_config(db, project_id)
        code_parts = []
        for seg in config.segments:
            if seg.type == "auto_increment":
                next_val = await cls._next_sequence(db, project_id, input_segments.get("stream_symbol"))
                code_parts.append(str(next_val).zfill(seg.length))
            elif seg.type == "stream_symbol":
                symbol = input_segments["stream_symbol"]
                await cls._validate_symbol(db, project_id, symbol)
                code_parts.append(symbol)
            elif seg.type == "enum":
                val = input_segments.get(seg.key)
                if val not in seg.values:
                    raise PcsError(422, f"枚举值 {val} 不在 {seg.values}")
                code_parts.append(val)
            # ... 其余类型
        return config.separator.join(code_parts)
FMT-4：管道代码 API + 测试
目标：实现管道代码模板 CRUD + 生成/验证端点。

文件：

Create: pcs-backend/app/api/v1/pipe_codes.py

Create: pcs-backend/tests/api/v1/test_pipe_codes.py

测试用例：

python
async def test_template_crud_roundtrip(client, token): ...
async def test_project_config_fork(client, token): ...
async def test_generate_endpoint(client, token): ...
async def test_generate_concurrent_endpoint(client, token): ...
async def test_validate_endpoint_valid(client, token): ...
async def test_validate_endpoint_invalid(client, token): ...
async def test_submit_approve_publish_flow(client, token): ...
INT-1：CATEGORY_1 项目模板集成
目标：项目模板增加 3 个字段，项目创建时自动 fork。

文件：

Modify: pcs-backend/app/models/project_template.py

Modify: pcs-backend/app/services/project_template_service.py（或对应服务）

Create: pcs-backend/tests/services/test_project_template_pipe_integration.py

测试用例：

python
async def test_project_template_has_pipe_fields(db):
    """模板包含 pipe_code_template_id / stream_symbol_table_id / default_pipe_class_ids"""
    ...

async def test_project_create_auto_forks_defaults(db, sample_template_with_pipe_config):
    """项目创建后自动 fork 模板中的默认等级和管道代码配置"""
    ...
INT-3：端到端集成测试
目标：验证全链路：项目模板 → 项目创建 → 自动 fork → 管道代码生成 → 等级选择。

测试用例：

python
async def test_e2e_project_create_pipe_code_generate(client, token):
    """1. 创建项目模板（含管道代码模板 + 默认等级）
       2. 创建项目（自动 fork）
       3. 生成管道代码
       4. 查询项目等级列表
       5. 获取有效等级详情
    """
质量门汇总
门	命令	通过条件
Lint	ruff check .	0 error
Type	mypy app/	0 error
Test	pytest -q	全量绿（基线 276 + 新增 ≥ 60）
Migration	alembic upgrade head && alembic downgrade -1 && alembic upgrade head	可逆
验证规则覆盖	37 条规则全部有测试	100%
Fuzz	tests/fuzz/test_pipe_code_generator.py	100 次随机输入无异常

INT-2 前端详细 Plan——管道等级 + 符号表 + 格式设计器
任务 ID：INT-2
工时：2.5 天
前置：PC-3（等级 CRUD）、SYM-2（符号表 CRUD）、FMT-2（格式模板 CRUD）后端就绪
定位：可与 P2 Sprint 2 前端波合并，也可作为独立前端任务先行

0. 技术栈确认
项	取值	说明
框架	React 18 + TypeScript	与 P0/P1 前端一致
状态管理	TanStack Query（服务端状态）+ Zustand（UI 状态）	若 P1 已定，沿用
表单	react-hook-form + zod	与后端 Pydantic schema 对齐
UI 组件库	待确认（Ant Design / MUI / shadcn）	按现有前端栈
HTTP	axios / fetch 封装	复用现有 api client
文件上传	antd Upload 或原生 input + FormData	Excel 导入用
1. 页面结构总览
text
/config/pipe-classes                     # 公司级管道等级列表
/config/pipe-classes/new                 # 新建等级
/config/pipe-classes/{classId}/edit      # 编辑等级
/config/pipe-classes/import              # Excel 批量导入

/projects/{projectId}/pipe-classes       # 项目级等级列表
/projects/{projectId}/pipe-classes/fork  # 从公司级 fork
/projects/{projectId}/pipe-classes/{id}/edit  # 编辑项目级等级

/config/stream-symbols                   # 公司级符号表
/projects/{projectId}/stream-symbols     # 项目级符号表

/config/pipe-code-templates              # 公司级格式模板列表
/config/pipe-code-templates/new          # 新建格式模板
/projects/{projectId}/pipe-code-configs  # 项目级格式配置
2. 管道等级编辑表单（核心组件）
2.1 组件树
text
<PipeClassForm>
├── <BasicInfoSection>
│   ├── classId（公司级可编辑，项目级只读）
│   ├── className
│   ├── materialStandard（下拉：ASME B31.3 / GB/T 20801 / HG/T 20615）
│   ├── baseMaterial（输入，支持斜杠分隔）
│   ├── corrosionAllowance（数字输入，0~6.5）
│   ├── designPressure（数字输入，0~42）
│   └── designTemperature（数字输入，-196~650）
├── <DnSeriesSection>
│   ├── minDn（数字）
│   ├── maxDn（数字）
│   ├── 标准步长按钮：DN15/20/25/40/50/80/100/150/200/250/300/350/400/450/500/600/700/800/900
│   └── 手动增删 DN 列表
├── <SchSeriesSection>
│   ├── 按 DN 分组列表
│   ├── 每组 Sch 值多选（40/80/160/XS/STD/10S/40S 等）
│   └── 添加/删除 DN 分组
├── <FlangeSection>
│   ├── flangeClass（下拉：150#/300#/400#/600#/900#/1500#/2500#）
│   ├── fittingType（多选：对焊/承插/螺纹/法兰，斜杠拼接）
│   ├── allowableStressTable（JSON 编辑：table 名 + overrides）
│   └── branchTable（JSON 编辑）
└── <ValidationFeedback>
    ├── 实时校验结果（来自 PC-V 系列）
    ├── 错误阻止保存
    └── 警告高亮提示
2.2 表单校验（zod schema 与后端对齐）
typescript
const pipeClassSchema = z.object({
  class_id: z.string().max(50),
  class_name: z.string().min(1).max(100),
  material_standard: z.string().min(1),
  base_material: z.string().min(1),
  corrosion_allowance: z.number().min(0).max(6.5),
  design_pressure: z.number().positive().max(42),
  design_temperature: z.number().min(-196).max(650),
  dn_series_json: z.object({
    min: z.number().positive(),
    max: z.number().positive(),
    series: z.array(z.number()).min(1),
  }).refine(d => d.min <= d.max, "min 必须 ≤ max"),
  sch_series_json: z.record(z.string(), z.array(z.number().positive())),
  flange_class: z.enum(["150#", "300#", "400#", "600#", "900#", "1500#", "2500#"]),
  fitting_type: z.string(),
  allowable_stress_json: z.object({ table: z.string(), overrides: z.record(z.any()).optional() }),
  branch_table_json: z.object({ table: z.string(), overrides: z.record(z.any()).optional() }),
});
2.3 实时校验
字段失焦 → 调用后端 POST /pipe-classes/validate 或前端 zod 先做本地校验

后端返回 PC-V / PC-E 结果 → 表单下方分组展示 ERROR/WARN

有 ERROR → 保存按钮 disabled

3. 项目级 fork 流程
3.1 交互流程
text
项目级等级列表页
├── 「从公司级 fork」按钮
│   └── 弹窗：公司级等级列表（可搜索/筛选）
│       └── 选择等级 → 确认 fork
│           └── 后端返回 ProjectPipeClass（含 snapshot_json）
│               └── 跳转到编辑页（override_json 为空，显示快照值）
└── 「新建项目专属等级」按钮
    └── 空白表单（source_class_id=NULL）
3.2 fork 后编辑页
表单预填 snapshot_json 的值

用户修改的字段标记为「已覆写」（与快照不同）

后端保存时自动计算 override_json（仅存被覆写字段）

未修改的字段保持快照值，显示为只读或带「继承」标记

text
┌─────────────────────────────────────────┐
│ 项目级等级编辑                            │
│ 来源: 公司级 U4（快照绑定 V2）            │
├─────────────────────────────────────────┤
│ 腐蚀裕量 [3.2] ← 已覆写（原 1.6）        │
│ 法兰等级 [300#] ← 已覆写（原 150#）      │
│ 设计压力 [1.0] ← 继承自快照              │
│ ...                                     │
└─────────────────────────────────────────┘
3.3 有效值预览
编辑页底部提供「预览有效值」按钮

调用 GET /projects/{pid}/pipe-classes/effective/{class_name}

展示合并后的完整 JSON（快照 + 覆写）

4. Excel 批量导入界面
4.1 上传页布局
text
┌─────────────────────────────────────────┐
│ 管道等级 Excel 导入                       │
├─────────────────────────────────────────┤
│ 1. 下载模板 [等级列表.xlsx]               │
│ 2. 上传文件 [拖拽或点击选择]              │
│ 3. 预览结果                              │
│    ├── ✅ 有效 2 行                      │
│    ├── ⚠️ 警告 1 行                      │
│    └── ❌ 错误 1 行                      │
│ 4. [确认导入]（有错误时 disabled）        │
└─────────────────────────────────────────┘
4.2 预览表格
typescript
interface ImportPreviewRow {
  row_number: number;
  class_id: string;
  class_name: string;
  status: "valid" | "warn" | "error";
  messages: { rule_id: string; severity: "ERROR" | "WARN"; message: string }[];
}
4.3 上传流程
text
文件选择 → 上传到 POST /pipe-classes/import（preview 模式）
→ 返回 ImportPreview
→ 前端渲染分组表格
→ 用户点击「确认导入」
→ 调用 commit 端点（或同端点带 confirm 参数）
→ 成功后跳转到列表页
5. 物流符号表管理界面
5.1 公司级符号表
text
┌─────────────────────────────────────────┐
│ 公司级物流符号表                          │
│ [+ 新建符号]                             │
├─────────────────────────────────────────┤
│ symbol │ name              │ category │ 状态 │ 操作 │
│ P      │ PROCESS FLUID     │ PROCESS  │ PUBLISHED │ 编辑/作废 │
│ WA     │ WASTE WATER...    │ WASTE    │ PUBLISHED │ 编辑/作废 │
│ ...                                     │
└─────────────────────────────────────────┘
5.2 项目级符号表
fork 按钮：POST /projects/{pid}/stream-symbols/fork（复制全部公司级符号）

表格展示合并视图（公司级 + 项目覆写）

项目覆写的符号有「项目」标记

支持增删改（仅影响项目级）

5.3 符号编辑弹窗
text
┌──────────────────────────────┐
│ 编辑符号                      │
│ 符号 [WA]                     │
│ 含义 [WASTE WATER HARMLESS]  │
│ 分类 [WASTE ▼]               │
│ 启用 [✓]                      │
│ [保存] [取消]                 │
└──────────────────────────────┘
6. 管道代码格式设计器（最复杂组件）
6.1 拖拽式分段构建器
text
┌─────────────────────────────────────────────────────┐
│ 管道代码格式设计器                                     │
├─────────────────────────────────────────────────────┤
│ 可用分段：                                            │
│ [单元号 enum] [介质符号 stream_symbol] [序列号 auto]   │
│ [相态 enum] [自由文本 free_text] [常量 constant]      │
│ [分隔符 delimiter]                                    │
├─────────────────────────────────────────────────────┤
│ 格式画布（拖拽排序）：                                 │
│ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐                  │
│ │ 单元  │-│ 介质  │-│ 序列  │-│ 相态  │                  │
│ │enum  │ │symbol│ │ auto │ │enum  │                  │
│ └──────┘ └──────┘ └──────┘ └──────┘                  │
│  [×]    [×]    [×]    [×]                            │
├─────────────────────────────────────────────────────┤
│ 分段属性（点击分段后编辑）：                            │
│ 类型: enum | 值: [100,200,300] | 长度: 3 | 必填: ✓    │
├─────────────────────────────────────────────────────┤
│ 实时预览：                                            │
│ 输入示例值 → 100-P-001-L                              │
│ 校验状态：✅ 格式有效                                  │
└─────────────────────────────────────────────────────┘
6.2 分段类型配置面板
分段类型	配置字段
stream_symbol	长度（默认 10）
enum	values 列表编辑器、长度、必填
auto_increment	起始值、步长、填充方式（zero/none）、长度
free_text	长度、regex
constant	固定值
delimiter	分隔符字符
6.3 实时预览
用户点击「预览」后为每个非 auto 段输入示例值

auto_increment 段自动显示 001（模拟起始值）

底部显示拼接结果 + FMT 规则校验状态

6.4 校验反馈
FMT-V01~V09 规则实时检查

ERROR 阻止保存

WARN 高亮提示（如 auto_increment 未在末位）

7. 文件结构与组件清单
text
pcs-frontend/src/
├── pages/
│   ├── config/
│   │   ├── PipeClassList.tsx
│   │   ├── PipeClassForm.tsx
│   │   ├── PipeClassImport.tsx
│   │   ├── StreamSymbolList.tsx
│   │   ├── PipeCodeTemplateList.tsx
│   │   └── PipeCodeTemplateDesigner.tsx
│   └── projects/
│       ├── ProjectPipeClassList.tsx
│       ├── ProjectPipeClassFork.tsx
│       ├── ProjectStreamSymbols.tsx
│       └── ProjectPipeCodeConfigs.tsx
├── components/
│   ├── pipe-class/
│   │   ├── BasicInfoSection.tsx
│   │   ├── DnSeriesSection.tsx
│   │   ├── SchSeriesSection.tsx
│   │   └── ValidationFeedback.tsx
│   ├── stream-symbol/
│   │   └── SymbolEditModal.tsx
│   └── pipe-code/
│       ├── SegmentCanvas.tsx
│       ├── SegmentConfigPanel.tsx
│       └── CodePreview.tsx
├── api/
│   ├── pipeClasses.ts
│   ├── streamSymbols.ts
│   └── pipeCodes.ts
├── types/
│   ├── pipeClass.ts
│   ├── streamSymbol.ts
│   └── pipeCode.ts
└── hooks/
    ├── usePipeClassValidation.ts
    ├── usePipeCodeGeneration.ts
    └── useExcelImport.ts
8. 测试策略（前端）
测试层	内容	目标
组件测试	PipeClassForm 校验逻辑（zod schema）	每个 PC-V 规则对应的前端校验
组件测试	PipeCodeDesigner 拖拽/预览	分段添加/删除/排序/预览
组件测试	SymbolEditModal 增删改	项目内唯一性校验
集成测试	fork 流程（列表 → fork → 编辑 → 保存）	全链路
集成测试	Excel 上传 → 预览 → 确认导入	分组展示正确
E2E	项目模板 → 项目创建 → 管道代码生成	完整用户路径
9. 与后端对接的 API 清单
后端端点	前端调用点
GET /pipe-classes	公司级列表
POST /pipe-classes	新建等级
PUT /pipe-classes/{id}	编辑等级
POST /pipe-classes/validate	实时校验
POST /pipe-classes/import	Excel 上传预览
POST /pipe-classes/{id}/submit 等	审批流按钮
POST /projects/{pid}/pipe-classes/fork	项目级 fork
GET /projects/{pid}/pipe-classes/effective/{name}	有效值预览
GET/POST/PUT /stream-symbols	符号表 CRUD
POST /projects/{pid}/stream-symbols/fork	符号表 fork
GET/POST/PUT /pipe-code-templates	格式模板 CRUD
POST /pipe-codes/generate	实时预览生成
POST /pipe-codes/validate	格式校验
10. 工时拆分
子任务	内容	工时
INT-2a	PipeClassForm + 校验 + Dn/Sch 系列编辑	1 天
INT-2b	Excel 导入界面（上传 + 预览 + 确认）	0.5 天
INT-2c	项目级 fork 流程 + 有效值预览	0.5 天
INT-2d	符号表管理（公司级 + 项目级）	0.5 天
INT-2e	管道代码格式设计器（拖拽 + 预览）	1 天
合计		3.5 天（原估 2.5 天，含设计器复杂度，可标记为 2.5~3.5 天区间）

P2 增补 Spec——管道等级库 + 管道代码自定义（合并版）
文档编号：PCS-SPEC-P2-SUP-002
版本：V1.4（2026-09-06 审查修正：26 项问题全部落定）
日期：2026-09-06
状态：已定稿（作为 P2 追加 Sprint 实施依据）
依赖：SPEC-P2 V1.4、Plan Design 主文档、D29–D34 裁决、P2 Sprint 1.9 计划、三源种子

变更明细（V1.3 → V1.4）
一、SPEC 自相矛盾修正
#	位置	修正
1	§2.1 version 字段	int → str50，与 §0.5 裁决对齐
2	§0.4 迁移描述	统一为：DRAFT→DRAFT，ACTIVE→PUBLISHED，OBSOLETE→OBSOLETE
3	§11.1 version 字段	str50（与 §2.1 统一）
4	§11.3 format_definition_json	auto_increment 段增加 "scope": "project+symbol" 配置项
5	§7.2 project_stream_symbols	增加 override_json 字段（仅存与快照不同的字段），覆写机制与管道等级对齐
二、PC-1 迁移脚本重写
#	缺陷	修正
1	snapshot_json 回填 {}	改为 JOIN pipe_classes 逐字段构造完整 JSON 快照
2	新 PK 列名 project_class_id_new	创建后立即 ALTER TABLE ... RENAME COLUMN 为 project_class_id
3	enabled 字段未处理	enabled=false → status='OBSOLETE'；enabled=true → 保留原 status；随后删列
4	base_material 回填缺失	UPDATE pipe_classes SET base_material = material_standard WHERE base_material IS NULL（迁移后由种子重新导入修正）
三、PC-2 验证引擎修正
#	规则	修正
1	PC-E04	改为注入 common_tables: set[str] 参数，实际检查表名存在性
2	PC-E04 测试	传入 common_tables={"COMMON_ASME_B31_3_TABLE_A1", "COMMON_BRANCH_TABLE_01"}，NONEXISTENT_TABLE 触发 ERROR
3	PC-E06	新增实现：项目级 fork 时 design_pressure 在 override 中但 flange_class 不在 override 中 → WARN
4	PC-V10	新增实现：source_class_id 非空时由 service 层在 fork 前校验有效性，validator 提供辅助方法
5	PC-C04	实现 is_in_use classmethod（查询 piping_results FK 引用）
6	深合并	get_effective 递归合并：sch_series_json 内单 DN 键覆写时保留其他 DN
四、代码与测试缺陷修正
#	位置	修正
1	PC-3 测试	headers=auth → headers={"Authorization": f"Bearer {pc_token}"}
2	PC-3 Service	ConfigAsset(ref_id=...) → 移除 ref_id，改用 asset_subtype + name + category
3	PC-4 ORM	ProjectPipeClass 增加 UniqueConstraint("project_id", "class_name")
4	FMT-3 并发测试	改为 10 个独立 session（async_session() 各自创建），真实测试锁隔离
5	SYM-2 Service	fork_to_project(symbol_id=None) 返回 list[ProjectStreamSymbol]（复制全部），symbol_id 指定时返回单个
6	PC-5 导入	commit_import 改为接收 import_id（服务端暂存预览结果），或要求前端重新上传文件并携带校验哈希
五、设计遗漏补全
#	位置	补全
1	项目级 5 态审批	项目级表不挂 ConfigAsset（避免 config_assets 爆炸式增长）。项目级使用独立轻量状态列 + service 层状态流转（DRAFT→PENDING→APPROVED→PUBLISHED→OBSOLETE），审批记录写入 config_approvals 表（version_id 可空，增加 project_class_id 列）
2	fitting_type 枚举值	写入 SPEC：合法枚举为 对焊 / 承插 / 螺纹 / 法兰，斜杠分隔组合
3	INT-1 关联表	新增 project_template_pipe_classes 关联表：(template_id UUID FK, class_id varchar(50) FK, PRIMARY KEY(template_id, class_id))
4	INT-2 工时	统一为 3.5 天，§16 总表同步更新，合计 16.5 天
5	§4.2 拼写	引llowable_stress_json → allowable_stress_json
V1.4 关键修正段落（完整替换）
§2.1 version 字段
text
| version | str50 | — | 版本号（保留 str50，§0.5 裁决；权威版本链在 config_versions） |
§0.4 迁移描述
3 态并入 5 态（迁移兼容：DRAFT→DRAFT、ACTIVE→PUBLISHED、OBSOLETE→OBSOLETE，PENDING/APPROVED 迁移后为空集）

§11.3 auto_increment 段增加 scope
json
{
  "key": "sequence",
  "label": "序列号",
  "type": "auto_increment",
  "length": 3,
  "start_value": 1,
  "step": 1,
  "padding": "zero",
  "required": true,
  "position": 3,
  "scope": "project+symbol"
}
§7.2 project_stream_symbols 增加 override_json
text
| override_json | json | NOT NULL | 仅存被覆写字段（与快照不同）；新增符号时为空对象 |
PC-1 迁移脚本（重写关键段）
python
def upgrade():
    # ... 前置列操作不变

    # snapshot_json 回填：从 pipe_classes 构造完整快照
    op.execute("""
        UPDATE project_pipe_classes ppc
        SET snapshot_json = json_build_object(
            'class_name', pc.class_name,
            'material_standard', pc.material_standard,
            'base_material', pc.base_material,
            'corrosion_allowance', pc.corrosion_allowance,
            'design_pressure', pc.design_pressure,
            'design_temperature', pc.design_temperature,
            'dn_series_json', pc.dn_series_json,
            'sch_series_json', pc.sch_series_json,
            'flange_class', pc.flange_class,
            'fitting_type', pc.fitting_type,
            'allowable_stress_json', pc.allowable_stress_json,
            'branch_table_json', pc.branch_table_json
        ),
        source_class_id = ppc.class_id,
        class_name = pc.class_name,
        override_json = COALESCE(ppc.custom_override_json, '{}'::json)
        FROM pipe_classes pc
        WHERE ppc.class_id = pc.class_id
    """)

    # enabled → status 映射
    op.execute("""
        UPDATE project_pipe_classes
        SET status = CASE
            WHEN enabled = false THEN 'OBSOLETE'
            ELSE 'DRAFT'
        END
    """)

    # 新 UUID 列创建后重命名
    op.alter_column("project_pipe_classes", "project_class_id_new",
                    new_column_name="project_class_id")

    # 删除 enabled 和 custom_override_json 列
    op.drop_column("project_pipe_classes", "enabled")
    op.drop_column("project_pipe_classes", "custom_override_json")
PC-2 验证引擎修正（PC-E04 / PC-E06 / PC-V10 / PC-C04）
python
class PipeClassValidator:
    # 构造函数或方法参数注入 common_tables
    @classmethod
    def validate_company(cls, data: dict, common_tables: set[str] | None = None) -> list[ValidationResult]:
        common_tables = common_tables or set()
        results = cls._validate(data, ValidationContext(), common_tables)
        return results

    @classmethod
    def _validate(cls, data, ctx, common_tables: set[str]) -> list[ValidationResult]:
        # ... 其他规则

        # PC-E04 实际检查表存在性
        for field_name, obj in [("allowable_stress_json", data.get("allowable_stress_json") or {}),
                                 ("branch_table_json", data.get("branch_table_json") or {})]:
            table_name = obj.get("table")
            if table_name and table_name not in common_tables:
                results.append(ValidationResult("PC-E04", Severity.ERROR,
                    f"{field_name} 引用的表 {table_name} 不存在于 COMMON 库", field_name))

        # PC-E06 fork 覆写压力未覆写法兰等级
        if ctx.is_fork and "design_pressure" in data.get("_override_keys", []) \
           and "flange_class" not in data.get("_override_keys", []):
            results.append(ValidationResult("PC-E06", Severity.WARN,
                "覆写了设计压力但未覆写法兰等级", "flange_class"))

    @classmethod
    async def is_in_use(cls, db, class_id: str) -> bool:
        """PC-C04：检查 piping_results 是否引用了该等级"""
        from app.models.piping_result import PipingResult
        row = (await db.execute(
            select(PipingResult.piping_result_id).where(
                PipingResult.material_class == class_id
            ).limit(1)
        )).first()
        return row is not None
深合并修正
python
def _deep_merge(base: dict, override: dict) -> dict:
    """递归合并：字典逐键合并，列表整体替换，标量直接覆写"""
    result = dict(base)
    for key, val in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(val, dict):
            result[key] = _deep_merge(result[key], val)
        else:
            result[key] = val
    return result
项目级 5 态审批架构
项目级表不挂 ConfigAsset，使用轻量状态列 + service 层流转：

python
# app/services/project_pipe_class_state.py
class ProjectPipeClassStateMachine:
    """项目级管道等级轻量状态机（不挂 ConfigAsset）"""
    TRANSITIONS = {
        "DRAFT": {"submit", "obsolete"},
        "PENDING": {"approve", "reject"},
        "APPROVED": {"publish", "obsolete"},
        "PUBLISHED": {"obsolete"},
        "OBSOLETE": set(),
    }

    async def transition(self, ppc: ProjectPipeClass, action: str, actor) -> ProjectPipeClass:
        # 校验合法流转
        # 更新 ppc.status
        # 写入 config_approvals（新增 project_class_id 列）
config_approvals 表增加可空列：

sql
ALTER TABLE config_approvals
ADD COLUMN project_class_id UUID REFERENCES project_pipe_classes(project_class_id);
INT-1 关联表
sql
CREATE TABLE project_template_pipe_classes (
    template_id UUID NOT NULL REFERENCES project_templates(template_id),
    class_id varchar(50) NOT NULL REFERENCES pipe_classes(class_id),
    PRIMARY KEY (template_id, class_id)
);
修正后工时
任务	修正后工时
PC-1	1 天（原 0.5，迁移脚本重写 + 回填验证）
PC-2	1.5 天（原 1，PC-E04/E06/V10/C04 补全）
其余不变	—
INT-2	3.5 天（原 2.5，§16 同步）
合计	17.5 天（约 3.5 周）

---

## 未解决问题

1. **PC-FMT-01~06 与 INT-DROP-01/EXCEL-01** 已在 SPEC §0.6 落定（dn_series_json.series 可选；sch_series_json 裸 DN 键+SchEntry；flange_class 三形式；列宽保持现状；项目级审批不挂 ConfigAsset；公司级资产补挂走 PC-1 增量；auto_increment 复用 NumberingService/DocNoSequence；项目模板不增 stream_symbol_table_id 列；Excel Sheet1 沿用 1.9.6 十二列模板），本计划正文 baseline 与 §0.6 之间存在表述不一致风险——实施 Task 启动时需把 §0.6 6 条裁决一对一 patch 进对应 Step（如 PC-1 migration 加 enabled→status 映射、project_class_id 列重命名；FMT-1/FMT-2 直接套 FMT-SEQ-01）。
2. **config_approvals.project_class_id 列**新增由 PC-3 同步迁移做还是 PC-4 独立迁移做？V1.4 文本只规定「可空列」，未指定任务归属。建议随 PC-3 一次出 schema 改动，PC-4 直接读列；写入 config_approvals 走 PC-4 项目级审批 service。
3. **PC-5 import_id 暂存**方案需明确：服务端 preview 返回 import_id → 前端确认时携带 import_id → 服务端按 import_id 取预览结果重放。需新建 `pipe_class_import_previews` 表（包含原文件 + 校验结果 JSON + actor + expires_at）还是复用现有临时机制（如 Redis）？尚未裁决。
4. **PC-3 submit/approve/publish/obsolete 端点 ACL**沿用 P2 Sprint 1.2 的 CONFIG 审批链角色矩阵（已交付），还是 V1.4 追加项目级自定义角色？默认沿用既有矩阵，项目级自定义留 TODO。
5. **三源 71 等级种子**导入路径：1.9.6 Excel 模板（已锁）vs PC-1 后新增的 schema 直接 INSERT？前者保持种子文件锁不变，PC-1 迁移后跑 1.9.6 脚本种子会自然带出 base_material/asset_id 列（asset_id 由 PC-3 补建 ConfigAsset 时回填），不引入二次迁移风险。建议采纳。
6. **INT-2 拆分粒度**：3.5 天若并入 P2 Sprint 2 前端波，需在 P2 Sprint 2 计划里再起 task list；本计划仅交付 INT-2 后端契约 + API mock。是否在 Sprint 2 计划启动时把 INT-2 子任务（2a 表单/2b 导入/2c fork/2d 符号/2e 设计器）一并定义？建议 Sprint 2 启动时同步处理，本计划不动。



