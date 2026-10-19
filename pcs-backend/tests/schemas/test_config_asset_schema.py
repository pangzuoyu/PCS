"""AssetResponse.status 的词表（2026-10-19，bug-188）。

`AssetResponse.status` 此前是裸 `str`，**词表只写在 description 文字里**。
人类读到「DRAFT/PENDING/APPROVED/PUBLISHED/OBSOLETE」会说「哦，5 态」，
而客户端读到的只是 `"type": "string"` —— 机器读不到，于是**编了一个**
`IN_APPROVAL`（bug-187 的同一族，方向一致：词表没进契约 → 前端只能猜 →
猜错 → 生产显示「未知状态」/ 按钮永不启用）。

与 bug-187 的区别：那次连 description 都是错的；这次 description 写对了
但**没有机器可读**。两者后果一样 ⇒ 判别标准也一样：
**词表必须在类型里，不能只在散文里。**
"""
from __future__ import annotations

import uuid

import pytest
from pydantic import ValidationError

from app.models.enums import ConfigStatus
from app.schemas.config import AssetResponse

_BASE = {
    "asset_id": uuid.uuid4(),
    "category": "FORMULA",
    "name": "理想气体状态方程",
}


class TestAssetStatusVocabulary:
    def test_五态全接受(self):
        for s in ConfigStatus:
            assert AssetResponse(**_BASE, status=s.value).status == s

    @pytest.mark.parametrize("bad", ["IN_APPROVAL", "ACTIVE", "", "Published"])
    def test_非法值被拒(self, bad):
        # `IN_APPROVAL` 是前端凭空造的；`ACTIVE` 是 config_domain 里
        # 另 5 张子表的 default 值，不是 config_assets 的状态。
        with pytest.raises(ValidationError):
            AssetResponse(**_BASE, status=bad)

    def test_注解是枚举而非裸str(self):
        """裸 `str` ⇒ 词表从契约消失 ⇒ 前端只能猜。"""
        assert AssetResponse.model_fields["status"].annotation is ConfigStatus
