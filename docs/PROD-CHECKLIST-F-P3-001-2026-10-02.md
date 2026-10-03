# F-P3-001 Production 前置 Checklist

**来源**: ce-code-review 20261001-174422-16a356de F-P3-001  
**裁决**: 用户 2026-10-02 接受 advisory, 登记 production 前置  
**优先级**: ⚠️ Medium (mock-friendly intentional, production 必须修)  
**预计工作量**: 0.5 人天  
**Sprint 3 实施日期**: 2026-10-03  
**状态**: ✅ **5/5 全部完成** (#5 于 Sprint 3b 2026-10-03 收口)

---

## 问题

`pcs-backend/app/api/v1/config.py:460`:
```python
role = payload.get("role", "DESIGNER")
```

JWT 无 role 声明 → 默认 DESIGNER (最低权限). Mock 环境下友好, 但 **production 必须强制 issuer 校验 + role 必填**, 否则:
- 第三方 LDAP 配置错误 → 所有用户获得 DESIGNER 权限
- Mock token 绕过 → 不应继承到 prod
- 缺少 role allowlist 校验 → 任意字符串 role 通过

---

## Production 上线前必做 (checklist)

### 1. JWT issuer 强制校验 — ✅ DONE (Sprint 3)

**实施**: `pcs-backend/app/core/config.py` 加 `jwt_issuer` / `jwt_audience` 配置;
`core/security.py:decode_token` 用 PyJWT `issuer=` / `audience=` 参数 config-driven 校验;
`create_access_token` / `create_refresh_token` 对称写入 iss / aud claim.

```python
# 改: payload.get("role", "DESIGNER") → 必须有 role
role = payload.get("role")
if role not in ALLOWED_ROLES:  # 6 角色白名单含 VIEWER/CHECKER
    raise PcsError(code="INVALID_ROLE", message=f"role {role!r} not allowed", status=403)
```

**Commit**: `feat(p7-s3): F-P3-001 production hardening - JWT iss/aud config-driven + role fail-closed + LDAP fix`

### 2. Production 关闭 mock-login — ✅ EXISTING (不动)

- `pcs-backend/app/main.py:41-46` mock-login prod self-disable (双层保险: lifespan 检查 + mock_auth.py:51 guard)
- 通过 `settings.ENV == "production"` 检查 + 启动时移除路由
- 本批不重复修改 (carry-forward)

### 3. LDAP issuer 强校验 (production) — ✅ PARTIAL (config-driven 基础已就绪)

**实施**:
- `jwt_audience` 配置驱动校验 (Sprint 3 A.3) — 设置 `JWT_AUDIENCE=pcs-api` 即强制 aud claim 一致
- `jwt_issuer` 配置驱动校验 — 设置 `JWT_ISSUER=pcs-auth` 即强制 iss claim 一致
- 4 象限对称 (jwt.decode 在 issuer=None/audience=None 时自动跳过)

```bash
# production .env 必须设置:
JWT_ISSUER=pcs-auth
JWT_AUDIENCE=pcs-api
```

**剩余工作** (LDAP 接入 sprint 续做):
- 验证 LDAP 返回的 `iss` 声明 == 生产 LDAP issuer
- `nbf`/`exp` 严格 (默认 60min, 不允许 refresh 后超过 8h)
- 当前 Sprint 3 落地 config 基础, LDAP 接入时启用

### 4. role mapping 强校验 — ✅ DONE (Sprint 3)

**实施**: `pcs-backend/app/services/ldap_client.py:resolve_role`

```python
def resolve_role(groups: tuple[str, ...]) -> str:
    mapping = get_settings().group_role_map()
    group_cns = {_extract_cn(g) for g in groups}
    for group_cn, role in mapping.items():
        if group_cn in group_cns:
            return role
    if get_settings().is_production:
        raise LdapAuthError(
            "no role mapping for LDAP groups in production",
        )
    return "DESIGNER"  # dev mode fallback
```

- production: 找不到映射 → `LdapAuthError` 拒绝登录 (fail-closed)
- dev/test: fallback DESIGNER (mock 友好)
- `ALLOWED_ROLES` 白名单 6 角色: DESIGNER / PROCESS_CONTROLLER / REVIEWER / APPROVER / SYSTEM_ADMIN / VIEWER + CHECKER (per test_state_machine.py)

### 5. audit log 加强 — ✅ DONE (Sprint 3b, 2026-10-03)

**实施**: `pcs-backend/app/core/errors.py` 全局异常 handler choke point:
- 401/403 (PcsError MISSING_ROLE/INVALID_ROLE/MISSING_BEARER + HTTPException require_roles 拒绝)
  → `_record_rbac_denial` → audit_logs 写 RBAC_DENIED (resource_type=AUTHZ, detail 含
  path/method/ip/status/code/rate_limited; user_id best-effort 从 Bearer 解)
- per-IP 滑动窗口限流 (复用 F-P2-006 `check_rate_limit`): >5 次/min 同 IP →
  第 6 次起 429 RBAC_RATE_LIMITED (429 事件也写 audit, rate_limited=true)
- `_write_rbac_audit_row` 独立 session (get_async_session_factory), best-effort
  (失败仅 log warning 不阻断错误响应); pytest 环境跳过防测试写真库
- `AuditService.write` 放宽 `AuditAction | str` (core 层禁止 import models,
  architecture test 约束; str 经 services 层合法路径转枚举值)
- conftest 加 autouse `_clear_rbac_rate_limits` (防跨测试 429 污染)
- 8 单元测试 (`tests/test_rbac_audit.py`): 403/401 audit + 429 边界 + 窗口恢复 +
  404/200/422 不计数 + 真实 DB 写入路径

**Commit**: `feat(p7-s3b): F-P3-001 #5 — RBAC 401/403 audit + per-IP rate limit`

---

## Mock 友好的处理

**dev mode** (`ENV=development` 或 `ENV=test`):
- 保留 JWT role fallback `"DESIGNER"`
- 保留 `/auth/mock-login`
- 保留 LDAP stub
- JWT iss/aud 不写不校验 (config 未设)

**production mode** (`ENV=production`):
- role claim 缺失 → 401 (Sprint 3 实现)
- role 不在 ALLOWED_ROLES → 403 (Sprint 3 实现)
- LDAP 无映射 → raise LdapAuthError (Sprint 3 实现)
- 启动失败如 `/auth/mock-login` 注册到 router → 立即 raise (existing)
- LDAP issuer 不匹配 → fail-closed (config-driven 已就绪, 待 LDAP 接入启用)

---

## 状态

- [x] Issue 登记 → DONE (2026-10-02)
- [x] JWT role fallback 强制校验 → DONE (Sprint 3 2026-10-03, commit 见上)
- [x] `/auth/mock-login` production disable → EXISTING (carry-forward)
- [x] LDAP role mapping 强校验 → DONE (Sprint 3 2026-10-03)
- [x] LDAP issuer config-driven 校验 → DONE (Sprint 3 2026-10-03, LDAP 接入时启用)
- [x] audit log RBAC 401/403 + 限流扩展 → DONE (Sprint 3b 2026-10-03)

**关联文件 (Sprint 3 实施)**:
- `pcs-backend/app/core/config.py` (Settings: jwt_issuer, jwt_audience)
- `pcs-backend/app/core/security.py` (create_access_token / decode_token iss/aud)
- `pcs-backend/app/api/v1/config.py` (current_actor role fail-closed + ALLOWED_ROLES)
- `pcs-backend/app/services/ldap_client.py` (resolve_role production fail-closed)
- `tests/test_jwt_production.py` (13 单元测试)

**关联 buglog**: 登记 F-P3-001 production hardening, 防止后续 sprint 漏掉.

**Sprint 3 实施 commits**:
1. `feat(p7-s3): F-P3-001 production hardening - JWT iss/aud config-driven + role fail-closed + LDAP fix`