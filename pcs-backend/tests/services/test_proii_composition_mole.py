"""PRO/II 组成 → **摩尔分率**（P10-C · T4 · TODO-156）。

## 为什么要有这个文件

`app/services/import_service.py` 此前**不落组成**（`composition_json: None`）
⇒ ⇒ 导入出来的物流**进不了计算链**（flash 那条路要求有组成）
⇒ ⇒ SPEC §3.2.2 的 E2E-002「导入 ⇒ 物性补全」**中间那一环没被覆盖**。

⇒ ⇒ 现在：`.inp` 的 `COMPOSITION(M|W)`（**百分数** + **基准**）⇒ ⇒ 换成
`{CAS: 摩尔分率}`（和 = 1.0）⇒ ⇒ 送审时的组成门禁（100±0.5%）能过。

## 本文件钉的四条规则

1. **摩尔基准（M）** ⇒ 百分数 / 100 ⇒ 归一。
2. **质量基准（W）** ⇒ 质量→摩尔（按 MW）⇒ 归一 ⇒ ⇒ **与输入不等**
   （⇒ ⇒ 丢掉基准 ⇒ ⇒ 结果会错 ⇒ ⇒ 这条是最容易被漏的）。
3. **有一个组分认不出来 ⇒ ⇒ 整个组成为空**（「宁可没有组成，不要错组成」）。
4. **门禁口径**：归一后与 1.0 的偏差 ≤ **0.005**（≡ 100±0.5%）。
"""
from __future__ import annotations

import uuid
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.import_service import ImportService
from app.services.proii_composition import to_mole_fractions
from app.services.proii_parser import ProiiComposition, parse_compositions

FIXTURES = Path(__file__).parent.parent / "fixtures" / "proii"
SAMPLE6 = FIXTURES / "sample6_composition"

#: 组成门禁的容差（≡ `streams.py::_composition_gate` 的 100±0.5%）。
TOLERANCE = 0.005


@pytest_asyncio.fixture
async def make_project(db: AsyncSession):
    """Workspace + Project 工厂（commit 阶段需要 project_id）。

    ⚠️ 与 `tests/services/test_import_service.py` 的同名 fixture **同形**
    （那个是**文件内**的 ⇒ 不在 conftest ⇒ 这里自带一份）。
    """
    from app.models.project import Project, Workspace

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
        await db.flush()
        return proj

    return _make


# ---------------------------------------------------------------------------
# 换算本身
# ---------------------------------------------------------------------------


def test_mole_basis_is_scaled_to_fractions_and_normalized():
    """⚠️ **M 基准** ⇒ 百分数 / 100 ⇒ 归一 ⇒ 和 = 1.0。"""
    mole, unresolved = to_mole_fractions(
        ProiiComposition(basis="M", fractions={"WATER": 10.0, "METHANOL": 25.0})
    )
    assert unresolved == []
    assert mole is not None
    assert mole["7732-18-5"] == pytest.approx(10.0 / 35.0, rel=1e-6)
    assert mole["67-56-1"] == pytest.approx(25.0 / 35.0, rel=1e-6)
    assert abs(sum(mole.values()) - 1.0) <= TOLERANCE


def test_mass_basis_is_converted_to_mole_not_taken_as_is():
    """⚠️⚠️ **W 基准 ⇒ 质量→摩尔**（**结果 ≠ 输入**）⇒ 这是最容易漏的一条。

    ⇒ ⇒ 丢掉基准 ⇒ ⇒ 质量分率被当成摩尔分率 ⇒ ⇒ 组成**完全错**
    ⇒ ⇒ 而错组成比没组成**危险得多**（闪蒸会算出错的结果）。
    """
    mole, unresolved = to_mole_fractions(
        ProiiComposition(basis="W", fractions={"WATER": 80.0, "METHANOL": 20.0})
    )
    assert unresolved == []
    assert mole is not None
    # 水的 MW=18.015 < 甲醇的 32.04 ⇒ ⇒ 同样质量的水**摩尔数更多**
    # ⇒ ⇒ 水的**摩尔**分率（≈0.877）**大于**它的质量分率（0.80）
    # ⇒ ⇒ 这就是「结果 ≠ 输入」的证据（丢掉基准 ⇒ 直接返回 0.80/0.20 ⇒ 错）。
    assert mole["7732-18-5"] > 0.8
    assert mole["67-56-1"] < 0.2
    assert abs(sum(mole.values()) - 1.0) <= TOLERANCE


def test_unknown_component_voids_the_whole_composition():
    """⚠️ **有一个组分认不出来 ⇒ ⇒ 整个组成为空**（全有或全无）。"""
    mole, unresolved = to_mole_fractions(
        ProiiComposition(basis="M", fractions={"WATER": 50.0, "C99": 50.0})
    )
    assert mole is None
    assert unresolved == ["C99"]


# ---------------------------------------------------------------------------
# 导入链路
# ---------------------------------------------------------------------------


