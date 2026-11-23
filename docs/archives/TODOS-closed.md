# TODOS 归档 —— **已关闭**的条目（正文逐字保留）

> **这是 `TODOS.md` 的归档**（2026-11-23 瘦身时搬出来的）⇒ ⇒ **正文里只留还开着的条目**。
> ⚠️ **编号是追溯索引** ⇒ ⇒ 任何地方说「见 TODO-xxx」都能在这里找到原文。
> ⇒ ⇒ 新条目请写进 `TODOS.md`；**关闭**时把它搬回这里（并在 `TODOS.md` 文末的「已关闭」表里加一行）。
>
> ⚠️ **搬动造成的指向变化**：条目正文里若写「详见**本文件末尾**的 X」⇒ ⇒ 那句话原本指的是 `TODOS.md` ⇒ ⇒ 现在 X 可能留在 `TODOS.md` 里（例如「F4-PRE 裁决表」）⇒ ⇒ **以 `TODOS.md` 为准**。

## 索引

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

---

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

## ✅ DONE —— TODO-054: 记录侧「多级批准」的角色链无定义来源（2026-10-27 落地，P9B-2 · T2）

**落地**（P9B-2 · T2 · commit `678cc7b`，R-17）：

- **定义源 = 项目绑定的 `module='RECORD'` 签署矩阵**（数据模型已有该槽位 +
  绑定 API + 管理 UI ⇒ 零新增配置面；且与交付物签署链**同一套矩阵** = 一份真相）。
  ⇒ `POST /records/{module}/{id}/submit-approval` 改为**推导**：
  - `approval_role` = 链的第 1 步角色；`approval_depth` = 链的**总步数**；
  - `approval_step` 随推进前进（`_next_approval_role()`）。
- ⚠️ **契约破坏性变更**：请求体**不再收** `approval_role` / `approval_depth`
  ⇒ `SubmitApprovalRequest` 加 `extra="forbid"` ⇒ 多传旧字段 ⇒ **422**
  （静默忽略会让调用方以为自己传了角色，实际生效的是矩阵里的角色 ⇒
  「我明明选了 APPROVER」却吃 403）。
- ⚠️ **没绑矩阵** ⇒ 422 `RECORD_APPROVAL_MATRIX_NOT_BOUND`。
- ⚠️ **自审判据** = 提交人自己的角色出现在链里**任何一步**（不只挡第 1 步 ⇒
  不留「在第 2 步自己批自己」的洞）⇒ 403 `APPROVAL_SELF_REVIEW_FORBIDDEN`。
- ⚠️ `TRANSITION_ROLES[PASS_CHECK]` / `[REJECT_CHECK]` **补 REVIEWER** ——
  内置记录级矩阵第 2 步就是 REVIEWER，不加则第 2 步**谁也批不了**（403）。
  粗闸**不是**最终判据：端点仍要求 `actor.role == record.approval_role`。
- 前端同批改（T4）：**送审角色选择器消失** ⇒ 操作栏不再让用户选角色；
  「矩阵第 1 步角色 == 当前用户」⇒ 送审**禁用 + 说明**（不能自己送自己审）。

⚠️ `project_templates.record_approval_config` 现在**无消费方** ⇒ 建议后续删
（另议，本批只登记）。

**关联：** TODO-053 · ADR-0047 · P9B-2 · T2 / R-17

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

## ✅ DONE —— TODO-065: `GET /deliverables/{id}/progress` 聚合端点（2026-10-27 落地，P9B-2 · T0）

**落地**（P9B-2 · T0 · commit `f646b48`）：

- `GET /api/v1/deliverables/{deliverable_id}/progress` ⇒ 一次返回**两类**工作流的
  进度，每段带 `available` + `reason`（不可用时**说原因**，不返空数组冒充
  「这条流程一个节点都没有」）。
- ⚠️ **口径修订**（R-2 / R-13）—— 原表里的 `CHANGE_NOTICE` 行**删掉**，
  `CUSTOMER_APPROVAL_PROXY` 的 `workflow_id` 也**不是**版本 id：

| 工作流 | workflow_id | 说明 |
|---|---|---|
| `SIGN` | **版本 ID** | 版本行 id（`current_version_id`） |
| `CUSTOMER_APPROVAL_PROXY` | **交付物 ID** | 代录挂在交付物上，不是版本上 |
| ~~`CHANGE_NOTICE`~~ | — | **删**（R-13）：变更单**本身就是交付物**（`deliverable_type=CHANGE_NOTICE`）⇒ 它在进度页上自己一行、自有 SIGN 进度；而 `Deliverable.parent_deliverable_id` 全仓从未被写 ⇒ 靠它反查**永远查不到** ⇒ 留着一个**永远为假**的段比没有更坏（该列已由 T-2 的迁移 `p9_012` 删除） |

- ⚠️ **一条批量查询**（R-16）而不是「每段各查一次」⇒ 实测 **3 条 SELECT**
  （取交付物 1 + 取当前版本 1 + 批量取观测行 1）；测试里钉了「SELECT ≤ 5」的守卫。
- 前端接线（P9B-2 · T6 · commit `7fe7e29`）：`WorkflowProgressPanel` 加**受控
  模式**（传 `data` 就不自己拉）⇒ 展开一行 = **1 个**聚合请求（不是 1 + 每段 1 个）。
- **浏览器实测**（2026-10-27 QA 报告）：展开一行 ⇒ 网络面板看到
  `GET /api/v1/deliverables/d-2/progress`（**不是** `workflow-progress/SIGN/...`）
  ⇒ 两段都在；不可用段显示 `reason` 原文「尚未签发版本，无签署流程」。

**关联：** `docs/PCS-PLAN-P9B-2-签署流程与ADMIN前端.md` · T0 · ADR-0047 ·
QA 报告 `.gstack/qa-reports/qa-report-pcs-frontend-2026-10-27-p9b-2.md`

## ✅ DONE —— TODO-066: 编辑审计缺**按项目守卫**的读端点（2026-10-27 落地，P9B-2 · T1）

**落地**（P9B-2 · T1 · commit `c68bbf0`）：

- `GET /api/v1/records/{module}/{record_id}/edits` ⇒ 只回 `changed_fields`
  **字段名列表** + 操作人 + 时间（**不**回值 ⇒ 差异页不泄漏整行数据）。
- ⚠️ **按项目守卫**：越权 ⇒ **404**（不是 403）⇒ 不泄漏「这条记录存在」。
- ⚠️ 只回 `action=RECORD_EDITED` 的审计行（其余动作不进差异视图）。
- 前端接线（R-14）：409 弹窗的「查看差异」**改打新端点** ⇒ **普通用户点得开**
  （此前打 SYSTEM_ADMIN-only 的 `/audit-logs` ⇒ 普通 DESIGNER 拿到弹窗却
  点不开差异 ⇒ 弹窗的第二个出口形同虚设）。
  ⇒ 连带删掉 `api/audit.ts` 里与 `auditApi.listAuditLogs` **完全重复**的
  `listRecordEdits`（TODO-067 #6 一并闭环）。
- **差异视图的 `changed_fields` 在顶层**（不是 `detail_json` 里）⇒ 后端摊平。

**关联：** SPEC §6.21 P9A-LCK-006 · ADR-0048 §⑦ · P9B-2 · T1 / R-14

## ✅ DONE —— TODO-067: P9B-1 最终评审的 **7 条 deferred minor**（2026-10-27 全部闭环，P9B-2 · T9）

**逐条闭环**（每条 = 一个测试 + 一次改动）：

| # | 事项 | 改法 | 落点 |
|---|---|---|---|
| 1 | 「联系管理员」按钮在生产里是**死的** | `basis=no_baseline` 时**不渲染**死按钮 ⇒ 改成一条**真实**出路（提示「请联系管理员补齐该记录的并发基线后重试」） | T1 · `EditConflictModal.tsx`（commit `c68bbf0`） |
| 2 | `editableFields` 漏字段 ⇒ 静默从表单消失 | 加**守卫测试**「`editableFields ⊆ columns`」（漏了 ⇒ 变红） | T4 · `resultModules.ts`（commit `bb123bb`） |
| 3 | 降级横幅成功后**不消失**（`onDegraded(null)` 从不被调） | 取锁成功 / 续期成功 ⇒ `onDegraded(null)` | T9 #3 · `useEditLock.ts`（commit `6b0db55`） |
| 4 | `enabled` 翻 false 时状态不复位 | `enabled` 变 false ⇒ 状态复位 `idle`（换记录不再短暂显示上一条的「他人正在编辑」） | T9 #4 · `useEditLock.ts`（commit `012dd04`） |
| 5 | 卸载释放的路径硬编码 `/api/v1/locks/...` | 前缀取 `api.defaults.baseURL`（与 axios 实例同源 ⇒ 只有一处真相） | T9 #5 · `ResultEditDrawer.tsx`（commit `d9c2548`） |
| 6 | `api/audit.ts::listRecordEdits` 与 `auditApi.listAuditLogs` 完全重复 | **删**（R-14 切到新端点时一并做） | T1 · `api/audit.ts`（commit `c68bbf0`） |
| 7 | `WorkflowProgressPanel` 把 403 / 404 / 网络错误映射成同一句 | 三种**分开**：403「无权查看该工作流的进度」/ 404「该工作流不存在」/ 网络 ⇒ 宿主给的 `errorDescription` | T6 · `WorkflowProgressPanel.tsx`（commit `7fe7e29`） |

⚠️ **#3 的边界**：降级态**不续期**（续期失败会把「放行」变成只读 ⇒ 反而阻断
编辑）⇒ 降级持续期间横幅只能靠**重新取锁**（重开抽屉）消失。

**关联：** P9B-1 最终评审 ledger
`.superpowers/sdd/PCS-PLAN-P9B-1-结果记录页与编辑锁/progress.md`

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

## ✅ DONE —— TODO-075: `change_resolved_by` 只由「关记录」那步写（2026-10-27 落地）

**原症状：** 9 态状态机的 `APPLY_CHANGE`（CHANGE_PENDING → CHANGED）就写了
`change_resolved_at` + `change_resolved_by`；而 ADR-0002 说这两个字段记的是
**变更单的关闭人**（「可追溯的关闭凭证（**谁**、为什么、凭什么关闭）」）⇒ 写它
们的是**关记录那步**（变更单 APPROVED ⇒ `close_on_approved`），不是「校核完成」
那步。

⇒ 「谁关闭了这次变更」在变更单批准**之前**就有了值（= 校核人）⇒ 最终值会被
关记录那步覆盖（= 批准人）⇒ 落到库里是对的，但**中间态**的语义是错的，且任何
读 `change_resolved_by` 的地方在变更单批准前会拿到「校核人」。

**落地**

- `state_machine.transition`：**APPLY_CHANGE 不再写** `change_resolved_at` /
  `change_resolved_by` ⇒ 只有 `ChangeNoticeService.close_on_approved`（变更单
  APPROVED ⇒ 自动关记录）写 ⇒ 字段语义与 ADR-0002 / ADR-0008 **对齐**。
- ⚠️ **连带影响**：记录在 CHANGED（= 等关闭凭证）阶段，这两个字段是**空的**
  ⇒ 任何「变更已关闭」的查询在凭证批准前**查不到**（这是**正确**的：那时
  变更确实还没关闭）。
- 测试：既有 `tests/services/test_stream_transition.py` 的断言**前提已变**
  （原来断言「APPLY_CHANGE 写这两个字段」）⇒ 改成断言它们**仍是空的**；
  新增流程级用例 `test_change_resolved_by_is_written_only_when_the_notice_is_approved`
  （APPLY_CHANGE 后为空 → 签完最后一步才写）。

**归属：** 已闭环。**关联：** ADR-0002（关闭凭证的「谁」）· ADR-0008
（APPROVED ⇒ 系统自动关记录并写 `change_resolved_by`）· TODO-069。

## ✅ DONE —— TODO-076: 工作区类型门禁覆盖 UI-SPEC §5.3 的**全部**四类操作（2026-10-27 落地）

**原症状：** 工作区门禁（`require_formal_project_workspace`）只挂在
`POST /records/{module}/{id}/change-notice` 一个端点上 ⇒ UI-SPEC §5.3 的门禁
清单里的其余三类（**提交批准 / 创建交付物 / 签署**）在 API 层**没有**对应守卫
⇒ 「后端 403 为兜底」（UI-SPEC 自己写的）落空 ⇒ **绕过前端就能做**。

### 落地

- 门禁挂到 UI-SPEC §5.3 的**全部**四类操作：

| 操作 | 端点 |
|---|---|
| 提交批准 | `POST /records/{module}/{id}/submit-approval` · `/approval-step` |
| 创建交付物 | `POST /deliverables/{id}/issue` |
| 创建变更单 | `POST /records/{module}/{id}/change-notice`（原有） |
| 签署 | `POST /deliverables/{id}/sign-step` · `/customer-approval/proxy` |

  ⇒ 非 FORMAL 工作区一律 **403 `WORKSPACE_TYPE_NOT_ALLOWED`**。
- **两条放行（fail-open）分支显式化**：本守卫在「项目不存在 / 没挂工作区」与
  「工作区行不存在」时**放行**（**有意**：历史项目没挂工作区 ⇒ 不是个人草稿区
  ⇒ 不该因缺元数据把正常操作挡掉）⇒ 现在**各有**一条测试钉住（放行是**有意
  的选择**，不是漏网；哪天有人改成 fail-closed，测试会红）。
- 测试（**新增** `tests/api/v1/test_workspace_type_guard.py`，9 例）：四个端点
  各一条 403 用例 · 两条放行分支各一条 · 门禁本体（非 FORMAL ⇒ 403 /
  FORMAL ⇒ 放行）· 反向对照。

### 顺带修：`app/api/v1/_guard.py` 抛的异常变体

`_guard.py` 此前抛的是 **core 变体** `PcsError` ⇒ 而仓里的 `except PcsError`
**多半**捕的是 **service 变体**（TODO-080 第 3 条把 service 变体做成了 core
变体的**子类** ⇒ `except service.PcsError` **捕不到** core 变体抛出的错误）⇒
⇒ 改成抛 **service 变体**（子类 ⇒ 两种 `except` 都捕得到）。
⚠️ **同类残留见 TODO-089**（全仓还有 ~20 个模块抛 core 变体）。

**归属：** 已闭环。**关联：** UI-SPEC §5.3 · bug-2085 · TODO-089。

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

## ✅ DONE —— TODO-088: 6 条约束按 **schema** 补齐（2026-10-27 落地）

**原症状：** 在**隔离 schema**（`options=-csearch_path=<schema>`）上从零跑
`alembic upgrade head` ⇒ 建出来的 schema **缺** 6 条 ORM 声明的约束
（`ck_streams_phase` / `ck_streams_data_mode` / `ck_streams_source_type` /
`uq_report_definitions_project_name` / `uq_report_styles_scope_version` /
`future_dated_forbidden_chk`）⇒ 那个 schema 上的 `alembic check` 报 6 条
**假漂移**（`add_constraint`：ORM 要、DB 没有）。

**根因：** `p8_001` / `p8_008` / `p8_009` / `p8_011` 里那几条约束的**幂等检查**
写的是 `SELECT 1 FROM pg_constraint WHERE conname = '<名字>'` ⇒ **只按名字查，
不分 schema** ⇒ 而 `pg_constraint` 是**每库**不是**每 schema** ⇒ 同一个库里
**别的 schema**（例如 `public`）已有同名列 ⇒ **跳过建约束** ⇒ ⇒ 本 schema
永远拿不到。

⚠️ **两类后果**：①隔离 schema 验证 ⇒ 6 条**假漂移**（真·全新**数据库**没有
别的 schema ⇒ 约束**会**建出来 ⇒ CI 不受影响）；②**任何「按 schema 部署」的库**
（多租户 / 影子 schema）⇒ 约束**根本没装** ⇒ DB 层的安全网缺失。

**落地**

- **迁移 `p9_011`**（**不改历史** —— 改已应用的迁移会让「重放」得到不同结果）：
  判据改成 `connamespace = current_schema()::regnamespace` ⇒ **当前 schema**
  里没有就补上、有就跳过（幂等）⇒ 已有的 schema（`pcs` / `pcs_test`）**全部
  跳过**；缺约束的 schema **补上**。
- ⚠️ 三条 `ck_streams_*` 的取值**直接引用 ORM 枚举**（`app/models/enums.py` 是
  唯一来源）⇒ 不会与契约漂移（硬编码一份就是 bug-187~191 那一族）。
- **验证**：全新隔离 schema 从零 `alembic upgrade head` ⇒ **p9_011 (head)** ⇒
  6 条约束**全部在** ⇒ `alembic check` **exit 0**（此前 exit 255 + 6 条假漂移）；
  两库 `pcs` / `pcs_test` 各跑一次 `alembic check` ⇒ **exit 0**（`current` 均
  `p9_011` = head）。

## ✅ TODO-099: 后端单测全跑内存 SQLite，PG 语义无自动化车道（2026-11-03 关闭 · `b127495`）

**What:** CLAUDE.md 已记载的「漂移盲区」：迁移/方言相关缺陷在 SQLite 上不红。
本批已补两条 **skipif 有 PG 才跑**的引擎级测试（p9_013 真跑 + 降级环），但那是
逐案补的，不是车道。**Pre-existing**（评审 testing 登记）。

**Fix 方向:** 起一条 PG-backed pytest lane（CI service 容器 + `TEST_DATABASE_URL`），
- **落地**: `pcs-backend/scripts/pytest_pg.sh` —— **唯一入口**，fail-closed 三道闸：
  ① PG 实例未起 ⇒ 直接 exit 1（不静默跳过）；② 收集到 **0** 个 `pg` 用例 ⇒ exit 1
  （绿灯**证明不了**它们跑过）；③ 输出里没有 `N passed` ⇒ exit 1（skip 不算过）。
  配套：`docker-compose.yml` 的 `postgres-pgtest` 服务（`profiles: ["pg"]`，端口 5433，
  ⚠️ 数据卷挂 `/var/lib/postgresql` —— PG-18 镜像拒绝 `/var/lib/postgresql/data`）；
  `pyproject.toml` 注册 `pg` marker；4 个引擎级用例挂上 `@pytest.mark.pg`。
- **验证**: 车道 exit 0 + **4 passed**（本批末复跑同）；`tests/scripts/test_pytest_pg_gate.py`
  4 条（脚本存在且可执行 / PG 未起时失败 / 0 收集时失败 / 脚本里恰好 2 处 `uv run pytest`
  且含字面量 `pytest -m pg`）。
- ⚠️ **未覆盖**: CI **不**跑这条车道（单人开发裁决，见记忆「CI/CD 不做」）⇒ 车道是
  **本地**闸门，需人工执行。
把 `tests/alembic/` 的 skipif 测试与「双并发」类用例挂上去。

⚠️ **2026-11-02 补充（P9B-2F）**：P9B-2R 的行锁保证已由**方言级**断言钉住
（`test_locking_select_emits_for_update_on_postgres` = PG 方言编译出的 SQL
里含 `FOR UPDATE`）+ **接线**断言钉住（`test_write_paths_request_row_lock`）
⇒ 「删掉行锁必红」已是**实测**结论。但 **PG 上的实际并发结果**（一胜一拒、
审计不重不漏）**仍无自动化覆盖** ⇒ 本条（PG 车道）仍然是那条路的唯一解。

✅ **2026-11-02 已落地（P9B-3 · T0）**：本地 PG 车道已建 ——
`pcs-backend/scripts/pytest_pg.sh`（**唯一**入口，fail-closed 三约束：
PG 没起 / 收集到 0 个 PG 测试 / 全 skip ⇒ 三种情况都非零退出）+
`docker-compose.yml` 的 `pg` profile（独立实例 `postgres-pgtest`，库 `pcs_pgtest`，
端口 5433）+ `pg` pytest marker。
⚠️ 决策修正：委员会原议的「CI service 容器」**不做**（沿用「CI/CD 流水线不做」
的既有裁决）⇒ 车道是**本地**的，发布前由人手动跑 ⇒ 见 CLAUDE.md §「发布前检查（必做）」。

⚠️ **复审触发（2026-11-02 委员会）**：若未来 **2–3 个发布周期内**出现至少一次
「PG-specific bug 因为没跑 `scripts/pytest_pg.sh` 而在发布后暴露」⇒
2026-08-29 的「CI/CD 流水线不做」裁决**必须被重新提出**（不是被绕过），
依据是「自己记得跑」这个前提被证伪 N 次。

## ✅ TODO-101: `StateBadge` 的 DELIVERABLE 强调词表是**记录侧 9 态** ⇒ 交付物半透明（2026-11-03 关闭 · `51657ac`）

**What:** `pcs-frontend/src/components/common/StateBadge.tsx` 的
`MODULE_ACTIVATED.DELIVERABLE` 装的是 **9 态记录词表**
（DRAFT/IN_APPROVAL/CHECKED/...）⇒ 交付物自己的 4 态里 **`PENDING` 与
`APPROVED` 不在集合里** ⇒ 这两个状态渲染成 **opacity 0.4**（半透明），
看起来像「过期/不可用」，而真相是「待审 / 已批准」。

**Why:** 该文件头明确写「`MODULE_ACTIVATED` **只**决定 opacity，从不做有效性
检查」⇒ 半透明**不是**错误信号，但交付物用错了词表 ⇒ 用户会把「待审」读成
「过期」。**Pre-existing**（本批之前就在），但 P9B-2R 新引入的
`DeliverableSignStatus`（4 态）把这个分叉**显形**了。

**Fix 方向:** `DELIVERABLE` 的强调集改成它自己的 4 态
（`DRAFT/PENDING/APPROVED/OBSOLETE`）；改前先确认「已作废的交付物」该全透明
还是半透明（产品裁决），再配一条渲染测试。

**依据:** `docs/ce-code-review/20261102-004658-08a55f5c/report.md` §Pre-existing
- **落地**: `MODULE_ACTIVATED.DELIVERABLE` 改成**它自己的 4 态**
  （`DRAFT/PENDING/APPROVED/OBSOLETE`，契约派生 `DeliverableSignStatus`）⇒
  「待审 / 已批准」不再渲染成半透明（读成「过期」）。
- **验证**: `DELIVERABLE_FOUR_STATE` 数组 + **编译期双向断言**（少一个 ⇒ 后端真值落进
  「未知状态」兜底；多一个 ⇒ 契约里不存在的态被当成合法的）；渲染断言补上
  （`DeliverableProgressPage` 改用 `<StateBadge module="DELIVERABLE">` —— 不传 module
  的话强调修复是**空转**的）。
（maintainability 登记）。

## ✅ TODO-102: `POST /projects` 的 `IntegrityError → 409 PROJECT_NO_CONFLICT` 映射**过宽**（2026-11-03 关闭 · `909bc3a`）

**What:** `pcs-backend/app/api/v1/projects.py` 里项目 INSERT 捕获**任何**
`IntegrityError` ⇒ 一律报 409「项目编号已存在」。真正的约束只有
`project_no` 全局唯一，但**别的**约束违约（NOT NULL / FK / CHECK）也会被
说成「编号重复」⇒ 用户照着提示去换编号，换了还是错。

**Why:** 错误消息把「唯一的已知原因」说成了「唯一的原因」。**Pre-existing**
（P9B-2R 引入 409 时带的）。

**Fix 方向:** 只在约束名/列名命中 `project_no` 的唯一约束时映射 409，其余
`IntegrityError` 重新抛出（⇒ 500 + 服务端日志留详情）。

**依据:** `docs/ce-code-review/20261102-004658-08a55f5c/report.md` §R5 与
- **落地**: `app/api/v1/projects.py` 新增 `_is_project_no_unique_violation(exc)` ——
  只在**约束名**命中 `uq_projects_project_no`（或消息里同时含 UNIQUE + project_no）时
  映射 409；**其余 `IntegrityError` 重新抛出**（⇒ 500 + 服务端日志留详情）。
- **验证**: 新测试用**真实 SQLite 触发器**制造「别的约束违约」（NOT NULL / CHECK）
  ⇒ 断言 **500 INTERNAL_ERROR**（**不是** 409）⇒ 「用户照着提示换编号，换了还是错」
  的那条路径被钉死。
§Residual risks。

## ✅ TODO-103: `schema_compact_orm.md` 是 **53 表快照**（ORM 现有 107 张）（2026-11-03 关闭 · `0a0efd5`/`b948044`/`72f20be`）

**What:** `pcs-backend/docs/schema_compact_orm.md` 头部写「表数量：53」，生成
于 2026-09-02 ⇒ ORM 现有 **107** 张表，文件里**缺 54 张**（含 4 张记录表
`relief_results` / `column_sizing` / `mixer_results` /
`thermosiphon_circulation_results`）⇒ 它**不能**当完整的 ORM 参考用。

**Why:** 该文件被当成「照这张表手写 SQL」的依据 ⇒ 缺表 = 照着查不到的表去
写 SQL。本批（P9B-2F #10）已把 16 张在表内的记录表补上快照列，并在表头**如实
标注**了它是快照 —— 但**重新生成**（107 表）本身没人排期。

**Fix 方向:** 写一个生成脚本（从 `SA_Base.metadata` 导出，格式沿用现有
`col|type!` 风格）⇒ 每次改 mixin 后重跑 ⇒ 文件变成**派生**产物而不是手工
维护物。

