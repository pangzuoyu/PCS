# P9B-3 实施计划：本地 PG 车道 + 系统参数 + SIM 物流前端（SPEC §7.7 / §7.20）

> **For agentic workers:** REQUIRED SUB-SKILL: `superpowers:executing-plans`
> （或 `superpowers:subagent-driven-development`）。
> ledger: `.superpowers/sdd/PCS-PLAN-P9B-3-系统参数与SIM物流前端/progress.md`
>
> ⚠️ **本计划已吸收 2026-11-02 委员会的 8 条裁决 + 7 条前置核实**（见下）⇒
> 开工前**不需要**再问同一批问题。**「尚未解决的问题」一节是唯一还需要裁决的**。

**Goal:** 补上三块欠账 —— ①**本地 PG 车道**（TODO-099：PG 专属语义至今零自动化
覆盖）②**§7.20 系统参数页**（`system_settings` 表存在但零 API，前端零页面）
③**§7.7 SIM 物流前端**（列表工具栏/筛选/引用列、手动创建向导、详情页 7 个 Tab、
单条「提交校对」—— 三个页面目前都是极简占位）。

**Architecture:** 三个**互不依赖**的子系统，按「基础设施 → 契约 → 业务」顺序落地：
- **T0** 是**基础设施**（docker-compose `pg` profile 独立实例 + `pcs_pgtest` 库 +
  `scripts/pytest_pg.sh` 唯一入口）⇒ 它是 T3/T6/T8 里 PG 专属断言的**载体**；
- **T2**（SPEC V2.6）**先于**所有代码 —— CLAUDE.md 规定「前端唯一依据是 SPEC」，
  且「与 OpenAPI 冲突时以 OpenAPI 为准并**登记 SPEC 修订**」⇒ 契约先落；
- **T4**（系统参数后端）→ **T5**（系统参数前端）是**一条链**（端点 → 页面）；
  **T6/T7/T8**（物流列表 → 手动创建向导 → 详情页 Tab）是**另一条链**（列表页的
  「新建物流」跳向导，向导写完回列表，列表展开进详情）。

**Tech Stack:** React 19 + TypeScript + antd 5 + axios + zustand + vitest + MSW +
Playwright；后端 FastAPI + SQLAlchemy 2.x async + pytest + alembic。

**Spec:** 本文档即设计（委员会 2026-11-02 裁决 + 前置核实结论）⇒ 计划自证其依据。

---

## Global Constraints

| 约束 | 精确值 |
|---|---|
| 提交约定 | conventional commits，**无 attribution 行**；长消息写文件后 `git commit -F` |
| 分支 | 直提 `main`，**禁 worktree**（用户长期裁决 + 历史事故） |
| 每个 task 一 commit | 每批一收口报告 |
| 前端类型来源 | **契约派生**（`components['schemas'][...]`）；⚠️ 手写 union 是 bug-2040 那类漂移根因 |
| 后端错误 | 全仓唯一 `PcsError`（`app/core/errors.py`）；业务码大写蛇形 + HTTP 状态码 |
| 审计 | 状态变更写 `audit_logs`（`AuditService.write`）；动作名加进 `AuditAction` 枚举 |
| 口令 | **不上命令行**（会被权限分类器拦 + 进 shell 历史）⇒ 进程内派生 / 环境变量 |
| 验多库 | **每库一个独立进程**（alembic 的 `settings` 是 pydantic 缓存实例）⇒ 且**直查库**确认 |
| 行锁断言 | 方言级 SQL 断言（PG 方言编译出 `FOR UPDATE`）+ 接线断言；**不**依赖 SQLite |
| SPEC | 前端唯一编码依据；与 OpenAPI 冲突时以 OpenAPI 为准并**登记修订**（§12.4 加行） |
| 契约门禁 | 每批末 `bash pcs-backend/scripts/gate_08_openapi_contract.sh --check-baseline` |
| 发布前清单 | `CLAUDE.md` 的「发布前检查（必做）」四条（见 T0） |

## Review Focus

写实现前先读这五条 —— 每条对应一个**测试**，钉在拥有该代码的 task 里：

1. **批量保存系统参数时中途失败** ⇒ 期望**全不改**（不是改了一半）。
   → 钉在 **T4**（后端事务原子性测试）。
2. **后端返回 9 态之外的 `sign_status`** ⇒ 期望**降级显示**（`StateBadge` 的
   `unknownBadge`），不是 `TypeError` 整页崩（P9B-2F #14 的同形，新页面别重犯）。
   → 钉在 **T6**（列表）与 **T8**（详情）。
3. **物流组成合计 98.7%** ⇒ 期望送审**被拒**（422，具名错误码），不是放行。
   → 钉在 **T3**。
4. **PG 车道在 PG 没起 / 测试被全 skip 时** ⇒ 期望**非零退出**，不是「全绿」。
   → 钉在 **T0**。
5. **同一条 stream 被并发提交校对两次** ⇒ 期望**一胜一拒**（行锁），
   不是两次都成功（P9B-2 报告 #1 的同形）。→ 钉在 **P9B-3b**（本批只做单条，
   并发断言随批量端点一起做）。

---

## 委员会裁决（2026-11-02）

| # | 项 | 裁决 |
|---|---|---|
| 1 | §7.20 三页后端落法 | 选项 1（复用 `system_settings` + 新建 `prompt_templates`）—— ⚠️ **但见裁决 2**：AI 开关页与 Prompt 模板页**本批不做** ⇒ 实际只做**系统参数页** |
| 2 | AI 开关 + Prompt 模板 | **不做**（P10 前无下游消费者；未来签名未知 ⇒ 现在做要全部推翻）⇒ **必须同步修改 SPEC §7.21** |
| 3 | 角色分配（TODO-092） | **本批不做**（选项 3）⇒ 「AD 同步覆盖 roles」是**当前行为**，必须写进计划；角色来源权威性**升格独立 ADR**（不是计划里能拍的） |
| 4 | TODO-099 PG 车道 | **选项 1**（本地 PG 车道）+ 三条硬约束 + 一条复审触发（见 T0） |
| 5 | 校对批量 | D1~D6 六条决策全部采纳 ⇒ **单列 P9B-3b**（见文末移交节） |

## 事实基础（2026-11-02 实测，非推断）

### 后端

| 面 | 现状 | 出处 |
|---|---|---|
| `streams` 写面 | `POST /streams`（创建）· `POST /streams/validate` · `PATCH/DELETE /streams/{id}` | `app/api/v1/streams.py:202,241,325,347` |
| 物流状态机 | `POST /streams/{id}/submit`（**DRAFT → IN_APPROVAL**）· `approve` · `reject` · `initiate-change` · `pass-change` · `mark-stale` | `streams.py:518…604` |
| 物性 / 状态点 | `GET /streams/{id}/properties` · `POST .../estimate` · `GET /streams/{id}/state-points` | `streams.py:635,663,402` |
| 血缘 | `GET /lineage/{record_type}/{record_id}/upstream|downstream|graph` | `app/api/v1/lineage.py:28,59,92` |
| 审计读 | `GET /audit-logs` **已支持** `resource_type` / `resource_id` / `action` / `user_id` / 时间区间过滤 | `app/api/v1/audit.py:40-70` |
| `system_settings` | 表存在、**零 API**、**零行**；`setting_key` = **主键**（UNIQUE）· `setting_value_json` = **JSONB** · 无 `updated_by` · 无 CHECK | `app/models/system.py:140` + `dd47298c9c38…:293` |
| Prompt 模板 | **无表、无 API** | `grep -rniE "prompt_template"` = 0 命中 |
| AI 开关 | **无端点**；`ai_audit_log` 表存在（仅审计） | `app/models/system.py:185` |
| 角色分配 | `admin_users` 只有 list / disable / sync 三个端点 ⇒ TODO-092 确认 | `app/api/v1/admin_users.py:84,94,116` |

### 前端

| 面 | 现状 |
|---|---|
| `StreamListPage.tsx` | **140 行**：只有状态分页签 + 表格；**无**工具栏（导入/新建物流/提交校对/导出）· **无**筛选（工况/相态/状态/来源）· **无**引用列 |
| `StreamDetailPage.tsx` | **266 行**：只有「基础信息」Descriptions + 「组成」Table 两个 Card；**无 Tab**（SPEC 要 7 个） |
| `ImportWizardPage.tsx` | **105 行**：2 步（预览 / 确认）；SPEC §7.7.3 要 7 步（含「手工」分支 / Excel 列映射） |
| `src/api/stream.ts` | **1017B**：只有 `listByProject` + **手写** `StreamListItem`（5 字段）⇒ 契约脱钩 |
| ADMIN 页 | `UserAdminPage.tsx` ✓ · `ProjectAdminPage.tsx` ✓ · 系统参数 / 角色分配 / AI 开关 / Prompt 模板 ✗ |

### 七条前置核实的结论

