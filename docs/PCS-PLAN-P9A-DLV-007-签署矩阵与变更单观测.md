# P9A-DLV-007 + TODO-057 实施计划：签署矩阵的取得 + 变更单的观测写入点

> **For agentic workers:** REQUIRED SUB-SKILL: `superpowers:executing-plans`
> ledger: `.superpowers/sdd/PCS-PLAN-P9A-DLV-007-签署矩阵与变更单观测/progress.md`

**Goal:** 落地 **ADR-0047 §① 的第三个观测写入点**（CHANGE_NOTICE），
并清掉它卡住的那块：**签署矩阵没人创建、没人绑定** ⇒ 变更单的创建路径不可达。

**Architecture:** 一个新服务 `SignatureMatrixService` 负责「**矩阵从哪来** +
**步骤怎么解析**」；`ChangeNoticeService` 负责「变更单的建单与关闭」，
在**创建**与**自动关闭**两处写观测行（ADR-0047 §① 写入点 2）。

**Tech Stack:** FastAPI + SQLAlchemy 2.x async + pytest（内存 SQLite）。

**Spec:**
- `docs/adr/0047-workflow-progress-observation-layer.md` **§① 写入点清单** / §②③ 事务边界
- `docs/adr/0008-change-notice-as-deliverable-subtype.md`（变更单 = 交付物子类型 +
  默认 3 级矩阵 `CHANGE_NOTICE_3_LEVEL` + APPROVED 后自动联动记录）
- `docs/adr/0002-changed-lifecycle-and-change-notice.md`
- `spec/校审层级可配置化增补规格说明书.md` §2.3（矩阵模板 `steps_json` 形状）/ §2.4（版本目的 → 矩阵映射）
- `spec/PCS-REQ-2026-002-SPEC-P9 …` **§3.2.1 P9A-DLV-007** / §3.2.3 P9A-OBS-001~004
- `TODOS.md` **TODO-057**（本批要闭环的那条）/ TODO-052 / TODO-053

---

## Global Constraints

1. **观测写入只有一个入口**：`app/services/workflow_progress_writer.py` 的
   `record_step()`（ADR-0047 §① 🔒，`test_writer_has_no_second_entry_point` 钉住）
   ⇒ **不得**新写一个写入口。
2. **写入层必须在 service 层**（ADR-0047 §① 🔒）⇒ 写入落在
   `ChangeNoticeService`，**不**落在 API 层。
3. **同步写、与业务状态同一事务**；观测写失败 ⇒ 整个状态变更回滚
   （ADR-0047 §②③）⇒ `record_step` 不 commit，由调用方 commit。
4. **不 commit**：`record_step` 不 commit；本批的 service 在最后统一 commit。
5. **不新建写入口、不新建第二个 `steps_json` 解析口**：解析收敛到
   `SignatureMatrixService.parse_steps`，`DeliverableService._matrix_steps` 改为调它。
6. **矩阵的步骤定义是配置数据**：`steps_json` 的键序不保证 ⇒ 必须显式按
   `step_order` 排序；坏数据**不静默吞**（要么跳过并计数，要么明说 —— 见裁决 2）。
7. 提交约定：conventional commits，**无 attribution 行**。长 commit message 写文件后
   `git commit -F <file>`。
8. ⚠️ **不要建 worktree**（本仓历史事故，见 `.wolf/STATUS.md`）。
9. ⚠️ **本批不改迁移**（不改表结构 ⇒ 无漂移风险 ⇒ 无需在全新库上验）。

## Review Focus

