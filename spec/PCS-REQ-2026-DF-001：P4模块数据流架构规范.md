PCS-REQ-2026-DF-001：P4模块数据流架构规范
文件标识	PCS-REQ-2026-DF-001
当前版本	V1.1
发布日期	2026-09-01（V1.1 修订 2026-09-03，对齐 PCS 本体论 V1.6 §5.1 / §5.2 / §7 DF-001 数据流约束）
编制部门	工艺部 / 信息化联合项目组
适用对象	内部开发团队（后端/前端/测试）、工艺部全体用户代表
关联文档	PCS-DICT-ALL-003 V3.3、PCS-DICT-011、SPEC-P1 V1.3、SPEC-P4、ADR-0005/0022、**PCS 本体论与语义关系研究说明（V1.6）§5.1 / §5.2 / §7**
1. 目的
定义P4阶段四个核心计算模块（FLASH/PIPE/PUMP/PIPE_NET）之间的数据流架构、引用规范、血缘写入规则和开发顺序。确保每个模块只做自己的计算职责，物性和压降数据不重复计算，全部通过引用上游已CHECKED的结果获得。

核心原则：

PIPE不计算物性——物性来自Streams。PUMP不计算压降——压降来自PipingResults。PIPE_NET不计算单管压降——管段特性来自PipingResults。FLASH是物性缺失时的唯一补充来源。

2. 模块间数据流图
text
┌─────────────────────────────────────────────────────────────────┐
│                    P4 模块间数据流                               │
└─────────────────────────────────────────────────────────────────┘

  FLASH（闪蒸/物性计算）
    │ 输出：焓/熵/汽化分率/气液相组成 → 补充到Streams
    ▼
  Streams（物流表——物性唯一数据源）
    │ 提供：T/P/密度/粘度/分子量/组成/相态/气液组成
    │
    ├──► PIPE（单管压降计算）
    │        │ 输入：stream_id + 管道参数（DN/Sch/长度/管件）
    │        │ 输出：压降/流速/流型 → PipingResults
    │        │
    │        ├──► PUMP（泵计算）
    │        │        │ 输入：stream_id + 吸入/排出侧PipingResults压降
    │        │        │ 输出：NPSHa/扬程/功率 → PumpResults
    │        │
    │        └──► PIPE_NET（管网水力计算）
    │                 │ 输入：多个PipingResults的管段阻力特性
    │                 │ 输出：流量分配/节点压力 → PipeNetworkResults
    │
    └──► FLASH再调用（若需要精确相态判定）
3. 数据引用规范
3.1 PIPE → Streams（物料属性引用）
数据项	来源表字段	引用方式	计算时快照
操作温度	streams.temp	FK → streams.stream_id	✅
操作压力	streams.press	同上	✅
密度	streams.density	同上	✅
动力粘度	streams.viscosity_dynamic	同上	✅
运动粘度	streams.viscosity_kinematic	同上	✅
分子量	streams.molecular_weight	同上	✅
相态	streams.phase	同上	✅
汽化分率	streams.vapor_fraction	同上	✅
气液组成	streams.vapor/liquid_composition_json	同上	✅
压缩因子	streams.compressibility_factor	同上	✅
比热容	streams.specific_heat	同上	✅
导热系数	streams.thermal_conductivity	同上	✅
约束：

PIPE计算不自行计算物性。所有物性从streams读取。

若streams中物性缺失（为NULL），由FLASH模块补充计算后写回streams（标记estimated=true），然后PIPE再读取。

PIPE计算结果（PipingResults）中保存计算时使用的物性快照，用于追溯。若Streams后续变更，CIA通过哈希不匹配检测，PipingResults标记STALE。

3.2 PIPE → PUMP（压降引用）
数据项	来源	引用方式
吸入侧压降	piping_results（吸入侧管线记录）	FK → pipe_id
排出侧压降	piping_results（排出侧管线记录）	FK → pipe_id
吸入侧管径/等效长度	同上	同上
排出侧管径/等效长度	同上	同上
约束：

PUMP不重新计算管道压降。压降数据从piping_results读取。

若管道尚未计算（无PipingResults），PUMP可临时估算（标记estimated=true），但正式提交（CHECKED）必须引用已CHECKED的PipingResults。

