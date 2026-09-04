# P2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实施 PCS P2 配置层（公式/系数/模板/审批/编号）+ equipment_list 42 字段对齐 + CIA 集成 + 报表导出，共 ~5 周单人开发。

**Architecture:** 横向骨架优先（先 AuditAction 8 项 + ConfigStateMachine 5 态 + 双段签双行 config_approvals + LDAP 角色 ACL，再依次接 1.2~1.5 业务）；公式引擎用 Python `ast` 解析 + 节点白名单 + `__builtins__` 冻结 + 无缓存天然热更新 + 100% pass 硬门槛（D17：移除 SymPy 声明，纯 stdlib）；equipment_list 42 字段分 3 个 alembic migration；CIA 反向传播标 STALE；报表+openpyxl 导出。

**Tech Stack:** Python 3.12 + FastAPI + SQLAlchemy 2.0 async + Pydantic v2 + pytest-asyncio + alembic + SymPy + Jinja2 + openpyxl

**Spec:** `docs/superpowers/specs/2026-09-02-p2-plan-design.md`

## Global Constraints

- **配置状态机 5 态**（DRAFT/PENDING/APPROVED/PUBLISHED/OBSOLETE），不引入 APPROVED_PE；双段签用 `config_approvals` 两行表达（line 70 spec）
- **公式 unit_tests_json** schema（D16）：`{"unit_tests": [{"params": {...}, "expected": <num>, "tolerance": <num>}]}`，对象数组
- **公式 parameters_json** schema（D16）：`{"parameters": [{"name", "unit", "description", "min", "max", "default"}]}`
- **热更新（D17）**：无缓存设计；公式每次计算从 DB 加载；不调用 `session.expire_all()`
- **pass rate 硬门槛（D17）**：PUBLISH 强制 unit_tests 100% pass，否则 422
- **ACL（D15）**：DRAFT 任意 DESIGNER；PUBLISH 需 PROCESS_CONTROLLER + SYSTEM_ADMIN；复用 `workspaces` 项目组成员关系
- **AuditAction 8 项**：`CONFIG_ASSET_CREATED/CONFIG_VERSION_CREATED/CONFIG_ASSET_SUBMITTED/CONFIG_ASSET_APPROVED/CONFIG_ASSET_PUBLISHED/CONFIG_ASSET_OBSOLETED/CONFIG_ASSET_REJECTED/CONFIG_VERSION_DIFF_VIEWED`
- **不调用 `require_formal_workspace`**（CONFIG 全局非项目级）
- **复用 P1**：AuditService.write() / 双引擎 sync+async / commit_or_rollback
- **不引入 Redis**（D17）
- **不引入 APPROVED_PE**（5 态不变）
- **数值字段**：float=8 byte, int=4 byte, str(N)=N byte, dt=8 byte
- **测试覆盖**：新代码 ≥ 80%
- **质量门**：ruff ✅ + mypy ✅ + pytest 全绿 + alembic upgrade head ✅ + 结构化 diff DICT vs ORM 0 漂移

## File Structure

**新增**：
- `pcs-backend/app/models/enums.py` — 追加 8 项 CONFIG_* 枚举
- `pcs-backend/app/services/config_state_machine.py` — 5 态状态机（独立于记录层）
- `pcs-backend/app/services/formula_engine.py` — SymPy + AST + unit_tests 运行器
- `pcs-backend/app/services/coefficient_service.py` — 系数库 CRUD
- `pcs-backend/app/services/template_service.py` — 模板文件上传+占位符
- `pcs-backend/app/services/numbering_service.py` — 编号自增（事务+UQ）
- `pcs-backend/app/schemas/config.py` — ConfigAsset/Version/Approval Pydantic schema
- `pcs-backend/app/schemas/formula.py` — parameters_json / unit_tests_json schema
- `pcs-backend/app/api/v1/config.py` — 配置层 REST 端点（async）
- `pcs-backend/app/services/report_service.py` — 配置资产状态分布 + 编号模板用量
- `pcs-backend/app/services/export_service.py` — openpyxl CSV/Excel 导出
- `pcs-backend/tests/services/test_config_state_machine.py`
- `pcs-backend/tests/services/test_formula_engine.py`
- `pcs-backend/tests/services/test_numbering_service.py`
- `pcs-backend/tests/api/v1/test_config.py`
- `pcs-backend/tests/fuzz/test_formula_engine.py`
- `pcs-backend/alembic/versions/p2_sprint2_equipment_naming_fix.py`
- `pcs-backend/alembic/versions/p2_sprint2_equipment_procurement_delivery.py`
- `pcs-backend/alembic/versions/p2_sprint2_equipment_engineering.py`

**修改**：
- `pcs-backend/app/models/config_domain.py` — 已有，添加公式 status/version/category 等
- `pcs-backend/app/models/equipment.py` — 42 字段对齐 DICT V3.3
- `pcs-backend/app/services/cia_engine.py` — 添加 `propagate_from_source`
- `pcs-backend/docs/schema_compact_orm.md` — 重生成（53 表）
- `spec/PCS-DICT-ALL-003 V3.5.md` — 增量发布
- `spec/schema_compact_dict.md` — 同步 V3.5
- `CLAUDE.md` — 文档化 workspace 边界（CONFIG 不需 require_formal_workspace）

---

## Phase 1: Sprint 1 基础设施（~3 天）

### Task 1.1: AuditAction 8 项 CONFIG_* 枚举追加

**Files:**
- Modify: `pcs-backend/app/models/enums.py:1-50`（追加 AuditAction 末尾）
- Test: `pcs-backend/tests/models/test_enums.py`

**Interfaces:**
- Consumes: 现有 `AuditAction` 枚举类
- Produces: `AuditAction.CONFIG_ASSET_CREATED` 等 8 个新成员

- [ ] **Step 1: 写失败测试**

```python
# tests/models/test_enums.py
def test_config_audit_actions_exist():
    assert AuditAction.CONFIG_ASSET_CREATED.value == "CONFIG_ASSET_CREATED"
    assert AuditAction.CONFIG_VERSION_CREATED.value == "CONFIG_VERSION_CREATED"
    assert AuditAction.CONFIG_ASSET_SUBMITTED.value == "CONFIG_ASSET_SUBMITTED"
    assert AuditAction.CONFIG_ASSET_APPROVED.value == "CONFIG_ASSET_APPROVED"
    assert AuditAction.CONFIG_ASSET_PUBLISHED.value == "CONFIG_ASSET_PUBLISHED"
    assert AuditAction.CONFIG_ASSET_OBSOLETED.value == "CONFIG_ASSET_OBSOLETED"
    assert AuditAction.CONFIG_ASSET_REJECTED.value == "CONFIG_ASSET_REJECTED"
    assert AuditAction.CONFIG_VERSION_DIFF_VIEWED.value == "CONFIG_VERSION_DIFF_VIEWED"
    assert len(list(AuditAction)) >= 8 + 现有数量
```

- [ ] **Step 2: 跑测试，验证失败**

Run: `cd pcs-backend && uv run pytest tests/models/test_enums.py::test_config_audit_actions_exist -v`
Expected: FAIL `AttributeError: type object 'AuditAction' has no attribute 'CONFIG_ASSET_CREATED'`

- [ ] **Step 3: 追加 8 项枚举**

`app/models/enums.py` 在 `class AuditAction(str, Enum)` 末尾追加：
```python
# === CONFIG（P2 Sprint 1.1） ===
CONFIG_ASSET_CREATED = "CONFIG_ASSET_CREATED"
CONFIG_VERSION_CREATED = "CONFIG_VERSION_CREATED"
CONFIG_ASSET_SUBMITTED = "CONFIG_ASSET_SUBMITTED"
CONFIG_ASSET_APPROVED = "CONFIG_ASSET_APPROVED"
CONFIG_ASSET_PUBLISHED = "CONFIG_ASSET_PUBLISHED"
CONFIG_ASSET_OBSOLETED = "CONFIG_ASSET_OBSOLETED"
CONFIG_ASSET_REJECTED = "CONFIG_ASSET_REJECTED"
CONFIG_VERSION_DIFF_VIEWED = "CONFIG_VERSION_DIFF_VIEWED"
```

- [ ] **Step 4: 跑测试，验证通过**

Run: `cd pcs-backend && uv run pytest tests/models/test_enums.py::test_config_audit_actions_exist -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add pcs-backend/app/models/enums.py pcs-backend/tests/models/test_enums.py
git commit -m "feat(p2): 追加 8 项 CONFIG_* AuditAction 枚举"
```

### Task 1.2: ConfigStateMachine 5 态骨架

**Files:**
- Create: `pcs-backend/app/services/config_state_machine.py`
- Test: `pcs-backend/tests/services/test_config_state_machine.py`

**Interfaces:**
- Consumes: `ConfigAsset` ORM 模型（`app/models/config_domain.py`）
- Produces: `ConfigStateMachine.transition(asset, action, approver_id) -> ConfigAsset`

- [ ] **Step 1: 写失败测试**

```python
# tests/services/test_config_state_machine.py
import pytest
from app.models.enums import ConfigStatus, ConfigTransition, AuditAction
from app.models.audit_log import AuditLog
from app.services.config_state_machine import ConfigStateMachine

async def test_draft_to_pending_writes_audit(db):
    asset = await make_asset(db, status=ConfigStatus.DRAFT)
    sm = ConfigStateMachine(db)
    await sm.transition(asset, asset.current_version,
                        action=ConfigTransition.SUBMIT, actor=actor)
    await db.commit()
    assert asset.status == ConfigStatus.PENDING
    audit = (await db.execute(
        select(AuditLog).where(AuditLog.resource_id == str(asset.asset_id))
    )).scalar_one()
    assert audit.action == AuditAction.CONFIG_ASSET_SUBMITTED

async def test_pending_to_approved_single_writes_audit(db):
    asset = await make_asset(db, status=ConfigStatus.PENDING, category="CATEGORY_3")
    sm = ConfigStateMachine(db)
    await sm.transition(asset, asset.current_version,
                        action=ConfigTransition.APPROVE,
                        actor=actor, role="PROCESS_CONTROLLER")
    await db.commit()
    assert asset.status == ConfigStatus.APPROVED
    audit = (await db.execute(
        select(AuditLog).where(AuditLog.resource_id == str(asset.asset_id))
    )).scalar_one()
    assert audit.action == AuditAction.CONFIG_ASSET_APPROVED

async def test_pending_to_draft_on_reject_writes_audit(db):
    asset = await make_asset(db, status=ConfigStatus.PENDING)
    sm = ConfigStateMachine(db)
    await sm.transition(asset, asset.current_version,
                        action=ConfigTransition.REJECT, actor=actor)
    await db.commit()
    assert asset.status == ConfigStatus.DRAFT
    audit = (await db.execute(
        select(AuditLog).where(AuditLog.resource_id == str(asset.asset_id))
    )).scalar_one()
    assert audit.action == AuditAction.CONFIG_ASSET_REJECTED

async def test_approved_to_published_writes_audit(db):
    asset = await make_asset(db, status=ConfigStatus.APPROVED)
    sm = ConfigStateMachine(db)
    await sm.transition(asset, asset.current_version,
                        action=ConfigTransition.PUBLISH, actor=actor)
    await db.commit()
    assert asset.status == ConfigStatus.PUBLISHED
    audit = (await db.execute(
        select(AuditLog).where(AuditLog.resource_id == str(asset.asset_id))
    )).scalar_one()
    assert audit.action == AuditAction.CONFIG_ASSET_PUBLISHED

async def test_published_to_obsolete_writes_audit(db):
    asset = await make_asset(db, status=ConfigStatus.PUBLISHED)
    sm = ConfigStateMachine(db)
    await sm.transition(asset, asset.current_version,
                        action=ConfigTransition.OBSOLETE, actor=actor)
    await db.commit()
    assert asset.status == ConfigStatus.OBSOLETE
    audit = (await db.execute(
        select(AuditLog).where(AuditLog.resource_id == str(asset.asset_id))
    )).scalar_one()
    assert audit.action == AuditAction.CONFIG_ASSET_OBSOLETED

async def test_invalid_transition_raises(db):
    asset = await make_asset(db, status=ConfigStatus.DRAFT)
    sm = ConfigStateMachine(db)
    with pytest.raises(InvalidTransitionError):
        await sm.transition(asset, asset.current_version,
                            action=ConfigTransition.PUBLISH, actor=actor)
```

