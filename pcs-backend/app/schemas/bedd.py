"""BEDD 文档结构（P10-H · T2 · TODO-195 · SPEC §7.5）。

## 为什么是这 9 个分组

`docs/PCS-UI-SPEC.md` §7.5「BEDD 编辑：分组 Tab」逐字给了 Tab 表：

| Tab | 内容 |
|---|---|
| 气象 | 温度/湿度/气压/风/降雨/雪/蒸发/雷暴/雾/日照/太阳辐射/土壤/粉尘/海拔 |
| 水文地质 | 潮汐/河流/地质 |
| 地震 | 设防烈度/加速度/分组/场地类别 |
| 公用工程 | 蒸汽/水/空气/氮气/燃料气/燃料油/氢气/化学品/导热油/凝液/电气 |
| 排放限值 | 气体/焚烧/粉尘/废水/噪声/工作区空气 |
| 设计准则 | 设计寿命/操作/运输/噪声 |
| 安全消防 | 消防泵/消防车/泡沫/喷淋/探测/隔离阀/安全淋浴 |
| 火炬 | 背压/辐射 |
| 界面条件 | 进出界区条件表 |

⇒ ⇒ **本模块是那份表的唯一机器可读副本** ⇒ ⇒ 校验（模型）与表单渲染
（uiSchema）**从同一份来** ⇒ ⇒ 不会漂。

## 人裁（2026-11-23）

「BEDD 存什么？」⇒ ⇒ **按 SPEC：9 个分组**（不是前端 /bedd 页画的那套
「章节 + 签名」）⇒ ⇒ 前端那一页要改成分组表单。

## 为什么模型是**动态生成**的

字段清单（`BEDD_FIELDS`）是 SPEC 的抄本 ⇒ ⇒ 抄两遍（模型 + 表单）必然漂
⇒ ⇒ 这里用 `pydantic.create_model` **从同一张表**生成 9 个分组模型
⇒ ⇒ 模型与表单**同一份真相源**。

⚠️ **动态模型也要进 OpenAPI**（`components.schemas`）—— FastAPI / pydantic
会自动收进去 ⇒ ⇒ 前端 `openapi-typescript` 拿得到**具名类型**（不是裸 dict）
⇒ ⇒ 也不给「裸载荷字段」闸（`check_openapi_payload_coverage.py`）添债。

## 值为什么大多是「文本」

SPEC **没有给字段类型**（§7.5 只给字段名）⇒ ⇒ 编造类型就是**猜**
⇒ ⇒ 只把**明确是量**的字段（温度/压力/加速度/噪声/寿命/背压/辐射…）定成
数字，其余按**文本**（可填「厂区自产 / 外购」「详见附件」）。
"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, create_model

#: 字段类型：数字 / 文本。
BeddFieldKind = Literal["number", "text"]

#: 分组 key → ((字段 key, 中文标签, 控件类型, 字段类型, **canonical 单位**), ...)
#:
#: 控件类型取 `ui_schema_service.Widget` 的字面量（Input / NumberInput /
#: TextArea / Select）⇒ ⇒ 前端 SchemaForm 直接认。
#:
#: ⚠️ **第五个元素 = canonical 单位**（机器可读 · P10-K · W-1）⇒ ⇒ ⇒
#: **单位不再写在标签里** ⇒ ⇒ ⇒ 理由：标签里带单位 ⇒ ⇒ ⇒ 换算只能改字符串
#: ⇒ ⇒ ⇒ 而「US 模式下标签还写 kPa、值是 psi」= **双重单位 / 假标签**
#: ⇒ ⇒ ⇒ 标签的渲染由前端拼 `unit`（SI）或 `unit_display.display_unit`（US）。
#:
#: ⚠️ **canonical 单位 = 存储单位**（**恒 SI**）⇒ ⇒ ⇒ `None` = **无单位**
#: （介质、类别这类**本来就没有数可换**的字段）。
BeddFieldUnit = str | None

BEDD_FIELDS: dict[str, tuple[tuple[str, str, str, BeddFieldKind, BeddFieldUnit], ...]] = {
    "meteorology": (
        ("temperature", "温度", "NumberInput", "number", "degC"),
        ("humidity", "湿度", "NumberInput", "number", "%"),
        ("pressure", "气压", "NumberInput", "number", "kPa"),
        ("wind", "风", "NumberInput", "number", "m/s"),
        ("rainfall", "降雨", "NumberInput", "number", "mm/a"),
        ("snowfall", "雪", "NumberInput", "number", "mm/a"),
        ("evaporation", "蒸发", "NumberInput", "number", "mm/a"),
        ("thunderstorm", "雷暴", "NumberInput", "number", "d/a"),
        ("fog", "雾", "NumberInput", "number", "d/a"),
        ("sunshine", "日照", "NumberInput", "number", "h/a"),
        ("solar_radiation", "太阳辐射", "NumberInput", "number", "W/m2"),
        ("soil", "土壤", "Input", "text", None),
        ("dust", "粉尘", "Input", "text", None),
        ("altitude", "海拔", "NumberInput", "number", "m"),
    ),
    "hydrology_geology": (
        ("tidal", "潮汐", "Input", "text", None),
        ("river", "河流", "Input", "text", None),
        ("geology", "地质", "Input", "text", None),
    ),
    "seismic": (
        ("intensity", "设防烈度", "Input", "text", None),
        ("acceleration", "加速度", "NumberInput", "number", "g"),
        ("group", "分组", "Input", "text", None),
        ("site_category", "场地类别", "Input", "text", None),
    ),
    "utilities": (
        ("steam", "蒸汽", "Input", "text", None),
        ("water", "水", "Input", "text", None),
        ("air", "空气", "Input", "text", None),
        ("nitrogen", "氮气", "Input", "text", None),
        ("fuel_gas", "燃料气", "Input", "text", None),
        ("fuel_oil", "燃料油", "Input", "text", None),
        ("hydrogen", "氢气", "Input", "text", None),
        ("chemicals", "化学品", "Input", "text", None),
        ("heat_transfer_oil", "导热油", "Input", "text", None),
        ("condensate", "凝液", "Input", "text", None),
        ("electrical", "电气", "Input", "text", None),
    ),
    "emission_limits": (
        ("gas", "气体", "Input", "text", None),
        ("incineration", "焚烧", "Input", "text", None),
        ("dust", "粉尘", "Input", "text", None),
        ("wastewater", "废水", "Input", "text", None),
        ("noise", "噪声", "NumberInput", "number", "dB"),
        ("workplace_air", "工作区空气", "Input", "text", None),
    ),
    "design_criteria": (
        ("design_life", "设计寿命", "NumberInput", "number", "a"),
        ("operation", "操作", "Input", "text", None),
        ("transportation", "运输", "Input", "text", None),
        ("noise", "噪声", "NumberInput", "number", "dB"),
    ),
    "safety_fire": (
        ("fire_pump", "消防泵", "Input", "text", None),
        ("fire_truck", "消防车", "Input", "text", None),
        ("foam", "泡沫", "Input", "text", None),
        ("sprinkler", "喷淋", "Input", "text", None),
        ("detection", "探测", "Input", "text", None),
        ("isolation_valve", "隔离阀", "Input", "text", None),
        ("safety_shower", "安全淋浴", "Input", "text", None),
    ),
    "flare": (
        ("back_pressure", "背压", "NumberInput", "number", "kPa"),
        ("radiation", "辐射", "NumberInput", "number", "kW/m2"),
    ),
    "interface_conditions": (
        ("inlet", "进界区条件表", "Input", "text", None),
        ("outlet", "出界区条件表", "Input", "text", None),
    ),
}

#: 分组 key → 中文 Tab 名（SPEC §7.5 的 Tab 表）。
BEDD_GROUP_LABELS: dict[str, str] = {
    "meteorology": "气象",
    "hydrology_geology": "水文地质",
    "seismic": "地震",
    "utilities": "公用工程",
    "emission_limits": "排放限值",
    "design_criteria": "设计准则",
    "safety_fire": "安全消防",
    "flare": "火炬",
    "interface_conditions": "界面条件",
}

#: 分组顺序 = SPEC 的 Tab 顺序。
BEDD_GROUP_ORDER: tuple[str, ...] = tuple(BEDD_GROUP_LABELS)


def _group_model(group_key: str) -> type[BaseModel]:
    """按字段表生成一个分组模型（`extra="forbid"` ⇒ ⇒ 未知字段 ⇒ 422）。"""
    fields: dict[str, Any] = {}
    for field_key, _label, _widget, kind, _unit in BEDD_FIELDS[group_key]:
        annotation = float | None if kind == "number" else str | None
        fields[field_key] = (annotation | None, Field(default=None))
    model = create_model(
        f"Bedd{_camel(group_key)}",
        __config__=ConfigDict(extra="forbid"),
        **fields,
    )
    model.__doc__ = f"BEDD 分组「{BEDD_GROUP_LABELS[group_key]}」（SPEC §7.5）。"
    return model


def _camel(group_key: str) -> str:
    return "".join(part.capitalize() for part in group_key.split("_"))


#: 分组模型（`BEDD_FIELDS` 生成 ⇒ ⇒ 与表单同一份真相源）。
BEDD_GROUP_MODELS: dict[str, type[BaseModel]] = {
    group_key: _group_model(group_key) for group_key in BEDD_FIELDS
}


#: BEDD 文档（9 个分组 ⇒ ⇒ 每组一个可选的分组模型）。
#:
#: ⚠️ **结构由模型保证**：未知分组 / 未知字段 ⇒ **422**
#: （`extra="forbid"` ⇒ ⇒ 不静默丢字段）。
#:
#: ⚠️ **也是动态生成的** —— 分组清单只有 `BEDD_FIELDS` 一份 ⇒ ⇒ 手写一遍
#: 就会漂（多一个分组忘了加字段 ⇒ ⇒ 那个分组永远收不到值）。
BeddDocument = create_model(
    "BeddDocument",
    __config__=ConfigDict(extra="forbid"),
    **{
        group_key: (BEDD_GROUP_MODELS[group_key] | None, Field(default=None))
        for group_key in BEDD_FIELDS
    },
)
BeddDocument.__doc__ = "BEDD 文档（9 个分组 · SPEC §7.5）。"


class BeddResponse(BaseModel):
    """`GET /projects/{project_id}/bedd` 响应。"""

    model_config = ConfigDict(from_attributes=True)

    project_id: str
    document: BeddDocument = Field(
        default_factory=BeddDocument, description="BEDD 文档（9 个分组）"
    )
    updated_at: str | None = Field(
        default=None, description="项目行的更新时间（bedd_json 的写入时刻）"
    )
