---
module: pcs-backend 角色闸（app/api/v1/config.py · user_projects.py · stream_batch.py）
date: 2026-11-23
problem_type: security_issue
component: acl
severity: high
symptoms:
  - "`GET /api/v1/user-projects/me` ⇒ ⇒ **403**：`PROCESS_CONTROLLER` / `VIEWER` 拿不到**自己**的项目清单 ⇒ ⇒ 前端的项目选择器对这两类人**直接空**"
  - "`POST /api/v1/streams/batch-submit` ⇒ ⇒ **403**：合法角色 `PROCESS_CONTROLLOR`（多一个 O）**永远匹配不上** ⇒ ⇒ 工艺室的人批量提交校对**不可用**"
root_cause: role_whitelist_copied_by_hand
resolution_type: test_and_source_fix
---

# 角色白名单**手抄第二份** ⇒ ⇒ 合法用户 403（拼错比漏写更隐蔽）

## 现象

两处**都是合法用户被 403**，而代码里「看起来有闸门」：

| 端点 | 闸门里写的 | 真实角色 | 后果 |
|---|---|---|---|
| `GET /user-projects/me` | `DESIGNER` `CHECKER` `APPROVER` `REVIEWER` `SYSTEM_ADMIN` | 还应有 `PROCESS_CONTROLLER` `VIEWER` | 这两类人**拿不到自己的项目清单** |
| `POST /streams/batch-submit` | `DESIGNER` `PROCESS_CONTOLLOR` `SYSTEM_ADMIN` | `PROCESS_CONTROLLER` | 批量提交校对**永远 403** |

⚠️ 两个端点**都**在**文档 / OpenAPI 描述**里写着**正确的**角色
⇒ ⇒ 「照文档理解」的人看不出问题 ⇒ ⇒ 只有真用户撞上。

## 根因

**角色白名单被抄了第二份**：

- `current_actor` 里有**一份**（JWT 的 `role` 声明白名单 · 局部字面量）
- 端点想写「所有合法角色都能进」时 ⇒ ⇒ **只能再抄一份** ⇒ ⇒ 抄漏 / 抄错

⇒ ⇒ **拼错**比**漏写**更隐蔽：漏写 ⇒ ⇒ 那类用户**新出现**时才炸；
拼错 ⇒ ⇒ **从写下的那天起**那一类人就**一直**是 403 ⇒ ⇒ 而测试里
没有那种角色 ⇒ ⇒ **测试永远绿**。

## 处置

① **白名单提为模块级常量**（唯一真相源）：

```python
# app/api/v1/config.py
ALLOWED_ROLES: frozenset[str] = frozenset({
    "DESIGNER", "PROCESS_CONTROLLER", "REVIEWER", "APPROVER",
    "SYSTEM_ADMIN", "VIEWER", "CHECKER",
})
```

② 端点写「所有合法角色」时**引用**它，不再手抄：

```python
require_roles(actor, *ALLOWED_ROLES)
```

③ **守卫**（`tests/api/v1/test_user_projects_me_roles.py`）：
- **参数化**：白名单里的**每个**角色各打一次 `/me` ⇒ ⇒ **缺一个 ⇒ ⇒ 那个角色红**
  （新增角色时**自动**被覆盖）
- 「不在白名单的角色 ⇒ ⇒ 403」（闸门没被顺手拆掉）
- **根因守卫**：端点源码里**不得**再出现字面量角色清单 / 拼错的角色名

## 教训

- ⚠️ **任何「角色清单」新增 ⇒ ⇒ 先问：这是第几份？**
  ⇒ ⇒ 抄第二份 = 下一个「合法用户 403」。
- ⚠️ **拼写错误在 ACL 里等价于「永久拒绝」** ⇒ ⇒ 角色名**拼错**比**漏写**更贵
  ⇒ ⇒ ⇒ 白名单要有**唯一真相源**（常量）⇒ ⇒ 且要有**参数化**的逐角色断言
  （否则新角色进白名单时没人试）。
- ⚠️ **文档写对了不代表代码写对了** ⇒ ⇒ ACL 的**文档与实现**要能互查
  （本例：docstring 与 OpenAPI 都写着 `PROCESS_CONTROLLER` ⇒ ⇒
  反而**掩盖**了拼写错误）。
