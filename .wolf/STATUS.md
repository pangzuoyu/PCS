---
description: session handoff, regenerate with /handoff when a quest finishes
budget_tokens: 1200
---
# STATUS — PCS

> Read this FIRST when starting a session. Last updated: 2026-10-27（P9A-DLV-011 收官批：TODO-077/078/080/087 全闭环）。
> 保持 <2k tokens。历史细节查 `git log` / `docs/` / `TODOS.md` / `.wolf/memory.md`。

---

## ✅ Done

### 第 14 轮：**P9A-DLV-011 收官**（用户指令「顺序解决 TODO-077 · 078 · 080 · 087」）

| commit | 内容 |
|---|---|
| `471f22e` | **TODO-077** —— `apply-change` **要求记录真的改过**（409 `CHANGE_NO_MODIFICATION`；**业务裁决**推翻计划 R-11） |
| `03f9c89` | **TODO-078** —— **多记录变更**：一张变更单关多条记录（`record_ids` + binding 多行 + **全成或全败**关闭） |
| `3e0f093` | **TODO-080 + TODO-087**（见下） |
| `8af2358` | buglog 补 fix_commit |

**TODO-080**（P9A-DLV-007 评审的 3 条 deferred minor）：
1. **取消路径** —— `POST /records/{module}/{id}/change-notice/cancel`（理由必填）⇒ 变更单
   `OBSOLETE`（**不需要迁移**）+ 审计 + 观测 FAILED；⚠️ **记录不动**（保持 CHANGED）——
   作废的是「单据」不是「校核结论」⇒ 顺手关成 CHECKED = **绕过 3 级校审**。
   ⇒ 判重口径改为「**开着** = DRAFT / PENDING」；⚠️ `doc_no`/`scope_value` 改按
   **变更单自己的 uuid** 派生（原先按记录 ⇒ 第二张单撞唯一约束 ⇒ 500）。
2. **真覆盖** —— **删除**已弃用的 `approve_change_notice`（**绕过矩阵**且**连记录都不
   关**）+ 死代码 `_apply_record_resolution`；⚠️ 通知逻辑原只在被删的方法里 ⇒ **真实
   路径从不通知任何人** ⇒ 迁到 `close_on_approved`（同一事务写行，`sign_step` 在
   commit **之后**推）。真库用例搬到 `tests/services/test_change_notice_close_real_db.py`
   （4 例）；`test_change_notice_notification.py` 随之删除（断言并入新文件）。
3. **两个 `PcsError`** —— service 变体**继承** core 变体 ⇒ `except core.PcsError` 两个
   都捕得到；⚠️ core 对 service 的 import 改**惰性**（否则成环）；⚠️ 子类 `code`/`status`
   **必须**取 `type(self).*`（写死 ⇒ 124 个用例的子类退化成 `PCS_ERROR`）。

**TODO-087** —— 撤销/放弃**真的恢复**记录的数据与哈希：快照 `data_snapshot_json` 此前
**恒为 `{}`** ⇒ **只回状态不回数据**。新模块 `app/services/record_snapshot_codec.py`
（UUID/日期/Decimal/枚举**打标签**，恢复时**还原成真类型**；不采主键/归属/审计/状态机
流程列，**但采 `record_hash`**）⇒ 顺带修 `_load_active_snapshot` 的 PK 取法
（`getattr(record,"record_id")` ⇒ 只有部分表叫 `record_id` ⇒ 别的表恒为 None）。

⚠️ **为什么 TODO-080 与 TODO-087 同一个 commit**：TODO-086 的返工用例断言「本次变更前的
哈希 = h1」⇒ 只有快照真的装了数据才**确定性**成立 ⇒ 拆开 ⇒ 历史里留下一个 flaky commit。

