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

## ⚪ BLOCKED — 宿主未开工 / 等外部方

### TODO-005: LDAP TLS
- 等 IT 提供 LDAPS 端口 + CA 证书。`app/` 全仓无 `use_start_tls`/`use_ssl`。

### TODO-010: 多态 FK 应用层校验
- **前提不成立**: 挂「P1 deliverable 模块」，但 deliverable 至今**只有 5 张表 ORM 骨架，无 service、无 API、无路由**
  （`DeliverableRecordBinding` 在 `app/api/`、`app/services/` 零命中）。没有写入方就没有校验点。
  deliverable 开工时再捡起。

### TODO-012: make_draft_record fixture 覆盖全部 record type
- **描述已过时**: 条目写「17 类」，实测 `RECORD_TYPE_REGISTRY` 现有 **21 类**（P5-0-1b 又 +1 thermosiphon）。
  且 `make_draft_record` 在 `tests/` 全仓 0 命中，conftest 只有 `make_asset`/`make_user`。
  **照原文实现会写错** —— 要做先按 21 类重写条目。

---

## ♻️ STALE — 需重新裁决，不是照做

### TODO-042: PIPE_LINE_LIST DETAIL 视图补全
- 条目说「DETAIL 25 列含 `compressor_kw`/`heat_duty_kw` 等计算结果字段，部分列显示空」。
- **实测**: `PipeLineListPage.tsx` 全文件仅 21 个 `dataIndex`；`compressor_kw` 全仓 **0 命中**。
  **25 列契约已不存在**（列被删，不是待回填）。需先裁决 DETAIL 到底要哪些列，否则「回填」无处可指。

### TODO-033: Sprint 1.9 终审 DEFER 卫生批
- 自然消解若干；仍有残留：`pipe_class_service.py:49 _STATUS_OK` 死常量、`test_category3_seeds.py:58 creates_six` 命名、
  `app/main.py:33`「6 张」注释过时。均为 LOW，纯清理。

### TODO-003: JSONB GIN 索引（🟡 PARTIAL）
- 已建 1 个（`p7_s1_002_audit_logs_jsonb_gin.py:37`）；条目列的 3 个候选列未建。
- 触发条件「首个按 JSONB 内容过滤的端点」是否已出现需确认；未出现则不急。

### TODO-020: ADR-0012 ↔ ADR-0024 交叉引用（🟡 PARTIAL，单向）
- ADR-0024 已引用 ADR-0012（`:6,:11,:31`）；**ADR-0012 未反向标注被 0024 修订**。
- SPEC/DICT 同步部分：DICT-ALL-003 已滚到 **V3.6**，条目里说的「V3.2」已过时。

### `mypy --strict`（P1.2 收尾项）
- `pyproject.toml` 无 `strict` 配置，未启用。

### TODO-008 的隐性债（✅ DONE 但有雷）
- FK 改名**不是**用 `RENAME CONSTRAINT` 达成的，而是靠 `p1_sprint3_nullable_equipment_type_codes.py:36`
  `DROP CONSTRAINT pk_equipment_type_codes CASCADE` 的副作用连带删掉旧 FK，再用新名重建。
- **⚠️ 该迁移 downgrade 时会重建旧名 `fk_equipment_list_type_code`**（`:98-104`）——
  若将来跑 downgrade→upgrade，ORM 与 DB 会漂移。值得加一条注释或补一个正式 rename 迁移。

---

## 🕐 时间债（非代码）

### PRO/II 真实工程数据脱敏入库
- `tests/fixtures/proii/` 现有 5 个 .inp + 5 个 .inp.out **已入 git，但全是从对话历史重建的合成文件**。
- 仓库根 `sample/` 有真实工程数据（`dmc.inp` / `huafeng140_FCC2015.out` / `200FlexiCoking1.out` + 多个华南海东 xlsx），**尚未脱敏入库**。
- 单元测试基线的多样性取决于样例多样性 —— 真实工艺配置才是质量保证。

---

## ✅ 已关闭归档（核销于 2026-10-06，**勿按原文重做**）

| 条目 | 实际落地路径（与条目描述不同处已标） |
|---|---|
| TODO-001 前端测试基建 | `pcs-frontend/vitest.config.ts`；现 569 tests |
| TODO-008 FK 改名 | ✅ 但绕过式，见 STALE 区雷点 |
| TODO-009 血缘递归深度 | `lineage.py:149,176 max_depth=10`（**条目写 ≤8，实际落 10**）+ 环检测 |
| TODO-011 snapshot_status + ADR-0024 | `p1_sprint2_state_machine.py:39` 加列 / `deliverable.py:259` ORM / ADR status: accepted |
| TODO-013 | `change_pending_since` DONE（`state_machine.py:327,329`）；`old_record_hash_before_change` → 🚫 WONTFIX（ADR-0024 明写不新增列，改从快照读） |
| TODO-014 ADR-0025 | 见上方开放技术债区（ADR 已写，前端标记未实现） |
| TODO-018 ARQ 独立文件 | `app/workers/workspace_tasks.py` + `worker.py:61-63` 注册 |
| TODO-021 双引擎连接池 | `app/db/session.py:33-37`（5/45/30/1800）+ `:67-71`（10/20） |
| TODO-022 data_lineage 索引 | ✅ **列已改名 `occurred_at`**，索引随之建（`models/system.py:68`） |
| TODO-024 equipment_list 对齐 DICT | 条目称「18 列缺 56」→ **实测 69 列**，早做完了 |
| TODO-025 pump_results 补 6 列 | 实测 26 列 |
| TODO-030 openpyxl write_only | `export_service.py:45` write_only=True；条件链已走完（in-memory 10k×20 实测 6.8s > 2s 预算） |
| TODO-031 preconditions 门禁 | 复核通过：`config.py:297` PUBLISH → `formula_service.py:72,76` |
| TODO-036 StreamSignStatus 9 态 | `p3_sim_stream_sign_status_extend.py` |
| TODO-037 unreliable 硬拒绝 | `calc_entry.py:53 STREAM_UNRELIABLE_BLOCKED` / `UnreliableStreamGuard` |
| TODO-038 PRO/II fixtures | **路径不是 `app/seeds/proii_samples/`**，实际在 `tests/fixtures/proii/`，5 组已 tracked |
| TODO-043 Dashboard 3 端点 | `mocks/handlers.ts:138,142,146` 三条已注册 |
| P6-OPEN-009 psv_results 缺列 | `p6_5_006_orm_db_drift_final_fix.py` 已补 |
| P5-2 PSV 多标准前置 | `p5_0_5_psv_multi_standard.py` + `models/psv_standards.py` + `services/psv/psv_persist.py` |
| P1.2 组件清单 | `LineageGraph.tsx` / `RevTimeline.tsx` / `ChangeImpactPanel.tsx` 都在（**已改名**，非原名） |

**TODO-032 的 27 个真库测试文件**（超出条目声称的 4 个）：
`tests/models/{test_pipe_class_migration, test_sup008_result_fields, test_htri_template_schema, test_calc_audit_fields, test_sup008_column_sizing_design_stage}`、
`tests/services/{test_toe_conversion_service, test_cepci_seed, pipe/test_pipe_chain, pipe/test_two_phase, cool_tower/test_heat_aggregator, cool_tower/test_cool_tower_persist_service, psychro/test_saturation_persist_integration, psychro/test_psychro_persist_service, flare/test_flare_persist_service, flare/test_relief_aggregator, open_channel/test_open_channel_persist_service, filtration/test_filtration_persist_service}`、
`tests/{test_audit_guard, test_rbac_audit, test_cia_tasks}`、
`tests/seeds/{test_detail_templates, test_category3_seeds}`、
`tests/scripts/{test_p6_3_gate_04_seed, test_p6_3_gate_05_seed, test_p6_3_gate_06_seed}`

---

## 🚫 已裁决不做

- **CI/CD 流水线**（原 SPEC-P0 §3.2.5）：单人开发裁决 2026-08-29。多人协作时重新提出。
- **TODO-027 cost_est_results 补 RecordMixin**：`CostEstResult` docstring 明写「与设备一对一，不带 sign_status（跟随所属设备）」，
  cerebrum Do-Not-Repeat 亦记录此契约（与 `TwoPhaseResult` 同）。**补 RecordMixin 会破坏它。**
- **TODO-013 的 `old_record_hash_before_change` 列**：ADR-0024 Consequences 明确「P1-MVP 不新增列，从快照表读取旧哈希」。

---

## 核销方法学备注

- 4 组并行只读核验（子代理）+ 主会话实证，覆盖 44 条编号项 + 4 条无编号项，无一条凭印象下判。
- ⚠️ **核验时慎用组合正则**：本次发现子代理首轮 `grep "A\|B"` 被 rtk 过滤层吞掉、误报「0 匹配」，
  拆成两个独立 `grep -c` 后才得真实计数。多模式核验应逐条单发。

---

## ✅ `alembic check` 假漂移已修（2026-10-06，`app/models/__init__.py` 补 `util`）

- **原症状**：`uv run alembic check` 恒报 130 条（14 remove_table / 88 remove_index /
  26 add_index / 2 add_column），全假。CLAUDE.md 指定的人工守门动作因此形同虚设。
- **根因**：`alembic/env.py:7` 只 `import app.models  # 注册全部 53 表`，
  而 `app/models/__init__.py` 列了 16 个模块却**独漏 `util`**。
  实测：修复前裸 `import app.models` → **95 表**；修复后 → **102 表**。
- **修法**：`app/models/__init__.py` 补 `from app.models.util import *`。
  该包 docstring 明写「alembic/env.py 依赖本包导入即注册全部表」——漏 `util` 违反的是它自己的契约。
- **效果**：130 → **84** 条，`remove_table` 归零（7 张 UTIL 表对 autogenerate 可见了）。
- **为什么测试此前没炸**：`tests/conftest.py:34` 的 `from app.api.v1 import api_router`
  链式带出了 util 模型。**曾误判为「测试库缺 7 张表」，实测证伪**（隔离跑
  `tests/services/util/test_gas_media_and_low_temp_heat.py` → 8 passed）。特此记录以免重犯。
- **验证**：全量 3924 passed / 0 failed（与修复前同基线）；test_schema 7 passed；
  ruff clean；幂等闸 0 violations。

## ✅ DONE —— `alembic check` 的 84 条**真**索引漂移（2026-10-07 复核为 0）

- 原记 84 条构成：52 `remove_index`（DB 有、ORM 无）+ 30 `add_index`（ORM 有、DB 无）
  + 2 `add_column`，典型形态是改名对不上（`ix_cepci_year` vs `ix_cepci_index_series_year`）。
- **2026-10-07 复核：`add_index` / `remove_index` 漂移已归零**（与本批 84 条索引漂移
  核销、`p7_s5_002_sign_status_indexes` 等一并完成）。

