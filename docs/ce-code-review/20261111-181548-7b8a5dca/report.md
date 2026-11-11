## Code Review Results

**Scope:** `38c91ac..1c3acb9` (standalone scope, branch `main`, 52 files, 7132 changed lines; 可执行非测试行 1238). 工作树 = 被评审的 HEAD, 未做任何修改。
**Intent:** P9B-4 体验批 -- 收口 PCS 物流(SIM 物流)面的 7 处欠账: ①T0-B 账号停用立即生效 (判定移到 actor 层 `current_actor`, async + `Depends(get_db)`, 判 `users.status`, 在手 access token 下一次请求即 401 `USER_DISABLED`; `users` 表无行则放行) ②T0-C `create_stream`/`validate_stream` 一律用 `project.workspace_id` (忽略请求体) ③T0-D 物流血缘改「按源引用查」+ 合成 root (确定性 uuid5) + 具名 schema `LineageGraphResponse` + 未登记类型 fail-closed 404 ④T0-E 真实登录补写 `users.roles` (覆盖) ⑤T0-F mock 登录双闸 (`PCS_ENABLE_MOCK_LOGIN` 默认关 + `is_production`) ⑥T1 批量失败清单提升到 `useStreamBatchSubmit` hook (关弹窗不丢) + 只重试失败项 ⑦T2 物流列表「引用 📎xN」列 (后端两条 GROUP BY 聚合, 口径 = 下游物流 + 闪蒸结果; Q7 裁决后只算同项目).
**Plan:** `docs/superpowers/plans/2026-11-04-p9b-4-ux-batch.md` (plan_source = explicit; legacy 形态, **无 Requirements 节** => 完整性基线 = 计划自带的 9 个 Task 单元 T0-A..T0-F / T1 / T2 / T3 各自的验收步骤).
**Mode:** markdown report-only (`mode.apply_local = false` => 未应用任何修复, 工作树未改动).

**Reviewers:**
- correctness (session, always-on) -- 端点/服务的语义正确性与契约一致性
- security (session, always-on) -- 本批改了鉴权 (actor 层账号状态判定 + mock 登录双闸 + 项目守卫)
- adversarial (session, always-on) -- 对抗视角: 认证旁路 / 持久化写入 / 并发, 外加一条「会绿而真实现红」的部署断言
- project-standards (mid-tier) -- 仓库根 `CLAUDE.md` 管辖全部 52 个改动文件 (无 CODING_STANDARDS.md => 指令文件兜底)
- testing (mid-tier) -- 测试面大改 (8 个测试文件) + 多处新运行时行为
- maintainability (mid-tier) -- **派发失败**: 两次派发都被上游 Token Plan 配额 429 中断 => 该视角本轮缺失 (见 Coverage)
- performance (mid-tier) -- 两条聚合查询 + 血缘「按源引用查」的查询形状
- api-contract (mid-tier) -- `LineageGraphResponse` 具名 schema + `reference_count` 字段 + 响应形状/错误信封
- reliability (mid-tier) -- 207 部分失败闭环 / fail-closed 404 / 错误不吞 / 部署断言
- learnings-researcher (mid-tier) -- `docs/solutions/` 命中两条与本批同构的既往教训
- cross-model peer -- **未运行** (本机只有 Claude 一家 CLI) => 对抗视角由本地 adversarial-reviewer 承担


### Triage Groups

| Group | Findings | Context | Preferred Resolution | Why |
|-------|----------|---------|----------------------|-----|
| 「停用立即生效」的闭环: 前端会话 / 第二条鉴权入口 / 长连接 / 文档口径 | #1, #13, #5, #11 | T0-B 把判定移到 actor 层, 但同一条对外承诺在四处没有兑现: 前端收到 401 `USER_DISABLED` 不结束会话 (#1)、`current_user` 这条第二入口不判状态 (#13)、已握手的 WebSocket 继续推送 (#5)、`admin_users` 的 docstring 仍写着旧边界 (#11) | 先做 #1 (一行白名单 + 一条前端测试) => 它单独就能解掉用户可见的僵尸会话; 再对 #13 与 #5 各做一次「实现 or 明确登记为豁免」的决策 (写进 ADR-0046 §⑤ / SPEC §7.1); #11 的 docstring 随那两个决策一起改写, 与 ADR 逐字一致 | 四处是同一条承诺的四个面, 分头修会留下第二份口径; 先做 #1 是因为它是唯一有用户可见症状的一处. **apply-queue** |
| 血缘面: 角色门 / 未登记类型 / 序列化口径 / 测试钉子 | #3, #8, #4, #9 | T0-D 重写了血缘端点, 四个面需要一起看: 端点没有沿用 streams 的角色门 (#3)、fail-closed 把「能写血缘但不在 registry 里」的类型变成永久 404 (#8)、三个端点对同一行用两种表示 (#4)、fail-closed 的「逐字同形」没有测试钉住 (#9) | 先定 #3 的角色模型 (产品/权限口径, 需一次决策) => 再做 #8 (登记 `PsvResult` 或按 `TwoPhaseResult` 的方式明确登记为「不提供」) => 然后 #4 (统一 `LineageNode` schema) => 最后 #9 (按 #3/#4 定下的形状补断言) | #9 的断言要按 #3/#4 定下来的最终形状写, 先做会白写; #3 是这组里唯一需要人做决定的. **decision-gate** |
| 写下来的口径与代码对不上: 账簿 / docstring / hook 语义 | #10, #16 | 两处「文档或注释承诺 A, 代码做 B」: `TODOS.md` 与 buglog 说 roles 是「合并」而代码是「覆盖」 (#10)、`useStreamBatchSubmit` 的 docstring 说「整批失败才抛异常」而实现把刷新失败也算整批失败 (#16) | #10 先改 (账簿是下一个 agent 的输入源, 且 bug-2156 的 `fix_commit` 指向被推翻的那次提交) => #16 把 `onDone` 移出提交的错误域 | 这组的共同后果是「下一个读代码/读账簿的人会按错的口径改回去」=> 改口径的收益大于改代码. **apply-queue** |


### P1 -- High

| # | File | Issue | Reviewer | Confidence |
|---|------|-------|----------|------------|
| 1 | `pcs-frontend/src/api/client.ts:39` | 后端新增的 401 `USER_DISABLED` 不在 `SESSION_OVER_CODES` 白名单 => 前端不登出、不跳登录页, 被停用用户卡在任意业务页 | correctness, adversarial, api-contract, project-standards | 100 |

- **#1** -- **What:** axios 拦截器的登出条件是 `if (!code || SESSION_OVER_CODES.has(code))`, 而 `SESSION_OVER_CODES` (client.ts:24-31) 只含 MISSING_BEARER / INVALID_TOKEN / EXPIRED_TOKEN / WRONG_TOKEN_TYPE / INVALID_REFRESH / EXPIRED_REFRESH。**Why:** T0-B 让后端在 actor 层每请求判 `users.status` => 停用用户下一次请求即 401 且 body 带 `code="USER_DISABLED"` (pcs-backend/app/api/v1/config.py:565) => 条件为假 => 既不 `clearSession()` 也不跳 `/login` => 用户带着在手 token 停在页面上, 之后每个请求都 401, 只看到「加载物流列表失败」这类通用错误, 永远回不到登录页, 也永远不知道自己被停用。SPEC §7.1 (V2.12, 本批新增) 明写「前端按**普通 401** 处理（跳登录页）」=> 实现没兑现。**Response (机械):** 把 `'USER_DISABLED'` 加进 `SESSION_OVER_CODES` (可选一并加 `'REFRESH_REVOKED'`, ADR-0046 §⑤ 的 tv 闸在 refresh 路径会返回它, 同一形状的既有缺口), 跳转前可加一条「账号已被停用」的提示, 并补一条前端测试 (mock 401 + `{code:'USER_DISABLED'}` => 断言 `clearSession` 被调用且导航到 `/login`)。若产品更想「保留会话 + 页面提示停用原因」, 则改 SPEC §7.1 并按 `CLAUDE.md` 登记 SPEC 修订 -- 两边必须一致。**How sure:** 交叉评审一致 (4 个视角) + 独立验证批次确认 (100)。

