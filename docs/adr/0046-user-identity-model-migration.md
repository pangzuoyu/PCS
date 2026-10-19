# ADR-0046：用户身份模型迁移 —— uuid5(username) 派生改为 users 表持久化主键

- Status: **accepted**
- Date: 2026-10-19
- Deciders: PCS 架构组（单人开发，用户裁决）
- Consulted: `app/api/v1/auth.py`、`app/models/project.py:135`、`app/services/ldap_client.py`、`app/api/v1/mock_auth.py`
- Informed: P9A 实施者、P9B 前端
- Supersedes: —
- Superseded by: —
- Related: ADR-0007（客户凭证代录）、ADR-0041 §编号预留、CLAUDE.md §测试前检查、SPEC §3.2.2 P9A-USR-001~007、P9-OPEN-008

> **编号说明（2026-10-19 决策委员会要求补）**：本 ADR 取 **0046**，不是因为 0042~0045
> 已被占用，而是因为 **ADR-0041 正文预留了它们**：
>
> | 号 | ADR-0041 的处置（`docs/adr/0041-c-12-vessel-6-path-coverage.md:14-15`） | 本轮实际 |
> |---|---|---|
> | 0042 | **明确预留** = C-12 解冻机制 | 未动，留给解冻机制 |
> | 0043–0045 | 落入 ADR-0041 的「0043+ = 后续接口扩展」**兜底桶**，无逐号指定 | 本轮未占用 |
> | 0046–0049 | 0041 之后的首批空号 | **P9-Prep 的四份 ADR** |
>
> 简言之：**跳号是为了守住一个已写下的预留**，不是为了给已用号让路。
> 下一个写 ADR 的人若看到 0043~0045 空着，**不要**把它们当作「本可使用的空号」——
> 它们在 ADR-0041 的兜底桶里。要用请接着 0050 起。

## 背景

`app/api/v1/auth.py:31` 定义 `_UUID5_NAMESPACE_DNS = uuid.NAMESPACE_DNS`，
`_derive_user_id()`（`:34-39`）在 JWT 缺 `user_id` 声明时回退 `uuid5(NAMESPACE_DNS, sub)`。
`/auth/login` 更是**无条件**用 `user_id = uuid.uuid5(_UUID5_NAMESPACE_DNS, user.username)`
（`:263`）写进 JWT claim。

即当前**没有任何代码查 `users` 表**判身份。

`users` 表模型已存在（`app/models/project.py:135`），字段含
`status`（`UserStatus.ACTIVE/DISABLED`）、`roles`（JSONB）、`ad_groups`（JSONB）、
`email` / `department`，但**真库 0 行**。

`user_projects.user_id` 的 FK → `users.user_id`（`app/models/project.py:188-190`，
`ondelete="CASCADE"`）已随 P7-7+ 补上。**这意味着派生 ID 已可能指向不存在的 users 行**，
而 FK 约束只保证「users 行存在时 project 授权才成立」，不保证反向。

前端已在 P7-7+ 改为从 `/auth/me` 取权威 `user_id`，不再自行派生，
派生分叉风险仅存后端一处。

`token_version` 全仓 0 命中（`grep -rn "token_version" app/ alembic/`），为本 ADR 新引入。

## 决策

### ① 历史 uuid5 与 DB 主键的等价性

**DB 主键成为唯一权威。** 登录成功后查 `users`；命中则用其 `user_id` 写入 JWT
`user_id` claim（该通道已存在于 `auth.py:264-276`），此后所有请求的 actor id 取自 claim。

`uuid5` 回退**保留但降级**：仅用于签发前存量 JWT 的解析（access token TTL 30 分钟），
该窗口内若用户已被停用，靠 `token_version` 拒绝 refresh，access token 最长 30 分钟后自然失效。

> **不得**在迁移期直接删掉 `_derive_user_id` 的 uuid5 分支 ——
> 删了会让所有未过期的存量 access token 立刻 500，而不是优雅降级。

### ② 是否回填历史 uuid5 为 users 行

**不批量回填。** 理由：`users` 当前 0 行，回填需为 `user_projects` /
`audit_logs.created_by` 里每个 uuid5 反查 username，而派生值不可逆（`uuid5` 单向）
—— 只能靠 JWT / 审计里的 username 旁证，噪声大且不可验证。

改为**惰性建行**：用户首次登录时按 username upsert `users` 行。

存量孤儿（`user_projects.user_id` 无对应 users 行）在 ADR 落地时导出为一次性清单，
交由人工确认后再决定补行还是保留孤儿。**不删** —— `user_projects` 的 FK 是
`ondelete="CASCADE"`，删 users 行等于连带删光该用户的全部项目授权。