## 🔴 `alembic check` 剩余 349 条 `modify_comment`（2026-10-07 首次能跑时暴露）—— **需产品裁决**

- **现状**：应用 `p7_s5_005` + `p7_s5_006` 后，`alembic check` 结构化口径共 350 条：
  **349 条 `modify_comment`（47 张表）** + 1 条 `add_column`（= bug-143，`p7_s5_006` 已修）。
  `modify_nullable` / `modify_type` / 索引类均为 **0**。
- **性质**：COMMENT 是**纯元数据**，不影响功能、不丢数据、不会让查询变慢。
  代价纯粹是「每次 `alembic check` 都刷 349 行噪声」，守门价值被打折。
- **🔴 这不是纯技术债，必须先裁决方向**，因为两条路的代价是不对称的：
  - **对齐 DB → ORM**：写一条迁移把 349 条 COMMENT 改成 ORM 的写法。一次性成本低，
    但**从此以后每次改 ORM 的 comment 都得再写一条迁移** —— 把「写注释」变成
    「改 schema」，长期摩擦很大。
  - **对齐 ORM → DB**：改 349 处 ORM docstring/comment，零迁移。但会丢掉 DB 侧已有的
    更详细注释（如 `cepci_index_series.year` 的 DB 注释其实更准）。
  - **第三条路**：给 `alembic check` / autogenerate 关掉 comment 比对
    （`include_object` 或 `compare_comment=False` 之类），承认 COMMENT 不进契约。
    代价是注释漂移永久不可见 —— 但注释本来就不该是契约。
- **建议**：倾向第三条路 + 顺手把 ORM 侧明显更短的注释补齐。理由：注释不是行为契约，
  为它建迁移是把工具的噪声当成了模型的约束。
- **Owner**：待认领（**未做**，仅登记）

## 🟡 CATEGORY_6 地基 5 项：4 项已做，1 项按裁决不做（2026-10-07 更新）

**原 5 项硬伤**（`docs/PCS-NOTE-equipment_lib-废弃-2026-10-06.md`）的现状：

| # | 项 | 状态 |
|---|---|---|
| 1 | `type_code` 根本没采集（相似度无主匹配键） | ✅ 已做 `5017ced`。settle 采集，**源设备优先**（源是权威，避免调用方与源各报一个导致型号错配） |
| 2 | settle 无去重约束 | 🚫 **按裁决不做** —— 用户 2026-10-07 选「不硬去重，交给相似度归并」。库内允许重复，相似度是唯一识别手段 |
| 3 | `weight_kg` / `key_dimensions` 埋在 JSONB 无索引 | ⏸️ **有意延后**。相似度形态是「取候选集 → Python 打分」而非 SQL 内过滤排序，当前无支撑表达式索引的查询模式；CATEGORY_6 真库 0 行。属投机性工作 |
| 4 | `category` 无枚举 + 零索引 | ✅ 已做 `1448e02`（`p7_s5_004`）。CHECK 约束拒收域外值 + `(category,status)` 复合索引 |
| 5 | 审批语义冲突（SPEC 要单层，实际 5 态链） | ⏸️ **未做**，需产品裁决 + 动审批状态机，不宜顺手改 |

**相似度本身已实现**（`3702888`，UI-SPEC §7.16）：5 维加权、缺数据跳过权重重新归一、
`ref_*` 参照参数 + 按相似度降序 + 三档（≥90% RECOMMEND / 80~90% VERIFY / <80% DISPLAY_ONLY）。

实施中修掉一个设计缺陷：`equipment_type` 原被当相似度维度，但它同时是**检索过滤条件** ——
筛 PUMP 时每条在「类型」上恒为 1.0 而其余维度缺值跳过，导致**全部条目都算出 1.0/RECOMMEND，
信号变成噪声**。已移出维度集（单元测试当时全绿，实际跑数据才暴露）。

- **附带事实**：`ConfigAsset` CATEGORY_6 在真库仍 **0 行** —— 设备库功能从未被真实使用过。
  上述能力均只在 SQLite 测试库中验证过。
- **Owner**: 待认领

## 🔜 UI-SPEC §7.16 与实现的完整差额 —— **已裁决延后到下一版本**（2026-10-07）

> 用户裁决：本版本不做，作为未来功能增强。**不是遗忘，是裁决。**
> 完整决策记录 + 下一版本启动前的两个前提见
> `docs/PCS-NOTE-UI-SPEC-7.16-设备库检索延后-2026-10-07.md`。

**更正**：上文「地基 5 项全部完成」是错的。那 5 项是首轮审计识别出的**后端缺口**，
不是与 SPEC 的完整差额。逐条核对 SPEC §7.16 后，13 项要求只满足 2 项：

| SPEC §7.16 要求 | 状态 |
|---|---|
| **检索 · 工艺条件模糊搜索** | ❌ 只有 `keyword` → 设备名 ILIKE，**不是工艺条件**（压力/温度/介质） |
| **检索 · 参数区间** | ❌ 完全没有 min/max 过滤 |
| **检索 · 相似度计算** | ✅ 已做 |
| **结果列 · 设备类型 / 规格 / 材质 / 重量 / 标准图号** | ❌ `AssetResponse` 只有 asset_id/category/name/status/current_version，**SPEC 要的 8 列里 5 列没暴露** |
| **结果列 · 相似度** | ✅ 已做 |
| **结果列 · 原项目 / 投用日期** | ❌ 没有 |
| **limit ≤ 200** | ✅ |
| **分页** | ❌ 只有 limit，无 offset / total |
| **前端页面** | ❌ **完全没有**（`pcs-frontend/src` 下除生成的 `api.d.ts` 外零引用） |

### 两个额外发现

1. **「参数区间」当前无法实现，不只是没写**。`ApplicableConditions` 把工艺条件存成
   **自由文本区间串**（`pressure_mpa="0.1~2.5 MPa"`、`temperature_c="-20~200 °C"`），
   要做区间查询必须先解析文本。这是数据模型问题，不是加个索引的事。
2. **CATEGORY_6 第 3 项（JSONB 索引）当初的延后理由是错的**。我当时的理由是
   「没有支撑表达式索引的查询模式」—— 但 SPEC §7.16 **明确要求参数区间**，
   那就是查询模式。SPEC 是需求，不是等数据来了才成立。延后理由应改为
   「需先解决 applicable_conditions 自由文本的数据模型问题」。

- **Owner**：待认领（规模明显大于上面那 5 项，建议单独立项而非并入 CATEGORY_6）

---

## ✅ DONE —— 9 个既有 `p7_open_*`/`p7_s1_*` 迁移补幂等 guard（2026-10-07）

> ⚠️ **本条曾在 2026-10-06 的 `TODOS.md` 全量重写中丢失**（只剩 `STATUS.md` 提过），
> 2026-10-07 补回并已闭环。

- **结果**：共补 **49 处** guard，`alembic/versions/` 下 **28 个 `p7_*` 迁移全部纳入检查**，
  闸门 `OK: 0 violations`。原记的逐文件条数有两处偏低（`p7_open_009_005` 实为 7 非 6、
  `p7_s1_005` 实为 7 非 6），与此前「84 条」低估同源的字符串扫描问题，已按 AST 重数。
- **顺带修掉闸门自身的两个缺陷**（这才是本条的真正价值 —— guard 缺失只是症状）：
  1. **闸门用「行内子串 + 上下 8 行窗口」判定，长期假绿**。`p7_s3_005` 的
     `downgrade()` docstring 写着「删两张子表 (if_exists 幂等)」，窗口里的
     `if_exists` 掩盖了下面两行**实际没带** guard 的 `op.drop_table` ——
     白名单内的文件都被判为已加。已改为 AST 判定（`check_migration()`）。
  2. **`SAFE_OPS` 里 `op.create_unique_constraint: ["if_not_exists"]` 是错的**。
     实测 alembic 1.19.1 的 `create_unique_constraint` 签名无该形参（只有 `**kw`），
     PG 也不支持 `ADD CONSTRAINT IF NOT EXISTS`；传进去不报错但被静默吞掉，
     是「看着加了 guard 其实没加」，比不加更危险。已移出检查范围并在 docstring 写明原因。
- **验证**：注入式回归 —— 删掉 `p7_s5_004` 的一个 `if_not_exists`，闸门如期 FAIL(1)，
  还原后 OK(0)。全量 `pytest tests/ -q` = **3954 passed / 77 skipped / 1 xfailed / 0 failed**。
- **加 guard 的语义已逐个确认**：全部 `drop_table` 都在 `downgrade()`，无 upgrade 侧
  先删后建的隐患；`if_exists` 只放宽「对象不存在时不报错」，不改变已存在时的行为。
- **残留**：`p7_open_010_*` 两个文件有 19 条 ruff 报错（D103/E501/I001/F401），
  HEAD 上同样存在，非本次引入，按「不重构无关代码」未动。

## ✅ `.wolf/buglog.json` id 重号已去重（2026-10-07）

> 同上，本条也在 2026-10-06 重写中丢失，2026-10-07 补回并当场修复。

- **登记时的描述已过时**：当时记的是「四条 `bug-2026` + `bug-031`/`bug-002` 各重复，
  共 6 条重号」。实际 `bug-2026` 那四条早已被改成 `QA-2026-09-16-001..004`，
  **只剩 2 对重复**：`bug-002`（2 条）、`bug-031`（2 条）。
- **为何可以改号**：原方案说「不改历史条目的 id，因为 `fix_commit` 是 STATUS 反查的
  单点来源」。实测这 4 条的 `fix_commit` **全是空**，没有反查链可断 ——
  前提不成立，所以可以安全改号。
- **处置**：按「早的保留原号（稳定）」，晚的补空洞号，并双向 `related_bugs` 互链 +
  `id_reassigned_from` / `id_reassigned_reason` 留痕：

  | 保留 | 改号 | 改号原因 |
  |---|---|---|
  | `bug-002`（Incorrect value in code, 08-31） | `bug-039` | alembic `tag_number ... already exists`（09-16） |
  | `bug-031`（Wrong operator, 09-01 08:18） | `bug-072` | alembic `NameError: name Enum is not defined`（09-01 13:01） |

  复核：140 条，重复 0 个。
- **编号规则（防止复发）**：新条目用**顺序号 `bug-NNN`，下一个 = 当前 max+1**。
  **绝不使用年份式编号**（`bug-2026` 正是当初 4 条撞号的根因 —— 新条目按
  `max+1` 算出 `bug-2027` 时，`bug-2026` 这个非序号已经存在，于是继承了重号）。
- **Owner**: 已关闭

## 🟡 `auth_consistency.test.ts` 的「所有 auth 调用携带 Bearer token」只覆盖了 1/2（2026-10-07 登记）

- 该用例断言 `lastMeAuth`（`/auth/me` 调用的 Authorization 头），**未断言 mock-login
  那一路**。用例名说「所有 auth 调用」，实际只覆盖 `/auth/me` 一条路径。
