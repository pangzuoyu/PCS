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
    """未知格式必须 400 —— 静默接受会在执行时才炸，而那时用户已填完整个表单。"""
    r = await client.post("/api/v1/report-builder/definitions",
                          headers=_auth("author-1"),
                          json=_definition_body(output_format="csv"))
    assert r.status_code == 400, f"实得 {r.status_code}（CSV 属 b8，本批不支持）"


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
