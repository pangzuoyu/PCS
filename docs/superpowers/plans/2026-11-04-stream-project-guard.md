# 物流面项目守卫补齐 + review-log 端点 实施计划（紧急批次）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把物流模块 17 个端点缺失的**项目级访问守卫**补齐（读面 + 写面），并新增一个**按项目守卫**的 `GET /streams/{id}/review-log` 端点，让设计师能读到**自己物流**的校核记录。

**Architecture:** 守卫统一落在端点层，复用仓里既有的 `check_record_access_or_404`（**404**，不泄露存在性）。批量端点因是「部分成功」语义，跨项目的条目**按「不存在」处理**（理由文案与真不存在**逐字相同**）⇒ 攻击者无法区分。测试侧新增 `strict_client`（**不** mock 掉守卫）——现有 `client` fixture 把 `check_user_project_access` mock 成永远 True，**用它测不到任何守卫缺陷**。

**Tech Stack:** FastAPI · SQLAlchemy 2.x async · Pydantic v2 · pytest（asyncio_mode=auto）· React 19 + TS + antd 5 + vitest + MSW

**Spec:** `docs/PCS-UI-SPEC.md` §5.4（物流引用门禁）· §7.7.2（物流详情 7 Tab）· 本计划「裁决记录」节（用户 2026-11-04 裁决，原文照录）

---

## Global Constraints

- **分支 `main`，不要建 worktree**（历史事故：worktree 被删导致会话永久无法 Edit/Bash）。
- **conventional commits，**不带 attribution 行**；长消息写文件后 `git commit -F <file>`。
- ⚠️ **口令不要写在命令行**（会被权限分类器拦）——只在环境变量 / 进程内派生。
- ⚠️ **不要用 `git checkout <commit> --detach`** —— 会话里切 HEAD 有卡死风险。
- **守卫口径固定为 404**（`check_project_access_or_404` / `check_record_access_or_404`）——**不泄露「存在但无权」**。
- **每个 Task 一个 commit**；T5（review-log）**必须是独立 commit**（回滚粒度：112 的端点出问题**不能**连带回滚 17 个守卫）。
- 单测跑**内存 SQLite**（`tests/conftest.py` 用 `SA_Base.metadata.create_all`）⇒ **不改迁移** ⇒ 本批无 `alembic/versions/*` 变更 ⇒ 无迁移漂移风险。
- 契约：本批**新增一个端点 + 一个响应 schema** ⇒ 批末滚 OpenAPI baseline（`cp docs/openapi.json docs/openapi-baseline.json`）后再跑 `scripts/gate_08_openapi_contract.sh --check-baseline`。
- ⚠️ **裸载荷数不得上涨**（`check_openapi_payload_coverage.py` 基线 ≤ 71）⇒ 新端点用**具名 schema**，不用裸 dict。

---

## Review Focus

以下五类输入/情形**没有现成测试**，但最可能咬到真实用户；每条都已在对应 Task 里落成测试。

1. **「不存在」与「存在但跨项目」必须**完全同形**（都是 404 + 同文案）—— 否则攻击者能靠响应差异**枚举出某个 UUID 是否存在**。
2. **状态转移端点：守卫必须先于组成门禁** —— `POST /streams/{id}/submit` 现在先跑「组成合计 100±0.5%」校验（422 + **组成百分比**）再转移。若守卫在后，跨项目用户能拿到「该物流组成合计 87.3%」这种**数据泄露**（422 ≠ 404 ⇒ 存在性已暴露）。
3. **批量端点：跨项目条目混在合法条目里** —— 合法的那些**照常提交成功**，跨项目的那条**必须报告为失败**，且**失败理由与「不存在」逐字相同**（不能用 403 / 专门的错误码区分）。
4. **状态点端点**：状态点**没有** `project_id`（只有 `stream_id`）⇒ 守卫必须**经物流解析** —— 一个属于跨项目物流的状态点，`GET/PATCH/DELETE /state-points/{id}` 都要 404。
5. **血缘端点**：`record_type='streams'` 时守卫**结构性跳过**（`_guard_record_access` 对非 `PipingResult` 直接 `return`）⇒ 一个跨项目物流的血缘图**必须** 404。

---

## 裁决记录（用户 2026-11-04 · 原意照录）

**112 跟紧急批次一起做，但必须满足三个条件**：

- **条件 1**：112 必须是**独立 commit + 独立 Task**，不能和 113 的守卫混在一个 commit —— 紧急批次的核心价值是**可回滚**；112 的端点出问题（过滤口径错 / 性能差）时，回滚不能连带把 17 个守卫一起回滚。
- **条件 2**：112 必须有**自己的测试**，不能靠「守卫测试顺带覆盖」—— 守卫测试证明「越权被拒（404）」，112 的测试必须证明「**有权限时能读到正确的记录**（200 + 正确的 transition 列表）」。两个测试**目标相反**；只写守卫测试的话，112 的端点可能永远返回空数组而测试仍然绿。
- **条件 3**：112 的端点**不能扩大范围** —— 只做「读 review-log」。**不加**导出（CSV/Excel）、**不加**管理员视角、**不加**时间范围筛选、**不加**分页。评审时有人说「顺手加个 X」⇒ 拒绝。

**测试基建：方案 B（新旧并存）** —— 现有测试**全部保留旧 `client`**（不迁移）；新增 `strict_client` 仅用于守卫测试与 112 测试；「全测试迁移」登记为独立债项，**不拖住**本批。

**104（校核记录后端过滤）：设计并入 112，索引延后** —— 112 的端点内做**后端过滤**（最小暴露原则：只返回 review 相关的三条，不返回全部 `RECORD_TRANSITION`）；**不加索引**（当前 `audit_logs` 里 `RECORD_TRANSITION` 0 行 ⇒ 加索引是投机性优化）⇒ 104 的描述改为「若生产出现性能问题，加 `detail_json->>'transition'` 表达式索引」，触发条件：生产性能问题，或该类行数 > 10 万。

⚠️ **104 的索引理由已按实测修正**（2026-11-04 探针）：表上**已有** `ix_audit_logs_detail_json_gin`（`jsonb_path_ops`）⇒ 但它只支持 `@>` / `@?` / `@@` ⇒ **`->>` 用不上它** ⇒ 而 `@>` 在**测试库 SQLite 上不可用**（`unrecognized token: "@"`）⇒ 统一查询只能用 `->>` ⇒ 真要优化得**另加**表达式索引。⇒ TODO-104 的准确表述是「**已有 GIN 索引覆盖不到本查询的写法**」，不是「表上没索引」。

**批量操作统一、Excel 列映射/模板库**：不做（前者是架构演进 —— 两套批量模型是两种业务语义；后者独立批次）。

---

## 事实基础（2026-11-04 实测，非推断）

### 越权是真的（探针实测，探针已删）

用户只有项目 A 权限、物流在项目 B 时：

| 请求 | 实测 | 应为 |
|---|---|---|
| `GET /streams/{B}` | **200**（读到完整详情） | 404 |
| `POST /streams/{B}/submit` | **200** —— 状态**真的变成 IN_APPROVAL** | 404 |
| `POST /streams/batch-submit`（含 B 的 id） | **207 succeeded** | 404 |
| `GET /lineage/streams/{B}/graph` | 404，但原因是「no lineage for record」，**不是权限拒绝** ⇒ 守卫结构性缺失 | — |

### 端点清单（`app/api/v1/streams.py` 19 个端点）

