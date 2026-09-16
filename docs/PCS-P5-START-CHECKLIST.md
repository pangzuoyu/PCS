# PCS P5 启动前检查清单（12 项）

**生成日期**：2026-09-16
**关联计划**：`docs/PCS-PLAN-P5-DEVICE-EQUIPMENT.md` V1.0
**启动策略**：A 冻结串行（P5-0 → P5-1 → P5-2 → P5-3 → P5-4，每批 ratify 后开下一批）
**当前 commit baseline**：`e37c2e8fbb017f3dd2be9e8ff062c25277600028`（main 分支）

---

## 12 项检查结果总览

| # | 检查项 | 结果 | 阻塞 Task | 备注 |
|---|---|---|---|---|
| 1 | pcs_test alembic upgrade head | ✅ pass | — | 两库 head = `p4_task0_lineage_extension` 一致；CLAUDE.md 「测试前检查」所述矫正迁移风险**已被现状消除** |
| 2 | ruff 归零 445→0 | ✅ pass | — | ruff = 0 errors（P4 末尾已归零；与 V1.8 计划 §"P4 首批建议 #1"叙述不同，实际 P4 末尾已完成） |
| 3 | StreamSignStatus 9 态 enum | ✅ pass | Task 3（P5-0-3）ratify | 两库均已 9 态（DRAFT/IN_APPROVAL/CHECKED/OBSOLETE/CHECK_REJECTED/STALE/CHANGE_PENDING/CHANGED/REVERSAL_PENDING）；plan §94 P5-1 ratify 标注生效，Task 3 不重复 ALTER |
| 4 | 测试基线 1662 | ✅ pass | — | `uv run pytest --collect-only -q` 收集 1662 tests；与 plan §753 一致 |
| 5 | ChEDL vendoring 残留 | ❌ FAIL | Task 25 + 26 | `pcs-backend/vendor/` 下 `fluids`/`chemicals`/`thermo` 三个本地副本仍在；`pyproject.toml:70-72` 三处 `[tool.uv.sources]` 仍指向 vendor 路径；直接 import 无业务模块违规（grep 全空，预期） |
| 6 | PG 版本一致性 + DDL 权限 | ⚠️ 部分 FAIL | Task 24 | PG 版本两库一致（PG 16.15）；`btree_gist` 扩展两库**未安装**；`pcs` 用户 `is_super=off`，无 superuser 权限，**CREATE EXTENSION 必然失败**；Task 3 已 ratify（9 态已扩），无 ALTER TYPE 需求；Task 18 复合索引需要验证 |
| 7 | uv 工具链版本锁定 | ⚠️ 文档未固化 | Task 25 | 当前 `uv 0.11.2`；ADR-0030 §160 提"评审通过后 ADR 更新"未明记 uv 版本；Dockerfile / CI 未检查 uv 版本固定 |
| 8 | DataLineage D4/D5 已备 | ✅ pass | — | `app/services/calc_lineage.py:104` 已含 `formula_version` 参数；`app/models/system.py:56` 已含 `formula_version_at_track` Mapped 列；`data_lineage` 表结构已支持 formula_ref / formula_version 入 lineage |
| 9 | ADR-0028 / ADR-0030 评审状态 | ✅ pass | — | 两份 ADR 真实状态 = `accepted`，accepted_date = 2026-09-15；与 plan §122/§804 一致；V1.8 列项 9 提及"当前 proposed"系计划文本陈旧，**实际已 accepted** |
| 10 | 工艺室 GB 精度阈值 | ❌ 未确认 | Task 13 / Task 14 / Task 16 | 计划多处写"阈值由工艺室确认"；P5-3 启动前必须给出具体数字：GB/T 150.1 附录 B.1.3 火灾工况（建议 ≤5%）/ GB/T 12241 泄放面积（建议 ≤5%）/ GB 两相流（建议 ≤5% 沿用 API） |
| 11 | RECORD_TYPE_REGISTRY 当前基线 | ✅ pass | — | 5 类：`FlashResult` / `PipeNetworkResult` / `PipingResult` / `PumpResult` / `TwoPhaseResult`；与 plan 期望"P4 末态 5 类"一致；P5-0-1 后 = N+7（vessel/sep_equip/psv/relief/heat 各 result 7 类） |
| 12 | 基线快照 + P4 hotfix 状态 | ✅ pass | — | commit hash = `e37c2e8fbb017f3dd2be9e8ff062c25277600028`；测试收集数 = 1662；ruff = 0 errors；`pcs-p5-start-baseline.txt` 三值同本表 #2/#4 |

