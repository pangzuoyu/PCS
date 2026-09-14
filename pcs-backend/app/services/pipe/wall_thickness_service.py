"""P4-2-2：管道壁厚服务（ASME B31.3 2018/2020 §304.1.2 直管壁厚计算）。

公式：
- 无缝管（seamless）：t = P·D / (2·(S·E + P·Y))
- 焊接管（welded）：  t = P·D / (2·(S·E·W + P·Y))
  其中：
  - P = 设计压力（MPa）
  - D = 管外径（mm）
  - S = 材料许用应力（MPa，按设计温度插值，节点温度直接命中）
  - E = 质量系数（无缝 1.0；焊接按焊接接头类型取 ASME B31.3 表 304.1.2）
  - Y = 温度系数（ASME B31.3 表 304.1.2，< 482°C 取 0.4）
  - W = 焊缝接头强度减弱系数（ASME B31.3 §302.3.4，按焊缝检测比例取 0.85/1.0）

t_nom = t_calc + c（c = 腐蚀裕度 mm）
round_to_schedule：t_nom 圆整到 ASME B36.10（碳钢）/ B36.19（不锈钢）标准 Sch 系列；
  策略：选**最小**标准 Sch 使其壁厚 ≥ t_nom（HG/T 20570 越档+安全裕度同类策略）。

许用应力 S：复用 CommonService.allowable_stress（ASME B31.3 Table A-1 内置 +
温度线性插值；越界 → 422；未知材料 → 422）。本模块不重复造表，保持单一真源。
"""

from __future__ import annotations

from typing import Any, Final

from app.services.common_service import CommonService
from app.services.exceptions import PcsError

# ---------------------------------------------------------------------------
# 异常
# ---------------------------------------------------------------------------


class WallThicknessInputError(PcsError):
    """WallThickness 输入错误（业务非法 / 公式除零）。

    触发场景：
    - D ≤ 0（管径退化 / 无效）
    - S ≤ 0（许用应力为零）
    - c < 0（腐蚀裕度不能为负）
    - DN 不在标准 Sch 表覆盖范围（< DN15 或 > DN600）
    - 所有标准 Sch 厚度都 < t_nom（需要更厚管或换材料）
    - 材料牌号未在 ASME B31.3 Table A-1 内（422）
    """

    code = "WALL_THICKNESS_INPUT_ERROR"
    status = 422


class WallThicknessTempOOBError(PcsError):
    """设计温度超出许用应力表有效范围（< 38°C 或 > 500°C）。"""

    code = "WALL_THICKNESS_TEMP_OOB"
    status = 422


# ---------------------------------------------------------------------------
# 常量：DN 标准系列（与 sizing_service 对齐）
# ---------------------------------------------------------------------------


