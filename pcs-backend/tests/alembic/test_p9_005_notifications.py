"""P9A C0 迁移基座的 schema 断言 —— notifications（ADR-0049 §①/§③）。

⚠️ 迁移与 ORM 漂移时，**单测照绿、真库会炸**（CLAUDE.md 漂移盲区）。
本文件断言的是**元数据与迁移产物一致**，不是运行时行为。

## 10 列的依据

主键 1 + 业务 6（`recipient_id` / `kind` / `title` / `body` /
`detail_json` / `read_at`）+ TimestampMixin 3 = 10。

**刻意没有 `project_id`**（对比 `record_comments` / `workflow_progress` 都有）：
通知的读路径是「当前用户读自己的」，鉴权身份就是 `recipient_id` 本身 ——
加一列 `project_id` 会让它变成第二个可被写错、且写错后**鉴权仍然通过**的
依据（越权读别人项目的通知）。`PUT /notifications/{id}/read` 同理按
`recipient_id` 判归属，不是按项目。

## `kind` 是 String(40) 不是 PG enum

ADR-0049 §① 的 DTO 写的是 `kind: str`。若 DB 侧再开一个 PG enum，
「Python 侧有哪些 kind」与「DB 允许哪些 kind」就是两份清单 ——
本仓已经为 `RECORD_TYPE_REGISTRY` 的同类问题付过代价（TODO-058 裁决：
注册表是表枚举，能力是推导出的谓词，不给同一件事建两份人工清单）。
⇒ 单一来源是 Python 的 `NotificationKind`，DB 列放宽为 String。
"""
import pytest

import app.models  # noqa: F401  触发全部 model 注册
from app.db.base import Base
from app.models.notification import NotificationKind

_BUSINESS_COLUMNS = {
    "recipient_id",
    "kind",
    "title",
    "body",
    "detail_json",
    "read_at",
}
_AUDIT_COLUMNS = {"notification_id", "created_by", "created_at", "updated_at"}


def _table():
    return Base.metadata.tables["notifications"]


def _cols() -> set[str]:
    return set(_table().columns.keys())


def test_notifications_columns_are_exactly_the_10():
    """不多不少。多出的列没有 ADR 依据，少的列读 API 用不了。"""
    assert _cols() == _BUSINESS_COLUMNS | _AUDIT_COLUMNS, (
        f"notifications 列不符：多出 {_cols() - _BUSINESS_COLUMNS - _AUDIT_COLUMNS}，"
        f"缺少 {_BUSINESS_COLUMNS | _AUDIT_COLUMNS - _cols()}"
    )


def test_notifications_has_no_project_id():
    """鉴权身份就是 recipient_id 本身。多一个 project_id 就是多一个能写错、
    且写错后鉴权仍然通过的依据。"""
    assert "project_id" not in _cols()


def test_no_todos_table_exists():
    """ADR-0049 §②：todos **不建表**，走实时计算。建了就是第二个真相源。"""
    assert "todos" not in Base.metadata.tables


def test_updated_at_is_nullable_and_has_onupdate():
    col = _table().columns["updated_at"]
    assert col.nullable is True, "updated_at 必须可空（纯 INSERT 后是 NULL）"
    assert col.onupdate is not None, "updated_at 缺 onupdate ⇒ UPDATE 不刷新时间戳"
    assert "now()" in str(col.onupdate.arg), f"onupdate 不是 now()：{col.onupdate}"


def test_created_at_has_server_default_and_timezone():
    col = _table().columns["created_at"]
    assert col.server_default is not None, "created_at 缺 server_default ⇒ 纯 SQL 插入会炸"
    assert "now()" in str(col.server_default.arg)
    assert col.type.timezone is True


def test_notifications_partial_index_exists():
    """部分索引是 500ms 指标的全部支撑（ADR-0049 §③）。

    ⚠️ 不是「以后优化」：ADR-0049 §③ 与计划 C0 都把它列为**必须进迁移**的项。
    缺它时读未读通知走全表扫，指标不达标 —— 而这种缺失不会让任何测试变红。
    """
    idx = _table().indexes
    matches = [i for i in idx if i.name == "ix_notifications_recipient_unread"]
    assert len(matches) == 1, "缺 ix_notifications_recipient_unread 部分索引"
    t = matches[0]
    assert [c.name for c in t.columns] == ["recipient_id", "read_at"]
    where = t.dialect_options["postgresql"].get("where")
    assert where is not None, (
        "索引必须带 postgresql_where —— 建成全量索引时已读行也会进索引，"
        "未读占比下降后索引不再有选择性"
    )
    assert "read_at IS NULL" in str(where)


def test_partial_index_matches_sqlite_test_runtime_shape():
    """SQLite 下 `postgresql_where` 不生效 —— 断言分母仍在索引里，
    避免「只在 PG 生效」的守卫在单测环境静默通过。"""
    t = [i for i in _table().indexes if i.name == "ix_notifications_recipient_unread"][0]
    assert set(c.name for c in t.columns) == {"recipient_id", "read_at"}


