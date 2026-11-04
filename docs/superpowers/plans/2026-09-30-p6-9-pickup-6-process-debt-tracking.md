# P6-9-PICKUP-6 计划 — Process-Debt 持续追踪批 (docs-only)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development.
> Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal**: 闭环 P6-9-PICKUP-5 之后剩余的 5D 工艺室触发项 docs 跟踪位（6 PROCo OPEN + 2 DOC OPEN），加固 docs/tasks.md as-of date stamp，建立 P6-9-PICKUP-5 批 archive 文档（`docs/P6-9-PICKUP-6.md`），确保未来 5D 启动时有清晰的 trigger schedule 与 file-level diff 闭环条件。

**Architecture**: docs-only 批，单 SDD workspace + 多 task 并行/顺序执行。所有 commit 必须满足 file-level diff 证据（R=1 教训，已写入 `.wolf/cerebrum.md`）。不动 ruff config / 不动 service code / 不动 alembic / 不动 tests fixture。

**Tech Stack**: Git + bash + ruff（验证用）+ pytest（baseline 验证）+ gate_08_openapi_contract.sh（仅 docs 改动需 regen 校验）

**Spec**: `docs/tasks.md`（21 → 22 findings + P6-7-4 新立，14 CLOSED / 8 OPEN）

## Global Constraints

- **R=1 教训（已写入 `.wolf/cerebrum.md` §SDD 批状态回填 + §SDD brief 验证）**: 任何 closure 状态回填必须指向 file-level diff；不可指向分类/路由文档；brief 中代码状态描述必须 source-verify（行号、文件路径、字段数）
- **3 OPEN 跟踪位不变**：OPEN-P6-6A-10 / OPEN-P6-9-PICKUP-2-1 / OPEN-P6-9-PICKUP-2-2
- **8 OPEN items 状态不变**：2 DOC 撤回（P5-123-1/2）+ 6 PROCo 待工艺室对账
- **pytest baseline**: 3515 passed (P6-9-PICKUP-5 R=1 后)
- **不动**：service code / schema / alembic / DB / tests fixture / API
- **严禁**：引入未授权 hook / 外部仓库集成
- **5D 工艺室触发 schedule**（按 docs/tasks.md + .wolf/STATUS.md）：
  - 2026-10-15：OPEN-P6-6A-11（PROCo-P6-7-{1,2,3,4} 工艺室校准）+ OPEN-P6-4-3（C-08 vessel Imperial）
  - 2026-10-31：OPEN-P6-6A-9.{3,4}（真 Wichert-Aziz + Bukacek 工艺复核）
  - 2026-11-15：OPEN-P6-6A-10（AS 1210 PDF）+ OPEN-P6-9-PICKUP-2-{1,2}（F2 SGR + t_wall HYSYS 工艺校准）+ PROCo-P6-8-{1,3}
  - 2026-11-30：OPEN-P6-6A-9.5 + OPEN-P6-6A-11（Nielsen Table 2-3 完整）

## Review Focus

5 个最可能咬人的输入类 / 失败模式，spec 未明示但 spec reviewer 会盯：

1. **docs/tasks.md 14/8 闭环 statement**：as-of date stamp 必须明确（"as of 2026-09-30"），不可模糊"近期"或"现在"
2. **5D 工艺室触发 schedule**：每条 OPEN item 必须标注对应工艺室交付日期（2026-10-15 / 10-31 / 11-15 / 11-30 / 上线后）+ 关联 trigger task 名
3. **docs/P6-9-PICKUP-6.md archive 文档**：必须包含 7 commits 全 SHA + 14 CLOSED / 8 OPEN 详情表 + R=1 lessons 引用 + 5D 触发 plan；类似 docs/P6-9-PICKUP-4.md 格式
4. **R=1 lesson 引用一致性**：brief 验证纪律（行号核实 / file existence check / 字段数实测）必须在 docs/P6-9-PICKUP-6.md 中体现，避免下一批重蹈覆辙
5. **CHANGELOG.md 与 README.md 一致性**：顶部 P6-9-PICKUP-6 行与 README P6-9-PICKUP-6 闭环行日期 / commit 引用对齐

---

## Sub-batch T1: docs/tasks.md 闭环 statement + 5D 工艺室触发占位

**Files**:
- Modify: `docs/tasks.md`（第 92-100 行 总计 14/8 闭环 statement + 第 138-160 行 工艺室 2026-11-15 交付对账预留 + 第 130-135 行 P6-9-PICKUP-5 候选跟踪 + 新增第 160-180 行 5D 工艺室触发 schedule）

**Interfaces**:
- Consumes: 14 CLOSED / 8 OPEN 状态（P6-9-PICKUP-5 后 as of 2026-09-30）
- Produces: docs/tasks.md 闭环 statement 强化 + 5D 触发 schedule table + 6 PROCo + 2 DOC OPEN items 跟踪位