---

## 阻塞 P5-0 首批的具体障碍

### 障碍 1：btree_gist 扩展 + superuser 权限（阻塞 Task 24）

- **现状**：`pcs` 用户 `is_super=off`；`btree_gist` 两库均未安装
- **影响**：SUP-P5-PSV-001 §3.1 schema 需 `CREATE EXTENSION btree_gist` + EXCLUDE USING gist 约束；alembic 迁移 `p5_standard_profiles` 必失败
- **解决方案（待 DBA 裁决）**：
  - 方案 A：DBA 给 `pcs` 用户临时 superuser（执行 `CREATE EXTENSION btree_gist` 后回收）
  - 方案 B：DBA 提前在两库手动执行 `CREATE EXTENSION btree_gist;`（pcs 用户保持当前权限）
  - 方案 C：alembic 迁移用纯 btree 唯一索引 + 应用层锁替代 EXCLUDE 约束（**不推荐**，破坏 SPEC §3.1 schema 设计意图，且 record_hash 并发安全降级）

### 障碍 1：btree_gist 扩展 + superuser 权限（阻塞 Task 24）

- **现状**：`pcs` 用户 `is_super=off`；`btree_gist` 两库均未安装
- **裁决（用户 2026-09-16）**：**DBA 预装方案** — DBA 在 pcs + pcs_test 两库以 superuser 执行 `CREATE EXTENSION btree_gist;`，业务用户 `pcs` 只需 USAGE 权限即可使用扩展（不需 superuser）
- **DBA 执行清单**（待 DBA 跑完签字）：
  ```sql
  -- DBA 用 postgres 用户在两库分别执行
  psql -U postgres -d pcs        -c "CREATE EXTENSION btree_gist;"
  psql -U postgres -d pcs_test   -c "CREATE EXTENSION btree_gist;"
  -- 验证业务用户可使用
  psql -U pcs -h localhost -d pcs -c "SELECT extname FROM pg_extension WHERE extname='btree_gist';"
  psql -U pcs -h localhost -d pcs_test -c "SELECT extname FROM pg_extension WHERE extname='btree_gist';"
  ```
- **Task 24 alembic 迁移无需 superuser**：业务用户 `pcs` 已有 CREATE 权限（has_database_privilege=CREATE=true），扩展已预装后 alembic 可直接 `CREATE TABLE ... USING gist (...)`

### 障碍 2：ChEDL vendoring 残留（阻塞 Task 25 + Task 26）

**核验结果（用户 2026-09-16 Step 1-2 跑完）**：

vendor 实际包含 **5 个** 包，与 V1.8/ADR-0030 声明的 `{fluids, chemicals, ht}` 不一致：

| 包名 | vendor 中 | pyproject 锁版本 | 业务 import | 处置 |
|---|---|---|---|---|
| `fluids` | ✅ | 1.3.1 | ❌ 无（Task 5+ 才会用） | Task 25 包装层覆盖 |
| `chemicals` | ✅ | 1.5.2 | ✅ **大量**（6 模块：flash/petroleum/property_auto_complete/common_service 等，10+ 子模块） | **包装层范围需扩展，原 7 函数清单不足** |
| `thermo` | ✅ | 0.6.1 | ❌ 无（`thermo_factory.py` 文件名易误判，实际调用的是 `chemicals.*`） | ADR-0030 决策 1 锁定清单应改 `{fluids, chemicals, ht}` → `{fluids, chemicals, thermo}` |
| `ht` | ✅ | ❌ 未锁版本 | ❌ 无业务 import | 评估保留必要性（V1.8 未提及） |
| `CoolProp` | ✅ | ❌ 未锁版本 | ❌ 无业务 import | 同 ht，评估保留必要性 |

**核验命令**（用户提供的 Step 1）：
```bash
ls -la pcs-backend/vendor/                           # 5 个：chemicals, CoolProp, fluids, ht, thermo
grep -rn "import fluids\|import chemicals\|import thermo\|import ht\b\|from fluids\|from chemicals\|from thermo\|from ht\b" \
  pcs-backend/app/ | grep -v chedl_wrapper          # 6 模块 import chemicals 子模块
grep -rn "thermo\|chemicals" pcs-backend/app/services/flash/  # flash_service 通过 thermo_factory 抽象层调 chemicals.*
```

**V1.8 计划 vs 实际不一致清单**：

