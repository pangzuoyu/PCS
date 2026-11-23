#!/usr/bin/env python3
"""TODOS.md 瘦身 —— 把**已关闭**的条目搬进归档文件，正文只留**还开着**的。

## 为什么要有这个脚本

`TODOS.md` 长到 **5653 行 / 210 KB** ⇒ ⇒ 「越堆越长、越不敢看」
⇒ ⇒ 而其中 **~55%** 是**已经关闭**的条目（正文里还带着完整的取证过程、
裁决叙事、变异自证记录）⇒ ⇒ 它们**不再需要被逐字读**⇒ ⇒ 只要**编号可追溯**。

## 判定口径（保守）

一条目被搬进归档，必须满足**其一**：

1. **标题**里有关闭标记（`✅` / `已关闭` / `已裁决并落地` / `已闭环` / `已修（` / `已闭：`）；
2. **紧跟标题的状态行**以 `✅` 开头（本仓 2026-11-23 起加的那种一行状态）；
3. 条目正文里**只有一个**关闭小节 ⇒ ⇒ 整条已闭合。

⚠️ **第 3 条有两个例外**（脚本里显式列出）：
- `TODO-143` ⇒ ⇒ 只闭了**子项 3**（两个缺索引仍在）⇒ ⇒ **留正文**
- `TODO-192` ⇒ ⇒ #9 仍 `⏸ 独立批` ⇒ ⇒ **留正文**

⚠️ **带 `↪️` 的（转批）不算关闭** ⇒ ⇒ 那类条目**仍在账上**（只是归属变了）。

## 产物

- `docs/archives/TODOS-closed.md` —— 归档正文（**逐字保留**）+ 索引表
- `TODOS.md` —— 只留**还开着**的条目 + 文末的「已关闭」索引表（编号可追溯）

## 用法

```bash
python3 scripts/slim_todos.py            # 干跑（只打印统计）
python3 scripts/slim_todos.py --write    # 真写
```
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "TODOS.md"
ARCHIVE = ROOT / "docs" / "archives" / "TODOS-closed.md"

#: **只闭了子项 / 仍有未完项**的条目 ⇒ ⇒ 不搬（正文里还写着「还剩什么」）
KEEP_OPEN = {"TODO-143", "TODO-192"}

CLOSE_RE = re.compile(r"(✅|已关闭|已裁决并落地|已裁决 · 关闭|已闭环|已修（|已闭：)")
ENTRY_RE = re.compile(r"^#{2,3} (TODO-|bug-|✅)")
#: ⚠️ **必须带字母后缀**（`TODO-197b` / `TODO-187b`）—— 否则 `TODO-197b`
#: 会被**截成** `TODO-197` ⇒ ⇒ 索引表里两条不同条目**编号相同**
#: ⇒ ⇒ 「编号是追溯索引」这句话就废了（2026-11-23 发现）。
NUM_RE = re.compile(r"(TODO-\d+[a-z]?|bug-\d+[a-z]?)")
DATE_RE = re.compile(r"20\d\d-\d\d-\d\d")


def level(line: str) -> int:
    return len(line) - len(line.lstrip("#"))


#: **工具自己生成的**「已关闭」段标题 ⇒ ⇒ 跳过它（否则工具**不幂等**：
#: 第二次跑 ⇒ ⇒ 把它当成一条「已关闭条目」⇒ ⇒ 搬进归档 ⇒ ⇒ 文件结构被搞乱）。
GENERATED_SECTION_HEADS = ("✅ 已关闭（",)


def is_entry(line: str) -> bool:
    """这是不是「一条待办」（而不是分组标题）。"""
    if any(mark in line for mark in GENERATED_SECTION_HEADS):
        return False
    return bool(ENTRY_RE.match(line))


def extent(lines: list[str], heads: list[int], i: int) -> int:
    """本条目到下一个**同级或更高级**标题为止。"""
    lvl = level(lines[i])
    for j in heads:
        if j > i and level(lines[j]) <= lvl:
            return j
    return len(lines)


def is_closed(lines: list[str], heads: list[int], i: int) -> bool:
    head = lines[i]
    end = extent(lines, heads, i)
    subs = [lines[j] for j in heads if i < j < end]

    if level(head) <= 2:
        # ⚠️ **正文里还有「⏸」标记** ⇒ ⇒ 那些子项**仍在账上** ⇒ ⇒ 整条**不搬**
        body = "\n".join(lines[i:end])
        if "⏸" in body:
            return False
        # ⚠️ **条目自己写了「本条关闭 / 本条不关闭」** ⇒ ⇒ 以**最后一句**为准
        # （P10-H 那批条目在正文深处写了「✅ 已落地 ⇒ ⇒ 本条关闭」）
        closes = [m.start() for m in re.finditer(r"本条\*{0,2}关闭", body)]
        keeps = [m.start() for m in re.finditer(r"本条\*{0,2}不关闭", body)]
        if closes or keeps:
            return (max(closes) if closes else -1) > (max(keeps) if keeps else -1)
        if CLOSE_RE.search(head):
            return True
        # 紧跟标题的状态行（本仓 2026-11-23 起加的一行裁决）
        for j in range(i + 1, min(end, i + 4)):
            text = lines[j].strip()
            if not text:
                continue
            if text.startswith("↪️"):  # 转批 ⇒ ⇒ 仍在账上
                return False
            if text.startswith("✅"):
                return True
            break
        # 正文里只有一个关闭小节 ⇒ ⇒ 整条已闭合
        if not any(n in head for n in KEEP_OPEN):
            closed = [s for s in subs if CLOSE_RE.search(s)]
            if closed and len(closed) == len(subs):
                return True
        return False

    return bool(CLOSE_RE.search(head))


def strip_generated_blocks(lines: list[str]) -> list[str]:
    """剥掉**上一次生成的**两个索引块 ⇒ ⇒ 让本工具**幂等**。

    ⚠️⚠️ **2026-11-23 修**：本工具原先只**插入**新索引 ⇒ ⇒ 第二次跑
    ⇒ ⇒ 文件里出现**两份**「还开着」索引 ⇒ ⇒ 「哪份是真的」没人知道
    ⇒ ⇒ ⇒ 而且「已关闭」段也在文末**堆了两份**。

    ⇒ ⇒ 两个生成块的标记：
    - 头部：`## 📋 还开着的条目（**一眼看完**）` ⇒ ⇒ 到下一个标题为止
    - 文末：`## ✅ 已关闭（**正文已搬进归档**）` ⇒ ⇒ 到文件末尾
    """
    out: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith("## 📋 还开着的条目"):
            i += 1
            while i < len(lines) and not lines[i].startswith("#"):
                i += 1
            continue
        if line.startswith("## ✅ 已关闭（"):
            break   # 文末整段都是它 ⇒ ⇒ 直接截断
        # ⚠️ **瘦身提示行**（工具自己写的）⇒ ⇒ 也要剥 ⇒ ⇒ 否则每次跑多插一份
        if line.startswith("> **2026-11-23 瘦身**"):
            i += 1
            while i < len(lines) and lines[i].startswith("> ⇒ ⇒ 搬运由"):
                i += 1
            continue
        out.append(line)
        i += 1
    # ⚠️ 去掉尾部残留的「---」与空行 ⇒ ⇒ 否则新写的文末段前面会**多一个分隔线**
    while out and out[-1].strip() in ("", "---"):
        out.pop()
    return out


def main() -> None:
    write = "--write" in sys.argv
    lines = SRC.read_text(encoding="utf-8").splitlines()
    # ⚠️ **先剥掉上一次生成的索引块** ⇒ ⇒ 之后的行号/标题索引才对得上
    # ⇒ ⇒ 否则 `heads` 指向的是**剥之前**的行号 ⇒ ⇒ ⇒ IndexError。
    lines = strip_generated_blocks(lines)
    heads = [i for i, l in enumerate(lines) if re.match(r"^#{1,6} ", l)]

    # 每个标题的 **level-2 祖先**（level-3 的裁决小节归到它所属的条目）
    ancestor: dict[int, int] = {}
    last_l2 = -1
    for i in heads:
        if level(lines[i]) <= 2:
            last_l2 = i
        ancestor[i] = last_l2

    archived: list[tuple[int, int]] = []
    archived_starts: set[int] = set()
    for i in heads:
        if not is_entry(lines[i]):
            continue
        if not is_closed(lines, heads, i):
            continue
        archived.append((i, extent(lines, heads, i)))
        archived_starts.add(i)

    # level-3 的条目（老式写法：`## 分类` 下的 `### TODO-xxx`）：
    #   · 祖先是**分组标题**（不是条目）⇒ ⇒ 它自己就是一条 ⇒ ⇒ 单独搬
    #   · 祖先是**条目** ⇒ ⇒ 它是那条目的裁决小节 ⇒ ⇒ 跟着祖先走（不单独搬）
    kept_blocks: list[tuple[int, int]] = []
    for s, e in archived:
        if level(lines[s]) >= 3:
            anc = ancestor.get(s, -1)
            if anc >= 0 and is_entry(lines[anc]):
                continue
        kept_blocks.append((s, e))

    kept: list[str] = []
    archive_blocks: list[str] = []
    index_rows: list[tuple[str, str, str]] = []
    cursor = 0
    for s, e in kept_blocks:
        kept.extend(lines[cursor:s])
        block = lines[s:e]
        archive_blocks.append("\n".join(block).rstrip() + "\n")
        head = block[0]
        num = NUM_RE.search(head)
        if not num and level(head) >= 3:
            anc = ancestor.get(s, -1)
            if anc >= 0:
                num = NUM_RE.search(lines[anc])
        title = re.sub(r"^#{1,6}\s*", "", head)
        title = re.sub(r"^✅\s*DONE\s*——\s*", "", title)
        title = re.sub(r"^✅\s*", "", title)
        if num:
            title = re.sub(rf"^{re.escape(num.group(1))}\s*[::]?\s*", "", title)
        title = re.sub(r"^[+&]\s*(TODO-\d+|bug-\d+)\s*[::]?\s*", "", title)
        title = re.sub(r"\s*[🔴🟡🟠🟢⚪]+\s*$", "", title)  # 去掉尾部严重度标
        date = ""
        for line in block[:6]:
            m = DATE_RE.search(line)
            if m:
                date = m.group(0)
                break
        index_rows.append(
            (num.group(1) if num else "（批次汇总）", title.strip(), date or "—")
        )
        cursor = e
    kept.extend(lines[cursor:])

    # ── 正文顶部的「还开着」索引（一眼看完） ───────────────────────────────
    open_rows: list[tuple[str, str, str]] = []
    for i in heads:
        if not is_entry(lines[i]):
            continue
        if i in {s for s, _ in kept_blocks}:
            continue
        if level(lines[i]) >= 3:
            anc = ancestor.get(i, -1)
            if anc >= 0 and is_entry(lines[anc]):
                continue  # 祖先条目已经代表它了
        head = lines[i]
        num = NUM_RE.search(head)
        sev = ""
        m = re.search(r"[🔴🟡🟠🟢⚪]", head)
        if m:
            sev = m.group(0)
        title = re.sub(r"^#{1,6}\s*", "", head)
        if num:
            title = re.sub(rf"^{re.escape(num.group(1))}\s*[::]?\s*", "", title)
        title = re.sub(r"\s*[🔴🟡🟠🟢⚪]+\s*$", "", title)
        open_rows.append((num.group(1) if num else "—", sev, title.strip()))

    # ── 既有归档（**追加**，不是重建）────────────────────────────────────
    # ⚠️⚠️ **2026-11-23 修**：本工具原先**重建**归档文件 ⇒ ⇒ 第二次跑
    # ⇒ ⇒ 把**已归档的 98 条**抹掉（只剩本次搬的）⇒ ⇒ **数据丢失**。
    # ⇒ ⇒ 现在：**读既有归档** ⇒ ⇒ 索引行合并 + 正文块**追加** ⇒ ⇒ 可复跑。
    existing_rows: list[tuple[str, str, str]] = []
    existing_body: list[str] = []
    if ARCHIVE.exists():
        raw = ARCHIVE.read_text(encoding="utf-8").splitlines()
        sep = next((i for i, l in enumerate(raw) if l.strip() == "---"), None)
        head_part = raw[:sep] if sep is not None else raw
        body_part = raw[sep + 1:] if sep is not None else []
        for line in head_part:
            # ⚠️ **标题里可能含 `|`** ⇒ ⇒ 不能用固定三段正则
            # ⇒ ⇒ 按 ` | ` 切 ⇒ ⇒ 首段 = 编号 · 末段 = 日期 · 中间 = 标题
            parts = line.strip().strip("|").split(" | ")
            if len(parts) < 3:
                continue
            num = parts[0].strip().strip("`")
            date = parts[-1].strip()
            title = " | ".join(parts[1:-1]).strip()
            if num in ("编号", "---") or not title:
                continue
            existing_rows.append((num, title, date))
        existing_body = body_part
        # ⚠️ 去掉正文开头的空行 ⇒ ⇒ 否则**每次跑都多插一行**（归档文件逐次膨胀）
        while existing_body and not existing_body[0].strip():
            existing_body.pop(0)

    # ── 归档文件 ──────────────────────────────────────────────────────────
    arch: list[str] = [
        "# TODOS 归档 —— **已关闭**的条目（正文逐字保留）",
        "",
        "> **这是 `TODOS.md` 的归档**（2026-11-23 瘦身时搬出来的）⇒ ⇒ "
        "**正文里只留还开着的条目**。",
        "> ⚠️ **编号是追溯索引** ⇒ ⇒ 任何地方说「见 TODO-xxx」都能在这里找到原文。",
        "> ⇒ ⇒ 新条目请写进 `TODOS.md`；**关闭**时把它搬回这里"
        "（并在 `TODOS.md` 文末的「已关闭」表里加一行）。",
        ">",
        "> ⚠️ **搬动造成的指向变化**：条目正文里若写「详见**本文件末尾**的 X」"
        "⇒ ⇒ 那句话原本指的是 `TODOS.md` ⇒ ⇒ 现在 X 可能留在 `TODOS.md` 里"
        "（例如「F4-PRE 裁决表」）⇒ ⇒ **以 `TODOS.md` 为准**。",
        "",
        "## 索引",
        "",
        "| 编号 | 条目 | 关闭日期 |",
        "|---|---|---|",
    ]
    merged_rows = existing_rows + index_rows
    for num, title, date in merged_rows:
        arch.append(f"| `{num}` | {title} | {date} |")
    arch.append("")
    arch.append("---")
    arch.append("")
    arch.extend(existing_body)
    arch.extend(archive_blocks)

    # ── 正文文末的「已关闭」索引（编号可追溯） ─────────────────────────────
    tail = [
        "",
        "---",
        "",
        "## ✅ 已关闭（**正文已搬进归档**）",
        "",
        f"⚠️ **为什么搬走**：这些条目**已经闭合**（正文里带着完整的取证过程 / 裁决叙事 / "
        f"变异自证）⇒ ⇒ 它们**不再需要被逐字读**⇒ ⇒ 但**编号是追溯索引** ⇒ ⇒ "
        f"原文逐字保留在 **`docs/archives/TODOS-closed.md`**（{len(merged_rows)} 条）。",
        "",
        "| 编号 | 条目 | 关闭日期 |",
        "|---|---|---|",
    ]
    for num, title, date in merged_rows:
        tail.append(f"| `{num}` | {title} | {date} |")
    tail.append("")

    # ── 正文顶部的「还开着」索引 ───────────────────────────────────────────
    head_index = [
        "",
        "## 📋 还开着的条目（**一眼看完**）",
        "",
        f"⚠️ **正文里只有还开着的条目**（{len(open_rows)} 条）⇒ ⇒ "
        f"**已关闭**的 {len(merged_rows)} 条在 `docs/archives/TODOS-closed.md`"
        f"（编号可追溯 ⇒ ⇒ 文末有「已关闭」索引表）。",
        "",
        "| 编号 | 严重度 | 条目 |",
        "|---|---|---|",
    ]
    for num, sev, title in open_rows:
        head_index.append(f"| `{num}` | {sev} | {title} |")
    head_index.append("")

    # 插到「最后全量核销」那行之后（文件头的末尾）
    for pos, line in enumerate(kept):
        if line.startswith("最后全量核销"):
            insert_at = pos + 1
            break
    else:
        insert_at = 0
    note = [
        "",
        "> **2026-11-23 瘦身**：本文件曾到 **5653 行 / 210 KB** ⇒ ⇒ "
        f"**已关闭**的 {len(merged_rows)} 条整体搬进 **`docs/archives/TODOS-closed.md`**"
        "（正文逐字保留 · **编号可追溯**）⇒ ⇒ 本文件只留**还开着**的条目。",
        f"⇒ ⇒ 搬运由 `scripts/slim_todos.py` 完成（可复跑 · 判定口径写在脚本 docstring 里）。",
    ]
    kept = kept[:insert_at] + note + head_index + kept[insert_at:]

    print(f"本次归档条目: {len(index_rows)} 条（累计 {len(merged_rows)} 条）")
    print(f"TODOS.md: {len(lines)} 行 → {len(kept) + len(tail)} 行")
    print(f"归档文件: {sum(e - s for s, e in archived)} 行 → docs/archives/TODOS-closed.md")

    if not write:
        print("（干跑；加 --write 真写）")
        for num, title, date in index_rows:
            print(f"  {num:12s} {date:12s} {title[:70]}")
        return

    ARCHIVE.parent.mkdir(parents=True, exist_ok=True)
    ARCHIVE.write_text("\n".join(arch) + "\n", encoding="utf-8")
    SRC.write_text("\n".join(kept + tail), encoding="utf-8")
    print("已写入")


if __name__ == "__main__":
    main()
