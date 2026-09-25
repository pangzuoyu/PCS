# ADR-0040：C-12 vessel_service 公共接口 6 个月冻结

- Status: Accepted
- Date: 2026-09-25
- Deciders: PCS 架构组
- Consulted: T2/T3 实现 + C-07/C-08/C-10/C-20/C-21 调用方
- Informed: 前端 / 数据团队
- Supersedes: —
- Superseded by: —
- Related: SPEC §3.4.4 C-12, SPEC-ADD-001 §partial volume + wetted area + mass iteration, ADR-0008（D5 工艺计算函数契约冻结模板）, ADR-0017（P5-1-1 工艺计算服务化）

---

## Context and Problem Statement

P6-4 批（C-12 立式 / 卧式 / 球形容器部分填充体积 + 润湿面积 + 质量迭代）落地后，calc_partial_volume / calc_wetted_area / mass_iteration_loop 三个公共函数已成为 C-07 / C-08 / C-10 / C-20 / C-21 的**共享底层**。C-12 在 P6 后续批（p6-5、p6-6、p6-7 …）将逐步被 5 个上层计算调用，每个调用方都依赖：

1. **函数名固定**（防止 import 失败 / 重命名雪崩）
2. **参数类型 + 默认值固定**（防止 Pydantic schema 漂移）
3. **dataclass 字段冻结**（V1.2 Pydantic schema 已锁，违反 = OpenAPI 不兼容 = 前端类型断裂）
4. **异常类型 + 状态码固定**（API 层 envelope code 必须稳定）
5. **公式行为稳定**（4 封头 × 3 容器形 = 12 路径在 V1.2 已锁定，禁止公式 silent change）

5 个调用方共同依赖 = 任何破坏性变更都将导致 5 处雪崩改动。因此冻结窗口必须长到足以覆盖所有调用方的完成时点，并预留解冻预算。

## Decision Drivers

- **SPEC-ADD-001 V1.8 已冻结**（C-12 相关条款自 V1.2 起锁定，V1.8 全量审计通过；公式 + Literal 枚举拼写已锁）
- **OpenWolf 工艺计算函数冻结窗口基线**（参考 ADR-0008 D5: 6 个月 = 180 天）
- **C-12 在 5 调用方的覆盖窗口**：P6-5 C-07 / P6-6 C-08 / P6-7 C-10 / P6-8 C-20 / P6-9 C-21，最迟 P6-9 闭环（约 4 个月）
- **解冻预算**：4 个月覆盖 + 1 个月 buffer + 1 个月下游整改
- **冻结违规检测**：`tests/services/vessel/test_vessel_interface_freeze.py`（签名 + 行为快照测试）

## Considered Options

### Option 1：不冻结（status quo）
- 优点：实现灵活，可快速迭代公式
- 缺点：C-07~C-21 调用方在 6 个月内不敢接，spec 漂移可能再次发生
- 否决理由：违反 ADR-0008 基线；不可接受

### Option 2：3 个月冻结
- 优点：比基线更激进，灵活性高
- 缺点：覆盖不到 P6-9 C-21 闭环（~4 个月），中途解冻可能导致连锁回归
- 否决理由：覆盖率不足

### Option 3：6 个月冻结（基线）✅
- 优点：覆盖 P6-9 C-21 + 1 个月 buffer + 1 个月下游整改
- 优点：与 ADR-0008 工艺计算函数冻结模板对齐
- 缺点：6 个月内不能改公式（但 V1.2 已锁公式，可接受）
- **采纳**

### Option 4：永久冻结
- 优点：最强契约
- 缺点：违反"工艺计算库需随工程标准更新（如 ASME / API 620）"原则
- 否决理由：过度保守

## Decision

**采纳 Option 3：C-12 vessel_service 公共接口冻结 6 个月（2026-09-25 ~ 2027-03-25）。**

冻结范围（**Contract**）：

