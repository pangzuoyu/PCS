"""StreamSymbolValidator 单元测试（SYM-V01~V05）。"""
from app.services.stream_symbol_validator import (
    Severity,
    StreamSymbolValidator,
)


def test_v01_empty_symbol_errors():
    results = StreamSymbolValidator.validate({"symbol": "", "name": "x"})
    assert any(r.rule_id == "SYM-V01" and r.severity == Severity.ERROR for r in results)


def test_v01_overlong_symbol_errors():
    results = StreamSymbolValidator.validate({"symbol": "A" * 11, "name": "x"})
    assert any(r.rule_id == "SYM-V01" and r.severity == Severity.ERROR for r in results)


def test_v02_blank_name_errors():
    results = StreamSymbolValidator.validate({"symbol": "FOO", "name": ""})
    assert any(r.rule_id == "SYM-V02" and r.severity == Severity.ERROR for r in results)


def test_v03_project_dup_symbol_errors():
    results = StreamSymbolValidator.validate(
        {"symbol": "FOO", "name": "x"},
        project_existing_symbols=["FOO"],
    )
    assert any(r.rule_id == "SYM-V03" and r.severity == Severity.ERROR for r in results)


def test_v03_not_invoked_when_project_existing_is_none():
    results = StreamSymbolValidator.validate({"symbol": "FOO", "name": "x"})
    assert all(r.rule_id != "SYM-V03" for r in results)


def test_v04_unknown_category_warns():
    results = StreamSymbolValidator.validate(
        {"symbol": "FOO", "name": "x", "category": "MYSTERY"},
    )
    matched = [r for r in results if r.rule_id == "SYM-V04"]
    assert matched and matched[0].severity == Severity.WARN


def test_v04_known_category_clean():
    results = StreamSymbolValidator.validate(
        {"symbol": "FOO", "name": "x", "category": "PROCESS"},
    )
    assert all(r.rule_id != "SYM-V04" for r in results)


def test_v05_missing_snapshot_errors():
    result = StreamSymbolValidator.validate_fork_snapshot(None)
    assert result is not None
    assert result.rule_id == "SYM-V05"
    assert result.severity == Severity.ERROR


def test_v05_partial_snapshot_errors():
    result = StreamSymbolValidator.validate_fork_snapshot({"symbol": "X"})
    assert result is not None
    assert result.rule_id == "SYM-V05"


def test_v05_complete_snapshot_ok():
    assert StreamSymbolValidator.validate_fork_snapshot(
        {"symbol": "X", "name": "Y"}
    ) is None


def test_has_errors():
    results = StreamSymbolValidator.validate({"symbol": "", "name": ""})
    assert StreamSymbolValidator.has_errors(results) is True


def test_has_errors_no_errors():
    results = StreamSymbolValidator.validate(
        {"symbol": "FOO", "name": "x", "category": "PROCESS"},
    )
    assert StreamSymbolValidator.has_errors(results) is False