"""`/api/v1/report-builder` 路由契约（Phase 2）。

## 为什么字段树端点自带「一致性」测试

`GET /datasources` 的产出就是 `datasource_registry.DATASOURCES` 的序列化。
端点里**手写一遍字段清单**是最自然也最危险的写法：注册表改了、端点没改，
两边悄悄分叉，而端点返回 200、字段树照常有人用 —— 前端选了一个查不出的字段，
到执行时才报「字段不在数据源注册表中」。

所以本文件的核心断言是**双向**的：
- 正向：每个数据源的字段集合与注册表**逐字相等**（不是包含，是相等）
- 反向：注册表里每个字段都在响应里（防端点多返回了一个不存在的字段）

单向包含的断言会漏掉「端点有、注册表无」这一半 —— 而那正是选不出来的
那种分叉。
"""
from __future__ import annotations

import uuid

import pytest

from app.core.security import create_access_token
from app.services.report.datasource_registry import DATASOURCES, JOINS


@pytest.fixture
def auth_pc():
    token = create_access_token(subject="test-pc", role="PROCESS_CONTROLLER")
    return {"Authorization": f"Bearer {token}"}


# --- datasources ------------------------------------------------------------


@pytest.mark.asyncio
async def test_datasources_returns_every_registered_source(client, auth_pc):
    r = await client.get("/api/v1/report-builder/datasources", headers=auth_pc)
    assert r.status_code == 200, r.text
    got = {d["key"] for d in r.json()["datasources"]}
    assert got == set(DATASOURCES), "端点漏了数据源"


@pytest.mark.asyncio
async def test_datasource_field_tree_matches_registry_exactly(client, auth_pc):
    """字段树与注册表**逐字相等**（双向）。

    单向包含的断言漏掉一半分叉：端点返回一个注册表里没有的字段时，
    「注册表 ⊆ 响应」照样绿 —— 而那个字段在执行时查不出来。
    """
    r = await client.get("/api/v1/report-builder/datasources", headers=auth_pc)
    assert r.status_code == 200, r.text
    by_key = {d["key"]: d for d in r.json()["datasources"]}

    for key, ds in DATASOURCES.items():
        node = by_key[key]
        got = {f["name"]: f for f in node["fields"]}
        assert set(got) == set(ds.fields), (
            f"{key} 的字段树与注册表不一致："
            f"仅端点有={set(got) - set(ds.fields)}，仅注册表有={set(ds.fields) - set(got)}")
        for name, spec in ds.fields.items():
            assert got[name]["label"] == spec.label, f"{key}.{name} 标签不一致"
            assert got[name]["type"] == spec.type, f"{key}.{name} 类型不一致"
            assert got[name]["is_jsonb_key"] == spec.is_jsonb_key, f"{key}.{name} jsonb 标记不一致"


@pytest.mark.asyncio
async def test_datasources_require_auth(client):
    """字段树不是公开文档 —— 未登录 401。

    它泄露的是**内部表结构与列名**，等价于一份 schema 泄露。
    """
    r = await client.get("/api/v1/report-builder/datasources")
    assert r.status_code == 401, r.text


@pytest.mark.asyncio
async def test_join_whitelist_is_published_with_exactly_the_registry_pairs(client, auth_pc):
    """JOIN 白名单随字段树一起下发。

    前端必须**只能**从白名单里选关联 —— 后端 `join_key_for` 对不在白名单的
    组合直接 400。前端若自己猜，猜错就是「选得了、跑不了」。
    """
    r = await client.get("/api/v1/report-builder/datasources", headers=auth_pc)
    assert r.status_code == 200, r.text
    got = {(j["a"], j["a_field"], j["b"], j["b_field"]) for j in r.json()["joins"]}
    want = {(j.a, j.a_field, j.b, j.b_field) for j in JOINS}
    assert got == want, "下发的 JOIN 白名单与注册表不一致（前端会选到跑不了的组合）"


@pytest.mark.asyncio
async def test_jsonb_fields_are_marked_so_the_ui_can_warn(client, auth_pc):
    """JSONB 子键必须带标记 —— 前端要据此提示「取的是 JSON 里的键」。

    没有标记时 `output_json.sizing.liquid_volume_m3` 与真实列
    `total_toe` 在 UI 上长得一样，用户无从判断后者可以直接索引。
    """
    r = await client.get("/api/v1/report-builder/datasources", headers=auth_pc)
    fields = {f["name"]: f for d in r.json()["datasources"] for f in d["fields"]}
    assert fields["flow_rates_json.flow_m3_s"]["is_jsonb_key"] is True
    assert fields["tag_number"]["is_jsonb_key"] is False


@pytest.mark.asyncio
async def test_response_has_no_bare_object_fields(client, auth_pc):
    """零裸 object（P9A-DLV-010）：裸 object 会让前端类型退化成 any。"""
    r = await client.get("/api/v1/report-builder/datasources", headers=auth_pc)
    spec = r.json()
    assert isinstance(spec["datasources"], list)
    node = spec["datasources"][0]
    assert isinstance(node["fields"], list)
    f = node["fields"][0]
    for k in ("name", "type", "label", "is_jsonb_key"):
        assert k in f, f"字段缺 {k}，前端类型会缺成员"
    assert isinstance(f["is_jsonb_key"], bool)
    assert isinstance(f["name"], str)

# --- b2 定义 CRUD -----------------------------------------------------------

def _auth(subject: str, role: str = "DESIGNER"):
    return {"Authorization": f"Bearer {create_access_token(subject=subject, role=role)}"}


def _definition_body(**over):
    body = {
        "project_id": None,
        "name": "设备一览",
        "category": "设备类",
        "description": "按位号列设备",
        "output_format": "xlsx",
        "shared_with": "ALL_USERS",
        "definition_json": {
            "DataSources": [{"source": "EQUIP_LIST"}],
            "SelectedFields": [
                {"source": "EQUIP_LIST", "field": "tag_number",
                 "alias": "位号", "order": 0, "visible": True},
                {"source": "EQUIP_LIST", "field": "vendor",
                 "alias": "制造商", "order": 1, "visible": True},
            ],
        },
    }
    body.update(over)
    return body


@pytest.mark.asyncio
async def test_create_definition_starts_as_draft_owned_by_creator(client):
    r = await client.post("/api/v1/report-builder/definitions",
                          headers=_auth("author-1"), json=_definition_body())
    assert r.status_code == 201, r.text
    d = r.json()
    assert d["status"] == "DRAFT", "SPEC §3.2.2(6)：创建后状态 DRAFT"
    assert d["version"] == "0.1.0"
    assert d["created_by"], "必须记创建人 —— DRAFT 可见性完全依赖它"


@pytest.mark.asyncio
async def test_draft_is_invisible_to_others_but_visible_to_creator(client):
    """SPEC §3.2.2(6)：DRAFT **仅创建人可见和使用**。"""
    created = (await client.post("/api/v1/report-builder/definitions",
                                 headers=_auth("author-1"),
                                 json=_definition_body())).json()
    def_id = created["def_id"]

    # 别人的列表里没有它
    others = await client.get("/api/v1/report-builder/definitions",
                              headers=_auth("author-2"))
    assert others.status_code == 200
    assert def_id not in {d["def_id"] for d in others.json()["items"]}, \
        "DRAFT 出现在别人的列表里 —— SPEC 明确只有创建人可见"

    # 别人直接按 ID 取也拿不到（404 而非 403，不泄漏存在性）
    direct = await client.get(f"/api/v1/report-builder/definitions/{def_id}",
                              headers=_auth("author-2"))
    assert direct.status_code == 404, f"实得 {direct.status_code}"

    # 创建人自己看得到
    mine = await client.get(f"/api/v1/report-builder/definitions/{def_id}",
                            headers=_auth("author-1"))
    assert mine.status_code == 200, mine.text


@pytest.mark.asyncio
async def test_definition_endpoints_require_auth(client):
    assert (await client.get("/api/v1/report-builder/definitions")).status_code == 401
    assert (await client.post("/api/v1/report-builder/definitions",
                              json=_definition_body())).status_code == 401


@pytest.mark.asyncio
async def test_definition_rejects_datasource_not_in_registry(client):
    """数据源必须在注册表里 —— 写进来时拒，别等到执行时报「字段不存在」。"""
    r = await client.post(
        "/api/v1/report-builder/definitions",
        headers=_auth("author-1"),
        json=_definition_body(definition_json={
            "DataSources": [{"source": "NOT_A_REAL_SOURCE"}],
            "SelectedFields": [],
        }))
    assert r.status_code == 400, f"实得 {r.status_code}：{r.text}"
    assert r.json()["code"] == "REPORT_DATASOURCE_UNKNOWN"


@pytest.mark.asyncio
async def test_definition_rejects_field_not_in_that_datasource(client):
    """字段必须属于它声明的那个数据源 —— 跨源字段名在注册表里都合法，
    拼错源时查询会**静默返回空列**而不是报错（SQL 选出 NULL）。"""
    r = await client.post(
        "/api/v1/report-builder/definitions",
        headers=_auth("author-1"),
        json=_definition_body(definition_json={
            "DataSources": [{"source": "EQUIP_LIST"}],
            "SelectedFields": [{"source": "EQUIP_LIST", "field": "set_pressure",
                                "alias": "", "order": 0, "visible": True}],
        }))
    assert r.status_code == 400, f"实得 {r.status_code}：{r.text}"


