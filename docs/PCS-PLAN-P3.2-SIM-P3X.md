# PCS P3.2 SIM P3.x 续推计划 V1.0

| 项 | 值 |
|---|---|
| 计划版本 | V1.0 |
| 计划日期 | 2026-09-09 |
| 触发 | 用户裁决"所有项必须再进 P4 前解决"（2026-09-09） |
| 对照基准 | `docs/PCS-P3.2-SIM-AUDIT-V2.md`（30 项漏项 + 4 严重偏离 + 5 中度偏离） |
| 上游 | P3.2 SIM Sprint（14 task, 702 passing, 88% 覆盖, 2026-09-09 闭环 `7cdfc17`） |
| 总估时 | ~38d 串行 / ~20-25d 4 批并行 |
| 主负责人 | Claude (MiniMax-M3) + 用户裁决 |
| 关联审计 | `docs/PCS-P3.2-SIM-AUDIT-V2.md`（commit `949dd13`） |

---

## 0. 用户裁决（2026-09-09）

> "**所有项必须再进 P4 前解决**"

P3.2 SIM 14 task 闭环后留有 30 项偏离/漏项，4 严重偏离 + 5 中度偏离。本计划承接 30 项全部 P4 前闭环，**不分级、不分批分先后**，按依赖图分 4 批执行，**最终全部任务 must completed before P4 sprint kickoff**。

---

## 1. 范围

### 1.1 必做（用户强约束）

| 类别 | 数量 | 来源 |
|---|---|---|
| 严重偏离 | 4 项 | E-1（spec §5.5 7 表）/ E-2（PRO/II composition）/ E-3（ADD-002 §3.6 五 JSON）/ E-4（spec §6 API） |
| 中度偏离 | 5 项 | M-1（校验规则 5/36）/ M-2（streams 4 字段）/ M-3（Excel 模板 API）/ M-4（spec §5.6 估算）/ M-5（.out 20+ Section） |
| 漏项清单 | 30 项 | 审计 V2.0 §8（编号 1-30） |
| 原 TODO 收口 | 6 项 | TODO-034/035/037/040/041/042/043/044 |
| 任务清单 | **27 task**（SIM-14 ~ SIM-40） | 见 §2 |

### 1.2 不做（YAGNI）

- HYSYS/Aspen/HTRI 解析器（spec §6.5 预留 P4 之后）
- 前端集成（spec §3.8，前端 sprint 单独承接）
- LIMS/PAT 数据接入（不在 P3.2 范围）

---

## 2. 任务清单（27 task, SIM-14 ~ SIM-40）

| ID | 任务 | 估时 | 优先级 | 依赖 |
|---|---|---|---|---|
| **SIM-14** | sim_imports + sim_import_warnings 表 + 归档 API | 1d | P0 | — |
| **SIM-15** | sim_unit_op_results + 6 专用结果表 + 单元 SUMMARY 解析 | 5d | P0 | — |
| **SIM-16** | sim_tower_results 表 + COLUMN SUMMARY 解析 | 1d | P0 | — |
| **SIM-17** | streams 表 4 字段（simulation_status/tear_stream/estimated/stream_properties_json） | 0.5d | P0 | — |
| **SIM-18** | streams 表 4 JSON（user_provided/calculated/effective/conflict_resolutions_json） | 0.5d | P0 | — |
| **SIM-19** | PRO/II composition 提取 + 17 项 LIBID→CAS 别名映射 | 1d | P0 | — |
| **SIM-20** | .out 20+ Section 数值提取 | 3d | P1 | — |
| **SIM-21** | 5 类物性自动补全（Joback/Lee-Kesler/Rackett/CoolProp）+ estimated 标记 | 1d | P1 | SIM-17 |
| **SIM-22** | PropertyConflictResolver 类（10 字段物性冲突引擎） | 1d | P1 | SIM-18 + SIM-19 |
| **SIM-23** | DataLineage 反向查询（reference_count + references 数组 + in_use） | 0.5d | P1 | — |
| **SIM-24** | POST /streams/validate 端点 | 0.25d | P1 | — |
| **SIM-25** | GET /streams/import/excel/template 端点 + 50+ 别名表（合 TODO-034） | 0.5d | P1 | SIM-30 |
| **SIM-26** | GET /streams/{id}/properties + POST /properties/estimate 端点 | 0.5d | P1 | SIM-21 |
| **SIM-27** | 9 类 sim imports 查询端点 | 1d | P1 | SIM-14/15/16 |
| **SIM-28** | SIM-V03~V10 校验规则（8 条） | 0.5d | P1 | — |
| **SIM-29** | PR-V01~V14 + PRX-V01~V08 共 22 条 PRO/II 校验规则 | 1d | P1 | — |
| **SIM-30** | 50+ 组分别名表（spec §8.3 验收，合 SIM-25 别名部分） | 0.25d | P1 | — |
| **SIM-31** | composition_mass 模式 B + std_liq_density/specific_gravity/liquid_fraction 字段 | 0.5d | P1 | SIM-19 |
| **SIM-32** | update endpoint 状态限制（DRAFT/CHECK_REJECTED 可编辑） | 0.25d | P1 | — |
| **SIM-33** | 气相物性 10 字段 + 液相物性命名对齐 | 0.5d | P2 | — |
| **SIM-34** | 炼油专用 5 字段 + 蒸馏曲线 8 种 schema | 1d | P2 | — |
| **SIM-35** | SIM-E04 被引用后不可删除 | 0.25d | P2 | SIM-23 |
| **SIM-36** | PROII reaction kinetics 提取 | 0.5d | P2 | — |
| **SIM-37** | PRO/II 8.x 炼油版增量（ASSAY/D86/TBP/LIGHTEND/REFSTREAM/TRAY SIZING/REFINERY PROCESSOR） | 5d | P2 | SIM-15 |
| **SIM-38** | 塔盘详细数据（TRAY COMPOSITIONS/LOADING/RATING） | 3d | P2 | SIM-16 |
| **SIM-39** | TODO-040 alembic round-trip + TODO-044 状态机审计结构化 + TODO-037 不可靠产品下游拒绝 | 1d | P1 | — |
| **SIM-40** | P3.x 收口报告 V1.0 | 0.5d | — | 全部 above |
| **总计** | | **~30.5d** | | |

