"""P3.2 SIM-21：物性自动补全（spec V1.6 §5.6 + §5.3）。

spec V1.6 §5.6 物性 → 来源/方法映射：
    分子量       | COMMON 库       | -
    临界温度/压力 | COMMON 库/估算  | Joback 基团贡献法（**裁决替代**：chemicals
                               1.5.2 无 group_contribution 模块；改用
                               chemicals.critical.Tc/Pc 默认 HEOS + 备选
                               WEBBOOK/MATTHEWS CSP 方法，标注估算来源
                               ESTIMATED — 用户 2026-09-09 裁决事项）
    偏心因子     | COMMON 库/估算  | Lee-Kesler 关联式（chemicals.acentric.LK_omega）
    标准密度     | COMMON 库/估算  | Rackett 方程（chemicals.volume.Rackett）
    粘度/导热    | CoolProp（CSP） | Gharagheizi 对应态法（chemicals.viscosity
                               /thermal_conductivity）

估算标记：任何字段走估算（COMMON 库未命中或部分命中），estimated_<field>=True；
总览 estimated = 任一字段估算则 True。

PropertyAutoCompleter 接口：
- complete(cas, target_fields=None) -> dict
  返回 dict 含字段值（mw/tc_k/pc_pa/acentric_factor/...）+ estimated 标记
- batch_complete(cases) -> list（顺序与输入一致）
"""
from __future__ import annotations

from typing import Any

from app.services.common_service import CommonService
from app.services.exceptions import PcsError

# 5 类估算方法 → chemicals 函数名（dispatch 用）
# 注：用户 2026-09-09 裁决：Joback 不可用，本环境 chemicals 1.5.2 无
# group_contribution 模块；改用 chemicals 内置 CSP 方法集。
ESTIMATION_SOURCES: dict[str, str] = {
    "critical": "chemicals.critical.{Tc,Pc,Vc} (HEOS/WEBBOOK)",
    "acentric": "chemicals.acentric.LK_omega (Lee-Kesler)",
    "liquid_density": "chemicals.volume.Rackett",
    "viscosity_gas": "chemicals.viscosity.viscosity_gas_Gharagheizi",
    "thermal_conductivity_gas": (
        "chemicals.thermal_conductivity.Gharagheizi_gas"
    ),
}

# common 服务返回的字段名 → COMPLETE 输出统一别名
_FIELD_ALIASES: dict[str, str] = {
    "mw": "mw",
    "tc_k": "tc_k",
    "pc_pa": "pc_pa",
    "tb_k": "tb_k",
    "tm_k": "tm_k",
}