### ③ 登录路径变更

`POST /auth/login` 增一步：查 `users.status`；`DISABLED` → 401 + 写 `audit_logs`
（action = `USER_LOGIN_DENIED_DISABLED`）。`users` 无行 → 视为首次登录，建 ACTIVE 行（与 ② 一致）。

**`/auth/mock-login` 必须走同一条签发路径。**

现状（`app/api/v1/mock_auth.py:53-68`）：mock 端点从硬编码 `MOCK_USERS` 取 role，
直接调 `create_access_token` / `create_refresh_token`，**不查 `users` 表、
不写审计、签出的令牌既无 `user_id` claim 也无 `tv` claim**。若不一并处理，
三个断言会在 mock 流量下失效 —— **每一条是独立的触发路径，不是同一句话的三种说法**：

| ADR 断言 | 不处理 mock 的后果 | 触发时机 |
|---|---|---|
| §③ 停用用户拒绝登录 | mock-login 是独立签发路径，不查 `users.status` ⇒ **停用后仍能登录**、拿到全新令牌 | 停用**之后**发起的新登录 |
| §⑤ 停用即刻作废 | mock 令牌无 `tv` claim ⇒ `/auth/refresh` 无从比对 ⇒ **停用前已发出的令牌不会被作废**，可一直续期到过期 | 停用**之前**签发的存量令牌 |
| §① DB 主键唯一权威 | mock 不建 `users` 行 ⇒ `_derive_user_id` 永久回退 uuid5 ⇒ §② 的「30 分钟收敛窗口」变成**永久** | 一直存在 |

> 前两行都指向「停用不生效」，但**不是同一个漏洞**：第一行是「登录口没关」，
> 第二行是「已发的钥匙没作废」。**只修一行等于没修** —— 例如给 mock 加了 `users.status`
> 检查却仍不写 `tv`，停用用户照样能用旧令牌无限续期。

**裁定**：把「user_id 解析 + 惰性建行 + `tv` claim 签发 + `users.status` 判定 +
审计写入」抽成单一的 `_issue_tokens()`，**`/auth/login` 与 `/auth/mock-login` 共用**。
两条路径的唯一差异是凭据校验方式：LDAP bind vs 查 `MOCK_USERS` 表。

这样 §①/③/⑤ 对 mock 流量（前端 QA、pytest）同样成立，不存在「只有真实登录才受保护」的裂缝。

#### ③b mock **不得**建 `users` 行（决策委员会 2026-10-19 补充裁定）

⚠️ 「共用 `_issue_tokens()`」若按字面实现成「两条路都惰性建行」，会引入一个**新问题**：

`MOCK_USERS` 是硬编码的 `alice / bob / carol / dan` → 固定角色。
惰性建行的键是 username，而 uuid5 派生也用 username ⇒ **mock 的 `alice` 与
真实 AD 的 `alice` 会落进同一行 `users`**，该行的 `roles` / `ad_groups` / `last_login_at`
被 mock 流量写入。

这不是假想：`app/core/acl.py:13` 明写「ORM User（`app/models/project.py`）只有
`.roles`」—— **`users.roles` 是 ACL 的权威输入之一**，不是只写不读的展示字段。
往里写 mock 派生的角色，等于让测试数据参与生产授权判定。

> 与 §③ 末尾「角色来源不冲突」那段的关系：那段只论证了
> `/auth/login` 的 `resolve_role(user.groups)` 与 AD 同步同源，
> **没有覆盖 mock 这个第三方来源**。本条补的就是这个缺口。

**裁定：mock 走「临时签发，不持久化」。**

- `user_id` 仍是 `uuid5(NAMESPACE_DNS, username)`（确定性、可预测，不变）
- **不 INSERT / 不 UPDATE `users` 表**
- `users.status` 查询：无行 ⇒ 视为 ACTIVE（**与真实路径「无行建 ACTIVE 行」的
  结果一致，但不落库**）
- `tv` claim：写 **`0`**（哨兵值）。`/auth/refresh` 对 mock 令牌比对时，
  `users` 无行 ⇒ 期望值也是 0 ⇒ 放行。
  **一旦该 username 后来有了真实 `users` 行**（真实 `alice` 登录），
  真实行的 `token_version` 从 1 起 ⇒ `0 != 1` ⇒ **mock 的存量令牌自动失效**。
  这是想要的：mock 令牌不该在真实身份出现后还继续能用。

