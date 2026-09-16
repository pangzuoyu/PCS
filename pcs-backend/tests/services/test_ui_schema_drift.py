"""uiSchema ↔ Pydantic Schema drift 检测（P45-1-15 / Task 20）。

SPEC §8.5：表单 ↔ Pydantic Schema 静态对比，drift 即 fail。

检查项：
1. uiSchema 字段 widget 必须在 Widget 枚举内
2. uiSchema 字段 path 必须匹配 Pydantic 模型字段名（按 resource 映射）
3. SCHEMA_VERSION 必须符合 semver 字符串
4. uiSchema 与 Pydantic 必填字段一致性（required=true 字段必为 Pydantic 必填）

资源 → Pydantic 模型映射（V1.1 锁定）：
- stream → StreamBase
- workspace → WorkspaceCreate
- record → (record 不映射，Pydantic 端走状态机迁移，不视为表单字段)
- pipe_class → PipeClassBase
- equipment → EquipmentBase
"""
from __future__ import annotations

import pytest
from pydantic import BaseModel

from app.schemas.pipe_class import PipeClassBase
from app.schemas.stream import StreamBase
from app.services.ui_schema_service import (
    SCHEMA_VERSION,
    Widget,
    get_ui_schema,
    list_resources,
)

# === resource → Pydantic 模型 映射 ===
Pydantic_MAP: dict[str, type[BaseModel]] = {
    "stream": StreamBase,
    "pipe_class": PipeClassBase,
    # workspace / equipment 后续 Pydantic 接入后补充（当前后端无对应 BaseModel）
}


def _semver(v: str) -> bool:
    parts = v.split(".")
    if len(parts) != 3:
        return False
    return all(p.isdigit() for p in parts)


def test_schema_version_is_semver() -> None:
    """SCHEMA_VERSION 形如 X.Y.Z 三段整数。"""
    assert _semver(SCHEMA_VERSION), f"非 semver: {SCHEMA_VERSION}"


def test_widget_enum_is_exhaustive() -> None:
    """Widget 枚举至少包含 SPEC §8.3 映射的 9 类控件。"""
    expected = {
        "Input",
        "Select",
        "NumberInput",
        "TextArea",
        "Switch",
        "DatePicker",
        "AutoComplete",
        "Cascader",
        "TagPicker",
    }
    actual = {w.value for w in Widget}
    assert expected.issubset(actual), (
        f"Widget 缺: {expected - actual}"
    )


def test_list_resources_non_empty() -> None:
    """list_resources 返回所有可配置资源。"""
    resources = list_resources()
    assert "stream" in resources
    assert "pipe_class" in resources


@pytest.mark.parametrize("resource", list_resources())
def test_resource_schema_has_version(resource: str) -> None:
    schema = get_ui_schema(resource)
    assert schema["schema_version"] == SCHEMA_VERSION
    assert schema["resource"] == resource
    assert isinstance(schema["fields"], list)
    assert len(schema["fields"]) > 0


@pytest.mark.parametrize("resource", list_resources())
def test_resource_fields_widget_is_valid(resource: str) -> None:
    schema = get_ui_schema(resource)
    valid_widgets = {w.value for w in Widget}
    for f in schema["fields"]:
        assert f["widget"] in valid_widgets, (
            f"{resource}.{f['path']} widget={f['widget']!r} 不在 Widget 枚举内"
        )


@pytest.mark.parametrize("resource", list_resources())
def test_resource_fields_order_is_int(resource: str) -> None:
    schema = get_ui_schema(resource)
    for f in schema["fields"]:
        order = f.get("order", 0)
        assert isinstance(order, int), f"{resource}.{f['path']} order 非整数"


@pytest.mark.parametrize("resource", list_resources())
def test_resource_fields_path_unique(resource: str) -> None:
    """同一 resource 内 path 唯一。"""
    schema = get_ui_schema(resource)
    paths = [f["path"] for f in schema["fields"]]
    assert len(paths) == len(set(paths)), (
        f"{resource} 重复 path: {[p for p in paths if paths.count(p) > 1]}"
    )


@pytest.mark.parametrize("resource", list_resources())
def test_resource_drift_against_pydantic(resource: str) -> None:
    """uiSchema path 必须匹配对应 Pydantic 模型字段名。

    仅对有 Pydantic 映射的资源检查（stream / pipe_class）。其余资源（workspace /
    equipment / record）当前后端无对应 BaseModel，跳过本检查（前置条件：Pydantic
    schema 接入，登记于 P5 待办）。
    """
    if resource not in Pydantic_MAP:
        pytest.skip(f"{resource} 暂未映射 Pydantic BaseModel")

    schema = get_ui_schema(resource)
    model = Pydantic_MAP[resource]
    model_fields = set(model.model_fields.keys())
    schema_paths = {f["path"] for f in schema["fields"]}

    missing = schema_paths - model_fields
    assert not missing, (
        f"{resource} uiSchema 含 Pydantic 未定义的字段: {missing}"
    )
    # extra 字段（模型有但表单未暴露）是允许的（如内部字段 composition_json）
    assert len(schema_paths) >= 1, f"{resource} uiSchema 为空"


def test_stream_required_matches_pydantic() -> None:
    """stream.uiSchema 中 required=true 的字段必须是 Pydantic 必填。"""
    schema = get_ui_schema("stream")
    pydantic_required = {
        name
        for name, field in StreamBase.model_fields.items()
        if field.is_required()
    }
    schema_required = {
        f["path"] for f in schema["fields"] if f.get("required")
    }
    drift = schema_required - pydantic_required
    assert not drift, (
        f"uiSchema 标记 required 但 Pydantic 非必填: {drift}"
    )


def test_pipe_class_required_matches_pydantic() -> None:
    """pipe_class.uiSchema 中 required=true 字段必须是 Pydantic 必填。"""
    schema = get_ui_schema("pipe_class")
    pydantic_required = {
        name
        for name, field in PipeClassBase.model_fields.items()
        if field.is_required()
    }
    schema_required = {
        f["path"] for f in schema["fields"] if f.get("required")
    }
    drift = schema_required - pydantic_required
    assert not drift, (
        f"uiSchema 标记 required 但 Pydantic 非必填: {drift}"
    )