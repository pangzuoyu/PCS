"""Meta API 服务层 — 枚举字典 + 状态机 + 权限码 + 错误码。

P4.5 前端补课 Sprint (P45-0-4)。前端 13 组件 + SchemaForm 从这 4 端点
拉配置，避免硬编码状态色 / icon / 错误码 / 权限门禁。

设计原则：
- enum 字典从 app/models/enums.py 单一来源派生（颜色/icon 写死映射；不引 SQL）
- state-machine transitions 从 app/services/state_machine 派生
- permissions / error-codes V1 仅返回骨架（前端先用，V1.1 从源码 grep 补全）
"""
from __future__ import annotations

from typing import Any

from app.models.enums import (
    CalcStatus,
    DeliverableSignStatus,
    EquipmentStatus,
    RecordSignStatus9,
    SnapshotStatus,
    StreamSignStatus,
    WorkspaceType,
)

# 状态色 + icon 与 pcs-frontend/src/styles/tokens.css + PCS-UI-SPEC §6.1 一致
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
    "DRAFT": "草稿",
    "IN_APPROVAL": "批准中",
    "CHECKED": "已批准",
    "CHECK_REJECTED": "已退回",
    "STALE": "数据存疑",
    "CHANGE_PENDING": "变更中",
    "CHANGED": "已变更",
    "REVERSAL_PENDING": "撤销中",
    "OBSOLETE": "已作废",
    "PENDING": "待处理",
    "APPROVED": "已批准",
}


def _enum_to_dict(enum_cls: type, *, with_meta: bool = True) -> list[dict[str, Any]]:
    """把 enum 类转成 [{value, label, color?, icon?, order?}, ...] 列表。"""
    out: list[dict[str, Any]] = []
    for order, member in enumerate(enum_cls.__members__.values(), start=1):
        item: dict[str, Any] = {
            "value": member.value,
            "label": _STATE_LABEL_ZH.get(member.value, member.value),
            "order": order,
        }
        if with_meta and member.value in _STATE_META:
            item["color"] = _STATE_META[member.value]["color"]
            item["icon"] = _STATE_META[member.value]["icon"]
        out.append(item)
    return out


def get_enums() -> dict[str, list[dict[str, Any]]]:
    """枚举字典：9 态全集 / StreamSignStatus / DeliverableStatus / WorkspaceType / EquipmentStatus / CalcStatus / SnapshotStatus。"""  # noqa: E501
    return {
        "RecordSignStatus": _enum_to_dict(RecordSignStatus9),
        "StreamSignStatus": _enum_to_dict(StreamSignStatus),
        "DeliverableStatus": _enum_to_dict(DeliverableSignStatus, with_meta=False),
        "WorkspaceType": _enum_to_dict(WorkspaceType, with_meta=False),
        "EquipmentStatus": _enum_to_dict(EquipmentStatus, with_meta=False),
        "CalcStatus": _enum_to_dict(CalcStatus, with_meta=False),
        "SnapshotStatus": _enum_to_dict(SnapshotStatus, with_meta=False),
    }


# 状态机迁移表（与 P4 实施一致；9 态全集）
# 格式：from -> [可执行动作]
# 动作 SUBMIT / OBSOLETE / APPROVE / REJECT / WITHDRAW / RESUBMIT /
#       CONFIRM_RECALC / CHANGE_SUBMIT / CHANGE_APPROVE / CHANGE_REJECT /
#       REVERSE_SUBMIT / REVERSE_APPROVE / REVERSE_REJECT
_STATE_MACHINE_TRANSITIONS: dict[str, list[str]] = {
    "DRAFT":              ["SUBMIT", "OBSOLETE"],
    "IN_APPROVAL":        ["APPROVE", "REJECT", "WITHDRAW"],
    "CHECKED":            ["CHANGE_SUBMIT", "OBSOLETE"],
    "CHECK_REJECTED":     ["RESUBMIT", "OBSOLETE"],
    "STALE":              ["CONFIRM_RECALC", "OBSOLETE"],
    "CHANGE_PENDING":     ["CHANGE_APPROVE", "CHANGE_REJECT", "WITHDRAW"],
    "CHANGED":            ["REVERSE_SUBMIT", "OBSOLETE"],
    "REVERSAL_PENDING":   ["REVERSE_APPROVE", "REVERSE_REJECT"],
    "OBSOLETE":           [],
}


def get_state_machine() -> dict[str, Any]:
    """9 态状态机迁移表 + allowed 字典。

    transitions[] 含 from/action/to/allowed_roles/preconditions — V1 仅返 from/action，
    V1.1 从 app/services/state_machine.py 抽完整字段。
    """
    transitions = [
        {"from": frm, "action": action}
        for frm, actions in _STATE_MACHINE_TRANSITIONS.items()
        for action in actions
    ]
    return {
        "transitions": transitions,
        "allowed": _STATE_MACHINE_TRANSITIONS,
    }


