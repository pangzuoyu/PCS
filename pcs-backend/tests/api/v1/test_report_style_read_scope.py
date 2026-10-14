"""报表样式的**读**面作用域 —— 钉住一个**有意**的越界（评审 P2 #18）。

## 这条测试在断言「一个漏洞」

`_style_readable` 对**项目级**样式直接放行：登录即可读任意项目的
`style_json`（字体、版式、明细档位）。只有公司级（`project_id IS NULL`）
才卡 `SYSTEM_ADMIN`。

这是**有意**的取舍，不是疏漏 —— 模块 docstring 写明：写项目级要查
`UserProject`（打 DB），读列表逐行查就是 N+1。

## 为什么还要写测试

因为「有意」很容易在下一次重构里变成「真的疏漏」：
有人看到 `_style_readable` 只检查一个字段，很可能顺手「补上」项目权限 ——
而那会引入 N+1，或者让跨项目读样式失败。**两种改动都会让本测试变红**，
于是决定被显式记录下来，而不是躺在 docstring 里等人去读。

⚠️ 这类「断言一个已知越界」的测试很容易被当成误报而删掉。
**请勿删。** 它不是缺陷清单的残留，它是一条产品决策的落款。
若将来决定收紧（比如加 project 集合缓存），先改这条测试，
并在提交信息里写明收紧的理由 —— 而不是删掉它。
"""
from __future__ import annotations

import pathlib
import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.report import ReportStyleRow

pytestmark = pytest.mark.asyncio


async def _project(db: AsyncSession):
    from app.models.project import Project

    pid = uuid.uuid4()
    db.add(Project(
        project_id=pid, project_no=f"P-{pid.hex[:8]}", project_name="t",
        owner_company="t", location="t", project_type="test",
        design_phase="BASIC", unit_system="SI", status="ACTIVE",
        workspace_id=uuid.uuid4()))
    await db.flush()
    return pid


def _style(*, project_id, report_type="PUMP_DATA_TABLE", version="1.0.0"):
    return ReportStyleRow(
        style_id=uuid.uuid4(), report_type=report_type, project_id=project_id,
        style_json={"page_size": "A4", "font_size_body": 10},
        version=version, status="ACTIVE")


async def test_project_scoped_style_is_readable_by_any_authenticated_user(db):
    """**当前行为**：别的项目的样式也读得到。

    这不是「应该这样」，是「**目前就是这样**」。测试的作用是让任何
    收紧或放大的改动都必须显式经过这里。
    """
    from app.api.v1.report import _style_readable

    other_project = uuid.uuid4()
    row = _style(project_id=other_project)

    readable = _style_readable(
        row, actor_roles=[], user_id=uuid.uuid4())

    assert readable is True, (
        "项目级样式不再对任意已认证用户可读了 —— 若这是**有意收紧**"
        "（例如加了 project 集合缓存以避开 N+1），请一并更新本文件的"
        "docstring 与提交信息；若是误改，这是安全问题。")


async def test_company_wide_style_still_requires_system_admin(db):
    """公司级样式必须卡 `SYSTEM_ADMIN` —— 收紧不能把这条也一起放松了。"""
    from app.api.v1.report import _style_readable

    row = _style(project_id=None)

    assert _style_readable(row, actor_roles=[], user_id=uuid.uuid4()) is False
    assert _style_readable(row, actor_roles=["SYSTEM_ADMIN"],
                           user_id=uuid.uuid4()) is True


async def test_the_asymmetry_with_the_write_path_is_still_documented():
    """读放宽、写收紧 —— 这个**不对称**必须与 docstring 写的一致。

    读面 `_style_readable` 放行项目级，写面 `style_service` 查 `UserProject`。
    两边若哪天对称了，多半是有人只改了其中一边；本测试逼着那种改动
    同时更新两侧的说明。
    """
    from app.api.v1.report import _style_readable as reader
    from app.services.report import style_service

    read_doc = reader.__doc__ or ""
    assert "N+1" in read_doc, (
        "读面 docstring 不再说明为什么放宽 —— 那个理由是本决策的**全部依据**，"
        "没有它，后来者只会把它当疏漏")
    # ⚠️ 断言的是**模块源码**而不是 docstring —— `UserProject` 出现在
    # 函数体里（`check_user_project_access` 的调用点），不在文档串里。
    # 只扫 docstring 会让这条恒假，而恒假同样有害。
    write_src = pathlib.Path(style_service.__file__).read_text(encoding="utf-8")
    assert "UserProject" in write_src, (
        "写面不再提到 UserProject —— 那正是读面放宽的理由。"
        "⚠️ 曾经在这里写过 `... or True`，断言恒真、等于没写；"
        "断言恒真比不写更糟：它让人以为这一条被覆盖了。")
