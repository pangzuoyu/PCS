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

---

## 🔴 P0 — 真问题（部署阻塞 / 安全）

> 现状（2026-10-07）：4 项中 3 项已做。仅 **TODO-002 token_version** 仍开放。

### ✅ TODO-004 + TODO-019: CORS middleware 已挂载（2026-10-06）

- **原症状**: `grep -rn add_middleware app/` 全仓 0 命中 —— `cors_allow_origins` 配置项在，
  中间件从未挂载。**前后端一分域部署 preflight 直接 403**，dev 靠 Vite proxy 掩盖。
  旧的 `test_cors_allow_origins_parsed` 只测配置解析，不测中间件 —— 又一个「测了但没测到东西」。
- **落地**: `create_app()` 挂 `CORSMiddleware`（`allow_credentials=False`，全栈 Bearer token
  无 cookie，开凭证还会与 `*` 冲突）；lifespan startup 调 `validate_cors_for_production()`。
- **新函数**（`app/core/config.py`）: `parse_cors_origins()` / `validate_cors_for_production()`。
  prod 下 `*` 或空串均 fail-fast —— 症状会是「所有接口 403」，极难自查，必须启动期炸。
- **验证**: 8 条新测试（含真实 preflight 往返）。全量 3932 passed / 0 failed（+8）。
- ⚠️ **未覆盖**: lifespan startup 真正触发 fail-fast 的端到端路径（需跑 lifespan →
  依赖真实 DB）。函数本身有测试，调用点是一行，读代码可确认。

### ✅ TODO-006: 认证端点限流 + 登录审计（2026-10-07，`d196daa`）

- `/auth/login` 与 `/auth/refresh` 各 10 次/分钟/IP；login 成功与失败**都**写
  `audit_logs`（`LOGIN_SUCCESS` / `LOGIN_FAILED` + ip）——失败不记等于暴力破解无痕。
- `AuditService.write` 增加可选 `ip` 参数（`audit_logs.ip` 是 INET 列，此前无法填）。
- 实施中修掉两个真 bug（均由测试暴露）：
  1. **审计写入能把登录打挂** —— INET 列只接受合法 IP，而 `request.client.host`
     在 TestClient 下是 `"testclient"`，PG 抛 DataError → 登录 500。加 `_normalize_ip()`。
     unix socket 场景同样会给出非 IP 值，非纯理论问题
  2. **两处测试污染真实开发库** —— `/login` 新增 DB 依赖后 `test_auth.py` /
     `test_mock_auth.py` 的 TestClient 打到真实 pcs 库。已补 in-memory override，
     实测 `audit_logs` 全程 0 行
- 验证：全量 3938 passed（+6）

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

### ✅ TODO-007: JWT 过期 / 无效已细分（2026-10-07，`d196daa`）

- `security.py:116` docstring 早就承诺「由调用方转 PcsError」，但全仓
  `EXPIRED_TOKEN` 零命中 —— **承诺从未落地**。现拆为：
  `_decode_bearer` → `EXPIRED_TOKEN` / `INVALID_TOKEN`；
  `/auth/refresh` → `EXPIRED_REFRESH` / `INVALID_REFRESH`（对称）。
- 错误码注册表是 AST 派生的，4 个码自动收录（已实测）。
- **不重命名 `INVALID_TOKEN`**：被 `tests/test_auth.py` 与前端 meta seed 引用，
  改名收益不抵破坏面。
- ⚠️ **前端静默刷新仍未做**（TODO-001 遗留项）。`api/client.ts` 对任何 401 都直接
  跳登录。前端 meta seed 的 `ui_behavior` 因此保持 `redirect_to_login` 而非
  写成未实现的「静默刷新」——种子数据不应承诺没实现的行为。
  分码当前价值在可观测性。

---

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

### ✅ DONE —— 10 张计算表主键 rename（2026-10-08 核实关闭）

**原记录把方向记反了，而且这项工作早已完成。**

- **原 What**：`vessel_id→vessel_calc_id` / `cv_id→cv_calc_id` 等 10 条 rename。
- **权威方向是反的**：`docs/PCS-PLAN-P5-DEVICE-EQUIPMENT.md:106` 明写
  ——「10 表主键 rename（**`vessel_calc_id→vessel_id` / `heat_calc_id→heat_exchanger_id`
  等 DICT V3.3 §4.1**：移除 `_calc` 后缀……**V1.3 plan 文本写反了方向**，2026-09-16 修订）」。
  `docs/adr/0027-heat-results-dual-track.md:82` 记同一句。**是去掉 `_calc` 后缀，不是加上。**