**依据:** `docs/ce-code-review/20261102-004658-08a55f5c/report.md` #10。
- **落地**: `pcs-backend/scripts/gen_compact_orm.py` —— 从 `SA_Base.metadata`
  **重新生成** `docs/schema_compact_orm.md` ⇒ 文件变成**派生**产物而不是手工维护物
  （改 mixin 后重跑即可）。格式沿用既有 `col|type!` 风格 + PK/FK 后缀 + `[UNIQUE: …]`。
- **验证**: `tests/scripts/test_gen_compact_orm.py` 5 条 —— 覆盖**每一张** ORM 表 /
  提交态文件与重新生成的结果**一致**（忽略「生成时间」行）/ 格式标记 / 每张表恰好
  出现在一个章节。
- ⚠️ 踩坑记录：`table.constraints` 是 **set** ⇒ 迭代顺序不确定 ⇒ 生成物会漂 ⇒
  `[UNIQUE: …]` 按**约束名排序**输出。

## ✅ DONE —— TODO-089: 两个 `PcsError` 变体**合并成一个类**（2026-10-27 落地）

**原症状：** TODO-080 第 3 条只把 service 变体做成了 core 变体的**子类**
⇒ `except core.PcsError` 两个都捕得到 ✔，但**反方向不成立**：
`except service.PcsError` **捕不到** core 变体抛出的错误 ⇒ 全仓 **55** 处
`except PcsError` 都是**潜在漏网** ⇒ 业务错误（404/409/422）**静默变成 500**
（bug-2079 同一族，方向相反）。

**落地：两个类 → 一个类（别名）**

- `app/core/errors.py::PcsError` 现在**同时**吃**两种**调用风格：
  - **service 风格** `PcsError("消息", code="X", status=404, details={...})`
    ⇒ 缺省 `code=PCS_ERROR` / `status=422`；
  - **core 风格** `PcsError("CODE", "消息", 404, {...})` 或
    `PcsError(code="X", message="消息")` ⇒ 缺省 `status=400`（历史 core 变体）。
  - **status 缺省优先级**：显式传入 → **子类自己声明的** `status` 类属性
    （`WorkspaceNotFoundError` → 404 …）→ core 风格 400 / service 风格 422。
  - `details` 与 `detail` 是**同一份数据的两个名字**（`details` 是 service 变体
    的历史字段名）。
- `app/services/exceptions.py::PcsError` 现在是**同一个类的别名**
  （`PcsError = CorePcsError`）⇒ `except` 哪一个 import 都**捕得到全部**
  ⇒ 30 多个 service 子类（`PreconditionViolation` / `Psv*` / `Workspace*` …）
  **原地继承**，各自的 `code` / `status` 类属性**保持不变**。
- 全局异常处理器**从 2 个减到 1 个**（`_service_pcs` 删除）⇒ core / service
  两种抛出方走**同一条**渲染路径 ⇒ 响应信封必然一致。
  ⚠️ 副作用（**是修复不是回归**）：service 抛出的 401/403 现在**也**走
  RBAC 审计 + per-IP 限流（此前它们绕过这条路径 ⇒ 授权拒绝**没留痕**）。
- **测试**（**新增** `tests/core/test_pcs_error_unified.py`，13 例）：两个名字
  是同一个类（RF-1/RF-2）· 两种风格的缺省值（RF-3/RF-4）· 子类的
  `code`/`status` 不被合并覆盖（RF-5/RF-6）· `str(exc)` 仍是 message。

**归属：** 已闭环。**关联：** bug-2079（TODO-080 第 3 条）· bug-2085。

## ✅ DONE —— TODO-082: 两道「已对外生效」的门换成**真实可判定**的条件（2026-10-27 落地）

**原症状：** `records.locked_by_deliverable` 全仓**只被读，从未被写 True** ⇒

- `record_cancellation_service` 的「已绑定记录（`locked_by_deliverable=True`）
  必须先建 `change_type=RECORD_CANCELLATION` 的变更单才能作废」⇒ **不存在**；
- `reversal_approval_service` 的「已对外生效的记录只能走 `CHANGE_REVERSAL`」
  ⇒ **不存在**。

⇒ 任何记录都能被**直接弃用**、被**直接撤销** ⇒ 「作废/撤销都要有凭证」这条
业务约束**事实上不存在**。

**业务裁决（2026-10-27，用户选「换成真实可判定的条件」）**

**落地**

- 新增 `DeliverableService.is_record_effectively_published(db, record_type=,
  record_id=)` ⇒ 「记录有没有被一张 **APPROVED** 的交付物绑定」
  （`deliverable_record_bindings` ⋈ `deliverable_versions` ⋈ `deliverables`）。
  ⚠️ **判「APPROVED」而不是「有绑定」**：一张**还没签完**的变更单也绑了记录
  ⇒ 用「有绑定」当门禁 ⇒ 用户在变更单还没批准时就被挡住 ⇒ 流程走不动。
- 两道门改用该判据：
  - `RecordCancellationService.obsolete`（直接弃用）⇒ 已对外生效 ⇒ **409
    `RECORD_BOUND_USE_CHANGE_NOTICE`**（必须先建 RECORD_CANCELLATION 变更单）；
  - `ReversalApprovalService.request_reversal` ⇒ 已对外生效 ⇒ **409
    `REVERSAL_LOCKED_USE_CHANGE_REVERSAL`**（只能走 CHANGE_REVERSAL 反向变更）。
- ⚠️ `bound_obsolete_via_deliverable`（走变更单弃用的入口）改判「**这张**
  交付物**绑了**这条记录」（`is_record_bound_to_deliverable`）—— **不能**判
  「已批准」：本方法由变更单 APPROVED 流程调用 ⇒ 那一刻这张单**还没**批完 ⇒
  判「已批准」会把这条路径**永远堵死**。
- 测试（**新增** `tests/services/test_record_publication_gate.py`，5 例）：已批准
  ⇒ 两道门都拒（409）· 没绑定 / 还没批准 ⇒ **放行**（门不误伤）· 被拒后状态
  不变。⚠️ 既有**假 Session** 用例 `test_request_reversal_rejects_locked_by_deliverable`
  的前提（那个标志）已消失 ⇒ 删除 ⇒ 真库用例取代它。

**⚠️ 已知代价（用户裁决时已告知）**：一张变更单**批准**后，该记录就「已对外
生效」⇒ 之后**普通撤销**（request-reversal）会被拒 ⇒ 只能走 **CHANGE_REVERSAL
反向变更单**。

**✅ 已知代价的「逃生口」已钉住（2026-10-27）**：代价不能只是「告知」——
必须证明**替代路径真的通**（否则代价 = 死路）。新增
`tests/services/test_change_reversal_escape_hatch.py`（1 例，**端到端**）：
记录被 APPROVED 的交付物绑定（已对外生效）⇒ ①普通撤销被拒（409
`REVERSAL_LOCKED_USE_CHANGE_REVERSAL`，**消息点名** `CHANGE_REVERSAL`）·
②直接弃用被拒（409 `RECORD_BOUND_USE_CHANGE_NOTICE`，**消息点名**
`RECORD_CANCELLATION`）· ③**CHANGE_REVERSAL 反向变更单建得出来**（不撞
409/422）· ④签完 ⇒ 记录回 `CHECKED`。
⚠️ 顺带查清的一件事：`close_on_approved` **只关记录**，**不**把单推成
APPROVED（那是 `sign_step` 的动作）⇒ 「已对外生效」的真相仍是
`deliverables.sign_status == APPROVED` ⇒ TODO-090 的标记也照这个判据写。

**✅ 业务裁决（用户 2026-10-27）**：**「已对外生效（CHECKED）的记录**直接**建不了
CHANGE_REVERSAL 单」是**正确的**，不是缺陷** ⇒ ①`create_change_notice` 继续要求
记录处于 **CHANGED**（不许为已发布记录开反向单）；②「撤回一次已发布的内容」的正
确路径 = **先发起一次变更**（把数据改回原值）⇒ 记录进 CHANGED ⇒ 再开
**CHANGE_REVERSAL** 反向变更单走正常的 3 级矩阵 ⇒ **反转本身就是一次变更**；
③**别**为此加「允许对 CHECKED 记录开反向单」的特例 —— 那等于给已发布记录开一条
**绕过 3 级校审**的后门（与 TODO-078 记录的「作废不关记录」是同一条原则：
**单据的效力只能来自它自己的审批**）。

**遗留（TODO-090，已闭环 ⇒ 见下条）**：`locked_by_deliverable` 列 ⇒ 选**写成
审计标记**（不删列）。

**顺带修（bug-2088）**：迁移假用例时发现，记录弃用的**审计 `resource_id`** 用
的是 `getattr(rec, "record_id", "")` ⇒ 而各表的**主键列名不同** ⇒ 在别的表上
**恒为空串** ⇒ **审计链断**（查不到是哪条记录被弃用）⇒ 改用**调用方传入的
主键**。⚠️ 与 bug-2081 **同族**（同一个错：拿「列名可能不同的属性」当主键）。

**归属：** 已闭环。**关联：** TODO-069 · TODO-078 · ADR-0009 · bug-2086 ·
TODO-090。

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

## ✅ DONE —— TODO-090: `locked_by_deliverable` 列**写成审计标记**（2026-10-27 落地）

**原症状：** TODO-082 把两道「已对外生效」的门换成**真实可判定**的条件
⇒ 该列**既没有写入方**、**也不再是门禁** ⇒ 记录读端（`GET /records/{module}`）
把它**原样上报**（恒为 False）⇒ 前端拿到的是一个**永远为假的字段**。

**裁决：写它（不删列）** —— 选项①（审计标记）。

**落地**

- `ChangeNoticeService.close_on_approved`（变更单**签完** ⇒ 关记录那步）在关
  记录时写 `record.locked_by_deliverable = True`。
  ⚠️ **判据与门禁完全一致**：只有当**这张单已经 APPROVED**（真实路径 =
  `sign_step` 签完最后一步 ⇒ 先把单推成 APPROVED ⇒ 再调本方法）才写 True
  ⇒ 列与 `is_record_effectively_published` 判的是**同一个事实** ⇒
  **不会分叉**（单子还 PENDING ⇒ 不写 ⇒ 列说「没生效」而门禁也说「没生效」）。
  ⚠️ APPROVED 是**终态**（作废只认 DRAFT/PENDING 的单）⇒ 写 True 之后
  **不会**回退 ⇒ 列**不会**变成「陈旧的 True」。
- 门禁**仍然**走 `is_record_effectively_published`（**不拿这一列当判据**）——
  列是**派生标记**，查询才是**真相** ⇒ 直接改 DB 改不动门禁。
- 列注释改成「已被 APPROVED 的交付物绑定（=已对外生效）；变更单批准时写
  True」（`app/models/mixins.py`）；数据字典 `PCS-DICT-ALL-003 V3.6` 同步。
- **测试**（`tests/services/test_change_notice_close_real_db.py`）：单子
  APPROVED ⇒ 写 True；单子还 PENDING ⇒ **不**写（列与门禁一致）。

**归属：** 已闭环。**关联：** TODO-082 · ADR-0009 · 数据字典 V3.6。

## ✅ DONE —— TODO-085: 矩阵修改的**申请 + 双审** —— 本项目**不做**（业务裁决，2026-10-27）

**原症状：** `spec/校审层级可配置化增补规格说明书.md` §2.3 写明：「项目进行中：
修改签署矩阵需**项目负责人提出申请，审核+审定双重审批**」。本仓只落了
**「只有项目负责人能绑」这一层**（用户 2026-10-26 裁决），没有「申请 → 审核
→ 审定」的流程。

**业务裁决（2026-10-27，用户选「本项目不做双审」）**

**理由**：§2.3 那条规则针对的是**「项目级覆写」**（项目自己一份矩阵**内容**），
而 PCS **没有这个对象** —— 矩阵内容只有**一份全局的**
（`signature_matrices`），项目只能**选**哪一份（`project_signature_matrix_bindings`）
⇒ **该规则当前没有适用对象** ⇒ 实现「申请 + 双审」= 为一个不存在的场景造流程
⇒ 流程成本 > 收益。

**现行口径（写进 SPEC V1.2 §2.3 注记 + 版本历史）**

| 操作 | 谁 | 生效范围 |
|---|---|---|
| 改矩阵**内容**（步骤） | SYSTEM_ADMIN（全局模板） | 所有用它的项目 |
| 改项目**用哪一份** | 项目负责人（`PROJECT_LEAD`） | 本项目 |

⚠️ **将来若引入「项目级覆写」** ⇒ **必须**同时实现申请 + 双审 —— 否则
「全局模板改了 ⇒ 所有项目跟着变」这个天然闸门在覆写场景下会**失去**。

### 顺带闭环：**前端「作废变更单」入口**（本批最后一项）

- **后端新增读口** `GET /records/{module}/{id}/change-notice` ⇒ 返回该记录当前
  **开着**的变更单摘要（`has_open_notice` + 单号 / 交付物 / 版本）。
  ⚠️ **没有**用 404 表达「没有」⇒ `has_open_notice=false` + 其余字段为 null
  （404 是「资源不存在」，拿它当控制流会让前端到处 try/catch）。
- **前端**（`src/pages/results/ChangeNoticeAction.tsx`）：CHANGED 态的行**仍只给
  一个**按钮（沿用 UI-SPEC §6.3「按状态渲染」的口径）⇒ **弹窗**按「有没有开着
  的变更单」分两种：
  - 没有 ⇒ 「创建变更单」表单（现状不变）；
  - **已有** ⇒ 「**作废**变更单」表单（作废理由必填）+ 提示已有单号 ⇒ 作废后
    该记录**可以另起一张**（作废的单不挡新单）。
  ⚠️ 查询**只在打开弹窗时**发 ⇒ 列表页**不会有 N+1 请求**。
  ⚠️ **作废的是「单据」⇒ 记录不动**（仍 CHANGED）⇒ 前端**不改**记录状态。
- MSW mock 补齐 3 个端点（GET / POST cancel）+ 内存态（建单 ⇒ 有开着的单；
  作废 ⇒ 没有）⇒ 人工验收能看出变化。
- 测试（前端 **+5 例**）：`tests/pages/results/change_notice_cancel.test.tsx`
  （3 例：无单 ⇒ 创建表单 / 有单 ⇒ 作废表单 / 填理由 ⇒ 调作废端点且**记录状态
  不变**）+ `tests/api/change_notices_api.test.ts`（+2 例：URL 与 body 契约）。
- **契约影响**：OpenAPI **247 path**（同一路径多一个 GET 方法 ⇒ path 数不变）
  / **348 → 349 schema**（+1 = `ChangeNoticeOpenResponse`）⇒ `openapi.json` /
  baseline / 前端 snapshot + `api.d.ts` 已重新生成并滚 baseline；裸字段仍 **71**。

**归属：** 已闭环。**关联：** TODO-085 · UI-SPEC §6.3（2026-10-27 修订登记）·
bug-2087。

**归属：** 已闭环（按裁决**不做**）。**关联：** TODO-070 · TODO-074 ·
`spec/校审层级可配置化增补规格说明书.md` **V1.2 §2.3 注记** · 用户 2026-10-26
裁决「只有项目负责人能绑」。

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

### 收尾加固：快照列清单改成**从 mixin 自动推导**（2026-10-27）

⚠️ 原先的跳过集是**手写清单** ⇒ 风险有两条：
① 将来给 `RecordMixin` 加一个流程列 ⇒ **忘了**加进清单 ⇒ 快照把它一起存 ⇒
恢复时把**流程状态**也回滚 ⇒ 与当前状态打架 ⇒ 且**没有任何测试会红**（清单是
数据，不是断言）；
② **已经漏了一列** —— `approval_depth`（批准深度，流程列）不在手写清单里 ⇒
它**被快照了** ⇒ 恢复会把批准深度一起回滚。

⇒ 改成 `_mixin_columns(TimestampMixin, RecordMixin)` **自动推导** ⇒ 新列
**默认**被跳过 ⇒ 想快照它必须**显式**放行（当前放行：`record_hash` =
「变更前的数据指纹」、`tag_number` = 位号）。
⇒ 守卫测试（**新增**）：mixin 上的每一列，要么在跳过集里、要么在显式放行名单
里 ⇒ **忘了**加就**测试变红**。

## ✅ TODO-104: 已闭环（2026-11-09 · P9B-4 紧急批次）

**现状**：`GET /audit-logs?...&action=RECORD_TRANSITION` 返回该物流的全部状态转移，
前端按 `detail_json.transition` 过滤出校核相关的三条。

**为什么本批不做**：当前一个物流平均 5–10 次状态转移，前端过滤可接受。

**触发条件**：状态转移次数显著增长（如 > 50 次/物流），或校核记录 Tab 加载变慢。

**方案**：`audit_logs.detail_json` 加 GIN 索引，或表达式索引
`(detail_json->>'transition')`。

**归属：** P9B-4 或独立技术债。

**✅ 已闭环（2026-11-09 · P9B-4 紧急批次 T6）**：**后端过滤**已并入
`GET /streams/{id}/review-log`（只返回 SUBMIT_FOR_CHECK / PASS_CHECK / REJECT_CHECK
三条 ⇒ 前端**不再**自己过滤）。
⚠️ **索引部分仍延后** —— 准确表述是「**已有 GIN 索引覆盖不到本查询的写法**」：
表上 `ix_audit_logs_detail_json_gin` 是 `jsonb_path_ops` ⇒ 只支持 `@>` / `@?` / `@@`
⇒ 本查询用 `->>` ⇒ **用不上它**；而 `@>` 在**测试库 SQLite 上不可用**
（`unrecognized token: "@"`）⇒ 统一查询只能用 `->>` ⇒ 真要优化得**另加**表达式索引。
**触发条件不变**：生产出现性能问题，或该类行数 > 10 万。

## ✅ TODO-108: 已闭环（2026-11-11 · P9B-4 体验批 T2）

**本批修了什么**：① 后端 `StreamService.reference_counts` —— **两条聚合查询**
（`GROUP BY`）⇒ 整个列表 2 次往返 ⇒ **不是 N+1**；② `StreamResponse.reference_count`
（默认 0）+ 列表端点显式填（⚠️ 它**不是 ORM 列**）；③ 前端列表加「引用 📎×N」
列（0 ⇒ 「—」）；④ mock seed 同步。

**口径（钉死）** = **下游物流数**（`streams.upstream_stream_id`）+
**闪蒸结果数**（`flash_results.stream_id`）⇒ **不含**状态点（物流自己的子表）
与设备引用（JSONB 数组 · 无索引 · 延后）。

⚠️ **与删除门禁 `_collect_references` 的口径不同**（那边**含**状态点，因为状态点
会阻塞删除）⇒ 两个数字**不要**混用 ⇒ SPEC §7.7.1 已写明（「引用 0」**不等于**
「可以删」）。

⚠️ **空入参早返回**（`IN ()` 在 PG 上是**语法错误** ⇒ 筛选后列表为空时不让接口 500）。

**证据**：`tests/services/test_stream_reference_count.py`（8 例 · 口径）+
`tests/api/v1/test_stream_list_reference_count.py`（4 例 · 接线 + N+1 守卫）·
浏览器回归见 `.gstack/qa-reports/qa-report-pcs-frontend-2026-11-04-p9b4.md` §2.2。

**遗留**：设备引用（JSONB 数组）**是否**计入 ⇒ 登记为新条目（下一批裁决）。


**现状**：SPEC §7.7.1 的物流列表有一列「引用 📎×N」，但**只给了列名，没定义口径**；
后端列表响应**不返回**该字段 ⇒ 前端**画不出**这一列。

**本批做法**：SPEC §7.7.1 该列标 ⏳（未实现），前端**不渲染**这一列。

**建议口径**（下一批裁决）：N = 该物流被**下游引用**的条数
（设备 + 物流，lineage downstream 口径）⇒ 需后端在列表响应里加
`reference_count`（**一次聚合，无 N+1**）。

**归属：** 下一批（与 §7.7.1 其余筛选/列口径一并收口）。

## ✅ TODO-112: 已闭环（2026-11-09 · P9B-4 紧急批次）

**现状**（2026-11-03 实测）：`GET /audit-logs` **限 SYSTEM_ADMIN**
（`audit_logs` 表**没有** `project_id` ⇒ 端点无法按项目守卫 ⇒ 放开就等于
把**全公司**的审计流水暴露给每个设计员）。

⇒ 后果：DESIGNER 打开物流详情的「校核记录」Tab 看到的是「无权查看」——
**他看不到这条物流的校核经过**（而校核记录正是他最需要的东西）。

**建议**：新增**按项目守卫**的端点（参考 `GET /records/{module}/{record_id}/edits`
的守卫口径 —— 它就是为「普通用户点得开差异」而做的）⇒ 例如
`GET /streams/{id}/review-log`，只返回该物流的
`SUBMIT_FOR_CHECK` / `PASS_CHECK` / `REJECT_CHECK` 三条。

**归属**：P9B-4 或独立技术债（**不要**靠放开 `/audit-logs` 解决）。

**✅ 已闭环（2026-11-09 · P9B-4 紧急批次 T6）**：新增
`GET /streams/{id}/review-log`（**项目守卫**端点 + 具名 schema `ReviewLogItem`）⇒
DESIGNER 能读到**自己物流**的校核经过。前端 Tab 改调它，**删掉**前端那一套过滤。
⚠️ **裁决条件 3 守住**：只做「读 review-log」—— 无导出 / 无管理员视角 / 无时间筛选 / 无分页。

## ✅ TODO-113: 已闭环（2026-11-09 · P9B-4 紧急批次）

**现状**（2026-11-03 实测 · P9B-3 评审顺带发现 · **非本批引入**，`8b6d9ef` 已如此）：
`GET /api/v1/streams/{stream_id}` 只做 `require_roles(user, "DESIGNER", …)`，
**不校验该物流所属项目** ⇒ 任何 DESIGNER 持**任意 UUID**即可跨项目读物流详情。

⚠️ 本批的物流详情页（`/sim/streams/:id`）**依赖这个端点** ⇒ 前端做的任何
项目级过滤都挡不住后端放行。

**建议**：按 `check_project_access_or_404`（`app/api/v1/_guard.py`）补项目守卫
⇒ 跨项目访问返回 404（不泄露「存在但无权」）。

**归属**：独立技术债（**不要**在 P9B-3b 里顺手改 —— 那是批量端点，不是权限面）。

**✅ 已闭环（2026-11-09 · P9B-4 紧急批次 T2）**：`GET /api/v1/streams/{id}`
等 10 个物流读/写端点全部补上项目守卫 ⇒ 跨项目一律 **404**，且**与「不存在」
逐字同形**（`SIM_STREAM_NOT_FOUND`）⇒ 枚举不出某个 UUID 是否存在。
⚠️ 守卫用**新**的 service 层 `has_project_access()`（只回 bool）而不是
`check_record_access_or_404` —— 后者的 `"Project not found"` 与「不存在」的
信封**不同** ⇒ 可枚举。

## ✅ TODO-114: 已闭环（2026-11-09 · P9B-4 紧急批次）

**现状**（2026-11-03 实测 · P9B-3 评审顺带发现 · **非本批引入**）：
`app/api/v1/lineage.py::_guard_record_access` 里
`if record_type != "PipingResult": return` ⇒ **`record_type='streams'` 完全跳过**
访问校验。

⚠️ 本批新增的「血缘」Tab 是**首次以 `record_type='streams'`** 调它 ⇒
本批把这条既有缺口**暴露出来**（不是本批引入的，但本批是第一个消费者）。

**建议**：把守卫按记录类型注册表扩到 `streams`（及其它记录型表）⇒
与 TODO-113 一并收口。

**归属**：独立技术债（与 TODO-113 同批做更省事）。

**✅ 已闭环（2026-11-09 · P9B-4 紧急批次 T5）**：`_guard_record_access`
扩成**记录类型注册表**（`LINEAGE_GUARDED_RECORD_TYPES`：记录类型 → (模型, 主键列名)）⇒
`streams` 登记进去 ⇒ 不再跳过。
⚠️ 跨项目 ⇒ **与「无血缘」逐字同形**的 404（`no lineage for record`）—— 守卫**存在之前**
`streams` 整个跳过 ⇒ 两种情况都是这句 ⇒ **不可枚举**；改抛别的 message 反而会**引入**
枚举向量。

## ✅ TODO-118: 已闭环（2026-11-09 · P9B-4 紧急批次）

**现状**（2026-11-03 实测 · P9B-3b D3 决策 · **非本批引入**）：
`POST /streams/{id}/submit` / `approve` / `reject` / `initiate-change` /
`pass-change` / `mark-stale` 六个写端点**只做角色校验**
（`require_roles(user, "DESIGNER", …)`），**不校验物流所属项目**
⇒ 任何 DESIGNER 持任意 UUID 即可跨项目**写**物流。
（`current_actor` 只提供 `user_id` / `username` / `role`，**没有项目范围**；
但端点**确有** `Depends(current_actor)` ⇒ 不是「裸奔」，是「有认证无授权」。）

⚠️ **P9B-3b 的批次端点（`POST /streams/batch-submit`）复制了这个缺陷** ——
理由见 P9B-3b 计划 D3 决策：授权重构应**一次性**做（六个写端点 + 读面 +
批次一起修），不应在批次端点单独做。
⚠️ **批次端点的存在降低了攻击成本**：从「100 次请求」降到「1 次请求」，
使越权从「逐条摸索」变成「一次扫荡」。**这一事实不改变缺陷的性质，
但改变了严重性的评估。**

