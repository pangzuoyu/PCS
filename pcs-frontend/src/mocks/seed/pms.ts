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
const BEDD_UI_FIELDS: Array<[string, string, string, 'number' | 'text']> = [
  ['meteorology', 'temperature', '温度 (℃)', 'number'],
  ['meteorology', 'humidity', '湿度 (%)', 'number'],
  ['meteorology', 'pressure', '气压 (kPa)', 'number'],
  ['meteorology', 'wind', '风 (m/s)', 'number'],
  ['meteorology', 'rainfall', '降雨 (mm/a)', 'number'],
  ['meteorology', 'snowfall', '雪 (mm/a)', 'number'],
  ['meteorology', 'evaporation', '蒸发 (mm/a)', 'number'],
  ['meteorology', 'thunderstorm', '雷暴 (d/a)', 'number'],
  ['meteorology', 'fog', '雾 (d/a)', 'number'],
  ['meteorology', 'sunshine', '日照 (h/a)', 'number'],
  ['meteorology', 'solar_radiation', '太阳辐射 (W/m²)', 'number'],
  ['meteorology', 'soil', '土壤', 'text'],
  ['meteorology', 'dust', '粉尘', 'text'],
  ['meteorology', 'altitude', '海拔 (m)', 'number'],
  ['hydrology_geology', 'tidal', '潮汐', 'text'],
  ['hydrology_geology', 'river', '河流', 'text'],
  ['hydrology_geology', 'geology', '地质', 'text'],
  ['seismic', 'intensity', '设防烈度', 'text'],
  ['seismic', 'acceleration', '加速度 (g)', 'number'],
  ['seismic', 'group', '分组', 'text'],
  ['seismic', 'site_category', '场地类别', 'text'],
  ['utilities', 'steam', '蒸汽', 'text'],
  ['utilities', 'water', '水', 'text'],
  ['utilities', 'air', '空气', 'text'],
  ['utilities', 'nitrogen', '氮气', 'text'],
  ['utilities', 'fuel_gas', '燃料气', 'text'],
  ['utilities', 'fuel_oil', '燃料油', 'text'],
  ['utilities', 'hydrogen', '氢气', 'text'],
  ['utilities', 'chemicals', '化学品', 'text'],
  ['utilities', 'heat_transfer_oil', '导热油', 'text'],
  ['utilities', 'condensate', '凝液', 'text'],
  ['utilities', 'electrical', '电气', 'text'],
  ['emission_limits', 'gas', '气体', 'text'],
  ['emission_limits', 'incineration', '焚烧', 'text'],
  ['emission_limits', 'dust', '粉尘', 'text'],
  ['emission_limits', 'wastewater', '废水', 'text'],
  ['emission_limits', 'noise', '噪声 (dB)', 'number'],
  ['emission_limits', 'workplace_air', '工作区空气', 'text'],
  ['design_criteria', 'design_life', '设计寿命 (a)', 'number'],
  ['design_criteria', 'operation', '操作', 'text'],
  ['design_criteria', 'transportation', '运输', 'text'],
  ['design_criteria', 'noise', '噪声 (dB)', 'number'],
  ['safety_fire', 'fire_pump', '消防泵', 'text'],
  ['safety_fire', 'fire_truck', '消防车', 'text'],
  ['safety_fire', 'foam', '泡沫', 'text'],
  ['safety_fire', 'sprinkler', '喷淋', 'text'],
  ['safety_fire', 'detection', '探测', 'text'],
  ['safety_fire', 'isolation_valve', '隔离阀', 'text'],
  ['safety_fire', 'safety_shower', '安全淋浴', 'text'],
  ['flare', 'back_pressure', '背压 (kPa)', 'number'],
  ['flare', 'radiation', '辐射 (kW/m²)', 'number'],
  ['interface_conditions', 'inlet', '进界区条件表', 'text'],
  ['interface_conditions', 'outlet', '出界区条件表', 'text'],
];

/** BEDD 的 uiSchema 响应（契约 `UiSchemaResponse`）。 */
export const seedBeddUiSchema = {
  schema_version: '1.0.0',
  resource: 'bedd',
  fields: BEDD_UI_FIELDS.map(
    ([group, key, label, kind], i): UiSchemaField => ({
      path: `${group}.${key}`,
      label,
      widget: kind === 'number' ? 'NumberInput' : 'Input',
      order: (i % 20) * 10 + 10,
    }),
  ),
};
