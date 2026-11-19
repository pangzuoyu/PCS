/**
 * 设备台账 seed — 3 行（P10-C · T3 · TODO-157）
 *
 * ⚠️ **形状 = 契约 `EquipListResponse`**（18 个字段）⇒ ⇒ 不是手写副本。
 *
 * ⚠️ 第一行的位号 `132-P-101A/B` 与后端种子
 * （`pcs-backend/scripts/seed_e2e_flows.py::FLOW_EQUIPMENT_TAG`）**逐字一致**
 * ⇒ ⇒ 「种子设备在前端可见」这条断言有依据。
 */
import type { components } from '../../types/api';

type EquipListResponse = components['schemas']['EquipListResponse'];

export const seedEquipmentList: EquipListResponse[] = [
  {
    equipment_id: '33333333-3333-4333-8333-333333333333',
    equipment_type_project_id: '00000000-0000-0000-0000-000000000001',
    type_code: 'PUMP',
    equipment_name: 'E2E 种子泵',
    equipment_description: '蜡油加氢装置原料泵（后端种子的那一台）',
    tag_number: '132-P-101A/B',
    vendor: null,
    vendor_model: null,
    source_module: 'PUMP',
    source_service: null,
    source_record_id: null,
    procurement_status: null,
    installation_location: null,
    net_weight: null,
    equipment_status: 'A',
    sign_status: 'DRAFT',
    project_id: '00000000-0000-0000-0000-000000000001',
    workspace_id: '00000000-0000-0000-0000-000000000002',
    created_at: '2026-11-19T02:00:00Z',
    updated_at: '2026-11-19T02:00:00Z',
  },
  {
    equipment_id: '33333333-3333-4333-8333-333333333334',
    equipment_type_project_id: '00000000-0000-0000-0000-000000000001',
    type_code: 'HEAT',
    equipment_name: 'E-201 换热器',
    equipment_description: '塔底重沸器',
    tag_number: 'E-201',
    vendor: '中圣',
    vendor_model: 'BHS-400',
    source_module: 'HEAT',
    source_service: null,
    source_record_id: null,
    procurement_status: 'ORDERED',
    installation_location: '装置区 1',
    net_weight: 3200,
    equipment_status: 'B',
    sign_status: 'CHECKED',
    project_id: '00000000-0000-0000-0000-000000000001',
    workspace_id: '00000000-0000-0000-0000-000000000002',
    created_at: '2026-11-19T02:10:00Z',
    updated_at: '2026-11-19T02:10:00Z',
  },
  {
    equipment_id: '33333333-3333-4333-8333-333333333335',
    equipment_type_project_id: '00000000-0000-0000-0000-000000000001',
    type_code: 'VESSEL',
    equipment_name: 'V-101 分离器',
    equipment_description: null,
    tag_number: 'V-101',
    vendor: null,
    vendor_model: null,
    source_module: 'VESSEL',
    source_service: null,
    source_record_id: null,
    procurement_status: null,
    installation_location: null,
    net_weight: null,
    equipment_status: 'A',
    sign_status: 'IN_APPROVAL',
    project_id: '00000000-0000-0000-0000-000000000001',
    workspace_id: '00000000-0000-0000-0000-000000000002',
    created_at: '2026-11-19T02:20:00Z',
    updated_at: '2026-11-19T02:20:00Z',
  },
];
