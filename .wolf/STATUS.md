---
description: session handoff, regenerate with /handoff when a quest finishes
budget_tokens: 1500
---
# STATUS — PCS

> Read this FIRST when starting a session. Last updated: 2026-10-06.
> 保持 <2k tokens。历史细节查 `git log` / `docs/` / `TODOS.md` / `.wolf/memory.md`。

---

## ✅ CI 首次全绿（2026-10-07，`c09d551`）

`check-api-drift.yml` 跑通全链 9 步，2m19s，0 error。此前**从未绿过**：

1. **checkout 就死** —— index 里有 6 个 gitlink（`vendor/` 5 个 + `rdkit`）却没有
   `.gitmodules`（该文件从未提交）。`actions/checkout` 清理 SSH key 时跑
   `git submodule foreach` → `fatal: No url found for submodule path` → exit 128。
   修复 `87224a2`：移除 gitlink + gitignore（项目早已决定改走 PyPI，见
   `pyproject.toml:96-97`；rdkit 全仓零引用）
2. **第 3 步迁移链炸** —— `alembic_version.version_num` 是 VARCHAR(32)，而本项目
   **24 个 revision 名超 32 字符**（最长 47）。树里早有修复
   `p1_sprint3_bootstrap_alembic_version`，但它的 `down_revision` 排在**失败点下游**，
   全新库永远跑不到。修复 `682e64a`：把加宽语句放进根迁移 `dd47298c9c38`
3. **npm ci 网络抖动** —— `ECONNRESET` 一次抖动判死整个 job，且 workflow 没有
   `setup-node`（Node 版本靠 runner 自带、无 npm 缓存）。修复 `c09d551`：
   锁 Node 22 + `cache: npm` + 3 次重试

⚠️ **本地无法端到端验证迁移链**（建临时库两次被权限拦），第 2 项是 CI 替我们验的。

## ✅ Done（本会话）

**F-P7-S4-01 撤回**（`1180706`）—— 上一会话登记的待修缺陷是**误报**。最小复现证据
`assert 'QUALIFIED' == 'UNVERDICTABLE'`：`evaluate` 对 REFERENCE_ONLY 返回 QUALIFIED
（`deviation_service.py:240`），不触发 `can_confirm` 阻断。**无行为改动**，只改 docstring +
3 条测试断言方向 + bug-141 改「已撤回」。

**`TODOS.md` 46 项全量核销**（`ba101f2`）—— 4 组并行只读实证，判定 + 证据 + owner。
结论：16 DONE / 1 WONTFIX / 20 OPEN / 3 BLOCKED / 4 STALE。**17 条是陈旧假条目**，
其中 1 条照原文改会破坏契约（TODO-027）。文件从 467 行压到 268 行。

**删除 `equipment_lib` 死表**（`63c92bc`）—— 设备库改由 `ConfigAsset` + `CATEGORY_6` 唯一承载。
该表 0 行 / 0 代码引用 / 0 专属测试；SPEC P2 §3.2.6 标题即「复用设备库管理（CATEGORY_6）」，
**规格从未要求独立表**。落地：`p7_s5_001` 迁移（drop + 可回滚 downgrade）、
删 ORM、`test_schema` 104→103、ADR-0032 §P5-1-3 改写、`docs/PCS-NOTE-equipment_lib-废弃-2026-10-06.md`。
连带纠正一次基于错误前提的 DEFERRED（详见下方教训）。

**修 `app/models/__init__.py` 漏 import `util`**（`2c44e0c`）—— 该包 docstring 明写
「alembic/env.py 依赖本包导入即注册全部表」，却列了 16 个模块独漏 `util`。
后果：7 张 UTIL 表对 autogenerate 不可见 → `alembic check` 恒报 130 条**假**漂移
→ CLAUDE.md 指定的守门动作形同虚设。修后 95→102 表，130→84 条，`remove_table` 归零。

**更早的已完成批次**（细节查 git log）：P7 Sprint 0-4 全分支、T5 综合能耗封版
（tag `t5-energy-summary-2026-10-05`，**工艺室会签待补**）、P6 全系列、F-P0-001 折标系数签字。

---

## 🚀 Next quest

**无单一目标 —— 用户明确要求逐项拍板，勿替他选。** 队列（详见 `TODOS.md`）：

