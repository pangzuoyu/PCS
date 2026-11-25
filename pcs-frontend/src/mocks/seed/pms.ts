/**
 * PMS / BEDD seed（P10-H · T2 · TODO-195）。
 *
 * ⚠️ **形状照抄契约**（`PmsItemListResponse` / `BeddResponse` / `UiSchemaResponse`）
 * ⇒ ⇒ mock 通道与真后端**同一形状**（漂移棘轮盯着）。
 *
 * ⚠️ **BEDD 的 uiSchema 字段表是后端 `app/schemas/bedd.py::BEDD_FIELDS` 的镜像**
 * ⇒ ⇒ 两边必须同步 ⇒ ⇒ **漂移由一条前端测试盯着**
 * （`tests/mocks/bedd_ui_schema_drift.test.ts` ⇒ ⇒ 读后端源文件比对字段路径）
 * ⇒ ⇒ 「替身比被测物更宽容」这条老毛病在 BEDD 上被堵住了。
 */
import type { components } from '../../types/api';
import type { UiSchemaField } from '../../components/common/SchemaForm';

type PmsItemListResponse = components['schemas']['PmsItemListResponse'];
type BeddResponse = components['schemas']['BeddResponse'];

/** mock 通道的项目 id（与 `seed/workspaces.ts` 的 FORMAL 工作区一致）。 */
export const MOCK_PROJECT_ID = '00000000-0000-0000-0000-000000000001';

export const seedPmsList: PmsItemListResponse = {
  items: [
    {
      item_id: '11111111-1111-1111-1111-111111111101',
      project_id: MOCK_PROJECT_ID,
      pms_no: 'PMS-CS-001',
      description: '碳钢管道一般工况',
      pms_class: 'CS-A',
      hazard_level: 'LOW',
      sign_status: 'DRAFT',
      record_hash: 'a1b2c3d4e5f60718',
      created_by: null,
      created_at: '2026-09-10T10:00:00Z',
      updated_at: null,
    },
    {
      item_id: '11111111-1111-1111-1111-111111111102',
      project_id: MOCK_PROJECT_ID,
      pms_no: 'PMS-SS-002',
      description: '不锈钢管道腐蚀性工况',
      pms_class: 'SS-B',
      hazard_level: 'MEDIUM',
      sign_status: 'CHECKED',
      record_hash: 'b2c3d4e5f6071829',
      created_by: null,
      created_at: '2026-09-11T10:00:00Z',
      updated_at: null,
    },
  ],
  total: 2,
  limit: 100,
  offset: 0,
};

export const seedBedd: BeddResponse = {
  project_id: MOCK_PROJECT_ID,
  document: {
    meteorology: {
      temperature: 25.5,
      humidity: 60,
      pressure: 101.3,
      wind: 3.2,
      rainfall: 600,
      snowfall: null,
      evaporation: 1200,
      thunderstorm: 12,
      fog: 5,
      sunshine: 2200,
      solar_radiation: 500,
      soil: '壤土',
      dust: null,
      altitude: 10,
    },
    hydrology_geology: { tidal: null, river: '厂区北侧 2 km', geology: '粉质黏土' },
    seismic: { intensity: '7 度', acceleration: 0.1, group: '第三组', site_category: 'Ⅱ 类' },
    utilities: {
      steam: '自产 1.0 MPa',
      water: '厂内循环水',
      air: '空压站',
      nitrogen: '空分',
      fuel_gas: '自产',
      fuel_oil: null,
      hydrogen: null,
      chemicals: '外购',
      heat_transfer_oil: null,
      condensate: '回收',
      electrical: '110 kV 双回路',
    },
    emission_limits: {
      gas: 'GB 14554',
      incineration: 'GB 18484',
      dust: 'GB 16297',
      wastewater: 'GB 8978',
      noise: 55,
      workplace_air: 'GBZ 2.1',
    },
    design_criteria: { design_life: 20, operation: '连续', transportation: null, noise: 60 },
    safety_fire: {
      fire_pump: '2 台 × 100%',
      fire_truck: '2 台',
      foam: '3%',
      sprinkler: '全厂覆盖',
      detection: '火焰+可燃气体',
      isolation_valve: '电动',
      safety_shower: '每 30 m',
    },
    flare: { back_pressure: 101.3, radiation: 4.73 },
    interface_conditions: { inlet: '详见附件 A-01', outlet: '详见附件 A-02' },
  },
  updated_at: '2026-09-12T08:00:00Z',
};