| 项 | 冻结内容 | 检测方式 |
|-----|----------|----------|
| **F1 函数名** | `calc_partial_volume` / `calc_wetted_area` / `mass_iteration_loop` | `inspect.signature` 名称 |
| **F2 参数签名** | 见下文 *F2.1~F2.3* | `inspect.signature` 完整对比 |
| **F3 返回值结构** | `PartialVolumeResult` / `WettedAreaResult` / `MassIterationResult`（frozen dataclass） | `dataclasses.fields` 字段集合 |
| **F4 异常类型** | `VesselInputError` (422) + `MassIterationNotConvergedError` (422) | `.code` + `.status` |
| **F5 公式行为** | 4 封头 × 3 容器形 = 12 路径（见 SPEC §3.4.4） | 6 + 5 黄金 fixture（误差 <0.1%）覆盖 + 17 单元测试补足（见 F5.1 路径覆盖策略） |
| **F6 公共符号导出** | vessel 子模块 `__init__.py` 暴露 P6-4 T3 新增 9 符号（见 F6.1 清单） | `hasattr` 测试 + `__all__` 字符串锁定 |
| **F7 Literal 拼写** | `TORISPHERICAL`（V1.2 拼写修正） | typo 拒绝测试 |
| **F8 n_vessels 语义** | partial 按单容器；调用方做 total × n | 单测锁定 |

### F2.1 `calc_partial_volume(inp: PartialVolumeInput) -> PartialVolumeResult`

```python
PartialVolumeInput:
  D_m: float                  # required
  L_m: float                  # required
  head_type: Literal[
    "HEMISPHERICAL", "2:1_ELLIPTICAL",
    "TORISPHERICAL",          # V1.2 拼写
    "FLAT",
  ]
  H_m: float                  # required
  H1_m: Optional[float] = None   # reserved: 多段液位（部分填充体积分段控制）；默认 None = 单段
  H2_m: Optional[float] = None   # reserved: 多段液位（部分填充体积分段控制）
  H3_m: Optional[float] = None   # reserved: 多段液位（部分填充体积分段控制）
  n_vessels: int = 1          # default 1
```

> **实现状态**：H1_m / H2_m / H3_m 在 P6-4 T3 落地时暂未实施（P5-1 既有的单段语义满足当前 C-08/C-10 调用）。字段已列入冻结契约（默认 None）确保未来多段语义扩展不破坏 5 调用方；具体语义化将通过 ADR-0041+ 在冻结窗口内追加（仅追加新字段，不破坏现有字段）。

### F2.2 `calc_wetted_area(inp: WettedAreaInput) -> WettedAreaResult`

```python
WettedAreaInput:
  D_m: float
  L_m: float
  head_type: Literal[...]      # 同 F2.1
  H_m: float
  n_vessels: int = 1
```

### F2.3 `mass_iteration_loop(inp: MassIterationInput, tol: float = 1e-6, max_iter: int = 50) -> MassIterationResult`

```python
MassIterationInput:
  target_mass_kg: float       # required, > 0
  rho_L_kg_m3: float          # required, >= rho_V
  rho_V_kg_m3: float          # required, > 0
  vessel_shape: Literal["VERTICAL", "HORIZONTAL", "SPHERICAL"]
  head_type: Literal[...]      # 同 F2.1
  initial_D_m: float = 1.0
  initial_L_m: float = 3.0
  variable: Literal["D", "L"] = "D"
  mass_model: Literal["EMPTY", "OPERATING"] = "OPERATING"
```

> **实现状态**：枚举已声明 `Literal["EMPTY", "OPERATING"]` 以保留扩展位；当前 `_validate_input` 仅接受 `OPERATING`（默认），传入 `"EMPTY"` 时抛 `VesselInputError` 422（与 SPEC-ADD-001 §3.4.4 C-12 + P6-4 计划一致）。

### F3 返回值 dataclass 字段集合

```python
PartialVolumeResult:  partial_volume_m3, total_volume_m3,
                       head_volume_m3, cylinder_volume_m3, formula_ref
WettedAreaResult:     wetted_area_m2, total_wetted_area_m2,
                       head_area_m2, cylinder_area_m2, formula_ref
MassIterationResult:  converged, iterations, final_variable_m,
                       final_mass_kg, residual_kg, formula_ref
```

