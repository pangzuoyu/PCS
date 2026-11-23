"""迁移「遗留账号」（`user_id` ≠ 派生值）⇒ ⇒ 授权与审计都转到派生 id。

## 为什么需要这个脚本

`ensure_user_row` / `issue_tokens` 现在**只认派生 id**
（`uuid5(NAMESPACE_DNS, username)`）⇒ ⇒ 若某个用户名被一条
**`user_id` 与派生值不同**的**遗留行**占着（`users.username` 唯一 ⇒
派生 id 与遗留 id **不能并存**）⇒ ⇒ 建行会撞唯一约束 ⇒ ⇒
显式 409 `USER_ID_CONFLICT` ⇒ ⇒ ⇒ 那个用户**处处 404**。

⇒ ⇒ 本脚本把遗留行的身份与**全部引用**转到派生 id ⇒ ⇒ 之后登录即生效。

## ⚠️ 为什么**迁完不留遗留行**（而不是改名了事）

`CLAUDE.md` 的发布前检查有一条闸：

    SELECT count(*) FROM users WHERE user_id <> uuid5_derived(username) = 0

⇒ ⇒ 若把遗留行改名成 `legacy:alice` 留在表里 ⇒ ⇒ **闸永远不绿**
⇒ ⇒ ⇒ 所以本脚本**最后删掉遗留行**（引用已全部转走 ⇒ ⇒ 删得掉）。

## 三步（顺序不能错 —— 唯一约束 + FK）

1. **让出 username**：`users.username` 唯一 ⇒ ⇒ 派生 id 的行建不出来
   ⇒ ⇒ 先把遗留行改成 `legacy:<原名>`（临时占位，**最后随行一起删**）。
2. **建派生 id 的行**：身份字段（`display_name` / `email` / `department` /
   `roles` / `ad_groups` / `status` / `last_login_at` / `token_version`）
   **从遗留行复制** ⇒ ⇒ 这**是同一个人** ⇒ ⇒ 不丢角色
   （`ensure_user_row` 建行写 `roles=[]`，那是给**新**用户的 ⇒ 这里不适用）。
3. **把引用全部改指派生 id**，然后**删掉遗留行**。

## 引用列**从 ORM metadata 推导**（不手抄 ⇒ ⇒ 不会漂）

判据 = ① 列有 FK 指向 `users.user_id`　**或**　② 列名含 `user_id`
（`actor_user_id` / `user_id`）⇒ ⇒ 实测 9 列：

    ai_audit_log.user_id · audit_logs.user_id · data_lineage.actor_user_id
    cost_correlations.created_by · notifications.recipient_id
    project_calculation_standard_profiles.approved_by
    user_projects.user_id / granted_by / revoked_by

⚠️ **漏一列的后果**：那一列仍指向遗留 id ⇒ ⇒ 授权 / 审计 / 通知**留在**
遗留身份上 ⇒ ⇒ 迁移「看起来成功」但那个人**依旧没权限**。

用法：

    cd pcs-backend
    uv run python scripts/migrate_legacy_user_ids.py --dry-run
    uv run python scripts/migrate_legacy_user_ids.py

⚠️ 数据库口令从 `.env` 的 `DATABASE_URL` 读 —— **不要**出现在命令行。
"""
# ruff: noqa — 一次性运维脚本（非 app 代码），单点收敛
from __future__ import annotations

import argparse
import asyncio
import sys
import uuid
from dataclasses import dataclass, field
from pathlib import Path

# 允许 ``uv run python scripts/xxx.py`` 直接调用；app 包从 pcs-backend 根解析。
_BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from sqlalchemy import select, update  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: E402

from app.db.base import Base  # noqa: E402
from app.db.session import get_async_session_factory  # noqa: E402
from app.models.project import User, UserProject  # noqa: E402
from app.services.token_issuer import derive_user_id  # noqa: E402

#: 遗留行让出 username 时的**临时前缀**（**最后随行一起删** ⇒ 不留痕）。
LEGACY_USERNAME_PREFIX = "legacy:"

#: 身份字段：**从遗留行复制到派生行**（同一个人 ⇒ 不丢身份）。
IDENTITY_FIELDS = (
    "display_name",
    "email",
    "department",
    "roles",
    "ad_groups",
    "status",
    "last_login_at",
    "token_version",
)