- 该文件原本有个 `lastMockLoginAuth` 变量专门捕获 mock-login 的头，但**只写不读** ——
  捕获了却没有任何断言用它。2026-10-07 清 lint 死变量时已删除（若不删，
  `npm run lint` 因 `--max-warnings 0` 直接红，该测试文件则一直绿）。
- **本条不是「补一条断言」那么简单**：mock-login 在真实流程里发生在建会话之前，
  语义上**不应**携带 Bearer token，故正确的断言是 `toBeNull()` 而非
  `toBe('Bearer ...')`。补之前需确认 mock 流程的实际调用顺序。
- **Owner**：待认领（补断言时顺带把用例名改成与实际覆盖一致）

## 🔴 缺一个「ORM↔迁移」的静态列覆盖检查（2026-10-07 登记，**已评估后决定暂不做**）

- **动机**：bug-143（`user_projects.created_by`）是 ORM↔迁移漂移的又一个样本，而
  CLAUDE.md 明写「漂移会绿（不可见）—— 后者没有自动化能抓」。人工守门是
  `alembic check`，但它要求 DB 处于 head；一旦有已提交未应用的迁移就整个拒跑
  （本次即如此 —— 守门没报，是因为它根本没跑）。
- **已实测的方案与结论**：写脚本用 AST 解析全部迁移，抽出
  `op.create_table` / `op.add_column` 的 `sa.Column`，与 `Base.metadata` 对比。
  结果 **257 个「未覆盖」列散布 24 张表，全是假阳性** —— 项目大量使用数据驱动的
  循环式迁移（如 `p4_calc_audit_fields` 给 16 张计算表批量加审计列），
  静态解析必须建模这些循环才能不误报，成本与脆弱性都高。
- **结论：暂不做**。与其建一个假阳性一堆的静态分析器，不如把 `alembic check`
  变成**可自动跑的 CI/本地检查**（当前是纯人工记得才跑）。
- ⚠️ **否决范围限于「列覆盖比对」，不含「参数类型检查」**（2026-10-07 收窄）。
  上面那 257 个假阳性只证伪了**拿 `sa.Column` 集合比对 `Base.metadata`** 这一条路 ——
  它被循环式迁移打垮。但 bug-144 那类缺陷（`op.create_table` 收到裸 `sa.ForeignKey`
  位置参数）是**参数类型**问题：纯 AST 可判、与循环迁移无关、**零假阳性**。
  把它和「静态检查不可行」混为一谈，会关掉一个本该很便宜的定向闸门。
- **该加的检查放哪**：`scripts/check_migration_idempotency.py` 已遍历 `ast.Call`、
  且已对 `op.create_table` 特判（`SAFE_OPS` 里映射为 `[]`，因其无幂等 kwarg）。
  加一个「`op.create_table` 的每个位置参数必须是 `sa.Column`/`Constraint`」
  的独立检查函数，边际成本是几行，不是新工具。
- **真正该做的低成本版本**：把「改完 `alembic/versions/*` 必须跑
  `uv run alembic check`」从 CLAUDE.md 的一段文字，变成 git hook / 脚本，
  在提交迁移文件时自动跑一次并阻断。**待认领。**
- **Owner**：待认领（**明确暂不做的是列覆盖比对分析器**）

## 🔴 修正：`alembic check` 漂移真实条数是 **397**，不是先前报的 84 / 350 / 377（2026-10-07）

**这是同一类错误第三次犯**（84 → 377 → 350 → 397），必须记：
**用关键词白名单过滤 `compare_metadata` 的输出时，匹配不上的类别会被静默丢弃，
而总数看起来仍然「合理」，不会触发怀疑。**

- 本轮我写的过滤白名单写了 `add_foreign_key` / `remove_foreign_key`，但 alembic 实际
  发出的 op 名是 **`add_fk` / `remove_fk`** → 7 条 FK 漂移被静默丢掉；
  `remove_constraint` / `add_constraint` 压根没进白名单 → 又丢 40 条。
- 正确做法：**先 `Counter(type(x).__name__)` + 打印实际 op 名分布，再决定口径**，
  不要凭直觉写白名单。

### 397 条的真实构成（DB 停在 p7_s5_005，p7_s5_006 未应用）

| op | 条数 | 方向 |
|---|---|---|
| `modify_comment` | 349 | DB 注释 ≠ ORM 注释（47 张表） |
| `remove_constraint` | 39 | DB 有约束、ORM 无声明 |
| `add_fk` | 6 | **ORM 有外键、DB 没有** |
| `add_constraint` | 1 | `compound_api521_thresholds.threshold_type` 唯一约束 DB 缺 |
| `add_column` | 1 | `user_projects.created_by`（= bug-143，`p7_s5_006` 已写待应用） |
| `remove_fk` | 1 | `fk_utility_energy_summary_workspace_id_workspaces` 的 `ondelete`：DB=CASCADE，ORM=RESTRICT —— **两侧都声明了且不一致** |

- **索引类漂移确认为 0**（`add_index` / `remove_index` 均无），上一条的 DONE 结论成立。
- **`modify_nullable` / `modify_type` 为 0**，`p7_s5_005` 与 `p7_s5_003` 已彻底清干净。

### 🔴 其中 4 条 `add_fk` 是真缺陷（bug-144），且指向 IDOR 守卫

`user_projects` 的 `user_id` / `project_id` / `granted_by` / `revoked_by` **四个外键全缺**。
成因：`p7_open_010_user_projects_blocker3.py:40-43` 把裸 `sa.ForeignKey(...)` 当位置参数
传给 `op.create_table`，被 alembic **静默丢弃**（该 API 只收 Column / Constraint）。

**Owner**：待认领。需新迁移补 FK；补之前先清孤儿行（ADD CONSTRAINT 遇孤儿会失败回滚）。

## ✅ 归属澄清：bug-143 / bug-144 **不属于 P9，是 P7 欠账，应立刻修**（2026-10-07）

对照 `spec/工艺专用综合计算软件需求规格说明书 Web版 P9.md`：

| 发现 | P9 是否安排 | 处置 |
|---|---|---|
| `users` 表 0 行、无代码写入 | ✅ 已安排 —— `P9-ADM-001`「同步后自动创建系统用户记录」+ `POST /api/v1/admin/users/sync`（P9:156） | **P9 开工时做**，本轮不动 |
| token_version | ⚠️ **P9 无此条目**，但 `P9-ADM-001`「离职处理…系统标记为停用」蕴含之 | **P9 开工前补规格条目**，本轮不做 |
| `user_projects` 4 个外键缺失（bug-144） | ❌ P9 完全没提 | **P7 欠账，本轮修** —— 表是 P7-7+ BLOCKER-3 建的；不能拖到 P9，否则 AD 同步建出 users 行后授权表引用完整性仍是空的 |
| 397 条漂移 | ❌ 不在 P9 范围 | 工程债，见上条裁决方向 |

- **已核对无缺口**：P9-ADM-003「会话超时时间 30 分钟」与现有 `access_token_expire_minutes`
  = 30 **正好对上**。
- **Owner**：bug-144 迁移待授权应用

## ✅ COMMENT 比对已关（2026-10-07，`alembic check` 397 → 43）

用户裁决：注释不进契约。落地在 `alembic/env.py` 的 `_disable_comment_comparison()`。

- **实现绕了弯，值得记**：注释比对**不走 `include_object`** —— 那是对象级过滤器，
  对注释完全无效（先按 `include_object` 实现并**实测确认无效**后才改掉）。
  真正机制是 alembic 1.18+ 的 plugin（`autogenerate/compare/comments.py` 注册的
  comparator），最终做法是从 `alembic.runtime.plugins._all_plugins` 摘掉
  `alembic.autogenerate.comments`。
- **代价两条，已写进 env.py docstring**：① 注释漂移从此不可见；②
  `alembic revision --autogenerate` 生成的迁移不再带 COMMENT。
- `_all_plugins` 是私有 API → 已做存在性检查 + try/except，将来 alembic 改名则
  静默退回实施前状态，不会让 `alembic check` 崩掉。
- 效果：`alembic check` 输出从 ~200KB 降到 ~20KB。

## ✅ `alembic check` 43 条 → **0**（2026-10-07，`alembic check` exit 0）

> 本节保留为过程记录。当前 `uv run alembic check` 报
> **「No new upgrade operations detected」**（exit 0）。

原 43 条的构成与处置：

| op | 条数 | 处置 |
|---|---|---|
| `remove_constraint` | 39 | ORM `__table_args__` 补声明 —— **零迁移成本**，DB 侧本就正确（bug-147） |
| `add_constraint` | 1 | `compound_api521_thresholds` 改显式命名 UniqueConstraint |
| `add_fk` + `remove_fk` | 2 | `utility_energy_summary.workspace_id` ORM 改 `CASCADE` 对齐 DB（`fd0e8b9`） |
| `add_fk` | 1 | `fk_projects_workspace_id` 新迁移 `p7_s5_008` 补建（bug-146） |

补声明时确认的三件事（都记进 bug-147）：

1. **`alembic check` 的 `remove_constraint` 字面意思与正确处置恰好相反。**
   读作「DB 多余、ORM 要删」，实际是「DB 有安全网、ORM 漏声明」。
   照字面去删会把 DB 保护删掉。
2. **alembic 按名字匹配 CHECK，不比对表达式。** 实测：ORM 写可读表达式
   `cooling_water_consumption_t_yr IS NULL OR ... >= 0`，DB 是带 cast 的版本，
   名字对上就不报漂移。所以**可以写人话，不必抄 PG 的 cast 语法**。
3. **`unique=True, index=True` 并存时 SQLAlchemy 生成的是「唯一索引」而非
   UniqueConstraint**（`drain_orifice_Cd_Y_cr.fluid` 就是这样）——
   建表迁移这么写时 DB 上会出现「约束 + 唯一索引」两套，ORM 侧只留了后者。
4. **`compound_api521_thresholds` 的名字是被 `NAMING_CONVENTION` 展开错的**：
   `unique=True` → `uq_compound_api521_thresholds_threshold_type`，
   DB 里叫 `uq_compound_api521_thresholds_type`。名字对不上会**同时**产生
   一条 remove 和一条 add。改显式 `UniqueConstraint(..., name=...)`。

### 🟡 遗留：`drain_orifice_Cd_Y_cr` 上有**两个**功能重复的唯一索引

```
uq_drain_orifice_Cd_Y_cr_fluid  UNIQUE INDEX (fluid)   ← 约束自带的
ix_drain_orifice_Cd_Y_cr_fluid  UNIQUE INDEX (fluid)   ← 重复，白占写入开销
```

同列两个唯一索引，写入要维护两份。本轮只补了 ORM 声明让 `alembic check` 对齐，
**没动索引本身** —— 删索引是一条迁移。**Owner：待认领，优先级低。**