⚠️ 换句话说：批次端点与单条端点暂时同口径 —— 这个「同口径」是**已知缺陷的延续**，
不是设计意图。新代码本不应复制既有缺陷，但在本批不加守卫的理由是
「授权重构应一次性做」，**不是**「批次不需要守卫」。

**待修范围**（一次性）：
- 六个写端点 + 读面（`GET /streams/{id}` 等 · 见 TODO-113）
- 批次端点（`POST /streams/batch-submit`）
- 实现：复用 `check_record_access_or_404`（`app/api/v1/_guard.py`）
  或 `UserProjectService.list_user_projects` 一次取授权项目集合
  ⇒ `streams.project_id` 是**直接列** ⇒ 守卫可直接套用，无需 JOIN。

**触发条件**：任何一个真实越权事件发生，或访问控制审计要求。
**归属**：独立批次（**不是** P9B-3b）。
**相关**：TODO-113（读面）· TODO-114（血缘图的同类缺口）· P9B-3b 计划 D3 决策。

**✅ 已闭环（2026-11-09 · P9B-4 紧急批次 T2/T3/T4）**：
6 个状态转移端点（submit / approve / reject / initiate-change / pass-change /
mark-stale）+ 批次端点（`POST /streams/batch-submit`）全部补上项目守卫。
⚠️ **守卫先于组成门禁**：跨项目 submit ⇒ **404**（不是 422「组成合计 87.3%」）
—— 那种 422 同时泄露「存在」与「组成数据」。
⚠️ 批次端点的跨项目条目按「**不存在**」处理（`reason=SIM_STREAM_NOT_FOUND`）
⇒ 合法条目**照常成功**（D2 部分成功语义不受影响）。

## ✅ TODO-116: 已闭环（2026-11-11 · P9B-4 体验批 T1）

**本批修了什么**：① 失败清单从**组件局部 state** 提升到 **hook**
（`src/pages/sim/hooks/useStreamBatchSubmit.ts`）⇒ **关闭摘要弹窗不清清单**；
② 工具栏**下方**加**失败清单条**（`stream-batch-failure-bar`）+「只重试失败项」
+「清除」；③ 弹窗内也加「只重试失败项」（**复用同一份 hook 状态**，别写第二套）；
④ 关闭提示文案改写（「关闭后失败清单将不再显示」**已不成立** ⇒ 改成
「关闭弹窗后仍可用上方『只重试失败项』重试这 M 条」）。

**登记时写下的两条约束，落地结论**：
1. ⚠️ **失败清单要提升到上层状态** ⇒ 已做（hook）⇒ 「失败 id 已现成」**不再**
   只在弹窗打开期间成立；
2. ⚠️ **重试的幂等语义** ⇒ **不需要**后端区分「我重试成功的」与「被别人抢跑的」
   ⇒ 摘要里已有一行「其中 M 条本来就在审批中（幂等命中 · 本次**未**提交）」
   （TODO-124）⇒ 幂等命中**如实显示** ⇒ 用户不会误以为是自己重试生效的。

**语义**：**只重试上次的失败项**（成功的已经提交过了 ⇒ 重发是浪费）⇒ 重试后
失败清单**替换**为本次重试的失败清单（「上次失败、这次不再失败」的条目消失）。

**证据**：`tests/pages/sim/useStreamBatchSubmit.test.ts`（9 例）+ 页面 2 例
（关闭弹窗后仍能只重试失败项 / 清单条可清除）+ 浏览器回归见
`.gstack/qa-reports/qa-report-pcs-frontend-2026-11-04-p9b4.md` §2.3。

**已知限制**：失败清单是**内存态** ⇒ 刷新页面丢失 ⇒ UI 上已如实提示。


**现状**（2026-11-03 · P9B-3b）：`POST /streams/batch-submit` 返回 207（部分成功）
⇒ 前端摘要弹窗显示「失败 M 条」+ 每条原因，但**没有**「只把这 M 条再提交一次」
的按钮 ⇒ 用户要重试失败项时得**自己记住**哪 M 条（失败清单**关闭弹窗即丢**）。

**为什么需要**：批量操作最容易劝退人的地方就是「失败后要手动重来」—— 50 条里
8 条失败，用户要重试时得回列表逐条找 ⇒ 这个体验会让人下次不敢批量操作。

**现状的缓解（本批已做）**：摘要弹窗里有提示「关闭后失败清单不再显示」
⇒ 缺口**可见**，但未**解决**。

**未来实现的约束**（登记时就写下，避免将来低估工作量）：
1. ⚠️ **需要先把失败清单提升到上层状态** —— 当前 `batchResult` 是**组件局部
   state**（`useState`）⇒ 关闭弹窗即丢 ⇒ 「失败 id 已现成」**只在弹窗打开
   期间成立** ⇒ 未来加按钮前要先改状态管理（约 20 行）。
2. ⚠️ **重试场景下的幂等语义需要复核** —— D5 的幂等是「已 `IN_APPROVAL` 也
   视为成功」（`note=already_in_approval`）⇒ 重试时若某条**已被别人**提交，
   也会返回成功 ⇒ 前端需要区分「我重试成功的」与「被别人抢跑的」，
   否则用户会误以为是自己重试生效的。
   ⇒ 若要区分，**后端**需在响应里加字段（如 `note` 的细分来源）—— 这不阻塞，
   但**登记时写清楚**。

**后端是否需要改**：⚠️ **基本不需要**（复用同一个批量端点）；只有上面第 2 点
若要做，才需要后端加一个字段。

**触发条件**（任一成立时实施）：
- 本仓出现第一次「用户反馈批量提交后重试困难」的记录；
- P9B-4 或后续做「批量操作统一交互」时，一并做。

⚠️ **不写**「看真实频次再决定优先级」—— 当前**没有**「重试」的识别机制
（批次审计只记录批次整体，不区分「首次提交」与「重试」）⇒ 那个理由在现有
数据采集能力下**不成立** ⇒ 改成「凭用户反馈」。

**归属**：P9B-4 或「批量操作交互收口」专项（不单独立项）。
**依据**：`docs/superpowers/plans/2026-11-03-p9b-3b-batch-submit.md` 的 D8 决策
+ 摘要弹窗的失败清单关闭提示。
**相关**：D2（部分成功）· D5（幂等语义）。

## TODO-121: `PipeClassListPage` 的 antd Table 报 React key 警告 ✅ 已闭环（2026-11-04）

**现状**（2026-11-03 实测 · **P9B-3b 批末浏览器 QA 顺带发现** · **非本批引入**）：
快速连续切页时控制台出现
`Warning: Each child in a list should have a unique "key" prop.`
组件栈落在 `pcs-frontend/src/pages/pipe_class/PipeClassListPage.tsx:30`（antd `Table` 内部）。

**归属核实**：`git diff --name-only 252f25a~1 HEAD | grep pipe_class` 为空
⇒ **P9B-3b 全程没碰过该文件**；该文件最后一次改动是 `8c393a7`
（「StrictColumns —— 把 antd 的 dataIndex 收成行类型的 key」），早于本批。

**为什么没在本批修**：越界修改（CLAUDE.md §「外科手术式改动」：只碰与请求直接相关的行）
⇒ **不是**「修不了」，是「不该在这一批修」。

**建议**：查 `PipeClassListPage` 的 `columns` 里哪一列渲染了**数组**
（antd 的 `dataIndex` 指向数组时，展开的子项需要 key）⇒ 补 key 或改渲染函数。

**触发条件**：下一次动管道等级页时顺手修；或单开「前端既有缺陷清理」批。

**依据**：`.gstack/qa-reports/qa-report-pcs-frontend-2026-11-03-p9b3b.md` §3 MEDIUM-1
（该报告在 `.gitignore` 里 ⇒ 只落本地 ⇒ 本条 TODOS 是它的对外留痕）。

## TODO-122: 批次上限的 `int(raw)` 会把 JSON `true` 当成 **1** ✅ 已闭环（2026-11-04）

**现状**（2026-11-03 · P9B-3b 整支分支评审 Minor #2）：
`app/services/stream_batch_service.py::_batch_limit` 用 `int(raw)` 解析系统参数
`stream.batch_submit_limit` ⇒ `int(True) == 1`（bool 是 int 的子类）
⇒ 管理员若把这个参数存成布尔 `true`，批次上限会**静默变成 1**
（而不是回落默认 100）⇒ 用户批量提交 2 条就被 **422** 拒。

**为什么没在本批修**：本批的修法是**加一个 `isinstance(raw, bool)` 的特判**
—— 看起来很小，但它改的是「系统参数的取值口径」（布尔值到底算不算数字），
而这个口径**全仓共用**（别的参数也走 `get_setting_value`）⇒
应该一次想清楚，不是顺手在批次里单点特判。

**建议**：`get_setting_value` 的调用方各自声明「我这个参数接受什么类型」
（数字参数统一走一个 `coerce_int(raw, default)` 助手，
里面显式排除 bool）⇒ 而不是每个调用点各写各的。

**触发条件**：下一次动系统参数的取值口径时。

## TODO-123: 换筛选条件时**不清行选择** ⇒ 可能提交「看不见的行」 ✅ 已闭环（2026-11-04）

**现状**（2026-11-03 · P9B-3b 整支分支评审 Minor #1）：
`pcs-frontend/src/pages/sim/StreamListPage.tsx` 的 `setSelectedIds` 只在
「行选择变化」与「提交成功后」被调用 ⇒ **换筛选条件**（`setFilters` → 重新
`load()`）**不清选择** ⇒ 用户勾了 5 行 → 换筛选（只剩 3 行可见）→
点「批量提交校对」⇒ 提交的是 **5 条**（含 2 条已不在视野里的）。

⚠️ 影响有界（已 `IN_APPROVAL` 的会走幂等命中、结果逐条可见），
但按钮上**不显示「已选 N 条」** ⇒ 用户无从判断自己提交了多少。

**建议**：① `load()` 成功后（或 `setFilters` 里）清 `selectedIds`；
② 工具栏按钮上显示「批量提交校对（N）」。

**归属**：前端交互收口批（与 TODO-121 同批更省事）。

## TODO-124: 批次摘要**不区分**「真提交」与「幂等命中」 ✅ 已闭环（2026-11-04）

**现状**（2026-11-03 · P9B-3b 整支分支评审 Minor #4）：
契约的 `BatchSucceededItem.note` 有 `already_in_approval` 标记
（已 `IN_APPROVAL` 的那条**本来就在审批中**、这次**并没有真的提交**），
但 `StreamListPage.tsx` 的摘要只显示「成功 N · 失败 M」，
而 N **包含**幂等命中 ⇒ 用户以为提交了 N 条。

**为什么没在本批修**：需要先有「摘要要显示多少条幂等命中」的口径决定
（前端数 `note === 'already_in_approval'`？还是后端在响应里给个计数字段？）。

**建议**：摘要加一行「其中 M 条本来就在审批中」（前端数 `note` 即可，
不需要改契约）。

**触发条件**：下一次动批次结果弹窗时。

## TODO-125: `POST /streams/batch-submit` 的 `stream_ids` **没有硬上限** ✅ 已闭环（2026-11-04）

**现状**（2026-11-03 · P9B-3b 整支分支评审 Minor #5）：
`app/schemas/stream_batch.py` 的 `stream_ids` 只有 `min_length=1`
⇒ 客户端可以 POST 100 万个 id；service 先做 `dict.fromkeys` 去重（O(n) 内存）
**再**比动态上限 ⇒ 一次请求能吃掉不少内存。

**为什么没在本批修**：上限是**动态的**（读系统参数）⇒ 不能简单写死
`max_length` ⇒ 需要决定「硬上限取多少」（如 1000）。

**建议**：schema 上给一个宽松的**硬上限**（如 `max_length=1000`）做兜底，
动态上限仍由系统参数控制（两者取小）。

**触发条件**：安全审计或容量评估时。

## TODO-126: `system_setting_service.py` 的注释说批次上限「**本批无消费者**」 ✅ 已闭环（2026-11-04）

**现状**（2026-11-03 · P9B-3b 整支分支评审 Minor #6）：
`app/services/system_setting_service.py` 的 `DEFAULT_SETTINGS` 注释写着
「`stream.batch_submit_limit` 在本批**无消费者**（批量提交在 P9B-3b）」——
但 P9B-3b **就是**本批，它现在**有**消费者了
（`stream_batch_service.py::_batch_limit`）。

**为什么没在本批修**：一行注释，但它在**别的文件**（`system_setting_service.py`）⇒
属「本批范围外的小清理」。

**建议**：把那半句改成「消费者：`stream_batch_service._batch_limit`（P9B-3b）」。

**触发条件**：下一次动 `system_setting_service.py` 时。

## TODO-127: 403 的文案对**写操作**说「无权查看」 ✅ 已闭环（2026-11-04）

**现状**（2026-11-03 · P9B-3b 整支分支评审 Minor #3）：
`pcs-frontend/src/api/errors.ts::describePcsError` 对 403 一律返回
`无权查看：${message}` ⇒ 页面把它用在**批量提交校对**上 ⇒
用户看到「无权查看：需要角色 [...]」—— 但他刚才在**写**，不是在**看**。

**为什么没在本批修**：`describePcsError` 是**全仓共用**的 helper
（几十处调用）⇒ 改它影响面大；评审员也明确建议「本批最小改法是在批量这一处
不用 `describePcsError` 的权限分支，或换个 fallback 文案」。

**建议**（二选一）：
① 给 `describePcsError` 加一个**可选**参数（如 `permissionVerb = '无权查看'`）
⇒ 批量提交这处传「无权提交」⇒ **默认行为不变**（其余调用点无感）；
② 或批量这处不用该 helper，自己拼文案。

**触发条件**：下一次动 `errors.ts` 或批次结果弹窗时。

**相关**：P9B-3b 批次提交校对页（`src/pages/sim/StreamListPage.tsx`）。

---

## ✅ 2026-11-04：TODO-121~127 全部闭环（整批评审的 7 条 Minor）

**触发**：用户「清理minor」⇒ 把整支分支评审的 7 条 Minor 全部落地（不再只登记）。

| # | 修了什么 | 怎么验的 |
|---|---|---|
| 121 | **根因不是「数组没 key」** —— 是 `rowKey="pipe_class_id"`（**契约里没这个字段**！2026-10-19 bug-180 整组改名时**漏改**）⇒ **每行的 key 都是 `undefined`** ⇒ React key 警告 + **行的身份坏了**（选择/展开/局部更新都错配）。改 `rowKey="class_id"` ⇒ 浏览器实测 `data-row-key` 从**无属性**变成 `pc-001`~`pc-004` | 新增**棘轮** `tests/pages/rowKey_contract.test.ts`：扫全部页面的 `rowKey="字段"` ⇒ 断言该字段**既在契约里、也在手写类型里** ⇒ **整类缺陷**（改名漏改 rowKey）以后都会红 |
| 122 | `int(True) == 1`（bool 是 int 的子类）⇒ 上限**静默变成 1** ⇒ 批量提交 2 条就被 422 拒，而参数页显示「true」⇒ 用户看不懂。⇒ `int()` 之前先 `isinstance(raw, bool)` 排除（**不能靠 `int()` 抛异常兜** —— `int(True)` 不抛） | RED（整批 422）→ GREEN；新增 `test_batch_limit_treats_boolean_as_garbage` |
| 123 | 换筛选**不清行选择** ⇒ 勾了 5 行、换筛选只剩 3 行可见 ⇒ 提交的是 **5 条**（含 2 条看不见的）。⇒ `setFilter` 里先 `setSelectedIds([])` | RED（按钮仍 enabled）→ GREEN |
| 124 | 摘要「成功 N」**包含幂等命中**（那条本来就在审批中、**并没有真提交**）⇒ 用户以为提交了 N 条。⇒ 摘要下补一行「其中 M 条本来就在审批中」 | RED（摘要只有「成功 2 · 失败 0」）→ GREEN |
| 125 | `stream_ids` **无硬上限** ⇒ 客户端可 POST 100 万个 id ⇒ 服务端先**反序列化**一百万个 UUID 再比上限。⇒ 请求体加 `MAX_STREAM_IDS_PER_BATCH = 1000`（Pydantic **逐个追加时**就停 ⇒ 连反序列化都省了）；服务端上限**与之取小** | RED（导入失败）→ GREEN |
| 126 | `system_setting_service.py` 的注释说批次上限「本批无消费者」⇒ 已改成实际消费者 `stream_batch_service._batch_limit` | 注释修正 |
| 127 | 403 文案对**写操作**说「无权查看」。⇒ `describePcsError` 加**可选**参数 `permissionVerb`（默认「无权查看」⇒ **其余几十个调用点无感**），批量提交这处传「无权提交」 | RED（文案是「无权查看」）→ GREEN |

⚠️ **TODO-121 的教训**：原本以为「antd 表格某列渲染数组没 key」⇒ 实际是
**`rowKey` 指向了一个契约里不存在的字段** ⇒ 症状（key 警告）指向 antd 内部，
真因在**页面自己的一行配置**上 ⇒ **只看堆栈会找错方向** ⇒
必须顺着「这个字段在契约里吗」查下去。

⚠️ **TODO-121 的棘轮也提醒了一件事**：允许集必须包含**手写类型**的字段
（`types/pipe.ts` 的 `seq` / 页面本地的 `CompositionRow.component` 等）
⇒ 否则会把**合法**的 rowKey 误报 ⇒ 误报的棘轮 ⇒ 没人敢用 ⇒ 很快被绕过。

---

## ✅ TODO-132: 已闭环（2026-11-11 · P9B-4 体验批 T0-B）

**本批修了什么**：**判定放在 actor 层**（`current_actor` 改 async + `Depends(get_db)`
⇒ 每请求查一次 `users.status`）⇒ 一处判定、**全局生效**（含 SYSTEM_ADMIN bypass）。
- **无行 ⇒ 放行**（mock 登录不落 `users` 表 · ADR-0046 §③b ⇒ 判拒会让 dev/E2E 全线挂掉）。
- `ws.py::_authenticate` 是**唯一**非 `Depends` 的直接调用点 ⇒ 一并改 async。
- 实测开销（真实 PG · 100 次）：P50 **0.198ms** / P95 **0.297ms** / P99 **0.380ms**
  ⇒ 低于委员会 3ms 阈值 ⇒ 未触发「status 塞 token claim」的独立批预案。

⚠️ **改行为 ⇒ 文档同 commit 同步**（代码与 ADR **同一个 commit**）：ADR-0046 §⑤ +
「已知边界」+「后果」三处 + UI-SPEC §7.1 + V2.12 ⇒ 「停用后 access token 仍可用
至多 30 分钟」**不再成立**（⇒ 改成「**两道闸**：token_version（refresh 时校验）+
users.status（每请求校验）」）。
⚠️ **角色变更仍不立即生效**（`users.roles` 仍只在登录时写 ⇒ 见 TODO-134）。

**证据**：`tests/api/v1/test_user_disabled_guard.py`（8 例）+ ws 用例 2 例 + 后端全量绿。

**现状**（2026-11-10 · ce-code-review `20261109-181644-6f6ddca3` 的 residual risk
第 1 条 · 委员会要求**升格为 TODO**）：

`UserProjectService.check_user_project_access` 只查 `user_projects` 有没有有效授权行
⇒ **不看 `users.status`** ⇒ 一个被**禁用**（`status=DISABLED`）的用户，只要还有一条
未撤销的授权行，**仍然能访问物流面 20+ 个受守卫端点**（读物流详情、状态点、属性、
血缘，以及写：改、删、提交校对、批量提交……）。

⚠️ 现实登录路径在**发 token 时**拦了禁用用户（`token_issuer` ⇒ `USER_DISABLED` 401），
⇒ 已持有的 **token 仍有效**（除非靠 `token_version` 失效）⇒ 这段时间里禁用是**形同虚设**。

**归属**：独立技术债（与 P9B-4 紧急批次**无关**，是守卫面扩大后暴露得更明显）。

**建议改法（2026-11-10 委员会裁决）**：**在 actor 层判**（`current_actor`），
**不在守卫层 join** ⇒ 一处判定、全局生效（含 SYSTEM_ADMIN bypass 与将来新增的
bypass 路径）⇒ `current_actor` 改 **async + `Depends(get_db)`**，
`status == DISABLED` ⇒ 401 `USER_DISABLED`；⚠️ **`users` 表无该行 ⇒ 放行**
（mock 登录不落 `users` 表 ⇒ 否则 dev/E2E 全挂）。

⚠️ **连带义务**：**ADR-0046 §⑤ + 「已知边界」要改** —— 「停用后 access token 仍可用
至多 30 分钟」在每请求查 status 后**不再成立**（停用立即生效）⇒ `token_version`
（refresh 比对）**仍在** ⇒ 改写成「**两道闸**」。

⚠️ **另一个连带点**：`app/api/v1/ws.py` 里 `current_actor(...)` 是**直接调用**
（不是 `Depends`）⇒ 必须一并改，否则 WebSocket 握手断。

⇒ 落地批次：**P9B-4 体验批 T0-B**（P1）。

## ✅ TODO-133: 已闭环（2026-11-11 · P9B-4 体验批 T0-C）

**本批修了什么**：`create_stream` / `validate_stream` **一律**用
`project.workspace_id` ⇒ 请求体里的 `workspace_id` **被忽略**
（字段保留但标 `deprecated` ⇒ 非破坏性契约变更）。
⚠️ **静默纠正的取舍**：传了别的项目的 `workspace_id` ⇒ **不报错**（创建成功 201），
但落点 = URL 那个项目的工作区 ⇒ **数据落在正确的地方**（不是越权）⇒ 比报错更
接近「零影响」（前端**根本不发**这个字段 ⇒ 报错路径没有真实调用方）。
⚠️ `/validate`（预演）**同口径** ⇒ 预演结论与实际落点**同一口径**。

**证据**：`tests/api/v1/test_stream_workspace_ownership.py`（4 例）。

**现状**（2026-11-10 · 同上报告 residual risk 第 2 条 · 委员会要求**升格为 TODO**）：

`POST /projects/{project_id}/streams` 的 `workspace_id` 取自**请求体**
（`req.workspace_id or project.workspace_id`）⇒ **从不校验它属于 URL 里的那个项目**
⇒ 只拥有项目 A 权限的用户可以把物流**挂到项目 B 的工作区**下。

⚠️ 本批给 `create_stream` 补了**项目守卫**（守卫的是 URL 的 `project_id`）⇒
**工作区那一维仍然是缺口** ⇒ 跨项目写入仍然可能发生（只是落点不是 URL 的项目）。

**归属**：独立技术债（与 P9B-4 紧急批次**无关**，守卫没覆盖工作区这一维）。

**建议改法（2026-11-10 核实 + 裁决）**：**忽略请求体、强制用 `project.workspace_id`**
⇒ ✅ **已核实前端不用这个字段**：`grep -rn "workspace_id" pcs-frontend/src/pages/sim/
pcs-frontend/src/api/stream.ts` ⇒ **0 命中**；且 `StreamCreatePayload` 的
`Pick<...>` 字段清单里**没有** `workspace_id` ⇒ 前端根本发不出。
⇒ 契约里该字段**保留但标 deprecated**（删字段 = 破坏性契约变更）。

⇒ 落地批次：**P9B-4 体验批 T0-C**（P1）。

## ✅ TODO-134: 已闭环（2026-11-11 · P9B-4 体验批 T0-E）

**本批修了什么**：`issue_tokens` 的**真实分支**在「行已存在」时把真实角色
**覆盖**进 `users.roles`（`roles=[role]` —— **不是合并**）。
⚠️ **mock 分支绝不碰 roles**（ADR-0046 §③b：mock 与真实 AD 同名 ⇒ 写真实角色
⇒ 污染同一行 ⇒ 权限污染且不报错）⇒ mock 路径仍在「一次 DB 往返都没有」的位置
早返回 ⇒ 对照组用例钉住。

⚠️⚠️ **口径更正（2026-11-12 · P9B-4 评审 #13）**：本条**曾经**写成「**合并**」
⇒ 那是 `69b2327` 的实现 ⇒ **已被 `4a8e882` 推翻**（整批评审 Important #1）⇒
**当前实现是「覆盖」**，理由：`users.roles` 的权威来源是**真实身份** ⇒
AD 同步（`ad_sync._apply`）也是**覆盖**（`roles=[role] if role else None`）
⇒ 两处口径必须一致 ⇒ **只增不减会让「角色降级」永不生效** ⇒ 按 `users.roles`
圈人的通知逻辑会**继续找**已降级的人（「待办里有、点进去说你不是」）。

⚠️ **覆盖的代价（此前无处可查）**：一个 `users` 行若带**多个**角色 ⇒ 真实登录
**只保留最后一个角色** ⇒ `notification_recipients.resolve_role_recipients`
**不再**为被丢掉的那些角色选中该用户 ⇒ 「通知只发最后一个角色」是**已知取舍**。

**证据**：`tests/test_token_issuer.py` +4 例（含 **mock 不改 roles** 对照组、
**覆盖**（`seeded2`）与**幂等**（`seeded3`）两条口径用例）。
⚠️ `fix_commit` 指向**落地「覆盖」的那次提交** `4a8e882`（不是 `69b2327`）。

