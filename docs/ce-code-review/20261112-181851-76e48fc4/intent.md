# Stage 2 — Intent & Plan Discovery (P10-A)

## Intent summary

P10-A 落地两段。**段一（10.0 前置与测试左移）**：docker-compose 新增 test profile 下的一次性 `migrate` / `seed` 服务；新增幂等种子脚本（固定 UUID、`--reset` 只删自己、**必须造 `UserProject` 授权行**）；新增**真后端 E2E 通道**（`VITE_ENABLE_MOCK=false` 关 MSW + Playwright `real-backend` 项目 + `gotoViaMenu` SPA 导航 + 代理目标 env 可配 + mock-login 路径改写）。**段二（10.1 AI 预留）**：新增 5 个**一律返回 501** 的 AI 端点；新增唯一出站出口 `OutboundAIClient`（内网 CIDR 二次校验 + 脱敏 + 审计）；新增纯 ASGI **AI 审计中间件**（认证失败也留痕、body 读后重放）；新增 ARQ **异步审计任务**（幂等、partial 唯一索引、`ON CONFLICT ... index_where`）；`ai_audit_log` 加 8 列 + 迁移 `p10_001`；新增 `/api/v1/health/ai`；前端顶栏加**禁用**的 AI 占位；新增架构守卫「AI SDK 只能从唯一出口出去」。

**必须不回归的既有契约**（任何 finding 若指向这些，属于真实缺陷）：
1. **认证先于 501**：无有效 token ⇒ 401，不是 501。
2. **认证失败也要有审计行**（`user_id=None`）⇒ 审计表对探测行为不失明。
3. **body 重放**：中间件读 body 后下游仍能校验 ⇒ 参数错是 **422**、不是 501（否则症状与「参数错」无法区分）。
4. **审计写入幂等**：同一 `request_id` 重复写**不得**报错、不得产生重复行；partial 唯一索引必须与 `ON CONFLICT` 的 `index_where` 匹配（**PG 方言专属**，SQLite 单测照绿）。
5. **审计行不得被静默丢弃**：客户端可控的 `client_request_id` / path 超长时必须截断而不是让 PG varchar 报错丢行。
6. **种子脚本幂等**：重复跑结果一致；`--reset` 只删自己造的；**必须建 `UserProject` 授权行**（否则 dev 前端全站 404）。
7. **架构守卫真的会红**：绕过唯一出口直连 AI 端点 ⇒ 守卫必须报。
8. **真后端 E2E 通道不得静默跑成 mock**：代理目标不对时必须**失败**而不是假绿。
9. **分层约束**：`core ⊄ api/models`，`services ⊄ api`；`op.create_index` 必须带 `if_not_exists=True`。

## Plan discovery

| 项 | 值 |
|---|---|
| `plan_source` | `inferred`（无 PR/issue 元数据，从仓库内文档推断） |
| 批次计划 | `docs/superpowers/plans/2026-11-04-p10-batch-a-preflight-ai-reserve.md`（15 个任务 T1–T15） |
| 总纲计划 | `docs/superpowers/plans/2026-11-04-p10-master-plan.md`（「四之二、批次落地状态」记录本批） |
| 需求来源（spec） | `spec/P10 AI预留与测试部署开发规格说明书.md` |
| 执行账簿（裁决记录） | `.superpowers/sdd/2026-11-04-p10-batch-a-preflight-ai-reserve/progress.md`（含 20+ 条 `Ruling:`） |
| 前端 UI 规范 | `docs/PCS-UI-SPEC.md`（V1.0 冻结） |
| 偏离登记 | `spec/P10 …说明书.md` 第五部分「与仓库现状的偏离登记」**D1~D22** —— 大量「偏离」是**已裁决的刻意取舍**，评审前请先读该节，避免把已裁决项报成缺陷 |

⚠️ **已知 SPEC 版本事实**：计划引用的「P10 SPEC V1.3.1」**在仓库里不存在**；仓库里的 P10 SPEC 实际是 **V1.0**（= 偏离登记 D20）。评审时以仓库实际文件为准。

## Diff 范围

- BASE = `3fae3f6`，HEAD = `55239ff`（18 个提交，全在 `main`，**未 push**）。
- 规模：9059 changed lines / 2567 可执行非测试行 ⇒ `size_band=large` ⇒ **depth=full**。
- 硬阻断类命中：`migrations` ⇒ full review（迁移 `p10_001_ai_audit_request_fields.py` 在范围内）。
- 差异本体：`docs/ce-code-review/20261112-181851-76e48fc4/full.diff`（10431 行）；文件清单：同目录 `files.txt`（61 个文件）。
