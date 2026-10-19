"""AD 同步（SPEC P9A-USR-001/002/003，2026-10-19 用户裁决：加服务账号配置）。

覆盖三条主路径 + **两条安全属性**：

安全属性是这块最容易写出灾难的地方 ——
同步会把「目录里没有的人」标成离职，于是 filter 配错 = 全员停用。
所以「枚举抛异常」「枚举结果为空」两种情况都必须是 no-op。
"""
import uuid

import pytest
from ldap3.core.exceptions import LDAPSocketOpenError


class _AdUser:
    """`enumerate_users` 的返回项（测试自建，不依赖真实 LDAP）。"""

    def __init__(self, username, display_name, email, department, groups):
        self.username = username
        self.display_name = display_name
        self.email = email
        self.department = department
        self.groups = tuple(groups)


class _FakeEntry:
    def __init__(self, **attrs):
        for k, v in attrs.items():
            setattr(self, k, v)


class _FakeConn:
    """最小 ldap3.Connection 替身：只提供 `enumerate_users` 用到的三个方法。"""

    def __init__(self, entries=None, fail=False):
        self._entries = entries or []
        self._fail = fail
        self.search_args = None

    def search(self, *a, **kw):
        if self._fail:
            raise LDAPSocketOpenError("cannot reach server")
        self.search_args = kw

    @property
    def entries(self):
        return self._entries

    def unbind(self):
        pass


def _settings(monkeypatch, **kw):
    import app.core.config as cfg
    s = cfg.get_settings()
    for k, v in kw.items():
        monkeypatch.setattr(s, k, v, raising=False)
    return s


def _patch_ldap(monkeypatch, conn):
    import app.services.ldap_client as lc
    monkeypatch.setattr(lc.ldap3, "Server", lambda *a, **kw: object())
    monkeypatch.setattr(lc.ldap3, "Connection", lambda *a, **kw: conn)


async def _add_user(db_session, username, *, token_version=1, status="ACTIVE"):
    from app.models.project import User
    db_session.add(User(user_id=uuid.uuid4(), username=username,
                        display_name=username, roles=["DESIGNER"], ad_groups=[],
                        status=status, token_version=token_version))
    await db_session.flush()


async def _row(db_session, username):
    from app.models.project import User
    r = (await db_session.execute(
        User.__table__.select().where(User.__table__.c.username == username))).mappings().one()
    return r


def test_sync_not_configured_when_bind_dn_empty(monkeypatch):
    from app.services.ad_sync import ldap_sync_configured
    _settings(monkeypatch, ldap_bind_dn="")
    assert ldap_sync_configured() is False
    _settings(monkeypatch, ldap_bind_dn="cn=svc,DC=test")
    assert ldap_sync_configured() is True


def test_enumerate_users_reads_configured_attributes(monkeypatch):
    """属性名与 filter 全部走配置 —— AD 与 OpenLDAP 的属性名不同，写死就换不动。"""
    from app.services.ldap_client import enumerate_users
    _settings(monkeypatch, ldap_bind_dn="cn=svc,DC=test",
              ldap_user_filter="(objectClass=user)",
              ldap_user_attrs="displayName,mail,department,memberOf")
    conn = _FakeConn(entries=[_FakeEntry(
        uid=["alice"],
        displayName=["Alice Zhang"],
        mail=["alice@corp"],
        department=["Process"],
        memberOf=["cn=DESIGNER_GROUP,ou=Groups,dc=test,dc=local"],
    )])
    _patch_ldap(monkeypatch, conn)

    users = list(enumerate_users())
    assert len(users) == 1
    u = users[0]
    assert u.username == "alice"
    assert u.display_name == "Alice Zhang"
    assert u.email == "alice@corp"
    assert u.department == "Process"
    assert u.groups == ("cn=DESIGNER_GROUP,ou=Groups,dc=test,dc=local",)
    assert conn.search_args["search_filter"] == "(objectClass=user)"
    assert conn.search_args["attributes"][:4] == [
        "displayName", "mail", "department", "memberOf"]
    # username 主键属性必须被请求 —— ldap3 不返回没要过的属性
    assert "uid" in conn.search_args["attributes"]
    assert "sAMAccountName" in conn.search_args["attributes"]


def test_enumerate_users_raises_when_bind_fails(monkeypatch):
    """连不上目录必须抛 —— 调用方据此判定「同步失败」，而不是「全员离职」。"""
    from app.core.errors import PcsError
    from app.services.ldap_client import enumerate_users
    _settings(monkeypatch, ldap_bind_dn="cn=svc,DC=test")
    _patch_ldap(monkeypatch, _FakeConn(fail=True))
    with pytest.raises(PcsError):
        list(enumerate_users())


