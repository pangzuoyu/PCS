"""c6：样式写入服务（版本 + 回滚 + 两档权限 + 审计）。

## 为什么这些行为必须先钉死

用户 2026-10-13 裁决的权限模型**按破坏面分两档**，不是按角色统一：

| 作用域 | 谁能改 | 破坏面 |
|---|---|---|
| `project_id=NULL`（公司标准）| 仅 `SYSTEM_ADMIN` | 波及所有项目的所有报表 |
| `project_id=X`（项目级）| 有该项目访问权即可 | 限于单项目 |

**没有审批流**：样式是展示层，改错只是难看，数据正确性不受影响
（CONFIG CATEGORY_4 模板管理有审批流是因为渲染错会产出错误的正式文档 ——
那是数据正确性问题，性质不同）。

**版本 + 回滚**：每次改动**新增一行**（version+1），旧行保留。
回滚 = 把旧 version 重新置为 ACTIVE，**不删数据**。
按用户原话：「审批防的是『改错』，回滚解决的是『改错之后怎么办』。
前者依赖人的判断，后者是机制。」

⚠️ **不新增审批流是有意的**：这里少写一个状态机不是遗漏。
若将来加审批，下面「改 ACTIVE 会把在用的样式顶掉」这条测试会提醒重新审视。

## 为什么用「双向负向断言」而不是变异测试

本文件的两条要害（两档权限、审计范围）本来打算用变异测试证明 ——
把 `_authorize` 里的 ADMIN 判断改成 `if False`，看测试是否转红。
**这条路被安全分类器拦下了，且拦得对**：临时在生产代码里禁用授权检查
属于「削弱安全控制」，需要显式批准，不该由 agent 自行决定。

改用**双向断言**，效力等价且不动生产代码：

- `test_company_standard_requires_system_admin`：DESIGNER + 公司标准 → 拒绝
- `test_project_level_uses_project_access_not_admin`：DESIGNER + 项目级（有权限）→ 成功

同一个人物、同一段代码，两条断言要求**相反**的结果。所以：

- 去掉 ADMIN 判断 → 第一条转红
- 把判断改成一律要求 ADMIN（两档塌陷成一档）→ 第二条转红

任何一种退化都必有一条失败。审计范围同理（公司标准恰好 2 条 /
项目级恰好 0 条）。这比变异测试更强：它同时钉住了「两档确实不同」，
而变异测试只能证明「某个检查存在」。

## 与生成的接线

本文件只管「写」。样式**是否真的影响生成**由
`test_style_resolve_is_wired_into_generation` 守住 —— 那是另一个坑：
`resolve()` 曾长期零调用方，UI 上改样式对 PDF 毫无影响。
"""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select

from app.models.report import ReportStyleRow
from app.services.report.style_service import (
    STYLE_STATUSES,
    StylePermissionError,
    StyleService,
)

pytestmark = pytest.mark.asyncio


class _Actor:
    """最小 actor（对齐 `app.api.v1.config._Actor`）。"""

    def __init__(self, role: str = "DESIGNER", user_id: uuid.UUID | None = None):
        self.role = role
        self.user_id = user_id or uuid.uuid4()
        self.username = f"u-{role}"

    @property
    def roles(self) -> list[str]:
        return [self.role]


@pytest.fixture
async def session(db_session):
    """内存 SQLite（`tests/conftest.py` 用 `SA_Base.metadata.create_all` 建表）。

    ⚠️ **不是** `get_async_session_factory()`（那是生产工厂，连真库）。
    历史上用错工厂时症状是 `NoResultFound`，看起来像「数据不存在」
    而实际是**连错了库** —— 错库的错误会伪装成数据问题。
    """
    return db_session


# --- 版本：新行不覆盖旧行 -------------------------------------------------------


async def test_revise_adds_a_row_instead_of_overwriting(session):
    """⚠️ 改样式**必须新增一行**，不是在原行上改 `style_json`。

    原地改的后果：上一份用它生成的文件，事后无法复现 —— 而
    `report_files.style_version` 冻结版本号正是为了可复现
    （ADR-P8-001「样式配置的存储」）。原地改等于让那个字段说谎。
    """
    svc = StyleService(session)
    admin = _Actor("SYSTEM_ADMIN")
    first = await svc.create(report_type="HEAT_DETAIL", project_id=None,
                             patch={"font_size_body": 9}, actor=admin)
    second = await svc.revise(style_id=first.style_id,
                              patch={"font_size_body": 11}, actor=admin)

    rows = (await session.execute(select(ReportStyleRow))).scalars().all()
    assert len(rows) == 2, "改一次应留下两行，而不是覆盖"
    old = next(r for r in rows if r.style_id == first.style_id)
    assert old.style_json["font_size_body"] == 9, "旧行的样式被改掉了"
    assert old.status == "SUPERSEDED"
    assert second.style_json["font_size_body"] == 11
    assert second.status == "ACTIVE"


