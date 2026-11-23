# TODOS.md — PCS 延后工作清单

> **2026-10-06 全量核销重写。** 原文件 46 条积压自 2026-08，状态字段写的是「P1 Sprint 2」这类时间锚，
> P1–P7 全部收口后已完全失去意义，且无一条被勾销 —— 越堆越长、越不敢看。
> 本次对每条做只读实证核验，判定依据为 `文件:行号`，见每条「证据」。

## 判定图例

| 标记 | 含义 |
|---|---|
| 🔴 **OPEN** | 确实还没做 |
| 🟡 **PARTIAL** | 做了一半 |
| ⚪ **BLOCKED** | 宿主模块未开工 / 等外部方，暂不可动 |
| ✅ **DONE** | 已落地（**不要按原文重做**——多条实际路径与条目描述不同） |
| 🚫 **WONTFIX** | 已被产品/架构裁决关闭，**改回去会破坏既有契约** |
| ♻️ **STALE** | 描述已过时，任务本身失去意义，需重新裁决而非照做 |

**维护规则**：新增条目必须带 `证据` 字段；关闭条目移到文末归档表，不要删（编号是追溯索引）。
最后全量核销：2026-10-06。

> **2026-11-23 瘦身**：本文件曾到 **5653 行 / 210 KB** ⇒ ⇒ **已关闭**的 98 条整体搬进 **`docs/archives/TODOS-closed.md`**（正文逐字保留 · **编号可追溯**）⇒ ⇒ 本文件只留**还开着**的条目。
⇒ ⇒ 搬运由 `scripts/slim_todos.py` 完成（可复跑 · 判定口径写在脚本 docstring 里）。

## 📋 还开着的条目（**一眼看完**）

⚠️ **正文里只有还开着的条目**（76 条）⇒ ⇒ **已关闭**的 98 条在 `docs/archives/TODOS-closed.md`（编号可追溯 ⇒ ⇒ 文末有「已关闭」索引表）。

| 编号 | 严重度 | 条目 |
|---|---|---|
| `TODO-032` |  | 真库测试文件迁 conftest SQLite fixture |
| `TODO-035` |  | 物流校验规则 22 条补全 —— ♻️ 描述与实现脱节，先定扩展点 |
| `TODO-026` |  | P5 模块平铺字段 / data_sheet_json 展开（9/10 未做） |
| `TODO-029` |  | CIA 传播性能预算测试 |
| `TODO-034` |  | Excel 导入模板版本管理 |
| `TODO-016` |  | ARQ 失败注入 + DLQ 测试 |
| `TODO-017` |  | P4 接入验收 e2e 从 1 扩到 4 |
| `TODO-039` | 🔴 | + TODO-041: 前端类型来源唯一性 + MSW 契约冻结（🔴 逾期 ~20 天，**2026-10-08 已重定范围**） |
| `TODO-040` |  | PIPE_NET 完整版（reactflow / 布局 / 环路检测 / 序列化） |
| `TODO-044` |  | Per-Batch QA Gate —— ⚠️ 闸门写在了错误的层级 |
| `TODO-014` | 🟡 | 设备联动「设备同步中」前端标记（🟡 PARTIAL） |
| `TODO-015` |  | lineage_ctx 事务回滚清理语义文档化 |
| `TODO-023` |  | 计算函数签名约定写入 CLAUDE.md |
| `bug-190` |  | `ConfigAsset` 的 category / updated_by / hash / tags 全是前端编的 |
| `TODO-045` | 🟡 | `StrictColumns` 的数组形式不校验「段间路径」（🟡 已知边界，2026-10-19） |
| `TODO-046` | 🟡 | 其它表的裸串词表尚未系统排查（🟡，2026-10-19） |
| `TODO-055` |  | `RECORD_TYPE_REGISTRY` 的键风格不统一（P9A B4a 登记） |
| `TODO-056` |  | `NumberingTemplate.segments_json` 的 ORM 标注是错的（`Mapped[dict]`） |
| `TODO-060` |  | （原）: `record_type` 存在两套词表（类名 vs 表名） |
| `TODO-062` | 🟡 | `cia_engine.REGISTRY` 是 `record_type` 的**第 6 套词表**，且自相矛盾（🟡） |
| `TODO-063` | 🟡 | 迁移幂等守门的**遗留盲区**：`p1`~`p6` / `p8` 共 93 个文件从未被检查（🟡） |
| `TODO-064` | 🟡 | 全仓 **57 个**手写类型与生成契约 schema 同名（🟡 长期债，已有棘轮守卫） |
| `TODO-091` | 🟡 | `project_templates.record_approval_config` 作废（**只有注释、无消费方**） |
| `TODO-092` | 🟡 | ADMIN「角色分配」没有后端端点 |
| `TODO-093` | 🔴 | `sign_step` 并发无行锁 —— 两个签署者同时签，**后写的把先写的签名覆盖掉** |
| `TODO-094` | 🔴 | 二次认证接受**任意** AD 凭据，不校验「就是操作者本人」 |
| `TODO-095` | 🟢 | `GET /deliverables?sign_status=` 接受任意字符串 |
| `TODO-096` | 🟢 | 新工作流业务错误码未在 OpenAPI `responses=` 声明 |
| `TODO-097` | 🟢 | MSW edits mock 忽略 `limit/offset` |
| `TODO-098` | 🟢 | `deliverable_service.py` / `mocks/handlers.ts` 超 800 行上限 |
| `TODO-100` | 🟢 | 下一轮 review **必须**覆盖的未深审部分（复审追问 2） |
| `TODO-105` | 🟡 | `streams.source`（4 值 · 录入通道）与 `streams.source_type`（13 值 · 产出方式）长期是否合并 |
| `TODO-106` | 🟡 | Excel 导入行的 `source_type` 仍是 `SIM_IMPORT` ⇒ 是否扩该词表 |
| `TODO-107` | 🟡 | 10 个 `*_CALCULATED` 设备计算出口流在 `source` 的 4 值里无对应 ⇒ 是否加第 5 值 `CALCULATED` |
| `TODO-109` | 🟡 | `streamApi.listByProject` 的**手写轻量子集**何时统一到契约派生 |
| `TODO-110` | 🟡 | `CreateStreamRequest.payload` 与 state-points body 是**裸 object** ⇒ 前端拿不到具名类型 |
| `TODO-111` | 🟡 | 物流详情三个端点的响应是**裸 dict / 裸 object 数组** ⇒ 前端手写本地类型 |
| `TODO-115` | 🟢 | 多数物流在 `data_lineage` 里**没有行** ⇒ 血缘 Tab 显示 404 报错 |
| `TODO-119` | 🟢 | 加锁读只泛化了**物流**一种记录型表 |
| `TODO-120` | 🟢 | e2e 进批末闸门的**触发条件** |
| `TODO-128` | 🟡 | 全测试迁移到 `strict_client` —— 默认 client **测不到守卫缺陷** |
| `TODO-129` | 🟡 | 物流面**之外**的模块守卫覆盖审计 |
| `TODO-130` | 🟢 | `user_project_service.py` 的既有 ruff 债（F821 / UP035 / UP037） |
| `TODO-131` | 🔴 | 部署前置 —— 各环境必须先 seed 授权行，否则**全站物流 404** |
| `TODO-137` | 🟡 | 遗留账号（`user_id` ≠ 派生值）的授权迁移 —— 一次性运维动作 |
| `TODO-138` | 🟡 | `TwoPhaseResult` **没有 `project_id`** ⇒ 无法登记血缘守卫 |
| `TODO-139` | ⚪ | 物流来源 vs 计算来源是不是**同一个概念** |
| `TODO-141` | 🟡 | 全量测试迁移到 `strict_client`（守卫测试的唯一入口） |
| `TODO-142` | ⚪ | 前端 review-log 的 `rowKey` 可能撞（同一事务两行） |
| `TODO-143` | 🟡 | 两处**缺索引**的聚合查询（要迁移 ⇒ 独立批） |
| `TODO-144` | 🟡 | WS 握手拒绝的**原因**到不了客户端（accept 前 close ⇒ HTTP 403） |
| `TODO-145` | 🟡 | 遗留账号行上，登录路径与每请求路径的停用判定**相反** |
| `TODO-146` | 🟡 | AI 可选依赖（langchain / ollama / vllm）本批未加 —— 待网络与独立批次 |
| `TODO-147` | 🟡 | pgvector 扩展与 `document_chunks.embedding_vector` 的维度（待裁决） |
| `TODO-148` | 🟢 | 内网 CIDR 清单待 IT 提供（只影响真实启用，不影响机制） |
| `TODO-150` | 🟡 | AI 端点的权限模型待定（现在任何已认证用户都能调，但一律 501） |
| `TODO-151` | 🟡 | FastAPI 的 422 信封对深层嵌套 JSON 自己就 RecursionError（既有通用缺陷） |
| `TODO-152` | 🟡 | E2E 车道进 CI（PR 跑关键 / nightly 跑全量） |
| `TODO-153` | 🟡 | AUTH-E2E-11/12（`TEST_VIEWER` 看测试报告页） |
| `TODO-154` | 🟢 | E2E 流程级数据落在 `pcs_pgtest` 的 public schema |
| `TODO-155` | 🟡 | 「真过 Redis + ARQ worker」的那一段没被端到端覆盖（AI 审计 **+ 报表生成**） |
| `TODO-158` | 🔴 | 报表审计哈希的**根因未闭环**（bug-2165 的残余） |
| `TODO-161` | 🟡 | 管道链计算**在运行时写配置表**（占位管级 `CS-STD`） |
| `TODO-162` | 🟡 | 公式编辑器的参数表用了 antd `rowKey` 回调的 **index** 参数 |
| `TODO-163` | 🟡 | compose 的 `migrate` / `seed` 两个写者**不在车道互斥锁内** |
| `TODO-167` | 🟡 | 前端还有别处把**占位常量**当真项目 id 用 |
| `TODO-170` | 🟠 | `report_definitions.project_id` 是**死字段**（数据模型说项目级 · 授权说创建人级） |
| `TODO-172` | 🟡 | **publish 的职责分离未定义**（产品语义待定 · **不是**越权缺口） |
| `TODO-177` | 🟡 | **公司级模板（`project_id IS NULL`）当前不可执行**（已知限制） |
| `TODO-175` | 🟡 | `POST /projects` 允许 SYSTEM_ADMIN 在**别人**的 FORMAL 工作区里建项目（产品语义待定） |
| `TODO-184` | 🟢 | `GET /report/styles` 的 `project_id` 是**死参数** |
| `TODO-187` | 🟡 | 两种 404 的**文案不同** ⇒ 记录/项目存在性可枚举 |
| `TODO-192` | 🔴 | **ce-code-review（P10-F 整批 · 2026-11-18）的修复项** |
| `TODO-196` | 🟡 | DMC 专用组分的 CAS 号**待工艺室确认**（P10-C · T4 引入） |
| `TODO-198` | 🟠 | 「待办 500ms 预算」测的是 **pytest harness 开销**，不是查询 ⇒ ⇒ 车道假红 |
| `TODO-197` | 🟠 | 前端**没有「他人发布报表定义」的入口** ⇒ ⇒ 「发布」在 UI 上不可达 |


---

## 🔴 P0 — 真问题（部署阻塞 / 安全）

> 现状（2026-10-07）：4 项中 3 项已做。仅 **TODO-002 token_version** 仍开放。

### 🔁 TODO-002 重新排序：**不属于本轮，属 P9**（2026-10-07 复核 spec 后改判）

- **What**: users 表加 `token_version`；`create_token` 写入 claim；refresh 时校验。
- **Why**: 无状态 JWT 的 logout 只清前端内存，被盗 refresh token 7 天内无法作废。
- **证据**: `grep -rln token_version pcs-backend/ --include=*.py` 全仓 0 命中。

**⚠️ 原处方两处错，按原文做会白做：**
1. **「decode_token 校验」做不到** —— `decode_token` 是无状态纯函数，没有 DB 通道。
   正确位置是 **refresh 端点**（那里本来就查 DB）。access token 保持无状态，
   吊销粒度 = access TTL（30 分钟）——这是行业标准取舍，不要为「每个请求查一次库」
   把 JWT 的意义抵掉。
2. **顺序错了** —— `users` 表真库 **0 行且全仓无任何代码写入**，login 走 LDAP、
   `user_id = uuid5(username)` 派生，根本不碰 users。现在给这张表加吊销机制没有意义。

**正确归属：`spec/…Web版 P9.md` §3.2.3 `P9-ADM-001`（ADMIN 用户管理）**
- 「新增用户：**同步后自动创建系统用户记录**」+ 接口 `POST /api/v1/admin/users/sync`（P9:156）
- 用户列表字段（用户名/姓名/邮箱/部门/角色/状态/最后登录时间）**与 `User` ORM 的 7 个列
  逐字段对应** —— ORM 是照 P9 建的，P9 尚未开工
- 「离职处理：用户从AD中删除后，**系统标记为停用**，保留历史数据」—— 停用要让在手会话失效，
  这正是 token_version 的用途

**🔴 P9 的一处规格缺口（需在 P9 补条目）**：P9-ADM-001 对「停用」只写到「标记为停用」
四个字，**未规定已签发令牌如何处理**。P9 开工前应补一条「停用即刻作废该用户全部
access/refresh token」，并把 token_version 列为该条的实现手段。

- **Owner**：随 P9-ADM-001 交付（**本轮不做**）

## 🟡 开放技术债

### TODO-032: 真库测试文件迁 conftest SQLite fixture

- **What**: `get_async_session_factory()`（真 PG）→ `db_session` fixture。
- **⚠️ 范围被严重低估**: 条目只列 4 个文件，**实测 27 个**。不是 4 文件修补，是全测试目录级别的工程。
  27 个清单见归档区备注。附带修 `test_detail_templates` 每跑推高 `template_version_seq` 无清理的问题。
- **Owner**: 待认领

### TODO-035: 物流校验规则 22 条补全 —— ♻️ 描述与实现脱节，先定扩展点

- **What**: P3.2 SIM-7 只实现 3 条典型；P4 需补齐剩余（饱和蒸汽压、临界压缩因子、Cv 边界、热力学一致性…）。
- **⚠️ 条目描述与代码不符**: 条目说「新增 `ConflictResolver.check_<rule>()` 方法」——
  实测 `app/services/conflict_resolver.py` **0 个 `def check_`**，实际是 4 个私有 `_check_prx_v01/v03/v05/v06`
  + `resolve_proii_import`。**扩展点不存在，19 条规则无处挂载。动手前必须先裁决扩展点形态。**
- **Owner**: 待认领

### TODO-026: P5 模块平铺字段 / data_sheet_json 展开（9/10 未做）

- **What**: 10 张结果表里 9 张仍是 `input_json`/`output_json` 简化容器。
- **证据**: `app/models/calc.py` — VesselResult:416 / SepEquip:655 / Heat:681 / Cv:785 / Restriction:892 / Flare:400 / PipeNetwork:139。
  **现成模板**: `CoolingTowerResult` 已按 DICT-007 §SUP-012 加了 14 子结构（`calc.py:949-980`），照它做剩下 9 张。
- **Owner**: 待认领

### TODO-029: CIA 传播性能预算测试

- **What**: `test_cia_propagation_perf_budget` —— 100 下游 record / depth 8 / ≤500ms。
- **证据**: 全仓 `perf_budget` 只命中 `tests/services/test_export_service.py:53`（导出预算），CIA 那个从无。
  **对照**: 同批的 TODO-030 导出预算已落地并触发了 write_only 改造 —— 同一个 D26/D28 决议，一落地一没落地。
- **Owner**: 待认领

### TODO-034: Excel 导入模板版本管理

- **What**: 导入模板加 `template_version`；导入时校验，不兼容返 `STREAM_TEMPLATE_VERSION_MISMATCH`。
- **证据**: `STREAM_TEMPLATE_VERSION_MISMATCH` 全仓 0 命中；现有 `template_version_seq` 是 DB 侧序列，与模板文件无关。
- **Why**: P4 起字段增减后，旧模板导入会**静默**缺列/多列丢数据。
- **Owner**: 待认领

### TODO-016: ARQ 失败注入 + DLQ 测试

- **⚠️ 命名陷阱**: `tests/test_arq_failure.py` **存在**，但内容是 workspace 清理测试，
  与失败路径/DLQ 无关。`worker.py` 无 `max_tries` 配置。**失败路径覆盖为零。**
- **⚠️ 与 P9-Prep PP-5 的边界**（2026-10-19 补）：PP-5 落地的 alembic 漂移闸门
  （`.githooks/pre-commit` + `pcs-backend/scripts/gate_alembic_check.py`）管的是
  **ORM ↔ 迁移漂移**，与 worker 失败路径**无关**，不要因为「闸门已自动化」把本条读成已覆盖。
  ARQ 失败路径仍为零覆盖，归 P9A-NOT-004（通知 30 天清理任务的失败注入测试）。
- **Owner**: 待认领

### TODO-017: P4 接入验收 e2e 从 1 扩到 4

- **现状**: 只有 `tests/test_lineage.py:423 test_p4_flash_full_path`。PUMP/PIPE/PIPE_NET 只有单元/persist 测试，
  无「计算 → DRAFT → CHECKED + @lineage 写血缘 + 状态机落审计」全路径。
- **性质**: P4 已收口，这条是**当时遗漏的验收缺口**，不是未来项。
- **Owner**: 待认领

### TODO-039 + TODO-041: 前端类型来源唯一性 + MSW 契约冻结（🔴 逾期 ~20 天，**2026-10-08 已重定范围**）

- **原 What（错的）**: 7 个 mock type 文件（pipeClass/flash/pipe/pump/pipeNet/pms/common）改 import 自 `./api`；
  MSW handlers 按 OpenAPI 重写。
- **⚠️ 重定范围结论（2026-10-08 实证）**：**这不是前端任务**，是**后端载荷债的下游**。
  原表述把「改 import」说成机械替换，会让下一个人白跑。

#### 证据一：前后端是同一份数据、两套命名，且**单位不一致**

flash 的 `FlashInput` vs 后端 `CalculateRequest`：

| 前端 | 后端 | 备注 |
|---|---|---|
| `h_kj_kg` | `H_target` | 焓 |
| `p_mpa` | `P_Pa` | **单位都不同**（MPa vs Pa） |
| `s_kj_kg_k` | `S_target` | |
| `t_k` | `T_K` | |
| `calc_type` / `stream_id` | 同名 | 仅这 2 个对得上 |

换 import 会全线崩，且 **`p_mpa` 传成 Pa 值的数字，TS 一样绿** —— 单位错不会被类型系统发现。

#### 证据二：**载荷在后端根本没定义**，这才是真堵点

8 个相关端点现在**全部**有 `response_model`（本次补齐了 pipe-codes 那 2 个），
但载荷字段是**裸类型**：

| 端点 | 响应 schema | 问题字段 |
|---|---|---|
| `POST /pump/calc-chain` | `pump.CalcChainResponse` | `result: object`（无 properties） |
| `POST /flash/calculate` | `flash.CalculateResponse` | `result: object`（无 properties） |
| `POST /pipe-net/solve` | `PipeNetSolveResponse` | `edge_flows: array`（**无 items**）、`check_result: string` |

**全 OpenAPI 量化：259 个 schema 中，141 个 object/array 字段里有 71 个是裸类型
（无 `properties` / 无 `items`）—— 半数结构化载荷在 API 契约里没有被定义。**
前端对这些载荷**只能继续手写类型**，而那正是本 TODO 想消灭的东西。

> 这与 §3.4 约束①（载荷模型 0/25 表）是**同一笔债的两个观测面**：
> 一个在 ORM 侧（JSONB 列无嵌套模型），一个在 API 侧（响应字段是裸 object）。
> **做完 §3.4 约束①，这边自然解锁；反过来不成立。**

复现命令：
```bash
cd pcs-backend && uv run python -c "
from app.main import app
S = app.openapi()['components']['schemas']
n = sum(1 for s in S.values() for f, p in (s.get('properties') or {}).items()
        if '\$ref' not in p and p.get('type') in ('object','array')
        and not p.get('properties') and not p.get('items'))
print(n, '个裸载荷字段')"
```

#### 证据三：原 TODO 里「字段名已对齐」的说法是假的

`pipeClass.ts` 注释称「`PipeClassResponse` 字段名 `code`/`material`/`schedule` 已对齐」。
实测 `PipeClassResponse` 是 `class_id` / `class_name` / `material_standard` / `base_material` …，
**`code`、`material`、`schedule` 三个字段一个都不存在**。
且不是简单改名：前端 `size_range_json`（1 个字段）对应后端
`dn_series_json` + `sch_series_json`（2 个字段）—— **结构不同**。

#### 证据四：目前没有任何东西真的坏

7 个模块前端**全部走 MSW**（`pcs-frontend/src/api/` 里 0 引用 pipe/flash/pump/pipeNet/pms/pipeClass），
36 个 handler 兜着。漂移是**潜在的** —— 等有人接真实 client 那一刻才爆。

#### 本次已做（2026-10-08）

- **补齐 pipe-codes 两个响应 schema**：`GenerateResponse{code}`、
  `ValidateResponse{valid, errors, segments}`。这两个是 8 个端点里**唯一**
  完全没有响应 schema 的，补完前端可生成对应类型。
- **加 OpenAPI 响应契约测试**（`tests/test_schema.py`）：锁住「这些端点必须有响应 schema」。
  行为测试抓不到这件事 —— 端点照样返回正确数据、端到端照样绿，只有前端接 client 时才发现没有类型可用。
  ⚠️ 该测试断言的是**有效契约**（OpenAPI 里有没有 schema），不是某一种写法：
  FastAPI 从 `response_model=` 装饰器**或**返回类型注解都能推出，只撤装饰器它仍绿（正确的，契约没破），
  两个都撤才转红。已实测验证两种撤法。

#### 2026-10-08 已加覆盖率闸

`pcs-backend/scripts/check_openapi_payload_coverage.py` —— 把「71」从一次性数字
变成**可回归**的数字：

```
API 载荷结构覆盖: 70/141 (49.6%)，基线要求裸字段 <= 71
当前: 71 个裸 object/array（259 个 schema 全体扫描）
欠账明细（71 个，不阻断；修 §3.4 约束① 时自然下降）:
  DiffResponse: 3  [added, removed, changed]
  PipeClassCreate/Response/Update: 各 3  [allowable_stress_json, dn_series_json, sch_series_json]
  WeightEstimateResponse: 3  [segments, formula_ref, output_json]
  ...
```

- **退出码**：裸字段 ≤ 71 → 0；> 71 → 1。修好了就把 `BASELINE_BARE_FIELDS` 下调。
- **已端到端验证不是假绿**：往 `GenerateResponse` 塞一个裸 `dict` 字段 → 72 → exit 1；
  撤掉 → exit 0。另有单元测试把基线压到实际值以下验证闸会红。
