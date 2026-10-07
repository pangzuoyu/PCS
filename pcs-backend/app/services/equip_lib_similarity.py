"""设备库相似度计算（UI-SPEC §7.16 / P7 S3-2）。

UI-SPEC 原文：「相似度 ≥90% 推荐，80~90% 需校核，<80% 仅展示。」

**为什么相似度是承重墙而非锦上添花**：2026-10-07 裁决「settle 不做硬去重，
重复沉淀交给相似度归并」。这意味着库里允许同一型号有多条记录，而**相似度
是唯一让操作员看出「这些其实是同一台设备」的机制** —— 没有它，设备库会
退化成设备台账副本（而台账是 equipment_list 已经干的事）。

6 个维度对应 settle 沉淀的标准信息：设备类型 / 设备代号 / 材质 / 标准图号 /
重量 / 关键尺寸。

⚠️ **权重用模块常量而非 CONFIG 表**：权重是调参旋钮，读一次要过一次 async
DB，而相似度在检索路径上逐条调用（每条候选算一次）。真要按需调参再上
CONFIG（届时照 `services/_compound_config_cache.py` 的 5-min TTL 缓存范式）。
现在上 CONFIG 属于为不存在的需求付运行成本。
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Final

# 档位（UI-SPEC §7.16）
RECOMMEND: Final = "RECOMMEND"        # ≥90% 推荐
VERIFY: Final = "VERIFY"              # 80~90% 需校核
DISPLAY_ONLY: Final = "DISPLAY_ONLY"  # <80% 仅展示

_RECOMMEND_THRESHOLD: Final = 0.90
_VERIFY_THRESHOLD: Final = 0.80

# 分类维度（字符串精确比对，忽略大小写与首尾空白）
#
# ⚠️ **刻意不含 `equipment_type`**：它同时是检索的过滤条件。若也算相似度
# 维度，筛 PUMP 时每条结果在「类型」上都恒等于 1.0，而其余维度缺值会跳过
# → 全部条目都算出 1.0 / RECOMMEND，整个信号变成噪声。作为相似度维度，
# 它在使用场景里是恒真的废话。
_CATEGORICAL: Final = ("type_code", "material", "standard_drawing_no")
# 数值维度（相对差）
_NUMERIC: Final = ("weight_kg",)

# 各维度权重，合计 1.0
_WEIGHTS: Final[dict[str, float]] = {
    "type_code": 0.40,          # 型号最重 —— 不同型号就是不同设备
    "material": 0.20,
    "standard_drawing_no": 0.13,
    "weight_kg": 0.13,
    "key_dimensions": 0.14,
}

# 数值比对的相对差容忍：小于该比例算完全一致
_EPSILON: Final = 1e-9


@dataclass(frozen=True)
class SimilarityResult:
    """一次比对的结论。

    Attributes:
        score: 0..1 总体相似度。
        tier: RECOMMEND / VERIFY / DISPLAY_ONLY。
        per_dimension: 参与计分的各维度得分（未参与的不出现，便于排查）。
    """

    score: float
    tier: str
    per_dimension: dict[str, float] = field(default_factory=dict)


def classify(score: float) -> str:
    """按 UI-SPEC §7.16 把分数映射到档位。"""
    if score >= _RECOMMEND_THRESHOLD:
        return RECOMMEND
    if score >= _VERIFY_THRESHOLD:
        return VERIFY
    return DISPLAY_ONLY


def flatten_standard_info(content_json: dict[str, Any] | None) -> dict[str, Any]:
    """把 ConfigAsset.content_json 摊平成可直接比对的结构。

    沉淀时信息分两层：`equipment_type` 在顶层，其余在 `standard_info` 内。
    比对时不该关心这个嵌套，故摊平。
    """
    if not content_json:
        return {}
    flat: dict[str, Any] = {}
    standard = content_json.get("standard_info")
    if isinstance(standard, dict):
        flat.update(standard)
    for key in ("equipment_type",):
        if key in content_json:
            flat[key] = content_json[key]
    return flat


def _categorical_score(a: Any, b: Any) -> float:
    """字符串维度：归一化后完全相同记 1.0，否则 0.0。"""
    if a is None or b is None:
        return 0.0
    return 1.0 if str(a).strip().casefold() == str(b).strip().casefold() else 0.0


def _numeric_score(a: Any, b: Any) -> float | None:
    """数值维度：相对差。`850 vs 900` 高分，`850 vs 12000` 低分。

    用绝对差是错的 —— 泵的重量都在几百公斤，绝对差会把所有泵判成「不像」。
    返回 None 表示该维度不可比（缺值 / 非数值），由调用方跳过。
    """
    try:
        fa, fb = float(a), float(b)
    except (TypeError, ValueError):
        return None
    denom = max(abs(fa), abs(fb), _EPSILON)
    return max(0.0, 1.0 - min(1.0, abs(fa - fb) / denom))


def _key_dimensions_score(a: Any, b: Any) -> float | None:
    """关键尺寸：只比共有键，各自取相对差后取均值。

    两个设备的尺寸项本就可能不同（一边有 DN/PN，另一边有压力等级），
    比共有键才有意义。无共有键 → 不可比。
    """
    if not isinstance(a, dict) or not isinstance(b, dict):
        return None
    shared = [k for k in a if k in b]
    if not shared:
        return None
    scores = [s for s in (_numeric_score(a[k], b[k]) for k in shared) if s is not None]
    if not scores:
        return None
    return sum(scores) / len(scores)


def compute_similarity(
    reference: dict[str, Any] | None, candidate: dict[str, Any] | None
) -> SimilarityResult:
    """算两个标准化信息块的相似度（0..1）。

    **缺数据 ≠ 不相似**：某一维度任一侧缺值时该维度**跳过**，权重在剩余
    维度间重新归一。设备库里大量条目没有 weight_kg，若缺即判 0 分，
    所有设备都会被压到「仅展示」，相似度就失去筛选意义。

    反过来，**两侧都无可比维度时返回 0.0 而非 1.0** —— 「什么都不知道」
    不等于「完全相同」，报 1.0 会把陌生条目当成熟悉设备推荐出去。
    """
    ref = reference or {}
    cand = candidate or {}

    per_dimension: dict[str, float] = {}
    weighted_sum = 0.0
    weight_total = 0.0

    for dim in _CATEGORICAL:
        a, b = ref.get(dim), cand.get(dim)
        if a is None or b is None:      # 缺值 → 跳过，不计 0
            continue
        per_dimension[dim] = _categorical_score(a, b)
        weighted_sum += _WEIGHTS[dim] * per_dimension[dim]
        weight_total += _WEIGHTS[dim]

    for dim in _NUMERIC:
        a, b = ref.get(dim), cand.get(dim)
        if a is None or b is None:
            continue
        s = _numeric_score(a, b)
        if s is None:
            continue
        per_dimension[dim] = s
        weighted_sum += _WEIGHTS[dim] * s
        weight_total += _WEIGHTS[dim]

    a, b = ref.get("key_dimensions"), cand.get("key_dimensions")
    if a is not None and b is not None:
        s = _key_dimensions_score(a, b)
        if s is not None:
            per_dimension["key_dimensions"] = s
            weighted_sum += _WEIGHTS["key_dimensions"] * s
            weight_total += _WEIGHTS["key_dimensions"]

    if weight_total <= 0.0 or math.isnan(weighted_sum):
        return SimilarityResult(score=0.0, tier=DISPLAY_ONLY, per_dimension={})

    score = round(weighted_sum / weight_total, 4)
    return SimilarityResult(score=score, tier=classify(score), per_dimension=per_dimension)
