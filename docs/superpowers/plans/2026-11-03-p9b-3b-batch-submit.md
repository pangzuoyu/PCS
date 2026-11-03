# P9B-3b 批量「提交校对」实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 给 SIM 物流列表页加「多选 + 一键批量提交校对」，后端新增 `POST /api/v1/streams/batch-submit`（**207 Multi-Status**），一次请求 N 条 ⇒ 部分失败不回滚其它条、幂等去重、批次可预演（`dry_run`）、批次可审计。

**Architecture:** 后端新增一个**独立 service**（`app/services/stream_batch_service.py`）逐条复用既有单条语义（`StreamService.transition` ⇒ 行锁 + 角色校验 + 单条审计），端点层只做「上限校验 + 调 service + 写 1 条批次审计」。前端在既有 `StreamListPage` 上加 antd `rowSelection` + 工具栏按钮 + 一个结果弹窗（成功 N / 失败 M + 每条失败原因）。

**Tech Stack:** FastAPI · SQLAlchemy 2.x async · Pydantic v2 · pytest（asyncio_mode=auto）· React 19 · TypeScript · antd 5 · vitest · MSW · axios

**Spec:** `docs/PCS-PLAN-P9B-3-系统参数与SIM物流前端.md` §「P9B-3b 移交（批量「提交校对」—— 本批**不做**）」（委员会 2026-11-02 裁决 5 的 D1~D6）+ `docs/PCS-UI-SPEC.md` §7.7.1（V2.9）

---

## Global Constraints

- **端点路径 = `POST /api/v1/streams/batch-submit`**（用户 2026-11-03 裁决）——
  路径**两段**（`streams/batch-submit`），与三段的 `POST /streams/{stream_id}/submit`
  **不可能抢路由**；全仓 `grep '"/streams'` 只有 `app/api/v1/streams.py` 一个
  router，且它**没有** `POST /streams/{stream_id}`（两段）⇒ 本端点是两段路径里
  唯一的 POST ⇒ 零碰撞。
- **响应 = 207 Multi-Status**，body：
  `{batch_id, total, succeeded: [{status, stream_id, from_status, to_status, note?}], failed: [{status, stream_id, reason, detail?}], dry_run}`。
  ⚠️ 每条带**判别字段 `status`**（`"succeeded"` / `"failed"`）⇒ 调用方与前端
  都靠它分流（**不用** isinstance —— JSON 序列化后 isinstance 的信息会丢）。
  ⚠️ **207 是 2xx** ⇒ axios **不抛异常** ⇒ 前端**必须自己看 `failed` 数组**。
- **D1 后端端点**（不是前端循环）· **D2 部分成功**（一条失败不回滚其它条）·
  **D3 审计 N+1**（每条**真正转移**的物流 1 条 `RECORD_TRANSITION` + 批次 1 条
  新动作 `STREAM_BATCH_SUBMITTED`）· **D4 上限取 `system_settings` 的
  `stream.batch_submit_limit`**（默认 100）· **D5 幂等**（批次内按 `stream_id`
  去重；**已 `IN_APPROVAL`** 记成功且 `note="already_in_approval"`）·
  **D6 `dry_run=true`** ⇒ 不改状态、**不写任何审计**（含批次那条），只返回校验结果。
- ⚠️ **D4 的上限 100 条有**两个**理由，不止性能**（委员会 2026-11-03 · D3 约束 3）：
  ① **性能** —— 100 条 × 每条几次查询，PG 在 1s 内完成；
  ② **安全** —— 本端点**没有项目守卫**（与既有单条端点同口径，见 T6 的 TODO-118）
  ⇒ 上限把**单次越权的规模**限制在 100 条（100 条 vs 10000 条，攻击者的单次
  收益有界）。
  ⚠️ 这**不是**「修复越权」—— 修复越权是 TODO-118 的事；上限只是**降低单次规模**。
- ⚠️ **本端点没有项目守卫**（委员会 2026-11-03 · D3 裁决 C）：与既有单条端点
  `POST /streams/{id}/submit` **同口径**（都只做角色校验，不校验物流所属项目）
  ⇒ 这是**已知缺陷的延续**，不是设计意图；真修要**六个写端点 + 读面 + 批次一起修**
  （独立批次，登记为 TODO-118）。
  ⚠️ 但批次**降低了攻击成本**（从「100 次请求」降到「1 次请求」）⇒ 这一点必须写进
  债项，也因此**审计完整性是硬要求**（见 D3 约束 2 的批次审计字段）。
- **状态名一律 `IN_APPROVAL`**（9 态字面对齐记录侧）⇒ 幂等判定、错误码文案、
  前端徽章全部按它写（**不是** `PENDING`）。
- **组成门禁沿用既有错误码 `SIM_STREAM_COMPOSITION_OUT_OF_RANGE`**（T3 已提供，
  **不新造**）⇒ 口径 `|合计 − 1| ≤ 0.005`；`composition_json = null` ⇒ 跳过；
  `{}` ⇒ **拒绝**（未填写）。
- **单条端点语义**不许被本批改掉：`POST /streams/{id}/submit` 第二次提交仍是
  **422 `SIM_STREAM_INVALID_TRANSITION`**（幂等是**批次**的语义）。
- **逐条 commit**（不是整批一个事务）——`StreamService.transition` 失败时
  `await db.rollback()` **回滚的是当前事务** ⇒ 整批共用一个事务时「一条失败 ⇒
  前面成功的全被回滚」（与 D2 相反）⇒ 每条自成事务。
- **ACL 与单条端点同口径**：`DESIGNER` / `PROCESS_CONTROLLOR` / `SYSTEM_ADMIN`
  ⇒ 端点层 `require_roles` 整批 403；逐条的角色校验由状态机
  `TRANSITION_ROLES[SUBMIT_FOR_CHECK]` 负责。
- **契约字段一律具名 schema** ⇒ `check_openapi_payload_coverage.py` 的裸载荷数
  **只能持平或往下**（当前基线 **71**）。
- **前端类型契约派生**（`components['schemas'][...]`），不手写 union。
- **全仓只有一个 `PcsError`**（`app/core/errors.py`；`app/services/exceptions.py`
  里的是别名）⇒ 新代码从 `app.core.errors` import。
- **口令不上命令行**（会被权限分类器拦 + 进 shell 历史）⇒ 涉及 DB 的验证一律
  进程内派生 URL。
- **提交**：conventional commits，**不带 attribution 行**（用户全局规则优先）。

## Review Focus

以下五类输入/情形，**规格没写但一定会遇到** ⇒ 每条都要有一个测试把它钉住
（测试放在拥有该代码的任务里）：

1. **批次里同一个 `stream_id` 出现两次** ⇒ 只能处理一次（响应里只出现一条），
   且 `total` 是**去重后**的条数（不是请求条数）。
2. **批次里一条已 `IN_APPROVAL`** ⇒ 记**成功**（`note="already_in_approval"`），
   **不重复写 `RECORD_TRANSITION`** ⇒ 审计条数是「真正转移数 + 1」，不是「请求数 + 1」。
3. **`dry_run=true`** ⇒ 状态**一字未改**、**审计表零新增**（连批次那条也没有），
   但**仍然返回**每条的预判结果（成功/失败分开列）。
4. **同一批里既有成功又有失败** ⇒ 返回 **207** 且两张清单各自完整；**成功的那些
   不被回滚**（状态真的变成 `IN_APPROVAL`）⇒ 这是 D2 的全部意义。
5. **并发提交同一条 stream** ⇒ 行锁必须真的生效：单条端点「一胜一拒」
   （一�� 200、一条 422 `SIM_STREAM_INVALID_TRANSITION`）；批量端点因 D5 幂等
   表现为「两条都 207，但**只有一条**真正转移」（审计条数 == 1）⇒
   **必须**有方言级 SQL 断言 + 接线断言 + PG 车道真并发。

---

## Scope 说明（本批**包含一处对既有代码的修改**）

`StreamService.transition`（`app/services/stream_service.py:435`）里内联的
「加锁读一条物流」语句，会被替换为调用新的共享 helper
`select_stream_for_update()`（**一行替换**：`await db.execute(...)` →
`await select_stream_for_update(db, stream_id)`）。

**为什么这不算 scope creep**：
- 不是「顺手改」，是**本批的核心决策**（委员会 2026-11-03 · D4 裁决 A）——
  不抽就没有「单条路径与批次路径共用同一个**被断言**的加锁入口」；
- 改动是**一行替换**，**行为必须完全不变**；
- ⚠️ **C-1 的原始测试必须仍然通过，且那个测试文件一行都不许改**
  （`tests/services/test_stream_transition.py:243`
  `test_locked_read_is_not_shadowed_by_stale_identity_map` ⇒ 那是 C-1 的兜底）。

**为什么不放到独立批次**：独立批次会让批次 service 先写一份拷贝、下一批再抽
⇒ **中间一段时间存在两份拷贝**，而这段窗口正是**最可能引入回归**的时候
（批次刚写完、没人记得 C-1 的细节）。

⚠️ **D4 的真正问题不是「两份拷贝」，是「C-1 的修复没有断言钉住」** ——
只抽 helper 不加断言 = 抽出来只是让「删除」更难发生（两处可删 → 一处可删），
但删了那处测试仍然绿（SQLite 把 `FOR UPDATE` 编译掉，抓不住）⇒
**必须同时加两条断言**（见 T4：方言级 SQL + `populate_existing` 执行选项）。

---

## 文件结构

**后端（新增）**

```
pcs-backend/app/schemas/stream_batch.py              # T2：请求/响应契约（具名 schema）
pcs-backend/app/services/stream_batch_service.py     # T2：批次语义（D1~D6）
pcs-backend/app/api/v1/stream_batch.py                # T3：POST /streams/batch-submit（207）
pcs-backend/tests/services/test_stream_batch_service.py    # T2：service 级边界用例
pcs-backend/tests/api/v1/test_stream_batch_submit.py       # T3：HTTP 级（207 / ACL / 上限 / 审计）
pcs-backend/tests/api/v1/test_stream_batch_concurrency_pg.py  # T4：PG 车道真并发
```

**后端（修改）**

```
pcs-backend/app/services/stream_service.py            # T1：抽出 composition_mole_fraction_total
pcs-backend/app/api/v1/streams.py                    # T1：改用共享口径（行为不变）
pcs-backend/app/services/system_setting_service.py   # T1：get_setting_value
pcs-backend/app/models/enums.py                      # T1：AuditAction.STREAM_BATCH_SUBMITTED
pcs-backend/app/api/v1/__init__.py                   # T3：挂 stream_batch router
pcs-backend/docs/openapi.json                        # T3：契约重滚（生成物）
```

**前端（修改）**

```
pcs-frontend/src/api/stream.ts                       # T5：batchSubmitForReview + 契约派生类型
pcs-frontend/src/pages/sim/StreamListPage.tsx        # T5：rowSelection + 工具栏按钮 + 结果弹窗
pcs-frontend/src/mocks/handlers.ts                   # T5：dev mock 的批量端点
pcs-frontend/src/types/api.d.ts                     # T3/T5：契约重滚（生成物，勿手改）
pcs-frontend/tests/pages/sim/StreamListPage.test.tsx # T5：更新旧断言 + 新增 8 例
pcs-frontend/e2e/stream_batch_submit.spec.ts   # T5b：Playwright e2e（勾选 ⇒ 报文）
```

**文档**

```
docs/PCS-UI-SPEC.md        # T6：§7.7.1「批量提交校对」⏳ → ✅ + §12.4 加 V2.10 修订行
TODOS.md                   # T6：登记本批留下的债项
```

---

## Task 1: T1 · 批次的地基（四项可复用能力）

**Files:**
- Modify: `pcs-backend/app/services/stream_service.py`（新增模块级函数 `composition_mole_fraction_total`）
- Modify: `pcs-backend/app/api/v1/streams.py:531-546`（删掉本地 `_composition_mole_fraction_total`，改用 service 的）
- Modify: `pcs-backend/app/services/system_setting_service.py`（新增 `get_setting_value`）
- Modify: `pcs-backend/app/models/enums.py`（`AuditAction` 加 `STREAM_BATCH_SUBMITTED`）
- Test: `pcs-backend/tests/services/test_stream_batch_service.py`（本任务只放这三条能力的小测试）

**Interfaces:**
- Consumes: 无（基座）
- Produces:
  - `app.services.stream_service.composition_mole_fraction_total(stream: Stream) -> float | None`
    —— `None` = 无组成（`composition_json is None`）；否则返回各组分之和（`{}` ⇒ `0.0`）。
  - `app.services.system_setting_service.get_setting_value(db: AsyncSession, key: str, *, default: Any = None) -> Any`
    —— 键不存在 ⇒ 返回 `default`。
  - `app.models.enums.AuditAction.STREAM_BATCH_SUBMITTED`（值 `"STREAM_BATCH_SUBMITTED"`）。
  - `app.services.stream_service.build_stream_for_update_stmt(stream_id: uuid.UUID) -> Select`
    —— **只构造**「加锁读一条物流」的 SELECT（**不执行**）⇒ 方言级断言与
    `populate_existing` 断言都钉它。
  - `app.services.stream_service.select_stream_for_update(db: AsyncSession, stream_id: uuid.UUID) -> Stream | None`
    —— 执行上面那条语句并返回**锁定后**的行；**不存在返回 `None`**（由调用方
    抛 `SIM_STREAM_NOT_FOUND` ⇒ 单条端点的错误文案一字不变）。

- [ ] **Step 1: 写失败测试**

创建 `pcs-backend/tests/services/test_stream_batch_service.py`：

```python
"""批次「提交校对」的地基能力（P9B-3b · T1）。

本文件先只放三件**可复用**的小能力（后续 T2 的批次 service 全部依赖它们）：

1. `composition_mole_fraction_total` —— 组成合计口径（**单一来源**）；
2. `get_setting_value` —— 读系统参数（批次上限从这儿取）；
3. `AuditAction.STREAM_BATCH_SUBMITTED` —— 批次审计动作。

⚠️ 为什么组成口径要抽到 service：批次端点与单条端点**必须同一口径** ⇒
口径写在 router 里时，service 层只能反向 import 路由模块（分层倒挂）⇒ 抽。
"""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import AuditAction, StreamSignStatus
from app.models.project import Stream
from app.services.stream_service import composition_mole_fraction_total
from app.services.system_setting_service import get_setting_value

pytestmark = pytest.mark.asyncio


def _stream(**kw) -> Stream:
    """构造一个**不落库**的 Stream（只测组成口径，不碰 DB）。"""
    return Stream(
        stream_id=uuid.uuid4(),
        project_id=uuid.uuid4(),
        workspace_id=uuid.uuid4(),
        stream_name="S-1",
        sign_status="DRAFT",
        **kw,
    )


async def test_composition_total_none_means_no_composition():
    """`composition_json = None` ⇒ **跳过**（纯物质，无组成）。"""
    assert composition_mole_fraction_total(_stream(composition_json=None)) is None


async def test_composition_total_empty_object_is_zero():
    """`composition_json = {}` ⇒ 合计 0.0（⇒ 落在范围外 ⇒ **拒绝**，与「未填写」同义）。"""
    assert composition_mole_fraction_total(_stream(composition_json={})) == 0.0


async def test_composition_total_sums_fractions():
    """有内容 ⇒ 合计 = 各组分之和（值域 0~1 的小数，**不是**百分数）。"""
    total = composition_mole_fraction_total(
        _stream(composition_json={"7732-18-5": 0.6, "7440-23-5": 0.387})
    )
    assert total == pytest.approx(0.987)


async def test_get_setting_value_returns_stored_value(db_session: AsyncSession):
    """键存在 ⇒ 返回它的值。"""
    from app.services.system_setting_service import seed_defaults

    await seed_defaults(db_session)
    await db_session.commit()

    assert await get_setting_value(db_session, "stream.batch_submit_limit", default=7) == 100


async def test_get_setting_value_falls_back_to_default(db_session: AsyncSession):
    """键**不存在** ⇒ 返回 `default`（不抛异常 ⇒ 上限读不到时批次仍能跑）。"""
    assert await get_setting_value(db_session, "no.such.key", default=42) == 42


async def test_batch_audit_action_exists():
    """批次审计动作必须**存在**于枚举里（否则写审计时退化成裸字符串 ⇒ 审计页筛不出来）。"""
    assert AuditAction.STREAM_BATCH_SUBMITTED.value == "STREAM_BATCH_SUBMITTED"
```

- [ ] **Step 2: 跑测试，确认失败**

```bash
cd pcs-backend && uv run pytest tests/services/test_stream_batch_service.py -q
```

Expected: FAIL —— `ImportError: cannot import name 'composition_mole_fraction_total'`（三个能力都还不存在）

- [ ] **Step 3: 实现（三处最小改动）**

① `pcs-backend/app/services/stream_service.py` —— 在模块级（`_ROLE_ALIAS` 附近）加：

```python
def composition_mole_fraction_total(stream: Stream) -> float | None:
    """物流的组成摩尔分率合计；**无组成**（`composition_json is None`）返回 None。

    ⚠️ `composition_json` 是 `{CAS 号: 摩尔分率}` 字典，值域 **0~1 的小数**
    （**不是**百分数）—— 实测真库的组成合计恒为 `1.0000`。
    ⇒ 判定用 `|合计 − 1| ≤ 0.005`（≡ SPEC §7.7.2 的「100±0.5%」）。

    ⚠️ **唯一口径来源**（P9B-3b · T1）：单条端点与批量端点**必须同一口径**
    ⇒ 口径住在 service 层，不住在 router 里（router 里的版本 service 反向 import
    路由模块 = 分层倒挂）。
    """
    composition = stream.composition_json
    if composition is None:
        return None
    return sum(float(v) for v in composition.values())
```

② `pcs-backend/app/api/v1/streams.py` —— 删掉本地的 `_composition_mole_fraction_total`
（第 531~546 行那整个函数），并在 import 区加：

```python
from app.services.stream_service import (
    composition_mole_fraction_total,
    # ... 其余既有 import 保持不动
)
```

把 `submit_stream` 里的调用改成：

```python
            total = composition_mole_fraction_total(stream)
```

⚠️ **函数体其余部分一字不动**（docstring 里的口径说明保留在 service 侧）。

③ `pcs-backend/app/services/system_setting_service.py` —— 追加：

```python
async def get_setting_value(
    db: AsyncSession, key: str, *, default: Any = None
) -> Any:
    """读一个系统参数的值；**键不存在** ⇒ 返回 `default`。

    ⚠️ 只读**值列**（不加载整行）⇒ 不会把实体塞进 session 的 identity map。
    ⚠️ 值是 JSONB ⇒ 可能是任意 JSON（数字 / 布尔 / 对象）⇒ 调用方负责收窄。
    """
    value = (
        await db.execute(
            select(SystemSetting.setting_value_json).where(
                SystemSetting.setting_key == key
            )
        )
    ).scalar_one_or_none()
    return default if value is None else value
```

④ `pcs-backend/app/models/enums.py` —— 在 **`AuditAction` 类体内**（该类起于
第 317 行，`ConfigTransition` 起于第 481 行 ⇒ 别插进后者）**`SYSTEM_SETTINGS_UPDATED`
（第 431 行）之后**加：

```python
    # === 物流批量提交校对（P9B-3b · D3）===
    # 批次级汇总动作：每条**真正转移**的物流另有一条 RECORD_TRANSITION
    # （由状态机写）⇒ 本动作只记「这一批做了什么」。
    STREAM_BATCH_SUBMITTED = "STREAM_BATCH_SUBMITTED"
```

⚠️ **插错类也会「值相等就通过」**（bug-156：`ConfigTransition` 里插过一批
`REPORT_*`，断言值相同就放行了 ⇒ 值相同不代表类相同）⇒ T1 的那条测试断言的是
`AuditAction.STREAM_BATCH_SUBMITTED.value` ⇒ **必须确认它在 `AuditAction` 里**
（`AuditAction` 与 `ConfigTransition` 的成员名不重叠 ⇒ 名字写错会直接 ImportError）✓

⑤ **`app/services/stream_service.py`** —— 抽出**唯一**的加锁读入口
（委员会 2026-11-03 · D4 裁决 A）：

