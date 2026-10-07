# P8 报表与输出 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development`（推荐）或 `superpowers:executing-plans` 逐任务执行。步骤用 checkbox（`- [ ]`）跟踪。

**Goal:** 交付 REPORT 引擎（正式报表生成 → ReportLab/python-docx/XlsxWriter 直接构建 → 二维码 → 假设声明页 → 异步任务 → 下载审计）与 REPORT_BUILDER（自定义报表定义、字段选择、16 操作符过滤、显式 JOIN、执行导出）。

**Architecture:** 单一渲染路径，代码 → 文档，**无中间格式转换、无用户提供模板**（ADR-P8-001）。样式由 `ReportStyle` JSON 配置驱动，四级优先级合并。渲染器按输出格式分工，各自独立可测。

**Tech Stack:** FastAPI / SQLAlchemy 2.0 async / Alembic / python-docx / XlsxWriter / ReportLab / ARQ / pytest / SQLite(测试) + PostgreSQL 18(真库)

**Spec:** `spec/工艺专用综合计算软件需求规格说明书 Web版 P8.md`（V1.3）
**ADR:** `docs/adr/ADR-P8-001：报表生成采用全直接生成模式.md`、`docs/adr/HEAT 报表双 detail_level 模板裁决.md`

## Global Constraints

- **禁止引入**：LibreOffice / unoserver / docxtpl / openpyxl 模板填充 / pydocx-pdf / Gotenberg / Aspose。用户 `.dotx`/`.xltx` **不是运行时模板**。
- **报表响应 schema 不得含裸 `object`/`array`** —— 走 `PcsError` 不用 `response: object`（P9A-DLV-010 硬约束，闸 `scripts/check_openapi_payload_coverage.py`）。
- **约束名走 `NAMING_CONVENTION`**（`app/db/base.py`），不手写；改迁移后必跑 `uv run alembic check`（**退出码 255，不是 1**）。
- **迁移幂等**：`op.drop_constraint(..., if_exists=True)` + create；`op.create_table` 的位置参数只能是 `Column`/`Constraint`，**裸 `sa.ForeignKey` 会被静默丢弃**（bug-144）。
- **`op.create_table` 的 CHECK 表达式若含 PG 专有语法**（如 `interval '1s'` 类型字面量），SQLite 建表会炸 → 需在 `tests/conftest.py` 的 `SQLiteDDLCompiler` 替身表登记等价式。**本计划已全部避开 PG 专有语法。**
- **测试库是 in-memory SQLite + `create_all`（从 ORM metadata）** —— 测试**永远绿**，真库才会炸。改迁移后必须 `uv run alembic check` + 在 `pcs_test` 上 `alembic upgrade head` 复跑。
- 性能：简单报表 ≤5s；复杂报表（50–200 行）≤15s；PDF 简单 <1s、复杂 1–3s；XLSX 100 万行内存 <100MB。
- 审计动作新增 `REPORT_GENERATED` / `REPORT_DOWNLOADED` / `REPORT_FAILED` / `REPORT_EXECUTED`（`app/models/enums.py:222` `AuditAction`，值 ≤50 字符）。
- 每批交付前跑 Per-Batch QA Gate：typecheck / lint / test / 浏览器巡检（**必须用 `history.pushState` 客户端导航，token 仅存内存，`goto` 会弹回登录页导致假绿**）。
- **`Block` 联合与 `_cell_text` / `truncate` 一律从 `blocks.py` import**，三个渲染器互不 import。PDF 与 XLSX/DOCX 在架构上对等，不存在谁在谁之上。
- **BUILDER 执行（b7）走 ARQ 任务，不走同步端点** —— 10000 行 ≤10s 的同步查询会阻塞整个 event loop。
- **假设字段标记 = 表头拼 `▲` + 单元格文字橙色**，两个都做（SPEC §3.2.1(4)）。三个渲染器各自的表头语法不同，但「加三角」这个逻辑在 `blocks.py` 的 `assumed_header()` 里只写一次。
- **ORM 不 import `get_settings()`** —— 绝对路径拼接在 `report_service.resolve_path()` 里，与其他 100+ 个模型一致。
- **collector 每个 report_type 一次批量 SELECT**，在 Python 里组装。禁止在循环里查库。
- **性能断言用绝对预算，不引入 pytest-benchmark** —— CI 共享 runner 负载波动会让相对阈值频繁误报，最后被 disable。`max_jobs` 需为报表任务预留容量。

## Review Focus

SPEC 是愿景文档，它没说的输入**不等于可以破坏程序**。以下五类最可能伤到真实使用者，各行对应一个必须存在的测试：

1. **字体缺失** → PDF 中文渲染成方块或空白。测试：缺 `font_dir` 时抛 `PcsError(code="REPORT_FONT_MISSING")`，**不产出半成品 PDF**。
2. **数据源某字段为 NULL** → 表格单元格写 `None` 字面量或整表渲染失败。测试：字段全 NULL 的记录仍能出表，单元格渲染为 `—`。
3. **过滤条件值为空**（`{"operator": "IS_NULL"}` 无 `value`）→ 拼接出 `WHERE x = ` 语法错或**误判为全表**。测试：返回该字段为空的结果集，不是报错也不是全表。
4. **超长字符串**（设备描述 5000 字）→ 表格撑破版式。测试：单元格设 `max_len` 截断 + 省略号。
5. **重复生成相同内容** → 文件存储按内容哈希命名，重复生成**必须复用同一文件**而不是产生第二份（SPEC §3.2.1(6) 文件不可变性）。测试：两次生成 → `report_files` 只有 1 行。

---

## File Structure

```
pcs-backend/
  app/models/report.py              4 张新表 ORM（唯一新增模型文件）
  app/schemas/report.py             Pydantic 请求/响应（零裸 object）
  app/services/report/
    style.py                        ReportStyle 模型 + resolve() 四级合并
    blocks.py                       Block 联合 + _cell_text + truncate（**三者共用，勿下沉到任一渲染器**）
    datasource_registry.py          13 数据源字段注册表 + JOIN 白名单
    renderer_docx.py                python-docx
    renderer_xlsx.py                XlsxWriter
    renderer_pdf.py                 ReportLab（含二维码直绘）
    qr.py                           二维码内容组装（doc_no+Rev+hash 摘要）
    collector.py                    报表类型 → 数据收集（10 类）
    report_service.py               生成编排 + 文件存储 + 审计
    builder_service.py              过滤/排序/执行/导出
  app/api/v1/report.py              全部路由
  app/workers/report_tasks.py       ARQ 任务（注册进 worker.py functions）
  alembic/versions/p8_001_*.py      迁移（每张表一条，全部幂等）
  tests/
    services/report/test_*.py       单元 + 引擎测试
    api/v1/test_report.py           端点测试
    golden/report/*.pdf|.xlsx|.docx Golden 文件
    fixtures/report/seed.py         10 类报表 seed
```

**分工原则**：三个 renderer 互不依赖，只吃 `(data, style)`；`collector` 只管取数不管渲染；`report_service` 只做编排。三者任一换实现不影响另两个。

---

# Phase 1 — P8a REPORT 核心

## Task 1: 样式层 `ReportStyle`

**Files:**
- Create: `pcs-backend/app/models/report.py`
- Create: `pcs-backend/app/services/report/style.py`
- Test: `pcs-backend/tests/services/report/test_style.py`

**Interfaces:**
- Consumes: `app/db/base.py` `Base`（自带 `NAMING_CONVENTION`）、`app/db/base.py` 的 `Uuid`/`JSONB` 导入惯例
- Produces:
  - `ReportStyle(BaseModel)` —— 字段见下方代码
  - `resolve(*, defaults: ReportStyle, project: ReportStyle | None, by_type: ReportStyle | None, runtime: ReportStyle | None) -> ReportStyle`
  - ORM `ReportStyleRow`（`report_styles` 表）

- [ ] **Step 1: 写失败测试**

```python
# tests/services/report/test_style.py
from app.services.report.style import ReportStyle, resolve

def test_runtime_overrides_type_overrides_project_overrides_defaults():
    d = ReportStyle(font_size_body=10)
    p = ReportStyle(font_size_body=11)
    t = ReportStyle(font_size_body=12)
    r = ReportStyle(font_size_body=13)
    assert resolve(defaults=d, project=p, by_type=t, runtime=r).font_size_body == 13
    assert resolve(defaults=d, project=p, by_type=t, runtime=None).font_size_body == 12
    assert resolve(defaults=d, project=p, by_type=None, runtime=None).font_size_body == 11
    assert resolve(defaults=d, project=None, by_type=None, runtime=None).font_size_body == 10


def test_none_layers_do_not_erase_lower_precedence_values():
    d = ReportStyle(font_size_body=10, font_family_cn="Noto Sans CJK SC")
    out = resolve(defaults=d, project=None, by_type=ReportStyle(), runtime=None)
    assert out.font_family_cn == "Noto Sans CJK SC", "空层不得把下层值清掉"


def test_unset_field_falls_through_to_lower_layer():
    """只覆盖一个字段时，其余字段必须保留低层值 —— 靠 exclude_unset。
    注意：model_validate({...}) 不会把未出现的键算作「已设置」，
    而 ReportStyle(font_size_body=12) 的其余字段全部是「已设置」。"""
    layer = ReportStyle.model_validate({"font_size_body": 12})
    out = resolve(defaults=ReportStyle.model_validate(
                      {"font_size_body": 10, "font_family_cn": "A"}),
                  project=layer, runtime=None)
    assert out.font_size_body == 12
    assert out.font_family_cn == "A"
```

