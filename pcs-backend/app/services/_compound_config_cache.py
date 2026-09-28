"""P6-5 C5 收口：4 张 CONFIG 表的 5 min TTL 缓存加载辅助（共享模块）。

架构组 Q3 裁决：原 ``functools.lru_cache(maxsize=1)`` 是进程内永久缓存，
会让运营期 ``compound_*`` 表变更不可见；已替换为真实 5 min TTL
（``time.monotonic()`` + ``threading.Lock``）。调用 ``clear_all_caches()``
可强制清空（热重载 / 运营期手动触发）。

service 层调用入口（dispersion / noise / hydrate_inhibition）触发首次 DB
read；后续 5 min 内调用直接返回内存值。任一 loader 异常都吞掉并返回
None，由 service fallback 到 dataclass 内联常量。

仅 stdlib（``threading``、``time``）；同步加载，不能在 async 上下文中调用。
参考：``docs/superpowers/plans/2026-09-26-p6-5-batch.md`` Step 4。
"""
from __future__ import annotations

import threading
import time
from typing import Any, Final

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.core.config import get_settings

_CACHE_TTL_SECONDS: Final[int] = 300  # 5 minutes per plan C5 Step 4
_TTL_CACHE_STATE: Final[dict[str, tuple[float, Any]]] = {}
_TTL_CACHE_LOCK: Final[threading.Lock] = threading.Lock()


def _get_cached_or_reload(cache_key: str, loader_fn) -> Any:
    """TTL 缓存：命中返回内存值，过期或首次访问调用 ``loader_fn`` 重读。"""
    with _TTL_CACHE_LOCK:
        entry = _TTL_CACHE_STATE.get(cache_key)
        if entry is not None and time.monotonic() - entry[0] <= _CACHE_TTL_SECONDS:
            return entry[1]
    value = loader_fn()  # 锁外执行 DB 加载，避免长时持锁
    with _TTL_CACHE_LOCK:
        _TTL_CACHE_STATE[cache_key] = (time.monotonic(), value)
    return value


def clear_all_caches() -> None:
    """强制清空全部 TTL 缓存（热重载 / 运营期手动触发）。"""
    with _TTL_CACHE_LOCK:
        _TTL_CACHE_STATE.clear()


def _load_with_fallback[T](loader):
    """DB 加载失败时返回 None（由 service fallback 到内联常量）。"""
    try:
        settings = get_settings()
        engine = create_engine(settings.database_url)
        Session = sessionmaker(bind=engine)
        try:
            with Session() as session:
                return loader(session)
        finally:
            engine.dispose()
    except Exception:
        return None


# -----------------------------------------------------------------------------
# 1. Pasquill-Gifford σ 系数（C-22 dispersion_service）
# -----------------------------------------------------------------------------
def get_pasquill_sigma_table() -> dict[str, tuple[float, float, float, float]] | None:
    """从 ``compound_pasquill_sigma`` 表加载 Briggs 1973 系数。"""
    from app.models.config import CompoundPasquillSigma

    def loader() -> dict[str, tuple[float, float, float, float]] | None:
        def query(session) -> dict[str, tuple[float, float, float, float]] | None:
            rows = session.execute(select(CompoundPasquillSigma)).scalars().all()
            if not rows:
                return None
            return {r.stability_class: (r.a_y, r.b_y, r.a_z, r.b_z) for r in rows}
        return _load_with_fallback(query)

    return _get_cached_or_reload("pasquill_sigma", loader)


# -----------------------------------------------------------------------------
# 2. API 521 §5.15 致死/致伤阈值（C-22 dispersion_service）
# -----------------------------------------------------------------------------
def get_api521_thresholds_table() -> dict[str, float] | None:
    """从 ``compound_api521_thresholds`` 表加载 INJURY/LETHALITY 阈值。"""
    from app.models.config import CompoundApi521Thresholds

    def loader() -> dict[str, float] | None:
        def query(session) -> dict[str, float] | None:
            rows = session.execute(select(CompoundApi521Thresholds)).scalars().all()
            if not rows:
                return None
            return {r.threshold_type: r.flux_kw_m2 for r in rows}
        return _load_with_fallback(query)

    return _get_cached_or_reload("api521_thresholds", loader)


