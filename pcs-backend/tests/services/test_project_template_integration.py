"""INT-1：ProjectTemplate 默认等级 + 默认管道代码模板（V1.4 §15 / PC-OPEN-04）。

INT-DROP-01 撤销 stream_symbol_table_id 列（公司符号表无聚合实体）。
"""
from __future__ import annotations

import uuid
from collections import namedtuple

import pytest
import pytest_asyncio

from app.models.config_domain import PipeClass, ProjectTemplate
from app.services.exceptions import PcsError
from app.services.pipe_class_service import PipeClassService
from app.services.project_template_service import ProjectTemplateService

_AuthUser = namedtuple("_AuthUser", ["user_id"])


@pytest.fixture
def actor() -> _AuthUser:
    """最小 actor：service 层只用 user_id。"""
    return _AuthUser(user_id=uuid.uuid4())


@pytest_asyncio.fixture
async def make_company_pc(db, actor):
    """公司级等级 → PUBLISHED（PC-OPEN-04 fork 前提）。"""

    async def _make(class_id: str, name: str) -> PipeClass:
        from app.schemas.pipe_class import PipeClassCreate

        payload = PipeClassCreate(
            class_id=class_id,
            class_name=name,
            material_standard="ASME B31.3",
            corrosion_allowance=1.6,
            design_pressure=1.0,
            design_temperature=110.0,
            dn_series_json={"min": 15, "max": 200},
            sch_series_json={"DN15": "40,80"},
            flange_class="150#",
            source="COMPANY_STD",
            version="v1",
        )
        pc = await PipeClassService.create_with_config_asset(
            db, payload=payload, actor=actor,
        )
        await PipeClassService.submit(db, pc.class_id, actor=actor)
        await PipeClassService.approve(db, pc.class_id, actor=actor)
        await PipeClassService.publish(db, pc.class_id, actor=actor)
        return pc

    return _make


async def test_set_and_get_default_pipe_class_ids(db, make_company_pc):
    """set_default_pipe_classes 写入 → get_default_pipe_class_ids 读出（按 class_id 排序）。"""
    await make_company_pc("INT-A1", "INT A1")
    await make_company_pc("INT-A2", "INT A2")
    await make_company_pc("INT-A3", "INT A3")

    tpl = ProjectTemplate(
        name=f"tpl-{uuid.uuid4().hex[:8]}",
        default_config_json={},
        version="v1",
        status="ACTIVE",
    )
    db.add(tpl)
    await db.flush()

    await ProjectTemplateService.set_default_pipe_classes(
        db, tpl.template_id, ["INT-A2", "INT-A1"], actor=actor,
    )
    ids = await ProjectTemplateService.get_default_pipe_class_ids(
        db, tpl.template_id,
    )
    assert ids == ["INT-A1", "INT-A2"]  # 排序输出


async def test_set_default_replaces_not_appends(db, make_company_pc):
    """设置默认等级是替换语义而非追加。"""
    await make_company_pc("INT-B1", "INT B1")
    await make_company_pc("INT-B2", "INT B2")

    tpl = ProjectTemplate(
        name="tpl-replace",
        default_config_json={},
        version="v1",
        status="ACTIVE",
    )
    db.add(tpl)
    await db.flush()

    await ProjectTemplateService.set_default_pipe_classes(
        db, tpl.template_id, ["INT-B1"], actor=actor,
    )
    await ProjectTemplateService.set_default_pipe_classes(
        db, tpl.template_id, ["INT-B2"], actor=actor,
    )
    ids = await ProjectTemplateService.get_default_pipe_class_ids(
        db, tpl.template_id,
    )
    assert ids == ["INT-B2"]


async def test_set_default_validates_existence(db, actor):
    """set_default_pipe_classes 校验等级存在 → 不存在抛 404。"""
    tpl = ProjectTemplate(
        name="tpl-validate",
        default_config_json={},
        version="v1",
        status="ACTIVE",
    )
    db.add(tpl)
    await db.flush()

    with pytest.raises(PcsError) as e:
        await ProjectTemplateService.set_default_pipe_classes(
            db, tpl.template_id, ["NONEXISTENT"], actor=actor,
        )
    assert e.value.status == 404
    assert "NONEXISTENT" in str(e.value)


async def test_get_pipe_code_template_id_returns_column_value(db):
    """get_pipe_code_template_id 返回 ProjectTemplate.pipe_code_template_id 列值。"""
    pcc_id = uuid.uuid4()
    tpl = ProjectTemplate(
        name="tpl-pcc",
        default_config_json={},
        version="v1",
        status="ACTIVE",
        pipe_code_template_id=pcc_id,
    )
    db.add(tpl)
    await db.flush()

    got = await ProjectTemplateService.get_pipe_code_template_id(
        db, tpl.template_id,
    )
    assert got == pcc_id


async def test_get_pipe_code_template_id_none_when_unset(db):
    """pipe_code_template_id 为空时返回 None。"""
    tpl = ProjectTemplate(
        name="tpl-no-pcc",
        default_config_json={},
        version="v1",
        status="ACTIVE",
    )
    db.add(tpl)
    await db.flush()

    got = await ProjectTemplateService.get_pipe_code_template_id(
        db, tpl.template_id,
    )
    assert got is None


async def test_template_has_pipe_code_template_id_column(db):
    """ProjectTemplate ORM 已声明 pipe_code_template_id 列（migration 已升）。"""
    tpl = ProjectTemplate(
        name="tpl-col",
        default_config_json={},
        version="v1",
        status="ACTIVE",
    )
    db.add(tpl)
    await db.flush()

    assert hasattr(tpl, "pipe_code_template_id")
    assert tpl.pipe_code_template_id is None