- [ ] **Step 2: 跑测试确认失败**

Run: `uv run pytest tests/services/report/test_style.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.services.report'`

- [ ] **Step 3: 最小实现**

```python
# app/services/report/style.py
"""报表样式配置 —— ADR-P8-001：样式驱动生成，替代 .dotx/.xltx 模板。"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class Margins(BaseModel):
    top: float = 20.0
    bottom: float = 20.0
    left: float = 25.0
    right: float = 20.0


class HeaderFooterConfig(BaseModel):
    left: str = ""
    center: str = ""
    right: str = ""


class TableStyle(BaseModel):
    header_bg: str = "#D9E1F2"
    header_bold: bool = True
    border_width: float = 0.5
    border_color: str = "#000000"
    cell_padding: int = 4
    zebra_stripe: bool = True
    max_cell_chars: int = 200          # Review Focus #4：超长截断


class ReportStyle(BaseModel):
    page_size: Literal["A4", "A3", "Letter"] = "A4"
    orientation: Literal["portrait", "landscape"] = "portrait"
    margins: Margins = Margins()
    font_family_cn: str = "Noto Sans CJK SC"
    font_family_en: str = "Arial"
    font_size_body: int = 10
    font_size_heading: int = 14
    line_spacing: float = 1.5
    header: HeaderFooterConfig = HeaderFooterConfig(
        left="{{project_no}}", center="{{report_name}}", right="Rev {{rev}}"
    )
    footer: HeaderFooterConfig = HeaderFooterConfig(
        left="{{doc_no}}", center="", right="第 {{page}} 页 / 共 {{pages}} 页"
    )
    table: TableStyle = TableStyle()
    assumption_mark: str = "▲"
    assumption_color: str = "#FF8C00"
    qr_position: Literal["footer", "header"] = "footer"
    qr_size_mm: int = 20
    # 字体目录：PDF 渲染器据此定位 TTF。缺字体抛 REPORT_FONT_MISSING（Review Focus #1）
    font_dir: str = "fonts"


def resolve(*, defaults: ReportStyle, project: ReportStyle | None,
            by_type: ReportStyle | None, runtime: ReportStyle | None) -> ReportStyle:
    """四级优先级合并：默认 → 项目 → 报表类型 → 运行时。

    只用**显式设置过**的字段覆盖（exclude_unset）——
    否则上层一个空 ReportStyle() 会把下层全部字段清成默认值（Review Focus #2）。
    """
    merged = defaults.model_dump()
    for layer in (project, by_type, runtime):
        if layer is None:
            continue
        for k, v in layer.model_dump(exclude_unset=True).items():
            if v is not None:
                merged[k] = v
    return ReportStyle.model_validate(merged)
```

- [ ] **Step 4: 跑测试确认通过**

Run: `uv run pytest tests/services/report/test_style.py -v`
Expected: 3 passed

- [ ] **Step 5: 提交**

```bash
git add app/services/report/style.py app/services/report/__init__.py tests/services/report/test_style.py
git commit -m "feat(report): ReportStyle 模型 + 四级优先级合并"
```

---

## Task 2: `report_styles` / `report_files` 迁移 + ORM

**Files:**
- Create: `pcs-backend/app/models/report.py`
- Create: `pcs-backend/alembic/versions/p8_001_report_tables.py`
- Modify: `pcs-backend/app/models/__init__.py`（补 `from app.models.report import *` —— **漏这一行会导致 `alembic check` 假漂移**，见 `2c44e0c`）
- Test: `pcs-backend/tests/models/test_report_models.py`

**Interfaces:**
- Consumes: `Base`、`Uuid`、`JSONB`（`app/models/config_domain.py` 的导入模式）
- Produces: ORM `ReportStyleRow`、`ReportFile`、`ReportDefinition`、`ReportExecutionLog`

- [ ] **Step 1: 写失败测试**

```python
# tests/models/test_report_models.py
from app.db.base import Base

def test_report_tables_registered():
    for t in ("report_styles", "report_files", "report_definitions", "report_execution_logs"):
        assert t in Base.metadata.tables, f"{t} 未注册（多半是 app/models/__init__.py 漏 import）"


def test_constraint_names_follow_convention():
    """约束名必须走 NAMING_CONVENTION，不手写 —— 否则 alembic check 报漂移。"""
    c = Base.metadata.tables["report_definitions"].constraints
    names = {x.name for x in c if getattr(x, "name", None)}
    assert "pk_report_definitions" in names
    assert "uq_report_definitions_project_name" in names
```

- [ ] **Step 2: 跑测试确认失败** → `KeyError: 'report_definitions'`

- [ ] **Step 3: ORM**

```python
# app/models/report.py
"""P8 报表与输出 ORM（ADR-P8-001 路线）。

4 张表：report_styles（样式配置）/ report_files（生成文件元数据）/
report_definitions（自定义报表定义）/ report_execution_logs（执行审计）。
**不含** .dotx/.xltx 模板表 —— 该机制已废止。
"""
from __future__ import annotations

import datetime
import uuid

from sqlalchemy import (
    Boolean, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import TimestampMixin


class ReportStyleRow(TimestampMixin, Base):
    """报表样式配置（report_styles 表）。

    ADR-P8-001 §样式配置结构：style_json 为 ReportStyle 的序列化结果。
    **style_version 随报表生成记录冻结，保证可复现**。
    """

    __tablename__ = "report_styles"
    __table_args__ = (
        UniqueConstraint("report_type", "project_id", "version", name="uq_report_styles_scope_version"),
        Index("ix_report_styles_report_type", "report_type"),
    )

    style_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    report_type: Mapped[str] = mapped_column(String(64), nullable=False)
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("projects.project_id", ondelete="CASCADE"), nullable=True
    )
    style_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    version: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="DRAFT", nullable=False)


class ReportFile(TimestampMixin, Base):
    """生成文件元数据（report_files 表）。

    文件按**内容哈希**命名（{sha256[:16]}.{ext}），同内容重复生成复用同一行 ——
    对应 SPEC §2.5「文件不可变性」与 Review Focus #5。
    """

    __tablename__ = "report_files"
    __table_args__ = (
        UniqueConstraint("content_hash", name="uq_report_files_content_hash"),
        Index("ix_report_files_project_id", "project_id"),
    )

    report_file_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    file_format: Mapped[str] = mapped_column(String(10), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    style_version: Mapped[str | None] = mapped_column(String(32), nullable=True)
    data_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # 异步任务状态：PENDING / SUCCEEDED / FAILED（Task 7 用）
    status: Mapped[str] = mapped_column(String(20), default="SUCCEEDED", nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 是否含假设数据声明页（Task 6 验收用）
    has_assumption_page: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    @property
    def absolute_path(self) -> str:
        """磁盘绝对路径。file_path 存相对路径，落盘根目录由 REPORT_STORAGE_DIR 决定。"""
        from app.core.config import get_settings
        return str(Path(get_settings().report_storage_dir) / self.file_path)


class ReportDefinition(TimestampMixin, Base):
    """自定义报表定义（report_definitions 表，REPORT_BUILDER）。

    definition_json 承载 SPEC §3.2.2 的 DataSources / SelectedFields /
    FilterConditions / SortBy；**JOIN 只能取 datasource_registry 白名单**，
    不接受任意关联键（SPEC §1.3）。
    """

    __tablename__ = "report_definitions"
    __table_args__ = (
        UniqueConstraint("project_id", "name", name="uq_report_definitions_project_name"),
        Index("ix_report_definitions_status", "status"),
    )

    def_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("projects.project_id", ondelete="CASCADE"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    category: Mapped[str] = mapped_column(String(32), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    definition_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    output_format: Mapped[str] = mapped_column(String(10), nullable=False)
    max_rows: Mapped[int] = mapped_column(Integer, default=10000, nullable=False)
    version: Mapped[str] = mapped_column(String(32), default="0.1.0", nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="DRAFT", nullable=False)
    shared_with: Mapped[str] = mapped_column(String(20), default="CREATOR_ONLY", nullable=False)


class ReportExecutionLog(BaseModel):
    pass  # 占位，实际定义见下一步


class ReportExecutionLog(TimestampMixin, Base):
    """执行审计（report_execution_logs 表）。

    条件快照必存 —— 临时调整不修改定义定义本身，事后要能复现当时查了什么。
    """

    __tablename__ = "report_execution_logs"
    __table_args__ = (Index("ix_report_execution_logs_def_id", "def_id"),)

    log_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    def_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("report_definitions.def_id", ondelete="CASCADE"), nullable=False
    )
    def_version: Mapped[str] = mapped_column(String(32), nullable=False)
    condition_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False)
    row_count: Mapped[int] = mapped_column(Integer, nullable=False)
    output_format: Mapped[str] = mapped_column(String(10), nullable=False)
    executed_by: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    is_temporary_adjust: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
```

