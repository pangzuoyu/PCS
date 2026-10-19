"""业务枚举（项目/角色/状态等数据库可空字符串字段的 Python 枚举映射）。

含 ProjectRole / WorkspaceType / WorkspaceStatus / ConfigStatus 等；
DB 字段使用 VARCHAR（不是 PG enum）以便演进，新枚举值直接加即可。
"""

import enum


class RecordSignStatus9(str, enum.Enum):
    """记录签审 9 态全集（核心 9 态机，P3 锁定）。

    业务：DRAFT/IN_APPROVAL/CHECKED/CHECK_REJECTED/STALE/CHANGE_PENDING/
    CHANGED/REVERSAL_PENDING/OBSOLETE 共 9 态；state_machine.ALLOWED_TRANSITIONS
    派生迁移表；前端 meta API 用此 enum 渲染状态色 + 按钮。
    """

    DRAFT = "DRAFT"
    IN_APPROVAL = "IN_APPROVAL"
    CHECKED = "CHECKED"
    CHECK_REJECTED = "CHECK_REJECTED"
    STALE = "STALE"
    CHANGE_PENDING = "CHANGE_PENDING"
    CHANGED = "CHANGED"
    REVERSAL_PENDING = "REVERSAL_PENDING"
    OBSOLETE = "OBSOLETE"


class StreamSignStatus(str, enum.Enum):
    """SIM-13 扩展为 9 态全集（与 RecordSignStatus9 字面对齐）。

    状态机迁移：P3 活跃 4 态 → 9 态全集（PG enum streamsignstatus ADD VALUE）。
    cerebrum 2026-09-08 锁定：值与 RecordSignStatus9 完全一致，PG enum 扩展不可逆。
    """

    DRAFT = "DRAFT"
    IN_APPROVAL = "IN_APPROVAL"
    CHECKED = "CHECKED"
    CHECK_REJECTED = "CHECK_REJECTED"
    STALE = "STALE"
    CHANGE_PENDING = "CHANGE_PENDING"
    CHANGED = "CHANGED"
    REVERSAL_PENDING = "REVERSAL_PENDING"
    OBSOLETE = "OBSOLETE"


class StreamPhase(str, enum.Enum):
    """物流主相态 4 态（`streams.phase`，可空）。

    ## 为什么是 4 值而不是 SPEC P3-SIM 写的 3 值

    SPEC「SIM 模块 输入」只列 VAPOR/LIQUID/MIXED，**漏了 SOLID**，而后端
    `import_service._phase_norm` 会把 P&ID/文件里的 `S`/`SOLID` 归一成
    `SOLID`（实测存在于真实导入路径）。砍掉它 ⇒ 固相在客户端渲染成空标签。
    按 CLAUDE.md「与 SPEC 冲突时以 OpenAPI 为准并登记 SPEC 修订」，本枚举
    是权威；SPEC 的三值表登记为待修订（见 `TODOS.md`）。

    与 `conflict_resolver._VALID_PHASES` 逐字一致（那处是校验侧的唯一来源，
    本枚举是声明侧的 —— 已加一致性测试锁住两者）。

    ⚠️ `import_service._phase_norm` 把 **MIXED 映射成 None**（避免 SIM-V01
    BLOCK：MIXED 必填两相组成，而 PRO/II parser 不抽组成），另用
    `is_mixed_phase` 布尔列保留「原始是混相」这一事实。所以 **MIXED 是
    合法值但导入路径暂不产出**，两者不矛盾。
    """

    VAPOR = "VAPOR"
    LIQUID = "LIQUID"
    MIXED = "MIXED"
    SOLID = "SOLID"


class StreamDataMode(str, enum.Enum):
    """物流数据模式 3 态（`streams.data_mode`，String(20)）。

    前端按此值渲染不同字段集（化学组成 / 石油特征 / 固体物料）。

    ⚠️ 2026-10-19 从 `app/services/meta_service.py` 搬到这里：原来它在
    service 层，而 `schemas/stream.py` 用裸 `str`，于是「meta 端点返的
    enum」与「响应 schema 接受的类型」是**两份互不引用的定义** ——
    改一处不会带动另一处（bug-187/188/189/190 全是这个形态）。
    现在只有一个来源。
    """

    CHEMICAL = "CHEMICAL"
    PETROLEUM = "PETROLEUM"
    SOLID = "SOLID"


