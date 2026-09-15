"""uiSchema 服务 — 表单节点契约（P45-2-0 / Task 18.5）。

与 Task 4.5 区别：
- Task 4.5 = enum / state-machine / permissions / error-codes 数据字典
- Task 18.5 = 表单节点结构（visible/required/hidden/placeholder/help/order/widget）
  — 驱动前端 SchemaForm 渲染。

资源首批（覆盖 P0–P4 主表单）：
stream / workspace / record / pipe_class / equipment。

数据源策略：硬编码字典（与 SPEC §8.3 widget 映射对齐）。Pydantic Field metadata
派生留待 P5 复用（需统一定义 metadata 字段，成本高于 4h）。

widget 取值（与 SPEC §8.3 + 前端 SchemaForm controls/ 对齐）：
Input / Select / NumberInput / TextArea / Switch / DatePicker / AutoComplete /
Cascader / TagPicker。
"""
from __future__ import annotations

from enum import Enum
from typing import Any


class Widget(str, Enum):
    """SchemaForm 控件类型枚举。"""

    INPUT = "Input"
    SELECT = "Select"
    NUMBER_INPUT = "NumberInput"
    TEXT_AREA = "TextArea"
    SWITCH = "Switch"
    DATE_PICKER = "DatePicker"
    AUTO_COMPLETE = "AutoComplete"
    CASCADER = "Cascader"
    TAG_PICKER = "TagPicker"


SCHEMA_VERSION = "1.0.0"


# === resource × fields 表 ===

