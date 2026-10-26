"""签署矩阵服务的守卫（P9A-DLV-007 · SUP-005 · ADR-0008）。

## 为什么这个服务存在

`signature_matrices` 表**恒为 0 行** —— 全仓**没有任何地方创建矩阵** ⇒
变更单（`Deliverable.matrix_id` **NOT NULL** + FK）**建不出来**
⇒ ADR-0047 §① 的第三个观测写入点（CHANGE_NOTICE）**没有可达路径**
（= TODO-057 卡住的地方）。

⇒ 本服务负责两件事：**解析** `steps_json`（唯一解析口）+ **取得**矩阵
（惰性建内置模板 + 项目绑定）。

## 这组测试钉住的失败模式

| # | 失败模式 | 期望 |
|---|---|---|
| RF-1 | 坏数据被**静默吞** ⇒ 变更单按 0 步走 | 坏项跳过；**全部非法** ⇒ 422 `SIGNATURE_MATRIX_INVALID` |
| RF-2 | **两份解析** ⇒ 签署路径与变更单路径给出不同的步骤 | `parse_steps` 是唯一解析口 |
| RF-3 | 惰性建行**不幂等** ⇒ 每次建单都新建矩阵 | 同项目同模块只建一次 |
| RF-4 | **跨项目串矩阵** | 模板全局、绑定按项目 |
"""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import func, select

from app.models.deliverable import (
    ProjectSignatureMatrixBinding,
    SignatureMatrix,
)
from app.services.deliverable_service import DeliverableService
from app.services.exceptions import PcsError
from app.services.signature_matrix_service import (
    SignatureMatrixService,
)


def _matrix(steps: list) -> SignatureMatrix:
    """构造一个**内存里**的矩阵（不落库）—— 只测解析。"""
    return SignatureMatrix(
        matrix_id=uuid.uuid4(),
        matrix_name="T",
        module="*",
        doc_type="X",
        version_purpose="ISSUED_FOR_DESIGN",
        steps_json=steps,
        status="ACTIVE",
    )


# ---------------------------------------------------------------------------
# parse_steps —— 排序 / 空 / 坏数据 / 缺省
# ---------------------------------------------------------------------------


def test_parse_steps_sorts_by_step_order():
    """⚠️ `steps_json` 的键序**不保证** ⇒ 必须显式排序（签署推进依赖顺序）。"""
    matrix = _matrix(
        [
            {"step_order": 3, "sign_role": "APPROVER"},
            {"step_order": 1, "sign_role": "CHECKER"},
            {"step_order": 2, "sign_role": "REVIEWER"},
        ]
    )
    steps = SignatureMatrixService.parse_steps(matrix)
    assert [s.step_order for s in steps] == [1, 2, 3]
    assert [s.sign_role for s in steps] == ["CHECKER", "REVIEWER", "APPROVER"]


def test_parse_steps_empty_matrix():
    """矩阵缺失 / 步骤为空 ⇒ 空列表（调用方按越界处理）。"""
    assert SignatureMatrixService.parse_steps(None) == []
    assert SignatureMatrixService.parse_steps(_matrix([])) == []


def test_parse_steps_skips_broken_items():
    """坏项**跳过**，好项保留（RF-1）。

    坏项有三种：`step_order` 不是 int、`sign_role` 不是非空字符串、不是 dict。
    ⚠️ `isinstance(True, int)` 为 True ⇒ `bool` 的 `step_order` 也算坏。
    """
    matrix = _matrix(
        [
            {"step_order": 1, "sign_role": "CHECKER"},
            {"step_order": "2", "sign_role": "REVIEWER"},  # 非 int
            {"sign_role": "REVIEWER"},  # 缺 step_order
            {"step_order": 3, "sign_role": ""},  # sign_role 空
            {"step_order": True, "sign_role": "X"},  # bool 不是合法序号
            "not-a-dict",
            {"step_order": 4, "sign_role": "APPROVER"},
        ]
    )
    steps = SignatureMatrixService.parse_steps(matrix)
    assert [(s.step_order, s.sign_role) for s in steps] == [
        (1, "CHECKER"),
        (4, "APPROVER"),
    ]


def test_parse_steps_all_broken_raises():
    """⚠️ **全部非法** ⇒ 422 明说（不能当空矩阵 ⇒ 否则变更单按 0 步走）。"""
    matrix = _matrix([{"step_order": "x"}, "nope"])
    with pytest.raises(PcsError) as exc:
        SignatureMatrixService.parse_steps(matrix)
    assert exc.value.code == "SIGNATURE_MATRIX_INVALID"
    assert exc.value.status == 422


