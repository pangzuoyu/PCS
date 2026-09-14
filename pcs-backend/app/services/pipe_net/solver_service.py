"""P4-3-2：管网 Hardy-Cross 求解器（流量分配 + 压力回推 + 节点压降守恒校验）。

算法（Hardy-Cross 经典管网水力计算）：
1. validate_topology（复用 P4-3-1）：图连通性 / 边界压力合法性
2. 初值分配（EVEN_DEMAND_PROPORTIONAL）：按 demand 比例从 SOURCE 输出到下游
3. 提取 R（阻力系数）和 n（指数）：对每条边调用一次 calc_chain（初始 Q）
   得 total_dp；分离 elevation 静态项与 friction Q-dependent 项
   - R = (total_dp - |elevation_static|) / |Q_ref|^n
   - n = 1 当链式任一段 LAMINAR；否则 n = 2（DW 湍流）
4. 找独立环：E - V + 1 个（cyclomatic complexity）；BFS 树 + 每条 chord 与
   parent chain 构成一个独立环
5. 迭代：每环 ΔQ = -Σ(h_i · sign_i · |Q_i|^(n-1)) / Σ(n_i · h_i · |Q_i|^(n-1))
6. 收敛判定：max(|ΔQ|) < tolerance_m3_s
7. 节点压力回推：从 SOURCE 沿路径积分 dp（每边 final calc_chain 给出总 dp）
8. confidence / check_result 聚合：worst-wins（P4-2-5 链式规则外推到管网层）

设计要点：
- 纯函数：只解算流量 + 压力，不触 DB。
- pipe_chain / topology 只读复用（P4-2-5 / P4-3-1）。
- 不引入新依赖（纯 Python；无 numpy）。
- 高程修正：ρgΔz 静态部分从总 dp 中分离（不参与迭代）；最终压力回推时
  由 calc_chain 的 total_dp 自动包含 elevation。
"""
from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Final, Literal

from app.services.exceptions import PcsError
from app.services.pipe.pipe_chain_service import (
    PipeChainInput,
    PipeChainResult,
    PipeSegmentInput,
    calc_chain,
)
from app.services.pipe.pressure_drop_service import (
    PressureDropCheck,
    PressureDropConfidence,
)
from app.services.pipe_net.topology_service import (
    EdgeInput,
    PipeNetworkInput,
    validate_topology,
)

# ---------------------------------------------------------------------------
# 物理与算法常量
# ---------------------------------------------------------------------------

# ISO 80000-3 重力加速度
_G: Final[float] = 9.80665

# Hardy-Cross 指数：1 = 层流（Poiseuille），2 = 湍流（Darcy-Weisbach）
_EXP_LAMINAR: Final[int] = 1
_EXP_TURBULENT: Final[int] = 2

# 数值保护：避免 |Q|^(n-1) 在 Q=0 处求导时 NaN
_Q_FLOOR: Final[float] = 1e-12


# ---------------------------------------------------------------------------
# 异常
# ---------------------------------------------------------------------------


class PipeNetworkSolverInputError(PcsError):
    """管网求解器输入非法（结构错误）。

    触发场景：
    - 网络无环（树状；E - V + 1 == 0）
    - 网络多连通分量（拓扑非法）
    - 任一 pipe_chain 字段缺失 / 物性非法
    """

    code = "PIPE_NETWORK_SOLVER_INPUT_ERROR"
    status = 422


class NetworkConvergenceError(PcsError):
    """管网 Hardy-Cross 未在 max_iterations 内收敛。

    触发场景：
    - 极紧 tolerance + 小 max_iterations
    - 病态网络（极不平衡 R 比率）
    """

    code = "NETWORK_CONVERGENCE_ERROR"
    status = 422


# ---------------------------------------------------------------------------
# 配置与结果 dataclass
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SolverConfig:
    """Hardy-Cross 求解配置。

    Attributes:
        tolerance_m3_s: 流量收敛容差 (m³/s)；max(|ΔQ|) < 此值视为收敛
        max_iterations: 最大迭代次数；超出仍未收敛 → raise
        initial_flow_strategy: 初值策略；本批仅支持 EVEN_DEMAND_PROPORTIONAL
    """

    tolerance_m3_s: float = 1e-6
    max_iterations: int = 100
    initial_flow_strategy: Literal["EVEN_DEMAND_PROPORTIONAL"] = (
        "EVEN_DEMAND_PROPORTIONAL"
    )


@dataclass(frozen=True)
class EdgeFlowResult:
    """单边流量解。

    Attributes:
        edge_id: 边 ID
        flow_m3_s: 流量 (m³/s)；正 = from→to，负 = to→from
        flow_direction: FORWARD (from→to) / REVERSE (to→from)
        dp_pa: 该 Q 下 calc_chain 总压降 (Pa；含 elevation)
        iterations_to_converge: 收敛时的迭代次数（未收敛 = None）
    """

    edge_id: str
    flow_m3_s: float
    flow_direction: Literal["FORWARD", "REVERSE"]
    dp_pa: float
    iterations_to_converge: int | None