---

## 3. 依赖图

```
批 1 基础数据层（必先）
  SIM-17 ─┐
  SIM-18 ─┤
  SIM-19 ─┼─→ 批 2
  SIM-14 ─┤
  SIM-15 ─┤
  SIM-16 ─┘

批 2 功能补全
  SIM-20 ─┐
  SIM-21 ─┤  (SIM-21 依赖 SIM-17)
  SIM-22 ─┤  (SIM-22 依赖 SIM-18 + SIM-19)
  SIM-23 ─┼─→ 批 3
  SIM-27 ─┘  (SIM-27 依赖 SIM-14/15/16)

批 3 API + 校验
  SIM-24 ─┐
  SIM-25 ─┤  (SIM-25 依赖 SIM-30)
  SIM-26 ─┤  (SIM-26 依赖 SIM-21)
  SIM-28 ─┤
  SIM-29 ─┤
  SIM-30 ─┤
  SIM-31 ─┤  (SIM-31 依赖 SIM-19)
  SIM-32 ─┤
  SIM-35 ─┘  (SIM-35 依赖 SIM-23)

批 4 增补 + 收口
  SIM-33 ─┐
  SIM-34 ─┤
  SIM-36 ─┤
  SIM-37 ─┤  (SIM-37 依赖 SIM-15)
  SIM-38 ─┤  (SIM-38 依赖 SIM-16)
  SIM-39 ─┤
  SIM-40 ─┘  (SIM-40 依赖全部 above)
```

---

## 4. 执行批次（4 批串行，批内可并行）

| 批 | 内容 | task 数 | 估时 | 关键产出 |
|---|---|---|---|---|
| **批 1 基础数据层** | SIM-14/15/16/17/18/19 | 6 | 9.5d | sim_imports/sim_unit_op_results/sim_tower_results/sim_import_warnings 4 表 + streams 8 字段 + composition |
| **批 2 功能补全** | SIM-20/21/22/23/27 | 5 | 7d | .out 20+ 解析 + 5 类物性估算 + PropertyConflictResolver + DataLineage 反查 + 9 类查询 API |
| **批 3 API + 校验** | SIM-24/25/26/28/29/30/31/32/35 | 9 | 4.5d | 3 API 端点 + 30 校验规则（SIM-V8 + PR22）+ 50 别名 + composition_mass + update 状态 + SIM-E04 |
| **批 4 增补 + 收口** | SIM-33/34/36/37/38/39/40 | 7 | 11.5d | ADD-001 字段补全 + 蒸馏曲线 8 种 + reaction kinetics + PRO/II 8.x 炼油 + 塔盘数据 + TODO 收口 + 收口报告 |
| **总计** | | **27** | **~32.5d 串行** | / |

**并行优化**：
- 批 1 内部 6 task 全并行（人手够 → ~5d）
- 批 2 内部 SIM-20/21/23/27 可并行（~4d）
- 批 3 全 task 可并行（~1.5d）
- 批 4 内部 SIM-33/34/36/39 可并行（~3.5d）；SIM-37/38 串行（5d + 3d）
- **4 批串行 + 批内并行 → ~15-20d 实际工期**

---

## 5. 每个 task 实施流程

```
1. 读 spec 对应章节 + audit V2.0 对应编号
2. 写测试（RED）— pytest 失败
3. 实施（GREEN）— pytest 通过
4. 重构（IMPROVE）— ruff 0 错 + 88% 覆盖
5. 独立 commit（<type>(p3.2-sim-p3x): <desc>）
6. 累计回归 702+ 新增全绿
7. 闭环审计（buglog 记录新坑）
```

