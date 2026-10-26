---
description: session handoff, regenerate with /handoff when a quest finishes
budget_tokens: 1200
---
# STATUS — PCS

> Read this FIRST when starting a session. Last updated: 2026-10-27（P9A-DLV-011 **欠账清理批**：TODO-073/074/075/076/082/085 + 前端接线 + 快照加固）。
> 保持 <2k tokens。历史细节查 `git log` / `docs/` / `TODOS.md` / `.wolf/memory.md`。

---

## ✅ Done

### 第 15 轮：**P9A-DLV-011 欠账清理批**（用户「顺序解决 1-4 未解决问题」）

| commit | 内容 |
|---|---|
| `5416e5f` | **TODO-073** —— 变更单编号走**编号模板**（可读 `{项目号}-CHANGE_NOTICE-{序号}`）+ 迁移 **`p9_009`** |
| `e8d34c8` | **TODO-074** —— 矩阵**同名同状态**不许两份（应用层 409 + 迁移 **`p9_010`**） |
| `334e140` | **TODO-075** —— `change_resolved_by` **只由「关记录」那步**写（语义对齐 ADR-0002） |
| `4487475` | **TODO-076** —— 工作区门禁覆盖 UI-SPEC §5.3 **全部四类**操作 + 两条放行分支**钉住** |
| `50c3e28` | **TODO-082** —— 两道「已对外生效」的门换成**真实可判定**的条件（APPROVED 的交付物绑定） |
| `6febab1` | **TODO-085** —— 矩阵修改的申请+双审：**本项目不做**（业务裁决，写进校审层级 SPEC **V1.2**） |
| `30df88e` | **前端「作废变更单」入口**（+ 后端读口 `GET .../change-notice`） |
| `a551fc1` | 快照列清单改成**从 mixin 自动推导**（顺手修掉漏网的 `approval_depth`） |
| `66dba93` | 批末用例迁移 + 顺带修 **audit `resource_id` 恒空串**（bug-2088） |

**两处业务裁决（用户 2026-10-27）**：①「已对外生效」的门 ⇒ 换成**真实可判定的
条件**（不再用那个**从不被写**的 `locked_by_deliverable` 列）⇒ **已知代价**：变更单
批准后该记录不能再走普通撤销（只能走 CHANGE_REVERSAL）；②矩阵修改的**申请+双审**
⇒ **本项目不做**（PCS 没有「项目级覆写」对象 ⇒ 该规则当前**没有适用对象**）。

**顺带发现并修掉的真缺陷**：`record_cancellation_service` 的审计 `resource_id` 用
`getattr(rec, "record_id", "")` ⇒ 各表**主键列名不同** ⇒ **恒为空串** ⇒ 审计链断
（bug-2088，与 bug-2081 同族）。

**验收**：后端 `pytest -q` **5292 passed / 77 skipped / 1 xfailed / 0 failed**；
前端 typecheck / lint exit 0、`vitest run` **840 passed / 91 files**；G-08 门禁 4
阶段 exit 0（**247 path / 349 schema**，裸字段仍 **71**）；两库 `pcs` / `pcs_test`
均在 **`p9_010`**（head）· `alembic check` 各 exit 0。

### 第 14 轮：**P9A-DLV-011 收官批**（TODO-077/078/080/087 全闭环）

- `471f22e` **TODO-077**（`apply-change` 要求记录真的改过）· `03f9c89` **TODO-078**
  （多记录变更）· `3e0f093` **TODO-080 + TODO-087**（取消路径 / 真覆盖 / PcsError
  统一 / 撤销**真的恢复**数据与哈希）· `8af2358` `a3e9c9c` buglog + STATUS。
- 登记：SPEC **V2.10** · `TODOS.md` TODO-077/078/080/087 **闭环** · buglog
  bug-2070/2076~2081。

---

## 🚀 Next quest