```python
def build_stream_for_update_stmt(stream_id: uuid.UUID):
    """构造「加锁读一条物流」的 SELECT（**只构造，不执行**）。

    ## 为什么单独抽一个「只构造」的函数

    两条断言都要钉**生产路径实际用的那条语句**：
    - **方言级**：`with_for_update()` 在 SQLite 上被**方言省略**（单测里等于
      压根没有锁）⇒ 只能靠「用 PG 方言编译这条语句、断言 SQL 里含
      `FOR UPDATE`」来钉住机制；
    - **`populate_existing`**：它是 **C-1 的修复点** ⇒ 删掉它测试仍然绿
      （SQLite 编译掉 FOR UPDATE，行为看着正常）⇒ 必须单独断言。

    ⚠️ 若把 select 写在执行函数里，测试只能**照抄**一遍 ⇒ 照抄的那份与生产
    代码可以各改各的 ⇒ 删掉锁 / 删掉 populate_existing，测试照样绿
    （与 `app/api/v1/records_actions.py::_locked_select` 同一个道理）。
    """
    return (
        select(Stream)
        .where(Stream.stream_id == stream_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )


async def select_stream_for_update(
    db: AsyncSession, stream_id: uuid.UUID
) -> Stream | None:
    """读一条物流并加行锁（**状态转移专用**）。

    ⚠️ **必须**配合 `populate_existing=True` —— 锁读要返回数据库的**最新行**，
    而不是 identity map 里的缓存。

    **为什么这是关键**：如果同 session 里之前已经 load 过这条记录（比如组成
    门禁先读了一次），不加 `populate_existing` 的锁读会返回 identity map 里的
    **旧对象**，而不是数据库里**已经被锁住的新行**。结果：锁虽然加了，但读到
    的数据是旧的 —— 两个并发请求都读到旧状态 `DRAFT`、都判断可以转移到
    `IN_APPROVAL`、都成功。**这就是 P9B-3 评审 C-1 的根因**（行锁形同虚设）。

    ⚠️ 本函数是**单条提交**（`StreamService.transition`）与**批量提交**
    （`stream_batch_service`）的**唯一**加锁入口 —— 不要在别处再写一份
    `SELECT ... FOR UPDATE`，改这里就够了。

    ⚠️ **不得**用 `.with_for_update()` 而不带 `populate_existing` ——
    那在 SQLite 上测不出来（方言省略 `FOR UPDATE`）⇒ 只有方言级断言 +
    `populate_existing` 断言能抓（见 T4）。

    Args:
        db: 会话。
        stream_id: 物流 id。

    Returns:
        锁定后的 Stream 对象；**不存在时返回 `None`**（由调用方抛
        `SIM_STREAM_NOT_FOUND` —— 单条端点的错误文案一字不变）。
    """
    result = await db.execute(build_stream_for_update_stmt(stream_id))
    return result.scalar_one_or_none()
```

⚠️ **与委员会给的签名有一处刻意的偏差**：委员会示意的是
「不存在即抛 404」。本仓的**实际**错误码是 `SIM_STREAM_NOT_FOUND`（不是
`STREAM_NOT_FOUND`），且**批次**需要区分「不存在」（`failed` 里 reason =
`SIM_STREAM_NOT_FOUND`）与「其它失败」⇒ 本计划让它**返回 `None`**，
由两个调用方各自抛 `SIM_STREAM_NOT_FOUND` ⇒ **行为等价、不新增错误码**。

⑥ **把 `StreamService.transition` 改成调用它**（`app/services/stream_service.py`
第 435~442 行那段内联 select）：

```python
        stream = await select_stream_for_update(db, stream_id)
```

⚠️ 其余代码**一字不动**（404 分支、角色解析、try/except、commit、refresh
全部保留）⇒ **行为必须完全不变**。
⚠️ **C-1 的原始测试必须仍然通过，且 `tests/services/test_stream_transition.py`
一行都不许改**（`test_locked_read_is_not_shadowed_by_stale_identity_map` 是
C-1 的兜底）。

- [ ] **Step 4: 跑测试，确认通过**

```bash
cd pcs-backend && uv run pytest tests/services/test_stream_batch_service.py -q
```

Expected: PASS（6 passed）

同时跑既有组成门禁用例，确认**单条端点行为没变**：

```bash
cd pcs-backend && uv run pytest tests/api/v1/test_stream_composition_sum.py tests/services/test_stream_transition.py -q
```

Expected: PASS（全部通过，无新增失败）

⚠️ **C-1 的兜底必须仍然绿**：
`tests/services/test_stream_transition.py::test_locked_read_is_not_shadowed_by_stale_identity_map`
（该文件第 243 行）⇒ 它是「加锁读被 identity map 旧副本遮蔽」的回归测试
⇒ 抽出 helper 后**必须仍然通过**，且**那个文件一行都不许改**
（改了 = 把兜底改成了迎合实现 ⇒ 回归就又藏回去了）。

- [ ] **Step 5: 提交**

```bash
cd /home/pangzy/code_project/PCS && git add pcs-backend/app/services/stream_service.py pcs-backend/app/api/v1/streams.py pcs-backend/app/services/system_setting_service.py pcs-backend/app/models/enums.py pcs-backend/tests/services/test_stream_batch_service.py
git commit -F /tmp/p9b3b-t1-msg.txt
```

（`/tmp/p9b3b-t1-msg.txt` 内容：

```
feat(P9B-3b): 批量提交校对的地基 —— 组成口径单一来源 + 参数读取 + 批次审计动作 + 加锁读唯一入口

T1：四项可复用能力，后续批次 service 全部依赖它们。

1. `composition_mole_fraction_total` 抽到 **service 层** —— 单条端点与批量
   端点**必须同一口径**（口径住在 router 里时 service 只能反向 import 路由
   模块 = 分层倒挂）。
2. `get_setting_value(db, key, default=...)` —— 读系统参数；键不存在返回
   default（上限读不到时批次仍能跑）。
3. `AuditAction.STREAM_BATCH_SUBMITTED` —— 批次级汇总动作（D3 的 N+1 里的
   那 1 条）。
4. `select_stream_for_update()` / `build_stream_for_update_stmt()` —— 抽出
   **唯一**的加锁读入口（单条提交与批量提交共用）；`StreamService.transition`
   改成调用它（**一行替换**）。

⚠️ 单条端点行为**一字未改**（既有组成门禁用例全绿）。
⚠️ **C-1 的兜底测试文件一行未改**（`test_stream_transition.py`）⇒
`test_locked_read_is_not_shadowed_by_stale_identity_map` 仍然绿。
⚠️ `populate_existing=True` 是 **C-1 的修复点** ⇒ 留在 helper 里不动，
并由 T4 的两条断言钉住（方言级 + 执行选项）。
```

）

---

## Task 2: T2 · 批次 service（D1~D6 的全部语义）

**Files:**
- Create: `pcs-backend/app/services/stream_batch_service.py`
- Create/Modify: `pcs-backend/tests/services/test_stream_batch_service.py`（追加本任务的用例）

**Interfaces:**
- Consumes: T1 的 `composition_mole_fraction_total` / `get_setting_value` / `AuditAction.STREAM_BATCH_SUBMITTED`
- Produces:
  - `app.services.stream_batch_service.submit_batch(db: AsyncSession, stream_ids: list[uuid.UUID], *, actor_user_id: uuid.UUID, actor_role: str, dry_run: bool = False) -> StreamBatchSubmitResponse`
  - `app.services.stream_batch_service._locked_select(stream_id: uuid.UUID) -> Select`
    （**加锁读**物流的语句；抽成独立函数是为了方言级断言）
  - `app.schemas.stream_batch.StreamBatchSubmitResponse`（T2 建、T3 用）

- [ ] **Step 1: 写失败测试（契约 + service 行为）**

在 `pcs-backend/tests/services/test_stream_batch_service.py` 追加
（**并在该文件的 import 区补一行** `import pytest_asyncio` —— T1 的文件头
只 import 了 `pytest`，而下面这个 fixture 用的是 `pytest_asyncio.fixture`）：

```python
# ---------------------------------------------------------------------------
# T2：批次 service 本身（D1~D6）
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def batch_project(db_session: AsyncSession):
    """一个项目 + 一个工作区（批次里的物流都挂在它下面）。"""
    from app.models.project import Project, Workspace

    ws = Workspace(workspace_type="FORMAL", name=f"ws-{uuid.uuid4().hex[:8]}")
    db_session.add(ws)
    await db_session.flush()
    proj = Project(
        project_no=f"P-{uuid.uuid4().hex[:8]}",
        project_name="批量测试",
        owner_company="测试业主",
        location="测试地点",
        project_type="CHEMICAL",
        design_phase="FEED",
        unit_system="SI",
        workspace_id=ws.workspace_id,
    )
    db_session.add(proj)
    await db_session.commit()
    return proj


async def _make_draft(db: AsyncSession, proj, name: str, composition=None) -> Stream:
    """建一条 DRAFT 物流（绕过 API：service 层只关心状态与组成）。"""
    stream = Stream(
        project_id=proj.project_id,
        workspace_id=proj.workspace_id,
        stream_name=name,
        case_type="NORMAL",
        data_mode="CHEMICAL",
        source_type="MANUAL_ENTRY",
        source="MANUAL",
        phase="LIQUID",
        temp=80.0,
        press=200.0,
        mass_flow=1000.0,
        composition_json=composition if composition is not None else {"7732-18-5": 1.0},
        sign_status=StreamSignStatus.DRAFT,
        # ⚠️ `approval_depth` 是 Stream 上**唯一没有默认值**的 NOT NULL 列
        #   （cerebrum Do-Not-Repeat：写 DB fixture 前必查 NOT NULL 列）
        #   ⇒ 取值与 `StreamService.create` 一致（1 步校对）。
        approval_depth=1,
    )
    db.add(stream)
    await db.commit()
    await db.refresh(stream)
    return stream


async def test_batch_deduplicates_stream_ids(db_session, batch_project):
    """⚠️ Review Focus #1：同一批里重复的 id **只处理一次**，`total` 是去重后的条数。"""
    from app.services.stream_batch_service import submit_batch

    s = await _make_draft(db_session, batch_project, "S-1")
    result = await submit_batch(
        db_session,
        [s.stream_id, s.stream_id, s.stream_id],
        actor_user_id=uuid.uuid4(),
        actor_role="DESIGNER",
    )

    assert result.total == 1
    assert len(result.succeeded) == 1
    assert len(result.failed) == 0


async def test_batch_success_moves_status_and_reports_transition(
    db_session, batch_project
):
    """正常路径：DRAFT → IN_APPROVAL，响应里 from/to 都给。"""
    from app.services.stream_batch_service import submit_batch

    s = await _make_draft(db_session, batch_project, "S-1")
    result = await submit_batch(
        db_session,
        [s.stream_id],
        actor_user_id=uuid.uuid4(),
        actor_role="DESIGNER",
    )

    assert result.total == 1
    assert len(result.succeeded) == 1
    item = result.succeeded[0]
    assert item.stream_id == s.stream_id
    assert item.from_status == "DRAFT"
    assert item.to_status == "IN_APPROVAL"
    assert item.note is None

    await db_session.refresh(s)
    assert s.sign_status.value == "IN_APPROVAL"


async def test_batch_partial_success_does_not_roll_back_the_good_ones(
    db_session, batch_project
):
    """⚠️ Review Focus #4（D2 的全部意义）：一条失败**不回滚**成功的那些。

    失败样本：组成合计 98.7%（门禁拒）⇒ 状态不变；成功样本：正常转移。
    """
    from sqlalchemy import update

    from app.services.stream_batch_service import submit_batch

    good = await _make_draft(db_session, batch_project, "GOOD")
    bad = await _make_draft(db_session, batch_project, "BAD")
    await db_session.execute(
        update(Stream)
        .where(Stream.stream_id == bad.stream_id)
        .values(composition_json={"7732-18-5": 0.6, "7440-23-5": 0.387})
    )
    await db_session.commit()

    result = await submit_batch(
        db_session,
        [good.stream_id, bad.stream_id],
        actor_user_id=uuid.uuid4(),
        actor_role="DESIGNER",
    )

    assert [i.stream_id for i in result.succeeded] == [good.stream_id]
    assert [i.stream_id for i in result.failed] == [bad.stream_id]
    assert result.failed[0].reason == "SIM_STREAM_COMPOSITION_OUT_OF_RANGE"

    await db_session.refresh(good)
    await db_session.refresh(bad)
    assert good.sign_status.value == "IN_APPROVAL", "成功的被失败的那条回滚了"
    assert bad.sign_status.value == "DRAFT", "失败的这条状态变了"


async def test_batch_already_in_approval_is_idempotent_success(db_session, batch_project):
    """⚠️ Review Focus #2（D5）：已 `IN_APPROVAL` ⇒ 记**成功** + `note`，且**不重复转移**。"""
    from app.services.stream_batch_service import submit_batch

    s = await _make_draft(db_session, batch_project, "S-1")
    s.sign_status = StreamSignStatus.IN_APPROVAL
    await db_session.commit()

    result = await submit_batch(
        db_session,
        [s.stream_id],
        actor_user_id=uuid.uuid4(),
        actor_role="DESIGNER",
    )

    assert len(result.failed) == 0
    item = result.succeeded[0]
    assert item.note == "already_in_approval"
    assert item.from_status == "IN_APPROVAL"
    assert item.to_status == "IN_APPROVAL"


async def test_batch_reports_missing_stream_as_failed_item(db_session, batch_project):
    """不存在的 id ⇒ **该条**失败（`SIM_STREAM_NOT_FOUND`），整批**不**报错。"""
    from app.services.stream_batch_service import submit_batch

    result = await submit_batch(
        db_session,
        [uuid.uuid4()],
        actor_user_id=uuid.uuid4(),
        actor_role="DESIGNER",
    )

    assert result.total == 1
    assert len(result.succeeded) == 0
    assert result.failed[0].reason == "SIM_STREAM_NOT_FOUND"


async def test_batch_rejects_stream_in_non_submittable_status(db_session, batch_project):
    """已 `CHECKED`（不可再提交）⇒ 该条失败 `SIM_STREAM_INVALID_TRANSITION`。"""
    from app.services.stream_batch_service import submit_batch

    s = await _make_draft(db_session, batch_project, "S-1")
    s.sign_status = StreamSignStatus.CHECKED
    await db_session.commit()

    result = await submit_batch(
        db_session,
        [s.stream_id],
        actor_user_id=uuid.uuid4(),
        actor_role="DESIGNER",
    )

    assert len(result.succeeded) == 0
    assert result.failed[0].reason == "SIM_STREAM_INVALID_TRANSITION"


async def test_batch_limit_exceeded_raises(db_session, batch_project):
    """D4：超过上限 ⇒ 整批拒（422 `SIM_STREAM_BATCH_LIMIT_EXCEEDED`），**不**部分执行。"""
    from app.core.errors import PcsError
    from app.services.stream_batch_service import submit_batch

    ids = [uuid.uuid4() for _ in range(3)]
    with pytest.raises(PcsError) as exc:
        await submit_batch(
            db_session,
            ids,
            actor_user_id=uuid.uuid4(),
            actor_role="DESIGNER",
            limit=2,
        )
    assert exc.value.code == "SIM_STREAM_BATCH_LIMIT_EXCEEDED"
    assert exc.value.status == 422


async def test_batch_limit_is_configurable(db_session, batch_project):
    """D4 的上限**取自系统参数**（`stream.batch_submit_limit`），不是写死的 100。"""
    from app.services.system_setting_service import get_setting_value, seed_defaults, update_batch

    await seed_defaults(db_session)
    await db_session.commit()
    await update_batch(
        db_session,
        {"stream.batch_submit_limit": 1},
        actor_user_id=uuid.uuid4(),
    )
    await db_session.commit()
    assert await get_setting_value(db_session, "stream.batch_submit_limit") == 1

    s = await _make_draft(db_session, batch_project, "S-1")
    s2 = await _make_draft(db_session, batch_project, "S-2")

    from app.core.errors import PcsError
    from app.services.stream_batch_service import submit_batch

    with pytest.raises(PcsError) as exc:
        await submit_batch(
            db_session,
            [s.stream_id, s2.stream_id],
            actor_user_id=uuid.uuid4(),
            actor_role="DESIGNER",
        )
    assert exc.value.code == "SIM_STREAM_BATCH_LIMIT_EXCEEDED"


async def test_dry_run_changes_nothing_and_writes_no_audit(db_session, batch_project):
    """⚠️ Review Focus #3（D6）：预演 ⇒ 状态不变、**审计表零新增**（连批次那条也没有）。"""
    from sqlalchemy import func, select

    from app.models.system import AuditLog
    from app.services.stream_batch_service import submit_batch

    s = await _make_draft(db_session, batch_project, "S-1")
    before = (
        await db_session.execute(select(func.count()).select_from(AuditLog))
    ).scalar_one()

    result = await submit_batch(
        db_session,
        [s.stream_id],
        actor_user_id=uuid.uuid4(),
        actor_role="DESIGNER",
        dry_run=True,
    )

    assert result.dry_run is True
    assert len(result.succeeded) == 1
    assert result.succeeded[0].to_status == "IN_APPROVAL"

    await db_session.refresh(s)
    assert s.sign_status.value == "DRAFT", "预演改了状态"

    after = (
        await db_session.execute(select(func.count()).select_from(AuditLog))
    ).scalar_one()
    assert after == before, "预演写了审计"


async def test_dry_run_still_reports_failures(db_session, batch_project):
    """预演也要**报出失败项**（否则「预演」等于「说没事」）。"""
    from sqlalchemy import update

    from app.services.stream_batch_service import submit_batch

    bad = await _make_draft(db_session, batch_project, "BAD")
    await db_session.execute(
        update(Stream)
        .where(Stream.stream_id == bad.stream_id)
        .values(composition_json={"7732-18-5": 0.6, "7440-23-5": 0.387})
    )
    await db_session.commit()

    result = await submit_batch(
        db_session,
        [bad.stream_id],
        actor_user_id=uuid.uuid4(),
        actor_role="DESIGNER",
        dry_run=True,
    )

    assert len(result.failed) == 1
    assert result.failed[0].reason == "SIM_STREAM_COMPOSITION_OUT_OF_RANGE"


# ---------------------------------------------------------------------------
# T2 补充：union 契约的三个断言（委员会 2026-11-03 · D5 裁决「必须加的三个测试」）
# ---------------------------------------------------------------------------


async def test_succeeded_item_requires_from_status():
    """成功项的 `from_status` **必填** —— 缺字段要抛 ValidationError。

    ⚠️ 这是「去掉中间类型」相对「保留 `_Outcome`」的核心优势之一：
    `_Outcome` 能构造出 `ok=True, from_status=None` 的非法状态（静态类型挡不住），
    union 的两个契约类型**每个字段都必填** ⇒ 非法状态构造不出来。
    """
    from pydantic import ValidationError

    from app.schemas.stream_batch import BatchSucceededItem

    with pytest.raises(ValidationError):
        BatchSucceededItem(
            status="succeeded",
            stream_id=uuid.uuid4(),
            to_status="IN_APPROVAL",
            note=None,
            # from_status 缺失
        )


async def test_batch_response_splits_by_status(db_session, batch_project):
    """成功的进 `succeeded`、失败的进 `failed`，**无交叉**（靠 `status` 判别）。"""
    from sqlalchemy import update

    from app.services.stream_batch_service import submit_batch

    good = await _make_draft(db_session, batch_project, "GOOD")
    bad = await _make_draft(db_session, batch_project, "BAD")
    await db_session.execute(
        update(Stream)
        .where(Stream.stream_id == bad.stream_id)
        .values(composition_json={"7732-18-5": 0.6, "7440-23-5": 0.387})
    )
    await db_session.commit()

    result = await submit_batch(
        db_session,
        [good.stream_id, bad.stream_id],
        actor_user_id=uuid.uuid4(),
        actor_role="DESIGNER",
    )

    assert len(result.succeeded) == 1
    assert len(result.failed) == 1
    # ⚠️ **无交叉**：两张清单里的 `status` 必须各自纯粹
    assert all(item.status == "succeeded" for item in result.succeeded)
    assert all(item.status == "failed" for item in result.failed)
    assert result.succeeded[0].stream_id == good.stream_id
    assert result.failed[0].stream_id == bad.stream_id


async def test_submit_one_returns_contract_types():
    """⚠️ **结构性断言**：`_submit_one` 的返回类型**必须**是契约里的两个类型。

    这条不测行为、测**类型关系** ⇒ 保证「有人把 `_submit_one` 改成返回
    `_Outcome`（或别的中间类型）」时立刻变红 ⇒ 契约与实现**不会分叉**
    （字段定义只有一处）。
    """
    import inspect

    from app.services import stream_batch_service

    sig = inspect.signature(stream_batch_service._submit_one)
    return_type = str(sig.return_annotation)
    assert "BatchSucceededItem" in return_type, return_type
    assert "BatchFailedItem" in return_type, return_type


# ---------------------------------------------------------------------------
# T2 补充：三条「计划里写了分支但没写测试」的缺口（2026-11-03 eng review）
# ---------------------------------------------------------------------------


async def test_unexpected_error_becomes_failed_item_and_batch_continues(
    db_session, batch_project, monkeypatch
):
    """⚠️ 非预期异常 ⇒ 变成 `INTERNAL_ERROR` 的失败项，**且批次继续**。

    这是委员会 D5 刚加的兜底路径（`_submit_one` 的 `except Exception`）⇒
    必须有测试钉住两件事：① 不抛异常；② **后面的条目照常处理**。
    """
    from app.services import stream_batch_service

    good = await _make_draft(db_session, batch_project, "GOOD")
    boom = await _make_draft(db_session, batch_project, "BOOM")

    original = stream_batch_service.StreamService.transition

    async def exploding(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(
        stream_batch_service.StreamService, "transition", staticmethod(exploding)
    )

    result = await stream_batch_service.submit_batch(
        db_session,
        [boom.stream_id, good.stream_id],
        actor_user_id=uuid.uuid4(),
        actor_role="DESIGNER",
    )

    # 两条都失败，但**没有异常冒泡**
    assert len(result.failed) == 2
    assert all(item.reason == "INTERNAL_ERROR" for item in result.failed)
    # ⚠️ 失败项**不泄露内部细节**
    assert all("boom" not in (item.detail or "") for item in result.failed)
    monkeypatch.setattr(
        stream_batch_service.StreamService, "transition", original
    )


async def test_single_item_role_forbidden_becomes_failed_item(db_session, batch_project):
    """⚠️ 单条**角色无权** ⇒ 该条失败 `SIM_STREAM_ROLE_FORBIDDEN`（批次继续）。

    ⚠️ HTTP 上走不到这条（端点 ACL 已经把 VIEWER 挡在外面）⇒
    但**服务层是公开 API** ⇒ 逐条的角色校验必须有测试。
    """
    from app.services.stream_batch_service import submit_batch

    s = await _make_draft(db_session, batch_project, "S-1")
    result = await submit_batch(
        db_session,
        [s.stream_id],
        actor_user_id=uuid.uuid4(),
        actor_role="VIEWER",  # 不在 TRANSITION_ROLES[SUBMIT_FOR_CHECK] 里
    )

    assert len(result.succeeded) == 0
    assert result.failed[0].reason == "SIM_STREAM_ROLE_FORBIDDEN"


async def test_batch_audit_write_failure_still_returns_results(
    db_session, batch_project, monkeypatch
):
    """⚠️ **批次审计写失败** ⇒ 已提交的条目**不回滚**、仍返 207、响应带 `warning`。

    （委员会 2026-11-03 · D7 裁决的「遗漏项」：批次审计是**最后**单独写的，
    写失败**绝不能**把已提交的成果回滚掉 —— 那是 D2「部分成功」的成果。）
    """
    from app.services import stream_batch_service

    s = await _make_draft(db_session, batch_project, "S-1")

    class _BoomAudit:
        """只让**批次模块**用的 AuditService 抛错（状态机自己的审计不受影响）。"""

        def __init__(self, _db):
            pass

        async def write(self, **_kwargs):
            raise RuntimeError("audit down")

    monkeypatch.setattr(stream_batch_service, "AuditService", _BoomAudit)

    result = await stream_batch_service.submit_batch(
        db_session,
        [s.stream_id],
        actor_user_id=uuid.uuid4(),
        actor_role="DESIGNER",
    )

    # ⚠️ 条目**已经提交**（状态真的变了）⇒ 不能因为批次审计失败而回滚
    await db_session.refresh(s)
    assert s.sign_status.value == "IN_APPROVAL", "批次审计失败把已提交的结果回滚了"
    # ⚠️ 但响应必须**如实**说「批次记录没写成」
    assert result.warning is not None
    assert "批次记录写入失败" in result.warning
    assert len(result.succeeded) == 1


async def test_batch_limit_falls_back_when_value_is_garbage(db_session, batch_project):
    """⚠️ 上限的**值不是整数** / **小于 1** ⇒ 回落默认值（不崩、不放行无上限）。"""
    from app.services.system_setting_service import seed_defaults, update_batch

    await seed_defaults(db_session)
    await db_session.commit()

    from app.services.stream_batch_service import submit_batch

    s = await _make_draft(db_session, batch_project, "S-1")

    # ① 值不是整数 ⇒ 回落 100（这条能过 ⇒ 上限**没有**变成「无上限」）
    await update_batch(
        db_session, {"stream.batch_submit_limit": "abc"}, actor_user_id=uuid.uuid4()
    )
    await db_session.commit()
    result = await submit_batch(
        db_session,
        [s.stream_id],
        actor_user_id=uuid.uuid4(),
        actor_role="DESIGNER",
    )
    assert len(result.succeeded) == 1, "上限读成垃圾值时不该整批失败"

    # ② limit < 1 ⇒ 兜底成 1（不是 0 ⇒ 那样任何批次都会被拒）
    await update_batch(
        db_session, {"stream.batch_submit_limit": 0}, actor_user_id=uuid.uuid4()
    )
    await db_session.commit()
    from app.core.errors import PcsError

    # ⚠️ **必须两条不同的物流** —— 同一个 id 传两次会被**去重**（D5）⇒
    #   去重后只剩 1 条 ⇒ 永远超不过上限 ⇒ 断言不可能成立。
    s2 = await _make_draft(db_session, batch_project, "S-2")
    with pytest.raises(PcsError) as exc:
        await submit_batch(
            db_session,
            [s.stream_id, s2.stream_id],
            actor_user_id=uuid.uuid4(),
            actor_role="DESIGNER",
        )
    assert exc.value.code == "SIM_STREAM_BATCH_LIMIT_EXCEEDED"
```

