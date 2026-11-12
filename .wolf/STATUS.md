---
description: session handoff, regenerate with /handoff when a quest finishes
budget_tokens: 1200
---
# STATUS — PCS

> Read this FIRST when starting a session. Last updated: 2026-11-12（第 28 轮：**P9B-4 评审修复批 19 条 finding 全闭环**，已推送 `origin/main` `4f21baa`）。
> 保持 <2k tokens。历史细节查 `git log` / `docs/` / `TODOS.md` / `.wolf/memory.md`。

---

## ✅ Done（第 28 轮：P9B-4 评审修复批 —— 19 条 finding 全闭环）

用户「开始按队列修复」⇒ 把 `ce-code-review`（`docs/ce-code-review/20261111-181548-7b8a5dca/`
+ `hermes` GLM-5.2 跨模型对抗审查）的 **19 条** finding 全部落地（TDD 红→绿）。
**4 条用户裁决**：血缘角色 = 沿用 streams 白名单 · 停用覆盖面 = **全部补齐**
（WS 投递复检 + `current_user` 也判）· CSV 导出 = 加「引用」列 · 批末重跑浏览器回归。

分组（**逐条台账见 `TODOS.md` 末节**）：`#1` 前端 `USER_DISABLED` 登出 · `#3` 血缘角色门 ·
`#4` 一行一种表示（三端点统一 `LineageNode`）· `#6` WS 投递复检 · `#7` 握手非 `PcsError` 兜底 ·
`#8` 部署闸门**另看路由表** · `#9` 登记 `PsvResult` + **不依赖 `RECORD_TYPE_REGISTRY`** 的
契约测试 · `#10` 停用判定共享谓词 + 源码扫描棘轮 · `#11` 逐字同形 404 钉住 · `#13` 账簿
「合并」→「覆盖」· `#14`/`#26` docstring · `#15` 消费守卫返回值 · `#16` `current_user` 也判
账号状态 · `#20` 刷新失败≠提交失败 · `#23` 删除门禁补下游物流 + `IntegrityError`→409 ·
`#24` WS 拒绝原因只对日志可见 · `#25` 并发首登撞唯一约束 ⇒ 回滚重读 · `#27` 导出含「引用」列。

**实测**：后端 **5662 passed / 77 skipped**（+39）· 前端 **116 files / 1053 tests**（+7）·
PG 车道 5 passed · 裸载荷 **71 未涨** · 契约门禁 drift 一致 · **零迁移**
· **批末浏览器回归重跑**（#2 指出的缺口：上份报告跑在批末前两个提交上）⇒ 8 路由全绿 ·
控制台 0 error · 网络 0×404/0×500 · **导出实测含「引用」列**且与表里 📎N 逐条一致 ·
血缘 Tab 时间戳已是 `Z`。⇒ **已推送**（16 提交 · ahead 0）。
**两条诚实边界入 TODO-144 / TODO-145** ⇒ 台账见 `TODOS.md` 末节 + SPEC **V2.16** + ADR-0046 §⑤。

⚠️ 本轮**未改 `alembic/versions/*`** ⇒ 两库仍在 `p9_015`，本批没碰过。

**更早的轮次**（细节查 git log / `.wolf/memory.md`）：第 27 轮 P9B-3b 评审 Minor 全闭环
（TODO-121~127 · `00aae19`）· 第 25~26 轮 P9B-3b 批量「提交校对」（计划
`docs/superpowers/plans/2026-11-03-p9b-3b-batch-submit.md` + ledger
`.superpowers/sdd/2026-11-03-p9b-3b-batch-submit/progress.md`）。

---

## 🚀 Next quest

1. **下一 quest 待用户定**：P9B-4 剩余的批量操作交互收口，或 P9B-3c。
   起点线索：`docs/PCS-PLAN-P9B-3-系统参数与SIM物流前端.md` 的「P9B-3b 移交」节已全部落地 ⇒ 该节可标「已完成」。
2. **下一轮 ce-code-review**：scope **必须**含 TODO-100 点名的三处未深审部分
   （`test_deliverable_issue.py` + deliverables/record_edits API 改动 + 其余 diff）。
3. 开放 TODO：**091-115 + 116/118/119/120**（**121~127 / 134 已闭环**；099/101/102/103 已关闭）；
   **144 / 145**（本轮新增的两条诚实边界）；57 手写类型长期债；ADR-0050「先不做」。
   ⚠️ **TODO-118（🔴）是刻意接受的越权缺口**（批次端点与六个写端点同口径，只做角色校验）
   ⇒ 批次把越权成本从「100 次请求」降到「1 次扫荡」；TODO-113/114 是**读面**的同类缺口。
4. **未跟踪的 6 个遗留文件**（`docs/superpowers/plans/2026-09-30-*.md` ×5 +
   `spec/PCS-SPEC-P10 V1.3.1….md`）—— 非本会话产出，处置由用户定。

---

## Context

