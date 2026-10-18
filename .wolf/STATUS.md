---
description: session handoff, regenerate with /handoff when a quest finishes
budget_tokens: 1500
---
# STATUS — PCS

> Read this FIRST when starting a session. Last updated: 2026-10-19.
> 保持 <2k tokens。历史细节查 `git log` / `docs/` / `TODOS.md` / `.wolf/memory.md`。

---

## ✅ 本会话完成

**P8 评审的 30 条 findings 全部处理完毕**（`c9d937f` → `6448041`）。

1. **#24 MSW 契约冻结**（`346c257`）：30 个 mock 端点里 **23 个有契约**、
   7 个刻意 mock-only（方法级匹配，路径级会多算一个）。全部用生成的
   OpenAPI 类型标注 → `tsc` 一次跑出 **5 处真漂移**（checklist
   completeness 字段整组不同、vessel/sep-equip 返契约里一个都没有的字段、
   `formula_ref` 塞 boolean、Workspace 手写类型缺必填 `status`）。
2. **#19 输出格式白名单**（`c142014`）：报告说「两份」，实际**四份**，
   且其中一份注释写着「取自 EXPORT_FORMATS」而代码是硬编码字面量；
   另有第五处 `_MEDIA` 缺 csv 且**静默兜底**成 octet-stream。全部合到
   `watermark.EXPORT_FORMATS` 一处。
3. **#22 #21 #29**（`2a23d2e`）：并发冲突的 `db.rollback()` 改 SAVEPOINT；
   审计缺口改 ERROR + 点名 file_id；验签密钥加 32 字节下限。
4. **#27 状态筛选**（`81947bd`）：后端加 `status` 查询参数（未知词 400、
   `status=OBSOLETE` **不翻出**已作废定义）+ 前端删虚构的 `report_type`
   + MSW 同步遵守该参数。
5. **#10 #30 #26**（`e35ecfc`）：定义拉换取消失效机制；缺 `source` 不再伪造
   `EQUIP_LIST`（含计数器同步）；过滤条件行改用 `node.id` 当 key。
6. **产物更新**（`e46caee` / `6448041`）：评审 README 补「修复落地状态」；
   buglog 补 bug-180..183；新增 solutions 一篇 + cerebrum 两条。

### 🔴 #24 引出的**生产缺陷**（未修，bug-180）

`mocks/seed/pipe-classes.ts` 返 `{pipe_class_id, code}`，契约
`PipeClassResponse` 是 `{class_id, class_name, material_standard, ...}`
—— **字段名整组不同**。`PipeClassListPage` 读 `record.pipe_class_id`
（`rowKey` 也用它）、`PipeComputePage` 下拉用 `{value: p.pipe_class_id,
label: p.code}` ⇒ 真后端下全是 `undefined`。
**管道等级页在生产上就是坏的，是这份 mock 一直在替它遮着。**

未修：改它要动页面 + `types/pipeClass.ts` = **TODO-039 前端类型唯一性**。
已在 `mocks/seed/pipe-classes.ts` 留注释指向评审 README 的对应节。

---

## 🚀 Next quest

1. **管道等级页（bug-180）** —— 上条。这是本会话查出的唯一**生产级缺陷**，
   而非仅 mock 脏。做法同 TODO-039：把手写 `types/pipeClass.ts` 并到
   生成的契约类型，页面跟着改字段名。
2. **`scripts/check-api-drift.sh:64`** —— docstring 声称能检出属性类型
   变更/删除，实际只比 `required` 数组。本会话 5 处漂移里 4 处它看不见。
3. **P9 起步**：`report_verify_base_url` 未配置 ⇒ 二维码当前默认不印
   （`#4` 的修复已就位，配置后生效）；`assemble` 真分批；TODO-026（JSONB 子键平铺）。
4. 低优先数据层：TODO-028（10 表主键 rename）、TODO-032（27 个真库测试迁 SQLite）。

---

## Context

- main，工作区除 `.wolf/*`（钩子维护）外干净。**不要建 worktree**（历史事故）。
- **两库均在 `p8_010`，`alembic check` 均 exit 0**。`pcs_test` 是行为验证库。
- 基线：后端 **4516 passed / 0 failed**，前端 **637 passed / 0 failed**，
  两端 lint / typecheck clean。本会话共 +21 条后端 / +12 条前端测试。
- 改迁移的纪律：`alembic check` 退出码 **255**；先 `current` vs `heads`
  确认它跑了；**每个库各跑一次**；行为验证上真库。
- 无 CI/CD（单人开发裁决，勿再建议）。

---

## 教训（本会话新增，全文见 solutions 一篇）

- **守门测试会被它守护的那行注释骗过**：`inspect.getsource()` 找子串证明
  「A 引用了 B」，会被 A 上面那句**说谎的注释**命中。同类：用
  `str(stmt.whereclause)` 当判据恒不命中 ⇒「功能从未执行」被读成
  「测试通过」。⇒ 断言要打在 AST / 对象身份 / 调用序数上。
- **mock 与契约一致是正确性的一部分**，不是开发体验问题 ——
  mock 越宽松，它替页面扛的越多，而差异平时不可见（bug-180）。
- **评审说的份数要重数**：本次 N → N+1，且新增的那份注释在说谎。
- 注释里出现「已消除」「唯一来源」「覆盖」时，当成待验证的代码事实。
- 断言在修复落地前可以只是**探针**：跑出发现，不成立处换成文档注释，
  别留一个红 `tsc` 把构建变红。

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