**已有项目守卫（3 个，不动）**：`POST /projects/{project_id}/streams`（创建）· `POST /projects/{project_id}/streams/validate` · `GET /projects/{project_id}/streams`（列表）

**缺守卫（16 个）**：

| # | 端点 | 行号 | 落点 |
|---|---|---|---|
| 1 | `GET /streams/{stream_id}` | 324 | T1 |
| 2 | `PATCH /streams/{stream_id}` | 339 | T1 |
| 3 | `DELETE /streams/{stream_id}` | 361 | T1 |
| 4 | `POST /streams/{stream_id}/state-points` | 391 | T1 |
| 5 | `GET /streams/{stream_id}/state-points` | 416 | T1 |
| 6 | `GET /state-points/{state_point_id}` | 431 | T1 |
| 7 | `PATCH /state-points/{state_point_id}` | 446 | T1 |
| 8 | `DELETE /state-points/{state_point_id}` | 468 | T1 |
| 9 | `POST /streams/{stream_id}/submit` | 532 | T2 |
| 10 | `POST /streams/{stream_id}/approve` | 572 | T2 |
| 11 | `POST /streams/{stream_id}/reject` | 588 | T2 |
| 12 | `POST /streams/{stream_id}/initiate-change` | 606 | T2 |
| 13 | `POST /streams/{stream_id}/pass-change` | 624 | T2 |
| 14 | `POST /streams/{stream_id}/mark-stale` | 641 | T2 |
| 15 | `GET /streams/{stream_id}/properties` | 672 | T1 |
| 16 | `POST /streams/{stream_id}/properties/estimate` | 700 | T1 |

**第 17 个**：`POST /streams/batch-submit`（`app/api/v1/stream_batch.py`）⇒ T3（TODO-118）。
**第 18 条路径**：`GET /lineage/{record_type}/{record_id}/{upstream,downstream,graph}` ⇒ T4（TODO-114）。

### 已排除的误报

- `app/api/v1/stream_symbols.py` 的 9 个无守卫端点 ⇒ `StreamSymbol` 表**没有** `project_id`（全局符号库）⇒ 无守卫是**对的**，不动。
- `GET /projects/{project_id}/streams`（列表）**已有**守卫 ⇒ 列表侧没问题。

### 为什么这个洞活到今天（写进 cerebrum）

`tests/conftest.py` 的 `client` fixture 把 `UserProjectService.check_user_project_access` **mock 成永远 True** ⇒ **任何「端点缺项目守卫」的缺陷，单测都抓不到**；而前端 dev 跑 MSW mock、**根本不连真后端**。两个盲区叠加 ⇒ 洞一直没被看见。

---

## 文件结构

| 文件 | 责任 | 本批改动 |
|---|---|---|
| `pcs-backend/app/api/v1/streams.py` | 物流端点 | 新增 2 个守卫 helper；17 处端点接入 |
| `pcs-backend/app/api/v1/stream_batch.py` | 批量端点 | 传 `actor_roles` 给 service |
| `pcs-backend/app/services/stream_batch_service.py` | 批次 service | 新增逐条项目守卫（跨项目条目按「不存在」处理） |
| `pcs-backend/app/api/v1/lineage.py` | 血缘端点 | `_guard_record_access` 扩成**记录类型注册表** |
| `pcs-backend/app/schemas/stream_review_log.py` | **新建** | review-log 响应 schema（具名 ⇒ 裸载荷不涨） |
| `pcs-backend/app/services/stream_review_log_service.py` | **新建** | 读 audit_logs + 后端过滤 + 排序 |
| `pcs-backend/app/api/v1/streams.py`（T5 追加） | 端点 | `GET /streams/{id}/review-log` |
| `pcs-backend/tests/conftest.py` | 测试基建 | 新增 `strict_client` + `grant_project` fixture |
| `pcs-backend/tests/api/v1/test_stream_project_guard.py` | **新建** | 17 个端点的越权回归测试（T1~T3 共用） |
| `pcs-backend/tests/api/v1/test_stream_review_log.py` | **新建** | 112 的正向测试（条件 2：证明**能读到**，不只是 404） |
| `pcs-backend/tests/api/v1/test_lineage_guard.py` | **新建** | 血缘守卫（114） |
| `pcs-frontend/src/api/stream.ts` | 前端 API | 新增 `fetchReviewLog` |
| `pcs-frontend/src/pages/sim/tabs/StreamReviewLogTab.tsx` | 前端 Tab | 改调新端点（不再调 `/audit-logs`） |

---

## Task T0：`strict_client` 测试基建

**Files:**
- Modify: `pcs-backend/tests/conftest.py`（在现有 `client` fixture **之后**追加）
- Test: `pcs-backend/tests/api/v1/test_strict_client_fixture.py`（**新建**，证明 fixture 本身有效）

**Interfaces:**
- Consumes: 现有 `db_engine` / `db_session` fixture；`app.services.user_project_service.UserProjectService.grant_project_access(session, *, user_id, project_id, role_in_project)`
- Produces:
  - `strict_client` fixture → `httpx.AsyncClient`（**不** mock `check_user_project_access`）
  - `grant_project` fixture → `async (user_id: uuid.UUID, project_id: uuid.UUID, role_in_project: str = "DESIGNER") -> None`（往库里写 `UserProject` 行）

- [ ] **Step 1: 写失败的测试 —— 证明 `strict_client` 真的走真实守卫**

`pcs-backend/tests/api/v1/test_strict_client_fixture.py`：

```python
async def test_strict_client_rejects_a_user_without_project_grant(
    strict_client, db_session, designer_headers
):
    """strict_client 不 mock 守卫 ⇒ 无授权行的用户 ⇒ 404（不是 200）。"""
    from app.models.project import Project, Workspace
    # 建一个项目（无授权行）
    ...
    r = await strict_client.get(
        f"/api/v1/projects/{proj.project_id}/streams", headers=designer_headers
    )
    assert r.status_code == 404
```

同时加一个对照测试，证明**旧的** `client` 在同样条件下**返回 200**（⇒ 把「两套 client 的差别」钉成事实，防后人误以为 `client` 也严格）：

```python
async def test_legacy_client_bypasses_the_guard(client, ...):
    """⚠️ 旧 client 把守卫 mock 成永远 True ⇒ 同条件下 200。
    这条测试是**故意**记录一个缺陷（守卫缺陷测不出来）—— 别删。"""
    assert r.status_code == 200
```

- [ ] **Step 2: 跑测试确认它**失败**（`strict_client` 还不存在 ⇒ fixture not found）**

Run: `cd pcs-backend && uv run pytest tests/api/v1/test_strict_client_fixture.py -q`
Expected: FAIL —— `fixture 'strict_client' not found`

- [ ] **Step 3: 实现 `strict_client` 与 `grant_project`**

在 `pcs-backend/tests/conftest.py` 里，**紧跟**现有 `client` fixture 之后追加（**不要**改现有 `client`）：