### ⚪ 另两个 alembic 事实（不是漂移，但会误导下一个人）

- **`alembic check` 检出漂移时退出码是 255**，不是 1。做闸门判断别按 `== 1` 写。
- **`use_alter=True` 不会自己生成迁移。** 它的语义是「由一条
  `ALTER TABLE ADD CONSTRAINT` 迁移单独创建」。ORM 里写了就必须有人补那条迁移，
  否则 DB 上根本没有这个约束 —— `projects` 表整整一张零外键就是这么来的
  （bug-146）。

<details><summary>原 43 条明细（已处理，留档）</summary>

| op | 条数 | 分布 |
|---|---|---|
| `remove_constraint` | 39 | **28 条 CheckConstraint + 11 条 UniqueConstraint**，均为 DB 有、ORM 未声明。Check 集中在 `utility_energy_summary`(8) / `utility_heat_exchange`(6) / `utility_fuel_gas`(5) / `util_results`(4) / `utility_power_items`(4)；Unique 分布在 `column_sizing` / `compound_*` / `cooling_tower_results` / `drain_orifice_Cd_Y_cr` / `flare_system_results` / `glycol_dehydration_full_system` / `mixer_results` / `pipe_e_modulus` / `psychro_results` / `user_projects` / `project_calculation_standard_profiles` |
| `add_constraint` | 1 | `uq_compound_api521_thresholds_threshold_type` —— ORM 声明了唯一约束，DB 没有 |
| `add_fk` + `remove_fk` | 2 | 同名 `fk_utility_energy_summary_workspace_id_workspaces`：**DB=CASCADE，ORM=RESTRICT**，两侧都声明且不一致 |
| `add_fk` | 1 | `fk_projects_workspace_id`（`use_alter=True` 延迟外键，通常是后续迁移才建的） |

- **`user_projects` 的 `uq_user_projects_user_project (user_id, project_id)`** 值得单独说：
  DB 有、ORM 无。`UserProjectService.grant_project_access` 用
  `scalar_one_or_none()` 依赖唯一性，DB 保证了它，但 ORM 侧无声明 → 换库/建表
  （单测的 SQLite `create_all`）就**没有**这唯一约束，单测里若有重复行测试会漏过。

</details>


| op | 条数 | 分布 |
|---|---|---|
| `remove_constraint` | 39 | **28 条 CheckConstraint + 11 条 UniqueConstraint**，均为 DB 有、ORM 未声明。Check 集中在 `utility_energy_summary`(8) / `utility_heat_exchange`(6) / `utility_fuel_gas`(5) / `util_results`(4) / `utility_power_items`(4)；Unique 分布在 `column_sizing` / `compound_*` / `cooling_tower_results` / `drain_orifice_Cd_Y_cr` / `flare_system_results` / `glycol_dehydration_full_system` / `mixer_results` / `pipe_e_modulus` / `psychro_results` / `user_projects` / `project_calculation_standard_profiles` |
| `add_constraint` | 1 | `uq_compound_api521_thresholds_threshold_type` —— ORM 声明了唯一约束，DB 没有 |
| `add_fk` + `remove_fk` | 2 | 同名 `fk_utility_energy_summary_workspace_id_workspaces`：**DB=CASCADE，ORM=RESTRICT**，两侧都声明且不一致 |
| `add_fk` | 1 | `fk_projects_workspace_id`（`use_alter=True` 延迟外键，通常是后续迁移才建的） |

- **`utility_*` 那 23 条 CHECK 值得优先看**：这些表是 P7 Sprint 5 期间新建的，
  CHECK 约束在建表迁移里写了、ORM 侧没同步声明 —— 与 bug-144 同类（**迁移对、ORM 漏**），
  但方向相反：DB 多了约束，**功能上更安全**，纯粹是 ORM 声明缺失。
  ⚠️ 补 ORM 声明前要逐条核对 CHECK 表达式与 DB 是否一致（autogenerate 只比名字，
  `ck_util_results_*` 这类同名不同义的情况它抓不到）。
- **`user_projects` 的 `uq_user_projects_user_project (user_id, project_id)`** 值得单独说：
  DB 有、ORM 无。`UserProjectService.grant_project_access` 用
  `scalar_one_or_none()` 依赖唯一性，DB 保证了它，但 ORM 侧无声明 → 换库/建表
  （单测的 SQLite `create_all`）就**没有**这唯一约束，单测里若有重复行测试会漏过。
- **Owner**：待认领。`utility_*` 那批可一次性补 ORM `__table_args__`（零迁移成本）；
  `ondelete` 那条必须先裁决 CASCADE / RESTRICT 哪个对（涉及删除项目时是否连带删
  能耗汇总记录，是业务语义问题）。
- **`alembic check` 检出漂移时退出码是 255**，不是 1。做闸门判断别按 `== 1` 写。

## ⚪ 本轮新发现的既有阻塞（非本轮引入，也非 P9 之外）

`grant_project_access` 目前在真库上**仍会失败** —— 现在报的是
`ForeignKeyViolation`（bug-144 修好后的正确行为），因为 `users` 与 `projects`
两张表都是 **0 行**：
- `users` 要等 P9 的 AD 同步（`P9-ADM-001`）才会有行；
- `projects` 需要正常业务使用才会产生。

即 **BLOCKER-3 的 IDOR 守卫在有真实数据之前无法端到端验证**。
这不是本轮能解决的，但**排 P7 收尾 / P9 联调时必须知道**。

## ✅ Postgres 版本已对齐 18（2026-10-07，用户裁决）

**起因**：`docker-compose.yml` 声明 `postgres:16-alpine`、CI 用 `postgres:16`，
而开发库实跑 **18.6** —— 本地 18.6 / CI 16 的隐性漂移。

**查清了「为什么两个都装」**（原先只登记为"不一致"，未查因）：
- **PG 16 是有意装的** —— `docs/adr/signatures/dba-btree-gist-install-request.md`
  （2026-09-16）明确「`btree_gist` 在 **PG 16 已 stable**」，确认件记录在 **5432**
  上给 `pcs` / `pcs_test` 装成 `btree_gist 1.7`
- **PG 18 无任何项目记录** —— `git log --all -i --grep` 搜不到；它的集群后来抢占
  5432（即 16 当时的端口），把 16 挤到 5433 且 `down`
- 证据表明项目数据已从 16 迁到 18 且**这次迁移无记录**：当前 `pcs` 103 张表、
  `btree_gist` **1.8**（DBA 在 16 上装的是 **1.7**）、`pcs`/`pcs_test` 两库都在

**裁决与落地**：
1. `docker-compose.yml` → `postgres:18-alpine`
2. CI `check-api-drift.yml` → `postgres:18`
3. `pcs_test` 补 `alembic upgrade head` —— 原停在 `p7_s4_001`（落后 3 个 revision、
   104 张表，多一张已被 `p7_s5_001` 删除的 `equipment_lib`），现已到 `p7_s5_007` / 103 张表
4. 根 `CLAUDE.md` 更正 —— 原文「当前无 `pcs_test`」是**错的**，且已补上版本与第二库的操作说明

**仍待办 / 已知残留**：
- ⚠️ **本机 PG 16 集群仍在**（`16-main`，5433，`down`）。它是旧集群，与开发库无关，
  但机器上两个版本并存这件事本身有再次踩坑的风险。是否清理由用户定。
- ⚠️ `REFERENCES users.user_id` → `InvalidSchemaName` 那个坑**仍未在 16 上验证**
  （起 16 需 root、docker 拉镜像网络超时）。**修复本身不依赖它** —— 走
  `op.create_foreign_key`，生成标准函数式 `REFERENCES users (user_id)`。
  版本敏感的只有文档里那句断言，已标注「跨版本未验」。
- 早先 bug-143 / bug-144 的修复是在 18.6 上验的；CI 此前用 16 跑绿过整条迁移链，
  本次改动后 CI 首次以 18 跑 —— 结果待观察。


## ✅ `ondelete` CASCADE/RESTRICT 争议已裁决（2026-10-07，用户裁决）

争议：`fk_utility_energy_summary_workspace_id_workspaces` —— DB=CASCADE，ORM=RESTRICT。

**裁决：ORM 改 CASCADE 对齐 DB**（ORM-only 改动，零迁移成本，DB 本来就是这个行为）。

**理由**（用户给出，核实后成立）：
- workspace 是数据容器，汇总记录的存在依赖它 → 级联删除是合理的容器语义
- workspace 删除走的是 **硬删除**（`workspace_service.py:162` 的 `delete(Workspace)`），
  不是软删 → FK 约束**确实会触发**，RESTRICT 不是等价选项
- RESTRICT 会让 workspace 自动清理任务在遇到能耗数据时失败 —— 那不是预期行为
- 若业务上需要「删正式 workspace 前先确认数据已导出」，应在 **service 层**做显式检查，
  **FK 是数据完整性约束，不是业务规则**

已改：`app/models/util.py` 的 `UtilityEnergySummary.workspace_id`
`ondelete="RESTRICT"` → `"CASCADE"`，并在 comment 里写明「工作区删除时汇总跟随删除 ——
如需保留数据请走归档而非删除」。

⚠️ 注意 `util.py` 里有 **6 处**长得完全一样的 workspace_id RESTRICT 声明，
但只有这一处在漂移（其余 5 处 DB 也是 RESTRICT）—— 改的时候不能 `replace_all`。

**效果**：`alembic check` 从 43 降到 **41**（`add_fk` + `remove_fk` 两项同时消失）。

---

## 🔴 P9A 前置：`create_change_notice` 不可用（2026-10-07 复核 bug-145）

**归属已由 SPEC 确认，不是我推断** —— `P9 SPEC V1.3` 任务表：

| 任务 | 内容 | 现状 |
|---|---|---|
| `P9A-DLV-007` | **SignatureMatrixService**：`steps_json` 消费方，矩阵步骤推进、角色判定、动态列数 | SUP-005，**未落地** |

P9 SPEC 的 R1 备注也印证了现状：「V1.3 假设『后端已由 P1 交付』，
**实测 Deliverable/SignatureMatrix 无 service、无 API、无路由**」。
（该备注现已部分过期 —— `deliverable_service.py` 补了 Deliverable 读面，
SignatureMatrix 仍空。）

### 事实

- `Deliverable.matrix_id` 是 **NOT NULL + FK**（真库 `is_nullable=NO` 确认），
  而 `create_change_notice` 写死 `matrix_id=None` → 真库上必 500。
- `signature_matrices` 真库 **0 行**；全仓无任何 service / API / seed 创建矩阵。
- `ChangeNoticeService` **无任何 API 路由调用** —— 是**未接线的死路径**，
  不是线上 500。严重性比 bug-145 原记录低。

### 本次已做（2026-10-07）

不是修功能（功能归 P9A-DLV-007），是**把哑雷变成显式路障**：