def test_recipient_id_is_not_null_and_indexed():
    """收件人是通知的存在理由；可空的收件人通知永远读不出来。"""
    col = _table().columns["recipient_id"]
    assert col.nullable is False
    indexed = {c.name for idx in _table().indexes for c in idx.columns}
    assert "recipient_id" in indexed


def test_read_at_is_nullable():
    """read_at 可空 = 未读。NOT NULL 就没有「未读」这个态。"""
    assert _table().columns["read_at"].nullable is True


def test_read_at_has_timezone():
    """已读时刻要与 created_at 同精度比较（清理任务算 30 天）。"""
    assert _table().columns["read_at"].type.timezone is True


def test_detail_json_is_jsonb():
    """P9A-DLV-010：detail_json 装结构化上下文，JSONB 才能建 GIN 索引
    与用 PG 的 JSONB 操作符查询；退化成 Text 就只能整列扫描。"""
    from sqlalchemy.dialects.postgresql import JSONB

    assert isinstance(_table().columns["detail_json"].type, JSONB)


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("SIGN_COMPLETED", "SIGN_COMPLETED"),
        ("STEP_RETURNED", "STEP_RETURNED"),
        ("PROXY_RECORDED", "PROXY_RECORDED"),
        ("CHANGE_NOTICE_APPROVED", "CHANGE_NOTICE_APPROVED"),
    ],
)
def test_kind_has_the_4_wired_triggers(name, value):
    """用户 2026-10-20 裁决的最小接线集合：签署成功 / 步骤被退回 /
    代录完成 / 变更单审批。逐个点名 —— 「有枚举」不等于「有这四个」。"""
    assert name in NotificationKind.__members__


def test_kind_enum_has_no_extra_members():
    assert set(NotificationKind.__members__) == {
        "SIGN_COMPLETED",
        "STEP_RETURNED",
        "PROXY_RECORDED",
        "CHANGE_NOTICE_APPROVED",
    }, (
        "kind 多出计划外的成员。⚠️ 这不是「加一个也无妨」—— "
        "接线集合是用户裁决的边界，新增触发源要先回 ADR-0049 记一笔"
    )


def test_kind_enum_values_equal_names():
    """DB 存值不存名。值与名不一致会让查出来的行读成另一个 kind。"""
    for name, member in NotificationKind.__members__.items():
        assert member.value == name


def test_kind_column_is_string_not_pg_enum():
    """DB 侧刻意不放 enum —— 两份「有哪些 kind」的清单必然漂移（模块 docstring）。"""
    col = _table().columns["kind"]
    assert not hasattr(col.type, "enums"), "kind 不该是 PG enum（见模块 docstring）"
    assert col.type.length == 40


def test_title_and_body_are_not_null():
    """标题与正文是铃铛上显示的全部内容；可空的通知前端无从渲染。"""
    assert _table().columns["title"].nullable is False
    assert _table().columns["body"].nullable is False


def test_notifications_created_index_exists():
    """⚠️ 断线兜底列表**实际靠的是这个索引**，不是那个部分索引。

    真库实测（2000 行、事务内、ROLLBACK 无残留）：

    ```
    select * from notifications
     where recipient_id = :u and read_at is null
     order by created_at desc limit 50;
    ── Index Scan Backward using ix_notifications_recipient_created
       Index Cond: (recipient_id = ...)
       Filter: (read_at IS NULL)          ← 部分索引没被用上
       Execution Time: 0.026 ms
    ```

    原因：`ORDER BY created_at DESC` 需要按 created_at 排序，而部分索引是
    `(recipient_id, read_at)` —— 没有 created_at，**排不了序**，于是 planner
    选了能提供顺序的那个索引。

    ⇒ 两个索引各有各的用处，**都**必须进迁移：
    - `ix_notifications_recipient_created` → 列表（要排序）
    - `ix_notifications_recipient_unread` → 未读计数（铃铛红点，不必排序）
    """
    idx = _table().indexes
    matches = [i for i in idx if i.name == "ix_notifications_recipient_created"]
    assert len(matches) == 1, "缺 ix_notifications_recipient_created"
    assert [c.name for c in matches[0].columns] == ["recipient_id", "created_at"]


def test_cleanup_query_has_its_own_index_shape():
    """⚠️ 30 天清理的 `WHERE read_at IS NOT NULL AND created_at < cutoff`
    **用不了**那个部分索引（它的前导列是 recipient_id，而清理不按人筛）。

    真库实测它走 `ix_notifications_recipient_created` 的 index skip scan
    （PG 18），成本可接受（0.044 ms / 2000 行）。

    ⇒ 这里**不**加第三个索引：清理是每日一次的 cron，表规模是
    「每年几千行」量级，一次范围扫描毫秒级。加索引要付写入开销与
    schema 复杂度，换不来可观测的收益（D7 裁决的同一条理由）。
    """
    # 断言「清理不按 recipient_id 筛」这件事不会被人悄悄改掉
    import inspect

    from app.workers.notification_tasks import cleanup_old_notifications

    src = inspect.getsource(cleanup_old_notifications)
    assert "recipient_id" not in src, (
        "清理查询按 recipient_id 过滤了 —— 那会让部分索引变成第二个真相源"
    )
