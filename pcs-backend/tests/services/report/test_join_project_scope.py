"""JOIN 的项目隔离 —— b6 遗漏（用户 2026-10-13 分析发现）。

## 症状

`_fetch_join_rows` 只按 `WHERE 关联键 IN (...)` 从表取数，**不带项目过滤**：

```python
rows_by_source[extra] = await _fetch_join_rows(
    db, source=extra, join_field=b_key,
    keys=[r.get(a_key) for r in main_rows if r.get(a_key) is not None])
```

而位号的唯一性是**项目内**唯一（`.wolf/cerebrum.md`：tag_number NOT NULL
且「unique per project」）。于是**两个项目用同一个位号**时，从表那次
`IN (...)` 会把**别人项目的行也捞进来**。

## 为什么连症状都没有

`query_engine.assemble` 对重复关联键的处理是
`{row.get(b_key): row for row in rows_by_source[b]}` —— **取最后一条**，
既不报错也不告警（注释写着「与 SQL JOIN 的行为一致」）。

所以不是「行数爆炸」，而是「**悄悄挂上了别人项目的那一行**」：
报表 200、行数正常、列也齐，只是某个字段的值来自另一个项目。
用户要过很久才会发现，而发现时通常已经当成设计值用了。

**这比报错严重得多** —— 报错会让人停下，串数据不会。

## 修法

从表侧**带上与主表相同的项目过滤**。与主源那条一样是「越权边界」，
不是「用户条件的一部分」：独立与 `WHERE` 合并，谁也替代不了谁。

## 公司级目录（SUPPLIERS）是例外且有意

`SUPPLIERS` 供应商名录没有 `project_id` 列 —— 它本来就是公司级共享目录。
对它加项目过滤会直接查不出任何行。故按「该源有没有 project_id」分支，
而不是硬编码源名。
"""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.calc import PumpResult
from app.models.equipment import EquipmentList

pytestmark = pytest.mark.asyncio


#: EQUIP_LIST / PUMP_RESULTS 都登记了它（`_add_project_columns` 按
#: 「表上有这列」自动登记）。故意用它当返回值列 —— 那正是**串数据**
#: 最可能被肉眼忽略的位置（一个编号，不同项目重复很正常）。
_PUMP_ID_FIELD = "pump_id"


async def _project(db: AsyncSession):
    """最小 Project 行。

    ⚠️ `projects` 有 8 个「NOT NULL 且无默认」的列（location / project_type /
    design_phase / unit_system / workspace_id …）—— 漏一个的症状是
    `IntegrityError: NOT NULL constraint failed`，看着像 schema 有问题，
    实际是 fixture 没填全。列表取自
    `[c.name for c in Project.__table__.columns if not c.nullable and
      c.default is None and c.server_default is None]`。
    """
    from app.models.project import Project

    pid = uuid.uuid4()
    db.add(Project(
        project_id=pid, project_no=f"P-{pid.hex[:8]}", project_name="t",
        owner_company="t", location="t", project_type="test",
        design_phase="BASIC", unit_system="SI", status="ACTIVE",
        workspace_id=uuid.uuid4(),
    ))
    await db.flush()
    return pid


async def _equipment(db: AsyncSession, *, project_id, tag: str):
    row = EquipmentList(
        equipment_id=uuid.uuid4(),
        project_id=project_id,
        workspace_id=uuid.uuid4(),
        type_code="PUMP", equipment_name=f"E-{tag}", tag_number=tag,
    )
    db.add(row)
    return row


def _pump(*, project_id, tag: str) -> PumpResult:
    return PumpResult(
        pump_id=uuid.uuid4(),
        project_id=project_id,
        workspace_id=uuid.uuid4(),
        tag_number=tag,
        basic_info_json={}, fluid_properties_json={}, flow_rates_json={},
        suction_calculation_json={}, discharge_calculation_json={},
        differential_pressure_json={}, design_pressure_json={},
        power_consumption_json={},
    )


#: SelectedFields 的顺序 = 结果表的列序（0=位号, 1=泵记录）
_COL_PUMP = 1


async def _execute(db: AsyncSession, def_id, *, user_id, project_id):
    """执行一份定义 —— **先发布**。

    ⚠️ `execute_definition` 拒绝 DRAFT（409 `REPORT_DEFINITION_STATE`）。
    这个 409 是对的，但症状是「明明刚建的定义却说不能执行」，
    不知道的人会以为是权限问题。
    """
    from app.services.report.definition_service import DefinitionService
    from app.services.report.builder_service import execute_definition

    await DefinitionService(db).publish(def_id=def_id)
    await db.commit()
    return await execute_definition(db, def_id=def_id, user_id=user_id,
                                    project_id=project_id)


