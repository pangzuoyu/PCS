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


# ---------------------------------------------------------------------------
# C-06 气体热值（P6-4 / spec §3.2.3.6 + GPSA FIG. 23-2 + API 5B6）
# ---------------------------------------------------------------------------


class HeatingValueCalcRequest(BaseModel):
    """气体热值计算请求体（C-06 / spec §3.2.3.6）。

    业务：

    - ``compositions`` 为 ``[{"cas": str, "mol_frac": float}, ...]``，
      至少 1 项；不要求和为 1（service 层自动归一化）。
    - ``excess_air_pct`` 过量空气百分比（默认 0 = 化学计量空气；
      0~1000 范围内有效）。
    """

    compositions: list[dict] = Field(
        ...,
        min_length=1,
        description="组分列表；每项含 cas (CAS 注册号) + mol_frac (摩尔分数)",
    )
    excess_air_pct: float = Field(
        default=0.0,
        ge=0.0,
        le=1000.0,
        description="过量空气百分比（0 = 化学计量；默认 0.0）",
    )


class HeatingValueCalcResponse(BaseModel):
    """气体热值计算响应（C-06 / spec §3.2.3.6）。

    业务（GPSA FIG. 23-2 + API 5B6 公式法）：

    - ``feed_mw_kg_per_kmol`` 进料平均分子量（kg/kmol）；
    - ``hhv_mj_per_sm3`` 高位热值（MJ/sm³，60°F 14.696 psia 标准条件）；
    - ``hhv_btu_per_scf`` 高位热值（BTU/SCF，与 sm³ 同基准条件）；
    - ``lhv_mj_per_sm3`` / ``lhv_btu_per_scf`` 同上 LHV 版；
    - ``stoichiometric_air_sm3_per_sm3`` 化学计量空气（sm³ 空气 / sm³ 燃料）；
    - ``flue_gas_sm3_per_sm3`` 完全燃烧烟气（sm³ 烟气 / sm³ 燃料）；
    - ``flue_gas_composition`` 烟气体积分数 dict（CO2 / H2O / SO2 / N2 / O2）；
    - ``flue_gas_mw_kg_per_kmol`` 烟气平均分子量；
    - ``formula_ref`` CAS → 数据来源标记（GPSA FIG. 23-2 / API 5B6 / MENDELEEV_FALLBACK）。
    """

    feed_mw_kg_per_kmol: float = Field(
        ...,
        description="进料平均分子量（kg/kmol；g/mol 数值相同）",
    )
    hhv_mj_per_sm3: float = Field(
        ...,
        description="高位热值（MJ/sm³；60°F 14.696 psia 标准条件）",
    )
    hhv_btu_per_scf: float = Field(
        ...,
        description="高位热值（BTU/SCF；与 sm³ 同基准条件）",
    )
    lhv_mj_per_sm3: float = Field(
        ...,
        description="低位热值（MJ/sm³；gaseous H2O 生成条件）",
    )
    lhv_btu_per_scf: float = Field(
        ...,
        description="低位热值（BTU/SCF；gaseous H2O 生成条件）",
    )
    stoichiometric_air_sm3_per_sm3: float = Field(
        ...,
        description="化学计量空气体积（sm³ 空气 / sm³ 燃料）",
    )
    flue_gas_sm3_per_sm3: float = Field(
        ...,
        description="完全燃烧烟气体积（sm³ 烟气 / sm³ 燃料）",
    )
    flue_gas_composition: dict[str, float] = Field(
        ...,
        description="烟气体积分数 dict（CO2 / H2O / SO2 / N2 / O2；归一化和=1）",
    )
    flue_gas_mw_kg_per_kmol: float = Field(
        ...,
        description="烟气平均分子量（kg/kmol）",
    )
    formula_ref: dict[str, str] = Field(
        ...,
        description="CAS → 数据来源标记；GPSA_23-2 / API_5B6 / MENDELEEV_FALLBACK",
    )