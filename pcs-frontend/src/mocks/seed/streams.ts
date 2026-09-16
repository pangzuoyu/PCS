/**
 * Stream seed — 5 条 SIM 物流（QA 11 组件实例化 P1）
 *
 * 状态覆盖 9 态中的 5 种以触发 StateBadge 多色渲染；温度/压力/流量差异
 * 触发 NumericCell 等宽对齐。
 */
import type { Stream } from '../../types/stream';
import type { SignatureRecord, SignatureStep } from '../../components/common/SignatureMatrix';
import type { ApprovalStep } from '../../components/common/ApprovalStepBar';
import type { Conflict } from '../../components/common/ConflictResolver';
import type { LineageNode, LineageEdge } from '../../components/common/LineageGraph';
import type { ChangeSource, AffectedRecord } from '../../components/common/ChangeImpactPanel';
import type { UiSchemaResponse } from '../../components/common/SchemaForm';

export const seedStreams: Stream[] = [
  {
    stream_id: 's-101',
    tag_number: 'S-101',
    stream_name: '进料物流',
    phase: 'LIQUID',
    subphase: 'SUBCOOLED',
    temperature_c: 25.5,
    pressure_mpa: 0.5,
    total_mass_flow_kg_h: 1000.0,
    total_molar_flow_kmol_h: 45.5,
    composition_json: { WATER: 0.6, ETHANOL: 0.4 },
    sign_status: 'CHECKED',
    approved_hash: 'a1b2c3d4e5f6789',
    updated_by: 'alice',
    updated_at: '2026-09-15T08:30:00Z',
  },
  {
    stream_id: 's-102',
    tag_number: 'S-102',
    stream_name: '塔顶蒸汽',
    phase: 'VAPOR',
    subphase: 'SAT_VAPOR',
    temperature_c: 78.4,
    pressure_mpa: 1.2,
    total_mass_flow_kg_h: 500.0,
    total_molar_flow_kmol_h: 22.7,
    composition_json: { ETHANOL: 0.95, WATER: 0.05 },
    sign_status: 'IN_APPROVAL',
    updated_by: 'bob',
    updated_at: '2026-09-16T03:15:00Z',
  },
  {
    stream_id: 's-103',
    tag_number: 'S-103',
    stream_name: '塔釜液',
    phase: 'LIQUID',
    subphase: 'SAT_LIQUID',
    temperature_c: 95.8,
    pressure_mpa: 1.1,
    total_mass_flow_kg_h: 480.0,
    total_molar_flow_kmol_h: 21.8,
    composition_json: { WATER: 0.97, ETHANOL: 0.03 },
    sign_status: 'DRAFT',
    updated_by: 'alice',
    updated_at: '2026-09-16T02:50:00Z',
  },
  {
    stream_id: 's-104',
    tag_number: 'S-104',
    stream_name: '回流',
    phase: 'LIQUID',
    subphase: 'SAT_LIQUID',
    temperature_c: 78.3,
    pressure_mpa: 1.3,
    total_mass_flow_kg_h: 320.0,
    total_molar_flow_kmol_h: 14.5,
    composition_json: { ETHANOL: 0.94, WATER: 0.06 },
    sign_status: 'STALE',
    approved_hash: 'b2c3d4e5f67890a',
    updated_by: 'carol',
    updated_at: '2026-09-14T16:20:00Z',
  },
  {
    stream_id: 's-105',
    tag_number: 'S-105',
    stream_name: '侧线采出',
    phase: 'MIXED',
    temperature_c: 85.0,
    pressure_mpa: 1.05,
    total_mass_flow_kg_h: 200.0,
    total_molar_flow_kmol_h: 9.1,
    composition_json: { ETHANOL: 0.55, WATER: 0.45 },
    sign_status: 'CHECK_REJECTED',
    approved_hash: 'c3d4e5f67890ab1',
    updated_by: 'dan',
    updated_at: '2026-09-15T11:00:00Z',
  },
];

// === Detail-page 8 组件实例化（P2 详情数据）===

/** 3 步校核/审核/审定（SPEC §6.2 + §6.19） */
export const seedSignatureMatrix: SignatureStep[] = [
  { step_index: 1, role: '设计' },
  { step_index: 2, role: '校核' },
  { step_index: 3, role: '审核' },
];

/** ApprovalStepBar 数据：当前走到 step 2（校核）+ step 1 已完成 + step 3 待办 */
export const seedApprovalSteps: ApprovalStep[] = [
  { step: 1, role: 'DESIGNER', roleLabel: '设计人', approver: 'alice', approvedAt: '2026-09-15T08:30:00Z', decision: 'APPROVED' },
  { step: 2, role: 'CHECKER', roleLabel: '校核人', approver: 'bob', approvedAt: '2026-09-16T03:00:00Z', decision: 'APPROVED' },
  { step: 3, role: 'APPROVER', roleLabel: '审核人' },
];