**现状**（2026-11-10 · 同上报告 residual risk 第 3 条 · 委员会要求**升格为 TODO**）：

`ensure_user_row` 建行时 `roles=[]`（**刻意**：ADR-0046 §③b 禁止 mock 登录往
`users.roles` 写角色）⇒ 而真实登录路径（`token_issuer`）**只在自己建行时**写 roles，
**不会更新已存在的行** ⇒ 一个先被 seed 脚本建出来、之后才走真实登录的用户，
**`users.roles` 永远是 `[]`** ⇒ `notification_recipients.py` 之类**按 `users.roles`
圈人**的逻辑**永远选不到他**。

**归属**：独立技术债。

**建议改法**：真实登录路径在**已存在**的行上也**合并**真实角色（而非只在建行时写）
—— 但要绕开 ADR-0046 §③b 的「mock 与真实 AD 同名 ⇒ 污染同一行」问题
（mock 登录**不得**写真实角色，真实登录**可以**写真实角色）。

## ✅ TODO-135: 已闭环（2026-11-11 · P9B-4 体验批 T0-F）

**本批修了什么**：① 新开关 **`PCS_ENABLE_MOCK_LOGIN`**（**默认关**）⇒ 启用条件
**双闸**（非生产 **且** 显式 opt-in）⇒ 部署时忘了配 = 安全的；
② 生产里开关开着 ⇒ **启动即失败**（部署期断言 · 矛盾配置 fail-fast）；
③ `.env.example` + README 写明 dev 要显式打开。

⚠️ **顺带修好一条既有空转的断言**：旧的「生产里 mock 路由不得挂载」断言
**一直是空转** —— FastAPI ≥ 0.141 改成**懒挂载** ⇒ `include_router` 进来的 router
在 `app.routes` 里是一个**没有 `path` 属性**的包装对象 ⇒ 只遍历 `app.routes`
**漏掉整棵子树** ⇒ 断言**升级后失效了，却一直绿** ⇒ 改成按 **OpenAPI 的实际路径**判。

**证据**：`tests/test_mock_auth.py` 14 例（闸门矩阵 4 种组合 + 默认关 + 环境变量名
+ 部署期断言 3 例）。

**现状**（2026-11-10 · 同上报告 residual risk 第 4 条 · 委员会要求**升格为 TODO**）：

`auth.py::mock_login` 给四个固定用户名签发**任意 role claim** 的 token
⇒ 这是一条**完整的鉴权旁路**（拿到 token = 任意角色）。
⇒ 现在**只**靠两道闸：① `settings.is_production`；② 该 router **不在生产挂载**。

⚠️ 闸门回归（配置写错 / 挂载代码改动）⇒ 就是**完整 auth bypass**。

**归属**：独立技术债（与 P9B-4 紧急批次**无关**）。

**建议改法**：mock 登录的启用条件**双闸**（`is_production` **且** 显式的
`PCS_ENABLE_MOCK_LOGIN=true`）+ 给「mock 路由未挂载」加一条**部署期断言**
（启动时检查生产环境里没有 mock 路由）。

## ✅ TODO-136: 已闭环（2026-11-11 · P9B-4 体验批 T0-D）

**本批修了什么**（委员会裁决的三步全做）：
1. **快照** ✅（前端只查 `streams`；能写出的类型 = `RECORD_TYPE_REGISTRY` 的 21 个，
   20 个有 `project_id`、1 个没有）；
2. **补已知** ✅ —— 注册表**从 `RECORD_TYPE_REGISTRY` 派生**（新文件
   `app/services/lineage_registry.py`）⇒ **不手写第二份**；pk 列用
   `inspect(model).primary_key[0].name`；**键 = `model.__name__`**（写入方写进
   `data_lineage.record_type` 的就是**类名** ⇒ registry 的 5 个非类名键
   **抄不得**，抄了就永远匹配不上）；`streams` **单独登记**（入口专用键）；
3. **未知 fail-closed** ✅ —— 未登记的 `record_type` ⇒ **404**（与「记录不存在」
   **逐字同形**）⇒ 不再是「可枚举信号」（此前 `/upstream` 对未知类型返 200+[]）。

**顺带**：① `/lineage/streams/{id}/graph` 补「**按源引用查**」（`source_ref_type='Stream'`）
+ **合成 root**（确定性 uuid5 · 10 字段与真实 root **同形**）；
② 血缘 graph 响应改**具名 schema** `LineageGraphResponse {root, upstream, downstream}`
（**三键形状不变** ⇒ 前端零改动）。

**证据**：`tests/api/v1/test_lineage_by_source_ref.py`（33 例 · 含 20 个已登记类型
的**参数化**跨项目 404 + 本项目 200 对照 + 镜像测试）+ 前端 4 例。

**现状**（2026-11-10 · ce-code-review 的 **#6 rejection** 的残余 · 委员会要求登记）：

`app/api/v1/lineage.py::LINEAGE_GUARDED_RECORD_TYPES` 只有两项
（`PipingResult` / `streams`）⇒ **未登记的 `record_type` 直接跳过守卫**
（fail-open）。

⚠️ ce-code-review 把「fail-open」判为 **pre-existing**（改前是
`if record_type != "PipingResult": return`）⇒ **本批不修**（收窄了暴露面，
不是引入）。
⚠️ 但**注册表这个机制**是本批引入的 ⇒ 它**允许**新增类型被遗漏 ⇒ 这条要登记。

⚠️ 另外两个**不一致**也要一并记：
① 注册表的键**混用两种口径**（`PipingResult` 是**类名**（写入方存的就是类名），
`streams` 是**表名**）⇒ 写方用 `record.__class__.__name__` ⇒ 按表名登记的那一项
**匹配不上**写入方的值；
② 前端调的是 `/lineage/streams/{id}/graph`（表名拼写）⇒ 与写入方的类名拼写**不一致**
⇒ 物流的血缘图**永远是空的**。

**归属**：与 TODO-129（物流面之外的守卫覆盖审计）**是一对**。

**建议改法（2026-11-10 委员会裁决 = 分三步，不是二选一）**：
1. **快照**（✅ **已实测**：前端只查 `streams` 一个类型；后端能写出的类型 =
   `RECORD_TYPE_REGISTRY` 的 **21 个**，其中 **20 个有 `project_id`**、
   **1 个（`TwoPhaseResult`）没有**）；
2. **补已知** —— 把那 20 个类型补进守卫注册表 ⇒ **从 `RECORD_TYPE_REGISTRY` 派生**，
   别手写第二份；主键列用 `inspect(model).primary_key[0].name` 取，别硬编码；
   **键口径统一成写入方用的类名**（写入方写的就是类名 ⇒ 统一到类名；
   而 `streams` 是「按源引用查」的**入口键**，不是写入方的键 ⇒ 注释写明区别）；
3. **未知 fail-closed** —— 未登记的 `record_type` ⇒ 与「无血缘」**同形**的 404
   （不能成为可枚举信号）；再加一条**镜像测试**（所有能写出的 `record_type`
   都在注册表里 ⇒ 用 `RECORD_TYPE_REGISTRY` 的键参数化断言）。

⚠️ **`TwoPhaseResult` 没有 `project_id`** ⇒ 无法登记 ⇒ fail-closed 下永久 404
⇒ 另立 **TODO-138**。

⇒ 落地批次：**P9B-4 体验批 T0-D**（P1）—— ⚠️ 成本从「半天」升到「**一天到一天半**」。

## TODO-140: 「设备引用（JSONB 数组）」**是否**计入 📎×N ✅（已裁决 · 维持不计）

**裁决**（2026-11-11 · 用户裁决 **Q8 = ① 维持不计**）：「引用 📎×N」**继续不含**
设备引用 ⇒ SPEC §7.7.1 已写明（V2.15）。

**为什么没含**（四条障碍，缺一不可）：
1. **装的是 SID 字符串、不是 UUID** —— `sim_unit_op_results.feed_streams_json` 等
   4 个 JSONB 列里是 **PRO/II 的 stream tag**（`proii_parser.py:889/1014`）
   ⇒ 落到 `streams` 上只能按 `stream_name` **字符串 join**
   （`stream_name` 的唯一约束是 `(project_id, stream_name)` ⇒ 必须同时带项目条件）；
2. **设备结果表没有 `project_id`** ⇒ 要绕 `import_id → sim_imports.project_id`；
3. **JSONB 数组无索引** ⇒ `jsonb_array_elements_text` 是**全表扫**
   ⇒ 列表页**每行每次请求**都要算；
4. **口径未定义** —— 「进料 / 出料 / 塔侧线 / 计算器序列」各自算不算，
   要**逐设备类型**定。

**触发条件**（翻案）：用户问「这条物流被哪些设备用了」⇒ 重新评估 ⇒ 那时做成
**详情页「设备连接」Tab 的反查**（单条查询、允许慢、允许人工核对），
**不是**列表页的每行计数。

⇒ 归属：独立技术债（**已裁决 · 触发式重开**）。

## ✅ 2026-11-12：P9B-4 评审修复批 —— 19 条 finding 全部闭环

**触发**：用户「开始按队列修复」⇒ 把 `ce-code-review` 报告
（`docs/ce-code-review/20261111-181548-7b8a5dca/report.md`）+ `hermes`
（GLM-5.2 跨模型对抗审查）的 **19 条** finding 全部落地。

**用户裁决（4 条）**：血缘角色 = **沿用 streams 白名单**；停用覆盖面 =
**全部补齐**（WS 投递路径复检 + `current_user` 也判）；CSV 导出 = **加「引用」列**；
批末 = **重跑一次** gstack 浏览器回归。

| # | 修了什么 | 怎么验的 |
|---|---|---|
| 1 | 前端不认 `USER_DISABLED` ⇒ 停用用户**带在手 token 卡在任意业务页**、永不回登录页 ⇒ 加进 `SESSION_OVER_CODES`（+ 同形状的 `REFRESH_REVOKED`） | 新增 `tests/api/session_over_codes.test.ts`（5 例，含**二次认证失败不许登出**的对照组）RED→GREEN |
| 3 | 血缘三端点**绕过物流角色门** ⇒ `VIEWER`/`REVIEWER`/`CHECKER` 从 `GET /streams/{id}` 拿 403 却能从血缘端点读物流字段 ⇒ 统一 `require_roles`（**在项目守卫之前** ⇒ 不泄漏存在性） | `test_lineage_endpoints_use_the_streams_role_whitelist`（3 角色 × 3 端点）RED→GREEN |
| 4 | 同一行血缘在兄弟端点**两种表示**（`Z` vs `+00:00`）⇒ 三端点统一 `LineageNode` 具名 schema | `test_same_lineage_row_has_one_representation_across_endpoints` RED→GREEN |
| 6 | WS 长连接是「停用即刻」的**例外**（握手只查一次）⇒ **投递前复检**账号状态 ⇒ 停用 ⇒ 关连接 + 不投递 | 新增 `_make_sink()` + 两条用例（停用 ⇒ 不投递且关连接 / 正常 ⇒ 照常投递）RED→GREEN |
| 7 | 握手期 DB 故障**不是** `PcsError` ⇒ 逃出处理器 ⇒ **裸 500 且无日志** ⇒ 加非 `PcsError` 兜底（记日志 + 同形关连接） | `test_ws_handshake_db_failure_closes_instead_of_500` RED→GREEN |
| 8 | 部署期断言在 mock 路由**已挂载但对 OpenAPI 隐身**时**报绿** ⇒ 断言**另看路由表**（递归展开懒挂载 + 累加 prefix） | `test_production_with_mock_route_hidden_from_openapi_still_fails_startup` RED→GREEN |
| 9 | fail-closed 守卫让 **PSV 血缘永久 404**（`PsvResult` 不在 `RECORD_TYPE_REGISTRY` —— 那张表是**表枚举**不是写入方清单）⇒ 显式登记 + 加**不依赖那张表**的契约测试 | `test_every_calc_result_model_is_registered_in_the_guard` + `test_psv_result_lineage_is_queryable` RED→GREEN |
| 10 | 「判定只在一处」是**假的**（比较散在**三处**：每请求 / 登录 / AD 同步）⇒ 抽出共享谓词 `is_disabled_status()` + 源码扫描的**棘轮测试**（`== UserStatus.DISABLED` 在 `app/` 里只许出现一次） | `tests/services/test_user_status_service.py`（9 例）RED→GREEN |
| 11 | 「未登记类型」与「记录不存在」的 404 **逐字同形**没被钉住 ⇒ 三端点各一条 | `test_unknown_record_type_404_*` RED→GREEN |
| 13 | 账簿（`TODOS.md` + `buglog.json`）写「**合并**」而代码是「**覆盖**」⇒ 下一个读账簿的人会把合并恢复回去 ⇒ 两处改口径 + `fix_commit` 指向 `4a8e882` + 补**覆盖的代价** | 账簿复核（本条本身即文档） |
| 14 | `admin_users` docstring 还写「在手 access 仍可用 30 分钟」⇒ 与 ADR-0046 §⑤ **矛盾** ⇒ 改成「停用即刻 / **角色变更**不即刻」 | 文档复核 |
| 15 | 守卫的返回值被丢弃、行被重查 ⇒ 把守卫返回的行传下去（省一次查 + 删掉不可达的 404 分支） | 由 #4 的用例覆盖 |
| 16 | `current_user` **不判账号状态** ⇒ `GET /auth/me` + 6 个 `GET /meta/*` 对停用用户**照样 200** ⇒ 前端会话自查返回「有效」⇒ **僵尸会话** ⇒ `current_user` 改 async + `Depends(get_db)` | 新增 `tests/api/v1/test_disabled_user_endpoints.py`（7 例，含**无行 ⇒ 放行**与**正常用户不受影响**两条对照组）RED→GREEN |
| 20 | 刷新列表失败被报成「**批量提交失败**」（而那批其实已提交成功）⇒ **两个错误域**：提交失败仍抛，刷新失败吞掉（不清摘要、不 rethrow） | `useStreamBatchSubmit.test.ts` 新增一例 RED→GREEN |
| 23 | 删除被**下游物流**引用的物流 ⇒ 撞 FK（无 `ondelete`）⇒ `IntegrityError` **不是** `PcsError` ⇒ **裸 500** ⇒ `_collect_references` 补第三张表 + `commit()` 兜 `IntegrityError`→409 | `test_delete_blocked_when_downstream_stream_references` RED→GREEN（SQLite 不强制 FK ⇒ 服务层缺口先显形） |
| 24 | WS 拒绝原因在**真实传输**里**不可见**（accept 前 close ⇒ HTTP 403）⇒ 选**最小方案**：原因**写日志** + docstring **不再**承诺客户端可区分 | 文档复核（见下方「已知边界」） |
| 25 | **并发首次登录** ⇒ 两个请求同时「SELECT 见空」⇒ 都 INSERT ⇒ 输家撞唯一约束 ⇒ **裸 500**（偶发 ⇒ 极难复现）⇒ 撞车 ⇒ 回滚 ⇒ 重读 ⇒ 照常签发 | `test_concurrent_first_login_race_does_not_become_a_500` RED→GREEN |
| 26 | `StreamListPage` 模块 docstring 说「引用列本批不渲染」，而**同一文件里就渲染着** ⇒ 改成实况 | 文档复核 |
| 27 | CSV 导出**漏「引用」列** ⇒ 导出件与屏幕所见不一致 ⇒ 表头 + 数据行补「引用」（导出用 **0**，不用表上的「—」⇒ Excel 能求和） | `StreamListPage.test.tsx` 新增一例（拦 `createObjectURL` 取 Blob）RED→GREEN + **浏览器实测**导出文本 |

**批末回归**：`gstack` 浏览器回归**重跑**（评审 #2 指出的缺口：上一份报告跑在
批末前两个提交上）⇒ **8 条路由全绿 · 控制台 0 error · 网络 0×404/0×500**
⇒ 导出实测含「引用」列且**逐条与表里的 📎N 一致** ⇒ 血缘 Tab 时间戳已是 `Z`
⇒ 报告 `.gstack/qa-reports/qa-report-pcs-frontend-2026-11-12-p9b4-review-fixes.md`
（批末 HEAD `4032617`）。

**基线**：后端 **5662 passed**（+39）· 前端 **116 files / 1053 tests**（+7）·
裸载荷 **71**（未涨）· **零迁移**。

⚠️ **两条诚实边界**（**不是**缺陷 ⇒ 写进文档，不再假装已解决）：

1. **WS 拒绝原因只对日志可见** —— ASGI 规定 accept 前的 close 被服务端当成
   **HTTP 403 握手拒绝** ⇒ close code（1008）与 reason（`USER_DISABLED` 等）
   **到不了客户端** ⇒ 每种拒绝在客户端看来**完全一样**。
   ⚠️ Starlette 的 `TestClient` 却把它还原成 `WebSocketDisconnect(1008)`
   ⇒ **测试观察到的是部署里不存在的拒绝语义**。
   ⇒ 要让原因**真正**到达客户端必须**先 accept 再 close** ⇒ 那是**传输层变更**
   （客户端会看到「连上了又断」）⇒ **独立设计裁决**，不在本批顺手做。
   ⇒ **已登记 TODO-144**（含两个选项与触发条件）。
2. **遗留账号行**（`user_id` ≠ 派生值 · **TODO-137**）上，登录路径（按 username）
   与每请求路径（按 `user_id`）**会给出相反结论** ⇒ 停用的遗留账号
   **登录被拒、手里的 token 却还能用** ⇒ 已写进
   `app/services/user_status_service.py` 的模块 docstring + ADR-0046 §⑤
   + 一条钉住的测试 ⇒ **已登记 TODO-145**（首选：随 TODO-137 的迁移一并消失）。

---

## TODO-149: P10-B 开工前先量一次「18 个 E2E 场景的种子数据规模」 ✅ 已答（2026-11-13）

**结论（不必再量）**：**种子不扩量** —— 缺的**不是数据规模，是角色维度**。

**理由**（P10-B 计划 `docs/superpowers/plans/2026-11-13-p10-batch-b-fullflow-e2e.md`）：

- **计算链的输入写在场景里**（与现有单测的合成输入同源）⇒ 种子**不灌**输入
  ⇒ 种子规模与「要跑几个计算域」**解耦** ⇒ 场景加到 18 个，种子**一行都不用加**。
  ⚠️ 因此**不取** `sample/` 的真实 PRO/II 工程（不入 git ⇒ 别的机器没有 ⇒ 车道不可移植）。
- 种子真正要补的是 **角色矩阵**：6 个用户（全局角色各异）× **项目内**角色各异
  ⇒ 权限矩阵（AUTH-E2E-01~10）才有东西可测
  ⇒ 现种子的项目内角色**统一 `DESIGNER`** ⇒ 权限矩阵**测不出来**。
- 种子只造**起点态**（DRAFT 记录 / DRAFT 交付物 / 签署矩阵）⇒ 其余状态由场景
  **走真实端点**推进 ⇒ 否则 E2E 只是「断言一个摆好的状态」。

⇒ 实现落在**新脚本** `scripts/seed_e2e_flows.py`（T2）⇒ 现有
`scripts/seed_e2e_data.py`（冒烟级，服务真后端 Playwright 通道）**不动**。

---

## TODO-156: PRO/II 解析器**不抽组成** ⇒ 导入的物流**进不了计算链** 🟡

**现状**（2026-11-16 · P10-B 的 E2E-002 撞出来的）：

`app/services/import_service.py:135` 明写：「**PRO/II parser 当前不提取 composition**
（SIM-10 MVP 仅 T/P/flow/phase 落库）」⇒ 导入出来的物流 `composition_json is None`
⇒ ⇒ **计算链的入口不收**（flash 那条路要求有组成）
⇒ ⇒ **「导入 ⇒ 直接算物性」这条路今天走不通**。

**为什么重要**：SPEC §3.2.2 的 E2E-002 写的是「导入 ⇒ 物性补全」
⇒ 现在只能**拆两段**测（导入段 + 物性补全段）⇒ **中间那一环没被覆盖**。

**何时做**：**P10-C 或 P10-F**（与「PROII 解析补组成」一起做）
⇒ 补法：解析 `.inp` 的组分表 ⇒ 写进 `composition_json`（摩尔分率）
⇒ ⚠️ 注意组成门禁（`app/api/v1/streams.py::_composition_gate`）要求
**100±0.5%** ⇒ 解析出来的摩尔分率必须归一 ⇒ 否则送审直接 422。

**归属**：**P10-C · 前端收口子批**（人裁决 2026-11-18 · `docs/superpowers/plans/2026-11-18-p10-c-frontend-closure.md`）
⚠️ **本条是后端项**（PRO/II 解析器）⇒ ⇒ **搭车**该批收口（批内单列）。

### ✅ **已关闭 · 2026-11-19 · P10-C · T4 · `bbea848`**（人裁决：**「我补 CAS 号并标注待确认」**）

⇒ ⇒ **链路打通**：`.inp` 的 `COMPOSITION(M|W)` ⇒ ⇒ **`{CAS: 摩尔分率}`**
⇒ ⇒ 落进 `composition_json` ⇒ ⇒ 送审的组成门禁（100±0.5%）能过
⇒ ⇒ 「导入 ⇒ 直接算物性」这条路**通了**。

⇒ ⇒ **四个必须记住的点**（都是踩出来的）：

1. **基准（M / W）必须保留** —— PRO/II 的 `COMPOSITION(M)` 是**摩尔**分率、
   `COMPOSITION(W)` 是**质量**分率 ⇒ ⇒ 丢掉它 ⇒ ⇒ 质量分率被当成摩尔用
   ⇒ ⇒ 组成**完全错** ⇒ ⇒ 解析器此前**把 M/W 标记丢了**（本批补上）。
2. **数值是百分数**（0~100）⇒ ⇒ 不是 0~1 的小数 ⇒ ⇒ 用之前先 /100。
3. **「宁可没有组成，不要错组成」** —— **有一个组分认不出来 ⇒ ⇒ 整个组成为空**
   （`composition_json = None`）+ 告警写明是哪些组分
   ⇒ ⇒ 缺一个组分的组成送进闪蒸 ⇒ ⇒ 算出**错**的结果 ⇒ ⇒ 比没组成危险得多。
4. **归一是必要的** —— 样例里原始和**不是** 100（`sample/dmc.inp` 的 S18 =
   99.9648%）⇒ ⇒ 归一到 1.0 后才过门禁（⇒ ⇒ 门禁判的是「录入者填的组成
   自洽吗」，而导入的组成是**机器算出来的**）。

⇒ ⇒ **新增**：`app/services/component_cas.py`（规范名 → CAS · **域数据**）·
`app/services/proii_composition.py`（换算 · 归一 · fail-closed）·
`tests/fixtures/proii/sample6_composition/`（含 M / W / 认不出的组分三种流）·
`tests/services/test_proii_composition_mole.py`（8 例）。

⇒ ⇒ **变异自证**（三条各自变红）：丢基准 ⇒ 解析器那条红 · 不落组成 ⇒ 导入那条红 ·
去掉 fail-closed ⇒ 「认不出 ⇒ 整条作废」那条红。

⇒ ⇒ ⚠️ **CAS 号待工艺室确认** ⇒ ⇒ 已登记 **TODO-196**（10 个 DMC 专用组分）。

## TODO-157: 前端**没有设备清单页**（`/equipment-list` 有端点无页面） 🟡

**现状**（2026-11-16 · P10-B 的 T7 撞出来的）：

后端有 `GET /api/v1/equipment-list`（`app/api/v1/equip_list.py`）· 种子也造了
设备（`132-P-101A/B`）⇒ 但**前端没有对应页面** ⇒
`src/types/api.d.ts` 里有生成的类型、**没有任何组件消费它**
⇒ ⇒ 「设备一览」页（`/config/asset-list`）列的是 **`ConfigAsset`**
（配置资产：公式/模板/系数表），**不是 `EquipmentList`（设备台账）**
⇒ ⇒ 两条「设备」概念在 UI 上**只有一条可见**。

**为什么重要**：P10-B 的 T7 原计划有一条「设备表：种子设备可见」的 UI 流
⇒ 改不成（页面不存在）⇒ 登记为 D36 ⇒ 设备台账这条线**前端没入口**。

**何时做**：**P10-C**（补一页设备台账，或明确「设备一览 = ConfigAsset」
且设备台账只走 API）⇒ 补的话要定：列表字段（位号 / 类型 / 厂家）·
项目作用域（`equipment_type_project_id`）· 与「冷却水子表」「换热器」
里手填 `equipment_tag` 的关系。

**归属**：**P10-C · 前端收口子批**（人裁决 2026-11-18 · `docs/superpowers/plans/2026-11-18-p10-c-frontend-closure.md`）

### ✅ **已关闭 · 2026-11-19 · P10-C · T3 · `bbea848`**（人裁决：**① 补一页设备台账**）

⇒ ⇒ 新页 `/equipment-list`（菜单「设备台账」**独立成组** ⇒ ⇒ 与「设备一览」
`/config/asset-list`（`ConfigAsset` 配置资产）**分开** ⇒ ⇒ 两条「设备」
概念在 UI 上**都可见**了）。

