# Cerebrum

> OpenWolf 学习记忆。**只放「下次还会犯」的规则与速查表**。
>
> **本文件的目标体积：≤ 24 000 token**（2026-11-12 瘦身前是 **34 100** ⇒ 现在 **23 218**）。
> ⚠️ **历史条款**：本文件 2026-11-12 之前写着「≤2000 token」而**实际 34k** ⇒
> 契约是假的 ⇒ 现在改成**可核对的**（上面那个数 + 下面的清退规则）。
>
> ⚠️ **为什么目标不是 2k**：剩下的 ≈20k 是 **97 条仍在生效的 Do-Not-Repeat**
> （每条带日期 + bug/评审出处 + 判据）⇒ 再压小只能**逐条改写成一句话**
> ⇒ 那会把**证据细节**压掉（判据与反例正是这条的价值）⇒ 那是**另一档方案**，
> 本轮**没做**。⇒ 真正的成本不在体积，在**通读** ⇒ 所以下面有**索引表**：
> **先查索引 → 只读命中的那一条**（≈200~400 tok）⇒ 不要通读。
>
> **清退规则（防止再次只进不出）**：
> ① 新条目进来 ⇒ 同一主题里**最旧**的一条要么被它**取代**、要么**移进归档**；
> ② 一个批次的**决策叙事**在批次闭环时**整段进归档**，不在本文件留正文；
> ③ 每季度（或每 5 个批次）核对一次体积 ⇒ 超 8k 就再清一轮。
>
> **归档**：`.wolf/cerebrum.archive.md`（已闭环批次的决策叙事 + 已被
> `docs/solutions/` 覆盖的旧条目）⇒ 要追溯就 `grep` 那里，**不要**往本文件回填。
> **更早的全文**：本文件的 git 历史（`git log -p .wolf/cerebrum.md`）。

## User Preferences

- 全程中文；术语中文为主、枚举/代码标识用英文。
- 用户审批风格：每决议指出「卡线/模糊」+ 给建议；接到反馈时**直接采纳可执行建议 + task note 记录边界**，不反复询问。
- 简单确认（"继续"）= 驱动下一 task，不重新讨论已完成项。
- ADR 编号按**文件序列**为准（用户口头编号可能错位）；映射差异回复中一句话说明即可。

## 索引 —— 按主题查（**先查这里，别通读**）

| 主题 | 条目数 | 关键词（grep 这些词就能定位） |
|---|---|---|
| **A 契约 · 权限 · 守卫** | 17 | 同形 / 枚举 / 守卫 / fail-closed / actor 层 / 覆盖 / 角色 / 归属 / 注册表 / 早于 / 鉴权 / 不可逆 |
| **B 数据 · 迁移 · 事务** | 19 | savepoint / get-or-create / 加锁 / FOR UPDATE / populate_existing / 回滚 / expire / 迁移 / FK / 唯一约束 / 布尔 / 硬上限 / project_id |
| **C 测试 · 守门 · 假绿** | 23 | 假绿 / 变异 / 观测 / 正向对照 / strict_client / SQLite / 注释骗人 / docstring / 守卫 / 断言 |
| **D 前端 · 契约派生 · 可空性** | 16 | 词表 / 契约派生 / mock / 可空性 / rowKey / 选中集 / 权威 / 类型检查 / 手写类型 / or 兜底 |
| **E 工具 · 命令 · 浏览器** | 6 (+3 延伸) | 退出码 / 管道 / CI 步骤 / 基线 / page.goto / @eN / 空转 / 门禁 |
| **F 流程 · 断言 · 协作** | 13 | 断言前先实测 / grep 既存 / 口径 / 评审结论 / 落点 / 逃生口 / 反向变更 / 真实可判定 |
| **G 领域 · 技术速查** | 10 (+1 指针) | Alias / chemicals / IAPWS / PropertyAutoCompleter / JSONB / mixin 必填 / API 520 / GB/T 12241 / Two-Point Omega / SIM 范围 |

⚠️ **每条都带日期与出处**（bug 号 / 评审号 / 裁决号）⇒ 判它是否仍适用时
**先看出处**（`docs/solutions/`、`TODOS.md`、git log）。

## Do-Not-Repeat（按主题）

### A 契约 · 权限 · 守卫

#### 一次性守卫 + 实时配置回查 = **纸门**（2026-10-31 · P9B-2R #1）

「检查一次、之后每次回查可变配置」**等价于配置可以事后改掉规则** ⇒ 守卫形同虚设。

⇒ 凡守卫判据源自**可变配置**（矩阵 / 模板 / 角色表）⇒ 必须在**动作发起时**
**冻结判据快照**进业务行（记录侧 `approval_chain_snapshot` 与交付物侧
`_steps_for_version` **同构**）。
⇒ 配套：前端同类信息**不得**用跨挂载缓存（chainCache 教训）。
⇒ 全文见 `docs/solutions/security-issues/midflight-config-rebind-defeeds-one-shot-guards.md`。


#### 「无权」与「不存在」必须**逐字同形**，否则可枚举 UUID（2026-11-09 · P9B-4 紧急批次）

**404 ≠ 403，而且 404 也要「同形」。** 跨项目访问若返回**与「不存在」不同**的
信封（不同的 `code` 或 `message`），攻击者就能靠响应差异**枚举出某个 UUID
是否存在**。

⚠️ **仓里现成的 `check_record_access_or_404` 恰好踩这个坑**：它无权时抛
`HTTPException(404, "Project not found: <id>")` ⇒ 全局 handler 渲染成
`code="HTTP_404"`；而「物流不存在」是 `code="SIM_STREAM_NOT_FOUND"` ⇒
**两个 404 的信封完全不同** ⇒ 可枚举。

⇒ 本仓的做法：service 层加 `has_project_access()`（**只回 bool**、不抛异常、
含 SYSTEM_ADMIN bypass、口径与 `check_project_access_or_404` 一致）⇒
**由调用方决定抛什么** ⇒ 调用方抛**与「不存在」逐字相同**的 `PcsError`。
⇒ 同形性不靠「两处写一样的话」，靠**同一个 helper**。

⚠️ **同形测试必须用同一个 uuid 测两次**（先「不存在」、再「存在但跨项目」）：
消息里本来就带着**请求的 id** ⇒ 拿两个**不同**的 uuid 比**测不出**同形性。

#### 守卫要判账号状态：光在**登录时**拦不够（2026-11-11 · P9B-4）

「停用」只在**登录时**拦 ⇒ 在手 token 在过期前（30 分钟）**完全不受影响**
⇒ 停用形同虚设。⇒ 每请求查一次 `users.status`（实测 P95 **0.297ms**）
⇒ 停用**立即生效**。

#### 账号有效性判在 **actor 层**，不在守卫层（2026-11-11 · P9B-4）

守卫层 join + API 层 bypass = **判定分裂两处** ⇒ 将来加第三条 bypass /
改 status 词表都会漏 ⇒ **一处判定**（`current_actor`）才全局生效
（含 SYSTEM_ADMIN bypass）。

#### 无状态 token 的吊销窗口要缩，就把它**变有状态**（2026-11-11 · P9B-4）

「30 分钟窗口」不再成立 ⇒ 变成「**两道闸**：token_version（refresh 时校验）
+ users.status（每请求校验）」⇒ ⚠️ **改行为要同步改 ADR**（代码与 ADR
**同一个 commit**）⇒ 否则文档在撒谎。

#### 角色的真值是**覆盖**，不是**合并**（2026-11-11 · P9B-4 整批评审）

`users.roles` 的真值是**当前身份** ⇒ AD 同步（`ad_sync._apply`）也是**覆盖**
⇒ 真实登录**必须同口径覆盖** ⇒ 只增不减会让「**角色降级**」永不生效 ⇒
旧角色一直留着 ⇒ 按 `users.roles` 圈人的通知逻辑会**继续找**已降级的人
（「待办里有、点进去说你不是」比没有待办更坏）。
⚠️ 「seed 行可能已带别的角色」这个理由**不成立**（`ensure_user_row` 建行就是
`roles=[]` ⇒ 非空 roles 只来自上一次真实登录/AD 同步 ⇒ 那就是权威值）。

#### 创建时的**归属**也要校验（2026-11-11 · P9B-4）

守卫保护「**已有**记录」，但「**新建时挂到别处**」是另一个洞 ⇒
`create_stream` 的 `workspace_id` 此前取自**请求体**且**从不校验归属**
⇒ 补：一律用 `project.workspace_id`（请求体的被忽略 + 标 deprecated）。

#### 守卫注册的**键 = 写入方实际写的值**（2026-11-11 · P9B-4）

键口径混用 ⇒ 守卫加在一个**永远不匹配**的查询上 ⇒ 守卫形同虚设（而且**全绿**）。
写入方写 `record.__class__.__name__` ⇒ 注册表的键**必须**是**类名**
⇒ `RECORD_TYPE_REGISTRY` 的 5 个键不是类名 ⇒ **抄不得**。

#### 注册表**别手写第二份**（2026-11-11 · P9B-4）

从 `RECORD_TYPE_REGISTRY` **派生** + `inspect(model).primary_key[0].name` 取 pk
⇒ 新增类型**自动**被守卫 ⇒ 不靠「开发者记得补」。
⚠️ 派生时要放**服务层**（api 层 import 会**循环导入**）。

#### 未知类型要 **fail-closed**（2026-11-11 · P9B-4）

靠「开发者记得补」是**纪律**，不是**结构** ⇒ 未登记的 `record_type` ⇒
与「记录不存在」**逐字同形**的 404 ⇒ 不可枚举。
⚠️ 此前「未登记 ⇒ 跳过」⇒ `/upstream` 返 200+[] ⇒ **可枚举信号**。

#### 守卫必须**早于**一切业务门禁（2026-11-09 · P9B-4 紧急批次）

**顺序错了 ⇒ 越权用户拿到的是「业务细节」而不是「无权」。**
`POST /streams/{id}/submit` 原来先跑组成合计校验（422 + **组成百分比**）
再转移 ⇒ 跨项目用户能拿到「该物流组成合计 87.3%」⇒ **一次响应同时泄露
「存在」与「数据」**。

⇒ 守卫是**最外层**的检查：在**载荷校验**之前、在**业务门禁**之前。
（同 bug-2039：守卫写在写入之后 ⇒ 响应是 404 但行已经被改了。）

#### 「不存在」也必须走**同一个** 404，别让端点各自兜底（2026-11-10 · ce-code-review P1 #1）

守卫在「记录不存在」时**静默 return** ⇒ 端点**各有各的兜底** ⇒
`/graph`、`/downstream` 恰好抛 404（同形），`/upstream` 却返回 **200 `[]`**
⇒ 攻击者据此区分「这个 UUID 存在但不是我的」与「这个 UUID 根本不存在」
⇒ **枚举向量**（本批守卫要关的正是它）。

⇒ **守卫自己**抛那个 404，别指望端点碰巧同形。
⚠️ 同形断言必须**覆盖端点族的所有后缀**（只测 `/graph` ⇒ `/upstream` 漏网）。

#### 过滤条件要**少依赖一个维度** —— 冗余谓词 = 未来的漂移点（2026-11-10 · ce-code-review P1 #2）

端点按 `action == "RECORD_TRANSITION"` 过滤，而状态机给 PASS/REJECT 写的是
`APPROVAL_STEP_PASSED` / `APPROVAL_STEP_REJECTED` ⇒ **校对通过/驳回两行被静默吞掉**
（200 + 部分列表，**不报错**）。

⇒ 那个 `action` 谓词**没有信息量**（`detail_json.transition` 白名单**已经精确**
选中那几条）⇒ 冗余谓词 = **状态机改词表时把端点打瞎的漂移点** ⇒ **删掉**。

⚠️ **推论（更一般）**：**手抄的枚举字面量**（`"RECORD_TRANSITION"`、
`"PASS_CHECK"` …）是**第二份真相源** ⇒ 从**枚举/映射派生**。
⚠️ **推论（测试侧）**：**fixture 必须从真正的写入方派生** ⇒ 手抄一个「看起来像」的
形状 ⇒ 造出**生产中不存在的行** ⇒ 端点口径漂移时测试**照样绿**
（= `docs/solutions/testing-issues/guard-test-fooled-by-lying-comment.md` 那条）。

#### 身份**不许静默替换**（2026-11-10 · ce-code-review P2 #10）

「按 `user_id` 找不到 ⇒ 按 `username` 兜底」返回的那行可能 `user_id` 与请求方
**完全不同** ⇒ 授权落在**请求方的 token 根本不认**的身份上 ⇒
创建者访问不到自己刚建的项目 + **另一个账号**被授了权。

⇒ **只认 `user_id`**；username 被别人占着 ⇒ **显式报错**（409，指名道姓）
⇒ 绝不静默返回一个「不是请求方」的身份。

#### 要签署的东西**必须有版本行**（2026-10-26，P9A-DLV-011：bug-2055 / bug-2058）

**「绑了矩阵」≠「矩阵生效」。** 变更单绑了 3 级矩阵，却**没有版本行** ⇒
`sign_step` 要 `version_id` ⇒ 它**永远进不了签署流程** ⇒ 审批只能走一个
「不查矩阵、不查角色」的直批方法 ⇒ **矩阵是装饰品**，而且没人发现
（测试全绿，因为矩阵确实被绑上了）。

⇒ **凡是要走签署流程的对象（交付物 / 变更单 / 任何要「谁签、谁先签」的东西），
必须有 `DeliverableVersion` 行**；审批入口必须是**签署流程的终点**
（`sign_step` 最后一步），而不是另一个能绕过矩阵的端点。
⇒ 自查：**「谁该签这一步」这个问题的答案在哪一行里？** 找不到 ⇒ 矩阵没生效。

#### 鉴权必须在**写之前**，且断言「响应 404」不等于「没被改」（2026-10-20，bug-2039）

**守卫的位置比守卫的存在更隐蔽。** 实测（bug-2039）：`filtration`/`flare`/`psychro`
三个 PATCH 的顺序是 `require_roles → 保存 → check_project_access_or_404` ——
鉴权写在保存**之后**，而 service 取记录时**不带 project_id** ⇒ 保存那一步零隔离
⇒ 无权用户改到**别人项目**的行，鉴权只把**响应**变成 404。`cool_tower` DELETE
更糟：**根本没有守卫**（service 传 `project_id=None`）。

