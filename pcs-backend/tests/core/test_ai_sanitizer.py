"""`app/core/ai_sanitizer.py` 的测试（P10-A · Task T6）。

## 为什么脱敏是强制的

SPEC §2.5「**数据脱敏强制**：发送给 LLM 的文本必须经过脱敏处理」。

## 脱敏哪几类

- **SPEC §3.2.1(3) 的三类**（权威）：设备位号 `[EQUIPMENT_TAG]` ·
  项目编号 `[PROJECT_NO]` · 管线号 `[LINE_NO]`
- **邮箱 / 手机号**（计划的追加项）：`[EMAIL]` · `[PHONE]`

## 人名遮蔽**默认关**

开了会把几乎每个中文词都遮掉 ⇒ 脱敏后的文本基本不可读 ⇒ 默认关，
且由 env `AI_MASK_PERSON_NAME` 显式 opt-in（接线在 `app/main.py`）。

⚠️ 实现是**标签锚定**的启发式（只在「姓名：」「负责人：」这类标签之后遮蔽）
⇒ 不会把普通词当人名。
"""
from __future__ import annotations

import pytest

from app.core.ai_sanitizer import (
    enable_person_name_mask,
    hash_sanitized,
    sanitize_for_ai,
)


def test_sanitize_masks_email_and_phone_in_nested_payload() -> None:
    """嵌套 dict/list 里的邮箱与手机号都被替换（递归）。"""
    payload = {
        "text": "联系 someone@example.com 或 13812345678",
        "items": [{"mail": "a.b@example.org"}, {"tel": "13900001111"}],
    }

    out = sanitize_for_ai(payload)

    assert "someone@example.com" not in str(out)
    assert "13812345678" not in str(out)
    assert "[EMAIL]" in str(out)
    assert "[PHONE]" in str(out)
    # 嵌套层也被处理
    assert "a.b@example.org" not in str(out)


def test_sanitize_leaves_numbers_and_booleans_untouched() -> None:
    """非字符串原样返回。"""
    payload = {"n": 42, "f": 1.5, "b": True, "none": None, "s": "plain text"}

    out = sanitize_for_ai(payload)

    assert out["n"] == 42
    assert out["f"] == 1.5
    assert out["b"] is True
    assert out["none"] is None
    assert out["s"] == "plain text"


def test_sanitize_masks_the_spec_patterns() -> None:
    """SPEC §3.2.1(3) 的三类：设备位号 / 项目编号 / 管线号。

    ⚠️ **LINE_NO 先于 EQUIPMENT_TAG 匹配** —— 否则 `[A-Z]{2}-\\d{3}` 被
    `[A-Z]{2,4}-\\d{3,5}` **完全遮蔽**（后者的字母/数字范围包含前者）
    ⇒ `[LINE_NO]` 永远不会出现。
    """
    text = "位号 ABCD-1234 · 编号 1234.567.890 · 管线 AB-123"

    out = sanitize_for_ai(text)

    assert "[EQUIPMENT_TAG]" in out
    assert "[PROJECT_NO]" in out
    assert "[LINE_NO]" in out


def test_person_name_mask_is_off_by_default() -> None:
    """默认**不**遮中文人名（开了会把几乎每个中文词都遮掉）。"""
    assert "[PERSON_NAME]" not in sanitize_for_ai("姓名：张三")


def test_person_name_mask_can_be_enabled_at_runtime() -> None:
    """enable_person_name_mask(True) ⇒ 遮；再关掉 ⇒ 不遮（**全局状态要能复位**）。"""
    enable_person_name_mask(True)
    try:
        masked = sanitize_for_ai("姓名：张三")
    finally:
        enable_person_name_mask(False)

    assert "[PERSON_NAME]" in masked
    assert sanitize_for_ai("姓名：张三") == "姓名：张三"


def test_hash_sanitized_is_stable_for_equal_bodies() -> None:
    """同一 body 两次 ⇒ 同哈希（规范化：sort_keys + ensure_ascii=False）。

    ⚠️ **键序不同也必须同哈希** —— 否则同一个请求重试会算出两个哈希
    ⇒ 审计表里「同一次调用」对不上。
    """
    a = b'{"b": 2, "a": 1}'
    b = b'{"a": 1, "b": 2}'

    assert hash_sanitized(a) == hash_sanitized(b)
    assert hash_sanitized(a).startswith("sha256:")


def test_hash_sanitized_differs_for_different_bodies() -> None:
    """不同 body ⇒ 不同哈希。"""
    assert hash_sanitized(b'{"a": 1}') != hash_sanitized(b'{"a": 2}')


def test_hash_sanitized_falls_back_to_raw_bytes_on_invalid_json() -> None:
    """非 JSON ⇒ hash 原始 bytes（**不**记录内容）。"""
    digest = hash_sanitized(b"not json at all")

    assert digest.startswith("sha256:")
    assert digest == hash_sanitized(b"not json at all")


@pytest.mark.parametrize("body", [b"", b"[]", b'{"a": null}'])
def test_hash_sanitized_handles_edge_bodies(body: bytes) -> None:
    """边界 body（空 / 数组 / null）⇒ 也能算出稳定哈希，不抛。"""
    assert hash_sanitized(body).startswith("sha256:")
