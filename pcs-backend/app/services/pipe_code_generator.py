"""PipeCodeGenerator — 管道代码生成/验证（SUP-002 §11.5 + FMT-OPEN-01 scope）。

- generate()：按项目 PUBLISHED 配置的 format_definition_json 拼接管道代码。
  auto_increment 段调用 ``_next_sequence()``（UPSERT 原子自增，10 并发全部唯一）。
- validate()：反向解析管道代码段，回填 segments dict。
- FMT-OPEN-01：scope_key 默认 ``f"{project_id}:{stream_symbol}"``，项目内
  与 stream_symbol 联动；同 stream_symbol 内从 1 起递增。
"""
from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.pipe_code_template import (
    PipeCodeTemplate,
    ProjectPipeCodeConfig,
)
from app.services.exceptions import PcsError
from app.services.stream_symbol_service import StreamSymbolService


@dataclass
class ValidationOutcome:
    valid: bool
    errors: list[str] = field(default_factory=list)
    segments: dict = field(default_factory=dict)


class PipeCodeGenerator:
    """FMT 段生成器 + 验证器。"""

    # ---------- 内部工具 ----------

    @classmethod
    async def _get_effective_format(
        cls, db: AsyncSession, project_id: uuid.UUID,
    ) -> tuple[uuid.UUID, dict]:
        """项目级 PUBLISHED 配置优先；无则退回公司级 PUBLISHED 模板。

        Returns ``(config_id, fmt)``。config_id 用于 ``_next_sequence`` 计数；
        当回退到公司级模板时，构造一个 stable pseudo-id（template_id）以便
        计数器仍可工作。
        """
        cfg = (
            await db.execute(
                select(ProjectPipeCodeConfig).where(
                    ProjectPipeCodeConfig.project_id == project_id,
                    ProjectPipeCodeConfig.status == "PUBLISHED",
                ).order_by(ProjectPipeCodeConfig.created_at.desc()).limit(1)
            )
        ).scalar_one_or_none()
        if cfg:
            return cfg.config_id, cfg.format_definition_json
        # 公司级 PUBLISHED 回退：用最新的一个
        tpl = (
            await db.execute(
                select(PipeCodeTemplate).where(
                    PipeCodeTemplate.status == "PUBLISHED",
                ).order_by(PipeCodeTemplate.created_at.desc()).limit(1)
            )
        ).scalar_one_or_none()
        if tpl:
            return tpl.template_id, tpl.format_definition_json
        raise PcsError(
            f"项目 {project_id} 无已发布的管道代码配置",
            code="PIPE_CODE_NO_CONFIG",
            status=409,
        )

    @classmethod
    async def _next_sequence(
        cls,
        db: AsyncSession,
        counter_id: uuid.UUID,
        scope_key: str,
    ) -> int:
        """原子自增；10 并发全部唯一。

        使用 Postgres UPSERT (``INSERT ... ON CONFLICT DO UPDATE``) 保证
        一次性写入 + 自增 + 返回。SQLite 测试也支持 UPSERT（自 3.24）。
        """
        row = (
            await db.execute(
                text(
                    """
                    INSERT INTO project_pipe_code_sequences (config_id, scope_key, next_value)
                    VALUES (:cfg, :scope, 2)
                    ON CONFLICT (config_id, scope_key)
                    DO UPDATE SET next_value = project_pipe_code_sequences.next_value + 1
                    RETURNING next_value - 1 AS value
                    """
                ),
                {"cfg": str(counter_id), "scope": scope_key},
            )
        ).first()
        await db.commit()
        return int(row.value)

    @classmethod
    async def _project_symbol_keys(
        cls, db: AsyncSession, project_id: uuid.UUID,
    ) -> set[str]:
        items = await StreamSymbolService.list_project(
            db, project_id=project_id, include_company=True,
        )
        return {it["symbol"] for it in items if it.get("is_active", True)}

    # ---------- 生成 ----------

    @classmethod
    async def generate(
        cls,
        db: AsyncSession,
        project_id: uuid.UUID,
        input_segments: dict | None = None,
    ) -> str:
        config_id, fmt = await cls._get_effective_format(db, project_id)
        segments = sorted(
            fmt.get("segments") or [],
            key=lambda s: s.get("position", 0),
        )
        separator = fmt.get("separator", "") or ""
        input_segments = input_segments or {}
        code_parts: list[str] = []
        sym_value: str | None = input_segments.get("stream_symbol")

        sym_keys = await cls._project_symbol_keys(db, project_id)
        for seg in segments:
            t = seg.get("type")
            if t == "delimiter":
                sep = str(seg.get("separator", separator) or "")
                code_parts.append(sep)
                continue
            if t == "stream_symbol":
                if not sym_value:
                    raise PcsError(
                        "stream_symbol 段必须提供",
                        code="PIPE_CODE_MISSING_SYM",
                        status=422,
                    )
                if sym_keys and sym_value not in sym_keys:
                    raise PcsError(
                        f"符号 {sym_value} 不在项目有效符号表",
                        code="PIPE_CODE_BAD_SYMBOL",
                        status=422,
                    )
                code_parts.append(sym_value)
            elif t == "auto_increment":
                scope_key = f"{project_id}:{sym_value}" if sym_value else f"{project_id}:default"
                nxt = await cls._next_sequence(db, config_id, scope_key)
                length = int(seg.get("length", 3) or 1)
                code_parts.append(str(nxt).zfill(length))
            elif t == "enum":
                v = input_segments.get(seg.get("key", ""))
                if v is None:
                    if seg.get("required", True):
                        raise PcsError(
                            f"枚举段 {seg.get('key')!s} 必填",
                            code="PIPE_CODE_MISSING_ENUM",
                            status=422,
                        )
                    continue
                if v not in (seg.get("values") or []):
                    raise PcsError(
                        f"枚举值 {v!s} 不在 {seg.get('values')!s}",
                        code="PIPE_CODE_BAD_ENUM",
                        status=422,
                    )
                code_parts.append(str(v))
            elif t == "constant":
                code_parts.append(str(seg.get("value", "") or ""))
            elif t == "free_text":
                v = input_segments.get(seg.get("key", ""), "")
                pattern = seg.get("regex")
                if pattern:
                    if not re.fullmatch(pattern, str(v)):
                        raise PcsError(
                            f"free_text 段 {seg.get('key')!s} 不匹配 {pattern!s}",
                            code="PIPE_CODE_BAD_REGEX",
                            status=422,
                        )
                code_parts.append(str(v))
            else:
                raise PcsError(
                    f"未知段类型 {t!s}",
                    code="PIPE_CODE_BAD_TYPE",
                    status=422,
                )

        # 拼接：段间插入 separator，跳过 delimiter 段自带 sep 的重复
        out = []
        prev_was_delimiter = False
        for i, part in enumerate(code_parts):
            if i == 0:
                out.append(part)
            else:
                seg = segments[i] if i < len(segments) else {}
                if seg.get("type") == "delimiter":
                    # delimiter 段的 part 直接是分隔符，已合并
                    out.append(part)
                elif prev_was_delimiter:
                    out.append(part)
                else:
                    out.append(separator)
                    out.append(part)
            prev_was_delimiter = (
                i < len(segments) and segments[i].get("type") == "delimiter"
            )
        return "".join(out)

    # ---------- 验证 ----------

    @classmethod
    async def validate(
        cls,
        db: AsyncSession,
        project_id: uuid.UUID,
        code: str,
    ) -> ValidationOutcome:
        """校验管号格式（dry-run，不落库）。

        步骤：
        1. 取项目内有效模板 (_get_effective_format)；
           失败 → ValidationOutcome(valid=False, errors=[...])，不抛异常
        2. 按 format.separator 切分 code（空 separator → 整体 1 段）
        3. 逐段校验（按 segments 顺序）：
           - auto_increment：必须全数字 + 长度 ≤ spec.length
           - stream_symbol：必须在项目有效符号表内
           - enum：值必须在 spec.values 白名单内
           - constant：值必须 = spec.value
           - free_text：可选 regex 校验
        4. 返回 ValidationOutcome{valid, errors[], segments{key: val}}

        与 generate 区别：validate 仅 dry-run，不写 Sequence、不落库；
        generate 走完整流程 + 落库 + 取号（写 ProjectPipeCodeSequence 自增 1）。
        """
        try:
            _, fmt = await cls._get_effective_format(db, project_id)
        except PcsError as e:
            return ValidationOutcome(valid=False, errors=[str(e)])
        segments = sorted(
            fmt.get("segments") or [],
            key=lambda s: s.get("position", 0),
        )
        # delimiter 段：作为分隔符在拼接时存在；解析时按 format 切片
        non_delim = [s for s in segments if s.get("type") != "delimiter"]
        sym_keys = await cls._project_symbol_keys(db, project_id)
        # 用 separator 切分（最简实现：适用于单字符 separator）
        sep = fmt.get("separator", "") or ""
        if sep:
            parts = code.split(sep)
        else:
            parts = [code]

        errors: list[str] = []
        out: dict = {}
        # 期望段数 = non_delim 段数
        if len(parts) < len(non_delim):
            errors.append(f"段数不足：期望 {len(non_delim)} 实际 {len(parts)}")
            return ValidationOutcome(valid=False, errors=errors, segments=out)
        for i, seg in enumerate(non_delim):
            t = seg.get("type")
            val = parts[i] if i < len(parts) else ""
            if t == "auto_increment":
                length = int(seg.get("length", 3) or 1)
                if not (val.isdigit() and len(val) <= length):
                    errors.append(
                        f"auto_increment 段 {val!r} 非数字或超长（≤{length}）",
                    )
                out[seg.get("key", f"seg{i}")] = val
            elif t == "stream_symbol":
                if sym_keys and val not in sym_keys:
                    errors.append(f"符号 {val!s} 不在项目有效符号表")
                out[seg.get("key", f"seg{i}")] = val
            elif t == "enum":
                if val not in (seg.get("values") or []):
                    errors.append(f"枚举值 {val!s} 不在 {seg.get('values')!s}")
                out[seg.get("key", f"seg{i}")] = val
            elif t == "constant":
                expected = str(seg.get("value", "") or "")
                if val != expected:
                    errors.append(f"常量段 {val!r} ≠ {expected!r}")
                out[seg.get("key", f"seg{i}")] = val
            elif t == "free_text":
                pattern = seg.get("regex")
                if pattern and not re.fullmatch(pattern, str(val)):
                    errors.append(f"free_text 段 {val!r} 不匹配 {pattern!s}")
                out[seg.get("key", f"seg{i}")] = val
        return ValidationOutcome(valid=not errors, errors=errors, segments=out)


__all__ = ["PipeCodeGenerator", "ValidationOutcome"]
