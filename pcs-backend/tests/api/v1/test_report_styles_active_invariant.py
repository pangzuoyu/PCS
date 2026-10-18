"""「每个作用域至多一个 ACTIVE」必须由**数据库**保证（用户裁决 #23）。

## 为什么下沉到 DB

`create` / `revise` / `activate` 原先都是「先查当前 ACTIVE，再决定是否报错」。
那个 `select` **无锁** ⇒ 两个并发请求都查到「没有」⇒ 各自插入 ⇒
两个同作用域的 ACTIVE。而 `style_service` 的 docstring 声明它为**绝对**的不变量。

裁决：下沉为**部分唯一索引**（`uq_report_styles_one_active`，
`UNIQUE (report_type, project_id) NULLS NOT DISTINCT WHERE status='ACTIVE'`），
而不是在服务层加 `SELECT ... FOR UPDATE` —— 索引是永久防护，
且 `revise`/`activate` 两条路径一次覆盖。

## 本文件测的是「冲突以可读错误返回」，不是「数据库会拒绝」

数据库那一半只能在真库验（`postgresql_where` 与 `nulls_not_distinct`
都是 dialect 专属，SQLite 上被忽略）。真库证据在
`alembic/versions/p8_010_one_active_style.py`：

    第一条 ACTIVE (P8_010_A)    : INSERT 0 1
    第二条同作用域 ACTIVE       : ERROR: duplicate key value violates
                                  unique constraint "uq_report_styles_one_active"
    换个 report_type           : INSERT 0 1
    同 report_type 非 ACTIVE    : INSERT 0 1     ← 部分谓词生效

这一半要防的是**新引入的 500**：索引生效后，并发失败的那一路拿到的
不再是「查得到 → 报 StyleConflict」，而是 `IntegrityError`。若不转成
可读的业务错误，用户看到的就是 500 而不是「该作用域已有 ACTIVE 样式」。
"""
from __future__ import annotations

import pytest

from app.models.report import ReportStyleRow

pytestmark = pytest.mark.asyncio


def test_the_partial_unique_index_is_declared_with_the_right_shape():
    """索引本身：唯一 + 部分谓词 + NULLS NOT DISTINCT。

    少任何一样都会让不变量失效：
      - 去掉部分谓词 ⇒ 历史 SUPERSEDED 行之间也会互斥（版本号不同才对）
      - 去掉 NULLS NOT DISTINCT ⇒ 公司级（`project_id IS NULL`）形同虚设
      - 去掉唯一 ⇒ 那就不是约束了
    """
    idx = next(i for i in ReportStyleRow.__table__.indexes
               if i.name == "uq_report_styles_one_active")
    assert idx.unique is True, "索引不唯一 —— 那它不构成任何约束"
    assert [c.name for c in idx.columns] == ["report_type", "project_id"], \
        f"列变了：{[c.name for c in idx.columns]}"


def test_the_index_predicate_is_status_equals_active():
    """部分谓词必须是 `status = 'ACTIVE'` —— 不能是别的。

    谓词写错的后果**不是报错**，而是历史版本之间互相排斥：
    `revise` 会把旧的转 SUPERSEDED，而同一作用域可以有很多个
    SUPERSEDED 版本（正是它们让「回滚到上周那一版」成为可能）。
    """
    import pathlib

    from app.models import report as report_model

    src = pathlib.Path(report_model.__file__).read_text(encoding="utf-8")
    idx_src = src[src.index('"uq_report_styles_one_active"'):]
    idx_src = idx_src[:idx_src.index("),\n    )")]
    assert "status = 'ACTIVE'" in idx_src, (
        f"部分谓词不是 status='ACTIVE'：{idx_src}")
    assert "nulls_not_distinct" in idx_src.lower(), (
        "部分唯一索引漏了 NULLS NOT DISTINCT —— 公司级样式 "
        "（project_id IS NULL）在 PG 上会完全绕开它")


