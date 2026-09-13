# P4 核心计算引擎（第一批）实施计划 V1.1

> **执行方式**：superpowers TDD（每 task：RED 测试 → GREEN 实现 → commit）；
> 可用 subagent-driven-development（每 task 派新 agent）或 executing-plans（本 session 批量）。
> **基线 spec**：`spec/工艺专用综合计算软件需求规格说明书 Web版 P4.md`（V1.5）
> **开发计划**：`spec/...Web版开发计划.md` §P4（4.1~4.4）｜ **TODOS**：034/035/036
> **V1.1（2026-09-13）**：7 项裁决落地（见文末裁决记录）

**Goal**：交付 FLASH/PIPE/PIPE_NET/PUMP 四模块计算链（物性→管道→管网→泵），9 态记录门禁 + CIA STALE 传播闭环。

**Architecture**：Thermo(vendored) 相平衡 → fluids(vendored) 管道水力学 → SciPy 管网迭代 → 伯努利泵链；结果入 P0 已建表（calc.py）+ OPEN-008 扩展；每计算自动 record_hash + 血缘 + 出口物流（ADR-0022）；审计写入统一走 lineage helper（禁直写审计列）。

**Tech**：FastAPI + SQLAlchemy 2.0 async + PG16 + thermo/fluids(vendored) + scipy + numpy.float64

## 全局约束

- 单位契约：API 入参 SI（K/Pa/m³s/kg/m），schema 层换算（同 SIM 模式）
- 浮点：numpy.float64；Golden Test 偏差 ≤1e-12（spec §3.3.2）
- 公式版本：每次计算写 FormulaVersion 入 DataLineage（spec §2.5）
- 引用物流须 CHECKED（DRAFT → 403）+ 不可靠流 → 422 STREAM_UNRELIABLE_BLOCKED（guard 已备）
- 性能预算：FLASH ≤2s / PIPE 链 ≤3s / PIPE_NET(10 节点) ≤5s / PUMP ≤2s；迭代上限 100
- 出口物流：PIPE/PIPE_NET/PUMP/CV 完成自动建出口物流（source_type=DEVICE_CALCULATED，DRAFT，change_type=PUMP_WORK/FRICTION_PRESSURE_DROP…）
- **物性三段式（裁决 #7）**：已有→用；可估算（白名单：密度/粘度/比热/导热系数）→ estimated 标记继续；不可估算→422 PHYSICAL_PROPERTY_MISSING（列缺失项）。**Pv 蒸气压与表面张力禁估算，缺失即 422**；estimated 写入 output_json 并传播下游；涉及 estimated 的 check_result 最高 WARNING
- **审计护栏（裁决 #1）**：批 1~4 落库统一走 lineage/record_hash helper，禁各模块直写审计列；RECORD_TYPE_REGISTRY 先用集中常量占位
- ruff 0 errors（已归零，572cef3）；测试基线 1220 passed

---

## 批 0 前置数据层（~2d）

### P4-0-1 审计字段迁移（OPEN-010 残余 + 005/006 子集）

enum 5 态已由 SIM-13 落地（勿重复）。残余：streams + 4 计算记录表加审计字段。

护栏（裁决 #1）：本 task 同时交付 `app/services/calc_lineage.py`（统一 record_hash + 血缘 + 审计列写入 helper）+ `RECORD_TYPE_REGISTRY` 常量占位 + 豁免 ADR（P4 计算链条件启动，全量本体论后置 P4-TASK0 批次）。

**Files**: Create `alembic/versions/p4_calc_audit_fields.py` + `app/services/calc_lineage.py` + `docs/adr/0031-p4-task0-exemption.md`；Modify `app/models/mixins.py`（RecordMixin 扩展）+ `app/models/calc.py`

**测试**（RED，仿 test_alembic_roundtrip 模式）：
```python
def test_audit_columns_exist():
    # streams/piping_results/pump_results/flash_results/pipe_network_results
    # 均含 stale_resolution_path(String30|null) + hash_changed(Bool|null, default false)
    # + changed_fields(JSONB|null)
```
步骤：写迁移（5 表 × 3 列 ADD COLUMN）→ mixin/模型同步 → pcs_test upgrade → 测试绿 → commit `feat(p4-0-1): calc audit fields migration`

