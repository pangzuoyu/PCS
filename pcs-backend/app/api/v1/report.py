"""`/api/v1/report` 路由。

七个别扭但必要的端点：

| 端点 | 认证 | 说明 |
|---|---|---|
| `POST /generate` | Bearer | 202 + task_id，异步任务 |
| `GET /{id}/status` | Bearer | 读 DB 的 `report_files.status`，**不读 ARQ** |
| `GET /{id}/download` | Bearer + 项目访问权 | 404 而非 403（不泄漏存在性） |
| `GET /verify/{id}` | **免登录 + 短时效签名** | 只返结论，不返哈希 |
| `GET /{id}/hash` | Bearer + 项目访问权 | 审计角色取完整哈希 |

**两个消费者，两个端点**：`verify` 给现场扫码（免登录、只给结论），
`/{id}/hash` 给审计（要凭据、给全量）。不要合并成「加个参数」。

## 状态查询读 DB，不读 ARQ

ARQ 的 `keep_result` 默认 **3600 秒** —— 任务结果与异常在 Redis 里 1 小时后
被清除。所以 `/{id}/status` 必须读 `report_files.status`（我们自己在库里的
真相），**不能**去查 ARQ 的 job 结果：那东西一小时后就没了。

## 签名：UUID 不是防线

二维码印在 PDF 上，任何人拿到 PDF 都能提取 `report_file_id`。所以 verify
必须带**短时效 HMAC 签名**（`?sig=…&exp=…`，HMAC-SHA256(secret, "{id}:{exp}")），
且签名**绑定 report_id** —— 否则拿 A 的合法签名能查 B。
免登录免的是 Bearer token，不是签名。
"""
from __future__ import annotations

import datetime as dt
import hashlib
import hmac
import logging
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1._guard import check_project_access_or_404
from app.api.v1.config import _Actor, current_actor
from app.core.config import get_settings
from app.db.session import get_db
from app.models.report import ReportFile, ReportStyleRow
from app.schemas.report import (
    SUPPORTED_OUTPUT_FORMATS,
    ReportGenerateRequest,
    ReportGenerateResponse,
    ReportHashResponse,
    ReportFileStatusResponse,
    ReportStyleListResponse,
    ReportStyleSummary,
    ReportVerifyResponse,
)
from app.services.audit_service import AuditService
from app.services.exceptions import PcsError
from app.services.report import paths
from app.services.report.style import ReportStyle

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/report", tags=["report"])

DbDep = Annotated[AsyncSession, Depends(get_db)]
ActorDep = Annotated[_Actor, Depends(current_actor)]

# verify 签名有效期（秒）。现场扫码是「此刻验证这份文件对不对」，
# 15 分钟足够走到扫描枪前；再长就削弱了「短期凭据」的意义。
VERIFY_SIG_TTL_S = 900


def _client_ip(request: Request) -> str:
    """取客户端 IP。

    ⚠️ `request.client` **不保证是对象**：uvicorn 给 `(host, port)`，
    而 httpx 的 ASGITransport（测试用的就是这个）给**字符串**。
    直接 `.host` 会在测试里 AttributeError，而在生产里恰好能用 ——
    测试与生产的形状不一致，正是要避免的。
    """
    c = request.client
    if c is None:
        return "unknown"
    if isinstance(c, str):
        return c
    return getattr(c, "host", "unknown")


def _check_sig(report_file_id: uuid.UUID, sig: str, exp: int) -> None:
    """校验短时效签名。**失败抛 403 而不是 404** —— 403 才能让调用方
    知道是「签名问题」而非「文件不存在」，现场人员才报得对。"""
    secret = get_settings().report_verify_secret
    if not secret:
        # fail-closed：签名密钥没配 = 无法验证任何签名 = 全部拒绝。
        # fail-open 会让配置遗漏变成「二维码校验形同虚设」。
        raise HTTPException(status_code=403, detail="verify 未配置签名密钥")
    if exp < int(dt.datetime.now(dt.UTC).timestamp()):
        raise HTTPException(status_code=403, detail="签名已过期")
    expect = hmac.new(secret.encode(), f"{report_file_id}:{exp}".encode(),
                      hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expect, sig or ""):
        raise HTTPException(status_code=403, detail="签名无效")


