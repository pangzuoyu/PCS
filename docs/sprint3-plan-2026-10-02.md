# Sprint 3 计划: Production 前置 + Audit 可观测性

## Context

Sprint 2 收口后 (30+ commits, T5 ≤2% PASS, ce-code-review 全闭环), 进入 Sprint 3. 用户裁决: 全选 4 项 (A F-P3-001 + B F-P3-003 + C F-P2-009 + D e2e), 拆两批执行:

- **批次 1 (~2 人天)**: A (JWT/LDAP production 前置) + B (workspace archive API) + C 后端 (audit query API)
- **批次 2 (~1 人天)**: C 前端 (audit viewer) + D (e2e 覆盖)

**问题**: 当前 production 风险 (JWT role fallback 静默降级, LDAP role fallback, 无 iss/aud 校验) + audit 可观测性缺失 (无 query API + 无 viewer) + 测试覆盖缺口 (无 equipment-list e2e, 无 error-path 覆盖).

**预期结果**: 5 项 production 前置 hardening + audit 全链路可查询 + 关键页 e2e 覆盖.

---

## 增量需求 (用户裁决)

**F-P0-001 R1 签署痕迹 audit**: C 的 GET /audit-logs 应支持 `resource_type=config_energy_conversion_factors` 过滤, 让工艺室 R1 修订的 CONFIG 变更可追溯.

---

## 批次 1 (~2 人天, 可并行)

### A. F-P3-001 Production 前置

**文件**: `pcs-backend/app/api/v1/config.py`, `pcs-backend/app/services/ldap_client.py`, `pcs-backend/app/core/security.py`

**改动**:

1. `app/api/v1/config.py:460` — role fallback 单行改 fail-closed:

   **路径澄清 (source-verify 通过)**: `grep -n "current_actor" app/api/v1/config.py` 在 line 151 命中 `Depends(current_actor)`. 该文件不是 "CONFIG 实体配置" (那是 `app/models/config.py` / `app/services/config_*`), 而是 **actor 安全模块** (承载 `current_actor()` 依赖 + `role_from_payload` JWT 解析, 每次认证请求触发). 当前 actor 解析用 `payload.get("role", "DESIGNER")` 静默降级——production 必须 fail-closed.

   ```python
   role = payload.get("role")
   if not role:
       if settings.is_production:
           raise PcsError(code="MISSING_ROLE", message="JWT missing 'role' claim", status=401)
       role = "DESIGNER"  # dev mode fallback (mock 友好)
   if role not in ALLOWED_ROLES:  # {"DESIGNER", "PROCESS_CONTROLLER", "REVIEWER", "APPROVER", "SYSTEM_ADMIN"}
       raise PcsError(code="INVALID_ROLE", message=f"role {role!r} not allowed", status=403)
   ```
   **dev mode 保留 DESIGNER fallback** (mock 友好). 切分条件 = `settings.is_production` (与 LDAP 改动 2 一致).

   **与 A 改动 3 JWT iss/aud 的边界**: jwt_issuer / jwt_audience 用 config-driven (Issue 1 校准); role fallback 用 is_production 切分 (本改). 两者切分语义不同: JWT iss/aud 是 claim 配置, role fallback 是 环境标志.

2. `app/services/ldap_client.py:106` — 同样逻辑:
   ```python
   def resolve_role(groups: list[str]) -> str:
       for group in groups:
           role = settings.ldap_group_role_map.get(group)
           if role:
               return role
       if settings.is_production:
           raise LdapAuthError("no role mapping for LDAP groups in production")
       return "DESIGNER"  # dev mode fallback
   ```

3. **JWT iss/aud 校验** (Issue 1 校准: config-driven 对称) — `core/security.py:decode_token()` + `create_access_token()`:
   ```python
   # core/config.py — 加 jwt_issuer / jwt_audience 配置
   class Settings(BaseSettings):
       jwt_issuer: str | None = None      # production: "pcs-auth"; dev/test: None
       jwt_audience: str | None = None    # production: "pcs-api"; dev/test: None

   # core/security.py create_access_token (对称写入)
   def create_access_token(*, subject, role, extra=None):
       settings = get_settings()  # 显式获取 (与 decode_token 一致, 避免隐式模块级)
       payload = {"sub": subject, "role": role, "iat": ..., "exp": ...}
       if settings.jwt_issuer:
           payload["iss"] = settings.jwt_issuer
       if settings.jwt_audience:
           payload["aud"] = settings.jwt_audience
       return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)

   # core/security.py decode_token (config-driven 校验, 4 象限对称)
   def decode_token(token: str) -> dict:
       settings = get_settings()
       # require 按各自配置独立判断 (4 象限对称):
       # - jwt_issuer=None + jwt_audience=None: 不要求 iss/aud
       # - jwt_issuer 有: 要求 iss, jwt.decode(issuer=...) 也校验
       # - jwt_audience 有: 要求 aud, jwt.decode(audience=...) 也校验
       # 避免"配 issuer 不配 audience"的 4 象限不对称 (create 写 iss / decode 拒 aud)
       required = ["exp", "iat", "sub"]
       if settings.jwt_issuer:
           required.append("iss")
       if settings.jwt_audience:
           required.append("aud")
       # PyJWT: None 时自动跳过 iss/aud 校验 (无需 if/else 包装)
       return jwt.decode(
           token, settings.secret_key, algorithms=[ALGORITHM],
           issuer=settings.jwt_issuer,
           audience=settings.jwt_audience,
           options={"require": required},
       )
       # 注意: "role" 不在 require 里. role claim 存在性 + 语义由 A 改动 1 处理
       # (actor 安全模块). decode_token 只保证 token 签名 + 时效 + iss/aud.
   ```
   **关键**: 配置 jwt_issuer/audience 才写+校验; 未配置则既不写也不校验. 现有 fixture 走 dev 路径零影响. **职责分离**: decode_token 保证 token 层 (签名/时效/iss/aud); role 语义 (存在性/白名单) 由 A 改动 1 处理.

   **app/api/v1/mock_auth.py:66** (源-verify 后无需改 — 仅是 caller):
   ```python
   # pcs-backend/app/api/v1/mock_auth.py (line 66)
   return MockLoginResponse(
       access_token=create_access_token(subject=body.username, role=role),  # ← 仅调用
       ...
   )
   ```
   **source-verify**: `grep -rn "def create_access_token" pcs-backend/app/` → 唯一定义在 `app/core/security.py:44`. mock_auth.py:66 + auth.py:239 都是 **caller**, **不重复写入**. 改 core/security.py 一处即覆盖所有 caller (DRY).

   **app/api/v1/auth.py:239** (源-verify 后无需改 — 同样是 caller):
   ```python
   # pcs-backend/app/api/v1/auth.py (line 239, /refresh endpoint)
   return RefreshResponse(
       access_token=create_access_token(subject=sub, role=role),  # ← 仅调用
       refresh_token=create_refresh_token(subject=sub, role=role),
   )
   ```