泵设计压力计算中使用的"最大吸入压力"必须基于吸入侧管道的上游容器设计压力，而非管道压降本身。

3.3 PIPE → PIPE_NET（管段特性引用）
数据项	来源	引用方式
各管段直径	piping_results.line_size	FK → pipe_id
各管段长度	拓扑JSON中引用	拓扑JSON中存储
各管段粗糙度	拓扑JSON中引用（默认0.046mm）	拓扑JSON中存储
各管段阻力特性	piping_results（K值/Darcy系数）	通过data_lineage关联
约束：

PIPE_NET不重复计算单管压降。它使用PIPE提供的管段阻力特性，只进行流量分配求解。

PIPE_NET的拓扑数据中包含每个管段的pipe_id引用，用于从PipingResults加载阻力特性。

4. 数据血缘写入规范
4.1 血缘写入矩阵
计算模块	source_type	source_id	target_type	target_id	dependency_type
FLASH	STREAM	stream_id	FLASH_RESULT	flash_id	CALCULATION
FLASH→Streams回写	FLASH_RESULT	flash_id	STREAM	stream_id	ESTIMATED
PIPE	STREAM	stream_id	PIPE_RESULT	pipe_id	CALCULATION
PUMP	STREAM	stream_id	PUMP_RESULT	pump_id	CALCULATION
PUMP	PIPE_RESULT	suction_pipe_id	PUMP_RESULT	pump_id	CALCULATION
PUMP	PIPE_RESULT	discharge_pipe_id	PUMP_RESULT	pump_id	CALCULATION
PIPE_NET	PIPE_RESULT（×N）	各pipe_id	PIPE_NETWORK_RESULT	net_id	CALCULATION
4.2 使用P1-MVP已交付的@lineage装饰器

> ⚠️ **装饰器扩展计划（P4 Task 0 执行）**
>
> 本节 `sources=[(param_name, source_type)]` 是 **P4 目标态语法**。
> P1-MVP 已实现的装饰器仅支持 `@lineage(sources=("USER",))` 抽象标签模式。
>
> P4 启动前必须扩展装饰器以支持：
> - `sources` 接受 `list[tuple[str, str]]`（参数名 → source_type 映射）
> - 新增 `target_type` 和 `dependency_type` 参数
> - 从 `kwargs` 按参数名提取 UUID，查询对应表获取 `record_hash`
> - 向后兼容：`tuple[str, ...]` 裸字符串仍可用
>
> 扩展后签名（目标态）：
> ```python
> def lineage(
>     *,
>     sources: tuple[str, ...] | list[tuple[str, str]] = (),  # 两种模式共存
>     target_type: str | None = None,       # P4 模式必填
>     dependency_type: str | None = None,   # P4 模式必填
>     summary: str | None = None,           # P1 模式保留
> ):
> ```
>
> 调用对比：
> ```python
> # P1 调用（现有 5 处测试不变）
> @lineage(sources=("USER",), summary="用户操作")
>
> # P4 调用（新语法）
> @lineage(
>     sources=[("stream_id", "STREAM")],
>     target_type="PIPE_RESULT",
>     dependency_type="CALCULATION",
> )
> ```


python
# PIPE计算——单依赖（stream）
@lineage(
    sources=[("stream_id", "STREAM")],
    target_type="PIPE_RESULT",
    dependency_type="CALCULATION",
)
async def calculate_pipe(db: AsyncSession, *, stream_id: UUID, ...) -> PipingResult:
    """PIPE计算：物性从streams读取，不自行计算。"""
    ...


# PUMP计算——三依赖（stream + 吸入侧pipe + 排出侧pipe）
@lineage(
    sources=[
        ("stream_id", "STREAM"),
        ("suction_pipe_id", "PIPE_RESULT"),
        ("discharge_pipe_id", "PIPE_RESULT"),
    ],
    target_type="PUMP_RESULT",
    dependency_type="CALCULATION",
)
async def calculate_pump(
    db: AsyncSession,
    *,
    stream_id: UUID,
    suction_pipe_id: UUID,
    discharge_pipe_id: UUID,
    ...
) -> PumpResult:
    """PUMP计算：压降从PipingResults读取，不重新计算。"""
    ...
