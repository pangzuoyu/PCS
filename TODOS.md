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

---

## TODO-042 遗留两项：✅ 已闭环（2026-10-19）

### 1. `streams` 三条 CHECK（迁移 `p8_011`，已在两个库执行）

契约已收紧成枚举，但 `streams` 表原本**只有** `ck_streams_case_type`
⇒ 走 API 被 422 挡住、**直接 SQL / 脚本却能写进去**，直到下次 GET 的
响应校验才 500（写入现场与报错现场分离）。

新增 `ck_streams_phase` / `ck_streams_data_mode` / `ck_streams_source_type`，
迁移**从枚举取值**而非硬编码（硬编码 = 与 `enums.py` 形成第二份定义，
正是 bug-187~191 的根），ORM 同步声明，幂等（先查 `pg_constraint`）。

⚠️ **这条 CHECK 当场抓出一处测试数据缺陷**：三个 heat/outlet 测试的 fixture
写的 `data_mode="MEASURED"` / `source_type="MEASURED"` 不在任何词表里
（`MEASURED` 是 `simulation_status` 的值，不是 `data_mode`）。
已改成 `CHEMICAL` / `SIM_IMPORT`。**让 fixture 不能瞎填，就是 CHECK 的价值。**

**执行结果**：

| 库 | revision | CHECK | `raw_phase` | streams 行数 | `alembic check` |
|---|---|---|---|---|---|
| `pcs`（开发） | `p8_011` | 4 条 | 有 | 0 | **exit 0** |
| `pcs_test`（行为验证） | `p8_011` | 4 条 | 有 | **202（未变）** | **exit 0** |

⚠️ `alembic check` 退出码是 **255 不是 1**；且 DB 落后 code head 时它**直接拒绝跑**
——「守门没报」有时是**它根本没跑**（bug-143/144 藏了很久就是这么来的）。
两个库都先确认 `current == heads` 才看它的结论。

**约束在真库上真的生效**（SAVEPOINT 回滚探针，`pcs_test`）：

| 插入 | 结果 |
|---|---|
| `data_mode=CHEMICAL` / `source_type=SIM_IMPORT` / `phase=NULL` | ✅ 接受 |
| `phase=SOLID` | ✅ 接受 |
| `phase=NULL` + `raw_phase='SUPERHEATED'`（词表外原值可留） | ✅ 接受 |
| `data_mode='MEASURED'` | ❌ `CheckViolation` |
| `data_mode='GAS'`（PSV 的词，不是物流的） | ❌ `CheckViolation` |
| `source_type='NOPE'` / `'PIPE_CALCULATED2'` | ❌ `CheckViolation` |
| `phase='GAS'` | ❌ `CheckViolation` |

### 2. `streams.raw_phase` —— 堵住一次静默的数据丢失

词表外的相态字母此前一律置 None 且**原值被丢弃**：用户只看到「相态没填」，
不知道丢了什么、为什么丢。

- 新列 `raw_phase`（可空，**故意不加 CHECK** —— 它的用途就是装下词表外的值，
  加 CHECK 就把用途删了）；
- **只在归一失败时填**；认出来了就不填，否则它变成与 `phase` 恒等的冗余，
  且失去「异常信号」语义；
- `MIXED` 不填 —— 它是**已知**合法值（只是导入器不抽组成），
  另有 `is_mixed_phase` 记录，那不是「丢失」；
- 进了契约 ⇒ **`phase IS NULL && raw_phase 非空` = 「有个值没认出来」，可查**。

### ⚠️ 探针本身犯了三次错（这一段比上面两张表更值得记）

真库验证时，我的探针**连续三次**给出了误导性结论：

1. `INSERT` 漏了 `workspace_id` ⇒ 五条探针全被 NOT NULL 挡掉，
   「被拒」是假结论 —— **失败原因不是被测的那条约束，就等于没验**；
2. 第一条探针**提交了**，后续全部撞 `uq_streams_project_stream_name`，
   报的是 UniqueViolation 而非 CheckViolation；
3. 改了探针的 label 但**没改实际插入值** —— 探针 4/5 插的仍是
   `CHEMICAL`/`SIM_IMPORT`，什么都没验到，却输出「被接受」。

同一天我在别处还犯过一次：python 批量替换字符串后**无条件打印 "ok"**，
而替换其实静默失败了（目标串没匹配）⇒ 一段本该落进文件的文档其实没落。

⇒ **「我做了 X」的结论只有在「X 的效果真的被观察到」时才成立。**
写探针与写测试是同一门手艺：断言必须落在被测路径上。
（同 `bug-174` 的空绿、`test_pipe_class_schema.py` 里被自己解释文字触发的 docstring 守卫。）

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

## TODO-052: `workflow_progress` 表名在两个规格里有互不相容的定义（✅ 已裁决 2026-10-20）

| 出处 | 字段 | 语义 | 状态 |
|---|---|---|---|
| `SUP-008 V1.1 §8.5` | **14**：`sequence_no / main_workflow_item / progress_percent / external_condition_1..5(+_progress) / start_date / completion_date` | **项目作业流程进度百分比表**（Excel Sheet 2「作业流程」导入） | **未落地** |
| SPEC-P9 `P9A-OBS-001` / ADR-0047 | **8**（实 10，见 TODO-053） | **签署 / 变更单 / 代录的工作流步骤观测表** | **已落地**（P9A-2 B0） |

两者**领域不同**却共用表名。把两个领域塞进一张表，与 ADR-0047 §后果
「写入点超出这个数 ⇒ 回 ADR 修订，不要就地加」是同类错误。

### 裁决（2026-10-20，决策委员会）

1. **本版建后者，不建前者。** ADR-0047 语境下的 `workflow_progress` 是准确的 ——
   它记录的是「工作流（签署/变更单/代录）的进度」。
2. **将来若要建 SUP-008 §8.5 那张表，必须另起表名**（建议 `project_job_progress`），
   **不得复用 `workflow_progress`**。

### 已落的两处引用修正（随本次裁决一起完成）

- **ADR-0047 的 Related 栏原写「SUP-008 V1.1 §2.6」是错的引用** —— §2.6 实为
  「2.6 新模块：反应器计算」，§3.2.6 是「新增 reactor_results 表」，
  **8 字段的定义在 SUP-008 里根本不存在**。已在 ADR-0047 头部加「引用勘误」，
  并在「背景」段新增「同名不同表」小节。
- **SPEC `P9A-OBS-001` 的「依据」栏有同一个错引用** —— 已在该行下方加勘误注记
  （**未删改正文**，保留原始表述以留痕）。

- **发现**：2026-10-20，P9A B0 开工前实测
- **严重度**：~~🔴~~ → **已关闭**（表名与引用都已定）
- **关联**：ADR-0047 · TODO-053 · TODO-057

---

## TODO-053: `workflow_progress` 实际 10 个业务字段，比 SPEC 列的 8 个多 2（🟡 已知偏差）

SPEC P9-OPEN-007 / P9A-OBS-001 列 8 字段，P9A B0 建了 **10 个**业务列。
多出的两列**不是设计口味，是被 P9A 自己的需求强制的**：

- `workflow_type` —— P9A-OBS-003 的读 API 路径是 `{workflow_type}/{workflow_id}`；
  ADR-0047 §① 的三个写入点（签署 / 变更单 / 代录批准）也靠它区分。缺了它，
  一次签署与一次代录的进度行无法分辨，甘特图会把两条工作流画成一条。
- `project_id` —— 读 API 要按项目鉴权（越权 404），而 `workflow_id` 是多态的
  （`SIGN`→版本 ID / 其余→交付物 ID），无法 join 回项目。

另有 2 处改名：`step_no` → `step_order`、`step_name` → `step_role`，
为与 `SignatureMatrix.steps_json` 的键（`step_order` / `sign_role`）逐字一致，
写入时不需要翻译层。

**不回改 SPEC 正文** —— SPEC 是绑定权威，改它要重走 §7.2 验收；
改为**在 SPEC §3.2.3 `P9A-OBS-001` 行下方加实现偏离注记**（2026-10-20 已落）——
「加注记」与「改正文」成本完全不同：前者是记录，后者触发验收重走。
ADR-0047 §后果 段也已加同一份偏离说明（下一个实施者读到「8 字段」而代码是 10 列时，
应当知道代码是对的、文档过时）。

- **发现**：2026-10-20，P9A B0
- **归属**：SPEC 下次修订（P9A 收口时一并处理）
  ✅ **已于 2026-10-21（P9A Z 收口）登记** —— `spec/PCS-REQ-2026-002-SPEC-P9 …`
  **V2.1**：§3.2.3 `P9A-OBS-001` 的「8 字段」**保留原文不改**（它是原始设计，
  不是实现目标 —— 改正文要重走 §7.2 验收），实际 10 业务列 + 2 处改名以
  **行下注记 + ADR-0047 §后果 + V2.1 版本历史**三重登记。
  ⇒ 本条**关闭**（文档侧已对齐；代码侧的 2 列**不删** —— 删了会破项目鉴权）。
- **严重度**：LOW（多出的 2 列都被读 API 实际使用，删了会破项目鉴权；
  不存在「文档说有、实现没有」的功能缺口）
- **关联**：TODO-052 · ADR-0047 · P9A-OBS-001

---

## TODO-054: 记录侧「多级批准」的角色链无定义来源（P9A B4b 裁决登记）

`RecordMixin` 只有 `approval_step` / `approval_depth` / `approval_role` 三个标量列；
`project_templates.default_config_json` 的 `record_approval_config` 只有一句注释、
**无消费方**（`grep record_approval_config app/` 仅命中那一句）。

**P9A B4b 的裁决**（不发明需求）：
- `approval_role` 由 `POST /records/{module}/{id}/submit-approval` 请求体指定
  （7 值词表逐字取自 `app/models/project.py:154`），并保持到终态；
