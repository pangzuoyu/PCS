"""c6：样式写入端点契约。

## 端点

| 端点 | 语义 |
|---|---|
| `POST /report/styles` | 建一条 ACTIVE 样式 |
| `POST /report/styles/{id}/revise` | 改 = 新增一行 version+1 |
| `POST /report/styles/{id}/activate` | 回滚 = 旧版本重新 ACTIVE |

## 这里测什么、不测什么

**权限的完整语义在 `tests/services/report/test_style_service.py`**
（两档、回滚、审计）。本文件只测「端点把服务层的语义接对了」：
状态码对不对、响应体带不带对的东西、**写入面被禁的字段有没有真的被禁**。

⚠️ `client` fixture 默认 bypass `UserProject` guard（返回有权限），
所以这里能干净地测**公司标准那一档**的 ADMIN 闸 —— 那一档不走
`check_project_access_or_404`，不会被 fixture 绕过。
"""
from __future__ import annotations

import uuid

import pytest

from app.core.security import create_access_token


def _auth(role: str) -> dict:
    return {"Authorization": f"Bearer {create_access_token(subject='u', role=role)}"}


@pytest.fixture
def auth_admin():
    return _auth("SYSTEM_ADMIN")


@pytest.fixture
def auth_designer():
    return _auth("DESIGNER")


CREATE = "/api/v1/report/styles"


# --- 建 ----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_returns_201_with_the_summary_shape(client, auth_admin):
    r = await client.post(CREATE, headers=auth_admin, json={
        "report_type": "HEAT_DETAIL", "project_id": None,
        "style": {"font_size_body": 9}})
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["version"] == "0.1.0"
    assert body["status"] == "ACTIVE"
    assert body["style"]["font_size_body"] == 9
    assert body["style_id"]


@pytest.mark.asyncio
async def test_company_standard_requires_admin(client, auth_designer):
    """公司标准（project_id=NULL）仅 SYSTEM_ADMIN 可建。"""
    r = await client.post(CREATE, headers=auth_designer, json={
        "report_type": "HEAT_DETAIL", "project_id": None, "style": {}})
    assert r.status_code == 403, r.text


@pytest.mark.asyncio
async def test_second_active_style_in_same_scope_is_409(client, auth_admin):
    """同作用域已有 ACTIVE 时再建 → 409，不是静默并存。

    两条 ACTIVE 的后果不是「多显示一条」：生成时取哪条不确定，
    同一份报表两次生成可能长得不一样。
    """
    payload = {"report_type": "HEAT_DETAIL", "project_id": None, "style": {}}
    assert (await client.post(CREATE, headers=auth_admin, json=payload)).status_code == 201
    again = await client.post(CREATE, headers=auth_admin, json=payload)
    assert again.status_code == 409, again.text


@pytest.mark.asyncio
async def test_company_and_project_scopes_do_not_collide(client, auth_admin):
    """⚠️ `project_id=NULL` 与某个具体 project 是**两个作用域**。

    若按 `report_type` 唯一而不区分 project，第二条项目级样式会被
    误判成「重复」。
    """
    pid = str(uuid.uuid4())
    a = await client.post(CREATE, headers=auth_admin, json={
        "report_type": "HEAT_DETAIL", "project_id": None, "style": {}})
    b = await client.post(CREATE, headers=auth_admin, json={
        "report_type": "HEAT_DETAIL", "project_id": pid, "style": {}})
    assert (a.status_code, b.status_code) == (201, 201), (a.text, b.text)


# --- 改 / 回滚 ----------------------------------------------------------------


@pytest.mark.asyncio
async def test_revise_returns_new_version_and_keeps_the_old_row(client, auth_admin):
    sid = (await client.post(CREATE, headers=auth_admin, json={
        "report_type": "HEAT_DETAIL", "project_id": None,
        "style": {"font_size_body": 9}})).json()["style_id"]

    r = await client.post(f"{CREATE}/{sid}/revise", headers=auth_admin,
                          json={"style": {"font_size_body": 12}})
    assert r.status_code == 200, r.text
    assert r.json()["version"] == "0.1.1"
    assert r.json()["style_id"] != sid, "改样式应产生新行，不是原地改"

    old = await client.get(f"{CREATE}/{sid}", headers=auth_admin)
    assert old.json()["style"]["font_size_body"] == 9, "旧版本的样式被覆盖了"
    assert old.json()["status"] == "SUPERSEDED"