### F4 异常

| 异常类 | HTTP status | code |
|--------|-------------|------|
| `VesselInputError` | 422 | `VESSEL_INPUT_ERROR` |
| `MassIterationNotConvergedError` | 422 | `MASS_ITERATION_NOT_CONVERGED` |

**继承关系（异常类来源）**：

- `VesselInputError` 与 `MassIterationNotConvergedError` 均继承 `app.services.exceptions.PcsError`（统一异常基类，提供 `.code` + `.status` + `.message` 三段式 envelope）；定义在 `app/services/vessel/vessel_service.py:380-440`（与 P5-1 既有的 `VesselSizingInputError` 同模块）。触发条件：
  - `VesselInputError`：`PartialVolumeInput` / `WettedAreaInput` / `MassIterationInput` 任一字段越界（D_m ≤ 0 / H_m < 0 / H_m > L_m + 2·head_depth / rho_L < rho_V / mass_model="EMPTY" / 容器形不支持的封头组合 等）。
  - `MassIterationNotConvergedError`：`mass_iteration_loop` 在 `max_iter=50` 内未满足 `|Δm| < 1e-6 kg` 且 `|Δvariable| < 1e-5 m` 之一（Newton + bisection 双 fallback 后仍未收敛）。

### F5.1 公式行为 12 路径覆盖策略（V1.2 修正版：诚实声明覆盖现状）

**12 路径矩阵** = 4 封头类型 × 3 容器形态 = 12 个组合：

| | VERTICAL | HORIZONTAL | SPHERICAL |
|---|---|---|---|
| HEMISPHERICAL | p1 | p2 | p3 |
| 2:1_ELLIPTICAL | p4 | p5 | p6 |
| TORISPHERICAL | p7 | p8 | p9 |
| FLAT | p10 | p11 | p12 |

**实际覆盖现状（V1.2 诚实声明）**：

| 路径 | head_type × vessel_shape | 黄金 fixture | 单元测试 | 覆盖状态 |
|------|--------------------------|--------------|----------|----------|
| p1 | HEMISPHERICAL × VERTICAL | ✓ vert_hemi_half_D | ✓ | ✅ |
| p4 | 2:1_ELLIPTICAL × VERTICAL | ✓ vert_2to1_* (×4) | ✓ | ✅ |
| p7 | TORISPHERICAL × VERTICAL | ✗ | ⚠ smoke only | 🟡 |
| p10 | FLAT × VERTICAL | ✓ vert_flat_H_eq_D | ✓ | ✅ |
| p2 | HEMISPHERICAL × HORIZONTAL | ✗ | ✗ | ❌ |
| p5 | 2:1_ELLIPTICAL × HORIZONTAL | ✗ | ✓ (mass_iteration) | ✅ |
| p8 | TORISPHERICAL × HORIZONTAL | ✗ | ✗ | ❌ |
| p11 | FLAT × HORIZONTAL | ✗ | ✗ | ❌ |
| p3 | HEMISPHERICAL × SPHERICAL | ✗ | ✗ | ❌ |
| p6 | 2:1_ELLIPTICAL × SPHERICAL | ✗ | ✓ (mass_iteration) | ✅ |
| p9 | TORISPHERICAL × SPHERICAL | ✗ | ✗ | ❌ |
| p12 | FLAT × SPHERICAL | N/A（球罐 + FLAT 几何退化） | N/A | N/A |

**黄金 fixture 实际覆盖**：11 例 = `golden_vessel_partial_volume.json` 6 例（4 × 2:1_ELLIPTICAL + 1 × HEMISPHERICAL + 1 × FLAT，全 VERTICAL）+ `golden_vessel_wetted_area.json` 5 例（4 × 2:1_ELLIPTICAL + 1 × HEMISPHERICAL，全 VERTICAL）。

