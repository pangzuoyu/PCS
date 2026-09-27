"""OPEN-P6-6A-1: 饱和水含量 service docstring scope 段 防回归测试。

P6-6A T9 / Ruling 9 总结：``calc_saturation_water_content`` 仅适用于
湿空气（humid air），不适用于天然气 / 烃类气体饱和水含量（Behr 相关式
或 GPSA Fig. 20-XX 系列）。该结论已写入 service docstring 的
**Scope** 段。本测试断言：

1. docstring 含 **Scope** 段标题；
2. 显式声明"仅适用于湿空气"或同义措辞；
3. 显式声明"不适用于天然气 / 烃类"或同义措辞；
4. 引用 Ruling 9 ID（防止漂移到其它 wording）；
5. dry air 基准说明（三档输出单位均为 dry air）。

防止未来有人在重构时静默删除 scope 段（OPEN-P6-6A-1 防回归）。
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest

_SERVICE = Path(__file__).resolve().parents[3] / (
    "app/services/psychro/saturation_water_content_service.py"
)


def _module_docstring(path: Path) -> str:
    """Extract top-level module docstring (PEP 257)."""
    source = path.read_text(encoding="utf-8")
    module = ast.parse(source)
    doc = ast.get_docstring(module)
    if doc is None:
        pytest.fail(f"module {path} has no top-level docstring")
    return doc


class TestScopeDocstring:
    def test_scope_section_present(self) -> None:
        doc = _module_docstring(_SERVICE)
        assert "Scope" in doc, (
            "docstring missing Scope section header "
            "(OPEN-P6-6A-1 wording formalization)"
        )

    def test_documents_humid_air_only(self) -> None:
        """显式声明本 service 仅适用于湿空气。"""
        doc = _module_docstring(_SERVICE)
        assert any(
            phrase in doc
            for phrase in (
                "仅适用于湿空气",
                "仅适用于 湿空气",
                "humid air only",
                "湿空气**（",
            )
        ), "docstring should explicitly state service applies to humid air only"

    def test_documents_natural_gas_out_of_scope(self) -> None:
        """显式声明天然气 / 烃类 OUT OF SCOPE。"""
        doc = _module_docstring(_SERVICE)
        assert any(
            phrase in doc
            for phrase in (
                "天然气 / 烃类",
                "天然气/烃类",
                "不适用于天然气",
                "natural gas",
            )
        ), (
            "docstring should explicitly state natural gas / hydrocarbon is "
            "OUT OF SCOPE (Ruling 9)"
        )

    def test_references_ruling_9(self) -> None:
        """引用 Ruling 9 ID / wording 防漂移。"""
        doc = _module_docstring(_SERVICE)
        assert "Ruling 9" in doc, (
            "docstring should reference Ruling 9 wording "
            "(OPEN-P6-6A-1 / P6-6A T9 mapping defect)"
        )

    def test_documents_dry_air_basis(self) -> None:
        """三档输出单位均为 dry air 基准。"""
        doc = _module_docstring(_SERVICE)
        assert "dry air" in doc.lower() or "干空气" in doc, (
            "docstring should state output units are dry-air basis"
        )


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))