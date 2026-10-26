"""NumberingService — 文档编号原子自增 + UNIQUE 约束防并发（Task 2.7）。

SELECT ... FOR UPDATE 行锁串行化同 scope 的并发 + UNIQUE 约束兜底。
写 audit：reset() 必须留痕（counter 被人重置是高敏操作）。

实现注意（与 brief 偏差，防御性）：
1. 补全 brief 缺失的 `AsyncSession` import（brief 仅 import `from sqlalchemy import select`）。
2. `reset()` 在 composite resource_id 超过 100 字符时由 AuditService 自动截断
   （audit_service.py:52）；UUID 36 + "/" + 36 + "/" + scope_key<=50 = 124 上限，
   实际 scope_key 默认 "scope_A" (7 chars) → 81 chars，安全。
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.config_domain import DocNoSequence, NumberingTemplate
from app.models.enums import AuditAction
from app.services.audit_service import AuditService


class SequenceNotFoundError(Exception):
    """查不到指定 DocNoSequence 时抛出。"""


class NumberingService:
    """文档号计数服务（DICT V3.4 §68）。

    业务：next_value 按 (project, template, scope) 行锁（SELECT ... FOR UPDATE）
    Postgres 串行化同 scope 并发取号；DICT V3.4 §68 维护 doc_no_sequences 表，
    防高并发下文档号跳号或重复。
    """

    #: 内置**变更单**编号模板（TODO-073）：变更单的编号要走模板 ⇒ 可读。
    #: ⚠️ 模板名**全局唯一**（迁移 `p9_009`）⇒ 并发建模板时靠它兜底。
    CHANGE_NOTICE_TEMPLATE_NAME = "变更单编号模板"

    #: 变更单编号的段：`{项目号}-{文档类型}-{序号}`（P2 计划 §3.5 的段约定）。
    CHANGE_NOTICE_SEGMENTS: list[str] = ["project_no", "-", "doc_type", "-", "seq"]

    def __init__(self, session: AsyncSession):
        """构造 NumberingService（注入 session + AuditService 写取号审计）。"""
        self.session = session
        self.audit = AuditService(session)

    async def get_or_create_change_notice_template(self) -> NumberingTemplate:
        """内置**变更单**编号模板（**幂等**：有就用，没有才建）。

        ## 为什么变更单要自己的模板

        变更单的编号是给用户看的（要口述、要检索）⇒ `CN-{32 位 uuid hex}`
        不可读 ⇒ 走模板渲染成 `{项目号}-CHANGE_NOTICE-{序号}`。

        ## 并发

        「先查后建」挡不住两个事务同时建 ⇒ 靠 `template_name` 的**唯一约束**
        （迁移 `p9_009`）兜底 ⇒ 撞约束 ⇒ **重读**赢家那一行（而不是 500）。
        ⚠️ **SAVEPOINT 必须包住 `db.add`**（见
        `signature_matrix_service._ensure_binding` 的同款注释：savepoint 之外
        的 INSERT 撞约束会**中止整个事务** ⇒ 外层一起回滚）。
        """
        template = (
            await self.session.execute(
                select(NumberingTemplate).where(
                    NumberingTemplate.template_name == self.CHANGE_NOTICE_TEMPLATE_NAME
                )
            )
        ).scalar_one_or_none()
        if template is not None:
            return template

        template = NumberingTemplate(
            template_name=self.CHANGE_NOTICE_TEMPLATE_NAME,
            description="CHANGE_NOTICE",
            segments_json=list(self.CHANGE_NOTICE_SEGMENTS),
            separator="-",
            status="ACTIVE",
        )
        try:
            async with self.session.begin_nested():
                self.session.add(template)
                await self.session.flush()
        except IntegrityError:
            existing = (
                await self.session.execute(
                    select(NumberingTemplate).where(
                        NumberingTemplate.template_name
                        == self.CHANGE_NOTICE_TEMPLATE_NAME
                    )
                )
            ).scalar_one_or_none()
            if existing is None:
                raise
            return existing
        return template

    async def next_value(self, project_id: UUID, template_id: UUID, scope_key: str) -> int:
        """取文档号下一个值（按 (project, template, scope) 行锁串行化）。

        步骤：
        1. SELECT ... FOR UPDATE 行锁（Postgres 串行化同 scope 并发取号）
        2. 行不存在则初始化（current_value=0）
        3. current_value += 1，flush 返回新值

        不主动 commit，flush 后由调用方负责（保证整笔业务原子）。
        返回新 current_value（≥1）。
        """
        # SELECT ... FOR UPDATE 行锁 — Postgres 串行化同 scope 的并发
        row = (await self.session.execute(
            select(DocNoSequence).where(
                DocNoSequence.project_id == project_id,
                DocNoSequence.template_id == template_id,
                DocNoSequence.scope_key == scope_key,
            ).with_for_update()
        )).scalar_one_or_none()
        if row is None:
            row = DocNoSequence(
                project_id=project_id,
                template_id=template_id,
                scope_key=scope_key,
                current_value=0,
            )
            self.session.add(row)
            await self.session.flush()
        row.current_value += 1
        await self.session.flush()
        return row.current_value

    async def reset(self, project_id, template_id, scope_key, *, new_value=0, actor: UUID) -> None:
        """重置文档号序列（管理员/纠错用）。

        步骤：
        1. SELECT ... FOR UPDATE 行锁（同 next_value，并发安全）
        2. 行不存在 → SequenceNotFoundError
        3. current_value = new_value（默认 0），flush
        4. 写 Audit CONFIG_VERSION_CREATED（resource_id 拼 {project/template/scope}）

        注意：重置操作不可逆，调用方应确认业务场景（编错回退、年初清零等）。
        不主动 commit（flush + Audit.write 后调用方负责）。
        """
        row = (await self.session.execute(
            select(DocNoSequence).where(
                DocNoSequence.project_id == project_id,
                DocNoSequence.template_id == template_id,
                DocNoSequence.scope_key == scope_key,
            ).with_for_update()
        )).scalar_one_or_none()
        if row is None:
            raise SequenceNotFoundError(f"未找到 scope={scope_key}")
        row.current_value = new_value
        await self.session.flush()
        await self.audit.write(
            user_id=actor,
            action=AuditAction.CONFIG_VERSION_CREATED,
            resource_type="doc_no_sequence",
            resource_id=f"{project_id}/{template_id}/{scope_key}",
        )