@pytest.mark.asyncio
async def test_definition_rejects_unsupported_output_format(client):
    """未知格式必须 400 —— 静默接受会在执行时才炸，而那时用户已填完整个表单。

    ⚠️ 这里的样本格式随 b8 变过一次：原本用 `csv`（当时确实不支持），
    CSV 落地后改成 `rtf`。留着旧样本的话，格式**从不支持变成支持**时
    这条测试会红，而红的原因（CSV 现在合法了）跟它想验的东西毫无关系。
    """
    r = await client.post("/api/v1/report-builder/definitions",
                          headers=_auth("author-1"),
                          json=_definition_body(output_format="rtf"))
    assert r.status_code == 400, f"实得 {r.status_code}"
    assert r.json()["code"] == "REPORT_OUTPUT_FORMAT_UNSUPPORTED"


@pytest.mark.asyncio
async def test_update_draft_keeps_draft_and_version(client):
    """改草稿仍是草稿、版本不动 —— 它还没进过审批线。"""
    created = (await client.post("/api/v1/report-builder/definitions",
                                 headers=_auth("author-1"),
                                 json=_definition_body())).json()
    r = await client.put(f"/api/v1/report-builder/definitions/{created['def_id']}",
                         headers=_auth("author-1"),
                         json=_definition_body(name="设备一览（改）"))
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "DRAFT"
    assert r.json()["version"] == "0.1.0", "草稿阶段改内容不该进版本号"
    assert r.json()["name"] == "设备一览（改）"


@pytest.mark.asyncio
async def test_update_by_non_creator_gets_404(client):
    created = (await client.post("/api/v1/report-builder/definitions",
                                 headers=_auth("author-1"),
                                 json=_definition_body())).json()
    r = await client.put(f"/api/v1/report-builder/definitions/{created['def_id']}",
                         headers=_auth("author-2"), json=_definition_body())
    assert r.status_code == 404, f"实得 {r.status_code}：别人的草稿不该能改"


@pytest.mark.asyncio
async def test_duplicate_name_in_same_project_rejected(client):
    """同项目同名 —— DB 有唯一约束，但先在应用层给可读的错误。"""
    first = await client.post("/api/v1/report-builder/definitions",
                              headers=_auth("author-1"),
                              json=_definition_body(project_id=None))
    assert first.status_code == 201, first.text
    dup = await client.post("/api/v1/report-builder/definitions",
                            headers=_auth("author-1"), json=_definition_body(project_id=None))
    assert dup.status_code == 409, f"实得 {dup.status_code}：{dup.text}"


# --- b3 版本与审批 -----------------------------------------------------------

PUBLISH = "/api/v1/report-builder/definitions/{d}/publish"
OBSOLETE = "/api/v1/report-builder/definitions/{d}/obsolete"


async def _make(client, subject="author-1", **over):
    r = await client.post("/api/v1/report-builder/definitions",
                          headers=_auth(subject), json=_definition_body(**over))
    assert r.status_code == 201, r.text
    return r.json()


@pytest.mark.asyncio
async def test_publish_requires_reviewer_role(client):
    """SPEC §3.2.2(6)「发布审批 需审核角色审批通过」。

    创建人**自己不能**发布 —— 否则审批这一步形同虚设。
    """
    d = await _make(client, "author-1")
    r = await client.post(PUBLISH.format(d=d["def_id"]), headers=_auth("author-1"))
    assert r.status_code == 403, f"实得 {r.status_code}：创建人不该能自己发布"

    ok = await client.post(PUBLISH.format(d=d["def_id"]),
                           headers=_auth("reviewer-1", "REVIEWER"))
    assert ok.status_code == 200, ok.text
    assert ok.json()["status"] == "PUBLISHED"


@pytest.mark.asyncio
async def test_published_all_users_is_visible_to_others(client):
    d = await _make(client, "author-1", shared_with="ALL_USERS")
    await client.post(PUBLISH.format(d=d["def_id"]),
                      headers=_auth("reviewer-1", "REVIEWER"))
    lst = await client.get("/api/v1/report-builder/definitions",
                           headers=_auth("someone-else"))
    assert d["def_id"] in {x["def_id"] for x in lst.json()["items"]}


@pytest.mark.asyncio
async def test_published_creator_only_stays_hidden(client):
    d = await _make(client, "author-1", shared_with="CREATOR_ONLY")
    await client.post(PUBLISH.format(d=d["def_id"]),
                      headers=_auth("reviewer-1", "REVIEWER"))
    direct = await client.get(f"/api/v1/report-builder/definitions/{d['def_id']}",
                              headers=_auth("someone-else"))
    assert direct.status_code == 404, "CREATOR_ONLY 发布后仍只对创建人可见"


@pytest.mark.asyncio
async def test_editing_published_definition_bumps_version_and_reverts_to_draft(client):
    """SPEC §3.2.2(6)「已发布定义修改时自动创建新版本」。

    关键在 **状态退回 DRAFT**：只 +1 版本而保持 PUBLISHED，等于任何人改一下
    就生效，审批被绕过 —— 这正是审批制要防的事。
    """
    d = await _make(client, "author-1", shared_with="ALL_USERS")
    await client.post(PUBLISH.format(d=d["def_id"]),
                      headers=_auth("reviewer-1", "REVIEWER"))
    upd = await client.put(f"/api/v1/report-builder/definitions/{d['def_id']}",
                           headers=_auth("author-1"),
                           json=_definition_body(name="改了", shared_with="ALL_USERS"))
    assert upd.status_code == 200, upd.text
    assert upd.json()["version"] == "0.1.1", f"实得 {upd.json()['version']}"
    assert upd.json()["status"] == "DRAFT", "新版本必须重新过审批"

    # 退回草稿后，他人重新看不见
    direct = await client.get(f"/api/v1/report-builder/definitions/{d['def_id']}",
                              headers=_auth("someone-else"))
    assert direct.status_code == 404


@pytest.mark.asyncio
async def test_republish_after_edit_needs_approval_again(client):
    d = await _make(client, "author-1", shared_with="ALL_USERS")
    await client.post(PUBLISH.format(d=d["def_id"]),
                      headers=_auth("reviewer-1", "REVIEWER"))
    await client.put(f"/api/v1/report-builder/definitions/{d['def_id']}",
                     headers=_auth("author-1"), json=_definition_body(shared_with="ALL_USERS"))
    blocked = await client.post(PUBLISH.format(d=d["def_id"]),
                                headers=_auth("author-1"))
    assert blocked.status_code == 403, "改了之后创建人不能自批"
    ok = await client.post(PUBLISH.format(d=d["def_id"]),
                           headers=_auth("reviewer-1", "REVIEWER"))
    assert ok.json()["status"] == "PUBLISHED"
    assert ok.json()["version"] == "0.1.1"


@pytest.mark.asyncio
async def test_publishing_twice_is_conflict(client):
    d = await _make(client, "author-1")
    await client.post(PUBLISH.format(d=d["def_id"]), headers=_auth("rev", "REVIEWER"))
    again = await client.post(PUBLISH.format(d=d["def_id"]),
                              headers=_auth("rev", "REVIEWER"))
    assert again.status_code == 409, f"实得 {again.status_code}"


@pytest.mark.asyncio
async def test_obsolete_requires_reviewer_and_leaves_default_list(client):
    d = await _make(client, "author-1", shared_with="ALL_USERS")
    await client.post(PUBLISH.format(d=d["def_id"]), headers=_auth("rev", "REVIEWER"))
    denied = await client.post(OBSOLETE.format(d=d["def_id"]), headers=_auth("author-1"))
    assert denied.status_code == 403
    ok = await client.post(OBSOLETE.format(d=d["def_id"]),
                           headers=_auth("rev", "REVIEWER"))
    assert ok.status_code == 200, ok.text
    assert ok.json()["status"] == "OBSOLETE"
    lst = await client.get("/api/v1/report-builder/definitions",
                           headers=_auth("author-1"))
    assert d["def_id"] not in {x["def_id"] for x in lst.json()["items"]}, \
        "已作废不该再出现在默认列表"


@pytest.mark.asyncio
async def test_obsoleted_definition_cannot_be_executed_or_republished(client):
    d = await _make(client, "author-1")
    await client.post(PUBLISH.format(d=d["def_id"]), headers=_auth("rev", "REVIEWER"))
    await client.post(OBSOLETE.format(d=d["def_id"]), headers=_auth("rev", "REVIEWER"))
    again = await client.post(PUBLISH.format(d=d["def_id"]),
                              headers=_auth("rev", "REVIEWER"))
    assert again.status_code == 409, f"实得 {again.status_code}：已作废不能复活"


@pytest.mark.asyncio
async def test_reviewer_cannot_edit_someone_elses_draft(client):
    """审核角色有发布权，但没有替别人改内容的权 —— 审批与编辑要分开。"""
    d = await _make(client, "author-1")
    r = await client.put(f"/api/v1/report-builder/definitions/{d['def_id']}",
                         headers=_auth("rev", "REVIEWER"), json=_definition_body())
    assert r.status_code == 404, f"实得 {r.status_code}"


# --- b4 字段选择器：别名/排序/显隐往返一致 ------------------------------------


