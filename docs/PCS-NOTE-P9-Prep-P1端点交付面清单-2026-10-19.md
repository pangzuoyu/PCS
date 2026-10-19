# 《P1 实际交付面清单》—— P9-Prep 交付物

- **日期**：2026-10-19
- **依据**：`spec/PCS-REQ-2026-002-SPEC-P9 …（修订版）` §2.2.3
- **用途**：P9A 排期时以本表为准，不再以 SPEC §2.2.3 的**假设路径**为准
- **状态**：已完成

---

## 0. 先说一件会毁掉整份核实的事

SPEC §2.2.3 给的核实命令是：

```bash
grep -rn "submit-approval" app/api/
```

`app/` **不在仓库根**，在 `pcs-backend/app/`。实测：

| 执行位置 | 结果 | 含义 |
|---|---|---|
| 仓库根 | `ugrep: warning: app/api/: No such file or directory`（RC=2） | 目录不存在，**零证据** |
| `pcs-backend/` | RC=1，零命中 | 真正的「未交付」结论 |

两者**都表现为「搜不到」**，但根目录那条是**命令根本没执行成功**，不是「搜过了没有」。
照 SPEC 原样在仓库根跑，据此判「未交付」是**假阴性**。

> **规矩**：核实端点一律 `cd pcs-backend` 后执行。根目录的 grep 结果不作为证据。

---

## 1. 权威来源：怎么枚举真实路由

⚠️ **不要用 `for r in app.routes`。** 本仓 FastAPI 版本把 `include_router` 进来的
路由包成 `_IncludedRouter` 对象而**不展开**，`app.routes` 只有 6 项（4 个内置文档路由
+ 2 个 `_IncludedRouter`），**一条 API 路由都枚举不到** —— 它会静默产出一份空清单，
比假阴性更难发现。

正确做法是读 OpenAPI（`app.openapi()` 展开全部 216 条 path）：

```bash
cd pcs-backend
uv run python -c "
from app.main import app
paths = app.openapi()['paths']
print('TOTAL PATHS', len(paths))
for p in sorted(paths):
    if 'record' in p or 'deliverable' in p or 'change-impact' in p:
        print(sorted(paths[p].keys()), p)
" 2>/dev/null
```

实测输出（`TOTAL PATHS 216`，下表即由此得出；完整 216 条可用上面命令原样重新生成）：

```
['post']                                    /api/v1/change-impact/{record_type}/{record_id}/confirm-recalc
['delete', 'get', 'patch']                  /api/v1/cool-tower/results/{record_id}
['get']                                     /api/v1/deliverables
['get']                                     /api/v1/deliverables/{deliverable_id}
['get']                                     /api/v1/deliverables/{deliverable_id}/versions
['get']                                     /api/v1/deliverables/{deliverable_id}/versions/{rev}/snapshot
['delete', 'get', 'patch']                  /api/v1/flare/results/{record_id}
['get']                                     /api/v1/lineage/{record_type}/{record_id}/downstream
['get']                                     /api/v1/lineage/{record_type}/{record_id}/graph
['get']                                     /api/v1/lineage/{record_type}/{record_id}/upstream
['delete', 'get', 'patch']                  /api/v1/psychro/results/{record_id}
['get', 'post']                             /api/v1/records/piping
['delete', 'get']                           /api/v1/records/piping/{pipe_id}
['get']                                     /api/v1/records/piping/{pipe_id}/snapshots
['post']                                    /api/v1/records/piping/{pipe_id}/transition
```

---

## 2. SPEC §2.2.3 点名的 12 个端点

| SPEC 假设路径 | 实际 | 存在 | 证据 | 归属 |
|---|---|---|---|---|
| `POST /records/{module}/{id}/submit-approval` | — | ❌ | `app/api/v1/records.py` 全部 6 个路由见下 | P9A |
| `POST /records/{module}/{id}/approval-step` | — | ❌ | 同上 | P9A |
| `POST /records/{module}/{id}/abandon-change` | — | ❌ | 同上 | P9A |
| `POST /records/{module}/{id}/request-reversal` | — | ❌ | 同上 | P9A |
| `POST /records/{module}/{id}/reversal-decision` | — | ❌ | 同上 | P9A |
| `POST /records/{module}/{id}/obsolete` | — | ❌ | 同上；`app/models/mixins.py:88-92` 只有 `obsoleted_reason/by/at/via_deliverable_id` **数据列**，无端点 | P9A |
| `POST /records/{module}/{id}/comments` | — | ❌ | 同上 | P9A |
| `GET /deliverables/{id}/actions` | — | ❌ | `deliverables.py` 只有 4 个 GET，见下 | P9A |
| `POST /deliverables/{id}/issue` | — | ❌ | 同上 | P9A |
| `POST /deliverables/{id}/sign-step` | — | ❌ | 同上 | P9A |
| `POST /deliverables/{id}/customer-approval/proxy` | — | ❌ | 同上 | P9A |
| `POST /change-impact/{module}/{id}/confirm` | `POST /api/v1/change-impact/{record_type}/{record_id}/confirm-recalc` | ⚠️ **存在，但不是 SPEC 要的那个** | `app/api/v1/change_impact.py:27` | 见 §3 |

