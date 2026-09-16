/**
 * 工作区 + 清单 seed — 3 + 10 条（QA 11 组件实例化 P1）
 *
 * 3 类工作区（FORMAL/PERSONAL/TEMPORARY）触发 WorkspaceSwitcher 类型切换；
 * 10 项清单覆盖 5 个分组（PROCESS/EQUIPMENT/SAFETY/PIPING/PROJECT_DOC）。
 */
import type { Workspace } from '../../types/workspace';
import type { ChecklistItem } from '../../types/checklist';

export const seedWorkspaces: Workspace[] = [
  {
    workspace_id: 'ws-formal-001',
    workspace_type: 'FORMAL',
    name: '30 万吨乙烯项目',
    project_id: '00000000-0000-0000-0000-000000000001',
    owner_id: '0a0a03b8-d27e-4c65-9874c5e-d874c5eea0aa',
    created_at: '2026-08-01T09:00:00Z',
    last_active_at: '2026-09-16T03:00:00Z',
    retention_days: null,
  },
  {
    workspace_id: 'ws-personal-002',
    workspace_type: 'PERSONAL',
    name: '个人草稿空间',
    project_id: null,
    owner_id: '0a0a03b8-d27e-4c65-9874c5e-d874c5eea0aa',
    created_at: '2026-09-01T14:00:00Z',
    last_active_at: '2026-09-16T02:30:00Z',
    retention_days: null,
  },
  {
    workspace_id: 'ws-temp-003',
    workspace_type: 'TEMPORARY',
    name: '闪蒸试算 (临时)',
    project_id: null,
    owner_id: '0a0a03b8-d27e-4c65-9874c5e-d874c5eea0aa',
    created_at: '2026-09-16T01:00:00Z',
    last_active_at: '2026-09-16T02:55:00Z',
    retention_days: 7,
  },
];

/** 清单项 — 直接复用 ChecklistItem 类型（来自 /api/v1/checklist/projects/{project_id}） */

export const seedChecklist: ChecklistItem[] = [
  // 状态对齐 ChecklistStatus（NOT_STARTED/IN_PROGRESS/VERIFIED/ASSUMED/NOT_APPLICABLE）
  // 注意：InputChecklistPanel 的 STATUS_TO_BADGE 只映射这 5 态，其他值会令 StateBadge 收到 undefined 而崩。
  // PROCESS 组（3 项）
  { checklist_id: 'cl-001', project_id: '00000000-0000-0000-0000-000000000001', item_key: 'PROC-001', item_label: '工艺流程图 PFD', module: 'PROCESS', input_category: 'REQUIRED', required: true, input_value_json: null, source_type: null, status: 'VERIFIED', verified_by: 'bob', verified_at: '2026-09-10T10:00:00Z', assumption_reason: null, note: null },
  { checklist_id: 'cl-002', project_id: '00000000-0000-0000-0000-000000000001', item_key: 'PROC-002', item_label: '工艺物料平衡', module: 'PROCESS', input_category: 'REQUIRED', required: true, input_value_json: { value: 1.5 }, source_type: 'DESIGNER_INPUT', status: 'IN_PROGRESS', verified_by: null, verified_at: null, assumption_reason: null, note: null },
  { checklist_id: 'cl-003', project_id: '00000000-0000-0000-0000-000000000001', item_key: 'PROC-003', item_label: '公用工程平衡', module: 'PROCESS', input_category: 'CONDITIONAL', required: false, input_value_json: null, source_type: null, status: 'NOT_STARTED', verified_by: null, verified_at: null, assumption_reason: null, note: null },
  // EQUIPMENT 组（2 项）
  { checklist_id: 'cl-004', project_id: '00000000-0000-0000-0000-000000000001', item_key: 'EQ-001', item_label: '塔器设计', module: 'EQUIPMENT', input_category: 'REQUIRED', required: true, input_value_json: { value: 32 }, source_type: 'DESIGNER_INPUT', status: 'IN_PROGRESS', verified_by: null, verified_at: null, assumption_reason: null, note: null },
  { checklist_id: 'cl-005', project_id: '00000000-0000-0000-0000-000000000001', item_key: 'EQ-002', item_label: '换热器选型', module: 'EQUIPMENT', input_category: 'OPTIONAL', required: false, input_value_json: null, source_type: null, status: 'NOT_APPLICABLE', verified_by: null, verified_at: null, assumption_reason: null, note: '本项目无低温换热需求' },
  // SAFETY 组（2 项）
  { checklist_id: 'cl-006', project_id: '00000000-0000-0000-0000-000000000001', item_key: 'SAFE-001', item_label: 'HAZOP 分析', module: 'SAFETY', input_category: 'REQUIRED', required: true, input_value_json: null, source_type: null, status: 'ASSUMED', verified_by: null, verified_at: null, assumption_reason: '业主尚未提供 HAZOP 报告', note: '假设按同类项目经验取值' },
  { checklist_id: 'cl-007', project_id: '00000000-0000-0000-0000-000000000001', item_key: 'SAFE-002', item_label: '安全阀计算', module: 'SAFETY', input_category: 'REQUIRED', required: true, input_value_json: null, source_type: null, status: 'NOT_STARTED', verified_by: null, verified_at: null, assumption_reason: null, note: null },
  // PIPING 组（2 项）
  { checklist_id: 'cl-008', project_id: '00000000-0000-0000-0000-000000000001', item_key: 'PIPE-001', item_label: '管道等级表', module: 'PIPING', input_category: 'REQUIRED', required: true, input_value_json: { value: 5 }, source_type: 'DESIGNER_INPUT', status: 'VERIFIED', verified_by: 'bob', verified_at: '2026-09-12T15:00:00Z', assumption_reason: null, note: null },
  { checklist_id: 'cl-009', project_id: '00000000-0000-0000-0000-000000000001', item_key: 'PIPE-002', item_label: '管道应力分析', module: 'PIPING', input_category: 'CONDITIONAL', required: false, input_value_json: null, source_type: null, status: 'IN_PROGRESS', verified_by: null, verified_at: null, assumption_reason: null, note: null },
  // PROJECT_DOC 组（1 项）
  { checklist_id: 'cl-010', project_id: '00000000-0000-0000-0000-000000000001', item_key: 'DOC-001', item_label: 'BEDD 文档', module: 'PROJECT_DOC', input_category: 'REQUIRED', required: true, input_value_json: null, source_type: null, status: 'NOT_STARTED', verified_by: null, verified_at: null, assumption_reason: null, note: null },
];