- `create_change_notice` 开头 `raise NotImplementedError`，消息指明堵点
  （矩阵 NOT NULL + `P9A-DLV-007`）。下方实现原样保留标注为 P9A 参照。
- 5 个 happy-path 测试改为断言「拒绝」，并加两条关键断言：
  **拒绝前 `db.added` 为空、`db.commits == 0`**；**不产生 CHANGE_NOTICE_CREATED 审计**。
- 原 422 / 404 校验经 stub 已不可达 → 改为直接测 `_check_record_charged`，
  让 P9A 继承这份覆盖。
- 清掉两处**悬空的 `SIM-39` 引用**（矩阵、doc_no）。该编号在仓库里被复用了
  **至少 4 次**（不可靠流守卫 / 记录弃用 / 状态机审计 / 这两处），
  指着一个已关闭且不同范围的任务。

### P9A 落地时要一起做的三件小事

1. 解析 `CHANGE_NOTICE_3_LEVEL` 矩阵写入 `matrix_id`（SPEC 增补 §P2
   要求模板库含此矩阵；`PCS-DICT-005` 已给出 `steps_json` 的 seed 形态）。
2. `doc_no` 接编号模板（现为 `CN-{record_id 前 8 位}` 的简化写法）。
3. 把 `test_create_change_notice_writes_no_audit` 改回「写了」，
   断言 `CHANGE_NOTICE_CREATED` / `resource_type=DELIVERABLE`。

### 选型记录

**为什么显式拒绝，而不是把 `matrix_id` 放宽为可空**：SPEC 的设计意图是
「没有矩阵就无法签署」，放宽等于把设计约束降级成软约束；且 P9A 反正要落这个
消费方，放宽的收益是零。

**为什么原记录说「无任何测试」是错的**：判「有没有测试」不能只 `ls tests/` 顶层，
`tests/services/` 子目录里有 5 个。真正的坑更深 —— 那些测试用假 DB，
结构上观察不到 DB 层约束。已写进 `.wolf/cerebrum.md` Do-Not-Repeat。

## 🟡 antd Table `rowKey` 回调的 `index` 参数已弃用（2026-10-08 QA 巡检发现）

控制台：`[antd: Table] 'index' parameter of 'rowKey' function is deprecated.`

antd v6 会移除 `rowKey(value, index)` 的第二个参数。当前写法依赖 index 做行 key
的，升级后会静默错乱 —— 属「现在不影响功能、升级才炸」的一类。
**Owner：待认领。** 修法：改成只取 `value` 上的稳定唯一字段。

---

## 🔴 P8 落地遗留（2026-10-12 登记，T1–T5b 收口时）

> 这四条是 P8 Task 1–5b 执行过程中**新发现**的，不是历史积压。
> 全部有代码依据，见每条「证据」。

### ~~TODO-045: 部署镜像需显式跑一次 `build_report_font.py`~~ ✅ 2026-10-13 修完（用户裁决：加部署自检脚本）

新增 `scripts/check_report_font.py`（4 条测试）：复用
`renderer_pdf._register_font` —— **生产真正走的那条路**，不是抄一份检查逻辑
等它漂移。全链落空/全链被否 → 退出 1 + 每个候选被否的原因 + 修法；
就绪 → 退出 0 + 报出实际选中的路径。

⚠️ **原文里「Dockerfile 里 `apt install fonts-noto-cjk`」这条建议是错的**，
已用测试钉住（`test_a_present_but_unreadable_font_is_rejected_not_swallowed`）：
fonts-noto-cjk 装出 `.ttc` + CFF 轮廓，reportlab 直接抛
`TTFError: postscript outlines are not supported`。装了它自检照样红 ——
这正是自检存在的意义。

**部署清单**（后端尚无 Dockerfile，此清单挂到建镜像那天）：
1. 镜像里投放 OFL 的 NotoSansSC-VF.ttf（源），构建时跑
   `uv run python scripts/build_report_font.py`；或直接投放派生产物
2. 上线前跑 `uv run python scripts/check_report_font.py`（退出码即结论）

- **Owner**: 已完成

### ~~TODO-046: CI 未装 poppler-utils，`@pytest.mark.visual` 测试会 fail~~ ✅ 2026-10-13 修完（用户裁决：加进现有 workflow）

`check-api-drift.yml` 新增步骤 `Visual renderer tests`：

1. `apt-get install poppler-utils`（缺它这些测试 fail-not-skip，2026-10-09 裁决）
2. 从 noto-cjk 上游拉 **可变** TTF 到派生脚本的默认搜索路径 ——
   Ubuntu 仓库没有任何包提供它（fonts-noto-cjk 是 .ttc+CFF，reportlab 读不了）。
   上游路径已用 blob:none clone + `git ls-tree` 逐一核实存在
3. 下载后用 fontTools 自检 `fvar` 存在 —— 上游若改成 LFS 指针/404 HTML，
   以清晰信息立刻失败，不等 conftest 长堆栈
4. `uv run pytest -m visual tests/services/report/test_renderer_visual.py`
   —— CLI `-m visual` 覆盖 pyproject addopts 的 `-m 'not visual'`（实测 4 passed）

本地已验证：YAML 可解析、同款 pytest 命令 0.37s 全绿、自检片段可跑。
GitHub Actions 侧无法本地预跑，首次 push 后看一次实际运行。

- **Owner**: 已完成

### ⚪ TODO-047: ADR-P8-004 报表任务队列与文件生命周期 —— 等运维

- **症状**: T7（ARQ 任务）依赖队列隔离策略与文件保留期。
- **证据**: `docs/adr/ADR-P8-004：报表任务队列与文件生命周期.md`（含 3 个队列选项、
  4 个保留期选项、运维需提供的输入）。
- **当前临时状态**: 同队列、`max_jobs` 保持 4、文件**永不删除**。
  按此实现 T7 不会返工，但保留期一旦定下来要补清理任务。
- **Owner**: 运维（**用户已确认这是外部依赖，不阻塞 T4/T5/T6**）

### ~~TODO-048: 变异测试工具链无法区分「变异没应用」与「测试没抓到」~~ ✅ 2026-10-13 修完

`tests/mutation.py` 新增 `expect_killed(...)`，把**三类**失败都变成硬失败：

| 失败 | 谁拦 |
|---|---|
| 变异没应用（空操作）| `mutate` 的 `assert old in source` |
| 变异应用了但**测试没抓到** | `expect_killed` 第 3 步 |
| 测试**本来就红**（基线不绿）| `expect_killed` 第 1 步 |

第三条最容易漏：一个**恒红的测试**能「杀掉」任何变异，于是「100% 变异被
杀死」全是假的。所以施加变异**之前**先跑基线，基线红就报错。

⚠️ **配套的 `assert_restored` 第一版拿 `git diff` 当基线，是错的**：
变异测试是在有正常工作改动的工作区里做的，那些改动本身就在 diff 里。
实测踩过 —— 文件明明已正确还原，检查却红了。基线必须是**进入时读到的内容**
（`snapshot()`）。

**工具自身 13 条测试**，并**在真代码上验证有效**：去掉
`definition_service.update()` 里的 `await db.refresh(row)` →
`expect_killed` 抓到，文件还原到变异前内容。

- **Owner**: 已完成

### ~~TODO-049: 生产 session 未设 `expire_on_flush=False`~~ ✅ 2026-10-13 结案

**⚠️ 结论与原提案相反：修法 1 不成立，已撤回。**

原提的两个候选里，「在生产 factory 加 `expire_on_flush=False`」是**无效**的。
2026-10-13 实测：

```
expire_on_flush = False
expired after flush: ['updated_at']          ← 照样 expired
read updated_at FAIL -> MissingGreenlet
```

`onupdate=func.now()` 这类列的值是**SQL 表达式在数据库里算出来的**，
SQLAlchemy 无从知道结果，所以 flush 后**必定**标记 expired。
`expire_on_flush` 只管「本来已加载的属性」，管不了服务端表达式列。

（实现上也踩了一层：`expire_on_flush` **不是** `async_sessionmaker` 的
参数，`Session.__init__` 不收它。最初的断言查 `factory.kw["expire_on_flush"]`
得到 KeyError，看着像「配置不对」，其实是「断言查了不存在的键」。）

**真正的修法是候选 2**：service 返回 ORM 行前显式 `await db.refresh(row)`。
`definition_service` 的 update/publish/obsolete 早已这么做 —— 本轮做的是
**把它钉住**，并把「别去加 expire_on_flush」的实测结论写成测试：

`tests/db/test_server_generated_columns.py`
- `test_expire_on_flush_false_does_not_help_server_generated_columns`
  —— 钉住「加了也没用」，防止下一个人再走一遍这条弯路
- `test_refresh_makes_the_column_readable` —— refresh 确实让它可读
- `test_definition_service_update_does_not_trip_missinggreenlet`
  —— 端到端后果（变异验证：注释掉 `refresh` → 转红）

**仍未强制的部分**：规则本身（返回含服务端生成列的 ORM 行前必须 refresh）
**靠人工遵守**，没有架构级检查。新增 service 时仍可能忘 —— 这条残余风险
已如实记录，不假装解决了。

- **Owner**: 已结案（含残余风险记录）

### ~~TODO-050: 管道后报告命令退出码 = 报的是最后一个命令的~~ ✅ 2026-10-13 修完

`cmd | tail -10; echo "EXIT=$?"` 里的 `$?` 是 **`tail` 的**退出码。
实测已因此至少两次把红的守门报成绿的（`check_openapi_payload_coverage`
裸字段 71→73；`alembic check` 的 255）。

**修法**：新增 `scripts/run_gate.py`（7 条测试）——

```bash
uv run python scripts/run_gate.py --tail 10 -- <要跑的命令>
# 打印最后 N 行 + "EXIT=<该命令自己的码>"，并以同一个码退出
```

⚠️ **不要**把它的输出再接管道然后 `$?` —— 那就回到原问题。

规则同时进了 `.wolf/cerebrum.md` 的 Do-Not-Repeat，并列出四种同类陷阱
（`| tail` / `| head` / `a && b` / 函数内失败）。

- **Owner**: 已完成

### ~~TODO-051: P8b 前端 b10–b12 需重新评估迁移口径~~ ✅ 2026-10-13 关闭

- **原症状**: 计划写 b10–b12（定义编辑器 / 执行面板 / 管理列表），
  并注明前置「TODO-039/041 的 7 个 mock type 文件改 import 自 ./api」，
  但同一段又自陈该前提**不成立**（28/31 interface 在 OpenAPI 无对应 schema）。
- **本轮核实结论：这个阻塞对 b10–b12 根本不成立**：
  - 那 7 个 mock type 文件（pipeClass/flash/pipe/pump/pipeNet/pms/common）
    **只被 P7 页面与 MSW seed 消费，零个 report builder 消费者**；
  - P8 自己的 **19 个 schema 在 `api.d.ts` 里全部有类型**，裸
    object/array 计 0。
  所以计划里那条前置是**自陈失效的前提**，直接开工即可。
