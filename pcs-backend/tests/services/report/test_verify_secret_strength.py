"""`REPORT_VERIFY_SECRET` 必须有长度下限（评审 #29）。

## 缺陷

启动校验只检查密钥**非空**：

```python
if not s.report_verify_secret:
    if s.is_production: raise RuntimeError(...)
    s.report_verify_secret = _DEFAULT_DEV_SECRET_PREFIX + secrets.token_urlsafe(48)
```

于是运维把 `REPORT_VERIFY_SECRET` 设成一个字符也能正常启动，
HMAC 于是可被暴力穷举。dev 自动填充用 `token_urlsafe(48)`（约 384 位），
但 1 字节密钥能通过**同一个检查**。

评审的原话很准：这个端点对「缺配置」是 fail-closed，对「弱配置」却是
fail-open —— 同一个变量，两种相反的失败姿态。

## 为什么下限是 32 字节

`SECRET_KEY` 在本仓已经是这个下限（`config.py` 里 `len(...) < 32`），
且形态一致：production 抛错、非 production 警告。
本测试不发明新规则，只是要求第二个密钥享有同一把尺子 ——
**一致性本身就是可维护性**：下次有人加第三个密钥，照抄即可。

## 注意与既有顺序约束的关系

`config.py` 里 REPORT_VERIFY_SECRET 的检查**刻意**放在 JWT iss/aud 之后
（`tests/test_jwt_production.py` 按错误消息断言，顺序反了会让那些测试
拿到本条的消息、掩盖它们本来要验的场景）。本文件只加**长度**这一维，
不改动既有的先后顺序。
"""

from __future__ import annotations

import pytest

from app.core.config import get_settings

#: HMAC-SHA256 的常规密钥下限，与 `SECRET_KEY` 的门槛同值。
MIN_VERIFY_SECRET_BYTES = 32


@pytest.fixture
def clean_env(monkeypatch):
    """清 lru_cache + 环境，避免拿到别的测试留下的 settings。"""
    get_settings.cache_clear()
    monkeypatch.setenv("ENV", "production")
    monkeypatch.setenv("JWT_ISSUER", "pcs-auth")
    monkeypatch.setenv("JWT_AUDIENCE", "pcs-api")
    monkeypatch.setenv("SECRET_KEY", "test-secret-key-must-be-at-least-32-bytes-long")
    yield
    get_settings.cache_clear()


class TestVerifySecretStrength:
    def test_production_rejects_a_short_secret(self, clean_env, monkeypatch):
        """1 字节密钥在 production 必须**拒绝启动**。

        「启动失败」在这里是**正确**行为：继续跑下去等于把二维码
        验签交给可穷举的密钥，而验签失败的症状是 403，
        运维会把 403 归因到「配置漏了」而不是「密钥太弱」。
        """
        monkeypatch.setenv("REPORT_VERIFY_SECRET", "x")
        with pytest.raises(RuntimeError, match="REPORT_VERIFY_SECRET"):
            get_settings()

    def test_production_accepts_a_long_enough_secret(self, clean_env, monkeypatch):
        """下限本身通过 ⇒ 不能把**所有**配置都拒掉（否则测试是在测「总是失败」）。"""
        monkeypatch.setenv("REPORT_VERIFY_SECRET", "y" * MIN_VERIFY_SECRET_BYTES)
        assert len(get_settings().report_verify_secret) >= MIN_VERIFY_SECRET_BYTES

    def test_short_secret_is_still_accepted_in_development_with_a_warning(
        self, clean_env, monkeypatch,
    ):
        """dev 不拦（拦了会打断本地开发），但**必须出声**。

        与 `SECRET_KEY` 的既有形态一致：production 抛错、dev 警告。
        静默接受一个弱密钥正是 #29 指出的 fail-open。
        """
        monkeypatch.setenv("ENV", "development")
        monkeypatch.delenv("JWT_ISSUER", raising=False)
        monkeypatch.delenv("JWT_AUDIENCE", raising=False)
        monkeypatch.setenv("REPORT_VERIFY_SECRET", "x")
        with pytest.warns(RuntimeWarning, match="REPORT_VERIFY_SECRET"):
            s = get_settings()
        assert s.report_verify_secret == "x", "dev 下不应替换运维设的值"

    def test_missing_secret_in_development_gets_a_random_one(self, clean_env, monkeypatch):
        """**没配**才自动填。配了（哪怕短）就用配的那个 —— 见上一条。"""
        monkeypatch.setenv("ENV", "development")
        monkeypatch.delenv("JWT_ISSUER", raising=False)
        monkeypatch.delenv("JWT_AUDIENCE", raising=False)
        monkeypatch.delenv("REPORT_VERIFY_SECRET", raising=False)
        with pytest.warns(RuntimeWarning):
            s = get_settings()
        assert len(s.report_verify_secret) > MIN_VERIFY_SECRET_BYTES, (
            "dev 自动填充必须给出强随机密钥（现状是 token_urlsafe(48)）"
        )