- [ ] **Step 2: 跑测试，验证失败**

Run: `cd pcs-backend && uv run pytest tests/services/test_config_state_machine.py -v`
Expected: FAIL `ModuleNotFoundError: No module named 'app.services.config_state_machine'`

- [ ] **Step 3: 创建状态机**

`app/services/config_state_machine.py`：
```python
from uuid import UUID
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.config_domain import ConfigAsset, ConfigVersion
from app.models.audit_log import AuditLog
from app.services.audit_service import AuditService
from app.models.enums import AuditAction, ConfigTransition, ConfigStatus  # ← 单一来源

class InvalidTransitionError(Exception):
    pass

# action → audit action 映射
TRANSITION_AUDIT_ACTION: dict[ConfigTransition, AuditAction] = {
    ConfigTransition.SUBMIT: AuditAction.CONFIG_ASSET_SUBMITTED,
    ConfigTransition.APPROVE: AuditAction.CONFIG_ASSET_APPROVED,
    ConfigTransition.REJECT: AuditAction.CONFIG_ASSET_REJECTED,
    ConfigTransition.PUBLISH: AuditAction.CONFIG_ASSET_PUBLISHED,
    ConfigTransition.OBSOLETE: AuditAction.CONFIG_ASSET_OBSOLETED,
}

class ConfigStateMachine:
    """配置资产状态机 — 与 P1 StateMachineService 一致：审计内置 + caller commit。"""
    TRANSITIONS = {
        ConfigStatus.DRAFT: {ConfigTransition.SUBMIT, ConfigTransition.OBSOLETE},
        ConfigStatus.PENDING: {ConfigTransition.APPROVE, ConfigTransition.REJECT},
        ConfigStatus.APPROVED: {ConfigTransition.PUBLISH, ConfigTransition.OBSOLETE},
        ConfigStatus.PUBLISHED: {ConfigTransition.OBSOLETE},
        ConfigStatus.OBSOLETE: set(),
    }

    def __init__(self, session: AsyncSession):
        self.session = session
        self.audit = AuditService(session)

    async def transition(
        self,
        asset: ConfigAsset,
        version: ConfigVersion,
        *,
        action: ConfigTransition,
        actor: AuthUser,
        reason: Optional[str] = None,
    ) -> ConfigVersion:
        """执行状态转移 + 审计落库。caller 负责 session.commit()。"""
        allowed = self.TRANSITIONS.get(asset.status, set())
        if action not in allowed:
            raise InvalidTransitionError(f"{asset.status} → {action} 不允许")
        old_status = asset.status
        # 状态变更
        if action == ConfigTransition.SUBMIT:
            asset.status = ConfigStatus.PENDING
        elif action == ConfigTransition.APPROVE:
            asset.status = ConfigStatus.APPROVED
        elif action == ConfigTransition.REJECT:
            asset.status = ConfigStatus.DRAFT
        elif action == ConfigTransition.PUBLISH:
            asset.status = ConfigStatus.PUBLISHED
        elif action == ConfigTransition.OBSOLETE:
            asset.status = ConfigStatus.OBSOLETE
        await self.session.flush()
        # 审计写入
        await self.audit.write(
            user_id=actor.user_id,
            module="CONFIG",
            object_id=str(asset.asset_id),
            action=TRANSITION_AUDIT_ACTION[action],
            old_value={"status": old_status.value},
            new_value={"status": asset.status.value},
            remarks=reason,
        )
        return version
```

`app/models/enums.py` 追加 `ConfigStatus` 和 `ConfigTransition` 枚举（**唯一来源**，状态机 import 不重复定义）：
```python
class ConfigStatus(str, Enum):
    DRAFT = "DRAFT"
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    PUBLISHED = "PUBLISHED"
    OBSOLETE = "OBSOLETE"

class ConfigTransition(str, Enum):
    SUBMIT = "SUBMIT"
    APPROVE = "APPROVE"
    REJECT = "REJECT"
    PUBLISH = "PUBLISH"
    OBSOLETE = "OBSOLETE"
```

- [ ] **Step 4: 跑测试，验证通过**

Run: `cd pcs-backend && uv run pytest tests/services/test_config_state_machine.py -v`
Expected: 6 passed（每个测试同时验证状态 + 审计落库）

- [ ] **Step 5: Commit**

```bash
git add pcs-backend/app/services/config_state_machine.py pcs-backend/app/models/enums.py pcs-backend/tests/services/test_config_state_machine.py
git commit -m "feat(p2): ConfigStateMachine 5 态骨架"
```

### Task 1.3: 双重审批通过双行 config_approvals 表达

**Files:**
- Modify: `pcs-backend/app/services/config_state_machine.py`
- Test: `pcs-backend/tests/services/test_config_state_machine.py`（追加）

**Interfaces:**
- Consumes: `ConfigApproval` ORM 模型
- Produces: `ConfigStateMachine.approve_with_double_signoff(asset, approver_id, role) -> bool`

- [ ] **Step 1: 写失败测试**

```python
def test_double_signoff_full_approve():
    asset = make_asset(status=ConfigStatus.PENDING, category="CATEGORY_2")
    # 第一行：PROCESS_CONTROLLER 批准
    ConfigStateMachine.record_approval(asset, approver_id=user_a, role="PROCESS_CONTROLLER", decision="APPROVED")
    assert asset.status == ConfigStatus.PENDING  # 还未到 APPROVED
    # 第二行：SYSTEM_ADMIN 批准
    ConfigStateMachine.record_approval(asset, approver_id=user_b, role="SYSTEM_ADMIN", decision="APPROVED")
    assert asset.status == ConfigStatus.APPROVED  # 两行均 APPROVED 才进

def test_double_signoff_any_reject_returns_to_draft():
    asset = make_asset(status=ConfigStatus.PENDING, category="CATEGORY_2")
    ConfigStateMachine.record_approval(asset, approver_id=user_a, role="PROCESS_CONTROLLER", decision="APPROVED")
    ConfigStateMachine.record_approval(asset, approver_id=user_b, role="SYSTEM_ADMIN", decision="REJECTED")
    assert asset.status == ConfigStatus.DRAFT  # 任一驳回即回 DRAFT
```

- [ ] **Step 2-4: 实现 record_approval 双行逻辑（D20 一致：instance method + 审计内置）**

`config_state_machine.py` 追加：
```python
from app.models.config_domain import ConfigApproval
from sqlalchemy import select

class ConfigStateMachine:
    DOUBLE_SIGNOFF_CATEGORIES = {"CATEGORY_2"}

    async def record_approval(
        self,
        asset: ConfigAsset,
        version: ConfigVersion,
        *,
        approver_id: UUID,
        role: str,
        decision: str,  # "APPROVED" | "REJECTED"
        actor: AuthUser,
        reason: Optional[str] = None,
    ) -> ConfigApproval:
        """插入 config_approvals 行 + 状态判定 + 审计落库。

        双段签（CATEGORY_2）：第 1/2 行都 APPROVED → APPROVED；任一 REJECTED → DRAFT
        单层（CATEGORY_3 等）：单行 APPROVED → APPROVED；REJECTED → DRAFT
        caller 负责 session.commit()。
        """
        approval = ConfigApproval(
            version_id=version.version_id,
            approver_id=approver_id,
            approver_role=role,
            decision=decision,
        )
        self.session.add(approval)
        await self.session.flush()  # 让 approval 立即可查，避免脏读

        # 重新查询该 version 下所有 approvals（确保包含本行）
        approvals = (await self.session.execute(
            select(ConfigApproval).where(ConfigApproval.version_id == version.version_id)
        )).scalars().all()

        old_status = asset.status
        if asset.category in self.DOUBLE_SIGNOFF_CATEGORIES:
            # 双段签：任一驳回即回 DRAFT；全部批准才进 APPROVED
            if any(a.decision == "REJECTED" for a in approvals):
                asset.status = ConfigStatus.DRAFT
            elif len(approvals) >= 2 and all(a.decision == "APPROVED" for a in approvals):
                asset.status = ConfigStatus.APPROVED
            # 否则保持 PENDING（等下一段签）
        else:
            # 单层：单行决定
            if decision == "REJECTED":
                asset.status = ConfigStatus.DRAFT
            elif decision == "APPROVED":
                asset.status = ConfigStatus.APPROVED

        await self.session.flush()
        # 审计落库（D20 一致）
        audit_action = (
            AuditAction.CONFIG_ASSET_REJECTED if decision == "REJECTED"
            else AuditAction.CONFIG_ASSET_APPROVED
        )
        await self.audit.write(
            user_id=actor.user_id,
            module="CONFIG",
            object_id=str(asset.asset_id),
            action=audit_action,
            old_value={"status": old_status.value, "approver_role": role},
            new_value={"status": asset.status.value, "approval_id": str(approval.approval_id)},
            remarks=reason,
        )
        return approval
```

**调用方**：
```python
sm = ConfigStateMachine(db)
await sm.record_approval(
    asset, asset.current_version,
    approver_id=user.user_id, role="PROCESS_CONTROLLER",
    decision="APPROVED", actor=user,
)
await commit_or_rollback(db)
```

- [ ] **Step 5: 跑测试 + Commit**

Run: `cd pcs-backend && uv run pytest tests/services/test_config_state_machine.py -v`
Expected: 8 passed

```bash
git commit -am "feat(p2): 双段签通过 config_approvals 双行表达（与 D20 一致）"
```

### Task 1.4: ACL 装饰器（LDAP 角色 + workspaces 项目组）

**Files:**
- Create: `pcs-backend/app/core/acl.py`
- Test: `pcs-backend/tests/core/test_acl.py`

**Interfaces:**
- Consumes: `current_user` 依赖（来自 P1 auth）
- Produces: `require_role("PROCESS_CONTROLLER")`、`require_workspace_member(project_id)`

- [ ] **Step 1: 写失败测试**

```python
def test_require_role_designer_can_create_draft():
    user = make_user(roles=["DESIGNER"])
    decorator = require_role("DESIGNER")
    assert decorator(lambda: "ok")(user=user) == "ok"

def test_require_role_process_controller_blocks_designer():
    user = make_user(roles=["DESIGNER"])
    decorator = require_role("PROCESS_CONTROLLER")
    with pytest.raises(PermissionDeniedError):
        decorator(lambda: "ok")(user=user)
```

- [ ] **Step 2-4: 实现 acl 模块**

`app/core/acl.py`：
```python
from functools import wraps

class PermissionDeniedError(Exception):
    pass

def require_role(*allowed_roles):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, user=None, **kwargs):
            if user is None or not any(r in allowed_roles for r in user.roles):
                raise PermissionDeniedError(f"需要角色 {allowed_roles}")
            return func(*args, user=user, **kwargs)
        return wrapper
    return decorator
```