| 核实 | 结论 |
|---|---|
| 1 `system_settings` 表结构 | **适合复用**：`setting_key` 是主键（UNIQUE ✓）· JSONB ✓ · 真库 0 行（无存量要迁）· 无 `updated_by` **不是缺口**（全仓口径是 `updated_at` + `audit_logs` 写审计，`config_assets` 同样没有 `updated_by`）⇒ **不需加列** |
| 2 AI 开关是否独立概念 | 是 key 前缀（方案 A）—— ⚠️ 但 SPEC §7.21 明写「**P10 前禁用**」⇒ **无消费者** ⇒ 裁决 2：**不做** |
| 3 Prompt 模板是否要版本 | SPEC **无**版本要求 ⇒ 覆盖式 + 审计 —— ⚠️ 随裁决 2 **不做** |
| 4 「复用」≠「零成本」 | 表存在 ≠ API 存在 ⇒ 仍需 **1 service + 1 router + 批量原子端点**（T4） |
| A `StreamSignStatus` 状态机 | **9 态**（与 `RecordSignStatus9` 字面对齐）：DRAFT / IN_APPROVAL / CHECKED / CHECK_REJECTED / STALE / CHANGE_PENDING / CHANGED / REVERSAL_PENDING / OBSOLETE ⇒「提交校对」= `SUBMIT_FOR_CHECK` = **DRAFT → IN_APPROVAL** |
| B 单条提交端点是否存在 | **存在** ✓ `POST /streams/{id}/submit`（ACL：DESIGNER / PROCESS_CONTROLLER / SYSTEM_ADMIN；`reason=None`）⇒ 批量端点是「N 次单条语义的批量化」 |
| C 校核记录存哪 | **在 `audit_logs`**（动作 `RECORD_TRANSITION`，`resource_type='streams'`，与记录侧同构）⇒ `GET /audit-logs` 已能按 `resource_type` + `resource_id` 过滤 ⇒ **校核记录 Tab 不需要新后端端点** |

### ⚠️ 与委员会 brief 的三处偏差（计划按**实测**写，不是按 brief 写）

1. **状态名**：brief 假设 `DRAFT → PENDING`；实测是 **`DRAFT → IN_APPROVAL`**（9 态字面对齐记录侧）⇒ 幂等判定、审计 action 名、错误码文案全部按 `IN_APPROVAL` 写。
2. **审计动作**：brief 建议新动作 `STREAM_SUBMITTED_FOR_REVIEW`；实测 streams 的转移**复用** `RECORD_TRANSITION`（`state_machine.TRANSITION_AUDIT_ACTION`）⇒ **不新造动作**（新造会让「按动作查审计」分裂成两套）。只有**批次**那条是新动作 `STREAM_BATCH_SUBMITTED`（P9B-3b）。
3. **组成合计校验不存在**（`grep COMPOSITION` = 0 命中）⇒ brief 里的失败原因 `COMPOSITION_SUM_OUT_OF_RANGE` **需要新建**（T3），不是「复用既有的」。

---

## NOT in scope（本批明确不做）

| 不做 | 理由 | 归属 |
|---|---|---|
| **AI 开关页 + Prompt 模板页**（含后端表与 API） | P10 前无下游消费者；未来签名未知 ⇒ 现在做要全部推翻（裁决 2） | P10（随 AI 助手本体） |
| **角色分配页**（含 `PUT /admin/users/{id}/roles`） | 「手工优先」是 ADR 级改动；角色来源权威性**升格独立 ADR**（裁决 3） | 独立 ADR + 后续批次 |
| **批量「提交校对」** | 委员会裁决 5：六条契约决策量大 ⇒ 单列 | **P9B-3b**（文末移交节） |
| AI 助手本体（对话面板 / 知识检索 / 相似设备） | P10 | P10 |
| `prompt_templates` 表与迁移 | 随裁决 2 | P10 |
| 物流 Excel 列映射 / 模板库（§7.7.3 步骤 4） | 本批只做**手工**分支（T7） | P9B-4 |
| §7.7.2 的「物性」页内编辑 | `POST /streams/{id}/properties/estimate` 已有，只读展示 + 触发估算 | 后续 |

---

## 文件结构

**后端（新增）**

```
pcs-backend/app/schemas/system_settings.py      # T4：SystemSettingOut / SystemSettingBatchIn
pcs-backend/app/services/system_setting_service.py  # T4：批量原子写
pcs-backend/app/api/v1/system_settings.py       # T4：GET /system-settings · PUT /system-settings
pcs-backend/scripts/pytest_pg.sh                 # T0：PG 车道唯一入口（fail-closed）
pcs-backend/scripts/gen_compact_orm.py           # T1：compact ORM 表生成器（TODO-103）
pcs-backend/tests/api/v1/test_system_settings.py # T4
pcs-backend/tests/api/v1/test_stream_composition_sum.py  # T3
pcs-backend/tests/scripts/test_pytest_pg_gate.py # T0：脚本的 fail-closed 行为
pcs-backend/tests/alembic/test_p9_013_bind_default_record_matrix.py  # T0：docstring 再更正
pcs-backend/tests/alembic/test_p9_014_record_approval_chain_snapshot.py  # T0：docstring 再更正
```

**后端（修改）**

```
pcs-backend/app/models/enums.py                  # T4：AuditAction 加 SYSTEM_SETTINGS_UPDATED
pcs-backend/app/api/v1/streams.py                # T3：submit 前加组成合计校验
pcs-backend/app/api/v1/projects.py               # T1：IntegrityError 只在命中 project_no 时映射 409
pcs-backend/app/api/v1/__init__.py               # T4：挂 system_settings router
pcs-backend/pyproject.toml                       # T0：注册 pg marker
pcs-backend/docs/openapi.json                   # T4：契约重滚
```

**前端（新增）**

```
pcs-frontend/src/api/systemSettings.ts           # T5
pcs-frontend/src/pages/admin/SystemSettingsPage.tsx  # T5
pcs-frontend/src/pages/sim/StreamManualWizardPage.tsx  # T7
pcs-frontend/src/pages/sim/tabs/StreamBasicTab.tsx      # T8
pcs-frontend/src/pages/sim/tabs/StreamCompositionTab.tsx  # T8
pcs-frontend/src/pages/sim/tabs/StreamPropertiesTab.tsx  # T8
pcs-frontend/src/pages/sim/tabs/StreamStatePointsTab.tsx  # T8
pcs-frontend/src/pages/sim/tabs/StreamConnectionsTab.tsx  # T8
pcs-frontend/src/pages/sim/tabs/StreamLineageTab.tsx      # T8
pcs-frontend/src/pages/sim/tabs/StreamReviewLogTab.tsx    # T8
```

**前端（修改）**

```
pcs-frontend/src/api/stream.ts                   # T6/T7/T8：契约派生类型 + 新端点封装
pcs-frontend/src/pages/sim/StreamListPage.tsx    # T6：工具栏 / 筛选 / 引用列 / 行操作
pcs-frontend/src/pages/sim/StreamDetailPage.tsx  # T8：改成 7 Tab 宿主（拆子组件）
pcs-frontend/src/router/App.tsx（实为 src/App.tsx）  # T5：/admin/system-settings 路由 + 菜单
pcs-frontend/src/types/api.d.ts                 # T4：契约重滚（生成物，勿手改）
```

**文档**

```
docs/PCS-UI-SPEC.md        # T2：§12.4 加 V2.6 行 + §7.7/§7.20/§7.21 正文
TODOS.md                   # T2：TODO-092 升格 ADR 的登记 + TODO-100 的 scope 登记
CLAUDE.md                  # T0：发布前检查（必做）清单
docker-compose.yml         # T0：pg profile 独立实例
```

---

## Task T0：本地 PG 车道（TODO-099 · 裁决 4）

**Files:**
- Modify: `docker-compose.yml`（加 `postgres-pgtest` 服务 + `pgtestdata` 卷）
- Modify: `pcs-backend/pyproject.toml`（注册 `pg` marker）
- Create: `pcs-backend/scripts/pytest_pg.sh`
- Create: `pcs-backend/tests/scripts/test_pytest_pg_gate.py`
- Modify: `pcs-backend/tests/alembic/test_p9_013_bind_default_record_matrix.py`（docstring 再更正）
- Modify: `pcs-backend/tests/alembic/test_p9_014_record_approval_chain_snapshot.py`（同上 + 标 `pg`）
- Modify: `CLAUDE.md`（发布前检查清单）

**Interfaces:**
- Consumes: `tests/alembic/` 里现有的 PG 引擎级测试（p9_013 两条 + p9_014 两条）。
- Produces: **`scripts/pytest_pg.sh`** —— 全仓**唯一**的 PG 车道入口；
  `pg` pytest marker（`pytest -m pg` 只选 PG 专属用例）；CLAUDE.md 的发布前清单。

- [ ] **Step 1: 写脚本行为测试（先红）**