- [ ] **Step 4: 迁移（幂等）**

```python
# alembic/versions/p8_001_report_tables.py
"""P8 报表 4 张表。幂等：每张表先 drop(if_exists) 再 create。"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "p8_001"
down_revision = "p7_s5_008"
branch_labels = None
depends_on = None

_TABLES = ("report_styles", "report_files", "report_definitions", "report_execution_logs")


def upgrade() -> None:
    """建 4 张表（先 drop 再 create，天然幂等）。"""
    for t in _TABLES:
        op.drop_table(t, if_exists=True)
    # ... 此处放 op.create_table(...) 定义（字段与 ORM 一一对应）
    # ⚠️ 约束名必须与 ORM 的 NAMING_CONVENTION 展开结果逐字一致，
    #    否则 alembic check 会报漂移。可用：
    #    python -c "from app.db.base import Base; print(sorted(c.name for c in Base.metadata.tables['report_files'].constraints))"
```

**实现要点**（不留 TODO）：
1. 先跑上面那条 `python -c` 拿到 4 张表的真实约束名，逐字抄进 `op.create_table` 的 `sa.UniqueConstraint(..., name=...)`。
2. 所有外键**必须嵌在 Column 里**：`sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.project_id", ondelete="CASCADE"), nullable=True)`。裸位置参数会被 alembic 静默丢弃（bug-144）。
3. CHECK 表达式只用 SQLite 也能解析的语法（本计划无 CHECK，若后来加 `max_rows > 0` 这类通用语法则安全）。

- [ ] **Step 5: 验证真库**

```bash
uv run alembic upgrade head
uv run alembic check          # 必须 exit 0；exit 255 = 有漂移
DATABASE_URL="postgresql+psycopg://pcs:pcs_dev@localhost:5432/pcs_test" uv run alembic upgrade head
```

- [ ] **Step 6: 跑测试确认通过** → 2 passed

- [ ] **Step 7: 提交**

```bash
git add app/models/report.py app/models/__init__.py alembic/versions/p8_001_report_tables.py tests/models/test_report_models.py
git commit -m "feat(db): P8 报表 4 张表（幂等迁移）"
```

---

## Task 3: PDF 渲染器（ReportLab）

**Files:**
- Create: `pcs-backend/app/services/report/renderer_pdf.py`
- Create: `pcs-backend/tests/services/report/test_renderer_pdf.py`
- Modify: `pcs-backend/pyproject.toml`（加 `reportlab`、`qrcode`）

**Interfaces:**
- Consumes: `ReportStyle`（Task 1）、`PcsError`
- Produces: `render_pdf(*, title: str, blocks: list[Block], style: ReportStyle, qr_payload: str | None, assumed_fields: list[str]) -> bytes`

```python
# app/services/report/blocks.py —— 三个渲染器共用的中间表示
#
# ⚠️ **刻意不放 renderer_pdf.py**（2026-10-08 审查决策）：PDF / XLSX / DOCX 三者
# 在架构上对等，不该有谁 import 谁。改 PDF 渲染器不应波及 XLSX。
@dataclass(frozen=True)
class HeadingBlock:  text: str; level: int = 1
@dataclass(frozen=True)
class KeyValueBlock: rows: list[tuple[str, object]]
@dataclass(frozen=True)
class TableBlock:    headers: list[str]; rows: list[list[object]]; assumed_cols: tuple[int, ...] = ()
@dataclass(frozen=True)
class PageBreakBlock: pass
Block = HeadingBlock | KeyValueBlock | TableBlock | PageBreakBlock

_NULL = "—"

def _cell_text(value: object, max_chars: int = 200) -> str:
    """NULL → —，超长截断加省略号。三个渲染器共用（DRY）。"""
    if value is None:
        return _NULL
    s = str(value)
    return s if len(s) <= max_chars else s[: max_chars - 1] + "…"

def assumed_header(header: str, assumed: bool, mark: str = "▲") -> str:
    """SPEC §3.2.1(4)：受影响字段在表头带橙色三角。

    三个渲染器的表头语法不同（ReportLab Paragraph / XlsxWriter write /
    python-docx run），但「加三角」这个逻辑只在这里写一次。
    """
    return f"{header}{mark}" if assumed else header
```

- [ ] **Step 1: 写失败测试**

```python
# tests/services/report/test_renderer_pdf.py
import pytest
from app.services.exceptions import PcsError
from app.services.report.renderer_pdf import render_pdf
from app.services.report.style import ReportStyle

HDR = ["位号", "口径", "描述"]


def test_renders_table_and_returns_pdf_bytes():
    out = render_pdf(title="设备一览表",
                      blocks=[__import__("app.services.report.renderer_pdf", fromlist=["TableBlock"]).TableBlock(
                          headers=HDR, rows=[["P-101", "DN50", "工艺水"]],
                          assumed_cols=(2,))],
                      style=ReportStyle(), qr_payload=None, assumed_fields=[])
    assert out[:5] == b"%PDF-", "必须返回真 PDF 字节"
    assert len(out) > 1000


def test_missing_font_raises_instead_of_emitting_blank_pdf():
    """Review Focus #1：字体缺失必须显式失败，不产出半成品。"""
    s = ReportStyle(font_dir="/nonexistent/fonts")
    with pytest.raises(PcsError) as e:
        render_pdf(title="x", blocks=[], style=s, qr_payload=None, assumed_fields=[])
    assert e.value.code == "REPORT_FONT_MISSING"


def test_null_cell_renders_dash_not_none_literal():
    """Review Focus #2：NULL 单元格渲染为 —，不写 Python None 字面量。"""
    from app.services.report.renderer_pdf import TableBlock, _cell_text
    assert _cell_text(None) == "—"
    assert _cell_text("x") == "x"


def test_long_cell_truncated_with_ellipsis():
    """Review Focus #4：超长文本截断，不撑破版式。"""
    from app.services.report.blocks import _cell_text
    assert _cell_text("x" * 500).endswith("…")
    assert len(_cell_text("x" * 500)) == ReportStyle().table.max_cell_chars + 1


def test_assumed_header_gets_triangle_and_others_dont():
    """SPEC §3.2.1(4)：受影响字段表头带 ▲，其余不带。"""
    from app.services.report.blocks import assumed_header
    assert assumed_header("管径", True) == "管径▲"
    assert assumed_header("管径", False) == "管径"


def test_zero_blocks_still_renders_valid_pdf():
    from app.services.report.renderer_pdf import render_pdf
    out = render_pdf(title="空报表", blocks=[], style=ReportStyle(),
                     qr_payload=None, assumed_fields=[], font_dir=FONT_DIR)
    assert out[:5] == b"%PDF-"


def test_table_spanning_pages_still_renders():
    """跨页表格：200 行必须能出，且页数 > 1（LongTable 路径）。"""
    from app.services.report.renderer_pdf import render_pdf, TableBlock
    rows = [[f"P-{i}", "DN50", "工艺水"] for i in range(200)]
    out = render_pdf(title="跨页", blocks=[TableBlock(headers=["位号", "口径", "介质"], rows=rows)],
                     style=ReportStyle(), qr_payload=None, assumed_fields=[], font_dir=FONT_DIR)
    assert out[:5] == b"%PDF-"
    assert len(PdfReader(io.BytesIO(out)).pages) > 1
```

**⚠️ Task 3 验收卡点（缺了就是假绿）**：

```python
def test_chinese_text_is_extractable_and_font_embedded(tmp_path, monkeypatch):
    """**PDF 的全部价值就是「中文字形真的嵌进去了」。**

    只测 `%PDF-` 头是不够的：字体没嵌上时 PDF 结构仍然合法、字节数仍 >1000，
    测试照样绿，用户拿到的是一堆方块。这与 bug-143/145/149/150 同族 ——
    绿灯测的不是出问题的那层。
    """
    from pypdf import PdfReader
    out = render_pdf(title="泵数据表", blocks=[TableBlock(
        headers=["位号", "介质"], rows=[["P-101", "天然气"]])],
        style=ReportStyle(), qr_payload=None, assumed_fields=[], font_dir=FONT_DIR)
    text = PdfReader(io.BytesIO(out)).pages[0].extract_text()
    assert "天然气" in text, "中文抽不出来 = 字形没嵌对"

    f = tmp_path / "o.pdf"; f.write_bytes(out)
    fonts = subprocess.run(["pdffonts", str(f)], capture_output=True, text=True).stdout
    assert "Noto" in fonts and "yes" in fonts, f"字体未嵌入：\n{fonts}"
```