- 「多级批准」表达为**同一待批角色逐级批 N 次**，`approval_depth` 由请求体给出；
- 每一步只允许 `record.approval_role` 那个角色批（403 `APPROVAL_ROLE_MISMATCH`）；
- `can_self_check` 在记录侧无配置源 ⇒ 取**最强形式**：提交人不能把
  `approval_role` 设成自己的角色（403 `APPROVAL_SELF_REVIEW_FORBIDDEN`）。
  宽松形式（只在配置说 false 时才拒）在没有配置源时**永远不成立 = 没有防护**。

**待定**：`record_approval_config` 的真实结构由谁定义（项目模板？硬编码 4 级链？
沿用 `SignatureMatrix.steps_json`？）。定了之后 `submit-approval` 应改为**推导**
而不是显式输入。

- **发现**：2026-10-20，P9A B4b 开工前
- **归属**：P9B 或独立一轮（**不阻塞 P9A**：当前形态自洽且有测试）
- **严重度**：MEDIUM（批准链退化为「同角色批 N 次」，与 SPEC 可能的「多角色链」
  不同；每一步仍留痕、可追溯，只是不区分人）
- **关联**：TODO-053 · ADR-0047

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

## ✅ DONE —— TODO-057: ADR-0047 §① 的第三个观测写入点（变更单）（2026-10-26 落地，P9A-DLV-007 同批）

ADR-0047 §① 列了**三个**工作流写入点，P9A B lane 只落了**两个**：

| 工作流 | 写入点 | 状态 |
|---|---|---|
| SIGN | `DeliverableService.sign_step` | ✅ B2 |
| CUSTOMER_APPROVAL_PROXY | `DeliverableService.record_customer_approval_proxy` | ✅ B3 |
| **CHANGE_NOTICE** | 变更单的**创建**与**自动关闭** | ✅ **2026-10-26** |

### 落地了什么（commit `da299fb` + `3b7e99b`）

- **矩阵有了**（前置）：`SignatureMatrixService.ensure_change_notice_matrix`
  惰性建内置模板 `CHANGE_NOTICE_3_LEVEL`（3 级：校核/审核/审定）+ 项目绑定
  ⇒ `signature_matrices` 不再恒 0 行。
- **创建路径可达**：`create_change_notice` 不再抛 `NotImplementedError` ——
  建 `deliverables`（`matrix_id` 非空）+ `change_notice_details` + 审计。
- **写入点 2a（创建）**：写一行 `CHANGE_NOTICE` / **PENDING**
  （流程已发起、尚未关闭），`workflow_id` = **变更单自己的 deliverable_id**
  （不是版本 id）。
- **写入点 2b（自动关闭）**：`approve_change_notice` 把该行改成 **COMPLETED**
  （`completed_at` 非空）。审批失败（404/409）**不写**观测。
- **同一事务**：观测写与业务变更同生共死（观测写失败 ⇒ 建单回滚）。

### 口径（写进 SPEC 验收记录的那句）

**CHANGE_NOTICE 工作流只写 1 行**（`step_order=1`，`step_role='CHANGE_NOTICE'`），
不是矩阵的 N 行。变更单的**签署步骤**已由 SIGN 工作流观测
（`workflow_id` = 版本 id）⇒ 再写一份就是同一事实的两个来源。
⇒ 变更单的 3 级校审在**签发之前**不可见（那时它还没有版本行）—— 与真相一致。

### 遗留（**本条关闭，但下列各项另立条目**）

- 变更单仍**无 HTTP 入口** ⇒ TODO-068；
- 「一条记录同时只有一张变更单」是**新增业务约束**（`doc_no` 唯一约束的副产品）
  ⇒ TODO-069；
- `signature_matrices` **无管理面**（项目自定义矩阵建不了）⇒ TODO-070；
- `project_signature_matrix_bindings` **缺 (project_id, module) 唯一约束**
  ⇒ TODO-071（bug-2052）；
- `steps_json` **校验器**（部分跳过目前只记 WARNING 日志）⇒ TODO-072。

### 历史（保留当时的判断，勿删）

#### 状态措辞（2026-10-20 决策委员会纠正）

**这是「不可演示」，不是「不采纳」。**
- 「不采纳」意味着该项从验收清单里消失；
- 「不可演示」意味着**该项存在、待实现**。

⇒ P9A 整体验收时按「**2/3 已写入，第 3 项待 P9A-DLV-007**」记录，
**既不得**记作「已写入」，**也不得**记作「不适用」。
（标错的后果与 TODO-045 同形：清单上看着处理过了，实际没做。）
✅ **该措辞已落到验收记录** —— `spec/PCS-REQ-2026-002-SPEC-P9 …` **V2.1 §7.2.1
P9A 验收状态**：该行状态 = **部分（2/3）**，并写明「记 2/3，第 3 项待
P9A-DLV-007」。**已于 2026-10-26 更新为 3/3**（P9A-DLV-007 落地）。

#### 事实（2026-10-20 实测，已过时）

`change_notice_service.create_change_notice` 目前直接 `raise NotImplementedError`
（等 P9A-DLV-007 `SignatureMatrixService`），所以 ADR §① 指定的两个触发点
（创建 / 自动关闭）今天**都没有可达路径**。

**为什么不在 `approve_change_notice` 里补**：ADR §① 指定的两个触发点是
「创建」与「自动关闭」，而 `approve_change_notice` 两者都不是 ——
它是「批准变更单、变更生效」（交付物 `PENDING → APPROVED`）。
在那里加写入 = 写一个不在 ADR 词表里的语义点。

**为什么不写占位测试**：永远绿的测试会把「缺一个写入点」伪装成「已覆盖」。
总纲第二轮处置第 2 条刚删过一个同形的伪测试，不重复同一个错。

#### 归属（决策委员会要求确认，二者同时成立，分工不同）

- **前置依赖 = P9A-DLV-007**（`SignatureMatrixService`）：`create_change_notice`
  卡在它上面，`Deliverable.matrix_id` 是 NOT NULL + FK，
  而解析 `CHANGE_NOTICE_3_LEVEL` 矩阵的正是这个服务。它不落地，
  变更单的创建路径不可达 ⇒ 触发条件。
- **改动落点 = `app/services/change_notice_service.py`**：写入点本身要加在
  变更单服务里（`create_change_notice` 与自动关闭路径），不是矩阵服务里。
- ⇒ 归属一句话：**触发看 P9A-DLV-007，改动在变更单服务**。
  排期跟着 DLV-007，做的时候不要去改矩阵服务。

- **发现**：2026-10-20，P9A B lane 终审（fresh reviewer 提出 HIGH，按后果改判 MEDIUM）
- **严重度**：MEDIUM → **已解除**（症状「变更单在甘特图上永远空白**且不报错**」
  不再成立）
- **关联**：ADR-0047 §① · TODO-052 · TODO-058 · TODO-068~072

---

## TODO-058: `RECORD_TYPE_REGISTRY` 的语义未定 + 列完整性无契约（✅ 已裁决 2026-10-20）

### 裁决

**`RECORD_TYPE_REGISTRY` = 「本仓的结果表模型清单」（表枚举）。**
它**不是**能力清单 —— 既不是 `finalize_calc_record` 的支持清单
（那段是鸭子类型，注册表从未驱动过，见 TODO-048），
也不是「可参与工作流的记录类型」。

**「能不能走 9 态工作流」是从 schema 推导的谓词，不是注册表的属性。**

### 依据（实测，2026-10-20）

1. 全仓 `RECORD_TYPE_REGISTRY` 的**代码消费方只有一个** ——
   `app/api/v1/records_actions.py`（P9A B lane 新写）。
   其余引用全是模型注释与 `tests/architecture/*` 的存在性断言
   （`len == 21`、`"X" in REGISTRY`）。**它此前没有功能消费方。**
2. 三个问题键各缺 **24~25 个 `RecordMixin` 列**
   （`CostEstResult` 25 / `TwoPhaseResult` 24 / `ProjectCalculationStandardProfile` 24），
   **根本不继承 `RecordMixin`** —— 它们不是记录。
   ⇒ 它们被登记的理由只是「它们是结果表」。

### 为什么不另建「可工作流模块清单」

它是**人工维护的事实**，而注册表也是人工维护的事实 —— **两份必然漂移，
而漂移的那份没人会去对**。本仓已为此付过代价：P9A B lane 明确拒绝另建
「模块 → 模型」映射而复用注册表；终审 CRITICAL 的 23 条 RED 也正源于
「注册表是能力清单」这个**未经证实的假设被当成了保护色**
（原测试断言「每个键都能解析」，却从未验证「解析后能用」）。

谓词从 `RecordMixin` 推导 ⇒ **推导出来的，不漂移**。

### 落地（`app/services/record_capabilities.py`）

- `REQUIRED_WORKFLOW_COLUMNS` —— **从 `RecordMixin.__annotations__` 派生**
  + `project_id`。手抄清单会与 mixin 漂移，漂移的表现是「哪天给 mixin 加了列、
  判定却没跟着变」—— 于是又出现一条「解析成功但加载 500」的路。
- `supports_state_workflow(model, *, need_workflow=True)` / `missing_workflow_columns(model)`
  —— 后者**报出缺哪些列**，不吞掉（「不支持」必须能回答「缺什么」，
  否则端点只能显示一句无信息量的文案）。
- `WORKFLOW_UNSUPPORTED` —— 当前不支持的键 + **真实理由**。
  它不新增键，只解释已存在的键；测试强制理由必须提到该键**实际缺失的列**，
  写「该表不参与工作流」这种放之四海皆准的空话会红。
