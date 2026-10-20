# ADR-0050：签署职责与任务参与 —— 词表分层、资格上限、项目生命周期

- Status: **proposed**（待评审）
- Date: 2026-10-20
- Deciders: PCS 架构组（单人开发，用户裁决）
- Consulted: `app/services/deliverable_service.py`、`app/api/v1/records_actions.py`、
  `app/services/user_project_service.py`、`app/services/calc_lineage.py`、
  `app/services/state_machine.py`、`app/models/project.py`、`app/models/deliverable.py`、
  `app/api/v1/config.py`、`app/services/ldap_client.py`
- Informed: P9A 实施者、P9B 通知中心 / 待办栏、P10 部署与容量
- Supersedes: —（**取代 `TODOS.md` TODO-059**，后者是本 ADR 的一个切面）
- Superseded by: —
- Related: ADR-0047（观测层）、ADR-0049（通知与待办数据模型）、
  SPEC §5 权限与门禁、§5.5 参与人员门禁（本次增补）、
  `TODOS.md` TODO-048（`CostEstResult` 缺列）、TODO-054（记录侧角色链无定义来源）、
  TODO-055（注册表键风格不统一）、TODO-058（注册表语义与能力清单）
- 状态说明：本 ADR 全文的「实测」断言均于 2026-10-20 在本仓代码与**开发库 `pcs`**
  上复核过；复核命令与结果见文末「附录 A」。

---

## 背景

P9A-3「通知待办」lane 收口时，为确定「谁能签第 N 步」，撞出一个**贯穿全仓的词表问题**。
下面 5 条是实测事实，不是推测。

### ① 全仓有**三份**角色词表，且**已经漂移**

| 词表 | 位置 | 值集 |
|---|---|---|
| A：token 角色白名单 | `app/api/v1/config.py:523-526` `_ALLOWED_ROLES` | `DESIGNER` `PROCESS_CONTROLLER` `REVIEWER` `APPROVER` `SYSTEM_ADMIN` `VIEWER` `CHECKER`（7） |
| B：记录批准链 | `app/schemas/records_actions.py:58-66` `ApprovalRole` | `DESIGNER` `CHECKER` `REVIEWER` `APPROVER` `SYSTEM_ADMIN` `PROCESS_CONTROLLER` **`DATA_ADMIN`**（7） |
| C：项目内角色 | `app/services/user_project_service.py:29` `VALID_PROJECT_ROLES` | `DESIGNER` `CHECKER` `APPROVER` `REVIEWER` `VIEWER`（5） |

实测差集：

- **`VIEWER` 只在 A / C**，B 里没有 ⇒ 一个合法的 token 角色，在记录批准链里是**非法值**。
- **`DATA_ADMIN` 只在 B**，A 里没有 ⇒ 一个合法的 `ApprovalRole`，**发不出 token**
  （`current_actor` 抛 403 `INVALID_ROLE`）。
- 三者交集只有 4 值（`APPROVER` `CHECKER` `DESIGNER` `REVIEWER`）。

这三份清单**没有任何契约测试互相对齐**。它们不是「三份必须同步的副本」——
它们是**三个各自演化的概念**，恰好用了同一批字符串。

### ② 签署矩阵比的是**全局角色**，项目侧只查成员身份

`app/services/deliverable_service.py:533-538`：

```python
sign_role = str(step.get("sign_role", ""))
if sign_role != actor_role:          # actor_role = current_actor().role = token 的 role claim
    raise PcsError(
        code="SIGN_STEP_ROLE_MISMATCH",
        message=f"第 {step_index} 步要求角色 {sign_role}，当前角色 {actor_role}",
        status=403,
    )
```

项目那侧（`app/api/v1/deliverables.py:74-92` `_authorize` →
`check_project_access_or_404` → `UserProjectService.check_user_project_access`）
**只校验成员身份**，不看角色。

⇒ **「能签第 N 步」= 有 `user_projects` 有效授权 且 全局角色 == `step["sign_role"]`。**

### ③ `user_projects.role_in_project` 至今**零授权消费方**

`app/services/user_project_service.py:151-152`：

```python
if required_role is not None:
    return record.role_in_project == required_role
```

`check_user_project_access()` 有 `required_role` 参数且会比对 `role_in_project`，
但**全仓 4 个调用点没有一个传它**（`app/api/v1/_guard.py:42`、
`app/api/v1/equip_list.py:130`、`:181`、`app/services/report/style_service.py:223`）。
⇒ 那条比对分支是**死代码**。项目内角色只被存下来、在 `user_projects` 端点响应里显示，
**从未参与任何鉴权判定**。

