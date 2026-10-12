"""c2：BASIC / DETAIL 双样式（ADR-0028「模板源与输出样式」）。

ADR 的关键句：「双模板 = 双套 ReportStyle + 字段映射配置，而非两个
.dotx / .xltx 文件」。所以 c2 交付的是**样式预设 + 分级闸**，不是模板文件。

## 三条边界

1. **BASIC 报表里不许有 DETAIL 字段。** 不校验的话，用户（或前端）给一份
   BASIC 定义选了 `lmtd`，报表照跑，只是多出一列 —— 而 ADR 的分级标准
   就是「BASIC 不含几何/热阻明细」，多一列等于分级失效。
2. **`heat_exchanger_type` 分支只影响版式**，不影响能不能选字段：
   专属几何字段（`baffle_spacing` 只属管壳式）在字段树里按类型分组，
   但**不是**硬闸 —— 用户可能先建报表再定类型。
3. **BASIC 与 DETAIL 的样式是真的不同**（横向/纵向、字号、斑马纹），
   不是同一个样式换个名字。否则「两套样式」只是措辞。
"""
from __future__ import annotations

import pytest

from app.services.exceptions import PcsError


def test_basic_and_detail_styles_are_genuinely_different():
    """两套预设必须真的不同 —— 相同的话「双样式」只是措辞。"""
    from app.services.report.style import heat_detail_styles

    a = heat_detail_styles("BASIC")
    b = heat_detail_styles("DETAIL")
    assert a.orientation != b.orientation, \
        "ADR：HTRI 空冷器横向、TEMA 管壳式纵向；BASIC/DETAIL 应有版式差别"
    assert a.model_dump() != b.model_dump()


def test_detail_level_enum_is_closed():
    """分级只有 BASIC / DETAIL。拼错必须报错，不能静默当 DETAIL ——
    静默升级的代价是 BASIC 报表多出 40 列。"""
    from app.services.report.style import heat_detail_styles

    with pytest.raises(PcsError) as e1:
        heat_detail_styles("basic")          # 大小写敏感
    assert e1.value.code == "REPORT_DETAIL_LEVEL_INVALID"
    with pytest.raises(PcsError) as e2:
        heat_detail_styles("ULTRA")
    assert e2.value.code == "REPORT_DETAIL_LEVEL_INVALID"


def test_heat_exchanger_type_is_part_of_the_style():
    """ADR：「ReportStyle 中通过 heat_exchanger_type 区分 AIR_COOLER /
    SHELL_TUBE，渲染器据此选择对应的表格结构」。"""
    from app.services.report.style import heat_detail_styles

    ac = heat_detail_styles("DETAIL", exchanger_type="AIR_COOLER")
    st = heat_detail_styles("DETAIL", exchanger_type="SHELL_TUBE")
    assert ac.heat_exchanger_type == "AIR_COOLER"
    assert st.heat_exchanger_type == "SHELL_TUBE"
    assert ac.orientation != st.orientation, \
        "ADR：空冷器横向布局、管壳式纵向布局"


def test_unknown_exchanger_type_is_rejected():
    from app.services.report.style import heat_detail_styles

    with pytest.raises(ValueError):
        heat_detail_styles("DETAIL", exchanger_type="PLATE")


def test_presets_respect_locked_company_standards():
    """预设不能解锁公司强制标准（page_size/orientation 由 defaults 锁）。

    ⚠️ `orientation` 同时在 locked_fields 里又要在两套预设里不同 ——
    矛盾。裁决：**locked_fields 只作用于 `resolve()` 的层级合并**，
    预设本身是公司标准的一部分，可以带不同的 orientation；
    但 page_size 两套预设必须一致（都是 A4 横向/纵向）。
    """
    from app.services.report.style import heat_detail_styles

    a = heat_detail_styles("BASIC")
    b = heat_detail_styles("DETAIL")
    assert a.page_size == b.page_size, \
        "两套预设的纸张规格必须一致（公司强制标准）"


# --- 分级闸 -------------------------------------------------------------------


def test_basic_level_permits_only_basic_fields():
    from app.services.report.datasource_registry import DATASOURCES
    from app.services.report.detail_level import fields_visible_at

    heat = DATASOURCES["HEAT_RESULTS"]
    detail_only = [n for n, s in heat.fields.items() if s.level == "DETAIL"]
    assert detail_only, "注册表里没有 DETAIL 字段 —— 分级闸无从验起"

    with pytest.raises(Exception) as exc:
        fields_visible_at("HEAT_RESULTS", "BASIC", want=[detail_only[0]])
    assert exc.value.code == "REPORT_DETAIL_LEVEL_VIOLATION"


def test_detail_level_permits_both():
    from app.services.report.datasource_registry import DATASOURCES
    from app.services.report.detail_level import fields_visible_at

    heat = DATASOURCES["HEAT_RESULTS"]
    mixed = [n for n, s in heat.fields.items()][:5]
    assert fields_visible_at("HEAT_RESULTS", "DETAIL", want=mixed) == mixed


def test_non_heat_sources_are_unaffected_by_detail_level():
    """只有 HEAT 有分级。其他数据源在 BASIC 下也必须照常可用 ——
    给所有数据源都套分级会让「BASIC 报表不能选设备字段」。"""
    from app.services.report.datasource_registry import DATASOURCES
    from app.services.report.detail_level import fields_visible_at

    equip = [n for n in DATASOURCES["EQUIP_LIST"].fields][:3]
    assert fields_visible_at("EQUIP_LIST", "BASIC", want=equip) == equip
