# F-P3-001 Production 前置 Checklist

**来源**: ce-code-review 20261001-174422-16a356de F-P3-001  
**裁决**: 用户 2026-10-02 接受 advisory, 登记 production 前置  
**优先级**: ⚠️ Medium (mock-friendly intentional, production 必须修)  
**预计工作量**: 0.5 人天

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

### 1. JWT issuer 强制校验

```python
# 改: payload.get("role", "DESIGNER") → 必须有 role
role = payload.get("role")
if role not in ALLOWED_ROLES:  # {"DESIGNER", "PROCESS_CONTROLLER", "REVIEWER", "APPROVER", "SYSTEM_ADMIN"}
    raise PcsError(code="INVALID_ROLE", message=f"role {role!r} not allowed", status=403)
```

### 2. Production 关闭 mock-login

- `pcs-backend/app/api/v1/auth.py` 的 `/auth/mock-login` 仅 dev 启用
- 通过 `settings.ENV == "production"` 检查 + 启动时移除路由
- 或用 feature flag: `MOCK_LOGIN_ENABLED=false` (env-based)

### 3. LDAP issuer 强校验 (production)

- 验证 `iss` 声明 == 生产 LDAP issuer
- 验证 `aud` 声明 == `pcs-api`
- `nbf`/`exp` 严格 (默认 60min, 不允许 refresh 后超过 8h)

### 4. role mapping 强校验

- LDAP group → PCS role 映射表 hardcoded, 启动时校验所有 group 名合法
- 不允许 LDAP 返回未在 ALLOWED_ROLES 列表的 role

### 5. audit log 加强

- role==DESIGNER 的 401/403 记录全部进 `audit_logs` (当前仅记认证/安全, 不记 RBAC)
- 短期 (>5/min) 403 触发 IP 限流 (F-P2-006 sliding window 扩展)

---

## Mock 友好的处理

**dev mode** (`ENV=development` 或 `ENV=test`):
- 保留 JWT role fallback `"DESIGNER"`
- 保留 `/auth/mock-login`
- 保留 LDAP stub

**production mode** (`ENV=production`):
- 启动失败如 JWT role fallback 路径被执行 → 立即 raise
- 启动失败如 `/auth/mock-login` 注册到 router → 立即 raise
- LDAP issuer 不匹配 → fail-closed (拒绝所有 token)

---

## 状态

- [ ] Issue 登记 → DONE (本文档)
- [ ] JWT role fallback 强制校验 → Sprint 3 production 前
- [ ] `/auth/mock-login` production disable → Sprint 3
- [ ] LDAP issuer 强校验 → Sprint 3 (LDAP 接入 sprint)
- [ ] rate limit 扩展 (403/401 也计) → Sprint 3 (扩展 F-P2-006)

**关联文件**:
- `pcs-backend/app/api/v1/config.py:460` (主修复点)
- `pcs-backend/app/core/security.py:44` (create_access_token)
- `pcs-backend/app/api/v1/auth.py:239` (login role 写入)
- `pcs-backend/app/api/v1/mock_auth.py:66` (mock token 路径)

**关联 buglog**: 登记 F-P3-001 production 前置, 防止 Sprint 3 启动前遗漏.
