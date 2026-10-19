# P9A-1 身份线（登录 / 停用 / AD 同步）

> 本文件是 `docs/PCS-PLAN-P9A.md`（总纲）的 **A 号 lane**。
> 共享的 Global Constraints / Review Focus / 失败模式 在总纲，只写一遍。
> **前置**：无前置 —— 整条线的起点
> **本 lane 的完成判定**（与总纲 §完成标准 对应）：见文末。

---

### A1：迁移基座（`users.token_version` + CHECK）

**Files:**
- Create: `pcs-backend/alembic/versions/p9_001_users_token_version.py`
- Modify: `pcs-backend/app/models/project.py`（`User.token_version`）
- ⚠️ 本迁移**只**做身份一件事。`cost_est_results.record_hash` → lane D；
  `workflow_progress` 表 → lane B；`notifications` 表 → lane C。
  **理由**：仓库迁移惯例是 0~2 个 DDL（实测最近 8 个迁移），合并会让
  4 条 lane 卡在同一个 alembic head 上，反而失去并行度。
- Test: `pcs-backend/tests/migrations/test_p9_001_schema.py`

**Interfaces:**
- Consumes: `RecordMixin` / `TimestampMixin`（`app/models/mixins.py`）、`BASELINE` 无
- Produces:
  - `users.token_version: int`（NOT NULL, server_default `'1'`, CHECK `>= 1`）
  - 🔧 **同批修正**：`User.roles` 的列注释 `SYSADMIN` → `SYSTEM_ADMIN`
    （ADR-0046 的「带归属的待办」；惰性建行正往这列写真值，照注释写会产出
    ACL 不认的字符串 —— `app/core/acl.py:13` 明写 `User.roles` 是 ACL 权威输入）
- 下游需要但**不在本 lane**：`workflow_progress` 表 → lane B；`notifications` 表 →
  lane C；`cost_est_results.record_hash` → lane D

- [ ] **Step 1: 写失败测试**

```python
# tests/migrations/test_p9_001_schema.py
"""P9A 迁移基座的 schema 断言 —— 防「ORM 写了但没迁移」与「迁移写了但 ORM 没跟上」。

⚠️ 迁移与 ORM 漂移时，**单测照绿、真库会炸**（CLAUDE.md 漂移盲区）。
本文件断言的是**元数据与迁移产物一致**，不是运行时行为。
"""
import pytest
from app.db.base import Base
import app.models  # noqa: F401  触发全部 model 注册
from sqlalchemy import inspect


def _cols(table: str) -> set[str]:
    return {c["name"] for c in Base.metadata.tables[table].columns}


def test_users_has_token_version():
    assert "token_version" in _cols("users")


def test_token_version_is_checked_ge_1():
    """0 是 mock 令牌的哨兵值 —— 真实用户永不为 0（ADR-0046 §③b）。"""
    t = Base.metadata.tables["users"]
    checks = [str(c.sqltext) for c in t.constraints if c.__class__.__name__ == "CheckConstraint"]
    assert any("token_version" in c and ">= 1" in c.replace(" ", "") for c in checks), \
        f"users 缺 CHECK (token_version >= 1)，现有约束：{checks}"


def test_cost_est_has_record_hash():
    assert "record_hash" in _cols("cost_est_results")


def test_workflow_progress_has_8_fields():
    assert _cols("workflow_progress") == {
        "progress_id", "project_id", "workflow_type", "workflow_id",
        "step_order", "step_role", "state", "updated_by", "created_at", "updated_at",
    }



```

- [ ] **Step 2: 跑测试确认红**

```bash
cd /home/pangzy/code_project/PCS/pcs-backend
uv run pytest tests/migrations/test_p9_001_schema.py -q
```
预期：`test_users_has_token_version` 失败（`users` 无该列）。

- [ ] **Step 3: ORM 声明**

`app/models/project.py` 的 `User` 类内追加（注意列注释词表 —— 见 Global Constraints 下面的实施陷阱）：

```python
    token_version: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("'1'"),
        comment="吊销版本；0 为保留值（mock 令牌哨兵），真实用户永不为 0",
    )
    __table_args__ = (
        CheckConstraint("token_version >= 1", name="ck_users_token_version_ge_1"),
    )
```

