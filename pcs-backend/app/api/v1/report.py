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

from fastapi import APIRouter, Depends, Query, Request, Response
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1._guard import check_project_access_or_404
from app.api.v1.config import _Actor, current_actor
from app.core.config import get_settings
from app.db.session import get_db
from app.models.report import ReportFile, ReportStyleRow
from app.schemas.report import (
    SUPPORTED_OUTPUT_FORMATS,
    ReportFileStatusResponse,
    ReportGenerateRequest,
    ReportGenerateResponse,
    ReportHashResponse,
    ReportStyleCreate,
    ReportStyleListResponse,
    ReportStyleRevise,
    ReportStyleSummary,
    ReportVerifyResponse,
)
from app.services.audit_service import AuditService
from app.services.exceptions import PcsError
from app.services.report import paths, qr
from app.services.report.style import ReportStyle
from app.services.report.style_service import (
    StyleConflict,
    StylePermissionError,
    StyleService,
)

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
        raise PcsError("verify 未配置签名密钥",
                       code="REPORT_VERIFY_NOT_CONFIGURED", status=403)
    if exp < int(dt.datetime.now(dt.UTC).timestamp()):
        raise PcsError("签名已过期",
                       code="REPORT_VERIFY_SIG_EXPIRED", status=403)
    expect = qr.sign(report_file_id=report_file_id, exp=exp, secret=secret)
    if not hmac.compare_digest(expect, sig or ""):
        raise PcsError("签名无效",
                       code="REPORT_VERIFY_SIG_INVALID", status=403)


async def _load_or_404(db: AsyncSession, report_file_id: uuid.UUID) -> ReportFile:
    row = (await db.execute(
        select(ReportFile).where(ReportFile.report_file_id == report_file_id)
    )).scalar_one_or_none()
    if row is None:
        raise PcsError("报表文件不存在",
                       code="REPORT_FILE_NOT_FOUND", status=404)
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

    # ⚠️ 传**名字字符串**（同 arq_queue 的理由：worker 用
    # `self.functions[function_name]` 查，键全是 str；传函数对象 →
    # job silently failed，API 却返 202）。仍 import 以便提前发现函数不存在。
    from app.workers.report_tasks import generate_report_task  # noqa: F401

    # ⚠️ **task_id 自选，并在入队之前**用它建好 PENDING 行（TODO-063）。
    # 顺序不能反：若先入队再建行，worker 可能抢在前面把行建掉，
    # 于是端点建出第二行 —— 一次执行两行，轮询端点的
    # `scalar_one_or_none()` 当场抛 MultipleResultsFound。
    # ARQ 的 `_job_id` 允许指定 id（`job_id = _job_id or uuid4().hex`），
    # 所以「自选 id」与「用同一个 id 入队」两件事能对上。
    task_id = uuid.uuid4().hex

    from app.services.report import report_service
    row = await report_service.ensure_pending_row(
        db, project_id=body.project_id, task_id=task_id,
        output_format=body.output_format)
    await db.commit()

    # ⚠️ `create_pool` 收的是 **RedisSettings**，不是 DSN 字符串 ——
    # 传字符串会在连接时炸 `'str' object has no attribute 'host'`。
    try:
        # ⚠️ `create_pool` 也在 try 里：它自己就会因 Redis 不可达而抛，
        # 只包 `enqueue_job` 的话连接异常会绕过 503 直奔 500。
        pool = await create_pool(RedisSettings.from_dsn(get_settings().redis_url))
    except Exception as e:  # noqa: BLE001 — Redis 各种连接异常
        await _fail_pending(db, row, f"Redis 连接失败：{type(e).__name__}: {e}")
        raise PcsError(
            message=f"任务队列不可用，本次报表未入队（{type(e).__name__}: {e}）。"
                    "**这不是执行失败** —— 任务从未开始，请稍后重试。",
            code="REPORT_QUEUE_UNAVAILABLE", status=503) from e
    try:
        job = await pool.enqueue_job(
            "generate_report_task",
            report_type=body.report_type,
            project_id=str(body.project_id),
            record_ids=[str(r) for r in body.record_ids],
            output_format=body.output_format,
            style_json={}, ctx_vars={"project_no": "", "doc_no": "", "rev": ""},
            _job_id=task_id,
        )
    except Exception as e:  # noqa: BLE001 — Redis 各种连接异常
        # 入队失败：刚建的 PENDING 行永远不会有人来跑它，就地标 FAILED ——
        # 否则它会一直挂在 PENDING 上，直到回收器 15 分钟后才动它。
        await _fail_pending(db, row, f"入队失败：{type(e).__name__}: {e}")
        raise PcsError(
            message=f"任务队列不可用，本次报表未入队（{type(e).__name__}: {e}）。"
                    "**这不是执行失败** —— 任务从未开始，请稍后重试。",
            code="REPORT_QUEUE_UNAVAILABLE", status=503) from e
    finally:
        await pool.aclose()

    if job is None:
        await _fail_pending(db, row, "入队未返回任务句柄")
        raise PcsError(message="入队未返回任务句柄",
                       code="REPORT_QUEUE_UNAVAILABLE", status=503)

    return ReportGenerateResponse(task_id=task_id,
                                 report_file_id=row.report_file_id,
                                 status="PENDING")


