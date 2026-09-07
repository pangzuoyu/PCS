"""PipeCodeValidator 单元测试（FMT-V01~V09 全部覆盖）。"""
from app.services.pipe_code_validator import (
    PipeCodeValidator,
    Severity,
)


def _seg(t, key="k", **kw):
    base = {"type": t, "key": key, "position": kw.pop("position", 1)}
    base.update(kw)
    return base


def _fmt(segments, separator="-"):
    return {"separator": separator, "segments": segments}


def test_v01_missing_auto_increment_errors():
    fmt = _fmt([
        _seg("stream_symbol", "sym", position=1),
        _seg("enum", "phase", values=["L"], position=2),
    ])
    results = PipeCodeValidator.validate_format_definition(fmt)
    assert any(r.rule_id == "FMT-V01" and r.severity == Severity.ERROR for r in results)


def test_v01_two_auto_increments_errors():
    fmt = _fmt([
        _seg("stream_symbol", "sym", position=1),
        _seg("auto_increment", "seq1", length=3, position=2),
        _seg("auto_increment", "seq2", length=3, position=3),
    ])
    results = PipeCodeValidator.validate_format_definition(fmt)
    matched = [r for r in results if r.rule_id == "FMT-V01"]
    assert matched and matched[0].severity == Severity.ERROR


def test_v02_missing_stream_symbol_errors():
    fmt = _fmt([
        _seg("auto_increment", "seq", length=3, position=1),
        _seg("enum", "phase", values=["L"], position=2),
    ])
    results = PipeCodeValidator.validate_format_definition(fmt)
    assert any(r.rule_id == "FMT-V02" and r.severity == Severity.ERROR for r in results)


def test_v03_duplicate_segment_keys_errors():
    fmt = _fmt([
        _seg("stream_symbol", "sym", position=1),
        _seg("auto_increment", "seq", length=3, position=2),
        _seg("enum", "seq", values=["L"], position=3),
    ])
    results = PipeCodeValidator.validate_format_definition(fmt)
    assert any(r.rule_id == "FMT-V03" and r.severity == Severity.ERROR for r in results)


def test_v04_adjacent_without_separator_errors():
    fmt = _fmt(separator="", segments=[
        _seg("stream_symbol", "sym", position=1),
        _seg("auto_increment", "seq", length=3, position=2),
    ])
    results = PipeCodeValidator.validate_format_definition(fmt)
    assert any(r.rule_id == "FMT-V04" and r.severity == Severity.ERROR for r in results)


def test_v04_delimiter_segment_relaxes_rule():
    fmt = _fmt(separator="", segments=[
        _seg("stream_symbol", "sym", position=1),
        _seg("delimiter", "_d_", separator="-", position=2),
        _seg("auto_increment", "seq", length=3, position=3),
    ])
    results = PipeCodeValidator.validate_format_definition(fmt)
    assert all(r.rule_id != "FMT-V04" for r in results)


def test_v05_overlong_total_length_errors():
    # 60 chars total > 50
    fmt = _fmt(separator="-", segments=[
        _seg("stream_symbol", "sym", length=10, position=1),
        _seg("auto_increment", "seq", length=30, position=2),
        _seg("enum", "phase", values=["L"], length=10, position=3),
    ])
    results = PipeCodeValidator.validate_format_definition(fmt)
    assert any(r.rule_id == "FMT-V05" and r.severity == Severity.ERROR for r in results)


def test_v06_enum_without_values_errors():
    fmt = _fmt([
        _seg("stream_symbol", "sym", position=1),
        _seg("auto_increment", "seq", length=3, position=2),
        _seg("enum", "phase", values=[], position=3),
    ])
    results = PipeCodeValidator.validate_format_definition(fmt)
    assert any(r.rule_id == "FMT-V06" and r.severity == Severity.ERROR for r in results)


def test_v07_stream_symbol_not_in_project_keys():
    fmt = _fmt([
        _seg("stream_symbol", "sym", position=1),
        _seg("auto_increment", "seq", length=3, position=2),
    ])
    results = PipeCodeValidator.validate_format_definition(
        fmt, project_symbol_keys=["OTHER"],
    )
    assert any(r.rule_id == "FMT-V07" and r.severity == Severity.ERROR for r in results)


def test_v08_project_config_name_dup():
    fmt = _fmt([
        _seg("stream_symbol", "sym", position=1),
        _seg("auto_increment", "seq", length=3, position=2),
    ])
    results = PipeCodeValidator.validate_format_definition(
        fmt,
        existing_config_names=["DUP"],
        project_config_name="DUP",
    )
    assert any(r.rule_id == "FMT-V08" and r.severity == Severity.ERROR for r in results)


def test_v09_auto_increment_in_middle_warns():
    fmt = _fmt([
        _seg("stream_symbol", "sym", position=1),
        _seg("auto_increment", "seq", length=3, position=2),
        _seg("enum", "phase", values=["L"], position=3),
        _seg("free_text", "note", position=4),
    ])
    results = PipeCodeValidator.validate_format_definition(fmt)
    matched = [r for r in results if r.rule_id == "FMT-V09"]
    assert matched and matched[0].severity == Severity.WARN


def test_v09_auto_increment_at_end_clean():
    fmt = _fmt([
        _seg("stream_symbol", "sym", position=1),
        _seg("enum", "phase", values=["L"], position=2),
        _seg("auto_increment", "seq", length=3, position=3),
    ])
    results = PipeCodeValidator.validate_format_definition(fmt)
    assert all(r.rule_id != "FMT-V09" for r in results)


def test_clean_format_no_errors():
    fmt = _fmt([
        _seg("stream_symbol", "sym", position=1),
        _seg("enum", "phase", values=["L"], position=2),
        _seg("auto_increment", "seq", length=3, position=3),
    ])
    results = PipeCodeValidator.validate_format_definition(fmt)
    assert not any(r.severity == Severity.ERROR for r in results)


def test_has_errors_helper():
    fmt = _fmt([
        _seg("stream_symbol", "sym", position=1),
    ])
    results = PipeCodeValidator.validate_format_definition(fmt)
    assert PipeCodeValidator.has_errors(results) is True
