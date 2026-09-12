# PCS P3.x SIM 收口报告 V1.0

> 日期：2026-09-13 ｜ 基线：`docs/PCS-P3.2-SIM-P3X.md`（V1.1，ed9a3fc）
> 范围：P3.x sprint 全部任务（批 1 基础数据层 → 批 4 增补收口）+ V1.0 漏项变更管理 4 task
> 结论：**27 task 全部 completed；P4 前无阻断漏项**

---

## 1. 验收对照（plan §6）

| 验收项 | 目标 | 实际 | 判定 |
|---|---|---|---|
| 27 task 完成 | 27/27 | 27/27（见 §2 映射） | ✅ |
| 全量回归 | 900+ 测试 | **1219 passed** + 1 flake（TODO-041 偶发）+ 1 skip（pcs_test 守卫） | ✅ |
| 覆盖率 | ≥ 88% | **88%**（--cov=app TOTAL） | ✅ |
| Ruff lint | 0 errors | **445 基线持平**（每 commit 不净增，用户裁决基线制） | ⚠️ 偏离见 §5.1 |
| spec §4 36 条规则 | 36/36 | SIM-28（SIM-V03~V10）+ SIM-29（PR-V01~V14 + PRX-V01~V08）落地 | ✅ |
| spec §5.5 7 张表 | 全部建表 | SIM-14/15/16 落地（sim_imports/6 专用结果表/sim_tower_results） | ✅ |
| spec §6 端点 | 4 缺失补齐 | SIM-24 validate / SIM-25 template / SIM-26 properties+estimate / SIM-27 9 类查询 | ✅ |
| spec §5.6 物性补全 | 6 类 | SIM-21（chemicals HEOS/Lee-Kesler/Rackett/Gharagheizi…） | ✅ |
| spec §3.6 五 JSON | 全部 | SIM-18 四 JSON + SIM-17 stream_properties_json | ✅ |
| spec §5.1 streams 4 字段 | 全部 | SIM-17（1228027） | ✅ |
| composition + 50+ 别名 | ≥50 ALIAS | SIM-19（17 LIBID→CAS）+ SIM-30（4 组 70 条，55 ALIAS ≥50） | ✅ |
| P5 后置项 SIM-37/38 | P4 前闭环 | SIM-37a/37b + SIM-38a/38b 全闭环（§2.3） | ✅ |
| TODO 收口 | 034/035/037/040/041/042/043/044 | 5 闭环 + 3 P4 裁决（§4） | ✅ |
| 收口报告 V1.0 | 落地 | 本文档 | ✅ |

## 2. 任务全景（task → commit 映射）

### 2.1 批 1 基础数据层（2026-09-09 闭环）

| Task | Commit | 交付 |
|---|---|---|
| SIM-14 (a/b/c) | 37eebd4 + b33928c + 11ad71e | sim_imports + warnings 表 + stateful preview（PREVIEW 状态 + import_id；闭环 D-4/TODO-043） |
| SIM-15 | 9aee70d | sim_unit_op_results + 6 专用结果表 + SUMMARY 解析 |
| SIM-16 | b5043e1 | sim_tower_results + COLUMN SUMMARY |
| SIM-17/18 | 1228027 | streams 8 字段（4 状态 + 4 JSON） |
| SIM-19 | 904dc35 | composition 提取 + 17 LIBID→CAS |
| SIM-20 (a/b/c/d) | e379579 + 581745c + 0086fc6 + ee43590 | .out 20+ Section + REFINERY PROCESSOR/TBP-ASTM（FCC） |

### 2.2 批 2 功能补全（2026-09-10 闭环）

| Task | Commit | 交付 |
|---|---|---|
| SIM-21 | bc5a8fa | 5 类物性自动补全 + estimated 标记 |
| SIM-22 | 4334168 | PropertyConflictResolver（10 字段三级冲突） |
| SIM-23 | 6303d11 | DataLineage 反向查询 |
| SIM-27 | f01267f | 9 类 sim imports 查询端点 |

### 2.3 批 3 API + 校验（2026-09-11 闭环）

| Task | Commit | 交付 |
|---|---|---|
| SIM-24 | 43f7aa8 | POST /streams/validate（离线不入库） |
| SIM-25 | 9ba4d10 | GET /imports/excel/template + 别名表 |
| SIM-26 | 8bc7e40 | GET /streams/{id}/properties + POST /properties/estimate |
| SIM-28 | 8ba602e | SIM-V03~V10 8 条 |
| SIM-29 | be46f4d | PR/PRX 22 条交叉校验（闭环 TODO-035） |
| SIM-30 | 46bc343 | alias_registry 单源 4 组 70 条（55 ALIAS ≥ §8.3） |
| SIM-31 | 647cbdd | composition_mass→mole + 2 液相字段 |
| SIM-32 | 9c75b1b | update 端点状态限制（锁定态 409） |
| SIM-35 | fbcc00e | 被引用不可删除（引用计数 409） |

### 2.4 批 4 增补 + 收口（2026-09-11 ~ 09-13 闭环）