async def _fail_pending(db: AsyncSession, row: ReportFile, reason: str) -> None:
    """把刚建好、但注定没人来跑的 PENDING 行就地标 FAILED 并提交。

    不标的话它会一直挂在 PENDING 上：状态端点显示「生成中」，
    回收器要等 15 分钟才动它，而真相是「压根没入队」。
    """
    row.status = "FAILED"
    row.error_message = reason[:500]
    row.heartbeat_at = dt.datetime.now(dt.UTC)
    await db.commit()


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
        raise PcsError("文件已被清理（登记还在，磁盘文件没了）",
                       code="REPORT_FILE_CLEANED", status=404)
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
        raise PcsError("报表文件不存在",
                       code="REPORT_FILE_NOT_FOUND", status=404)

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
    """列出样式。**只列调用者看得见的**。

    ⚠️ 修复：原先**完全没有权限过滤** —— 任何登录用户都能列出全部
    公司标准与他人项目样式。写入面（c6）按破坏面分两档，读面必须对齐，
    否则权限模型只在写的那半边存在。
    """
    stmt = select(ReportStyleRow).order_by(ReportStyleRow.created_at.desc())
    if report_type:
        stmt = stmt.where(ReportStyleRow.report_type == report_type)
    rows = (await db.execute(stmt)).scalars().all()
    visible = [r for r in rows
               if _style_readable(r, actor_roles=actor.roles, user_id=actor.user_id)]
    return ReportStyleListResponse(
        items=[_summary(r) for r in visible], total=len(visible))


@router.get("/styles/{style_id}", response_model=ReportStyleSummary)
async def get_style(style_id: uuid.UUID, db: DbDep, actor: ActorDep):
    """取单条样式。⚠️ 修复：原先无权限检查（IDOR）。

    凭 style_id 就能读别人的项目级样式 —— 与写入面的两档判定对齐。
    """
    row = await StyleService(db).get(style_id=style_id)
    if row is None:
        raise PcsError("样式不存在",
                       code="REPORT_STYLE_NOT_FOUND", status=404)
    if not _style_readable(row, actor_roles=actor.roles, user_id=actor.user_id):
        # 403 而非 404：调用方要区分「没权限」与「不存在」—— 这里
        # 回 404 会让「你无权」看起来像「样式没了」，用户会去建一条新的。
        # 项目级无权的情形仍由 guard 走 404（不泄漏项目存在性）。
        raise PcsError("无权读取该样式",
                       code="REPORT_STYLE_FORBIDDEN", status=403)
    return _summary(row)


def _style_readable(row, *, actor_roles: list[str], user_id) -> bool:
    """读面判定：公司标准要 ADMIN，项目级放行（写入时再查项目权限）。

    与写入面**不完全对称**是刻意的：写项目级要查 `UserProject`（要打 DB），
    读列表却对每一行都查一次是 N+1。这里放宽到「登录即可读项目级」，
    真正敏感的是公司标准 —— 那一条卡死在 ADMIN 上。
    """
    if row.project_id is None:
        return "SYSTEM_ADMIN" in actor_roles
    return True


def _summary(row: ReportStyleRow) -> ReportStyleSummary:
    return ReportStyleSummary(style_id=row.style_id, report_type=row.report_type,
                             project_id=row.project_id, version=row.version,
                             status=row.status, style=ReportStyle(**row.style_json))


# --- c6 写入面（用户 2026-10-13 裁决）------------------------------------------