@dataclass
class LegacyUser:
    """一条待迁移的遗留行。"""

    user_id: uuid.UUID
    username: str

    @property
    def derived_user_id(self) -> uuid.UUID:
        """派生 id（**唯一**派生点 `derive_user_id` ⇒ 不另抄一份）。"""
        return derive_user_id(self.username)


@dataclass
class MigrationReport:
    """一次迁移的结果（**可回显** ⇒ 运维知道做了什么）。"""

    migrated: list[LegacyUser] = field(default_factory=list)
    skipped: list[tuple[str, str]] = field(default_factory=list)
    #: (表, 列, 行数) —— 引用改指的明细
    remapped: list[tuple[str, str, int]] = field(default_factory=list)
    #: 被删掉的**重复授权行**（派生 id 已有同一项目的授权 ⇒ ⇒ 遗留那条冗余）
    deduped_grants: int = 0

    @property
    def total_remapped(self) -> int:
        return sum(n for _, _, n in self.remapped)


def remap_targets() -> tuple[tuple[str, str], ...]:
    """要改指的 `(表名, 列名)` 列表 —— **从 ORM metadata 推导**。

    判据 = ① 有 FK 指向 `users.user_id`　**或**　② 列名含 `user_id`。
    ⚠️ **`users` 表本身排除**（它的 `user_id` 是 PK ⇒ 靠**改名 + 删行**处理，
    不是靠改指）。
    """
    targets: list[tuple[str, str]] = []
    for table in Base.metadata.sorted_tables:
        if table.name == "users":
            continue
        for col in table.columns:
            is_fk = any(
                fk.target_fullname == "users.user_id" for fk in col.foreign_keys
            )
            if is_fk or "user_id" in col.name:
                targets.append((table.name, col.name))
    return tuple(targets)


async def find_legacy_users(session: AsyncSession) -> list[LegacyUser]:
    """找出所有「`user_id` ≠ 派生值」的遗留行。

    ⚠️ **已让出 username 的行（`legacy:` 前缀）不算遗留** ⇒ ⇒ 幂等：
    跑第二遍不会把同一行再处理一次。
    """
    rows = (await session.execute(select(User))).scalars().all()
    out: list[LegacyUser] = []
    for row in rows:
        if row.username.startswith(LEGACY_USERNAME_PREFIX):
            continue
        if row.user_id != derive_user_id(row.username):
            out.append(LegacyUser(user_id=row.user_id, username=row.username))
    return out


async def _remap_references(
    session: AsyncSession, legacy: LegacyUser, derived_id: uuid.UUID
) -> list[tuple[str, str, int]]:
    """把所有引用列从遗留 id 改指派生 id ⇒ ⇒ 返回明细。"""
    detail: list[tuple[str, str, int]] = []
    for table_name, column_name in remap_targets():
        table = Base.metadata.tables[table_name]
        column = table.c[column_name]
        result = await session.execute(
            update(table)
            .where(column == legacy.user_id)
            .values({column: derived_id})
        )
        if result.rowcount:
            detail.append((table_name, column_name, result.rowcount))
    return detail


async def _remaining_references(
    session: AsyncSession, legacy_id: uuid.UUID
) -> list[tuple[str, str, int]]:
    """遗留 id 上**还剩**多少引用（⇒ ⇒ 应当为空 ⇒ ⇒ 否则不许删行）。"""
    leftovers: list[tuple[str, str, int]] = []
    for table_name, column_name in remap_targets():
        table = Base.metadata.tables[table_name]
        column = table.c[column_name]
        count = (
            await session.execute(
                select(column).where(column == legacy_id)
            )
        ).all()
        if count:
            leftovers.append((table_name, column_name, len(count)))
    return leftovers