⚠️ 上面 `submit_batch(..., limit=2)` 用的是**显式参数**——本任务的服务签名里
`limit` 是**可选覆盖**（默认 `None` ⇒ 读系统参数）⇒ 端点层不传 ⇒ 走配置值。

- [ ] **Step 2: 跑测试，确认失败**

```bash
cd pcs-backend && uv run pytest tests/services/test_stream_batch_service.py -q
```

Expected: FAIL —— `ModuleNotFoundError: No module named 'app.services.stream_batch_service'`

- [ ] **Step 3: 建契约 schema**

创建 `pcs-backend/app/schemas/stream_batch.py`：

```python
"""批量「提交校对」的请求/响应契约（P9B-3b · D1~D6）。

⚠️ **具名 schema**（不是裸 dict）⇒ 前端类型可契约派生，且
`check_openapi_payload_coverage.py` 的裸载荷数**不涨**。
"""

from __future__ import annotations

import uuid
from typing import Literal

from pydantic import BaseModel, Field


class StreamBatchSubmitRequest(BaseModel):
    """批量提交校对的请求体。"""

    stream_ids: list[uuid.UUID] = Field(
        min_length=1,
        description=(
            "待提交校对的物流 id 列表（批次内**去重**；上限取系统参数 "
            "`stream.batch_submit_limit`，默认 100）"
        ),
    )
    dry_run: bool = Field(
        default=False,
        description="true ⇒ **只校验**：不改状态、不写审计（含批次那条）",
    )


class BatchSucceededItem(BaseModel):
    """一条成功的物流。

    ⚠️ `status` 是**判别字段**（discriminator）—— 成功与失败是**两个类型**的
    union ⇒ 前端与调用方都靠 `status` 分流，不必靠「在哪个数组里」判断
    （委员会 2026-11-03 · D5 裁决）。
    """

    status: Literal["succeeded"] = Field(description="判别字段：恒为 succeeded")
    stream_id: uuid.UUID
    from_status: str = Field(description="转移前的状态")
    to_status: str = Field(description="转移后的状态")
    note: str | None = Field(
        default=None,
        description="幂等命中标记：已 IN_APPROVAL 时为 `already_in_approval`",
    )


class BatchFailedItem(BaseModel):
    """一条失败的物流。"""

    status: Literal["failed"] = Field(description="判别字段：恒为 failed")
    stream_id: uuid.UUID
    reason: str = Field(
        description=(
            "具名错误码（如 `SIM_STREAM_COMPOSITION_OUT_OF_RANGE` / "
            "`SIM_STREAM_INVALID_TRANSITION` / `SIM_STREAM_NOT_FOUND` / "
            "`INTERNAL_ERROR`）"
        )
    )
    detail: str | None = Field(default=None, description="人类可读的失败原因")


class StreamBatchSubmitResponse(BaseModel):
    """207 Multi-Status 的批次结果。"""

    batch_id: uuid.UUID = Field(description="批次 id（同时是批次审计的 resource_id）")
    total: int = Field(description="**去重后**实际处理的条数")
    succeeded: list[BatchSucceededItem] = Field(default_factory=list)
    failed: list[BatchFailedItem] = Field(default_factory=list)
    dry_run: bool = Field(default=False, description="true ⇒ 本次是预演")
    warning: str | None = Field(
        default=None,
        description=(
            "**批次级**告警（如「批次记录写入失败」）；条目级问题在 `failed` 里"
        ),
    )
```

- [ ] **Step 4: 实现批次 service**

创建 `pcs-backend/app/services/stream_batch_service.py`：

```python
"""批量「提交校对」（P9B-3b · 委员会裁决 5 的 D1~D6）。

## 契约要点

- **D1** 后端端点：一次请求 N 条（前端**不**循环 —— 部分失败无法重试）。
- **D2** 部分成功：一条失败**不回滚**其它条。
- **D3** 审计 N+1：每条**真正转移**的物流 1 条 `RECORD_TRANSITION`（状态机写）
  + 批次 1 条 `STREAM_BATCH_SUBMITTED`（本模块写）。
- **D4** 上限取 `system_settings.stream.batch_submit_limit`（默认 100）。
- **D5** 幂等：批次内按 `stream_id` 去重；**已 `IN_APPROVAL`** 记成功
  （`note="already_in_approval"`）⇒ 重复提交**不报错**、也**不重复写审计**。
- **D6** `dry_run=true` ⇒ 不改状态、**不写任何审计**（含批次那条），
  只返回每条的预判结果。

## ⚠️ 为什么**逐条 commit**（而不是整批一个事务）

`StreamService.transition` 在非法转移 / 越权时 `await db.rollback()` ——
**rollback 掉的是「当前事务」** ⇒ 若整批共用一个事务，**一条失败会把前面已经
成功的那些全回滚掉**（与 D2 相反）⇒ 故每条自成事务：一条失败只回滚它自己。

⚠️ **「用 SAVEPOINT 隔离每条」这条路走不通**（2026-11-03 · D7 **实测**）：
在 `begin_nested()` 内调用 **session 级** `await db.rollback()` ⇒
**整个外层事务被关掉**（实测：后续 insert 报 `Can't operate on closed
transaction`，连 savepoint 之外的那行也没落库）⇒
**实测比文档措辞可靠**：只有 `begin_nested()` 返回的 `SessionTransaction`
句柄的 `rollback()` 才只回滚到 savepoint ⇒ 而 `transition` 内部调的是
session 级 `db.rollback()` ⇒ 救不了 ⇒ **逐条 commit 是唯一可行解**。

⚠️ **「整批一个事务」被排除的根本理由不是死锁，而是与 D2 冲突**：
D2 已裁决「部分成功」（50 条里 8 条失败不该回滚 42 条）⇒
「全成或全不成」是 D2 的反面。（死锁是可排序修复的次要问题，且逐条 commit
天然只持一把锁 ⇒ 没有死锁面。）

⚠️ **性能代价（实测本机 PG：18.6 · `synchronous_commit=on` · `fsync=on` ·
`wal_sync_method=fdatasync`）**：100 条 = 100 次 COMMIT ⇒ 每次一次 WAL fsync
≈ 0.5~2ms ⇒ 合计 **≈ 50~200ms** ⇒ **用户感知上不可区分**（< 200ms），
但吞吐量上确实有差 ⇒ 这是**刻意接受**的代价（换来：不持多把锁 + 与单条端点
**走同一条状态机路径**）。

⚠️ **实现形态（已核实，勿画蛇添足）**：`StreamService.transition` 内部
**自己** `db.commit()`（成功路径，第 477 行）+ `db.refresh()`，错误路径
`db.rollback()`（第 463/470 行）⇒ ⇒ **批次 service 不要用
`async with db.begin():` 包每条**（transition 已经提交了，再 commit 会撞
「closed transaction」）⇒ **直接调 transition，让它自己提交**就是「逐条 commit」
的正确实现 ⇒ 批次 service 在条目之间**不需要**额外的 commit / rollback。

## ⚠️ 为什么加锁读用 `populate_existing=True`

同 P9B-3 评审 C-1：加锁读的**目的**就是读「锁住的那一行」⇒ 若 session 里
已有同 PK 的实体（identity map），SQLAlchemy **默认不覆盖**它的已加载属性
⇒ 读到的是**过期**状态 ⇒ 并发时两个提交都基于同一个旧状态通过 ⇒ 行锁形同虚设。
"""

from __future__ import annotations

import logging
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import PcsError
from app.models.enums import AuditAction, StateTransition, StreamSignStatus
from app.models.project import Stream
from app.schemas.stream_batch import (
    BatchFailedItem,
    BatchSucceededItem,
    StreamBatchSubmitResponse,
)
from app.services.audit_service import AuditService
from app.services.stream_service import (
    StreamService,
    composition_mole_fraction_total,
    select_stream_for_update,
)
from app.services.system_setting_service import get_setting_value

logger = logging.getLogger(__name__)

#: 批次上限的配置键（值在 `system_settings` 表里，管理员可改）。
BATCH_LIMIT_SETTING_KEY = "stream.batch_submit_limit"

#: 配置读不到时的兜底上限（与 `DEFAULT_SETTINGS` 的 seed 值一致）。
DEFAULT_BATCH_LIMIT = 100

#: 组成合计的容差（≡ SPEC §7.7.2「100±0.5%」）。
COMPOSITION_TOLERANCE = 0.005

#: 幂等命中时的 `note`。
NOTE_ALREADY_IN_APPROVAL = "already_in_approval"


async def _batch_limit(db: AsyncSession) -> int:
    """批次上限（`system_settings.stream.batch_submit_limit`，默认 100）。"""
    raw = await get_setting_value(
        db, BATCH_LIMIT_SETTING_KEY, default=DEFAULT_BATCH_LIMIT
    )
    try:
        limit = int(raw)
    except (TypeError, ValueError):
        limit = DEFAULT_BATCH_LIMIT
    return max(limit, 1)


async def _submit_one(
    db: AsyncSession,
    stream_id: uuid.UUID,
    *,
    actor_user_id: uuid.UUID,
    actor_role: str,
    dry_run: bool,
) -> BatchSucceededItem | BatchFailedItem:
    """处理一条 ⇒ 返回**成功或失败**（**绝不抛异常**）。

    ⚠️ **绝不抛异常**是批次语义（D2 部分成功）的一部分：任何一条出错都必须
    变成 `BatchFailedItem`，**不能**让异常冒泡中断整个批次（委员会
    2026-11-03 · D5 裁决的「附加」条款）。

    ⚠️ 返回类型是 **union**（不是「带 ok 开关的 `_Outcome`」）：
    - 成功项只有成功的字段（`from_status` / `to_status` / `note`）；
    - 失败项只有失败的字段（`reason` / `detail`）；
    - `status` 是**判别字段** ⇒ 调用方与前端都靠它分流。

    ⚠️ 契约类型与内部计算是**同一件事**（批次结果就只是「成功 / 失败」）⇒
    直接返回契约类型，**不再有中间类型**（字段定义只有一处 ⇒ 不会分叉）。
    ⚠️ 这确实是**新引入的返回类型耦合**（`StreamService.transition` 返回的是
    ORM 实体 `Stream`）⇒ 理由是「批次结果的语义就是 schema 的语义」，
    **不是**「延续惯例」。
    """
    try:
        return await _submit_one_inner(
            db,
            stream_id,
            actor_user_id=actor_user_id,
            actor_role=actor_role,
            dry_run=dry_run,
        )
    except PcsError as e:
        return BatchFailedItem(
            status="failed",
            stream_id=stream_id,
            reason=getattr(e, "code", "SIM_STREAM_UNKNOWN"),
            detail=str(e),
        )
    except Exception:  # noqa: BLE001 —— 兜底：非预期异常也**不中断批次**
        # ⚠️ 这不是「打补丁」，是批次语义的要求：单条失败不应中断批次。
        logger.exception("批量提交校对：条目 %s 处理失败", stream_id)
        return BatchFailedItem(
            status="failed",
            stream_id=stream_id,
            reason="INTERNAL_ERROR",
            detail="服务端内部错误，请联系管理员",
        )


async def _submit_one_inner(
    db: AsyncSession,
    stream_id: uuid.UUID,
    *,
    actor_user_id: uuid.UUID,
    actor_role: str,
    dry_run: bool,
) -> BatchSucceededItem | BatchFailedItem:
    """处理一条的**业务逻辑**（异常由 `_submit_one` 统一兜住）。"""
    if dry_run:
        # ⚠️ 预演**不加锁**（不改任何东西 ⇒ 不该占着别人的行锁）。
        stream = (
            await db.execute(
                select(Stream).where(Stream.stream_id == stream_id)
            )
        ).scalar_one_or_none()
    else:
        # ⚠️ 加锁读走**唯一入口**（T1 抽出的 `select_stream_for_update`）——
        #    它带 `populate_existing=True`（C-1 的修复点）⇒ 并发时读到的是
        #    **锁住的那一行**，不是 identity map 里的旧副本。
        stream = await select_stream_for_update(db, stream_id)

    if stream is None:
        return BatchFailedItem(
            status="failed",
            stream_id=stream_id,
            reason="SIM_STREAM_NOT_FOUND",
            detail=f"物流 {stream_id} 不存在",
        )

    from_status = str(
        stream.sign_status.value
        if hasattr(stream.sign_status, "value")
        else stream.sign_status
    )

    # D5 幂等：已 IN_APPROVAL ⇒ 记成功，**不重复转移、不重复写审计**。
    if from_status == StreamSignStatus.IN_APPROVAL.value:
        return BatchSucceededItem(
            status="succeeded",
            stream_id=stream_id,
            from_status=from_status,
            to_status=from_status,
            note=NOTE_ALREADY_IN_APPROVAL,
        )

    # 组成合计门禁（与单条端点**同一口径**）。
    total = composition_mole_fraction_total(stream)
    if total is not None and abs(total - 1.0) > COMPOSITION_TOLERANCE:
        return BatchFailedItem(
            status="failed",
            stream_id=stream_id,
            reason="SIM_STREAM_COMPOSITION_OUT_OF_RANGE",
            detail=(
                f"物流 {stream_id} 的组成摩尔分率合计 {total * 100:.2f}%，"
                "不在 100±0.5% 内 ⇒ 不能提交校对"
            ),
        )

    if dry_run:
        # D6：预演 ⇒ 只给结论，不改状态、不写审计。
        return BatchSucceededItem(
            status="succeeded",
            stream_id=stream_id,
            from_status=from_status,
            to_status=StreamSignStatus.IN_APPROVAL.value,
        )

    # 真正的转移：行锁 + 角色校验 + 单条审计 + **提交**（逐条独立事务）。
    await StreamService.transition(
        db,
        stream_id,
        transition=StateTransition.SUBMIT_FOR_CHECK,
        actor_user_id=actor_user_id,
        actor_role=actor_role,
    )

    return BatchSucceededItem(
        status="succeeded",
        stream_id=stream_id,
        from_status=from_status,
        to_status=StreamSignStatus.IN_APPROVAL.value,
    )


async def _write_batch_audit(
    db: AsyncSession,
    *,
    batch_id: uuid.UUID,
    total: int,
    succeeded: list[BatchSucceededItem],
    failed: list[BatchFailedItem],
    actor_user_id: uuid.UUID,
    actor_role: str,
) -> None:
    """写批次审计（D7 的**最后一个**事务；预演不写）。

    ## ⚠️ 审计记录的形状（**给审计页的用户看的**）

    - `action = STREAM_BATCH_SUBMITTED`
    - `resource_type = "STREAM_BATCH"` ← **本批新增的资源类型**
    - `resource_id = str(batch_id)` ← **必须**等于响应里的 `batch_id`
      ⇒ 用户拿到 `batch_id` ⇒ 管理员就能在审计页查到这一批
      （**由测试 `test_batch_audit_resource_id_equals_response_batch_id` 钉住**）
    - `detail_json = {batch_id, total, succeeded_ids, failed_ids, dry_run,
      requester_user_id, requester_role, succeeded[], failed[]}`

    ## ⚠️ 怎么在审计页查到它（本批的审计页现状）

    审计页（`/audit`）的 `resource_type` 过滤是**自由文本输入框**（**不是下拉**
    —— `AuditLogPage.tsx:395`）⇒ 查批次审计的步骤：
    1. 打开 `/audit`；
    2. `resource_type` 输入 `STREAM_BATCH`；
    3. 知道批次 id 的话，`resource_id` 再输入那个 `batch_id`（uuid）；
    4. `action` 过滤可不填（会显示所有批次审计）。

    ⚠️ **不要在审计页加「STREAM_BATCH 下拉项」** —— 那是审计页的**通用**改进
    （`resource_type` 的下拉需要一个**权威词表来源**，而那个来源目前**不存在**
    ⇒ 不是「枚举词表麻烦」，是「未设计的通用功能」）⇒ **不是本批的事**。
    批次自己的义务是「**文档化自己的输出格式**」。

    ## ⚠️ 写失败**不能**回滚已提交的结果

    调用方兜住异常（记 ERROR 日志 + 回滚**这次**写入 + 在响应里带 `warning`）
    ⇒ 已提交的 stream 是 D2「部分成功」的成果，回滚它们违背 D2。
    """
    await AuditService(db).write(
        action=AuditAction.STREAM_BATCH_SUBMITTED,
        resource_type="STREAM_BATCH",
        resource_id=str(batch_id),
        user_id=actor_user_id,
        detail={
            # ⚠️ **审计完整性**（委员会 2026-11-03 · D3 约束 2）：本端点
            #    **没有项目守卫**（与既有单条端点同口径，见 T6 登记的
            #    TODO-118）⇒ 审计是**唯一**的事后追溯手段 ⇒ 这一行必须
            #    一次说清「谁 · 哪一批 · 动了哪些 · 每条什么结果」。
            "batch_id": str(batch_id),
            "total": total,
            "dry_run": False,
            "requester_user_id": str(actor_user_id),
            "requester_role": actor_role,
            # ⚠️ 两个 id 数组 = 「这一批动了哪些」的**可 grep** 形态
            #    （完整条目里也带 stream_id，但审计排查时按 id 数组找更快）
            "succeeded_ids": [str(item.stream_id) for item in succeeded],
            "failed_ids": [str(item.stream_id) for item in failed],
            # 完整条目（带 from/to/note 与 reason/detail ⇒ **失败原因不丢**）
            "succeeded": [item.model_dump(mode="json") for item in succeeded],
            "failed": [item.model_dump(mode="json") for item in failed],
        },
    )
    await db.commit()


async def submit_batch(
    db: AsyncSession,
    stream_ids: list[uuid.UUID],
    *,
    actor_user_id: uuid.UUID,
    actor_role: str,
    dry_run: bool = False,
    limit: int | None = None,
) -> StreamBatchSubmitResponse:
    """批量提交校对（D1~D6）。

    Args:
        db: async session
        stream_ids: 待提交的物流 id（**去重后**处理；保留请求顺序）
        actor_user_id: 操作用户（写审计）
        actor_role: 操作用户角色（状态机按 `TRANSITION_ROLES` 校验）
        dry_run: 只校验，不改状态、不写审计（D6）
        limit: **覆盖**批次上限（默认 `None` ⇒ 读系统参数 `stream.batch_submit_limit`）

    Returns:
        207 的批次结果（成功清单 + 失败清单）。

    Raises:
        PcsError: 422 —— 超过批次上限（整批拒，**不**部分执行）。
    """
    effective_limit = limit if limit is not None else await _batch_limit(db)

    # D5 去重（保留请求顺序 ⇒ 响应顺序可预期）。
    unique_ids = list(dict.fromkeys(stream_ids))

    if len(unique_ids) > effective_limit:
        raise PcsError(
            code="SIM_STREAM_BATCH_LIMIT_EXCEEDED",
            message=(
                f"批量提交 {len(unique_ids)} 条，超过上限 {effective_limit} 条"
                f"（系统参数 {BATCH_LIMIT_SETTING_KEY}）"
            ),
            status=422,
            detail={
                "limit": effective_limit,
                "requested": len(unique_ids),
                "setting_key": BATCH_LIMIT_SETTING_KEY,
            },
        )

    batch_id = uuid.uuid4()
    outcomes: list[BatchSucceededItem | BatchFailedItem] = []

    for stream_id in unique_ids:
        outcomes.append(
            await _submit_one(
                db,
                stream_id,
                actor_user_id=actor_user_id,
                actor_role=actor_role,
                dry_run=dry_run,
            )
        )

    # 分流：靠 **status 判别字段**（不用 isinstance —— JSON 序列化后
    # isinstance 的信息会丢，而 `status` 会留在契约里 ⇒ 前端也能靠它分流）。
    succeeded = [o for o in outcomes if o.status == "succeeded"]
    failed = [o for o in outcomes if o.status == "failed"]

    # D3 批次审计（D6：预演**不写**）。
    # ⚠️ **批次审计的写入时机**（委员会 2026-11-03 · D7 裁决的「遗漏项」）：
    #   - 每条 stream 的审计（`RECORD_TRANSITION`）在**每条自己的事务**里
    #     （随那条一起 commit / rollback）；
    #   - 批次的那一条（`STREAM_BATCH_SUBMITTED`）在**最后单独一次**事务里写；
    #   - ⚠️ **批次审计写失败 ⇒ 绝不能回滚已提交的 stream**（那是 D2「部分成功」
    #     的成果）⇒ 记 ERROR 日志 + 回滚**这次**审计写入 ⇒ **仍然返回 207**
    #     ⇒ 响应里带 `warning` ⇒ 前端提示「已提交 N 条，但批次记录写入失败」。
    warning: str | None = None
    if not dry_run:
        try:
            await _write_batch_audit(
                db,
                batch_id=batch_id,
                total=len(unique_ids),
                succeeded=succeeded,
                failed=failed,
                actor_user_id=actor_user_id,
                actor_role=actor_role,
            )
        except Exception:  # noqa: BLE001 —— 审计写失败**不能**毁掉已提交的结果
            logger.exception("批量提交校对：批次审计写入失败（batch_id=%s）", batch_id)
            await db.rollback()  # 只回滚**这次**审计写入
            warning = (
                f"已提交 {len(succeeded)} 条，但批次记录写入失败，请联系管理员"
                f"（batch_id={batch_id}）"
            )

    return StreamBatchSubmitResponse(
        batch_id=batch_id,
        total=len(unique_ids),
        succeeded=succeeded,
        failed=failed,
        dry_run=dry_run,
        warning=warning,
    )
```