- **这个闸不需要登记表**（与 §3.4 那个不同）：「载荷有没有定义」是 OpenAPI 自身的
  属性，不是人工映射判断，全部推导、零维护。§3.4 那个需要登记表是因为它比对的两端
  都要人工声明对应关系。
- ⚠️ 已知局限：闸只比总数，**说不出是哪几个新增的**。输出里已如实标注，定位靠
  `git stash` 对比或看 diff。

#### ⚠️ 2026-10-08 用户裁决：这条债已升级为 **P9B 阻塞项**

71 个裸字段不只是 §3.4 的下游 —— 它会**污染 P9 自身**：

P9B 需要的端点 | 响应 schema 现状
---|---
`POST /deliverables/{id}/issue` | P9A 待建
`POST /deliverables/{id}/sign-step` | P9A 待建
`POST /deliverables/{id}/customer-approval/proxy` | P9A 待建
`GET /deliverables/{id}/actions` | P9A 待建
`workflow_progress` 读 API | P9A 待建
`notifications` / `todos` | P9A 待建

**如果 P9A 沿用现有习惯（响应 `object` 裸类型），P9B 的 type 生成会得到一堆
`any` / `unknown`，P9B「前端 type 从 `./api` 生成」这条纪律在 P9 内部第一天
就废掉 —— 不是偿还本 TODO 的债，是把债复制进 P9。**

**已落地的硬约束**（写进 P9 SPEC 三处）：

1. **P9A 验收标准**：交付的每个新端点，响应 schema 不得含裸 object/array。
2. **新增任务 P9A-DLV-010**（与 P9A-DLV-0XX 区分：0XX 是修既有 71 个，
   DLV-010 是**新增的不许欠**）。两者都做，P9A 才不会一边修旧账一边欠新账。
3. **P9B 开工前提**：契约冻结的验收含「裸字段数仍为 71」。**只「冻结」不够
   —— 冻结一份满是 `object` 的契约等于把 unknown 合法化。**

执行闸：`pcs-backend/scripts/check_openapi_payload_coverage.py`（裸字段上涨即
exit 1）。P9A 收口时基线应**仍为 71**，不是下调到 0 —— 71 是既有欠账。

#### 仍然未解决

- **71 个裸载荷字段**（证据二）—— 主体工作，现已可测量、可回归。
- **逐模块字段映射 + 单位归一**（证据一、三）—— 依赖上一条先做，否则前端没得可映射。
- **MSW handlers 按最终契约重写** —— 最后一步，前两条不做就是白做。

**Owner**: 待认领。**建议顺序：§3.4 约束①（后端载荷模型）→ 本 TODO**，
反过来做会返工。

### TODO-040: PIPE_NET 完整版（reactflow / 布局 / 环路检测 / 序列化）

- **证据**: `package.json` 无 reactflow/dagre/elkjs 依赖；`PipeNetTopologyPage.tsx` 仍手写 SVG。
- **Owner**: 待认领

### TODO-044: Per-Batch QA Gate —— ⚠️ 闸门写在了错误的层级

- **现状**: `gstack-qa` 在 `~/.claude/settings.json` 已 `"on"` ✓；`.gstack/qa-reports/` 6 份报告 ✓。
- **⚠️ 问题**: 流程写在**全局** `~/.claude/CLAUDE.md`，项目根 `CLAUDE.md` grep 0 命中。
  换机器/换人/重新 clone 即失效，实际靠人肉记忆维持，且无自动化钩子。
- **修法**: 把闸门流程写进**项目根** `CLAUDE.md`（可入库、可 review），全局只留指针。
- **Owner**: 待认领

### TODO-014: 设备联动「设备同步中」前端标记（🟡 PARTIAL）

- **What**: ADR-0025 已声明 CHECKED 状态变化的 ≤5 分钟一致性窗口 + 「状态 CHECKED 但设备记录 STALE」中间态，
  并要求 CI/前端展示「设备同步中」标记。**ADR 写完了，前端没跟。**
- **证据**: `docs/adr/0025-equipment-eventual-consistency-window.md:6,13,24` 已写；
  `grep -rn "设备同步|同步中|syncing" pcs-frontend/src/` **0 命中**。
- **注意**: 这个窗口现在对用户**不可见** —— 用户看到「已 CHECKED 但设备显示 STALE」时无从判断是同步中还是出问题。
- **Owner**: 待认领

### TODO-015: lineage_ctx 事务回滚清理语义文档化

- **What**: docstring + SPEC 说明 ctxmgr 内 entry 在 `session.rollback()` 时自动清理，P4 开发者无需手写清理。
- **证据**: `app/services/lineage.py` / `lineage_extension.py` grep `rollback|回滚|事务` 0 命中。
- **Owner**: 待认领

### TODO-023: 计算函数签名约定写入 CLAUDE.md

- **证据**: `docs/p4-template.md` 不存在；项目根 `CLAUDE.md` 无该章节。装饰器从 `kwargs["db"]` 取值，签名是硬契约。
- **Owner**: 待认领

---

## bug-190: `ConfigAsset` 的 category / updated_by / hash / tags 全是前端编的

补 TODO-040 时接上真端点才发现，`AssetListPage` 读的数据没有一个字段对得上真表：

| 前端字段 | 真相 |
|---|---|
| `category: FORMULA/COEFFICIENT/TEMPLATE/STANDARD_DB/PROJECT_TEMPLATE/EQUIPMENT_LIB` | DB 的 CheckConstraint `config_assets_category_chk` **只允许 CATEGORY_1~6**。真实数据永远是 `CATEGORY_N` ⇒ **按类别过滤的 Tabs 在生产上一档都命中不了**；六个语义名里只有 `EQUIPMENT_LIB→CATEGORY_6` 碰巧对上 |
| `updated_by: string` | `config_assets` **没有这一列**（只有 `created_by`/`created_at`/`updated_at`）⇒ 「更新人」列恒空 |
| `hash` / `tags` | 表里没有，`AssetResponse` 也没有 ⇒ 详情里的哈希/标签恒不显示 |

⇒ 已把 `ConfigAsset` 并成 `components['schemas']['AssetResponse']`，
`ConfigCategory` 改成 CATEGORY_1~6 并给每值标注**依据出处**（不是猜的），
删掉两列与详情里三块。后端 `AssetResponse.category` 也补上枚举
（此前裸 `str`，bug-188 同型）。

⚠️ SPEC §7.10.1 列的展示顺序（公式/系数表/模板文件/标准数据库/项目模板/
复用设备库）**不是编号顺序**，且其中「标准数据库」在 CATEGORY_1~6 里**没有
对应项** —— 别照那个顺序生成 tab 顺序，也别以为 6 个语义名对应 6 个编号。

### CATEGORY_N 的业务含义（依据可追）

| 值 | 含义 | 依据 |
|---|---|---|
| 1 | 项目模板 | `版本与版次管理增补规格说明书.md` §3.2.7 |
| 2 | 公式 | `…开发计划.md` 2.2；`config.py:337`；`DOUBLE_SIGNOFF_CATEGORIES` |
| 3 | 系数表 | `coefficient_service.py` |
| 4 | 模板文件 | `…Web版 P8.md:66` |
| 5 | 管道等级/符号 | `pipe_class_service:402`、`stream_symbol_service:139` |
| 6 | 复用设备库 | `equip_lib_service:64` |

---

---

## 仍未解决（本会话结束时的状态）

| 项 | 规模 |
|---|---|
| **P9** | `report_verify_base_url` 未配置 ⇒ 二维码默认不印；`assemble` 真分批 |
| **TODO-026** | 9 张结果表里 8 张仍是 `input_json`/`output_json` 简化容器。照 `CoolingTowerResult` 的 14 子结构铺开 ≈ **100+ 个子结构** + 迁移 + 契约 + 测试 |
| **TODO-032** | 条目写 4 个测试文件，**实测 29 个**用真 PG（`get_async_session_factory`），是全测试目录级别的工程 |

**另有两项本轮明确留作已知边界，不阻塞**：
- `StrictColumns` 的数组形式只校验「每段都是某层的 key」，不校验「这些段能串成一条路」
  —— 严格路径要 `as const`，而 `as const` 一旦为了「让闸闭嘴」而加，闸就没了；
- `ConflictResolver._VALID_PHASES` 等**其它表**的裸串词表（如 `config_domain` 里
  5 张子表用 `default="ACTIVE"` 而 `ConfigAsset` 用 `ConfigStatus`）尚未系统排查。

---

## TODO-045: `StrictColumns` 的数组形式不校验「段间路径」（🟡 已知边界，2026-10-19）

### 边界是什么

`DeepKeys<T>` 的数组形式只校验**每一段都是行类型某层的 key**，不校验
**这些段能串成一条真实的路径**：

```ts
// ✅ 通过（每段都是合法 key，但串不成一条路）
{ dataIndex: ['class_id', 'class_name'] }   // 契约里两者都是 string，无子字段
{ dataIndex: ['result', 'relief_scenario'] }  // 正确用法
// ❌ 也会通过（真正的错误，但闸抓不住）
{ dataIndex: ['result', 'orifice', 'nope'] } // 'nope' 若在别的层出现过
```

⇒ **词表内的拼写错误抓得住**（那正是 bug-180 的形态）；
「段名合法但路径不存在」抓不住。

### 为什么不修

严格路径要求 `dataIndex: ['result','relief_scenario'] as const`（让 TS 推断成
tuple 而非 `string[]`）。本仓只有 4 处嵌套 `dataIndex`（都在 `PsvComputePage`），
加 `as const` 本身不贵 —— **贵的是它会成为一种「让闸闭嘴」的惯用写法**：
下次有人为了让闸通过而加 `as`，闸就没了，而且看不出区别。

### 补法（想收口时按此做）

定义一个路径构造 helper，让类型在编译期就能表达「这条路径存在」：

```ts
// 只有 'result' 下真有 relief_scenario 时，这个调用才成立
const p = path<Stream>('result', 'relief_scenario');
// → 类型是 ['result','relief_scenario'] 而不是 string[]
```
然后 `dataIndex: p`。**helper 内部必须真的是逐层 `keyof` 推导**，
不能内部 `as` —— 那样只是把洞从闸挪进 helper。

### 什么时候值得做

出现**第二处**嵌套 `dataIndex` 时。现在只有 4 处、都在一个文件，
收益不抵「引入一个可能被误用的 helper」的成本。

⚠️ 相关：`tests/types/strictColumns.test.ts` 里有一条
`test_⚠️_已知边界_段间路径不存在时抓不住` 的**显式用例**记着这件事 ——
别把它当重复而删掉。

---

## TODO-046: 其它表的裸串词表尚未系统排查（🟡，2026-10-19）

### 已知的一处

`app/models/config_domain.py` 里有**两套状态词表并存**：

- `ConfigAsset.status` / `PipeClass.status` → `ConfigStatus`
  （5 态：DRAFT/PENDING/APPROVED/PUBLISHED/OBSOLETE，DB 侧无 CHECK，
  契约侧已枚举化 —— bug-187/188 修的就是这个）
- **5 张子表**的 `status` → `default="ACTIVE"`：
  `formula_definitions` / `coefficient_tables` / `template_files` /
  `project_templates` / `numbering_template`

`ACTIVE` **不属于 `ConfigStatus`**。也就是说同一个 `config_domain` 模块里，
父表走审批链、子表用一个审批链里根本没有的状态。

### 为什么现在不动

子表各自的业务语义没查清 —— 它们可能**确实**只需要「启用/停用」两态
（那 `ACTIVE` 是对的，与父表的 5 态无关），也可能跟错了一直没人发现。
**猜错方向会把一个能用的东西改坏**，而这类判断必须逐表读代码/问业务。

### 开工前要做的三件事

1. 逐个列出这 5 张表的 status **实际取值**（代码产地 + 真库 DISTINCT，
   两个库各查一次）；
2. 确认它们**是否真的经过审批链** —— 若没有，`ACTIVE` 可能是刻意简化，
   该加的是 CHECK + 契约枚举，而不是换成 `ConfigStatus`；
3. 与 `POST /config/assets/{id}/{submit,approve,publish,obsolete}` 的行为对照：
   这四个端点**改不到子表的 status**（它们操作的是 `config_assets` 行）。

⚠️ **教训（来自 bug-187）**：这类判断**必须靠证据，不能靠对称性直觉** ——
上轮我就是看到「前端 3 态 / 后端注释 5 态」的矛盾就选了看起来更完整的那个，
而真正该问的是「哪个状态机是活的」（哪些端点真的会产生它）。

### TODO-047: advisory_lock.acquire_record_lock 跨进程不串行（Python hash 加盐）

`pcs-backend/app/services/advisory_lock.py:27-28` 用 `abs(hash(record_table))` /
`abs(hash(record_id))` 作 `pg_advisory_xact_lock` 的 classid/objid。
Python `str.__hash__` 默认按进程随机加盐（`PYTHONHASHSEED`），多 worker 部署下
同一 `(table, id)` 在不同进程算出不同 key ⇒ 锁静默失效、并发状态转移不被串行化。

同文件 `acquire_equip_list_lock`（`:67`）用 PG `hashtext(:key)`，是正确的。
裁定方向：统一到 `hashtext()`。

- **发现**：2026-10-19，P9-Prep 编写 ADR-0048 时
- **归属**：P9A-LCK 或独立修复；**不在 P9-Prep 修**（改动面在 P7 已验收代码）
- **严重度**：HIGH（并发正确性，且失败无声 —— 单进程测试全绿）

### TODO-048: RECORD_TYPE_REGISTRY 名不副实 —— 它不是 finalize 的支持清单

`pcs-backend/app/services/calc_lineage.py:68` 的 `RECORD_TYPE_REGISTRY: dict[str, type]`
看起来像「`finalize_calc_record` 支持哪些 record 类型」的清单。**它不是。** 2026-10-19 实测：

| 查什么 | 结果 |
|---|---|
| `finalize_calc_record` 体内引用注册表几次？ | **0 次** —— 它靠鸭子类型（`record.record_hash = ...`），从不查注册表 |
| `app/` 里除定义与 `__all__` 外的消费者？ | **0 个** —— 只有测试断言成员与数量 |

**为什么有害**：`CostEstResult` 在注册表里 ⇒ 读者以为它被 finalize 支持 ⇒
实际调用会抛 `AttributeError`（该表无 `record_hash` 列）。
目前靠 `app/services/cost_est/cost_est_persist_service.py:15` 的一句注释挡着 ——
**防线是注释不是代码**，而「注释防不住已进过记录的 bug」这条已进 cerebrum。

**裁定方向**（待 P9A 或独立修复）：
① `finalize_calc_record` 开头加显式校验：目标对象无 `record_hash` 列时抛带类型名的
   明确异常，取代裸 `AttributeError`；② 在注册表 docstring 里写明它是「名称 → 类」映射，
   **不表示 finalize 支持**。

⚠️ **不要加「registry ⇒ 有 record_hash 列」的一致性测试** —— 那是**不存在的不变式**，
加了会立刻红在 `CostEstResult` 上。

- **发现**：2026-10-19，P9-Prep 裁决会澄清注册表语义时
- **归属**：P9A（`cost_est_results` 补列时一并处理）或独立修复
- **严重度**：MEDIUM（当前无 bug，但给出假安全感；首次误用会抛 AttributeError 而非静默）
- **关联**：ADR-0048 §⑥ 语义澄清块

### TODO-049: two_phase_persist.py 的两处注释与代码不符

`pcs-backend/app/services/pipe/two_phase_persist.py:6-8` 写着：

- 「TwoPhaseResult 模型无 record_hash 列」
- 「finalize_calc_record 调用 RECORD_TYPE_REGISTRY，TwoPhaseResult 未注册」

**两句都不成立**（2026-10-19 实测）：该表**有** `record_hash` 列
（P4-TASK0 补的，模型注释自陈「接入 calc_lineage 收口」），且 `TwoPhaseResult`
**在注册表的 21 条里**。第二句还叠了一个错误前提：`finalize_calc_record`
**从不查注册表**（见 TODO-048）。

- **发现**：2026-10-19，P9-Prep 裁决会核实「two_phase 是否需要补 updated_at」时
- **归属**：独立修复（与三条裁决无耦合，**不阻塞 P9A 开工**）
- **严重度**：LOW（注释误导，但该表已登记且有列，无实际缺陷）
- **关联**：TODO-048

---

## TODO-055: `RECORD_TYPE_REGISTRY` 的键风格不统一（P9A B4a 登记）

`app/services/calc_lineage.py:68` 的注册表键混用两种风格：
`PipingResult` / `PumpResult`（类名）与 `cv_result` / `flare_system_result`（蛇形）。

P9A B4a 的 `POST /records/{module}/{id}/...` **直接以该注册表的键作为 URL 段**
（唯一真值源，不另起映射表），所以这个不统一现在**暴露在 API 形状上**：
同一个概念在 URL 里可能写成 `/records/PipingResult/...` 也可能是
`/records/cv_result/...`。

**未改的理由**：改键名会让 `finalize_calc_record` 等既有调用方一起断，
而 P9A 的范围是「接线」不是「重构注册表」。

- **发现**：2026-10-20，P9A B4a
- **归属**：独立一轮（改注册表键 + 全部调用方 + 迁移注释同步）
- **严重度**：LOW（功能无缺陷 —— 两种写法都能解析；代价是 URL 形状不统一）
- **关联**：TODO-048（同一注册表的另一处语义问题）

---

## TODO-056: `NumberingTemplate.segments_json` 的 ORM 标注是错的（`Mapped[dict]`）

真实内容是**列表**（P2 计划设计 §3.5 的示例 `["project_no","-","doc_type","-","seq"]`），
但模型标注成 `Mapped[dict]`。P9A B1 的 `_allocate_doc_no` 因此在自己的代码里用
`Any` 绕过（改那个标注会牵动别的消费者，且不在 P9A 范围）。

按 CLAUDE.md「发现无关缺陷要说、不要顺手改」登记在此。
下一个碰这个字段的人请顺手改掉标注并补一条断言（内容是 list）。

- **发现**：2026-10-20，P9A B1
- **归属**：独立修复（一个标注 + 一条断言）
- **严重度**：LOW（无运行期缺陷；只误导 mypy 与下一个消费者）

---

## TODO-060（原）: `record_type` 存在两套词表（类名 vs 表名）

| URL 空间 | 词表 | 例 |
|---|---|---|
| `/change-impact/{record_type}` | **类名**（`RECORD_TYPE_REGISTRY` 的键） | `PipingResult` / `CostEstResult` |
| `/results/{id}`（PATCH 6 个端点）+ `/locks/{record_type}` | **表名** | `cost_est_results` / `psychro_results` |
| `record_comments.record_type`（DB 列） | **类名** | `PipingResult` |

⇒ 同一概念（「这条记录是什么类型」）**三处三套写法**。

- **发现**：2026-10-20，P9A-4 D3 实施时（`change_impact.py` 加 `confirm` 端点，
  必然要选一个词表）。
- **为什么当时没统一**：D3 的新端点与既有的 `confirm-recalc` **同一个 URL
  空间** ⇒ 必须跟它一致（类名）；而 D2 的编辑 guard 与 `/locks` 是**另一个
  URL 空间**，且已在 SPEC §6.21 P9A-LCK-001~006 写死了表名 ⇒ 改它要连带改
  SPEC 与前端契约。
- **转换路径存在**：`model.__tablename__` ↔ `RECORD_TYPE_REGISTRY` 双向可换
  ⇒ 归一不是技术问题，是**要不要现在动**的判断。
- **风险（不动的代价）**：前端把 `CostEstResult` 传给 `/locks` 会静默落空
  （锁服务不校验类型 ⇒ 锁写到一个没人读的名字上）；反过来把
  `cost_est_results` 传给 `/change-impact` ⇒ 404（注册表查不到）。
  ⇒ 两边都**不会报错给用户看** ⇒ 属「错得安静」的一类。
- **建议**：随 P9A 前端接 §6.21 时一并归一（前端本来就要按 SPEC 新写这两处
  调用）⇒ 一次性改 SPEC + 两处后端 + 前端类型定义。**不要**在 D lane 内
  单方面改后端（会把已发布的契约与 SPEC 对不上）。
- **严重度**：MEDIUM（当前无调用方 ⇒ 无实际故障；前端接的时候必须一起改）
- **关联**：ADR-0050（同一形状的词表分叉）、ADR-0048 §⑥、
  `docs/PCS-UI-SPEC.md` §6.21、`RECORD_TYPE_REGISTRY`（见 TODO-048）

</details>

---

## TODO-062: `cia_engine.REGISTRY` 是 `record_type` 的**第 6 套词表**，且自相矛盾（🟡）

2026-10-20 实测（P9A-5 Task A 顺带发现，**未修**）：

```
app/services/cia_engine.py:46-52  REGISTRY = {"config_asset": ConfigAsset,
                                              "config_version": ConfigVersion,
                                              "equipment_list": EquipmentList}
app/services/cia_engine.py:160    data_lineage.record_type 写的是 cls.__name__（类名）
```

⇒ `REGISTRY` 的键是 snake 单数，而它**自己写进 DB 的值**是 PascalCase 类名
⇒ `cia_engine.py:447` 的 `_get_record(record_type)` 用 `REGISTRY.get(record_type)`
路由时，DB 里存的类名**永远匹配不上** ⇒ 注释自己承认的「未登记返回 None
（**静默跳过**）」。

- **为什么没在 P9A-5 Task A 里修**：改它要**重路由 CIA 扫描**（哪些配置资产被
  CIA 跟踪），属于 CIA 引擎的行为变更，不在「归一契约面词表」的范围内。
- **后果**：CIA 扫描对 `config_asset` / `config_version` / `equipment_list`
  这三类记录**静默跳过**（不报错、不告警）。
- **建议**：单独一笔。先用真库确认这三类记录在 `data_lineage` 里到底存的
  是什么值，再决定是改 `_get_record` 的路由还是改写入端 ⇒ **不要**两边一起改。
- **严重度**：MEDIUM（当前静默跳过，无数据损坏）
- **关联**：TODO-060（已闭环，本次把它收敛到 `RECORD_TYPE_REGISTRY` 的键）·
  ADR-0050 §未决 2

---

## TODO-063: 迁移幂等守门的**遗留盲区**：`p1`~`p6` / `p8` 共 93 个文件从未被检查（🟡）

2026-10-20 实测（P9A-5 Task B 顺带发现）：

- `scripts/check_migration_idempotency.py` 原先只扫 `p7_*.py` ⇒ **`p9_*` 的
  7 个文件也从未被检查**，其中 3 个共 **17 处**违规，而守门每次都报 `OK`。
  ⇒ 本次已把 `p9_*` 纳入并补掉那 17 处（见提交「迁移幂等守门覆盖 p9_*」）。
- 但把 glob 开到 `*.py` 会暴露 **93 个文件 / 350 处**违规（含
  `dd47298c9c38` 全 schema 迁移的几十个 `op.drop_table`）⇒ 一次补 350 处会
  淹没 diff，且每处都要确认语义（某些 `drop` 上加 `if_exists=True` 会掩盖
  真实错误）⇒ 有意留在覆盖外，脚本里以 `LEGACY_PREFIXES` 显式列出。
