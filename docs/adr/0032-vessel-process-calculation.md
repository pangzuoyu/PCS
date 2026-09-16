---
status: proposed
date: 2026-09-17
proposed_by: P5 架构评审委员会（P5-1-1 起草组）
related: [SUP-008, PCS-PLAN-P5-DEVICE-EQUIPMENT.md, ADR-0027 V1.0, ADR-0030 V1.1]
---

# VESSEL 工艺计算架构（P5-1 容器计算）

P5-1 batch 交付 VESSEL 容器计算模块（4 task：核心 / 流体力学 / EQUIP_LIB 匹配 / API 落库）。P5-1-1 交付 `calc_vessel_sizing` 核心计算（基于 ChEDL `fluids.separator.v_Souders_Brown` 的容器最小直径 + 持液量 + 停留时间）；P5-1-2/3/4 沿用本 ADR 架构。

若不显式约定 ChEDL 分层 + K 因子单位 + 停留时间分支 + 输入输出契约，将出现 P5-1-2/3/4 实现时跨函数耦合、业务代码直接 import fluids、SPEC §3.2.1 K 因子英制 vs 工程 SI 单位混淆、停留时间与行业惯例不一致、落库字段归属不清等问题。

本 ADR 记录 P5-1 VESSEL 工艺计算的 6 项架构裁决。

决定：**P5-1 容器计算按 ChEDL 分层 + SI 单位 + 停留时间分支 + 纯函数不触 DB 实施**。

---

## 决策 1：ChEDL 分层（业务代码禁直接 import fluids）

**理由**：
- ADR-0030 V1.1 决策 6：业务代码禁止直接 `import fluids.*`，统一 `from app.services import chedl_wrapper`
- 裁决 #8 + V1.8 包装层（PCS-PLAN §131）：包装函数记录 ChEDL 函数名 + 版本 + 已知限制 + 内部替代占位符；即使 ChEDL 某函数未来不可用，替换仅修改包装层内部
- P5-1-1 唯一允许的 ChEDL 函数调用：`from app.services import chedl_wrapper` + `chedl_wrapper.v_Souders_Brown(K, rhol, rhog)`

**P5-1 函数清单**（包装层已就绪，P5-0-7 Task 26 落地）：
| 函数 | 行号 | P5-1 用途 |
|---|---|---|
| `chedl_wrapper.v_Souders_Brown(K, rhol, rhog)` | chedl_wrapper.py:45-56 | P5-1-1 主入口（返回 V_max m/s） |
| `chedl_wrapper.K_separator_Watkins(x, rhol, rhog, horizontal, method)` | L59-77 | P5-1-1 备用 K 因子法 |
| `chedl_wrapper.K_separator_demister_York(P, horizontal)` | L80-87 | P5-1-1 带除雾器 K 因子 |
| `chedl_wrapper.K_Souders_Brown_theoretical`（P5-1-1 新增）| 待定 | PCS-PLAN §129 要求；P5-1-1 包装就绪供 P5-2+ 使用 |
| `chedl_wrapper.time_to_empty(D_tank, h0, d_orifice, Cd)` | L127-163 | P5-1-2 排空时间（fallback 自研） |
| `chedl_wrapper.tank_level_to_volume(D, h, head_type)` | L166-208 | P5-1-2 液位-容积曲线（fallback 自研） |

**自研范围**：K 因子 CONFIG 读取 + 容器类型分支（立式/卧式/带除沫器）+ D_min 公式 + 停留时间按 vessel_type 分支 + 边界校验。**不重写核心公式**。

---

## 决策 2：K 因子单位约定 SI m/s

**现状**：SPEC §3.2.1 K 因子取值"立式 0.03~0.15 / 卧式 0.15~0.35"——其中 0.35 是英制 GPSA ft/s 单位下的值（0.35 ft/s ≈ 0.107 m/s）。

**问题**：业务层若直接用英制 ft/s 值（0.35）与 ChEDL SI m/s（0.10）混用，将产生 3.4 倍偏差。

