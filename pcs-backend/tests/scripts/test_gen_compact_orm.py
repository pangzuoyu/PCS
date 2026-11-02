"""`scripts/gen_compact_orm.py` 的行为（TODO-103 · P9B-3 · T1）。

## 为什么这个文件存在

`docs/schema_compact_orm.md` 此前是 **2026-09-02 的手工快照**（53 张表），
ORM 现有 **107** 张 ⇒ 文件缺 54 张 ⇒ 被当成「照这张表手写 SQL」的依据时
**照着查不到的表去写 SQL**。

⇒ 生成器把它变成**派生产物**。但「加了脚本没人跑」与「脚本不存在」不可区分
（同 TODO-099 的教训）⇒ 这里钉住三件事：

1. 生成物**覆盖 ORM 的全部表**（不是某一份手工清单）；
2. 生成物与**仓库里那份**逐字一致（⇒ 改了 ORM 没重跑 ⇒ 这里红）；
3. 格式沿用历史文件的 `col|type!` 风格（`!` = NOT NULL，PK/FK 标记）。
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

_BACKEND_ROOT = Path(__file__).resolve().parents[2]
_SCRIPT = _BACKEND_ROOT / "scripts" / "gen_compact_orm.py"
_DOC = _BACKEND_ROOT / "docs" / "schema_compact_orm.md"


@pytest.fixture(scope="module")
def generator():
    """加载生成器模块（无副作用：只定义常量与函数）。"""
    spec = importlib.util.spec_from_file_location("gen_compact_orm", _SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def metadata():
    import app.models  # noqa: F401  触发全部 model 注册
    from app.db.base import Base

    return Base.metadata


def test_script_exists():
    assert _SCRIPT.exists(), "compact ORM 生成器不存在"


def test_generated_doc_covers_every_orm_table(generator, metadata):
    """⚠️ 核心断言：生成物**覆盖 ORM 的全部表**。

    这是「文件不再是手工快照」这条性质的**唯一**判据 ——
    少一张表 ⇒ 那张表就会从查询手册里消失 ⇒ 照着查不到的表去写 SQL。
    """
    text = generator.render(metadata)
    for name in metadata.tables:
        assert f"### {name}\n" in text, f"生成物缺表 {name}"


def test_generated_doc_is_in_sync_with_committed_file(generator, metadata):
    """⚠️ 改了 ORM 忘了重跑 ⇒ 这里红（而不是让过期文件继续躺在仓库里）。"""
    assert _DOC.exists(), "docs/schema_compact_orm.md 不存在"
    committed = _DOC.read_text(encoding="utf-8")
    fresh = generator.render(metadata)
    # 生成时间那一行每天会变 ⇒ 比对时把它抹掉，其余**逐字**比。
    def _normalize(t: str) -> str:
        return "\n".join(
            line for line in t.split("\n") if not line.startswith("> 生成时间：")
        )

    assert _normalize(committed) == _normalize(fresh), (
        "docs/schema_compact_orm.md 与 ORM 不同步 —— "
        "跑 `cd pcs-backend && uv run python scripts/gen_compact_orm.py`"
    )


def test_column_format_keeps_not_null_and_pk_markers(generator, metadata):
    """格式沿用历史文件的 `col|type!` 风格（`!` = NOT NULL，PK/FK 标记）。"""
    projects = metadata.tables["projects"]
    text = generator.render(metadata)
    line = next(
        line for line in text.split("\n") if line.startswith("  project_id|")
    )

    assert "project_id|CHARPK!" in line, line
    assert "project_no|str!" in line, line
    assert "workspace_id|CHARFK!" in line, line
    # 可空 UUID 列：无 `!`（`created_by` 可空 ⇒ `created_by|CHAR,`）
    assert "created_by|CHAR," in line, line
    assert "[UNIQUE: project_no]" in line, line

    # 可空列不带 `!`
    assert "project_name_cn|str," in line, line
    assert projects is not None


def test_every_table_gets_exactly_one_section(generator, metadata):
    """每张表恰好出现在一节里（不重复、不消失）。"""
    text = generator.render(metadata)
    for name in metadata.tables:
        assert text.count(f"### {name}\n") == 1, f"表 {name} 出现次数不对"