| # | 失败模式 | 期望行为 | 归属 |
|---|---|---|---|
| RF-1 | **矩阵被静默降级**：矩阵解析遇到坏数据就当空步骤 ⇒ 变更单按 **0 步**走 ⇒ 签署一推就「越界」 | 坏数据**明说**（422 `SIGNATURE_MATRIX_INVALID`），不静默当空 | T1 |
| RF-2 | **矩阵解析的第二份实现** ⇒ 签署路径与变更单路径对同一份 `steps_json` 给出**不同的步骤** | `parse_steps` 是**唯一**解析口；`DeliverableService._matrix_steps` 改为调它 | T1 |
| RF-3 | **惰性建行不幂等** ⇒ 每次建变更单都新建一个矩阵模板 ⇒ 矩阵表膨胀、且不同变更单用不同矩阵 | 同项目同模块**只建一次**（唯一性由查询保证，不靠 catch） | T1 |
| RF-4 | **跨项目串矩阵** —— 项目 A 的变更单用了项目 B 的矩阵 | 绑定按 `project_id` 查；模板是全局的但**绑定**是项目的 | T1 |
| RF-5 | **观测行写成了「访问日志」** ⇒ 甘特图把「建了变更单」算成流程活动 | 创建写 **PENDING**（流程已发起、尚未关闭），不是 COMPLETED | T2 |
| RF-6 | **观测写在了业务事务之外** ⇒ 业务成功但观测缺失（或反之） | 观测写与建单**同一事务**；观测写失败 ⇒ 建单回滚 | T2 |
| RF-7 | **关闭路径漏写** ⇒ 变更单永远停在「进行中」⇒ 超时告警永远不触发 | `approve_change_notice`（自动关闭）写 **COMPLETED** | T3 |
| RF-8 | **唯一约束撞车** —— `uq_deliverables_scope` = (project_id, deliverable_type, scope_type, scope_value) ⇒ 同一项目的第二张变更单**插不进去** | 变更单的 `scope_type` 用 `CUSTOM` + `scope_value` 带记录标识 ⇒ 每张变更单一行 | T2 |
| RF-9 | **矩阵未绑到项目** ⇒ 变更单建出来了却**签不了**（`_assert_matrix_bound` ⇒ 409） | 建单时**同时**建项目绑定（否则交付物机制对它无效） | T1 / T2 |

---

## 事实基础（2026-10-21 实测）

### DLV-007 的三个子项，**两个已经落地了**

P9 SPEC 写「P9A-DLV-007 `SignatureMatrixService`：steps_json 消费方，矩阵步骤推进、
角色判定、动态列数（SUP-005，当前未落地）」。**实测：后两项已在 P9A B2 落地**：

| 子项 | 现状 | 位置 |
|---|---|---|
| 矩阵步骤推进 | ✅ `DeliverableService.sign_step` 顺序推进、越步 409 | `deliverable_service.py:530` |
| 角色判定 | ✅ `sign_role != actor_role` ⇒ 403；`can_self_check` ⇒ 403 | `deliverable_service.py:585` |
| 动态列数 | ✅ 前端 `SignatureMatrix` 按 `steps.length` 出列 | `src/components/common/SignatureMatrix.tsx` |
| **矩阵从哪来** | ❌ **全仓无任何地方创建/绑定矩阵** ⇒ `signature_matrices` **恒 0 行** | `grep -rn "SignatureMatrix(" app/` ⇒ 0 |

⇒ **本批真正要补的是「矩阵的取得」**，外加把解析收敛到一处（避免两份
`steps_json` 解析给出不同结果）。

### 表与约束

- `signature_matrices`：`matrix_id` / `matrix_name` / `module`（`*` = 全部）/
  `doc_type` / `version_purpose` / `steps_json`（JSONB，形状
  `[{"step_order","sign_role","required","can_self_check","can_skip"}]`）/ `status`
  （DRAFT/PENDING/ACTIVE/OBSOLETE）。
- `project_signature_matrix_bindings`：`project_id` + `module` + `matrix_id`。
- `deliverables.matrix_id`：**NOT NULL** + FK → `signature_matrices.matrix_id`
  ⇒ **建变更单必须先有矩阵**（这就是 TODO-057 的「触发条件」）。
- ⚠️ `uq_deliverables_scope` = (project_id, deliverable_type, scope_type, scope_value)
  ⇒ 参照实现用 `scope_type='PROJECT_ALL' / scope_value='ALL'` ⇒
  **同一项目的第二张变更单插不进去**（IntegrityError / 409）⇒ RF-8。
- `change_notice_details`：`deliverable_id` unique + `change_type`（7 值）/
  `reason` / `triggered_by`（MANUAL/UPSTREAM_CHANGE）/ `source_record_type`。

### 观测层

- 唯一写入口 `record_step(session=, project_id=, workflow_type=, workflow_id=,
  step_order=, step_role=, state=, actor_user_id=, result_hash=)`，**不 commit**。