### ④ 全局角色实际是**单值**，且映射顺序会静默降级

- `app/services/ldap_client.py:204-220` `resolve_role(groups)`：遍历组映射
  `for group_cn, role in mapping.items(): if group_cn in group_cns: return role`
  ⇒ **返回第一个命中**。默认映射表（`app/core/config.py:55-58`）里
  `DESIGNER_GROUP` 排第一 ⇒ 既是设计者又是复核者的人**登录后拿到 `DESIGNER`**。
- `app/services/ad_sync.py:125`：`roles=[role] if role else []` ⇒ **单元素列表**。
- `app/core/security.py:44` `create_access_token(*, subject, role, extra=None)`
  ⇒ token 只带**一个** `role` claim。
- `app/api/v1/config.py:470-481` `_Actor.role: str` 单值，
  `roles` 是返回 `[self.role]` 的 **property**（假列表）。

⇒ `users.roles` 虽是 JSONB 列表，但**实际永远只有 0 或 1 个元素**。

### ⑤ PCS 没有项目生命周期

`app/models/enums.py:150-160`（`WorkspaceStatus` 的 docstring，ProjectStatus 那句在 `:155`）：

> 与 ProjectStatus 5-state 区分: Project 维持仅 ACTIVE default (Issue 2 拆出),
> **待业务需求驱动落地** ARCHIVED/IN_PROGRESS/CLOSED 等 5-state.

`app/models/project.py:80`：`projects.status` 是 `String(20), default="ACTIVE"`，
**没有任何生命周期端点**。而且**全仓没有项目创建端点**（`app/api/v1/projects.py`
只有 `GET /{project_id}` 与 `PATCH`；全仓没有构造 `Project(...)` 的代码路径）。

⇒ **「项目开始前指定参与人员」这句话，目前没有可挂靠的时点。**

---

## 决策

### §① 词表分层（本 ADR 的地基）

用户 2026-10-20 给出的目标模型（逐字）：

> 全局角色**不是单值**，它包括这个角色**可以被赋予的签署职责**（A 角色有资格作为设计和审核，
> 而 B 角色只有资格设计）。**项目角色从全局角色中选取**，同时赋予其项目中
> **某个任务的单一签署职责**（A 角色在 A 项目 task1 是设计，task2 作为较核出现，
> 但在 B 项目只能作为较核）。**任务是指在项目下单一的工作集**
> （在 A 项目下，sim 是 task1、管径核算是 task2、泵计算是 task3）。

落地为五层：

| 层 | 是什么 | 载体 | 例子 |
|---|---|---|---|
| **全局角色** | 组织职务，**可多个** | DB `global_roles` | `DESIGNER` `CHECKER` `REVIEWER` `APPROVER` `PROCESS_CONTROLLER` `SYSTEM_ADMIN` `VIEWER` `DATA_ADMIN` |
| **签署职责** | 矩阵步骤要求的职能 | **机械派生**：`'Project-' ‖ 全局角色名` | `Project-DESIGNER` `Project-REVIEWER` |
| **资格集** | 全局角色 → **可被授予**的签署职责 | DB `global_role_sign_qualifications` | `DESIGNER → {Project-DESIGNER, Project-CHECKER}` |
| **工作集** | 项目下的**单一工作集**（=「任务」） | DB `work_sets` | `SIM` `PIPING` `PUMP` …（见 §④） |
| **项目内职责** | (用户, 项目, 工作集) → **单一**签署职责 | DB `user_project_sign_assignments` | 张三 @ 项目A / PIPING → `Project-DESIGNER` |

**分名的机械规则写进 schema**：`CHECK (sign_role LIKE 'Project-%')`。
**签署词表不另立清单** —— 它是 `global_roles` 的投影。

### §② 能力挂在全局角色上

`global_roles.can_create` / `can_review`。
签署职责 `Project-X` 的能力 = `X` 的能力（因为前缀是机械的）⇒ **零漂移**。

初始值（用户 2026-10-20 裁决：按 9 态机批准链）：

