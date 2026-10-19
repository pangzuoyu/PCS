# ADR-0046：用户身份模型迁移 —— uuid5(username) 派生改为 users 表持久化主键

- Status: **accepted**
- Date: 2026-10-19
- Deciders: PCS 架构组（单人开发，用户裁决）
- Consulted: `app/api/v1/auth.py`、`app/models/project.py:135`、`app/services/ldap_client.py`、`app/api/v1/mock_auth.py`
- Informed: P9A 实施者、P9B 前端
- Supersedes: —
- Superseded by: —
- Related: ADR-0007（客户凭证代录）、ADR-0041 §编号预留（0042 = 解冻机制，故本 ADR 取 0046）、CLAUDE.md §测试前检查、SPEC §3.2.2 P9A-USR-001~007、P9-OPEN-008

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
三个断言会在 mock 流量下失效：

| ADR 断言 | 不处理 mock 的后果 |
|---|---|
| §③ 停用用户拒绝登录 | mock-login 是独立签发路径，停用用户在 mock 下照样拿到有效令牌 |
| §① DB 主键唯一权威 | mock 不建 `users` 行 ⇒ `_derive_user_id` 回退 uuid5 ⇒ §② 的「30 分钟收敛窗口」变成永久 |
| §⑤ 停用即刻作废 | mock 令牌无 `tv` claim ⇒ `/auth/refresh` 无从比对 ⇒ P9A-USR-004 离职处理失效 |

**裁定**：把「user_id 解析 + 惰性建行 + `tv` claim 签发 + `users.status` 判定 +
审计写入」抽成单一的 `_issue_tokens()`，**`/auth/login` 与 `/auth/mock-login` 共用**。
两条路径的唯一差异是凭据校验方式：LDAP bind vs 查 `MOCK_USERS` 表。

这样 §①/③/⑤ 对 mock 流量（前端 QA、pytest）同样成立，不存在「只有真实登录才受保护」的裂缝。

角色来源不冲突：`/auth/login` 的角色来自 `resolve_role(user.groups)`（`auth.py:261`），
AD 同步的角色来自同一批 AD 组 —— 同源，惰性建行不会与 AD 同步互相覆盖。

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

## 后果

- `users` 表从 0 行变为登录路径的必经表 ⇒ AD 同步（P9A-USR-002）成为必需而非可选。
- 历史 JWT 在 30 分钟窗口内 actor id 仍可能是 uuid5 值 ⇒ 该窗口内不得启用
  「按 users 行判停用」的强拦截以外的新逻辑。
- 迁移纪律：新表列走 `TimestampMixin` 三列纪律；本 ADR 涉及的列变更需手写迁移
  —— ORM 里写 `ForeignKey(..., use_alter=True)` **不会**自动生成迁移（bug-146）。
- 登录路径与 mock 路径共用 `_issue_tokens()` 后，`/auth/login` 的响应时延增加一次
  `users` 查表 + 可能的 upsert。**这是有意的**：把身份判定放在登录时，
  换来请求路径上不必每请求查库。

## 尚未解决

- **存量孤儿清单的产出归属未写明**。② 采纳了「惰性建行、不批量回填」，但
  「导出 `user_projects` / `audit_logs.created_by` 中无对应 users 行的 uuid5 清单」
  这一步需要先有 users 表与登录路径才有判据 ⇒ 落在 **P9A**。
  **P9A 开工时必须补这一条，否则会掉。**（已同步写入 SPEC §3.2.2 P9A-USR-005）
