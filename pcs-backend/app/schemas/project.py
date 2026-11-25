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

from app.models.enums import ProductCategory, ProjectStatus, UnitSystem


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
    # ⚠️ **默认显示单位制**（P10-K · W-2b）—— 前端 BEDD 页的单位制下拉
    # **默认取项目值** ⇒ ⇒ ⇒ 所以必须暴露 ⇒ ⇒ ⇒ 它是**显示**单位制，
    # **不是**存储单位（存储恒为 canonical/SI）。
    unit_system: UnitSystem
    # ⚠️ **项目两态**（P10-K · W-2c）—— `DRAFT` = 向导没走完
    # ⇒ ⇒ ⇒ ⚠️ **今天没有任何守卫读它** ⇒ ⇒ ⇒ 它只是**标签**。
    status: ProjectStatus


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


class UnitSystemUpdate(BaseModel):
    """设置项目**默认显示单位制**的请求体（P10-K · W-2b）。

    ⚠️ **它不是「把库里的值换算一遍」** —— 存储**恒为 canonical（SI）**
    ⇒ ⇒ ⇒ 本字段只决定「**这个项目默认按哪套单位显示**」⇒ ⇒ ⇒
    ⇒ ⇒ ⇒ 改它**不动任何已存的值**。
    """

    unit_system: UnitSystem = Field(
        ..., description="默认显示单位制 (SI/US)"
    )


class ProjectStatusUpdate(BaseModel):
    """设置项目**状态**的请求体（P10-K · W-2d）。

    ⚠️ **只允许 `DRAFT → ACTIVE`**（单向）⇒ ⇒ ⇒ 没有「DRAFT → 取消/删除」
    ⇒ ⇒ ⇒ 弃单项目**可被识别、可被清理**（运维只需 `status='DRAFT'` 一句）
    ⇒ ⇒ ⇒ 端点对**已经是 ACTIVE** 的项目 ⇒ ⇒ ⇒ **409**（不是 200 空转）
    ⇒ ⇒ ⇒ 因为「已激活」再激活一次 = 用户以为没生效、其实生效了 ⇒ ⇒ ⇒
    ⇒ ⇒ ⇒ 静默 200 会让人**以为失败**。
    """

    status: ProjectStatus = Field(..., description="目标状态 (DRAFT/ACTIVE)")


class ProjectCreate(BaseModel):
    """建项目的请求体（P9B-2 · T-1）。

    ## 为什么只收这 8 个必填字段

    它们是 `app/models/project.py::Project` 里**类型非 Optional**（⇒ NOT NULL）
    且**没有模型默认**的列：`project_no` · `project_name` · `owner_company` ·
    `location` · `project_type` · `design_phase` · `unit_system` ·
    `workspace_id`。

    ⚠️ `status` / `product_category` **有模型默认**（`ACTIVE` / `OTHER`）
    ⇒ **有默认、可省略**：客户端**可以**显式传（显式优先），不传则用服务端
    默认（两者词表一致，显式传不会引入新值）。
    ⇒ `project_id` **不暴露**（服务端生成）。

    ⚠️ `workspace_id` 是 FK ⇒ 必须先有工作区；不存在 ⇒ **404**（不建孤儿项目）；
    且必须是 **FORMAL** 工作区（评审 #4）⇒ PERSONAL/TEMPORARY ⇒
    **422** `WORKSPACE_NOT_FORMAL`（非 FORMAL 项目永远送不了审）。
    """

    project_no: str = Field(
        min_length=1, max_length=50, description="项目编号（全局唯一）"
    )
    project_name: str = Field(min_length=1, max_length=200, description="项目名")
    owner_company: str = Field(min_length=1, max_length=200, description="业主")
    location: str = Field(min_length=1, max_length=500, description="所在地")
    project_type: str = Field(min_length=1, max_length=30, description="项目类型")
    design_phase: str = Field(min_length=1, max_length=30, description="设计阶段")
    unit_system: UnitSystem = Field(
        description=(
            "默认**显示**单位制 (SI/US) —— 存储恒为 canonical(SI)，本字段只决定显示"
        )
    )
    workspace_id: uuid.UUID = Field(description="所属 FORMAL 工作区（必须已存在）")
    status: ProjectStatus = Field(
        default=ProjectStatus.ACTIVE,
        description=(
            "项目两态 (DRAFT/ACTIVE) —— ⚠️ 向导第 1 步显式传 DRAFT"
            "（DRAFT 只是「没走完」的标签，不改变任何行为）"
        ),
    )
    product_category: ProductCategory = Field(
        default=ProductCategory.OTHER,
        description="产品类别（GB 30251-2024 §6.1.5 电折标口径判据）",
    )