- **新增守卫**：`tests/scripts/test_check_migration_idempotency.py::
  test_covered_globs_include_every_migration_prefix` 断言「不在 `GLOBS`
  也不在 `LEGACY_PREFIXES` 的迁移文件数为 0」⇒ **加新一波前缀却忘了加 glob
  会立刻红**。
- **建议**：下一批迁移开工前，先跑一遍并把该批前缀加进 `GLOBS`；遗留的 93 个
  按 sprint 逐步消化（每个 sprint 顺手补自己那一段）。
- **严重度**：LOW（存量迁移已跑过，幂等 guard 只影响「重跑同一迁移」的场景）
- **关联**：`docs/PCS-PLAN-P9A-5-债项清理.md` Task B

---

## TODO-064: 全仓 **57 个**手写类型与生成契约 schema 同名（🟡 长期债，已有棘轮守卫）

2026-10-20 实测（P9B-1 Task F0 顺带发现，**未修**）：

`src/types/*.ts` 里有 **57 个** `export interface` 的名字**出现在
`openapi.snapshot.json` 的 `components.schemas` 里** ⇒ 同一契约两份手抄。

- **多数有消费方**（如 `HeatResultResponse` 被 `src/api/heat.ts` +
  `src/mocks/heat.ts` import）⇒ 改它们要连带核对页面与 mocks ⇒ 不是删了就完。
- ⚠️ **`npm run api:audit-types` 抓不到**：它维护的是一份**手写清单**
  （10 个类型），结果模块与这批**都不在清单里**
  ⇒ 「清单外的漂移」没有任何既有自动化会红。
- 已知的**实质漂移**（不是「可能」）：`CostEstUpdateRequest` 等 6 个
  `*UpdateRequest` **缺 `expected_hash`**（P9A-4 D2 之后后端必填）
  ⇒ 按手写类型发请求必然 409。

### 本批做了什么（不是全清）

1. **删掉 6 个可编辑结果模块的 18 个**（`*UpdateRequest` / `*ResultResponse` /
   `*ListResponse`）—— 全部**零消费方**且已漂移 ⇒ 直接判死，改用生成类型。
2. **加棘轮守卫** `pcs-frontend/tests/types/no_handwritten_result_types.test.ts`：
   - 定点：删掉的 18 个名字不许回来；
   - 棘轮：同名手写类型数量**只许减不许增**（基线 **57**）；
   - **零消费方 + 同名 ⇒ 直接判死**（除非登记例外）；
   - 例外表不许变成死水（例外必须仍然存在）。
   ⇒ 新写一个同名类型会红；修掉旧债会让计数下降。

### 建议

按模块逐个迁（一次一个模块：先 grep 消费方 → 改 import → 跑 vitest +
typecheck）。优先迁「零消费方」的（它们连棘轮都判死，会直接红），
其次是有 mocks 的（要同步 fixture 字段）。

- **严重度**：MEDIUM（当前无功能故障；有消费方的那些仍在工作，但少字段时会静默）
- **关联**：P9B-1 Task F0 · `scripts/audit-handwritten-types.mjs`（清单式审计的盲区）

## TODO-091: `project_templates.record_approval_config` 作废（**只有注释、无消费方**）🟡

**What:** `project_templates.default_config_json` 里的 `record_approval_config`
**没有任何消费方**（全仓只命中那一处注释）⇒ 2026-10-27 的裁决 **R-17** 把
「记录侧多级批准链」的定义源定为**项目绑定的 `module='RECORD'` 签署矩阵**
⇒ 这个配置项**彻底作废** ⇒ 建议从项目模板的默认配置里**删掉**（或明确标注
「已废弃，批准链见签署矩阵」）。

**Why:** 留着它 ⇒ 下一个读项目模板的人会以为「多级批准链在这里配」⇒ 去那里
找配置 ⇒ 找不到（因为没消费方）⇒ 白费时间。开发阶段**无历史配置数据**要清理
⇒ 现在删成本最低。

**Pros:** 消掉一个会误导人的配置项；项目模板的默认配置只留**真在用**的键。

**Cons:** 改 `project_templates` 的默认 JSON ⇒ 属于「模板内容」变更 ⇒ 要确认
没有别处按 key 读它（已查：零命中）。

**Context:** 2026-10-27 `/plan-eng-review` 复审 P9B-2 计划时发现 ⇒ 裁决 R-17
（批准链定义源 = 签署矩阵）⇒ 顺带发现这个配置项作废。证据：`app/models/project.py`
的 `default_config_json` 里那句注释 + **全仓零消费方**。

**Depends on / blocked by:** 无（独立）。**归属：** 项目模板相关批次（PMS / P2）；
**触发条件：** 下次改 `project_templates` 表 / 模板默认配置时一并删。

## TODO-092: ADMIN「角色分配」没有后端端点 🟡

**What:** `GET /admin/users` / `PUT /admin/users/{id}/disable` /
`POST /admin/users/sync` **三个端点里没有「改角色」** ⇒ 用户的全局角色
（`users.roles`）**只能靠 AD 同步的组映射**改 ⇒ 想手工给某人加/减一个角色，
**没有路**。

**Why:** AD 同步是「目录说了算」；本地手工调整（临时授权、纠错）没有出口 ⇒
管理员只能去改 AD ⇒ 生效还取决于下次同步。

**Pros:** 补一个 `PUT /admin/users/{id}/roles` ⇒ 管理员能手工纠错；
与「停用」并排 ⇒ 同一套审计（`token_version` 也要跟着涨，否则旧 token 仍有效）。

**Cons:** 新端点 + 契约 + 测试；**角色来源的权威性**要想清楚（AD 同步会不会把
手工改的角色冲掉 ⇒ 需要「手工优先」或「标记来源」）。

**Context:** 2026-10-27 `/plan-eng-review` 复审 P9B-2 时确认（`app/api/v1/admin_users.py`
只有 list / disable / sync 三个端点）⇒ P9B-2 的 ADMIN 前端**不含**角色分配
（计划的「NOT in scope」已登记）。

**Depends on / blocked by:** 无（独立）。**归属：** P9B-3 或更后的 ADMIN 批次；
**触发条件：** ADMIN 前端要能改角色时。

⚠️ **2026-11-02 委员会裁决 3（已登记，本批不做）**：
① **「AD 同步覆盖 `users.roles`」是**当前行为**（不是缺陷，是现状）
—— 记在此处是为了**留档**，不是待修；
② 「角色来源的权威性」（AD 同步会不会冲掉手工改的角色）**升格为独立 ADR**
—— **不是**计划里能拍的事 ⇒ 本批**不做**角色分配页，
SPEC §7.20 的「角色分配」标 ⏳；
③ 独立 ADR 的**编号与立项时机**待定（下一批开工前立）。

## TODO-093: `sign_step` 并发无行锁 —— 两个签署者同时签，**后写的把先写的签名覆盖掉** 🔴

**What:** `DeliverableService.sign_step`（`deliverable_service.py:694` 起）对
`DeliverableVersion` 的读-改-写（`signature_summary_json` 整列覆盖）**没有行锁**：
两个同角色用户（或一次重试）几乎同时签同一步 ⇒ READ COMMITTED 下都通过
`_assert_step_order` ⇒ 各自基于读到的旧快照重建整列 ⇒ **后提交者把先签者的
签名条目从版本快照里抹掉**——而 `audit_logs` / `workflow_progress` 两条都留着 ⇒
**签署证据（快照）与审计轨迹永久不一致**。同文件编号路径已经用
`SELECT ... FOR UPDATE`（:706），`sign_step` 没跟上。

**Why:** 签名快照是**法定签署证据**；静默丢一条比报错严重得多。P9B-2 整批评审
（2026-10-29，`docs/ce-code-review/20261028-074842-e15c26e8/`）由 adversarial 提出、
验证者经**出处核查**判为 **pre-existing**（base `346c696` 的 :694 即如此，本批只加了
`reason` 字段）⇒ 不阻塞 P9B-2，但**必须跟踪**。

**Pros:** 按编号路径同款：`select(DeliverableVersion).where(...).with_for_update()`
先锁行再校验 ⇒ 第二个签署者阻塞到第一个提交后吃 409。补一个双会话并发签测试。

**Cons:** 无意义冲突窗口变窄（可忽略）；测试要起两个并发事务。

**Context:** 评审报告 finding #2（REJECTED-as-pre-existing，证据链见该 run 的
`validator-verdicts.json`）。**归属：** 下一批签署流程修复；**触发条件：** 任何时候
（真实缺陷，双人签署即可能触发）。

## TODO-094: 二次认证接受**任意** AD 凭据，不校验「就是操作者本人」 🔴

**What:** `verify_secondary_auth`（`services/secondary_auth.py:61`）用客户端提交的
`secondary_username`/`secondary_password` 直接 LDAP bind，**从不与操作者身份比对**
（`actor.username` 在调用点就有，`deliverables.py:382` 原样转发未校验）⇒
代录客户批准（ADR-0007 路径 B「重输本人 AD 密码」）可以用**任何人的**有效凭据通过
⇒ 审计行（`SIGN_2FA_FALLBACK`，`resource_id=username`）指向**被借用的账号**，
污染的恰是代录规则要建立的证据链。门现在证明的是「调用者知道某个密码」，
不是「调用者就是他声称的人」。

**Why:** 认证强度塌缩 + 审计指向错误 ⇒ 两层都失守。P9B-2 整批评审 finding #3，
验证者经**出处核查**判 **pre-existing**（`77d2e78` / P9A 引入 `secondary_auth.py`
全 76 行，本批 diff 未触及）⇒ 不阻塞 P9B-2，但**必须跟踪**。

**Pros:** bind 前加一道：`secondary_username != actor.username` ⇒ 401
`SECONDARY_AUTH_FAILED`（报错文案保持笼统，不泄漏是哪一步失败）。

**Cons:** 几乎无（共享/服务账号被用于代录的场景本就该被拒）。

**Context:** 评审报告 finding #3（REJECTED-as-pre-existing）。与 TODO-076 的
fail-open、mock 登录生产守卫共同构成代录面，见报告 Residual risks。
**归属：** P9B-3 或安全加固批；**触发条件：** 任何时候（真实缺陷）。

## TODO-095: `GET /deliverables?sign_status=` 接受任意字符串 🟢

**What:** 列表端点对 `sign_status` 查询参数不做词表校验（deliverables.py:126 →
service 裸 `==` 比对 PG 原生枚举列）⇒ 传非法值时的行为介于「静默空表」与
「DB 查询错误」之间（未实测）。**Pre-existing**（P9B-2 评审 api-contract 登记）。

**Fix 方向:** Pydantic `Literal`/枚举参数化 ⇒ 非法值 422 + 一条负向测试。

## TODO-096: 新工作流业务错误码未在 OpenAPI `responses=` 声明 🟢

**What:** 422 `RECORD_APPROVAL_MATRIX_NOT_BOUND` / 403 `APPROVAL_SELF_REVIEW_FORBIDDEN` /
409 `SIGN_STEP_OUT_OF_ORDER` 等业务码只活在代码里，baseline 的 responses 段查不到
⇒ 契约消费者无法从 OpenAPI 发现它们（前端是按信封泛解析的，不受影响）。
**Pre-existing、族群一致**（全部 workflow 端点都这样）⇒ 要做就整族做。

**Fix 方向:** 批量补 `responses={4xx: {"model": ErrorResponse}}` + baseline 滚动。

## TODO-097: MSW edits mock 忽略 `limit/offset` 🟢

**What:** `GET /records/:module/:record_id/edits` 的 mock（signFlow.ts）不认分页参数，
而同批已把 audit-logs mock 修成认分页 ⇒ 未来的分页 UI 在 dev 里静默看到未分页种子。
当前调用方不传分页 ⇒ 无可观察漂移。**Pre-existing**（P9B-2 评审 api-contract 登记）。

**Fix 方向:** 照 audit-logs mock 的 `slice(offset, offset+limit)` 同款补上。

## TODO-098: `deliverable_service.py` / `mocks/handlers.ts` 超 800 行上限 🟢

**What:** 1420 / 1029 行（本批前已超），每批继续长 ⇒ 提取债务无人排期。
**Pre-existing**（评审 maintainability 登记）。

**Fix 方向:** deliverable_service 按读面/写面/客户批准拆；handlers 按域拆文件
（MSW 注册顺序无关 ⇒ 拆分安全）。

## TODO-100: 下一轮 review **必须**覆盖的未深审部分（复审追问 2） 🟢

**What:** P9B-2R follow-up review 的 Coverage 段如实登记了盲区：以下**本批次的
实质交付物**未被深审 ——

- `pcs-backend/tests/api/v1/test_deliverable_issue.py`（PE-1 修复的测试面）；
- `deliverables` / `record_edits` 两个 API 的改动；
- 该批 diff 里余下的部分（14279 行中的其余部分）。

**Why:** 这不是「本轮的失败」，是**已知盲区** —— 但 `record_edits` 是**本批次
新增的端点**（TODO-066），`test_deliverable_issue.py` 是 PE-1 的测试 ⇒ 两者的
交付物有一部分**没被验证过**。

**归属:** 下一轮 ce-code-review 的 scope（**不是**「如果时间允许」，是 scope
的一部分）。

**触发条件:** 下一次跑 `ce-code-review` 时，在 scope 段显式列出这三项。

**依据:** `docs/ce-code-review/20261102-004658-08a55f5c/report.md` §Coverage
（委员会追问 2，2026-11-02）。

⚠️ **2026-11-02 登记（下一轮 scope 的强制项）**：下一轮 ce-code-review 的
scope **必须包含**以下三项（**不是**「如果时间允许」，是 scope 的一部分）：

1. `pcs-backend/tests/api/v1/test_deliverable_issue.py`（PE-1 修复的测试面）；
2. `deliverables` / `record_edits` 两个 API 的改动；
3. 该批 diff 里余下的部分（14279 行中的其余部分）。

## TODO-105: `streams.source`（4 值 · 录入通道）与 `streams.source_type`（13 值 · 产出方式）长期是否合并 🟡

**现状**（2026-11-02 实测）：两列**语义正交** —— `source` = 这条物流**怎么进系统的**
（MANUAL / SIM_IMPORT / EXCEL / LAB），`source_type` = 这条物流的**数据怎么算出来的**
（3 个人工/导入 + 10 个 `*_CALCULATED` 设备计算出口流）。

⚠️ 两列有 **3 处取值重叠但拼写不同**（`SIM_IMPORT` 同名 / `MANUAL_ENTRY`↔`MANUAL` /
`LAB_REPORT`↔`LAB`）⇒ **同一概念两份定义 ⇒ 漂移的温床**
（bug-187~191 / bug-2040 同族）。

**本批做法**（防漂移，不是合并）：**两列在每个写入点成对赋值**
（`import_service` / `outlet_stream`），并有测试钉住配对关系。

**长期选项**：① 把 `source_type` 的 3 个人工值收窄进 `source`（破坏既有契约，不划算）；
② 在 ADR 层写明「两列正交」并永久保留。

**归属：** T2.5 落地后随 ADR 一并登记。

## TODO-106: Excel 导入行的 `source_type` 仍是 `SIM_IMPORT` ⇒ 是否扩该词表 🟡

**现状**（2026-11-02 实测）：`import_service._excel_preview_entry` 把 Excel 行的
`source_type` 也写成 `SIM_IMPORT` ⇒ 既有契约里**分不出** Excel 行与 PRO/II 行。

**本批做法**：新增的 `source` 列写 `EXCEL`（⇒ 两列取值**不同是有意的**）
⇒ 前端按 `source` 区分 ⇒ **既有 `source_type` 保持不动**
（改它要动既有枚举与契约 ⇒ 破坏性变更）。

**触发条件**：需要按 `source_type` 区分 Excel 与 PRO/II 时。

**归属：** 下一批或独立 ADR。

## TODO-107: 10 个 `*_CALCULATED` 设备计算出口流在 `source` 的 4 值里无对应 ⇒ 是否加第 5 值 `CALCULATED` 🟡

**现状**（2026-11-02 实测）：`pcs_test` 的 202 行物流里 101 行是
`PIPE_CALCULATED` / `PIPE_NET_CALCULATED`（设备计算出口流）⇒
`source` 的 4 值（MANUAL / SIM_IMPORT / EXCEL / LAB）里**没有**对应值。

**本批规则**：出口流**继承其上游物流的 `source`**（不造第 5 值、不撒谎）
⇒ 测试钉住。

**触发条件**：需要按「来源」区分「人工录入的物流」与「设备算出来的出口流」时。

**归属：** 下一批。

## TODO-109: `streamApi.listByProject` 的**手写轻量子集**何时统一到契约派生 🟡

**现状**（2026-11-03 实测）：`src/api/stream.ts` 有**两个**列表方法：

| 方法 | 返回 | 谁在用 |
|---|---|---|
| `listByProject` | **手写** `StreamListItem`（5 字段，含**契约里没有**的 `tag_number`） | Vessel / SepEquip / Heat / Cv 四个计算页 |
| `list` | **契约派生** `StreamResponse` + 四项筛选 | 物流列表页（T6） |

⚠️ 计划要求把 `listByProject` 的返回类型也换成契约派生 —— **实测会打破 4 个
消费者**：它们把结果映射成 `{stream_id, tag_number}`，而 `tag_number`
**不在契约里**（物流没有位号）⇒ 4 处 `s.tag_number` 全部编译不过。

⇒ 本批**另开** `list` 走契约派生，`listByProject` 一行不动。

**建议**：四个计算页的 Select 标签改用 `stream_name`（顺带修掉「标签恒为
undefined」的隐性缺陷）⇒ 之后删掉 `StreamListItem` 与 `listByProject`，
统一走 `list`。

**归属**：下一批（与 §7.7.1 其余筛选/列口径一并收口）。

## TODO-110: `CreateStreamRequest.payload` 与 state-points body 是**裸 object** ⇒ 前端拿不到具名类型 🟡

**现状**（2026-11-03 实测）：契约里

- `POST /projects/{id}/streams` 的 body = `{payload: {…}}`，而 `payload` 是
  `additionalProperties: true` 的**裸 object**（**无结构**）⇒ 前端**没有**
  `StreamCreate` 的具名 schema 可引用；
- `POST /streams/{id}/state-points` 的 body 同样是裸 object。

⇒ 本批前端只能：① 从**响应** schema `StreamResponse` 取字段名（`StreamBase` 与
`StreamResponse` 同名同义）拼出载荷类型；② 状态点载荷**手写**一份
（`src/api/stream.ts::StatePointPayload`）。

⚠️ 这是**裸载荷闸门**（`check_openapi_payload_coverage.py`）里的已知缺口之一
⇒ 前端类型与后端字段名**没有编译期约束** ⇒ 后端改字段名时前端不会红。

**建议**：后端把 `StreamBase` / `StreamStatePointBase` 提成**具名 schema**
（`CreateStreamRequest.payload` → `$ref`）⇒ 前端直接
`components['schemas']['StreamBase']` ⇒ 同时把裸字段数降 2。

**归属**：下一批（契约面统一收口时一并做）。

## TODO-111: 物流详情三个端点的响应是**裸 dict / 裸 object 数组** ⇒ 前端手写本地类型 🟡

**现状**（2026-11-03 实测）：契约里

- `GET /streams/{id}/properties` ⇒ 裸 dict（`additionalProperties: true`）
- `GET /streams/{id}/state-points` ⇒ 裸 object 数组
- `GET /lineage/{record_type}/{record_id}/graph` ⇒ 裸 dict

⇒ 前端**没有**具名 schema 可引用 ⇒ 本地手写了三份类型
（`src/api/stream.ts::StreamProperties` / `StreamStatePoint` / `LineageGraph`）
⇒ **字段名没有编译期约束**（后端改字段名时前端不会红）。

**建议**：后端把这三条的响应提成具名 schema（`StreamPropertiesResponse` /
`StreamStatePointResponse` / `LineageGraphResponse`）⇒ 前端改用
`components['schemas'][...]` ⇒ 同时把裸字段数降 3。

**归属**：下一批（契约面统一收口时一并做 · 与 TODO-110 同族）。

## TODO-115: 多数物流在 `data_lineage` 里**没有行** ⇒ 血缘 Tab 显示 404 报错 🟢

**现状**（2026-11-03 实测 · P9B-3 评审顺带发现）：
`GET /lineage/streams/{id}/graph` 在该物流没有血缘行时返 **404
`no lineage for record`** ⇒ 前端血缘 Tab 显示的是**错误提示**，而不是
「（无血缘记录）」。

⚠️ dev mock 恒返回 root ⇒ **浏览器 QA 查不出来**（本批 QA 就是这么漏掉的）。

**建议**：后端把「无血缘」当**空图**（200 + `{root: null, upstream: [], downstream: []}`）
⇒ 前端已有的「（无血缘记录）」分支才会走到。

**归属**：下一批（血缘 Tab 收口时一并做）。


## TODO-119: 加锁读只泛化了**物流**一种记录型表 🟢

**现状**（2026-11-03 · P9B-3b · D4 裁决 A 明确**不**在本批做通用化）：
本批把「加锁读」抽成了 `app/services/stream_service.py::
select_stream_for_update()`（物流专用），但仓里还有别的记录型表各自写着
自己的加锁读（如 `app/api/v1/records_actions.py::_locked_select`，锁的是
`PipingResult`，**模型泛型**版本）。

⚠️ **为什么不现在通用化**：通用化要么泛型化（typing 复杂度上升）要么参数化
（可读性下降），且**未来两个模块的需求可能分叉**（有的表要 `populate_existing`，
有的可能不要）⇒ 违背「不为未来可能的复用现在就做通用化」。

**建议**：等 `select_stream_for_update` 在 **2~3 批**里稳定后，再评估抽到
`app/db/locking.py`（届时两个模块的需求是否一致已有答案）。

**归属**：再下一批或独立 ADR（不急）。

## TODO-120: e2e 进批末闸门的**触发条件** 🟢

**现状**（2026-11-03 · P9B-3b D6 裁决 A）：7 个 e2e spec（现有 6 + P9B-3b 新增 1）
**不进批末闸门**，理由是它们依赖 playwright 浏览器（本地未装时无法运行）。
这与 PG 车道**处境类似** —— 但 PG 车道有 `scripts/pytest_pg.sh` 的 **fail-closed**
（PG 没起 ⇒ 明确退出非零）。

⚠️ **核实结论**（2026-11-03）：现有 6 个 spec 最后一次改动在 2026-10-04 ~ 10-28
⇒ **近一个月内活跃**，且有 `fix(e2e): 17/17 全通过` 的提交 ⇒ **有人真的在跑**
⇒ 「写完就忘」的腐化**尚未发生** ⇒ 本批不急着动闸门。

