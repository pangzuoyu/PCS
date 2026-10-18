---
description: session handoff, regenerate with /handoff when a quest finishes
budget_tokens: 1500
---
# STATUS — PCS

> Read this FIRST when starting a session. Last updated: 2026-10-19.
> 保持 <2k tokens。历史细节查 `git log` / `docs/` / `TODOS.md` / `.wolf/memory.md`。

---

## ✅ 本会话完成

**P8 评审 30 条 findings 全部闭环**（`c9d937f` → `5b1174c`），且**顺带查出并修掉
两个生产级缺陷**。

1. **评审修复**：`#24` MSW 契约冻结（`346c257`，查出 5 处真漂移）、`#19` 白名单
   （`c142014`，报告说两份实为**四份**）、`#22/#21/#29`（`2a23d2e`）、
   `#27` 状态筛选（`81947bd`）、`#10/#30/#26`（`e35ecfc`）。
2. **🔴 bug-180 管道等级页生产空白**（`09a2a88`）—— 评审 #24 引出的新发现。
   `PipeClassListPage` 读的 6 个字段名与契约**整组不同**（`pipe_class_id` vs
   `class_id`…），真后端下含 `rowKey` 全是 `undefined`。已把
   `types/pipeClass.ts` 并到契约类型、页面/mock 同步、状态列走
   `module="PIPE_CLASS"` 独立词表（非法组合**编译期即拒**）。
3. **🔴 bug-184 契约闸门 docstring 声称三项检测、实现零项**（`5b1174c`）。
   改字段名/改类型/删 enum 全放行 —— bug-180 就是这么过的闸。
   顺带：`export LC_ALL=C`（zh_CN 下 `sort`/`comm` 规则不一致，测试 1–4 本来就是红的）、
   **10s → 0.145s**。

## ✅ 基线

后端 **4516 passed / 0 failed**，前端 **675 passed / 0 failed**，两端 lint/typecheck clean。
`bash scripts/check-api-drift.sh` → OK / exit 0（test 1–9 全过）。

---

## 🚀 Next quest

1. **TODO-039 前端类型唯一性** —— bug-180 只并了 `PipeClass` 一个。
   `src/types/` 下还有多少手写副本与 `api.d.ts` 平行？逐个查
   「这份类型的字段名在契约里存在吗」比 #24 那次更彻底。
2. **契约侧两个缺口**（本轮发现，未动）：
   - `PipeClassResponse.status` 是裸 `str`，没 `Literal`
     （与评审 #28 的执行状态同类：词表没进契约，客户端无法枚举）
   - `check-api-drift.sh` 现在能检出**已提交的 snapshot 与新导出**的差异，
     但**检不出「前端代码用了契约里没有的字段」** —— 那需要另一道闸
3. **P9 起步**：`report_verify_base_url` 未配置 ⇒ 二维码默认不印（`#4` 修复已就位，
   配置后生效）；`assemble` 真分批；TODO-026（JSONB 子键平铺）。
4. 低优先：TODO-028（10 表主键 rename）、TODO-032（27 个真库测试迁 SQLite）。

---

## Context

- main，工作区除 `.wolf/*`（钩子维护）外干净。**不要建 worktree**（历史事故）。
- **两库均在 `p8_010`，`alembic check` 均 exit 0**。`pcs_test` 是行为验证库。
- 改迁移的纪律：`alembic check` 退出码 **255**；先 `current` vs `heads`；
  **每个库各跑一次**；行为验证上真库。
- 契约产物（`openapi.json` / `openapi.snapshot.json` / `api.d.ts`）由 G-08 钩子在
  **commit 之后**重生成，而 `git add` 在钩子之前 ⇒ 偶尔漏提交，
  手工 `git status` 看一眼。发现不同步时**不要** `git checkout --` 丢弃。
- 无 CI/CD（单人开发裁决，勿再建议）。

---

## 教训（本会话新增）

- **「窄的类型声明」是约束还是遗漏**：看它有没有运行时消费者在依赖它**做校验**。
  `MODULE_ACTIVATED.SIM`（4 态）只喂 opacity ⇒ 是**强调表**，物流实为 9 态；
  `STATUS_META` 的 `?? DRAFT` 兜底会**替换**未知值 ⇒ 是**约束**，而且是错的。
  把强调表提升为编译期词表 = 把**假绿换成假红**。
  全文 `docs/solutions/testing-issues/narrow-declaration-is-not-a-constraint.md`。
- **fixture 与被测对象共用一份错误类型 ⇒ 测试再多也是零信号**
  （bug-180 的 6 条组件测试全绿，页面生产上全空）。⇒ fixture 只能用契约类型构造。
- **守门的 docstring 也要被验**（bug-184）。本仓「注释比代码乐观」已五例。
- **缺失的值要显式失败，不要填默认值**：`?? STATUS_META.DRAFT` 让 ACTIVE 显示成草稿，
  用户不报错、会基于错误信息做决策。同 `toFilterTree` 伪造 `'EQUIP_LIST'`。
- 早期写 solutions/cerebrum 时**引用的常量名要核对**，别照抄上下文里的旧串。

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