class StreamSourceType(str, enum.Enum):
    """物流来源类型 13 值（`streams.source_type`，String(30)）。

    3 类人工/导入来源 + 10 类设备计算出口流。

    ⚠️ 契约的 description 此前只列了 5 个（SIM_IMPORT/MANUAL_ENTRY/
    LAB_REPORT/FLASH_CALCULATED/DEVICE_CALCULATED），**漏掉其中 10 个
    `*_CALCULATED`** —— 而 `outlet_stream.py` 的每个 persist 模块都在写它们。
    若当初有人照 description「收窄」枚举，13 个合法值会只剩 3 个。
    这正是「词表只写在散文里」的危害：散文既可能写少，也可能写错
    （`StreamResponse.sign_status` 的 description 就把 9 态写成了 4 态）。

    出口流那 10 个值由 `app/services/outlet_stream.py` 产出，引用本枚举而
    非散落字面量 —— `DEVICE_CALCULATED` 曾因散落写法被 Literal 遗漏过一次
    （A-03/C-05 LOW 修复记录在 outlet_stream 的注释里）。
    """

    # 人工/导入来源
    SIM_IMPORT = "SIM_IMPORT"
    MANUAL_ENTRY = "MANUAL_ENTRY"
    LAB_REPORT = "LAB_REPORT"
    # 设备计算出口流
    FLASH_CALCULATED = "FLASH_CALCULATED"
    PIPE_CALCULATED = "PIPE_CALCULATED"
    PUMP_CALCULATED = "PUMP_CALCULATED"
    PIPE_NET_CALCULATED = "PIPE_NET_CALCULATED"
    VESSEL_CALCULATED = "VESSEL_CALCULATED"
    SEP_EQUIP_CALCULATED = "SEP_EQUIP_CALCULATED"
    PSV_CALCULATED = "PSV_CALCULATED"
    HEAT_CALCULATED = "HEAT_CALCULATED"
    RESTRICTION_CALCULATED = "RESTRICTION_CALCULATED"
    DEVICE_CALCULATED = "DEVICE_CALCULATED"


class DeliverableSignStatus(str, enum.Enum):
    """交付物签审状态 4 态（DRAFT/PENDING/APPROVED/OBSOLETE）。

    业务：交付物版本全生命周期（草稿→待审→已批→作废）；与 record_sign_status
    不同的是交付物不参与 REVERSAL_PENDING（直接 APPROVED 后作废走 OBSOLETE）。
    """

    DRAFT = "DRAFT"
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    OBSOLETE = "OBSOLETE"


class WorkspaceType(str, enum.Enum):
    """工作区类型 3 类（FORMAL/PERSONAL/TEMPORARY）。

    业务：FORMAL 项目正式工作区（永久）、PERSONAL 个人草稿（90 天 TTL）、
    TEMPORARY 临时（7 天 TTL）；WorkspaceService.create 按此派生 retention_days。
    """

    FORMAL = "FORMAL"
    PERSONAL = "PERSONAL"
    TEMPORARY = "TEMPORARY"


class WorkspaceStatus(str, enum.Enum):
    """工作区状态（F-P3-003 Sprint 3, Issue 2 校准 — 仅 workspace 落地 2-state）。

    业务：ACTIVE 默认值，PATCH /workspaces/{id}/archive 改为 ARCHIVED。
    不删数据, 仅改 status. FK RESTRICT 允许显式删 (但当前无 DELETE 端点).

    与 ProjectStatus 5-state 区分: Project 维持仅 ACTIVE default (Issue 2 拆出),
    待业务需求驱动落地 ARCHIVED/IN_PROGRESS/CLOSED 等 5-state.
    """

    ACTIVE = "ACTIVE"
    ARCHIVED = "ARCHIVED"


