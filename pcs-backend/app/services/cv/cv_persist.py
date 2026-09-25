"""cv_persist 调节阀 Cv 计算结果落库 + 出口物流（P6-1 Task 9 / ADR-0022 / P6-1.5 C-07）。

完整实现 P6 SPEC §3.2.1.6 + §3.2.1.7：

- 调 CvEngine.calculate 计算 21 键 payload（SPEC §3.2.1.1~1.4）
- 计算 record_hash（数值规范化 → SHA-256 截断 16 hex；复用 calc_lineage）
- 构造 CvResult ORM 实例（v3_1 stub + 21 SPEC §3.2.1.6 字段）+ 落库 cv_results
- create_outlet_stream 出口物流链（DEVICE_CALCULATED, FRICTION_PRESSURE_DROP, CV-{tag}）

按 ADR-0022 V1.0 出口物流模型：
- source_type='DEVICE_CALCULATED'（设备计算结果作为源）
- sign_status='DRAFT'（计算阶段草稿；create_outlet_stream 内 hardcode）
- change_type='FRICTION_PRESSURE_DROP'（控制阀为摩擦压降设备；入 properties）
- device='CV-{tag_number}'（设备名格式）

C-07 裁决 2026-09-24：standard_profile_code 透传调用方字段（默认 IEC_60534）。
engine_kwargs 过滤保留 standard_profile_code，仅剔除 project_id/workspace_id/tag_number。

不：
- 不调 cv_api（Task 10 接入 Pydantic CvCalculateRequest）
- 不实现 record_hash 复杂算法（复用 app.services.calc_lineage.compute_record_hash）
- 不写前端类型（Task 11 实施）
"""
from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.calc import CvResult
from app.services.calc_lineage import compute_record_hash
from app.services.cv.cv_engine import CvEngine
from app.services.outlet_stream import create_outlet_stream

# P6-1.5 C-07 公式版本：默认 standard_profile_code 由 API-60534 改为 IEC_60534
# 公式不变；仅溯源字段口径调整（GB/T 4213 等同采用 IEC 60534-2-1:2011）
_FORMULA_VERSION = "CVv1.1-c07-iec-60534"


def _generate_tag_number(project_id: uuid.UUID) -> str:
    """生成项目内唯一 CvResult tag_number（8 hex，无前缀）。

    前缀 CV- 由 outlet.properties.device 字段补全（ADR-0022 设备名格式）。
    project_id 参数保留为接口签名（与 PsvService._generate_tag_number 对齐）。
    """
    return uuid.uuid4().hex[:8].upper()


def _extract_dP_pa(request: dict[str, Any]) -> float:
    """从 request 中提取压差（Pa）：dP_pa 优先，否则 dP_bar * 1e5。

    用于填充 v3_1 stub 列 pressure_drop（NOT NULL Float）。
    """
    if request.get("dP_pa") is not None:
        return float(request["dP_pa"])
    if request.get("dP_bar") is not None:
        return float(request["dP_bar"]) * 1.0e5
    return 0.0


def _build_input_json(request: dict[str, Any], payload: dict[str, Any]) -> dict:
    """input_json：原始请求 + payload 关键字段（不回灌 ORM 列覆盖丢失字段）。

    request 中 UUID/datetime 等非 JSON 原生类型转字符串再序列化，避免 SQLAlchemy
    JSONB 序列化抛 TypeError。
    """
    request_serializable = {
        k: (str(v) if isinstance(v, uuid.UUID) else v)
        for k, v in request.items()
    }
    return {
        "request": request_serializable,
        "fluid_phase": payload["fluid_phase"],
        "valve_type": payload["valve_type"],
        "design_stage": payload["design_stage"],
        "standard_profile_code": payload["standard_profile_code"],
    }


def _build_output_json(payload: dict[str, Any]) -> dict:
    """output_json：Cv 计算结果 + 状态判定 + 闪蒸修正（service 层组装，不入 ORM 列）。

    P6-4 Task 5（C-24 Masonelian fl）：V1.2 D3 严格 —
    fl / flash_steam_rate_kg_s 走 JSONB 容器（cerebrum.md Do-Not-Repeat：
    避免 alembic 单列迁移开销）；masonelian_model 走 ORM 列（独立字段）。
    """
    return {
        "Cv_calculated": payload["Cv_calculated"],
        "Cv_selected": payload["Cv_selected"],
        "choked": payload["choked"],
        "cavitation": payload["cavitation"],
        "flashing": payload["flashing"],
        "noise_sil_db": payload["noise_sil_db"],
        # P6-4 Task 5 C-24 Masonelian fl（V1.2 D3：JSONB 容器透传）
        "fl": payload.get("fl"),
        "flash_steam_rate_kg_s": payload.get("flash_steam_rate_kg_s"),
        "masonelian_model": payload.get("masonelian_model"),
        "standard_profile_code": payload["standard_profile_code"],
    }


