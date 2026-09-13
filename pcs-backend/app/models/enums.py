import enum


class RecordSignStatus9(str, enum.Enum):
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


class DeliverableSignStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    OBSOLETE = "OBSOLETE"


class WorkspaceType(str, enum.Enum):
    FORMAL = "FORMAL"
    PERSONAL = "PERSONAL"
    TEMPORARY = "TEMPORARY"


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

    # === 记录层 CRUD（P4-P6） ===
    RECORD_CREATED = "RECORD_CREATED"
    RECORD_UPDATED = "RECORD_UPDATED"
    RECORD_OBSOLETED = "RECORD_OBSOLETED"
    TAG_NUMBER_RELEASED = "TAG_NUMBER_RELEASED"  # P1.2 编号回滚

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

