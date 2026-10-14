"""报表定义管理（REPORT_BUILDER 的定义侧，Phase 2 b2/b3）。

**写入时校验、而不是执行时校验**：数据源与字段在 `POST/PUT` 就对着
`datasource_registry` 核一遍。放到执行时才核，用户已经填完整张报表、
配好了 JOIN、设完了条件，最后一步才告诉他字段名写错了 —— 那是几分钟的
工作作废。

## 可见性（SPEC §3.2.2(6)）

| 状态 | 谁能看/用 |
|---|---|
| DRAFT | **仅创建人** |
| PUBLISHED | 按 `shared_with`：`ALL_USERS` 全员 / `CREATOR_ONLY` 仅创建人 |
| OBSOLETE | 同 PUBLISHED（历史查询用），但不在默认列表里 |

对「无权访问」一律 **404 而非 403**：403 等于确认了这个 ID 存在。

## 三处裁决（SPEC 未明说，按最小可辩护方案定）

1. **`shared_with` 只实现两个取值。** SPEC 写「全部用户/指定角色/仅创建人」，
   但表里只有 `shared_with: String(20)` 一列，**没有角色清单列** —— 「指定
   角色」在当前 schema 下无法表达。收到该取值直接 400，**不静默降级成
   ALL_USERS**：可见范围静默放大是权限事故，不是体验问题。
2. **改已发布定义 = 原地版本 +1 且状态退回 DRAFT。** SPEC 说「已发布定义
   修改时自动创建新版本」。若只 +1 而保持 PUBLISHED，等于绕过了审批 ——
   谁都能改一下就生效。退回 DRAFT 让新版本重新过审批线。
   代价：没有保留旧版本内容的历史表；需要时再加。
3. **改草稿不动版本号。** 草稿没过审批线，「第几稿」对审批者无意义。
"""
from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.report import ReportDefinition
from app.services.exceptions import PcsError
from app.services.report.datasource_registry import DATASOURCES

# 状态集 —— SPEC §3.2.2(2) 的 `Status enum 草稿/已发布/已作废`。
#
# ⚠️ 计划文件写的是「5 态流转测试通过」，但 SPEC 只有 3 态，流程图里
# 「发布审批」是**动作**不是状态，也没有驳回态。以 SPEC 为准实现 3 态；
# 将来真要 5 态（多一个「待审批/驳回」），是**加状态**而不是改这里。
DEFINITION_STATUSES = frozenset({"DRAFT", "PUBLISHED", "OBSOLETE"})

# 见模块 docstring 裁决 1
SUPPORTED_SHARED_WITH = frozenset({"ALL_USERS", "CREATOR_ONLY"})

# ⚠️ **这是实现上限，不是 SPEC 要求**（用户 2026-10-14 裁决）。
#
# SPEC 只规定默认值 10000，**没有**规定上限。原先这里是 100_000，
# 而 `query_engine.assemble` 的 `batch_size` 默认 10000 且超限硬抛
# `REPORT_JOIN_TOO_LARGE` —— 两处分家，差集（10001..100000）里的定义
# 保存时校验通过、执行时确定性 400。那是「保存成功、执行时才炸」。
#
# 为什么是实现上限：ADR-P8-004 实测 10k 行 PDF = 9.6 秒 ⇒ 10 万行 = 96 秒，
# 而 SPEC 复杂报表预算是 15 秒。XLSX 快 40 倍（10 万行 ≈ 2.3 秒）在预算内，
# 所以「按输出格式定不同上限」是合理的未来形态 —— 但那是 P9 的范围，
# P8 不做。当前只有一个上限，如实声明。
#
# ⚠️ `assemble` 的 `batch_size` 语义上**是「分批大小」而不是「上限」**
# ——超了本该分批处理而不是抛错。两者被写成了同一个参数。
# 补齐真分批（内存边界、跨批状态、进度上报）是独立工作量，不在 P8。
# 有测试钉住两者相等，见 `test_every_advertised_max_rows_ceiling_equals_the_engine_limit`。
MAX_ROWS_CEILING = 10000
DEFAULT_VERSION = "0.1.0"