class ProductCategory(str, enum.Enum):
    """项目产品类别 — GB 30251-2024 §6.1.5 电折标系数口径判据。

    业务: REFINING (炼油) / ETHYLENE (乙烯) ⇒ 电折标系数必须用**等价值**
    (0.21 kg标油/kWh, 附录A 表A.1 序号12); 其余产品用**当量值**
    (0.086 kg标油/kWh)。两者差 2.44 倍, 选错直接导致综合能耗虚低/虚高。

    裁决: 用户 2026-10-05「按 project 产品类型强制」— 不再由调用方自由传
    electricity_value_type。落 Project.product_category 列 + CHECK 约束。

    与 Project.project_type 区分: 那个是「项目类型」(CHEMICAL/NEW/... 无枚举
    无约束, 历史值含 test/t 等垃圾), 本列是**折标口径判据**, 有 CHECK 约束。
    """

    REFINING = "REFINING"
    ETHYLENE = "ETHYLENE"
    OTHER = "OTHER"


class GasMedium(str, enum.Enum):
    """工艺气体介质分类 (P7-6B 收尾 / GB 30251-2024 附录A 表A.1).

    业务: `utility_gas_media` 子表的判别列 (单位 Nm³), 每个值映射到一条
    ConfigEnergyConversionFactor 行:

    | gas_medium       | CONFIG energy_type | sub_type        | 附录A 序号 | kg标油/Nm³ |
    |------------------|--------------------|-----------------|-----------|-----------|
    | PROCESS_GAS      | GAS                | NULL            | —         | 0.85      |
    | NITROGEN         | NITROGEN           | NULL            | 33        | 0.15      |
    | PURIFIED_AIR     | INSTRUMENT_AIR     | PURIFIED        | 31        | 0.038     |
    | NON_PURIFIED_AIR | INSTRUMENT_AIR     | NON_PURIFIED    | 32        | 0.028     |
    | PLANT_AIR        | INSTRUMENT_AIR     | NON_PURIFIED    | 32        | 0.028     |

    背景 (2026-10-05): 这几类的 CONFIG 系数一直存在, 但 `_aggregate_util_subtables`
    的 `gas_nm3_yr` 是**硬编码 None** —— 系数是死数据, 氮气/仪表空气从未进过
    综合能耗。同时 SPEC V1.4 §4.4 的 13→6 映射写着「NITROGEN / INSTRUMENT_AIR /
    PLANT_AIR → None（无 TOE 折标）」, 与炼化强制国标 GB 30251-2024 冲突,
    以标准为准修订。

    PLANT_AIR (厂区空气) 归非净化: 附录A 只有净化/非净化两档压缩空气。
    """

    PROCESS_GAS = "PROCESS_GAS"
    NITROGEN = "NITROGEN"
    PURIFIED_AIR = "PURIFIED_AIR"
    NON_PURIFIED_AIR = "NON_PURIFIED_AIR"
    PLANT_AIR = "PLANT_AIR"


class SnapshotStatus(str, enum.Enum):
    """V3.3 § 4.1 字典；record_change_snapshots.snapshot_status 列。"""

    ACTIVE = "ACTIVE"
    CONSUMED = "CONSUMED"
    ABANDONED = "ABANDONED"


class EquipmentStatus(str, enum.Enum):
    """设备在项目生命周期中的分类（DICT-002 定义）。

    N = New 新建（项目新增设备）
    E = Existing 已有（改造项目利用的原有设备）
    D = Delete 删除/拆除（原有设备取消）
    M = Modified 修改（原有设备保留但需改造）
    F = Future 预留（规划中的未来设备位号）

    与 calc_status / actual_data_status / sign_status 互不替代，各自独立：
    - equipment_status：设备在项目里的角色
    - calc_status：设备计算是否完成
    - actual_data_status：供应商实际数据录入状态
    - sign_status：审批门禁 9 态
    """

    N = "N"
    E = "E"
    D = "D"
    M = "M"
    F = "F"