### P2 -- Moderate

| # | File | Issue | Reviewer | Confidence |
|---|------|-------|----------|------------|
| 2 | `.gstack/qa-reports/qa-report-pcs-frontend-2026-11-04-p9b4.md:5` | 批末浏览器回归跑在 `f062e27`, 早于本批最终 HEAD `1c3acb9` | project-standards | 75 |
| 3 | `pcs-backend/app/api/v1/lineage.py:137` | 血缘端点没有沿用 streams 的角色门 (CWE-862) | security | 75 |
| 4 | `pcs-backend/app/api/v1/lineage.py:45` | 同一条血缘行在兄弟端点上有两种序列化表示 | api-contract | 75 |
| 5 | `pcs-backend/app/api/v1/ws.py:78` | 已握手的 WebSocket 在账号被停用后继续推送 | adversarial | 75 |
| 6 | `pcs-backend/app/api/v1/ws.py:96` | WS 握手只捕获 `PcsError` => DB 异常逃出成 500 而非 1008 | reliability | 75 |
| 7 | `pcs-backend/app/main.py:53` | 部署断言改判 OpenAPI 路径 => mock-login 路由仍挂着时断言可绿 | adversarial | 75 |
| 8 | `pcs-backend/app/services/lineage_registry.py:57` | fail-closed 血缘守卫让 `PsvResult` 血缘永久 404 | adversarial | 75 |
| 9 | `pcs-backend/tests/api/v1/test_lineage_by_source_ref.py:563` | fail-closed 血缘守卫没有测试钉住「逐字同形 404」 | testing | 75 |
| 10 | `TODOS.md:2946` | 账簿写 roles「合并」, 实现已是「覆盖」 | project-standards, adversarial | 75 |

- **#2** -- **What:** 仓库根 `CLAUDE.md` 的 Per-Batch QA Gate 要求「每批 sprint 的**最后一个 commit 落地后**」跑一次浏览器回归; 本批的 QA 报告把 `f062e27` 记为「批末 HEAD」, pytest 记 5623 passed, 但之后仍有 `4a8e882` (含前端 `StreamLineageTab.tsx` 改动)、`3e362ea`、`74b23fa` 落地, README 已把后端 baseline 更新为 5626 passed。**Why:** 报告 §4b 只用文字论证「§2.2 的实测数字仍然有效、前端零改动」而没有重跑浏览器 -- 而 `4a8e882` 恰恰改了前端血缘 Tab, 所以「前端零改动」这句本身就不成立; 下一批 (P10-A) 若以此为放行依据, 等于没对最终状态回归过。**Response (决策/发布动作):** 在当前 main (批末) 重跑一次 gstack 浏览器回归 (登录 -> 仪表盘 -> 物流列表 -> 物流详情 7 Tab -> 控制台/网络无 error), 把报告的「批末 HEAD」改写成实际回归时的 commit (`1c3acb9`), 补一节「批末重跑」记录 Q7 与 downstream 封顶后的复测结果 (尤其「引用」列与血缘 Tab); 若不打算重跑, 则把报告与 README 的「浏览器 QA 0C-0H-0M」改为「回归于 f062e27」并登记为待补项。
- **#3** -- **What:** `app/api/v1/streams.py` 的每个端点都 `require_roles(user, "DESIGNER", "PROCESS_CONTROLLER", "SYSTEM_ADMIN")` (streams.py:443), 但 `lineage.py` 的三个端点只靠有效 token + 项目成员资格 (导入行是 `from app.api.v1.config import _Actor, current_actor`, 全文件无 `require_roles`)。**Why:** 改前 `record_type='streams'` 分支永远 404 (没有任何写入方造过这种行), 本批让它第一次可达 => 一个角色在 streams 白名单之外 (`_ALLOWED_ROLES` 接受 VIEWER/REVIEWER/CHECKER) 但有 `UserProject` 行的用户, 从 `GET /streams/{id}` 拿 403, 从 `GET /lineage/streams/{id}/graph` 拿 200。**Response (决策):** 先定血缘面的角色模型 -- 若沿用 streams 白名单, 在 upstream/downstream/graph 的最外层 (守卫之前) 加 `require_roles`; 若产品本意是「任何项目成员可读血缘」, 则改 streams 端点的角色列表并记 SPEC 修订, 两条路必须一致。
- **#4** -- **What:** 只有 `/graph` 迁到了具名 schema; `/upstream` 与 `/downstream` 仍是 `response_model=list[dict]`。**Why:** 同一行 `data_lineage` 在 `/graph` 上是 pydantic 往返后的 `2026-09-15T14:00:00Z`, 在另两个端点上仍是 `_serialize` 的 `2026-09-15T14:00:00+00:00` => 同一行的时间戳字符串随端点而变, 且 `/graph` 相对改前的裸 dict 响应是一次未文档化的可见值变化; 未来 `_serialize` 加字段而 `LineageNode` 漏加时会被静默丢弃。**Response (机械):** 三个端点统一用 `list[LineageNode]`, 同一行只走一种表示 (时间戳会从 `+00:00` 变成 `Z`, 这是有意的收敛); 若必须逐字保持旧串, 则反向把 `/graph` 退回原始表示并在 SPEC 登记。
- **#5** -- **What:** T0-B 的对外结论是「停用立即生效」, 但 WebSocket 的凭证检查只在握手时做一次。**Why:** 一个已连上的用户被停用后, 仍会收到推给他的每一条通知, 直到 socket 自己关闭 (它不会)。HTTP 上生效、长连接上不生效, 而文档写的是一条全局规则。**Response (决策):** 在投递路径上重判账号状态 (例如发送前调 `is_account_disabled` + 短 TTL 缓存, 命中即以 1008 关闭), 或让停用动作发事件、由广播注册表关掉对应 socket; 若本批不做, 必须在 ADR-0046 §5 与 UI-SPEC §7.1 里把 WS 通道明确登记为「停用立即生效」的例外, 而不是留一句笼统承诺。
- **#6** -- **What:** 握手只捕获 `PcsError` (ws.py:94-98), 而本批新增的握手期 DB 读 (走 `current_actor` -> `is_account_disabled`) 抛的 SQLAlchemy 连接/连接池超时 (pool_timeout=30) 不是 `PcsError`; 模块里那条 `except Exception` 兜底在 `accept()` 之后的接收循环里, 覆盖不到握手。**Why:** 一次 DB 抖动表现为未处理异常 (ASGI 回 500) 而不是模块 docstring 承诺的 1008 关闭, 运维在 WS 模块里看不到任何日志, 客户端也无法区分「被拒」与「后端坏了」; 这条路径把通知通道与 DB 可用性绑死 (此前握手是纯 CPU 的 JWT 解码)。**Response (机械):** 在 `except PcsError` 之后补一条非业务异常兜底, 同样在 `accept()` 之前以 1008 + `reason="AUTH_UNAVAILABLE"` 关闭, 与现有分支同形。
- **#7** -- **What:** `assert_mock_auth_not_exposed` 改成判 `app.openapi()['paths']`, 而 OpenAPI 是路由表的**派生视图**, 会漏掉 `include_in_schema=False` 的路由。**Why:** 只要把 mock router 以 `include_in_schema=False` 挂上 (让它从 `/docs` 里消失), 断言就通过, 而 `/auth/mock-login` 仍挂着可达 -- 这条部署 tripwire 变成了对该次改动的静默放过。今天没有活的绕过 (生产环境 `create_app` 不挂 mock router, main.py:175-176, `mock_auth.py:57` 也仍拒生产), 所以这是「守卫会绿而现实会红」, 不是当前漏洞。**Response (机械):** 改判路由表而不是 schema (在 `app.routes` 上解析 FastAPI 0.141 的 `_IncludedRouter` 包装), 并补一条「用 `include_in_schema=False` 挂载时断言仍报错」的回归测试。
- **#8** -- **What:** 守卫注册表由 `RECORD_TYPE_REGISTRY` 派生, 而那张表**不含 `PsvResult`** -- 但 `PsvResult` 正是会写血缘行的模型之一 (`finalize_calc_record` -> `LineageTracker.track` 写 `record_type='PsvResult'`, psv_persist.py:444)。**Why:** 改前守卫会跳过未登记类型, `GET /lineage/PsvResult/{id}/graph` 能查到真实血缘; 改后同一条请求对每个 PSV 记录都是硬 404。仓库内没有调用方 (前端只查 `/lineage/streams/...`), 所以外部消费未被证实。**Response (机械):** 把每个会写血缘行的模型都登记进守卫表 (加 `LINEAGE_GUARDED_RECORD_TYPES["PsvResult"] = (PsvResult, "psv_id")`), 并加一条遍历「实际传给 `finalize_calc_record` 的模型」的测试断言每个类名都有守卫条目; 若产品决定 PSV 不提供血缘, 则按 `TwoPhaseResult` 的方式登记 (TODO + SPEC 注明)。
- **#9** -- **What:** 本批新加的两条「未登记类型」用例只断言 `status_code == 404` (test_lineage_by_source_ref.py:563, 574), 而同族用例 (tests/test_lineage_api.py:104、tests/api/v1/test_lineage_guard.py:184-185) 都断言 body (code + message)。**Why:** T0-D 做 fail-closed 的**全部目的**是响应与「记录不存在」**逐字同形**、不成为枚举信号; 将来有人把该分支的 detail 改成别的文案, 或让错误信封带上别的 code, 没有任何测试会红。同一条防线还有两处零覆盖: `/upstream` 的对外形状变了 (未登记类型此前 200 + [], 现在 404), 但没有任何 `/upstream` 用例覆盖未登记类型或 `record_type='streams'`。**Response (机械):** 补三条断言 -- 未登记类型与「不存在」逐字同形 (status + code + message 三者都相等)、已授权物流的 `/upstream` 返 200 且 body 为空数组、未登记类型的 `/upstream` 返与基准 404 逐字相同。
- **#10** -- **What:** T0-E 的最终实现是**覆盖** (`token_issuer.py` 的 `_write_real_role` docstring 明写「覆盖, 不是合并」, 执行 `.values(roles=[role])`), 但本批新写的两处账簿仍描述成**合并**: `TODOS.md` 的 TODO-134 闭环说明与 `.wolf/buglog.json` bug-2156 的 `fix` 字段。**Why:** 下一个读账簿的人 (或 agent) 会以为「合并」才是口径, 把 `_write_real_role` 改回只增不减 => 角色降级永不生效 (按 `users.roles` 圈人的通知逻辑会继续找已降级的人, 正是 `.wolf/cerebrum.md` 的 Do-Not-Repeat 条目点名要避免的); 而且 bug-2156 的 `fix_commit` 指向 `69b2327`, 正是**被本批自己推翻**的那一版, 反查单点来源会落到错误的提交上。**Response (机械):** 把两处「合并」改成「覆盖」并写明后果, 把 bug-2156 的 `fix_commit` 更新为真正落地覆盖语义的那次提交 (并注明原 `69b2327` 为已被推翻的合并版), 顺带把 TODO-134 标题下旧的「建议改法: ... 合并真实角色」标注为已被覆盖口径取代。