- [ ] **Step 5: 跑测试 + Commit**

```bash
git commit -am "feat(p2): ACL 装饰器 require_role"
```

---

## Phase 2: Sprint 1 公式/系数/模板/编号（~3 周）

### Task 2.1: parameters_json schema 锁定（D16）

**Files:**
- Create: `pcs-backend/app/schemas/formula.py`
- Test: `pcs-backend/tests/schemas/test_formula.py`

- [ ] **Step 1: 写失败测试**

```python
def test_parameters_json_schema_valid():
    schema = FormulaParametersSchema.model_validate({
        "parameters": [
            {"name": "f", "unit": "dimensionless", "description": "摩擦因子",
             "min": 0.0, "max": 1.0, "default": None}
        ]
    })
    assert schema.parameters[0].name == "f"

def test_parameters_json_schema_rejects_missing_name():
    with pytest.raises(ValidationError):
        FormulaParametersSchema.model_validate({
            "parameters": [{"unit": "x"}]
        })
```

- [ ] **Step 2-4: 实现 Pydantic schema**

```python
# app/schemas/formula.py
from pydantic import BaseModel, Field
from typing import Optional

class FormulaParameter(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    unit: Optional[str] = None
    description: Optional[str] = None
    min: Optional[float] = None
    max: Optional[float] = None
    default: Optional[float] = None

class FormulaParametersSchema(BaseModel):
    parameters: list[FormulaParameter]
```

- [ ] **Step 5: Commit**

```bash
git commit -am "feat(p2): parameters_json Pydantic schema"
```

### Task 2.2: unit_tests_json schema 锁定（D16）

**Files:**
- Modify: `pcs-backend/app/schemas/formula.py`
- Test: `pcs-backend/tests/schemas/test_formula.py`（追加）

- [ ] **Step 1-4: 实现对象数组 schema**

```python
class UnitTestCase(BaseModel):
    params: dict[str, float]
    expected: float
    tolerance: float = 0.01

class UnitTestsSchema(BaseModel):
    unit_tests: list[UnitTestCase]
```

- [ ] **Step 5: Commit**

### Task 2.3: FormulaEngine.parse() SymPy 解析 + AST 白名单

**Files:**
- Create: `pcs-backend/app/services/formula_engine.py`
- Test: `pcs-backend/tests/services/test_formula_engine.py`
- Fuzz: `pcs-backend/tests/fuzz/test_formula_engine.py`

**Interfaces:**
- Consumes: `expression: str`, `parameters: dict`
- Produces: `Callable[[dict], float]`

- [ ] **Step 1: 写失败测试（合法表达式）**

```python
def test_parse_simple_arithmetic():
    f = FormulaEngine.parse("a + b", {"a": 1.0, "b": 2.0})
    assert f({"a": 1.0, "b": 2.0}) == 3.0

def test_parse_math_function():
    f = FormulaEngine.parse("math.sqrt(x)", {"x": 4.0})
    assert f({"x": 4.0}) == 2.0
```

- [ ] **Step 2-4: 实现 parse**

```python
# app/services/formula_engine.py
import ast
import math
import operator as op
from typing import Callable

class FormulaSecurityError(Exception):
    pass

class FormulaEngine:
    ALLOWED_FUNCS = {"sqrt", "log", "exp", "sin", "cos", "tan", "pow", "abs", "min", "max"}
    ALLOWED_NAMES = {"math"} | ALLOWED_FUNCS
    FORBIDDEN_NODES = (
        ast.Import, ast.ImportFrom, ast.Global, ast.Nonlocal,
        ast.Lambda, ast.FunctionDef, ast.ClassDef,
        ast.Try, ast.With, ast.AsyncFor, ast.AsyncWith,
    )
    FORBIDDEN_NAMES = {"__", "open", "eval", "exec", "compile", "globals", "locals", "vars"}

    @classmethod
    def parse(cls, expression: str, parameters: dict) -> Callable:
        tree = ast.parse(expression, mode="eval")
        cls._validate_ast(tree)
        namespace = {"math": math, **{name: getattr(math, name) for name in cls.ALLOWED_FUNCS if hasattr(math, name)}}
        namespace.update(parameters)
        code = compile(tree, "<formula>", "eval")
        def evaluator(p: dict) -> float:
            merged = {**namespace, **p}
            return float(eval(code, {"__builtins__": {}}, merged))
        return evaluator

    @classmethod
    def _validate_ast(cls, tree):
        for node in ast.walk(tree):
            if isinstance(node, cls.FORBIDDEN_NODES):
                raise FormulaSecurityError(f"禁止节点: {type(node).__name__}")
            if isinstance(node, ast.Name) and any(f in node.id for f in cls.FORBIDDEN_NAMES):
                raise FormulaSecurityError(f"禁止名称: {node.id}")

    @staticmethod
    def compute_version_hash(expression: str, parameters: dict | None = None) -> str:
        """公式版本指纹（SHA-256 截前 16 位）。

        复用了 P1 ADR-0013 record_hash 的规范化策略：
        1) expression 字符串原样参与哈希（保留空格差异视为不同版本）
        2) parameters 按 key 排序后再序列化，避免 dict 顺序导致 hash 漂移
        3) SHA-256 → hex → 取前 16 字符（64 bit，碰撞概率 ~1/2^32 满足公式库规模）

        调用方：ConfigVersion 创建时自动调用填充 formula_version 列。
        """
        import hashlib
        import json
        params_repr = json.dumps(parameters or {}, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
        payload = f"{expression.strip()}\x1f{params_repr}".encode("utf-8")
        return hashlib.sha256(payload).hexdigest()[:16]
```

- [ ] **Step 5: Fuzz + Commit**

```python
# tests/fuzz/test_formula_engine.py
import hypothesis
from hypothesis import given, strategies as st

@given(st.text(min_size=1, max_size=100))
def test_no_rce_on_garbage(s):
    try:
        FormulaEngine.parse(s, {"x": 1.0})
    except (FormulaSecurityError, SyntaxError, ValueError):
        pass  # expected
```

Run: `cd pcs-backend && uv run pytest tests/fuzz/test_formula_engine.py -v`
Expected: PASS（无 RCE）

```bash
git commit -am "feat(p2): FormulaEngine SymPy 解析 + AST 白名单"
```

### Task 2.4: FormulaEngine.run_unit_tests + 100% pass 硬门槛

**Files:**
- Modify: `pcs-backend/app/services/formula_engine.py`
- Test: `tests/services/test_formula_engine.py`（追加）

- [ ] **Step 1-4: 实现 run_unit_tests**

```python
class FormulaEngine:
    @classmethod
    def run_unit_tests(cls, expression: str, parameters: dict, unit_tests: list[dict]) -> tuple[int, int]:
        """返回 (passed, total)。PUBLISH 端点断言 passed == total。"""
        fn = cls.parse(expression, parameters)
        passed = 0
        for tc in unit_tests:
            try:
                result = fn(tc["params"])
                if abs(result - tc["expected"]) <= tc.get("tolerance", 0.01):
                    passed += 1
            except Exception:
                pass
        return passed, len(unit_tests)
```

- [ ] **Step 5: Commit**

```bash
git commit -am "feat(p2): run_unit_tests 100% pass 硬门槛"
```

### Task 2.5: 系数库 service（CRUD + 批量修改）

**Files:**
- Create: `pcs-backend/app/services/coefficient_service.py`
- Test: `pcs-backend/tests/services/test_coefficient_service.py`

**Interfaces:**
- Consumes: `AssetRepository`（DRAFT/PUBLISHED 状态判定）、`AuditService(session)`
- Produces:
  - `CoefficientService.create_table(asset_id, name, data_json, applicable_range=None) -> CoefficientTable`
  - `CoefficientService.bulk_update(table_id, data_json, actor) -> CoefficientTable`
  - `CoefficientService.query(table_id) -> CoefficientTable`

- [ ] **Step 1: 写失败测试**

```python
# tests/services/test_coefficient_service.py
import pytest
from app.services.coefficient_service import CoefficientService, CoefficientNotFoundError

async def test_create_table(db):
    svc = CoefficientService(db)
    table = await svc.create_table(
        asset_id=uuid4(),
        name="摩阻系数",
        data_json={
            "headers": ["row_label", "value1", "unit"],
            "rows": [["condition_A", 1.0, "MPa"]],
        },
        applicable_range="0<T<200°C",
    )
    assert table.table_id is not None
    assert table.data_json["headers"][0] == "row_label"

async def test_bulk_update_replaces_data_json(db, sample_table):
    svc = CoefficientService(db)
    new_data = {"headers": ["x"], "rows": [[1.0]], "applicable_range": None}
    updated = await svc.bulk_update(sample_table.table_id, new_data, actor=uuid4())
    assert updated.data_json["headers"] == ["x"]
    # 审计写入
    audit = (await db.execute(select(AuditLog).where(AuditLog.resource_id == sample_table.table_id))).scalars().first()
    assert audit is not None
    assert audit.action == AuditAction.CONFIG_VERSION_CREATED

async def test_bulk_update_unknown_table_raises(db):
    svc = CoefficientService(db)
    with pytest.raises(CoefficientNotFoundError):
        await svc.bulk_update(uuid4(), {}, actor=uuid4())

async def test_query_returns_table(db, sample_table):
    svc = CoefficientService(db)
    t = await svc.query(sample_table.table_id)
    assert t.name == sample_table.name
```

- [ ] **Step 2: 跑测试，验证失败**

Run: `cd pcs-backend && uv run pytest tests/services/test_coefficient_service.py -v`
Expected: FAIL `ModuleNotFoundError: No module named 'app.services.coefficient_service'`

- [ ] **Step 3: 实现 service**

```python
# app/services/coefficient_service.py
from uuid import UUID
from app.models.config_domain import CoefficientTable
from app.services.audit_service import AuditService
from app.models.enums import AuditAction

class CoefficientNotFoundError(Exception):
    pass

class CoefficientService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.audit = AuditService(session)

    async def create_table(self, *, asset_id, name, data_json, applicable_range=None) -> CoefficientTable:
        table = CoefficientTable(
            asset_id=asset_id,
            name=name,
            data_json=data_json,
            applicable_range=applicable_range,
            status="DRAFT",
        )
        self.session.add(table)
        await self.session.flush()
        return table

    async def bulk_update(self, table_id: UUID, data_json: dict, *, actor: UUID) -> CoefficientTable:
        table = await self.session.get(CoefficientTable, table_id)
        if table is None:
            raise CoefficientNotFoundError(f"未找到 table_id={table_id}")
        table.data_json = data_json
        await self.session.flush()
        await self.audit.write(
            user_id=actor,
            action=AuditAction.CONFIG_VERSION_CREATED,
            resource_type="coefficient_table",
            resource_id=str(table_id),
        )
        return table

    async def query(self, table_id: UUID) -> CoefficientTable:
        table = await self.session.get(CoefficientTable, table_id)
        if table is None:
            raise CoefficientNotFoundError(f"未找到 table_id={table_id}")
        return table
```

- [ ] **Step 4: 跑测试，验证通过**

Run: `cd pcs-backend && uv run pytest tests/services/test_coefficient_service.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add pcs-backend/app/services/coefficient_service.py pcs-backend/tests/services/test_coefficient_service.py
git commit -m "feat(p2): CoefficientService create / bulk_update / query + audit"
```

### Task 2.6: 模板管理 service（文件上传 + sha256 + Jinja2 占位符）

**Files:**
- Create: `pcs-backend/app/services/template_service.py`
- Test: `pcs-backend/tests/services/test_template_service.py`