每个 task 验收：
- [ ] 测试覆盖率 ≥ 88%
- [ ] Ruff lint 0 errors
- [ ] 全量回归绿（无 SIM 模块退化）
- [ ] spec 对应章节引用 + audit V2.0 编号引用
- [ ] 独立 commit 落地
- [ ] buglog 记录（如有新发现）

---

## 6. 验收标准（P3.x sprint closure）

- [ ] 27 task 全部 completed
- [ ] 全量回归 702 + 新增全绿（目标 900+ 测试）
- [ ] 覆盖率 ≥ 88%（与 P3.2 SIM 持平或更高）
- [ ] Ruff lint 0 errors
- [ ] spec §4 36 条规则覆盖 36/36
- [ ] spec §5.5 7 张表全部建表
- [ ] spec §6 全部端点落地（4 缺失端点：validate/template/properties/9 类查询）
- [ ] spec §5.6 6 类物性自动补全全部落地
- [ ] spec §3.6 五 JSON 字段全部落地
- [ ] spec §5.1 streams 4 字段全部落地
- [ ] PRO/II composition + 50+ 别名映射落地
- [ ] P3.x 收口报告 V1.0 落地
- [ ] P5 后置项（SIM-37/38）已闭环
- [ ] 原 TODO 全部收口（034/035/037/040/041/042/043/044）

---

## 7. 风险

| 风险 | 等级 | 缓解 |
|---|---|---|
| PRO/II 8.x 炼油版解析涉及未知格式 | 高 | 估时 5d 包含 PoC + 5 fixture 验证 |
| .out 20+ Section 大文件解析性能 | 中 | SIM-20 估时 3d 含性能基准测试（≤5s/100 条） |
| CoolProp 5 类物性估算精度 | 中 | 与实验值对比测试（spec §5.6 误差阈值待确认） |
| SIM-22 PropertyConflictResolver 算法复杂度 | 中 | 与 spec §3.4 用户值 vs 计算值 5 优先级规则对齐 |
| 27 task 跨 4 批执行时间风险 | 中 | 批内并行 + 用户裁决优先级 |
| Schema 迁移 6→10 表可能影响 pcs_test | 低 | pcs_test 库已对齐先例，6 migration chain 已闭环 |

---

## 8. 尚未解决的问题（待用户裁决）

| # | 议题 | 选项 | 推荐 |
|---|---|---|---|
| 1 | **起点**：批 1 是否立即启动？ | (a) 立即启动批 1 (b) 等 P3.3 COMMON 衔接后再启 | (a) 立即 |
| 2 | **并行度**：批 1 6 task 全并行？ | (a) 全并行 (~5d) (b) 顺序 (~9.5d) | (a) 全并行 |
| 3 | **PR/commit 粒度** | (a) 每 task 一 commit (b) 每批一 commit | (a) 每 task（CLAUDE.md 默认）|
| 4 | **SIM-37/38（P5 范畴）** | (a) 真 P4 前闭环（5d + 3d）(b) 延后 P4.x | (a) 用户裁决已定 P4 前闭环 |
| 5 | **SIM-22 PropertyConflictResolver 估时** | 1d 是否够？ | PoC 后回调 |
| 6 | **.out 20+ Section 解析估时** | 3d 是否准确？ | PoC 后回调 |
| 7 | **CoolProp 5 类物性精度阈值** | spec 未明 | 与 P3.3 COMMON 衔接时定 |
| 8 | **pcs_test 库对齐策略** | 沿用 P3.2 SIM 手动 alembic upgrade head | 沿用先例 |
| 9 | **是否需要新分支 `p3.2-sim-p3x`** | (a) main 直接续推 (b) 新分支 | (a) 沿用 main（个人项目）|
| 10 | **每批完成后是否需要 batch checkpoint commit** | (a) 收口报告 (b) 累计 commit | (a) SIM-40 收口报告含全部 |

---

## 9. 与原 TODO 的关系

| 原 TODO | 落地 task |
|---|---|
| TODO-034（Excel 模板版本管理）| SIM-25（合入）|
| TODO-035（22 条校验规则 19 条未做）| SIM-28 + SIM-29（共 30 条，超 spec 36 总数中 22 条）|
| TODO-037（不可靠单元产品下游拒绝）| SIM-39（合入）|
| TODO-039（PRO/II composition）| SIM-19 |
| TODO-040（alembic round-trip）| SIM-39（合入）|
| TODO-041（export_service 性能）| SIM-39（合入）|
| TODO-042（commit 事务回滚）| SIM-39（合入）|
| TODO-043（stateful preview 落表）| SIM-14（合入 sim_imports）|
| TODO-044（状态机审计结构化）| SIM-39（合入）|

**原 9 项 TODO 全部纳入 P3.x sprint，零散落**。

---

## 10. 下一步

**待用户裁决** §8 议题 1-10 → 启动批 1 → 6 task 并行 → 累计 ~5d → 批 1 收口 → 启动批 2...

---

_V1.0 计划 · 2026-09-09 · main_