# -----------------------------------------------------------------------------
# 3. ISO 9613-2 大气吸收系数（C-23 noise_service；50% RH 默认行）
# -----------------------------------------------------------------------------
def get_iso9613_abs_default_db_per_km() -> float | None:
    """从 ``compound_iso9613_atmospheric_absorption`` 加载默认大气吸收系数。"""
    from app.models.config import CompoundIso9613AtmosphericAbsorption

    def loader() -> float | None:
        def query(session) -> float | None:
            rows = session.execute(
                select(CompoundIso9613AtmosphericAbsorption).where(
                    CompoundIso9613AtmosphericAbsorption.humidity_pct == 50.0,
                )
            ).scalars().all()
            if not rows:
                return None
            return rows[0].alpha_db_km
        return _load_with_fallback(query)

    return _get_cached_or_reload("iso9613_abs_default", loader)


# -----------------------------------------------------------------------------
# 5. 管材弹性模量 E（C-13 surge_pressure）
# -----------------------------------------------------------------------------
def get_pipe_E_modulus_table() -> dict[str, float] | None:
    """从 ``pipe_e_modulus`` 表加载 E 模量（psi → Pa 换算）。

    返回 ``{grade: E_Pa}`` 字典；DB 不可达时返回 None，由 service fallback
    到内联 5 等级 X42/X52/X65/X70/X80 圆整值（30e6 psi = 206.84e9 Pa）。
    """
    from app.models.config import PipeEModulus

    _PSI_TO_PA = 6894.76

    def loader() -> dict[str, float] | None:
        def query(session) -> dict[str, float] | None:
            rows = session.execute(select(PipeEModulus)).scalars().all()
            if not rows:
                return None
            return {r.grade: r.e_psi * _PSI_TO_PA for r in rows}
        return _load_with_fallback(query)

    return _get_cached_or_reload("pipe_E_modulus", loader)


# -----------------------------------------------------------------------------
# 4. Hammerschmidt K 因子（C-18 hydrate_inhibition_service）
# -----------------------------------------------------------------------------
def get_hammerschmidt_K_table() -> dict[str, float] | None:
    """从 ``compound_hammerschmidt_K`` 表加载 K 因子。"""
    from app.models.config import CompoundHammerschmidtK

    def loader() -> dict[str, float] | None:
        def query(session) -> dict[str, float] | None:
            rows = session.execute(select(CompoundHammerschmidtK)).scalars().all()
            if not rows:
                return None
            return {r.inhibitor_type: r.K for r in rows}
        return _load_with_fallback(query)

    return _get_cached_or_reload("hammerschmidt_K", loader)


# -----------------------------------------------------------------------------
# 6. Nielsen 1988 A/B/C 常数（C-18 hydrate_inhibition_service 备选 path）
# -----------------------------------------------------------------------------
def get_nielsen_1988_params() -> dict[str, tuple[float, float, float]] | None:
    """从 ``compound_nielsen_1988_params`` 表加载 A/B/C 常数。"""
    from app.models.config import CompoundNielsen1988Params

    def loader() -> dict[str, tuple[float, float, float]] | None:
        def query(session) -> dict[str, tuple[float, float, float]] | None:
            rows = session.execute(select(CompoundNielsen1988Params)).scalars().all()
            if not rows:
                return None
            return {r.component: (r.a, r.b, r.c) for r in rows}
        return _load_with_fallback(query)

    return _get_cached_or_reload("nielsen_1988_params", loader)


__all__: Final[list[str]] = [
    "get_pasquill_sigma_table",
    "get_api521_thresholds_table",
    "get_iso9613_abs_default_db_per_km",
    "get_hammerschmidt_K_table",
    "get_nielsen_1988_params",
    "get_pipe_E_modulus_table",
    "clear_all_caches",
]