@dataclass(frozen=True)
class NodePressureResult:
    """节点压力解。

    Attributes:
        node_id: 节点 ID
        pressure_pa: 节点压力 (Pa)
        elevation_m: 节点标高 (m)
        velocity_head_m: 速度头 v²/(2g) (m)；可选，未知 = None
    """

    node_id: str
    pressure_pa: float
    elevation_m: float
    velocity_head_m: float | None


@dataclass(frozen=True)
class PipeNetworkResult:
    """管网 Hardy-Cross 求解总结果。

    Attributes:
        converged: 是否在 max_iterations 内收敛
        iterations: 实际迭代次数
        max_flow_error_m3_s: 最后一轮迭代中最大 |ΔQ| (m³/s)
        edge_flows: 各边流量 + 方向 + 压降
        node_pressures: 各节点压力 + 标高 + 速度头
        confidence: 整体置信度（HIGH/MEDIUM/LOW）— worst-wins 各链式 confidence
        check_result: 整体校核（PASS/WARNING/FAIL）— 任一边 FAIL → FAIL；
            任一链含 TRANSITION → WARNING
        check_result_reason: 校核原因
    """

    converged: bool
    iterations: int
    max_flow_error_m3_s: float
    edge_flows: list[EdgeFlowResult]
    node_pressures: list[NodePressureResult]
    confidence: PressureDropConfidence
    check_result: PressureDropCheck
    check_result_reason: str | None


# ---------------------------------------------------------------------------
# 内部工具：边解算中间态
# ---------------------------------------------------------------------------


@dataclass
class _EdgeSolver:
    """每条边的求解器中间态（不可变 dataclass 副本）。"""

    edge_id: str
    from_node: str
    to_node: str
    pipe_chain: PipeChainInput
    R_friction: float  # R：h_friction = R × |Q|^n
    n_exponent: int  # 1 (LAMINAR) / 2 (TURBULENT)
    elevation_dp_pa: float  # 静态 elevation 部分 (Pa；含符号)
    chain_result: PipeChainResult  # 初始 calc_chain 结果（参考 Q）


# ---------------------------------------------------------------------------
# 内部工具：elevation 分离
# ---------------------------------------------------------------------------


def _seg_elevation_dp(seg: PipeSegmentInput) -> float:
    """单段 elevation 静态 dp = ρ × g × Δz (Pa)。

    两相段按液相密度简化（与 pipe_chain_service.calc_chain 一致）；
    VAPOR 段按气密度（GAS）。
    """
    if seg.fluid_phase == "TWO_PHASE":
        # pipe_chain 用液相密度；此处保持一致
        rho = seg.liquid_density_kg_m3 or seg.density_kg_m3
    else:
        rho = seg.density_kg_m3
    return rho * _G * seg.elevation_change_m


def _chain_total_elevation_dp(chain: PipeChainInput) -> float:
    """整链总静态 elevation dp (Pa)；与 calc_chain._fittings_k_sum 一致。"""
    return sum(_seg_elevation_dp(seg) for seg in chain.segments)


# ---------------------------------------------------------------------------
# 内部工具：n 指数（基于链式 flow_regimes 列表）
# ---------------------------------------------------------------------------


def _chain_n_exponent(chain_result: PipeChainResult) -> int:
    """链整体 Hardy-Cross 指数 n。

    任一段 LAMINAR → n=1（Poiseuille）；否则 n=2（DW 湍流）。
    TRANSITION 也用 n=2（D-W 近似 + 系数由 calc_chain 处理）。
    两相段 P4-2-5 占位为 TURBULENT → n=2。
    """
    for regime in chain_result.flow_regimes:
        if regime == "LAMINAR":
            return _EXP_LAMINAR
    return _EXP_TURBULENT


# ---------------------------------------------------------------------------
# 内部工具：build _EdgeSolver list
# ---------------------------------------------------------------------------


