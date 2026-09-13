# P4 核心计算引擎（第一批）实施计划 V1.0

> **执行方式**：superpowers TDD（每 task：RED 测试 → GREEN 实现 → commit）；
> 可用 subagent-driven-development（每 task 派新 agent）或 executing-plans（本 session 批量）。
> **基线 spec**：`spec/工艺专用综合计算软件需求规格说明书 Web版 P4.md`（V1.5）
> **开发计划**：`spec/...Web版开发计划.md` §P4（4.1~4.4）｜ **TODOS**：034/035/036

**Goal**：交付 FLASH/PIPE/PIPE_NET/PUMP 四模块计算链（物性→管道→管网→泵），9 态记录门禁 + CIA STALE 传播闭环。

**Architecture**：Thermo(vendored) 相平衡 → fluids(vendored) 管道水力学 → SciPy 管网迭代 → 伯努利泵链；结果入 P0 已建表（calc.py）+ OPEN-008 扩展；每计算自动 record_hash + 血缘 + 出口物流（ADR-0022）。

**Tech**：FastAPI + SQLAlchemy 2.0 async + PG16 + thermo/fluids(vendored) + scipy + numpy.float64

## 全局约束

- 单位契约：API 入参 SI（K/Pa/m³s/kg/m），schema 层换算（同 SIM 模式）
- 浮点：numpy.float64；Golden Test 偏差 ≤1e-12（spec §3.3.2）
- 公式版本：每次计算写 FormulaVersion 入 DataLineage（spec §2.5）
- 引用物流须 CHECKED（DRAFT → 403）+ 不可靠流 → 422 STREAM_UNRELIABLE_BLOCKED（guard 已备）
- 性能预算：FLASH ≤2s / PIPE 链 ≤3s / PIPE_NET(10 节点) ≤5s / PUMP ≤2s；迭代上限 100
- 出口物流：PIPE/PIPE_NET/PUMP/CV 完成自动建出口物流（source_type=DEVICE_CALCULATED，DRAFT，change_type=PUMP_WORK/FRICTION_PRESSURE_DROP…）
- ruff 0 errors（已归零，572cef3）；测试基线 1220 passed

---

## 批 0 前置数据层（~2d）

### P4-0-1 审计字段迁移（OPEN-010 残余 + 005/006 子集）

enum 5 态已由 SIM-13 落地（勿重复）。残余：streams + 4 计算记录表加审计字段。

**Files**: Create `alembic/versions/p4_calc_audit_fields.py`；Modify `app/models/mixins.py`（RecordMixin 扩展）+ `app/models/calc.py`

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
- 两相：首选 Dukler I，L-M 交叉验证；flow_pattern 判别（Hughmark/政府图简化查表）→ two_phase_results 字段
commit `feat(p4-2-4): compressible + two phase dp`

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

- HI 9.6.7-2015 修正（OPEN-002 假设版本，ADR 记录）：cH/cQ/cE 多项式（粘度 μ>20cP 触发）
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

## 验收（spec §3.2 各节 + §3.3）

| 项 | 标准 |
|---|---|
| FLASH | 纯物质饱和 vs CoolProp <0.5%；混合闪蒸 vs HYSYS <1%；泡露点 <0.5°C（golden 对照数据来源见未决 #2） |
| PIPE | 单相压降 <0.1%（vs fluids golden）；壁厚与手算一致；K 值 <2% Crane；综合 <5% 手算 |
| PIPE_NET | 并联 <1% 手算；环形 <2% Hardy-Cross 标准算例 |
| PUMP | 扬程 <1% 手算；NPSH/功率正确；控制阀分配合理 |
| 性能 | 4 模块预算（§3.3.1）全部断言 |
| 记录 | record_hash + 血缘 + 出口物流 + CIA STALE 闭环 |

## 估时

批 0 ≈2d → 批 1 ≈4d → 批 2 ≈6d → 批 3 ≈3d → 批 4 ≈4d ≈ **19d**（P3.x 实绩折算系数 ~0.3，实际可能 ~6-8d）

## 未解决问题（需用户/架构委员会裁决）

1. **P4-OPEN-005/006 本体论 Task 0 全量**：@lineage 装饰器（D4/D5）、RECORD_TYPE_REGISTRY、physical_semantics 列、importlinter D8、CI 三方比对——本计划仅落审计字段子集，全量待架构委员会按 V1.6 §5.1/§5.2 清单 approve 后增补批次
2. **Golden 对照数据来源**：HYSYS/商业软件偏差验收（<0.1%/1%）需要对照算例——用户提供？或降级为 fluids/thermo 自洽 + 手算基准
3. **OPEN-002**：粘度修正 HI 版本假设 9.6.7-2015，需确认 + ADR
4. **前端**：本计划仅后端（spec §3.1.1 四界面属前端计划，另行编制？）
5. **TODO-034/035**：模板版本管理 + 22 条校验规则补全——建议并入批 0/批 4 还是独立？
6. **流型判别方法**：两相 flow_pattern 用哪张流型图（Baker/Hughmark/Taitel）？spec 只定枚举未定算法
7. **Psat/物性默认来源**：PIPE 链的密度/粘度从 streams.stream_properties_json 读，缺失时走 COMMON 物性补全还是直接 422？