- upsert 键 = (workflow_type, workflow_id, step_order)。
- `WorkflowType` 3 值：`SIGN` / `CHANGE_NOTICE` / `CUSTOMER_APPROVAL_PROXY`。
- `workflow_progress_service._resolve`：**SIGN → `deliverable_versions`**，
  **其余两类 → `deliverables`** ⇒ ⇒ **CHANGE_NOTICE 的 `workflow_id` 是
  变更单的 `deliverable_id`**（不是版本 id）。
- ADR §① 写入点 2 = 变更单的「**创建**」与「**自动关闭**」。

### 已有测试

`tests/services/test_change_notice_service.py` 有 **5 个用例断言
`create_change_notice` 抛 `NotImplementedError`**（无副作用、不写审计）
⇒ 本批要**改写**它们（不是删掉）。

---

## 裁决

| # | 裁决 | 理由 | 代价 |
|---|---|---|---|
| **R-1** | **CHANGE_NOTICE 工作流只写 1 行**（`step_order=1`, `step_role='CHANGE_NOTICE'`），不是矩阵的 N 行 | 变更单的**签署步骤**已由 SIGN 工作流观测（`workflow_id` = 版本 id）⇒ 再写一份就是**同一事实的两个来源**（正是 TODO-065 聚合端点存在的原因：两类 id 不同）。CHANGE_NOTICE 工作流回答的是「**这张变更单**走到哪了」（发起 → 关闭），那是一个单步业务流程 | 变更单的 3 级校审在**签发之前**不可见（那时它还没有版本行，SIGN 工作流自然也没有）⇒ 与真相一致 |
| **R-2** | `parse_steps` 遇到**坏数据**（缺 `step_order` / `sign_role` 非字符串）⇒ **跳过该项**并继续，但**整个矩阵为空或全部非法** ⇒ 422 `SIGNATURE_MATRIX_INVALID` | 矩阵是配置数据：一份坏配置不该让**所有**签署流程 500；但**静默少一步**会让签署少一道校审（更危险）⇒ 「部分跳过 + 全部非法则明说」的折中。⚠️ 坏项被跳过这件事要**可观测**（返回里带 `skipped` 计数） | 部分跳过的矩阵会少一步 ⇒ 变更单的校审层数可能与预期不符 ⇒ 登记进 `steps_json` 的校验器（另批） |
| **R-3** | 矩阵模板**惰性建行**（与 P9A-USR-001「惰性建行」同形，ADR-0046 §③ 先例）：项目缺矩阵 ⇒ 建内置 `CHANGE_NOTICE_3_LEVEL` + 建项目绑定 | `signature_matrices` 恒 0 行且**全仓无创建方** ⇒ 不建行则变更单路径永远不可达。替代方案是 seed 脚本，但每个库/每个项目都要手动跑 ⇒ 服务层惰性建行是唯一能让路径**可达**的做法 | 首次建单会多 2 行（模板 + 绑定）⇒ 幂等性由查询保证（RF-3） |
| **R-4** | 内置模板的步骤取 **3 级：校核 / 审核 / 审定**（`CHECKER` / `REVIEWER` / `APPROVER`），`can_self_check` **默认 true**（与 `sign_step` 现有判据一致：`step.get("can_self_check", True)`） | ADR-0008「变更单默认 3 级矩阵（校核/审核/审定）」；`can_self_check` 不写 ⇒ 沿用现有默认（**不发明**与既有签署路径不同的语义） | 若业务要求变更单**禁止**自校，需要在模板里显式写 `can_self_check: false` ⇒ 另议 |
| **R-5** | 变更单的 `scope_type='CUSTOM'`、`scope_value=f"CHANGE_NOTICE:{record_type}:{record_id}"` | RF-8：`uq_deliverables_scope` 会让同一项目的第二张变更单插不进去 ⇒ 必须让每张变更单的 scope 唯一 | 与其它交付物（PROJECT_ALL）的 scope 语义不同 ⇒ 但变更单本来就是「针对某条记录的」，CUSTOM 恰好贴切 |
| **R-6** | **不抽** `sign_step` 里的角色判定进新服务 | 「矩阵步骤推进 / 角色判定」已在已验收的签署路径里落地 ⇒ 抽出来要动 P9A B2 的代码，收益是「名义上的 DLV-007 完整」，代价是签署路径的回归风险 | P9 SPEC 的 DLV-007 描述与代码现状不完全对齐 ⇒ 须在 SPEC 处登记实现偏离（同 TODO-053 的做法） |
| **R-7** | **不新增 API 端点**（变更单的创建仍只有 service 层入口） | TODO-057 = 观测写入点；ADR §① 要求的写入层就是 service 层。新增 HTTP 面会牵出权限、请求 schema、契约、前端按钮 —— 属另一批（已在 `TODOS.md` 登记） | 变更单仍不能从界面创建 ⇒ 「可达路径」= service 层可达 |