@pytest.mark.asyncio
async def test_sync_creates_rows_with_mapped_roles(db_session, monkeypatch):
    from app.services import ad_sync
    _settings(monkeypatch, ldap_bind_dn="cn=svc,DC=test")
    monkeypatch.setattr(ad_sync, "enumerate_users", lambda: iter([
        _AdUser("alice", "Alice Zhang", "alice@corp", "Process", ("DESIGNER_GROUP",)),
        _AdUser("bob", "Bob Li", "bob@corp", "Process", ("ADMIN_GROUP",)),
    ]))

    result = await ad_sync.sync_users(db_session)
    assert result.created == 2
    assert result.updated == 0

    alice, bob = await _row(db_session, "alice"), await _row(db_session, "bob")
    assert alice["roles"] == ["DESIGNER"]
    assert alice["email"] == "alice@corp"
    assert alice["department"] == "Process"
    assert bob["roles"] == ["SYSTEM_ADMIN"]


@pytest.mark.asyncio
async def test_sync_updates_existing_row_without_creating(db_session, monkeypatch):
    from app.services import ad_sync
    _settings(monkeypatch, ldap_bind_dn="cn=svc,DC=test")
    monkeypatch.setattr(ad_sync, "enumerate_users", lambda: iter([
        _AdUser("alice", "Alice Zhang", "alice@corp", "Process", ("DESIGNER_GROUP",)),
    ]))
    await ad_sync.sync_users(db_session)

    monkeypatch.setattr(ad_sync, "enumerate_users", lambda: iter([
        _AdUser("alice", "Alice Zhang-New", "alice2@corp", "R&D", ("CHECKER_GROUP",)),
    ]))
    result = await ad_sync.sync_users(db_session)
    assert result.created == 0
    assert result.updated == 1

    alice = await _row(db_session, "alice")
    assert alice["display_name"] == "Alice Zhang-New"
    assert alice["email"] == "alice2@corp"
    assert alice["department"] == "R&D"
    assert alice["roles"] == ["CHECKER"]


@pytest.mark.asyncio
async def test_sync_disables_users_missing_from_directory(db_session, monkeypatch):
    """P9A-USR-004：离职检测 —— 目录里没有的人标记停用 + tv 递增。"""
    from app.services import ad_sync
    _settings(monkeypatch, ldap_bind_dn="cn=svc,DC=test")
    await _add_user(db_session, "bob", token_version=1)

    monkeypatch.setattr(ad_sync, "enumerate_users", lambda: iter([
        _AdUser("alice", "Alice", "a@c", "P", ("DESIGNER_GROUP",)),
    ]))
    result = await ad_sync.sync_users(db_session)
    assert result.departed == 1

    bob = await _row(db_session, "bob")
    assert bob["status"] == "DISABLED"
    assert bob["token_version"] == 2


@pytest.mark.asyncio
async def test_sync_does_not_touch_already_departed(db_session, monkeypatch):
    """已停用的离职者不该被反复 tv += 1 —— 令牌早已作废，再涨只是噪声。"""
    from app.services import ad_sync
    _settings(monkeypatch, ldap_bind_dn="cn=svc,DC=test")
    await _add_user(db_session, "bob", token_version=5, status="DISABLED")

    monkeypatch.setattr(ad_sync, "enumerate_users", lambda: iter([
        _AdUser("alice", "Alice", "a@c", "P", ("DESIGNER_GROUP",)),
    ]))
    result = await ad_sync.sync_users(db_session)
    assert result.departed == 0
    assert (await _row(db_session, "bob"))["token_version"] == 5


@pytest.mark.asyncio
async def test_sync_aborts_when_enumeration_raises(db_session, monkeypatch):
    """⚠️ 安全属性：目录连不上时**绝不能**把所有人标成离职。"""
    from app.services import ad_sync
    _settings(monkeypatch, ldap_bind_dn="cn=svc,DC=test")

    def _boom():
        raise RuntimeError("LDAP unavailable")
        yield  # pragma: no cover

    monkeypatch.setattr(ad_sync, "enumerate_users", _boom)
    await _add_user(db_session, "carol")

    result = await ad_sync.sync_users(db_session)
    assert result.departed == 0
    assert result.ok is False
    assert (await _row(db_session, "carol"))["status"] == "ACTIVE", \
        "枚举失败被当成了全员离职"


@pytest.mark.asyncio
async def test_sync_is_noop_when_enumeration_empty(db_session, monkeypatch):
    """⚠️ 安全属性：空目录几乎总是 filter/base_dn 配错，不是全员离职。"""
    from app.services import ad_sync
    _settings(monkeypatch, ldap_bind_dn="cn=svc,DC=test")
    monkeypatch.setattr(ad_sync, "enumerate_users", lambda: iter([]))
    await _add_user(db_session, "dave")

    result = await ad_sync.sync_users(db_session)
    assert result.departed == 0
    assert result.skipped_empty is True
    assert (await _row(db_session, "dave"))["status"] == "ACTIVE"


def test_ad_sync_task_registered_in_worker():
    """ARQ 对未注册的函数名不报错，job 静静躺在队列里（worker.py:136-140）。"""
    from app.workers.ad_sync_tasks import sync_ad_users
    from app.workers.worker import WorkerSettings
    assert sync_ad_users in WorkerSettings.functions
    assert any(j.coroutine is sync_ad_users for j in WorkerSettings.cron_jobs)
