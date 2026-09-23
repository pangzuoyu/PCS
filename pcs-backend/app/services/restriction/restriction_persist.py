"""restriction_persist 限制装置计算结果落库 + 出口物流（P6-1 Task 13 / ADR-0022）。

完整实现 P6 SPEC §3.2.2.1~4 + §3.2.2.6：

- 调 RestrictionEngine.calculate 计算 13 键 payload（SPEC §3.2.2.6）
- 计算 record_hash（数值规范化 → SHA-256 截断 16 hex；复用 calc_lineage）
- 构造 RestrictionResult ORM 实例（v3_1 stub + 13 SPEC §3.2.2.6 字段）+ 落库 restriction_results
- create_outlet_stream 出口物流链（DEVICE_CALCULATED, ISOENTHALPIC, RES-{tag}）

按 ADR-0022 V1.0 出口物流模型：
- source_type='RESTRICTION_CALCULATED'（设备计算结果作为源）
- sign_status='DRAFT'（计算阶段草稿；create_outlet_stream 内 hardcode）
- change_type='ISOENTHALPIC'（限制装置为等熵焓降设备；**区别 CV 的 FRICTION_PRESSURE_DROP**）
- device='RES-{tag_number}'（设备名格式）

不：
- 不调 restriction_api（Task 14 接入 Pydantic RestrictionCalculateRequest）
- 不实现 record_hash 复杂算法（复用 app.services.calc_lineage.compute_record_hash）
- 不写前端类型（Task 15 实施）
"""
from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.calc import RestrictionResult
from app.models.enums import DesignStage
from app.services.calc_lineage import compute_record_hash
from app.services.outlet_stream import create_outlet_stream
from app.services.restriction.restriction_engine import RestrictionEngine

# P6-1 Task 13 formula_version：固定锚点（CIA 引擎版本对齐时一并 bump）
_FORMULA_VERSION = "RESv1.0-p6-1-13"

# v3_1 stub 列 restriction_type 默认值（与 device_type 对齐；向后兼容）
_STUB_RESTRICTION_TYPE_DEFAULT = "ORIFICE"


def _generate_tag_number(project_id: uuid.UUID) -> str:
    """生成项目内唯一 RestrictionResult tag_number（8 hex，无前缀）。

    前缀 RES- 由 outlet.properties.device 字段补全（ADR-0022 设备名格式）。
    project_id 参数保留为接口签名（与 PsvService._generate_tag_number 对齐）。
    """
    return uuid.uuid4().hex[:8].upper()


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
        "device_type": payload["device_type"],
        "fluid_phase": payload.get("fluid_phase", "LIQUID"),
        "design_stage": payload["design_stage"],
    }


def _build_output_json(payload: dict[str, Any]) -> dict:
    """output_json：Restriction 计算结果 + 状态判定（service 层组装，不入 ORM 列）。"""
    return {
        "C_discharge": payload["C_discharge"],
        "beta_ratio": payload["beta_ratio"],
        "epsilon": payload["epsilon"],
        "choked": payload["choked"],
        "flashing": payload["flashing"],
        "delta_omega_pa": payload["delta_omega_pa"],
        "stages": payload["stages"],
    }