- 契约测试 `tests/services/test_record_capabilities.py`（10 例）：
  注册表每个键要么支持、要么在例外字典里且理由非空且点名真实缺列；
  **两边都不能为空**（空集合说明分区写死了而不是真在推导）；
  已支持的键不得留在例外字典里（防僵尸条目）。
- `calc_lineage.py` 的模块 docstring 已澄清「它是什么 / 不是什么」，
  并指向 capabilities 模块 —— 这是 TODO-048「名不副实」那半的处置。

### 残余（不在本条裁决内）

`CostEstResult` / `TwoPhaseResult` / `ProjectCalculationStandardProfile`
**仍然留在注册表里**（移出会破坏 `tests/architecture/*` 的
`len == 21` 与 `"ProjectCalculationStandardProfile" in REGISTRY` 断言）。
它们不参与工作流这件事由谓词负责表达，不需要改注册表。
`CostEstResult` 补 `record_hash` 是 **D lane**（TODO-048 的补列那步）；
补齐 `project_id` / `sign_status` 之后，从 `WORKFLOW_UNSUPPORTED` 删掉条目即可，
`test_supported_keys_are_not_listed_as_exceptions` 会守住不出现僵尸条目。

- **发现**：2026-10-20，P9A-2 终审（决策委员会提出，用户裁决）
- **严重度**：~~🔴~~ → **已关闭**（语义定 + 谓词落地 + 契约测试）
- **关联**：TODO-048（同一注册表的 finalize 语义，已在其 docstring 澄清）· TODO-055（键风格不统一）

---

## TODO-059: 签署矩阵的 `sign_role` 是**全局角色**，与 `user_projects.role_in_project` 语义不对称（✅ 已被 ADR-0050 取代）

- **发现**：2026-10-20，P9A C lane（C4 待办实时计算）自查越权面时暴露
- **严重度**：🟡 已知不对称 —— **当前行为是自洽的**（见下），但口径本身待裁决
- **关联**：TODO-054（记录侧多级批准的角色链无定义来源，同一根因：角色词表有两个来源）

### 事实

签署矩阵的 `sign_role` 与 **token 的 role claim**（`users.roles`）比较：

```
app/services/deliverable_service.py
  sign_role = str(step.get("sign_role", ""))
  if sign_role != actor_role:      # actor_role = current_actor().role = 全局角色
      raise PcsError(code="SIGN_STEP_ROLE_MISMATCH", status=403)
```

而项目那一侧（`app/api/v1/deliverables.py::_authorize` →
`check_project_access_or_404`）**只校验成员身份**，不看角色。

⇒ **「能签第 N 步」= 有 `user_projects` 有效授权 且 全局角色 == `step.sign_role`**。

### 为什么这是问题

`user_projects.role_in_project` 存在（DESIGNER/CHECKER/APPROVER/REVIEWER/VIEWER），
但**签署矩阵不读它**。于是一个「全局 DESIGNER、项目内 REVIEWER」的人：

- 在项目 A 上**签不了** REVIEWER 那一步（403 `SIGN_STEP_ROLE_MISMATCH`）
- 在项目 A 上却**被当成** REVIEWER 之外的角色处理

「项目内角色」这套词表在签署链路上**实际上没有消费方**。

### 本 lane 的处置（已落地）

P9A C1b / C4 的通知收件人与待办**都按全局角色 ∩ 项目授权**算，与
`sign_step` 实际执行的口径一致。理由：按项目内角色圈人，会通知 / 列出那些
**点了必然 403** 的人 ——「待办里有，点进去说你不是」比没有待办更坏。

代码留痕：`app/services/todo_service.py::compute_todos` 的 docstring、
`app/services/notification_recipients.py::resolve_role_recipients` 的 docstring、
`tests/api/v1/test_todos.py::test_todo_does_not_list_items_the_user_cannot_sign`。

### 待裁决

**签署职责是「组织职能」还是「项目分工」？** —— 换句话说，矩阵里的
`sign_role` 该指哪一套角色词表。

#### 三条此前漏掉的事实（2026-10-20 复核时查实）

1. **全局角色实际是**单值**。`ldap_client.resolve_role()` 从组映射里返回
   **第一个**命中；`ad_sync` 写 `users.roles = [role]`（单元素）；token 只带
   **一个** `role` claim（`create_access_token(subject, role)`）⇒ 一个
   「既是设计者又是复核者」的人**登录后只有一个角色**，且映射表里
   `DESIGNER_GROUP` 排第一 ⇒ 静默取到 DESIGNER。
2. **`role_in_project` 至今零授权消费方**。`check_user_project_access()`
   有 `required_role` 参数且会比对 `role_in_project`，但**全仓 4 个调用点
   没有一个传它** ⇒ 那条比对分支是**死代码**。项目内角色只被存下来、
   在 `user_projects` 端点响应里显示，从未参与任何鉴权判定。
3. **矩阵已按项目绑定**（`project_signature_matrix_bindings`：project +
   module + matrix_id），`sign_step` 时 `deliverable.project_id` **现成**
   ⇒ 「矩阵要带项目上下文」这个说法**不成立**；且真库 `signature_matrices`
   **0 行**、后端与前端**都没有矩阵管理端点** ⇒ 改口径**不撞存量数据、
   不撞界面**。

#### 三个选项与真实代价

| 选项 | `sign_role` 指 | 收益 | 代价 |
|---|---|---|---|
| **A（现状）** | 全局角色（token claim） | 零改动；与 `_SIGN_ROLES` 粗筛同源 | 一个人在项目 A 上不能以「复核人」身份签（哪怕他在该项目的 `role_in_project` 是 REVIEWER）；`role_in_project` 继续零消费方；**全局单值**意味着「既是设计者又是复核者」的人只能占一个角色 |
| **B** | 项目内角色 | 项目分工可表达（这个项目上是复核人、那个项目上是设计人）；`role_in_project` 有了消费方 | 改 `sign_step` 判定口径（1 处比较 + 取值来源）；**项目授权的运营流程成为签署的前置** —— 每个项目每个签署角色都要有人手工 `grant_project_access`；`_SIGN_ROLES` 粗筛与细判的口径要一起复核 |
| **C** | 全局 ∪ 项目内 | 两种现实都能表达 | **职责分离被削弱**：全局是 REVIEWER 的人可签 DESIGNER 那一步 —— 正是 `can_self_check` 与「不能自己签发自己审」这套机制要防的 |

#### 一个与本条**独立**的潜在缺陷（无论选哪个都该修）

全局角色**单值**这件事本身是个隐患：既是设计者又是复核者的人，登录后只能
拿一个角色，而映射表顺序让 `DESIGNER_GROUP` 优先 ⇒ **静默降级**为设计者，
复核那一步**谁都签不了**。修它要动 `resolve_role` + token 的 `role` claim
（改成列表）+ `current_actor` 的 `_Actor.roles`（已是列表，兼容）。

⚠️ 本条（口径）与那条（单值）是**两件事**：即使裁决维持 A，单值缺陷仍要单独修。

- **裁决**：2026-10-20，用户给出完整目标模型（全局角色 → 资格集 → (用户,项目,工作集)
  的单一签署职责），并裁决：资格集入 DB 可配置、签署词表与全局词表彻底分名（`Project-` 前缀）、
  能力按 9 态机批准链、项目 DRAFT→ACTIVE、指定权限仅项目负责人、工作集入 DB 且 SIM 合成 1 个。
  ⇒ **本条被 `docs/adr/0050-sign-responsibility-and-task-participation.md` 取代**
  （ADR-0050 是本条的完整形态；本条只是它的一个切面）。
  ⇒ 本 lane 已落地的「全局角色 ∩ 项目授权」口径是**过渡态**，P6 将改为从
  `can_sign()` 派生（ADR-0050 §后果 迁移路径）。
- **发现**：2026-10-20，P9A C lane 自查
- **严重度**：✅（已被 ADR-0050 取代）
- **关联**：ADR-0050、TODO-054

---

## ✅ DONE —— TODO-060: `record_type` 两套词表（类名 vs 表名）→ 收敛为注册表键（2026-10-20 修完）

> **闭环摘要**：契约面（`/locks` + 6 个 PATCH 的 guard 入参）由**表名**改为
> `RECORD_TYPE_REGISTRY` 的**键**；`/locks` 三端点**加校验**（未登记 ⇒ 404）；
> `{record_type}` 在 OpenAPI 里带 `enum`；**SPEC 升 V2.0**（破坏性契约变更）。
> ⚠️ 实施中**推翻了本条的两处原文**：① 不是「三套词表」而是**五套**；②
> 「`__tablename__` ↔ 注册表键**双向**可换」**实测为假**（只有「键 → 表名」
> 单向成立）⇒ 原定的「归一到类名」方向作废（注册表 21 键里 5 个 ≠ 类名）。
> 详见 `docs/PCS-PLAN-P9A-5-债项清理.md` Task A。

<details><summary>原条目（2026-10-20 修前）</summary>

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

## ✅ DONE —— TODO-061: `CostEstResult` 无 `project_id` ⇒ 编辑面零项目隔离（2026-10-20 修完）

> **闭环摘要**：迁移 `p9_007` 补 `cost_est_results.project_id`（NOT NULL + FK +
> 索引，`UPDATE ... FROM equipment_list` 回填）；`cost_est.py` **8 个端点全部**
> 补守卫（实测原先 **0 处**）；`GET /results` 的 `project_id` 改**必填**。
> ⚠️ 实施中把本条的范围**写大了也更准了**：原文写「PATCH/DELETE」，实测
> **8 个端点全无鉴权**，且 `GET /results` 不传参时**整表返回**（跨项目**读**泄漏）。
> 详见下方原文与 `docs/PCS-PLAN-P9A-5-债项清理.md` Task B。

