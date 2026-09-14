"""P4-3-3 管网 Hardy-Cross 求解落库 helper + 出口物流（pipe_network_results + outlet_stream）。

统一收口（与 P4-1-3 FLASH / P4-2-5 PIPE_CHAIN 对齐）：
1. 写 pipe_network_results 单行（P4-0-2 已建：network_id PK +
   input_json/output_json JSONB + TaggedRecordMixin 全字段；input =
   PipeNetworkInput dataclass 序列化、output = PipeNetworkResult 序列化）。
2. ``finalize_calc_record`` 收口 record_hash + DataLineage
   （ADR-0031，RECORD_TYPE_REGISTRY["PipeNetworkResult"] 已注册）。
3. ``create_outlet_stream`` 复用 P4-1-3 helper（``source_type="PIPE_NET_CALCULATED"``
   → upstream_equipment_type="PIPE_NET"），不重写 outlet 逻辑。
4. 不 commit（事务由调用方控制 — 一个计算批次一个事务）。

design：
- pipe_network_results 模型仅含 network_id PK + input_json/output_json；
  业务字段（节点 / 边 / 流量 / 压力 / 置信度）走 output_json JSONB 直存；
  P4-0-2 SUP-008 11 字段不适用（管网是拓扑 + 求解解；与链式管道不同类）。
- input_json / output_json 全量 dataclass 序列化（UUID → str 跨 DB 引擎安全）。
- record_hash 由 finalize_calc_record 填充（不直写）。
"""
from __future__ import annotations

import dataclasses
import uuid
from collections.abc import Mapping
from typing import Any, Final

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.calc import PipeNetworkResult
from app.models.project import Stream
from app.services.calc_lineage import finalize_calc_record
from app.services.outlet_stream import create_outlet_stream
from app.services.pipe_net.solver_service import PipeNetworkResult as _PNResult
from app.services.pipe_net.topology_service import PipeNetworkInput

# 默认 formula_version（占位标注；与 calc_method 字段独立；本表无 calc_method
# 列，formula_version 仅作 finalize_calc_record 的 change_summary 元数据）
_DEFAULT_FORMULA_VERSION: Final[str] = "Hardy-Cross-v1.0"

# source_type（Stream.source_type 字符串列无 enum；与 P4-1-3 outlet_stream
# Literal 扩展对齐 — 已加 "PIPE_NET_CALCULATED"）
_PIPE_NET_SOURCE_TYPE: Final[str] = "PIPE_NET_CALCULATED"

# calc_type（写 record_hash change_summary + outlet stream_name 后缀）
_PIPE_NET_CALC_TYPE: Final[str] = "PIPE_NET"


def _json_safe(obj: Any) -> Any:
    """递归把 dataclass / UUID 容器转 JSON 安全的 dict / list / str / 标量。

    - UUID → str
    - dataclass → asdict（已嵌套处理）
    - list/tuple → list
    - dict → dict
    - 其他 → 原样

    PostgreSQL JSONB 原生接受 UUID（psycopg 适配），但 in-memory SQLite 测试
    fixture JSONB shim 不接受 UUID 对象；为跨环境一致，强制转 str。
    """
    if isinstance(obj, uuid.UUID):
        return str(obj)
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return _json_safe(dataclasses.asdict(obj))
    if isinstance(obj, Mapping):
        return {k: _json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_json_safe(v) for v in obj]
    return obj


async def persist_pipe_network_result(
    db: AsyncSession,
    inp: PipeNetworkInput,
    result: _PNResult,
    formula_version: str = _DEFAULT_FORMULA_VERSION,
) -> tuple[PipeNetworkResult, Stream]:
    """管网 Hardy-Cross 求解结果落 pipe_network_results + outlet_stream 统一收口。

    写入字段（按 calc.py PipeNetworkResult 实际列名）：
    - network_id: uuid4（PK；default 由 ORM 生成）
    - input_json: PipeNetworkInput dataclass 全量 JSON（UUID → str）
    - output_json: PipeNetworkResult dataclass 全量 JSON（UUID → str）
    - TaggedRecordMixin 字段：project_id / workspace_id / tag_number
      / sign_status=DRAFT / record_hash=""（finalize_calc_record 填充）
      / approval_depth=1 / approval_role=None / locked_by_deliverable=False
    - P4-0-1 审计列（stale_resolution_path / hash_changed / changed_fields）：
      默认空 / False / None（finalize_calc_record 不动）
    - TimestampMixin：created_by=None / created_at=now() / updated_at=None

    Args:
        db: 异步 session（不 commit；提交由调用方控制 — 一个计算批次一个事务）
        inp: PipeNetworkInput dataclass（topology + solver config）
        result: PipeNetworkResult dataclass（solve_network 输出）
        formula_version: 版本标记（占位；写 finalize_calc_record change_summary）

    Returns:
        (PipeNetworkResult, outlet Stream)：已 flush，调用方需 db.commit()

    Raises:
        OutletStreamProjectMismatchError: project_id 与源流 project_id 不一致
            （由 create_outlet_stream 内部 raise；P4-3-3 项目一致性契约）
        StreamNotFoundError: 源流不存在（由 create_outlet_stream 内部 raise）
    """
    # 1. 写 pipe_network_results 单行
    row = PipeNetworkResult(
        input_json=_json_safe(inp),
        output_json=_json_safe(result),
    )
    # TaggedRecordMixin / RecordMixin 字段显式赋值
    row.project_id = inp.project_id
    row.workspace_id = inp.workspace_id
    row.tag_number = inp.tag_number
    row.record_hash = ""  # finalize_calc_record 填充
    db.add(row)
    await db.flush()  # 让 network_id 落库

    # 2. finalize_calc_record 收口 record_hash + DataLineage
    await finalize_calc_record(
        db,
        row,
        source_stream_ids=[inp.source_stream_id],
        formula_version=formula_version,
    )

    # 3. outlet stream（复用 P4-1-3 helper；source_type=PIPE_NET_CALCULATED
    #    → upstream_equipment_type="PIPE_NET"）
    outlet = await create_outlet_stream(
        db,
        source_stream_id=inp.source_stream_id,
        calc_type=_PIPE_NET_CALC_TYPE,
        source_type=_PIPE_NET_SOURCE_TYPE,
        properties={
            "converged": result.converged,
            "iterations": result.iterations,
            "max_flow_error_m3_s": result.max_flow_error_m3_s,
            "edge_count": len(result.edge_flows),
            "node_count": len(result.node_pressures),
            "confidence": result.confidence,
            "check_result": result.check_result,
            "check_result_reason": result.check_result_reason,
            "_calc_type": _PIPE_NET_CALC_TYPE,
            "_tag_number": inp.tag_number,
        },
        project_id=inp.project_id,
        workspace_id=inp.workspace_id,
    )

    return row, outlet


__all__ = ["persist_pipe_network_result"]