| 优先级 | 项 | 工作量 |
|---|---|---|
| 🔴 | **CORS middleware 未挂** —— `grep add_middleware app/` 全仓 0 命中，`cors_allow_origins` 配置项无人消费。**前后端一分域部署 preflight 直接 403**，dev 靠 Vite proxy 掩盖至今未暴露 | 低（~20 行），独立 |
| 🔴 | **auth 安全三条** —— `/auth/login` 无限流、无 LOGIN_SUCCESS/FAILED 审计；JWT 过期/无效未细分（`security.py:116` 承诺过但 `AUTH_EXPIRED_TOKEN` 全仓 0 命中）；无 `token_version` | 中，一组 |
| 🔴 | **CATEGORY_6 设备库地基 5 项** —— `type_code` 根本没采集（相似度无主匹配键）、settle 无去重、JSONB 无索引、category 无枚举、审批语义冲突。**阻塞 UI-SPEC §7.16 相似度**。真库 CATEGORY_6 **0 行**，功能从未被真实使用 | 大 |
| 🟡 | **84 条真索引漂移** —— 假漂移修好后守门说真话了。以「索引名对不上」为主（`ix_cepci_year` vs `ix_cepci_index_series_year`）。逐个裁决 ORM 对 / 迁移对，建议按表分批 | 中 |
| 🟡 | **27 个真库测试文件迁 SQLite** —— `TODOS.md` 原称 4 个，实测 27 个 | 中 |

**P7 Sprint 5 计划尚未写**。若要写：`superpowers:writing-plans`，**不要**沿用 Sprint 4
的 plan 格式（无 Requirements/R-ID，review 扣分）。ledger 落 `.superpowers/sdd/` ——
**该目录 gitignore，持久约束必须落 tracked**。

---

## Context

- main @ `2c44e0c`，已推 origin/main，工作区干净（仅 `.wolf/*` 由钩子维护）。
  **不要建 worktree** —— 上一会话因 worktree 被删，harness 隔离守卫援引不存在路径且 cd 逃逸失效，
  会话永久卡在「能 Read 不能 Edit/Bash」。直接在主检出区起会话。
- 全量基线：**3924 passed / 77 skipped / 1 xfailed / 0 failed**（`uv run --no-sync pytest tests/ -q`，3.5 分钟）。
  单测跑内存 SQLite，**不需要** `alembic upgrade head` 前置。
  **但** `tests/test_schema.py` 例外——它连**真实 Postgres**（`get_settings().database_url`），
  改迁移后必须真跑。
- 无 CI/CD（单人开发裁决，勿再建议）。
- ce-code-review 产物：`docs/ce-code-review/20261006-sprint4/`。该 skill 的 `$RUN_DIR`
  **未展开**会在仓库根建 `RUN_DIR=` 字面量目录，见到了直接 `rm -rf "RUN_DIR="`。

---

## 教训（已写入 `TODOS.md` / `buglog`）

- **登记缺陷前必须跑最小复现，不能从 code 注释推断返回值。** bug-141 即如此：注释的
  「不判合格与否」说的是*不产出判定*，不等于 verdict 是 UNVERDICTABLE。
- **查错表会让需求被错误理由推迟两次。** UI-SPEC §7.16 的相似度：
  ①ADR-0032（2026-09-17）以「`equipment_lib` 0 行」为由 DEFERRED `recommend_vessels`，
  但沉淀功能早在 **11 天前**（2026-09-06）就接到 ConfigAsset 了；②P7 总计划的 S3-2
  在 2026-10-02 重划 Sprint 3 范围时被**静默丢弃**，无人察觉。计划文件 144 个 checkbox
  **0 个打勾** —— 执行从不回填，文件状态不可信，只能对代码验。
- **守门工具恒报噪声 = 狼来了。** `alembic check` 假漂移 130 条期间，CLAUDE.md 指定的
  漂移守门实际上一直没在工作。查 guard 本身是否可信，和用 guard 一样重要。
- **别把推断当发现报出去。** 本会话因 `app/models/__init__.py` 漏 `util`，差点断言
  「测试库缺 7 张表」——实际 conftest 的 `from app.api.v1 import api_router` 会链式注册，
  102 表齐全。已实测证伪并记入 `TODOS.md` 以免重犯。
- **docstring 首行用 ASCII `.`**，全角 `。` 触发 ruff D400/D415。
- **核验别用组合正则** —— `grep "A\|B"` 会被 rtk 过滤层吞掉误报「0 匹配」，逐模式单发。
