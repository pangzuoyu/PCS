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

import type { RecordSignStatus } from './records';

export type StreamPhase = 'LIQUID' | 'VAPOR' | 'MIXED' | 'AQUEOUS';
/** 流子相态（饱和态细分）：过冷 SUBCOOLED / 饱和液 SAT_LIQUID / 饱和气 SAT_VAPOR / 过热 SUPERHEATED。 */
export type StreamSubphase = 'SUBCOOLED' | 'SAT_LIQUID' | 'SAT_VAPOR' | 'SUPERHEATED';

/** SIM 物流条目：流号 + 业务 tag + 流名 + 主相态/子相态 + 温压 + 双流量 + 组成 + 5 态机签名状态。 */
export interface Stream {
  stream_id: string;
  tag_number: string;
  stream_name: string;
  phase: StreamPhase;
  subphase?: StreamSubphase;
  /* ⚠️ 以下四个字段 2026-10-19 对齐契约 `StreamResponse`（TODO-039 审计）。
   *
   * 方向依据 **DICT-007-SUP-011 §4.4「与 Streams 表的映射」**：
   *     temperature_c  → temp
   *     pressure_mpag  → press
   *     mass_flow_kg_h → mass_flow
   * 所以契约对、前端错，改前端。
   *
   * ⚠️ `press` 尤其不能只看字段名：schema 原写「压力 kPa」，而 DICT 的
   * 源字段是 `pressure_mpag`（**MPaG**），后端其余压力字段也一律 MPaG
   * —— 那句 kPa 是后端写错的，本轮已改（app/schemas/stream.py 4 处 +
   * ORM 补 comment="MPaG"）。若只把 `pressure_mpa` 换成 `press` 而不
   * 同步后端描述，页面会显示「0.50 MPa」而真值是 500 kPa，**差 1000 倍
   * 且看起来完全合理**。
   */
  /** 温度 °C（契约 temp）。 */
  temp: number;
  /** 压力 */
  press: number;
  /** 质量流量 kg/h（契约 mass_flow）。 */
  mass_flow: number;
  /** 摩尔流量 kmol/h（契约 molar_flow）。 */
  molar_flow: number;
  /** 组分名 → 摩尔分率（SPEC §7.7.2 组成 JSON）。 */
  composition_json: Record<string, number>;
  /**
   * 签署状态。**九态全集**，与后端 `StreamSignStatus`（`app/models/enums.py:29`）
   * 逐字相同 —— 物流记录走的就是记录层状态机。
   *
   * ⚠️ 此前这里只声明了 **5 态**（漏掉 CHANGE_PENDING / CHANGED /
   * REVERSAL_PENDING / OBSOLETE），是**少声明**，不是「多了 STALE」。
   * 证据：`stream_service.py:258` 的锁定检查逐个点名物流的终态 ——
   * `CHECKED / STALE / CHANGED / OBSOLETE / CHECK_REJECTED / REVERSAL_PENDING`。
   *
   * 为什么会漏：当时按 `StateBadge` 的 `MODULE_ACTIVATED.SIM`
   * （4 态「强调」子集）反推了词表。但那张表**只决定 opacity**，
   * 从不做有效性检查 —— 把「渲染强调」当成「合法性约束」，
   * 于是反过来把合法的 4 个态判成了不存在（bug-180 的元教训）。
   */
  sign_status: RecordSignStatus;
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