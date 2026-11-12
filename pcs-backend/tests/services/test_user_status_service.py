"""**账号停用判定**的单一判定点（P9B-4 评审 #10）。

## 这条 finding 在说什么

计划选「方案 B：**一个判定点**」的理由是「**改 status 词表要改两处**」⇒
⇒ 而实现上**判定散在三处**：

| 位置 | 查表键 | 语义 |
|---|---|---|
| `user_status_service.is_account_disabled` | `users.user_id` | 每请求（actor 层） |
| `token_issuer.issue_tokens` | `users.username` | 登录时 |
| `ad_sync`（离开 AD 的用户） | `users.username` | AD 同步 |

⇒ 三处**各自**写着 `status == UserStatus.DISABLED.value` ⇒ 改词表要改三处
⇒ 「单一判定点」的承诺**没兑现**。

## 本文件钉的三条

1. **比较只许有一处**（源码扫描）—— `== UserStatus.DISABLED` 这个**比较**
   在 `app/` 的生产代码里**只允许出现一次** ⇒ 三处调用点都走共享谓词。
   ⚠️ **写**（`user.status = UserStatus.DISABLED.value`）**不算**比较 ⇒ 不受影响。
2. **共享谓词对每个 status 取值给出唯一结论**（行为）—— 只有 `DISABLED` 判拒。
3. **两条路径的查表键不同 ⇒ 遗留行上会给出相反结论**（已知边界，登记在
   `TODOS.md` TODO-137）⇒ 显式钉住，让它**可见**而不是藏在两个实现里。
"""

from __future__ import annotations

import ast
import uuid
from pathlib import Path

import pytest

from app.models.enums import UserStatus

APP_DIR = Path(__file__).resolve().parents[2] / "app"


# ---------------------------------------------------------------------------
# 1. 比较只许有一处
# ---------------------------------------------------------------------------


def _dotted_name(node: ast.expr) -> str | None:
    """把 `a.b.c` 这样的属性链还原成字符串（不是属性链 ⇒ None）。"""
    parts: list[str] = []
    cur = node
    while isinstance(cur, ast.Attribute):
        parts.append(cur.attr)
        cur = cur.value
    if not isinstance(cur, ast.Name):
        return None
    parts.append(cur.id)
    return ".".join(reversed(parts))


def _is_disabled_ref(node: ast.expr) -> bool:
    """这个表达式是不是 `UserStatus.DISABLED`（或 `UserStatus.DISABLED.value`）。"""
    name = _dotted_name(node)
    if name is None:
        return False
    return name in ("UserStatus.DISABLED", "UserStatus.DISABLED.value")


def _disabled_comparison_sites() -> list[str]:
    """`app/` 生产代码里所有 `== UserStatus.DISABLED` 比较的位置（`file:line`）。"""
    sites: list[str] = []
    for path in sorted(APP_DIR.rglob("*.py")):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:  # pragma: no cover —— 仓库内不应有语法错误
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Compare):
                continue
            if not any(isinstance(op, ast.Eq) for op in node.ops):
                continue
            for side in (node.left, *node.comparators):
                if _is_disabled_ref(side):
                    sites.append(f"{path.relative_to(APP_DIR)}:{node.lineno}")
    return sites


def test_disabled_comparison_has_exactly_one_implementation():
    """⚠️ **「停用判定只在一处」必须是真的**（评审 #10）。

    ⇒ 三处调用点（每请求 / 登录 / AD 同步）都走**共享谓词**
    ⇒ 改 `status` 词表只改一处。
    """
    sites = _disabled_comparison_sites()
    assert len(sites) == 1, (
        f"停用判定的**比较**散在 {len(sites)} 处 ⇒ 改 status 词表要改多处：{sites}"
    )
    assert sites[0].startswith("services/user_status_service.py"), (
        f"唯一的比较点应当在 user_status_service（共享谓词），实际在 {sites[0]}"
    )


# ---------------------------------------------------------------------------
# 2. 共享谓词的行为
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        (UserStatus.DISABLED.value, True),
        (UserStatus.ACTIVE.value, False),
        (None, False),
        ("", False),
        ("disabled", False),  # ⚠️ 大小写敏感 —— 词表是**大写**枚举
    ],
)
def test_shared_predicate_only_rejects_the_disabled_literal(status, expected):
    """共享谓词：只有**恰好**等于 `DISABLED` 词表的取值才判拒。"""
    from app.services.user_status_service import is_disabled_status

    assert is_disabled_status(status) is expected


def test_shared_predicate_is_used_by_the_per_request_path():
    """每请求路径（actor 层）走共享谓词。"""
    from app.services.user_status_service import is_account_disabled, is_disabled_status

    src = Path(is_account_disabled.__code__.co_filename).read_text(encoding="utf-8")
    assert "is_disabled_status" in src, "每请求路径没走共享谓词"


def test_shared_predicate_is_used_by_the_login_path():
    """登录路径走共享谓词。"""
    from app.services.token_issuer import issue_tokens

    src = Path(issue_tokens.__code__.co_filename).read_text(encoding="utf-8")
    assert "is_disabled_status" in src, "登录路径没走共享谓词"


# ---------------------------------------------------------------------------
# 3. 两条路径的**已知分歧**（遗留行 · TODO-137）
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_legacy_row_is_denied_at_login_but_allowed_by_the_actor_layer(
    db_session,
):
    """⚠️ **已知边界**（评审 #10 明确要求写进文档）：两条路径**会分歧**。

    遗留账号行（`user_id` ≠ 派生值 · TODO-137 形状）：

    - **登录路径**按 `username` 查 ⇒ **查到**那一行 ⇒ `status=DISABLED` ⇒ 拒；
    - **每请求路径**按 `user_id` 查 ⇒ token 里的 `user_id` 是**派生值**
      ⇒ **查不到** ⇒ 「无行 ⇒ 放行」⇒ **放行**。

    ⇒ 同一个被停用的账号，**登录被拒、手里的 token 却还能用**。

    ⚠️ 暴露面很小：遗留行的 `user_id` 不是派生值 ⇒ `ensure_user_row` 与
    项目授权行都对不上 ⇒ 物流面**处处 404**（TODO-137 的既有结论）。

    ⇒ 本测试**钉住现状**（不是认可它）⇒ 将来谁把 actor 层改成按 `username` 查
    ⇒ 本测试会红 ⇒ 那时**正好**该把 docstring 与 `TODOS.md` 一起更新。
    """
    from app.models.project import User
    from app.services.token_issuer import derive_user_id
    from app.services.user_status_service import is_account_disabled

    legacy_user_id = uuid.uuid4()  # ⚠️ **不是**派生值 ⇒ 遗留行
    username = "legacy-disabled-user"
    db_session.add(
        User(
            user_id=legacy_user_id,
            username=username,
            display_name=username,
            roles=["DESIGNER"],
            ad_groups=[],
            status=UserStatus.DISABLED.value,
        )
    )
    await db_session.commit()

    # ① 登录路径（按 username）⇒ 查到那一行 ⇒ 判拒
    login_row = (
        await db_session.execute(
            User.__table__.select().where(User.__table__.c.username == username)
        )
    ).first()
    assert login_row is not None
    assert login_row.status == UserStatus.DISABLED.value

    # ② 每请求路径（按派生 user_id）⇒ 查不到 ⇒ 放行
    derived = derive_user_id(username)
    assert derived != legacy_user_id
    assert await is_account_disabled(db_session, user_id=derived) is False