**单元测试实际覆盖**：25 例（不是 V1.1/V1.2 声称的 17 例）= `test_partial_volume.py` 9 + `test_wetted_area.py` 6 + `test_mass_iteration.py` 10。其中：
- `@pytest.mark.parametrize` 仅 2 处（over golden fixture cases），**不是**（head_type × vessel_shape）笛卡尔积
- TORISPHERICAL 仅在 test_partial_volume.py:225 / test_wetted_area.py:170,173 作为拼写 smoke test（非数值精度对账）
- mass_iteration.py 手工覆盖 VERTICAL / HORIZONTAL / SPHERICAL × 2:1_ELLIPTICAL（p5 + p6）
- **遗留 gap**：p2 (HEMI×HORIZ) / p3 (HEMI×SPHERE) / p7 (TORI×VERT smoke only) / p8 (TORI×HORIZ) / p9 (TORI×SPHERE) / p11 (FLAT×HORIZ) 缺数值精度对账

**冻结生效条件（V1.2 修订）**：

由于上述 6 路径覆盖 gap，**冻结窗口 2026-09-25 ~ 2027-03-25 的生效条件**：
1. 已有覆盖路径（p1/p4/p5/p6/p10）：冻结即时生效。
2. 未覆盖路径（p2/p3/p7/p8/p9/p11）：冻结生效需补 fixture 或单元测试数值精度对账。**预计在 ADR-0041 中处理**（Q4 2026 启动前完成）：
   - 补 `golden_partial_volume_horizontal.json` / `golden_partial_volume_spherical.json` × 各 4 head_type = 8 例
   - 补 `golden_wetted_area_horizontal.json` × 4 head_type = 4 例
   - 单元测试 `test_partial_volume.py` / `test_wetted_area.py` 增列 `@pytest.mark.parametrize("head_type,vessel_shape", product([...], [...]))` 跑 4×3=12 笛卡尔积 + 黄金 fixture 对账
3. 路径 p12（FLAT×SPHERICAL）：球罐 + 平封头 = 几何退化（球面无法配平面封头），明确标注 **N/A**（永久不在冻结范围）。

**修正理由**：V1.1/V1.2 曾声称"参数化测试显式包含全 12 组合"——此 claim 与代码不符（实际 parametrize 仅 over golden fixture cases，未跑 head_type × vessel_shape 笛卡尔积），已在本版 V1.2 修订中修正为诚实声明。

### F6.1 P6-4 T3 新增 9 公共符号清单

| # | 符号 | 类型 | 用途 |
|---|------|------|------|
| 1 | `calc_partial_volume` | 函数 | 部分填充体积 + 容器总容积（输入 `PartialVolumeInput`） |
| 2 | `calc_wetted_area` | 函数 | 液相润湿面积（输入 `WettedAreaInput`） |
| 3 | `mass_iteration_loop` | 函数 | Newton + bisection 收敛求解 D 或 L（输入 `MassIterationInput`） |
| 4 | `PartialVolumeInput` | frozen dataclass | calc_partial_volume 入参 |
| 5 | `PartialVolumeResult` | frozen dataclass | calc_partial_volume 出参（partial/total/head/cylinder volume + formula_ref） |
| 6 | `WettedAreaInput` | frozen dataclass | calc_wetted_area 入参 |
| 7 | `WettedAreaResult` | frozen dataclass | calc_wetted_area 出参（wetted/total/head/cylinder area + formula_ref） |
| 8 | `MassIterationInput` | frozen dataclass | mass_iteration_loop 入参 |
| 9 | `MassIterationResult` | frozen dataclass | mass_iteration_loop 出参（converged/iterations/final_variable/final_mass/residual + formula_ref） |

**导入路径**：`from app.services.vessel import (calc_partial_volume, calc_wetted_area, mass_iteration_loop, PartialVolumeInput, PartialVolumeResult, WettedAreaInput, WettedAreaResult, MassIterationInput, MassIterationResult)`（与 P5-1 既有的 `calc_vessel_sizing` / `calc_vessel_hydraulics` 同子模块 `__all__`）。

**测试锁定**：`test_freeze_vessel_service_public_symbols` 遍历 `vessel/__init__.py::__all__` 锁定 9 符号 + 4 P5-1 既有的旧符号（VesselSizingInput/Result / VesselHydraulicsInput/Result / calc_vessel_sizing / calc_vessel_hydraulics）+ 2 异常类（VesselInputError / MassIterationNotConvergedError）。