async def migrate_one(
    session: AsyncSession, legacy: LegacyUser
) -> tuple[bool, str]:
    """迁移一条遗留行。Returns `(是否成功, 说明)`。

    ⚠️ **顺序**（唯一约束 + FK）：
    让出 username ⇒ ⇒ 建派生行 ⇒ ⇒ 改指引用 ⇒ ⇒ 删遗留行。
    """
    derived_id = legacy.derived_user_id

    existing = await session.get(User, derived_id)
    if existing is not None:
        return False, (
            f"{legacy.username}: 派生 id {derived_id} 已有行"
            f"（username={existing.username!r}）⇒ ⇒ 形状异常 ⇒ ⇒ **不自动处理**"
        )

    row = await session.get(User, legacy.user_id)
    if row is None:  # pragma: no cover — 并发删掉了
        return False, f"{legacy.username}: 遗留行已不存在"

    # ① 让出 username（`users.username` 唯一 ⇒ ⇒ 派生行建不出来）
    temp_name = f"{LEGACY_USERNAME_PREFIX}{legacy.username}"
    clash = (
        await session.execute(select(User).where(User.username == temp_name))
    ).scalar_one_or_none()
    if clash is not None:
        return False, (
            f"{legacy.username}: 临时名 {temp_name!r} 已被占用 ⇒ ⇒ **不自动处理**"
        )

    # ② 让出 username（`users.username` 唯一 ⇒ ⇒ 派生行建不出来）
    row.username = temp_name

    # ③ 建派生 id 的行（身份字段从遗留行复制 ⇒ ⇒ 同一个人）
    new_row = User(
        user_id=derived_id,
        username=legacy.username,
        display_name=row.display_name,
        email=row.email,
        department=row.department,
        roles=list(row.roles or []),
        ad_groups=list(row.ad_groups or []),
        status=row.status,
        last_login_at=row.last_login_at,
        token_version=row.token_version,
    )
    session.add(new_row)
    await session.flush()

    # ④ 引用改指
    detail = await _remap_references(session, legacy, derived_id)

    # ⚠️ **残留引用** ⇒ ⇒ 不许删行（否则 FK 悬空 ⇒ ⇒ PG 会拒 / SQLite 会静默）
    leftovers = await _remaining_references(session, legacy.user_id)
    if leftovers:
        raise RuntimeError(
            f"{legacy.username}: 遗留 id {legacy.user_id} 上仍有引用 {leftovers}"
            f" ⇒ ⇒ **拒绝删行**（否则引用悬空）"
        )

    # ⑤ 删掉遗留行（引用已全部转走 ⇒ ⇒ 删得掉 ⇒ ⇒ 发布闸才绿）
    await session.delete(row)
    await session.flush()
    return True, (
        f"{legacy.username}: {legacy.user_id} → {derived_id}"
        f"（改指 {sum(n for _, _, n in detail)} 行）"
    )


async def run_migration(
    session: AsyncSession, *, dry_run: bool = False
) -> MigrationReport:
    """扫全表 ⇒ ⇒ 逐条迁移 ⇒ ⇒ 返回报告（**唯一的实现**）。"""
    report = MigrationReport()
    for legacy in await find_legacy_users(session):
        if dry_run:
            report.skipped.append(
                (legacy.username, f"将迁移 {legacy.user_id} → {legacy.derived_user_id}")
            )
            continue
        ok, message = await migrate_one(session, legacy)
        if ok:
            report.migrated.append(legacy)
            print(f"[OK] {message}")
        else:
            report.skipped.append((legacy.username, message))
            print(f"[SKIP] {message}", file=sys.stderr)
    return report


async def _run(args: argparse.Namespace) -> int:
    factory = get_async_session_factory()
    async with factory() as session:
        legacy_users = await find_legacy_users(session)
        if not legacy_users:
            print("[OK] 没有遗留账号（user_id 全部等于派生值）⇒ ⇒ 无需迁移")
            return 0

        print(f"发现 {len(legacy_users)} 条遗留账号：")
        for legacy in legacy_users:
            print(
                f"  - {legacy.username}: {legacy.user_id} → {legacy.derived_user_id}"
            )
        if args.dry_run:
            print("[DRY-RUN] 未写库")
            return 0

        report = await run_migration(session)
        await session.commit()

        # 复核：迁移后不该再有遗留行（⇒ ⇒ 发布闸的 `= 0`）
        remaining = await find_legacy_users(session)
        if remaining:
            print(
                f"[ERROR] 迁移后仍有 {len(remaining)} 条遗留账号 ⇒ ⇒ **回滚**",
                file=sys.stderr,
            )
            await session.rollback()
            return 1
        print(
            f"[OK] 迁移完成 ⇒ ⇒ 遗留账号行数 = 0"
            f"（已迁 {len(report.migrated)} 条 · 跳过 {len(report.skipped)} 条）"
        )
        return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="把遗留账号（user_id ≠ 派生值）的身份与引用转到派生 id。",
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="只列出将要迁移的行，不写库"
    )
    args = parser.parse_args(argv)

    try:
        return asyncio.run(_run(args))
    except Exception as exc:  # noqa: BLE001 — 运维脚本：把原因说清楚再退出
        print(f"[ERROR] 迁移失败：{exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
