"""OPEN_CHANNEL 明渠流计算模块（SPEC §3.2.6）。

依据：P6-OPEN-001（G-01 degraded）+ ADR-0030 V1.2 决策 7（自研兜底）。

模块导出：

- ``manning`` 提供 ``calc_manning_flow``：Manning 公式流量
  Q = (1/n) × A × R^(2/3) × √S（矩形/梯形/圆形断面）
- ``section`` 提供 ``calc_optimal_section``：给定流量 + 坡度 + 糙率
  → 水力最优断面（矩形 b/h=2，梯形 b/h=2(√(1+m²)−m)，圆形二分法）
- ``critical`` 提供 ``calc_critical_depth`` + ``calc_froude_number``：
  矩形断面临界水深 h_c = (q²/g)^(1/3) + Froude 数 Fr = v / √(g × h_m)
- ``jump`` 提供 ``calc_hydraulic_jump``：矩形断面 Bélanger 方程
  共轭水深 h₂/h₁ = 0.5(√(1+8Fr₁²)−1) + 能量损失 ΔE + 5 档跃型判定

不含 endpoint 挂载（Task 32）+ 不含落库（Task 32）+ 不含 G-01 重试（P6+ backlog）。

P6-OPEN-001 G-01 degraded：禁止 import fluids.open_channel（子模块不存在）；
禁止 import chedl_wrapper 中 OPEN_CHANNEL 函数（无；本任务自研）。
"""
from app.services.open_channel.critical import (  # P6-3 Task 31
    CriticalInput,
    CriticalInputError,
    CriticalResult,
    calc_critical_depth,
    calc_froude_number,
)
from app.services.open_channel.jump import (  # P6-3 Task 31
    JumpInput,
    JumpInputError,
    JumpResult,
    calc_hydraulic_jump,
)
from app.services.open_channel.manning import (  # P6-3 Task 31
    ManningInput,
    ManningInputError,
    ManningResult,
    calc_manning_flow,
)
from app.services.open_channel.open_channel_persist_service import (  # P6-3 Task 32
    OpenChannelPersistInputError,
    create_open_channel_result_direct,
    get_open_channel_result_service,
    list_open_channel_results_service,
    save_critical_result,
    save_jump_result,
    save_manning_result,
    save_section_result,
    soft_delete_open_channel_result_service,
    update_open_channel_result_service,
)
from app.services.open_channel.section import (  # P6-3 Task 31
    SectionInput,
    SectionInputError,
    SectionResult,
    calc_optimal_section,
)

__all__ = [
    # manning（§3.2.6 Manning 公式流量）
    "ManningInput",
    "ManningResult",
    "ManningInputError",
    "calc_manning_flow",
    # section（§3.2.6 最优水力断面）
    "SectionInput",
    "SectionResult",
    "SectionInputError",
    "calc_optimal_section",
    # critical（§3.2.6 临界水深 + Froude 数）
    "CriticalInput",
    "CriticalResult",
    "CriticalInputError",
    "calc_critical_depth",
    "calc_froude_number",
    # jump（§3.2.6 水跃 Bélanger + 能量损失 + 跃型判定）
    "JumpInput",
    "JumpResult",
    "JumpInputError",
    "calc_hydraulic_jump",
    # P6-3 Task 32 — open_channel_persist（OpenChannelResult 落库 + CRUD）
    "OpenChannelPersistInputError",
    "save_manning_result",
    "save_section_result",
    "save_critical_result",
    "save_jump_result",
    "list_open_channel_results_service",
    "get_open_channel_result_service",
    "update_open_channel_result_service",
    "soft_delete_open_channel_result_service",
    "create_open_channel_result_direct",
]