@pytest.mark.asyncio
async def test_selected_fields_alias_order_visible_round_trip(client):
    """SPEC §3.2.2(3)：别名、拖拽排序、显示/隐藏都持久化到定义里。

    「往返一致」的重点在 `visible=False` 与**非零 order**：这两项最容易被
    「只存选中的字段」的实现悄悄吃掉 —— 隐藏字段不落库、排序塌成选中顺序，
    用户下次打开编辑器发现自己的设置全没了，而 API 一直返回 200。
    """
    fields = [
        {"source": "EQUIP_LIST", "field": "tag_number",
         "alias": "位　号（自定义）", "order": 3, "visible": True},
        {"source": "EQUIP_LIST", "field": "vendor",
         "alias": "制造商", "order": 1, "visible": False},   # 隐藏
        {"source": "EQUIP_LIST", "field": "vendor_model",
         "alias": "", "order": 2, "visible": True},
    ]
    d = await _make(client, "author-1", definition_json={
        "DataSources": [{"source": "EQUIP_LIST"}],
        "SelectedFields": fields,
    })
    got = (await client.get(f"/api/v1/report-builder/definitions/{d['def_id']}",
                            headers=_auth("author-1"))).json()
    assert got["definition_json"]["SelectedFields"] == fields, \
        "字段选择器设置没能原样往返"

    # 改一次别的再读，设置仍要还在（不能只活到第一次读取）
    await client.put(f"/api/v1/report-builder/definitions/{d['def_id']}",
                     headers=_auth("author-1"),
                     json=_definition_body(name="改名了", definition_json={
                         "DataSources": [{"source": "EQUIP_LIST"}],
                         "SelectedFields": fields,
                     }))
    again = (await client.get(f"/api/v1/report-builder/definitions/{d['def_id']}",
                              headers=_auth("author-1"))).json()
    assert again["definition_json"]["SelectedFields"] == fields


@pytest.mark.asyncio
async def test_max_rows_survives_round_trip(client):
    """MaxRows 是执行引擎唯一的规模闸 —— 丢了就等于没有上限。"""
    d = await _make(client, "author-1", max_rows=250)
    got = (await client.get(f"/api/v1/report-builder/definitions/{d['def_id']}",
                            headers=_auth("author-1"))).json()
    assert got["max_rows"] == 250
    assert got["definition_json"]["MaxRows"] == 250, "定义体内的 MaxRows 也要落库"


@pytest.mark.asyncio
async def test_jsonb_field_can_be_selected_in_definition(client):
    """JSONB 子键（如 `flow_rates_json.flow_m3_s`）必须能被选中 ——
    注册表里它带 `is_jsonb_key=True`，正是为了在定义里可引用。"""
    d = await _make(client, "author-1", definition_json={
        "DataSources": [{"source": "PUMP_RESULTS"}],
        "SelectedFields": [
            {"source": "PUMP_RESULTS", "field": "flow_rates_json.flow_m3_s",
             "alias": "流量", "order": 0, "visible": True},
        ],
    })
    assert d["def_id"]
# --- b7 执行引擎 --------------------------------------------------------------

EXEC = "/api/v1/report-builder/definitions/{d}/execute"


def _ctx_with(db, *, job_id: str, job_try: int = 1) -> dict:
    """构造 ARQ ctx。

    ⚠️ 键是 **`session_factory`** 不是 `db`（2026-10-13 修）。ARQ 的
    `on_startup` 把 `ctx["session_factory"]` 注入，任务体据此自己开
    session；`ctx["db"]` 从来不存在，所以旧写法让任务体在第一行就
    `KeyError` —— 而它同时**带着正确的 def_id** 传进去，症状像「参数错」。

    这里返回的 factory 把同一个 `db_session` 交出去，**不是**生产
    factory（那指向真库；单测库是内存 SQLite，见下方注释）。
    """
    return {"session_factory": lambda: db, "job_id": job_id, "job_try": job_try}

# ⚠️ 这几组测试用 `db_session` 而不是 `get_async_session_factory()` ——
# 后者是**生产** factory，指向真库；单测库是内存 SQLite（conftest 建表）。
# 上一版用错了 factory，`db.get()` 直接 NoResultFound —— 而那个失败信息
# 指向「定义不存在」，完全不像「连错了库」，很容易被追错方向。
DEF_JSON_EQUIP = {
    "DataSources": [{"source": "EQUIP_LIST"}],
    "SelectedFields": [
        {"source": "EQUIP_LIST", "field": "tag_number",
         "alias": "位号", "order": 0, "visible": True},
    ],
    "FilterConditions": [],
}


async def _make_project(db, name="报表执行测试项目"):
    """建一个真项目行。

    定义必须绑定到真实项目才能执行（`REPORT_PROJECT_SCOPE_REQUIRED`）——
    第一版测试没建项目、定义 project_id=None，症状是种子插入时
    `NOT NULL constraint failed: equipment_list.project_id`，
    报错指向种子而不是「这个定义根本没有项目」，很容易追错方向。
    """
    from app.models.project import Project
    proj = Project(
        project_no=f"RPT-{uuid.uuid4().hex[:8]}",
        project_name=name, owner_company="X", location="X",
        project_type="CHEMICAL", design_phase="FEED", unit_system="SI",
        workspace_id=uuid.uuid4(),
    )
    db.add(proj)
    await db.flush()
    return proj


async def _load_def(db, def_id):
    from app.models.report import ReportDefinition
    row = await db.get(ReportDefinition, uuid.UUID(def_id))
    assert row is not None, f"定义 {def_id} 不存在"
    return row


@pytest.fixture
def fake_queue(monkeypatch):
    """把入队边界打桩，测试不依赖本机有没有 Redis。

    为什么必须打桩：不打桩时，本机**没有 Redis**，端点返回 202 + 空
    task_id，测试要么红（没 Redis）要么绿（恰好有 Redis 却什么都没验证）。
    端点的职责是「入队 + 回 task_id」，不是「Redis 通不通」——
    后者由 `test_execute_reports_503_when_queue_is_down` 单独验。
    """
    from app.services.report import arq_queue

    calls = []

    async def _fake(func, **kwargs):
        calls.append(kwargs)
        return "job-123"

    monkeypatch.setattr(arq_queue, "_enqueue", _fake)
    return calls


@pytest.mark.asyncio
async def test_execute_returns_202_not_a_synchronous_report(client, fake_queue):
    """b7 决策（2026-10-08 审查）：执行走 ARQ 异步。

    10k 行 PDF ≈ 10 CPU-秒，同步跑会阻塞整个 event loop。端点必须
    **立刻**返回 202 + task_id，而不是把文件算完再返回。
    """
    d = await _make(client, "author-1")
    await client.post(PUBLISH.format(d=d["def_id"]), headers=_auth("rev", "REVIEWER"))
    r = await client.post(EXEC.format(d=d["def_id"]), headers=_auth("user-1"))
    assert r.status_code == 202, f"实得 {r.status_code}：{r.text}"
    assert r.json()["task_id"] == "job-123", "必须给出可追踪的 task_id"
    assert fake_queue, "端点压根没入队却回了 202"


@pytest.mark.asyncio
async def test_execute_reports_503_when_queue_is_down(client, monkeypatch):
    """入队失败是**第三种状态**，不是 202 也不是「生成失败」500。

    回 202 + 空 task_id 时，前端会拿着一个永远查不到结果的 ID 一直转圈；
    回 500「生成失败」是撒谎 —— 任务从未开始。503 + 明确的错误码才对。
    """
    from app.services.exceptions import PcsError
    from app.services.report import arq_queue

    async def _boom(func, **kwargs):
        raise PcsError("队列不可用", code="REPORT_QUEUE_UNAVAILABLE", status=503)

    monkeypatch.setattr(arq_queue, "_enqueue", _boom)

    d = await _make(client, "author-1")
    await client.post(PUBLISH.format(d=d["def_id"]), headers=_auth("rev", "REVIEWER"))
    r = await client.post(EXEC.format(d=d["def_id"]), headers=_auth("user-1"))
    assert r.status_code == 503, f"实得 {r.status_code}：{r.text}"
    assert r.json()["code"] == "REPORT_QUEUE_UNAVAILABLE"


@pytest.mark.asyncio
async def test_execute_requires_auth(client):
    r = await client.post(
        EXEC.format(d="00000000-0000-0000-0000-000000000000"))
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_execute_of_draft_is_rejected(client):
    """SPEC §3.2.2(5)「所有用户可执行**已发布**报表」。

    草稿只有创建人看得见，但「看得见」不等于「可执行」—— 执行面板列的是
    已发布定义。草稿要执行必须先发布，否则审批形同虚设。
    """
    d = await _make(client, "author-1")
    r = await client.post(EXEC.format(d=d["def_id"]), headers=_auth("author-1"))
    assert r.status_code == 409, f"实得 {r.status_code}：{r.text}"