⇒ **新写端点时**：任何 `check_project_access_or_404` / `check_record_access_or_404`
必须在第一次 `await session.commit()`（或任何 setattr 落库）**之前**。
⇒ **顺序不能只看本文件**：守卫正确但**排在** 409/404 之后 ⇒ 它仍然漏。
⇒ **写守卫测试时**：断言**响应状态码不够** —— 旧顺序下响应**也是** 404 ⇒
那样的测试在新代码上照样绿（假绿）。关键断言是**「行没变」**
（`db_session.refresh(row)` 后比对业务字段）。
⇒ 用例里的并发基线（`expected_hash`）要取**有效值**，否则请求在 409 就短路了，
根本走不到「保存」那一步 ⇒ 又是一条测不到写入的假绿。
⇒ 新写路由测试前先确认 **URL 前缀与 router 的 `prefix` 一致**（本轮写错过，
404 发生在**路由层** ⇒ 断言全绿却什么都没测）。

#### Auth hardening 模式（2026-09-18）

- **JWT decode 必传 `options={"require": [...]}`**：默认 PyJWT 不强制必填 claim。
  必传 `["exp", "iat", "sub"]` 至少这三项（与 create_*_token 实际写入对齐）。
  `MissingRequiredClaimError` 是 `PyJWTError` 子类，已被现有 `except jwt.PyJWTError` 自动捕获。
- **Refresh token 必须 JTI + rotation**：每次 `create_refresh_token` 写 `jti=uuid4()`；
  进程内 `_REVOKED_JTIS: set[str]` in-memory 即可，redis 单节点场景避免额外依赖。
  refresh 端点：检查 `is_jti_revoked` → 撤销旧 JTI → 返回新 access + 新 refresh。
  `RefreshResponse` 必须含 `refresh_token`，前端无需另存。
- **Logout 真正生效需要接 refresh_token**：旧实现 `return None` 是 no-op，
  与 refresh 不轮换配套下 logout 名存实亡。
  `LogoutRequest` 接收可选 `refresh_token` 字段，无 body / 伪造 / access 三场景
  全部幂等 204（防侧信道：不通过响应区分 token 状态）。
- **LDAP DN 必须 RFC 4514 §2.4 转义**：`_sanitize_dn_component(value)` 处理
  `\` `"` `#` `+` `,` `;` `<` `=` `>` 和 NUL。
  NUL 特殊：先跑单字符转表（NUL 不在表中保持原样），再单独 `replace("\x00", "\\00")`，
  否则 pre-replace 后反斜杠会被转义二次翻倍成 `\\\\00`。
  测试覆盖：parametrize 10 字符 + 集成（username=`alice,ou=admin` 注入 RDN 边界）。

#### 事件必须带前值快照（不可逆操作的第一原则）

- 任何会**覆盖**既有值的操作，payload 必须同时带 `before` 与 `after`。
  值一旦被覆盖，旧值就**永久丢失**，后续无法回溯补齐。
- 写 `emit_event('x_replaces_y', diff=...)` 这类只传 diff 的接口 =
  给未来埋一颗不可撤销的地雷。**多一个 dict key 的边际成本近零**。
- 幂等键（`event_id`）在反向事件里应**复用原事件 id** → 天然幂等，
  不需要另设计反向去重机制。
- 缺 `before` 的历史事件应**明确报"不可逆"**，不静默跳过 ——
  假装回滚成功比回滚失败更危险。

### B 数据 · 迁移 · 事务

#### 聚合要**有上限** + **最新的在前**（2026-11-11 · P9B-4 整批评审）

`data_lineage` **只增不删**（每次重算一行）⇒ 「查所有以该物流为源的行」**无界增长**
⇒ 端点的 `max_depth`（1..50）在「没有遍历」的入口下要**当条数上限用** ⇒
超限时截掉**最旧**的（⇒ 排序用 `occurred_at DESC` ⇒ 用户先看到最近的产出）。
⚠️ 排序要带**兜底键**（同一时刻的多行 ⇒ 顺序确定 ⇒ 可重复）。

#### 访问检查要**早于加锁**，且兜底**必须回滚**（2026-11-10 · ce-code-review P1 #3）

守卫（一条 DB 查询）挂在 `SELECT ... FOR UPDATE` **之后** ⇒ 它一抛错 ⇒
异常冒到批次兜底 ⇒ 兜底只返回失败项而**没人回滚** ⇒ 事务 aborted ⇒
**后面每一条都失败**（D2「一条失败不影响其他」被打破）+ 行锁一直持有；
且守卫拒绝**之前**已经锁住了**别人项目**的行（锁序侧信道）。

⇒ **非加锁**读出归属 → 访问检查 → 再加锁做正事；且**任何**兜底都要
`await db.rollback()`（不只是「转移失败」那条路径）。
⚠️ **测试要造真的 DB 级失败**（flush 失败）—— 抛 Python 异常**不会**让事务 abort
⇒ 那种测试**旧代码也绿** = 假绿。

#### get-or-create（SELECT 见空 → INSERT）必须**在 savepoint 里**（2026-11-10 · ce-code-review P2 #11）

两个并发请求都「SELECT-见空」⇒ 都 INSERT ⇒ 输家撞唯一约束。
⚠️ **savepoint 之外的 INSERT 撞约束会中止整个事务** ⇒ 调用方（`POST /projects`）
的项目 INSERT 与本插入同事务 ⇒ **整体回滚** ⇒ 偶发 500 + 项目建不出来。

⇒ 配方（`docs/solutions/database-issues/get-or-create-default-row-race-savepoint-reread.md`）：
`db.add()` 移进 `async with db.begin_nested():` **之内**；撞 `IntegrityError`
⇒ **重读赢家并原样返回**（**只读不写** —— 绝不把赢家的列改回自己的版本）。

#### 布尔**不是**数字（2026-11-04，bug-2137）

`int(True) == 1`（bool 是 int 的子类）⇒ 系统参数里存了 `true` ⇒ 上限**静默变成 1**
⇒ 批量提交 2 条被 422 拒，而参数页**显示「true」** ⇒ 用户看不懂。

⚠️ **不能靠 `int()` 抛异常兜** —— `int(True)` **不抛** ⇒ `except (TypeError,
ValueError)` 完全接不住 ⇒ 必须**在 `int()` 之前**先 `isinstance(raw, bool)`
显式排除。

⇒ 自查：**这个值可能来自 JSONB 吗？**（系统参数、JSON 字段、API 载荷）
⇒ 可能是 ⇒ **所有 `int()` / `float()` 之前先排 bool**。
⇒ 同族：字符串 `"100"` 与数字 `100` 混在 JSONB 里 ⇒ 一律 `isinstance` 收窄，
不要靠转换函数的异常。

#### 列表型入参要有**硬上限**（2026-11-04，bug-2140）

上限若是**动态**的（系统参数，管理员可改）⇒ 请求体本身**没有**上界 ⇒
服务端先把整个列表**反序列化完**再比上限 ⇒ **校验发生在成本之后**。
⇒ 请求体层加 `Field(max_length=…)` ⇒ Pydantic **逐个追加时**就停 ⇒
连反序列化都省了；服务端的动态上限与硬上限**取小**。

#### 加锁读**之前**读过同一实体 ⇒ 行锁读到**过期**状态（2026-11-03，P9B-3 评审 C-1 / bug-2122）

**「SELECT ... FOR UPDATE 发了」≠「读到的是锁住的那一行」。** SQLAlchemy 的
查询**默认不覆盖** session 里已加载实体的属性（`populate_existing=False`）⇒
只要**在加锁读之前**碰过同一个 PK（哪怕只是 `db.get` 读一个字段做校验），
实体就进了 identity map ⇒ 随后的加锁 select **不刷新**它 ⇒ 并发转移读到
**过期状态** ⇒ 转移被放行 ⇒ **行锁形同虚设**（实测：并发两次提交校对
**两次都 200**）。

⚠️ 这是**加锁读之后加的前置校验**引入的回归（加锁 select 是首次加载时
一切正常）⇒ 「加了个只读校验」看着无害。

⇒ **凡是用 `with_for_update()` 的 select，都必须加
`.execution_options(populate_existing=True)`** —— 加锁读的**目的**就是读
「锁住的那一行」⇒ 那行**永远赢**。
⇒ 自查：**这次加锁之前，这个 session 碰过这个 PK 吗？** 碰过 ⇒ 必须
`populate_existing`。
⇒ 回归测试可**不依赖真并发**：「同 session 预读 + 另一个事务改库」复现**同一
形态**的陈旧读（成因是 identity map，与方言无关 ⇒ SQLite 也能测）。

#### 关联走**表**，不走字符串（2026-10-26，P9A-DLV-011：bug-2057）

变更单与记录的关联只存在 `deliverables.scope_value` 的
`"CHANGE_NOTICE:{表名}:{id}"` 字符串里 ⇒ 「关掉这条记录」只能解析字符串 ⇒
格式一变就静默失效。

⇒ **多态关联（对象 ↔ 对象）要一张专门的关联表**（ADR-0008 已经指明
`deliverable_record_bindings` 替代 `change_notice_record_bindings`，本仓却
只留了字符串）。⇒ 字符串**只能**当「scope / 展示」用，不能当**关联**用；
两者并存时用**守卫测试**钉住一致。

#### 迁移里不要用 ORM 实体查整表（2026-10-21，bug-2041）

`select(ORM实体)` 会带上 **ORM 声明的全部列** ⇒ **ORM 后来加的列**会让**早就写好
的迁移**在**全新库**上炸（`UndefinedColumn`）—— 而 dev 库在迁移写好之前就应用过
它 ⇒ **天然免疫** ⇒ 本地全绿、CI（全新库）全红。
⇒ 迁移里要读表 ⇒ 按**此刻 DB 实际存在的列**裁剪 SELECT（`defer` 缺列），
**不要**写死「排除某个列」（下一个迁移再加一列就原地复发）。
⇒ ⚠️ CI 的 `api-drift` job 是**全新库** ⇒ 它是这类漂移的**唯一探测器** ⇒
改迁移后**必须**在全新库上验（本机无建库权限时用**隔离 schema**：
`options=-csearch_path=<schema>` + `alembic upgrade head`）。

#### 数据库/迁移

- 真库测试第二个起需 `_reset_async_engine` autouse fixture（单例引擎跨 event loop 炸）。
- 外科切割已提交代码后必复跑依赖测试；commit 自持性靠 worktree 验证。
- **写 migration 前必跑 SQLAlchemy reflection** 校核实际 schema（`Model.__table__.columns/constraints` 是 ground truth）。
- ORM `__table_args__` 必须含 `CheckConstraint` 同步 DB 约束（跨 dialect 不丢）。
- Pydantic schema 字段重复（Create+Update）→ Edit fail "Found 2 matches"，先 `grep -n` 再附上下文 unique。
- **单测不读迁移，别把 `alembic upgrade head` 当测试前置**（2026-10-06 实测证伪）：`conftest.db_engine` 建 `sqlite+aiosqlite:///:memory:` 并用 `SA_Base.metadata.create_all` 从 ORM 建表，`.env` 指向 `pcs`、无 `pcs_test`、无 `.env.test`。CLAUDE.md「测试前检查」原「先对 pcs_test 跑 upgrade head」一条已于同日改写为三段式。
- **⚠️ 漂移盲区：缺表会红（可见），漂移会绿（不可见）**。迁移改 schema 而 ORM 未跟随时单测全绿、真库炸，无自动化能抓（见 Key Learnings `bug-137`）。改 `alembic/versions/*` 后必跑 `uv run alembic check` 并手动核对 ORM 列。**该守门有三个会让人误判的读法，见 CLAUDE.md「测试前检查」**：① DB revision 落后 code head 时它直接拒跑，那是检查失败不是通过；② 退出码 **255** 不是 1（`check_migration_idempotency.py` 才用 1）；③ **2026-10-07 起 exit 0 是真实状态**（43 条已全清），所以 exit 255 一律是真缺陷，不必再对「已裁决残留」做豁免。
- **`alembic check` 的 `remove_constraint` 字面意思与正确处置恰好相反**（bug-147，43 条里 39 条）。它读作「DB 多余、ORM 要删」，实测那 39 条全是「**DB 有安全网、ORM 漏声明**」—— 照字面删会把 DB 保护删掉。补 ORM `__table_args__` 即可，零迁移成本。
- **alembic 按**名字**匹配 CHECK 约束，不比对表达式**（bug-147 实测）。ORM 侧可以写可读表达式，不必抄 PG 的 cast 语法 —— 这解锁了全部 28 条 CHECK 的补齐。
- **ORM 里写 `ForeignKey(..., use_alter=True)` 不会自己生成迁移**（bug-146）。`use_alter` 的语义是「由一条 `ALTER TABLE ADD CONSTRAINT` 迁移单独创建」。写了这行就必须有人补那条迁移，否则 DB 上压根没这个约束 —— `projects` 曾整表零外键。
- **⚠️ 断言内存对象的假 DB 测试，结构上观察不到 DB 层约束**（bug-145，2026-10-07 用户纠正）。`_FakeSession` / `_FakeDeliverable` + `assert db.added` 只证明对象被构造出来，**NOT NULL / FK / CHECK 一个都测不到**。写「这个 service 能落库」的测试必须打真 session（内存 SQLite 也行）—— 那 5 个测试把 `create_change_notice` 写死 `matrix_id=None` 的 NOT NULL 违例全放过了。
- **判某个服务/组件「有没有测试」不要用顶层 `ls tests/`** —— 子目录（`tests/services/`、`tests/models/`）里可能有。bug-145 原记录就因为这个把「有 5 个测试」误记成「无任何测试」。

- **手写 `op.create_table` 必查两件事**（bug-143/144，均为**静默**失败）：
  ① **mixin 继承的列有没有漏** —— `UserProject(TimestampMixin, Base)` 的 `created_by` 等三列
  在类体里一个都看不到，按类体抄写必然漏（那次漏 `created_by`，真库 INSERT 报 `UndefinedColumn`）；
  注释里写「Timestamps from TimestampMixin」不算核对，它只列出作者注意到的列。
  ② **外键是不是写成了裸 `sa.ForeignKey(...)` 位置参数** —— `op.create_table(*args)` 只收
  `Column`/`Constraint`，裸 `ForeignKey` 被**静默丢弃、不报错**。正确写法是嵌进列：
  `sa.Column("user_id", UUID(...), sa.ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False)`。
  那次 4 条 FK 一条没建出来，而 `user_projects` 是 BLOCKER-3 IDOR 守卫读的表。
  约束名另须从 `NAMING_CONVENTION` 推导，名字对不上 `alembic check` 照样报漂移。
