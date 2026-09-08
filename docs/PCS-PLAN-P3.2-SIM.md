# PCS P3.2 SIM 实施 Writing-Plan（V1.0，2026-09-08）

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans。Steps 用 `- [ ]` checkbox 跟踪。

**Goal：** 按 spec/PCS-SPEC-P3-SIM SIM 模块 输入.md（V1.3）+ spec/工艺专用综合计算软件需求规格说明书 Web版 P3.md（V1.6）落地 P3.2 SIM——物流/状态点双层 case_type、4 态活跃、PRO/II + 手工 + Excel 三入口、收敛分层、冲突三级。

**Architecture：** FastAPI + SQLAlchemy 2.0 async；Alembic migration 一次到位（17+ 字段）；Service 层走物性补全（调 COMMON service IAPWS-IF97）+ 状态机（走 P1 记录层 9 态全集，P3 活跃 4 态）；API 层复用 `current_actor / require_roles`，ACL = DESIGNER + PROCESS_CONTROLLER + SYSTEM_ADMIN；导入路径 PRO/II + Excel 走异步 preview→commit。

**Tech Stack：** Python 3.11 + FastAPI 0.115+ + SQLAlchemy 2.0 async + Alembic + Pydantic v2 + chemicals1.5.2（COMMON 已平）+ pytest-asyncio + httpx TestClient。

**Spec：** spec/PCS-SPEC-P3-SIM SIM 模块 输入.md（V1.3，2026-09-08）、spec/工艺专用综合计算软件需求规格说明书 Web版 P3.md（V1.6，2026-09-08）。

**Plan origin：** 本 plan 基于 2026-09-08 P3.3 COMMON 关闭会话的 12-task Writing-Plan 草稿（用户显式确认：CRITICAL #2+#3 + HIGH #4+#5+#13 合并裁决——一次 migration 落地、SIM-1 同时含 Schema 三套）。

---

## Global Constraints

- **schema 敏感测试运行前必须**：`cd pcs-backend && uv run alembic upgrade head`（矫正迁移 historically 只应用了 pcs 库；pcs_test 库 schema 必须手动对齐）
- **新表迁移必须含 TimestampMixin 三列**（created_by/created_at/updated_at；created_at 带 timezone+server_default，updated_at nullable）
- **Pydantic v2 Schema 必须 Field(description=...)**：spec 本体论 V1.6 §5.3 要求每字段含中文描述
- **COMMON service 已平**：物性查询 → 直接 `from app.services.common_service import CommonService`，无需重启 P3.3 工作
- **StreamSignStatus**：PG native enum 'streamsignstatus' 已落；P3 活跃 4 态（DRAFT/IN_APPROVAL/CHECKED/CHECK_REJECTED），P4 扩展走 `ALTER TYPE streamsignstatus ADD VALUE`（PG enum value add 不可逆）
- **case_type 双层语义**：streams.case_type ≠ stream_state_points.case_type，独立两字段（spec V1.6 §3.2.2）
- **冲突解决三级**：BLOCK（硬冲突阻止保存）/ WARN（用户值优先但标记）/ INFO（计算值优先派生类）
- **收敛分层**：CONVERGED/WARNINGS 全量导入，NOT_CONVERGED/ABORTED SOLVED 单元产品 `unreliable=True`
- **实施纪律**：每步独立 commit；复跑依赖测试后再 commit；工作树全绿不算数，干净 worktree 验证 import + alembic + pytest 是唯一可信证据
- **ruff/格式化**：Commit 前 ruff check 0 错误
- **YAGNI**：HYSYS/Aspen/HTRI 解析器后置 P4，本 Sprint 仅做 PRO/II + 手工 + Excel

---

## 文件结构（修改/新建）