4. **测试** (`tests/test_auth.py` 或新 `tests/test_jwt_production.py`):
   - `test_jwt_missing_role_in_production_401`
   - `test_jwt_missing_role_in_development_default_designer` (preserved dev friendly)
   - `test_jwt_invalid_role_in_production_403`
   - `test_jwt_iss_aud_required_in_production`
   - `test_jwt_iss_aud_not_required_in_development`
   - `test_ldap_no_role_mapping_production_raises`
   - `test_ldap_no_role_mapping_development_defaults_designer`

**关键约束**: mock-login 双重保险 **不动** (main.py:92-95 + mock_auth.py:51 已 protect).

### B. F-P3-003 Workspace Archive API

**文件**: `pcs-backend/app/models/enums.py`, `pcs-backend/app/models/project.py`, 新 `pcs-backend/alembic/versions/p7_s3_001_workspace_status.py`, 新端点 `pcs-backend/app/api/v1/workspaces.py` PATCH 段

**改动**:

1. **enum**: `app/models/enums.py` 加 `WorkspaceStatus(str, enum.Enum)`:
   ```python
   class WorkspaceStatus(str, enum.Enum):
       ACTIVE = "ACTIVE"
       ARCHIVED = "ARCHIVED"
   ```
   **不新增** `ProjectStatus` enum 类 (Issue 2 校准: 仅 workspace 落地 status, Project 维持 ACTIVE default + docstring 修正).

2. **model** `app/models/project.py:Workspace` 加 `status` 列:
   ```python
   status: Mapped[str] = mapped_column(String(20), nullable=False, default=WorkspaceStatus.ACTIVE.value, index=True)
   ```

   **Project 状态**: source-verify `grep "status.*mapped_column" app/models/project.py` 已确认 line 70: `status: Mapped[str] = mapped_column(String(20), default="ACTIVE")` — Project 已有 status 列, 仅 ACTIVE default. **不修改** Project.status (Issue 2 校准); 仅 docstring 修正 (见改动 5).

3. **migration** `p7_s3_001_workspace_status.py`:
   ```python
   revision = "p7_s3_001"
   # source-verify (2026-10-02): git log --all -- pcs-backend/alembic/versions/p7_s2_002_workspace_fk_restrict.py
   # → commit 498b8e7 "fix(p7-s2): F-P3-003 workspace FK CASCADE → RESTRICT"
   # → uv run alembic -c alembic.ini heads → p7_s2_002 (主分支 head, p3.2-sim 另一分支)
   # PCS Sprint 3 down_revision 选 p7_s2_002 (主分支 head).
   down_revision = "p7_s2_002"
   def upgrade():
       # 注意: alembic op.add_column 不接受 index=True 参数 (ORM 层 index=True 才生效)
       # 索引必须显式 op.create_index
       # if_not_exists=True: alembic 1.7+ 支持 (PCS 当前 1.19.1, ✅)
       op.add_column(
           "workspaces",
           sa.Column("status", sa.String(20), nullable=False, server_default="ACTIVE"),
       )
       op.create_index(
           "ix_workspaces_status", "workspaces", ["status"], if_not_exists=True,
       )
       # Project.status 已存在 (line 70), 不操作 projects 表
   ```
   注: ORM 模型 (`mapped_column(..., index=True)`) 与 alembic migration (`op.create_index(...)`) 是两层: ORM 用于 `Base.metadata.create_all()`, alembic 用于运行时迁移. 本批改 alembic 层. alembic 版本需求 ≥ 1.7 (source-verify `uv run alembic --version` → 1.19.1, pyproject.toml 声明 ≥ 1.13, uv 已解析 1.19.1).

4. **API endpoint** `app/api/v1/workspaces.py` 加 PATCH:
   ```python
   from sqlalchemy import text  # 文件顶部 import

   @router.patch("/{workspace_id}/archive", response_model=WorkspaceResponse)
   async def archive_workspace(
       workspace_id: uuid.UUID,
       db: Annotated[AsyncSession, Depends(get_db)],
       user: Annotated[_Actor, Depends(current_actor)],
   ) -> WorkspaceResponse:
       """归档 workspace (不删, 仅改 status='ARCHIVED').

       ACL: SYSTEM_ADMIN. archive 后 FK RESTRICT 允许显式删 (但当前无 DELETE 端点).

       D2 2A 模式: 同 workspace_id 串行 archive (advisory lock), 防并发竞态.
       """
       require_roles(user, "SYSTEM_ADMIN")
       # advisory_xact_lock 事务级, 事务结束自动释放
       await db.execute(
           text("SELECT pg_advisory_xact_lock(hashtext(:key))"),
           {"key": f"workspace_archive::{workspace_id}"},
       )
       record = (await db.execute(select(Workspace).where(Workspace.workspace_id == workspace_id))).scalar_one_or_none()
       if record is None:
           raise HTTPException(404, "Workspace not found")
       if record.status == WorkspaceStatus.ARCHIVED.value:
           # 幂等返回 (避免 409 误判)
           return WorkspaceResponse.model_validate(record, from_attributes=True)
       record.status = WorkspaceStatus.ARCHIVED.value
       await db.commit()
       return WorkspaceResponse.model_validate(record, from_attributes=True)
   ```

   **D2 2A 模式依据**: PCS 已用 advisory lock (advisory_lock.py) 防止并发状态转移. workspace archive 走相同模式, 与 `sync_from_source.actor` 一致.

