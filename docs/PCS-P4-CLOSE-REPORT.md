# PCS-P4 验收报告（核心引擎）

> 范围：批 0~4 + P4-TASK0，21 task 全闭环。
> 验收基线：HEAD = `cc2fcab`（含 `c9ee2e0` P4-TASK0 ontology）。
> ledger：`.superpowers/sdd/PCS-PLAN-P4-CORE-ENGINE/progress.md`（本地维护）。

## 一、范围

P4 = PCS 核心工艺引擎，含 **数据层 + 工艺计算 + 落库 + 审计门禁 + 本体论**。工艺室日常计算场景的最小完备集：闪蒸 / 管道 / 管网 / 泵。

## 二、任务清单（21 task）

### 批 0 — 数据层（3 task）

| task | commit | 关键交付 |
|---|---|---|
| P4-0-1 审计字段 + lineage helper | `e72116f` + R1 `422f014` | record_hash 6 位有效数字规范化；DataLineage 只追加；finalize_calc_record 统一收口 |
| P4-0-2 SUP-008 表扩展 + two_phase_results | `9d14ebf` | 5 表（flash / piping / two_phase / pipe_network / pump）+ 9 态 check_result |
| P4-0-3 计算入口守卫 | `3fcfea0` | check_calc_inputs 三步守卫（exists → CHECKED → unreliable） |

### 批 1 — FLASH（5 task）

| task | commit | 关键交付 |
|---|---|---|
| P4-1-1 thermo 封装 | `04a40b9` | 4 体系 Protocol（PRMIX/SRKMIX/NRTL/iapws95） |
| P4-1-2 8 calc（PT/PH/PS/BUBBLE/DEW/SAT） | `594e8e1` + `53aeefd` + `fed95a7` | step1~3 串行 |
| P4-1-3 FLASH API + 落库 + 状态点联动 + 出口物流 | `3cc1944` | outlet_stream helper（ADR-0022 模式） |
| P4-1-4 SIM 反向写入 | `25c6d06` | P3.2 SIM 产出接回 P4 数据层 |

### 批 2 — PIPE（5 task）

| task | commit | 关键交付 |
|---|---|---|
| P4-2-1 PipeSizing | `8c30fdb` | HG/T 20570.6-95 预定流速法 / 设定压力降法 |
| P4-2-2 WallThickness | `2786151` | ASME B31.3 + 18 OD 档 Sch 表 |
| P4-2-3 单相压降 | `ff31ccc` + R1 `308ae20` | Darcy-Weisbach + 精度护栏（R1 线性插值 [2320,4000]） |
| P4-2-4 两相压降 | `3ffe313` | Lockhart-Martinelli-Baker；6 流型；M1 record_hash 待 P4-TASK0 补 |
| P4-2-5 PipeChain + outlet_stream | `04a9b6d` | 链式 confidence 聚合（任一 LOW→整体 LOW，任一 TRANSITION→WARNING） |

### 批 3 — PIPE_NET（3 task）

| task | commit | 关键交付 |
|---|---|---|
| P4-3-1 拓扑模型 | `9714aae` | 10 校验规则（连通性、SOURCE/SINK、≤500 节点） |
| P4-3-2 Hardy-Cross 求解器 | `6eaabde` | BFS 找环 + n=1/2 + 5% 相对容差 |
| P4-3-3 API + 落库 + outlet_stream | `a4aed2f` + R1 `e0a3bfe` | 管网 calc PIPE_NET 单行落库 |

### 批 4 — PUMP（4 task）

| task | commit | 关键交付 |
|---|---|---|
| P4-4-1 泵选型 | `ccbd102` + R1 `9f5e576` | 比转速 ns + API 610 OH2/OH3/BB1/BB3/VS1 |
| P4-4-2 NPSHa | `360bdc9` | ANSI/HI 9.6.6-2016；confidence 透传 |
| P4-4-3 泵曲线插值 | `764e917` | 线性插值（无外推）；distance_from_rated_pct |
| P4-4-4 PUMP 链 + outlet_stream | `e6949e5` | select → NPSHa → curve 三步链 |

### P4-TASK0 — 本体论（1 task）