**`records.py` 的全部 6 个路由**（`grep -nE "@router\.(get|post|patch|delete|put)"` 实测，共 315 行）：

```
records.py:40   @router.get("/piping", response_model=list[dict])
records.py:78   @router.get("/piping/{pipe_id}", response_model=dict)
records.py:116  @router.post("/piping", response_model=dict)
records.py:167  @router.post("/piping/{pipe_id}/transition", response_model=dict)
records.py:219  @router.delete("/piping/{pipe_id}", response_model=dict)
records.py:270  @router.get("/piping/{pipe_id}/snapshots", response_model=list[dict])
```

只有 `piping` 一个模块，**没有任何工作流写端点**。

---

## 3. `confirm-recalc` 的实质裁决

`app/api/v1/change_impact.py:27-86` 全文只做四件事：

```
tracker = LineageTracker(session); latest = await tracker.latest(...)
marked = await CIAEngine(session).scan_stale()
propagation = await mark_stale_then_propagate(...)
await session.commit()
```

**它没有** P9A-CIA-001 要求的哈希判定分流 —— 即：

- 结果不变 → 返回 `STALE_RESOLVED_NO_CHANGE` **免凭证**
- 结果变化 → 返回 `CHANGE_PENDING` **要求重新签署**

两条分支一处都没有。

**裁决**：

1. `confirm-recalc` 是 **P1 已交付的传播触发器**，不是 SPEC §2.2.3 假设的 `confirm`。
2. **P9A-CIA-001（哈希判定分流）与 P9A-CIA-002（`manual-adjust`）均归 P9A**。
   `manual-adjust` 端点**不存在**，需 P9A 新建。
3. `confirm_recalc` 用 `response_model=dict`（`change_impact.py:27`）⇒ **贡献裸字段**。
   实测对基线的影响见 §4。

---

## 4. 裸字段基线实测（PP-M 的输入）

```bash
cd pcs-backend
uv run python scripts/check_openapi_payload_coverage.py
```

实测输出：

```
API 载荷结构覆盖: 87/158 (55.1%)，基线要求裸字段 <= 71
当前: 71 个裸 object/array（296 个 schema 全体扫描）
欠账明细（71 个，不阻断；修 §3.4 约束① 时自然下降）
RC=0
```

`scripts/check_openapi_payload_coverage.py:40` 的 `BASELINE_BARE_FIELDS = 71`
与实测**一致，无偏差**。

⇒ Task 8（PP-M）把 SPEC 里 70 / 71 两处表述统一为 **71**，理由是**代码是权威值，文档跟着代码改**。

---

## 5. SPEC 没列、但 P9B 要用的 4 个读端点

P8 前置已交付，schema 已显式声明，**零裸字段**：

| 端点 | 实现 | 位置 | 归属 |
|---|---|---|---|
| `GET /api/v1/deliverables` | `list_deliverables` | `deliverables.py:62` | P1（P8 前置） |
| `GET /api/v1/deliverables/{deliverable_id}` | `get_deliverable` | `deliverables.py:101` | P1（P8 前置） |
| `GET /api/v1/deliverables/{deliverable_id}/versions` | `list_deliverable_versions` | `deliverables.py:120` | P1（P8 前置） |
| `GET /api/v1/deliverables/{deliverable_id}/versions/{rev}/snapshot` | `get_deliverable_snapshot` | `deliverables.py:142` | P1（P8 前置） |

---

## 6. 对 P9A 排期的直接影响

> **P9 后端交付物子系统实际上没有由 P1 交付。**

P1 交付的是：状态机骨架（`transition`）+ deliverables 的**只读面**（4 个 GET）。
**9 个 records 工作流端点 + 4 个 deliverables 写端点 + 1 个 CIA 判定分流全部不存在。**

P9A 排期时按本表的「归属」列走，**不要**按 SPEC §2.2.3 的路径清单假定它们存在。

## 尚未解决

1. **`confirm_recalc` 的 `response_model=dict` 已计入 71 基线还是未计入，本次无法区分**
   —— 脚本只报总数，不按端点归因。若 P9A 要改造该端点为显式 schema，需先知道它当前占几个。
2. **P9B 的 `GET /deliverables/{id}/actions` 无对应数据源**
   —— 4 个既有读端点里没有「动作历史」。该数据来自 `audit_logs` 还是新表，属 P9A/P9B 交界，未在本清单裁决。
