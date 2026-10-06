---
description: session handoff, regenerate with /handoff when a quest finishes
budget_tokens: 1500
---
# STATUS — PCS

> Read this FIRST when starting a session. Last updated: 2026-10-06.
> 本文件已于 2026-10-06 精简重写（原 16k → <2k）。历史细节查 `git log` / `docs/` / `.wolf/memory.md`。

---

## ✅ Done

**P7 Sprint 4 全分支已合入 main**（`3e5ae90..dc134b2`，77 文件）。四件事：供应商实际数据录入 → 偏差报告 3+1 档判定 + xlsx/PDF 导出 → 泵设计值接线 → 蜡油加氢真实数据端到端。fix pass 关掉 34 条 ce-code-review finding。

**F-P7-S4-01 撤回**（`1180706`）—— 上一会话登记的待修缺陷是**误报**。
最小复现证据：`assert 'QUALIFIED' == 'UNVERDICTABLE'`。
`evaluate` 对 REFERENCE_ONLY 返回 QUALIFIED（`deviation_service.py:240`「参照量是有效数据、只是不承担判定」），不触发 `can_confirm` 阻断。原始代码本来就是对的，**无行为改动**；只改 docstring + 3 条测试断言方向 + buglog bug-141 改「已撤回」。
先前观察到的「不可判 1 项: 轴功率」真问题是 #8 的应检集补行，#8 落地时已排除 REFERENCE_ONLY，已修。

**T5 综合能耗验收封版**（2026-10-05，tag `t5-energy-summary-2026-10-05`）。基准重建为 GB 30251-2024 附录A 表A.1 独立重算（旧基准是旧代码输出反抄的自证循环，假 PASS）。Case 4 三项全 PASS（0.0011%/0.0000%/0.0020%）。**工艺室会签待补**。

**更早的已完成批次**（细节查 git log）：P7 Sprint 0-3、P6-4/5/6A/6B/7/8/9、F-P0-001 折标系数签字（`docs/PCS-SIGN-F-P0-001-2026-10-08.md`）。

---

## 🚀 Next quest

**P7 Sprint 5 启动**（尚未有计划文件）。方向待用户定，Sprint 5 候选：

- `CHECK_SUBMITTED` 的 `event_id` 派生口径 —— 判据已写进 `confirmation_service.py::confirm_actual_data` 的 `uuid4()` 处注释。（`cia_mark_stale` 已闭：改 uuid5 是 bug 不是 feature，别碰。）
- 非泵设备的「应检参数表」机制 —— 待其数据模型落地时再建（#8 的范围限定已登记）。
- `TODOS.md` 两条既有债（见下）。

**写 Sprint 5 计划时**：`superpowers:writing-plans`，**不要**沿用 Sprint 4 的 plan 文件格式（它非统一计划格式、无 Requirements/R-ID，review 时被扣分）。ledger 落 `.superpowers/sdd/<plan-basename>/` —— **该目录被 gitignore，持久约束必须落 tracked**。

---

## Context

- main @ `2a83af4`，已推 origin/main，工作区干净。**不要建 worktree** —— 上一会话因 worktree 被删导致 harness 隔离守卫援引不存在路径且 cd 逃逸失效，会话永久卡在「能 Read 不能 Edit/Bash」，无法修 main。直接在主检出区起会话。
- 全量回归基线：**3924 passed / 77 skipped / 1 xfailed / 0 failed**（后端 `uv run --no-sync pytest tests/ -q`，3.5 分钟）。单测跑内存 SQLite，**不需要** `alembic upgrade head` 前置。
- 无 CI/CD（单人开发裁决，勿再建议）。
- `.superpowers/` 已 gitignore；Sprint 4 执行 ledger 归档在 `.superpowers-sprint4-archive/sdd/sprint4-plan-2026-10-05/progress.md`（399 行，含全部 Ruling 行）。
- ce-code-review 产物：`docs/ce-code-review/20261006-sprint4/`（26 条 actionable，报告在 `report.md`）。该 skill 的 `$RUN_DIR` 变量**未展开**会在仓库根建 `RUN_DIR=` 字面量目录 —— 2026-10-01 那次的残留已清，未来再见到直接 `rm -rf "RUN_DIR="`。

---

## ⚠️ 已登记未清（均在 `TODOS.md` 尾部，勿重头推）

| Item | 修法顺序 |
|---|---|
| **9 个既有 `p7_open_*`/`p7_s1_*` 迁移缺幂等 guard** | 逐个补 `if_exists=True` → 补完一个从前缀白名单移一个 → 最后白名单改「全部 `p7_*`」。**顺序反了钩子立刻在无关文件上失败**（已实测）。不能无审查批量加 —— 会改变 downgrade 在「表不存在」时的行为。 |
| **`.wolf/buglog.json` 6 条 id 重号**（4× `bug-2026` + `bug-031`/`bug-002` 各重复） | 先去重再改编号算法（`max+1` 会算出 `bug-2027` 并继承重号）。**不改历史条目的 id** —— `fix_commit` 是 STATUS 反查的单点来源。 |

---

## 教训（已写入 `.wolf/cerebrum.md` Do-Not-Repeat）

- **登记缺陷前必须跑最小复现，不能从 code 注释推断返回值。** bug-141 就是这么来的：注释写「不判合格与否」被读成 verdict 是 UNVERDICTABLE，实际是 QUALIFIED。注释里「不产出判定」≠「verdict 是 UNVERDICTABLE」。
- 单测照绿 ≠ 真库能跑。改 `alembic/versions/*` 必须手动核对 ORM 列同步，缺表会红（可见），漂移会绿（不可见）。人工守门：`uv run alembic check`。
