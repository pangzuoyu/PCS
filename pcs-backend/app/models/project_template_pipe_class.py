"""ProjectTemplate ↔ PipeClass 多对多关联表（SUP-002 §15 / PC-OPEN-04）。"""
from __future__ import annotations

from sqlalchemy import ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import TimestampMixin


class ProjectTemplatePipeClass(TimestampMixin, Base):
    """项目模板↔管号等级多对多关联（project_template_pipe_classes 表，PC-OPEN-04）。

    业务：复合 PK (template_id, class_id)；一个项目模板可绑定多个管号等级
    （A/B/C 类），一个管号等级可被多个模板引用。
    """

    __tablename__ = "project_template_pipe_classes"

    template_id: Mapped[Uuid] = mapped_column(
        Uuid, ForeignKey("project_templates.template_id"), primary_key=True,
    )
    class_id: Mapped[str] = mapped_column(
        String(50), ForeignKey("pipe_classes.class_id"), primary_key=True,
    )