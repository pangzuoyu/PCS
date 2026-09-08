"""P3.2 SIM-1：Stream / StreamStatePoint Pydantic schema 契约测试。

锁定 Pydantic v2 Schema 签名（spec 本体论 V1.6 §5.3：每字段含中文描述）。
下游 SIM-2..12 直接 import 此模块，签名变更需同步 SIM-3 接口。

覆盖：
- StreamBase 必填字段（stream_name + case_type + data_mode）
- StreamCaseType 4 值（物流级 NORMAL/END_OF_RUN/START_OF_RUN/TURN_DOWN）
- StatePointCaseType 4 值（状态点级 NORMAL/MIN/MAX/ALTERNATE）
- StreamStatePointBase 必填 case_type
- StreamImportPreview / StreamImportResult 含 unreliable_streams 字段
- 中文 Field(description=...) 强制
"""
from __future__ import annotations

import pytest
from pydantic import ValidationError


def test_stream_base_requires_stream_name():
    """stream_name 必填。"""
    from app.schemas.stream import StreamBase

    with pytest.raises(ValidationError):
        StreamBase(
            case_type="NORMAL",
            data_mode="CHEMICAL",
        )  # stream_name 缺


def test_stream_base_requires_data_mode():
    from app.schemas.stream import StreamBase

    with pytest.raises(ValidationError):
        StreamBase(
            stream_name="S-101",
            case_type="NORMAL",
        )  # data_mode 缺


def test_stream_base_accepts_minimal_valid():
    from app.schemas.stream import StreamBase, StreamCaseType

    s = StreamBase(
        stream_name="S-101",
        case_type=StreamCaseType.NORMAL,
        data_mode="CHEMICAL",
        source_type="MANUAL_ENTRY",  # source_type 必填
    )
    assert s.stream_name == "S-101"
    assert s.case_type == StreamCaseType.NORMAL
    assert s.data_mode == "CHEMICAL"
    assert s.source_type == "MANUAL_ENTRY"


def test_stream_case_type_enum_values():
    from app.schemas.stream import StreamCaseType

    assert {e.value for e in StreamCaseType} == {
        "NORMAL",
        "END_OF_RUN",
        "START_OF_RUN",
        "TURN_DOWN",
    }


def test_state_point_case_type_enum_values():
    from app.schemas.stream import StatePointCaseType

    assert {e.value for e in StatePointCaseType} == {
        "NORMAL",
        "MIN",
        "MAX",
        "ALTERNATE",
    }


def test_stream_state_point_base_requires_case_type():
    from app.schemas.stream import StreamStatePointBase

    with pytest.raises(ValidationError):
        StreamStatePointBase(
            state_label="设计工况",
        )  # case_type 缺


def test_stream_state_point_base_accepts_minimal_valid():
    from app.schemas.stream import StatePointCaseType, StreamStatePointBase

    sp = StreamStatePointBase(
        state_label="设计工况",
        case_type=StatePointCaseType.NORMAL,
        temp=50.0,
        press=1000.0,
        phase="LIQUID",
        mass_flow=1000.0,
        composition_json={"7732-18-5": 1.0},
        source_type="MANUAL_ENTRY",
    )
    assert sp.case_type == StatePointCaseType.NORMAL
    assert sp.temp == 50.0
    assert sp.composition_json == {"7732-18-5": 1.0}


def test_stream_import_preview_has_unreliable_streams():
    from app.schemas.stream import StreamImportPreview

    p = StreamImportPreview(
        convergence_status="NOT_CONVERGED",
        unreliable_stream_names=["S-201", "S-202"],
        preview_streams=[],
    )
    assert p.convergence_status == "NOT_CONVERGED"
    assert "S-201" in p.unreliable_stream_names


def test_stream_import_result_has_committed_count():
    from app.schemas.stream import StreamImportResult

    r = StreamImportResult(
        committed_count=10,
        unreliable_count=2,
        skipped_count=0,
    )
    assert r.committed_count == 10
    assert r.unreliable_count == 2


def test_stream_base_has_chinese_field_descriptions():
    """spec V1.6 §5.3：每字段必含中文 Field(description=...)。"""
    from app.schemas.stream import StreamBase

    for name, field in StreamBase.model_fields.items():
        assert field.description, (
            f"StreamBase.{name} 缺中文 description（spec V1.6 §5.3 强制）"
        )
        # 简单断言含中文字符
        assert any("一" <= c <= "鿿" for c in field.description), (
            f"StreamBase.{name} description 非中文: {field.description!r}"
        )


def test_stream_state_point_base_has_chinese_field_descriptions():
    """spec V1.6 §5.3：状态点 Schema 字段描述必含中文。"""
    from app.schemas.stream import StreamStatePointBase

    for name, field in StreamStatePointBase.model_fields.items():
        assert field.description, (
            f"StreamStatePointBase.{name} 缺中文 description"
        )
        assert any("一" <= c <= "鿿" for c in field.description), (
            f"StreamStatePointBase.{name} description 非中文: {field.description!r}"
        )