- **PG 写 FK 用 `op.create_foreign_key`，别手写 `REFERENCES users.user_id`**（2026-10-07 实测）：
  未加引号的两段式报 `InvalidSchemaName: schema "users" does not exist` —— 表明明存在，错误
  信息却指向 schema；函数式 `REFERENCES users(user_id)` 与加引号式均正常。
  （该结论在开发库 PG 18.6 复现，compose 声明的是 16-alpine，跨版本未验。）
- **判「某组件/能力是否已交付」不能只搜计划里的那个文件名**：计划名与最终组件名不一致是常态（`LineagePanel`→`LineageGraph`、`ChangeNotification`→`NotificationCenter` 的「变更」分类）。**按 SPEC 章节号找，再落到实现**（2026-10-07 只搜文件名，把已交付的 NotificationCenter 误判成未做，差点重写一个重复组件）。
- **别拿「迁移里加了 guard」当保护已生效**：约束类 op 的存在性标志传进去不报错却被 `**kw`
  吞掉（`create_unique_constraint`/`create_check_constraint` 在 alembic 1.19.1 无该形参），比不加
  更危险。迁移期结构检查统一放 `scripts/check_migration_idempotency.py` —— 它已用 AST 遍历
  `ast.Call` 且对 `op.create_table` 特判，加新检查边际成本最低。

#### 数据完整性：缺数据就留空，不编造

- **来源表里没有的实测/设计值一律留空，不推算、不套标准值、不取邻近行**（2026-10-06，蜡油加氢
  真实数据验收）。`LOW_TEMP_ITEMS` 判空是因为 `机泵选型` 与工艺 XLS 里都无低温余热项，
  不是因为「不重要」。缺值走既有 UNVERDICTABLE / 需重算 档，不走「填个合理默认」。
- **XLS 里的自相矛盾/坏值当发现报，不静默修正**：氮气 MJ 列与 kg标油/m³ 口径打架、
  数量列前后不一致、`#DIV/0!` 单元格 —— 一律登记为待工艺室确认，由人裁决，不代填。
  设备级坏值（如 132-P-105A/B/C/D 电机与轴功相差 111.7 倍）进 `PUMP_DESIGN_EXCLUDED`
  显式排除并记原因，不删数据也不参与回填。

#### 折标系数改动前必跑一致性审计（bug-135/136, 2026-10-05）

- **跑** `uv run python scripts/p7_open_016_config_conformance_audit.py` ——
  逐行对 GB 30251-2024 附录A 表A.1（26 行 PCS 系数 vs 标准 34 行），别凭印象说"一致"。
  该脚本直接 import T0 seed 的 `R1_SIGNED_ENERGY_CONVERSION`，不复制数值。
- **已查出 2 处不一致**（当时 PCS 未自查）：
  除盐水/凝汽机凝结水 1.04 vs 标准 1.0（+4%，两份标准全文均无 1.04，来源不明）；
  LOW_TEMP_HEAT 硬编码 0.0341 vs 标准 0.012（+184%），且 0.0341 是 GB/T 2589
  表A.2「热力(当量值) 0.03412 **kgce/MJ**」，把 kg标煤/MJ 当 kg标油/MJ 用，量纲错。
- **CONFIG 查表静默 fallback 是惯犯**：`_compute_totals` 一律
  `factors.get(X, 硬编码默认值)` —— CONFIG 缺行时不报错，直接用错值。
  新增能源类别时**必须同时加 CONFIG 行**，否则永远吃 fallback。
- **不擅自改折标系数**：发现不一致先记账 + 审计常态化检出，工艺室裁决后再改
  （同「不得为了让验收变绿而修改 PCS 折标系数」）。

#### ORM 声明 ≠ 真实库 schema（bug-137, 2026-10-05）

- **测试全绿不能证明 schema 对**。测试用 in-memory SQLite
  `Base.metadata.create_all` —— **从 ORM 模型建表**，所以 ORM 声明了但
  没有任何 migration 创建的列，测试照样全绿。真实库却查不到。
  `config_energy_conversion_factors` 就是这么烂了：4 个 R1 分类列从未迁移 +
  R0 的 `UNIQUE(energy_type)` 从没 drop → 真实库 0 行，26 行 R1 机制只在测试里成立。
- **ORM `__table_args__` 改了 ≠ 老库会跟着变**。改 UniqueConstraint/Index/列
  必须**同时写 alembic migration**。查历史：`p7_open_010_r1_classification_fields.py`
  名字像是做分类字段迁移的，实际只碰了另外 3 张表 —— 名字骗人，要看内容。
- **改 schema 后必查真实库**：查一个真实 DB 的 `information_schema.columns` +
  `alembic_version`，别信测试。**注**（2026-10-06 更正）：原文此处要求「pcs_test 灌完
  先 upgrade head 再跑 schema 敏感测试」——已证伪，本仓库无 `pcs_test`，单测走内存
  SQLite 不读迁移，详见 `## Do-Not-Repeat` 的「数据库/迁移」节与 CLAUDE.md「测试前检查」。
- **PG 的 UNIQUE 遇 NULL 失效**：`UNIQUE(a, b, c)` 里 b/c 为 NULL 时，
  NULL 互不相等 → 重复行照插。`ON CONFLICT DO NOTHING`（不带 conflict target）
  也因此不生效。实测插出 7 行重复。要真约束需 PG 15+ `NULLS NOT DISTINCT`
  （本机 18.6 支持）或 COALESCE 表达式索引。
- **同名 energy_type 撞车**：用 `toe_factor` 之类数值列当行匹配键不安全 ——
  除盐水与凝汽机凝结水都是 1.0，我据此 UPDATE 时把一行改错了。按 id 修。

#### Do-Not-Repeat: 主键列名不能靠猜（2026-10-26，bug-2081）

`getattr(record, "record_id", None)` 只在**部分表**成立（`relief_results` 叫
`relief_id`、`streams` 叫 `stream_id`…）⇒ 在别的表上**恒为 None** ⇒ 查询静默
返回空 ⇒ 后续逻辑**空转**而不报错。

⇒ **按 mapper 取**（`inspect(cls).primary_key[0]`），或**由调用方传入**
（它就是 `db.get(table, pk)` 用的那个主键）。
⚠️ 「静默返回空 ⇒ 后续空转」比「直接报错」更贵：它把 bug 伪装成「数据本来就没有」。

#### Do-Not-Repeat: 子类的默认属性要用 `type(self).*`（2026-10-26，bug-2079）

让 `PcsError` 的 service 变体**继承** core 变体时，若在 `__init__` 里写死
`code="PCS_ERROR"` / `status=500`，**所有子类**（`MassIterationNotConvergedError`
等 100+ 个）都退化成父类的值 ⇒ 实测 **124 个既有用例同时红**。

⇒ 子类的默认取 **`type(self).code` / `type(self).status`**（类属性可被子类覆盖）。

#### Do-Not-Repeat: 从审计流水反推「执行者」要取**最后**一条（2026-11-02，P9B-2F）

「某条记录**当前这一轮**的提交人是谁」—— 从 `audit_logs` 反推时，流水里
**可能有多条**同类事件（「送审 → 驳回 → 再送审」⇒ 两条 `SUBMIT_FOR_CHECK`）
⇒ **当前轮次 = 最后一条**。

⚠️ 取第一条 ⇒ 拿**上一轮**的人当判据 ⇒ **本轮的人就能自己做自己的审批人**
⇒ 而这类「用事件流水反推当前状态」的逻辑**只在异常/兼容路径上出现**
（正常路径有更可靠的字段，比如快照里的 `submitted_by`）⇒ **正常路径测不到
⇒ 只有专门构造那条路径才暴露**。

⇒ 反推类逻辑一律：**按时间排序 → 取最后一条**，并**显式**写一条测试
（构造多轮 + 把时间戳**显式**设成不同值 ⇒ 测试确定性不依赖时钟分辨率）。
⚠️ SQLite 的 `CURRENT_TIMESTAMP` 只到**秒** ⇒ 并列时按返回顺序取最后
（等价于插入顺序）；PG 的 `func.now()` 是事务时间戳（微秒）⇒ 不会并列。

#### Do-Not-Repeat: 「失败即回滚」不只在**异常**路径上 —— flush 之后、commit 之前的失败会**污染下一条**（2026-11-03，P9B-3b）

**形状**：一批操作里每条各自 commit（⇒ 部分成功语义）⇒
某条在 **flush 之后、commit 之前**失败（最现实：**审计写失败**）⇒
那条的状态**已经写进当前事务**（未提交）⇒
若那条的失败路径**只把异常转成失败项、没人回滚** ⇒
**下一条处理成功时它的 `db.commit()` 会把上一条的脏写一起提交掉**
⇒ **响应说失败、DB 里却是成功态**（且没有审计 —— 审计正是失败的原因）。

⇒ **失败路径必须显式 `await db.rollback()`**（每条自成事务 ⇒ 只回滚这条）。
⇒ **并且**：commit 之后还有失败点（如 `db.refresh`）⇒ 数据**已经落库**
⇒ 回滚后要**读回真实状态**再决定报成功还是报失败 ⇒
「报失败」和「报成功」都可能撒谎，**读回真实状态**才不撒谎。
⚠️ 判据要可靠：只有当「本次转移前**不是**目标态」时，「现在**是**目标态」
才**必然**意味着这次转移真的提交了（幂等命中要在此之前就返回）。

⚠️ **写这类测试时**：被测实体在回滚后**已过期** ⇒ 读它的属性会触发
**同步 lazy-load** ⇒ `MissingGreenlet` ⇒ ①先把 id 存下来，
②断言用**直接 SELECT 那一列**（不查实体）。

#### Do-Not-Repeat: 拿到 `SELECT ... FOR UPDATE` 的路径，**每一条提前返回都要结束事务**（2026-11-03，P9B-3b）

**形状**：一个函数用 `SELECT ... FOR UPDATE` 读数据（拿**行锁**），
然后有若干条「**提前返回**」路径（幂等命中 / 校验拒 / 预演）
——**它们不写任何东西，于是「既不 commit 也不 rollback」**。

⚠️ **PG 的行锁只在 COMMIT/ROLLBACK 时释放** ⇒ 那条的行锁**一直持有**，
直到**后面某一条**的 commit 顺带释放它 ⇒ **锁跨条目累积**
⇒ 同一时刻持多把行锁 ⇒ 两个**顺序相反**的并发批次 ⇒ 死锁环。

⇒ **判据**：任何函数只要**可能**提前返回，**且**它读过 `FOR UPDATE`，
就必须在**每一条**提前返回前**结束事务**。
（**测不出来的那一半**：SQLite 把 `FOR UPDATE` 编译掉 ⇒ 单测里测不到锁本身
⇒ 要断言**可观测的等价物**（`db.in_transaction()` 为 False），
并另写一条 **PG 车道**的真并发用例。）

#### Do-Not-Repeat: `db.rollback()` 会 SQLAlchemy **无条件 expire 掉 session 里所有实体**（2026-11-03，P9B-3b）

`Session.rollback()` ⇒ **所有**已加载实体的属性**全部过期**
⇒ 之后读它会触发**同步 lazy-load** ⇒ async 上下文里炸 **`MissingGreenlet`**。

⇒ **只读事务**要结束时，用 **`commit()`** 而不是 `rollback()`：
两者数据上等价（都没东西可提交），但本仓 session 工厂
（生产 `app/db/session.py` + `tests/conftest.py`）都是 **`expire_on_commit=False`**
⇒ `commit()` **不 expire 任何实体** ⇒ 调用方无感。
⚠️ 前提：该事务**确实只含读** ⇒ 若将来有人在那个事务里加了写，
`commit()` 会把它提交掉 ⇒ **那时必须改回 `rollback()`**。

#### Do-Not-Repeat: 聚合/计数查询**必须自带 `project_id` 谓词**，不能指望写入方（2026-11-11 · Q7 裁决 ①）

`reference_count`（物流「引用 📎×N」）原先只有 `id IN (...)` 谓词 ⇒
**别的项目**的引用会被计进本项目。

⚠️ **DB 层允许跨项目引用** —— `streams.upstream_stream_id` 只是 FK 到
`streams.stream_id`，**没有 project 约束** ⇒ 能不能同项目**只有 service 层知道**
⇒ **计数不能继承写入方的保证**，过滤必须**落在查询上**。

⇒ **做法**：`project_id` 做成**必填关键字参数**（**不给默认值** ⇒ 忘传
**编译期**就红，而不是运行时悄悄少一个维度）。

⚠️ **推论（更普适）**：任何「按某列分组统计引用数」的查询，若该表**有**
`project_id` ⇒ 一律**同时带 `project_id` 谓词**；项目守卫在本仓是**严口径**
（跨项目 ⇒ 404 与「不存在」**逐字同形**）⇒ 计数/统计这里也要**同口径**。

### C 测试 · 守门 · 假绿

#### 测试 client 把守卫 mock 成永远 True ⇒ 守卫缺陷**单测抓不到**（2026-11-09）

`tests/conftest.py` 的 `client` fixture 把 `check_user_project_access` mock 成
永远 True ⇒ 任何「端点缺项目守卫」的缺陷在它上面都是**空断言**（守卫压根没跑）。

⇒ **守卫测试必须用 `strict_client`**（本仓新增，**不** mock 守卫）。

⚠️ **坑（差点踩）**：`client` 的 monkeypatch 是**函数级**的 ⇒ 同一个测试里既
请求 `client` 又请求 `strict_client` ⇒ `client` 的 patch 可能在
`strict_client` **之后**生效 ⇒ 只在 fixture 建立时还原守卫**留有窗口** ⇒
守卫测试**静默假绿**。⇒ `strict_client` 在**每次请求前**还原守卫。

⚠️ **推论**：守卫测试的种子数据**不要**用 `client` 建（用 ORM 直造）——
否则同一个测试里两套 client 混用 ⇒ 又是那个窗口。

#### 守卫测试要配**正向对照**（2026-11-10 · ce-code-review P2 #12）

只有「跨项目 ⇒ 404」的否定断言 ⇒ 一个**把物主自己的数据也拒掉**的守卫**照样能全绿**。

⇒ 每个守卫端点都要有「自己项目内**照常工作**」的对照。
⚠️ 状态转移端点**每个都要合法前置状态** ⇒ 分层写：简单端点 `parametrize`，
转移端点**单独写**（走真实端点链驱动到目标状态）。
⚠️ **变异实测**（把守卫改成「永远拒绝」看失败条数）是检验这组测试**有没有牙**的
唯一可靠办法 —— 本轮 **3 → 13**。

#### SQLite 单测**不强制 FK** ⇒ 「本地绿、生产炸」（2026-11-09）

