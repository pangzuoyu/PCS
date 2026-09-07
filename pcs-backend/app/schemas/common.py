"""COMMON API schemas（Pydantic v2；P3.3 / spec §3.2.3）。

数据来源标记：EXPERIMENTAL（实验值）/ IAPWS-IF97（高精度标准值）/
ESTIMATED（估算值）/ REFERENCE（标准规范值：ASME B31.3 Table A-1 / 内置安全库）。
"""
from __future__ import annotations

from pydantic import BaseModel, Field


class MaterialSearchResult(BaseModel):
    """材料搜索结果（chemicals 库 + 公式/CAS 命中）。"""

    cas: str = Field(..., description="CAS 注册号")
    name: str = Field(..., description="物质名（common_name 或 iupac_name）")
    formula: str | None = Field(None, description="分子式")
    mw: float | None = Field(None, description="分子量 g/mol")
    source: str = Field(default="CHEMICALS_LIBRARY", description="数据来源标记")


class MaterialDetail(MaterialSearchResult):
    """材料物性详情（CAS → 完整物性）。"""

    tc_k: float | None = Field(None, description="临界温度 K（IAPWS-IF97 水为 647.096）")
    pc_pa: float | None = Field(None, description="临界压力 Pa")
    tb_k: float | None = Field(None, description="常压沸点 K")
    tm_k: float | None = Field(None, description="三相点/熔点 K")
    synonyms: list[str] = Field(default_factory=list, description="别名列表")
    source: str = Field(
        default="EXPERIMENTAL",
        description="EXPERIMENTAL 实验值 / IAPWS-IF97 标准值 / ESTIMATED 估算值",
    )


class AllowableStressResult(BaseModel):
    """材料许用应力（ASME B31.3 Table A-1 插值）。"""

    material: str = Field(..., description="材料牌号（如 A106-GrB）")
    temp_c: float = Field(..., description="查询温度 °C")
    stress_mpa: float = Field(..., description="许用应力 MPa")
    interpolated: bool = Field(
        ...,
        description="是否插值（True=节点之间 / False=刚好命中表节点）",
    )
    source: str = Field(
        default="ASME_B31.3_TABLE_A1",
        description="数据来源：ASME B31.3 Table A-1",
    )


class SafetyResult(BaseModel):
    """介质安全数据（毒性分类 + 爆炸极限）。"""

    cas: str = Field(..., description="CAS 注册号")
    name: str | None = Field(None, description="物质名")
    toxicity_class: str = Field(
        ...,
        description="毒性分类：NONE / LOW / MEDIUM / HIGH / EXTREME",
    )
    lel_vol_pct: float | None = Field(None, description="爆炸下限 LEL vol%")
    uel_vol_pct: float | None = Field(None, description="爆炸上限 UEL vol%")
    source: str = Field(
        default="INTERNAL_SAFETY_DB",
        description="INTERNAL_SAFETY_DB 内置库 / CHEMICALS_SAFETY chemicals.iapws 派生",
    )