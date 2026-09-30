# PCS Project Changelog

记录每个发布批次的工艺覆盖、架构裁决、follow-up 跟踪号。本文件是项目级变更账本，git-ignored 的 SDD ledger（`.superpowers/sdd/...`）记录实施细节。

---

## [P6-5+] — 13 项工艺计算三批并行实施（2026-09-26）

### 范围

13 项 SPEC 覆盖项 + 4 张 CONFIG 表，跨 3 批 + 1 收口：
- **Batch A** PIPE / PIPE_NET：C-03 冲蚀 / C-05 尺寸 / C-13 浪涌 / C-15 持液率+流型
- **Batch B** VESSEL / CV / PSV / RESTRICTION：C-10 三相分离器 / C-09 AS 2360 / C-20 API 2000 / C-21 AS 1210 / C-19 排污孔板
- **Batch C** FLARE / PSYCHRO：C-22 Pasquill-Gifford / C-23 API 521 噪声 / C-16 TEG/DEG 脱水 / C-18 Hammerschmidt 水合物抑制
- **C5 收口**：4 张 CONFIG 表（`compound_pasquill_sigma` / `compound_api521_thresholds` / `compound_iso9613_atmospheric_absorption` / `compound_hammerschmidt_K`）+ 4 alembic 迁移 + 4 seed 脚本 + 5-min TTL 缓存层

### 覆盖

| 维度 | 数量 |
|---|---|
| Service 模块 | 13 个新文件 |
| 测试 | 185（13 service × 平均 14；baseline 47 + 增量 138 全部覆盖 Review Focus 5 类输入） |
| Frozen dataclass | 13 × 2（Input + Result） |
| PcsError 子类 | 13（每 service 一个，code/status 标准化） |
| CONFIG 表 | 4 张（带 alembic 迁移 + seed 脚本） |
| 黄金 fixture | 13 个 JSON |
| Commits | 20 个 `p6-5` 相关 commit |

### 架构组裁决（2026-09-26）

#### Q1：187 vs 47 测试数差异 4 倍

**裁决**：基本清完

- ✅ 185 测试明细（per-service 分布表 + Review Focus 5 类映射）已通过
- ✅ Scope check：0 frontend / 0 API 集成 / 0 alembic / 0 CONFIG cache 测试，**无 scope creep**
- ⚠️ 187 vs 185 数据矛盾：原始报告 "187" 是初稿错误；pytest `--collect-only` 实测 **185**
- ⚠️ C3/C4 (FLARE) 增量 +3 看似偏少，实际覆盖：F2（invalid_stability_class / invalid_wind_speed / invalid_distance / invalid_flame_power 共 4 个 `_raises` 测试）+ F5（extreme_unstable_dispersion / long_range absorption 2 个极端值测试）+ frozen + golden + PcsError
- ⚠️ C3/C4 F1 (imperial_units) 豁免依据：**Plan Header §Review Focus F1** 明确声明 C-22/C-23 为 SI-only（"FLARE is exempt from imperial_units per design"）；M-1 v2 BLOCKER 是 plan 审查中的优先级标签，非豁免依据

**合并前动作**：澄清 185/187 差异 + C3/C4 F5 覆盖（< 15 min）
**合并后动作**：若需补测，按需追加

#### Q2：3 处工程正确性优先裁决文献状态

**裁决**：部分清完（接受现状 + follow-up 立项）

| 裁决项 | 状态 | 锚定 | follow-up |
|---|---|---|---|
| C1 L/V_ref=242 | 设计工况归一化常数（3 gpm/MMscf × 1440 min/d），非单表数值 | GPSA §20.4 | **SPEC-ADD-001-Q2-1** |
| C2 MEOH=6.63 lb/gal | MeOH 标准密度 ~20°C 教科书值；独立验算 6.63 × 0.1198 ≈ 0.794 g/mL ≈ 792 kg/m³ ✓ | GPSA §20.3 | **SPEC-ADD-001-Q2-2** |
| C4 默认 A=1.5 dB/km | 生产路径保留已验证（`_DEFAULT_ATM_ABS_DB_PER_KM` + cache fallback）；测试 A=0 仅隔离几何衰减 | ISO 9613-2 §5 | 无（已 verified） |

