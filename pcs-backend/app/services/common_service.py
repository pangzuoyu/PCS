"""CommonService — 物性查询 + 许用应力插值 + 介质安全数据 + 气体热值（P3.3 + P6-4 / spec §3.2.3）。

数据来源：
- 物性：vendor chemicals1.5.2（search_chemical + identifiers + iapws IAPWS-IF97 水蒸气）；
  不依赖 CoolProp（pcs-backend 未引入；iapws.iapws97_* 与 CoolProp PropsSI 等价）。
- 许用应力：内置 _ASME_B31_3_A1（碳钢 + 不锈钢常用 5 牌号，按温度插值）。
- 介质安全：内置 _SAFETY_DATA（~15 种常见介质毒性 + 爆炸极限）。
- 化合物热值（C-06 / P6-4）：内置 _HARDCODED_COMPOUND_DATA（64 种 GPSA
  FIG. 23-2 + API 5B6 公开值近似；+2 种 Mendeleev 自研 fallback）。生产
  工艺室签字后由 ``compound_heating_values`` CONFIG 表（p6_4_001）替换。

设计要点：
- 全程纯函数 + 静态方法（无 DB），便于单测。
- lazy import chemicals 子模块（避免 module-load 时机问题）。
- 越界 / 缺失抛 PcsError（统一 spec §3.1.2 错误码）。
- 化合物热值模块级 cache 5 min TTL（避免重复 dict 构造）。
"""
# ruff: noqa: E501  (化合物热值表 + 物性表刻意保留紧凑的列对齐 >100 chars)
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from app.services.exceptions import PcsError

# ---------------------------------------------------------------------------
# 内置 ASME B31.3 Table A-1（5 牌号 × 6 温度点）
# 表值取自 ASME B31.3-2020 Table A-1（典型工程常用值，rel=±5% 容差足够 P3 阶段）
# ---------------------------------------------------------------------------

_ASME_B31_3_A1: dict[str, dict[int, float]] = {
    # 碳钢
    "A106-GrB": {38: 137.9, 100: 124.1, 200: 113.8, 300: 96.5, 400: 82.7, 500: 62.1},
    "A53-GrB": {38: 117.2, 100: 103.4, 200: 89.6, 300: 75.8, 400: 65.5, 500: 51.7},
    # 不锈钢 304 / 304L / 316 / 316L
    "304-SS": {38: 137.9, 100: 115.8, 200: 103.4, 300: 96.5, 400: 89.6, 500: 82.7},
    "316-SS": {38: 137.9, 100: 115.8, 200: 103.4, 300: 96.5, 400: 89.6, 500: 82.7},
    "A240-304L": {38: 115.1, 100: 96.5, 200: 82.7, 300: 75.8, 400: 68.9, 500: 62.1},
}

_ASME_TEMPS = (38, 100, 200, 300, 400, 500)


# ---------------------------------------------------------------------------
# 内置介质安全库（15 种常见介质）
# 毒性分级：NONE（基本无毒）/ LOW / MEDIUM / HIGH / EXTREME
# 爆炸极限：LFL/UFL vol% in air
# ---------------------------------------------------------------------------

_SAFETY_DATA: dict[str, dict[str, Any]] = {
    # LFL/UFL 来自 NFPA 68 / Crowl_Louvar（chemicals.LFL_all_methods 同源）
    # --- 烃类 ---
    "74-82-8": {"name": "methane",     "tox": "NONE",    "lfl": 5.0, "ufl": 15.0},
    "74-84-0": {"name": "ethane",      "tox": "LOW",     "lfl": 3.0, "ufl": 12.5},
    "74-98-6": {"name": "propane",     "tox": "LOW",     "lfl": 2.1, "ufl": 9.5},
    "106-97-8": {"name": "n-butane",   "tox": "LOW",     "lfl": 1.8, "ufl": 8.4},
    "110-54-3": {"name": "n-hexane",   "tox": "LOW",     "lfl": 1.1, "ufl": 7.5},
    "67-56-1": {"name": "methanol",    "tox": "MEDIUM",  "lfl": 6.0, "ufl": 36.5},
    "64-17-5": {"name": "ethanol",     "tox": "LOW",     "lfl": 3.3, "ufl": 19.0},
    "71-43-2": {"name": "benzene",     "tox": "HIGH",    "lfl": 1.2, "ufl": 7.8},
    "108-88-3": {"name": "toluene",    "tox": "MEDIUM",  "lfl": 1.1, "ufl": 7.1},
    "1330-20-7": {"name": "xylene",    "tox": "MEDIUM",  "lfl": 0.9, "ufl": 6.7},
    # --- 气体 ---
    "7732-18-5": {"name": "water",      "tox": "NONE",    "lfl": None, "ufl": None},
    "124-38-9": {"name": "CO2",         "tox": "LOW",     "lfl": None, "ufl": None},
    "630-08-0": {"name": "CO",          "tox": "HIGH",    "lfl": 12.5, "ufl": 74.0},
    "7664-41-7": {"name": "NH3",        "tox": "HIGH",    "lfl": 15.0, "ufl": 28.0},
    "7782-50-5": {"name": "Cl2",        "tox": "EXTREME", "lfl": None, "ufl": None},
}