5. **Project 修正** (与 Issue 2 校准):
   - **不新增** `ProjectStatus` enum 类
   - `Project.status` 列保留现状 (line 70 已 default="ACTIVE", 无 ARCHIVED 列值落地) — source-verify 已确认
   - 修改 `Project` docstring: 删除 "5 态 ACTIVE/ARCHIVED/IN_PROGRESS/CLOSED" 描述, 改为 "**当前仅 ACTIVE; ARCHIVED / IN_PROGRESS / CLOSED 等 5-state 设计待业务需求驱动落地 (登记 P7-6B follow-up)**". 删除"见 docstring 历史"——不可达, git history 才是归档。
   - 登记 R=1 变体到 `.wolf/cerebrum.md`: "docstring 未落地描述需标注"

6. **测试** `tests/test_workspace.py` (已存在):
   - `test_archive_workspace_success` (ACTIVE → ARCHIVED)
   - `test_archive_workspace_requires_admin_403` (非 SYSTEM_ADMIN)
   - `test_archive_workspace_not_found_404` (workspace 不存在)
   - `test_archive_workspace_idempotent_200` (重复归档 → 幂等返回 200, 不报 409)
   - `test_archive_then_fk_restrict_allows_delete` (新行为: archive 后 FK RESTRICT 仍生效, 但当前无 DELETE 端点 — 此测试在 DELETE 端点引入后落地)
   - **并发测试 defer**: workspace archive 已加 D2 2A advisory lock (改动 4), 并发竞态在实现层解决; 单元测试覆盖幂等性足够, 真并发 (两请求同毫秒) defer 到后续 stress test.

### C. F-P2-009 Audit Query 后端 (拆分点)

**文件**: 新 `pcs-backend/app/schemas/audit.py`, 新 `pcs-backend/app/api/v1/audit.py`

**改动**:

1. **Pydantic schemas** 新文件:
   ```python
   class AuditLogResponse(BaseModel):
       audit_id: uuid.UUID
       user_id: uuid.UUID | None
       action: str
       resource_type: str | None
       resource_id: str | None
       detail_json: dict | None
       occurred_at: datetime

   class AuditLogListResponse(BaseModel):
       items: list[AuditLogResponse]
       total: int
       limit: int
       offset: int

   class EquipmentDeletionAuditResponse(BaseModel):
       audit_id: uuid.UUID
       equipment_id: uuid.UUID
       project_id: uuid.UUID
       workspace_id: uuid.UUID
       equipment_tag: str
       deleted_by: uuid.UUID
       orphan_records: dict
       occurred_at: datetime
       reason: str | None

   class EquipmentDeletionAuditListResponse(BaseModel):
       items: list[EquipmentDeletionAuditResponse]
       total: int
       limit: int
       offset: int
   ```

