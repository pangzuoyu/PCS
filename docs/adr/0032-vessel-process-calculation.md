---
status: accepted
date: 2026-09-17
proposed_by: P5 架构评审委员会（P5-1-1 起草组）
accepted_by: 用户 2026-09-17 OPEN-2/3 裁决
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

## 决策 2：K 因子单位约定 SI m/s + vessel_type 子区间（V1.1 修订）

**V1.0 现状**：决策 2 初版用宽典型区间 (0.04, 0.15) 开区间（GPSA SI 通用范围），vessel_type 仅作推荐子区间参考，**不影响 HIGH/MEDIUM 判定**。P5-1-1 落地后，fixture 6 例 / boundary tests 按 (0.04, 0.15) 验证。

**V1.1 用户 2026-09-17 OPEN-2 裁决**：以"更保守经典值"为最终依据，**vessel_type 子区间生效**（影响 HIGH/MEDIUM 判定）。

**裁定**（V1.1 accepted）：
- P5-1 业务代码 **统一 SI m/s**
- **vessel_type 子区间**（开区间，边界值视为 MEDIUM 保守）：
  - 立式（VERTICAL）：**(0.01, 0.05)** m/s
  - 卧式（HORIZONTAL）：**(0.05, 0.11)** m/s
  - 带除沫器（WITH_DEMISTER）：**(0.04, 0.10)** m/s
- 物理合理范围（K 越界异常）：**[0.01, 1.0] m/s**
- K 严格落在 vessel_type 子区间内 → `HIGH`（典型工况）
- K = 子区间边界值 或 子区间外但 [0.01, 1.0] 内 → `MEDIUM`（保守）

**换算依据**：1 ft/s = 0.3048 m/s。SPEC §3.2.1 原写"立式 0.03~0.15 / 卧式 0.15~0.35"为英制 GPSA ft/s 经典值；本 V1.1 改 SI m/s。

**SPEC 修订**（同 commit 同步）：spec/P5.md §3.2.1 K 因子取值文本 + 加 "SI m/s" 单位标注。

**CONFIG 种子数据**：`app/seeds/category3_defaults.json` 后续补 VESSEL K 因子种子（vessel_type 三档）；P5-1-1 暂硬编码（K 因子由调用方传入，不依赖 CONFIG）。

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

## 决策 4：6 测试覆盖 + K 边界 + 边界异常（V1.1 更新 vessel_type 子区间）

**6 例 golden fixture**（V1.1 用 vessel_type 子区间中心值 + 边界值）：
1. `vertical_basic`：VERTICAL, K=0.03 → 立式 (0.01, 0.05) 内 → PASS / HIGH
2. `horizontal_basic`：HORIZONTAL, K=0.08 → 卧式 (0.05, 0.11) 内 → PASS / HIGH
3. `vertical_with_demister`：WITH_DEMISTER, K=0.07 → 除沫器 (0.04, 0.10) 内 → PASS / HIGH
4. `horizontal_high_pressure`：HORIZONTAL, K=0.06 → 卧式 (0.05, 0.11) 内 → PASS / HIGH
5. `k_boundary_vertical`：VERTICAL, K=0.05 → 立式上界（边界）→ WARNING / MEDIUM
6. `k_boundary_horizontal`：HORIZONTAL, K=0.11 → 卧式上界（边界）→ WARNING / MEDIUM

**boundary tests**（K 越界 + 子区间边界）：
- K=0.01（立式下界 = 物理下界）→ MEDIUM（边界）
- K=0.05（立式上界）→ MEDIUM（边界）
- K=0.11（卧式上界）→ MEDIUM（边界）
- K=2.0（远超 1.0 上界）→ VesselInputError（422）

**交叉验证**：
- 与手算 V_max = K × √((ρ_L - ρ_V) / ρ_V) 偏差 ≤1%
- 与 ChEDL `v_Souders_Brown(K, rhol, rhog)` 直调偏差 ≤1%（PCS-PLAN §129 V1.7 问题1 强制）

**异常覆盖**：
- `liquid_flow_m3_s <= 0` → VesselInputError
- `vapor_flow_m3_s <= 0` → VesselInputError
- `rho_L <= rho_V`（密度倒置）→ VesselInputError
- `K_factor_ms` 超出 `[0.01, 1.0]` → VesselInputError

