"""P4-1-3 FLASH API + 落库 + 状态点联动 + 出口物流 集成测试。

端到端验证（in-memory SQLite + httpx async）：
- POST /api/v1/flash/calculate（PT_FLASH / PH_FLASH / PS_FLASH / SATURATION）
- POST /api/v1/flash/bubble（mode=T 给 P 算 T_bubble；mode=P 给 T 算 P_bubble）
- POST /api/v1/flash/dew（同上）
- 出口物流 DRAFT 态拒绝下游（403 STREAM_NOT_CHECKED）
- 不可靠流守卫（422 STREAM_UNRELIABLE_BLOCKED）
- stream 不存在（404 SIM_STREAM_NOT_FOUND）
- 状态点联动（vapor_fraction 写入 stream_properties_json，estimated=true）
- outlet_stream helper 单独调用（DRAFT + properties + project_id 一致）

record_hash 契约（ADR-0031）：16 hex，6 位有效数字规范化（lineage 共享）。
"""
from __future__ import annotations

import re
import uuid
from typing import Any

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token
from app.models.enums import StreamSignStatus
from app.models.project import Project, Stream, Workspace
from app.schemas.stream import StreamCreate
from app.services.outlet_stream import create_outlet_stream
from app.services.stream_service import StreamService

# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------

_HASH_RE = re.compile(r"^[0-9a-f]{16}$")


@pytest_asyncio.fixture
async def make_project(db: AsyncSession):
    """最小 Workspace + Project 工厂。"""

    async def _make() -> Project:
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


@pytest_asyncio.fixture
async def seeded_stream(db: AsyncSession, make_project) -> Stream:
    """Workspace + Project + Stream（CHEMICAL，两组分 liquid，CHECKED）。

    两组分丙烷(74-98-6) + 正丁烷(106-97-8) 是 P4-1-2 step1 golden 用例；
    适合做 PT/BUBBLE/DEW flash 测试输入。
    """
    proj = await make_project()
    sp, _ = await StreamService.create(
        db,
        StreamCreate(
            project_id=proj.project_id,
            workspace_id=proj.workspace_id,
            stream_name="S-101",
            case_type="NORMAL",
            data_mode="CHEMICAL",
            source_type="MANUAL_ENTRY",
            temp=80.0,
            press=200.0,
            phase="LIQUID",
            mass_flow=1000.0,
            composition_json={"74-98-6": 0.3, "106-97-8": 0.7},
        ),
        actor=uuid.uuid4(),
    )
    # 推到 CHECKED 态（calc 入口要求）
    sp.sign_status = StreamSignStatus.CHECKED
    await db.commit()
    await db.refresh(sp)
    return sp


@pytest.fixture
def designer_headers() -> dict[str, str]:
    token = create_access_token(subject="test-designer", role="DESIGNER")
    return {"Authorization": f"Bearer {token}"}


def _calc_pt_body(stream_id: uuid.UUID, **kw) -> dict[str, Any]:
    """PT_FLASH 计算请求 body（SI 单位）。"""
    base: dict[str, Any] = dict(
        calc_type="PT_FLASH",
        stream_id=str(stream_id),
        T_K=335.0,
        P_Pa=1.0e6,
    )
    base.update(kw)
    return base


# ============================================================================
# 1) happy path：PT_FLASH 计算 → 201 + record_hash 16hex + lineage + outlet DRAFT
# ============================================================================


@pytest.mark.asyncio
async def test_calculate_pt_flash_happy_path(
    client, seeded_stream, designer_headers
):
    """PT_FLASH 计算：返回 calc_id + record_hash 16 hex + lineage 记录 + outlet DRAFT 流。"""
    r = await client.post(
        "/api/v1/flash/calculate",
        json=_calc_pt_body(seeded_stream.stream_id),
        headers=designer_headers,
    )
    assert r.status_code == 201, r.text
    body = r.json()

    # calc_id + record_hash
    assert "calc_id" in body
    assert _HASH_RE.match(body["record_hash"]), body["record_hash"]
    assert body["calc_type"] == "PT_FLASH"

    # lineage：至少 1 条
    assert len(body["lineage_ids"]) >= 1

    # outlet_stream：DRAFT 态创建
    assert body.get("outlet_stream_id") is not None
    # outlet 名称：源流名 + 计算后缀
    assert body["outlet_stream_name"].startswith(seeded_stream.stream_name)