2. **API endpoints** 新 `app/api/v1/audit.py` (混合 RBAC 方案):
   ```python
   # /audit-logs — 通用 audit (audit_logs 表无 project_id 列), 限 SYSTEM_ADMIN
   # source-verify: grep "class AuditLog" app/models/system.py — 表列只有 audit_id, action,
   # resource_type, resource_id, ip, user_agent, request_id, detail_json, occurred_at, user_id
   # 无 project_id 列. 选项 a (加列) 估时 ~1.0 人天 (含 audit_service.write 写入侧改造)
   # 选项 b (关联查询) 维护成本随资源类型增长. 选项 c 收窄 RBAC — 选 c.
   @router.get("/audit-logs", response_model=AuditLogListResponse)
   async def list_audit_logs(
       db, user,
       resource_type: str | None = Query(None, max_length=50),
       resource_id: str | None = Query(None, max_length=100),
       user_id: uuid.UUID | None = Query(None),
       action: str | None = Query(None, max_length=50),
       occurred_after: datetime | None = Query(None),
       occurred_before: datetime | None = Query(None),
       limit: int = Query(50, ge=1, le=200),
       offset: int = Query(0, ge=0),
   ) -> AuditLogListResponse:
       """Audit logs 通用查询. SYSTEM_ADMIN only (F-P0-004 收窄).

       F-P0-001 R1 签署痕迹: 走 GET /config-audit (独立端点, 限 DESIGNER+);
       或 admin 代查 (R1 签字确认书 docs/PCS-SIGN-F-P0-001-2026-10-08-R1.md 已足够追溯).
       """
       require_roles(user, "SYSTEM_ADMIN")  # 收窄到 admin
       conditions = []
       # 9-dim filter (无 project filter — 该表无 project_id 列)
       if resource_type: conditions.append(AuditLog.resource_type == resource_type)
       if resource_id: conditions.append(AuditLog.resource_id == resource_id)
       if user_id: conditions.append(AuditLog.user_id == user_id)
       if action: conditions.append(AuditLog.action == action)
       if occurred_after: conditions.append(AuditLog.occurred_at >= occurred_after)
       if occurred_before: conditions.append(AuditLog.occurred_at < occurred_before)
       where_clause = and_(*conditions) if conditions else None
       total = (await db.execute(select(func.count()).select_from(AuditLog).where(where_clause))).scalar_one()
       items = (await db.execute(
           select(AuditLog).where(where_clause)
           .order_by(AuditLog.occurred_at.desc())
           .limit(limit).offset(offset)
       )).scalars().all()
       return AuditLogListResponse(
           items=[AuditLogResponse.model_validate(r, from_attributes=True) for r in items],
           total=total, limit=limit, offset=offset,
       )

   # /equipment-deletion-audit — 该表有 project_id 列, DESIGNER+ 可查 (RBAC 限制)
   @router.get("/equipment-deletion-audit", response_model=EquipmentDeletionAuditListResponse)
   async def list_equipment_deletion_audit(
       db, user,
       project_id: uuid.UUID | None = Query(None),  # F-P0-004 IDOR 防护
       workspace_id: uuid.UUID | None = Query(None),
       equipment_id: uuid.UUID | None = Query(None),
       deleted_by: uuid.UUID | None = Query(None),
       occurred_after: datetime | None = Query(None),
       occurred_before: datetime | None = Query(None),
       limit: int = Query(50, ge=1, le=200),
       offset: int = Query(0, ge=0),
   ) -> EquipmentDeletionAuditListResponse:
       """设备删除 audit 查询 (F-P0-004 IDOR 防护 — 该表有 project_id).

       非 SYSTEM_ADMIN 强制 project 隔离.
       """
       require_roles(user, "DESIGNER", "PROCESS_CONTROLLER", "REVIEWER", "APPROVER", "SYSTEM_ADMIN")
       conditions = []
       # F-P0-004: project 隔离 (use .role 单数, source-verify _Actor 有 .role + .roles 两者)
       if user.role != "SYSTEM_ADMIN":
           if not project_id:
               raise HTTPException(403, "project_id required for non-system-admin")
           conditions.append(EquipmentDeletionAudit.project_id == project_id)
       elif project_id:
           conditions.append(EquipmentDeletionAudit.project_id == project_id)
       # 其他 filter
       if workspace_id: conditions.append(EquipmentDeletionAudit.workspace_id == workspace_id)
       if equipment_id: conditions.append(EquipmentDeletionAudit.equipment_id == equipment_id)
       if deleted_by: conditions.append(EquipmentDeletionAudit.deleted_by == deleted_by)
       if occurred_after: conditions.append(EquipmentDeletionAudit.occurred_at >= occurred_after)
       if occurred_before: conditions.append(EquipmentDeletionAudit.occurred_at < occurred_before)
       where_clause = and_(*conditions) if conditions else None
       total = (await db.execute(select(func.count()).select_from(EquipmentDeletionAudit).where(where_clause))).scalar_one()
       items = (await db.execute(
           select(EquipmentDeletionAudit).where(where_clause)
           .order_by(EquipmentDeletionAudit.occurred_at.desc())
           .limit(limit).offset(offset)
       )).scalars().all()
       return EquipmentDeletionAuditListResponse(
           items=[EquipmentDeletionAuditResponse.model_validate(r, from_attributes=True) for r in items],
           total=total, limit=limit, offset=offset,
       )

   # /config-audit — F-P0-001 R1 签署痕迹独立端点 (DESIGNER+)
   # source-verify 2026-10-03:
   # - resource_type 实际值是 "config_energy_conversion_factors" (与 ConfigEnergyConversionFactor.__tablename__ 一致)
   # - ConfigEnergyConversionFactor 是公司级全局元数据 (无 project_id / workspace_id 列)
   # - resource_id 类型 BIGINT (audit_logs.resource_id String(100), 需 str() 转换)
   # - F-P0-004 IDOR 不适用 (非 project-scoped, 全公司同系数)
   # 与 /equipment-deletion-audit 模式不同: 走 audit_logs 直接按 resource_type 过滤,
   # 无需关联子表 (该表本身无 project_id 列).
   @router.get("/config-audit", response_model=AuditLogListResponse)
   async def list_config_audit(
       db, user,
       asset_id: int | None = Query(None, ge=1, description="ConfigEnergyConversionFactor.id (BIGINT)"),
       occurred_after: datetime | None = Query(None),
       occurred_before: datetime | None = Query(None),
       limit: int = Query(50, ge=1, le=200),
       offset: int = Query(0, ge=0),
   ) -> AuditLogListResponse:
       """F-P0-001 R1 签署痕迹独立端点 (DESIGNER+, 全公司可查).

       业务: 工艺室 / 设计 / 审查 / 审批可查 ConfigEnergyConversionFactor 全量 audit.
       F-P0-001 R1 修订 trace 是其中一类 action=CONFIG_R1_BACKFILL / R1_REVISION.

       resource_type='config_energy_conversion_factors' 的 audit 历史.
       包括: 表格编辑、审批、发布、折标系数 R1 修订 (action=CONFIG_R1_BACKFILL).
       """
       require_roles(user, "DESIGNER", "PROCESS_CONTROLLER", "REVIEWER", "APPROVER", "SYSTEM_ADMIN")
       conditions = [AuditLog.resource_type == "config_energy_conversion_factors"]
       # 单一条件过滤 — 无 project 隔离 (公司级元数据)
       if asset_id is not None:
           conditions.append(AuditLog.resource_id == str(asset_id))
       # 日期 filter
       if occurred_after: conditions.append(AuditLog.occurred_at >= occurred_after)
       if occurred_before: conditions.append(AuditLog.occurred_at < occurred_before)
       where_clause = and_(*conditions)
       total = (await db.execute(select(func.count()).select_from(AuditLog).where(where_clause))).scalar_one()
       items = (await db.execute(
           select(AuditLog).where(where_clause)
           .order_by(AuditLog.occurred_at.desc())
           .limit(limit).offset(offset)
       )).scalars().all()
       return AuditLogListResponse(
           items=[AuditLogResponse.model_validate(r, from_attributes=True) for r in items],
           total=total, limit=limit, offset=offset,
       )

   # rate limit 决策: **无限流** (三个端点都适用).
   # - 理由 1: limit≤200 已限单次成本 (issue 5 错误路径)
   # - 理由 2: audit query 是低频 admin 工具 (R1 签署痕迹查询, 系统管理员/工艺室)
   # - 理由 3: F-P2-006 限流 (5/min/user) 是针对 /energy-summary/aggregate
   #      这类高频写路径, 不适用于低频读路径
   # 替代安全措施: 9-dim filter + RBAC (按端点收窄) + 复合索引 + limit≤200 + F-P0-004 project 隔离
   ```

3. **router 注册** `app/api/v1/__init__.py` 加 `audit_router`.

4. **测试** 新 `tests/api/v1/test_audit_query.py`:
   - `test_list_audit_logs_paginated`
   - `test_list_audit_logs_filter_resource_type_config_energy_conversion_factors` (F-P0-001 R1 增量)
   - `test_list_audit_logs_filter_user_id`
   - `test_list_audit_logs_filter_date_range`
   - `test_list_audit_logs_requires_auth`
   - `test_list_equipment_deletion_audit_filter_project`
   - `test_list_equipment_deletion_audit_filter_equipment`

