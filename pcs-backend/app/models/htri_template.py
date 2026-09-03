import uuid

from sqlalchemy import Integer, String, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import TimestampMixin

VALID_HTRI_DEVICE_TYPES = {"ACHE", "SHELL_TUBE"}

class HtriTemplateSchema(TimestampMixin, Base):
    """HTRI 解析模板 schema（V1.4 P2-OPEN-005）。"""
    __tablename__ = "htri_template_schemas"
    schema_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    device_type: Mapped[str] = mapped_column(String(20), comment="ACHE/SHELL_TUBE")
    column_count: Mapped[int] = mapped_column(Integer)
    columns_json: Mapped[dict] = mapped_column(JSONB,
        comment="[{name, type, required, unit}, ...]")
    tema_type: Mapped[str | None] = mapped_column(String(10), nullable=True,
        comment="BEM/AES/AKT（仅 SHELL_TUBE 适用）")
    version: Mapped[str] = mapped_column(String(50))
    source_file_ref: Mapped[str | None] = mapped_column(String(200),
        comment="原始 .xls 文件引用")
