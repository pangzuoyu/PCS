"""二维码载荷必须带**可验的签名** —— 否则 `/report/verify` 必然 403。

## 缺陷（评审 P1 #4）

`report_service._render_sync` 把 `qr_payload=None` **写死**，
`build_qr_payload` 在生产路径上**零调用者**，而 `_check_sig` 要求
`sig` + `exp` 齐备才放行、缺一即 403。于是印在报表上的二维码用于现场
核验这条能力**今天不可能成功** —— 且没有任何一层会说话。

## 评审说的那个障碍不存在

评审建议「签名含时间戳，不能参与 `_content_hash`，否则破坏同内容同哈希，
所以要把 `store_rendered` 改成『先 upsert PENDING 行 → 用它的 id 签名 →
渲染 → 落盘』」。**这个前提是错的**：`_content_hash` 哈希的是
**Blocks + style + format + ctx**，`qr_payload` **根本不在其中**
（见 `_content_hash` 的 docstring：刻意不对渲染后的字节取哈希）。

所以不需要重排 `store_rendered`，只需要在渲染**之前**自选一个
`report_file_id`、用它签名、渲染时带上，并在 upsert 时把**同一个 id**
写进那一行。
"""
from __future__ import annotations

import datetime as dt
import uuid

import pytest

SECRET = "unit-test-secret"


@pytest.fixture
def secret(monkeypatch):
    """把签名密钥钉成定值。

    ⚠️ 不钉的话，`get_settings()` 在 dev 会**每次进程启动自动生成**一个随机
    密钥（`config.py:169-176`）。那意味着签名侧与验签侧各拿一次 settings ——
    同一进程内是一致的，所以本该没问题；但测试里若只在一侧钉值，
    症状是「签名无效」，排查方向会跑到密钥配置上去，而真因是测试没钉。
    """
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "report_verify_secret", SECRET, raising=False)
    return SECRET


def _parse(url: str) -> tuple[str, dict[str, str], str]:
    """拆 QR URL -> (path, query, fragment)。"""
    from urllib.parse import parse_qs, urlsplit

    parts = urlsplit(url)
    q = {k: v[0] for k, v in parse_qs(parts.query).items()}
    return parts.path, q, parts.fragment


def test_signed_payload_round_trips_through_the_real_check(secret):
    """签出来的 `sig`/`exp` 必须能被 `_check_sig` 接受。"""
    from app.api.v1.report import _check_sig
    from app.services.report.qr import build_qr_payload

    rid = uuid.uuid4()
    url = build_qr_payload(
        report_id=str(rid), doc_no="D-001", rev="A",
        version_purpose="DESIGN", record_hashes=["h1", "h2"],
        verify_base_url="https://pcs.example.com",
        report_file_id=rid, secret=SECRET, ttl_seconds=900)  # now=None = 真实当前

    _path, query, _frag = _parse(url)
    assert query.get("sig"), f"URL 里没有 sig：{url}"
    assert query.get("exp"), f"URL 里没有 exp：{url}"

    # 不抛异常 = 验签通过。这是唯一有意义的断言：分两处各写一遍 HMAC 公式，
    # 而其中一处改错了格式，两边都会静默地互相对不上。
    _check_sig(rid, query["sig"], int(query["exp"]))


def test_a_payload_signed_with_a_different_secret_is_rejected(secret):
    """签名必须真的绑定密钥 —— 换密钥就该失效。"""
    from app.api.v1.report import _check_sig
    from app.services.exceptions import PcsError
    from app.services.report.qr import build_qr_payload

    rid = uuid.uuid4()
    url = build_qr_payload(
        report_id=str(rid), doc_no="D", rev="A", version_purpose="DESIGN",
        record_hashes=["h1"], verify_base_url="https://x",
        report_file_id=rid, secret="another-secret",   # ≠ secret
        ttl_seconds=900, now=dt.datetime(2026, 10, 14, tzinfo=dt.UTC))
    _p, q, _f = _parse(url)
    with pytest.raises(PcsError) as ei:
        _check_sig(rid, q["sig"], int(q["exp"]))
    assert ei.value.status == 403


def test_signature_is_bound_to_the_report_file_id(secret):
    """签名必须绑定 id —— 把 A 的签名挪到 B 的 URL 上就该失效。"""
    from app.api.v1.report import _check_sig
    from app.services.exceptions import PcsError
    from app.services.report.qr import build_qr_payload

    a, b = uuid.uuid4(), uuid.uuid4()
    url_a = build_qr_payload(
        report_id=str(a), doc_no="D", rev="A", version_purpose="DESIGN",
        record_hashes=["h"], verify_base_url="https://x",
        report_file_id=a, secret=SECRET, ttl_seconds=900)
    _p, q, _f = _parse(url_a)
    with pytest.raises(PcsError) as ei:
        _check_sig(b, q["sig"], int(q["exp"]))   # 签名是 A 的，却用来验 B
    assert ei.value.status == 403


def test_expired_signature_is_rejected(secret):
    from app.api.v1.report import _check_sig
    from app.services.exceptions import PcsError
    from app.services.report.qr import build_qr_payload

    rid = uuid.uuid4()
    # ttl=1 且 now 取两小时前 ⇒ exp 已过期
    url = build_qr_payload(
        report_id=str(rid), doc_no="D", rev="A", version_purpose="DESIGN",
        record_hashes=["h"], verify_base_url="https://x",
        report_file_id=rid, secret=SECRET, ttl_seconds=1,
        now=dt.datetime.now(dt.UTC) - dt.timedelta(hours=2))
    _p, q, _f = _parse(url)
    with pytest.raises(PcsError) as ei:
        _check_sig(rid, q["sig"], int(q["exp"]))
    assert ei.value.status == 403


def test_the_hmac_formula_has_exactly_one_implementation(secret):
    """签与验必须共用**一份**公式。

    两处各写一遍 HMAC，而其中一处改错格式时，两边会静默地互相对不上 ——
    症状是「所有二维码扫码都是 403」，而签名代码看起来完全正常。
    这与 bug-172 同族（同名副本只修了一个）。
    """
    import ast
    import pathlib

    root = pathlib.Path(__file__).resolve().parents[3] / "app"
    sites = []
    for path in sorted(root.rglob("*.py")):
        src = path.read_text(encoding="utf-8")
        if "sha256" not in src and "new(" not in src:
            continue
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            fn = node.func
            name = getattr(fn, "attr", None) or getattr(fn, "id", None)
            if name == "new":          # hmac.new(...)
                sites.append(f"{path.relative_to(root)}:{node.lineno}")
    assert len(sites) == 1, (
        f"HMAC 计算出现在 {len(sites)} 处：{sites} —— "
        "签名与验签必须共用一份公式，否则改坏其中一处时两边静默对不上")