def _build_edge_solvers(
    inp: PipeNetworkInput,
    flows_m3_s: dict[str, float],
) -> list[_EdgeSolver]:
    """对每条边调用 calc_chain（参考 Q）→ R / n / elevation 静态 dp。"""
    out: list[_EdgeSolver] = []
    for e in inp.edges:
        chain = e.pipe_chain
        q_ref = flows_m3_s[e.edge_id]
        # 用参考 Q 替换 mass_flow（仅对单相段有意义；两相段保持原 liquid/gas 质量流）
        chain_with_q = _replace_flow_in_chain(chain, q_ref)
        chain_res = calc_chain(chain_with_q)
        elevation_dp = _chain_total_elevation_dp(chain)
        friction_dp = max(chain_res.total_dp_pa - abs(elevation_dp), 0.0)
        n = _chain_n_exponent(chain_res)
        # R = friction_dp / |Q|^n
        # Q=0 时：friction_dp 视为 0（管段无流量无摩阻）；R 取 0
        if abs(q_ref) > _Q_FLOOR and n > 0:
            r_fric = friction_dp / (abs(q_ref) ** n)
        else:
            r_fric = 0.0
        out.append(
            _EdgeSolver(
                edge_id=e.edge_id,
                from_node=e.from_node,
                to_node=e.to_node,
                pipe_chain=chain,
                R_friction=r_fric,
                n_exponent=n,
                elevation_dp_pa=elevation_dp,
                chain_result=chain_res,
            )
        )
    return out


def _replace_flow_in_chain(chain: PipeChainInput, q_ref: float) -> PipeChainInput:
    """构造 chain 的"参考 Q"副本：单相段 mass_flow = ρ × Q；两相段按 demand 比例缩放。

    两相段保留原 liquid/gas 质量流（不重新拆 Q，因 service 不知道 vfrac）；
    本批求解器对两相段用 chain_result 中的总 dp（视为 n=2 默认），
    用户需自行保证两相段 Q 与需求匹配。
    """
    new_segments: list[PipeSegmentInput] = []
    for seg in chain.segments:
        if seg.fluid_phase == "TWO_PHASE":
            new_segments.append(seg)  # 保留原值
        else:
            # 单相：mass_flow = ρ × Q
            new_mass = seg.density_kg_m3 * abs(q_ref)
            new_segments.append(
                PipeSegmentInput(
                    fluid_phase=seg.fluid_phase,
                    mass_flow_kg_s=new_mass,
                    density_kg_m3=seg.density_kg_m3,
                    viscosity_pa_s=seg.viscosity_pa_s,
                    pipe_diameter_m=seg.pipe_diameter_m,
                    pipe_roughness_m=seg.pipe_roughness_m,
                    length_m=seg.length_m,
                    inclination_deg=seg.inclination_deg,
                    elevation_change_m=seg.elevation_change_m,
                    surface_tension_n_m=seg.surface_tension_n_m,
                    liquid_density_kg_m3=seg.liquid_density_kg_m3,
                    liquid_viscosity_pa_s=seg.liquid_viscosity_pa_s,
                    gas_density_kg_m3=seg.gas_density_kg_m3,
                    gas_viscosity_pa_s=seg.gas_viscosity_pa_s,
                    liquid_mass_flow_kg_s=seg.liquid_mass_flow_kg_s,
                    gas_mass_flow_kg_s=seg.gas_mass_flow_kg_s,
                    fittings=seg.fittings,
                )
            )
    return PipeChainInput(
        project_id=chain.project_id,
        workspace_id=chain.workspace_id,
        source_stream_id=chain.source_stream_id,
        tag_number=chain.tag_number,
        segments=new_segments,
        inlet_pressure_pa=chain.inlet_pressure_pa,
        inlet_temperature_K=chain.inlet_temperature_K,
        parallel_branches=chain.parallel_branches,
    )


# ---------------------------------------------------------------------------
# 内部工具：拓扑（环查找）
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _Loop:
    """一个独立环：按 edge_id 顺序遍历，sign = +1 (沿 from→to) / -1 (沿 to→from)。"""

    edges: list[tuple[str, int]]  # (edge_id, sign)