### P4-0-2 OPEN-008 表扩展（SUP-008 V1.1）

**Files**: Create `alembic/versions/p4_sup008_result_fields.py`；Modify `app/models/calc.py`

- piping_results +12：line_description, pipe_type(enum PUMP_SUCTION/PUMP_DISCHARGE/SELF_FLOW/HEATING_STEAM/TWO_PHASE), max_flow_factor, selected_diameter, liquid_velocity_max, gas_velocity_max, pressure_drop_per_100m, selected_pipe_size, recommended_pipe_size, check_result(enum PASS/FAIL/WARNING), velocity_range_reference（PG enum ×2）
- pump_results +4：selected_pump_model, selected_motor_model, selected_motor_power, pump_operation(enum NORMAL/STANDBY/OFF)
- pump_results/psv_results/vessel_results + design_stage(enum BASIC/DETAIL, default BASIC)（OPEN-009）
- 新表 two_phase_results（13 字段：Bx/By/flow_pattern enum ANNULAR/MIST/BUBBLE/SLUG/STRATIFIED/WAVE/two_phase_check enum PASS/WARNING/FAIL + 其余按 SUP-008 §8.3.4）

**测试**：列存在性 + enum 值域 + design_stage 默认 BASIC。commit `feat(p4-0-2): sup008 result fields + two_phase_results`

### P4-0-3 计算入口守卫接线

**Files**: Create `app/services/calc_entry.py`；Test `tests/services/test_calc_entry.py`

```python
async def check_calc_inputs(db, stream_ids) -> None:
    """统一入口：物流存在 → CHECKED 校验(403) → UnreliableStreamGuard.check(422)。"""
```
被批 1~4 全部 calculate 端点复用。commit `feat(p4-0-3): calc entry guard (CHECKED + unreliable)`

---

## 批 1 FLASH（~4d，spec §3.2.1）

### P4-1-1 Thermo 封装层

**Files**: Create `app/services/flash/thermo_factory.py`；Test `tests/services/flash/test_thermo_factory.py`

```python
THERMO_METHOD_MAP = {  # 体系类型 → thermo 实现
    "LIGHT_HYDROCARBON": "PRMIX", "GAS_PROCESSING": "SRKMIX",
    "POLAR": "NRTL", "WATER_STEAM": "CoolProp",
}
def build_thermo(method: str, zs: list[float], CASs: list[str]) -> ThermoInterface
```
测试：4 体系映射 + 未知体系 422 + 组成归一化。commit `feat(p4-1-1): thermo factory`

### P4-1-2 闪蒸计算核心（8 种）

**Files**: Create `app/services/flash/flash_service.py`；Test `tests/services/flash/test_flash_service.py`（golden）

8 种：PT/PH/PS_FLASH + BUBBLE_P/T + DEW_P/T + SATURATION。
golden 基准（手算/库内自洽）：
```python
# 纯水 101.325kPa 饱和温度：CoolProp 373.12K，偏差 <0.5%（spec 验收）
# 丙烷(0.3)+正丁烷(0.7) PT_FLASH @ 300K/1MPa：首跑固化 golden.json，
#   断言 vapor_fraction 单调性 + 后续运行 ≤1e-12 漂移
# 泡露点：纯组分时 BUBBLE_P == DEW_P == Psat（热力学自洽校验）
```
PH/PS 用 thermo 的 TS/PS flash；SATURATION 走 chemicals.iapws/CoolProp（cerebrum：iapws95_Tsat 是函数）。commit `feat(p4-1-2): flash core 8 calcs`

### P4-1-3 API + 落库 + 状态点联动 + 出口物流

**Files**: Create `app/api/v1/flash.py`（3 端点：calculate/bubble/dew）+ `app/services/flash/flash_persist.py`；Modify `app/api/v1/__init__.py` 路由注册

- flash_results 落库（input_json/output_json/calc_type/method）+ record_hash（6 位有效数字规范化）+ 血缘
- 状态点联动（ADR-0020）：T/P/组成 → 算气液分率写回 state point（estimated 标记）
- 出口物流创建（ADR-0022）：source_type=FLASH_CALCULATED，DRAFT
- 测试：POST 3 端点 e2e + DRAFT 物流 403 + 不可靠流 422 + 出口物流存在。commit `feat(p4-1-3): flash api + persistence + outlet stream`

