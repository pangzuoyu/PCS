"""并发令牌自检（ADR-0048 §⑥ 的残留风险，ARQ cron）。

## 为什么要有这条

「提交了但没 finalize」的行会**永久**停在 `record_hash = ""` ⇒ 退化阶梯
（§⑥）只能落到 `no_baseline` ⇒ **那一行没有并发保护**。

而症状是**静默**的：编辑照常成功、接口不报错，只是「别人改了我不知道」
这件事永远检测不到。与本仓已修的「守门没跑却看着是绿的」同形状。

⇒ 每日扫一次；发现空 hash 就记 **ERROR** 日志（不是 warning —— 它意味着
并发保护在一个真实缺口上失效）。

⚠️ 本任务**只告警不修**：自动回填 hash 会掩盖「哪条写入路径漏了 finalize」
这个真正的根因（漏 finalize 的路径才是要修的东西）。
"""
from __future__ import annotations

from app.services.edit_guard import scan_missing_record_hash


async def scan_empty_record_hash(ctx: dict) -> dict[str, int]:
    """扫出 record_hash 为空的行。返回 {表名: 行数}。

    ⚠️ 无人可扫（全是 0）是一种状态，不是一次失败 ⇒ 不抛。
    """
    factory = ctx["session_factory"]
    async with factory() as session:
        return await scan_missing_record_hash(session)


__all__ = ["scan_empty_record_hash"]