- **旧 7 个文件的处置**：**维持现状，不动**。它们是 §3.4 约束①
  （载荷模型）的下游债，改它们要先把后端载荷定义补齐 —— 那是 P7 的账，
  与 P8 无关。TODO-039/041 的重定范围结论仍然有效。
- **交付**：b12 列表 / b10 编辑器 / b11 执行面板 / c6 样式页四屏，
  类型全部来自 `./api`。分两批（用户 2026-10-13 裁决），详见下方新条目。
- **Owner**: 已完成

#### 附：QA 挖出的三个真缺陷（都已修，详见 QA 报告）

1. **HIGH** 四屏在 dev 里**打不开**（进页面即被弹回登录）。根因是 dev
   登录走 MSW 的 `mock-login`，返回**假 token**，而页面用真 client →
   401 → 拦截器清会话。单测查不出（不经过 MSW 登录链路）。
   已补 `src/mocks/reportBuilder.ts`（与 `heat.ts` 同形态）。
2. **MEDIUM** antd `rowKey` 用数组下标 → 上下移动行时「显示名」串行。
3. **LOW** `asSingleFilter` 遇 AND/OR 分组返回 `null` → 编辑器显示
   「无过滤」而保存会抹掉它。**已知数据丢失**，见 TODO-060。

### ~~TODO-052: 「非发布件」水印是文字横幅，不是视觉水印~~ ✅ 2026-10-13 用户确认关闭

用户裁决：**文字横幅够用，维持现状**。理由在案 —— xlsx 没有图层概念
画不了半透明斜排，文字横幅是三种格式（PDF/XLSX/DOCX/CSV）唯一一致
可验的形式；验收口径「可见 = 可被抽出/读到的文字」（pypdf 抽文本 /
CSV 断言首行）不变。

若未来产品改主意：PDF 可用 reportlab canvas、DOCX 可用页眉水印，
xlsx 仍是死路 —— 届时需要先裁决「xlsx 怎么办」，本条重开。

- **Owner**: 已关闭（用户确认）

### ~~TODO-053: CSV 首行 `#` 注释会让 Excel 双击报「格式不符」~~ ✅ 2026-10-13 用户确认关闭

用户裁决：**维持现状**。CSV 定位是「给脚本再处理」，水印是语义声明
（这份没签署）不能去；要双击看请导 xlsx。原取舍（2026-10-09）成立，
不改成水印列 —— 那会让脚本把水印当数据列，与 CSV 的定位相抵触。

- **Owner**: 已关闭（用户确认）

### TODO-055: c4/c5 缺 HTRI/TEMA 参考文件

- **症状**: P8c 的 c4（HTRI 兼容测试，`121-A-101.xls` 33 列 +
  `131-E-102-EOR.xls` 23 列 覆盖比对）与 c5（DETAIL 覆盖率 ≥95%）
  都需要这两份 HTRI/TEMA 输出作为基准。**仓库里没有**（`sample/` 下只有
  `1216D132…xlsx` / `dmc.out` / `huafeng140_FCC2015.out` 等，
  不是这两个 Xace/Xist 表）。
- **本轮已交付的部分**: c5 的**工具**已建好并用合成基准验过 ——
  `scripts/report_heat_coverage.py`（退出码：0 达标 / 1 未达标 /
  **2 缺输入**；缺输入绝不算「0% 通过」）。
- **还缺什么**: 把两份 .xls 放进 `sample/`（不入 git，与既有 sample 一致），
  然后 `uv run python scripts/report_heat_coverage.py sample/121-A-101.xls \
  sample/131-E-102-EOR.xls`。
- **合成基准的试跑结果**（27 列的假 HTRI 表）: 覆盖率 88.9%，3 个服务不了的
  列恰好是已知的数据模型缺口 —— `Service` / `Air Flow Rate` / `Fin Height`，
  与 c1 登记的 `ADR_FIELDS_WITHOUT_COLUMN` 一致。**这不能替代真实比对**：
  真实模板的列名与列数未知，`COLUMN_MAP` 必然要按真实文件补。
- **已解除（2026-10-12）**: 文件已到位（`sample/A-101.xls` + `sample/131-E-102-EOR.xls`，
  注意第二个计划里写的是 `121-A-101.xls`，实际叫 `A-101.xls`）。c4/c5 的工具
  已能在真实文件上跑通并出数。

- **优先级**: —
- **Owner**: —（见下 TODO-056 / TODO-057）


### TODO-056: ACHE 翅片几何字段在数据模型里缺失（真实 HTRI 文件证实）

- **症状**: `sample/A-101.xls`（HTRI Xace 空冷器）里有 9 个翅片/空气侧
  字段，`heat_results.ache_params` 一个都没有：
  `Air humidity` / `Fin height` / `Fin thickness at base` /
  `Fin root diameter` / `Fins per unit length` / `Fin efficiency` /
  `Over fin diameter` / `Unfinned length` / `Unheated length`。
- **为什么没登记**: `AcheParams` dataclass 里**没有这些字段**，写入方
  （`save_ache_params`）也从不写它们。登记进注册表 = 字段树里选得到、
  执行时查出全 NULL —— 与 c1 里刻意不登记的其他缺口同一性质。
- **处置顺序（缺一不可）**:
  1. `AcheParams` 加字段 + 找到/写入方（`heat_data_service` 的哪个入口能拿到）
  2. 注册表登记（`_jfx(..., "AIR_COOLER")`）
  3. `scripts/report_heat_coverage.py` 的 `COLUMN_MAP` 加映射
  跳过 2 直接做 3 = 覆盖率替不存在的字段记功（已有测试
  `test_map_targets_must_exist_in_registry` 挡着）。
- **优先级**: TODO 级。这是 DETAIL 覆盖率未达标的主因之一。
- **Owner**: 工艺 + 数据

#### 2026-10-13 收口：9 条全部落地

两批共 **9 个** ACHE 字段（不是 9 个标签对 9 个列，见下表）已贯通
**解析 → `AcheParams` → `_ache_with_geometry` 写入 → 注册表 → `COLUMN_MAP`**：

| 批次 | 字段 |
|---|---|
| 第一批 | `fin_height_mm` / `fin_thickness_mm` / `fin_root_diameter_mm` / `over_fin_diameter_mm` / `tip_clearance_mm` |
| 第二批 | `air_humidity_percent` / `fin_density_per_m` / `fin_efficiency_percent` / `unfinned_length_mm` / `unheated_length_mm` |

**真实值**（`A-101.xls` `2 - Final Results` 实测）：

| 字段 | 实测 | 备注 |
|---|---|---|
| `fin_density_per_m` | 433.1 | |
| `fin_efficiency_percent` | 80.0 | |
| `unheated_length_mm` | 127.000 | |
| `unfinned_length_mm` | **0.000** | 整段都有翅片 —— **0 是合法值**，见 bug-161 |
| `air_humidity_percent` | **无值** | r13 只有标签 col16 与单位 col20，中间空。`None` 是正确结果 |
| `tip_clearance_mm` | 9.525 | 第一批登记了却恒为 `None`（只读了一侧）—— c1「登记了不等于有数据」的又一个实例 |

⚠️ **`Air humidity` 仍登记**：HTRI 在别的工况下会输出它，且它确实是设计
输入。登记了才谈得上「某次导入没取到」；不登记则是字段树上选都选不到。

⚠️ **注册口径覆盖率从 60.2% 掉到 57.4%**（62/103 → 62/108）：**分子没动、
分母 +5**。这 5 个标签都在 `2 - Final Results`，而主表口径只读
`2 - Output Summary`，于是进分母、进不了分子。已按工具既定流程**重测基线**
（不是猜的），并在常量处写明原因与查看口径（`--sheet "2 - Final Results"`
下是 49/108）。模板口径不变（79.7%）。

**顺带清掉一处死常量**：`KNOWN_ACHE_GEOMETRY_GAPS` 列的正是这 5 个标签，
但它**定义了却全项目零引用** —— 看上去在守护「刻意不映射」，实际没人读它，
这些标签照常落进 `unmapped_labels`。已删除并把 5 条转正进 `COLUMN_MAP`。


### TODO-057: 「DETAIL 覆盖率 ≥95%」的分母口径需拍板

- **症状**: 计划只写「≥95%」，没写分母是**模板字段数**还是**我们已登记
  字段数**。两个口径在同一份真实文件上差了 **32.1% vs 61.4%**。
- **本轮实测**（`sample/A-101.xls` + `sample/131-E-102-EOR.xls`，
  159 个提取标签 / 83 个已登记 DETAIL 字段）:
  | 口径 | 数值 |
  |---|---|
  | 模板口径（认得几项）| **52.8%**（84/159 条标签）|
  | 注册口径（覆盖几项）| **61.4%**（51/83 个字段）|

  分 sheet 看（`A-101.xls` 4 个 sheet）：`Output Summary` 50 标签、
  `Final Results` 95 标签，另两个 sheet 布局不同提不到标签
  （提取规则的已知偏差，不是「那两个 sheet 没字段」）。
- **⚠️ 与计划数字对不上**: 计划写「33 列 / 23 列」，而提取到 159 个标签。
  差 ~5 倍。最可能是计划数的是**主表字段数**（如 Xace 的 `Output Summary`
  单表），而我按「全部工作表的所有带单位标签」提取。若按主表口径，
  数值会高很多 —— **但我没有按那个口径出数**，因为无从确认计划的取数范围。
- **已裁决（2026-12-12）**: 分母取**模板主表口径**（`--scope main`，默认）。
  实现按「第一个提取到标签的 sheet」选主表，并同时打印各 sheet 的标签数 ——
  口径的敏感度必须可见，静默换分母是这类指标最容易被忽略的作弊。
- **随后用户裁决放弃 95% 目标本身**（见 ADR-0028 修订记录）：改为记录基线
  （模板 64.9% / 注册 53.0%）+ 2pp 回归容差，**防回归不追覆盖率**。
- **优先级**: —（已关闭）
- **Owner**: —

### TODO-058: HEAT 主表 11 条缺口的分类 —— **3 条已裁决落地，其余待定**

#### ✅ 已落地（用户 2026-12-12 裁决「壁温进规格书、两相含量要显示、管排数空冷器专属」）

| 裁决 | 落地 | 迁移 |
|---|---|---|
| 壁温进规格书 | `skin_temp_min` / `skin_temp_max`（管程侧，°C） | p8_003 |
| 两相含量要显示 | `shell_params`/`tube_params` 各 4 个 wt% 键（气/液 × 进出口） | 无（JSONB 词汇表）|
| 管排数空冷器专属 | `tube_rows`（INTEGER，`exchanger_type=AIR_COOLER`） | p8_003 |
| 附带（TODO-056 第一批）| `ache_params` 加 5 个翅片/风机几何键 | 无（dataclass）|