| 全局角色 | can_create | can_review | 依据 |
|---|---|---|---|
| `DESIGNER` | ✅ | ❌ | `state_machine.py:98` `SUBMIT_FOR_CHECK` 含 DESIGNER |
| `PROCESS_CONTROLLER` | ✅ | ❌ | 既有计算端点 ACL 一律 `DESIGNER/PROCESS_CONTROLLER/SYSTEM_ADMIN` |
| `CHECKER` | ❌ | ✅ | `state_machine.py:99` `PASS_CHECK` 含 CHECKER |
| `REVIEWER` | ❌ | ✅ | 4 档批准链 `DESIGNER→CHECKER→REVIEWER→APPROVER`（`RecordMixin.approval_depth` 1-4） |
| `APPROVER` | ❌ | ✅ | `PASS_CHECK` / `APPROVE_REVERSAL` 含 APPROVER |
| `SYSTEM_ADMIN` | ✅ | ✅ | 管理员兜底 |
| `VIEWER` | ❌ | ❌ | 只读 |
| `DATA_ADMIN` | ❌ | ❌ | 数据管理，无签署/创作权 |

> ⚠️ **一处容易被误读的地方**：`REVIEWER` **不在** `TRANSITION_ROLES` 里 ——
> `state_machine.py:97-108` 的 `SUBMIT_FOR_CHECK` = `{DESIGNER,CHECKER,APPROVER,SYSTEM_ADMIN}`、
> `PASS_CHECK` = `{CHECKER,APPROVER,SYSTEM_ADMIN}`。`REVIEWER` 来自**4 档批准链**
> （`RecordMixin.approval_depth` 1-4，`approval_role` 取自请求体）与 `ApprovalRole` 词表。
> 这两层的差别是**动作闸**与**职责档位**的差别，不是矛盾。

### §③ 参与人员 = 有项目内职责的人。**不另建「参与人员」表**

「参与人员」与「项目内职责」是**同一件事的两个说法**：
一个在 (项目, 工作集) 上有职责分配的人，就是那个工作集的参与人员。
另建一张 `project_participants` 表 = 同一件事的第二份清单 = 本仓反复付过代价的坑。

`user_project_sign_assignments` 的 `UNIQUE (user_id, project_id, work_set)`
就是「**单一签署职责**」的直接落地：一个用户在一个项目的一个工作集上只有一个职责。
（张三分身有术也不行 —— 那正是「单一职责」的意义。）

### §④ 工作集词表

用户裁决：**SIM 合成 1 个**；**每个工作集各有各的签署流程**；**工作集入 DB**。

| work_set | 覆盖的当前结果表（`RECORD_TYPE_REGISTRY` 键 / SIM 家族） |
|---|---|
| `SIM` | `sim_unit_op` `sim_tower` `sim_calculator` `sim_compressor` `sim_cstr` `sim_reactor` `sim_splitter` `sim_stca`（**8 张合成 1 个**） |
| `PIPING` | `PipingResult`（管径核算） |
| `PUMP` | `PumpResult`（泵计算） |
| `PIPE_NETWORK` | `PipeNetworkResult` |
| `HEAT` | `HeatResult` |
| `VESSEL` | `VesselResult` |
| `SEP_EQUIP` | `SepEquipResult` |
| `FLASH` | `FlashResult` |
| `TWO_PHASE` | `TwoPhaseResult` |
| `RELIEF` | `ReliefResult` |
| `COLUMN_SIZING` | `ColumnSizingResult` |
| `MIXER` | `MixerResult` |
| `CV` | `cv_result` |
| `RESTRICTION` | `restriction_result` |
| `FLARE` | `flare_system_result` |
| `COOLING_TOWER` | `cooling_tower_result` |
| `PSYCHRO` | `psychro_result` |
| `OPEN_CHANNEL` | `OpenChannelResult` |
| `FILTRATION` | `FiltrationResult` |
| `COST_EST` | `CostEstResult` |
| `THERMOSIPHON` | `ThermosiphonCirculationResult` |
| `STREAM` | `stream_symbols`（管道图） |
| `EQUIP` | 设备台账 |

⚠️ `ProjectCalculationStandardProfile` **不是工作集**（是配置），不入表。

⚠️ **键名不一致必须点名**：`RECORD_TYPE_REGISTRY`（`app/services/calc_lineage.py:83-113`）
的 21 个键里 **16 个 PascalCase + 5 个 snake_case**
（`cv_result` `restriction_result` `flare_system_result` `cooling_tower_result` `psychro_result`）。
而 **`record_comments.record_type` 列存的是客户端传的注册表键**
（`app/api/v1/records_actions.py:514` 写的是路径参数 `module` 本身，
经 `resolve_record_model()` 校验 ⇒ 只接受注册表键）
⇒ `cv_result` 这个键在 `record_comments.record_type` 里存的是 **`"cv_result"`，
不是 `"CvResult"`**。
⚠️ **本段原文（2026-10-20 写）写成「DB 列存类名」，是事实错误**：
把 `data_lineage.record_type`（`lineage.py:109` 确实写 `__class__.__name__`）
与 `record_comments.record_type` 混为一谈。实测同一张库里
`record_type` 这一列名**至少 3 种存法**（类名 / 表名 / 注册表键）。
⇒ **路径参数 `{module}` 与 `record_comments` 列都用注册表键**（唯一词表，
P9A-5 Task A / SPEC V2.0）；`data_lineage` / `record_change_snapshots`
存类名，属**历史存量**，本轮不动。

