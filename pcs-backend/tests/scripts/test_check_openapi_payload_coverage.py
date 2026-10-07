"""API 载荷结构覆盖率闸的测试.

闸本身见 `scripts/check_openapi_payload_coverage.py`。

**本文件最要紧的是 `test_gate_is_not_vacuous` 那两条** —— 一个恒报 0 的闸
和没有闸一样有害（cerebrum: 「守门恒报噪声 = 狼来了」的反面）。
所以这里显式验证闸**会红**，而不只是验证它现在绿。
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

SCRIPT_PATH = (
    Path(__file__).resolve().parent.parent.parent
    / "scripts"
    / "check_openapi_payload_coverage.py"
)


def _load_module():
    spec = importlib.util.spec_from_file_location(
        "check_openapi_payload_coverage", SCRIPT_PATH
    )
    mod = importlib.util.module_from_spec(spec)
    # 必须先注册进 sys.modules：脚本在 `from __future__ import annotations` 下
    # 用了 @dataclass，dataclasses 解析字符串注解时要回查 sys.modules[cls.__module__]
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_current_repo_is_green():
    """真实仓库跑闸必须绿 —— 否则第一天就会被关掉."""
    mod = _load_module()
    assert mod.main() == 0


def test_bare_count_matches_the_recorded_baseline():
    """裸字段数必须与 BASELINE 一致。

    两者不等说明有人改了 schema 但没同步基线：涨了是倒退（闸会红），
    掉了是修好了（该下调基线并写进提交）。这里把两种情况都暴露出来。
    """
    mod = _load_module()
    r = mod.check()
    assert r.bare_fields <= mod.BASELINE_BARE_FIELDS, (
        f"裸字段 {r.bare_fields} > 基线 {mod.BASELINE_BARE_FIELDS}，闸已经红了"
    )


def test_debt_is_reported_not_hidden():
    """欠账必须被报出来，不能静默通过."""
    mod = _load_module()
    r = mod.check()
    assert r.bare_fields > 0, "预期当前有欠账（§3.4 约束① 未落地）"
    assert r.bare_by_schema, "欠账必须按 schema 聚合，否则无法定位"


def test_gate_goes_red_when_baseline_is_lowered():
    """⚠️ 关键：把基线压到实际值以下，闸必须转红。

    验证「倒退会被拦」是真的，不是恒绿。
    """
    mod = _load_module()
    saved = mod.BASELINE_BARE_FIELDS
    try:
        mod.BASELINE_BARE_FIELDS = mod.check().bare_fields - 1
        assert mod.main() == 1, "基线低于实际值时闸必须阻断"
    finally:
        mod.BASELINE_BARE_FIELDS = saved
        assert mod.main() == 0, "恢复后必须回到绿"


def test_bare_field_would_be_detected():
    """给闸喂一个假的 OpenAPI，验证它真的能识别裸字段。

    只测「基线调低会红」还不够 —— 那可能只是基线比较逻辑在起作用，
    而裸字段的**识别**本身可能是坏的（比如把所有 object 都算成裸）。
    """
    mod = _load_module()
    fake = {
        "Bare": {"properties": {"payload": {"type": "object"}}},
        "Typed": {
            "properties": {
                "payload": {"type": "object", "properties": {"a": {"type": "string"}}},
                "rows": {"type": "array", "items": {"type": "string"}},
            }
        },
        "Scalar": {"properties": {"name": {"type": "string"}, "n": {"type": "integer"}}},
    }
    names = [f"{schema}.{fname}"
             for schema, s in fake.items()
             for fname, p in s["properties"].items()
             if mod._is_bare(p)]
    assert names == ["Bare.payload"], names


def test_allof_and_ref_count_as_typed():
    """带 $ref / allOf 的字段是**已定义**的，不能误判成裸.

    Pydantic 生成的嵌套模型走的就是 $ref，误判会让基线虚高。
    """
    mod = _load_module()
    assert not mod._is_bare({"$ref": "#/components/schemas/Foo"})
    assert not mod._is_bare({"allOf": [{"$ref": "#/components/schemas/Foo"}]})
    assert not mod._is_bare({"oneOf": [{"type": "string"}, {"type": "integer"}]})


def test_scalar_fields_are_not_counted():
    """标量字段本就能生成类型，不该进载荷口径."""
    mod = _load_module()
    assert not mod._is_bare({"type": "string"})
    assert not mod._is_bare({"type": "integer"})
    assert not mod._is_bare({"type": "boolean"})