**Steps**:

- [ ] **Step 1**: 强化第 92-100 行 闭环 statement：
  ```
  闭环状态：as of 2026-09-30
  14 项 CLOSED via P6-9-PICKUP-5（HYG 8 / DOC 4 / REF 2）
  8 项 OPEN：DOC 2（P5-123-{1,2} 撤回）+ PROCo 6（工艺室 2026-10-15/11-15/11-30 触发）
  HYG 0 / REF 0 全部闭环
  ```
- [ ] **Step 2**: 新增 5D 工艺室触发 schedule section（建议第 160-180 行）：
  ```
  ## 5D 工艺室触发 schedule

  | 触发日期 | OPEN items | 5D 子批 | 工时估算 |
  |---|---|---|---|
  | 2026-10-15 | OPEN-P6-6A-11（PROCo-P6-7-{1,2,3,4}）+ OPEN-P6-4-3 | 5D-1 psychro 工艺室校准 | ~2.0 天 |
  | 2026-10-31 | OPEN-P6-6A-9.{3,4}（真 Wichert-Aziz + Bukacek 复核）| 5D-2 Behr 工艺室复核 | ~1.5 天 |
  | 2026-11-15 | OPEN-P6-6A-10（AS 1210 PDF）+ OPEN-P6-9-PICKUP-2-{1,2}（F2 SGR + t_wall HYSYS）+ PROCo-P6-8-{1,3} | 5D-3 综合工艺室交付 | ~2.5 天 |
  | 2026-11-30 | OPEN-P6-6A-9.5 + OPEN-P6-6A-11（Nielsen Table 2-3）| 5D-4 Nielsen 工艺室交付 | ~1.5 天 |
  | 上线后 | OPEN-P6-4-2（Kb 厂商数据）| 5D-5 上线后批 | 推迟 |

  总计触发：6 PROCo + 2 DOC 撤回 + 5 OPEN 跟踪位 = 13 item 关联 5 个 5D 子批
  ```
- [ ] **Step 3**: 更新 6 PROCo + 2 DOC OPEN items 行的「状态」列：
  - PROCo-P6-7-{1,2,3}：状态列补「→ 5D-1 触发（2026-10-15 后）」
  - PROCo-P6-7-4（5B R=1 新立）：状态列补「→ 5D-1 触发（2026-10-15 后）」
  - PROCo-P6-8-{1,3}：状态列补「→ 5D-3 触发（2026-11-15 后）」
  - DOC-P5-123-{1,2}：状态列保持「OPEN（撤回 0 matches，无证据）」+ 标注「保留 OPEN 跟踪位；不计入 5D 触发」（说明撤回决策与 OPEN 状态并存）
- [ ] **Step 4**: 验证 grep 一致性：
  ```bash
  grep -c "as of 2026-09-30\|5D-1\|5D-2\|5D-3\|5D-4" docs/tasks.md
  # 期望：≥ 5
  ```

## Sub-batch T2: docs/P6-9-PICKUP-6.md archive 文档（仿 docs/P6-9-PICKUP-4.md）

**Files**:
- Create: `docs/P6-9-PICKUP-6.md`（新建，仿 docs/P6-9-PICKUP-4.md 格式）

**Interfaces**:
- Consumes: P6-9-PICKUP-5 batch 全部信息（7 commits + 14 CLOSED / 8 OPEN 详情 + R=1 lessons）
- Produces: ~150-200 行 archive 文档

**Steps**:

- [ ] **Step 1**: 创建 `docs/P6-9-PICKUP-6.md`，标题「P6-9-PICKUP-5 工艺债务批 archive（2026-09-30）」
- [ ] **Step 2**: 写入结构（仿 docs/P6-9-PICKUP-4.md）：
  ```
  # P6-9-PICKUP-5 工艺债务批 archive
  
  > 来源：P6-9-PICKUP-6 docs-only 批（2026-09-30）
  > 上游：docs/tasks.md 21 + 1 项 findings（P6-9-PICKUP-6 R=1 + 5B R=1 Nielsen x 漂移）
  > 本文档：P6-9-PICKUP-5 7 commits 全 SHA + 14 CLOSED / 8 OPEN 详情 + R=1 lessons
  
  ## 来源 + 分布
  
  ## HYG-2 ruff D + .gitattributes（5A 60444e5）
  
  ## DOC-4 SPEC V1.13 + service docstring（5B fd56fa8 + 2f2e80a + ae91e75 + dbdd6a1）
  
  ## REF-2 子模块拆分（5C d8f97dd + 9df10cc）
  
  ## R=1 教训
  
  ## 5D 工艺室触发 schedule
  
  ## 未解决问题
  ```
