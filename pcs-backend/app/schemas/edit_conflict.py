"""编辑冲突的请求/响应契约（ADR-0048 §⑥ §⑦ · SPEC §6.21 P9A-LCK-005）。

⚠️ **零裸字段**（P9A-DLV-010）：字段必须显式声明。

## 409 响应体的形状

ADR-0048 §⑦ 原文写的是顶层三字段（`error_code` / `message` / `conflict`）。
**本仓的统一错误信封是 `{code, message, detail, trace_id}`**
（`app/core/errors.py::ErrorResponse`，全局异常处理器产出）⇒ 本实现把
冲突对象放进 `detail.conflict`：

```json
{
  "code": "RECORD_EDIT_CONFLICT",
  "message": "该记录已被他人修改，请刷新后重新编辑",
  "detail": {"conflict": {"record_type": "…", "basis": "record_hash", …}},
  "trace_id": "…"
}
```

⇒ ADR-0048 §⑦ 已按此修订（内容不变，**信封**归一）。
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

#: 冲突判定的三条依据（ADR-0048 §⑥ 的阶梯分支）。
ConflictBasis = Literal["record_hash", "updated_at", "no_baseline"]


class ConflictDetail(BaseModel):
    """409 里的 `conflict` 对象（ADR-0048 §⑦）。

    `basis` 三值让前端能区分「别人改了」（刷新有用）与「记录没基线」
    （刷新没用，应联系管理员）。
    """

    record_type: str = Field(..., description=(
        "记录类型：`RECORD_TYPE_REGISTRY` 的键（如 `CostEstResult`）—— 不是表名"
    ))
    record_id: str = Field(..., description="记录 ID")
    your_expected_hash: str | None = Field(
        None, description="客户端带来的基线 hash（16 hex）"
    )
    current_hash: str | None = Field(None, description="库中当前 hash（16 hex）")
    changed_by: str | None = Field(
        None, description="上一次改动者 user_id（取自编辑审计；取不到为 null）"
    )
    changed_at: datetime | None = Field(
        None, description="上一次改动时间（取自编辑审计的 occurred_at）"
    )
    basis: ConflictBasis = Field(..., description="判定依据（三值之一）")


class EditAuditDetail(BaseModel):
    """编辑审计 `detail_json` 的**显式** schema（ADR-0048 §⑦ 强制）。

    ⚠️ 不得是自由 dict —— 409 弹窗的「查看差异」要靠 `changed_fields`。
    ⚠️ `changed_fields` 是**字段名列表**，不是完整值（一次大改版几十 KB，
    完整值进审计表会把它撑爆）。
    """

    changed_fields: list[str] = Field(
        default_factory=list, description="本次改动的字段名列表（不含值）"
    )
    overwrote_stale_baseline: bool = Field(
        False,
        description="本次保存覆盖了无法校验的基线（无并发令牌可比对）",
    )


class EditBaselineMixin(BaseModel):
    """编辑请求的**并发基线**（6 个 PATCH 端点共用）。

    ⚠️ **不带基线的编辑一律 409**（basis=no_baseline）——
    「客户端没告诉服务端它基于哪一版」= 服务端无法判定并发 ⇒ 不得放行。
    这不是可选的严格：放行等于「保护可以不存在」。

    ⚠️ 这两个字段**不是业务字段** ⇒ 调用方必须从业务 payload 里剔除
    （`model_dump(exclude={...})`），否则会被 service 层的字段白名单拒绝。
    """

    expected_hash: str | None = Field(
        None,
        description="客户端看到的 record_hash（16 hex）；必填，否则 409",
    )
    expected_updated_at: datetime | None = Field(
        None,
        description="客户端看到的 updated_at（无 hash 令牌时的第二档基线）",
    )


#: 需要从业务 payload 里剔除的基线字段名。
BASELINE_FIELDS: frozenset[str] = frozenset({"expected_hash", "expected_updated_at"})


__all__ = [
    "BASELINE_FIELDS",
    "ConflictBasis",
    "ConflictDetail",
    "EditAuditDetail",
    "EditBaselineMixin",
]
