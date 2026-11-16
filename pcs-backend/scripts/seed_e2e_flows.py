"""流程级 E2E 种子 —— P10-B（`scripts/seed_e2e_flows.py`）。

## 它解决什么

`scripts/seed_e2e_data.py`（P10-A）是**冒烟级**：4 个用户 · **项目内角色统一
`DESIGNER`** ⇒ **测不了权限矩阵**（每个角色看到的东西一模一样 ⇒
「越权 ⇒ 404」这类断言一条都写不出来）。

⇒ 本种子只加**一个维度**：**角色矩阵**（per-user 的全局角色 × 项目内角色）
⇒ **业务数据量不扩**（TODO-149 的结论：种子只够跑冒烟，但缺的是**角色维度**）。

## 三条硬约束（每条都对应一类**静默**失败）

1. **幂等** —— 跑第二遍不炸、不重复、不留脏数据。
   不幂等的症状很隐蔽：E2E 第二次跑时表里多了一行 ⇒ 断言飘 ⇒
   排查方向会跑到「业务代码有 bug」上，而真因是脚本没幂等。
2. **只造起点态** —— 记录 = DRAFT、交付物 = DRAFT ⇒ **状态必须由场景走出来**
   ⇒ 否则 E2E 只是断言一个「摆好的状态」⇒ 状态机坏了 E2E 也绿。
3. **只删自己造的** —— `--reset` 按固定 UUID 列表筛 ⇒ 不碰业务数据。
   ⚠️ **`users` 表一个都不删**（`user_id` 是**派生值**
   `uuid5(NAMESPACE_DNS, username)` ⇒ 与真实 LDAP 账号的 id **完全相同**
   ⇒ 按 id 删 = **删掉真实账号**（`roles` / `status` / `token_version` 全丢，
   其 `user_projects` 授权行被 CASCADE）⇒ 而下次登录会把它**重建为 ACTIVE**
   ⇒ **被停用的账号被悄悄启用**。

## 授权行（`user_projects`）不是可选项

带项目守卫的端点按「该用户对该项目**有没有授权行**」判定 ⇒
没有授权行 ⇒ **一律 404**（与「不存在」逐字同形）⇒ E2E 看到的全是 404，
而 404 在这个系统里**长得和「资源不存在」一模一样**⇒ 极难定位。

## 用法

    uv run python scripts/seed_e2e_flows.py            # 幂等灌种子
    uv run python scripts/seed_e2e_flows.py --reset    # 先删自己的行再灌
"""

from __future__ import annotations

import uuid


def _uid(name: str) -> uuid.UUID:
    """固定 UUID（`uuid5` 派生 ⇒ 跨机器一致 ⇒ 幂等的基础）。"""
    return uuid.uuid5(uuid.NAMESPACE_DNS, name)


# ---------------------------------------------------------------------------
# 固定 id
# ---------------------------------------------------------------------------

#: 工作区（FORMAL）。
FLOW_WORKSPACE_ID = _uid("pcs-e2e-flows-workspace")
#: 项目（绑 `module='RECORD'` 签署矩阵）。
FLOW_PROJECT_ID = _uid("pcs-e2e-flows-project")
#: 记录级签署矩阵（3 级：CHECKER → REVIEWER → APPROVER）。
FLOW_MATRIX_ID = _uid("pcs-e2e-flows-matrix")
#: 起点交付物（DRAFT · 计算书）。
FLOW_DELIVERABLE_ID = _uid("pcs-e2e-flows-deliverable")
#: 起点记录（DRAFT · `PipingResult`）。
FLOW_RECORD_ID = _uid("pcs-e2e-flows-piping-result")
#: 自定义报表定义。
FLOW_REPORT_DEF_ID = _uid("pcs-e2e-flows-report-def")

#: 种子物流（管段）名 ⇒ `stream_id` 同样派生。
FLOW_STREAM_NAMES: tuple[str, ...] = ("E2E-FLOW-S-001", "E2E-FLOW-S-002")


def _stream_id(name: str) -> uuid.UUID:
    return uuid.uuid5(uuid.NAMESPACE_DNS, f"pcs-e2e-flow-stream-{name}")


