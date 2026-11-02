"""系统参数读写（§7.20.1 · T4）。

⚠️ **原子性**（委员会硬约束 1）：批量保存是**一次事务** ⇒ 任一键失败 ⇒
**全部不落** ⇒ 不留「半改」状态。实现上：先校验全部键存在，再一次性写。

⚠️ **已知限制（P2-3）**：系统参数**只能改已有键的值，不能新增键**。新增键需要
改代码（`DEFAULT_SETTINGS` 清单）+ 重启。理由：允许管理员新增键会导致
键名拼写错误污染表 —— **键的集合由开发者控制，值由管理员控制**。
（同一条限制写进 SPEC §7.20.1。）

⚠️ `updated_at` 是 `onupdate=func.now()` —— **服务端**表达式 ⇒ flush 之后 ORM
上的值是旧的（甚至过期）⇒ 端点层负责 refresh 读回（见 `api/v1/system_settings.py`）。
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import PcsError
from app.models.enums import AuditAction
from app.models.system import SystemSetting

#: 默认参数清单 —— **键的集合由开发者控制**（见模块 docstring 的 P2-3）。
#: `stream.batch_submit_limit` 在本批**无消费者**（批量提交在 P9B-3b），
#: 提前 seed 比 P9B-3b 再补省事（seed 幂等 ⇒ 多一个键零成本），
#: 但前端页面**必须能编辑它**（否则管理员看到「有配置但改不了」会困惑）。
DEFAULT_SETTINGS: list[dict[str, Any]] = [
    {"key": "session.timeout_minutes", "value": 30, "description": "会话超时（分钟）"},
    {"key": "notification.retention_days", "value": 30, "description": "已读通知保留天数"},
    {"key": "edit_lock.ttl_minutes", "value": 30, "description": "编辑锁有效期（分钟）"},
    {"key": "edit_lock.renew_enabled", "value": True, "description": "编辑锁自动续期"},
    {"key": "record.self_check_allowed", "value": False, "description": "是否允许设计兼任校核"},
    {"key": "equip_list.auto_sync_enabled", "value": True, "description": "CHECKED 触发设备表同步"},
    {
        "key": "stream.batch_submit_limit",
        "value": 100,
        "description": "物流批量提交上限（P9B-3b 用）",
    },
]


async def seed_defaults(db: AsyncSession) -> list[str]:
    """幂等：缺失则写入，存在则跳过（**不覆盖**管理员改过的值）。

    Returns:
        本次**新增**的键（空列表 = 已是最新状态）。

    ⚠️ 自己 commit —— 启动钩子的 session 用完即关，不提交等于回滚。
    """
    existing = set(
        (await db.execute(select(SystemSetting.setting_key))).scalars().all()
    )
    created: list[str] = []
    for item in DEFAULT_SETTINGS:
        if item["key"] in existing:
            continue
        db.add(
            SystemSetting(
                setting_key=item["key"],
                setting_value_json=item["value"],
                description=item["description"],
            )
        )
        created.append(item["key"])
    if created:
        await db.commit()
    return created


async def list_all(db: AsyncSession) -> list[SystemSetting]:
    """列出全部系统参数（按键排序，页面上顺序稳定）。"""
    rows = (
        await db.execute(select(SystemSetting).order_by(SystemSetting.setting_key))
    ).scalars()
    return list(rows)


async def update_batch(
    db: AsyncSession,
    values: dict[str, Any],
    *,
    actor_user_id: uuid.UUID | None,
) -> list[SystemSetting]:
    """批量改值 —— **全改或全不改**。

    步骤：
    1. 一次 SELECT 取全部目标行；
    2. **缺任何一个键 ⇒ 抛 404**（**在任何写入之前** ⇒ 天然原子）；
    3. 全部命中 ⇒ 逐个赋值 + 一次 flush + **一条**审计。

    Raises:
        PcsError: 404 —— 键不存在。
    """
    keys = list(values.keys())
    if not keys:
        return []

    rows = (
        await db.execute(select(SystemSetting).where(SystemSetting.setting_key.in_(keys)))
    ).scalars()
    found = {row.setting_key: row for row in rows}
    missing = [k for k in keys if k not in found]
    if missing:
        raise PcsError(
            code="SYSTEM_SETTING_NOT_FOUND",
            message=f"系统参数不存在：{', '.join(missing)}",
            status=404,
            detail={"missing": missing},
        )

    before = {k: found[k].setting_value_json for k in keys}
    for key in keys:
        found[key].setting_value_json = values[key]
    await db.flush()

    from app.services.audit_service import AuditService

    await AuditService(db).write(
        action=AuditAction.SYSTEM_SETTINGS_UPDATED,
        resource_type="SYSTEM_SETTINGS",
        resource_id=None,
        user_id=actor_user_id,
        detail={"keys": keys, "before": before},
    )
    return [found[k] for k in keys]