class CalcStatus(str, enum.Enum):
    """设备计算状态。

    NOT_CALCULATED 未计算 / CALCULATING 计算中 / COMPLETED 已完成 / NEED_RECALC 需重算
    """

    NOT_CALCULATED = "NOT_CALCULATED"
    CALCULATING = "CALCULATING"
    COMPLETED = "COMPLETED"
    NEED_RECALC = "NEED_RECALC"


class ActualDataStatus(str, enum.Enum):
    """供应商实际数据录入状态。

    NOT_ENTERED 未录入 / PENDING_CONFIRM 待确认 / CONFIRMED 已确认 / NEED_RECALC 需重算（ADR-0025）
    """

    NOT_ENTERED = "NOT_ENTERED"
    PENDING_CONFIRM = "PENDING_CONFIRM"
    CONFIRMED = "CONFIRMED"
    NEED_RECALC = "NEED_RECALC"


class StateTransition(str, enum.Enum):
    """Sprint 2 状态机 13 项事件（ADR-0002 + ADR-0024 锁定）。

    CONFIRM_CHANGE_PENDING 已合并到 RESOLVE_STALE_CHANGED（同一 STALE→CHANGE_PENDING 路径）。
    """

    SUBMIT_FOR_CHECK = "SUBMIT_FOR_CHECK"
    PASS_CHECK = "PASS_CHECK"
    REJECT_CHECK = "REJECT_CHECK"
    REQUEST_REVERSAL = "REQUEST_REVERSAL"
    APPROVE_REVERSAL = "APPROVE_REVERSAL"
    REJECT_REVERSAL = "REJECT_REVERSAL"
    INITIATE_CHANGE = "INITIATE_CHANGE"  # ADR-0002：CHECKED → CHANGE_PENDING 主动路径
    APPLY_CHANGE = "APPLY_CHANGE"
    ABANDON_CHANGE = "ABANDON_CHANGE"
    MARK_STALE = "MARK_STALE"
    RESOLVE_STALE_NO_CHANGE = "RESOLVE_STALE_NO_CHANGE"
    RESOLVE_STALE_CHANGED = "RESOLVE_STALE_CHANGED"
    OBSOLETE = "OBSOLETE"


class UserStatus(str, enum.Enum):
    """用户状态（ACTIVE 活跃 / DISABLED 禁用）。

    业务：用户登录有效性判定（auth 路由 login 校验）；DISABLED 用户禁止
    任何 token 颁发，但已签发 token 仍可使用至过期（兼容审计追溯）。
    """

    ACTIVE = "ACTIVE"
    DISABLED = "DISABLED"