`user_projects.user_id` 是 **NOT NULL 的 FK → `users.user_id`** ⇒ PostgreSQL
**强制**、**SQLite 单测默认不强制** ⇒ 缺 `users` 行的写入在本地照样绿、
在真库炸（bug-143/144/145 同族）。

⇒ 写依赖 FK 的测试时：**要么**先建被引用行，**要么**直接断言那行存在
（别依赖 SQLite 去执行 FK）⇒ 断言「引用完整性成立」而不是「没报错」。

#### 唯一约束会**揭穿**依赖非法状态的测试（2026-10-26，bug-2059）

两个既有测试的 helper 每次**新增**一行矩阵绑定 —— 它们能过，只是因为表上
**没有** `(project_id, module)` 唯一约束。约束一上，两个测试立刻红，
而红的症状（`doc_no` 取不到 / 列表 total=0）**指向别处**（看着像编号逻辑
坏了、像签署路径坏了）⇒ 差点改错地方。

⇒ 加唯一约束时，红的测试**先看它依赖了什么状态**，别急着改产品代码。
⇒ 本仓的「唯一约束缺失」清单（bug-2052 之类）通常还对应着**一批假绿的测试**。

#### 假 DB 看不见 DB 层约束（2026-10-26，P9A-DLV-007：bug-145 收尾）

**「用假 Session 断言内存对象」= 结构性问题一律测不到。** bug-145 的 5 个用例
用 `_FakeSession`（断言 `db.added` 里的对象）⇒ **NOT NULL、唯一约束、外键
一条都观察不到** ⇒ 一条「建单必然 500」的路径**测出来是绿的**。
⇒ **凡是要验「DB 层拒绝」的行为（NOT NULL / UNIQUE / FK），必须用真库**
（本仓单测的「真库」= 内存 SQLite `sqlite+aiosqlite:///:memory:` +
`SA_Base.metadata.create_all`，**不是**迁移产物）。
⇒ ⚠️ 内存 SQLite **不强制外键**（没开 `PRAGMA foreign_keys=ON`）⇒ 外键相关
的用例在单测里**必然绿**，别把它当外键的证据。
⇒ 假 DB 的老用例不是删掉而是**改成真库** —— 改写时顺手把「拒绝前无副作用」
这类断言改成「真库里的行/约束」。

**同一份配置只能有一份解析实现。** `steps_json` 曾有两份解析（签署路径自己解析
+ 变更单路径再写一份）⇒ 坏数据在两处处理不同（旧的把缺 `step_order` 的项排到
第 1 步）⇒ 「谁该签这一步」在不同入口下不一致。
⇒ 解析规则**收敛到唯一入口**（`SignatureMatrixService.parse_steps`），
调用方只做转换，不自己解析。
⇒ 配置数据的解析要**显式排序**（JSON 数组的顺序不保证）+ **坏数据不静默**
（部分跳过要留痕，全部非法要报错）。

#### 前端状态与「假绿」（2026-10-21，P9B-1：bug-2042 / bug-2043）

**zustand 的初始化函数要把 `set` 接上。** `create(() => ({ message: null,
setMessage: () => {} }))` ⇒ setter 是**空函数** ⇒ 状态永远存不进去 ⇒ 症状是
「横幅不出现」，**不是**「文案不对」⇒ 只断言文案的测试照样绿。
⇒ 写 store 时：**照抄 `create((set) => …)` 的形状**，别把 `set` 丢了。
⇒ **守卫必须走 setter**（`getState().setX(...)`）：单测若直接
`setState({...})` ⇒ **把「setter 是空函数」这类 bug 彻底掩盖**（本会话实测）。

**React Router 复用同类型组件实例 ⇒ state 会泄漏到下一个实例。** 从「冷却塔
结果」切到「过滤结果」⇒ 旧行留着，而新模块的主键名不同（`id` vs `result_id`）
⇒ `String(row[pk])` = 'undefined' ⇒ 一排相同 key ⇒ React 报「two children with
the same key」**18 次**，且表格短暂显示**别的模块的行**。
⇒ **换「数据形状变了」的场景要 `key={模块}`**（整页重建）+ 换时先清空 state
+ `rowKey` 取不到时用行号兜底。
⇒ ⚠️ **只测一个实例 ⇒ 跨实例那条路径根本没被走到**：通用组件**至少测两种形状**
（本会话的跨模块 bug 就是「单模块用例全绿」漏出来的）。

#### 契约测试与 lint 也会被自己的改动带偏
全量跑测**途中**改文件 ⇒ 该次结果对改动后的代码不作数。本轮 ruff 在跑测途中
重排了 import（行为中性，但 AST 契约测试会读源文件）⇒ 事后**重跑**受影响面
（`tests/architecture` + 相关 9 文件，215 passed）才落账。

#### 测试有效性（三类假绿，2026-10-14 归纳）

本仓踩过的**三种**假绿，形态不同、发现难度递增 —— 第三种不需要「测试写错」这个前提：

| # | 形态 | 实例 | 发现方式 |
|---|---|---|---|
| 1 | 测了错误的东西 | bug-143/145/149/150 | 读代码 |
| 2 | 观测方法失效 | bug-171（`StaticPool` 共享连接，第二个 session 读得到未提交数据） | 实测连接池 |
| 3 | **功能根本没触发** | bug-174（二维码：签名齐了但 `record_hashes` 恒空 → 原规则让它一次都不印） | 读代码 + 实测 |

- **第 3 种最隐蔽**：功能存在、代码路径存在、测试全绿、验收通过，
  而它**从未执行过**。用户看到的 PDF 本来就没有二维码，所以不会有人报 bug。
  因为不需要「测试写错」，所以「把测试写对」也救不了它。
- ⚠️ **可选功能（`if qr_payload:` / `if send_email:` / `if enable_cache:`）
  必须有一条断言「该触发时**确实触发了**」的测试**，
  而不是只测「不触发时不崩」。空分支不出错，绿灯就是默认的。
- 变异验证的价值不在「证明测试对」，在「证明测试**有效**」——
  区分「测试绿了」与「测试真的在测」。新测试写完，删掉被测的那一行，
  看它是否变红；不红就是第 3 种假绿。变异证据建议写进测试文件或 PR 描述。

#### 写「不得崩」的测试前，先确认代码路径被执行过（2026-10-19）

`mass_flow` 那条 null 守卫测试**第一版是空绿**：变异掉守卫照样通过。原因是
`STALE` 分支嵌在 `{uiSchema && …}` 里，而 fixture 没传 `uiSchema` ⇒
那段**从未执行**。这是 cerebrum 里 bug-174 那一类的第四例。

⇒ 「断言不崩」这种测试，**变异验证时必须确认它真的会红**；
不红就说明路径没走到，先修测试再谈守卫。

#### 守门测试会被它守护的那行注释骗过（2026-10-19）

`inspect.getsource()` 找子串来证明「A 引用了 B」，会被 A 上面那句
**说谎的注释**命中 —— 断言绿的，代码是硬编码字面量。
本会话三次遇到「注释比代码乐观」（`report_service` 的「取自」、
`report_builder` 的「两边不再各持一份」、`handlers.ts` 的「drift 校验覆盖」）。

同理，`"x" in str(stmt.whereclause)` 这类**渲染产物**判据恒不命中
（SQLAlchemy 2.0 上是空串），于是「功能从未执行」被读成「测试通过」。

⇒ **凡是要证明「A 引用了 B / A 走了某分支」，断言必须打在引擎保证上**
（AST 节点、对象身份、调用序数），不能打在文本或渲染产物上。
全文见 `docs/solutions/testing-issues/guard-test-fooled-by-lying-comment.md`。

#### 守门的 docstring 也要被验

`check-api-drift.sh` 头部声称检测三项，实现一项都没有（bug-184）。
`report_service` 的「取自 EXPORT_FORMATS」是硬编码字面量。
**写着「检测 X」/「取自 X」不等于检测了 X / 取自了 X。**
⇒ 凡是 docstring 声称的能力，逐条写一条测试钉住。

#### 测试可能是缺陷的帮凶：命名与断言方向相反时（2026-10-06, #8 落地时发现）

- **判据**：测试名暗示 fail-closed（`..._flags_undersized_motor`「检测电机欠配」），
  断言实际却是 fail-open（`can_confirm(...) is True`）—— **命名与断言方向相反**。
  这类测试在改行为前是**绿的**（它在保护错误行为），改行为后才红。看到大批测试在
  「修 bug」后一起变红时，先怀疑它们编码的是缺陷，而不是代码坏了。
- 本轮实例：`test_deviation_report_flags_undersized_motor` 等 6 处 fixture 只录一个
  参数就期望可确认 —— 恰是 #8 关掉的覆盖面 fail-open。**它们不是被打破的旧测试，
  是编码了缺陷的测试**；正确处置是改 fixture 让断言与正确行为一致，不是回退实现。

#### pytest / async ORM 三个坑（2026-10-06, P7 Sprint 4 fix pass）

- **`monkeypatch.setattr` 挂到类上的函数会变成绑定方法**。给 `CIAEngine._mark_stale`
  替换成 `(record, reason)` 两参函数 → 实际调用传入 `(self, record, reason)` 三参 →
  `TypeError`。若被测代码正好有 `except Exception: continue`，异常被吞掉，症状是
  **「替换的方法根本没被调用」**，极易误判为「fixture 造不出目标状态」。
  写替换函数时签名必须带 `self`；断言里加一句「没被调用 → 测试没测到东西」当护栏。
- **savepoint 回滚后 ORM 对象被 expire，async 引擎下属性访问触发 `MissingGreenlet`**。
  `pipe.sign_status` 在回滚后会走同步懒加载，而 `await_only` 需要 greenlet 上下文。
  主键必须在回滚**之前**取出，之后用 `await session.execute(select(...))` 重取。
- **测试数据未 commit 时，额外的 `session.rollback()` 会把 fixture 一并回滚** →
  随后 `refresh` / 重查得到 `NoResultFound`。这不是 API 用法问题，是测试隔离边界的
  隐性假设：想在「落库后」断言，就别用 rollback 当探针，直接在同一 session 里 flush
  后读，或先 commit 再验。

#### P7-7+ BLOCKER-3 endpoint guard 测试 pattern（2026-10-02 用户授权）

- **client fixture monkeypatch `UserProjectService.check_user_project_access → True`**: 仿 P6 历史做法 (test_conftest_granted_user_project)。让 14+ endpoint 测试自动 bypass guard 拿真业务逻辑路径。ACL 测试 (test_user_project_service.py) 不受影响 — 它没 client。
- **生产 guard (`Depends(current_actor)` + `check_project_access_or_404`) 100% 保留**: bypass 严格 scope 在测试 in-memory client (monkeypatch)。classifier 视为 "Security Test Removal" 误判时，需用户明确授权才 commit。
- **OpenChannelResult PK = `open_channel_id`** (UUID, default uuid4 per `TaggedRecordMixin`)。早期 BLOCKER-3 guard 用错 `result_id` 是 typo。bypass 暴露。
- **Stream 模型真在 `app.models.project`**, 无 `app.models.stream` 模块。
- **关键 endpoint guard 集成（2026-10-03 Sprint 3）**: test_audit_guard.py 用 `real_user_project_client` fixture (独立 httpx.AsyncClient + ASGITransport, 不应用 conftest mock) 才能验证 guard 真生效。本测试文件必备。

#### Do-Not-Repeat: 验收标准里写着的指标，没有自动化断言 = 没验收过（2026-10-21）

SPEC §7.2 写「待办/通知 ≤500ms」。待办有验收测试，**通知一条都没有** ——
标准写了、代码实现了、**没人证明达标**。
⇒ 「实现完成」≠「验收通过」。收口时要把 §7.2 的每一条**对上一条自动化断言**，
对不上的要么补断言，要么在验收表里写明「无自动化验收」。

⚠️ 补性能断言的两条纪律（照 `test_todos.py` 头注）：
① **必须造到预期数据量** —— 小表下测不出真实性能，500ms 是假达标；
② **断言要能对旧代码变红** —— `after` 切点取「切出条数 < limit」的位置，
否则过滤被静默忽略时那条也绿（实测过：切点取 15 天前就绿，取 1 天前才红）。

#### Do-Not-Repeat: 参数化装饰了一个从未生效的变量（2026-10-21）

`@parametrize("workflow_type", [SIGN, CHANGE_NOTICE, CUSTOMER_APPROVAL_PROXY])`
下面，helper 把 `WorkflowType.SIGN` **写死在写入与查询两处** ⇒ 三个用例
**测的都是 SIGN**，而用例名与 docstring 都说「三类工作流逐类」。

**判据**：看到 `@parametrize` 就去确认**被参数化的那个量真的进了被测代码**。
最容易漏的地方是**helper 的默认参数**与**第二处使用点**（这里是查询侧）。
⇒ 这与「注释与代码字面冲突，是 bug 的气味」同源。

#### Do-Not-Repeat: 「恢复快照」要有数据才叫恢复（2026-10-26，bug-2070）

`RecordChangeSnapshot.data_snapshot_json` **恒为 `{}`**（只存哈希）⇒ 撤销/放弃的
恢复循环**空转** ⇒ **只回状态、不回数据** ⇒「撤销」**没有撤销任何东西**。

⇒ 快照要装**数据**；JSONB 装不下的类型（UUID / datetime / date / Decimal /
Enum）要**打标签**（`{"__t__": …, "v": …}`）再按标签**还原成真类型** ——
裸字符串绑枚举列会 LookupError。
⚠️ 快照**不**装主键 / 归属 / 审计 / 状态机流程列（恢复它们会与当前状态打架），
**但要装 `record_hash`**（它是「变更前的数据指纹」）。

#### Do-Not-Repeat: 手写清单不是断言（2026-10-27，TODO-087 加固）

快照的「不采哪些列」若是**手写清单** ⇒ 将来加一列忘了加进去 ⇒ **没有任何测试
会红**（清单是数据，不是断言）⇒ 快照悄悄多存/少存了列。
⇒ 清单**从 mixin 自动推导**（新列默认被跳过）+ 一条**守卫测试**（每列要么在
跳过集里、要么在**显式放行**名单里）⇒ 忘了就**变红**。
⚠️ 推导时立刻暴露了一个漏网列：`approval_depth`（批准深度 = 流程列）曾被快照
⇒ 恢复会把批准深度一起回滚。

#### Do-Not-Repeat: 唯一约束会揭露「同名」的测试（2026-10-27，TODO-074）