1. **P9B-2**：签署流程前端（操作栏 / 批注 / 状态时间线）+ ADMIN 前端（用户管理 /
   审计日志）+ **两个后端前置**（**TODO-065** `GET /deliverables/{id}/progress`、
   **TODO-066** 按项目守卫的编辑审计读端点）。
   ⚠️ 计划 `docs/PCS-PLAN-P9B-2-签署流程与ADMIN前端.md` **尚未过 `/plan-eng-review`**。
2. **P9B-3**：系统参数前端 + 物流手动创建向导 + 校对 UI。
3. **本批仍开着**：
   - **TODO-088** —— 在**隔离 schema** 上跑迁移会**漏建** 6 条约束（p8_001/p8_008/
     p8_009 的幂等检查**只按名字**查 `pg_constraint` ⇒ 不分 schema）⇒ 那个 schema
     上的 `alembic check` 报 6 条**假漂移** ⇒ **别照字面「修」**。
   - **TODO-089** —— 两个 `PcsError` 变体只统一了一半：`except service.PcsError`
     **捕不到** core 变体抛出的错误 ⇒ 全仓 55 处 `except` 是潜在漏网 ⇒ 彻底修 =
     合并两个类。
   - **TODO-090** —— `locked_by_deliverable` 列现在既无写入方也不是门禁 ⇒ 写它
     （审计标记）还是删列（16 张表 + 字典）。
   - **TODO-073~076 / 079~087** ⇒ **已闭环**；**TODO-077/078/080/082/085** ⇒ 已闭环。
4. **ADR-0050**：用户 2026-10-20 裁决「先不做」⇒ 再开工按 P1~P6。

---

## Context

- main，工作区干净。**不要建 worktree**（历史事故）。
- 两库均在 **`p9_010`**（head）· `alembic check` 两库各 exit 0（退出码 **255** = 真
  漂移；先 `current` vs `heads`；`pcs_test` 的 URL 从 `.env` 派生，**不要把口令写在
  命令行**）。
- ⚠️ **CI 现在是活的**（`.github/workflows/check-api-drift.yml`，全新 Postgres）⇒ 改了
  迁移必须**在全新库上验**（本机用隔离 schema：`options=-csearch_path=<schema>`；URL
  里**不能有 `%`**）—— ⚠️ 该 schema 上有 6 条**假漂移**（TODO-088）。
- **Redis**：跨进程/锁的测试需要真 Redis（`docker compose up -d redis`）。
- 契约：批末滚 `pcs-backend/docs/openapi-baseline.json`（前端 snapshot / api.d.ts 由
  `gate_08_openapi_contract.sh` 重生成）⇒ 本批已滚。
- 提交约定：conventional commits，**无 attribution 行**；长消息写文件后
  `git commit -F <file>`。
- ⚠️ **API 测试的 `client` fixture 把 `check_user_project_access` mock 成恒 True** ⇒
  **项目授权（404）在 API 测试里测不了** ⇒ 要测 404 必须用 `_guard_client`。
- ⚠️ **in-memory SQLite 的 StaticPool 让 `db` 与独立 client 共用同一条连接** ⇒ 独立
  client 退出时的 rollback 会把 `db` 这边**未提交**的 INSERT 一起回滚 ⇒ 造完 fixture
  必须先 `await db.commit()`。

---

## 教训（本批新增，已进 cerebrum）

- **判据要用「真实可判定」的条件**：拿一个**从不被写**的列当门禁 ⇒ 门永远不
  触发 ⇒ 那条业务约束**事实上不存在**（且没人发现）。
- **主键一律用「调用方传入的那个」**：`db.get(table, pk)` 的 `pk` **就是**主键 ⇒
  不要从对象上「猜」列名（各表列名不同 ⇒ 猜错 ⇒ 静默返回空 ⇒ 审计链断）。
- **手写清单不是断言**：快照的「不采哪些列」手写 ⇒ 忘了加就**没有任何测试会红**
  ⇒ 改成**从 mixin 自动推导** + 一条**守卫测试**（漏了 ⇒ 变红）。
- **唯一约束会揭露「同名」的测试**：加约束后测试红了 ⇒ 那是测试**依赖了非法状态**
  ⇒ 改测试（名字逐条不同），不是改约束。