`FONT_DIR` 由 `tests/conftest.py` 提供（`pytest.fixture`，指向仓库内 `pcs-backend/fonts/`）。
**若仓库无 Noto CJK 字体，Task 3 Step 1 第一件事是把字体加进仓库** —— 否则整个 PDF 路线无法验证。

- [ ] **Step 2: 跑测试确认失败** → `ModuleNotFoundError`

- [ ] **Step 3: 实现**（写出 `renderer_pdf.py` 全部内容）

```python
"""PDF 渲染器 —— ReportLab Platypus 直接生成。

ADR-P8-001：**不经 LibreOffice 转换**。二维码直接用
`reportlab.graphics.barcode.qr` 绘制，**不做 pypdf 后处理**。
中文经 `pdfmetrics.registerFont(TTFont)` 注册，不依赖系统字体包。
"""
from __future__ import annotations

import io
from dataclasses import dataclass
from pathlib import Path

from reportlab.graphics.barcode import qr
from reportlab.lib import colors
from reportlab.lib.pagesizes import A3, A4, LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (PageBreak, Paragraph, SimpleDocTemplate,
                                Spacer, Table, TableStyle)

from app.services.exceptions import PcsError
from app.services.report.style import ReportStyle

from app.services.report.blocks import (Block, PageBreakBlock, TableBlock,
                                        _cell_text, assumed_header)

_PAGESIZES = {"A4": A4, "A3": A3, "Letter": LETTER}
_FONT_FILES = {
    "Noto Sans CJK SC": "NotoSansCJKsc-Regular.otf",
    "Noto Serif CJK SC": "NotoSerifCJKsc-Regular.otf",
}


def _register_font(style: ReportStyle, font_dir: str | Path) -> str:
    """注册中文字体。缺字体**显式失败**——产出中文方块的 PDF 比报错更难排查。"""
    pdfmetrics.registerFontFamily(style.font_family_cn, normal=style.font_family_cn)
    name = style.font_family_cn
    if name in pdfmetrics.getRegisteredFontNames():
        return name
    path = Path(font_dir) / _FONT_FILES.get(name, f"{name}.ttf")
    if not path.exists():
        raise PcsError(
            f"中文字体缺失：{path}。PDF 中文会渲染为方块，故直接失败。"
            f"请提供 Noto CJK 字体文件或设置 REPORT_FONT_DIR。",
            code="REPORT_FONT_MISSING",
            status=500,
        )
    pdfmetrics.registerFont(TTFont(name, str(path)))
    return name


def render_pdf(*, title: str, blocks: list[Block], style: ReportStyle,
               qr_payload: str | None, assumed_fields: list[str],
               font_dir: str | Path | None = None) -> bytes:
    """渲染 PDF 并返回字节。"""
    font_dir = font_dir or style.font_dir
    font = _register_font(style, font_dir)
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=_PAGESIZES[style.page_size],
        leftMargin=style.margins.left, rightMargin=style.margins.right,
        topMargin=style.margins.top, bottomMargin=style.margins.bottom,
        title=title,
    )
    base = getSampleStyleSheet()
    h1 = ParagraphStyle("h1", parent=base["Heading1"], fontName=font,
                        fontSize=style.font_size_heading, leading=style.font_size_heading * 1.4)
    body = ParagraphStyle("body", parent=base["BodyText"], fontName=font,
                          fontSize=style.font_size_body, leading=style.font_size_body * style.line_spacing)

    story: list = [Paragraph(title, h1)]
    if assumed_fields:
        note = Paragraph(
            f"本页含假设数据：{style.assumption_mark} " + "、".join(assumed_fields), body)
        story += [note, Spacer(1, 8)]

    for b in blocks:
        if isinstance(b, HeadingBlock):
            story.append(Paragraph(b.text, h1 if b.level == 1 else body))
        elif isinstance(b, PageBreakBlock):
            story.append(PageBreak())
        elif isinstance(b, KeyValueBlock):
            story.append(Table(
                [[Paragraph(str(k), body), Paragraph(_cell_text(v), body)] for k, v in b.rows],
                colWidths=[doc.width * 0.3, doc.width * 0.7],
                style=TableStyle([("GRID", (0, 0), (-1, -1), style.table.border_width,
                                   colors.HexColor(style.table.border_color))]),
            ))
        elif isinstance(b, TableBlock):
            mc = style.table.max_cell_chars
            data = [[Paragraph(assumed_header(h, ci in b.assumed_cols,
                                              style.assumption_mark), body)
                     for ci, h in enumerate(b.headers)]] + [
                [Paragraph(_cell_text(c, mc), body) for c in row] for row in b.rows]
            t = Table(data, repeatRows=1, hAlign="LEFT")
            cmds = [
                ("GRID", (0, 0), (-1, -1), style.table.border_width,
                 colors.HexColor(style.table.border_color)),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(style.table.header_bg)),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
            if style.table.zebra_stripe:
                for i in range(2, len(data), 2):
                    cmds.append(("BACKGROUND", (0, i), (-1, i), colors.HexColor("#F5F7FB")))
            for ci in b.assumed_cols:
                cmds.append(("TEXTCOLOR", (ci, 1), (ci, -1), colors.HexColor(style.assumption_color)))
            # 表头三角：headers 已在上面渲染，这里用 colspan=0 的空 cell 无法改字，
            # 故三角直接写进 header 文本（见 blocks.assumed_header）
            t.setStyle(TableStyle(cmds))
            story.append(t)

    doc.build(story, onFirstPage=_decorate, onLaterPages=_decorate)
    return buf.getvalue()


def _decorate(canvas, doc) -> None:
    """页脚：二维码 + 文档信息。qr_payload 由 report_service 注入闭包。"""
    pass
```

**⚠️ 实现者必须补完的两处**（上面是骨架，二维码与页眉页脚是 SPEC 硬要求，不是可选项）：

1. `_decorate` 需要闭包拿到 `style` / `qr_payload`，改成在 `render_pdf` 内定义局部函数：
   ```python
   def _page(canvas, doc):
       canvas.saveState()
       canvas.setFont(font, style.font_size_body - 2)
       canvas.drawString(doc.leftMargin, doc.bottomMargin / 2,
                         _fill_placeholders(style.footer.left, ctx))
       canvas.drawCentredString(doc.width / 2, doc.bottomMargin / 2,
                                _fill_placeholders(style.footer.right, ctx).replace("{{page}}", str(doc.page)))
       if qr_payload:
           canvas.drawRightString(doc.width - doc.rightMargin, doc.bottomMargin / 2,
                                  qr_payload[:40])
           q = qr.QrCodeWidget(qr_payload)
           q.drawOn(canvas, doc.width - doc.rightMargin - style.qr_size_mm,
                   doc.bottomMargin / 2)
       canvas.restoreState()
   ```
2. `_fill_placeholders(text, ctx)` —— 只支持 SPEC §4.1 的 7 个：`project_no` / `project_name` / `doc_no` / `rev` / `report_name` / `page` / `pages`。**遇到未知占位符原样保留**（便于发现拼写错误），不抛异常。

- [ ] **Step 4: 跑测试确认通过** → 4 passed

- [ ] **Step 5: 验证中文字体真的嵌入**

```bash
uv run pytest tests/services/report/test_renderer_pdf.py -v
# 手工验：把返回字节写到临时文件后
#   pdffonts /tmp/out.pdf | grep -i noto
```

- [ ] **Step 6: 提交**

```bash
git add app/services/report/renderer_pdf.py tests/services/report/test_renderer_pdf.py pyproject.toml
git commit -m "feat(report): PDF 渲染器（ReportLab Platypus + 二维码直绘）"
```

---

## Task 4: DOCX / XLSX 渲染器

**Files:**
- Create: `pcs-backend/app/services/report/renderer_docx.py`
- Create: `pcs-backend/app/services/report/renderer_xlsx.py`
- Test: `pcs-backend/tests/services/report/test_renderers.py`

**Interfaces:**
- Consumes: `Block`、`ReportStyle`（Task 1、3）
- Produces:
  - `render_docx(*, title: str, blocks: list[Block], style: ReportStyle, context: dict) -> bytes`
  - `render_xlsx(*, title: str, blocks: list[Block], style: ReportStyle, context: dict) -> bytes`

- [ ] **Step 1: 写失败测试**