**合并前动作**：无（已澄清现状）
**合并后立即动作**：
1. SPEC-ADD-001-Q2-1：SPEC V1.2 §3.9.4 增补 C1 L/V_ref=242 设计工况推导注释
2. SPEC-ADD-001-Q2-2：SPEC V1.2 §3.9.5 增补 C2 MEOH=6.63 物性表溯源 + 温度敏感性说明

#### Q3：lru_cache 非严格 5-min TTL

**裁决**：清完（fix 已落地）

| 项 | 值 |
|---|---|
| Commit | `e35064b` — `fix(p6-5): real 5-min TTL for compound_config_cache (Q3 architecture fix)` |
| 文件 | `pcs-backend/app/services/_compound_config_cache.py`（145 LOC） |
| 机制 | `time.monotonic()` + `threading.Lock`（DB 加载锁外） |
| TTL | `_CACHE_TTL_SECONDS: Final[int] = 300` |
| 4 个独立 key | `pasquill_sigma` / `api521_thresholds` / `iso9613_abs_default` / `hammerschmidt_K` |
| 热重载 | `clear_all_caches()` 导出在 `__all__` |
| 回归 | 181 passed / 5 skipped（与 C5 基线一致） |
| C-12 frozen | `vessel_service.py` 未触碰 |

**合并前动作**：无
**合并后立即动作**：补 3 个正式 TTL 单元测试：
1. `test_cache_ttl_expiry_triggers_reload`（mock `time.monotonic` 后断言 loader 被再次调用）
2. `test_cache_clear_all_caches_forces_reload`（smoke test 转正式）
3. `test_cache_per_key_isolation`（key A 过期不影响 key B）

### 5 项裁决项确认

| # | 裁决项 | 状态 |
|---|---|---|
| 1 | G-08 baseline drift（pre-existing） | 接受（Task 16/28 收口） |
| 2 | pcs_test DB alembic + 4 seeds | **CI 验证待执行**（migration chain + seed `--dry-run` 已通过；CI runner 有 pcs_test 访问后执行） |
| 3 | lru_cache 不接受 | **Q3 fix 落地**（commit `e35064b`） |
| 4 | openapi-baseline.json | 接受 |
| 5 | 前端 wrapper | 接受 |

### Follow-up 跟踪号

| 跟踪号 | 类别 | 描述 | 状态 |
|---|---|---|---|
| SPEC-ADD-001-Q2-1 | SPEC 修订 | C1 L/V_ref=242 设计工况推导 | 已并入主 SPEC **V1.10** §3.9.1.1（`d3e9e60`） |
| SPEC-ADD-001-Q2-2 | SPEC 修订 | C2 MEOH=6.63 物性表溯源 + 温度敏感性 | 已并入主 SPEC **V1.10** §3.9.3.1（`d3e9e60`） |
| TTL-TEST-001~003 | 后合并测试 | 3 个正式 TTL 单元测试（Q3 fix 配套） | **已落地**（merge `63d8e1a`） |
| CI-P6-5-SEED | CI 任务 | alembic upgrade head + 4 seed 脚本在 pcs_test 库执行 | **已执行**（本批；本地 pcs_test，无 CI 环境 per 单人开发裁决） |

### 分支状态

- HEAD: `e35064b`
- Commits since plan anchor: 20
- ruff: 0 errors
- pytest flare+psychro: 181 passed / 5 skipped
- C-12 frozen contract: 未触碰
- SDD ledger: `.superpowers/sdd/2026-09-26-p6-5-batch/progress.md`

---

## [P6-5+] — follow-up: 3 TTL 正式单元测试（2026-09-26）

### 范围

架构组 Q3 裁决"合并后立即补测"——为 commit `e35064b` 的真实 5-min TTL 机制补 3 个正式单元测试，固化不变量回归。

| 跟踪号 | 测试 | 验证不变量 |
|---|---|---|
| TTL-TEST-001 | `test_cache_ttl_expiry_triggers_reload` | TTL=300s：t=0 首次加载命中 loader；TTL 内命中 cache；t=301 触发重载 |
| TTL-TEST-002 | `test_cache_clear_all_caches_forces_reload` | TTL 内连续命中 cache；`clear_all_caches()` 后下次调用强制重载 |
| TTL-TEST-003 | `test_cache_per_key_isolation` | key A TTL 过期触发重载，key B 在 TTL 内继续命中 cache（per-key 隔离） |

### 测试设计

