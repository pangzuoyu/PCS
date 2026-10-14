"""`resolve()` 接进生成路径。

## 这条链曾经整段是死的

2026-10-13 实测（接之前）：

| 组件 | 状态 |
|---|---|
| `resolve()`（四级合并）| **零调用方** —— 全项目 grep 只有定义 |
| `report_styles` 表 | 只有两个 GET 端点读，**没有任何写入方** |
| 唯一的生成入口 `report_builder_tasks.py` | 传**裸 `ReportStyle()`**（全默认值）|
| `heat_detail_styles()`（BASIC/DETAIL 预设）| 只有它自己的测试在调用 |

三处脱钩的合成后果：**在 UI 里改样式，对生成的 PDF 没有任何影响**；
连 ADR-0028 要求的「DETAIL 必须横向」也从来没落到输出上 ——
`heat_detail_styles("DETAIL")` 返回 `orientation="landscape"`，但没人调用它。

## 为什么这些断言是「反向」的

本文件几乎全部是「**某样东西不该再是 None / 不该再是默认值**」的断言。
它们的价值在于：如果哪天有人把接线拆掉，这些会立刻红。

一个具体的坑：**`heat_detail_styles()` 返回的是带默认值的完整 ReportStyle**，
直接当 `resolve()` 的 defaults 传进去，`exclude_unset` 就全失效了 ——
上层只设一个字段，其余会被 presets 的值全量覆盖。所以下面
`test_presets_are_not_wrecked_by_exclude_unset` 专门盯这一点。
"""
from __future__ import annotations

import uuid

import pytest

from app.services.report.style import ReportStyle, heat_detail_styles, resolve
from app.services.report.style_service import StyleService


class _Actor:
    def __init__(self, role="SYSTEM_ADMIN"):
        self.role = role
        self.user_id = uuid.uuid4()
        self.username = "u"

    @property
    def roles(self):
        return [self.role]


@pytest.fixture
async def session(db_session):
    return db_session


# --- 第 1 层：DETAIL 预设必须真的影响生成 ---------------------------------------


def test_detail_preset_actually_reaches_a_style():
    """ADR-0028 的核心要求：DETAIL 横向。它曾经只存在于代码里。"""
    assert heat_detail_styles("DETAIL", exchanger_type="AIR_COOLER").orientation \
        == "landscape"


def test_resolve_is_no_longer_dead_code():
    """`resolve()` 曾零调用方。本测试**自己**调它 ——
    真正的守卫在下面的 `test_generation_task_builds_style_from_layers`：
    它证明生产路径会走到这里，而不只是「有个函数存在」。
    """
    out = resolve(defaults=ReportStyle(), runtime=ReportStyle(font_size_body=30))
    assert out.font_size_body == 30


# --- 第 2 层：四层合并语义在真实数据上成立 -------------------------------------


async def test_by_type_overrides_company_defaults(session):
    svc = StyleService(session)
    defaults = ReportStyle(font_size_body=10, font_family_cn="宋体")
    by_type = ReportStyle.model_validate(
        (await svc.create(report_type="HEAT", project_id=None,
                          patch={"font_size_body": 11}, actor=_Actor())).style_json)

    merged = resolve(defaults=defaults, by_type=by_type)
    assert merged.font_size_body == 11, "报表类型级没有盖过默认级"
    assert merged.font_family_cn == "宋体", "未设置的字段不该被上层清掉"


async def test_project_layer_overrides_by_type(session):
    """项目级压过公司标准 —— ADR-P8-001 的优先级方向。

    反过来（公司标准压项目）会让「项目级样式」这一层失去意义，
    所以这条的方向性本身就是契约。
    """
    svc = StyleService(session)
    by_type = ReportStyle.model_validate(
        (await svc.create(report_type="HEAT", project_id=None,
                          patch={"font_size_body": 11}, actor=_Actor())).style_json)
    project = ReportStyle.model_validate(
        (await svc.create(report_type="HEAT", project_id=uuid.uuid4(),
                          patch={"font_size_body": 13}, actor=_Actor())).style_json)
    assert resolve(defaults=ReportStyle(), by_type=by_type, project=project) \
        .font_size_body == 13


async def test_locked_fields_survive_a_project_layer(session):
    """⚠️ 公司强制标准任何层都改不了 —— 包括项目级。"""
    svc = StyleService(session)
    project = ReportStyle.model_validate(
        (await svc.create(report_type="HEAT", project_id=uuid.uuid4(),
                          patch={"page_size": "A3"},
                          actor=_Actor())).style_json)
    merged = resolve(defaults=ReportStyle(page_size="A4"), project=project)
    assert merged.page_size == "A4", "locked_fields 被项目级解锁了"


# --- 第 3 层：生成路径真的调了它 ------------------------------------------------