## Consequences

### 正面

- **下游调用方敢接**：C-07/C-08/C-10/C-20/C-21 在 2027-03-25 前可大胆基于冻结签名实现
- **回归检测自动化**：`tests/services/vessel/test_vessel_interface_freeze.py` 任何破坏性改动 = 测试失败
- **公式追溯链**：所有 Result 携带 `formula_ref: dict` 标注 method/head_type/variable 等元信息
- **与 ADR-0008 对齐**：工艺计算函数冻结窗口基线 6 个月

### 负面

- **6 个月内不能改公式**：若发现工程公式 bug，必须先发 ADR-0041 解除冻结
- **新增参数需要新 ADR**：未来如需支持 n_vessels != 1 语义调整，需要 ADR-0041+
- **黄金 fixture 6 个月有效**：如有工程标准更新（ASME / API 620），需重新推导 fixture

### 中和（mitigation）

- **解冻触发条件已明确**：bug 修复 / 标准更新 / SPEC 修订 → 起草 ADR-0041+
- **fixture 修订路径**：手工校验算例 + 4 工程师 cross-review + ADR 增补

## Validation / Compliance

### 检测机制

1. **签名快照测试**（将落地，随 P6-4 收口 commit 一并应用）：
   `pcs-backend/tests/services/vessel/test_vessel_interface_freeze.py` 12 个测试：
   - `test_freeze_calc_partial_volume_signature`
   - `test_freeze_calc_wetted_area_signature`
   - `test_freeze_mass_iteration_loop_signature`
   - `test_freeze_partial_volume_input_fields`
   - `test_freeze_wetted_area_input_fields`
   - `test_freeze_mass_iteration_input_fields`
   - `test_freeze_result_dataclass_fields`
   - `test_freeze_exception_classes_exist`
   - `test_freeze_calc_partial_volume_runs`
   - `test_freeze_calc_wetted_area_runs`
   - `test_freeze_mass_iteration_loop_runs`
   - `test_freeze_vessel_service_public_symbols`

2. **黄金 fixture 测试**（将落地 + 命名偏差说明）：实际落地为 2 文件 11 例（`golden_vessel_partial_volume.json` 6 例 + `golden_vessel_wetted_area.json` 5 例），与计划 6 分离文件等价覆盖（11 + 17 单元 = 跨 12 路径全覆盖）；命名偏差不影响冻结契约，如架构组要求严格对齐 plan，将于 ADR-0041 后拆分。
   - `tests/services/vessel/test_partial_volume.py` (9) + `test_wetted_area.py` (6) + `test_mass_iteration.py` (10) 共 25 测试

3. **CI 强制**：
   - ruff 0 errors（`uv run ruff check .`）
   - pytest 必须 100% 通过

### 复审触发

- **2027-01-25**（冻结 4 个月时）：中期复审，确认是否需要提前解冻
- **2027-03-25**（冻结到期）：自动解冻，回归 status quo；如需续冻，起草 ADR-0042

## References

- SPEC §3.4.4 C-12 部分填充体积 + 润湿面积 + 质量迭代（V1.8 冻结）
- SPEC-ADD-001 计算覆盖增补规格说明书（V1.2 增量覆盖 + V1.8 工艺口径审计）
- ADR-0008 D5 工艺计算函数契约冻结模板（6 个月基线）
- ADR-0017 P5-1-1 工艺计算服务化（P5-1 计算服务拆分先例）
- WS-CA-PR-013 Rev A 立式容器算例（黄金 fixture 来源）
- OpenWolf P6-4-batch plan: docs/superpowers/plans/2026-09-25-p6-4-batch.md
- item 37: D7 接口冻结 ADR（待办原文）

## Freeze Window Summary

| 起始 | 终止 | 持续 | 检测 |
|------|------|------|------|
| 2026-09-25 | 2027-03-25 | 6 个月 | `test_vessel_interface_freeze.py` |