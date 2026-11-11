"""血缘守卫的记录类型注册表（**派生**，不手抄）—— P9B-4 T0-D（TODO-136）。

## 为什么单独一个模块

`app/api/v1/lineage.py` 需要这张表，而表的内容**派生自**
`app/services/calc_lineage.py::RECORD_TYPE_REGISTRY` ⇒ 后者 `import` 了
`app/services/lineage.py` ⇒ 直接在 api 层 import 会**循环导入**
⇒ 放服务层（本模块 import `calc_lineage`，`calc_lineage` 不 import 本模块）。

## 键口径（踩过的坑）

写入方 `LineageTracker.track` 写的是 **`record.__class__.__name__`**（**类名**）：

```python
entry = DataLineage(record_type=record.__class__.__name__, ...)
```

⇒ 守卫注册表的键**必须**是**同一个值**才匹配得上。

⚠️ `RECORD_TYPE_REGISTRY` 的键有 **5 个不是类名**（实测 2026-11-10）：
`cv_result` / `restriction_result` / `flare_system_result` /
`cooling_tower_result` / `psychro_result` ⇒ **派生时一律用 `model.__name__`**，
不抄 registry 的键（否则这 5 个类型的血缘行**永远查不到** ⇒ 等于没守卫）。

## `streams` 为什么单独登记

物流在血缘行里**从不作为 `record_type`** 存在（它是 `source_ref_type='Stream'`
的**源引用**）⇒ 不在派生集合里 ⇒ 但它是前端唯一的查询入口
（`GET /lineage/streams/{id}/graph`）⇒ **单独登记**。
"""

from __future__ import annotations

from sqlalchemy import inspect as _inspect

import app.models  # noqa: F401  —— 导入即注册全部表（`inspect` 需要 mapper 就绪）
from app.models.project import Stream
from app.services.calc_lineage import RECORD_TYPE_REGISTRY

__all__ = ["LINEAGE_GUARDED_RECORD_TYPES"]


def _pk_col(model: type) -> str:
    """模型的主键列名（`inspect(model).primary_key[0].name`）。"""
    return _inspect(model).primary_key[0].name


#: 需要项目守卫的记录类型 → (ORM 模型, 主键列名)。
#:
#: ⚠️ **键 = `model.__name__`**（类名）—— 与写入方写进 `data_lineage.record_type`
#: 的值**逐字相同** ⇒ 匹配得上。
#:
#: ⚠️ **只有带 `project_id` 的模型才能登记** ⇒ 登记一个没有项目归属的模型
#: ⇒ 守卫拿不到项目 ⇒ `record.project_id` 会炸（fail-loud，而不是静默放行）。
#: ⇒ `TwoPhaseResult`（无 `project_id`）**不登记** ⇒ 端点对它 404
#: ⇒ 明确「该类型不提供血缘查询」（TODO-138）。
LINEAGE_GUARDED_RECORD_TYPES: dict[str, tuple[type, str]] = {
    model.__name__: (model, _pk_col(model))
    for model in RECORD_TYPE_REGISTRY.values()
    if hasattr(model, "project_id")
}

#: ⚠️ `streams` 是**入口专用键**（前端查 `/lineage/streams/{id}/graph`），
#: 但物流在血缘行里**从不作为 `record_type`**（它是 `source_ref_type='Stream'`）
#: ⇒ 不在上面的派生集合里 ⇒ **单独登记**。
LINEAGE_GUARDED_RECORD_TYPES["streams"] = (Stream, "stream_id")
