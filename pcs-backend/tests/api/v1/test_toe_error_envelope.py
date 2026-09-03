"""services.PcsError 错误信封 API 测试（终审 F2 / V1.4 P2-OPEN-005）。

ToeConversionService 抛的是 app/services/exceptions.PcsError（与
app/core/errors.PcsError 是两个类）。修复前该类没有 exception handler，
端点里抛出会直接 500；修复后 install_exception_handlers 把它映射到与
core.PcsError 相同的 ErrorResponse 信封（code / message / detail / trace_id）。

断言（真实路由 GET /api/v1/config/toe-conversion，query 参数 fuel_type + year）：
- 非法 fuel_type → 422 code=TOE_INVALID_FUEL
- 合法 fuel_type 但系数表无该年数据（空表）→ 404 code=TOE_NOT_FOUND
"""

from __future__ import annotations


async def test_toe_invalid_fuel_returns_422_envelope(client):
    r = await client.get(
        "/api/v1/config/toe-conversion",
        params={"fuel_type": "BAD", "year": 2026},
    )
    assert r.status_code == 422
    body = r.json()
    assert body["code"] == "TOE_INVALID_FUEL"
    assert "BAD" in body["message"]
    assert "trace_id" in body


async def test_toe_not_found_returns_404_envelope(client):
    # client fixture 的 in-memory SQLite 中 pcs_toe_conversion_factors 为空表，
    # 合法 fuel_type 也会命中 TOE_NOT_FOUND（404）路径。
    r = await client.get(
        "/api/v1/config/toe-conversion",
        params={"fuel_type": "GAS", "year": 2026},
    )
    assert r.status_code == 404
    body = r.json()
    assert body["code"] == "TOE_NOT_FOUND"
    assert "GAS" in body["message"]
    assert "trace_id" in body