**触发条件**（出现任一情况时，e2e 应进闸门）：
1. 连续 3 批里，**批末 QA 阶段**发现 e2e 相关 bug（说明「靠人记得跑」失效）；
2. 本仓**有了 CI**（与「不做 CI/CD」裁决冲突时需重新裁决）；
3. 有人**主动发起**「e2e 腐化」专项（发现现有 spec 已经不可信）。

**如果触发，怎么做**：
- 新建 `pcs-frontend/scripts/run_e2e.sh`，**fail-closed**（浏览器没装 ⇒ 明确提示
  + 非零退出）；
- 在 `CLAUDE.md` §发布前检查加一行 `bash pcs-frontend/scripts/run_e2e.sh`
  （**发布前检查**，不是「每批闸门」—— 这两个概念在 P9B-3 T0 已经区分过）。

**为什么现在不做**：e2e 的「接线验证」是**低频**的（列表页不常改），而 PG 车道的
「迁移 / 并发验证」是**每次改迁移都需要**的 ⇒ e2e 的紧迫性低一档。

**归属**：触发时再做（本批不做 —— 它需要基础设施：fail-closed 脚本 + 发布前
检查清单更新，与 T0 的 PG 车道同量级）。

## TODO-128: 全测试迁移到 `strict_client` —— 默认 client **测不到守卫缺陷** 🟡

**现状**（2026-11-09 · P9B-4 紧急批次发现）：`tests/conftest.py` 的 `client`
fixture 把 `UserProjectService.check_user_project_access` **mock 成永远 True**
⇒ 任何「端点缺项目守卫」的缺陷在它上面**一个都测不出来**。

⇒ 本批新增了 `strict_client`（**不** mock 守卫）+ `grant_project` fixture，
但**只**新写的守卫测试在用 ⇒ 其余测试**仍然**用默认 `client` ⇒
**其余模块若还有守卫缺口，照样测不出来**。

⚠️ **为什么本批不迁**：裁决「新旧并存」⇒ 「全测试迁移」登记为**独立债项**，
不拖住本批。

**方案**：`client` 逐步改名 `permissive_client`（语义更准），默认改成严格；
需要越权的测试显式请求 permissive 那个。

**触发条件**：下一批要审计**物流面之外**的模块守卫时（那时才会大面积撞上）。

## TODO-129: 物流面**之外**的模块守卫覆盖审计 🟡

**现状**（2026-11-09 · P9B-4 紧急批次只扫了物流面）：
本批**只**审了 `streams.py` / `stream_batch.py` / `lineage.py`。
其它模块**未审**（已知的候选：`config.py` 12 端点、`report_builder.py` 9 端点、
`psychro.py` 13 端点……）⇒ **不能**据此认为它们没问题。

⚠️ 与 TODO-128 是一对：**没有 strict_client 就测不出**（TODO-128），
**没有审计就不知道有多少缺口**（本条）⇒ 一起做才有效。

**归属**：独立技术债。

**T0-A 快照结果**（2026-11-10 · P9B-4 开工前实测 · 关键词
`check_project_access_or_404` / `check_record_access_or_404` / `has_project_access`）：

| 分类 | 模块 | 结论 |
|---|---|---|
| 有项目守卫 | `streams.py` · `lineage.py` · `stream_batch.py`（service 层）· `util.py` · `pipe_*` · `checklist` · `open_channel` · `flare` · `filtration` · `cost_est` · `cool_tower` · `stream_symbols` · `psychro` · `imports` · `deliverables` · `records*` · `heat` · `flash` · `change_impact` · `report` · `projects` · `workspaces` · `workflow_progress` · `supplier` · `sep_equip` · `pump` · `pipe_net` · `equip_list` · `cv` · `audit` · `record_edits` · `notifications` | ✅ 物流面**已覆盖** |
| **无项目守卫（缺口）** | `vessel.py`（1）· `psv.py`（1）· `restriction.py`（2）· `thermosiphon.py`（1）· `report_builder.py`（9）· `locks.py`（3） | 🔴 这几个模块**只有角色 ACL**，**不按项目隔离** ⇒ 计算结果/报表定义/编辑锁**可能跨项目** ⇒ **本条 TODO 的具体清单** |
| 不适用 | `config.py` · `meta.py` · `auth.py` · `admin_users.py` · `system_settings.py` · `user_projects.py` · `mock_auth.py` · `health.py` · `ws.py` · `common.py` · `equip_lib.py` | 非项目数据面 / 本身即 ACL 管理面 |

⚠️ `vessel/psv/restriction/thermosiphon` 的 api 层 **0 处** `project_id`
⇒ 不是「忘了加守卫」而是「**结果记录根本不带项目维度**」⇒ 补守卫要先想清楚
「项目归属从哪来」⇒ 审计工作量比「加一行守卫」大。

**归属**：独立技术债。

## TODO-130: `user_project_service.py` 的既有 ruff 债（F821 / UP035 / UP037） 🟢

**现状**（2026-11-09 顺带发现 · **非本批引入**）：
`uv run ruff check app/services/user_project_service.py` 报 3 条 ——
`F821 Undefined name 'datetime'`（`_now()` 的返回标注 `"datetime.datetime"` 而
`datetime` 未导入）、`UP035`（`Sequence` 应从 `collections.abc` 导入）、
`UP037`（多余的引号）。

⚠️ 本批**只**在同文件追加了新函数 ⇒ 按「不顺手改无关代码」的纪律**没动**它们。

**归属**：独立技术债（顺手可修，但别混进功能批）。

## TODO-131: 部署前置 —— 各环境必须先 seed 授权行，否则**全站物流 404** 🔴

**现状**（2026-11-09 · P9B-4 紧急批次 T0 的结论）：补上物流面项目守卫后，
**任何没有 `UserProject` 授权行的用户访问任何物流端点都 404**。

⇒ 仓里**没有一条能持续产生授权行的路径**（除了 SYSTEM_ADMIN only、
前端无页面的 `POST /user-projects/grant`）⇒ 本批交付了两条：
① `POST /projects` ⇒ **自动授权创建者**；② `scripts/seed_user_project_access.py`
（幂等，**用户不在 `users` 表时建行**）。

⚠️ **mock 登录不落 `users` 表**（ADR-0046 §③b）⇒ dev 环境的 alice / bob /
carol / dan **必须靠 seed 脚本**拿到授权 ⇒ **上线前每个环境跑一次**：

```bash
cd pcs-backend
uv run python scripts/seed_user_project_access.py --username alice --project <该环境的项目 UUID>
```

⚠️ **生产库的用户必须先在 `users` 表里存在**（FK 约束）⇒ 走真实登录路径即可。


## TODO-137: 遗留账号（`user_id` ≠ 派生值）的授权迁移 —— 一次性运维动作 🟡

**现状**（2026-11-10 · ce-code-review 的 **#10** 修复引入的**新前置**）：

`ensure_user_row` 现在**只认 `user_id`** ⇒ 若某个用户名已被一条
**`user_id` 与派生值不同**的遗留行占着（`users.username` 唯一 ⇒ 派生 id 与遗留 id
**不能并存**）⇒ 建行会撞唯一约束 ⇒ **显式 409 `USER_ID_CONFLICT`**（不再静默替换）。

⇒ 需要**一次性迁移**把遗留账号的授权转到派生 id。**核查结果**：开发库
`users` **0 行**、`user_projects` **0 行**、**0 条** id 与派生值不一致的行
⇒ **当前没有这样的遗留行** ⇒ 本条是**预防性**的。

**迁移步骤**（顺序不能错 —— FK 约束）：

```sql
-- ① 遗留行让出 username（否则派生 id 的行建不出来）
UPDATE users SET username = 'legacy:' || username
 WHERE user_id <> uuid5(namespace_dns, username);   -- ← 派生函数在应用层，见下
-- ② 建派生 id 的行（username 用原名，roles 按真实登录路径补）
-- ③ 把授权转到派生 id
UPDATE user_projects SET user_id = <派生 id> WHERE user_id = <遗留 id>;
```

⚠️ 派生 id 的**唯一**算法在 `app/services/token_issuer.py::derive_user_id`
（`uuid5(NAMESPACE_DNS, username)`）⇒ 迁移脚本必须**调用它**，不要另抄一份。

**归属**：一次性运维动作（代码侧已 fail-loud 护住）。

## TODO-138: `TwoPhaseResult` **没有 `project_id`** ⇒ 无法登记血缘守卫 🟡

**现状**（2026-11-10 · P9B-4 体验批 T0-D 的注册完整性快照实测）：
`app/services/calc_lineage.py::RECORD_TYPE_REGISTRY` 的 **21 个类型**里，
`TwoPhaseResult`（表 `two_phase_results`，pk `two_phase_id`）**没有 `project_id`**
⇒ 它**能写出 `data_lineage` 行**，但守卫**拿不到项目归属**
⇒ 无法登记进 `LINEAGE_GUARDED_RECORD_TYPES`
⇒ 在「未登记类型 fail-closed」下**永久 404**（该类型的血缘查不到）。

⚠️ 兄弟类型（20 个）都有 `project_id`（含 `TaggedRecordMixin` 的）⇒ 这是**单点缺列**。

**归属**：独立技术债（改 schema = 要迁移 ⇒ 不进 P9B-4）。

**建议改法（2026-11-10 委员会裁决）**：✅ **不补列** ⇒ 明确「**该类型不提供血缘查询**」：
- 守卫注册表里**不登记**它；
- 血缘端点对它 ⇒ **404**（与「未登记类型」**同形**）；
- **SPEC §7.7.2 注明「`TwoPhaseResult` 不支持血缘查询」**；
- 本条**只留触发条件**，不排期。

⚠️ **理由**：补列的成本（迁移 + 回填 + 检查所有写入点）**大于**收益（血缘需求
**未验证**）⇒ fail-closed 是正确的默认；且「**不提供**」比「提供了但永远 404」
更清晰（后者让用户困惑「为什么这个类型查不到」）。

**触发条件**：将来有用户报「查不到两相流的血缘」⇒ 重新评估补列。

⇒ 落地批次：**P9B-4 体验批 T0-D**（fail-closed + SPEC 注明）；补列若需要 ⇒ 独立批。

✅ **fail-closed 部分已落地**（2026-11-11 · T0-D）：`TwoPhaseResult` **不登记**
⇒ 血缘端点对它 **404**（与「未登记类型」同形）⇒ SPEC §7.7.2 已注明
「`TwoPhaseResult` 不支持血缘查询」。⇒ **本条只剩「补列」这一半**（未排期）。

## TODO-139: 物流来源 vs 计算来源是不是**同一个概念** ⚪

**现状**（2026-11-10 · P9B-4 体验批 T0-D 的合成 root 带出的设计问题）：
- `streams.source`（4 值：`MANUAL` / `SIM_IMPORT` / `EXCEL` / `LAB`）——
  「这条物流**怎么进系统**的」；
- `data_lineage.source`（写入方实际写 `CALC` 等）—— 「这条记录**怎么算出来**的」；
- 两者在血缘图的「来源」列里**并存**（合成 root 的 `source` 取前者，血缘行取后者）
  ⇒ 用户看到同一列有两种词 ⇒ 困惑。

**问题**：这两个是不是同一个概念？
- **是** ⇒ 应该统一词表；
- **不是** ⇒ 应该在 UI 上明确区分。

**本批的处置**：⚪ **不裁决**（更大的设计问题）⇒ 本批的做法（前端「来源」列**只显示
计算来源** + root 行把物流来源放 **tooltip** + **SPEC §7.7.2 注明两套词表**）
在**两种情况下都成立** ⇒ 不受本裁决影响；若将来决定统一 ⇒ 前端改一行（去掉 tooltip），
**不是架构级改动**。

**触发条件**：用户反馈「来源列显示混乱」⇒ 重新评估。

⇒ 归属：独立设计债（不进 P9B-4）。

## TODO-141: 全量测试迁移到 `strict_client`（守卫测试的唯一入口） 🟡

**现状**（2026-11-11 · P9B-4 紧急批次的遗留）：默认的 `client` fixture 把项目
守卫 **mock 成永远 True** ⇒ 「端点缺项目守卫」这类缺陷在它上面**一个都测不出来**
⇒ 守卫测试**必须**用 `strict_client`（不 mock 守卫 + 需先 `grant_project`）。

⚠️ **风险**：新写的用例若图省事用 `client` ⇒ 守卫缺陷**静默通过**。

**建议改法**（下一批）：
- 逐步把**带项目维度的**用例迁到 `strict_client`；
- 或加一条**架构守卫**：新写的 `tests/api/v1/**` 文件里若出现 `client` fixture ⇒
  需显式写明理由（白名单 + 理由）。

⇒ 归属：独立技术债（不进本批）。

## TODO-142: 前端 review-log 的 `rowKey` 可能撞（同一事务两行） ⚪

**现状**（2026-11-11 · 上批 ce-code-review 的 residual risk D3）：校核记录列表的
`rowKey` 若用**时间戳**（或转移 id 之外的值）⇒ **同一事务里的两条转移**可能同值
⇒ React `key` 重复 ⇒ 复用错行。

**优先级**：低（不影响数据正确性，只影响极端情况下的渲染）。

⇒ 归属：独立技术债（不进本批）。

## TODO-143: 两处**缺索引**的聚合查询（要迁移 ⇒ 独立批） 🟡

**现状**（2026-11-11 · P9B-4 体验批 T2 的整批评审 Minor #1 / #2）：

| # | 位置 | 问题 | 影响 |
|---|---|---|---|
| 1 | `streams.upstream_stream_id`（`app/models/project.py:442`） | **无索引** | `reference_counts` 的第一条聚合（下游物流数）⇒ **每次列表请求全表扫** |
| 2 | `data_lineage.source_ref_type` / `source_ref_id`（`app/models/system.py:46-47`） | **无索引** | 物流血缘 Tab 的「按源引用查」⇒ **每次开 Tab 扫 `data_lineage` 全表**（该表**只增不删**） |

⚠️ 两条都要**改 `alembic/versions/*`** ⇒ **本批不动迁移**（P9B-4 的硬约束）
⇒ 独立批处理（**P10-D** · 压测驱动 ⇒ 同 TODO-104）。

✅ **原第 3 条（「`reference_count` 未按项目过滤」）已闭**（2026-11-11）——
见下节。

⇒ 归属：独立技术债（不进本批）。

### 已闭：TODO-143-3「`reference_count` 是否按项目过滤」 ✅（Q7 = ① 只算同项目）

**裁决**（2026-11-11 · 用户裁决 **Q7 = ① 只算同项目**）：`reference_count`
**只统计同项目**的引用（别的项目的引用**不计入**）。

**已落地**（**零迁移** —— `Stream.project_id` 与 `FlashResult.project_id` 两列
本来就存在）：
- `StreamService.reference_counts(db, ids, *, project_id)` —— `project_id`
  是**必填关键字参数**（没有默认值 ⇒ 忘传编译期就红）
  ⇒ 两条聚合各带一个 `project_id` 谓词；
- `list_project_streams` 传 `project_id=project_id`（路径参数）；
- 用例：`test_reference_count_excludes_cross_project_downstream_streams` /
  `..._excludes_cross_project_flash_results` /
  `..._still_counts_same_project_references`（三条全 RED→GREEN）。

⚠️ **今天的数值一个都没变** ⇒ 这不是修现存 bug，是**前瞻性保护**：
`create_outlet_stream`（强制 `source.project_id == project_id`）与
`flash_persist`（用 `stream.project_id`）都保证**同项目**
⇒ **跨项目引用造不出来**；而 DB 层**允许**
（`streams.upstream_stream_id` 只是 FK 到 `streams.stream_id`，没有 project
约束）⇒ 过滤必须落在**查询**上，不能指望写入方。

⇒ SPEC §7.7.1 已同步（V2.15）。

## TODO-144: WS 握手拒绝的**原因**到不了客户端（accept 前 close ⇒ HTTP 403） 🟡

**现状**（2026-11-12 · P9B-4 评审 **#24** 的**剩余一半** · 评审给的两个选项里
选了**最小方案**，传输层那一半未做）：

`app/api/v1/ws.py` 的握手失败路径调 `websocket.close(code=1008, reason=<code>)`
**且是在 `accept()` 之前** ⇒ 按 ASGI 规则，服务端会把它当成 **HTTP 403 握手拒绝**
⇒ close code（1008）与 reason（`USER_DISABLED` / `MISSING_TOKEN` /
`INVALID_TOKEN` / `HANDSHAKE_FAILED`）**到不了客户端**
⇒ **每一种拒绝在客户端看来完全一样**。

⚠️ **更隐蔽的一半**：Starlette 的 `TestClient` 会把 accept 前的 close **还原成**
`WebSocketDisconnect(1008)` ⇒ **测试观察到的是一个部署里并不存在的拒绝语义**
⇒ 「绿灯的测试，nobody 能观测的通道」。
⇒ 本批已做的（最小方案）：**原因写进日志**（`logger.warning`）
+ docstring **不再**承诺「客户端能区分拒绝原因」+ 契约测试旁加注。

**证据**：`app/api/v1/ws.py::notifications_ws` 的 docstring（§「拒绝原因只对日志可见」）
+ `tests/api/v1/test_ws_notifications.py::test_ws_requires_a_token`（断言 1008）。

**要真正做到「原因到达客户端」** ⇒ 必须 **先 `accept()` 再 `close(code, reason)`**
⇒ 客户端会看到「**连上了又断**」⇒ 与本模块 docstring 原来的论证
（「先 accept 再关会让前端把它记成『连上了但没消息』」）**直接冲突**
⇒ **这是传输层的设计裁决**，不是 bug 修复 ⇒ 需要**产品/架构裁决**：
- **选项 A**（本批现状）：拒绝原因**只对日志可见** ⇒ 客户端只能看到
  「连不上」，**不能**区分「被停用」与「token 坏了」；
- **选项 B**：先 accept 再 close ⇒ 原因到达客户端 ⇒ 客户端要能处理
  「刚连上就断」这一状态（前端目前**没有** WS 消费者）。

⚠️ **暴露面**：本仓**没有** `/api/v1/ws/notifications` 的前端调用方
⇒ 选项 B 的前端配套成本目前是 **0** ⇒ 若将来接上前端，**趁那时**一起做。

**触发条件**：前端开始消费通知 WebSocket，且需要区分拒绝原因
⇒ 那时做选项 B（**含**前端「连上即断」的处理）。

⇒ 归属：独立设计债（不进 P9B-4 评审修复批）。

## TODO-145: 遗留账号行上，登录路径与每请求路径的停用判定**相反** 🟡

**现状**（2026-11-12 · P9B-4 评审 **#10** 逼出来的**诚实边界**）：

停用判定**两个入口**、**两个查表键**（**刻意的** —— 登录时只有用户名）：

| 入口 | 查表键 | 停用的遗留账号 |
|---|---|---|
| 登录（`token_issuer.issue_tokens`） | `users.username` | **查到** ⇒ **拒** ✅ |
| 每请求（`current_actor` / `current_user`） | `users.user_id` | **查不到** ⇒ **放行** ❌ |

⇒ 一个 `user_id` ≠ 派生值、且 `status = DISABLED` 的**遗留账号**：
**登录被拒，但手里已发出的 token 仍能访问** ⇒ 「停用即刻」在它身上**不成立**。

**证据**：`app/services/user_status_service.py` 的模块 docstring（「查表键不同是
刻意的」＋「两条路径在遗留行上会给出相反结论」）+ ADR-0046 §⑤ 同段
+ `tests/services/test_user_status_service.py::test_legacy_row_is_denied_at_login_but_allowed_by_the_actor_layer`
（**钉住现状**，不是认可它 ⇒ 将来谁改成按 username 查 ⇒ 该测试会红
⇒ 那时正好该把本条与 docstring 一起更新）。

⚠️ **暴露面很小**：遗留行的 `user_id` 对不上 ⇒ `ensure_user_row` 与项目授权行
都认不出他 ⇒ 物流面**处处 404**（TODO-137 的既有结论）⇒ 他能到达的只有
**不按项目**的端点（`/auth/me`、6 个 `/meta/*`）。

**建议改法**（**独立批** · 与 TODO-137 的迁移**同批做**最省事）：
- **首选**：TODO-137 的**一次性迁移**把遗留行转成派生 id ⇒ **该形状不再存在**
  ⇒ 本条随之消失（**不需要改代码**）；
- **次选**（若迁移推迟）：每请求路径**按 `username` 兜底查一次**
  （token 的 `sub` 就是用户名）⇒ 两条路径结论一致 ⇒ ⚠️ 代价 = **多一次查询**
  + 与「无行 ⇒ 放行」的 mock 边界要一起想清楚（mock 的 `sub` 是 mock 用户名
  ⇒ 查不到行 ⇒ 仍放行 ⇒ 边界不变）。

⚠️ **不要**把 actor 层的查表键**直接**改成 username ⇒ 那会让「按 `user_id`
授权」（`user_projects` 的 FK 是 `user_id`）与「按 username 判状态」**分叉**
⇒ 反而多一处口径。

⇒ 归属：独立技术债（**与 TODO-137 合并处理**最省事）。

---

## TODO-146: AI 可选依赖（langchain / ollama / vllm）本批未加 —— 待网络与独立批次 🟡

**现状**（2026-11-12 · P10-A 批末 · SPEC 偏离登记 **D19**）：

SPEC §3.2.1(8) 要求在 `pyproject.toml` 加 `[project.optional-dependencies] ai`
并让「默认环境不装这三个包」。**本批未加**，实测原因：

- `uv lock` 解析的是**一份版本集** ⇒ 把 `vllm` 加进去会把**默认环境**的
  `numpy` 一并升级（实测触发了 15.8MiB 的 numpy 重装）
  ⇒ 与「optional 组不影响默认环境」的意图**相反**；
- 且重装会在批中动到**全仓 5700+ 测试共用**的 venv ⇒ 风险与收益不成比例。

**已回滚**（`pyproject.toml` / `uv.lock` 复原，`uv lock --check` 通过、
`uv sync --frozen` 干净）。

**替代方案（已生效）**：架构守卫改为**扫源码**（不依赖包是否安装）
⇒ 目标（AI SDK 只能从唯一出口出去）照样达成。

**何时做**：网络可用 + 单独一批；**先验 `numpy` 不被连带升级**。

---

## TODO-147: pgvector 扩展与 `document_chunks.embedding_vector` 的维度（待裁决） 🟡

**现状**（2026-11-12 · P10-A · SPEC 偏离登记 **D3 / D6**）：

- SPEC §3.2.1(2) 要求 `CREATE EXTENSION IF NOT EXISTS vector`；
  但 `postgres:18-alpine` **不带** vector 扩展，且仓里
  `document_chunks.embedding_vector` 是 **JSONB**（不是 vector）
  ⇒ 扩展建了**无处可用** ⇒ **本批不建**、compose / CI **不换镜像**。
- SPEC §4.1 的 `document_chunks` 字段（`document_id` / `content` /
  `source`）与仓里既有的 7 字段**完全不同** ⇒ 本批**不动这张表**。

