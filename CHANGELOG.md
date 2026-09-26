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
| SPEC-ADD-001-Q2-1 | SPEC 修订 | V1.2 §3.9.4 增补 C1 L/V_ref=242 设计工况推导 | 已 commit (`b70fb55`) |
| SPEC-ADD-001-Q2-2 | SPEC 修订 | V1.2 §3.9.5 增补 C2 MEOH=6.63 物性表溯源 + 温度敏感性 | 已 commit (`b70fb55`) |
| TTL-TEST-001~003 | 后合并测试 | 3 个正式 TTL 单元测试（Q3 fix 配套） | **已落地**（本批） |
| CI-P6-5-SEED | CI 任务 | alembic upgrade head + 4 seed 脚本在 CI pcs_test 库执行 | 待 CI 环境就绪 |

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
