"""种**项目模板** + 一个**未占用的 FORMAL 工作区**（幂等）—— P10-K · W-0。

## 为什么这是**硬前置**

SPEC §7.5 的项目向导第 3 步「选模板」是**必选**⇒ ⇒ ⇒ 而

- `project_templates` 表**两库都是 0 行**（2026-11-24 实测）⇒ ⇒ ⇒
  `GET /api/v1/project-templates` **恒返空**⇒ ⇒ ⇒ 向导**卡死**；
- `pcs` 库**只有 1 个 FORMAL 工作区**、且**已被唯一项目占用**
  ⇒ ⇒ ⇒ 向导第 1 步的工作区下拉**恒空**⇒ ⇒ ⇒ ⇒ **没有它整个向导跑不起来**。

⇒ ⇒ ⇒ 本脚本是那两样东西的**唯一来源**（本批**没有发布端点** ——
模板的运营与发布流程另开 · **TODO-206**）。

## 为什么种**两条**模板（不是一条）

⚠️ `record_approval` ↔ `signature_matrix` **互斥**（`SignatureMatrixBinding`
的 docstring 明写「用其一即可」）⇒ ⇒ ⇒ **一条模板填不满 7 段**
⇒ ⇒ ⇒ ⇒ 所以：

| 模板 | 类型 | 填的段 |
|---|---|---|
| **A** | 签署矩阵型 | `signature_matrix` ✔ + `record_approval` ✘ + 其余 5 段 ✔ |
| **B** | 审批深度型 | `record_approval` ✔ + `signature_matrix` ✘ + 其余 5 段 ✔ |

⇒ ⇒ ⇒ **7 段在集合层面全覆盖** + 互斥被遵守。

## 幂等

- 模板按 `name` 查（已存在 ⇒ **更新**配置，不新增）；
- 签署矩阵按 `matrix_name` 查；管号模板按 `template_name` 查；
- 关联行（`project_template_pipe_classes`）按 `(template_id, class_id)` 查；
- 工作区按 `name` 查 ⇒ **已存在且未被占用** ⇒ 复用 ⇒ ⇒ ⇒ **不新建**
  ⇒ ⇒ ⇒（向导第 1 步的工作区下拉**不会因为多跑一次脚本就多一个**）。

⚠️ **口令从 `.env` 的 `DATABASE_URL` 读** —— **不要**出现在命令行。

用法：

    cd pcs-backend
    uv run python scripts/seed_project_templates.py
    uv run python scripts/seed_project_templates.py --dry-run
"""
# ruff: noqa — 一次性运维脚本（非 app 代码），单点收敛
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

# 允许 ``uv run python scripts/xxx.py`` 直接调用；app 包从 pcs-backend 根解析。
_BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from sqlalchemy import select  # noqa: E402

from app.db.session import get_async_session_factory  # noqa: E402
from app.models.config_domain import PipeClass, ProjectTemplate  # noqa: E402
from app.models.deliverable import SignatureMatrix  # noqa: E402
from app.models.enums import ProjectTemplateStatus  # noqa: E402
from app.models.pipe_code_template import PipeCodeTemplate  # noqa: E402
from app.models.project import Workspace  # noqa: E402
from app.models.project_template_pipe_class import ProjectTemplatePipeClass  # noqa: E402

#: 种出来的**模板名**（幂等的锚点）
TPL_A_NAME = "乙烯项目模板（签署矩阵型）"
TPL_B_NAME = "通用项目模板（审批深度型）"
#: 种出来的**签署矩阵名**（模板 A 引用它）
MATRIX_NAME = "TPL_SIGNATURE_MATRIX"
#: 种出来的**管号模板名**
PIPE_CODE_TEMPLATE_NAME = "TPL_PIPE_CODE"
#: 种出来的**未占用工作区名**
WORKSPACE_NAME = "FORMAL-未占用（模板向导用）"

#: 模板 A 的 7 段（签署矩阵型）—— ⚠️ **不含 `record_approval`**（互斥）
TPL_A_CONFIG: dict = {
    "stream_approval": {"max_depth": 2},
    "numbering": {
        "segments": [{"type": "PREFIX", "value": "P-"}, {"type": "SEQ", "value": None}],
        "separator": "-",
        "revision_separate": True,
    },
    "customer_approval": {"proxy_allowed": False, "attachment_required": True},
    "signature_matrix": {
        "matrix_name": MATRIX_NAME,
        "steps": [
            {"role": "DESIGNER", "level": 1, "required": True},
            {"role": "REVIEWER", "level": 2, "required": True},
        ],
    },
    "version_sequence": {
        "skip_alpha_versions": False,
        "allowed_purposes": ["DRAFT", "PUBLISHED"],
    },
    "reversal_role": {"reversal_approver_role": "APPROVER"},
}

