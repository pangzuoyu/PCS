---
description: session handoff, regenerate with /handoff when a quest finishes
budget_tokens: 1200
---
# STATUS — PCS

> Read this FIRST when starting a session. Last updated: 2026-11-02（**P9B-2F：follow-up 评审修复批全落地**）。
> 保持 <2k tokens。历史细节查 `git log` / `docs/` / `TODOS.md` / `.wolf/memory.md`。

---

## ✅ Done

### 第 22 轮：**P9B-2R 的 follow-up 评审（委员会裁决）→ 修复批（P9B-2F）**

**复审**（`docs/ce-code-review/20261102-004658-08a55f5c/`）：8 reviewer + 独立验证批
（8 selected / **8 confirmed** / 0 rejected），Verdict **Ready with fixes** —— 17 条
actionable（1 P1 + 12 P2 + 4 P3）。委员会 3 条补充裁决 + 1 条 fix order 调整 + 2 条追问。

**修复批**（`77e3293..c7fb6c9`，6 commits，每条先红）：

| commit | 内容 |
|---|---|
| `0586693` | **#1 P1**：行锁**可观测**（`_locked_select` 方言级断言 + 接线断言；变异实测 3 处全红）+ 删掉 false delegation；**#9**：存量行从审计流水反推提交人 + 首次触达冻结 + 查不到提交人响亮 409；**#8**：两端点 docstring 重写（快照语义 + 错误码） |
| `1e5a4d9` | **#6**：`sign_status` 词表进契约（后端枚举 + 前端 union 改契约派生）+ 新增词表守卫测试 |
| `a44c354` | **#5**：p9_014 表清单守卫（ORM 叶子表 ≡ 迁移 `_TABLES`，双向）+ jsonb/可空真引擎断言 + 降级环；**#11/#16/#17/#18**：p9_013 测试文件的假 CI 委托更正、降级目标 docstring、模块 docstring、清理失败不再静默 |
| `ef3f438` | **#14** 未知 `workflow_type` 降级（不再整页崩）· **#13** 列表信封契约派生 · **#2** 403 docblock 归位 · **#12** `record-actions-error` testid 去重（含 `destroyOnHidden`） |
| `780b1ab` | **#4** SPEC V2.5 登记 · **#10** compact ORM 补 16 行 + 表头标注快照性质 · **#15** 补 `engine-level-migration-tests-skipif-pg` 条目 · R16 第三课（`information_schema` 不受 search_path 约束）· 回滚清单补 p9_014 行 + 多库独立进程规则 |
| `c7fb6c9` | TODOS **100-103** 登记（下一轮 review 必审范围 / StateBadge 交付物词表 / 409 映射过宽 / compact ORM 快照）· TODO-099 补并发覆盖说明 |
| `c962758` | 归档报告补「委员会裁决」errata（**不改写正文** —— 评审产物是时点快照） |
| `9f08a0d` | ⚠️ **自审发现**：存量行反推提交人取了**第一条**送审审计 ⇒ 「送审→驳回→再送审」的记录会用上一轮的人当提交人 ⇒ 本轮提交人可批自己的记录 ⇒ 改取**最后**一条 + 变异实测 |

**验收**：后端 **5405 passed / 77 skipped / 1 xfailed / 0 failed**（基线 5390 ⇒ +15）·
前端 typecheck/lint clean + **989 tests 全过**（+2）· G-08 契约门禁 4 阶段全过（baseline 已滚动）·
**三库 `p9_014` 且 `alembic check` exit 0**（**每库独立进程** + 直查库确认，非推断）·
浏览器 QA 0C/0H/0M（7 条路由 + 建项目 FORMAL 下拉实测 + 签署进度展开实测）·
**5 处变异实测全部按预期变红** · buglog +10（2111-2120）· cerebrum +5 条 Do-Not-Repeat。

**QA 报告**：`.gstack/qa-reports/qa-report-pcs-frontend-2026-11-02-p9b2f.md`
（**certified `77e3293..c7fb6c9`** ⇒ 顺带覆盖上一份报告漏掉的 3 个 commit）。

**委员会裁决落实**：#1 理由改为「机制无观察 + docstring 主动误导」且**变异实测**化 ·
#9 **取消决策门**直接修（从审计推导 submitter）· 证据更正（「同进程改
DATABASE_URL 验多库 = 没跑」）进 **CLAUDE.md + cerebrum + 两份部署文档** ·
#3 的 QA 闸门**移到末尾**（本报告）。

---

## 🚀 Next quest

1. **P9B-3**：系统参数前端 + 物流手动创建向导 + 校对 UI（SPEC §7.20 的
   「AI 开关 / 系统参数 / Prompt 模板 / 角色分配」几页仍未落地；TODO-092 同面）。
2. **下一轮 ce-code-review**：scope **必须**含 TODO-100 点名的三处未深审部分
   （`test_deliverable_issue.py` + deliverables/record_edits API 改动 + 其余 diff）。
3. 开放 TODO：**091-104**（093/094 安全项；099 PG 车道；100-103 本轮登记）；
   57 手写类型长期债；ADR-0050「先不做」。

---

## Context

- main，工作区干净（`.wolf/*` hook 自动维护）。**不要建 worktree**（历史事故）。
- 两库均在 **`p9_014`**（head），`alembic check` exit 0。
- ⚠️ **验多库必须每库独立进程**（alembic settings 是 pydantic 缓存实例）+
  **直查库**确认（`alembic_version` + 列存在性），不能只信命令输出。
- ⚠️ **本仓无自动化 PG 测试通道**（CI 的 api-drift job 一条后端 pytest 都不跑）⇒
  `tests/alembic/` 的引擎级测试**必须本地手动跑**；文档里不得写「CI 承担」。
- **全量 pytest 前先 `docker compose up -d redis`**（ws/broadcaster 系列失败 =
  环境未起）；**别信 `pytest | tail` 的退出码**；`test_todos.py` 的 500ms 墙钟
  预算测试在满负载下会抖（隔离跑即过）。
- 契约：批末滚 baseline（`cp openapi.json openapi-baseline.json`）后跑 G-08
  `--check-baseline`；快照列**未**入契约（内部列）。
- 提交约定：conventional commits，无 attribution 行；长消息写文件后 `git commit -F`。
- ⚠️ API 测试 `client` fixture mock 掉项目授权；StaticPool 共连接 ⇒ 真并发测试
  不可表达（行锁只能**方言级**钉）。
- ⚠️ 前端 e2e：`browse goto` 清 zustand ⇒ 路由可达性检查走 **SPA 菜单点击**。

---

## 教训（本批新增，已进 cerebrum）

- 「CI 在验」之前必须**读那个 workflow 的 steps**（本仓已两次假委托）。
- `finally` 里的 assert 会**顶掉**原始异常 ⇒ 清理判定放 try/finally **之后**。
- 方言级断言必须**抽生产代码出来**，否则测试只能照抄 ⇒ 删了锁照样绿。
- 评审的「全绿」结论：**先变异实测再转述**（推断 ≠ 实测）。
- 从审计流水反推「当前轮次的执行者」⇒ 取**最后**一条（构造多轮测试 +
  时间戳显式设值，别依赖时钟分辨率）。