async def _definition(db: AsyncSession, *, project_id, user_id):
    from app.services.report.definition_service import DefinitionService

    return await DefinitionService(db).create(
        name=f"JOIN 项目隔离 {uuid.uuid4().hex[:6]}", category="测试",
        description="", output_format="csv", shared_with="ALL_USERS",
        project_id=project_id, user_id=user_id,
        definition_json={
            "DataSources": [{"source": "EQUIP_LIST"},
                            {"source": "PUMP_RESULTS"}],
            "SelectedFields": [
                {"source": "EQUIP_LIST", "field": "tag_number",
                 "alias": "位号", "order": 0, "visible": True},
                {"source": "PUMP_RESULTS", "field": _PUMP_ID_FIELD,
                 "alias": "泵记录", "order": 1, "visible": True},
            ],
            "FilterConditions": [], "SortBy": [], "MaxRows": 100,
            "OutputFormat": "csv", "detailLevel": "BASIC",
        },
    )


async def test_two_projects_sharing_a_tag_do_not_bleed_into_each_other(db_session):
    """⚠️ **根断言**：两个项目用**同一个位号**，报表只能拿到本项目那台泵。

    修法前后都能跑通、都能返回 200 —— 区别只在 `PUMP_RESULTS.pump_id`
    那一列是本项目的还是别人的。这正是它危险的地方。
    """
    from app.services.report.builder_service import execute_definition

    user_id = uuid.uuid4()
    pid_a, pid_b = await _project(db_session), await _project(db_session)
    await _equipment(db_session, project_id=pid_a, tag="P-1001")
    await _equipment(db_session, project_id=pid_b, tag="P-1001")
    pump_a = _pump(project_id=pid_a, tag="P-1001")
    pump_b = _pump(project_id=pid_b, tag="P-1001")
    db_session.add_all([pump_a, pump_b])
    await db_session.commit()

    d = await _definition(db_session, project_id=pid_a, user_id=user_id)
    out = await _execute(db_session, d.def_id, user_id=user_id, project_id=pid_a)

    assert len(out.rows) == 1, f"应只有项目 A 的那台设备，实得 {out.rows}"
    # ⚠️ `ExecutionResult.rows` 是 **list[list]**（已按 SelectedFields
    # 排好列序），不是 list[dict] —— 写 `rows[0][...]` 当 dict 用会得到
    # 「'list' object has no attribute 'get'」。
    assert out.headers[0] == "位号" and out.headers[_COL_PUMP] == "泵记录", \
        f"列序与 SelectedFields 不符：{out.headers}"
    got = out.rows[0][_COL_PUMP]
    # 返回的是**原生 UUID 对象**（不是 str）—— 与 `_project_field` 那条
    # 注释里说的 bind processor 同一类事实，别拿 str 去比。
    assert got == pump_a.pump_id, \
        (f"关联到了别人项目的泵！A 应为 {pump_a.pump_id}，"
         f"B 是 {pump_b.pump_id}，实得 {got}")


async def test_the_missing_link_is_absent_not_null(db_session):
    """没有对应泵记录时是**缺键**，不是 None —— 两者在导出时含义不同。

    若这条也变成 None，用户会以为「这台的泵数据是空的」，
    而真相是「这台设备根本没做过泵计算」。
    """
    from app.services.report.builder_service import execute_definition

    user_id = uuid.uuid4()
    pid = await _project(db_session)
    await _equipment(db_session, project_id=pid, tag="P-2002")
    await db_session.commit()

    d = await _definition(db_session, project_id=pid, user_id=user_id)
    out = await _execute(db_session, d.def_id, user_id=user_id, project_id=pid)

    assert len(out.rows) == 1
    assert out.rows[0][_COL_PUMP] is None, \
        "没关联上的泵列应是 None（缺键在 assemble 后表现为该列为 None）"


async def test_same_project_join_still_works(db_session):
    """⚠️ 反向守卫：加项目过滤**不能**把正常的同项目关联也滤掉。

    这条与上面那条构成**双向断言** —— 只写「跨项目不泄漏」的话，
    一个「一律返回空」的修复同样能过。必须同时证明同项目照样关联得上。
    """
    from app.services.report.builder_service import execute_definition

    user_id = uuid.uuid4()
    pid = await _project(db_session)
    await _equipment(db_session, project_id=pid, tag="P-3003")
    pump = _pump(project_id=pid, tag="P-3003")
    db_session.add(pump)
    await db_session.commit()

    d = await _definition(db_session, project_id=pid, user_id=user_id)
    out = await _execute(db_session, d.def_id, user_id=user_id, project_id=pid)

    assert out.rows[0][_COL_PUMP] == pump.pump_id


async def test_company_level_sources_are_not_project_filtered(db_session):
    """⚠️ 公司级目录（`SUPPLIERS`）**不能**被项目过滤。

    它没有 `project_id` 列 —— 加了过滤就是永远查不出任何行，
    表现为「供应商列整列空白」，而那看起来像数据缺失不像配置错误。
    故按「该源有没有 project_id」分支，不硬编码源名。
    """
    from app.services.report.datasource_registry import DATASOURCES

    suppliers = DATASOURCES["SUPPLIERS"]
    assert "project_id" not in suppliers.fields, \
        ("前提变了：SUPPLIERS 现在有 project_id —— "
         "那么它应该被项目隔离，本测试与实现都要改（这是有意的提醒）")
    assert "project_id" in DATASOURCES["PUMP_RESULTS"].fields
