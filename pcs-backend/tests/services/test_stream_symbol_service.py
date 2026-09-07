"""StreamSymbolService 集成测试（SYM-2）。

依赖 db fixture（SQLite in-memory）；StreamSymbol + ProjectStreamSymbol
两表须在 db_session 时建（继承 conftest 的 Base.metadata.create_all）。
"""
import uuid

import pytest
import pytest_asyncio

from app.models.project import Project, Workspace
from app.services.exceptions import PcsError
from app.services.stream_symbol_service import StreamSymbolService


def _payload(symbol="FOO", **kw):
    base = dict(symbol=symbol, name=f"符号 {symbol}", category="PROCESS", version="1")
    base.update(kw)
    return base


@pytest_asyncio.fixture
async def make_project(db):
    """最小 Project（继承 PC-1 fixture 模式）。"""

    async def _make():
        ws = Workspace(workspace_type="FORMAL", name=f"ws-{uuid.uuid4().hex[:8]}")
        db.add(ws)
        await db.flush()
        proj = Project(
            project_no=f"P-{uuid.uuid4().hex[:8]}",
            project_name="测试项目",
            owner_company="测试业主",
            location="测试地点",
            project_type="CHEMICAL",
            design_phase="FEED",
            unit_system="SI",
            workspace_id=ws.workspace_id,
        )
        db.add(proj)
        await db.commit()
        return proj

    return _make


# ---------- 公司级 ----------


async def test_create_company_happy_path(db, actor):
    ss = await StreamSymbolService.create_company(
        db, data=_payload(symbol="FOO"), actor=actor,
    )
    assert ss.symbol == "FOO"
    assert ss.status == "DRAFT"
    assert ss.asset_id is not None


async def test_create_company_duplicate_raises_409(db, actor):
    await StreamSymbolService.create_company(
        db, data=_payload(symbol="FOO"), actor=actor,
    )
    with pytest.raises(PcsError) as e:
        await StreamSymbolService.create_company(
            db, data=_payload(symbol="FOO"), actor=actor,
        )
    assert e.value.status == 409
    assert e.value.code == "STREAM_SYMBOL_DUP"


async def test_get_missing_raises_404(db):
    with pytest.raises(PcsError) as e:
        await StreamSymbolService.get(db, uuid.uuid4())
    assert e.value.status == 404


async def test_list_company_orders_by_symbol(db, actor):
    await StreamSymbolService.create_company(db, data=_payload(symbol="BBB"), actor=actor)
    await StreamSymbolService.create_company(db, data=_payload(symbol="AAA"), actor=actor)
    rows = await StreamSymbolService.list_company(db)
    assert [r.symbol for r in rows] == ["AAA", "BBB"]


async def test_update_company_updates_fields(db, actor):
    ss = await StreamSymbolService.create_company(
        db, data=_payload(symbol="FOO"), actor=actor,
    )
    updated = await StreamSymbolService.update_company(
        db, ss.symbol_id, data={"name": "新名字", "category": "UTILITY"}, actor=actor,
    )
    assert updated.name == "新名字" and updated.category == "UTILITY"


async def test_delete_company_happy_path(db, actor):
    ss = await StreamSymbolService.create_company(
        db, data=_payload(symbol="FOO"), actor=actor,
    )
    await StreamSymbolService.delete_company(db, ss.symbol_id, actor=actor)
    with pytest.raises(PcsError):
        await StreamSymbolService.get(db, ss.symbol_id)


async def test_state_machine_submit_publish_flow(db, actor):
    """DRAFT → PENDING（submit）→ APPROVED（approve）→ PUBLISHED（publish）"""
    ss = await StreamSymbolService.create_company(
        db, data=_payload(symbol="FOO"), actor=actor,
    )
    assert ss.status == "DRAFT"
    pending = await StreamSymbolService.submit(db, ss.symbol_id, actor=actor)
    assert pending.status == "PENDING"
    # approve / publish
    approved = await StreamSymbolService.approve(db, ss.symbol_id, actor=actor)
    assert approved.status == "APPROVED"
    published = await StreamSymbolService.publish(db, ss.symbol_id, actor=actor)
    assert published.status == "PUBLISHED"


# ---------- 项目级 fork ----------


async def test_fork_all_publishes_only(db, actor, make_project):
    pub = await StreamSymbolService.create_company(
        db, data=_payload(symbol="PUB"), actor=actor,
    )
    await StreamSymbolService.submit(db, pub.symbol_id, actor=actor)
    await StreamSymbolService.approve(db, pub.symbol_id, actor=actor)
    await StreamSymbolService.publish(db, pub.symbol_id, actor=actor)
    await StreamSymbolService.create_company(
        db, data=_payload(symbol="DRFT"), actor=actor,
    )
    proj = await make_project()
    rows = await StreamSymbolService.fork_to_project(
        db, project_id=proj.project_id, symbol_id=None, actor=actor,
    )
    symbols = {r.symbol for r in rows}
    assert "PUB" in symbols
    assert "DRFT" not in symbols  # DRAFT 不被 fork