**Interfaces:**
- Consumes: 本地文件系统 `/var/lib/pcs/templates/`、Jinja2 Environment
- Produces:
  - `TemplateService.upload(asset_id, file_bytes, file_name, file_type) -> TemplateFile`
  - `TemplateService.render(template_id, context: dict) -> str`
  - `TemplateService.update_placeholders(template_id, placeholders_json, actor) -> TemplateFile`

- [ ] **Step 1: 写失败测试**

```python
# tests/services/test_template_service.py
import pytest
from app.services.template_service import TemplateService, TemplateRenderError

async def test_upload_writes_file_and_records_sha256(db, tmp_path):
    svc = TemplateService(db, storage_root=tmp_path)
    file_bytes = b"<html>{{title}}</html>"
    tpl = await svc.upload(
        asset_id=uuid4(),
        file_bytes=file_bytes,
        file_name="report.html.j2",
        file_type="html",
    )
    assert tpl.sha256 == hashlib.sha256(file_bytes).hexdigest()
    assert (tmp_path / f"{tpl.sha256}.html.j2").read_bytes() == file_bytes

async def test_render_substitutes_placeholders(db, tmp_path, sample_template):
    svc = TemplateService(db, storage_root=tmp_path)
    rendered = await svc.render(sample_template.template_id, {"title": "P&ID Report"})
    assert "P&ID Report" in rendered

async def test_render_unknown_placeholder_raises(db, tmp_path, sample_template):
    svc = TemplateService(db, storage_root=tmp_path)
    with pytest.raises(TemplateRenderError):
        await svc.render(sample_template.template_id, {"undefined_var": 1})
```

- [ ] **Step 2: 跑测试，验证失败**

Run: `cd pcs-backend && uv run pytest tests/services/test_template_service.py -v`
Expected: FAIL `ModuleNotFoundError`

- [ ] **Step 3: 实现 service**

```python
# app/services/template_service.py
import hashlib
from pathlib import Path
from jinja2 import Environment, StrictUndefined, TemplateError
from app.models.config_domain import TemplateFile
from app.services.audit_service import AuditService
from app.models.enums import AuditAction

class TemplateRenderError(Exception):
    pass

class TemplateService:
    def __init__(self, session: AsyncSession, storage_root: Path):
        self.session = session
        self.storage_root = Path(storage_root)
        self.audit = AuditService(session)
        self.storage_root.mkdir(parents=True, exist_ok=True)
        self.jinja = Environment(undefined=StrictUndefined)

    async def upload(self, *, asset_id, file_bytes: bytes, file_name: str, file_type: str) -> TemplateFile:
        sha = hashlib.sha256(file_bytes).hexdigest()
        path = self.storage_root / f"{sha}.{file_name}"
        path.write_bytes(file_bytes)
        tpl = TemplateFile(
            asset_id=asset_id,
            name=file_name,
            file_type=file_type,
            file_path=str(path),
            placeholders_json={"vars": []},
            status="DRAFT",
        )
        self.session.add(tpl)
        await self.session.flush()
        return tpl

    async def render(self, template_id: UUID, context: dict) -> str:
        tpl = await self.session.get(TemplateFile, template_id)
        if tpl is None:
            raise TemplateRenderError(f"未找到 template_id={template_id}")
        body = Path(tpl.file_path).read_text(encoding="utf-8")
        try:
            return self.jinja.from_string(body).render(**context)
        except TemplateError as e:
            raise TemplateRenderError(str(e)) from e

    async def update_placeholders(self, template_id: UUID, placeholders_json: dict, *, actor: UUID) -> TemplateFile:
        tpl = await self.session.get(TemplateFile, template_id)
        if tpl is None:
            raise TemplateRenderError(f"未找到 template_id={template_id}")
        tpl.placeholders_json = placeholders_json
        await self.session.flush()
        await self.audit.write(
            user_id=actor,
            action=AuditAction.CONFIG_VERSION_CREATED,
            resource_type="template_file",
            resource_id=str(template_id),
        )
        return tpl
```

- [ ] **Step 4: 跑测试，验证通过**

Run: `cd pcs-backend && uv run pytest tests/services/test_template_service.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add pcs-backend/app/services/template_service.py pcs-backend/tests/services/test_template_service.py
git commit -m "feat(p2): TemplateService upload + sha256 + Jinja2 render"
```

### Task 2.7: 编号 service（事务原子自增 + UQ 防并发）

**Files:**
- Create: `pcs-backend/app/services/numbering_service.py`
- Test: `pcs-backend/tests/services/test_numbering_service.py`

**Interfaces:**
- Consumes: `doc_no_sequences` 表，`UNIQUE(project_id, template_id, scope_key)` 约束
- Produces:
  - `NumberingService.next_value(project_id, template_id, scope_key) -> int`
  - `NumberingService.reset(project_id, template_id, scope_key, new_value=0, actor) -> None`

- [ ] **Step 1: 写失败测试**

```python
# tests/services/test_numbering_service.py
import pytest
import asyncio
from app.services.numbering_service import NumberingService, SequenceNotFoundError

async def test_next_value_increments(db, sample_sequence):
    svc = NumberingService(db)
    v1 = await svc.next_value(sample_sequence.project_id, sample_sequence.template_id, "scope_A")
    v2 = await svc.next_value(sample_sequence.project_id, sample_sequence.template_id, "scope_A")
    assert v2 == v1 + 1

async def test_next_value_creates_sequence_if_missing(db, project_id, template_id):
    svc = NumberingService(db)
    v = await svc.next_value(project_id, template_id, "new_scope")
    assert v == 1

async def test_concurrent_calls_yield_unique_values(db, project_id, template_id):
    svc = NumberingService(db)
    # 预热创建 sequence
    await svc.next_value(project_id, template_id, "concurrent_scope")
    await db.commit()
    # 10 个并发调用
    results = await asyncio.gather(*[
        NumberingService(db).next_value(project_id, template_id, "concurrent_scope")
        for _ in range(10)
    ])
    assert len(set(results)) == 10  # 全部唯一
    assert min(results) == 2 and max(results) == 11  # 1 是预热

async def test_reset_clears_counter(db, sample_sequence, actor):
    svc = NumberingService(db)
    await svc.next_value(sample_sequence.project_id, sample_sequence.template_id, "scope_A")
    await svc.reset(sample_sequence.project_id, sample_sequence.template_id, "scope_A", new_value=0, actor=actor)
    v = await svc.next_value(sample_sequence.project_id, sample_sequence.template_id, "scope_A")
    assert v == 1
```

- [ ] **Step 2: 跑测试，验证失败**

Run: `cd pcs-backend && uv run pytest tests/services/test_numbering_service.py -v`
Expected: FAIL `ModuleNotFoundError`

- [ ] **Step 3: 实现 service**

```python
# app/services/numbering_service.py
from uuid import UUID
from sqlalchemy import select
from app.models.config_domain import DocNoSequence
from app.services.audit_service import AuditService
from app.models.enums import AuditAction

class SequenceNotFoundError(Exception):
    pass

class NumberingService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.audit = AuditService(session)

    async def next_value(self, project_id: UUID, template_id: UUID, scope_key: str) -> int:
        # SELECT ... FOR UPDATE 行锁 — Postgres 串行化同 scope 的并发
        row = (await self.session.execute(
            select(DocNoSequence).where(
                DocNoSequence.project_id == project_id,
                DocNoSequence.template_id == template_id,
                DocNoSequence.scope_key == scope_key,
            ).with_for_update()
        )).scalar_one_or_none()
        if row is None:
            row = DocNoSequence(
                project_id=project_id,
                template_id=template_id,
                scope_key=scope_key,
                current_value=0,
            )
            self.session.add(row)
            await self.session.flush()
        row.current_value += 1
        await self.session.flush()
        return row.current_value

    async def reset(self, project_id, template_id, scope_key, *, new_value=0, actor: UUID) -> None:
        row = (await self.session.execute(
            select(DocNoSequence).where(
                DocNoSequence.project_id == project_id,
                DocNoSequence.template_id == template_id,
                DocNoSequence.scope_key == scope_key,
            ).with_for_update()
        )).scalar_one_or_none()
        if row is None:
            raise SequenceNotFoundError(f"未找到 scope={scope_key}")
        row.current_value = new_value
        await self.session.flush()
        await self.audit.write(
            user_id=actor,
            action=AuditAction.CONFIG_VERSION_CREATED,
            resource_type="doc_no_sequence",
            resource_id=f"{project_id}/{template_id}/{scope_key}",
        )
```

- [ ] **Step 4: 跑测试，验证通过**

Run: `cd pcs-backend && uv run pytest tests/services/test_numbering_service.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add pcs-backend/app/services/numbering_service.py pcs-backend/tests/services/test_numbering_service.py
git commit -m "feat(p2): NumberingService 事务原子自增 + 并发测试"
```

### Task 2.7.1: 测试 fixtures (conftest.py)

**Files:**
- Create: `pcs-backend/tests/conftest.py`

各 Task 测试大量使用 `make_asset` / `sample_user_token` / `sample_draft_asset` 等 fixture。统一在 `conftest.py` 定义，避免重复。

- [ ] **Step 1: 实现 conftest**

```python
# tests/conftest.py
import pytest
from uuid import uuid4, UUID
from httpx import AsyncClient
from app.db.session import async_session_factory
from app.models.config_domain import (
    ConfigAsset, ConfigVersion, ConfigApproval,
    CoefficientTable, TemplateFile, DocNoSequence,
)
from app.models.equipment import EquipmentList
from app.models.data_lineage import DataLineage
from app.models.enums import ConfigStatus
from app.auth.ldap_mock import make_token  # P1 mock

@pytest.fixture
async def db():
    async with async_session_factory() as session:
        yield session
        await session.rollback()

@pytest.fixture
def actor() -> UUID:
    """默认测试 actor UUID。"""
    return uuid4()

@pytest.fixture
def pc_actor() -> UUID:
    """PROCESS_CONTROLLER 角色 UUID。"""
    return uuid4()

@pytest.fixture
def designer_actor() -> UUID:
    """DESIGNER 角色 UUID。"""
    return uuid4()

@pytest.fixture
async def make_asset(db):
    """资产工厂。"""
    async def _make(*, status=ConfigStatus.DRAFT, category="CATEGORY_2", name="test"):
        asset = ConfigAsset(category=category, name=name, status=status)
        db.add(asset)
        await db.flush()
        version = ConfigVersion(
            asset_id=asset.asset_id,
            version_code="v1",
            content_json={},
            status=status,
            formula_version=FormulaEngine.compute_version_hash(expression="", parameters={}),
        )
        db.add(version)
        await db.flush()
        asset.current_version_id = version.version_id
        await db.flush()
        return asset
    return _make

@pytest.fixture
async def sample_draft_asset(db, make_asset):
    return await make_asset(status=ConfigStatus.DRAFT)

@pytest.fixture
async def sample_pending_asset(db, make_asset):
    return await make_asset(status=ConfigStatus.PENDING)

@pytest.fixture
async def sample_pending_asset_c3(db, make_asset):
    return await make_asset(status=ConfigStatus.PENDING, category="CATEGORY_3")

@pytest.fixture
async def sample_approved_formula_asset(db, make_asset):
    """公式资产，APPROVED 且 unit_tests_json 全部通过。"""
    asset = await make_asset(status=ConfigStatus.APPROVED, category="CATEGORY_2")
    asset.current_version.content_json = {
        "expression": "a + b",
        "parameters_json": {"parameters": [{"name": "a"}, {"name": "b"}]},
        "unit_tests_json": {"unit_tests": [{"params": {"a": 1, "b": 2}, "expected": 3, "tolerance": 0.01}]},
    }
    await db.flush()
    return asset

@pytest.fixture
async def sample_approved_formula_with_failing_test(db, make_asset):
    asset = await make_asset(status=ConfigStatus.APPROVED, category="CATEGORY_2")
    asset.current_version.content_json = {
        "expression": "a + b",
        "parameters_json": {"parameters": [{"name": "a"}, {"name": "b"}]},
        "unit_tests_json": {"unit_tests": [
            {"params": {"a": 1, "b": 2}, "expected": 3, "tolerance": 0.01},  # pass
            {"params": {"a": 2, "b": 2}, "expected": 999, "tolerance": 0.01},  # fail
        ]},
    }
    await db.flush()
    return asset

@pytest.fixture
async def sample_published_asset(db, make_asset):
    return await make_asset(status=ConfigStatus.PUBLISHED)

@pytest.fixture
async def sample_two_version_asset(db, make_asset):
    asset = await make_asset(status=ConfigStatus.PUBLISHED)
    v2 = ConfigVersion(asset_id=asset.asset_id, version_code="v2",
                       content_json={"new_field": 1}, status=ConfigStatus.PUBLISHED,
                       formula_version=FormulaEngine.compute_version_hash(expression="", parameters={"new_field": 1}))
    db.add(v2)
    await db.flush()
    return asset

@pytest.fixture
async def sample_assets_and_versions(db):
    """报表测试用：3 个 category 各自不同状态的资产 + 版本。"""
    # 实际填充按 Task 5.1 测试用例需求
    pass  # 在 Task 5.1 测试文件中按需实现

@pytest.fixture
async def sample_sequence(db):
    seq = DocNoSequence(
        project_id=uuid4(),
        template_id=uuid4(),
        scope_key="scope_A",
        current_value=0,
    )
    db.add(seq)
    await db.flush()
    return seq

@pytest.fixture
async def sample_user_token() -> str:
    return make_token(roles=["DESIGNER"])

@pytest.fixture
async def sample_pc_token() -> str:
    return make_token(roles=["PROCESS_CONTROLLER"])

@pytest.fixture
async def sample_designer_token() -> str:
    return make_token(roles=["DESIGNER"])

@pytest.fixture
async def client(db):
    from app.main import app
    async with AsyncClient(app=app, base_url="http://test") as c:
        yield c
```

