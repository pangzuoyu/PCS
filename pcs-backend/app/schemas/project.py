"""项目 schema —— product_category 口径判据 + **项目创建**（P9B-2 · T-1）。

用户裁决 2026-10-05「按 project 产品类型强制」落地配套: product_category
原先只能在 DB/seed 层设置 (PCS 长期没有 Project create API), 真实项目运维
成本高。本 schema 让它可经 API 设置与查询。

⚠️ **T-1（P9B-2 · 2026-10-27 用户裁决）补上了 `POST /projects`** ——
没有它, 项目建不出来 ⇒ 签署流程的对象（记录 / 交付物）全都挂在项目下
⇒ P9B-2 交付后签署流程在**真实 UI** 上走不通。

只覆盖 product_category 相关字段 + 建项目的最小字段集, **不做完整 Project CRUD**
（删除 / 列表仍超出范围）。
"""

from __future__ import annotations

import uuid

from pydantic import BaseModel, Field

from app.models.enums import ProductCategory


class ProjectOut(BaseModel):
    """项目只读响应 (product_category 视角的最小字段集)."""

    project_id: uuid.UUID
    project_no: str
    project_name: str
    project_type: str
    product_category: str
    # 派生态: 该项目当前生效的电折标口径 (GB 30251-2024 §6.1.5)
    # 由后端按 product_category 推导后一并返回, 运维不必读代码推断。
    electricity_value_type: str


class ProductCategoryUpdate(BaseModel):
    """设置项目产品类别的请求体."""

    product_category: ProductCategory = Field(
        ...,
        description=(
            "产品类别 (GB 30251-2024 §6.1.5): REFINING (炼油) / ETHYLENE (乙烯) "
            "⇒ 电折标系数用等价值 (0.21 kg标油/kWh); OTHER ⇒ 当量值 "
            "(0.086 kg标油/kWh)"
        ),
    )


class ProjectCreate(BaseModel):
    """建项目的请求体（P9B-2 · T-1）。

    ## 为什么只收这 8 个必填字段

    它们是 `app/models/project.py::Project` 里**类型非 Optional**（⇒ NOT NULL）
    且**没有模型默认**的列：`project_no` · `project_name` · `owner_company` ·
    `location` · `project_type` · `design_phase` · `unit_system` ·
    `workspace_id`。

    ⚠️ `status` / `product_category` **有模型默认**（`ACTIVE` / `OTHER`）
    ⇒ **不由客户端重复指定**（要客户端复述一个默认值只是噪音）。
    ⇒ `project_id` **不暴露**（服务端生成）。

    ⚠️ `workspace_id` 是 FK ⇒ 必须先有工作区；不存在 ⇒ **404**（不建孤儿项目）。
    """

    project_no: str = Field(
        min_length=1, max_length=50, description="项目编号（全局唯一）"
    )
    project_name: str = Field(min_length=1, max_length=200, description="项目名")
    owner_company: str = Field(min_length=1, max_length=200, description="业主")
    location: str = Field(min_length=1, max_length=500, description="所在地")
    project_type: str = Field(min_length=1, max_length=30, description="项目类型")
    design_phase: str = Field(min_length=1, max_length=30, description="设计阶段")
    unit_system: str = Field(min_length=1, max_length=20, description="单位制（SI 等）")
    workspace_id: uuid.UUID = Field(description="所属 FORMAL 工作区（必须已存在）")
    status: str = Field(default="ACTIVE", max_length=20, description="项目状态")
    product_category: ProductCategory = Field(
        default=ProductCategory.OTHER,
        description="产品类别（GB 30251-2024 §6.1.5 电折标口径判据）",
    )