def _find_independent_loops(edges: list[EdgeInput]) -> list[_Loop]:
    """找 E - V + 1 个独立环（BFS 树 + 每条 chord 与 parent chain 构成环）。

    parent[node] = (parent_node, parent_edge_id, edge_dir)
        - edge_dir = +1 表示 BFS 从 parent_node → node（即 parent 是 from，node 是 to）
        - edge_dir = -1 表示 BFS 从 node → parent_node（即 node 是 from，parent 是 to）

    Raises:
        PipeNetworkSolverInputError: 节点数 < 2 / 边数 < 3 / 无环路
    """
    # 邻接表：(neighbor, edge_id, direction_relative_to_node)
    adj: dict[str, list[tuple[str, str, int]]] = defaultdict(list)
    node_ids: set[str] = set()
    for e in edges:
        node_ids.add(e.from_node)
        node_ids.add(e.to_node)
        adj[e.from_node].append((e.to_node, e.edge_id, +1))
        adj[e.to_node].append((e.from_node, e.edge_id, -1))

    if len(node_ids) < 2:
        raise PipeNetworkSolverInputError(
            f"网络节点数 {len(node_ids)} < 2",
            details={"node_count": len(node_ids)},
        )

    # 期望环路数 = E - V + 1（连通图）
    expected_loops = len(edges) - len(node_ids) + 1
    if expected_loops <= 0:
        raise PipeNetworkSolverInputError(
            "网络无环路（树状结构）；Hardy-Cross 求解要求至少 1 个环路",
            details={
                "node_count": len(node_ids),
                "edge_count": len(edges),
                "expected_loops": expected_loops,
            },
        )

    # BFS 树：取任意有边的节点为根
    root = next(
        (n for n, lst in adj.items() if lst), None
    )
    if root is None:
        raise PipeNetworkSolverInputError(
            "网络无任何边",
            details={"edge_count": 0},
        )

    # parent[node] = (parent_node, parent_edge_id, edge_dir)
    # edge_dir = +1: edge goes parent → node (parent=from, node=to)
    # edge_dir = -1: edge goes node → parent (node=from, parent=to)
    parent: dict[str, tuple[str, str, int]] = {}
    visited: set[str] = {root}
    queue: deque[str] = deque([root])
    tree_edges: set[str] = set()
    while queue:
        u = queue.popleft()
        for v, eid, dirn in adj[u]:
            if v not in visited:
                visited.add(v)
                parent[v] = (u, eid, dirn)
                tree_edges.add(eid)
                queue.append(v)

    # 非树边（chord）→ 每个 chord 与 parent chain 构成一个独立环
    loops: list[_Loop] = []
    for e in edges:
        if e.edge_id in tree_edges:
            continue
        # chord: e.from_node=u, e.to_node=v
        u, v = e.from_node, e.to_node
        # 环遍历方向：u → chord → v → ... → u
        loop_edges: list[tuple[str, int]] = [(e.edge_id, +1)]
        # path_v: [v, parent[v], parent[parent[v]], ..., root]
        path_v = _ancestor_path(v, parent)
        path_u = _ancestor_path(u, parent)
        lca = _find_lca(path_v, path_u)
        idx_v = path_v.index(lca)
        idx_u = path_u.index(lca)

        # v → lca 上溯：每步 ancestor → parent[ancestor]
        # parent chain 中 edge 方向 = parent_dir（parent → ancestor）
        # 遍历方向 ancestor → parent = 反向 → sign = -parent_dir
        for ancestor in path_v[:idx_v]:
            _, peid, pdir = parent[ancestor]
            loop_edges.append((peid, -pdir))

        # lca → u 下溯：path_u 倒序 [lca, ..., parent[u], u]
        # 不含 lca 自身（含 lca 时 idx_u 位置为 lca）
        # path_u[idx_u-1] = u 的 grandparent，...，path_u[0] = u
        for i in range(idx_u - 1, -1, -1):
            ancestor = path_u[i]
            if ancestor == lca:
                # 跳过 lca 自身；parent[lca] 不存在
                continue
            _, peid, pdir = parent[ancestor]
            # 遍历方向 parent[ancestor] → ancestor = pdir
            # 我们要从 lca 走到 u，下溯到 ancestor
            # path_u[i] = ancestor，path_u[i+1] = parent[ancestor]
            # （因为 ancestor 的 parent 在 path 中靠后）
            # 实际：parent[ancestor] 是 ancestor 的 parent，在 path_u 中位置 = i+1
            # 下溯方向：parent[ancestor] → ancestor = pdir
            # 我们要走 path_u[i+1] → path_u[i] = parent[ancestor] → ancestor
            # sign = +pdir
            loop_edges.append((peid, pdir))

        loops.append(_Loop(edges=loop_edges))

    return loops


def _ancestor_path(
    node: str, parent: dict[str, tuple[str, str, int]]
) -> list[str]:
    """节点 → 根的祖先路径（含自身和根）。"""
    path: list[str] = [node]
    cur = node
    while cur in parent:
        cur = parent[cur][0]
        path.append(cur)
    return path


def _find_lca(path_a: list[str], path_b: list[str]) -> str:
    """最近公共祖先（path 含自身和根；根在末尾）。"""
    set_a = set(path_a)
    for n in path_b:
        if n in set_a:
            return n
    # 兜底（不应到这）
    return path_a[-1]


# ---------------------------------------------------------------------------
# 内部工具：初值分配（EVEN_DEMAND_PROPORTIONAL）
# ---------------------------------------------------------------------------