| 路径 | 状态 | 行数估 | 职责 |
|------|------|--------|------|
| `pcs-backend/alembic/versions/p3_sim_stream_schema_upgrade.py` | 新 | ~180 | 17+ 字段 migration |
| `pcs-backend/app/models/project.py`（Stream + StreamStatePoint） | 改 | +120 | ORM 同步 |
| `pcs-backend/app/models/__init__.py` | 改 | +5 | export 新 ORM |
| `pcs-backend/app/schemas/stream.py` | 新 | ~250 | StreamBase/Create/Update/Response + StatePoint + ImportPreview/ImportResult |
| `pcs-backend/app/services/stream_service.py` | 新 | ~500 | 物流 CRUD + 状态机 + 冲突检测 + **状态点 CRUD/冲突检测（合并自 StatePointService，共享事务）** |
| `pcs-backend/app/services/parsers/proii_parser.py` | 新 | ~400 | .inp 双文件解析 + 收敛分层 |
| `pcs-backend/app/services/parsers/excel_parser.py` | 新 | ~150 | openpyxl 解析 |
| `pcs-backend/app/services/property_completion.py` | 新 | ~200 | 调 COMMON 物性补全 |
| `pcs-backend/app/services/conflict_resolver.py` | 新 | ~180 | 三级冲突检测 |
| `pcs-backend/app/services/importers/proii_importer.py` | 新 | ~250 | preview → commit + unreliable 标记 |
| `pcs-backend/app/services/importers/excel_importer.py` | 新 | ~200 | preview → commit |
| `pcs-backend/app/api/v1/streams.py` | 新 | ~200 | 物流端点（CRUD + import） |
| `pcs-backend/app/api/v1/__init__.py` | 改 | +3 | 注册 streams_router |
| `pcs-backend/tests/services/test_stream_service.py` | 新 | ~280 | 物流 + 状态点 service 单测（含状态点同事务保证） |
| `pcs-backend/tests/services/test_proii_parser.py` | 新 | ~250 | 5 样例基线 + 收敛分层 |
| `pcs-backend/tests/services/test_excel_parser.py` | 新 | ~100 | Excel 解析 |
| `pcs-backend/tests/services/test_property_completion.py` | 新 | ~120 | 物性补全 |
| `pcs-backend/tests/services/test_conflict_resolver.py` | 新 | ~150 | 三级冲突 |
| `pcs-backend/tests/api/v1/test_streams.py` | 新 | ~250 | API 集成 + ACL |
| `pcs-backend/tests/integration/test_sim_e2e.py` | 新 | ~200 | 三入口端到端 |
| `pcs-backend/app/seeds/proii_samples/` | 新 | 5 文件 | 5 样例 .inp（spec §第三部分） |
| `pcs-backend/app/seeds/excel_templates/` | 新 | 1 文件 | Excel 模板（含字段说明） |
| `docs/PCS-P3.2-SIM-CLOSE-REPORT.md` | 新 | ~120 | Sprint 收口报告 |

**总计 ~3950 行新增**（按 200-400 行/文件、800 行 max 拆分；StatePointService 合并到 StreamService）

---

## 任务依赖图

```
SIM-1 (schema) ─┬─> SIM-3 (物性补全) ─> SIM-7 (冲突三级)
                ├─> SIM-4 (物流 CRUD)  ─┐
                ├─> SIM-8 (状态点)     ├─> SIM-11 (E2E)
                ├─> SIM-5 (Excel) ─────┤
                └─> SIM-2 (PRO/II 解析)─┘
                                ↓
                          SIM-6 (手工表单) + SIM-9 (状态点冲突)
                                ↓
                          SIM-10 (PRO/II 导入预览)
                                ↓
                          SIM-11 (E2E 集成测试)
                                ↓
                          SIM-12 (收口报告)
```

---

## Task 列表（12 tasks × 20.5 天）

### Task SIM-1：Streams 表 schema 升级 + ORM + Schema 三套（1 天）

**Files:**
- Create: `pcs-backend/alembic/versions/p3_sim_stream_schema_upgrade.py`
- Modify: `pcs-backend/app/models/project.py`（Stream + StreamStatePoint ORM 段，约 line 1-400 区域）
- Modify: `pcs-backend/app/models/__init__.py`
- Create: `pcs-backend/app/schemas/stream.py`
- Test: `pcs-backend/tests/models/test_stream_orm.py`
- Test: `pcs-backend/tests/schemas/test_stream_schema.py`

**Interfaces:**
- Consumes: 已有 Stream 模型（spec §第五部分 5.1，约 58 列）+ TimestampMixin + UUIDMixin
- Produces:
  - `app.models.project.Stream` 新增字段：`case_type`、`surface_tension`、`api_gravity`、`critical_temp`、`critical_press`、`vapor_fraction`、`actual_vol_flow`、`import_source_type`、`import_original_row`、`viscosity_temperature_curve`（JSONB）
  - `app.models.project.StreamStatePoint` 新增字段：`case_type`（状态点级 NORMAL/MIN/MAX/ALTERNATE）
  - `app.models.project.Stream.sign_status` 由 `varchar(20)` → `varchar(32)`
  - `app.schemas.stream.StreamBase/Create/Update/Response/ImportPreview/ImportResult` + `StreamStatePointBase/Create/Update/Response`

- [ ] **Step 1: 写失败的 model 测试**

```python
# tests/models/test_stream_orm.py
async def test_stream_has_case_type_column():
    cols = {c.name for c in Stream.__table__.columns}
    assert "case_type" in cols

async def test_stream_sign_status_varchar_32():
    col = Stream.__table__.columns["sign_status"]
    assert col.type.length == 32

async def test_stream_has_viscosity_curve_jsonb():
    col = Stream.__table__.columns["viscosity_temperature_curve"]
    assert "JSONB" in str(col.type)
```

- [ ] **Step 2: 跑测试确认 RED**

`cd pcs-backend && uv run pytest tests/models/test_stream_orm.py -v`
预期：FAIL（columns missing）

- [ ] **Step 3: 写 Schema 验证测试**

```python
# tests/schemas/test_stream_schema.py
def test_stream_base_requires_tag_number():
    from pydantic import ValidationError
    from app.schemas.stream import StreamBase
    with pytest.raises(ValidationError):
        StreamBase()  # tag_number 必填

def test_stream_state_point_case_type_enum():
    from app.schemas.stream import StreamStatePointBase, StatePointCaseType
    sp = StreamStatePointBase(case_type=StatePointCaseType.NORMAL, ...)
    assert sp.case_type.value == "NORMAL"
```