> 🔒 **`0` 是保留值 —— 真实用户的 `token_version` 永不为 0。**
> 迁移的列定义是 `Integer NOT NULL server_default '1'`（§④），**默认必须是 1**。
> 若 AD 同步（P9A-USR-002）或任何后续代码把 `server_default` / 建行逻辑改成 `0`，
> §③b 的自动失效机制**会静默反向**：mock 令牌与真实用户的 `tv` 全部相等，
> 变成**任何 mock 令牌都能刷新任何真实用户的会话**。
> ⇒ **`token_version = 0` 是非法值，`users` 表应有 CHECK 约束守住它**（P9A 迁移时加）。

**代价（写明，不掩盖）**：§①「DB 主键唯一权威」对 mock **流量不成立** ——
mock 的 actor id 永远来自 uuid5 而非 `users` 行。

**为什么接受这个代价**：mock 用户没有 AD 身份，`users` 表的语义是「真实自然人」，
让测试流量往里写行是污染而不是「让它也受保护」。而 mock 的存在性本身受
`app/main.py:118-119` 的 `if not settings.is_production` 限制 ——
**生产环境连这条路径都不存在**，§① 在生产面上不受影响。

**未采纳的替代方案**：给 mock 行加 `is_mock BOOLEAN` 或往 `ad_groups` 塞 `MOCK:` 前缀。
否决理由：`ad_groups` 的语义是 AD 组 DN，塞假值同样污染词表
（本仓刚在 P8 词表治理里为此付出过 bug-180~191 的代价，见 `.wolf/buglog.json`）；
而 `is_mock` 列要为一个**生产上不存在的路径**给全表加列，不值。

角色来源不冲突：`/auth/login` 的角色来自 `resolve_role(user.groups)`（`auth.py:261`），
AD 同步的角色来自同一批 AD 组 —— 同源，惰性建行不会与 AD 同步互相覆盖。
（mock 例外见 §③b：它根本不建行。）

### ④ token_version 引入时机

与本 ADR 同批迁移加列，`Integer NOT NULL server_default '1'`。`create_refresh_token`
写入 `tv` claim。**access token 不写 tv**（保持无状态，SPEC P9A-USR-007 明确此粒度）。

### ⑤ 停用即刻作废的实现

`POST /auth/refresh` 比对 `claim.tv == users.token_version`，不等 → 401。
停用操作（`PUT /admin/users/{id}/disable`）在同一事务里 `token_version += 1`。

## 已知边界（**不得被表述为「已解决」**）

停用后**在手 access token 仍可用至多 30 分钟**（无状态，不查库）。
这是 SPEC P9A-USR-007 明确接受的吊销粒度，不是缺陷。若业务要求秒级失效，
唯一出路是改 access token 为有状态（每次校验查库）—— 属独立裁决，本 ADR 不做。

> ⚠️ **不接受「加个内存黑名单」这类半吊子方案。**
>
> **与 ADR-0048 §⑤ 是同一个 concept，两处要一起读。** ADR-0048 §⑤ 处理的是
> 「Redis 不可用时锁怎么办」，本条处理的是「不查库时吊销怎么办」，但两者踩的是**同一个坑**：
> **把一个必须跨进程共享的状态放进单个进程的内存里。**
>
> | | ADR-0048 §⑤ | 本条 |
> |---|---|---|
> | 共享状态该放哪 | Redis 锁 | `users.token_version` |
> | 用进程内存代替的后果 | 锁静默失效、并发不被串行 | 吊销名单不共享、重启即丢 |
> | 失效是否可见 | ❌ 无声（单进程测试全绿） | ❌ 无声（同左） |
> | 实证 | `advisory_lock.py:27-28` 用 `hash()` 而非 `hashtext()`（**TODO-047**，HIGH，失败无声） | 同类，无实证 |
>
> 所以：**要缩短吊销窗口，唯一出路是把 access token 改为有状态（每次校验查库）**，
> 走已收敛的 `users.token_version`。走内存名单是**换一个更安静的坑**。
>
> 📌 本段须被 **P9A 实施计划原文引用**，不能只链接 ADR —— 实施者可能只看计划不看 ADR。
> 同理，TODO-047 本身也应在 P9A-LCK 开工前处理，否则那条锁在多 worker 下一直无效。

## 后果

- `users` 表从 0 行变为登录路径的必经表 ⇒ AD 同步（P9A-USR-002）成为必需而非可选。
- 历史 JWT 在 30 分钟窗口内 actor id 仍可能是 uuid5 值 ⇒ 该窗口内不得启用
  「按 users 行判停用」的强拦截以外的新逻辑。
- 迁移纪律：新表列走 `TimestampMixin` 三列纪律；本 ADR 涉及的列变更需手写迁移
  —— ORM 里写 `ForeignKey(..., use_alter=True)` **不会**自动生成迁移（bug-146）。