**待裁决**：向量维度（SPEC P10-OPEN-002；OpenAI Embedding 是 1536，本地模型
未必相同）⇒ 裁决后一并做「建扩展 + 改列类型 + 迁移」。

---

## TODO-148: 内网 CIDR 清单待 IT 提供（只影响真实启用，不影响机制） 🟢

**现状**（2026-11-12 · P10-A · SPEC P10-OPEN-010）：

本批只做**机制**：`INTERNAL_CIDRS` 可配 · 非法即启动报错 · 启动时校验
（AI 开着时 endpoint 必须解析到内网）。**清单本身不影响本批交付**。

**何时要**：真开 AI 之前 ⇒ IT 给出内网网段 ⇒ 写进部署 env。

---

## TODO-150: AI 端点的权限模型待定（现在任何已认证用户都能调，但一律 501） 🟡

**现状**（2026-11-12 · P10-A）：

SPEC §3.2.1(1) 只写了 `Depends(current_user)`，**没说什么角色能调**
⇒ 本批按「任何已认证用户都能调（但一律 501）」实现
（⇒ 审计表能记下「谁在什么时候探过 AI 端点」）。

**何时定**：真开 AI 之前 ⇒ 谁该能用 AI（按项目角色？按全局角色？）须裁决
⇒ 否则一开就是「全公司都能调」。

---

## TODO-151: FastAPI 的 422 信封对深层嵌套 JSON 自己就 RecursionError（既有通用缺陷） 🟡

**现状**（2026-11-13 · P10-A 评审修复批 · bug-2161）：

FastAPI 在**请求体不合法**时，把**整个非法输入**回显进 422 信封
⇒ `jsonable_encoder` 对 ~1000 层嵌套的 JSON **自己**就 `RecursionError`
⇒ 异常**逃出 app** ⇒ 客户端拿到 **500**（而不是 422）。

⚠️ **与 AI 审计路径无关** —— **任何端点**收到深层 JSON 都一样
⇒ 本批的 #17（深层 body 也要留审计行）用例**只钉审计契约**
（审计行必须落），把响应码放宽到 `422 / 500`。

**为什么现在登记而不是现在修**：修它 = 改全局异常处理（截断回显深度 /
给 422 编码加递归上限）⇒ 影响**所有端点的错误信封** ⇒ 属**跨批**改动
⇒ 本批不动。

**何时做**：下一批（任一）碰到「错误信封」主题时 ⇒ 给 422 编码加递归上限
（或截断回显的嵌套深度）⇒ 并加一条**跨端点**的回归用例
（任意端点 + 深层 body ⇒ 不是 500）。

---

## TODO-152: E2E 车道进 CI（PR 跑关键 / nightly 跑全量） 🟡

**现状**（2026-11-13 · P10-B 计划的 /plan-eng-review · 偏离登记 D25）：

SPEC §3.2.2 的验收写了两条：「E2E 在 CI 中可自动执行」+「PR 跑关键 E2E，
nightly 跑全量 E2E」⇒ 而本仓的既有裁决是「**不新建 CI 流水线**」
⇒ **两边冲突** ⇒ P10-B 只给**本地**车道入口（`pcs-backend/scripts/pytest_e2e.sh`）
⇒ 该验收项**本批不满足**（**不假装满足**）。

**为什么重要**：E2E 只在本机跑 ⇒ **没人跑 ⇒ 很快腐烂**
⇒ 而腐烂的 E2E 比没有 E2E 更坏（它会给人「已覆盖」的错觉）。

**不新建流水线 ≠ 不能扩面**：现有 `.github/workflows/check-api-drift.yml`
已在**全新 PG** 上跑 alembic + API drift ⇒ 加一个 E2E job 是**扩现有 workflow**
⇒ 裁决「不新建流水线」是否允许这么做（这是**唯一**要先定的点）。

**何时做**：**P10-F**（生产就绪评审）⇒ 届时一并裁决：
① 「不新建流水线」是否允许在现有 workflow 里加 job；
② 「关键 E2E」是哪几条（建议：权限矩阵 + 状态机路径 + AI 审计两段 = Review Focus 五条）；
③ nightly 跑全量 18 场景的耗时是否可接受。

---

## TODO-153: AUTH-E2E-11/12（`TEST_VIEWER` 看测试报告页） 🟡

**现状**（2026-11-13 · P10-B 计划的 /plan-eng-review · 偏离登记 D24）：

SPEC §3.2.2 的权限矩阵共 12 条 ⇒ P10-B 做完了 **10 条**（AUTH-E2E-01~10）
⇒ 剩 **2 条**：AUTH-E2E-11（`TEST_VIEWER` 看测试报告页 ⇒ 200）
与 AUTH-E2E-12（`DESIGNER` 看测试报告页 ⇒ 403）。

**为什么本批不做**（两条，都不是「懒得做」）：
① `TEST_VIEWER` **这个角色不存在** —— 项目内角色现有 6 值
（`DESIGNER` / `CHECKER` / `APPROVER` / `REVIEWER` / `VIEWER` / `PROJECT_LEAD`）
⇒ 它是**新增第 7 个**，而 SPEC 说它要「**在 P9 权限矩阵登记**」⇒ 改的是 P9 的登记表；
② **测试报告页**本身属 **P10-C**（部署与可观测性）⇒ 本批做它 = 提前施工
⇒ 而页面形态在 P10-C 才定 ⇒ **大概率返工**。

**何时做**：**P10-C**（建测试报告页时一并做）⇒ 那时：登记角色 → 建页 →
补两条 E2E 用例 ⇒ 权限矩阵这条验收才**整条**闭合。

---

## TODO-154: E2E 流程级数据落在 `pcs_pgtest` 的 public schema 🟢

**现状**（2026-11-13 · P10-B 计划的 /plan-eng-review · D3 的副产物）：

P10-B 的真后端 Playwright 通道的后端连的是 **`pcs_pgtest` 的 public schema**
⇒ 而 E2E 车道的数据在**隔离 schema** 里 ⇒ 两个房间不通
⇒ ⇒ **flows 种子也要在 public schema 跑一遍**（脚本幂等）
⇒ 于是 `pcs_pgtest` 的 public schema 里会多一份**流程级测试数据**
（6 个 `e2e-*` 用户 · 1 个项目 · 交付物 · 签署矩阵 · 报表定义）。

**风险**：低（`pcs_pgtest` 是**测试库**，不是 `pcs` 开发库）
⇒ 但**以后有人查这个库**时会看到它们 ⇒ 分不清是业务数据还是测试残留。

**何时做**：发布前检查清单**目前没有 `pcs_pgtest` 这一项**
⇒ 写清单时一并加：① 「public schema 里的 `e2e-*` 数据是测试残留，不是业务数据」
⇒ ② 一个清理脚本（或一条 `TRUNCATE` 清单）。

---

## TODO-155: 「真过 Redis + ARQ worker」的那一段没被端到端覆盖（AI 审计 **+ 报表生成**） 🟡

**现状**（2026-11-13 · P10-B 计划的 /plan-eng-review · D6 的副产物；
**2026-11-16 扩到报表** —— hermes 第三视角的 P0-1）：

⚠️ **报表生成也在这条债里**（`E2E-009` / `E2E-015`）：
`POST /api/v1/report/generate` 走 `create_pool(RedisSettings.from_dsn(...))`
（`app/api/v1/report.py:178`）⇒ **Redis 不可达 ⇒ 入队失败 ⇒ 就地把那行标 `FAILED`**
⇒ 「轮询到 `SUCCESS`」**不可达** ⇒ P10-B 因此改用**两段式**
（202 受理 + **直调** `generate_report_task` / `execute_definition_task`）
⇒ ⇒ **「入队 → Redis → worker 消费 → 改状态」那一段仍未被端到端覆盖**
⇒ 与 AI 审计那条**同一个修法**（一起起 Redis + worker 就都覆盖了）。

P10-B 的 E2E-017 采用**两段式**：① spy `enqueue_ai_audit_log`（断「请求产生了审计」）
② 直调 `app.workers.ai_audit_tasks` 的写库任务（断「落库这一段是对的」）
⇒ **两段各自被钉住**，但「**真的经过 Redis 队列 + ARQ worker**」那一段
**没被端到端覆盖** ⇒ 断在队列上时（Redis 挂了 / worker 没注册任务 /
job 被 ARQ 当场判死），这两条断言**照样绿**。

**为什么重要**：审计链路断在队列上的后果正是 SPEC 反复强调的那句
——「审计表对 AI 调用失明」⇒ 而中间件入队失败是**静默降级**
（`arq_queue.py` 记 warning 不抛）⇒ 没有端到端用例就没人知道。

**何时做**：**P10-F**（与 TODO-152 同批做最划算 —— 都需要「车道里能起 worker」）
⇒ 补法：在 E2E 车道里真起 Redis + `app/workers/worker.py` ⇒ 走完整链路
⇒ **一次补两条**（AI 审计 + 报表生成）⇒ 别只补 AI 审计那条。

## TODO-158: 报表审计哈希的**根因未闭环**（bug-2165 的残余） 🔴

**现状**（2026-11-16 · P10-B 的 T4 撞出来的）· **2026-11-17 关闭 · `cebf48d`**：

⚠️ **真根因不是「对象脱钩」** —— 那是当时的**误判** ⇒ ⇒ 真因是
`row.data_version = digest` 那行**写在 `dup` 分支的 `return` 之后** ⇒
⇒ **永不可达** ⇒ ⇒ 存活的那行**从没带过** `data_version`。
⇒ ⇒ **A1 裁决**：端点改读 `content_hash`（NOT NULL · 每行都有值 ⇒ 不需 backfill）·
⇒ ⇒ `data_version` 保留它自己的语义（「登记时冻结的数据版本」）⇒ ⇒ 任务侧
**不再**写它 ⇒ ⇒ E2E-009 的 `pytest.xfail()` **已去掉**（改成真断言）⇒ ⇒ 车道 **0 xfailed**。

`GET /api/v1/report/{report_file_id}/hash` 在**生成的**报表上**恒返回空哈希**
⇒ 已在任务侧补 `row.data_version = digest`（赋值确实执行）⇒
**但库里仍是 NULL** ⇒ 说明**那个对象与被 flush 的行不是同一个**
⇒ ⇒ **E2E-009 里那条断言现在标 `pytest.xfail`**（不假装绿）
⇒ ⇒ 一旦有人定位到「对象脱钩」的真因并修好 ⇒ 那行会**自然变成真断言**。

**为什么重要**：「审计要完整哈希」这条需求今天**实际是空的**
⇒ 报表的审计链**追不回内容**。

**何时做**：**P10-C**（或任何一批碰 `app/workers/report_tasks.py::_mark_pending`
/ `_finalize` 时）⇒ 先查「`_mark_pending` 返回的对象」与「被 flush 的行」
是不是同一个（⇒ 怀疑 `session.refresh` / 局部 `row` 拷贝）。

**归属**：P10-C

## TODO-161: 管道链计算**在运行时写配置表**（占位管级 `CS-STD`） 🟡

**现状**（2026-11-16 · P10-B 的 E2E-003 撞出来的）· **2026-11-17 关闭 · `062110a`**：

⚠️ **两条路都走了** ⇒ ① 新迁移 `p10_002` 用 **`ON CONFLICT (class_id) DO NOTHING`**
种 `CS-STD`（⇒ 并发安全）⇒ ② lifespan 启动时**幂等 ensure** 兜底（老库没跑迁移 /
行被删）⇒ ⇒ **请求路径不再写配置主表** ⇒ ⇒ 「计算端点改配置表」这个味道**没了**
⇒ ⇒ 并发首算撞主键那条（评审 #1）随之**作废**。

`app/services/pipe/pipe_chain_persist.py` 写 `piping_results` 时用
`material_class="CS-STD"` ⇒ 而该列是**指向 `pipe_classes.class_id` 的外键**
⇒ ⇒ 迁移里**不种**这条配置 ⇒ ⇒ 插记录撞 FK ⇒ 端点 500
⇒ ⇒ P10-B 的修法是**运行时兜底建那条占位管级**（幂等：先查再建）。

⚠️ **但「计算端点改配置表」本身是味道** —— 配置表的行应由**配置流程**（或
迁移种子）产生，而不是被一个计算请求顺手写出来 ⇒ ⇒ 两台机器并发首跑
可能撞唯一约束 ⇒ ⇒ （现在是先查后插，**并发下仍可能撞**）。

**何时做**：**P10-C** ⇒ 要么把占位行改成**迁移种子**（⇒ 过 ORM 漂移核对），
要么给兜底加**幂等的 upsert**（`ON CONFLICT DO NOTHING`）⇒ 并发安全。
⇒ ⚠️ 迁移种子的话注意：`pipe_classes` 是**配置表**（CLAUDE.md 的漂移盲区）。

**归属**：P10-C

## TODO-162: 公式编辑器的参数表用了 antd `rowKey` 回调的 **index** 参数 🟡

**现状**（2026-11-17 · P10-B 评审 #7 的路由扫描撞出来的）：

`src/pages/config/FormulaEditorPage.tsx:241` 写
`rowKey={(_r, idx) => String(idx)}` ⇒ antd **5.29 起弃用**回调的 `index`
参数 ⇒ 控制台出**错误级**告警：

```
[antd: Table] `index` parameter of `rowKey` function is deprecated.
There is no guarantee that it will work as expected.
```

⚠️ **当前不炸**（antd 5 仍会传 index）⇒ 但 antd 6 可能**移除** ⇒ ⇒
参数表的行 key 会变成 `undefined` ⇒ 行渲染错乱。

⚠️ **为什么不能简单改成 `rowKey={(r) => r.name}`** —— 参数行的 `name`
**允许为空**（新建的行）且**允许重复** ⇒ antd 会报「Duplicate row key」
⇒ 换成另一种告警。⇒ ⇒ 仓里已有同款解法
（`src/pages/sim/tabs/StreamStatePointsTab.tsx`：**取数时**把 key 算好 ⇒
`rowKey="key"` 用字符串形式）⇒ 参数表要改成同款（**给每行一个内部 key**
⇒ ⚠️ 不能加进 `FormulaParam` 公开形状 ⇒ 会漏进保存的载荷）。

**何时做**：**P10-C**（前端改造）⇒ 改造后**删掉**路由扫描里那条白名单
（`e2e/real_backend_route_sweep.spec.ts::ALLOWED_CONSOLE_ERRORS`）。

**归属**：P10-C

**2026-11-17 · P10-F 的 F2-T4 关闭** ⇒ ⇒ **根因已消除**（不是「页面改好了」）：

- **组件**：`FormulaEditorPage` 的参数表 `rowKey` 改成**只收一个参数**的回调
  （`rowKey={(r) => r.__rowKey}`）⇒ ⇒ 行**自带稳定 key**（内部类型
  `EditableParam`）⇒ ⇒ **出参时剥掉**（`toPublicEditor`）⇒ ⇒
  `FormulaEditor`（公开形状 / 保存的载荷）**不受影响** ⇒ ⇒ **无契约变化**。
- **棘轮**：`tests/pages/rowKey_contract.test.ts` 扩展到**函数形式**
  ⇒ ⇒ 判据 = **回调的参数个数**（antd 的告警判据是 `rowKey.length > 1`
  ⇒ ⇒ **参数叫 `i` / `pos` 也一样告警** ⇒ ⇒ 断名字不够）⇒ ⇒
  ⇒ **一处复发即红**（而不是一页一断言）。
- **白名单**：`ALLOWED_CONSOLE_ERRORS` **删掉那条** ⇒ ⇒ 现在这张表
  **是空的** ⇒ ⇒ 真后端通道的路由扫描**照旧全绿** ⇒ ⇒
  ⇒ 这就是「组件修好后删白名单条目」这条纪律的**验证本身**。

## TODO-163: compose 的 `migrate` / `seed` 两个写者**不在车道互斥锁内** 🟡

**现状**（2026-11-17 · P10-B 评审 #15 的第 ① 步）：

`scripts/pytest_pg.sh` 的车道互斥锁只约束**走进这个脚本的进程**
（PG 车道 / E2E 车道）⇒ ⇒ 而 compose 的两个**一次性写者**
（`migrate` · `seed`）**不经过这个脚本** ⇒ ⇒ 它们与车道**并发**时：

- `migrate`（`alembic upgrade head`）与车道在**同一个库**上建 schema
  ⇒ ⇒ DDL 互相等锁 ⇒ ⇒ 表现是「**偶发卡住**」（不是报错 ⇒ 极难定位）；
- `seed` 往 **public schema** 灌数据 ⇒ ⇒ 与车道的隔离 schema 不冲突，
  但**同库同表** ⇒ ⇒ 可能撞唯一约束。

**为什么本批只做了一半**（评审 #15 的裁决是「最小可行三步」）：

① compose 的两个服务要进**同一把锁** ⇒ ⇒ 容器里得 `flock` 同一个文件 ⇒ ⇒
需要 ① 把锁目录**以可写方式**挂进容器（`./pcs-backend:/app:ro` 是**只读**的）
② 容器镜像里要有 `flock`（`util-linux`）—— 本机**无外网** ⇒ 镜像既不能构建
也不能在运行时 `apt-get` ⇒ ⇒ **改完无法验证** ⇒ ⇒ 留到 P10-C（有网环境）。

⇒ ⇒ 本批已做的两步（**可验证**）：
- **第 ② 步**：默认锁路径从 `/tmp/pcs-pgtest-lane.lock` 改**项目内**
  `pcs-backend/.tmp/lane.lock` ⇒ ⇒ `/tmp` 会被清理 ⇒ inode 换新 ⇒ ⇒
  正在跑的车道的锁对新车道**不可见** ⇒ ⇒ 互斥**静默失效** ⇒
  （`.gitignore` 已加 `pcs-backend/.tmp/`）
- **第 ③ 步**：守门测试补一条「**默认路径**下两 lane 互斥」的**子进程实测**
  （`tests/scripts/test_pytest_pg_gate.py::test_two_lanes_are_mutually_exclusive_on_the_default_path`）
  ⇒ ⇒ 之前只测过「覆盖过的锁文件」⇒ ⇒ **默认路径从没被测过**

**何时做**：**P10-C**（有网环境 ⇒ 能构建镜像 ⇒ 能验证 compose 侧改动）

**2026-11-17 · P10-F 的 F2-T3 部分关闭** ⇒ ⇒ **宿主侧**已进同一把锁：

- `scripts/compose_test_stack.sh` 现在**先抢车道锁**（与 `scripts/pytest_pg.sh`
  **同一把**、**同一路径口径** `${BACKEND_DIR}/.tmp/lane.lock`、同样支持
  `PCS_PGTEST_LANE_LOCK` 覆盖）⇒ ⇒ 抢不到 ⇒ 非零退出 + 「另一条车道正在跑」。
- 守卫两条（`tests/scripts/test_compose_test_profile.py`）：静态（锁在调
  compose **之前** + `flock -n` + `exec 9>`）+ **行为**（锁被占着 ⇒ 假 docker
  + 真占锁进程 ⇒ 脚本必须失败）。
- `docker-compose.yml` 的 `migrate` / `seed` 两个服务都注明「**必须**经
  `scripts/compose_test_stack.sh` 起」。

⚠️ **残留**（**未关闭** ⇒ 归 P10-C）：直接 `docker compose run --rm seed`
**仍能绕过锁** ⇒ ⇒ 容器侧装 `flock` + 把锁目录**可写**挂进容器那条路
⇒ ⇒ 本机 docker registry 拉不动 ⇒ ⇒ **改完无法验证** ⇒ ⇒ 不硬改。
⇒ ⇒ **保留本条**（状态从「完全没做」变成「宿主侧已做 · 容器侧待 P10-C」）。

**归属**：P10-C

---

## TODO-167: 前端还有别处把**占位常量**当真项目 id 用 🟡

**现状**（2026-11-17 · P10-F 的 F2-T2 期间发现）：

评审 #24 的根因是「占位 id 被当真值用」⇒ ⇒ 本批已修**仪表盘**那一处
（守卫条件改成「**拿到了真 project_id**」）⇒ ⇒ 并把常量改名成
`PLACEHOLDER_PROJECT_ID`（`src/constants/env.ts`）⇒ ⇒ 旧名 `PROJECT_ID`
保留为别名（语义 = 占位 id）。

⇒ ⇒ **仍有 4 处引用**把它当**真 id** 用：

- `src/pages/routeWrappers.tsx:136`（`StreamManualWizardRoute`）
- `src/pages/routeWrappers.tsx:212`（`PipeLineListRoute`）
- `src/pages/routeWrappers.tsx:331`（`PmsRoute`）
- `src/pages/routeWrappers.tsx:335`（`BeddRoute`）

⚠️ **2026-11-18 · 整支评审 I6 订正**：上面那份清单**严重低估**
⇒ ⇒ 实测（`grep -rn PROJECT_ID src/`）⇒ ⇒ **12 个页面文件 · 24 处**：

| 文件 | 处数 | 用法 |
|---|---|---|
| `src/pages/routeWrappers.tsx` | 6 | `StreamManualWizardRoute` · `StreamListRoute` · `PipeLineListRoute` · `PsvStandardProfileRoute` · `PmsRoute` · `BeddRoute` |
| `src/pages/heat/HeatComputePage.tsx` | 4 | `listByProject` + `project_id` + `workspace_id`（同源占位） |
| `src/pages/cv/CvComputePage.tsx` | 3 | `listByProject` + `project_id` + `workspace_id`（同源占位） |
| `src/pages/deliverables/SignatureMatrixPage.tsx` | 2 | `bind` / `unbind` |
| `src/pages/deliverables/DeliverableProgressPage.tsx` | 2 | `listProjectBindings` + 查询参数 |
| `src/pages/vessel/VesselComputePage.tsx` | 1 | `listByProject` |
| `src/pages/sim/StreamManualWizardPage.tsx` | 1 | props 默认值 |
| `src/pages/sim/StreamListPage.tsx` | 1 | props 默认值 |
| `src/pages/sep_equip/SepEquipComputePage.tsx` | 1 | `listByProject` |
| `src/pages/results/ResultListPage.tsx` | 1 | 查询参数 |
| `src/pages/util/EnergySummaryAggregatePage.tsx` | 1 | `project_id \|\| PROJECT_ID` |
| `src/pages/util/CoolingWaterPage.tsx` | 1 | `project_id \|\| PROJECT_ID` |

⚠️ **不算在内**：`src/mocks/seed/*.ts` 里那几个 `PROJECT_ID` 是**各文件自己
定义的本地常量**（mock 项目的 id）⇒ ⇒ **不是** `env.ts` 的消费者；
`src/vite-env.d.ts` 里的是 `VITE_PROJECT_ID`（另一个东西）。

⇒ ⇒ **改名的收益目前是 0**（`PLACEHOLDER_PROJECT_ID` **零消费者** ⇒ ⇒
新名字只是文档）⇒ ⇒ **改名的收益 = 让名字说真话** ⇒ ⇒ 真问题是
「**拿哪个真 id**」⇒ ⇒ 归 TODO-159。