```python
@pytest_asyncio.fixture
async def strict_client(db_engine) -> AsyncIterator[AsyncClient]:
    """**严格**测试 client —— **不** mock 项目守卫，走真实的
    `check_user_project_access`。

    ⚠️ **用它测不到守卫缺陷** ⇒ 守卫测试请用 strict_client。

    用它时**必须先造 `UserProject` 授权行**（用 `grant_project` fixture），
    否则所有带项目守卫的请求都 404 —— 这不是 bug，是你没授权。

    用途：
    - 守卫测试（证明跨项目越权被拒 → 404）
    - review-log 端点测试（证明有权限时能读到 → 200 + 正确内容）
    """
    # ⚠️ **故意不 patch** `check_user_project_access` —— 这正是它与 `client`
    #   的唯一区别。改这里之前先想清楚：你要测的是守卫还是业务。
    factory = async_sessionmaker(db_engine, expire_on_commit=False)

    async def _override_get_db() -> AsyncIterator[AsyncSession]:
        async with factory() as session:
            yield session

    from fastapi import FastAPI
    from app.core.errors import install_exception_handlers
    app = FastAPI(title="PCS Test (strict)")
    install_exception_handlers(app)
    app.include_router(api_router)
    app.dependency_overrides[get_db] = _override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest_asyncio.fixture
async def grant_project(db_session: AsyncSession):
    """给某个 user 造一条 `UserProject` 授权行（strict_client 专用）。"""
    async def _grant(user_id, project_id, role_in_project="DESIGNER"):
        from app.services.user_project_service import UserProjectService
        await UserProjectService.grant_project_access(
            db_session,
            user_id=user_id,
            project_id=project_id,
            role_in_project=role_in_project,
        )
        await db_session.commit()

    return _grant
```

- [ ] **Step 4: 跑测试确认它**通过**

Run: `cd pcs-backend && uv run pytest tests/api/v1/test_strict_client_fixture.py -q`
Expected: PASS（2 passed）

- [ ] **Step 5: 提交**

```bash
git add pcs-backend/tests/conftest.py pcs-backend/tests/api/v1/test_strict_client_fixture.py
git commit -F <msgfile>   # 首行: test(T0): strict_client 测试基建 —— 不 mock 项目守卫的客户端
```

---

## Task T1：物流读/写端点的项目守卫（10 个）

**Files:**
- Modify: `pcs-backend/app/api/v1/streams.py`（加 2 个 helper；接入 10 个端点）
- Test: `pcs-backend/tests/api/v1/test_stream_project_guard.py`（**新建**）

**Interfaces:**
- Consumes: `app.api.v1._guard.check_record_access_or_404(db, *, user_id, record, actor_roles)`（已存在）
- Produces:
  - `async def _load_stream_guarded(db: AsyncSession, stream_id: uuid.UUID, user: _Actor) -> Stream` —— 加载物流 + 项目守卫；不存在或无权**都**抛 404
  - `async def _load_state_point_guarded(db: AsyncSession, state_point_id: uuid.UUID, user: _Actor) -> tuple[StreamStatePoint, Stream]` —— 加载状态点 + **经其 `stream_id` 解析**物流 + 项目守卫

- [ ] **Step 1: 写失败的测试**

`pcs-backend/tests/api/v1/test_stream_project_guard.py`（**新建**）。用 `strict_client` + `grant_project`：建项目 A（已授权）与项目 B（**未授权**），在 B 里建一条物流，然后逐个断言 404。

```python
@pytest_asyncio.fixture
async def two_projects(db_session):
    """项目 A（用户已授权）+ 项目 B（用户**未**授权）。"""

@pytest_asyncio.fixture
async def stream_in_project_b(client, db_session, two_projects, designer_headers):
    """在项目 B 里建一条物流（建的时候守卫被 client fixture bypass 掉了）。"""

# —— 守卫测试：跨项目访问一律 404 ——
async def test_get_stream_in_another_project_is_404(strict_client, ...):
    assert (await strict_client.get(f"/api/v1/streams/{sid}", headers=designer_headers)).status_code == 404

async def test_patch_stream_in_another_project_is_404(strict_client, ...):
    ...  # PATCH /streams/{id}

async def test_delete_stream_in_another_project_is_404(strict_client, ...):
    ...  # DELETE /streams/{id}

async def test_list_state_points_of_another_project_is_404(strict_client, ...):
    ...  # GET /streams/{id}/state-points

async def test_create_state_point_in_another_project_is_404(strict_client, ...):
    ...  # POST /streams/{id}/state-points

async def test_get_state_point_of_another_project_is_404(strict_client, ...):
    ...  # GET /state-points/{id}  （Review Focus #4：经 stream_id 解析）

async def test_patch_state_point_of_another_project_is_404(strict_client, ...):
    ...

async def test_delete_state_point_of_another_project_is_404(strict_client, ...):
    ...

async def test_get_properties_of_another_project_is_404(strict_client, ...):
    ...  # GET /streams/{id}/properties

async def test_estimate_properties_of_another_project_is_404(strict_client, ...):
    ...  # POST /streams/{id}/properties/estimate

# —— 同形测试（Review Focus #1）——
async def test_not_found_and_cross_project_are_indistinguishable(strict_client, ...):
    """不存在 ⇒ 404；跨项目 ⇒ 404；**两条响应体的 code/message 必须逐字相同**。"""
    r_missing = await strict_client.get("/api/v1/streams/<随机 uuid>", headers=designer_headers)
    r_forbidden = await strict_client.get(f"/api/v1/streams/{sid}", headers=designer_headers)
    assert r_missing.status_code == r_forbidden.status_code == 404
    assert r_missing.json()["code"] == r_forbidden.json()["code"]
    assert r_missing.json()["message"] == r_forbidden.json()["message"]

# —— 正向测试：自己项目内的物流**照常工作**（守卫不能把正常路径也堵死）——
async def test_own_project_stream_is_fully_readable(strict_client, ...):
    assert (await strict_client.get(f"/api/v1/streams/{own_sid}", headers=designer_headers)).status_code == 200
```

⚠️ **状态点端点的正向测试也要有**（在项目 B 里建状态点 ⇒ 用 B 的授权身份访问 ⇒ 200）—— 否则一个「永远 404」的守卫也能让 404 测试全绿。

- [ ] **Step 2: 跑测试确认它们**失败**（现在是 200）**

Run: `cd pcs-backend && uv run pytest tests/api/v1/test_stream_project_guard.py -q`
Expected: FAIL —— 跨项目请求返回 **200**（不是 404）

- [ ] **Step 3: 实现两个 helper**

在 `pcs-backend/app/api/v1/streams.py` 的「Endpoints」分节**之前**加：

```python
async def _load_stream_guarded(
    db: AsyncSession, stream_id: uuid.UUID, user: _Actor
) -> Stream:
    """加载物流 + **项目守卫**（无权 404）。

    ⚠️ **404 = 不存在 + 无权**（两者同形）⇒ 攻击者无法靠响应差异
    枚举出某个 UUID 是否存在（`check_record_access_or_404` 的既定口径）。
    ⚠️ 用 `db.get`（**不加锁**）—— 守卫只读项目归属；
    真正要加锁的写路径由 `StreamService.transition` 内部的
    `SELECT ... FOR UPDATE`（`populate_existing=True`）负责。
    """
    stream = await db.get(Stream, stream_id)
    if stream is None:
        raise PcsError(
            f"物流 {stream_id} 不存在",
            code="SIM_STREAM_NOT_FOUND",
            status=404,
        )
    await check_record_access_or_404(
        db, user_id=user.user_id, record=stream, actor_roles=user.roles
    )
    return stream


async def _load_state_point_guarded(
    db: AsyncSession, state_point_id: uuid.UUID, user: _Actor
) -> tuple[StreamStatePoint, Stream]:
    """加载状态点 + **经其 `stream_id` 解析**物流 + 项目守卫。

    ⚠️ 状态点表**没有** `project_id`（只有 `stream_id` FK）⇒ 守卫只能
    绕道物流拿项目归属。
    """
    sp = await StreamService.get_state_point(db, state_point_id)
    stream = await _load_stream_guarded(db, sp.stream_id, user)
    return sp, stream
```