- **隔离 DB 依赖**：`patch.object(_compound_config_cache, "_load_with_fallback", ...)` 把 SQLAlchemy engine 装载短路为受控返回值；不依赖真库 / alembic / seed 数据
- **可控时钟**：`patch.object(_compound_config_cache.time, "monotonic")` 模拟时间快进，避免 sleep 300s
- **走公开入口**：用 `get_pasquill_sigma_table()` / `get_api521_thresholds_table()`，覆盖生产代码的真实 TTL 路径（含锁 + 缓存状态字典）

### 验证

| 项 | 命令 | 结果 |
|---|---|---|
| 新测试 | `uv run pytest tests/services/test_compound_config_cache.py -v` | 3 passed, 0 skipped, 0.51s |
| 回归（cache consumers） | `uv run pytest tests/services/flare/ tests/services/psychro/ -q` | 181 passed, 5 skipped（与 C5 baseline 一致） |
| ruff | `uv run ruff check tests/services/test_compound_config_cache.py app/services/_compound_config_cache.py` | All checks passed |

### 文件

- 新建：`pcs-backend/tests/services/test_compound_config_cache.py`（101 LOC）
- 改动：0（仅新增测试文件，未触碰 `_compound_config_cache.py` 145 LOC 实现）

---

## 模板（后续批次使用）

```markdown
## [P6-X+] — <标题>（YYYY-MM-DD）

### 范围
- ...

### 覆盖
| 维度 | 数量 |
|---|---|
| ... | ... |

### 架构组裁决
#### Q1：<问题>
**裁决**：<状态>
- ...

#### Q2：<问题>
**裁决**：<状态>
- ...

### Follow-up 跟踪号
| 跟踪号 | 类别 | 描述 | 状态 |
|---|---|---|---|
| ... | ... | ... | ... |
```

---

## [P6-5+] — follow-up: CI-P6-5-SEED 落地 + 全量回归暴露的 6 项修复（2026-09-26）

### CI-P6-5-SEED 执行（pcs_test 对齐）

| 步骤 | 结果 |
|---|---|
| `alembic upgrade head`（p6_4_004 → p6_5_004） | 4 迁移全过 |
| 4 seed 脚本 | pasquill_sigma 6 行 / api521_thresholds 2 行 / iso9613 4 行 / hammerschmidt_K 5 行（合计 17 行，`SYNTHETIC_TEST_DATA` 标记） |
| 表名核对 | `compound_hammerschmidt_K`（大写 K，与 ORM `config.py` 一致） |
| flare+psychro 回归 | 186 passed / 0 skipped —— 原 5 个 DB 依赖 skip 全部解除并通过（seed 生效直接证据） |

### 全量回归暴露的 6 项缺陷与修复

首次对齐 pcs_test 后跑全量（3178 用例）暴露 24 failed；逐一定性后 6 项修复：

| # | 缺陷 | 根因 | 严重度 | 修复 |
|---|---|---|---|---|
| 1 | 19 个 validator/meta 测试失败（`Severity` 无 `ERROR`、`StreamDataMode` 空） | commit `a5f9360`（P5c-low docstring 补全）误把 3 个枚举的成员行替换成 docstring | HIGH（SYM/FMT 验证器 + meta enums API 全挂） | 恢复成员：`Severity.ERROR/WARN` ×2 + `StreamDataMode.CHEMICAL/PETROLEUM/SOLID` |
| 2 | `heat_results`/`vessel_results`/`cv_results`/`restriction_results`/`equipment_list` 真库 INSERT 必炸 | ORM `RecordMixin` 在 20 表映射审计三件套，历史迁移只落了 15 表（`p4_calc_audit_fields` 仅 5 表 + P6-2+ 新建表自带） | **HIGH（生产缺陷）** | 新迁移 `p6_5_005_audit_trio_drift_fix`：5 表 × 3 列 nullable（沿 P6-OPEN-009 psv 先例） |
| 3 | `test_reversible_segment_roundtrip` 降级链炸（`psychro_results` RENAME 时表不存在） | `p6_2_001` downgrade 只 drop 不还原 v3_1 stub，下层 `p5_0_4a` downgrade 引用缺失表 | MEDIUM | `p6_2_001` downgrade 还原 cooling_tower/psychro 两张 stub（p5_0_4a 改名后 PK 形态；flare 在链上无创建者不还原） |
| 4 | `test_table_count` 期望 84 实际 88 | P6-5 批次加 4 张 CONFIG 表未更新断言（实施时 pcs_test 未对齐故未暴露） | LOW | 断言 84 → 88 |
| 5 | `test_p4_flash_full_path` NOT NULL 炸 | `FlareSystemResult.calc_type` NOT NULL（P6-2 加），测试 fixture 漏传 | LOW | fixture 补 `calc_type="RELIEF_SUMMARY"` |
| 6 | `test_heat_aggregator_g07_real_pcs_test` 两连炸 | ①缺陷 2 的三件套缺失；②fixture 漏 `workspace_id`（RecordMixin NOT NULL，真库用例从未绿过） | MEDIUM | ①迁移矫正；②3 个 HeatResult 补 `workspace_id` |