```python
# pcs-backend/tests/scripts/test_pytest_pg_gate.py
"""scripts/pytest_pg.sh 的 fail-closed 行为（T0 · TODO-099 · 裁决 4 约束 1）。

## 为什么这个文件存在

「一键脚本」如果没有**强制力**，等于没有 —— 没人跑就等于没做。
委员会的三条硬约束里第一条就是「**fail-closed**」：
PG 没起 ⇒ FAIL；收集到 0 个 PG 测试 ⇒ FAIL；测试被全 skip ⇒ FAIL。
⇒ 这三条必须**有测试**，否则「脚本写了但没人跑」与「脚本不存在」不可区分
（同 `docs/solutions/testing-issues/guard-test-fooled-by-lying-comment.md`）。
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "pytest_pg.sh"


def _run(env_extra: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(SCRIPT)],
        cwd=SCRIPT.parents[1],
        env={**os.environ, **env_extra},
        capture_output=True,
        text=True,
        timeout=120,
    )


def test_script_exists_and_is_executable():
    assert SCRIPT.exists(), "PG 车道入口脚本不存在"
    assert os.access(SCRIPT, os.X_OK), "脚本不可执行"


def test_fails_when_pg_instance_is_not_running():
    """PG 实例没起 ⇒ 非零退出 + 明确提示（不是「跳过」）。"""
    r = _run({"PG_COMPOSE_PROJECT": "pcs_pg_absent_project"})
    assert r.returncode != 0, "PG 没起却退出 0 ⇒ 假绿"
    assert "docker compose --profile pg up -d" in (r.stdout + r.stderr)


def test_fails_when_zero_pg_tests_are_collected():
    """收集到 0 个 PG 测试 ⇒ 非零退出（「收集到 0 个」不是「通过」）。"""
    r = _run({
        "PG_COMPOSE_PROJECT": "pcs_pg_absent_project",
        "PG_PYTEST_MARK": "pg",  # 默认
    })
    # 上例已因 PG 未起而失败；本例单独验证「收集到 0 个」这一条：
    r2 = _run({"PG_COMPOSE_PROJECT": "pcs_pg_absent_project",
               "PG_PYTEST_MARK": "no_such_marker_xyz"})
    assert r2.returncode != 0


def test_script_does_not_teach_a_second_entry_point():
    """⚠️ 唯一入口：脚本里不得出现「直接 DATABASE_URL=... pytest」的第二条路。"""
    body = SCRIPT.read_text(encoding="utf-8")
    assert "pytest -m pg" in body
    # 不得在脚本里另起一条不经脚本的 pytest 调用路径（注释里说明允许）
    assert body.count("uv run pytest") == 2, (
        "脚本里应只有「收集计数」与「正式执行」两次 pytest 调用；"
        "多出来的说明有人加了第二条路径"
    )
```

- [ ] **Step 2: 跑测试确认红**

Run: `cd pcs-backend && uv run pytest tests/scripts/test_pytest_pg_gate.py -v`
Expected: FAIL —— `scripts/pytest_pg.sh` 不存在。

- [ ] **Step 3: 加 `pg` marker**

在 `pcs-backend/pyproject.toml` 的 `markers = [...]` 里追加：

```toml
    "pg: PG 专属用例（需真 PostgreSQL）。只能经 scripts/pytest_pg.sh 跑 —— 平时被 skipif 静默跳过。",
```

⚠️ `addopts = "-m 'not visual'"` 会被命令行后出现的 `-m` 覆盖 ⇒ `pytest -m pg` 选得到。

- [ ] **Step 4: 给 PG 用例打标记**

`tests/alembic/test_p9_013_bind_default_record_matrix.py` 的
`test_p9_013_runs_on_fresh_postgres_schema` 与
`test_p9_013_p9_012_downgrade_upgrade_roundtrip`，
`tests/alembic/test_p9_014_record_approval_chain_snapshot.py` 的两条 PG 测试，
各加一行 `@pytest.mark.pg`。

- [ ] **Step 5: 写 `scripts/pytest_pg.sh`**

```bash
#!/usr/bin/env bash
# 唯一的 PG 车道入口（TODO-099 · 委员会 2026-11-02 裁决 4）。
#
# ⚠️ **不得**在 README/CLAUDE.md 里教「也可以直接 DATABASE_URL=... pytest」——
#    那会重新引入「多条路径做同一件事」的分叉。
#
# 三条 fail-closed 约束（缺一条就等于没做）：
#   ① PG 实例没起 ⇒ FAIL（不是 skip）
#   ② 收集到 0 个 PG 测试 ⇒ FAIL（「收集到 0 个」不是「通过」）
#   ③ 测试被全 skip ⇒ FAIL（PG 起了但没真跑，与没起无法区分）
set -euo pipefail

cd "$(dirname "$0")/.."

PG_COMPOSE_PROJECT="${PG_COMPOSE_PROJECT:-pcs}"
PG_PYTEST_MARK="${PG_PYTEST_MARK:-pg}"
PG_DB_NAME="${PG_DB_NAME:-pcs_pgtest}"
PG_PORT="${PG_PORT:-5433}"

# ① PG 实例必须起着
if ! docker compose --profile pg ps --status running \
     | grep -q "postgres-pgtest"; then
  echo "FAIL: PG 测试实例未起 ⇒ docker compose --profile pg up -d" >&2
  exit 1
fi

# 口令**只在环境变量里**（不上命令行 —— 会被权限分类器拦，且进 shell 历史）
PG_USER="${POSTGRES_USER:-pcs}"
PG_PASS="${POSTGRES_PASSWORD:-pcs_dev}"
export DATABASE_URL="postgresql+psycopg://${PG_USER}:${PG_PASS}@localhost:${PG_PORT}/${PG_DB_NAME}"
export TEST_DATABASE_URL="$DATABASE_URL"

# ② 收集到的 PG 测试数必须 > 0
collected="$(uv run pytest -m "$PG_PYTEST_MARK" --collect-only -q 2>/dev/null \
  | grep -oE '[0-9]+ tests? collected' | grep -oE '[0-9]+' | head -1 || true)"
if [ "${collected:-0}" -eq 0 ]; then
  echo "FAIL: 收集到 0 个 PG 测试（标记缺失 / 全部 skip）" >&2
  exit 1
fi

# ③ 正式执行；输出里必须有「至少 1 passed」
out="$(uv run pytest -m "$PG_PYTEST_MARK" -q 2>&1)" || { echo "$out"; exit 1; }
echo "$out"
if ! echo "$out" | grep -qE '[1-9][0-9]* passed'; then
  echo "FAIL: PG 车道没有实际执行任何测试（全部 skip？）" >&2
  exit 1
fi
```

`chmod +x pcs-backend/scripts/pytest_pg.sh`

- [ ] **Step 6: 加 docker-compose 的 `pg` profile（独立实例 + 独立库）**

```yaml
  postgres-pgtest:
    # ⚠️ **独立实例**（不是复用开发库那个 postgres）：PG 车道跑的是
    # 迁移 / 降级环 / 并发用例 ⇒ 绝不能污染开发数据（CLAUDE.md「漂移盲区」）。
    # 独立 database（pcs_pgtest）防「开发时 alembic upgrade head 误把
    # 测试数据升了」。裁决 4 修正 2 明确要求独立实例 + 独立 database。
    profiles: ["pg"]
    image: postgres:18-alpine
    environment:
      POSTGRES_USER: ${POSTGRES_USER:-pcs}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-pcs_dev}
      POSTGRES_DB: pcs_pgtest
    ports: ["5433:5432"]
    volumes: [pgtestdata:/var/lib/postgresql/data]
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U pcs -d pcs_pgtest"]
      interval: 5s
      timeout: 3s
      retries: 10
```

并在 `volumes:` 段加 `pgtestdata:`。

- [ ] **Step 7: 跑脚本测试确认绿**

Run: `cd pcs-backend && uv run pytest tests/scripts/test_pytest_pg_gate.py -v`
Expected: PASS（4 例）。

- [ ] **Step 8: 真跑一次 PG 车道**

```bash
cd /home/pangzy/code_project/PCS && docker compose --profile pg up -d
cd pcs-backend && bash scripts/pytest_pg.sh
```
Expected: 退出 0，输出含 `4 passed`（p9_013 两条 + p9_014 两条）。
⚠️ 若 PG 刚起还没 ready，先 `docker compose --profile pg ps` 确认 healthcheck 通过。

- [ ] **Step 9: 修两条 false delegation docstring（裁决 4 约束 2）**

`tests/alembic/test_p9_013_bind_default_record_matrix.py` 与
`tests/alembic/test_p9_014_record_approval_chain_snapshot.py` 里凡出现
「CI 的 api-drift job 承担同口径验证」/「CI 覆盖不到本文件」的句子，一律改成：

> 引擎级验证**必须**在发布前经 `scripts/pytest_pg.sh` 手动跑（唯一入口）。
> CI **不**跑 pytest —— `check-api-drift` job 只跑 `alembic upgrade head` 与
> OpenAPI 导出；见 `CLAUDE.md` §「发布前检查（必做）」。

- [ ] **Step 10: CLAUDE.md 加「发布前检查（必做）」清单**

在 `CLAUDE.md` 的「测试前检查」一节末尾追加：

```markdown
## 发布前检查（必做）

- [ ] `alembic check` 在两库（pcs / pcs_test）各 exit 0 —— ⚠️ 必须**独立进程**跑，
      见 cerebrum「alembic settings 缓存」；且**直查库**确认 revision 与目标列
- [ ] `scripts/pytest_pg.sh` exit 0 —— 覆盖 `tests/alembic/` 的引擎级用例与并发类用例
- [ ] `check_openapi_payload_coverage.py` RC 0（裸字段 ≤ 基线）
- [ ] `check_migration_idempotency.py` RC 0
- [ ] 前后端全量测试绿

⚠️ 第 1 条验「迁移与 ORM 一致」，第 2 条验「迁移在**真实 PG** 上跑得通 + 并发语义正确」
⇒ 两者**不互相替代** ⇒ 「只跑 alembic check」不算发布前检查通过。
```