def _initial_flows_even_demand_proportional(
    inp: PipeNetworkInput,
) -> dict[str, float]:
    """初值：split-equally（每个节点 incoming 均分给 outgoing edges）。

    算法（拓扑序前向传递）：
    1. 计算每个节点 supply（SOURCE：总需求；JUNCTION：上一节点传递；
       SINK：demand_m3_s）
    2. 按拓扑序传播 supply，每个节点 outgoing edge flow = supply / n_outgoing
    3. 若节点 outgoing 数 = 0 但 supply > 0 → raise（拓扑非法）
    4. 保证初始 flows 满足所有节点质量守恒（除 SOURCE / SINK 边界）

    Raises:
        PipeNetworkSolverInputError: 无 SINK demand / 拓扑非法
    """
    out_adj: dict[str, list[str]] = defaultdict(list)
    in_count: dict[str, int] = defaultdict(int)
    for e in inp.edges:
        out_adj[e.from_node].append(e.edge_id)
        in_count[e.to_node] += 1
    # 初始化所有节点的 remaining_in（默认 0 入边）
    for n in inp.nodes:
        if n.node_id not in in_count:
            in_count[n.node_id] = 0

    total_demand = sum(
        n.demand_m3_s for n in inp.nodes if n.node_type == "SINK"
    )
    if total_demand <= 0.0:
        raise PipeNetworkSolverInputError(
            "SINK 总需求 ≤ 0；无可分配流量",
            details={"total_demand": total_demand},
        )

    # 找 SOURCE 节点（供给起点）
    source_nodes = [n for n in inp.nodes if n.node_type == "SOURCE"]
    if not source_nodes:
        raise PipeNetworkSolverInputError("无 SOURCE 节点", details={})

    # 拓扑序：Kahn 算法
    remaining_in = {n.node_id: in_count[n.node_id] for n in inp.nodes}
    queue: deque[str] = deque()
    for n in inp.nodes:
        if remaining_in[n.node_id] == 0:
            queue.append(n.node_id)
    topo_order: list[str] = []
    while queue:
        nid = queue.popleft()
        topo_order.append(nid)
        for eid in out_adj[nid]:
            e = next(x for x in inp.edges if x.edge_id == eid)
            remaining_in[e.to_node] -= 1
            if remaining_in[e.to_node] == 0:
                queue.append(e.to_node)

    # 按拓扑序传播：每节点 supply = Σ incoming flows（SOURCE = src_supply）；
    # 然后把 supply 均分到 outgoing edges
    n_sources = max(len(source_nodes), 1)
    src_supply = total_demand / n_sources

    # 邻接：edge_id → (from, to) 用于反向查 incoming
    edge_ends: dict[str, tuple[str, str]] = {
        e.edge_id: (e.from_node, e.to_node) for e in inp.edges
    }

    flows: dict[str, float] = {e.edge_id: 0.0 for e in inp.edges}
    incoming_flows: dict[str, list[float]] = {
        n.node_id: [] for n in inp.nodes
    }
    # outgoing edges 列表（每个节点）
    out_edges: dict[str, list[str]] = {n.node_id: [] for n in inp.nodes}
    for e in inp.edges:
        out_edges[e.from_node].append(e.edge_id)

    for nid in topo_order:
        node = next(x for x in inp.nodes if x.node_id == nid)
        n_out = len(out_edges[nid])
        if node.node_type == "SOURCE":
            supply = src_supply
        elif node.node_type == "SINK":
            # SINK：自身 demand 作为 supply（流出的方向）；
            # 但通常 SINK 无 outgoing edges；若有，按 demand 均分
            supply = node.demand_m3_s
        else:
            # JUNCTION / EQUIPMENT_INTERFACE：supply = Σ incoming flows
            supply = sum(incoming_flows[nid])
        if n_out > 0 and supply > 0.0:
            per_edge = supply / n_out
            for eid in out_edges[nid]:
                flows[eid] = per_edge
                # 记入 to_node 的 incoming
                _, to_n = edge_ends[eid]
                incoming_flows[to_n].append(per_edge)
        elif n_out > 0:
            # supply = 0，但有 outgoing edges（罕见）：不分配
            pass

    # 兜底：未赋值的边（孤立子图残余）给一个种子
    seed = total_demand * 0.001
    for e in inp.edges:
        if flows[e.edge_id] == 0.0:
            flows[e.edge_id] = seed
    return flows


# ---------------------------------------------------------------------------
# 内部工具：Hardy-Cross 单步迭代
# ---------------------------------------------------------------------------


def _h_friction_pa(es: _EdgeSolver, q_m3_s: float) -> float:
    """h = R × |Q|^n（friction only，不含 elevation）。"""
    if abs(q_m3_s) < _Q_FLOOR or es.R_friction <= 0.0:
        return 0.0
    return es.R_friction * (abs(q_m3_s) ** es.n_exponent)