⇒ ⇒ **列表字段**（**以契约为准**）：位号 / 类型 / 名称 / 描述 / 厂家 / 型号 /
来源 / 采购状态 / 安装位置 / 设备状态 / 签署状态
⇒ ⇒ ⚠️ SPEC §7.13 里的「**包号**」「**单元**」「**计算状态**」**契约里没有**
⇒ ⇒ **不编**（编出来 = 幽灵列）⇒ ⇒ 登记 SPEC 修订（NOTE §6）。

⇒ ⇒ **项目作用域**：页面走 `useProjectScope` ⇒ ⇒ 拿**真** project id 调
`GET /equipment-list?project_id=…` ⇒ ⇒ **不是**占位常量。

⇒ ⇒ ⚠️⚠️ **顺带补上两个跨项目洞**（本批发现 · 建页时撞出来的）：
① **跨项目读**：`GET /api/v1/equipment-list` 此前**只有角色闸** ⇒ ⇒ 任何
DESIGNER / PROCESS_CONTROLLER 都能列**全部项目**的设备台账 ⇒ ⇒ 现在：
传 `project_id` ⇒ 该项目必须对我有授权（否则 **404**）⇒ 不传 ⇒ 只返回
**我有授权的项目**的设备（SYSTEM_ADMIN 全局 bypass）。
② ⚠️⚠️ **跨项目写**（**更严重**）：**sync** 的写入落在**源记录的 `project_id`**
上（`sync_from_source` 用的是它）⇒ ⇒ 而单条 sync 此前**只**查了
**equipment 行**的项目 ⇒ ⇒ 源记录在**别的**项目 ⇒ ⇒ **写进别的项目**
⇒ ⇒ **与 TODO-180「写面授权判 A、行落进 B」同形** ⇒ ⇒ bulk-sync 更是
**完全没查** ⇒ ⇒ 现在：单条 ⇒ ⇒ 无权 ⇒ **404**；bulk ⇒ ⇒ 逐条预检 ⇒
无权 ⇒ 标 `failed` 且**不写**。

⇒ ⇒ **教训**：写面守卫要判「**行实际落到哪儿**」⇒ ⇒ 不是判「请求里说的那个 id」。

⇒ ⇒ 8 例新测试（`strict_client`）+ **变异自证**（删读授权 ⇒ 3 例红 ·
删单条 sync 守卫 ⇒ 1 例红 · 删 bulk 预检 ⇒ 1 例红）。

⇒ ⇒ **证据**：前端 7 例页面测试 · 后端 8 例守卫测试 · 真后端扫描加了
「**种子设备 `132-P-101A/B` 可见**」的断言 ⇒ ⇒ 一条断言同时验了
真端点 + 项目作用域解析 + 页面渲染。

## TODO-159: 前端调用了**不存在的端点**的 3 个页面（真后端下打不开数据） 🟠

**现状**（2026-11-16 · P10-B 的 T8 路由扫描撞出来的）：

真后端通道（`--project=real-backend`）逐条走完 **44 条路由** ⇒ 三处请求
**404**（⇒ 页面拿不到数据、只能显示错误）：

| 页面 | 前端请求的端点 | 状态 |
|---|---|---|
| 管道一览表 `/pipe/line-list` | `GET /projects/{id}/pipe-line-list` | **404** |
| PMS 规格 `/pms` | `GET /projects/{id}/pms` | **404** |
| BEDD 文档 `/bedd` | `GET /projects/{id}/bedd` | **404** |

⚠️ **既有缺口**（不是 P10-B 引入的）⇒ mock 通道里 **MSW 有 handler** ⇒
一路绿灯 ⇒ **只有真后端通道能抓到**（与 bug-2169 同形）。
⇒ ⇒ 这三个页面的数据源**要么端点要补、要么前端该指向既有端点**
⇒ **先查契约**（`docs/openapi.json` 里有没有等价端点）⇒ 有 ⇒ 改前端指向；
没有 ⇒ 补后端端点（或明确「这三页是占位」并在前端说明）。

**何时做**：**P10-C**（前端补齐批次）⇒ 补完把 TODO 里的断言**加回**
`e2e/real_backend_route_sweep.spec.ts`（现在只打印不断言 ⇒ 故意留的）。

**归属**：**P10-C · 前端收口子批**（人裁决 2026-11-18 · `docs/superpowers/plans/2026-11-18-p10-c-frontend-closure.md`）

### ✅ **已关闭 · 2026-11-19 · P10-C · T2 · `75cece5`**

**查契约的结论**（`pcs-backend/docs/openapi.json`）⇒ **三个端点都不存在**
⇒ ⇒ 「改前端指向」这条路走不通（`GET /records/piping` 只返 5 字段，
管道一览表要 43 列）⇒ ⇒ 分两种处置：

| 页面 | 处置 | 依据 |
|---|---|---|
| `/pipe/line-list` | **补后端端点** `GET /projects/{project_id}/pipe-line-list` | 数据**确实存在**：`piping_results`（管道记录的**唯一真相源**）⇒ ⇒ 列清单 = **SPEC §7.11.2 的 43 列**逐条对应 ⇒ ⇒ 不再是「前端编的一份形状」 |
| `/pms` | **明确占位**（不发请求） | 后端**没有** PMS 实体与端点 ⇒ ⇒ 最接近的 `pipe_classes`（管道等级）**是另一个东西** ⇒ ⇒ 拿它冒充 = 答非所问 |
| `/bedd` | **明确占位**（不发请求） | `projects.bedd_json` 这一列**存在**，但**没有任何写入路径**（全仓只有建表迁移提到它）⇒ ⇒ 补出来的端点**永远返回空** ⇒ ⇒ 「看起来有、其实永远空」比没有更坏 |

⇒ ⇒ **前端同时改了**：
1. 新增 `useProjectScope` hook ⇒ 从 `GET /workspaces` 解析**真** project id
   （**不再用**占位常量 `00000000-…-0001` ⇒ 那**不是真项目**）
2. `PipeLineListRow` 改成**契约类型**（此前是前端手写的 25 列，
   含 4 个**后端根本没有**的列 ⇒ 幽灵字段）
3. PMS / BEDD 两页**明写**「数据源尚未接入」（占位说明 + 依据）
4. 真后端扫描的**白名单删掉 TODO-159 那三条** ⇒ ⇒ 白名单现在**是空的**

⇒ ⇒ **证据**：后端 5 例新测试（含变异自证：删授权 ⇒ 2 例红）·
前端 5 例路由测试 + 4 例 hook 测试 · vitest 1082/1082 · typecheck / lint clean。

⇒ ⇒ **连带修掉一个三年前的洞**：`tests/mocks/handlers.test.ts` 的
「devOnly ∩ 契约」棘轮**直接拿 MSW 的 `:param` 路径**比契约的 `{param}` 路径
⇒ ⇒ **永远不相等** ⇒ ⇒ 凡是用 `:param` 写的 mock 端点，**这条棘轮看不见**
⇒ ⇒ 补了路径归一化 ⇒ ⇒ **多出 14 条**「已进契约却没 ajv 校验」的端点
⇒ ⇒ 登记为 **TODO-193**（欠账不许悄悄消失：清单里少一条就红）。

## TODO-160: 物性/许用应力/毒性三页**首屏 422**（空查询打后端） 🟡

**现状**（2026-11-16 · 同一次扫描）：

`/common/properties` · `/common/stress` · `/common/toxicity` 三个页面**首屏**
就发一个**空查询** ⇒ 后端 **422**：

- `GET /api/v1/common/materials/search` → 422
- `GET /api/v1/common/allowable-stress` → 422
- `GET /api/v1/common/safety` → 422

⇒ 页面首屏就是错误态（用户得先填条件才有数据）⇒ 至少是**噪声**，
也可能是**契约形状错了**（前端没传后端要的必填参数）。

**何时做**：**P10-C** ⇒ 要么前端首屏**不发请求**（等用户填条件），
要么前端按契约补参数（⇒ 先对 OpenAPI）。

**归属**：**P10-C · 前端收口子批**（人裁决 2026-11-18 · `docs/superpowers/plans/2026-11-18-p10-c-frontend-closure.md`）

### ✅ **已关闭 · 2026-11-19 · P10-C · T1 · `ba312b9`**

**对 OpenAPI 的结论**（`pcs-backend/docs/openapi.json`）⇒ 三个端点的
必填参数是：

| 端点 | 必填参数 | 返**单个**还是**数组** |
|---|---|---|
| `GET /common/materials/search` | `keyword`（min_length=1） | 数组（但后端 `search_chemical` **单命中** ⇒ 最多 1 条） |
| `GET /common/allowable-stress` | `material` + `temp_c` | **单个对象**（插值结果） |
| `GET /common/safety` | `cas` | **单个对象** |

⇒ ⇒ 走「**首屏不发请求**」那条（= TODO-160 的第一个选项）⇒ ⇒ 三页改成
「**填条件才查**」（300ms 防抖）⇒ ⇒ 首屏**零请求** ⇒ ⇒ 没有 422。

⇒ ⇒ **顺带发现两处形状错**（此前没被发现，因为请求**从来没成功过**）：
`allowable-stress` 与 `safety` 返的是**单个对象**，而前端当**数组**用
⇒ ⇒ 页面把单条包成 1 行喂给同一张表 / 同一张分组卡片。

⇒ ⇒ **MSW mock 同步收紧**（此前它**无视**参数、永远返整表 ⇒
「替身比被测物更宽容」⇒ ⇒ 前端漏传参数在 mock 通道里**看不出来**）
⇒ ⇒ 现在：缺参数 ⇒ **422**、命中不到 ⇒ **404**、许用应力照抄后端的
**线性插值** ⇒ ⇒ mock 不再比真后端宽容。

⇒ ⇒ **证据**：3 个页面测试重写（断言**调用参数** ⇒ 漏参数必红）
+ **变异自证**（删早退 / 改参数 ⇒ 6 条断言转红）· vitest 1082/1082。

⇒ ⇒ **SPEC 修订已登记**：`docs/PCS-NOTE-SPEC-7.8-三查询页改为查询驱动-2026-11-19.md`

## TODO-164: **默认单测车道**连了**开发库**与**真 Redis** ⇒ ⇒ 违反「单测车道绝不碰开发库」 🔴

✅ **已裁决并落地**（2026-11-23 · F4-PRE · FP-T3）—— **关闭**：默认车道**零连真 PG**（`pg` 标记用例只在车道跑）· 详见本文件末尾「F4-PRE 裁决表」。


**现状**（2026-11-17 · P10-F 计划评审期间**实测**发现）：

跑默认车道 `cd pcs-backend && uv run pytest -q` 时，用 `ss -tnp` 看这个进程的 socket：

```
ESTAB 127.0.0.1:41122 → 127.0.0.1:6379   (Redis)   ×3
ESTAB 127.0.0.1:54322 → 127.0.0.1:5432   (开发库 pcs)
```

⇒ ⇒ 那一轮跑到 **22% 就挂死 33 分钟**（41 个线程全在 `futex_do_wait`）⇒ ⇒ 已被 kill。

**根因**（读码确认）：

- `tests/conftest.py:118-119` 只把**异步**引擎换成 `sqlite+aiosqlite:///:memory:`
  ⇒ ⇒ 而 `app/db/session.py:22-39` 的**同步**引擎 `_sync_engine` 仍按 `settings.database_url`
  建连 ⇒ ⇒ 那是**开发库**（`5432`）；
- Redis 侧**没有替身**：`app/core/config.py:44` 的默认是 `redis://localhost:6379/0`
  ⇒ ⇒ `app/services/edit_lock.py:142` 与 `app/services/broadcaster.py:80,144`
  直接 `aioredis.Redis.from_url(settings.redis_url)` ⇒ ⇒ **真 Redis**。

**为什么重要**：

- CLAUDE.md 明写「**单测车道绝不碰开发库**」⇒ ⇒ 现状**违反**；
- 与 P10-B 评审 #22 的第三条**同一形状**（`_sync_engine` 是第三个未被覆写的 singleton），
  但发生在**默认车道** ⇒ ⇒ **那一侧从来没被审过**；
- 真 Redis 里的编辑锁/pubsub 会被单测写进去 ⇒ ⇒ 跨轮污染 + 依赖一个外部服务
  ⇒ ⇒ 「绿灯」不代表「这条测试自己跑得通」。

**建议改法**（见 P10-F 计划 F2-T5）：

① `tests/conftest.py` 把 `_sync_engine` 也覆写成 SQLite 同步引擎（与 `_async_engine` **成对**）；
② 把 `settings.redis_url` 指向**不可路由端口**（`redis://127.0.0.1:1/0`）⇒ ⇒ 「连了就炸」比
「查到了再判」更硬 ⇒ ⇒ ⚠️ **不新增 fakeredis 依赖**；
③ ⚠️ 若某测试因此变红 ⇒ ⇒ 说明它**依赖**真 Redis ⇒ ⇒ 该测试应迁到 `scripts/pytest_pg.sh`
那条真 PG 车道 ⇒ ⇒ 另立 TODO。

**何时做**：**P10-F 的 F2 批**（F2-T5）

**归属**：P10-F（F2）

---

## TODO-165: 依赖**真 Redis 语义**的测试该迁到 `scripts/pytest_pg.sh` 车道 🟡

✅ **已裁决并落地**（2026-11-23 · F4-PRE · FP-T3）—— **关闭**：21 条真 Redis 用例**自动标 `pg`** ⇒ ⇒ PG 车道 46 passed（原 7）⇒ ⇒ 覆盖回来了。


**现状**（2026-11-17 · P10-F 的 F2-T5 期间发现）：

F2-T5 要把默认车道的 `settings.redis_url` 指向**不可路由端口**
（`redis://127.0.0.1:1/0`）⇒ ⇒ 「连了就炸」比「查到了再判」更硬。

⇒ ⇒ 若某些测试因此变红 ⇒ ⇒ 说明它们**依赖真 Redis 的语义**
（编辑锁 `app/services/edit_lock.py` · 广播 `app/services/broadcaster.py` 的
pub/sub 行为）⇒ ⇒ 这类测试**不该**在默认车道跑。

**建议改法**：

① 逐条判定：该测试的断言是否**真的**需要 Redis 的行为 ⇒ ⇒ 不需要 ⇒ ⇒ **修它**（用桩）
⇒ ⇒ 需要 ⇒ ⇒ 标 `@pytest.mark.skip(reason="依赖真 Redis ⇒ 迁到 scripts/pytest_pg.sh 车道")`
② 需要真 Redis 的那几条 ⇒ ⇒ 迁到 `scripts/pytest_pg.sh`（**真 PG 车道**）里
⇒ ⇒ ⚠️ 那条车道的库是 `pcs_pgtest`，但 **Redis 是同一个 `localhost:6379`**
⇒ ⇒ ⇒ 迁移时要想清楚：是让真 Redis 也进车道锁，还是接受「Redis 不隔离」
⇒ ⇒ ⇒ **交人裁决**（建议：Redis 的写入是短 TTL 的编辑锁 ⇒ ⇒ 与库隔离的诉求不同）

**何时做**：F2-T5 落地时（届时逐条判定 ⇒ ⇒ 有几条就登记几条）

**归属**：P10-F（F2-T5 的延伸）

**2026-11-17 · F2-T5 落地时逐条判定的结果** ⇒ ⇒ **20 条用例（3 个文件）**
依赖真 Redis 语义（⚠️ 2026-11-18 实测订正：先前写的「3 处」**低估了近 7 倍**
⇒ ⇒ 两个 `real_redis` fixture 各门控**整个文件**）：

| 位置 | 用例 | 依赖什么 |
|---|---|---|
| `tests/api/v1/test_ws_notifications.py` | `test_ws_accepts_a_valid_token` | WS 握手要**发**通知 ⇒ 要真 Redis 的 pub/sub |
| `tests/api/v1/test_ws_notifications.py` | `test_ws_delivers_notification_published_by_another_worker` | 跨进程推送（ADR-0049 §⑤ 的唯一端到端证明） |
| `tests/services/test_broadcaster.py` | `real_redis` fixture（**8 条**有效用例） | 跨进程推送 |
| `tests/services/test_edit_lock.py` | `real_redis` fixture（**11 条**有效用例） | TTL / 续期 |

⇒ ⇒ 默认车道里它们**运行期 skip**（判据 = `settings.redis_url` 是否被隔离成
不可路由端口 ⇒ `tests/lane_guards.py::require_real_redis`）⇒ ⇒
⇒ 迁到 `scripts/pytest_pg.sh` 车道时**要去掉那个 skip** ⇒ ⇒ 那一道里
Redis 是**同一个 `localhost:6379`** ⇒ ⇒ 迁移时要先想清楚：Redis 要不要也进
车道锁（编辑锁是短 TTL ⇒ ⇒ 与库隔离的诉求不同）⇒ ⇒ **交人裁决**。

⚠️ **2026-11-18 · 整支评审 I1/I2 订正**：上面那条「迁过去时去掉 skip」
**原先根本执行不了** —— 判据是「`redis_url` 是否被隔离」，而根 `conftest.py`
的隔离 fixture 是 **autouse** ⇒ ⇒ 它对 `pytest -m pg` **同样生效**
⇒ ⇒ 在车道里 `redis_url` 也被隔离 ⇒ ⇒ 去掉 skip 也没用。
⇒ ⇒ **已修**：隔离**只作用于默认车道**（判据 = 车道脚本导出的
`PCS_TEST_LANE`）⇒ ⇒ 现在「把用例标成 `pg` + 去掉 skip」是**可执行**的。
⇒ ⇒ **本条仍未完成**：那 20 条用例**一条都没标 `pg`** ⇒ ⇒ 迁移本身还没做。

⇒ ⇒ ⚠️ **默认车道剩下的真 Redis 连接**：**0**（实测 `ss` 监控）⇒ ⇒
⇒ 那 2 条 Redis 依赖的用例在**默认车道**里被跳过 ⇒ ⇒ 它们的覆盖**由
PG 车道接管**（本批**尚未**迁 ⇒ ⇒ 迁之前这段时间它们是**只跑不覆盖**的）⇒ ⇒
⇒ **本条要迁** ⇒ ⇒ 别把它忘了。

---

## TODO-166: 公司管级列表里**要不要**出现「E2E 种子管级」 🟡

**现状**（2026-11-17 · P10-F 的 F1-T3 期间发现）：

评审 #17 要求把种子管级的 `source` 从契约外的 `"E2E_SEED"` 改成契约内的
`"COMPANY_STD"`（`PipeClassBase.source` 是 `Literal["COMPANY_STD","PROJECT"]`），
否则**按 id 取那一族 500**。

⇒ ⇒ **副作用**：`PipeClassService.list_company` **固定过滤**
`source == 'COMPANY_STD'` ⇒ ⇒ 改完之后，**这行会出现在公司管级列表里**
⇒ ⇒ 前端「管子等级」页会看到一行叫「E2E 种子管级」的测试数据。

⚠️ 这是**产品决定**，不是技术债 ⇒ ⇒ **不代决**（P10-F 计划的「尚未解决的问题」#2）。

**候选处置**：

① **接受**（列表里有 E2E 种子行）⇒ ⇒ 需要前端能把它标出来（比如名字前缀 `E2E`）
② **列表过滤掉**（`list_company` 排除测试行）⇒ ⇒ ⚠️ 那要**再加一个列**
（或用 `class_id` 前缀判）⇒ ⇒ 契约面变化 ⇒ ⇒ 属另一批
③ **种子行不叫公司标准** ⇒ ⇒ 那就得**扩 `Literal`**（违反评审 #2 的裁决：
「不扩 Literal」）⇒ ⇒ **不取**
④ **E2E 车道用独立的公司管级行**（不与生产同名）⇒ ⇒ 仍会出现在列表里 ⇒ 同 ①

**何时做**：下一批（产品裁决）

**归属**：P10-F（F1-T3 的延伸 · 交人裁决）

### ✅ 已裁决（2026-11-18 · 人裁决）—— **接受现状**

⇒ ⇒ **选项 ①**（接受）⇒ ⇒ **不改代码**。

**理由（人裁决时给的事实）**：

| 环境 | 影响 |
|---|---|
| 开发库 `pcs` | **零影响**（实测：**没有**这行 ⇒ 公司管级列表只有 `CS-STD` 一行） |
| `pcs_pgtest`（真后端通道 / E2E 车道） | 多一行「E2E 种子管级」（名字自带 **E2E** ⇒ 一眼可辨） |
| 生产 | **零影响**（生产不跑这个种子脚本） |

⇒ ⇒ 「公司标准列表永远干净」这件事**目前没有机制保证**（选项 ③ 要动契约 ⇒ 属另一批）
⇒ ⇒ 若将来公司管级列表要进**客户演示**，再走选项 ③。

⇒ ⇒ 另两个选项**明确不取**：②（改 `source="PROJECT"`）语义更歪（项目派生实际在
`project_pipe_classes` 表）且这行任何列表端点都看不到 ⇒ 等于躲起来；④（扩 Literal）
**违反评审 #2 的裁决**。

---

## TODO-168: 默认车道的**漂移守卫**仍连**开发库**（只读） 🟡

✅ **已裁决并落地**（2026-11-23 · F4-PRE · FP-T3）—— **关闭**：5 个漂移守卫全部离开默认车道（3 个标 `pg` · 1 个改指车道库 · 1 个本就 pcs_test 门）。


**现状**（2026-11-17 · P10-F 的 F2-T5 实测）：

F2-T5 把默认车道的**应用侧**连接全部隔离了（同步引擎单例 ⇒ SQLite ·
Redis ⇒ 不可路由端口）⇒ ⇒ 实测（`ss -tnp` 监控整轮跑）**仍有 15 条**到
`127.0.0.1:5432`（开发库 `pcs`）的连接 ⇒ ⇒ 来源是**一批「查真库 schema」的
漂移守卫**：

- `tests/models/test_sim_tower_model.py`（`create_engine(get_settings().database_url)`
  ⇒ 查 FK）
- `tests/models/test_streams_sim_fields.py`（查列）
- `tests/models/test_sim_unit_op_model.py`
- `tests/services/psychro/test_schema_drift.py`
- `tests/test_sqlite_check_constraint_overrides.py`

⚠️ **全是只读**（`information_schema` 查询）⇒ ⇒ **实测开发库没有被写入**：
查 `pcs` 库里最新的 E2E 种子行与 `RBAC_DENIED` 审计行，时间戳都是
**2026-11-12**（P10-A/P10-B 时代）⇒ ⇒ **本批（11-17/18）零写入** ✓。

**建议改法**：这些守卫**本来就该**按 `CLAUDE.md` 的惯例跑在 **`pcs_test`**
（对齐后的真库）⇒ ⇒ ① 加 `_ONLY_PCS_TEST` 跳过标记（与
`tests/models/test_orm_db_drift.py` 同款）⇒ ⇒ ② 或者在默认车道里把
`settings.database_url` 指向 `pcs_test`（**只读** ⇒ 安全）⇒ ⇒
⇒ **二选一** ⇒ ⇒ 都会让默认车道**零**连开发库。

**何时做**：下一批（**不阻塞** F2-T5 ⇒ ⇒ 因为是只读的 ⇒ ⇒ 没有污染）

**归属**：P10-F（F2-T5 的延伸 · 残留）

---

## TODO-169: **FORMAL 工作区是否必然属于一个项目**？要不要 **PERSONAL 工作区**这种形态？ 🟡

**现状**（2026-11-18 · P10-F 整支评审 I5 期间发现）：

主计划的「尚未解决的问题」#3 写的是：**#24 的产品决定**（FORMAL 工作区
**要不要**回填 `project_id`）⇒ ⇒ **交人裁决** ⇒ ⇒ **F2-T2 默认**只补
`owner_id`（保留「无项目工作区」的形态供测）⇒ ⇒ **回填登记 TODO**。

⚠️ **执行时选了执行者那一支**（账簿 Task 6 的 Ruling「本批**照做**」）
⇒ ⇒ 于是「FORMAL 归属一个项目」这条**产品语义**被写进了种子脚本，
⇒ ⇒ 而**计划要求的「回填登记 TODO」没做** ⇒ ⇒ 本条就是那个漏掉的登记。

**现在的代码事实**（`scripts/seed_e2e_flows.py`）：

| 工作区 | `workspace_type` | `project_id` | 归属 |
|---|---|---|---|
| `FLOW_WORKSPACE_ID` | `FORMAL` | ✅ 回填（种的项目） | 业主项目 |
| `FLOW_PERSONAL_WORKSPACE_ID` | `PERSONAL` | ❌ 空（**无项目**） | alice 个人 |

⇒ ⇒ 仪表盘那条「**选到没有项目的工作区 ⇒ 面板不渲染**」的路径
⇒ ⇒ **靠 PERSONAL 这行才测得了** ⇒ ⇒ 这条路径**目前是被测到的**。

**为什么必须人裁**（机器判不了）：

① 真实产品里 **FORMAL 工作区是不是必然有项目**？⇒ ⇒ 如果「不是」，
   ⇒ ⇒ 当前实现把种子里的 FORMAL **强制**绑到项目 ⇒ ⇒ 与真实语义不符
   ⇒ ⇒ 真后端通道测出来的行为**不代表**真实产品。
② **要不要引入 PERSONAL 这种工作区形态**（真实产品里存在吗）？
   ⇒ ⇒ 如果不存在 ⇒ ⇒ 种子造它就是**造了一个假形态** ⇒ ⇒
   ⇒ ⇒ 那条仪表盘路径**测不到真实形态**（测了个不存在的东西）。