- [ ] **Step 11: 登记复审触发（裁决 4）**

在 `TODOS.md` 的 TODO-099 条目里追加：

```markdown
⚠️ **复审触发（2026-11-02 委员会）**：若未来 **2–3 个发布周期内**出现至少一次
「PG-specific bug 因为没跑 `scripts/pytest_pg.sh` 而在发布后暴露」⇒
2026-08-29 的「CI/CD 流水线不做」裁决**必须被重新提出**（不是被绕过），
依据是「自己记得跑」这个前提被证伪 N 次。
```

- [ ] **Step 12: Commit**

```bash
git add docker-compose.yml pcs-backend/pyproject.toml pcs-backend/scripts/pytest_pg.sh \
        pcs-backend/tests/scripts/test_pytest_pg_gate.py \
        pcs-backend/tests/alembic/ CLAUDE.md TODOS.md
git commit -F <消息文件>
```
消息首行：`feat(P9B-3): 本地 PG 车道（TODO-099）—— 独立实例 + fail-closed 唯一入口`

---

## Task T1：债项三条（TODO-101 / 102 / 103）

**Files:**
- Modify: `pcs-frontend/src/components/common/StateBadge.tsx`
- Test: `pcs-frontend/tests/components/common/StateBadge.test.tsx`（新增）
- Modify: `pcs-backend/app/api/v1/projects.py`
- Test: `pcs-backend/tests/api/v1/test_projects_api.py`（既有文件，加用例）
- Create: `pcs-backend/scripts/gen_compact_orm.py`
- Modify: `pcs-backend/docs/schema_compact_orm.md`（生成物）

**Interfaces:**
- Consumes: `DeliverableSignStatus`（4 态，契约派生）；`projects.project_no` 唯一约束。
- Produces: `scripts/gen_compact_orm.py`（可重跑，把 compact ORM 表变成**派生**产物）。

- [ ] **Step 1: TODO-101 —— StateBadge 交付物强调集（先红）**

`StateBadge.tsx` 的 `MODULE_ACTIVATED.DELIVERABLE` 现在装的是**记录侧 9 态**
⇒ 交付物自己的 `PENDING` / `APPROVED` 不在集合里 ⇒ 渲染成 opacity 0.4
（看起来像「过期」）。改成交付物 4 态：

```ts
  DELIVERABLE: new Set<DeliverableSignStatus>([
    'DRAFT', 'PENDING', 'APPROVED', 'OBSOLETE',
  ]),
```

（`MODULE_ACTIVATED` 的类型是 `Record<StateBadgeModule, ReadonlySet<AnyKnownStatus>>`，
⇒ 需要把 `AnyKnownStatus` 扩成 `RecordSignStatus | DeliverableSignStatus`，
或把该表的类型放宽到 `ReadonlySet<string>`。）

测试（新增文件 `pcs-frontend/tests/components/common/StateBadge.test.tsx`）：

```tsx
it('交付物的 PENDING / APPROVED **不半透明**（TODO-101）', () => {
  const { container } = render(<StateBadge module="DELIVERABLE" status="PENDING" />);
  const badge = container.querySelector('[data-testid=state-badge]') as HTMLElement;
  expect(badge.style.opacity).toBe('1');   // 此前是 0.4
});
```

- [ ] **Step 2: 跑测试确认红 → 改实现 → 跑绿**

Run: `cd pcs-frontend && npx vitest run tests/components/common/StateBadge.test.tsx`
Expected: 先 FAIL（opacity 0.4）⇒ 改实现 ⇒ PASS。

- [ ] **Step 3: TODO-102 —— IntegrityError 只在命中 project_no 时映射 409（先红）**

`projects.py` 现在把**任何** `IntegrityError` 报成 409「项目编号已存在」⇒
NOT NULL / FK / CHECK 违约也会被说成「编号重复」⇒ 用户照提示换编号，换了还是错。

改成只在该约束命中时映射 409，其余重新抛出：

```python
    try:
        await db.flush()
    except IntegrityError as e:
        # ⚠️ **只有** `project_no` 唯一约束冲突才是 409（TODO-102）；
        #    其它约束违约（NOT NULL / FK / CHECK）重新抛 ⇒ 500 + 服务端留详情，
        #    不把「另一种错」说成「编号重复」。
        if "project_no" not in str(getattr(e, "orig", e)):
            raise
        await db.rollback()
        raise PcsError(
            code="PROJECT_NO_CONFLICT",
            message=f"项目编号 {payload.project_no} 已存在（全局唯一），请换一个",
            status=409,
        ) from e
```

测试（加到 `tests/api/v1/test_projects_api.py`）：构造一条**别的**约束违约
（例如 `project_name=None` 触发 NOT NULL）⇒ 期望 **500 / 未被映射成 409**。

- [ ] **Step 4: TODO-103 —— compact ORM 表改成派生**

新建 `pcs-backend/scripts/gen_compact_orm.py`：从 `SA_Base.metadata` 导出
`docs/schema_compact_orm.md`，格式沿用现有的 `列|类型!` 风格（`!` = NOT NULL，
`CHARPK` / `CHARFK` / `jsonb` / `dt` 等类型映射照现有文件）。

⚠️ 现有文件是 **2026-09-02 的 53 表快照**（ORM 现有 107 张）⇒ 生成器一次会
把它变成 **107 表** ⇒ diff 很大但**正确**（TODO-103 的目的就是让文件不再过期）。
生成器的头部必须写：

```markdown
> 生成时间：<ISO 日期> | 来源：app/models/*.py（**生成物，勿手改**）
> 重新生成：`cd pcs-backend && uv run python scripts/gen_compact_orm.py`
```

- [ ] **Step 5: 跑生成器 + 断言它包含新列**

```bash
cd pcs-backend && uv run python scripts/gen_compact_orm.py
grep -c "approval_chain_snapshot|jsonb" docs/schema_compact_orm.md   # 应为 20
```

- [ ] **Step 6: Commit**

```bash
git add pcs-frontend/src/components/common/StateBadge.tsx \
        pcs-frontend/tests/components/common/StateBadge.test.tsx \
        pcs-backend/app/api/v1/projects.py pcs-backend/tests/api/v1/test_projects_api.py \
        pcs-backend/scripts/gen_compact_orm.py pcs-backend/docs/schema_compact_orm.md
git commit -F <消息文件>
```
首行：`fix(P9B-3): 债项三条 —— StateBadge 交付物词表 / 409 映射收窄 / compact ORM 改派生`

---

## Task T2：SPEC V2.6 修订 + TODO 登记

**Files:**
- Modify: `docs/PCS-UI-SPEC.md`（§7.7.1 / §7.7.2 / §7.7.3 / §7.20 / §7.21 / §12.4）
- Modify: `TODOS.md`

**Interfaces:**
- Consumes: 委员会裁决 2 / 3；P9B-2F 的 SPEC V2.5（`docs/PCS-UI-SPEC.md` §12.4 最后一行）。
- Produces: **前端实现的唯一依据**（CLAUDE.md）—— T4~T8 的字段与错误码口径全部落在这里。

- [ ] **Step 1: §7.20 增「7.20.1 系统参数」小节**

字段（后端 T4 按此实现）：

```text
系统参数（/admin/system-settings · SYSTEM_ADMIN）

- 键值表（后端 system_settings）：setting_key（≤100 字符，主键）/
  setting_value_json（JSONB）/ description / updated_at
- **批量保存**：一次 PUT 提交全部改动 ⇒ 事务内**全改或全不改**
  （硬约束：不做「每个键一个 PATCH」—— 那会让保存变成 N 个请求且中途失败留半改状态）
- 审计：每次写入一条 audit_logs（action=SYSTEM_SETTINGS_UPDATED，detail 含变更前后的键集合）
- 错误码：403 HTTP_403（无 SYSTEM_ADMIN）/ 404 SYSTEM_SETTING_NOT_FOUND（改不存在的键时）
```

- [ ] **Step 2: §7.20 清单里标注 AI 开关 / Prompt 模板为 P10 前不做**

在 §7.20 的「AI 开关」「Prompt 模板」两行后加注：

```text
⚠️ AI 开关 / Prompt 模板 **P10 前不做**（2026-11-02 委员会裁决）：
   §7.21 明写「AI 助手 P10 前禁用」⇒ 这两个配置**当前没有任何下游消费者**
   ⇒ 现在做等于写无消费者的配置（ADR-0049 §① 同族）⇒ 随 AI 助手本体同批交付（P10）。
```

- [ ] **Step 3: §7.21 补一句归属**

在 §7.21 末尾「P10 前禁用，Tooltip『AI 功能未启用』。」之后追加：

```text
⚠️ **AI 开关与 Prompt 模板随本节同批交付**（P10）—— P9B-3 明确不做
   （无消费者 ⇒ 空壳；且未来的参数化 / 版本 / A-B / 模型绑定形态未知，
   现在做要全部推翻）。
```

- [ ] **Step 4: §7.7.1 / §7.7.2 / §7.7.3 补齐口径**

- §7.7.1：工具栏「提交校对」**本批为单条**（行操作用）；列表级批量见 P9B-3b；
  筛选新增「工况 / 相态 / 状态 / 来源」四项；「引用 📎×N」的口径见「尚未解决的问题」第 1 条。