def bump_patch(version: str) -> str:
    """修订位 +1，带进位：`0.1.9 → 0.2.0`。

    解析不了就退回 `0.1.1` 而不是抛错：版本号是**展示与审计**用的，
    为了它拒绝一次编辑是本末倒置（但静默保持原值也不行，那会让「改了
    却没有新版本」看不出来）。
    """
    parts = version.split(".")
    try:
        major, minor, patch = (int(p) for p in parts[:3])
    except (ValueError, TypeError):
        return "0.1.1"
    patch += 1
    if patch >= 10:
        patch, minor = 0, minor + 1
    return f"{major}.{minor}.{patch}"


def validate_definition_json(payload: dict[str, Any]) -> None:
    """按注册表核对数据源与字段；不合法抛 `PcsError`（400）。

    两条不同的错误码，因为处置不同：
    - `REPORT_DATASOURCE_UNKNOWN`：源本身不存在 → 定义得重写
    - `REPORT_FIELD_UNKNOWN`：源存在但字段不属于它 → 通常是源选错了
    """
    if not isinstance(payload, dict):
        raise PcsError("定义内容必须是对象", code="REPORT_DEFINITION_INVALID", status=400)

    sources: list[str] = []
    for entry in payload.get("DataSources") or []:
        key = entry.get("source") if isinstance(entry, dict) else entry
        if key not in DATASOURCES:
            raise PcsError(
                f"未知数据源：{key!r}。可用：{', '.join(sorted(DATASOURCES))}",
                code="REPORT_DATASOURCE_UNKNOWN", status=400,
            )
        sources.append(key)
    if not sources:
        raise PcsError("至少要选一个数据源", code="REPORT_DEFINITION_INVALID", status=400)

    # 分级核对（ADR-0028）。只有 HEAT_RESULTS 参与，其他源不受影响。
    from app.services.report.detail_level import validate_definition

    validate_definition(payload)

    for sel in payload.get("SelectedFields") or []:
        src = sel.get("source")
        field = sel.get("field")
        # 字段必须属于它声明的那个源：跨源字段名在注册表里常常都是合法的
        # （多个源都有 tag_number），拼错源时查询会**静默返回全 NULL 列**
        # 而不是报错 —— 所以这里必须逐条核对「字段属于这个源」。
        if src not in DATASOURCES or field not in DATASOURCES[src].fields:
            raise PcsError(
                f"字段 {src}.{field} 不在数据源注册表中",
                code="REPORT_FIELD_UNKNOWN", status=400,
            )


def align_with_columns(definition_json: dict[str, Any], *, max_rows: int,
                       output_format: str) -> dict[str, Any]:
    """把定义体里与 ORM 列重复的两个键，对齐到列的值。

    `MaxRows` / `OutputFormat` 在 SPEC §3.2.2(2) 里属于定义体，但**权威副本
    是 ORM 列**（可索引、执行时直接读、不用解 JSON）。两个副本各自可写时
    必然漂移 —— 第一版就这样：列存了 250、定义体还是默认 10000，
    **两个值都合法、两个都不报错**，等到执行时按哪个取全看实现心情。

    所以写入时以列为准覆盖定义体，返回新对象（不改入参）。
    """
    out = dict(definition_json)
    out["MaxRows"] = max_rows
    out["OutputFormat"] = output_format
    return out


def _to_dict(row: ReportDefinition) -> dict[str, Any]:
    return {
        "def_id": row.def_id,
        "project_id": row.project_id,
        "name": row.name,
        "category": row.category,
        "description": row.description,
        "definition_json": row.definition_json,
        "output_format": row.output_format,
        "max_rows": row.max_rows,
        "version": row.version,
        "status": row.status,
        "shared_with": row.shared_with,
        "created_by": row.created_by,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }


def visible_clause(user_id: uuid.UUID):
    """SQL 侧的可见性过滤 —— 与 `is_visible` 保持同一套规则。

    ⚠️ 列表和详情**必须用同一个规则**：列表过滤掉、详情却能按 ID 取到，
    等于没有过滤。所以规则写在这里，两处共用，不各写一遍。
    """
    return (
        (ReportDefinition.created_by == user_id)
        | (
            (ReportDefinition.status == "PUBLISHED")
            & (ReportDefinition.shared_with == "ALL_USERS")
        )
    )