---

## 文件结构

**新建**（3 个）：

| 文件 | 职责 |
|---|---|
| `pcs-backend/app/services/signature_matrix_service.py` | **矩阵的取得与解析**（唯一 `steps_json` 解析口 + 惰性建内置模板与项目绑定） |
| `pcs-backend/tests/services/test_signature_matrix_service.py` | T1 的守卫 |
| `pcs-backend/tests/services/test_change_notice_observation.py` | T2 / T3 的守卫（观测写入点） |

**修改**（3 个）：

| 文件 | 改什么 |
|---|---|
| `pcs-backend/app/services/change_notice_service.py` | ① `create_change_notice` 落地（去 `NotImplementedError`）+ **写观测（创建）**；② `approve_change_notice` **写观测（自动关闭）** |
| `pcs-backend/app/services/deliverable_service.py` | `_matrix_steps` 改为调 `SignatureMatrixService.parse_steps`（消除第二份解析，RF-2） |
| `pcs-backend/tests/services/test_change_notice_service.py` | 5 个「断言 NotImplementedError」的用例改写为**断言新行为** |

---

## Task T1：`SignatureMatrixService` —— 矩阵的取得与解析（P9A-DLV-007）

**Files:**
- Create: `pcs-backend/app/services/signature_matrix_service.py`、
  `pcs-backend/tests/services/test_signature_matrix_service.py`
- Modify: `pcs-backend/app/services/deliverable_service.py`（`_matrix_steps` 改调服务）

**Interfaces:**
- Consumes: `SignatureMatrix` / `ProjectSignatureMatrixBinding`（ORM）、
  `PcsError`。
- Produces:
  ```python
  @dataclass(frozen=True)
  class MatrixStep:
      step_order: int
      sign_role: str
      required: bool = True
      can_self_check: bool = True
      can_skip: bool = False

  class SignatureMatrixService:
      DEFAULT_CHANGE_NOTICE_MATRIX_NAME = "CHANGE_NOTICE_3_LEVEL"
      DEFAULT_CHANGE_NOTICE_STEPS: tuple[dict, ...] = (...)

      @staticmethod
      def parse_steps(matrix: SignatureMatrix | None) -> list[MatrixStep]
      @classmethod
      async def ensure_change_notice_matrix(
          cls, db: AsyncSession, *, project_id: uuid.UUID
      ) -> SignatureMatrix
      @staticmethod
      def role_for_step(steps: list[MatrixStep], step_order: int) -> str | None
  ```

**Step 1: 写失败测试**（`tests/services/test_signature_matrix_service.py`）

必含断言：
1. `parse_steps` 按 `step_order` **升序**（`steps_json` 里的顺序是乱的 ⇒
   排序是必须的，RF-2 的核心）。
2. `parse_steps(None)` / 空 `steps_json` ⇒ `[]`。
3. **坏数据**：缺 `step_order` / `sign_role` 非字符串的项被**跳过**，
   其余项保留（R-2）。
4. **全部非法** ⇒ 抛 `PcsError` `SIGNATURE_MATRIX_INVALID`（422）。
5. `can_self_check` 缺省 ⇒ **true**（与 `sign_step` 的既有默认一致，R-4）。
6. `ensure_change_notice_matrix`：
   - 项目**没有**绑定 ⇒ 建**内置模板**（`matrix_name='CHANGE_NOTICE_3_LEVEL'`、
     `module='CHANGE_NOTICE'`、`status='ACTIVE'`、3 步）+ 建**项目绑定**；
   - **再调一次** ⇒ **不重复建**（模板数与绑定数不变）⇒ RF-3；
   - 两个项目 ⇒ 各自的绑定指向**同一个**全局模板，但**绑定行各一份**
     ⇒ RF-4（项目 A 的变更单不会用项目 B 的绑定）。
