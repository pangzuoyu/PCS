/**
 * PUMP 模块类型（P45-3-7 / Task 34）。
 *
 * SPEC §7.11.4：
 * - 输入：吸入口（容器压力/液位/管径/管件）+ 排出口（容器压力/静扬程/管径/管件）
 *       + 流量（normal/min/design）+ 效率（泵/电机）+ 控制阀压降
 * - 输出：扬程 / NPSH / 功率 / 设计压力 / 控制阀 Kv / 当量长度 / 压降分段
 *
 * TODO(api-migration): V1 极简版前端 mock props shape；P5-1 PumpCalculate
 * 端点冻结后由 src/types/api.d.ts 替换。
 */

export interface PumpSuction {
  vessel_pressure_mpa: number;
  liquid_level_m: number;
  pipe_dn: number;
  fittings_json: Record<string, number>;
}

export interface PumpDischarge {
  vessel_pressure_mpa: number;
  static_head_m: number;
  pipe_dn: number;
  fittings_json: Record<string, number>;
}

export interface PumpFlow {
  normal: number;
  min: number;
  design: number;
}

export interface PumpEfficiency {
  pump: number;
  motor: number;
}

export interface PumpInput {
  stream_id: string;
  suction: PumpSuction;
  discharge: PumpDischarge;
  flow: PumpFlow;
  efficiency: PumpEfficiency;
  control_valve_dp_kpa: number;
}

export interface PumpDpSegment {
  segment: string;
  dp_kpa: number;
}

export interface PumpResult {
  head_m: number;
  npsh_m: number;
  power_kw: number;
  design_pressure_mpa: number;
  control_valve_kv: number;
  equivalent_length_m: number;
  dp_breakdown: PumpDpSegment[];
}