### §⑤ 三个判定函数（**唯一实现**）

```python
async def qualified_sign_roles(db, user_id) -> set[str]:
    """该用户因全局角色而【可被授予】的签署职责。"""

async def can_sign(db, *, user_id, project_id, work_set, required_sign_role) -> bool:
    """能签 (项目, 工作集) 的某一步吗。"""

async def can_participate(db, *, user_id, project_id, work_set, capability) -> bool:
    """能创建 / 能审阅该工作集的内容吗。capability ∈ {create, review}。"""
```

**通知收件人、待办、签署、创建、审阅，全部从这三个函数派生。**

> ⚠️ **上一轮的教训**（`/home/pangzy/code_project/PCS/.superpowers/sdd/PCS-PLAN-P9A-3-通知待办/progress.md`）：
> P9A C lane 曾把「共用一个 helper」当成防漂移的保证，结果**同一个 helper 被用出两个意思**
> —— 通知侧解析「全体用户里谁有这角色」，待办侧解析「我有没有这角色」，
> 方向相反 ⇒ 通知越权 + 待办缺项。
> ⇒ **本次的硬约束**：三个判定函数是**同一层**的（都回答「这个用户在这个项目这个工作集上能干什么」），
> 不允许任何一方自己再解析一遍角色。

**资格上限必须查两次**：

| 时机 | 挡什么 | 为什么不能只查一次 |
|---|---|---|
| **授权时** | 授予资格外的职责 | 防止把 `Project-APPROVER` 授给只有 `DESIGNER` 资格的人 |
| **使用时**（签署 / 创建 / 审阅） | 全局角色降级后**旧授权仍生效** | 人的全局角色会变（离职/调岗/AD 同步）。只在授权时查 ⇒ 降级后他仍能签 |

### §⑥ 项目生命周期 DRAFT → ACTIVE

用户裁决：时序门用**项目 DRAFT→ACTIVE**。

- `projects.status` 两态：`DRAFT`（准备中，可指定参与人员）/ `ACTIVE`（进行中）。
- **转态前置**：该项目**每个已声明工作集**（`project_work_sets`）都有 ≥1 名有效参与人员。
- ⚠️ **PCS 没有项目创建端点**（背景 §⑤ 实测）⇒ DRAFT 从哪来必须交代。
  本 ADR 决定：**新增 `POST /projects`**（创建即 DRAFT），并新增
  `POST /projects/{id}/start`（执行转态，校验前置）。
  这两笔属 **P2**，不在 P1。
- 项目涉及哪些工作集 ⇒ 新表 `project_work_sets (project_id, work_set)`。
  **不推导、不默认全选** —— 「这个项目做哪几块」是项目负责人的决定。
- 现有项目全部保持 `ACTIVE`（不迁数据）；`projects.status` 的 `default` 改为 `DRAFT`
  只影响**新建**项目。

### §⑦ 指定参与人员的权限 = **仅项目负责人**

`projects.owner_id`（`app/models/project.py:117`）。
不是 `PROCESS_CONTROLLER`，不是 `SYSTEM_ADMIN` —— 职责最分明，代价是单人瓶颈
（见「尚未解决」）。

### §⑧ 冻结规则

该工作集一旦有产出（记录 / 交付物），人员指定即**锁定**，改动走既有变更单机制
（ADR-0002 的 `CHANGE_NOTICE`）。

理由：「项目开始前指定」这句话若没有冻结约束就失去意义 ——
中途换人 = 职责分离被绕过（同一份工作可以由被复核者自己审）。

### §⑨ 与既有裁决的张力（**正面处理，不绕**）

`alembic/versions/p9_005_notifications.py:19-22` 与 `TODOS.md` TODO-058 的裁决：

> **不要在 DB 侧再开一份词表**（PG enum / CHECK 清单）——「Python 有哪些」与
> 「DB 允许哪些」两份清单必须同步维护，是本仓反复付过代价的坑。

本 ADR 把**两个词表放进 DB**，与它**表面冲突**。区别在于：

