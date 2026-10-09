"""变异测试的元断言工具（用户 2026-10-09 审查引入）。

## 为什么需要它

变异测试自己也会**假绿**，而且是最阴的一种：变异**根本没应用上**，
于是测试套件原样通过，看起来像「测试抓住了这个变异」，其实什么都没发生。

实际踩过一次：把

    rejected.append(f"{path}（无法解析：{type(e).__name__}）")
    continue

改成 `raise`，因为手写的 `old` 字符串和文件里的实际内容差了一个字符，
`str.replace` 静默返回原串 —— 变异是**空操作**，测试全绿。
若当时没多问一句「变异到底应用上没有」，就会把一条假绿的验证写进提交信息。

**两种失败必须能区分**：
  - 「变异没应用」→ 元断言在这里就该炸（`mutate` 的 `assert old in source`）
  - 「变异应用了但测试没抓到」→ 那是真实缺口，登记 TODOS.md

## 用法

    from tests.mutation import mutate

    src = mutate(Path("app/x.py").read_text(), "OLD", "NEW")
    ...  # 临时写回、跑测试、还原

⚠️ `mutate` **不做替换计数校验**之外的任何事：它只保证 old 存在且至少替换一处。
若 old 在文件里出现多次，`str.replace` 会全换 —— 想只换一处就把上下文一起传进 old。
"""
from __future__ import annotations


def mutate(source: str, old: str, new: str) -> str:
    """替换并**断言目标确实存在**。

    Raises:
        AssertionError: `old` 不在 `source` 里 —— 变异是空操作，后续的绿灯无意义。
    """
    assert old in source, (
        f"变异目标未找到，变异是空操作：{old!r}\n"
        f"文件实际内容可能已变（格式化 / 重构 / 上一轮已改过）。"
        f"不要把「测试仍然全绿」当成「测试抓住了变异」。"
    )
    return source.replace(old, new)


def mutate_count(source: str, old: str, new: str, expected: int = 1) -> str:
    """同 `mutate`，但额外校验替换次数 —— 多处命中时用这个。"""
    assert old in source, f"变异目标未找到：{old!r}"
    actual = source.count(old)
    assert actual == expected, f"目标出现 {actual} 次，期望 {expected} 次：{old!r}"
    return source.replace(old, new)