- **实际主键（2026-10-08 从 ORM 读出）**：`vessel_id` / `heat_exchanger_id` / `cv_id` /
  `network_id` / `orifice_id` / `cooling_tower_id` / `psychro_id` / `sep_equip_id` /
  `filter_id` / `open_channel_id` —— 全是短名，**已符合 DICT V3.3 §4.1**。
- **完成度核实**：全库 102 张表 / 105 个主键列，**`*_calc_id` 残留 0 个**；
  `uv run alembic check` exit 0，证明 DB 侧同样是短名（ORM 与 DB 一致）。

**原记录的证据为什么误导**：「`grep -rn "vessel_calc_id|..." app/models/` 仅 2 处命中
—— 基本未做」。那 2 处命中的是**规划文档里的旧方向描述**，不是 ORM 声明。
因为方向记反，grep 找的是「应该被移除的名字」，找到 0 个 ORM 声明就被读成
「没做」，实际含义是「已经做完了」。

⚠️ 原记录里 4 个「旧名」与实际不符：`net_id`（实际已叫 `network_id`，即目标名）、
`restriction_id`（实际 `orifice_id`）、`ct_id`（实际 `cooling_tower_id`）、
`channel_id`（实际 `open_channel_id`）。若照原文执行会改错列。

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

## ✅ DONE —— TODO-041: antd `dataIndex` 是类型闸的洞（2026-10-19 修完）

`tsconfig` 的 `include` 已含 `tests`（那次纳入带出 7 条噪声，清完）。
但那道闸有个洞：**抓得住属性访问与漏必填，抓不住 `dataIndex`** ——
而没有 `render` 的列，值的唯一来源就是 `dataIndex`，bug-180 正是死在这里。

### 补法：选了「收窄类型」而不是 eslint 规则

新增 `src/types/strictColumns.ts` 的 `StrictColumns<T>`：把 `dataIndex`
从 antd 的 `string | string[]` 收成 `DeepKeys<T> | DeepKeys<T>[]`。
**18 个页面的 `ColumnsType<X>` 标注全部替换**，`<Table columns={…}>` 照常工作
（可赋值性已验证 —— 那是这套设计的前提，不是巧合）。

选它不选 eslint 规则：**编译期闸比 lint 硬**，且替换是机械的（只改类型标注，
不改任何列内容）。lint 规则只能报「你用了字符串字面量」，消掉它需要
`as` / `satisfies` —— 而那正是把闸拆掉的动作。

### 两个必须记下的设计约束（都踩过）

1. **不能写 `readonly`**：antd 的 `dataIndex` 是可变数组，写成
   `readonly DeepKeys<T>[]` 会让 `StrictColumns<T>` 不再可赋值给
   `ColumnsType<T>`，`Table` 直接报错 —— 闸变成障碍，人就会去绕它。

2. ⚠️ **`DeepKeys` 必须过滤索引签名容器**（`string extends keyof T ? never`）。
   契约类型几乎每张表都有 JSONB 列，openapi-typescript 生成
   `{ [key: string]: number }`；递归进去后 `keyof` 塌成 `string | number`，
   **整个并集被污染 → `DeepKeys<T>` 变成 `string` → 任何 dataIndex 都合法**。
   实测 `PipeClassResponse.allowable_stress_json` 一个字段就足以让
   bug-180 的 `dataIndex: 'pipe_class_id'` 通过。

   ⚠️ 这个坑**第一版就踩了**：自检用的是干净的 `interface Row`，探针全绿；
   接到真页面上才发现闸根本没生效。⇒ **闸的自检必须用真实契约类型**，
   干净的假接口比生产环境宽容得多（与「fixture 比被测物干净」同族）。

### 闸的自检（`tests/types/strictColumns.test.ts`，11 条）

- 用 `@ts-expect-error` 断言「该红的一定红」：闸失效时这些抑制变成
  「未使用」，`tsc` 报 TS2578 ⇒ **闸的失效能被它自己抓到**（已变异验证三条全报）。
- 含**已知边界**的显式用例：数组形式只校验「每段都是某层的 key」，
  不校验「这些段能串成一条路」（`['class_id','class_name']` 会过）。
  有意的取舍 —— 严格路径要 `as const`，而 `as const` 一旦为了「让闸闭嘴」
  而加，闸就没了。
- 变异验证：在真实页面 `PipeClassListPage` 上把 `dataIndex` 改回
  `'pipe_class_id'` → 编译期报错并列出契约里的真实字段。