**裁定**：
- P5-1-1 业务代码 **统一 SI m/s**
- 立式典型区间：**0.04~0.10 m/s**
- 卧式典型区间：**0.07~0.15 m/s**
- 带除沫器（WITH_DEMISTER）：同立式 **0.04~0.10 m/s**（除沫器进一步降低 K）
- K 因子测试边界：**0.04 / 0.10 / 0.15**（plan §131 锚定）

**SPEC 修订待办**：登记 spec §3.2.1 K 因子英制 vs SI 修订项；本 ADR 不替代 spec 修订，仅约束 P5-1 实施按 SI 推进。

**CONFIG 种子数据**：`app/seeds/category3_defaults.json` 后续补 VESSEL K 因子种子（立式 0.04~0.10 / 卧式 0.07~0.15）；P5-1-1 暂硬编码（K 因子由调用方传入，不依赖 CONFIG）。

---

## 决策 3：停留时间按 vessel_type 分支（V1.6 关注项修正）

**V1.6 关注项**：卧式液位控制比立式复杂（液相面积更大、停留时间难精确控制），行业惯例停留时间上浮。

**裁定**：
- 立式（VERTICAL）：**3~5 分钟**（紧凑型）
- 卧式（HORIZONTAL）：**5~10 分钟**（宽松型 + 上浮）
- 带除沫器（WITH_DEMISTER）：**3~5 分钟**（同立式）

**API 约定**：输入 `residence_time_min = 0` 时按 vessel_type 默认区间取**中值**（vertical=4 / horizontal=7.5 / with_demister=4）；输入 > 0 时按用户值使用；输入 < 0 或越界时报 VesselInputError。

**下游使用**：持液量 V_liq = Q_L × t_residence（m³）；用于 P5-1-2 流体力学校核（溢流口、液位-容积曲线）。

---

## 决策 4：6 测试覆盖 + K 边界 + 边界异常

**6 例 golden fixture**（4 容器类型 × 卧式/立式 + K 边界）：
1. `vertical_basic`：立式基础例（K=0.10, ρ_L=850, ρ_V=1.2）→ V_max=2.660 m/s
2. `horizontal_basic`：卧式基础例（K=0.12, ρ_L=1000, ρ_V=1.2）→ V_max=3.162 m/s
3. `vertical_with_demister`：立式带除沫器（K=0.08, ρ_L=750, ρ_V=2.5）
4. `horizontal_high_pressure`：卧式高压（K=0.07, ρ_L=900, ρ_V=5.0）
5. `k_boundary_low`：K=0.04 立式下边界 → check_result=WARNING
6. `k_boundary_high`：K=0.15 卧式上边界 → check_result=WARNING

**交叉验证**：
- 与手算 V_max = K × √((ρ_L - ρ_V) / ρ_V) 偏差 ≤1%
- 与 ChEDL `v_Souders_Brown(K, rhol, rhog)` 直调偏差 ≤1%（PCS-PLAN §129 V1.7 问题1 强制）

**异常覆盖**：
- `liquid_flow_m3_s <= 0` → VesselInputError
- `vapor_flow_m3_s <= 0` → VesselInputError
- `rho_L <= rho_V`（密度倒置）→ VesselInputError
- `K_factor_ms` 超出 `[0.01, 1.0]` → VesselInputError

**置信度分类**（基于 K 因子 + vessel_type）：
- K 在典型区间内 → `HIGH`
- K 在典型区间外但物理合理 → `MEDIUM`
- check_result：HIGH → `PASS`，MEDIUM → `WARNING`

---

## 决策 5：纯函数不触 DB（P5-1-1）；P5-1-4 才落库 + outlet_stream

**P5-1-1 范围**：`calc_vessel_sizing(inp: VesselSizingInput) -> VesselSizingResult` 纯计算函数，不依赖 DB session、不写日志、不发 RPC。