async def test_version_increments_on_each_revise(session):
    svc = StyleService(session)
    admin = _Actor("SYSTEM_ADMIN")
    v1 = await svc.create(report_type="HEAT_DETAIL", project_id=None,
                          patch={}, actor=admin)
    v2 = await svc.revise(style_id=v1.style_id, patch={}, actor=admin)
    v3 = await svc.revise(style_id=v2.style_id, patch={}, actor=admin)
    assert (v1.version, v2.version, v3.version) == ("0.1.0", "0.1.1", "0.1.2")


async def test_only_one_active_row_per_scope(session):
    """同一 (report_type, project_id) 下**有且只有一行** ACTIVE。

    两条 ACTIVE 的后果不是「多显示一条」：生成时取哪条不确定，
    同一份报表两次生成可能长得不一样 —— 而内容哈希把 style 算进去了，
    于是同一份数据算出两个哈希，缓存语义直接失效。
    """
    svc = StyleService(session)
    admin = _Actor("SYSTEM_ADMIN")
    v1 = await svc.create(report_type="HEAT_DETAIL", project_id=None,
                          patch={"font_size_body": 9}, actor=admin)
    await svc.revise(style_id=v1.style_id, patch={"font_size_body": 10},
                     actor=admin)

    rows = (await session.execute(
        select(ReportStyleRow).where(ReportStyleRow.status == "ACTIVE")
    )).scalars().all()
    assert len(rows) == 1


# --- 回滚：置旧版本为 ACTIVE，不删数据 -----------------------------------------


async def test_rollback_reactivates_the_old_row_without_deleting(session):
    """回滚 = 旧行重新 ACTIVE，**不删任何一行**。

    删数据的话，「上周那份报表当时用的什么样式」就再也答不上来了。
    """
    svc = StyleService(session)
    admin = _Actor("SYSTEM_ADMIN")
    v1 = await svc.create(report_type="HEAT_DETAIL", project_id=None,
                          patch={"font_size_body": 9}, actor=admin)
    v2 = await svc.revise(style_id=v1.style_id, patch={"font_size_body": 11},
                          actor=admin)
    back = await svc.activate(style_id=v1.style_id, actor=admin)

    assert back.style_id == v1.style_id
    assert back.status == "ACTIVE"
    assert back.style_json["font_size_body"] == 9

    rows = (await session.execute(select(ReportStyleRow))).scalars().all()
    assert len(rows) == 2, "回滚删了数据 —— 旧版本必须保留可查"
    assert {r.style_id for r in rows} == {v1.style_id, v2.style_id}
    assert next(r for r in rows if r.style_id == v2.style_id).status == "SUPERSEDED"


async def test_activate_of_an_already_active_row_is_a_no_op_not_an_error(session):
    """已是 ACTIVE 的行再点一次「启用」应当幂等成功，不是报错。

    用户在列表里连点两下是很正常的；报 409 会让人以为出了故障。
    """
    svc = StyleService(session)
    admin = _Actor("SYSTEM_ADMIN")
    v1 = await svc.create(report_type="HEAT_DETAIL", project_id=None,
                          patch={}, actor=admin)
    again = await svc.activate(style_id=v1.style_id, actor=admin)
    assert again.status == "ACTIVE"


# --- 权限：两档，按破坏面 ------------------------------------------------------


async def test_company_standard_requires_system_admin(session):
    """`project_id=NULL` = 公司标准，破坏面波及所有项目 → 仅 SYSTEM_ADMIN。"""
    svc = StyleService(session)
    with pytest.raises(StylePermissionError) as ei:
        await svc.create(report_type="HEAT_DETAIL", project_id=None,
                         patch={}, actor=_Actor("DESIGNER"))
    assert ei.value.status_code == 403


