# DBA 执行请求：预装 btree_gist 扩展（两库）

**请求人**：P5 启动协调
**请求日期**：2026-09-16
**优先级**：P0（阻塞 Task 24 / P5-0-5 PSV 标准配置模型启动）
**关联**：ADR-0028 V1.1 已 accepted / PCS-P5-START-CHECKLIST.md §障碍 1

---

## 一、背景

`SUP-P5-PSV-001 V1.0` §3.1 schema 设计要求 `project_calculation_standard_profiles` 表的 `(project_id, discipline, standard_profile_code, version)` 四元组有唯一性约束（防止同一项目同一专业配置重复标准 profile）。PostgreSQL 的 `EXCLUDE USING gist` 是表达"任意两行不重叠"的最直接约束，需要 `btree_gist` 扩展支持 btree 类型（`int`、`text`）作为 gist 索引键。

P5-0-5 Task 24 的 alembic 迁移 `p5_standard_profiles` 必失败（无 `btree_gist` 扩展时 `CREATE EXTENSION` 需要 superuser）。

业务用户 `pcs` `is_super=off`，无 superuser 权限，**必须由 DBA 在两库以 superuser 执行 `CREATE EXTENSION btree_gist;`**。

---

## 二、执行清单（请 DBA 复制执行）

### 2.1 安装扩展（两库分别执行）

```bash
# pcs 库
psql -U postgres -d pcs        -c "CREATE EXTENSION btree_gist;"

# pcs_test 库
psql -U postgres -d pcs_test   -c "CREATE EXTENSION btree_gist;"
```

**预期输出**（两库各 1 行）：
```
CREATE EXTENSION
```

如两库已存在则报 `ERROR: extension "btree_gist" already exists`，可忽略（说明已预装）。

### 2.2 验证扩展可用（业务用户视角）

```bash
# pcs 库
psql -U pcs -h localhost -d pcs -c "SELECT extname, extversion FROM pg_extension WHERE extname='btree_gist';"

# pcs_test 库
psql -U pcs -h localhost -d pcs_test -c "SELECT extname, extversion FROM pg_extension WHERE extname='btree_gist';"
```

**预期输出**（两库各 1 行）：
```
 extname    | extversion
-----------+------------
 btree_gist | 1.6
```

`extversion` 数字以 PG 16 实际版本为准（1.5 ~ 1.7 都可接受）。

### 2.3 验证业务用户可使用扩展（无需 superuser）

```bash
# pcs 库
psql -U pcs -h localhost -d pcs -c "SELECT has_function_privilege('pcs', 'gist_text_consistent(internal, internal, int4, internal, internal)', 'execute');"

# pcs_test 库
psql -U pcs -h localhost -d pcs_test -c "SELECT has_function_privilege('pcs', 'gist_text_consistent(internal, internal, int4, internal, internal)', 'execute');"
```

**预期输出**（两库各 1 行 `t`）：
```
 has_function_privilege
------------------------
 t
```

---

## 三、alembic 迁移可行性验证（DBA 执行完毕后）

DBA 执行完毕后，业务用户即可执行 alembic 迁移：

```bash
cd pcs-backend && uv run alembic upgrade head
cd pcs-backend && uv run alembic -x dburl=postgresql+psycopg://pcs:pcs_dev@localhost:5432/pcs_test upgrade head
```

Task 24（P5-0-5）的 alembic 迁移 `p5_standard_profiles` 将包含 `CREATE TABLE ... USING gist (...)` 约束，依赖 `btree_gist` 扩展。

---

## 四、回退预案（如安装失败）

如 DBA 因 PG 版本或仓库配置问题无法安装 `btree_gist`：
- **方案 A**：DBA 升级 PG 版本（`btree_gist` 在 PG 16 已 stable，无需升级）
- **方案 B**：方案 C 备选——alembic 迁移降级为 btree 唯一索引 + 应用层锁（**不推荐**，破坏 SPEC §3.1 schema 设计意图）

---

## 五、签字栏

| 角色 | 操作 | 日期 | 签字 |
|---|---|---|---|
| DBA | 2.1 安装扩展（pcs + pcs_test） | 2026-09-__ | ________________ |
| DBA | 2.2 验证扩展可用 | 2026-09-__ | ________________ |
| 业务方（PCS） | 2.3 验证业务用户可用 | 2026-09-__ | ________________ |
| 业务方（PCS） | 3. alembic 迁移可行性 | 2026-09-__ | ________________ |

DBA 执行完毕后，请将本文件提交至 P5 启动协调，由秘书处归档至 `docs/adr/signatures/dba-btree-gist-install-confirmation.md`（确认版，含扩展版本号 + 签字时间）。

---

## 六、关联文件

- `docs/PCS-P5-START-CHECKLIST.md` §障碍 1 — 启动前 12 项检查清单
- `docs/PCS-PLAN-P5-DEVICE-EQUIPMENT.md` §P5-0-5 — Task 24 详细描述
- `spec/SUP-P5-PSV-001 PSV 多标准.md` §3.1 — schema 设计要求
- `docs/adr/0028-psv-multi-standard-engine.md` V1.1 accepted — 决策 1 + 决策 5 落地需要