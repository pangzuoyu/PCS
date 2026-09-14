"""P4-3+ 管网计算服务包。

子模块：
- topology_service：P4-3-1 管网拓扑模型（节点 / 边 / 图结构 + 合法性校验）。
- solver_service：P4-3-2 Hardy-Cross 求解器（流量分配 + 压力回推 + 节点压降守恒）。
"""
from app.services.pipe_net.solver_service import (
    EdgeFlowResult,
    NetworkConvergenceError,
    NodePressureResult,
    PipeNetworkResult,
    PipeNetworkSolverInputError,
    SolverConfig,
    solve_network,
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
    "TopologyInputError",
    "TopologyUnconnectedError",
    "TopologyValidation",
    "solve_network",
    "validate_topology",
]