5. 模块开发顺序
顺序	模块	前置依赖	交付物
1	FLASH	streams（P0已建表）；thermo/CoolProp库	物性计算+相态判定+Streams物性补充
2	PIPE	FLASH（物性补充）+ streams + PIPE_CLASS（P0已有）	管径+壁厚+压降+流速+流型
3	PUMP	PIPE（压降）+ streams（物性）	NPSHa+扬程+功率+设计压力+控制阀
4	PIPE_NET	PIPE（管段特性）	流量分配+节点压力
FLASH必须最先开发——它是所有物性数据的最终来源。

6. 数据字典变更
6.1 PipingResults新增字段（管道数据字典增补）
在PipingResults表（piping_results）的JSON字段中增加stream_reference子结构：

json
{
  "stream_reference": {
    "stream_id": null,
    "stream_name": "S-101",
    "density_kg_m3": null,
    "viscosity_cp": null,
    "molecular_weight": null,
    "phase": null,
    "is_estimated": true
  }
}
6.2 PumpResults新增字段（PCS-DICT-011增补）
在line_references子结构中增加压降引用：

json
{
  "line_references": {
    "suction_line_no": "TXPL-264",
    "discharge_line_no": "TXPL-1102 272",
    "suction_vessel_tag": "FV-TX-274",
    "discharge_vessel_tag": null,
    "suction_pipe_record_id": null,
    "discharge_pipe_record_id": null
  }
}
6.3 PipeNetworkResults新增字段（管网数据字典增补）
在topology_json中明确管段引用：

json
{
  "topology_json": {
    "nodes": [
      {"node_id": "N1", "label": "泵出口", "type": "JUNCTION"}
    ],
    "pipes": [
      {
        "pipe_record_id": null,
        "from_node": "N1",
        "to_node": "N2",
        "length_m": 100,
        "diameter_mm": 100,
        "roughness_mm": 0.046
      }
    ]
  }
}
关键变更：pipes数组中新增pipe_record_id字段，引用已CHECKED的PipingResults记录。若无已计算的管段，pipe_record_id为NULL，PIPE_NET使用拓扑中的基础参数进行初步估算（标记estimated=true）。

7. CIA联动规则
7.1 上游Streams变更 → 下游模块STALE
上游变更	下游受影响	传播路径
Streams.T/P/密度/粘度/组成变化	PIPE → PUMP → PIPE_NET	CIA 1分钟增量扫描
Streams相态变化（单相→两相）	PIPE（两相流模型切换）→ PUMP	同上
Streams物性缺失→FLASH补充	Streams（estimated标记）	FLASH写回血缘
7.2 PipingResults变更 → 下游模块STALE
上游变更	下游受影响	传播路径
PipingResults压降变化	PUMP（NPSHa/扬程/功率重算）	CIA
PipingResults管径变化	PUMP（吸入/排出管径） + PIPE_NET（管段特性）	CIA

> ⚠️ **传播机制（P4 Sprint 2 实现）**
>
> 本表描述的跨表 STALE 传播通过反查 `source_ref_type` + `source_ref_id` 实现：
>
> ```
> PipingResults X 变更
>   → CIA 反查：SELECT * FROM data_lineage
>              WHERE source_ref_type='PIPE_RESULT' AND source_ref_id=X
>   → 找到所有引用 X 的下游血缘行（如 PUMP_RESULT、PIPE_NETWORK_RESULT）
>   → 对每条下游行的 target 记录标记 STALE
> ```
>
> 此机制依赖 §4.3 定义的 `source_record_hash` 写入（P4 Task 0）。
> P1-MVP 的 `propagate()` 仅按 `parent_lineage_id` 自链传播，覆盖版本链场景。
> 两种传播模式在 P4 Sprint 2 中合并：自链（版本依赖）+ 反查（FK 引用依赖）。
> 详见 §4.4。

## 4.4 CIA 传播双模式（P4 Sprint 2 实现）