同时在文件顶部补 import：`from app.api.v1._guard import check_record_access_or_404`（已有 `check_project_access_or_404` 的 import 行，合并即可）。

- [ ] **Step 4: 接入 10 个端点**

逐个改（行号是改动前的，实施时以函数名为准）：

| 端点 | 改法 |
|---|---|
| `get_stream`（324） | `stream = await _load_stream_guarded(db, stream_id, user)`，替掉 `StreamService.get` + `except PcsError → _to_http` 那段 |
| `update_stream`（339） | 同上，在 service 调用**之前** |
| `delete_stream`（361） | 同上 |
| `create_state_point`（391） | `await _load_stream_guarded(db, stream_id, user)` 放在 `StreamService.create_state_point` **之前** |
| `list_state_points`（416） | 同上 |
| `get_state_point`（431） | `sp, _stream = await _load_state_point_guarded(db, state_point_id, user)`，替掉 `StreamService.get_state_point` |
| `update_state_point`（446） | 同上 |
| `delete_state_point`（468） | 同上 |
| `get_properties`（672） | `await _load_stream_guarded(db, stream_id, user)` |
| `estimate_properties`（700） | 同上 |

⚠️ 守卫抛的是 `HTTPException`（`check_record_access_or_404` 内部）⇒ **不要**用 `_to_http` 包它；`PcsError`（物流不存在）仍走原有的 `except PcsError: raise _to_http(e)` 路径。

- [ ] **Step 5: 跑测试确认**通过**

Run: `cd pcs-backend && uv run pytest tests/api/v1/test_stream_project_guard.py -q`
Expected: PASS（全部）

- [ ] **Step 6: 跑回归**

Run: `cd pcs-backend && uv run pytest tests/api/v1/ -q`
Expected: PASS —— ⚠️ 既有测试若**依赖**跨项目访问（用旧 `client` fixture 的**全部**测试都 bypass 守卫）⇒ 不受影响；若某个测试**真的**撞上了守卫（说明它之前依赖了越权），**改测试**（给它加 `grant_project`），**不要**改守卫。

- [ ] **Step 7: 提交**

```bash
git add pcs-backend/app/api/v1/streams.py pcs-backend/tests/api/v1/test_stream_project_guard.py
git commit -F <msgfile>   # 首行: fix(T1): 物流读/写端点补项目守卫（10 个端点，越权一律 404）
```

---

## Task T2：状态转移端点的项目守卫（6 个）

**Files:**
- Modify: `pcs-backend/app/api/v1/streams.py`（`_transition_endpoint` 加守卫 + `precheck` 参数；`submit_stream` 把组成门禁改成 precheck 回调）
- Test: `pcs-backend/tests/api/v1/test_stream_project_guard.py`（**追加**用例）

**Interfaces:**
- Consumes: T1 产出的 `_load_stream_guarded`
- Produces:
  - `_transition_endpoint(stream_id, event, user, db, reason, *, precheck: Callable[[Stream], Awaitable[None]] | None = None) -> dict[str, Any]` —— **先守卫（404）→ 再 precheck（422）→ 最后转移**

- [ ] **Step 1: 写失败的测试**（追加到 `test_stream_project_guard.py`）

```python
# —— 6 个状态转移端点：跨项目一律 404 ——
@pytest.mark.parametrize(
    "path",
    [
        "/submit", "/approve", "/reject",
        "/initiate-change", "/pass-change", "/mark-stale",
    ],
)
async def test_state_transition_in_another_project_is_404(strict_client, ..., path):
    r = await strict_client.post(f"/api/v1/streams/{sid}{path}", json={}, headers=designer_headers)
    assert r.status_code == 404

# —— Review Focus #2：守卫必须**先于**组成门禁 ——
async def test_cross_project_submit_leaks_no_composition_detail(strict_client, ...):
    """跨项目 submit ⇒ 404（**不是** 422「组成合计 87.3%」）——
    422 会暴露「这条物流存在」+「它的组成不合法」。"""
    r = await strict_client.post(f"/api/v1/streams/{sid}/submit", json={}, headers=designer_headers)
    assert r.status_code == 404
    assert "组成" not in r.text

# —— 状态**没被改**（守卫失败 ⇒ 绝不留下半成品）——
async def test_cross_project_submit_does_not_change_status(strict_client, db_session, ...):
    ...  # 查库：sign_status 仍是 DRAFT
```

⚠️ 构造「组成不合法」的物流：建物流时 `composition_json={"CAS": 0.5}`（合计 50% ⇒ 非法）⇒ 修复前该请求会返回 **422**（暴露组成百分比）⇒ 修复后 **404**。

- [ ] **Step 2: 跑测试确认它们**失败**

Run: `cd pcs-backend && uv run pytest tests/api/v1/test_stream_project_guard.py -q -k "transition or cross_project_submit"`
Expected: FAIL —— 返回 **200**（跨项目提交**成功**了）

- [ ] **Step 3: 给 `_transition_endpoint` 加守卫 + `precheck` 参数**

`pcs-backend/app/api/v1/streams.py`：

```python
async def _transition_endpoint(
    stream_id: uuid.UUID,
    event: StateTransition,
    user: _Actor,
    db: AsyncSession,
    reason: str | None,
    *,
    precheck: Callable[[Stream], Awaitable[None]] | None = None,
) -> dict[str, Any]:
    """6 状态机端点共用 helper：**项目守卫（404）→ precheck（422）→ 转移**。

    ⚠️ **顺序不可换**：
    - 守卫在前 ⇒ 跨项目用户只会拿到 **404**，**看不到**任何业务细节
      （组成百分比、当前状态……）⇒ 那些细节本身就是信息泄露。
    - precheck 在守卫之后、转移之前 ⇒ 非法组成**不会**留下
      「已进校对」的半成品。
    """
    stream = await _load_stream_guarded(db, stream_id, user)   # ① 404
    if precheck is not None:
        await precheck(stream)                                  # ② 422
    try:
        stream = await StreamService.transition(
            db, stream_id,
            transition=event,
            actor_user_id=user.user_id,
            actor_role=user.role,
            reason=reason,
        )
    except PcsError as e:
        raise _to_http(e) from e
    return { ... }   # 原样保留
```

- [ ] **Step 4: 把 `submit_stream` 的组成门禁改成 precheck 回调**

现状：`submit_stream` 里先 `db.get(Stream, ...)` 再跑组成校验，然后调 `_transition_endpoint`。改成：

```python
async def _composition_gate(stream: Stream) -> None:
    """组成合计门禁 —— 100±0.5%（SPEC §7.7.2）。

    ⚠️ `None` = 无组成（纯物质）⇒ **跳过**；`{}` = 未填写 ⇒ **拒绝**。
    """
    composition = stream.composition_json
    if composition is None:
        return
    total = composition_mole_fraction_total(stream)
    if total is None or abs(total - 1.0) > 0.005:
        raise CorePcsError(
            code="SIM_STREAM_COMPOSITION_OUT_OF_RANGE",
            message=(
                f"物流 {stream.stream_id} 的组成摩尔分率合计 {total * 100:.2f}%，"
                "不在 100±0.5% 内 ⇒ 不能提交校对"
            ),
            status=422,
        )
```