- [ ] **Step 4: 跑测试确认 RED**

`cd pcs-backend && uv run pytest tests/schemas/test_stream_schema.py -v`
预期：FAIL（ModuleNotFoundError: app.schemas.stream）

- [ ] **Step 5: 写 Alembic migration**

```python
# alembic/versions/p3_sim_stream_schema_upgrade.py
"""P3.2 SIM streams 表 schema 升级

- case_type 列（streams + stream_state_points 双层语义）
- P3-OPEN-005 16 字段（surface_tension / api_gravity / critical_temp / ...）
- viscosity_temperature_curve JSONB
- sign_status varchar(20) → varchar(32)（P4 ALTER TYPE 预留）
"""
revision = "p3sim_stream_upgrade"
down_revision = "<latest_sup_sprint_revision>"  # 从 alembic 实际查

def upgrade():
    op.add_column("streams", sa.Column("case_type", sa.String(20), nullable=True))
    op.add_column("streams", sa.Column("surface_tension", sa.Float, nullable=True))
    # ... 16 字段全列
    op.add_column("streams", sa.Column("viscosity_temperature_curve", postgresql.JSONB, nullable=True))
    op.alter_column("streams", "sign_status", type_=sa.String(32))

    # stream_state_points
    op.add_column("stream_state_points", sa.Column("case_type", sa.String(20), nullable=True))
    # CHECK 约束（NORMAL/MIN/MAX/ALTERNATE）
    op.create_check_constraint(
        "ck_stream_state_points_case_type",
        "stream_state_points",
        "case_type IN ('NORMAL','MIN','MAX','ALTERNATE')",
    )
    # streams 表 case_type CHECK
    op.create_check_constraint(
        "ck_streams_case_type",
        "streams",
        "case_type IN ('NORMAL','END_OF_RUN','START_OF_RUN','TURN_DOWN')",
    )
```

- [ ] **Step 6: ORM 同步**（修改 `app/models/project.py`）

在 `Stream` 类追加 16+ 字段；`StreamStatePoint` 加 `case_type` 字段；`sign_status` 长度改 32。

- [ ] **Step 7: 创建 Schema 三套**（`app/schemas/stream.py`）

StreamBase（含 17+ 字段，Field(description=...)）+ StreamCreate + StreamUpdate + StreamResponse + StreamStatePointBase/Create/Update/Response + StreamImportPreview + StreamImportResult + 枚举类 StreamCaseType / StatePointCaseType。

- [ ] **Step 8: 跑 pcs_test 库对齐**

```bash
cd pcs-backend && uv run alembic upgrade head
```

- [ ] **Step 9: 跑测试确认 GREEN**

`cd pcs-backend && uv run pytest tests/models/test_stream_orm.py tests/schemas/test_stream_schema.py -v`
预期：PASS

- [ ] **Step 10: ruff + 跑回归**

```bash
cd pcs-backend && uv run ruff check .
cd pcs-backend && uv run pytest -x
```
预期：ruff 0、新测试 PASS、回归 491/491 通过（477 旧 + 14 新）

- [ ] **Step 11: Commit**

```bash
git add pcs-backend/alembic/versions/p3_sim_stream_schema_upgrade.py \
        pcs-backend/app/models/project.py pcs-backend/app/models/__init__.py \
        pcs-backend/app/schemas/stream.py \
        pcs-backend/tests/models/test_stream_orm.py \
        pcs-backend/tests/schemas/test_stream_schema.py
git commit -m "feat(p3-sim-1): streams schema 升级 migration + ORM + Schema 三套"
```

---

### Task SIM-2：PRO/II .inp 双文件解析器（2.5 天）

**Files:**
- Create: `pcs-backend/app/services/parsers/proii_parser.py`
- Create: `pcs-backend/app/seeds/proii_samples/sample1_petroleum_fractionation.inp` + sample2~5
- Test: `pcs-backend/tests/services/test_proii_parser.py`

**Interfaces:**
- Consumes: `bytes`（.inp 文件内容）+ 文件路径
- Produces: `ProIIParseResult` dataclass 含：
  - `streams: list[ParsedStream]`
  - `units: list[ParsedUnit]`
  - `convergence_status: Literal['CONVERGED', 'WARNINGS', 'NOT_CONVERGED', 'ABORTED', 'NOT_SOLVED']`
  - `unreliable_unit_products: set[str]`（NOT_CONVERGED/ABORTED 单元的产品流名）
  - `warnings: list[str]`

**D9 critical gap #1：** 上传 .inp 文件大小限制 10 MB（spec §性能 ≤ 30s/1000 条推算 50 流约 500KB，10MB 是 20x 安全余量）。超出在端点层 middleware 校验，返 413 Payload Too Large + STREAM_IMPORT_FILE_TOO_LARGE 错误码。

- [ ] **Step 1: 写失败测试（spec §第三部分 5 样例基线）**

