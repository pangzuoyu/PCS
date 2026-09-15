"""Meta API 测试（P4.5 P45-0-4 / P45-0-4.5 V1.1）。

V1：4 端点 × 1 happy + 1 anonymous denied = 8 例。
V1.1：扩展 enum/state-machine 字段/errors 全集/permissions 全集/CSV。
"""
from __future__ import annotations


def _auth(tok: str) -> dict:
    return {"Authorization": f"Bearer {tok}"}


# ---------- happy path ----------


# V1 — 9 态全集
async def test_get_enums_returns_required_groups(client, sample_user_token):
    r = await client.get("/api/v1/meta/enums", headers=_auth(sample_user_token))
    assert r.status_code == 200, r.text
    data = r.json()
    required = {
        "RecordSignStatus",      # 9 态全集（含 color/icon）
        "StreamSignStatus",      # 9 态全集
        "DeliverableSignStatus",
        "WorkspaceType",
        "EquipmentStatus",       # N/E/D/M/F
        "CalcStatus",
        "ActualDataStatus",
        "SnapshotStatus",
        "ConfigStatus",          # P2 配置资产 5 态
        "ConfigTransition",
        "PipeType",              # SUP-008
        "CheckResult",
        "PumpOperation",
        "DesignStage",
        "FlowPattern",           # 两相流
        "TwoPhaseCheck",
        "StreamDataMode",        # CHEMICAL/PETROLEUM/SOLID
        "StreamCaseType",        # 物流级 4 值
        "StatePointCaseType",    # 状态点级 4 值
    }
    missing = required - set(data.keys())
    assert not missing, f"missing enum groups: {missing}"
    for key in required:
        assert data[key], f"{key} is empty"


async def test_record_sign_status_9_with_meta(client, sample_user_token):
    r = await client.get("/api/v1/meta/enums", headers=_auth(sample_user_token))
    data = r.json()
    values = [item["value"] for item in data["RecordSignStatus"]]
    assert values == [
        "DRAFT", "IN_APPROVAL", "CHECKED", "CHECK_REJECTED", "STALE",
        "CHANGE_PENDING", "CHANGED", "REVERSAL_PENDING", "OBSOLETE",
    ]
    draft = data["RecordSignStatus"][0]
    assert draft["color"] == "state-draft"
    assert draft["icon"] == "EditOutlined"
    assert draft["order"] == 1


async def test_get_state_machine_with_full_fields(client, sample_user_token):
    r = await client.get("/api/v1/meta/state-machine", headers=_auth(sample_user_token))
    assert r.status_code == 200, r.text
    data = r.json()
    assert "transitions" in data and "allowed" in data
    # transitions[] 字段齐全
    for t in data["transitions"]:
        assert {"from", "action", "to", "allowed_roles", "preconditions", "side_effects"} <= t.keys(), \
            f"transition 字段缺：{t}"
    # 实际 13 StateTransition 事件 × 多 from 态 = 21 条（ALLOWED_TRANSITIONS）
    assert len(data["transitions"]) >= 20, f"transitions 太少：{len(data['transitions'])}"
    # allowed_roles 是 list[str]
    for t in data["transitions"]:
        assert isinstance(t["allowed_roles"], list)
        assert t["allowed_roles"], f"allowed_roles 空：{t}"
    # preconditions + side_effects 是 list[str]
    for t in data["transitions"][:3]:
        assert isinstance(t["preconditions"], list)
        assert isinstance(t["side_effects"], list)


async def test_state_machine_uses_real_state_transition_names(client, sample_user_token):
    """事件命名必须用真实 StateTransition enum 值（不是简化版）。"""
    r = await client.get("/api/v1/meta/state-machine", headers=_auth(sample_user_token))
    actions = {t["action"] for t in r.json()["transitions"]}
    # Sprint 2 真实事件
    for expected in (
        "SUBMIT_FOR_CHECK", "PASS_CHECK", "REJECT_CHECK", "MARK_STALE",
        "INITIATE_CHANGE", "APPLY_CHANGE", "REQUEST_REVERSAL",
        "APPROVE_REVERSAL", "OBSOLETE",
    ):
        assert expected in actions, f"缺事件 {expected}"


async def test_get_error_codes_full_set(client, sample_user_token):
    r = await client.get("/api/v1/meta/error-codes", headers=_auth(sample_user_token))
    assert r.status_code == 200, r.text
    data = r.json()
    codes = {e["code"] for e in data}
    # 全 94 条断言 ≥ 80（实际 94）
    assert len(codes) >= 80, f"error codes 太少：{len(codes)}"
    # 关键项必含
    for required_code in (
        "STREAM_UNRELIABLE_BLOCKED",  # P0-AUTH-001
        "PIPE_CLASS_BAD_TRANSITION",
        "CHANGE_NOTICE_BAD_STATE",
        "REVERSAL_BAD_STATE",
        "MISSING_BEARER", "INVALID_CREDENTIALS", "WRONG_TOKEN_TYPE",
    ):
        assert required_code in codes, f"缺错误码 {required_code}"
    for e in data:
        assert {"code", "http", "message", "ui_behavior"} <= e.keys()


async def test_get_permissions_7_roles_full(client, sample_user_token):
    r = await client.get("/api/v1/meta/permissions", headers=_auth(sample_user_token))
    assert r.status_code == 200, r.text
    data = r.json()
    roles = {p["role"] for p in data}
    # 实际使用：6 from require_roles + CHECKER/SYSADMIN from state_machine + VIEWER
    for role in (
        "DESIGNER", "CHECKER", "REVIEWER", "APPROVER",
        "SYSADMIN", "PROCESS_CONTROLLER", "VIEWER",
    ):
        assert role in roles, f"缺角色 {role}"
    # SYSTEM_ADMIN 与 SYSADMIN 别名同时出现
    assert "SYSTEM_ADMIN" in roles
    # 全 require_roles 调用点 → 至少 15 条
    assert len(data) >= 15, f"permissions 太少：{len(data)}"
    for p in data:
        assert {"role", "resource", "action", "permission_code", "frontend_behavior"} <= p.keys()


async def test_get_permissions_csv(client, sample_user_token):
    r = await client.get("/api/v1/meta/permissions.csv", headers=_auth(sample_user_token))
    assert r.status_code == 200, r.text
    assert r.headers["content-type"].startswith("text/csv")
    body = r.text
    # header
    assert body.splitlines()[0] == "role,resource,action,permission_code,frontend_behavior"
    # 至少 7 角色都有 1 行
    lines = body.splitlines()[1:]
    assert len(lines) >= 15


# ---------- anonymous denied ----------


async def test_enums_anonymous_denied(client):
    r = await client.get("/api/v1/meta/enums")
    assert r.status_code == 401


async def test_permissions_anonymous_denied(client):
    r = await client.get("/api/v1/meta/permissions")
    assert r.status_code == 401


async def test_error_codes_anonymous_denied(client):
    r = await client.get("/api/v1/meta/error-codes")
    assert r.status_code == 401


async def test_state_machine_anonymous_denied(client):
    r = await client.get("/api/v1/meta/state-machine")
    assert r.status_code == 401


async def test_permissions_csv_anonymous_denied(client):
    r = await client.get("/api/v1/meta/permissions.csv")
    assert r.status_code == 401