- **发现**：2026-10-20，P9A-4 D2 修 bug-2039 时顺带查出来的。
- **事实**（实测 2026-10-20）：
  - `app/models/calc.py:1193` `class CostEstResult(Base)` —— **不继承**任何
    mixin ⇒ **没有 `project_id` / `workspace_id`**，只有 `equipment_id`。
  - `app/api/v1/cost_est.py` 全文 **0 处** `check_project_access_or_404` /
    `check_record_access_or_404` ⇒ 任何持 `DESIGNER` 角色的登录用户都能
    改/删**别人项目的**造价结果。
- **为什么 D2 没顺手修**：隔离需要一条「这条记录属于哪个项目」的路径。
  `CostEstResult` 本身答不了 ⇒ 要么补 `project_id` 列（迁移 + 回填 +
  6 处守卫面），要么经 `equipment_id → Equipment.project_id` 反查。
  **两者都是设计决策，不属于 D lane 的授权范围** ⇒ 只登记。
- **不修的代价**：这是本仓目前**唯一一类**「连守卫都不存在」的编辑面
  （bug-2039 那族至少有守卫，只是顺序错了）⇒ ADR-0050 P5「参与人员门挂
  24 个创建/审阅端点」之前必须先补，否则**门挂上去也是空的**。
- **建议**：随 ADR-0050 P5 一起做，且**先补 `project_id` 列**（与
  ADR-0050「`CostEstResult` 无 `project_id` ⇒ 工作集归属需先补列」是同一笔，
  两处登记指向同一件事，**只做一次**）。
- **严重度**：HIGH（真实越权面，非理论）
- **关联**：bug-2039（守卫顺序族）、ADR-0050 P5、TODO-048

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

## TODO-065: `GET /deliverables/{id}/progress` 聚合端点（缺失 · P9B-2 前置）

**What:** 后端加一个聚合端点，一次返回某交付物**三类**工作流的进度：
`GET /api/v1/deliverables/{deliverable_id}/progress`。

**Why:** `GET /workflow-progress/{workflow_type}/{workflow_id}` 是**单条**查询，
而三类工作流的 `workflow_id` 语义**各不相同**（实测 2026-10-21）：

| 工作流 | workflow_id | 前端怎么拿 |
|---|---|---|
| `SIGN` | 版本 ID | `DeliverableResponse.current_version_id`（P9B-1 本批加） |
| `CUSTOMER_APPROVAL_PROXY` | 版本 ID | 同上 |
| `CHANGE_NOTICE` | **变更单自身的 deliverable_id**（变更单是独立交付物，`deliverable_type=CHANGE_NOTICE`） | ⛔ 前端**拿不到** —— 需要查「当前交付物 → 它的变更单」的关联 |

⇒ 前端要凑齐三类 ⇒ 4~5 个请求/行，且「变更单的 workflow_id 怎么拿」这段逻辑
会落在**前端** ⇒ 错误的位置（关联规则在后端：`change_notice_details` 与
`deliverables` 的关系不是简单外键）。

**Pros:** 前端 1 次请求拿全；关联解析归后端；P9B-2 加新工作流类型时前端不动。

**Cons:** 新端点 + 契约 + 测试；需定义「一个交付物有多个变更单时取哪个」的口径。

**Context:** P9B-1（2026-10-21 裁决）**本批不做** —— 本批范围收窄为「只展示
SIGN 工作流」，SIGN 用既有 `GET /workflow-progress/SIGN/{version_id}` 即可，
聚合端点此时「退化成一个没有收益的新端点」。
**触发条件：P9B-2 开始实现 `CUSTOMER_APPROVAL_PROXY` / `CHANGE_NOTICE` 面板时，
先做聚合端点，再做面板** —— 否则前端要自己解析变更单关联（P9B-2 会重走一遍
「三个选项」的讨论）。
**归属：** P9B-2，与两个新面板同批。

## TODO-066: 编辑审计缺**按项目守卫**的读端点（普通用户看不到「查看差异」）

**What:** 后端加 `GET /records/{module}/{record_id}/edits`（只回 `changed_fields`
字段名列表 + 操作人 + 时间），带**项目守卫**（`check_record_access_or_404`）。

**Why:** SPEC §6.21 P9A-LCK-006 要求 409 弹窗提供「查看差异」，而差异内容在
**编辑审计**里（`audit_logs` 的 `RECORD_EDITED` action）。但唯一的读端点
`GET /audit-logs` **限 SYSTEM_ADMIN**（实测：`app/api/v1/audit.py:58`
`require_roles(user, "SYSTEM_ADMIN")`，且 `audit_logs` 表**无 project_id**）
⇒ 普通 DESIGNER 拿到 409 弹窗却**点不开差异**。

**Pros:** 普通用户能看差异（409 弹窗的第二个出口才有意义）；不泄露跨项目数据。

**Cons:** 新端点 + 契约 + 测试；`audit_logs` 无 `project_id` ⇒ 授权只能靠
`resource_type + resource_id` 反查所属项目（`records` 表有 project_id）。

**Context:** P9B-1（2026-10-21 裁决）**本批不做** —— 前端优雅降级：
「查看差异」遇 403 ⇒ 显示「无权查看差异（需系统管理员）」并**保留**
「放弃我的修改并刷新」出口。
**触发条件：P9B-2 做签署流程前端（批注/状态时间线）时一并做** —— 那时编辑审计
的展示面更大。
**归属：** P9B-2。**关联：** SPEC §6.21 P9A-LCK-006 · ADR-0048 §⑦。

## TODO-067: P9B-1 最终评审的 **7 条 deferred minor**（🟡 延后到 P9B-2 顺手做）

**What:** P9B-1 的最终整支评审（2026-10-21，范围 `a963a76..ed58075`）报出
1 Critical + 5 Important + 8 Minor。Critical 与 Important **已修**（commit
`20a3cc6`，见 `.wolf/buglog.json` 的 bug-2044~2049）；下面 7 条 Minor 按
「每个都要一个测试 + 一次改动」的规矩**延后**：

| # | 事项 | 位置 |
|---|---|---|
| 1 | 「联系管理员」按钮在生产里是**死的**（`onContact` 可选，唯一的生产调用方省略了它）⇒ `basis=no_baseline` 时点它**没反应** | `EditConflictModal.tsx:101` |
| 2 | `editableFieldDefs` 从 `columns` 派生 ⇒ `editableFields` 里漏掉的字段会**静默**从表单消失（无错误、无测试）⇒ 缺一条「`editableFields ⊆ columns`」的守卫 | `resultModules.ts:314` |
| 3 | 降级横幅成功后**不消失**（`onDegraded(null)` 从不被调）⇒ 一次 Redis 抖动把警告钉到会话结束 | `useEditLock.ts:114` |
| 4 | `enabled` 翻 false 时状态不复位 ⇒ 换一条记录会短暂显示上一条的「他人正在编辑 / 锁已失效」 | `useEditLock.ts:70` |
| 5 | 卸载释放的路径硬编码 `/api/v1/locks/...`（应取 `api.defaults.baseURL`）—— 那是**卸载期间唯一必须成功**的路径 | `ResultEditDrawer.tsx:121` |
| 6 | `api/audit.ts` 的 `listRecordEdits` 与 `auditApi.listAuditLogs` **完全重复**（同端点同响应类型）⇒ 只多一个名字 | `api/audit.ts:108` |
| 7 | `WorkflowProgressPanel` 把 403 / 404 / 网络错误都映射成同一句 `errorDescription` ⇒ **404 被读成「无权限」** | `WorkflowProgressPanel.tsx:74` |

**Why:** 评审的 skill 明确「Minor 进 ledger 延后，不进修复批」⇒ 一次一个测试 +
一次改动，混进来会让这批的修复面失控。

**归属：** P9B-2（顺手做，不单独排期）。**关联：** P9B-1 最终评审 ledger
`.superpowers/sdd/PCS-PLAN-P9B-1-结果记录页与编辑锁/progress.md`。

## ✅ DONE —— TODO-068: 变更申请**无 HTTP 入口**（2026-10-26 落地，P9A-DLV-011 T4）

**落地（用户 2026-10-26 裁决「068 全闭环（ADR-0008 忠实）」）**：

- 3 个新端点：`POST /records/{module}/{id}/initiate-change`（CHECKED →
  CHANGE_PENDING）、`/apply-change`（→ CHANGED）、`/change-notice`（建变更单）。
- ⚠️ **此前记录到不了 CHANGED** —— `INITIATE_CHANGE` / `APPLY_CHANGE` 全仓
  **没有任何 API/服务触发** ⇒ 建单端点即使写出来也不可达（已补）。
- 变更单**建单即带版本行** ⇒ 3 级矩阵走**既有** `sign-step` ⇒ 矩阵**真的生效**
  （角色 403 / 越步 409 / 自校禁止 403）—— 此前 `approve_change_notice` 直接
  批准 ⇒ 矩阵是**装饰品**。
- **自动关记录**（ADR-0008）：触发点 = `sign_step` 最后一步置 APPROVED 的那一刻
  ⇒ 记录 CHANGED → CHECKED + `change_resolved_by` + 观测 COMPLETED，同一事务。
  ⚠️ 关之前**先确认记录还在 CHANGED**（不许复活已作废的记录 ⇒ 409
  `CHANGE_NOTICE_RECORD_BAD_STATE`）—— 这一条守卫**落在 `cda6e40`**，
  **在本轮评审的 diff 范围之外**（评审器只看到 `9a4f66b`）⇒ 由评审发现
  后补上，不算「评审漏看」。
- 驳回后**不再永久卡死**：`issue` 幂等判据放宽为「有未退回的版本」。
- 工作区门禁：FORMAL 才许建（UI-SPEC §5.3）。