- §7.7.2：7 个 Tab 的清单与「校核记录」的数据来源（`GET /audit-logs?resource_type=streams&resource_id=…`）。
- §7.7.3：明确「手工」分支 = **本批的手动创建向导**（T7）；Excel 列映射 / 模板库不在本批。

- [ ] **Step 5: §12.4 加 V2.6 行 + 文件头版本号升到 V2.6**

- [ ] **Step 6: TODOS.md 登记**

- TODO-092 追加：「**角色来源权威性升格独立 ADR**」（不是计划里能拍的）；并写明
  「**AD 同步覆盖 `users.roles` 是当前行为**」（本批不做 ⇒ 行为不变，但必须留档）；
- 新增一条 TODO 指向「角色分配 ADR」的立项（编号接 104）；
- TODO-100 追加触发条件：「下一轮 ce-code-review 的 scope 须含
  `test_deliverable_issue.py` + deliveries / record_edits API 改动 + 该批 diff 其余部分」。

- [ ] **Step 7: Commit**

```bash
git add docs/PCS-UI-SPEC.md TODOS.md
git commit -F <消息文件>
```
首行：`docs(P9B-3): SPEC V2.6 —— §7.20.1 系统参数 + §7.7 物流三节口径 + AI/Prompt 移出 P9B-3`

---

## Task T3：物流组成合计校验（后端门禁）

**Files:**
- Modify: `pcs-backend/app/api/v1/streams.py`（submit 前校验）
- Modify: `pcs-backend/app/models/enums.py`（新错误码进 `PcsError` 的 code 字符串即可，无需枚举）
- Test: `pcs-backend/tests/api/v1/test_stream_composition_sum.py`（新建）

**Interfaces:**
- Consumes: `Stream.composition_json`（JSONB，NOT NULL）；SPEC §7.7.2「底部合计校验（100±0.5%）」。
- Produces: 错误码 `SIM_STREAM_COMPOSITION_OUT_OF_RANGE`（422）。

- [ ] **Step 1: 写失败测试**

```python
# pcs-backend/tests/api/v1/test_stream_composition_sum.py
"""物流组成合计校验（SPEC §7.7.2「底部合计校验（100±0.5%）」）。

## 为什么这是**新增**而不是复用

⚠️ 实测（2026-11-02）：全仓 `grep -rn "COMPOSITION"` = 0 命中 ⇒
「组成合计」这条校验**根本不存在** ⇒ 委员会 brief 里假设的失败原因
`COMPOSITION_SUM_OUT_OF_RANGE` 需要**新建**（不是复用既有的）。

## 为什么校验挂在**送审**上

物流的组成不合法却进了校对 ⇒ 校对人在 Tab「组成」里看到合计 98.7%
却已经被要求签字 ⇒ 门禁必须**前置**（SPEC §5.1「门禁前置」）⇒ 挂在
`POST /streams/{id}/submit`（DRAFT → IN_APPROVAL）之前。
"""
```

断言两条：
1. 组成摩尔分率合计 = 0.987 ⇒ submit ⇒ **422** `SIM_STREAM_COMPOSITION_OUT_OF_RANGE`，
   且 `sign_status` **不变**（仍 DRAFT）；
2. 合计 = 1.0 ⇒ submit ⇒ **200**（或至少不是该错误码）。

- [ ] **Step 2: 跑测试确认红**

Run: `cd pcs-backend && uv run pytest tests/api/v1/test_stream_composition_sum.py -v`
Expected: FAIL（现在放行）。

- [ ] **Step 3: 实现校验**

在 `streams.py` 的 `submit_stream` 里，进入 `_transition_endpoint` **之前**：

```python
    # ⚠️ 组成合计门禁（SPEC §7.7.2「100±0.5%」）—— 送审**前**校验，
    #    不合法不放进校对（门禁前置，SPEC §5.1）。
    total = _composition_mole_fraction_total(stream)
    if total is not None and abs(total - 100.0) > 0.5:
        raise PcsError(
            code="SIM_STREAM_COMPOSITION_OUT_OF_RANGE",
            message=(
                f"物流 {stream_id} 的组成摩尔分率合计 {total:.2f}%，"
                "不在 100±0.5% 内 ⇒ 不能提交校对"
            ),
            status=422,
        )
```

`_composition_mole_fraction_total` 的口径（**已按实测钉死**，不再是待裁决项）：

- `composition_json` 是 **`{CAS 号: 摩尔分率}` 字典**（`app/schemas/stream.py:331`
  「总组成 CAS→摩尔分率」；`flash_persist._extract_composition` 取 `comp[c]` 当
  `zs` 喂给闪蒸计算器 ⇒ **值域 0~1 的小数**，不是百分数）；
- 合计 = `sum(float(v) for v in composition_json.values())`；
- 判定 `abs(total - 1.0) > 0.005`（≡ SPEC §7.7.2 的「100±0.5%」）；
- 错误消息里**同时给百分比**：`合计 {total * 100:.2f}%`；
- `composition_json` 为空 ⇒ **跳过校验**（不拦 —— 没有组成就没有可校验的组成；
  `flash_persist` 对空组成是单独抛错的，不在本门禁范围）。

- [ ] **Step 4: 跑测试确认绿 + 跑既有 streams 套件防回归**

Run: `cd pcs-backend && uv run pytest tests/api/v1/ -k stream -q`
Expected: PASS。

- [ ] **Step 5: Commit**

```bash
git add pcs-backend/app/api/v1/streams.py pcs-backend/tests/api/v1/test_stream_composition_sum.py
git commit -F <消息文件>
```
首行：`feat(P9B-3): 物流组成合计门禁（送审前置，100±0.5%）`

---

## Task T4：系统参数后端（service + router + 批量原子写）

**Files:**
- Create: `pcs-backend/app/schemas/system_settings.py`
- Create: `pcs-backend/app/services/system_setting_service.py`
- Create: `pcs-backend/app/api/v1/system_settings.py`
- Modify: `pcs-backend/app/models/enums.py`（`AuditAction` 加 `SYSTEM_SETTINGS_UPDATED`）
- Modify: `pcs-backend/app/api/v1/__init__.py`（挂 router）
- Modify: `pcs-backend/docs/openapi.json`（契约重滚，生成物）
- Test: `pcs-backend/tests/api/v1/test_system_settings.py`

**Interfaces:**
- Consumes: `app.models.system.SystemSetting`（已存在）；`AuditService.write`。
- Produces:
  - `GET /api/v1/system-settings` ⇒ `list[SystemSettingOut]`
  - `PUT /api/v1/system-settings` ⇒ `SystemSettingBatchOut`
  - `SystemSettingOut = {setting_key: str, setting_value_json: Any, description: str | None, updated_at: datetime}`
  - `SystemSettingBatchIn = {settings: dict[str, Any]}`
  - `SystemSettingBatchOut = {updated: list[SystemSettingOut]}`
  - 错误码：`HTTP_403`（非 SYSTEM_ADMIN）/ `SYSTEM_SETTING_NOT_FOUND`（404，改不存在的键）

- [ ] **Step 1: 写失败测试**

```python
# pcs-backend/tests/api/v1/test_system_settings.py
"""系统参数 CRUD（§7.20.1 · P9B-3 · T4）。

## 硬约束：批量 + **原子**

委员会 2026-11-02 裁决「硬约束 1」：系统参数页一次改多个参数 ⇒
**一次 PUT**（body 是 `{key: value}` 的 map）⇒ 事务内**要么全改、要么全不改**。
⚠️ 不做「每个键一个 PATCH」—— 那会让「保存」变成 N 个请求且中途失败留半改状态。
⇒ 本文件的核心断言就是**原子性**：一个键非法 ⇒ **一个键都不改**。
"""
```

断言三条：
1. `GET /system-settings`（SYSTEM_ADMIN）⇒ 200 + 列表；非 SYSTEM_ADMIN ⇒ 403。
2. `PUT` 两个键都合法 ⇒ 200 + 两个键都变了 + **一条** `SYSTEM_SETTINGS_UPDATED` 审计。
3. ⚠️ **原子性**：`PUT` 里塞一个**不存在的键** ⇒ 404 `SYSTEM_SETTING_NOT_FOUND`
   ⇒ 且**另一个合法键的值没变**（直查 DB 断言）。

- [ ] **Step 2: 跑测试确认红**（404 —— 端点不存在）

- [ ] **Step 3: 写 schema**

```python
# pcs-backend/app/schemas/system_settings.py
"""系统参数（§7.20.1）。

⚠️ `system_settings` 是**已存在的表**（`app/models/system.py`），此前**零 API**
⇒ 本文件是它的**第一个**对外形状 ⇒ 「表存在」≠「API 存在」（核实 4）。
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class SystemSettingOut(BaseModel):
    """一条系统参数。"""

    model_config = ConfigDict(from_attributes=True)

    setting_key: str
    setting_value_json: Any
    description: str | None = None
    updated_at: datetime


class SystemSettingBatchIn(BaseModel):
    """批量保存的请求体 —— **一次 PUT 提交全部改动**（硬约束 1）。"""

    settings: dict[str, Any] = Field(description="setting_key → 新值；整批原子提交")


class SystemSettingBatchOut(BaseModel):
    """批量保存的结果。"""

    updated: list[SystemSettingOut]
```

