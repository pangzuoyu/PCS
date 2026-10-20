"""`record_type` **只有一套词表** —— P9A-5 Task A（TODO-060）。

## 为什么单独一个文件

实测（2026-10-20）本仓有**五套** `record_type` 写法，其中两套上过**对外契约面**：

| 面 | 原用词表 |
|---|---|
| `/change-impact/{record_type}` · `/records/{module}` | `RECORD_TYPE_REGISTRY` 的键（21 个） |
| `/locks/{record_type}` · 6 个 PATCH 的 guard 入参 | **表名**（`cost_est_results`） |

⇒ 同一个 UI 要同时持两套标识。更糟的是两套**没有任何一方会报错**：

- `/locks` 收到表名**直接 200**（无校验）⇒ 锁写进 `lock:edit:cost_est_results:{id}`；
  前端若传类名则写进 `lock:edit:CostEstResult:{id}` ⇒ **两个命名空间互不可见
  ⇒ 两个人用不同拼写可以同时编辑同一条记录**，锁形同虚设。
- `has_conflict_detection("CostEstResult")` 返回 False（不在 `GUARDED_TABLES`）
  ⇒ Redis 降级时横幅会**错误地**追加「；本次编辑无冲突检测」，而该表其实**有**检测。

## 裁决：单一来源 = `RECORD_TYPE_REGISTRY` 的键

⚠️ **不是「类名」**：`RECORD_TYPE_REGISTRY` 的 21 个键里有 **5 个 ≠ 类名**
（`cv_result` / `restriction_result` / `flare_system_result` /
`cooling_tower_result` / `psychro_result`）⇒ 「类名」本身不是一套词表。
⚠️ 也不是「表名」：`__tablename__` → 注册表键的反查**对 21 个全部失败**
（表名是复数 `xxx_results`，注册表里是 `xxx_result` 单数）——
⇒ 「双向可换」（TODO-060 原话）**实测为假**，只有「键 → 表名」单向成立。
"""
from __future__ import annotations

import ast
import uuid
from pathlib import Path

import pytest
import pytest_asyncio
import redis.asyncio as aioredis

from app.services.calc_lineage import RECORD_TYPE_REGISTRY
from app.services.edit_guard import TABLE_CAPABILITIES, capability_of
from app.services.edit_lock import EditLockService, set_edit_lock

pytestmark = pytest.mark.asyncio

REDIS_URL = "redis://localhost:6379/9"

#: 6 张有编辑路径的表，其注册表键（= 契约面唯一词表）。
#:
#: ⚠️ **这 6 个键的风格不统一**（3 个 snake_case + 3 个 PascalCase）——
#: `RECORD_TYPE_REGISTRY` 的历史遗留（TODO-055 已登记）。归一的**目标**是
#: 「只有一套」，风格统一是**另一笔**（要动 `/change-impact` 与
#: `/records/{module}` 两个已发布契约 + 存量 DB 列）⇒ 本次不做。
EXPECTED_KEYS = {
    "cooling_tower_result",
    "FiltrationResult",
    "flare_system_result",
    "OpenChannelResult",
    "psychro_result",
    "CostEstResult",
}


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def lock_service():
    r = aioredis.Redis.from_url(REDIS_URL, socket_connect_timeout=1)
    try:
        await r.ping()
    except Exception:  # noqa: BLE001
        await r.aclose()
        pytest.skip("真 Redis 未运行（docker compose up redis）")
    await r.aclose()
    svc = EditLockService(REDIS_URL)
    set_edit_lock(svc)
    try:
        yield svc
    finally:
        set_edit_lock(None)
        await svc.aclose()


# ---------------------------------------------------------------------------
# 1. 能力表本身
# ---------------------------------------------------------------------------


async def test_capability_keys_are_registry_keys():
    """`TABLE_CAPABILITIES` 的键 = 注册表键（**不是**表名、**不是**类名）。"""
    assert set(TABLE_CAPABILITIES) == EXPECTED_KEYS
    for key in TABLE_CAPABILITIES:
        assert key in RECORD_TYPE_REGISTRY, f"{key} 不在注册表里 ⇒ 又一套词表"


async def test_no_key_equals_a_table_name():
    """⚠️ 防回归：**表名**（`xxx_results`）**不得**再当键出现。

    比 `endswith("_results")` 更严：直接查「有没有哪个键**恰好**是某个模型的
    `__tablename__`」⇒ 表名换个花样（单数、带前缀）也抓得到。
    """
    table_names = {m.__tablename__ for m in RECORD_TYPE_REGISTRY.values()}
    offenders = set(TABLE_CAPABILITIES) & table_names
    assert not offenders, f"表名又混进能力表了：{offenders}"


async def test_no_key_equals_a_class_name_it_should_not():
    """⚠️ 防回归：3 个键**看起来像**类名但**不是**（注册表的历史遗留）。

    这三条钉住「归一的基准是注册表键，不是类名」—— 若哪天有人把
    `cooling_tower_result` 悄悄改成 `CoolingTowerResult`，本例立刻红。
    """
    not_class_name = {"cooling_tower_result", "flare_system_result", "psychro_result"}
    assert not_class_name <= set(TABLE_CAPABILITIES)
    for key in not_class_name:
        assert key != RECORD_TYPE_REGISTRY[key].__name__, (
            f"{key} 现在等于类名了 ⇒ 归一的基准变了（键 vs 类名不再有区别）"
        )


