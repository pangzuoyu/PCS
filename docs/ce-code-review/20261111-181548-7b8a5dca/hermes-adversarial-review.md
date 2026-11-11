# 跨模型对抗性审查 —— hermes（GLM-5.2 / Z.AI）

> 本文件是**外部异族模型**对同一批改动的独立对抗审查产出（ce-code-review 的
> "cross-model pass" 坑位：其自带 worker 只认 codex/claude/grok/cursor/composer/opencode，
> 不认 hermes ⇒ 直接驱动本机 hermes CLI）。
>
> - **模型 / 接收方**：`glm-5.2` · Z.AI / GLM（`Ark.cn-beijing.volces.com`）
> - **出口**：报告 + 补充 + 计划 + hermes 自行读取的源码片段发往上述提供方
> - **只读**：提示词限定只读文件与只读 git 命令；派发前后 `git status` 快照一致 ⇒ **工作树未被改动**
> - **与既有 9 视角的关系**：既有评审全部在 Claude 同族内完成 ⇒ hermes 是**唯一异族视角**
>
> **编排方复核结果**（对 hermes 的关键论断逐条回源码核对）：
> - ✅ **新增 P2「删除被下游物流引用的物流 ⇒ 500」成立**：
>   `_collect_references`（`app/services/stream_service.py:493-537`）只查
>   `stream_state_points` + `flash_results`，**不查** `streams.upstream_stream_id`；
>   而 `app/models/project.py:442-444` 的该 FK **无 `ondelete`** ⇒ PG 默认 NO ACTION；
>   `app/services/outlet_stream.py:164` 每次计算出口流都写 `upstream_stream_id=source.stream_id`；
>   `app/api/v1/streams.py:484-487` 的端点**只捕 `PcsError`** ⇒ `IntegrityError` 裸穿成 500。
>   ⚠️ 本批的 📎 列**恰好把这一类引用变成用户可见承诺**（`reference_counts` 第①条聚合数的就是它）。
> - ✅ **M5 应降为 P3 成立**（hermes 对我先前说法的反驳正确）：`clearFailures()` 的唯一调用点是
>   失败清单条里的「清除」按钮（`StreamListPage.tsx:345`），而弹窗打开时 antd Modal 的
>   **mask 默认开启**（`node_modules/antd/es/modal/interface.d.ts` 的 `mask`）⇒ 整页被遮罩挡住
>   ⇒ 点不到该按钮；弹窗关闭时 `result` 已为 null ⇒ 陈旧清单与提示都不渲染
>   ⇒ **今天没有任何点击序列能生产出 M5 描述的用户可见故障**（结构上仍可漂移 ⇒ 保留为 P3 加固）。
> - ✅ **WS 拒绝信道传输层不可见成立**：`ws.py:97` 的 `close()` 在 `accept()`（:100）**之前**
>   ⇒ 真实客户端看到 HTTP 403 握手失败，1008/reason 只在 Starlette TestClient 里存在。
> - ✅ **#8 的加强论断成立**：`app/api/v1/psv.py:247` 直接查 `DataLineage.record_type == "PsvResult"`
>   ⇒ 该类型**有活跃消费方**，不是「没人用的类型」。
> - ✅ **`StreamListPage.tsx:14` docstring 说谎成立**：该文件头仍写「引用 📎×N 列本批不渲染」。
> - ✅ **CSV 导出缺「引用」列成立**：`exportCsv`（:168）的 headers 无「引用」。

---

读完了全部指定材料（报告、补充、计划、diff 的 52 个文件里核心的 20 个源文件），并对报告 14 条主 finding 里的 12 条逐条到源码核了前提。以下是对抗审查产出。

---

## A. 对代码的对抗性攻击（报告里没有的）

