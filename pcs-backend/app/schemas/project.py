"""项目产品类别 schema (GB 30251-2024 §6.1.5 电折标口径判据).

用户裁决 2026-10-05「按 project 产品类型强制」落地配套: product_category
原先只能在 DB/seed 层设置 (PCS 长期没有 Project create API), 真实项目运维
成本高。本 schema 让它可经 API 设置与查询。

只覆盖 product_category 相关字段, **不做完整 Project CRUD** (超出本次范围)。
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
