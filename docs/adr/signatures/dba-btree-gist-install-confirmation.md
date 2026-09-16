# DBA 执行确认：btree_gist 扩展预装（两库）

**关联请求**：`docs/adr/signatures/dba-btree-gist-install-request.md`（2026-09-16）
**执行日期**：2026-09-16
**确认日期**：2026-09-16
**归档类型**：DBA 执行完毕确认版

---

## 一、执行结果

### 1.1 扩展安装（两库）

DBA 已分别于 `pcs` 与 `pcs_test` 库执行 `CREATE EXTENSION btree_gist;`，两库均成功。

| 库 | 扩展 | 版本 | 状态 |
|---|---|---|---|
| pcs | btree_gist | 1.7 | ✅ 已安装 |
| pcs_test | btree_gist | 1.7 | ✅ 已安装 |

版本 1.7 在 PG 16 stable 范围内，符合请求文档 §2.2 验收标准（1.5 ~ 1.7 均可接受）。

### 1.2 业务用户视角验证（pcs 用户，非 superuser）

业务用户 `pcs`（`is_super=off`）通过非 superuser 连接执行扩展元数据查询：

```bash
PGPASSWORD='pcs_dev' psql -h 127.0.0.1 -p 5432 -U pcs -d pcs \
  -c "SELECT extname, extversion FROM pg_extension WHERE extname='btree_gist';"
# extname   | extversion
# ------------+------------
#  btree_gist | 1.7
# (1 row)

PGPASSWORD='pcs_dev' psql -h 127.0.0.1 -p 5432 -U pcs -d pcs_test \
  -c "SELECT extname, extversion FROM pg_extension WHERE extname='btree_gist';"
# extname   | extversion
# ------------+------------
#  btree_gist | 1.7
# (1 row)
```

**结论**：业务用户 `pcs` 已具备 `btree_gist` 扩展使用权限，无需 superuser 介入。

---

## 二、后续步骤解锁

Task 24（P5-0-5 PSV 标准配置模型）的 alembic 迁移 `p5_standard_profiles` 现可执行：

```bash
cd pcs-backend
uv run alembic upgrade head
uv run alembic -x dburl=postgresql+psycopg://pcs:pcs_dev@localhost:5432/pcs_test upgrade head
```

迁移中 `CREATE TABLE ... USING gist (...)` 约束将基于 `btree_gist` 扩展生效。

---

## 三、签字栏

| 角色 | 操作 | 日期 | 签字 |
|---|---|---|---|
| DBA | 2.1 安装扩展（pcs + pcs_test） | 2026-09-16 | ✅ 已执行（双库 v1.7） |
| DBA | 2.2 验证扩展可用 | 2026-09-16 | ✅ 已验证 |
| 业务方（PCS） | 2.3 验证业务用户可用 | 2026-09-16 | ✅ 已验证（pcs 用户查询双库均返回 v1.7） |
| 业务方（PCS） | 3. alembic 迁移可行性 | 2026-09-16 | 待 Task 24 启动后回填 |

---

## 四、影响解链

- **Task 24（P5-0-5 PSV 标准配置模型）**：阻塞解除，立即可启动
- **Task 25（P5-0-6 ChEDL 版本锁定）**：原本无依赖，已可启动
- **Task 26（P5-0-7 ChEDL 包装层）**：依赖 Task 25 完成
- **P5-0 批整体**：7/7 task 全部可启动或进入排队

---

## 五、关联文件

- `docs/adr/signatures/dba-btree-gist-install-request.md` — 执行请求（已归档）
- `docs/PCS-P5-START-CHECKLIST.md` §障碍 1 — 启动前 12 项检查清单
- `docs/PCS-PLAN-P5-DEVICE-EQUIPMENT.md` §P5-0-5 — Task 24 详细描述
- `spec/SUP-P5-PSV-001 PSV 多标准.md` §3.1 — schema 设计要求
- `docs/adr/0028-psv-multi-standard-engine.md` V1.1 accepted — 决策 1 + 决策 5 落地需要

---

**归档人**：P5 启动协调
**归档日期**：2026-09-16
**版本**：V1.0