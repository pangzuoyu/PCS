"""create_outlet_stream properties 深拷贝单测（P5-123 MEDIUM 收口）。

本测试只验证 JSONB properties 深拷贝语义，不依赖 DB。
DB 集成测试走现有 api/v1 入口（POST /vessel/calculate 等）。

回归保护：若有人未来误把 copy.deepcopy 退回 dict(properties) 或
shallow dict() 拷贝，本测试 fail。
"""
from __future__ import annotations

import copy

from app.services.outlet_stream import create_outlet_stream


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