### P3 -- Low

| # | File | Issue | Reviewer | Confidence |
|---|------|-------|----------|------------|
| 11 | `pcs-backend/app/api/v1/admin_users.py:107` | docstring 仍宣称在手 access 可用至过期 | correctness | 100 |
| 12 | `pcs-backend/app/api/v1/lineage.py:166` | `_stream_graph` 重复查 Stream, 守卫返回值被丢弃 | correctness | 100 |
| 13 | `pcs-backend/app/api/v1/auth.py:149` | 停用判定未覆盖 `current_user` 依赖的 7 个端点 | correctness, security | 75 |
| 16 | `pcs-frontend/src/pages/sim/hooks/useStreamBatchSubmit.ts:81` | 提交已成功但列表刷新失败 => 报成「批量提交失败」 | reliability | 75 |

- **#11** -- **What:** 该 docstring 的「已知边界」段仍写着「在手 access 仍可用至过期 (默认 30 分钟)」且标成「不得表述为已解决」, 而 ADR-0046 §⑤ 已在本批改写为「停用的即时失效已解决」。**Why:** 代码注释与 ADR/SPEC 互相矛盾 => 运维读注释会以为离职者的 token 还能用半小时。**Response (机械):** 改写该段 -- 停用已在 actor 层每请求判 `users.status` => 在手 access **立即** 401 `USER_DISABLED`; 仍然成立的边界是「**角色变更**不即时生效」(role claim 在 token 里, 要到 refresh 才更新), 与 ADR-0046 §⑤ 逐字一致。
- **#12** -- **What:** 本批给 `_guard_record_access` 加了返回值并在 docstring 里写明「调用方不必再查一次」, 但三个调用点全都把它丢掉, `_stream_graph` 又 `session.get(Stream, stream_id)` 取了一遍。**Why:** 新增的返回值契约是**死的**, 读代码的人会以为它被用上了。**Response (机械):** 把守卫的返回值传下去 (`_stream_graph(session, stream, *, max_depth)`), 删掉 `_stream_graph` 里的 `session.get` 分支 (守卫已保证行存在, 不存在时它自己抛 404)。**注意:** 这**不是**多一次 DB 往返 -- `Session.get` 先查 identity map, 守卫的 `select` 已把该行放进 identity map, 真实后果只是一处冗余再取 + 一条没被兑现的 docstring 契约。
- **#13** -- **What:** ADR-0046 §⑤、`user_status_service.py` 的模块 docstring 与本批计划都写「一处判定、**全局生效**」, 但 `GET /auth/me` (auth.py:287) 与 meta.py 的 6 个端点用的是另一个依赖 `current_user` (auth.py:149, 纯 JWT 解码、**不查 `users.status`**)。**Why:** 被停用用户的会话自检仍返 200 => 前端认为会话有效 (叠加 #1 的「没有登出」=> 僵尸会话)。影响面小 (`/auth/me` 只回调用者自己的身份, meta 只回静态字典, 不泄露用户数据), 但「全局生效」这句在代码上不成立, 且没有任何测试钉住这些端点的停用行为。**Response (决策):** 首选让 `current_user` 也做同样判定 (改 async + `Depends(get_db)`, 复用 `is_account_disabled`); 次选是刻意豁免 -- 在 ADR-0046 §⑤ 与 SPEC §7.1 明确登记这 7 个端点为豁免并写明理由。两条路都必须留一条测试钉住「停用用户在这些端点上得到什么」。
- **#16** -- **What:** hook 的 `submit()` 把「提交请求」与「提交后的列表刷新 (`onDone`)」放在同一个 try 里、共用一个 catch (useStreamBatchSubmit.ts:76-86)。**Why:** `onDone` 一旦 reject, catch 会 `setResult(null)` (把刚拿到的批次摘要弹窗关掉) 并把异常 rethrow 给页面 => 页面顶部显示「批量提交校对失败」, 而批次其实已经提交成功; 用户据此重发整批。这与 hook 自己的 docstring（「批次**整批**失败才抛给调用方」）和 catch 里的注释（「整批失败 => 没有新摘要」）不一致。今天唯一消费者传的 `onDone` 是 `load()`, 而 `load` 自己吞掉了所有异常 => 这条路径目前是潜伏的而非活跃故障, 但它是一颗装在失败路径上的地雷。**Response (机械):** 把刷新移出提交的错误域 -- 提交结果确定后刷新失败只记日志, 不清 `result`、不 rethrow。