@pytest.mark.asyncio
async def test_activate_rolls_back_without_deleting(client, auth_admin):
    v1 = (await client.post(CREATE, headers=auth_admin, json={
        "report_type": "HEAT_DETAIL", "project_id": None,
        "style": {"font_size_body": 9}})).json()
    v2 = (await client.post(f"{CREATE}/{v1['style_id']}/revise",
                            headers=auth_admin,
                            json={"style": {"font_size_body": 12}})).json()

    back = await client.post(f"{CREATE}/{v1['style_id']}/activate",
                             headers=auth_admin)
    assert back.status_code == 200, back.text
    assert back.json()["style"]["font_size_body"] == 9

    listing = await client.get(CREATE, headers=auth_admin)
    ids = {s["style_id"] for s in listing.json()["items"]}
    assert ids == {v1["style_id"], v2["style_id"]}, "回滚把历史版本删了"


@pytest.mark.asyncio
async def test_roll_back_of_a_company_style_still_requires_admin(client, auth_admin,
                                                                auth_designer):
    """回滚也是写 —— 权限在**每次写入**上重判。

    否则管理员建了公司标准后，别人凭 style_id 就能回滚它。
    """
    v1 = (await client.post(CREATE, headers=auth_admin, json={
        "report_type": "HEAT_DETAIL", "project_id": None, "style": {}})).json()
    r = await client.post(f"{CREATE}/{v1['style_id']}/activate", headers=auth_designer)
    assert r.status_code == 403, r.text


@pytest.mark.asyncio
async def test_unknown_style_id_is_404_not_500(client, auth_admin):
    r = await client.post(f"{CREATE}/{uuid.uuid4()}/activate", headers=auth_admin)
    assert r.status_code == 404, r.text


# --- 写入面必须禁的字段 --------------------------------------------------------


@pytest.mark.asyncio
async def test_font_dir_cannot_be_set_through_the_api(client, auth_admin):
    """⚠️ **`font_dir` 禁止从 API 写入**。

    它是**服务器上的文件系统路径**，PDF 渲染器拿它去定位 TTF。
    开放写入等于让调用方指定渲染器读哪个目录的文件 —— 一个目录遍历的入口。
    它应当只来自服务端配置（`get_settings().report_font_dir`）。
    """
    r = await client.post(CREATE, headers=auth_admin, json={
        "report_type": "HEAT_DETAIL", "project_id": None,
        "style": {"font_dir": "/etc"}})
    assert r.status_code == 422, r.text


@pytest.mark.asyncio
async def test_locked_fields_cannot_be_relaxed_through_the_api(client, auth_admin):
    """⚠️ **`locked_fields` 禁止从 API 写入** —— 它是「哪些字段锁死」的名单。

    放进可写字段里，用户就能传 `locked_fields: ["font_size_body"]`
    给自己解锁。公司强制标准（`page_size` / `orientation`）就再也锁不住了。
    """
    r = await client.post(CREATE, headers=auth_admin, json={
        "report_type": "HEAT_DETAIL", "project_id": None,
        "style": {"locked_fields": ["font_size_body"]}})
    assert r.status_code == 422, r.text


@pytest.mark.asyncio
async def test_unknown_style_field_is_rejected(client, auth_admin):
    """未知字段不能静默吞掉 —— 拼错字段名会「保存成功但什么都没变」。

    Pydantic 默认 `extra="ignore"`：写 `font_size_bodyy` 会通过校验、
    返回 201，而样式毫无变化。这是要消除的那一静默。
    """
    r = await client.post(CREATE, headers=auth_admin, json={
        "report_type": "HEAT_DETAIL", "project_id": None,
        "style": {"font_size_bodyy": 9}})
    assert r.status_code == 422, r.text


@pytest.mark.asyncio
async def test_invalid_page_size_is_rejected(client, auth_admin):
    """`page_size` 是 `Literal["A4","A3","Letter"]` —— 传别的必须被拒。

    渲染器按纸张尺寸取常量，拿到未知值只能抛或默默按默认渲染。
    """
    r = await client.post(CREATE, headers=auth_admin, json={
        "report_type": "HEAT_DETAIL", "project_id": None,
        "style": {"page_size": "A5"}})
    assert r.status_code == 422, r.text


# --- 读面：既有的 GET 端点也有权限洞 -------------------------------------------


@pytest.mark.asyncio
async def test_getting_a_company_style_requires_admin(client, auth_designer):
    """⚠️ 既有 `GET /styles/{id}` **完全没有权限检查** —— 任何登录用户
    都能读公司标准（以及别人的项目级样式）。IDOR。

    本轮修：读面复用同一套两档判定，与写面对齐。
    """
    sid = (await client.post(CREATE, headers=_auth("SYSTEM_ADMIN"), json={
        "report_type": "HEAT_DETAIL", "project_id": None, "style": {}})).json()["style_id"]
    r = await client.get(f"{CREATE}/{sid}", headers=auth_designer)
    assert r.status_code == 403, r.text