class CommonService:
    """COMMON 子系统服务：物性 + 许用应力 + 介质安全（无 DB）。"""

    @classmethod
    def search_material(cls, keyword: str) -> list[dict[str, Any]]:
        """按名称 / CAS / 分子式搜索 chemicals.search_chemical。

        返回 list[dict]：每条含 cas / name / formula / mw / source。
        空关键字 → 422；无命中 → []。
        """
        kw = (keyword or "").strip()
        if not kw:
            raise PcsError(
                "keyword 必填", code="COMMON_MISSING_KEYWORD", status=422,
            )
        try:
            from chemicals import search_chemical
            from chemicals.identifiers import int_to_CAS

            meta = search_chemical(kw)
            if not meta or not getattr(meta, "CAS", None):
                return []
            cas_int = meta.CAS
            cas_str = int_to_CAS(cas_int)
            name = (
                getattr(meta, "common_name", None)
                or getattr(meta, "iupac_name", None)
                or kw
            )
            return [{
                "cas": cas_str,
                "name": name,
                "formula": getattr(meta, "formula", None),
                "mw": getattr(meta, "MW", None),
                "source": "CHEMICALS_LIBRARY",
            }]
        except PcsError:
            raise
        except ValueError:
            # chemicals 抛 ValueError 表示无命中 → 空列表
            return []
        except Exception as e:  # noqa: BLE001
            raise PcsError(
                f"chemicals 搜索失败：{e}",
                code="COMMON_SEARCH_FAILED", status=500,
            ) from e

    @classmethod
    def get_material(cls, cas: str) -> dict[str, Any]:
        """按 CAS 查完整物性（water 走 IAPWS-IF97 精确值，其余 chemicals）。"""
        cas = (cas or "").strip()
        if not cas:
            raise PcsError("cas 必填", code="COMMON_MISSING_CAS", status=422)
        if cas == "7732-18-5":
            # 水走 IAPWS-IF97 精确值（spec §3.2.3「高精度物性」要求）
            from chemicals.iapws import iapws95_MW, iapws95_Pc, iapws95_Tc, iapws95_Tsat, iapws95_Tt
            return {
                "cas": "7732-18-5",
                "name": "water",
                "formula": "H2O",
                "mw": float(iapws95_MW),
                "tc_k": float(iapws95_Tc),
                "pc_pa": float(iapws95_Pc),
                "tb_k": float(iapws95_Tsat(101325.0)),  # 101325 Pa = 1 atm
                "tm_k": float(iapws95_Tt),
                "synonyms": ["water", "dihydrogen monoxide", "H2O"],
                "source": "IAPWS-IF97",
            }
        try:
            from chemicals import search_chemical
            from chemicals.identifiers import CAS_to_int, int_to_CAS

            cas_int = CAS_to_int(cas)
            meta = search_chemical(cas)
            if not meta or int(meta.CAS) != cas_int:
                raise PcsError(
                    f"CAS {cas} 未命中",
                    code="COMMON_MATERIAL_NOT_FOUND", status=404,
                )
            mw = getattr(meta, "MW", None)
            name = (
                getattr(meta, "common_name", None)
                or getattr(meta, "iupac_name", None)
                or cas
            )
            syn = list(getattr(meta, "synonyms", []) or [])
            return {
                "cas": int_to_CAS(meta.CAS),
                "name": name,
                "formula": getattr(meta, "formula", None),
                "mw": float(mw) if mw else None,
                "tc_k": None,
                "pc_pa": None,
                "tb_k": None,
                "tm_k": None,
                "synonyms": syn,
                "source": "EXPERIMENTAL" if mw else "ESTIMATED",
            }
        except PcsError:
            raise
        except ValueError as e:
            # chemicals 抛 ValueError 表示无命中 → 404
            raise PcsError(
                f"CAS {cas} 未命中：{e}",
                code="COMMON_MATERIAL_NOT_FOUND", status=404,
            ) from e
        except Exception as e:  # noqa: BLE001
            raise PcsError(
                f"chemicals 物性查询失败：{e}",
                code="COMMON_GET_FAILED", status=500,
            ) from e

    @classmethod
    def allowable_stress(cls, material: str, temp_c: float) -> dict[str, Any]:
        """ASME B31.3 Table A-1 按材料牌号 + 温度查许用应力 + 线性插值。

        越界温度 → 422；未知材料 → 404。
        """
        material = (material or "").strip()
        if not material:
            raise PcsError(
                "material 必填", code="COMMON_MISSING_MATERIAL", status=422,
            )
        table = _ASME_B31_3_A1.get(material)
        if table is None:
            raise PcsError(
                f"材料 {material} 不在 ASME B31.3 Table A-1",
                code="COMMON_MATERIAL_NOT_FOUND", status=404,
            )
        tmin, tmax = _ASME_TEMPS[0], _ASME_TEMPS[-1]
        if not (tmin <= temp_c <= tmax):
            raise PcsError(
                f"温度 {temp_c}°C 越界（有效 {tmin}~{tmax}°C）",
                code="COMMON_TEMP_OOB", status=422,
            )
        # 节点温度直接命中 → 精确值
        int_t = int(round(temp_c))
        if int_t in table:
            return {
                "material": material,
                "temp_c": temp_c,
                "stress_mpa": table[int_t],
                "interpolated": False,
                "source": "ASME_B31.3_TABLE_A1",
            }
        # 节点间线性插值（prev = 最靠近 temp_c 且 < temp_c 的节点；
        # next = 最靠近 temp_c 且 > temp_c 的节点）
        prev_t = max(t for t in _ASME_TEMPS if t < temp_c)
        next_t = min(t for t in _ASME_TEMPS if t > temp_c)
        ratio = (temp_c - prev_t) / (next_t - prev_t)
        stress = table[prev_t] + ratio * (table[next_t] - table[prev_t])
        return {
            "material": material,
            "temp_c": temp_c,
            "stress_mpa": round(stress, 3),
            "interpolated": True,
            "source": "ASME_B31.3_TABLE_A1",
        }

    @classmethod
    def safety_data(cls, cas: str) -> dict[str, Any]:
        """按 CAS 查介质毒性 + 爆炸极限（内置库）。"""
        cas = (cas or "").strip()
        if not cas:
            raise PcsError("cas 必填", code="COMMON_MISSING_CAS", status=422)
        rec = _SAFETY_DATA.get(cas)
        if rec is None:
            raise PcsError(
                f"CAS {cas} 无安全数据",
                code="COMMON_SAFETY_NOT_FOUND", status=404,
            )
        return {
            "cas": cas,
            "name": rec["name"],
            "toxicity_class": rec["tox"],
            "lel_vol_pct": rec["lfl"],
            "uel_vol_pct": rec["ufl"],
            "source": "INTERNAL_SAFETY_DB",
        }

    # ---- C-06 气体热值（GPSA FIG. 23-2 + API 5B6 + Mendeleev 自研 fallback）----

    @classmethod
    def calculate_gas_heating_value(
        cls,
        compositions: list[dict[str, Any]],
        excess_air_pct: float = 0.0,
    ) -> HeatingValueResult:
        """按摩尔分数计算混合气体热值 + 烟气组成（C-06 / spec §3.2.3.6）。

        业务：

        - 输入 ``compositions`` 为 ``[{"cas": str, "mol_frac": float}, ...]``，
          不要求和为 1（自动归一化）；按 mol 分数加权计算混合气体的 HHV /
          LHV / 化学计量空气 / 烟气组成 / 烟气 MW。
        - 数据源：``_load_compound_data()`` 命中 DB/硬编码 dict（64 GPSA
          + 2 Mendeleev fallback）；CAS 未命中 → 404。
        - 烟气组成：CO2 / H2O / N2 / SO2 / O2（excess air 时含未反应 O2）。
        - 单位：HHV/LHV per sm³ (60°F, 14.696 psia 标准条件) + per SCF。

        错误：

        - 空 compositions → 422 ``COMMON_HEATING_VALUE_EMPTY``；
        - mol_frac 全 ≤ 0 → 422 ``COMMON_HEATING_VALUE_EMPTY``；
        - CAS 未命中且无 fallback → 404 ``COMMON_HEATING_VALUE_NOT_FOUND``。
        """
        if not compositions:
            raise PcsError(
                "compositions 不能为空",
                code="COMMON_HEATING_VALUE_EMPTY", status=422,
            )
        total_frac = sum(
            float(c.get("mol_frac", 0.0) or 0.0) for c in compositions
        )
        if total_frac <= 0:
            raise PcsError(
                "mol_frac 总和必须 > 0",
                code="COMMON_HEATING_VALUE_EMPTY", status=422,
            )

        data = cls._load_compound_data()

        # ---- 累积加权值（按 mol 分数归一化）----
        weighted_mw: float = 0.0       # g/mol（口径即 kg/kmol）
        weighted_hhv_mj: float = 0.0   # MJ/kmol 燃料（按 mol 分数加权）
        weighted_lhv_mj: float = 0.0
        weighted_stoich_o2: float = 0.0  # mol O2 / mol 燃料
        # 烟气体积（per kmol 燃料，未混空气 N2）
        flue_co2: float = 0.0
        flue_h2o: float = 0.0
        flue_so2: float = 0.0
        flue_n2_from_fuel: float = 0.0
        # 烟气 MW 加权（按 mol 烟气组分）
        flue_mw: float = 0.0

        formula_ref: dict[str, str] = {}

        for comp in compositions:
            cas = str(comp.get("cas", "")).strip()
            mol_frac = float(comp.get("mol_frac", 0.0) or 0.0)
            if not cas or mol_frac <= 0:
                continue

            cd = data.get(cas)
            if cd is None:
                raise PcsError(
                    f"CAS {cas} 未命中且无 Mendeleev fallback 数据",
                    code="COMMON_HEATING_VALUE_NOT_FOUND", status=404,
                )

            norm = mol_frac / total_frac
            mw = cd["mw_g_mol"]  # g/mol
            # 加权进料分子量：g/mol（口径即 kg/kmol）
            weighted_mw += norm * mw
            # HHV / LHV 加权（MJ/kmol 燃料）：
            #   hhv_mj_kg [MJ/kg] × mw_g_mol [g/mol] × (1 kg / 1000 g) × (1000 mol / kmol)
            #   = hhv_mj_kg × mw_g_mol（数值相乘）= MJ/kmol
            weighted_hhv_mj += norm * cd["hhv_mj_kg"] * mw
            weighted_lhv_mj += norm * cd["lhv_mj_kg"] * mw

            # 化学计量 O₂（Mendeleev 自研公式）：stoich_O2 = C + H/4 + S - O/2
            atoms = _COMPOUND_ATOMS.get(cas)
            if atoms is None:
                raise PcsError(
                    f"CAS {cas} 无化学式数据（无法计算化学计量 O₂）",
                    code="COMMON_HEATING_VALUE_NOT_FOUND", status=404,
                )
            c_atoms, h_atoms, n_atoms, s_atoms, o_atoms = atoms
            stoich_o2 = c_atoms + h_atoms / 4.0 + s_atoms - o_atoms / 2.0
            weighted_stoich_o2 += norm * stoich_o2

            # 烟气产物（per mol 燃料）：CO2=C, H2O=H/2, SO2=S, N2_fuel=N/2
            co2_i = c_atoms
            h2o_i = h_atoms / 2.0
            so2_i = s_atoms
            n2_fuel_i = n_atoms / 2.0

            flue_co2 += norm * co2_i
            flue_h2o += norm * h2o_i
            flue_so2 += norm * so2_i
            flue_n2_from_fuel += norm * n2_fuel_i

            # 烟气 MW 加权（按产物 mol）
            flue_mw += norm * (
                co2_i * 44.009
                + h2o_i * 18.015
                + so2_i * 64.066
                + n2_fuel_i * 28.014
            )

            formula_ref[cas] = cd["source"]

        # ---- 化学计量空气（per mol 燃料，理想气 vol/mol = 1）----
        air_per_kmol_fuel = weighted_stoich_o2 / 0.21
        n2_from_air_per_kmol_fuel = air_per_kmol_fuel * 0.79
        excess_o2_per_kmol_fuel = (
            weighted_stoich_o2 * (excess_air_pct / 100.0)
        )

        # ---- 烟气总量（per mol 燃料）----
        flue_total_per_kmol_fuel = (
            flue_co2 + flue_h2o + flue_so2
            + flue_n2_from_fuel + n2_from_air_per_kmol_fuel
            + excess_o2_per_kmol_fuel
        )

        # ---- 单位换算 ----
        # weighted_hhv_mj 是 MJ/kmol 燃料；per sm3 = MJ/kmol / (m³/kmol)
        hhv_mj_per_sm3 = weighted_hhv_mj / SM3_PER_KMOL
        lhv_mj_per_sm3 = weighted_lhv_mj / SM3_PER_KMOL
        # per SCF = MJ/kmol * 1000 kJ/MJ * 0.9478 BTU/kJ / SCF/kmol
        hhv_btu_per_scf = (
            weighted_hhv_mj * 1000.0 * BTU_PER_KJ / SCF_PER_KMOL
        )
        lhv_btu_per_scf = (
            weighted_lhv_mj * 1000.0 * BTU_PER_KJ / SCF_PER_KMOL
        )

        # ---- 烟气组成（体积分数）----
        if flue_total_per_kmol_fuel > 0:
            flue_comp: dict[str, float] = {
                "CO2": flue_co2 / flue_total_per_kmol_fuel,
                "H2O": flue_h2o / flue_total_per_kmol_fuel,
                "SO2": flue_so2 / flue_total_per_kmol_fuel,
                "N2": (flue_n2_from_fuel + n2_from_air_per_kmol_fuel)
                / flue_total_per_kmol_fuel,
                "O2": excess_o2_per_kmol_fuel / flue_total_per_kmol_fuel,
            }
        else:
            flue_comp = {"CO2": 0.0, "H2O": 0.0, "SO2": 0.0, "N2": 0.0, "O2": 0.0}

        return HeatingValueResult(
            feed_mw_kg_per_kmol=round(weighted_mw, 3),
            hhv_mj_per_sm3=round(hhv_mj_per_sm3, 4),
            hhv_btu_per_scf=round(hhv_btu_per_scf, 2),
            lhv_mj_per_sm3=round(lhv_mj_per_sm3, 4),
            lhv_btu_per_scf=round(lhv_btu_per_scf, 2),
            stoichiometric_air_sm3_per_sm3=round(air_per_kmol_fuel, 4),
            flue_gas_sm3_per_sm3=round(flue_total_per_kmol_fuel, 4),
            flue_gas_composition={
                k: round(v, 4) for k, v in flue_comp.items()
            },
            flue_gas_mw_kg_per_kmol=round(flue_mw, 3),
            formula_ref=formula_ref,
        )

    @classmethod
    def _load_compound_data(cls) -> dict[str, dict[str, Any]]:
        """Lazy-load 化合物热值 + 化学式数据（5 min TTL cache）。

        设计：

        - 模块级 dict cache（避免每次重构造 64+2 项 dict）；
        - TTL = 5 min（参见 brief 锚点 _load_compound_data cache 5 min TTL）；
        - 当前实现使用模块级硬编码 dict（生产可替换为 DB 读取
          ``compound_heating_values`` CONFIG 表；DB schema 与本 dict 字段
          一致——``hhv_mj_kg / lhv_mj_kg / mw_g_mol``）。
        """
        global _COMPOUND_CACHE, _COMPOUND_CACHE_TIME  # noqa: PLW0603
        now = time.monotonic()
        if (
            _COMPOUND_CACHE is not None
            and (now - _COMPOUND_CACHE_TIME) < _COMPOUND_CACHE_TTL
        ):
            return _COMPOUND_CACHE

        # 深拷贝避免上游修改污染
        cache: dict[str, dict[str, Any]] = {
            cas: dict(rec) for cas, rec in _HARDCODED_COMPOUND_DATA.items()
        }
        _COMPOUND_CACHE = cache
        _COMPOUND_CACHE_TIME = now
        return _COMPOUND_CACHE

    @classmethod
    def _stoichiometric_o2(cls, compound_cas: str) -> float:
        """Mendeleev 自研 fallback：化学计量 O₂（mol O₂ / mol 燃料）。

        公式（spec §3.2.3.6 + Mendeleev 1898 氧平衡）：

            C_x H_y N_z S_w + (x + y/4 + w) O₂ →
                x CO₂ + y/2 H₂O + z/2 N₂ + w SO₂

        完整 Mendeleev 含 O 平衡：stoich_O2 = C + H/4 + S - O/2
        （含氧化合物如甲醇 CH₄O 的内氧需扣除 1/2 O）。

        返回化学计量氧 mol / mol 燃料；惰性气（He / Ar）返回 0.0。
        """
        cas = (compound_cas or "").strip()
        if not cas:
            raise PcsError(
                "cas 必填", code="COMMON_MISSING_CAS", status=422,
            )
        atoms = _COMPOUND_ATOMS.get(cas)
        if atoms is None:
            raise PcsError(
                f"CAS {cas} 无化学式数据（无法计算 Mendeleev 化学计量 O₂）",
                code="COMMON_FORMULA_NOT_FOUND", status=404,
            )
        c_atoms, h_atoms, _n_atoms, s_atoms, o_atoms = atoms
        return c_atoms + h_atoms / 4.0 + s_atoms - o_atoms / 2.0


