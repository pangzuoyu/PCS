"""Meta API 服务层 — 枚举字典 + 状态机 + 权限码 + 错误码（P4.5 V1.1）。

前端 13 组件 + SchemaForm 从这 4 端点拉配置，避免硬编码状态色 / icon /
错误码 / 权限门禁。

V1.1 改进：
- enum 字典：19 组（含 P0–P4 全部 enum 类）
- state-machine：13 StateTransition 事件 × 9 态 → 含 from/action/to/
  allowed_roles/preconditions/side_effects；从 app/services/state_machine
  派生（单一来源）
- errors：全仓 AST 扫描 PcsError 实例（约 94 条）
- permissions：7 角色 × 全 require_roles 调用点（从 app/api/v1/* 扫描）
- CSV 导出：/meta/permissions.csv

设计原则：
- 枚举从 app/models/enums.py + schemas/stream.py 派生（颜色/icon 写死映射）
- state-machine 字段从 app/services/state_machine.ALLOWED_TRANSITIONS +
  TRANSITION_ROLES + TRANSITION_AUDIT_ACTION + SNAPSHOT_TRIGGERS 派生
- errors / permissions V1.1 自动 AST 扫仓（前端可直接消费全量）
"""
from __future__ import annotations

import ast
import glob
from enum import Enum
from typing import Any

from app.models.enums import (
    ActualDataStatus,
    CalcStatus,
    CheckResult,
    ConfigStatus,
    ConfigTransition,
    DeliverableSignStatus,
    DesignStage,
    EquipmentStatus,
    FlowPattern,
    PipeType,
    PumpOperation,
    RecordSignStatus9,
    SnapshotStatus,
    StreamSignStatus,
    TwoPhaseCheck,
    WorkspaceType,
)
from app.schemas.stream import StatePointCaseType, StreamCaseType
from app.services.state_machine import (
    ALLOWED_TRANSITIONS,
    SNAPSHOT_TRIGGERS,
    TRANSITION_AUDIT_ACTION,
    TRANSITION_ROLES,
)


# StreamDataMode：DB 层 streams.data_mode 是 String(20) + 注释提示，
# 此处提供 enum 以供前端统一消费（值与 model 注释一致）
class StreamDataMode(str, Enum):
    CHEMICAL = "CHEMICAL"
    PETROLEUM = "PETROLEUM"
    SOLID = "SOLID"

# 状态色 + icon 与 pcs-frontend/src/styles/tokens.css + PCS-UI-SPEC §6.1 对齐
_STATE_META: dict[str, dict[str, str]] = {
    "DRAFT":              {"color": "state-draft",           "icon": "EditOutlined"},
    "IN_APPROVAL":        {"color": "state-in-approval",     "icon": "LoadingOutlined"},
    "CHECKED":            {"color": "state-checked",         "icon": "CheckCircleOutlined"},
    "CHECK_REJECTED":     {"color": "state-check-rejected",  "icon": "CloseCircleOutlined"},
    "STALE":              {"color": "state-stale",           "icon": "WarningOutlined"},
    "CHANGE_PENDING":     {"color": "state-change-pending",  "icon": "EditOutlined"},
    "CHANGED":            {"color": "state-changed",         "icon": "SwapOutlined"},
    "REVERSAL_PENDING":   {"color": "state-reversal-pending", "icon": "UndoOutlined"},
    "OBSOLETE":           {"color": "state-obsolete",        "icon": "StopOutlined"},
}

_STATE_LABEL_ZH: dict[str, str] = {
    "DRAFT": "草稿", "IN_APPROVAL": "批准中", "CHECKED": "已批准",
    "CHECK_REJECTED": "已退回", "STALE": "数据存疑", "CHANGE_PENDING": "变更中",
    "CHANGED": "已变更", "REVERSAL_PENDING": "撤销中", "OBSOLETE": "已作废",
    "PENDING": "待处理", "APPROVED": "已批准",
    "PUBLISHED": "已发布",
    "NOT_CALCULATED": "未计算", "CALCULATING": "计算中",
    "COMPLETED": "已完成", "NEED_RECALC": "需重算",
    "NOT_ENTERED": "未录入", "PENDING_CONFIRM": "待确认", "CONFIRMED": "已确认",
    "NORMAL": "正常", "STANDBY": "备用", "OFF": "停运",
    "BASIC": "基础设计", "DETAIL": "详细设计",
    "ANNULAR": "环状流", "MIST": "雾状流", "BUBBLE": "泡状流",
    "SLUG": "段塞流", "STRATIFIED": "分层流", "WAVE": "波状流",
    "CHEMICAL": "化学品", "PETROLEUM": "石油", "SOLID": "固体",
    "END_OF_RUN": "末期", "START_OF_RUN": "开车", "TURN_DOWN": "调节",
    "MIN": "最小", "MAX": "最大", "ALTERNATE": "可替",
    "FORMAL": "正式", "PERSONAL": "个人", "TEMPORARY": "临时",
    "ACTIVE": "活跃", "CONSUMED": "已消费", "ABANDONED": "已废弃",
    "PUMP_SUCTION": "泵吸入管", "PUMP_DISCHARGE": "泵排出管",
    "SELF_FLOW": "自流", "HEATING_STEAM": "蒸汽伴热", "TWO_PHASE": "两相流",
    "PASS": "合格", "FAIL": "不合格", "WARNING": "警告",
}


