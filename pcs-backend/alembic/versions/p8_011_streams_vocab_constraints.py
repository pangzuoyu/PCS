"""`streams` 的 phase / data_mode / source_type 加 CHECK + 新增 `raw_phase`。

## 为什么现在才补（2026-10-19，TODO-042 遗留）

2026-10-19 把这三个字段从裸 `str` 收紧成契约枚举（`StreamPhase` /
`StreamDataMode` / `StreamSourceType`，见 `app/models/enums.py`）。但**契约
比 DB 严**：`streams` 表上只有 `ck_streams_case_type` 一条 CHECK，这三列在
DB 层仍是自由字符串。于是出现一个不对称的局面：

- 走 API 写入 → Pydantic 422，值进不来；
- **直接 SQL / 脚本 / 未来的 service 绕过 schema 写入 → 照进不误**，
  直到下次 GET 的**响应校验**才 500 —— 写入现场与报错现场分离，
  是最难查的一类（p8_008 的 docstring 描述过同一类痛点）。

⇒ 契约收窄了就该把 DB 侧也收窄，让「写不进」发生在写入现场而不是读取现场。

## 三个 CHECK 的取值从哪来（**不是从 description 抄的**）

description 本身就不可信，这是 bug-191 的实测结论：

| 字段 | description 写的 | 实际 | 后果 |
|---|---|---|---|
| `source_type` | 5 个 | **13 个** | 照它写会砍掉全部 10 个 `*_CALCULATED` 出口流值 |
| `sign_status` | 4 态 | **9 态**（PG enum `streamsignstatus`） | 照它写会拒掉 5 个合法值 |

⇒ 本迁移的值**直接引用枚举**（`app/models/enums.py` 是唯一来源），
并在迁移模块里断言「ORM 枚举的取值集合 == 这里写进 CHECK 的集合」——
两处再次漂移时这条迁移自己会红。

## 为什么加 `raw_phase`

`import_service._phase_norm` 对词表外的相态字母（`SUPERHEATED` 等）
一律置 None —— 这是 2026-10-19 收窄时定的（此前是 `return p` 原样放行，
会把非法值写进枚举列）。但**原始字母被丢弃**，用户看到的是「相态没填」，
完全不知道自己的 `SUPERHEATED` 被丢了。

⇒ `raw_phase` 保留原值（可空）。「相态没认出来」从此是**可查的**，
而不是一个静默的数据丢失。

它**不在任何 CHECK 里** —— 它的存在意义就是能装下词表外的值。

## 单测为什么抓不到

`tests/conftest.py` 从 `SA_Base.metadata.create_all` 建内存 SQLite 表，
**不跑迁移**。所以 CHECK 写没写、对不对，4500+ 单测一律绿。
本迁移的正确性只能靠**在真库上跑**验证（CLAUDE.md 的纪律）。
"""
from __future__ import annotations

from alembic import op
from sqlalchemy import inspect

from app.models.project import Stream

revision = "p8_011"
down_revision = "p8_010"
branch_labels = None
depends_on = None

_TABLE = "streams"


def _enum_values() -> dict[str, tuple[str, ...]]:
    """从 ORM 枚举取取值集合 —— 迁移不许硬编码一份。

    硬编码会与 `app/models/enums.py` 形成**第二份定义**，那正是 bug-187~191
    这一族问题的根（同一概念两份定义，漂移只是时间问题）。
    """
    from app.models.enums import StreamDataMode, StreamPhase, StreamSourceType

    return {
        "phase": tuple(sorted(p.value for p in StreamPhase)),
        "data_mode": tuple(sorted(d.value for d in StreamDataMode)),
        "source_type": tuple(sorted(t.value for t in StreamSourceType)),
    }


def _in_list(values: tuple[str, ...]) -> str:
    return ",".join(f"'{v}'" for v in values)


def upgrade() -> None:
    vals = _enum_values()

    # 1) raw_phase 列（幂等）
    cols = {c["name"] for c in inspect(op.get_bind()).get_columns(_TABLE)}
    if "raw_phase" not in cols:
        op.add_column(
            _TABLE,
            op.Column("raw_phase", op.String(20), nullable=True),
        )
        op.create_comment(
            _TABLE,
            "raw_phase",
            "相态原始值（PRO/II 字母或原文）；词表外时保留原样，"
            "phase 置 NULL 等待人工补录。不设 CHECK —— 它的用途就是装下词表外的值。",
        )

    # 2) 三条 CHECK。PG 没有 `ADD CONSTRAINT IF NOT EXISTS`，先查 pg_constraint。
    for col, values in vals.items():
        cname = f"ck_streams_{col}"
        op.execute(f"""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint WHERE conname = '{cname}'
            ) THEN
                ALTER TABLE {_TABLE}
                    ADD CONSTRAINT {cname}
                    CHECK ({col} IS NULL OR {col} IN ({_in_list(values)}));
            END IF;
        END $$;
        """)


def downgrade() -> None:
    # ⚠️ `raw_phase` 用 IF EXISTS：删列在某些状态下不可逆，
    # 而无条件 drop 会在「列本来就不存在」的库上炸。
    op.drop_column(_TABLE, "raw_phase")
    for col in ("phase", "data_mode", "source_type"):
        op.execute(f"ALTER TABLE {_TABLE} DROP CONSTRAINT IF EXISTS ck_streams_{col};")


# 契约一致性断言：ORM 的 `__table_args__` 必须声明**同样的三条 CHECK**。
#
# `alembic check` 只在你连上的那个库上比对 ORM ↔ DB，跨库漂移不在它视野里；
# 而「迁移写了、ORM 没声明」这类不一致，单测更是永远绿（内存 SQLite 从
# metadata 建表，不跑迁移）。所以在 import 期就断言一次。
#
# 注意这里断言的是**约束名**，不是表达式文本 —— PG 会把 CHECK 表达式重新
# 打印成自己的形态（`('A'::character varying)::text`），文本比对必然误报
# （同 bug-147）。
_ORM_CONSTRAINT_NAMES = {
    c.name for c in Stream.__table__.constraints if c.name is not None
}
for _col in _enum_values():
    _name = f"ck_streams_{_col}"
    assert _name in _ORM_CONSTRAINT_NAMES, (
        f"迁移创建了 {_name}，但 ORM 的 Stream.__table_args__ 没声明它 —— "
        "alembic check 会报 add_constraint（ORM 要、DB 有）。"
    )
