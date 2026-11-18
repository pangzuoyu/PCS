"""种子管级「按 id 查不 500」（P10-F · 评审 #17）。

## 为什么必须在 **E2E 车道**（真 PG）跑

⚠️ **SQLite 不强制 FK** ⇒ 单测（内存 SQLite）**照样绿** ⇒ 真库才炸 ⇒
这正是「单测照绿、真库会炸」的形状（bug-2166）。

⚠️ **为什么列表端点也要断**：改 `source` 成 `COMPANY_STD` 之后
（`PipeClassService.list_company` 固定过滤 `source == 'COMPANY_STD'`）⇒
**这行会出现在公司管级列表里** ⇒ ⇒ 而列表端点的 `response_model` 是
`list[PipeClassResponse]` ⇒ **一行形状不对 ⇒ 整条列表 500** ⇒
⇒ 把「它在列表里」这个副作用钉死，不留给下一个人猜。

## 事实基础（2026-11-17 核）

- `PipeClassBase.dn_series_json` = `dict[str, int]` = **{"min","max"}**
  （`_check_dn` 还会校验 `0 < min <= max`）·
  `sch_series_json` = `dict[str, str]`（DN→Sch 字符串）·
  `source` = `Literal["COMPANY_STD", "PROJECT"]`。
- 种子原先写的是 `dn_series_json={"DN150": 1.0}` · `sch_series_json={"DN150": 40.0}` ·
  `source="E2E_SEED"` ⇒ 三条**全部**违反契约 ⇒ 按 id 取 ⇒ **500**。
"""
from __future__ import annotations

import pytest

from scripts.seed_e2e_flows import FLOW_PIPE_CLASS_ID


@pytest.mark.e2e
async def test_seed_pipe_class_is_readable_by_id(e2e_client, role_headers):
    """按 id 取种子管级 ⇒ **200** 且形状符合契约。"""
    resp = await e2e_client.get(
        f"/api/v1/pipe-classes/{FLOW_PIPE_CLASS_ID}",
        headers=role_headers("DESIGNER"),
    )
    assert resp.status_code == 200, (
        f"按 id 取种子管级失败：{resp.status_code} {resp.text[:300]}"
    )
    body = resp.json()
    assert body["dn_series_json"] == {"min": 150, "max": 150}, body
    # ⚠️ **SCH 的键是裸 DN 数字**（与 `dn_series_json` 同一口径 · 与 `CS-STD`
    # 占位行同款）⇒ ⇒ 前端 `dnNumeric` 只认裸数字 ⇒ ⇒ `"DN150"` 会排到
    # 数字键之后（P10-F · 整支评审 M1）。
    assert body["sch_series_json"] == {"150": "40"}, body
    assert body["source"] == "COMPANY_STD", body


@pytest.mark.e2e
async def test_seed_pipe_class_appears_in_the_company_list(e2e_client, role_headers):
    """列表端点 **200**，且**这行在里面**（改 `source` 的副作用 ⇒ 钉死）。"""
    resp = await e2e_client.get("/api/v1/pipe-classes", headers=role_headers("DESIGNER"))
    assert resp.status_code == 200, (
        f"列公司管级失败：{resp.status_code} {resp.text[:300]}"
    )
    class_ids = [row["class_id"] for row in resp.json()]
    assert FLOW_PIPE_CLASS_ID in class_ids, (
        f"种子管级不在公司管级列表里 ⇒ `source` 不是 COMPANY_STD？{class_ids}"
    )
