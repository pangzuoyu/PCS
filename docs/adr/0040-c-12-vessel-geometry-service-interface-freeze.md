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

- **SPEC-ADD-001 V1.2 已冻结**（公式 + Literal 枚举拼写已锁）
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
| **F5 公式行为** | 4 封头 × 3 容器形 = 12 路径（见 SPEC §3.4.4） | 6 + 5 黄金 fixture（误差 <0.1%） |
| **F6 公共符号导出** | vessel 子模块 `__init__.py` 暴露 9 新符号 | `hasattr` 测试 |
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
  n_vessels: int = 1          # default 1
```

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
  mass_model: Literal["OPERATING"] = "OPERATING"   # EMPTY 未实现
```

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

1. **签名快照测试**（已落地）：
   `pcs-backend/tests/services/vessel/test_vessel_interface_freeze.py` 11 个测试：
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

2. **黄金 fixture 测试**（已落地）：
   - `tests/services/vessel/fixtures/golden_vessel_partial_volume.json`（6 例）
   - `tests/services/vessel/fixtures/golden_vessel_wetted_area.json`（5 例）
   - `tests/services/vessel/test_partial_volume.py` + `test_wetted_area.py` + `test_mass_iteration.py` 共 17 测试

3. **CI 强制**：
   - ruff 0 errors（`uv run ruff check .`）
   - pytest 必须 100% 通过

### 复审触发

- **2027-01-25**（冻结 4 个月时）：中期复审，确认是否需要提前解冻
- **2027-03-25**（冻结到期）：自动解冻，回归 status quo；如需续冻，起草 ADR-0042

## References

- SPEC §3.4.4 C-12 部分填充体积 + 润湿面积 + 质量迭代（V1.2 冻结）
- SPEC-ADD-001 计算覆盖增补规格说明书
- ADR-0008 D5 工艺计算函数契约冻结模板（6 个月基线）
- ADR-0017 P5-1-1 工艺计算服务化（P5-1 计算服务拆分先例）
- WS-CA-PR-013 Rev A 立式容器算例（黄金 fixture 来源）
- OpenWolf P6-4-batch plan: docs/superpowers/plans/2026-09-25-p6-4-batch.md
- item 37: D7 接口冻结 ADR（待办原文）

## Freeze Window Summary

| 起始 | 终止 | 持续 | 检测 |
|------|------|------|------|
| 2026-09-25 | 2027-03-25 | 6 个月 | `test_vessel_interface_freeze.py` |