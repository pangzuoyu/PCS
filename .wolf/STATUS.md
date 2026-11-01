---
description: session handoff, regenerate with /handoff when a quest finishes
budget_tokens: 1200
---
# STATUS — PCS

> Read this FIRST when starting a session. Last updated: 2026-11-01（**P9B-2 评审修复批 P9B-2R 全落地**；上批：P9B-2 整批 + minors）。
> 保持 <2k tokens。历史细节查 `git log` / `docs/` / `TODOS.md` / `.wolf/memory.md`。

---

## ✅ Done

### 第 20-21 轮：**P9B-2 整批 ce-code-review + 委员会两轮裁决的修复批（P9B-2R）**

**审查**（2026-10-29，`docs/ce-code-review/20261028-074842-e15c26e8/`）：11 reviewer +
独立验证批（6 confirmed / 2 rejected-as-pre-existing），判定 Ready with fixes。
配额打爆两次 ⇒ 串行小批收齐（cerebrum 有恢复姿势）。

**修复批**（`58341eb..369e855`，5 commits，每条先红）：

| commit | 内容 |
|---|---|
| `58341eb` | **#1 P1**：审批链 submit 冻结快照（mixin 列 + 迁移 p9_014×20 表）+ 每步 submitted_by 二次断言 + submit/approval-step 行锁；顺带 #16/#17/#9 |
| `607dee5` | **#4** FORMAL 门（后端 422 + 前端过滤）· **#5** 重号 409 · **#6** 默认矩阵 savepoint+重读（bug-2062 同款）· **PE-1** 枚举 .value · #13 |
| `dcfbc75` | **#8** 决胜列钉住（含变异验证）· p9_013 **真跑引擎** + 降级环测试 · **A-4** 降级口径诚实化 |
| `7cce7da` | **#10** 过滤器只在「查询」冻结 · **#11** 列表重试 · **#18** 凭据复位 · chainCache 并入 #1（挂载级）· **A-3** WORKFLOW_LABELS 词表合一 · B-1 mock can_skip 409 · B-4 批注末页 · 清理批 #7/#14/#15/#20/遮罩错误 |
| `369e855` | TODOS **095-099** 登记 · solutions 回写 ×2 · ROLLBACK-RUNBOOK（追问 1）· SPEC #12 · schema doc |

**验收**：后端全绿（首跑 8 failed = Redis 未起，起后 --lf 8/8；带 Redis 全量在跑
收尾中）；前端 typecheck/lint/`vitest run` 全过（新增 14 测试）；Playwright 21/21；
三库 `p9_014 (head)` + `alembic check` exit 0 + 降级环实测；G-08 ×2 过；
浏览器 QA 0C/0H/0M（`.gstack/qa-reports/qa-report-pcs-frontend-2026-11-01-p9b2-review-fixes.md`，
FORMAL 过滤下拉实测生效）。buglog +10（2101-2110）。

**委员会裁决落实**：#2/#3 pre-existing ⇒ TODO-**093/094**（安全，开放）；
chainCache 已并入 #1 修完；PE-1 升必修已修。

---

## 🚀 Next quest

1. **P9B-3**：系统参数前端 + 物流手动创建向导 + 校对 UI（SPEC §7.20 的
   「AI 开关 / 系统参数 / Prompt 模板 / 角色分配」几页仍未落地；TODO-092 同面）。
2. **follow-up review**（委员会追问 4）：对 P9B-2R 修复批的下一轮 review 须把
   cap-tail 四条（#10/#11/#12/#18）+ #1 快照语义列入 scope 复核。
3. 开放 TODO：**091-099**（093/094 是安全项：sign_step 并发丢签名 / 二次认证
   任意凭据）；57 手写类型长期债；ADR-0050「先不做」。

---

## Context

- main，工作区干净（`.wolf/*` hook 自动维护）。**不要建 worktree**（历史事故）。
- 两库均在 **`p9_014`**（head）。迁移三库验证 = pcs + pcs_test（进程内 DATABASE_URL，
  **别 set_main_option**）+ 隔离 schema（tests/alembic 的 roundtrip 测试现成）。
- **CI 是活的** ⇒ 改迁移必须在全新库上验；**全量 pytest 前先 `docker compose up -d redis`**
  （ws/broadcaster 系列失败 = 环境未起，不是回归；**别信 `pytest | tail` 的退出码**）。
- 契约：批末滚 baseline（pre-commit G-08 自动跑）；快照列**未**入契约（内部列）。
- 提交约定：conventional commits，无 attribution 行；长消息写文件后 `git commit -F`。
- ⚠️ API 测试 `client` fixture mock 掉项目授权；StaticPool 共连接 ⇒ 真并发测试
  不可表达（见 test_second_submit_after_commit_is_409 的 docstring）。
- ⚠️ 前端 e2e：SPA 菜单导航（goto 清 zustand）；antd 汉字按钮插空格 ⇒ 用正则。

---

## 教训（本批新增，已进 cerebrum）

- 一次性守卫 + 实时配置回查 = 纸门 ⇒ 动作发起时冻结判据快照（两侧同构）。
- 新写 get-or-create 先 grep 同文件同形方法（_ensure_binding 模式直接抄）。
- 管道尾 `| tail` 吃掉 pytest 退出码 —— 看文本结果行，别信退出码。
