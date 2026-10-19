"""`GET /api/v1/config/assets` 列表端点（2026-10-19，TODO-040）。

## 为什么之前没有

SPEC `工艺专用综合计算软件需求规格说明书 Web版 P2.md §3.1.2` 第一行就是
「配置资产通用：`GET /api/v1/config/assets?category=` 列出配置资产」，
但后端只实现了 `post` + 一串 `/{asset_id}/...` 动作。`git log -S` 确认
**从未实现过** —— 不是回归，是前端跑在了后端前面。

后果不是 404 本身，而是：页面此前 `useFetch` 打这个端点 ⇒ 生产必然 404
⇒ **404 会被监控记成故障**，而端点却是「照 SPEC 实现的」这个印象。
本轮先把前端改成显式传空数组止血（`routeWrappers.AssetListRoute`），
这里把端点补上闭环。

## 范围纪律

SPEC 只写了 `?category=` 一个查询参数 —— 所以**只实现 category 过滤**。
分页、排序、按 status 过滤都不做（没被要求就不发明，见 CLAUDE.md
「Simplicity First」）。要加先改 SPEC。
"""
from __future__ import annotations

from app.core.security import create_access_token
from app.models.enums import ConfigStatus

_ASSETS = [
    ("CATEGORY_3", "饱和液体密度表"),
    ("CATEGORY_3", "气化潜热表"),
    ("CATEGORY_5", "管道等级 ASME B31.3"),
    ("CATEGORY_6", "离心泵复用设备"),
]


async def _mk(client, token, category, name):
    r = await client.post(
        "/api/v1/config/assets",
        json={"category": category, "name": name},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 201, r.text
    return r.json()


class TestListAssets:
    async def test_list_all_without_category(self, client, sample_user_token):
        for c, n in _ASSETS:
            await _mk(client, sample_user_token, c, n)
        r = await client.get(
            "/api/v1/config/assets",
            headers={"Authorization": f"Bearer {sample_user_token}"},
        )
        assert r.status_code == 200, r.text
        names = {a["name"] for a in r.json()}
        assert {n for _, n in _ASSETS} <= names

    async def test_filter_by_category(self, client, sample_user_token):
        for c, n in _ASSETS:
            await _mk(client, sample_user_token, c, n)
        r = await client.get(
            "/api/v1/config/assets",
            params={"category": "CATEGORY_3"},
            headers={"Authorization": f"Bearer {sample_user_token}"},
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body, "过滤后应有结果"
        assert {a["category"] for a in body} == {"CATEGORY_3"}

    async def test_empty_db_returns_empty_list(self, client, sample_user_token):
        """前端 `filtered.length === 0` 走 Empty 分支；404 会让整页进错误态。"""
        r = await client.get(
            "/api/v1/config/assets",
            headers={"Authorization": f"Bearer {sample_user_token}"},
        )
        assert r.status_code == 200
        assert r.json() == []

    async def test_invalid_category_returns_400(self, client, sample_user_token):
        """⚠️ 未知过滤值必须 400 —— 静默返回全部等于过滤没生效且看不出来。"""
        for c, n in _ASSETS:
            await _mk(client, sample_user_token, c, n)
        r = await client.get(
            "/api/v1/config/assets",
            params={"category": "FORMULA"},
            headers={"Authorization": f"Bearer {sample_user_token}"},
        )
        assert r.status_code == 400
        assert r.json()["code"] == "CONFIG_ASSET_INVALID_CATEGORY"

    async def test_unauthorized_401(self, client):
        r = await client.get("/api/v1/config/assets")
        assert r.status_code in (401, 403)

    async def test_forbidden_role_403(self, client, sample_user_token):
        for c, n in _ASSETS:
            await _mk(client, sample_user_token, c, n)
        token = create_access_token(subject="test-viewer", role="VIEWER")
        r = await client.get(
            "/api/v1/config/assets",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 403


class TestResponseShape:
    async def test_shape_matches_contract(self, client, sample_user_token):
        """`status` 必须是 `ConfigStatus` 5 态（bug-188）—— 裸 str 会让
        客户端又去猜，而前端已经猜错过一次。"""
        await _mk(client, sample_user_token, "CATEGORY_3", "系数表 A")
        r = await client.get(
            "/api/v1/config/assets",
            headers={"Authorization": f"Bearer {sample_user_token}"},
        )
        allowed = {s.value for s in ConfigStatus}
        for a in r.json():
            assert set(a) >= {"asset_id", "category", "name", "status", "current_version"}
            assert a["status"] in allowed, f"{a['status']} 不在 ConfigStatus 里"
