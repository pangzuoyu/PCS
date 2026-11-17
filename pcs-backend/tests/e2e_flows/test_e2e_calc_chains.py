"""E2E-003~006：计算链（管道 / 泵 / 安全阀 / 容器）—— P10-B · T3。

## ⚠️ 这些场景是「薄壳」

E2E 测的是**编排**（端点契约 · 结果落库 · 下游可见），**不是算法**
⇒ 断言落在「**201 + 响应体形状 + 落库行存在 + 下游列表能看到**」，
**不重复**单测里的数值断言（不写「管径 = 57.15 mm」这种）
⇒ 避免两套数值断言漂移，也避免把 E2E 写成第二个单测。

## ⚠️ 源物流必须是 `CHECKED`

`app/services/calc_entry.py::check_calc_inputs` ⇒ 输入物流不是 `CHECKED`
⇒ **403 `STREAM_NOT_CHECKED`** ⇒ 种子的源物流因此是 `CHECKED`。
"""
from __future__ import annotations

import pytest

from tests.e2e_flows.helpers import (
    pipe_chain_body,
    post_calc,
    psv_body,
    pump_chain_body,
    vessel_body,
)


@pytest.mark.e2e
async def test_e2e_003_pipe_calc_chain_populates_the_pipe_class_table(
    e2e_client, role_headers, e2e_seed
):
    """POST /pipe/calc-chain ⇒ 201 ⇒ **计算链不往配置表写行**（#2 裁决）。

    ⚠️ **断言变了**：原先断「管级表**多了一行**」⇒ 那断的正是「**计算端点在
    运行时写配置主表**」这个副作用（#2 · P1）⇒ ⇒ 现在断：
    ① 占位管级 `CS-STD` **已经存在**（由**迁移**种 ⇒ 不是链计算种的）
    ② 链计算之后**管级表行数不变**（⇒ 请求路径不再写配置表）
    """
    headers = role_headers("DESIGNER")

    before = await e2e_client.get("/api/v1/pipe-classes", headers=headers)
    assert before.status_code == 200, f"读管级列表失败：{before.status_code}"
    before_rows = before.json()
    before_count = len(before_rows if isinstance(before_rows, list) else before_rows.get("items", []))

    result = await post_calc(
        e2e_client,
        "/api/v1/pipe/calc-chain",
        pipe_chain_body(
            project_id=e2e_seed["project_id"],
            workspace_id=e2e_seed["workspace_id"],
            source_stream_id=e2e_seed["stream_ids"][0],
            tag_number="E2E-003-PIPE",
        ),
        headers=headers,
    )
    assert result.get("record_hash"), f"管道计算没产出记录哈希：{sorted(result)[:12]}"
    assert result.get("outlet_stream_id"), "管道计算没产出出口物流"

    # ① 占位管级**已经存在**（迁移种的 ⇒ 不是链计算种的）
    before_ids = {
        r.get("class_id")
        for r in (before_rows if isinstance(before_rows, list) else before_rows.get("items", []))
    }
    assert "CS-STD" in before_ids, (
        f"占位管级 CS-STD 不存在（{sorted(before_ids)[:8]}）⇒ 迁移没种它"
    )

    after = await e2e_client.get("/api/v1/pipe-classes", headers=headers)
    after_rows = after.json()
    after_count = len(after_rows if isinstance(after_rows, list) else after_rows.get("items", []))
    # ② **行数不变** ⇒ 计算链**没有**往配置主表写行（#2）
    assert after_count == before_count, (
        f"计算链往配置表写了行（{before_count} → {after_count}）"
        "⇒ 请求路径仍在写配置主表（#2 未修）"
    )


@pytest.mark.e2e
async def test_e2e_004_pump_calc_chain_returns_a_pump_result(
    e2e_client, role_headers, e2e_seed
):
    """POST /pump/calc-chain ⇒ 201 ⇒ 响应里有泵的结果字段。"""
    headers = role_headers("DESIGNER")

    result = await post_calc(
        e2e_client,
        "/api/v1/pump/calc-chain",
        pump_chain_body(
            project_id=e2e_seed["project_id"],
            workspace_id=e2e_seed["workspace_id"],
            source_stream_id=e2e_seed["stream_ids"][0],
            tag_number="E2E-004-PUMP",
        ),
        headers=headers,
    )
    assert result.get("record_hash"), f"泵计算没产出记录哈希：{sorted(result)[:12]}"
    assert result.get("outlet_stream_id"), "泵计算没产出出口物流"


@pytest.mark.e2e
async def test_e2e_005_psv_calculate_returns_the_relief_area(
    e2e_client, role_headers, e2e_seed
):
    """POST /psv/calculate ⇒ 201 ⇒ 响应里有**泄放面积**字段。

    ⚠️ **不断数值**（面积是多少由单测负责）⇒ 只断「**有这个字段**」
    ⇒ 挡的是「字段没了 / 计算链断了」。
    """
    headers = role_headers("DESIGNER")

    result = await post_calc(
        e2e_client,
        "/api/v1/psv/calculate",
        psv_body(source_stream_id=e2e_seed["stream_ids"][0]),
        headers=headers,
    )
    assert result.get("record_hash"), f"安全阀计算没产出记录哈希：{sorted(result)[:12]}"
    # ⚠️ 结果字段在 **`result` 里面**（顶��是 envelope：calc_id / record_hash / …）
    payload = result.get("result") or {}
    area_keys = [k for k in payload if "area" in k.lower()]
    assert area_keys, (
        f"安全阀结果里没有面积字段：{sorted(payload)[:16]}"
    )


@pytest.mark.e2e
async def test_e2e_006_vessel_calculate_returns_dimensions(
    e2e_client, role_headers, e2e_seed
):
    """POST /vessel/calculate ⇒ 201 ⇒ 响应里有**尺寸**字段。"""
    headers = role_headers("DESIGNER")

    result = await post_calc(
        e2e_client,
        "/api/v1/vessel/calculate",
        vessel_body(source_stream_id=e2e_seed["stream_ids"][0]),
        headers=headers,
    )
    assert result.get("record_hash"), f"容器计算没产出记录哈希：{sorted(result)[:12]}"
    # ⚠️ 结果字段在 **`result` 里面**（顶层是 envelope：calc_id / record_hash / …）
    payload = result.get("result") or {}
    # ⚠️ **不断尺寸数值** —— 尺寸要 `sizing_spec`（C-08 **V1.2** 的两相分离器
    # 尺寸，Souders-Brown）⇒ 而那是 **P6-4 的遗留债**（SPEC V1.1 内部不一致 ⇒
    # 计划已停工待 V1.2）⇒ ⇒ 本场景断「**算出了尺寸输入的那套结果**」
    # （`sizing` + `hydraulics` 两块都在），尺寸本身留给那条债。
    for key in ("sizing", "hydraulics"):
        assert key in payload, f"容器结果里没有 {key} 块：{sorted(payload)[:16]}"
    assert payload["sizing"], "容器结果里的 sizing 是空的"
    assert payload["hydraulics"], "容器结果里的 hydraulics 是空的"
