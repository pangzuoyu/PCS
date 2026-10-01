"""S1-3 EquipmentTypeCodeService — 设备类型代码 seed + 查询。

Per SPEC V1.4 §3.2.1 (3) + plan brief Step 3：seed 既有 equipment_type_codes
表（公司级默认，project_id NULL）~30 codes 核心子集。

80 codes 全清单属 Sprint 1 收口后工艺工程师扩字 follow-up（记录进 TODOS.md）。

设计：
- 沿用 ToeConversionService 模式（async + idempotent seed_defaults classmethod）
- 公司级默认（project_id=None）；项目级覆写 P2+ 模板导入后启用
- 6 category: STATIC / ROTATING / PACKAGE / ELECTRICAL / INSTRUMENT / OTHER
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.equipment import EquipmentTypeCode


# 关键 codes（per brief + SPEC V1.4 §3.2.1 (3) 核心子集）
KEY_TYPE_CODES: tuple[str, ...] = (
    # ROTATING
    "P",    # Pump
    "C",    # Compressor
    "GT",   # Gas Turbine
    "M",    # Mixer
    # STATIC
    "V",    # Vessel (incl. Drum, Column)
    "T",    # Tower (Tray Column)
    "E",    # Heat Exchanger (Shell & Tube)
    "H",    # Heater (Fired Heater)
    "F",    # Filter
    "ST",   # Steam Generator / Boiler
    "CT",   # Cooling Tower
    # PACKAGE
    "A",    # Air Cooler
    # ELECTRICAL
    "X",    # Motor / Electrical
    # INSTRUMENT
    "PSV",  # Pressure Safety Valve
    "PRD",  # Pressure Relief Device
    "PVRV", # Pilot-Operated Relief Valve
    "ERV",  # Emergency Relief Valve
    # OTHER / 安全
    "FA",   # Flame Arrester
    "ARU",  # Air Recovery Unit
    "MRU",  # Material Recovery Unit
    "LOS",  # Local Operating Station
    "SOS",  # Stationary Operating Station
    "R",    # Reactor (specialized vessel)
    "S",    # Separator
)


# 完整 seed 列表（含 KEY_TYPE_CODES 全集 + 补充常用项）
SEED_TYPE_CODES: tuple[dict, ...] = (
    # ROTATING
    {"type_code": "P",  "equipment_description": "Pump", "description_cn": "泵", "category": "ROTATING", "is_process_equipment": True},
    {"type_code": "C",  "equipment_description": "Compressor", "description_cn": "压缩机", "category": "ROTATING", "is_process_equipment": True},
    {"type_code": "GT", "equipment_description": "Gas Turbine", "description_cn": "燃气轮机", "category": "ROTATING", "is_process_equipment": True},
    {"type_code": "M",  "equipment_description": "Mixer", "description_cn": "混合器", "category": "ROTATING", "is_process_equipment": True},
    # STATIC
    {"type_code": "V",  "equipment_description": "Vessel (Drum)", "description_cn": "容器（罐）", "category": "STATIC", "is_process_equipment": True, "is_pressure_vessel": True},
    {"type_code": "T",  "equipment_description": "Tray Column", "description_cn": "板式塔", "category": "STATIC", "is_process_equipment": True, "is_pressure_vessel": True},
    {"type_code": "E",  "equipment_description": "Heat Exchanger (Shell & Tube)", "description_cn": "管壳式换热器", "category": "STATIC", "is_process_equipment": True, "is_pressure_vessel": True},
    {"type_code": "H",  "equipment_description": "Fired Heater", "description_cn": "加热炉", "category": "STATIC", "is_process_equipment": True},
    {"type_code": "F",  "equipment_description": "Filter", "description_cn": "过滤器", "category": "STATIC", "is_process_equipment": True},
    {"type_code": "ST", "equipment_description": "Steam Generator / Boiler", "description_cn": "蒸汽发生器/锅炉", "category": "STATIC", "is_process_equipment": True, "is_pressure_vessel": True},
    {"type_code": "CT", "equipment_description": "Cooling Tower", "description_cn": "冷却塔", "category": "STATIC", "is_process_equipment": True},
    {"type_code": "R",  "equipment_description": "Reactor", "description_cn": "反应器", "category": "STATIC", "is_process_equipment": True, "is_pressure_vessel": True},
    {"type_code": "S",  "equipment_description": "Separator", "description_cn": "分离器", "category": "STATIC", "is_process_equipment": True, "is_pressure_vessel": True},
    # PACKAGE
    {"type_code": "A",  "equipment_description": "Air Cooler", "description_cn": "空冷器", "category": "PACKAGE", "is_process_equipment": True},
    {"type_code": "OC", "equipment_description": "Open Channel (Water Cooling)", "description_cn": "明渠（水冷）", "category": "PACKAGE", "is_process_equipment": True},
    # ELECTRICAL
    {"type_code": "X",  "equipment_description": "Motor / Electrical", "description_cn": "电机/电气", "category": "ELECTRICAL", "is_process_equipment": False},
    {"type_code": "TR", "equipment_description": "Transformer", "description_cn": "变压器", "category": "ELECTRICAL", "is_process_equipment": False},
    # INSTRUMENT
    {"type_code": "PSV",  "equipment_description": "Pressure Safety Valve", "description_cn": "压力安全阀", "category": "INSTRUMENT", "is_process_equipment": False},
    {"type_code": "PRD",  "equipment_description": "Pressure Relief Device", "description_cn": "压力泄放装置", "category": "INSTRUMENT", "is_process_equipment": False},
    {"type_code": "PVRV", "equipment_description": "Pilot-Operated Relief Valve", "description_cn": "先导式泄压阀", "category": "INSTRUMENT", "is_process_equipment": False},
    {"type_code": "ERV",  "equipment_description": "Emergency Relief Valve", "description_cn": "紧急泄压阀", "category": "INSTRUMENT", "is_process_equipment": False},
    {"type_code": "FA",   "equipment_description": "Flame Arrester", "description_cn": "阻火器", "category": "INSTRUMENT", "is_process_equipment": False},
    # OTHER
    {"type_code": "ARU", "equipment_description": "Air Recovery Unit", "description_cn": "空气回收装置", "category": "OTHER", "is_process_equipment": False},
    {"type_code": "MRU", "equipment_description": "Material Recovery Unit", "description_cn": "物料回收装置", "category": "OTHER", "is_process_equipment": False},
    {"type_code": "LOS", "equipment_description": "Local Operating Station", "description_cn": "现场操作站", "category": "OTHER", "is_process_equipment": False},
    {"type_code": "SOS", "equipment_description": "Stationary Operating Station", "description_cn": "固定操作站", "category": "OTHER", "is_process_equipment": False},
    {"type_code": "D",   "equipment_description": "Drum", "description_cn": "罐", "category": "STATIC", "is_process_equipment": True, "is_pressure_vessel": True},
    {"type_code": "B",   "equipment_description": "Blower", "description_cn": "鼓风机", "category": "ROTATING", "is_process_equipment": True},
    {"type_code": "CV",  "equipment_description": "Control Valve", "description_cn": "调节阀", "category": "INSTRUMENT", "is_process_equipment": False},
    {"type_code": "TK",  "equipment_description": "Storage Tank", "description_cn": "储罐", "category": "STATIC", "is_process_equipment": True},
    {"type_code": "STK", "equipment_description": "Stack / Chimney", "description_cn": "烟囱/排气筒", "category": "OTHER", "is_process_equipment": False},
)


class EquipmentTypeCodeService:
    """设备类型代码 service（equipment_type_codes 表，复合 PK (project_id, type_code)）。

    业务：seed_defaults 幂等 seed 31 个核心 type_code（公司级默认，project_id NULL）；
    query_by_code / list_by_category 提供 read-only 查询；项目级覆写 P2+ 模板导入后
    启用（不属本 service 范围）。

    F-P1-012 fix: 数量注释对齐 — 真实 seed 31 个（KEY_TYPE_CODES 24 + 7 常用补充）
    """

    @classmethod
    async def seed_defaults(cls, session: AsyncSession) -> int:
        """幂等 seed 31 个核心 type_code（公司级默认，project_id NULL）。

        F-P1-011 fix: 由 all-or-nothing 改为 per-entry 增量（partial pre-seeding
        不阻塞剩余 type_codes seed）。

        Returns:
            新增行数（幂等：第二次返回 0；partial pre-seed → 只增 missing 项）。
        """
        existing_stmt = select(EquipmentTypeCode.type_code).where(
            EquipmentTypeCode.project_id.is_(None)
        )
        existing = set((await session.execute(existing_stmt)).scalars().all())

        new_count = 0
        for entry in SEED_TYPE_CODES:
            if entry["type_code"] in existing:
                continue  # F-P1-011 fix: 跳过已存在项
            session.add(
                EquipmentTypeCode(
                    project_id=None,  # 公司级默认
                    type_code=entry["type_code"],
                    equipment_description=entry["equipment_description"],
                    description_cn=entry.get("description_cn"),
                    category=entry["category"],
                    is_process_equipment=entry.get("is_process_equipment", True),
                    is_pressure_vessel=entry.get("is_pressure_vessel", False),
                    source="SPEC V1.4 §3.2.1 (3)",
                    status="ACTIVE",
                )
            )
            new_count += 1
        if new_count > 0:
            await session.commit()
        return new_count
