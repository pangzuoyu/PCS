"""HTRI 自研解析器（P5-4-1 / Task 19）。

按 PCS-PLAN-P5-DEVICE-EQUIPMENT.md Task 19：
- 自研解析 HTRI 文本输出（公司常用 Xist v6 + Xchanger Suite v8）
- `detect_version(path)` 按首行魔数探测
- `HTRI_VERSION_SUPPORTED` 白名单（默认 ['Xist_v6','Xchanger_Suite_v8']）
- 不在白名单 → `HtriVersionUnsupportedError` 含 `upgrade_url` 升级指引
- 解析失败 → `HtriParseError`（空文件 / 损坏文件）

**OPEN**：P5-OPEN-001（HTRI 版本兼容范围）默认按公司常用版本实施，
扩展性通过 `HtriParsedData.version: str` 字段预留 — 新版本加入时仅需
新增白名单 + 新增解析分支。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

# HTRI 白名单（按公司常用版本 + P5-OPEN-001 默认）
HTRI_VERSION_SUPPORTED: list[str] = ["Xist_v6", "Xchanger_Suite_v8"]

# 版本探测正则（首行魔数）
_VERSION_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"HTRI\s+Xist\s+v(?P<v>\d+)", re.IGNORECASE), "Xist_v{v}"),
    (re.compile(r"HTRI\s+Xchanger\s+Suite\s+v(?P<v>\d+)", re.IGNORECASE), "Xchanger_Suite_v{v}"),
]

# 升级指引 URL（P5-OPEN-001 默认；用户可后续覆盖）
VERSION_UPGRADE_URL: str = (
    "https://pcs.internal/docs/htri-versions"  # 公司内部版本升级指引
)

# 字段提取正则（Field: <value> <unit>?）
_NUMERIC_FIELD_RE = re.compile(
    r"^\s*(?P<key>[A-Za-z][A-Za-z0-9 _\-]+?):\s*(?P<value>[-+]?\d+(?:\.\d+)?)\s*(?P<unit>\S*)?\s*$"
)


# ===== 异常 =====


class HtriParseError(Exception):
    """HTRI 文本解析失败（空文件 / 损坏 / 缺关键字段）。"""


class HtriVersionUnsupportedError(HtriParseError):
    """HTRI 版本不在白名单。

    Attributes:
        detected_version: 探测到的版本字符串（如 "Xist_v99"）
        versions_supported: 白名单（HTRI_VERSION_SUPPORTED）
        upgrade_url: 升级指引 URL
    """

    def __init__(self, detected_version: str, versions_supported: list[str], upgrade_url: str):
        """构造 HtriVersionUnsupportedError（detected/supported/upgrade_url 驱动 message）。"""
        self.detected_version = detected_version
        self.versions_supported = versions_supported
        self.upgrade_url = upgrade_url
        super().__init__(
            f"HTRI version '{detected_version}' not supported. "
            f"Supported versions: {versions_supported}. "
            f"Upgrade guide: {upgrade_url}"
        )


# ===== 数据结构 =====


@dataclass
class HtriParsedData:
    """HTRI 解析输出（基本 + 管壳 + 空冷 共用）。"""

    version: str
    case_name: str

    # 核心计算字段
    heat_duty_w: float
    overall_u_w_m2k: float
    area_required_m2: float
    # 换热器类型：Air Cooler（Xace，扇风式） vs 壳管式（TEMA Xist）。
    # 字段树按它分组（ADR-0028），也决定哪些几何字段可选。
    exchanger_kind: str = ""
    # ⚠️ 以下是**管程侧**的热工量 —— 空冷器里管程侧是工艺侧、空气侧是
    # 另一侧；管壳式里管程侧就是 tube side。命名用 `cold_*` 是从 TEMA 的
    # shell/tube 视角来的，Xace 的「空气侧」在 OUTSIDE 列。
    # ⚠️ 单位：**已换算成 °C / mm / kg/s**。Excel 报表里就是这些单位，
    # 而纯文本 parser 用的是 K（`*_t_k` 系列）。两个 parser 的单位口径
    # 必须一致，否则同一份数据经两条链路进来温度差 273。
    cold_inlet_t_c: float | None = None
    cold_outlet_t_c: float | None = None
    cold_mass_flow_kgs: float | None = None
    hot_inlet_t_c: float | None = None
    hot_outlet_t_c: float | None = None
    hot_mass_flow_kgs: float | None = None
    air_inlet_t_c: float | None = None

    # 管壳字段（None 表示非管壳 / ACHE）
    shell_dia_m: float | None = None
    tube_length_m: float | None = None
    tube_count: int | None = None
    baffle_spacing_m: float | None = None

    # 物性 — 热侧
    hot_inlet_t_k: float | None = None
    hot_outlet_t_k: float | None = None
    hot_mass_flow_kgs: float | None = None
    hot_cp_j_kgk: float | None = None

    # 物性 — 冷侧（ACHE 无冷侧 → None）
    cold_inlet_t_k: float | None = None
    cold_outlet_t_k: float | None = None
    cold_mass_flow_kgs: float | None = None
    cold_cp_j_kgk: float | None = None

    # ACHE 字段
    air_inlet_t_k: float | None = None
    bundle_area_m2: float | None = None
    fan_count: int | None = None

    # === 用户 2026-12-12 裁决要进规格书的字段 ===
    # ⚠️ 下列字段在 HTRI 报表里是「一个标签两个值」（min/max、进出口、
    # 汽/液），所以**成对**。解析时按 `/` 或 `,` 拆 —— HTRI 的多值字段
    # 两种分隔符都用（`Skin temperature: 39.24/91.03` 与
    # `Tubepasses/Tuberows: 2/4`）。
    skin_temp_min_c: float | None = None   # 管壁温度 min（°C）
    skin_temp_max_c: float | None = None   # 管壁温度 max（°C）
    tube_rows: int | None = None           # 管排数（ACHE 专属）
    # ⚠️ HTRI 的 `Vapor (In/Out)` 是**四个**值：
    #   壳程进口 / 壳程出口 / 管程进口 / 管程出口
    # 冷侧同样有（冷凝侧液相含量 100%）。故每侧各一对。
    vapor_wt_frac_in: float | None = None      # 热侧气相含量 进口 wt%
    vapor_wt_frac_out: float | None = None     # 热侧气相含量 出口 wt%
    liquid_wt_frac_in: float | None = None     # 热侧液相含量 进口 wt%
    liquid_wt_frac_out: float | None = None    # 热侧液相含量 出口 wt%
    cold_vapor_wt_frac_in: float | None = None   # 冷侧气相含量 进口 wt%
    cold_vapor_wt_frac_out: float | None = None  # 冷侧气相含量 出口 wt%
    cold_liquid_wt_frac_in: float | None = None  # 冷侧液相含量 进口 wt%
    cold_liquid_wt_frac_out: float | None = None # 冷侧液相含量 出口 wt%
    # ACHE 翅片/风机几何（TODO-056 第一批）
    fin_height_mm: float | None = None
    fin_thickness_mm: float | None = None
    fin_root_diameter_mm: float | None = None
    over_fin_diameter_mm: float | None = None
    tip_clearance_mm: float | None = None
    # TODO-056 剩余 5 个：真实 `A-101.xls` 的 `2 - Final Results` 里确有
    # 这 5 个标签，此前 `AcheParams` 与注册表都没有 —— 报表里有、我们取不到。
    air_humidity_percent: float | None = None      # Air humidity (%)
    fin_density_per_m: float | None = None         # Fins per unit length (fin/m)
    fin_efficiency_percent: float | None = None    # Fin efficiency (%)
    unfinned_length_mm: float | None = None        # Unfinned length (mm)
    unheated_length_mm: float | None = None        # Unheated length (mm)
    # 主表剩余 4 条缺口（用户 2026-12-12）
    # mm 单位版（Excel 报表口径；纯文本 parser 用 *_m）
    shell_id_mm: float | None = None
    baffle_spacing_mm: float | None = None
    tube_passes: int | None = None
    heat_transfer_safety_factor: float | None = None
    fan_face_area_ratio: float | None = None
    fan_power_kw: float | None = None
    extended_area_m2: float | None = None
    bare_area_m2: float | None = None
    fan_face_area_ratio: float | None = None
    heat_transfer_safety_factor: float | None = None

    # 解析元数据
    raw_text: str = field(default="", repr=False)


# ===== 公共 API =====


def detect_version(path: Path) -> str | None:
    """探测 HTRI 版本（按首行魔数）。

    Returns:
        版本字符串（如 "Xist_v6" / "Xchanger_Suite_v8"）；空文件 / 无法判别 → None。
    """
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    if not text.strip():
        return None
    first_line = text.splitlines()[0] if text else ""
    for regex, template in _VERSION_PATTERNS:
        m = regex.search(first_line)
        if m:
            return template.format(v=m.group("v"))
    return None


def parse_htri(path: Path) -> HtriParsedData:
    """解析 HTRI 文本输出。

    Raises:
        HtriVersionUnsupportedError: 版本不在 HTRI_VERSION_SUPPORTED。
        HtriParseError: 空文件 / 缺关键字段（heat_duty_w / overall_u / area_required）。
    """
    text = path.read_text(encoding="utf-8", errors="replace")
    if not text.strip():
        raise HtriParseError(f"HTRI 文件为空：{path}")

    version = detect_version(path)
    if version is None:
        raise HtriParseError(
            f"HTRI 文件首行无法判别版本（期望 'HTRI Xist v<N>' 或 "
            f"'HTRI Xchanger Suite v<N>'）：{path}"
        )
    if version not in HTRI_VERSION_SUPPORTED:
        raise HtriVersionUnsupportedError(
            detected_version=version,
            versions_supported=HTRI_VERSION_SUPPORTED,
            upgrade_url=VERSION_UPGRADE_URL,
        )

    fields = _parse_fields(text)

    # 关键字段强校验
    try:
        heat_duty = _coerce_w(fields.get("Heat Duty"))
        overall_u = _coerce_numeric(fields.get("Overall U"))
        area_req = _coerce_numeric(fields.get("Area Required"))
    except _FieldMissing as e:
        raise HtriParseError(f"HTRI 缺关键字段：{e}") from e

    # 多值字段（用户 2026-12-12 裁决）。**缺失即 None，绝不抛** ——
    # 一次升级不该让全部历史导入失败（见 test_missing_new_fields_are_none_not_errors）。
    skin = _multi_numeric(fields.get("Skin Temperature"))
    # Vapor/Liquid 是**四值**字段（壳进/壳出/管进/管出），故用列表不是定长 2
    vapor = _multi_value(fields.get("Vapor"))
    liquid = _multi_value(fields.get("Liquid"))

    return HtriParsedData(
        version=version,
        case_name=str(fields.get("Case Name") or "").strip(),
        heat_duty_w=heat_duty,
        overall_u_w_m2k=overall_u,
        area_required_m2=area_req,
        shell_dia_m=_coerce_optional_numeric(fields.get("Shell Diameter")),
        tube_length_m=_coerce_optional_numeric(fields.get("Tube Length")),
        tube_count=_coerce_optional_int(fields.get("Tube Count")),
        baffle_spacing_m=_coerce_optional_numeric(fields.get("Baffle Spacing")),
        hot_inlet_t_k=_coerce_optional_numeric(fields.get("Hot Inlet T")),
        hot_outlet_t_k=_coerce_optional_numeric(fields.get("Hot Outlet T")),
        hot_mass_flow_kgs=_coerce_optional_numeric(fields.get("Hot Mass Flow")),
        hot_cp_j_kgk=_coerce_optional_numeric(fields.get("Hot Cp")),
        cold_inlet_t_k=_coerce_optional_numeric(fields.get("Cold Inlet T")),
        cold_outlet_t_k=_coerce_optional_numeric(fields.get("Cold Outlet T")),
        cold_mass_flow_kgs=_coerce_optional_numeric(fields.get("Cold Mass Flow")),
        cold_cp_j_kgk=_coerce_optional_numeric(fields.get("Cold Cp")),
        air_inlet_t_k=_coerce_optional_numeric(fields.get("Air Inlet T")),
        bundle_area_m2=_coerce_optional_numeric(fields.get("Bundle Area")),
        fan_count=_coerce_optional_int(fields.get("Fan Count")),
        skin_temp_min_c=skin[0],
        skin_temp_max_c=skin[1],
        # vapor/liquid 取前两个（其余用 _nth 越界给 None）
        tube_rows=_nth(_multi_value(fields.get("Tubepasses/Tuberows")), 1),
        vapor_wt_frac_in=_nth(vapor, 0),
        vapor_wt_frac_out=_nth(vapor, 1),
        liquid_wt_frac_in=_nth(liquid, 0),
        liquid_wt_frac_out=_nth(liquid, 1),
        cold_vapor_wt_frac_in=_nth(vapor, 2),
        cold_vapor_wt_frac_out=_nth(vapor, 3),
        cold_liquid_wt_frac_in=_nth(liquid, 2),
        cold_liquid_wt_frac_out=_nth(liquid, 3),
        fin_height_mm=_coerce_optional_numeric(fields.get("Fin Height")),
        fin_thickness_mm=_coerce_optional_numeric(fields.get("Fin Thickness")),
        fin_root_diameter_mm=_coerce_optional_numeric(
            fields.get("Fin Root Diameter")),
        over_fin_diameter_mm=_coerce_optional_numeric(
            fields.get("Over Fin Diameter")),
        tip_clearance_mm=_coerce_optional_numeric(fields.get("Tip Clearance")),
        extended_area_m2=_coerce_optional_numeric(fields.get("Extended Area")),
        bare_area_m2=_coerce_optional_numeric(fields.get("Bare Area")),
        fan_face_area_ratio=_coerce_optional_numeric(
            fields.get("Fan/Bundle Face Area Ratio")),
        heat_transfer_safety_factor=_coerce_optional_numeric(
            fields.get("Heat Transfer Safety Factor")),
    )


# ===== 内部工具 =====


class _FieldMissing(Exception):
    """解析过程中遇到缺失/格式错误字段。"""


def _parse_fields(text: str) -> dict[str, str]:
    """解析 `Key: value` 行 → {key: value_str}。

    空行 / 段标题（无冒号的行）跳过；多词 key 允许（"Hot Inlet T"、"Heat Duty"）。
    """
    out: dict[str, str] = {}
    for line in text.splitlines():
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip()
        value = value.strip()
        if not key or not value:
            continue
        out[key] = value
    return out


def _coerce_w(value: str | None) -> float:
    """单位转换：MW / kW → W；默认 W。"""
    if value is None:
        raise _FieldMissing("Heat Duty")
    raw, unit = _split_unit(value)
    n = float(raw)
    if unit == "MW":
        return n * 1_000_000.0
    if unit == "kW":
        return n * 1_000.0
    return n


def _coerce_numeric(value: str | None) -> float:
    """必填数字字段强转（HTRI Excel 解析，None 时抛 _FieldMissing）。

    业务：value 为 None → 抛 _FieldMissing（必填项缺失）；否则按 _split_unit
    拆出 raw 数字部分，float 强转；与 schema 必填校验互为兜底。
    """

    if value is None:
        raise _FieldMissing("numeric value")
    raw, _ = _split_unit(value)
    return float(raw)


def _multi_value(value: str | None) -> list[float | None]:
    """拆「一个标签多个值」→ 每个值的数值列表。

    HTRI 同一份报表里两种分隔符都用：`Skin Temperature: 39.24/91.03`
    与 `Tubepasses/Tuberows: 2/4` 都用斜杠；而 `dmc.out` 的输入卡里是
    `DUTY 1,1/2,12`（逗号 + 斜杠混排）。所以两者都认。

    解析不出数值的位置一律给 None，**不抛** —— 缺后半段是常态
    （老版本报表只有单值字段）。
    """
    if not value:
        return []
    parts = [p for p in re.split(r"[/,]", value) if p.strip()]
    out: list[float | None] = []
    for p in parts:
        raw, _unit = _split_unit(p.strip())
        try:
            out.append(float(raw))
        except ValueError:
            out.append(None)
    return out


def _nth(values: list[float | None], index: int) -> float | None:
    """取第 `index` 个值，越界给 None。

    ⚠️ 别直接 `values[index]`：字段缺失时 `_multi_value` 返回空列表，
    那会让「这一份报表没有这个字段」变成 `IndexError` ——
    于是一次 parser 升级让**所有**不含该字段的历史导入全部失败。
    """
    return values[index] if index < len(values) else None


def _multi_numeric(value: str | None) -> tuple[float | None, float | None]:
    """`_multi_value` 的定长 2 版（min/max、进出口）。不足则补 None。"""
    vals = _multi_value(value)
    return (vals[0] if vals else None, vals[1] if len(vals) > 1 else None)


def _coerce_optional_numeric(value: str | None) -> float | None:
    """选填数字字段软解析（None 或非法字符串均返回 None）。

    业务：None → None；非数字字符（带单位除外）抛 ValueError 时静默吞掉
    返回 None；HTRI Excel 单元格的"-"或空文本统一当 None 处理。
    """

    if value is None:
        return None
    raw, _ = _split_unit(value)
    try:
        return float(raw)
    except ValueError:
        return None


def _coerce_optional_int(value: str | None) -> int | None:
    """选填整数字段软解析（先按 float 取整，None/非法 → None）。

    业务：与 _coerce_optional_numeric 类似，但 int(float(raw)) 截断小数；
    用于 HTRI TEMA 表盘数（管程数/壳程数等整数字段）。
    """

    if value is None:
        return None
    raw, _ = _split_unit(value)
    try:
        return int(float(raw))
    except ValueError:
        return None


def _split_unit(value: str) -> tuple[str, str]:
    """拆分数字部分和单位。"""
    m = _NUMERIC_FIELD_RE.match("dummy: " + value)
    if not m:
        # 兜底：按首个空白拆分
        parts = value.split(maxsplit=1)
        return (parts[0], parts[1] if len(parts) > 1 else "")
    return m.group("value"), m.group("unit") or ""