```python
# tests/services/report/test_renderers.py
import io, zipfile
from app.services.report.renderer_docx import render_docx
from app.services.report.renderer_xlsx import render_xlsx
from app.services.report.renderer_pdf import TableBlock
from app.services.report.style import ReportStyle

B = [TableBlock(headers=["位号", "口径"], rows=[["P-101", "DN50"], ["P-102", "DN80"]])]


def test_docx_is_valid_zip_with_document_xml():
    b = render_docx(title="设备一览表", blocks=B, style=ReportStyle(), context={})
    z = zipfile.ZipFile(io.BytesIO(b))
    assert "word/document.xml" in z.namelist()


def test_xlsx_is_valid_zip_with_sheet_xml():
    b = render_xlsx(title="设备一览表", blocks=B, style=ReportStyle(), context={})
    z = zipfile.ZipFile(io.BytesIO(b))
    assert "xl/worksheet.xml" in z.namelist()


def test_xlsx_uses_constant_memory_and_streams(tmp_path):
    """10000 行必须能出（SPEC ≤10s / <100MB），验证 constant_memory 路径不炸。"""
    rows = [[f"P-{i}", "DN50"] for i in range(10000)]
    b = render_xlsx(title="大表", blocks=[TableBlock(headers=["位号", "口径"], rows=rows)],
                    style=ReportStyle(), context={})
    assert len(b) > 100_000
```

- [ ] **Step 2: 跑测试确认失败** → `ModuleNotFoundError`

- [ ] **Step 3: 实现 `renderer_xlsx.py`**

```python
"""XLSX 渲染器 —— XlsxWriter 流式写入（ADR-P8-001：不用 openpyxl 模板填充）。

`constant_memory=True` 是硬要求：100 万行内存约 80MB（SPEC Global Constraints）。
副作用：constant_memory 模式下必须**按行顺序写**，不能回头改前面的行；
冻结窗格与自动筛选改用 worksheet 的 `freeze_panes()` 在写完后设置。
"""
from __future__ import annotations

import io

import xlsxwriter

from app.services.report.blocks import (Block, HeadingBlock, KeyValueBlock,
                                        PageBreakBlock, TableBlock, _cell_text,
                                        assumed_header)
from app.services.report.style import ReportStyle


def render_xlsx(*, title: str, blocks: list[Block], style: ReportStyle,
                context: dict) -> bytes:
    buf = io.BytesIO()
    wb = xlsxwriter.Workbook(buf, {"in_memory": True, "constant_memory": True})
    ws = wb.add_worksheet("报表")
    hdr = wb.add_format({"bold": style.table.header_bold,
                         "bg_color": style.table.header_bg, "border": 1,
                         "valign": "top", "text_wrap": True})
    cell = wb.add_format({"border": 1, "valign": "top", "text_wrap": True})
    assumed = wb.add_format({"border": 1, "valign": "top", "text_wrap": True,
                             "font_color": style.assumption_color})
    head = wb.add_format({"bold": True, "font_size": style.font_size_heading})
    mc = style.table.max_cell_chars

    ws.write(0, 0, title, head)
    r = 2
    for b in blocks:
        if isinstance(b, HeadingBlock):
            ws.write(r, 0, b.text, head); r += 1
        elif isinstance(b, PageBreakBlock):
            r += 1
        elif isinstance(b, KeyValueBlock):
            for k, v in b.rows:
                ws.write(r, 0, str(k), hdr)
                ws.write(r, 1, _cell_text(v, mc), cell); r += 1
        elif isinstance(b, TableBlock):
            for ci, h in enumerate(b.headers):
                ws.write(r, ci, assumed_header(h, ci in b.assumed_cols,
                                               style.assumption_mark), hdr)
            r += 1
            for row in b.rows:
                for ci, v in enumerate(row):
                    fmt = assumed if ci in b.assumed_cols else cell
                    ws.write(r, ci, _cell_text(v, mc), fmt)
                r += 1
            ws.freeze_panes(r - len(b.rows) - 1, 0)
    wb.close()
    return buf.getvalue()
```

- [ ] **Step 4: 实现 `renderer_docx.py`**

```python
"""DOCX 渲染器 —— python-docx 直接构建（ADR-P8-001：不用 docxtpl 模板填充）。

表头页脚按 `style.header` / `style.footer` 写入 section，
占位符在 `context` 齐备时替换，未替换的**原样保留**（便于发现拼写错误）。
"""
from __future__ import annotations

import io

from docx import Document
from docx.enum.section import WD_ORIENT
from docx.shared import Mm, Pt

from app.services.report.blocks import (Block, HeadingBlock, KeyValueBlock,
                                        PageBreakBlock, TableBlock, _cell_text,
                                        assumed_header)
from app.services.report.style import ReportStyle

_PAGESIZES = {"A4": (210, 297), "A3": (297, 420), "Letter": (215.9, 279.4)}


def _fill(text: str, context: dict) -> str:
    for k, v in context.items():
        text = text.replace("{{" + k + "}}", "" if v is None else str(v))
    return text


def render_docx(*, title: str, blocks: list[Block], style: ReportStyle,
                context: dict) -> bytes:
    doc = Document()
    sec = doc.sections[0]
    w, h = _PAGESIZES[style.page_size]
    if style.orientation == "landscape":
        w, h = h, w
        sec.orientation = WD_ORIENT.LANDSCAPE
    sec.page_width, sec.page_height = Mm(w), Mm(h)
    sec.top_margin, sec.bottom_margin = Mm(style.margins.top), Mm(style.margins.bottom)
    sec.left_margin, sec.right_margin = Mm(style.margins.left), Mm(style.margins.right)
    sec.header.paragraphs[0].text = _fill(style.header.left, context)
    sec.footer.paragraphs[0].text = _fill(style.footer.left, context)

    doc.add_heading(title, level=1)
    mc = style.table.max_cell_chars
    for b in blocks:
        if isinstance(b, HeadingBlock):
            doc.add_heading(b.text, level=min(b.level, 4))
        elif isinstance(b, PageBreakBlock):
            doc.add_page_break()
        elif isinstance(b, KeyValueBlock):
            t = doc.add_table(rows=0, cols=2); t.style = "Table Grid"
            for k, v in b.rows:
                c = t.add_row().cells
                c[0].text, c[1].text = str(k), _cell_text(v, mc)
        elif isinstance(b, TableBlock):
            t = doc.add_table(rows=1, cols=len(b.headers)); t.style = "Table Grid"
            for i, h in enumerate(b.headers):
                t.rows[0].cells[i].text = assumed_header(
                    h, i in b.assumed_cols, style.assumption_mark)
            for row in b.rows:
                cells = t.add_row().cells
                for i, v in enumerate(row):
                    cells[i].text = _cell_text(v, mc)
    buf = io.BytesIO(); doc.save(buf)
    return buf.getvalue()
```

- [ ] **Step 5: 跑测试确认通过** → 3 passed

- [ ] **Step 6: 提交**

```bash
git add app/services/report/renderer_docx.py app/services/report/renderer_xlsx.py tests/services/report/test_renderers.py pyproject.toml
git commit -m "feat(report): DOCX / XLSX 渲染器（python-docx / XlsxWriter 流式）"
```

---

## Task 5: 数据源注册表 + 10 类报表 collector

**Files:**
- Create: `pcs-backend/app/services/report/datasource_registry.py`
- Create: `pcs-backend/app/services/report/collector.py`
- Test: `pcs-backend/tests/services/report/test_collector.py`

**Interfaces:**
- Consumes: ORM 各 `*_results` 表
- Produces:
  - `DATASOURCES: dict[str, DataSource]`，`DataSource(key, label, model, fields: dict[str, FieldSpec])`
  - `JOINS: tuple[JoinRule, ...]`（SPEC §1.3 的 5 对）
  - `collect(report_type: str, *, project_id, record_ids) -> list[Block]`

- [ ] **Step 1: 写失败测试**

```python
# tests/services/report/test_collector.py
import pytest
from app.services.exceptions import PcsError
from app.services.report.datasource_registry import JOINS, join_key_for
from app.services.report.collector import collect, REPORT_TYPES

def test_ten_report_types_registered():
    assert len(REPORT_TYPES) == 10


def test_join_rules_match_spec_whitelist():
    """SPEC §1.3 只批了 5 对 JOIN，多一条都不行。"""
    assert len(JOINS) == 5
    assert join_key_for("EQUIP_LIST", "PUMP_RESULTS") == ("tag_number", "tag_number")


def test_unsupported_join_raises_explicit_error():
    with pytest.raises(PcsError) as e:
        join_key_for("EQUIP_LIST", "STREAMS")
    assert e.value.code == "REPORT_BUILDER_JOIN_NOT_SUPPORTED"


def test_collect_unknown_report_type_raises():
    with pytest.raises(PcsError) as e:
        collect("NOPE", project_id=None, record_ids=[])
    assert e.value.code == "REPORT_TYPE_UNKNOWN"
```

- [ ] **Step 2: 跑测试确认失败** → `ModuleNotFoundError`