# ---------------------------------------------------------------------------
# C-06 气体热值（P6-4 / spec §3.2.3.6 + GPSA FIG. 23-2 + API 5B6）
# ---------------------------------------------------------------------------

# 单位换算常量（GPSA 标准条件 60°F, 14.696 psia）
SCF_PER_KMOL: float = 836.6  # 1 kmol = 836.6 SCF
SM3_PER_KMOL: float = SCF_PER_KMOL * 0.0283168  # = 23.69 m³/kmol
BTU_PER_KJ: float = 1.0 / 1.05506  # 1 kJ = 0.9478 BTU

# 标准生成焓（25°C, kJ/mol；GPSA Thermodynamic Properties 表）
_DHF_CO2_GAS: float = -393.5  # kJ/mol
_DHF_H2O_LIQ: float = -285.8  # kJ/mol（HHV 用 liquid H2O）
_DHF_H2O_GAS: float = -241.8  # kJ/mol（LHV 用 gaseous H2O）
_DHF_SO2_GAS: float = -296.8  # kJ/mol

# 化合物化学式（C, H, N, S, O 原子数）— 64 GPSA/API 常见化合物 + 2 fallback
# D11 fallback：98-82-8 (cumene) + 108-95-2 (phenol) 用于 Mendeleev 单元测试
_COMPOUND_ATOMS: dict[str, tuple[int, int, int, int, int]] = {
    # ---- 轻烃 C1~C10 ----
    "74-82-8":  (1, 4, 0, 0, 0),   # methane
    "74-84-0":  (2, 6, 0, 0, 0),   # ethane
    "74-98-6":  (3, 8, 0, 0, 0),   # propane
    "106-97-8": (4, 10, 0, 0, 0),  # n-butane
    "75-28-5":  (4, 10, 0, 0, 0),  # isobutane
    "109-66-0": (5, 12, 0, 0, 0),  # n-pentane
    "78-78-4":  (5, 12, 0, 0, 0),  # isopentane
    "110-54-3": (6, 14, 0, 0, 0),  # n-hexane
    "107-83-5": (6, 14, 0, 0, 0),  # 2-methylpentane
    "96-14-0":  (6, 14, 0, 0, 0),  # 3-methylpentane
    "142-82-5": (7, 16, 0, 0, 0),  # n-heptane
    "111-65-9": (8, 18, 0, 0, 0),  # n-octane
    "111-84-2": (9, 20, 0, 0, 0),  # n-nonane
    "124-18-5": (10, 22, 0, 0, 0), # n-decane
    "287-92-3": (5, 10, 0, 0, 0),  # cyclopentane
    "110-82-7": (6, 12, 0, 0, 0),  # cyclohexane
    "96-37-7":  (6, 12, 0, 0, 0),  # methylcyclopentane
    "108-87-2": (7, 14, 0, 0, 0),  # methylcyclohexane
    # ---- 烯 / 炔 ----
    "74-85-1":  (2, 4, 0, 0, 0),   # ethylene
    "115-07-1": (3, 6, 0, 0, 0),   # propylene
    "106-98-9": (4, 8, 0, 0, 0),   # 1-butene
    "590-18-1": (4, 8, 0, 0, 0),   # cis-2-butene
    "624-64-6": (4, 8, 0, 0, 0),   # trans-2-butene
    "115-11-7": (4, 8, 0, 0, 0),   # isobutene
    "74-86-2":  (2, 2, 0, 0, 0),   # acetylene
    # ---- 芳香烃 ----
    "71-43-2":  (6, 6, 0, 0, 0),   # benzene
    "108-88-3": (7, 8, 0, 0, 0),   # toluene
    "100-41-4": (8, 10, 0, 0, 0),  # ethylbenzene
    "95-47-6":  (8, 10, 0, 0, 0),  # o-xylene
    "108-38-3": (8, 10, 0, 0, 0),  # m-xylene
    "106-42-3": (8, 10, 0, 0, 0),  # p-xylene
    "91-20-3":  (10, 8, 0, 0, 0),  # naphthalene
    "100-42-5": (8, 8, 0, 0, 0),   # styrene
    # ---- 含氧有机物 ----
    "67-56-1":  (1, 4, 0, 0, 1),   # methanol
    "64-17-5":  (2, 6, 0, 0, 1),   # ethanol
    "67-63-0":  (3, 8, 0, 0, 1),   # isopropanol
    "71-23-8":  (3, 8, 0, 0, 1),   # n-propanol
    "71-36-3":  (4, 10, 0, 0, 1),  # n-butanol
    "67-64-1":  (3, 6, 0, 0, 1),   # acetone
    "78-93-3":  (4, 8, 0, 0, 1),   # methyl ethyl ketone
    "1634-04-4": (5, 12, 0, 0, 1), # MTBE
    "115-10-6": (2, 6, 0, 0, 1),   # dimethyl ether
    "50-00-0":  (1, 2, 0, 0, 1),   # formaldehyde
    "75-07-0":  (2, 4, 0, 0, 1),   # acetaldehyde
    "64-19-7":  (2, 4, 0, 0, 2),   # acetic acid
    # ---- 含硫 ----
    "74-93-1":  (1, 4, 0, 1, 0),   # methyl mercaptan
    "75-08-1":  (2, 6, 0, 1, 0),   # ethyl mercaptan
    "75-18-3":  (2, 6, 0, 1, 0),   # dimethyl sulfide
    "75-15-0":  (1, 0, 0, 2, 0),   # carbon disulfide
    "463-58-1": (1, 0, 0, 1, 1),   # carbonyl sulfide
    "7783-06-4": (0, 2, 0, 1, 0),  # hydrogen sulfide
    # ---- 无机 / 含氮 ----
    "1333-74-0": (0, 2, 0, 0, 0),  # hydrogen
    "630-08-0":  (1, 0, 0, 0, 1),  # carbon monoxide
    "7664-41-7": (0, 3, 1, 0, 0),  # ammonia
    "74-90-8":   (1, 1, 1, 0, 0),  # hydrogen cyanide
    # ---- 不可燃 / 惰性 ----
    "7446-09-5": (0, 0, 0, 1, 2),  # sulfur dioxide
    "7727-37-9": (0, 0, 2, 0, 0),  # nitrogen
    "7782-44-7": (0, 0, 0, 0, 2),  # oxygen
    "7732-18-5": (0, 2, 0, 0, 1),  # water
    "124-38-9":  (1, 0, 0, 0, 2),  # carbon dioxide
    "7440-59-7": (0, 0, 0, 0, 0),  # helium
    "7440-37-1": (0, 0, 0, 0, 0),  # argon
    # ---- 异构 ----
    "540-84-1": (8, 18, 0, 0, 0),  # isooctane
    "592-41-6": (6, 12, 0, 0, 0),  # 1-hexene
    # ---- D11 Mendeleev fallback（不在 64 表；自研 ΔHf° 派生）----
    "98-82-8":  (9, 12, 0, 0, 0),  # cumene / isopropylbenzene (C9H12)
    "108-95-2": (6, 6, 0, 0, 1),   # phenol (C6H6O)
}