# ---------------------------------------------------------------------------
# 角色矩阵
# ---------------------------------------------------------------------------

#: 种子用户（**7** 个）。
#:
#: ⚠️ `alice` 是给**前端真后端通道**（T7）准备的：mock 登录只认
#: `alice`/`bob`/`carol`/`dan`（`app/api/v1/mock_auth.py::MOCK_USERS`）
#: ⇒ 种子里的 `e2e-*` **一个都登不进去** ⇒ UI 流必须有一个能登录且有授权的人。
#:
#: ⚠️ `bob`/`carol`/`dan` **故意不授权** ⇒ 他们是 UI 通道里的「局外人」。
FLOW_USERNAMES: tuple[str, ...] = (
    "e2e-designer",
    "e2e-checker",
    "e2e-reviewer",
    "e2e-approver",
    "e2e-admin",
    "e2e-outsider",
    "alice",
)

#: 用户名 → **全局**角色（JWT claim）。
#:
#: ⚠️ 「全局角色 ≠ 项目内角色」：状态机按**全局**判（`TRANSITION_ROLES`）·
#: 项目守卫按**项目内**判 ⇒ 两个维度都要有 ⇒ 不能一个角色打天下。
USERNAME_TO_ROLE: dict[str, str] = {
    "e2e-designer": "DESIGNER",
    "e2e-checker": "CHECKER",
    "e2e-reviewer": "REVIEWER",
    "e2e-approver": "APPROVER",
    "e2e-admin": "SYSTEM_ADMIN",
    # ⚠️ 同为 DESIGNER，但**没有**授权行 ⇒ 跨项目 ⇒ 404（验「与不存在同形」）
    "e2e-outsider": "DESIGNER",
    # ⚠️ 为 UI 通道准备（mock 登录能登）⇒ 后端场景**不得**解析到它
    "alice": "DESIGNER",
}

#: 全局角色 → **有授权**的种子用户（**唯一**映射 ⇒ `role_headers(<role>)` 用它）。
#:
#: ⚠️ **只列有授权的人** —— `e2e-outsider` / `alice` 不在表里 ⇒
#: 要用他们必须**显式点名**（`role_headers(username="e2e-outsider")`）
#: ⇒ 否则正常场景会拿到局外人的 token ⇒ **全部变 404**（症状像「端点坏了」）。
ROLE_TO_USERNAME: dict[str, str] = {
    "DESIGNER": "e2e-designer",
    "CHECKER": "e2e-checker",
    "REVIEWER": "e2e-reviewer",
    "APPROVER": "e2e-approver",
    "SYSTEM_ADMIN": "e2e-admin",
}

#: 用户名 → **项目内**角色（`user_projects.role_in_project`）。
#:
#: ⚠️ 合法值 6 个：DESIGNER / CHECKER / APPROVER / REVIEWER / VIEWER / PROJECT_LEAD
#: ⇒ **没有 `TEST_VIEWER`**（SPEC 的 AUTH-E2E-11/12 因此延到 P10-C）。
USERNAME_TO_PROJECT_ROLE: dict[str, str] = {
    "e2e-designer": "DESIGNER",
    "e2e-checker": "CHECKER",
    "e2e-reviewer": "REVIEWER",
    "e2e-approver": "APPROVER",
    "e2e-admin": "VIEWER",
    "alice": "DESIGNER",
    # ⚠️ `e2e-outsider` **故意没有**授权行（⇒ 跨项目 ⇒ 404）
}

#: 有授权的用户（`UserProject` 行数 = 它的长度）。
AUTHORIZED_USERNAMES: tuple[str, ...] = tuple(USERNAME_TO_PROJECT_ROLE)



__all__ = [
    "AUTHORIZED_USERNAMES",
    "FLOW_DELIVERABLE_ID",
    "FLOW_MATRIX_ID",
    "FLOW_PROJECT_ID",
    "FLOW_REPORT_DEF_ID",
    "FLOW_USERNAMES",
    "FLOW_WORKSPACE_ID",
    "ROLE_TO_USERNAME",
    "USERNAME_TO_PROJECT_ROLE",
    "USERNAME_TO_ROLE",
]