| | 既有裁决反对的 | 本 ADR 做的 |
|---|---|---|
| 形态 | 同一概念在 **Python 与 DB 各有一份硬编码清单** | **单一来源在 DB**，代码侧**不再复制** |
| 方向 | 反对「两份」 | 正是 TODO-058 裁决原话「**不给同一件事建两份人工清单**」的反面正确做法 |
| 例子 | `NotificationKind` 在 Python，DB 列放宽为 `String(40)` | 全局角色 / 工作集**以 DB 为准**，代码侧改为读 DB |

⇒ **配套义务（缺一不可）**：

1. **代码侧不得再保留全局角色 / 工作集的硬编码枚举。**
   改为启动时从 DB 读 + 运行时校验。
2. **契约测试断言「DB 词表 == 代码侧若有枚举」** ——
   照抄 `tests/architecture/test_notification_invariants.py`（AST 不变量）
   与 `alembic/versions/p8_011_streams_vocab_constraints.py`（**CHECK 值从枚举导入**
   + import 期断言 ORM 声明了同名约束）的做法。
3. ⚠️ **已知例外与债务**：`ApprovalRole` / `_ALLOWED_ROLES` / `VALID_PROJECT_ROLES`
   三份代码侧清单的**退役**属 **P4**（行为变更）。本 ADR 只登记债务与顺序，
   不在 P1 强行退役 —— 强制退役会让现有 24 个创建端点的 ACL 一次性变形。

### §⑩ 数据模型（DDL 草案）

> 迁移约定（`scripts/check_migration_idempotency.py` 的静态扫描要求）：
> `op.create_index` 必须 `if_not_exists=True`；`op.drop_index` / `op.drop_table`
> 必须 `if_exists=True`；`op.create_table` 的参数**白名单**只允许
> `Column` / `PrimaryKeyConstraint` / `UniqueConstraint` / `ForeignKeyConstraint` /
> `CheckConstraint` —— **其它参数被 alembic 静默丢弃**（bug-144 曾因此丢过 4 条外键）。
> 下面 DDL 已满足该白名单。

```sql
-- ① 全局角色词表（唯一来源）+ 能力
CREATE TABLE global_roles (
    role_name     VARCHAR(30)  PRIMARY KEY,
    display_name  VARCHAR(100) NOT NULL,
    description   TEXT,
    can_create    BOOLEAN NOT NULL DEFAULT false,
    can_review    BOOLEAN NOT NULL DEFAULT false,
    active        BOOLEAN NOT NULL DEFAULT true
);

-- ② 资格集：全局角色 → 可被授予的签署职责
CREATE TABLE global_role_sign_qualifications (
    global_role VARCHAR(30) NOT NULL REFERENCES global_roles(role_name),
    sign_role   VARCHAR(40) NOT NULL,
    PRIMARY KEY (global_role, sign_role),
    CONSTRAINT ck_gq_sign_role_prefix CHECK (sign_role LIKE 'Project-%')
);

-- ③ 工作集（项目下的单一工作集 = 「任务」）
CREATE TABLE work_sets (
    work_set     VARCHAR(40)  PRIMARY KEY,
    display_name VARCHAR(100) NOT NULL,
    description  TEXT,
    active       BOOLEAN NOT NULL DEFAULT true
);

-- ④ 工作集 ↔ 结果表（RECORD_TYPE_REGISTRY 的键）
CREATE TABLE work_set_record_types (
    work_set    VARCHAR(40) NOT NULL REFERENCES work_sets(work_set),
    record_type VARCHAR(60) NOT NULL,
    PRIMARY KEY (work_set, record_type)
);

-- ⑤ 项目涉及哪些工作集（转态前置的判据）
CREATE TABLE project_work_sets (
    project_id UUID NOT NULL REFERENCES projects(project_id),
    work_set   VARCHAR(40) NOT NULL REFERENCES work_sets(work_set),
    PRIMARY KEY (project_id, work_set)
);

-- ⑥ 项目内职责 = 参与人员名单
CREATE TABLE user_project_sign_assignments (
    assignment_id UUID PRIMARY KEY,
    user_id       UUID NOT NULL REFERENCES users(user_id),
    project_id    UUID NOT NULL REFERENCES projects(project_id),
    work_set      VARCHAR(40) NOT NULL REFERENCES work_sets(work_set),
    sign_role     VARCHAR(40) NOT NULL,
    granted_by    UUID REFERENCES users(user_id),
    granted_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    revoked_at    TIMESTAMPTZ,
    CONSTRAINT uq_upsa UNIQUE (user_id, project_id, work_set),
    CONSTRAINT ck_upsa_sign_role_prefix CHECK (sign_role LIKE 'Project-%')
);
```