@pytest.mark.asyncio
async def test_a_race_is_stopped_by_the_index_not_by_the_check(client, monkeypatch):
    """竞态下第二次写入必须**失败**，而不是并存两条 ACTIVE。

    ## 怎么造出竞态

    把服务层的「先查当前 ACTIVE」打桩成永远返回空 —— 那正是两个并发请求
    都完成 check、还没提交 insert 时的状态。此时只剩数据库能拦住。

    ## 为什么用**项目级**作用域

    单测库是 SQLite，`NULLS NOT DISTINCT` 在 SQLite 上没有对应语法 ——
    公司级（`project_id IS NULL`）的唯一性在单测库里**不生效**。
    项目级（具体 project_id）两者一致，可以用它验「索引确实拦住了」。
    公司级那一半在真库验过（见本文件 docstring 的实测记录）。

    ⚠️ 注意别和 `test_report_styles_write.py::test_second_active_style_in_same_scope_is_409`
    混淆：那条走公司级且**不**打桩，命中的是**服务层**的检查，
    与索引无关 —— 所以它在 SQLite 上也成立。
    """
    import uuid as _uuid

    from app.core.security import create_access_token
    from app.services.report.style_service import StyleService

    async def _none(self, *a, **k):
        return None

    monkeypatch.setattr(StyleService, "_current", _none)

    headers = {"Authorization": f"Bearer {create_access_token(subject='u', role='SYSTEM_ADMIN')}"}
    payload = {"report_type": "RACE_A", "project_id": str(_uuid.uuid4()), "style": {}}

    first = await client.post("/api/v1/report/styles", headers=headers, json=payload)
    assert first.status_code == 201, first.text

    # 服务层查不到（竞态）⇒ 只剩数据库唯一索引能拦
    second = await client.post("/api/v1/report/styles", headers=headers, json=payload)
    assert second.status_code == 409, (
        f"实得 {second.status_code} —— 竞态下第二条 ACTIVE 居然建成了，"
        f"说明「每个作用域至多一个 ACTIVE」只由应用层的无锁查询保证。"
        f"响应：{second.text}")


@pytest.mark.asyncio
async def test_the_index_violation_reaches_the_client_as_409_not_500(db):
    """索引拦下的冲突必须被 `_style_call` 翻成 409，而不是穿透成 500。

    500 会被前端当成「系统坏了」，用户反复重试 —— 而重试只会再撞一次。
    """
    from sqlalchemy.exc import IntegrityError

    from app.api.v1.report import _style_call
    from app.services.exceptions import PcsError

    async def boom():
        raise IntegrityError("INSERT", {}, Exception("uq_report_styles_one_active"))

    # ⚠️ 2026-10-18 起契约是 PcsError（评审 #17：信封统一、code 语义化），
    # 不再是 HTTPException —— 全局 handler 会把它翻成同样的
    # {code, message} 信封，code 从 HTTP_409 变成 REPORT_STYLE_CONFLICT。
    with pytest.raises(PcsError) as ei:
        await _style_call(boom)

    assert ei.value.status == 409, f"实得 {ei.value.status}"
    assert ei.value.code == "REPORT_STYLE_CONFLICT"
    assert "ACTIVE" in str(ei.value)
    assert "修订" in str(ei.value), \
        "409 的文案要告诉用户下一步做什么（改用修订），而不是只说冲突"


@pytest.mark.asyncio
async def test_other_integrity_errors_are_not_swallowed_into_409(db):
    """**只**认那一条约束名。

    把所有 IntegrityError 都吞成 409 会掩盖真实故障：比如 content_hash
    冲突、字段超长，都会变成一句「该作用域已有 ACTIVE 样式」——
    而真实原因在那条消息里一个字都看不到。
    """
    from sqlalchemy.exc import IntegrityError

    from app.api.v1.report import _style_call

    async def boom():
        raise IntegrityError("INSERT", {}, Exception("uq_report_files_content_hash"))

    with pytest.raises(IntegrityError):
        await _style_call(boom)