- [ ] **Step 3: 实现** —— 写出 `datasource_registry.py` 完整内容，13 个数据源按 SPEC §3.2.2(1) 的字段清单逐条登记为 `FieldSpec(name, type, label)`，`type ∈ {"string","number","date","enum"}`；`join_key_for(a, b)` 只查 `JOINS` 白名单，命中返回 `(left_col, right_col)`，未命中抛 `REPORT_BUILDER_JOIN_NOT_SUPPORTED`（status 400）。

- [ ] **Step 4: 实现 `collector.py`** —— 10 个 `report_type` 常量与各自的数据收集函数，**每个返回 `list[Block]`**。`EQUIP_LIST.vendor_id → SUPPLIERS.supplier_id` 那条按 SPEC §1.3：列不存在时降级为 `vendor = supplier_name` 并发 WARN 级日志（用 `logging.warning`，不用 `print`）。

- [ ] **Step 5: 跑测试确认通过** → 4 passed

- [ ] **Step 6: 提交**

```bash
git add app/services/report/datasource_registry.py app/services/report/collector.py tests/services/report/test_collector.py
git commit -m "feat(report): 数据源注册表 + JOIN 白名单 + 10 类报表 collector"
```

---

## Task 6: 二维码 + 生成编排 + 文件存储

**Files:**
- Create: `pcs-backend/app/services/report/qr.py`
- Create: `pcs-backend/app/services/report/report_service.py`
- Test: `pcs-backend/tests/services/report/test_report_service.py`

**Interfaces:**
- Consumes: Task 1/3/4/5 全部
- Produces: `generate(*, report_type, project_id, record_ids, output_format, style, ctx) -> ReportFile`

- [ ] **Step 1: 写失败测试**

```python
# tests/services/report/test_report_service.py
import pytest
from app.services.report.report_service import generate
from app.services.report.style import ReportStyle

@pytest.mark.asyncio
async def test_same_content_twice_reuses_one_file(db, project_id):
    """Review Focus #5：内容哈希命名 → 重复生成复用同文件。"""
    a = await generate(report_type="EQUIPMENT_LIST", project_id=project_id,
                       record_ids=[], output_format="pdf",
                       style=ReportStyle(), ctx={})
    b = await generate(report_type="EQUIPMENT_LIST", project_id=project_id,
                       record_ids=[], output_format="pdf",
                       style=ReportStyle(), ctx={})
    assert a.report_file_id == b.report_file_id
    from sqlalchemy import func, select
    n = await db.scalar(select(func.count()).select_from(a.__table__))
    assert n == 1


@pytest.mark.asyncio
async def test_failure_still_writes_report_failed_audit(db, project_id, monkeypatch):
    """SPEC §六验收明写「失败也记录」。漏了这条测试就发现不了。"""
    async def boom(*a, **k):
        raise RuntimeError("渲染炸了")
    monkeypatch.setattr("app.services.report.report_service._render", boom)
    with pytest.raises(RuntimeError):
        await generate(report_type="EQUIPMENT_LIST", project_id=project_id,
                       record_ids=[], output_format="pdf",
                       style=ReportStyle(), ctx={})
    acts = [a for a in db.actions if getattr(a, "action", None) == "REPORT_FAILED"]
    assert acts, "失败路径必须写 REPORT_FAILED 审计"


@pytest.mark.asyncio
async def test_disk_write_failure_raises_pcserror_not_raw_oserror(db, project_id, monkeypatch):
    """磁盘满 / 权限不足 → 必须是 PcsError(REPORT_STORAGE_FAILED)，
    不能把裸 OSError 抛到 API 层变成 500 之外的奇怪响应。"""
    def boom(*a, **k):
        raise OSError(28, "No space left on device")
    monkeypatch.setattr("app.services.report.report_service._write_file", boom)
    with pytest.raises(PcsError) as e:
        await generate(report_type="EQUIPMENT_LIST", project_id=project_id,
                       record_ids=[], output_format="pdf",
                       style=ReportStyle(), ctx={})
    assert e.value.code == "REPORT_STORAGE_FAILED"


@pytest.mark.asyncio
async def test_assumed_input_adds_declaration_page(db, project_id, assumed_record):
    """SPEC §3.2.1(4)：存在 ASSUMED/NOT_STARTED 输入项 → 自动加声明页。"""
    out = await generate(report_type="EQUIPMENT_LIST", project_id=project_id,
                         record_ids=[assumed_record], output_format="pdf",
                         style=ReportStyle(), ctx={})
    assert out.has_assumption_page is True
```

- [ ] **Step 2: 跑测试确认失败** → `ModuleNotFoundError`

- [ ] **Step 3: 实现 `qr.py`**

```python
"""二维码内容组装 —— SPEC §3.2.1(3)。

内容 = doc_no + Rev + 版本目的 + 生成时间 + 绑定记录哈希摘要，SHA-256。
指向 `/api/v1/report/verify/{report_id}`，扫描后比对 DB 中的原始哈希。
"""
from __future__ import annotations

import datetime
import hashlib
import json


def build_qr_payload(*, report_id: str, doc_no: str, rev: str,
                     version_purpose: str, record_hashes: list[str],
                     verify_base_url: str) -> str:
    """组装二维码文本载荷。record_hashes 为空也能生成（此时摘要为 sha256(b'')）。"""
    body = "|".join(sorted(record_hashes))
    digest = hashlib.sha256(body.encode("utf-8")).hexdigest()
    meta = {
        "report_id": report_id,
        "doc_no": doc_no,
        "rev": rev,
        "version_purpose": version_purpose,
        "generated_at": datetime.datetime.now(datetime.UTC).isoformat(),
        "record_hash_digest": digest,
    }
    return f"{verify_base_url.rstrip('/')}/api/v1/report/verify/{report_id}#" + \
        json.dumps(meta, ensure_ascii=False, separators=(",", ":"))
```

- [ ] **Step 4: 实现 `report_service.py`** —— 编排：查样式 → `collect()` → 按 `output_format` 调对应 renderer → 算内容哈希 → upsert `ReportFile` → 写 `AuditService.write(action=REPORT_GENERATED, ...)`。**失败路径也必须写 `REPORT_FAILED` 审计**（SPEC 验收：「失败也记录」）。

- [ ] **Step 5: 跑测试确认通过** → 2 passed

- [ ] **Step 6: 提交**

```bash
git add app/services/report/qr.py app/services/report/report_service.py tests/services/report/test_report_service.py
git commit -m "feat(report): 二维码载荷 + 生成编排 + 内容哈希文件存储"
```

---

## Task 7: ARQ 异步任务 + 状态查询

**Files:**
- Create: `pcs-backend/app/workers/report_tasks.py`
- Modify: `pcs-backend/app/workers/worker.py:61`（`functions` 列表追加）
- Modify: `pcs-backend/app/models/enums.py:222`（`AuditAction` 追加 4 个 REPORT_* 值）
- Test: `pcs-backend/tests/workers/test_report_tasks.py`

**Interfaces:**
- Consumes: Task 6 `generate()`
- Produces: `generate_report_task(ctx: dict, *, report_type, project_id, record_ids, output_format, style_json, ctx_vars) -> str`

- [ ] **Step 1: 写失败测试**

```python
# tests/workers/test_report_tasks.py
import pytest
from app.workers.report_tasks import generate_report_task

@pytest.mark.asyncio
async def test_task_persists_status_and_returns_file_id(db, project_id, monkeypatch):
    out = await generate_report_task(
        {"db": db},
        report_type="EQUIPMENT_LIST", project_id=str(project_id),
        record_ids=[], output_format="pdf", style_json={}, ctx_vars={},
    )
    assert isinstance(out, str) and len(out) == 36   # uuid4 字符串


@pytest.mark.asyncio
async def test_task_failure_sets_failed_status_and_writes_audit(db, project_id, monkeypatch):
    async def boom(*a, **k):
        raise RuntimeError("渲染炸了")
    monkeypatch.setattr("app.workers.report_tasks.generate", boom)
    with pytest.raises(RuntimeError):
        await generate_report_task({"db": db}, report_type="EQUIPMENT_LIST",
                                   project_id=str(project_id), record_ids=[],
                                   output_format="pdf", style_json={}, ctx_vars={})
    # 断言：状态置 FAILED + AuditAction.REPORT_FAILED 被写入
```

@pytest.mark.asyncio
async def test_stale_pending_task_is_reclaimed(db, project_id):
    """**ARQ 进程被 OOM kill，状态会永远卡在 PENDING，前端无限轮询。**

    TODO-016 记「ARQ 失败路径覆盖为零」，这条正好落在那个已知空洞上。
    实现要求：任务带 `heartbeat_at`；启动时 + 定时扫描 `status=PENDING 且
    heartbeat_at 超过 N 分钟` → 置 FAILED 并写审计。
    """
    stale = await _make_task_row(db, project_id, status="PENDING",
                                 heartbeat_at=dt.datetime.now(dt.UTC) - dt.timedelta(minutes=30))
    await reclaim_stale_tasks(db, older_than_minutes=15)
    await db.refresh(stale)
    assert stale.status == "FAILED"
    assert stale.error_message


