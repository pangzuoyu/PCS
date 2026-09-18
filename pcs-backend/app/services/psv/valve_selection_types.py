"""SUP-P5-PSV-002 V1.14 §3.2 类型定义 + ValidatedParams 容器。

按 SPEC V1.14 §3.2（11 Literal 枚举 + 1 dataclass）：

- 枚举：PsvValveType / PsvBodyMaterial / PsvBellowsMaterial /
        PsvOrificeSize / PsvBackPressureType / PsvMedium /
        PsvPilotTempClass / PsvRuptureDiscPosition / PsvFlangeClass /
        PsvKbSource
- PsvValveBrand：自由字符串（V1.14 P2-1 修订：不引入枚举）
- ValidatedParams：validate_valve_params 派生值容器（kb_factor /
                    cdtp_applied / rupture_disc_kc / candidates / warnings）

复用：
- PsvOrificeSize 与 app/services/psv/orifice_service.py OrificeSize 同义
  （保持独立避免循环 import；alembic 列 comment 用此）
- 11 Literal + 1 dataclass = Pydantic v2 字段类型共享

不做：
- 不含数据（_KB_DATA 在 kb_service.py）
- 不含映射（API 526 Tables 2-15 在 orifice_flange.py）
- 不含校验（validate_valve_params 在 valve_validation.py）
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Final, Literal

# ---------------------------------------------------------------------------
# 11 Literal 枚举（与 SPEC §3.2 一一对应）
# ---------------------------------------------------------------------------

PsvValveType = Literal[
    "SPRING_LOADED",      # 弹簧载荷式（默认；P5 完整实现）
    "BALANCED_BELLOWS",   # 平衡波纹管式（P5 完整实现）
    "PILOT_OPERATED",     # 先导式（P5 拦截 G7；§2.2 P5+ 实施）
    "RUPTURE_DISC",       # 爆破膜式（P5 拦截 G8；§2.2 P6+ 实施）
]

PsvBodyMaterial = Literal[
    "CARBON_STEEL",       # 碳钢
    "SS304",              # 不锈钢 304
    "SS316",              # 不锈钢 316（默认）
    "SS316L",             # 不锈钢 316L
    "ALLOY",              # 合金钢
]

PsvBellowsMaterial = Literal[
    "HASTELLOY_C276",     # 哈氏合金 C276
    "SS316L",             # 316L 经济型
    "INCONEL_625",        # 因科镍 625
    "INCONEL_718",        # 因科镍 718
    "ALLOY_400",          # 蒙乃尔 400
    "ALLOY_C22",          # 哈氏合金 C22
]

PsvOrificeSize = Literal[
    "D", "E", "F", "G", "H", "J", "K", "L",
    "M", "N", "P", "Q", "R", "T",
]

PsvBackPressureType = Literal[
    "BUILT_UP",           # 累积背压
    "SUPERIMPOSED",       # 恒定叠加背压
]

PsvMedium = Literal[
    "GAS",                # 气体
    "VAPOR",              # 蒸汽
    "LIQUID",             # 液体
    "TWO_PHASE",          # 两相流
]

PsvPilotTempClass = Literal[
    "GENERAL",            # 常温（默认；Sanmar Series 500）
    "HIGH_TEMP",          # 高温（LESER Type 824）
    "CRYOGENIC",          # 低温（待核验 OPEN-18）
]

PsvRuptureDiscPosition = Literal[
    "UPSTREAM",           # 爆破膜在 PSV 上游（Kc=0.90 per ASME UG-127）
    "DOWNSTREAM",         # 爆破膜在 PSV 下游（Kc=1.00）
    "NONE",               # 无爆破膜（默认）
]

PsvFlangeClass = Literal[
    "150#",
    "300#",
    "600#",
    "900#",
    "1500#",
    "2500#",
]

# PsvKbSource: "none" = API 520 标准定义 1.0；其他 = 厂商/API 520 Fig.30/EN 4126
# H-P5-4d-4 — HIGH backend — 改用 str 接受任意 manufacturer:* 和 mixed:* 组合；
# PsvKbSourceLiteral 仅保留静态枚举（用于前端 select option 与 backward compat）。
# kb_service.lookup_kb_with_priority 运行时拼接的字符串一律属此范畴。
PsvKbSourceLiteral = Literal[
    "none",
    "manufacturer:LESER",
    "manufacturer:Consolidated",
    "manufacturer:Anderson_Greenwood",
    "manufacturer:Farris",
    "manufacturer:Crosby",
    "mixed:LESER+Consolidated",
    "mixed:LESER+Anderson_Greenwood",
    "mixed:Consolidated+Anderson_Greenwood",
    "mixed:LESER+Consolidated+Anderson_Greenwood",
    "api520_fig30",
    "en4126",
]

# H-P5-4d-4 — 运行时扩展：任意 manufacturer:* 和 mixed:* 均合法（用户传入任意厂商名）
PsvKbSource = str  # 实际合法值范围 = PsvKbSourceLiteral ∪ {"manufacturer:*", "mixed:*"}

# PsvValveBrand: 自由字符串（V1.14 P2-1 修订裁决）
#    已知品牌：LESER / Consolidated / Anderson_Greenwood / Farris / Crosby
#    后端 Warning + 回退覆盖/保守优先策略
PsvValveBrand = str

# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------

# V1.14 P5 默认值（与前端 PsvComputePage 默认值对齐；§7.2 向后兼容）
DEFAULT_VALVE_TYPE: Final[PsvValveType] = "SPRING_LOADED"
DEFAULT_BODY_MATERIAL: Final[PsvBodyMaterial] = "SS316"
DEFAULT_BACK_PRESSURE_TYPE: Final[PsvBackPressureType] = "BUILT_UP"
DEFAULT_OVERPRESSURE_PCT: Final[float] = 0.10  # 10% API 520 §5.3.1 默认
DEFAULT_FLANGE_CLASS: Final[PsvFlangeClass] = "300#"
DEFAULT_PILOT_TEMP_CLASS: Final[PsvPilotTempClass] = "GENERAL"
DEFAULT_RUPTURE_DISC_POSITION: Final[PsvRuptureDiscPosition] = "NONE"
DEFAULT_BLOWDOWN_FRACTION: Final[float] = 0.05  # 5% API 520 惯例

# 入口最小尺寸（API 526 弹簧载荷式；§3.3 + §4.2 G14）
API526_MIN_INLET: Final[str] = "1 inch"

# Rupture disc Kc（ASME UG-127）
RUPTURE_DISC_KC: Final[dict[PsvRuptureDiscPosition, float | None]] = {
    "UPSTREAM": 0.90,
    "DOWNSTREAM": 1.00,
    "NONE": None,
}

# BLOWDOWN 范围（SPEC §3.5；按 valve_type + medium）
# 弹簧式/平衡波纹管式 GAS/VAPOR: 5-10%；LIQUID: 10-20%；TWO_PHASE: 10-15%
# 先导式 GAS/VAPOR/LIQUID: 2-5%（P5 拦截；保留以供 P5+）
BLOWDOWN_RANGE: Final[dict[tuple[str, str], tuple[float, float]]] = {
    ("SPRING_LOADED", "GAS"): (0.05, 0.10),
    ("SPRING_LOADED", "VAPOR"): (0.05, 0.10),
    ("SPRING_LOADED", "LIQUID"): (0.10, 0.20),
    ("SPRING_LOADED", "TWO_PHASE"): (0.10, 0.15),
    ("BALANCED_BELLOWS", "GAS"): (0.05, 0.10),
    ("BALANCED_BELLOWS", "VAPOR"): (0.05, 0.10),
    ("BALANCED_BELLOWS", "LIQUID"): (0.10, 0.20),
    ("BALANCED_BELLOWS", "TWO_PHASE"): (0.10, 0.15),
    # PILOT_OPERATED：P5 拦截 G7；保留范围供 P5+
    ("PILOT_OPERATED", "GAS"): (0.02, 0.05),
    ("PILOT_OPERATED", "VAPOR"): (0.02, 0.05),
    ("PILOT_OPERATED", "LIQUID"): (0.02, 0.05),
}

# 介质默认 blowdown（前端 V1.14 §5.1 联动规则）
BLOWDOWN_DEFAULT_BY_MEDIUM: Final[dict[str, float]] = {
    "GAS": 0.05,
    "VAPOR": 0.05,
    "LIQUID": 0.10,
    "TWO_PHASE": 0.10,
}

# 背压阀型上限（§3.5 + §4.2 G10）
BACK_PRESSURE_MAX_BY_TYPE: Final[dict[PsvValveType, dict[PsvBackPressureType, float | None]]] = {
    "SPRING_LOADED": {"BUILT_UP": 10.0, "SUPERIMPOSED": None},  # 10% 硬限
    "BALANCED_BELLOWS": {"BUILT_UP": 50.0, "SUPERIMPOSED": 50.0},  # total ≤ 50%
    "PILOT_OPERATED": {"BUILT_UP": None, "SUPERIMPOSED": None},  # P5 拦截
    "RUPTURE_DISC": {"BUILT_UP": None, "SUPERIMPOSED": None},  # P5 拦截
}

# 平衡波纹管式须咨询厂商阈值（§3.5）
BELLOWS_CONSULT_THRESHOLD: Final[float] = 30.0

# 平衡波纹管式爆破膜失效率（force balance after bellows rupture；§5.3）
#   API 520 §5.4.2：波纹管破裂后退化为常规式，若背压 > 10% 则泄放能力不足
BELLOWS_RUPTURE_BACKPRESSURE_LIMIT: Final[float] = 10.0

# ---------------------------------------------------------------------------
# ValidatedParams（validate_valve_params 输出容器）
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ValidatedParams:
    """validate_valve_params 派生值容器（§4.2 + §4.3 + §4.4 + §4.5）。

    字段：
      - valve_type / medium / flange_class：透传（便于调用方使用）
      - inlet_size / outlet_size：透传
      - cdtp_applied：CDTP 修正是否生效（SUPERIMPOSED BP>0 时 = True）
      - kb_factor：背压修正系数（弹簧式零背压/标准定义 = 1.0）
      - kb_source：Kb 来源标识（PsvKbSource）
      - cdtp_set_pressure_pa：CDTP 修正后设定压力（仅 cdtp_applied=True 时有意义）
      - rupture_disc_kc：爆破膜组合 Kc（ASME UG-127；UPSTREAM=0.90 / DOWNSTREAM=1.00 / NONE=None）
      - candidates：候选孔口列表（按 inlet/outlet/flange_class 过滤）
      - orifice_override_validated：orifice_override 校验通过（Pydantic 给出 None 时 = None）
      - warnings：Warning 列表（G18/G19/G22/G23/G24/G25；不 raise 仅记录）
    """

    valve_type: PsvValveType
    medium: PsvMedium
    flange_class: PsvFlangeClass
    inlet_size: str | None
    outlet_size: str | None
    cdtp_applied: bool
    kb_factor: float
    kb_source: PsvKbSource | None
    cdtp_set_pressure_pa: float | None
    rupture_disc_kc: float | None
    candidates: list[PsvOrificeSize]
    orifice_override_validated: PsvOrificeSize | None
    warnings: list[str] = field(default_factory=list)


__all__ = [
    "PsvValveType",
    "PsvBodyMaterial",
    "PsvBellowsMaterial",
    "PsvOrificeSize",
    "PsvBackPressureType",
    "PsvMedium",
    "PsvPilotTempClass",
    "PsvRuptureDiscPosition",
    "PsvFlangeClass",
    "PsvKbSource",
    "PsvKbSourceLiteral",
    "PsvValveBrand",
    "ValidatedParams",
    "DEFAULT_VALVE_TYPE",
    "DEFAULT_BODY_MATERIAL",
    "DEFAULT_BACK_PRESSURE_TYPE",
    "DEFAULT_OVERPRESSURE_PCT",
    "DEFAULT_FLANGE_CLASS",
    "DEFAULT_PILOT_TEMP_CLASS",
    "DEFAULT_RUPTURE_DISC_POSITION",
    "DEFAULT_BLOWDOWN_FRACTION",
    "API526_MIN_INLET",
    "RUPTURE_DISC_KC",
    "BLOWDOWN_RANGE",
    "BLOWDOWN_DEFAULT_BY_MEDIUM",
    "BACK_PRESSURE_MAX_BY_TYPE",
    "BELLOWS_CONSULT_THRESHOLD",
    "BELLOWS_RUPTURE_BACKPRESSURE_LIMIT",
]