- [ ] **Step 4: 写 service（原子写）**

```python
# pcs-backend/app/services/system_setting_service.py
"""系统参数读写（§7.20.1 · T4）。

⚠️ **原子性**（委员会硬约束 1）：批量保存是**一次事务** ⇒ 任一键失败 ⇒
**全部不落** ⇒ 不留「半改」状态。实现上：先校验全部键存在，再一次性写。
"""
```

`list_all(db) -> list[SystemSetting]` 与
`update_batch(db, values: dict[str, Any], *, actor_user_id) -> list[SystemSetting]`：

- 先 `SELECT ... WHERE setting_key IN (...)` 取全部目标行；
- **缺任何一个键 ⇒ 抛 `PcsError(code="SYSTEM_SETTING_NOT_FOUND", status=404)`**
  （**在任何写入之前** ⇒ 天然原子）；
- 全部命中 ⇒ 逐个赋值 + **一次** `db.flush()` + **一次** `AuditService.write`
  （`action=AuditAction.SYSTEM_SETTINGS_UPDATED`，`detail={"keys": [...], "before": {...}}`）。

- [ ] **Step 5: 写 router**

```python
# pcs-backend/app/api/v1/system_settings.py
"""系统参数端点（§7.20.1）。

⚠️ **批量 + 原子**：`PUT /system-settings` 一次提交全部改动，事务内全改或全不改。
"""
```

- `GET ""` ⇒ `require_roles(user, "SYSTEM_ADMIN")` ⇒ `list_all`
- `PUT ""` ⇒ 同上 ⇒ `update_batch` ⇒ 提交 ⇒ 返回 `SystemSettingBatchOut`

⚠️ `AuditAction` 枚举**要加** `SYSTEM_SETTINGS_UPDATED = "SYSTEM_SETTINGS_UPDATED"`
（`app/models/enums.py`，与 `CONFIG_*` 一族同处）。

- [ ] **Step 6: 挂 router**（`app/api/v1/__init__.py`，与其它 router 同款）

- [ ] **Step 7: 跑测试确认绿 + 重滚契约**

```bash
cd pcs-backend && uv run pytest tests/api/v1/test_system_settings.py -v
cd /home/pangzy/code_project/PCS && bash pcs-backend/scripts/gate_08_openapi_contract.sh
```
Expected: 3 passed；契约重滚无漂移。

- [ ] **Step 8: Commit**

```bash
git add pcs-backend/app/schemas/system_settings.py pcs-backend/app/services/system_setting_service.py \
        pcs-backend/app/api/v1/system_settings.py pcs-backend/app/api/v1/__init__.py \
        pcs-backend/app/models/enums.py pcs-backend/docs/openapi.json \
        pcs-backend/tests/api/v1/test_system_settings.py
git commit -F <消息文件>
```
首行：`feat(P9B-3): 系统参数后端（批量原子 PUT + 审计）`

---

## Task T5：系统参数前端页

**Files:**
- Create: `pcs-frontend/src/api/systemSettings.ts`
- Create: `pcs-frontend/src/pages/admin/SystemSettingsPage.tsx`
- Modify: `pcs-frontend/src/App.tsx`（路由 + 菜单）
- Modify: `pcs-frontend/src/types/api.d.ts`（生成物）
- Test: `pcs-frontend/tests/pages/admin/systemSettings.test.tsx`

**Interfaces:**
- Consumes: T4 的 `GET/PUT /api/v1/system-settings`（契约类型
  `components['schemas']['SystemSettingOut']` / `SystemSettingBatchOut`）。
- Produces: 路由 `/admin/system-settings`；`systemSettingsApi.list()` / `.save(values)`。

- [ ] **Step 1: 写失败测试**（vitest + MSW）

```tsx
/**
 * 系统参数页（§7.20.1 · P9B-3 · T5）。
 *
 * ⚠️ **一次保存 = 一个 PUT**（硬约束 1）—— 测试要钉住「保存只发一个请求」，
 * 否则前端改成逐键 PATCH 时测试不会红，而那正是委员会禁止的形状。
 */
```

断言三条：
1. 页面渲染出参数行（键 + 值），值取自 mock；
2. ⚠️ 改两个参数后点「保存」⇒ **只发一个** `PUT /system-settings`，
   body 的 `settings` 含两个键；
3. PUT 失败（500）⇒ 页面显示错误，**不**显示「已保存」。

- [ ] **Step 2: 跑测试确认红**（页面不存在）

- [ ] **Step 3: 写 api 客户端**

```ts
// pcs-frontend/src/api/systemSettings.ts
/**
 * 系统参数客户端（§7.20.1 · P9B-3）。
 *
 * ⚠️ 类型**契约派生**（`components['schemas'][...]`）—— 不手写 union
 * （手写 = 与后端脱钩 = bug-2040 那类漂移根因）。
 *
 * ⚠️ `save()` **一次 PUT 提交全部改动**（委员会硬约束 1）—— 不做逐键 PATCH。
 */
import { api } from './client';
import type { components } from '../types/api';

export type SystemSettingOut = components['schemas']['SystemSettingOut'];
export type SystemSettingBatchOut = components['schemas']['SystemSettingBatchOut'];

export const systemSettingsApi = {
  list: (): Promise<SystemSettingOut[]> =>
    api.get<SystemSettingOut[]>('/system-settings').then((r) => r.data),

  save: (settings: Record<string, unknown>): Promise<SystemSettingBatchOut> =>
    api
      .put<SystemSettingBatchOut>('/system-settings', { settings })
      .then((r) => r.data),
};
```

- [ ] **Step 4: 写页面**

`src/pages/admin/SystemSettingsPage.tsx`：从 `systemSettingsApi.list()` 拉列表 ⇒
渲染成表单（每行一个键 + 一个 JSON 值输入）⇒ 「保存」按钮**一次**调
`systemSettingsApi.save(changed)` ⇒ 成功提示 / 失败提示。

⚠️ 值是 JSONB ⇒ 输入框给 **JSON 文本**，保存前 `JSON.parse` ⇒ 解析失败就**就地报错**
（不发请求）—— 解析失败不是后端的错。

- [ ] **Step 5: 挂路由 + 菜单**（`src/App.tsx`，与 `/admin/users` 同款）

⚠️ 菜单项仅 **SYSTEM_ADMIN** 可见（与 `/admin/users` / `/admin/projects` 同口径）。

- [ ] **Step 6: 跑测试 + typecheck + lint**

```bash
cd pcs-frontend && npx vitest run tests/pages/admin/systemSettings.test.tsx && npm run typecheck && npm run lint
```
Expected: PASS / clean / clean。

- [ ] **Step 7: Commit**

```bash
git add pcs-frontend/src/api/systemSettings.ts pcs-frontend/src/pages/admin/SystemSettingsPage.tsx \
        pcs-frontend/src/App.tsx pcs-frontend/src/types/api.d.ts \
        pcs-frontend/tests/pages/admin/systemSettings.test.tsx
git commit -F <消息文件>
```
首行：`feat(P9B-3): 系统参数页（一次保存 = 一个 PUT）`

---

## Task T6：SIM 物流列表页（工具栏 / 筛选 / 引用列 / 行操作）

**Files:**
- Modify: `pcs-frontend/src/api/stream.ts`（契约派生类型 + 端点封装）
- Modify: `pcs-frontend/src/pages/sim/StreamListPage.tsx`（重写）
- Test: `pcs-frontend/tests/pages/sim/streamList.test.tsx`（新建）

**Interfaces:**
- Consumes: `GET /api/v1/projects/{project_id}/streams`（既有）；`POST /streams/{id}/submit`（既有，T6 用它做**单条**提交校对）。
- Produces: `streamApi.list(projectId)`（**契约派生**类型）、`streamApi.submitForReview(id)`。

- [ ] **Step 1: 写失败测试**

断言四条：
1. 工具栏出现 **导入 / 新建物流 / 导出** 三个按钮（**没有**「批量提交校对」——
   批量在 P9B-3b，SPEC §7.7.1 的工具栏批量口径由 T2 登记）；
2. 筛选有 **工况 / 相态 / 状态 / 来源** 四项，且改了筛选会重新请求（带 query 参数）；
3. 行操作有 **查看 / 校对 / 变更** 三个入口；
4. ⚠️ 点行「校对」⇒ 调 `POST /streams/{id}/submit` ⇒ 成功后该行状态徽章变
   `IN_APPROVAL`；失败（403）⇒ 显示错误**且状态不变**；
5. ⚠️ **未知 `sign_status`**（mock 返回 `"SOMETHING_NEW"`）⇒ 列表**照常渲染**
   （StateBadge 的未知态兜底），不是整页崩（Review Focus 第 2 条）。

- [ ] **Step 2: 跑测试确认红**

- [ ] **Step 3: api 客户端改成契约派生**

```ts
// pcs-frontend/src/api/stream.ts（重写）
/**
 * SIM 物流 API 客户端（P9B-3 · T6/T7/T8 扩展）。
 *
 * ⚠️ 类型**契约派生** —— 此前是手写的 `StreamListItem`（5 字段）⇒ 与契约脱钩
 * （backend `StreamListItem` 实际有几十个字段）⇒ 后端加字段前端静默丢。
 * ⇒ 本批改成 `components['schemas'][...]`，并新增 submit / properties /
 * state-points 三个端点封装。
 */
```