@pytest.mark.asyncio
async def test_calculate_pt_flash_lineage_in_db(
    client, db: AsyncSession, seeded_stream, designer_headers
):
    """lineage 记录真实落库（DataLineage.source_ref_id = stream_id）。"""
    r = await client.post(
        "/api/v1/flash/calculate",
        json=_calc_pt_body(seeded_stream.stream_id),
        headers=designer_headers,
    )
    assert r.status_code == 201
    body = r.json()
    calc_id = uuid.UUID(body["calc_id"])

    from app.models.system import DataLineage

    rows = (
        await db.execute(
            select(DataLineage).where(
                DataLineage.record_type == "FlashResult",
                DataLineage.record_id == calc_id,
            )
        )
    ).scalars().all()
    assert len(rows) >= 1
    assert rows[0].source_ref_type == "Stream"
    assert rows[0].source_ref_id == seeded_stream.stream_id


# ============================================================================
# 2) CALCULATE SATURATION：无 outlet 流；只返 T_sat + h_fg
# ============================================================================


@pytest.mark.asyncio
async def test_calculate_saturation_no_outlet_stream(
    client, seeded_stream, designer_headers
):
    """SATURATION 是纯组分计算，无 outlet 流（无源流组成）；返 T_sat + h_fg。"""
    body = _calc_pt_body(seeded_stream.stream_id, calc_type="SATURATION")
    body["fluid"] = "PROPANE"
    body["T_K"] = 300.0  # 给 T → 求 P_sat
    body.pop("P_Pa")  # SATURATION 与 P_Pa 互斥
    r = await client.post(
        "/api/v1/flash/calculate",
        json=body,
        headers=designer_headers,
    )
    assert r.status_code == 201, r.text
    resp = r.json()
    assert resp["calc_type"] == "SATURATION"
    assert resp["outlet_stream_id"] is None
    # result 含 P_sat + h_fg
    assert "P_sat_Pa" in resp["result"]
    assert "h_fg_J_per_kg" in resp["result"]
    assert resp["result"]["P_sat_Pa"] > 0
    assert resp["result"]["h_fg_J_per_kg"] > 0


# ============================================================================
# 3) bubble T：已知 P=1MPa, zs=[0.3,0.7]，T_bubble ≈ 329.5939059867394（≤ 1e-2 K）
# ============================================================================


@pytest.mark.asyncio
async def test_calculate_bubble_T_matches_step2(
    client, seeded_stream, designer_headers
):
    """bubble 端点：mode=P 给 P=1MPa → T_bubble ≈ step2 golden（≤ 1e-2 K）。"""
    r = await client.post(
        "/api/v1/flash/bubble",
        json={
            "stream_id": str(seeded_stream.stream_id),
            "mode": "P",
            "value": 1.0e6,
        },
        headers=designer_headers,
    )
    assert r.status_code == 201, r.text
    body = r.json()
    # T_bubble ≈ 329.5939 K（golden step2）
    assert abs(body["bubble_T_K"] - 329.5939059867394) < 1e-2
    assert _HASH_RE.match(body["record_hash"])
    # outlet 流（DRAFT）
    assert body.get("outlet_stream_id") is not None


# ============================================================================
# 4) dew T：同 3 但 dew
# ============================================================================


@pytest.mark.asyncio
async def test_calculate_dew_T_matches_step2(
    client, seeded_stream, designer_headers
):
    """dew 端点：mode=P 给 P=1MPa → T_dew ≈ step2 golden（≤ 1e-2 K）。"""
    r = await client.post(
        "/api/v1/flash/dew",
        json={
            "stream_id": str(seeded_stream.stream_id),
            "mode": "P",
            "value": 1.0e6,
        },
        headers=designer_headers,
    )
    assert r.status_code == 201, r.text
    body = r.json()
    # T_dew ≈ 342.2622 K（golden step2）
    assert abs(body["dew_T_K"] - 342.26223500680044) < 1e-2
    assert _HASH_RE.match(body["record_hash"])


