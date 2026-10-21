/**
 * 6 个可编辑结果模块的**类型化描述符**（P9B-1 · SPEC §6.21）。
 *
 * ## 为什么是「一个通用页 + 6 个描述符」，不是 6 份页面
 *
 * 6 张结果表的差异只有五处：**record_type / 路径 / 主键名 / 字段清单 /
 * 偏移参数名**。其余（列表 / 编辑抽屉 / 取锁 / 心跳 / 基线 / 保存 / 409）
 * **全部共用** ⇒ 抄 6 份页面 = 抄 6 份 bug。
 *
 * ## ⚠️ 字段清单**只有这一处**
 *
 * `editableFields` 的类型是 `readonly (keyof TRes & string)[]`，
 * 而 `TRes` 是**各模块自己的响应类型**（生成的 `api.d.ts`）⇒
 * **字段名拼错 = 编译期错误**（改字段名时全仓一起红）。
 *
 * ⚠️ **只放标量业务字段**：`*_json` 与后端计算字段（`pass`）**不进表单**
 * —— 它们要么是 JSON 容器（表单渲染不了），要么是**后端算出来的**
 * （让人手改就等于造出第二套真相）。
 *
 * ## ⚠️ `sign_status` / `updated_at` **不是 6 张表都有**
 *
 * `cost_est_results` **没有**这两列（后端「1:1 跟随设备、状态跟设备」）⇒
 * `CommonResultRow` 里它们是**可选**的 ⇒
 * 「有没有状态门禁」由**行数据**决定（`isRowEditable`），不由模块写死。
 */
import type { components } from '../../types/api';
import { RESULT_BASES, type EditableRecordType } from '../../api/records';

export type CostEstResultResponse = components['schemas']['CostEstResultResponse'];
export type FiltrationResultResponse = components['schemas']['FiltrationResultResponse'];
export type FlareResultResponse = components['schemas']['FlareResultResponse'];
export type OpenChannelResultResponse = components['schemas']['OpenChannelResultResponse'];
export type PsychroResultResponse = components['schemas']['PsychroResultResponse'];
export type CoolTowerResultResponse = components['schemas']['CoolTowerResultResponse'];

/**
 * 页面通用读取所需的最小行形状。
 *
 * ⚠️ **只有 6 张表**共有**的列才设为必填**（`project_id` / `created_at` /
 * `record_hash?`）；`sign_status` / `updated_at` / `workspace_id` /
 * `tag_number` 在 `cost_est_results` 上**不存在** ⇒ 全部**可选**。
 */
export interface CommonResultRow {
  project_id: string;
  created_at: string;
  record_hash?: string | null;
  updated_at?: string | null;
  sign_status?: string | null;
  workspace_id?: string | null;
  tag_number?: string | null;
}

/** 一个字段的展示 / 表单元信息。 */
export interface ResultFieldDef {
  key: string;
  label: string;
  /** 数字字段用 `InputNumber`，文本字段用 `Input`。 */
  kind: 'number' | 'text';
  unit?: string;
  precision?: number;
}

export interface ResultModuleDef<TRes extends CommonResultRow = CommonResultRow> {
  recordType: EditableRecordType;
  base: string;
  /** ⚠️ 各不相同（实测）：cost-est / filtration / open-channel 用 `result_id`。 */
  pk: 'id' | 'result_id';
  route: string;
  title: string;
  /** 展示列 + 表单元信息的**唯一来源**（表单只渲染其中 `editableFields` 那部分）。 */
  columns: ResultFieldDef[];
  /** 可编辑字段（**只放标量业务字段**）。 */
  editableFields: readonly (keyof TRes & string)[];
}

/** 页面用的描述符形状（字段清单按 `string` 收窄 —— 逐模块的类型检查在各自 const 处完成）。 */
export type ResultModule = Omit<ResultModuleDef, 'editableFields'> & {
  editableFields: readonly string[];
};

