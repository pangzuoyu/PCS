"""**404 文案逐字同形**（2026-11-23 · P10-I · T2 · TODO-187b）。

## 缺陷是什么

端点常见「**先取记录 ⇒ 再判授权**」的写法 ⇒ ⇒ 于是同一条请求有**两种 404**：

| 情况 | 端点自己抛的 | 守卫抛的 |
|---|---|---|
| 记录**不存在** | `"FiltrationResult not found"` | —— |
| 记录存在但**无权** | —— | `"Project not found: {project_id}"` |

⇒ ⇒ ⇒ **两种文案不同 ⇒ ⇒ 无权者能靠文案枚举出记录是否存在**（存在性泄露）。

## 修法（人裁 2026-11-23 · 选 A）

守卫加**两个可选参数** `not_found_code` / `not_found_message`
⇒ ⇒ 端点把**自己那条**文案传给守卫 ⇒ ⇒ 守卫照抄
⇒ ⇒ ⇒ **「不存在」与「无权」逐字同形** ⇒ ⇒ ⇒ 不可区分。

⚠️ **默认文案一个字都不能改**（`"Project not found: {project_id}"`）
⇒ ⇒ 124 处 project 级调用依赖它 ⇒ ⇒ ⇒ 有测试钉子。

## 本文件断什么

1. **约束 2 的钉子**：不传参数调用守卫 ⇒ ⇒ 仍是 `"Project not found: {project_id}"`
2. **守卫的形状**：`not_found_message` ⇒ ⇒ `HTTPException` 形状（code `HTTP_404`）；
   `not_found_code` ⇒ ⇒ `PcsError(code=…)` 形状 ⇒ ⇒ **code 与 message 一起对齐**
3. **AST 完整性守卫**：**每一个**「先抛自己的 404 再调守卫」的端点
   ⇒ ⇒ 都必须把**自己那条**文案传给守卫（逐字比对 AST）
   ⇒ ⇒ ⇒ 漏一处 / 抄错一个字 ⇒ ⇒ 这里红
4. **端到端**：几族代表性端点 ⇒ ⇒ 「不存在」与「无权」的 `(code, message)` **逐字相同**
"""
from __future__ import annotations

import ast
import uuid
from pathlib import Path

import pytest

from app.core.security import create_access_token

API_DIR = Path(__file__).resolve().parents[3] / "app" / "api" / "v1"

#: 守卫的两个入口
GUARD_NAMES = ("check_project_access_or_404", "check_record_access_or_404")


def _auth(subject: str, role: str = "DESIGNER", *, user_id: uuid.UUID | None = None):
    extra = {"user_id": str(user_id)} if user_id else None
    token = create_access_token(subject=subject, role=role, extra=extra)
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# ① 约束 2 的钉子：默认文案一个字都不能改
# ---------------------------------------------------------------------------


async def test_project_guard_default_message_is_unchanged(db_session):
    """⚠️ **守卫的默认文案不得因加可选参数而改变**（人裁约束 2）。

    ⇒ ⇒ 124 处 project 级调用依赖它 ⇒ ⇒ 这是**最大的回归风险点**
    ⇒ ⇒ ⇒ 用一条测试钉死。
    """
    from fastapi import HTTPException

    from app.api.v1._guard import check_project_access_or_404

    project_id = uuid.uuid4()
    with pytest.raises(HTTPException) as exc:
        await check_project_access_or_404(
            db_session, user_id=uuid.uuid4(), project_id=project_id,
        )
    assert exc.value.status_code == 404
    assert exc.value.detail == f"Project not found: {project_id}"


# ---------------------------------------------------------------------------
# ② 守卫的两种形状
# ---------------------------------------------------------------------------


async def test_guard_with_custom_message_keeps_the_http_exception_shape(db_session):
    """⚠️ **给了 `not_found_message`** ⇒ ⇒ 仍是 `HTTPException` 形状
    ⇒ ⇒ code 仍是 `HTTP_404`（与端点自己抛的一致）⇒ ⇒ 前端按 code 分流不变。"""
    from fastapi import HTTPException

    from app.api.v1._guard import check_project_access_or_404

    with pytest.raises(HTTPException) as exc:
        await check_project_access_or_404(
            db_session, user_id=uuid.uuid4(), project_id=uuid.uuid4(),
            not_found_message="FiltrationResult not found",
        )
    assert exc.value.status_code == 404
    assert exc.value.detail == "FiltrationResult not found"


