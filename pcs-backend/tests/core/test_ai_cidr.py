"""`app/core/ai_cidr.py` 的测试（P10-A · Task T5）。

## 为什么要有这一层

SPEC §2.5「**私有化强制**：所有 LLM 模型必须部署于公司内网，禁止调用外部云
AI 服务」⇒ endpoint 的 IP **必须**落在内网 CIDR 里。
⇒ 校验点有两个：**启动时**（配置错了就别起）· **调用时**（防 DNS 漂移）。

## 三条容易写错的

1. **地址族不匹配不得抛** —— `IPv6Address in IPv4Network` 是 `TypeError`
   ⇒ 一个 IPv6 endpoint 打 IPv4 CIDR 会直接崩（而不是「不匹配」）。
2. **非法 CIDR ⇒ `RuntimeError`**（不是裸 `ValueError`）—— 启动时抛裸
   `ValueError` 运维看不懂 ⇒ 消息里要带**原文**。
3. **DNS 必须 mock** —— 真解析依赖网络 ⇒ 测试环境可能无网/不稳定 ⇒ flaky。
"""
from __future__ import annotations

import socket

import pytest

from app.core.ai_cidr import (
    ip_in_cidrs,
    parse_cidrs,
    resolve_ai_endpoint_ips,
    validate_ai_endpoint,
    validate_ai_startup_config,
)


def test_parse_cidrs_handles_empty_and_spaces() -> None:
    """'' ⇒ []；' 10.0.0.0/8 , 192.168.0.0/16 ' ⇒ 两条（去空格）。"""
    assert parse_cidrs("") == []
    assert parse_cidrs("   ") == []
    assert parse_cidrs(" 10.0.0.0/8 , 192.168.0.0/16 ") == [
        "10.0.0.0/8",
        "192.168.0.0/16",
    ]


def test_parse_cidrs_rejects_invalid_cidr_with_clear_message() -> None:
    """'not-a-cidr' ⇒ RuntimeError，消息里含那个串。

    ⚠️ 必须是 `RuntimeError` 而不是裸 `ValueError` —— 启动时抛裸
    `ValueError` 运维看不懂「哪个值坏了」。
    """
    with pytest.raises(RuntimeError) as excinfo:
        parse_cidrs("not-a-cidr")

    assert "not-a-cidr" in str(excinfo.value)


def test_ip_in_cidrs_handles_ipv6_against_ipv4_list() -> None:
    """⚠️ **地址族不匹配不得抛** —— `IPv6Address in IPv4Network` 会 TypeError
    ⇒ 必须捕获并返回 False（否则一个 IPv6 endpoint 打 IPv4 CIDR 直接崩）。"""
    assert ip_in_cidrs("fd00::1", ["10.0.0.0/8"]) is False


def test_ip_in_cidrs_supports_ipv6() -> None:
    """'fd00::1' in ['fd00::/8'] ⇒ True。"""
    assert ip_in_cidrs("fd00::1", ["fd00::/8"]) is True


def test_ip_in_cidrs_returns_false_for_garbage_ip() -> None:
    """非法 IP ⇒ False（不是抛）—— 调用方拿它做「要不要拒绝」的判断。"""
    assert ip_in_cidrs("not-an-ip", ["10.0.0.0/8"]) is False


def test_validate_ai_endpoint_rejects_public_ip() -> None:
    """8.8.8.8 + ['10.0.0.0/8'] ⇒ RuntimeError。"""
    with pytest.raises(RuntimeError):
        validate_ai_endpoint("8.8.8.8", ["10.0.0.0/8"])


def test_validate_ai_endpoint_accepts_private_ip() -> None:
    """10.1.2.3 + ['10.0.0.0/8'] ⇒ 不抛。"""
    validate_ai_endpoint("10.1.2.3", ["10.0.0.0/8"])


def test_validate_ai_endpoint_rejects_dns_resolving_outside(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """域名解析到公网 ⇒ RuntimeError。

    ⚠️ **必须 mock DNS**（`monkeypatch.setattr(socket, "getaddrinfo", fake)`）——
    真解析依赖网络 ⇒ 测试环境可能无网/不稳定 ⇒ **flaky 测试**。
    """

    def fake_getaddrinfo(host, port, *args, **kwargs):  # noqa: ANN001, ANN002, ANN003, ANN201
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("8.8.8.8", 443))]

    monkeypatch.setattr(socket, "getaddrinfo", fake_getaddrinfo)

    with pytest.raises(RuntimeError):
        validate_ai_endpoint("ai.example.internal", ["10.0.0.0/8"])


def test_resolve_ai_endpoint_ips_returns_literal_for_ip_endpoint() -> None:
    """IP 字面量 ⇒ 直接返回它（**不解析 DNS**）。"""
    assert resolve_ai_endpoint_ips("10.1.2.3") == ["10.1.2.3"]


def test_resolve_ai_endpoint_ips_raises_on_unresolvable_host(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """域名解析失败 ⇒ RuntimeError（不是空列表 ⇒ 空列表会被当成「不在内网」）。

    ⚠️ 空列表的语义歧义：解析失败 vs 解析到公网 ⇒ 两者处置不同 ⇒ 抛错。
    ⚠️ **mock 掉 DNS** —— 真解析依赖网络（可能无网 / 很慢 ⇒ flaky）。
    """

    def fake_getaddrinfo(host, port, *args, **kwargs):  # noqa: ANN001, ANN002, ANN003, ANN201
        raise socket.gaierror("Name or service not known")

    monkeypatch.setattr(socket, "getaddrinfo", fake_getaddrinfo)

    with pytest.raises(RuntimeError):
        resolve_ai_endpoint_ips("no-such-host.invalid")


# ---------------------------------------------------------------------------
# 启动时校验（SPEC §3.2.1(5)）—— 判定逻辑是**纯函数** ⇒ 好测
# ---------------------------------------------------------------------------


def test_startup_validation_passes_when_ai_disabled() -> None:
    """AI 关着 ⇒ **直接放行**（P10 阶段 AI 默认关 ⇒ 不能挡住服务启动）。"""
    validate_ai_startup_config(ai_enabled=False, endpoint=None, cidrs=[])


def test_startup_validation_rejects_enabled_without_endpoint() -> None:
    """AI 开着但 endpoint 为空 ⇒ RuntimeError。"""
    with pytest.raises(RuntimeError):
        validate_ai_startup_config(ai_enabled=True, endpoint=None, cidrs=["10.0.0.0/8"])


def test_startup_validation_rejects_endpoint_outside_cidrs() -> None:
    """AI 开着 + endpoint 在公网 ⇒ RuntimeError（**启动即失败**，不是等第一次调用）。"""
    with pytest.raises(RuntimeError):
        validate_ai_startup_config(
            ai_enabled=True, endpoint="8.8.8.8", cidrs=["10.0.0.0/8"]
        )


def test_startup_validation_accepts_endpoint_inside_cidrs() -> None:
    """AI 开着 + endpoint 在内网 ⇒ 放行。"""
    validate_ai_startup_config(
        ai_enabled=True, endpoint="10.1.2.3", cidrs=["10.0.0.0/8"]
    )