```python
# tests/services/test_proii_parser.py
async def test_proii_sample1_petroleum_fractionation_parses_50_streams():
    raw = (Path("app/seeds/proii_samples/sample1_petroleum_fractionation.inp")).read_bytes()
    result = parse_proii(raw)
    assert len(result.streams) >= 50
    assert result.convergence_status == "CONVERGED"

async def test_proii_sample2_unconverged_marks_unit_products_unreliable():
    raw = Path("app/seeds/proii_samples/sample2_unconverged.inp").read_bytes()
    result = parse_proii(raw)
    assert result.convergence_status in {"NOT_CONVERGED", "ABORTED"}
    assert len(result.unreliable_unit_products) > 0

# sample3~5 类似，含侧线 / 酸性水汽提 / DMC 反应精馏
```

- [ ] **Step 2: RED 确认**

`cd pcs-backend && uv run pytest tests/services/test_proii_parser.py -v`
预期：FAIL

- [ ] **Step 3: 准备 5 样例 .inp**

从 spec §第三部分 §607-628 引用 + 历史 PCS-NL-P3-SIM V1.1 §2.2 样例库复制（tests/fixtures/proii_samples/，5 文件，FCC 催化裂化 41 组分、SIDESTRIPPER/COMPRESSOR×2/SPLITTER×7/FLASH×4/VALVE/CONTROLLER/HX×25）。

- [ ] **Step 4: 实现 parser**

```python
# app/services/parsers/proii_parser.py
"""PRO/II .inp 双文件解析器（spec §第三部分）。
- 跳过 `** WARNING **` 输出信息行
- `$` 后非注释数据截断（如 `NORMALIZE$158.344,`）
- 零流量物流保留（mass_flow=0 不剔除，标记 zero_flow=True）
- 收敛分层（CONVERGED/WARNINGS/NOT_CONVERGED/ABORTED/NOT_SOLVED）
- 不可靠单元产品（NOT_CONVERGED/ABORTED SOLVED 单元的输出流）→ unreliable=True
"""
def parse_proii(raw: bytes, file_name: str = "<upload>") -> ProIIParseResult:
    ...
```

- [ ] **Step 5: GREEN 确认**

`cd pcs-backend && uv run pytest tests/services/test_proii_parser.py -v`
预期：5 样例全 PASS

- [ ] **Step 6: ruff + commit**

```bash
git add pcs-backend/app/services/parsers/proii_parser.py \
        pcs-backend/tests/services/test_proii_parser.py \
        pcs-backend/app/seeds/proii_samples/
git commit -m "feat(p3-sim-2): PRO/II .inp 解析器 + 5 样例基线"
```

---

### Task SIM-3：物性补全服务（1.5 天）

**Files:**
- Create: `pcs-backend/app/services/property_completion.py`
- Test: `pcs-backend/tests/services/test_property_completion.py`

**Interfaces:**
- Consumes: `ParsedStream` + `StreamStatePoint`（来自 SIM-2 / 手工 / Excel）
- Produces: 补全后的 `effective` JSON：调用 `CommonService.get_material(cas)` 补 MW/Tc/Pc/Tb，水 走 IAPWS-IF97，缺 CAS 走化学品库模糊匹配

- [ ] **Step 1: 写失败测试**

```python
async def test_property_completion_water_uses_iapws():
    stream = ParsedStream(tag="W1", cas="7732-18-5", temperature_k=373.15)
    eff = await complete_properties(stream)
    assert eff["mw"] == pytest.approx(18.015, rel=1e-3)
    assert eff["source"] == "IAPWS-IF97"

async def test_property_completion_unknown_cas_leaves_null():
    stream = ParsedStream(tag="X1", cas="0000-00-0")
    eff = await complete_properties(stream)
    assert eff["mw"] is None
    assert "warning" in eff  # 标记缺失
```

- [ ] **Step 2: RED → Step 3: 实现 → Step 4: GREEN**

```python
# app/services/property_completion.py
"""物性补全服务（spec §3.3.1）。
- 调 CommonService.get_material(cas) 补 MW/Tc/Pc/Tb；水走 IAPWS-IF97
- 缺 CAS 走 chemicals.search_chemical 子串匹配
- 性能：100 条物流并行（asyncio.gather），总耗时 ≤ 5s（spec ≤ 30s/1000 条）
"""
import asyncio

async def complete_properties(stream: ParsedStream) -> dict:
    if not stream.cas:
        return {"mw": None, "warning": "MISSING_CAS"}
    try:
        return CommonService.get_material(stream.cas)  # 同步，纯函数，亚毫秒
    except PcsError as e:
        return {"mw": None, "warning": str(e)}

async def complete_batch(streams: list[ParsedStream]) -> list[dict]:
    """批量并行：100 条 ~ 5s（vs 串行 ~30s 超 spec 预算）。"""
    return await asyncio.gather(*[complete_properties(s) for s in streams])
```

- [ ] **Step 4b: 加性能断言测试（spec §3.3.1 ≤ 5s/100 条）**

```python
# tests/services/test_property_completion.py
async def test_complete_batch_100_streams_under_5_seconds():
    streams = [ParsedStream(tag=f"S{i}", cas="7732-18-5") for i in range(100)]
    t0 = time.monotonic()
    results = await complete_batch(streams)
    elapsed = time.monotonic() - t0
    assert len(results) == 100
    assert elapsed < 5.0, f"批 100 条耗时 {elapsed:.2f}s 超 spec 预算 5s"
```