⚠️ `test_batch_limit_exceeded_raises` 用了 `limit=2` 覆盖 ⇒ `submit_batch`
必须带 `limit` 参数（上面已带）。

- [ ] **Step 5: 跑测试，确认通过**

```bash
cd pcs-backend && uv run pytest tests/services/test_stream_batch_service.py -q
```

Expected: PASS（6 条 T1 + 10 条 T2 = 16 passed）

⚠️ 若 `test_batch_partial_success_does_not_roll_back_the_good_ones` 红了
（成功项被回滚）⇒ 说明 `StreamService.transition` 的 rollback 波及了前面的
成功项 ⇒ 检查「每条之后有没有 commit」。

- [ ] **Step 6: 提交**

```bash
cd /home/pangzy/code_project/PCS && git add pcs-backend/app/services/stream_batch_service.py pcs-backend/app/schemas/stream_batch.py pcs-backend/tests/services/test_stream_batch_service.py
git commit -F /tmp/p9b3b-t2-msg.txt
```

（`/tmp/p9b3b-t2-msg.txt` 内容：

```
feat(P9B-3b): 批次 service —— D1~D6 全部语义（去重 / 幂等 / 部分成功 / 预演 / 上限）

T2：批次 service（`submit_batch`）+ 契约 schema（`StreamBatchSubmitResponse` 等）。

- **D1** 一次请求 N 条（前端不循环）。
- **D2** **逐条 commit** ⇒ 一条失败**不回滚**其它条（`StreamService.transition`
  失败时的 `db.rollback()` 回滚的是「当前事务」⇒ 整批一个事务会把前面成功的
  全回滚掉）。
- **D3** 审计 N+1：真正转移的每条 1 条 `RECORD_TRANSITION`（状态机写）+ 批次
  1 条 `STREAM_BATCH_SUBMITTED`。
- **D4** 上限取 `system_settings.stream.batch_submit_limit`（可配置，默认 100）。
- **D5** 批次内去重；已 `IN_APPROVAL` 记成功且 `note=already_in_approval`
  （不重复转移、不重复写审计）。
- **D6** `dry_run` 不改状态、**不写任何审计**，但仍返回每条预判结果。

⚠️ 单条端点语义**未改**（第二次单条提交仍是 422 INVALID_TRANSITION）。
```

）

---

## Task 3: T3 · HTTP 端点 + 契约（207 / ACL / 审计完整性 / 追溯链）

**Files:**
- Create: `pcs-backend/app/api/v1/stream_batch.py`
- Modify: `pcs-backend/app/api/v1/__init__.py`（挂 router）
- Modify: `pcs-backend/docs/openapi.json`（生成物）
- Create: `pcs-backend/tests/api/v1/test_stream_batch_submit.py`

**Interfaces:**
- Consumes: T2 的 `submit_batch` 与 `app.schemas.stream_batch.*`
- Produces: `POST /api/v1/streams/batch-submit` → **207** +
  `StreamBatchSubmitResponse`；错误码 `SIM_STREAM_BATCH_LIMIT_EXCEEDED`（422）

- [ ] **Step 1: 写失败测试**

创建 `pcs-backend/tests/api/v1/test_stream_batch_submit.py`：

```python
"""批量「提交校对」的 HTTP 面（P9B-3b · T3）。

守四件事：

1. **207 Multi-Status**：一条成功 + 一条失败 ⇒ 仍然 207（不是 200 也不是 500）；
2. **ACL**：非 `DESIGNER` / `PROCESS_CONTROLLOR` / `SYSTEM_ADMIN` ⇒ 整批 403
   （与单条端点同口径）；
3. **上限**：超过 `stream.batch_submit_limit` ⇒ 422 `SIM_STREAM_BATCH_LIMIT_EXCEEDED`；
4. **审计 N+1**：真正转移的每条 1 条 `RECORD_TRANSITION` + 批次 1 条
   `STREAM_BATCH_SUBMITTED`（幂等命中**不**写 `RECORD_TRANSITION`）。
"""

from __future__ import annotations

import uuid
from typing import Any

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token
from app.models.enums import StreamSignStatus
from app.models.project import Project, Stream, Workspace
from app.models.system import AuditLog

pytestmark = pytest.mark.asyncio

BATCH_URL = "/api/v1/streams/batch-submit"


@pytest.fixture
def designer_headers() -> dict[str, str]:
    token = create_access_token(subject="test-designer", role="DESIGNER")
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def viewer_headers() -> dict[str, str]:
    token = create_access_token(subject="test-viewer", role="VIEWER")
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def make_project(db: AsyncSession):
    ws = Workspace(workspace_type="FORMAL", name=f"ws-{uuid.uuid4().hex[:8]}")
    db.add(ws)
    await db.flush()
    proj = Project(
        project_no=f"P-{uuid.uuid4().hex[:8]}",
        project_name="批量提交测试",
        owner_company="测试业主",
        location="测试地点",
        project_type="CHEMICAL",
        design_phase="FEED",
        unit_system="SI",
        workspace_id=ws.workspace_id,
    )
    db.add(proj)
    await db.commit()
    return proj


async def _make_draft(db: AsyncSession, proj, name: str) -> Stream:
    stream = Stream(
        project_id=proj.project_id,
        workspace_id=proj.workspace_id,
        stream_name=name,
        case_type="NORMAL",
        data_mode="CHEMICAL",
        source_type="MANUAL_ENTRY",
        source="MANUAL",
        phase="LIQUID",
        temp=80.0,
        press=200.0,
        mass_flow=1000.0,
        composition_json={"7732-18-5": 1.0},
        sign_status=StreamSignStatus.DRAFT,
        # ⚠️ `approval_depth` 是 Stream 上**唯一没有默认值**的 NOT NULL 列
        #   ⇒ 取值与 `StreamService.create` 一致（1 步校对）。
        approval_depth=1,
    )
    db.add(stream)
    await db.commit()
    await db.refresh(stream)
    return stream


async def test_batch_submit_returns_207_with_both_lists(
    client, db_session, make_project, designer_headers
):
    """⚠️ 一条成功 + 一条失败 ⇒ **207**，两张清单各自完整。"""
    proj = make_project
    good = await _make_draft(db_session, proj, "GOOD")
    missing = uuid.uuid4()

    resp = await client.post(
        BATCH_URL,
        json={"stream_ids": [str(good.stream_id), str(missing)]},
        headers=designer_headers,
    )

    assert resp.status_code == 207, resp.text
    body = resp.json()
    assert body["total"] == 2
    assert [s["stream_id"] for s in body["succeeded"]] == [str(good.stream_id)]
    assert body["succeeded"][0]["from_status"] == "DRAFT"
    assert body["succeeded"][0]["to_status"] == "IN_APPROVAL"
    # ⚠️ `status` 是**判别字段**（前端与调用方都靠它分流 ⇒ 必须真的在契约里）
    assert body["succeeded"][0]["status"] == "succeeded"
    assert [f["stream_id"] for f in body["failed"]] == [str(missing)]
    assert body["failed"][0]["reason"] == "SIM_STREAM_NOT_FOUND"
    assert body["failed"][0]["status"] == "failed"
    assert body["dry_run"] is False


async def test_batch_submit_requires_allowed_role(
    client, db_session, make_project, viewer_headers
):
    """越权 ⇒ **整批 403**（与单条端点同口径）。"""
    proj = make_project
    stream = await _make_draft(db_session, proj, "S-1")

    resp = await client.post(
        BATCH_URL,
        json={"stream_ids": [str(stream.stream_id)]},
        headers=viewer_headers,
    )

    assert resp.status_code == 403, resp.text
    await db_session.refresh(stream)
    assert stream.sign_status.value == "DRAFT", "被拒的批次却改了状态"


async def test_batch_submit_rejects_empty_list(client, designer_headers):
    """空列表 ⇒ 422（请求体校验）。"""
    resp = await client.post(
        BATCH_URL, json={"stream_ids": []}, headers=designer_headers
    )
    assert resp.status_code == 422, resp.text


async def test_batch_submit_enforces_configured_limit(
    client, db_session, make_project, designer_headers
):
    """D4：把上限改成 1 ⇒ 提交 2 条 ⇒ 422 `SIM_STREAM_BATCH_LIMIT_EXCEEDED`。"""
    from app.services.system_setting_service import seed_defaults, update_batch

    proj = make_project
    s1 = await _make_draft(db_session, proj, "S-1")
    s2 = await _make_draft(db_session, proj, "S-2")

    await seed_defaults(db_session)
    await db_session.commit()
    await update_batch(
        db_session, {"stream.batch_submit_limit": 1}, actor_user_id=uuid.uuid4()
    )
    await db_session.commit()

    resp = await client.post(
        BATCH_URL,
        json={"stream_ids": [str(s1.stream_id), str(s2.stream_id)]},
        headers=designer_headers,
    )

    assert resp.status_code == 422, resp.text
    assert resp.json()["code"] == "SIM_STREAM_BATCH_LIMIT_EXCEEDED", resp.text
    await db_session.refresh(s1)
    await db_session.refresh(s2)
    assert s1.sign_status.value == "DRAFT", "超限的批次却执行了"
    assert s2.sign_status.value == "DRAFT"


async def test_batch_submit_writes_n_plus_one_audits(
    client, db_session, make_project, designer_headers
):
    """D3：审计 **N+1** 条（N 条 `RECORD_TRANSITION` + 1 条批次）。"""
    proj = make_project
    s1 = await _make_draft(db_session, proj, "S-1")
    s2 = await _make_draft(db_session, proj, "S-2")

    resp = await client.post(
        BATCH_URL,
        json={"stream_ids": [str(s1.stream_id), str(s2.stream_id)]},
        headers=designer_headers,
    )
    assert resp.status_code == 207, resp.text
    batch_id = resp.json()["batch_id"]

    transitions = (
        (
            await db_session.execute(
                select(AuditLog).where(AuditLog.action == "RECORD_TRANSITION")
            )
        )
        .scalars()
        .all()
    )
    assert len(transitions) == 2, f"应有 2 条单条审计，实际 {len(transitions)}"

    batch_rows = (
        (
            await db_session.execute(
                select(AuditLog).where(AuditLog.action == "STREAM_BATCH_SUBMITTED")
            )
        )
        .scalars()
        .all()
    )
    assert len(batch_rows) == 1, f"应有 1 条批次审计，实际 {len(batch_rows)}"
    assert batch_rows[0].resource_id == batch_id
    detail = batch_rows[0].detail_json or {}
    assert detail["total"] == 2
    assert len(detail["succeeded"]) == 2
    # ⚠️ **审计完整性**（委员会 2026-11-03 · D3 约束 2）：本端点**没有项目守卫**
    #    ⇒ 审计是唯一的事后追溯手段 ⇒ 这六个字段缺一不可（测试必须钉住）。
    assert detail["batch_id"] == batch_id
    assert detail["dry_run"] is False
    assert detail["requester_user_id"], "审计里没有操作人 ⇒ 事后追不到人"
    assert detail["requester_role"]
    assert sorted(detail["succeeded_ids"]) == sorted(
        [str(s1.stream_id), str(s2.stream_id)]
    )
    assert detail["failed_ids"] == []


async def test_batch_audit_resource_id_equals_response_batch_id(
    client, db_session, make_project, designer_headers
):
    """⚠️ **追溯链的完整性**：审计的 `resource_id` 必须**等于**响应的 `batch_id`。

    这是「跳过 D9（不改审计页）但保持追溯链可用」的最后一道保险 ——
    审计页靠 `resource_type=STREAM_BATCH` + `resource_id=<batch_id>` 查这一批
    ⇒ 两者若不等（一个用 `uuid4()` 一个用别的），**用户拿着响应里的 batch_id
    也查不到** ⇒ 「怎么查」写在 docstring 里也是空话。
    """
    proj = make_project
    s1 = await _make_draft(db_session, proj, "S-1")

    resp = await client.post(
        BATCH_URL,
        json={"stream_ids": [str(s1.stream_id)]},
        headers=designer_headers,
    )
    assert resp.status_code == 207, resp.text
    batch_id = resp.json()["batch_id"]

    rows = (
        (
            await db_session.execute(
                select(AuditLog)
                .where(AuditLog.action == "STREAM_BATCH_SUBMITTED")
                .where(AuditLog.resource_id == batch_id)
            )
        )
        .scalars()
        .all()
    )
    assert len(rows) == 1, (
        f"用响应里的 batch_id={batch_id} 查不到批次审计 ⇒ 追溯链断了"
    )
    assert rows[0].resource_type == "STREAM_BATCH"


async def test_idempotent_hit_writes_no_second_transition_audit(
    client, db_session, make_project, designer_headers
):
    """⚠️ Review Focus #2：已 `IN_APPROVAL` ⇒ 记成功但**不写** `RECORD_TRANSITION`。"""
    proj = make_project
    s1 = await _make_draft(db_session, proj, "S-1")
    s1.sign_status = StreamSignStatus.IN_APPROVAL
    await db_session.commit()

    resp = await client.post(
        BATCH_URL,
        json={"stream_ids": [str(s1.stream_id)]},
        headers=designer_headers,
    )

    assert resp.status_code == 207, resp.text
    body = resp.json()
    assert body["succeeded"][0]["note"] == "already_in_approval"

    transitions = (
        (
            await db_session.execute(
                select(AuditLog).where(AuditLog.action == "RECORD_TRANSITION")
            )
        )
        .scalars()
        .all()
    )
    assert len(transitions) == 0, "幂等命中却写了单条转移审计"


async def test_dry_run_writes_no_audit_at_all(
    client, db_session, make_project, designer_headers
):
    """⚠️ Review Focus #3：预演 ⇒ **审计表零新增**（连批次那条也没有）。"""
    proj = make_project
    s1 = await _make_draft(db_session, proj, "S-1")

    resp = await client.post(
        BATCH_URL,
        json={"stream_ids": [str(s1.stream_id)], "dry_run": True},
        headers=designer_headers,
    )

    assert resp.status_code == 207, resp.text
    assert resp.json()["dry_run"] is True
    rows = (await db_session.execute(select(AuditLog))).scalars().all()
    assert rows == [], f"预演写了 {len(rows)} 条审计"
    await db_session.refresh(s1)
    assert s1.sign_status.value == "DRAFT"
```

- [ ] **Step 2: 跑测试，确认失败**

```bash
cd pcs-backend && uv run pytest tests/api/v1/test_stream_batch_submit.py -q
```

Expected: FAIL —— 404（端点还不存在）

- [ ] **Step 3: 实现端点**

创建 `pcs-backend/app/api/v1/stream_batch.py`：

