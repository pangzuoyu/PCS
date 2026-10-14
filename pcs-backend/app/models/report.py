"""P8 报表与输出 ORM（ADR-P8-001 全直接生成路线）。

4 张表：
- `report_styles`          样式配置（ReportStyle 的 JSON 快照）
- `report_files`           生成文件元数据（按内容哈希命名）
- `report_definitions`     自定义报表定义（REPORT_BUILDER）
- `report_execution_logs`  执行审计

**不含** .dotx / .xltx 模板表 —— ADR-P8-001 已废止用户提供模板的机制，
样式改由 `ReportStyle` JSON 驱动。

`report_definitions` / `report_execution_logs` 沿用 bootstrap 迁移
`dd47298c9c38` 起的表名，但那两张表**从未被使用**（无 service / API / 前端
引用，0 行），字段与 SPEC-P8 §3.2.2(2) 完全不同。用户 2026-10-08 裁决就地改造，
避免仓库里同时存在两个「报表定义」概念。
"""
from __future__ import annotations

import datetime
import uuid

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import TimestampMixin

# `report_files.status` 的完整状态集合 —— **契约**，不是随手写的字符串。
#
# `DELETING` 是 ADR-P8-004 决策 2 的**三步删除**中间态：
#   1. 事务内：status = 'DELETING'
#   2. 事务外：删磁盘文件（幂等，文件不存在不报错）
#   3. 事务内：删行
# 任何一步失败都留下可恢复的中间态，下次扫描据此重试：
#   | 失败点        | 留下的状态              | 恢复动作         |
#   | 标记失败      | 行正常                  | 下次扫描重试     |
#   | 删文件失败    | DELETING + 文件在       | 下次扫描删文件   |
#   | 删行失败      | DELETING + 文件已没了   | 下次扫描删行     |
#
# ⚠️ 二步方案（删文件 → 删行）在「删文件成功、删行失败」时会**丢掉执行记录**：
# 下次扫描看不到这行，文件已删，无从重试。这正是 ADR 要防的「删错不可逆」。
REPORT_FILE_STATUSES = frozenset({"PENDING", "SUCCEEDED", "FAILED", "DELETING"})


class ReportStyleRow(TimestampMixin, Base):
    """报表样式配置（report_styles 表）。

    `style_json` 是 `ReportStyle` 的序列化结果；`style_version` 随报表生成记录
    冻结，保证可复现（ADR-P8-001 §样式配置的存储）。
    """

    __tablename__ = "report_styles"
    __table_args__ = (
        # ⚠️ `postgresql_nulls_not_distinct` 不是可选项（2026-10-14 修，
        # 评审 P2 #14）。`project_id` 可空表示「公司级样式」，而 PG 认为
        # **NULL 互不相等** ⇒ 不加这个开关，公司级行完全绕开唯一约束：
        # 两个同版本的 ACTIVE 公司样式可以并存。而应用层的「先查有没有」
        # 无锁，并发两次都查得到「没有」。
        #
        # ⚠️ 这是 **PG 专属**选项，SQLite 上被忽略 —— 所以单测跑不出这个
        # 行为，`tests/services/report/test_nulls_distinct_unique.py` 只能验
        # 「ORM 声明了它」。真库验证在 p8_009 与 TODOS 复核清单里。
        UniqueConstraint("report_type", "project_id", "version",
                         name="uq_report_styles_scope_version",
                         postgresql_nulls_not_distinct=True),
        Index("ix_report_styles_report_type", "report_type"),
    )

    style_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    report_type: Mapped[str] = mapped_column(String(64), nullable=False)
    # nullable=True：公司级样式不属于任何项目
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("projects.project_id", ondelete="CASCADE"), nullable=True
    )
    style_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    version: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="DRAFT", nullable=False)