def _enum_to_dict(enum_cls: type, *, with_meta: bool = True) -> list[dict[str, Any]]:
    """把 enum 类转成 [{value, label, color?, icon?, order?}, ...] 列表。"""
    out: list[dict[str, Any]] = []
    for order, member in enumerate(enum_cls.__members__.values(), start=1):
        value = member.value
        item: dict[str, Any] = {
            "value": value,
            "label": _STATE_LABEL_ZH.get(value, value),
            "order": order,
        }
        if with_meta and value in _STATE_META:
            item["color"] = _STATE_META[value]["color"]
            item["icon"] = _STATE_META[value]["icon"]
        out.append(item)
    return out


def get_enums() -> dict[str, list[dict[str, Any]]]:
    """19 组枚举字典（含 RecordSignStatus 9 态全集 + StreamDataMode +
    StreamCaseType/StatePointCaseType + P2 配置资产 + SUP-008 管道/泵）。"""
    return {
        "RecordSignStatus":     _enum_to_dict(RecordSignStatus9),
        "StreamSignStatus":     _enum_to_dict(StreamSignStatus),
        "DeliverableSignStatus": _enum_to_dict(DeliverableSignStatus, with_meta=False),
        "WorkspaceType":        _enum_to_dict(WorkspaceType, with_meta=False),
        "EquipmentStatus":      _enum_to_dict(EquipmentStatus, with_meta=False),
        "CalcStatus":           _enum_to_dict(CalcStatus, with_meta=False),
        "ActualDataStatus":     _enum_to_dict(ActualDataStatus, with_meta=False),
        "SnapshotStatus":       _enum_to_dict(SnapshotStatus, with_meta=False),
        "ConfigStatus":         _enum_to_dict(ConfigStatus, with_meta=False),
        "ConfigTransition":     _enum_to_dict(ConfigTransition, with_meta=False),
        "PipeType":             _enum_to_dict(PipeType, with_meta=False),
        "CheckResult":          _enum_to_dict(CheckResult, with_meta=False),
        "PumpOperation":        _enum_to_dict(PumpOperation, with_meta=False),
        "DesignStage":          _enum_to_dict(DesignStage, with_meta=False),
        "FlowPattern":          _enum_to_dict(FlowPattern, with_meta=False),
        "TwoPhaseCheck":        _enum_to_dict(TwoPhaseCheck, with_meta=False),
        "StreamDataMode":       _enum_to_dict(StreamDataMode, with_meta=False),
        "StreamCaseType":       _enum_to_dict(StreamCaseType, with_meta=False),
        "StatePointCaseType":   _enum_to_dict(StatePointCaseType, with_meta=False),
    }


def _preconditions_for(action: str, from_state: str) -> list[str]:
    """从 state_machine 派生 preconditions（前端禁用按钮 + tooltip）。"""
    pre: list[str] = []
    if action == "MARK_STALE":
        pre.append("源快照哈希与下游比对不一致")
    if action == "INITIATE_CHANGE":
        pre.append(f"当前 {from_state} 且绑定 ConfigAsset/ConfigVersion")
    if action == "REQUEST_REVERSAL":
        pre.append("CHANGED 状态且未被交付物绑定")
    if action in ("APPROVE_REVERSAL", "REJECT_REVERSAL"):
        pre.append("存在 ACTIVE 快照")
    if action == "OBSOLETE":
        pre.append("无下游引用（计算结果/状态点）")
    return pre


def _side_effects_for(action: str) -> list[str]:
    """从 state_machine 派生 side_effects（前端告知用户后果）。"""
    eff: list[str] = []
    if action in SNAPSHOT_TRIGGERS:
        eff.append("CREATE record_change_snapshot")
    if action in ("PASS_CHECK", "REJECT_CHECK"):
        eff.append("WRITE audit_log")
    if action == "OBSOLETE":
        eff.append("WRITE audit_log + 阻断下游引用")
    if action in TRANSITION_AUDIT_ACTION:
        eff.append(f"AUDIT {TRANSITION_AUDIT_ACTION[action].name}")
    return eff


def get_state_machine() -> dict[str, Any]:
    """13 事件 × 9 态迁移表 — 从 ALLOWED_TRANSITIONS 派生，含
    from/action/to/allowed_roles/preconditions/side_effects。
    """
    transitions: list[dict[str, Any]] = []
    for (from_state, event), to_state in ALLOWED_TRANSITIONS.items():
        transitions.append({
            "from": from_state.value,
            "action": event.value,
            "to": to_state.value,
            "allowed_roles": sorted(TRANSITION_ROLES.get(event, set())),
            "preconditions": _preconditions_for(event.value, from_state.value),
            "side_effects": _side_effects_for(event.value),
        })
    return {
        "transitions": transitions,
        "allowed": {
            from_state.value: sorted(
                {e.value for (f, e), _ in ALLOWED_TRANSITIONS.items() if f == from_state}
            )
            for from_state in RecordSignStatus9
        },
    }