# V1 骨架 — 5 角色 × 资源 × 动作
# 后续 V1.1 从 app/api/deps.py + 各端点扫描 Depends(...) 抽权限码全集
_DESIGNER_STREAM = {"role": "DESIGNER", "resource": "STREAM", "action": "WRITE", "permission_code": "STREAM.WRITE", "frontend_behavior": "show"}  # noqa: E501
_DESIGNER_STREAM_SUBMIT = {"role": "DESIGNER", "resource": "STREAM", "action": "SUBMIT", "permission_code": "STREAM.SUBMIT", "frontend_behavior": "show"}  # noqa: E501
_DESIGNER_PIPE = {"role": "DESIGNER", "resource": "PIPE", "action": "CALCULATE", "permission_code": "PIPE.CALCULATE", "frontend_behavior": "show"}  # noqa: E501
_DESIGNER_DELIV = {"role": "DESIGNER", "resource": "DELIVERABLE", "action": "CREATE", "permission_code": "DELIVERABLE.CREATE", "frontend_behavior": "show"}  # noqa: E501
_DESIGNER_CHG = {"role": "DESIGNER", "resource": "CHANGE_NOTICE", "action": "CREATE", "permission_code": "CHANGE_NOTICE.CREATE", "frontend_behavior": "hide_in_non_formal"}  # noqa: E501
_CHECKER_STREAM = {"role": "CHECKER", "resource": "STREAM", "action": "APPROVE", "permission_code": "STREAM.APPROVE", "frontend_behavior": "show"}  # noqa: E501
_CHECKER_PIPE = {"role": "CHECKER", "resource": "PIPE", "action": "APPROVE", "permission_code": "PIPE.APPROVE", "frontend_behavior": "show"}  # noqa: E501
_REVIEWER_STREAM = {"role": "REVIEWER", "resource": "STREAM", "action": "APPROVE", "permission_code": "STREAM.APPROVE", "frontend_behavior": "show"}  # noqa: E501
_APPROVER_DELIV = {"role": "APPROVER", "resource": "DELIVERABLE", "action": "APPROVE", "permission_code": "DELIVERABLE.APPROVE", "frontend_behavior": "show"}  # noqa: E501
_ADMIN = {"role": "ADMIN", "resource": "*", "action": "*", "permission_code": "*", "frontend_behavior": "show"}  # noqa: E501

_PERMISSIONS_SKELETON: list[dict[str, str]] = [
    _DESIGNER_STREAM,
    _DESIGNER_STREAM_SUBMIT,
    _DESIGNER_PIPE,
    _DESIGNER_DELIV,
    _DESIGNER_CHG,
    _CHECKER_STREAM,
    _CHECKER_PIPE,
    _REVIEWER_STREAM,
    _APPROVER_DELIV,
    _ADMIN,
]


def get_permissions() -> list[dict[str, str]]:
    """权限矩阵骨架（V1）；V1.1 抽全 Depends 派生权限码。"""
    return list(_PERMISSIONS_SKELETON)


# V1 骨架 — PCS 错误码表（前端 ErrorState 渲染用）
# 与 app/core/errors.py + PcsError(code=..., status=...) 派生
_E_STREAM_UNVERIFIED = {"code": "PCS-4031", "http": 403, "message": "物流未校对，不可引用", "ui_behavior": "block_toast"}  # noqa: E501
_E_VALIDATION = {"code": "PCS-4221", "http": 422, "message": "输入校验失败", "ui_behavior": "inline_field_error"}  # noqa: E501
_E_STATE = {"code": "PCS-4222", "http": 422, "message": "状态机迁移不允许", "ui_behavior": "modal_confirm"}  # noqa: E501
_E_CUSTOM = {"code": "PCS-4223", "http": 422, "message": "CUSTOM profile 审批依据缺失", "ui_behavior": "modal_confirm"}  # noqa: E501
_E_PERM = {"code": "PCS-4032", "http": 403, "message": "无权限执行此操作", "ui_behavior": "disable_with_tooltip"}  # noqa: E501
_E_DB = {"code": "PCS-5001", "http": 500, "message": "数据库约束违反", "ui_behavior": "block_toast_with_trace"}  # noqa: E501
_E_TOKEN = {"code": "MISSING_BEARER", "http": 401, "message": "缺少 Bearer token", "ui_behavior": "redirect_to_login"}  # noqa: E501
_E_TTYPE = {"code": "WRONG_TOKEN_TYPE", "http": 401, "message": "token 类型错误", "ui_behavior": "redirect_to_login"}  # noqa: E501
_E_CRED = {"code": "INVALID_CREDENTIALS", "http": 401, "message": "凭据无效", "ui_behavior": "inline_form_error"}  # noqa: E501

_ERROR_CODES_SKELETON: list[dict[str, Any]] = [
    _E_STREAM_UNVERIFIED,
    _E_VALIDATION,
    _E_STATE,
    _E_CUSTOM,
    _E_PERM,
    _E_DB,
    _E_TOKEN,
    _E_TTYPE,
    _E_CRED,
]


def get_error_codes() -> list[dict[str, Any]]:
    """错误码表骨架（V1）；V1.1 扫 PcsError 实例抽全集。"""
    return list(_ERROR_CODES_SKELETON)