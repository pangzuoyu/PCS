"""P6-5 Q3 fix 配套正式单元测试。

覆盖 TTL 机制 3 个不变量（架构组裁决"合并后立即补测"，commit e35064b）：
  1. TTL 过期后下次调用触发 loader 重载
  2. clear_all_caches() 强制清空，下次调用重新加载
  3. 4 个独立 cache_key 互相隔离（key A 过期不影响 key B）

mock time.monotonic 控制时钟；patch _load_with_fallback 隔离 DB 依赖，
走 get_pasquill_sigma_table() / get_api521_thresholds_table() 公开入口的真实 TTL 路径。
"""
from __future__ import annotations

from unittest.mock import patch

import pytest

from app.services import _compound_config_cache
from app.services._compound_config_cache import clear_all_caches


@pytest.fixture(autouse=True)
def _isolate_cache_state():
    """每个测试前后清空全局 TTL 状态，避免测试间相互污染。"""
    clear_all_caches()
    yield
    clear_all_caches()


def test_cache_ttl_expiry_triggers_reload():
    """TTL=300s：t=0 首次加载命中 loader；TTL 内命中 cache；TTL 过期触发重载。"""
    fake_table = {"A": (0.1, 0.2, 0.3, 0.4)}
    with patch.object(
        _compound_config_cache,
        "_load_with_fallback",
        return_value=fake_table,
    ) as mock_load:
        with patch.object(_compound_config_cache.time, "monotonic") as mock_clock:
            # t=0：首次加载（cache miss）
            mock_clock.return_value = 0.0
            r1 = _compound_config_cache.get_pasquill_sigma_table()
            # t=100：TTL 内命中 cache（100-0=100 ≤ 300）
            mock_clock.return_value = 100.0
            r2 = _compound_config_cache.get_pasquill_sigma_table()
            # t=301：超过 TTL 触发重载（301-0=301 > 300）
            mock_clock.return_value = 301.0
            r3 = _compound_config_cache.get_pasquill_sigma_table()

    assert r1 == fake_table
    assert r2 == fake_table  # 命中 cache，值不变
    assert r3 == fake_table  # 重载后值仍一致
    assert mock_load.call_count == 2  # r1 + r3 各调 1 次，r2 命中 cache


def test_cache_clear_all_caches_forces_reload():
    """TTL 内连续调用命中 cache；clear_all_caches() 后下次调用强制重载。"""
    fake_table = {"A": (0.1, 0.2, 0.3, 0.4)}
    with patch.object(
        _compound_config_cache,
        "_load_with_fallback",
        return_value=fake_table,
    ) as mock_load:
        with patch.object(
            _compound_config_cache.time,
            "monotonic",
            return_value=0.0,
        ):
            r1 = _compound_config_cache.get_pasquill_sigma_table()
            r2 = _compound_config_cache.get_pasquill_sigma_table()  # TTL 内命中 cache
            clear_all_caches()
            r3 = _compound_config_cache.get_pasquill_sigma_table()  # cache 清空，强制重载

    assert r1 == r2 == r3 == fake_table
    assert mock_load.call_count == 2  # r1 + r3 各调 1 次


def test_cache_per_key_isolation():
    """key A 过期触发 A 重载，key B 在 TTL 内继续命中 cache（per-key 隔离）。"""
    fake_a = {"A": (0.1, 0.2, 0.3, 0.4)}
    fake_b = {"LETHALITY": 6.31}
    call_count = {"n": 0}

    def selective_fallback(loader_fn):
        """按调用顺序返回 fake_a / fake_b / fake_a（pasquill / api521 / pasquill 重载）。"""
        call_count["n"] += 1
        if call_count["n"] == 1:
            return fake_a  # pasquill 首次
        if call_count["n"] == 2:
            return fake_b  # api521 首次
        if call_count["n"] == 3:
            return fake_a  # pasquill TTL 过期重载
        raise AssertionError(
            f"unexpected _load_with_fallback call #{call_count['n']} "
            "(per-key isolation 失效：B 在 TTL 内被不应重载)",
        )

    with patch.object(
        _compound_config_cache,
        "_load_with_fallback",
        side_effect=selective_fallback,
    ):
        with patch.object(_compound_config_cache.time, "monotonic") as mock_clock:
            # t=0：A 首次加载（pasquill 缓存时间戳 = 0.0）
            mock_clock.return_value = 0.0
            r_a1 = _compound_config_cache.get_pasquill_sigma_table()
            # t=100：B 首次加载（api521 缓存时间戳 = 100.0）
            mock_clock.return_value = 100.0
            r_b1 = _compound_config_cache.get_api521_thresholds_table()
            # t=250：两者都在 TTL 内
            # （A：250-0=250 ≤ 300；B：250-100=150 ≤ 300）
            mock_clock.return_value = 250.0
            r_a2 = _compound_config_cache.get_pasquill_sigma_table()
            r_b2 = _compound_config_cache.get_api521_thresholds_table()
            # t=301：A 过期（301-0=301 > 300），B 未过期（301-100=201 ≤ 300）
            mock_clock.return_value = 301.0
            r_a3 = _compound_config_cache.get_pasquill_sigma_table()
            r_b3 = _compound_config_cache.get_api521_thresholds_table()

    assert r_a1 == r_a2 == r_a3 == fake_a
    assert r_b1 == r_b2 == r_b3 == fake_b
    # 关键断言：3 次 _load_with_fallback 调用（A1 / B1 / A3），B 第二次起全 cache 命中
    assert call_count["n"] == 3, (
        f"expected 3 _load_with_fallback calls (per-key isolation broken), "
        f"got {call_count['n']}",
    )