### 验证

| 项 | 结果 |
|---|---|
| 24 个原失败用例重跑 | **24/24 通过** |
| 全量回归（对齐 pcs_test） | **3173 passed / 5 skipped / 0 failed**（修复前 24 failed / 3149 passed） |
| ruff（全部改动文件） | All checks passed |
| roundtrip（head → p3sim 锚点 → head） | 通过（首次全链可逆） |

### 已知残留

- **pcs 开发库**（`DATABASE_URL` 默认指向）停在 `p6_3_002`，落后 10 个迁移（P6-4 ×4 + P6-5 ×4 + 矫正 ×1 + gate_03）。应用层连开发库时 CONFIG 服务走内联 fallback 常量（设计如此）；P6-4 起的 `*_results` 新列在开发库缺失会影响落库。是否推进开发库迁移待用户裁决。

---

## [P6-5+] — follow-up: pcs 开发库对齐 + ORM↔DB drift 终扫清零（2026-09-26）

### pcs 开发库对齐（用户裁决"执行"）

- `alembic upgrade head`：p6_3_002 → p6_5_006（12+1 迁移，含 P6-3 尾段 / P6-4 全部 / P6-5 全部）
- 4 seed 脚本：compound_* 17 行入库（CONFIG 服务 DB 优先生效）
- 开发库此前停在 p6_3_002，P6-4+ 新列全缺（bug-101 同模式的落库炸点）

### p6_5_006 终扫迁移（3 表 6 列）

p6_5_005 后用 ORM metadata 全库程序化对比（不再手写表名清单），暴露并修复：

| 表 | 缺列 |
|---|---|
| `sep_equip_results` | 审计三件套 ×3（bug-101 清单遗漏，同为 P4 前旧表） |
| `pipe_class_import_previews` | `created_by` / `updated_at`（TimestampMixin 未落迁移） |
| `project_template_pipe_classes` | `created_by` |

幂等 `ADD COLUMN IF NOT EXISTS` 写法，两库通用。

### 验证

| 项 | 结果 |
|---|---|
| ORM↔pcs drift 扫描 | **清零 ✓**（87 ORM 表全列一致） |
| ORM↔pcs_test drift 扫描 | **清零 ✓** |
| 全量回归（pcs_test） | 3173 passed / 5 skipped / 0 failed（保持） |

---

## [P6-5+] — SPEC V1.10 冻结（2026-09-26，commit d3e9e60）

主 SPEC `PCS-SPEC-ADD-001` V1.9 → **V1.10（已冻结 — P6-4/P6-5+ 实施基线）**：

- §3.9.1.1 并入 C1 L/V_ref=242 双层口径推导（Q2-1 v2）
- §3.9.3.1 并入 C2 MEOH=6.63 lb/gal 物性溯源（Q2-2）
- §0.1 V1.10 实施终态注记：24 项计算全部落地（P6-4 `849a1bb` + P6-5+ `f530daa`）
- Q2 增补文档转编号 `PCS-SPEC-ADD-001-ATT-02`（Q2 工艺推导附件，git rename 保留历史）

**P6-5+ 全部跟踪项闭环。** 剩余开口：SYNTHETIC_TEST_DATA → 真实厂商/GPSA 数据（P6-6+ 工艺工程师接管）。

---

## [P6-5+] — follow-up: B 批 4 项（drift 守卫 / G-08 / STATUS / 前端 3 页）（2026-09-27）

