"""P9A 迁移基座的 schema 断言 —— workflow_progress（SPEC P9A-OBS-001 + ADR-0047）。

⚠️ 迁移与 ORM 漂移时，**单测照绿、真库会炸**（CLAUDE.md 漂移盲区）。
本文件断言的是**元数据与迁移产物一致**，不是运行时行为。

## 为什么是 10 个业务字段而不是 SPEC P9-OPEN-007 写的 8 个

SPEC P9-OPEN-007 列的 8 个字段（`workflow_id / step_no / step_name / step_status /
started_at / completed_at / assignee / result_hash`）**少两列，而这两列都被 P9A 自己
的需求强制要求**：

- `workflow_type` —— P9A-OBS-002 的读 API 是 `GET /workflow-progress/{workflow_type}/
  {workflow_id}`（B5）；ADR-0047 §① 的三个写入点（签署 / 变更单 / 代录批准）
  也靠它区分。缺了它，一次签署和一次代录的进度行无法分辨。
- `project_id` —— P9A-OBS-003 的读 API 要按项目鉴权（越权 404），而 `workflow_id`
  是多态的（版本 ID / 交付物 ID），无法 join 回项目。

⇒ 本测试断言 10 个业务列 + `progress_id` 主键 + TimestampMixin 三列。
差异已登记到 `TODOS.md`（未回改 SPEC —— SPEC 是绑定权威，改动要重走 §7.2 验收）。

## 另一个必须钉住的：`todos` 表**不建**

ADR-0049 §② 裁决待办走**实时计算**，不建表。建了就多一个真相源，
而且它的生命周期会与计算逻辑漂移 —— 这是 TODO-047 同构的坑。
"""
import pytest

import app.models  # noqa: F401  触发全部 model 注册
from app.db.base import Base
from app.models.enums import WorkflowProgressState, WorkflowType

# P9A-OBS-001 的 8 个 + P9A-OBS-002/003 强制的 2 个（见模块 docstring）
_BUSINESS_COLUMNS = {
    "project_id",
    "workflow_type",
    "workflow_id",
    "step_order",
    "step_role",
    "step_status",
    "started_at",
    "completed_at",
    "assignee",
    "result_hash",
}


def _table():
    return Base.metadata.tables["workflow_progress"]


def _cols() -> set[str]:
    return set(_table().columns.keys())


def test_workflow_progress_columns_are_exactly_the_10_business_ones():
    """业务列不多不少 —— 多的列没有 SPEC 依据，少的列读 API 用不了。"""
    got = _cols()
    # 主键 + TimestampMixin 三列之外，必须恰好是那 10 个
    rest = got - {"progress_id", "created_by", "created_at", "updated_at"}
    assert rest == _BUSINESS_COLUMNS, (
        f"workflow_progress 业务列不符：多出 {rest - _BUSINESS_COLUMNS}，"
        f"缺少 {_BUSINESS_COLUMNS - rest}"
    )


def test_workflow_progress_inherits_timestamp_mixin_three():
    """三列纪律（mixins.py:34-41）：created_by / created_at / updated_at。"""
    cols = _cols()
    for name in ("created_by", "created_at", "updated_at"):
        assert name in cols, f"缺 TimestampMixin 列 {name}"


def test_updated_at_is_nullable_and_has_onupdate():
    """TimestampMixin 纪律：updated_at 可空 + onupdate=func.now()（mixins.py:38-40）。

    注意 `col.onupdate` 是 `ColumnElementColumnDefault`，`now()` 藏在 `.arg` 里 ——
    直接 `str(col.onupdate)` 会打印整个 wrapper，`"now()" in` 反而可能误配中。
    """
    col = _table().columns["updated_at"]
    assert col.nullable is True, "updated_at 必须可空（纯 INSERT 后是 NULL）"
    assert col.onupdate is not None, "updated_at 缺 onupdate ⇒ UPDATE 不刷新时间戳"
    assert "now()" in str(col.onupdate.arg), f"onupdate 不是 now()：{col.onupdate}"


def test_created_at_has_server_default_and_timezone():
    """created_at 由 DB 填（server_default=func.now()）+ 带时区。"""
    col = _table().columns["created_at"]
    assert col.server_default is not None, "created_at 缺 server_default ⇒ 纯 SQL 插入会炸"
    assert "now()" in str(col.server_default.arg), \
        f"server_default 不是 now()：{col.server_default}"
    assert col.type.timezone is True, "created_at 必须带时区（DateTime(timezone=True)）"


def test_project_id_is_not_null():
    """读 API 按项目鉴权（B5 test_read_api_is_project_scoped）⇒ 这一列不能空。"""
    assert _table().columns["project_id"].nullable is False


@pytest.mark.parametrize(
    "state_name",
    ["PENDING", "IN_PROGRESS", "COMPLETED", "SKIPPED", "FAILED"],
)
def test_state_enum_is_exactly_5_values(state_name):
    """P9A-OBS-001：5 态枚举。逐态断言 —— 少一态甘特图缺色，多一态是没人设计的第 6 态。"""
    assert state_name in WorkflowProgressState.__members__


def test_state_enum_has_no_extra_members():
    assert set(WorkflowProgressState.__members__) == {
        "PENDING",
        "IN_PROGRESS",
        "COMPLETED",
        "SKIPPED",
        "FAILED",
    }, "枚举多出计划外的态"


def test_state_enum_values_equal_names():
    """DB 存的是值不是名 —— 值与名不一致会让查出来的行读成另一个态。"""
    for name, member in WorkflowProgressState.__members__.items():
        assert member.value == name


def test_workflow_type_enum_is_exactly_3_values():
    """ADR-0047 §① 的三个写入点：签署 / 变更单 / 代录批准。

    ADR 明写「若将来超出这个数，说明有第四类工作流被漏登记 —— 届时回本 ADR 修订，
    不要就地加写入点」。做成 Enum 就是让那条约束在类型层成立。
    """
    assert set(WorkflowType.__members__) == {
        "SIGN",
        "CHANGE_NOTICE",
        "CUSTOMER_APPROVAL_PROXY",
    }


def test_progress_row_is_unique_per_workflow_step_order():
    """同一工作流同一顺序号只允许一行。

    没有它：重复签署会追加第二行，甘特图出现两个同序号步骤，
    「哪条是当前的」取决于插入顺序 —— 而 read API 读不出这个差别。
    """
    uniq = [
        u
        for u in _table().constraints
        if u.__class__.__name__ == "UniqueConstraint"
    ]
    assert any(
        set(u.columns.keys()) == {"workflow_type", "workflow_id", "step_order"}
        for u in uniq
    ), f"workflow_progress 缺 (workflow_type, workflow_id, step_order) UNIQUE，现有：{uniq}"


def test_read_api_lookup_columns_are_indexed():
    """读 API 按 (workflow_type, workflow_id) 查；无索引则甘特图每次全表扫。"""
    indexed = {c.name for idx in _table().indexes for c in idx.columns}
    assert {"workflow_type", "workflow_id"} <= indexed, (
        f"读路径列未建索引，现有索引列：{indexed}"
    )


def test_no_todos_table_exists():
    """ADR-0049 §②：todos **不建表**，走实时计算。建了就是第二个真相源。"""
    assert "todos" not in Base.metadata.tables, (
        "todos 表不该存在 —— ADR-0049 §② 裁决待办实时计算"
    )