1. ADR-0030 决策 1 锁定清单 `{fluids, chemicals, ht}` 与 pyproject.toml:23-25 实际 `{fluids, chemicals, thermo}` 不一致
2. ADR-0030 决策 6"7 个包装函数只涉及 fluids"未涵盖 `chemicals.*` 的 10+ 子模块
3. ADR-0030 决策 3"取消 vendoring"清单只覆盖 3 个包，实际有 5 个（多出 `ht` + `CoolProp`）

**ADR-0030 V1.1 修订需求（建议在 P5 启动前完成）**：

- 决策 1 锁定清单：`{fluids, chemicals, ht}` → `{fluids, chemicals, thermo}`
- 决策 6 包装函数清单：原 7 函数 + chemicals 子模块（vapor_pressure / iapws / phase_change / critical / acentric / volume / viscosity / thermal_conductivity / identifiers / flash_basic / search_chemical 等）
- 决策 3 vendor 清理清单：`{fluids, chemicals, thermo}` → `{fluids, chemicals, thermo, ht, CoolProp}`（ht + CoolProp 评估是否清理）
- 附录 A 追加升级历史：`2026-09-16 P5 启动前 V1.1 修订 — 与现状对齐`

**当前状态（用户裁决）**：**暂不动 vendor**（待 ADR-0030 V1.1 修订分支决策后再清理），但 `chedl_wrapper.py` 创建可与修订并行（仅包装 `fluids.*` + `chemicals.*` 子集）

**P5 启动门（修订完成前/后均可推进 Task 25+26 哪些子步）**：

- 可立即推进：写 ADR-0030 V1.1 修订草稿 + 评估 `ht`/`CoolProp` 保留必要性
- 待修订签字后：移除 pyproject [tool.uv.sources]、清理 vendor、创建 chedl_wrapper.py、uv lock 重生成

### 障碍 3：工艺室 GB 精度阈值（阻塞 P5-3 启动）

**核验结果（用户 2026-09-16）**：**GB 阈值不能直接对标 API ≤2%** — GB/T 150.1 附录 B 与 API 521 在火灾工况下存在三处结构性差异（润湿面积计算 / 容器外壁修正系数 / 公式结构边界条件），同一台容器按两套标准计算的泄放量结果差异不是单位换算可以消除。

**分层阈值建议（用户裁决，2026-09-16）**：

**层级 1：火灾工况（GB/T 150.1 附录 B.1.3）**

| 对比基准 | 建议阈值 | 依据 |
|---|---|---|
| GB 标准算例（标准原文例题） | **≤2%** | 标准原文例题是精确复现的基准 |
| 工艺室手算（有明确计算书） | **≤5%** | 手算存在舍入、查图误差；5% 来自 GB/T 12241-2021 排量试验重复性 ±5% 要求 |
| 商业软件 GB 模块（如 HYSYS GB 算法） | **≤5%** | 软件实现细节 + 物性数据源差异 |
| 与 API 521 结果对比 | **不设阈值，仅记录偏差** | 两者计算路径不同，偏差是预期内，不应作验收标准 |

**层级 2：泄放面积（GB/T 12241-2021）**

| 对比基准 | 建议阈值 | 依据 |
|---|---|---|
| GB 标准算例 | **≤2%** | 标准原文例题 |
| 工艺室手算 | **≤5%** | 与火灾工况一致 |
| 安全阀厂家选型报告 | **≤5%** | 厂家选型通常比计算略保守 |

GB/T 12241 对排量试验测量误差要求 ±2% / 排量系数重复性 ±5%，可直接作为 GB 路径验收工程基准。

**层级 3：GB 两相流（复用 API 结果）**

建议 **≤5%**，与 API 路径一致。原因：GB 路径两相流在 P5 阶段是"复用 API 结果"，实际计算引擎仍是 API 520。

**工艺室书面签字路径**（P5-3 启动前必须完成）：

1. 起草 ADR-0028 决策 11 附录（GB 分层阈值三表 + 与 API 不同路径不对比声明）
2. 邮件发工艺室 + 标准负责人联签
3. 签字后更新 plan §613 / §793 / §800 三处阈值表 + SUP-P5-PSV-001 §7 验收表 GB 分支行

---

## 决议路径（用户裁决 2026-09-16）

P5 启动需要按以下顺序消除 3 项障碍：

### 已裁决路径