async def test_guard_with_custom_code_raises_pcs_error(db_session):
    """⚠️ **给了 `not_found_code`** ⇒ ⇒ 抛 `PcsError`（**code 与 message 一起**）
    ⇒ ⇒ 否则 code 不同 ⇒ ⇒ 前端仍能分流 ⇒ ⇒ 存在性仍可枚举。"""
    from app.api.v1._guard import check_project_access_or_404
    from app.services.exceptions import PcsError

    with pytest.raises(PcsError) as exc:
        await check_project_access_or_404(
            db_session, user_id=uuid.uuid4(), project_id=uuid.uuid4(),
            not_found_code="SIM_STREAM_NOT_FOUND", not_found_message="Stream not found",
        )
    assert exc.value.status == 404
    assert exc.value.code == "SIM_STREAM_NOT_FOUND"
    assert "Stream not found" in exc.value.message


# ---------------------------------------------------------------------------
# ③ AST 完整性守卫：每一个端点都必须把**自己那条**文案传给守卫
# ---------------------------------------------------------------------------


def _own_not_found_node(fn: ast.FunctionDef) -> ast.Raise | None:
    """端点自己抛的那个 404（`Raise` 节点）—— 用来比**先后顺序**。"""
    for node in ast.walk(fn):
        if isinstance(node, ast.Raise) and isinstance(node.exc, ast.Call):
            name = getattr(node.exc.func, "id", None) or getattr(node.exc.func, "attr", None)
            if name in ("HTTPException", "PcsError", "CorePcsError"):
                kw = {k.arg: k.value for k in node.exc.keywords}
                status = kw.get("status") or kw.get("status_code")
                if status is not None and not (
                    isinstance(status, ast.Constant) and status.value == 404
                ):
                    continue
                if name == "HTTPException" and "detail" not in kw:
                    continue
                if name != "HTTPException" and "code" not in kw:
                    continue
                return node
    return None


def _own_not_found(fn: ast.FunctionDef) -> tuple[ast.expr | None, ast.expr | None]:
    """端点自己抛的 404 ⇒ ⇒ (code 表达式, message 表达式)。

    - `HTTPException(status_code=404, detail=<expr>)` ⇒ ⇒ (None, <expr>)
      ⇒ ⇒ code 隐含是 `HTTP_404`
    - `PcsError(<msg>, code=<code>, status=404)` ⇒ ⇒ (<code>, <msg>)
    - `CorePcsError(code=<code>, message=<msg>, status=404)` ⇒ ⇒ (<code>, <msg>)
    """
    for node in ast.walk(fn):
        if not isinstance(node, ast.Raise) or not isinstance(node.exc, ast.Call):
            continue
        func = node.exc.func
        name = getattr(func, "id", None) or getattr(func, "attr", None)
        if name not in ("HTTPException", "PcsError", "CorePcsError"):
            continue
        kw = {k.arg: k.value for k in node.exc.keywords}
        # 只认「明确 404」的
        status = kw.get("status") or kw.get("status_code")
        if status is not None:
            if not (isinstance(status, ast.Constant) and status.value == 404):
                continue
        if name == "HTTPException":
            detail = kw.get("detail")
            if detail is None:
                continue
            return None, detail
        message = kw.get("message")
        if message is None and node.exc.args:
            message = node.exc.args[0]
        code = kw.get("code")
        if code is None:
            continue
        return code, message
    return None, None


def _guard_call(fn: ast.FunctionDef) -> ast.Call | None:
    """端点里的守卫调用（取第一个）。"""
    for node in ast.walk(fn):
        if isinstance(node, ast.Call):
            name = getattr(node.func, "id", None) or getattr(node.func, "attr", None)
            if name in GUARD_NAMES:
                return node
    return None


def _has_vector(fn: ast.FunctionDef) -> bool:
    """这个端点**有没有枚举向量** ⇒ ⇒ 自己的 404 **必须**在守卫**之前**。

    ⇒ ⇒ 若守卫先跑 ⇒ ⇒ 无权者拿到的**永远是守卫那条** 404
    ⇒ ⇒ ⇒ 自己的那条（记录不存在）压根不可达 ⇒ ⇒ ⇒ **没有两种文案** ⇒ ⇒ 无需对齐。
    """
    own = _own_not_found_node(fn)
    call = _guard_call(fn)
    if own is None or call is None:
        return False
    return own.lineno < call.lineno


def _same_expr(a: ast.expr | None, b: ast.expr | None) -> bool:
    """两个表达式**逐字**相同（AST 结构一致 ⇒ ⇒ 字面量/f-string 的模板一致）。"""
    if a is None or b is None:
        return a is None and b is None
    return ast.dump(a) == ast.dump(b)


