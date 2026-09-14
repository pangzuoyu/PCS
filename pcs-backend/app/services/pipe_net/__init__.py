"""P4-3+ 管网计算服务包。

子模块：
- topology_service：P4-3-1 管网拓扑模型（节点 / 边 / 图结构 + 合法性校验）。
  P4-3-2 求解器（流量平衡 / Hardy-Cross / Newton-Raphson）将在此包内新增。
"""
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
    "EdgeInput",
    "NodeInput",
    "NodeType",
    "PipeNetworkInput",
    "TopologyInputError",
    "TopologyUnconnectedError",
    "TopologyValidation",
    "validate_topology",
]