async def test_capability_model_comes_from_the_registry_not_a_second_list():
    """`model` 必须**就是**注册表按键取出的那个类（不是第二份清单）。"""
    for key, cap in TABLE_CAPABILITIES.items():
        assert cap.model is RECORD_TYPE_REGISTRY[key], (
            f"{key} 的 model 与注册表不一致 ⇒ 同一概念两份清单（会漂移）"
        )


async def test_capability_of_rejects_a_table_name():
    """未登记的写法 ⇒ 抛错，**不得**静默放行。"""
    from app.services.edit_guard import UnregisteredTableError

    with pytest.raises(UnregisteredTableError):
        capability_of("cost_est_results")  # 表名，不是键


# ---------------------------------------------------------------------------
# 2. 契约面：`/locks` 收表名必须 404
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "operation", ["acquire", "renew", "release"], ids=["acquire", "renew", "release"]
)
async def test_locks_reject_a_table_name_record_type(
    client, sample_user_token, lock_service, operation
):
    """表名 ⇒ **404**。

    ⚠️ 旧行为是 **200**（锁真的写进了 Redis）—— 本例在改代码前**必须**红，
    否则这条守卫是假绿。
    """
    r = await client.post(
        f"/api/v1/locks/cost_est_results/{uuid.uuid4()}/{operation}",
        headers=_auth(sample_user_token),
    )
    assert r.status_code == 404, f"got {r.status_code}: {r.text}"


@pytest.mark.parametrize(
    "operation", ["acquire", "renew", "release"], ids=["acquire", "renew", "release"]
)
async def test_locks_accept_a_registry_key_record_type(
    client, sample_user_token, lock_service, operation
):
    """注册表键 ⇒ 正常受理，且响应原样回显该键。"""
    rid = str(uuid.uuid4())
    r = await client.post(
        f"/api/v1/locks/CostEstResult/{rid}/{operation}",
        headers=_auth(sample_user_token),
    )
    assert r.status_code in (200, 409), f"got {r.status_code}: {r.text}"
    assert r.json()["record_type"] == "CostEstResult"


async def test_locks_reject_a_garbage_record_type(client, sample_user_token):
    """未知写法 ⇒ 404（**不需要** Redis：校验发生在碰 Redis 之前）。"""
    r = await client.post(
        f"/api/v1/locks/total_garbage/{uuid.uuid4()}/acquire",
        headers=_auth(sample_user_token),
    )
    assert r.status_code == 404, f"got {r.status_code}: {r.text}"


async def test_degraded_message_does_not_falsely_say_no_conflict_detection(
    client, sample_user_token, monkeypatch
):
    """用**注册表键**时，降级横幅**不得**误加「；本次编辑无冲突检测」。

    ⚠️ 该表**有**冲突检测（`cost_est_results` 在 `GUARDED_TABLES` 里）。
    传类名/表名拼错 ⇒ `has_conflict_detection` 返回 False ⇒ 横幅会说错，
    让用户在**有保护**的情况下以为自己在无保护状态下编辑。
    """
    svc = EditLockService("redis://127.0.0.1:6399/0")  # 无人监听 ⇒ 降级
    set_edit_lock(svc)
    try:
        r = await client.post(
            f"/api/v1/locks/CostEstResult/{uuid.uuid4()}/acquire",
            headers=_auth(sample_user_token),
        )
        assert r.status_code == 200, f"got {r.status_code}: {r.text}"
        data = r.json()
        assert data["degraded"] is True
        assert "无冲突检测" not in data["message"], (
            f"该表**有**冲突检测，横幅却说无：{data['message']}"
        )
    finally:
        set_edit_lock(None)
        await svc.aclose()


# ---------------------------------------------------------------------------
# 3. 接线契约：6 个 PATCH 传的字面量必须都在能力表里
# ---------------------------------------------------------------------------


def _patch_call_site_literals() -> set[str]:
    """扫 `app/api/v1/*.py`，取出传给 `check_conflict` 的 `record_type=` 字面量。"""
    api_dir = Path(__file__).resolve().parents[3] / "app" / "api" / "v1"
    found: set[str] = set()
    for py in sorted(api_dir.glob("*.py")):
        tree = ast.parse(py.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            fname = getattr(node.func, "id", None) or getattr(node.func, "attr", None)
            if fname not in {"check_conflict", "record_edit_audit"}:
                continue
            for kw in node.keywords:
                if kw.arg == "record_type" and isinstance(kw.value, ast.Constant):
                    found.add(str(kw.value.value))
    return found


async def test_every_patch_call_site_passes_a_registered_key():
    """6 个 PATCH 端点传给 guard 的 `record_type` 必须是**已登记的键**。

    ⚠️ 这条是「防再分叉」的核心：新增编辑端点时若传了别的写法，
    契约测试立刻红，而不是等线上把锁写进错误的命名空间。
    """
    literals = _patch_call_site_literals()
    assert literals, "没扫到任何 check_conflict/record_edit_audit 调用点"
    unknown = literals - set(TABLE_CAPABILITIES)
    assert not unknown, (
        f"这些 record_type 没登记在能力表里：{unknown} —— "
        "要么登记，要么改回已登记的写法（TODO-060）"
    )


async def test_all_editable_tables_are_covered_by_a_patch_call_site():
    """能力表里的每张表**都要**有保存路径真的在用它（否则登记是空话）。"""
    literals = _patch_call_site_literals()
    orphan = set(TABLE_CAPABILITIES) - literals
    assert not orphan, f"能力表登记了但没有保存路径在用：{orphan}"