class DefinitionService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, *, user_id: uuid.UUID, name: str, category: str,
                     description: str, output_format: str,
                     definition_json: dict[str, Any], shared_with: str,
                     project_id: uuid.UUID | None = None,
                     max_rows: int = 10000) -> ReportDefinition:
        if shared_with not in SUPPORTED_SHARED_WITH:
            raise PcsError(
                f"shared_with 只支持 {sorted(SUPPORTED_SHARED_WITH)}。"
                "「指定角色」需要角色清单列，当前 schema 没有 —— "
                "静默降级成 ALL_USERS 会把可见范围放大成事故，故拒绝。",
                code="REPORT_DEFINITION_INVALID", status=400,
            )
        validate_definition_json(definition_json)
        await self._check_demo_limit()
        await self._reject_duplicate(project_id, name, exclude=None)
        definition_json = align_with_columns(
            definition_json, max_rows=max_rows, output_format=output_format)

        row = ReportDefinition(
            project_id=project_id, name=name, category=category,
            description=description, definition_json=definition_json,
            output_format=output_format, max_rows=max_rows,
            version=DEFAULT_VERSION, status="DRAFT", shared_with=shared_with,
            created_by=user_id,
        )
        self.db.add(row)
        await self.db.flush()
        return row

    async def get(self, *, def_id: uuid.UUID, user_id: uuid.UUID) -> ReportDefinition:
        row = await self.db.get(ReportDefinition, def_id)
        if row is None or not self._can_see(row, user_id):
            raise PcsError(f"报表定义不存在：{def_id}",
                           code="REPORT_DEFINITION_NOT_FOUND", status=404)
        return row

    async def list(self, *, user_id: uuid.UUID,
                   project_id: uuid.UUID | None = None) -> list[ReportDefinition]:
        stmt = select(ReportDefinition).where(visible_clause(user_id))
        if project_id is not None:
            stmt = stmt.where(ReportDefinition.project_id == project_id)
        # 已作废的不进默认列表（还能按 ID 取到，供审计追溯）
        stmt = stmt.where(ReportDefinition.status != "OBSOLETE")
        return list((await self.db.execute(stmt.order_by(
            ReportDefinition.created_at.desc()))).scalars())

    async def update(self, *, def_id: uuid.UUID, user_id: uuid.UUID,
                     name: str, category: str, description: str,
                     output_format: str, definition_json: dict[str, Any],
                     shared_with: str, max_rows: int = 10000,
                     project_id: uuid.UUID | None = None) -> ReportDefinition:
        row = await self.get(def_id=def_id, user_id=user_id)
        if row.created_by != user_id:
            # 非创建人改 PUBLISHED 的定义 = 绕过审批（见模块 docstring 裁决 2）
            raise PcsError(f"报表定义不存在：{def_id}",
                           code="REPORT_DEFINITION_NOT_FOUND", status=404)
        if shared_with not in SUPPORTED_SHARED_WITH:
            raise PcsError(
                f"shared_with 只支持 {sorted(SUPPORTED_SHARED_WITH)}",
                code="REPORT_DEFINITION_INVALID", status=400,
            )
        validate_definition_json(definition_json)
        await self._reject_duplicate(project_id, name, exclude=def_id)
        definition_json = align_with_columns(
            definition_json, max_rows=max_rows, output_format=output_format)

        was_published = row.status == "PUBLISHED"
        row.project_id = project_id
        row.name = name
        row.category = category
        row.description = description
        row.definition_json = definition_json
        row.output_format = output_format
        row.max_rows = max_rows
        row.shared_with = shared_with
        if was_published:
            row.version = bump_patch(row.version)
            row.status = "DRAFT"
        await self.db.flush()
        # ⚠️ 必须显式 refresh。UPDATE flush 之后，服务端生成的列
        # （`updated_at` = onupdate=func.now()）被 SQLAlchemy 标记为 expired，
        # 不 refresh 的话，调用方读 row.updated_at 就是一次隐式 SELECT
        # 落在同步上下文里 → MissingGreenlet → 500。
        #
        # ⚠️ **不是 `expire_on_flush` 能解决的**（2026-10-13 实测，见
        # tests/db/test_server_generated_columns.py）：`onupdate=func.now()`
        # 的值由数据库算出，SQLAlchemy 无从知道，flush 后**必定**标记
        # expired，设 `expire_on_flush=False` 也一样炸。refresh 是唯一解。
        #
        # ⚠️ 改 conftest 的 fixture 不算修：db_session 恰好设了
        # expire_on_flush=False，会得到「测试绿、生产红」——
        # **替身比被测物更宽容**，缺陷就是这么活下来的。
        await self.db.refresh(row)
        return row

    async def publish(self, *, def_id: uuid.UUID) -> ReportDefinition:
        """DRAFT → PUBLISHED。权限在**端点层**用 `require_roles` 判。

        幂等不做：重复发布是 409 而不是静默成功 —— 调用方（前端重试、
        脚本重复执行）需要知道这次到底改没改状态。
        """
        row = await self.db.get(ReportDefinition, def_id)
        if row is None:
            raise PcsError(f"报表定义不存在：{def_id}",
                           code="REPORT_DEFINITION_NOT_FOUND", status=404)
        if row.status == "PUBLISHED":
            raise PcsError("该定义已发布", code="REPORT_DEFINITION_STATE", status=409)
        if row.status == "OBSOLETE":
            raise PcsError("已作废的定义不能重新发布",
                           code="REPORT_DEFINITION_OBSOLETE", status=409)
        row.status = "PUBLISHED"
        await self.db.flush()
        await self.db.refresh(row)   # 见 update() 的同款注释
        return row

    async def obsolete(self, *, def_id: uuid.UUID) -> ReportDefinition:
        """PUBLISHED → OBSOLETE（作废）。

        作废后仍可按 ID 查到（审计追溯），但不在默认列表、不再可执行。
        DRAFT 直接作废是允许的：草稿只有创建人看得见，直接删更合理，
        但统一走一个状态机比「DRAFT 就得删、PUBLISHED 就得作废」两套规则
        少一类边界。
        """
        row = await self.db.get(ReportDefinition, def_id)
        if row is None:
            raise PcsError(f"报表定义不存在：{def_id}",
                           code="REPORT_DEFINITION_NOT_FOUND", status=404)
        if row.status == "OBSOLETE":
            raise PcsError("该定义已作废", code="REPORT_DEFINITION_STATE", status=409)
        row.status = "OBSOLETE"
        await self.db.flush()
        await self.db.refresh(row)
        return row

    async def _check_demo_limit(self) -> None:
        """演示版定义数上限（SPEC §3.2.2(8)，SUP-006）。

        计数是**全库**而不是「按用户」：演示版是给外部看的一个受限部署，
        按用户限 3 个等于每人 3 个 —— 限制形同虚设。所以列表端点返回的
        个数与这里的判定口径必须一致，故直接数库里的行。
        """
        from app.services.report import watermark

        if not get_settings().report_demo_mode:
            return
        n = len((await self.db.execute(
            select(ReportDefinition.def_id))).all())
        watermark.check_demo_definition_limit(n)

    async def _reject_duplicate(self, project_id: uuid.UUID | None, name: str,
                                *, exclude: uuid.UUID | None) -> None:
        stmt = select(ReportDefinition).where(
            ReportDefinition.project_id == project_id,
            ReportDefinition.name == name,
        )
        if exclude is not None:
            stmt = stmt.where(ReportDefinition.def_id != exclude)
        if (await self.db.execute(stmt)).scalars().first() is not None:
            raise PcsError(f"同名报表定义已存在：{name}",
                           code="REPORT_DEFINITION_DUPLICATE", status=409)

    @staticmethod
    def _can_see(row: ReportDefinition, user_id: uuid.UUID) -> bool:
        if row.created_by == user_id:
            return True
        return row.status == "PUBLISHED" and row.shared_with == "ALL_USERS"


__all__ = ["DefinitionService", "DEFINITION_STATUSES", "SUPPORTED_SHARED_WITH",
           "bump_patch", "validate_definition_json", "align_with_columns",
           "visible_clause"]