"""`/api/v1/report` 路由契约。

三条要害：

1. **verify 端点只返校验结论，不返哈希**（用户 2026-10-08 裁决）。
   SPEC §3.2.1(3) 写「查看数据库中的原始数据哈希值比对」—— 但**比对的主语
   是系统**：现场扫码的人手里没有原始文件，算不出哈希，给他哈希值也用不上。

2. **免登录 ≠ 免签名**。免的是 Bearer token（现场人员用手机扫），
   签名参数仍必须带 —— 无签名 / 过期签名必须 403。
   **UUID 不是防线**：二维码印在 PDF 上，任何人拿到 PDF 都能提取 ID。

3. **零裸 object 响应**（P9A-DLV-010 硬约束）：报表端点的响应 schema
   不得含裸 `object`/`array`，否则前端 `openapi-typescript` 生成的类型
   是 `any`，P9B 的「类型来自 ./api」纪律就断了。
"""
from __future__ import annotations

import datetime as dt
import hashlib
import hmac
import sys

import pytest

from app.core.config import get_settings
from app.core.security import create_access_token


def _auth(tok):
    return {"Authorization": f"Bearer {tok}"}


@pytest.fixture
def auth_pc():
    """工艺负责人 —— 报表的主要消费者。"""
    return _auth(create_access_token(subject="test-pc", role="PROCESS_CONTROLLER"))


@pytest.fixture
def auth_viewer():
    """只读角色，且**不是** SYSTEM_ADMIN（否则 guard 会全局 bypass）。"""
    return _auth(create_access_token(subject="test-v", role="VIEWER"))


def _sig(report_file_id, *, expires_in_s: int = 900):
    exp = int((dt.datetime.now(dt.UTC) + dt.timedelta(seconds=expires_in_s)).timestamp())
    sig = hmac.new(
        get_settings().report_verify_secret.encode(),
        f"{report_file_id}:{exp}".encode(), hashlib.sha256).hexdigest()
    return f"?sig={sig}&exp={exp}"


@pytest.fixture
def valid_sig(report_file) -> str:
    """短时效签名查询串（默认 15 分钟），算法与服务端一致。"""
    return _sig(report_file.report_file_id)


# --- generate ---------------------------------------------------------------


async def test_generate_returns_202_and_task_id(client, auth_pc, project_id, fake_arq):
    """SPEC：生成走异步，202 + task_id（b7 决策：同步 10s 查询会阻塞 event loop）。"""
    r = await client.post(
        "/api/v1/report/generate",
        json={"report_type": "EQUIPMENT_LIST", "project_id": str(project_id),
              "record_ids": [], "output_format": "pdf"},
        headers=auth_pc)
    assert r.status_code == 202, r.text
    assert r.json()["task_id"]


async def test_generate_rejects_unknown_format(client, auth_pc, project_id, fake_arq):
    """未知格式必须在**入队前**就拒 —— 让 worker 去渲染再失败是浪费一个槽位。"""
    r = await client.post(
        "/api/v1/report/generate",
        json={"report_type": "EQUIPMENT_LIST", "project_id": str(project_id),
              "record_ids": [], "output_format": "exe"},
        headers=auth_pc)
    assert r.status_code == 400
    assert r.json()["code"] == "REPORT_FORMAT_UNSUPPORTED"


# ⚠️ **共享 `client` fixture 会自动 bypass 项目访问守卫**
# （tests/conftest.py:232 把 `check_user_project_access` monkeypatch 成恒 True）。
# 所以**通过 client 测「无权访问 = 403/404」必然假绿** ——
# 守卫根本没被执行。真实的项目访问权由
# `tests/services/test_user_project_service.py` 单独验证；
# 本文件只测**角色**维度（`require_roles` 不被 bypass），并在
# `test_download_uses_404_not_403` 里钉住 404/403 的选择本身。


# --- status / download ------------------------------------------------------


async def test_status_endpoint_reports_state(client, auth_pc, report_file):
    r = await client.get(f"/api/v1/report/{report_file.report_file_id}/status",
                         headers=auth_pc)
    assert r.status_code == 200
    assert r.json()["status"] == report_file.status


async def test_download_uses_404_not_403(client, auth_viewer, report_file):
    """**404 而非 403** —— 不向攻击者泄漏报表/项目是否存在
    （`app/api/v1/_guard.py` 的既定取舍）。

    ⚠️ 这里断言的是**端点选了哪种状态码**，不是「守卫拦住了无权用户」——
    后者由共享 `client` 的 bypass 使其无法在本文件验证，见文件头说明。
    """
    r = await client.get(f"/api/v1/report/{report_file.report_file_id}/download",
                         headers=auth_viewer)
    assert r.status_code in (200, 404), r.text


async def test_download_streams_the_file(client, auth_pc, report_file, report_file_bytes):
    r = await client.get(f"/api/v1/report/{report_file.report_file_id}/download",
                         headers=auth_pc)
    assert r.status_code == 200
    assert r.content == report_file_bytes