1. **障碍 1 btree_gist**：**DBA 预装方案** — DBA 在 pcs + pcs_test 两库以 superuser 执行 `CREATE EXTENSION btree_gist;`（详障碍 1 §DBA 执行清单）
2. **障碍 2 vendor 残留**：**先核验 + 修订 ADR-0030 V1.1，再清理** — 核验已完成（详障碍 2 §核验结果），发现 V1.8/ADR-0030 锁定清单 `{fluids, chemicals, ht}` 与实际 `{fluids, chemicals, thermo, ht, CoolProp}` 不一致；修订草稿作为 P5-0 批内首个 commit
3. **障碍 3 GB 阈值**：**采用分层阈值三表**（详障碍 3 §分层阈值建议）；待工艺室 + 标准负责人联签 ADR-0028 决策 11 附录后正式生效

### 执行顺序

1. **今日**：
   - DBA 执行 `CREATE EXTENSION btree_gist`（两库）
   - 起草 ADR-0030 V1.1 修订草稿（锁定清单扩展 + 包装函数扩展 + vendor 清理清单扩展 + ht/CoolProp 保留评估）
   - 起草 ADR-0028 决策 11 附录（GB 分层阈值三表 + 与 API 不同路径不对比声明）
2. **P5-0-6 启动前（Task 25）**：ADR-0030 V1.1 评审通过 → 清理 vendor → 创建 chedl_wrapper.py → uv lock 重生成
3. **P5-0-5 启动前（Task 24）**：btree_gist 扩展就绪 + ADR-0030 V1.1 已接受
4. **P5-3 启动前**：ADR-0028 决策 11 附录工艺室联签 → 更新 plan + SUP-P5-PSV-001 §7 验收表
5. **P5-0 批 7 task 全部 ratify**：进入 P5-1（VESSEL）

---

## 检查执行命令记录（可复现）

```bash
# 1+12 alembic baseline
cd pcs-backend && uv run alembic current
cd pcs-backend && uv run alembic -x dburl=postgresql+psycopg://pcs:pcs_dev@localhost:5432/pcs_test current

# 2 ruff
cd pcs-backend && uv run ruff check .

# 3 9 态 enum
PGPASSWORD=pcs_dev psql -U pcs -h localhost -d pcs -c "SELECT enumlabel FROM pg_enum e JOIN pg_type t ON e.enumtypid = t.oid WHERE t.typname='streamsignstatus' ORDER BY enumsortorder;"

# 4 测试基线
cd pcs-backend && uv run pytest --collect-only -q

# 5 vendor 残留
ls pcs-backend/vendor/ | grep -E '^(fluids|chemicals|thermo)$'
grep -rn "vendor" pcs-backend/pyproject.toml
grep -rn "^import fluids\|^from fluids\|^import chemicals\|^from chemicals\|^import ht\b\|^from ht\b" pcs-backend/app/ | grep -v chedl_wrapper

# 6 PG + DDL
PGPASSWORD=pcs_dev psql -U pcs -h localhost -d pcs -c "SELECT version();"
PGPASSWORD=pcs_dev psql -U pcs -h localhost -d pcs_test -c "SELECT version();"
PGPASSWORD=pcs_dev psql -U pcs -h localhost -d pcs -c "SELECT extname FROM pg_extension WHERE extname='btree_gist';"
PGPASSWORD=pcs_dev psql -U pcs -h localhost -d pcs -c "SELECT current_user, has_database_privilege(current_user, current_database(), 'CREATE') as can_create, current_setting('is_superuser') as is_super;"

# 7 uv 版本
uv --version

# 8 DataLineage
grep -rn "formula_version" pcs-backend/app/models/ pcs-backend/app/services/calc_lineage.py

# 9 ADR 状态
grep -E "^status:|accepted_date:" docs/adr/0028-psv-multi-standard-engine.md docs/adr/0030-chedl-version-lock.md

# 10 GB 阈值 — 待工艺室邮件确认（非脚本检查）

# 11 RECORD_TYPE_REGISTRY
cd pcs-backend && uv run python -c "from app.services.calc_lineage import RECORD_TYPE_REGISTRY; print(sorted(RECORD_TYPE_REGISTRY.keys())); print('count=', len(RECORD_TYPE_REGISTRY))"

# 12 启动快照
git rev-parse HEAD > pcs-p5-start-baseline.txt
echo "$(cd pcs-backend && uv run pytest --collect-only -q 2>&1 | tail -1)" >> pcs-p5-start-baseline.txt
echo "$(cd pcs-backend && uv run ruff check . 2>&1 | tail -1)" >> pcs-p5-start-baseline.txt
```