**「签署职责」不建表** —— 它是 `global_roles` 的投影：
`sign_role = 'Project-' || global_roles.role_name`。
可用视图或派生函数提供，**不得**落成第二张表。

### §⑪ 矩阵绑定与交付物（P3 范围内，本 ADR 只定方向）

- `ProjectSignatureMatrixBinding`（`app/models/deliverable.py:168-186`）的语义
  从 (project, module) 改为 **(project, work_set)** ⇒ **每个工作集各有各的签署流程**
  （用户裁决）。
- `Deliverable` 增加 `work_set` 列。**不能从记录推导** —— 记录绑定发生在**签发之后**
  （B4 submit-approval），签发时还没有记录可依据。
- `steps_json[].sign_role` 的值加 `Project-` 前缀。
  成本：真库 `signature_matrices` **0 行**、`project_signature_matrix_bindings` **0 行**、
  后端与前端**都没有矩阵管理端点** ⇒ **零存量迁移**；代码与测试 **19 处 / 9 文件**机械改名。

> ⚠️ 顺带记录一处**既有不一致**：`ProjectSignatureMatrixBinding` 的 docstring 写着
> 「一个项目同一模块只能绑定一个矩阵（**matrix_id 唯一**）」，
> 但该表**没有任何 UniqueConstraint**（实测 `UniqueConstraint: []`）⇒ 那句注释是假的。
> P3 改造时一并补上唯一约束。

---

## 后果

### 正面

- **「谁能签 / 谁能创建 / 谁能审阅」有唯一实现。** 通知、待办、签署、创建、审阅
  全部从 `can_sign()` / `can_participate()` 派生 ⇒ 不再各自解析角色。
- **职责分离由结构保证**：「单一签署职责」（`UNIQUE(user_id, project_id, work_set)`）
  + 资格上限（资格集）⇒ 一个人在同一工作集上不可能既是设计者又是复核者。
- **词表单一来源。** 三份漂移的代码侧清单（`ApprovalRole` / `_ALLOWED_ROLES` /
  `VALID_PROJECT_ROLES`）在 P4 退役后，全仓只剩 DB 一份。
- **矩阵零存量。** 真库 0 矩阵 + 无管理端点 ⇒ `Project-` 前缀改造不撞任何数据。

### 负面 / 风险

- ⚠️ **P4 切 `sign_step` 判定是行为变更。** 切换后，一批当前**能签**的人会签不了
  （他们的全局角色 ≠ 矩阵要求），除非先在 `user_project_sign_assignments` 里
  补上对应职责。⇒ **切换顺序必须是「先补数据、再切代码」**，且要有过渡期双判。
- ⚠️ **P5 加门会首次暴露既有越权面。** 24 个创建端点里 **7 个当前没有项目守卫**：
  - `app/api/v1/restriction.py:61` `POST /restriction/calculate` ——
    **连 `current_actor` 依赖都没有**（实测该函数签名无 `user` 参数），
    任何未认证请求可往任意 `project_id` 写 `restriction_results` + outlet stream。
  - `app/api/v1/cost_est.py:93/169/227/290` —— 4 个，无项目守卫，
    且 `CostEstResult` **没有 `project_id` 列** ⇒ 加门前须先补列（TODO-048 同族）。
  - `app/api/v1/psv.py:260`、`app/api/v1/vessel.py:215` —— `project_id` 在源流上，
    但**没查用户是否属于该 stream 的项目**。
  - `app/api/v1/sep_equip.py:131` —— 条件式守卫，源流 `project_id` 为 NULL 时静默跳过。
  - `app/api/v1/equip_list.py:283` `POST /bulk-sync` —— 无项目守卫，
    请求体**连 `project_id` 字段都没有**。
  - `app/api/v1/records.py:116` `POST /records/piping` —— 无 `require_roles`
    （docstring 自陈 "Sprint 2 dev-only"）。
  - `app/api/v1/cv.py:41` —— 无 `require_roles`。
  ⇒ **建议先补守卫再加门**，否则「加参与人员门」会同时变成一次越权清扫，
  两件事混在一笔里，出问题时说不清是哪一层坏的。
- ⚠️ **没有公共层可插。** 记录创建**无 service 基类、无通用写 helper**
  （21 个模块各自 `save_*` / `persist_*`）；`app/services/calc_entry.py` 的
  `check_calc_inputs` 是**输入守卫**（物流状态），不是授权守卫，
  且只覆盖 10/24 个端点、签名里没有 actor ⇒ **不能把门加在它上面**。
  ⇒ 门落在 `app/api/v1/_guard.py`（与 `check_project_access_or_404` 并列），
  逐端点接线 —— 这正是 `_guard.py:9-10` 已定的本仓模式
  （「调用方只需在 endpoint 里加一行 await ...」）。
