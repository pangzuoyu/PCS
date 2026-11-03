"""批量「提交校对」的请求/响应契约（P9B-3b · D1~D6）。

⚠️ **具名 schema**（不是裸 dict）⇒ 前端类型可契约派生，且
`check_openapi_payload_coverage.py` 的裸载荷数**不涨**。
"""

from __future__ import annotations

import uuid
from typing import Literal

from pydantic import BaseModel, Field

#: 批次 id 列表的**硬上限**（请求体层面）。
#:
#: ⚠️ **为什么需要**：系统参数里的上限是**动态**的（管理员可改）⇒
#: 请求体本身**没有**上界 ⇒ 客户端可以 POST 100 万个 id ⇒
#: 服务端先把这一百万个 UUID **反序列化**（内存 + CPU）**再**去比上限
#: ⇒ 一次请求就能吃掉大量资源。
#:
#: ⇒ 这里给一个**宽松的硬上限**做兜底 ⇒ Pydantic 在**逐个追加元素时**
#: 就会停下 ⇒ 连反序列化都省了。
#:
#: ⚠️ **不取代**动态上限：真正的批次上限仍取
#: `system_settings.stream.batch_submit_limit`（默认 100），
#: 且**两者取小**（见 `stream_batch_service._batch_limit`）。
MAX_STREAM_IDS_PER_BATCH = 1000


class StreamBatchSubmitRequest(BaseModel):
    """批量提交校对的请求体。"""

    stream_ids: list[uuid.UUID] = Field(
        min_length=1,
        max_length=MAX_STREAM_IDS_PER_BATCH,
        description=(
            "待提交校对的物流 id 列表（批次内**去重**；上限取系统参数 "
            "`stream.batch_submit_limit`，默认 100；"
            f"请求体另有硬上限 {MAX_STREAM_IDS_PER_BATCH} 条做兜底）"
        ),
    )
    dry_run: bool = Field(
        default=False,
        description="true ⇒ **只校验**：不改状态、不写审计（含批次那条）",
    )


class BatchSucceededItem(BaseModel):
    """一条成功的物流。

    ⚠️ `status` 是**判别字段**（discriminator）—— 成功与失败是**两个类型**的
    union ⇒ 前端与调用方都靠 `status` 分流，不必靠「在哪个数组里」判断
    （委员会 2026-11-03 · D5 裁决）。
    """

    status: Literal["succeeded"] = Field(description="判别字段：恒为 succeeded")
    stream_id: uuid.UUID
    from_status: str = Field(description="转移前的状态")
    to_status: str = Field(description="转移后的状态")
    note: str | None = Field(
        default=None,
        description="幂等命中标记：已 IN_APPROVAL 时为 `already_in_approval`",
    )


class BatchFailedItem(BaseModel):
    """一条失败的物流。"""

    status: Literal["failed"] = Field(description="判别字段：恒为 failed")
    stream_id: uuid.UUID
    reason: str = Field(
        description=(
            "具名错误码（如 `SIM_STREAM_COMPOSITION_OUT_OF_RANGE` / "
            "`SIM_STREAM_INVALID_TRANSITION` / `SIM_STREAM_NOT_FOUND` / "
            "`INTERNAL_ERROR`）"
        )
    )
    detail: str | None = Field(default=None, description="人类可读的失败原因")


class StreamBatchSubmitResponse(BaseModel):
    """207 Multi-Status 的批次结果。"""

    batch_id: uuid.UUID = Field(description="批次 id（同时是批次审计的 resource_id）")
    total: int = Field(description="**去重后**实际处理的条数")
    # ⚠️ **必填**（不是 `default_factory=list`）—— 有 default ⇒ OpenAPI 标成
    #   **非必填** ⇒ 前端契约派生的类型变成可选 ⇒ 页面里 `result.succeeded.length`
    #   报 TS18048 ⇒ 逼每个调用方判空。而 service **总是**给这两个数组
    #   （空批次也是 `[]`）⇒ 必填才是如实的契约。
    succeeded: list[BatchSucceededItem]
    failed: list[BatchFailedItem]
    dry_run: bool = Field(default=False, description="true ⇒ 本次是预演")
    warning: str | None = Field(
        default=None,
        description=(
            "**批次级**告警（如「批次记录写入失败」）；条目级问题在 `failed` 里"
        ),
    )