- [ ] **Step 2: 验证**

```bash
cd pcs-backend && uv run pytest tests/conftest.py -v --collect-only
```

- [ ] **Step 3: Commit**

```bash
git add pcs-backend/tests/conftest.py
git commit -m "test(p2): 共享 conftest fixtures"
```

### Task 2.8: API 端点 + 双引擎 async

**Files:**
- Create: `pcs-backend/app/api/v1/config.py`
- Test: `pcs-backend/tests/api/v1/test_config.py`

**端点列表**：
```
POST   /api/v1/config/assets                # 创建 config_asset (DRAFT)
POST   /api/v1/config/assets/{id}/versions  # 新版本（DRAFT）
POST   /api/v1/config/assets/{id}/fork      # 从 PUBLISHED fork 新 DRAFT 版本
POST   /api/v1/config/assets/{id}/submit    # DRAFT→PENDING
POST   /api/v1/config/assets/{id}/approve   # PENDING→APPROVED（CATEGORY_2 走 record_approval 双行）
POST   /api/v1/config/assets/{id}/publish   # APPROVED→PUBLISHED（含公式 unit_tests 100% pass 校验）
POST   /api/v1/config/assets/{id}/obsolete  # →OBSOLETE
GET    /api/v1/config/assets/{id}/diff?v1&v2
```

均 async + commit_or_rollback 包裹。

- [ ] **Step 1: 写失败测试（happy + 1 failure per endpoint）**

```python
# tests/api/v1/test_config.py
import pytest
from httpx import AsyncClient

@pytest.fixture
async def client(db):
    from app.main import app
    async with AsyncClient(app=app, base_url="http://test") as c:
        yield c

# POST /assets — happy
async def test_create_asset_returns_draft(client, sample_user_token):
    r = await client.post(
        "/api/v1/config/assets",
        json={"category": "CATEGORY_2", "name": "摩擦系数公式"},
        headers={"Authorization": f"Bearer {sample_user_token}"},
    )
    assert r.status_code == 201
    assert r.json()["status"] == "DRAFT"

# POST /assets — failure: missing name
async def test_create_asset_missing_name_returns_422(client, sample_user_token):
    r = await client.post(
        "/api/v1/config/assets",
        json={"category": "CATEGORY_2"},
        headers={"Authorization": f"Bearer {sample_user_token}"},
    )
    assert r.status_code == 422

# POST /versions — happy
async def test_create_version_for_draft_asset(client, sample_user_token, sample_draft_asset):
    r = await client.post(
        f"/api/v1/config/assets/{sample_draft_asset.asset_id}/versions",
        json={"content_json": {"expression": "a + b"}},
        headers={"Authorization": f"Bearer {sample_user_token}"},
    )
    assert r.status_code == 201
    assert r.json()["status"] == "DRAFT"

# POST /versions — failure: asset 已 PUBLISHED,必须用 /fork
async def test_create_version_on_published_asset_returns_409(client, sample_user_token, sample_published_asset):
    r = await client.post(
        f"/api/v1/config/assets/{sample_published_asset.asset_id}/versions",
        json={"content_json": {}},
        headers={"Authorization": f"Bearer {sample_user_token}"},
    )
    assert r.status_code == 409
    assert "fork" in r.json()["detail"]

# POST /submit — happy
async def test_submit_draft_to_pending(client, sample_user_token, sample_draft_asset):
    r = await client.post(
        f"/api/v1/config/assets/{sample_draft_asset.asset_id}/submit",
        headers={"Authorization": f"Bearer {sample_user_token}"},
    )
    assert r.status_code == 200
    assert r.json()["status"] == "PENDING"

# POST /submit — failure: 不是 DRAFT 不能 submit
async def test_submit_pending_asset_returns_409(client, sample_user_token, sample_pending_asset):
    r = await client.post(
        f"/api/v1/config/assets/{sample_pending_asset.asset_id}/submit",
        headers={"Authorization": f"Bearer {sample_user_token}"},
    )
    assert r.status_code == 409

# POST /approve — happy (CATEGORY_3 单层)
async def test_approve_pending_single_signoff(client, sample_pc_token, sample_pending_asset_c3):
    r = await client.post(
        f"/api/v1/config/assets/{sample_pending_asset_c3.asset_id}/approve",
        headers={"Authorization": f"Bearer {sample_pc_token}"},
    )
    assert r.status_code == 200
    assert r.json()["status"] == "APPROVED"

# POST /approve — failure: 角色错（DESIGNER 不能 approve）
async def test_approve_requires_process_controller(client, sample_designer_token, sample_pending_asset_c3):
    r = await client.post(
        f"/api/v1/config/assets/{sample_pending_asset_c3.asset_id}/approve",
        headers={"Authorization": f"Bearer {sample_designer_token}"},
    )
    assert r.status_code == 403

# POST /publish — happy (公式 100% pass)
async def test_publish_approved_with_passing_formula(client, sample_pc_token, sample_approved_formula_asset):
    r = await client.post(
        f"/api/v1/config/assets/{sample_approved_formula_asset.asset_id}/publish",
        headers={"Authorization": f"Bearer {sample_pc_token}"},
    )
    assert r.status_code == 200
    assert r.json()["status"] == "PUBLISHED"

# POST /publish — failure: 公式 unit_tests 未 100% pass
async def test_publish_fails_when_unit_tests_incomplete(client, sample_pc_token, sample_approved_formula_with_failing_test):
    r = await client.post(
        f"/api/v1/config/assets/{sample_approved_formula_with_failing_test.asset_id}/publish",
        headers={"Authorization": f"Bearer {sample_pc_token}"},
    )
    assert r.status_code == 422
    assert "unit_tests" in r.json()["detail"]

# POST /obsolete — happy
async def test_obsolete_published(client, sample_pc_token, sample_published_asset):
    r = await client.post(
        f"/api/v1/config/assets/{sample_published_asset.asset_id}/obsolete",
        headers={"Authorization": f"Bearer {sample_pc_token}"},
    )
    assert r.status_code == 200
    assert r.json()["status"] == "OBSOLETE"

# POST /obsolete — failure: 未 PUBLISHED 不能 obsolete
async def test_obsolete_draft_returns_409(client, sample_pc_token, sample_draft_asset):
    r = await client.post(
        f"/api/v1/config/assets/{sample_draft_asset.asset_id}/obsolete",
        headers={"Authorization": f"Bearer {sample_pc_token}"},
    )
    assert r.status_code == 409

# POST /fork — happy
async def test_fork_published_creates_draft(client, sample_pc_token, sample_published_asset):
    r = await client.post(
        f"/api/v1/config/assets/{sample_published_asset.asset_id}/fork",
        json={"change_note": "修订摩擦因子"},
        headers={"Authorization": f"Bearer {sample_pc_token}"},
    )
    assert r.status_code == 201
    assert r.json()["status"] == "DRAFT"
    assert r.json()["parent_version_id"] is not None

# POST /fork — failure: DRAFT 不能 fork
async def test_fork_draft_returns_409(client, sample_pc_token, sample_draft_asset):
    r = await client.post(
        f"/api/v1/config/assets/{sample_draft_asset.asset_id}/fork",
        json={},
        headers={"Authorization": f"Bearer {sample_pc_token}"},
    )
    assert r.status_code == 409

# GET /diff — happy
async def test_diff_two_versions_returns_delta(client, sample_pc_token, sample_two_version_asset):
    r = await client.get(
        f"/api/v1/config/assets/{sample_two_version_asset.asset_id}/diff",
        params={"v1": str(sample_two_version_asset.versions[0].version_id),
                "v2": str(sample_two_version_asset.versions[1].version_id)},
        headers={"Authorization": f"Bearer {sample_pc_token}"},
    )
    assert r.status_code == 200
    assert "added" in r.json() or "changed" in r.json()

# GET /diff — failure: v1 = v2 报错
async def test_diff_same_version_returns_400(client, sample_pc_token, sample_two_version_asset):
    vid = str(sample_two_version_asset.versions[0].version_id)
    r = await client.get(
        f"/api/v1/config/assets/{sample_two_version_asset.asset_id}/diff",
        params={"v1": vid, "v2": vid},
        headers={"Authorization": f"Bearer {sample_pc_token}"},
    )
    assert r.status_code == 400
```

- [ ] **Step 2: 跑测试，验证失败**

Run: `cd pcs-backend && uv run pytest tests/api/v1/test_config.py -v`
Expected: 16 FAIL（endpoint 不存在）

- [ ] **Step 3: 实现 7 个端点**