**F-P0-001 R1 增量验证**: 用 `resource_type=config_energy_conversion_factors` 过滤应能拉出 **backfill 脚本产生的 audit 记录 (actor=SYSTEM, reason="F-P0-001 R1 backfill")**. **不是** commit 3f89733 的 CONFIG seed (原 seed 走 `db.add(...)` 不经 service, 无 audit 记录).

**Pydantic schema 定义顺序** (校准 Issue 5):
1. 先 `source-verify` AuditLog + EquipmentDeletionAudit 表列 (per前提 3 已确认: 9 列 / 9 列, 全部对齐)
2. 再定义 Pydantic schema (确保字段名/类型对齐)
3. 定义后 endpoints 必须有 Pydantic ORM 模型验证 (`from_attributes=True`)
4. 测试先写, 实现后改 (TDD)

---

## 批次 2 (~1 人天, frontend 人可用性待确认)

### C 前端. Audit Viewer 页

**文件**: 新 `pcs-frontend/src/pages/audit/AuditLogPage.tsx`, 新 `pcs-frontend/src/api/audit.ts`, 新 `pcs-frontend/src/mocks/handlers.ts` 加 MSW

**改动**:

1. **API client** 新 `api/audit.ts`:
   ```typescript
   export const auditApi = {
     listAuditLogs: (params: ListAuditLogsParams) =>
       api.get<AuditLogListResponse>('/audit-logs', { params }).then(r => r.data),
     listEquipmentDeletionAudit: (params: ListEquipmentDeletionAuditParams) =>
       api.get<EquipmentDeletionAuditListResponse>('/equipment-deletion-audit', { params }).then(r => r.data),
   };
   ```

2. **MSW handlers** 增 `src/mocks/handlers.ts`:
   - GET /audit-logs → 返回 5 条 seed (含 1 条 resource_type=config_energy_conversion_factors)
   - GET /equipment-deletion-audit → 返回 2 条 seed

3. **Page** `AuditLogPage.tsx`: antd Table + Filter form (resource_type select + date range), 进入默认查最近 7 天.

4. **Route** `router.tsx` 加 `/audit-logs` 路由 + nav menu 入口.

5. **测试** `tests/pages/audit/AuditLogPage.test.tsx` (vitest + MSW) - 渲染/筛选/翻页.

### D. P7-6B Playwright e2e 补 case

**文件**: 新 `pcs-frontend/e2e/fixtures.ts`, 新 `pcs-frontend/e2e/equipment_list.spec.ts`, 新 `pcs-frontend/e2e/audit_log.spec.ts`

**改动**:

1. **共享 fixtures** `e2e/fixtures.ts`:
   ```typescript
   export const test = base.extend({
     loggedInPage: async ({ page }, use) => {
       // 复用 cooling_water.spec.ts 的 4-step auth dance, 提取到 fixture
     },
   });
   ```
   现有 2 specs 重构为用 `loggedInPage`.

2. **equipment_list e2e** `e2e/equipment_list.spec.ts`:
   - route reach + 列表渲染
   - 删除按钮可见 (admin only)
   - 删除确认 modal → 调用 audit log
   - 401/403 error path

3. **audit_log e2e** `e2e/audit_log.spec.ts`:
   - 访问 /audit-logs
   - filter by resource_type=config_energy_conversion_factors
   - filter by date range
   - 翻页

4. **error-path 覆盖** 各 spec 加 401/403/422 测试 case.

---

## 关键文件清单

### 后端 (批次 1)
- `pcs-backend/app/api/v1/config.py:460` (role fallback)
- `pcs-backend/app/services/ldap_client.py:106` (LDAP role fallback)
- `pcs-backend/app/core/security.py` (decode_token iss/aud)
- `pcs-backend/app/core/config.py` (Settings: jwt_issuer, jwt_audience)
- `pcs-backend/app/models/enums.py` (WorkspaceStatus enum only)
- `pcs-backend/app/models/project.py` (Workspace.status only; Project docstring 修正)
- 新 `pcs-backend/alembic/versions/p7_s3_001_workspace_status.py`
- `pcs-backend/app/api/v1/workspaces.py` (PATCH archive)
- 新 `pcs-backend/app/schemas/audit.py`
- 新 `pcs-backend/app/api/v1/audit.py`
- `pcs-backend/app/api/v1/__init__.py` (router 注册)
- 测试: `tests/test_auth.py`, `tests/test_workspace.py`, 新 `tests/api/v1/test_audit_query.py`

### 前端 (批次 2)
- 新 `pcs-frontend/src/api/audit.ts`
- `pcs-frontend/src/mocks/handlers.ts` (新增 MSW)
- 新 `pcs-frontend/src/pages/audit/AuditLogPage.tsx`
- `pcs-frontend/src/router.tsx` (新路由)
- `pcs-frontend/src/components/AppLayout.tsx` (nav menu)
- 新 `pcs-frontend/e2e/fixtures.ts`
- 新 `pcs-frontend/e2e/equipment_list.spec.ts`
- 新 `pcs-frontend/e2e/audit_log.spec.ts`

---

## 验证 (Verification)

### 批次 1
```bash
cd pcs-backend
uv run pytest tests/test_auth.py tests/test_workspace.py tests/api/v1/test_audit_query.py -q
uv run pytest tests/ -q  # 全量回归
set -a; source .env.test; set +a
uv run alembic upgrade head  # pcs_test DB 同步
./scripts/check_migration_idempotency.py  # p7_s3_* 通过
```

### 批次 2
```bash
cd pcs-frontend
npm run typecheck
npm run api:gen  # 重生成
bash scripts/check-api-drift.sh  # 漂移检测
npx playwright test e2e/equipment_list.spec.ts e2e/audit_log.spec.ts
```

### Production 前置验证 (A 核心)
```python
# 单元测试: prod mode fail-closed, dev mode preserves fallback
test_jwt_missing_role_in_production_401
test_jwt_missing_role_in_development_default_designer
```

