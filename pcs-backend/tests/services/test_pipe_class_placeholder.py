"""占位管级 `CS-STD` 的**单一来源**与**幂等 ensure**（P10-B 评审 #2 · P1）。

## 背景

`piping_results.material_class` 是指向 `pipe_classes.class_id` 的外键 ⇒
链计算写死 `"CS-STD"` ⇒ 该行**必须真的存在** ⇒ 否则真库上插记录撞 FK ⇒ 端点 500
（SQLite 不强制 FK ⇒ 单测照绿 ⇒ 本仓最怕的形状）。

⇒ 人裁决（2026-11-17）：**迁移种子 + lifespan 幂等 ensure**，**删掉请求路径写入**
⇒ ⇒ ① 迁移种一行（配置数据的 canonical 落点）② 启动时幂等兜底
（防「迁移没跑 / 行被删」）③ **计算端点不再写配置表**。

## 断言

- ensure **幂等**（跑两次 ⇒ 只有一行）
- ensure 造出来的行**符合 `PipeClassResponse` 契约**
  （`dn_series_json` 含 `{min,max}` 且是 **int** · `sch_series_json` 是
  **DN→Sch 字符串映射** ⇒ 不符 ⇒ 列表端点整条 500）
- **`source="COMPANY_STD"`**（公司管架列表只列它 ⇒ 不符 ⇒ 下游看不见）
"""
from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_ensure_placeholder_is_idempotent_and_contract_shaped(db_session):
    from app.models.config_domain import PipeClass
    from app.services.pipe_class_service import (
        PLACEHOLDER_MATERIAL_CLASS,
        ensure_placeholder_pipe_class,
    )
    from sqlalchemy import select

    await ensure_placeholder_pipe_class(db_session)
    await ensure_placeholder_pipe_class(db_session)  # 幂等：再跑一次

    rows = (
        (
            await db_session.execute(
                select(PipeClass).where(
                    PipeClass.class_id == PLACEHOLDER_MATERIAL_CLASS
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(rows) == 1, f"占位管级应恰好 1 行，实际 {len(rows)}"
    row = rows[0]

    # ⚠️ **契约形状**（`app/schemas/pipe_class.py::PipeClassBase`）
    mn, mx = row.dn_series_json.get("min"), row.dn_series_json.get("max")
    assert isinstance(mn, int) and isinstance(mx, int), row.dn_series_json
    assert 0 < mn <= mx, row.dn_series_json
    assert row.sch_series_json, "sch_series_json 不能为空"
    assert all(
        isinstance(k, str) and isinstance(v, str)
        for k, v in row.sch_series_json.items()
    ), row.sch_series_json
    assert row.source == "COMPANY_STD", row.source
    assert row.status == "DRAFT", row.status
    assert row.version, "version 不能为空"