`submit_stream` 的函数体退化成：

```python
    require_roles(user, "DESIGNER", "PROCESS_CONTROLLER", "SYSTEM_ADMIN")
    return await _transition_endpoint(
        stream_id, StateTransition.SUBMIT_FOR_CHECK, user, db, reason=None,
        precheck=_composition_gate,
    )
```

⚠️ 补 import：`from collections.abc import Awaitable, Callable`。

- [ ] **Step 5: 跑测试确认**通过**

Run: `cd pcs-backend && uv run pytest tests/api/v1/test_stream_project_guard.py -q`
Expected: PASS

- [ ] **Step 6: 跑回归**（状态机相关）

Run: `cd pcs-backend && uv run pytest tests/api/v1/test_streams_state_machine_api.py tests/api/v1/test_stream_composition_sum.py tests/services/ -q`
Expected: PASS —— ⚠️ `test_stream_composition_sum.py` 的门禁断言（422 + 文案）**必须仍然绿** ⇒ 门禁只是挪了位置，没被删掉。

- [ ] **Step 7: 提交**

```bash
git add pcs-backend/app/api/v1/streams.py pcs-backend/tests/api/v1/test_stream_project_guard.py
git commit -F <msgfile>   # 首行: fix(T2): 状态转移端点补项目守卫（6 个）—— 守卫先于组成门禁
```

---

## Task T3：批量端点的项目守卫（TODO-118）

**Files:**
- Modify: `pcs-backend/app/api/v1/stream_batch.py`（传 `actor_roles`）
- Modify: `pcs-backend/app/services/stream_batch_service.py`（逐条守卫）
- Test: `pcs-backend/tests/api/v1/test_stream_project_guard.py`（**追加**用例）

**Interfaces:**
- Consumes: `UserProjectService.check_user_project_access(session, *, user_id, project_id) -> bool`
- Produces: `submit_batch(db, stream_ids, *, actor_user_id, actor_role, actor_roles: list[str] | None = None, dry_run=False, limit=None)` —— 新增**可选**参数 `actor_roles`（默认 `None` ⇒ 退化为只看 `actor_role`），供 SYSTEM_ADMIN bypass 用

- [ ] **Step 1: 写失败的测试**（追加到 `test_stream_project_guard.py`）

```python
# —— Review Focus #3：跨项目条目混在合法条目里 ——
async def test_batch_submit_skips_cross_project_stream_as_not_found(strict_client, ...):
    """跨项目的那条 ⇒ 报告为失败，且**理由与「不存在」逐字相同**；
    自己项目的那条 ⇒ 照常成功。"""
    r = await strict_client.post(
        "/api/v1/streams/batch-submit",
        json={"stream_ids": [own_sid, foreign_sid]},
        headers=designer_headers,
    )
    assert r.status_code == 207
    body = r.json()
    assert [s["stream_id"] for s in body["succeeded"]] == [own_sid]
    assert len(body["failed"]) == 1
    assert body["failed"][0]["stream_id"] == foreign_sid
    assert body["failed"][0]["reason"] == "SIM_STREAM_NOT_FOUND"   # ← 与「不存在」同一码

async def test_batch_submit_of_only_foreign_stream_looks_identical_to_missing(strict_client, ...):
    """全是跨项目 ⇒ 与全是随机 uuid **同形**（都是 207 + 全 failed / NOT_FOUND）。"""
```

⚠️ **为什么用 `SIM_STREAM_NOT_FOUND` 而不是 403**：403 与 404 的差别**就是存在性** ⇒ 攻击者据此枚举。判定为「不存在」⇒ 与真不存在**逐字同形** ⇒ 无泄露。（代价：用户分不清「打错 id」与「不是我的」，但那正是 404 语义该给的信息。）

- [ ] **Step 2: 跑测试确认它们**失败**

Run: `cd pcs-backend && uv run pytest tests/api/v1/test_stream_project_guard.py -q -k batch`
Expected: FAIL —— 跨项目那条进了 `succeeded`

- [ ] **Step 3: service 端加逐条守卫**

`pcs-backend/app/services/stream_batch_service.py`：在 `_submit_one_inner` 里，**加载物流之后、任何写之前**，加一道项目归属判定。

- 新增模块级 helper：

```python
async def _accessible(
    db: AsyncSession, stream: Stream, *, user_id: uuid.UUID, actor_roles: list[str] | None
) -> bool:
    """该 actor 能否访问这条物流所属项目。

    ⚠️ SYSTEM_ADMIN 全局 bypass（与 `check_project_access_or_404` 同口径）。
    ⚠️ **不做「无权」与「不存在」的区分** —— 调用方把「无权」当「不存在」
    处理（理由码逐字相同）⇒ 攻击者无法枚举 UUID 是否存在。
    """
    if actor_roles and "SYSTEM_ADMIN" in actor_roles:
        return True
    return await UserProjectService.check_user_project_access(
        db, user_id=user_id, project_id=stream.project_id
    )
```

- `_submit_one_inner` 里，拿到 stream 之后：

```python
    if not await _accessible(db, stream, user_id=actor_user_id, actor_roles=actor_roles):
        # ⚠️ **当成「不存在」**（与真不存在同形）⇒ 不泄露存在性
        return BatchFailedItem(
            status="failed",
            stream_id=stream_id,
            reason="SIM_STREAM_NOT_FOUND",
            detail=None,
        )
```

- `submit_batch` 签名加 `actor_roles: list[str] | None = None`，并**逐层传下去**到 `_submit_one_inner`。
- `app/api/v1/stream_batch.py`：`submit_batch(db, req.stream_ids, actor_user_id=user.user_id, actor_role=user.role, actor_roles=list(user.roles), dry_run=req.dry_run)`。

- [ ] **Step 4: 跑测试确认**通过**

Run: `cd pcs-backend && uv run pytest tests/api/v1/test_stream_project_guard.py -q -k batch`
Expected: PASS

- [ ] **Step 5: 跑回归**（批次 service 的既有 32 个测试）

Run: `cd pcs-backend && uv run pytest tests/services/test_stream_batch_service.py tests/api/v1/test_stream_batch_submit.py -q`
Expected: PASS（32 + 9）

- [ ] **Step 6: 提交**

```bash
git add pcs-backend/app/api/v1/stream_batch.py pcs-backend/app/services/stream_batch_service.py pcs-backend/tests/api/v1/test_stream_project_guard.py
git commit -F <msgfile>   # 首行: fix(T3): 批量端点补项目守卫（TODO-118）—— 跨项目条目按「不存在」处理
```

---

## Task T4：血缘端点的守卫注册表（TODO-114）

**Files:**
- Modify: `pcs-backend/app/api/v1/lineage.py`（`_guard_record_access` 扩成注册表）
- Test: `pcs-backend/tests/api/v1/test_lineage_guard.py`（**新建**）

**Interfaces:**
- Consumes: `check_record_access_or_404`
- Produces: 模块级常量 `LINEAGE_GUARDED_RECORD_TYPES: dict[str, type]` —— 记录类型 → ORM 模型（**有 `project_id` 的**才登记）

- [ ] **Step 1: 写失败的测试**

`pcs-backend/tests/api/v1/test_lineage_guard.py`（**新建**）：