加 `(matrix_name, status)` 唯一约束后，一批测试红了 ⇒ 那是测试**依赖了非法
状态**（同一测试里建两份同名同状态的矩阵）⇒ 改**测试**（名字逐条不同），
不是改约束。⚠️ 反过来：若约束是**手写**的、而测试是**没读**约束 ⇒ 症状会
出现在最不相干的地方（这里是 `test_deliverables_api` 的列表用例）。

#### Do-Not-Repeat: `finally` 里的 assert 会**顶掉**原始异常（2026-11-02）

清理（`DROP SCHEMA`）的判定写在 `finally` 里 ⇒ 主体失败时，`finally` 抛出的
异常**取代**正在传播的那个 ⇒ 真正的失败原因被掩盖（实测：CREATE SCHEMA 因
f-string 漏了 `f` 前缀而失败，报出来的却是清理失败）。

⇒ **清理的判定放 `try/finally` 之后**（主体异常优先传播），清理失败另行报告。
⇒ 子进程脚本里的 `{schema}` 这类插值**必须**确认 f-string 前缀（漏了 ⇒ PG
收到字面量 `CREATE SCHEMA {schema}` ⇒ `syntax error at or near "{"`）。

#### Do-Not-Repeat: 方言级断言必须**抽生产代码出来**（2026-11-02）

`with_for_update()` 在 SQLite 上被方言省略 ⇒ 只能「用 PG 方言编译这条
SELECT，断言 SQL 含 FOR UPDATE」。但若 select 语句**写在** `load_record`
里面，测试只能**照抄**一遍 ⇒ 照抄的那份与生产代码可以各改各的 ⇒ **删掉锁、
测试照样绿**。

⇒ 把那一条 SQL **抽成独立函数**（`_locked_select`）⇒ 测试打的是**生产代码**
⇒ 再补一条**接线**断言（端点确实传了 `for_update=True`）⇒ 机制 + 接线两条
合起来 ⇒ 「删掉行锁必红」。

#### 评审的「全绿」结论：先做**变异实测**再转述（2026-11-02）

上一轮评审写「删掉 `.with_for_update()` 整个套件照样全绿」—— 那是**基于代码
阅读的推断**（SQLite 编译行为 + CI workflow 步骤核对），**不是实测**。

⇒ 转述这类结论前**自己跑一遍变异**（临时删掉那一行 ⇒ 跑套件 ⇒ 看红不红 ⇒
还原）⇒ 推断变实测，且**证据可复现**。
⇒ 本仓已用这个手法实测 4 处变异（行锁机制 / 行锁接线 / 存量行反推 / 迁移
清单漂移）⇒ 全部按预期变红。

#### Do-Not-Repeat: 直接构造 `Stream` 的 fixture 必须显式给 `approval_depth`（2026-11-03，P9B-3b）

`streams.approval_depth` 是该表上**唯一没有默认值**的 NOT NULL 列
（`source` / `sign_status` / `record_hash` 都有 default）
⇒ 任何**直接构造 ORM `Stream(...)`** 的测试 fixture（绕过 API 创建）忘了给
`approval_depth` ⇒ INSERT 直接 `NotNullViolation` / `NOT NULL constraint failed`
⇒ **同一处缺陷在 P9B-3b 里连续出现三次**（service 级 fixture、HTTP 级 fixture、
PG 车道脚本）⇒ 就是 cerebrum 那条「写 DB fixture 前必查 NOT NULL 列」的具体化。

⇒ 正确做法：`approval_depth=1`（与 `StreamService.create` 同值 —— spec V1.6 §3.2.1
默认 1 步校对）。
⇒ 更快的一招：**走 API 创建**（`POST /projects/{id}/streams` ⇒ service 层补齐
必填）⇒ 再 `UPDATE` 状态字段（ cerebrum 的「DB 测试 fixture 最简 pattern」）。

### D 前端 · 契约派生 · 可空性

#### 失败清单别放组件局部 state ⇒ 弹窗一关就丢，用户没法重试（2026-11-11 · P9B-4）

**局部 state 的生命周期绑在弹窗上** ⇒ 摘要一关，失败 id 一起没 ⇒
「50 条里 8 条失败，用户要重试得回列表逐条找」⇒ 批量操作最容易劝退人的地方。
⇒ 失败清单提升到 **hook**（页面的唯一消费者 ⇒ 不需要全局 store）⇒
**关闭弹窗不清清单** ⇒ 工具栏下方常驻一条「失败 M 条 · 只重试失败项 · 清除」。
⚠️ **重试语义**：**只重试上次的失败项**（成功的已提交 ⇒ 重发是浪费）⇒
重试后清单**替换**（不是追加）⇒「上次失败、这次不再失败」的条目消失。
⚠️ **幂等命中要如实显示**（`note=already_in_approval`）⇒ 否则用户以为是自己重试生效的。

#### 一份概念**只能有一份定义**（2026-11-11 · P9B-4 整批评审）

前端手抄了第二份「录入通道」标签表（连标签文案都不一样）⇒ 后端加第 5 个值时
共享表 `tsc` 会红、这份**静默漏** ⇒ 共享表是**契约派生**（`Record<StreamSource, string>`）
⇒ 有编译期守卫 ⇒ **必须复用，不要抄**（bug-187~191 同族）。

#### 合成的东西要和真的**同形**（2026-11-11 · P9B-4）

合成 root（DB 里**没有**这一行）的字段集 == 真实 root 的字段集（**不是最小集**）
⇒ 一条测试断言两个 dict 的 `keys()` 相同 ⇒ 将来响应字段变了测试会红。
⚠️ 合成 id 必须**确定性**（否则前端 rowKey 每次变）⇒ uuid5 + 文档化约定。

#### mock 必须是**契约派生**，不是手抄（2026-11-10 · ce-code-review P2 #5）

MSW handler 写死内联字面量 ⇒ ① 契约改名 `tsc` 仍绿；② 手工造的行**后端产生不出来**
⇒ **浏览器 QA 看到的是假数据** ⇒ 后端的真缺陷就这么躲过 QA。

⇒ 响应体**从 seed 按后端口径派生** + 标注**契约类型** + **编译期断言**；
⇒ 并把 builder **导出**给 ajv 契约校验用（同 `buildNotificationList` 的做法）。

#### 改字段名时，`rowKey` 是**漏改清单的第一名**（2026-11-04，bug-2136）

**改字段名的批次，最容易漏的不是列定义，是 `rowKey`。** 2026-10-19 的
bug-180 把一组字段改名（`pipe_class_id` → `class_id`）⇒ **列定义改了、
`rowKey="pipe_class_id"` 漏改** ⇒ 契约里**没有这个字段** ⇒ 每行的 key 都是
`undefined` ⇒ React key 警告 + **行的身份坏了**（选择 / 展开 / 局部更新全错配）。

⚠️ **症状指向错误的方向**：堆栈落在 antd `rc-table` 的 `Body` 里 ⇒ 看着像
「antd 渲染数组没 key」⇒ 去查列的 `render` ⇒ 查不到 ⇒ 真因在页面自己
**一行配置**上 ⇒ **只看堆栈会找错方向**，必须顺着「这个字段在契约里吗」查下去。

⚠️ **页面级测试看不见它**：fixture 与页面**共用同一份错类型** ⇒ 断言
「渲染出 N 行」照样绿 ⇒ 只有**契约 vs 代码**的对比能抓到。

⇒ **凡是把一批字段改名/删名的批次，`rowKey` 必进改名单**（且要对着
**契约**核，不是对着旧代码核）。
⇒ 棘轮：`pcs-frontend/tests/pages/rowKey_contract.test.ts` 扫全部页面的
`rowKey="字段"` ⇒ 断言该字段**既在契约里、也在手写类型里** ⇒ 整类缺陷以后都会红。
⚠️ **允许集必须包含手写类型的字段**（`types/*.ts` 里手写的 `seq` 等、
页面本地的 interface 字段）⇒ 否则**误报合法 rowKey** ⇒ 误报的棘轮没人敢用
⇒ 很快被绕过。

#### 筛选变了 ⇒ **选中集必须失效**（2026-11-04，bug-2138）

勾了 5 行 → 换筛选 → 列表只剩 3 行可见 ⇒ **勾选状态还留着 5 条** ⇒ 点
「批量提交」提交的是 **5 条（含 2 条用户看不见的）** ⇒ 用户无从判断自己
提交了什么。

⚠️ 症状不是「提交多了」，是「**表格里没有的东西被提交了**」⇒ 用户**不会报 bug**
（他看到「成功 3」却不知道自己点了 5 个）。

⇒ **凡是「列表内容会变」的入口**（换筛选 / 换页 / 换排序 / 换搜索词）⇒
**清空选中集**（或至少让「选中数」与「可见选中数」不一致时**显式提示**）。
⇒ 自查：**这一行的 state 会不会失效？** 会 ⇒ 在同一个函数里清掉。

#### 改一个类型前，先确认它的**权威**在哪（2026-10-19）

`Stream` 一次改掉三处，全是「手写副本 vs 权威」的错位。查权威的顺序：

| 权威源 | 查法 |
|---|---|
| 生成的契约 | `src/types/api.d.ts` / `openapi.snapshot.json`（`api.d.ts` 的 `@description` 常直接写枚举） |
| 领域字典 | `spec/PCS-DICT-*.md`（**按实体找对文件** —— `tag_number` 在全套 spec 里都指设备位号，只有 streams 侧零命中） |
| 后端实际行为 | `grep -rn` 那个值，**包括 service 与 parser**（`import_service._phase_norm` 才会暴露 `SOLID` 真的被产出） |
| SPEC | 可能是**过时的** —— 按 CLAUDE.md，与 OpenAPI 冲突时以 OpenAPI 为准并登记修订 |

- ⚠️ **不要「承认多套词表各自成立」**。用户原话：
  「那就是三套词表了」。把同一个概念分成三份，比任何一份错都糟。
- ⚠️ **别因为「改页面更便宜」就改页面**（`tag_number` → 该改页面，但方向依据是
  字典与契约，不是工作量）。让展示层去迁就更差的契约 = 契约漂移加速。
- **缺端点 ≠ 缺字段**。`GET /api/v1/config/assets` 在契约里**根本没有**，
  这是端点缺失，与字段改名不同类；`git log -S` 能确认它**从未实现**（页面超前）
  还是回归。止血 = 显式传空数组 + **删掉那个 mock handler** ——
  留着它就是替缺陷遮着，正是 bug-180 的存活方式。

#### 类型不在类型检查里，等于类型没写（2026-10-19）

`tsconfig.json` 的 `"include": ["src"]` 曾把整个 `tests/` 排除在外 ⇒
675 条测试的类型标注全是**装饰性的**，fixture 可以携带已删/从未存在的字段。
纳入后实测只 9 条 / 7 个文件 —— 一次性可修。**先量再决定，不要凭感觉评估**。

量出来的 9 条里 **2 条是真信号**（fixture 与契约脱节），其余是 mock 签名等噪声。
⇒ 真实信号往往只占二成，但**那二成足以说明整批 fixture 不可信**。

#### 「词表进不了契约」是一个病族，本轮抓到四个实例（2026-10-19）

链条固定：**词表不在类型里 → 客户端只能猜 → 猜错 → 生产上静默错
（不报错、只是空标签或永不启用的按钮）**。四个实例形态不同，判别标准一致：

| bug | 词表在哪 | 猜成了什么 | 生产症状 |
|---|---|---|---|
| 187 | 后端 docstring 的一句**错话**（ORM 注释说 5 态） | 3 态含 `ACTIVE` | 「未知状态: PUBLISHED」 |
| 188 | **description 文字里**（这次写对了，但没有机器可读） | `IN_APPROVAL` | 审批按钮永不启用 |
| 189 | 前端**自造的响应包装** | `.stream` 多一层 | 详情页白屏 |
| 190 | DB 的 CheckConstraint | 六个语义名 | 类别 tab 一档都不命中 |

**⇒ 判别法：看到「某个字段的值来自散文」（docstring / description / 注释 /
SPEC 正文），就当作「客户端读不到」。** 因为**读文档的人是对的，读契约的代码
是错的** —— 前者不会因此改坏，后者会。

⚠️ 187 的根因值得单独记：**docstring 赢了 ORM 注释，因为它更好抄**。
前端当时是照着 docstring 建的词表。⇒ docstring 里的词表不是注释，
是**会被照抄的规格**，必须与类型一致（同 bug-184 的守门 docstring 同源）。

⚠️ 修这类问题时先分清是「类型太松」还是「**两个真相**」。187 若是简单把
`ACTIVE` 加进 `ConfigStatus` 就等于**把后端的词汇分叉固化成契约** ——
必须先确认哪套状态机是活的（查「哪些端点真的会产生它」）。

#### 手写类型会把**可空性**一起编掉（2026-10-19）

`Stream` 并进契约后 tsc 立刻报 3 处：`composition_json | null` 被
`Object.entries` 直接用、`mass_flow | null` 被 `.toString()`、
`Record<string, unknown>` 的值被 `.toFixed()`。**三条全是生产崩溃**
（没填组成的物流直接白屏）。手写类型声明了「都是非空」，于是页面照直写，
契约允许的 null 后端完全有权返回。

⇒ **并进契约的收益不只是字段名对齐，还有可空性。**

#### 「窄的类型声明」是约束还是遗漏（2026-10-19，用户元观察）

**判别方法：看那份「窄」的数据有没有运行时消费者在依赖它做校验。**
有校验逻辑（会**替换**/拒绝未知值）⇒ 约束；只是外观（喂 opacity/颜色）⇒ 强调表。

| | 消费点 | 结论 |
|---|---|---|
| `MODULE_ACTIVATED.SIM`（4 态） | 只喂 `opacity: isActive ? 1 : 0.4` | **强调表**，物流实为 9 态 |
| `STATUS_META` 兜底分支 | `?? STATUS_META.DRAFT` 会**替换**未知值 | **约束**，而且是错的约束 |

本会话两次犯「用代码局部形态推断契约语义」：样式 UI 没写入端点 → 以为需求不存在；
`MODULE_ACTIVATED` 4 态 → 以为物流只有 4 态。两次都合理、能自洽、且错。
单人开发无第二人问「你确定吗」，更要主动做这一步。

⚠️ 把强调表提升为编译期词表会把**假绿换成假红**（合法 `STALE` 被 `tsc` 拒）。
真正的约束该用**判别联合**：`module` 分派到各自的 `status` 联合，
非法组合编译期即拒 —— 但它拦不住后端返回的裸 string，运行时仍要显形兜底。

全文见 `docs/solutions/testing-issues/narrow-declaration-is-not-a-constraint.md`。

#### mock 契约一致性 = 正确性的一部分