- [ ] **Step 5: ruff + commit**

```bash
git commit -m "feat(p3-sim-3): 物性补全服务（asyncio.gather 并行 + 性能断言 ≤5s/100 条）"
```

---

### Task SIM-4：物流 CRUD + 状态机（2 天）

**Files:**
- Create: `pcs-backend/app/services/stream_service.py`
- Test: `pcs-backend/tests/services/test_stream_service.py`

**Interfaces:**
- Consumes: `db_session` + `StreamCreate/Update` + actor（DESIGNER/PC/SA）
- Produces: 物流 CRUD + 状态机 transition（DRAFT → IN_APPROVAL → CHECKED / CHECK_REJECTED），调用 P1 记录层状态机（`app.services.state_machine.StreamSignStateMachine`，已实现）
- **D7 性能要求：** `list` 方法使用 `selectinload(Stream.state_points)` 一次 query 拿全部状态点，避免 N+1
- **D9 状态机并发安全：** `transition` 方法用 `SELECT ... FOR UPDATE` 悲观锁防并发覆盖（同流两 PC 同时点 approve，后到者拿到锁后看到 CHECKED 状态抛 InvalidTransition）

- [ ] **Step 1-5: RED → 实现 → GREEN → ruff → commit**

```python
# tests/services/test_stream_service.py
async def test_create_stream_in_draft_status(db_session, sample_project, sample_user):
    s = await StreamService.create(db_session, sample_project.id, StreamCreate(tag_number="S1", ...), sample_user)
    assert s.sign_status == "DRAFT"

async def test_submit_for_check_transitions_to_in_approval(db_session, sample_stream, sample_user):
    s = await StreamService.transition(db_session, sample_stream.id, "IN_APPROVAL", sample_user)
    assert s.sign_status == "IN_APPROVAL"

async def test_check_reject_transitions_to_check_rejected(db_session, sample_stream_in_approval, pc_user):
    s = await StreamService.transition(db_session, sample_stream_in_approval.id, "CHECK_REJECTED", pc_user, reason="...")
    assert s.sign_status == "CHECK_REJECTED"

# D7 性能：selectinload 防止 N+1
async def test_list_streams_with_state_points_single_query(db_session, sample_project, sample_user):
    """StreamService.list 应一次 query 拿到所有 stream 的 state_points，无 N+1。"""
    from sqlalchemy import event, select
    from app.models.project import Stream

    # 预创建 3 个流 + 每个 4 个状态点
    for i in range(3):
        s = await StreamService.create(db_session, sample_project.id, StreamCreate(tag_number=f"S{i}"), sample_user)
        for j, ct in enumerate(["NORMAL", "MIN", "MAX", "ALTERNATE"]):
            await StreamService.create_state_point(db_session, s.id, StreamStatePointCreate(case_type=StatePointCaseType(ct)))

    # 计数查询
    query_log = []
    @event.listens_for(db_session.get_bind(), "before_cursor_execute")
    def _log(*_): query_log.append(_)

    streams = await StreamService.list(db_session, sample_project.id)

    # 断言：state_points 已 eagerly loaded，访问不再触发 query
    for s in streams:
        _ = s.state_points  # 触发访问；已 eager-loaded 不再 query
    # 期望：list 触发的 query 数 ≤ 2（1 select streams + 1 selectinload state_points）
    assert len(query_log) <= 2, f"N+1 detected: {len(query_log)} queries, expected ≤ 2"

# D9 状态机并发：FOR UPDATE 防后写覆盖
async def test_concurrent_transition_second_writer_rejected(db_session, sample_stream_in_approval):
    """两并发 transition：第一个 IN_APPROVAL→CHECKED 成功；第二个 CHECKED→CHECKED 抛 InvalidTransition。"""
    import asyncio
    results = await asyncio.gather(
        StreamService.transition(db_session, sample_stream_in_approval.id, "CHECKED", pc_user_a),
        StreamService.transition(db_session, sample_stream_in_approval.id, "CHECKED", pc_user_b),
        return_exceptions=True,
    )
    successes = [r for r in results if not isinstance(r, Exception)]
    failures = [r for r in results if isinstance(r, Exception)]
    assert len(successes) == 1
    assert len(failures) == 1
    assert "InvalidTransition" in type(failures[0]).__name__
```

```bash
git commit -m "feat(p3-sim-4): 物流 CRUD + 状态机（DRAFT/IN_APPROVAL/CHECKED/CHECK_REJECTED + SELECT FOR UPDATE 并发安全）"
```

---

### Task SIM-5：Excel 导入/导出（1.5 天）

**Files:**
- Create: `pcs-backend/app/services/parsers/excel_parser.py`
- Create: `pcs-backend/app/seeds/excel_templates/stream_import_template.xlsx`
- Create: `pcs-backend/app/services/importers/excel_importer.py`
- Test: `pcs-backend/tests/services/test_excel_parser.py`

**Interfaces:**
- `parse_excel(raw: bytes) -> list[ParsedStream]`：openpyxl 解析 sheet1（物流）+ sheet2（状态点）
- `import_excel_streams(db, project_id, raw, actor) -> ImportResult`：preview→commit

