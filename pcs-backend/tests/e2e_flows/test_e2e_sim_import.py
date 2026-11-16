"""E2E-002：PRO/II 导入 → 物流 → 物性补全（P10-B · T3）。

## ⚠️ 端点形状（别写成不存在的那个）

**没有** `POST /api/v1/imports` ⇒ 真路径是

- `POST /api/v1/projects/{project_id}/imports/proii/preview`
  （**multipart/form-data** · 两个字段：`file_inp` + `file_out`）
  ⇒ 响应 `{import_id, preview}`
- `GET  /api/v1/imports/{import_id}/preview-streams` ⇒ 预览出来的物流
- `POST /api/v1/projects/{project_id}/imports/proii/commit`
  （body `{"import_id": ...}`）⇒ 响应 `{committed_count, stream_ids, ...}`

⚠️ **输入用仓内已提交的夹具**：`tests/fixtures/proii/sample1_34comp/`
（`.inp` + `.out` 两个文件 · 34 组分 · CONVERGED）⇒ **不用**根目录 `sample/`
（不入 git ⇒ 别的机器没有 ⇒ 车道不可移植）。
"""
from __future__ import annotations

from pathlib import Path

import pytest

from tests.e2e_flows.helpers import advance_stream_to_checked, flash_body, post_calc

#: PRO/II 夹具（仓内已提交 ⇒ 别的机器也有）。
FIXTURE_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "proii" / "sample1_34comp"
INP_FILE = FIXTURE_DIR / "sample1_34comp.inp"
OUT_FILE = FIXTURE_DIR / "sample1_34comp.out"


@pytest.mark.e2e
async def test_e2e_002_sim_import_creates_streams_and_completes_properties(
    e2e_client, role_headers, e2e_seed
):
    """PRO/II 双文件上传 ⇒ 物流数 > 0 ⇒ commit ⇒ 物流落库 ⇒ 物性补全。"""
    assert INP_FILE.exists(), f"夹具不存在：{INP_FILE}"
    assert OUT_FILE.exists(), f"夹具不存在：{OUT_FILE}"

    headers = role_headers("DESIGNER")
    project_id = str(e2e_seed["project_id"])

    # ① preview（multipart：两个文件字段）
    with INP_FILE.open("rb") as f_inp, OUT_FILE.open("rb") as f_out:
        resp = await e2e_client.post(
            f"/api/v1/projects/{project_id}/imports/proii/preview",
            files={
                "file_inp": (INP_FILE.name, f_inp, "text/plain"),
                "file_out": (OUT_FILE.name, f_out, "text/plain"),
            },
            headers=headers,
        )
    assert resp.status_code in (200, 201), (
        f"PRO/II preview 失败：{resp.status_code} {resp.text[:400]}"
    )
    import_id = resp.json()["import_id"]

    # ② 预览出的物流 > 0
    preview = await e2e_client.get(
        f"/api/v1/imports/{import_id}/preview-streams", headers=headers
    )
    assert preview.status_code == 200, (
        f"preview-streams 失败：{preview.status_code} {preview.text[:300]}"
    )
    preview_body = preview.json()
    rows = preview_body if isinstance(preview_body, list) else preview_body.get("streams", [])
    assert len(rows) > 0, "preview 没解析出物流 ⇒ 解析器没跑通"

    # ③ commit ⇒ 物流真的落库
    committed = await e2e_client.post(
        f"/api/v1/projects/{project_id}/imports/proii/commit",
        json={"import_id": import_id},
        headers=headers,
    )
    assert committed.status_code in (200, 201), (
        f"PRO/II commit 失败：{committed.status_code} {committed.text[:400]}"
    )
    body = committed.json()
    assert body["committed_count"] > 0, f"commit 没提交任何物流：{body}"
    stream_ids = body["stream_ids"]
    assert stream_ids, f"commit 没返回物流 id：{body}"

    # ④ 推进到 CHECKED —— ⚠️ 计算链的入口守卫要求 `CHECKED`
    #    （`app/services/calc_entry.py::check_calc_inputs`）⇒ 不推进就 403
    await advance_stream_to_checked(
        e2e_client, stream_ids[0], role_headers=role_headers
    )

    # ⑤ **物性补全**（PT_FLASH）—— ⚠️ **用种子里那条 CHECKED 且有组成的物流**
    #
    # ⚠️ **为什么不是导入出来的物流**：**PRO/II 解析器不抽组成**
    # （`app/services/import_service.py:135` 明写「SIM-10 MVP 仅 T/P/flow/phase
    # 落库」）⇒ 导入的物流 `composition_json is None`
    # ⇒ flash 计算要求有组成 ⇒ 直接算 ⇒ **422/500**
    # ⇒ ⇒ 「导入」与「物性补全」**分成两段**：导入段断「物流落库 + 能进审批流」，
    # 物性补全段断「有组成的 CHECKED 物流能算出物性」⇒ 两段各自真实可判。
    # ⇒ ⚠️ 「导入的物流进不了计算链」是**产品缺口** ⇒ 已登记（计划偏离 + TODO）。
    result = await post_calc(
        e2e_client,
        "/api/v1/flash/calculate",
        flash_body(stream_id=e2e_seed["stream_ids"][0]),
        headers=headers,
    )
    assert result.get("outlet_stream_id"), (
        f"flash 计算没产出出口物流（编排断了）：{sorted(result)[:12]}"
    )
    assert result.get("record_hash"), "flash 计算没产出记录哈希"