class ReportFile(TimestampMixin, Base):
    """生成文件元数据（report_files 表）。

    文件按**内容哈希**命名，同内容重复生成复用同一行 —— 对应 SPEC §2.5
    「文件不可变性」与 Review Focus #5。

    ⚠️ **`project_id` 刻意不加 FK**（与 ReportStyleRow / ReportDefinition 不同）。
    加了 `ondelete=CASCADE` 的话，项目一删 DB 行没了但磁盘文件还在 → 变成无
    记录的孤儿文件，比有记录更难排查。不加 FK 则这些行仍在，可被清理任务
    （ADR-P8-004 待确认）按条件捞出。**不要「顺手补上 FK」。**
    """

    __tablename__ = "report_files"
    __table_args__ = (
        UniqueConstraint("content_hash", name="uq_report_files_content_hash"),
        Index("ix_report_files_project_id", "project_id"),
        Index("ix_report_files_status", "status"),
        Index("ix_report_files_task_id", "task_id"),
    )

    report_file_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    # 固定 10 类报表的 202 → 文件桥（TODO-063，alembic p8_006）。
    # 行由 `/report/generate` 在**入队时**建，worker 靠占位 content_hash
    # 找回**同一行**；ARQ 重试时 `_job_id` 不变，所以重试不留孤儿 PENDING。
    task_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # 刻意无 FK，见上方 docstring
    project_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    file_format: Mapped[str] = mapped_column(String(10), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    # 文件编号与版次。**给 verify 端点用**（Task 8）—— 现场扫码的人靠这两个
    # 确认「自己扫的是哪一份」。没有它们，verify 响应只剩 match + 时间戳，
    # 对拿着纸质件的人毫无意义。
    doc_no: Mapped[str | None] = mapped_column(String(50), nullable=True)
    rev: Mapped[str | None] = mapped_column(String(20), nullable=True)
    # 生成时冻结的样式版本，保证可复现
    style_version: Mapped[str | None] = mapped_column(String(32), nullable=True)
    data_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # 异步任务状态，见 REPORT_FILE_STATUSES。**刻意用自由 String 而非 DB enum** ——
    # 加一个状态值零迁移成本；改成 native_enum 后不仅要写迁移，`alembic check`
    # 还看不见（它比类型不比取值）。有测试钉住这条。
    status: Mapped[str] = mapped_column(String(20), default="SUCCEEDED", nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 任务心跳。ARQ 进程被 kill 时状态会永远卡在 PENDING，Task 7 的回收任务
    # 靠这个字段识别僵死任务 —— 没有它前端会无限轮询且无人知道。
    heartbeat_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(),
        nullable=False,
    )
    # 是否含假设数据声明页（SPEC §3.2.1(4)）
    has_assumption_page: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class ReportDefinition(TimestampMixin, Base):
    """自定义报表定义（report_definitions 表，REPORT_BUILDER）。

    `definition_json` 承载 SPEC §3.2.2(2) 的 DataSources / SelectedFields /
    FilterConditions / SortBy。**JOIN 只能取 datasource_registry 白名单**，
    不接受任意关联键（SPEC §1.3）。
    """

    __tablename__ = "report_definitions"
    __table_args__ = (
        # ⚠️ 同上：`project_id IS NULL` = 公司级模板作用域，
        # 不加 NULLS NOT DISTINCT 就能有两个同名公司级定义。
        UniqueConstraint("project_id", "name",
                         name="uq_report_definitions_project_name",
                         postgresql_nulls_not_distinct=True),
        Index("ix_report_definitions_status", "status"),
    )

    def_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("projects.project_id", ondelete="CASCADE"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    # 设备类/管道类/物流类/综合类/管理类
    category: Mapped[str] = mapped_column(String(32), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    definition_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    output_format: Mapped[str] = mapped_column(String(10), nullable=False)
    # ⚠️ **P8 引擎上限 10000**（`query_engine.assemble` 的 batch 边界）。
    # **这是实现限制，不是 SPEC 要求** —— SPEC 只规定默认值 10000，未规定上限。
    # 将来 `assemble` 引入真分批后此上限可提高，见
    # `definition_service.MAX_ROWS_CEILING`（对外承诺与引擎边界相等，
    # 有测试钉住）。曾短暂设为 100_000，那是「保存通过、执行期必然 400」。
    max_rows: Mapped[int] = mapped_column(Integer, default=10000, nullable=False)
    version: Mapped[str] = mapped_column(String(32), default="0.1.0", nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="DRAFT", nullable=False)
    # 全部用户/指定角色/仅创建人
    shared_with: Mapped[str] = mapped_column(String(20), default="CREATOR_ONLY", nullable=False)


class ReportExecutionLog(TimestampMixin, Base):
    """执行审计（report_execution_logs 表）。

    `condition_snapshot` 必存 —— 执行时允许临时调整过滤条件而不改定义本身，
    事后要能复现当时查了什么（SPEC §3.2.2(5)）。
    """

    __tablename__ = "report_execution_logs"
    __table_args__ = (
        Index("ix_report_execution_logs_def_id", "def_id"),
        # 轮询按 task_id 查（b11）。没索引就是每 2 秒一次全表扫。
        Index("ix_report_execution_logs_task_id", "task_id"),
        # 回收器按 status 扫（TODO-064）。没索引就是每次 cron 一次全表扫。
        Index("ix_report_execution_logs_status", "status"),
    )

    log_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    def_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("report_definitions.def_id", ondelete="CASCADE"), nullable=False
    )
    def_version: Mapped[str] = mapped_column(String(32), nullable=False)
    condition_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False)
    row_count: Mapped[int] = mapped_column(Integer, nullable=False)
    output_format: Mapped[str] = mapped_column(String(10), nullable=False)
    executed_by: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    # 本次执行是否临时改过过滤条件（不修改定义本身）
    is_temporary_adjust: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # --- b11 时序契约（2026-10-13 补，见 alembic p8_005）---
    # `/execute` 返回 202 + task_id，status 端点只认 report_file_id。
    # 这两列是两者之间**唯一**的桥：2026-10-13 实测此前不存在，
    # 前端拿到 202 之后永远拿不到文件。
    task_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # 生成前为 NULL —— 这正是「还在跑」的信号，不需要额外 status 列。
    # **刻意无 FK**：与 ReportFile.project_id 同理，项目删除后不留孤儿引用。
    report_file_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)

    # --- 执行状态（2026-10-13，alembic p8_007，TODO-064）---
    # ⚠️ **不要**再用 `report_file_id IS NULL` 合成状态：那样「已入队」
    # 「正在跑」「已经僵死」三种情况长得一样，回收器没有地方写下第三种，
    # 而它是审计表、又不能删行，于是「谁请求过这次执行、结果如何」
    # 永远差一个结局。端点现在直接读这一列。
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="QUEUED", server_default="QUEUED",
        comment="QUEUED 已入队 / RUNNING 执行中 / FINISHED 已出文件 / FAILED 已终结（含被回收）")
