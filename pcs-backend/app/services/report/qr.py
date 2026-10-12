"""二维码内容组装 —— SPEC §3.2.1(3)。

指向 `/api/v1/report/verify/{report_id}`，扫描后由系统与 DB 中的原始哈希
比对（用户 2026-10-09 裁决：「比对」的主语是**系统**不是用户 ——
现场扫码的人手里没有原始文件，比对必须是服务端做的事）。

## ⚠️ 载荷必须**确定性** —— 这是内容哈希复用的根

载荷会被**画进 PDF**。若载荷含 `datetime.now()`，同一份内容两次生成的
PDF 字节就不同 → 内容哈希不同 → `report_files` 永远新增行、磁盘永远多一份
完全相同的文件。而且失效得很隐蔽：哈希机制照常工作，只是**永远命中不了**。

计划原本在载荷里放 `generated_at`，已移除 —— 生成时间在
`report_files.created_at` 与审计里，不需要在二维码里再存一份，
二维码的职责是「让现场扫码的人拿到可核验的凭据」，不是「记录何时生成」。

摘要用**排序后**的 record_hashes：同批记录换个顺序仍是同一份报表。
"""
from __future__ import annotations

import hashlib
import json


def build_qr_payload(*, report_id: str, doc_no: str, rev: str,
                     version_purpose: str, record_hashes: list[str],
                     verify_base_url: str) -> str:
    """组装二维码文本载荷。

    `record_hashes` 为空也能生成（摘要 = sha256('')），但那意味着没有可比对的
    凭据 —— 调用方（`report_service`）应在此时**不加二维码**，而不是加一个
    恒定摘要的空壳。
    """
    body = "|".join(sorted(record_hashes))
    digest = hashlib.sha256(body.encode("utf-8")).hexdigest()
    meta = {
        "report_id": report_id,
        "doc_no": doc_no,
        "rev": rev,
        "version_purpose": version_purpose,
        "record_hash_digest": digest,
    }
    return (f"{verify_base_url.rstrip('/')}/api/v1/report/verify/{report_id}#"
            + json.dumps(meta, ensure_ascii=False, separators=(",", ":"),
                         sort_keys=True))