# 化合物热值硬编码数据（64 GPSA + 2 fallback）
# 与 scripts/p6_4_gate_03_compound_heating_values_seed.py 同源。
# 行长刻意保留紧凑的 6 字段对齐（>100 chars）；通过文件级 ruff noqa
# 控制，避免 dict literal 多行换行降低可读性。
_HARDCODED_COMPOUND_DATA: dict[str, dict[str, Any]] = {
    "74-82-8":  {"name": "methane",          "hhv_mj_kg": 55.53, "lhv_mj_kg": 50.02, "mw_g_mol": 16.043,  "source": "GPSA_23-2"},
    "74-84-0":  {"name": "ethane",           "hhv_mj_kg": 51.90, "lhv_mj_kg": 47.49, "mw_g_mol": 30.070,  "source": "GPSA_23-2"},
    "74-98-6":  {"name": "propane",          "hhv_mj_kg": 50.35, "lhv_mj_kg": 46.34, "mw_g_mol": 44.097,  "source": "GPSA_23-2"},
    "106-97-8": {"name": "n-butane",         "hhv_mj_kg": 49.50, "lhv_mj_kg": 45.72, "mw_g_mol": 58.123,  "source": "GPSA_23-2"},
    "75-28-5":  {"name": "isobutane",        "hhv_mj_kg": 49.36, "lhv_mj_kg": 45.58, "mw_g_mol": 58.123,  "source": "GPSA_23-2"},
    "109-66-0": {"name": "n-pentane",        "hhv_mj_kg": 48.95, "lhv_mj_kg": 45.35, "mw_g_mol": 72.150,  "source": "GPSA_23-2"},
    "78-78-4":  {"name": "isopentane",       "hhv_mj_kg": 48.74, "lhv_mj_kg": 45.13, "mw_g_mol": 72.150,  "source": "GPSA_23-2"},
    "110-54-3": {"name": "n-hexane",         "hhv_mj_kg": 48.56, "lhv_mj_kg": 45.10, "mw_g_mol": 86.178,  "source": "GPSA_23-2"},
    "107-83-5": {"name": "2-methylpentane",  "hhv_mj_kg": 48.32, "lhv_mj_kg": 44.81, "mw_g_mol": 86.178,  "source": "GPSA_23-2"},
    "96-14-0":  {"name": "3-methylpentane",  "hhv_mj_kg": 48.31, "lhv_mj_kg": 44.78, "mw_g_mol": 86.178,  "source": "GPSA_23-2"},
    "142-82-5": {"name": "n-heptane",        "hhv_mj_kg": 48.28, "lhv_mj_kg": 44.92, "mw_g_mol": 100.205, "source": "GPSA_23-2"},
    "111-65-9": {"name": "n-octane",         "hhv_mj_kg": 48.07, "lhv_mj_kg": 44.79, "mw_g_mol": 114.232, "source": "GPSA_23-2"},
    "111-84-2": {"name": "n-nonane",         "hhv_mj_kg": 47.91, "lhv_mj_kg": 44.69, "mw_g_mol": 128.259, "source": "GPSA_23-2"},
    "124-18-5": {"name": "n-decane",         "hhv_mj_kg": 47.79, "lhv_mj_kg": 44.62, "mw_g_mol": 142.286, "source": "GPSA_23-2"},
    "287-92-3": {"name": "cyclopentane",     "hhv_mj_kg": 48.51, "lhv_mj_kg": 45.01, "mw_g_mol": 70.135,  "source": "GPSA_23-2"},
    "110-82-7": {"name": "cyclohexane",      "hhv_mj_kg": 48.24, "lhv_mj_kg": 44.85, "mw_g_mol": 84.162,  "source": "GPSA_23-2"},
    "96-37-7":  {"name": "methylcyclopentane","hhv_mj_kg": 48.05, "lhv_mj_kg": 44.64, "mw_g_mol": 84.162, "source": "GPSA_23-2"},
    "108-87-2": {"name": "methylcyclohexane","hhv_mj_kg": 47.78, "lhv_mj_kg": 44.46, "mw_g_mol": 98.190,  "source": "GPSA_23-2"},
    "74-85-1":  {"name": "ethylene",         "hhv_mj_kg": 50.32, "lhv_mj_kg": 47.16, "mw_g_mol": 28.054,  "source": "GPSA_23-2"},
    "115-07-1": {"name": "propylene",        "hhv_mj_kg": 48.92, "lhv_mj_kg": 45.95, "mw_g_mol": 42.081,  "source": "GPSA_23-2"},
    "106-98-9": {"name": "1-butene",         "hhv_mj_kg": 48.44, "lhv_mj_kg": 45.32, "mw_g_mol": 56.108,  "source": "GPSA_23-2"},
    "590-18-1": {"name": "cis-2-butene",     "hhv_mj_kg": 47.91, "lhv_mj_kg": 44.79, "mw_g_mol": 56.108,  "source": "GPSA_23-2"},
    "624-64-6": {"name": "trans-2-butene",   "hhv_mj_kg": 47.86, "lhv_mj_kg": 44.74, "mw_g_mol": 56.108,  "source": "GPSA_23-2"},
    "115-11-7": {"name": "isobutene",        "hhv_mj_kg": 48.17, "lhv_mj_kg": 45.04, "mw_g_mol": 56.108,  "source": "GPSA_23-2"},
    "74-86-2":  {"name": "acetylene",        "hhv_mj_kg": 49.91, "lhv_mj_kg": 48.22, "mw_g_mol": 26.038,  "source": "GPSA_23-2"},
    "71-43-2":  {"name": "benzene",          "hhv_mj_kg": 42.41, "lhv_mj_kg": 40.18, "mw_g_mol": 78.114,  "source": "GPSA_23-2"},
    "108-88-3": {"name": "toluene",          "hhv_mj_kg": 42.45, "lhv_mj_kg": 40.52, "mw_g_mol": 92.141,  "source": "GPSA_23-2"},
    "100-41-4": {"name": "ethylbenzene",     "hhv_mj_kg": 43.00, "lhv_mj_kg": 41.16, "mw_g_mol": 106.168, "source": "GPSA_23-2"},
    "95-47-6":  {"name": "o-xylene",         "hhv_mj_kg": 43.40, "lhv_mj_kg": 41.55, "mw_g_mol": 106.168, "source": "GPSA_23-2"},
    "108-38-3": {"name": "m-xylene",         "hhv_mj_kg": 43.35, "lhv_mj_kg": 41.51, "mw_g_mol": 106.168, "source": "GPSA_23-2"},
    "106-42-3": {"name": "p-xylene",         "hhv_mj_kg": 43.31, "lhv_mj_kg": 41.47, "mw_g_mol": 106.168, "source": "GPSA_23-2"},
    "91-20-3":  {"name": "naphthalene",      "hhv_mj_kg": 40.05, "lhv_mj_kg": 38.65, "mw_g_mol": 128.174, "source": "GPSA_23-2"},
    "100-42-5": {"name": "styrene",          "hhv_mj_kg": 43.80, "lhv_mj_kg": 41.85, "mw_g_mol": 104.152, "source": "GPSA_23-2"},
    "67-56-1":  {"name": "methanol",         "hhv_mj_kg": 22.69, "lhv_mj_kg": 19.94, "mw_g_mol": 32.042,  "source": "API_5B6"},
    "64-17-5":  {"name": "ethanol",          "hhv_mj_kg": 29.67, "lhv_mj_kg": 26.90, "mw_g_mol": 46.069,  "source": "API_5B6"},
    "67-63-0":  {"name": "isopropanol",      "hhv_mj_kg": 33.40, "lhv_mj_kg": 30.20, "mw_g_mol": 60.096,  "source": "API_5B6"},
    "71-23-8":  {"name": "n-propanol",       "hhv_mj_kg": 33.60, "lhv_mj_kg": 30.40, "mw_g_mol": 60.096,  "source": "API_5B6"},
    "71-36-3":  {"name": "n-butanol",        "hhv_mj_kg": 36.10, "lhv_mj_kg": 33.00, "mw_g_mol": 74.123,  "source": "API_5B6"},
    "67-64-1":  {"name": "acetone",          "hhv_mj_kg": 31.35, "lhv_mj_kg": 29.10, "mw_g_mol": 58.080,  "source": "API_5B6"},
    "78-93-3":  {"name": "methyl ethyl ketone","hhv_mj_kg": 36.90, "lhv_mj_kg": 33.70, "mw_g_mol": 72.107, "source": "API_5B6"},
    "1634-04-4":{"name": "MTBE",             "hhv_mj_kg": 38.20, "lhv_mj_kg": 35.20, "mw_g_mol": 88.150,  "source": "API_5B6"},
    "115-10-6": {"name": "dimethyl ether",   "hhv_mj_kg": 31.70, "lhv_mj_kg": 28.85, "mw_g_mol": 46.069,  "source": "API_5B6"},
    "50-00-0":  {"name": "formaldehyde",     "hhv_mj_kg": 19.00, "lhv_mj_kg": 17.10, "mw_g_mol": 30.026,  "source": "API_5B6"},
    "75-07-0":  {"name": "acetaldehyde",     "hhv_mj_kg": 26.40, "lhv_mj_kg": 24.40, "mw_g_mol": 44.053,  "source": "API_5B6"},
    "64-19-7":  {"name": "acetic acid",      "hhv_mj_kg": 14.60, "lhv_mj_kg": 13.20, "mw_g_mol": 60.052,  "source": "API_5B6"},
    "74-93-1":  {"name": "methyl mercaptan", "hhv_mj_kg": 25.00, "lhv_mj_kg": 23.20, "mw_g_mol": 48.109,  "source": "API_5B6"},
    "75-08-1":  {"name": "ethyl mercaptan",  "hhv_mj_kg": 31.40, "lhv_mj_kg": 29.80, "mw_g_mol": 62.136,  "source": "API_5B6"},
    "75-18-3":  {"name": "dimethyl sulfide", "hhv_mj_kg": 31.60, "lhv_mj_kg": 29.70, "mw_g_mol": 62.136,  "source": "API_5B6"},
    "75-15-0":  {"name": "carbon disulfide", "hhv_mj_kg": 14.30, "lhv_mj_kg": 14.30, "mw_g_mol": 76.140,  "source": "API_5B6"},
    "463-58-1": {"name": "carbonyl sulfide", "hhv_mj_kg": 11.30, "lhv_mj_kg": 11.30, "mw_g_mol": 60.070,  "source": "API_5B6"},
    "7783-06-4":{"name": "hydrogen sulfide", "hhv_mj_kg": 16.30, "lhv_mj_kg": 15.20, "mw_g_mol": 34.080,  "source": "API_5B6"},
    "1333-74-0":{"name": "hydrogen",         "hhv_mj_kg": 141.80, "lhv_mj_kg": 119.96, "mw_g_mol": 2.016, "source": "GPSA_23-2"},
    "630-08-0": {"name": "carbon monoxide",  "hhv_mj_kg": 10.10, "lhv_mj_kg": 10.10, "mw_g_mol": 28.010,  "source": "GPSA_23-2"},
    "7664-41-7":{"name": "ammonia",          "hhv_mj_kg": 22.50, "lhv_mj_kg": 18.60, "mw_g_mol": 17.031,  "source": "GPSA_23-2"},
    "74-90-8":  {"name": "hydrogen cyanide", "hhv_mj_kg": 22.50, "lhv_mj_kg": 20.30, "mw_g_mol": 27.026,  "source": "GPSA_23-2"},
    "7446-09-5":{"name": "sulfur dioxide",   "hhv_mj_kg": 0.00, "lhv_mj_kg": 0.00, "mw_g_mol": 64.066,    "source": "GPSA_23-2"},
    "7727-37-9":{"name": "nitrogen",         "hhv_mj_kg": 0.00, "lhv_mj_kg": 0.00, "mw_g_mol": 28.014,    "source": "GPSA_23-2"},
    "7782-44-7":{"name": "oxygen",           "hhv_mj_kg": 0.00, "lhv_mj_kg": 0.00, "mw_g_mol": 31.998,    "source": "GPSA_23-2"},
    "7732-18-5":{"name": "water",            "hhv_mj_kg": 0.00, "lhv_mj_kg": 0.00, "mw_g_mol": 18.015,    "source": "GPSA_23-2"},
    "124-38-9": {"name": "carbon dioxide",   "hhv_mj_kg": 0.00, "lhv_mj_kg": 0.00, "mw_g_mol": 44.009,    "source": "GPSA_23-2"},
    "7440-59-7":{"name": "helium",           "hhv_mj_kg": 0.00, "lhv_mj_kg": 0.00, "mw_g_mol": 4.003,     "source": "GPSA_23-2"},
    "7440-37-1":{"name": "argon",            "hhv_mj_kg": 0.00, "lhv_mj_kg": 0.00, "mw_g_mol": 39.948,    "source": "GPSA_23-2"},
    "540-84-1": {"name": "isooctane",        "hhv_mj_kg": 47.78, "lhv_mj_kg": 44.50, "mw_g_mol": 114.232, "source": "GPSA_23-2"},
    "592-41-6": {"name": "1-hexene",         "hhv_mj_kg": 47.95, "lhv_mj_kg": 44.83, "mw_g_mol": 84.162,  "source": "GPSA_23-2"},
    # ---- D11 Mendeleev fallback（ΔHf° 自研派生）----
    "98-82-8":  {"name": "cumene",           "hhv_mj_kg": 43.40, "lhv_mj_kg": 41.55, "mw_g_mol": 120.195, "source": "MENDELEEV_FALLBACK"},
    "108-95-2": {"name": "phenol",           "hhv_mj_kg": 32.50, "lhv_mj_kg": 31.00, "mw_g_mol": 94.113,  "source": "MENDELEEV_FALLBACK"},
}  # noqa: E501 (compact dict table — readability > line-length)

