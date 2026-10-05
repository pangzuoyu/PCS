"""供应商偏差判定引擎 (P7 Sprint 4 S4-2 / SPEC V1.4 §3.2.4(2)).

SPEC §3.2.4(2) 的允许偏差表**以泵为例**，6 条规则的判定类型是异构的 ——
不是一条统一的百分比公式：

| 实际数据字段      | 允许偏差                | kind             | 语义                    |
|-------------------|-------------------------|------------------|-------------------------|
| 实际流量-扬程曲线  | 额定点扬程 +5%/-0%      | ASYMMETRIC_BAND  | 低于额定点→不满足工况    |
| 实际效率曲线       | ≥95% 设计值             | MIN_RATIO        | 低于→能效不达标          |
| 实际NPSHr         | 不得超过设计值          | MAX_ONLY         | 超过→汽蚀风险            |
| 实际电机额定功率   | 偏差 ±10%               | SYMMETRIC_BAND   | 偏小→不满足，偏大→可接受 |
| 实际转速、叶轮直径 | 允许差异，需重新校核性能 | RECHECK_ALWAYS   | 恒需复核                 |
| 厂家型号、材质     | 不得低于设计要求         | MANUAL_CHECK     | 序数比较，机器判不了      |

套一条统一公式会把 6 条判错至少 4 条，故按 kind 分派。

第 4 档 `UNVERDICTABLE`（不可判）是本引擎在 SPEC 三档之外的补充：表内本就有
2 条无数值阈值规则，且表头明写「以泵为例」—— 非泵设备参数必然落不到规则。
把「判不了」并入「合格」会让 SPEC §3.2.4(4) 的确认门禁形同虚设，故独立成档、
且**不可确认**（fail-closed）。
"""

from __future__ import annotations

from dataclasses import dataclass, field

# 结论档位
QUALIFIED = "QUALIFIED"
WARNING = "WARNING"
UNQUALIFIED = "UNQUALIFIED"
UNVERDICTABLE = "UNVERDICTABLE"

_LABELS = {
    QUALIFIED: "合格",
    WARNING: "警告",
    UNQUALIFIED: "不合格",
    UNVERDICTABLE: "不可判",
}

# SPEC §3.2.4(3) 三档颜色；不可判用灰色（本引擎新增档，非 SPEC 规定）
_COLORS = {
    QUALIFIED: "绿色",
    WARNING: "黄色",
    UNQUALIFIED: "红色",
    UNVERDICTABLE: "灰色",
}


@dataclass(frozen=True)
class DeviationRule:
    """一条允许偏差规则。`lower`/`upper` 单位为百分点（相对设计值）。

    `design_parameter`: 判定所依据的**设计参数名**。默认与 `parameter` 同名；
    电机裕量规则例外 —— 它的参照量是**轴功率**而非设计电机功率。
    """

    parameter: str
    kind: str
    lower: float | None = None
    upper: float | None = None
    ratio: float | None = None
    spec_ref: str = ""
    aliases: tuple[str, ...] = field(default_factory=tuple)
    design_parameter: str | None = None

    @property
    def design_key(self) -> str:
        """在 `design_parameters_json` 里查哪个键。"""
        return self.design_parameter or self.parameter

    def matches(self, name: str) -> bool:
        key = _normalize(name)
        return key == _normalize(self.parameter) or key in {
            _normalize(a) for a in self.aliases
        }


@dataclass(frozen=True)
class Evaluation:
    verdict: str
    deviation_pct: float | None = None
    note: str = ""
    requires_recheck: bool = False
    requires_manual_check: bool = False

    @property
    def label(self) -> str:
        return _LABELS[self.verdict]

    @property
    def color(self) -> str:
        return _COLORS[self.verdict]


# 边界比较容差 —— 33.6/32.0-1 在 IEEE754 下是 5.000000000000004%，不兜住会把
# 「恰好 +5%」判成超限。SPEC 的带宽边界是闭区间，不能被浮点噪声顶出去。
_EPS = 1e-9


def _normalize(name: str) -> str:
    """参数名归一 —— 录入方（供应商/设计人）与 SPEC 用词不必一致。"""
    return str(name).strip().lower().replace(" ", "").replace("_", "")


# ---------------------------------------------------------------------------
# SPEC §3.2.4(2) 允许偏差表（逐条转录，勿凭印象改数值）
# ---------------------------------------------------------------------------