/**
 * BEDD 的 uiSchema 字段（**后端 `BEDD_FIELDS` 的镜像** ⇒ ⇒ 路径与标签逐条相同）。
 *
 * ⚠️ 控件类型与后端一致（Input / NumberInput）⇒ ⇒ 前端 SchemaForm 渲染一致。
 */
const BEDD_UI_FIELDS: Array<
  [string, string, string, 'number' | 'text', string | null]
> = [
  ['meteorology', 'temperature', '温度', 'number', 'degC'],
  ['meteorology', 'humidity', '湿度', 'number', '%'],
  ['meteorology', 'pressure', '气压', 'number', 'kPa'],
  ['meteorology', 'wind', '风', 'number', 'm/s'],
  ['meteorology', 'rainfall', '降雨', 'number', 'mm/a'],
  ['meteorology', 'snowfall', '雪', 'number', 'mm/a'],
  ['meteorology', 'evaporation', '蒸发', 'number', 'mm/a'],
  ['meteorology', 'thunderstorm', '雷暴', 'number', 'd/a'],
  ['meteorology', 'fog', '雾', 'number', 'd/a'],
  ['meteorology', 'sunshine', '日照', 'number', 'h/a'],
  ['meteorology', 'solar_radiation', '太阳辐射', 'number', 'W/m2'],
  ['meteorology', 'soil', '土壤', 'text', null],
  ['meteorology', 'dust', '粉尘', 'text', null],
  ['meteorology', 'altitude', '海拔', 'number', 'm'],
  ['hydrology_geology', 'tidal', '潮汐', 'text', null],
  ['hydrology_geology', 'river', '河流', 'text', null],
  ['hydrology_geology', 'geology', '地质', 'text', null],
  ['seismic', 'intensity', '设防烈度', 'text', null],
  ['seismic', 'acceleration', '加速度', 'number', 'g'],
  ['seismic', 'group', '分组', 'text', null],
  ['seismic', 'site_category', '场地类别', 'text', null],
  ['utilities', 'steam', '蒸汽', 'text', null],
  ['utilities', 'water', '水', 'text', null],
  ['utilities', 'air', '空气', 'text', null],
  ['utilities', 'nitrogen', '氮气', 'text', null],
  ['utilities', 'fuel_gas', '燃料气', 'text', null],
  ['utilities', 'fuel_oil', '燃料油', 'text', null],
  ['utilities', 'hydrogen', '氢气', 'text', null],
  ['utilities', 'chemicals', '化学品', 'text', null],
  ['utilities', 'heat_transfer_oil', '导热油', 'text', null],
  ['utilities', 'condensate', '凝液', 'text', null],
  ['utilities', 'electrical', '电气', 'text', null],
  ['emission_limits', 'gas', '气体', 'text', null],
  ['emission_limits', 'incineration', '焚烧', 'text', null],
  ['emission_limits', 'dust', '粉尘', 'text', null],
  ['emission_limits', 'wastewater', '废水', 'text', null],
  ['emission_limits', 'noise', '噪声', 'number', 'dB'],
  ['emission_limits', 'workplace_air', '工作区空气', 'text', null],
  ['design_criteria', 'design_life', '设计寿命', 'number', 'a'],
  ['design_criteria', 'operation', '操作', 'text', null],
  ['design_criteria', 'transportation', '运输', 'text', null],
  ['design_criteria', 'noise', '噪声', 'number', 'dB'],
  ['safety_fire', 'fire_pump', '消防泵', 'text', null],
  ['safety_fire', 'fire_truck', '消防车', 'text', null],
  ['safety_fire', 'foam', '泡沫', 'text', null],
  ['safety_fire', 'sprinkler', '喷淋', 'text', null],
  ['safety_fire', 'detection', '探测', 'text', null],
  ['safety_fire', 'isolation_valve', '隔离阀', 'text', null],
  ['safety_fire', 'safety_shower', '安全淋浴', 'text', null],
  ['flare', 'back_pressure', '背压', 'number', 'kPa'],
  ['flare', 'radiation', '辐射', 'number', 'kW/m2'],
  ['interface_conditions', 'inlet', '进界区条件表', 'text', null],
  ['interface_conditions', 'outlet', '出界区条件表', 'text', null],
];

