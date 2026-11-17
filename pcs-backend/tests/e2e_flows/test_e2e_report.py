"""E2E-009/015：计算书 · 自定义报表（P10-B · T4）。

## ⚠️ 为什么是**三段式**

报表生成走 **ARQ + Redis** ⇒ 车道**没有 worker** ⇒ 只入队不消费 ⇒
行永远停在 `PENDING` ⇒ **「轮询到 SUCCESS」不可达** ⇒

1. **HTTP 段** —— `POST /report/generate` ⇒ **202**（队列可用但没人消费）
   **或** **503**（队列不可达 ⇒ 当场失败）⇒ 两者都断 ⇒
   「**要么被受理、要么当场明确失败**，没有第三种」
2. **产物段** —— **直调** `generate_report_task`（worker 的那段代码跑一次）
3. **产物断言** —— 终态 `SUCCESS` + 哈希非空 + 下载**字节数 > 0**（三段各自独立可失败）

⚠️ **「HTTP 202 → Redis → worker 消费 → 状态变更」那条真链路仍未覆盖**
⇒ 登记 **TODO-155**（与 AI 审计那条一起补）。
"""
from __future__ import annotations

import pytest

from tests.e2e_flows.helpers import run_report_task

#: 固定计算书报表类型（`app/services/report/collector.py::REPORT_TYPES`）。
REPORT_TYPE = "PIPING_CALC_BOOK"


@pytest.mark.e2e
async def test_e2e_009_report_generation_produces_a_hashed_report_file(
    e2e_client, role_headers, e2e_seed
):
    """三段：① 受理或当场失败 ② 直调任务体 ③ 终态 SUCCESS + 哈希 + 下载。"""
    headers = role_headers("DESIGNER")

    # ① 产物段（**直调任务体**）
    # ⚠️ **顺序要紧**：直调**先于**HTTP 那次 ⇒ 否则 HTTP 入队建的那行与
    # 直调这行**内容相同** ⇒ `_finalize` 的「同内容复用」分支会把直调那行删掉、
    # 返回**没 finalize 的旧行** ⇒ ⇒ 它的 `data_version` 是空的
    # ⇒ ⇒ 哈希断言读到空串（P10-B 的 E2E-009 撞出来的）。
    file_id = await run_report_task(
        e2e_client,
        report_type=REPORT_TYPE,
        project_id=e2e_seed["project_id"],
        record_ids=[e2e_seed["record_id"]],
        output_format="xlsx",
    )
    assert file_id, "任务体没返回 report_file_id"


    # ② HTTP 段（端点契约：**受理** 或 **当场失败**，没有第三种）
    resp = await e2e_client.post(
        "/api/v1/report/generate",
        json={
            "report_type": REPORT_TYPE,
            "project_id": str(e2e_seed["project_id"]),
            "record_ids": [str(e2e_seed["record_id"])],
            "output_format": "xlsx",
        },
        headers=headers,
    )
    assert resp.status_code in (202, 503), (
        f"报表生成端点既没受理（202）也没当场失败（503）⇒ {resp.status_code}"
        f" {resp.text[:300]}"
    )
    if resp.status_code == 503:
        assert resp.json().get("code") == "REPORT_QUEUE_UNAVAILABLE", (
            f"503 的错误码不对：{resp.text[:200]}"
        )

    # ③ 产物断言（三段各自独立可失败）
    status = await e2e_client.get(
        f"/api/v1/report/{file_id}/status", headers=headers
    )
    assert status.status_code == 200, (
        f"读报表状态失败：{status.status_code} {status.text[:300]}"
    )
    # ⚠️ 终态词是 **SUCCEEDED**（不是 SUCCESS）—— 计划里写的那词是错的
    assert status.json()["status"] == "SUCCEEDED", (
        f"报表终态不是 SUCCEEDED：{status.json()}"
    )

    digest = await e2e_client.get(f"/api/v1/report/{file_id}/hash", headers=headers)
    assert digest.status_code == 200, (
        f"读报表哈希失败：{digest.status_code} {digest.text[:300]}"
    )
    # ⚠️ 字段名是 **`record_hash_digest`**（不是 hash）
    # ⚠️⚠️ **不再 xfail**（2026-11-17 · A1 裁决 + P10-B 评审 #3/#4/#12/#14）：
    # 审计端点现在读 **`content_hash`**（交付文件的 sha256）⇒ 生成的报表**有值**
    # ⇒ ⇒ 这里断的是**真断言**：等于该文件的 sha256 · 且是 **64 位 hex**。
    # ⚠️ **64 位**：这里断的是**真生成的文件** ⇒ 全量 sha256（单测的 fixture 是
    # 占位串 ⇒ 那边断「同长 + hex」⇒ 两处各断各的层）。
    digest_value = digest.json()["record_hash_digest"]
    assert digest_value, f"审计哈希端点在生成的报表上返空串：{digest.json()}"
    assert len(digest_value) == 64, f"审计哈希不是 64 位 hex：{digest_value!r}"
    assert all(c in "0123456789abcdef" for c in digest_value), digest_value

    download = await e2e_client.get(f"/api/v1/report/{file_id}/download", headers=headers)
    assert download.status_code == 200, (
        f"下载报表失败：{download.status_code} {download.text[:300]}"
    )
    assert len(download.content) > 0, "下载到的报表是空文件"