- ⚠️ **端到端测试可能恒绿。** `tests/conftest.py:239-248` 把
  `UserProjectService.check_user_project_access` monkeypatch 成**恒 True**。
  ⇒ 参与人员门**不能**落在那层之下（否则 HTTP 端到端测试永远通过），
  必须走独立路径，且契约测试要**直接断言端点函数体里出现了该调用**（AST）。
- ⚠️ **全局角色单值是独立缺陷**（背景 §④）。它与本 ADR 的口径选择**无关**：
  即使裁决维持「全局角色」口径，一人只有一档角色这件事仍会让
  「既是设计者又是复核者」的人无法承担两档职责。⇒ 单独排期（见「尚未解决」）。

### 迁移路径

| 期 | 内容 | 行为变更 |
|---|---|---|
| **P1** | 6 张表 + 迁移 `p9_006` + ORM + 种子 + 3 个判定函数 + 契约测试 | **无**（纯增量） |
| **P2** | 项目生命周期 DRAFT→ACTIVE + `project_work_sets` + `POST /projects` + `POST /projects/{id}/start` + 指定参与人员端点 | 有 |
| **P3** | 矩阵绑定改 (project, work_set) + `Deliverable.work_set` + `steps_json.sign_role` 加 `Project-` 前缀 + `issue` 带 work_set + 补矩阵绑定唯一约束 | 有（零存量） |
| **P4** | `sign_step` 切 `can_sign()` + token 多角色化 + 三份代码侧词表退役 + `role_in_project` 退役 | 有 |
| **P5** | 参与人员门挂 24 个创建/审阅端点 + 集合关系契约测试 | 有 |
| **P6** | 通知收件人 / 待办改为从 `can_sign()` 派生（P9A C lane 已落地的口径随之切换） | 有 |

**P1 的种子数据**（`global_roles` 8 行 + `global_role_sign_qualifications` + `work_sets` 23 行
+ `work_set_record_types`）沿用本仓既有做法：
真值放仓库文件（先例 `app/seeds/category3_defaults.json`），
启动时 `await ...seed(...)` 落库（先例 `app/main.py:56-59` 的
`CoefficientService.seed_default_tables` —— **先查后写、逐行增量、无新增不 commit**）。

⚠️ `app/main.py:56-59` 的 seed **失败会让应用起不来**（无 try/except）。
本仓已有对照：同文件 shutdown 路径的 `_close_redis_connections()`（`:95`）是
**显式吞异常**的。⇒ P1 的 seed 建议采用 shutdown 同款防护，或至少在 ADR 里记录该风险。

### 与其它文档的关系

- **ADR-0049**（通知与待办）：本 ADR **不改动**其 §①~§⑥；但 P6 会把
  ADR-0049 落地时用的「全局角色 ∩ 项目授权」口径换成 `can_sign()`。
  ⇒ ADR-0049 §「尚未解决」需回填一条指向本 ADR。
- **ADR-0047**（观测层）：不改动。
- **TODO-059**：**被本 ADR 取代**（它是本 ADR 的一个切面）。
- **TODO-054**（记录侧多级批准的角色链无定义来源）：本 ADR §② 的
  `global_roles.can_review` 给了记录侧一个**可配置**的角色来源 ——
  但 TODO-054 的「多级批准的角色**链**（第几档是谁）」仍未定义
  （本 ADR 只定义「谁能审」，不定义「第几档该谁审」）。
- **TODO-058**（注册表语义）：见 §⑨。
- **TODO-055**（注册表键风格不统一）：见 §④ 的键名不一致点名。

---

## 尚未解决

- **全局角色多值化**（背景 §④：`resolve_role` 只返第一个 / `ad_sync` 写单元素 /
  token 单 `role` claim / `_Actor.role` 单值）—— **与本 ADR 的口径选择无关**，
  是一条独立缺陷。修它要动 `ldap_client.resolve_role` + `token_issuer` +
  `create_access_token` 的 `role` claim（改列表）+ `current_actor` 的 `_Actor`。
  ⚠️ 动 token claim 是**全仓鉴权面**的变更，须单独排期与评审。
- **指定参与人员仅项目负责人 ⇒ 单人瓶颈**（用户裁决）。
  负责人离岗时谁来指定？是否需要「代理负责人」？本 ADR 不解决。
- **项目 DRAFT 期间能做什么？** DRAFT 只约束「转态前置」，
  但 DRAFT 期间是否允许创建记录 / 交付物？本 ADR 留白（P2 决定）。
