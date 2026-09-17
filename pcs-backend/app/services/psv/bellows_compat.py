"""SUP-P5-PSV-002 V1.14 §3.8 波纹管材料-介质兼容矩阵。

按 SPEC V1.14 §3.8：

6 种波纹管材料 × ASTM 标准 + forbidden 条件（来源：材料手册 + NACE + API 571）：

| 材料             | ASTM                | 禁用条件                                |
|------------------|---------------------|-----------------------------------------|
| HASTELLOY_C276   | B 575 / B 622       | 强氧化性介质（热浓硝酸等）              |
| ALLOY_C22        | B 575 / B 622       | 强氧化性介质                            |
| SS316L           | A 240 / A 312       | 氯化物 SCC 环境（NACE，500 ppm 保守）   |
| INCONEL_625      | B 443               | 高温高浓度 HF（需专项评估）             |
| INCONEL_718      | B 670               | 高温高硫环境                            |
| ALLOY_400        | B 127 / B 165       | 强氧化性 / 湿 H₂S                       |

设计要点：
- forbidden 列表：每项含 condition（中文短语）+ source（依据来源）
- validate_bellows_compat 匹配 service_note 子串 → 抛 PsvBellowsIncompatible
- 条件匹配：精确子串匹配（in 操作符）；service_note 为 None 时跳过（不抛错）
- 注：氯化物阈值 500 ppm 是工程保守参考，非 NACE 硬性阈值（V1.14 P5 §3.8）

不做：
- 不实现自动介质分析（service_note 是人工输入；氯化物浓度解析 P6+）
- 不强制介质-材料规则（OPEN-06 待 P5+ 裁）
"""
from __future__ import annotations

from typing import Any, Final

from app.services.psv.valve_selection_types import PsvBellowsMaterial

# ---------------------------------------------------------------------------
# §3.8 波纹管材料-介质兼容矩阵
# ---------------------------------------------------------------------------


# forbidden 条件结构：{"condition", "source", "note"?, "conservative_threshold_ppm"?}
BELLOWS_MATERIAL_COMPAT: Final[dict[PsvBellowsMaterial, dict[str, Any]]] = {
    "HASTELLOY_C276": {
        "astm": ["ASTM B 575", "ASTM B 622"],
        "forbidden": [
            {
                "condition": "强氧化性介质",
                "source": "Haynes International C-276 材料手册 + API 571 §3.5.2",
                "note": "热浓硝酸等强氧化环境禁用",
            },
        ],
        "note": "通用耐蚀合金，适用于大多数酸性介质",
    },
    "ALLOY_C22": {
        "astm": ["ASTM B 575", "ASTM B 622"],
        "forbidden": [
            {
                "condition": "强氧化性介质",
                "source": "Haynes International C-22 材料手册",
                "note": "耐蚀性优于 C276，但同样受限于强氧化",
            },
        ],
        "note": "耐蚀性优于 C276",
    },
    "SS316L": {
        "astm": ["ASTM A 240", "ASTM A 312"],
        "forbidden": [
            {
                "condition": "氯化物应力腐蚀开裂",
                "source": "NACE MR0175 / ISO 15156 + 行业工程经验",
                "note": "NACE 对 316L 的氯化物限制非固定阈值；500 ppm 为工程保守参考值",
                "conservative_threshold_ppm": 500,
            },
        ],
        "note": "经济型；高氯环境需按 NACE 评估",
    },
    "INCONEL_625": {
        "astm": ["ASTM B 443"],
        "forbidden": [
            {
                "condition": "高温高浓度氢氟酸",
                "source": "Special Metals INCONEL 625 手册 + HF 环境腐蚀研究",
                "note": "HF 溶液中 Alloy 625 耐蚀性相对优异，非硬性禁忌；高浓度 + 高温需专项评估",
            },
        ],
        "note": "高温高强度；HF 环境耐蚀性优于 C276",
    },
    "INCONEL_718": {
        "astm": ["ASTM B 670"],
        "forbidden": [
            {
                "condition": "高温高硫环境",
                "source": "Special Metals INCONEL 718 手册",
                "note": "高浓度含硫化合物在高温下加速腐蚀",
            },
        ],
        "note": "高强度高温合金",
    },
    "ALLOY_400": {
        "astm": ["ASTM B 127", "ASTM B 165"],
        "forbidden": [
            {
                "condition": "强氧化性介质",
                "source": "Special Metals MONEL 400 手册",
                "note": "MONEL 400 不耐强氧化",
            },
            {
                "condition": "湿 H₂S",
                "source": "Special Metals MONEL 400 手册 + API 571 §3.3",
                "note": "干燥硫和干燥 H₂S 环境可长期使用；湿 H₂S（含水分）敏感",
            },
        ],
        "note": "耐海水和氢氟酸；干燥含硫可用，湿 H₂S 需评估",
    },
}


# ---------------------------------------------------------------------------
# §3.8 校验函数
# ---------------------------------------------------------------------------


def get_bellows_material_info(material: PsvBellowsMaterial) -> dict[str, Any]:
    """获取材料兼容矩阵条目（不存在时 KeyError）。"""
    return BELLOWS_MATERIAL_COMPAT[material]


def get_matching_forbidden_condition(
    material: PsvBellowsMaterial,
    service_note: str | None,
) -> dict[str, Any] | None:
    """检查 service_note 是否匹配材料的 forbidden 条件。

    Returns:
        None = 无匹配（通过）
        dict = 匹配的条件详情（含 condition/source/note/conservative_threshold_ppm）

    Args:
        material: 波纹管材料
        service_note: 服务工况备注（人工输入；包含介质描述）

    Notes:
        - 匹配策略：service_note 子串包含 forbidden.condition
        - service_note 为 None → 返回 None（无信息可判断）
        - 大小写敏感（材料手册术语固定）
    """
    if not service_note:
        return None
    items = BELLOWS_MATERIAL_COMPAT[material].get("forbidden", [])
    for item in items:
        if item["condition"] in service_note:
            return item
    return None


def validate_bellows_compat(
    material: PsvBellowsMaterial,
    service_note: str | None,
) -> None:
    """波纹管材料-介质兼容性校验（§3.8）。

    Raises:
        PsvBellowsIncompatible: 匹配 forbidden 条件时（code=PSV_BELLOWS_INCOMPATIBLE, status=422）

    Notes:
        - service_note 为 None → 不抛错（无信息可判断；由用户承担风险）
        - 抛错时 message 含：材料 + ASTM 标准 + 禁用条件 + 来源
    """
    from app.services.exceptions import PsvBellowsIncompatible  # 延迟 import 避免循环

    matched = get_matching_forbidden_condition(material, service_note)
    if matched is None:
        return

    info = BELLOWS_MATERIAL_COMPAT[material]
    astm_str = " / ".join(info["astm"])
    raise PsvBellowsIncompatible(
        f"波纹管材料 {material}（{astm_str}）禁用于：{matched['condition']}"
        f"（来源：{matched['source']}）",
        details={
            "material": material,
            "astm": info["astm"],
            "forbidden_condition": matched["condition"],
            "source": matched["source"],
            "note": matched.get("note"),
            "conservative_threshold_ppm": matched.get("conservative_threshold_ppm"),
        },
    )


__all__ = [
    "BELLOWS_MATERIAL_COMPAT",
    "get_bellows_material_info",
    "get_matching_forbidden_condition",
    "validate_bellows_compat",
]