覆盖率 64.9% → **74.3%**，缺口 11 → 5。

⚠️ **三列目前只有手工录入（`HeatCalcInput`）能填**：`htri_parser` 只提
16 个字段，导入的行这几列是 NULL。这是**已文档化的诚实缺口**，不是缺陷
藏起来 —— 测试钉住了，解析器补上时会被迫同步更新。补解析见 TODO-056。

⚠️ **两个写入方的键集必须逐字相同**（bug-160 的教训）：侧物性的键集
收敛到 `SIDE_PARAM_KEYS` 常量、`AcheParams` 用 `dataclasses.fields()`
自检，两侧键集不等时**当场断言失败**。

#### 仍未裁决的 5 条

`Area ratio (fin/bare)`、`Area ratio(out/in)`、`Heat transfer safety factor`、
`Ratio, Fan/bundle face area`，以及 `tube_rows` 之外的 `Number of rows` 同族。
前两条是**派生量**（可由已有面积算出，也可只做计算列不存库）；
后两条原判为 B 类「HTRI 专有诊断输出，客户不需要」—— 需确认。

#### 已关闭部分

用户 2026-12-12 裁决：分母取**模板主表口径**（`--scope main`，默认）。
实测 `sample/A-101.xls`（取 `2 - Output Summary`，50 标签）+
`sample/131-E-102-EOR.xls`（取 `1 - Rating Data Sheet`，25 标签）：

| 口径 | 数值 |
|---|---|
| 模板口径（认得几项）| **64.9%**（48/74 条标签）|
| 注册口径（覆盖几项）| 53.0%（44/83 个字段）|
| 目标 | ≥95% |

分母 74 条标签中 **11 条服务不了**。逐条分类如下（A/B/C 三类）：

#### A. 数据模型缺口 —— 可补，需加列 + 写入方（6 条）

| 标签 | 说明 | 建议落点 |
|---|---|---|
| `Skin temperature, Min/Max` | 管壁温度（表面温度）min/max | `heat_results` 新增 2 列；壁温是热工校核的常规量 |
| `Tip clearance` | 风机叶尖与筒壁间隙 | `ache_params`（空冷器几何） |
| `Fin root` / `Over fin` | 翅片根径 / 翅片外径 | `ache_params`（与 TODO-056 同批补） |
| `Number of rows` | 管排数 | `heat_results` 新增列（现只有 `tube_passes`） |
| `Area ratio (fin/bare)` / `Area ratio(out/in)` | 翅片面积比 / 内外面积比 | 派生量，可由已有面积算出 —— 也可只做**计算列**不存库 |

#### B. 明确不做 —— HTRI 专有诊断输出，客户规格书不需要（3 条）

| 标签 | 为什么不做 |
|---|---|
| `Heat transfer safety factor` | HTRI 内部校核裕度因子，非交付字段 |
| `Ratio, Fan/bundle face area` | 风机几何校核比 |
| `Vapor (In/Out)` / `Liquid` | 与 `Vapor (In/Out)` 成对的两相含量 —— **除非规格书要显示两相工况**，否则属诊断 |

⚠️ B 类的判断是**我的工程判断，不是工艺裁决**。若工艺要这些字段，
它们就从 B 移到 A（`Skin temperature` 同理）。

#### C. 需业务裁决（2 条 + 1 组）

1. **`Skin temperature, Min/Max`** —— 我放在 A（建议补），但管壁温度在
   壳程/管程规格书里是否必需，是工艺口径。若必需必须补列。
2. **两相工况显示**（`Vapor (In/Out)` + `Liquid`）—— 规格书要不要显示
   两相含量百分比？`streams` 里有相态，但换热器结果表里没有含量字段。
3. **`Number of rows`（管排数）** —— 空冷器管排数是选型关键参数，
   管壳式不适用。是「空冷器专属」还是通用？

#### 补完后的预估

A 类全补 → 48+6 = 54/74 = **73.0%**；B 类确认不做 → 仍 73.0%。
**达不到 95%。** 缺口的主要来源不是这 11 条，而是**分母口径本身**：
74 条主表标签里有相当一部分（壁温、两相含量、面积比、风机几何）
根本不属于「规格书字段」的范畴。

→ **用户 2026-12-12 裁决放弃 95% 目标**（见 ADR-0028 修订记录）。
覆盖率不再作为验收线，改为**回归闸**：实测基线 64.9%，各留 2pp 容差，
跌超容差才报。涨随便涨。

⚠️ 工具里**没有**把目标改成 0 —— 那会让覆盖率工具恒绿，比没有工具更坏。

**本 TODO 的 A/B/C 分类本身仍然有效**（分类是工程判断，与目标无关），
但已不再是「为达 95% 而补」的清单，而是「要不要做这些字段」的参考。
- **优先级**: TODO 级（降级：不再是达标路径）
- **Owner**: 工艺（C 类的三条需业务裁决）

### TODO-059: HTRI 真实报表是 Excel 版，parser 读的是纯文本（已澄清并处理）

- **2026-10-13 用户澄清**: `sample/A-101.xls` 就是 HTRI 文件的 Excel 版。
  **真实样本一直都在** —— 原记录里「缺样本」的判断是错的，真实问题是
  **`htri_parser` 读错了格式**。

- **原判断为什么错**: `sample/*.out` 是 HTRI **输入卡**
  （`OPER DUTY=0.18`），不是输出报表。`htri_parser` 解析的是
  `Key: value` 纯文本格式 —— 而那个格式只存在于
  `tests/services/heat/fixtures/*.txt` 里**手写的合成 fixture**。
  于是「4 个真实文件全解析失败」被误读成「没有真实样本」。

- **本轮已做**: 新增 `app/services/heat/htri_excel_parser.py`，
  直接解析两份真实报表，产出**同一个 `HtriParsedData`**，
  落库链路（`map_htri_to_heat_input`）完全共用 —— 不另起写入路径。
  9 条测试全部对着真实文件跑。

- **真实报表有五种写法，全都要覆盖**（都是实测踩出来的）:
  | 写法 | 例 |
  |---|---|
  | 1 标签\|单位\|值 | `Total flow rate \| (kg/s) \| 17.797`（Xace）|
  | 2 标签\|值\|单位 | `Heat Exchanged \| 44711. \| kW`（TEMA）|
  | 3 值+单位在**下一格** | `Shell ID \| 1600.00  mm`（TEMA）|
  | 4 值+单位**同格**（标签另起） | `Surf/Unit (Gross/Eff) 1945.40 / 1862.49 m2` |
  | 5 值+单位同格（同一格） | `Cross Baffle Type PERPEND. SINGLE-SEG. \| %Cut (Diam) 25.0` |

- **两个静默出错点（都有测试）**:
  1. **侧分界不能用表头位置**：Xace 表头 `Outside`@7 / `Tubeside`@15，
     但**值**在 6/10 与 14/16 —— 表头是合并单元格的居中位置。取第二个
     表头当分界会把管程进口 131.79°C 归进空气侧（该侧只有 32.00°C），
     **差 4 倍且不报错**。正确做法：取两个表头位置的**中点**。
  2. **功率换算不能用数值大小猜**：`Heat Exchanged 44711 kW` 与 W 单位的
     44711 从数字上无法区分。猜错 = 1000 倍误差。

- **仍未做**: `htri_parser`（纯文本那条路径）**仍然读不了真实文件**，
  保留是因为它在测 fixture 下工作正常，且 `htri_excel_parser` 的字段
  口径要对齐它（单位：Excel 用 °C/mm，纯文本用 K/m）。
  两条路径的字段命名已统一到 `HtriParsedData` 上。

- **优先级**: 已处理。后续若拿到 HTRI **纯文本**输出报表，
  再把 `htri_parser` 补上；在此之前以 Excel 路径为准。
- **Owner**: —

### TODO-058 收口：主表缺口已清零

2026-10-13 实测：模板口径 **79.7%**（59/74）、注册口径 **60.2%**（62/103），
**未覆盖标签 0 条**（此前 11 → 4 → 0）。

剩余差额全部来自**提取噪声 15 条**（`In` / `Outlet` / `Midpoint` 等列头
被当成字段标签），不是我们缺字段。要不要把噪声从分母里剔掉是口径问题，
未裁决 —— 剔除后分母降到 59，模板口径即 100%。

新增字段全部经 `htri_parser` → `map_htri_to_heat_input` → DB 端到端验证
（`test_htri_parser_new_fields.py`，含一条「解析了不等于落库了」的
反向测试）。

### TODO-059 补记：Excel 解析器已接入导入端点

`POST /api/v1/heat/import-htri` 现按**上传文件名后缀**分派
（`.xls/.xlt/.xlsx/.xlsm` → `parse_htri_excel`，其余 → `parse_htri`）。

⚠️ 临时文件**必须沿用后缀** —— 原实现固定 `.txt`，Excel 报表被存成
`.tmp.txt` 后走文本 parser，报「首行无法判别版本」，把用户指向
**版本**问题，而真实原因是「这是 Excel」。错误信息指错方向比不报更难查。

**两条 parser 的单位口径不同**，在 `map_htri_to_heat_input` 收敛
（Excel 优先，回退纯文本）：

| 量 | 纯文本 | Excel | 取法 |
|---|---|---|---|
| 壳体直径 | `shell_dia_m`（m）| `shell_id_mm`（mm）| Excel 优先，回退 m×1000 |
| 挡板间距 | `baffle_spacing_m`（m）| `baffle_spacing_mm`（mm）| 同上 |
| 温度 | `*_t_k`（**K**）| `*_t_c`（**°C**）| Excel 优先，回退 K−273.15 |

⚠️ 只读其中一套的话，另一套 parser 导入的数据会**整列为空**，而导入
照样返回 201。


### ~~TODO-060: 编辑器遇到 AND/OR 分组会**抹掉**已有过滤条件~~ ✅ 2026-10-13 修完

**修法**：编辑态从「至多一条 EQ」改为**递归的 `FilterTreeEditor`**，
`toFilterTree` / `fromFilterTree` 严格互逆，往返无损。

⚠️ 顺带发现并修掉一批里我自己埋的**死代码**：`asSingleFilter` 的组检测
查 `children`，而那个键后端**从不产生**（组判据是「有没有 `conditions` 键」，
见 `query_engine._build_condition` 注释）。所以返回 null 靠的是后面
「没有 field 字段」的检查 —— 结果照样丢数据，**但理由是错的**：换个键名
就会静默变成「当成叶子条件」。

**验证**：变异测试（`fromFilterTree` 退回只发单条 → 3 条往返断言转红）
+ **真后端端到端 10/10**（两层嵌套 + BETWEEN list + IS_NULL null 逐字往返，
且「只改别的字段的别名」保存后组仍在）。

<details><summary>原始描述（已解决，保留）</summary>

### 原始：编辑器遇到 AND/OR 分组会**抹掉**已有过滤条件（数据丢失）

