"""P7 Task S1-2: equipment_list 补 SourceService 列（SPEC V1.4 §3.2.1（2）来源组）.

背景（P7 Complete Implementation Plan V2.2 Task S1-2，R=1 source-verify 修正）:

- `EquipmentList` ORM 早已存在（app/models/equipment.py:58，96 列），表
  `equipment_list` 由 dd47298c9c38 建表 + p1_sprint3_equipment_status_columns
  补 3 状态列。plan brief 的「新建 app/models/equip_list.py 重建 EquipmentList」
  前提不成立（同一 MetaData 重复映射 equipment_list 会在 import 期抛
  InvalidRequestError），故本迁移按「加法补丁」执行：只补 V1.4 唯一缺口。
- V1.4 缺口：`source_service`（来源组 V1.4 新增字段，区分同模块多子服务）。
  SPEC §3.2.1（2）来源组 = SourceModule + SourceRecordID + **SourceService**
  + InPackage + DataSources；既有 ORM 已含其余 4 项。
- 业务动机：SPEC §3.2.1（1）+ §4.3 规定 C-08/C-07/C-10 三个 VESSEL 子服务
  （two_phase_separator_sizing_service / two_phase_separator_service /
  three_phase_separator_service）的设备记录共用 TypeCode D/V/T/R，仅靠
  source_service 区分。

字段契约：`String(64)` + 可空。历史行无来源服务，不回填（回填属 S1-4 同步服务
职责，不在迁移内做数据推断）。

本迁移不含 UNIQUE(project_id, tag_number)——controller 已终裁（2026-10-01）：
既有 TaggedRecordMixin 文档（app/models/mixins.py:127-132）明确「(project_id,
tag_number) 唯一性由服务层强制（避免 autogenerate 跨表错挂 bug）」，D2 裁决 2A
的问题前提（既有 ORM 已有 tag_number unique=True）不成立。并发语义由 S1-4 的
advisory lock 承担。
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "p7_s1_001"
down_revision: str | None = "p5_0_1b_1_thermosiphon"
branch_labels: str | None = None
depends_on: str | None = None

_TABLE = "equipment_list"
_COLUMN = "source_service"
_COMMENT = (
    "V1.4 新增（SPEC §3.2.1（2）来源组）：区分同模块多子服务，"
    "如 C-08/C-07/C-10 三个 VESSEL 子服务共用 TypeCode D/V/T/R"
)


def upgrade() -> None:
    """equipment_list 加 source_service 列（V1.4 溯源三件套之三）。"""
    op.add_column(
        _TABLE,
        sa.Column(_COLUMN, sa.String(length=64), nullable=True, comment=_COMMENT),
    )


def downgrade() -> None:
    """删 source_service 列（与 upgrade 互逆）。

    历史行本就无来源服务值，故 downgrade 不丢业务数据；仅回退 V1.4 schema 增量。
    """
    op.drop_column(_TABLE, _COLUMN)