### F-P0-001 R1 audit 增量验证
```python
# 工艺室 CONFIG R1 修订痕迹可查询 — backfill 后
GET /api/v1/config-audit?asset_id=<ConfigEnergyConversionFactor.id>
# 期望返回: backfill 脚本产生的 audit 记录 (resource_type=config_energy_conversion_factors, actor=SYSTEM, reason="F-P0-001 R1 backfill")
# 权限: DESIGNER+ (工艺室可查自己 project, 不需 admin)
# NOT: /audit-logs (限 SYSTEM_ADMIN) — RBAC 已收窄
# NOT: commit 3f89733 的 CONFIG seed (原 seed 不经 service, 无 audit 记录)
```

---

## 风险 + 缓解

| 风险 | 等级 | 缓解 |
|------|------|------|
| A 改 JWT 校验影响 mock-login | 中 | mock-login 双重保险不动 (main.py:92-95 + mock_auth.py:51); A 只修 production 路径 |
| B migration 加列需 down_revision | 低 | down_revision="p7_s2_002"; if_exists=True 兜底 |
| C 后端 API 与 audit 表 schema 偏离 | 低 | source-verify audit_logs/equipment_deletion_audit schema 后定义 Pydantic |
| C 前端 viewer 阻塞批次 2 | 中 | frontend 人可用性先确认; 不可用则 defer 到 Sprint 3b |
| D 的 error-path 覆盖需 fixtures | 低 | fixtures.ts 与 MSW handler 同步设计 |

---

## 关联引用

- **Do-Not-Repeat**: 复用已有模式:
  - `tests/conftest.py:86-115` SQLite + gen_random_uuid 处理
  - `tests/conftest.py:195-232` client fixture + UserProject monkeypatch
  - `pcs-backend/alembic/versions/p1_sprint3_equipment_status_columns.py:38-106` 状态列 migration 模板
  - `pcs-backend/app/api/v1/sim_imports_query.py:200-243` 9-dim filter 模板
  - `pcs-frontend/e2e/cooling_water.spec.ts:15-27` 4-step auth dance (提取到 fixtures.ts)
- **已存在的功能不重做**: 
  - `pcs-backend/app/services/audit_service.py:write` (write 路径已完整)
  - `pcs-backend/app/main.py:41-46` mock-login prod self-disable (不动)
  - `pcs-backend/app/api/v1/equip_list.py:141-231` DELETE endpoint (写路径已完整, 只补 query)
- **buglog**: 登记 F-P3-001 production hardening, 防止后续 sprint 漏掉.

---

## GSTACK REVIEW REPORT

| Review | Trigger | Why | Runs | Status | Findings |
|--------|---------|-----|------|--------|-------|
| Eng Review | `/plan-eng-review` | Architecture, tests (required) | 1 | issues_open | 6 issues, 1 critical gap (Issue 6) |
| CEO Review | — | — | 0 | — | not run |
| Design Review | — | — | 0 | — | not run |
| Codex Review | — | — | 0 | — | not run |
| DX Review | — | — | 0 | — | not run |
| Outside Voice | — | independent 2nd opinion | 0 | skipped | Codex unavailable; user provided independent critiques during review |

**Issues Found (eng review):**

| # | Severity | Confidence | Title | Resolution |
|---|----------|-----------|-------|------------|
| 1 | HIGH | 9/10 | JWT iss/aud 不对称 — decode 校验但 create 不写入 | Config-driven 对称: 配 iss/aud 才写+校验 |
| 2 | MEDIUM | 8/10 | ProjectStatus 5-state 超越 B 范围 | 拆出 — 只加 WorkspaceStatus(2-state); Project docstring 5-state 描述修正 |
| 3 | MEDIUM | 7/10 | 测试 fixture 连锁影响 | Config-driven 让 conftest 不动; 新增 prod-mode token fixture |
| 4 | MEDIUM | 8/10 | audit-logs 缺复合索引, 全表扫 | 加 3 个复合索引 (resource_type+id+time / user+time / action+time) |
| 5 | HIGH | 9/10 | 测试 19 个仅覆盖 happy path | 加错误路径 + limit 边界 + 1 深分页 (limit=1000 + offset=9000); 并发测试 defer (B 改动 4 已加 D2 2A advisory lock, 并发竞态在实现层解决) |
| 6 | HIGH | 9/10 | F-P0-001 R1 增量 source-verify fail — seed 脚本不写 audit_logs, GET /audit-logs?resource_type=config_energy_conversion_factors 返回空 | 加 backfill 脚本走 ConfigAssetService 触发 audit; actor=SYSTEM 角色; 估时 +0.5 人天 |
| 7 | HIGH | 10/10 | F-P0-004 IDOR 继承 — audit query 无 project 过滤, DESIGNER 可查所有项目 audit; audit_logs 表无 project_id 列 (source-verify). **进一步 source-verify (2026-10-03): ConfigEnergyConversionFactor 也是公司级全局 (无 project_id), F-P0-004 IDOR 不适用 /config-audit** | 混合 RBAC: /audit-logs 限 SYSTEM_ADMIN (全表无 project_id); /equipment-deletion-audit DESIGNER+ + project_id filter (该表有 project_id); /config-audit DESIGNER+ + 单一 resource_type 过滤 (公司级元数据, 不需 project 隔离); resource_type=config_energy_conversion_factors (source-verify 校准, 原 config_asset 错误); +0.2 人天 |

**Outside Voice: skipped** — Codex unavailable, Claude subagent would rehash user's own challenges in this session (Issue 1-6 each had detailed engagement from outside reviewer via user feedback).

**Cross-Model Tension: none** — single reviewer with full-mode engagement.

---

## Review-Driven Plan Updates

### Issue 1 (A: JWT iss/aud config-driven 对称)

**config-driven 方案**:
```python
# core/config.py
class Settings(BaseSettings):
    jwt_issuer: str | None = None      # production: "pcs-auth"
    jwt_audience: str | None = None    # production: "pcs-api"
    # dev/test: 两者为 None

# core/security.py create_access_token
if settings.jwt_issuer:
    payload["iss"] = settings.jwt_issuer
if settings.jwt_audience:
    payload["aud"] = settings.jwt_audience

# decode_token
verify_iss/aud = bool(settings.jwt_issuer)
```