def _endpoints_with_two_404s() -> list[tuple[str, str, ast.expr | None, ast.expr | None, ast.Call]]:
    """扫全 api 层 ⇒ ⇒ 找出「自己抛 404 **且** 调守卫」的端点。"""
    found = []
    for path in sorted(API_DIR.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for fn in [n for n in ast.walk(tree) if isinstance(n, ast.AsyncFunctionDef)]:
            own_code, own_msg = _own_not_found(fn)
            if own_msg is None:
                continue
            call = _guard_call(fn)
            if call is None:
                continue
            if not _has_vector(fn):
                continue   # ⇒ ⇒ 守卫在前 ⇒ ⇒ 自己的 404 不可达 ⇒ ⇒ 无向量
            found.append((path.name, fn.name, own_code, own_msg, call))
    return found


ALIGNED = _endpoints_with_two_404s()


def test_the_ast_guard_actually_found_endpoints() -> None:
    """⚠️ **守卫本身要先有效** ⇒ ⇒ 扫不到端点 ⇒ ⇒ 下面的守卫是**假绿**。"""
    assert len(ALIGNED) >= 20, (
        f"只扫到 {len(ALIGNED)} 个「两种 404」的端点 ⇒ ⇒ 扫描规则坏了"
        " ⇒ ⇒ 下面的断言会**恒真**（假绿）"
    )


@pytest.mark.parametrize(
    "filename,endpoint,own_code,own_msg,call",
    ALIGNED,
    ids=[f"{f}::{e}" for f, e, _, _, _ in ALIGNED],
)
def test_every_guarded_endpoint_aligns_its_own_not_found(
    filename: str, endpoint: str,
    own_code: ast.expr | None, own_msg: ast.expr, call: ast.Call,
) -> None:
    """⚠️ **每一个**「自己抛 404 再调守卫」的端点
    ⇒ ⇒ 都必须把**自己那条**（code + message）传给守卫 ⇒ ⇒ **逐字**。

    ⇒ ⇒ 漏传 ⇒ ⇒ 两种文案不同 ⇒ ⇒ 存在性可枚举 ⇒ ⇒ 这里红。
    ⇒ ⇒ 抄错一个字 ⇒ ⇒ 这里红。
    """
    kw = {k.arg: k.value for k in call.keywords}
    assert "not_found_message" in kw, (
        f"{filename}::{endpoint} 自己抛了「不存在」的 404 ⇒ ⇒ 但守卫调用"
        "**没传** `not_found_message` ⇒ ⇒ 「无权」与「不存在」文案不同"
        " ⇒ ⇒ 存在性可枚举"
    )
    assert _same_expr(kw["not_found_message"], own_msg), (
        f"{filename}::{endpoint} 传给守卫的 `not_found_message` "
        "与它自己抛的那条**不一致** ⇒ ⇒ 两种情况仍可区分"
    )
    if own_code is not None:
        assert "not_found_code" in kw, (
            f"{filename}::{endpoint} 自己抛的是 `PcsError(code=…)` "
            "⇒ ⇒ 守卫也必须带 `not_found_code` ⇒ ⇒ 否则 code 不同 ⇒ ⇒ 仍可分流"
        )
        assert _same_expr(kw["not_found_code"], own_code), (
            f"{filename}::{endpoint} 传给守卫的 `not_found_code` "
            "与它自己抛的那条**不一致**"
        )
    else:
        assert "not_found_code" not in kw, (
            f"{filename}::{endpoint} 自己抛的是 `HTTPException`（code = HTTP_404）"
            " ⇒ ⇒ 守卫也必须是同一形状 ⇒ ⇒ 不该传 `not_found_code`"
        )


# ---------------------------------------------------------------------------
# ④ 端到端：「不存在」与「无权」的 (code, message) **逐字相同**
# ---------------------------------------------------------------------------


async def _mk_project(db_session, name: str):
    """造一个 Project 行（`grant_project` 需要它）。"""
    from app.models.project import Project

    proj = Project(
        project_no=f"R404-{uuid.uuid4().hex[:8]}",
        project_name=name, owner_company="X", location="X",
        project_type="CHEMICAL", design_phase="FEED", unit_system="SI",
        status="ACTIVE", workspace_id=uuid.uuid4(),
    )
    db_session.add(proj)
    await db_session.flush()
    return proj


async def _create_psychro(strict_client, project_id: uuid.UUID, creator: uuid.UUID) -> str:
    body = {
        "project_id": str(project_id),
        "workspace_id": str(uuid.uuid4()),
        "tag_number": "PSY-404-001",
        "standard_profile_code": "ASHRAE_FUND_2021",
        "calc_type": "HUMIDITY_RATIO",
        "sign_status": "DRAFT",
        "humidity_ratio_kg_kg": 0.00993,
        "dew_point_c": 13.87,
        "wet_bulb_c": 17.88,
        "enthalpy_kj_kg": 50.423,
        "specific_volume_m3_kg": 0.858,
        "input_json": {"t_c": 25.0, "rh": 0.5, "p_pa": 101325.0},
        "output_json": {"humidity_ratio_kg_kg": 0.00993},
    }
    r = await strict_client.post(
        "/api/v1/psychro/results", json=body,
        headers=_auth("creator-1", "DESIGNER", user_id=creator),
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def _create_filtration(strict_client, project_id: uuid.UUID, creator: uuid.UUID) -> str:
    body = {
        "project_id": str(project_id),
        "workspace_id": str(uuid.uuid4()),
        "tag_number": "FIL-404-001",
        "filter_type": "RUTH_CONST_PRESSURE",
        "media_type": "SAND",
        "area": 1.0,
        "cycle_time": 1.0,
        "pressure_drop": 1e5,
        "cake_resistance_alpha": 1e10,
        "specific_resistance_r0": 1e10,
    }
    r = await strict_client.post(
        "/api/v1/filtration/results", json=body,
        headers=_auth("creator-1", "DESIGNER", user_id=creator),
    )
    assert r.status_code == 201, r.text
    return r.json()["result_id"]


#: (族名, 造记录的协程)
E2E_FAMILIES = [
    ("psychro", _create_psychro),
    ("filtration", _create_filtration),
]


@pytest.mark.parametrize(
    "family,create", E2E_FAMILIES, ids=[f[0] for f in E2E_FAMILIES],
)
async def test_missing_and_unauthorized_are_byte_identical(
    strict_client, db_session, grant_project, family, create,
):
    """⚠️ **端到端**：同**一个**无权用户探两个 id
    ⇒ ⇒ **存在**（无权）· **不存在** ⇒ ⇒ 两种 404 的 `(code, message)` 必须**逐字相同**。

    ⇒ ⇒ 不同 ⇒ ⇒ 无权者能靠文案**枚举出记录是否存在**（存在性泄露）。
    ⇒ ⇒ ⚠️ 用 `strict_client`（默认 `client` 把守卫 mock 成永远 True ⇒ ⇒ 测不出来）。

    ⚠️⚠️ **URL 字面量必须写在本函数体里** —— 棘轮（`test_strict_client_ratchet.py`）
    只扫**测试函数体**里的 URL ⇒ ⇒ 写在模块级常量里 ⇒ ⇒ 棘轮**看不见**
    ⇒ ⇒ 台账（`AUDITED_PROJECT_SCOPED_ENDPOINTS`）里那两条会**假绿**。
    """
    creator = uuid.uuid4()
    outsider = uuid.uuid4()
    project = await _mk_project(db_session, f"404 同形 {family}")
    await grant_project(creator, project.project_id)

    record_id = await create(strict_client, project.project_id, creator)

    # ⚠️ 字面量在函数体内（见上面的说明）⇒ ⇒ 棘轮扫得到 ⇒ ⇒ 台账不假绿。
    urls = {
        "psychro": f"/api/v1/psychro/results/{record_id}",
        "filtration": f"/api/v1/filtration/results/{record_id}",
    }
    missing_urls = {
        "psychro": f"/api/v1/psychro/results/{uuid.uuid4()}",
        "filtration": f"/api/v1/filtration/results/{uuid.uuid4()}",
    }

    # ① 无权 + 记录**存在**
    r_forbidden = await strict_client.get(
        urls[family], headers=_auth("outsider-1", "DESIGNER", user_id=outsider),
    )
    # ② 无权 + 记录**不存在**
    r_missing = await strict_client.get(
        missing_urls[family],
        headers=_auth("outsider-1", "DESIGNER", user_id=outsider),
    )

    assert r_forbidden.status_code == 404, r_forbidden.text
    assert r_missing.status_code == 404, r_missing.text
    assert r_forbidden.json()["code"] == r_missing.json()["code"], (
        f"{family}: 两种情况的 **code** 不同 ⇒ ⇒ 前端按 code 分流 ⇒ ⇒ 仍可枚举"
        f" ⇒ ⇒ 无权={r_forbidden.json()} 不存在={r_missing.json()}"
    )
    assert r_forbidden.json()["message"] == r_missing.json()["message"], (
        f"{family}: 两种情况的 **message** 不同 ⇒ ⇒ 存在性可枚举"
        f" ⇒ ⇒ 无权={r_forbidden.json()} 不存在={r_missing.json()}"
    )