**置信度分类**（基于 K 因子 + vessel_type 子区间，V1.1）：
- K 严格落在 vessel_type 子区间内 → `HIGH`
- K = 子区间边界值 或 子区间外但 [0.01, 1.0] 内 → `MEDIUM`
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

## 决策 6：P5-1-4 落库 JSONB 双轨（不沉 13 列）

**V1.0 现状**：决策 6 初版"评估是否下沉 13 字段"，OPEN-3 待 P5-1-4 实施前裁决。

**V1.1 用户 2026-09-17 OPEN-3 裁决**：**P5-1-4 落库用 `input_json` + `output_json` 两 JSONB，不做 13 字段平铺**。

**裁定**（V1.1 accepted）：
- **scope**：
  - `vessel_results` 落库：`input_json`（VesselSizingInput + VesselHydraulicsInput）+ `output_json`（合并 sizing + hydraulics 结果）
  - `record_hash` + `data_lineage`：按现有 TaggedRecordMixin 机制
  - `outlet_stream`：扩展 `OutletSourceType` Literal `"VESSEL"`
- **不动 schema**（不增加 13 平铺列）
- **理由**：
  - 与 ADR-0027 HEAT 双轨结构一致（input_json / output_json 已存业务字段）
  - P5-1 后续变更（加字段）无需 alembic 迁移
  - 工作量小（vs 平铺 13 列 alembic 迁移 + ORM 字段 + roundtrip 测试）

**推迟**（不在 P5-1-4 scope）：13 列平铺下沉 → 若 P5-4 HEAT 或后续批次需 SQL 报表过滤，专项 migration；不阻塞 P5-1-4。

**P5-1-4 跟踪项**：
- 落库函数 `persist_vessel_calc(vessel_id, sizing_result, hydraulics_result)`
- API 路由 `POST /api/v1/vessel/{vessel_id}/calculate`
- outlet_stream Literal 扩展 `"VESSEL"`
- REGISTRY 注册 VesselResult（与 HEAT 一致）

---

## 决策影响段（与 ADR-0027 / ADR-0030 交叉引用）

- **ADR-0027 V1.0**：HEAT 双轨 P5-0-2 落地，与 VESSEL 共享 ChEDL 分层架构（决策 1 一致）
- **ADR-0030 V1.1 决策 6**：ChEDL 版本锁定 + 业务代码禁直接 import fluids（决策 1 严格继承）
- **PCS-PLAN §129 V1.7 问题 1**：ChEDL 函数签名确认（决策 4 交叉验证强制固化）
- **PCS-PLAN §134**：K 因子 SI 单位约定（决策 2 严格继承）
- **PCS-PLAN §131**：ChEDL 包装层集中封装（决策 1 + 决策 4 ChEDL 直调交叉验证）

---

## P5-1-3 EQUIP_LIB DEFERRED（V1.1 OPEN-1 登记）

**状态**：DEFERRED（阻塞 + 暂跳过）

**核实结果**（2026-09-17）：
- `equip_lib` 表名错误（实际名 `equipment_lib`，12 列含 equip_id/type_code/size/weight/material 等）
- `equipment_lib` 表结构存在，但 **0 行数据**（pcs + pcs_test 两库均空）
- 无 P2/P3 交付物可灌数据（equipment_lib 属业务数据，由用户/采购录入）

**DEFER 理由**：P5-1-3 `recommend_vessels` 是 EQUIP_LIB 匹配（按相似度返回相似设备列表）；空表下无可匹配数据 → 阻塞。

**后续路径**：
- 等业务侧提供 equipment_lib 数据源后启动 P5-1-3
- 或 P5-1-3 调整为"无 EQUIP_LIB 时返回空列表 + 推荐理由说明"
- 不阻塞 P5-1-4（API + 落库 + outlet_stream）

---

## 版本历史

| 版本 | 日期 | 修改内容 |
|---|---|---|
| V1.0 | 2026-09-17 | 初始版本：P5-1-1 实施依据（6 项裁决） |
| V1.1 | 2026-09-17 | 决策 2 K 因子 vessel_type 子区间（保守经典值：立式 0.01~0.05 / 卧式 0.05~0.11 / 除沫器 0.04~0.10）；决策 4 fixture 重设计 + 子区间影响 HIGH/MEDIUM；决策 6 P5-1-4 落库 JSONB 双轨决议（OPEN-3 用户裁定）；加 P5-1-3 DEFERRED 跟踪段（OPEN-1 equipment_lib 0 行核实结果）；status: accepted |