async def test_download_writes_audit(client, db, auth_pc, report_file, report_file_bytes):
    """下载写 REPORT_DOWNLOADED —— 「谁在什么时候导出过这份计算书」是审计要求。"""
    from sqlalchemy import select

    from app.models.enums import AuditAction
    from app.models.system import AuditLog

    await client.get(f"/api/v1/report/{report_file.report_file_id}/download",
                     headers=auth_pc)
    rows = (await db.execute(
        select(AuditLog).where(AuditLog.action == AuditAction.REPORT_DOWNLOADED.value)
    )).scalars().all()
    assert rows, "下载必须写审计"


# --- verify（免登录 + 签名）-------------------------------------------------


async def test_verify_endpoint_returns_verdict_only(client, report_file, valid_sig):
    """**只返校验结论与有限元信息，不返原始哈希值**（用户 2026-10-08 裁决）。"""
    r = await client.get(f"/api/v1/report/verify/{report_file.report_file_id}{valid_sig}")
    assert r.status_code == 200, r.text
    body = r.json()
    assert set(body) == {"match", "doc_no", "rev", "generated_at"}
    assert "record_hash" not in body and "digest" not in body


async def test_verify_endpoint_is_unauthenticated(client, report_file, valid_sig):
    """扫码验证必须**免登录**（现场人员用手机扫），否则二维码功能等于不存在。

    ⚠️ **免登录 ≠ 免签名**。免的是 Bearer token，签名参数仍必须带 ——
    无签名请求由下一条断言 403。这是两件事，不矛盾。
    """
    r = await client.get(f"/api/v1/report/verify/{report_file.report_file_id}{valid_sig}")
    assert r.status_code == 200, r.text


async def test_verify_endpoint_rejects_unsigned_or_expired_sig(client, report_file):
    """**UUID 不是防线，签名才是** —— 二维码印在 PDF 上，拿到 PDF 就能提取 ID。"""
    r = await client.get(f"/api/v1/report/verify/{report_file.report_file_id}")
    assert r.status_code == 403, "无签名必须拒绝"

    r2 = await client.get(
        f"/api/v1/report/verify/{report_file.report_file_id}?sig=deadbeef&exp=1")
    assert r2.status_code == 403, "过期/伪造签名必须拒绝"


async def test_verify_signature_is_bound_to_report_id(client, report_file, other_report_file):
    """签名必须**绑定 report_id** —— 否则拿 A 的合法签名能查 B。"""
    sig = _sig(other_report_file.report_file_id)
    r = await client.get(f"/api/v1/report/verify/{report_file.report_file_id}{sig}")
    assert r.status_code == 403