③ 两者都要「**没有项目的工作区**」这个形态吗？⇒ ⇒ 那是**第三种**形态。

**建议处置**（**不代决**）：

① 确认真实产品的工作区形态清单 ⇒ ⇒ 再决定种子造哪几种
② 若「无项目工作区」只该是 **PERSONAL** ⇒ ⇒ 现在的实现**就是对的**
   ⇒ ⇒ 本条改为「已确认 · 登记语义」并把结论写进 `CONCEPTS.md`
③ 若 FORMAL 也允许无项目 ⇒ ⇒ 种子要**再造一个 FORMAL 且无项目**的工作区
   ⇒ ⇒ 并让仪表盘那条断言覆盖**两种**形态

**何时做**：产品裁决批（**不阻塞** P10-F ⇒ ⇒ 当前实现自洽且可测）

**归属**：P10-F（F2-T2 的延伸 · **交人裁决** · 补主计划「尚未解决的问题」#3 的登记）

### ✅ 已裁决（2026-11-18 · 人裁决）—— **FORMAL 必然有项目；无项目的就是 PERSONAL**

⇒ ⇒ **选项 ①** ⇒ ⇒ **零代码改动**（当前实现**正确**）。

⇒ ⇒ 该语义已写进 **`CONCEPTS.md` 的「Workspace project binding」**段
（连同「为什么它是结构性的」两条：`Project.workspace_id` NOT NULL ⇒ 工作区先建；
`workspaces.project_id` 是 FK ⇒ 绑定只能在项目建好之后写）。

⇒ ⇒ 裁决同时**确认**了两件事：

① 种子里 FORMAL 那行**回填 `project_id`** 是**结构决定的**，不是随手定的
   ⇒ ⇒ 保留；
② 「没有项目的工作区」在产品里就是 **PERSONAL**（契约里 `workspace_type` 只有
   FORMAL/PERSONAL/TEMPORARY 三类，且 `project_id` 只对 PERSONAL 写「可空」）
   ⇒ ⇒ 种子那个 PERSONAL 工作区**不是造了个假形态** ⇒ ⇒ 保留
   ⇒ ⇒ 仪表盘那条「选了无项目工作区 ⇒ 面板不渲染」的路径**测的是真形态** ✓。

⇒ ⇒ **旁证**（既有行为，本来就站在这条裁决这边）：bug-2102 已经把
「在 **PERSONAL** 工作区建项目」改成 **422 `WORKSPACE_NOT_FORMAL`**
⇒ ⇒ 即**产品行为**本来就是「项目只能住在 FORMAL 工作区」
⇒ ⇒ 「FORMAL 归属一个项目、无项目的工作区就是 PERSONAL」与既有实现**一致** ✓。

⇒ ⇒ 另两个选项**明确不取**：②（FORMAL 也可无项目）⇒ 要再造一行 FORMAL 无项目
的工作区（改种子 + 改 E2E 断言）；③（另立第三种形态）⇒ 要改契约 Literal + 迁移 +
前后端类型 ⇒ **属另一批**。

---

## TODO-171: `DefinitionService.update` 的**写闸**没有独立断言（删掉 ⇒ 71 条全绿）🟠

✅ **已裁决 · 关闭**（2026-11-23 · F4-PRE · FP-T4）—— 写闸**已有独立断言**（`test_update_cannot_repoint_a_definition_to_an_ungranted_project` · P10-G 落地）⇒ ⇒ 不是缺口。


**现状**（2026-11-18 · F3-T2a 的**抽样变异**抓到的）：

`update()` 里有两道检查：

1. **读闸**：`await self.get(def_id, user_id)` ⇒ ⇒ `visible_clause` ⇒ ⇒
   非创建人**看不见** ⇒ ⇒ 404；
2. **写闸**：`if row.created_by != user_id: raise 404`。

⇒ ⇒ ⚠️ **变异实测**：把**写闸**整段删掉 ⇒ ⇒
`tests/api/v1/test_report_builder.py` **71 条全绿** ⇒ ⇒
⇒ `test_update_by_non_creator_gets_404` **挡的是读闸，不是写闸**
⇒ ⇒ ⇒ **写闸没有任何断言**。

⚠️ **为什么这不只是「冗余代码」**：写闸的注释写着「非创建人改 PUBLISHED 的
定义 = 绕过审批」⇒ ⇒ 它是**纵深防御** ⇒ ⇒ 今天的 `visible_clause` 让它
**碰不到** ⇒ ⇒ 但**可见性规则一旦放宽**（见 TODO-170 的 ②）⇒ ⇒ 它立刻
变成**唯一**的那道闸 ⇒ ⇒ 而那时**没有断言**守着它。

**建议改法**：补一条**只测写闸**的断言 ⇒ ⇒ 必须绕开读闸才能测到写闸
（例如：直接调 `DefinitionService.update`（不经端点的 `get`），
或用「`PUBLISHED` + `shared_with=ALL_USERS` ⇒ ⇒ 非创建人**能看见** ⇒ ⇒
改它必须被拒」这一路）⇒ ⇒ 且该断言必须**对删掉写闸敏感**（变异自证）。

**何时做**：下一批（**不阻塞** ⇒ ⇒ 现在读闸在挡 ⇒ ⇒ 无实际漏洞）

**归属**：P10-F（F3-T2a · G2）

---

## TODO-176: 默认 `client` 把**项目守卫 mock 成永远 True** ⇒ ⇒「已覆盖」的结论需要复核 🟠

✅ **已裁决 · 关闭**（2026-11-23 · F4-PRE · FP-T1）—— 默认 client 的 mock 是**设计**（对策是 `strict_client` + 台账棘轮，FP-T2 已抬真）⇒ ⇒ 不是缺陷。


**现状**（2026-11-18 · F3-T2a 期间发现 · 人裁决要求登记）：

`tests/conftest.py` 的默认 `client` fixture 把
`UserProjectService.check_user_project_access` **mock 成永远 True**
⇒ ⇒ 于是**任何**项目授权判定在它上面都是 **no-op** ⇒ ⇒
⇒ **把端点里的授权调用删掉，测试照样绿**。

⚠️ **这与 ce review #5 是同族的病**：角色闸挡在项目守卫前 ⇒ ⇒ `403 === 403`
⇒ ⇒ 项目守卫**一次都没执行** ⇒ ⇒ **测试环境的 mock 让授权判定变成空转**。

⇒ ⇒ **后果（对 F3 审计的直接冲击）**：凡是标「已覆盖」的端点，
⇒ ⇒ 若它**唯一**的断言是用默认 `client` 跑的 ⇒ ⇒ 那个「已覆盖」**是假的**
⇒ ⇒ ⇒ 「审计完成」会让人误以为授权判定**都被验证过**。

**本批已做的部分**（不阻塞，但方向已定）：

① **`tests/conftest.py` 的 `strict_client` docstring 写清楚**：
「**默认 client 不测授权**」+ 说明它是 ce review #5 同族病；
② **加了可执行的棘轮**（`tests/test_strict_client_ratchet.py`）：
「用到 `strict_client` 的测试函数数 ≥ **已审的『带项目维度』端点数**」
⇒ ⇒ 台账在 `tests/conftest.py::AUDITED_PROJECT_SCOPED_ENDPOINTS`
⇒ ⇒ **审计每推进一个带项目维度的端点 ⇒ ⇒ 必须补一条 `strict_client` 断言**
⇒ ⇒ ⇒ 棘轮才咬得紧（当前台账 = 2 ⇒ ⇒ 仓里已有 77 条 `strict_client` 断言）。

**建议改法**（**大动作 ⇒ ⇒ 不在 P10-F 修**）：

① **默认改成 `strict`**（不 mock 守卫）⇒ ⇒ 需要 bypass 的测试**显式 opt-in**
⇒ ⇒ 好处：所有守卫测试**默认**有效 ⇒ ⇒ 代价：大批既有测试要补授权行
⇒ ⇒ ⇒ **工作量按「用到项目守卫的测试」计**；
② 或者**保持现状 + 靠纪律 + 棘轮**（本批做的）⇒ ⇒ ⇒ 缺口是「纪律靠人记」。

**何时做**：下一批或更后（**不阻塞** F3 其余子批 ⇒ ⇒ 用 `strict_client` 补断言即可）

**归属**：P10-F（F3 的「测试基础设施缺口」一节 · **不进 P10-F 修复范围**）

---

## TODO-173: `config.py` 的 **8 个端点**的角色闸**没有 403 断言** 🟠

✅ **已裁决并落地**（2026-11-23 · F4-PRE · FP-T4）—— **关闭**：11 条端点逐条 403 断言 + AST 完整性守卫（新增带闸门的端点忘了写 ⇒ ⇒ 红）。


**现状**（2026-11-18 · F3-T2a）：

`config.py` 的 11 个端点**全部**有角色闸 `require_roles(...)` ⇒ ⇒
且资源是**公司级**（`ConfigAsset` 无 `project_id` ⇒ ⇒ docstring 明写
「公司级配置资产」）⇒ ⇒ **无跨项目越权面**（角色闸就是对的闸）✓

⚠️ **但 8 个端点的角色闸没有 403 断言**（只有 `approve` 与
`status-report` 有 ⇒ ⇒ 两条都**变异敏感** ✓）：

| # | 端点 | 角色闸行号 | 角色要求 |
|---|---|---|---|
| 1 | `POST /config/assets` | `config.py:198` | DESIGNER / PROCESS_CONTROLLER / SYSTEM_ADMIN |
| 2 | `POST /config/assets/{asset_id}/versions` | `:219` | 同上 |
| 3 | `POST /config/assets/{asset_id}/fork` | `:253` | 同上 |
| 4 | `POST /config/assets/{asset_id}/submit` | `:278` | 同上 |
| 5 | `POST /config/assets/{asset_id}/publish` | `:335` | **PROCESS_CONTROLLER / SYSTEM_ADMIN** |
| 6 | `POST /config/assets/{asset_id}/obsolete` | `:373` | **PROCESS_CONTROLLER / SYSTEM_ADMIN** |
| 7 | `GET /config/assets/status-report/export` | `:414` | DESIGNER / PC / SA |
| 8 | `GET /config/assets/{asset_id}/diff` | `:435` | 同上 |

⇒ ⇒ **5 / 6 最要紧**（**发布 / 作废公司级配置**的审批闸）⇒ ⇒
⇒ 删掉那两个 `require_roles` ⇒ ⇒ **测试全绿** ⇒ ⇒ 那道闸是**没有证据**的。

**建议改法**：逐条补「角色不够 ⇒ 403」的断言 ⇒ ⇒ 每条都要**对删掉
`require_roles` 敏感**（变异自证）⇒ ⇒ 建议先补 5 / 6（审批闸）。

**何时做**：下一批（**不阻塞** ⇒ ⇒ 闸在代码里 ⇒ ⇒ 只是没证据）

**归属**：P10-F（F3-T2a · A）

---

## TODO-174: 报表执行的**项目作用域**从不对执行者做授权判定（跨项目读 · **high**）🔴

**现状**（2026-11-18 · P10-F 的 F3-T2a 审计**实测取证**）：

⚠️ **实测演示**（证据在 `.superpowers/sdd/2026-11-17-p10-batch-f-production-readiness/demo-scope-gap.py`
⇒ ⇒ 跑它 ⇒ ⇒ **绿** ⇒ ⇒ 越权成立）：

```
[演示] 执行者对目标项目无授权，却取到 2 行
        （定义 project_id=259a677c-… ，目标项目=259a677c-…）
```

**链路（三步，每步都实测过）**：

| # | 步骤 | 代码事实 |
|---|---|---|
| 1 | `POST /report-builder/definitions`，body 里 **`project_id` 客户端可填任意值** | `DefinitionService.create`（`definition_service.py:186-210`）**只查重名**（`_reject_duplicate`）⇒ ⇒ **不验授权** |
| 2 | `POST /definitions/{id}/publish`（需 REVIEWER / APPROVER / SYSTEM_ADMIN） | service 层 `publish()` **不查 `created_by`** ⇒ ⇒ **任何 REVIEWER 都能发布别人的草稿**（= TODO-172） |
| 3 | `POST /definitions/{id}/execute` | `builder_service.py:176`：**`scope = project_id or row.project_id`** ⇒ ⇒ **scope = 定义里那个项目** ⇒ ⇒ 报表引擎按它取数 |

⇒ ⇒ ⇒ **而 `execute_definition` 的 `user_id` 只写进执行日志**
（`executed_by=user_id` · `builder_service.py:270,281`）
⇒ ⇒ ⇒ **没有任何一处把「执行者」与「scope 项目」做授权判定**
⇒ ⇒ ⇒ **执行者拿到了他没有任何 `user_projects` 授权行的项目的行**。

⚠️ **这与 bug-172 是同一族**（固定 10 类报表导出**不按项目隔离** ⇒ ⇒ 当时的修法是
「项目作用域 ∩ `record_ids`，**两者都是必需项**」）⇒ ⇒ ⇒ **同一个团队以前抓过
这类病** ⇒ ⇒ ⇒ 这条是**同一个洞的另一条路** ⇒ ⇒ ⇒ 修法应当照抄那条：
**scope 项目必须是执行者有授权的项目**。

⚠️ **`test_execution_never_crosses_project_boundary` 断的不是这条**
⇒ ⇒ 它断的是「**A 项目的定义**执行时不返回 B 项目的行」（= scope 的隔离）
⇒ ⇒ **没有**断「执行者对 scope 项目有授权」⇒ ⇒ ⇒ **断言缺口与越权缺口并存**。

**建议改法**：

① `execute_definition` 拿到 `user_id` ⇒ ⇒ 查 `user_projects`（或调
   `check_project_access_or_404`）⇒ ⇒ **scope 项目无授权 ⇒ ⇒ 403/404**
   ⇒ ⇒ ⚠️ ARQ 任务体里也有 `session_factory` ⇒ ⇒ 查得了；
② 或者在**端点层**（`execute_definition_endpoint`）就查 ⇒ ⇒ 早失败、
   错误码更准（任务体里失败 ⇒ ⇒ 用户只看到「执行失败」）；
③ **顺带**：`publish` / `obsolete` 补 `created_by` 判定（= TODO-172）
   ⇒ ⇒ 否则第 2 步仍可被利用。

**何时做**：**下一批优先**（⇒ ⇒ 这是**读**越权 ⇒ ⇒ 数据泄露面）

**归属**：P10-F（F3-T2a · **high** · 与 TODO-170 同源 · 与 TODO-172 联动）

### ✅ 已修（2026-11-18 · commit `c7da7b6`）—— ① 与 ③

⇒ ⇒ **攻击链已断**：① 堵住「把定义挂到别人项目上」⇒ ⇒ ③ 堵住
「执行一个 scope 不属于自己的定义」⇒ ⇒ ⇒ **两步都不需要 ②**（publish 的
`created_by`）才能止血 ⇒ ⇒ ⇒ ② 降级为「多一道防线」（= TODO-172）。

| 步骤 | 修法 | 落点 |
|---|---|---|
| **① create** | `project_id` 非空 ⇒ ⇒ 验授权 ⇒ ⇒ **404** | `definition_service.py::create`（新增 `actor_roles`） |
| **③ execute** | **端点层**（早失败 ⇒ ⇒ POST 直接 **404**）+ **service 层**（纵深防御 ⇒ ⇒ 任务体也挡住） | `report_builder.py::execute_definition_endpoint` + `builder_service.py::execute_definition` |

⚠️ **③ 的位置是硬要求**（bug-172 的教训）：判定**必须**在
`scope = project_id or row.project_id` **之后、任何取数之前**
⇒ ⇒ 早一点就是「先取数再判无权」⇒ ⇒ 那等于没判
⇒ ⇒ 测试钉子里**断言 `_fetch_source` 一次都没被调用**。

⇒ ⇒ **测试钉子 4 条**（RED → GREEN）：
① 填别人项目建定义 ⇒ ⇒ **404** · ② 执行者无 scope 授权 ⇒ ⇒ **404** +
**取数函数没被调** · ③ service 层也挡 · ④ **正面路径**（有授权 ⇒ ⇒ 执行得下去）
⇒ ⇒ ④ 是为了防「所有人都被拒」被当成「修好了」。

⚠️ **这 4 条用 `strict_client`** ⇒ ⇒ 默认 `client` 把项目守卫 mock 成永远 True
⇒ ⇒ 「端点缺项目守卫」这类缺陷在它上面**一个都测不出来**。

⚠️ **① 与 ③ 引入两份「项目访问权」判定**（API 层 `HTTPException` 404 /
服务层 `PcsError` 404）⇒ ⇒ 语义一致、**信封不同** ⇒ ⇒
⇒ 「同一个失败在两层两种信封」是**已知不一致** ⇒ ⇒ 统一它要动 21+ 端点
⇒ ⇒ **属另一批**（不要在修 bug 的机会顺手改）。

**归属**：P10-F（F3-T2a · **high** · 与 TODO-170 同源 · 与 TODO-172 联动）

---


---

## TODO-178: `test_publish_requires_reviewer_role` **不敏感于它命名的缺陷**（「自审自批」）🟡

**现状**（2026-11-18 · F3-T2a 的探针实测）：

该测试的 docstring 写着：

> 「**创建人自己不能**发布 —— 否则审批这一步形同虚设。」

⇒ ⇒ **但这条意图并没有被守住**：

| 事实 | 证据 |
|---|---|
| 该测试之所以绿 | 它的创建人是 **DESIGNER** ⇒ ⇒ 不在 `PUBLISH_ROLES` 里 ⇒ ⇒ **挡的是角色闸**，不是「自审自批」 |
| **创建人自己是 REVIEWER** | 探针实测：发布自己创建的定义 ⇒ ⇒ **HTTP 200** ⇒ ⇒ 「自审自批」**允许** |

⇒ ⇒ ⇒ **断言存在，但不敏感于它命名的缺陷** ⇒ ⇒ 与 TODO-171 **同族**
⇒ ⇒ ⇒ 这正是 F3 抽样变异要抓的东西（本次是**探针**发现的：代码里没有
「创建人 ≠ 发布人」这道闸 ⇒ ⇒ 断言自然测不到）。

**建议改法**（**取决于 TODO-172 的产品语义裁决**）：

- 若裁决「**禁止自审自批**」⇒ ⇒ 实现加「`created_by != 发布人`」的判定
  ⇒ ⇒ **并**补一条断言（创建人是 REVIEWER 时发布自己的定义 ⇒ ⇒ 403）
  ⇒ ⇒ ⚠️ 这会与 SPEC §3.2.2(6) 的读法相关 ⇒ ⇒ 一并裁决；
- 若裁决「**允许自审**（现状）**」⇒ ⇒ **改那条测试的 docstring**
  ⇒ ⇒ 把它声称的东西改成它真正断的（「角色不够 ⇒ ⇒ 403」）⇒ ⇒
  ⇒ ⇒ **别让 docstring 声称一条没守住的规则**（本仓反复吃这个亏）。

**何时做**：随 TODO-172 的裁决一起做

**归属**：P10-F（F3-T2a · 断言缺口 · 依赖 TODO-172）


### ✅ 已修（2026-11-18 · commit `09c9282` · TODO-172 裁决落地）

⇒ ⇒ 人裁决「**审核者不能审自己创建的**」⇒ ⇒ ⇒ 实现加「`created_by != 发布人`」
⇒ ⇒ ⇒ **403** `REPORT_DEFINITION_SELF_REVIEW_FORBIDDEN`（在 **service 层**
⇒ ⇒ ⇒ ⇒ 端点漏调也绕不过）。
⇒ ⇒ ⇒ 新增**敏感**断言：`tests/api/v1/test_report_definition_publish_duty.py::
test_creator_who_is_a_reviewer_cannot_publish_own_definition`
⇒ ⇒ ⇒ ⇒ （**创建人自己是 REVIEWER** ⇒ ⇒ ⇒ ⇒ 此前是 **HTTP 200** ⇒ ⇒ ⇒
⇒ ⇒ ⇒ 现在 **403**）。
⇒ ⇒ ⇒ 既有那条 `test_publish_requires_reviewer_role` **保留** ⇒ ⇒ ⇒ 它断的
「角色不够 ⇒ ⇒ 403」是**另一件事** ⇒ ⇒ ⇒ 两条各断各的。


---

## TODO-179: `records.py` 的**读面**既不要求登录也不做项目授权（匿名可读任意项目的管路记录）🔴

**现状**（2026-11-18 · P10-F 的 F3-T2b 审计**实测取证**）：

⚠️ **实测演示**（证据见 `.superpowers/sdd/2026-11-17-p10-batch-f-production-readiness/audit-f3-t2b.md` §五
⇒ ⇒ 演示文件**用完移走**，不进仓库 ⇒ ⇒ 复现方式见该节）：

```
[演示·甲] 无 token：列表 200 (1 行) · 详情 200 · 快照 200
[演示·甲] 无授权用户：列表 200 (1 行)
```

**三个端点**（`app/api/v1/records.py`）：

| 端点 | 行 | 缺什么 |
|---|---|---|
| `GET /records/piping` | `:40-75` | **没有 `current_actor` 依赖** ⇒ ⇒ 不带 `Authorization` 头也 200 |
| `GET /records/piping/{pipe_id}` | `:78-113` | 同上 |
| `GET /records/piping/{pipe_id}/snapshots` | `:270-316` | 同上 |

⇒ ⇒ ⇒ **没有 `current_actor`** ⇒ ⇒ **连「登录」都不要求**
⇒ ⇒ ⇒ 而 `get_workspace`（`app/api/deps.py:20-40`）**只判存在性**
⇒ ⇒ ⇒ **没有任何 `user_projects` 判定** ⇒ ⇒ ⇒ 换成**任何一个**有 token 的用户也一样读到。

**放大链（闭合）**：`GET /api/v1/workspaces`（`app/api/v1/workspaces.py:63-81`）
**同样不要求登录**，且 `owner_id` 不传即**返回全部** workspace
（`workspace_service.py:86-100`：`owner_id=None` 视为不过滤）
⇒ ⇒ **匿名可枚举 workspace_id** ⇒ ⇒ 再读管路记录
⇒ ⇒ ⇒ **攻击链闭合**（⚠️ `workspaces.py` 属 **T3a** 范围 ⇒ ⇒ T3a 要一并复核）。

**泄露面**：项目管路记录（`line_no` / `sign_status` / `approval_step` /
`locked_by_deliverable` / `seq_no` / `source_pid`）+ 变更快照（**审计轨迹**）。

**建议改法**：

① 三个端点加 `current_actor` 依赖（⇒ ⇒ 至少要登录）；
② 再按 `workspace.project_id` 做**项目授权判定**
   ⇒ ⇒ **无授权 ⇒ ⇒ 404**（与「不存在」同形 ⇒ ⇒ 不泄露存在性）
   ⇒ ⇒ ⚠️ 参照 `app/api/v1/_guard.py::check_project_access_or_404`
   ⇒ ⇒ `workspace.project_id IS NULL` 时怎么办 ⇒ ⇒ **产品语义**
   （TODO-169「FORMAL 是否必然属于一个项目」相关 ⇒ ⇒ 一起裁决）；
③ `GET /workspaces` 是否要一并收紧（列表面）⇒ ⇒ **T3a 裁决**
   （人已裁决「工作区 id 令牌 ① 保留」⇒ ⇒ 但「**关联项目数据必须审**」
   ⇒ ⇒ 「列表能枚举别的项目的 workspace」属于「关联」⇒ ⇒ 要审）。

**何时做**：**下一批优先**（⇒ ⇒ 匿名可读 ⇒ ⇒ 数据泄露面最大）

**归属**：P10-F（F3-T2b · **critical** · 与 TODO-180 同族）

### ✅ 已修（2026-11-18 · commit `a2b9889`）

⇒ ⇒ 三个 GET 端点**加 `current_actor`**（⇒ ⇒ 不带 token ⇒ ⇒ **401**）
⇒ ⇒ **加工作区授权**（`require_workspace_access_or_404` ⇒ ⇒ 无权 ⇒ ⇒ **404**）
⇒ ⇒ ⇒ 「无权」与「不存在」抛**同一个** `WorkspaceNotFoundError` ⇒ ⇒ 逐字同形。
⇒ ⇒ 断言：`tests/api/v1/test_workspace_access_guard.py`（**全用 `strict_client`**）
⇒ ⇒ 另：`tests/test_records.py` 此前**不带 token** ⇒ ⇒ 已改成带令牌。


---

## TODO-180: `records.py` 写面授权的 id 与落库的 id **不同源**（跨项目写入）🟠

**现状**（2026-11-18 · P10-F 的 F3-T2b 审计**实测取证**）：

```
[演示·乙] 攻击者（仅授权项目 A）向项目 B 的 workspace 写入 ⇒ HTTP 200
[演示·乙] 对照组（payload 写 B）⇒ HTTP 404
```

⇒ ⇒ ⇒ **守卫是「真」的**（对照组 404）⇒ ⇒ ⇒ **洞恰好在 id 不同源**。

**机制**（`app/api/v1/records.py::create_piping`）：