- [ ] **Step 3**: 写入 P6-9-PICKUP-5 batch 5A/5B/5C 各 task 详情（line range + 关键改动 + commit 引用）
- [ ] **Step 4**: 写入 3 implementer judgment calls（5A per-file-ignores / 5B UI-SPEC→ADD-001 / 5C stripping-gas 占位 vs Antoine）+ R=1/R=2 ledger accuracy 修复
- [ ] **Step 5**: 验证文档完整性：
  ```bash
  wc -l docs/P6-9-PICKUP-6.md
  # 期望：150-250 行
  grep -c "60444e5\|fd56fa8\|2f2e80a\|ae91e75\|dbdd6a1\|d8f97dd\|9df10cc" docs/P6-9-PICKUP-6.md
  # 期望：≥ 7（每个 commit 至少 1 引用）
  ```

## Sub-batch T3: CHANGELOG.md + README.md 顶部 P6-9-PICKUP-6 行

**Files**:
- Modify: `CHANGELOG.md`（顶部新增「P6-9-PICKUP-6 process-debt tracking」行）
- Modify: `README.md`（如需要，闭环行）

**Interfaces**:
- Consumes: docs-only 批落地信息
- Produces: CHANGELOG/README 一致性

**Steps**:

- [ ] **Step 1**: CHANGELOG.md 顶部新增：
  ```
  ## P6-9-PICKUP-6 process-debt tracking（2026-09-30）
  - docs/tasks.md: 14/8 闭环 statement 加固 + as-of date + 5D 工艺室触发 schedule
  - docs/P6-9-PICKUP-6.md archive 文档新建
  ```
- [ ] **Step 2**: README.md 检查 P6-9-PICKUP 闭环 section（如有）；如已含 P6-9-PICKUP-5 行则新增 P6-9-PICKUP-6 行；如未含则保持不动（不破坏 README 既有结构）
- [ ] **Step 3**: 验证 grep 一致性：
  ```bash
  head -30 CHANGELOG.md | grep "P6-9-PICKUP-6"
  # 期望：含 P6-9-PICKUP-6 引用
  ```

## Sub-batch 收口: G-08 + ruff + pytest + push + workspace cleanup

**Files**:
- 无新增；仅验证 + push

**Steps**:

- [ ] **Step 1**: G-08 phase 1-4 验证（docs-only 改动可能影响 openapi.json baseline）：
  ```bash
  bash pcs-backend/scripts/gate_08_openapi_contract.sh --check-baseline 2>&1 | tail -20
  ```
  期望：阶段 1-4 全过；baseline diff = 0
- [ ] **Step 2**: ruff 全 0 验证：
  ```bash
  cd pcs-backend && uv run ruff check . 2>&1 | tail -3
  # 期望：All checks passed!
  ```
- [ ] **Step 3**: pytest 回归（docs-only 应 0 regression）：
  ```bash
  cd pcs-backend
  DATABASE_URL=postgresql+psycopg://pcs:pcs_dev@localhost:5432/pcs_test uv run pytest tests/ -q 2>&1 | tail -5
  # 期望：3515 passed, 0 failed
  ```
- [ ] **Step 4**: 单 commit + push：
  ```bash
  cd /home/pangzy/code_project/PCS
  git add docs/tasks.md docs/P6-9-PICKUP-6.md CHANGELOG.md README.md
  git status --short
  git commit -m "docs(p6-9-pickup-6): process-debt tracking批 docs only — 5D 工艺室触发占位 + archive 文档"
  git push origin main 2>&1 | tail -5
  ```
- [ ] **Step 5**: `.wolf/STATUS.md` 更新 P6-9-PICKUP-6 entry + `.wolf/cerebrum.md` 5D 触发占位记录（如有新 lessons）
- [ ] **Step 6**: SDD workspace 清理 `.superpowers/sdd/2026-09-30-p6-9-pickup-6-process-debt-tracking/`

## 关键文件路径

- `docs/tasks.md`（as-of date stamp + 5D 触发 schedule + OPEN items 跟踪位）
- `docs/P6-9-PICKUP-6.md`（archive 新建）
- `CHANGELOG.md`（顶部 P6-9-PICKUP-6 行）
- `README.md`（顶部 P6-9-PICKUP-6 行；如有）
- `.wolf/STATUS.md`（批次登记）
- `.wolf/cerebrum.md`（Do-Not-Repeat lessons）

## 复用清单