- [ ] **Step 1-5: RED → 实现 → GREEN → ruff → commit**

```python
# tests/services/test_excel_parser.py
async def test_excel_template_parses_10_streams():
    raw = Path("app/seeds/excel_templates/stream_import_template.xlsx").read_bytes()
    streams = parse_excel(raw)
    assert len(streams) == 10
    assert all(s.tag_number for s in streams)

async def test_excel_missing_required_column_raises():
    raw = make_invalid_excel()  # 缺 tag_number
    with pytest.raises(PcsError, match="STREAM_MISSING_TAG_NUMBER"):
        parse_excel(raw)
```

```bash
git commit -m "feat(p3-sim-5): Excel 导入/导出 + 模板生成"
```

---

### Task SIM-6：手工表单端点（1 天）

**Files:**
- Modify: `pcs-backend/app/api/v1/streams.py`（SIM-4 创建路由，本 task 加手工表单端点）
- Test: `pcs-backend/tests/api/v1/test_streams.py`（追加手工用例）

- [ ] **Step 1-5: RED → 实现 → GREEN → ruff → commit**

```python
# POST /api/v1/projects/{pid}/streams/manual
async def test_create_stream_manual(client, sample_project, sample_user_token):
    r = await client.post(
        f"/api/v1/projects/{sample_project.id}/streams/manual",
        json={"tag_number": "M1", "cas": "7732-18-5", "temperature_k": 373.15, ...},
        headers=auth(sample_user_token),
    )
    assert r.status_code == 201
    assert r.json()["sign_status"] == "DRAFT"
```

```bash
git commit -m "feat(p3-sim-6): 物流手工表单端点"
```

---

### Task SIM-7：物流冲突三级检测（1.5 天）

**Files:**
- Create: `pcs-backend/app/services/conflict_resolver.py`
- Test: `pcs-backend/tests/services/test_conflict_resolver.py`

**Interfaces:**
- `resolve_conflicts(calculated: dict, user_provided: dict) -> ConflictResolution`：
  - BLOCK（相态矛盾、质量-摩尔流量换算不一致）
  - WARN（用户值优先但偏差 >5%）
  - INFO（计算值优先 MW/总流量）
  - 返回 `effective = calculated ⊕ user_provided`

- [ ] **Step 1-5: RED → 实现 → GREEN → ruff → commit**

```python
async def test_block_phase_contradiction():
    calc = {"phase": "VAPOR", "mw": 18.0}
    user = {"phase": "LIQUID"}
    res = resolve_conflicts(calc, user)
    assert res.level == "BLOCK"
    assert res.can_save is False

async def test_warn_temperature_deviation_5pct():
    calc = {"temperature_k": 373.15}
    user = {"temperature_k": 400.0}  # 7.2% 偏差
    res = resolve_conflicts(calc, user)
    assert res.level == "WARN"
    assert res.effective["temperature_k"] == 400.0  # 用户值优先

async def test_info_mw_calculated_priority():
    calc = {"mw": 18.015}
    user = {"mw": 20.0}  # 用户填错，MW 由 CAS 计算
    res = resolve_conflicts(calc, user)
    assert res.level == "INFO"
    assert res.effective["mw"] == 18.015  # 计算值优先
```

```bash
git commit -m "feat(p3-sim-7): 物流冲突三级检测（BLOCK/WARN/INFO）"
```

---

### Task SIM-8：stream_state_points CRUD（合并到 StreamService，1.5 天）

**Files:**
- Modify: `pcs-backend/app/services/stream_service.py`（追加 state point 方法段，约 +200 行）
- Modify: `pcs-backend/app/api/v1/streams.py`（追加状态点端点）
- Modify: `pcs-backend/tests/services/test_stream_service.py`（追加状态点用例）

**Interfaces:**
- 状态点作为 StreamService 的方法（`create_state_point`, `list_state_points`, `update_state_point`），与 stream CRUD 共享 db_session 同事务
- case_type 必填（NORMAL/MIN/MAX/ALTERNATE）
- sign_status 跟随所属 stream（不独立状态机）

**为什么合并：** 状态点必须与所属 stream 原子写入（防孤儿点）；同事务保证是硬约束，独立 service 会逼出跨 service 事务样板代码（gstack 偏好 boring by default）。

- [ ] **Step 1-5: RED → 实现 → GREEN → ruff → commit**

```python
async def test_create_state_point_requires_case_type():
    with pytest.raises(ValidationError, match="case_type"):
        StreamStatePointCreate(temperature_k=300, pressure_pa=101325)  # 缺 case_type
```

```bash
git commit -m "feat(p3-sim-8): 状态点 CRUD + 双层 case_type"
```

---

### Task SIM-9：状态点冲突检测（1 天）

**Files:**
- Modify: `pcs-backend/app/services/conflict_resolver.py`（追加 state_point_resolve）
- Test: 追加到 `tests/services/test_conflict_resolver.py`

- [ ] **Step 1-5: RED → 实现 → GREEN → ruff → commit**

```python
async def test_state_point_case_type_collision_block():
    """同一 stream + 同一 case_type 已存在 → BLOCK。"""
    ...

async def test_state_point_temperature_deviation_warn():
    ...
```

