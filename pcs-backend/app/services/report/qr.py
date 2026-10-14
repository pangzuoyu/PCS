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

import datetime as dt
import hashlib
import hmac
import json
import uuid

#: 签名有效期（秒）。现场扫码是「人拿着报表走到设备前扫」，
#: 短到够防二维码被截图转发、长到够覆盖排队与对光焦的时间。
VERIFY_TTL_SECONDS = 900


def sign(*, report_file_id: uuid.UUID, exp: int, secret: str) -> str:
    """HMAC-SHA256(`{id}:{exp}`) 的十六进制。

    ## 为什么这一份公式住在 `qr.py` 而不是各写一遍（2026-10-14）

    `/report/verify` 的 `_check_sig` 与这里的签名**必须**是同一个公式。
    分成两处的话，改坏其中一处（换分隔符、少拼一个冒号、忘记 `.hex()`）
    时**两边都看起来完全正常**，症状是「所有二维码扫码一律 403」，
    而排查的人会去看「是不是密钥配错了」。

    这与 bug-172 同族：`builder_service` 与 `report_service` 各有一个同名
    `_fetch_join_rows`，bug-162 只修了其中一个，于是项目隔离只对一个
    调用方成立。有测试钉住 `hmac.new` 在全仓只出现一次。
    """
    return hmac.new(secret.encode(), f"{report_file_id}:{exp}".encode(),
                    hashlib.sha256).hexdigest()


def build_qr_payload(*, report_id: str, doc_no: str, rev: str,
                     version_purpose: str, record_hashes: list[str],
                     verify_base_url: str,
                     report_file_id: uuid.UUID, secret: str,
                     ttl_seconds: int = VERIFY_TTL_SECONDS,
                     now: dt.datetime | None = None) -> str:
    """组装二维码文本载荷，**带可验的短时效签名**。

    ⚠️ `record_hashes` **为空也照常生成**（摘要 = sha256('')）。旧版 docstring
    说「为空就不加二维码，因为没有可比对的凭据」—— 那条规则已与实现脱节：
    `/report/verify` 做的是**文件完整性校验**（重算磁盘 sha256 比 `content_hash`），
    从头到尾没读过 `record_hash_digest`；而 `record_hash` 压根没登记进
    datasource_registry，10 类报表的 `record_hashes` 恒为空 ——
    照旧规则执行的结果是二维码**一次都不会出现**。
    让核验成立的是**签名 + report_file_id**，两者恒在。

    ## `now` 为什么是参数

    为了可测：过期判定靠它，直接在函数里 `datetime.now()` 就没法写
    「一个已经过期的签名」这条测试。默认取当前时间。

    ## 载荷里为什么**不含**签名（§载荷必须确定性）

    签名含时间戳，所以它在 **query string**（`?sig=..&exp=..`）里，
    而**不在 fragment 里**。fragment 里的 `meta` 是给人看的凭据，
    它必须与内容哈希一样是确定性的（见模块 docstring）——
    签名每份报表都不同，放进去就等于给 PDF 注入随机字节，
    而 `_content_hash` 虽然刻意不哈希渲染后的字节，可一旦将来有人改回
    「哈希渲染结果」，去重就永久失效且**不会报错**。
    """
    now = now or dt.datetime.now(dt.UTC)
    exp = int(now.timestamp()) + ttl_seconds
    sig = sign(report_file_id=report_file_id, exp=exp, secret=secret)

    body = "|".join(sorted(record_hashes))
    digest = hashlib.sha256(body.encode("utf-8")).hexdigest()
    meta = {
        "report_id": report_id,
        "doc_no": doc_no,
        "rev": rev,
        "version_purpose": version_purpose,
        "record_hash_digest": digest,
    }
    return (f"{verify_base_url.rstrip('/')}/api/v1/report/verify/{report_id}"
            f"?sig={sig}&exp={exp}#"
            + json.dumps(meta, ensure_ascii=False, separators=(",", ":"),
                         sort_keys=True))