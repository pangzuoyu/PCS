---
module: pcs-backend records_actions — approval chain
date: 2026-10-31
problem_type: security_issue
component: workflow / authorization
severity: high
tags: [approval-chain, signature-matrix, cwe-863, snapshot, race, P9B-2]
symptoms: 提交人可以在送审后批自己的记录（APPROVAL_SELF_REVIEW_FORBIDDEN 被绕过）；矩阵中途被禁用后已提交的链卡死（409 SIGNATURE_MATRIX_NOT_ACTIVE）
root_cause: 一次性守卫 + 实时配置回查的组合：自审禁令只在 submit 时查一次（对着当时的矩阵），而中间步骤的待批角色每次都从「当前绑定的矩阵」重新推导 ⇒ 任何提交后发生的配置变更（重绑 / 禁用 / 删行）都能改写已进入审批的链
---

# 中途配置重绑绕过一次性守卫 —— 审批链必须在提交时冻结（快照）

## 形状

「检查一次 + 之后每次回查实时配置」的守卫，等价于「配置可以在检查之后改掉规则」。
攻击（CWE-863）：SYSTEM_ADMIN 在链外提交（自审过关）→ 重绑项目矩阵把自己塞进
第 2 步 → 第 1 步过后待批角色变成自己 → 自己批自己。同族还有：矩阵中途被
禁用 ⇒ 已提交的链吃 409 卡死；矩阵行被删 ⇒ 链静默换轨。

## 解法（与交付物侧 `_steps_for_version` 同构，别造第二套）

1. **submit 时冻结整条链**进记录行（`approval_chain_snapshot` JSONB：
   `{matrix_id, steps[], submitted_by, submitted_by_role}`）——记录表是
   mixin 共列（20 张表一个迁移 `p9_014`），列 nullable 兼容存量行；
2. **中间步骤只读快照**；快照为 NULL（部署窗口前的存量 IN_APPROVAL 行）
   才回退实时矩阵（行为不劣于修前）；
3. **提交人身份写进快照，每步二次断言**（`actor.user_id == submitted_by`
   ⇒ 403）——即使角色恰好匹配被注入的下一步，提交人也批不了自己；
4. **submit/approval-step 都持行锁**（`SELECT … FOR UPDATE` +
   `populate_existing`，同文件编号路径的既有模式）：并发双提交/双批注在
   PG 上串行化为一成一拒 ⇒ 审计不重不漏（ADR-0047）。

## 检测（为什么单测全绿）

两个洞都是「配置变更发生在 submit 之后」的时序问题——正向流程测试里矩阵
从不动。钉住它的测试必须**在 submit 之后改配置**再推进一步
（`test_midflight_rebind_cannot_change_pending_role` /
`test_matrix_disabled_mid_approval_keeps_chain`）。

## 教训

- 「一次性检查」守卫的判据源若可变，守卫就是纸；
- 前端配套：链信息的**客户端缓存不得跨挂载**（曾用模块级 Map 永生缓存 ⇒
  重绑后 SPA 拿旧链直到整页刷新 ⇒ 前端门禁与后端判据分叉）；
- SQLite 单测并发不可表达（StaticPool 共连接 ⇒ 无隔离），行锁语义只有
  PG 能验 ⇒ 见 [[engine-level-migration-tests-skipif-pg]]。