| Task | Commit | 交付 |
|---|---|---|
| SIM-33 | 7499224 | 气相 9 字段 + 液相命名对齐 + SIM-31 JSONB→ORM |
| SIM-34 | 357fb76 | 炼油 5 字段 + 蒸馏曲线 8 种 schema 验证器 |
| SIM-36 | a28d40c | PRO/II reaction kinetics（双格式兼容） |
| SIM-37a | 4512944 | 炼油版关键字识别 PoC（8 类枚举 + RefineryReport） |
| SIM-37b (1/2/3) | 092fda6 + 6b04bb8 + 5fcdf6b | ASSAY+D86 / TBP+LIGHTEND / REFSTREAM+TRAY SIZING（6 parser） |
| SIM-38a | 174a82d | 塔盘 COMPOSITIONS 单 Section PoC |
| SIM-38b (1/2/3) | 0723577 + e8b8e43 + a533765 | LOADING（双子表）/ RATING（9/10 列双版本）/ COMPOSITIONS 全量集成 |
| SIM-39 | 6a7b075 | TODO-037 守卫 + TODO-044 审计结构化 + TODO-040 round-trip |
| SIM-40 | 本 commit | 收口报告 V1.0 |

### 2.5 V1.0 漏项·变更管理闭环（编号为 V1.0 系列，与 §2.4 V1.1 编号无冲突）

| V1.0 Task | Commit | 交付 |
|---|---|---|
| SIM-37 | 72feed8 | 项目级符号/格式模板审批收口（三域 5 态机） |
| SIM-38 | df68d7e | 一键变更单 RECORD_CHANGE（ChangeNoticeService，7 值 change_type） |
| SIM-39 | aaf8bd5 | 记录弃用 RECORD_CANCELLATION（BoundObsoleteError 双路径） |
| SIM-40 | 1b912e2 | 反向签署 REVERSAL_APPROVAL（三事件 + 快照恢复） |

> **编号说明**：commit 前缀 `p3x-38/39/40` 为 V1.0 漏项系列（变更管理）；
> V1.1 起 SIM-38a/38b/39/40 为炼油塔盘/TODO/报告系列。两系列全部闭环。

## 3. 数值指标

| 指标 | 值 |
|---|---|
| 测试总数 | 1221（1219 passed + 1 flake + 1 skip） |
| 覆盖率（--cov=app） | 88% |
| ruff 基线 | 445（持平不净增；起点 437 → SIM-36 后 445 漂移 +8，之后持平） |
| P3.x 期间 commit | 55（2026-09-09 起） |
| 估时 vs 实际 | 32.5d 估时；批 3+4 实际 3 天（含并行） |

## 4. TODO 收口终态

| TODO | 内容 | 终态 |
|---|---|---|
| TODO-034 | Excel 模板版本管理 | **P4 裁决保留**（SIM-25 已交模板端点；版本管理后置） |
| TODO-035 | 物流校验 22 条 | ✅ SIM-29 闭环（be46f4d） |
| TODO-037 | 不可靠流下游拒绝 | ✅ SIM-39 提前闭环（UnreliableStreamGuard，422 STREAM_UNRELIABLE_BLOCKED） |
| TODO-040 | alembic round-trip | ✅ SIM-39（可逆段 + pcs_test 守卫 + 锚点契约） |
| TODO-041 | export perf 偶发超时 | **P4 裁决保留**（低优 flake，本报告 §3 实测复现 1 次） |
| TODO-042 | commit BLOCK 事务回滚优化 | **P4 裁决保留**（优化项，非缺陷） |
| TODO-043 | stateful preview 落表 | ✅ SIM-14 闭环（37eebd4~11ad71e） |
| TODO-044 | 审计结构化 | ✅ SIM-39（snapshot_id/snapshot_action 两键 additive） |

## 5. 已知偏离与漏项

### 5.1 ruff 基线 445 ≠ 0 errors（plan §6 偏离）

用户裁决基线制（每 commit 不净增）：批 3 起点 437，SIM-34/36 期间漂移至 445，
此后 8 个 commit 全部持平。0 errors 需专项清理（约 31 fixable + 手工），建议 P4 初
一次性 `ruff --fix` + 人工复核后归零并锁 CI。

### 5.2 export_service perf flake（TODO-041）

`test_export_perf_budget` 偶发超时（本报告覆盖率运行中复现 1 次）。与 SIM 数据
无关；P4 修（阈值放宽或隔离冷启动）。

### 5.3 proii .out（4.17）fixture 事实

多 problem 拼接 + T1 报告重复 ×2；T2/T3 仅 INDEX 有条目、输出无 section。
后续以输出实测为准（cerebrum 已记），勿按 INDEX 推断测试预期。

### 5.4 不可逆迁移边界

`p3sim_stream_sign_status_extend`（enum ADD VALUE）downgrade 抛
NotImplementedError —— round-trip 测试以它为下界锚点（SIM-39）。生产回退需
手动 ALTER TABLE TYPE varchar 重建（迁移文件头注释有 SOP）。

## 6. P4 衔接建议

1. **ruff 归零专项**（§5.1）：31 fixable + 手工复核，半天。
2. **calculate 入口接 Guard**：P4 工艺计算首个端点直接调用
   `UnreliableStreamGuard.check`（SIM-39 已备，含 422 契约测试）。
3. **9 态 enum 扩展（TODO-036）**：PG `ALTER TYPE ADD VALUE` 不可逆 —— 迁移
   前备份 enum definition（cerebrum 政策）。
4. **塔盘/炼油 parser 入库链路**：SIM-37b/38b 产出为 dataclass 层，P4 需
   import_service 集成（写 sim_tower_results / stream_properties_json）。
5. **覆盖率抬升**：88% → 90%（app/ 中 1109 未覆盖行集中在 api 层 error 分支）。

## 7. 决议与文档引用

- 执行契约：用户 2026-09-08（30 漏项 P4 前闭环）+ 2026-09-09（27 task 不分级）
- plan V1.1 D-* 闭环对照：ed9a3fc
- 变更管理 spec：ADR-0002/0009/0010/0024
- 本报告不改基线文档；P3.x 状态以本文 + git log 为准。
