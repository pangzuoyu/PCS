"""P4-3+ 管网计算服务包。

子模块：
- topology_service：P4-3-1 管网拓扑模型（节点 / 边 / 图结构 + 合法性校验）。
- solver_service：P4-3-2 Hardy-Cross 求解器（流量分配 + 压力回推 + 节点压降守恒）。
- pipe_net_persist：P4-3-3 落库 helper（pipe_network_results + outlet_stream）。
- surge_pressure：P6-5+C-13 PIPE_NET 浪涌压力（Joukowsky + Wylie-Streeter 管壁修正）。
"""
from app.services.pipe_net.pipe_net_persist import persist_pipe_network_result
from app.services.pipe_net.solver_service import (
    EdgeFlowResult,
    NetworkConvergenceError,
    NodePressureResult,
    PipeNetworkResult,
    PipeNetworkSolverInputError,
    SolverConfig,
    solve_network,
)
from app.services.pipe_net.surge_pressure import (
    SurgePressureInput,
    SurgePressureInputError,
    SurgePressureResult,
    calc_water_hammer_surge,
)
from app.services.pipe_net.topology_service import (
    EdgeInput,
    NodeInput,
    NodeType,
    PipeNetworkInput,
    TopologyInputError,
    TopologyUnconnectedError,
    TopologyValidation,
    validate_topology,
)

__all__ = [
    "EdgeFlowResult",
    "EdgeInput",
    "NetworkConvergenceError",
    "NodeInput",
    "NodePressureResult",
    "NodeType",
    "PipeNetworkInput",
    "PipeNetworkResult",
    "PipeNetworkSolverInputError",
    "SolverConfig",
    "SurgePressureInput",
    "SurgePressureInputError",
    "SurgePressureResult",
    "TopologyInputError",
    "TopologyUnconnectedError",
    "TopologyValidation",
    "calc_water_hammer_surge",
    "persist_pipe_network_result",
    "solve_network",
    "validate_topology",
]