🔧 **同批必须修正**（ADR-0046 带归属的待办）：`User.roles` 的列注释仍写着 `SYSADMIN`，
而 2026-10-04 的 role-string 收敛已改为 `SYSTEM_ADMIN`（`app/api/v1/_guard.py:37`）。
**惰性建行正往这一列写真值，照注释写会产出 ACL 不认的字符串**（`app/core/acl.py:13`
明写 `User.roles` 是 ACL 权威输入）。改成现行词表。

- [ ] **Step 4: 跑测试确认半绿（ORM 绿、迁移红）**

```bash
uv run pytest tests/migrations/test_p9_001_schema.py -q
```
预期：2 个测试全绿。

- [ ] **Step 5: 写迁移**

```python
# alembic/versions/p9_001_users_token_version.py
"""P9A 身份迁移：users.token_version + CHECK >= 1。

ADR-0046 §④（token_version 引入）、§③b（0 是 mock 令牌的哨兵 ⇒ 真实用户永不为 0）。
⚠️ 本迁移只做身份一件事 —— 其余三样分属 lane B/C/D（见 Files 段的理由）。
"""
from alembic import op
import sqlalchemy as sa

revision = "p9_001"
down_revision = "p8_011"          # ⚠️ 开工时先 `uv run alembic heads` 确认
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column(
        "token_version", sa.Integer(), nullable=False, server_default=sa.text("'1'")))
    op.create_check_constraint("ck_users_token_version_ge_1", "users", "token_version >= 1")


def downgrade() -> None:
    op.drop_constraint("ck_users_token_version_ge_1", "users", type_="check")
    op.drop_column("users", "token_version")
```

- [ ] **Step 6: 应用 + 双库验漂移**

```bash
cd /home/pangzy/code_project/PCS/pcs-backend
uv run alembic upgrade head
uv run python scripts/check_openapi_payload_coverage.py   # RC 预期 0
uv run python scripts/gate_alembic_check.py               # RC 预期 0
# 第二库单独跑（CLAUDE.md 读法③：hook 绿 ≠ 两库都干净）
DATABASE_URL="$(grep -oE '^DATABASE_URL=.*' .env | cut -d= -f2 | sed 's|@localhost:5432/pcs$|@localhost:5432/pcs_test|')" \
  uv run python scripts/gate_alembic_check.py
```

- [ ] **Step 7: 存量数据检查**

`users` 表当前 **0 行** ⇒ `server_default='1'` 自动覆盖，**无需回填**（回填脚本是本计划
上一稿对 `cost_est_results` 写的，那张表归 lane D）。
```bash
uv run python -c "
import asyncio
from app.db.session import get_async_session_factory
from sqlalchemy import text
async def main():
    async with get_async_session_factory()() as s:
        n = (await s.execute(text('select count(*) from users'))).scalar()
        print('users 行数:', n)
asyncio.run(main())
"
```

- [ ] **Step 8: 回归 + commit**

```bash
uv run pytest tests/ -q -x
cd .. && git add -A && git commit -m "feat(P9A): 迁移基座 token_version/CHECK + cost_est.record_hash + workflow_progress + notifications"
```

---

---

---

### A2：登录签发共用路径（`_issue_tokens()`）

**Files:**
- Modify: `pcs-backend/app/api/v1/auth.py:217-285`（login）、`app/api/v1/mock_auth.py:53-68`
- Create: `pcs-backend/app/services/token_issuer.py`
- Modify: `pcs-backend/app/api/v1/auth.py`（refresh，`/auth/refresh`）
- Test: `pcs-backend/tests/api/v1/test_token_issuer.py`

**Interfaces:**
- Consumes: Task 1 的 `users.token_version`；`ldap_client.authenticate`；`mock_auth.MOCK_USERS`
- Produces:
  - `async def issue_tokens(*, session, username, role, actor_user_id, token_version, persist_user: bool) -> TokenPair`
    —— `persist_user=False` 即 mock 路径（ADR-0046 §③b：不写 users 表）
  - `/auth/refresh` 比对 `claim.tv == users.token_version`，不等 → 401

- [ ] **Step 1: 写失败测试**

