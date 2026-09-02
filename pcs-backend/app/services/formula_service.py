"""FormulaService — 公式 PUBLISH 前置校验（Task 2.8 / D18）。

薄包装：从 ConfigAsset.current_version (字符串列) 查到 ConfigVersion，
抽出 content_json 里的 expression / parameters / unit_tests，调用
FormulaEngine.run_unit_tests，返回 UnitTestResult。

实现注意（与 brief 偏差 / 防御性）：
1. `asset.current_version` 是 String(50) 列（不是关系/对象），需要按
   version_code 显式查 ConfigVersion。
2. `FormulaEngine.run_unit_tests` 期望 `parameters: dict[str, float]`；
   我们从 content_json["parameters_json"]["parameters"] 列表转
   `{name: default}` 字典。
3. unit_tests 也从 content_json["unit_tests_json"]["unit_tests"] 抽 list[dict]。
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.config_domain import ConfigAsset, ConfigVersion
from app.services.formula_engine import FormulaEngine


@dataclass
class UnitTestResult:
    """formula unit_tests 执行结果。"""

    passed: int
    total: int


class FormulaService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def run_unit_tests(self, asset: ConfigAsset) -> UnitTestResult:
        """执行 asset 当前 version 的所有 unit_tests。

        不存在 version 或缺少 expression 时返回 0/0（业务上视为不通过 —
        PUBLISH 端点会比对 passed==total）。
        """
        version = await self._current_version(asset)
        if version is None:
            return UnitTestResult(passed=0, total=0)
        content = version.content_json or {}
        expression = content.get("expression", "")
        parameters_section = content.get("parameters_json") or {}
        unit_tests_section = content.get("unit_tests_json") or {}
        parameters_list = parameters_section.get("parameters") or []
        unit_tests_list = unit_tests_section.get("unit_tests") or []
        # parameters 转 dict {name: default}
        params: dict[str, float] = {}
        for p in parameters_list:
            if not isinstance(p, dict):
                continue
            name = p.get("name")
            if name is None:
                continue
            default = p.get("default", 0.0)
            params[str(name)] = float(default) if default is not None else 0.0
        passed, total = FormulaEngine.run_unit_tests(
            expression=expression,
            parameters=params,
            unit_tests=unit_tests_list,
        )
        return UnitTestResult(passed=passed, total=total)

    async def _current_version(self, asset: ConfigAsset) -> ConfigVersion | None:
        result = await self.session.execute(
            select(ConfigVersion).where(
                ConfigVersion.asset_id == asset.asset_id,
                ConfigVersion.version_code == asset.current_version,
            )
        )
        return result.scalar_one_or_none()


__all__ = ["FormulaService", "UnitTestResult"]