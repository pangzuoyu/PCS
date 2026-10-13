"""b11：执行时序契约 —— `task_id` 必须能查到 `report_file_id`。

## 这是「绿灯测的不是出问题那层」的典型样本

2026-10-13 实测发现的缺口：

- `POST /report-builder/definitions/{id}/execute` 返回 **202 + `task_id`**
- `GET /report/{report_file_id}/status` **只认 `report_file_id`**
- 两者的映射**无处可查**

于是前端拿到 202 之后永远拿不到文件 —— 执行面板转圈到超时。
而**每一层各自的测试都是绿的**：端点返回 202 符合契约、status 端点
按 id 查也正确、审计照写。缺的是两者**之间**的那一环，
只有把「202 之后能不能真的拿到文件」当一条测试才暴露得出来。

用户 2026-10-13 裁决：「修的是契约，不是 UI。」
"""
from __future__ import annotations

import uuid

import pytest

from app.core.security import create_access_token


def _auth(role="DESIGNER"):
    return {"Authorization": f"Bearer {create_access_token(subject='u', role=role)}"}


#: 端点级执行日志带 `task_id` ↔ `report_file_id` 的映射
POLL = "/api/v1/report-builder/executions"


@pytest.mark.asyncio
async def test_unknown_task_id_is_404_not_500(client):
    r = await client.get(f"{POLL}/{uuid.uuid4()}", headers=_auth())
    assert r.status_code == 404, r.text


@pytest.mark.asyncio
async def test_unknown_task_id_does_not_leak_other_executions(client):
    """查一个不存在的 task_id 必须 404，且不返回任何执行信息。

    轮询端点若在「查不到」时回一个带默认值的响应
    （`{status: "PENDING", report_file_id: null}`），前端就分不清
    「这个任务不存在」与「这个任务还在跑」—— 而前者应当立刻停止轮询。
    """
    r = await client.get(f"{POLL}/no-such-task", headers=_auth())
    assert r.status_code == 404, r.text
    assert "report_file_id" not in r.text


@pytest.mark.asyncio
async def test_polling_requires_auth(client):
    assert (await client.get(f"{POLL}/abc")).status_code == 401


@pytest.mark.asyncio
async def test_execution_log_row_carries_the_two_link_columns(client, db_session):
    """⚠️ **映射必须真的落在执行日志行上**，不只是端点能编出来。

    端点自己拼一个 `task_id` → 文件的映射（比如查 audit_logs 的
    detail_json）也能让上面几条绿，但那样每次轮询都要扫 JSONB。
    这里直接钉住：执行日志行上有 `task_id` 与 `report_file_id` 两列。
    """
    from app.models.report import ReportExecutionLog

    cols = set(ReportExecutionLog.__table__.columns.keys())
    assert {"task_id", "report_file_id"} <= cols, \
        f"执行日志缺列：{sorted(cols)}"


@pytest.mark.asyncio
async def test_task_id_is_indexed(client):
    """轮询是每 2 秒一次、并发多个用户 —— 没有索引就是全表扫。"""
    from sqlalchemy import Index

    from app.models.report import ReportExecutionLog

    idx = {i.name for i in ReportExecutionLog.__table__.indexes}
    assert "ix_report_execution_logs_task_id" in idx, f"现有索引：{sorted(idx)}"


# --- 端到端：映射真的会闭合吗 ---------------------------------------------------


async def _published_def(client) -> str:
    """建一条**已发布**定义并返回其 id。

    走 API 而不是直接插 ORM 行：端点自己 commit，且发布流程（DRAFT →
    PUBLISHED）也一并覆盖。直接插行的话，轮询端点的可见性检查会
    正确地 404 —— 症状是「测试数据不存在」，看起来像端点坏了。
    """
    # ⚠️ 创建是 DESIGNER，**发布**要 REVIEWER/APPROVER/SYSTEM_ADMIN
    # （`require_roles` 钉的）。用错角色的症状是 403 而不是 201 ——
    # 看起来像「端点坏了」，实际是测试没过权限那一关。
    h = _auth()
    body = {
        "project_id": None, "name": "轮询契约用定义", "category": "测试",
        "description": "", "output_format": "pdf", "shared_with": "ALL_USERS",
        "definition_json": {
            "DataSources": [{"source": "EQUIP_LIST"}],
            "SelectedFields": [{"source": "EQUIP_LIST", "field": "tag_number",
                                "alias": "位号", "order": 0, "visible": True}],
        },
    }
    r = await client.post("/api/v1/report-builder/definitions", headers=h, json=body)
    assert r.status_code == 201, r.text
    d = r.json()["def_id"]
    p = await client.post(f"/api/v1/report-builder/definitions/{d}/publish",
                          headers=_auth("REVIEWER"))
    assert p.status_code == 200, p.text
    return d


@pytest.mark.asyncio
async def test_worker_backfills_report_file_id_so_the_bridge_closes(client,
                                                                    db_session):
    """⚠️ **根断言**：任务体跑完后，`task_id` 必须能查出 `report_file_id`。

    上面的测试各自只证明「列存在」「端点不 500」—— 两者都成立时
    桥仍然是断的（列永远是 NULL，轮询永远停在 RUNNING）。
    所以这里把 worker 的回填动作真跑一遍。

    这是本文件存在的理由：**每一层单独看都是绿的，缺的只是它们之间
    那一环**，只有把整条链跑一遍才看得见。
    """
    import uuid as _uuid

    from app.models.report import ReportExecutionLog
    from app.workers.report_builder_tasks import _link_report_file

    def_id = await _published_def(client)
    task_id = "task-abc"
    db_session.add(ReportExecutionLog(
        def_id=_uuid.UUID(def_id), def_version="0.1.0",
        condition_snapshot={}, row_count=0, output_format="pdf",
        is_temporary_adjust=False, task_id=task_id))
    # ⚠️ 必须 commit：`db_session` 与 `client` 各有各的事务，
    # 不提交的话端点那边根本看不见这行 —— 症状是「测试写的行不存在」。
    await db_session.commit()

    file_id = _uuid.uuid4()
    await _link_report_file(db_session, task_id=task_id, report_file_id=file_id)
    await db_session.commit()

    r = await client.get(f"{POLL}/{task_id}", headers=_auth())
    assert r.status_code == 200, r.text
    assert r.json()["report_file_id"] == str(file_id), \
        "回填没生效 —— 轮询会永远停在 RUNNING"


@pytest.mark.asyncio
async def test_still_running_before_the_file_exists(client, db_session):
    """文件还没生成时 `report_file_id` 为 null、status=RUNNING。

    ⚠️ 必须是 **null 而不是空串/占位 id** —— 前端拿到一个不存在的 id
    会去 `/report/{id}/status` 查，那儿 404，于是「还在跑」被误读成
    「任务死了」。
    """
    import uuid as _uuid

    from app.models.report import ReportExecutionLog

    def_id = await _published_def(client)
    task_id = "task-running"
    db_session.add(ReportExecutionLog(
        def_id=_uuid.UUID(def_id), def_version="0.1.0",
        condition_snapshot={}, row_count=0, output_format="pdf",
        is_temporary_adjust=False, task_id=task_id))
    await db_session.commit()

    r = await client.get(f"{POLL}/{task_id}", headers=_auth())
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "RUNNING"
    assert body["report_file_id"] is None
