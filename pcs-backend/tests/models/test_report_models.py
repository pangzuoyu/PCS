"""P8 报表 4 张表的 ORM 契约。

两条测试守的都是**跨层契约**，不是模型内部行为：
1. 表已注册 —— 漏了 `app/models/__init__.py` 的 import 会让 `alembic check`
   报出一堆假漂移（历史事故 `2c44e0c`：漏 import `util` 导致 130 条假漂移）。
2. 约束名符合预期 —— 名字对不上 `alembic check` 就会报真漂移，而真库是迁移
   建出来的、ORM 是另一份声明，两边名字必须逐字一致。
"""
from app.db.base import Base

_TABLES = ("report_styles", "report_files", "report_definitions", "report_execution_logs")


def test_report_tables_registered():
    for t in _TABLES:
        assert t in Base.metadata.tables, f"{t} 未注册（多半是 app/models/__init__.py 漏 import）"


def test_constraint_names_follow_convention():
    """约束名必须与迁移里写的一致，否则 `alembic check` 报漂移。"""
    c = Base.metadata.tables["report_definitions"].constraints
    names = {x.name for x in c if getattr(x, "name", None)}
    assert "pk_report_definitions" in names
    assert "uq_report_definitions_project_name" in names


def test_report_file_project_id_has_no_fk_deliberately():
    """**刻意不加 FK** —— 加了 CASCADE 的话，项目一删 DB 行没了、磁盘文件还在，
    变成无记录的孤儿文件，比有记录更难排查。不加 FK 则这些行仍在，可被清理任务
    （ADR-P8-004 待确认）按条件捞出。执行时不要「顺手补上 FK」。
    """
    col = Base.metadata.tables["report_files"].columns["project_id"]
    assert list(col.foreign_keys) == [], "report_files.project_id 不应有 FK"


def test_report_file_has_heartbeat_and_status_for_task_recovery():
    """Task 7 的僵死任务回收靠这两个字段。

    没有 `heartbeat_at`，ARQ 进程被 kill 后状态会永远卡在 PENDING，前端无限轮询。
    """
    cols = Base.metadata.tables["report_files"].columns
    for c in ("status", "heartbeat_at", "error_message"):
        assert c in cols, f"report_files 缺 {c}"


def test_report_file_status_state_set_is_pinned():
    """`report_files.status` 的状态集合是**契约**，不是随手写的字符串。

    ADR-P8-004 决策 2 的三步删除需要 `DELETING` 中间态：先在事务内标记、
    再在事务外删文件、最后删行。任何一步失败都留下可恢复的中间态，
    下次扫描据此重试。二步方案（删文件 → 删行）在「删文件成功、删行失败」
    时**丢掉了执行记录** —— 下次扫描看不到这行，文件已删，无从重试。

    这条测试钉住状态集合：日后加状态必须同步改这里并想清楚恢复路径。
    """
    from app.models.report import REPORT_FILE_STATUSES

    assert REPORT_FILE_STATUSES == frozenset(
        {"PENDING", "SUCCEEDED", "FAILED", "DELETING"})
    col = Base.metadata.tables["report_files"].columns["status"]
    assert col.type.length >= len("DELETING"), "列太短，新状态存不下"


def test_status_column_is_free_string_not_db_enum():
    """刻意用自由 String 而非 DB enum —— 加 `DELETING` **零迁移成本**。

    若日后有人「规范」成 native_enum，加一个状态值就要一条 alembic 迁移，
    而 `alembic check` 对 enum 值变化是看不出来的（它比的是类型不是取值）。
    """
    from sqlalchemy import Enum as SAEnum

    col = Base.metadata.tables["report_files"].columns["status"]
    assert not isinstance(col.type, SAEnum), \
        "改成 native enum 会让加状态值必须写迁移，且 alembic check 看不见"


def test_report_file_carries_doc_no_and_rev():
    """verify 端点要回 `{match, doc_no, rev, generated_at}`（用户 2026-10-08 裁决）。

    现场扫码的人就是靠 doc_no / rev 确认**自己扫的是哪一份**。没有这两列，
    响应就只剩一个 match 和一个时间戳 —— 对拿纸的人来说没有意义。
    """
    cols = Base.metadata.tables["report_files"].columns
    assert "doc_no" in cols, "verify 响应要回 doc_no，ReportFile 必须存它"
    assert "rev" in cols, "verify 响应要回 rev，ReportFile 必须存它"