# 关键外径 OD（mm；ASME B36.10 / B36.19）→ 落在该 OD 的标准 Sch 系列壁厚表
# 溯源：ASME B36.10（碳钢焊接管）/ B36.19（不锈钢管）2018 版标准壁厚表。
# 覆盖 DN15 ~ DN600（21.3 mm ~ 610 mm OD），支持工程常用规格。
_SCHEDULE_TABLE: Final[dict[float, dict[str, float]]] = {
    # DN15 (NPS 1/2", OD=21.3)
    21.3: {
        "SCH 5": 1.65,
        "SCH 10": 2.11,
        "SCH 40": 2.77,
        "STD": 2.77,
        "SCH 80": 3.73,
        "XS": 3.73,
        "SCH 160": 4.78,
        "XXS": 7.47,
    },
    # DN20 (NPS 3/4", OD=26.7)
    26.7: {
        "SCH 5": 1.65,
        "SCH 10": 2.11,
        "SCH 40": 2.87,
        "STD": 2.87,
        "SCH 80": 3.91,
        "XS": 3.91,
        "SCH 160": 5.56,
        "XXS": 7.82,
    },
    # DN25 (NPS 1", OD=33.4)
    33.4: {
        "SCH 5": 1.65,
        "SCH 10": 2.77,
        "SCH 40": 3.38,
        "STD": 3.38,
        "SCH 80": 4.55,
        "XS": 4.55,
        "SCH 160": 6.35,
        "XXS": 9.09,
    },
    # DN32 (NPS 1-1/4", OD=42.2)
    42.2: {
        "SCH 5": 1.65,
        "SCH 10": 2.77,
        "SCH 40": 3.56,
        "STD": 3.56,
        "SCH 80": 4.85,
        "XS": 4.85,
        "SCH 160": 6.35,
        "XXS": 9.70,
    },
    # DN40 (NPS 1-1/2", OD=48.3)
    48.3: {
        "SCH 5": 1.65,
        "SCH 10": 2.77,
        "SCH 40": 3.68,
        "STD": 3.68,
        "SCH 80": 5.08,
        "XS": 5.08,
        "SCH 160": 7.14,
        "XXS": 10.16,
    },
    # DN50 (NPS 2", OD=60.3)
    60.3: {
        "SCH 5": 1.65,
        "SCH 10": 2.77,
        "SCH 40": 3.91,
        "STD": 3.91,
        "SCH 80": 5.54,
        "XS": 5.54,
        "SCH 160": 8.74,
        "XXS": 11.07,
    },
    # DN65 (NPS 2-1/2", OD=73.0)
    73.0: {
        "SCH 5": 2.11,
        "SCH 10": 3.05,
        "SCH 40": 5.16,
        "STD": 5.16,
        "SCH 80": 7.01,
        "XS": 7.01,
        "SCH 160": 9.53,
        "XXS": 14.02,
    },
    # DN80 (NPS 3", OD=88.9)
    88.9: {
        "SCH 5": 2.11,
        "SCH 10": 3.05,
        "SCH 20": 3.18,
        "SCH 40": 5.49,
        "STD": 5.49,
        "SCH 80": 7.62,
        "XS": 7.62,
        "SCH 120": 11.13,
        "SCH 160": 13.49,
        "XXS": 15.24,
    },
    # DN100 (NPS 4", OD=114.3)
    114.3: {
        "SCH 5": 2.11,
        "SCH 10": 3.05,
        "SCH 20": 3.76,
        "SCH 40": 6.02,
        "STD": 6.02,
        "SCH 80": 8.56,
        "XS": 8.56,
        "SCH 120": 11.13,
        "SCH 160": 13.49,
        "XXS": 17.12,
    },
    # DN125 (NPS 5", OD=141.3)
    141.3: {
        "SCH 5": 2.77,
        "SCH 10": 3.40,
        "SCH 40": 6.55,
        "STD": 6.55,
        "SCH 80": 9.53,
        "XS": 9.53,
        "SCH 120": 12.70,
        "SCH 160": 15.88,
        "XXS": 19.05,
    },
    # DN150 (NPS 6", OD=168.3)
    168.3: {
        "SCH 5": 2.77,
        "SCH 10": 3.40,
        "SCH 20": 3.96,
        "SCH 40": 3.91,
        "STD": 3.91,
        "SCH 60": 5.56,
        "SCH 80": 5.49,
        "XS": 5.49,
        "SCH 100": 6.35,
        "SCH 120": 7.14,
        "SCH 140": 8.74,
        "SCH 160": 9.53,
    },
    # DN200 (NPS 8", OD=219.1)
    219.1: {
        "SCH 5": 2.77,
        "SCH 10": 3.76,
        "SCH 20": 5.56,
        "SCH 30": 7.04,
        "SCH 40": 6.35,
        "STD": 6.35,
        "SCH 60": 8.18,
        "SCH 80": 8.18,
        "XS": 8.18,
        "SCH 100": 10.31,
        "SCH 120": 12.70,
        "SCH 140": 14.27,
        "SCH 160": 18.26,
        "XXS": 22.23,
    },
    # DN250 (NPS 10", OD=273.0)
    273.0: {
        "SCH 5": 3.40,
        "SCH 10": 4.19,
        "SCH 20": 6.35,
        "SCH 30": 7.80,
        "SCH 40": 7.80,
        "STD": 7.80,
        "SCH 60": 9.27,
        "SCH 80": 9.27,
        "XS": 9.27,
        "SCH 100": 12.70,
        "SCH 120": 15.06,
        "SCH 140": 18.26,
        "SCH 160": 21.44,
        "XXS": 25.40,
    },
    # DN300 (NPS 12", OD=323.9)
    323.9: {
        "SCH 5": 3.96,
        "SCH 10": 4.57,
        "SCH 20": 6.35,
        "SCH 30": 8.38,
        "SCH 40": 8.38,
        "STD": 8.38,
        "SCH 60": 10.31,
        "SCH 80": 12.70,
        "XS": 12.70,
        "SCH 100": 15.06,
        "SCH 120": 17.48,
        "SCH 140": 21.44,
        "SCH 160": 25.40,
        "XXS": 33.32,
    },
    # DN350 (NPS 14", OD=355.6)
    355.6: {
        "SCH 5": 3.96,
        "SCH 10": 4.78,
        "SCH 20": 7.92,
        "SCH 30": 9.53,
        "SCH 40": 9.53,
        "STD": 9.53,
        "SCH 60": 11.91,
        "SCH 80": 12.70,
        "XS": 12.70,
        "SCH 100": 15.06,
        "SCH 120": 19.05,
        "SCH 140": 23.83,
        "SCH 160": 28.58,
    },
    # DN400 (NPS 16", OD=406.4)
    406.4: {
        "SCH 5": 4.19,
        "SCH 10": 4.78,
        "SCH 20": 7.92,
        "SCH 30": 9.53,
        "SCH 40": 9.53,
        "STD": 9.53,
        "SCH 60": 12.70,
        "SCH 80": 14.27,
        "XS": 14.27,
        "SCH 100": 16.66,
        "SCH 120": 21.44,
        "SCH 140": 26.19,
        "SCH 160": 30.96,
    },
    # DN500 (NPS 20", OD=508.0)
    508.0: {
        "SCH 5": 4.78,
        "SCH 10": 5.54,
        "SCH 20": 9.53,
        "SCH 30": 12.70,
        "SCH 40": 12.70,
        "STD": 12.70,
        "SCH 60": 14.27,
        "SCH 80": 15.06,
        "XS": 15.06,
        "SCH 100": 20.62,
        "SCH 120": 26.19,
        "SCH 140": 32.54,
        "SCH 160": 38.10,
    },
    # DN600 (NPS 24", OD=610.0)
    610.0: {
        "SCH 5": 5.54,
        "SCH 10": 6.35,
        "SCH 20": 9.53,
        "SCH 30": 12.70,
        "SCH 40": 12.70,
        "STD": 12.70,
        "SCH 60": 17.48,
        "SCH 80": 17.48,
        "XS": 17.48,
        "SCH 100": 24.61,
        "SCH 120": 30.96,
        "SCH 140": 38.89,
        "SCH 160": 46.02,
    },
}