def test_parse_steps_defaults():
    """缺省值：`required=True`、`can_self_check=True`（与 `sign_step` 既有默认一致）。"""
    matrix = _matrix([{"step_order": 1, "sign_role": "CHECKER"}])
    step = SignatureMatrixService.parse_steps(matrix)[0]
    assert step.required is True
    # ⚠️ 与 `deliverable_service.sign_step` 的 `step.get("can_self_check", True)` 一致
    assert step.can_self_check is True
    assert step.can_skip is False


def test_parse_steps_strips_sign_role():
    """⚠️ `sign_role` 前后空白**必须剥掉**。

    判空用 `.strip()` 却存原值 ⇒ 矩阵里写 `" CHECKER "` ⇒ 校验通过、
    存进去带空格 ⇒ `sign_step` 拿它和 actor 的角色比 ⇒ 403
    `SIGN_STEP_ROLE_MISMATCH`，而用户收到的消息是「第 1 步要求角色
    『 CHECKER 』，当前角色 CHECKER」—— 一个带空格的自己。
    """
    matrix = _matrix([{"step_order": 1, "sign_role": " CHECKER "}])
    step = SignatureMatrixService.parse_steps(matrix)[0]
    assert step.sign_role == "CHECKER"


def test_parse_steps_logs_skipped_count(caplog):
    """⚠️ **部分**跳过必须**可观测**（计划 R-2）。

    全非法时报 422 是「明说」；部分跳过没有报错，只能靠日志 ——
    否则「矩阵少了一步」这件事在生产里**无人知晓**，而签署少一道校审
    比报错更危险。
    """
    matrix = _matrix(
        [
            {"step_order": 1, "sign_role": "CHECKER"},
            {"step_order": "2", "sign_role": "REVIEWER"},
            {"sign_role": "REVIEWER"},
        ]
    )
    with caplog.at_level("WARNING", logger="app.services.signature_matrix_service"):
        SignatureMatrixService.parse_steps(matrix)
    assert any("2" in r.getMessage() for r in caplog.records), (
        "跳过项数必须出现在日志里"
    )


# ---------------------------------------------------------------------------
# ensure_change_notice_matrix —— 惰性建行 + 幂等 + 项目隔离
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ensure_creates_builtin_template_and_binding(db, project_id):
    """项目没有矩阵 ⇒ 建**内置模板**（3 级）+ 建**项目绑定**。"""
    matrix = await SignatureMatrixService.ensure_change_notice_matrix(
        db, project_id=project_id
    )
    assert matrix.matrix_name == "CHANGE_NOTICE_3_LEVEL"
    assert matrix.module == "CHANGE_NOTICE"
    assert matrix.status == "ACTIVE"
    # 3 级：校核 / 审核 / 审定（ADR-0008）
    roles = [s["sign_role"] for s in matrix.steps_json]
    assert roles == ["CHECKER", "REVIEWER", "APPROVER"]

    bindings = (
        await db.execute(
            select(ProjectSignatureMatrixBinding).where(
                ProjectSignatureMatrixBinding.project_id == project_id
            )
        )
    ).scalars().all()
    assert len(bindings) == 1
    assert bindings[0].matrix_id == matrix.matrix_id
    assert bindings[0].module == "CHANGE_NOTICE"


@pytest.mark.asyncio
async def test_ensure_is_idempotent(db, project_id):
    """⚠️ 再调一次**不重复建**（RF-3）：模板数与绑定数都不变。"""
    first = await SignatureMatrixService.ensure_change_notice_matrix(
        db, project_id=project_id
    )
    second = await SignatureMatrixService.ensure_change_notice_matrix(
        db, project_id=project_id
    )
    assert first.matrix_id == second.matrix_id

    matrices = (await db.execute(select(func.count()).select_from(SignatureMatrix))).scalar()
    bindings = (
        await db.execute(
            select(func.count()).select_from(ProjectSignatureMatrixBinding)
        )
    ).scalar()
    assert matrices == 1
    assert bindings == 1


@pytest.mark.asyncio
async def test_ensure_is_project_scoped(db, project_id, db_session):
    """⚠️ 两个项目 ⇒ **同一个全局模板**，但**各有一份绑定**（RF-4）。"""
    from app.services.user_project_service import UserProjectService

    other_user = uuid.uuid4()
    other_project = uuid.uuid4()
    await UserProjectService.grant_project_access(
        db_session,
        user_id=other_user,
        project_id=other_project,
        role_in_project="DESIGNER",
    )

    a = await SignatureMatrixService.ensure_change_notice_matrix(
        db, project_id=project_id
    )
    b = await SignatureMatrixService.ensure_change_notice_matrix(
        db, project_id=other_project
    )
    # 模板是全局的（同一个）
    assert a.matrix_id == b.matrix_id
    # 绑定是项目的（各一份）
    rows = (
        await db.execute(select(ProjectSignatureMatrixBinding))
    ).scalars().all()
    assert {r.project_id for r in rows} == {project_id, other_project}