# ============================================================================
# 5) DRAFT 物流 403：手动设 outlet stream 为 DRAFT 后，下游 calculate 调它 → 403
# ============================================================================


@pytest.mark.asyncio
async def test_calculate_using_draft_outlet_stream_403(
    client, db: AsyncSession, seeded_stream, designer_headers
):
    """outlet stream 创建时是 DRAFT；用它做下游 calc 输入 → 403 STREAM_NOT_CHECKED。"""
    # 1. 先创建一个 outlet stream（DRAFT）
    outlet = await create_outlet_stream(
        db,
        source_stream_id=seeded_stream.stream_id,
        calc_type="PT_FLASH",
        source_type="FLASH_CALCULATED",
        properties={"vapor_fraction": 0.32},
        project_id=seeded_stream.project_id,
        workspace_id=seeded_stream.workspace_id,
    )
    assert outlet.sign_status == StreamSignStatus.DRAFT

    # 2. 用 DRAFT outlet 做下游 PT_FLASH 计算 → 403 STREAM_NOT_CHECKED
    r = await client.post(
        "/api/v1/flash/calculate",
        json=_calc_pt_body(outlet.stream_id),
        headers=designer_headers,
    )
    assert r.status_code == 403, r.text
    assert r.json()["code"] == "STREAM_NOT_CHECKED"


# ============================================================================
# 6) 不可靠流 422：mock UnreliableStreamGuard 触发 → 422 STREAM_UNRELIABLE_BLOCKED
# ============================================================================


@pytest.mark.asyncio
async def test_calculate_unreliable_stream_422(
    client, db: AsyncSession, make_project, monkeypatch, designer_headers
):
    """is_unreliable=True 流触发 UnreliableStreamGuard → 422 STREAM_UNRELIABLE_BLOCKED。"""
    proj = await make_project()
    sp, _ = await StreamService.create(
        db,
        StreamCreate(
            project_id=proj.project_id,
            workspace_id=proj.workspace_id,
            stream_name="S-UNC",
            case_type="NORMAL",
            data_mode="CHEMICAL",
            source_type="MANUAL_ENTRY",
            temp=80.0,
            press=200.0,
            phase="LIQUID",
            mass_flow=1000.0,
            composition_json={"74-98-6": 1.0},
        ),
        actor=uuid.uuid4(),
    )
    sp.sign_status = StreamSignStatus.CHECKED
    sp.is_unreliable = True
    await db.commit()
    await db.refresh(sp)

    r = await client.post(
        "/api/v1/flash/calculate",
        json=_calc_pt_body(sp.stream_id),
        headers=designer_headers,
    )
    assert r.status_code == 422, r.text
    assert r.json()["code"] == "STREAM_UNRELIABLE_BLOCKED"


# ============================================================================
# 7) stream 不存在 404：mock stream_id 不在库 → 404 SIM_STREAM_NOT_FOUND
# ============================================================================


@pytest.mark.asyncio
async def test_calculate_stream_not_found_404(client, designer_headers):
    """stream_id 不在库 → 404 SIM_STREAM_NOT_FOUND。"""
    r = await client.post(
        "/api/v1/flash/calculate",
        json=_calc_pt_body(uuid.uuid4()),
        headers=designer_headers,
    )
    assert r.status_code == 404, r.text
    assert r.json()["code"] == "SIM_STREAM_NOT_FOUND"


# ============================================================================
# 8) 状态点联动：calc 前 stream_properties_json 无 vapor_fraction；
#    calc 后有且等于计算值（estimated=true 标记）
# ============================================================================