⇒ ⇒ 那 3 个页面的 404 是 **TODO-159**（前端调了**不存在**的端点）的
**既有白名单项** ⇒ ⇒ **本批不顺手改**（改了 ⇒ 白名单失效 ⇒ 反而掩盖真缺口）。

**建议改法**：给那 3 个端点补齐（TODO-159）⇒ ⇒ 页面改成从
**路由上下文 / 用户选择**里拿真 `project_id` ⇒ ⇒ 然后删掉白名单条目。
⚠️ 改名只是「让名字说真话」，**不解决**「拿哪个真 id」的问题 ⇒ ⇒
**必须与 TODO-159 一起做**。

**何时做**：TODO-159 那一批

**归属**：P10-F（F2-T2 的延伸 · 与 TODO-159 绑定）

---

## TODO-170: `report_definitions.project_id` 是**死字段**（数据模型说项目级 · 授权说创建人级）🟠

**现状**（2026-11-18 · P10-F 的 F3-T2a 审计发现）：

`ReportDefinition` **有** `project_id` 列（可空 ⇒ 注释明写「`project_id IS NULL`
= 公司级模板作用域」）⇒ ⇒ **看起来**是项目级资源 ⇒ ⇒ **但可见性规则
完全不看它**：

```python
# app/services/report/definition_service.py::visible_clause
(ReportDefinition.created_by == user_id) | (status == "PUBLISHED" & shared_with == "ALL_USERS")
```

⇒ ⇒ ⇒ **`project_id` 能填、能存、但不参与任何授权判定** ⇒ ⇒
⇒ **数据模型说「项目级」、授权说「创建人级」** ⇒ ⇒ **口径不一致**。
⚠️ `POST /report-builder/definitions` 的 body **直接暴露** `project_id`
⇒ ⇒ 客户端可以把它**指向任意项目**（包括自己没有授权的项目）。

⇒ ⇒ ⚠️ **2026-11-18 追记**：初判说它「**不参与授权**」是**只对了一半**
⇒ ⇒ 它**不参与「定义的可见性」判定**（那是 `created_by` / `shared_with`）
⇒ ⇒ **但它决定「报表取哪个项目的数据」** ⇒ ⇒
`builder_service.py:176`：**`scope = project_id or row.project_id`**
⇒ ⇒ ⇒ **所以它不是死字段** ⇒ ⇒ ⇒ **真缺口的严重度因此升级 ⇒ ⇒
⇒ ⇒ 见 TODO-174（**high** · 跨项目读 · **实测取证**）**。
⇒ ⇒ ⇒ 本条的「口径不一致」是**成因** ⇒ ⇒ ⇒ 两条要一起修。

**建议改法**（**两条路，要人选** —— 这是产品语义）：

① **明确「报告定义不按项目隔离」** ⇒ ⇒ 把 `project_id` 从写入路径拿掉
   （或只允许 `NULL`）⇒ ⇒ 数据模型与授权一致 ⇒ ⇒ **改动小**
② **明确「按项目隔离」** ⇒ ⇒ `visible_clause` 加项目维度（谁的 `user_projects`
   授权行在 ⇒ ⇒ 可见）⇒ ⇒ **改动大**（要动列表/详情/执行三处口径）

⇒ ⇒ ⚠️ **不要「两边都留着」** ⇒ ⇒ 那正是现在这个状态。

**何时做**：下一批（**不阻塞** T2a ⇒ ⇒ 当前实现**自洽且可测**）

**归属**：P10-F（F3-T2a · G1 · **交人裁决**）

---

## TODO-172: **publish 的职责分离未定义**（产品语义待定 · **不是**越权缺口）🟡

⚠️ **2026-11-18 · 人裁决重写** —— 本条原先被写成「缺陷」（「别人也能发」⇒ ⇒
当成了 low 级越权）⇒ ⇒ **那个描述是错的** ⇒ ⇒ 它把「**职责分离未定义**」
写成了「权限漏洞」⇒ ⇒ ⇒ 现在按**产品语义待定**重写。

**现状**（2026-11-18 · F3-T2a 核实）：

`report_builder.py` 的 `publish` / `obsolete` **端点层**有
`require_roles(actor, "REVIEWER", "APPROVER", "SYSTEM_ADMIN")` ⇒ ⇒
service 层的 `publish(def_id=...)` / `obsolete(def_id=...)`
**不查 `created_by`** ⇒ ⇒ ⇒ 现状是：

| 问题 | 现状 |
|---|---|
| ① 审核者能否审核**自己创建**的定义？ | **能** —— 任何 REVIEWER+ 都能发任何定义，包括自己的（⚠️ 既有测试 `test_publish_requires_reviewer_role` 的 docstring 写的是「**创建人自己不能**发布」⇒ ⇒ **与现状相反** ⇒ ⇒ 见下） |
| ② 审核者是否需要对定义关联的 `project_id` 有授权？ | **不需要** —— 审核者可以对一个自己**无授权**的项目发布定义 |

⚠️ **为什么这不是越权缺口**：①+③ 已把攻击链断死（**TODO-174**，已修）⇒ ⇒
定义**建不出来**指向别人项目、**执行不了**别人的 scope ⇒ ⇒ ⇒ 「别人能发我的定义」
这条**拿不到我的数据** ⇒ ⇒ ⇒ 收益只是「**多一道防线**」⇒ ⇒ ≠ 越权。

⚠️ **实测（2026-11-18 · 探针）**：既有测试
`test_publish_requires_reviewer_role` 的 docstring 写着「**创建人自己不能**发布
—— 否则审批这一步形同虚设」⇒ ⇒ **但这条意图并没有被守住**：

- 该测试之所以绿 ⇒ ⇒ 是因为它的创建人是 **DESIGNER**（不在 `PUBLISH_ROLES` 里）
  ⇒ ⇒ ⇒ **它挡的是角色闸，不是「自审自批」**；
- 探针实测：**创建人自己是 REVIEWER** ⇒ ⇒ 发布自己创建的定义 ⇒ ⇒ **HTTP 200**
  ⇒ ⇒ ⇒ 「自审自批」是**允许**的。

⇒ ⇒ ⇒ **那条断言不敏感于它命名的缺陷** ⇒ ⇒ 与 TODO-171 **同族**
⇒ ⇒ ⇒ 独立登记为 **TODO-178**（断言缺口 · 技术债）⇒ ⇒ ⇒ **它的修法取决于本条
（产品语义）的裁决**。

**要裁决的**（**产品语义 + 审批流程设计** ⇒ ⇒ 不是代码能定的）：

- ① publish 的正确语义是「**审核角色审批 DRAFT 定义**」（SPEC §3.2.2(6)）
  ⇒ ⇒ 那么：**审核者能不能审自己创建的定义**？
- ② 审核者**必须**对定义关联的项目有授权吗？
- ③ 还是允许「**公司级审核者**」审所有项目的定义（= 现状）？

**归属**：P10-F 之外的独立批（产品语义 + 审批流程设计）· **不在 P10-F 修**

---

## TODO-177: **公司级模板（`project_id IS NULL`）当前不可执行**（已知限制）🟡

↪️ **已裁决 · 转批**（2026-11-23 · F4-PRE · FP-T1）—— **P10-J**（`docs/superpowers/plans/2026-11-23-p10-j-feature-backlog.md`）⇒ ⇒ 属新功能（要改契约）⇒ ⇒ 待人裁决后开工。


**现状**（2026-11-18 · F3-T2a 核实 · 人裁决要求登记）：

`execute_definition` 里：

```python
scope = project_id or row.project_id
if scope is None:
    raise PcsError(..., code="REPORT_PROJECT_SCOPE_REQUIRED", status=400)
```

⇒ ⇒ 而端点传的是 `project_id=str(row.project_id or "")` ⇒ ⇒ **恒为空串**
⇒ ⇒ ⇒ **`project_id IS NULL` 的公司级模板 ⇒ ⇒ 永远 400**
⇒ ⇒ （既有测试 `test_company_level_definition_cannot_execute_without_a_project`
断的正是这个 ⇒ ⇒ **不是回归，是现状**）。

⚠️ **为什么「执行时指定项目」这条路走不通**：`ReportExecuteRequest`
**没有 `project_id` 字段** ⇒ ⇒ **没有任何入口能传项目 id**
⇒ ⇒ ⇒ 「逼执行时指定项目」⇒ ⇒ **是死路**。

**要让它可执行需要**（**属新功能 ⇒ ⇒ 不在评审批范围**）：

① 给 `ReportExecuteRequest` 加 `project_id` 字段 ⇒ ⇒ **契约变化**
⇒ ⇒ 滚 OpenAPI baseline + 同步前端类型；
② 实现「指定的项目对执行者有授权」的判定（与 TODO-174 的 ③ 同款）。

⇒ ⇒ ⇒ **这两件事都是新功能** ⇒ ⇒ 计划明写「**不许在评审批里偷偷加功能**」
⇒ ⇒ ⇒ 本批**不做** ⇒ ⇒ ⇒ 登记为**已知限制**（不是缺陷）。

**归属**：P10-F 之外的独立批（新功能）⇒ ⇒ **P10-J · T1**
（`docs/superpowers/plans/2026-11-23-p10-j-feature-backlog.md`）

### ⚖️ hermes 第三方意见（2026-11-23）—— 技术侧只剩**一个**选项

⇒ ⇒ **3.1 是产品决定**（需人裁）⇒ ⇒ 但技术侧**只剩一个选项**：
**不存在「无项目地执行」** ⇒ ⇒ `execute_definition` 的 `scope is None` ⇒ 恒 400
（`builder_service.py:179-185`；注释：「**不能默认全库查询** —— 那会把别的项目的数据一起导出去」）
⇒ ⇒ ⇒ 「① 可执行 vs ② 只做模板、执行时选项目」**其实是同一件事**
⇒ ⇒ ⇒ **真问句是「要不要把『执行时选项目』做成 UI 流程」**。

⇒ ⇒ **三条技术约束（落地时必须满足）**：
- **a** 前端地基已在（P10-H · TODO-194）⇒ ⇒ 但执行页**完全不认项目** ⇒ ⇒ 要接
- **b** ⚠️ **必须把 scope 顺序倒过来：`scope = row.project_id or body.project_id`**
  （现状 `project_id or row.project_id`）⇒ ⇒ 一旦请求体带 `project_id`，前端**总是**
  发当前选中项目 ⇒ ⇒ **绑在项目 B 的定义会被拿项目 A 的数据执行** ⇒ ⇒ 不是越权，
  而是「定义名叫 B、出来的是 A 的数据」的**静默语义事故**
  ⇒ ⇒ ⚠️ **这是「实现时必须做」，不是「要不要」**
- **c** ⚠️ **入队必须传「解析后的 scope」**（现状传 `str(row.project_id or "")`
  （`report_builder.py:463`）⇒ ⇒ 否则公司级模板一执行 ⇒ ⇒ `report_files.project_id` 落
  NULL ⇒ ⇒ **产出文件无项目归属**

⇒ ⇒ **3.2 = 404**（**技术决定** · 非产品决定）⇒ ⇒ ⚠️ **钉子**：须走 **service 层**那份
（`code="PROJECT_NOT_FOUND"`）⇒ ⇒ **不能**用 api 层那份（`HTTP_404`）⇒ ⇒ 否则
**code 不同仍可枚举** ⇒ ⇒ **403 的合法位置只剩「角色闸」**。

---

## TODO-175: `POST /projects` 允许 SYSTEM_ADMIN 在**别人**的 FORMAL 工作区里建项目（产品语义待定）🟡

**现状**（2026-11-18 · F3-T2a 核实 · 人裁决「**不并入 B 档**」⇒ ⇒ 因为越权面 ≈ 0）：

`POST /api/v1/projects`：

| 事实 | 位置 |
|---|---|
| **只有 SYSTEM_ADMIN 能调** | `app/api/v1/projects.py:119` `require_roles(user, "SYSTEM_ADMIN")` |
| 校验工作区**存在** + 必须是 **FORMAL** | `:120-137`（非 FORMAL ⇒ 422 `WORKSPACE_NOT_FORMAL`） |
| 自动授权给**请求方自己** | `:189-201` `grant_project_access(user_id=user.user_id, …, role_in_project="PROJECT_LEAD")` |
| 授权键钉在**请求方的身份**上 | bug-2150 的修法（不用 `ensure_user_row` 的返回值 ⇒ 免得授权落到遗留身份） |

⇒ ⇒ ⇒ **它写的授权行是「给自己的」** ⇒ ⇒ **不产生「给他人授权」的路径**
⇒ ⇒ ⇒ SYSTEM_ADMIN 建的项目归他 ⇒ ⇒ **没有越权** ⇒ ⇒ ⇒ 并入 B 档会**稀释
B 档的结论密度**（人裁决）⇒ ⇒ ⇒ **不并入**。

⚠️ **唯一的小瑕疵**（不是越权）：`workspace_id` 是**客户端可填**的
⇒ ⇒ SYSTEM_ADMIN 可以在**别人的 FORMAL 工作区**里建项目
⇒ ⇒ 而那个工作区的 owner **不会**自动获得项目授权
⇒ ⇒ ⇒ 项目「**住在**别人的工作区里却不属于他」（可见性按 `user_projects`）
⇒ ⇒ ⇒ 那个 owner **看不见**这个项目。

**要裁决的**（**产品语义**）：

① SYSTEM_ADMIN 能不能**替别人**建项目？
② 如果能 ⇒ ⇒ 工作区 owner 是否应自动获得项目授权（`PROJECT_LEAD` 或 `VIEWER`）？
③ 如果不能 ⇒ ⇒ 是否应禁止在**非自己 owner** 的工作区建项目？

**归属**：P10-F 之外的独立批（**产品语义**，不是安全缺口）

⚠️ **联动**：若 F3-T3a 审 `workspaces.py` 时发现「工作区 owner 看不到住在自己
工作区里的项目」**可被利用**（例：owner 能删工作区 ⇒ ⇒ 项目 CASCADE 删除）
⇒ ⇒ 那是**另一条** ⇒ ⇒ 单独登记 ⇒ ⇒ 不属于本条。

---

## TODO-184: `GET /report/styles` 的 `project_id` 是**死参数** 🟢

**现状**（2026-11-18 · P10-F 的 F3-T2b 审计）：

`app/api/v1/report.py::list_styles`：

| 事实 | 行 |
|---|---|
| 声明了 `project_id` 查询参数 | `:319` |
| **查询里从不用它** | `:326-331`（只按 `report_type` 过滤） |

⇒ ⇒ ⇒ 契约里有个「按项目过滤样式」的参数，**行为上不存在**
⇒ ⇒ ⇒ 与 `report_builder.py` 的「死字段 `project_id`」**同形**（= TODO-170）。

⚠️ **注意**：本条**当前不构成越权面** ⇒ ⇒ 因为读面对**项目级**样式
**有意放宽**（登录即可读，见 §二 P6）⇒ ⇒ ⇒ 过滤与否不影响可见性
⇒ ⇒ ⇒ 但它是「契约说有、行为没有」的**同一类债** ⇒ ⇒ ⇒ 将来若把读面收紧
⇒ ⇒ ⇒ 这个死参数会变成「过滤器形同虚设」。

**建议改法**：要么实现它（按 `project_id` 过滤），要么从契约里去掉
⇒ ⇒ ⇒ 后者要动 OpenAPI ⇒ ⇒ 走契约变更流程。

**何时做**：低优先（⇒ ⇒ 登记即可）

**归属**：P10-F（F3-T2b · **low** · 与 TODO-170 同族）

---

## TODO-187: 两种 404 的**文案不同** ⇒ 记录/项目存在性可枚举 🟡

⚖️ **已裁决（2026-11-23 · 人）—— 选 A**（守卫加**可选** `not_found_code` / `not_found_message`
⇒ ⇒ 12 族各传自己的「X not found」⇒ ⇒ 端点自身的 404 与守卫的 404 **逐字同形**）
⇒ ⇒ **严重度 low**（不是 medium）⇒ ⇒ 落地条目 = **TODO-187b**（下一批做）
⇒ ⇒ 计划 **P10-I · T2**（`docs/superpowers/plans/2026-11-23-p10-i-report-review-publish.md`）。
⚠️ **范围已实测收窄**（2026-11-23 · F4-PRE 复核）：**不是「21+ 端点族」** ⇒ ⇒
守卫共 **140 处调用**（124 project 级 + 16 record 级）⇒ ⇒ **project 级已经同形**
（守卫是 404 的唯一来源 ⇒ 「不存在」与「无权」都是 "Project not found"）⇒ ⇒
**真正有两种文案的只有 12 个文件**（checklist · cool_tower · cost_est · filtration ·
flare · flash · open_channel · psychro · report · supplier · util · workspaces）
⇒ ⇒ 工作量 ≈ **30~40 行** ⇒ ⇒ 详见 **TODO-187b**（选 A 的落地条目）
⇒ ⇒ **优先级低于 TODO-197**（medium · 功能缺口 > low · 加固）。


**现状**（2026-11-18 · P10-F 的 F3-T3a 审计）：

| 来源 | 文案 | 位置 |
|---|---|---|
| 项目守卫（无权） | `"Project not found: {project_id}"` | `app/api/v1/_guard.py:47-50` |
| 端点自己的「记录不存在」 | `"PsychroResult not found"` | `app/api/v1/psychro.py:635`（PATCH `:688` · DELETE 同形） |

⇒ ⇒ ⇒ 信封把 `detail` 放进 `message`（`app/core/errors.py:305-311`）
⇒ ⇒ ⇒ 攻击者能靠 `message` **区分**「记录存在但我没权限」与「记录不存在」
⇒ ⇒ ⇒ 与本仓自己的规矩（「无权 ≡ 不存在 ⇒ ⇒ **逐字同形**」）**冲突**。

⚠️ **范围**：`check_project_access_or_404` 被 **21+ 端点**共用
⇒ ⇒ 凡「先按 id 取记录 ⇒ 再判项目授权」的端点都有这个形状
⇒ ⇒ `psychro.results` 是本批的代表 ⇒ ⇒ **不是单点问题**。

**严重性**：**低**（要枚举 UUID）⇒ ⇒ 但它是**规则冲突**。

**建议改法**：守卫与端点用**逐字相同**的 404 文案 ⇒ ⇒ 或统一走
`PcsError(code=..., status=404)` 且 **code 也一致**
（TODO-174 已记「同一失败在两层两种信封」⇒ ⇒ 本条是**同一层的两种文案**）。

**何时做**：低优先（⇒ ⇒ 登记即可 ⇒ ⇒ 修的时候按端点族**一起**改）

**归属**：P10-F（F3-T3a · **medium** · 跨端点族）

---

## TODO-192: **ce-code-review（P10-F 整批 · 2026-11-18）的修复项** 🔴

**来源**：`ce-code-review` 审 P10-F 整批（43 commit · base `2618f46`）⇒ ⇒
**10 个评审员全部返回**（correctness · security · adversarial · testing ·
api-contract · reliability · project-standards · maintainability · performance ·
learnings）⇒ ⇒ **51 条原始发现** ⇒ ⇒ 合并去重后 **1 P0 + 3 P1 + 8 P2 + 18 P3**。

⚠️ **P0 已修**（bug-2192 · commit `4b374b0`）：工作区守卫的真相源
（`workspaces.project_id` **生产路径从来不写** ⇒ ⇒ FORMAL 被当成 PERSONAL ⇒ ⇒
成员 404 + 写入恒 400）⇒ ⇒ 改成**反查 `projects.workspace_id`**。

**剩下的**（⇒ ⇒ **一条一条登记** ⇒ ⇒ 与仓库既有风格一致）：

| # | 严重度 | 缺口 | 位置 | 命中评审员 | 状态（2026-11-18） |
|---|---|---|---|---|---|
| 1 | 🔴 **P1** | **FORMAL 类型闸（403）排在工作区授权守卫（404）之前** ⇒ ⇒ 无权者拿到**可区分的 403** ⇒ ⇒ **存在性可枚举** | `app/api/v1/records.py:136` | adversarial + security | ✅ **已修** `2a77bd6`（类型闸拆成 `require_formal_workspace_type` ⇒ ⇒ 授权在前 404 · 类型在后 403）|
| 2 | 🔴 **P1** | **`DefinitionService.update` 改 `project_id` 不查项目授权**（`create` 查了 · `PUT` 没查）⇒ ⇒ 创建人可把定义改挂到无授权项目 | `app/services/report/definition_service.py:332` | **5 位独立命中** | ✅ **已修** `2a77bd6`（`update()` 补 `require_project_access_or_404`）|
| 3 | 🔴 **P1** | **工作区 owner 自动授权会造 `ws-owner-<uuid>` 的假用户名 `users` 行** ⇒ ⇒ 破坏「`user_id` = `uuid5(username)`」派生不变式 ⇒ ⇒ owner 之后真登录被 `USER_ID_CONFLICT` 挡住 | `app/api/v1/projects.py:245` | adversarial + project-standards | ✅ **已修** `2a77bd6`（不再造假用户名 ⇒ ⇒ owner 无 `users` 行 ⇒ ⇒ 跳过 + warning）|
| 4 | 🟠 P2 | `obsolete()` **不查任何身份/项目** ⇒ ⇒ 任意审核角色可作废别人的定义 | `definition_service.py:430` | maintainability + security + correctness | ✅ **已修** `f4a3246`（补**项目授权** ⇒ ⇒ 无权 404；⚠️ **禁自审**不补 ⇒ ⇒ 仍归 TODO-190）|
| 5 | 🟠 P2 | 项目级定义的 `shared_with` **被静默忽略** ⇒ ⇒ `CREATOR_ONLY` 发布后对全体项目成员可见 ⇒ ⇒ **字段与实现不符** | `definition_service.py:218` | adversarial + api-contract + project-standards | ✅ **已修**（2026-11-19 · P10-G · 人裁决**②**）⇒ ⇒ `CREATOR_ONLY` 对项目级**也生效** ⇒ ⇒ 只有创建人看得见 |
| 6 | 🟠 P2 | 审计脚本 `AUTHZ_GUARDS` **漏了两个新 service 层守卫** ⇒ ⇒ 把新守卫判成「无守卫」⇒ ⇒ **假阴性** | `scripts/audit_list_endpoints.py:84` | maintainability + adversarial + correctness | ✅ **已修** `f4a3246`（补两个 service 层守卫 + `interesting` 加 `TYPE_GUARDS`）|
| 7 | 🟠 P2 | 报表执行的 scope 授权在 `user_id is None` 时**整段跳过** ⇒ ⇒ **fail-open** | `app/services/report/builder_service.py:193` | reliability + security | ✅ **已修** `f4a3246`（`user_id is None` ⇒ ⇒ **拒绝执行** · fail-closed）|
| 8 | 🟠 P2 | `POST /workspaces` 收**任意 `project_id`** 且无项目授权（⚠️ **授权面影响已被 P0 修消除** ⇒ ⇒ 只剩「展示字段被污染」） | `app/api/v1/workspaces.py:73` | adversarial + security | ✅ **已修**（2026-11-19 · P10-G · 人裁决**①**）⇒ ⇒ 无权 ⇒ ⇒ **404**（与「不存在」同形）|
| 9 | 🟠 P2 | 「无权」在**三层返回三种错误码** ⇒ ⇒ 逐字同形只做到「同层内」 | `user_project_service.py:372` | api-contract + maintainability | ⏸ **独立批**（要动 21+ 端点的错误信封）|
| 10 | 🟠 P2 | `visible_clause` 与 `require_project_access_or_404` **对 SYSTEM_ADMIN bypass 口径不一致** | `definition_service.py:169/198` | api-contract + maintainability | ✅ **已修**（2026-11-19 · P10-G · 人裁决**②**）⇒ ⇒ admin **全可见**（含别人的草稿）⇒ ⇒ 与项目守卫同口径 |
| 11 | 🟠 P2 | 棘轮 `AUDITED_PROJECT_SCOPED_ENDPOINTS = 2`（实际 17+ 条）⇒ ⇒ **永不触发** | `tests/conftest.py:301` | testing | ✅ **已修** `f4a3246`（台账从**计数 2** 改成**路径清单** + 两条只增不减的下限）|

