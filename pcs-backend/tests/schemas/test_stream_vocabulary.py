"""`Stream` 四个词表字段必须在契约里（2026-10-19，TODO-042 / bug-191）。

## 背景

`StreamResponse` 的 `phase` / `sign_status` / `data_mode` / `source_type`
四个字段此前都是**裸 `str`** —— 词表只写在 description 文字里。客户端读到的
是 `"type": "string"`，于是只能猜，而它确实猜错过（bug-187/188/190）。

## 为什么这四个特别危险

| 字段 | description 写的 | 实际 |
|---|---|---|
| `phase` | VAPOR/LIQUID/MIXED/SOLID | ✅ 对（但 SPEC P3 是 3 值，漏 SOLID） |
| `sign_status` | DRAFT/IN_APPROVAL/CHECKED/OBSOLETE | ❌ **只写了 4 个，实际 9 个** —— DB 的 PG enum `streamsignstatus` 有 9 值 |
| `data_mode` | CHEMICAL/PETROLEUM/SOLID | ✅ 对 |
| `source_type` | 5 个 | ❌ **实际 13 个**，漏掉全部 10 个 `*_CALCULATED` |

⇒ 「description 里的词表」既可能**写少**也可能**写错**，所以它不能当规格用。
本测试把四个词表钉进类型，并**与代码里的其他定义做一致性检查** ——
因为「同一概念两份定义」正是这一族 bug 的根。
"""
from __future__ import annotations

import uuid

import pytest
from typing import get_args

from pydantic import ValidationError

from app.models.enums import (
    StreamDataMode,
    StreamPhase,
    StreamSignStatus,
    StreamSourceType,
)
from app.schemas.stream import (
    StreamBase,
    StreamResponse,
    StreamStatePointBase,
)

_BASE = {
    "stream_name": "进料物流",
    "case_type": "NORMAL",
    "data_mode": "CHEMICAL",
}


#: StreamResponse 的契约必填字段（除词表四项外的那些）。
#: 少给就是 Pydantic 的「Field required」而不是我们想测的那个错。
_DEFAULTS = {
    "stream_id": uuid.uuid4(),
    "sign_status": "DRAFT",
    "record_hash": "deadbeef",
    "approval_depth": 2,
    "created_at": "2026-10-19 08:00:00",
    "source_type": "SIM_IMPORT",
}


def _resp(**over):
    return StreamResponse(**{**_BASE, **_DEFAULTS, **over})


class TestVocabularyIsTyped:
    """四个字段的注解必须是枚举，不能是裸 `str`。"""

    @pytest.mark.parametrize(
        "field,enum_",
        [
            # phase 声明为 `StreamPhase | None`（DB 允许空），
            # 所以断言的是「optional 后仍是那个枚举」而不是「就是那个枚举」——
            # 后者会因为 `Optional` 退化成对可空性的误报。
            ("phase", StreamPhase),
            ("data_mode", StreamDataMode),
            ("source_type", StreamSourceType),
        ],
    )
    def test_StreamBase的字段是枚举(self, field, enum_):
        ann = StreamBase.model_fields[field].annotation
        assert enum_ in get_args(ann) or ann is enum_, f"{field} 的注解不是 {enum_}"

    def test_sign_status是枚举(self):
        assert StreamResponse.model_fields["sign_status"].annotation is StreamSignStatus

    def test_状态点那一份也是枚举(self):
        # StreamStatePointBase 另有一套 phase / source_type —— 同样不能裸 str
        assert StreamStatePointBase.model_fields["phase"].annotation is StreamPhase
        assert StreamStatePointBase.model_fields["source_type"].annotation is StreamSourceType


class TestValuesAreAccepted:
    @pytest.mark.parametrize("p", list(StreamPhase))
    def test_四相态全接受(self, p):
        assert _resp(phase=p.value).phase == p

    @pytest.mark.parametrize("s", list(StreamSignStatus))
    def test_九态全接受(self, s):
        """⚠️ description 曾只写 4 态；DB 的 PG enum `streamsignstatus` 有 9 值。
        若照 description 收窄成 4 个，另外 5 个会被拒 —— 而它们是合法的。"""
        assert _resp(sign_status=s.value).sign_status is s

    @pytest.mark.parametrize("d", list(StreamDataMode))
    def test_三数据模式全接受(self, d):
        assert _resp(data_mode=d.value).data_mode == d

    @pytest.mark.parametrize("t", list(StreamSourceType))
    def test_十三来源类型全接受(self, t):
        assert _resp(source_type=t.value).source_type == t

    def test_phase可空(self):
        assert _resp(phase=None).phase is None