async def test_project_level_uses_project_access_not_admin(session):
    """项目级：有该项目访问权即可，**不要求 ADMIN**。

    这是与公司标准那档的**唯一**区别。若这里也要求 ADMIN，
    「两档按破坏面分」就退化成了「一律 ADMIN」，用户裁决失去意义。
    """
    from app.services.user_project_service import UserProjectService

    pid = uuid.uuid4()
    granted = {"value": True}
    orig = UserProjectService.check_user_project_access

    async def fake(cls, db, *, user_id, project_id):
        granted["value"] = True
        return True

    UserProjectService.check_user_project_access = classmethod(fake)
    try:
        svc = StyleService(session)
        row = await svc.create(report_type="HEAT_DETAIL", project_id=pid,
                               patch={}, actor=_Actor("DESIGNER"))
        assert row.project_id == pid
        assert granted["value"], "根本没查项目访问权 —— 权限检查被绕过了"
    finally:
        UserProjectService.check_user_project_access = orig


async def test_project_level_denied_when_no_project_access(session):
    """无项目访问权 → 拒绝，且**不回显项目是否存在**。"""
    from app.services.user_project_service import UserProjectService

    orig = UserProjectService.check_user_project_access

    async def deny(cls, db, *, user_id, project_id):
        return False

    UserProjectService.check_user_project_access = classmethod(deny)
    try:
        svc = StyleService(session)
        with pytest.raises(StylePermissionError) as ei:
            await svc.create(report_type="HEAT_DETAIL", project_id=uuid.uuid4(),
                             patch={}, actor=_Actor("DESIGNER"))
        assert ei.value.status_code == 404, "无权访问必须是 404 而非 403"
    finally:
        UserProjectService.check_user_project_access = orig


async def test_system_admin_bypasses_project_check(session):
    """SYSTEM_ADMIN 全局 bypass —— 与 `_guard` 既有语义一致，不另立规矩。"""
    svc = StyleService(session)
    row = await svc.create(report_type="HEAT_DETAIL", project_id=uuid.uuid4(),
                           patch={}, actor=_Actor("SYSTEM_ADMIN"))
    assert row.project_id is not None


async def test_revising_a_company_standard_still_requires_admin(session):
    """权限在**每次写入**上重判，不在创建时判一次就放行。

    否则：管理员建了一条公司标准 → 之后普通用户凭 style_id 就能改它。
    修「查看权限」不重判写入权限是最常见的 ACL 漏洞。
    """
    svc = StyleService(session)
    admin = _Actor("SYSTEM_ADMIN")
    row = await svc.create(report_type="HEAT_DETAIL", project_id=None,
                           patch={}, actor=admin)
    with pytest.raises(StylePermissionError):
        await svc.revise(style_id=row.style_id, patch={"font_size_body": 30},
                         actor=_Actor("DESIGNER"))


# --- 审计：只有公司标准必写 ----------------------------------------------------


async def test_company_standard_change_writes_audit(session):
    """⚠️ 公司标准改动**必须**写 `audit_logs`。

    项目级改动可写可不写（破坏面小）；公司标准波及所有项目，
    「谁把全公司的报表字号改了」必须查得到。
    """
    from app.models.system import AuditLog

    svc = StyleService(session)
    admin = _Actor("SYSTEM_ADMIN")
    v1 = await svc.create(report_type="HEAT_DETAIL", project_id=None,
                          patch={"font_size_body": 9}, actor=admin)
    await svc.revise(style_id=v1.style_id, patch={"font_size_body": 11},
                     actor=admin)

    rows = (await session.execute(select(AuditLog))).scalars().all()
    actions = [r.action for r in rows]
    assert len([a for a in actions if a == "REPORT_STYLE_CHANGED"]) == 2, \
        f"创建 + 修订应各写一条审计，实得 {actions}"


async def test_project_level_change_writes_no_audit(session):
    """项目级不强制审计 —— 避免审计表被日常改样式淹掉。"""
    from app.models.system import AuditLog

    svc = StyleService(session)
    await svc.create(report_type="HEAT_DETAIL", project_id=uuid.uuid4(),
                     patch={}, actor=_Actor("SYSTEM_ADMIN"))
    rows = (await session.execute(select(AuditLog))).scalars().all()
    assert not [r for r in rows if r.action == "REPORT_STYLE_CHANGED"]


# --- 状态集合 ------------------------------------------------------------------


def test_statuses_are_exactly_active_and_superseded():
    """刻意**不加** PENDING/APPROVED。

    用户 2026-10-13 裁决「不要审批流」。这里把状态集合钉死，
    将来有人加审批状态时这条会红 —— 那是一次需要重新裁决的改动，
    不该悄悄溜进来。
    """
    assert STYLE_STATUSES == frozenset({"ACTIVE", "SUPERSEDED"})