async def _load_or_404(db: AsyncSession, report_file_id: uuid.UUID) -> ReportFile:
    row = (await db.execute(
        select(ReportFile).where(ReportFile.report_file_id == report_file_id)
    )).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Report file not found")
    return row


async def _guard_project(db: AsyncSession, row: ReportFile, actor: _Actor) -> None:
    """项目访问权校验。`project_id` 可空（公司级样式/文件），空则只过角色。"""
    if row.project_id is None:
        return
    await check_project_access_or_404(db, user_id=actor.user_id,
                                       project_id=row.project_id,
                                       actor_roles=actor.roles)


# --- 生成 -------------------------------------------------------------------


@router.post("/generate", response_model=ReportGenerateResponse, status_code=202)
async def generate_report(body: ReportGenerateRequest, db: DbDep, actor: ActorDep):
    """入队异步生成。**入队前**就拒未知格式 —— 让 worker 渲染完再失败
    是白占一个槽位 + 白刷一条 REPORT_FAILED。"""
    if body.output_format not in SUPPORTED_OUTPUT_FORMATS:
        raise PcsError(
            message=f"不支持的输出格式：{body.output_format!r}",
            code="REPORT_FORMAT_UNSUPPORTED", status=400)
    if body.project_id is not None:
        await check_project_access_or_404(db, user_id=actor.user_id,
                                           project_id=body.project_id,
                                           actor_roles=actor.roles)

    from arq import create_pool
    from arq.connections import RedisSettings

    from app.workers.report_tasks import generate_report_task

    # ⚠️ `create_pool` 收的是 **RedisSettings**，不是 DSN 字符串 ——
    # 传字符串会在连接时炸 `'str' object has no attribute 'host'`。
    pool = await create_pool(RedisSettings.from_dsn(get_settings().redis_url))
    try:
        job = await pool.enqueue_job(
            generate_report_task,
            report_type=body.report_type,
            project_id=str(body.project_id),
            record_ids=[str(r) for r in body.record_ids],
            output_format=body.output_format,
            style_json={}, ctx_vars={"project_no": "", "doc_no": "", "rev": ""},
        )
    finally:
        await pool.aclose()
    return ReportGenerateResponse(task_id=job.job_id if job else "", status="PENDING")


# --- 状态 / 下载 ------------------------------------------------------------


@router.get("/{report_file_id}/status", response_model=ReportFileStatusResponse)
async def report_status(report_file_id: uuid.UUID, db: DbDep, actor: ActorDep):
    row = await _load_or_404(db, report_file_id)
    await _guard_project(db, row, actor)
    return ReportFileStatusResponse(
        report_file_id=row.report_file_id, status=row.status,
        file_format=row.file_format, size_bytes=row.size_bytes,
        error_message=row.error_message, heartbeat_at=row.heartbeat_at)


@router.get("/{report_file_id}/download")
async def download(report_file_id: uuid.UUID, db: DbDep, actor: ActorDep):
    row = await _load_or_404(db, report_file_id)
    await _guard_project(db, row, actor)
    path = paths.resolve_path(row.file_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="文件已被清理")
    await AuditService(db).write(
        action="REPORT_DOWNLOADED", resource_type="report",
        resource_id=row.report_file_id, user_id=actor.user_id)
    # ⚠️ **必须显式 commit**。`get_db` 只在异常时 rollback，**不负责提交** ——
    # 漏了这一行，审计写在 session close 时随未提交事务一起消失，
    # 而响应仍是 200。生产上表现为「谁导出过这份计算书」永远查不到。
    await db.commit()
    return FileResponse(path, media_type=_MEDIA.get(row.file_format, "application/octet-stream"),
                        filename=path.name)


# --- verify（免登录 + 签名）-------------------------------------------------