**修改文件** (Issue 1, source-verify 后):
- `core/config.py` — 加 jwt_issuer / jwt_audience 配置
- `app/core/security.py:44` — create_access_token 对称写入 (**唯一定义点**, 覆盖所有 caller)
- `app/core/security.py:decode_token` — 校验 iss/aud
- **auth.py:239 + mock_auth.py:66 — source-verify 后确认是 caller, 无需改** (DRY: 改 core/security.py:44 一处即覆盖)

**mock-login 双重保险不动** (main.py:92-95 + mock_auth.py:51). 这是不同层面的代码.

### Issue 2 (B: ProjectStatus 5-state 拆出)

- B 仅加 `WorkspaceStatus(str, enum.Enum)` (ACTIVE / ARCHIVED, 2-state)
- `Project.status` 列保留现状 (仅 ACTIVE)
- `Project` docstring 修正: 删除 "5 态 ACTIVE/ARCHIVED/IN_PROGRESS/..." 描述, 改为 "当前仅 ACTIVE; 5-state 待业务需求"
- 登记 R=1 变体到 `.wolf/cerebrum.md`: docstring 未落地描述需标注

### Issue 3 (A: 测试 fixture 不动)

**现有 fixture 零改动**:
- config-driven 方案下 dev/test 环境 jwt_issuer=None → create 不写 → decode 不校验
- conftest.py:467-481 sample_user_token 走 create_access_token, dev 路径零影响

**新增 prod-mode 测试专用 fixture** (局部):
```python
@pytest.fixture
def prod_mode_settings(monkeypatch):
    monkeypatch.setattr(settings, "jwt_issuer", "pcs-auth")
    monkeypatch.setattr(settings, "jwt_audience", "pcs-api")
    yield

def test_token_has_iss_aud_in_prod(prod_mode_settings):
    token = create_access_token(...)
    payload = jwt.decode(token, options={"verify_signature": False})
    assert payload["iss"] == "pcs-auth"
    assert payload["aud"] == "pcs-api"
```

### Issue 4 (C: audit-logs 复合索引)

**新增 migration** `p7_s3_002_audit_logs_composite_indexes.py`:

| # | 索引 | 覆盖查询 |
|---|------|---------|
| 1 | `(resource_type, resource_id, occurred_at DESC)` | GET /equipment-deletion-audit?equipment_id=X; GET /audit-logs?resource_type=X&resource_id=Y |
| 2 | `(user_id, occurred_at DESC)` | GET /audit-logs?user_id=X |
| 3 | `(action, occurred_at DESC)` | GET /audit-logs?action=X (升级现有单列 ix_audit_logs_action) |

**`if_not_exists=True`** (F-P3-002 教训).

### Issue 5 (C: 测试错误路径 + limit 边界)

**新增测试** (`tests/api/v1/test_audit_query.py` + D e2e):

| 测试 | 期望 |
|------|------|
| 无 token 访问 | 401 |
| 跨 workspace 用户 | 403 |
| resource_type=invalid | 422 |
| from > to | 422 |
| limit=0 | 422 |
| limit>1000 | 422 |
| limit=1000 (边界) + offset=9000 | 200 (深分页) |
| workspace 不存在 | 404 |
| 重复归档 | **200 (幂等返回, 不报 409)** — B 改动 4 已裁决幂等 |
| /audit-logs DESIGNER 访问 | **403** (Issue 7 收窄 RBAC: 仅 SYSTEM_ADMIN) |
| /audit-logs SYSTEM_ADMIN 访问 | 200 |
| /equipment-deletion-audit DESIGNER + 自己 project | 200 |
| /equipment-deletion-audit DESIGNER + 他人 project | 200 + 空 items (F-P0-004 IDOR) |
| /config-audit DESIGNER + 任意 asset_id | 200 + R1 签署痕迹 (公司级全局, 无 project 隔离) |
| /config-audit asset_id=不存在 | 200 + 空 items |

**并发测试 defer**: workspace archive 已加 D2 2A advisory lock (B 改动 4), 并发竞态在实现层解决; 单元测试覆盖幂等性 (重复归档返回 200) 即可, 真并发 (两请求同毫秒) defer 到后续 stress test 阶段.

### Issue 6 (F-P0-001 R1 audit backfill)

**新增 backfill 脚本** `pcs-backend/scripts/p7_s3_003_backfill_config_audit.py`:
- 走 ConfigEnergyConversionFactorService.create / update 路径触发 audit
- resource_type = `"config_energy_conversion_factors"` (与 ConfigEnergyConversionFactor.__tablename__ 一致, source-verify 2026-10-03)
- resource_id = `str(ConfigEnergyConversionFactor.id)` (BIGINT → String(100))
- actor_user_id = SYSTEM_USER_ID (UUID ...0001)
- actor_role = SYSTEM
- 含 service 权限矩阵评审 (~0.1 人天)
- 测试 (backfill 验证 + audit 查询 R1 seed 可查)

**不修改原 seed 脚本** (`p7_open_012_t5_r1_verification.py`):
- seed 是数据初始化, 不应承担 audit 责任
- 未来 CONFIG 变更走 service 路径, audit 自动触发

---

## Final Scope (Issue-Resolved)

| 批次 | 项 | 工作量 | 内容 |
|------|----|--------|------|
| 批次 1 | A (config-driven iss/aud + role fail-closed + LDAP fix) | 0.5 人天 | config-driven 对称 (改 core/security.py:44 一处, 覆盖所有 caller) |
| 批次 1 | B (workspace archive, 2-state + advisory lock) | 0.7 人天 | WorkspaceStatus 2-state; D2 2A advisory lock; Project docstring 修正; idempotent 幂等返回 |
| 批次 1 | C 后端 (audit query + 3 indexes + error path tests + Issue 7 /config-audit 独立端点) | 1.0 人天 | GET /audit-logs + /equipment-deletion-audit + /config-audit (F-P0-001 R1 痕迹) + RBAC 收窄; Pydantic schemas; p7_s3_002 复合索引; 错误路径 + limit 边界 + 深分页 + IDOR 测试 |
| 批次 1 | F-P0-001 R1 backfill | 0.5 人天 | backfill 脚本 + service 权限评审 |
| 批次 2 | C 前端 (audit viewer) | 0.5 人天 | page + API client + MSW |
| 批次 2 | D e2e 补 | 0.5 人天 | equipment-list + audit + fixtures |