# 权限：AST 扫 app/api/v1/*.py 的 require_roles(user, "X", "Y", ...) 调用点
_PERMISSIONS_CACHE: list[dict[str, str]] | None = None


def _scan_permissions() -> list[dict[str, str]]:
    """AST 扫 app/api/v1/*.py 的 require_roles(user, "X", "Y", ...) 调用点。"""
    perms: list[dict[str, str]] = []
    seen: set[tuple[str, str, str]] = set()
    for fn in glob.glob("app/api/v1/*.py"):
        if "test_" in fn:
            continue
        with open(fn) as f:
            try:
                tree = ast.parse(f.read())
            except SyntaxError:
                continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            f2 = node.func
            if not (isinstance(f2, ast.Name) and f2.id == "require_roles"):
                continue
            if len(node.args) < 2:
                continue
            roles: list[str] = []
            for a in node.args[1:]:
                if isinstance(a, ast.Constant) and isinstance(a.value, str):
                    roles.append(a.value)
            if not roles:
                continue
            resource = fn.replace("app/api/v1/", "").replace(".py", "")
            for role in roles:
                key = (role, resource, "WRITE")
                if key in seen:
                    continue
                seen.add(key)
                perms.append({
                    "role": role,
                    "resource": resource,
                    "action": "WRITE",
                    "permission_code": f"{resource.upper()}.WRITE",
                    "frontend_behavior": "show",
                })
    return perms


def get_permissions() -> list[dict[str, str]]:
    """权限矩阵 — 7 角色 × 所有 require_roles 调用点 + 状态机 TRANSITION_ROLES。"""
    global _PERMISSIONS_CACHE  # noqa: PLW0603
    if _PERMISSIONS_CACHE is None:
        perms = _scan_permissions()
        for event, roles in TRANSITION_ROLES.items():
            for role in sorted(roles):
                if (role, "state_machine", event.value) in seen_keys(perms):
                    continue
                perms.append({
                    "role": role,
                    "resource": "state_machine",
                    "action": event.value,
                    "permission_code": f"STATE_MACHINE.{event.value}",
                    "frontend_behavior": "show",
                })
        _PERMISSIONS_CACHE = perms
    return list(_PERMISSIONS_CACHE)


def seen_keys(perms: list[dict[str, str]]) -> set[tuple[str, str, str]]:
    return {(p["role"], p["resource"], p["action"]) for p in perms}


def get_permissions_csv() -> str:
    """权限矩阵 CSV 导出（前端可下载做权限审计）。"""
    lines = ["role,resource,action,permission_code,frontend_behavior"]
    for p in get_permissions():
        lines.append(",".join([
            p["role"], p["resource"], p["action"],
            p["permission_code"], p["frontend_behavior"],
        ]))
    return "\n".join(lines) + "\n"


# 错误码：AST 扫全仓 PcsError 实例
_UI_BEHAVIORS = {
    400: "block_toast", 401: "redirect_to_login", 403: "disable_with_tooltip",
    404: "block_toast", 409: "modal_confirm", 410: "block_toast",
    413: "block_toast", 422: "inline_field_error", 500: "block_toast_with_trace",
}


def _scan_error_codes() -> list[dict[str, Any]]:
    """AST 扫 app/ 全仓 raise PcsError(...) 实例。"""
    codes: dict[str, dict[str, Any]] = {}
    for fn in glob.glob("app/**/*.py", recursive=True):
        if "test_" in fn or "/migrations/" in fn:
            continue
        with open(fn) as f:
            try:
                tree = ast.parse(f.read())
            except SyntaxError:
                continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Raise):
                continue
            exc = node.exc
            if not isinstance(exc, ast.Call):
                continue
            cf = exc.func
            if not (isinstance(cf, ast.Name) and cf.id == "PcsError"):
                continue
            kw = {k.arg: k.value for k in exc.keywords if k.arg}
            if "code" not in kw or not isinstance(kw["code"], ast.Constant):
                continue
            code = kw["code"].value
            msg_node = kw.get("message", exc.args[0] if exc.args else None)
            msg: str = ""
            if isinstance(msg_node, ast.Constant):
                msg = msg_node.value
            elif isinstance(msg_node, ast.JoinedStr):
                parts: list[str] = []
                for x in msg_node.values:
                    parts.append(x.value if isinstance(x, ast.Constant) else "...")
                msg = "".join(parts)
            status = 400
            if "status" in kw and isinstance(kw["status"], ast.Constant):
                status = kw["status"].value
            if code in codes:
                if msg and len(msg) > len(codes[code]["message"]):
                    codes[code]["message"] = msg
                continue
            codes[code] = {
                "code": code,
                "http": status,
                "message": msg,
                "ui_behavior": _UI_BEHAVIORS.get(status, "block_toast"),
            }
    return sorted(codes.values(), key=lambda e: e["code"])


def get_error_codes() -> list[dict[str, Any]]:
    """错误码全集（全仓 AST 派生）。"""
    return _scan_error_codes()