**同批更早闭环**：矩阵绑定权限按用户裁决「**只有项目负责人能绑**」（新增项目内角色
`PROJECT_LEAD`，无 DB CHECK ⇒ 零迁移）· ADR-0002 vs ADR-0008 的驳回矛盾（**ADR-0008
管辖**）· 前端缺口 TODO-079（矩阵管理页）+ TODO-083（变更单前端入口）· TODO-084（5 条
minor）· TODO-086（重走后绑定哈希刷新）。

登记：SPEC **V2.10** · `TODOS.md` TODO-077/078/080/087 **闭环** · buglog bug-2070/2076~
2081 · 四份历史计划补「后续」注记 · README 计数 **247 path / 348 schema**。

**验收**：后端 `pytest -q` **5269 passed / 77 skipped / 1 xfailed / 0 failed**；前端
typecheck / lint exit 0、`vitest run` **835 passed / 90 files**；G-08 门禁 4 阶段 exit 0；
裸字段仍 **71**。

---

## 🚀 Next quest

1. **P9B-2**：签署流程前端（操作栏 / 批注 / 状态时间线）+ ADMIN 前端（用户管理 /
   审计日志）+ **两个后端前置**（**TODO-065** `GET /deliverables/{id}/progress`、
   **TODO-066** 按项目守卫的编辑审计读端点）。
   ⚠️ 计划 `docs/PCS-PLAN-P9B-2-签署流程与ADMIN前端.md` **尚未过 `/plan-eng-review`**。
2. **P9B-3**：系统参数前端 + 物流手动创建向导 + 校对 UI。
3. **本批仍开着**：TODO-073（变更单编号走编号模板）· TODO-074（矩阵名唯一约束）·
   TODO-075（`change_resolved_by` 语义与 ADR-0002 冲突）· TODO-076（工作区门禁只覆盖
   本批端点 + 两条 fail-open 分支）· **TODO-082**（`locked_by_deliverable` 死闸门）·
   **TODO-085**（矩阵修改的申请 + 双审）· **前端缺「作废变更单」按钮**（后端已就绪）。
   ⇒ TODO-077/078/079/080/083/084/086/087 **已闭环**。
4. **ADR-0050**：用户 2026-10-20 裁决「先不做」⇒ 再开工按 P1~P6。
5. **P9A-1 遗留**（未变）：access token 不带 `tv`；AD 同步需运维服务账号。

---

## Context

- main，工作区干净。**不要建 worktree**（历史事故）。
- 两库均在 **`p9_008`**（head）· `alembic check` 两库各 exit 0（退出码 **255** = 真漂移；
  先 `current` vs `heads`；`pcs_test` 的 URL 从 `.env` 派生，**不要把口令写在命令行**）。
- ⚠️ **CI 现在是活的**（`.github/workflows/check-api-drift.yml`，全新 Postgres）⇒ 改了
  迁移必须**在全新库上验**（本机用隔离 schema：`options=-csearch_path=<schema>`；URL 里
  **不能有 `%`**）。
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

- **「恢复快照」要有数据才叫恢复**：快照只存哈希 ⇒ 恢复循环空转 ⇒ 撤销**只回状态**。
  ⇒ 快照要装**数据**，且 JSONB 装不下的类型（UUID/日期/枚举）要**打标签**再还原
  （裸字符串绑枚举列会 LookupError）。
- **主键列名不能靠猜**：`getattr(record, "record_id")` 只在部分表成立 ⇒ 别的表**恒为
  None** ⇒ 查不到 ⇒ 静默空转 ⇒ **按 mapper 取**，或**由调用方传入**。
- **子类的默认属性要用 `type(self).*`**：写死 `code`/`status` ⇒ 所有子类退化成父类
  的值 ⇒ 124 个既有用例同时红。
- **两个同名的异常类要合并成一个继承链**：否则 `except` 捕不到 ⇒ 业务错误落 500。
- **一条 commit 要确定绿**：若 A 依赖 B 才能让既有用例确定通过 ⇒ 合并落地，别拆。
