/**
 * Meta seed fixture — 与 pcs-backend Task 4.5 V1.1 一致（P45-0-5）
 *
 * 19 组 enum + 13 事件状态机 + 7 角色权限矩阵 + 94 错误码
 *
 * 与 backend meta_service.py 单一来源派生；前端 seed 在 MSW 离线开发时
 * 返同样的数据结构（前端能完全离线跑 13 组件 + SchemaForm）。
 */

const STATE_META: Record<string, { color: string; icon: string }> = {
  DRAFT:              { color: "state-draft",           icon: "EditOutlined" },
  IN_APPROVAL:        { color: "state-in-approval",     icon: "LoadingOutlined" },
  CHECKED:            { color: "state-checked",         icon: "CheckCircleOutlined" },
  CHECK_REJECTED:     { color: "state-check-rejected",  icon: "CloseCircleOutlined" },
  STALE:              { color: "state-stale",           icon: "WarningOutlined" },
  CHANGE_PENDING:     { color: "state-change-pending",  icon: "EditOutlined" },
  CHANGED:            { color: "state-changed",         icon: "SwapOutlined" },
  REVERSAL_PENDING:   { color: "state-reversal-pending", icon: "UndoOutlined" },
  OBSOLETE:           { color: "state-obsolete",        icon: "StopOutlined" },
};

const LABEL_ZH: Record<string, string> = {
  DRAFT: "草稿", IN_APPROVAL: "批准中", CHECKED: "已批准",
  CHECK_REJECTED: "已退回", STALE: "数据存疑", CHANGE_PENDING: "变更中",
  CHANGED: "已变更", REVERSAL_PENDING: "撤销中", OBSOLETE: "已作废",
  PENDING: "待处理", APPROVED: "已批准", PUBLISHED: "已发布",
  NOT_CALCULATED: "未计算", CALCULATING: "计算中",
  COMPLETED: "已完成", NEED_RECALC: "需重算",
  NOT_ENTERED: "未录入", PENDING_CONFIRM: "待确认", CONFIRMED: "已确认",
  NORMAL: "正常", STANDBY: "备用", OFF: "停运",
  BASIC: "基础设计", DETAIL: "详细设计",
  ANNULAR: "环状流", MIST: "雾状流", BUBBLE: "泡状流",
  SLUG: "段塞流", STRATIFIED: "分层流", WAVE: "波状流",
  CHEMICAL: "化学品", PETROLEUM: "石油", SOLID: "固体",
  END_OF_RUN: "末期", START_OF_RUN: "开车", TURN_DOWN: "调节",
  MIN: "最小", MAX: "最大", ALTERNATE: "可替",
  FORMAL: "正式", PERSONAL: "个人", TEMPORARY: "临时",
  ACTIVE: "活跃", CONSUMED: "已消费", ABANDONED: "已废弃",
  PUMP_SUCTION: "泵吸入管", PUMP_DISCHARGE: "泵排出管",
  SELF_FLOW: "自流", HEATING_STEAM: "蒸汽伴热", TWO_PHASE: "两相流",
  PASS: "合格", FAIL: "不合格", WARNING: "警告",
};

function enumToDict(values: string[], withMeta = false) {
  return values.map((value, i) => {
    const item: { value: string; label: string; order: number; color?: string; icon?: string } = {
      value, label: LABEL_ZH[value] ?? value, order: i + 1,
    };
    if (withMeta && STATE_META[value]) {
      item.color = STATE_META[value].color;
      item.icon = STATE_META[value].icon;
    }
    return item;
  });
}

const NINE_STATES = [
  "DRAFT", "IN_APPROVAL", "CHECKED", "CHECK_REJECTED", "STALE",
  "CHANGE_PENDING", "CHANGED", "REVERSAL_PENDING", "OBSOLETE",
];

