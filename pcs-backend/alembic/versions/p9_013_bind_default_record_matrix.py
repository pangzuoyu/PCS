"""给**存量项目**回填默认的 RECORD 签署矩阵（P9B-2 · Batch F）。

## 为什么需要这次回填

`POST /projects`（T-1）在建项目时**同一事务**里绑一份 ACTIVE 的 RECORD 矩阵
⇒ **新建**的项目当场就能送审。

⚠️ 但**存量**项目是在那之前建的 ⇒ 没有任何 RECORD 绑定 ⇒ 批准链（TODO-054
· R-17）**推导不出来** ⇒ 后端 422 `RECORD_APPROVAL_MATRIX_NOT_BOUND`
⇒ **存量记录一律送不了审** ⇒ 交付的签署流程在**真实数据**上走不通。

⇒ 这次迁移把**存量项目**补齐到与新建项目**同一份**矩阵。

## 为什么**不**调 `ensure_default_record_matrix` 服务

⚠️ 迁移必须**自包含**：服务代码会变 ⇒ 迁移的行为跟着变 ⇒ 老库升级的结果
**不可复现**（同一份迁移在不同时间跑出不同数据，是迁移最坏的性质）。
⇒ 默认矩阵的定义在这里**内联**，并由
`tests/alembic/test_p9_013_bind_default_record_matrix.py` 断言它与服务常量
**一致**（服务是**按名字找**已有矩阵的 ⇒ 定义漂了 ⇒ 服务会静默复用旧定义
⇒ 那条断言就是唯一的闸门）。

## 幂等

- **默认矩阵**：`(matrix_name, status)` 唯一（迁移 `p9_010`）⇒ 「有就复用、
  没有才建」天然幂等；
- **绑定**：**只给没有 RECORD 绑定的项目**补 ⇒ 已有绑定的项目**原样保留**
  （人工改过的绑定不被夺走 —— 与 `ensure_default_record_matrix` 同口径：
  「谁该签」的决定权不在系统手里）。

## ⚠️ `downgrade` 是**有损**的（评审 A-4：范围比「回填的」更广，如实登记）

降级删除的是**所有**指向默认 ACTIVE 矩阵的 `module='RECORD'` 绑定 ——
不止本迁移回填的，还包括：

- **运行时**创建的绑定（升级后 `POST /projects` 自动绑的）；
- **管理员手工**绑到该矩阵的绑定。

矩阵行本身**保留**（全局模板，删了会让升级之后新建的项目绑定悬空）。
被删的绑定是**用户配置**，降级不恢复、重跑 `upgrade head` 会按「没绑的
项目」重新补齐（代价：期间该项目送审吃 422 `RECORD_APPROVAL_MATRIX_NOT_BOUND`
的**中断窗口**）。没有只删「回填行」的精确途径（回填与运行时写入同构，
无标记列可区分 —— 加标记列的成本高于收益，裁决：docstring 如实说）。

## Revision

`revision = p9_013`，`down_revision = p9_012`（当前 head）。
"""
from __future__ import annotations

from alembic import op

revision = "p9_013"
down_revision = "p9_012"
branch_labels = None
depends_on = None

#: 默认记录级矩阵的**固定名**（与服务 `SignatureMatrixService.DEFAULT_RECORD_MATRIX_NAME` 一致）
_MATRIX_NAME = "DEFAULT_RECORD_3_LEVEL"
#: 绑定的模块标识（与服务 `SignatureMatrixService.RECORD_MODULE` 一致）
_MODULE = "RECORD"
#: 默认矩阵的步骤（与服务 `SignatureMatrixService.DEFAULT_RECORD_STEPS` 一致）
_STEPS_JSON = (
    '[{"step_order": 1, "sign_role": "CHECKER", "required": true},'
    ' {"step_order": 2, "sign_role": "REVIEWER", "required": true},'
    ' {"step_order": 3, "sign_role": "APPROVER", "required": true}]'
)

# ① 默认矩阵（**有就复用，没有才建** ⇒ 幂等）
_CREATE_MATRIX = f"""
INSERT INTO signature_matrices (
    matrix_id, matrix_name, module, doc_type, version_purpose,
    steps_json, status
)
SELECT
    gen_random_uuid(),
    '{_MATRIX_NAME}',
    '{_MODULE}',
    '{_MODULE}',
    'PUBLISHED',
    '{_STEPS_JSON}'::jsonb,
    'ACTIVE'
WHERE NOT EXISTS (
    SELECT 1 FROM signature_matrices
    WHERE matrix_name = '{_MATRIX_NAME}' AND status = 'ACTIVE'
)
"""

# ② 给**没有 RECORD 绑定**的项目补绑定（已有绑定的原样保留 ⇒ 幂等）
_CREATE_BINDINGS = f"""
INSERT INTO project_signature_matrix_bindings (
    binding_id, project_id, module, matrix_id
)
SELECT
    gen_random_uuid(),
    p.project_id,
    '{_MODULE}',
    m.matrix_id
FROM projects p
CROSS JOIN (
    SELECT matrix_id FROM signature_matrices
    WHERE matrix_name = '{_MATRIX_NAME}' AND status = 'ACTIVE'
    LIMIT 1
) m
WHERE NOT EXISTS (
    SELECT 1 FROM project_signature_matrix_bindings b
    WHERE b.project_id = p.project_id AND b.module = '{_MODULE}'
)
"""

# ③ 降级：删掉**所有**指向默认矩阵的 RECORD 绑定（矩阵行保留 —— 范围见模块 docstring 的有损声明）
_DROP_BINDINGS = f"""
DELETE FROM project_signature_matrix_bindings
WHERE module = '{_MODULE}'
  AND matrix_id IN (
      SELECT matrix_id FROM signature_matrices
      WHERE matrix_name = '{_MATRIX_NAME}' AND status = 'ACTIVE'
  )
"""


def upgrade() -> None:
    """建默认矩阵 + 给存量项目补 RECORD 绑定。"""
    op.execute(_CREATE_MATRIX)
    op.execute(_CREATE_BINDINGS)


def downgrade() -> None:
    """删掉所有指向默认矩阵的 RECORD 绑定（⚠️ **有损且比回填范围广** —— 见模块 docstring）。"""
    op.execute(_DROP_BINDINGS)
