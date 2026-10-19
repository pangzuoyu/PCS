---
description: session handoff, regenerate with /handoff when a quest finishes
budget_tokens: 1500
---
# STATUS — PCS

> Read this FIRST when starting a session. Last updated: 2026-10-19（第 2 轮）。
> 保持 <2k tokens。历史细节查 `git log` / `docs/` / `TODOS.md` / `.wolf/memory.md`。

---

## ✅ 本会话完成

### 第 1 轮：P8 评审闭环 + 类型唯一性起步

**P8 评审 30 条 findings 全部闭环**（`c9d937f` → `5b1174c`），顺带查出两个生产级缺陷：
bug-180 管道等级页生产空白（`09a2a88`）、bug-184 契约闸门 docstring 声称三项检测
实现零项（`5b1174c`，10s → 0.145s）。

### 第 2 轮：一个病族，四个实例

起因是「改一个类型前要先定位权威在哪」。查权威时挖出一条链：

**契约里词表没进类型 → 客户端只能猜 → 猜错 → 生产上静默错。** 本轮修了四处：

| bug | 现象 | 根因 |
|---|---|---|
| 187 | 管号等级全显示「未知状态: PUBLISHED」 | 前端的 3 态词表**抄自后端 docstring 的一句错话**；真因是后端**两套状态机并存**（4 个端点走 `ConfigStatus` 5 态，`PUT` 里跑着 1.9 遗留的 `DRAFT→ACTIVE→OBSOLETE`，而 `ACTIVE` **没有任何路径会产生**） |
| 188 | 资产「审批」按钮永远点不动 | `AssetResponse.status` 裸 `str`，词表**只写在 description 文字里** —— 「读文档的人是对的，读契约的代码是错的」 |
| 189 | 物流详情页生产白屏 | 前端把响应包装成自造的 8 件套 payload，后端返的是扁平 `StreamResponse`，且那 7 块**根本没有端点** |
| 190 | 类别过滤 tab 生产一档都不命中 | `category` 用了六个语义名，DB CheckConstraint 只允许 `CATEGORY_1~6`；`updated_by`/`hash`/`tags` **表里根本没有** |
| 191 | Stream 四词表进契约 | 四个字段都是裸 `str`；且 description 本身不可信（`sign_status` 写 4 态实际 9 态、`source_type` 写 5 个实际 13 个） |

**ⓘ 两道编译期闸已补齐**：
- `StrictColumns<T>`（`src/types/strictColumns.ts`）把 antd 的 `dataIndex`
  收成行类型的 key，18 个页面全部替换 ⇒ bug-180 的形态现在编译期即拒。
- `StreamPhase` 等词表改用契约类型 + **双向编译期断言**。
- ⚠️ 两道闸都写了**自检**（`@ts-expect-error` + 真实契约类型）——
  第一版 `DeepKeys` 因 JSONB 索引签名塌成 `string` 而**完全失效**，
  探针用的是干净 interface 所以没发现。**闸的自检必须用真实类型。**

- **`tests` 已纳入 tsconfig**（此前 675 条测试的类型标注全是装饰性的）。
  7 条噪声清完，**探针验证过边界**：抓得住属性访问与漏必填，
  **抓不住 antd `dataIndex`**（TODO-041）。
- **`Stream` 并进契约**后 tsc 立刻挖出 3 个真生产崩溃（可空字段被当非空用）。
- **新增守门**：`handlers.test.ts` 的「响应体 ↔ OpenAPI」ajv 组 —— 既有那条只验
  **路径**一致性，mock 多返一层 `.stream` 全绿通过。
- **TODO-040 补完**：`GET /config/assets` 从未实现（前端跑在前面），已补并接回。

## ✅ 基线

后端 **4516 passed / 0 failed**，前端 **677 passed / 0 failed**，
两端 lint/typecheck clean。`check-api-drift.sh` → OK / exit 0（test 1–9 全过）。

---

## 🚀 Next quest

1. **P9 起步**：`report_verify_base_url` 未配置 ⇒ 二维码默认不印；`assemble` 真分批。
2. **两件多日工程，别当小任务排**：
   - **TODO-026**：9 张结果表里 8 张仍是 `input_json`/`output_json` 简化容器，
     照 `CoolingTowerResult` 的 14 子结构铺开 ≈ **100+ 个子结构** + 迁移 + 契约 + 测试；
   - **TODO-032**：条目写 4 个文件，**实测 29 个**用真 PG（`get_async_session_factory`）。

✅ **TODO-028 已于 2026-10-08 核实关闭**（主键已是 DICT V3.3 短名，`*_calc_id`
残留 0 个，`alembic check` exit 0）—— 此前 STATUS 里挂着是陈旧引用，已移除。

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