```python
# tests/api/v1/test_token_issuer.py
"""`_issue_tokens()` 的测试 —— ADR-0046 §③ 的三条断言在两条路径上都要成立。

**mock 不落库**（§③b）：MOCK_USERS 的 alice 与真实 AD 的 alice 同名 + uuid5 以
username 为键 ⇒ 若落库会污染同一行；而 `app/core/acl.py:13` 明写 `User.roles`
是 ACL 的权威输入。
"""
import pytest


async def _mk_user(session, *, uid="u1", username="alice", roles=None, token_version=1, status="ACTIVE"):
    from app.models.project import User
    u = User(user_id=uid, username=username, display_name=username,
             roles=roles or ["DESIGNER"], ad_groups=[], status=status,
             token_version=token_version)
    session.add(u)
    await session.flush()
    return u


@pytest.mark.asyncio
async def test_login_persists_user_row(session):
    """真实路径：惰性建行 + tv claim = 行内 token_version。"""
    from app.services.token_issuer import issue_tokens
    pair = await issue_tokens(session=session, username="bob", role="DESIGNER",
                              actor_user_id=None, persist_user=True)
    from app.models.project import User
    row = (await session.execute(User.__table__.select().where(
        User.username == "bob"))).first()
    assert row is not None, "真实登录必须惰性建 users 行"
    assert pair.refresh_claims["tv"] == row.token_version


@pytest.mark.asyncio
async def test_mock_does_not_persist(session):
    """§③b：mock 绝不写 users 表。"""
    from app.services.token_issuer import issue_tokens
    from app.models.project import User
    await issue_tokens(session=session, username="alice", role="DESIGNER",
                       actor_user_id=None, persist_user=False)
    row = (await session.execute(User.__table__.select().where(
        User.username == "alice"))).first()
    assert row is None, "mock 建了行 ⇒ 会污染同名真实用户的 roles"


@pytest.mark.asyncio
async def test_mock_tv_is_sentinel_zero(session):
    """mock 的 tv = 0；真实行出现后（tv>=1）mock 存量令牌自动失效。"""
    from app.services.token_issuer import issue_tokens
    pair = await issue_tokens(session=session, username="carol", role="APPROVER",
                              actor_user_id=None, persist_user=False)
    assert pair.refresh_claims["tv"] == 0
    # 真实 carol 登录建行后，0 != 1 ⇒ 旧 mock refresh 必须被拒
    await _mk_user(session, username="carol", token_version=1)
    from app.services.token_issuer import verify_refresh_tv
    assert await verify_refresh_tv(session, username="carol", tv=0) is False


@pytest.mark.asyncio
async def test_disabled_user_rejected(session):
    """§③：停用用户拒绝登录 + 写审计 USER_LOGIN_DENIED_DISABLED。"""
    from app.services.token_issuer import issue_tokens
    from app.core.errors import PcsError
    await _mk_user(session, username="dave", status="DISABLED")
    with pytest.raises(PcsError) as ei:
        await issue_tokens(session=session, username="dave", role="DESIGNER",
                           actor_user_id=None, persist_user=True)
    assert ei.value.status == 401
    from app.models.system import AuditLog
    actions = (await session.execute(
        AuditLog.__table__.select().with_only_columns(AuditLog.__table__.c.action)
        .where(AuditLog.__table__.c.action == "USER_LOGIN_DENIED_DISABLED"))).scalars().all()
    assert actions, "停用拒绝必须写审计，否则无法追责"
```

- [ ] **Step 2: 跑测试确认红**（`ModuleNotFoundError: app.services.token_issuer`）

- [ ] **Step 3: 写实现**

`app/services/token_issuer.py` 核心（签名见 Interfaces）：

```python
MOCK_TV_SENTINEL = 0   # 保留值；真实用户 token_version >= 1（ADR-0046 §③b）

async def issue_tokens(*, session, username, role, actor_user_id,
                       persist_user: bool) -> TokenPair:
    """登录签发的**唯一**路径。`/auth/login` 与 `/auth/mock-login` 都调它。

    persist_user=False（mock）：不查不写 users 表，tv 写哨兵 0。
    persist_user=True（真实）：查 users.status（DISABLED → 401 + 审计），
    无行则惰性建 ACTIVE 行，tv 写行内 token_version。
    """
```

⚠️ **登录角色来源**：`/auth/login` 的 role 来自 `resolve_role(user.groups)`（`auth.py:261`），
不要用 `MOCK_USERS` 的值覆盖真实路径 —— 否则 mock 角色会经惰性建行写进 `users.roles`。