**遗留**：前端无入口（用户裁决只做后端）；变更单编号仍非编号模板（见 TODO-073）。

---

## ✅ DONE —— TODO-069: 「一条记录同时只有一张变更单」是**新增业务约束**（2026-10-26 落地）

**落地**：
- `doc_no` 改用**完整 32 位 hex**（`CN-{uuid.hex}`）⇒ 跨记录撞号归零
  （原取前 8 位 = 32 bit ⇒ 同项目 ~65k 张单即可能撞 `uq_deliverables_doc_no`
  ⇒ 未捕获的 IntegrityError 500）。
- 同记录的第二次建单 ⇒ **409 `CHANGE_NOTICE_ALREADY_EXISTS`**（明说，不是撞约束）。
- 记录↔变更单的关联改走 **`deliverable_record_bindings`**（ADR-0008 明写用它
  替代原 `change_notice_record_bindings`）⇒ 不再靠解析 `scope_value` 字符串；
  `scope_value` 与 binding 由守卫测试钉住一致。

**⚠️ 仍未由 SPEC 确认**（业务口径待裁决）：
1. 「一条记录同时只有一张变更单」这条规则本身仍是**实现推导**出来的
   （doc_no 派生的副产品），SPEC 侧尚未确认 ⇒ 保留本条记录的**裁决请求**。
   ⚠️ **2026-10-26 口径已随 TODO-078 调整**：「一条记录同时只在**一张未关闭**的
   变更单里」（判重按 **binding**，且**已 APPROVED** 的那单不挡新单）——
   多记录变更单落地后，原来的「一张单只绑一条 + 按 scope 判重」已经不成立。
2. ~~**已取消的变更单也会挡住再次建单**~~ ⇒ ✅ **2026-10-26 闭环**：取消路径
   已落地（`POST /records/{module}/{id}/change-notice/cancel` ⇒ 变更单
   `OBSOLETE`）+ 判重口径改为「**开着** = DRAFT / PENDING」⇒ **已作废/已批准
   的单都不挡新单**。⚠️ 「作废时记录怎么办」的口径已定：**记录不动**（保持
   CHANGED）—— 作废的是「单据」，不是「校核结论」。
3. `doc_no` 只是**唯一**，不是可读编号 ⇒ 见 TODO-073。
4. ⚠️ **「第二次变更」的后果**（2026-10-26 评审登记）：记录在 CHANGED 期间
   **不能再发起一轮变更** —— `INITIATE_CHANGE` 的合法前态是 CHECKED
   ⇒ 有未关闭的变更单时再发起 ⇒ 409（状态不对）⇒ **记录卡在 CHANGED**，
   直到那张变更单被签完（自动关记录）才回 CHECKED 才能再发起。
   ⇒ 这是「一条记录同时只有一张变更单」这条约束的**下游后果**，同样待 SPEC
   确认（业务上是否接受「变更单没签完就不能再改」）。

---

## ✅ DONE —— TODO-070: `signature_matrices` **无管理面**（2026-10-26 落地，P9A-DLV-011 T3）

**落地**：6 个端点（`GET/POST /signature-matrices`、`GET/PUT
/signature-matrices/{id}`、`POST /projects/{id}/signature-matrices`、
`DELETE /projects/{id}/signature-matrices/{module}`）+ service CRUD。

**权限分层**（用户 2026-10-26 裁决）：
- 改**模板**（全局表）= **SYSTEM_ADMIN**（项目角色能改 ⇒ 别的项目在用的矩阵
  跟着变）；
- **绑定**项目 = 全局角色 ∈ {DESIGNER, PROCESS_CONTROLLER, SYSTEM_ADMIN}
  + 项目授权（与 `_ISSUE_ROLES` 同形；项目内角色词表无序 ⇒ 不按它分级）。

**遗留**：前端没有矩阵管理页（用户裁决只做后端）；矩阵**名**未加唯一约束
⇒ 并发下可能建出两份同名模板（内容相同，无害）⇒ 见 TODO-074。

---

## ✅ DONE —— TODO-071: `project_signature_matrix_bindings` 缺 (project_id, module) 唯一约束（2026-10-26 落地）

**落地**：迁移 `p9_008`（+ ORM 同步声明）+ `SignatureMatrixService._ensure_binding`
撞约束 ⇒ **SAVEPOINT** 回滚这一段 ⇒ 重读那一行（而不是 500）。

⚠️ SAVEPOINT 而不是裸 catch：PostgreSQL 撞唯一约束会**中止整个事务** ⇒ 裸
catch 会把前面建的矩阵/交付物一起丢。

**验证**：`alembic upgrade head` 在**全新隔离 schema** 上从零跑通（CI 的
api-drift job 跑的就是全新 Postgres）+ `alembic check` 在 `pcs` 与 `pcs_test`
**各跑一次**均 exit 0（两库均到 `p9_008` head）。

**连带**：两个既有测试的 helper 依赖了「同项目同模块两行绑定」这个**非法状态**
⇒ 改成换绑/复用（与生产代码同形）。

---

## ✅ DONE —— TODO-072: `steps_json` **校验器**缺失（2026-10-26 落地，P9A-DLV-011 T3）

**落地**：`SignatureMatrixService.validate_steps` —— **写**路径的严格校验
（任一项非法 ⇒ 422 `SIGNATURE_MATRIX_INVALID`，**不部分入库**；另挡**序号
重复**）。

| | `parse_steps`（读） | `validate_steps`（写） |
|---|---|---|
| 单项坏 | 跳过 + WARNING 日志 | **422** |
| 全坏 | 422 | **422** |

读路径必须容忍**存量脏数据**；写路径必须**挡住坏配置** ⇒ 新写进来的矩阵一定
干净 ⇒ 读路径的「部分跳过」只服务存量。

---

## ✅ DONE —— TODO-073: 变更单编号**可读**（走编号模板）（2026-10-27 落地）

**原症状：** 变更单的 `doc_no` 是 `CN-{变更单自己的 32 位 uuid hex}` ⇒ 它只
保证**唯一**，但它是给用户看的编号 ⇒ 一串 32 位 hex **不可读**、不可口述、不可
检索 ⇒ 用户报「变更单 CN-3F2A…」时谁都对不上。

**落地**

- **内置变更单编号模板**（`NumberingService.get_or_create_change_notice_template`）
  ⇒ 段 = `["project_no", "-", "doc_type", "-", "seq"]` ⇒ 编号渲染成
  **`{项目号}-CHANGE_NOTICE-{序号}`**（如 `P-1A2B3C4D-CHANGE_NOTICE-1`）。
  ⚠️ **幂等**（有就用，没有才建）+ **并发安全**（靠 `template_name` 唯一约束
  兜底 ⇒ 撞约束 ⇒ SAVEPOINT + **重读赢家那一行**，与
  `signature_matrix_service._ensure_binding` 同一套写法）。
- ⚠️ **必须在建行之前取号**：`uq_deliverables_doc_no` 是**全局唯一** ⇒
  「先建行、编号后补」⇒ 同一事务里的第二张变更单两行编号都是空串 ⇒ 撞约束
  ⇒ 500 ⇒ 为此把渲染逻辑从 `_allocate_doc_no`（吃交付物行）里**抽**成
  `DeliverableService.render_doc_no(db, project_id=, template_id=, doc_type=)`
  （不依赖已存在的行）⇒ `_allocate_doc_no` 改为转调它（行为不变）。
- 变更单交付物行 ⇒ `doc_no_mode="TEMPLATE"` + `numbering_template_id` 指向模板
  ⇒ 之后**再签发版本**时 `issue` 会**重新取号**（与其它交付物同一条路）。
- **迁移 `p9_009`**：`numbering_templates.template_name` 加**全局唯一**约束
  （不唯一 ⇒ 并发下两份同名模板 ⇒ **两条独立号段** ⇒ 同一项目里出现两个
  同号的变更单 ⇒ 凭证认不出是哪一张）。
  ⇒ 两库 `pcs` / `pcs_test` 各跑一次 `alembic check` **exit 0**；全新隔离
  schema 从零 `alembic upgrade head` 通过。
- 测试（新增 `tests/services/test_change_notice_numbering.py`，4 例）：编号
  **可读**（含项目号/文档类型/序号）· 序号**递增** · 交付物行**绑了**模板 ·
  模板**幂等**（两张单 ⇒ 同一模板 ⇒ 同一号段 ⇒ 全库只有一份模板）。

**已知取舍：** 编号里含**项目号** ⇒ 项目号改了 ⇒ 历史编号**不变**（编号是
**快照**，不是实时计算）—— 与其它交付物同一口径。

**归属：** 已闭环。**关联：** TODO-069 · ADR-0008（变更单编号模板）· bug-2082。

## ✅ DONE —— TODO-074: 签署矩阵**同名同状态**不许存在两份（2026-10-27 落地）

**原症状：** `signature_matrices.matrix_name` 无唯一约束 ⇒
`SignatureMatrixService._get_or_create_builtin_matrix` 按
`(matrix_name, status='ACTIVE')` **找第一份** ⇒ **并发**下两个事务各建一份
⇒ 同名的 ACTIVE 矩阵有**两份** ⇒ 两个项目可能绑到**不同的一份** ⇒
「谁该签这一步」出现**两个答案**。

**落地**

- **应用层**（友好错误）：`SignatureMatrixService._assert_name_free` ⇒ 建矩阵 /
  改名时若**同名 + 同状态**已存在 ⇒ **409 `SIGNATURE_MATRIX_NAME_CONFLICT`**
  （不是 500）。⚠️ 应用层这一查只挡**顺序**调用；并发窗口靠下面的 DB 约束。
- **DB 约束**（并发兜底）：**迁移 `p9_010`** ⇒
  `uq_signature_matrices_name_status` = **(matrix_name, status)** 唯一。
