"""`/api/v1/report-builder` 的请求/响应模型（Phase 2）。

**零裸 object 响应**（P9A-DLV-010 硬约束）同 `schemas/report.py`：字段树
是前端字段选择器的唯一数据源，一旦有成员是 `object`，`openapi-typescript`
生成的就是 `any`，P9B「类型来自 ./api」的纪律当场断掉。

⚠️ 名字全部带 `Report` 前缀 —— `DatasourceField` 这类通用名会被别处占用，
FastAPI 遇到同名 response_model 时**静默改名后来注册的那个**（bug-158：
`GenerateResponse` 被改写，11 个测试红）。
"""
from __future__ import annotations

import datetime as dt
import uuid

from pydantic import BaseModel, Field


class ReportBuilderField(BaseModel):
    name: str
    type: str          # string | number | date | enum
    label: str
    # JSONB 子键（`容器列.子键`）为 True —— 前端据此提示「取的是 JSON 里的键，
    # 不能直接索引」。缺了这个标记，用户无从区分它与一个真实列。
    is_jsonb_key: bool = False


class ReportBuilderDatasource(BaseModel):
    key: str
    label: str
    model: str
    fields: list[ReportBuilderField]


class ReportBuilderJoin(BaseModel):
    a: str
    a_field: str
    b: str
    b_field: str
    degrade_warn: str | None = None


class ReportBuilderDatasourceList(BaseModel):
    datasources: list[ReportBuilderDatasource]
    joins: list[ReportBuilderJoin] = Field(default_factory=list)


__all__ = ["ReportBuilderField", "ReportBuilderDatasource", "ReportBuilderJoin",
           "ReportBuilderDatasourceList"]

# --- b2/b3 定义管理 ----------------------------------------------------------


class ReportDefSource(BaseModel):
    """`DataSources` 的一项。`join_to` 为空表示不关联。"""

    source: str
    join_to: str | None = None


class ReportDefSelectedField(BaseModel):
    """`SelectedFields` 的一项（SPEC §3.2.2(2)）。"""

    source: str
    field: str
    alias: str = ""
    order: int = 0
    visible: bool = True


class ReportDefCondition(BaseModel):
    """`FilterConditions` 的叶子项（形状对齐 `query_engine._build_condition`）。

    `value` 是联合类型而不是 `Any`：IN / NOT_IN / BETWEEN 收列表，其余收标量。
    写成 `list` 或 `Any` 都是裸载荷（闸门会记一笔）。
    """

    operator: str
    source: str
    field: str
    value: str | float | int | bool | list[str | float | int | bool | None] | None = None


class ReportDefFilterGroup(BaseModel):
    """条件组（AND/OR），可嵌套 —— SPEC §3.2.2(4)「支持 AND/OR 分组，条件可嵌套」。

    `conditions` 是**自引用联合**：`apply_filters` 靠「有没有 conditions 键」
    区分组与叶子，所以两种形状都得能出现在同一个列表里。写成 `list[dict]`
    既丢类型又仍被闸门记为裸载荷。
    """

    operator: str = "AND"          # AND / OR
    # 联合类型里两个类互相递归引用，此刻后者还没定义。文件顶部有
    # `from __future__ import annotations`，注解惰性求值，所以不报错；
    # `model_rebuild()` 在下面负责把它们解析进 Pydantic 的 schema。
    conditions: list[ReportDefCondition | ReportDefFilterGroup] = Field(
        default_factory=list)


ReportDefNode = ReportDefCondition | ReportDefFilterGroup
ReportDefFilterGroup.model_rebuild()


class ReportDefSort(BaseModel):
    source: str
    field: str
    direction: str = "ASC"          # ASC / DESC


class ReportDefinitionBody(BaseModel):
    """`definition_json` 的结构（SPEC §3.2.2(2)）。

    ⚠️ **必须逐字段声明**，不能写 `definition_json: dict`：那是裸 object，
    `openapi-typescript` 给前端生成的就是 `any`，P9B「类型来自 ./api」
    的纪律当场断掉（`scripts/check_openapi_payload_coverage.py` 就是守
    这一条；第一次写成 dict 就被它挡下，71 → 73）。

    结构合法性之外，**字段是否属于它声明的数据源**由
    `definition_service.validate_definition_json` 对注册表核对 —— Pydantic
    表达不了「tag_number 属于 EQUIP_LIST 但不属于 PIPING_RESULTS」这种
    跨源规则。
    """

    DataSources: list[ReportDefSource] = Field(default_factory=list)
    SelectedFields: list[ReportDefSelectedField] = Field(default_factory=list)
    FilterConditions: list[ReportDefNode] = Field(default_factory=list)
    SortBy: list[ReportDefSort] = Field(default_factory=list)
    MaxRows: int = Field(default=10000, ge=1, le=100_000)
    OutputFormat: str = "pdf"


class ReportDefinitionUpsert(BaseModel):
    """创建/更新定义的请求体。"""

    project_id: uuid.UUID | None = None
    name: str = Field(max_length=200)
    category: str = Field(max_length=32)
    description: str = ""
    output_format: str = "pdf"
    definition_json: ReportDefinitionBody
    shared_with: str = "CREATOR_ONLY"
    max_rows: int = Field(default=10000, ge=1, le=100_000)


class ReportDefinitionOut(BaseModel):
    def_id: uuid.UUID
    project_id: uuid.UUID | None
    name: str
    category: str
    description: str
    definition_json: ReportDefinitionBody
    output_format: str
    max_rows: int
    version: str
    status: str
    shared_with: str
    created_by: uuid.UUID | None
    created_at: dt.datetime | None = None
    updated_at: dt.datetime | None = None


class ReportDefinitionList(BaseModel):
    items: list[ReportDefinitionOut]
    total: int


__all__ += ["ReportDefSource", "ReportDefSelectedField", "ReportDefCondition",
           "ReportDefFilterGroup", "ReportDefNode", "ReportDefSort",
           "ReportDefinitionBody", "ReportDefinitionUpsert",
           "ReportDefinitionOut", "ReportDefinitionList"]