#: 模板 B 的 7 段（审批深度型）—— ⚠️ **不含 `signature_matrix`**（互斥）
TPL_B_CONFIG: dict = {
    "record_approval": {
        "steps": [
            {"role": "DESIGNER", "level": 1, "required": True, "can_self_check": False},
            {"role": "REVIEWER", "level": 2, "required": True, "can_self_check": False},
        ]
    },
    "stream_approval": {"max_depth": 1},
    "numbering": {
        "segments": [{"type": "PREFIX", "value": "U-"}, {"type": "SEQ", "value": None}],
        "separator": "-",
        "revision_separate": True,
    },
    "customer_approval": {"proxy_allowed": True, "attachment_required": False},
    "version_sequence": {
        "skip_alpha_versions": True,
        "allowed_purposes": ["DRAFT", "PUBLISHED", "CHANGE_NOTICE"],
    },
    "reversal_role": {"reversal_approver_role": "APPROVER"},
}

#: 两个模板的**输入清单**（`checklist_json` ⇒ 落 `project_input_checklist`）
CHECKLIST_A: dict = {
    "items": [
        {
            "item_key": "bedd",
            "item_label": "BEDD 文档",
            "required": True,
            "module": "BEDD",
            "input_category": "REQUIRED",
        },
        {
            "item_key": "pms",
            "item_label": "PMS 材料规格",
            "required": True,
            "module": "PMS",
            "input_category": "REQUIRED",
        },
        {
            "item_key": "equipment_list",
            "item_label": "设备一览",
            "required": False,
            "module": "EQUIP",
            "input_category": "OPTIONAL",
        },
    ]
}
CHECKLIST_B: dict = {
    "items": [
        {
            "item_key": "bedd",
            "item_label": "BEDD 文档",
            "required": True,
            "module": "BEDD",
            "input_category": "REQUIRED",
        },
        {
            "item_key": "equipment_list",
            "item_label": "设备一览",
            "required": True,
            "module": "EQUIP",
            "input_category": "REQUIRED",
        },
    ]
}

#: 模板 A 的**默认单位制**（P10-K · TODO-210 · **D1 裁决**）
#:
#: ⚠️ **默认值语义** ⇒ ⇒ ⇒ 「用户显式选过 ⇒ ⇒ ⇒ **不覆盖**」⇒ ⇒ ⇒
#: ⇒ ⇒ ⇒ 向导第 1 步**没动过**单位制时 ⇒ ⇒ ⇒ 这个值**生效**。
TPL_A_UNIT_SYSTEM = "SI"

#: 模板 B 的**默认单位制**（**故意用 US** ⇒ ⇒ ⇒ 用来验「D1 的两条路径」
#: ⇒ ⇒ ⇒ —— ① 用户没动 ⇒ ⇒ ⇒ 生效（写成 US）② 用户选过 ⇒ ⇒ ⇒ 不覆盖）。
TPL_B_UNIT_SYSTEM = "US"

#: 模板 A 的 **BEDD 默认值**（P10-K · TODO-210 · **D3 裁决**）
#:
#: 形状 = `{"分组.字段": 值}` ⇒ ⇒ ⇒ apply 时**只填空缺** ⇒ ⇒ ⇒
#: ⇒ ⇒ ⇒ 与「输入清单」完全同款（按 key 幂等）⇒ ⇒ ⇒ 用户已填的不动。
TPL_A_BEDD_DEFAULTS: dict = {
    "meteorology.pressure": 101.325,
    "meteorology.temperature": 25.0,
    "flare.back_pressure": 101.325,
}

#: 模板 B 的 BEDD 默认值（**只一条** ⇒ ⇒ ⇒ 用来验「只填空缺」）
TPL_B_BEDD_DEFAULTS: dict = {
    "meteorology.pressure": 101.325,
}

PIPE_CODE_FORMAT: dict = {
    "segments": [
        {"type": "PREFIX", "value": "P-"},
        {"type": "SEQ", "value": None},
    ],
    "separator": "-",
    "revision_separate": True,
}