**总**: **~3.7 人天** (校验: 批次 1 = A 0.5 + B 0.7 + C 后端 1.0 + backfill 0.5 = 2.7; 批次 2 = C 前端 0.5 + D 0.5 = 1.0; 合计 **3.7 人天**).

**Baseline 定义**: 原 ~2 人天 baseline 指 "用户 v0 计划原始估时" (4 项粗估 0.5/0.5/0.5/0.5). 实际展开后 baseline 应为 **2.5 人天** (A 0.5 + B 0.5 + C 后端 0.5 + 批次 2 1.0). 增量 +1.2 人天: B advisory lock +0.2, C 错误路径 +0.3, backfill +0.5 (含服务权限评审), Issue 7 /config-audit 独立端点 +0.2 (/config-audit ~0.1 + 混合 RBAC +0.05 + 4 IDOR 测试 +0.05).

**Issue 7 resource_type source-verify 校准** (2026-10-03):
- audit_logs.resource_type 实际值在 services 中: `"CONFIG"` / `"coefficient_table"` / `"workspaces"` 等
- ConfigEnergyConversionFactor 表名 `"config_energy_conversion_factors"` — backfill 脚本必须用此值 (与 __tablename__ 一致), 原 plan 中 `config_asset` 是错误的
- ConfigEnergyConversionFactor **无 project_id / workspace_id 列** (公司级全局元数据) — `/config-audit` IDOR 防护代码改为单一 resource_type 过滤, 不需关联子表

---

## NOT in Scope (deferred with rationale)

| 项 | 理由 |
|----|------|
| T6 catalyst_loading | BLOCKER-2 阻塞 (工艺室 XLS 2026-10-15 签); 待解锁 |
| 综合能耗出厂 ≤2% 验收正式封板 | 已 PASS @ 9887ad9, T6 fixture 待补 |
| ProjectStatus 5-state | Issue 2 拆出, 业务需求驱动时补 (登记 P7-6B follow-up) |
| 并发 workspace archive 测试 (真并发) | B 改动 4 已加 D2 2A advisory lock, 并发竞态在实现层解决; 单元测试覆盖幂等性足够, 真并发 (两请求同毫秒) defer 到后续 stress test |
| Frontend gstack-qa 本批 | 本次仅 backend; 批次 2 完后跑 |

---

## What Already Exists (复用，避免重做)

- `audit_service.py:write` — C 后端写入口复用
- `data_lineage_query.py:35-69` occurred_at DESC 模式
- `sim_imports_query.py:200-243` 9-dim filter 模式
- `sim_imports_query.py:200-243` 9-dim filter 模板
- `tests/test_mock_auth.py:42-50` prod-mode monkeypatch 模式
- `cooling_water.spec.ts:15-27` 4-step auth dance (提取到 fixtures.ts)
- `advisory_lock.py` — **本批 workspace archive 已用** (B 改动 4, D2 2A 模式)

---

## Failure Modes (Critical Gaps)

| 路径 | 失败场景 | 错误可见性 | 测试覆盖 |
|------|---------|-----------|---------|
| Issue 6 backfill | seed 路径不写 audit (R=1 history 不可查) | 用户查 GET /audit-logs?resource_type=config_energy_conversion_factors 返回空 | ✅ Issue 6 backfill 解决 (走 ConfigAssetService 触发 audit) |
| JWT iss/aud decode | 配置 iss/aud 但 create 不写 → 全 token 拒 | 高 (production 上线即 401 全站挂) | ✅ Issue 1 config-driven 对称 |
| audit-logs 全表扫 | resource_type+resource_id 联合查询 100k 行表 | 高 (响应慢) | ✅ Issue 4 复合索引 (3 个) |
| workspace archive 并发 | 同毫秒两个 archive 请求 | 隐式 (数据一致) | ✅ D2 2A advisory lock (本批实现) |

**Critical gaps**: 0 (Issue 6 backfill 已被裁决 + B 加 advisory lock 闭环).

---

## TODOS.md (deferred to next sprint)

| Item | Why | Action |
|------|-----|--------|
| ProjectStatus 5-state | 业务需求驱动时补 | 登记 P7-6B follow-up |
| 综合能耗出厂验收正式封板 | T6 后正式封 | T6 解锁后 |
| T6 catalyst_loading | BLOCKER-2 解锁 | 工艺室 XLS 签后 |

---

## Test Plan Artifact (供 /qa 后续使用)

**Affected Pages/Routes:**
- POST /api/v1/util/energy-summary/aggregate (F-P2-007 已加 source param — 已有, 无变更)
- DELETE /api/v1/equipment-list/{id} (F-P2-009 已落 — 已有, 无变更)
- POST /api/v1/workspaces/{id}/archive (B 新增)
- GET /api/v1/audit-logs (C 新增, SYSTEM_ADMIN only)
- GET /api/v1/equipment-deletion-audit (C 新增, DESIGNER+ + project_id filter)
- GET /api/v1/config-audit (C 新增, DESIGNER+, 公司级全局)
- /audit-logs 前端页面 (批次 2)

**Key Interactions:**
- JWT 在生产/销毁的 iss/aud 校验
- workspace archive 幂等性 (重复归档)
- audit query 过滤 (resource_type, user_id, 时间范围)
- audit-logs 深分页 (limit=1000, offset=9000)

**Edge Cases:**
- archive 不存在 workspace 角色权限
- audit query 无 token / 跨 workspace / 非法 query 参数
- backfill 后 CONFIG R1 seed 可查

**Critical Paths:**
- 完整 archive 流 (active → archived → 不删数据, 仅改状态)
- 完整 audit 流 (write → query → resource_type 过滤)
- F-P0-001 R1 CONFIG seed → backfill → audit 可查
