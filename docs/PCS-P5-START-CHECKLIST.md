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

### 障碍 2：ChEDL vendoring 残留（阻塞 Task 25 + Task 26）

- **现状**：`pcs-backend/vendor/fluids` + `vendor/chemicals` + `vendor/thermo` 三个本地副本；`pyproject.toml:70-72` `[tool.uv.sources]` 仍指向 vendor
- **冲突**：ADR-0030 决策 3 要求"取消 vendoring，依赖 uv/pip 安装"；`fluids==1.3.1` 精确版本（决策 1/2）要求单一来源 `pyproject.toml`；当前 vendor + pyproject 双源并存
- **同时缺**：`pcs-backend/app/services/chedl_wrapper.py` 文件不存在（Task 26 待建）
- **解决方案（Task 25 + 26 启动前必须执行）**：
  1. 备份 `vendor/{fluids,chemicals,thermo}` 三目录（移到 `vendor/_archived_2026-09-16/` 备查，避免 GPL 传染传播）
  2. 移除 `pyproject.toml:70-72` `[tool.uv.sources]` 三行
  3. `uv lock` 重生成（验证 `fluids==1.3.1` / `chemicals==1.5.2` 来自 PyPI）
  4. 创建 `pcs-backend/app/services/chedl_wrapper.py`（决策 6 + 决策 7 fallback 语义，详 ADR-0030 §99-§140）
  5. 写 Task 25 测试断言：`uv run python -c "import fluids; assert fluids.__version__ == '1.3.1'"` + `import chedl_wrapper` smoke test
  6. 写 ADR-0030 附录 A 第一行：升级历史 = `2026-09-16 P5 启动 vendor 清理 + pyproject.toml 单一来源`

### 障碍 3：工艺室 GB 精度阈值（阻塞 P5-3 启动）

- **现状**：plan §613 / §615 / §793 / §800 / §801 多处写"阈值由工艺室确认"
- **影响**：Task 13 / Task 14 / Task 16 / Task 17 测试基线无法定稿（≤5% vs ≤2% 影响测试用例数与通过率）
- **解决方案**：P5-3 启动评审会上书面确认；建议 ≤5%（GB 路径润湿面积计算与 API 差异较大，2% 可能不可达）

---

## 决议路径

P5 启动需要按以下顺序消除 3 项障碍：

1. **今日**：DBA 沟通 btree_gist 权限（方案 A/B/C 待裁决） + 工艺室 GB 阈值邮件确认
2. **P5-0-6 启动前**：vendor 清理 + chedl_wrapper.py 创建（Task 25 启动门槛）
3. **P5-0-5 启动前**：btree_gist 扩展就绪（Task 24 启动门槛）
4. **P5-0 批 7 task 全部 ratify**：进入 P5-1（VESSEL）

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