⚠️ **列表响应是否带 `reference_count`**（SPEC §7.7.1「引用 📎×N」）——
后端**当前不返回**该字段 ⇒ 见「尚未解决的问题」第 1 条。
⇒ **本批先不渲染引用列**，等口径定下再补（T2 已登记）。

⚠️ **`listByProject` 这个名字必须保留** —— `VesselComputePage.tsx:127` 在用它
（OPEN-4-1：没注入 streams 时走 `streamApi.listByProject` 自取）⇒ 改名会破坏
那个页面。本批只把它**返回类型**换成契约派生，**不动名字**。

⚠️ **「来源」列与「来源」筛选本批不做** —— 实测 `streams` 表**没有「来源」字段**
（`data_mode` 是「数据模式」CHEMICAL / PETROLEUM / SOLID，**不是** SPEC §7.7.1 的
「SIM导入 / 手动 / Excel / 化验」）⇒ 无数据源可显示、可筛 ⇒ 硬画一列等于造假
⇒ 登记为 SPEC ↔ 实现分叉（T2）+ 后端债（未解决问题第 3 条）。

- [ ] **Step 4: 重写 StreamListPage**

列（SPEC §7.7.1）：物流号（等宽）· 名称 · 工况 · 相态 · 温度 · 压力 ·
质量流量 · 状态（StateBadge）· 来源 · 操作。
筛选：工况 / 相态 / 状态 / 来源（来源是**自由文本** ⇒ 用 Select 的枚举，
取值待与后端 `streams` 的来源口径对齐，见未解决问题第 3 条）。
工具栏：导入 / 新建物流 / 导出。

⚠️ 「新建物流」⇒ 跳 **T7** 的手动创建向导（路由 `/sim/streams/new`）。

- [ ] **Step 5: 跑测试 + typecheck + lint**

- [ ] **Step 6: Commit**

```bash
git add pcs-frontend/src/api/stream.ts pcs-frontend/src/pages/sim/StreamListPage.tsx \
        pcs-frontend/tests/pages/sim/streamList.test.tsx
git commit -F <消息文件>
```
首行：`feat(P9B-3): 物流列表页 —— 工具栏 / 四项筛选 / 单条提交校对`

---

## Task T7：物流手动创建向导

**Files:**
- Create: `pcs-frontend/src/pages/sim/StreamManualWizardPage.tsx`
- Modify: `pcs-frontend/src/App.tsx`（路由 `/sim/streams/new`）
- Modify: `pcs-frontend/src/api/stream.ts`（`create` / `validate` 封装）
- Test: `pcs-frontend/tests/pages/sim/streamManualWizard.test.tsx`（新建）

**Interfaces:**
- Consumes: `POST /api/v1/streams`（既有，`StreamCreate`）· `POST /streams/validate`（既有）。
- Produces: 路由 `/sim/streams/new`；向导写完跳回列表。

- [ ] **Step 1: 写失败测试**

断言四条：
1. 向导是 **多步**（不是一行表单）：基本信息 → 组成 → 物性 → 状态点 → 校验 → 写入 → 提交；
2. 「校验」步调 `POST /streams/validate` ⇒ 通过项绿 / 警告项黄 / 错误项红
   （SPEC §7.7.3「校验结果」）；
3. ⚠️ **校验有红项 ⇒ 「写入 DRAFT」按钮禁用**（阻断项必须处理，SPEC §7.7.3）；
4. 「写入 DRAFT」⇒ `POST /streams` ⇒ 成功 ⇒ 跳回列表；失败 ⇒ 显示错误。

- [ ] **Step 2: 跑测试确认红**

- [ ] **Step 3: 写向导页**

⚠️ **不**塞进 `ImportWizardPage`（那是**导入**专用，105 行；混进去会让它超 800 行
上限，且「导入」与「新建」是两种心智）⇒ 新建独立页 `StreamManualWizardPage.tsx`。

步骤与字段（SPEC §7.7.3 的「手工」分支裁剪版 —— 手工没有「上传文件」也没有
「Excel 列映射」）：

| 步 | 内容 | 后端 |
|---|---|---|
| 1 基本信息 | 物流号 / 名称 / 描述 / 相态 / 工况 / 来源 / 项目 / 工作区 | `StreamCreate` 必填字段 |
| 2 组成 | 组分名 / 分子式 / 摩尔分率 / 质量分率 / 体积分率 + **底部合计校验（100±0.5%）** | `composition_json` |
| 3 物性 | 温压 + 估算触发 | `POST /streams/{id}/properties/estimate`（写入后才有 id ⇒ 该步放在「写入」之后或先建后补 ⇒ 见未解决问题第 4 条） |
| 4 状态点 | 标签 / 类型 / 温压 / 相态 / 汽化分率 | `state_points` |
| 5 校验 | 绿 / 黄 / 红 三色结果 | `POST /streams/validate` |
| 6 写入 DRAFT | 调 `POST /streams` ⇒ 得 `stream_id` | — |
| 7 提交校对 | 调 `POST /streams/{id}/submit` ⇒ DRAFT → IN_APPROVAL | — |

⚠️ 步骤 3 与 6 的**顺序矛盾**（估算要先有 stream_id）⇒ 见未解决问题第 4 条。

- [ ] **Step 4: 跑测试 + typecheck + lint**

- [ ] **Step 5: Commit**

```bash
git add pcs-frontend/src/pages/sim/StreamManualWizardPage.tsx pcs-frontend/src/App.tsx \
        pcs-frontend/src/api/stream.ts pcs-frontend/tests/pages/sim/streamManualWizard.test.tsx
git commit -F <消息文件>
```
首行：`feat(P9B-3): 物流手动创建向导（7 步 · 校验阻断 + 写入 DRAFT + 提交校对）`

---

## Task T8：物流详情页 7 Tab + 校核记录

**Files:**
- Modify: `pcs-frontend/src/pages/sim/StreamDetailPage.tsx`（改成 Tab 宿主）
- Create: `pcs-frontend/src/pages/sim/tabs/StreamBasicTab.tsx`
- Create: `pcs-frontend/src/pages/sim/tabs/StreamCompositionTab.tsx`
- Create: `pcs-frontend/src/pages/sim/tabs/StreamPropertiesTab.tsx`
- Create: `pcs-frontend/src/pages/sim/tabs/StreamStatePointsTab.tsx`
- Create: `pcs-frontend/src/pages/sim/tabs/StreamConnectionsTab.tsx`
- Create: `pcs-frontend/src/pages/sim/tabs/StreamLineageTab.tsx`
- Create: `pcs-frontend/src/pages/sim/tabs/StreamReviewLogTab.tsx`
- Modify: `pcs-frontend/src/api/stream.ts`（properties / state-points / lineage / audit 封装）
- Test: `pcs-frontend/tests/pages/sim/streamDetailTabs.test.tsx`（新建）

**Interfaces:**
- Consumes（**全部已存在**，本 task 不需要新后端端点）：
  - `GET /streams/{id}/properties` · `GET /streams/{id}/state-points`
  - `GET /lineage/{record_type}/{record_id}/graph`（`record_type` = `streams`）
  - `GET /audit-logs?resource_type=streams&resource_id={id}&action=RECORD_TRANSITION`
- Produces: 7 个 Tab 组件（各 ≤ 150 行）。

- [ ] **Step 1: 写失败测试**

断言三条：
1. 7 个 Tab **都在**（label 逐个断言）：基本信息 / 组成 / 物性 / 状态点 / 设备连接 /
   血缘 / 校核记录；
2. ⚠️ **校核记录 Tab** 调 `GET /audit-logs` 且带 `resource_type=streams` +
   `resource_id=<id>` ⇒ 只显示**校对相关**的行（`detail.transition` ∈
   {SUBMIT_FOR_CHECK, PASS_CHECK, REJECT_CHECK}）⇒ 断言**其它 transition 不出现**；
3. **组成 Tab** 底部显示合计 + 超出 100±0.5% 时**标红**（T3 的门禁在前端也要看得见）。

- [ ] **Step 2: 跑测试确认红**

- [ ] **Step 3: 拆成 7 个子组件**

⚠️ `StreamDetailPage.tsx` 现有 266 行、两个 Card ⇒ 改成 **Tab 宿主**（只管
`Tabs` + 数据加载 + 状态），内容全部下沉到 `tabs/` 下 7 个文件 ⇒ 每个 ≤ 150 行
（`docs/TODOS.md` TODO-098 同类拆分口径）。

- [ ] **Step 4: 校核记录 Tab 的过滤逻辑**

```ts
// ⚠️ 审计行的 action 是 `RECORD_TRANSITION`（与记录侧**同构**，不新造动作）
// ⇒ 过滤靠 detail_json.transition，而不是新动作名。
const REVIEW_TRANSITIONS = ['SUBMIT_FOR_CHECK', 'PASS_CHECK', 'REJECT_CHECK'];
const rows = audit.rows.filter((r) => REVIEW_TRANSITIONS.includes(r.detail_json?.transition));
```

⚠️ `audit_logs.detail_json` 在 OpenAPI 里是 `object`（任意）⇒ 前端要**防御性**读
（`r.detail_json?.transition`），不能假设它存在。

