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

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
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
    # 管理面（TODO-070）：模板 CRUD + 项目绑定
    # ------------------------------------------------------------------

    @classmethod
    def validate_steps(cls, steps: list) -> list[MatrixStep]:
        """**严格**校验一份步骤定义（**写入**路径用）。

        ## 与 `parse_steps` 的区别（两个口，两个语义）

        | | `parse_steps`（读） | `validate_steps`（写） |
        |---|---|---|
        | 单项坏 | 跳过 + WARNING 日志 | **422** |
        | 全坏 | 422 | **422** |

        读路径必须容忍**存量脏数据**（否则一个坏矩阵让签署整体 500）；
        写路径必须**挡住坏配置**（否则「签署少一道校审」而没人知道）。
        ⇒ 新写进来的矩阵一定是干净的 ⇒ 读路径的「部分跳过」只服务存量。

        Raises:
            PcsError 422 `SIGNATURE_MATRIX_INVALID` —— 任一项非法。
        """
        if not steps:
            raise PcsError(
                "签署矩阵至少要有 1 个步骤",
                code="SIGNATURE_MATRIX_INVALID",
                status=422,
            )
        out: list[MatrixStep] = []
        for index, raw in enumerate(steps):
            if not isinstance(raw, dict):
                raise cls._invalid_step(index, "必须是对象")
            order = raw.get("step_order")
            if isinstance(order, bool) or not isinstance(order, int) or order <= 0:
                raise cls._invalid_step(index, "step_order 须为正整数")
            role = raw.get("sign_role")
            if not isinstance(role, str) or not role.strip():
                raise cls._invalid_step(index, "sign_role 须为非空字符串")
            out.append(
                MatrixStep(
                    step_order=order,
                    sign_role=role.strip(),
                    required=bool(raw.get("required", True)),
                    can_self_check=bool(raw.get("can_self_check", True)),
                    can_skip=bool(raw.get("can_skip", False)),
                )
            )
        # 序号重复 ⇒ 「谁该签这一步」有两个答案 ⇒ 挡住
        orders = [s.step_order for s in out]
        if len(set(orders)) != len(orders):
            raise PcsError(
                f"签署矩阵的 step_order 重复：{sorted(orders)}",
                code="SIGNATURE_MATRIX_INVALID",
                status=422,
            )
        return sorted(out, key=lambda s: s.step_order)

    @staticmethod
    def _invalid_step(index: int, why: str) -> PcsError:
        return PcsError(
            f"签署矩阵第 {index + 1} 个步骤不合法：{why}",
            code="SIGNATURE_MATRIX_INVALID",
            status=422,
        )

    @classmethod
    async def _assert_name_free(
        cls,
        db: AsyncSession,
        *,
        matrix_name: str,
        status: str,
        exclude_matrix_id: uuid.UUID | None = None,
    ) -> None:
        """同名 + 同状态的矩阵**不许**存在两份 ⇒ 409（TODO-074）。

        ## 为什么

        内置矩阵是按 `(matrix_name, status='ACTIVE')` **找第一份**的 ⇒ 同名
        的 ACTIVE 矩阵有两份 ⇒ 两个项目可能绑到**不同的一份** ⇒
        「谁该签这一步」出现**两个答案**。

        ## 约束为什么是 **(matrix_name, status)** 而不是「名字全局唯一」

        一份**已作废**（OBSOLETE）的同名模板不该**永久堵住**重建 ⇒ 否则
        作废后再也建不出同名的 ACTIVE 模板 ⇒ 运维只能改名字 ⇒ 历史绑定里的旧
        名字全是死链。⇒ 同一**状态**下名字唯一就够。

        ⚠️ 应用层这一查只挡**顺序**调用；**并发**下两个事务都查不到 ⇒ 靠 DB
        唯一约束（迁移 `p9_010`）兜底 ⇒ 撞约束时端点返 **500**（而不是 409）
        —— 这是并发窗口的固有代价，不在这里假装能挡。
        """
        conditions = [
            SignatureMatrix.matrix_name == matrix_name,
            SignatureMatrix.status == status,
        ]
        if exclude_matrix_id is not None:
            conditions.append(SignatureMatrix.matrix_id != exclude_matrix_id)
        existing = (
            await db.execute(select(SignatureMatrix).where(*conditions))
        ).scalars().first()
        if existing is None:
            return
        raise PcsError(
            f"签署矩阵名 {matrix_name!r}（状态 {status}）已被占用"
            f"（矩阵 {existing.matrix_id}）",
            code="SIGNATURE_MATRIX_NAME_CONFLICT",
            status=409,
        )

    @classmethod
    async def create_matrix(
        cls,
        db: AsyncSession,
        *,
        matrix_name: str,
        module: str,
        doc_type: str,
        version_purpose: str,
        steps: list,
        status: str = "DRAFT",
    ) -> SignatureMatrix:
        """建一个矩阵模板（**不 commit** —— 事务边界归调用方）。"""
        validated = cls.validate_steps(steps)
        await cls._assert_name_free(db, matrix_name=matrix_name, status=status)
        matrix = SignatureMatrix(
            matrix_name=matrix_name,
            module=module,
            doc_type=doc_type,
            version_purpose=version_purpose,
            steps_json=[
                {
                    "step_order": s.step_order,
                    "sign_role": s.sign_role,
                    "required": s.required,
                    "can_self_check": s.can_self_check,
                    "can_skip": s.can_skip,
                }
                for s in validated
            ],
            status=status,
        )
        db.add(matrix)
        await db.flush()
        return matrix

    @classmethod
    async def get_matrix(
        cls, db: AsyncSession, *, matrix_id: uuid.UUID
    ) -> SignatureMatrix:
        """取矩阵；不存在 ⇒ 404。"""
        matrix = await db.get(SignatureMatrix, matrix_id)
        if matrix is None:
            raise PcsError(
                f"签署矩阵 {matrix_id} 不存在",
                code="SIGNATURE_MATRIX_NOT_FOUND",
                status=404,
            )
        return matrix

    @classmethod
    async def list_matrices(
        cls,
        db: AsyncSession,
        *,
        module: str | None = None,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[SignatureMatrix], int]:
        """列矩阵模板（分页）。返回 (items, total)。"""
        conditions = []
        if module:
            conditions.append(SignatureMatrix.module == module)
        if status:
            conditions.append(SignatureMatrix.status == status)
        total = int(
            await db.scalar(
                select(func.count()).select_from(SignatureMatrix).where(*conditions)
            )
            or 0
        )
        rows = (
            await db.execute(
                select(SignatureMatrix)
                .where(*conditions)
                .order_by(SignatureMatrix.created_at, SignatureMatrix.matrix_id)
                .limit(limit)
                .offset(offset)
            )
        ).scalars().all()
        return list(rows), total

    @classmethod
    async def update_matrix(
        cls,
        db: AsyncSession,
        *,
        matrix_id: uuid.UUID,
        matrix_name: str | None = None,
        module: str | None = None,
        doc_type: str | None = None,
        version_purpose: str | None = None,
        steps: list | None = None,
        status: str | None = None,
    ) -> SignatureMatrix:
        """改矩阵模板（**不 commit**）。`steps` 给了就**整体替换**。"""
        matrix = await cls.get_matrix(db, matrix_id=matrix_id)
        if matrix_name is not None:
            await cls._assert_name_free(
                db,
                matrix_name=matrix_name,
                status=status if status is not None else matrix.status,
                exclude_matrix_id=matrix_id,
            )
            matrix.matrix_name = matrix_name
        if module is not None:
            matrix.module = module
        if doc_type is not None:
            matrix.doc_type = doc_type
        if version_purpose is not None:
            matrix.version_purpose = version_purpose
        if status is not None:
            matrix.status = status
        if steps is not None:
            validated = cls.validate_steps(steps)
            matrix.steps_json = [
                {
                    "step_order": s.step_order,
                    "sign_role": s.sign_role,
                    "required": s.required,
                    "can_self_check": s.can_self_check,
                    "can_skip": s.can_skip,
                }
                for s in validated
            ]
        await db.flush()
        return matrix

    @classmethod
    async def bind_to_project(
        cls,
        db: AsyncSession,
        *,
        project_id: uuid.UUID,
        module: str,
        matrix_id: uuid.UUID,
    ) -> ProjectSignatureMatrixBinding:
        """把矩阵绑到项目 × 模块（**幂等**；换绑 = 改 matrix_id）。

        ⚠️ `(project_id, module)` 唯一约束（迁移 `p9_008`）⇒ 同一项目同一模块
        只可能有一行绑定 ⇒ 「谁该签这一步」不会有两个答案。

        ## 三道校验（都**响亮失败**，不静默）

        1. 矩阵必须 **ACTIVE** —— DRAFT/PENDING/OBSOLETE 的模板**不许**接管
           生产签署（否则「还没启用的模板」已经在签真实变更单了）。
        2. 矩阵的 `module` 必须与绑定的 `module` 一致（或 `*` = 全部模块）
           —— 否则一个为 RECORD 建的矩阵被绑成 CHANGE_NOTICE ⇒ 用**错误的角色集**
           去签变更单。
        3. 并发 ⇒ 撞唯一约束 ⇒ **SAVEPOINT** 回滚这一行 + 重读（不是 500）。
           ⚠️ `db.add()` 必须在 savepoint **之内**（`begin_nested()` 会先 flush
           一次 pending ⇒ savepoint 之外的 INSERT 不受保护）。
        """
        matrix = await cls.get_matrix(db, matrix_id=matrix_id)
        if matrix.status != "ACTIVE":
            raise PcsError(
                f"签署矩阵 {matrix.matrix_name!r} 当前 {matrix.status}，"
                f"只有 ACTIVE 的矩阵可以绑定到项目",
                code="SIGNATURE_MATRIX_NOT_ACTIVE",
                status=422,
            )
        if matrix.module not in ("*", module):
            raise PcsError(
                f"签署矩阵 {matrix.matrix_name!r} 属于模块 {matrix.module!r}，"
                f"不能绑成 {module!r}",
                code="SIGNATURE_MATRIX_MODULE_MISMATCH",
                status=422,
            )
        binding = (
            await db.execute(
                select(ProjectSignatureMatrixBinding).where(
                    ProjectSignatureMatrixBinding.project_id == project_id,
                    ProjectSignatureMatrixBinding.module == module,
                )
            )
        ).scalar_one_or_none()
        if binding is not None:
            binding.matrix_id = matrix.matrix_id
            await db.flush()
            return binding
        binding = ProjectSignatureMatrixBinding(
            project_id=project_id,
            module=module,
            matrix_id=matrix.matrix_id,
        )
        try:
            # ⚠️ `db.add` 必须在 savepoint **之内**（`begin_nested()` 会先 flush
            # pending ⇒ savepoint 之外的 INSERT 撞约束时会**中止整个事务**）。
            async with db.begin_nested():
                db.add(binding)
                await db.flush()
        except IntegrityError:
            # 并发：另一个请求先绑上了 ⇒ 重读那一行（不覆盖赢家的 matrix_id）
            existing = (
                await db.execute(
                    select(ProjectSignatureMatrixBinding).where(
                        ProjectSignatureMatrixBinding.project_id == project_id,
                        ProjectSignatureMatrixBinding.module == module,
                    )
                )
            ).scalar_one_or_none()
            if existing is None:
                raise
            return existing
        return binding

    @classmethod
    async def unbind_from_project(
        cls, db: AsyncSession, *, project_id: uuid.UUID, module: str
    ) -> bool:
        """解绑（返回是否真删了一行）。"""
        binding = (
            await db.execute(
                select(ProjectSignatureMatrixBinding).where(
                    ProjectSignatureMatrixBinding.project_id == project_id,
                    ProjectSignatureMatrixBinding.module == module,
                )
            )
        ).scalar_one_or_none()
        if binding is None:
            return False
        await db.delete(binding)
        await db.flush()
        return True

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
                # ⚠️ 绑着的矩阵必须 **ACTIVE** —— DRAFT/PENDING/OBSOLETE 的模板
                # 不该接管生产签署。**响亮失败**（不静默换回内置模板：静默换
                # 会让项目在**不知情**的情况下换了签署规则）。
                if matrix.status != "ACTIVE":
                    raise PcsError(
                        f"项目 {project_id} 绑定的签署矩阵 {matrix.matrix_name!r} "
                        f"当前 {matrix.status}，不是 ACTIVE",
                        code="SIGNATURE_MATRIX_NOT_ACTIVE",
                        status=409,
                    )
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
        """项目 × 模块 的矩阵绑定（**幂等** + 并发安全）。

        ⚠️ **并发**：应用层的「先查后建」挡不住两个事务同时建 ⇒ 靠
        `(project_id, module)` 唯一约束兜底（迁移 `p9_008`）。
        撞约束 ⇒ **重读**那一行（而不是 500）——
        没有兜底的话，同一项目同一模块会绑到两个矩阵，
        之后每次解析绑定都 `MultipleResultsFound` ⇒ 该项目的变更单路径永久 500。
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
            binding.matrix_id = matrix_id
            return binding
        binding = ProjectSignatureMatrixBinding(
            project_id=project_id,
            module=cls.CHANGE_NOTICE_MODULE,
            matrix_id=matrix_id,
        )
        try:
            # ⚠️ **SAVEPOINT 必须包住 `db.add`**：`Session.begin_nested()` 在
            # 发出 SAVEPOINT **之前**会先 flush 一次 pending（SQLAlchemy 2.0 的
            # `SessionTransaction._take_snapshot`：`if not is_begin: session.flush()`）
            # ⇒ 若 `db.add` 在 savepoint **之外**，那条会撞约束的 INSERT 就**不在
            # savepoint 里** ⇒ PostgreSQL 撞唯一约束会**中止整个事务**（25P02）
            # ⇒ 外层（矩阵/交付物）一起回滚 ⇒ 500。
            #
            # ⚠️ 反过来：savepoint **之前**的 pending（矩阵行）会在
            # `begin_nested()` 的那次 flush 里落库 ⇒ 它在 savepoint **之外**
            # ⇒ 回滚时不受影响 ✔（这正是我们要的：只回滚这一行绑定）。
            async with db.begin_nested():
                db.add(binding)
                await db.flush()
        except IntegrityError:
            # 并发：另一个事务先建了 ⇒ 重读那一行
            existing = (
                await db.execute(
                    select(ProjectSignatureMatrixBinding).where(
                        ProjectSignatureMatrixBinding.project_id == project_id,
                        ProjectSignatureMatrixBinding.module == cls.CHANGE_NOTICE_MODULE,
                    )
                )
            ).scalar_one_or_none()
            if existing is None:
                raise
            # ⚠️ **不覆盖**赢家的 matrix_id：并发下「最后写入者胜」会让
            # 输家**静默改掉**赢家的绑定（lost update）。
            return existing
        return binding


__all__ = [
    "MatrixStep",
    "SignatureMatrixService",
]
