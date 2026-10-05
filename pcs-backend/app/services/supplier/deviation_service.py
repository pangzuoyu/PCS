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
    """一条允许偏差规则。`lower`/`upper` 单位为百分点（相对设计值）。"""

    parameter: str
    kind: str
    lower: float | None = None
    upper: float | None = None
    ratio: float | None = None
    spec_ref: str = ""
    aliases: tuple[str, ...] = field(default_factory=tuple)

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
        kind="SYMMETRIC_BAND",
        lower=-10.0,
        upper=10.0,
        spec_ref="SPEC §3.2.4(2) 实际电机额定功率：偏差 ±10%",
        aliases=("电机功率", "设计电机功率", "额定功率", "功率"),
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
    "verdict_color",
    "verdict_label",
]