class CvService:
    """调节阀 Cv 计算落库 service（P6-1 Task 9 / ADR-0022）。"""

    @staticmethod
    async def persist_calculate(
        db: AsyncSession,
        *,
        source_stream_id: uuid.UUID,
        request: dict[str, Any],
    ) -> CvResult:
        """调 CvEngine + 落 cv_results + record_hash + outlet stream。

        流程：
        1. 调 CvEngine.calculate(**engine_kwargs) 返回 21 键 payload
        2. 构造 CvResult ORM 实例（v3_1 stub + 21 SPEC 字段）
        3. db.add + db.flush（cv_id 分配）
        4. record_hash = compute_record_hash(cv_result)
        5. create_outlet_stream(DEVICE_CALCULATED, FRICTION_PRESSURE_DROP, CV-{tag})
        6. db.commit + 返回 cv_result

        Args:
            db: 异步 session
            source_stream_id: 源流 UUID（写入 outlet.upstream_stream_id）
            request: dict 含 CvEngine kwargs（fluid_phase/Q_m3h/SG/dP_bar/...）
                     + 必填字段 project_id / workspace_id；tag_number 可选（缺省自生成）

        Returns:
            CvResult ORM 实例（已 commit + refresh）
        """
        # 1. CvEngine.calculate → 21 键 payload
        engine_kwargs = {
            k: v
            for k, v in request.items()
            if k not in ("project_id", "workspace_id", "tag_number")
        }
        payload = CvEngine().calculate(**engine_kwargs)

        # 2. 解析必填上下文字段
        project_id: uuid.UUID = request["project_id"]
        workspace_id: uuid.UUID = request["workspace_id"]
        tag_number: str = request.get("tag_number") or _generate_tag_number(project_id)

        # 3. 构造 CvResult ORM 实例
        # 必填非空字段（如 P1_pa/P2_pa/T1_k/cv_value/flow_rate/pressure_drop）若 None
        # 默认 0.0；用户应在 request 中显式提供（液体/气体最小三件套）。
        cv_result = CvResult(
            tag_number=tag_number,
            project_id=project_id,
            workspace_id=workspace_id,
            # v3_1 stub 列（向后兼容；不被 cv_engine 直接写）
            cv_value=payload["Cv_calculated"],
            flow_rate=payload["Q_m3_per_h"] if payload["Q_m3_per_h"] is not None else 0.0,
            pressure_drop=_extract_dP_pa(request),
            choked_flow=payload["choked"],
            # 21 SPEC §3.2.1.6 字段（按平铺顺序）
            valve_type=payload["valve_type"],
            fluid_phase=payload["fluid_phase"],
            P1_pa=payload["P1_pa"] if payload["P1_pa"] is not None else 0.0,
            P2_pa=payload["P2_pa"] if payload["P2_pa"] is not None else 0.0,
            T1_k=payload["T1_k"] if payload["T1_k"] is not None else 0.0,
            Q_m3_per_h=payload["Q_m3_per_h"],
            rho=payload["rho"],
            SG=payload["SG"],
            FL=payload["FL"],
            xT=payload["xT"],
            gamma=payload["gamma"],
            M=payload["M"],
            Z=payload["Z"],
            Cv_calculated=payload["Cv_calculated"],
            Cv_selected=payload["Cv_selected"],
            choked=payload["choked"],
            cavitation=payload["cavitation"],
            flashing=payload["flashing"],
            noise_sil_db=payload["noise_sil_db"],
            # P6-4 Task 5 C-24 Masonelian 模型口径字段（V1.2 D3：仅 1 列走 ORM）
            masonelian_model=payload.get("masonelian_model"),
            standard_profile_code=payload["standard_profile_code"],
            design_stage=payload["design_stage"],
            # JSONB 容器
            input_json=_build_input_json(request, payload),
            output_json=_build_output_json(payload),
        )
        db.add(cv_result)
        await db.flush()  # cv_id 分配 + record_hash 计算前置

        # 4. record_hash（cv_id 落库后）
        cv_result.record_hash = compute_record_hash(cv_result)

        # 5. outlet stream（ADR-0022 DEVICE_CALCULATED + FRICTION_PRESSURE_DROP）
        await create_outlet_stream(
            db,
            source_stream_id=source_stream_id,
            calc_type="CV",
            source_type="DEVICE_CALCULATED",
            properties={
                "device": f"CV-{cv_result.tag_number}",
                "change_type": "FRICTION_PRESSURE_DROP",
                "fluid_phase": payload["fluid_phase"],
                "Cv_calculated": payload["Cv_calculated"],
                "choked": payload["choked"],
                "cavitation": payload["cavitation"],
                "flashing": payload["flashing"],
                "noise_sil_db": payload["noise_sil_db"],
                # P6-4 Task 5 C-24 Masonelian fl（outlet 流线也透传，便于前端可视化）
                "fl": payload.get("fl"),
                "flash_steam_rate_kg_s": payload.get("flash_steam_rate_kg_s"),
                "masonelian_model": payload.get("masonelian_model"),
                "standard_profile_code": payload["standard_profile_code"],
                "design_stage": payload["design_stage"],
            },
            project_id=cv_result.project_id,
            workspace_id=cv_result.workspace_id,
        )

        # 6. commit + refresh
        await db.commit()
        await db.refresh(cv_result)
        return cv_result


__all__ = ["CvService", "_FORMULA_VERSION", "_generate_tag_number"]