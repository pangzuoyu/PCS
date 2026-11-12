"""AI 端点的**内网 CIDR 校验**（P10-A · Task T5）。

## 为什么

SPEC §2.5「**私有化强制**：所有 LLM 模型必须部署于公司内网，禁止调用外部
云 AI 服务」⇒ AI endpoint 解析出的 IP **必须**落在内网 CIDR 里。

⇒ 校验点有**两个**，缺一不可：

- **启动时**（`app/main.py` 的 lifespan）—— 配置错了就别起来，
  而不是等到第一次调用才发现打到了公网；
- **调用时**（`app/core/outbound_ai_client.py`）—— DNS 会漂移
  （内网域名解析到公网）⇒ 启动时过了不代表此刻还成立。

## 三条容易写错的（都在测试里钉住）

1. **地址族不匹配不得抛** —— `IPv6Address in IPv4Network` 是 `TypeError`
   ⇒ 一个 IPv6 endpoint 打 IPv4 CIDR 会直接崩（而不是「不匹配」）。
2. **非法 CIDR ⇒ `RuntimeError`**（不是裸 `ValueError`）—— 启动时抛裸
   `ValueError` 运维看不懂「哪个值坏了」⇒ 消息里带**原文**。
3. **解析失败 ⇒ 抛错**（不是返回空列表）—— 空列表的语义歧义：
   「解析失败」与「解析到公网」处置不同 ⇒ 混成一个空列表 = 把两种故障
   压成一种。
"""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse


def parse_cidrs(value: str) -> list[str]:
    """把逗号分隔的 CIDR 串解析成列表。

    - 空值 / 全空白 ⇒ `[]`
    - 每项去空白
    - **非法 CIDR ⇒ `RuntimeError`**（消息里带原文）

    ⚠️ 这是**单一解析点**（`Settings.internal_cidrs` 存原始串 ⇒ 解析只发生
    在这里）⇒ 非法值能报出清晰错误，而不是散落在各处各解析一次。
    """
    items = [part.strip() for part in value.split(",")]
    result: list[str] = []
    for item in items:
        if not item:
            continue
        try:
            ipaddress.ip_network(item, strict=False)
        except ValueError as exc:
            raise RuntimeError(
                f"非法的内网 CIDR 配置：{item!r}（{exc}）"
                " —— INTERNAL_CIDRS 必须是逗号分隔的 CIDR，例：10.0.0.0/8,192.168.0.0/16"
            ) from exc
        result.append(item)
    return result


def ip_in_cidrs(ip: str, cidrs: list[str]) -> bool:
    """IP 是否落在任一 CIDR 内。

    ⚠️ **地址族不匹配 ⇒ 不匹配（不抛）**：IPv6 地址查 IPv4 网段
    （`IPv6Address in IPv4Network` 是 `TypeError`）⇒ 必须显式跳过。
    ⚠️ 非法 IP / 非法 CIDR ⇒ 当作不匹配（不抛）—— 调用方拿返回值做
    「要不要拒绝」的判断，抛错会让调用点的错误处理变得不一致。
    """
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return False
    for entry in cidrs:
        try:
            network = ipaddress.ip_network(entry, strict=False)
        except ValueError:
            continue
        if addr.version != network.version:
            continue
        if addr in network:
            return True
    return False


def host_of(endpoint: str) -> str:
    """从 endpoint（可能是 URL 或裸 host:port）取出主机部分。

    ⚠️ **唯一的一份解析**（2026-11-12 评审 M-6）：`/health/ai` 曾内联复制
    一份「去协议 / 去路径 / 去端口」的逻辑 ⇒ 与 `urlparse` 的口径不同
    （大小写、`user:pass@host`）⇒ **两个安全相关判断可能给出相反结论**。
    ⇒ 公开出来给调用方复用。
    """
    raw = endpoint.strip()
    if "://" in raw:
        parsed = urlparse(raw)
        return parsed.hostname or ""
    # 裸 `host:port` —— 去掉端口
    if raw.startswith("[") and "]" in raw:  # IPv6 字面量 [::1]:8000
        return raw[1 : raw.index("]")]
    return raw.split(":", 1)[0]


def resolve_ai_endpoint_ips(endpoint: str) -> list[str]:
    """解析 endpoint ⇒ 它当前解析到的 IP 列表。

    - **IP 字面量** ⇒ 直接返回它（**不解析 DNS**）
    - **域名** ⇒ 走 `socket.getaddrinfo`
    - 解析失败 ⇒ `RuntimeError`（**不是**空列表 —— 见模块 docstring）

    ⚠️ 一个域名可能解析到**多个** IP ⇒ 返回列表（逐个判定）。
    """
    host = host_of(endpoint)
    if not host:
        raise RuntimeError(f"AI endpoint 为空或格式非法：{endpoint!r}")
    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        return [host]

    try:
        infos = socket.getaddrinfo(host, None, proto=socket.IPPROTO_TCP)
    except OSError as exc:
        raise RuntimeError(f"AI endpoint 的主机名解析失败：{host!r}（{exc}）") from exc
    ips = sorted({info[4][0] for info in infos})
    if not ips:
        raise RuntimeError(f"AI endpoint 的主机名解析不到任何 IP：{host!r}")
    return ips


def validate_ai_endpoint(endpoint: str, cidrs: list[str]) -> None:
    """校验 endpoint 落在内网 CIDR 内；不在 ⇒ `RuntimeError`。

    ⚠️ **一个 IP 都不在 ⇒ 拒**；**部分在内、部分在外 ⇒ 拒**
    （部分在内意味着有流量会打到公网 ⇒ 违反「私有化强制」）。
    """
    ips = resolve_ai_endpoint_ips(endpoint)
    outside = [ip for ip in ips if not ip_in_cidrs(ip, cidrs)]
    if outside:
        raise RuntimeError(
            f"AI endpoint {endpoint!r} 解析到不在内网 CIDR 的地址：{outside}"
            f"（允许的内网网段：{cidrs or '（未配置）'}）"
            " —— SPEC §2.5 要求模型私有化部署，禁止外部 API 调用"
        )


def validate_ai_startup_config(
    *, ai_enabled: bool, endpoint: str | None, cidrs: list[str]
) -> None:
    """**启动时**校验 AI 配置（纯函数 ⇒ 好测）。

    - AI 关着 ⇒ **直接放行**（P10 阶段 AI 默认关 ⇒ 不能挡住服务启动）
    - AI 开着但 endpoint 为空 ⇒ `RuntimeError`
    - AI 开着且 endpoint 不在内网 ⇒ `RuntimeError`

    ⚠️ 调用方（`app/main.py` 的 lifespan）负责**读库**拿 `ai_enabled` 与
    `ai_endpoint`，本函数只管判定 ⇒ 判定逻辑可单测。
    """
    if not ai_enabled:
        return
    if not endpoint:
        raise RuntimeError("ai_enabled=true 但 AI endpoint 为空")
    validate_ai_endpoint(endpoint, cidrs)