- [ ] **Step 5: 跑测试 + typecheck + lint + 全量前端测试**

- [ ] **Step 6: Commit**

```bash
git add pcs-frontend/src/pages/sim/StreamDetailPage.tsx pcs-frontend/src/pages/sim/tabs/ \
        pcs-frontend/src/api/stream.ts pcs-frontend/tests/pages/sim/streamDetailTabs.test.tsx
git commit -F <消息文件>
```
首行：`feat(P9B-3): 物流详情页 7 Tab（含校核记录 · 读 audit_logs）`

---

## Task T9：QA gate + 收口

**Files:**
- Create: `.gstack/qa-reports/qa-report-pcs-frontend-2026-11-XX-p9b3.md`（gitignored）
- Modify: `TODOS.md`（本批结项）
- Modify: `.wolf/STATUS.md`（下一 quest）

- [ ] **Step 1: 后端全量**（先起 Redis）

```bash
cd pcs-backend && docker compose up -d redis && uv run pytest -q
```
⚠️ **别信 `pytest | tail` 的退出码**（管道会吃掉）⇒ 看文本结果行。

- [ ] **Step 2: PG 车道**（T0 的唯一入口）

```bash
cd pcs-backend && bash scripts/pytest_pg.sh
```
Expected: 退出 0 且输出含 `N passed`（N ≥ 1）。

- [ ] **Step 3: 前端全量**

```bash
cd pcs-frontend && npm run typecheck && npm run lint && npm run test
```

- [ ] **Step 4: 契约门禁（批末）**

```bash
cd /home/pangzy/code_project/PCS
cp pcs-backend/docs/openapi.json pcs-backend/docs/openapi-baseline.json
bash pcs-backend/scripts/gate_08_openapi_contract.sh --check-baseline
```

- [ ] **Step 5: 三库验证（每库独立进程 + 直查库）**

⚠️ **必须每库一个独立进程**（alembic 的 settings 是 pydantic 缓存实例）⇒ 且
**直查库**的 `alembic_version` 与目标列，不能只信命令输出。

- [ ] **Step 6: 浏览器 QA**

`npm run dev` ⇒ `~/.claude/skills/gstack/browse/dist/browse`（`CI=1`）：
login 200 → dashboard → 逐条走 T5/T6/T7/T8 的新页面 ⇒ 控制台 0 error ⇒ 网络 0×404。
⚠️ `goto` 会清 zustand ⇒ 路由可达性检查走 **SPA 菜单点击**。

- [ ] **Step 7: 写 QA 报告 + 结项**

报告路径 `.gstack/qa-reports/qa-report-pcs-frontend-2026-11-XX-p9b3.md`，**certified 范围
写真实 commit 区间**（评审 #3 的教训）。

- [ ] **Step 8: Commit**

---

## 验收（全批）

| 门 | 判据 |
|---|---|
| 后端全量 | `pytest -q` 0 failed（基线 5405 passed / 77 skipped / 1 xfailed ⇒ 本批净增） |
| **PG 车道** | `scripts/pytest_pg.sh` exit 0 且 `N passed`（N ≥ 1）—— **不是**「skip 也算过」 |
| 前端全量 | `npm run typecheck` / `npm run lint` / `npm run test` 全绿 |
| 契约门禁 | `gate_08_openapi_contract.sh --check-baseline` 四阶段全过 |
| 三库 | `pcs` / `pcs_test` 各 `p9_014` + `alembic check` exit 0（独立进程 + 直查库） |
| 浏览器 | 新页面全部可达；控制台 0 error；网络 0×404 |
| 债项 | TODO-101 / 102 / 103 关闭；TODO-099 关闭（PG 车道落地）；TODO-092 / 100 仍在（**本批不做**，已登记） |

---

## P9B-3b 移交（批量「提交校对」—— 本批**不做**）

委员会 2026-11-02 裁决 5：六条契约决策全部采纳，但**归属取决于 P9B-3 的总量**
⇒ P9B-3 本体 ≈ 11 天（≈ 2.2 周）⇒ 已接近 2 周 ⇒ **按委员会建议单列 P9B-3b**。

**P9B-3b 的任务书（本批只留接口与移交说明，实施另起计划）**

后端 `POST /streams/batch/submit`：

- 请求 `{stream_ids: [uuid], dry_run: false}`；响应 **207 Multi-Status**：
  `{batch_id, total, succeeded: [{stream_id, from_status, to_status}], failed: [{stream_id, reason, detail}]}`
- **D1** 后端端点（不是前端循环）—— 典型批量 30–50 条，前端循环部分失败无法重试
- **D2** 部分成功（**不做**全原子）—— 50 条里 8 条失败不该回滚 42 条
- **D3** 审计 **N+1** 条：N 条单条（动作沿用 **`RECORD_TRANSITION`** —— 见
  「与 brief 的偏差」第 2 条）+ 1 条批次（新动作 `STREAM_BATCH_SUBMITTED`）
- **D4** 上限 100 条，配置化（`system_settings` 的 `stream.batch_submit_limit`）
- **D5** 幂等：按 `stream_id` 去重；**已 `IN_APPROVAL`** 视为成功
  （`note: "already_in_approval"`；⚠️ 状态名见「与 brief 的偏差」第 1 条）
- **D6** `dry_run=true` ⇒ 不改状态、不写审计，只返回校验结果
- ⚠️ **失败原因 `SIM_STREAM_COMPOSITION_OUT_OF_RANGE`** 由 T3 提供（不是新造）
- ⚠️ **最关键的测试**：并发提交同一条 stream ⇒ 一胜一拒（行锁）——
  **与 P9B-2 报告 #1 同形** ⇒ 必须有方言级 SQL 断言 + 接线断言（PG 级并发靠
  `scripts/pytest_pg.sh` 车道）

12 条边界用例清单（委员会 brief 第五节）照抄进 P9B-3b 的计划。

---

## 尚未解决的问题（开工前需裁决或登记）

| # | 问题 | 现状 | 建议 | 归属 |
|---|---|---|---|---|
| 1 | SPEC §7.7.1「引用 📎×N」的 **N 是什么** | SPEC 只给了列名，未定义口径；后端列表响应**不返回**该字段 | N = 该物流被**下游引用**的条数（设备 + 物流，lineage downstream 口径）⇒ 需后端在列表响应里加 `reference_count`（**一次聚合，无 N+1**） | **本批开工前裁决**（T2 已登记「本批先不渲染引用列」） |
| 2 | 组成合计的**气/液两相口径** | 主组成 `composition_json` 的口径已按实测钉死（CAS→摩尔分率，0~1，判定 \|sum−1\| ≤ 0.005，见 T3） | **但**两相流的 `vapor_composition_json` / `liquid_composition_json` 是否**各自**也要合计校验？ | 建议：**只校验主组成**（两相的两份是同一套组分的相态拆分，各自合计本就 ≈1 ⇒ 重复校验只会制造噪音） |
| 3 | 物流列表「来源」列 —— **后端没有这个字段** | 实测 `streams` 无 `source` 列；`data_mode` 是「数据模式」（CHEMICAL / PETROLEUM / SOLID），**不是** SPEC §7.7.1 的「SIM导入 / 手动 / Excel / 化验」 ⇒ SPEC ↔ 实现分叉 | 二选一：**(a)** 后端加 `streams.source` 列 + 迁移（记录创建方式：手动向导写「手动」、导入写「SIM导入」）⇒ 一次迁移，且让 T7 向导能记录来源；**(b)** 改 SPEC §7.7.1 删掉「来源」列与筛选 | 建议 **(a)**（来源是业务真实维度，导入向导本来就分「PRO/II / 手工 / Excel」）—— 但它给本批加一次迁移 ⇒ **开工前裁决** |
| 4 | 手动创建向导里「物性估算」与「写入 DRAFT」的**顺序** | 估算要 `stream_id`，写入要校验通过 | 建议：**先校验 → 写入 DRAFT → 再估算**（估算失败不回滚 DRAFT，只提示） | 开工前裁决（T7 依赖它） |
| 5 | 「提交校对」要不要**理由** | 既有单条端点 `reason=None` | 本批**沿用不要求理由**（与既有行为一致，不扩语义） | 已定（无需裁决） |
| 6 | 系统参数页显示**哪些键** | `system_settings` 是通用 KV，键由后端/运维写入 | 页面显示**全部键**（不做白名单）⇒ 白名单反而要求后端维护一份清单 | 已定（无需裁决） |
| 7 | 角色分配 ADR 的**编号与立项时机** | 裁决 3 要求升格独立 ADR | 建议下一批开工前先立 ADR（与 P9B-3 并行不冲突） | 下一批 |
| 8 | P9B-3b 的端点命名 | 委员会 brief 用 `POST /streams/batch/submit` | 与 FastAPI 现有前缀风格一致（`/streams/{id}/submit`）⇒ `POST /streams/batch/submit` 可用，但 `batch` 会与 `{stream_id}` 抢路由 ⇒ **建议** `/streams/batch-submit` | P9B-3b 开工前裁决 |

---

## GSTACK REVIEW REPORT

> 计划成型后跑 `gstack review`（或 `/plan-eng-review`）做一次外部复核；复核结论以
> **追加节**形式写回本文档（不改写正文 —— 计划是时点快照，改写它会让「当时说了什么」
> 不可追溯）。