- [ ] **Step 4: 两端点改调共用路径**

`auth.py` 的 login 与 `mock_auth.py:53-68` 都换成 `issue_tokens(...)`；
`mock_login` 额外检查**不得**导入任何 ORM 写操作。`/auth/refresh` 加 `tv` 比对：
无 users 行且 `tv == 0` ⇒ 放行（mock）；有行则 `tv == row.token_version` 才放行。

- [ ] **Step 5: 跑测试 + 全量回归**

```bash
uv run pytest tests/api/v1/test_token_issuer.py tests/api/v1/test_auth.py -q
uv run pytest tests/ -q    # 基线 4643 + 新增，不得倒退
```

- [ ] **Step 6: commit**

```bash
git add -A && git commit -m "feat(P9A): 登录签发共用 _issue_tokens 路径（mock 不落 users + tv 哨兵 0 + 停用拒绝）"
```

---

---

### A3：ADMIN 端点 + AD 同步最小实现

**Files:**
- Create: `pcs-backend/app/api/v1/admin_users.py`
- Modify: `pcs-backend/app/api/v1/__init__.py`（挂 router）
- Create: `pcs-backend/app/services/ad_sync.py`
- Test: `pcs-backend/tests/api/v1/test_admin_users.py`、`tests/services/test_ad_sync.py`

**Interfaces:**
- Consumes: Task 1 `token_version`；Task 2 `issue_tokens`；`ldap_client`
- Produces: `GET /api/v1/admin/users`、`PUT /api/v1/admin/users/{user_id}/disable`（SPEC `P9A-ADM-001/002`）
  - ✅ **全环境挂载**，用 `require_roles("SYSTEM_ADMIN")` 把关（2026-10-19 决策委员会 D2 裁决）。
    **mock 用户不豁免** —— mock 的 dan 是 SYSTEM_ADMIN，但停用 mock 用户对 QA 无意义且会
    误伤测试；需要时在测试里 mock 掉。
    ⚠️ **不可照搬 `mock_auth` 的形态**：那个是「生产不该有」，这个是「生产必须有」——
    只在非生产挂载 ⇒ 生产上永远无法停用任何人 ⇒ P9A-USR-004 验收无法演示，
    ADR-0046 §⑤ 整段落不了地。

- [ ] **Step 1: 写失败测试**（根断言，逐条都要有）：

```python
async def test_disable_requires_system_admin(client, designer_token):
    # 鉴权是唯一的门 —— 端点全环境挂载，必须挡住非 SYSTEM_ADMIN
    r = await client.put(f"/api/v1/admin/users/{uid}/disable", headers=designer_token)
    assert r.status_code == 403

async def test_admin_router_mounted_in_production(...):
    # 端点**必须**在生产挂载：否则生产无法停用任何人。
    # ⚠️ 这条防的是「照搬 mock_auth 的非生产挂载」—— 把「生产不该有」的形态
    #    套到「生产必须有」的东西上。
    ...

async def test_disable_increments_token_version(session): ...
async def test_disabled_user_refresh_returns_401(client): ...
```

- [ ] **Step 2: 跑测试确认红**

- [ ] **Step 3: 实现**

`disable` 的核心事务语义（ADR-0046 §⑤）：

```python
row.token_version += 1        # 同事务；已发 refresh 令牌全部失效
await _record_audit(session, action="USER_DISABLED", user_id=actor_id, resource_id=str(row.user_id))
# access token 不写 tv ⇒ 在手 access 仍可用至多 30 分钟（已知边界，不得表述为已解决）
```

`ad_sync.py` 最小实现（SPEC `P9A-USR-001/002/003`）：手动触发端点 + 每日凌晨 cron
（频率由 P9-OPEN-004 裁决为每日凌晨），AD 组 → 系统角色映射走 `resolve_role`。

- [ ] **Step 4: 验演示路径成立**

**`users` 表必须有行才能演示 disable。** 脚本验证：
`POST /auth/login` 建行 → `GET /admin/users` 可见 → `disable` → 该用户 refresh 401。
这条是 SPEC `P9A-USR-004` 的验收标准，不可跳过。

- [ ] **Step 5: 回归 + commit**

```bash
git add -A && git commit -m "feat(P9A): ADMIN 用户列表与停用端点 + AD 同步最小实现"
```

---