class AuditAction(str, enum.Enum):
    """audit_logs.action 标准值。

    P0 + P1 完整集合（Issue 6 锁定，38 项）。所有值 ≤50 字符
    （test_audit_action_max_length_50 断言）。DB 字段类型 String(50)，
    零 migration 成本。
    """

    # === 认证/会话（P0） ===
    LOGIN_SUCCESS = "LOGIN_SUCCESS"
    LOGIN_FAILED = "LOGIN_FAILED"
    LOGOUT = "LOGOUT"
    TOKEN_REFRESHED = "TOKEN_REFRESHED"
    # F-P3-001 #5 (Sprint 3b): RBAC 401/403 拒绝事件 (含 429 限流命中)
    RBAC_DENIED = "RBAC_DENIED"
    # P9A (ADR-0046 §③): 停用用户登录被拒。没有它，停用策略完全无痕。
    USER_LOGIN_DENIED_DISABLED = "USER_LOGIN_DENIED_DISABLED"
    # P9A (ADR-0046 §⑤): 管理员停用某人。不留痕就无法追责「谁停的」。
    USER_DISABLED = "USER_DISABLED"

    # === 记录层 CRUD（P4-P6） ===
    RECORD_CREATED = "RECORD_CREATED"
    RECORD_UPDATED = "RECORD_UPDATED"
    RECORD_OBSOLETED = "RECORD_OBSOLETED"
    TAG_NUMBER_RELEASED = "TAG_NUMBER_RELEASED"  # P1.2 编号回滚

    # === CONFIG 元数据（F-P0-001 R1 / P7 Sprint 3 Issue 6）===
    CONFIG_R1_BACKFILL = "CONFIG_R1_BACKFILL"  # R1 修订折标系数回填 audit
    CONFIG_R1_REVISION = "CONFIG_R1_REVISION"  # 工艺室 R1 修订

    # === 状态机（P1 Sprint 2） ===
    RECORD_TRANSITION = "RECORD_TRANSITION"
    APPROVAL_STEP_PASSED = "APPROVAL_STEP_PASSED"
    APPROVAL_STEP_REJECTED = "APPROVAL_STEP_REJECTED"

    # === 变更管理（P1 Sprint 2） ===
    CHANGE_ABANDONED = "CHANGE_ABANDONED"
    CHANGE_INITIATED = "CHANGE_INITIATED"  # ADR-0002：主动发起变更
    CHANGE_REVERSAL_REQUESTED = "CHANGE_REVERSAL_REQUESTED"
    CHANGE_REVERSAL_APPROVED = "CHANGE_REVERSAL_APPROVED"
    CHANGE_REVERSAL_REJECTED = "CHANGE_REVERSAL_REJECTED"
    CHANGE_RESOLVED = "CHANGE_RESOLVED"
    # SIM-38（ADR-0008 变更单=交付物子类型）：变更单创建/审批/弃用审计
    CHANGE_NOTICE_CREATED = "CHANGE_NOTICE_CREATED"
    CHANGE_NOTICE_APPROVED = "CHANGE_NOTICE_APPROVED"
    CHANGE_NOTICE_CANCELLED = "CHANGE_NOTICE_CANCELLED"

    # === 快照（P1 Sprint 2） ===
    SNAPSHOT_CREATED = "SNAPSHOT_CREATED"
    SNAPSHOT_RESTORED = "SNAPSHOT_RESTORED"

    # === 血缘（P1 Sprint 3） ===
    LINEAGE_WRITTEN = "LINEAGE_WRITTEN"

    # === 变更影响分析（P1 Sprint 3） ===
    CIA_SCAN_STARTED = "CIA_SCAN_STARTED"
    CIA_SCAN_COMPLETED = "CIA_SCAN_COMPLETED"
    CIA_NOTIFIED = "CIA_NOTIFIED"
    CIA_NO_IMPACT = "CIA_NO_IMPACT"
    STALE_RESOLVED_NO_CHANGE = "STALE_RESOLVED_NO_CHANGE"
    STALE_RESOLVED_CHANGED = "STALE_RESOLVED_CHANGED"

    # === 工作区（P1 Sprint 1） ===
    WORKSPACE_CREATED = "WORKSPACE_CREATED"
    WORKSPACE_IMPORTED = "WORKSPACE_IMPORTED"
    WORKSPACE_CLEANED = "WORKSPACE_CLEANED"

    # === 输入清单（P1 Sprint 1） ===
    CHECKLIST_ITEM_VERIFIED = "CHECKLIST_ITEM_VERIFIED"
    CHECKLIST_ITEM_ASSUMED = "CHECKLIST_ITEM_ASSUMED"
    CHECKLIST_COMPLETENESS_BLOCKED = "CHECKLIST_COMPLETENESS_BLOCKED"

    # === 通用 CRUD ===
    READ = "READ"
    CREATE = "CREATE"
    UPDATE = "UPDATE"
    DELETE = "DELETE"

    # === 许可（P0） ===
    LICENSE_VIOLATION = "LICENSE_VIOLATION"

    # === 客户批准（P1.2 预留） ===
    CUSTOMER_APPROVAL_PROXIED = "CUSTOMER_APPROVAL_PROXIED"
    CUSTOMER_APPROVAL_ATTACHMENT_UPLOADED = "CUSTOMER_APPROVAL_ATTACHMENT_UPLOADED"

    # === CONFIG（P2 Sprint 1.1） ===
    CONFIG_ASSET_CREATED = "CONFIG_ASSET_CREATED"
    CONFIG_VERSION_CREATED = "CONFIG_VERSION_CREATED"
    CONFIG_ASSET_SUBMITTED = "CONFIG_ASSET_SUBMITTED"
    CONFIG_ASSET_APPROVED = "CONFIG_ASSET_APPROVED"
    CONFIG_ASSET_PUBLISHED = "CONFIG_ASSET_PUBLISHED"
    CONFIG_ASSET_OBSOLETED = "CONFIG_ASSET_OBSOLETED"
    CONFIG_ASSET_REJECTED = "CONFIG_ASSET_REJECTED"
    CONFIG_VERSION_DIFF_VIEWED = "CONFIG_VERSION_DIFF_VIEWED"

    # === P8 报表（ADR-P8-001 全直接生成路线）===
    REPORT_GENERATED = "REPORT_GENERATED"
    REPORT_DOWNLOADED = "REPORT_DOWNLOADED"
    # ⚠️ REPORT_FAILED **每次失败尝试都写一条**（用户 2026-10-09 裁决），
    # detail_json 带 {task_id, attempt_no}。不是只写最后一次：
    # ARQ 的 keep_result 默认 3600 秒，Redis 里的异常 1 小时后就清空，
    # audit_logs 是失败的**唯一**持久记录；而「失败过几次」本身是信号
    # （某类报表平均重试 2 次才成功 = 有系统性质量问题）。
    REPORT_FAILED = "REPORT_FAILED"
    # REPORT_BUILDER（Phase 2 b9）：每次执行写一条，含条件快照 + 行数
    REPORT_EXECUTED = "REPORT_EXECUTED"
    # 僵死任务回收（Task 7）：ARQ 进程被 kill 后状态卡在 PENDING，
    # 由 reclaim_stale_tasks 改成 FAILED 并写这条 —— 否则「为什么这一行
    # 变成 FAILED」查不到。
    REPORT_TASK_RECLAIMED = "REPORT_TASK_RECLAIMED"

    # REPORT_STYLE_CHANGED（c6）：样式改动。**公司标准必写、项目级不写**
    # —— 项目级改字号是日常操作，全写会把审计表淹掉，真正的公司标准
    # 改动反而淹没在里面。详见 style_service._audit。
    REPORT_STYLE_CHANGED = "REPORT_STYLE_CHANGED"