@pytest.mark.asyncio
async def test_calculate_writes_vapor_fraction_to_stream(
    client, db: AsyncSession, seeded_stream, designer_headers
):
    """PT_FLASH 后源流 stream_properties_json 写入 vapor_fraction（estimated=true）。"""
    # 1. 初始确认无 vapor_fraction
    await db.refresh(seeded_stream)
    assert not seeded_stream.stream_properties_json or (
        "vapor_fraction" not in (seeded_stream.stream_properties_json or {})
    )

    # 2. 跑 PT_FLASH（335K, 1MPa → vfrac ≈ 0.32）
    r = await client.post(
        "/api/v1/flash/calculate",
        json=_calc_pt_body(seeded_stream.stream_id),
        headers=designer_headers,
    )
    assert r.status_code == 201

    # 3. 验证 stream_properties_json 写入 vapor_fraction + estimated flag
    await db.refresh(seeded_stream)
    spj = seeded_stream.stream_properties_json or {}
    assert "vapor_fraction" in spj
    vf = spj["vapor_fraction"]
    assert isinstance(vf, (int, float))
    assert 0.0 <= vf <= 1.0
    # estimated flag
    assert spj.get("_source") == "FLASH_CALCULATED"
    assert spj.get("_estimated") is True


@pytest.mark.asyncio
async def test_calculate_existing_vapor_fraction_logs_conflict(
    client, db: AsyncSession, seeded_stream, designer_headers
):
    """已有 user-set vapor_fraction 时不静默覆盖：写 conflict_resolutions_json。"""
    # 1. 预先设置 user vapor_fraction = 0.5
    seeded_stream.stream_properties_json = {
        "vapor_fraction": 0.5,
        "_source": "USER",
        "_estimated": False,
    }
    await db.commit()
    await db.refresh(seeded_stream)

    # 2. 跑 PT_FLASH
    r = await client.post(
        "/api/v1/flash/calculate",
        json=_calc_pt_body(seeded_stream.stream_id),
        headers=designer_headers,
    )
    assert r.status_code == 201

    # 3. user 值保留 + conflict_resolutions_json 写入冲突记录
    await db.refresh(seeded_stream)
    spj = seeded_stream.stream_properties_json or {}
    # user 值仍为 0.5（不被静默覆盖）
    assert spj["vapor_fraction"] == 0.5
    # 冲突记录
    crj = seeded_stream.conflict_resolutions_json or {}
    assert "vapor_fraction" in crj
    rec = crj["vapor_fraction"]
    assert rec["user_value"] == 0.5
    assert "calc_value" in rec
    assert rec["source"] == "FLASH_CALCULATED"


# ============================================================================
# 9) outlet_stream helper 单独测试：DRAFT + properties + project_id 一致
# ============================================================================


@pytest.mark.asyncio
async def test_outlet_stream_helper_creates_draft(
    db: AsyncSession, seeded_stream
):
    """create_outlet_stream：sign_status=DRAFT + properties 入 stream_properties_json
    + project_id 与 source 一致 + source_type=FLASH_CALCULATED。"""
    outlet = await create_outlet_stream(
        db,
        source_stream_id=seeded_stream.stream_id,
        calc_type="PT_FLASH",
        source_type="FLASH_CALCULATED",
        properties={"vapor_fraction": 0.32, "T_K": 335.0},
        project_id=seeded_stream.project_id,
        workspace_id=seeded_stream.workspace_id,
    )
    # DRAFT 态
    assert outlet.sign_status == StreamSignStatus.DRAFT
    # source_type=FLASH_CALCULATED
    assert outlet.source_type == "FLASH_CALCULATED"
    # project_id 一致
    assert outlet.project_id == seeded_stream.project_id
    assert outlet.workspace_id == seeded_stream.workspace_id
    # properties 入 stream_properties_json
    assert outlet.stream_properties_json == {
        "vapor_fraction": 0.32,
        "T_K": 335.0,
    }
    # 来源溯源字段
    assert outlet.upstream_stream_id == seeded_stream.stream_id
    assert outlet.upstream_equipment_type == "FLASH"


@pytest.mark.asyncio
async def test_outlet_stream_helper_project_mismatch_raises(
    db: AsyncSession, make_project, seeded_stream
):
    """project_id 与 source_stream 不一致 → OutletStreamProjectMismatchError。"""
    other_proj = await make_project()
    from app.services.outlet_stream import OutletStreamProjectMismatchError

    with pytest.raises(OutletStreamProjectMismatchError):
        await create_outlet_stream(
            db,
            source_stream_id=seeded_stream.stream_id,
            calc_type="PT_FLASH",
            source_type="FLASH_CALCULATED",
            properties={},
            project_id=other_proj.project_id,  # 跨 project
            workspace_id=other_proj.workspace_id,
        )