async def test_fork_single_symbol(db, actor, make_project):
    ss = await StreamSymbolService.create_company(
        db, data=_payload(symbol="ONLY"), actor=actor,
    )
    proj = await make_project()
    rows = await StreamSymbolService.fork_to_project(
        db, project_id=proj.project_id, symbol_id=ss.symbol_id, actor=actor,
    )
    assert len(rows) == 1 and rows[0].symbol == "ONLY"
    assert rows[0].snapshot_json["symbol"] == "ONLY"


async def test_fork_idempotent_when_already_forked(db, actor, make_project):
    ss = await StreamSymbolService.create_company(
        db, data=_payload(symbol="DUPE"), actor=actor,
    )
    proj = await make_project()
    first = await StreamSymbolService.fork_to_project(
        db, project_id=proj.project_id, symbol_id=ss.symbol_id, actor=actor,
    )
    second = await StreamSymbolService.fork_to_project(
        db, project_id=proj.project_id, symbol_id=ss.symbol_id, actor=actor,
    )
    assert first[0].project_symbol_id == second[0].project_symbol_id


async def test_delete_company_blocked_when_forked(db, actor, make_project):
    ss = await StreamSymbolService.create_company(
        db, data=_payload(symbol="REF"), actor=actor,
    )
    proj = await make_project()
    await StreamSymbolService.fork_to_project(
        db, project_id=proj.project_id, symbol_id=ss.symbol_id, actor=actor,
    )
    with pytest.raises(PcsError) as e:
        await StreamSymbolService.delete_company(db, ss.symbol_id, actor=actor)
    assert e.value.code == "STREAM_SYMBOL_IN_USE"


# ---------- 项目级 CRUD ----------


async def test_add_project_symbol_happy_path(db, actor, make_project):
    proj = await make_project()
    pss = await StreamSymbolService.add_project_symbol(
        db, project_id=proj.project_id,
        symbol="LOC", name="本地符号", category="OFFSITE", actor=actor,
    )
    assert pss.symbol == "LOC" and pss.source_symbol_id is None


async def test_add_project_symbol_dup_raises_409(db, actor, make_project):
    proj = await make_project()
    await StreamSymbolService.add_project_symbol(
        db, project_id=proj.project_id,
        symbol="LOC", name="x", category=None, actor=actor,
    )
    with pytest.raises(PcsError) as e:
        await StreamSymbolService.add_project_symbol(
            db, project_id=proj.project_id,
            symbol="LOC", name="y", category=None, actor=actor,
        )
    assert e.value.code == "PROJECT_STREAM_SYMBOL_DUP"


async def test_update_project_symbol_merges_override(db, actor, make_project):
    proj = await make_project()
    pss = await StreamSymbolService.add_project_symbol(
        db, project_id=proj.project_id,
        symbol="LOC", name="原名", category=None, actor=actor,
    )
    updated = await StreamSymbolService.update_project_symbol(
        db, project_symbol_id=pss.project_symbol_id,
        data={"override": {"note": "x"}, "name": "新名"}, actor=actor,
    )
    assert updated.name == "新名"
    assert updated.override_json["note"] == "x"


async def test_delete_project_symbol_removes(db, actor, make_project):
    proj = await make_project()
    pss = await StreamSymbolService.add_project_symbol(
        db, project_id=proj.project_id,
        symbol="DEL", name="x", category=None, actor=actor,
    )
    await StreamSymbolService.delete_project_symbol(
        db, project_symbol_id=pss.project_symbol_id, actor=actor,
    )
    with pytest.raises(PcsError):
        await StreamSymbolService.update_project_symbol(
            db, project_symbol_id=pss.project_symbol_id,
            data={"name": "y"}, actor=actor,
        )


async def test_list_project_includes_inherited_company(db, actor, make_project):
    pub = await StreamSymbolService.create_company(
        db, data=_payload(symbol="INH"), actor=actor,
    )
    await StreamSymbolService.submit(db, pub.symbol_id, actor=actor)
    await StreamSymbolService.approve(db, pub.symbol_id, actor=actor)
    await StreamSymbolService.publish(db, pub.symbol_id, actor=actor)
    proj = await make_project()
    rows = await StreamSymbolService.list_project(
        db, project_id=proj.project_id, include_company=True,
    )
    assert any(r["symbol"] == "INH" and r["status"] == "INHERITED" for r in rows)