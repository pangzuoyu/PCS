---
description: session handoff, regenerate with /handoff when a quest finishes
budget_tokens: 1500
---
# STATUS — PCS

> Read this FIRST when starting a session. Last updated: 2026-10-19.
> 保持 <2k tokens。历史细节查 `git log` / `docs/` / `TODOS.md` / `.wolf/memory.md`。

---

## ✅ 本会话完成

**TODO-039 前端类型唯一性** —— 把「手写副本 vs 契约」从一次性排查变成可复跑的
`scripts/audit-handwritten-types.mjs`（`npm run api:audit-types`），随后按
contracts 逐项收敛：

1. **`PipeClass` 并进契约** —— bug-180，生产整页空白（`09a2a88`）。
2. **`Stream` 三处漂移一次改掉**（`6a94109`）：
   - 删 `tag_number`（物流无位号，那是 `TaggedRecordMixin` 给计算记录的字段），
     首列与详情页标题改 `stream_name`；
   - 相态收敛为契约四值：**砍 AQUEOUS**（前端发明，三处零命中）、
     **补 SOLID**（`import_service._phase_norm` 真产出，砍掉则固相渲染成空标签）；
   - `AssetListRoute` 停止请求**契约里不存在**的 `GET /api/v1/config/assets`，
     并删掉那个替缺陷遮着的 mock handler。
   两条相态回归测试**做了 mutation 验证**（标签改 undefined 即红）。
3. **`press` 单位**：契约描述原写 kPa，DICT 源字段是 `pressure_mpag` ——
   差 **1000 倍且看起来完全合理**。改后端 schema + ORM `comment="MPaG"`。
4. **`check-api-drift.sh`**：docstring 声称三项检测、实现零项（bug-184）；
   10s → **0.145s**；补字段删除/类型变更/enum 值删除三项检测。

## ✅ 基线

后端 **4516 passed / 0 failed**，前端 **677 passed / 0 failed**，
两端 lint/typecheck clean。`check-api-drift.sh` → OK / exit 0（test 1–9 全过）。

---

## 🚀 Next quest

1. **把 `tests` 纳入 tsconfig**（已实测：**9 条错 / 7 个文件**，一次性可修）。
   其中 2 条是真信号（fixture 与契约脱节）。本轮未修 —— 保持 main 绿。
   修完这道闸才立得住：**「代码用了契约里没有的字段」目前无任何自动化**。
2. **`StreamDetailPayload`（C 类，用户已批准单独排期）** —— 手写侧是 7 个东西的
   合成体，契约侧是单个 `StreamResponse`，**结构不同源**，改字段名解决不了，
   要先定后端响应形状。
3. **契约侧缺口**：`PipeClassResponse.status` 是裸 `str`，没 `Literal` ——
   词表没进契约，客户端无法枚举（与评审 #28 同类）。
4. **P9 起步**：`report_verify_base_url` 未配置 ⇒ 二维码默认不印；
   `assemble` 真分批；TODO-026（JSONB 子键平铺）。
5. 低优先：TODO-040（`GET /api/v1/config/assets`）、TODO-028、TODO-032。

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

- **改类型前先定位权威**：契约 → **对应实体的**字典 → 后端实际行为
  （含 parser）→ SPEC（可能过时）。查 tag_number 时必须按实体找字典文件，
  否则会被「其他 spec 里到处都是它」误导。
- **不要「承认多套词表各自成立」** —— 那是把同一个概念分成三份，比任一份错都糟。
- **缺端点 ≠ 缺字段**。端点缺失时 `git log -S` 能确认是「从未实现」还是回归；
  止血要**连 mock 一起删**，否则它继续替缺陷遮着。
- **不在类型检查里的类型 = 没写的类型**。实测才知道代价（9 条而非 675）——
  **先量再决定，别凭感觉评估**；但量出来的错里真信号常占二成，
  那二成说明整批 fixture 不可信。
- **fixture 与被测对象不是同一份来源 ⇒ 零信号**（bug-180 的 6 条绿）。本轮两个
  SIM fixture 同样如此：带 `subphase`/`approved_hash`/`tag_number`，全绿。

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