// ---------------------------------------------------------------------------
// 字段清单（⚠️ 全部逐字取自各模块 `*UpdateRequest` 的**标量**字段，
// 排除 `expected_hash` / `expected_updated_at` / `*_json` / 计算字段 `pass`）
// ---------------------------------------------------------------------------

const COST_EST: ResultModuleDef<CostEstResultResponse> = {
  recordType: 'CostEstResult',
  base: RESULT_BASES.CostEstResult,
  pk: 'result_id',
  route: '/results/cost-est',
  title: '成本估算结果',
  columns: [
    { key: 'record_hash', label: '记录哈希', kind: 'text' },
    { key: 'estimated_cost', label: '估算成本', kind: 'number', unit: '', precision: 2 },
    { key: 'currency', label: '货币', kind: 'text' },
    { key: 'cost_index_year', label: '目标年', kind: 'number' },
    { key: 'base_cost', label: '基准年成本', kind: 'number', precision: 2 },
    { key: 'base_year', label: '基准年', kind: 'number' },
    { key: 'cepci_index_base', label: '基准年 CEPCI', kind: 'number', precision: 4 },
    { key: 'cepci_index_target', label: '目标年 CEPCI', kind: 'number', precision: 4 },
    { key: 'correlation_source', label: '关联式来源', kind: 'text' },
    { key: 'scaling_exponent', label: '缩放指数 n', kind: 'number', precision: 4 },
  ],
  editableFields: [
    'estimated_cost',
    'currency',
    'cost_index_year',
    'base_cost',
    'base_year',
    'cepci_index_base',
    'cepci_index_target',
    'correlation_source',
    'scaling_exponent',
  ],
};

const FILTRATION: ResultModuleDef<FiltrationResultResponse> = {
  recordType: 'FiltrationResult',
  base: RESULT_BASES.FiltrationResult,
  pk: 'result_id',
  route: '/results/filtration',
  title: '过滤结果',
  columns: [
    { key: 'tag_number', label: '位号', kind: 'text' },
    { key: 'sign_status', label: '状态', kind: 'text' },
    { key: 'record_hash', label: '记录哈希', kind: 'text' },
    { key: 'filter_type', label: '过滤形式', kind: 'text' },
    { key: 'media_type', label: '滤材类型', kind: 'text' },
    { key: 'area', label: '过滤面积', kind: 'number', unit: 'm²' },
    { key: 'cycle_time', label: '运行周期', kind: 'number', unit: 'h' },
    { key: 'pressure_drop', label: '压降', kind: 'number', unit: 'kPa' },
    { key: 'cake_resistance_alpha', label: '滤饼阻力 α', kind: 'number', precision: 6 },
    { key: 'specific_resistance_r0', label: '滤材比阻 r₀', kind: 'number', precision: 6 },
    { key: 'permeability_k', label: '渗透系数 k', kind: 'number', precision: 6 },
    { key: 'porosity_eps', label: '孔隙率 ε', kind: 'number', precision: 6 },
    { key: 'filter_velocity', label: '过滤速度', kind: 'number', unit: 'm/s' },
  ],
  editableFields: [
    'filter_type',
    'media_type',
    'area',
    'cycle_time',
    'pressure_drop',
    'cake_resistance_alpha',
    'specific_resistance_r0',
    'permeability_k',
    'porosity_eps',
    'filter_velocity',
  ],
};