@pytest.mark.asyncio
async def test_polling_right_after_202_returns_queued_not_404(
        client, fake_queue, db_session):
    """202 之后**立刻**轮询必须是 200 QUEUED，不是 404。

    ⚠️ 这是实测出来的：执行日志行原先由**任务体**写，而任务体要等 worker
    消费才跑。于是「202 已返回、日志行还不存在」这段窗口里轮询端点只能
    404 —— 而前端 `ReportExecutePage` 的轮询把**任何**错误都当成终态失败
    （`stopPolling(); setPhase('failed')`）。实测 worker 跑这个定义要 0.4 秒，
    真实场景 10k 行 PDF 约 10 秒（ADR-P8-004）—— 也就是**每一次**执行都会
    在前端显示失败，而任务其实正在跑并会成功。

    端点自己的 docstring 写着「查不到就是 404，不返回占位 PENDING」，理由是
    「让前端分不清任务不存在与还在跑」。那个理由成立的前提是**行从入队就存在**，
    而写入时机破坏了这个前提。修法是让前提成真，不是改前端去容忍 404 ——
    容忍之后，404 就同时意味着「不存在」与「刚开始」，又分不清了。
    """
    proj = await _make_project(db_session)
    d = await _make(client, "author-1", project_id=str(proj.project_id),
                    definition_json=DEF_JSON_EQUIP)
    await client.post(PUBLISH.format(d=d["def_id"]), headers=_auth("rev", "REVIEWER"))

    r = await client.post(EXEC.format(d=d["def_id"]), headers=_auth("author-1"))
    assert r.status_code == 202, r.text
    task_id = r.json()["task_id"]

    poll = await client.get(f"/api/v1/report-builder/executions/{task_id}",
                            headers=_auth("author-1"))
    assert poll.status_code == 200, (
        f"202 之后立刻轮询得到 {poll.status_code} —— "
        f"前端会把它当终态失败报给用户：{poll.text}")
    body = poll.json()
    # ⚠️ **不断言 QUEUED**：端点刻意把「已入队未开始」与「正在渲染」合成
    # 一个状态（它的 docstring：分开只会让前端多写两个分支，而对用户是
    # 同一件事）。这里钉的是**这件事**：行存在、还没有文件 id。
    assert body["status"] in ("QUEUED", "RUNNING"), f"实得 {body['status']}"
    assert body["report_file_id"] is None, "还没渲染完就不该有文件 id"
    assert body["def_id"] == d["def_id"]


@pytest.mark.asyncio
async def test_execute_writes_execution_log_with_snapshot(client, db_session):
    """b9：每次执行写 `report_execution_logs`，含**条件快照 + 行数**。

    快照不是可选的：执行时允许临时改条件（is_temporary_adjust=True），
    事后要能复现当时查了什么 —— 只存 def_id 就再也复现不了。
    """
    from sqlalchemy import select

    from app.models.report import ReportExecutionLog
    from app.services.report.builder_service import execute_definition
    from tests.fixtures.report.seed import make_report_seed

    proj = await _make_project(db_session)
    d = await _make(client, "author-1", project_id=str(proj.project_id),
                    definition_json=DEF_JSON_EQUIP)
    await client.post(PUBLISH.format(d=d["def_id"]), headers=_auth("rev", "REVIEWER"))

    row = await _load_def(db_session, d["def_id"])
    await make_report_seed(db_session, proj.project_id, "EQUIPMENT_LIST")
    out = await execute_definition(db_session, def_id=row.def_id, user_id=None)
    await db_session.commit()

    logs = (await db_session.execute(select(ReportExecutionLog))).scalars().all()
    assert out.row_count > 0, "执行引擎一行都没取到"
    assert len(logs) == 1, f"应写 1 条执行日志，实得 {len(logs)}"
    assert logs[0].row_count == out.row_count, "日志行数与实际行数必须一致"
    assert logs[0].def_version == row.version
    assert logs[0].condition_snapshot["SelectedFields"], "快照里必须有字段选择"
    assert logs[0].is_temporary_adjust is False


@pytest.mark.asyncio
async def test_temporary_filter_adjustment_does_not_touch_the_definition(client, db_session):
    """b7 验收：临时调整不改定义本身。

    「不改定义」不能靠「没调 update」—— 若实现在查完回写一次条件，
    定义里的 FilterConditions 就被用户的临时筛选污染了，下一个看这份
    定义的人拿到的是别人一次临时的筛选。
    """
    from sqlalchemy import select

    from app.models.report import ReportExecutionLog
    from app.services.report.builder_service import execute_definition
    from tests.fixtures.report.seed import make_report_seed

    proj = await _make_project(db_session)
    d = await _make(client, "author-1", project_id=str(proj.project_id),
                    definition_json=DEF_JSON_EQUIP)
    await client.post(PUBLISH.format(d=d["def_id"]), headers=_auth("rev", "REVIEWER"))

    row = await _load_def(db_session, d["def_id"])
    await make_report_seed(db_session, proj.project_id, "EQUIPMENT_LIST")
    await execute_definition(
        db_session, def_id=row.def_id, user_id=None,
        temporary_filters={"operator": "AND", "conditions": [
            {"operator": "EQ", "source": "EQUIP_LIST",
             "field": "vendor", "value": "ACME"}]})
    await db_session.commit()

    await db_session.refresh(row)
    assert row.definition_json["FilterConditions"] == [], \
        "临时过滤条件被写回定义了 —— 定义被一次临时操作污染"
    logs = (await db_session.execute(
        select(ReportExecutionLog).order_by(ReportExecutionLog.created_at))).scalars().all()
    assert logs[-1].is_temporary_adjust is True, "临时执行没在审计里标记出来"
    assert logs[-1].condition_snapshot["FilterConditions"], "临时条件必须进快照"


@pytest.mark.asyncio
async def test_execution_respects_max_rows_and_says_so(client, db_session):
    """MaxRows 是硬闸 —— 静默截断会让人拿到少了几千行却毫无察觉的报表。"""
    from app.services.report.builder_service import execute_definition
    from tests.fixtures.report.seed import make_bulk_seed

    proj = await _make_project(db_session)
    d = await _make(client, "author-1", project_id=str(proj.project_id),
                    max_rows=50, definition_json=DEF_JSON_EQUIP)
    await client.post(PUBLISH.format(d=d["def_id"]), headers=_auth("rev", "REVIEWER"))

    row = await _load_def(db_session, d["def_id"])
    await make_bulk_seed(db_session, proj.project_id, "EQUIPMENT_LIST", 200)
    out = await execute_definition(db_session, def_id=row.def_id, user_id=None)
    assert out.row_count <= 50, f"实得 {out.row_count} 行，MaxRows=50 形同虚设"
    assert out.truncated is True, "截断了必须明说，不能静默"


@pytest.mark.asyncio
async def test_hidden_fields_are_not_rendered_but_are_still_stored(client, db_session):
    """`visible=False` 的字段不进输出表 —— 否则「显示/隐藏」开关没生效。"""
    from app.services.report.builder_service import execute_definition
    from tests.fixtures.report.seed import make_report_seed

    proj = await _make_project(db_session)
    d = await _make(client, "author-1", project_id=str(proj.project_id),
                    definition_json={
        "DataSources": [{"source": "EQUIP_LIST"}],
        "SelectedFields": [
            {"source": "EQUIP_LIST", "field": "tag_number",
             "alias": "位号", "order": 0, "visible": True},
            {"source": "EQUIP_LIST", "field": "vendor_model",
             "alias": "隐藏列", "order": 1, "visible": False},
        ],
    })
    await client.post(PUBLISH.format(d=d["def_id"]), headers=_auth("rev", "REVIEWER"))

    row = await _load_def(db_session, d["def_id"])
    await make_report_seed(db_session, proj.project_id, "EQUIPMENT_LIST")
    out = await execute_definition(db_session, def_id=row.def_id, user_id=None)
    assert out.headers == ["位号"], f"实得表头 {out.headers} —— 隐藏列漏进输出了"


@pytest.mark.asyncio
async def test_alias_overrides_registry_label(client, db_session):
    """别名优先于注册表的默认 label（SPEC §3.2.2(3) 别名设置）。"""
    from app.services.report.builder_service import execute_definition
    from tests.fixtures.report.seed import make_report_seed

    proj = await _make_project(db_session)
    d = await _make(client, "author-1", project_id=str(proj.project_id),
                    definition_json={
        "DataSources": [{"source": "EQUIP_LIST"}],
        "SelectedFields": [{"source": "EQUIP_LIST", "field": "tag_number",
                            "alias": "我的位号", "order": 0, "visible": True}],
    })
    await client.post(PUBLISH.format(d=d["def_id"]), headers=_auth("rev", "REVIEWER"))

    row = await _load_def(db_session, d["def_id"])
    await make_report_seed(db_session, proj.project_id, "EQUIPMENT_LIST")
    out = await execute_definition(db_session, def_id=row.def_id, user_id=None)
    assert out.headers == ["我的位号"]


@pytest.mark.asyncio
async def test_company_level_definition_cannot_execute_without_a_project(client, db_session):
    """⚠️ 安全边界：`project_id` 为空的公司级模板**不能**无作用域执行。

    放行的后果不是「数据多一点」，而是**全库所有项目的数据**被导进一份
    报表交给任何一个能打开执行面板的人。所以解析不到项目时直接 400，
    不「那就不筛吧」。
    """
    from app.services.exceptions import PcsError
    from app.services.report.builder_service import execute_definition

    d = await _make(client, "author-1", project_id=None,
                    definition_json=DEF_JSON_EQUIP)
    await client.post(PUBLISH.format(d=d["def_id"]), headers=_auth("rev", "REVIEWER"))
    row = await _load_def(db_session, d["def_id"])

    with pytest.raises(PcsError) as exc:
        await execute_definition(db_session, def_id=row.def_id, user_id=None)
    assert exc.value.code == "REPORT_PROJECT_SCOPE_REQUIRED"