- ⚠️ **为什么是 `(matrix_name, status)` 而不是「名字全局唯一」**：一份**已作废**
  （OBSOLETE）的同名模板不该**永久堵住**重建 ⇒ 否则作废后再也建不出同名的
  ACTIVE 模板 ⇒ 运维只能改名字 ⇒ 历史绑定里的旧名字全是死链。⇒ 应用层与
  DB 约束**同口径**（同名 + 同状态）。
- 测试（3 例）：建同名矩阵 ⇒ 409 且**只落一行** · 改名成别人已用的名字 ⇒ 409
  且**被拒的改名不许生效** · **同名但不同状态**（ACTIVE + OBSOLETE）⇒ **允许**
  （把约束的形状钉死）。

**归属：** 已闭环。**关联：** TODO-070（矩阵管理面）· bug-2083 · `p9_010`。

## TODO-075: `change_resolved_by` 被写**两次**（语义错位）🟡

**What:** 9 态状态机的 `APPLY_CHANGE`（CHANGE_PENDING → CHANGED）就写了
`change_resolved_at` + `change_resolved_by`；而 ADR-0002 说这两个字段记的是
**变更单的关闭人**（变更单 APPROVED 时才写）。

**Why:** ⇒ 「谁关闭了这次变更」在变更单批准**之前**就有了值（校核完成的人）。
最终值会被关记录那步覆盖（= 批准人）⇒ 落到库里是对的，但**中间态**的语义是错的，
且任何读 `change_resolved_by` 的地方在变更单批准前会拿到「校核人」。

**How:** 把 `APPLY_CHANGE` 写这两个字段的行为去掉（或改名），只由关记录那步写。
⚠️ 动状态机会影响既有测试 ⇒ 独立一轮。**归属：** 独立一轮。

## TODO-076: 工作区类型门禁只覆盖本批端点（全端点仍缺）🟡

**What:** 工作区门禁目前只挂在
`POST /records/{module}/{id}/change-notice` 上。

> ⚠️ **2026-10-26 更名**：本批用的守卫原名 `require_formal_workspace`
> （`app/api/v1/_guard.py`）与 `app/api/deps.py` 里**已存在的同名** FastAPI
> 依赖撞名 ⇒ 已改名 **`require_formal_project_workspace`**（按项目查工作区）。
> 两个函数语义**不同**（见下），撞名会让后面的人 import 错。

**Why:** UI-SPEC §5.3 的门禁清单覆盖**提交批准 / 创建交付物 / 创建变更单 /
签署** ⇒ 其余三类在 API 层**没有**对应守卫（前端有，但「后端 403 为兜底」是
UI-SPEC 自己写的 ⇒ 后端缺 ⇒ 绕过前端就能做）。

**⚠️ 本守卫是 fail-open 的**（`require_formal_project_workspace`）：

| 情况 | 本守卫 | `deps.require_formal_workspace`（fail-closed） |
|---|---|---|
| 项目不存在 / 没挂工作区 | **放行** | 404 |
| 工作区行不存在 | **放行** | 404 |
| 工作区不是 FORMAL | 403 | 403 |

「放行」是**有意的**（历史项目没挂工作区 ⇒ 不是个人草稿区 ⇒ 不该因缺元数据
挡掉正常操作）⇒ 但这是**两条 fail-open 分支**，与「门禁覆盖面」一起登记。

**How:** 把 `require_formal_project_workspace` 挂到其余写端点上（records 的
submit-approval / approval-step / deliverables 的 issue / sign-step），
并补守卫测试；同时把两条 fail-open 分支显式化（要么改 fail-closed，要么写
明「为什么放行」并加测试钉住）。**归属：** 独立一轮。

## ✅ DONE —— TODO-077: `apply-change` 不要求 hash 变化（2026-10-26 落地）

**业务裁决（2026-10-26，用户指令「顺序解决」）**：**强制 hash 变化** ——
推翻计划 R-11 当初「不要求 hash 变化」的取舍。

**理由**：
1. ADR-0002 的 CHANGE_PENDING = 「**获准修改**、正在改+重校核」⇒
   「提交变更完成」= 有变更完成了；
2. 确实无需修改的正确动作是「**放弃变更**」（ABANDON_CHANGE → CHECKED），
   不是提交完成；
3. 不拦 ⇒ 可「发起变更 → 什么都不改 → 提交变更完成 → 变更单签完」⇒ 一条
   **没有实质变更**的记录被关掉，而变更单里写着「管径修正」⇒ 凭证说的不是
   事实（ADR-0002「防止无声修改」被架空）。

**落地**：
- `StateMachineService._assert_change_modified`：**APPLY_CHANGE 的业务前置**
  （与角色/状态校验同层 ⇒ 任何调用方都躲不掉）—— 判据 = 记录当前
  `record_hash` vs **最新 ACTIVE 的 BEFORE_CHANGE 快照**哈希 ⇒ 相同 ⇒ 抛
  `NoModification`。放在**迁移之前** ⇒ 被拒时一行都没写。
- 端点映射：⇒ **409 `CHANGE_NO_MODIFICATION`**（并提示「若确实无需修改，请改用
  「放弃变更」」）。不映射会落到 500 兜底 —— 而这是用户「忘了改数据」的
  **正常结果**，不是系统故障。
- ⚠️ **两种「无从判断」⇒ 放行**：记录**没有** `record_hash` 列、或哈希是**空串**
  （物流 streams 的 `record_hash` 恒为 "" ⇒ 没有可比的东西）⇒ 不因缺元数据把
  正常操作挡掉。
- 测试（RED→GREEN）：`test_apply_change_requires_an_actual_modification`
  （没改 ⇒ 409 且状态不变）+ `test_apply_change_allows_a_modified_record`
  （改过 ⇒ 200）。

**⚠️ 已知代价**：「重新校核后确认无需修改」的场景现在会被 409 挡住（可改用
「放弃变更」）—— 这是**有意的**：那条路会留下「变更完成」的假凭证。

**关联：** ADR-0002 · 计划 R-11′（推翻 R-11）· TODO-078 · TODO-087。

## ✅ DONE —— TODO-078: 变更单只绑**一条**记录（多记录变更未支持）（2026-10-26 落地）

**落地**：
- 建单请求体加 **`record_ids: list[uuid] | None`** = 本次变更影响的**全部**记录
  —— **必须包含**路径里的 `{record_id}`（否则 422
  `CHANGE_NOTICE_RECORD_SET_INVALID`）；不给 = 只有路径那条（**向后兼容**）。
- `deliverable_record_bindings` **每条记录一行** ⇒ 关闭时**批量**关
  （`close_on_approved` 逐条关，任一条不合格 ⇒ **整批失败**（事务回滚 ⇒ 一条
  都不关）—— 半关半不关 = 一张单关了两条而另一条还开着）。
- ⚠️ 「重复绑定」判重改按 **binding** 找（不再按 `scope_value`）：多记录变更单
  的 scope 只标识**主记录** ⇒ 次要记录在 scope 里查不到 ⇒ 必须按 binding 查。
- ⚠️ 「未关闭」= 交付物**不是** `APPROVED`（已批准的那张**已经关过记录**了 ⇒
  不该再挡住新变更单）。
- 返回值**向后兼容**（单记录时与旧版逐字一致）+ 新增 `closed_records`（全部）。
- 测试（3 例）：`test_change_notice_can_bind_multiple_records`（两行 binding ⇒
  签完两条都回 CHECKED）· `test_change_notice_record_set_must_contain_the_path_record`
  （集合不含路径记录 ⇒ 422）· `test_a_record_cannot_be_in_two_open_change_notices`
  （一条记录不能同时在两张**未关闭**的变更单里 ⇒ 409）。

**⚠️ 契约影响**：`ChangeNoticeRequest` 加 `record_ids` 字段 ⇒ OpenAPI
**schemas 数不变**（346→347 是上一批的 `ChangeActionRequest`；本批只加**字段**）、
paths 246 不变 ⇒ `openapi.json` / baseline / 前端 snapshot + `api.d.ts`
**已重新生成并滚 baseline**；裸字段仍 **71**。

**关联：** TODO-069（「一条记录一张变更单」规则已随本条调整为「同时只在**一张
未关闭**的变更单里」）· ADR-0002 · TODO-077。

## ✅ DONE —— TODO-079: 矩阵管理面**没有前端**（2026-10-26 落地）

**落地**（P9A-DLV-011 收尾批）：
- 新页 `src/pages/deliverables/SignatureMatrixPage.tsx`（路由
  `/deliverables/signature-matrices`，菜单「交付物 → 签署矩阵」）：
  矩阵列表（名称 / 模块 / 文档类型 / 版本目的 / 状态 / **签署步骤序列**）+
  新建 / 编辑（**动态步骤编辑器**：序号 / 签署角色 / 必签 / 可自校 / 可跳过）+
  **绑定到当前项目**（项目 × 模块 → 矩阵）+ 解绑。
- API 客户端 `src/api/signatureMatrices.ts`（类型**全部**取生成的 OpenAPI 类型）。
- MSW handlers `src/mocks/signatureMatrices.ts`（**有状态**：建/改/绑/解绑真的改
  内存态 ⇒ 人工验收能看出变化）。
- 测试：`tests/api/signature_matrices_api.test.ts`（请求契约 5 例）+
  `tests/pages/deliverables/signature_matrix_page.test.tsx`（渲染 / 步骤显示 /
  错误条 3 例）。

**为什么现在做**：用户 2026-10-26 裁决「只有项目负责人能绑」⇒ 绑定成了**治理
动作** ⇒ 没有界面就等于「只有 curl 能治理」⇒ 本批补上。

## ✅ DONE —— TODO-080: P9A-DLV-007 评审的 **3 条 deferred minor**（2026-10-26 全部落地）

