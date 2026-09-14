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


# ============================================================================
# 10) P4-1-4 FLASH 反向写入：H/S/vfrac → stream_properties_json
#     规则：calc 提供时写入；用户已设值走 conflict_resolutions_json（user-wins）；
#     单相不污染；统一 _source=Flash_CALCULATED + estimated=true 标记
# ============================================================================


@pytest.mark.asyncio
async def test_writeback_pt_flash_writes_enthalpy(
    client, db: AsyncSession, seeded_stream, designer_headers
):
    """PT_FLASH 反向写入：vapor_fraction（2-phase 时）+ enthalpy（J/mol）+ 标记。"""
    # 跑 PT_FLASH（335K, 1MPa → 2-phase）
    r = await client.post(
        "/api/v1/flash/calculate",
        json=_calc_pt_body(seeded_stream.stream_id),
        headers=designer_headers,
    )
    assert r.status_code == 201, r.text

    await db.refresh(seeded_stream)
    spj = seeded_stream.stream_properties_json or {}

    # vfrac（既有 P4-1-3 行为）
    assert "vapor_fraction" in spj
    assert 0.0 < spj["vapor_fraction"] < 1.0

    # enthalpy：calc 提供时（P4-1-4 新增）
    assert "enthalpy" in spj
    assert isinstance(spj["enthalpy"], (int, float))
    # 占位 thermo 模型：理想液体 + 理想气体，H 为正值（Cp * T）
    assert spj["enthalpy"] > 0

    # 统一 source 标记
    assert spj.get("_source") == "FLASH_CALCULATED"
    assert spj.get("_estimated") is True


@pytest.mark.asyncio
async def test_writeback_ph_flash_writes_enthalpy(
    client, db: AsyncSession, seeded_stream, designer_headers
):
    """PH_FLASH 反向写入：enthalpy（来自 H_target，FLASH_CALCULATED 标记）。

    准备：先用 PT_FLASH 找出 2-phase 区间内的 H 值，再 PH_FLASH 跑回去。
    """
    # 1. 先 PT_FLASH 拿一个有效 vfrac + H（在 2-phase 区）
    r_pt = await client.post(
        "/api/v1/flash/calculate",
        json=_calc_pt_body(seeded_stream.stream_id),
        headers=designer_headers,
    )
    assert r_pt.status_code == 201
    pt_result = r_pt.json()["result"]
    assert 0.0 < pt_result["vapor_fraction"] < 1.0

    # 2. 拿 spj 里的 enthalpy 作为 PH_FLASH 的 H_target（保证能收敛到 2-phase）
    await db.refresh(seeded_stream)
    spj_before = seeded_stream.stream_properties_json or {}
    h_target = float(spj_before["enthalpy"])

    # 3. PH_FLASH（用刚算出的 H 作为 target）
    r = await client.post(
        "/api/v1/flash/calculate",
        json={
            "calc_type": "PH_FLASH",
            "stream_id": str(seeded_stream.stream_id),
            "T_K": 335.0,
            "H_target": h_target,
        },
        headers=designer_headers,
    )
    assert r.status_code == 201, r.text

    # 4. enthalpy 应保留（H 值一致 → 幂等 no-op，不应触发冲突）
    await db.refresh(seeded_stream)
    spj = seeded_stream.stream_properties_json or {}
    assert "enthalpy" in spj
    assert abs(float(spj["enthalpy"]) - h_target) < 1e-3
    # 没有冲突记录（值一致 → 幂等）
    crj = seeded_stream.conflict_resolutions_json or {}
    assert "enthalpy" not in crj


@pytest.mark.asyncio
async def test_writeback_ps_flash_writes_entropy(
    client, db: AsyncSession, seeded_stream, designer_headers
):
    """PS_FLASH 反向写入：entropy（J/mol/K，FLASH_CALCULATED 标记）。"""
    # 1. 先 PT_FLASH 拿 entropy 基准（2-phase 区）
    r_pt = await client.post(
        "/api/v1/flash/calculate",
        json=_calc_pt_body(seeded_stream.stream_id),
        headers=designer_headers,
    )
    assert r_pt.status_code == 201

    # 2. 读 PT_FLASH 算出的 entropy 作为 PS_FLASH 的 S_target
    await db.refresh(seeded_stream)
    s_target = float(seeded_stream.stream_properties_json["entropy"])

    # 3. PS_FLASH（用算出的 S 作为 target）
    r = await client.post(
        "/api/v1/flash/calculate",
        json={
            "calc_type": "PS_FLASH",
            "stream_id": str(seeded_stream.stream_id),
            "T_K": 335.0,
            "S_target": s_target,
        },
        headers=designer_headers,
    )
    assert r.status_code == 201, r.text

    # 4. entropy 应保留
    await db.refresh(seeded_stream)
    spj = seeded_stream.stream_properties_json or {}
    assert "entropy" in spj
    assert abs(float(spj["entropy"]) - s_target) < 1e-3
    # source 标记
    assert spj.get("_source") == "FLASH_CALCULATED"
    assert spj.get("_estimated") is True