⇒ ⇒ **P3（18 条）** 登记在计划的「低优先」一节（前端 axios / MSW mock / 车道脚本 /
ARQ / 索引 / 文档 frontmatter …）⇒ ⇒ 不逐条开 TODO。

### ✅ **2026-11-19 · P10-G · 人裁决落地**（#5 / #8 / #10 三条）

| # | 裁决 | 落到哪儿 | 证据 |
|---|---|---|---|
| **#5** | **② `CREATOR_ONLY` 对项目级也生效** | `visible_clause`：两条发布档的公共前提 = `shared_with == ALL_USERS` ⇒ ⇒ `CREATOR_ONLY` ⇒ ⇒ **只有创建人看得见**（公司级 / 项目级一致） | 2 例新测试（看不见 + 正对照看得见）· 变异自证 1 条 |
| **#8** | **① 补项目授权校验** | `POST /workspaces`：`project_id` 非空 ⇒ ⇒ `check_project_access_or_404` ⇒ ⇒ 无权 ⇒ ⇒ **404** | 3 例新测试（无权 404 + 两个正对照）· 变异自证 1 条 |
| **#10** | **② admin 全可见** | `visible_clause` 收 `actor_roles` ⇒ ⇒ SYSTEM_ADMIN ⇒ ⇒ 恒真（含别人的草稿）⇒ ⇒ 与 `require_project_access_or_404` **同一谓词** ⇒ ⇒ 两处不漂 | 2 例新测试（admin 看得见 + 普通用户看不见的正对照）· 变异自证 1 条 |

⇒ ⇒ 端点层要跟着改：`list` / `get` / `execute` **三个**都把
`actor_roles` 传下去 ⇒ ⇒ 否则 admin 的 bypass 只在 service 内部生效
⇒ ⇒ 端点那一侧**等于没生效**。

⚠️ **误报（已实测排除）**：① 「审计脚本 `type_only` 档不可达」⇒ ⇒ 实测
`interesting` **已含** `TYPE_GUARDS` ⇒ ⇒ 该发现基于旧版本文件；② 「`shared_with`
被忽略」在公司级定义上**不成立**（公司级分支**有**该条件）⇒ ⇒ 只在项目级分支缺。

**归属**：**P10-F · 「守卫补洞批」**（计划：`docs/superpowers/plans/2026-11-18-p10-f-guard-hole-batch.md`）

---

## TODO-196: DMC 专用组分的 CAS 号**待工艺室确认**（P10-C · T4 引入） 🟡

**现状**（2026-11-19 · P10-C · T4）：

PRO/II 的 DMC `.inp`（`sample/dmc.inp`）的 `COMPONENT DATA` 段用的是**装置缩写**
（PO / PROPCARB / DMCARB / 12PG / DIPRPGLY / TPG / AA / OXYLENE / MOXYPROH /
PROPALD）⇒ ⇒ 别名表里没有 ⇒ ⇒ 组成落不到 CAS ⇒ ⇒ 「导入 ⇒ 物性补全」断链。

⇒ ⇒ 本批（**人裁决：「我补 CAS 号并标注待确认」**）补了：
① `alias_registry` 的 **10 条** DMC 别名 ⇒ 规范名；
② `app/services/component_cas.py` 的 **10 条** 规范名 → CAS
⇒ ⇒ **CAS 是按公开的化学物质登记号填的** ⇒ ⇒ **未经工艺室逐条核对**。

⚠️ **为什么要核对**：CAS 错 ⇒ ⇒ 组成错 ⇒ ⇒ 闪蒸算出**错**的结果
⇒ ⇒ 而错组成比没组成**危险得多** ⇒ ⇒ 这 10 条应当由工艺室确认后再投产。

⚠️ **兜底已经在了**：任何一条 CAS 认不出来 ⇒ ⇒ 该流的组成**整个作废**
（`composition_json = None`）+ 告警 ⇒ ⇒ **不会**带着错 CAS 落库。

**归属**：**工艺室确认**（⇒ ⇒ 确认完在本条里把 CAS 号逐条核一遍 + 记确认人/日期）

⚠️ **2026-11-19 人裁：维持现状**（选项 ②）⇒ ⇒ **未确认的 CAS 照常落库、
照常过送审门禁** ⇒ ⇒ 只靠**人工登记**这条 TODO 兜着
⇒ ⇒ ⇒ ⚠️ 风险照旧：**CAS 错了 ⇒ ⇒ 组成错 ⇒ ⇒ 闪蒸算出错的结果**
⇒ ⇒ ⇒ 投产后端点必须**先**把这条关掉。
⇒ ⇒ ⇒ （曾提过「送审门禁拒收含未确认组分的组成」这条更严的路 ⇒ ⇒
人裁选了维持现状 ⇒ ⇒ **不做**。）

---

## TODO-198: 「待办 500ms 预算」测的是 **pytest harness 开销**，不是查询 ⇒ ⇒ 车道假红 🟠

**现状**（2026-11-19 · P10-G 批末撞出来的）：

`tests/api/v1/test_todos.py::test_todo_sql_and_parse_both_within_budget`
⇒ ⇒ 断言 `GET /api/v1/todos` 端到端 **≤ 500ms**。

⚠️⚠️ **它在完整车道的默认 capture 下会红**（P10-G 实测 3/3），
而**同一份代码**在 `--capture=no` 下是绿的 ⇒ ⇒ ⇒ **红的不是代码，是 harness**。

| 跑法 | 实测 |
|---|---|
| 该测试**单独**跑（默认 capture） | **235ms** ✔ |
| `tests/alembic/ + tests/api/v1/`（默认 capture） | **233ms** ✔ |
| **完整车道**（默认 capture） | **2039 ~ 2162ms** ✘（超预算 4 倍） |
| **完整车道**（`--capture=no`） | **227ms** ✔ |
| **查询本身**（`compute_todos` 直调，兄弟测试量的是它） | **12.7ms** ✔ |

⇒ ⇒ ⇒ 结论：**500ms 预算里没有一分钱是查询花的** ⇒ ⇒ 预算测的是
**pytest 的 fd 级 capture + ASGI 往返** ⇒ ⇒ 完整车道里那份开销被放大到 ~2s
⇒ ⇒ ⇒ **这是一个「测机器噪声」的断言**，不是「测性能」的断言。

⚠️ **HEAD（未含本批改动）下默认 capture 是绿的**（实测 2/2）⇒ ⇒ 它本来就
**贴着预算边**（233ms vs 500ms）⇒ ⇒ 本批只是把它推过了线
⇒ ⇒ ⇒ **不是功能回归**（查询 12.7ms 不变）。

**建议改法**（**下一批**·不在本批改 —— 改断言让它绿是本仓明令禁止的）：

① **预算断言改测「查询 + 解析」**（像兄弟测试 `test_todo_at_expected_data_volume`
   那样直调 `todo_service.compute_todos`）⇒ ⇒ 测的是**它该测的东西**；
② **HTTP 往返的预算单独给一条**（且给足余量）⇒ ⇒ 明确「这是 harness 预算，
   不是服务预算」；
③ ⇒ ⇒ 或者干脆**删掉 HTTP 往返那条**（兄弟测试已经覆盖了真正的性能面）。

⇒ ⇒ ⇒ **本批的处置**：默认 capture 的车道有 **1 条**红（就是它）⇒ ⇒
用 `--capture=no` 的车道作批末证据（**5935 passed · EXIT=0** ⇒ ⇒ 其余
全部绿）⇒ ⇒ **如实登记本条**，不掩盖。

**归属**：**下一批 · 测试质量**（与 TODO-193 同批做）

---

## TODO-197: 前端**没有「他人发布报表定义」的入口** ⇒ ⇒ 「发布」在 UI 上不可达 🟠

⚖️ **已裁决（2026-11-23 · 人）—— 选方案 ①「待我审核」队列 + 列表页发布按钮**（+ 三个约束 · 见下）
⇒ ⇒ **严重度 medium**（不是 high：没有越权，只是**流程走不完**；不是 low：SPEC §3.2.2
「发布须由审核角色」在 UI 上**不成立** ⇒ ⇒ 是**功能缺口**不是加固）
⇒ ⇒ **归属**：**独立批 = P10-I · T1**（`docs/superpowers/plans/2026-11-23-p10-i-report-review-publish.md`）
⇒ ⇒ **与 TODO-187 同一批**（都是「后端能力齐全 · 前端/契约收口」类）
⇒ ⇒ ⚠️ **不塞 P10-C 前端收口**（那条批 T1~T5 已满 ⇒ ⇒ 会变成「杂项收口」）
⇒ ⇒ **优先级**：TODO-197（medium · 功能缺口）**>** TODO-187（low · 加固）。

**约束 1 · 队列是只读视图，不是「放开草稿可见性」**
⇒ ⇒ 审核者通过队列能看到草稿的**元数据**（标题 · 创建人 · 项目 · 创建时间 · 摘要）
⇒ ⇒ **不能进入编辑器** ⇒ ⇒ `update()` 对非创建人 **404** 的现状**保持不变**
⇒ ⇒ 队列只提供两个动作：**发布 / 忽略**（**「拒绝」本批不做** ⇒ 见约束 3）
⇒ ⇒ ⚠️ 这是 ① 与 ② 的**分界线**：若审核者能点进草稿编辑器改内容 ⇒ ⇒ 就滑向 ②
⇒ ⇒ 那与「草稿只有创建人可见」的既有裁决**正面冲突**（半成品被审核者看到/改动 = 产品事故）。

**约束 2 · 队列的过滤条件与 `visible_clause` 分离**
⇒ ⇒ 队列的口径 = 「**我可审 ∧ 我可见的元数据**」，不是「我可审的所有草稿」：

| 草稿类型 | 审核者可见 | 条件 |
|---|---|---|
| 公司级（`project_id IS NULL`） | ✔ | `REVIEWER+` |
| 项目级（`project_id` 非空） | ✔ | `REVIEWER+` ∧ 我在该项目有 `user_projects` 授权 |
| 项目级 · 我无授权 | ✘ | ——（即使我是 `REVIEWER`）|
| `created_by == 我` | ✘ | ——（自审禁止 ⇒ 与 `publish()` 的 **403** 一致）|

⇒ ⇒ ⚠️ **这组规则必须写进队列端点的 docstring**（不是只写在实现里）
⇒ ⇒ 否则下一个维护者会以为队列 = 「所有 DRAFT」。

**约束 3 · 「拒绝」动作本批不做 ⇒ ⇒ 登记 TODO-197b**
⇒ ⇒ 队列只有「发布」⇒ ⇒ 审核者看到不合格的草稿只能发布或忽略
⇒ ⇒ 产品上需要「拒绝」（状态改回 DRAFT 或加 `REJECTED` 状态）
⇒ ⇒ ⚠️ `REJECTED` 是**新状态** ⇒ ⇒ 会牵动可见性 / 执行 / 列表过滤 / 前端 badge
⇒ ⇒ ⇒ 那是**新功能** ⇒ ⇒ 不是本批该做的 ⇒ ⇒ 归下一批 / 产品语义批。

### ⚖️ hermes 第三方意见（2026-11-23）—— 查出一个**真漏洞** + 四条实现要求

⚠️ **`publish()` 不判 `shared_with`**（`definition_service.py:454-478` 只判自审 / 项目授权 /
状态）⇒ ⇒ **`CREATOR_ONLY` 的草稿谁都能发** ⇒ ⇒ 发布后**仅创建人可见**
⇒ ⇒ ⚠️ **队列一上 UI 就给它开了口子**（审核者能把「只我可见」的草稿发布掉）
⇒ ⇒ 而**约束 2 的过滤表漏了这一维** ⇒ ⇒ **需人裁**（队列不列 `CREATOR_ONLY`？
还是 `publish()` 补判？）。

⇒ ⇒ **四条实现要求**（hermes）：
- **A-1** 过滤落 **service 层**（既有模式：判定在 service ⇒ 端点漏调也绕不过）
- **A-2** 两份 EXISTS **抽共享 helper**（勿复制）
- **A-3** 角色闸引**唯一真相源**（现状**已 3 份**：词表 `ALLOWED_ROLES`
  `app/api/v1/config.py:92` + `PUBLISH_ROLES` `app/api/v1/report_builder.py:236` +
  `OBSOLETE_ROLES` `app/services/report/definition_service.py:65`
  ⇒ ⇒ 队列会是**第 4 份** ⇒ ⇒ 落 `app/core/acl.py`）
- **A-4** **SYSTEM_ADMIN 也排除自己的草稿**（否则队列出现「点了必失败」的按钮）

⇒ ⇒ **队列响应**（新具名 schema `ReportDefinitionReviewItem`）= `def_id` / `name` /
`created_by` / `project_id` / `created_at` / `updated_at` / `description` / `category`
⇒ ⇒ **不带** `definition_json`（约束 1）· `version`（改草稿不动版本号 ⇒ 恒值）·
`status`（恒 DRAFT）⇒ ⇒ 先例：SPEC §6.22 的待办 item 也**只带够做动作的字段 + title**。

⇒ ⇒ ⚠️ **措辞出入**：人裁原话是「**列表页**发布按钮」⇒ ⇒ 但审核者在**列表页**看不到
别人的草稿（可见性只给本人 + 已发布）⇒ ⇒ 按钮必须长在**队列页** ⇒ ⇒ 列表页那处
对审核者是**死按钮** ⇒ ⇒ **需人明确**。

**为什么不是 ② / ③ / ④**（人裁决的理由）：

| 方案 | 否决理由 |
|---|---|
| ② 放开草稿可见性 | 与「草稿只有创建人可见」**正面冲突**；所有审核角色看见所有草稿（含半成品）⇒ ⇒ **产品事故面** |
| ③ 移交审核（指派） | 动数据模型 + 迁移 ⇒ ⇒ 风险大；且要求创建人**主动指派** ⇒ ⇒ 增加创建人负担；**创建人不指派 ⇒ 草稿永远卡死** ⇒ ⇒ 比 ① 更差 |
| ④ 按 id 发布 + 通知/待办 | 单靠它**解不了 UI 不可达**（前端入口仍需设计）；且「通知系统」是另一个大项 |

⇒ ⇒ ① 是最小可行的「**拉**模式」（审核者主动去队列看）⇒ ⇒ 未来可叠加 ③ 的「指派」
或 ④ 的「通知」变成「**推**模式」⇒ ⇒ 那是**增量**，不推翻 ①。

**与 P10-F · F3 的交叉**（人裁决要求）
⇒ ⇒ F3-T2a 审 `report_builder.py` 的结论写「publish 已覆盖」⇒ ⇒ **必须注明
「UI 不可达」** ⇒ ⇒ **API 层覆盖 ≠ 产品流程覆盖** ⇒ ⇒ 这**不是审计缺口**
（API 是对的）⇒ ⇒ 是**产品缺口** ⇒ ⇒ 已进 F3 结论的「**排除/移交**」节
（`docs/solutions/security-issues/guard-coverage-audit-logistics-adjacent-modules.md` §六）。

**现状**（2026-11-19 · P10-G · TODO-191 落地时**顺带查出来**）：

⚠️⚠️ 全仓**只有一处**能发布报表定义 ⇒ ⇒ 编辑器页的「保存并发布」按钮
⇒ ⇒ 而**创建人不能发布自己创建的**（后端 `publish()` 对
`created_by == actor` 返 **403** `REPORT_DEFINITION_SELF_REVIEW_FORBIDDEN`）
⇒ ⇒ 而**只有创建人能打开编辑器**（`update()` 对非创建人返 404）
⇒ ⇒ ⇒ ⇒ **那个按钮 100% 失败** ⇒ ⇒ ⇒ 「谁去发布」这件事**在 UI 上没有答案**
⇒ ⇒ ⇒ 审核者**连别人的草稿都看不见**（可见性：草稿只有创建人可见）
⇒ ⇒ ⇒ ⇒ 「创建 ⇒ 交给审核者 ⇒ 审核者发布」这条链**在 UI 上断在第二环**。

⇒ ⇒ 2026-11-19 的人裁（TODO-191）把那个按钮**置灰**了 ⇒ ⇒ 如实反映
⇒ ⇒ ⇒ 但**没有**补上「审核者发布」的那个入口 ⇒ ⇒ ⇒ 本条就是那个缺口。

**为什么重要**：SPEC §3.2.2(6) 的「发布须由审核角色」这条流程
⇒ ⇒ 今天在 UI 上**走不完** ⇒ ⇒ 只走 API 才走得完。

**建议改法**（**待人裁**，不属本批）：

① **列表页加「发布」动作** ⇒ ⇒ 但审核者**看不见别人的草稿**
⇒ ⇒ ⇒ 得先放开「审核者能看到待审草稿」这条可见性（那是**另一条**裁决）；
② **在定义详情页加一条「移交审核」的显式动作**（改状态 / 建一条待审记录）
⇒ ⇒ 需要后端支持；
③ **审核者从「我建的」列表里发布** ⇒ ⇒ 但那还是自审 ⇒ ⇒ 与裁决 ① 冲突
⇒ ⇒ **不可行**。

**归属**：**下一批 · 项目上下文 / 选择器** 之后的独立小批（或与 TODO-195
落地同批做 —— 都要碰报表定义这块前端）

---

## TODO-187b: 12 族端点的 404 文案**逐字同形**（选 A · 守卫加可选文案参数）🟢

**来源**（2026-11-23 · 人裁 **TODO-187** ⇒ ⇒ 选 **A** ⇒ ⇒ **独立条目**
⇒ ⇒ 以便与原条目 TODO-187（审计发现 · 当时记的是 medium · 「跨 21+ 端点族」）
**区分开** —— 那个范围后来**实测收窄**了）

⚖️ **裁决（2026-11-23 · 人）—— 选 A**

| 维度 | **A（选中）** | B（否决） |
|---|---|---|
| 逐字同形 | ✔ | ✔ |
| 可诊断性 | ✔ 保留（"PsychroResult not found" vs "Project not found"）| ✘ 丢失 |
| 前端按 code 分流 | **不变** | ✘ 变粗（前端在用**几十个专属 code** ⇒ ⇒ 盘点工作量大）|
| 改动面 | 12 族各 1~2 处调用 + 常量（≈ **30~40 行**）| 12 族 + **全前端 code 分流盘点** |
| 向后兼容 | ✔（**可选参数默认保持原行为** ⇒ ⇒ 124 处 project 级不受影响）| ✘（code 统一是**破坏性**变化）|

⇒ ⇒ B 的唯一优势是「全仓一句话」更简单 ⇒ ⇒ 代价（前端几十个专属 code 的盘点 +
丢失诊断性）⇒ ⇒ **不值得**。

**约束 1 · 同一端点、同一资源类型 ⇒ 「不存在」与「无权」必须逐字同形**
⇒ ⇒ **不同资源类型之间可以不同**（「PsychroResult not found」与
「Project not found」不同是**正常的** ⇒ ⇒ 端点路径本身就暴露了资源类型）
⇒ ⇒ 关键是**同一个端点内**，攻击者**不能**靠 `message` 区分
「不存在」与「存在但我无权」。

**约束 2 · 守卫的默认文案 `"Project not found: {project_id}"` **不得因加参数而改变**
⇒ ⇒ **124 处 project 级调用**依赖这个默认值 ⇒ ⇒ 加可选参数时**默认值必须是现状**
（**不是**空、**不是**通用文案）⇒ ⇒ ⚠️ **本条最大的回归风险点**：
「加一个参数顺手把默认改了」⇒ ⇒ 124 处全变 ⇒ ⇒ 测试红一大片。
⇒ ⇒ **测试钉子**：至少一条断言 ——
`check_project_access_or_404(db, user_id=…, project_id=…)`
**不传** `not_found_message` 时 ⇒ ⇒ 仍抛 **`"Project not found: {project_id}"`**。

**落地要点**（实现时必须满足）：

- [ ] 守卫加**两个可选参数** `not_found_code: str | None = None` ·
      `not_found_message: str | None = None` ⇒ ⇒ **默认 = 现状**
- [ ] ⚠️ **code 与 message 要**一起**对齐**：端点自身的不存在若是
      `PcsError(code="REPORT_FILE_NOT_FOUND", …)` ⇒ ⇒ 守卫也必须能覆盖 **code**
      ⇒ ⇒ 这就是**为什么两个参数都要**（只传 message ⇒ ⇒ code 仍不同 ⇒ ⇒
      **仍然可枚举** ⇒ ⇒ **没修掉**）
- [ ] 12 族各 1~2 处调用点传自己的文案（**逐字**抄端点自身那条）
- [ ] 每族 **2 条参数化用例**：无权 ⇒ 与「不存在」**逐字相同**（code + message 都比）
- [ ] **约束 2 的钉子**（见上）单独一条
- [ ] ⚠️ **124 处 project 级**调用**一行不动**（默认路径）⇒ ⇒ 跑默认车道 + PG 车道验证零回归

**严重度**：🟢 **low**（不是 medium）—— 理由：project 级 **124 处已同形**；
record 级与混合族的攻击面要求攻击者**已能访问某 project** ⇒ ⇒ 只能枚举
**该 project 内**某 record 是否存在 ⇒ ⇒ **不泄露跨 project 数据**
⇒ ⇒ 这是**信息泄露的纵深加固**，不是直接越权。

**归属**：**独立批 = P10-I · T2**（`docs/superpowers/plans/2026-11-23-p10-i-report-review-publish.md`）
⇒ ⇒ ⚠️ **不塞 P10-C 前端收口**（那条批是前端收口 ⇒ ⇒ 塞后端 404 文案会**失焦**）
⇒ ⇒ ⚠️ **不塞 F3**（F3 是**审计 + 结论**，不是修）
⇒ ⇒ **下一批做**（P10-I · T2 · 与 T1 的 TODO-197 同批 ⇒ ⇒ T1 优先）