| # | 事项 | 落地 |
|---|---|---|
| 1 | 「同记录已有变更单 ⇒ 409」**不区分已取消** | ✅ **补上取消路径**（见下）+ 判重口径改为「**开着** = DRAFT / PENDING」（已 APPROVED / 已 OBSOLETE 都**不挡**新单）⇒ `_find_open_notice_for_record` 与 `refresh_open_bindings` **同一口径** |
| 2 | approve 用例用假 Session ⇒ **零覆盖** | ✅ **删掉**已弃用的 `approve_change_notice`（它**连记录都不关** ⇒ 用了它记录永远停在 CHANGED）+ 连带删掉**死代码** `_apply_record_resolution` ⇒ 该文件**再无假 Session**（`_FakeSession` + 假模型全删）⇒ 真覆盖搬到新文件 `tests/services/test_change_notice_close_real_db.py`（4 例，真库） |
| 3 | 两个 `PcsError` 变体互捕不到 | ✅ service 变体**继承** core 变体（`app/services/exceptions.py::PcsError(CorePcsError)`）⇒ `except core.PcsError` **两个都捕得到**；⚠️ 为此把 `app/core/errors.py` 里对 service 变体的 import 改成**惰性**（否则 core → services → core 成环 ⇒ 启动即 ImportError） |

### 顺带落地：**取消路径**（用户指令里点名的「变更单没有取消路径」）

- 新端点 `POST /records/{module}/{record_id}/change-notice/cancel`（理由必填）⇒
  变更单 `sign_status = OBSOLETE`（交付物 4 态里**已有**这一态 ⇒ **不需要迁移**）
  + 审计 `CHANGE_NOTICE_CANCELLED` + 观测 FAILED（与签署被退回同口径）。
- ⚠️ **记录不动**（保持 CHANGED）：作废的是「单据」，不是「校核结论」⇒ 顺手把
  记录关成 CHECKED = **绕过 3 级校审** ⇒ 不做。
- ⇒ 作废后该记录**可以另起一张**（作废的单不挡新单）。
- ⚠️ **前端没有「作废变更单」按钮** —— 本批只做后端能力（端点 + 语义 + 观测）。
  ⇒ 前端接线属 **TODO-083 的后续**（变更单前端入口那批已闭环 ⇒ 这里补一个按钮
  即可：结果记录行 → 变更动作区加「作废变更单」）。
- ⚠️ 为此 **`doc_no` 与 `scope_value` 改为按「变更单自己的 uuid」派生**
  （原先按记录派生 ⇒ 同一记录的第二张单会撞 `uq_deliverables_doc_no` /
  `uq_deliverables_scope` ⇒ 未捕获的 IntegrityError 500）；scope 仍**以记录身份
  开头**（`CHANGE_NOTICE:{表名}:{记录ID}:{单号后缀}` ⇒ 与 binding 一致，由守卫
  测试钉住）。

### 顺带落地：**真实路径的通知**（原先真实路径**不通知任何人**）

审批通过的通知逻辑原先在**已弃用**的 `approve_change_notice` 里 ⇒ 真实路径
（`sign_step` → `close_on_approved`）**从不通知** ⇒ 用户不知道「变更被批准了」。
⇒ 随该方法删除，通知**迁到** `close_on_approved`（通知行**同一事务**写，推送由
`sign_step` 在 commit **之后**做 —— 与 `_notify_sign_outcome` 同一批推）。

**归属：** 已闭环。**关联：** P9A-DLV-007 评审 ledger
`.superpowers/sdd/PCS-PLAN-P9A-DLV-007-签署矩阵与变更单观测/progress.md`。

## ✅ DONE —— TODO-081: `approve_change_notice` 是**绕过矩阵的第二条关闭路径**（2026-10-26 落地）

**落地**：**选项① —— 删掉** `ChangeNoticeService.approve_change_notice`
（连带删掉**死代码** `_apply_record_resolution` —— `approve_change_notice`
其实**连记录都不关**（`record_transition` 恒为 None）⇒ 用了它，记录**永远
停在 CHANGED**）。

⇒ 现在**唯一**的关闭路径 = 签署流程的终点（`sign_step` 最后一步 ⇒
`close_on_approved`）⇒ 矩阵**不可能**被绕过（bug-2058 的根因消除）。
审批通过的通知逻辑**一并迁到**这条真实路径（原先真实路径**不通知任何人**）。

**测试**：该文件**再无假 Session** ⇒ 真覆盖搬到
`tests/services/test_change_notice_close_real_db.py`（4 例，真库）+
`tests/api/v1/test_change_notice_api.py`（端到端）。

**归属：** 已闭环。**关联：** bug-2058 · TODO-080。

## TODO-088: 全新隔离 schema 上跑迁移会**漏建** 6 条约束（幂等检查**只按名字**查）🟡

**What:** 在**隔离 schema**（`options=-csearch_path=<schema>`）上从零跑
`alembic upgrade head` ⇒ 建出来的 schema **缺** 6 条 ORM 声明的约束：

| 约束 | 表 |
|---|---|
| `future_dated_forbidden_chk` | `project_calculation_standard_profiles` |
| `uq_report_definitions_project_name` | `report_definitions` |
| `uq_report_styles_scope_version` | `report_styles` |
| `ck_streams_data_mode` / `ck_streams_phase` / `ck_streams_source_type` | `streams` |

⇒ 在那个隔离 schema 上跑 `alembic check` ⇒ **exit 255 + 6 条「add_constraint」**
⇒ 看着像「ORM 与迁移漂移」，其实**不是**。

**Why（根因）：** `p8_001` / `p8_008` / `p8_009` 的幂等检查写成
`SELECT 1 FROM pg_constraint WHERE conname = '<名字>'` ⇒ **`pg_constraint`
是「每库」不是「每 schema」** ⇒ 同一个库里**别的 schema**（例如 `public`）
已有同名列 ⇒ **跳过建约束** ⇒ 隔离 schema 永远拿不到这 6 条。
⚠️ **真·全新数据库**（CI 的 fresh Postgres）里没有别的 schema ⇒ 约束**会**建出来
⇒ CI 不受影响 ⇒ 只有**本地用隔离 schema 验证**时会看到这 6 条假漂移。

**How:** ①把那 3 条迁移的幂等检查改成**按 schema 过滤**
（`connamespace = to_regnamespace(current_schema())`）；②或本地验证时**逐条对照**
这 6 个约束是否存在，别把 `alembic check` 的 exit 255 当成真漂移。

⚠️ **别照字面「修」**：CLAUDE.md 写明过「`remove_constraint` 的字面意思与正确处置
**恰好相反** —— 实测那些条全是「DB 有安全网、ORM 漏声明」⇒ 照字面删会把 DB 保护
删掉」。这 6 条**反过来**（ORM 声明了、隔离 schema 没有）⇒ 照字面「加」会写出一条
**重复**的迁移。

**归属：** 独立一轮（要改 3 条既有迁移的幂等检查 ⇒ 改历史迁移要谨慎）。
**关联：** CLAUDE.md「测试前检查 · 漂移盲区」· bug-147 · `p8_008`。

## TODO-082: `locked_by_deliverable` 门是**死代码**（永远 False）🟡

**What:** `records.locked_by_deliverable` 全仓**只被读，从未被写 True**。

**Why:** 两个服务把它当门禁用：
- `record_cancellation_service.py:168` —— 「已绑定记录（`locked_by_deliverable=True`）
  必须先建 `change_type=RECORD_CANCELLATION` 的变更单才能作废」；
- `reversal_approval_service.py:156` —— 「已对外生效的记录只能走
  `CHANGE_REVERSAL`，不能走普通变更」。

⇒ 但**没有任何代码把它置 True** ⇒ 两道门**永远不触发** ⇒
「记录作废前必须有变更单凭证」这条业务约束**事实上不存在**。
⚠️ 本批（P9A-DLV-011）补的变更单闭环**也没写它** ⇒ 变更单签完只关记录，
不把记录标成「已对外生效」。

**How:** 二选一 —— ①在「变更单被签完 / 交付物发布」时把绑定的记录
`locked_by_deliverable` 置 True（+ 迁移确认该列在全部记录表上都有）；
②删掉这两道门（承认「变更单不参与作废/反转的准入判断」）。
⇒ 选 ① 要连带确认「记录表清单」与「哪些交付物算对外生效」⇒ 独立一轮。

**归属：** 独立一轮。**关联：** TODO-069 · TODO-078。

## ✅ DONE —— TODO-083: 变更单闭环**没有前端入口**（2026-10-26 落地）

**落地**（P9A-DLV-011 收尾批）：
- 结果记录页（P9B-1 的 `ResultListPage`）每行新增**变更动作**
  `src/pages/results/ChangeNoticeAction.tsx`：**按 `sign_status` 只给一个按钮**
  —— CHECKED → 「变更申请」（initiate-change）/ CHANGE_PENDING → 「提交变更完成」
  （apply-change）/ CHANGED → 「创建变更单」（change-notice）⇒ 三个端点是**一条
  状态机**，同时显示三个按钮 = 让用户去撞 409。
- 建变更单的弹窗带**变更类型**（7 值 + 中文标签）+ 变更原因。
- 成功后**就地更新行状态**（不重拉列表）⇒ 按钮不会停在旧状态让人连点两次。
- API 客户端 `src/api/changeNotices.ts` + MSW handlers
  `src/mocks/changeNotices.ts`（**状态机真的走**：状态不对 ⇒ 409）。
- 测试：`tests/api/change_notices_api.test.ts`（3 例）+
  `tests/pages/results/change_notice_action.test.tsx`（4 例）。