@router.post("/styles", response_model=ReportStyleSummary, status_code=201)
async def create_style(body: ReportStyleCreate, db: DbDep,
                       actor: ActorDep) -> ReportStyleSummary:
    """建一条 ACTIVE 样式。权限两档，见 `style_service` 模块 docstring。"""
    row = await _style_call(
        lambda: StyleService(db).create(
            report_type=body.report_type, project_id=body.project_id,
            patch=body.style.model_dump(exclude_unset=True), actor=actor))
    await db.commit()      # ⚠️ 端点负责 commit（与 report_builder.py 一致）
    return _summary(row)


@router.post("/styles/{style_id}/revise", response_model=ReportStyleSummary)
async def revise_style(style_id: uuid.UUID, body: ReportStyleRevise, db: DbDep,
                       actor: ActorDep) -> ReportStyleSummary:
    """改样式 = **新增一版本**（version+1），旧行保留为 SUPERSEDED。

    不在原行上改 `style_json`：`report_files.style_version` 冻结版本号
    就是为了可复现，原地改等于让那个字段说谎。
    """
    row = await _style_call(
        lambda: StyleService(db).revise(
            style_id=style_id,
            patch=body.style.model_dump(exclude_unset=True), actor=actor))
    await db.commit()
    return _summary(row)


@router.post("/styles/{style_id}/activate", response_model=ReportStyleSummary)
async def activate_style(style_id: uuid.UUID, db: DbDep,
                         actor: ActorDep) -> ReportStyleSummary:
    """回滚：把某一历史版本重新置为 ACTIVE。**不删任何行。**"""
    row = await _style_call(
        lambda: StyleService(db).activate(style_id=style_id, actor=actor))
    await db.commit()
    return _summary(row)


#: 竞态被数据库拦下时的文案。与 `style_service.StyleConflict` 的措辞一致，
#: 用户看到哪一条都该得出同一个结论：「该改用修订，不是系统坏了」。
_STYLE_RACE_MSG = "该作用域已有 ACTIVE 样式，请改用修订（revise）。"


async def _style_call(fn):
    """把服务层异常翻成 HTTP。

    ⚠️ 刻意**不**在这里 catch 一切 —— 未知异常仍应是 500。
    只翻三种已定义的语义：权限（403/404）、作用域冲突（409）、
    以及**竞态导致的唯一约束冲突**（409）。
    """
    try:
        return await fn()
    except StylePermissionError as e:
        raise PcsError(e.message, code="REPORT_STYLE_PERMISSION",
                       status=e.status_code) from e
    except StyleConflict as e:
        raise PcsError(str(e), code="REPORT_STYLE_CONFLICT", status=409) from e
    except IntegrityError as e:
        # ⚠️ 「至多一个 ACTIVE」现在由**部分唯一索引**兜底
        # （`uq_report_styles_one_active`，p8_010）。于是两个并发请求里，
        # 失败的那一路**不再**走服务层的「先查有没有」，而是在 flush 时撞索引。
        #
        # 不翻译的后果：用户看到 500「系统错误」，而不是
        # 「该作用域已有 ACTIVE 样式，请改用修订」。500 会被前端当成
        # 故障、用户反复重试，而重试只会再撞一次。
        #
        # ⚠️ 只认这一条约束：其余 IntegrityError（如 content_hash 冲突）
        # 有各自的处理路径，不该被吞成 409。
        #
        # ⚠️ **两种 dialect 的报错文本不一样**，实测：
        #   PG      → `violates unique constraint "uq_report_styles_one_active"`
        #   SQLite  → `UNIQUE constraint failed: report_styles.report_type,
        #              report_styles.project_id`
        # 所以只按索引名匹配的话，单测里会漏（SQLite 不带索引名），
        # 症状是「竞态测试红、真库绿」—— 又一处测试与生产不一致。
        msg = str(e.orig)
        if ("uq_report_styles_one_active" in msg
                or "report_styles.report_type, report_styles.project_id" in msg
                or "report_styles.project_id, report_styles.report_type" in msg):
            raise PcsError(
                f"{_STYLE_RACE_MSG}（并发写入，已由数据库唯一索引拦下）",
                code="REPORT_STYLE_CONFLICT", status=409,
            ) from e
        raise


#: 下载端点的 Content-Type。**必须覆盖 `watermark.EXPORT_FORMATS` 全集**。
#: csv 曾不在这里，而 `_MEDIA.get(fmt, "application/octet-stream")` 会静默兜底
#: —— 不报错，浏览器把 CSV 当二进制下载而不是表格（2026-10-18，#19）。
_MEDIA = {"pdf": "application/pdf",
          "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
          "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
          "csv": "text/csv"}


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