7. `role_for_step(steps, 2)` ⇒ 第 2 步的 `sign_role`；越界 ⇒ `None`。

**Step 2: 跑测试确认失败**

Run: `cd pcs-backend && uv run pytest tests/services/test_signature_matrix_service.py -q`
Expected: FAIL —— 模块不存在。

**Step 3: 写服务**

```python
"""签署矩阵服务（P9A-DLV-007 · SUP-005 · ADR-0008）。

## 它管两件事

1. **解析**：`steps_json` → `MatrixStep[]`（**唯一的解析口**）
2. **取得**：项目要用的矩阵从哪来（**惰性建行**，见下）

## 为什么要「惰性建行」

`signature_matrices` **恒为 0 行** —— 全仓**没有任何地方创建矩阵**
⇒ 变更单（`Deliverable.matrix_id` NOT NULL + FK）**建不出来**
⇒ ADR-0047 §① 的第三个写入点（CHANGE_NOTICE）**没有可达路径**
（这就是 TODO-057 卡住的地方）。

⇒ 本服务在需要时建**内置模板**并**绑到项目**（与 P9A-USR-001「惰性建行」
同形，ADR-0046 §③ 先例）。

## 内置模板

`CHANGE_NOTICE_3_LEVEL` —— 3 级（校核 / 审核 / 审定），
依据 ADR-0008「变更单默认 3 级矩阵（校核/审核/审定）」与
`spec/校审层级可配置化增补规格说明书.md` §2.4 的版本目的 → 矩阵映射表。
"""
```

实现要点：
- `parse_steps`：`steps_json` 非 dict 的项跳过；`step_order` 必须是 **int**（`bool`
  不算 int！`isinstance(True, int)` 为真 ⇒ 要显式排除）、`sign_role` 必须是
  **非空 str**；其余项按 `step_order` 升序；**全部非法** ⇒
  `PcsError(code="SIGNATURE_MATRIX_INVALID", status=422)`。
- `ensure_change_notice_matrix`：
  1. 查项目绑定（`module='CHANGE_NOTICE'`）⇒ 有 ⇒ 取那个矩阵返回；
  2. 否则查**全局模板**（`matrix_name='CHANGE_NOTICE_3_LEVEL'` 且 `status='ACTIVE'`）
     ⇒ 没有 ⇒ **建**（3 步，R-4）；
  3. 建项目绑定（若还没有同 (project, module) 的绑定）⇒ 返回矩阵。
  ⚠️ **不 commit**（与 `record_step` 一致：事务边界归调用方）。

**Step 4: 收敛第二份解析**

`DeliverableService._matrix_steps` 改为：

```python
    @staticmethod
    def _matrix_steps(matrix: SignatureMatrix | None) -> list[dict[str, Any]]:
        """取矩阵步骤，按 `step_order` 升序（**委托给唯一解析口**）。"""
        return [
            {
                "step_order": s.step_order,
                "sign_role": s.sign_role,
                "required": s.required,
                "can_self_check": s.can_self_check,
                "can_skip": s.can_skip,
            }
            for s in SignatureMatrixService.parse_steps(matrix)
        ]
```
⚠️ **行为变化**（要写进 commit message）：`can_self_check` 的缺省值从
「字典里没有 ⇒ `sign_step` 用 `step.get('can_self_check', True)` ⇒ true」
变成「解析时补成 `True`」⇒ **等价**（RF-2 的目的就是让两处一致）。

**Step 5: 跑测试确认通过 + 全量后端**

Run: `cd pcs-backend && uv run pytest tests/services/test_signature_matrix_service.py -q`
Expected: PASS。

**Step 6: 提交**

```bash
git add app/services/signature_matrix_service.py app/services/deliverable_service.py \
  tests/services/test_signature_matrix_service.py
git commit -m "feat(P9A-DLV-007): 签署矩阵服务 —— steps_json 唯一解析口 + 内置模板惰性建行"
```

---

