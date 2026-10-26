"""签署矩阵服务（P9A-DLV-007 · SUP-005 · ADR-0008）。

## 它管两件事

1. **解析**：`SignatureMatrix.steps_json` → `MatrixStep[]`
   —— **唯一的解析口**（`DeliverableService._matrix_steps` 改为调它）。
2. **取得**：项目要用的矩阵从哪来 —— **惰性建行**（见下）。

## 为什么要「惰性建行」

`signature_matrices` 表**恒为 0 行** —— 全仓**没有任何地方创建矩阵**
（`grep -rn "SignatureMatrix(" app/` ⇒ 0 处）⇒ 变更单
（`Deliverable.matrix_id` **NOT NULL** + FK → `signature_matrices.matrix_id`）
**建不出来** ⇒ ADR-0047 §① 的第三个观测写入点（CHANGE_NOTICE）**没有可达路径**
（= `TODOS.md` TODO-057 卡住的地方，P9A-DLV-009 记录的「哑雷」）。

⇒ 本服务在需要时建**内置模板**并**绑到项目**（与 P9A-USR-001「惰性建行」
同形，ADR-0046 §③ 先例）。

## 内置模板 `CHANGE_NOTICE_3_LEVEL`

3 级：**校核 / 审核 / 审定**（`CHECKER` / `REVIEWER` / `APPROVER`）。

依据：
- ADR-0008「变更单默认 3 级矩阵（校核/审核/审定，通常无 CUSTOMER；
  响应客户意见的项目可配置增加）」
- `spec/校审层级可配置化增补规格说明书.md` §2.4 的「版本目的 → 默认签署矩阵」
  映射表：`ISSUED_FOR_CHANGE` → `CHANGE_NOTICE_3_LEVEL`（客户签署 = 否）

⚠️ `can_self_check` **不写** ⇒ 解析时补成 `True`
（与 `DeliverableService.sign_step` 现有的 `step.get("can_self_check", True)`
**逐字一致** —— 不发明与既有签署路径不同的语义）。

## 事务语义

**不 commit** —— 与 `workflow_progress_writer.record_step` 一致：
事务边界归调用方（ADR-0047 §②③「与主事务同生共死」）。

## 抛的异常是哪一类

本模块抛 **`app.services.exceptions.PcsError`**（`message` 在前、
`code`/`status` 为 kwarg、默认 422）—— 与 `app.core.errors.PcsError`
**不是同一个类**（后者 `code`/`message` 在前、默认 400）。
⚠️ `deliverable_service` 用的是 **core 变体** ⇒ 在那里写
`except PcsError`（core）**捕不到**本模块抛的 422 ⇒ 会静默变成 500。
⇒ 需要捕获时，从 `app.services.exceptions` 导入。
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.deliverable import (
    ProjectSignatureMatrixBinding,
    SignatureMatrix,
)
from app.services.exceptions import PcsError

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class MatrixStep:
    """签署矩阵的一步。

    字段与 `SignatureMatrix.steps_json` 的键**逐字对应**
    （`step_order` / `sign_role` / `required` / `can_self_check` / `can_skip`）
    ⇒ 与 `workflow_progress.step_order` / `step_role` 同名同义
    （ADR-0047 §后果的改名条）。
    """

    step_order: int
    sign_role: str
    required: bool = True
    can_self_check: bool = True
    can_skip: bool = False


class SignatureMatrixService:
    """签署矩阵的**取得**与**解析**（P9A-DLV-007）。"""

    #: 内置变更单矩阵名（ADR-0008 / SUP-005 §2.4）
    DEFAULT_CHANGE_NOTICE_MATRIX_NAME = "CHANGE_NOTICE_3_LEVEL"

    #: 变更单矩阵的模块标识（`ProjectSignatureMatrixBinding.module`）
    CHANGE_NOTICE_MODULE = "CHANGE_NOTICE"

    #: 内置变更单矩阵的步骤（3 级：校核 / 审核 / 审定）
    DEFAULT_CHANGE_NOTICE_STEPS: tuple[dict[str, object], ...] = (
        {"step_order": 1, "sign_role": "CHECKER", "required": True},
        {"step_order": 2, "sign_role": "REVIEWER", "required": True},
        {"step_order": 3, "sign_role": "APPROVER", "required": True},
    )

    # ------------------------------------------------------------------
    # 解析（唯一解析口）
    # ------------------------------------------------------------------

    @staticmethod
    def parse_steps(matrix: SignatureMatrix | None) -> list[MatrixStep]:
        """把 `steps_json` 解析成**有序**的步骤列表。

        ## 为什么要排序

        `steps_json` 是一个 JSON 数组，**键序不保证**（写入方爱怎么排怎么排），
        而签署推进完全依赖顺序 ⇒ 必须显式按 `step_order` 升序，
        不能靠数组下标。

        ## 坏数据怎么办（RF-1）

        - **单项坏**（不是 dict / `step_order` 不是正整数 / `sign_role` 不是
          非空字符串）⇒ **跳过**它，其余项保留。
          ⚠️ `isinstance(True, int)` 为 True ⇒ `bool` 的 `step_order` 也要排除。
        - **全部坏**（矩阵有步骤但一项都不合法）⇒ **422 明说**
          （`SIGNATURE_MATRIX_INVALID`）。
          ⚠️ 不能当空矩阵返回：那会让变更单按 **0 步**走 ⇒ 签署一推就「越界」，
          而用户看到的是「矩阵是空的」而不是「矩阵配错了」。

        Raises:
            PcsError 422 `SIGNATURE_MATRIX_INVALID` —— 矩阵非空但无合法步骤。
        """
        if matrix is None or not matrix.steps_json:
            return []
        steps: list[MatrixStep] = []
        skipped = 0
        for raw in matrix.steps_json:
            if not isinstance(raw, dict):
                skipped += 1
                continue
            order = raw.get("step_order")
            # ⚠️ `bool` 是 `int` 的子类 ⇒ 显式排除（`True` 不是合法序号）
            if isinstance(order, bool) or not isinstance(order, int) or order <= 0:
                skipped += 1
                continue
            role = raw.get("sign_role")
            if not isinstance(role, str) or not role.strip():
                skipped += 1
                continue
            steps.append(
                MatrixStep(
                    step_order=order,
                    # ⚠️ **剥掉前后空白**：判空用 `.strip()` 却存原值 ⇒
                    # 矩阵里写 `" CHECKER "` ⇒ 签署时 403「要求角色『 CHECKER 』」
                    # —— 一个带空格的自己。
                    sign_role=role.strip(),
                    required=bool(raw.get("required", True)),
                    can_self_check=bool(raw.get("can_self_check", True)),
                    can_skip=bool(raw.get("can_skip", False)),
                )
            )
        if skipped:
            # ⚠️ 「部分跳过」没有报错，只能靠日志可观测 —— 签署少一道校审
            # 比报错更危险（计划 R-2 / RF-1）。
            logger.warning(
                "签署矩阵 %r 跳过了 %d 个非法步骤（保留 %d 步）",
                matrix.matrix_name,
                skipped,
                len(steps),
            )
        if not steps:
            raise PcsError(
                code="SIGNATURE_MATRIX_INVALID",
                message=(
                    f"签署矩阵 {matrix.matrix_name!r} 的步骤全部不合法"
                    "（step_order 须为正整数、sign_role 须为非空字符串）"
                ),
                status=422,
            )
        return sorted(steps, key=lambda s: s.step_order)

    # ------------------------------------------------------------------
    # 取得（惰性建行）
    # ------------------------------------------------------------------

    @classmethod
    async def ensure_change_notice_matrix(
        cls, db: AsyncSession, *, project_id: uuid.UUID
    ) -> SignatureMatrix:
        """取「变更单该用哪个矩阵」，没有就**建出来**。

        顺序：
        1. 项目**已绑定**的变更单矩阵 ⇒ 用它；
        2. 否则取**全局内置模板** `CHANGE_NOTICE_3_LEVEL`（没有就建）；
        3. 给项目建**绑定**（若还没有）。

        ⚠️ **绑定是签发的前置**：`DeliverableService._assert_matrix_bound`
        要求矩阵**真的绑在这个项目上**，否则变更单建出来了也**签不了**
        （409 `DELIVERABLE_MATRIX_UNBOUND`）。

        ⚠️ **不 commit**（事务边界归调用方）。

        Returns:
            该项目用的变更单签署矩阵。
        """
        binding = (
            await db.execute(
                select(ProjectSignatureMatrixBinding).where(
                    ProjectSignatureMatrixBinding.project_id == project_id,
                    ProjectSignatureMatrixBinding.module == cls.CHANGE_NOTICE_MODULE,
                )
            )
        ).scalar_one_or_none()
        if binding is not None:
            matrix = await db.get(SignatureMatrix, binding.matrix_id)
            if matrix is not None:
                return matrix

        matrix = await cls._get_or_create_builtin_matrix(db)
        await cls._ensure_binding(db, project_id=project_id, matrix_id=matrix.matrix_id)
        return matrix

    @classmethod
    async def _get_or_create_builtin_matrix(
        cls, db: AsyncSession
    ) -> SignatureMatrix:
        """全局内置模板（**幂等**：有就用，没有才建）。"""
        matrix = (
            await db.execute(
                select(SignatureMatrix).where(
                    SignatureMatrix.matrix_name == cls.DEFAULT_CHANGE_NOTICE_MATRIX_NAME,
                    SignatureMatrix.status == "ACTIVE",
                )
            )
        ).scalars().first()
        if matrix is not None:
            return matrix
        matrix = SignatureMatrix(
            matrix_name=cls.DEFAULT_CHANGE_NOTICE_MATRIX_NAME,
            module=cls.CHANGE_NOTICE_MODULE,
            doc_type=cls.CHANGE_NOTICE_MODULE,
            version_purpose="ISSUED_FOR_CHANGE",
            steps_json=[dict(s) for s in cls.DEFAULT_CHANGE_NOTICE_STEPS],
            status="ACTIVE",
        )
        db.add(matrix)
        await db.flush()
        return matrix

    @classmethod
    async def _ensure_binding(
        cls, db: AsyncSession, *, project_id: uuid.UUID, matrix_id: uuid.UUID
    ) -> ProjectSignatureMatrixBinding:
        """项目 × 模块 的矩阵绑定（**幂等**）。"""
        binding = (
            await db.execute(
                select(ProjectSignatureMatrixBinding).where(
                    ProjectSignatureMatrixBinding.project_id == project_id,
                    ProjectSignatureMatrixBinding.module == cls.CHANGE_NOTICE_MODULE,
                )
            )
        ).scalar_one_or_none()
        if binding is not None:
            binding.matrix_id = matrix_id
            return binding
        binding = ProjectSignatureMatrixBinding(
            project_id=project_id,
            module=cls.CHANGE_NOTICE_MODULE,
            matrix_id=matrix_id,
        )
        db.add(binding)
        await db.flush()
        return binding

__all__ = [
    "MatrixStep",
    "SignatureMatrixService",
]