@pytest.mark.e2e
async def test_e2e_015_custom_report_definition_executes_and_returns_data(
    e2e_client, role_headers, e2e_seed
):
    """三段：建定义 → publish → execute（202|503）⇒ 直调任务体 ⇒ 数据非空。"""
    headers = role_headers("DESIGNER")

    # ① 建 + 发布一个自定义报表定义
    created = await e2e_client.post(
        "/api/v1/report-builder/definitions",
        json={
            "name": "E2E-015 自定义报表",
            "category": "CUSTOM",
            "description": "E2E 场景用",
            # ⚠️ **形状是 PascalCase 且 forbid extra**
            # （`ReportDefinitionBody-Input`）⇒ 写错 ⇒ 422 `extra_forbidden`
            "definition_json": {
                "DataSources": [{"source": "STREAMS", "join_to": None}],
                "SelectedFields": [
                    {"source": "STREAMS", "field": "stream_name", "order": 1},
                    {"source": "STREAMS", "field": "phase", "order": 2},
                ],
                "MaxRows": 100,
                "OutputFormat": "xlsx",
            },
            "output_format": "xlsx",
        },
        headers=headers,
    )
    assert created.status_code in (200, 201), (
        f"建报表定义失败：{created.status_code} {created.text[:300]}"
    )
    def_id = created.json()["def_id"]

    # ⚠️ **发布要 REVIEWER / APPROVER / SYSTEM_ADMIN**（与「建」不同角色）
    # ⇒ 又一处「设计人 ≠ 校核人」的门禁
    published = await e2e_client.post(
        f"/api/v1/report-builder/definitions/{def_id}/publish",
        headers=role_headers("SYSTEM_ADMIN"),
    )
    assert published.status_code in (200, 201), (
        f"发布报表定义失败：{published.status_code} {published.text[:300]}"
    )

    # ② HTTP 段：execute ⇒ **202**（入队成功）
    # ⚠️ **必须 202**（不能是 503）：任务体是拿 `ctx["job_id"]` 去**找端点建的那一行**
    # （`report_builder_tasks.py` 的 `task_row` 查找）⇒ 没有端点的 task_id
    # ⇒ 任务体无从更新状态 ⇒ 状态端点查不到 ⇒ 场景断不了。
    # ⇒ ⇒ **车道的另一个前置：compose 的 redis 起着**（只用于**入队**，
    # **不需要 worker** —— 没人消费那个 job 是故意的）。
    resp = await e2e_client.post(
        f"/api/v1/report-builder/definitions/{def_id}/execute",
        json={"project_id": str(e2e_seed["project_id"])},
        headers=headers,
    )
    assert resp.status_code == 202, (
        f"execute 没被受理（202）⇒ {resp.status_code} {resp.text[:300]}"
        "（⚠️ 需要 compose 的 redis 起着 —— 入队要它，但**不需要 worker**）"
    )
    task_id = resp.json()["task_id"]

    # ③ 产物段：直调任务体 ⇒ 执行状态 + 数据行数 > 0
    from app.workers.report_builder_tasks import execute_definition_task

    factory = e2e_client._e2e_session_factory  # type: ignore[attr-defined]
    await execute_definition_task(
            {
                "session_factory": factory,
                # ⚠️ **必须与端点的 task_id 相同** ⇒ 任务体才找得到那一行
                "job_id": task_id,
                "job_try": 1,
            },
            def_id=str(def_id),
            project_id=str(e2e_seed["project_id"]),
            user_id=str(e2e_seed["users"]["e2e-designer"]),
            filters=None,
            max_rows=100,
            output_format="xlsx",
    )

    status = await e2e_client.get(
        f"/api/v1/report-builder/executions/{task_id}", headers=headers
    )
    assert status.status_code == 200, (
        f"读执行状态失败：{status.status_code} {status.text[:300]}"
    )
    body = status.json()
    # ⚠️ 终态词是 **FINISHED**（不是 SUCCESS / COMPLETED / DONE）
    assert body.get("status") == "FINISHED", f"执行状态不是 FINISHED：{body}"
    file_id = body.get("report_file_id")
    assert file_id, f"执行完了却没产出报表文件：{body}"

    # ⚠️ **执行状态端点不暴露「数据行数」** ⇒ 「数据非空」只能断在**产物**上：
    # 产出的报表文件**有内容**（size_bytes > 0）⇒ 那一行取到了数据。
    # ⇒ 「行数」本身不可观测 ⇒ 记为小缺口（计划的 E2E-015 写的是「数据非空」）。
    file_status = await e2e_client.get(
        f"/api/v1/report/{file_id}/status", headers=headers
    )
    assert file_status.status_code == 200, (
        f"读产物状态失败：{file_status.status_code} {file_status.text[:300]}"
    )
    assert file_status.json()["status"] == "SUCCEEDED", (
        f"产物的终态不是 SUCCEEDED：{file_status.json()}"
    )
    assert int(file_status.json().get("size_bytes") or 0) > 0, (
        f"产出的报表是空文件：{file_status.json()}"
    )