> ⚠️ **迁移 / PG 车道 / 裸载荷基线 / 发布前检查** ⇒ 见 `CLAUDE.md`（§测试前检查、§发布前检查）⇒ **不重复**。

- main。**不要建 worktree**（历史事故）· **不要 `git checkout <commit> --detach`**。
  **不得擅自 push**（用户明确要求才推）。`.wolf/*` 由 hook 自动维护，别手工 revert。
- 提交约定：conventional commits，**带** `Co-Authored-By: Claude Code` 行；长消息写文件后 `git commit -F`。
- ⚠️ **全量 pytest 前先 `docker compose up -d redis`**；**别信 `pytest | tail` 的退出码**。
  ⚠️ **满负载会假红**：`test_notification_list_budget.py` 的 500ms 墙钟预算 ·
  本轮 `project_admin.test.tsx` 假红 1 条 ⇒ **单跑 + 全量重跑**确认后再判定，别直接改代码。
- ⚠️ **FastAPI 0.141 懒挂载** ⇒ `app.routes` 里 include 进来的 router 是**没有 `path` 的包装对象**
  ⇒ 遍历一层会漏整棵子树 ⇒ 判「挂没挂」要**递归展开**（鸭子类型 `original_router` + prefix 累加）。
  ⚠️ **只看 `app.openapi()["paths"]` 也不够** ⇒ `include_in_schema=False` ⇒ 路由照挂但 schema 隐身。
- ⚠️ **`RECORD_TYPE_REGISTRY` 是「表枚举」不是「写入方清单」** ⇒ 拿它当守卫注册表的基准 ⇒
  漏登记的类型**永远测不出来**（`PsvResult` 曾因此永久 404）⇒ 契约测试要用**独立判据**。
- ⚠️ **「一处判定」通常指「一处比较」** ⇒ 查表键不同往往是**刻意的**（登录只有 username）
  ⇒ 处置是**共享谓词 + 如实写 docstring**，不是硬统一查表键。
- ⚠️ **`TestClient` 把 accept 前的 WS close 还原成 `WebSocketDisconnect(1008)`** ⇒
  测试观察到的拒绝语义**在部署里不存在**（真实是 HTTP 403）⇒ TODO-144。
- ⚠️ 前端 e2e / 浏览器 QA：`page.goto` / `browse goto` / `reload` 会清 zustand（内存态）
  ⇒ 路由可达性走 **SPA 菜单点击**；⚠️ `browse snapshot` 的 `@eN` **每次导航后失效**
  ⇒ 每次点击前重新 snapshot 取 ref；⚠️ `browse click @eN` 对 antd 表格复选框会解析成
  表头「Select all」⇒ 勾选改用 `js` 点 DOM + Playwright 交叉验证 ⇒ **别当应用 bug**。
- ⚠️ **axios 用 `window.location.href` 解析相对 URL** ⇒ 桩 `location` 时 `href` 必须是**绝对 URL**。
  ⚠️ **jsdom 的 `Blob` 没有 `.text()`** ⇒ 用 `FileReader`。
- ⚠️ **PG 行锁只在 COMMIT/ROLLBACK 时释放** ⇒ 任何 `SELECT ... FOR UPDATE` 之后的
  **提前返回**路径**必须先结束事务** ⇒ 否则锁跨条目累积 ⇒ 真死锁（bug-2135）。
  ⚠️ 只读事务要结束用 **`commit()`** 不用 `rollback()`（后者 expire 掉所有实体 ⇒ async 下炸 `MissingGreenlet`）。
- ⚠️ **改字段名/删字段的批次 ⇒ `rowKey` 必进改名单**（bug-180 漏改 ⇒ 每行 key 都是 `undefined`；
  棘轮 `tests/pages/rowKey_contract.test.ts` 会红）。⚠️ 允许集**必须**含手写类型字段 ⇒ 否则误报合法 rowKey。
- ⚠️ **布尔不是数字**：`int(True) == 1` ⇒ JSONB 里的 `true` 会静默变成上限 1
  ⇒ `int()` 之前先 `isinstance(x, bool)` 排除（**异常兜不住**）。
- ⚠️ 契约缺口（裸 dict）：`CreateStreamRequest.payload`、state-points body、properties/state-points/
  lineage graph 响应 ⇒ 前端手写本地类型 ⇒ **字段名无编译期约束**（TODO-110/111）。
- ⚠️ **子代理 Bash 会挂起** ⇒ 派发审阅/实现子代理**只给 Read/Grep**。

---

## 教训（**已进 cerebrum**，此处只留最新两条）

- **守门自己的 docstring 也要被验** ⇒ 「检测 X」不等于检测了 X（`check-api-drift.sh` 教训）。
- **「一处实现」要分清「一处比较」与「一处查表」** ⇒ 查表键不同常常是刻意的。
⇒ 其余历史教训查 `.wolf/cerebrum.md` 的 Do-Not-Repeat。