| # | 项 | commit | 结果 |
|---|---|---|---|
| 1 | ORM↔DB drift 守卫测试（bug-101/102 防回归，pcs_test-only） | `bba7625` | pcs_test PASS / 默认 skip |
| 2 | G-08 openapi-baseline 滚动（Task 16/28 收口） | `384d8c7` | +37 端点 / +82 schema（P6-2~5 纯增量）；四阶段全过（161 paths / 203 schemas） |
| 3 | `.wolf/STATUS.md` 重生成（/handoff，1749 行 → 紧凑版） | —（.wolf hooks 维护） | Next quest 更新为 P6-6+ |
| 4 | 前端补课 3 计算页（P6-4 DECISION 推迟项） | `67633a9` | heating-value / saturation-water-content / cv；tsc 0 / eslint 0 / vitest 548 passed（基线 525） |

---

## [P6-9-PICKUP-4] — ce-code-review P5+P6 残留 debt 闭环（2026-09-30）

### 范围

`docs/ce-code-review-p5-p6-summary.md`（5 batch × 47 commits）登记的 50 findings 中，P6-9-PICKUP-2/3 已收口 4 CRITICAL + 9 HIGH + 7 MEDIUM；本批清剩余 21 LOW/INFO + 9 pre-existing pytest failures + 5 ruff errors + 工艺室 2026-11-15 交付对账预留位。

### 覆盖

| 维度 | 数量 |
|---|---|
| Pre-existing pytest failures（pcs_test schema drift） | 9 个测试，4 文件（psychro / cv / schema_drift / fixtures） |
| Pre-existing ruff errors（calibrate_behr_coefficients.py） | 5 errors → 0 |
| LOW/INFO 项 detail 分类（docs/tasks.md 21 项 4 维） | 5 PROCo + 8 HYG + 6 DOC + 2 REF |
| 工艺室 2026-11-15 交付对账预留位 | OPEN-P6-6A-10 / OPEN-P6-9-PICKUP-2-1/2 / OPEN-P6-6A-9.5 / OPEN-P6-6A-11 共 5 项 |
| Commits | 4（`f9f1360` / `15b6edd` / `6271db7` / `b15512a`） |

### 实施拆解

| Task | commit | 内容 |
|---|---|---|
| T1 | `f9f1360` | 9 pre-existing pytest failures 修复（psychro schema drift + 4 类 DB drift） |
| T2 | `0cec39a`（沿用 PICKUP-3） | `calibrate_behr_coefficients.py` ruff 5 errors 收口（PICKUP-3 T3-batch-5 已分批修，本批 rebase） |
| T3 | `15b6edd` / `6271db7` | 21 LOW/INFO 项 4 维分类 + 数学一致性修正（26 → 21 IDs 对齐上游计数） |
| T4 | `b15512a` | 工艺室 2026-11-15 交付跟踪位预留（OPEN 5 项状态字段 + 前置条件） |

### 验证

| 项 | 结果 |
|---|---|
| pytest 全量 | **3515 passed / 0 failed**（9 pre-existing 修复后无 regression） |
| ruff check（全局） | **0 errors**（`scripts/dev/calibrate_behr_coefficients.py` 5 项清零） |
| docs/tasks.md 总计 | 21 项 = 5 PROCo + 8 HYG + 6 DOC + 2 REF ✓ |
| vitest 全量 | 548 passed（基线持平） |
| G-08 phase 1-4 | 全过 drift=0 |

### 下游 batch 推荐（docs/tasks.md §推荐下游 batch）

- **P6-9-PICKUP-5**（建议）：工艺计算正确性 + 重构（7 项，~2.0 天），依赖工艺室 2026-11-15 / 2026-11-30 交付
- **P6-9-PICKUP-6**（建议）：代码卫生 + documentation（14 项，~1.0 天），无外部依赖可并行启动

### OPEN 状态变化

| OPEN | 变化 |
|---|---|
| OPEN-P6-6A-10 | partial closure（待 AS 1210 PDF 升级 confidence B → A） |
| OPEN-P6-9-PICKUP-2-1 | partial closure（xfail 工艺室 k_strip 校准） |
| OPEN-P6-9-PICKUP-2-2 | 闭环（`258d857` t_wall_mm → t_wall_m 修复） |
| OPEN-P6-6A-9.5 | 关联（PROCo-P6-7-2 high_acid 重发） |
| OPEN-P6-6A-11 | 关联（PROCo-P6-7-{1,3} Nielsen 精确常数） |
| OPEN-P6-9-PICKUP-4 | 新增（T4 跟踪位） |