SPEC_RULES: tuple[DeviationRule, ...] = (
    DeviationRule(
        parameter="扬程",
        kind="ASYMMETRIC_BAND",
        lower=0.0,
        upper=5.0,
        spec_ref="SPEC §3.2.4(2) 实际流量-扬程曲线：额定点扬程 +5%/-0%",
        aliases=("设计扬程", "实际扬程", "H", "扬程H"),
    ),
    DeviationRule(
        parameter="效率",
        kind="MIN_RATIO",
        ratio=0.95,
        spec_ref="SPEC §3.2.4(2) 实际效率曲线：设计流量下实际效率 ≥95% 设计值",
        aliases=("设计效率", "实际效率", "η", "eta", "效率η"),
    ),
    DeviationRule(
        parameter="NPSHr",
        kind="MAX_ONLY",
        spec_ref="SPEC §3.2.4(2) 实际NPSHr：实际值不得超过设计值",
        aliases=("NPSR", "npshr", "汽蚀余量", "设计NPSHr", "实际NPSHr"),
    ),
    DeviationRule(
        parameter="电机额定功率",
        kind="MOTOR_TIER_FLOOR",
        design_parameter="轴功率",   # ← 参照量是轴功率, 不是「设计电机功率」
        spec_ref=(
            "API 610 电机裕量分档下限: <22kW 1.25 / 22-55kW 1.15 / >55kW 1.10"
            "（**取代** SPEC §3.2.4(2) 原「偏差 ±10%」—— 电机按系列选取, "
            "±10% 量的是档位差不是设备偏差, 见 tests/.../test_motor_tier_rule.py）"
        ),
        aliases=("电机功率", "额定功率", "功率", "电机"),
    ),
    # 电机功率规则的**参照物**是轴功率, 不是「设计电机功率」。
    # 故轴功率单独建一条规则, 让录入方把设计值也带进来。
    DeviationRule(
        parameter="轴功率",
        kind="REFERENCE_ONLY",
        spec_ref=(
            "设计轴功率 —— 电机裕量分档的参照量, 本身不判合格与否"
        ),
        aliases=("设计轴功率", "泵轴功率", "shaft_power", "轴功"),
    ),
    DeviationRule(
        parameter="转速",
        kind="RECHECK_ALWAYS",
        spec_ref="SPEC §3.2.4(2) 实际转速、叶轮直径：允许差异，需重新校核性能",
        aliases=("实际转速", "设计转速", "叶轮直径", "实际叶轮直径", "设计叶轮直径"),
    ),
    DeviationRule(
        parameter="材质",
        kind="MANUAL_CHECK",
        spec_ref="SPEC §3.2.4(2) 厂家型号、材质：材质不得低于设计要求",
        aliases=("厂家型号", "型号", "材质牌号", "设计材质"),
    ),
)

_RULE_INDEX = {r.parameter: r for r in SPEC_RULES}


def find_rule(name: str) -> DeviationRule | None:
    """按参数名查规则；查不到返回 None（调用方据此判「无判定规则」）."""
    for rule in SPEC_RULES:
        if rule.matches(name):
            return rule
    return None


# ---------------------------------------------------------------------------
# 判定
# ---------------------------------------------------------------------------


def _is_number(value) -> bool:
    return not isinstance(value, bool) and isinstance(value, (int, float))


# API 610 电机裕量分档（泵轴功率 kW → 电机功率下限倍数）。
# 1.25 只是**小泵档**, 不是通用值 —— 蜡油加氢 132-P-101A/B 轴功率 2214 kW、
# 选配电机 2500 kW, 比值 1.129, 拍 1.25 会把它误判成不合格, 而大泵 1.10 即合规。
# 边界按 API 610 原文: <22 → 1.25 / 22–55(**含**) → 1.15 / >55 → 1.10
_MOTOR_TIER_SMALL_MAX = 22.0
_MOTOR_TIER_MED_MAX = 55.0


def motor_tier_factor(shaft_power_kw) -> float | None:
    """按 API 610 返回电机功率下限倍数。轴功率非正/非数值 → None（无档可卡）."""
    if not _is_number(shaft_power_kw) or shaft_power_kw <= 0:
        return None
    if shaft_power_kw < _MOTOR_TIER_SMALL_MAX:
        return 1.25
    if shaft_power_kw <= _MOTOR_TIER_MED_MAX:
        return 1.15
    return 1.10