### P4-1-4 SIM 反向写入

**Files**: Modify `app/services/flash/flash_persist.py`；Test 补充

焓/熵/汽化分率写 streams.stream_properties_json（来源标记 FLASH_CALCULATED，经 conflict_resolver effective 合成，不静默覆盖用户值）。commit `feat(p4-1-4): flash writeback to stream`

---

## 批 2 PIPE（~6d，spec §3.2.2）

### P4-2-1 PipeSizingService

**Files**: Create `app/services/pipe/sizing_service.py`；Test `tests/services/pipe/test_sizing.py`

- 预定流速法 D=1000×√(V/(0.785v))；设定压力降法迭代最小 DN 满足每 100m 压降约束
- 推荐流速表从 CONFIG（HG/T 20570.6-95 种子）；DN 圆整从 PIPE_CLASS 标准系列
```python
# golden：V=0.01 m³/s, v=2 m/s → D=79.8mm → 圆整 DN80（精确断言）
```
commit `feat(p4-2-1): pipe sizing (velocity + dp methods)`

### P4-2-2 WallThicknessService（ASME B31.3）

**Files**: Create `app/services/pipe/wall_thickness_service.py`；Test

- 无缝 t=PD/(2(SE+PY))；焊接 t=PD/(2(SEW+PY))；t_nom=t+c 圆整 Sch
- S 按设计温度从 PIPE_CLASS/COMMON 许用应力表插值；c/E/Y/W 从 PIPE_CLASS
```python
# golden 手算：P=2.0MPa, D=168.3mm, S=138MPa, E=1, Y=0.4
#   → t=2×168.3/(2×(138+2×0.4))=1.213mm；c=2 → 3.213 → Sch 圆整断言
```
commit `feat(p4-2-2): wall thickness b31.3`

### P4-2-3 单相压降

**Files**: Create `app/services/pipe/pressure_drop_service.py`；Test

- Darcy-Weisbach + Colebrook + fluids.fittings（弯头/三通/阀门/变径/出入 口 K 值表映射）
- ΔP/P₁<10% 不可压缩近似；≥10% 转 P4-2-4
```python
# golden：水 20°C，DN50 Sch40（ID 52.5mm），Q=20 m³/h，L=100m，粗糙度 0.046mm
#   fluids 首跑固化 golden.json（≤1e-12 漂移）；Crane K 值断言（90° 弯头 std R≈0.75K？用库值固化）
```
commit `feat(p4-2-3): single phase dp + fittings`

### P4-2-4 可压缩 + 两相

**Files**: Create `app/services/pipe/compressible_dp.py` + `app/services/pipe/two_phase_dp.py`；Test

- 可压缩：fluids.compressible 等温/绝热（Pantheon/Mach 数判定）
- 两相：首选 Dukler I，L-M 交叉验证；flow_pattern 判别 **Baker 图查表**（裁决 #6：
  系数表固化版本 + 回归测试标 regression_baseline；超适用范围降级 WARNING +
  confidence=LOW；封装为可替换函数 `classify_flow_pattern(Gm, Lm, ρg, ρl) →
  (pattern, confidence)`，P5+ 切 Taitel-Dukler 不动调用方）→ two_phase_results 字段
commit `feat(p4-2-4): compressible + two phase dp + baker flow pattern`

### P4-2-5 calculate-all 链 + 落库

**Files**: Create `app/api/v1/pipe.py`（4 端点）+ `app/services/pipe/pipe_chain.py`；Test e2e

物性准备(SIM)→相态(FLASH)→管径→壁厚→压降→流速校核(check_result)→PipingResults 全字段落库 + two_phase_results + 出口物流 + record_hash/血缘。性能 ≤3s 断言。commit `feat(p4-2-5): pipe calculate-all chain + api`

---

## 批 3 PIPE_NET（~3d，spec §3.2.3）

### P4-3-1 拓扑模型