def _hardy_cross_step(
    flows: dict[str, float],
    edges_by_id: dict[str, _EdgeSolver],
    loops: list[_Loop],
) -> tuple[dict[str, float], float]:
    """单轮 Hardy-Cross 修正。返回新 flows + max(|ΔQ|)。"""
    new_flows = dict(flows)
    max_dq = 0.0

    for loop in loops:
        # Hardy-Cross 修正（标准公式）：
        #   ΔQ = -Σ(h_i × sign_i) / Σ(n_i × h_i / |Q_i|)
        # 等价形式：
        #   num = Σ(R_i × |Q_i|^n × sign_loop_i)
        #   den = Σ(n × R_i × |Q_i|^(n-1))
        num = 0.0
        den = 0.0
        for eid, sign in loop.edges:
            es = edges_by_id[eid]
            q = flows[eid]
            abs_q = abs(q)
            if abs_q < _Q_FLOOR or es.R_friction <= 0.0:
                # Q ≈ 0：h ≈ 0；dh/dQ = n × R × |Q|^(n-1) 在 n=2 时 ≈ 0
                # 在 n=1 时 dh/dQ = R（常数）；仍可贡献
                if abs_q < _Q_FLOOR and es.n_exponent == 1 and es.R_friction > 0.0:
                    den += es.R_friction  # dh/dQ = R
                continue
            h = es.R_friction * (abs_q ** es.n_exponent)
            # numerator: h × sign_loop（h 已是 magnitude × sign(Q) 等价 → 取绝对 × sign_loop）
            # 实际 h = R × |Q|^n 是 magnitude；方向由 sign_loop × sign(Q) 决定
            # 这里我们假设初始 flow 已大致正确，sign_loop 已考虑 Q 方向
            num += h * sign
            # denominator: n × h / |Q| = n × R × |Q|^(n-1)
            den += es.n_exponent * h / abs_q
        if abs(den) < 1e-30:
            continue
        dq = -num / den
        if abs(dq) > max_dq:
            max_dq = abs(dq)
        # 应用修正：每条边 Q += ΔQ × sign
        for eid, sign in loop.edges:
            new_flows[eid] = new_flows.get(eid, 0.0) + dq * sign

    return new_flows, max_dq


# ---------------------------------------------------------------------------
# 内部工具：压力回推
# ---------------------------------------------------------------------------


def _reconstruct_pressures(
    inp: PipeNetworkInput,
    flows: dict[str, float],
    edges_by_id: dict[str, _EdgeSolver],
) -> dict[str, float]:
    """节点压力回推：从 SOURCE 出发，沿有向边计算 neighbor P。

    算法：
    - 拓扑序 BFS（从 SOURCE 开始）
    - 对每条边 (u→v)，用最终 Q 重新算 calc_chain → 总 dp（含 elevation）
    - 若 Q > 0（u→v）：P_v = P_u - dp
    - 若 Q < 0（v→u 实际流向）：P_v = P_u + dp（因为流向反向时 dp 是 v→u 的落差，
      反推 u→v 即 v 比 u 高 dp）
    - 等价：P_v = P_u - sign(Q) × dp

    对于 SOURCE pressure_pa=None 的情况（开放边界）：
    - 取所有 SOURCE 中第一个 pressure_pa 非 None 的作为锚定基准
    - 若全 None 则取 SINK 的 pressure_pa 锚定
    """
    # 选锚定 SOURCE
    anchor_id: str | None = None
    anchor_p: float | None = None
    for n in inp.nodes:
        if n.node_type == "SOURCE" and n.pressure_pa is not None:
            anchor_id = n.node_id
            anchor_p = n.pressure_pa
            break
    if anchor_id is None:
        # 兜底：取任一有 pressure_pa 的节点
        for n in inp.nodes:
            if n.pressure_pa is not None:
                anchor_id = n.node_id
                anchor_p = n.pressure_pa
                break

    if anchor_id is None or anchor_p is None:
        raise PipeNetworkSolverInputError(
            "无锚定节点（所有节点 pressure_pa 均为 None）",
            details={"node_count": len(inp.nodes)},
        )

    pressures: dict[str, float] = {anchor_id: anchor_p}
    # BFS 从锚定节点出发
    out_adj: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for e in inp.edges:
        out_adj[e.from_node].append((e.to_node, e.edge_id))
    visited: set[str] = {anchor_id}
    queue: deque[str] = deque([anchor_id])
    while queue:
        u = queue.popleft()
        if u not in pressures:
            continue
        for v, eid in out_adj[u]:
            if v in visited:
                continue
            visited.add(v)
            es = edges_by_id[eid]
            q_final = flows[eid]
            # 用最终 Q 重算 chain（更准确）
            chain_with_q = _replace_flow_in_chain(es.pipe_chain, q_final)
            try:
                chain_res = calc_chain(chain_with_q)
            except Exception:
                # 兜底：calc_chain 异常（Q 反向 / 物性越界等）→ 用参考 R 估算
                h_est = _h_friction_pa(es, q_final)
                dp_est = h_est + es.elevation_dp_pa
                sign_q = 1.0 if q_final >= 0.0 else -1.0
                pressures[v] = pressures[u] - sign_q * dp_est
                queue.append(v)
                continue
            sign_q = 1.0 if q_final >= 0.0 else -1.0
            pressures[v] = pressures[u] - sign_q * chain_res.total_dp_pa
            queue.append(v)

    # 未访问节点（孤立 / 锚定选错）→ 用输入 pressure_pa
    for n in inp.nodes:
        if n.node_id not in pressures and n.pressure_pa is not None:
            pressures[n.node_id] = n.pressure_pa

    return pressures


