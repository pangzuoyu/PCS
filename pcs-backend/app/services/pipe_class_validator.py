"""管道等级验证引擎——PC-2：22 条规则（PC-V×11 + PC-E×7 + PC-C×4）。

V1.4 修正要点：
- PC-E04 注入 common_tables 集合实际校验表存在性
- PC-E06 新增：is_fork=True + override 设计压力但未覆写法兰 → WARN
- PC-V10 移交给 service 层（PipeClassValidator.is_valid_source_class_id async classmethod）
- PC-C04 由 service 层调 PipeClassValidator.is_in_use 校验（async classmethod）
- PC-V09/PC-C03 语义合并为「项目级重名」（V1.4：保留 PC-V09 ERROR，PC-C03 同时触发）
- PC-V08 法兰三形式（ASME class / ASME Lb / PN 系列）规范化
- PC-V03 DN 系列判定：series 缺省时按 min/max range 判定（PC-FMT-01）
- PC-V04 Sch 值兼容 int 与 string（PC-FMT-02）

接口与 spec/PCS-SPEC-P2-SUP-002 §4 一致。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any
from uuid import UUID


class Severity(str, Enum):
    """校验严重级。"""

    ERROR = "ERROR"
    WARN = "WARN"


@dataclass
class ValidationResult:
    """单条校验结果。"""

    rule_id: str
    severity: Severity
    message: str
    field: str | None = None


@dataclass
class ValidationContext:
    """项目上下文（PC-C 系列用）。"""

    project_id: UUID | None = None
    project_pressure_limit: float | None = None
    project_allowed_materials: list[str] | None = None
    existing_class_names: list[str] = field(default_factory=list)
    # V1.4：PC-E06 用
    is_fork: bool = False
    override_keys: list[str] = field(default_factory=list)


# ---------- 法兰等级-压力对照表（38°C 基准） ----------
FLANGE_PRESSURE_RATINGS: dict[str, float] = {
    "150#": 1.96,
    "300#": 5.11,
    "400#": 6.81,
    "600#": 10.21,
    "900#": 15.32,
    "1500#": 25.53,
    "2500#": 42.55,
}

# V1.4：法兰三形式
# 1. ASME class 系列（带 #）
# 2. ASME Lb 系列（带 Lb，可带 /RF /RJ 等面形式后缀）
# 3. PN 系列（欧标，无 rating，不参与 E02/E03 压力评估）
ASME_CLASSES = {
    "150#", "300#", "400#", "600#", "900#", "1500#", "2500#",
    "150Lb", "300Lb", "400Lb", "600Lb", "900Lb", "1500Lb", "2500Lb",
}
_PN_PATTERN = re.compile(r"^PN\d+$")
_FACE_SUFFIX_PATTERN = re.compile(r"/(RF|RJ|FM|MF|TG|RF\+\d*)$")

# ---------- fitting_type 枚举（V1.4 §0.6） ----------
FITTING_TYPES = {"对焊", "承插", "螺纹", "法兰"}

# ---------- 碳钢高温材料前缀（PC-E01） ----------
CARBON_STEEL_PREFIXES = ("A106", "A53", "A234", "API 5L", "Q235", "20#")

# ---------- Sch 字符串白名单（PC-V04 兼容 PC-FMT-02） ----------
_SCH_STRING_ALLOW = {"STD", "XS", "XXS", "10S", "20S", "40S", "80S"}


def _normalize_flange_class(fc: str) -> str | None:
    """返回 ASME 标准 class 名（如 150Lb → "150#"）；PN 返回 None。"""
    if not fc:
        return None
    base = _FACE_SUFFIX_PATTERN.sub("", fc)
    if base in ASME_CLASSES:
        return base
    return None


def _is_valid_flange_class(fc: str) -> bool:
    """检查法兰等级合法性：ASME class / ASME Lb / PN 任一即可。"""
    if not fc:
        return False
    base = _FACE_SUFFIX_PATTERN.sub("", fc)
    return base in ASME_CLASSES or bool(_PN_PATTERN.match(base))


def _is_pn_only(fc: str) -> bool:
    """PN 系列不参与 E02/E03 压力评估（无 rating 表）。"""
    if not fc:
        return False
    base = _FACE_SUFFIX_PATTERN.sub("", fc)
    return bool(_PN_PATTERN.match(base))


def _asme_rating(fc: str) -> float | None:
    """取 ASME class 对应 MPa 压力上限；PN/非法返 None。"""
    base = _normalize_flange_class(fc)
    if base is None:
        return None
    if base.endswith("Lb"):
        # Lb 形式与 # 同义
        key = base.replace("Lb", "#")
    else:
        key = base
    return FLANGE_PRESSURE_RATINGS.get(key)


def _parse_dn_key(dn_key: Any) -> int | None:
    """解析 sch_series_json 键为 DN 整数；返回 None 表示无法解析。"""
    s = str(dn_key).strip()
    if s.upper().startswith("DN"):
        s = s[2:]
    try:
        return int(s)
    except (ValueError, TypeError):
        return None


class PipeClassValidator:
    """管道等级验证引擎——所有输入方式（表单 / Excel / API）共用。"""

    # ---------- 公开入口 ----------

    @classmethod
    def validate_company(
        cls,
        data: dict[str, Any],
        *,
        common_tables: set[str] | None = None,
    ) -> list[ValidationResult]:
        """公司级验证：PC-V + PC-E（不含项目上下文）。"""
        return cls._validate(data, ValidationContext(), common_tables)

    @classmethod
    def validate_project(
        cls,
        data: dict[str, Any],
        context: ValidationContext,
        *,
        common_tables: set[str] | None = None,
    ) -> list[ValidationResult]:
        """项目级验证：PC-V + PC-E + PC-C（PC-V09 + PC-E06 fork 覆写检查）。"""
        return cls._validate(data, context, common_tables)

    @classmethod
    def has_errors(cls, results: list[ValidationResult]) -> bool:
        """是否存在 ERROR 级结果。"""
        return any(r.severity == Severity.ERROR for r in results)

    # ---------- DB 辅助（V1.4：service 层在 fork 前/删除前调用） ----------

    @classmethod
    async def is_in_use(cls, db, class_id: str) -> bool:
        """PC-C04：检查 piping_results.material_class 是否引用了该等级。"""
        from sqlalchemy import select

        from app.models.calc import PipingResult

        row = (
            await db.execute(
                select(PipingResult.pipe_id)
                .where(PipingResult.material_class == class_id)
                .limit(1)
            )
        ).first()
        return row is not None

    @classmethod
    async def is_valid_source_class_id(cls, db, source_class_id: str) -> bool:
        """PC-V10 移交：service 层在 fork 前校验 source_class_id 是否存在。"""
        from sqlalchemy import select

        from app.models.config_domain import PipeClass

        row = (
            await db.execute(
                select(PipeClass.class_id)
                .where(PipeClass.class_id == source_class_id)
                .limit(1)
            )
        ).first()
        return row is not None

    # ---------- 核心校验逻辑 ----------

    @classmethod
    def _validate(
        cls,
        data: dict[str, Any],
        ctx: ValidationContext,
        common_tables: set[str] | None,
    ) -> list[ValidationResult]:
        results: list[ValidationResult] = []

        # PC-V01 必填字段
        required = [
            "class_name", "material_standard", "base_material",
            "design_pressure", "design_temperature", "corrosion_allowance",
        ]
        for f in required:
            if data.get(f) in (None, "", []):
                results.append(ValidationResult(
                    "PC-V01", Severity.ERROR,
                    f"必填字段 {f} 为空", f,
                ))

        # PC-V02 dn_series min<=max（空对象也算 ERROR）
        dn = data.get("dn_series_json") or {}
        if not dn or dn.get("min") is None or dn.get("max") is None:
            results.append(ValidationResult(
                "PC-V02", Severity.ERROR, "DN 系列为空", "dn_series_json",
            ))
        elif dn.get("min", 0) > dn.get("max", 0):
            results.append(ValidationResult(
                "PC-V02", Severity.ERROR, "DN 系列 min > max", "dn_series_json",
            ))

        # PC-V03 sch DN 必须在 dn_series 内
        # series 缺省时按 min/max range 判定（PC-FMT-01）
        sch = data.get("sch_series_json") or {}
        dn_series = dn.get("series") or []
        dn_min = dn.get("min", 0)
        dn_max = dn.get("max", 0)
        dn_set: set[int] | None = set(dn_series) if dn_series else None
        for dn_key in sch:
            dn_num = _parse_dn_key(dn_key)
            if dn_num is None:
                continue  # 无法解析的键跳过（其他规则覆盖）
            in_range = dn_min <= dn_num <= dn_max
            in_list = dn_set is None or dn_num in dn_set
            if not (in_range and in_list):
                range_desc = (
                    sorted(dn_set) if dn_set else f"[{dn_min},{dn_max}]"
                )
                results.append(ValidationResult(
                    "PC-V03", Severity.ERROR,
                    f"Sch 系列中 DN{dn_num} 不在 DN 系列 {range_desc} 中",
                    "sch_series_json",
                ))

        # PC-V04 Sch 值 > 0（兼容 int 与 string，PC-FMT-02）
        for dn_key, sch_values in sch.items():
            for v in sch_values:
                if isinstance(v, (int, float)):
                    if v <= 0:
                        results.append(ValidationResult(
                            "PC-V04", Severity.ERROR,
                            f"DN{dn_key} 的 Sch 值必须 > 0", "sch_series_json",
                        ))
                        break
                else:
                    s = str(v).strip()
                    if not s:
                        continue
                    if s in _SCH_STRING_ALLOW:
                        continue
                    try:
                        num = float(s)
                        if num <= 0:
                            results.append(ValidationResult(
                                "PC-V04", Severity.ERROR,
                                f"DN{dn_key} 的 Sch 值必须 > 0",
                                "sch_series_json",
                            ))
                            break
                    except ValueError:
                        results.append(ValidationResult(
                            "PC-V04", Severity.ERROR,
                            f"DN{dn_key} 的 Sch 值 {v} 不在白名单",
                            "sch_series_json",
                        ))
                        break

        # PC-V05 压力范围 (0, 42]
        dp = data.get("design_pressure")
        if dp is not None and not (0 < dp <= 42):
            results.append(ValidationResult(
                "PC-V05", Severity.ERROR,
                f"设计压力 {dp} MPa 超出范围 (0, 42]", "design_pressure",
            ))

        # PC-V06 温度范围 [-196, 650] WARN
        dt = data.get("design_temperature")
        if dt is not None and not (-196 <= dt <= 650):
            results.append(ValidationResult(
                "PC-V06", Severity.WARN,
                f"设计温度 {dt}°C 超出常规范围 [-196, 650]",
                "design_temperature",
            ))

        # PC-V07 腐蚀裕量 NULL→ERROR，超 [0,6.5]→ERROR
        ca = data.get("corrosion_allowance")
        if ca is None:
            results.append(ValidationResult(
                "PC-V07", Severity.ERROR,
                "腐蚀裕量不允许为 NULL（0 表示无腐蚀）",
                "corrosion_allowance",
            ))
        elif not (0 <= ca <= 6.5):
            results.append(ValidationResult(
                "PC-V07", Severity.ERROR,
                f"腐蚀裕量 {ca} mm 超出范围 [0, 6.5]", "corrosion_allowance",
            ))

        # PC-V08 法兰等级（三形式规范化）
        fc = data.get("flange_class", "") or ""
        if not _is_valid_flange_class(fc):
            results.append(ValidationResult(
                "PC-V08", Severity.ERROR,
                f"法兰等级 {fc} 不在枚举 {sorted(ASME_CLASSES)} / PN* 内",
                "flange_class",
            ))

        # PC-V11 fitting_type 各分段枚举（斜杠分隔）
        ft = data.get("fitting_type", "") or ""
        for seg in ft.split("/"):
            seg = seg.strip()
            if seg and seg not in FITTING_TYPES:
                results.append(ValidationResult(
                    "PC-V11", Severity.ERROR,
                    f"连接形式分段 {seg} 不在枚举 {sorted(FITTING_TYPES)} 内",
                    "fitting_type",
                ))
                break

        # PC-E01 碳钢高温 WARN
        bm = data.get("base_material", "") or ""
        if dt is not None and dt > 400 and any(
            bm.startswith(p) for p in CARBON_STEEL_PREFIXES
        ):
            results.append(ValidationResult(
                "PC-E01", Severity.WARN,
                f"碳钢材料 {bm} 在 {dt}°C 下使用需确认", "design_temperature",
            ))

        # PC-E03 法兰超压 ERROR（PN 系列不参与）
        if not _is_pn_only(fc):
            rating = _asme_rating(fc)
            if rating is not None and dp is not None and dp > rating:
                results.append(ValidationResult(
                    "PC-E03", Severity.ERROR,
                    f"设计压力 {dp} MPa 超过 {fc} 法兰最大允许压力 {rating} MPa",
                    "design_pressure",
                ))

        # PC-E02 150# 法兰超基准 WARN（独立于 E03，可同时触发）
        if (
            fc == "150#"
            and dp is not None
            and dp > FLANGE_PRESSURE_RATINGS["150#"]
        ):
            base = FLANGE_PRESSURE_RATINGS["150#"]
            results.append(ValidationResult(
                "PC-E02", Severity.WARN,
                f"150# 法兰设计压力 {dp} MPa 超过基准允许值 {base} MPa",
                "design_pressure",
            ))

        # PC-E04 引用表存在性（V1.4：注入 common_tables）
        if common_tables is not None:
            for field_name in ("allowable_stress_json", "branch_table_json"):
                obj = data.get(field_name) or {}
                table_name = obj.get("table")
                if table_name and table_name not in common_tables:
                    results.append(ValidationResult(
                        "PC-E04", Severity.ERROR,
                        f"{field_name} 引用的表 {table_name} 不存在于 COMMON 库",
                        field_name,
                    ))

        # PC-E05 DN > 600 WARN
        dn_max_val = dn.get("max") if dn else None
        if isinstance(dn_max_val, (int, float)) and dn_max_val > 600:
            results.append(ValidationResult(
                "PC-E05", Severity.WARN,
                f"DN 最大值 {dn_max_val} 超过 600", "dn_series_json",
            ))

        # PC-E06 fork 覆写设计压力但未覆写法兰（V1.4）
        if (
            ctx.is_fork
            and "design_pressure" in ctx.override_keys
            and "flange_class" not in ctx.override_keys
        ):
            results.append(ValidationResult(
                "PC-E06", Severity.WARN,
                "覆写了设计压力但未覆写法兰等级", "flange_class",
            ))

        # PC-E07 Sch 空但 DN 非空
        if dn and dn.get("series") and not sch:
            results.append(ValidationResult(
                "PC-E07", Severity.ERROR,
                "Sch 系列为空但 DN 系列非空", "sch_series_json",
            ))

        # ---------- 项目上下文（PC-C + PC-V09） ----------

        if (
            ctx.project_pressure_limit is not None
            and dp is not None
            and dp > ctx.project_pressure_limit
        ):
            results.append(ValidationResult(
                "PC-C01", Severity.WARN,
                f"等级设计压力 {dp} MPa 超过项目上限 {ctx.project_pressure_limit} MPa",
                "design_pressure",
            ))

        if (
            ctx.project_allowed_materials
            and bm
            and bm not in ctx.project_allowed_materials
        ):
            results.append(ValidationResult(
                "PC-C02", Severity.WARN,
                f"材料 {bm} 不在项目允许列表 {ctx.project_allowed_materials} 内",
                "base_material",
            ))

        # PC-V09 + PC-C03（V1.4：语义合并——项目内同名重名同时触发两条规则）
        if (
            ctx.existing_class_names
            and data.get("class_name") in ctx.existing_class_names
        ):
            name = data.get("class_name")
            results.append(ValidationResult(
                "PC-V09", Severity.ERROR,
                f"项目内已存在同名等级 {name}", "class_name",
            ))
            results.append(ValidationResult(
                "PC-C03", Severity.ERROR,
                f"项目内已存在同名等级 {name}", "class_name",
            ))

        return results