### Requirements Completeness

计划来源 = explicit (`docs/superpowers/plans/2026-11-04-p9b-4-ux-batch.md`)。该计划是 legacy 形态, **没有 Requirements 节** => 需求提取为空, 完整性基线按计划自带的 9 个 Task 单元各自的验收步骤核对。

| Task | 覆盖 | 依据 / 缺口 |
|---|---|---|
| T0-A 守卫覆盖快照 | met | 快照表落在 `TODOS.md` TODO-129 (d585564): 本批动的三个模块都有守卫, 缺口 (vessel/psv/restriction/thermosiphon/report_builder/locks) 按 Step 4 登记为独立审计 TODO |
| T0-B 账号停用立即生效 | partially addressed | actor 层 async 判定、`users` 无行放行、WS 握手连带改造、ADR-0046 §⑤ 同 commit 改写、开销实测 (P50 0.198ms / P95 0.297ms / P99 0.380ms, 100 次真实 PG) 全部落地; **前端侧未兑现** SPEC §7.1 的「跳登录页」=> **#1** |
| T0-C workspace 归属 | met | `create_stream`/`validate_stream` 一律用 `project.workspace_id` (streams.py:320-330, 366-374), 字段标 deprecated, 跨项目用例已写 |
| T0-D 物流血缘 | partially addressed | 按源引用查 + 合成 root (确定性 uuid5) + 派生注册表 (`model.__name__`) + fail-closed + 具名 schema `LineageGraphResponse` + 前端 tooltip + SPEC 词表说明 全部落地, 键口径三条配套测试齐全; 但镜像测试的「可写出类型」集合取的是 `RECORD_TYPE_REGISTRY` 而非实际写入方 => **#8**; fail-closed 的「逐字同形」只钉了状态码、`/upstream` 形状变化零覆盖 => **#9** |
| T0-E roles 补写 | met (实现) / partially addressed (账簿) | 实现是覆盖语义且测试覆盖 (追加/覆盖/重复登录/mock 不写); 账簿仍写「合并」且 bug-2156 的 `fix_commit` 指向被推翻的提交 => **#10** |
| T0-F mock 登录双闸 | met | `PCS_ENABLE_MOCK_LOGIN` 默认关 + `is_production` 双闸 (mock_auth.py:57)、启动期断言已加 (main.py:44-55); 断言本身的盲区 => **#7** |
| T1 只重试失败项 | met | hook 提升失败清单、关弹窗不丢、只重试失败项、重试后清单替换; T1 commit 是纯前端 (4 个文件) => 「116 无后端改动」达标 |
| T2 引用 📎xN | met | `StreamResponse.reference_count` + 两条 GROUP BY 聚合 (整个列表 2 次往返, 有 N+1 守卫) + 前端列 (0 => 「—」, >0 => 📎N) + mock 同步 + 裸载荷 71 未涨; Q7「只算同项目」是调用方裁决 (74b23fa), 已登记在 SPEC §7.7.1 与 TODOS.md |
| T3 SPEC/账簿/QA 收口 | partially addressed | SPEC §7.7.1/§7.7.2、TODOS 六条闭环、buglog、cerebrum Do-Not-Repeat 全部落地; 但浏览器回归跑在 `f062e27` 而非最终 HEAD => **#2**; 运维手册 (P10-E) 按计划本身的口径延后到 P10-E 出, 已登记 (a5f62c6) |

**反向检查 (diff 相对计划引入的、计划未要求的行为规则):**

- `/graph` 的 `occurred_at` 因改用具名 schema 而从 `+00:00` 变成 `Z` -- 计划未要求这一条可见值变化。已由 **#4** 承载, 不另开条目。
- Q7「只算同项目」改变了 `reference_count` 的可见口径, 但它来自调用方/委员会裁决并已登记进 SPEC 与账簿 => 属「已请求」, 不记为计划外行为规则。
- 其余未发现计划未要求的行为规则。