| 事实 | 行 |
|---|---|
| 授权判的是 **payload 里的 `project_id`** | `:130-134` `check_project_access_or_404(... project_id=uuid.UUID(payload["project_id"]))` |
| 行落在 **`workspace_id` 指向的 workspace** | `:137` `workspace_id=workspace.workspace_id` |
| ⇒ ⇒ **两个 id 可以互不相同** | ⇒ ⇒ 守卫查 A（过）⇒ ⇒ 行落进 **B 的 workspace** |

⇒ ⇒ ⇒ **授权在项目 A 的人，把记录写进了项目 B 的工作区**。

**同族**（三个 id 可互不相同）：`transition_piping`（`:189-193`）与
`obsolete_piping`（`:243-247`）授权的是 **`ws.project_id`**，
而行自己的 `project_id` 可能是别的值（由 `create` 写进去的）
⇒ ⇒ 读面（`GET /records/piping`）**只按 `workspace_id` 过滤** ⇒ ⇒
⇒ ⇒ 记录落在哪个项目、谁能看到它，**三处口径各不相同**。

**建议改法**：

① `create_piping` 的 `payload["project_id"]` 必须与
   `workspace.project_id` **一致** ⇒ ⇒ 不一致 ⇒ ⇒ **400**
   （⇒ ⇒ 错误码要选：422 语义对但本仓习惯 400 ⇒ ⇒ 与 SPEC 对齐）；
② 或者反过来：改用 **`workspace.project_id`** 作授权对象，
   `payload["project_id"]` 只作**冗余校验**；
③ `transition` / `obsolete` 的授权对象与 `create` **统一**（同一个 id）。

**何时做**：下一批（⇒ ⇒ 与 TODO-179 同批做最省事：都在 `records.py`）

**归属**：P10-F（F3-T2b · **high** · 与 TODO-179 同族）

### ✅ 已修（2026-11-18 · commit `a2b9889`）

⇒ ⇒ **授权对象统一成「工作区」** ⇒ ⇒ `create_piping` 判**工作区的项目**
⇒ ⇒ 且 `payload["project_id"]` 必须与之一致 ⇒ ⇒ 否则 **400**（请求自相矛盾）。
⇒ ⇒ ⇒ 顺序：**先授权（404）后一致性（400）** ⇒ ⇒ 否则无权者能靠 400
⇒ ⇒ ⇒ 读出「这个工作区属于别的项目」。
⇒ ⇒ 断言：`test_records_create_rejects_project_mismatch`（授权在 B、payload 写 A ⇒ ⇒ 400）。


---

## TODO-181: `records.py` / `report.py` 的**项目守卫零断言**（变异无人应答）🟠

✅ **已裁决并落地**（2026-11-23 · F4-PRE · FP-T4）—— **关闭**：report.py 4 条端点补 `strict_client` 断言 + 恒真断言删除 + 进台账；records.py 三条此前已入台账。


**现状**（2026-11-18 · P10-F 的 F3-T2b **抽样变异**实测）：

| 变异 | 删掉的东西 | 实测 |
|---|---|---|
| M3 | `records.py::transition_piping` 的 `check_project_access_or_404` | **49 个测试全绿** |
| M4 | `report.py::_guard_project` 的守卫调用 | **45 个测试全绿** |
| M5 | `report.py::generate_report` 的守卫调用 | **29 个测试全绿** |

⇒ ⇒ ⇒ **守卫删了没有任何测试变红** ⇒ ⇒ ⇒ 「已覆盖」只是**代码上的**，
**断言层面没有任何东西守着**。

**根因**：这些端点的测试都用**默认 `client`** ⇒ ⇒ 默认 `client` 把
`UserProjectService.check_user_project_access` mock 成永远 True
（`tests/conftest.py:257-264`）⇒ ⇒ 「无权 ⇒ 404」的断言即便写了也是 **no-op**。

⚠️ **已有的最弱断言也不算数**：
`tests/api/v1/test_report.py::test_download_uses_404_not_403` 断言的是
`status_code in (200, 404)` ⇒ ⇒ **恒真**（两个值都可能）⇒ ⇒ 不算覆盖
⇒ ⇒ 它自己的 docstring 也写了「断言的是**端点选了哪种状态码**，不是「守卫拦住了无权用户」」。

**建议改法**：

① 用 **`strict_client`**（+ 真 `UserProject` 授权行）补断言：
   「无权用户 ⇒ ⇒ **404**」；
② **同时把 `tests/conftest.py::AUDITED_PROJECT_SCOPED_ENDPOINTS` 的棘轮数上调**
   （当前 = 2 ⇒ ⇒ 只算 `report_builder` 的 create / execute
   ⇒ ⇒ ⇒ 本条要把 `records.py`(3) + `report.py`(4) 计进去）；
③ 顺手把 `test_download_uses_404_not_403` 的恒真断言改成**真断言**
   （要么 `== 404`（无权）+ `== 200`（有权）两条，要么删掉它并把意图移到别处）。

**何时做**：随 TODO-179 / 180 一批（⇒ ⇒ 守卫改完**立刻**补断言，
⇒ ⇒ 否则又是一批「改了但没人守」）

**归属**：P10-F（F3-T2b · 断言缺口 · **high**）

### ➕ F3-T3a 追加的端点（2026-11-18 · 同一族 · 同一批修）

⇒ ⇒ T3a 又查出 **4 个**「代码里有守卫但没人守」的端点：

| 端点 | 变异 | 结果 |
|---|---|---|
| `GET /psychro/results/{record_id}` 的项目守卫（`psychro.py:639`） | M6 | ⚪ 26 passed |
| `POST /user-projects/grant` 的角色闸（`user_projects.py:86`） | M7 | ⚪ 15 passed |
| `GET /user-projects/{user_id}` 的角色闸（`user_projects.py:136`） | M11 | ⚪ 15 passed |
| `PATCH /workspaces/{id}/archive` 的**项目守卫**（`workspaces.py:139`） | M10 | ⚪ 6 passed |

⇒ ⇒ ⇒ 累计「无断言」端点 = **9 个**（T2b 的 M3/M4/M5 + 上表 4 个）
⇒ ⇒ ⇒ 棘轮 `AUDITED_PROJECT_SCOPED_ENDPOINTS` 的真实值 ≈ **18**
（2 + `records.py` 6 + `report.py` 4 + `psychro` 5 + `workspaces.archive` 1）
⇒ ⇒ ⇒ **抬棘轮与补断言必须同批**（否则要么红、要么假绿）。

### ➕ F3 修复批的进展（2026-11-18 · commit `a2b9889`）

⇒ ⇒ `records.py` 的**三个读端点** + `workspaces.py` 的**三个端点**
⇒ ⇒ **已补 `strict_client` 断言**（`tests/api/v1/test_workspace_access_guard.py`）
⇒ ⇒ ⇒ 「无断言」端点从 9 降到 **6**（`report.py` 4 · `psychro` 1 ·
`user_projects` 2 · `workspaces.archive` 1 ⇒ ⇒ 其中 `user_projects` 的两个是
**角色闸** ⇒ ⇒ 不需要 `strict_client` ⇒ ⇒ ⇒ 真正要补 `strict_client` 的
只剩 `report.py` 4 + `psychro` 1 + `workspaces.archive` 1 = **6 个**）。

⇒ ⇒ ⚠️ **棘轮数仍未抬**（仍是 2）⇒ ⇒ **抬它与补断言必须同批**
⇒ ⇒ ⇒ 否则要么红、要么假绿 ⇒ ⇒ ⇒ 留给下一批。

⇒ ⇒ ⚠️ **注意**：`user_projects` 的两个是**角色闸**（403）⇒ ⇒ 不需要 `strict_client`
⇒ ⇒ ⇒ 但**默认 `client` 不 mock `require_roles`** ⇒ ⇒ ⇒ 那两个的断言缺口
是「**根本没写**」，不是「写了但 no-op」⇒ ⇒ ⇒ 补起来更便宜。

---

## TODO-182: `records.py` 的状态机守卫在 `ws.project_id IS NULL` 时**整段跳过**🟡

**现状**（2026-11-18 · P10-F 的 F3-T2b 审计）：

`app/api/v1/records.py`：

| 端点 | 行 | 形状 |
|---|---|---|
| `transition_piping` | `:189-193` | `if ws.project_id is not None:` ⇒ ⇒ **非空才判** |
| `obsolete_piping` | `:243-247` | 同上 |
| `create_piping` | `:130-134` | 判 **payload** 的 `project_id`（**必填** ⇒ ⇒ 永远有） |

⇒ ⇒ ⇒ **FORMAL 且未绑项目的 workspace** ⇒ ⇒ **任何登录用户**都能改该
workspace 里记录的状态（`DRAFT → IN_APPROVAL → CHECKED → …`）
⇒ ⇒ ⇒ 而 `create` 写进去的行**永远带 `project_id`** ⇒ ⇒
⇒ ⇒ **两个口径不一致**（= TODO-180 的另一半）。

**建议改法**：与 TODO-180 的 ③ 一起统一：授权对象**只认一个** id
⇒ ⇒ 至于「workspace 没有项目」时怎么办 ⇒ ⇒ **产品语义**
⇒ ⇒ 与 TODO-169（FORMAL 是否必然属于一个项目）**一起裁决**。

**何时做**：随 TODO-179 / 180 一批

**归属**：P10-F（F3-T2b · **high** · 与 TODO-180 同族 · 依赖 TODO-169 的裁决）

### ✅ 已修（2026-11-18 · commit `a2b9889`）

⇒ ⇒ `transition_piping` / `obsolete_piping` 的 `if ws.project_id is not None:`
⇒ ⇒ **整段删掉** ⇒ ⇒ 改用 `require_workspace_access_or_404`（工作区口径）
⇒ ⇒ ⇒ **不再有「跳过」分支** ⇒ ⇒ 无项目的工作区 ⇒ ⇒ 走 **owner 口径**。


---

## TODO-183: `test_project_level_uses_project_access_not_admin` 的断言**恒真** 🟡

✅ **已裁决并落地**（2026-11-23 · F4-PRE · FP-T4）—— **关闭**：断言初值 `True` ⇒ ⇒ `False` ⇒ ⇒ 变异自证（删守卫 ⇒ ⇒ 2 条红）。


**现状**（2026-11-18 · P10-F 的 F3-T2b **抽样变异**发现）：

`tests/services/report/test_style_service.py:208`：

```python
granted = {"value": True}      # ← 起始值就是 True
...
assert granted["value"], "根本没查项目访问权 —— 权限检查被绕过了"   # :221
```

⇒ ⇒ ⇒ **`granted` 起始值是 `True`** ⇒ ⇒ ⇒ 随后的断言**永远为真**
⇒ ⇒ ⇒ 它**侦测不到「项目检查被删掉」**。

⚠️ **实测**：本批 M2 变异（删掉 `style_service._authorize` 里的
`check_user_project_access` 调用）⇒ ⇒ **这条测试仍然绿**
⇒ ⇒ ⇒ 而它的失败消息写的正是「根本没查项目访问权 —— 权限检查被绕过了」
⇒ ⇒ ⇒ **消息描述的正是它做不到的事**。

⇒ ⇒ ⇒ **同批 M2 里 `test_project_level_denied_when_no_project_access` 变红了**
⇒ ⇒ ⇒ 说明**拒绝路径**有断言守着 ⇒ ⇒ **缺的是「确实去查了」这一侧**。

**建议改法**：`granted = {"value": False}` 起步
⇒ ⇒ M2 变异即可让它变红 ⇒ ⇒ 它才真的守着它声称的东西。

**何时做**：随手（⇒ ⇒ 一行改动 ⇒ ⇒ 但**必须**与守卫补断言同批做，
⇒ ⇒ 否则改完仍然没人守）

**归属**：P10-F（F3-T2b · 断言缺口 · 与 TODO-181 同族）

---

## TODO-185: `GET /records/piping/{pipe_id}`（详情端点）**零测试** 🟢

**现状**（2026-11-18 · P10-F 的 F3-T2b 审计）：

全仓 `grep "records/piping"` 只命中 `tests/test_records.py`
（列表 / 快照 / 写）⇒ ⇒ ⇒ **详情端点 `GET /records/piping/{pipe_id}`
没有任何测试** ⇒ ⇒ ⇒ 连「它返回 200」都没人钉
⇒ ⇒ ⇒ 而它恰好是 TODO-179 里三个**无授权**端点之一。

**建议改法**：随 TODO-179 补测试 ⇒ ⇒ 一条「无权用户 ⇒ ⇒ 404」
+ 一条「有权用户 ⇒ ⇒ 200 且字段齐」。

**何时做**：随 TODO-179 一批

**归属**：P10-F（F3-T2b · 断言缺口 · **low** · 与 TODO-179 联动）

### ✅ 已修（2026-11-18 · commit `a2b9889`）

⇒ ⇒ 详情端点此前**零测试** ⇒ ⇒ 新增
`tests/api/v1/test_workspace_access_guard.py::test_records_detail_of_own_record_is_200`
（正面路径）与 `::test_records_detail_and_snapshots_of_another_project_are_404`
（越权路径）⇒ ⇒ **全部用 `strict_client`**。


---

---

## TODO-186: `workspaces.py` 的三个端点**不要求登录**（匿名枚举 + 匿名写库 + 审计伪造）🔴

**现状**（2026-11-18 · P10-F 的 F3-T3a 审计**实测取证**）：

⚠️ **实测演示**（证据见 `.superpowers/sdd/2026-11-17-p10-batch-f-production-readiness/audit-f3-t3a.md` §三-1
⇒ ⇒ 演示文件**用完移走**，不进仓库）：

```
[演示·甲] 匿名 GET /workspaces ⇒ HTTP 200 · 1 个 · 受害者的在不在：True
[演示·甲] 匿名 GET /workspaces/{id} ⇒ HTTP 200 · last_active_at: None → 2026-11-18 02:16:45
[演示·甲] 匿名 POST /workspaces（owner_id=6352aa65-…）⇒ HTTP 201
[演示·甲] 记在伪造 owner 名下的审计行：1 条 （action=['WORKSPACE_CREATED']）
```

| 端点 | 事实 | 位置 |
|---|---|---|
| `POST /workspaces` | **无 `current_actor`**；`owner_id` 是**客户端参数** ⇒ ⇒ 建的行的 `owner_id` = 客户端给的值 | `app/api/v1/workspaces.py:30-35` |
| ⇒ ⇒ | 审计行 `WORKSPACE_CREATED` 的 `user_id` **也是那个 `owner_id`** ⇒ ⇒ **匿名可把审计行记在别人名下** | `workspaces.py:52-58` ⇒ `workspace_service.py:68-74` |
| `GET /workspaces` | **无认证**；`owner_id` 不传 ⇒ `list_for_user(owner_id=None)` ⇒ **返回全部** | `workspaces.py:63-81` ⇒ `workspace_service.py:86-100` |
| ⇒ ⇒ | ⚠️ **前端自己的注释说那是「admin 视图」** ⇒ ⇒ **admin 视图没有 admin 闸** | `tests/e2e_flows/test_e2e_workspaces_visible.py:11-13` |
| `GET /workspaces/{id}` | **无认证** ⇒ ⇒ 可读任意 workspace；⚠️ **且 `svc.touch` + `commit`** ⇒ ⇒ **匿名 GET = 匿名写库**（改 `last_accessed_at`） | `workspaces.py:104-105` ⇒ `workspace_service.py:126-140` |

⇒ ⇒ ⇒ **与 TODO-179 合起来是一条完整链**：
**匿名枚举全部 workspace_id（这里）⇒ ⇒ 匿名读走任意项目的管路记录（那里）**。

⚠️ **仓库自己的测试把「无认证可读可建」当成正常行为钉住了**
（`tests/test_workspace.py:10-19` 无 token ⇒ 201 · `:45-53` 无 token ⇒ 200）
⇒ ⇒ ⇒ 修的时候**那些测试要一起改**（否则它们会红 ⇒ ⇒ 而红是对的方向）。

**建议改法**：

① 三个端点加 `current_actor`；
② `owner_id` **不再由客户端提供** ⇒ ⇒ 取 `actor.user_id`
   （或不一致 ⇒ ⇒ 403）；
③ `GET /workspaces` 不传 `owner_id`（= admin 视图）⇒ ⇒ 要求 `SYSTEM_ADMIN`
   ⇒ ⇒ 与前端注释对齐；
④ `GET /workspaces/{id}` ⇒ ⇒ 按 `owner_id` 或项目授权判定
   （无授权 ⇒ ⇒ **404**，与「不存在」同形）；
⑤ `touch` 的写副作用 ⇒ ⇒ **只在授权通过后**才做。

**何时做**：**下一批优先**（⇒ ⇒ 与 TODO-179 同批 ⇒ ⇒ 两条是一条链）

**归属**：P10-F（F3-T3a · **critical** · 与 TODO-179 联动）

### ✅ 已修（2026-11-18 · commit `a2b9889`）

⇒ ⇒ 三个端点**加 `current_actor`** + 授权：
① `POST`：`owner_id` 必须是**令牌里的那个人** ⇒ ⇒ 否则 **403**
（⇒ ⇒ 审计行不再记在别人名下 ⇒ ⇒ 审计污染断掉）；
② `GET ""`：`owner_id` 不传（= admin 视图）⇒ ⇒ **仅 SYSTEM_ADMIN**；
③ `GET /{id}`：无权 ⇒ ⇒ **404**，且 **`touch` 的写副作用只在授权通过后**做
（⇒ ⇒ 匿名 GET = 匿名写库 ⇒ ⇒ 断掉）；
④ 「不存在」与「无权」抛**同一个** `WorkspaceNotFoundError` ⇒ ⇒ 逐字同形。
⇒ ⇒ 断言：`tests/api/v1/test_workspace_access_guard.py`（9 例 · 全 `strict_client`）。
⚠️ **合同变更**：`GET /workspaces/{id}` 的「不存在」错误码由 `HTTP_404` 变成
`WORKSPACE_NOT_FOUND`（与 `records.py` 的既有形状对齐）⇒ ⇒ 前端不依赖该码。


---

## TODO-188: `GET /user-projects/me` 的**角色清单不全** ⇒ 合法用户 403 🟡

✅ **已裁决并落地**（2026-11-23 · F4-PRE · FP-T4）—— **关闭**：角色白名单提为**模块级常量** `ALLOWED_ROLES`（唯一真相源）+ `/me` 改用 `*ALLOWED_ROLES` + 同族笔误 `PROCESS_CONTROLLOR` 修正。


**现状**（2026-11-18 · P10-F 的 F3-T3a 审计）：

`app/api/v1/user_projects.py:123`：

```python
require_roles(actor, "DESIGNER", "CHECKER", "APPROVER", "REVIEWER", "SYSTEM_ADMIN")
```

⇒ ⇒ ⇒ **缺 `PROCESS_CONTROLLER` / `VIEWER` / `DATA_ADMIN`**
⇒ ⇒ ⇒ 真实 AD 用户里**存在** `PROCESS_CONTROLLER`
（`app/api/v1/auth.py:267` 的注释列了它）
⇒ ⇒ ⇒ **这类用户拿不到自己的项目列表**（403）。

⚠️ **潜伏**：前端目前**没有消费者**
（`grep "user-projects" pcs-frontend/src` 只命中生成的类型）
⇒ ⇒ ⇒ 且 mock 账号的四种角色（DESIGNER/CHECKER/APPROVER/SYSTEM_ADMIN）
**都在清单内** ⇒ ⇒ ⇒ mock 通道**测不出来**。

**建议改法**：端点本来就是「**我有哪些项目**」⇒ ⇒ 不该被全局角色卡住
⇒ ⇒ 要么清单补全 ⇒ ⇒ 要么改成「只要登录过就返回自己的清单」。

**何时做**：低优先（⇒ ⇒ 但**改前先确认前端要不要用它**）

**归属**：P10-F（F3-T3a · **medium**）

---

---

## TODO-189: 仓库里有**两个**「不 mock 项目守卫」的 client ⇒ ⇒ 棘轮看不见其中一个 🟢

✅ **已裁决并落地**（2026-11-23 · F4-PRE · FP-T2）—— **关闭**：`test_audit_guard.py` 改用 `strict_client` + 新增「自建 client 的文件集合**冻结**」守卫 ⇒ ⇒ 不会有第三个。


**现状**（2026-11-18 · P10-F 的 F3-T3b 审计发现）：

| fixture | 位置 | 引入时间 |
|---|---|---|
| `strict_client` | `pcs-backend/tests/conftest.py:339` | P9B-4 T0/T1 |
| `real_user_project_client` | `pcs-backend/tests/test_audit_guard.py:32` | 更早（该文件**自己写**的独立 fixture） |

⇒ ⇒ ⇒ **两者做的是同一件事**（不 mock `check_user_project_access` ⇒ ⇒ 让守卫真跑）
⇒ ⇒ ⇒ 而 `tests/test_strict_client_ratchet.py`（TODO-176 的可执行形态）
**只数 `strict_client`** ⇒ ⇒ ⇒ **`real_user_project_client` 的用例对棘轮是隐形的**
⇒ ⇒ ⇒ 「已审面」的计数**偏小** ⇒ ⇒ ⇒ 棘轮说「≥ N」时，实际覆盖可能更少。

⚠️ **顺带**：`real_user_project_client` 是**第三个**「守卫要真跑」的写法之前
（P9B-4 之前还有别的文件各写各的）⇒ ⇒ 分散 ⇒ ⇒ 下一个还会再写一个。

**建议改法**：

① `tests/test_audit_guard.py` 改用 `conftest.py` 的 **`strict_client`**
   （⚠️ 它比本地的那个多做一件事：**每次请求前**还原守卫 ⇒ ⇒ 不会被
   `client` 的 monkeypatch 抢在前面 ⇒ ⇒ **更稳**）；
② 或者：把棘轮改成「**数两种 client**」⇒ ⇒ 但那等于承认分散 ⇒ ⇒ 不推荐；
③ 补一条**架构测试**：全仓**只允许一处**定义「不 mock 项目守卫的 client」
   ⇒ ⇒ 防止第三个再出现。

**何时做**：低优先（⇒ ⇒ 随手可做 ⇒ ⇒ 但**做的时候要把那条 404 断言跑一遍**
⇒ ⇒ 确认换成 `strict_client` 后它还红）

**归属**：P10-F（F3-T3b · 断言基础设施 · **low**）

---

---

## ✅ TODO-172: **已裁决并落地**（2026-11-18 · commit `09c9282`）

**人裁决（三条）**：

| # | 裁决 | 落点 |
|---|---|---|
| ① | **审核者不能审自己创建的** | `created_by == actor` ⇒ ⇒ **403** `REPORT_DEFINITION_SELF_REVIEW_FORBIDDEN` |
| ② | **审核者需要对定义的项目有授权** | `project_id` 非空 ⇒ ⇒ 查 `user_projects` ⇒ ⇒ 无授权 ⇒ ⇒ **404** |
| ③ | **允许公司级审核者** | `project_id IS NULL` ⇒ ⇒ **不做项目判定** ⇒ ⇒ 任何审核角色（且非创建人）都能审 |

⇒ ⇒ 判定落在 **service 层**（`DefinitionService.publish`）⇒ ⇒ 端点漏调也绕不过
⇒ ⇒ ⇒ 这正是 TODO-178 的根因（断言在、但不敏感于缺陷）。
⇒ ⇒ ② 的 404 与「不存在」**逐字同形**（同一个 `REPORT_DEFINITION_NOT_FOUND`）。
⇒ ⇒ ③ 是 ② 的例外（否则公司级模板**永远没人能审**）。

⇒ ⇒ 测试：`tests/api/v1/test_report_definition_publish_duty.py`（5 例 · 全
`strict_client`）⇒ ⇒ 三条裁决各有用例 + 两条**正面路径**。

⇒ ⇒ ⚠️ **裁决未覆盖的一处** ⇒ ⇒ `obsolete`（作废）**仍不查 `created_by`**
⇒ ⇒ ⇒ **别人发布的定义，任意审核角色都能作废** ⇒ ⇒ ⇒ 登记 **TODO-190**。

---

## ✅ TODO-175: **已裁决并落地**（2026-11-18 · commit `09c9282`）

**人裁决**：「**只有系统管理员可以替别人建项目**」+「**工作区的 owner
自动获得授权**」。

⇒ ⇒ ① `POST /projects` 本来就**只允许 SYSTEM_ADMIN** ⇒ ⇒ 现状即满足。
⇒ ⇒ ② **工作区 owner 自动获得授权**（`PROJECT_LEAD`）⇒ ⇒ 理由：工作区是他的，
项目住在**他的工作区**里 ⇒ ⇒ ⇒ 否则项目「住在别人的工作区里却不属于他」
⇒ ⇒ ⇒ 而可见性按 `user_projects` ⇒ ⇒ ⇒ 他**永远看不见**。
⇒ ⇒ ⚠️ `owner_id` 可空（老工作区）⇒ ⇒ ⇒ 空 ⇒ ⇒ 跳过（不造幽灵授权行）。

⇒ ⇒ 测试：`tests/api/v1/test_project_owner_access.py::test_creating_a_project_grants_the_workspace_owner_access`。

---

## TODO-190: `obsolete`（作废报表定义）**不查 `created_by`** ⇒ ⇒ 任意审核角色都能作废别人的定义 🟡

**现状**（2026-11-18 · P10-F 的 TODO-172 裁决落地时**顺带查出来**）：

