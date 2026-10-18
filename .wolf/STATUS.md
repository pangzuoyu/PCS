---
description: session handoff, regenerate with /handoff when a quest finishes
budget_tokens: 1500
---
# STATUS — PCS

> Read this FIRST when starting a session. Last updated: 2026-10-18.
> 保持 <2k tokens。历史细节查 `git log` / `docs/` / `TODOS.md` / `.wolf/memory.md`。

---

## ✅ 本会话完成

**P8 ce-code-review 评审 + 全部 6 步修复落地**（commit `211f3c6`..`c9d937f`）。

1. **评审**：13 reviewer、30 primary findings；8 条 P0/P1 全部 validator
   confirmed。产物入库 `docs/ce-code-review/20261014-005528-981d772a/`
   （**入口 `README.md`**，本体 `report.md`；两处已证伪断言标明勿从 reviewer
   json 捡回：15 算子「从未执行」不实、JSONB「PG 500」未证实）。
2. **修复**：2 P0（固定 10 类项目隔离 `6b5c756`、回收器不 commit `211f3c6`）
   + 6 P1（`#3/4/5/6/7/8`）+ 8 条裁决 P2/P3（`#9/11/12/14/15/17/18/23/25`）。
   迁移新增 `p8_008/009/010`（补 CHK、NULLS NOT DISTINCT、ACTIVE 部分唯一索引）。
3. **三处评审前提被实测推翻**：#4 签名不在 `_content_hash`（qr_payload 根本
   不参与哈希）；#7「重跑」被按钮 disabled 拦死（世代守卫只剩卸载可达，
   变异证据已写进该测试 docstring）；#17 信封本就统一（真问题是 code 不语义，
   已语义化 + 发布说明 `docs/PCS-NOTE-P8-错误信封统一-2026-10-18.md`）。
4. **两类基础设施级假绿源**入 `docs/solutions/` 三篇：ARQ 0.28 静默失效族、
   `:memory:` StaticPool 盲区（「第二个 session 读」全仓失效）、方言盲区族
   （NULLS NOT DISTINCT / sqlite_where / alembic check 只审所连库）。
   bug-169..179 入 buglog（均带 fix_commit）。
5. **CLAUDE.md** 加 `alembic check` 第 4 条读法（跨库需各跑一次）。
   bug-171 审计收尾：6 测试定性完毕（见 TODOS.md 结论表）。

## ✅ 早前已完成（细节查 git log）

P7 迁移守门修复（幂等闸 AST 化、bug-143/144、COMMENT 比对关闭）、
CORS、auth 三条、CATEGORY_6 设备库地基、CI 首次全绿。

---

## 🚀 Next quest

P8 主体已闭环。候选（按价值排）：

1. **`TODOS.md` 的 43 条 alembic 旧账**（明细表在 TODOS.md）：
   39 条补 ORM 声明零迁移成本；`utility_energy_summary.workspace_id`
   CASCADE vs RESTRICT **需业务裁决**。
2. **TODO-039/041**（前端类型唯一性、MSW 契约冻结，逾期 20+ 天；
   评审 #24 MSW mock 落后契约三处也在此族）。
3. **P9 起步**：`report_verify_base_url` 未配置 ⇒ 二维码当前默认不印
   （`#4` 的修复已就位，配置后生效）；`assemble` 真分批（P9 范围）；
   TODO-026（JSONB 子键平铺）。

---

## Context

- main，工作区除 `.wolf/*`（钩子维护）外干净。**不要建 worktree**（历史事故）。
- **两库均在 `p8_010`，`alembic check` 均 exit 0**。`pcs_test` 是行为验证库
  （迁移 guard / 约束实测都在它上面做，用后恢复 head）。
- 基线：后端 **4495 passed / 0 failed**，前端 **621 passed / 0 failed**，
  两端 lint / typecheck clean。改 OpenAPI/schemas 的 commit 会自动触发
  G-08 契约门禁并重生成 `api.d.ts`。
- 改迁移的纪律：`alembic check` 退出码 **255**；先 `current` vs `heads`
  确认它跑了；**每个库各跑一次**；行为验证上真库（单测对 dialect 选项
  与约束语义全盲）。
- 无 CI/CD（单人开发裁决，勿再建议）。

---

## 教训（本会话新增，全文见 docs/solutions/ 三篇）

- **三级假绿**：测错东西 → 观测方法被 fixture 击穿（StaticPool）→
  **功能从未触发**（第三种不需要「测试写错」，空分支的绿灯是默认的）。
  可选功能必须有「该触发时确实触发了」的测试。
- **评审结论当「要修什么」读，不当「怎么修」读**：三处建议方向对、
  前提在本仓不成立。推理正确但前提错误的建议比推理错误的更危险。
- **方言选项要三处齐**：`postgresql_nulls_not_distinct` +
  `postgresql_where` + `sqlite_where`，少一处就是测试/生产语义分叉。
- 变异验证证明的是「测试**有效**」，不是「测试对」—— 新守卫测试必做。
- 测试断言别写 `... or True`（恒真比不写更糟）；观测点先做最小探针。