def test_preview_proii_carries_mole_fractions():
    """⚠️ **导入预览 ⇒ `composition_json` 非空且摩尔分率和 = 100±0.5%**。"""
    preview = ImportService.preview_proii(
        SAMPLE6 / "sample6_composition.inp",
        SAMPLE6 / "sample6_composition.out",
    )
    by_name = {e["stream_name"]: e for e in preview["preview_streams"]}

    # S1：COMPOSITION(M) ⇒ 摩尔 ⇒ 直接就是 10% / 60% / 25% / 5%
    comp = by_name["S1"]["composition_json"]
    assert comp, "S1 的组成不应为空"
    assert comp["7732-18-5"] == pytest.approx(0.10, rel=1e-6)
    assert comp["75-56-9"] == pytest.approx(0.60, rel=1e-6)
    assert abs(sum(comp.values()) - 1.0) <= TOLERANCE

    # S2：COMPOSITION(W) ⇒ 质量⇒摩尔 ⇒ 换算过 ⇒ 仍归一
    comp2 = by_name["S2"]["composition_json"]
    assert comp2, "S2 的组成不应为空"
    assert abs(sum(comp2.values()) - 1.0) <= TOLERANCE

    # S3：含认不出的组分 C99 ⇒ ⇒ **不带组成** + 有告警（fail-closed）
    assert by_name["S3"]["composition_json"] is None
    assert any("C99" in w for w in preview["warnings"])


def test_preview_proii_warns_about_unresolved_components():
    """⚠️ **没认出来的组分名要出现在 warnings 里**（用户看得见）。"""
    preview = ImportService.preview_proii(
        SAMPLE6 / "sample6_composition.inp",
        SAMPLE6 / "sample6_composition.out",
    )
    assert any("C99" in w for w in preview["warnings"])


def test_real_dmc_sample_composition_sums_to_100():
    """⚠️ **真样例**（`sample/dmc.inp`，⚠️ **不入 git**）⇒ ⇒ 组成归一后过门禁。

    ⇒ ⇒ 样例里的原始和**不是** 100（S18 = 99.9648%）⇒ ⇒ 归一后才过
    ⇒ ⇒ 这正是「归一是对的行为」的证据。
    """
    repo_sample = Path(__file__).resolve().parents[3] / "sample" / "dmc.inp"
    if not repo_sample.exists():
        pytest.skip("仓库根 sample/dmc.inp 不在（不入 git 的本地样例）")
    compositions = parse_compositions(repo_sample)
    assert compositions, "样例里应有组成"
    checked = 0
    for tag, comp in compositions.items():
        mole, unresolved = to_mole_fractions(comp)
        if mole is None:
            # ⇒ ⇒ 全有或全无 ⇒ ⇒ 未认出来 ⇒ ⇒ 不落组成（正确）
            assert unresolved
            continue
        checked += 1
        assert abs(sum(mole.values()) - 1.0) <= TOLERANCE, tag
    assert checked > 0, "样例里至少有一条流应当能换算成摩尔分率"


# ---------------------------------------------------------------------------
# 落库
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_commit_proii_persists_the_mole_fractions(db, make_project):
    """⚠️⚠️ **落库那一步** ⇒ ⇒ `streams.composition_json` 里是**摩尔分率**。

    ⇒ ⇒ 这是「导入 ⇒ 物性补全」那条链**真正接通**的那一环
    ⇒ ⇒ 只断 preview ⇒ ⇒ 断的是**导入 ⇒ 直接算物性**这条路。
    """
    from app.models.project import Stream

    proj = await make_project()
    preview = ImportService.preview_proii(
        SAMPLE6 / "sample6_composition.inp",
        SAMPLE6 / "sample6_composition.out",
    )
    result = await ImportService.commit_proii(
        db,
        project_id=proj.project_id,
        workspace_id=proj.workspace_id,
        preview_streams=preview["preview_streams"],
        actor=uuid.uuid4(),
    )
    assert result["committed_count"] >= 1

    rows = (
        await db.execute(select(Stream).where(Stream.project_id == proj.project_id))
    ).scalars().all()
    assert rows, "应当有物流落库"
    by_name = {r.stream_name: r for r in rows}

    # S1（M 基准）⇒ 组成落库且和 = 1.0
    comp = by_name["S1"].composition_json
    assert comp, "S1 的组成应当落库"
    assert comp["7732-18-5"] == pytest.approx(0.10, rel=1e-6)
    assert abs(sum(comp.values()) - 1.0) <= TOLERANCE

    # S3（认不出的组分）⇒ ⇒ **不带组成**（fail-closed ⇒ 不会带着错 CAS 落库）
    assert by_name["S3"].composition_json is None


@pytest.mark.asyncio
async def test_composition_total_passes_the_submit_gate_tolerance():
    """⚠️ **门禁口径**：组成合计与 1.0 的偏差 ≤ 0.005（≡ 100±0.5%）。

    ⇒ ⇒ 与 `app/api/v1/streams.py::_composition_gate` **同一常量**。
    ⇒ ⇒ 这条把「归一后的组成必然过门禁」钉住（不是碰巧）。
    """
    from app.api.v1.streams import _composition_gate

    mole, unresolved = to_mole_fractions(
        ProiiComposition(basis="M", fractions={"WATER": 33.33, "METHANOL": 33.33})
    )
    assert unresolved == []
    assert mole is not None
    total = sum(mole.values())
    assert abs(total - 1.0) <= 0.005

    # ⚠️⚠️ **真的过一遍门禁**（`streams.py::_composition_gate`）⇒ ⇒ 不抛 422。
    #    这是「导入 ⇒ 送审」这条链的**最后一环** ⇒ ⇒ 断在这里 ⇒ ⇒
    #    整条链走不通。
    from types import SimpleNamespace

    from app.api.v1.streams import _composition_gate

    stream = SimpleNamespace(
        stream_id=uuid.uuid4(),
        composition_json=mole,
    )
    await _composition_gate(stream)  # 不抛 ⇒ 过