```python
"""批量「提交校对」的端点（P9B-3b）。

⚠️ **路径为什么是 `/streams/batch-submit`**（用户 2026-11-03 裁决）：本路径
**两段**，与三段的 `POST /streams/{stream_id}/submit` **不可能抢路由** ⇒
不需要任何路由顺序技巧。
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.config import _Actor, current_actor, require_roles
from app.db.session import get_db
from app.schemas.stream_batch import (
    StreamBatchSubmitRequest,
    StreamBatchSubmitResponse,
)
from app.services.stream_batch_service import submit_batch

router = APIRouter()


@router.post(
    "/streams/batch-submit",
    status_code=207,
    response_model=StreamBatchSubmitResponse,
    summary="批量提交校对（DRAFT → IN_APPROVAL，207 Multi-Status）",
    # ⚠️ **只登记描述、不登记 model**：仓里**没有**通用错误信封 schema
    #    （只有 `ConflictEnvelope`，是 409 专用的）⇒ 登记 model 要新造一个
    #    ⇒ 那是 TODO-096 的活。本端点先用 `description` 把错误码写清楚。
    responses={
        403: {"description": "角色无权（需 DESIGNER / PROCESS_CONTROLLER / SYSTEM_ADMIN）"},
        422: {"description": "超过批次上限 —— SIM_STREAM_BATCH_LIMIT_EXCEEDED"},
    },
)
async def batch_submit_streams(
    req: StreamBatchSubmitRequest,
    user: Annotated[_Actor, Depends(current_actor)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> StreamBatchSubmitResponse:
    """批量提交校对。

    ACL：DESIGNER / PROCESS_CONTROLLER / SYSTEM_ADMIN（与单条端点同口径）。

    ⚠️ **207 Multi-Status**：一条失败**不回滚**其它条 ⇒ 成功与失败**分两张清单**
    返回（`succeeded` / `failed`）。⚠️ 207 是 **2xx** ⇒ 客户端**不会**自动
    抛异常 ⇒ 必须自己看 `failed`。
    """
    require_roles(user, "DESIGNER", "PROCESS_CONTROLLOR", "SYSTEM_ADMIN")

    # ⚠️ service 抛的 `PcsError`（如超限 422）**不用**在这里转 —— 全局
    # handler（`app/core/errors.py::install_exception_handlers`）已经把它
    # 渲染成统一信封 `{code, message, detail, trace_id}` ⇒ 在这里 try/except
    # 再 raise 只是把同一个异常抛两遍。
    return await submit_batch(
        db,
        req.stream_ids,
        actor_user_id=user.user_id,
        actor_role=user.role,
        dry_run=req.dry_run,
    )
```

修改 `pcs-backend/app/api/v1/__init__.py`：

```python
from app.api.v1.stream_batch import router as stream_batch_router  # P9B-3b 批量提交校对
```

并在 `api_router.include_router(...)` 列表里（紧挨 `streams_router` 那一行）加：

```python
api_router.include_router(stream_batch_router)  # P9B-3b 批量提交校对
```

- [ ] **Step 4: 跑测试，确认通过**

```bash
cd pcs-backend && uv run pytest tests/api/v1/test_stream_batch_submit.py -q
```

Expected: PASS（7 passed）

⚠️ 若 `test_batch_submit_writes_n_plus_one_audits` 红的行数不是 2/1 ⇒ 检查
「真正转移的每条写 1 条 + 批次 1 条」。

- [ ] **Step 5: 重滚契约 + 跑裸载荷闸门**

```bash
cd pcs-backend && uv run python scripts/export_openapi.py
cd pcs-backend && uv run python scripts/check_openapi_payload_coverage.py
```

Expected: 裸字段数 **71**（**不涨**）

```bash
cd pcs-backend && uv run pytest tests/api/v1/test_stream_batch_submit.py tests/services/test_stream_batch_service.py -q
```

Expected: PASS（23 passed）

- [ ] **Step 6: 提交**

```bash
cd /home/pangzy/code_project/PCS && git add pcs-backend/app/api/v1/stream_batch.py pcs-backend/app/api/v1/__init__.py pcs-backend/docs/openapi.json pcs-backend/tests/api/v1/test_stream_batch_submit.py
git commit -F /tmp/p9b3b-t3-msg.txt
```

（`/tmp/p9b3b-t3-msg.txt` 内容：

```
feat(P9B-3b): 批量提交校对端点 —— POST /streams/batch-submit（207 Multi-Status）

T3：端点 + 契约重滚 + 裸载荷闸门。

- 路径 **两段**（`/streams/batch-submit`）⇒ 与三段的 `/streams/{id}/submit`
  **不可能抢路由**（全仓只有 streams.py 一个 router，且它没有两段的 POST）。
- **207 Multi-Status**：成功与失败分两张清单 ⇒ 一条失败不回滚其它条。
- ACL 与单条端点同口径（DESIGNER / PROCESS_CONTROLLER / SYSTEM_ADMIN）。
- 上限 422 `SIM_STREAM_BATCH_LIMIT_EXCEEDED`（取系统参数）。
- 契约**具名 schema** ⇒ 裸载荷数仍是 **71**（未涨）。
```

）

---

## Task 4: T4 · 行锁与并发（方言级 + `populate_existing` + 接线 + PG 车道真并发）

**Files:**
- Create: `pcs-backend/tests/api/v1/test_stream_batch_concurrency_pg.py`
- Modify: `pcs-backend/tests/services/test_stream_batch_service.py`（加方言级 + 接线断言）

**Interfaces:**
- Consumes: T1 的 `select_stream_for_update` / `build_stream_for_update_stmt` + T2 的 `submit_batch`
- Produces: 无新代码（**纯测试**）；若 T4 暴露 bug ⇒ 修在 T2/T3 的文件里

- [ ] **Step 1: 写方言级 + 接线断言（普通单测，跑得快）**

在 `pcs-backend/tests/services/test_stream_batch_service.py` 追加：

```python
# ---------------------------------------------------------------------------
# T4：行锁（方言级 + 接线）
# ---------------------------------------------------------------------------


async def test_locked_select_emits_for_update_on_postgres():
    """方言级断言：加锁那条 SELECT 在 **PG 方言**下真的带 `FOR UPDATE`。

    ## 为什么是方言级而不是「真跑 PG 并发」

    - in-memory SQLite 把 `with_for_update()` **编译成空串**（压根没有锁），
      且 StaticPool 共享连接 ⇒ 真并发在本仓单测 fixture 上**不可表达**；
    - 真 PG 双连接并发 ⇒ `scripts/pytest_pg.sh` 车道（见同目录的
      `test_stream_batch_concurrency_pg.py`）。

    ⇒ 这里钉**机制**（SQL 形状），下面两条钉「接线」与「C-1 的修复点」。
    """
    from sqlalchemy.dialects import postgresql

    from app.services.stream_service import build_stream_for_update_stmt

    stmt = build_stream_for_update_stmt(uuid.uuid4())
    sql = str(stmt.compile(dialect=postgresql.dialect()))
    assert "FOR UPDATE" in sql, sql


async def test_locked_select_sets_populate_existing(
    db_session, batch_project, monkeypatch
):
    """⚠️ **C-1 的修复点必须有断言钉住**（委员会 2026-11-03 · D4 裁决）。

    **为什么这条比「抽 helper」本身更重要**：SQLite 把 `FOR UPDATE` 编译掉
    ⇒ 删掉 `populate_existing=True` 后测试**仍然绿**（行为看着正常）⇒
    回归会以另一种形式回来（并发时两个提交都基于旧状态通过 ⇒ 行锁形同虚设）。

    ⇒ 这里断言**生产路径实际执行的那条语句**带 `populate_existing=True`
    （spy 抓的是 `build_stream_for_update_stmt` 的返回值 ⇒ 抓的是真语句，
    不是测试自己重抄的一份）。
    """
    from app.services import stream_service

    seen: list[Any] = []
    original = stream_service.build_stream_for_update_stmt

    def spy(stream_id):
        stmt = original(stream_id)
        seen.append(stmt)
        return stmt

    monkeypatch.setattr(stream_service, "build_stream_for_update_stmt", spy)

    s = await _make_draft(db_session, batch_project, "S-1")
    await stream_service.select_stream_for_update(db_session, s.stream_id)

    assert seen, "根本没走加锁读"
    for stmt in seen:
        assert stmt.get_execution_options().get("populate_existing") is True, (
            "加锁读**没有** populate_existing ⇒ C-1 的修复被删了 ⇒ "
            "并发时两个提交都会基于旧状态通过（行锁形同虚设）"
        )


async def test_batch_submit_uses_the_locked_select(
    db_session, batch_project, monkeypatch
):
    """接线断言：**批次**真的请求了**加锁读**（而不是随便一条 SELECT）。

    ⚠️ 批次路径会加锁读**两次**（批次的预检 + `StreamService.transition`
    内部的转移）⇒ 断言「至少一次、且每一条都带 populate_existing」。
    """
    from app.services import stream_service
    from app.services.stream_batch_service import submit_batch

    seen: list[Any] = []
    original = stream_service.build_stream_for_update_stmt

    def spy(stream_id):
        stmt = original(stream_id)
        seen.append(stmt)
        return stmt

    monkeypatch.setattr(stream_service, "build_stream_for_update_stmt", spy)

    s = await _make_draft(db_session, batch_project, "S-1")
    await submit_batch(
        db_session,
        [s.stream_id],
        actor_user_id=uuid.uuid4(),
        actor_role="DESIGNER",
    )

    assert seen, "批次没走加锁读"
    for stmt in seen:
        assert stmt.get_execution_options().get("populate_existing") is True
```

- [ ] **Step 2: 跑测试，确认它们能失败（变异实测）**

```bash
cd pcs-backend && uv run pytest tests/services/test_stream_batch_service.py -q
```

Expected: PASS（此时实现已存在）

⇒ **变异实测**（必做，证明断言有效）：临时把
`app/services/stream_service.py` 里 `build_stream_for_update_stmt` 的
`.with_for_update()` 删掉，重跑上面三条 ⇒ **方言级那条必须红**；
再把 `.execution_options(populate_existing=True)` 删掉，重跑 ⇒
**`populate_existing` 那条必须红**（⚠️ SQLite 把 `FOR UPDATE` 编译掉 ⇒
这条是 C-1 修复的**唯一**自动闸门）；把批次 service 里的
`select_stream_for_update(db, stream_id)` 换成裸 `select(...)` ⇒
**接线那条必须红**。验证完**改回来**
（`git checkout -- pcs-backend/app/services/stream_service.py pcs-backend/app/services/stream_batch_service.py`）。

- [ ] **Step 3: 写 PG 车道真并发用例**

创建 `pcs-backend/tests/api/v1/test_stream_batch_concurrency_pg.py`：

```python
"""批量/单条「提交校对」的**真并发**（PG 车道 · P9B-3b · T4）。

## 为什么必须真 PG

SQLite 把 `SELECT ... FOR UPDATE` 编译成空串 ⇒ 单测里的「并发」只是
**顺序执行** ⇒ 证明不了行锁。⇒ 真并发必须在 PG 上用**两个连接**跑。

⚠️ `pg` marker 的用例平时被 `pytest.skip` 静默跳过 ⇒ 绿灯**证明不了**
它们跑过 ⇒ **必须**经 `scripts/pytest_pg.sh`（唯一入口）跑。

## 隔离 schema（不碰开发库）

沿用 `tests/alembic/test_p9_013_bind_default_record_matrix.py` 的做法：
建一个隔离 schema ⇒ 在它上面 `alembic upgrade head` ⇒ 用
`options=-csearch_path=<schema>` 让应用连到它 ⇒ 测完 `DROP SCHEMA ... CASCADE`
⇒ 开发库一个字节都不动。

⚠️ **口令不上命令行** ⇒ URL 只在**进程内**派生（`DATABASE_URL` 环境变量
传给子进程，不出现在 argv 里）。
"""

from __future__ import annotations

import os
import subprocess
import sys
import uuid
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def _pg_url() -> str | None:
    """PostgreSQL URL：`DATABASE_URL` 环境变量优先，否则 `.env`。"""
    url = os.environ.get("DATABASE_URL")
    if not url:
        env_file = ROOT / ".env"
        if env_file.exists():
            from dotenv import dotenv_values

            url = dotenv_values(env_file).get("DATABASE_URL")
    return url if url and url.startswith("postgres") else None


@pytest.mark.pg
def test_concurrent_submit_same_stream_one_wins_one_rejected():
    """⚠️ **最关键的测试**：并发提交同一条 stream ⇒ **一胜一拒**（行锁真的生效）。

    - 单条端点：两个并发 `submit_batch` 之外的 `StreamService.transition`
      ⇒ 一个成功（DRAFT → IN_APPROVAL），另一个 **422
      `SIM_STREAM_INVALID_TRANSITION`**（它拿到锁时状态已是 IN_APPROVAL）；
    - 批量端点：因 D5 幂等 ⇒ 两个都返回成功，但**只有一条真正转移**
      （`RECORD_TRANSITION` 审计**恰好 1 条**）。

    ⇒ 「行锁被绕过」的两种表现（两次都转移 / 审计两条）都会让本用例红。
    """
    url = _pg_url()
    if url is None:
        pytest.skip(
            "无 PostgreSQL URL —— 引擎级验证须经 scripts/pytest_pg.sh 跑（唯一入口）"
        )

    schema = f"iso_batch_{uuid.uuid4().hex[:8]}"
    # ⚠️ 隔离 schema 的 URL = 原 URL **追加** `options=-csearch_path=<schema>`
    #    （`?` 还是 `&` 看原 URL 有没有 query）。
    #    ⚠️ `alembic/env.py` 用 `settings.database_url`（pydantic-settings：
    #    **环境变量优先于 .env**）⇒ 把 scoped URL 放进子进程的 `DATABASE_URL`
    #    就能让 alembic 建表到隔离 schema ⇒ 开发库 public schema 一个字节不动。
    scoped_url = url + ("&" if "?" in url else "?") + f"options=-csearch_path={schema}"
    script = r'''
import asyncio, os, uuid
# ⚠️ `DATABASE_URL` 已由父进程派生成「指向隔离 schema」的版本 ⇒ 直接用。

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.errors import PcsError
from app.models.enums import StateTransition
from app.models.project import Project, Stream, Workspace
from app.services.stream_batch_service import submit_batch
from app.services.stream_service import StreamService


async def main():
    engine = create_async_engine(os.environ["DATABASE_URL"])
    maker = async_sessionmaker(engine, expire_on_commit=False)

    async with maker() as db:
        ws = Workspace(workspace_type="FORMAL", name="ws-conc")
        db.add(ws)
        await db.flush()
        proj = Project(
            project_no="P-CONC",
            project_name="并发测试",
            owner_company="业主",
            location="地点",
            project_type="CHEMICAL",
            design_phase="FEED",
            unit_system="SI",
            workspace_id=ws.workspace_id,
        )
        db.add(proj)
        await db.flush()
        stream = Stream(
            project_id=proj.project_id,
            workspace_id=ws.workspace_id,
            stream_name="S-CONC",
            case_type="NORMAL",
            data_mode="CHEMICAL",
            source_type="MANUAL_ENTRY",
            source="MANUAL",
            phase="LIQUID",
            temp=80.0,
            press=200.0,
            mass_flow=1000.0,
            composition_json={"7732-18-5": 1.0},
            sign_status="DRAFT",
        )
        db.add(stream)
        await db.commit()
        sid = stream.stream_id

    # ---- ① 单条：并发两次 ⇒ 一胜一拒 -------------------------------
    async def submit_once():
        async with maker() as s:
            try:
                await StreamService.transition(
                    s, sid,
                    transition=StateTransition.SUBMIT_FOR_CHECK,
                    actor_user_id=uuid.uuid4(),
                    actor_role="DESIGNER",
                )
                return "ok"
            except PcsError as e:
                return e.code

    results = await asyncio.gather(submit_once(), submit_once())
    assert sorted(results) == ["SIM_STREAM_INVALID_TRANSITION", "ok"], results

    # ---- ② 批量：并发两次 ⇒ 都成功，但只有一条真正转移 ---------------
    async with maker() as s:
        await s.execute(
            Stream.__table__.update()
            .where(Stream.stream_id == sid)
            .values(sign_status="DRAFT")
        )
        await s.commit()

    from sqlalchemy import func, select
    from app.models.system import AuditLog

    async def transition_audit_count():
        async with maker() as s:
            return (
                await s.execute(
                    select(func.count())
                    .select_from(AuditLog)
                    .where(AuditLog.action == "RECORD_TRANSITION")
                    .where(AuditLog.resource_id == str(sid))
                )
            ).scalar_one()

    # ⚠️ 取**增量**：① 已经写过 1 条 ⇒ 绝对值不是 1
    before = await transition_audit_count()

    async def batch_once():
        async with maker() as s:
            res = await submit_batch(
                s, [sid],
                actor_user_id=uuid.uuid4(),
                actor_role="DESIGNER",
            )
            return res

    r1, r2 = await asyncio.gather(batch_once(), batch_once())
    notes = [item.note for res in (r1, r2) for item in res.succeeded]
    assert "already_in_approval" in notes, (
        f"并发批次里没有幂等命中：{r1} / {r2}"
    )

    after = await transition_audit_count()
    assert after - before == 1, (
        f"并发批次写了 {after - before} 条单条转移审计（应恰好 1 条）⇒ 行锁被绕过"
    )

    await engine.dispose()
    print("P9B3B_CONCURRENCY_OK")


asyncio.run(main())
'''

    try:
        created = subprocess.run(
            [
                sys.executable,
                "-c",
                """
import asyncio, os
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
async def main():
    engine = create_async_engine(os.environ["BASE_PG_URL"])
    async with engine.begin() as conn:
        await conn.execute(text("CREATE SCHEMA " + os.environ["ISO_SCHEMA"]))
    await engine.dispose()
asyncio.run(main())
""",
            ],
            env={**os.environ, "BASE_PG_URL": url, "ISO_SCHEMA": schema},
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=300,
        )
        assert created.returncode == 0, f"CREATE SCHEMA 失败:\n{created.stderr}"

        upgraded = subprocess.run(
            [
                sys.executable,
                "-c",
                """
import os
from alembic import command
from alembic.config import Config
cfg = Config("alembic.ini")
command.upgrade(cfg, "head")
print("UPGRADE_OK")
""",
            ],
            # ⚠️ **scoped_url** ⇒ 表建在隔离 schema 里（pydantic-settings：
            #    环境变量优先于 .env ⇒ `settings.database_url` 就是 scoped URL）
            env={**os.environ, "DATABASE_URL": scoped_url},
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=900,
        )
        assert upgraded.returncode == 0, f"alembic upgrade 失败:\n{upgraded.stderr}"
        assert "UPGRADE_OK" in upgraded.stdout, upgraded.stdout

        result = subprocess.run(
            [sys.executable, "-c", script],
            env={**os.environ, "DATABASE_URL": scoped_url},
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=600,
        )
        assert result.returncode == 0, (
            f"并发脚本失败:\n{result.stdout}\n{result.stderr}"
        )
        assert "P9B3B_CONCURRENCY_OK" in result.stdout, result.stdout
    finally:
        cleanup = subprocess.run(
            [
                sys.executable,
                "-c",
                """
import asyncio, os
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
async def main():
    engine = create_async_engine(os.environ["BASE_PG_URL"])
    async with engine.begin() as conn:
        await conn.execute(text("DROP SCHEMA IF EXISTS " + os.environ["ISO_SCHEMA"] + " CASCADE"))
    await engine.dispose()
asyncio.run(main())
""",
            ],
            env={**os.environ, "BASE_PG_URL": url, "ISO_SCHEMA": schema},
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=120,
        )
        assert cleanup is not None and cleanup.returncode == 0, (
            f"DROP SCHEMA {schema} 失败（隔离 schema 可能残留在库里）:\n"
            f"{cleanup.stdout}\n{cleanup.stderr}"
        )
```

- [ ] **Step 4: 跑 PG 车道（唯一入口）**

```bash
cd pcs-backend && bash scripts/pytest_pg.sh
```

Expected: `1 passed`（或更多）且 **exit 0**

⚠️ 若报「收集到 0 个 PG 测试」⇒ marker 没生效 ⇒ 检查 `pyproject.toml` 的
`pg` marker 注册；若报「PG 测试实例未起」⇒ 先
`docker compose --profile pg up -d`（仓库根目录）。

- [ ] **Step 5: 跑全量后端测试（确认没打破别的）**

```bash
cd pcs-backend && uv run pytest -q
```

Expected: 全绿（基线 5439 + 本批新增用例数）

- [ ] **Step 6: 提交**

```bash
cd /home/pangzy/code_project/PCS && git add pcs-backend/tests/services/test_stream_batch_service.py pcs-backend/tests/api/v1/test_stream_batch_concurrency_pg.py
git commit -F /tmp/p9b3b-t4-msg.txt
```

（`/tmp/p9b3b-t4-msg.txt` 内容：

```
test(P9B-3b): 行锁断言 —— 方言级 + 接线 + PG 车道真并发

T4：⚠️ **最关键的测试**（与 P9B-2 报告 #1 同形）。

- **方言级**：`build_stream_for_update_stmt` 用 PG 方言编译后 SQL 里必须含
  `FOR UPDATE`（删掉 `.with_for_update()` ⇒ 必红）。
- **`populate_existing`**：生产路径实际执行的那条语句必须带
  `populate_existing=True`（⚠️ 这是 **C-1 的修复点** ⇒ SQLite 把 `FOR UPDATE`
  编译掉 ⇒ 只有这条断言抓得住）。
- **接线**：批次真的走了加锁读（spy `build_stream_for_update_stmt` ⇒ 删掉加锁必红）。
- **PG 车道真并发**（`scripts/pytest_pg.sh`，唯一入口）：隔离 schema 上
  ①单条并发 ⇒ **一胜一拒**（一 200、一条 422 INVALID_TRANSITION）；
  ②批量并发 ⇒ 因 D5 幂等都返回成功，但 `RECORD_TRANSITION` 审计**恰好 1 条**
  ⇒「行锁被绕过」（两次都转移）必红。

⚠️ 隔离 schema + 进程内派生 URL ⇒ 口令不上命令行、开发库零改动。
```