```python
async def test_lineage_graph_of_another_project_stream_is_404(strict_client, ...):
    """`record_type='streams'` ⇒ 跨项目物流的血缘图 404。"""

async def test_lineage_upstream_of_another_project_stream_is_404(strict_client, ...):
    ...

async def test_lineage_downstream_of_another_project_stream_is_404(strict_client, ...):
    ...
```

⚠️ 端点是 `GET /api/v1/lineage/{record_type}/{record_id}/graph`（router 前缀见 `lineage.py` 顶部）。

- [ ] **Step 2: 跑测试确认**失败**

Run: `cd pcs-backend && uv run pytest tests/api/v1/test_lineage_guard.py -q`
Expected: FAIL —— 返回 **200**（或 404 但原因是「no lineage for record」，**不是**权限拒绝）⇒ 断言要检查**原因**：守卫修好后，未授权 ⇒ 「Project not found」；未授权**且**有血缘 ⇒ 也是「Project not found」。测试断言 `r.json()["message"].startswith("Project not found")` 之类 ⇒ 区分「权限拒绝」与「没有血缘」。

- [ ] **Step 3: 实现注册表**

`pcs-backend/app/api/v1/lineage.py`：

```python
#: 需要项目守卫的记录类型 → ORM 模型（**必须带 project_id**）。
#:
#: ⚠️ **以前这里是 `if record_type != "PipingResult": return`** ⇒ 任何其它
#: 记录类型（`streams` …）**完全跳过**访问校验（TODO-114）⇒ 改成**注册表**
#: ⇒ 加一种记录类型只要**登记一行**，不会再漏。
LINEAGE_GUARDED_RECORD_TYPES: dict[str, Any] = {
    "PipingResult": PipingResult,   # 管道结果
    "streams": Stream,               # 物流（P9B-3 的血缘 Tab 首次用到）
}
```

`_guard_record_access` 改成：

```python
async def _guard_record_access(session, user, record_type, record_id) -> None:
    """按记录类型注册表做项目鉴权（无权 404）。

    ⚠️ **不在注册表里的记录类型 ⇒ 跳过**（沿用旧行为：`PipingResult` 之外的
    类型此前就是跳过的）⇒ 但**新增记录类型必须登记**，否则又是同一个洞。
    """
    model = LINEAGE_GUARDED_RECORD_TYPES.get(record_type)
    if model is None:
        return
    ...
```

⚠️ `PipingResult` 的主键是 `pipe_id`（不是 `record_id`）—— 沿用现有查询逻辑（`PipingResult.pipe_id == record_id`），而 `Stream` 用 `Stream.stream_id == record_id` ⇒ 注册表要带上**主键列名**：

```python
LINEAGE_GUARDED_RECORD_TYPES: dict[str, tuple[type, str]] = {
    # 记录类型 → (ORM 模型, 主键列名)
    "PipingResult": (PipingResult, "pipe_id"),
    "streams": (Stream, "stream_id"),
}
```

- [ ] **Step 4: 跑测试确认**通过**

Run: `cd pcs-backend && uv run pytest tests/api/v1/test_lineage_guard.py tests/test_lineage_api.py tests/test_lineage.py -q`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add pcs-backend/app/api/v1/lineage.py pcs-backend/tests/api/v1/test_lineage_guard.py
git commit -F <msgfile>   # 首行: fix(T4): 血缘守卫扩成记录类型注册表（TODO-114）—— streams 不再跳过
```

---

## Task T5：`GET /streams/{id}/review-log` 端点（TODO-112 · 独立 commit）

> ⚠️ **裁决条件 1**：本 Task 必须是**独立 commit** —— 它的端点出问题（过滤口径错 / 性能差）时，回滚**不能**连带把 T1~T4 的 18 个守卫一起回滚。
> ⚠️ **裁决条件 2**：本 Task 的测试文件**独立**（`test_stream_review_log.py`），且必须包含**正向**测试（200 + 正确内容），不能只有 404。
> ⚠️ **裁决条件 3**：端点**只做读 review-log** —— 不加导出、不加管理员视角、不加时间筛选、不加分页。

**Files:**
- Create: `pcs-backend/app/schemas/stream_review_log.py`
- Create: `pcs-backend/app/services/stream_review_log_service.py`
- Modify: `pcs-backend/app/api/v1/streams.py`（追加端点 + 注册 router —— `streams.py` 的 router 已在 `app/api/v1/__init__.py` 注册 ⇒ 无需改 `__init__.py`）
- Modify: `pcs-frontend/src/api/stream.ts`（新增 `fetchReviewLog`）
- Modify: `pcs-frontend/src/pages/sim/tabs/StreamReviewLogTab.tsx`（改调新端点）
- Test: `pcs-backend/tests/api/v1/test_stream_review_log.py`（**新建**）
- Test: `pcs-frontend/tests/pages/sim/tabs/StreamReviewLogTab.test.tsx`（**新建或改**）

**Interfaces:**
- Consumes: `app.models.system.AuditLog`（`resource_type` / `resource_id` / `action` / `detail_json` / `occurred_at` / `user_id`）
- Produces:
  - `GET /api/v1/streams/{stream_id}/review-log` → `list[ReviewLogItem]`
  - `ReviewLogItem` schema：`transition: str` · `operator: str | None` · `occurred_at: str` · `detail: str | None`
  - `app.services.stream_review_log_service.list_review_log(db, *, stream_id, actor_user_id, actor_roles) -> list[ReviewLogItem]`

- [ ] **Step 1: 写失败的测试（后端 · 正向 + 负向）**

`pcs-backend/tests/api/v1/test_stream_review_log.py`（**新建**）：

```python
# —— 正向（条件 2：证明「有权限时能读到正确的记录」）——
async def test_review_log_returns_only_review_transitions(strict_client, ...):
    """只返回 SUBMIT_FOR_CHECK / PASS_CHECK / REJECT_CHECK 三条，
    **不含**其它状态转移（如 INITIATE_CHANGE）—— 最小暴露原则。"""

async def test_review_log_is_sorted_by_occurred_at_asc(strict_client, ...):
    ...

async def test_review_log_of_a_stream_without_transitions_is_empty_list(strict_client, ...):
    """无校核记录 ⇒ **200 + []**（不是 404）—— 端点存在，只是没记录。"""

# —— 负向 ——
async def test_review_log_of_another_project_stream_is_404(strict_client, ...):
    ...

async def test_review_log_of_unknown_stream_is_404(strict_client, ...):
    ...
```

⚠️ 造审计行的方式：直接在库里写 `AuditLog` 行（`resource_type='streams'` / `resource_id=<sid>` / `action='RECORD_TRANSITION'` / `detail_json={'transition': 'SUBMIT_FOR_CHECK'}`）。⚠️ `AuditLog` 表**没有** `project_id` ⇒ 守卫只能**经物流**（`check_record_access_or_404`）⇒ 这正是端点必须先加载物流再查审计的原因。

- [ ] **Step 2: 跑测试确认**失败**（端点不存在 ⇒ 404/405）**

Run: `cd pcs-backend && uv run pytest tests/api/v1/test_stream_review_log.py -q`
Expected: FAIL —— 404（路由不存在）

- [ ] **Step 3: 写 schema（具名 ⇒ 裸载荷不涨）**

`pcs-backend/app/schemas/stream_review_log.py`（**新建**）：

```python
"""物流「校核记录」的响应契约（TODO-112）。

⚠️ **具名 schema** —— 不是裸 dict ⇒ 前端类型可契约派生，
且 `check_openapi_payload_coverage.py` 的裸载荷数**不涨**。
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class ReviewLogItem(BaseModel):
    """一条校核记录（一次校对相关状态转移）。"""

    transition: str = Field(
        description="状态转移名：SUBMIT_FOR_CHECK / PASS_CHECK / REJECT_CHECK"
    )
    operator: str | None = Field(
        default=None, description="操作人 user_id（审计里的 actor）"
    )
    occurred_at: str = Field(description="发生时间（ISO 8601）")
    detail: str | None = Field(default=None, description="附加说明（如驳回理由）")
```

- [ ] **Step 4: 写 service（后端过滤 + 升序）**

`pcs-backend/app/services/stream_review_log_service.py`（**新建**）：

```python
"""读物流的「校核记录」（TODO-112）。