class RestrictionService:
    """限制装置计算落库 service（P6-1 Task 13 / ADR-0022）。"""

    @staticmethod
    async def persist_calculate(
        db: AsyncSession,
        *,
        source_stream_id: uuid.UUID,
        request: dict[str, Any],
    ) -> RestrictionResult:
        """调 RestrictionEngine + 落 restriction_results + record_hash + outlet stream。

        流程：
        1. 调 RestrictionEngine.calculate(**engine_kwargs) 返回 13 键 payload
        2. 构造 RestrictionResult ORM 实例（v3_1 stub + 13 SPEC §3.2.2.6 字段）
        3. db.add + db.flush（orifice_id 分配）
        4. record_hash = compute_record_hash(restriction_result)
        5. create_outlet_stream(DEVICE_CALCULATED, ISOENTHALPIC, RES-{tag})
        6. db.commit + 返回 restriction_result

        Args:
            db: 异步 session
            source_stream_id: 源流 UUID（写入 outlet.upstream_stream_id）
            request: dict 含 RestrictionEngine kwargs（device_type/D_pipe_m/d_solved_m/
                     Re_D/P1_pa/dP_pa/rho1/stages） + 必填字段 project_id / workspace_id；
                     tag_number 可选（缺省自生成）

        Returns:
            RestrictionResult ORM 实例（已 commit + refresh）
        """
        # 1. RestrictionEngine.calculate → 13 键 payload
        engine_kwargs = {
            k: v
            for k, v in request.items()
            if k not in ("project_id", "workspace_id", "tag_number")
        }
        payload = RestrictionEngine().calculate(**engine_kwargs)

        # 2. 解析必填上下文字段
        project_id: uuid.UUID = request["project_id"]
        workspace_id: uuid.UUID = request["workspace_id"]
        tag_number: str = request.get("tag_number") or _generate_tag_number(project_id)

        # 3. 构造 RestrictionResult ORM 实例
        restriction_result = RestrictionResult(
            tag_number=tag_number,
            project_id=project_id,
            workspace_id=workspace_id,
            # v3_1 stub 列（向后兼容；不被 restriction_engine 直接写）
            restriction_type=payload.get(
                "device_type", _STUB_RESTRICTION_TYPE_DEFAULT
            ),
            # 13 SPEC §3.2.2.6 字段（按平铺顺序）
            device_type=payload["device_type"],
            D_pipe_m=payload["D_pipe_m"],
            d_solved_m=payload["d_solved_m"],
            beta_ratio=payload["beta_ratio"],
            C_discharge=payload["C_discharge"] if payload["C_discharge"] is not None else 0.0,
            epsilon=payload["epsilon"],
            Re_D=payload["Re_D"],
            delta_P_pa=payload["delta_P_pa"],
            delta_omega_pa=payload["delta_omega_pa"],
            choked=payload["choked"],
            flashing=payload["flashing"],
            stages=payload["stages"],
            design_stage=DesignStage(payload.get("design_stage", "BASIC")),
            # JSONB 容器
            input_json=_build_input_json(request, payload),
            output_json=_build_output_json(payload),
        )
        db.add(restriction_result)
        await db.flush()  # orifice_id 分配 + record_hash 计算前置

        # 4. record_hash（orifice_id 落库后）
        restriction_result.record_hash = compute_record_hash(restriction_result)

        # 5. outlet stream（ADR-0022 DEVICE_CALCULATED + ISOENTHALPIC 区别 CV FRICTION）
        await create_outlet_stream(
            db,
            source_stream_id=source_stream_id,
            calc_type="RESTRICTION",
            source_type="RESTRICTION_CALCULATED",
            properties={
                "device": f"RES-{restriction_result.tag_number}",
                "change_type": "ISOENTHALPIC",
                "fluid_phase": request.get("fluid_phase", "LIQUID"),
                "device_type": payload["device_type"],
                "C_discharge": payload["C_discharge"],
                "beta_ratio": payload["beta_ratio"],
                "epsilon": payload["epsilon"],
                "choked": payload["choked"],
                "flashing": payload["flashing"],
                "delta_omega_pa": payload["delta_omega_pa"],
                "stages": payload["stages"],
                "standard_profile_code": payload.get(
                    "standard_profile_code", "ISO-5167"
                ),
                "design_stage": payload["design_stage"],
            },
            project_id=restriction_result.project_id,
            workspace_id=restriction_result.workspace_id,
        )

        # 6. commit + refresh
        await db.commit()
        await db.refresh(restriction_result)
        return restriction_result


__all__ = ["RestrictionService", "_FORMULA_VERSION", "_generate_tag_number"]