/**
 * **US 显示变换**（后端 `app/services/unit_conversion.py::US_DISPLAY` 的镜像）。
 *
 * ⚠️ **为什么 mock 也要抄一份因子** —— 真实通道里因子由**后端下发**
 * ⇒ ⇒ ⇒ mock 通道扮演后端 ⇒ ⇒ ⇒ 就得**扮演到位** ⇒ ⇒ ⇒ 否则 mock 通道
 * **测不出**「换算因子没到前端」这类缺陷。
 *
 * ⚠️ **这 8 个字段** = 后端 `US_DISPLAY` 的 8 个键 ⇒ ⇒ ⇒ 少一个 ⇒ ⇒ ⇒
 * mock 通道与真通道**行为不同** ⇒ ⇒ ⇒ 而漂移守卫（W-10）只比**字段路径
 * 与单位**⇒ ⇒ ⇒ **因子本身**靠这条注释 + 人眼。
 */
const US_DISPLAY: Record<string, { factor: number; offset: number; display_unit: string }> = {
  'meteorology.temperature': { factor: 9 / 5, offset: 32, display_unit: 'degF' },
  'meteorology.pressure': { factor: 1 / 6.894757293168361, offset: 0, display_unit: 'psi' },
  'flare.back_pressure': { factor: 1 / 6.894757293168361, offset: 0, display_unit: 'psi' },
  'meteorology.wind': { factor: 1 / 0.3048, offset: 0, display_unit: 'ft/s' },
  'meteorology.altitude': { factor: 1 / 0.3048, offset: 0, display_unit: 'ft' },
  'meteorology.rainfall': { factor: 1 / 25.4, offset: 0, display_unit: 'in/a' },
  'meteorology.snowfall': { factor: 1 / 25.4, offset: 0, display_unit: 'in/a' },
  'meteorology.evaporation': { factor: 1 / 25.4, offset: 0, display_unit: 'in/a' },
};

/** BEDD 的 uiSchema 响应（契约 `UiSchemaResponse`）。 */
export const seedBeddUiSchema = {
  schema_version: '1.0.0',
  resource: 'bedd',
  fields: BEDD_UI_FIELDS.map(
    ([group, key, label, kind, unit], i): UiSchemaField => ({
      path: `${group}.${key}`,
      label,
      widget: kind === 'number' ? 'NumberInput' : 'Input',
      order: (i % 20) * 10 + 10,
      unit: unit,
      unit_display: US_DISPLAY[`${group}.${key}`] ?? null,
    }),
  ),
};

/**
 * **项目模板**（P10-K · W-3）—— `GET /api/v1/project-templates` 的 mock 数据。
 *
 * ⚠️ **形状照抄契约 `ProjectTemplateSummary`** ⇒ ⇒ ⇒ **不含**
 * `default_config_json`（完整 7 段配置 ⇒ ⇒ ⇒ 那是「应用模板」时才读的）。
 *
 * ⚠️ **两条模板**（对应后端 seed 的两条：签署矩阵型 / 审批深度型）
 * ⇒ ⇒ ⇒ 呼应后端「`record_approval` ↔ `signature_matrix` **互斥**」
 * ⇒ ⇒ ⇒ ⇒ 一条模板**填不满 7 段** ⇒ ⇒ ⇒ ⇒ 集合层面才全覆盖。
 */
export const seedProjectTemplates = [
  {
    template_id: '00000000-0000-0000-0000-00000000c001',
    name: '乙烯项目模板（签署矩阵型）',
    industry: 'CHEMICAL',
    version: '1.0.0',
    status: 'PUBLISHED',
    default_pipe_class_ids: [],
    checklist_item_count: 3,
    // ⚠️ 模板的**默认**单位制（P10-K · TODO-210 · D1）⇒ ⇒ ⇒ 模板 A = SI
    unit_system: 'SI',
  },
  {
    template_id: '00000000-0000-0000-0000-00000000c002',
    name: '通用项目模板（审批深度型）',
    industry: 'CHEMICAL',
    version: '1.0.0',
    status: 'PUBLISHED',
    default_pipe_class_ids: [],
    checklist_item_count: 2,
    // ⚠️ 模板 B = **US**（**故意**）⇒ ⇒ ⇒ 用来验 D1 的两条路径
    //   ⇒ ⇒ ⇒ —— ① 用户没动 ⇒ ⇒ ⇒ 生效（写成 US）
    //   ⇒ ⇒ ⇒ —— ② 用户选过 ⇒ ⇒ ⇒ **不覆盖**（以用户的为准）
    unit_system: 'US',
  },
];