const FLARE: ResultModuleDef<FlareResultResponse> = {
  recordType: 'flare_system_result',
  base: RESULT_BASES.flare_system_result,
  pk: 'id',
  route: '/results/flare',
  title: '火炬系统结果',
  columns: [
    { key: 'tag_number', label: '位号', kind: 'text' },
    { key: 'sign_status', label: '状态', kind: 'text' },
    { key: 'record_hash', label: '记录哈希', kind: 'text' },
    { key: 'calc_type', label: '计算类型', kind: 'text' },
    { key: 'total_relief_load_kg_h', label: '总泄放量', kind: 'number', unit: 'kg/h' },
    { key: 'header_diameter_mm', label: '总管直径', kind: 'number', unit: 'mm' },
    { key: 'header_mach', label: '总管马赫数', kind: 'number', precision: 4 },
    { key: 'header_pressure_drop_kpa', label: '总管压降', kind: 'number', unit: 'kPa' },
    { key: 'kod_diameter_mm', label: "KO'D 直径", kind: 'number', unit: 'mm' },
    { key: 'water_seal_height_mm', label: '水封高度', kind: 'number', unit: 'mm' },
    { key: 'stack_height_m', label: '烟囱高度', kind: 'number', unit: 'm' },
    { key: 'stack_diameter_m', label: '烟囱直径', kind: 'number', unit: 'm' },
    { key: 'radiation_at_grade_kw_m2', label: '地面辐射热流', kind: 'number', unit: 'kW/m²' },
    { key: 'radiation_limit_kw_m2', label: '辐射限值', kind: 'number', unit: 'kW/m²' },
    { key: 'flare_tip_diameter_mm', label: '火炬头直径', kind: 'number', unit: 'mm' },
    { key: 'steam_for_smokeless_kg_h', label: '无烟蒸汽量', kind: 'number', unit: 'kg/h' },
  ],
  editableFields: [
    'calc_type',
    'total_relief_load_kg_h',
    'header_diameter_mm',
    'header_mach',
    'header_pressure_drop_kpa',
    'kod_diameter_mm',
    'water_seal_height_mm',
    'stack_height_m',
    'stack_diameter_m',
    'radiation_at_grade_kw_m2',
    'radiation_limit_kw_m2',
    'flare_tip_diameter_mm',
    'steam_for_smokeless_kg_h',
  ],
};

const OPEN_CHANNEL: ResultModuleDef<OpenChannelResultResponse> = {
  recordType: 'OpenChannelResult',
  base: RESULT_BASES.OpenChannelResult,
  pk: 'result_id',
  route: '/results/open-channel',
  title: '明渠计算结果',
  columns: [
    { key: 'tag_number', label: '位号', kind: 'text' },
    { key: 'sign_status', label: '状态', kind: 'text' },
    { key: 'record_hash', label: '记录哈希', kind: 'text' },
    { key: 'channel_type', label: '渠型', kind: 'text' },
    { key: 'flow_rate', label: '流量', kind: 'number', unit: 'm³/s' },
    { key: 'depth', label: '水深', kind: 'number', unit: 'm' },
    { key: 'velocity', label: '流速', kind: 'number', unit: 'm/s' },
    { key: 'slope', label: '底坡', kind: 'number' },
    { key: 'critical_depth', label: '临界水深', kind: 'number', unit: 'm' },
    { key: 'froude_number', label: '弗劳德数', kind: 'number', precision: 4 },
    { key: 'manning_n', label: '曼宁系数 n', kind: 'number', precision: 4 },
    { key: 'hydraulic_radius', label: '水力半径', kind: 'number', unit: 'm' },
    { key: 'jump_type', label: '水跃形态', kind: 'text' },
    { key: 'conjugate_depth', label: '共轭水深', kind: 'number', unit: 'm' },
    { key: 'energy_loss', label: '能量损失', kind: 'number', unit: 'm' },
  ],
  editableFields: [
    'channel_type',
    'flow_rate',
    'depth',
    'velocity',
    'slope',
    'critical_depth',
    'froude_number',
    'manning_n',
    'hydraulic_radius',
    'jump_type',
    'conjugate_depth',
    'energy_loss',
  ],
};