- 登录路径与 mock 路径共用 `_issue_tokens()` 后，`/auth/login` 的响应时延增加一次
  `users` 查表 + 可能的 upsert。**这是有意的**：把身份判定放在登录时，
  换来请求路径上不必每请求查库。

### 🔧 待办（带归属）：`users.roles` 的列注释词表是陈旧的

**归属：P9A-USR-001「惰性建行」实施时必须一并修正。**
这不是提醒，是**欠账** —— 实施者碰到写入路径时若不同时修，治理倒退会被无声引入。

**事实**：`app/models/project.py:153` 的 `User.roles` 列注释写：

```
ApprovalRole 7 值：DESIGNER/CHECKER/REVIEWER/APPROVER/SYSADMIN/PROCESS_CONTROLLER/DATA_ADMIN
```

其中的 **`SYSADMIN` 是错的** —— 2026-10-04 的 role-string 收敛已把它全量改为
**`SYSTEM_ADMIN`**（`app/api/v1/_guard.py:37`：「历史双写 "SYSADMIN" 已全量收敛为
"SYSTEM_ADMIN"（state_machine/cia_engine/mock_auth/LDAP 同步）」，
`app/core/config.py:57` 的 `ADMIN_GROUP:SYSTEM_ADMIN` 也是这个值）。

**为什么严重** —— 这不是「文档过时」，是**文档主动误导实施者**：

1. 它**挡在写入路径上**。实施者做惰性建行时第一眼看到的是这列注释，
   不是 `_guard.py:37`。照注释写 ⇒ 产出 ACL 不认的字符串。
2. `users.roles` 是 **ACL 的权威输入**（`app/core/acl.py:13`），不是展示字段 ⇒
   错值直接进授权判定。
3. 这正是 **P8 词表治理（bug-180~191）刚消灭过的那一类**「词表不在类型里 →
   调用方猜 → 猜错 → 静默失效」。P8 刚做完的收敛，若因一条过时注释在 P9A
   被重新引入，**是治理的倒退**。

**P9A-USR-001 的动作项**：
1. 把 `project.py:153` 的注释改为现行词表（`SYSTEM_ADMIN`）；
2. 惰性建行**以 `_guard.py` 的现行词表为准**，不以该列注释为准；
3. 落库前对 `roles` 取值做契约枚举校验（同 P8 的 `StrictColumns` 做法）。

> **为什么不在 P9-Prep 修**：
> ① 修改既有 ORM 注释不在 ADR-0046 的范围内；
> ② 它是 2026-10-04 收敛的**既有遗漏**，若在 P9-Prep 顺手修，
> 日后追溯「这条注释什么时候变的」会指向 ADR-0046 的 commit —— **归属错误**。
> 正确归属是 P9A-USR-001：**那时才真正碰到写入路径**。
> ③ 列注释变更会留下一条 `alembic` 相关的 diff，等下次有人开
> `_disable_comment_comparison` 时看到，不如在有明确理由的那次一起改。

## 尚未解决

- **存量孤儿清单的产出归属未写明**。② 采纳了「惰性建行、不批量回填」，但
  「导出 `user_projects` / `audit_logs.created_by` 中无对应 users 行的 uuid5 清单」
  这一步需要先有 users 表与登录路径才有判据 ⇒ 落在 **P9A**。
  **P9A 开工时必须补这一条，否则会掉。**（已同步写入 SPEC §3.2.2 P9A-USR-005）

  **⚠️ 清单产出之后交给谁裁决（决策委员会 2026-10-19 补充）**：

  **交用户裁决，实施者不得自行决定。** P9A 只负责①产出清单、②提供补行的 SQL 模板，
  **不代替用户选**。

  理由：两种处置对授权的后果**方向相反**，不是技术优劣问题 ——
  - **补行** = 该用户的 `user_projects` 授权**恢复生效**（`user_id` 从孤儿变成有效 FK）
  - **保留孤儿** = 该用户的**全部项目授权静默失效**（访问时被 `check_record_access_or_404`
    以 404 挡掉，且不报错）

  后者尤其危险：用户只会看到「打不开」，不会看到「因为你的 users 行不存在」。
  实施者若默认「全部补行」，等于在没查清的情况下批量恢复授权；
  若默认「全部保留」，等于批量注销。二者都不可接受。

  清单产出时应同时给出：孤儿数、每个孤儿名下 `user_projects` 的行数
  （= 影响多少条授权）、以及建议的处置（补行 / 保留），供用户逐项或批量拍板。