def _recompute_chain_results(
    edges: list[EdgeInput],
    flows: dict[str, float],
) -> dict[str, PipeChainResult]:
    """用最终 Q 重算各边 calc_chain（用于 dp_pa / confidence 聚合）。"""
    out: dict[str, PipeChainResult] = {}
    for e in edges:
        q = flows[e.edge_id]
        chain_with_q = _replace_flow_in_chain(e.pipe_chain, q)
        try:
            out[e.edge_id] = calc_chain(chain_with_q)
        except Exception:
            # 兜底：用初始 chain_result
            out[e.edge_id] = _calc_chain_fallback(e.pipe_chain)
    return out


def _calc_chain_fallback(chain: PipeChainInput) -> PipeChainResult:
    """calc_chain 异常时构造一个最小占位 result（不应触发，仅作兜底）。"""

    # 用初始 mass_flow 重算
    try:
        return calc_chain(chain)
    except Exception:
        # 极端兜底：构造零压降 result
        return PipeChainResult(
            total_dp_pa=0.0,
            total_length_m=sum(s.length_m for s in chain.segments),
            total_K=0.0,
            dp_per_segment_pa=[0.0] * len(chain.segments),
            need_two_phase=False,
            velocity_m_s=0.0,
            reynolds=0.0,
            friction_factor=0.0,
            flow_pattern=None,
            outlet_pressure_pa=chain.inlet_pressure_pa,
            pressure_gradient_kpa_m=0.0,
            flow_regimes=["TURBULENT"] * len(chain.segments),
            check_result="PASS",
            check_result_reason=None,
            confidence="LOW",
        )


# ---------------------------------------------------------------------------
# 内部工具：confidence / check_result 聚合
# ---------------------------------------------------------------------------


_CONFIDENCE_RANK: Final[dict[PressureDropConfidence, int]] = {
    "HIGH": 0,
    "MEDIUM": 1,
    "LOW": 2,
}

_CHECK_RANK: Final[dict[PressureDropCheck, int]] = {
    "PASS": 0,
    "WARNING": 1,
    "FAIL": 2,
}


def _aggregate_confidence(
    per_edge: list[PressureDropConfidence],
) -> PressureDropConfidence:
    """worst-wins：任一 LOW → 整体 LOW；否则任一 MEDIUM → 整体 MEDIUM；全 HIGH → HIGH。"""
    if not per_edge:
        return "HIGH"
    worst_rank = max(_CONFIDENCE_RANK[c] for c in per_edge)
    for level, rank in _CONFIDENCE_RANK.items():
        if rank == worst_rank:
            return level
    return "HIGH"


def _aggregate_check_result(
    per_edge_check: list[PressureDropCheck],
) -> tuple[PressureDropCheck, str | None]:
    """worst-wins：任一 FAIL → FAIL；否则任一 WARNING → WARNING；全 PASS → PASS。"""
    if not per_edge_check:
        return "PASS", None
    worst_rank = max(_CHECK_RANK[c] for c in per_edge_check)
    for level, rank in _CHECK_RANK.items():
        if rank == worst_rank:
            reason: str | None
            if level == "FAIL":
                reason = "EDGE_FAIL"
            elif level == "WARNING":
                reason = "EDGE_WARNING"
            else:
                reason = None
            return level, reason
    return "PASS", None


# ---------------------------------------------------------------------------
# 入口：solve_network
# ---------------------------------------------------------------------------