const PSYCHRO: ResultModuleDef<PsychroResultResponse> = {
  recordType: 'psychro_result',
  base: RESULT_BASES.psychro_result,
  pk: 'id',
  route: '/results/psychro',
  title: '湿空气计算结果',
  columns: [
    { key: 'tag_number', label: '位号', kind: 'text' },
    { key: 'sign_status', label: '状态', kind: 'text' },
    { key: 'record_hash', label: '记录哈希', kind: 'text' },
    { key: 'humidity_ratio_kg_kg', label: '含湿量', kind: 'number', unit: 'kg/kg' },
    { key: 'dew_point_c', label: '露点温度', kind: 'number', unit: '℃' },
    { key: 'wet_bulb_c', label: '湿球温度', kind: 'number', unit: '℃' },
    { key: 'enthalpy_kj_kg', label: '焓', kind: 'number', unit: 'kJ/kg' },
    { key: 'specific_volume_m3_kg', label: '比容', kind: 'number', unit: 'm³/kg' },
    { key: 'sensible_heat_kw', label: '显热', kind: 'number', unit: 'kW' },
    { key: 'latent_heat_kw', label: '潜热', kind: 'number', unit: 'kW' },
    { key: 'saturation_w_kg_kg', label: '饱和含湿量', kind: 'number', unit: 'kg/kg' },
    { key: 'saturation_w_mg_sm3', label: '饱和含湿量', kind: 'number', unit: 'mg/m³' },
    { key: 'saturation_w_lb_per_mmscf', label: '饱和含湿量', kind: 'number', unit: 'lb/MMscf' },
    { key: 'saturation_T_c', label: '饱和温度', kind: 'number', unit: '℃' },
  ],
  editableFields: [
    'humidity_ratio_kg_kg',
    'dew_point_c',
    'wet_bulb_c',
    'enthalpy_kj_kg',
    'specific_volume_m3_kg',
    'sensible_heat_kw',
    'latent_heat_kw',
    'saturation_w_kg_kg',
    'saturation_w_mg_sm3',
    'saturation_w_lb_per_mmscf',
    'saturation_T_c',
  ],
};

const COOL_TOWER: ResultModuleDef<CoolTowerResultResponse> = {
  recordType: 'cooling_tower_result',
  base: RESULT_BASES.cooling_tower_result,
  pk: 'id',
  route: '/results/cool-tower',
  title: '冷却塔计算结果',
  columns: [
    { key: 'tag_number', label: '位号', kind: 'text' },
    { key: 'sign_status', label: '状态', kind: 'text' },
    { key: 'record_hash', label: '记录哈希', kind: 'text' },
    { key: 'tower_type', label: '塔型', kind: 'text' },
    { key: 'duty_kw', label: '热负荷', kind: 'number', unit: 'kW' },
    { key: 'water_flow_m3h', label: '水量', kind: 'number', unit: 'm³/h' },
    { key: 'makeup_water_m3h', label: '补水量', kind: 'number', unit: 'm³/h' },
    { key: 'fan_power_kw', label: '风机功率', kind: 'number', unit: 'kW' },
    { key: 'merkel_integral', label: 'Merkel 积分', kind: 'number', precision: 6 },
  ],
  editableFields: [
    'tower_type',
    'duty_kw',
    'water_flow_m3h',
    'makeup_water_m3h',
    'fan_power_kw',
    'merkel_integral',
  ],
};

/** 6 个模块（顺序 = 菜单顺序）。 */
export const RESULT_MODULES: readonly ResultModule[] = [
  COOL_TOWER,
  FILTRATION,
  FLARE,
  OPEN_CHANNEL,
  PSYCHRO,
  COST_EST,
];

/** 按 `recordType` 取模块（路由 / 菜单用）。 */
export function moduleByRecordType(recordType: EditableRecordType): ResultModule {
  const found = RESULT_MODULES.find((m) => m.recordType === recordType);
  if (!found) throw new Error(`未登记的结果模块：${recordType}`);
  return found;
}

/** 该模块的**可编辑字段元信息**（表单按它渲染）。 */
export function editableFieldDefs(module: ResultModule): ResultFieldDef[] {
  const editable = new Set<string>(module.editableFields);
  return module.columns.filter((c) => editable.has(c.key));
}