）

---

## Task 5: T5 · 前端（多选 + 工具栏按钮 + 结果弹窗 + mock）

**Files:**
- Modify: `pcs-frontend/src/api/stream.ts`
- Modify: `pcs-frontend/src/pages/sim/StreamListPage.tsx`
- Modify: `pcs-frontend/src/mocks/handlers.ts`
- Modify: `pcs-frontend/src/types/api.d.ts`（生成物）
- Modify: `pcs-frontend/tests/pages/sim/StreamListPage.test.tsx`

**Interfaces:**
- Consumes: T3 的契约（`StreamBatchSubmitResponse` / `BatchSucceededItem` / `BatchFailedItem`）
- Produces: `streamApi.batchSubmitForReview(streamIds: string[], dryRun?: boolean): Promise<StreamBatchSubmitResponse>`

- [ ] **Step 1: 重滚前端契约类型（T3 的后端契约已就位）**

```bash
cd /home/pangzy/code_project/PCS && bash pcs-frontend/scripts/gen-api-types.sh
```

Expected: `src/types/api.d.ts` 里出现 `StreamBatchSubmitResponse` / `BatchSucceededItem` / `BatchFailedItem`

⚠️ 若脚本要求后端 `openapi.json` 是最新的 ⇒ 先在仓库根跑
`bash scripts/gate_08_openapi_contract.sh`（阶段 1~3）。

- [ ] **Step 2: 写失败测试**

修改 `pcs-frontend/tests/pages/sim/StreamListPage.test.tsx`：

① 顶部 docstring 的第 1 条改为：

```
 * 1. 工具栏有 **导入 / 新建物流 / 导出 / 批量提交校对**（P9B-3b 已落地）
```

② 在 mock server 里加批量端点（在 `http.post('/api/v1/streams/:stream_id/submit', ...)` 之后）：

⚠️ **不要**写 `isAuthed(request)` —— 那个 helper 只存在于 `src/mocks/handlers.ts`，
本测试文件里没有 ⇒ 会编译不过 ⇒ 这里直接放行。

```tsx
  http.post('/api/v1/streams/batch-submit', async ({ request }) => {
    const body = (await request.json()) as {
      stream_ids: string[];
      dry_run?: boolean;
    };
    batchRequests.push({ ids: body.stream_ids, dryRun: body.dry_run === true });
    if (batchStatus !== 207) {
      return HttpResponse.json(
        {
          code: 'SIM_STREAM_BATCH_LIMIT_EXCEEDED',
          message: '批量提交 150 条，超过上限 100 条',
          detail: null,
          trace_id: 't-batch',
        },
        { status: batchStatus },
      );
    }
    const succeeded = body.stream_ids.map((id) => ({
      status: 'succeeded',
      stream_id: id,
      from_status: 'DRAFT',
      to_status: 'IN_APPROVAL',
      note: null,
    }));
    // ⚠️ mock 要**改内存态**（模拟后端把 DRAFT 推进 IN_APPROVAL）⇒
    //    否则「成功后列表刷新」那条测试验不到真东西。
    rows = rows.map((r) =>
      body.stream_ids.includes(r.stream_id)
        ? { ...r, sign_status: 'IN_APPROVAL' }
        : r,
    );
    return HttpResponse.json(
      {
        batch_id: 'b-1',
        total: succeeded.length,
        succeeded,
        failed: [],
        dry_run: body.dry_run === true,
        warning: null,
      },
      { status: 207 },
    );
  }),
```

③ 在状态变量区加：

```tsx
/** 批量提交的请求记录（断言 body）。 */
let batchRequests: { ids: string[]; dryRun: boolean }[] = [];
/** 批量端点的 HTTP 状态（207 = 正常；422 = 超限）。 */
let batchStatus = 207;
```

④ 在 `beforeEach` 里重置：

```tsx
    batchRequests = [];
    batchStatus = 207;
    // ⚠️ 必须 resetHandlers() —— 下面「部分失败」那条用 server.use() 临时
    //    覆盖了批量端点 ⇒ 不重置的话它会**泄漏**到后面的用例
    //    （下一条要测 422，不重置就会拿到 207 ⇒ 假红）。
    server.resetHandlers();
```

⑤ 把旧用例「工具栏有 导入 / 新建物流 / 导出，**没有**「批量提交校对」」改成：

```tsx
  it('工具栏有 导入 / 新建物流 / 导出 / **批量提交校对**', async () => {
    renderPage();
    await waitFor(() => expect(screen.getByTestId('stream-import')).toBeTruthy());

    expect(btnText('stream-import')).toBe('导入');
    expect(btnText('stream-create')).toBe('新建物流');
    expect(btnText('stream-export')).toBe('导出');
    // ✅ P9B-3b：批量提交校对**已实现**（SPEC §7.7.1 ⏳ → ✅）
    expect(btnText('stream-batch-submit')).toBe('批量提交校对');
  });
```

⑥ 文件末尾追加新用例：

```tsx
  it('⚠️ 没选中行 ⇒ 「批量提交校对」**禁用**', async () => {
    renderPage();
    await waitFor(() => expect(screen.getByTestId('stream-row')).toBeTruthy());

    expect(screen.getByTestId('stream-batch-submit')).toBeDisabled();
  });

  it('⚠️ 选中行 ⇒ 点「批量提交校对」⇒ POST 选中的 id 列表', async () => {
    rows = [makeStream(), makeStream({ stream_id: 's-2', stream_name: '塔顶气' })];
    renderPage();
    await waitFor(() => expect(screen.getAllByTestId('stream-row').length).toBe(2));

    // ⚠️ antd 的行选择框在表格的选择列里（`.ant-table-selection-column`）
    const headerCheckbox = document.querySelector(
      '.ant-table-selection-column .ant-checkbox-input',
    ) as HTMLInputElement;
    fireEvent.click(headerCheckbox);

    await waitFor(() =>
      expect(screen.getByTestId('stream-batch-submit')).not.toBeDisabled(),
    );
    fireEvent.click(screen.getByTestId('stream-batch-submit'));

    await waitFor(() => expect(batchRequests.length).toBe(1));
    expect(batchRequests[0].ids.sort()).toEqual(['s-1', 's-2']);
    expect(batchRequests[0].dryRun).toBe(false);
  });

  it('⚠️ 批量结果 ⇒ 弹窗显示「成功 N · 失败 M」', async () => {
    renderPage();
    await waitFor(() => expect(screen.getByTestId('stream-row')).toBeTruthy());

    const headerCheckbox = document.querySelector(
      '.ant-table-selection-column .ant-checkbox-input',
    ) as HTMLInputElement;
    fireEvent.click(headerCheckbox);
    await waitFor(() =>
      expect(screen.getByTestId('stream-batch-submit')).not.toBeDisabled(),
    );
    fireEvent.click(screen.getByTestId('stream-batch-submit'));

    await waitFor(() => expect(screen.getByTestId('stream-batch-summary')).toBeTruthy());
    expect(screen.getByTestId('stream-batch-summary').textContent).toContain('成功 1');
    expect(screen.getByTestId('stream-batch-summary').textContent).toContain('失败 0');
  });

  it('⚠️ 批量部分失败 ⇒ 摘要显示失败数 + 每条原因', async () => {
    // ⚠️ 207 是 2xx ⇒ axios **不抛异常** ⇒ 前端必须自己看 `failed`
    server.use(
      http.post('/api/v1/streams/batch-submit', async ({ request }) => {
        const body = (await request.json()) as { stream_ids: string[] };
        return HttpResponse.json(
          {
            batch_id: 'b-2',
            total: body.stream_ids.length,
            succeeded: [
              {
                status: 'succeeded',
                stream_id: body.stream_ids[0],
                from_status: 'DRAFT',
                to_status: 'IN_APPROVAL',
                note: null,
              },
            ],
            failed: [
              {
                status: 'failed',
                stream_id: body.stream_ids[1] ?? 's-2',
                reason: 'SIM_STREAM_COMPOSITION_OUT_OF_RANGE',
                detail: '组成摩尔分率合计 98.70%，不在 100±0.5% 内',
              },
            ],
            dry_run: false,
            warning: null,
          },
          { status: 207 },
        );
      }),
    );
    rows = [makeStream(), makeStream({ stream_id: 's-2', stream_name: '塔顶气' })];
    renderPage();
    await waitFor(() => expect(screen.getAllByTestId('stream-row').length).toBe(2));

    const headerCheckbox = document.querySelector(
      '.ant-table-selection-column .ant-checkbox-input',
    ) as HTMLInputElement;
    fireEvent.click(headerCheckbox);
    await waitFor(() =>
      expect(screen.getByTestId('stream-batch-submit')).not.toBeDisabled(),
    );
    fireEvent.click(screen.getByTestId('stream-batch-submit'));

    await waitFor(() => expect(screen.getByTestId('stream-batch-summary')).toBeTruthy());
    const summary = screen.getByTestId('stream-batch-summary').textContent ?? '';
    expect(summary).toContain('成功 1');
    expect(summary).toContain('失败 1');
    // ⚠️ 每条失败**带原因**（用户要知道为什么失败）
    const failures = screen.getByTestId('stream-batch-failures').textContent ?? '';
    expect(failures).toContain('SIM_STREAM_COMPOSITION_OUT_OF_RANGE');
    // ⚠️ **关闭提示**（D8 裁决的「本批必做」）：失败清单关闭即丢 ⇒ 必须告知用户
    expect(screen.getByTestId('stream-batch-close-hint').textContent).toContain(
      '关闭后失败清单将不再显示',
    );
  });

  it('⚠️ 批量请求本身失败（422 超限）⇒ 显示错误，**不**显示结果摘要', async () => {
    batchStatus = 422;
    renderPage();
    await waitFor(() => expect(screen.getByTestId('stream-row')).toBeTruthy());

    const headerCheckbox = document.querySelector(
      '.ant-table-selection-column .ant-checkbox-input',
    ) as HTMLInputElement;
    fireEvent.click(headerCheckbox);
    await waitFor(() =>
      expect(screen.getByTestId('stream-batch-submit')).not.toBeDisabled(),
    );
    fireEvent.click(screen.getByTestId('stream-batch-submit'));

    await waitFor(() => expect(screen.getByTestId('stream-batch-error')).toBeTruthy());
    expect(screen.getByTestId('stream-batch-error').textContent).toContain('上限');
    expect(screen.queryByTestId('stream-batch-summary')).toBeNull();
    // ⚠️ 请求失败 ⇒ **状态不变**（后端没执行）
    expect(screen.getByTestId('stream-row').getAttribute('data-status')).toBe('DRAFT');
  });

  it('⚠️ 批量成功后 ⇒ **列表刷新**（那一行的徽章变 IN_APPROVAL）', async () => {
    renderPage();
    await waitFor(() => expect(screen.getByTestId('stream-row')).toBeTruthy());

    const headerCheckbox = document.querySelector(
      '.ant-table-selection-column .ant-checkbox-input',
    ) as HTMLInputElement;
    fireEvent.click(headerCheckbox);
    await waitFor(() =>
      expect(screen.getByTestId('stream-batch-submit')).not.toBeDisabled(),
    );
    fireEvent.click(screen.getByTestId('stream-batch-submit'));

    // ⚠️ 后端返回的**最新态**才是真相 ⇒ 前端必须重新拉列表
    await waitFor(() =>
      expect(screen.getByTestId('stream-row').getAttribute('data-status')).toBe(
        'IN_APPROVAL',
      ),
    );
    expect(screen.getByTestId('state-badge-label').textContent).toBe('审批中');
  });

  it('⚠️ 连点两次「批量提交校对」⇒ **只发一次请求**', async () => {
    renderPage();
    await waitFor(() => expect(screen.getByTestId('stream-row')).toBeTruthy());

    const headerCheckbox = document.querySelector(
      '.ant-table-selection-column .ant-checkbox-input',
    ) as HTMLInputElement;
    fireEvent.click(headerCheckbox);
    await waitFor(() =>
      expect(screen.getByTestId('stream-batch-submit')).not.toBeDisabled(),
    );

    const btn = screen.getByTestId('stream-batch-submit');
    fireEvent.click(btn);
    fireEvent.click(btn); // ⚠️ 连点

    await waitFor(() => expect(batchRequests.length).toBeGreaterThan(0));
    // ⚠️ 提交进行中按钮**禁用** ⇒ 第二次点击不该再发一次
    expect(batchRequests.length).toBe(1);
  });

  it('⚠️ 批次级 `warning`（如批次记录写失败）⇒ 摘要里**如实显示**', async () => {
    server.use(
      http.post('/api/v1/streams/batch-submit', async ({ request }) => {
        const body = (await request.json()) as { stream_ids: string[] };
        return HttpResponse.json(
          {
            batch_id: 'b-3',
            total: body.stream_ids.length,
            succeeded: [
              {
                status: 'succeeded',
                stream_id: body.stream_ids[0],
                from_status: 'DRAFT',
                to_status: 'IN_APPROVAL',
                note: null,
              },
            ],
            failed: [],
            dry_run: false,
            // ⚠️ 批次审计写失败 ⇒ 条目**已提交**，但批次记录没写成
            warning: '已提交 1 条，但批次记录写入失败，请联系管理员',
          },
          { status: 207 },
        );
      }),
    );
    renderPage();
    await waitFor(() => expect(screen.getByTestId('stream-row')).toBeTruthy());

    const headerCheckbox = document.querySelector(
      '.ant-table-selection-column .ant-checkbox-input',
    ) as HTMLInputElement;
    fireEvent.click(headerCheckbox);
    await waitFor(() =>
      expect(screen.getByTestId('stream-batch-submit')).not.toBeDisabled(),
    );
    fireEvent.click(screen.getByTestId('stream-batch-submit'));

    await waitFor(() => expect(screen.getByTestId('stream-batch-warning')).toBeTruthy());
    expect(screen.getByTestId('stream-batch-warning').textContent).toContain(
      '批次记录写入失败',
    );
  });
```

- [ ] **Step 3: 跑测试，确认失败**

```bash
cd pcs-frontend && npx vitest run tests/pages/sim/StreamListPage.test.tsx
```

Expected: FAIL —— 找不到 `stream-batch-submit` / `stream-batch-summary` / `stream-batch-error`

- [ ] **Step 4: 实现 api 客户端**

修改 `pcs-frontend/src/api/stream.ts` —— 在类型区加：

```ts
/** 批量提交校对的响应（**契约派生** · P9B-3b）。 */
export type StreamBatchSubmitResponse = components['schemas']['StreamBatchSubmitResponse'];
/** 批量里成功的一条（契约派生）。 */
export type StreamBatchSucceeded = components['schemas']['BatchSucceededItem'];
/** 批量里失败的一条（契约派生）。 */
export type StreamBatchFailed = components['schemas']['BatchFailedItem'];
```

在 `streamApi` 对象里加：

```ts
  /**
   * 批量**提交校对**（`POST /streams/batch-submit` · 207 Multi-Status）。
   *
   * ⚠️ **207 是 2xx ⇒ axios 不抛异常** ⇒ 部分失败**不会**进 catch ⇒
   * 调用方**必须自己看** `failed` 数组（`failed.length > 0` ⇒ 有条没成）。
   * ⚠️ 与行操作那条「校对」（`submitForReview`，单条）**不是同一件事**。
   */
  batchSubmitForReview: (
    streamIds: string[],
    dryRun = false,
  ): Promise<StreamBatchSubmitResponse> =>
    api
      .post<StreamBatchSubmitResponse>('/streams/batch-submit', {
        stream_ids: streamIds,
        dry_run: dryRun,
      })
      .then((r) => r.data),
```

- [ ] **Step 5: 实现列表页**

修改 `pcs-frontend/src/pages/sim/StreamListPage.tsx`：

① import 追加：

```tsx
import { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Alert, Button, Modal, Select, Space, Table, Tag, Typography } from 'antd';
```

（`Modal` 是新增的；`Typography` / `Tag` / `Space` 保持原样。）

② import 类型追加：

```tsx
import { streamApi, type StreamBatchSubmitResponse, type StreamListFilters } from '../../api/stream';
```

③ 状态区追加：

```tsx
  /** 行多选（批量提交校对的输入）。 */
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  /** 批量提交的结果摘要（成功 N / 失败 M）。 */
  const [batchResult, setBatchResult] = useState<StreamBatchSubmitResponse | null>(null);
  /** 批量提交**本身**失败（网络/超限/403）⇒ 顶部错误条。 */
  const [batchError, setBatchError] = useState<string | null>(null);
  /** 批量提交进行中（禁用按钮，防重复提交）。 */
  const [batchSubmitting, setBatchSubmitting] = useState(false);
```

④ 工具栏里（`stream-export` 那个 Button 之后）加按钮：

```tsx
        <Button
          data-testid="stream-batch-submit"
          onClick={submitBatch}
          disabled={selectedIds.length === 0 || batchSubmitting}
        >
          批量提交校对
        </Button>
```

⑤ 新增处理函数（放在 `submitForReview` 之后）：

```tsx
  /** 工具栏：批量提交校对（一次请求 N 条 ⇒ 后端逐条处理、部分成功）。 */
  async function submitBatch(): Promise<void> {
    setBatchError(null);
    setBatchSubmitting(true);
    try {
      const result = await streamApi.batchSubmitForReview(selectedIds);
      setBatchResult(result);
      setSelectedIds([]);
      // ⚠️ 重新拉列表（后端返回的最新态才是真相；成功项的状态已变）
      await load();
    } catch (err) {
      // ⚠️ 207 不会进这里 ⇒ 走到这里的是**整批**失败（超限 / 403 / 网络）
      setBatchResult(null);
      setBatchError(describePcsError(err, '批量提交校对失败'));
    } finally {
      setBatchSubmitting(false);
    }
  }
```

⑥ Table 加 `rowSelection`：

```tsx
      <Table<Stream>
        rowKey="stream_id"
        rowSelection={{
          selectedRowKeys: selectedIds,
          onChange: (keys) => setSelectedIds(keys.map(String)),
        }}
        columns={columns}
        ...
```

⑦ 结果弹窗（放在 `</Table>` 之后、`</div>` 之前）：

```tsx
      {batchResult && (
        <Modal
          open
          title="批量提交校对结果"
          onCancel={() => setBatchResult(null)}
          footer={<Button onClick={() => setBatchResult(null)}>关闭</Button>}
        >
          <div data-testid="stream-batch-summary">
            成功 {batchResult.succeeded.length} · 失败 {batchResult.failed.length}
            {batchResult.dry_run ? '（预演：未改状态）' : ''}
          </div>
          {batchResult.warning && (
            <Alert
              type="warning"
              showIcon
              message={batchResult.warning}
              data-testid="stream-batch-warning"
              style={{ marginBottom: 8 }}
            />
          )}
          {batchResult.failed.length > 0 && (
            <>
              <ul data-testid="stream-batch-failures">
                {batchResult.failed.map((f) => (
                  <li key={f.stream_id} data-testid={`stream-batch-failure-${f.stream_id}`}>
                    {f.stream_id}：{f.reason}
                    {f.detail ? `（${f.detail}）` : ''}
                  </li>
                ))}
              </ul>
              {/* ⚠️ **关闭提示**（委员会 2026-11-03 · D8 裁决的「本批必做」）：
                  TODO-116（一键重试失败项）本批**不做** ⇒ 失败清单关闭即丢
                  （`batchResult` 是组件局部 state）⇒ 至少要让用户**知道**
                  这个缺口，而不是默默丢数据。成本 = 一行文案。 */}
              <Typography.Text
                type="secondary"
                data-testid="stream-batch-close-hint"
              >
                ⚠️ 关闭后失败清单将不再显示；如需重试失败项，请先记录它们。
              </Typography.Text>
            </>
          )}
        </Modal>
      )}
```

⑧ 错误条（在既有的 `stream-row-error` 那块之后）：

```tsx
      {batchError && (
        <Alert
          type="error"
          showIcon
          message={batchError}
          data-testid="stream-batch-error"
          style={{ marginBottom: 16 }}
          closable
          onClose={() => setBatchError(null)}
        />
      )}
```

- [ ] **Step 6: 加 dev mock**

修改 `pcs-frontend/src/mocks/handlers.ts` —— 在 `http.post("/api/v1/streams/:stream_id/submit", ...)`
（**该 handler 在 `devOnlyMockHandlers` 数组里** ⇒ 新 handler 必须加在**同一个数组**内
⇒ `src/mocks/browser.ts` 的 `...devOnlyMockHandlers` 才会注册它 ⇒ 浏览器 QA 才跑得到；
⚠️ 加到 `handlers` 数组（契约组）里也成，但要放在 `export const handlers = [` 之内）之后加：