class ConfigStatus(str, enum.Enum):
    """配置资产状态（P2 Sprint 1.2 / SUP-001 §2.1 锁定）。

    5 态：DRAFT → PENDING → APPROVED → PUBLISHED → OBSOLETE。
    DRAFT 和 APPROVED 支持跳过审批的 OBSOLETE。
    """

    DRAFT = "DRAFT"
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    PUBLISHED = "PUBLISHED"
    OBSOLETE = "OBSOLETE"


class ConfigTransition(str, enum.Enum):
    """配置资产状态机事件（P2 Sprint 1.2）。

    SUBMIT/APPROVE/REJECT/PUBLISH/OBSOLETE 5 项；与 ConfigStatus 一一映射（除 OBSOLETE
    多入口）。单一来源：本枚举 + ConfigStateMachine.TRANSITIONS 是状态转移真理。
    """

    SUBMIT = "SUBMIT"
    APPROVE = "APPROVE"
    REJECT = "REJECT"
    PUBLISH = "PUBLISH"
    OBSOLETE = "OBSOLETE"


class PipeType(str, enum.Enum):
    """管道类型（SUP-008 OPEN-008，piping_results.pipe_type）。

    PUMP_SUCTION 泵吸入管 / PUMP_DISCHARGE 泵排出管 / SELF_FLOW 自流 /
    HEATING_STEAM 蒸汽伴热 / TWO_PHASE 两相流。
    """

    PUMP_SUCTION = "PUMP_SUCTION"
    PUMP_DISCHARGE = "PUMP_DISCHARGE"
    SELF_FLOW = "SELF_FLOW"
    HEATING_STEAM = "HEATING_STEAM"
    TWO_PHASE = "TWO_PHASE"