**Files**: Create `app/schemas/pipe_net.py`（Pydantic：nodes[{id,pressure_spec?}]/segments[{id,from,to,diameter,length,roughness,fittings}]）

校验：连通性 + 节点质量平衡边界（源/汇足够）。commit `feat(p4-3-1): pipe net topology schema`

### P4-3-2 求解器

**Files**: Create `app/services/pipe_net/solver.py`；Test

- Hardy-Cross（scipy.optimize.fsolve 环路流量）+ 节点法（线性化迭代）双实现，按拓扑自动选择（环形→HC，复杂→节点法）
- PIPE 集成：每管段调 PressureDropService 得阻力特性 → 求解 → 回写流速迭代至收敛（≤100 次）
```python
# golden：两并联管（同 DN 同 L）等流量分配（解析精确：各 50%，断言 <1% 与手算，spec 验收）
# 环形 3 管网 Hardy-Cross 标准算例：首跑固化 golden
```
commit `feat(p4-3-2): hardy-cross + nodal solvers`

### P4-3-3 API + 落库

**Files**: Create `app/api/v1/pipe_net.py`（solve + get results）

pipe_network_results(input/output_json) + 收敛日志输出 + 性能 ≤5s(10 节点)。commit `feat(p4-3-3): pipe net api`

---

## 批 4 PUMP（~4d，spec §3.2.4）

### P4-4-1 等效长度计算器

**Files**: Create `app/services/pump/equivalent_length.py`；Test

管件枚举 TUBE/BENDS/VALVES/TEE/CHECK_VALVE/REDUCER ×(数量, Le/D)；K→Le 换算复用 fluids.fittings。commit `feat(p4-4-1): equivalent length calc`

### P4-4-2 扬程 + NPSHa + 设计压力

**Files**: Create `app/services/pump/head_service.py`；Test

- H=ΔP/(ρg)+ΔZ+Σhf（吸入/排出双侧明细）
- NPSHa=(Ps−Pv)/(ρg)+v²/2g−h损失；NPSHa vs NPSHr（选型输入）余量断言
- 泵设计压力 = MaxSuctionPressure + 1.25×DP
```python
# golden 手算：ΔP=0.5MPa, ρ=998（水 20°C）→ ΔP/ρg≈51.0m；+ΔZ=10m+Σhf=2.5 → H≈63.5m（精确断言）
```
commit `feat(p4-4-2): head + npsh + design pressure`

### P4-4-3 粘度修正 + 功率 + 控制阀分配

**Files**: Create `app/services/pump/power_service.py` + `app/services/pump/viscosity_correction.py`；Test

- **HI 9.6.7 2021 Parameter-B** 修正（裁决 #3：2015 版已被 2021-11-13 取代；
  ADR-0030 记录）：cH/cQ/cE 修正系数（粘度 μ>20cP 触发）
- BHP=Q×H×ρ×g/(3600×η)；电机功率 = BHP/η_motor×安全系数(CONFIG)
- 控制阀压降：设计/正常/最小 3 工况分配规则（CONFIG：按 ΔP_line 比例 + 最小压差约束）
commit `feat(p4-4-3): viscosity + power + control valve dp`

### P4-4-4 calculate 完整链 + CIA STALE 联动

**Files**: Create `app/api/v1/pump.py`（3 端点）+ `app/services/pump/pump_chain.py`；Modify `app/services/cia_engine.py`

- pump_results 全 12 JSON 段落库 + selected_* 4 字段 + design_stage
- 出口物流（PUMP_WORK）+ record_hash
- **CIA STALE（OPEN-011）**：上游物流 CHANGE_PENDING→CHANGED(hash 变) → 下游计算记录自动 STALE + 快照；「重算」端点（hash 不变免凭证回 CHECKED，变则 CHANGE_PENDING）；扩展 cia_engine 9 态支持 + perf ≤1000 条 ≤30s 测试
commit `feat(p4-4-4): pump chain + cia stale propagation`

---

## 验收（spec §3.2 各节 + §3.3，裁决 #2 校准）