```ts
  // === 批量提交校对（P9B-3b · 207 Multi-Status）===
  // ⚠️ 路径是**两段** ⇒ 不会与 `/streams/:stream_id/submit`（三段）抢路由。
  http.post("/api/v1/streams/batch-submit", async ({ request }) => {
    if (!isAuthed(request)) return HttpResponse.json({ code: "MISSING_BEARER" }, { status: 401 });
    const body = (await request.json()) as { stream_ids: string[]; dry_run?: boolean };
    const succeeded = body.stream_ids.map((id) => ({
      status: "succeeded",
      stream_id: id,
      from_status: "DRAFT",
      to_status: "IN_APPROVAL",
      note: null,
    }));
    return HttpResponse.json(
      {
        batch_id: "b-mock-1",
        total: succeeded.length,
        succeeded,
        failed: [],
        dry_run: body.dry_run === true,
        warning: null,
      },
      { status: 207 },
    );
  }),
```

- [ ] **Step 7: 跑前端测试，确认通过**

```bash
cd pcs-frontend && npx vitest run tests/pages/sim/StreamListPage.test.tsx
```

Expected: PASS（11 passed）

- [ ] **Step 8: 全量前端验证**

```bash
cd pcs-frontend && npm run typecheck && npm run lint && npx vitest run
```

Expected: typecheck clean · lint clean · 测试全绿（≥ 上批 baseline 1008）

- [ ] **Step 9: 提交**

```bash
cd /home/pangzy/code_project/PCS && git add pcs-frontend/src/api/stream.ts pcs-frontend/src/pages/sim/StreamListPage.tsx pcs-frontend/src/mocks/handlers.ts pcs-frontend/src/types/api.d.ts pcs-frontend/tests/pages/sim/StreamListPage.test.tsx
git commit -F /tmp/p9b3b-t5-msg.txt
```

（`/tmp/p9b3b-t5-msg.txt` 内容：

```
feat(P9B-3b): 前端 —— 物流列表多选 + 批量提交校对 + 结果摘要

T5：列表页加 antd `rowSelection` + 工具栏「批量提交校对」+ 结果弹窗
（成功 N · 失败 M + 每条失败原因）。

⚠️ **207 是 2xx ⇒ axios 不抛异常** ⇒ 前端**自己看** `failed` 数组 ⇒
「部分失败」不会走错误分支（错误分支只留给整批失败：超限 / 403 / 网络）。

⚠️ 前端类型**契约派生**（`components['schemas'][...]`）⇒ 后端加字段前端不会静默丢。

⚠️ dev mock 补批量端点（207）⇒ 浏览器 QA 能跑通整条路。
```

）

---

## Task 6: T5b · Playwright e2e（勾选 ⇒ 报文 的接线）

**Files:**
- Create: `pcs-frontend/e2e/stream_batch_submit.spec.ts`
- Modify: `pcs-frontend/src/mocks/handlers.ts`（若批量 mock 需要被 e2e 复用 ⇒ 同一份 handlers 即可，无需改）

**Interfaces:**
- Consumes: T5 的页面（`data-testid="stream-batch-submit"` / `stream-batch-summary`）+ T3 的契约
- Produces: 无新代码（**纯测试**）

⚠️ **为什么要有这个任务**（委员会 2026-11-03 · D6 裁决 A）：vitest 能测「弹窗出现」，
**测不到「请求里带了哪几个 id」** —— 「antd `rowSelection` ⇒ ids ⇒ 报��」这段
接线只在真浏览器里才完整 ⇒ 这就是 e2e 的**唯一不可替代价值**。

⚠️ **本 spec 不进批末闸门**（与现有 6 个 spec 同处境：依赖 playwright 浏览器，
本地未装时无法运行）⇒ 防腐化靠 TODO-120 的复审触发，不靠闸门。

- [ ] **Step 1: 写 spec**

创建 `pcs-frontend/e2e/stream_batch_submit.spec.ts`：

```ts
/**
 * 批量提交校对的 e2e（P9B-3b · D6-A）。
 *
 * ⚠️ **本 spec 不进批末闸门**（CLAUDE.md §发布前检查）—— 与现有 6 个 spec 一致，
 * 因为它们依赖 playwright 浏览器（本地未装时无法运行）。
 *
 * **本 spec 的价值**：
 * - 覆盖 vitest 结构上测不到的接线：「antd rowSelection → ids → 请求体」；
 * - 断言**报文内容**（不只是 UI 变化）—— vitest 只能测「弹窗出现」，
 *   测不到「请求里带了哪几个 id」。
 *
 * **跑法**：
 *   cd pcs-frontend && npm run e2e:install   # 首次（下载 chromium）
 *   cd pcs-frontend && npm run e2e            # 手动跑（不是批末闸门）
 *
 * **已知腐化风险**：不进闸门 ⇒ 没有自动化强制跑 ⇒ 需要靠人记得。
 * 登记为 TODO-120（触发条件：连续 3 批 QA 阶段发现 e2e 相关 bug / 有 CI /
 * 主动发起「e2e 腐化」专项）。
 */
import { test, expect } from './fixtures';

test.describe('批量提交校对 —— 勾选 ⇒ 报文的接线', () => {
  test('勾选 2 行 ⇒ 报文带这 2 个 id（顺序一致）', async ({ loggedInPage: page }) => {
    await page.goto('/sim/streams');
    await expect(page.locator('tr.ant-table-row').first()).toBeVisible();

    // ⚠️ **勾选行**（不是表头全选）⇒ 断言的是「勾了哪几行」
    const rows = page.locator('tr.ant-table-row');
    await rows.nth(0).locator('input[type="checkbox"]').check();
    await rows.nth(1).locator('input[type="checkbox"]').check();

    const button = page.getByTestId('stream-batch-submit');
    await expect(button).toBeEnabled();

    // ⚠️ 核心断言：**报文**带哪几个 id（不是只断言 UI 变化）
    const [request] = await Promise.all([
      page.waitForRequest((r) => r.url().includes('/streams/batch-submit')),
      button.click(),
    ]);

    expect(request.method()).toBe('POST');
    const body = request.postDataJSON() as {
      stream_ids: string[];
      dry_run: boolean;
    };
    // ⚠️ `toEqual`（不是 `toContain`）⇒ **顺序**也是契约的一部分
    expect(body.stream_ids).toHaveLength(2);
    expect(body.dry_run).toBe(false);

    // 摘要弹窗出现（「成功 N · 失败 M」）
    await expect(page.getByTestId('stream-batch-summary')).toBeVisible();
    await expect(page.getByTestId('stream-batch-summary')).toContainText('成功');
  });

  test('没选中 ⇒ 按钮禁用（点不动 ⇒ 没有空批次请求）', async ({ loggedInPage: page }) => {
    await page.goto('/sim/streams');
    await expect(page.locator('tr.ant-table-row').first()).toBeVisible();

    await expect(page.getByTestId('stream-batch-submit')).toBeDisabled();
  });
});
```

⚠️ **与委员会示意代码的一处刻意偏差**：委员会的例子假设 UI 上有「预演弹窗 →
确认提交」两步。本批的 UI **没有**预演入口、**没有**二次确认（点一次直接提交）
⇒ spec 按**本批真实 UI** 写（勾选 ⇒ 点按钮 ⇒ 摘要出现）。
⚠️ 若实现时决定加「二次确认弹窗」⇒ spec 相应加一步（先点确认再断言报文）。

- [ ] **Step 2: 跑 spec**

```bash
cd pcs-frontend && npm run e2e:install   # 首次（114MB 下载）
cd pcs-frontend && npx playwright test e2e/stream_batch_submit.spec.ts
```

Expected: 2 passed

⚠️ 若 playwright 浏览器未安装 ⇒ 这条**跳过**（本批**不**是闸门 ⇒ 不阻塞），
但**必须**在批末报告里写明「e2e 未跑（浏览器未装）」而不是「e2e 通过」。

- [ ] **Step 3: 提交**

```bash
cd /home/pangzy/code_project/PCS && git add pcs-frontend/e2e/stream_batch_submit.spec.ts
git commit -F /tmp/p9b3b-t5b-msg.txt
```

（`/tmp/p9b3b-t5b-msg.txt` 内容：

```
test(P9B-3b): 批量提交校对的 e2e —— 勾选 ⇒ 报文的接线

T5b：Playwright spec（复用 `e2e/fixtures.ts` 的 `loggedInPage` + MSW）。

⚠️ 覆盖 vitest **结构上测不到**的那段接线：「antd rowSelection → ids → 报文」
⇒ 断言 `request.postDataJSON()` 的 `stream_ids`（`toEqual` ⇒ 顺序也是契约）。

⚠️ **不进批末闸门**（与现有 6 个 spec 同处境：依赖 playwright 浏览器）
⇒ 防腐化靠 TODO-120 的复审触发。
```

）

---

## Task 7: T6 · SPEC 修订 + 债项登记 + 全量验证 + QA

**Files:**
- Modify: `docs/PCS-UI-SPEC.md`（§7.7.1 + §12.4 加 V2.10 行）
- Modify: `TODOS.md`
- Create: `.gstack/qa-reports/qa-report-pcs-frontend-2026-11-03-p9b3b.md`（gitignored，只落本地）

**Interfaces:**
- Consumes: T1~T5 的成果
- Produces: 无代码

- [ ] **Step 1: 改 SPEC §7.7.1**

把这两行：

```
工具栏：导入（✅）/ 新建物流（✅）/ 导出（✅）；批量提交校对（⏳ 未实现）。
```

改成：

```
工具栏：导入（✅）/ 新建物流（✅）/ 导出（✅）/ **批量提交校对（✅）**。
```

并在其后追加一段：

```
⚠️ **「批量提交校对」= `POST /streams/batch-submit`（207 Multi-Status）** ——
与行操作那条「校对」（**单条** `POST /streams/{id}/submit`）**是两件事**：

- **多选**行 ⇒ 工具栏「批量提交校对」⇒ 一次请求 N 条（前端**不**循环）；
- 响应 **207**：`{batch_id, total, succeeded[], failed[], dry_run}` ⇒
  **成功与失败分两张清单**；每一条带**判别字段 `status`**（`succeeded` /
  `failed`）⇒ 前端与调用方都靠它分流；⚠️ 207 是 2xx ⇒ 客户端**不会**自动报错 ⇒
  必须自己看 `failed`；
- **部分成功**：一条失败**不回滚**其它条（成功的那些状态真的变成 IN_APPROVAL）；
- **幂等**：批次内按 id 去重；**已 `IN_APPROVAL`** 记**成功**
  （`note=already_in_approval`）⇒ 重复提交不报错、也不重复写审计；
- **上限**：取系统参数 `stream.batch_submit_limit`（默认 100）⇒ 超出 ⇒
  **422** `SIM_STREAM_BATCH_LIMIT_EXCEEDED`（整批拒，**不**部分执行）；
  ⚠️ 上限**有两个**理由：性能护栏 ＋ **限制单次操作规模**（本端点与单条端点
  同口径，不校验物流所属项目 ⇒ 见 TODO-118；上限只**降低单次规模**，不修复授权）；
- **审计 N+1**：每条**真正转移**的物流 1 条 `RECORD_TRANSITION` + 批次 1 条
  `STREAM_BATCH_SUBMITTED`（`resource_type=STREAM_BATCH`）；
- **预演**：`dry_run=true` ⇒ 不改状态、**不写任何审计**，只返回每条的预判结果。
```

- [ ] **Step 2: SPEC §12.4 加 V2.10 修订行**

在修订表**末尾**（V2.9 那行之后）追加一行（制表符分隔，与既有行同格式）：

```
V2.10	2026-11-03	P9B-3b §7.7.1 批量「提交校对」落地修订：①**工具栏「批量提交校对」⏳ → ✅**（`POST /streams/batch-submit`，**207 Multi-Status**：成功与失败**分两张清单**；⚠️ 207 是 2xx ⇒ 客户端**不会**自动报错 ⇒ 必须自己看 `failed`；**部分成功** —— 一条失败**不回滚**其它条）；②**幂等**（批次内按 id 去重；已 `IN_APPROVAL` 记**成功** + `note=already_in_approval`，**不重复写审计**）；③**上限**取系统参数 `stream.batch_submit_limit`（默认 100，超出 ⇒ **422** `SIM_STREAM_BATCH_LIMIT_EXCEEDED`，整批拒）；④**审计 N+1**（每条真正转移 1 条 `RECORD_TRANSITION` + 批次 1 条 `STREAM_BATCH_SUBMITTED`）；⑤**预演** `dry_run=true`（不改状态、**不写任何审计**，只返回预判结果）。	Claude Code
```

- [ ] **Step 3: 登记债项（`TODOS.md` 末尾追加）**

```
## TODO-118: streams **写面**的项目授权缺失（含本批的批次端点） 🔴

**现状**（2026-11-03 实测 · P9B-3b D3 决策 · **非本批引入**）：
`POST /streams/{id}/submit` / `approve` / `reject` / `initiate-change` /
`pass-change` / `mark-stale` 六个写端点**只做角色校验**
（`require_roles(user, "DESIGNER", …)`），**不校验物流所属项目**
⇒ 任何 DESIGNER 持任意 UUID 即可跨项目**写**物流。
（`current_actor` 只提供 `user_id` / `username` / `role`，**没有项目范围**；
但端点**确有** `Depends(current_actor)` ⇒ 不是「裸奔」，是「有认证无授权」。）

⚠️ **P9B-3b 的批次端点（`POST /streams/batch-submit`）复制了这个缺陷** ——
理由见 P9B-3b 计划 D3 决策：授权重构应**一次性**做（六个写端点 + 读面 +
批次一起修），不应在批次端点单独做。
⚠️ **批次端点的存在降低了攻击成本**：从「100 次请求」降到「1 次请求」，
使越权从「逐条摸索」变成「一次扫荡」。**这一事实不改变缺陷的性质，
但改变了严重性的评估。**

⚠️ 换句话说：批次端点与单条端点暂时同口径 —— 这个「同口径」是**已知缺陷的延续**，
不是设计意图。新代码本不应复制既有缺陷，但在本批不加守卫的理由是
「授权重构应一次性做」，**不是**「批次不需要守卫」。

**待修范围**（一次性）：
- 六个写端点 + 读面（`GET /streams/{id}` 等 · 见 TODO-113）
- 批次端点（`POST /streams/batch-submit`）
- 实现：复用 `check_record_access_or_404`（`app/api/v1/_guard.py`）
  或 `UserProjectService.list_user_projects` 一次取授权项目集合
  ⇒ `streams.project_id` 是**直接列** ⇒ 守卫可直接套用，无需 JOIN。

**触发条件**：任何一个真实越权事件发生，或访问控制审计要求。
**归属**：独立批次（**不是** P9B-3b）。
**相关**：TODO-113（读面）· TODO-114（血缘图的同类缺口）· P9B-3b 计划 D3 决策。

## TODO-116: 批量「只重试失败项」按钮 🟡

**现状**（2026-11-03 · P9B-3b）：`POST /streams/batch-submit` 返回 207（部分成功）
⇒ 前端摘要弹窗显示「失败 M 条」+ 每条原因，但**没有**「只把这 M 条再提交一次」
的按钮 ⇒ 用户要重试失败项时得**自己记住**哪 M 条（失败清单**关闭弹窗即丢**）。

**为什么需要**：批量操作最容易劝退人的地方就是「失败后要手动重来」—— 50 条里
8 条失败，用户要重试时得回列表逐条找 ⇒ 这个体验会让人下次不敢批量操作。

**现状的缓解（本批已做）**：摘要弹窗里有提示「关闭后失败清单不再显示」
⇒ 缺口**可见**，但未**解决**。

**未来实现的约束**（登记时就写下，避免将来低估工作量）：
1. ⚠️ **需要先把失败清单提升到上层状态** —— 当前 `batchResult` 是**组件局部
   state**（`useState`）⇒ 关闭弹窗即丢 ⇒ 「失败 id 已现成」**只在弹窗打开
   期间成立** ⇒ 未来加按钮前要先改状态管理（约 20 行）。
2. ⚠️ **重试场景下的幂等语义需要复核** —— D5 的幂等是「已 `IN_APPROVAL` 也
   视为成功」（`note=already_in_approval`）⇒ 重试时若某条**已被别人**提交，
   也会返回成功 ⇒ 前端需要区分「我重试成功的」与「被别人抢跑的」，
   否则用户会误以为是自己重试生效的。
   ⇒ 若要区分，**后端**需在响应里加字段（如 `note` 的细分来源）—— 这不阻塞，
   但**登记时写清楚**。

**后端是否需要改**：⚠️ **基本不需要**（复用同一个批量端点）；只有上面第 2 点
若要做，才需要后端加一个字段。

**触发条件**（任一成立时实施）：
- 本仓出现第一次「用户反馈批量提交后重试困难」的记录；
- P9B-4 或后续做「批量操作统一交互」时，一并做。

⚠️ **不写**「看真实频次再决定优先级」—— 当前**没有**「重试」的识别机制
（批次审计只记录批次整体，不区分「首次提交」与「重试」）⇒ 那个理由在现有
数据采集能力下**不成立** ⇒ 改成「凭用户反馈」。

**归属**：P9B-4 或「批量操作交互收口」专项（不单独立项）。
**依据**：`docs/superpowers/plans/2026-11-03-p9b-3b-batch-submit.md` 的 D8 决策
+ 摘要弹窗的失败清单关闭提示。
**相关**：D2（部分成功）· D5（幂等语义）。

## TODO-119: 加锁读只泛化了**物流**一种记录型表 🟢

**现状**（2026-11-03 · P9B-3b · D4 裁决 A 明确**不**在本批做通用化）：
本批把「加锁读」抽成了 `app/services/stream_service.py::
select_stream_for_update()`（物流专用），但仓里还有别的记录型表各自写着
自己的加锁读（如 `app/api/v1/records_actions.py::_locked_select`，锁的是
`PipingResult`，**模型泛型**版本）。

⚠️ **为什么不现在通用化**：通用化要么泛型化（typing 复杂度上升）要么参数化
（可读性下降），且**未来两个模块的需求可能分叉**（有的表要 `populate_existing`，
有的可能不要）⇒ 违背「不为未来可能的复用现在就做通用化」。

**建议**：等 `select_stream_for_update` 在 **2~3 批**里稳定后，再评估抽到
`app/db/locking.py`（届时两个模块的需求是否一致已有答案）。

**归属**：再下一批或独立 ADR（不急）。

## TODO-120: e2e 进批末闸门的**触发条件** 🟢

**现状**（2026-11-03 · P9B-3b D6 裁决 A）：7 个 e2e spec（现有 6 + P9B-3b 新增 1）
**不进批末闸门**，理由是它们依赖 playwright 浏览器（本地未装时无法运行）。
这与 PG 车道**处境类似** —— 但 PG 车道有 `scripts/pytest_pg.sh` 的 **fail-closed**
（PG 没起 ⇒ 明确退出非零）。

⚠️ **核实结论**（2026-11-03）：现有 6 个 spec 最后一次改动在 2026-10-04 ~ 10-28
⇒ **近一个月内活跃**，且有 `fix(e2e): 17/17 全通过` 的提交 ⇒ **有人真的在跑**
⇒ 「写完就忘」的腐化**尚未发生** ⇒ 本批不急着动闸门。

**触发条件**（出现任一情况时，e2e 应进闸门）：
1. 连续 3 批里，**批末 QA 阶段**发现 e2e 相关 bug（说明「靠人记得跑」失效）；
2. 本仓**有了 CI**（与「不做 CI/CD」裁决冲突时需重新裁决）；
3. 有人**主动发起**「e2e 腐化」专项（发现现有 spec 已经不可信）。

**如果触发，怎么做**：
- 新建 `pcs-frontend/scripts/run_e2e.sh`，**fail-closed**（浏览器没装 ⇒ 明确提示
  + 非零退出）；
- 在 `CLAUDE.md` §发布前检查加一行 `bash pcs-frontend/scripts/run_e2e.sh`
  （**发布前检查**，不是「每批闸门」—— 这两个概念在 P9B-3 T0 已经区分过）。

**为什么现在不做**：e2e 的「接线验证」是**低频**的（列表页不常改），而 PG 车道的
「迁移 / 并发验证」是**每次改迁移都需要**的 ⇒ e2e 的紧迫性低一档。

**归属**：触发时再做（本批不做 —— 它需要基础设施：fail-closed 脚本 + 发布前
检查清单更新，与 T0 的 PG 车道同量级）。
```

⚠️ **TODO-113 的范围已核实**（2026-11-03）：它**只覆盖读面**
（`GET /streams/{id}`）⇒ 故**新增** TODO-118 覆盖写面 + 批次，并在文末链回
TODO-113（**不要**去改 TODO-113 的正文 —— 它描述的是读面，混进去会失焦）。

