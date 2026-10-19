"""AD 同步的 ARQ 任务（SPEC P9A-USR-002 的「定时任务」）。

⚠️ **未配置时必须 no-op + 一条 WARN**，不能抛：
未配置是**常态**（多数部署没有服务账号），让 cron 每晚抛一次只会污染日志，
让人对这条任务的告警脱敏 —— 真正的目录故障也就被淹没了。
`sync_users` 内部对未配置抛 `PcsError`，由这里翻译成 no-op。
"""

from __future__ import annotations

import logging

from app.services.ad_sync import ldap_sync_configured, sync_users

logger = logging.getLogger(__name__)


async def sync_ad_users(ctx: dict) -> dict[str, object]:
    """每日凌晨跑一次全量 AD 同步（ARQ cron 触发）。

    Args:
        ctx: ARQ context，必须带 `session_factory`（`worker._db_session` 的来源）。

    Returns:
        `SyncResult.as_dict()`；未配置时返回 `{"ok": False, "skipped": "not_configured"}`。
    """
    if not ldap_sync_configured():
        logger.warning("AD 同步跳过：LDAP_BIND_DN 未配置")
        return {"ok": False, "skipped": "not_configured"}

    factory = ctx["session_factory"]
    async with factory() as session:
        result = await sync_users(session)
    logger.info("AD 同步完成: %s", result.as_dict())
    return result.as_dict()