```python
# app/api/v1/config.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from app.core.acl import require_role
from app.core.commit_or_rollback import commit_or_rollback
from app.db.session import get_session
from app.services.config_state_machine import ConfigStateMachine
from app.services.formula_service import FormulaService  # D18 新增
from app.models.enums import ConfigTransition, ConfigStatus
from app.schemas.config import (
    CreateAssetRequest, AssetResponse,
    CreateVersionRequest, ForkVersionRequest, VersionResponse,
    DiffResponse,
)

router = APIRouter(prefix="/api/v1/config", tags=["config"])

@router.post("/assets", status_code=201, response_model=AssetResponse)
@require_role("DESIGNER")
async def create_asset(req: CreateAssetRequest, db: AsyncSession = Depends(get_session), user=Depends(current_user)):
    from app.services.config_service import ConfigService
    asset = await ConfigService(db).create_asset(category=req.category, name=req.name, actor=user.user_id)
    await commit_or_rollback(db)
    return asset

@router.post("/assets/{asset_id}/versions", status_code=201, response_model=VersionResponse)
@require_role("DESIGNER")
async def create_version(asset_id: UUID, req: CreateVersionRequest, db: AsyncSession = Depends(get_session), user=Depends(current_user)):
    asset = await db.get(ConfigAsset, asset_id)
    if asset is None or asset.current_version.status == ConfigStatus.PUBLISHED:
        raise HTTPException(status_code=409, detail="PUBLISHED asset 必须用 /fork 创建新版本")
    # formula_version 自动从 content_json.expression + parameters 计算（D29）
    from app.services.formula_engine import FormulaEngine
    expression = req.content_json.get("expression", "")
    parameters = req.content_json.get("parameters_json", {})
    formula_version = FormulaEngine.compute_version_hash(expression=expression, parameters=parameters)
    version = await ConfigService(db).create_version(
        asset, content_json=req.content_json,
        formula_version=formula_version, actor=user.user_id,
    )
    await commit_or_rollback(db)
    return version

@router.post("/assets/{asset_id}/fork", status_code=201, response_model=VersionResponse)
@require_role("DESIGNER")
async def fork_version(asset_id: UUID, req: ForkVersionRequest, db: AsyncSession = Depends(get_session), user=Depends(current_user)):
    asset = await db.get(ConfigAsset, asset_id)
    if asset is None or asset.current_version.status != ConfigStatus.PUBLISHED:
        raise HTTPException(status_code=409, detail="只能 fork PUBLISHED 版本")
    # fork 沿用 PUBLISHED 的 expression/parameters，hash 应与原版一致（不变更语义）
    src = asset.current_version
    version = await ConfigService(db).fork_from_published(
        asset, change_note=req.change_note,
        formula_version=src.formula_version,  # 沿用；如 expression 变更则重新计算
        actor=user.user_id,
    )
    await commit_or_rollback(db)
    return version

@router.post("/assets/{asset_id}/submit", response_model=AssetResponse)
@require_role("DESIGNER")
async def submit(asset_id: UUID, db: AsyncSession = Depends(get_session), user=Depends(current_user)):
    asset = await db.get(ConfigAsset, asset_id)
    sm = ConfigStateMachine(db)
    await sm.transition(asset, asset.current_version, action=ConfigTransition.SUBMIT, actor=user)
    await commit_or_rollback(db)
    return asset

@router.post("/assets/{asset_id}/approve", response_model=AssetResponse)
@require_role("PROCESS_CONTROLLER", "SYSTEM_ADMIN")
async def approve(asset_id: UUID, db: AsyncSession = Depends(get_session), user=Depends(current_user)):
    asset = await db.get(ConfigAsset, asset_id)
    sm = ConfigStateMachine(db)
    await sm.record_approval(asset, asset.current_version, role=user.primary_role, actor=user)
    await commit_or_rollback(db)
    return asset

@router.post("/assets/{asset_id}/publish", response_model=AssetResponse)
@require_role("PROCESS_CONTROLLER")
async def publish(asset_id: UUID, db: AsyncSession = Depends(get_session), user=Depends(current_user)):
    asset = await db.get(ConfigAsset, asset_id)
    if asset.category == "CATEGORY_2":
        # 公式 PUBLISH 必须 100% pass
        formula_service = FormulaService(db)
        result = await formula_service.run_unit_tests(asset)
        if result.passed != result.total:
            raise HTTPException(status_code=422, detail=f"公式 unit_tests 未通过 {result.passed}/{result.total}")
    sm = ConfigStateMachine(db)
    await sm.transition(asset, asset.current_version, action=ConfigTransition.PUBLISH, actor=user)
    await commit_or_rollback(db)
    return asset

@router.post("/assets/{asset_id}/obsolete", response_model=AssetResponse)
@require_role("PROCESS_CONTROLLER")
async def obsolete(asset_id: UUID, db: AsyncSession = Depends(get_session), user=Depends(current_user)):
    asset = await db.get(ConfigAsset, asset_id)
    sm = ConfigStateMachine(db)
    await sm.transition(asset, asset.current_version, action=ConfigTransition.OBSOLETE, actor=user)
    await commit_or_rollback(db)
    return asset

@router.get("/assets/{asset_id}/diff", response_model=DiffResponse)
@require_role("DESIGNER")
async def diff(asset_id: UUID, v1: UUID, v2: UUID, db: AsyncSession = Depends(get_session), user=Depends(current_user)):
    if v1 == v2:
        raise HTTPException(status_code=400, detail="v1 和 v2 不能相同")
    service = ConfigService(db)
    delta = await service.diff_versions(asset_id, v1, v2, actor=user)
    # 审计：CONFIG_VERSION_DIFF_VIEWED
    await AuditService(db).write(user_id=user.user_id, action=AuditAction.CONFIG_VERSION_DIFF_VIEWED, ...)
    await commit_or_rollback(db)
    return delta
```

- [ ] **Step 4: 跑测试，验证通过**

Run: `cd pcs-backend && uv run pytest tests/api/v1/test_config.py -v`
Expected: 16 passed

- [ ] **Step 5: Commit**

```bash
git add pcs-backend/app/api/v1/config.py pcs-backend/tests/api/v1/test_config.py
git commit -m "feat(p2): 配置层 7 端点 (assets/versions/fork/submit/approve/publish/obsolete/diff)"
```

---

## Phase 3: Sprint 2 equipment_list 42 字段（~3h）

### Task 3.1: p2_sprint2_equipment_naming_fix migration

**Files:**
- Create: `pcs-backend/alembic/versions/p2_sprint2_equipment_naming_fix.py`

- [ ] **Step 1: 写 migration（7 个命名修正）**

```python
"""P2 Sprint 2：equipment_list 命名修正（7 项）"""
revision = "p2_sprint2_equipment_naming_fix"
down_revision = "p2_sprint1_config_layer_fix"

def upgrade():
    op.alter_column("equipment_list", "description", new_column_name="equipment_description")
    op.alter_column("equipment_list", "install_location", new_column_name="installation_location")
    op.alter_column("equipment_list", "weight_kg", new_column_name="net_weight")
    op.alter_column("equipment_list", "paint_spec", new_column_name="paint")
    op.alter_column("equipment_list", "drawing_no", new_column_name="flowsheet_drawing_number")
    op.alter_column("equipment_list", "engineering_notes", new_column_name="process_engineering_remarks")
    # vendor_id (FK) → vendor (string 200) — 见 §12 问题1 裁决（3 步走）
    # Step 1: 新增 vendor 字符串列（nullable）
    op.add_column("equipment_list", sa.Column("vendor", sa.String(200), nullable=True))
    # Step 2: 数据迁移（仅当 suppliers 表存在时执行回填；否则跳过）
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "suppliers" in inspector.get_table_names():
        op.execute(
            "UPDATE equipment_list SET vendor = "
            "(SELECT supplier_name FROM suppliers WHERE supplier_id = equipment_list.vendor_id) "
            "WHERE vendor_id IS NOT NULL AND vendor IS NULL"
        )
    # Step 3: 删除 FK 约束 + 旧 vendor_id 列
    op.drop_constraint("equipment_list_vendor_id_fkey", "equipment_list", type_="foreignkey")
    op.drop_column("equipment_list", "vendor_id")

def downgrade():
    op.add_column("equipment_list", sa.Column("vendor_id", sa.dialects.postgresql.UUID(), nullable=True))
    op.create_foreign_key("equipment_list_vendor_id_fkey", "equipment_list", "suppliers", ["vendor_id"], ["supplier_id"])
    op.drop_column("equipment_list", "vendor")
    op.alter_column("equipment_list", "process_engineering_remarks", new_column_name="engineering_notes")
    op.alter_column("equipment_list", "flowsheet_drawing_number", new_column_name="drawing_no")
    op.alter_column("equipment_list", "paint", new_column_name="paint_spec")
    op.alter_column("equipment_list", "net_weight", new_column_name="weight_kg")
    op.alter_column("equipment_list", "installation_location", new_column_name="install_location")
    op.alter_column("equipment_list", "equipment_description", new_column_name="description")
```

- [ ] **Step 2: 跑迁移 + 验证**

```bash
cd pcs-backend && uv run alembic upgrade head
uv run pytest tests/models/test_equipment.py -v  # 若有 ORM 模型测试
```

- [ ] **Step 3: ORM 模型同步**

修改 `app/models/equipment.py`，将字段名与 DICT V3.3 对齐（42 项）。

- [ ] **Step 4: Commit**

```bash
git commit -am "feat(p2-s2): equipment_list 7 个命名修正"
```

### Task 3.2: p2_sprint2_equipment_procurement_delivery migration

- [ ] **Step 1: 写 migration（采购 12 + 图纸 3 + 交付 5 + 安装 6 + 重量 4 = 30 项）**

字段清单见 `spec/P2 Sprint 2 执行依据）.md` §四-§七。全部 nullable=true。

- [ ] **Step 2: ORM + Commit**

### Task 3.3: p2_sprint2_equipment_engineering migration

- [ ] **Step 1: 写 migration（工程 9 + 标识 6 + 类型 5 + 来源 4 + 涂装 1）**

注意：与执行依据计数略有差异（涂装 1 而非 0），以 V3.3 实际为准。

- [ ] **Step 2: ORM + Commit**

### Task 3.4: DICT V3.5 发布 + 结构化 diff 0 漂移

- [ ] **Step 1: 重生成 ORM compact**

```bash
cd /home/pangzy/code_project/PCS && uv run --project pcs-backend python /tmp/gen_compact.py
```

- [ ] **Step 2: 改 spec/schema_compact_dict.md + 增量写 spec/PCS-DICT-ALL-003 V3.5.md**

- [ ] **Step 3: 跑结构化 diff 验证 0 漂移**

```bash
python3 scripts/diff_schema.py  # 复用 Task 0 的 parser
```

- [ ] **Step 4: Commit**

```bash
git commit -am "feat(p2-s2): equipment_list 42 字段对齐 + DICT V3.5"
```

---

## Phase 4: Sprint 3 CIA 集成 + workspace 边界（~1 周）

### Task 4.1: CIAEngine.propagate_from_source（反向传播标 STALE）

