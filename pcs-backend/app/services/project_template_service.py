from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.config_domain import PipeClass, ProjectTemplate
from app.models.deliverable import (
    ProjectSignatureMatrixBinding,
    SignatureMatrix,
)
from app.models.enums import ProjectTemplateStatus
from app.models.project import Project
from app.models.pipe_code_template import PipeCodeTemplate, ProjectPipeCodeConfig
from app.models.project_template_pipe_class import ProjectTemplatePipeClass
from app.models.system import ProjectInputChecklist
from app.schemas.project_template import (
    ProjectTemplateConfig,
    ProjectTemplateSummary,
    UnitSystemSource,
)
from app.services.exceptions import PcsError
from app.services.signature_matrix_service import SignatureMatrixService


def _checklist_item_count(checklist_json: Any) -> int:
    """模板的输入清单**条目数**（列表页显示用）。

    ⚠️ **形状不校验** —— `checklist_json` 是**手写 JSON** ⇒ ⇒ ⇒ 形状可能
    不对 ⇒ ⇒ ⇒ 这里**只数 `items` 列表** ⇒ ⇒ ⇒ 形状不对 ⇒ ⇒ ⇒ **当 0**
    ⇒ ⇒ ⇒（不是 500 —— 列表页不该因为一条脏数据整个挂掉）。
    """
    if not isinstance(checklist_json, dict):
        return 0
    items = checklist_json.get("items")
    return len(items) if isinstance(items, list) else 0


