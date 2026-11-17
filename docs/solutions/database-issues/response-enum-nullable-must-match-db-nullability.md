---
module: pcs-backend 响应 schema（app/schemas/stream.py）
date: 2026-11-17
problem_type: database_issue
component: api_contract / database
severity: high
symptoms:
  - "`GET /api/v1/projects/{id}/streams` 整个端点 **500**：`ResponseValidationError`（枚举校验失败）"
  - "只有**某些行**会炸（老行 / P3.2 SIM-10 之前建的行）⇒ 新建的数据看着一切正常"
  - "同一个字段：DB 可空、响应必填 ⇒ 读得到 null 却写不回去（GET→POST 回写 422）"
root_cause: response_schema_narrower_than_db_column
resolution_type: test_and_source_fix
framework_version: FastAPI / SQLAlchemy 2.0 / Pydantic 2.13
related_components:
  - api_contract
  - database
  - openapi
tags:
  - contract-drift
  - nullable
  - enum
  - response-validation
---

# 响应的可空性必须与 DB 列**一致** —— 窄声明就是 500

## 1. 现象：整个列表端点 500

`GET /api/v1/projects/{id}/streams` 返回 500，错误是
`ResponseValidationError`（枚举 `StreamCaseType` 校验失败）。

## 2. 根因：DB 可空，响应必填

DB 列 `streams.case_type` 是 **`Mapped[str | None]`**（可空）⇒ ⇒ 而
P3.2 SIM-10 **之前**建的物流、以及手建没填工况的物流都是 **NULL** ⇒ ⇒
响应 schema 却要求 `StreamCaseType`（非空枚举）⇒ ⇒ FastAPI 序列化时
**逐行校验** ⇒ ⇒ 遇到第一行 NULL 就 **整个端点 500**。

⚠️ **症状离病因很远**：新建的数据看着一切正常 ⇒ ⇒ 「这个端点坏了」的
直觉指向**写入路径**，而病因在**读取路径的契约**上。

## 3. 形状（可复用）

> **响应字段的可空性必须从 DB 列推出来**，不是从「业务上应该必填」推出来。
> 窄声明 ⇒ 500；宽声明（可空）⇒ 最多是「少一个值」。

⇒ `StreamResponse` 覆写 `case_type: StreamCaseType | None = Field(None, …)`
（bug-2167）⇒ ⇒ 契约与 DB 对齐。

⚠️ **旁证**：轻量子集 `StreamListItem.case_type` **本来就是可空的** ⇒ ⇒
同一份数据，两个响应形状不一致 ⇒ ⇒ 那个「更严」的那个就是 500 的来源。

## 4. 连带的第二条：**读写对称**

响应可空而请求必填 ⇒ ⇒ 「**拿响应当入参**」的客户端（GET → POST 回写）
读到 null 就 **422** ⇒ ⇒ 契约上「能读出来的写不回去」。

⇒ ⇒ 请求侧也允许省略（`StreamBase.case_type` ⇒ Optional，省略 ⇒ 落库 NULL）
⇒ ⇒ 读写对称（评审 #26）。

⚠️ **注意契约的实际形状**：建物流的请求体在 OpenAPI 里是**裸 dict**
（`payload: additionalProperties`）⇒ ⇒ 这一处改动**不动**契约快照 ⇒ ⇒
别以为「改了 schema 就会有契约漂移」——**先看契约里它长什么样**。

## 5. 怎么发现这类问题

⇒ 对每个响应字段，**逐一对照 ORM 的 `Mapped[...]`** ⇒ ⇒
`Mapped[str | None]` 但响应写着 `str`/`SomeEnum`（非 Optional）⇒ ⇒ 就是缺陷。

⇒ 与
`docs/solutions/testing-issues/narrow-declaration-is-not-a-constraint.md`
同族：**窄声明不是约束，是事故**。