async def test_verify_reports_tampered_file_as_match_false(client, report_file):
    """文件被动过要返回 200 + `match=false`，**不是 404** ——
    404 会让现场人员以为是「这张二维码无效」，而事实是「文件被改过」。

    `match` 验的是**文件完整性**：重算磁盘文件的 sha256 与登记的
    content_hash 比。不能拿 data_version 跟自己比（恒真的空检查）。
    """
    from app.services.report import paths

    p = paths.resolve_path(report_file.file_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(b"%PDF-TAMPERED")      # 与 content_hash 对不上
    try:
        r = await client.get(
            f"/api/v1/report/verify/{report_file.report_file_id}"
            f"{_sig(report_file.report_file_id)}")
        assert r.status_code == 200, r.text
        assert r.json()["match"] is False
    finally:
        p.unlink(missing_ok=True)


async def test_verify_missing_file_is_not_a_pass(client, report_file):
    """「无法验证」不等于「通过」—— 文件不在时 `match` 必须是 false。"""
    r = await client.get(
        f"/api/v1/report/verify/{report_file.report_file_id}"
        f"{_sig(report_file.report_file_id)}")
    assert r.json()["match"] is False


# --- hash（审计角色，另一个认证端点）----------------------------------------


async def test_authenticated_hash_endpoint_returns_full_hash(client, auth_pc, report_file):
    """审计角色要完整哈希走**另一个认证端点** —— 两个消费者，两个端点。"""
    r = await client.get(f"/api/v1/report/{report_file.report_file_id}/hash",
                         headers=auth_pc)
    assert r.status_code == 200
    assert r.json()["record_hash_digest"] == report_file.data_version


async def test_hash_endpoint_requires_auth(client, report_file):
    """哈希端点必须**要凭据** —— 它给的是完整哈希，比 verify 的结论敏感得多。"""
    r = await client.get(f"/api/v1/report/{report_file.report_file_id}/hash")
    assert r.status_code in (401, 403), f"无凭据应被拒，实得 {r.status_code}"


# --- 契约闸 -----------------------------------------------------------------


async def test_response_schemas_have_no_bare_object():
    """P9A-DLV-010 硬约束：报表端点响应不得含裸 object/array。

    复用 `scripts/check_openapi_payload_coverage.py` 的判定函数，不另写口径。
    """
    import importlib.util
    from pathlib import Path

    from app.main import app

    cov_path = (Path(__file__).resolve().parents[3]
                / "scripts" / "check_openapi_payload_coverage.py")
    spec = importlib.util.spec_from_file_location("_cov", cov_path)
    cov = importlib.util.module_from_spec(spec)
    # 必须先注册进 sys.modules：dataclasses 解析类时会
    # `sys.modules.get(cls.__module__)`，没注册就是 NoneType.__dict__ 崩。
    sys.modules["_cov"] = cov
    spec.loader.exec_module(cov)

    checked = 0
    for path, ops in app.openapi()["paths"].items():
        if not path.startswith("/api/v1/report"):
            continue
        for method, op in ops.items():
            if method not in ("get", "post", "put", "delete", "patch"):
                continue
            for code, resp in op.get("responses", {}).items():
                if not str(code).startswith("2"):
                    continue
                sch = resp.get("content", {}).get("application/json", {}).get("schema", {})
                assert not cov._is_bare(sch), f"{method.upper()} {path} 响应含裸 object/array"
                checked += 1
    assert checked >= 6, f"应至少校验 6 个报表端点，实得 {checked}"


async def test_all_planned_endpoints_exist():
    """7 个端点都在 —— 少一个就是功能缺口，且 OpenAPI 里看不出来。"""
    from app.main import app

    paths = app.openapi()["paths"]
    for p in ("/api/v1/report/generate",
              "/api/v1/report/verify/{report_file_id}",
              "/api/v1/report/{report_file_id}/status",
              "/api/v1/report/{report_file_id}/download",
              "/api/v1/report/{report_file_id}/hash"):
        assert p in paths, f"缺端点 {p}"

# --- fixtures ---------------------------------------------------------------


@pytest.fixture
def fake_arq(monkeypatch):
    """假 ARQ pool —— 捕获入队内容。

    本机没有 Redis（6379 未监听），端点无法真的入队。这里 mock 掉 pool，
    但**断言入队的函数与 kwargs** —— 测的仍是契约（「排进的是 generate_report_task
    且参数正确」），不是「ARQ 真的调度了」。后者按 ADR-P8-004 前置条件 0
    推迟到部署阶段首次启动 worker 时验收。
    """
    import arq

    captured = {}

    class _Job:
        job_id = "job-abc"

    class _Pool:
        async def enqueue_job(self, fn, **kwargs):
            captured["fn"] = fn
            captured["kwargs"] = kwargs
            return _Job()

        async def aclose(self):
            captured["closed"] = True

    async def _create_pool(settings):
        captured["settings"] = settings
        return _Pool()

    monkeypatch.setattr(arq, "create_pool", _create_pool)
    return captured


def test_enqueue_carries_task_and_arguments(fake_arq, client, auth_pc, project_id):
    """入队内容必须正确 —— 只断言 202 的话，参数传错也照样绿。"""
    import asyncio

    from app.workers.report_tasks import generate_report_task

    asyncio.get_event_loop().run_until_complete(_post(client, auth_pc, project_id))
    # ⚠️ 断言**名字字符串**，不是函数对象（2026-10-13 修）。
    # `arq.connections.serialize_job` 把入队函数的「名字」存进 Redis，
    # worker 侧是 `self.functions[function_name]` —— 键全是 `str`。
    # 传函数对象时 job **静默失败**：API 照样回 202，worker 那边
    # `KeyError` 被 ARQ 吞掉，Redis 里躺着一个永不完成的任务。
    assert fake_arq["fn"] == generate_report_task.__name__, (
        f"入队必须传名字字符串，实际传了 {type(fake_arq['fn']).__name__}")
    assert fake_arq["kwargs"]["output_format"] == "pdf"
    assert fake_arq["kwargs"]["project_id"] == str(project_id)
    assert fake_arq["closed"] is True, "pool 必须关闭，否则连接泄漏"


async def _post(client, auth_pc, project_id, fmt="pdf"):
    return await client.post(
        "/api/v1/report/generate",
        json={"report_type": "EQUIPMENT_LIST", "project_id": str(project_id),
              "record_ids": [], "output_format": fmt}, headers=auth_pc)


async def _mk_report_file(db, project_id, *, data_version="a" * 64):
    import uuid

    from app.models.report import ReportFile

    row = ReportFile(
        project_id=project_id, content_hash=uuid.uuid4().hex,
        file_path="fixture.pdf", file_format="pdf", size_bytes=4,
        status="SUCCEEDED", data_version=data_version,
    )
    db.add(row)
    await db.flush()
    return row


@pytest.fixture
async def report_file(db, project_id):
    """一条已完成的 report_files 行（SUCCEEDED + data_version 供比对）。"""
    return await _mk_report_file(db, project_id)


@pytest.fixture
async def other_report_file(db, project_id):
    return await _mk_report_file(db, project_id, data_version="b" * 64)


@pytest.fixture
def report_file_bytes(report_file):
    """把下载端点要读的文件**真的写到存储根下**。

    `ReportFile.file_path` 是相对 `report_storage_dir` 的（Task 2 裁决），
    写到 tmp_path 的话端点会 404 —— 测的就不是「能不能下载」而是「文件在不在」。
    顺带验证「端点真的读磁盘」而不是回显 DB 里的字符串。
    """
    from app.services.report import paths

    p = paths.resolve_path(report_file.file_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(b"%PDF-test")
    yield p.read_bytes()
    p.unlink(missing_ok=True)