_MIN_OD_MM: Final[float] = min(_SCHEDULE_TABLE.keys())
_MAX_OD_MM: Final[float] = max(_SCHEDULE_TABLE.keys())


# ---------------------------------------------------------------------------
# 公式：t_calc（无缝 / 焊接）
# ---------------------------------------------------------------------------


def calc_wall_thickness_seamless(
    P_MPa: float,
    D_mm: float,
    S_MPa: float,
    E: float,
    Y: float,
) -> float:
    """ASME B31.3 §304.1.2 无缝管壁厚计算。

    公式：t = P·D / (2·(S·E + P·Y))

    Args:
        P_MPa: 设计压力（MPa；P=0 时 t=0，公式自然为零）
        D_mm: 管外径（mm）
        S_MPa: 材料许用应力（MPa）
        E: 质量系数（无缝管 E=1.0）
        Y: 温度系数（< 482°C 取 0.4）

    Returns:
        t_calc（mm）

    Raises:
        WallThicknessInputError: D ≤ 0 或 S ≤ 0
    """
    if D_mm <= 0:
        raise WallThicknessInputError(
            f"seamless D_mm={D_mm} 必须 > 0（管径退化 / 无效）",
            details={"D_mm": D_mm},
        )
    if S_MPa <= 0:
        raise WallThicknessInputError(
            f"seamless S_MPa={S_MPa} 必须 > 0（许用应力为零 / 无效）",
            details={"S_MPa": S_MPa},
        )
    if P_MPa <= 0:
        # P=0 → 无内压，t=0；P<0 → 物理非法（真空段另行处理，本模块不覆盖）
        if P_MPa < 0:
            raise WallThicknessInputError(
                f"seamless P_MPa={P_MPa} 不能为负（真空段另行处理）",
                details={"P_MPa": P_MPa},
            )
        return 0.0
    return P_MPa * D_mm / (2.0 * (S_MPa * E + P_MPa * Y))