- **症状**：`definitionBody.ts` 的 `asSingleFilter()` 只认**叶子条件**，
  遇到 `{logic:'AND', children:[...]}` 一律返回 `null`。后果：
  打开一份含条件组的定义 → 页面显示「无过滤条件」→ **点保存就把
  条件组整段抹掉**。
- **为什么第一批就这么做**：b10 第一批只做 EQ 单条（用户 2026-10-13
  裁决的分批）。返回 `null` 而不是「显示一条假的」是刻意的 ——
  显示假条件会让用户以为过滤还在，而抹掉至少会在保存后的报表里
  **看得见**（行数突然变多）。但它仍然是数据丢失。
- **临时缓解**：代码注释里写明「此页面暂不可用于编辑含分组的
  旧定义」。**这只是文档，不是防护** —— 页面上没有任何提示。
- **正确修法**（第二批第一项）：
  1. `asSingleFilter` 改为返回「叶子条件 **或** 分组」的判别联合；
  2. 页面遇到分组时**禁用保存**并显示「本定义含 AND/OR 条件组，
     第一批编辑器不支持，请用第二批或直接改定义」；
  3. 更彻底的做法：`buildBody` 保留**未被编辑的**原有条件组
     （原样回写），而不是丢弃。
- **优先级**：**MEDIUM（不是 LOW）** —— 它会丢数据。QA 报告里我按
  「展示层不完整」归成 LOW-1，那个分级不对，这里更正。
- **Owner**: 已完成（2026-10-13）

</details>

### ~~TODO-061: REPORT_BUILDER 前端第二批~~ ✅ 2026-10-13 完成

第二批 5 项已全部落地（commit `f014e9f`）：

| 项 | 状态 |
|---|---|
| 15 个操作符全集 | ✅ 值渲染按后端 `_VALUELESS` / `_LIST_OPS` / `BETWEEN` 三类分支 |
| AND/OR 嵌套 | ✅ 递归 `FilterTreeEditor`，同时修掉 TODO-060 |
| 多条条件 | ✅ 无上限（深度上限 4，防手滑） |
| 5 对 JOIN 白名单选择 | ✅ `availableJoins` 实时收窄 + 降级关联显式警告 |
| 临时调整过滤条件（不落库） | ✅ 执行面板，界面上明写「不回写定义」 |

<details><summary>原始分批记录</summary>

第一批（已完成，见 QA 报告
`.gstack/qa-reports/qa-report-pcs-frontend-2026-10-13-report-builder.md`）
只做：数据源 + 字段树勾选/别名/排序/显隐 + **EQ 单条过滤** + 执行链路。

**第二批要做**：

| 项 | 说明 |
|---|---|
| 15 个操作符全集 | `EQ NEQ GT GTE LT LTE IN NOT_IN CONTAINS STARTS_WITH ENDS_WITH IS_NULL IS_NOT_NULL BETWEEN LIKE`（枚举已在 `api/reportBuilder.ts` 里备好，第一批只用 `EQ`） |
| AND/OR 嵌套 | 并**同时修掉 TODO-060 的数据丢失** |
| 多条条件 | 现在硬上限 1 条 |
| 5 对 JOIN 白名单选择 | 后端 b6 已就绪，前端字段树已下发 `joins` |
| 临时调整过滤条件 | 不落库（SPEC §3.2.2(5)），后端 `temporary_filters` 已支持 |
| c7 JOIN 扩展 | 计划里就有，**无具体需求陈述**，未开工 |

⚠️ **不要把「只有一个 EQ」当 bug**。`api/reportBuilder.ts` 的
`OPERATORS_BATCH_1` 与编辑器页的「第一批：仅 EQ 单条」标记就是为此。

- **Owner**: 待认领


### TODO-062: c7 JOIN 扩展 —— 机制已就绪，等需求（**不猜**）

- **症状**：计划里 c7 只有一行「JOIN 扩展 / 按需开放更多 JOIN 对 /
  每对 1 测试」。缺的不是代码，是**需求**。
- **层次一（机制已就绪，c7 无可做）**：`datasource_registry.JOINS` 是个
  tuple 常量，`join_key_for(a, b)` 查白名单。加一对就是加一条 + 一条测试。
- **层次二（c7 的真正内容）= 决定加哪几对**：SPEC §1.3 只批了 5 对，
  说「首批」却**没列后续批次应该有哪些**。任何候选对（管道↔物流、
  泵↔能耗、换热器↔能耗…）都是**推测** —— 没有真实用户问过
  「我要同时看泵和它的能耗」，加进去就是给未来加负担。
  **白名单是安全边界，不是功能清单。**
- **层次三（每加一对前必须验证）**：
  1. **唯一性** —— `tag_number` 两侧都唯一吗？不唯一则 assemble 取最后
     一条（静默）
  2. **NULL 语义** —— 一侧为 NULL 怎么办（缺键 vs None，导出时含义不同）
  3. **大小写/空白规范化** —— `P-101` vs `p-101` vs `P-101 ` 会不会不匹配
  4. ~~**项目一致性**~~ —— **已在 bug-162 修掉，不必等到 c7**（见下）

**触发条件**（不写「等有需求」这种空话）：
> 出现第一个「需要跨源查询、且不在 SPEC §1.3 首批 5 对白名单内」的
> **真实报表定义**时启动。每加一对前须完成上述 1–3 项验证。

- **Owner**: 待认领（等真实需求触发）


### ~~b6 遗漏：JOIN 缺项目一致性校验~~ ✅ 2026-10-13 修完（bug-162）

用户分析指出「5 对白名单缺项目一致性校验」—— **核实后确认成立**，
且比预想更严重。已修，见 bug-162。

- `_fetch_join_rows` 原本只按关联键 `IN (...)` 从表取数，**不带项目过滤**；
  而位号唯一性是**项目内**唯一 → 两个项目用同一���号时，
  项目 A 的报表会**拿到项目 B 的泵记录**。
- 连症状都没有：`assemble` 对重复键取最后一条，不报错不告警。
  报表 200、行数正常、列也齐，只是某个字段的值来自另一个项目 ——
  **报错会让人停下，串数据不会**。
- 修法：从表侧 `and_(关联键 IN (...), project_id == scope)`；
  **按「该源有没有 project_id」分支**（`SUPPLIERS` 是公司级目录，
  加过滤会永远查不出行、表现为「供应商列整列空白」）；
  **不**走 `apply_filters`（项目过滤是越权边界，不能混进用户条件）。
- 测试 `tests/services/report/test_join_project_scope.py` 4 条，
  变异验证（撤掉过滤 → 精确只有跨项目那条转红）。

⚠️ **这条不属于 c7**：c7 是「加更多 JOIN 对」，这是「已有 5 对不完整」。

---

## ✅ TODO-063 固定 10 类报表没有 `task_id` → `report_file_id` 的轮询端点（2026-10-13 修完，27cb4b0 → 见下）

`POST /report/generate` 只回 `task_id`，而 `/report/{id}/status` 只认
`report_file_id`，**两者之间没有桥**。b11 的桥（`report_execution_logs.task_id`
/ `report_file_id`）只加在 report-builder 那条路上。

- 后果：调用方拿到 202 + task_id 之后**没有任何办法知道文件 id**。
  只能在 1 小时内从 ARQ 的 job 结果里捞（`keep_result=3600`），而过期就永远拿不到。
- 本次 QA 脚本是**直接查库**绕过这个缺口的 —— 也就是说这个缺口是已知的、
  绕过去的，不是没看见。
- 与 bug-167 **不是同一件事**：bug-167 是「有端点但时机错了」（已修），
  这里是「这条路上根本没有端点」。
### ✅ 2026-10-13 修完

用户裁决「解决」后按 **SPEC P8 §a7** 定的：SPEC 明写「ARQ 任务；状态查询端点；
失败重试，验收『任务提交 → 轮询状态 → 成功/失败』」，所以这是 SPEC 缺口不是
可选项。同时查清：**这条路的消费方一个都没有** —— 前端只调 report-builder，
后端也只有端点自己调 `generate_report_task`。所以这个缺口不会被任何界面暴露，
只会在按 SPEC 验收时炸。

修法（**没有新增端点**）：

- `report_files` 加 `task_id`（p8_006）。**不**复用 `report_execution_logs`：
  那张表 `def_id` 是 NOT NULL 外键指向 `report_definitions`，而固定 10 类
  报表没有 report_definition —— 复用它就得让 `def_id` 可空再加一列
  `report_type`，等于给一张审计表加一个恒为空的语义分支。
- `task_id` 由**端点自选**（`uuid4().hex`），入队时作 `_job_id` 传给 ARQ
  （`job_id = _job_id or uuid4().hex`）。顺序是**先建行、后入队**：反过来
  worker 可能抢在前面建行，于是出现第二行，轮询端点的
  `scalar_one_or_none()` 当场 MultipleResultsFound。
- `POST /report/generate` 的 202 现在**同时返回 `report_file_id`**，
  调用方直接用它轮询既有的 `/report/{id}/status` —— 不需要新端点。
- 建行逻辑抽到 `report_service.ensure_pending_row`，端点与 worker 共用一份。
  两处各写一遍不是「重复」而是**时序**：只有 worker 建行的话 202 与
  「行存在」之间有 404 窗口（就是 bug-167 那个坑）。
- 入队失败时那一行就地标 FAILED —— 否则留下一行注定没人跑的 PENDING，
  用户看到的是「转圈 15 分钟然后莫名失败」（回收器才纠正）。
  同族坑见 `arq_queue` docstring：「入队失败必须让端点知道」。

## 🟡 TODO-064 builder 执行日志没有回收器（2026-10-13 E2E 真跑发现）

- `reclaim-stale-report-tasks` cron 只回收 `report_files` 的 PENDING 行，
  **不管 `report_execution_logs`**。
- 2026-10-13 的修复让日志行在**入队时**就存在（bug-167），于是
  「worker 全挂 ⇒ 行永远停在排队态」第一次成为可观测的挂起状态。
- 此前不可观测：行由任务体建，worker 不跑就没有行。
- 阈值可复用 `report_files` 那套（15 分钟）。

## 📋 P8 异步链路首轮真跑结论（2026-10-13）

报告：`.gstack/qa-reports/qa-report-pcs-backend-2026-10-13-arq-chain.md`
（`.gstack/` 已 gitignore，只落本地）

- 自定义定义链路 11/11、固定 10 类链路 6/6、后端全量 4445 passed / 0 failed
- 暴露 11 个缺陷（bug-163~167），全部已修并有回归测试
- 方法论要点见报告「三条方法论教训」——
  **「替身比被测物更宽容」是本轮最贵的失效模式**：
  测试复用任务自己的 session，于是「从不 commit」在任何断言下都看不出来，
  修法是**换观测点**（任务返回后用另一个 session 读），不是加断言。
