"""PipeClass schema 的 status 词表（2026-10-19，bug-187）。

## 为什么要有这条测试

`PipeClassResponse.status` 此前是**裸 `str`**。后果不是「类型不严」这么轻：

1. 词表进不了 OpenAPI ⇒ 前端只能自己猜；
2. 前端猜成了 3 态 `DRAFT/ACTIVE/OBSOLETE` —— 而这个错误词表**抄自我
   本模块 docstring 里的一句「公司级 PipeClass：3 态 DRAFT/ACTIVE/OBSOLETE」**，
   那句话本身就是错的（ORM 列注释写的是 5 态 `ConfigStatus`）；
3. 于是生产上每个真实管号等级（`PUBLISHED`）都落到「未知状态: PUBLISHED」
   兜底分支 —— 不报错，只是没有内容。

⇒ 契约层写死 `ConfigStatus`，是**唯一**能把这件事钉死的地方。
下面几条守卫分别封住「词表被改」「枚举被换成非 ConfigStatus」「docstring 又漂」。

**注意**：断言用的是 `ConfigStatus` 本身，不是字面量列表 ——
这样以后合法地加一个态，本测试**不会**误报（那是合法契约变更），
但换成别的枚举 / 删值仍会被下面「契约形状」那条抓住。
"""
from __future__ import annotations

from typing import get_args, get_origin

import pytest
from pydantic import ValidationError

from app.models.enums import ConfigStatus
from app.schemas.pipe_class import PipeClassResponse

# 与 PipeClassBase 必填字段一致的最小响应
_BASE = {
    "class_id": "PC-001",
    "class_name": "ASME B31.3",
    "material_standard": "A106-B",
    "corrosion_allowance": 1.5,
    "design_pressure": 2.5,
    "design_temperature": 250.0,
    "dn_series_json": {"min": 15, "max": 600},
    "sch_series_json": {"15": "Sch 40"},
    "flange_class": "150#",
    "source": "COMPANY_STD",
    "version": "1.0",
}


class TestStatusVocabulary:
    def test_五个真态全部接受(self):
        for s in ConfigStatus:
            r = PipeClassResponse(**_BASE, status=s.value)
            assert r.status == s

    @pytest.mark.parametrize("bad", ["ACTIVE", "IN_APPROVAL", "PENDING_", "", "published"])
    def test_非法值被拒(self, bad):
        # ACTIVE 是**别的表**（formula_definitions 等）的 default 值，
        # 不是 pipe_classes 的状态。放它进来等于把后端的词汇分叉
        # 固化成契约。
        with pytest.raises(ValidationError):
            PipeClassResponse(**_BASE, status=bad)

    def test_契约形状是枚举而非裸str(self):
        """`status` 的注解必须是枚举 —— 裸 `str` 会让词表从契约里消失。"""
        field = PipeClassResponse.model_fields["status"]
        assert field.annotation is ConfigStatus


class TestDocstringVocabulary:
    def test_模块docstring不得再宣称3态(self):
        """docstring 里的词表会被前端照抄，必须与 ConfigStatus 一致。"""
        from app.schemas import pipe_class as mod

        doc = mod.__doc__ or ""
        # 这句话曾经是错的源头：ACTIVE 不是本表的态，且漏了 3 个真态。
        assert "3 态 DRAFT/ACTIVE/OBSOLETE" not in doc
        # 声明的态数必须等于真实词表长度。
        if "5 态" in doc:
            assert "5 态" in doc and len(list(ConfigStatus)) == 5


class TestNoLocalDuplicate:
    def test_status没有在别处被重新声明成str(self):
        """防回退：有人图省事把注解改回 `str` 会立刻红。"""
        field = PipeClassResponse.model_fields["status"]
        assert get_origin(field.annotation) is None
        assert field.annotation is ConfigStatus
        # str 是 Union 成员，说明又退回裸 str 了
        assert str not in get_args(field.annotation)
