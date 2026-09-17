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
        raw_text=text,
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
    if value is None:
        raise _FieldMissing("numeric value")
    raw, _ = _split_unit(value)
    return float(raw)


def _coerce_optional_numeric(value: str | None) -> float | None:
    if value is None:
        return None
    raw, _ = _split_unit(value)
    try:
        return float(raw)
    except ValueError:
        return None


def _coerce_optional_int(value: str | None) -> int | None:
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