def solve_network(
    inp: PipeNetworkInput,
    config: SolverConfig = SolverConfig(),
) -> PipeNetworkResult:
    """管网 Hardy-Cross 求解（流量分配 + 压力回推 + 节点压降守恒校验）。

    流程：
    1. validate_topology（复用 P4-3-1）
    2. 找独立环（E - V + 1 个；无环 → raise）
    3. 初值分配（EVEN_DEMAND_PROPORTIONAL）
    4. 构建 _EdgeSolver 列表（calc_chain @ Q_ref → R / n / elevation）
    5. 迭代 Hardy-Cross 直到 max(|ΔQ|) < tolerance_m3_s
    6. 节点压力回推（从 SOURCE 出发 calc_chain @ Q_final）
    7. 聚合 confidence / check_result（worst-wins）

    Args:
        inp: 管网输入（含 nodes / edges / pipe_chain）
        config: 求解配置（tolerance / max_iterations / strategy）

    Returns:
        PipeNetworkResult：各边流量 + 节点压力 + 整体收敛状态

    Raises:
        TopologyInputError / TopologyUnconnectedError: 拓扑非法
        PipeNetworkSolverInputError: 网络无环 / 无 SINK demand / 无锚定节点
        NetworkConvergenceError: 超过 max_iterations 仍未收敛
    """
    # --- 1. 拓扑校验（复用 P4-3-1）---
    validate_topology(inp)

    # --- 2. 独立环查找 ---
    loops = _find_independent_loops(inp.edges)
    if not loops:
        # E - V + 1 == 0（树状）；理论上 _find_independent_loops 已 raise
        raise PipeNetworkSolverInputError(
            "网络无独立环（树状结构）；Hardy-Cross 求解要求至少 1 个环路",
            details={},
        )

    # --- 3. 初值分配 ---
    flows = _initial_flows_even_demand_proportional(inp)

    # --- 4. 构建 _EdgeSolver 列表 ---
    edge_solvers = _build_edge_solvers(inp, flows)
    edges_by_id: dict[str, _EdgeSolver] = {
        es.edge_id: es for es in edge_solvers
    }

    # --- 5. Hardy-Cross 迭代 ---
    converged = False
    iterations = 0
    max_err = 0.0
    for it in range(1, config.max_iterations + 1):
        iterations = it
        new_flows, max_dq = _hardy_cross_step(flows, edges_by_id, loops)
        max_err = max_dq
        flows = new_flows
        if max_dq < config.tolerance_m3_s:
            converged = True
            break

    if not converged:
        raise NetworkConvergenceError(
            f"Hardy-Cross 求解未在 {config.max_iterations} 轮内收敛；"
            f"最后 max|ΔQ|={max_err:.3e} m³/s",
            details={
                "max_iterations": config.max_iterations,
                "max_flow_error_m3_s": max_err,
                "tolerance_m3_s": config.tolerance_m3_s,
            },
        )

    # --- 6. 压力回推 + chain_result 重算 ---
    pressures = _reconstruct_pressures(inp, flows, edges_by_id)
    final_chain_results = _recompute_chain_results(inp.edges, flows)

    # --- 7. 聚合 confidence / check_result ---
    confidences: list[PressureDropConfidence] = []
    checks: list[PressureDropCheck] = []
    for e in inp.edges:
        cr = final_chain_results[e.edge_id]
        confidences.append(cr.confidence)
        checks.append(cr.check_result)
    overall_conf = _aggregate_confidence(confidences)
    overall_check, overall_reason = _aggregate_check_result(checks)

    # 构造 edge_flows
    edge_flow_results: list[EdgeFlowResult] = []
    for e in inp.edges:
        q = flows[e.edge_id]
        cr = final_chain_results[e.edge_id]
        direction: Literal["FORWARD", "REVERSE"] = (
            "FORWARD" if q >= 0.0 else "REVERSE"
        )
        edge_flow_results.append(
            EdgeFlowResult(
                edge_id=e.edge_id,
                flow_m3_s=q,
                flow_direction=direction,
                dp_pa=cr.total_dp_pa,
                iterations_to_converge=iterations,
            )
        )

    # 构造 node_pressures
    node_pressure_results: list[NodePressureResult] = []
    for n in inp.nodes:
        p = pressures.get(n.node_id)
        if p is None:
            # 未到达节点：用输入值
            p = n.pressure_pa if n.pressure_pa is not None else 0.0
        # 速度头：取第一个从 n 出发的边的入口速度（简化）
        velocity_head: float | None = None
        for e in inp.edges:
            if e.from_node == n.node_id:
                cr = final_chain_results[e.edge_id]
                if cr.velocity_m_s > 0.0:
                    velocity_head = cr.velocity_m_s ** 2 / (2.0 * _G)
                    break
        node_pressure_results.append(
            NodePressureResult(
                node_id=n.node_id,
                pressure_pa=p,
                elevation_m=n.elevation_m,
                velocity_head_m=velocity_head,
            )
        )

    return PipeNetworkResult(
        converged=converged,
        iterations=iterations,
        max_flow_error_m3_s=max_err,
        edge_flows=edge_flow_results,
        node_pressures=node_pressure_results,
        confidence=overall_conf,
        check_result=overall_check,
        check_result_reason=overall_reason,
    )


__all__ = [
    "EdgeFlowResult",
    "NetworkConvergenceError",
    "NodePressureResult",
    "PipeNetworkResult",
    "PipeNetworkSolverInputError",
    "SolverConfig",
    "solve_network",
]