## Task T2：`create_change_notice` 落地 + 写观测（创建）

**Files:**
- Modify: `pcs-backend/app/services/change_notice_service.py`
- Modify: `pcs-backend/tests/services/test_change_notice_service.py`（5 个旧用例改写）
- Create: `pcs-backend/tests/services/test_change_notice_observation.py`

**Interfaces:**
- Consumes: `SignatureMatrixService.ensure_change_notice_matrix`（T1）、
  `record_step`（唯一写入口）、`WorkflowType.CHANGE_NOTICE`、
  `WorkflowProgressState.PENDING`。
- Produces: `ChangeNoticeService.create_change_notice` 不再抛
  `NotImplementedError`；返回的 DTO 增加 `workflow_id` 与 `matrix_id`。

**Step 1: 改写旧测试（RED）**

`tests/services/test_change_notice_service.py` 里 5 个用例
（`test_create_change_notice_is_not_implemented` /
`test_create_change_notice_writes_nothing_before_raising` /
`test_create_change_notice_writes_no_audit` 等）**改成断言新行为**：

- 建单成功 ⇒ 返回 `deliverable_id` / `doc_no` / `detail`；
- **真库**里 `deliverables` 有一行 `deliverable_type='CHANGE_NOTICE'`，
  `matrix_id` **非空**；
- `change_notice_details` 有一行，`change_type` / `reason` 对得上；
- 写了一条审计 `CHANGE_NOTICE_CREATED`；
- **同项目第二张变更单也能建**（RF-8：唯一约束不撞）；
- 记录**不是** CHANGED ⇒ 422 `CHANGE_NOTICE_BAD_STATE`（保留既有契约）。

⚠️ 这些用例必须用**真 DB**（内存 SQLite），不能用原来的假 DB
（`_FakeSession` 只断言内存对象 ⇒ 看不到 NOT NULL / 唯一约束）⇒
这正是 P9A-DLV-009 说的「假 DB 把结构性问题藏起来」。

**Step 2: 新建观测测试（RED）**（`tests/services/test_change_notice_observation.py`）

1. 建单 ⇒ `workflow_progress` 有 **1 行**：
   `workflow_type='CHANGE_NOTICE'`、`workflow_id=变更单的 deliverable_id`、
   `step_order=1`、`step_role='CHANGE_NOTICE'`、`step_status='PENDING'`、
   `project_id=项目`。
2. 建单 ⇒ 观测行与建单**同一事务**（RF-6）：观测写失败 ⇒ 建单**也回滚**
   ⇒ 断言「没有 deliverables 行」。
3. 建单**不**把观测写成 COMPLETED（RF-5）⇒ 断言 `step_status == 'PENDING'`。

**Step 3: 跑测试确认失败**

Run: `cd pcs-backend && uv run pytest tests/services/test_change_notice_service.py tests/services/test_change_notice_observation.py -q`
Expected: FAIL（仍抛 `NotImplementedError`）。

**Step 4: 实现**

在 `create_change_notice` 里（删掉 `raise NotImplementedError` 与其后的
「不可达」注释块）：

```python
        # 1. 校验：record 必须存在且为 CHANGED 状态（保留原语义）
        ...
        # 2. 取矩阵（**惰性建行**：矩阵没人创建 ⇒ 变更单建不出来）
        matrix = await SignatureMatrixService.ensure_change_notice_matrix(
            db, project_id=project_id
        )
        # 3. 建 deliverables 行
        deliverable = Deliverable(
            project_id=project_id,
            deliverable_type="CHANGE_NOTICE",
            # ⚠️ scope 必须**逐单唯一**：`uq_deliverables_scope` =
            # (project_id, deliverable_type, scope_type, scope_value)
            # ⇒ 用 PROJECT_ALL/ALL 会让同一项目的**第二张**变更单插不进去。
            scope_type="CUSTOM",
            scope_value=f"CHANGE_NOTICE:{record_table.__name__ if record_table else ''}:{record_id}",
            parent_deliverable_id=None,
            doc_no=f"CN-{record_id.hex[:8].upper()}",
            doc_no_mode="MANUAL",
            title=f"变更单 - {change_type.value}",
            current_rev="0",
            version_purpose="ISSUED_FOR_CHANGE",
            sign_status=DeliverableSignStatus.PENDING,
            matrix_id=matrix.matrix_id,
        )
        db.add(deliverable)
        await db.flush()

        # 4. 1:1 扩展 change_notice_details（保留）
        ...
        # 5. **观测写入点 2a：变更单的「创建」**（ADR-0047 §① 🔒 service 层）
        await record_step(
            session=db,
            project_id=project_id,
            workflow_type=WorkflowType.CHANGE_NOTICE,
            workflow_id=deliverable.deliverable_id,
            step_order=1,
            step_role="CHANGE_NOTICE",
            state=WorkflowProgressState.PENDING,
            actor_user_id=getattr(actor, "user_id", None),
        )
        # 6. 审计 + commit（保留）
```