async def _seed(db, *, dry_run: bool) -> None:
    # ---- ① 签署矩阵（模板 A 引用它）---------------------------------
    matrix = (
        await db.execute(
            select(SignatureMatrix).where(SignatureMatrix.matrix_name == MATRIX_NAME)
        )
    ).scalar_one_or_none()
    if matrix is None:
        matrix = SignatureMatrix(
            matrix_name=MATRIX_NAME,
            module="RECORD",
            doc_type="RECORD",
            version_purpose="DRAFT",
            steps_json=[
                {
                    "step_order": 1,
                    "sign_role": "DESIGNER",
                    "required": True,
                    "can_self_check": False,
                    "can_skip": False,
                },
                {
                    "step_order": 2,
                    "sign_role": "REVIEWER",
                    "required": True,
                    "can_self_check": False,
                    "can_skip": False,
                },
            ],
            status="ACTIVE",
        )
        db.add(matrix)
        print(f"+ 签署矩阵 {MATRIX_NAME}")
    else:
        print(f"= 签署矩阵 {MATRIX_NAME}（已存在）")

    # ---- ② 公司级管号模板 --------------------------------------------
    pipe_tpl = (
        await db.execute(
            select(PipeCodeTemplate).where(
                PipeCodeTemplate.template_name == PIPE_CODE_TEMPLATE_NAME
            )
        )
    ).scalar_one_or_none()
    if pipe_tpl is None:
        pipe_tpl = PipeCodeTemplate(
            template_name=PIPE_CODE_TEMPLATE_NAME,
            description="项目模板附带的默认管号格式",
            format_definition_json=PIPE_CODE_FORMAT,
            status="PUBLISHED",
            version="1",
        )
        db.add(pipe_tpl)
        print(f"+ 管号模板 {PIPE_CODE_TEMPLATE_NAME}")
    else:
        print(f"= 管号模板 {PIPE_CODE_TEMPLATE_NAME}（已存在）")

    await db.flush()

    # ---- ③ 两条已发布模板 --------------------------------------------
    for name, cfg, checklist, pipe_id, unit_system, bedd_defaults in (
        (TPL_A_NAME, TPL_A_CONFIG, CHECKLIST_A, pipe_tpl.template_id,
         TPL_A_UNIT_SYSTEM, TPL_A_BEDD_DEFAULTS),
        (TPL_B_NAME, TPL_B_CONFIG, CHECKLIST_B, pipe_tpl.template_id,
         TPL_B_UNIT_SYSTEM, TPL_B_BEDD_DEFAULTS),
    ):
        tpl = (
            await db.execute(select(ProjectTemplate).where(ProjectTemplate.name == name))
        ).scalar_one_or_none()
        if tpl is None:
            tpl = ProjectTemplate(
                name=name,
                industry="CHEMICAL",
                default_config_json=cfg,
                version="1.0.0",
                status=ProjectTemplateStatus.PUBLISHED.value,
                checklist_json=checklist,
                pipe_code_template_id=pipe_id,
                unit_system=unit_system,
                bedd_defaults_json=bedd_defaults,
            )
            db.add(tpl)
            print(f"+ 项目模板 {name}")
        else:
            tpl.default_config_json = cfg
            tpl.checklist_json = checklist
            tpl.pipe_code_template_id = pipe_id
            tpl.status = ProjectTemplateStatus.PUBLISHED.value
            tpl.unit_system = unit_system
            tpl.bedd_defaults_json = bedd_defaults
            print(f"= 项目模板 {name}（已存在 ⇒ 已更新配置）")
        await db.flush()

        # ---- ④ 默认管道等级关联（**有等级才建**）----------------------
        classes = (
            await db.execute(select(PipeClass.class_id).order_by(PipeClass.class_id))
        ).scalars().all()
        for class_id in classes[:3]:
            exists = (
                await db.execute(
                    select(ProjectTemplatePipeClass).where(
                        ProjectTemplatePipeClass.template_id == tpl.template_id,
                        ProjectTemplatePipeClass.class_id == class_id,
                    )
                )
            ).scalar_one_or_none()
            if exists is None:
                db.add(
                    ProjectTemplatePipeClass(
                        template_id=tpl.template_id, class_id=class_id
                    )
                )
        print(f"  默认等级关联：{len(classes[:3])} 条（库里共 {len(classes)} 个等级）")

    # ---- ⑤ 一个**未占用**的 FORMAL 工作区 ----------------------------
    ws = (
        await db.execute(select(Workspace).where(Workspace.name == WORKSPACE_NAME))
    ).scalar_one_or_none()
    if ws is None:
        db.add(
            Workspace(
                workspace_type="FORMAL",
                name=WORKSPACE_NAME,
                status="ACTIVE",
                project_id=None,
            )
        )
        print(f"+ 工作区 {WORKSPACE_NAME}（未被占用 ⇒ 向导第 1 步可选）")
    elif ws.project_id is None:
        print(f"= 工作区 {WORKSPACE_NAME}（已存在且未被占用）")
    else:
        print(
            f"⚠️ 工作区 {WORKSPACE_NAME} **已被项目占用**（{ws.project_id}）"
            "⇒ ⇒ ⇒ 向导第 1 步的工作区下拉会是空的 ⇒ ⇒ ⇒ 换一个名字重跑本脚本"
        )

    if dry_run:
        print("\n--dry-run ⇒ 不提交")
        return
    await db.commit()
    print("\n✅ seed 完成")


def main() -> None:
    parser = argparse.ArgumentParser(description="种项目模板 + 未占用 FORMAL 工作区")
    parser.add_argument("--dry-run", action="store_true", help="只打印，不提交")
    args = parser.parse_args()

    async def run() -> None:
        factory = get_async_session_factory()
        async with factory() as db:
            await _seed(db, dry_run=args.dry_run)

    asyncio.run(run())


if __name__ == "__main__":
    main()