### 模式 1：版本链传播（P1-MVP 已实现）
- 通过 `parent_lineage_id` 自链遍历
- 场景：同一记录被修改产生新版本，旧版本标记 OBSOLETE
- 适用：记录自身变更历史

### 模式 2：FK 引用反查传播（P4 Sprint 2 新增）
- 通过 `source_ref_type` / `source_ref_id` 反查
- 场景：上游 PipingResults 变更 → 下游 PUMP/PIPE_NET STALE
- 实现：
  ```python
  async def propagate_from_source(self, source_type: str, source_id: UUID):
      lineages = await self.session.execute(
          select(DataLineage).where(
              DataLineage.source_ref_type == source_type,
              DataLineage.source_ref_id == source_id,
          )
      )
      for lin in lineages.scalars():
          target = await self._load_record(lin.target_type, lin.target_id)
          if target and target.sign_status != RecordSignStatus9.STALE:
              await self._mark_stale(target)
  ```

### 触发顺序
1. CIA 扫描发现 PipingResults 的 `source_record_hash` 与上游不一致
2. PipingResults 自身标记 STALE
3. 触发 `propagate_from_source("PIPE_RESULT", pipe_id)`
4. 下游 PUMP/PIPE_NET 标记 STALE
5. 递归传播（如果 PUMP 又有下游）

### P4 Sprint 2 CIA 扩展完整范围
1. `propagate_from_source()` 新方法（FK 反查）
2. `_mark_stale()` 幂等性增强（已 STALE 跳过）
3. 递归传播（防循环：已访问集合）
4. 传播深度限制（ADR-0022 链式传播，建议 ≤8）
5. 与版本链传播合并（两模式统一入口）
6. 设备联动（ADR-0025）整合到传播路径
7.3 设备联动（ADR-0025）
PipingResults STALE → 关联的PumpResults STALE（如果PUMP引用了该管线）

PumpResults STALE → 关联的EquipmentList设备记录 STALE

传播窗口 ≤ 5分钟（CIA cron兜底）

8. P4开发模板约定（写入CLAUDE.md）
python
# 所有P4计算函数必须遵循以下签名约定：
async def calculate_xxx(
    db: AsyncSession,           # 必须为关键字参数
    *,
    stream_id: UUID | None = None,      # 物性来源（PIPE/PUMP必填）
    upstream_record_ids: dict[str, UUID] | None = None,  # 上游计算记录引用
    params: XxxCalcParams,      # 计算参数（Pydantic模型）
) -> XxxResult:
    """
    1. 创建结果记录 → db.add → flush → 获得PK
    2. 从streams/上游记录读取依赖数据（不重复计算）
    3. 执行本模块的专用计算
    4. 写回结果
    5. @lineage装饰器自动写血缘
    """
    ...
9. 验收标准

> ⚠️ **本节为 V1.1 扩写版（P4 启动前重审）。v1.0 4 条拆分为 7 条，新增 Target/Source 维度区分 + 实现阶段标注。**

项	要求	实现阶段
数据流正确性	PIPE 不从 COMMON 直接查物性（必须走 streams）；PUMP 不调用 PIPE 计算函数（必须读 PipingResults）	P4 各模块自检

> ⚠️ **数据流正确性自动护栏（P4 Task 0 引入）**
>
> 本行描述的架构约束（PIPE 不从 COMMON 直接查物性、PUMP 不调用 PIPE 计算函数）通过 importlinter 契约自动验证：
>
> - `contracts.py` 定义分层依赖规则
> - `test_architecture_contracts.py` 在 pytest 中执行
> - 违规 import 在本地 pytest 阶段即失败（无需 CI）
>
> 执行时机：P4 Task 0（与 D4/D5 装饰器扩展同步）。
血缘完整性（Target 维度）	每次计算自动写入血缘，target_record_hash 正确	P1-MVP 已实现
血缘完整性（Source 维度）	每次计算自动写入血缘，source_record_hash 正确（从引用的上游记录读取）	P4 Task 0 装饰器扩展
CIA 联动（Target 自检）	记录自身 record_hash 与血缘中存储值不一致 → STALE	P1-MVP 已实现
CIA 联动（Source 传播）	血缘中 source_record_hash 与上游记录当前 hash 不一致 → 下游 STALE	P4 Sprint 2
估算标记	所有估算值（物性缺失/压降未计算/拓扑无 PipingResults）标记 estimated=true	P4 各模块
正式提交要求	CHECKED 状态的计算记录，其上游引用必须也是 CHECKED 或已确认	P4 状态机守卫