---

## TODO-197b: 「待我审核」队列需要**「拒绝」动作** ⇒ ⇒ 状态要加 `REJECTED` 🟡

**来源**（2026-11-23 · 人裁 TODO-197 的**约束 3**）

⇒ ⇒ TODO-197 选定的方案 ①（待我审核队列）**本批只做「发布 / 忽略」**
⇒ ⇒ 审核者看到**不合格**的草稿 ⇒ ⇒ 只能发布或忽略 ⇒ ⇒ **没有「打回」的路**
⇒ ⇒ 产品上需要「拒绝」。

**为什么本批不做**（人裁决）：
⇒ ⇒ 「拒绝」要么把状态**改回 DRAFT**（⇒ ⇒ 那不是拒绝，是「退回修改」⇒ ⇒
还要能通知创建人），要么**加一个新状态 `REJECTED`** ⇒ ⇒ ⚠️ 新状态会牵动
**可见性 / 执行 / 列表过滤 / 前端 badge / 状态机** ⇒ ⇒ **那是新功能**
⇒ ⇒ 不是「收口批」该做的。

**待人裁**（下一批 / 产品语义批）：
① 状态模型：**退回 DRAFT**（复用现有态 + 一个「被退回」标记）还是**新增 `REJECTED`**？
② 谁能看到 `REJECTED` 的定义？（创建人 / 项目内 / 审核者 / 不可见）
③ `REJECTED` 能不能**再编辑**（⇒ ⇒ 创建人要能改完再交审）？
④ 要不要**通知创建人**（⇒ ⇒ 牵动「通知系统」那一条）？

**归属**：**P10-J · 功能批**（`docs/superpowers/plans/2026-11-23-p10-j-feature-backlog.md`）
⇒ ⇒ 与 TODO-196（CAS · 工艺室确认）· TODO-177（公司级模板可执行）同类
⇒ ⇒ **等人裁决后**才排得上期。

---

# F4-PRE 裁决表（2026-11-23 · P10-F · F4 前置批）

> **为什么有这张表**：F4-PRE 的主任务（FP-T1）是「**逐条裁决**」14 条遗留债
> ⇒ ⇒ 每条必须落成**三者之一**：① **本批修** ② **转某批**（写明批号）
> ③ **关闭**（写明理由 + 证据）
> ⇒ ⇒ **不许留「下一批」这种写法** —— 那正是这批债攒下来的原因。
>
> ⇒ ⇒ 本表 = 那 14 条的**唯一账本**（与计划文件末尾的表一一对应）。
> ⚠️ **190 / 191** 已在 2026-11-19 · P10-G 关闭 ⇒ ⇒ 此处只列**当时状态**。

| # | 条目 | 裁决 | 落点 / 证据 |
|---|---|---|---|
| **164** | 默认单测车道连开发库与真 Redis | ① 本批修 → **关闭** | 应用侧隔离（F2-T5）之外还有**残留**：`pg` 标记用例在默认车道会连**开发库**建隔离 schema ⇒ ⇒ 本批在 `tests/conftest.py` 加**收集期**闸（`pg` 用例只在车道跑）⇒ ⇒ 默认车道**零连真 PG** |
| **165** | 依赖真 Redis 语义的测试该迁 PG 车道 | ① 本批修 → **关闭** | `tests/conftest.py` 按 **fixture 名**（`real_redis`）**自动**标 `pg` ⇒ ⇒ 21 条用例（编辑锁 11 · 广播 8 · WS 2）进 PG 车道 ⇒ ⇒ **PG 车道 7 → 46 passed**（覆盖回来了）|
| **168** | 默认车道的漂移守卫仍连开发库 | ① 本批修 → **关闭** | 5 处全部离开默认车道：3 个标 `pg`（sim_tower / streams_sim_fields / sim_unit_op）· `test_sqlite_check_constraint_overrides` 标 `pg` 且**改指车道库**（原来连 `pcs_test` 建探针表）· psychro 那条本就 `pcs_test` 门 ⇒ ⇒ 默认车道零连 PG |
| **171** | `DefinitionService.update` 写闸无独立断言 | ③ **关闭** | **已有**：`test_update_cannot_repoint_a_definition_to_an_ungranted_project`（P10-G · `09c9282`）⇒ ⇒ 守卫与断言都在 ⇒ ⇒ 不是缺口 |
| **173** | `config.py` 8 端点角色闸无 403 断言 | ① 本批修 → **关闭** | `tests/api/v1/test_config_role_gates.py`：**11 条**端点逐条 403（角色闸走**角色字符串** ⇒ 不受项目守卫 mock 影响 ⇒ ⇒ 断言是真的）+ **AST 完整性守卫**（新增带闸门的端点忘了写 ⇒ ⇒ 红）|
| **176** | 默认 `client` 把项目守卫 mock 成永远 True | ③ **关闭** | 这是**设计**（让非守卫测试不被授权绑死）⇒ ⇒ 对策是 `strict_client` + **台账棘轮**（FP-T2 已把它从计数改成**清单**）⇒ ⇒ 「已覆盖」的复核口径 = 「这条断言用的是 `strict_client`」⇒ ⇒ **有工具了** ⇒ ⇒ 不是缺陷 |
| **177** | 公司级模板（`project_id IS NULL`）不可执行 | ② **转 P10-J** | 要改契约（`ReportExecuteRequest` 加 `project_id`）= **新功能** ⇒ ⇒ 计划 `docs/superpowers/plans/2026-11-23-p10-j-feature-backlog.md`（P10-J-T1）⇒ ⇒ **待人裁** |
| **181** | `records.py` / `report.py` 项目守卫零断言 | ① 本批修 → **关闭** | `records.py` 三条此前已入台账（P9B-4 批 4）；`report.py` **4 条**本批补 `strict_client` 断言（`tests/api/v1/test_report_project_guard.py`）+ 删掉那条**恒真**断言（`status_code in (200, 404)`）⇒ ⇒ 变异自证（删守卫 ⇒ ⇒ 3 条红）|
| **183** | `test_project_level_uses_project_access_not_admin` 断言恒真 | ① 本批修 → **关闭** | 根因：字典初值是 `True` ⇒ ⇒ 「守卫被调用过」与「守卫从没被调用」都绿 ⇒ ⇒ 改成 `False` ⇒ ⇒ 变异自证（删守卫 ⇒ ⇒ 2 条红）|
| **187** | 两种 404 文案不同 ⇒ 存在性可枚举 | ② **转 P10-I · T2**（**2026-11-23 已裁：选 A**） | 改 404 文案 = **改守卫逻辑** ⇒ ⇒ 超出 F4-PRE 的批次边界 ⇒ ⇒ 计划 `docs/superpowers/plans/2026-11-23-p10-i-report-review-publish.md` ⇒ ⇒ ⚠️ **范围已实测收窄**：守卫 140 处调用里 **124 处 project 级已经同形** ⇒ ⇒ 真正要改的只有 **12 族** ⇒ ⇒ ≈ 30~40 行 ⇒ ⇒ 落地条目 **TODO-187b**（🟢 low）|
| **188** | `GET /user-projects/me` 角色清单不全 ⇒ 合法用户 403 | ① 本批修 → **关闭** | 根因是**手抄第二份清单** ⇒ ⇒ 角色白名单提为**模块级常量** `app.api.v1.config.ALLOWED_ROLES`（唯一真相源）⇒ ⇒ `/me` 改用 `*ALLOWED_ROLES` ⇒ ⇒ **抄漏**不再可能 ⇒ ⇒ 顺带修**同族笔误** `PROCESS_CONTROLLOR`（批量提交端点）⇒ ⇒ 11 条断言 |
| **189** | 两个「不 mock 守卫」的 client ⇒ 棘轮看不见其中一个 | ① 本批修 → **关闭** | `tests/test_audit_guard.py` 改用 `strict_client`（唯一真相源）⇒ ⇒ 另加**架构守卫**：「自建 ASGI client 的文件集合**冻结**」⇒ ⇒ 不会有第三个 |
| **190** | `obsolete` 不查 `created_by` | ③ 已关闭 | 2026-11-19 · P10-G（人裁决①：PUBLISHED 禁自审 / DRAFT 自己能删）⇒ ⇒ 4 条用例 + 2 条变异自证 |
| **191** | 前端「保存并发布」对创建人自己无提示 | ③ 已关闭 | 2026-11-19 · P10-G（人裁决①：拆成「保存草稿」+ 发布置灰）⇒ ⇒ 3 条前端用例 + 变异自证 |

⇒ ⇒ **裁决分布**：① 本批修 **8 条** · ② 转批 **2 条**（P10-I / P10-J）
· ③ 关闭 **4 条**（190 / 191 早已关 · 171 / 176 本批关）
⇒ ⇒ **没有一条留在「未定」** ⇒ ⇒ F4 开工前台账是干净的。

---

## ✅ 已关闭（**正文已搬进归档**）

⚠️ **为什么搬走**：这些条目**已经闭合**（正文里带着完整的取证过程 / 裁决叙事 / 变异自证）⇒ ⇒ 它们**不再需要被逐字读**⇒ ⇒ 但**编号是追溯索引** ⇒ ⇒ 原文逐字保留在 **`docs/archives/TODOS-closed.md`**（98 条）。

| 编号 | 条目 | 关闭日期 |
|---|---|---|
| `TODO-004` | CORS middleware 已挂载（2026-10-06） | 2026-10-06 |
| `TODO-006` | 认证端点限流 + 登录审计（2026-10-07，`d196daa`） | 2026-10-07 |
| `TODO-007` | JWT 过期 / 无效已细分（2026-10-07，`d196daa`） | 2026-10-07 |
| `（批次汇总）` | 10 张计算表主键 rename（2026-10-08 核实关闭） | 2026-10-08 |
| `TODO-041` | antd `dataIndex` 是类型闸的洞（2026-10-19 修完） | 2026-10-19 |
| `TODO-042` | 遗留两项：✅ 已闭环（2026-10-19） | 2026-10-19 |
| `TODO-052` | `workflow_progress` 表名在两个规格里有互不相容的定义（✅ 已裁决 2026-10-20） | 2026-10-20 |
| `TODO-053` | `workflow_progress` 实际 10 个业务字段，比 SPEC 列的 8 个多 2（🟡 已知偏差） | — |
| `TODO-054` | 记录侧「多级批准」的角色链无定义来源（2026-10-27 落地，P9B-2 · T2） | 2026-10-27 |
| `TODO-057` | ADR-0047 §① 的第三个观测写入点（变更单）（2026-10-26 落地，P9A-DLV-007 同批） | 2026-10-26 |
| `TODO-058` | `RECORD_TYPE_REGISTRY` 的语义未定 + 列完整性无契约（✅ 已裁决 2026-10-20） | 2026-10-20 |
| `TODO-059` | 签署矩阵的 `sign_role` 是**全局角色**，与 `user_projects.role_in_project` 语义不对称（✅ 已被 ADR-0050 取代） | 2026-10-20 |
| `TODO-060` | `record_type` 两套词表（类名 vs 表名）→ 收敛为注册表键（2026-10-20 修完） | 2026-10-20 |
| `TODO-061` | `CostEstResult` 无 `project_id` ⇒ 编辑面零项目隔离（2026-10-20 修完） | 2026-10-20 |
| `TODO-065` | `GET /deliverables/{id}/progress` 聚合端点（2026-10-27 落地，P9B-2 · T0） | 2026-10-27 |
| `TODO-066` | 编辑审计缺**按项目守卫**的读端点（2026-10-27 落地，P9B-2 · T1） | 2026-10-27 |
| `TODO-067` | P9B-1 最终评审的 **7 条 deferred minor**（2026-10-27 全部闭环，P9B-2 · T9） | 2026-10-27 |
| `TODO-068` | 变更申请**无 HTTP 入口**（2026-10-26 落地，P9A-DLV-011 T4） | 2026-10-26 |
| `TODO-069` | 「一条记录同时只有一张变更单」是**新增业务约束**（2026-10-26 落地） | 2026-10-26 |
| `TODO-070` | `signature_matrices` **无管理面**（2026-10-26 落地，P9A-DLV-011 T3） | 2026-10-26 |
| `TODO-071` | `project_signature_matrix_bindings` 缺 (project_id, module) 唯一约束（2026-10-26 落地） | 2026-10-26 |
| `TODO-072` | `steps_json` **校验器**缺失（2026-10-26 落地，P9A-DLV-011 T3） | 2026-10-26 |
| `TODO-073` | 变更单编号**可读**（走编号模板）（2026-10-27 落地） | 2026-10-27 |
| `TODO-074` | 签署矩阵**同名同状态**不许存在两份（2026-10-27 落地） | 2026-10-27 |
| `TODO-075` | `change_resolved_by` 只由「关记录」那步写（2026-10-27 落地） | 2026-10-27 |
| `TODO-076` | 工作区类型门禁覆盖 UI-SPEC §5.3 的**全部**四类操作（2026-10-27 落地） | 2026-10-27 |
| `TODO-077` | `apply-change` 不要求 hash 变化（2026-10-26 落地） | 2026-10-26 |
| `TODO-078` | 变更单只绑**一条**记录（多记录变更未支持）（2026-10-26 落地） | 2026-10-26 |
| `TODO-079` | 矩阵管理面**没有前端**（2026-10-26 落地） | 2026-10-26 |
| `TODO-080` | P9A-DLV-007 评审的 **3 条 deferred minor**（2026-10-26 全部落地） | 2026-10-26 |
| `TODO-081` | `approve_change_notice` 是**绕过矩阵的第二条关闭路径**（2026-10-26 落地） | 2026-10-26 |
| `TODO-088` | 6 条约束按 **schema** 补齐（2026-10-27 落地） | 2026-10-27 |
| `TODO-099` | 后端单测全跑内存 SQLite，PG 语义无自动化车道（2026-11-03 关闭 · `b127495`） | 2026-11-03 |
| `TODO-101` | `StateBadge` 的 DELIVERABLE 强调词表是**记录侧 9 态** ⇒ 交付物半透明（2026-11-03 关闭 · `51657ac`） | 2026-11-03 |
| `TODO-102` | `POST /projects` 的 `IntegrityError → 409 PROJECT_NO_CONFLICT` 映射**过宽**（2026-11-03 关闭 · `909bc3a`） | 2026-11-03 |
| `TODO-103` | `schema_compact_orm.md` 是 **53 表快照**（ORM 现有 107 张）（2026-11-03 关闭 · `0a0efd5`/`b948044`/`72f20be`） | 2026-11-03 |
| `TODO-089` | 两个 `PcsError` 变体**合并成一个类**（2026-10-27 落地） | 2026-10-27 |
| `TODO-082` | 两道「已对外生效」的门换成**真实可判定**的条件（2026-10-27 落地） | 2026-10-27 |
| `TODO-083` | 变更单闭环**没有前端入口**（2026-10-26 落地） | 2026-10-26 |
| `TODO-084` | P9A-DLV-011 评审的 **5 条 deferred minor**（2026-10-26 全部落地） | 2026-10-26 |
| `TODO-090` | `locked_by_deliverable` 列**写成审计标记**（2026-10-27 落地） | 2026-10-27 |
| `TODO-085` | 矩阵修改的**申请 + 双审** —— 本项目**不做**（业务裁决，2026-10-27） | 2026-10-27 |
| `TODO-086` | 重走变更后，变更单的**绑定哈希**不再等于记录当前哈希（2026-10-26 落地） | 2026-10-26 |
| `TODO-087` | 撤销/放弃**真的恢复**记录的数据与哈希（快照不再恒空）（2026-10-26） | 2026-10-26 |
| `TODO-104` | 已闭环（2026-11-09 · P9B-4 紧急批次） | 2026-11-09 |
| `TODO-108` | 已闭环（2026-11-11 · P9B-4 体验批 T2） | 2026-11-11 |
| `TODO-112` | 已闭环（2026-11-09 · P9B-4 紧急批次） | 2026-11-09 |
| `TODO-113` | 已闭环（2026-11-09 · P9B-4 紧急批次） | 2026-11-09 |
| `TODO-114` | 已闭环（2026-11-09 · P9B-4 紧急批次） | 2026-11-09 |
| `TODO-118` | 已闭环（2026-11-09 · P9B-4 紧急批次） | 2026-11-09 |
| `TODO-116` | 已闭环（2026-11-11 · P9B-4 体验批 T1） | 2026-11-11 |
| `TODO-121` | `PipeClassListPage` 的 antd Table 报 React key 警告 ✅ 已闭环（2026-11-04） | 2026-11-04 |
| `TODO-122` | 批次上限的 `int(raw)` 会把 JSON `true` 当成 **1** ✅ 已闭环（2026-11-04） | 2026-11-04 |
| `TODO-123` | 换筛选条件时**不清行选择** ⇒ 可能提交「看不见的行」 ✅ 已闭环（2026-11-04） | 2026-11-04 |
| `TODO-124` | 批次摘要**不区分**「真提交」与「幂等命中」 ✅ 已闭环（2026-11-04） | 2026-11-04 |
| `TODO-125` | `POST /streams/batch-submit` 的 `stream_ids` **没有硬上限** ✅ 已闭环（2026-11-04） | 2026-11-04 |
| `TODO-126` | `system_setting_service.py` 的注释说批次上限「**本批无消费者**」 ✅ 已闭环（2026-11-04） | 2026-11-04 |
| `TODO-127` | 403 的文案对**写操作**说「无权查看」 ✅ 已闭环（2026-11-04） | 2026-11-04 |
| `TODO-121` | 2026-11-04：TODO-121~127 全部闭环（整批评审的 7 条 Minor） | 2026-11-04 |
| `TODO-132` | 已闭环（2026-11-11 · P9B-4 体验批 T0-B） | 2026-11-11 |
| `TODO-133` | 已闭环（2026-11-11 · P9B-4 体验批 T0-C） | 2026-11-11 |
| `TODO-134` | 已闭环（2026-11-11 · P9B-4 体验批 T0-E） | 2026-11-11 |
| `TODO-135` | 已闭环（2026-11-11 · P9B-4 体验批 T0-F） | 2026-11-11 |
| `TODO-136` | 已闭环（2026-11-11 · P9B-4 体验批 T0-D） | 2026-11-11 |
| `TODO-140` | 「设备引用（JSONB 数组）」**是否**计入 📎×N ✅（已裁决 · 维持不计） | 2026-11-11 |
| `（批次汇总）` | 2026-11-12：P9B-4 评审修复批 —— 19 条 finding 全部闭环 | 2026-11-12 |
| `TODO-149` | P10-B 开工前先量一次「18 个 E2E 场景的种子数据规模」 ✅ 已答（2026-11-13） | 2026-11-13 |
| `TODO-156` | PRO/II 解析器**不抽组成** ⇒ 导入的物流**进不了计算链** | 2026-11-16 |
| `TODO-157` | 前端**没有设备清单页**（`/equipment-list` 有端点无页面） | 2026-11-16 |
| `TODO-159` | 前端调用了**不存在的端点**的 3 个页面（真后端下打不开数据） | 2026-11-16 |
| `TODO-160` | 物性/许用应力/毒性三页**首屏 422**（空查询打后端） | 2026-11-16 |
| `TODO-164` | **默认单测车道**连了**开发库**与**真 Redis** ⇒ ⇒ 违反「单测车道绝不碰开发库」 | 2026-11-23 |
| `TODO-165` | 依赖**真 Redis 语义**的测试该迁到 `scripts/pytest_pg.sh` 车道 | 2026-11-23 |
| `TODO-166` | 公司管级列表里**要不要**出现「E2E 种子管级」 | 2026-11-17 |
| `TODO-168` | 默认车道的**漂移守卫**仍连**开发库**（只读） | 2026-11-23 |
| `TODO-169` | **FORMAL 工作区是否必然属于一个项目**？要不要 **PERSONAL 工作区**这种形态？ | 2026-11-18 |
| `TODO-171` | `DefinitionService.update` 的**写闸**没有独立断言（删掉 ⇒ 71 条全绿） | 2026-11-23 |
| `TODO-176` | 默认 `client` 把**项目守卫 mock 成永远 True** ⇒ ⇒「已覆盖」的结论需要复核 | 2026-11-23 |
| `TODO-173` | `config.py` 的 **8 个端点**的角色闸**没有 403 断言** | 2026-11-23 |
| `TODO-174` | 报表执行的**项目作用域**从不对执行者做授权判定（跨项目读 · **high**） | 2026-11-18 |
| `TODO-178` | `test_publish_requires_reviewer_role` **不敏感于它命名的缺陷**（「自审自批」） | 2026-11-18 |
| `TODO-179` | `records.py` 的**读面**既不要求登录也不做项目授权（匿名可读任意项目的管路记录） | 2026-11-18 |
| `TODO-180` | `records.py` 写面授权的 id 与落库的 id **不同源**（跨项目写入） | 2026-11-18 |
| `TODO-181` | `records.py` / `report.py` 的**项目守卫零断言**（变异无人应答） | 2026-11-23 |
| `TODO-182` | `records.py` 的状态机守卫在 `ws.project_id IS NULL` 时**整段跳过** | 2026-11-18 |
| `TODO-183` | `test_project_level_uses_project_access_not_admin` 的断言**恒真** | 2026-11-23 |
| `TODO-185` | `GET /records/piping/{pipe_id}`（详情端点）**零测试** | 2026-11-18 |
| `TODO-186` | `workspaces.py` 的三个端点**不要求登录**（匿名枚举 + 匿名写库 + 审计伪造） | 2026-11-18 |
| `TODO-188` | `GET /user-projects/me` 的**角色清单不全** ⇒ 合法用户 403 | 2026-11-23 |
| `TODO-189` | 仓库里有**两个**「不 mock 项目守卫」的 client ⇒ ⇒ 棘轮看不见其中一个 | 2026-11-23 |
| `TODO-172` | **已裁决并落地**（2026-11-18 · commit `09c9282`） | 2026-11-18 |
| `TODO-175` | **已裁决并落地**（2026-11-18 · commit `09c9282`） | 2026-11-18 |
| `TODO-190` | `obsolete`（作废报表定义）**不查 `created_by`** ⇒ ⇒ 任意审核角色都能作废别人的定义 | 2026-11-18 |
| `TODO-191` | 前端「保存并发布」对**创建人自己**没有提示 ⇒ ⇒ 点了才吃 403 | 2026-11-18 |
| `TODO-193` | mock ↔ 契约的漂移棘轮**看不见 `:param` 写法的端点**（14 条欠账） | 2026-11-19 |
| `TODO-194` | 前端**没有项目选择器** ⇒ 「项目作用域」只能取**第一个**有项目的工作区 | 2026-11-19 |
| `TODO-195` | PMS / BEDD **后端没有实体** ⇒ 两页只能是占位（产品语义） | 2026-11-19 |
| `TODO-199` | 4 条端点的契约**本身就是裸 object** ⇒ ⇒ 形状无人保证 | 2026-11-23 |