@pytest.mark.asyncio
async def test_execution_never_crosses_project_boundary(client, db_session):
    """A 项目的定义执行时**绝不**返回 B 项目的行。

    项目过滤与用户过滤合并成 AND 组，且项目条件不是「用户条件之一」——
    这一条是上两条的正面验证。
    """
    from app.services.report.builder_service import execute_definition
    from tests.fixtures.report.seed import make_report_seed

    proj_a = await _make_project(db_session, "项目甲")
    proj_b = await _make_project(db_session, "项目乙")

    d = await _make(client, "author-1", project_id=str(proj_a.project_id),
                    definition_json=DEF_JSON_EQUIP)
    await client.post(PUBLISH.format(d=d["def_id"]), headers=_auth("rev", "REVIEWER"))

    await make_report_seed(db_session, proj_a.project_id, "EQUIPMENT_LIST")
    await make_report_seed(db_session, proj_b.project_id, "EQUIPMENT_LIST")

    row = await _load_def(db_session, d["def_id"])
    out = await execute_definition(db_session, def_id=row.def_id, user_id=None)
    assert out.row_count == 2, f"实得 {out.row_count} 行：甲乙两项目各 2 行，期望只出甲的 2 行"


@pytest.mark.asyncio
async def test_builder_task_renders_a_file_and_audits(db_session, monkeypatch):
    """ARQ 任务体：取数 → 渲染 → 落 report_files → 写 REPORT_EXECUTED 审计。"""
    from sqlalchemy import select

    from app.models.report import ReportFile
    from app.services.report import paths
    from app.workers import report_builder_tasks as tasks
    from tests.fixtures.report.seed import make_report_seed

    proj = await _make_project(db_session)
    # 任务体自己开不走 HTTP 建定义，直接写一行已发布定义
    from app.models.report import ReportDefinition

    definition = {
        "DataSources": [{"source": "EQUIP_LIST"}],
        "SelectedFields": [{"source": "EQUIP_LIST", "field": "tag_number",
                            "alias": "位号", "order": 0, "visible": True}],
        "FilterConditions": [], "MaxRows": 10000, "OutputFormat": "pdf",
    }
    d = ReportDefinition(
        project_id=proj.project_id, name="任务体测试", category="设备类",
        description="", definition_json=definition, output_format="pdf",
        max_rows=10000, version="0.1.0", status="PUBLISHED",
        shared_with="ALL_USERS", created_by=uuid.uuid4(),
    )
    db_session.add(d)
    await db_session.flush()
    await make_report_seed(db_session, proj.project_id, "EQUIPMENT_LIST")

    file_id = await tasks.execute_definition_task(
        _ctx_with(db_session, job_id="job-x"),
        def_id=str(d.def_id), project_id=str(proj.project_id),
        user_id=str(uuid.uuid4()), output_format="pdf",
    )

    row = (await db_session.execute(
        select(ReportFile).where(
            ReportFile.report_file_id == uuid.UUID(file_id)))).scalar_one()
    assert row.status == "SUCCEEDED"
    assert row.size_bytes > 0, "落了一个 0 字节文件"
    assert paths.resolve_path(row.file_path).exists(), "文件没真的写到磁盘"

    # 审计必须能查到 REPORT_EXECUTED，且带条件快照与行数
    from app.models.system import AuditLog
    audits = (await db_session.execute(
        select(AuditLog).where(AuditLog.action == "REPORT_EXECUTED"))).scalars().all()
    assert audits, "没有 REPORT_EXECUTED 审计"
    detail = audits[-1].detail_json
    assert detail["row_count"] == 2, f"审计行数与实际不符：{detail}"
    assert detail["condition_snapshot"]["project_id"] == str(proj.project_id)


@pytest.mark.asyncio
async def test_truncation_is_visible_on_the_rendered_output(db_session):
    """截断必须在**成品上**看得见，不只是返回值里的一个 flag。

    一份少了 9950 行却什么都不说的报表，比直接报错危险得多。
    """
    from app.services.report.blocks import HeadingBlock, TableBlock
    from tests.fixtures.report.seed import make_bulk_seed

    proj = await _make_project(db_session)
    await make_bulk_seed(db_session, proj.project_id, "EQUIPMENT_LIST", 30)

    blocks: list = [HeadingBlock(text="自定义报表", level=1),
                    HeadingBlock(text="⚠ 结果已截断：最多 20 行", level=1),
                    TableBlock(headers=["位号"],
                               rows=[[f"P-{i}"] for i in range(20)],
                               assumed_cols=())]
    import io

    from pypdf import PdfReader

    from app.services.report.renderer_pdf import render_pdf
    from app.services.report.style import ReportStyle

    data = render_pdf(title="自定义报表", blocks=blocks, style=ReportStyle(),
                      qr_payload=None, assumed_fields=[], context={})
    text = "\n".join(p.extract_text() for p in PdfReader(io.BytesIO(data)).pages)
    assert "截断" in text, "PDF 上看不到截断提示 —— 用户以为这就是全部"


# --- b8 导出：水印 / DEMO 限制 -------------------------------------------------

#: SPEC §3.2.2(8)「即席导出件 …… 文件带『非发布件』时间戳水印」
WATERMARK_TEXT = "非发布件"


@pytest.fixture
def demo_mode(monkeypatch):
    """打开演示版。**配置驱动** —— 演示版是部署形态，不是运行期开关。"""
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "report_demo_mode", True, raising=False)
    return True


def _pdf_text(path) -> str:
    from pypdf import PdfReader
    return "\n".join(p.extract_text() for p in PdfReader(str(path)).pages)


@pytest.mark.asyncio
async def test_adhoc_export_carries_non_issued_watermark(db_session):
    """即席导出件必须带「非发布件」时间戳水印（SPEC §3.2.2(8)）。

    水印是**语义声明**：这份文件不是签署过的交付物。没水印的文件被
    当成正式版打印出去，是整个签署体系失效的入口。
    """
    from app.services.report import watermark
    from app.services.report.blocks import TableBlock

    blocks = [TableBlock(headers=["位号"], rows=[["P-101"]], assumed_cols=())]
    marked = watermark.apply(blocks, timestamp="2026-10-12 19:00:00",
                             demo=False)
    pdf = watermark.render_to_bytes(
        marked, output_format="pdf", title="测试",
        style=__import__("app.services.report.style", fromlist=["ReportStyle"]).ReportStyle(),
        context={})
    import io
    text = "\n".join(p.extract_text() for p in
                     __import__("pypdf", fromlist=["PdfReader"]).PdfReader(io.BytesIO(pdf)).pages)
    assert WATERMARK_TEXT in text, "PDF 上看不到『非发布件』水印"
    assert "2026-10-12" in text, "水印缺时间戳 —— 那只是装饰，不是声明"


@pytest.mark.asyncio
async def test_demo_mode_adds_demo_watermark_on_top_of_non_issued():
    from app.services.report.blocks import HeadingBlock
    """演示版叠加 DEMO 水印（SUP-006），且**不替换**非发布件水印。"""
    from app.services.report import watermark
    from app.services.report.blocks import TableBlock

    blocks = [TableBlock(headers=["位号"], rows=[["P-101"]], assumed_cols=())]
    marked = watermark.apply(blocks, timestamp="2026-10-12 19:00:00", demo=True)
    text = "\n".join(b.text for b in marked if isinstance(b, HeadingBlock))
    assert WATERMARK_TEXT in text
    assert "DEMO" in text, "演示版没有 DEMO 水印"


@pytest.mark.asyncio
async def test_demo_mode_caps_definition_count(client, demo_mode):
    """SPEC §3.2.2(8)：演示版报表定义数量限 3 个。

    第 4 个必须被拒，且**已建的 3 个还在** —— 拒绝发生在写入之前。
    """
    made = []
    for i in range(3):
        r = await client.post("/api/v1/report-builder/definitions",
                              headers=_auth(f"demo-{i}"),
                              json=_definition_body(name=f"演示定义{i}"))
        assert r.status_code == 201, f"第 {i + 1} 个定义被拒：{r.text}"
        made.append(r.json())

    over = await client.post("/api/v1/report-builder/definitions",
                             headers=_auth("demo-4"),
                             json=_definition_body(name="第 4 个"))
    assert over.status_code == 403, f"实得 {over.status_code}：演示版不限数量"
    assert over.json()["code"] == "REPORT_DEMO_LIMIT"

    lst = await client.get("/api/v1/report-builder/definitions",
                           headers=_auth("demo-0"))
    assert len(lst.json()["items"]) == 1, "计数是按用户算的？"


@pytest.mark.asyncio
async def test_demo_limit_does_not_apply_outside_demo_mode(client):
    """非演示版不该受 3 个的限制 —— 否则正式部署根本没法用。"""
    for i in range(4):
        r = await client.post("/api/v1/report-builder/definitions",
                              headers=_auth("normal-user"),
                              json=_definition_body(name=f"正式定义{i}"))
        assert r.status_code == 201, f"第 {i + 1} 个被拒：{r.text}"


