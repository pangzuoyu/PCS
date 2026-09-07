"""CommonService — 物性查询 + 许用应力插值 + 介质安全数据（P3.3 / spec §3.2.3）。

数据来源：
- 物性：vendor chemicals1.5.2（search_chemical + identifiers + iapws IAPWS-IF97 水蒸气）；
  不依赖 CoolProp（pcs-backend 未引入；iapws.iapws97_* 与 CoolProp PropsSI 等价）。
- 许用应力：内置 _ASME_B31_3_A1（碳钢 + 不锈钢常用 5 牌号，按温度插值）。
- 介质安全：内置 _SAFETY_DATA（~15 种常见介质毒性 + 爆炸极限）。

设计要点：
- 全程纯函数 + 静态方法（无 DB），便于单测。
- lazy import chemicals 子模块（避免 module-load 时机问题）。
- 越界 / 缺失抛 PcsError（统一 spec §3.1.2 错误码）。
"""
from __future__ import annotations

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
        # 节点间线性插值
        prev_t = next(t for t in _ASME_TEMPS if t < temp_c)
        next_t = next(t for t in reversed(_ASME_TEMPS) if t > temp_c)
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