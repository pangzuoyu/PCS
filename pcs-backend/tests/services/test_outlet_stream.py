"""create_outlet_stream properties 深拷贝单测（P5-123 MEDIUM 收口）。

本测试只验证 JSONB properties 深拷贝语义，不依赖 DB。
DB 集成测试走现有 api/v1 入口（POST /vessel/calculate 等）。

回归保护：若有人未来误把 copy.deepcopy 退回 dict(properties) 或
shallow dict() 拷贝，本测试 fail。

A-03 / C-05 LOW 修复（2026-09-24）：
新增 OutletSourceType Literal 字面集合一致性单测（DEVICE_CALCULATED
必须在 Literal；cv_persist.py:185 / restriction_persist.py:186 实测
已落库 DEVICE_CALCULATED；防回归）。
"""
from __future__ import annotations

import copy
from typing import get_args

from app.services.outlet_stream import OutletSourceType, create_outlet_stream


async def test_create_outlet_stream_deep_copies_properties(monkeypatch):
    """properties 含嵌套 dict 时，调用方后续修改嵌套值不影响 DB 持久化值。

    用 monkeypatch 替换 db.flush / db.get / db.add 让 create_outlet_stream 走完逻辑
    不抛错；捕获 Stream 实例断言 stream_properties_json 是深拷贝。
    """
    nested = {"key1": {"nested_key": "original"}, "key2": [1, 2, 3]}
    properties = {"outer": nested, "scalar": 42}

    captured: dict = {}

    class _FakeStream:
        pass

    async def fake_flush():
        pass

    class _FakeDB:
        async def get(self, _model, _id):
            # 返回一个 minimal source 流，project_id 校验通过
            src = _FakeStream()
            src.stream_id = "src-stream-id"
            src.project_id = "proj-1"
            src.stream_name = "S-1"
            src.case_type = "LIQUID"
            src.data_mode = "MEASURED"
            src.composition_json = None
            src.temp = None
            src.press = None
            src.mass_flow = None
            src.molar_flow = None
            return src

        def add(self, outlet):
            """捕获 service 层 add(outlet) 的对象到 captured 字典供断言。"""
            captured["outlet"] = outlet

        async def flush(self):
            captured.setdefault("flushed", True)

    fake_db = _FakeDB()

    await create_outlet_stream(
        fake_db,
        source_stream_id="src-1",
        calc_type="FLASH",
        source_type="FLASH_CALCULATED",
        properties=properties,
        project_id="proj-1",
        workspace_id="ws-1",
    )

    outlet = captured["outlet"]
    persisted = outlet.stream_properties_json

    # 1) 持久化值与原值当前一致
    assert persisted == properties

    # 2) 修改原 properties 嵌套 dict（key1.nested_key）→ 持久化值不变
    nested["key1"]["nested_key"] = "MUTATED"
    assert persisted["outer"]["key1"]["nested_key"] == "original"

    # 3) 修改原 properties 嵌套 list（outer.key2[0]）→ 持久化值不变
    properties["outer"]["key2"][0] = 999
    assert persisted["outer"]["key2"] == [1, 2, 3]

    # 4) 持久化 dict 与原 dict 是不同对象（深拷贝特征）
    assert persisted["outer"] is not properties["outer"]
    assert persisted["outer"]["key1"] is not properties["outer"]["key1"]

    # 5) 防退化：若实现退化为浅拷贝，此断言应 catch
    #    复制 reference 验证非 identity-equal
    fresh = copy.deepcopy(properties)
    fresh["outer"]["key1"]["nested_key"] = "fresh mutation"
    assert persisted["outer"]["key1"]["nested_key"] == "original"


# ---------------------------------------------------------------------------
# A-03 / C-05 LOW 修复：OutletSourceType Literal 字面集合一致性
# ---------------------------------------------------------------------------


def test_outlet_source_type_literal_includes_device_calculated():
    """OutletSourceType Literal 必须包含 'DEVICE_CALCULATED'（C-05 评审 LOW 修复）。

    落库侧 cv_persist.py:185 / restriction_persist.py:186 已用此字面值；
    若未来有人误删 Literal 成员，运行时不报错但 IDE/mypy 会报警，
    此测试保证 Literal 与实际落库口径一致。
    """
    members = get_args(OutletSourceType)
    assert "DEVICE_CALCULATED" in members, (
        f"OutletSourceType Literal 必须含 DEVICE_CALCULATED，实际 {members}"
    )


def test_outlet_source_type_literal_total_count():
    """P6-1 期间 Literal 共 9 种 CALCULATED 派生；A-03 加 DEVICE_CALCULATED 后 10 种。

    若未来新增 CALCULATED 派生，更新此计数 + 在 Literal + _EQUIP_TYPE_MAP
    同步加条目（A-03 经验：Literal 与落库口径漂移是 LOW 但真实的回归源）。
    """
    members = get_args(OutletSourceType)
    assert len(members) == 10, (
        f"OutletSourceType 应共 10 种（P6-1 9 + DEVICE_CALCULATED），实际 {len(members)}: {members}"
    )


def test_device_calculated_uses_split_fallback_in_equip_type_map():
    """DEVICE_CALCULATED 不进 _EQUIP_TYPE_MAP：split 兜底返 'DEVICE'，与现状一致。

    CV 与 RESTRICTION 都用 source_type='DEVICE_CALCULATED'（仅 change_type 不同）；
    若强行映射 DEVICE_CALCULATED→CV，RESTRICTION 出口流 upstream_equipment_type
    会被误归 "CV"，所以 Literal 已加但 _EQUIP_TYPE_MAP 保持现状。
    """
    from app.services.outlet_stream import _upstream_equipment_type

    # split("_")[0] 兜底返回 "DEVICE"，与未改 _EQUIP_TYPE_MAP 之前一致
    assert _upstream_equipment_type("DEVICE_CALCULATED") == "DEVICE", (
        "DEVICE_CALCULATED 应走 split 兜底返 'DEVICE'，"
        "否则 RESTRICTION 出口流 upstream_equipment_type 会被误归 'CV'"
    )


def test_cv_persist_uses_device_calculated_literally():
    """cv_persist.py:185 用字面 'DEVICE_CALCULATED'，与 OutletSourceType Literal 一致。

    静态校验：直接 import cv_persist 模块并 assert create_outlet_stream 调用处
    的 source_type 字符串在 Literal 成员集合中。防有人未来误改 cv_persist 落库
    字面值与 Literal 漂移。
    """
    import inspect

    import app.services.cv.cv_persist as cv_persist
    import app.services.outlet_stream as outlet_stream_mod

    # outlet_stream 模块级源码应声明 DEVICE_CALCULATED 字面（Literal 成员）
    src_module = inspect.getsource(outlet_stream_mod)
    assert "DEVICE_CALCULATED" in src_module, (
        "outlet_stream 模块源码必须声明 DEVICE_CALCULATED 字面（Literal 成员）"
    )
    # cv_persist.persist_calculate 必须把 source_type='DEVICE_CALCULATED' 传入
    src_persist = inspect.getsource(cv_persist)
    assert 'source_type="DEVICE_CALCULATED"' in src_persist, (
        "cv_persist.py 应以字面 DEVICE_CALCULATED 写入 source_type"
    )
    # 该字面值必须在 Literal 中（与 Literal 漂移即 fail）
    members = get_args(OutletSourceType)
    assert "DEVICE_CALCULATED" in members, (
        f"DEVICE_CALCULATED 落库字面值必须包含在 Literal 中，实际 {members}"
    )