### [P2] 删一条「被下游物流引用」的物流 ⇒ 500 INTERNAL_ERROR，本批的 📎 列恰恰把这个引用类变成了用户可见承诺
- **位置**：`pcs-backend/app/services/stream_service.py:494`（`_collect_references`）+ `pcs-backend/app/models/project.py:442` + `pcs-backend/app/services/outlet_stream.py:164` + `pcs-backend/app/api/v1/streams.py:485`
- **逐字代码行**：
  - stream_service.py:511-509（引用表清单只有两张）：
    `# 1. stream_state_points` … `# 2. flash_results` —— 全函数没有一处查 `Stream.upstream_stream_id`
  - project.py:442-444：`upstream_stream_id: Mapped[uuid.UUID | None] = mapped_column(` `ForeignKey("streams.stream_id")` —— **无 `ondelete`** ⇒ PG 默认 NO ACTION
  - outlet_stream.py:164：`upstream_stream_id=source.stream_id,` —— 每次 PSV/CV/restriction/flash 计算的出口流都写这个 FK
  - streams.py:485-488：`await StreamService.delete(db, stream_id, actor=user.user_id)` `except PcsError as e:` —— 只捕 `PcsError`，`IntegrityError` 裸穿到 `core/errors.py:290` 的兜底 handler
- **触发条件**（级联）：① 建物流 A → ② 对 A 跑一次 CV/PSV 计算（cv.py 不建 `flash_results`，只建 outlet B：`upstream_stream_id=A`）→ ③ 列表页 A 显示「📎1」（`reference_counts` 第①条聚合**正是**数 `upstream_stream_id`）→ ④ 操作员据此删 A → `_collect_references` 返回 `{}`（无状态点、无闪蒸）→ `db.delete + commit` → FK 违约 → `IntegrityError` → 500 `INTERNAL_ERROR`。
- **后果**：操作员看到「📎1 ⇒ 被引用」然后删除得到一个无任何解释的 500；SIM-35 自己的契约注释（stream_service.py:469-472「被引用时拒绝删除（409 SIM_STREAM_REFERENCED）」）对这个引用类**不成立**，且错误信息永远不会告诉他「先删下游 B」这条唯一出路。DB 层 FK 保住了完整性，但错误契约碎了。这是**组合失败**：删除门禁是旧代码，但本批把「下游物流 = 引用」做成了用户可见语义（列 + SPEC §7.7.1 口径钉死），两个组件各自“正确”，凑起来互相打脸。
- **修法**：`_collect_references` 加第三张表 `select(func.count()).select_from(Stream).where(Stream.upstream_stream_id == stream_id)`（命名字典键 `streams`）；同时在 `StreamService.delete` 里把 `commit()` 的 `IntegrityError` 兜成 409 `SIM_STREAM_REFERENCED`（防御未来新增的引用 FK——`cv_results`/`psv_results` 类的直连 FK 同样不在清单里）。报告 residual risk 只登记了「两个口径刻意不同」，没有登记这个 500。

### [P3] WS 握手的拒绝信道在真实传输层不可见：close-before-accept ⇒ HTTP 403，1008 + reason 永远到不了客户端（「验证机制保真度」类）
- **位置**：`pcs-backend/app/api/v1/ws.py:97`（+ 模块 docstring 第 90-93 行的承诺）
- **逐字代码行**：`await websocket.close(code=_WS_POLICY_VIOLATION, reason=e.code)` —— 调用点在 `await websocket.accept()`（第 100 行）**之前**
- **触发条件**：任何真实浏览器/uvicorn 客户端带停用账号的 token 连 `WS /api/v1/ws/notifications`。按 ASGI 规范，accept 之前发 `websocket.close` ⇒ 服务端以 **HTTP 403 拒绝握手**；关闭码 1008 与 reason `"USER_DISABLED"` 不会以 close frame 形式送达。
- **后果**：模块 docstring 承诺的「客户端可区分被拒原因」在传输层不成立——所有 `PcsError` 拒绝（MISSING_TOKEN / INVALID_TOKEN / USER_DISABLED）对真实客户端是**同一个** HTTP 403。Starlette TestClient 会把 pre-accept close 还原成 `WebSocketDisconnect(1008)` ⇒ **测试观测到的拒绝语义在部署环境不存在**（会绿而现实不同形——正是本次要专门构造的那类问题）。注意：close-before-accept 是既有代码，本批只是加倍押注了这条 docstring（「否则 WebSocket 直接断」）。
- **修法**：二选一并写明：① 先 `accept()` 再 `close(1008, reason)`（忍受 docstring 里反对的那半个缺点），让 reason 真正可达；② 保持 pre-accept 拒绝，但把 docstring 与 reason 参数删掉/改写为「仅日志可见」，避免下一个人继续相信这个信道。报告 #6 的建议修法（「同样以 1008 + AUTH_UNAVAILABLE 关闭，与现有分支同形」）会复制同一个不可见性，见下面 B 部分对 #6 的挑战。

