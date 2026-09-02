"""ConfigService — 配置资产 CRUD + 版本 fork + diff（Task 2.8）。

薄包装：
- `create_asset`：插入一行 DRAFT ConfigAsset，并创建首个 DRAFT ConfigVersion。
- `create_version`：基于现有 asset 追加新 ConfigVersion，刷新
  `asset.current_version` 字符串列（P1 SUP-001 §2.1 锁定）。
- `fork_from_published`：仅当 asset 处于 PUBLISHED 时复制其当前 version 为
  新 DRAFT ConfigVersion（parent_version_id 指向源）。
- `diff_versions`：基于 ConfigVersion.content_json 做 shallow dict diff，
  返回 {added, removed, changed} 三段式。

实现注意（与 brief 偏差 / 防御性）：
1. `ConfigVersion` 无 `formula_version` 列（P1 schema 真实结构 — Task 2.7.1
   已验证），本服务因此**不写** formula_version 字段；调用方如需版本指纹
   应使用 FormulaEngine.compute_version_hash 单独持久化或放在 content_json。
2. `asset.current_version` 是 String(50) 列，不是 FK 关系；本服务在
   `create_version` / `fork_from_published` 后把字符串列更新到新 version_code。
3. `create_asset` 默认建立首个 ConfigVersion（version_code="v1"）——
   `sample_draft_asset` 测试 fixture 也是这样做的（保持 DRAFT 状态必有 v1）。
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.config_domain import ConfigAsset, ConfigVersion
from app.models.enums import AuditAction, ConfigStatus
from app.services.audit_service import AuditService


class AssetNotFoundError(Exception):
    """查不到指定 ConfigAsset 时抛出。"""


class VersionNotFoundError(Exception):
    """查不到指定 ConfigVersion 时抛出。"""


class ConfigService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.audit = AuditService(session)

    # ------------------------------------------------------------------
    # Create
    # ------------------------------------------------------------------

    async def create_asset(
        self,
        *,
        category: str,
        name: str,
        actor: UUID,
    ) -> ConfigAsset:
        """插入一行 DRAFT ConfigAsset + 首个 ConfigVersion。

        返回 ConfigAsset；首个 version_code="v1"。
        """
        asset = ConfigAsset(
            category=category,
            name=name,
            current_version="v1",
            status=ConfigStatus.DRAFT.value,
        )
        self.session.add(asset)
        await self.session.flush()
        version = ConfigVersion(
            asset_id=asset.asset_id,
            version_code="v1",
            content_json={},
            status=ConfigStatus.DRAFT.value,
        )
        self.session.add(version)
        await self.session.flush()
        # 链接 via string column（schema 真实结构）
        asset.current_version = version.version_code
        await self.session.flush()
        await self.audit.write(
            user_id=actor,
            action=AuditAction.CONFIG_ASSET_CREATED,
            resource_type="CONFIG",
            resource_id=str(asset.asset_id),
            detail={"category": category, "name": name},
        )
        return asset

    async def create_version(
        self,
        asset: ConfigAsset,
        *,
        content_json: dict[str, Any],
        formula_version: str | None = None,
        actor: UUID,
    ) -> ConfigVersion:
        """为现有 asset 追加新 ConfigVersion；新 version_code 自 v1/v2/v3... 续号。

        `formula_version` 参数保留兼容接口（brief 第 4 段要求），但不写入 DB
        列（model 无该列）；调用方若需可写入 content_json。
        """
        # 计算下一个 version_code：max(existing) + 1
        existing = (
            await self.session.execute(
                select(ConfigVersion.version_code)
                .where(ConfigVersion.asset_id == asset.asset_id)
            )
        ).scalars().all()
        next_idx = len(existing) + 1
        new_code = f"v{next_idx}"
        # parent 指向当前 current_version 行
        current_row = None
        if asset.current_version:
            current_row = (
                await self.session.execute(
                    select(ConfigVersion).where(
                        ConfigVersion.asset_id == asset.asset_id,
                        ConfigVersion.version_code == asset.current_version,
                    )
                )
            ).scalar_one_or_none()
        new_version = ConfigVersion(
            asset_id=asset.asset_id,
            version_code=new_code,
            parent_version_id=current_row.version_id if current_row else None,
            content_json=content_json,
            status=ConfigStatus.DRAFT.value,
        )
        self.session.add(new_version)
        await self.session.flush()
        asset.current_version = new_code
        await self.session.flush()
        await self.audit.write(
            user_id=actor,
            action=AuditAction.CONFIG_VERSION_CREATED,
            resource_type="CONFIG",
            resource_id=str(asset.asset_id),
            detail={
                "version_id": str(new_version.version_id),
                "version_code": new_code,
                "formula_version": formula_version,
            },
        )
        return new_version

    async def fork_from_published(
        self,
        asset: ConfigAsset,
        *,
        change_note: str | None = None,
        formula_version: str | None = None,
        actor: UUID,
    ) -> ConfigVersion:
        """从 PUBLISHED asset 的当前版本 fork 出新 DRAFT ConfigVersion。

        要求：asset.status == PUBLISHED（caller 负责检查；本方法不抛业务异常，
        仅依赖 ConfigStateMachine 在后续转移时兜底）。
        """
        # 取当前 PUBLISHED version
        current_row = (
            await self.session.execute(
                select(ConfigVersion).where(
                    ConfigVersion.asset_id == asset.asset_id,
                    ConfigVersion.version_code == asset.current_version,
                )
            )
        ).scalar_one_or_none()
        # 计算下一个 version_code
        existing = (
            await self.session.execute(
                select(ConfigVersion.version_code)
                .where(ConfigVersion.asset_id == asset.asset_id)
            )
        ).scalars().all()
        next_idx = len(existing) + 1
        new_code = f"v{next_idx}"
        new_version = ConfigVersion(
            asset_id=asset.asset_id,
            version_code=new_code,
            parent_version_id=current_row.version_id if current_row else None,
            change_note=change_note,
            content_json=dict(current_row.content_json or {}) if current_row else {},
            status=ConfigStatus.DRAFT.value,
        )
        self.session.add(new_version)
        await self.session.flush()
        asset.current_version = new_code
        # 资产回到 DRAFT（fork 出来就是修订起点）
        asset.status = ConfigStatus.DRAFT.value
        await self.session.flush()
        await self.audit.write(
            user_id=actor,
            action=AuditAction.CONFIG_VERSION_CREATED,
            resource_type="CONFIG",
            resource_id=str(asset.asset_id),
            detail={
                "forked_from": (
                    str(current_row.version_id) if current_row else None
                ),
                "version_code": new_code,
                "change_note": change_note,
                "formula_version": formula_version,
            },
        )
        return new_version

    # ------------------------------------------------------------------
    # Diff
    # ------------------------------------------------------------------

    async def diff_versions(
        self,
        asset_id: UUID,
        v1_id: UUID,
        v2_id: UUID,
        *,
        actor: UUID | None = None,
    ) -> dict[str, Any]:
        """两版本 content_json 的 shallow diff（顶层 key 集合对比）。

        返回 {added, removed, changed}：
        - added  : v2 有 v1 没有的 key（值取 v2）
        - removed: v1 有 v2 没有的 key（值取 v1）
        - changed: 两版本都有但值不同的 key（值取 v2）
        """
        v1 = await self.session.get(ConfigVersion, v1_id)
        v2 = await self.session.get(ConfigVersion, v2_id)
        if v1 is None or v2 is None:
            raise VersionNotFoundError(
                f"未找到 v1={v1_id} 或 v2={v2_id}"
            )
        # 防御：跨 asset 对比无意义，但 caller 已保证 asset_id 一致；这里仅
        # 落库 audit 时用 asset_id，不做硬断言。
        a = v1.content_json or {}
        b = v2.content_json or {}
        added = {k: b[k] for k in b.keys() - a.keys()}
        removed = {k: a[k] for k in a.keys() - b.keys()}
        changed = {k: b[k] for k in a.keys() & b.keys() if a[k] != b[k]}
        if actor is not None:
            await self.audit.write(
                user_id=actor,
                action=AuditAction.CONFIG_VERSION_DIFF_VIEWED,
                resource_type="CONFIG",
                resource_id=str(asset_id),
                detail={
                    "v1": str(v1_id),
                    "v2": str(v2_id),
                    "added_keys": list(added.keys()),
                    "removed_keys": list(removed.keys()),
                    "changed_keys": list(changed.keys()),
                },
            )
        return {"added": added, "removed": removed, "changed": changed}


__all__ = [
    "AssetNotFoundError",
    "ConfigService",
    "VersionNotFoundError",
]