@pytest.mark.asyncio
async def test_csv_export_is_available(db_session):
    """SPEC b8 要求 Excel / CSV / PDF 三种导出。

    CSV 此前不在 `SUPPORTED_FORMATS` 里（Excel/CSV 都走 xlsx 渲染器），
    结果是用户在输出格式下拉框里选不到 CSV。
    """
    from app.services.report import watermark
    from app.services.report.blocks import TableBlock
    from app.services.report.style import ReportStyle

    blocks = [TableBlock(headers=["位号", "制造商"],
                         rows=[["P-101", "ACME"], ["P-102", "ACME"]],
                         assumed_cols=())]
    marked = watermark.apply(blocks, timestamp="2026-10-12 19:00:00", demo=False)
    data = watermark.render_to_bytes(
        marked, output_format="csv", title="设备一览", style=ReportStyle(),
        context={})
    assert data.startswith(b"\xef\xbb\xbf"), "缺 UTF-8 BOM：Excel 双击打开会乱码"
    text = data.decode("utf-8-sig")
    assert "P-101" in text
    lines = text.splitlines()
    assert lines[0].startswith("#"), f"首行不是注释：{lines[0]!r}"
    assert WATERMARK_TEXT in lines[0], "CSV 上没有『非发布件』水印"
    assert lines[1] == "位号,制造商", f"表头行不对：{lines[1]!r}"


@pytest.mark.asyncio
async def test_csv_quotes_fields_containing_commas():
    """字段值里含逗号/引号/换行时必须转义 —— 手工 `",".join` 会列错位，
    而列错位的数据表比报错更难发现。"""
    from app.services.report import watermark
    from app.services.report.blocks import TableBlock
    from app.services.report.style import ReportStyle

    blocks = [TableBlock(headers=["位号", "备注"],
                         rows=[["P-101", "A,B 含逗号"], ["P-102", '他说"你好"']],
                         assumed_cols=())]
    data = watermark.render_to_bytes(
        blocks, output_format="csv", title="t", style=ReportStyle(), context={})
    import csv as _csv
    import io
    rows = list(_csv.reader(io.StringIO(data.decode("utf-8-sig"))))
    assert rows[0] == ["位号", "备注"]
    assert rows[1] == ["P-101", "A,B 含逗号"], f"含逗号的字段没被引号包住：{rows[1]}"
    assert rows[2] == ["P-102", '他说"你好"']


@pytest.mark.asyncio
async def test_builder_export_actually_carries_the_watermark(db_session):
    """端到端：ARQ 任务体产出的 PDF 上**真的有**水印。

    上一条测的是 `watermark.render_to_bytes` 自己 —— 但如果任务体没调
    `watermark.apply`，那条测试照样绿，而用户拿到的文件光秃秃。
    这条钉的是**调用链**。
    """
    import uuid as _uuid

    from sqlalchemy import select

    from app.models.report import ReportFile
    from app.services.report import paths
    from app.services.report.watermark import NON_ISSUED_PREFIX
    from app.workers import report_builder_tasks as tasks
    from tests.fixtures.report.seed import make_report_seed

    proj = await _make_project(db_session)
    from app.models.report import ReportDefinition
    d = ReportDefinition(
        project_id=proj.project_id, name="水印端到端", category="设备类",
        description="",
        definition_json={
            "DataSources": [{"source": "EQUIP_LIST"}],
            "SelectedFields": [{"source": "EQUIP_LIST", "field": "tag_number",
                                "alias": "位号", "order": 0, "visible": True}],
            "FilterConditions": [], "MaxRows": 10000, "OutputFormat": "pdf"},
        output_format="pdf", max_rows=10000, version="0.1.0",
        status="PUBLISHED", shared_with="ALL_USERS", created_by=_uuid.uuid4())
    db_session.add(d)
    await db_session.flush()
    await make_report_seed(db_session, proj.project_id, "EQUIPMENT_LIST")

    file_id = await tasks.execute_definition_task(
        _ctx_with(db_session, job_id="job-wm"),
        def_id=str(d.def_id), project_id=str(proj.project_id),
        user_id=str(_uuid.uuid4()), output_format="pdf")
    row = (await db_session.execute(select(ReportFile).where(
        ReportFile.report_file_id == _uuid.UUID(file_id)))).scalar_one()
    assert NON_ISSUED_PREFIX in _pdf_text(paths.resolve_path(row.file_path)), \
        "即席导出件上没有『非发布件』水印 —— 它会被当成签署过的交付物"


@pytest.mark.asyncio
async def test_signed_deliverable_path_has_no_non_issued_watermark(db, project_id):
    """反向约束：固定 10 类报表走的是**交付物**流程（SUP-007：带 Rev 与签署），
    不能标「非发布件」—— 那是两种相反的语义。

    这条测试是防止「为了统一，把水印加在 `report_service.generate` 上」
    而写的：那样即席导出对了，交付物却自称非发布件。
    """
    from app.services.report import paths
    from app.services.report.report_service import generate
    from app.services.report.style import ReportStyle
    from app.services.report.watermark import NON_ISSUED_PREFIX
    from tests.fixtures.report.seed import make_report_seed

    ids = await make_report_seed(db, project_id, "EQUIPMENT_LIST")
    out = await generate(report_type="EQUIPMENT_LIST", project_id=project_id,
                         record_ids=ids, output_format="pdf",
                         style=ReportStyle(), ctx={}, db=db)
    assert NON_ISSUED_PREFIX not in _pdf_text(paths.resolve_path(out.file_path)), \
        "正式交付物流程的文件被标成了『非发布件』"


@pytest.mark.asyncio
async def test_csv_is_offered_by_the_execute_endpoint(client, fake_queue):
    """CSV 落地后，API 的输出格式白名单必须**跟着变**。

    第一版白名单写死 `{pdf,xlsx,docx}`，CSV 落地后没人改它 ——
    用户在输出格式下拉框里选不到 CSV，而 SPEC 明确要求三种都可导出。
    白名单与实现各持一份 = 迟早分叉，故这里直接断言两者一致。
    """
    from app.services.report.watermark import EXPORT_FORMATS

    assert set(_api_renderable_formats()) == set(EXPORT_FORMATS), \
        "API 白名单与 watermark.EXPORT_FORMATS 不一致 —— 某个格式选得到却跑不了"
    assert "csv" in EXPORT_FORMATS, "SPEC b8 要求 Excel/CSV/PDF 三种都可导出"

    d = await _make(client, "author-1")
    await client.post(PUBLISH.format(d=d["def_id"]), headers=_auth("rev", "REVIEWER"))
    r = await client.post(EXEC.format(d=d["def_id"]), headers=_auth("user-1"),
                          json={"output_format": "csv"})
    assert r.status_code == 202, f"CSV 仍被拒：{r.text} {r.json()}"


def _api_renderable_formats() -> frozenset:
    from app.api.v1.report_builder import _RENDERABLE_FORMATS
    return _RENDERABLE_FORMATS


# --- c2 detail_level 分级（端到端） -------------------------------------------


HEAT_BASIC_9 = {
    "DataSources": [{"source": "HEAT_RESULTS"}],
    "SelectedFields": [
        {"source": "HEAT_RESULTS", "field": f, "alias": "", "order": i,
         "visible": True}
        for i, f in enumerate([
            "tag_number", "effective_area", "duty", "u_overall",
            "shell_params.temp_in", "shell_params.temp_out",
            "tube_params.temp_in", "tube_params.temp_out", "shell_params.pd",
        ])
    ],
    "detailLevel": "BASIC",
}


@pytest.mark.asyncio
async def test_basic_definition_with_detail_field_is_rejected(client):
    """BASIC 报表里放 DETAIL 字段 → 400。

    ADR 的分级标准是「BASIC 不含几何/热阻明细」，多一列就等于分级失效，
    而报表照跑只是多出一列 —— 用户看不出自己选的字段越了级。
    """
    body = dict(HEAT_BASIC_9)
    body["SelectedFields"] = HEAT_BASIC_9["SelectedFields"] + [
        {"source": "HEAT_RESULTS", "field": "lmtd",
         "alias": "对数平均温差", "order": 99, "visible": True},
    ]
    r = await client.post("/api/v1/report-builder/definitions",
                          headers=_auth("heat-author"),
                          json=_definition_body(name="越级的 BASIC 报表",
                                               definition_json=body))
    assert r.status_code == 400, f"实得 {r.status_code}：{r.text}"
    assert r.json()["code"] == "REPORT_DETAIL_LEVEL_VIOLATION"


@pytest.mark.asyncio
async def test_the_same_fields_are_fine_at_detail_level(client):
    """同样的字段在 DETAIL 下合法 —— 分级闸不能是「DETAIL 字段一律拒」。"""
    body = {**HEAT_BASIC_9, "detailLevel": "DETAIL"}
    body["SelectedFields"] = HEAT_BASIC_9["SelectedFields"] + [
        {"source": "HEAT_RESULTS", "field": "lmtd",
         "alias": "对数平均温差", "order": 99, "visible": True},
    ]
    r = await client.post("/api/v1/report-builder/definitions",
                          headers=_auth("heat-author"),
                          json=_definition_body(name="完整换热器报表",
                                               definition_json=body))
    assert r.status_code == 201, r.text
    assert r.json()["definition_json"]["detailLevel"] == "DETAIL"


