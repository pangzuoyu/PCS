"""ACL 工具（基于 user 对象的 duck-typing）。

提供：
- PermissionDeniedError — 鉴权失败异常
- _user_attr(user, name) — 安全取属性，user=None/缺属性/空集合 → None
- **REVIEW_ROLES** — 审核角色的**唯一一份**清单（2026-11-23 · P10-I · T1）

契约（V1.5 P0-MED-001，2026-09-18）：
- 真实鉴权走内联 `require_roles(user, *roles)` 调用（app.api.v1.config 末尾），
  不再用装饰器（functools.wraps 替换函数签名，与 FastAPI Depends 冲突）。
- 本模块仅保留 PermissionDeniedError + _user_attr 辅助。

user 对象需具备 `.roles: Iterable[str]` 与 `.workspace_ids: Iterable[uuid.UUID]`
属性；ORM User（app.models.project.User）只有 .roles，.workspace_ids 由调用方
按业务上下文组装（ACL 模块不耦合 ORM）。

## ⚠️ 为什么角色清单落在**core**

`REVIEW_ROLES` 此前**写了两遍**（2026-11-23 · P10-I · T1 · hermes A-3 查出）：

| 位置 | 名字 | 形状 |
|---|---|---|
| `app/api/v1/report_builder.py` | `PUBLISH_ROLES` | tuple |
| `app/services/report/definition_service.py` | `OBSOLETE_ROLES` | frozenset |

⇒ ⇒ **同一组角色、两个副本、两个名字** ⇒ ⇒ 改一处忘了另一处
⇒ ⇒ **没有任何测试会发现**（两处都自洽）
⇒ ⇒ 现在收进 `core`（**api 与 service 都能 import 的那一层**
⇒ ⇒ 层规则：service **不** import api ⇒ ⇒ 只能放 core）。

⚠️ 形状取 **tuple**（有序）⇒ ⇒ 错误文案里的角色列表**顺序稳定**
⇒ ⇒ 用 `frozenset(REVIEW_ROLES)` 做集合判定。
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

#: **审核角色**（发布 / 作废 / 待审队列共用这一份）—— SPEC §3.2.2(6)
#: 「需审核角色审批通过」没点名 ⇒ ⇒ 落 REVIEWER（字面对应「审核」）；
#: APPROVER 也放行：P2 的 CONFIG 审批流用的是它，两个审批角色只放一个
#: 会让用户在审批页被拒。
REVIEW_ROLES: tuple[str, ...] = ("REVIEWER", "APPROVER", "SYSTEM_ADMIN")


class PermissionDeniedError(Exception):
    """ACL 鉴权失败（缺角色 / 缺项目访问权 / user 缺失）。"""


def _user_attr(user: Any, name: str) -> Iterable[Any] | None:
    """安全取 user 属性。

    P0-MED-007 fix（2026-09-18）：
    - user=None 或缺属性 → None
    - 空集合 → None（避免误判"无属性"，与"空集合"统一为空权限语义）
    - 非空集合 → 真实引用

    调用方对 None 与空集合语义等同（"无授权"），下游统一处理。
    """
    if user is None:
        return None
    value = getattr(user, name, None)
    if not value:
        return None
    return value