@pytest.mark.asyncio
async def test_writeback_user_value_wins_with_conflict(
    client, db: AsyncSession, seeded_stream, designer_headers
):
    """用户已设 enthalpy → calc 值入 conflict_resolutions_json；effective 不变（user-wins）。

    不静默覆盖：流 stream_properties_json.enthalpy = user 值；冲突记录入
    conflict_resolutions_json.enthalpy = {user_value, calc_value, source, resolver=user-wins}。
    """
    # 1. 预设 user_enthalpy = 1000（模拟用户手工设置）
    seeded_stream.stream_properties_json = {
        "enthalpy": 1000.0,
        "_source": "USER",
        "_estimated": False,
    }
    await db.commit()
    await db.refresh(seeded_stream)

    # 2. 跑 PH_FLASH（H_target=35000 在物理范围 [3e4, 4.2e4] 内）
    r = await client.post(
        "/api/v1/flash/calculate",
        json={
            "calc_type": "PH_FLASH",
            "stream_id": str(seeded_stream.stream_id),
            "T_K": 335.0,
            "H_target": 35000.0,
        },
        headers=designer_headers,
    )
    assert r.status_code == 201, r.text

    # 3. user 值保留 + 冲突记录
    await db.refresh(seeded_stream)
    spj = seeded_stream.stream_properties_json or {}
    # user 值未被覆盖
    assert spj["enthalpy"] == 1000.0

    crj = seeded_stream.conflict_resolutions_json or {}
    assert "enthalpy" in crj
    rec = crj["enthalpy"]
    assert rec["user_value"] == 1000.0
    assert "calc_value" in rec
    assert float(rec["calc_value"]) != 1000.0  # calc 与 user 不同才冲突
    assert rec["source"] == "FLASH_CALCULATED"
    assert rec["resolver"] == "user-wins"


@pytest.mark.asyncio
async def test_writeback_single_phase_no_vapor_fraction(
    client, db: AsyncSession, seeded_stream, designer_headers
):
    """单相不污染：vfrac=0 或 v=1 的 PT_FLASH 不写 vapor_fraction 到 stream_properties_json。

    极端条件：
    - v=0（液相）：T=250K, P=10MPa（远低于 bubble 温度，高于 dew 压力）
    - v=1（汽相）：T=600K, P=10kPa（远高于 dew 温度，低于 bubble 压力）
    """
    # v=1 路径：高温低压
    r = await client.post(
        "/api/v1/flash/calculate",
        json=_calc_pt_body(seeded_stream.stream_id, T_K=600.0, P_Pa=1.0e4),
        headers=designer_headers,
    )
    assert r.status_code == 201, r.text
    body = r.json()
    vf = body["result"]["vapor_fraction"]
    assert vf == 1.0, f"期望 v=1，实际 v={vf}"

    # 单相：源流不应被写入 vapor_fraction
    await db.refresh(seeded_stream)
    spj = seeded_stream.stream_properties_json or {}
    assert "vapor_fraction" not in spj, (
        f"单相不应污染 stream_properties_json.vapor_fraction，实际={spj}"
    )

    # 但 enthalpy 仍可写（calc 提供了）
    assert "enthalpy" in spj

    # 清理：换成 v=0 路径（新流）
    proj_id = seeded_stream.project_id
    workspace_id = seeded_stream.workspace_id
    sp2, _ = await StreamService.create(
        db,
        StreamCreate(
            project_id=proj_id,
            workspace_id=workspace_id,
            stream_name="S-102",
            case_type="NORMAL",
            data_mode="CHEMICAL",
            source_type="MANUAL_ENTRY",
            temp=250.0,
            press=10.0,
            phase="LIQUID",
            mass_flow=1000.0,
            composition_json={"74-98-6": 0.3, "106-97-8": 0.7},
        ),
        actor=uuid.uuid4(),
    )
    sp2.sign_status = StreamSignStatus.CHECKED
    await db.commit()
    await db.refresh(sp2)

    r2 = await client.post(
        "/api/v1/flash/calculate",
        json=_calc_pt_body(sp2.stream_id, T_K=250.0, P_Pa=1.0e7),
        headers=designer_headers,
    )
    assert r2.status_code == 201, r2.text
    body2 = r2.json()
    vf2 = body2["result"]["vapor_fraction"]
    assert vf2 == 0.0, f"期望 v=0，实际 v={vf2}"

    await db.refresh(sp2)
    spj2 = sp2.stream_properties_json or {}
    assert "vapor_fraction" not in spj2, (
        f"单相不应污染 stream_properties_json.vapor_fraction，实际={spj2}"
    )


@pytest.mark.asyncio
async def test_writeback_estimated_marker_present(
    client, db: AsyncSession, seeded_stream, designer_headers
):
    """所有 calc 写入字段（vfrac/H/S）的 _source=FLASH_CALCULATED + estimated=true 必须存在。"""
    # 跑 PT_FLASH（vfrac + enthalpy）
    r = await client.post(
        "/api/v1/flash/calculate",
        json=_calc_pt_body(seeded_stream.stream_id),
        headers=designer_headers,
    )
    assert r.status_code == 201

    await db.refresh(seeded_stream)
    spj = seeded_stream.stream_properties_json or {}

    # _source + _estimated 标记
    assert spj.get("_source") == "FLASH_CALCULATED"
    assert spj.get("_estimated") is True
    # calc 写入的字段至少包含 vfrac + enthalpy
    assert "vapor_fraction" in spj
    assert "enthalpy" in spj