class TestOutOfVocabularyRejected:
    @pytest.mark.parametrize("bad", ["VAPOUR", "LIQUID ", "gas", "MIXED_PHASE"])
    def test_非法相态被拒(self, bad):
        """`_phase_norm` 对未知值 `return p` 原样放行 —— 收紧后拼写错误会 422，
        不再静默落库成一条谁也查不出来的孤儿物流。"""
        with pytest.raises(ValidationError):
            _resp(phase=bad)

    @pytest.mark.parametrize("bad", ["SIGNED", "checked", "OBSOLETE2"])
    def test_非法签署态被拒(self, bad):
        with pytest.raises(ValidationError):
            _resp(sign_status=bad)

    @pytest.mark.parametrize("bad", ["CHEM", "OIL", "GAS"])
    def test_非法数据模式被拒(self, bad):
        with pytest.raises(ValidationError):
            _resp(data_mode=bad)

    @pytest.mark.parametrize("bad", ["IMPORT", "flash", "CALCULATED"])
    def test_非法来源类型被拒(self, bad):
        with pytest.raises(ValidationError):
            _resp(source_type=bad)


class TestSingleSourceOfTruth:
    """同一概念**两份定义**是这一族 bug 的根，所以锁住它。"""

    def test_meta_service的StreamDataMode就是同一个枚举(self):
        from app.services.meta_service import StreamDataMode as FromMeta

        assert FromMeta is StreamDataMode, (
            "meta_service 里另有一份 StreamDataMode 定义 —— "
            "改一处不会带动另一处（bug-187/188/190 全是这个形态）"
        )

    def test_phase与conflict_resolver的校验集一致(self):
        from app.services.conflict_resolver import ConflictResolver

        assert set(ConflictResolver._VALID_PHASES) == {p.value for p in StreamPhase}

    def test_出口流用的source_type都在枚举里(self):
        """`outlet_stream.py` 产出的每个值都必须在枚举内。

        `DEVICE_CALCULATED` 曾因散落字面量被 Literal 遗漏过一次
        （A-03/C-05 LOW 修复）—— 这条测试就是为了让它不能再漏第二次。
        """
        import app.services.outlet_stream as os_mod

        missing = {v for v in os_mod._EQUIP_TYPE_MAP} - {t.value for t in StreamSourceType}
        assert not missing, f"出口流在用但枚举里没有: {sorted(missing)}"


class TestImportNormalizationAgreesWithVocabulary:
    """`_phase_norm` 归一出的每个值都必须在枚举里。

    ## 为什么必须一致

    2026-10-19 把 `StreamBase.phase` 从裸 `str` 收紧成 `StreamPhase` 枚举。
    而 `import_service._phase_norm` 的兜底是 `return p` —— **原样放行**：
    一个拼错的相态（`SUPERHEATED`）会被写进 DB，然后下一次 GET 的响应
    校验直接 500。写入现场与报错现场分离，这是最难查的一类。

    ⇒ 词表外的值走 `None`（与 MIXED 同一处理），不落库。
    代价：原始字母被丢弃，用户看不到「你的相态没认出来」。
    根治办法是加一列 `raw_phase`，登记在 TODOS.md（本轮不做）。
    """

    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("V", StreamPhase.VAPOR), ("vapor", StreamPhase.VAPOR),
            ("L", StreamPhase.LIQUID), (" liquid ", StreamPhase.LIQUID),
            ("S", StreamPhase.SOLID), ("solid", StreamPhase.SOLID),
            # MIXED → None：PRO/II parser 不抽组成，MIXED 会触发 SIM-V01 BLOCK
            ("M", None), ("MIXED", None),
            # 词表外 → None（此前是原样放行 ⇒ 会写进枚举列 ⇒ 响应 500）
            ("SUPERHEATED", None), ("VAPOUR", None), ("", None),
            (None, None),
        ],
    )
    def test_归一结果要么是枚举要么None(self, raw, expected):
        from app.services.import_service import _phase_norm

        got = _phase_norm(raw)
        assert got == (expected.value if expected else None), f"{raw!r} → {got!r}"
