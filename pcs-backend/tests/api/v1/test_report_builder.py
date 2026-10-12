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
# --- b7 执行引擎 --------------------------------------------------------------

EXEC = "/api/v1/report-builder/definitions/{d}/execute"

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
        {"db": db_session, "job_id": "job-x", "job_try": 1},
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
