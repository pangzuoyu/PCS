---
module: pcs-backend — workspaces / records
date: 2026-11-18
problem_type: security_issue
component: authorization
severity: critical
tags: [authorization, workspace, project-scope, owner, 404-same-shape, P10-F, F3, audit]
symptoms: 匿名调用方 GET /api/v1/records/piping?workspace_id=… 返回 200 + 别人的管路记录与变更快照；GET /api/v1/workspaces（不带 owner_id）返回**全部**工作区；GET /api/v1/workspaces/{id} 还顺手改了 last_accessed_at（匿名写库）；POST /api/v1/workspaces 的 owner_id 由客户端指定 ⇒ ⇒ WORKSPACE_CREATED 审计行记在别人名下
root_cause: 两处**结构性缺失**叠加：① 端点**没有 current_actor 依赖** ⇒ ⇒ 连「登录」都不要求；② 作用域 id（workspace_id）只过 get_workspace ⇒ ⇒ 而它**只判存在性、零 user_projects 判定** ⇒ ⇒ ⇒ 匿名可枚举 workspace_id（workspaces 的列表端点也不要求登录且 owner_id 不传即全量）⇒ ⇒ 再用它换走任意项目的业务数据（records 的读端点）
---

# 工作区访问权：项目授权 or owner —— 「登录」是下限，不是授权

## 形状

一条链，三步，每步都独立成立：

1. `GET /api/v1/workspaces`（**不要求登录**，`owner_id` 不传 ⇒ 全量）
   ⇒ ⇒ 攻击者拿到**全部** `workspace_id`；
2. `GET /api/v1/records/piping?workspace_id=…`（**不要求登录**、**零项目授权**）
   ⇒ ⇒ 拿到**任意项目**的管路记录与变更快照；
3. `GET /api/v1/workspaces/{id}` 还带**写副作用**（`svc.touch` ⇒ 改
   `last_accessed_at`）⇒ ⇒ 匿名 GET = **匿名写库**；`POST /workspaces` 的
   `owner_id` 由客户端指定 ⇒ ⇒ **审计行也记在别人名下**（审计污染）。

⚠️ **审计面自己被污染** ⇒ ⇒ `GET /audit-logs` 给管理员看到的东西**不可信**
⇒ ⇒ 离职取证 / 签署痕迹的**流程效力**受影响。

## 口径（**这是本篇的核心**）

> **A FORMAL workspace belongs to exactly one project; a workspace that belongs
> to no project is PERSONAL.**（人裁决 2026-11-18 · TODO-169 · `CONCEPTS.md`）

⇒ ⇒ ⇒ **工作区的访问权 = 两类两种判**：

| 工作区 | 谁能访问 |
|---|---|
| **有项目**（FORMAL） | 对该项目**有 `user_projects` 授权行**的人 |
| **无项目**（PERSONAL） | **owner 本人** |

⇒ ⇒ ⇒ **「登录」是下限，不是授权** ⇒ ⇒ 一个登录用户对别人的 PERSONAL 工作区
**同样无权**。

⇒ ⇒ ⇒ **无权 ⇒ ⇒ 404**，且与「不存在」抛**同一个**异常 ⇒ ⇒ 响应**逐字相同**
⇒ ⇒ ⇒ 枚举不出 UUID。

⚠️ **为什么不能只判「登录」**：登录是**身份**，工作区归属是**授权**
⇒ ⇒ 只判登录 ⇒ ⇒ 换个账号就能读别人的数据 ⇒ ⇒ 「加了认证」不等于「加了授权」。

⚠️ **为什么不能只判项目**：PERSONAL 工作区**没有项目** ⇒ ⇒ 只判项目
⇒ ⇒ 要么把 PERSONAL 全部放行（⇒ ⇒ 又是「登录即可读别人」）
⇒ ⇒ 要么把它**整个挡掉**（⇒ ⇒ owner 本人也读不了自己的草稿区）
⇒ ⇒ ⇒ 两类工作区**必须分开判**。

## 实现（**一份**真相源）

`app/services/workspace_service.py::require_workspace_access_or_404`
⇒ ⇒ **service 层** ⇒ ⇒ API 层与 worker 层都能用（**不让 service 反向依赖 api**）
⇒ ⇒ SYSTEM_ADMIN 全局 bypass（与 `check_project_access_or_404` 同口径）。

⚠️ **「逐字同形」怎么做到的**：`get_workspace` 取不到行时抛
`WorkspaceNotFoundError` ⇒ ⇒ 守卫**也抛同一个** ⇒ ⇒ `code` 与 `message` 都一样
⇒ ⇒ ⇒ 前端**不需要**区分「不存在」与「无权」⇒ ⇒ ⇒ 枚举向量被守住。

⚠️ **反面教材（同一个仓里）**：守卫抛 `HTTPException(404, "Project not found: …")`
而端点自己的「记录不存在」抛 `HTTPException(404, "X not found")`
⇒ ⇒ **状态码相同、文案不同** ⇒ ⇒ 可区分 ⇒ ⇒ ⇒ 枚举得出存在性
（登记为 TODO-187）。

## 同族坑：授权判的 id 与落库的 id **不同源**

`POST /records/piping` 原来判 **payload 里的 `project_id`**，行却落进
**`workspace_id` 指向的工作区** ⇒ ⇒ 两个 id 可以互不相同 ⇒ ⇒
「授权在项目 A 的人把记录写进项目 B 的工作区」（实测 **200**；对照组
payload=B ⇒ ⇒ **404** ⇒ ⇒ 守卫本身是「真」的 ⇒ ⇒ **洞恰在 id 不同源**）。