| 项 | 标准 |
|---|---|
| FLASH | 纯物质饱和 vs CoolProp/IAPWS <0.5%（硬基准）；**混合闪蒸 thermo 快照标 regression_baseline（条件验收，挂 P4-OPEN-GOLDEN）**；泡露点纯组分自洽 + 手算 |
| PIPE | 单相压降 fluids 快照 regression_baseline + 手算 <5%；壁厚与手算一致（硬基准）；K 值 Crane 库值固化 |
| PIPE_NET | 并联 <1% 手算（硬基准）；环形 Hardy-Cross 标准算例快照 |
| PUMP | 扬程 <1% 手算（硬基准）；NPSH/功率正确；控制阀分配合理 |
| 流型 | Baker 图 regression_baseline（挂 P4-OPEN-FLOWPATTERN 如需实验/商业对照） |
| 性能 | 4 模块预算（§3.3.1）全部断言 |
| 记录 | record_hash + 血缘 + 出口物流 + CIA STALE 闭环（统一 helper） |

> **条件验收边界（裁决 #2/#6）**：HYSYS/商业软件偏差验收待用户提供惠州 xlsx
> 点位后补对照测试；未补前上述 regression_baseline 项为回归保护而非精度验收。

## 估时

批 0 ≈2d → 批 1 ≈4d → 批 2 ≈6d → 批 3 ≈3d → 批 4 ≈4d ≈ **19d**（P3.x 实绩折算系数 ~0.3，实际可能 ~6-8d）

## 裁决记录（2026-09-13，V1.1 全部已决）

| # | 议题 | 裁决 |
|---|---|---|
| 1 | 本体论 Task 0（OPEN-005/006） | **子集先行 + 护栏**：批 0 仅落审计 3 列；同时交付统一 lineage helper（禁直写审计列）+ RECORD_TYPE_REGISTRY 常量占位 + 豁免 ADR-0031；全量（@lineage D4/D5/physical_semantics/importlinter D8/CI 三方比对/Pydantic↔ORM CI）拆独立 **P4-TASK0 批次**，不阻塞批 1~4，但 P4 验收前必须关闭（否则 P4 条件验收）。架构委员会拒豁免时切最小化方案（physical_semantics+D4/D5+骨架 CI 先行） |
| 2 | golden 对照来源 | **手算 + 快照混合**：壁厚/泵/并联管网手算硬基准；纯组分饱和 CoolProp/IAPWS 硬基准；混合闪蒸/单相压降 thermo/fluids 快照标 regression_baseline（回归保护非精度验收）；可提供惠州 xlsx 点位则补 HYSYS 对照；否则挂 **P4-OPEN-GOLDEN** 条件验收 |
| 3 | HI 粘度修正版本 | **HI 9.6.7 2021 Parameter-B**（2015 版已 superseded）；ADR-0030 |
| 4 | 前端 | **后端先行**；spec §3.1.1 四界面后端 API 冻结后另编前端计划 |
| 5 | TODO-034/035 | **独立小 sprint**（~1.5d，与计算链解耦，不进本计划） |
| 6 | 流型判别 | **Baker 图查表**：系数表固化 + regression_baseline；超适用范围 WARNING + confidence=LOW；封装可替换函数（P5+ 切 Taitel-Dukler 不动调用方）；需实验/商业对照则挂 **P4-OPEN-FLOWPATTERN** |
| 7 | 物性缺失策略 | **三段式**：已有→用 / 可估算→estimated 继续 / 不可估算→422；白名单仅密度/粘度/比热/导热系数；**Pv 与表面张力禁估算**；estimated 写 output_json 传播下游；涉 estimated 的 check_result 最高 WARNING；上游物性变更触发 CIA STALE |

### 新挂 OPEN 项（条件验收）

- **P4-OPEN-GOLDEN**：混合闪蒸/压降 vs HYSYS 偏差验收，待用户提供惠州 xlsx 对照点位
- **P4-OPEN-FLOWPATTERN**：Baker 流型 vs 实验/商业软件对照，如验收要求时补

### 后置批次（P4 验收前关闭）

- **P4-TASK0**：本体论全量（V1.6 §5.1/§5.2 清单逐项，架构委员会 approve 后细化）
- **P4.x-TODO**：TODO-034 模板版本 + TODO-035 22 条校验（独立小 sprint ~1.5d）
