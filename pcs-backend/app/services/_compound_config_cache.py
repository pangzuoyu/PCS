"""P6-5 C5 收口：4 张 CONFIG 表的 5 min TTL 缓存加载辅助（共享模块）。

按 P6-5 计划 Task C5 Step 4：service 层启动时 5 min TTL 缓存 CONFIG 表 →
fallback 到 dataclass 内联常量（双轨制，缺数据时不抛错）。

设计要点：

- ``functools.lru_cache(maxsize=1)`` 进程内永久缓存（brief 锁定模式）；
  真实 5 min 失效可在后续批通过外部 cron / ``cache_clear()`` 触发。
- 4 个独立函数分别覆盖 4 张表，**任一函数异常都吞掉并返回 None**（不
  影响主流程），由调用 service 自行 fallback 到内联常量。
- DB 会话通过 ``app.db.session.get_engine()`` + 新建 ``sessionmaker``；
  避免引入额外异步依赖（service 层同步计算）。
- 一次性开销（首次调用 DB read），后续调用内存返回（微秒级）。

约束：

- 不继承 ``TaggedRecordMixin``（元数据表非业务计算记录）；service 层只
  读取 ``source='SYNTHETIC_TEST_DATA'`` 之外的所有行（真实数据优先）。
- 该模块为同步加载，**不能**在 async 上下文中直接调用；service 层
  在同步主流程入口调用（dispersion_service.calc_dispersion 等）。
"""
from __future__ import annotations

import functools
from typing import Final

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.core.config import get_settings


def _load_with_fallback[T](loader):
    """通用包装：DB 加载失败时返回 None（由 service fallback）。

    Args:
        loader: 接收 ``Session`` 实例并返回 T（已构造好的 fallback 数据）。

    Returns:
        DB 加载成功返回 loader(session) 结果；失败返回 None。
    """
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
        # DB 不可达 / 表未迁移 / 其他异常 — 静默返回 None，由 service fallback
        return None


# -----------------------------------------------------------------------------
# 1. Pasquill-Gifford σ 系数（C-22 dispersion_service）
# -----------------------------------------------------------------------------
@functools.lru_cache(maxsize=1)
def get_pasquill_sigma_table() -> (
    "dict[str, tuple[float, float, float, float]] | None"
):
    """从 ``compound_pasquill_sigma`` 表加载 Briggs 1973 系数。

    Returns:
        ``{stability_class: (a_y, b_y, a_z, b_z)}`` 或 None（DB 不可达
        / 表空 / 异常）。
    """
    from app.models.config import CompoundPasquillSigma

    def loader(session) -> dict[str, tuple[float, float, float, float]] | None:
        rows = session.execute(select(CompoundPasquillSigma)).scalars().all()
        if not rows:
            return None
        return {
            r.stability_class: (r.a_y, r.b_y, r.a_z, r.b_z) for r in rows
        }

    return _load_with_fallback(loader)


# -----------------------------------------------------------------------------
# 2. API 521 §5.15 致死/致伤阈值（C-22 dispersion_service）
# -----------------------------------------------------------------------------
@functools.lru_cache(maxsize=1)
def get_api521_thresholds_table() -> "dict[str, float] | None":
    """从 ``compound_api521_thresholds`` 表加载 INJURY/LETHALITY 阈值。

    Returns:
        ``{threshold_type: flux_kw_m2}`` 或 None。
    """
    from app.models.config import CompoundApi521Thresholds

    def loader(session) -> dict[str, float] | None:
        rows = session.execute(select(CompoundApi521Thresholds)).scalars().all()
        if not rows:
            return None
        return {r.threshold_type: r.flux_kw_m2 for r in rows}

    return _load_with_fallback(loader)


# -----------------------------------------------------------------------------
# 3. ISO 9613-2 大气吸收系数（C-23 noise_service；仅取 50% RH 默认行）
# -----------------------------------------------------------------------------
@functools.lru_cache(maxsize=1)
def get_iso9613_abs_default_db_per_km() -> "float | None":
    """从 ``compound_iso9613_atmospheric_absorption`` 加载默认大气吸收系数。

    选取 ``humidity_pct=50`` 的行（噪声计算标准工况）；取首条作为
    默认（温度自适应由 service 决定）。

    Returns:
        ``alpha_db_km``（dB/km）或 None。
    """
    from app.models.config import CompoundIso9613AtmosphericAbsorption

    def loader(session) -> float | None:
        rows = session.execute(
            select(CompoundIso9613AtmosphericAbsorption).where(
                CompoundIso9613AtmosphericAbsorption.humidity_pct == 50.0,
            )
        ).scalars().all()
        if not rows:
            return None
        return rows[0].alpha_db_km

    return _load_with_fallback(loader)


# -----------------------------------------------------------------------------
# 4. Hammerschmidt K 因子（C-18 hydrate_inhibition_service）
# -----------------------------------------------------------------------------
@functools.lru_cache(maxsize=1)
def get_hammerschmidt_K_table() -> "dict[str, float] | None":
    """从 ``compound_hammerschmidt_K`` 表加载 K 因子。

    Returns:
        ``{inhibitor_type: K}`` 或 None。
    """
    from app.models.config import CompoundHammerschmidtK

    def loader(session) -> dict[str, float] | None:
        rows = session.execute(select(CompoundHammerschmidtK)).scalars().all()
        if not rows:
            return None
        return {r.inhibitor_type: r.K for r in rows}

    return _load_with_fallback(loader)


__all__: Final[list[str]] = [
    "get_pasquill_sigma_table",
    "get_api521_thresholds_table",
    "get_iso9613_abs_default_db_per_km",
    "get_hammerschmidt_K_table",
]
