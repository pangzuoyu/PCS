"""AD 同步（SPEC P9A-USR-001/002/003，ADR-0046 §⑤）。

一次同步做三件事：
1. **建/更**：`users` 行按目录条目 upsert（姓名/邮箱/部门 + 组映射出的角色）
2. **离职**：目录里已不存在、且当前 ACTIVE 的用户 → `status=DISABLED` + `tv += 1`
3. 全部动作写 `USER_SYNC` 审计

## ⚠️ 两条安全属性（写错就是生产事故）

同步的「离职」判定是**减法**（不在目录里 ⇒ 离职）。减法遇到异常输入会变成
「全员离职」—— 一次 filter 配错，全公司被停用且令牌全部作废。

所以：

| 情况 | 处置 | 理由 |
|---|---|---|
| 枚举抛异常（目录连不上 / 凭据错） | `ok=False`，**不做任何写入** | 连不上 ≠ 没人 |
| 枚举结果为空 | `skipped_empty=True`，**不做任何写入** | 空目录 = filter/base_dn 配错 |

两条的共同形状：**只有「成功枚举到一个非空目录」才允许执行离职判定。**
这不是防御性编程的口头禅，是这块代码唯一的正确性前提。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import AuditAction, UserStatus
from app.models.project import User
from app.services.ldap_client import DirectoryUser, enumerate_users, resolve_role
from app.services.token_issuer import derive_user_id

logger = logging.getLogger(__name__)


def ldap_sync_configured() -> bool:
    """服务账号是否已配置。未配置时同步端点返 503、cron no-op。"""
    from app.core.config import get_settings

    return bool(get_settings().ldap_bind_dn)


@dataclass(frozen=True)
class SyncResult:
    """一次同步的结果。`ok=False` 表示**什么都没做**（不是「做了但失败」）。"""

    ok: bool
    created: int = 0
    updated: int = 0
    departed: int = 0
    skipped_empty: bool = False
    error: str | None = None

    def as_dict(self) -> dict[str, object]:
        return {
            "ok": self.ok,
            "created": self.created,
            "updated": self.updated,
            "departed": self.departed,
            "skipped_empty": self.skipped_empty,
            "error": self.error,
        }


async def sync_users(db: AsyncSession) -> SyncResult:
    """执行一次全量同步。

    幂等：重复执行同一目录两次，第二次 `created=0 updated=N departed=0`。

    Raises:
        PcsError: 服务账号未配置 —— 调用方**不要**吞掉，要让端点返 503。
    """
    from app.core.config import get_settings

    settings = get_settings()
    if not settings.ldap_bind_dn:
        from app.core.errors import PcsError

        raise PcsError(
            code="LDAP_SYNC_NOT_CONFIGURED",
            message="LDAP_BIND_DN 未配置，AD 同步不可用",
            status=503,
        )

    try:
        directory = list(enumerate_users())
    except Exception as e:  # noqa: BLE001 — 任何失败都不许推进离职判定
        logger.warning("AD 同步失败（枚举异常），本次跳过离职判定: %s", e)
        return SyncResult(ok=False, error=str(e))

    if not directory:
        # 空目录几乎总是 filter / base_dn 配错。当成「全员离职」是灾难。
        logger.warning("AD 同步枚举到 0 个用户 —— 疑似 filter/base_dn 配错，本次跳过离职判定")
        return SyncResult(ok=True, skipped_empty=True, error="empty_directory")

    from app.services.audit_service import AuditService

    audit = AuditService(db)
    existing = {
        u.username: u
        for u in (await db.execute(select(User))).scalars().all()
    }
    seen: set[str] = set()
    created = updated = departed = 0

    for entry in directory:
        seen.add(entry.username)
        row = existing.get(entry.username)
        if row is None:
            row = User(
                user_id=derive_user_id(entry.username),
                username=entry.username,
                display_name=entry.display_name or entry.username,
                email=entry.email,
                department=entry.department,
                ad_groups=list(entry.groups),
                roles=[_role_of(entry)],
                status=UserStatus.ACTIVE.value,
            )
            db.add(row)
            created += 1
            continue
        changed = _apply(row, entry)
        if changed:
            updated += 1

    for username, row in existing.items():
        if username in seen or row.status == UserStatus.DISABLED.value:
            continue
        row.status = UserStatus.DISABLED.value
        row.token_version += 1
        departed += 1
        await audit.write(
            action=AuditAction.USER_DISABLED,
            resource_type="USER",
            resource_id=row.user_id,
            user_id=None,  # 同步是系统动作，无人触发
            detail={
                "username": username,
                "reason": "AD_SYNC_NOT_FOUND",
                "token_version": row.token_version,
            },
        )

    await audit.write(
        action=AuditAction.USER_SYNC,
        resource_type="USER",
        resource_id=None,
        user_id=None,
        detail={"created": created, "updated": updated, "departed": departed},
    )
    await db.commit()
    return SyncResult(ok=True, created=created, updated=updated, departed=departed)


def _role_of(entry: DirectoryUser) -> str:
    """组 → 角色。映射不到时 `resolve_role` 自行 fail-closed（production）。"""
    try:
        return resolve_role(entry.groups)
    except Exception as e:  # noqa: BLE001 — 映射不到不该让整次同步崩掉
        logger.warning("用户 %s 的 LDAP 组未映射到角色: %s", entry.username, e)
        return "DESIGNER"


def _apply(row: User, entry: DirectoryUser) -> bool:
    """把目录条目写进行；返回是否有改动。"""
    changed = False
    for attr, value in (
        ("display_name", entry.display_name or row.display_name),
        ("email", entry.email),
        ("department", entry.department),
        ("ad_groups", list(entry.groups)),
        ("roles", [_role_of(entry)]),
    ):
        if value is not None and getattr(row, attr) != value:
            setattr(row, attr, value)
            changed = True
    return changed