async def test_generation_task_builds_style_from_layers(session, monkeypatch):
    """⚠️ **端到端**：ARQ 任务体里用的样式必须来自四层合并，
    而不是裸 `ReportStyle()`。

    这是整个接线的根断言。前两条测的是「合并函数对不对」，
    这条测的是「有没有人真的调它」—— 而后者曾经完全不成立：
    `report_builder_tasks.py` 传的是 `ReportStyle()`，
    于是 ADR-0028 的 DETAIL 横向从来没出现在任何一份 PDF 上。
    """

    svc = StyleService(session)
    # 作用域用**主数据源名**（不是自造的 "CUSTOM"）—— 与 `_build_style`
    # 的取法一致。用 "CUSTOM" 会让所有自定义报表共用一条样式。
    await svc.create(report_type="HEAT_RESULTS", project_id=None,
                     patch={"font_size_body": 42}, actor=_Actor())

    captured: dict = {}

    async def fake_store(db, *, blocks, project_id, output_format, style,
                         ctx, title, assumed_fields=None, audit_detail=None):
        captured["style"] = style
        captured["title"] = title
        raise RuntimeError("stop-after-capture")   # 渲染不必真跑

    monkeypatch.setattr(
        "app.services.report.report_service.store_rendered", fake_store)

    from app.workers import report_builder_tasks as tasks

    with pytest.raises(RuntimeError):
        await tasks._render_and_store(
            db=session, project_id=uuid.uuid4(), out=_FakeOutput(),
            job_id="j1", output_format="pdf",
        )

    assert captured.get("style") is not None, "没抓到样式 —— 任务体没传"
    assert captured["style"].font_size_body == 42, \
        "公司标准里设的字号没进生成 —— 样式仍未接线"


class _FakeOutput:
    """`execute_definition` 的最小返回值，够 `_render_and_store` 渲染。

    `snapshot` 必须长得像真的 `condition_snapshot` —— `_build_style` 从里面
    取 `DataSources` / `SelectedFields` / `detailLevel`，空 dict 会让它
    退化成 `"CUSTOM"` + BASIC（于是公司标准查不到，测试变成在测兜底路径）。
    """

    headers = ["tag_number"]
    rows = [["E-101"]]
    row_count = 1
    truncated = False
    def_version = "0.1.0"
    snapshot: dict = {
        "DataSources": [{"source": "HEAT_RESULTS", "alias": "换热"}],
        "SelectedFields": [{"source": "HEAT_RESULTS", "field": "tag_number",
                            "alias": "位号", "order": 0, "visible": True}],
        "detailLevel": "BASIC",
        "project_id": "", "max_rows": 10000, "output_format": "pdf",
    }


# --- presets 与 exclude_unset 的相容性 ----------------------------------------


def test_presets_are_sparse_enough_to_be_a_layer():
    """⚠️ `heat_detail_styles()` 返回的是**稀疏**对象（pydantic v2 只把
    显式构造的字段算作已设置），所以它可以安全地当 `resolve()` 的**上层**。

    若哪天有人改成返回 `ReportStyle()` 全量填充的副本，
    `exclude_unset` 就会失效 —— 那一层会把 defaults 的其余字段全刷成
    preset 的值，用户存的项目级设置被静默清空。这条断言钉住「保持稀疏」。
    """
    detail = heat_detail_styles("DETAIL", exchanger_type="AIR_COOLER")
    assert detail.model_fields_set == {
        "orientation", "font_size_body", "font_size_heading", "table",
        "heat_exchanger_type"}, \
        f"预设的已设置字段变了：{sorted(detail.model_fields_set)}"


def test_detail_preset_must_be_the_defaults_layer_not_an_upper_layer():
    """⚠️ ADR-0028 的「DETAIL 必须横向」**只有一种接法能落地**。

    把 DETAIL 预设当 `by_type` 层传给 `resolve()` 是**无效的** ——
    `orientation` 在 `locked_fields` 里，`resolve()` 拒绝任何层改它，
    而 `orientation` 恰恰是预设要设的字段。实测：预设走 by_type 层时
    `merged.orientation == "portrait"`，横向要求被 `locked_fields` 挡掉了。

    这不是 bug 而是**设计**：`style.py` 的 docstring 写着「`locked_fields`
    只作用于 `resolve()` 的层级合并，不约束本函数 … 否则『DETAIL 必须
    横向』这条 ADR 要求永远落不了地」。预设因此必须当 **defaults 层** ——
    它自带 `locked_fields`，横向既落地又仍锁得住（谁也改不了）。

    反过来说：如果把预设当上层，用户存的公司标准**永远改不动
    orientation**，而 UI 上那是一个可编辑字段 —— 「能改但改了没用」
    比「不允许改」更糟。
    """
    preset = heat_detail_styles("DETAIL", exchanger_type="AIR_COOLER")
    assert resolve(defaults=ReportStyle(), by_type=preset).orientation \
        == "portrait", "预设走上层时 orientation 被锁 —— 这条钉住接法"

    merged = resolve(defaults=preset, by_type=ReportStyle(font_family_cn="宋体"))
    assert merged.orientation == "landscape", "预设当 defaults 才能落地横向"
    assert merged.font_family_cn == "宋体", "用户层仍能覆盖未锁字段"
