/**
 * 物性 / 许用应力 / 毒性爆炸 seed — 各 3 条（QA 11 组件实例化 P1）
 *
 * 数值差异触发 NumericCell 等宽对齐 + 精度格式（significant / decimal）。
 */
import type { ComponentProperty, AllowableStress, ToxicityClass } from '../../types/common';

export const seedMaterials: ComponentProperty[] = [
  {
    component_id: 'm-001',
    name: '水',
    formula: 'H2O',
    cas_number: '7732-18-5',
    mw: 18.015,
    tc_k: 647.096,
    pc_mpa: 22.064,
    omega: 0.344,
  },
  {
    component_id: 'm-002',
    name: '乙醇',
    formula: 'C2H6O',
    cas_number: '64-17-5',
    mw: 46.068,
    tc_k: 513.92,
    pc_mpa: 6.137,
    omega: 0.649,
  },
  {
    component_id: 'm-003',
    name: '苯',
    formula: 'C6H6',
    cas_number: '71-43-2',
    mw: 78.114,
    tc_k: 562.05,
    pc_mpa: 4.895,
    omega: 0.210,
  },
  {
    component_id: 'm-004',
    name: '乙烯',
    formula: 'C2H4',
    cas_number: '74-85-1',
    mw: 28.054,
    tc_k: 282.34,
    pc_mpa: 5.041,
    omega: 0.087,
  },
];

export const seedAllowableStress: AllowableStress[] = [
  { material: 'A106-B', temperature_c: 38, allowable_stress_mpa: 137.9, standard: 'ASME' },
  { material: 'A106-B', temperature_c: 200, allowable_stress_mpa: 117.2, standard: 'ASME' },
  { material: 'A312-TP304', temperature_c: 38, allowable_stress_mpa: 137.9, standard: 'ASME' },
  { material: 'A312-TP304', temperature_c: 400, allowable_stress_mpa: 103.4, standard: 'ASME' },
];

export const seedToxicityClasses: ToxicityClass[] = [
  {
    component_id: 'm-002',
    name: '乙醇',
    ld50_mg_kg: 7060,
    pel_ppm: 1000,
    explosive_limit_json: { lel: 3.3, uel: 19.0 },
    hazard_class: 'LOW',
  },
  {
    component_id: 'm-003',
    name: '苯',
    ld50_mg_kg: 930,
    pel_ppm: 1,
    explosive_limit_json: { lel: 1.2, uel: 7.8 },
    hazard_class: 'HIGH',
  },
  {
    component_id: 'm-001',
    name: '水',
    explosive_limit_json: undefined,
    hazard_class: 'LOW',
  },
];