_FIELDS: dict[str, list[dict[str, Any]]] = {
    "stream": [
        {
            "path": "stream_name",
            "label": "管段物流号",
            "widget": Widget.INPUT.value,
            "required": True,
            "placeholder": "如 FEED-101",
            "help": "物流唯一标识（最大 100 字符）",
            "order": 10,
            "min_length": 1,
            "max_length": 100,
        },
        {
            "path": "case_type",
            "label": "物流工况",
            "widget": Widget.SELECT.value,
            "required": True,
            "enum_group": "StreamCaseType",
            "help": "NORMAL / END_OF_RUN / START_OF_RUN / TURN_DOWN",
            "order": 20,
        },
        {
            "path": "data_mode",
            "label": "数据模式",
            "widget": Widget.SELECT.value,
            "required": True,
            "enum_group": "StreamDataMode",
            "help": "CHEMICAL / PETROLEUM / SOLID",
            "order": 30,
        },
        {
            "path": "description",
            "label": "物流描述",
            "widget": Widget.TEXT_AREA.value,
            "required": False,
            "placeholder": "可选描述",
            "order": 40,
            "max_length": 500,
        },
        {
            "path": "phase",
            "label": "相态",
            "widget": Widget.SELECT.value,
            "enum_group": "Phase",
            "help": "VAPOR / LIQUID / MIXED / SOLID",
            "order": 50,
        },
        {
            "path": "temp",
            "label": "温度",
            "widget": Widget.NUMBER_INPUT.value,
            "unit": "°C",
            "order": 60,
        },
        {
            "path": "press",
            "label": "压力",
            "widget": Widget.NUMBER_INPUT.value,
            "unit": "kPa",
            "order": 70,
        },
        {
            "path": "mass_flow",
            "label": "质量流量",
            "widget": Widget.NUMBER_INPUT.value,
            "unit": "kg/h",
            "order": 80,
        },
        {
            "path": "composition_json",
            "label": "组成（CAS→摩尔分率）",
            "widget": Widget.TEXT_AREA.value,
            "help": "JSON 文本；前端用 JsonEditor 渲染",
            "order": 200,
            "visible": False,
        },
    ],

    "workspace": [
        {
            "path": "workspace_type",
            "label": "工作区类型",
            "widget": Widget.SELECT.value,
            "required": True,
            "enum_group": "WorkspaceType",
            "help": "FORMAL / PERSONAL / TEMPORARY",
            "order": 10,
        },
        {
            "path": "name",
            "label": "工作区名称",
            "widget": Widget.INPUT.value,
            "required": True,
            "placeholder": "请输入名称",
            "order": 20,
            "min_length": 1,
            "max_length": 200,
        },
        {
            "path": "project_id",
            "label": "项目 ID",
            "widget": Widget.INPUT.value,
            "required": False,
            "placeholder": "UUID",
            "help": "可选；FORMAL 必填",
            "order": 30,
        },
        {
            "path": "retention_days",
            "label": "保留天数",
            "widget": Widget.NUMBER_INPUT.value,
            "unit": "天",
            "help": "1~365；默认由后端策略",
            "order": 40,
        },
    ],

    "record": [
        {
            "path": "record_type",
            "label": "记录类型",
            "widget": Widget.INPUT.value,
            "readonly": True,
            "order": 10,
            "help": "如 stream / workspace / pipe_class",
        },
        {
            "path": "record_id",
            "label": "记录 ID",
            "widget": Widget.INPUT.value,
            "readonly": True,
            "order": 20,
        },
        {
            "path": "sign_status",
            "label": "签章状态",
            "widget": Widget.SELECT.value,
            "readonly": True,
            "enum_group": "RecordSignStatus",
            "help": "9 态全集（前端只读）",
            "order": 30,
        },
        {
            "path": "transition",
            "label": "迁移事件",
            "widget": Widget.SELECT.value,
            "required": True,
            "enum_group": "ConfigTransition",
            "help": "按 state-machine 允许的事件",
            "order": 40,
        },
        {
            "path": "reason",
            "label": "变更原因",
            "widget": Widget.TEXT_AREA.value,
            "required": False,
            "placeholder": "请说明原因",
            "order": 50,
        },
    ],

    "pipe_class": [
        {
            "path": "class_id",
            "label": "管子等级代号",
            "widget": Widget.INPUT.value,
            "required": True,
            "placeholder": "如 1A1",
            "order": 10,
            "min_length": 1,
            "max_length": 20,
        },
        {
            "path": "class_name",
            "label": "管子等级名称",
            "widget": Widget.INPUT.value,
            "required": True,
            "order": 20,
            "min_length": 1,
            "max_length": 200,
        },
        {
            "path": "material_standard",
            "label": "材料标准",
            "widget": Widget.INPUT.value,
            "required": True,
            "order": 30,
            "min_length": 1,
            "max_length": 100,
        },
        {
            "path": "corrosion_allowance",
            "label": "腐蚀裕量",
            "widget": Widget.NUMBER_INPUT.value,
            "required": True,
            "unit": "mm",
            "help": "≥ 0",
            "order": 40,
        },
        {
            "path": "design_pressure",
            "label": "设计压力",
            "widget": Widget.NUMBER_INPUT.value,
            "required": True,
            "unit": "MPaG",
            "help": "> 0",
            "order": 50,
        },
        {
            "path": "design_temperature",
            "label": "设计温度",
            "widget": Widget.NUMBER_INPUT.value,
            "required": True,
            "unit": "°C",
            "order": 60,
        },
        {
            "path": "flange_class",
            "label": "法兰等级",
            "widget": Widget.INPUT.value,
            "required": True,
            "placeholder": "如 150LB / 300LB",
            "order": 70,
            "min_length": 1,
            "max_length": 20,
        },
    ],

    "equipment": [
        {
            "path": "equipment_name",
            "label": "设备名称",
            "widget": Widget.INPUT.value,
            "required": True,
            "order": 10,
            "min_length": 1,
            "max_length": 200,
        },
        {
            "path": "equipment_type",
            "label": "设备类型",
            "widget": Widget.INPUT.value,
            "required": True,
            "placeholder": "如 PUMP / CV / TOWER",
            "order": 20,
            "min_length": 1,
            "max_length": 30,
        },
        {
            "path": "material",
            "label": "材质",
            "widget": Widget.INPUT.value,
            "required": True,
            "order": 30,
            "min_length": 1,
            "max_length": 200,
        },
        {
            "path": "original_tag",
            "label": "原项目位号",
            "widget": Widget.INPUT.value,
            "required": True,
            "order": 40,
            "min_length": 1,
            "max_length": 50,
        },
        {
            "path": "weight_kg",
            "label": "重量",
            "widget": Widget.NUMBER_INPUT.value,
            "required": False,
            "unit": "kg",
            "help": "> 0（如有必填）",
            "order": 50,
        },
        {
            "path": "commissioning_date",
            "label": "投用日期",
            "widget": Widget.DATE_PICKER.value,
            "required": True,
            "help": "YYYY-MM-DD",
            "order": 60,
        },
    ],
}


def list_resources() -> list[str]:
    """返回已配置 uiSchema 的资源列表（用于 OpenAPI 文档 + 客户端预加载）。"""
    return list(_FIELDS.keys())


def get_ui_schema(resource: str) -> dict[str, Any]:
    """按 resource 返回 uiSchema；未知 resource 抛 KeyError。

    返回结构：
    {
      "schema_version": "1.0.0",
      "resource": "stream",
      "fields": [{path, label, widget, required?, readonly?, enum_group?,
                  placeholder?, help?, order?, unit?, min_length?, max_length?,
                  visible?, hidden_when?}, ...]
    }
    """
    if resource not in _FIELDS:
        raise KeyError(resource)
    return {
        "schema_version": SCHEMA_VERSION,
        "resource": resource,
        "fields": _FIELDS[resource],
    }