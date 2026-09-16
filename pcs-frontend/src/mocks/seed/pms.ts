/**
 * PMS / BEDD seed — 4 + 3 条（QA 11 组件实例化 P1）
 *
 * PMS 项覆盖危险等级 LOW/MED/HIGH；状态覆盖 5 态。
 */
import type { PmsItem, BeddSection } from '../../types/pms';

export const seedPmsItems: PmsItem[] = [
  {
    item_id: 'pms-001',
    pms_no: 'PMS-CS-001',
    description: '碳钢管道一般工况',
    pms_class: 'CS-A',
    hazard_level: 'LOW',
    sign_status: 'CHECKED',
  },
  {
    item_id: 'pms-002',
    pms_no: 'PMS-SS-002',
    description: '不锈钢管道腐蚀性工况',
    pms_class: 'SS-B',
    hazard_level: 'MEDIUM',
    sign_status: 'IN_APPROVAL',
  },
  {
    item_id: 'pms-003',
    pms_no: 'PMS-AS-003',
    description: '合金钢高温高压',
    pms_class: 'AS-C',
    hazard_level: 'HIGH',
    sign_status: 'DRAFT',
  },
  {
    item_id: 'pms-004',
    pms_no: 'PMS-LTCS-004',
    description: '低温碳钢',
    pms_class: 'LTCS',
    hazard_level: 'MEDIUM',
    sign_status: 'STALE',
  },
];

export const seedBeddSections: BeddSection[] = [
  {
    section_id: 'bedd-001',
    title: '项目概况',
    content: '本项目为年产 30 万吨乙烯装置的工艺设计计算...',
    sign_status: 'CHECKED',
  },
  {
    section_id: 'bedd-002',
    title: '设计基础',
    content: '设计压力 1.0 MPaG，设计温度 -45~540℃...',
    sign_status: 'IN_APPROVAL',
  },
  {
    section_id: 'bedd-003',
    title: '物性数据',
    content: '主要介质：乙烯、丙烯、丙烷...',
    sign_status: 'DRAFT',
  },
];