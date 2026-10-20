"""编辑锁：Redis 层的**悲观**互斥（ADR-0048 §①~⑤）。

## 它是什么，不是什么

- **是**：体验层。让他人正在改这版**可见**（「张三 正在编辑」）。
- **不是**：正确性保证。并发覆盖由 **DB 层**（`record_hash` 乐观比对，
  ADR-0048 §⑥，D2 落地）拦住。

⇒ 本模块**只碰 Redis**。它**没有 session 参数、也不 import 任何
ORM / db 模块** ⇒ 「判定时顺手查了库」在结构上不可能发生
（守卫：`tests/services/test_edit_lock.py::test_acquire_does_not_consult_database`）。
这不只是性能考量 —— 锁必须在 **DB 挂掉时仍然可用**（那时正是最需要
「别同时改」这个提示的时候）。

## 存储形状（§①）

key = `lock:edit:{record_type}:{record_id}`，value = **hash**：

| field | 含义 |
|---|---|
| `user_id` | 持有者 |
| `username` | 持有者显示名（**免掉一次 DB 解析** —— 锁判定不查库） |
| `acquired_at` | 获取时刻（ISO8601） |

用 hash 而不是裸字符串，是因为续期要**只比较 user_id**（compare-and-expire）
而不能整串替换 —— 整串替换会把「获取时刻」也换掉，续期就不再是续期了。

## 三个操作的原子性

| 操作 | 语义 | 实现 |
|---|---|---|
| acquire | 存在即拒 | Lua：`exists` → `hset` + `expire`（整体原子） |
| renew | **值是我的**才重置 TTL | Lua：`hget user_id` == 我 → `expire` |
| release | **值是我的**才删 | Lua：`hget user_id` == 我 → `del` |

⚠️ renew / release **必须原子**：先 GET 再改的写法有 TOCTOU 窗口
（GET 之后、EXPIRE 之前锁被释放并被别人拿走 ⇒ 我把别人的锁续了命）。
"""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

import redis.asyncio as aioredis
import redis.exceptions as redis_exc

from app.services.edit_guard import has_conflict_detection

logger = logging.getLogger(__name__)

#: ADR-0048 §②：默认租约 30 分钟。
#: ⚠️ **可注入**（`ttl_seconds=`）—— 测试要短 TTL 证明到期行为；
#: 30min 是默认值，不是硬编码。
DEFAULT_TTL_SECONDS = 30 * 60

#: ADR-0048 §②：前端心跳 60s（TTL 的 1/30 余量：抖一次不失锁）。
HEARTBEAT_SECONDS = 60

#: ADR-0048 §①：key 前缀。
KEY_PREFIX = "lock:edit"

#: ADR-0048 §⑤：降级横幅文案。
DEGRADED_MESSAGE = "锁服务不可用，保存时可能冲突"
NO_CONFLICT_DETECTION_MESSAGE = "本次编辑无冲突检测"

# acquire：不存在才建；**已经是我的** ⇒ 续期并照常返回成功（幂等）。
# 返回 1 = 拿到，0 = 别人持有。
#
# ⚠️ 「已经是我的也算成功」不是可有可无的：前端进编辑器就 acquire 一次，
# 页面刷新 / 路由回退会再 acquire 一次。若这时返回「别人持有」，
# 界面会显示「XX 正在编辑」—— 而 XX 就是自己 ⇒ **假的冲突提示**。
_ACQUIRE_LUA = """
local current = redis.call('hget', KEYS[1], 'user_id')
if current == false then
  redis.call('hset', KEYS[1], 'user_id', ARGV[1], 'acquired_at', ARGV[2],
             'username', ARGV[4])
  redis.call('expire', KEYS[1], ARGV[3])
  return 1
end
if current == ARGV[1] then
  redis.call('expire', KEYS[1], ARGV[3])
  return 1
end
return 0
"""

# renew：值是我的才重置 TTL（compare-and-expire）。
_RENEW_LUA = """
if redis.call('hget', KEYS[1], 'user_id') == ARGV[1] then
  return redis.call('expire', KEYS[1], ARGV[2])
end
return 0
"""

# release：值是我的才删。
_RELEASE_LUA = """
if redis.call('hget', KEYS[1], 'user_id') == ARGV[1] then
  return redis.call('del', KEYS[1])
end
return 0
"""