### [P3] 首次真实登录的惰性建行竞态 ⇒ 登录 500
- **位置**：`pcs-backend/app/services/token_issuer.py:105-123`（+ `app/models/project.py:147`）
- **逐字代码行**：
  - `if row is None:` → `session.add(User(` … `))` → `await session.flush()` —— 无 `IntegrityError` 处理
  - project.py:147：`username: Mapped[str] = mapped_column(String(100), unique=True)`
- **触发条件**：同一**新**用户名的两次真实登录并发到达（E2E 并行套件、慢网络下登录按钮重发）：两个请求都在对方 flush 前通过了 `row is None` 检查 ⇒ 两个 INSERT ⇒ 后到者撞 `uq_users_username`。
- **后果**：一次登录得到 500 `INTERNAL_ERROR`（而非 401/409），重试即成功——症状是「偶发、无法复现的登录失败」，排障方向会被带偏。`StreamService.create`（stream_service.py:269-285）对同一形状是捕了 `IntegrityError` 的，`issue_tokens` 没有。
- **修法**：`try: await session.flush() except IntegrityError: 回滚后重查一次行并继续`（把竞态收敛为「另一请求已建行」）。

### [P3] `StreamListPage` 模块 docstring 仍宣称「引用列本批不渲染」——本批自己的新代码与自己的注释矛盾
- **位置**：`pcs-frontend/src/pages/sim/StreamListPage.tsx:14`（vs 同文件 243-253 行真的渲染了该列）
- **逐字代码行**：`* ⚠️ **「引用 📎×N」列本批不渲染** —— 后端列表响应**不返回**该字段，口径也未定`
- **触发条件**：任何读这个文件头的人（或按 docstring 生成页面摘要的 agent）。
- **后果**：与报告 #11（admin_users docstring 说谎）完全同族的「注释承诺 A、代码做 B」，但这条在本批 diff 的**改动文件内部**——报告只抓到了 admin_users 那处。
- **修法**：删掉或改写 StreamListPage.tsx:14-15 这两行（列已渲染、口径已钉死）。

### [P3] CSV 导出缺「引用」列：屏幕上有、导出里没有
- **位置**：`pcs-frontend/src/pages/sim/StreamListPage.tsx:168`（`exportCsv`）vs 243-253（表格列）
- **逐字代码行**：`const headers = ['名称', '工况', '相态', '温度(°C)', '压力(MPaG)', '质量流量(kg/h)', '状态', '来源'];`
- **触发条件**：用户在物流列表点「导出」。
- **后果**：导出的 CSV 与页面表格列集不一致；SPEC §7.7.1 现在把「引用」列为正式列，而导出静默缺列。轻微但用户可感。
- **修法**：headers 加 `'引用'`，rows 里追加 `s.reference_count ?? 0`（或明确裁决「导出不含引用」并写进 SPEC §7.7.1）。

---

## B. 对报告的挑战

**逐条（只列有异议或需要增补的）：**