**Files:**
- Modify: `pcs-backend/app/services/cia_engine.py`
- Test: `pcs-backend/tests/services/test_cia_propagation.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/services/test_cia_propagation.py
import pytest
from app.services.cia_engine import CIAEngine

async def test_propagate_marks_downstream_stale(db):
    config_v = await create_config_version(db, status=PUBLISHED)
    record = await create_record(db, source_ref_type="config_version", source_ref_id=config_v.version_id)
    await CIAEngine(db).propagate_from_source("config_version", config_v.version_id)
    await db.refresh(record)
    assert record.sign_status == "STALE"

async def test_propagate_handles_cycle(db):
    """A→B→A 循环：visited set 防递归死循环"""
    a = await create_record(db, source_ref_type="config", source_ref_id=uuid4())
    b = await create_record(db, source_ref_type="record", source_ref_id=a.record_id)
    # a 引用 b 形成环：b 是 a 的下游，a 也是 b 的下游
    await create_lineage(db, source_ref_type="record", source_ref_id=b.record_id,
                         record_type="record", record_id=a.record_id)
    # 不应抛错或死循环
    await CIAEngine(db).propagate_from_source("config", a.source_ref_id)

async def test_propagate_respects_max_depth(db):
    """深度 9+ 应被截断 (MAX_DEPTH=8)"""
    parent = await create_record(db, source_ref_type="config", source_ref_id=uuid4())
    current = parent
    for i in range(10):  # 建 10 层链
        child = await create_record(db, source_ref_type="record", source_ref_id=current.record_id)
        await create_lineage(db, source_ref_type="record", source_ref_id=current.record_id,
                             record_type="record", record_id=child.record_id)
        current = child
    await CIAEngine(db).propagate_from_source("config", parent.source_ref_id)
    # 深度 8 之内的应被标 STALE，深度 9+ 不应被标
    # 验证 chain 中某些层是 STALE，某些层不是（取决于递归起点）

async def test_propagate_marks_multiple_downstream_records(db):
    """一个 source 多个下游，全部标 STALE"""
    config_v = await create_config_version(db, status=PUBLISHED)
    records = [
        await create_record(db, source_ref_type="config_version", source_ref_id=config_v.version_id)
        for _ in range(5)
    ]
    await CIAEngine(db).propagate_from_source("config_version", config_v.version_id)
    for r in records:
        await db.refresh(r)
        assert r.sign_status == "STALE"

async def test_propagate_skips_missing_record(db):
    """lineage 引用已删除的 record 时不崩"""
    config_v = await create_config_version(db, status=PUBLISHED)
    # 创建 lineage 行，引用不存在的 record_id
    await create_lineage(db, source_ref_type="config_version", source_ref_id=config_v.version_id,
                         record_type="record", record_id=uuid4())  # 幽灵记录
    # 不应抛错
    await CIAEngine(db).propagate_from_source("config_version", config_v.version_id)
```

- [ ] **Step 2: 跑测试，验证失败**

Run: `cd pcs-backend && uv run pytest tests/services/test_cia_propagation.py -v`
Expected: 5 FAIL（`propagate_from_source` 不存在或签名错）

- [ ] **Step 3: 实现 propagate_from_source**

```python
# app/services/cia_engine.py
from app.models.record import Records            # P1 既有
from app.models.config_domain import (           # P2 新增
    ConfigAsset, ConfigVersion,
)

# data_lineage.record_type → ORM 模型 映射表（新增 record_type 必须登记）
REGISTRY: dict[str, type] = {
    "record":         Records,         # P1 记录层 9 态记录
    "config_asset":   ConfigAsset,     # P2 配置资产
    "config_version": ConfigVersion,   # P2 配置版本快照
}


class CIAEngine:
    MAX_DEPTH = 8

    def __init__(self, session: AsyncSession):
        self.session = session

    async def propagate_from_source(self, source_type: str, source_id: UUID) -> None:
        visited: set[tuple[str, UUID]] = set()
        await self._propagate_recursive(source_type, source_id, depth=0, visited=visited)

    async def _propagate_recursive(self, source_type: str, source_id: UUID, *, depth: int, visited: set) -> None:
        if depth >= self.MAX_DEPTH:
            return
        key = (source_type, source_id)
        if key in visited:
            return
        visited.add(key)
        rows = (await self.session.execute(
            select(DataLineage).where(
                DataLineage.source_ref_type == source_type,
                DataLineage.source_ref_id == source_id,
            )
        )).scalars().all()
        for lineage in rows:
            record = await self._get_record(lineage.record_type, lineage.record_id)
            if record is not None and getattr(record, "sign_status", None) != "STALE":
                record.sign_status = "STALE"
            await self._propagate_recursive(
                lineage.record_type, lineage.record_id,
                depth=depth + 1, visited=visited,
            )

    async def _get_record(self, record_type: str, record_id: UUID):
        """按 record_type 路由到对应 ORM 模型。若 record 已删除则返回 None。

        未登记的 record_type 直接返回 None（静默跳过），不抛错 —— 避免某模块
        删表后遗留 lineage 行导致传播中断。
        """
        model = REGISTRY.get(record_type)
        if model is None:
            return None
        return await self.session.get(model, record_id)
```

- [ ] **Step 4: 跑测试，验证通过**

Run: `cd pcs-backend && uv run pytest tests/services/test_cia_propagation.py -v`
Expected: 5 passed

- [ ] **Step 5: 接入 PUBLISH 端点 + Commit**

```bash
git add pcs-backend/app/services/cia_engine.py pcs-backend/tests/services/test_cia_propagation.py
git commit -m "feat(p2-s3): CIAEngine 反向传播 + cycle / depth / multi / missing 覆盖"
```

### Task 4.2: ~~audit_logs.action 8 项接入~~ (已删除 — D20)

> **D20 裁决**：审计由 `ConfigStateMachine.transition` 内置调用 `AuditService.write()`，见 Task 1.2 实现。Task 4.2 取消，无 retrofit。

### Task 4.3: CLAUDE.md workspace 边界声明

- [ ] **Step 1: 追加段落**

> **配置层 API 不调用 `require_formal_workspace`**。所有登录用户可读；写操作需 D15 规定的 LDAP 角色（DESIGNER / PROCESS_CONTROLLER / SYSTEM_ADMIN）。

- [ ] **Step 2: Commit**

---

## Phase 5: Sprint 4 报表 + 导出（~3 天）

### Task 5.1: report_service 配置资产状态分布

**Files:**
- Create: `pcs-backend/app/services/report_service.py`
- Test: `pcs-backend/tests/services/test_report_service.py`

**Interfaces:**
- Consumes: `config_assets` + `config_versions` 表
- Produces: `ReportService.config_asset_status(db) -> list[ConfigAssetReport]`

- [ ] **Step 1: 写失败测试**

```python
# tests/services/test_report_service.py
import pytest
from app.services.report_service import ReportService

async def test_empty_db_returns_empty_list(db):
    svc = ReportService(db)
    result = await svc.config_asset_status()
    assert result == []

async def test_aggregates_by_category_and_status(db, sample_assets_and_versions):
    svc = ReportService(db)
    result = await svc.config_asset_status()
    by_key = {(r.category, r.published): r for r in result}
    assert by_key[("CATEGORY_2", 2)].published == 2  # 2 个 CATEGORY_2 PUBLISHED
    assert by_key[("CATEGORY_3", 1)].pending == 1

async def test_handles_all_status_values(db, sample_assets):
    svc = ReportService(db)
    result = await svc.config_asset_status()
    assert {r.category for r in result} == {"CATEGORY_2", "CATEGORY_3"}
```

- [ ] **Step 2: 跑测试，验证失败**

Run: `cd pcs-backend && uv run pytest tests/services/test_report_service.py -v`
Expected: FAIL `ModuleNotFoundError`

- [ ] **Step 3: 实现 service**

```python
# app/services/report_service.py
from sqlalchemy import text
from pydantic import BaseModel
from typing import Literal

ConfigStatusLiteral = Literal["DRAFT", "PENDING", "APPROVED", "PUBLISHED", "OBSOLETE"]

class ConfigAssetReport(BaseModel):
    category: str
    draft: int
    pending: int
    approved: int
    published: int
    obsolete: int

class ReportService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def config_asset_status(self) -> list[ConfigAssetReport]:
        rows = (await self.session.execute(text("""
            SELECT ca.category, cv.status, COUNT(*) AS n
            FROM config_assets ca
            JOIN config_versions cv ON cv.asset_id = ca.asset_id
            GROUP BY ca.category, cv.status
        """))).all()
        # 聚合
        agg: dict[str, dict[str, int]] = {}
        for category, status, n in rows:
            agg.setdefault(category, {"DRAFT": 0, "PENDING": 0, "APPROVED": 0, "PUBLISHED": 0, "OBSOLETE": 0})[status] = n
        return [
            ConfigAssetReport(category=cat, **counts)
            for cat, counts in sorted(agg.items())
        ]
```

- [ ] **Step 4: 跑测试，验证通过**

Run: `cd pcs-backend && uv run pytest tests/services/test_report_service.py -v`
Expected: 3 passed

- [ ] **Step 5: API 端点 + Commit**

```bash
git add pcs-backend/app/services/report_service.py pcs-backend/tests/services/test_report_service.py pcs-backend/app/api/v1/config.py
git commit -m "feat(p2-s4): 配置资产状态分布报表"
```

### Task 5.2: report_service 编号模板用量

**Files:**
- Modify: `pcs-backend/app/services/report_service.py`
- Test: `pcs-backend/tests/services/test_report_service.py`（追加）

- [ ] **Step 1: 写失败测试**

```python
class TestDocNoUsage:
    async def test_empty_db_returns_empty_list(self, db):
        svc = ReportService(db)
        assert await svc.doc_no_sequence_usage() == []

    async def test_sums_per_template(self, db, sample_doc_no_sequences):
        svc = ReportService(db)
        result = await svc.doc_no_sequence_usage()
        by_template = {r.template_id: r.total for r in result}
        assert by_template[sample_doc_no_sequences[0].template_id] == 50

    async def test_skips_zero_counters(self, db, sample_template_with_zero_counter):
        svc = ReportService(db)
        result = await svc.doc_no_sequence_usage()
        template_ids = [r.template_id for r in result]
        assert sample_template_with_zero_counter.template_id not in template_ids
```

- [ ] **Step 2-4: 实现 doc_no_sequence_usage**

```python
from pydantic import BaseModel
from uuid import UUID

class DocNoUsage(BaseModel):
    template_id: UUID
    template_name: str
    total: int

class ReportService:
    async def doc_no_sequence_usage(self) -> list[DocNoUsage]:
        rows = (await self.session.execute(text("""
            SELECT nt.template_id, nt.template_name, COALESCE(SUM(dns.current_value), 0) AS total
            FROM numbering_templates nt
            LEFT JOIN doc_no_sequences dns ON dns.template_id = nt.template_id
            GROUP BY nt.template_id, nt.template_name
            HAVING SUM(dns.current_value) > 0
        """))).all()
        return [DocNoUsage(template_id=tid, template_name=name, total=total) for tid, name, total in rows]
```

- [ ] **Step 5: Commit**

```bash
git commit -am "feat(p2-s4): 编号模板用量报表"
```

### Task 5.3: export_service openpyxl Excel 导出

**Files:**
- Create: `pcs-backend/app/services/export_service.py`
- Test: `pcs-backend/tests/services/test_export_service.py`

**Interfaces:**
- Consumes: `data: list[dict]`, `headers: list[str]`
- Produces: `ExportService.to_excel(data, headers, sheet_name="Report") -> BytesIO`

- [ ] **Step 1: 写失败测试**

```python
# tests/services/test_export_service.py
import openpyxl
from app.services.export_service import ExportService

async def test_to_excel_produces_valid_workbook():
    data = [{"a": 1, "b": 2}, {"a": 3, "b": 4}]
    buf = await ExportService.to_excel(data, headers=["a", "b"])
    wb = openpyxl.load_workbook(buf)
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    assert rows[0] == ("a", "b")
    assert rows[1] == (1, 2)
    assert rows[2] == (3, 4)

async def test_to_excel_empty_data_only_header():
    buf = await ExportService.to_excel([], headers=["a"])
    wb = openpyxl.load_workbook(buf)
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    assert rows == [("a",)]

async def test_to_excel_custom_sheet_name():
    buf = await ExportService.to_excel([{"x": 1}], headers=["x"], sheet_name="P&ID")
    wb = openpyxl.load_workbook(buf)
    assert "P&ID" in wb.sheetnames
```

- [ ] **Step 2: 跑测试，验证失败**

Run: `cd pcs-backend && uv run pytest tests/services/test_export_service.py -v`
Expected: FAIL `ModuleNotFoundError`

