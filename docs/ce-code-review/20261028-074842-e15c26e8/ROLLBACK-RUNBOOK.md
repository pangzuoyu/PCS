# P9B-2 Roll-forward Runbook（追问 1 补件）

> 配套 `deployment-verification.md`（Go/No-Go 清单）使用：那份管「上线前/后」，
> 这份管**上线后出问题时值班的人**。所有命令在 `pcs-backend/` 下执行，
> 口令不落命令行（`DATABASE_URL` 从 `.env` 进程内读）。

## R-1 出现 `RECORD_APPROVAL_MATRIX_NOT_BOUND`（422）日志

**判断**：哪个项目没绑 RECORD 矩阵（新建项目漏绑 / p9_013 降级过的库 / 手工删过绑定）。

```sql
-- 找没绑 RECORD 矩阵的项目（这就是日志里 422 的来源集合）
SELECT p.project_id, p.project_no
FROM projects p
WHERE NOT EXISTS (
  SELECT 1 FROM project_signature_matrix_bindings b
  WHERE b.project_id = p.project_id AND b.module = 'RECORD'
);
```

**处置**：对每个漏绑项目执行（即手工重放 p9_013 的回填）：

```sql
INSERT INTO project_signature_matrix_bindings (binding_id, project_id, module, matrix_id)
SELECT gen_random_uuid(), p.project_id, 'RECORD', m.matrix_id
FROM projects p
CROSS JOIN (
  SELECT matrix_id FROM signature_matrices
  WHERE matrix_name = 'DEFAULT_RECORD_3_LEVEL' AND status = 'ACTIVE' LIMIT 1
) m
WHERE NOT EXISTS (
  SELECT 1 FROM project_signature_matrix_bindings b
  WHERE b.project_id = p.project_id AND b.module = 'RECORD'
);
-- 预期：INSERT n（= 上面查出的项目数）；受影响用户重试送审即 200
```

## R-2 `/records/*/submit-approval` 4xx 率突增

**判断**：先分形状，别混为一谈。

```bash
# ① 看是不是 stale bundle（部署窗口内旧前端还在跑）
#    特征：请求体里带 approval_role / approval_depth（旧契约字段）⇒ 422 VALIDATION_ERROR
#    且 User-Agent / 版本头是旧 bundle 的。确认 ⇒ 等窗口自然衰减 + 公告硬刷新（Ctrl+Shift+R）。
# ② 特征：APPROVAL_SELF_REVIEW_FORBIDDEN（403）⇒ 预期新行为（用户裁决放行的
#    自审拦截），转支持解释，不是事故。
# ③ 特征：RECORD_APPROVAL_MATRIX_NOT_BOUND ⇒ 走 R-1。
```

**阈值参考**：部署后 30 分钟内 4xx 率尖峰 → 2 小时应衰减到部署前基线
（`sum(rate(http_requests_total{path=~"/records/.*/submit-approval",code=~"4.."}[5m]))`，
无现成监控时用网关/uvicorn access log 计数）。**2 小时不衰减 = 不是 stale
bundle，按 ③ 查配置、仍无解则升级**。

## R-3 想回滚（读这份之前：p9_012 删列不可逆，优先 roll-forward）

| 想回滚的东西 | 命令 | 代价 |
|---|---|---|
| 只回代码（保留 DB 在 head） | 部署上一版镜像，**不跑** alembic | 旧 ORM 对 p9_014 新列不认识但无害（多列不炸）；旧代码对 p9_013 无依赖 ⇒ 可行 |
| 回滚 p9_014（快照列层） | `command.downgrade(cfg, "p9_013")` | ⚠️ 删掉 20 张表的 `approval_chain_snapshot` ⇒ **在飞的冻结批准链一起没了** ⇒ 已提交待审的记录退回「实时矩阵」语义 ⇒ 中途重绑矩阵又可能改链（CWE-863）⇒ **回滚 p9_014 等于把 #1 的修复退回去**。回滚前先查有没有在飞的记录（见下方 SQL）；有则**优先 roll-forward**（修代码），别回滚列 |
| 回滚 p9_013（ bindings 层） | 见下 | ⚠️ 删**所有**指向默认矩阵的 RECORD 绑定（含运行时/手工绑的，不只是回填的）⇒ R-1 的 SQL 可完整复原，代价是中断窗口 |
| 回滚 p9_012（删列层） | **不存在**安全路径 | 列已物理删除，数据不可恢复（本批裁决：0 行 0 写入 ⇒ 可接受） |

```sql
-- 回滚 p9_014 前先看有没有在飞的批准链（IN_APPROVAL）
SELECT r.pipe_id FROM piping_results r WHERE r.sign_status = 'IN_APPROVAL'
UNION ALL SELECT r.flash_id FROM flash_results r WHERE r.sign_status = 'IN_APPROVAL';
-- （20 张记录表各查一次；返回非空 ⇒ **不要**回滚 p9_014）
```

```bash
# 回滚 p9_013（会删绑定 ⇒ 先跑 R-1 的 SELECT 记下当前漏绑数，回滚后对比）
uv run python -c "
import os
from dotenv import dotenv_values
from alembic import command
from alembic.config import Config
os.environ['DATABASE_URL'] = dotenv_values('.env')['DATABASE_URL']
command.downgrade(Config('alembic.ini'), 'p9_012')
"
# 恢复（roll-forward 修复一切）：
#   同款脚本 command.upgrade(cfg, 'head')，然后跑 R-1 的 INSERT 补回绑定
```

⚠️ **验多个库 ⇒ 一库一个进程**（2026-11-02 实测打脸）：alembic 的 `settings`
是 **pydantic 缓存实例** ⇒ **同一进程内第二次改 `os.environ['DATABASE_URL']`
不生效** ⇒ 第二遍连的仍是第一个库；而 `upgrade` 幂等 ⇒ 两遍都打印同一个
`(head)`，**输出无法区分** ⇒ 上一轮 QA 据此得出的「两库都干净」是**假证据**。
⇒ 上面的配方只适用于**单个**库；要验多个库 ⇒ **每库起独立进程**，且**直查
库的 `alembic_version` + 目标列存在性**，不能只信命令输出。

## R-4 日志出现 `UndefinedColumn: parent_deliverable_id` / `approval_chain_snapshot`

**判断**：代码与迁移版本错配（新代码 + 旧库，或反之）。
**处置**：`uv run alembic current` 对 `uv run alembic heads` ——不一致就
`upgrade head`（roll-forward 修复）；一致还报 ⇒ 部署了混合版本镜像，重启到
单一版本。