⚠️ **顺带更正 UI-SPEC §6.3 的登记**：本批第一次登记写成「『变更申请』按钮应挂到
CHANGED 态」—— **错了**（把「变更申请 = 建变更单」搞混）。真相：UI-SPEC 表的
三个按钮与后端三个端点**一一对应**（「关闭凭证」= 建变更单）⇒ **表不用改**，
只有措辞（「提交变更批准」→ 前端用「提交变更完成」）登记待修订。

**关联：** TODO-079 · TODO-068 · UI-SPEC §6.3。

## ✅ DONE —— TODO-084: P9A-DLV-011 评审的 **5 条 deferred minor**（2026-10-26 全部落地）

| # | 事项 | 落地 |
|---|---|---|
| 1 | 变更单响应里的 `sign_status` 是**硬编码**的 `PENDING` | ✅ service 从交付物**行**读出真值并返回，端点用它（`sign_status=result["sign_status"]`）⇒ 端点**不再**自己编一个常量。测试用 monkeypatch 制造「版本行建了但没推进」⇒ 响应必须说 DRAFT |
| 2 | service 层**不校验** `project_id` 与记录所属项目一致 | ✅ `create_change_notice` 自查：`record.project_id != project_id` ⇒ 422 `CHANGE_NOTICE_PROJECT_MISMATCH`，**且一行都不写**（真库用例 `tests/services/test_change_notice_project_guard.py`） |
| 3 | 矩阵**全部非法**时待办**静默消失**且**一条日志都没有** | ✅ `todo_service` 加 `logger` + `except PcsError` 分支记 **error**（带 deliverable_id / matrix_id / code）⇒ 「这个交付物没人能签」不再不可见。断言加在既有用例 `test_todo_skips_matrix_with_all_invalid_steps` 上（caplog） |
| 4 | ~~ADR-0002 与 ADR-0008 在「驳回」上矛盾~~ | ✅ **已裁决**（上一轮）：ADR-0008 管辖；两份 ADR 加修订记录；「重改」路径由 `test_rejected_notice_can_be_reworked_via_reversal` 钉住 |
| 5 | `initiate-change` / `apply-change` 复用 `ObsoleteRequest` | ✅ 新增 **`ChangeActionRequest`**（字段与约束**与 `ObsoleteRequest` 完全相同** ⇒ **纯改名**，请求体形状/校验/行为零变化），三个变更动作端点（initiate / apply / abandon）改用它；`obsolete` 端点**仍用** `ObsoleteRequest`。契约测试 `tests/architecture/test_change_request_schema.py` 钉住（**含反向对照**） |

**契约影响**：OpenAPI **346 → 347 schemas**（+1 = `ChangeActionRequest`），
paths 不变（246）⇒ `openapi.json` / `openapi-baseline.json` /
前端 `openapi.snapshot.json` + `src/types/api.d.ts` **已重新生成并滚动 baseline**；
裸字段仍 **71**（未上涨）。

**验收**：后端 `pytest -q`（见提交信息）· 前端 typecheck / lint exit 0、
`vitest run` **835 passed / 90 files / 0 failed**（类型重新生成后无回归）·
G-08 契约门禁 4 阶段 exit 0。

**关联：** 评审 ledger `.superpowers/sdd/PCS-PLAN-P9A-DLV-011-变更单闭环与签署矩阵管理面/progress.md`
的「Deferred minors」段。

## TODO-085: 改签署矩阵的**申请 + 双重审批**未实现（校审层级 SPEC 的规则）🟡

**What:** `spec/校审层级可配置化增补规格说明书.md` §2.3 写明：「项目进行中：
修改签署矩阵需**项目负责人提出申请，审核+审定双重审批**」。本批只落了
**「只有项目负责人能绑」这一层**（用户 2026-10-26 裁决），**没有**「申请 →
审核 → 审定」的流程。

**Why:** 直接改 = 改了矩阵立刻生效 ⇒ 与 SPEC 的「双重审批」不符。

**How:** ①把「绑定/解绑」改成「**提交变更申请**」（写一条申请行，状态
DRAFT → 审核 → 审定 → 才真正改绑定）；②或先明确「矩阵修改走审批」是否
**本项目要**（PCS 的矩阵多数是全局模板 + 项目绑定，项目级覆写少 ⇒ 流程
成本可能大于收益）。⇒ **需业务裁决**，不自行发明流程。

**归属：** 独立一轮。**关联：** TODO-070 · `spec/校审层级可配置化增补规格说明书.md`。

## ✅ DONE —— TODO-086: 重走变更后，变更单的**绑定哈希**不再等于记录当前哈希（2026-10-26 落地）

**落地**：
- `ChangeNoticeService.refresh_open_bindings(...)`：把该记录名下**未关闭**
  （deliverable `sign_status != APPROVED`）的变更单绑定刷新成
  `record_hash` = 记录**当前**哈希、
  `old_record_hash_before_change` = **本次** BEFORE_CHANGE 快照哈希
  （与建单时**同一口径** ⇒ 复用 `_pre_change_hash`）。
- 调用点 = `records_actions.apply_change`（CHANGE_PENDING → CHANGED，记录
  **再次**变 CHANGED 的唯一入口）⇒ 与状态迁移**同一事务**。
- ⚠️ **只刷「未关闭」的** —— 已 APPROVED 的变更单**已经关过记录**了 ⇒ 它的
  绑定描述的是**那一轮**的哈希 ⇒ 改它 = 篡改历史。
- 审计：新增 `AuditAction.CHANGE_NOTICE_BINDING_REFRESHED`（`String(50)` 列
  ⇒ 零迁移成本）。
- 测试（2 条）：`test_rework_refreshes_the_open_notice_binding_hashes`
  （返工 ⇒ 绑定刷新成 `h2-after-rework` + 旧哈希是**本次**快照的 `h1`）·
  `test_closed_notice_binding_is_not_rewritten`（已关闭的绑定不许被改写）。

**Why:** 变更单的**全部价值**就是「谁、为什么、凭什么关闭」—— 哈希对不上，
凭证就不可信。而 `close_on_approved` 今天**不校验**哈希（与 TODO-077 同源）
⇒ 漂移**无人发现**。

**关联：** TODO-077 · ADR-0002 修订记录 · **TODO-087**（本批顺带发现）。

## ✅ DONE —— TODO-087: 撤销/放弃**真的恢复**记录的数据与哈希（快照不再恒空）（2026-10-26）

**原症状：** `RecordChangeSnapshot.data_snapshot_json` **恒为 `{}`** ——
`state_machine._create_snapshot` 写的是空 dict，**全仓没有任何代码往里放数据**
⇒ `_restore_snapshot`（state_machine）与 `ReversalApprovalService._restore_snapshot`
的恢复循环**空转** ⇒ **撤销批准只回状态，不回数据**。

**为什么它是「撤销」的命门：** 撤销（APPROVE_REVERSAL）的语义是「这次变更作废，
记录回到变更前」⇒ 记录带着**改动过的数据**回到 CHECKED ⇒ 「已生效的记录被撤销」
之后数据其实**还在** ⇒ 撤销**没有撤销任何东西**。
⚠️ 这也是 TODO-086「返工」路径的隐性依赖：返工之所以成立，是因为**第二次**
CHANGE_PENDING 里又改了一遍数据，**不是**因为撤销恢复了数据。

### 落地

- 新模块 **`app/services/record_snapshot_codec.py`**（快照的**编解码**）：
  - `capture_record_data(record)` ⇒ 采集记录的业务数据（JSONB 装不下的
    **UUID / datetime / date / Decimal / Enum** **打标签**：`{"__t__": …, "v": …}`）；
  - `apply_snapshot_data(record, data)` ⇒ 按标签**还原成真类型**（枚举按列类型的
    `enum_class` 还原成**成员** —— 裸字符串绑枚举列会 LookupError）；
  - `record_pk(record)` ⇒ **按 mapper 取主键**（各表 PK 列名不同）。
- `state_machine._create_snapshot_if_needed` ⇒ 快照**真的装数据**；
  `_restore_snapshot_if_needed` ⇒ 用 codec 还原。
- ⚠️ **不**快照**主键 / 归属（`project_id`/`workspace_id`）/ 审计 / 状态机流程列**
  （`sign_status` / `approval_*` / `change_*` / `obsoleted_*` / `reversal_*` /
  `stale_*` / `locked_by_deliverable`）—— 它们由**转移本身**维护，恢复它们会与
  「当前处于哪个状态」打架；**但快照 `record_hash`**（它是「变更前的数据指纹」，
  TODO-077 的判据要比它）。
- ⚠️ **顺带修 PK 取法**：`ReversalApprovalService._load_active_snapshot` 此前用
  `getattr(record, "record_id", None)` ⇒ **只有部分表的 PK 叫 `record_id`**
  （`relief_results` 叫 `relief_id`、`streams` 叫 `stream_id`…）⇒ 在别的表上
  **恒为 None** ⇒ 快照永远查不到 ⇒ 撤销**什么都不恢复**。

### 测试（RED → GREEN）

- `tests/services/test_record_snapshot_codec.py`（**新增**，8 例）：采集业务列 ·
  不采主键/归属/状态列 · 类型打标签 · 还原回**真类型** · 未知列跳过 ·
  `record_pk` 取真主键 · **JSONB 落库再读回**数据还在。
- `tests/api/v1/test_change_notice_api.py`：xfail 用例
  `test_reversal_actually_restores_the_record_data` **摘掉 xfail 转绿**；
  新增 `test_initiate_change_snapshot_carries_the_record_data`（快照里有数据）
  与 `test_abandon_change_restores_the_record_data`（**放弃变更**也真恢复）。

**归属：** 已闭环。**关联：** TODO-086 · ADR-0002 §修订记录 · ADR-0024
（「撤销或放弃时回滚」的承诺**已兑现**）· bug-2070。
