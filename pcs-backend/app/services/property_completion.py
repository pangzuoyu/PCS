"""P3.2 SIM-3：物性补全服务（spec V1.6 §3.3.1）。

调 CommonService.get_material(cas) 补 MW/Tc/Pc/Tb/Tm；
水（7732-18-5）走 IAPWS-IF97 精确值（CommonService 内部已实现）。

- 输入：ParsedStream（frozen dataclass；或任何含 .cas 命名属性的对象）
- 输出：effective 物性 dict {cas, mw, tc_k, pc_pa, tb_k, tm_k, source, warning?}
- 批量：complete_batch 走 asyncio.gather（CommonService 同步纯函数，亚毫秒，
  100 条 ~ 1s 远低于 spec §3.3.1 5s 预算）

下游 SIM-2/SIM-5 解析器 + SIM-7 conflict_resolver 复用本接口。
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Protocol

from app.services.common_service import CommonService
from app.services.exceptions import PcsError


class _StreamLike(Protocol):
    """最小输入契约：含 .cas 命名属性即可（dataclass / dict 属性访问兼容）。"""

    cas: str | None


@dataclass(frozen=True)
class ParsedStream:
    """PRO/II / Excel / 手工导入的中间表示（spec V1.6 §3.2.3）。

    SIM-2 proii_parser / SIM-5 excel_parser / SIM-6 manual entry 都会构造此对象。
    字段命名稳定：下游 complete_properties / conflict_resolver 引用锁定。
    """

    tag: str
    cas: str | None = None
    temperature_k: float | None = None
    pressure_pa: float | None = None
    composition: dict[str, float] | None = None  # CAS → 摩尔分率
    name: str | None = None


def complete_properties(stream: _StreamLike) -> dict[str, Any]:
    """补全单条 stream 物性。失败不抛错（返回 None + warning）。"""
    cas = getattr(stream, "cas", None)
    if not cas or not str(cas).strip():
        return {
            "cas": cas,
            "mw": None,
            "tc_k": None,
            "pc_pa": None,
            "tb_k": None,
            "tm_k": None,
            "source": "MISSING_CAS",
            "warning": "MISSING_CAS",
        }
    try:
        mat = CommonService.get_material(cas)
    except PcsError as e:
        # 404 COMMON_MATERIAL_NOT_FOUND / 422 COMMON_MISSING_CAS / 500 COMMON_GET_FAILED
        if e.code in {"COMMON_MATERIAL_NOT_FOUND", "COMMON_MISSING_CAS"}:
            return {
                "cas": cas,
                "mw": None,
                "tc_k": None,
                "pc_pa": None,
                "tb_k": None,
                "tm_k": None,
                "source": "NOT_FOUND",
                "warning": f"COMMON_MATERIAL_NOT_FOUND: {cas}",
            }
        # 其他 PcsError 仍为系统级错误
        return {
            "cas": cas,
            "mw": None,
            "tc_k": None,
            "pc_pa": None,
            "tb_k": None,
            "tm_k": None,
            "source": "ERROR",
            "warning": f"{e.code}: {e.message}",
        }
    return mat


async def complete_properties_async(stream: _StreamLike) -> dict[str, Any]:
    """async 包装（CommonService 同步纯函数亚毫秒，包装仅为接口统一）。"""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, complete_properties, stream)


async def complete_batch_async(streams: list[_StreamLike]) -> list[dict[str, Any]]:
    """异步并行补全（asyncio.gather + run_in_executor）。"""
    return await asyncio.gather(*[complete_properties_async(s) for s in streams])


def complete_batch(streams: list[_StreamLike]) -> list[dict[str, Any]]:
    """同步批量入口：跑 asyncio event loop 后关闭。

    100 条水（7732-18-5）实测 ~ 0.5s（vs spec 预算 5s）。
    """
    return asyncio.run(complete_batch_async(streams))