class ProjectTemplateService:
    """项目模板服务（template_files + ProjectTemplate + ProjectTemplateConfig）。

    业务：承载项目模板元数据 + 模板配置 JSON（Pydantic v2 ProjectTemplateConfig 强类型
    校验）；validate_config 失败抛 PcsError(TEMPLATE_CONFIG_INVALID)；
    create_from_template 实例化模板为项目（带 workspace_id）。
    """

    @staticmethod
    def validate_config(raw: dict) -> ProjectTemplateConfig:
        """Pydantic v2 验证 default_config_json；失败抛 PcsError(TEMPLATE_CONFIG_INVALID)。"""
        try:
            return ProjectTemplateConfig.model_validate(raw)
        except Exception as e:
            raise PcsError(
                f"ProjectTemplate.default_config_json 验证失败：{e}",
                code="TEMPLATE_CONFIG_INVALID",
                status=422,
                details={"validation_error": str(e), "raw_keys": list(raw.keys())},
            ) from e

    @classmethod
    async def load(cls, db: AsyncSession, template_id: UUID) -> ProjectTemplate:
        """加载 ProjectTemplate，自动验证 default_config_json。"""
        tpl = await db.get(ProjectTemplate, template_id)
        if not tpl:
            raise PcsError(
                f"ProjectTemplate {template_id} 不存在",
                code="TEMPLATE_NOT_FOUND",
                status=404,
            )
        if tpl.default_config_json:
            cls.validate_config(tpl.default_config_json)
        return tpl

    # ----- INT-1：模板级默认等级（PC-OPEN-04 自动 fork 入口） -----

    @classmethod
    async def get_default_pipe_class_ids(
        cls, db: AsyncSession, template_id: UUID,
    ) -> list[str]:
        """PC-OPEN-04：取模板默认等级清单（按 class_id 排序）。"""
        rows = (await db.execute(
            select(ProjectTemplatePipeClass.class_id)
            .where(ProjectTemplatePipeClass.template_id == template_id)
            .order_by(ProjectTemplatePipeClass.class_id)
        )).all()
        return [r.class_id for r in rows]

    @classmethod
    async def get_pipe_code_template_id(
        cls, db: AsyncSession, template_id: UUID,
    ) -> UUID | None:
        """取模板指定的默认管道代码模板。"""
        tpl = await cls.load(db, template_id)
        return tpl.pipe_code_template_id

    @classmethod
    async def set_default_pipe_classes(
        cls,
        db: AsyncSession,
        template_id: UUID,
        class_ids: list[str],
        actor,
    ) -> None:
        """替换模板默认等级清单（PC-OPEN-04 写入；替换语义）。"""
        # 1. 校验等级存在（避免 FK 悬空）
        if class_ids:
            rows = (await db.execute(
                select(PipeClass.class_id).where(PipeClass.class_id.in_(class_ids))
            )).all()
            existing = {r.class_id for r in rows}
            missing = set(class_ids) - existing
            if missing:
                raise PcsError(
                    f"等级 {sorted(missing)} 不存在",
                    code="PIPE_CLASS_NOT_FOUND",
                    status=404,
                )
        # 2. 清空旧关联
        await db.execute(
            ProjectTemplatePipeClass.__table__.delete()
            .where(ProjectTemplatePipeClass.template_id == template_id)
        )
        # 3. 写入新关联
        for cid in class_ids:
            db.add(ProjectTemplatePipeClass(template_id=template_id, class_id=cid))
        await db.commit()
    # ------------------------------------------------------------------
    # P10-K · W-3 / W-3c / W-3d：模板列表 + 应用到项目
    # ------------------------------------------------------------------

    @classmethod
    async def list_published(cls, db: AsyncSession) -> list["ProjectTemplateSummary"]:
        """**已发布**模板列表（`status='PUBLISHED'`）+ 批量取默认等级（**无 N+1**）。

        ⚠️ **为什么批量**：`get_default_pipe_class_ids`（`:52-61`）**每模板一次
        查询** ⇒ ⇒ ⇒ N 个模板 = N+1 次查询 ⇒ ⇒ ⇒ ⇒ 改成**一次**查全部
        ⇒ ⇒ ⇒ 在 Python 里按 template_id 分组 ⇒ ⇒ ⇒ 查询数恒为 2。

        ⚠️ **为什么只列 PUBLISHED**：模板**没有发布端点**（本批只有 seed 写
        PUBLISHED · 运营流程另开 · TODO-206）⇒ ⇒ ⇒ ⇒ 列 DRAFT/OBSOLETE
        ⇒ ⇒ ⇒ 会让用户选到**没人审核过**的模板。
        """
        rows = (
            await db.execute(
                select(ProjectTemplate)
                .where(ProjectTemplate.status == ProjectTemplateStatus.PUBLISHED.value)
                .order_by(ProjectTemplate.name)
            )
        ).scalars().all()
        if not rows:
            return []
        ids = [r.template_id for r in rows]
        pairs = (
            await db.execute(
                select(
                    ProjectTemplatePipeClass.template_id,
                    ProjectTemplatePipeClass.class_id,
                )
                .where(ProjectTemplatePipeClass.template_id.in_(ids))
                .order_by(ProjectTemplatePipeClass.class_id)
            )
        ).all()
        by_template: dict[UUID, list[str]] = {}
        for tid, cid in pairs:
            by_template.setdefault(tid, []).append(cid)
        out: list[ProjectTemplateSummary] = []
        for r in rows:
            out.append(
                ProjectTemplateSummary(
                    template_id=r.template_id,
                    name=r.name,
                    industry=r.industry,
                    version=r.version,
                    status=r.status,
                    default_pipe_class_ids=by_template.get(r.template_id, []),
                    checklist_item_count=_checklist_item_count(r.checklist_json),
                    # ⚠️ 模板的**默认**单位制（D1）⇒ ⇒ ⇒ 向导据此告知
                    # 「模板是 US，你选的是 SI ⇒ 以你的为准」
                    unit_system=r.unit_system,
                )
            )
        return out

    @classmethod
    async def apply_to_project(
        cls,
        db: AsyncSession,
        *,
        project_id: uuid.UUID,
        template_id: UUID,
        actor: Any,
        unit_system_source: str = UnitSystemSource.FORM.value,
    ) -> dict[str, Any]:
        """把模板应用到项目（**同一事务** · **幂等** · P10-K · W-3d）。

        ## 7 段落在哪（人裁 2026-11-25）

        | 段 | 落点 |
        |---|---|
        | `signature_matrix` | `project_signature_matrix_bindings`（**唯一干净落点**）|
        | `record_approval` | **条件化改绑** —— 只替「自动绑的默认」，**不夺人工绑定** |
        | `pipe_code_template_id` | 项目管号配置 **fork**（带 `source_template_id` 溯源）|
        | `numbering` | **对齐**（随管号 fork 落）⇒ ⇒ ⇒ **不另建**（与管号子系统语义重叠）|
        | `checklist_json` | `project_input_checklist` 行（**按 item_key 幂等**）|
        | `stream_approval` | `projects.stream_approval_max_depth` |
        | `customer_approval` | `projects.customer_approval_proxy_allowed` + `_attachment_required` |
        | `version_sequence` | `projects.version_sequence_skip_alpha_versions` + `_allowed_purposes` |
        | `reversal_role` | `projects.reversal_role_reversal_approver_role` |

        ⚠️ **同一事务**：任一段失败 ⇒ ⇒ ⇒ **全部回滚** ⇒ ⇒ ⇒ 项目不会被
        配成「一半模板、一半默认」⇒ ⇒ ⇒ ⇒ 所以本方法**不 commit**
        ⇒ ⇒ ⇒（事务边界归调用方 · 端点 commit 一次）。

        ⚠️ **幂等**：重复应用同一模板 ⇒ ⇒ ⇒ 结果**相同**、**不产生重复行**
        ⇒ ⇒ ⇒（管号配置按名字查 · 清单按 item_key 查 · 矩阵按名字查）。

        ⚠️ **`record_approval` 只替「自动绑的默认」** ——
        `ensure_default_record_matrix`（`signature_matrix_service.py:751-758`）
        明写「**不覆盖：人工改过的绑定不被夺走**」⇒ ⇒ ⇒ ⇒ 「谁该签」的
        决定权**不在系统手里** ⇒ ⇒ ⇒ 模板**也不夺**。
        """
        tpl = await cls.load(db, template_id)
        if tpl.status != ProjectTemplateStatus.PUBLISHED.value:
            raise PcsError(
                f"模板 {template_id} 的状态是 {tpl.status} ⇒ ⇒ ⇒ 只有 PUBLISHED 的模板能应用。",
                code="TEMPLATE_NOT_PUBLISHED",
                status=409,
            )
        cfg = cls.validate_config(tpl.default_config_json or {})
        project = (
            await db.execute(select(Project).where(Project.project_id == project_id))
        ).scalar_one_or_none()
        if project is None:
            raise PcsError(
                f"Project not found: {project_id}", code="PROJECT_NOT_FOUND", status=404
            )

        segments: dict[str, str] = {}

        # ---- ① signature_matrix → 绑定 --------------------------------
        if cfg.signature_matrix is not None:
            matrix = (
                await db.execute(
                    select(SignatureMatrix).where(
                        SignatureMatrix.matrix_name == cfg.signature_matrix.matrix_name,
                        SignatureMatrix.status == "ACTIVE",
                    )
                )
            ).scalars().first()
            if matrix is None:
                raise PcsError(
                    f"模板引用的签署矩阵「{cfg.signature_matrix.matrix_name}」不存在"
                    "（或不是 ACTIVE）⇒ ⇒ ⇒ 无法绑定。",
                    code="TEMPLATE_MATRIX_NOT_FOUND",
                    status=422,
                )
            module = matrix.module or SignatureMatrixService.RECORD_MODULE
            await cls._upsert_binding(
                db, project_id=project_id, module=module, matrix_id=matrix.matrix_id
            )
            segments["signature_matrix"] = f"bound:{matrix.matrix_name}"

        # ---- ② record_approval → 条件化改绑 ---------------------------
        if cfg.record_approval is not None:
            segments["record_approval"] = await cls._apply_record_approval(
                db, project_id=project_id, project=project, cfg=cfg
            )

        # ---- ③ pipe_code_template_id → fork ---------------------------
        if tpl.pipe_code_template_id is not None:
            segments["pipe_code_template_id"] = await cls._fork_pipe_code_config(
                db, project_id=project_id, template_id=tpl.pipe_code_template_id,
                config_name=f"{tpl.name} 管号配置", actor=actor,
            )

        # ---- ④ numbering → 对齐（不另建）------------------------------
        if cfg.numbering is not None:
            segments["numbering"] = "aligned_with_pipe_code_config"

        # ---- ⑤ checklist_json → 输入清单行 ---------------------------
        if tpl.checklist_json:
            segments["checklist_json"] = await cls._seed_checklist(
                db, project_id=project_id, checklist_json=tpl.checklist_json
            )

        # ---- ⑥~⑨ 4 段 typed 列 ----------------------------------------
        if cfg.stream_approval is not None:
            project.stream_approval_max_depth = cfg.stream_approval.max_depth
            segments["stream_approval"] = "applied"
        if cfg.customer_approval is not None:
            project.customer_approval_proxy_allowed = cfg.customer_approval.proxy_allowed
            project.customer_approval_attachment_required = (
                cfg.customer_approval.attachment_required
            )
            segments["customer_approval"] = "applied"
        if cfg.version_sequence is not None:
            project.version_sequence_skip_alpha_versions = (
                cfg.version_sequence.skip_alpha_versions
            )
            project.version_sequence_allowed_purposes = list(
                cfg.version_sequence.allowed_purposes
            )
            segments["version_sequence"] = "applied"
        if cfg.reversal_role is not None:
            project.reversal_role_reversal_approver_role = (
                cfg.reversal_role.reversal_approver_role
            )
            segments["reversal_role"] = "applied"

        # ---- ⑦ 模板的**默认单位制**（D1）--------------------------------
        # ⚠️ **默认值语义** ⇒ ⇒ ⇒ 「用户显式选过 ⇒ ⇒ ⇒ **不覆盖**」
        # ⇒ ⇒ ⇒ 「用户动没动过」由**调用方**说（`unit_system_source`）
        # ⇒ ⇒ ⇒ 后端**不猜**（猜错 = 静默推翻用户的显式选择）。
        # ⚠️ 模板**没带**默认单位制（NULL）⇒ ⇒ ⇒ 什么都不做。
        if unit_system_source == UnitSystemSource.TEMPLATE.value:
            if tpl.unit_system:
                project.unit_system = tpl.unit_system
                segments["unit_system"] = f"applied:{tpl.unit_system}"
            else:
                segments["unit_system"] = "skipped_no_template_default"
        else:
            segments["unit_system"] = "kept_form_value"

        # ---- ⑧ 模板的 **BEDD 默认值**（D3）------------------------------
        if tpl.bedd_defaults_json:
            segments["bedd_defaults"] = await cls._apply_bedd_defaults(
                db, project=project, defaults=tpl.bedd_defaults_json
            )

        # ---- provenance ------------------------------------------------
        project.applied_template_json = {
            "template_id": str(tpl.template_id),
            "template_name": tpl.name,
            "template_version": tpl.version,
            "applied_at": datetime.now(UTC).isoformat(),
            "applied_by": str(getattr(actor, "user_id", "") or ""),
            "segments": segments,
        }
        await db.flush()
        return {
            "template_id": str(tpl.template_id),
            "template_name": tpl.name,
            "template_version": tpl.version,
            "segments": segments,
        }

    # ------------------------------------------------------------------
    # apply_to_project 的分步实现
    # ------------------------------------------------------------------

    @classmethod
    async def _upsert_binding(
        cls, db: AsyncSession, *, project_id: uuid.UUID, module: str, matrix_id: uuid.UUID
    ) -> None:
        """绑（或改绑）项目 × 模块的签署矩阵（**幂等**）。

        ⚠️ **唯一约束兜底**：`uq_project_signature_matrix_bindings_project_module`
        ⇒ ⇒ ⇒ 并发下两个事务都可能想建 ⇒ ⇒ ⇒ 撞约束 ⇒ ⇒ ⇒ **重读**那一行
        ⇒ ⇒ ⇒（与 `SignatureMatrixService._ensure_binding` 同款处置）。
        """
        binding = (
            await db.execute(
                select(ProjectSignatureMatrixBinding).where(
                    ProjectSignatureMatrixBinding.project_id == project_id,
                    ProjectSignatureMatrixBinding.module == module,
                )
            )
        ).scalar_one_or_none()
        if binding is not None:
            binding.matrix_id = matrix_id
            return
        db.add(
            ProjectSignatureMatrixBinding(
                project_id=project_id, module=module, matrix_id=matrix_id
            )
        )
        try:
            await db.flush()
        except IntegrityError:
            # ⇒ 并发下别人先建了 ⇒ 重读并改绑（不是 500）
            await db.rollback()
            again = (
                await db.execute(
                    select(ProjectSignatureMatrixBinding).where(
                        ProjectSignatureMatrixBinding.project_id == project_id,
                        ProjectSignatureMatrixBinding.module == module,
                    )
                )
            ).scalar_one_or_none()
            if again is None:
                raise
            again.matrix_id = matrix_id

    @classmethod
    async def _apply_record_approval(
        cls, db: AsyncSession, *, project_id: uuid.UUID, project: Project, cfg: ProjectTemplateConfig
    ) -> str:
        """`record_approval` 段 ⇒ ⇒ ⇒ **条件化改绑**。

        - **还没绑 RECORD 矩阵** ⇒ ⇒ ⇒ 建一份**由模板 steps 派生**的矩阵并绑上
          ⇒ ⇒ ⇒ 矩阵名**确定化**（`PRJ-{project_no}-RECORD-TPL`）⇒ ⇒ ⇒
          ⇒ ⇒ ⇒ **幂等**（重复应用不会堆出一串同名矩阵）；
        - **绑着「自动绑的默认」**（`DEFAULT_RECORD_3_LEVEL`）⇒ ⇒ ⇒ **替换**
          ⇒ ⇒ ⇒（这是模板该做的事）；
        - **绑着别的东西** ⇒ ⇒ ⇒ **不夺** ⇒ ⇒ ⇒ 返回
          `skipped_manual_binding` ⇒ ⇒ ⇒ 理由见 `ensure_default_record_matrix`
          的 docstring：「**谁该签**的决定权不在系统手里」。
        """
        matrix_name = f"PRJ-{project.project_no}-RECORD-TPL"
        binding = (
            await db.execute(
                select(ProjectSignatureMatrixBinding).where(
                    ProjectSignatureMatrixBinding.project_id == project_id,
                    ProjectSignatureMatrixBinding.module == SignatureMatrixService.RECORD_MODULE,
                )
            )
        ).scalar_one_or_none()
        default_matrix = (
            await db.execute(
                select(SignatureMatrix).where(
                    SignatureMatrix.matrix_name == SignatureMatrixService.DEFAULT_RECORD_MATRIX_NAME,
                    SignatureMatrix.status == "ACTIVE",
                )
            )
        ).scalars().first()

        if binding is not None:
            # ⚠️ **只在「绑着的确实是自动绑的默认」时才替换**
            # ⇒ ⇒ ⇒ 而**默认矩阵不存在**（项目没走过 ensure_default_record_matrix）
            # ⇒ ⇒ ⇒ ⇒ 那就**一律不夺** ⇒ ⇒ ⇒（保守：宁可不改，也不夺人工绑定）
            if default_matrix is None or binding.matrix_id != default_matrix.matrix_id:
                # ⚠️ **人工改过的绑定不被夺走**（与 ensure_default_record_matrix 同款）
                return "skipped_manual_binding"

        matrix = (
            await db.execute(
                select(SignatureMatrix).where(
                    SignatureMatrix.matrix_name == matrix_name,
                    SignatureMatrix.status == "ACTIVE",
                )
            )
        ).scalars().first()
        steps_json = [
            {
                "step_order": i + 1,
                "sign_role": s.role,
                "required": s.required,
                "can_self_check": s.can_self_check,
                "can_skip": s.can_skip,
            }
            for i, s in enumerate(cfg.record_approval.steps)
        ] if cfg.record_approval else []
        if matrix is None:
            matrix = SignatureMatrix(
                matrix_name=matrix_name,
                module=SignatureMatrixService.RECORD_MODULE,
                doc_type=SignatureMatrixService.RECORD_MODULE,
                version_purpose="DRAFT",
                steps_json=steps_json,
                status="ACTIVE",
            )
            db.add(matrix)
            await db.flush()
        else:
            # ⇒ 幂等重放 ⇒ 更新 steps（模板改了 ⇒ 派生矩阵跟着改）
            matrix.steps_json = steps_json
        await cls._upsert_binding(
            db,
            project_id=project_id,
            module=SignatureMatrixService.RECORD_MODULE,
            matrix_id=matrix.matrix_id,
        )
        return "applied"

    @classmethod
    async def _fork_pipe_code_config(
        cls,
        db: AsyncSession,
        *,
        project_id: uuid.UUID,
        template_id: uuid.UUID,
        config_name: str,
        actor: Any,
    ) -> str:
        """把公司级管号模板 fork 到项目（**幂等** · 同名字段已存在 ⇒ 跳过）。

        ⚠️ **为什么不直接调 `PipeCodeTemplateService.fork_to_project`** ——
        那个函数**自己 commit** ⇒ ⇒ ⇒ 调它就等于把「同一事务」破了
        ⇒ ⇒ ⇒ ⇒ 本批要求「7 段中任一段失败 ⇒ ⇒ ⇒ **全部回滚**」
        ⇒ ⇒ ⇒ ⇒ 所以这里**内联** fork 的那一小段（复制 ≠ 抄错：只 4 行），
        ⚠️ **事务边界归调用方**（端点 commit 一次）。
        """
        existing = (
            await db.execute(
                select(ProjectPipeCodeConfig).where(
                    ProjectPipeCodeConfig.project_id == project_id,
                    ProjectPipeCodeConfig.config_name == config_name,
                )
            )
        ).scalar_one_or_none()
        if existing is not None:
            return f"exists:{existing.config_name}"
        tpl = (
            await db.execute(
                select(PipeCodeTemplate).where(PipeCodeTemplate.template_id == template_id)
            )
        ).scalar_one_or_none()
        if tpl is None:
            raise PcsError(
                f"管号模板 {template_id} 不存在",
                code="PIPE_CODE_TEMPLATE_NOT_FOUND",
                status=404,
            )
        db.add(
            ProjectPipeCodeConfig(
                project_id=project_id,
                source_template_id=template_id,
                config_name=config_name,
                format_definition_json=tpl.format_definition_json,
                snapshot_json=tpl.format_definition_json,
                status="DRAFT",
                created_by=getattr(actor, "user_id", None),
            )
        )
        await db.flush()
        return f"forked:{config_name}"

    @classmethod
    async def _apply_bedd_defaults(
        cls, db: AsyncSession, *, project: Project, defaults: dict
    ) -> str:
        """把模板的 **BEDD 默认值**写进项目（**只填空缺** · D3 裁决）。

        ## 形状

        `{"分组.字段": 值}`（如 `{"meteorology.pressure": 101.325}`）
        ⇒ ⇒ ⇒ 与 BEDD 文档的形状（`{分组: {字段: 值}}`）**一一对应**。

        ## ⚠️ **只填空缺**（与「输入清单」**完全同款**）

        - 项目里**已经填了**的字段 ⇒ ⇒ ⇒ **不动**（用户的编辑不被模板冲掉）；
        - 空缺（**没有这个键**或值是 `None`）⇒ ⇒ ⇒ 填上模板的默认值；
        - ⇒ ⇒ ⇒ 重复 apply **幂等** ⇒ ⇒ ⇒ 用户的数据不丢。

        ## ⚠️ **字段路径要校验**

        路径不在 `BEDD_FIELDS` 里 ⇒ ⇒ ⇒ **422**（不是静默丢弃）
        ⇒ ⇒ ⇒ ⇒ 否则模板作者写错一个键 ⇒ ⇒ ⇒ 用户永远看不到那个字段
        ⇒ ⇒ ⇒ ⇒ 而模板看起来「生效了」。
        """
        from app.schemas.bedd import BEDD_FIELDS

        valid_paths: set[str] = set()
        for group_key, fields in BEDD_FIELDS.items():
            for field_key, *_rest in fields:
                valid_paths.add(f"{group_key}.{field_key}")

        unknown = [p for p in defaults if p not in valid_paths]
        if unknown:
            raise PcsError(
                f"模板的 BEDD 默认值里有**不存在的字段路径**：{sorted(unknown)}"
                f"（合法路径见 BEDD 的 {len(valid_paths)} 个字段）",
                code="TEMPLATE_BEDD_DEFAULTS_INVALID",
                status=422,
            )

        document = dict(project.bedd_json or {})
        filled = 0
        for path, value in defaults.items():
            group_key, field_key = path.split(".", 1)
            group = dict(document.get(group_key) or {})
            # ⚠️ **只填空缺** ⇒ ⇒ ⇒ 已填的值（哪怕是 0 / ""）**不动**
            if group.get(field_key) is not None:
                continue
            group[field_key] = value
            document[group_key] = group
            filled += 1
        project.bedd_json = document
        await db.flush()
        return f"filled:{filled}"

    @classmethod
    async def _seed_checklist(
        cls, db: AsyncSession, *, project_id: uuid.UUID, checklist_json: dict
    ) -> str:
        """把模板的输入清单**种进**项目（**按 item_key 幂等**）。

        ⚠️ **已存在的 item_key 不覆盖** ⇒ ⇒ ⇒ 人工填过的清单项**不会被
        模板冲掉** ⇒ ⇒ ⇒ （重放模板 ≠ 重置项目）。
        """
        items = checklist_json.get("items") if isinstance(checklist_json, dict) else None
        items = items or []
        if not items:
            return "empty"
        existing = set(
            (
                await db.execute(
                    select(ProjectInputChecklist.item_key).where(
                        ProjectInputChecklist.project_id == project_id
                    )
                )
            ).scalars().all()
        )
        added = 0
        for it in items:
            key = str(it.get("item_key") or "").strip()
            if not key or key in existing:
                continue
            db.add(
                ProjectInputChecklist(
                    project_id=project_id,
                    item_key=key,
                    item_label=str(it.get("item_label") or key),
                    required=bool(it.get("required", True)),
                    note=it.get("note"),
                    module=it.get("module"),
                    input_category=it.get("input_category"),
                    status="NOT_STARTED",
                )
            )
            existing.add(key)
            added += 1
        await db.flush()
        return f"seeded:{added}"