def evaluate(
    rule: DeviationRule, *, design, actual
) -> Evaluation:
    """按规则判定单参数。

    设计值/实际值任一缺失、或不是数值 → `UNVERDICTABLE`（不可判，非合格）。
    """
    if rule.kind == "MANUAL_CHECK":
        return Evaluation(
            UNVERDICTABLE,
            note="序数比较（不得低于），机器判不了 —— 需人工核对",
            requires_manual_check=True,
        )
    if rule.kind == "RECHECK_ALWAYS":
        return Evaluation(
            WARNING,
            note="允许差异，但需重新校核性能（校核未做前不算合格）",
            requires_recheck=True,
        )
    if rule.kind == "REFERENCE_ONLY":
        # 参照量（如轴功率服务于电机分档）—— 本身不判合格与否, 但也不是「不可判」:
        # 它是有效数据, 只是不承担判定。标为合格 + 备注, 避免把有效设计值报成缺数据。
        return Evaluation(
            QUALIFIED,
            None,
            note="参照量，本身不判合格与否（供其他规则使用）",
        )

    if rule.kind == "MOTOR_TIER_FLOOR":
        return _evaluate_motor_tier(design, actual)

    if design is None or actual is None:
        return Evaluation(UNVERDICTABLE, note="缺设计值或实际值")
    if not _is_number(design) or not _is_number(actual):
        return Evaluation(UNVERDICTABLE, note="设计值/实际值非数值，无法按数值规则判定")
    if design == 0:
        return Evaluation(UNVERDICTABLE, note="设计值为 0，百分比偏差无定义")

    deviation = (actual - design) / design * 100.0
    if rule.kind == "ASYMMETRIC_BAND":
        if deviation < rule.lower - _EPS:
            return Evaluation(UNQUALIFIED, deviation, f"低于额定点下限 {rule.lower:g}%")
        if deviation > rule.upper + _EPS:
            return Evaluation(WARNING, deviation, f"超出上限 {rule.upper:g}%（偏大可接受）")
        return Evaluation(QUALIFIED, deviation)

    if rule.kind == "SYMMETRIC_BAND":
        if rule.lower - _EPS <= deviation <= rule.upper + _EPS:
            return Evaluation(QUALIFIED, deviation)
        if deviation > rule.upper:
            return Evaluation(WARNING, deviation, f"超出上限 {rule.upper:g}%（偏大可接受）")
        return Evaluation(UNQUALIFIED, deviation, f"低于下限 {rule.lower:g}%（不满足工艺要求）")

    if rule.kind == "MIN_RATIO":
        ratio = actual / design
        if ratio >= rule.ratio:
            return Evaluation(QUALIFIED, deviation)
        return Evaluation(
            UNQUALIFIED, deviation, f"实际/设计 = {ratio:.3f} < {rule.ratio:.2f}"
        )

    if rule.kind == "MAX_ONLY":
        if actual <= design:
            return Evaluation(QUALIFIED, deviation)
        return Evaluation(UNQUALIFIED, deviation, "超过设计值")

    # 规则表外的 kind —— fail-closed，不当成合格
    return Evaluation(UNVERDICTABLE, deviation, f"未知判定类型 {rule.kind!r}")


def _evaluate_motor_tier(design, actual) -> Evaluation:
    """电机额定功率是否达到 API 610 分档下限.

    `design` = 设计**轴**功率 kW（不是设计电机功率）; `actual` = 实测电机额定功率 kW.
    电机按系列选取, 故**不比较设计电机 vs 实际电机** —— 那量的是档位差。
    """
    if not _is_number(design) or not _is_number(actual):
        return Evaluation(UNVERDICTABLE, note="轴功率/电机功率非数值")
    factor = motor_tier_factor(design)
    if factor is None:
        return Evaluation(
            UNVERDICTABLE, note=f"轴功率 {design} 无适用裕量档（须 > 0）"
        )
    floor = design * factor
    if actual >= floor:
        return Evaluation(
            QUALIFIED,
            note=(
                f"电机 {actual:g} kW ≥ 下限 {floor:.1f} kW"
                f"（轴功率 {design:g} kW × {factor}）"
            ),
        )
    return Evaluation(
        UNQUALIFIED,
        note=(
            f"电机 {actual:g} kW < 下限 {floor:.1f} kW"
            f"（轴功率 {design:g} kW × {factor}）—— 电机不足以驱动"
        ),
    )


def verdict_label(verdict: str) -> str:
    return _LABELS.get(verdict, "不可判")


def verdict_color(verdict: str) -> str:
    return _COLORS.get(verdict, "灰色")


__all__ = [
    "QUALIFIED",
    "WARNING",
    "UNQUALIFIED",
    "UNVERDICTABLE",
    "DeviationRule",
    "Evaluation",
    "SPEC_RULES",
    "evaluate",
    "find_rule",
    "motor_tier_factor",
    "verdict_color",
    "verdict_label",
]