# ---------------------------------------------------------------------------
# DeliverableService._matrix_steps —— 唯一解析口的守卫（RF-2）
# ---------------------------------------------------------------------------


def test_deliverable_matrix_steps_delegates_to_parse_steps():
    """签署路径必须走**同一个**解析口（RF-2）。

    两份解析 ⇒ 签署路径与变更单路径对同一份 `steps_json` 给出不同的步骤 ⇒
    「谁该签这一步」在不同入口下不一致。

    断言的是**解析后的形状**（有序 + 缺省补齐），不是内部调用 ——
    因为「唯一解析口」是结构约束，能被外部观察到的等价物是
    「两条路径给出同样的步骤」。
    """
    matrix = _matrix(
        [
            {"step_order": 2, "sign_role": "REVIEWER"},
            {"step_order": 1, "sign_role": "CHECKER"},
        ]
    )
    steps = DeliverableService._matrix_steps(matrix)
    assert [s["step_order"] for s in steps] == [1, 2]
    assert [s["sign_role"] for s in steps] == ["CHECKER", "REVIEWER"]
    # 缺省补齐（与 `sign_step` 的既有默认一致）
    assert steps[0]["required"] is True
    assert steps[0]["can_self_check"] is True
    assert steps[0]["can_skip"] is False


def test_deliverable_matrix_steps_all_broken_raises():
    """⚠️ 全部非法 ⇒ 422 明说（不能当空矩阵 ⇒ 否则签署按 0 步走）。

    签署路径与变更单路径**同一条**判据 ⇒ 同一份坏配置在两处都报同一个错。
    """
    matrix = _matrix([{"step_order": "x"}, "nope"])
    with pytest.raises(PcsError) as exc:
        DeliverableService._matrix_steps(matrix)
    assert exc.value.code == "SIGNATURE_MATRIX_INVALID"
    assert exc.value.status == 422


def test_deliverable_matrix_steps_empty_matrix_is_empty_list():
    """空矩阵（无步骤）⇒ 空列表，**不报错** —— 越界由调用方按 404 处理。"""
    assert DeliverableService._matrix_steps(None) == []
    assert DeliverableService._matrix_steps(_matrix([])) == []


@pytest.mark.asyncio
async def test_ensure_binding_recovers_from_concurrent_insert(db, project_id, monkeypatch):
    """⚠️ 并发建绑定 ⇒ 唯一约束撞车 ⇒ **重读**那一行（不是 500）。

    没有兜底的话：同一项目同一模块绑到两个矩阵 ⇒ 之后每次解析绑定都
    `MultipleResultsFound` ⇒ 该项目的变更单路径**永久 500**（bug-2052）。

    竞态用「把 `_ensure_binding` 里那次查藏起来」模拟：查的时候没有，
    插的时候另一个事务已经插好了。
    """
    from sqlalchemy import insert

    matrix = SignatureMatrix(
        matrix_name="CHANGE_NOTICE_3_LEVEL",
        module="CHANGE_NOTICE",
        doc_type="CHANGE_NOTICE",
        version_purpose="ISSUED_FOR_CHANGE",
        steps_json=[{"step_order": 1, "sign_role": "CHECKER"}],
        status="ACTIVE",
    )
    db.add(matrix)
    await db.flush()

    real_execute = db.execute
    seen = {"n": 0}
    other_id: list[uuid.UUID] = []

    class _Empty:
        def scalar_one_or_none(self):
            return None

    async def _execute(stmt, *args, **kwargs):
        if "project_signature_matrix_bindings" in str(stmt):
            seen["n"] += 1
            if seen["n"] == 1:
                # 竞态窗口：查的时候「还没有」，但**另一个事务已经插好了**
                other = ProjectSignatureMatrixBinding(
                    project_id=project_id,
                    module="CHANGE_NOTICE",
                    matrix_id=matrix.matrix_id,
                )
                db.add(other)
                await db.flush()
                other_id.append(other.binding_id)
                return _Empty()
        return await real_execute(stmt, *args, **kwargs)

    monkeypatch.setattr(db, "execute", _execute)

    result = await SignatureMatrixService.ensure_change_notice_matrix(
        db, project_id=project_id
    )

    assert result.matrix_id == matrix.matrix_id
    rows = (
        await db.execute(select(ProjectSignatureMatrixBinding))
    ).scalars().all()
    assert len(rows) == 1, "撞约束后必须复用已存在的那行，而不是再建一行"
    assert rows[0].binding_id == other_id[0]