⚠️ `doc_no` 的唯一性：`uq_deliverables_doc_no` = (project_id, doc_no) ⇒
`CN-{record_id 前 8 位}` 对**不同记录**唯一，但**同一条记录**第二次建变更单
会撞 ⇒ 参照实现的 doc_no 生成器不处理这个 ⇒ **裁决**：doc_no 带上
`record_id` 的**全 32 位 hex**？⇒ 太长（doc_no 限 200 字符，无妨）。
⚠️ 但这样同一记录**仍然**撞（同一 record_id ⇒ 同一 doc_no）⇒
⇒ **裁决**：doc_no 加一个短后缀保证唯一：`f"CN-{record_id.hex[:8].upper()}-{uuid4().hex[:4].upper()}"`？
⚠️ 那就不是「可读编号」了。⇒ 更好：doc_no 用 record_id 全 hex（32 字符）：
`f"CN-{record_id.hex.upper()}"` ⇒ 同一记录仍撞。
⇒ **真正的解**：一条记录**只允许一张**变更单？ADR-0002/0008 没说。
⇒ **裁决**：doc_no = `f"CN-{record_id.hex[:8].upper()}"`，并在建单前检查
**该记录是否已有变更单** ⇒ 有 ⇒ 409 `CHANGE_NOTICE_ALREADY_EXISTS`
（明说：「这条记录已有变更单」）⇒ 既不撞唯一约束，也符合业务直觉
（一条记录同时只有一张进行中的变更单）。
⚠️ 这是**新增的业务约束**（原来没有）⇒ 必须在 commit message 与 SPEC 处登记。

**Step 5: 跑测试确认通过**

Run: `cd pcs-backend && uv run pytest tests/services/test_change_notice_service.py tests/services/test_change_notice_observation.py -q`
Expected: PASS。

**Step 6: 提交**

```bash
git add app/services/change_notice_service.py tests/services/
git commit -m "feat(TODO-057): 变更单创建落地 + ADR-0047 写入点 2a（创建时写观测）"
```

---

## Task T3：自动关闭路径写观测（写入点 2b）

**Files:**
- Modify: `pcs-backend/app/services/change_notice_service.py`
- Test: `tests/services/test_change_notice_observation.py`（追加）

**Step 1: 写失败测试**

1. `approve_change_notice` ⇒ `workflow_progress` 那一行变成 **COMPLETED**
   （`completed_at` 非空）。
2. 自动关闭前是 PENDING ⇒ 关闭后是 COMPLETED（RF-7）。
3. 审批**失败**（409 / 404）⇒ **不**写观测（不写「已完成」给一个没关闭的变更单）。

**Step 2: 跑测试确认失败** ⇒ FAIL（观测行仍是 PENDING）。

**Step 3: 实现**

在 `approve_change_notice` 里（审批通过、commit 之前）：

```python
        # ⚠️ **观测写入点 2b：变更单的「自动关闭」**（ADR-0047 §① 🔒）
        # 变更单 APPROVED ⇒ 它作为业务流程**结束** ⇒ 观测行标 COMPLETED。
        # ⚠️ 必须在**同一个事务**里（与业务状态同生共死）。
        await record_step(
            session=db,
            project_id=deliverable.project_id,
            workflow_type=WorkflowType.CHANGE_NOTICE,
            workflow_id=deliverable_id,
            step_order=1,
            step_role="CHANGE_NOTICE",
            state=WorkflowProgressState.COMPLETED,
            actor_user_id=getattr(actor, "user_id", None),
        )
```
⚠️ `record_step` 是 **upsert**（同键更新）⇒ 不需要先查那一行 ⇒
「没建过变更单却调了 approve」⇒ 会凭空造一行 ⇒ 但那种情况 `deliverable` 根本
不存在（404）⇒ 安全。

