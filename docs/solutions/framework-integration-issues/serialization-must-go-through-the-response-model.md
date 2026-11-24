---
module: pcs-backend 报表定义（app/api/v1/report_builder.py）
date: 2026-11-24
problem_type: framework_integration_issue
component: backend
severity: medium
symptoms:
  - "ORM 加了三列、OpenAPI 里也有 ⇒ ⇒ ⇒ **响应里却没有那三列** ⇒ ⇒ ⇒ 不报错"
  - "前端判据 `rejected_at != null` **永远为假** ⇒ ⇒ ⇒ 「被退回」badge **永远不亮**"
  - "后端单测全绿（只断 200）· 前端单测全绿（fixture 里带着那三列）⇒ ⇒ ⇒ **没人看见**"
root_cause: response_bypasses_the_declared_response_model
resolution_type: source_fix
framework_version: FastAPI / SQLAlchemy 2 / Pydantic v2
related_components:
  - backend
  - frontend
  - openapi
tags:
  - silent-drift
  - serialization
  - response-model
  - false-green
---

# 序列化**必须走声明好的响应模型** —— 否则字段会**静默**少掉

## 1. 现象：契约说有，响应里没有

P10-J · T2 给「报表定义」加「被退回」标记：

```python
# ORM（app/models/report.py）
rejected_at: Mapped[datetime.datetime | None] = ...
rejected_by: Mapped[uuid.UUID | None] = ...
reject_reason: Mapped[str | None] = ...
```

契约（`pcs-backend/docs/openapi.json`）里 `ReportDefinitionOut` 也**确实**多了这三列
⇒ ⇒ ⇒ 契约检查器（`check_openapi_payload_coverage.py`）**绿** ⇒ ⇒ ⇒
前端 `api.d.ts` 也**确实**重新生成了 ⇒ ⇒ ⇒ 一切看着都对。

**但实际响应里没有那三列** —— 因为序列化**没走 `ReportDefinitionOut`**，
而是端点自己拼了一个 dict：

```python
def _as_dict(row) -> dict:
    return {                       # ← **手写的字段清单**
        "def_id": row.def_id,
        "name": row.name,
        # … 加列的人**不会**记得来这里加一行
    }
```

⇒ ⇒ ⇒ 前端 `rejected_at != null` **永远为假**
⇒ ⇒ ⇒ 「被退回」badge **永远不亮**
⇒ ⇒ ⇒ 而**后端单测全绿**（只断状态码 200）
⇒ ⇒ ⇒ **前端单测也全绿**（fixture 里**手工带着**那三列）
⇒ ⇒ ⇒ ⇒ ⇒ ⇒ **没有任何一道关卡会红**。

## 2. 根因：**响应模型是装饰品**

FastAPI 的 `response_model=` 只在**你把对象交给它**的时候才起作用。
一旦端点返回 `dict`，那条路就**整个绕开**了 Pydantic ⇒ ⇒ ⇒
**schema 与响应之间没有任何机械关卡** ⇒ ⇒ ⇒
「schema 说有」与「响应真的有」**各写一份字段名** ⇒ ⇒ ⇒
两份会漂 ⇒ ⇒ ⇒ **漂的方向是少字段**（不炸 ⇒ ⇒ ⇒ 静默）。

⚠️ **契约检查器看不见它**：那个检查器比的是 **ORM/schema ↔ OpenAPI**，
不是 **OpenAPI ↔ 实际响应体** ⇒ ⇒ ⇒ 这一类漂移**结构性漏检**。

⚠️ **前端 fixture 会把它盖住**：fixture 是**手写**的 ⇒ ⇒ ⇒
它带着那三列 ⇒ ⇒ ⇒ 前端单测测的是「fixture ⇒ 渲染」，
不是「后端响应 ⇒ 渲染」⇒ ⇒ ⇒ 契约与实现之间断了一环，**测试还是绿的**。

## 3. 修法

① **响应体一律走声明好的响应模型**（`response_model=ReportDefinitionOut` +
返回 ORM 对象 ⇒ ⇒ ⇒ Pydantic 按 schema 取字段 ⇒ ⇒ ⇒ ORM 加列**自动**多字段）。
⇒ ⇒ ⇒ **加列的人不需要记得改任何地方** ⇒ ⇒ ⇒ 漂移**不再可能**。

② 若端点必须自己拼 dict（历史包袱）⇒ ⇒ ⇒ **把清单集中到一处**并留注释
写明「**为什么必须显式列**」：

```python
# ⚠️ 手写字段清单 ⇒ ⇒ ⇒ ORM 加列时**必须**来这里加一行
# ⇒ ⇒ ⇒ 否则响应**静默少字段** ⇒ ⇒ ⇒ 前端判据永远为假（bug-2203）
```

③ **断言要断「渲染结果」，不是「字段在不在」**：
   前端用例断「『被退回』badge 出现 / 不出现」⇒ ⇒ ⇒
   少一列会**立刻**表现为「badge 不亮」⇒ ⇒ ⇒
   **测试对契约漂移敏感** ⇒ ⇒ ⇒ 这才是有效的关卡。

④ **fixture 不要比契约「更完整」**：fixture 里**多**写那三列 ⇒ ⇒ ⇒
   恰好把「后端少字段」这件事**藏起来** ⇒ ⇒ ⇒
   宁可 fixture 少写（那样会**红**，红得对）。

## 4. 判别句（下次遇到「加了字段但前端看不见」先问这句）

> **这个响应体是「模型序列化」出来的，还是「手拼 dict」出来的？**
>
> 手拼 ⇒ ⇒ ⇒ **契约里多出来的字段，响应里不一定有**
> ⇒ ⇒ ⇒ 而且**不会有任何报错**
> ⇒ ⇒ ⇒ 唯一的发现方式是**端到端看渲染结果**。

⚠️ 相关：[`docs/solutions/frontend-issues/`] 里的
「断言必须对它**命名的那个缺陷**敏感」——
「断字段在不在」是**弱断言**（「断渲染结果」才是敏感断言）。

## 5. 关联

- bug-2203（`.wolf/buglog.json`）—— 本文的实例
- `pcs-backend/app/api/v1/report_builder.py::_as_dict`
- `pcs-backend/app/schemas/report_builder.py::ReportDefinitionOut`
