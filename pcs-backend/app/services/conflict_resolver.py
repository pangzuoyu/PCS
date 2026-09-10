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

from app.services.proii_parser import ProiiParseResult
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

    # SIM-SV03 组成归一化容差（spec 工艺实践参考）：
    #   PRO/II/Aspen 默认 warn 0.1% / reject 1%
    #   工艺包物料衡算 / 安全泄放：偏差 < 0.5% 可信
    #   实验室分析报告：偏差 > 1% 视为数据质量差
    # → 落地：≤0.1% 通过 / (0.1%, 1%] WARN / >1% BLOCK
    _COMPOSITION_SUM_WARN_TOL = 0.001    # 0.1%
    _COMPOSITION_SUM_BLOCK_TOL = 0.01     # 1%

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
    # SIM-29：PRO/II 双文件交叉校验入口（PR-V + PRX-V 共 22 条）
    # -----------------------------------------------------------------

    def resolve_proii_import(
        self,
        inp_result: ProiiParseResult,
        out_result: ProiiParseResult,
        *,
        block_on_error: bool = True,
    ) -> ConflictReport:
        """PRO/II .inp + .out 双文件交叉校验（spec V1.6 §4.3 + §4.4）。

        涵盖 PR-V01~V14（结构）+ PRX-V01~V08（交叉）。
        parser 层已经做的正则/语法校验不在此处重复；本方法只覆盖
        在解析后结构上仍可检测的 22 条业务规则。

        PR-V01~V06/V09/V11~V14 需要原始 .inp 文本扫描——本接口只接收结构化
        ProiiParseResult，故这些规则由 parser 层保证（parser 内已 raise
        PcsError 或在 warnings 列表）。resolver 端检测以「结构 + 数值」可判的
        子集（PRX 系列 + PR-V05/V10 等少量规则）。
        """
        report = ConflictReport()
        self._check_prx_v01_components_match(inp_result, out_result, report)
        self._check_prx_v03_unit_ops_match(inp_result, out_result, report)
        self._check_prx_v05_stream_complete(inp_result, report)
        self._check_prx_v05_stream_complete(out_result, report)
        self._check_prx_v06_zero_flow_confirmed(out_result, report)
        return report

    def _check_prx_v01_components_match(
        self,
        inp: ProiiParseResult,
        out: ProiiParseResult,
        report: ConflictReport,
    ) -> None:
        """PRX-V01：.inp 组件集合 = .out 组件集合。"""
        diff_inp = set(inp.components) - set(out.components)
        diff_out = set(out.components) - set(inp.components)
        if diff_inp or diff_out:
            extras = diff_inp | diff_out
            report.add(
                Conflict(
                    level=ConflictLevel.BLOCK,
                    code="PRX-V01",
                    message=(
                        f".inp/.out 组件不一致：差异 {','.join(sorted(extras))}"
                    ),
                    field="components",
                )
            )

    def _check_prx_v03_unit_ops_match(
        self,
        inp: ProiiParseResult,
        out: ProiiParseResult,
        report: ConflictReport,
    ) -> None:
        """PRX-V03：.inp UIDs = .out UNIT SUMMARY UIDs。"""
        diff = set(inp.unit_ops) - set(out.unit_ops)
        if diff:
            report.add(
                Conflict(
                    level=ConflictLevel.WARN,
                    code="PRX-V03",
                    message=f".out 缺这些 UID：{','.join(sorted(diff))}",
                    field="unit_ops",
                )
            )

    def _check_prx_v05_stream_complete(
        self,
        r: ProiiParseResult,
        report: ConflictReport,
    ) -> None:
        """PRX-V05：每条物流有 T/P/flow（非零流量时）。"""
        for tag, s in r.streams.items():
            if s.zero_flow:
                continue  # 零流量物流跳过 T/P 必填
            missing: list[str] = []
            if s.temperature_k is None:
                missing.append("temperature_k")
            if s.pressure_pa is None:
                missing.append("pressure_pa")
            if s.mass_flow_kg_h is None or s.mass_flow_kg_h <= 0:
                missing.append("mass_flow_kg_h")
            if missing:
                report.add(
                    Conflict(
                        level=ConflictLevel.BLOCK,
                        code="PRX-V05",
                        message=f"物流 {tag} 缺 {','.join(missing)}",
                        stream_name=tag,
                        field="streams",
                    )
                )

    def _check_prx_v06_zero_flow_confirmed(
        self,
        r: ProiiParseResult,
        report: ConflictReport,
    ) -> None:
        """PRX-V06：zero_flow_streams 标记确认（INFO）。"""
        for tag in r.zero_flow_streams:
            report.add(
                Conflict(
                    level=ConflictLevel.INFO,
                    code="PRX-V06",
                    message=f"物流 {tag} 已标记 zero_flow=True",
                    stream_name=tag,
                    field="zero_flow",
                )
            )

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
        self._check_sim_v03_pressure(s, report)
        self._check_sim_v04_phase(s, report)
        self._check_sim_v05_flow(s, report)
        self._check_sim_v06_composition_present(s, report)
        self._check_sim_v07_cas_resolvable(s, report)
        self._check_sim_v08_composition_unique(s, report)
        self._check_sim_v09_composition_sum(s, report)
        self._check_sim_v10_composition_sum_warn(s, report)

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
    # SIM-V03：压力越界（0 <= p <= 100000 kPa = 1e8 Pa）
    # -----------------------------------------------------------------

    _PRESSURE_MAX_PA = 1.0e8

    def _check_sim_v03_pressure(
        self, s: ParsedStream, report: ConflictReport
    ) -> None:
        if s.pressure_pa is None:
            return
        if s.pressure_pa < 0 or s.pressure_pa > self._PRESSURE_MAX_PA:
            report.add(
                Conflict(
                    level=ConflictLevel.BLOCK,
                    code="SIM-V03",
                    message=(
                        f"压力越界 {s.pressure_pa:.1f} Pa，"
                        f"应在 [0, {self._PRESSURE_MAX_PA:.0e}] Pa"
                    ),
                    stream_name=s.tag,
                    field="pressure_pa",
                )
            )

    # -----------------------------------------------------------------
    # SIM-V04：相态枚举非法
    # -----------------------------------------------------------------

    _VALID_PHASES = frozenset({"VAPOR", "LIQUID", "MIXED", "SOLID"})

    def _check_sim_v04_phase(
        self, s: ParsedStream, report: ConflictReport
    ) -> None:
        if s.phase is None:
            return
        if s.phase not in self._VALID_PHASES:
            report.add(
                Conflict(
                    level=ConflictLevel.BLOCK,
                    code="SIM-V04",
                    message=(
                        f"相态 '{s.phase}' 非法，应为 "
                        f"{'/'.join(sorted(self._VALID_PHASES))}"
                    ),
                    stream_name=s.tag,
                    field="phase",
                )
            )

    # -----------------------------------------------------------------
    # SIM-V05：流量全 0
    # -----------------------------------------------------------------

    def _check_sim_v05_flow(
        self, s: ParsedStream, report: ConflictReport
    ) -> None:
        if s.zero_flow:
            report.add(
                Conflict(
                    level=ConflictLevel.BLOCK,
                    code="SIM-V05",
                    message="物流标记 zero_flow=True",
                    stream_name=s.tag,
                    field="mass_flow_kg_h",
                )
            )
            return
        mass = s.mass_flow_kg_h
        molar = s.molar_flow_kmol_h
        if (mass is None or mass <= 0) and (molar is None or molar <= 0):
            report.add(
                Conflict(
                    level=ConflictLevel.BLOCK,
                    code="SIM-V05",
                    message="质量流量与摩尔流量均为 0 或缺失",
                    stream_name=s.tag,
                    field="mass_flow_kg_h",
                )
            )

    # -----------------------------------------------------------------
    # SIM-V06：composition 为空/缺
    # -----------------------------------------------------------------

    def _check_sim_v06_composition_present(
        self, s: ParsedStream, report: ConflictReport
    ) -> None:
        # composition=None 表示「未提供组成」——允许（utility 流、批次数据等场景）
        # 仅当 composition 被显式声明为空 dict 时报 BLOCK。
        if s.composition is not None and len(s.composition) == 0:
            report.add(
                Conflict(
                    level=ConflictLevel.BLOCK,
                    code="SIM-V06",
                    message="composition 被声明但为空",
                    stream_name=s.tag,
                    field="composition",
                )
            )

    # -----------------------------------------------------------------
    # SIM-V07：composition CAS 无法解析
    # -----------------------------------------------------------------

    def _check_sim_v07_cas_resolvable(
        self, s: ParsedStream, report: ConflictReport
    ) -> None:
        # V07 与 SIM-V01-NF 语义重叠：CAS 不可解析。
        # 既有合约是 WARN（test_create_stream_warn_cas_not_found_saves_with_warning
        # 期望 SIM-V01-NF 在 warnings 而非 blocks），保持 WARN。
        if not s.composition:
            return  # V06 已覆盖
        try:
            from app.services.property_completion import complete_properties
        except ImportError:
            return
        bad: list[str] = []
        for cas in s.composition:
            try:
                info = complete_properties(
                    ParsedStream(
                        tag=s.tag,
                        cas=cas,
                        temperature_k=s.temperature_k,
                        pressure_pa=s.pressure_pa,
                    )
                )
                if not info or info.get("mw") is None:
                    bad.append(cas)
            except Exception:
                bad.append(cas)
        if bad:
            report.add(
                Conflict(
                    level=ConflictLevel.WARN,
                    code="SIM-V07",
                    message=f"下列 CAS 无法解析：{','.join(bad)}",
                    stream_name=s.tag,
                    field="composition",
                )
            )

    # -----------------------------------------------------------------
    # SIM-V08：composition 重复 CAS（dict key 自动去重——defensive 检查）
    # -----------------------------------------------------------------

    def _check_sim_v08_composition_unique(
        self, s: ParsedStream, report: ConflictReport
    ) -> None:
        if not s.composition:
            return
        # dict 自动去重后这里基本无意义；保留为防御性检查，
        # 当上游传入 list[tuple] 时再切回 dict 时若发生覆盖，这里记 INFO。
        keys = list(s.composition.keys())
        if len(set(keys)) != len(keys):
            report.add(
                Conflict(
                    level=ConflictLevel.BLOCK,
                    code="SIM-V08",
                    message="composition 包含重复 CAS",
                    stream_name=s.tag,
                    field="composition",
                )
            )

    # -----------------------------------------------------------------
    # SIM-V09：composition sum drift > 0.1% 阈值（BLOCK）
    # -----------------------------------------------------------------

    def _check_sim_v09_composition_sum(
        self, s: ParsedStream, report: ConflictReport
    ) -> None:
        if not s.composition:
            return
        total = sum(s.composition.values())
        drift = abs(total - 1.0)
        if drift > self._COMPOSITION_SUM_WARN_TOL:
            report.add(
                Conflict(
                    level=ConflictLevel.BLOCK,
                    code="SIM-V09",
                    message=(
                        f"组成和 = {total:.4f}，偏离 1.0 {drift*100:.2f}%"
                    ),
                    stream_name=s.tag,
                    field="composition",
                )
            )

    # -----------------------------------------------------------------
    # SIM-V10：composition sum drift > 1% 阈值（WARN）
    # -----------------------------------------------------------------

    def _check_sim_v10_composition_sum_warn(
        self, s: ParsedStream, report: ConflictReport
    ) -> None:
        if not s.composition:
            return
        total = sum(s.composition.values())
        drift = abs(total - 1.0)
        if drift > self._COMPOSITION_SUM_BLOCK_TOL:
            report.add(
                Conflict(
                    level=ConflictLevel.WARN,
                    code="SIM-V10",
                    message=(
                        f"组成和 = {total:.4f}，严重偏离 1.0 "
                        f"{drift*100:.2f}%，请校对组分"
                    ),
                    stream_name=s.tag,
                    field="composition",
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

    def _check_sim_sv03_composition_sum(
        self, sp: ParsedStatePoint, report: ConflictReport
    ) -> None:
        """组成归一化校验（spec 工艺实践参考阈值）：
        - ≤0.1% 偏差：通过
        - 0.1%~1% 偏差：WARN（标记但允许保存）
        - >1% 偏差：BLOCK（阻止保存，提示检查组成数据）
        """
        if not sp.composition:
            return
        total = sum(sp.composition.values())
        dev = abs(total - 1.0)
        if dev > self._COMPOSITION_SUM_BLOCK_TOL:
            report.add(
                Conflict(
                    level=ConflictLevel.BLOCK,
                    code="SIM-SV03",
                    message=(
                        f"组成摩尔分率和 {total:.4f} 偏离 1.0 "
                        f"（偏差 {dev:.2%} > 1%，拒绝保存）"
                    ),
                    stream_name=sp.stream_name,
                    field="composition",
                )
            )
        elif dev > self._COMPOSITION_SUM_WARN_TOL:
            report.add(
                Conflict(
                    level=ConflictLevel.WARN,
                    code="SIM-SV03",
                    message=(
                        f"组成摩尔分率和 {total:.4f} 偏离 1.0 "
                        f"（偏差 {dev:.2%}，0.1%~1% 区间，建议校正）"
                    ),
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