⚠️ **后端过滤**（最小暴露原则）：只返回
`SUBMIT_FOR_CHECK` / `PASS_CHECK` / `REJECT_CHECK` 三条 ⇒
前端拿到什么就显示什么 ⇒ 过滤逻辑只有**一处**、可测。

⚠️ **不加索引**（TODO-104 的结论）：`audit_logs` 里 `RECORD_TRANSITION`
当前 0 行 ⇒ 加 `detail_json->>'transition'` 表达式索引是**投机性优化**
⇒ 等生产出现性能问题（或该类行数 > 10 万）再补。
"""

REVIEW_TRANSITIONS = ("SUBMIT_FOR_CHECK", "PASS_CHECK", "REJECT_CHECK")


async def list_review_log(
    db: AsyncSession,
    *,
    stream_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    actor_roles: list[str] | None = None,
) -> list[ReviewLogItem]:
    """读一条物流的校核记录（**按 occurred_at 升序**）。

    ⚠️ **项目守卫在端点层**（先加载物流再守卫）—— 本函数**假定**调用方
    已完成守卫 ⇒ 不要在别处直接调它。
    """
```

SQL（**一次**往返，不要 N+1）：

```python
    rows = (
        await db.execute(
            select(AuditLog)
            .where(
                AuditLog.resource_type == "streams",
                AuditLog.resource_id == str(stream_id),   # ⚠️ resource_id 是 **String(100)** 列！
                AuditLog.action == "RECORD_TRANSITION",
                AuditLog.detail_json["transition"].as_string().in_(REVIEW_TRANSITIONS),
            )
            .order_by(AuditLog.occurred_at.asc(), AuditLog.audit_id.asc())
        )
    ).scalars().all()
```

⚠️ **三处实测钉死的细节**（2026-11-04 在 SQLite 上探针验证）：

1. ⚠️ **`resource_id` 是 `String(100)`**（不是 UUID 列）⇒ 比较要用 `str(stream_id)`，写 `stream_id`（UUID）**匹配不到任何行**。
2. ⚠️ **JSONB 取值写法**：`as_string()` ✅ 与 `astext` ✅ 在 SQLite 上都能跑；**`contains()`（`@>`）❌ 在 SQLite 上直接报** `unrecognized token: "@"` ⇒ **不能**用 `@>`（虽然它是 PG 上唯一能吃到已有 GIN 索引的写法）。⇒ 统一用 **`as_string()`**（PG 上编译成 `CAST(detail_json ->> 'transition' AS VARCHAR)`）。
3. ⚠️ **索引**：表上**已有** `ix_audit_logs_detail_json_gin`（`jsonb_path_ops`）⇒ 但它只支持 `@>` / `@?` / `@@` ⇒ **`->>` 用不上它** ⇒ 真要优化得**另加**表达式索引（`detail_json->>'transition'`）⇒ 这正是 TODO-104「索引延后」的准确理由（**不是**「表上没索引」）。

⚠️ **`REVIEW_TRANSITIONS` 用 `in_()` 还是三次 `OR`**：用 `in_()`（一个 `IN` 列表）⇒ SQL 简洁、可读计划好；`as_string().in_(...)` 在 PG 上是 `CAST(... AS VARCHAR) IN (...)` ⇒ 走不了 GIN（本来也走不了）⇒ 无所谓。

- [ ] **Step 5: 加端点**

`pcs-backend/app/api/v1/streams.py` 追加：

```python
@router.get("/streams/{stream_id}/review-log", response_model=list[ReviewLogItem])
async def get_stream_review_log(
    stream_id: uuid.UUID,
    user: Annotated[_Actor, Depends(current_actor)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[ReviewLogItem]:
    """物流的校核记录（**只读**，TODO-112）。

    ⚠️ **为什么不用 `GET /audit-logs`**：那个端点限 SYSTEM_ADMIN
    （`audit_logs` 表**没有** `project_id` ⇒ 无法按项目守卫）⇒
    设计师打开这个 Tab 只看到「无权查看」—— **他看不到自己物流的校核经过**。

    ⚠️ **范围**：只返回三条校对相关转移；**不加**导出 / 管理员视角 /
    时间筛选 / 分页（裁决条件 3）。
    """
    require_roles(user, "DESIGNER", "PROCESS_CONTROLLER", "SYSTEM_ADMIN")
    await _load_stream_guarded(db, stream_id, user)   # 404
    return await list_review_log(
        db, stream_id=stream_id, actor_user_id=user.user_id, actor_roles=list(user.roles)
    )
```

- [ ] **Step 6: 跑测试确认**通过**

Run: `cd pcs-backend && uv run pytest tests/api/v1/test_stream_review_log.py -q`
Expected: PASS

- [ ] **Step 7: 前端改调新端点**

`pcs-frontend/src/api/stream.ts` 追加：

```ts
  /** 校核记录（**只读** · 契约派生）。 */
  fetchReviewLog: (streamId: string): Promise<ReviewLogItem[]> =>
    api.get<ReviewLogItem[]>(`/streams/${streamId}/review-log`).then((r) => r.data),
```

`pcs-frontend/src/pages/sim/tabs/StreamReviewLogTab.tsx`：
- 数据源从 `auditApi.listAuditLogs({resource_type:'streams', ...})` 改成 `streamApi.fetchReviewLog(streamId)`
- **删掉**前端过滤（`REVIEW_TRANSITIONS` / `transitionOf` / `reviewRows`）—— 过滤已在后端 ⇒ 前端**不得**再过滤一遍（两处过滤 = 两个口径 = 迟早漂移）
- 列改为：`transition`（用中文标签）· `operator` · `occurred_at`

- [ ] **Step 8: 前端测试**

`pcs-frontend/tests/pages/sim/tabs/StreamReviewLogTab.test.tsx`（新建或改）：
- 渲染三条校核记录（mock 端点）⇒ 表格出现 3 行
- mock 返回空数组 ⇒ 显示「（无校核记录）」
- mock 返回 404 ⇒ 显示错误条

- [ ] **Step 9: 跑前端全量 + typecheck + lint**

Run: `cd pcs-frontend && npm run typecheck && npm run lint && npm run test`
Expected: 全部绿；测试数 **≥ 上批 baseline**

- [ ] **Step 10: 提交（独立 commit · 条件 1）**

```bash
git add pcs-backend/app/schemas/stream_review_log.py pcs-backend/app/services/stream_review_log_service.py pcs-backend/app/api/v1/streams.py pcs-backend/tests/api/v1/test_stream_review_log.py pcs-frontend/src/api/stream.ts pcs-frontend/src/pages/sim/tabs/StreamReviewLogTab.tsx pcs-frontend/tests/pages/sim/tabs/StreamReviewLogTab.test.tsx
git commit -F <msgfile>   # 首行: feat(T5): 新增 GET /streams/{id}/review-log（TODO-112）—— 开口子，非修补
```

⚠️ commit message 正文**必须**写明「**新增端点：开口子，非修补**」—— 让 reviewer 知道这个 commit 与前面的守卫 commit **方向相反**（一个堵、一个开），回滚粒度独立。

---

## Task T6：契约 / 文档 / QA 收口

**Files:**
- Modify: `pcs-backend/docs/openapi.json`（重新生成）
- Modify: `pcs-backend/docs/openapi-baseline.json`（滚 baseline）
- Modify: `pcs-frontend/openapi.snapshot.json`（同步）
- Modify: `pcs-frontend/src/types/api.d.ts`（重新生成）
- Modify: `docs/PCS-UI-SPEC.md` §7.7.2（校核记录 Tab 的数据源说明）
- Modify: `TODOS.md`（TODO-112 / 113 / 114 / 118 / 104 的状态）
- Modify: `.wolf/buglog.json` + `.wolf/cerebrum.md`（账簿）

- [ ] **Step 1: 重新生成契约**

Run: `cd pcs-backend && uv run python scripts/export_openapi.py && cp docs/openapi.json docs/openapi-baseline.json && cd ../pcs-frontend && npm run gen:types`（若脚本名不同，看 `pcs-frontend/package.json` 的 scripts）
Expected: `openapi.json` 里出现 `GET /api/v1/streams/{stream_id}/review-log` 与 `ReviewLogItem` schema

- [ ] **Step 2: 跑契约闸门**

Run: `cd pcs-backend && uv run python scripts/check_openapi_payload_coverage.py && bash scripts/gate_08_openapi_contract.sh --check-baseline`
Expected: RC=0；裸载荷 **71**（未涨）

- [ ] **Step 3: 后端全量**

Run: `cd pcs-backend && uv run pytest -q`
Expected: **0 failed**（基线 5481 passed ⇒ 本批**净增**）

- [ ] **Step 4: PG 车道**

Run: `cd pcs-backend && bash scripts/pytest_pg.sh`
Expected: exit 0 且 `N passed`（N ≥ 1）

- [ ] **Step 5: 前端全量**

Run: `cd pcs-frontend && npm run typecheck && npm run lint && npm run test`
Expected: 全绿

- [ ] **Step 6: 浏览器回归**

用 `~/.claude/skills/gstack/browse/dist/browse`（`CI=1`）：
- 登录 → 物流一览 → 点进一条物流 → **校核记录 Tab** 渲染出记录（不再是「无权查看」）
- ⚠️ **用 SPA 菜单点击**导航（`page.goto` / `reload` 会清 zustand 内存态 ⇒ 弹回 `/login`）
- 控制台 0 error、0 key 警告；网络 0×404
- 报告落 `.gstack/qa-reports/qa-report-pcs-frontend-2026-11-04-stream-guard.md`（**gitignored**，只落本地）

- [ ] **Step 7: 更新 SPEC + TODOS + 账簿**

- `docs/PCS-UI-SPEC.md` §7.7.2：校核记录 Tab 的数据源从 `GET /audit-logs` 改成 `GET /streams/{id}/review-log`；记录「**后端过滤** + 索引延后（TODO-104）」
- `TODOS.md`：TODO-112 / 113 / 114 / 118 标 ✅ 已闭环；**TODO-104 改写**为「索引延后」（设计已并入 112）；**新增**一条「全测试迁移到 `strict_client`」的债项
- `.wolf/buglog.json`：新增 4 条（112 / 113 / 114 / 118），`fix_commit` 填各 Task 的 commit 短 SHA
- `.wolf/cerebrum.md` Do-Not-Repeat 新增：
  - 「**测试 client 把守卫 mock 成永远 True ⇒ 守卫缺陷单测抓不到**」⇒ 守卫测试必须用 `strict_client`
  - 「**404 ≠ 403** ⇒ 无权与不存在必须**同形**，否则可枚举 UUID」
  - 「**守卫要早于业务门禁** ⇒ 否则 422 的业务细节会泄露跨项目数据」

- [ ] **Step 8: 提交**

```bash
git add -A
git commit -F <msgfile>   # 首行: docs(T6): 契约滚动 + SPEC/TODOS/账簿同步 —— 物流面守卫补齐收口
```

---

## 验收

| 门 | 判据 |
|---|---|
| 守卫 | 18 个端点跨项目一律 **404**；与「不存在」**同形**（Review Focus #1） |
| 顺序 | 跨项目 `submit` ⇒ **404**（不是 422 组成百分比）；状态**未变** |
| 批量 | 跨项目条目按 `SIM_STREAM_NOT_FOUND` 处理；合法条目照常成功 |
| 状态点 | 经 `stream_id` 解析 ⇒ 跨项目状态点 404 |
| 血缘 | `record_type='streams'` ⇒ 跨项目 404 |
| review-log | 自己项目 ⇒ **200 + 只含三条校对转移 + 升序**；跨项目 ⇒ 404；无记录 ⇒ 200 + `[]` |
| 正向 | 自己项目内**所有**物流操作**照常工作**（守卫不能把正常路径堵死） |
| 后端全量 | `pytest -q` 0 failed（基线 5481 ⇒ 净增） |
| PG 车道 | `scripts/pytest_pg.sh` exit 0 且 `N passed` |
| 前端全量 | typecheck + lint + vitest 全绿（≥ 上批 baseline） |
| 契约 | G-08 `--check-baseline` 4/4；裸载荷 **71**（未涨） |
| 浏览器 | 校核记录 Tab **渲染出记录**；0 error / 0×404 |

---

## 尚未解决的问题（开工前需裁决或登记）

| # | 问题 | 现状 | 本批处置 |
|---|---|---|---|
| 1 | **生产库没有 `UserProject` 授权行怎么办** | `pcs` 开发库当前 **0 项目 / 0 用户 / 0 授权**；`UserProject` 行只由 `POST /user-projects`（管理员 API）创建 ⇒ 补守卫后，**没有任何授权行的用户会处处 404** | ⚠️ **本批不解决**（属运维/部署面）⇒ 但**必须在计划执行前**确认生产环境有授权行；否则补守卫 = 全站 404。**建议**：单独一条运维任务（启动时给默认项目 seed 一条授权，或在 README 写明「先建授权」）。**登记为 TODO** |
| 2 | `UserProject` 表**没有** `revoked_at` 之外的多项目语义问题 | `check_user_project_access` 支持多项目（按行查）⇒ 多项目用户天然可用 | 无需处置 |
| 3 | **其余模块**是否有同样的守卫缺口 | 本批**只**扫了物流面（`streams.py` / `stream_batch.py` / `lineage.py`）。其它模块（`config.py` 12 端点 0 守卫、`report_builder.py` 9 端点 0 守卫、`psychro.py` 13 端点 6 守卫……）**未审** | ⚠️ **本批不做** ⇒ 登记为独立技术债（「物流面之外的模块守卫覆盖审计」） |
| 4 | 设备引用（JSONB 数组 `feed_streams_json`）**不计入**引用数 | 见 P9B-4 计划的口径裁决 | 不在本批 |
| 5 | 「全测试迁移到 `strict_client`」 | 现有测试全部用旧 `client`（bypass 守卫）⇒ **仍然测不到守卫缺陷** | 按裁决**延后**，登记为独立债项 |