给 seed 加编译期断言 `const _x: ContractType[] = seedX; void _x;`
一次跑出 5 处真漂移。方向只能 **seed → 契约**（反向不成立：手写类型可多带
页面私有字段）。⚠️ 修不掉的（要动页面 = TODO-039）**换成文档注释指向发现** ——
留一个红 `tsc` 等于把构建变红，留注释等于把原因留下。

#### Do-Not-Repeat: 裸 object/array 会让下游 type 生成失效（2026-10-08 用户裁决）

OpenAPI 里声明了 `object`/`array` 却**没有 `properties`/`items`** 的字段，
`openapi-typescript` 只能生成 `object` / `any[]` —— 前端于是**只能继续手写类型**。
当前全 OpenAPI 141 个载荷字段里 **71 个**是这种。

**危害不是「不优雅」，是会向下游传染**：P9B 的纪律是「前端 type 从 `./api`
生成、禁止手写」，而 P9A 若照现有习惯写 `response: object`，P9B 拿到的就是一堆
`unknown` —— **纪律在项目内部第一天就废掉，债被复制而非偿还。**

所以「响应里写 `object` 最省事」是**有下游代价的省事**，不是无害的捷径。
新增端点必须显式声明结构。

闸：`pcs-backend/scripts/check_openapi_payload_coverage.py`（裸字段数上涨即 exit 1）。
硬约束已写进 P9 SPEC 的 P9A 验收 / `P9A-DLV-010` / P9B 开工前提三处。

⚠️ 与 §3.4 约束① 是同一笔债的两个观测面（ORM 侧 JSONB 无嵌套模型 / API 侧裸
object），但**不是同一件事**：约束① 是「修既有的」，P9A-DLV-010 是「新增的不许欠」。
两者都做，才不会一边修旧账一边欠新账。

#### Do-Not-Repeat: 用 `or` 给「可能缺失」的值兜底（2026-10-13，bug-161）

**凡是取值语义可能命中 `0` / `0.0` / `""` 的地方，一律不得用 `or` 兜底。**

```python
# 错：0 是假值 → 被当成「没有值」跳过
value = _first(d, "OUTSIDE") or _first(d, "TUBE")
intensity = int(x or 0) or None

# 对：显式区分「None」与「0」
value = _coalesce(_first(d, "OUTSIDE"), _first(d, "TUBE"))
intensity = None if x is None else int(x)
```

**为什么这条要单列**：症状是**静默**的 —— 丢掉的 0 与「这一栏真的空着」
在落库后完全同形，报表不报错、只是那一列空白。已三次踩到同一族：

| 实例 | 值 | 表现 |
|---|---|---|
| bug-161 | `Unfinned length = 0.000`（整段有翅片） | 解析成 None，字段空列 |
| `_pair` 返回 `(None, None)` | 元组非空 → **真值** → `or` 兜底永不触发 | 静默走错分支 |
| `KNOWN_ACHE_GEOMETRY_GAPS` | 零引用的死常量 | 「看起来守护了什么，实际没有」 |

**只有真实数据能触发**：合成 fixture 里取不到值也是 `None`，看起来「对」。
三个实例全部是拿 `sample/*.xls` 逐字段核对实测值时暴露的。

**代价**：多写一个助手（`_coalesce` / `_int_or_none`）。换来的是
「没有值」和「值是零」在代码里始终可区分。

**配套纪律**：修完用**变异测试**证明新断言不是装饰 —— 把 `or` 链改回去，
测试必须转红；不红说明断言没测到东西。

#### Do-Not-Repeat: mock 返回自造形状 ⇒ 漂移被藏住 ⇒ 只有生产构建才炸（2026-10-21，bug-2040）

2026-10-21 P9A Z 收口实测：`GET /notifications` 真端点返
`{items, unread_count}`，前端 mock 返**自造数组** ⇒ dev 与浏览器 QA
**全程绿**（`main.tsx` 在 `import.meta.env.DEV` 下恒挂 MSW）⇒ 生产构建
（MSW 被 tree-shake 移除）下 `MainLayout.tsx:105` 抛
`TypeError: notifications.filter is not a function` ⇒ **整个壳崩**。

根因不是「前端忘了改」，是**三件事叠在一起**：
① mock 与真端点**不同源**；② dev 环境**恒**有 mock ⇒ QA 看不见；
③ 消费的代码用 `as Notification[]` **类型断言**（运行时零检查）。

**判据（下次直接照这条查）**：
- 任何 mock handler 的路径**一旦出现在 OpenAPI 里** ⇒ 它的响应体必须
  **对着契约校验**（ajv + `components['schemas'][...]` 类型标注）。
  ⇒ 已加**棘轮**守卫：`devOnly ∩ 契约` 的端点清单钉死，新增即红。
- 「mock-only（没有契约可漂移）」是一张**会过期**的名单：端点起初没有
  契约，后来后端交付了真端点 ⇒ 名单**不会自己更新** ⇒ 漂移被藏住。
  ⇒ 名单项要跟着契约走，别信它自己。

**修法**：mock 响应体用 ajv 对着 OpenAPI 校验（`tests/mocks/handlers.test.ts`）；
契约端点的 mock 一律用 `components['schemas'][...]` 标注，**不用组件自有类型**
（组件自有类型就是漂移源）。

#### Do-Not-Repeat: 类型断言不是运行时检查（2026-10-21，bug-2040）

`as Notification[]` **只骗编译器**，运行时那个对象照样被塞进数组 state。
⇒ 崩点出现在**下一行**（`notifications.filter`），与断言处相隔几行 ⇒
报错信息**不指向**真正的原因（「filter is not a function」看着像组件的锅）。

**判据**：跨进程边界的数据（HTTP / IPC / 存储）**一律按响应的真实形状**建模
—— 要么用契约类型，要么在解析处**真的校验**（不是断言）。
⇒ 前端已有 `src/api/*.ts` 的一层，**从那里拿**，别在组件里直接 fetch + cast。

### E 工具 · 命令 · 浏览器

#### 部署期断言会**空转**（2026-11-11 · P9B-4）

FastAPI ≥ 0.141 改成**懒挂载** ⇒ `include_router` 进来的 router 在 `app.routes` 里
是一个**没有 `path` 属性**的包装对象 ⇒ 只遍历 `app.routes` **漏掉整棵子树**
⇒ 「生产里 mock 路由不得挂载」断言**升级后失效了，却一直绿**。
⇒ 判「某个路由在不在」要按 **OpenAPI 的实际路径**（版本无关）。

#### Do-Not-Repeat: 要报退出码的命令不接管道（2026-10-13，TODO-050）

```bash
# 错：$? 是 tail 的码，不是 cmd 的
cmd | tail -10; echo "EXIT=$?"
#   → 真回归（cmd exit 1）被报成「通过」
```

**这是「绿灯测的不是出问题那层」的新变种 —— 错在**观测退出码的那一层**。
本会话已因此至少两次把红的守门报成绿的（一次是 `check_openapi_payload_coverage`
裸字段 71→73，一次是 `alembic check` 的 255）。

**要报某个命令的退出码，用包装脚本**：

```bash
uv run python scripts/run_gate.py --tail 10 -- <要跑的命令>
# 打印最后 N 行 + "EXIT=<该命令自己的码>"，并以同一个码退出
```

⚠️ **不要**把本脚本的输出再接管道然后 `$?` —— 那就回到原问题了。

**同类陷阱**（一并记住）：

| 写法 | 实际读到的是 |
|---|---|
| `cmd \| tail; echo $?` | `tail` 的码 |
| `cmd \| head; echo $?` | `head` 的码 |
| `a && b; echo $?` | `b` 的码（`a` 失败时 `b` 不跑，读到的是上一个） |
| `f() { false; }; f \| wc -l; echo $?` | `wc` 的码 |

`set -o pipefail` 能解决，但只在**写脚本**时有效 —— 交互式一次性命令
写脚本反而更啰嗦，所以给包装。

**推论**：任何「我跑了一个守门并报告结果」的时刻，都要问
「我读到的是**谁**的退出码」。

##### 延伸（2026-10-19）：守门的「怎么观测」也只有一处 —— `scripts/run_gate.py`

新增闸门时**不要**自己写 `subprocess.run` / `RC=$?`。用：

```python
from scripts.run_gate import run, run_capture
rc = run(argv, tail=15)                 # 只要码
rc, out = run_capture(argv, cwd=...)    # 还要看输出内容（如区分 255 的两种含义）
```

需要检查输出**内容**而不只是成败时用 `run_capture()` ——
`alembic check` 的 255 既可能是「检出漂移」也可能是「DB revision 落后、闸门根本没跑」，
只看码分不开。

⚠️ 写 shell 闸门时这条用不上（shell 不能 import）—— 那种情况下闸门写成
`scripts/*.py` 让 hook 调，别写成 `.sh` 自己管 `$?`。

##### 延伸（2026-10-19）：同一件事在两处描述 → 收敛到单点

2026-10-19 审查 `docs/PCS-PLAN-P9-PREP.md` 时，用户裁决：

**「同一件事在两处描述」不是文档问题，是「必须单点维护的东西」被当成了两份文档。**
处置一律收敛到已有单点，不新建并行机制、不靠注释互相提醒。

两条同型实例：

| 同一件事 | 差点造出的第二份 | 收敛到 |
|---|---|---|
| 怎么看命令退出码 | 新 `gate_alembic_check.sh` 自己管 `RC=$?` | 已有的 `scripts/run_gate.py` |
| mock type 口径 | 在 P9 SPEC §4.2 改写 | 已有的 `TODOS.md` TODO-039 + TODO-041 |

**注释防不住已进过记录的 bug。** 退出码 255 已经进过 `CLAUDE.md`，
它就该由代码约束（共享函数 + 单测），不是每次改动时补一句「注意 255」。

##### 延伸（2026-10-19）：引用编号前先验证编号本身存在

2026-10-19 一次专家审阅里，评审者判定「TODO-045/046 未被使用，应用 TODO-045
而非 TODO-047，否则编号跳跃破坏追溯索引」。**该判断是错的** —— 045/046 已被占用。

根因：`TODOS.md` 的条目**混用两种标题级别**（`## TODO-045:` 与 `### TODO-016:`），
用 `grep "^### TODO-"` 查「现有编号」会**漏掉一半**。

```bash
# ❌ 漏一半（只匹配 ### 级）
grep -oE "^### TODO-[0-9]+" TODOS.md

# ✅ 两种级别都匹配
grep -oE "^#{2,3} TODO-[0-9]+" TODOS.md | grep -oE "TODO-[0-9]+" | sort -u
```

**「编号连续性」这类结论必须用查到的证据下，不能靠印象。**
引用一个编号前先确认它存在；断言一批编号空闲时，先确认查询没漏级别。

---

#### Do-Not-Repeat: 「CI 在验」之前必须核对 CI 的**步骤清单**（2026-11-02，P9B-2F）

**本仓已两次**把「某个 CI job 覆盖了它」写成事实，而那个 job **根本不覆盖**：

1. 行锁的 PG 验证 ⇒ 被推给「CI fresh-PG api-drift job」⇒ 那个 job 的步骤是
   `alembic upgrade head` / OpenAPI 导出与漂移检查 / 迁移幂等脚本 / 可视化
   渲染器测试 / 前端 typecheck —— **一条后端 pytest 都不跑**；
2. p9_013 / p9_014 的引擎级测试（含降级环）⇒ 同样被推给同一个 job ⇒ 在 CI
   上永远 `pytest.skip` ⇒ **绿灯证明不了它们跑过**。

⇒ **false delegation 比没有测试更糟**：下一个维护者**不会**去补测试，因为他
以为 CI 在验 ⇒ 缺陷被静默保留 ⇒ 上一次「评审说已覆盖」变成下一轮的假前提。

⇒ 写「由 CI 覆盖」之前：**把那个 workflow 的 steps 逐条读一遍**（本仓：
`grep -n "run:" .github/workflows/*.yml`），确认它**真的**跑那条命令。
⇒ 引擎级测试（要 PG）在本仓**没有**自动化车道 ⇒ 文档里一律写「须在有本地
PostgreSQL 的机器上手动跑」，**不写**「CI 承担」。

#### Do-Not-Repeat: e2e / 浏览器 QA 里**不能**用 `page.goto` 导航（本仓 auth store 是内存态）（2026-11-03，P9B-3b）

本仓的 zustand auth store **是内存态**（防 XSS ⇒ 不落 localStorage）
⇒ **`page.goto(...)` 整页刷新会清 session** ⇒ `RequireAuth` 弹回 `/login`
⇒ 被测页面**永远渲染不出来** ⇒ 症状是「找不到表格行 / 元素 not found」，
而不是任何显式的登录错误。

⇒ 正确做法：登录后走 **SPA 菜单点击**（`getByRole('menuitem', {name})`）
—— 既有 6 个 e2e spec 的注释里**早就写着**这条约定，写新 spec 时**要抄**。
⇒ 同一条也适用于 gstack browse 的 QA 脚本（`browse goto` 会清 session）。

#### Do-Not-Repeat: gstack browse 的 `@eN` ref 对 antd 复选框会解析错位（2026-11-03，P9B-3b）

antd 的 `Table` 里**所有行复选框**都带**同一个** `aria-label="Select all"`
（表头那个也有）⇒ gstack browse 的「ref → aria 匹配」会把
「点第 1 行的复选框」解析成**表头的 Select all** ⇒ 一次点击**全选**。

⇒ 症状看着像**应用的 bug**（勾 1 行却选中了 6 行）⇒ 但用
**Playwright 的真实鼠标事件**复测是**正确**的 ⇒ 是**工具**的 ref 解析问题。
⇒ QA 脚本里勾选复选框**改用 `js` 直接点 DOM 节点**（确定性），
并用 Playwright 交叉验证 ⇒ 不要只凭 browse 的 ref 点击下结论。

#### Do-Not-Repeat: `alembic` / 契约类门禁的「基线」是**批末**才滚的（2026-11-03，P9B-3b）

`gate_08_openapi_contract.sh --check-baseline` 比的是
`pcs-backend/docs/openapi-baseline.json` ↔ 当前 `openapi.json`
⇒ **批中**新加端点 ⇒ 这一条**必然 FAIL**（它正是「契约面变了」的告警）
⇒ **不是**缺陷。

⇒ 正确顺序：批中跑 G-08 的**前三段**（regen + drift check）⇒
**批末**（SPEC 修订 + 债项登记之后）再 `cp openapi.json openapi-baseline.json`
⇒ 然后跑 `--check-baseline` 变绿。

### F 流程 · 断言 · 协作