| task | commit | 关键交付 |
|---|---|---|
| P4-TASK0 ontology | `c9ee2e0` | D4/D5 lineage +4 字段；RECORD_TYPE_REGISTRY 5 类；physical_semantics 自实现；importlinter D8 4 层；CI baseline 3 cases |

## 三、工艺能力清单（已落地）

- **闪蒸 FLASH**：PT/PH/PS_FLASH + BUBBLE_P/T + DEW_P/T + SATURATION（4 thermo 体系）
- **管道 PIPE**：预定流速法 + 设定压力降法 + ASME B31.3 壁厚 + 单相 Darcy-Weisbach + 两相 Lockhart-Martinelli-Baker + 链式管道
- **管网 PIPE_NET**：拓扑校验 + Hardy-Cross 流量分配 + 节点压力回推
- **泵 PUMP**：选型（API 610）+ NPSHa + 曲线插值 + 链式集成
- **出口物流 outlet_stream**：`source_type ∈ {FLASH, PIPE, PUMP, PIPE_NET}` 统一 helper（sign_status=DRAFT）
- **精度护栏**：3 流态（LAMINAR/TRANSITION 2000–4000 强制 WARNING/TURBULENT）+ Crane TP-410 K 表 `reynolds_applicable` 标注 + confidence HIGH/MEDIUM/LOW + 链式 worst-wins 聚合 + NPSHa 不能 PASS at LOW confidence

## 四、关键技术决策

| 决策 | 锚点 | 要点 |
|---|---|---|
| 两层模型 | ADR-0001 | 计算记录（数据门禁 9 态）+ 交付物（签署矩阵） |
| 出口物流 ADR-0022 | helper | 设备是物流间转换函数，不是一条物流内部环节 |
| user-wins conflict_resolver | ADR-0019~0022 | 用户编辑优先于系统推断 |
| P4-TASK0 后置 | ADR-0031 | 批 0–4 子集先行；三条护栏（registry 占位 / finalize_calc_record 收口 / hash 6 位有效数字） |
| 数值规范化 | ADR-0031 | Float 列 6 位有效数字 → sha256 截断 16 hex（hash 幂等） |

## 五、测试与质量基线

- **全量回归**：`pcs_test` 库 **1603 passed / 0 failed / 0 error**（75.7s）
- **新增测试**：P4 期间累计 +60+ 例（golden fixture 手算 + 流型/校核/roundtrip/边界）
- **ruff**：`uv run ruff check .` → All checks passed
- **alembic**：`pcs_test uv run alembic upgrade head` OK（P4-TASK0 lineage 扩展迁移已对齐）

## 六、Backlog（P5+）

按优先级：

1. **Hooper 2-K / Darby 3-K** 低 Re K 值修正（`get_fitting_k` Re 参数预留位已留，P4-2-5 / P4-2-3 阶段共识）
2. **ChEDL 版本锁定 ADR**（fluids / thermo / chemicals 频繁更新，需复现性）
3. **`fluids.two_phase` Beggs-Brill** 交叉校核（当前仅 Lockhart-Martinelli-Baker）
4. **`fluids.fittings` K_from_f** 交叉校核（K 表本地化真源已就位）
5. **P4-2-6** 热损失 + 混合黏度（链式管道 outlet_temperature_K 接管 + ρgΔz 修正）
6. **JUNCTION** demand 初始流量扣除（管网初始猜测精度）
7. **CIA 引擎**（hash_changed / changed_fields / STALE→CHANGE_PENDING 传播）
8. **控制阀 / PSV**（独立批次；不在 P4 范围）

## 七、验收建议

**结论**：**P4 通过验收**。

理由：
- 21 task 全闭环（实施 + 审查双轨）
- 测试基线 1603 passed / 0 failed
- ruff 0 错
- ADR-0031 P4-TASK0 闸门解除
- 工艺能力覆盖工艺室日常计算最小完备集（闪蒸 / 管道 / 管网 / 泵）
- 精度护栏在 NPSHa / 链式管道 / 过渡区已布防
- 风险点（ChEDL 版本、Hooper 2-K、Beggs-Brill）已 backlog 化

可进入 P5+ 实施周期。