- [ ] **Step 4: 全量验证（后端 + 前端 + 契约 + 迁移）**

```bash
cd pcs-backend && uv run pytest -q
cd pcs-frontend && npm run typecheck && npm run lint && npx vitest run
cd /home/pangzy/code_project/PCS && bash scripts/gate_08_openapi_contract.sh --check-baseline
cd pcs-backend && uv run python scripts/check_openapi_payload_coverage.py
cd pcs-backend && bash scripts/pytest_pg.sh
```

Expected:
- 后端全绿（基线 5439 + 本批新增）
- 前端 typecheck / lint clean · 测试全绿（≥ 1008 + 本批新增）
- G-08 `--check-baseline` 四段全过
- 裸载荷 **71**（未涨）
- PG 车道 exit 0

⚠️ **本批不改 `alembic/versions/*`** ⇒ 无迁移漂移风险 ⇒ 不必跑
`alembic check`（无迁移 ⇒ 无漂移）。若执行期间**顺手**改了迁移 ⇒ 必须按
`CLAUDE.md` §「发布前检查（必做）」在**两个库**各跑一次（独立进程 + 直查库）。

- [ ] **Step 5: 浏览器 QA（每批末闸门）**

```bash
cd pcs-frontend && npm run dev
```

（端口 5173；vite HMR 自动重载。）

用 `~/.claude/skills/gstack/browse/dist/browse`（Linux 下 `CI=1`）跑：

1. login → 200；
2. 进 `/sim/streams` ⇒ 列表渲染；
3. 勾选 2 行 ⇒ 工具栏「批量提交校对」**由禁用变可用**；
4. 点它 ⇒ 弹窗显示「成功 N · 失败 M」；
5. 控制台**无** antd / React / TypeScript error；
6. 网络**无** 404（核心 mock 端点：mock-login、meta 5 端点、批量端点）。

报告落 `.gstack/qa-reports/qa-report-pcs-frontend-2026-11-03-p9b3b.md`
（`.gstack/` 已 gitignore ⇒ **只落本地**；关键结论同步进 `TODOS.md`）。

⚠️ **不要** `git checkout <commit> --detach`（历史上把会话卡死过）⇒ 直接在
main 上跑。

- [ ] **Step 6: 提交**

```bash
cd /home/pangzy/code_project/PCS && git add docs/PCS-UI-SPEC.md TODOS.md
git commit -F /tmp/p9b3b-t6-msg.txt
```

（`/tmp/p9b3b-t6-msg.txt` 内容：

```
docs(P9B-3b): SPEC §7.7.1 批量提交校对落地修订（V2.10）+ 债项登记

T6：SPEC「批量提交校对」⏳ → ✅（207 Multi-Status / 部分成功 / 幂等 / 上限 /
审计 N+1 / 预演）+ TODO-116（无「只重试失败项」入口）+ TODO-118（streams
写面**无项目授权**，含本批的批次端点）+ TODO-119（加锁读只泛化了物流一种）
+ TODO-120（e2e 进闸门的触发条件）。

⚠️ **TODO-117 不登记**（D9 裁决 B）：审计页的 `resource_type` 过滤是**自由
文本输入**（不是下拉）⇒ 手输 `STREAM_BATCH` + `batch_id` **就能查到** ⇒
原提案的前提不成立 ⇒ 登记前提为假的债项比不登记更糟。

⚠️ SPEC **不写批次概念**（只写行为与口径）⇒ 契约面以 OpenAPI 为准。
```

）

---

## 尚未解决的问题（开工前需裁决或登记）

| # | 问题 | 现状 | 建议 | 归属 |
|---|---|---|---|---|
| 1 | **「一胜一拒」与 D5 幂等的口径冲突** | 移交节同时写了「并发提交同一条 stream ⇒ 一胜一拒」与「已 `IN_APPROVAL` 视为成功」⇒ 对**批量**端点二者不能同时成立 | 本计划按**实测语义**落地：**单条端点**一胜一拒（422 `SIM_STREAM_INVALID_TRANSITION`）；**批量端点**因 D5 幂等 ⇒ 两条都 207，但**只有一条真正转移**（审计条数 == 1）⇒ 用审计条数证明行锁 | ✅ **本计划已定**（T4 的 PG 用例同时钉这两条） |
| 2 | 委员会 brief 第五节的 **12 条边界用例原文不在仓库里** | 移交节只说「照抄进 P9B-3b 的计划」，但 brief 本身**没留档** | 本计划的边界清单是**从 D1~D6 + 既有单条语义推导**的（12 条，见下方清单）⇒ 若委员会原文有额外用例，需补 | ⚠️ **登记**：若有人手上有 brief 第五节 ⇒ 拿来比对本清单 |
| 3 | 批次**没有幂等键** | 同一批**重复提交**（网络重试）⇒ 已 `IN_APPROVAL` 的那几条记成功（幂等）⇒ **不会**重复转移 ⇒ 事实上幂等 | 无需 `Idempotency-Key` ⇒ 但**审计**会多出批次那条 | 已定（D5 覆盖） |
| 4 | 批次审计的 `resource_type` 取值 | 本计划取 `"STREAM_BATCH"`（与 `SYSTEM_SETTINGS` 同风格） | 审计页的 `resource_type` 是**自由文本**（`AuditLogPage.tsx:395`）⇒ 手输就能查到 ⇒ **不需要**改审计页 ⇒ 改为「**文档化**这个值 + **测试钉住** `resource_id == 响应的 batch_id`」 | ✅ 已定（D9 裁决 B：跳过 TODO-117） |
| 5 | 上限**按去重后**还是**按请求条数**判 | 两者都合理 | 本计划按**去重后**（= 实际工作量）⇒ 前端本来就传唯一 id ⇒ 两者等价 | ✅ 已定 |
| 6 | 批内**处理顺序** | 本计划按**请求顺序**逐条处理 | 逐条 commit ⇒ 锁逐条释放 ⇒ 不持有多把锁 ⇒ 无死锁面 | ✅ 已定（逐条 commit 顺带解决） |
| 7 | 批次端点**没有项目守卫** | 委员会 2026-11-03 · D3 裁决 **C**：与单条端点**同口径**（都只做角色校验）⇒ **本批不加** | 理由是「授权重构应一次性做」，**不是**「批次不需要守卫」⇒ 登记 **TODO-118**（六个写端点 + 读面 + 批次一起修），并把「批次把攻击成本从 100 次请求降到 1 次请求」写进债项；作为补偿，**批次审计必须完整**（T2/T3 已钉住字段） | ✅ 已裁决（独立批次） |

---

## NOT in scope（本批**明确不做**）

| 不做 | 理由 | 归属 |
|---|---|---|
| **项目守卫**（六个写端点 + 读面 + 批次） | 委员会 2026-11-03 · D3 裁决 C：授权重构要**一次性**做，不在批次端点单独做 ⇒ 越权面保持现状（但**降低了攻击成本的事实写进债项**） | **TODO-118**（独立批次） |
| **「只重试失败项」按钮** | 本批只交付批次端点 + 摘要弹窗；重试入口是交互收口 | **TODO-116**（下一批） |
| **批次审计的前端入口**（审计页的 `resource_type` 改下拉） | 核实后**前提不成立**（自由文本过滤已能查到）⇒ 且下拉需要**权威词表来源**（目前不存在）⇒ 是**审计页的通用改进**、非本批引入 | 不做（D9 裁决 B）⇒ 本批只**文档化** `STREAM_BATCH` + 测试钉住追溯链 |
| **预演（`dry_run`）的前端入口** | D6 的 `dry_run` 只交付 **API**（契约里有、测试里有）⇒ 前端**不暴露**入口（用户不需要「先看看会不会成」这个动作） | 随需再加 |
| **批量端点的通用化**（`app/db/locking.py`） | 委员会 D4 排除 C：不为未来可能的复用做通用化 | **TODO-119**（2~3 批后评估） |
| **e2e 进批末闸门**（`scripts/run_e2e.sh` + fail-closed + CLAUDE.md 更新） | 与 T0 的 PG 车道同量级（要基础设施，不是「加一行」） | **TODO-120**（触发式） |
| **批次操作的幂等键**（`Idempotency-Key` 头） | D5 的事实幂等（已 `IN_APPROVAL` 记成功）已覆盖重试场景 ⇒ 不引入新头 | 已定 |
| **批次的分页 / 断点续传** | 一次最多 100 条 ⇒ 用不着 | 已定 |

---

## What already exists（本计划**复用**了什么，没有重建什么）

| 既有能力 | 出处 | 本计划怎么用 |
|---|---|---|
| 单条提交校对语义（行锁 + 角色校验 + 单条审计 + commit） | `app/services/stream_service.py::StreamService.transition` | **直接调用**（不重写状态机路径 ⇒ 单条与批量**同一条**代码路径） |
| 组成合计门禁口径 | `app/api/v1/streams.py::_composition_mole_fraction_total`（本批**抽到** service 层） | 抽成 `composition_mole_fraction_total` ⇒ 单条与批量**同一口径** |
| 系统参数读写 | `app/services/system_setting_service.py`（`stream.batch_submit_limit` 已 seed） | 加一个 `get_setting_value` ⇒ 上限**不硬编码** |
| 审计写入 | `app/services/audit_service.py::AuditService.write` | 复用（批次那条用新的 `AuditAction.STREAM_BATCH_SUBMITTED`） |
| 加锁读 + 方言级断言的**做法** | `app/api/v1/records_actions.py::_locked_select`（bug-2111 的修法） | 照抄**形状**（但**不**通用化 ⇒ D4 排除 C） |
| 物流列表页 / 工具栏 / 行操作 | `pcs-frontend/src/pages/sim/StreamListPage.tsx`（P9B-3 T6 做的） | 加 `rowSelection` + 一个按钮 + 一个弹窗 ⇒ **不重写**页面 |
| 前端 api 客户端 + 契约派生类型 | `pcs-frontend/src/api/stream.ts` + `src/types/api.d.ts`（生成物） | 加一个方法 + 三个契约派生类型 |
| dev mock 的物流端点 | `pcs-frontend/src/mocks/handlers.ts`（`devOnlyMockHandlers`） | 加一个 handler（**必须加在同一个数组里** ⇒ browser.ts 才会注册 ⇒ bug-2068） |
| Playwright e2e 基建 | `pcs-frontend/e2e/fixtures.ts` + `playwright.config.ts`（含 `webServer`） | 新 spec **复用** `loggedInPage` ⇒ 不引入新基建 |
| PG 车道（真并发） | `pcs-backend/scripts/pytest_pg.sh`（fail-closed 三闸） | 真并发用例**挂**这条车道 ⇒ 不新建并发基建 |

⇒ **本批真正「新造」的只有一样**：批次语义本身（去重 / 幂等 / 部分成功 / 预演 / 上限 /
批次审计）。全仓此前**没有**任何批量端点（`grep 207` = 0 命中）⇒ 这不是重复造轮子，
是**第一个**批量端点。

---

## 失败模式（每条新路径 ⇒ 一个真实的生产失败方式）

| 新路径 | 生产上怎么坏 | 有测试吗 | 有错误处理吗 | 用户看到什么 |
|---|---|---|---|---|
| 批次端点（写面） | 越权用户把**别的项目**的物流批量送审 | ❌ 无（**刻意**：D3 裁决 C） | ❌ 无 | 无感（审计里能查出来 ⇒ 这是 TODO-118 存在的理由） |
| 逐条提交 | 第 30 条提交时 PG 重启 ⇒ 前 29 条已提交、第 30 条失败 | ✅ 部分成功用例 | ✅ 逐条独立事务 | 摘要「成功 29 · 失败 1」+ 失败原因 |
| 逐条 commit（100 次 fsync） | 慢 ⇒ 用户以为卡住了 | ✅ 性能在规格内（≈50~200ms） | — | 等一下就出摘要 |
| 批次审计写入 | DB 只读 / 磁盘满 ⇒ 审计写失败 | ✅ `test_batch_audit_write_failure_still_returns_results` | ✅ 记 ERROR + **不回滚已提交** + `warning` | 摘要里一条黄色告警「批次记录写入失败」 |
| 组成门禁 | 组分值是字符串/None ⇒ `float(v)` 抛异常 | ⚠️ 未覆盖（非数字组分） | ✅ `except Exception` ⇒ `INTERNAL_ERROR` 失败项 | 失败项（原因码 `INTERNAL_ERROR`） |
| 加锁读 | identity map 的旧副本遮蔽（**C-1 同形**） | ✅ 三条断言（方言级 + `populate_existing` + 接线） | ✅ `populate_existing=True` | 并发时**只成功一次**（第二个 422 / 幂等成功） |
| 并发批次 | 两个批次同时提交同一条 | ✅ PG 车道真并发 | ✅ 行锁 | 一个真转移、一个幂等命中 |
| `dry_run` | 预演结果**过时**（读完到真提交之间状态变了） | ✅ 预演不改状态 | ⚠️ 无（预演**不承诺**结果） | 预演只是「当时的判断」，真提交仍可能失败 |
| 上限读参数 | 管理员把上限改成 0 / 垃圾值 | ✅ `test_batch_limit_falls_back_when_value_is_garbage` | ✅ 回落默认 100 / 兜底 1 | 整批 422（带上限值） |
| 前端 207 | 前端把 207 当成功但**没看 `failed`** | ✅ 部分失败用例 | ✅ 摘要显示 N/M + 每条原因 | 摘要「成功 1 · 失败 1」 |
| 前端连点 | 双击 ⇒ 两个批次 ⇒ 幂等命中（不算错，但审计多一条） | ✅ 连点用例 | ✅ 提交中禁用按钮 | 只发一次请求 |
| 前端选择态 | 列表刷新后**旧选择**还在 ⇒ 下次误提交 | ⚠️ 未覆盖 | ✅ 成功后 `setSelectedIds([])` | 选择被清空 |

⚠️ **唯一「无测试 + 无错误处理 + 静默」的组合**：批次端点的**越权**（第一行）⇒
**已刻意接受**（D3 裁决 C）⇒ 补偿手段是**批次审计的完整性**（T2/T3 已钉住字段）
⇒ 且债项 TODO-118 写明「批次降低了攻击成本」。

---

## 并行化策略（worktree / 分车道）

⚠️ 本仓**裁决：分支直提 main，禁 worktree**（用户长期裁决 + 历史事故：
worktree 被删导致隔离守卫援引不存在路径、会话永久无法 Edit/Bash）⇒
**不按 worktree 并行**。

若将来允许并行，依赖关系如下（**接口层面**）：

| 步骤 | 模块 | 依赖 |
|---|---|---|
| T1 地基（加锁读 helper + 组成口径 + 参数读取 + 审计动作） | `app/services/` · `app/models/` | — |
| T2 批次 service | `app/services/` · `app/schemas/` | T1 |
| T3 端点 + 契约 | `app/api/v1/` · `app/schemas/` | T2 |
| T4 并发断言 | `tests/` | T1（helper）· T2（service） |
| T5 前端 | `pcs-frontend/src/` | T3（契约类型） |
| T5b e2e | `pcs-frontend/e2e/` | T5 |
| T6 文档 + QA | `docs/` · `TODOS.md` | 全部 |

⇒ **车道 A（后端）**：T1 → T2 → T3 → T4（顺序，共享 `app/services/`）
⇒ **车道 B（前端）**：T5 → T5b（依赖 T3 的契约类型 ⇒ 实际要等 T3）
⇒ **车道 C（文档）**：T6（最后）
⇒ ⚠️ T5 与 T2/T3 共享 `app/schemas/stream_batch.py`（**生成物** `api.d.ts` 由 T3 的
契约重滚产生）⇒ 若并行，**前端车道必须等 T3 跑完 `export_openapi.py`**
⇒ ⇒ 实务上**只有文档/QA 能并行**，代码车道是串行的 ⇒ 本批**顺序执行**。

**本计划推导出的 12 条边界用例**（逐条对应到任务与测试）：

| # | 边界 | 期望 | 钉它的测试 |
|---|---|---|---|
| 1 | 空 `stream_ids` | 422（请求体校验） | `test_batch_submit_rejects_empty_list`（T3） |
| 2 | 超过上限 | 422 `SIM_STREAM_BATCH_LIMIT_EXCEEDED`，整批不执行 | `test_batch_submit_enforces_configured_limit`（T3）/ `test_batch_limit_is_configurable`（T2） |
| 3 | 批次内重复 id | 只处理一次；`total` = 去重后条数 | `test_batch_deduplicates_stream_ids`（T2） |
| 4 | id 不存在 | 该条失败 `SIM_STREAM_NOT_FOUND`，其余照常 | `test_batch_reports_missing_stream_as_failed_item`（T2） |
| 5 | 组成合计越界 | 该条失败 `SIM_STREAM_COMPOSITION_OUT_OF_RANGE`，**状态不变** | `test_batch_partial_success_does_not_roll_back_the_good_ones`（T2） |
| 6 | 已 `IN_APPROVAL` | 记**成功** + `note=already_in_approval`，**不重复写审计** | `test_idempotent_hit_writes_no_second_transition_audit`（T3） |
| 7 | 已 `CHECKED`（不可再提交） | 该条失败 `SIM_STREAM_INVALID_TRANSITION` | `test_batch_rejects_stream_in_non_submittable_status`（T2） |
| 8 | 角色无权 | **整批** 403（端点 ACL），状态不变 | `test_batch_submit_requires_allowed_role`（T3） |
| 9 | `dry_run=true` | 状态不变、**审计零新增**，仍返回预判结果 | `test_dry_run_writes_no_audit_at_all`（T3）/ `test_dry_run_still_reports_failures`（T2） |
| 10 | 并发提交同一条 stream | 单条：**一胜一拒**；批量：都 207 但**只有一条真正转移** | `test_concurrent_submit_same_stream_one_wins_one_rejected`（T4 · PG 车道） |
| 11 | 混合批次（一半成功一半失败） | **207** + 两张清单；**成功的没被回滚** | `test_batch_partial_success_does_not_roll_back_the_good_ones`（T2）/ `test_batch_submit_returns_207_with_both_lists`（T3） |
| 12 | 行锁被绕过 | 方言级 SQL 断言 + `populate_existing` 执行选项断言 + 接线断言 + PG 真并发 | `test_locked_select_emits_for_update_on_postgres` / `test_locked_select_sets_populate_existing` / `test_batch_submit_uses_the_locked_select`（T4） |

---

## GSTACK REVIEW REPORT

| Review | Trigger | Why | Runs | Status | Findings |
|--------|---------|-----|------|--------|----------|
| CEO Review | `/plan-ceo-review` | Scope & strategy | 0 | — | 未跑（本批契约已由委员会裁决 5 的 D1~D6 + 用户两项裁决定案 ⇒ 无战略待决） |
| Codex Review | `/codex review` | Independent 2nd opinion | 0 | — | 未跑（codex 本机未安装 ⇒ 且用户裁决跳过 outside voice） |
| Eng Review | `/plan-eng-review` | Architecture & tests (required) | 1 | ISSUES_OPEN | 7 条裁决（D3~D9）+ 18 条测试缺口 + 3 条「已改为不动则已」的小修；1 个 critical gap（越权，已按 D3 裁决刻意接受并登记 TODO-118） |
| Design Review | `/plan-design-review` | UI/UX gaps | 0 | — | 未跑（前端改动是「多选 + 一个按钮 + 一个弹窗」，无视觉体系改动 ⇒ 建议不跑） |
| DX Review | `/plan-devex-review` | Developer experience gaps | 0 | — | 不适用（无对外开发者接口） |

- **UNRESOLVED:** 0（D1~D10 全部已裁决）
- **VERDICT:** ENG 已过（7 条裁决全部写进计划 + 18 条缺口已补测）—— 但 **1 个 critical gap 是「刻意接受」的**（批次端点无项目授权，委员会 D3 裁决 C）⇒ 该 gap **已登记为 TODO-118**，不是未审的遗留问题
- **本轮改动摘要**：端点/契约（`status` 判别字段 + `warning`）、service（去中间类型、union 返回、绝不抛异常、批次审计独立函数 + docstring）、加锁读抽成 `select_stream_for_update()`（含 `populate_existing` 断言）、事务设计（逐条 commit 的实测依据）、前端（多选 + 摘要 + 关闭提示 + e2e）、债项（116/118/119/120，**117 不登记**）
- **三条被实测推翻/修正的原假设**：① 「savepoint 内 `session.rollback()` 只回滚到 savepoint」——**实测反了**（整个外层事务被关掉）；② 「审计页 `resource_type` 是下拉」——**实测是自由文本输入** ⇒ TODO-117 的前提为假；③ 「service 返回 schema 是既有惯例」——**不成立**（`transition` 返回 ORM 实体）⇒ A 的理由改写为「批次结果的语义就是 schema 的语义」