export const metaSeed = {
  enums: {
    RecordSignStatus: enumToDict(NINE_STATES, true),
    StreamSignStatus: enumToDict(NINE_STATES, true),
    DeliverableSignStatus: enumToDict(["DRAFT", "PENDING", "APPROVED", "OBSOLETE"]),
    WorkspaceType: enumToDict(["FORMAL", "PERSONAL", "TEMPORARY"]),
    EquipmentStatus: enumToDict(["N", "E", "D", "M", "F"]),
    CalcStatus: enumToDict(["NOT_CALCULATED", "CALCULATING", "COMPLETED", "NEED_RECALC"]),
    ActualDataStatus: enumToDict(["NOT_ENTERED", "PENDING_CONFIRM", "CONFIRMED", "NEED_RECALC"]),
    SnapshotStatus: enumToDict(["ACTIVE", "CONSUMED", "ABANDONED"]),
    ConfigStatus: enumToDict(["DRAFT", "PENDING", "APPROVED", "PUBLISHED", "OBSOLETE"]),
    ConfigTransition: enumToDict(["SUBMIT", "APPROVE", "REJECT", "PUBLISH", "OBSOLETE"]),
    PipeType: enumToDict(["PUMP_SUCTION", "PUMP_DISCHARGE", "SELF_FLOW", "HEATING_STEAM", "TWO_PHASE"]),
    CheckResult: enumToDict(["PASS", "FAIL", "WARNING"]),
    PumpOperation: enumToDict(["NORMAL", "STANDBY", "OFF"]),
    DesignStage: enumToDict(["BASIC", "DETAIL"]),
    FlowPattern: enumToDict(["ANNULAR", "MIST", "BUBBLE", "SLUG", "STRATIFIED", "WAVE"]),
    TwoPhaseCheck: enumToDict(["PASS", "WARNING", "FAIL"]),
    StreamDataMode: enumToDict(["CHEMICAL", "PETROLEUM", "SOLID"]),
    StreamCaseType: enumToDict(["NORMAL", "END_OF_RUN", "START_OF_RUN", "TURN_DOWN"]),
    StatePointCaseType: enumToDict(["NORMAL", "MIN", "MAX", "ALTERNATE"]),
  },

  stateMachine: {
    transitions: [
      // 9 态 → SUBMIT/OBSOLETE
      { from: "DRAFT", action: "SUBMIT_FOR_CHECK", to: "IN_APPROVAL",
        allowed_roles: ["APPROVER", "CHECKER", "DESIGNER", "SYSADMIN"],
        preconditions: [], side_effects: ["WRITE audit_log"] },
      { from: "DRAFT", action: "OBSOLETE", to: "OBSOLETE",
        allowed_roles: ["APPROVER", "CHECKER", "DESIGNER", "SYSADMIN"],
        preconditions: ["无下游引用"], side_effects: ["WRITE audit_log + 阻断下游引用", "AUDIT RECORD_OBSOLETED"] },
      // IN_APPROVAL → APPROVE/REJECT
      { from: "IN_APPROVAL", action: "PASS_CHECK", to: "CHECKED",
        allowed_roles: ["APPROVER", "CHECKER", "SYSADMIN"],
        preconditions: [], side_effects: ["WRITE audit_log", "AUDIT APPROVAL_STEP_PASSED"] },
      { from: "IN_APPROVAL", action: "REJECT_CHECK", to: "CHECK_REJECTED",
        allowed_roles: ["APPROVER", "CHECKER", "SYSADMIN"],
        preconditions: [], side_effects: ["WRITE audit_log", "AUDIT APPROVAL_STEP_REJECTED"] },
      // CHECK_REJECTED → RESUBMIT
      { from: "CHECK_REJECTED", action: "SUBMIT_FOR_CHECK", to: "IN_APPROVAL",
        allowed_roles: ["APPROVER", "CHECKER", "DESIGNER", "SYSADMIN"],
        preconditions: [], side_effects: ["WRITE audit_log"] },
      { from: "CHECK_REJECTED", action: "OBSOLETE", to: "OBSOLETE",
        allowed_roles: ["APPROVER", "CHECKER", "DESIGNER", "SYSADMIN"],
        preconditions: ["无下游引用"], side_effects: ["WRITE audit_log + 阻断下游引用", "AUDIT RECORD_OBSOLETED"] },
      // CHECKED → CHANGE / OBSOLETE
      { from: "CHECKED", action: "INITIATE_CHANGE", to: "CHANGE_PENDING",
        allowed_roles: ["DESIGNER", "SYSADMIN"],
        preconditions: ["绑定 ConfigAsset/ConfigVersion"], side_effects: ["CREATE record_change_snapshot", "AUDIT CHANGE_INITIATED"] },
      { from: "CHECKED", action: "MARK_STALE", to: "STALE",
        allowed_roles: ["DESIGNER", "CHECKER", "SYSADMIN"],
        preconditions: ["源快照哈希与下游比对不一致"], side_effects: ["AUDIT RECORD_TRANSITION"] },
      { from: "CHECKED", action: "OBSOLETE", to: "OBSOLETE",
        allowed_roles: ["APPROVER", "CHECKER", "DESIGNER", "SYSADMIN"],
        preconditions: ["无下游引用"], side_effects: ["WRITE audit_log + 阻断下游引用", "AUDIT RECORD_OBSOLETED"] },
      // STALE → CONFIRM_RECALC
      { from: "STALE", action: "RESOLVE_STALE_NO_CHANGE", to: "CHECKED",
        allowed_roles: ["CHECKER", "SYSADMIN"],
        preconditions: [], side_effects: ["AUDIT STALE_RESOLVED_NO_CHANGE"] },
      { from: "STALE", action: "RESOLVE_STALE_CHANGED", to: "CHANGE_PENDING",
        allowed_roles: ["CHECKER", "DESIGNER", "SYSADMIN"],
        preconditions: [], side_effects: ["CREATE record_change_snapshot", "AUDIT STALE_RESOLVED_CHANGED"] },
      { from: "STALE", action: "OBSOLETE", to: "OBSOLETE",
        allowed_roles: ["APPROVER", "CHECKER", "DESIGNER", "SYSADMIN"],
        preconditions: ["无下游引用"], side_effects: ["WRITE audit_log + 阻断下游引用", "AUDIT RECORD_OBSOLETED"] },
      // CHANGE_PENDING → APPROVE / REJECT
      { from: "CHANGE_PENDING", action: "APPLY_CHANGE", to: "CHANGED",
        allowed_roles: ["DESIGNER", "CHECKER", "SYSADMIN"],
        preconditions: [], side_effects: ["AUDIT CHANGE_RESOLVED"] },
      { from: "CHANGE_PENDING", action: "ABANDON_CHANGE", to: "CHECKED",
        allowed_roles: ["DESIGNER", "SYSADMIN"],
        preconditions: [], side_effects: ["AUDIT CHANGE_ABANDONED"] },
      { from: "CHANGE_PENDING", action: "OBSOLETE", to: "OBSOLETE",
        allowed_roles: ["APPROVER", "CHECKER", "DESIGNER", "SYSADMIN"],
        preconditions: ["无下游引用"], side_effects: ["WRITE audit_log + 阻断下游引用", "AUDIT RECORD_OBSOLETED"] },
      // CHANGED → REVERSE / OBSOLETE
      { from: "CHANGED", action: "REQUEST_REVERSAL", to: "REVERSAL_PENDING",
        allowed_roles: ["APPROVER", "CHECKER", "DESIGNER", "SYSADMIN"],
        preconditions: ["CHANGED 状态且未被交付物绑定"], side_effects: ["AUDIT CHANGE_REVERSAL_REQUESTED"] },
      { from: "CHANGED", action: "OBSOLETE", to: "OBSOLETE",
        allowed_roles: ["APPROVER", "CHECKER", "DESIGNER", "SYSADMIN"],
        preconditions: ["无下游引用"], side_effects: ["WRITE audit_log + 阻断下游引用", "AUDIT RECORD_OBSOLETED"] },
      // REVERSAL_PENDING → APPROVE / REJECT
      { from: "REVERSAL_PENDING", action: "APPROVE_REVERSAL", to: "CHECKED",
        allowed_roles: ["APPROVER", "SYSADMIN"],
        preconditions: ["存在 ACTIVE 快照"], side_effects: ["AUDIT CHANGE_REVERSAL_APPROVED"] },
      { from: "REVERSAL_PENDING", action: "REJECT_REVERSAL", to: "CHANGED",
        allowed_roles: ["APPROVER", "SYSADMIN"],
        preconditions: ["存在 ACTIVE 快照"], side_effects: ["AUDIT CHANGE_REVERSAL_REJECTED"] },
      // IN_APPROVAL OBSOLETE
      { from: "IN_APPROVAL", action: "OBSOLETE", to: "OBSOLETE",
        allowed_roles: ["APPROVER", "CHECKER", "DESIGNER", "SYSADMIN"],
        preconditions: ["无下游引用"], side_effects: ["WRITE audit_log + 阻断下游引用", "AUDIT RECORD_OBSOLETED"] },
    ],
    allowed: {
      DRAFT: ["SUBMIT_FOR_CHECK", "OBSOLETE"],
      IN_APPROVAL: ["PASS_CHECK", "REJECT_CHECK", "OBSOLETE"],
      CHECKED: ["INITIATE_CHANGE", "MARK_STALE", "OBSOLETE"],
      CHECK_REJECTED: ["SUBMIT_FOR_CHECK", "OBSOLETE"],
      STALE: ["RESOLVE_STALE_NO_CHANGE", "RESOLVE_STALE_CHANGED", "OBSOLETE"],
      CHANGE_PENDING: ["APPLY_CHANGE", "ABANDON_CHANGE", "OBSOLETE"],
      CHANGED: ["REQUEST_REVERSAL", "OBSOLETE"],
      REVERSAL_PENDING: ["APPROVE_REVERSAL", "REJECT_REVERSAL"],
      OBSOLETE: [],
    },
  },

  permissions: [
    { role: "DESIGNER", resource: "streams", action: "WRITE", permission_code: "STREAMS.WRITE", frontend_behavior: "show" },
    { role: "DESIGNER", resource: "pipe_classes", action: "WRITE", permission_code: "PIPE_CLASSES.WRITE", frontend_behavior: "show" },
    { role: "DESIGNER", resource: "pipe_codes", action: "WRITE", permission_code: "PIPE_CODES.WRITE", frontend_behavior: "show" },
    { role: "DESIGNER", resource: "config", action: "WRITE", permission_code: "CONFIG.WRITE", frontend_behavior: "show" },
    { role: "DESIGNER", resource: "stream_symbols", action: "WRITE", permission_code: "STREAM_SYMBOLS.WRITE", frontend_behavior: "show" },
    { role: "DESIGNER", resource: "imports", action: "WRITE", permission_code: "IMPORTS.WRITE", frontend_behavior: "show" },
    { role: "REVIEWER", resource: "pipe_classes", action: "WRITE", permission_code: "PIPE_CLASSES.WRITE", frontend_behavior: "show" },
    { role: "APPROVER", resource: "pipe_classes", action: "WRITE", permission_code: "PIPE_CLASSES.WRITE", frontend_behavior: "show" },
    { role: "APPROVER", resource: "config", action: "WRITE", permission_code: "CONFIG.WRITE", frontend_behavior: "show" },
    { role: "PROCESS_CONTROLLER", resource: "config", action: "WRITE", permission_code: "CONFIG.WRITE", frontend_behavior: "show" },
    { role: "PROCESS_CONTROLLER", resource: "stream_symbols", action: "WRITE", permission_code: "STREAM_SYMBOLS.WRITE", frontend_behavior: "show" },
    { role: "PROCESS_CONTROLLER", resource: "pipe_codes", action: "WRITE", permission_code: "PIPE_CODES.WRITE", frontend_behavior: "show" },
    { role: "PROCESS_CONTROLLER", resource: "imports", action: "WRITE", permission_code: "IMPORTS.WRITE", frontend_behavior: "show" },
    { role: "SYSTEM_ADMIN", resource: "*", action: "*", permission_code: "*", frontend_behavior: "show" },
    { role: "VIEWER", resource: "imports", action: "WRITE", permission_code: "IMPORTS.WRITE", frontend_behavior: "show" },
    // state_machine TRANSITION_ROLES
    { role: "CHECKER", resource: "state_machine", action: "PASS_CHECK", permission_code: "STATE_MACHINE.PASS_CHECK", frontend_behavior: "show" },
    { role: "CHECKER", resource: "state_machine", action: "MARK_STALE", permission_code: "STATE_MACHINE.MARK_STALE", frontend_behavior: "show" },
    { role: "DESIGNER", resource: "state_machine", action: "INITIATE_CHANGE", permission_code: "STATE_MACHINE.INITIATE_CHANGE", frontend_behavior: "show" },
    { role: "APPROVER", resource: "state_machine", action: "APPROVE_REVERSAL", permission_code: "STATE_MACHINE.APPROVE_REVERSAL", frontend_behavior: "show" },
    { role: "SYSADMIN", resource: "state_machine", action: "OBSOLETE", permission_code: "STATE_MACHINE.OBSOLETE", frontend_behavior: "show" },
  ],

  errorCodes: [
    { code: "MISSING_BEARER", http: 401, message: "Authorization: Bearer <token>", ui_behavior: "redirect_to_login" },
    { code: "WRONG_TOKEN_TYPE", http: 401, message: "not an access token", ui_behavior: "redirect_to_login" },
    { code: "INVALID_TOKEN", http: 401, message: "token 已失效", ui_behavior: "redirect_to_login" },
    { code: "INVALID_REFRESH", http: 401, message: "refresh token 已失效", ui_behavior: "redirect_to_login" },
    { code: "INVALID_CREDENTIALS", http: 401, message: "凭据无效", ui_behavior: "inline_form_error" },
    { code: "MOCK_DISABLED", http: 403, message: "mock auth is disabled in production", ui_behavior: "disable_with_tooltip" },
    { code: "SIM_STREAM_ROLE_FORBIDDEN", http: 403, message: "角色 ... 无权执行 ...", ui_behavior: "disable_with_tooltip" },
    { code: "RECORD_NOT_FOUND", http: 404, message: "记录 ... 不存在", ui_behavior: "block_toast" },
    { code: "PIPE_CLASS_NOT_FOUND", http: 404, message: "公司级等级 ... 不存在", ui_behavior: "block_toast" },
    { code: "STREAM_UNRELIABLE_BLOCKED", http: 422, message: "输入物流含不可靠流，拒绝下游计算", ui_behavior: "block_toast_with_trace" },
    { code: "FLASH_INPUT_ERROR", http: 422, message: "未支持的 calc_type", ui_behavior: "inline_field_error" },
    { code: "PIPE_CLASS_BAD_TRANSITION", http: 409, message: "非法状态流转", ui_behavior: "modal_confirm" },
    { code: "CHANGE_NOTICE_BAD_STATE", http: 422, message: "记录当前状态不能发起变更单", ui_behavior: "modal_confirm" },
    { code: "REVERSAL_BAD_STATE", http: 409, message: "记录当前状态不能批准撤销", ui_behavior: "modal_confirm" },
    { code: "STREAM_IMPORT_FILE_TOO_LARGE", http: 413, message: "文件过大", ui_behavior: "block_toast" },
    { code: "INTERNAL_ERROR", http: 500, message: "internal server error", ui_behavior: "block_toast_with_trace" },
  ],
};

export const MOCK_TOKEN = "mock-jwt-token";