# 模块级 cache（5 min TTL）
_COMPOUND_CACHE: dict[str, dict[str, Any]] | None = None
_COMPOUND_CACHE_TIME: float = 0.0
_COMPOUND_CACHE_TTL: float = 300.0  # 5 minutes


@dataclass(frozen=True)
class HeatingValueResult:
    """气体热值计算结果（GPSA FIG. 23-2 + API 5B6 公式法）。

    业务：

    - ``feed_mw_kg_per_kmol`` 进料分子量（g/mol × 摩尔分数加权）；
    - ``hhv_mj_per_sm3`` HHV / sm³（60°F, 14.696 psia 标准条件）；
    - ``hhv_btu_per_scf`` HHV / SCF（与 sm³ 同基准条件）；
    - ``lhv_mj_per_sm3`` / ``lhv_btu_per_scf`` 同上 LHV 版；
    - ``stoichiometric_air_sm3_per_sm3`` 化学计量空气体积 / 燃料体积；
    - ``flue_gas_sm3_per_sm3`` 完全燃烧烟气体积 / 燃料体积；
    - ``flue_gas_composition`` 烟气体积分数 dict（CO2 / H2O / N2 / SO2 / O2）；
    - ``flue_gas_mw_kg_per_kmol`` 烟气平均分子量；
    - ``formula_ref`` CAS → 数据来源标记（GPSA FIG. 23-2 / API 5B6 / MENDELEEV_FALLBACK）。
    """

    feed_mw_kg_per_kmol: float
    hhv_mj_per_sm3: float
    hhv_btu_per_scf: float
    lhv_mj_per_sm3: float
    lhv_btu_per_scf: float
    stoichiometric_air_sm3_per_sm3: float
    flue_gas_sm3_per_sm3: float
    flue_gas_composition: dict[str, float] = field(default_factory=dict)
    flue_gas_mw_kg_per_kmol: float = 0.0
    formula_ref: dict[str, str] = field(default_factory=dict)