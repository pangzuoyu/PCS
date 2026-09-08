"""P3.2 SIM-7：三级冲突检测服务（spec V1.6 §3.4）。

用户 2026-09-08 完整设计：
- 冲突三级：BLOCK（阻止保存）/ WARN（写入 + 警告 sim_import_warnings）/
  INFO（写入 + 信息日志）
- 4 大检测维度：
  * SIM-V01~V10 结构完整性（phase=组成一致性、流量-物性一致性等）
  * SIM-E01~E04 工程一致性（T/P/vf 越界等）
  * PR-V01~V14 PRO/II 结构（零流量、收敛层等，随 SIM-2 扩展）
  * PRX-V01~V08 双文件交叉（.inp/.out 物流对齐，随 SIM-2 扩展）
- 核心接口：Conflict dataclass + ConflictResolver.resolve_batch() → ConflictReport
- 与 SIM-3 衔接：MISSING_CAS→INFO / NOT_FOUND→WARN / ERROR→WARN

本期落地：核心 dataclass + ConflictReport + SIM-V01/V02 + SIM-E01/E02/E03
+ SIM-3 错误码转译。PR-* / PRX-* 规则随 SIM-2 推进时扩展。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Protocol

from app.services.property_completion import (
    VALID_STATE_POINT_CASE_TYPES,
    ParsedStatePoint,
    ParsedStream,
    complete_properties,
)


class ConflictLevel(str, Enum):
    """冲突三级。"""

    BLOCK = "BLOCK"
    WARN = "WARN"
    INFO = "INFO"


@dataclass(frozen=True)
class Conflict:
    """单条冲突。code 前缀：SIM-V / SIM-E / PR-V / PRX-V。"""

    level: ConflictLevel
    code: str
    message: str
    stream_name: str | None = None
    unit_id: str | None = None
    field: str | None = None


@dataclass
class ConflictReport:
    """冲突报告：分三级聚合 + 统计。"""

    blocks: list[Conflict] = field(default_factory=list)
    warnings: list[Conflict] = field(default_factory=list)
    infos: list[Conflict] = field(default_factory=list)
    stats: dict[str, int] = field(default_factory=dict)

    def __post_init__(self) -> None:
        # 自动统计（避免调用方手工维护）
        self.stats = {
            "BLOCK": len(self.blocks),
            "WARN": len(self.warnings),
            "INFO": len(self.infos),
            "TOTAL": len(self.blocks) + len(self.warnings) + len(self.infos),
        }

    @property
    def has_blocks(self) -> bool:
        return bool(self.blocks)

    @property
    def has_warnings(self) -> bool:
        return bool(self.warnings)

    def add(self, c: Conflict) -> None:
        if c.level == ConflictLevel.BLOCK:
            self.blocks.append(c)
        elif c.level == ConflictLevel.WARN:
            self.warnings.append(c)
        else:
            self.infos.append(c)
        # 维护 stats
        self.stats[c.level.value] += 1
        self.stats["TOTAL"] += 1


class _StreamLike(Protocol):
    """最小输入契约：含 .cas + .tag 命名属性即可。"""

    cas: str | None
    tag: str


class ConflictResolver:
    """三级冲突检测引擎。无状态（class 直接用，无需注入）。"""

    # 摩尔-质量流量一致容差（spec 暂定 1%，可后续校核）
    _MOLAR_MASS_TOL = 0.01

    def resolve_batch(
        self,
        streams: list[ParsedStream],
        *,
        block_on_error: bool = True,
    ) -> ConflictReport:
        """批量检测，返回分级报告。

        block_on_error 仅控制是否抛错（默认 True：发现 BLOCK 立即 raise，
        供 SIM-10 导入预览用；False：caller 自己看 has_blocks 决策）。
        """
        report = ConflictReport()
        for s in streams:
            self._check_stream(s, report)
            if block_on_error and report.has_blocks:
                # 不抛错但 break——caller 一次性看完整 BLOCK 列表
                continue
        return report

    def resolve_state_points(
        self,
        state_points: list[ParsedStatePoint],
        *,
        parent_streams: list[str],
        block_on_error: bool = True,
    ) -> ConflictReport:
        """状态点级冲突检测（spec V1.6 §3.2.2 + §3.4）。

        parent_streams 是已落库 stream_name 列表（供 SIM-SV04 孤儿检测）。
        """
        report = ConflictReport()
        seen_keys: set[tuple[str, str]] = set()
        for sp in state_points:
            self._check_state_point(sp, parent_streams, seen_keys, report)
            if block_on_error and report.has_blocks:
                continue
        return report

    # -----------------------------------------------------------------
    # 单 stream 规则
    # -----------------------------------------------------------------

    def _check_stream(self, s: ParsedStream, report: ConflictReport) -> None:
        # 1. SIM-3 物性补全错误码转译（先做，以便后续规则复用 effective MW）
        eff = complete_properties(s)
        self._translate_property_status(s, eff, report)

        # 2. SIM-V 结构完整性
        self._check_sim_v01_phase_completeness(s, report)
        self._check_sim_v02_molar_mass_consistency(s, eff, report)

        # 3. SIM-E 工程一致性
        self._check_sim_e01_temperature(s, report)
        self._check_sim_e02_pressure(s, report)
        self._check_sim_e03_vapor_fraction(s, report)

    def _translate_property_status(
        self,
        s: ParsedStream,
        eff: dict[str, Any],
        report: ConflictReport,
    ) -> None:
        """SIM-3 complete_properties 返回 source 转译为冲突。

        映射：MISSING_CAS→INFO / NOT_FOUND→WARN / ERROR→WARN；
        IAPWS-IF97/EXPERIMENTAL/ESTIMATED → 无冲突。
        """
        src = eff.get("source", "")
        if src == "MISSING_CAS":
            report.add(
                Conflict(
                    level=ConflictLevel.INFO,
                    code="SIM-V00",
                    message="缺失 CAS 号，无法补全物性",
                    stream_name=s.tag,
                    field="cas",
                )
            )
        elif src == "NOT_FOUND":
            report.add(
                Conflict(
                    level=ConflictLevel.WARN,
                    code="SIM-V01-NF",
                    message=f"CAS {s.cas} 未命中化学库，估算值可能偏差",
                    stream_name=s.tag,
                    field="cas",
                )
            )
        elif src == "ERROR":
            report.add(
                Conflict(
                    level=ConflictLevel.WARN,
                    code="SIM-V01-ERR",
                    message=f"物性服务异常：{eff.get('warning', 'unknown')}",
                    stream_name=s.tag,
                    field="cas",
                )
            )

    # -----------------------------------------------------------------
    # SIM-V01：MIXED 相必须气/液组成都齐
    # -----------------------------------------------------------------

    def _check_sim_v01_phase_completeness(
        self, s: ParsedStream, report: ConflictReport
    ) -> None:
        if s.phase != "MIXED":
            return
        missing: list[str] = []
        if not s.vapor_composition:
            missing.append("vapor_composition")
        if not s.liquid_composition:
            missing.append("liquid_composition")
        if missing:
            report.add(
                Conflict(
                    level=ConflictLevel.BLOCK,
                    code="SIM-V01",
                    message=f"MIXED 相缺 {','.join(missing)}，两相流必填",
                    stream_name=s.tag,
                    field="phase",
                )
            )

    # -----------------------------------------------------------------
    # SIM-V02：摩尔-质量流量一致性（molar × MW ≈ mass）
    # -----------------------------------------------------------------

    def _check_sim_v02_molar_mass_consistency(
        self,
        s: ParsedStream,
        eff: dict[str, Any],
        report: ConflictReport,
    ) -> None:
        # 缺数据不算冲突（信息缺失归 INFO，由 SIM-3 翻译处理）
        if s.molar_flow_kmol_h is None or s.mass_flow_kg_h is None:
            return
        # MW 优先用 stream 自带，否则用 effective 补全值
        mw = s.molecular_weight
        if mw is None:
            mw = eff.get("mw")
        if mw is None or mw <= 0:
            return  # 无 MW 可对账，跳过
        expected = s.molar_flow_kmol_h * mw
        if expected == 0:
            return
        rel_err = abs(s.mass_flow_kg_h - expected) / abs(expected)
        if rel_err > self._MOLAR_MASS_TOL:
            report.add(
                Conflict(
                    level=ConflictLevel.BLOCK,
                    code="SIM-V02",
                    message=(
                        f"质量流量 {s.mass_flow_kg_h} kg/h 与 "
                        f"摩尔流量 {s.molar_flow_kmol_h} kmol/h × MW {mw} "
                        f"= {expected:.2f} kg/h 不一致（偏差 {rel_err:.1%}）"
                    ),
                    stream_name=s.tag,
                    field="mass_flow_kg_h",
                )
            )

    # -----------------------------------------------------------------
    # SIM-E01：温度越界（T < 0 K 或 T > 1000 K 工程外推上限）
    # -----------------------------------------------------------------

    def _check_sim_e01_temperature(
        self, s: ParsedStream, report: ConflictReport
    ) -> None:
        t = s.temperature_k
        if t is None:
            return
        if t < 0 or t > 1000:
            report.add(
                Conflict(
                    level=ConflictLevel.BLOCK,
                    code="SIM-E01",
                    message=f"温度 {t} K 越界（有效 0~1000 K）",
                    stream_name=s.tag,
                    field="temperature_k",
                )
            )

    # -----------------------------------------------------------------
    # SIM-E02：压力非正
    # -----------------------------------------------------------------

    def _check_sim_e02_pressure(
        self, s: ParsedStream, report: ConflictReport
    ) -> None:
        p = s.pressure_pa
        if p is None:
            return
        if p <= 0:
            report.add(
                Conflict(
                    level=ConflictLevel.BLOCK,
                    code="SIM-E02",
                    message=f"压力 {p} Pa 非正",
                    stream_name=s.tag,
                    field="pressure_pa",
                )
            )

    # -----------------------------------------------------------------
    # SIM-E03：气相分率越界（[0, 1]）
    # -----------------------------------------------------------------

    def _check_sim_e03_vapor_fraction(
        self, s: ParsedStream, report: ConflictReport
    ) -> None:
        vf = s.vapor_fraction
        if vf is None:
            return
        if vf < 0 or vf > 1:
            report.add(
                Conflict(
                    level=ConflictLevel.BLOCK,
                    code="SIM-E03",
                    message=f"气相分率 {vf} 越界（有效 [0, 1]）",
                    stream_name=s.tag,
                    field="vapor_fraction",
                )
            )

    # -----------------------------------------------------------------
    # 状态点规则：SIM-SV01~SV05
    # -----------------------------------------------------------------

    def _check_state_point(
        self,
        sp: ParsedStatePoint,
        parent_streams: list[str],
        seen_keys: set[tuple[str, str]],
        report: ConflictReport,
    ) -> None:
        self._check_sim_sv01_case_type(sp, report)
        self._check_sim_sv02_required_fields(sp, report)
        self._check_sim_sv03_composition_sum(sp, report)
        self._check_sim_sv04_orphan(sp, parent_streams, report)
        self._check_sim_sv05_unique(sp, seen_keys, report)

    def _check_sim_sv01_case_type(
        self, sp: ParsedStatePoint, report: ConflictReport
    ) -> None:
        if sp.case_type not in VALID_STATE_POINT_CASE_TYPES:
            report.add(
                Conflict(
                    level=ConflictLevel.BLOCK,
                    code="SIM-SV01",
                    message=(
                        f"case_type '{sp.case_type}' 不在 "
                        f"{sorted(VALID_STATE_POINT_CASE_TYPES)} 内"
                    ),
                    stream_name=sp.stream_name,
                    field="case_type",
                )
            )

    def _check_sim_sv02_required_fields(
        self, sp: ParsedStatePoint, report: ConflictReport
    ) -> None:
        missing: list[str] = []
        if sp.temperature_k is None:
            missing.append("temperature_k")
        if sp.pressure_pa is None:
            missing.append("pressure_pa")
        if missing:
            report.add(
                Conflict(
                    level=ConflictLevel.BLOCK,
                    code="SIM-SV02",
                    message=f"状态点缺 {','.join(missing)}（必填）",
                    stream_name=sp.stream_name,
                    field=missing[0],
                )
            )

    # 组成摩尔分率和容差（spec 暂定 0.5%）
    _COMPOSITION_SUM_TOL = 0.005

    def _check_sim_sv03_composition_sum(
        self, sp: ParsedStatePoint, report: ConflictReport
    ) -> None:
        if not sp.composition:
            return
        total = sum(sp.composition.values())
        if abs(total - 1.0) > self._COMPOSITION_SUM_TOL:
            report.add(
                Conflict(
                    level=ConflictLevel.WARN,
                    code="SIM-SV03",
                    message=f"组成摩尔分率和 {total:.4f} 偏离 1.0（容差 ±0.5%）",
                    stream_name=sp.stream_name,
                    field="composition",
                )
            )

    def _check_sim_sv04_orphan(
        self,
        sp: ParsedStatePoint,
        parent_streams: list[str],
        report: ConflictReport,
    ) -> None:
        if sp.stream_name not in parent_streams:
            report.add(
                Conflict(
                    level=ConflictLevel.BLOCK,
                    code="SIM-SV04",
                    message=(
                        f"状态点关联 stream_name='{sp.stream_name}' "
                        f"不在已落库 stream 列表中（孤立）"
                    ),
                    stream_name=sp.stream_name,
                    field="stream_name",
                )
            )

    def _check_sim_sv05_unique(
        self,
        sp: ParsedStatePoint,
        seen_keys: set[tuple[str, str]],
        report: ConflictReport,
    ) -> None:
        key = (sp.stream_name, sp.case_type)
        if key in seen_keys:
            report.add(
                Conflict(
                    level=ConflictLevel.BLOCK,
                    code="SIM-SV05",
                    message=(
                        f"(stream_name='{sp.stream_name}', "
                        f"case_type='{sp.case_type}') 重复（应唯一）"
                    ),
                    stream_name=sp.stream_name,
                    field="case_type",
                )
            )
        else:
            seen_keys.add(key)