`DefinitionService.obsolete(def_id)`（`app/services/report/definition_service.py`）
⇒ ⇒ 与 `publish` 同款形状 ⇒ ⇒ **只查状态**（DRAFT/PUBLISHED ⇒ 可作废）
⇒ ⇒ ⇒ **不查 `created_by`** ⇒ ⇒ ⇒ 任何 `PUBLISH_ROLES`
（REVIEWER / APPROVER / SYSTEM_ADMIN）都能**作废别人发布的定义**。

⇒ ⇒ ⚠️ **为什么本次没顺手修**：TODO-172 的裁决是「**审核者**不能**审**自己
创建的」⇒ ⇒ 「作废」≠「审」⇒ ⇒ ⇒ 裁决**没有**覆盖它
⇒ ⇒ ⇒ 要不要一并禁（作废也算「治理动作」）是**产品语义** ⇒ ⇒ ⇒ 单独登记。

⇒ ⇒ **实际可利用性**：低 ⇒ ⇒ 作废一个**别人**的定义 ⇒ ⇒ 对方的工作流被打断
⇒ ⇒ ⇒ 但作废是**可逆的**（重新发布需要 REVIEWER ⇒ ⇒ 前提是那条定义还能被
看到 ⇒ ⇒ PUBLISHED + ALL_USERS ⇒ ⇒ 可见 ⇒ ⇒ ⇒ 可以重新发布回来）
⇒ ⇒ ⇒ ⇒ 属「可用性」而非「数据泄露」。

⇒ ⇒ **建议改法**：与 publish 同款 ⇒ ⇒ `created_by == actor` ⇒ ⇒ 403
（**除非**该定义本来就是他建的 ⇒ ⇒ 那时他作废自己的当然可以）。

**何时做**：低优先（⇒ ⇒ 但改的时候**别忘了 publish 那条已经落地** ⇒ ⇒
⇒ ⇒ 两边口径应当一致 ⇒ ⇒ ⇒ 一起改才不分裂）

**归属**：P10-F 之外的独立批（**产品语义**）

### ✅ **已关闭 · 2026-11-19 · P10-G**（人裁决：**① PUBLISHED 禁自审 / DRAFT 自己能删**）

| 定义状态 | 谁能作废 |
|---|---|
| **DRAFT** | **只有创建人**（草稿只有创建人看得见 ⇒ ⇒ 别人 ⇒ ⇒ **404**，与「不存在」同形） |
| **PUBLISHED** | **除创建人以外的**审核角色（REVIEWER / APPROVER / SYSTEM_ADMIN） |

⇒ ⇒ **可见性成为唯一判据** ⇒ ⇒ 「谁能作废」直接由 `visible_clause` 决定
⇒ ⇒ 不另写一份 Python 规则 ⇒ ⇒ **列表 / 详情 / 作废三处不会漂**。

⚠️⚠️ **端点的角色闸必须挪走**（这条是本条裁决的**真正代价**）：

端点原来对 `obsolete` 一律 `require_roles(PUBLISH_ROLES)` ⇒ ⇒ **创建人
（哪怕只是 DESIGNER）连自己的草稿都删不掉** ⇒ ⇒ 与「DRAFT 保留创建人
自救通道」**直接冲突** ⇒ ⇒ ⇒ 「没人能删草稿」的死角**又回来了**
⇒ ⇒ ⇒ 角色闸改成**按状态分档**（PUBLISHED 要审核角色 · DRAFT 只要创建人）
⇒ ⇒ ⇒ 角色闸因此**挪进 service 层**（只有 service 层知道状态）。

⚠️ **错误码是新的**（`REPORT_DEFINITION_SELF_OBSOLETE_FORBIDDEN`）⇒ ⇒ 不复用
publish 的 `..._SELF_REVIEW_FORBIDDEN` ⇒ ⇒ 「作废」≠「审」⇒ ⇒ 复用会让人
以为该去「发布」。

⇒ ⇒ **证据**：后端 4 例新测试（1 例「创建人不能作废自己的已发布定义」
· 1 例「别人能作废」正对照 · 1 例「创建人能删自己的草稿」
· 1 例「别人的草稿 ⇒ ⇒ 404」）⇒ ⇒ **变异自证 2 条**（删禁自审 ⇒ 红 ·
删可见性闸 ⇒ 红）⇒ ⇒ 既有那条「无项目授权 ⇒ ⇒ 404」的夹具改成**先发布**
（否则 404 会来自「草稿只有创建人看得见」⇒ ⇒ 断言**不敏感**）。

---

## TODO-191: 前端「保存并发布」对**创建人自己**没有提示 ⇒ ⇒ 点了才吃 403 🟢

**现状**（2026-11-18 · TODO-172 裁决落地时查出来）：

`pcs-frontend/src/pages/report/ReportDefinitionEditorPage.tsx:242` 的
「保存并发布」（`thenPublish`）⇒ ⇒ 直接调 `reportBuilderApi.publish(def_id)`
⇒ ⇒ ⇒ 创建人**自己**是 REVIEWER 时 ⇒ ⇒ ⇒ 后端现在返 **403**
`REPORT_DEFINITION_SELF_REVIEW_FORBIDDEN` ⇒ ⇒ ⇒ 前端只在
`setError(errorMessage(err))` 里**显示错误** ⇒ ⇒ ⇒ 用户要**点一次**才知道
「发布须由他人审核」。

⇒ ⇒ ⇒ **功能不算坏**（错误码 + 文案都到位）⇒ ⇒ ⇒ 只是**提示晚了一步**。

**建议改法**（**前端小改 · 属产品体验**）：

① 编辑器页在「当前用户就是创建人」时 ⇒ ⇒ 「保存并发布」按钮
**改成「仅保存草稿」** + Tooltip「**发布须由他人审核**」；
② 或者保留按钮 ⇒ ⇒ 但在点击前就提示「你是创建人，发布需要另一位审核者」。

⚠️ **要不要做**：由人定（**不影响正确性**）⇒ ⇒ ⇒ 后端语义已钉死（TODO-172）
⇒ ⇒ ⇒ 前端只是把「点一下才知道」变成「一开始就知道」。

**归属**：P10-F 之外的独立批（**前端体验**）

### ✅ **已关闭 · 2026-11-19 · P10-G**（人裁决：**① 拆成「保存草稿」+ 发布置灰**）

⇒ ⇒ 编辑器页拿到定义的 `created_by` ⇒ ⇒ 与当前用户（`useAuth().userId`）
比 ⇒ ⇒ **是创建人** ⇒ ⇒ 「保存并发布」**置灰** + Tooltip
（「你是创建人 · 发布须由他人审核（后端 403）」）+ 页面顶部一条说明。

⚠️⚠️ **「置灰」不等于「砍功能」** —— 全仓**只有这一个**发布入口
⇒ ⇒ 且只有创建人能打开编辑器（`update()` 对非创建人返 404）
⇒ ⇒ ⇒ 这个按钮**从来就 100% 失败**（后端 403）⇒ ⇒ 置灰是**如实反映**。

⇒ ⇒ **顺带查出来的一个真缺口** ⇒ ⇒ 前端**没有任何「他人发布」的入口**
⇒ ⇒ ⇒ 「谁来发布」这件事在 UI 上**不可达**（只能走 API）
⇒ ⇒ ⇒ 已登记 **TODO-197**。

⇒ ⇒ **证据**：前端 3 例新测试（创建人 ⇒ ⇒ 置灰 + 提示 · 非创建人 ⇒ ⇒
**可用**（正对照）· 新建态 ⇒ ⇒ 置灰）⇒ ⇒ **变异自证**（删 `disabled` ⇒ 2 例红）。

---

## TODO-193: mock ↔ 契约的漂移棘轮**看不见 `:param` 写法的端点**（14 条欠账） 🟡

**现状**（2026-11-19 · P10-C · T2 暴露）：

`pcs-frontend/tests/mocks/handlers.test.ts` 的棘轮
「devOnly ∩ 契约 的端点清单」**直接拿 MSW 的路径**去比契约的路径：

```
MSW    : /api/v1/projects/:project_id/pipe-line-list
契约   : /api/v1/projects/{project_id}/pipe-line-list
```

⇒ ⇒ **永远不相等** ⇒ ⇒ 凡是用 `:param` 写的 mock 端点，
**这条棘轮根本看不见它** ⇒ ⇒ 「已进契约却没 ajv 校验」的洞一直敞着
⇒ ⇒ （管道一览表那个端点就是靠这个躲过了三年）。

⇒ ⇒ **已修一部分**（2026-11-19 · P10-C · T2）：路径**归一化**
（`:name` → `{name}`）⇒ ⇒ 棘轮**看得见**了 ⇒ ⇒ 代价是**多出 14 条**欠账。

**欠账清单**（**已进契约、但 mock 响应体还没有 ajv 校验**）：

```
/api/v1/checklist/projects/{project_id}
/api/v1/checklist/projects/{project_id}/completeness
/api/v1/heat/{heat_id}
/api/v1/heat/{heat_id}/weight-estimate
/api/v1/lineage/{record_type}/{record_id}/graph
/api/v1/projects/{project_id}/psv/standard-profile
/api/v1/projects/{project_id}/streams
/api/v1/projects/{project_id}/streams/validate
/api/v1/streams/{stream_id}
/api/v1/streams/{stream_id}/properties
/api/v1/streams/{stream_id}/properties/estimate
/api/v1/streams/{stream_id}/review-log
/api/v1/streams/{stream_id}/state-points
/api/v1/streams/{stream_id}/submit
```

⇒ ⇒ 清单**写在测试文件里**（`CONTRACT_ENDPOINTS_NOT_YET_VALIDATED`）
⇒ ⇒ 且有一条断言盯着「**欠账不许悄悄消失**」（端点若从 mock 删了 ⇒ 这里红）
⇒ ⇒ **补完一条就从清单里删一条**（并加进 ajv 校验用例）。

**为什么先登记不一次还完**：这 14 条**每条**都要按契约形状逐字段核
（含 POST 端点的 201/207 响应）⇒ ⇒ 体量超出「P10-C 前端收口」这一批的范围
⇒ ⇒ 单开一批做。

**归属**：**下一批 · mock 漂移棘轮补债**

✅ **已排期**（2026-11-19 人裁）⇒ ⇒ 下一批**做**（与 TODO-194 / TODO-195
落地一起排）⇒ ⇒ 顺序见批次计划。

✅ **已落地**（2026-11-23 · **P10-H · T3**）⇒ ⇒ **本条关闭**

- 新增 `tests/mocks/contract_debt_193.test.ts`：**14 条端点 = 14 条断言**
  ⇒ ⇒ 每条把 **mock 的响应体**过一遍**契约 schema 的 ajv 校验**。
- 棘轮清单：14 条从「欠账清单」**移进「已校验名单」**
  ⇒ ⇒ `CONTRACT_ENDPOINTS_NOT_YET_VALIDATED` 现在是**空集**
  ⇒ ⇒ 但**机制不许删**：① 新增契约端点出现在 devOnly 里 ⇒ ⇒ 立刻红；
  ② 「欠账不许悄悄消失」那条断言保留。
- **变异自证**：把 `seedStreams[0].stream_name` 改成 `undefined`
  ⇒ ⇒ 断言立刻红（错误信息精确到 `missingProperty: 'stream_name'`）
  ⇒ ⇒ 证明这些断言**不是空的**。

⚠️ **4 条的契约**本身就是**裸 object**（`/streams/{id}/properties` ·
`/properties/estimate` · `/state-points` · `/submit`）⇒ ⇒ 后端**没声明形状**
⇒ ⇒ 这 4 条的 ajv 校验只能证明「是个 object」⇒ ⇒ **真正的形状靠前端消费端
保证** ⇒ ⇒ **登记 TODO-199**（后端补具名 schema）⇒ ⇒ **不归本条**。

⚠️ **「替身比被测物更宽容」是本仓第三次撞上** ⇒ ⇒ 这条欠账清单的价值不在
「14 条」这个数 ⇒ ⇒ 在于**棘轮从此看得见 `:param` 写法的端点** ⇒ ⇒
以后新增契约端点若没补校验 ⇒ ⇒ **立刻红**。

---

## TODO-194: 前端**没有项目选择器** ⇒ 「项目作用域」只能取**第一个**有项目的工作区 🟡

**现状**（2026-11-19 · P10-C · T2 引入）：

`useProjectScope`（`pcs-frontend/src/hooks/useProjectScope.ts`）从
`GET /workspaces` 里取**第一个** `project_id` 非空的工作区 ⇒ ⇒ **没有选择器**。

⇒ ⇒ **后果**：一个用户被授权了**多个**项目时 ⇒ ⇒ 前端**只能看到其中一个**
⇒ ⇒ 且是「列表里的第一个」⇒ ⇒ 与用户当前想看的项目**可能无关**。

⇒ ⇒ **为什么先这样**：`GET /workspaces` 对普通用户**只返回自己的**
⇒ ⇒ 「我有授权但不是我拥有的项目」**根本不在列表里**
⇒ ⇒ 真解法是走 `GET /user-projects/me`（**我的全部授权**）⇒ ⇒ 那要配
一个**项目选择器**（UI + 状态）⇒ ⇒ 是独立功能 ⇒ ⇒ 不塞本批。

⇒ ⇒ **本批的临时口径**：管道一览表等页面对**第一个**项目作用域取数
⇒ ⇒ 用户看得见的是「某个项目」⇒ ⇒ **不是**完整的多项目体验。

**归属**：**下一批 · 项目上下文 / 选择器**

✅ **已排期**（2026-11-19 人裁）⇒ ⇒ 下一批**做**（走
`GET /user-projects/me` 拿**我的全部授权** + 一个项目选择器 UI）
⇒ ⇒ 它是 TODO-195 落地（PMS / BEDD 要**真**项目作用域）的**前置**。

✅ **已落地**（2026-11-23 · **P10-H · T1**）⇒ ⇒ **本条关闭**

| 项 | 落点 |
|---|---|
| 状态 | `src/store/projectScope.ts`（zustand · 模块级 ⇒ 换页不丢选择） |
| 候选来源 | `GET /user-projects/me`（我的全部授权）**∪** `GET /workspaces` 挂的项目（admin 全量 / 普通用户 `?owner_id={我}`） |
| 项目名 | `GET /projects/{id}` 的 `ProjectOut.project_name`（授权列表**没有**名字）⇒ ⇒ 拉不到 ⇒ 退回 id 前 8 位 |
| 选择 | 优先级 = **用户已选** > `VITE_PROJECT_ID` hint > 第一个 ⇒ ⇒ hint 只作**首次默认值** |
| UI | `src/components/common/ProjectSelector.tsx`（antd `Select` + `showSearch`）⇒ ⇒ 挂在 `MainLayout` 顶栏（**SPEC §3.2 TopBar「项目切换：下拉，显示最近项目 + 搜索」**） |
| mock | 补 `GET /user-projects/me` + `GET /api/v1/projects/:project_id`（**契约形状** + ajv 校验 ⇒ 棘轮） |
| 顺带 | ① `useProjectScope` 的 `workspaceId` **无人消费** ⇒ ⇒ 删掉 ② 登出 ⇒ ⇒ **清项目作用域**（否则下一个登录的人继承上一个身份选的项目 ⇒ 跨身份越界） |

⚠️ **admin 的额外一条**：`/user-projects/me` 只返**授权行**⇒ ⇒ admin 若没有
授权行 ⇒ 选择器会是空的 ⇒ ⇒ admin 连自己的项目都选不了 ⇒ ⇒ **功能回退**
⇒ ⇒ 所以候选里**并上**「admin 的工作区全量」。

⚠️ **测试里必须 `useProjectScopeStore.getState().reset()`**（store 是**模块级**
的 ⇒ 用例之间会串）⇒ ⇒ `tests/pages/routeWrappers.projectScope.test.tsx` 已踩过一次。

---

## TODO-195: PMS / BEDD **后端没有实体** ⇒ 两页只能是占位（产品语义） 🔴

**现状**（2026-11-19 · P10-C · T2 查明）：

| 前端页 | SPEC 里的对应物 | 后端实况 |
|---|---|---|
| `/pms`「PMS 管道材料规格」 | §7.5 的**项目创建向导**第 2 步「PMS」 | **没有** PMS 表 / 端点；最接近的是 `pipe_classes`（管道等级）⇒ ⇒ **不是同一件事** |
| `/bedd`「BEDD 文档」 | §7.5 的**向导**第 3 步「BEDD 录入」+「分组 Tab 编辑」 | `projects.bedd_json` 这一列**存在**，但**没有任何写入路径**（全仓只有建表迁移提到它）⇒ ⇒ **没有数据** |

⇒ ⇒ 这两页**是前端超前实现**（P45-3-8 Task 35）⇒ ⇒ SPEC 里**没有**
「独立的 PMS 列表页 / BEDD 文档页」⇒ ⇒ **两页与 SPEC 对不上**。

⇒ ⇒ 本批的处置（**保守**，不是产品裁决）：**不发请求** + 页面明写
「数据源尚未接入」+ 给出依据 ⇒ ⇒ 不再 404，但**功能仍是空的**。

⇒ ⇒ **待人裁**（产品语义 ⇒ 执行者不代裁）：
① 删掉这两页（按 SPEC §7.5 归到**向导**里）
② 补后端实体（PMS 表 / BEDD 录入与 SchemaForm）⇒ ⇒ 那是**新功能**（体量大）
③ 保留占位（现状）

**归属**：**下一批 · PMS / BEDD 后端实体落地**

✅ **已裁决**（2026-11-19 人裁）⇒ ⇒ **② 补后端实体** ⇒ ⇒ 本条**不关闭**
⇒ ⇒ 下一批要落的东西（拆开算体量）：

| 子项 | 内容 | 备注 |
|---|---|---|
| **PMS** | PMS 表 + 端点（SPEC §7.5 向导第 2 步「材料规格」） | 前端 `/pms` 页接真端点（列以契约为准） |
| **BEDD** | `projects.bedd_json` 的**写入路径**（现在只有建表迁移提到它 ⇒ ⇒ 补出来的端点**永远返回空**） | 前端 `/bedd` 页接真端点 |

⇒ ⇒ ⚠️ **前置**：项目作用域要能**选**（TODO-194）⇒ ⇒ 否则两页只能取
「第一个项目」⇒ ⇒ 仍是半成品。
⇒ ⇒ ⚠️ SPEC §7.5 的向导里 PMS / BEDD 两步**本身也是空占位**
⇒ ⇒ ⇒ 做完这三件，向导那两步才有内容。

✅ **已落地**（2026-11-23 · **P10-H · T2a + T2b**）⇒ ⇒ **本条关闭**
（人裁 2026-11-23 把口径定死：PMS = 沿用前端形状 + 签署流；BEDD = 按 SPEC
的 9 个分组）

| 子项 | 落点 | commit |
|---|---|---|
| **PMS 表** | `pms_items`（迁移 `p10_004`）⇒ ⇒ 继承 `RecordMixin` ⇒ ⇒ **直接吃通用 9 态工作流**（`/records/PmsItem/{id}/submit-approval`）⇒ ⇒ **不另造签署框架** | `ba116da` |
| **PMS 端点** | `GET/POST /projects/{id}/pms` · `GET/PATCH /projects/{id}/pms/{item_id}` ⇒ ⇒ 无权 ⇒ ⇒ **404**；`pms_no` 项目内唯一 ⇒ ⇒ **409**；**只有 DRAFT 能改** ⇒ ⇒ 锁定态 **409** | `ba116da` |
| **BEDD 写入路径** | `PUT /projects/{id}/bedd`（**整份替换**）⇒ ⇒ 此前 `bedd_json` **从未有过写入路径** ⇒ ⇒ 这一条就是它 | `ba116da` |
| **BEDD 读** | `GET /projects/{id}/bedd` ⇒ ⇒ 没写过 ⇒ ⇒ **空文档**（不是 404） | `ba116da` |
| **BEDD 结构** | `app/schemas/bedd.py` = **SPEC §7.5 分组表的唯一机器可读副本** ⇒ ⇒ 分组模型由 `create_model` **从字段表生成** ⇒ ⇒ 9 个具名 schema 进 OpenAPI（不给「裸载荷字段」闸添债）⇒ ⇒ 未知分组/字段 ⇒ ⇒ **422** | `ba116da` |
| **uiSchema** | 新增 `bedd` 资源（`GET /meta/ui-schema/bedd`）⇒ ⇒ 前端 **分组 Tab**（路径前缀 = 分组） | `ba116da` |
| **前端两页** | `/pms` 接真端点（列不变 · 状态列现在是**真的 9 态** · DRAFT 行给「提交审核」）· `/bedd` 改成**分组 Tab**（不再是占位） | `5d60df7` |
| **类型** | 手写的 `PmsItem` / `BeddSection` **删掉** ⇒ ⇒ 改用生成的契约类型（bug-180 那类漂移从根上没了） | `5d60df7` |
| **mock + 守卫** | 三个 handler 挪进**契约组** + ajv 校验 + **新守卫**：mock 的 BEDD 字段表是后端 `BEDD_FIELDS` 的镜像 ⇒ ⇒ 漂移即红（变异自证） | `5d60df7` |

⚠️ **遗留（不归本条）**：SPEC §7.5 的**向导**里 PMS / BEDD 两步**仍是空占位**
⇒ ⇒ 本批只把**独立页**做实 ⇒ ⇒ 向导那两步要另开。

---

## TODO-199: 4 条端点的契约**本身就是裸 object** ⇒ ⇒ 形状无人保证 🟡

**现状**（2026-11-23 · P10-H · T3 · 还 TODO-193 欠账时**顺带查出来**）：

| 端点 | 契约里的响应 |
|---|---|
| `GET /api/v1/streams/{stream_id}/properties` | `{"type": "object", "additionalProperties": true}` |
| `POST /api/v1/streams/{stream_id}/properties/estimate` | 同上 |
| `GET /api/v1/streams/{stream_id}/state-points` | `{"type": "array", "items": {"type": "object", "additionalProperties": true}}` |
| `POST /api/v1/streams/{stream_id}/submit` | `{"type": "object", "additionalProperties": true}` |

⇒ ⇒ **后端根本没声明这四条响应的形状** ⇒ ⇒ 前端 `src/types/api.d.ts` 生成出来
就是**裸 object** ⇒ ⇒ 前端**只能继续手写类型**（= TODO-039/041 想消灭的那件事）
⇒ ⇒ 也让「裸载荷字段」闸（`check_openapi_payload_coverage.py`）一直欠着。

⇒ ⇒ **P10-H · T3 的 ajv 校验对这 4 条只能证明「是个 object」** ⇒ ⇒ 真正的
形状**只靠前端消费端**保证 ⇒ ⇒ **漂移抓不到**。

**归属**：**下一批 · 契约补洞**（给这 4 条补具名 schema ⇒ ⇒ 前端类型自动生成）

⇒ ⇒ ⚠️ **不是** TODO-193 的尾巴 ⇒ ⇒ TODO-193 已于 2026-11-23 关闭（14 条欠账
逐条还完）⇒ ⇒ 这 4 条**另立一条**（别让「还完了」这句话掩盖「还有 4 条是空的」）。

✅ **已落地**（2026-11-23 · **P10-H · T4**）⇒ ⇒ **本条关闭**

| 端点 | 响应 schema | 备注 |
|---|---|---|
| `GET /streams/{id}/properties` | `StreamPropertiesResponse` | 4 个物性袋 ⇒ `StreamPropertyBag` |
| `POST /streams/{id}/properties/estimate` | `StreamPropertiesEstimateResponse` | `{results: [...]}`（此前 mock 返 `{estimated: 1}` ⇒ **与真后端不同形**） |
| `GET/POST/PATCH /streams/{id}/state-points` | `StreamStatePointResponse`（**已存在** ⇒ 只是挂上去） | 21 个字段全部具名 |
| `POST /streams/{id}/submit` | `StreamTransitionResponse` | 5 个字段 |

- **物性袋的字段表只有一份**：`PropertyAutoCompleter.COMMON_FIELDS` ∪
  `ESTIMATABLE_FIELDS`（**公开化**）⇒ ⇒ `StreamPropertyBag` 用 `create_model`
  **从它生成** ⇒ ⇒ 与 BEDD 分组表同一手法 ⇒ ⇒ 抄第二份必然漂。
- ⚠️ **载荷不许变**：加 `response_model` 后 pydantic 会把未赋值字段补成 null
  ⇒ ⇒ 那会**改变现有载荷** ⇒ ⇒ 4 条都带 `response_model_exclude_unset=True`
  ⇒ ⇒ 只保留端点**真的产出的**键（实测：存量断言「只有填了的键」照绿）。
- ⚠️ **`composition_json` 只在响应侧放宽成可空**（请求侧仍必填）⇒ ⇒ 否则它
  在 OpenAPI 里是**裸 object** ⇒ ⇒ **裸载荷字段闸从 71 涨到 72 ⇒ ⇒ 倒退**。
- 后果：契约 schema **395 → 402**；前端 `src/types/api.d.ts` 同步 ⇒ ⇒
  **这 4 条端点前端终于有类型了**（此前是 `object`）。
- 守卫：后端新测试 `tests/api/v1/test_stream_typed_responses.py`（4 条）⇒ ⇒
  含一条「**载荷不多不少**」的断言（钉住 `exclude_unset` 的意义）。

---