def calc_wall_thickness_welded(
    P_MPa: float,
    D_mm: float,
    S_MPa: float,
    E: float,
    Y: float,
    W: float,
) -> float:
    """ASME B31.3 §304.1.2 焊接管壁厚计算（含焊缝减弱系数 W）。

    公式：t = P·D / (2·(S·E·W + P·Y))

    Args:
        P_MPa: 设计压力（MPa）
        D_mm: 管外径（mm）
        S_MPa: 材料许用应力（MPa）
        E: 质量系数（焊接按焊缝检测比例：100% 取 1.0；局部取 0.85 等）
        Y: 温度系数
        W: 焊缝接头强度减弱系数（ASME B31.3 §302.3.4）

    Returns:
        t_calc（mm）

    Raises:
        WallThicknessInputError: D ≤ 0 / S ≤ 0
    """
    if D_mm <= 0:
        raise WallThicknessInputError(
            f"welded D_mm={D_mm} 必须 > 0",
            details={"D_mm": D_mm},
        )
    if S_MPa <= 0:
        raise WallThicknessInputError(
            f"welded S_MPa={S_MPa} 必须 > 0",
            details={"S_MPa": S_MPa},
        )
    if P_MPa <= 0:
        if P_MPa < 0:
            raise WallThicknessInputError(
                f"welded P_MPa={P_MPa} 不能为负",
                details={"P_MPa": P_MPa},
            )
        return 0.0
    return P_MPa * D_mm / (2.0 * (S_MPa * E * W + P_MPa * Y))


# ---------------------------------------------------------------------------
# t_nom：计算壁厚 + 腐蚀裕度
# ---------------------------------------------------------------------------


def nominal_thickness(t_calc: float, c_mm: float) -> float:
    """计算壁厚 + 腐蚀裕度 → 公称壁厚。

    公式：t_nom = t_calc + c

    Args:
        t_calc: 公式计算壁厚（mm；≥ 0）
        c_mm: 腐蚀裕度（mm；≥ 0）

    Returns:
        t_nom（mm）

    Raises:
        WallThicknessInputError: c < 0
    """
    if c_mm < 0:
        raise WallThicknessInputError(
            f"c_mm={c_mm} 不能为负（腐蚀裕度物理意义 ≥ 0）",
            details={"c_mm": c_mm},
        )
    return t_calc + c_mm


# ---------------------------------------------------------------------------
# round_to_schedule：圆整到 ASME B36.10/B36.19 标准 Sch 系列
# ---------------------------------------------------------------------------


def _lookup_schedule_table(DN_mm: float) -> dict[str, float]:
    """按 OD 查标准 Sch 表（精确匹配 OD；OD 不在表内 → 边界错误）。"""
    # OD 必须在表内精确匹配（DN 离散档，不做内插）
    if DN_mm < _MIN_OD_MM:
        raise WallThicknessInputError(
            f"DN_mm={DN_mm} 小于最小标准 OD {_MIN_OD_MM} mm（DN15）",
            details={"DN_mm": DN_mm, "min_OD_mm": _MIN_OD_MM},
        )
    if DN_mm > _MAX_OD_MM:
        raise WallThicknessInputError(
            f"DN_mm={DN_mm} 大于最大标准 OD {_MAX_OD_MM} mm（DN600）",
            details={"DN_mm": DN_mm, "max_OD_mm": _MAX_OD_MM},
        )
    table = _SCHEDULE_TABLE.get(DN_mm)
    if table is None:
        raise WallThicknessInputError(
            f"DN_mm={DN_mm} 不在标准 Sch 表覆盖范围（离散 OD："
            f"{_MIN_OD_MM} ~ {_MAX_OD_MM} mm）",
            details={"DN_mm": DN_mm},
        )
    return table