| 现有 | 路径 | 复用任务 | 用法 |
|---|---|---|---|
| `docs/P6-9-PICKUP-4.md` 模板 | `docs/P6-9-PICKUP-4.md` | T2 | archive 文档格式仿此（5 个 section 结构） |
| P6-9-PICKUP-5 7 commits SHA | `git log --oneline 376ca2c..9df10cc` | T2 | archive 全列 commit SHA |
| P6-9-PICKUP-5 闭环详情 | 9df10cc commit msg + 5C report | T2 | archive 内容来源 |
| docs/tasks.md 既有 14/8 状态 | `docs/tasks.md` | T1 Step 1 | 强化 + as-of date |
| 工艺室 OPEN items 跟踪 | `docs/tasks.md:138-160` + `.wolf/STATUS.md` | T1 Step 3 | 5D 触发 schedule 来源 |
| CHANGELOG 顶部已有 P6-9-PICKUP-6 行格式 | `CHANGELOG.md` 顶部 | T3 | 新行格式一致 |
| gate_08_openapi_contract.sh | `pcs-backend/scripts/gate_08_openapi_contract.sh` | 收口 Step 1 | baseline diff 验证 |

## 端到端验证矩阵

| # | 项 | 命令 | 期望 |
|---|---|---|---|
| T1-1 | docs/tasks.md as-of | `grep "as of 2026-09-30" docs/tasks.md` | ≥ 1 |
| T1-2 | 5D 触发 schedule | `grep "5D-1\|5D-2\|5D-3\|5D-4" docs/tasks.md` | ≥ 4 |
| T2-1 | archive 文档行数 | `wc -l docs/P6-9-PICKUP-6.md` | 150-250 |
| T2-2 | 7 commits 引用 | `grep -c "60444e5\|fd56fa8\|2f2e80a\|ae91e75\|dbdd6a1\|d8f97dd\|9df10cc" docs/P6-9-PICKUP-6.md` | ≥ 7 |
| T3-1 | CHANGELOG P6-9-PICKUP-6 | `head -10 CHANGELOG.md` | 含 P6-9-PICKUP-6 引用 |
| 收-1 | G-08 phase 1-4 | `bash pcs-backend/scripts/gate_08_openapi_contract.sh --check-baseline` | baseline diff = 0 |
| 收-2 | ruff 全 0 | `cd pcs-backend && uv run ruff check .` | All checks passed! |
| 收-3 | pytest 0 regression | `cd pcs-backend && DATABASE_URL=... uv run pytest tests/ -q` | 3515 passed, 0 failed |
| 收-4 | push | `git log --oneline -1 origin/main` | 新 commit SHA |

## 风险 + 缓解

| 风险 | 等级 | 缓解 |
|---|---|---|
| R-1 docs/tasks.md as-of date stamp 缺失 → 闭环 statement 模糊 | 低 | T1 Step 4 grep 验证 |
| R-2 5D 触发 schedule 与 docs/tasks.md 工艺室 OPEN items 不匹配 | 中 | T1 Step 3 逐条核对 .wolf/STATUS.md OPEN items list |
| R-3 docs/P6-9-PICKUP-6.md 内容不全（漏 R=1 lessons 或 5D schedule） | 中 | T2 Step 5 验证 7 commits 引用 + R=1 lessons section |
| R-4 G-08 baseline drift（docs 改动触发 openapi regen） | 低 | 收口 Step 1 跑 gate_08；如 drift 评估是否需 roll-back docs |
| R-5 R=1 教训再现 — closure 状态回填不可指文档 | 中 | 收口 commit msg 显式引用 `9df10cc` (HYG 2 row) 等具体 commit SHA |

## 工时表

| Sub-batch | 工时 |
|---|---|
| T1 docs/tasks.md 闭环 + 5D 触发 | 0.3 天 |
| T2 docs/P6-9-PICKUP-6.md archive | 0.4 天 |
| T3 CHANGELOG + README | 0.1 天 |
| 收口 + wolf + workspace cleanup | 0.2 天 |
| **总计** | **~1.0 工作日** |

## 后续

P6-9-PICKUP-6 docs-only 落地后 → 等工艺室 2026-10-15 交付 → 启动 5D-1（psychro 工艺室校准 ~2.0 天）；后续 5D-2/3/4 跟随工艺室 2026-10-31/11-15/11-30 交付触发。

## 未解决问题

1. **OPEN-P6-4-2**（Kb 厂商数据）— 推迟到上线后批（OPEN-P6-6A-10 PDF 升级是关键依赖）
2. **2 DOC OPEN（P5-123-{1,2}）** — 撤回 statement 保留 OPEN 跟踪位；不计入 5D 触发
3. **5D 工艺室交付 schedule** — 完全依赖工艺室 2026-10-15/10-31/11-15/11-30 时间表；如延期需相应推迟 5D 子批
4. **R=1 lesson（brief 验证）应用** — 已写入 cerebrum.md；下批 brief 应加 source-verify 步骤（行号 + 文件存在 + 字段数实测）