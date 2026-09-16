/**
 * Stream 类型定义（P45-3-1 / Task 28）。
 *
 * SPEC §7.7 SIM 物流：
 * - 物流号 / 名称 / 相态 / 温压 / 流量 / 组成 / 状态
 *
 * TODO(api-migration): 此为 V1 极简版前端 mock props shape，与后端
 * StreamResponse 字段命名不一致（前端 temperature_c / pressure_mpa /
 * total_mass_flow_kg_h vs 后端 temp / press / mass_flow）。P5-1 完成
 * 后：
 * 1) 后端 OpenAPI 暴露完整 stream/tag 路径参数 → 跑 npm run api:gen
 * 2) 由 src/types/api.d.ts 的 StreamResponse 替换本页类型
 * 3) 现有 Page-level props shape 升级为 API DTO
 *
 * 见 docs/superpowers/plans/2026-09-16-p45-frontend-sprint-batch3.md
 * §"P5 契约冻结点"
 */

export type StreamPhase = 'LIQUID' | 'VAPOR' | 'MIXED' | 'AQUEOUS';
export type StreamSubphase = 'SUBCOOLED' | 'SAT_LIQUID' | 'SAT_VAPOR' | 'SUPERHEATED';

export interface Stream {
  stream_id: string;
  tag_number: string;
  stream_name: string;
  phase: StreamPhase;
  subphase?: StreamSubphase;
  temperature_c: number;
  pressure_mpa: number;
  total_mass_flow_kg_h: number;
  total_molar_flow_kmol_h: number;
  /** 组分名 → 摩尔分率（SPEC §7.7.2 组成 JSON）。 */
  composition_json: Record<string, number>;
  sign_status: 'DRAFT' | 'IN_APPROVAL' | 'CHECKED' | 'CHECK_REJECTED' | 'STALE';
  approved_hash?: string;
  updated_by?: string;
  updated_at?: string;
}

export const STREAM_PHASE_LABEL: Record<StreamPhase, string> = {
  LIQUID: '液相',
  VAPOR: '气相',
  MIXED: '混合',
  AQUEOUS: '水相',
};

export const STREAM_SUBPHASE_LABEL: Record<StreamSubphase, string> = {
  SUBCOOLED: '过冷',
  SAT_LIQUID: '饱和液',
  SAT_VAPOR: '饱和气',
  SUPERHEATED: '过热',
};