@router.get("/verify/{report_file_id}", response_model=ReportVerifyResponse)
async def verify(request: Request, report_file_id: uuid.UUID, db: DbDep,
                 sig: Annotated[str, Query()] = "",
                 exp: Annotated[int, Query()] = 0):
    """扫码校验。**免登录但不免签名** —— 免的是 Bearer token。

    响应**不含哈希**（用户 2026-10-08 裁决）：比对的主语是系统。
    """
    from app.services._sliding_window_rate_limit import check_rate_limit

    ip = _client_ip(request)
    if not await check_rate_limit(f"report_verify:{ip}",
                                  limit=get_settings().report_verify_rate_limit,
                                  window_seconds=60):
        raise PcsError(message="验证过于频繁，请稍后再试",
                       code="REPORT_VERIFY_RATE_LIMITED", status=429)

    _check_sig(report_file_id, sig, exp)
    row = (await db.execute(
        select(ReportFile).where(ReportFile.report_file_id == report_file_id)
    )).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Report file not found")

    # `match` 的含义：**这份登记过的文件，在磁盘上还是原样吗**。
    #
    # ⚠️ 不能拿 `data_version` 和自己比 —— 那是恒真的空检查（第一版就写错了，
    # 靠「把 data_version 改成别的值」的测试才发现：改完仍然 match=true）。
    # 现场扫码的人手里没有原始文件，算不出源记录哈希，所以唯一**可执行**的
    # 校验是文件完整性：重算磁盘文件的 sha256，与登记时的 content_hash 比。
    #
    # 不一致返回 **200 + match=false** 而不是 404 —— 404 会让现场人员以为是
    # 「二维码无效」，而事实是「文件被改过」，那是两句不同的话。
    return ReportVerifyResponse(
        match=_file_intact(row),
        doc_no=row.doc_no, rev=row.rev, generated_at=row.created_at)


@router.get("/{report_file_id}/hash", response_model=ReportHashResponse)
async def report_hash(report_file_id: uuid.UUID, db: DbDep, actor: ActorDep):
    """审计角色取完整哈希 —— 与 verify 分端点，敏感度不同。"""
    row = await _load_or_404(db, report_file_id)
    await _guard_project(db, row, actor)
    return ReportHashResponse(report_file_id=row.report_file_id,
                        record_hash_digest=_expected_digest(row),
                        data_version=row.data_version,
                        generated_at=row.created_at)


# --- 样式 -------------------------------------------------------------------


@router.get("/styles", response_model=ReportStyleListResponse)
async def list_styles(db: DbDep, actor: ActorDep,
                      report_type: Annotated[str, Query()] = "",
                      project_id: Annotated[uuid.UUID | None, Query()] = None):
    stmt = select(ReportStyleRow).order_by(ReportStyleRow.created_at.desc())
    if report_type:
        stmt = stmt.where(ReportStyleRow.report_type == report_type)
    rows = (await db.execute(stmt)).scalars().all()
    items = [ReportStyleSummary(style_id=r.style_id, report_type=r.report_type,
                          project_id=r.project_id, version=r.version,
                          status=r.status, style=ReportStyle(**r.style_json))
             for r in rows]
    return ReportStyleListResponse(items=items, total=len(items))


@router.get("/styles/{style_id}", response_model=ReportStyleSummary)
async def get_style(style_id: uuid.UUID, db: DbDep, actor: ActorDep):
    row = (await db.execute(
        select(ReportStyleRow).where(ReportStyleRow.style_id == style_id)
    )).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Style not found")
    return ReportStyleSummary(style_id=row.style_id, report_type=row.report_type,
                        project_id=row.project_id, version=row.version,
                        status=row.status, style=ReportStyle(**row.style_json))


_MEDIA = {"pdf": "application/pdf",
          "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
          "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document"}


def _file_intact(row: ReportFile) -> bool:
    """磁盘文件的内容指纹是否仍与登记时一致。

    文件不在 / 读不出来 → **False**（而不是 True）：「无法验证」不等于「通过」。
    """
    try:
        path = paths.resolve_path(row.file_path)
        if not path.exists():
            return False
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
    except (OSError, PcsError):
        return False
    return digest == row.content_hash


def _expected_digest(row: ReportFile) -> str:
    """登记时冻结的数据版本（`data_version`），供审计端点查。"""
    return row.data_version or ""


__all__ = ["router", "Response"]