@dataclass(frozen=True)
class LockHolder:
    """锁的持有者。"""

    user_id: uuid.UUID
    acquired_at: datetime
    username: str | None = None


@dataclass(frozen=True)
class LockState:
    """一次锁操作的结果。

    `success` 的含义随操作而变（**由调用方解释**）：
    - acquire：True = 锁归我；False = 别人持有（看 `holder`）。
    - renew：True = 续期成功；False = 不是持有者或已过期。
    - release：True = 已释放；False = 不是持有者。

    `degraded=True` ⇒ Redis 不可用，本次是**降级放行**（§⑤）。
    """

    success: bool
    holder: LockHolder | None
    ttl_seconds: int
    degraded: bool = False
    message: str | None = None


class EditLockService:
    """编辑锁（ADR-0048 §①~⑤）。**只碰 Redis。**"""

    DEFAULT_TTL_SECONDS = DEFAULT_TTL_SECONDS
    HEARTBEAT_SECONDS = HEARTBEAT_SECONDS

    def __init__(self, redis_url: str) -> None:
        self._redis_url = redis_url
        self._client: aioredis.Redis = aioredis.Redis.from_url(
            redis_url, decode_responses=True
        )

    # -- key ---------------------------------------------------------------

    @staticmethod
    def key(record_type: str, record_id: str) -> str:
        """`lock:edit:{record_type}:{record_id}`（§①）。"""
        return f"{KEY_PREFIX}:{record_type}:{record_id}"

    # -- 操作 --------------------------------------------------------------

    async def acquire(
        self,
        *,
        record_type: str,
        record_id: str,
        user_id: uuid.UUID,
        ttl_seconds: int | None = None,
        username: str | None = None,
    ) -> LockState:
        """取锁。已有人持有 ⇒ 不给（并返回持锁人信息）。"""
        ttl = ttl_seconds or self.DEFAULT_TTL_SECONDS
        key = self.key(record_type, record_id)
        now = datetime.now(UTC)
        try:
            ok = await self._client.eval(
                _ACQUIRE_LUA,
                1,
                key,
                str(user_id),
                now.isoformat(),
                ttl,
                username or "",
            )
        except (TimeoutError, redis_exc.RedisError, OSError) as exc:
            return self._degraded(record_type, "acquire", exc)
        if int(ok) == 1:
            return LockState(
                success=True,
                holder=LockHolder(
                    user_id=user_id, acquired_at=now, username=username
                ),
                ttl_seconds=ttl,
            )
        holder = await self._holder(record_type, record_id)
        return LockState(success=False, holder=holder, ttl_seconds=ttl)

    async def renew(
        self,
        *,
        record_type: str,
        record_id: str,
        user_id: uuid.UUID,
        ttl_seconds: int | None = None,
    ) -> LockState:
        """续期（compare-and-expire）。**他人的心跳不得延长我的锁。**"""
        ttl = ttl_seconds or self.DEFAULT_TTL_SECONDS
        key = self.key(record_type, record_id)
        try:
            ok = await self._client.eval(_RENEW_LUA, 1, key, str(user_id), ttl)
        except (TimeoutError, redis_exc.RedisError, OSError) as exc:
            return self._degraded(record_type, "renew", exc)
        if int(ok) == 1:
            holder = await self._holder(record_type, record_id)
            return LockState(success=True, holder=holder, ttl_seconds=ttl)
        holder = await self._holder(record_type, record_id)
        # holder 为 None ⇒ 锁已过期（没人持有）⇒ 续期失败
        return LockState(success=False, holder=holder, ttl_seconds=ttl)

    async def release(
        self,
        *,
        record_type: str,
        record_id: str,
        user_id: uuid.UUID,
    ) -> LockState:
        """释放锁。**仅持有者可释放**（非持有者 ⇒ 不得动别人的锁）。"""
        key = self.key(record_type, record_id)
        try:
            ok = await self._client.eval(_RELEASE_LUA, 1, key, str(user_id))
        except (TimeoutError, redis_exc.RedisError, OSError) as exc:
            return self._degraded(record_type, "release", exc)
        if int(ok) == 1:
            return LockState(
                success=True,
                holder=LockHolder(user_id=user_id, acquired_at=datetime.now(UTC)),
                ttl_seconds=0,
            )
        holder = await self._holder(record_type, record_id)
        return LockState(success=False, holder=holder, ttl_seconds=0)

    # -- 读 ---------------------------------------------------------------

    async def is_held(self, *, record_type: str, record_id: str) -> bool:
        """锁是否有人持有。"""
        return await self._holder(record_type, record_id) is not None

    async def holder(
        self, *, record_type: str, record_id: str
    ) -> LockHolder | None:
        """当前持有者（没有 ⇒ None）。"""
        return await self._holder(record_type, record_id)

    async def _holder(self, record_type: str, record_id: str) -> LockHolder | None:
        key = self.key(record_type, record_id)
        try:
            data = await self._client.hgetall(key)
        except (TimeoutError, redis_exc.RedisError, OSError):
            logger.warning("读编辑锁失败（降级：当作无人持有）", exc_info=True)
            return None
        if not data:
            return None
        raw_uid = data.get("user_id")
        if not raw_uid:
            return None
        try:
            uid = uuid.UUID(str(raw_uid))
        except ValueError:
            logger.warning("编辑锁的 user_id 不是 UUID：%r", raw_uid)
            return None
        acquired_at = _parse_iso(data.get("acquired_at"))
        raw_name = data.get("username") or None
        return LockHolder(
            user_id=uid, acquired_at=acquired_at, username=raw_name or None
        )

    # -- 降级 --------------------------------------------------------------

    def _degraded(self, record_type: str, operation: str, exc: Exception) -> LockState:
        """Redis 不可用 ⇒ **降级放行** + ERROR 日志 + 横幅（§⑤）。

        ⚠️ **不是 503**：用户不是被系统挡住，而是「体验层没了，正确性层
        还在」。真正的拒绝发生在保存时（DB 层的 record_hash 比对）。

        ⚠️ 横幅文案**按表**给：没有接上 DB 兜底的表必须额外提示
        「本次编辑无冲突检测」—— 用户在无保护状态下编辑，**必须知道**
        （§⑤：「这不是可选的措辞优化」）。
        """
        logger.error(
            "编辑锁 %s 降级（Redis 不可用）：%s", operation, exc, exc_info=True
        )
        message = DEGRADED_MESSAGE
        if not has_conflict_detection(record_type):
            message = f"{message}；{NO_CONFLICT_DETECTION_MESSAGE}"
        return LockState(
            success=True,
            holder=None,
            ttl_seconds=0,
            degraded=True,
            message=message,
        )

    # -- 生命周期 ----------------------------------------------------------

    async def aclose(self) -> None:
        """关连接（进程级单例不关 ⇒ 每次优雅重启漏连接）。"""
        try:
            await self._client.aclose()
        except Exception:  # noqa: BLE001 — 关闭失败不该让 shutdown 失败
            logger.warning("关闭编辑锁的 Redis 连接失败", exc_info=True)


def _parse_iso(raw: str | None) -> datetime:
    """解析 acquired_at；坏值 ⇒ 当前时间（不让一个坏字段毁掉整个响应）。"""
    if not raw:
        return datetime.now(UTC)
    try:
        dt = datetime.fromisoformat(raw)
    except ValueError:
        return datetime.now(UTC)
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


_lock_service: EditLockService | None = None


def get_edit_lock() -> EditLockService:
    """进程级单例（Redis 连接是进程级资源）。"""
    global _lock_service
    if _lock_service is None:
        from app.core.config import get_settings

        _lock_service = EditLockService(get_settings().redis_url)
    return _lock_service


def set_edit_lock(service: EditLockService | None) -> None:
    """替换单例（测试用；传 None ⇒ 下次取时重建）。"""
    global _lock_service
    _lock_service = service


__all__ = [
    "DEGRADED_MESSAGE",
    "DEFAULT_TTL_SECONDS",
    "HEARTBEAT_SECONDS",
    "KEY_PREFIX",
    "NO_CONFLICT_DETECTION_MESSAGE",
    "EditLockService",
    "LockHolder",
    "LockState",
    "get_edit_lock",
    "set_edit_lock",
]