## 4.3 source_record_hash 抓取机制（P4 Task 0 实现）

### 目的
使 CIA 能够检测"上游记录变更 → 下游记录 STALE"的传播路径。仅靠 Target 自检无法捕获"目标记录自身未改、但上游改了"的场景。

### 实现要求
当装饰器使用 FK 引用模式（`sources=[(param_name, source_type)]`）时：

1. 从函数 `kwargs` 按 `param_name` 提取 UUID 值
2. 根据 `source_type` 查 `RECORD_TYPE_REGISTRY` 映射的 ORM 类
3. 从 DB 加载该 source 记录
4. 计算该 source 记录的 `record_hash`
5. 将 `source_record_hash` 写入 `data_lineage` 行（与 target_hash 同行）

### 与 target_hash 的关系
- **target_record_hash**：目标记录自身哈希（防外部修改）
- **source_record_hash**：上游记录哈希快照（防上游变更未传播）

### 与 physical_semantics 的关系（V1.1，对齐本体论 V1.6 §7）

**physical_semantics 作为语义标签层（JSONB 数组），不影响数据流拓扑**：

- data_lineage 表新增 `physical_semantics` JSONB nullable 列（仅占位），P4 Task 0-Code 起加 `@P7-eval-point` 列注释
- `@lineage` 装饰器**不暴露** `physical_semantics` 参数——P4–P6 开发者无需知道此字段存在，永远为 NULL
- 数据流架构（FLASH → Streams → PIPE → PUMP/PIPE_NET）保持不变；`dependency_type` 单一字符串（CALCULATION/REFERENCE/MANUAL_OVERRIDE/ESTIMATED）继续驱动 CIA 传播
- `dependency_type` 与 `physical_semantics` 职责分离：前者用于 CIA 传播（P1 已实现），后者用于语义查询（P7 评估后裁定是否启用）
- 评估触发：P7 启动前基于 P4–P6 积累的审计日志数据（stale_resolution_path / hash_changed / changed_fields），决策是否启用语义过滤。详见本体论 V1.6 §3.2b 三元决策机制

**Pydantic ↔ ORM 同步 CI（V1.1 增补，对齐 V1.6 §5.2 / §6 规则 11）**：

- ORM Column comment ↔ Pydantic `Field(description=...)` 静态对比 CI 测试
- 漂移即 fail（与 RECORD_TYPE_REGISTRY 三方比对 CI 同级硬性）
- 单一事实来源：Pydantic Schema 是 JSONB 子结构的唯一载体；ORM comment 需与之一致但非主源

### CIA 两种扫描模式

| 模式 | 检测内容 | 对比对象 | 实现阶段 |
|---|---|---|---|
| Target 自检 | 记录自身被外部修改 | 当前 `record_hash` vs lineage 中 `target_hash` | P1-MVP 已实现 |
| Source 传播 | 上游记录已变更 | 当前 source hash vs lineage 中 `source_hash` | P4 Sprint 2 |
10. 版本历史
版本	日期	修改内容
V1.0	2026-09-01	初始版本：P4模块间数据流架构规范（FLASH→Streams→PIPE→PUMP/PIPE_NET）
V1.1	2026-09-03	对齐 PCS 本体论 V1.6 §7：§4.3 末段新增"与 physical_semantics 的关系"小节，明确 physical_semantics 作为语义标签层不影响数据流拓扑（@lineage 装饰器不暴露、P4–P6 永久 NULL）；新增 Pydantic ↔ ORM 同步 CI（V1.6 §5.2 / §6 规则 11，硬性）；本版本不修改 §2/§3/§4.1–§4.2 等已建立的数据流拓扑与引用规范
PCS-REQ-2026-DF-001完。 本文档作为P4开发的前置架构规范，所有P4计算模块开发必须遵守此数据流。与PCS-DICT-ALL-003 V3.3、PCS-DICT-011配合使用。