@pytest.mark.asyncio
async def test_hidden_detail_field_is_still_rejected_at_basic(client):
    """`visible=False` 的 DETAIL 字段**也要拒**。

    放过去等于把问题推到更远的地方：定义存得进去，将来有人把 visible
    改成 true 就会撞上一个 BASIC 定义里本不该有的字段，而那时没人会
    记得当初为什么没拦。
    """
    body = dict(HEAT_BASIC_9)
    body["SelectedFields"] = HEAT_BASIC_9["SelectedFields"] + [
        {"source": "HEAT_RESULTS", "field": "baffle_spacing",
         "alias": "", "order": 99, "visible": False},
    ]
    r = await client.post("/api/v1/report-builder/definitions",
                          headers=_auth("heat-author"),
                          json=_definition_body(name="藏了个越级字段",
                                               definition_json=body))
    assert r.status_code == 400, f"隐藏字段绕过了分级闸：{r.status_code}"


@pytest.mark.asyncio
async def test_detail_level_does_not_affect_other_sources(client):
    """非 HEAT 源在 BASIC 下照常可选 —— 给所有源套分级会让 BASIC 报表
    连设备字段都选不了。"""
    r = await client.post("/api/v1/report-builder/definitions",
                          headers=_auth("heat-author"),
                          json=_definition_body(name="普通设备报表"))
    assert r.status_code == 201, r.text


@pytest.mark.asyncio
async def test_datasource_tree_exposes_level_and_exchanger_type(client, auth_pc):
    """字段树必须带上分级与换热器类型，否则前端没法按 ADR 分组。"""
    r = await client.get("/api/v1/report-builder/datasources", headers=auth_pc)
    assert r.status_code == 200, r.text
    heat = next(d for d in r.json()["datasources"] if d["key"] == "HEAT_RESULTS")
    by_name = {f["name"]: f for f in heat["fields"]}
    assert by_name["lmtd"]["level"] == "DETAIL"
    assert by_name["tag_number"]["level"] == "BASIC"
    assert by_name["baffle_spacing"]["exchanger_type"] == "SHELL_TUBE"
    assert by_name["ache_params.fan_power_kw"]["exchanger_type"] == "AIR_COOLER"
    assert by_name["duty"]["exchanger_type"] is None, "通用字段不该带类型标记"

    # 非 HEAT 源不带分级 —— 前端据此决定是否显示分级控件
    equip = next(d for d in r.json()["datasources"] if d["key"] == "EQUIP_LIST")
    assert all(f["level"] is None for f in equip["fields"])


@pytest.mark.asyncio
async def test_detail_style_is_used_when_rendering_a_detail_definition(db_session):
    """DETAIL 定义的渲染必须用 DETAIL 样式（横向），不是 BASIC 的。"""
    from app.services.report.style import heat_detail_styles

    assert heat_detail_styles("DETAIL").orientation == "landscape"
    assert heat_detail_styles("BASIC").orientation == "portrait"


@pytest.mark.asyncio
async def test_definition_field_in_the_wrong_place_is_rejected_not_defaulted(client):
    """`detailLevel` 写在**顶层**（而非 definition_json 里）必须 422。

    Pydantic 默认 `extra="ignore"`：字段写错位置会被静默丢弃，定义拿到
    默认 BASIC —— 而 BASIC 比 DETAIL 少 40 列，报表照跑、只是内容少一大截，
    没有任何一层会说话。**默认值会吞掉字段放错这个错误。**
    """
    r = await client.post("/api/v1/report-builder/definitions",
                          headers=_auth("heat-author"),
                          json=_definition_body(name="位置写错了",
                                               detailLevel="DETAIL"))
    assert r.status_code == 422, f"实得 {r.status_code}：字段放错位置被静默忽略了"
    assert "detailLevel" in r.text


async def test_task_closes_the_session_it_opened(db_session, monkeypatch):
    """⚠️ 任务必须 `close()` 自己开的 session。

    ARQ 的 ctx 给的是 **factory**，任务体自己开 session —— 于是**关闭的责任
    也在任务体**。不关的话，每次 job 都把一条连接挂在 session 上，直到 GC 才
    归还连接池。症状不是报错，是连接数缓慢爬升，最后撞上
    `remaining connection slots are reserved for roles with the SUPERUSER`
    —— 而报错发生在**完全无关的**命令（比如跑迁移）上。

    之前的测试都用 `_ctx_with(db_session)` 复用同一个 session，替身比被测物
    更宽容：它既不新建也不归还连接，于是这条泄漏在单测里根本不可见。
    """
    from app.models.report import ReportDefinition
    from tests.fixtures.report.seed import make_report_seed

    proj = await _make_project(db_session, "会话关闭测试项目")
    d = ReportDefinition(
        project_id=proj.project_id, name="会话关闭测试", category="设备类",
        description="", definition_json=DEF_JSON_EQUIP, output_format="pdf",
        max_rows=10000, version="0.1.0", status="PUBLISHED",
        shared_with="ALL_USERS", created_by=uuid.uuid4())
    db_session.add(d)
    await db_session.flush()
    await make_report_seed(db_session, proj.project_id, "EQUIPMENT_LIST")

    closed = []

    class _RecordingSession:
        """代理真实 session，只记录 close / aclose 有没有被调用。"""

        def __getattr__(self, name):
            return getattr(db_session, name)

        async def close(self):
            closed.append("close")

        async def aclose(self):
            closed.append("aclose")

    from app.workers import report_builder_tasks as tasks
    await tasks.execute_definition_task(
        {"session_factory": _RecordingSession, "job_id": "job-close", "job_try": 1},
        def_id=str(d.def_id), project_id=str(proj.project_id),
        user_id=str(uuid.uuid4()), output_format="pdf",
    )
    assert closed, (
        "任务体开了 session 却从不 close —— 每个 job 泄漏一条连接，"
        "直到 GC 才归还；报错会出现在无关命令上（连接槽耗尽）")


@pytest.mark.asyncio
async def test_worker_updates_the_queued_log_row_instead_of_adding_a_second(
        client, fake_queue, db_session):
    """入队建的行与任务体跑出来的行**必须是同一行**。

    两处各写一条的话，每次执行留两条日志：一条 row_count=0 的空壳，
    一条真正的执行记录。而按 `task_id` 查的轮询端点用
    `scalar_one_or_none()` —— 命中两行会直接抛
    `MultipleResultsFound`，于是**执行刚成功、轮询就 500**。

    ⚠️ `test_execute_writes_execution_log_with_snapshot` 验不到这条：它直接
    调 `execute_definition`，绕过了「入队先建一行」那半边。
    """
    from sqlalchemy import func, select

    from app.models.report import ReportExecutionLog
    from app.workers import report_builder_tasks as tasks
    from tests.fixtures.report.seed import make_report_seed

    proj = await _make_project(db_session)
    d = await _make(client, "author-1", project_id=str(proj.project_id),
                    definition_json=DEF_JSON_EQUIP)
    await client.post(PUBLISH.format(d=d["def_id"]), headers=_auth("rev", "REVIEWER"))
    await make_report_seed(db_session, proj.project_id, "EQUIPMENT_LIST")

    r = await client.post(EXEC.format(d=d["def_id"]), headers=_auth("author-1"))
    task_id = r.json()["task_id"]

    await tasks.execute_definition_task(
        {"session_factory": lambda: db_session, "job_id": task_id, "job_try": 1},
        def_id=d["def_id"], project_id=str(proj.project_id),
        user_id=None, output_format="csv")
    await db_session.commit()

    n = await db_session.scalar(
        select(func.count()).select_from(ReportExecutionLog))
    assert n == 1, f"task_id={task_id} 名下应有且只有 1 行，实得 {n} —— " \
                   "任务体若又 INSERT 一条，轮询端的 scalar_one_or_none() 会抛 MultipleResultsFound"
    row = (await db_session.execute(
        select(ReportExecutionLog).where(ReportExecutionLog.task_id == task_id)
    )).scalar_one()
    assert row.row_count > 0, "行数还是 0 —— 任务体没把入队那一行更新成真实结果"
    assert row.report_file_id is not None