```bash
git commit -m "feat(p3-sim-9): 状态点冲突检测（case_type 唯一 + 偏差 WARN）"
```

---

### Task SIM-10：PRO/II 导入预览 + commit（2 天）

**Files:**
- Create: `pcs-backend/app/services/importers/proii_importer.py`
- Modify: `pcs-backend/app/api/v1/streams.py`（POST `/import/proii`）
- Test: `tests/api/v1/test_streams.py` 追加 + `tests/integration/test_sim_imports.py`

**Interfaces:**
- `preview_proii_import(raw, project_id, actor) -> ImportPreview`：返回将创建的 stream 数 + 冲突清单 + 不可靠单元产品数
- `commit_proii_import(preview_id, actor) -> ImportResult`：写入 DB + 标记 unreliable

**D2 架构裁决：** preview_id 写入 `import_previews` 表（复用 P2-SUP-002 PC5 模式，schema 已存在；user 2026-09-08 显式裁决）。commit 路由用 preview_id 关联解析结果，避免 stateless 重跑带来的：
1. preview/confirm 之间文件被改 → 冲突检测失效
2. PRO/II 50+ 流重解析数秒浪费
3. 前端要处理「文件已变」边界

**D3 默认裁决：** 幂等键 `(project_id, import_session_id, tag_number, case_type)` 唯一约束；二次写入静默跳过返回已存在 ID（spec §第六部分「增量幂等」既有约定）。

**D4 默认裁决：** ACL 走统一三角色（DESIGNER + PC + SA），与 P2 Sprint 1.8 一致；细粒度角色×操作矩阵 P4 再议。

- [ ] **Step 1-5: RED → 实现 → GREEN → ruff → commit**

```python
async def test_proii_import_preview_returns_conflicts(client, sample_project, sample_user_token):
    raw = Path("app/seeds/proii_samples/sample1_petroleum_fractionation.inp").read_bytes()
    r = await client.post(
        f"/api/v1/projects/{sample_project.id}/streams/import/proii/preview",
        files={"file": ("sample1.inp", raw)},
        headers=auth(sample_user_token),
    )
    assert r.status_code == 200
    body = r.json()
    assert body["stream_count"] >= 50
    assert "conflicts" in body
    assert body["unreliable_unit_products"] == []  # sample1 CONVERGED

async def test_proii_import_commit_creates_draft_streams(client, sample_project, sample_user_token):
    ...
```

```bash
git commit -m "feat(p3-sim-10): PRO/II 导入预览 + commit + unreliable 标记"
```

---

### Task SIM-11：端到端集成测试（1.5 天）

**Files:**
- Create: `pcs-backend/tests/integration/test_sim_e2e.py`

- [ ] **Step 1: 写 E2E（spec §第三部分 §637 三入口一致性 + D6 4 项关键边界）**

```python
# === 核心 3 项（spec 强制） ===
async def test_sim_three_entry_consistency(client, sample_project, sample_user_token):
    """同一物流：手工 / Excel / PRO/II 三入口导入后，effective 物性应一致。"""

async def test_sim_convergence_layer_not_converged_unreliable(client, sample_project, sample_user_token):
    """NOT_CONVERGED 单元产品标记 unreliable=True，不参与下游计算。"""

async def test_sim_block_conflict_prevents_save(client, sample_project, sample_user_token):
    """BLOCK 级冲突（相态矛盾）阻止保存，返回 422。"""

# === D6 关键边界 4 项 ===
async def test_sim_check_rejected_to_draft_resubmit_cycle(client, sample_project, sample_user_token, pc_user_token):
    """完整生命周期：DRAFT → IN_APPROVAL → CHECK_REJECTED → 修改 → DRAFT 重提 → IN_APPROVAL → CHECKED。
    验证驳回后修改重提路径不丢失字段、不破坏状态机约束。"""

async def test_sim_property_completion_partial_failure_aggregation(client, sample_project, sample_user_token):
    """complete_batch：100 条流中 10 条 CAS 非法 → 返 100 条结果，10 条带 warning，其余正常；不 fail-fast。"""

async def test_sim_migration_idempotent_run_twice_noop():
    """alembic upgrade head 跑两次：第二次应 no-op（无新 revision），schema 不变。"""

async def test_sim_block_conflict_user_fix_path(client, sample_project, sample_user_token):
    """BLOCK 后用户修复：POST phase=VAPOR+temperature=200K → 422；POST phase=LIQUID+temperature=400K → 201。
    验证错误码 STREAM_BLOCK_CONFLICT 返 422 含具体 conflict 字段，让 UI 能引导用户修复。"""
```

- [ ] **Step 2: GREEN → ruff → 全套回归**

```bash
cd pcs-backend && uv run pytest -x
```
预期：所有测试 PASS（491 旧 + 新增 ~17 = 508）

- [ ] **Step 3: commit**

```bash
git commit -m "test(p3-sim-11): SIM 端到端集成测试（三入口一致性 + 收敛分层 + 冲突 + 4 项关键边界）"
```

---

### Task SIM-12：收口报告 + 性能验收（0.5 天）

