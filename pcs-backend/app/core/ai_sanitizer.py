"""AI 请求的**递归脱敏** + 规范化哈希（P10-A · Task T6）。

## 为什么

SPEC §2.5「**数据脱敏强制**：发送给 LLM 的文本必须经过脱敏处理」——
AI 请求体里可能带设备位号、项目编号、邮箱、手机号 ⇒ 这些**不应**离开内网。

## 脱敏哪几类

| 类 | 占位符 | 来源 |
|---|---|---|
| 设备位号 | `[EQUIPMENT_TAG]` | SPEC §3.2.1(3) |
| 项目编号 | `[PROJECT_NO]` | SPEC §3.2.1(3) |
| 管线号 | `[LINE_NO]` | SPEC §3.2.1(3) |
| 邮箱 | `[EMAIL]` | 本批追加 |
| 手机号 | `[PHONE]` | 本批追加 |
| 中文人名 | `[PERSON_NAME]` | 本批追加，**默认关** |

⚠️ **LINE_NO 必须排在 EQUIPMENT_TAG 前面** —— 后者的字母/数字范围
（`[A-Z]{2,4}-\\d{3,5}`）**完全包含**前者（`[A-Z]{2}-\\d{3}`）⇒
按 SPEC 原顺序匹配时 `[LINE_NO]` 永远不会出现（一条死规则）。
⇒ 调换顺序后：「AB-123」→ 管线号；「ABCD-1234」→ 设备位号（`\\b` 边界
保证不会把 "ABCD-1234" 里的 "CD-123" 误判成管线号）。

## 人名遮蔽**默认关**

开了会把几乎每个中文词都遮掉 ⇒ 脱敏后的文本基本不可读。
⇒ 用**标签锚定**的启发式（只在「姓名：」「负责人：」这类标签之后遮蔽）
而不是「所有 2~4 字中文词」⇒ 不会误伤普通词。
⇒ 开关是**运行时全局状态**（`enable_person_name_mask`），由 env
`AI_MASK_PERSON_NAME` 接线（见 `app/main.py`）。
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any

#: 结构化脱敏规则（顺序即优先级，见模块 docstring 的 LINE_NO 说明）。
SENSITIVE_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\b[A-Z]{2}-\d{3}\b"), "[LINE_NO]"),
    (re.compile(r"\b[A-Z]{2,4}-\d{3,5}[A-Z]?\b"), "[EQUIPMENT_TAG]"),
    (re.compile(r"\b\d{4}\.\d{3}\.\d{3}\b"), "[PROJECT_NO]"),
    (re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"), "[EMAIL]"),
    (re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)"), "[PHONE]"),
)

#: 人名遮蔽：**标签锚定**（不在标签后的中文串一律不遮）。
#: ⚠️ 用捕获组而不是 lookbehind —— Python 的 lookbehind 要求**固定宽度**，
#: 而这里的标签长度不一。
_PERSON_NAME_PATTERN = re.compile(
    r"((?:姓名|负责人|联系人|工程师|经办人|审核人|编制人|设计人)\s*[:：]\s*)"
    r"([一-龥]{2,4})"
)

#: **运行时开关**（默认关）。
_PERSON_NAME_MASK_ENABLED = False


def enable_person_name_mask(enabled: bool) -> None:
    """打开/关闭中文人名遮蔽（**全局状态**，调用方负责复位）。

    ⚠️ 这是**进程级**状态 ⇒ 单测里必须自己复位（`finally`），
    否则会污染同进程的后续用例。
    """
    global _PERSON_NAME_MASK_ENABLED
    _PERSON_NAME_MASK_ENABLED = bool(enabled)


def _sanitize_text(text: str) -> str:
    """对**单个字符串**脱敏。"""
    for pattern, replacement in SENSITIVE_PATTERNS:
        text = pattern.sub(replacement, text)
    if _PERSON_NAME_MASK_ENABLED:
        text = _PERSON_NAME_PATTERN.sub(r"\1[PERSON_NAME]", text)
    return text


def sanitize_for_ai(value: Any) -> Any:
    """递归脱敏任意结构（dict / list / tuple / str）。

    - 字符串 ⇒ 逐条规则替换
    - dict / list / tuple ⇒ **递归**处理其元素（键也处理）
    - 其余类型（数字 / 布尔 / None）⇒ **原样返回**
    """
    if isinstance(value, str):
        return _sanitize_text(value)
    if isinstance(value, dict):
        return {
            _sanitize_text(key) if isinstance(key, str) else key: sanitize_for_ai(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [sanitize_for_ai(item) for item in value]
    if isinstance(value, tuple):
        return tuple(sanitize_for_ai(item) for item in value)
    return value


def hash_sanitized(body: bytes) -> str:
    """对请求体算**规范化**哈希 ⇒ `"sha256:<hex>"`。

    ⚠️ **规范化**（JSON ⇒ `sort_keys=True` + `ensure_ascii=False` 再序列化）：
    同一个请求**键序不同**也要算出同一个哈希 —— 否则一次调用重试会得到
    两个哈希 ⇒ 审计表里「同一次调用」对不上。
    ⚠️ 非 JSON ⇒ hash **原始 bytes**（不记录内容）。
    """
    try:
        parsed = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        parsed = None
        canonical = body
    else:
        canonical = json.dumps(
            parsed, sort_keys=True, ensure_ascii=False, separators=(",", ":")
        ).encode("utf-8")
    return "sha256:" + hashlib.sha256(canonical).hexdigest()