- **`CostEstResult` 无 `project_id` 列** ⇒ 它的工作集归属与加门需先补列
  （TODO-048 同族，归属 D lane）。
- ~~**SPEC 的 `P9A-OBS-001~004` / `P9A-NOT-001~006` 至今不在 SPEC 里**
  （全文 grep 0 命中）—— ADR-0047 §后果 与 ADR-0049 §⑥ 承诺要写进去的条款
  **至今未写**。本次 SPEC 增补**不补**它们（超出本轮范围），
  但登记在此处免得又欠一笔。~~
  ✅ **已于 2026-10-21（P9A Z 收口）补写** —— `docs/PCS-UI-SPEC.md` V2.1：
  §6.22 TodoPanel（P9A-NOT-002）/ §6.23 RealtimeStatus（P9A-NOT-005/006）/
  §6.24 WorkflowProgressPanel（P9A-OBS-001~004）+ §6.20 扩写
  （P9A-NOT-001/003/004）。
- **「只读也能算参与人员吗」** —— `Project-VIEWER` 职责是否构成参与人员？
  本 ADR 规定：参与人员 = 有**任意**职责分配的人（含只读职责）。
  若产品认为只读不算，转态前置的判据要改。

---

## 附录 A：实测复核记录（2026-10-20）

| 断言 | 复核方式 | 结果 |
|---|---|---|
| 三份词表差集 | 脚本求 A/B/C 的 set 差 | A 独有 ∅；B 独有 `DATA_ADMIN`；C 独有 ∅；交集 4 值 |
| `sign_role` 比全局角色 | 读 `deliverable_service.py:533-538` | 确认，403 `SIGN_STEP_ROLE_MISMATCH` |
| `required_role` 无调用方 | `grep -rn "required_role=" app/` | 0 命中 |
| `resolve_role` 返回单值 | 读 `ldap_client.py:204-220` | 确认，`return role` 首个命中 |
| AD 同步写单元素 | `grep -n "roles=" app/services/ad_sync.py` | `:125` `roles=[role] if role else []` |
| `_Actor.role` 单值 | 读 `config.py:470-481` | 确认，`roles` 是 `[self.role]` 的 property |
| ProjectStatus 5-state 被拆出 | 读 `enums.py:155` | 确认 |
| 无项目创建端点 | `grep -rn "= Project(\|Project("`（排除 get_or_404 / class / import） | 0 命中 |
| `ProjectSignatureMatrixBinding` 无唯一约束 | 读 `Base.metadata.tables[...]` 的 `constraints` | `UniqueConstraint: []`（docstring 声称有） |
| `restriction.py:61` 裸奔 | 读该端点签名与函数体 | 无 `current_actor` / 无 `require_roles` / 无项目守卫 |
| `conftest` 恒真 monkeypatch | 读 `tests/conftest.py:239-248` | 确认，`check_user_project_access` → 恒 True |
| `RECORD_TYPE_REGISTRY` 键风格 | 脚本抽 21 键 | 16 PascalCase + 5 snake_case |
| `TRANSITION_ROLES` 角色集 | 读 `state_machine.py:97-108` | `SUBMIT_FOR_CHECK` 4 值 / `PASS_CHECK` 3 值，**均无 REVIEWER** |
| 矩阵绑定/矩阵表存量 | 查真库 `pcs` | `signature_matrices` 0 行；`project_signature_matrix_bindings` 0 行；`deliverables` 0 行 |
| `sign_role` 出现处 | `grep -rn '"sign_role"' app/ tests/` | 19 处 / 9 文件 |
| 迁移参数白名单 | 读 `scripts/check_migration_idempotency.py` | `create_table` 只允许 Column / PK / Unique / FK / Check |

---

## 附录 B：本轮用户裁决原文（2026-10-20）

1. **模型**：全局角色不是单值，它包括这个角色可以被赋予的签署职责（A 角色有资格作为设计和审核，
   B 角色只有资格设计）；项目角色从全局角色中选取，同时赋予其项目中某个任务的单一签署职责；
   任务是指在项目下单一的工作集。
2. **词表分名**：签署职责词表与全局角色词表彻底分名，签署词表在全局角色词表前加 `Project-` 作为区分。
3. **资格集载体**：使用数据库，并可以配置修改。
4. **能力初值**：按 9 态机批准链。
5. **时序门**：项目 DRAFT → ACTIVE。
6. **指定权限**：仅项目负责人。
7. **工作集**：SIM 合成 1 个；每个工作集各有各的签署流程；工作集也入 DB。