- **#6（P2，WS 握手 DB 异常成 500）—— 结论对，严重度与修法错一半。** 事实核对无误：`except PcsError` 之外的确裸穿（ws.py:94-98）。但报告的核心理由「客户端无法区分『被拒』与『后端坏了』」**在现状下就已经不成立**——所有 PcsError 拒绝走 close-before-accept，真实客户端（uvicorn/浏览器）一律看到 HTTP 403 握手失败，1008 和 reason 根本不可达（见上面第 2 条新发现）。所以「补一条 1008 + AUTH_UNAVAILABLE 兜底」修的是**日志与异常处理卫生**（值得修：现在无日志、占池 30s），不是客户端可观测性——建议降为 P3，修法改为「先 accept 再 close」或同时补日志；按报告原修法落地后测试会绿而客户端依旧什么都分不清。
- **M5（补充报告 P2，failedIds 与 result.failed 两份状态漂移）—— 构造出的失败态在真实 UI 不可达，判为（当前）假阳性，建议降 P3。** M5 的故障态要求「弹窗开着（result≠null）且 failedIds 为空」。核对代码：唯一的 `clearFailures()` 调用点是失败清单条里的「清除」按钮（StreamListPage.tsx:345），而弹窗打开时有 mask 挡住整页（antd Modal 默认 mask），点不到它；弹窗关闭时 `batch.result` 已是 null，陈旧清单与提示（都由 `batch.result` 真值 + `batch.result.failed.length > 0` 门控，442/494 行）根本不渲染。两个 state 槽**结构上**确实可以漂移，但今天没有任何点击序列能生产出 M5 描述的用户可见故障。保留为 P3 加固项（「单一真值源」的建议本身对），不应占 P2。补充报告自己也声明「未执行测试、行为断言来自阅读」——这里就是它读漏了 mask。
- **#8（PsvResult 永久 404）—— 结论维持，且比报告说的更实：仓库里存在该数据的活跃消费方。** 报告说「仓库内没有调用方（前端只查 /lineage/streams/...）」。核对 `pcs-backend/app/api/v1/psv.py:247`：`DataLineage.record_type == "PsvResult"` —— PSV 自己的 API **绕过血缘端点直接查同一批行**。也就是说 PsvResult 血缘数据既有写入方（psv_persist.py:444 → finalize_calc_record）也有读取方，唯独新的 fail-closed 守卫把它挡成 404。这不是「没人用的类型」，是「有现役消费路径的类型在另一个入口下可达、在这个入口下永久 404」——支持维持 P2 甚至加固其优先级。
- **#16 —— 无挑战但补一个精确事实**：报告说「今天唯一消费者传的 onDone 是 load()，而 load 自己吞掉了所有异常 ⇒ 潜伏」。核对无误（StreamListPage.tsx:70-83，try/catch/finally 无 rethrow），定性准确。

**其余未挑战的条目（#1 #2 #3 #4 #5 #7 #9 #10 #11 #12 #13）**：我逐条到源码核对了前提（client.ts:24-31、lineage.py 无 require_roles、ws.py sink 无复查、main.py:53 openapi 判据、test_lineage_by_source_ref.py:563 只断言状态码、TODOS.md:2946 写「合并」、admin_users.py:107-108、守卫返回值三处丢弃、auth.py:149 无状态判定），**没有发现结论错误或假阳性**。

---

## 你找到的、报告里没有的（按严重度）

1. **[P2] 删除被下游物流引用的物流 ⇒ FK 违约裸穿成 500**（📎 列的新承诺 × 旧删除门禁的组合失败；`_collect_references` 漏 `streams.upstream_stream_id`，FK 无 ondelete，端点只捕 PcsError）。
2. **[P3] WS 拒绝信道传输层不可见**（close-before-accept ⇒ HTTP 403；1008/reason 只在 TestClient 里存在——守卫“会绿而现实不同形”的又一例，且会污染 #6 的修复方案）。
3. **[P3] 首次登录惰性建行竞态 ⇒ 500**（`issue_tokens` 不捕 IntegrityError，username 唯一约束存在）。
4. **[P3] StreamListPage docstring 与本批自己的代码矛盾**（「引用列本批不渲染」）。
5. **[P3] CSV 导出缺「引用」列**（屏幕/导出不一致）。

---

## 一句总体判断

**「Ready with fixes」成立，但修复队列不完整**：报告的 P1（#1）与三个决策项定性都经得起对抗核对，没有需要推翻的结论；但它漏了一条应当排进 apply 队列的 P2（删除被引用物流 ⇒ 500 —— 本批招牌功能 📎 列直接把用户引向这条路径），且 #6 的修法若按报告原样落地会修在一个客户端根本观测不到的信道上。修完 #1、补上删除门禁的 409、并把 M5 从 P2 撤下之后，这个 verdict 才名副其实。
