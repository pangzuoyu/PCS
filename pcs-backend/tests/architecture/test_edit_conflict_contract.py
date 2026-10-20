"""编辑冲突的 409 契约必须**在 OpenAPI 里**（P9A-5 追加）。

## 为什么单独立一个测试

2026-10-20 实测：6 个 PATCH 端点只声明 `200` / `422` ⇒ 409 的形状**不在
OpenAPI 里**，`ConflictDetail` 也不是 component schema
⇒ 前端 `src/types/api.d.ts` 里**没有任何 `basis`** ⇒ 要按 SPEC §6.21
P9A-LCK-006「按 basis 三值分流」就只能**照 SPEC 的示例手写一份**
⇒ 那正是「同一契约两份清单」，字段一改就静默漂移（前端没有任何东西会红）。

⚠️ **契约缺口的症状与「代码没实现」不一样**：后端 409 **一直是对的**
（`tests/api/v1/test_edit_conflict.py` 8 例覆盖）⇒ 只有**契约产物**缺
⇒ 没有任何既有测试会红 ⇒ 必须专门钉。
"""
from __future__ import annotations

import pytest

#: 6 个有并发基线的 PATCH 端点（与 `edit_guard.TABLE_CAPABILITIES` 一致）。
PATCH_PATHS = [
    "/api/v1/cool-tower/results/{record_id}",
    "/api/v1/cost-est/results/{result_id}",
    "/api/v1/filtration/results/{result_id}",
    "/api/v1/flare/results/{record_id}",
    "/api/v1/open-channel/results/{result_id}",
    "/api/v1/psychro/results/{record_id}",
]


@pytest.fixture(scope="module")
def openapi() -> dict:
    from app.main import app

    return app.openapi()


@pytest.mark.parametrize("path", PATCH_PATHS, ids=lambda p: p.split("/")[3])
def test_patch_declares_its_409_response(openapi: dict, path: str):
    """每个 PATCH 都必须声明 409（否则前端拿不到冲突形状）。"""
    responses = openapi["paths"][path]["patch"]["responses"]
    assert "409" in responses, (
        f"{path} 的 PATCH 没声明 409 ⇒ 前端拿不到冲突形状，只能手写一份"
    )


@pytest.mark.parametrize("path", PATCH_PATHS, ids=lambda p: p.split("/")[3])
def test_patch_409_points_at_the_conflict_envelope(openapi: dict, path: str):
    """409 必须指向 `ConflictEnvelope`，而不是裸 `dict` / `object`。"""
    schema = (
        openapi["paths"][path]["patch"]["responses"]["409"]["content"][
            "application/json"
        ]["schema"]
    )
    assert schema == {"$ref": "#/components/schemas/ConflictEnvelope"}, schema


def test_conflict_detail_basis_is_a_three_value_enum(openapi: dict):
    """`basis` 必须是**三值 enum**（前端按它分流文案与动作）。

    ⚠️ SPEC §6.21 P9A-LCK-006 的分流表就是这三行；生成类型里若没有 enum，
    前端只能写字符串字面量 ⇒ 拼错了没有任何东西会红。
    """
    basis = openapi["components"]["schemas"]["ConflictDetail"]["properties"]["basis"]
    assert basis["enum"] == ["record_hash", "updated_at", "no_baseline"], basis


def test_conflict_envelope_shape_matches_the_repo_error_envelope(openapi: dict):
    """信封必须是 `{code, message, detail, trace_id}`（仓库统一形状）。

    ⚠️ 与 `app/core/errors.py::ErrorResponse` 一致；ADR-0048 §⑦ 原文的
    顶层三字段已按仓库信封归一（bug-2038）。
    """
    props = openapi["components"]["schemas"]["ConflictEnvelope"]["properties"]
    assert set(props) == {"code", "message", "detail", "trace_id"}, set(props)
    # 冲突对象在 detail.conflict（不在顶层）
    detail_ref = props["detail"]["anyOf"][0]["$ref"].split("/")[-1]
    wrapper = openapi["components"]["schemas"][detail_ref]["properties"]
    assert "conflict" in wrapper, wrapper


def test_changed_by_and_changed_at_stay_nullable(openapi: dict):
    """`changed_by` / `changed_at` 必须可空。

    ⚠️ SPEC §6.21 P9A-LCK-006：两者为 null 时**不得**用 `updated_at` 冒充
    （ADR-0048 §⑦）。若把它们声明成必填，生成的 TS 类型会逼前端编一个值出来
    ⇒ 反而制造 SPEC 明令禁止的行为。
    """
    detail = openapi["components"]["schemas"]["ConflictDetail"]["properties"]
    for name in ("changed_by", "changed_at", "current_hash", "your_expected_hash"):
        schema = detail[name]
        nullable = schema.get("type") == "string" or any(
            o.get("type") == "null" for o in schema.get("anyOf", [])
        )
        assert nullable, f"{name} 应可空，实际 {schema}"