**P5-1-2/3/4 扩展**：
- P5-1-2 `calc_vessel_hydraulics`：纯计算函数（同 P5-1-1 模式），复用 chedl_wrapper.time_to_empty + tank_level_to_volume
- P5-1-3 `recommend_vessels`：DB 依赖（EQUIP_LIB 匹配）
- P5-1-4 vessel_persist + API：落库 `vessel_results` + outlet_stream（source_type 扩展 `"VESSEL"`）+ finalize_calc_record

**P5-1-1 不下沉字段**：VesselResult 当前 4 列（PK + input_json + output_json + design_stage）足够承载；具体业务字段全部进 `input_json` / `output_json`。P5-1-4 评估 13 字段 roundtrip 需求时再决定是否下沉（见决策 6）。

**入口函数签名**（frozen dataclass 不可变 + 可哈希）：
```python
@dataclass(frozen=True)
class VesselSizingInput:
    vessel_type: Literal["VERTICAL", "HORIZONTAL", "WITH_DEMISTER"]
    rho_L_kg_m3: float
    rho_V_kg_m3: float
    liquid_flow_m3_s: float
    vapor_flow_m3_s: float
    residence_time_min: float  # 0 = 默认 vessel_type 中值
    K_factor_ms: float

@dataclass(frozen=True)
class VesselSizingResult:
    V_max_ms: float       # 允许最大气速（Souders-Brown）
    D_min_m: float        # 容器最小直径
    liquid_volume_m3: float  # 持液量
    vessel_type: Literal["VERTICAL", "HORIZONTAL", "WITH_DEMISTER"]
    K_factor_ms: float    # 实际使用 K 因子
    residence_time_min: float  # 实际使用停留时间
    check_result: Literal["PASS", "WARNING", "FAIL"]
    confidence: Literal["HIGH", "MEDIUM", "LOW"]
```

---

## 决策 6：VesselResult ORM 当前 4 列足够，P5-1-4 评估是否下沉

**现状**（P5-0-4a closure，commit 34ab33e）：
- `vessel_results` 表 PK = `vessel_id`（已 rename closure）
- 当前列：PK + `input_json` + `output_json` + `design_stage`
- 继承 TaggedRecordMixin → `project_id` / `workspace_id` / `tag_number` / `sign_status` / `approval_*` / `record_hash`

**P5-1-4 plan §P5-1-4 L196 要求**：13 字段 roundtrip（vessel_type / D_min / V_max / K_factor / liquid_volume / residence_time / 校验 / confidence 等）。

**裁定**：
- P5-1-1 业务字段全部进 `output_json`（VESSEL_OUTPUT_KEYS 字典）：`vessel_type` / `D_min_m` / `V_max_ms` / `K_factor_ms` / `liquid_volume_m3` / `residence_time_min` / `check_result` / `confidence`
- P5-1-4 实施前**重新评估**：如果 13 字段频繁查询/索引，下沉到 ORM 列；如果仅 roundtrip 用途，继续 JSONB
- **不预先下沉**（避免空壳字段；待 P5-1-4 有明确查询场景再补列）

**P5-1-4 跟踪项**：13 字段下沉评估 + outlet_stream Literal 扩展 `"VESSEL"` + REGISTRY 注册 VesselResult。

---

## 决策影响段（与 ADR-0027 / ADR-0030 交叉引用）

- **ADR-0027 V1.0**：HEAT 双轨 P5-0-2 落地，与 VESSEL 共享 ChEDL 分层架构（决策 1 一致）
- **ADR-0030 V1.1 决策 6**：ChEDL 版本锁定 + 业务代码禁直接 import fluids（决策 1 严格继承）
- **PCS-PLAN §129 V1.7 问题 1**：ChEDL 函数签名确认（决策 4 交叉验证强制固化）
- **PCS-PLAN §134**：K 因子 SI 单位约定（决策 2 严格继承）
- **PCS-PLAN §131**：ChEDL 包装层集中封装（决策 1 + 决策 4 ChEDL 直调交叉验证）

---

## 版本历史

| 版本 | 日期 | 修改内容 |
|---|---|---|
| V1.0 | 2026-09-17 | 初始版本：P5-1-1 实施依据（6 项裁决） |