**Step 4: 跑测试确认通过 + 全量后端**

Run: `cd pcs-backend && uv run pytest tests/services/ -q` ⇒ PASS
Run: `cd pcs-backend && uv run pytest -q` ⇒ 全绿（基线 5168 passed / 77 skipped）

**Step 5: 提交**

```bash
git add app/services/change_notice_service.py tests/services/test_change_notice_observation.py
git commit -m "feat(TODO-057): ADR-0047 写入点 2b（变更单自动关闭时写观测）"
```

---

## Task T4：收口

- [ ] `uv run pytest -q` 全绿；`uv run alembic check` exit 0（**本批不改迁移** ⇒ 只需确认没漂）
- [ ] `bash pcs-backend/scripts/gate_08_openapi_contract.sh`（**本批不改契约** ⇒ 应无变化）
- [ ] `.wolf/buglog.json`：登记本批修掉的缺陷（若有）
- [ ] `TODOS.md`：**TODO-057 闭环**（措辞改成「已落地」，并写明
  「CHANGE_NOTICE 工作流只写 1 行」这个口径）；**P9A-DLV-007** 记「已落地 + 实现偏离」
  （R-6：推进/角色判定已在 B2 落地）；登记「变更申请 API 端点缺失」（若尚未登记）
- [ ] `.wolf/STATUS.md` 更新
- [ ] `spec/PCS-REQ-2026-002-SPEC-P9 …` §3.2.1 P9A-DLV-007 与 §7.2.1 验收状态：
  「部分（2/3）」⇒ **「3/3」**（P9A-OBS-002 的验收行）+ P9A-DLV-007 的实现偏离注记

## 验收（全 lane）

- [ ] `create_change_notice` 在**真库**上建出 `deliverables`（`matrix_id` 非空）
      + `change_notice_details` 两行，并写一条 `CHANGE_NOTICE_CREATED` 审计
- [ ] 同项目**第二张**变更单能建（唯一约束不撞，RF-8）；**同一条记录**的第二张
      变更单 ⇒ 409 `CHANGE_NOTICE_ALREADY_EXISTS`（明说）
- [ ] 建单 ⇒ `workflow_progress` 有一行 CHANGE_NOTICE / PENDING /
      `workflow_id = 变更单的 deliverable_id`
- [ ] 关闭（approve）⇒ 该行变 COMPLETED 且 `completed_at` 非空
- [ ] 观测写失败 ⇒ 建单**整体回滚**（同一事务）
- [ ] `parse_steps` 是唯一的 `steps_json` 解析口（`DeliverableService` 已改调它）
- [ ] 全量后端测试绿；契约无变化；无迁移改动

## 尚未解决的问题（开工前需裁决或登记）

1. **变更单仍无 HTTP 入口**（R-7）⇒ 「变更申请」按钮（SPEC §6.3）仍不可用
   ⇒ 需登记 `TODOS.md`（P9B-2 的 R-6 已依赖它）。
2. **「一条记录同时只有一张变更单」是本批新增的业务约束**（doc_no 唯一约束的
   副产品）⇒ 未经 SPEC 确认 ⇒ 须登记 + 在 SPEC 侧提修订。
3. **`record_approval_config` 批准深度**（TODO-054）仍未定义 ⇒ 变更单的 3 级
   校审是**矩阵**说了算，与记录层的批准深度是**两套** ⇒ 待 TODO-054 收口。
4. **ADR-0050（签署职责 / 工作集参与人员）**「先不做」⇒ 变更单的「谁该签这一步」
   仍是**全局角色**判定（`sign_role == actor_role`），不是项目内职责判定 ⇒
   与 ADR-0050 落地时可能要改。
5. **`signature_matrices` 仍无管理面** ⇒ 矩阵只能由本服务惰性建**内置**模板，
   项目自定义矩阵**建不了**（⇒ 交付物签发路径同样受阻）⇒ 登记。
