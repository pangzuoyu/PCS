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