/** 签署记录：3 步全签 */
export const seedSignatures: SignatureRecord[] = [
  { step_index: 1, signer_name: 'alice', signed_at: '2026-09-15T08:30:00Z', record_hash: 'a1b2c3d4e5f6789' },
  { step_index: 2, signer_name: 'bob', signed_at: '2026-09-16T03:00:00Z', record_hash: 'd5e6f7a8b9c0d1e2' },
  { step_index: 3, signer_name: 'carol', signed_at: '2026-09-16T04:15:00Z', record_hash: 'f3a4b5c6d7e8f9a0' },
];

/** SIM 物性冲突 3 条（BLOCK/WARN/INFO） */
export const seedConflicts: Conflict[] = [
  { field: 'mw', field_label: '分子量', level: 'BLOCK', user_value: 46.07, calc_value: 46.068, user_unit: 'g/mol', calc_unit: 'g/mol', deviation_pct: '0.004%' },
  { field: 'bp', field_label: '沸点', level: 'WARN', user_value: 78.4, calc_value: 78.37, user_unit: '°C', calc_unit: '°C', deviation_pct: '0.04%' },
  { field: 'density', field_label: '密度', level: 'INFO', user_value: 789.0, calc_value: 789.5, user_unit: 'kg/m³', calc_unit: 'kg/m³', deviation_pct: '0.06%' },
];

/** 数据血缘：居中节点 + 上下游 */
export const seedLineageCenter = 's-101';
export const seedLineageNodes: LineageNode[] = [
  { id: 's-101', kind: 'stream', label: 'S-101 进料' },
  { id: 's-102', kind: 'stream', label: 'S-102 塔顶' },
  { id: 's-103', kind: 'stream', label: 'S-103 塔釜' },
  { id: 'e-t-201', kind: 'equipment', label: 'T-201 塔' },
  { id: 'assumed-pressure', kind: 'assumed', label: '压力（假设）', is_assumed: true },
];
export const seedLineageEdges: LineageEdge[] = [
  { source: 's-101', target: 'e-t-201', kind: 'reference' },
  { source: 'e-t-201', target: 's-102', kind: 'calculation' },
  { source: 'e-t-201', target: 's-103', kind: 'calculation' },
  { source: 'assumed-pressure', target: 's-101', kind: 'manual_override', hash_mismatch: true },
];

/** 变更影响：S-101 流量变更触发 3 条重算 */
export const seedChangeImpact: { source: ChangeSource; records: AffectedRecord[] } = {
  source: {
    description: 'S-101 · 流量 1000 → 1100 kg/h',
    changed_by: 'alice',
    changed_at: '2026-09-16T04:30:00Z',
  },
  records: [
    { record_id: 'pipe-p-1001', record_type: 'PIPE', tag_number: 'P-1001', result_label: '压降 8.5 → 9.2 kPa' },
    { record_id: 'pipe-p-1002', record_type: 'PIPE', tag_number: 'P-1002', result_label: '压降 12.0 → 12.8 kPa' },
    { record_id: 'pump-pu-301', record_type: 'PUMP', tag_number: 'PU-301', result_label: '扬程 24.5 → 25.3 m' },
  ],
};

/** SchemaForm UiSchema：stream 基础信息 6 字段 */
export const seedStreamUiSchema: UiSchemaResponse = {
  schema_version: '1.0.0',
  resource: 'stream',
  fields: [
    { path: 'tag_number', label: '物流号', widget: 'Input', required: true, readonly: true, order: 1 },
    { path: 'stream_name', label: '物流名称', widget: 'Input', required: true, order: 2 },
    { path: 'phase', label: '相态', widget: 'Select', required: true, order: 3 },
    { path: 'temperature_c', label: '温度', widget: 'NumberInput', unit: '°C', required: true, order: 4 },
    { path: 'pressure_mpa', label: '压力', widget: 'NumberInput', unit: 'MPa', required: true, order: 5 },
    { path: 'total_mass_flow_kg_h', label: '质量流量', widget: 'NumberInput', unit: 'kg/h', required: true, order: 6 },
  ],
};

/** GET /api/v1/streams/:id 返回的完整 payload（stream + 详情组件所需数据） */
export interface StreamDetailPayload {
  stream: Stream;
  matrix: SignatureStep[];
  signatures: SignatureRecord[];
  approvalSteps: ApprovalStep[];
  currentApprovalStep: number;
  conflicts: Conflict[];
  lineage: { center: string; nodes: LineageNode[]; edges: LineageEdge[] };
  changeImpact: { source: ChangeSource; records: AffectedRecord[] } | null;
  uiSchema: UiSchemaResponse;
}

export function buildStreamDetail(streamId: string): StreamDetailPayload | null {
  const stream = seedStreams.find((s) => s.stream_id === streamId);
  if (!stream) return null;
  return {
    stream,
    matrix: seedSignatureMatrix,
    signatures: seedSignatures,
    approvalSteps: seedApprovalSteps,
    currentApprovalStep: 2,
    conflicts: seedConflicts,
    lineage: { center: seedLineageCenter, nodes: seedLineageNodes, edges: seedLineageEdges },
    changeImpact: stream.sign_status === 'STALE' ? seedChangeImpact : null,
    uiSchema: seedStreamUiSchema,
  };
}