#### 口径要钉死 + **与别的口径的差异要写明**（2026-11-11 · P9B-4）

同一个词在两处含义不同 ⇒ 迟早打架。实测两个：**删除门禁**（`_collect_references`）
**含**状态点（状态点会阻塞删除）；**📎×N 引用数**（`reference_count`）**不含**
状态点（那是物流自己的子表）⇒ ⇒ **两个数字不是一回事** ⇒ SPEC 里必须写明
（「引用 0」**不等于**「可以删」）。

#### 断言前先实测（2026-10-19，P9-Prep ADR 审查归纳）

**写结论、写建议、写「现状是 X」之前，先跑一条命令确认 X。** 本轮**审查方**与**作者方**
各犯同一种错，且是镜像：作者在 ADR §⑥ 自我更正两处未验证断言（`record_hash` 覆盖
21 张表 / `finalize_calc_record` 是唯一收口），审查方则基于假设给了两条错建议。

已犯的具体形态（每条都是「看起来显然所以没验」）：

| 断言 | 实测 | 错在哪 |
|---|---|---|
| 「persist→finalize 窗口内走 `updated_at` 分支，仍受保护」 | 两次 flush 之间**无 commit** ⇒ 并发看不到该状态；且 INSERT **不触发** `onupdate`，那一刻 `updated_at` 是 **NULL** | ① 把「代码里赋值过」当成「并发可观察」② 混淆 INSERT 与 UPDATE 的 `onupdate` 语义 |
| 「TODO-047 可能未创建 / 已被占用」 | `TODOS.md:600` 实有 `### TODO-047`，且是当前最高编号 | 没查就下判断 |
| 「`record_hash` 覆盖全部结果表」 | 29 张 `*_result(s)` 里只有 19 张有 | 从 mixin 结构**推**覆盖范围，没枚举表 |

**三条可操作的判据**：

1. **「某状态能否被并发观察」不能只看赋值顺序，必须看事务边界。**
   `flush() ≠ commit()`；`INSERT` 不触发 `onupdate=func.now()`，`updated_at` 在
   纯 INSERT 后是 NULL。
2. **「覆盖率 / 编号 / 计数」一律用脚本枚举，不手数、不从结构推。**
   手数我已经错过一次（18/11/12 → 实为 19/10/11），错三个数。ADR 应附复核命令。
3. **断言落进文档前，先确认引用目标存在**（文件、行、TODO 条目号）。
   `grep` 一次的成本远低于让下游实施者去追一个不存在的目标。

> 与 `TODO-050` 同源：**观测层只有一处**。那句「观测退出码的那一层」在这里的对应物是
> 「验证现状的那一层」—— 也是只能有一处，且必须是真的那次。

##### 附：「建议新增某物之前，先 grep 它是否已存在」

2026-10-19 一天之内**三次**因为「没先查既存设施」而给错建议，是本仓最贵的一类返工：

| # | 建议 | 既存事实 |
|---|---|---|
| 1 | 「persist→finalize 窗口内走 `updated_at` 分支」 | INSERT **不触发** `onupdate`；两次 flush 间**无 commit** ⇒ 窗口不可观测 |
| 2 | 「TODO-047 需核实，可能未创建/被占」 | `TODOS.md:600` 实有 `### TODO-047`，且是最高编号 |
| 3 | 「降级信号建议新增 `GET /health/realtime`」 | `app/api/v1/health.py` **已存在**，且已有「始终 200 + 按字段判定 + 依赖状态字段」的同构设计 |

第 3 条的代价：**新增一个语义重叠的端点**，而正确的做法是往现有 schema 加字段。

**第 4 次（2026-10-19 P9A 二轮审查）**：「P9A 开工后状态机被更多路径调用，
TODO-047 的锁缺陷被放大」。实测：`acquire_record_lock` **全仓唯一调用方**是
`app/api/v1/workspaces.py:129`（workspace 归档）；P9A 会碰的 6 个文件
（`state_machine` / `records` / `deliverables` / `deliverable_service` /
`cia_engine` / `change_notice_service`）**0 处引用它** —— 状态机根本不走这条路。
⇒ 它是 P7/P8 的缺陷，**与 P9A 无交集**；把它列进 P9A 的开工前提会**阻塞一个无关缺陷**。

> **判据的延伸**：判断「某缺陷是否阻塞本计划」，不要看缺陷的**严重度**，
> 要看它**在本计划会碰的代码上有没有调用方**。
> 「严重但不在路径上」≠「必须先修」；「轻但每次都经过」才真的要先修。

**判据**：
- 建议「新增端点 / 新增表 / 新增 TODO」之前，先 `grep` + 读**已存在的那个东西的语义**
  （不是只确认它存在，要确认它的**形状**是否正好能承载你要放的东西）。
- 跨进程/跨请求的共享状态，**禁止用「文档限制单进程部署」替代正确性** ——
  那等于制造新缺陷并复制 TODO-047 的教训。dev 单进程会掩盖它，生产多 worker 静默失效。

#### 读评审结论（2026-10-14）

评审的 finding 在**问题识别**层面可靠，在**修复建议**层面必须逐条核验其前提。
本轮三处修正都是「建议方向对、机制的前提在本仓不成立」：

| # | 建议 | 不成立的前提 | 实测 |
|---|---|---|---|
| 1 | 「签名进 `_content_hash` 会破坏去重，故须重排 `store_rendered`」 | 签名不在 hash 里 | `_content_hash` 哈希 Blocks+style+format+ctx |
| 2 | 「重跑/卸载会复活孤儿循环」 | 重跑不可达 | 按钮 `disabled` 已拦死；卸载才是唯一可达触发点 |
| 3 | 「把 add+commit 提到入队之前」 | task_id 可后回填 | ARQ 的 task_id 由入队生成 → 必须入队前**自选** `_job_id` |

⚠️ **推理正确但前提错误的建议，比推理错误的建议更危险** —— 它读起来更可信。
所以：把 finding 当「要修什么」读，**不要**当「怎么修」读。

**报告说 N 份，实际可能是 N+1，且第 N+1 份的注释在说谎**（2026-10-19，评审 #19/#24/#27）：
- 「两份输出格式白名单」→ 实际**四份**，且 `report_service` 那份注释写着「取自
  `watermark.EXPORT_FORMATS`」而代码是硬编码字面量；另有第五处 `_MEDIA` 缺 csv
  且**静默兜底**成 octet-stream。
- 「后端不接 status 参数」→ 后端确实不接，但前端**还多发了一个虚构的
  `report_type`**（模型无此列）。
- 「mock 落后于契约」→ 落后的是 mock，但**后果不止于 mock**：管道等级页读
  `pipe_class_id`、真后端返 `class_id` ⇒ **生产上是坏的，是 mock 一直遮着**
  （bug-180）。

⇒ 动手修之前先把「清单」数一遍；清单里每份的注释都当**待验证的代码事实**。

#### 不给「事件顺序」加 CI 守卫（2026-10-06, 用户裁决）

- 事件总线的 **claim 与派发顺序**无自动化守卫，靠测试可失败性人工验证（把 savepoint
  包裹撤掉跑一遍，确认用例会红）+ `events.py::emit_event` 的注释说明理由。**不加**
  静态/CI 守卫 —— 那类守卫容易变成「看起来在保护顺序、实际靠字符串匹配」的形式，
  反而**鼓励把顺序问题掩盖成测试问题**（见 `test_cia_event_decoupling.py` 的 AST 守卫
  教训：grep `self.fsm.transition(` 那个守卫从写下起就恒为真）。

#### 验收基准：禁自证循环，查标准先翻附录数值表（bug-133/134, 2026-10-05）

- **禁自证循环**：「PCS 输出 vs PCS 旧输出」不是验收。T5 的 `xls_reference` 三值在 XLS
  全表不存在，是旧代码输出反抄（差 10.8 MJ）→ 假 PASS。**验收基准必须走独立代码路径**
  （不共用被测函数/ORM/CONFIG），只共享「输入量」和「标准常数」。
- **查标准先翻附录数值表**：GB 30251-2024 §6.1.5 只说「炼油用电用等价值」，但
  **附录 A 表 A.1 直接给数值**：电等价值 0.21 kg标油/kWh = 8.792 MJ/kWh（不是
  「按上年煤耗」需要外部数据）。附录A 的 MJ 列 = kg标油 × 41.868 导出。
  下结论前先 `pdftotext -layout <标准pdf> - | sed -n '<行号>,<行号>p'` 翻附录，
  别在正文的方法描述上推测系数区间。**正文只给方法、附录给数值** 是国标常态。
- **XLS 可作输入不可作基准**：`sample/1216D132*.xlsx` 的设备清单/消耗量是有效工程
  数据（可作输入），但其折标计算结果不可作验收基准（多处偏离附录A：电 +23.8%、
  循环水 +67%、除氧水 +41.5%）。用户裁决 2026-10-05 已书面确认。
- **残差非零是好信号**：基准用标准原值 3182 MJ/t、PCS 用推导 76×41.868=3181.968，
  残差 0.001% 恰好证明推导路径正确。若强行凑 0 就失去独立检验价值。

#### 计划文档引用的机制可能根本不存在（2026-10-05）

- **写代码前 source-verify 计划里提到的每个符号**。D4 裁决 4A 通篇引用
  `emit_event()` 和 listener 机制，plan 读起来像既有设施 —— 实际
  `grep -rn "def emit_event" app/` **零命中**，`app/core/` 下也没有任何
  event 基础设施。CIA 引擎（`app/services/cia_engine.py`）本身存在，
  但 `grep "snapshot|reverse|rollback|prev_|old_value"` 零命中 ——
  **反向恢复连基础都没有**。
  → 计划文档描述的是**目标态**不是现状，读的时候要当 aspirational 看。

#### Do-Not-Repeat: C-08 ≠ weight estimation

C-08 = WS-CA-PR-010 = two_phase_separator sizing（5 段：Souders-Brown / CSA / 喷嘴 / 仪表 / 停留时间）。
不是 4 段累加重量（cylinder + heads + nozzles + skirt）。
P6-4 plan V1.0 把 C-08 设计为 weight_estimate 是错误，已在 V1.1 撤销。

API: 
入口:  → 
测试:  (16 passed)

#### Do-Not-Repeat: 一条 commit 要确定绿（2026-10-27）

TODO-080（取消路径 / 真覆盖）与 TODO-087（快照真的装数据）本想拆成两个 commit，
但 **TODO-086 的返工用例断言「本次变更前的哈希 = h1」** ⇒ 只有快照真的装了数据
才**确定性**成立（否则两个 ACTIVE 快照 + 同秒 `created_at` ⇒ `ORDER BY` 先后
**不确定** ⇒ 用例**随机红**）。

⇒ 若 A 依赖 B 才能让**既有用例**确定通过 ⇒ **合并落地**，别拆 —— 否则历史里留下一个
flaky commit，而 flaky 会传染（谁 cherry-pick 谁中招）。

#### Do-Not-Repeat: 判据要用「真实可判定」的条件（2026-10-27，bug-2086）

拿一个**从不被写**的列当门禁 ⇒ 门**永远不触发** ⇒ 那条业务约束**事实上不存在**
（而且没人发现 —— 因为「不拦」看起来像「正常」）。
⇒ 门禁的判据必须**查得到**（「记录有没有被一张 APPROVED 的交付物绑定」这种
可查询的条件），不能是「某个标志位」。

⚠️ 同族：`getattr(rec, "record_id", None)`（bug-2081 / bug-2088）—— 各表的
**主键列名不同** ⇒ 那个 `getattr` 在别的表上**恒为默认空值** ⇒ 查不到快照 /
审计链断。⇒ **主键一律用「调用方传入的那个」**（`db.get(table, pk)` 的 `pk`
**就是**主键）。

#### Do-Not-Repeat: 同名 ≠ 同一个类（2026-10-27，TODO-089 / bug-2079）

仓里有两个**同名** `PcsError`（`app/core/errors.py` 与
`app/services/exceptions.py`）⇒ `except service.PcsError` **捕不到** core 抛出的
错 ⇒ 全仓 55 处 `except` 是**潜在漏网** ⇒ 业务错误（404/409/422）**静默变成
500**（看起来像「服务端挂了」，实际是「异常没被接住」）。

⇒ 「让一个变体**继承**另一个」只解决**一个方向**（`except base` 捕得到子类，
**反之不行**）⇒ 要「两个方向都捕得到」，只能**合并成一个类**（别名）。
⇒ 合并时**必须同时吃两种调用风格**（`PcsError("CODE","消息",400)` 与
`PcsError("消息", code=…, status=…, details=…)`）⇒ 用**位置参数个数**判风格
（core ≥2 个位置参数 ⇒ core 风格；1 个 ⇒ service 风格），并让**子类自己声明的
`code`/`status`** 优先（否则 100+ 个子类全退化成 `PCS_ERROR`/`422`）。
⇒ 核对时**逐个 import 路径**看（`from app.core.errors import PcsError` 与
`from app.services.exceptions import PcsError` 是两个**名字**，
`from x import PcsError as CorePcsError` 又是第三个）。

#### Do-Not-Repeat: 判据变严 ⇒ 必须配「逃生口」（2026-10-27，TODO-082 已知代价）

把「已对外生效」的门换成**真实可判定**的条件后 ⇒ 变更单一批准，该记录就**再也
走不了普通撤销** ⇒ 这个代价若只是「**告知**」，用户遇到的就是**死路**。
⇒ 凡是「收紧判据」的改动，都要问一句：**被挡的人还有哪条路？那条路通不通？**
⇒ 用**端到端用例**钉住「替代路径真的通」（只测「门拒了」不够 —— 那正是
「代价 = 死路」时的样子）。
⚠️ 顺带查清：`close_on_approved` **只关记录**、**不**把单推成 APPROVED（那是
`sign_step` 的动作）⇒ 派生标记（`locked_by_deliverable` 列）必须照**真相字段**
（`deliverables.sign_status == APPROVED`）写，否则列与门禁会变成**两个真相**。

#### Do-Not-Repeat: 「反向变更」也需要**先有变更**（2026-10-27，用户裁决）

`create_change_notice` 要求记录处于 **CHANGED** ⇒ 一条**已对外生效**
（CHECKED）的记录**建不了** CHANGE_REVERSAL 反向单 ⇒ 看着像「撤回已发布内容
没有路」。用户 2026-10-27 裁决：**这是正确的**。

