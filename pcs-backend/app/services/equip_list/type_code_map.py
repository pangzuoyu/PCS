"""S1-4 R4: SourceModule string → equipment type_code 映射表。

Used by ``sync_from_source`` to populate composite FK
``(equipment_type_project_id, type_code) → equipment_type_codes``.
Per SPEC V1.4 §3.2.1 type code dictionary（80 codes；sync 仅涉及核心 8 module）。

扩展：未来 SourceModule 增多时 append 新条目；保持 R=3 brief 同步范围最小。
"""

from __future__ import annotations

from app.services.equip_list.source_resolver import UnsupportedSourceModuleError

MODULE_TYPE_CODE_MAP: dict[str, str] = {
    "PUMP": "P",
    "VESSEL": "V",
    "HEAT": "E",  # HEAT Exchanger
    "PSV": "PSV",
    "CV": "CV",
    "COOL_TOWER": "CT",
    "PSYCHRO": "X",
    "OPEN_CHANNEL": "OC",
}


def derive_type_code(source_module: str) -> str:
    """R4: source_module → type_code (per SPEC V1.4 §3.2.1).

    Raises:
        UnsupportedSourceModuleError: source_module 不在映射表。
    """
    if source_module not in MODULE_TYPE_CODE_MAP:
        raise UnsupportedSourceModuleError(
            f"source_module {source_module!r} not in type_code map; "
            f"valid: {sorted(MODULE_TYPE_CODE_MAP.keys())}"
        )
    return MODULE_TYPE_CODE_MAP[source_module]