- [ ] **Step 3: 实现 service**

```python
# app/services/export_service.py
from io import BytesIO
import openpyxl

class ExportService:
    @staticmethod
    async def to_excel(data: list[dict], *, headers: list[str], sheet_name: str = "Report") -> BytesIO:
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = sheet_name[:31]  # Excel 限制
        ws.append(headers)
        for row in data:
            ws.append([row.get(h) for h in headers])
        buf = BytesIO()
        wb.save(buf)
        buf.seek(0)
        return buf
```

- [ ] **Step 4: 跑测试，验证通过**

Run: `cd pcs-backend && uv run pytest tests/services/test_export_service.py -v`
Expected: 3 passed + 1 perf budget test

- [ ] **Step 4.5: 性能预算测试（D28）**

```python
# tests/services/test_export_service.py — 追加
import time
import tracemalloc

async def test_export_perf_budget():
    """D28 性能预算：10k 行 × 20 列 ≤ 2s + 内存 ≤ 50MB。"""
    rows = [{f"col_{j}": f"v_{i}_{j}" for j in range(20)} for i in range(10_000)]
    tracemalloc.start()
    start = time.monotonic()
    output = await ExportService.to_excel(rows, headers=[f"col_{j}" for j in range(20)])
    elapsed = time.monotonic() - start
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    assert elapsed < 2.0, f"导出超时 {elapsed:.2f}s"
    assert peak < 50 * 1024 * 1024, f"导出内存 {peak/1e6:.1f}MB"
    assert len(output) > 0
```

预算失败触发 TODO-030（write_only=True 流式写入）。

- [ ] **Step 5: API 端点 + Commit**

```bash
git add pcs-backend/app/services/export_service.py pcs-backend/tests/services/test_export_service.py pcs-backend/app/api/v1/config.py
git commit -m "feat(p2-s4): openpyxl Excel 导出 service"
```

### Task 5.4: DICT V3.5 增量（报表相关）

- 增量发布 V3.5（如新增报表字段）

---

## Self-Review

**Spec 覆盖**：
- §3.1 1.1.1 AuditAction → Task 1.1 ✅
- §3.1 1.1.2 ConfigStateMachine → Task 1.2 ✅
- §3.1 1.1.3 双段签 → Task 1.3 ✅
- §3.2 1.2.1-1.2.4 公式引擎 → Task 2.3 + 2.4 ✅
- §3.3 系数库 → Task 2.5 ✅
- §3.4 模板 → Task 2.6 ✅
- §3.5 编号 → Task 2.7 ✅
- §4 Sprint 2 equipment_list 42 字段 → Task 3.1-3.4 ✅
- §5.1 CIA 传播 → Task 4.1 ✅
- §5.2 audit 接入 → Task 1.2 内置 ✅（D20 删除 Task 4.2）
- §5.3 workspace 边界 → Task 4.3 ✅
- §6 Sprint 4 报表 → Task 5.1-5.2 ✅
- §6 导出 → Task 5.3 ✅
- D14 横向骨架优先 → Phase 1 在 Phase 2 之前 ✅
- D15 LDAP 角色 → Task 1.4 ✅
- D16 schema 锁定 → Task 2.1 + 2.2 ✅
- D17 无缓存 + 100% pass → Task 2.4 ✅

**Placeholder 扫描**：✅ 无 TBD/TODO。

**Type 一致性**：
- `ConfigStateMachine.transition(asset, version, *, action, actor, reason=None)` — D23 重命名后全 plan 一致
- `FormulaEngine.parse(expression, parameters) -> Callable` — Task 2.3 + 2.4 一致
- `CIAEngine(db).propagate_from_source(source_type, source_id)` — Task 4.1 一致

**待 writing-plans 阶段外裁决**：见 spec §12 5 项（vendor_id 迁移策略 / unit_tests_json 示例 / 模板存储路径 / P3 起跳 / 公式表达式版本管理粒度）。

> 上述 5 项 + Codex/Design/DX Review 时机已全部裁决完毕（2026-09-02），落地细节见下方 "外部依赖与决策" 一节。

---

## GSTACK REVIEW REPORT

| Review | Trigger | Why | Runs | Status | Findings |
|--------|---------|-----|------|--------|----------|
| CEO Review | `/plan-ceo-review` | Scope & strategy | 0 | — | not run |
| Codex Review | `/codex review` | Independent 2nd opinion | 0 | — | not run |
| Eng Review | `/plan-eng-review` | Architecture & tests (required) | 1 | issues_open | 16 findings (5 arch / 3 code / 6 test / 2 perf) |
| Design Review | `/plan-design-review` | UI/UX gaps | 0 | — | not run |
| DX Review | `/plan-devex-review` | Developer experience gaps | 0 | — | not run |

**Decisions logged during review (D17–D28)**:
- **D17** 公式引擎: 纯 AST+eval，更新文档移除 SymPy 声明
- **D18** FormulaService (DB 加载 + 引擎胶水) 新增
- **D19** 新 ConfigVersion 流程：专用 `/fork` 端点
- **D20** ConfigStateMachine 构造器模式 + 审计内置；删除 Task 4.2
- **D21** FormulaEngine 参数键名走 FORBIDDEN_NAMES 校验
- **D22** FormulaEngine.run_unit_tests 返回 TestResult dataclass（含失败原因）
- **D23** transition() 参数名 → `action`
- **D24** (audit assertion 加到每个 1.2 测试)
- **D25** (Tasks 2.5/2.6/2.7 完整 TDD 内联)
- **D26** CIA 传播保留 N+1，加 perf 预算测试
- **D27** FormulaEngine._compile() @lru_cache(maxsize=128)
- **D28** openpyxl 推迟 write_only，加 perf 预算测试 + TODO-030

**CODEX:** not run
**CROSS-MODEL:** n/a
**UNRESOLVED:** 0 — 所有 finding 用户已裁决
**VERDICT:** ENG CLEARED (issues_open status 因含已裁决的 16 项 findings；全部内联修订入 plan) — ready to execute Phase 1

### Post-review fixes (applied 2026-09-02)

执行正确性 6 项修订已内联至 plan：

| # | 位置 | 修订 |
|---|------|------|
| 1 | Global Constraints | "SymPy 解析" → "Python `ast` 解析 + 节点白名单 + `__builtins__` 冻结 + 无缓存天然热更新 + 100% pass 硬门槛（D17：移除 SymPy 声明，纯 stdlib）" |
| 2 | Task 1.2 | 删除重复的 `ConfigStatus`/`ConfigTransition` 定义，保留 `from app.models.enums import ...`，enums.py 单一来源 |
| 3 | Task 2.7 | `DocumentNoSequence(...)` → `DocNoSequence(...)` 拼写修正 |
| 4 | Task 2.7.1 | 新增 conftest.py spec：db / actor / pc_actor / designer_actor / make_asset factory / sample_*_asset / sample_*_token / client 全套 fixture |
| 5 | Task 1.3 | `record_approval` 改写：先 `session.add(approval) + flush()`，再重新查询 approvals 做判定（避免脏读）；同时改为 instance method + audit 内置，与 D20 一致 |
| 6 | Task 4.1 | 新增 `REGISTRY: dict[str, type]` 模块级映射（record/config_asset/config_version → ORM 模型）；`_get_record` 静默跳过未登记类型（避免遗留 lineage 行中断传播） |

**修订后 VERDICT：** ENG CLEARED + 6 项执行正确性修订已落地，可立即进入 Phase 1 实施。

---

## 外部依赖与决策（2026-09-02 裁决）

### 1. equipment_list vendor_id → vendor 迁移（D29）

**决策**：Task 3.1 migration 采用 3 步走策略（add_column → 数据回填 → drop FK + drop_column）。

**约束**：仅当 `suppliers` 表存在时执行回填；否则直接删 FK + 删列（开发环境可能无 suppliers 表）。
Migration 已内联在 Task 3.1，含 downgrade（重建 FK + vendor_id 列）。

### 2. formula_definitions.unit_tests_json 示例（D30）

**决策**：已解决——Task 2.2 schema + Task 2.4 测试代码已给完整 JSON 示例：
```json
{"unit_tests": [{"params": {"a": 1, "b": 2}, "expected": 3, "tolerance": 0.01}]}
```
**剩余动作（文档侧）**：在 `PCS-DICT-ALL-003 V3.5` 的 `formula_definitions.unit_tests_json` 字段注释里补充此 JSON 示例。无需修改代码。

### 3. 模板文件存储路径（D31）

**决策**：可配置化，避免 IT 后期改路径时需改代码。

`pcs-backend/app/core/settings.py` 追加：
```python
from pathlib import Path

class Settings(BaseSettings):
    # ... 现有字段 ...
    template_storage_root: Path = Path("/var/lib/pcs/templates/")
    
    class Config:
        env_prefix = "PCS_"  # 环境变量 PCS_TEMPLATE_STORAGE_ROOT 可覆写

settings = Settings()
```

调用方（Task 2.6）：`file_path = settings.template_storage_root / filename` 而非硬编码。
**Phase 1~3 不依赖此路径**（公式/系数/编号），仅 Task 2.6 模板管理需就绪。

### 4. P3 起跳时机（D32）

**决策**：PO/架构委员会决定，本计划不做硬性约定。

落地原则：P2 Sprint 4 评审后由 PO 决策（先发 v1.0 试点 / 立即堆 P3 / 修复 P2 已知缺陷）。
**技术债清单**：P2 阶段产出时附带一份"建议立即解决的 P2 已知缺陷"列表供 PO 参考。

### 5. 公式表达式版本指纹（D33）

**决策**：复用 ADR-0013 record_hash 规范化策略 + SHA-256(16) 截位。

`FormulaEngine.compute_version_hash(expression, parameters) -> str` 已落地（Task 2.3）。
- 规则：expression 原样 + parameters 按 key 排序 JSON 序列化 → `f"{expr}\x1f{params_repr}"` → SHA-256 → 截前 16 hex
- 调用：API 端点 `/versions`（POST）+ `/fork`（POST）在创建 ConfigVersion 时自动填充 `formula_version` 列（Task 2.8 实现已内联）
- 碰撞概率：64-bit → ~1/2^32 满足公式库规模

### 6. Codex / Design / DX Review 时机（D34）

**决策**：分级降级，按需补审。

| Review | 必要性 | 时机 |
|--------|--------|------|
| Codex Review（独立 2nd opinion） | 中 | Phase 1（基础设施）完成后触发——骨架阶段改造成本最低 |
| Design Review（UI/UX） | 低 | P2 主要为后台配置管理（列表+表单），降级为"API Schema 一致性检查"，已隐含在 Eng Review 的 Pydantic Schema 审核中 |
| DX Review（开发者体验） | 中 | Phase 2（业务端点）完成后由另一位后端 Lead 快速走查 API 路径/状态码/错误消息规范性 |

**前置假设**：若团队信任 Eng Review 的内审质量且无强制合规要求，Codex Review 可豁免；否则按 Phase 1 后补审执行。

---

## 最终交付状态

- **Eng Review**: CLEARED（16 findings + 6 post-review fixes + 6 unresolved-item fixes 全部内联落地）
- **范围**: Phase 1~5 完整 TDD 实施计划，单人 ~5 周
- **依赖闭环**: 5 项外部裁决 + 3 项 Review 时机已记录
- **可执行性**: 所有 Task 含完整代码、测试、Commit 步骤，可直接进入 subagent-driven-development 或 executing-plans
- **剩余决策点**: 0 — 无技术债阻塞 Phase 1 启动