"""P3.2 SIM-22：物性冲突解决器（spec V1.6 §3.6 ADD-002）。

spec V1.6 §3.6 三原则：
1. 数学一致性 > 用户输入（硬冲突阻止保存 — 由 SIM-7 ConflictResolver 处理）
2. 实测数据 > 模型计算（物性类字段：用户值优先，标记偏差）
3. 精确计算 > 用户估计（分子量/换算流量：计算值优先，用户输入忽略）

USER_PRIORITY 字段（6 个，实测优先）：liquid_density, liquid_viscosity,
vapor_density, surface_tension, rvp, tvp。偏差阈值 per field。
偏差 > 阈值 → WARN（用户值已采用但警告）；否则 INFO（通过）。

CALCULATED_PRIORITY 字段（3 个，精确计算优先）：molecular_weight,
total_molar_flow, total_mass_flow。用户填了但偏差 > 1% → WARN；effective
始终取 calculated（用户输入被忽略）。

effective = calculated ⊕ user_provided（user 顶层键覆写 calculated），
但 CALCULATED_PRIORITY_FIELDS 例外（始终取 calculated）。

与 SIM-7 ConflictResolver 关系：
- SIM-7：硬冲突（相态/T/P/组成数学一致性）+ 物性补全错误码转译（MISSING_CAS 等）
- SIM-22：物性类字段（实测 vs 模型）的偏差分级与 effective 合成
- 二者互补，不重叠：SIM-7 BLOCK 阻止保存 → SIM-22 根本不会被调用。
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from numbers import Real
from typing import Any


class ConflictSeverity(str, Enum):
    """冲突三级（与 SIM-7 ConflictLevel 同语义，独立 enum 避免耦合）。"""

    BLOCK = "BLOCK"
    WARN = "WARN"
    INFO = "INFO"


@dataclass(frozen=True)
class ConflictResolution:
    """单条物性冲突解决记录。

    severity / field / resolution 三元组是契约核心：
    - severity: BLOCK / WARN / INFO（spec V1.6 §3.6 三级）
    - resolution: USER_VALUE / CALCULATED_VALUE / USER_MUST_CHANGE
      （USER_MUST_CHANGE 当前不由本类产出，留作扩展——硬冲突归 SIM-7）
    """

    severity: ConflictSeverity
    field: str
    user_value: float | str | None
    calculated_value: float | str | None
    resolution: str
    message: str


# USER_PRIORITY 字段：实测优先 + per-field 偏差阈值
USER_PRIORITY_FIELDS: dict[str, float] = {
    "liquid_density": 0.10,
    "liquid_viscosity": 0.20,
    "vapor_density": 0.10,
    "surface_tension": 0.15,
    "rvp": 0.10,
    "tvp": 0.10,
}

# CALCULATED_PRIORITY 字段：精确计算优先 + 统一 1% 阈值
CALCULATED_PRIORITY_FIELDS: dict[str, float] = {
    "molecular_weight": 0.01,
    "total_molar_flow": 0.01,
    "total_mass_flow": 0.01,
}

# resolution 取值集合（文档化，避免调用方拼错）
_RES_USER = "USER_VALUE"
_RES_CALC = "CALCULATED_VALUE"


def _is_numeric(v: Any) -> bool:
    """判断值是否可参与偏差计算。bool 视为非数值（避免 True/False 误判）。"""
    return isinstance(v, Real) and not isinstance(v, bool)


class PropertyConflictResolver:
    """物性冲突解决器（无状态；可作单例 / 每次新建皆可）。

    输入：user_provided_properties_json + calculated_properties_json（dict）
    输出：list[ConflictResolution] + effective dict + conflict_resolutions_json
    """

    # ------------------------------------------------------------------
    # 核心：resolve
    # ------------------------------------------------------------------

    def resolve(
        self,
        *,
        user_props: dict[str, Any],
        calc_props: dict[str, Any],
    ) -> list[ConflictResolution]:
        """检测 user vs calc 的物性冲突。"""
        conflicts: list[ConflictResolution] = []
        # USER_PRIORITY 字段（实测优先）
        for field, threshold in USER_PRIORITY_FIELDS.items():
            if field not in user_props or field not in calc_props:
                continue
            u = user_props[field]
            c = calc_props[field]
            if not _is_numeric(u) or not _is_numeric(c):
                continue
            c_val = float(c)
            if c_val == 0:
                continue  # 无基准，跳过（与 CALCULATED 一致行为）
            deviation = abs(float(u) - c_val) / abs(c_val)
            if deviation > threshold:
                conflicts.append(
                    ConflictResolution(
                        severity=ConflictSeverity.WARN,
                        field=field,
                        user_value=u,
                        calculated_value=c,
                        resolution=_RES_USER,
                        message=(
                            f"用户 {field}={u} 与计算值 {c} 偏差 {deviation:.1%}，"
                            f"超过阈值 {threshold:.0%}，请确认是否为实测值"
                        ),
                    )
                )
            else:
                conflicts.append(
                    ConflictResolution(
                        severity=ConflictSeverity.INFO,
                        field=field,
                        user_value=u,
                        calculated_value=c,
                        resolution=_RES_USER,
                        message=(
                            f"用户 {field}={u} 与计算值 {c} 偏差 {deviation:.1%}，"
                            "用户值已采用"
                        ),
                    )
                )
        # CALCULATED_PRIORITY 字段（精确计算优先）
        for field, threshold in CALCULATED_PRIORITY_FIELDS.items():
            if field not in user_props or field not in calc_props:
                continue
            u = user_props[field]
            c = calc_props[field]
            if not _is_numeric(u) or not _is_numeric(c):
                continue
            c_val = float(c)
            if c_val == 0:
                continue  # 避免 ZeroDivisionError
            deviation = abs(float(u) - c_val) / abs(c_val)
            if deviation > threshold:
                conflicts.append(
                    ConflictResolution(
                        severity=ConflictSeverity.WARN,
                        field=field,
                        user_value=u,
                        calculated_value=c,
                        resolution=_RES_CALC,
                        message=(
                            f"{field} 由组成/换算精确计算"
                            f"（偏差 {deviation:.1%} > {threshold:.0%}），"
                            "用户输入已被忽略"
                        ),
                    )
                )
            # 偏差 ≤ 阈值：用户值与计算值一致，无需冲突
        return conflicts

    # ------------------------------------------------------------------
    # effective = calculated ⊕ user_provided
    # ------------------------------------------------------------------

    def compute_effective(
        self,
        *,
        user_props: dict[str, Any],
        calc_props: dict[str, Any],
    ) -> dict[str, Any]:
        """合成 effective_properties_json。

        规则：effective = calculated ⊕ user（user 顶层键覆写 calculated），
        但 CALCULATED_PRIORITY_FIELDS 始终取 calculated。
        非 USER/CALC_PRIORITY 的字段（如 source="Joback" 元数据）按
        顶层 merge 走 user 优先。
        """
        effective: dict[str, Any] = dict(calc_props)
        for k, v in user_props.items():
            if k in CALCULATED_PRIORITY_FIELDS:
                # 计算值优先：effective 已是 calc 值，不覆写
                continue
            effective[k] = v
        return effective

    # ------------------------------------------------------------------
    # conflict_resolutions_json 序列化
    # ------------------------------------------------------------------

    def to_conflict_resolutions_json(
        self, conflicts: list[ConflictResolution]
    ) -> dict[str, dict[str, Any]]:
        """把 ConflictResolution 列表压缩成 streams.conflict_resolutions_json 形态。

        输出契约：
            {
              "<field>": {
                  "strategy": "USER_PROVIDED" | "CALCULATED",
                  "diff_pct": float,
                  "severity": "BLOCK" | "WARN" | "INFO",
                  "message": str,
              },
              ...
            }
        与 tests/models/test_streams_sim_fields.py:87 契约一致。
        """
        out: dict[str, dict[str, Any]] = {}
        for c in conflicts:
            # diff_pct
            uv = c.user_value
            cv = c.calculated_value
            if _is_numeric(uv) and _is_numeric(cv) and float(cv) != 0:
                diff = abs(float(uv) - float(cv)) / abs(float(cv)) * 100
            else:
                diff = 0.0
            strategy = (
                "USER_PROVIDED"
                if c.resolution == _RES_USER
                else "CALCULATED"
            )
            out[c.field] = {
                "strategy": strategy,
                "diff_pct": round(diff, 4),
                "severity": c.severity.value,
                "message": c.message,
            }
        return out