@pytest.mark.asyncio
async def test_fresh_pending_task_is_not_reclaimed(db, project_id):
    ok = await _make_task_row(db, project_id, status="PENDING",
                              heartbeat_at=dt.datetime.now(dt.UTC))
    await reclaim_stale_tasks(db, older_than_minutes=15)
    await db.refresh(ok)
    assert ok.status == "PENDING", "新鲜的 PENDING 不能被误杀"
```

- [ ] **Step 2: 跑测试确认失败** → `ModuleNotFoundError`

- [ ] **Step 3: 追加 `AuditAction` 枚举值**（在 `app/models/enums.py` 的 `AuditAction` 末尾，值必须 ≤50 字符，有 `test_audit_action_max_length_50` 断言）

```python
    # === P8 报表（ADR-P8-001 路线）===
    REPORT_GENERATED = "REPORT_GENERATED"
    REPORT_DOWNLOADED = "REPORT_DOWNLOADED"
    REPORT_FAILED = "REPORT_FAILED"
    REPORT_EXECUTED = "REPORT_EXECUTED"
```

- [ ] **Step 4: 实现 `report_tasks.py`** —— 参照 `app/workers/workspace_tasks.py` 的签名兼容处理（该文件第 35 行注释说明「兼容旧 ARQ 任务签名」），`max_tries=3`。

- [ ] **Step 5: 注册进 `worker.py:61` 的 `functions` 列表，并把 `max_jobs` 提上去**

PDF 渲染（ReportLab）与 XLSX `constant_memory` 都是 CPU 密集。现 `max_jobs = 4`
且与 workspace 清理任务共用 —— 并发报表生成时排队，叠加上面「PENDING 无人回收」
的问题会极难排查。**建议单独给报表任务预留容量**（调 `max_jobs` 或分独立 worker）。

- [ ] **Step 5b: 加 stale 任务回收**（`reclaim_stale_tasks`）—— 见 Step 1 的两个测试

- [ ] **Step 6: 跑测试确认通过** → 2 passed

- [ ] **Step 7: 提交**

```bash
git add app/workers/report_tasks.py app/workers/worker.py app/models/enums.py tests/workers/test_report_tasks.py
git commit -m "feat(report): ARQ 异步生成任务 + REPORT_* 审计动作"
```

---

## Task 8: API 路由

**Files:**
- Create: `pcs-backend/app/schemas/report.py`
- Create: `pcs-backend/app/api/v1/report.py`
- Modify: `pcs-backend/app/api/v1/__init__.py`（`api_router.include_router(report_router)`）
- Test: `pcs-backend/tests/api/v1/test_report.py`

**Interfaces:**
- Consumes: Task 6/7
- Produces: 路由前缀 `/api/v1/report`，端点见下

- [ ] **Step 1: 写失败测试**

```python
# tests/api/v1/test_report.py
async def test_generate_returns_202_and_task_id(client, pc_token, project_id):
    r = await client.post("/api/v1/report/generate",
                          json={"report_type": "EQUIPMENT_LIST",
                                "project_id": str(project_id),
                                "record_ids": [], "output_format": "pdf"},
                          headers=_auth(pc_token))
    assert r.status_code == 202
    assert r.json()["task_id"]


async def test_download_without_project_access_is_403(client, other_token, report_file):
    r = await client.get(f"/api/v1/report/{report_file.report_file_id}/download",
                         headers=_auth(other_token))
    assert r.status_code == 403


async def test_verify_endpoint_returns_hash_match(client, report_file):
    r = await client.get(f"/api/v1/report/verify/{report_file.report_file_id}")
    assert r.status_code == 200 and r.json()["match"] is True


async def test_verify_endpoint_is_rate_limited(client, report_file):
    """SPEC §六验收明写「二维码验证端点限流」。"""
    codes = [(await client.get(
        f"/api/v1/report/verify/{report_file.report_file_id}")).status_code
        for _ in range(REPORT_VERIFY_RATE_LIMIT + 5)]
    assert 429 in codes, f"验证端点无限流：{codes.count(200)} 次 200 全部通过"
    # 限流后仍应能恢复
    assert codes[-1] in (200, 429)


async def test_verify_endpoint_is_unauthenticated(client, report_file):
    """扫码验证必须免登录（现场人员用手机扫），否则二维码功能等于不存在。"""
    r = await client.get(f"/api/v1/report/verify/{report_file.report_file_id}")
    assert r.status_code == 200


async def test_response_schemas_have_no_bare_object():
    """P9A-DLV-010 硬约束：报表端点响应不得含裸 object/array。"""
    import importlib.util
    from app.main import app
    # 复用已有闸的判定函数，不另写一套口径（scripts/check_openapi_payload_coverage.py）
    _spec = importlib.util.spec_from_file_location(
        "_cov", "scripts/check_openapi_payload_coverage.py")
    _cov = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(_cov)
    bare_fields_in = _cov._is_bare
    for path, spec in app.openapi()["paths"].items():
        if not path.startswith("/api/v1/report"):
            continue
        for method, op in spec.items():
            if method not in ("get", "post", "put", "delete", "patch"):
                continue
            for code, resp in op.get("responses", {}).items():
                if not str(code).startswith("2"):
                    continue
                sch = resp.get("content", {}).get("application/json", {}).get("schema", {})
                assert not bare_fields_in(sch), f"{method.upper()} {path} 响应含裸 object/array"
```

- [ ] **Step 2: 跑测试确认失败** → 404

- [ ] **Step 3: 实现 `app/schemas/report.py`** —— 全部响应模型**显式声明字段**，禁止 `dict` / `Any` 直出。

- [ ] **Step 4: 实现 `app/api/v1/report.py`** —— 端点：`POST /generate`(202) / `GET /{id}/status` / `GET /{id}/download` / `GET /styles?report_type=` / `GET /styles/{id}` / `GET /verify/{id}`。下载走 `_guard.check_project_access_or_404`（与 `pipe_codes.py` 同模式）。

- [ ] **Step 5: 注册路由** —— `app/api/v1/__init__.py` 加 `from app.api.v1.report import router as report_router` + `api_router.include_router(report_router)`

- [ ] **Step 6: 跑测试 + 契约闸**

```bash
uv run pytest tests/api/v1/test_report.py -v
uv run python scripts/check_openapi_payload_coverage.py   # 裸字段数必须仍为 71
```

- [ ] **Step 7: 提交**

```bash
git add app/schemas/report.py app/api/v1/report.py app/api/v1/__init__.py tests/api/v1/test_report.py
git commit -m "feat(api): /api/v1/report 路由（零裸 object 响应）"
```

---

## Task 9: 测试 seed + Golden 文件

**Files:**
- Create: `pcs-backend/tests/fixtures/report/seed.py`
- Create: `pcs-backend/tests/fixtures/report/__init__.py`
- Test: `pcs-backend/tests/services/report/test_golden.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/services/report/test_golden.py
import pytest
from app.services.report.collector import REPORT_TYPES
from app.services.report.report_service import generate
from app.services.report.style import ReportStyle
from tests.fixtures.report.seed import make_report_seed

@pytest.mark.parametrize("report_type", sorted(REPORT_TYPES))
@pytest.mark.asyncio
async def test_golden_bytes_stable(db, project_id, report_type, golden_dir):
    ids = make_report_seed(db, project_id, report_type)
    out = await generate(report_type=report_type, project_id=project_id, record_ids=ids,
                         output_format="pdf", style=ReportStyle(), ctx={})
    got = open(out.absolute_path, "rb").read()
    want = (golden_dir / f"{report_type}.pdf").read_bytes()
    assert _normalize_pdf(got) == _normalize_pdf(want), f"{report_type} Golden 不一致"
```

**⚠️ PDF 二进制不可直接比对**（含时间戳与文档 ID）。`_normalize_pdf()` 必须用 `pypdf` 抽出**文本内容**再比：

```python
def _normalize_pdf(data: bytes) -> str:
    import io
    from pypdf import PdfReader
    return "\n".join(p.extract_text() for p in PdfReader(io.BytesIO(data)).pages)