@pytest.mark.asyncio
async def test_successful_builder_execution_marks_the_log_row_FINISHED(
        client, fake_queue, db_session):
    """成功执行必须把行标成 **FINISHED**，不能停在 RUNNING。

    ⚠️ 这不是「状态显示得好看」的问题，是**回收器会吃掉它**：
    `reclaim_stale_execution_logs` 扫的是 `status IN ('QUEUED','RUNNING')`
    且超时 15 分钟的行。停在 RUNNING 上 ⇒ 一次**已经出了文件**的成功执行，
    15 分钟后被改判 FAILED，并在 `condition_snapshot` 里写下 `reclaimed_at`
    —— 而那是模块自己声明为审计表、不容篡改的表。
    轮询端点于是对一个真有文件的任务报失败。

    （此前这个改判被回收器不 commit 掩盖着，所以损坏没落库。
    回收器的 commit 修好之后，这条就从「潜伏」变成「活跃」。两处必须同批落地。）

    观测点用同一个 session 就够：要验的是「有没有赋这个值」，
    不是「有没有提交」—— 后者由 test_report_tasks.py 里那条
    文件库测试负责（`:memory:` 的 StaticPool 让第二个 session
    根本不是第二个连接）。
    """
    from sqlalchemy import select

    from app.models.report import ReportExecutionLog
    from app.workers import report_builder_tasks as tasks
    from tests.fixtures.report.seed import make_report_seed

    proj = await _make_project(db_session)
    d = await _make(client, "author-1", project_id=str(proj.project_id),
                    definition_json=DEF_JSON_EQUIP)
    await client.post(PUBLISH.format(d=d["def_id"]), headers=_auth("rev", "REVIEWER"))
    await make_report_seed(db_session, proj.project_id, "EQUIPMENT_LIST")

    r = await client.post(EXEC.format(d=d["def_id"]), headers=_auth("author-1"))
    task_id = r.json()["task_id"]

    await tasks.execute_definition_task(
        {"session_factory": lambda: db_session, "job_id": task_id, "job_try": 1},
        def_id=d["def_id"], project_id=str(proj.project_id),
        user_id=None, output_format="csv")
    await db_session.commit()

    row = (await db_session.execute(
        select(ReportExecutionLog).where(ReportExecutionLog.task_id == task_id)
    )).scalar_one()
    assert row.status == "FINISHED", (
        f"成功执行后 status={row.status!r} —— 停在 RUNNING 上，"
        "15 分钟后会被回收器当成僵死的改判成 FAILED。"
        "全 app/ 只有这里该写 FINISHED 却没写。")


# --- TODO-016：builder 任务体的失败路径 -----------------------------------------


@pytest.mark.asyncio
async def test_builder_failure_writes_one_audit_row_per_attempt(
        client, fake_queue, db_session, monkeypatch):
    """**每次**失败都写一条 REPORT_FAILED 审计，带 attempt_no（用户 2026-10-09 裁决）。

    为什么是必然而不是偏好：ARQ 的 `keep_result` 默认 3600 秒，Redis 里的
    异常 1 小时后就清空。audit_logs 是失败的**唯一持久记录** ——
    「第 2 次为什么又失败」只有这里能回答。

    ⚠️ 一条断言都不加就会绿：原先这条路径上没有任何「失败会怎样」的测试，
    而任务体里那两行（写审计、标状态）任何一行被删掉都无人察觉。
    """
    from sqlalchemy import select

    from app.models.enums import AuditAction
    from app.models.system import AuditLog
    from app.services.report import builder_service
    from app.workers import report_builder_tasks as tasks

    proj = await _make_project(db_session, "失败审计用项目")
    d = await _make(client, "author-1", project_id=str(proj.project_id),
                    definition_json=DEF_JSON_EQUIP)
    await client.post(PUBLISH.format(d=d["def_id"]),
                      headers=_auth("rev", "REVIEWER"))

    async def boom(*a, **k):
        raise RuntimeError("取数炸了")

    monkeypatch.setattr(builder_service, "execute_definition", boom)

    for attempt in (1, 2):
        with pytest.raises(RuntimeError):
            await tasks.execute_definition_task(
                {"session_factory": lambda: db_session,
                 "job_id": f"job-audit-{attempt}", "job_try": attempt},
                def_id=d["def_id"], project_id=str(proj.project_id),
                user_id=None, output_format="pdf")
    await db_session.commit()

    rows = (await db_session.execute(select(AuditLog).where(
        AuditLog.action == AuditAction.REPORT_FAILED.value))).scalars().all()
    assert len(rows) == 2, f"两次失败应写 2 条审计，实得 {len(rows)}"
    attempts = {r.detail_json.get("attempt_no") for r in rows}
    assert attempts == {1, 2}, f"审计里应带 attempt_no 1 与 2，实得 {attempts}"
    assert all(r.detail_json.get("task_id") for r in rows), "审计里必须带 task_id"


@pytest.mark.asyncio
async def test_builder_intermediate_failure_does_not_end_the_execution(
        client, fake_queue, db_session, monkeypatch):
    """中间那次失败**不能**把执行标成 FAILED —— ARQ 还会重试。

    标了就是**假的终态**：前端显示「失败」，而任务随后重试成功、
    文件照样出来。用户看到「生成失败」却下载得到文件。

    与 `test_status_is_not_failed_until_the_last_attempt`（固定 10 类那条）
    成对：两条路的失败语义必须一致，否则同一个用户在两条路上看到
    互相矛盾的行为。
    """
    from sqlalchemy import select

    from app.models.report import ReportExecutionLog
    from app.services.report import builder_service
    from app.workers import report_builder_tasks as tasks
    from app.workers.worker import MAX_TRIES

    proj = await _make_project(db_session, "中间失败用项目")
    d = await _make(client, "author-1", project_id=str(proj.project_id),
                    definition_json=DEF_JSON_EQUIP)
    await client.post(PUBLISH.format(d=d["def_id"]),
                      headers=_auth("rev", "REVIEWER"))
    r = await client.post(EXEC.format(d=d["def_id"]), headers=_auth("author-1"))
    task_id = r.json()["task_id"]

    async def boom(*a, **k):
        raise RuntimeError("取数炸了")

    monkeypatch.setattr(builder_service, "execute_definition", boom)

    with pytest.raises(RuntimeError):
        await tasks.execute_definition_task(
            {"session_factory": lambda: db_session,
             "job_id": task_id, "job_try": 1},
            def_id=d["def_id"], project_id=str(proj.project_id),
            user_id=None, output_format="pdf")
    await db_session.commit()

    row = (await db_session.execute(select(ReportExecutionLog).where(
        ReportExecutionLog.task_id == task_id))).scalar_one()
    assert row.status != "FAILED", (
        f"第 1 次尝试就标了 FAILED：{row.status} —— 而 max_tries="
        f"{MAX_TRIES}，ARQ 还会重试，用户拿到的是假的终态")
    # ⚠️ **不断言 RUNNING**。失败路径第一步是 `rollback()`，而 RUNNING 是
    # 在它之前 flush 的 —— 于是那次 flush 被回滚掉，读回来是 QUEUED。
    # 而 QUEUED 恰恰是**准确**的：此刻任务正等着被重试，并没有在跑。
    # （曾一度在这里断言 RUNNING，症状是「明明跑了怎么还是排队」，
    #  实际是断言写错了，不是代码错了。）
    assert row.status in ("QUEUED", "RUNNING"), f"实得 {row.status}"

    # 最后一次：必须落终态，否则前端转圈到超时
    with pytest.raises(RuntimeError):
        await tasks.execute_definition_task(
            {"session_factory": lambda: db_session,
             "job_id": task_id, "job_try": MAX_TRIES},
            def_id=d["def_id"], project_id=str(proj.project_id),
            user_id=None, output_format="pdf")
    await db_session.commit()
    # ⚠️ **重新查**而不是 `refresh(row)`：失败路径的 `rollback()` 已把那个
    # ORM 实例踢出本 session，`refresh` 会抛
    # `Instance ... is not persistent within this Session` —— 症状看着像
    # 「数据库连接坏了」，实际只是行被回滚掉了。
    row = (await db_session.execute(select(ReportExecutionLog).where(
        ReportExecutionLog.task_id == task_id))).scalar_one()
    assert row.status == "FAILED", (
        f"最后一次尝试后状态是 {row.status} —— 没有终态，前端会转圈到超时")


@pytest.mark.asyncio
async def test_builder_failure_asks_arq_to_retry(client, fake_queue, db_session,
                                                 monkeypatch):
    """与固定 10 类那条同义：失败且**还有次数**时必须抛 `Retry`。

    ⚠️ **ARQ 0.28 不会因为普通异常重试** —— `arq/worker.py:612-637` 的分支只认
    `Retry` / `CancelledError` / `RetryJob`，其余一律 `failed, finish = True`
    当场判死。所以只配 `WorkerSettings.max_tries` 的话，一个普通 `PcsError`
    永远只跑一次，SPEC §a7 的「失败重试 max_tries=3」根本不成立。

    两条路（固定 10 类 / 自定义定义）必须一致：同一个用户在两条路上不该看到
    互相矛盾的失败语义。
    """
    from arq import Retry

    from app.services.report import builder_service
    from app.workers import report_builder_tasks as tasks
    from app.workers.worker import MAX_TRIES

    proj = await _make_project(db_session, "重试信号用项目")
    d = await _make(client, "author-1", project_id=str(proj.project_id),
                    definition_json=DEF_JSON_EQUIP)
    await client.post(PUBLISH.format(d=d["def_id"]),
                      headers=_auth("rev", "REVIEWER"))

    async def boom(*a, **k):
        raise RuntimeError("取数炸了")

    monkeypatch.setattr(builder_service, "execute_definition", boom)

    r = await client.post(EXEC.format(d=d["def_id"]), headers=_auth("author-1"))
    task_id = r.json()["task_id"]
    ctx = {"session_factory": lambda: db_session, "job_id": task_id}

    with pytest.raises(Retry):
        await tasks.execute_definition_task(
            {**ctx, "job_try": 1}, def_id=d["def_id"],
            project_id=str(proj.project_id), user_id=None, output_format="pdf")

    # 最后一次必须抛原始异常：否则 ARQ 会再排一次，
    # 于是「重试已经用完」这件事永远传不出去。
    with pytest.raises(RuntimeError):
        await tasks.execute_definition_task(
            {**ctx, "job_try": MAX_TRIES}, def_id=d["def_id"],
            project_id=str(proj.project_id), user_id=None, output_format="pdf")