**未覆盖的 Task / 需求单元:** 无 -- 9 个 Task 均有对应实现落地; 上述 partial 项全部由既有 finding 覆盖 (其中 #1 是计划 T0-B / SPEC §7.1 自身写下的未兑现承诺, 已按 explicit 计划来源以 P1 进 actionable 队列)。


### Actionable Findings

| # | File | Issue | Route | Notes |
|---|------|-------|-------|-------|
| 1 | `pcs-frontend/src/api/client.ts:39` | 401 `USER_DISABLED` 不在 `SESSION_OVER_CODES` => 被停用用户卡死在页面上 | `gated_auto -> downstream-resolver` | `suggested_fix` present -- 一行白名单 + 一条前端测试 |
| 3 | `pcs-backend/app/api/v1/lineage.py:137` | 血缘端点无 `require_roles` 角色门 | `manual -> downstream-resolver` | 需先定血缘面的角色模型 (决策), 再落代码 |
| 4 | `pcs-backend/app/api/v1/lineage.py:45` | 同一血缘行两种序列化表示 | `gated_auto -> downstream-resolver` | `suggested_fix` present -- 三端点统一 `list[LineageNode]` |
| 6 | `pcs-backend/app/api/v1/ws.py:96` | 握手 DB 异常逃出 `except PcsError` => 500 | `gated_auto -> downstream-resolver` | `suggested_fix` present -- 补非业务异常兜底 (1008) |
| 7 | `pcs-backend/app/main.py:53` | 部署断言改判 OpenAPI => mock 路由仍挂时断言可绿 | `manual -> downstream-resolver` | `suggested_fix` present -- 改判路由表 + 补回归测试 |
| 8 | `pcs-backend/app/services/lineage_registry.py:57` | fail-closed 让 `PsvResult` 血缘永久 404 | `manual -> downstream-resolver` | `suggested_fix` present -- 登记 `PsvResult` 或按 `TwoPhaseResult` 方式登记为不提供 |
| 9 | `pcs-backend/tests/api/v1/test_lineage_by_source_ref.py:563` | fail-closed 「逐字同形 404」无断言 | `gated_auto -> downstream-resolver` | `suggested_fix` present -- 补三条同形断言 |
| 10 | `TODOS.md:2946` | 账簿写「合并」, 实现是「覆盖」 | `gated_auto -> downstream-resolver` | `suggested_fix` present -- 改两处口径 + 更新 `fix_commit` |
| 12 | `pcs-backend/app/api/v1/lineage.py:166` | 守卫返回值被丢弃, `_stream_graph` 重复查 | `gated_auto -> downstream-resolver` | `suggested_fix` present -- 传返回值, 删 `session.get` 分支 |
| 16 | `pcs-frontend/src/pages/sim/hooks/useStreamBatchSubmit.ts:81` | 刷新失败被报成「批量提交失败」 | `gated_auto -> downstream-resolver` | `suggested_fix` present -- `onDone` 移出提交错误域 |

### Decisions Required (human / release -- 不在 apply 队列, report-only)

| # | File | Issue | Route | 需要什么 |
|---|------|-------|-------|---------|
| 2 | `.gstack/qa-reports/qa-report-pcs-frontend-2026-11-04-p9b4.md:5` | 浏览器回归早于最终 HEAD | `advisory -> release` | 决定是否在批末重跑一次回归 (发布动作) |
| 5 | `pcs-backend/app/api/v1/ws.py:78` | 已握手的 WS 在停用后继续推送 | `advisory -> human` | 决定「投递路径重判状态」还是「明确登记为豁免」 |
| 11 | `pcs-backend/app/api/v1/admin_users.py:107` | docstring 与 ADR 口径矛盾 | `gated_auto -> human` | 随 #5 / #13 的决策一起改写 (口径统一) |
| 13 | `pcs-backend/app/api/v1/auth.py:149` | `current_user` 这条第二入口不判状态 | `manual -> human` | 决定「补判定」还是「登记豁免」 |


### Learnings & Past Solutions

- [Known Pattern] `docs/solutions/security-issues/midflight-config-rebind-defeeds-one-shot-guards.md` -- **本批正面命中**: T0-B 把账号状态判定从一次性登录闸门移到 actor 层、每次请求重读可变真值, 正是该教训要求的形状; 其「查不到就放行」的 fail-open 窗口 (遗留 `user_id` 行) 已登记为 residual risk。
- [Known Pattern] `docs/solutions/testing-issues/sqlite-staticpool-hides-uncommitted.md` -- **本批正面命中**: 新的 WS 守卫用例显式 commit 并让握手用自己的 session factory 指向同一个 engine, T0-B 用例断言错误码而非状态码并使用 `strict_client` => 三处都按该教训的纪律写。
- [Known Pattern] `docs/solutions/testing-issues/narrow-declaration-is-not-a-constraint.md` -- **未闭合的一半**: 血缘注册表的镜像用例钉的是「对 `RECORD_TYPE_REGISTRY` 的覆盖」, 不是「派生」; 而 `RECORD_TYPE_REGISTRY` 本身不是 `finalize_calc_record` 的写入方清单 => 「所有能写出血缘行的类型都在注册表里」这句没有被任何测试证明 (见 #8 及其 testing gap)。另: `reference_counts` 的 Q7 同项目过滤也是一条没有反例测试的「前瞻性保护」。
- [Known Pattern] `docs/solutions/testing-issues/guard-test-fooled-by-lying-comment.md` -- **相关但未被违反**: `main.py:48-52` 的注释断言「FastAPI >= 0.141 懒挂载 => 旧的 `app.routes` 断言一直是空转」, 同一说法被抄进 `.wolf/buglog.json` 的 `root_cause`。learnings-researcher 在系统解释器的 fastapi 0.135.3 上把它证伪, 但 `pcs-backend/uv.lock` 锁的是 fastapi 0.141.1 (= 在役版本) => 该「误诊」未被证实, 本轮不作为 finding 登记, 只留一条 residual risk (版本敏感的断言应写明验证时的版本)。
- [Known Pattern] `docs/solutions/database-issues/information-schema-not-scoped-by-search-path.md` -- **不适用**: 本批未改任何 `alembic/versions/*` (无漂移风险), 新聚合只用普通 IN + GROUP BY + count(), 无方言相关选项。


### Coverage

**评审团队与结果**

| Reviewer | Tier | 结果 |
|---|---|---|
| correctness | session | 4 条 finding, 全部保留或合并 |
| security | session | 2 条 finding, 全部并入保留项 |
| adversarial | session | 6 条 finding: 4 保留, 1 合并, 1 降为 testing gap |
| project-standards | mid-tier | 3 条 finding, 全部保留 (其中一条与 adversarial 重复合并) |
| testing | mid-tier | 4 条 finding: 1 条伞形项保留, 3 条降为 testing gap |
| maintainability | mid-tier | **FAILED** -- 两次派发都被上游 Token Plan 配额 429 中断 (第二次运行 30 分钟未产出 artifact) => 结构性/可维护性视角**本轮未覆盖** |
| performance | mid-tier | 2 条 finding: 1 条因已裁决方案的偏好被丢弃, 1 条在锚点 50 被抑制并路由到 residual risk |
| api-contract | mid-tier | 2 条 finding, 全部并入保留项 |
| reliability | mid-tier | 2 条 finding, 全部保留 |
| learnings-researcher | mid-tier | 非结构化返回 (扫 `docs/solutions/` 10 个文件); 本轮无 pack rule (`roster.packs.roots` 为空), 其条目均未成为 finding (见 Learnings & Past Solutions) |

**评审环境与范围 (dispatch 交接, 逐字)**

- project standards: 用仓库根 CLAUDE.md 作判据（无 CODING_STANDARDS.md => 指令文件兜底）；该文件同时指向 .claude/rules/openwolf.md（属本 checkout 的生效规则）。
- cross-model pass: not run —— 本机只装了 Claude 一家 CLI（codex / grok / cursor-agent / composer / opencode 均未安装），无可用的异族路由 => 对抗视角由本地 adversarial-reviewer 承担。
- maintainability 视角缺失：两次派发都被上游 Token Plan 配额 429 中断（第二次运行 30 分钟仍未产出 artifact）=> 结构性视角未覆盖。
- 范围修正：调用方给的基线 a5f62c6 早于 T0-B 的实现 commit 9d10767 => 基线修正为 38c91ac（批次真实起点），否则 T0-B 整块落在范围外。
- 未跟踪文件：无（工作树干净）。
- 评审环境限制：所有评审子代理均只读（Read/Grep），未执行任何测试、未执行 EXPLAIN => 涉及运行期行为的结论均为静态阅读推导。
- cross-model pass: not run —— 本机只装了 Claude 一家 CLI（codex / grok / cursor-agent / composer / opencode 均未安装），无可用的异族路由 => 对抗视角由本地 adversarial-reviewer 承担（该评审已完成并交卷 6 条）。

**合成与校验 (Stage 5 / Stage 5b 产出)**

- project standards: 用仓库根 CLAUDE.md 作判据（无 CODING_STANDARDS.md => 指令文件兜底）；该文件同时指向 .claude/rules/openwolf.md（属本 checkout 的生效规则）。全局 ~/.claude/rules 的通用规则（覆盖率 80%、函数 <50 行等）未被当作本批的适用标准。
- 评审环境限制：所有评审子代理均只读（Read/Grep），未执行任何测试、未执行 EXPLAIN => 涉及运行期行为的结论均为静态阅读推导；本批自述的「后端 5626 passed / 前端 1046 tests / 裸载荷 71 / PG 车道 5」与 QA 报告的数字未经独立复核。
- 计划来源 = explicit，但该计划没有 Requirements 节（legacy 形态）=> requirements 提取为空；Stage 6 的完整性基线按计划自带的 9 个 Task 单元（T0-A~T0-F / T1 / T2 / T3）各自的验收步骤核对。
- 结算检查：计划的 T0-B Step 3（方案 B：每请求查 users.status）与 E8（P95 超标才启动「status 塞进 token claim」的独立批）是已裁决的 KTD => performance 那条「每请求多一次 users.status 查询」的候选只是偏好另一种方案，已丢弃；其「加一条性能预算测试」的部分作为 testing gap 保留。结算抑制**已评估**（plan_source = explicit）。
- 被丢弃的候选数：1（performance #1 -- 相对已裁决方案的偏好）；语义合并掉的候选数：6（correctness #1、adversarial #1、api-contract #1、project-standards #1 合成 #1；correctness #4 + security #2 合成 #13；project-standards #2 + adversarial #5 合成 #10；testing #1 + testing #2 合成 #9 的伞形项）。
- mode-aware 降级数：4 -- 3 条从 primary 降为 testing_gaps（#14 N+1 守卫的子串判据、#15 MSW 批量 mock 永不失败、#17 血缘 Tab 负向用例的真实 sleep），1 条从 suppressed 分区降为 residual risk（performance 的 IN 列表，锚点 50）。
- helper 抑制计数：锚点 50 抑制 1 条（performance 的 IN 列表候选）；锚点 25 抑制 0 条；锚点 75 与 100 无抑制。
- first_evidence_backfilled：0；quote-the-line 降级数：0（所有 25 条 compact finding 都带可核对的 first_evidence，其中合并后的 #1 / #10 / #13 使用其主来源评审员的引文）。
- helper 运行：malformed_findings 0、malformed_returns 0（首轮 25 条 / 终轮 23 个 returns 全部通过校验）。
- pre_existing 分区为空：#1（前端 client.ts）、#11（admin_users.py docstring）、#2（.gstack QA 报告）三处引用的文件本身不在本批改动面内，但它们的问题由本批的行为变化直接造成 => 按直接依赖规则留在 primary，不进 pre-existing。

**验证批次 (Stage 5b):**

- 选中 10 条 (#1, #3, #4, #6, #7, #8, #9, #10, #12, #16) => **一个批次**发出, 等待上限内**全部落定** (未超时, 无基础设施失败)。
- 判定结果: confirmed 10 / rejected 0 / unresolved 0 / malformed 0 / failed 0 / shortcut-skipped 0。
- 跳过数为 0 (没有一条满足「有 `first_evidence` 且同时有普通评审员与 `adversarial-<provider>` 独立确认」的免检条件; 本轮跨模型 peer 未运行, 因此没有任何一条可免检)。
- 每条 confirmed 都保留了原有 severity / confidence / 路由; 未因此提升任何严重度或置信度。#1 / #3 / #4 / #7 的判定中给出了受保护主体 (authorization-authentication / public-contract), 与本人的分类一致, 无重分类。

**Residual risks (25, 仅供参考)**

- 调用点完整性: 本轮每一条「`current_actor` 只有 ws.py 一个调用点」/「没有别的 `USER_DISABLED` 消费者」的陈述都基于文本检索 (无符号级或 AST 检索) => reflection / `dependency_overrides` / 动态注册的调用点无法排除。
- `users` 无行时按构造 fail-open: `is_account_disabled` 按 token 的 `user_id` 查 `User`, 查不到即返回 False。一个 `user_id != uuid5(NAMESPACE_DNS, username)` 的遗留账号行对该查询不可见 => 即使 `status=DISABLED` 也完全可访问。该窗口只由仓库的发布前 SQL 检查 (`SELECT count(*) FROM users WHERE user_id <> uuid5_derived(username)) = 0`) 关闭, 是部署前置而非代码缺陷; TODO-137 没有把它登记成停用保证上的洞。
- `users.status` 是无 CHECK 约束的自由 `VARCHAR(20)`, `is_account_disabled` 只与 `UserStatus.DISABLED.value` 比较 => NULL status 或拼错的取值都会读成「未停用」(fail-open)。今天没有代码路径写这种值。
- mock 登录双闸的强度取决于两个条件的组合: `is_production` 是精确字符串比较 (`self.env == "production"`), 而随包的 `pcs-backend/.env.example` 设了 `PCS_ENABLE_MOCK_LOGIN=true`。抄用示例文件且 ENV 不是恰好 `production` (例如 `prod`、`Production`) 的部署会同时挂上 mock router 并通过第二道闸 => mock-login 仍然存活并为 `dan` 签发 SYSTEM_ADMIN token。该开关在 `docker-compose.yml` 与 `.github/workflows` 里都不存在, 任何依赖 mock 登录的部署或 CI 环境必须显式添加。
- WebSocket 握手用查询参数接收 bearer token (`?token=`), 凭证会进入访问日志与代理日志 (CWE-532)。该 token 传输方式本次 diff 未改, 且本仓库内未找到 `/api/v1/ws/notifications` 的前端调用方, 实际暴露程度无法证实。
- `reference_counts` 把整个项目的 stream ids 当 IN 列表下发 (pcs-backend/app/services/stream_service.py:378 与 :393), 而 `list_by_project` 没有 LIMIT => 每次列表请求一个 stream id 一个绑定参数、两条查询, 计划成本随项目规模而不是随返回页数增长。这个 IN 列表还与已有的 `project_id` 谓词冗余 (ids 是该项目的子集)。今天没坏; 建议与 TODO-143 的索引工作合并到 P10-D, 不要单独上线。
- `LineageTracker.by_source_ref` (本次 diff 新增, pcs-backend/app/services/lineage.py:144-176) 过滤 `data_lineage(source_ref_type, source_ref_id)` -- 两列都没有索引 (pcs-backend/app/models/system.py:46-47), 表只增不减 => 每次打开物流血缘 Tab 的成本是一次扫描加一次 `ORDER BY occurred_at DESC, lineage_id DESC` 排序 (LIMIT 在数据库侧生效, 所以响应有界而扫描/排序无界)。根因与已登记的 TODO-143 延后项相同; 复合索引 `(source_ref_type, source_ref_id, occurred_at DESC)` 才能让它变成可提前终止的索引扫描 -- 值得折进 P10-D 的索引任务。
- `LineageTracker.by_source_ref` 只按 `source_ref_type`/`source_ref_id` 过滤, 没有 `project_id` 谓词, 而同批的计数列刚拿到一个 (Q7: 只算同项目)。今天没有代码路径会造出跨项目引用 (`create_outlet_stream` 强制 `source.project_id == project_id`; `flash_persist` 用 `stream.project_id`), 所以这是一致性/加固项而非已证实的缺陷。
- `reference_count` 是 `StreamResponse` 上的公开字段, 但只有项目物流列表端点会算它; `GET`/`PATCH /streams/{id}` 恒答 0 => 「0」同时意味着「没有引用」和「没算」。OpenAPI 描述 (「下游物流数 + 闪蒸结果数」) 没有说明该字段只由列表端点填充, 外部消费方照契约读会信任一个错数。 (已作为本批的已知限制登记; 前端只在列表页读该字段。)
- `CreateStreamRequest.workspace_id` 现在被接受并静默丢弃 (端点强制 `project.workspace_id`)。这个变更已公告 (OpenAPI `deprecated:true` + description), 前端也从不发该字段, 但一个刻意指向别的工作区的外部客户端收不到任何 409/422 告知它自己的值被忽略了。
- 前端的 `SESSION_OVER_CODES` 集合同样缺 `'REFRESH_REVOKED'` -- ADR-0046 §5 的 token_version 闸可以从 `POST /auth/refresh` 返回它 (既有缺口, 早于本批), 但与 #1 的 `USER_DISABLED` 是同一形状。
- 对 `record_type='streams'`, `/upstream` 答 200 + [] 而 `/graph` 与 `/downstream` 答数据或 404 -- 「没有上游血缘行」与「不存在」的区分是刻意设计并在端点 docstring 里写明的, 但三个端点对同一记录族给出三种状态/形状组合 => 客户端必须特判 streams。
- MSW 的血缘 mock 无论请求什么 `record_type` 都返回合成 root (`source` 为 `MANUAL`、`change_summary` 为「物流本身（合成根节点）」), 而后端对非 streams 的记录类型返回真实血缘行 (`source` 为 `CALC`)。形状符合契约 (ajv 校验过), 但语义只对 `record_type='streams'` 与后端一致。
- `current_actor` 每请求读一次 `users.status`, 其中的 DB 失败会向上抛 (不吞、不转成「用户不存在」) => 一次 DB 抖动就让所有 `Depends(current_actor)` 的端点返 500。方向是 fail-closed (拒绝所有人而不是放行所有人), 与本批意图一致, 但它自己没有降级信号 (无状态缓存、无熔断)。
- WS 握手现在与 DB 共命运 (此前是纯 CPU 的 JWT 解码): DB 不可用或连接池耗尽时, 一次握手要等满 `pool_timeout=30s` 才失败 => 重连风暴下每次握手占 30s。连接池参数本身 (pool_size=10 / max_overflow=20 / pool_timeout=30) 未变。
- 每请求一次的 `users.status` 探测由**每个**已认证请求承担, 不只是本批关心的那 20 个物流端点; 导入图的爆炸半径估计是下界, 因为图不跟踪 `Depends()` 式的用法。成本本身是已裁决项 (计划 T0-B Step 4 实测过 P95 阈值; 计划条目 E8 把「status 塞进 token claim」保留为独立批次, 只在实测 P95 超标时才启动) => 此处不重提。
- `users.roles` 只在真实登录成功时被覆盖: 若一个人被从所有映射的 LDAP 组里移除, `resolve_role` 抛 `LdapAuthError` => 登录失败 => 覆盖不发生 => `users.roles` 保留旧角色 => 按角色圈人的通知逻辑 (`notification_recipients.resolve_role_recipients`) 仍会选中他。AD 同步 (`ad_sync._apply`, 无角色时覆盖并置空) 覆盖了这个场景, 所以这依赖 AD 同步在跑 (ADR-0046 把「角色变更不即时生效」登记为已知边界)。
- 引用数的口径 (下游物流 + 闪蒸结果) 与删除门禁的口径 (状态点 + 闪蒸结果) 刻意不同, 且不共享任何常量或断言 => 改一个不会让另一个变红 (SPEC §7.7.1 记录了这个差异, 但代码里没有钉住它)。
- `reference_count` 在 OpenAPI 里带 `default: 0` 但不在 required 列表里 => 前端的 ajv 棘轮在某个 seed 或 mock 漏掉它时不会红 (ajv 不套用默认值); 今天只有 tsc 能抓到这种漂移。
- FastAPI 版本敏感性: `pcs-backend/uv.lock` 锁 fastapi 0.141.1 而系统解释器是 0.135.3 => 依赖框架路由/Schema 行为的断言是版本绑定的 (`main.py` 关于「FastAPI >= 0.141 懒挂载」的注释描述的是锁定版本而非系统版本) => 这类断言应写明它是在哪个版本上验证的。
- `pcs-backend/app/api/v1/lineage.py` 的 `_stream_graph` 又用 `session.get(Stream, stream_id)` 取了一遍 stream, 尽管守卫已经加载过该行; 这不是额外往返 (`Session.get` 先查 identity map), 代价只是一次冗余再取 + 一个没人用的返回契约 -- 见 finding #12。
- `assert_mock_auth_not_exposed` 在启动时调用 `app.openapi()` => 会物化整份 schema => 一个 response model 无法内省的路由会让启动直接失败, 而不是静默通过 (本次 diff 里没有任何测试走到这个失败面)。
- `pcs-backend/app/services/stream_service.py` 的 `list_by_project` 没有 LIMIT, 列表端点返回整个项目 => 列表端点的每次请求成本随项目规模增长而不是随页数增长; 任何地方都没有断言这个上界 (见 testing gaps)。
- 后端批量提交路径 (`POST /streams/batch-submit`) 没有出现在 diff 的 hunk 里 => 它被当作既有代码处理, 其逐条工作本轮未深入审查。
- `.wolf/anatomy-index.json` 仍把 `pcs-backend/app/services/token_issuer.py` 的符号记作 `_merge_real_role`, 而最终代码把它重命名成了 `_write_real_role` => OpenWolf 索引落后于最后一次重命名; 该文件由 hook 维护、不得手改, 所以这里只作备注。

**Testing gaps (21, 仅供参考)**

- 没有前端测试覆盖「401 `USER_DISABLED` => clearSession + 跳 `/login`」, `SESSION_OVER_CODES` 也完全没有表驱动测试 => 改白名单没有护栏 (#1 背后的缺口)。
- `SESSION_OVER_CODES` 是会话结束码的手写第二份真值 => 后端新增任何「会话结束」码 (`USER_DISABLED`、`USER_LOGIN_DENIED_DISABLED` ...) 客户端都认不出来; 值得做一条架构测试 (后端错误码表 <-> 前端集合) 或一份共享的「会话码」契约。
- 没有用例断言 `/graph` 与 `/downstream` 对 `record_type='streams'` 行为一致 (同样的 `max_depth` => 同样的下游行上限, 都是最新优先) -- SPEC 要求两个端点一致, 但没有任何断言在同样的 `data_lineage` 行上比较它们。
- 没有 HTTP 层的用例覆盖「真的会写血缘行但不在 `RECORD_TYPE_REGISTRY` 里的记录类型」 (今天是 `PsvResult`): 镜像测试是拿 `RECORD_TYPE_REGISTRY` 比的, 而 `app/services/calc_lineage.py` 自己的 docstring 明说该注册表不是 `finalize_calc_record` 的支持集 (鸭子类型, TODO-048) => 测试名夸大了它证明的东西 (#8 背后的覆盖缺口)。
- 没有端到端用例覆盖「跨项目引用 => 列表响应里的 `reference_count` 为 0」: 服务层有两条跨项目排除用例, 但端点只断言 `project_id` 被透传 => 如果端点传错项目 id、或服务层的 `project_id` 谓词被删, 端到端不会红。
- 没有查询计数断言钉住 `GET /projects/{project_id}/streams` 的往返次数 (本批前 4 次 -> 现在 6 次) => 将来有人把两条聚合改成逐行查询仍然会绿。
- 没有性能预算测试覆盖每请求一次的 `users.status` 探测。仓库已有这个模式 (tests/services/test_export_service.py 有性能预算) => 给列表端点加一条请求数或延迟预算, 就能让计划的 P95 阈值 (条目 E8: >5ms 则评估「status 塞进 token claim」) 变成自动闸门而不是一次性测量。
- `reference_counts` 从未用大 id 列表测过 (单测只用了少量 stream) => 一条用几千个 id 的用例 (同时断言返回计数与参数个数/查询形状) 能让 O(项目规模) 的参数增长在成为问题之前就可见。
- 没有测试断言 `by_source_ref` 的 limit 是在数据库侧生效 (而不是取回后再截断) => 一条捕获语句的测试能钉住端点 docstring 声称的「响应有界且扫描有界」。
- 没有测试断言 `_serialize` 新增的字段能活过 `LineageGraphResponse` 响应模型: 现有的「合成 root 与真实 root 同形」用例比较的是 `_serialize` 的 dict 与 `_serialize` 的 dict, 不是与校验后的响应体 => schema/序列化漂移会通过它。
- 没有后端测试断言三个血缘端点对同一行给出同一种表示 (例如同一 `lineage_id` 的 `/graph` 节点体与 `/downstream` 节点体, 含 `occurred_at` 的字符串形态) => #4 的 `+00:00` 与 `Z` 分歧没有护栏。
- 没有用例覆盖 `current_actor` 的 DB 读失败 (连接丢失 / 连接池超时 / 语句超时) => 全系统依赖的行为（「DB 抖动 => 全站 500, fail-closed」）没有被任何测试钉住; tests/api/v1/test_user_disabled_guard.py 只覆盖了 DISABLED / ACTIVE / 无 users 行 / 可 await / 端点仍可用。
- 没有用例覆盖 `users` 行的 `user_id` 不是派生的 `uuid5(NAMESPACE_DNS, username)` (TODO-137 的遗留形态), 也没有覆盖 NULL 或无法识别的 status 取值 => 两者当前都求值为「未停用」, 没有任何记录表明这是有意的。
- T0-E 只覆盖了「行已存在」的各种情形 (追加 / 覆盖 / 重复登录不追加) 加上「mock 从不写」, 没有覆盖「真实登录但角色被降级为空」(`role` 为 None) -- 此时 `_write_real_role` 写 `roles=[role]`, 而 AD 同步那侧写 `roles=[role] if role else None`, 两边在那个边界上不一致。
- `GET /streams/{id}` (单条) 恒答 `reference_count = 0` (已登记的已知限制) => 没有用例钉住「恒为 0」; 前端只在列表页读该字段, 将来一个详情页会静默显示错数。
- 没有前端用例钉住合成 root 与真实 root 暴露同样的字段集: 后端有 `test_synthetic_root_has_same_shape_as_real_root` (同 key), 但前端的 `buildLineageGraph` mock 只被 ajv 按契约形状校验 => 两边可以各走各的而都不红。
- 没有用例覆盖「用户被停用时仍开着的 WebSocket」 (投递路径上的状态复查) -- #5 那个待决场景。
- mock 登录闸门的测试覆盖了 `PCS_ENABLE_MOCK_LOGIN` 这个环境变量名与生产环境的 RuntimeError, 但没有测试断言「用 `include_in_schema=False` 挂载 mock router 时启动断言会触发」 (#7 那个恰好会绿的情况), 也没有断言生产配置下 lifespan 真的跑了那个断言。
- `tests/api/v1/test_deliverables_current_version.py` 里的 N+1 守卫用子串 ('users' in s and 'status' in s) 识别 actor 层的 `users.status` 查询 => 任何同时提到 users 表与 status 列的业务查询都会被误计 (假红), 同时还会被挤出「<= 3 条业务查询」的预算 => 判据应当测编译后语句的表/列名而不是原始 SQL 文本。
- MSW 的批量提交 mock 永远答 `failed: []` => 常驻失败清单条与「只重试失败项」这条路径 (本批的招牌 UX 交付) 在浏览器 QA 通道里永远渲染不出来 => 一次绿色的浏览器回归对 T1 什么也证明不了。
- 血缘 Tab 的负向用例靠真实的 300ms sleep 断言 tooltip 不出现 => 它只证明 tooltip 在那个窗口内没出现 (慢机器上也会过) => 应当用假时钟并断言 tooltip 节点不存在。

---

### Verdict

> **Verdict:** Ready with fixes
>
> **Reasoning:** 1 个 P1 必须先修: T0-B 在后端实现了「停用立即生效」, 但前端不认这个 401 (`#1`) => 被停用的用户带着在手 token 卡在任意业务页上, 永远回不到登录页 -- 这正是本批对外承诺的核心语义, 且 SPEC §7.1 (V2.12) 已写明「前端按普通 401 处理（跳登录页）」=> 实现与自家 SPEC 冲突。其余 9 个 P2 中有 3 个需要一次产品/权限决策 (#3 血缘面的角色模型、#7 部署断言的判据、#8 `PsvResult` 血缘是否提供), 其余是可直接落的机械修复; 4 个 P3 是口径与文档同步。计划 (explicit) 的 9 个 Task 全部有实现落地, 未发现完全未覆盖的 Task 单元, 4 处 partial 已被上表 finding 覆盖。跨模型对抗视角本机不可用 (只有 Claude 一家 CLI), maintainability 视角因配额 429 两次派发失败 => 这两个结构性盲区没有覆盖, 结论以本地交叉评审 + 独立验证批次为准。所有 10 条送检 finding 均被判 confirmed, 无 rejected / unresolved / malformed。
>
> **Fix order:** `#1` (P1, 前端会话结束) -> `#3` 的角色模型决策 (它决定 `#8` / `#9` 的最终形状) -> `#3` / `#8` / `#4` -> `#6` / `#7` / `#9` / `#10` / `#12` / `#16` -> P3 (`#11` 随决策一起改写, `#5` / `#13` 各做一次「实现 or 登记豁免」的决策) -> `#2` 批末浏览器回归

### Actionable Findings (summary)

1. **#1** | P1 | `pcs-frontend/src/api/client.ts:39` | 后端 401 `USER_DISABLED` 不在 `SESSION_OVER_CODES` => 前端不登出、不跳登录页, 被停用用户卡死 | `gated_auto` | suggested_fix: yes | confidence 100
2. **#3** | P2 | `pcs-backend/app/api/v1/lineage.py:137` | 血缘端点没有沿用 streams 的角色门 (VIEWER/REVIEWER/CHECKER 可读) | `manual` | suggested_fix: yes | confidence 75
3. **#4** | P2 | `pcs-backend/app/api/v1/lineage.py:45` | 同一血缘行在 `/graph` 与 `/upstream`/`/downstream` 上有两种序列化表示 | `gated_auto` | suggested_fix: yes | confidence 75
4. **#6** | P2 | `pcs-backend/app/api/v1/ws.py:96` | 握手只捕获 `PcsError` => DB 异常成 500 而非 1008 | `gated_auto` | suggested_fix: yes | confidence 75
5. **#7** | P2 | `pcs-backend/app/main.py:53` | 部署断言改判 OpenAPI 路径 => mock-login 仍挂着时断言可绿 | `manual` | suggested_fix: yes | confidence 75
6. **#8** | P2 | `pcs-backend/app/services/lineage_registry.py:57` | fail-closed 让 `PsvResult` 血缘永久 404 | `manual` | suggested_fix: yes | confidence 75
7. **#9** | P2 | `pcs-backend/tests/api/v1/test_lineage_by_source_ref.py:563` | fail-closed 的「逐字同形 404」只钉了状态码 | `gated_auto` | suggested_fix: yes | confidence 75
8. **#10** | P2 | `TODOS.md:2946` | 账簿写 roles「合并」, 实现是「覆盖」; bug-2156 的 `fix_commit` 指向被推翻的提交 | `gated_auto` | suggested_fix: yes | confidence 75
9. **#12** | P3 | `pcs-backend/app/api/v1/lineage.py:166` | 守卫返回值被丢弃, `_stream_graph` 重复查 Stream | `gated_auto` | suggested_fix: yes | confidence 100
10. **#16** | P3 | `pcs-frontend/src/pages/sim/hooks/useStreamBatchSubmit.ts:81` | 提交成功但刷新失败被报成「批量提交失败」 | `gated_auto` | suggested_fix: yes | confidence 75

需要人做决定 (report-only, 不在 apply 队列): **#2** (P2, 批末浏览器回归是否重跑, 发布动作) ; **#5** (P2, 已握手的 WS 是否在投递路径重判状态, 否则登记为豁免) ; **#11** (P3, admin_users docstring 与 ADR 口径统一) ; **#13** (P3, `current_user` 是否补判定, 否则登记豁免)。

Run artifact: `/tmp/compound-engineering-1000/ce-code-review/20261111-181548-7b8a5dca/report.md`