def round_to_schedule(t_nom: float, DN_mm: float) -> str:
    """公称壁厚圆整到 ASME B36.10/B36.19 标准 Sch 系列。

    策略：选**最小**标准 Sch 使其壁厚 ≥ t_nom（HG/T 20570 越档+安全裕度同类策略）。
    - t_nom ≤ 0 → 选最薄的标准 Sch（SCH 5 起算）
    - 所有标准 Sch 厚度都 < t_nom → raise WallThicknessInputError（管材不足）

    Args:
        t_nom: 公称壁厚（mm）
        DN_mm: 公称通径外径 OD（mm；须与 _SCHEDULE_TABLE 内键精确匹配）

    Returns:
        Sch 标签字符串（如 "SCH 40" / "STD" / "XS"）

    Raises:
        Wall thicknessInputError: DN 越界 / 所有 Sch 都 < t_nom
    """
    table = _lookup_schedule_table(DN_mm)
    if t_nom <= 0:
        # t_nom=0 → 选最薄（dict 按插入顺序遍历，首项即最薄）
        return next(iter(table.keys()))

    # 按厚度升序遍历，找首个 ≥ t_nom
    sorted_sch = sorted(table.items(), key=lambda kv: kv[1])
    for sch_name, thickness_mm in sorted_sch:
        if thickness_mm >= t_nom:
            return sch_name

    raise WallThicknessInputError(
        f"DN_mm={DN_mm} 所有标准 Sch 厚度（最大 {max(table.values()):.2f} mm）"
        f"都 < t_nom={t_nom:.2f} mm；建议提高材料强度 / 改用更高等级 Sch / 更换材料",
        details={"DN_mm": DN_mm, "t_nom_mm": t_nom, "max_sch_thickness_mm": max(table.values())},
    )


# ---------------------------------------------------------------------------
# get_allowable_stress：许用应力（温度插值）
# ---------------------------------------------------------------------------


def get_allowable_stress(material: str, design_temp_C: float) -> dict[str, Any]:
    """按材料牌号 + 设计温度查许用应力（ASME B31.3 Table A-1）。

    复用 CommonService.allowable_stress（单一真源）。本模块仅做错误码映射：
    - 材料未知 → PcsError（422 COMMON_MATERIAL_NOT_FOUND）
    - 温度越界 → PcsError（422 COMMON_TEMP_OOB）

    Args:
        material: 材料牌号（必须命中 _ASME_B31_3_A1 表；如 "A106-GrB" / "304-SS"）
        design_temp_C: 设计温度（°C；有效 38 ~ 500）

    Returns:
        dict（含 material / temp_c / stress_mpa / interpolated / source）

    Raises:
        Wall thicknessInputError: material 未命中（映射 COMMON_MATERIAL_NOT_FOUND）
        Wall thicknessTempOOBError: 温度越界（映射 COMMON_TEMP_OOB）
    """
    try:
        return CommonService.allowable_stress(material, design_temp_C)
    except PcsError as e:
        # 错误码映射：保持 wall thickness 域名前缀，便于 API 层归类
        if e.code == "COMMON_TEMP_OOB":
            raise WallThicknessTempOOBError(
                e.args[0] if e.args else "设计温度越界",
                details=e.details,
            ) from e
        if e.code == "COMMON_MATERIAL_NOT_FOUND" or e.code == "COMMON_MISSING_MATERIAL":
            raise WallThicknessInputError(
                e.args[0] if e.args else "材料未命中",
                details=e.details,
            ) from e
        raise


__all__ = [
    "WallThicknessInputError",
    "WallThicknessTempOOBError",
    "calc_wall_thickness_seamless",
    "calc_wall_thickness_welded",
    "nominal_thickness",
    "round_to_schedule",
    "get_allowable_stress",
]