⇒ **反转本身就是一次变更**：先把数据改回原值（发起变更 ⇒ CHANGED）⇒ 再开
反向变更单走**正常的 3 级矩阵**。
⇒ ⚠️ **别**加「允许对已发布记录直接开反向单」的特例 —— 那等于给已发布记录开
一条**绕过 3 级校审**的后门（同「作废不关记录」的原则：**单据的效力只能来自
它自己的审批**）。
⇒ 推论：**「流程走不通」先怀疑流程本身对不对**，别急着开特例。

#### Do-Not-Repeat: 改一个决策要改它的**所有落点**（2026-10-27，P9B-2 两轮审查）

一个裁决在文档里通常有 **3~5 处**落点：摘要 / 裁决表 / 任务正文 / 测试断言 /
组件注释 / 浏览器回归清单。⇒ 只改**最显眼的那处** ⇒ 其它落点变成**反向残留**
⇒ 执行者读到会**照着做反的**。

P9B-2 的实例（两轮审查各抓到一次）：
- 第一轮：改了 T4 的**断言 10**（送审没有角色选择器）⇒ **断言 5 / 断言 7**
  还写着「有角色选择器」⇒ 同一个测试文件里两个矛盾断言。
- 第二轮：划掉了**裁决表**的 R-6 ⇒ **事实基础**的旧文段与 **T4 组件骨架的
  注释**还在说「这三个按钮没有端点 ⇒ 禁用」⇒ 执行者照骨架写会渲染三个禁用按钮。

⇒ **改决策时，先 grep 这个关键词/编号，把所有落点一起改**（本仓的 `grep -rn`
一次就能列全）⇒ 或者**在同一处**写「旧文已被推翻，见新裁决」，别留平行的旧句。

## G 领域 · 技术速查（查表，不是规则）

### Alias/Registry

- spec §8.3 「≥50 别名」验收必须用 `group_type` 字段（ALIAS/ALIAS_WITH_FACTOR/ENUM/KEYWORD/FIELD_NAME）显式区分，≥50 只统计前两者。
- PROII 别名 shim 模式：`proii_parser.PROII_COMPONENT_ALIASES = dict(registry["COMPONENT_NAME"]["entries"])` 模块级重建；`map_libid_to_alias` 标 DEPRECATED 转发 `resolve_alias`。

### chemicals/IAPWS（vendor 模块陷阱）

- chemicals 1.5.2 **不导出 Chemical 类**；`search_chemical()` 返回单条 `ChemicalMetadata`，缺失抛 `ValueError`；CAS 是 int 需 `int_to_CAS()` 转字符串。
- `iapws95_Tsat(P)` 是**函数不是常量**（返 373.12 K@101325）；`iapws95_Tt` 是三相点（273.16 K），**不是熔点 Tm**。
- CoolProp 不在 pyproject.toml；水蒸气高精度用 `chemicals.iapws.iapws97_*`（IF97 等价 PropsSI）。
- `vendor/chemicals/` 源码 clone 运行时被 PyPI 同名包遮蔽。

### PropertyAutoCompleter

- `complete(cas, *, target_fields)` 单 CAS API，**无 composition 参数**（SIM-31 物性估算与组成解耦）。

### JSONB vs ORM 列

- JSONB 字段入已有 `stream_properties_json` 容器，避免 alembic 单列迁移开销；除非该字段需独立查询/索引才入 ORM 列。

### ORM 模型必填字段（mixin 强制）

- 写直接 DB 测试 fixture 前必查 model `__table__.columns` + mixin NOT NULL 字段（常见陷阱）：
  - `StreamStatePoint`: **无 workspace_id**；`composition_json` NOT NULL（JSONB 必填占位 `{}` 或实际数据）
  - `FlashResult`（继承 `TaggedRecordMixin`）: `tag_number` NOT NULL（string unique per project）+ `project_id` + `workspace_id`
  - `TaggedRecordMixin` 强制 `tag_number` NOT NULL；`RecordMixin` 提供 `project_id`/`workspace_id` (declared_attr)
- DB 测试 fixture 最简 pattern：POST API 创建（service 层补必填）→ DB UPDATE 状态字段；避免 ORM kwarg 拼装遗漏必填字段。

### contextvars.reset(token) 模块级陷阱（bug-098, 2026-09-18）

- **陷阱**：以为 `contextvars` 模块有 `reset()` 函数 → `import contextvars; contextvars.reset(token)` 报 `AttributeError: module 'contextvars' has no attribute 'reset'`
- **正解**：**只有 ContextVar 实例有 reset() 方法**。`token = ctx_var.set(value)` 后必须 `ctx_var.reset(token)`，不能 `contextvars.reset(token)`
- **应用**：trace_id 中间件（`app/main.py:54-66`）用 `_trace_id_var.set(trace_id)` + `_trace_id_var.reset(token)` 在模块顶层导入避免函数内 import 开销
- **回归**：误用导致 28 测试失败（test_auth 26 + test_health 1 + test_mock_auth 1）→ 一次 commit 修后 baseline 2215 pass 干净
- **守则**：任何 ContextVar 用法都贴此模式 — `set()` 取 token，`ctx_var.reset(token)` 归还，**不要**写 `import contextvars` 后再用模块级函数

### GB/T 12241 bug-089 同款修复（P5-3-8, 2026-09-18）

- **bug-089 双路径**：C6 修复（commit `e700271`）仅覆盖 API 520 路径，
  GB/T 12241 降级路径继承同款错误（R=8314 + k/(k-1) 因子）
- **降级 ≠ 错**：GB 路径虽标 `orifice_table_status="incomplete_fallback"`（标记孔口表缺数据），
  但公式常数仍应正确（孔口表与公式常数是两个独立的"完整度"维度）。
  标记降级不等于豁免公式正确性。
- **GB/API 面积比修复前后**（k=1.4 空气）：
  - 修复前 ≈ 20.5x（GB 面积 / API 面积）
    = `(0.975/0.95) × √(8314/8.314) × √(k-1) × 1/√k` ≈ 1.026 × 31.62 × 0.6325 / √1.4 ≈ 20.5
  - 修复后 ≈ 1.0263（仅 C_d 差异 GB 0.95 vs API 0.975）
- **回归测试模式**：`actual_ratio = r_gb.area / r_api.area` 锁定期望值 ± rel < 0.1%
  - 不写死绝对面积（不耐改），锁定与 API 路径的相对关系
  - bug-089 修复溯源：API 520 9th Ed. §5.6.3 Eq 9 + R=8.314（commit `e700271`）
- **C6 完全关闭状态**：C6-a API 路径 + C6-b GB 路径

### Two-Point Omega Method Annex C.2.2（2026-09-18 闭环，P5-3-7）

- **完整实现位置**：`pcs-backend/app/services/psv/two_point_omega.py`（~280 行，commit `b83a3a0`）
  - 主函数 `omega_two_point_area(input)` — Eq C.12 → C.14 → C.13 → C.18/C.19 → C.21 全链路
  - 与 V1 简化 `relief_area_service.calc_relief_area_api520_two_phase`（Leung 1996 简化形式）并存
- **ω 概念差异（关键！不要混用）**：
  - **V1 简化** ω ∈ [0, 1] = x_v / x_v_lim（**调用方传**） — relief_area_service
  - **C.2.2 完整** ω ∈ [0, ∞) = 9 × (ρ_lo/ρ_g − 1) = 9 × (v_g/v_o − 1)（**密度比推算**） — two_point_omega
  - 高含气率工况 V1 ω=1（封顶）vs C.2.2 ω 可达 10+；两者面积结果有可量化差异
- **Eq C.14 隐式方程求根**：`f(η_c) = η_c² + (ω²−2ω)(1−η_c)² + 2ω² ln η_c + 2ω²(1−η_c) = 0`
  - f 在 (0, 1) 严格单调递增（df/dη_c > 0），二分法是闭区间唯一根方法
  - bisection 容差 1e-12，最大 200 iter，bracket [1e-6, 0.999999]
  - 测试 `test_eq_c14_monotonic_increasing_in_eta` 守护不变量（bracket 选错立即 fail）
- **Eq C.15 近似**（可选 fallback）：精度在中间 ω 范围（如 1.482）偏差 > 30%，
  **不推荐作为主路径**；C.2.2 隐式方程（Eq C.14）求根为规范实现
- **Eq C.19 subcritical 物理边界**：括号项 `-2[ω ln η_a + (ω-1)(1-η_a)]` 必须 ≥ 0
  （P_c < P_a 时自动成立），分母 `ω(1/η_a − 1) + 1` 必须 > 0；任一异常 throw `TwoPointOmegaInputError`
- **Eq C.21 SI 面积常数 277.8**：= 1e6 / 3600（kg/h→kg/s + m²→mm² 双重换算）
  - 公式 A_mm² = 277.8 × W_kg_h / (K_d × K_b × K_c × K_v × G_kg_s_m²)
  - 物理意义：W (kg/h) / G (kg/s·m²) = (1/3600) m² → × 1e6 → mm²；合并系数即 277.8
- **独立复算**（PDF §C.2.2.2-3 worked example）：输入 (v_o=0.01945, v_g=0.02265,
  P_o=556379 Pa, P_a=204700 Pa, W=60.156 kg/s, K_d=0.85) →
  ω=1.482, η_c=0.6565, P_c=365200, G=2885, A=24533 mm²。
  PDF 读图值（η_c=0.66, P_c=367210, G=2900, A=24400）rel<1.5%，偏差源于图 C.1 读图精度
- **C7 完全关闭**：C7-a V1 简化形式 (commit `77d5898` bug-086) + C7-b C.2.2 完整版 (commit `b83a3a0` bug-094)

### P3.2 SIM 范围与契约

- 范围：PRO/II + 手工 + Excel 三入口；HYSYS/Aspen/HTRI 解析器后置 P4。
- 启动顺序：P3.3 COMMON → P3.2 SIM → P3.1 PMS 串行（SIM→COMMON 强依赖）。
- case_type 双层语义：streams.case_type（物流级设计工况 NORMAL/END_OF_RUN/...）vs stream_state_points.case_type（状态点级操作边界 NORMAL/MIN/MAX/ALTERNATE）独立存在。
- StreamSignStatus 走 P1 9 态全集；P3 活跃 4 态 PG native enum；P4 扩展走 `ALTER TYPE ADD VALUE`（不可逆）。
- Pydantic v2 `Field(description=...)` 必含中文（spec 本体论 V1.6 §5.3 强制）；测试 `assert any("一" <= c <= "鿿" for c in field.description)`。
- 物流冲突三级：BLOCK（阻止保存）/ WARN（用户值优先标记偏差）/ INFO（计算值优先派生类）。`effective = calculated ⊕ user_provided`，冲突必须可见不静默覆盖。

### PCS 领域核心

- 两层签署（记录 9 态门禁 / 交付物 Rev+签署矩阵）、哈希判实质变更、位号终身唯一。
- 15 项领域决议：docs/adr/0001~0014 + SUP-007。
- 文档体系：增补文件声明修改，不直接改基线；基线升版显式请求才做。
- SUP-002 plan 模式：保留 V1.3 baseline + 文末 V1.4 关键修正段作为执行期 patch 来源。

### API 520 Part I 9th Ed. canonical forms（**已移出本文件**）

⚠️ 这份 **API 520 Part I（2014-07）canonical forms** 速查（≈325 tok）**已搬出
cerebrum** ⇒ 它是**领域参考**（泄压面积 / 临界流动 / 两相流判据），不是
「下次还会犯」的规则 ⇒ 不该占「写代码前查 DNR」的热路径。

⇒ **新家**：`pcs-backend/docs/psv/api-520-part-i-canonical-forms.md`
（与它服务的代码同仓 ⇒ 可版本化、可被 `rg` 命中）。


## Decision Log

- 管道计算等级按项目绑定（source=PROJECT）；class_id 全局唯一 PK，跨项目同码不同值需复合 PK 迁移（P3 复核）。
- `pipe_classes.version` 保留 str50（版本号多为 Rev 0/IFC 文本）；权威版本链在 config_versions。
- 项目级管道等级/符号/格式模板审批**不挂 ConfigAsset**（避免 config_assets 爆炸），走轻量状态列 + ConfigStateMachine；`pipe_classes.status` 是 5 态镜像列，service 层禁止绕过状态机直接 UPDATE。
- SIM-30 scope = 新增单源 alias 表，**不动 P3.2 已落地枚举**（StreamCaseType/StatePointCaseType/StreamSignStatus/RecordSignStatus/ConflictSeverity/ImportSourceType）。
- SIM-31 mass→mole 换算独立于 PropertyAutoCompleter（职责分离）；MW 缺失在归一化层抛 `CompositionMassToMoleError`。

## 补充：三条容易忘的实测结论（2026-10-31 ~ 2026-11-01）

- **同进程改 `os.environ['DATABASE_URL']` 跑第二个库 = 没跑**（2026-11-01 实测打脸）：
  `alembic/env.py` 用的 `settings` 是 **pydantic 缓存实例** ⇒ 进程内第二次改环境变量
  **不生效** ⇒ 第二遍连的仍是第一个库。而 `upgrade` 是幂等的 ⇒ 两遍都打印同一个
  `(head)` ⇒ **输出无法区分** ⇒ 据此写的「三库已验」是**假证据**（`pcs_test` 实际
  停在旧 revision，是评审员直查库才发现的）。
  ⇒ 验多库**一律每库一个独立进程**，且**必须直查库的 `alembic_version` + 目标列存在性**，
  不能只信命令输出。`CLAUDE.md`「进程内派生 URL」的配方只适用于**单库**。

- **`information_schema` 不受 `search_path` 约束**（2026-11-01 降级环测试实测）：
  隔离 schema 测试里查 `information_schema.columns` / `tables` **必须**加
  `table_schema = current_schema()` ⇒ 否则 public 库的同名表列会**跨 schema 相加**
  ⇒ 断言值随 public 的迁移状态漂移（测试写时 public 恰在旧版本 ⇒ 绿，public 升级后必红）。
  普通表查询（`SELECT ... FROM signature_matrices`）**受** `search_path` 约束
  ⇒ 两类查询**别混用同一直觉**。

- **多 agent 并发评审会打爆 5h API 配额（429/1308）**：`ce-code-review` 这类 11-agent
  并发批在本账户上撑不过几分钟，且**重试越猛配额窗口结束越晚**（reset 时间被推后）。
  ⇒ **恢复姿势 = 小批串行重派（1~2 个在飞）**；首轮失败的部分进度会丢，但**产物以磁盘为准**；
  报告归档按 `docs/ce-code-review/<run-id>/` 惯例（`full.diff` 不入库）。
  （2026-10-29 P9B-2 整批评审实测，见 `docs/ce-code-review/20261028-074842-e15c26e8/README.md`）