⇒ ⇒ **修法**：授权对象**统一成「工作区」** ⇒ ⇒ 且 `payload.project_id`
必须与**该工作区实际挂的项目** **一致** ⇒ ⇒ 否则 **400**（请求自相矛盾）。

⚠️ **顺序**：**先授权（404）后一致性（400）** ⇒ ⇒ 反过来 ⇒ ⇒ 无权者能靠
400 读出「这个工作区属于别的项目」⇒ ⇒ ⇒ 顺序本身也是防线。

## ⚠️⚠️ 二次修正（2026-11-18 · P10-F 评审查出的 **P0**）：**「有项目」怎么判定**

上一版把「FORMAL vs PERSONAL」的分档键写成了 **`workspaces.project_id`** ⇒ ⇒
**那一列在生产路径上从来不写** ⇒ ⇒ ⇒ **FORMAL 分支在生产上永远走不到**。

| 证据 | 结果 |
|---|---|
| 谁写 `workspaces.project_id` | 只有 `POST /workspaces`（**客户端自填**）与 `import_records`（**占位方法，无调用方**）⇒ ⇒ **`POST /projects` 从不回填** |
| 迁移 | 无一条给它回填 |
| 前端 | `workspaceApi.create` **零调用方** ⇒ ⇒ 工作区只来自种子 |
| 种子 | `seed_e2e_flows.py` **会**回填 ⇒ ⇒ **E2E 造的是生产不存在的形状** |
| 开发库实测 | workspaces 1 行 · **`project_id` 非空 0 行** · projects 1 行 |
| `pcs_test` 实测（迁移前） | workspaces 254 行 · **`project_id` 非空 0 行** |

⇒ ⇒ **后果**（不是安全洞，是**功能死掉**）：
① 守卫把**所有**工作区当成 PERSONAL ⇒ ⇒ 只有 owner 本人能进 ⇒ ⇒
**项目的其他成员（有 `user_projects` 授权行）读管路记录 ⇒ ⇒ 404**；
② `POST /records/piping` 的一致性判定 `workspace.project_id is None` ⇒ ⇒
**恒 400** ⇒ ⇒ **整条写入路径死掉**。

⇒ ⇒ **修法（人裁决 2026-11-18 · 选「A」）**：
① **真相源 = 反查 `projects.workspace_id`**（`resolve_workspace_project`）⇒ ⇒
`workspaces.project_id` 降级成**展示用的冗余副本**；
② `POST /projects` 建项目后**回填**那一列 ⇒ ⇒ 副本不再过期；
③ 迁移 `p10_003` 把存量对齐（只处理**恰好挂一个项目**的工作区）；
④ **歧义 ⇒ ⇒ fail-loud（409 `WORKSPACE_PROJECT_AMBIGUOUS`）** ⇒ ⇒
「挂两个项目」违反 1:1 ⇒ ⇒ **不猜**（挑一个 ⇒ 「授权在 A 的人」可能因为挑到 B 被拒）；
⑤ `POST /projects` 建第二个项目 ⇒ ⇒ **409**（提前挡住歧义状态）。

⚠️ **教训（比缺陷本身更值钱）**：
- **守卫的键不能是「只有夹具会填的列」** ⇒ ⇒ 「守卫代码是对的」≠「守卫能跑起来」；
- **夹具必须能证伪守卫** ⇒ ⇒ 本仓的夹具**故意不填** `workspaces.project_id`
  ⇒ ⇒ 这样「把守卫改回按那一列判」的变异**必须变红**（实测 8 条红）⇒ ⇒
  ⇒ 变异敏感才是「断言在守」的证据；
- **种子脚本会掩盖生产缺陷** ⇒ ⇒ 种子回填了那一列 ⇒ ⇒ E2E 全绿而生产是死的
  ⇒ ⇒ ⇒ 「替身比被测物更宽容」的又一例。

## 顺序也是防线

守卫**必须**在**任何取数/写入之前** ⇒ ⇒ 否则「先取数再判无权」等于没判
（同 bug-172 的教训）⇒ ⇒ ⇒ 测试钉子里要断言「取数函数**一次没被调用**」。

## 测试上的两个坑

1. **默认 `client` 把项目守卫 mock 成永远 True** ⇒ ⇒ 「端点缺项目守卫」
   这类缺陷在它上面**一个都测不出来** ⇒ ⇒ ⇒ 断授权的断言**必须**用
   `strict_client`（+ 真 `UserProject` 授权行）。
2. **仓库自己的测试可能把漏洞钉成「正常行为」** ⇒ ⇒ 本次
   `tests/test_workspace.py` 与 `tests/test_records.py` **不带 token** 就断言
   201/200 ⇒ ⇒ ⇒ 「匿名可读可建」被写进了测试 ⇒ ⇒ ⇒ **修漏洞时要一并改那些
   测试**（否则它们会红 ⇒ ⇒ 而红是对的方向）。

## 效果

- `GET /records/piping` 等三个端点：匿名 ⇒ ⇒ **401**；无权 ⇒ ⇒ **404**；
- `GET /workspaces` 等三个端点：匿名 ⇒ ⇒ **401**；`owner_id` 不传 ⇒ ⇒
  **403**（admin 视图 ⇒ ⇒ 仅 SYSTEM_ADMIN）；`owner_id` 是别人的 ⇒ ⇒ **403**；
- `POST /workspaces`：`owner_id` 与令牌不符 ⇒ ⇒ **403**（⇒ ⇒ 审计行不再
  记在别人名下）；
- `GET /workspaces/{id}`：无权 ⇒ ⇒ **404**；`touch` 只在授权通过后做。

⇒ ⇒ 落地：`a2b9889`（P10-F 批 4 · F3 修复批）⇒ ⇒ 审计结论见
`guard-coverage-audit-logistics-adjacent-modules.md`。