class CheckResult(str, enum.Enum):
    """流速校核结果（SUP-008 OPEN-008，piping_results.check_result）。

    PASS 合格 / FAIL 不合格 / WARNING 警告（接近上限）。
    """

    PASS = "PASS"
    FAIL = "FAIL"
    WARNING = "WARNING"


class PumpOperation(str, enum.Enum):
    """泵运行模式（SUP-008 OPEN-008，pump_results.pump_operation）。

    NORMAL 正常运行 / STANDBY 备用 / OFF 停运。
    """

    NORMAL = "NORMAL"
    STANDBY = "STANDBY"
    OFF = "OFF"


class DesignStage(str, enum.Enum):
    """设计阶段（SUP-008 OPEN-009，pump_results/psv_results/vessel_results.design_stage）。

    BASIC 基础设计 / DETAIL 详细设计。default BASIC。
    """

    BASIC = "BASIC"
    DETAIL = "DETAIL"


class FlowPattern(str, enum.Enum):
    """两相流流型（SUP-008 §8.3.4，two_phase_results.flow_pattern）。

    ANNULAR 环状流 / MIST 雾状流 / BUBBLE 泡状流 / SLUG 段塞流 /
    STRATIFIED 分层流 / WAVE 波状流（Baker 图判别）。
    """

    ANNULAR = "ANNULAR"
    MIST = "MIST"
    BUBBLE = "BUBBLE"
    SLUG = "SLUG"
    STRATIFIED = "STRATIFIED"
    WAVE = "WAVE"


class TwoPhaseCheck(str, enum.Enum):
    """两相流校核结果（SUP-008 §8.3.4，two_phase_results.two_phase_check）。

    PASS 合格 / WARNING 警告 / FAIL 不合格。
    """

    PASS = "PASS"
    WARNING = "WARNING"
    FAIL = "FAIL"


class ReliefScenario(str, enum.Enum):
    """泄放工况（SUP-008 §8.3.2 + P5-OPEN-005，relief_results.relief_scenario）。

    6 态（合并 P5 spec）：
    - FIRE 火灾
    - CLOSED_VALVE 出口阀关闭
    - REACTION_LOSS_OF_CONTROL 反应失控
    - BLOCKED_OUTLET 出口堵塞
    - COOLING_FAILURE 冷却失效
    - UPSET 异常扰动（SUP-008 §8.3.2 原 4 态无 UPSET；P5-OPEN-005 扩展为 6 态）

    历史：SUP-008 §8.3.2 仅列 4 态（FIRE/BLOCKED_OUTLET/COOLING_FAILURE/POWER_FAILURE）；
    POWER_FAILURE 在 P5-OPEN-005 合并版改为 UPSET（覆盖更广）。当前采纳 P5-OPEN-005 6 态。
    """

    FIRE = "FIRE"
    CLOSED_VALVE = "CLOSED_VALVE"
    REACTION_LOSS_OF_CONTROL = "REACTION_LOSS_OF_CONTROL"
    BLOCKED_OUTLET = "BLOCKED_OUTLET"
    COOLING_FAILURE = "COOLING_FAILURE"
    UPSET = "UPSET"



# ---------------------------------------------------------------------------
# M1 fix: 通用 helper — 跨 DB enum/str dual-format 兼容
# ---------------------------------------------------------------------------


def to_value(value) -> str:
    """接受 enum 或 str，返回底层 str value。

    用途：跨 DB 测试兼容性 — SQLite native_enum 自动降级为 VARCHAR，SQLAlchemy
    读回时 column 属性是 str 而非 enum。生产 PG 走 enum；测试 fixture 偶用 str 方便。

    Examples:
        >>> to_value(RecordSignStatus9.CHECKED)
        'CHECKED'
        >>> to_value("CHECKED")
        'CHECKED'

    Notes:
        bug-116 起源：sync_service 原本 `source.sign_status.value` 在 SQLite 测
        试 fixture 用 str 构造 PumpResult 时 AttributeError 失败。
        M1 fix：centralize 到此处供 sync_service + api/v1/equip_list + tests 复用。
    """
    if hasattr(value, "value"):
        return str(value.value)
    return str(value)