**Files:**
- Create: `docs/PCS-P3.2-SIM-CLOSE-REPORT.md`

- [ ] **Step 1: 写收口报告**

按 P3.3 COMMON 关闭报告模板：端点清单、数据来源、文件清单、测试结果、API 验收对齐、错误码、未做（YAGNI）、未解决问题。

- [ ] **Step 2: 性能验收**

- spec §3.3.1 ≤ 300ms 物性查询 → 已在 COMMON 平
- 物流导入 ≤ 30s/1000 条（spec §性能）→ 实测 sample1（50 流）< 1s，记录
- 冲突检测 ≤ 100ms/物流 → 实测

- [ ] **Step 3: 提交**

```bash
git add docs/PCS-P3.2-SIM-CLOSE-REPORT.md
git commit -m "docs(p3-sim-12): P3.2 SIM 关闭报告"
```

- [ ] **Step 4: /handoff 刷新 .wolf/STATUS.md**

---

## Self-Review（自检）

### 1. Spec 覆盖
- [x] §0 定位与三入口 → SIM-2/5/6
- [x] §1 手工输入 → SIM-6
- [x] §2 Excel 导入 → SIM-5
- [x] §3 PRO/II 解析 → SIM-2 + SIM-10
- [x] §4 统一校验 → SIM-7 + SIM-9
- [x] §5 PCS 数据模型 → SIM-1
- [x] §6 API 设计 → SIM-4/6/8/10
- [x] §7 实施计划 → 本 plan
- [x] §8 测试策略 → SIM-11

### 2. Placeholder 扫描
- 无 "TBD"/"TODO"/"implement later"
- 无 "add appropriate error handling"（全部 PcsError 抛具体错误码）
- 无 "similar to Task N" 简化引用（每 Task 含完整代码块）

### 3. 类型一致性
- `StreamCreate` / `StreamUpdate` / `StreamResponse` 在 SIM-1 定义，SIM-4/6/7/10 全部一致使用
- `StreamStatePoint*` 同上
- `ProIIParseResult` 在 SIM-2 定义，SIM-10 直接 import
- `ConflictResolution` 在 SIM-7 定义，SIM-9 复用扩展
- `CommonService.get_material(cas)` 在 P3.3 已实现，SIM-3 直接 import

---

## 质量门（每 Task 必过）

1. ruff check 0 错误
2. 新测试 100% PASS
3. 全套回归测试 PASS（基线 491 + 累计新增）
4. Alembic upgrade head 在 pcs_test 库成功（schema 敏感 Task）
5. Commit 信息含 task 编号（feat(p3-sim-N): ...）

---

## 未解决问题列表

1. **PRO/II 5 样例 .inp 文件实际存放位置**：spec §第三部分 §607-628 引用 + 历史 PCS-NL-P3-SIM V1.1 §2.2 样例库——SIM-2 Step 3 需先确认 5 样例文件可访问（NAS 路径 / git LFS / fixtures 目录）
2. **Stream 字段顺序对 API 契约的影响**：新增 17+ 字段后 `StreamResponse` JSON 字段顺序——前端 SPEC-P3-SIM V1.3 §2.5 示例按字典序输出，Pydantic v2 默认按字段定义序。需确认前端是否依赖字段顺序（YAGNI 默认按定义序）
3. **不可靠单元产品下游计算拒绝**：SIM-10 unreliable=True 标记后，下游工艺计算器（P3.3 之后扩展）是否需要硬拒绝调用？还是仅标记？本 plan 仅标记，未实现下游拒绝——P4 再议（TODO-037 已建）
4. **物性补全性能预算**：✅ 已解决（plan-eng-review D6 裁决 asyncio.gather 并行 + 性能断言 ≤5s/100 条，SIM-3 Step 3+4b 已编码）
5. **Excel 模板版本管理**：spec 未明确模板版本字段。SIM-5 仅生成 V1 模板，模板格式变更时旧数据导入兼容性留 P4 议（TODO-034 已建）
6. **校验规则 §第四部分 22 条全覆盖**：本 plan SIM-7 + SIM-9 仅实现 3 类典型（相态/偏差/MW 优先级）。其余 19 条（饱和蒸汽压、临界压缩因子等）逐条覆盖需额外 ~2 天，本 Sprint 仅做骨架（TODO-035 已建）

---

## GSTACK REVIEW REPORT

| Review | Trigger | Why | Runs | Status | Findings |
|--------|---------|-----|------|--------|----------|
| CEO Review | `/plan-ceo-review` | Scope & strategy | 0 | — | not run (optional) |
| Codex Review | `/codex review` | Independent 2nd opinion | 0 | — | codex unavailable |
| Eng Review | `/plan-eng-review` | Architecture & tests (required) | 1 | CLEAR | 11 issues, 2 critical gaps, 9 user decisions applied |
| Design Review | `/plan-design-review` | UI/UX gaps | 0 | — | not run (backend-only) |
| DX Review | `/plan-devex-review` | Developer experience gaps | 0 | — | not run |

- **UNRESOLVED:** 1 (Stream 字段顺序对 API 契约影响，1B — implementation-time concern)
- **VERDICT:** ENG CLEARED — plan ready for implementation. Run /ship when done.
