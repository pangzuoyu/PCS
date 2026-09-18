---
status: accepted
date: 2026-09-19
proposed_by: P6-0 架构负责人
accepted_by: 用户 2026-09-19 G-01 核验触发裁决
related: [ADR-0030 V1.2, P6 SPEC V2.0 §3.2.6, G-01 核验报告]
supersedes: P6 SPEC §4.2 P6-OPEN-001（"待验证"→"自研兜底"）
---

# P6-OPEN-001 裁决：OPEN_CHANNEL 模块自研兜底（fluids.open_channel API 缺失）

## 一、触发门禁

G-01（`fluids.open_channel` API dir() 前置核验），核验脚本：

- `pcs-backend/scripts/p6_0_gate_01_open_channel_dir.py`
- 报告：`docs/p6-gate-reports/gate-01-open-channel-api.json`

## 二、核验结论

| 项 | 值 |
|---|---|
| status | **degraded** |
| fluids 版本 | 1.3.1（pyproject 锁定） |
| SPEC 命名 `fluids.open_channel` | 不存在（ModuleNotFoundError） |
| 实际最近等价路径 | `fluids.open_flow`（38 个导出符号） |
| REQUIRED 命中 | 1/5 — `V_Manning` |
| REQUIRED 缺失 | 4 — `Manning`, `Manning_flow`, `critical_depth`, `hydraulic_radius` |

## 三、缺失函数清单与兜底实现路径

| 缺失函数 | 自研实现路径（参照 ADR-0030 决策 7 自研兜底模式） |
|---|---|
| `Manning`（粗糙度 → 谢才系数 C） | 自研：Chézy 公式 `C = R^(1/6) / n`（R = 水力半径，n = Manning 粗糙度系数）；与 `fluids.open_flow.C_Chezy_to_n_Manning` 互校 |
| `Manning_flow`（已知水深求流量） | 自研：Manning 公式 `Q = (1/n) × A × R^(2/3) × S^(1/2)`；A / R 由断面几何函数给出（梯形/矩形/圆形） |
| `critical_depth`（临界水深） | 自研：Froude 数判定 `Fr = V / √(g·D_h) = 1`；矩形断面临界水深 `y_c = (q²/g)^(1/3)`；一般断面迭代求解 `Q²/g = A³/T` |
| `hydraulic_radius`（水力半径） | 自研：`R = A / P`（A 断面面积，P 湿周）；按断面类型分别实现 |
| `V_Manning` | ✅ 已有（`fluids.open_flow.V_Manning`），包装层直连 |

## 四、兜底架构

按 ADR-0030 决策 7（fluids.tanks 双套测试模式）：

1. 包装层 `app/services/open_channel/open_channel_wrapper.py` 内部透明 fallback：优先调用 `fluids.open_flow.*`（如 `V_Manning`），其余缺失函数走自研几何 + Manning 公式 + 临界水深迭代
2. `formula_ref.source` 由包装层返回，业务层不判断（保持业务无感知）
3. 自研函数双套测试：`test_<func>_self_implemented`（始终执行）+ `test_<func>_with_chedl`（`skipif not hasattr` 守卫）

## 五、影响范围

- **OPEN_CHANNEL 模块**（P6-3 Task 31）：实施按本兜底架构推进；不阻塞 P6-3 启动
- **chedl_wrapper.py**：本批次不修改（OPEN_CHANNEL 包装层在 P6-3 Task 31 内独立新增 `app/services/open_channel/open_channel_wrapper.py`，不混入 P5 的 chedl_wrapper）
- **G-01 闸门条件**：本裁决关闭；P6-3 OPEN_CHANNEL 实施不再以 `fluids.open_channel` API 可用性为前置

## 六、Owner

- 待工艺工程师（OPEN_CHANNEL Manning n 值取值 / 临界水深 / 水跃共轭水深公式细节评审 + 自研函数 golden 值校核）
- P6-0 架构负责人：本兜底架构评审与包装层契约确认

## 七、关联文档

- ADR-0030 V1.2（ChEDL 版本锁定 + dir() 前置核验 + 决策 7 降级预案）
- P6 SPEC V2.0 §3.2.6 OPEN_CHANNEL + §4.2 P6-OPEN-001 待确定问题
- G-01 核验报告：`docs/p6-gate-reports/gate-01-open-channel-api.json`
- P6 实施计划：`docs/superpowers/plans/2026-09-19-p6-batch.md`

## 八、结论

P6-OPEN-001 由"待验证"关闭为"自研兜底（ADR-0030 决策 7 模式）"。OPEN_CHANNEL 模块按自研 + 部分 ChEDL 包装（仅 `V_Manning`）实施，G-01 闸门条件满足，P6-3 Task 31 可启动。