```

- [ ] **Step 2: 跑测试确认失败** → seed 不存在

- [ ] **Step 3: 实现 `seed.py`** —— `make_report_seed(db, project_id, report_type) -> list[str]`，10 类报表各 2–3 组。**必须走 ORM 构造**（conftest 建表从 metadata，ORM 写入才有效），且满足 `TaggedRecordMixin` 的 `tag_number` NOT NULL 等约束。

- [ ] **Step 4: 生成 Golden 并提交**

```bash
uv run pytest tests/services/report/test_golden.py --update-golden
git add tests/fixtures/report/ tests/golden/report/
git commit -m "test(report): 10 类报表 seed + Golden 基线"
```

- [ ] **Step 5: 复跑确认稳定**（关键：Golden 必须第二次跑仍绿，否则说明输出含不稳定内容）

```bash
uv run pytest tests/services/report/test_golden.py -v
```

---

## Task 10: 性能基准

**Files:**
- Create: `pcs-backend/tests/benchmarks/test_report_perf.py`
- Modify: `pcs-backend/pyproject.toml`（加 `pytest-benchmark`）

- [ ] **Step 1: 写性能测试（绝对预算，不引入 pytest-benchmark）**

```python
# tests/benchmarks/test_report_perf.py
"""SPEC §3.3.1 性能指标 —— **绝对阈值断言**。

刻意不用 pytest-benchmark：它的相对阈值（±X%）在 CI 共享 runner 上会因负载
波动频繁误报，几次之后就会被 disable —— 这是 cerebrum 里「守门恒报噪声 =
狼来了」的另一个版本。要曲线就本地手动跑，这个文件只管守 SPEC 的三个数字。
"""
import time

import pytest

SIMPLE_LIMIT_S, COMPLEX_LIMIT_S, BUILDER_10K_LIMIT_S = 5, 15, 10


@pytest.mark.asyncio
async def test_simple_report_under_5s(db, project_id, simple_ids):
    t0 = time.perf_counter()
    await _gen_simple(db, project_id, simple_ids)
    el = time.perf_counter() - t0
    assert el < SIMPLE_LIMIT_S, f"简单报表 {el:.2f}s > {SIMPLE_LIMIT_S}s"


@pytest.mark.asyncio
async def test_complex_report_under_15s(db, project_id, complex_ids):
    t0 = time.perf_counter()
    await _gen_complex(db, project_id, complex_ids)
    el = time.perf_counter() - t0
    assert el < COMPLEX_LIMIT_S, f"复杂报表 {el:.2f}s > {COMPLEX_LIMIT_S}s"


@pytest.mark.asyncio
async def test_builder_10k_rows_under_10s(db, project_id, big_def):
    """b7 已改为 ARQ 异步；此测的是**任务体本身**的耗时，不含队列等待。"""
    t0 = time.perf_counter()
    await _execute_rows(db, project_id, big_def, max_rows=10000)
    el = time.perf_counter() - t0
    assert el < BUILDER_10K_LIMIT_S, f"1 万行执行 {el:.2f}s > {BUILDER_10K_LIMIT_S}s"
```

- [ ] **Step 2: 跑测试确认当前不满足**（首次大概率红 —— 这正是要先测的意义）

- [ ] **Step 3: 优化至达标** —— 优先：`constant_memory` 已在 Task 4；字体注册结果**进程内缓存**（`_register_font` 每次 `getRegisteredFontNames()` 已短路，确认命中）；ReportLab 复用 `SimpleDocTemplate` 样式对象。

- [ ] **Step 4: 提交**

```bash
git add tests/benchmarks/ pyproject.toml
git commit -m "perf(report): 性能基准纳入 CI 阈值（简单≤5s 复杂≤15s 1万行≤10s）"
```

---

# Phase 2 — P8b REPORT_BUILDER（任务级，执行前需按本文格式展开为步骤）

依赖：Task 1（样式）、Task 5（数据源注册表）。**Task 8 完成后才可接前端。**

| # | 任务 | 产出 | 验收 |
|---|---|---|---|
| b1 | 数据源注册表 API | `GET /report-builder/datasources` 返回 13 源字段树 | 字段树与 `datasource_registry.DATASOURCES` 一致 |
| b2 | 定义 CRUD | `ReportDefinition` 模型 + 4 端点 | DRAFT 仅创建人可见 |
| b3 | 版本与审批 | publish 流程；改已发布定义自动 `version` +1 | 5 态流转测试通过 |
| b4 | 字段选择器后端 | 别名/排序/显隐持久化到 `definition_json` | 往返一致 |
| b5 | 过滤条件引擎 | **16 个操作符**全实现；AND/OR 嵌套 | 每操作符 1 测试；**空 value 返回空集而非全表**（Review Focus #3）；注入尝试返回空结果；collector/b5 一律批量 SELECT（Task 5 决策） |
| b6 | JOIN 引擎 | 5 对白名单 JOIN | 不支持的对报 `REPORT_BUILDER_JOIN_NOT_SUPPORTED` |
| b7 | 执行引擎（**ARQ 异步，2026-10-08 审查决策**） | `POST /execute` 返回 202 + task_id；参数化 SQL；10000 行 ≤10s（测**任务体**耗时）；临时调整不改定义 | 条件快照写 `report_execution_logs`；**并发执行时 API 仍可响应**（同步 10s 查询会阻塞整个 event loop） |
| b8 | 导出 | Excel/CSV/PDF；非发布件时间戳水印；DEMO 水印 + 定义数限 3 | 水印可见；限制生效 |
| b9 | 审计 | 每次执行写 `REPORT_EXECUTED` | 审计行含条件快照 + 行数 |
| b10–b12 | 前端三件套 | 定义编辑器 / 执行面板 / 管理列表 | 按 `docs/PCS-UI-SPEC.md` V1.0 |

**b5 的 16 个操作符**（SPEC §3.2.2(4)）：`EQ NEQ GT GTE LT LTE IN NOT_IN CONTAINS STARTS_WITH ENDS_WITH IS_NULL IS_NOT_NULL BETWEEN LIKE`

⚠️ **b10–b12 前置**：TODO-039/041 已重定范围（见 `TODOS.md`），**「7 个 mock type 文件改 import 自 ./api」的前提不成立** —— 28/31 个 interface 在 OpenAPI 里无对应 schema，前后端字段名与**单位**都不同（`p_mpa` ↔ `P_Pa`）。前端开工前须按 TODOS.md 重新评估。

---

# Phase 3 — P8c HEAT DETAIL + 样式 UI（任务级）

| # | 任务 | 产出 | 验收 |
|---|---|---|---|
| c1 | HEAT 字段映射 | `heat_results` 39 字段 + `ache_params` JSONB → HEAT 数据源 | 字段清单与 ORM 逐条对齐 |
| c2 | BASIC/DETAIL 双样式 | BASIC 9 字段（ReportStyle-A）；DETAIL 39 字段（ReportStyle-B） | 两套样式均可渲染 |
| c3 | ADR-0028 | **已完成**，见 `docs/adr/HEAT 报表双 detail_level 模板裁决.md` | — |
| c4 | HTRI 兼容测试 | `121-A-101.xls`(33 列) + `131-E-102-EOR.xls`(23 列) 覆盖比对 | 差异清单 |
| c5 | 覆盖率报告 | DETAIL 字段覆盖率自动计算 | **≥95%** |
| c6 | 样式管理 UI | ReportStyle 可视化编辑 + 实时预览 | 不涉及占位符绑定（已废止） |
| c7 | JOIN 扩展 | 按需开放更多 JOIN 对 | 每对 1 测试 |

---

## 尚未解决的问题

1. **Task 2 迁移的 4 张表 DDL 未逐字展开** —— 计划里给了「怎么拿到约束名」的命令和不可省略的三条规则（约束名走 convention、FK 必须嵌 Column 内、CHECK 避开 PG 专有语法），但 `op.create_table` 的具体 `sa.Column` 列表要实现者照 ORM 抄。这是刻意的：抄一遍必然与 ORM 不同步，不如给规则让他从 ORM 生成。
2. **Task 3/4 的 `_decorate` / 占位符替换留了骨架并标了「必须补完」** —— 因为二维码位置、页眉页脚格式属于 SPEC 已定但实现自由度高的部分，展开成完整代码会锁死样式而样式恰恰是 P8c 要开放给用户改的。
3. **PDF Golden 的稳定性未验证** —— `_normalize_pdf` 抽文本比对是本计划的设计，但如果渲染里有时间戳/ID 进入文本层，Golden 会飘。Task 9 Step 5 的「复跑确认稳定」就是为这个设的卡点，**第一次跑可能会红，不要跳过**。
4. **`REPORT_VERIFY` 端点的限流未设计** —— SPEC §六 验收要求「二维码验证端点限流」，但没给阈值与算法。需在 Task 8 补，或单列 TODO。
6. **PDF 页数（`{{pages}}`）拿不到** —— ReportLab 需要两遍渲染才能知道总页数。本计划未处理，Task 3 需确认；若不做，`{{pages}}` 占位符应从 SPEC §4.1 移除。
7. **P8b/P8c 是任务级而非步骤级** —— 按 CLAUDE.md「计划必须极具简洁」压缩。执行前需按 Phase 1 的格式展开，否则不满足 writing-plans 的「无占位符」要求。
8. **`suppliers.vendor_id` 列是否存在未核实** —— SPEC §1.3 已给降级方案（不存在则用 `vendor = supplier_name` + WARN），Task 5 Step 4 照做即可，但降级路径应补测试。