class PropertyAutoCompleter:
    """物性自动补全（无状态；可作单例）。

    流程：
    1. 先查 COMMON 库（CommonService.get_material）——已知值直接采纳
    2. COMMON 库未命中字段走估算（对应 ESTIMATION_SOURCES 方法）
    3. 任一字段估算 → 该字段 estimated_<field>=True，total estimated=True
    """

    # COMMON 库可提供的核心物性集（命中即不估算）
    _COMMON_FIELDS: frozenset[str] = frozenset(
        {"mw", "tc_k", "pc_pa", "tb_k", "tm_k"}
    )

    # 估算可提供的扩展物性集（COMMON 库不提供）
    _ESTIMATABLE_FIELDS: frozenset[str] = frozenset(
        {
            "acentric_factor",  # Lee-Kesler
            "liquid_density",   # Rackett @ Tb
            "viscosity_gas",    # Gharagheizi
            "thermal_conductivity_gas",  # Gharagheizi
            # critical (Tc/Pc/Vc) 走估算时也走 chemicals.critical
        }
    )

    def complete(
        self, cas: str, *, target_fields: set[str] | None = None
    ) -> dict[str, Any]:
        """补全物性。返回 dict 含字段值 + estimated 标记。

        target_fields 为 None 时返回全集；为 set 时仅返回指定字段
        （未指定字段直接省略，不影响 estimated 总览）。
        """
        cas = (cas or "").strip()
        if not cas:
            return {}

        # 1) COMMON 库查询
        common_data: dict[str, Any] = {}
        common_error: bool = False
        try:
            common_data = CommonService.get_material(cas)
        except PcsError:
            common_error = True

        result: dict[str, Any] = {}
        # 标记：字段是否估算（仅对最终输出的字段标记）
        estimated_flags: dict[str, bool] = {}

        # 2) 处理 COMMON 库可提供字段
        target = target_fields or (
            self._COMMON_FIELDS | self._ESTIMATABLE_FIELDS
        )
        for field in target:
            if field in self._COMMON_FIELDS:
                if not common_error:
                    val = common_data.get(field)
                    if val is not None:
                        result[field] = val
                        estimated_flags[field] = False
                        continue
                # COMMON 库缺该字段 → 走估算（critical 字段）
                if field in {"tc_k", "pc_pa"}:
                    val = self._estimate_critical(cas, field)
                    estimated_flags[field] = True  # 即便 None 也标估算
                    if val is not None:
                        result[field] = val
                # 其他 COMMON 字段（mw/tb_k/tm_k）若 COMMON 缺则不补
            elif field == "acentric_factor":
                val = self._estimate_acentric(cas, common_data)
                estimated_flags[field] = True
                if val is not None:
                    result[field] = val
            elif field == "liquid_density":
                val = self._estimate_liquid_density(cas, common_data)
                estimated_flags[field] = True
                if val is not None:
                    result[field] = val
            elif field == "viscosity_gas":
                val = self._estimate_viscosity_gas(cas, common_data)
                estimated_flags[field] = True
                if val is not None:
                    result[field] = val
            elif field == "thermal_conductivity_gas":
                val = self._estimate_thermal_conductivity_gas(cas, common_data)
                estimated_flags[field] = True
                if val is not None:
                    result[field] = val

        # 3) 估算标记
        result["estimated"] = any(estimated_flags.values())
        for f, est in estimated_flags.items():
            result[f"estimated_{f}"] = est
        return result

    # ------------------------------------------------------------------
    # 估算方法
    # ------------------------------------------------------------------

    def _estimate_critical(
        self, cas: str, field: str
    ) -> float | None:
        """chemicals.critical.Tc/Pc/Vc 默认 HEOS + 备选 WEBBOOK。"""
        try:
            from chemicals.critical import Pc, Tc
            if field == "tc_k":
                for method in ("HEOS", "WEBBOOK", "MATTHEWS"):
                    try:
                        val = Tc(cas, method=method)
                        if val is not None:
                            return float(val)
                    except (ValueError, TypeError):
                        continue
            elif field == "pc_pa":
                for method in ("HEOS", "WEBBOOK", "MATTHEWS"):
                    try:
                        val = Pc(cas, method=method)
                        if val is not None:
                            return float(val)
                    except (ValueError, TypeError):
                        continue
            else:
                return None
        except Exception:  # noqa: BLE001
            return None
        return None

    def _estimate_acentric(
        self, cas: str, common: dict[str, Any]
    ) -> float | None:
        """chemicals.acentric.LK_omega（Lee-Kesler 关联式）+ 备选 omega(method='HEOS')。

        LK_omega 需要 Tb/Tc/Pc；Tb 缺失时退到 omega(method='HEOS') 取
        chemicals 数据库直接存的 ω 值（如果有）。
        """
        try:
            from chemicals.acentric import LK_omega, omega
            tc = common.get("tc_k")
            pc = common.get("pc_pa")
            try:
                val = LK_omega(cas, Tc=tc, Pc=pc)
                if val is not None:
                    return float(val)
            except (TypeError, ValueError, ZeroDivisionError):
                pass  # 缺 Tb/Tc 时退到 omega(HEOS)
            # 备选：omega(method='HEOS') 直接取数据库值
            for method in ("HEOS", "PSRK", "YAWS", "PD"):
                try:
                    val = omega(cas, method=method)
                    if val is not None:
                        return float(val)
                except (ValueError, TypeError):
                    continue
        except Exception:  # noqa: BLE001
            return None
        return None

    def _estimate_liquid_density(
        self, cas: str, common: dict[str, Any]
    ) -> float | None:
        """chemicals.volume.Rackett（标准液体密度 @ Tb）。"""
        try:
            from chemicals.volume import Rackett
            tc = common.get("tc_k")
            pc = common.get("pc_pa")
            tb = common.get("tb_k")
            if tc is None or pc is None or tb is None:
                # 缺关键参数无法估算
                return None
            # Zc ≈ 0.27（多数烃类近似）；更精确应查 Zc，spec 没要求
            zc = 0.27
            vs = Rackett(T=float(tb), Tc=float(tc), Pc=float(pc), Zc=zc)
            # vs 单位 m³/mol；密度 = MW / vs (kg/m³)
            mw = common.get("mw")
            if mw is None:
                # COMMON 库未命中分子量，无法换算
                return None
            return float(mw) / float(vs)
        except Exception:  # noqa: BLE001
            return None

    def _estimate_viscosity_gas(
        self, cas: str, common: dict[str, Any]
    ) -> float | None:
        """chemicals.viscosity.viscosity_gas_Gharagheizi @ T=298.15K。

        tc/pc 优先从 COMMON 库取，缺失时走 _estimate_critical。
        """
        try:
            from chemicals.viscosity import viscosity_gas_Gharagheizi
            tc = common.get("tc_k") or self._estimate_critical(cas, "tc_k")
            pc = common.get("pc_pa") or self._estimate_critical(cas, "pc_pa")
            mw = common.get("mw")
            if tc is None or pc is None or mw is None:
                return None
            val = viscosity_gas_Gharagheizi(
                T=298.15, Tc=float(tc), Pc=float(pc), MW=float(mw)
            )
            if val is not None:
                return float(val)
        except Exception:  # noqa: BLE001
            return None
        return None

    def _estimate_thermal_conductivity_gas(
        self, cas: str, common: dict[str, Any]
    ) -> float | None:
        """chemicals.thermal_conductivity.Gharagheizi_gas @ T=298.15K。

        acentric 走 _estimate_acentric（含 HEOS 备选）；tb 缺失时该字段
        产出 None，estimated 标记仍记录。
        """
        try:
            from chemicals.thermal_conductivity import Gharagheizi_gas
            mw = common.get("mw")
            tb = common.get("tb_k")
            pc = common.get("pc_pa") or self._estimate_critical(cas, "pc_pa")
            acentric = self._estimate_acentric(cas, common)
            if mw is None or tb is None or pc is None or acentric is None:
                return None
            val = Gharagheizi_gas(
                T=298.15,
                MW=float(mw),
                Tb=float(tb),
                Pc=float(pc),
                omega=float(acentric),
            )
            if val is not None:
                return float(val)
        except Exception:  # noqa: BLE001
            return None
        return None

    # ------------------------------------------------------------------
    # 批量
    # ------------------------------------------------------------------

    def batch_complete(self, cases: list[str]) -> list[dict[str, Any]]:
        """顺序批量（COMMON 库同步纯函数，亚毫秒；无需 asyncio）。"""
        return [self.complete(c) for c in cases]
