/**
 * PsvComputePage — PSV 安全阀计算界面（V1.2 SPEC §7.11.5）。
 *
 * 按 SPEC V1.2 + 后端 OpenAPI（commit 93627a7）：
 * - 多工况泄放：Select mode="multiple" 支持 FIRE / CLOSED_VALVE /
 *   REACTION_RUNAWAY / THERMAL_EXPANSION 同时勾选
 * - 多工况计算：onCalculate 对每个 scenario 并行 POST /psv/calculate
 *   （Promise.all），取 orifice.actual_area_m2 最大者为主导工况（dominant）
 * - 结果区：主导工况详情 + 多工况对比表（每 scenario 一行，max 高亮）
 * - 设计阶段 BASIC ≤25 列 / DETAIL 完整切换
 * - 错误 envelope（403/404/422）按 code 分支提示
 *
 * 复用 api/psv.ts（commit 238f882）+ types/psv.ts（commit 61a3706）。
 *
 * 注：本版本为纯前端多工况聚合，不动后端契约。后端单 scenario API 已被前端
 * 循环调用 + Promise.all 聚合，等价于"前端层多工况 max"。
 */
import { useState } from 'react';
import type { JSX } from 'react';
import {
  Alert,
  Button,
  Card,
  Checkbox,
  Col,
  Collapse,
  Descriptions,
  Empty,
  Form,
  Input,
  InputNumber,
  Radio,
  Row,
  Select,
  Space,
  Statistic,
  Table,
  Tabs,
  Tag,
  Typography,
  message,
} from 'antd';

import { PageHeader } from '../../components/common/PageHeader';
import { psvApi } from '../../api/psv';
import type {
  DesignStage,
  FireScenarioParams,
  ClosedValveScenarioParams,
  ReactionRunawayScenarioParams,
  ThermalExpansionScenarioParams,
  PsvCalculateRequest,
  PsvCalculateResponse,
  PsvStandardProfileCode,
  PsvValveType,
  PsvBodyMaterial,
  PsvBellowsMaterial,
  PsvBackPressureType,
  PsvMedium,
  PsvRuptureDiscPosition,
  PsvFlangeClass,
  OrificeSize,
  ReliefScenario,
  ReliefPhase,
  ScenarioParams,
} from '../../types/psv';

interface StreamLite {
  stream_id: string;
  tag_number: string;
  sign_status: string;
}

interface Props {
  streams: StreamLite[];
  projectStandard?: PsvStandardProfileCode;
}

const SCENARIO_OPTIONS: { value: ReliefScenario; label: string }[] = [
  { value: 'FIRE', label: '火灾工况' },
  { value: 'CLOSED_VALVE', label: '阀门关闭' },
  { value: 'REACTION_RUNAWAY', label: '反应失控' },
  { value: 'THERMAL_EXPANSION', label: '热膨胀' },
];

const SCENARIO_LABELS: Record<ReliefScenario, string> = {
  FIRE: '火灾工况',
  CLOSED_VALVE: '阀门关闭',
  REACTION_RUNAWAY: '反应失控',
  THERMAL_EXPANSION: '热膨胀',
};

const PHASE_OPTIONS: { value: ReliefPhase; label: string }[] = [
  { value: 'GAS', label: '气体' },
  { value: 'LIQUID', label: '液体' },
  { value: 'TWO_PHASE', label: '两相流' },
];

// SUP-P5-PSV-002 V1.14 §5.1 安全阀选型全字段选项
const VALVE_TYPE_OPTIONS: { value: PsvValveType; label: string }[] = [
  { value: 'SPRING_LOADED', label: '弹簧载荷式' },
  { value: 'BALANCED_BELLOWS', label: '平衡波纹管式' },
  { value: 'PILOT_OPERATED', label: '先导式（P5+ 支持）' },
  { value: 'RUPTURE_DISC', label: '爆破膜式（P6+ 支持）' },
];

const BODY_MATERIAL_OPTIONS: { value: PsvBodyMaterial; label: string }[] = [
  { value: 'CARBON_STEEL', label: '碳钢' },
  { value: 'SS304', label: 'SS304' },
  { value: 'SS316', label: 'SS316' },
  { value: 'SS316L', label: 'SS316L' },
  { value: 'ALLOY', label: '合金钢' },
];

// §3.2 V1.14 P2-1：阀体品牌为自由字符串；已知品牌见 _KB_DATA
const VALVE_BRAND_OPTIONS: { value: string; label: string }[] = [
  { value: '', label: '未指定（保守优先）' },
  { value: 'LESER', label: 'LESER' },
  { value: 'Consolidated', label: 'Consolidated' },
  { value: 'Anderson_Greenwood', label: 'Anderson Greenwood' },
  { value: 'Farris', label: 'Farris' },
  { value: 'Crosby', label: 'Crosby' },
  { value: '__other__', label: '其他（自由输入）' },
];

const BELLOWS_MATERIAL_OPTIONS: { value: PsvBellowsMaterial; label: string }[] = [
  { value: 'HASTELLOY_C276', label: 'Hastelloy C276（通用耐蚀）' },
  { value: 'SS316L', label: 'SS316L（经济型，氯环境需评估）' },
  { value: 'INCONEL_625', label: 'Inconel 625（高温高强度）' },
  { value: 'INCONEL_718', label: 'Inconel 718（高温合金）' },
  { value: 'ALLOY_400', label: 'Monel 400（耐海水 / HF，湿 H₂S 敏感）' },
  { value: 'ALLOY_C22', label: 'Alloy C22（耐蚀优于 C276）' },
];

const FLANGE_CLASS_OPTIONS: { value: PsvFlangeClass; label: string }[] = [
  { value: '150#', label: '150#（T 孔口仅 65 psig）' },
  { value: '300#', label: '300#' },
  { value: '600#', label: '600#' },
  { value: '900#', label: '900#' },
  { value: '1500#', label: '1500#' },
  { value: '2500#', label: '2500#' },
];

const MEDIUM_OPTIONS: { value: PsvMedium; label: string }[] = [
  { value: 'GAS', label: '气体' },
  { value: 'VAPOR', label: '蒸汽' },
  { value: 'LIQUID', label: '液体' },
  { value: 'TWO_PHASE', label: '两相流' },
];

const BACK_PRESSURE_TYPE_OPTIONS: { value: PsvBackPressureType; label: string }[] = [
  { value: 'BUILT_UP', label: 'Built-up（泄放时产生）' },
  { value: 'SUPERIMPOSED', label: 'Superimposed（恒定 + CDTP）' },
];

// §5.1 超压百分比固定 3 档
const OVERPRESSURE_OPTIONS: { value: number; label: string }[] = [
  { value: 0.10, label: '10%（API 521 默认）' },
  { value: 0.16, label: '16%（火灾工况）' },
  { value: 0.21, label: '21%（紧急 / 流体扩展）' },
];

const RUPTURE_DISC_POSITION_OPTIONS: { value: PsvRuptureDiscPosition; label: string }[] = [
  { value: 'NONE', label: '无（仅 PSV）' },
  { value: 'UPSTREAM', label: '上游（Kc = 0.90）' },
  { value: 'DOWNSTREAM', label: '下游（Kc = 1.00）' },
];

const SIZE_OPTIONS = ['1 inch', '1.5 inch', '2 inch', '3 inch', '4 inch', '6 inch', '8 inch', '10 inch', '12 inch'];

// API 526 孔口系列（顺序：D→T，面积递增）
const ORIFICE_OPTIONS: { value: OrificeSize; label: string }[] = [
  'D', 'E', 'F', 'G', 'H', 'J', 'K', 'L', 'M', 'N', 'P', 'Q', 'R', 'T',
].map((o) => ({ value: o as OrificeSize, label: `API 526 ${o}` }));

const ORIFICE_ORDER: OrificeSize[] = ['D', 'E', 'F', 'G', 'H', 'J', 'K', 'L', 'M', 'N', 'P', 'Q', 'R', 'T'];

// §3.3 API 526 孔口-法兰映射（前端用：反查候选孔口）
// 与后端 API526_FLANGE_TO_ORIFICES（orifice_flange.py:75-85）完全对齐：
// - 顺序约定：主候选在前（H > G），保留 "size 升序" 阅读
// - 含 ('6 inch','10 inch'): ['R']（前端遗漏，后端完整）
// 注：法兰等级过滤在后端 get_candidate_orifices() 处理（前端选 orifice_size 后透传 flange_class）
const FLANGE_TO_ORIFICES: Record<string, OrificeSize[]> = {
  '1 inch|2 inch': ['D'],
  '1.5 inch|2.5 inch': ['E', 'F'],
  '1.5 inch|3 inch': ['G'],
  '2 inch|3 inch': ['H', 'G'], // H 主 + G 高压档
  '3 inch|4 inch': ['J', 'K'],
  '4 inch|6 inch': ['L', 'M', 'N'],
  '6 inch|8 inch': ['P', 'Q'],
  '6 inch|10 inch': ['R'],
  '8 inch|10 inch': ['Q', 'R', 'T'],
};

// §3.5 吹扫范围按 (阀型, 介质)
const BLOWDOWN_RANGE: Record<string, [number, number]> = {
  'SPRING_LOADED|GAS': [0.05, 0.10],
  'SPRING_LOADED|VAPOR': [0.05, 0.10],
  'SPRING_LOADED|LIQUID': [0.10, 0.20],
  'SPRING_LOADED|TWO_PHASE': [0.10, 0.15],
  'BALANCED_BELLOWS|GAS': [0.05, 0.10],
  'BALANCED_BELLOWS|VAPOR': [0.05, 0.10],
  'BALANCED_BELLOWS|LIQUID': [0.10, 0.20],
  'BALANCED_BELLOWS|TWO_PHASE': [0.10, 0.15],
};

const BLOWDOWN_DEFAULT_BY_MEDIUM: Record<PsvMedium, number> = {
  GAS: 0.05,
  VAPOR: 0.05,
  LIQUID: 0.10,
  TWO_PHASE: 0.10,
};

const BACK_PRESSURE_MAX_BY_TYPE: Record<PsvBackPressureType, number> = {
  BUILT_UP: 10.0,
  SUPERIMPOSED: 50.0,
};

const INLET_SIZE_DEFAULT = '4 inch';
const OUTLET_SIZE_DEFAULT = '6 inch';
const FLANGE_CLASS_DEFAULT: PsvFlangeClass = '300#';
const VALVE_TYPE_DEFAULT: PsvValveType = 'SPRING_LOADED';
const BODY_MATERIAL_DEFAULT: PsvBodyMaterial = 'SS316';
const MEDIUM_DEFAULT: PsvMedium = 'GAS';
const BACK_PRESSURE_TYPE_DEFAULT: PsvBackPressureType = 'BUILT_UP';
const OVERPRESSURE_DEFAULT = 0.10;
const OVERPRESSURE_FIRE = 0.16;

interface PcsErrorEnvelope {
  code?: string;
  message?: string;
  detail?: unknown;
  trace_id?: string;
}

function extractPcsError(err: unknown): PcsErrorEnvelope {
  if (err && typeof err === 'object' && 'response' in err) {
    const data = (err as { response?: { data?: PcsErrorEnvelope } }).response?.data;
    if (data && typeof data === 'object') return data;
  }
  return {};
}

/**从 formValues 提取某 scenario 的字段（去掉 scenario 前缀）。*/
function extractScenarioValues(
  scenario: ReliefScenario,
  formValues: Record<string, number | undefined>,
): Record<string, number> {
  const prefix = `${scenario}_`;
  const out: Record<string, number> = {};
  for (const k in formValues) {
    if (k.startsWith(prefix) && formValues[k] !== undefined) {
      out[k.slice(prefix.length)] = formValues[k] as number;
    }
  }
  return out;
}

export function PsvComputePage({
  streams,
  projectStandard = 'API',
}: Props): JSX.Element {
  const [streamId, setStreamId] = useState<string | undefined>();
  const [scenarios, setScenarios] = useState<ReliefScenario[]>(['FIRE']);
  const [phase, setPhase] = useState<ReliefPhase>('GAS');
  const [designStage, setDesignStage] = useState<DesignStage>('DETAIL');
  // SUP-P5-PSV-002 V1.14 §5.1 安全阀选型全字段 state
  const [valveType, setValveType] = useState<PsvValveType>(VALVE_TYPE_DEFAULT);
  const [bodyMaterial, setBodyMaterial] = useState<PsvBodyMaterial>(BODY_MATERIAL_DEFAULT);
  const [medium, setMedium] = useState<PsvMedium>(MEDIUM_DEFAULT);
  const [bellowsMaterial, setBellowsMaterial] = useState<PsvBellowsMaterial>('HASTELLOY_C276');
  const [valveBrand, setValveBrand] = useState<string>(''); // V1.14 P2-1 自由字符串
  const [valveBrandCustom, setValveBrandCustom] = useState<string>(''); // 其他品牌自由输入
  const [inletSize, setInletSize] = useState<string>(INLET_SIZE_DEFAULT);
  const [outletSize, setOutletSize] = useState<string>(OUTLET_SIZE_DEFAULT);
  const [flangeClass, setFlangeClass] = useState<PsvFlangeClass>(FLANGE_CLASS_DEFAULT);
  const [backPressureType, setBackPressureType] = useState<PsvBackPressureType>(BACK_PRESSURE_TYPE_DEFAULT);
  const [backPressurePct, setBackPressurePct] = useState<number>(0);
  const [overpressurePct, setOverpressurePct] = useState<number>(OVERPRESSURE_DEFAULT);
  const [orificeOverride, setOrificeOverride] = useState<OrificeSize | null>(null);
  const [ruptureDiscPosition, setRuptureDiscPosition] = useState<PsvRuptureDiscPosition>('NONE');
  const [fireProtection, setFireProtection] = useState<boolean>(false);
  const [serviceNote, setServiceNote] = useState<string>('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<PsvCalculateResponse | null>(null);
  const [allResults, setAllResults] = useState<PsvCalculateResponse[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  // SUP-P5-PSV-002 V1.14 §5.2：先导式 / 爆破膜式 → 禁用提交 + 黄色提示
  const isUnsupportedValveType =
    valveType === 'PILOT_OPERATED' || valveType === 'RUPTURE_DISC';
  // §5.2 平衡波纹管式 + 背压 >30% → 黄色提示
  const bellowsConsultWarn =
    valveType === 'BALANCED_BELLOWS' && backPressurePct > 30;
  // §5.2 背压类型 = superimposed → 显示 CDTP
  const cdtpActive = backPressureType === 'SUPERIMPOSED' && backPressurePct > 0;
  // §5.2 FIRE + PILOT_OPERATED → 红色警告
  const firePilotWarn =
    scenarios.includes('FIRE') && valveType === 'PILOT_OPERATED';
  // §5.2 Scenario + 阀型 不推荐组合 → 黄色提示
  const scenarioValveWarn = scenarios.some((s) => {
    if (s === 'FIRE' && valveType === 'PILOT_OPERATED') return true;
    if (s === 'REACTION_RUNAWAY' && valveType === 'PILOT_OPERATED') return true;
    if (s === 'THERMAL_EXPANSION' && valveType === 'PILOT_OPERATED') return true;
    return false;
  });
  // §5.2 阀体品牌：未知品牌 → 黄色提示
  const knownBrands = ['LESER', 'Consolidated', 'Anderson_Greenwood', 'Farris', 'Crosby'];
  const effectiveBrand = valveBrand === '__other__' ? valveBrandCustom : valveBrand;
  const brandUnknown =
    effectiveBrand.length > 0 && !knownBrands.includes(effectiveBrand);
  // §5.2 介质切换 → blowdown 范围动态
  const blowdownRange = BLOWDOWN_RANGE[`${valveType}|${medium}`] ?? [0.05, 0.10];
  // §5.2 入/出口尺寸 → 候选孔口（API 526 反查）
  const candidateOrifices = FLANGE_TO_ORIFICES[`${inletSize}|${outletSize}`] ?? [];
  const orificeMismatch = Boolean(inletSize) && Boolean(outletSize) && candidateOrifices.length === 0;
  // §5.1 T 孔口在 150# 下 65 psig 警告
  const tOrificeLowClassWarn =
    flangeClass === '150#' && orificeOverride === 'T';

  const checkedStreams = streams.filter((s) => s.sign_status === 'CHECKED');

  const onCalculate = async (formValues: Record<string, number | undefined>) => {
    if (!streamId) {
      message.error('请先选择 CHECKED 物流');
      return;
    }
    if (scenarios.length === 0) {
      message.error('请选择至少一个泄放工况');
      return;
    }
    // V1.14 §5.2 前端拦截：先导式 / 爆破膜式禁用提交
    if (isUnsupportedValveType) {
      message.error(
        `${VALVE_TYPE_OPTIONS.find((o) => o.value === valveType)?.label ?? valveType}：当前 P5 阶段不支持，请选择其他阀体型式`,
      );
      return;
    }
    // V1.14 §5.2 FIRE + PILOT_OPERATED → 红色警告拦截
    if (firePilotWarn) {
      message.error('FIRE + PILOT_OPERATED 需 API 521 专项评估（OPEN-19），当前不支持');
      return;
    }
    // V1.14 §5.2：blowdown_fraction 超出 (阀型, 介质) 范围 → 前端阻止
    const blowdown = formValues.blowdown_fraction as number | undefined;
    if (
      blowdown !== undefined &&
      (blowdown < blowdownRange[0] || blowdown > blowdownRange[1])
    ) {
      message.error(
        `${valveType}/${medium} blowdown 需在 ${blowdownRange[0] * 100}% ~ ${blowdownRange[1] * 100}% 之间`,
      );
      return;
    }
    // V1.14 §5.2：平衡波纹管式未选波纹管材料 → 前端阻止
    if (valveType === 'BALANCED_BELLOWS' && !bellowsMaterial) {
      message.error('平衡波纹管式必须选择波纹管材料（§3.5 必填）');
      return;
    }
    // V1.14 §5.2：入/出口尺寸无候选孔口 → 阻止
    if (orificeMismatch) {
      message.error(`入/出口尺寸 ${inletSize} × ${outletSize} 与 API 526 孔口表无匹配`);
      return;
    }
    // V1.14 §5.2：手动 override 不在候选孔口 → 阻止
    if (orificeOverride && candidateOrifices.length > 0 && !candidateOrifices.includes(orificeOverride)) {
      message.error(
        `手动孔口 ${orificeOverride} 不在候选列表（${candidateOrifices.join('/')}），请选择候选内或修改尺寸`,
      );
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const baseSizing = {
        phase,
        P_back_pa: formValues.P_back_pa as number,
        P_set_pa: formValues.P_set_pa as number,
        T_k: formValues.T_k as number,
        M_kg_per_mol: formValues.M_kg_per_mol as number,
        Z: formValues.Z as number,
        k_cp_ratio: formValues.k_cp_ratio as number,
        rho_L_kg_m3: formValues.rho_L_kg_m3 as number,
        relief_mass_flow_kgs: formValues.relief_mass_flow_kgs as number,
      };
      // FIRE 工况自动 16%（V1.14 §3.5）
      const effectiveOverpressure =
        scenarios.includes('FIRE') && overpressurePct === OVERPRESSURE_DEFAULT
          ? OVERPRESSURE_FIRE
          : overpressurePct;
      const responses = await Promise.all(
        scenarios.map((s) => {
          const values = extractScenarioValues(s, formValues);
          const req: PsvCalculateRequest = {
            source_stream_id: streamId,
            relief_scenario: s,
            scenario_params: buildScenarioParams(s, values),
            sizing_params: baseSizing,
            design_stage: designStage,
            blowdown_fraction: blowdown ?? BLOWDOWN_DEFAULT_BY_MEDIUM[medium],
            // V1.14 §5.1 全字段（后端 extra='ignore' 静默兼容）
            inlet_size: inletSize,
            outlet_size: outletSize,
            valve_type: valveType,
            body_material: bodyMaterial,
            bellows_material: valveType === 'BALANCED_BELLOWS' ? bellowsMaterial : null,
            medium,
            flange_class: flangeClass,
            back_pressure_pct: backPressurePct,
            back_pressure_type: backPressureType,
            overpressure_pct: effectiveOverpressure,
            orifice_override: orificeOverride,
            valve_brand: effectiveBrand || null,
            rupture_disc_position: ruptureDiscPosition,
            fire_protection: fireProtection,
            service_note: serviceNote || null,
          };
          return psvApi.calculate(req);
        }),
      );
      // 取 orifice.actual_area_m2 最大者为主导工况
      const dominant = responses.reduce((max, r) =>
        r.result.orifice.actual_area_m2 > max.result.orifice.actual_area_m2 ? r : max,
      );
      // V1.14 §5.2：孔口手动 override 面积校验（前端阻止）
      if (orificeOverride) {
        const overrideIdx = ORIFICE_ORDER.indexOf(orificeOverride);
        const computedIdx = ORIFICE_ORDER.indexOf(dominant.result.orifice.selected_size);
        if (overrideIdx < computedIdx) {
          message.error(
            `手动孔口 ${orificeOverride}（小于计算孔口 ${dominant.result.orifice.selected_size}），请清除 override 或选择更大孔口`,
          );
          setAllResults(responses);
          setResult(dominant);
          setLoading(false);
          return;
        }
      }
      setAllResults(responses);
      setResult(dominant);
      message.success(
        `PSV 多工况计算完成：主导工况=${SCENARIO_LABELS[dominant.result.aggregate.dominant_scenario]}（${dominant.result.orifice.selected_size}）`,
      );
    } catch (err: unknown) {
      const env = extractPcsError(err);
      const code = env.code ?? '';
      const msg = env.message ?? 'PSV 计算失败';
      // SUP-P5-PSV-002 V1.14 §6 错误码 G7-G25 全部分支
      if (code === 'STREAM_NOT_CHECKED') {
        message.error('源流未签收，请先在物流一览完成 CHECKED 流程');
      } else if (code === 'SIM_STREAM_NOT_FOUND') {
        message.error('源流不存在，请重新选择');
      } else if (code === 'PSV_INPUT_ERROR') {
        message.error(`输入参数不合法：${msg}`);
      } else if (code === 'PSV_PILOT_OPERATED_NOT_SUPPORTED') {
        // G7
        message.error('先导式阀计算 P5+ 实施，请联系标准负责人评估升级路径');
      } else if (code === 'PSV_RUPTURE_DISC_NOT_SUPPORTED') {
        // G8
        message.error('爆破膜式 P6+ 实施');
      } else if (code === 'PSV_ORIFICE_OVERRIDE_TOO_SMALL') {
        // G9
        message.error(`手动孔口面积小于计算面积：${msg}`);
      } else if (code === 'PSV_BACK_PRESSURE_EXCEEDED') {
        // G10
        message.error(`背压超阀型范围（${valveType}：${BACK_PRESSURE_MAX_BY_TYPE[backPressureType]}%）：${msg}`);
      } else if (code === 'PSV_BLOWDOWN_OUT_OF_RANGE') {
        // G11
        message.error(`blowdown 超 (${valveType}, ${medium}) 范围 ${blowdownRange[0] * 100}%~${blowdownRange[1] * 100}%：${msg}`);
      } else if (code === 'PSV_INLET_OUTLET_MISMATCH') {
        // G12
        message.error(`入/出口尺寸与 API 526 不匹配：${msg}`);
      } else if (code === 'PSV_MATERIAL_INCOMPATIBLE') {
        // G13
        message.error(`阀体/波纹管材料与介质不兼容：${msg}`);
      } else if (code === 'PSV_INLET_TOO_SMALL') {
        // G14
        message.error(`入口尺寸 < 1"：${msg}`);
      } else if (code === 'PSV_ORIFICE_TEMPERATURE_LIMIT') {
        // G15 Q/R/T 孔口 T>177°C 且 MW<10 须业主工程师批准
        message.error(`Q/R/T 孔口高温-低分子量限制：${msg}`);
      } else if (code === 'PSV_BELLOWS_MATERIAL_REQUIRED') {
        // G17
        message.error('平衡波纹管式必须指定波纹管材料');
      } else if (code === 'PSV_BELLOWS_INCOMPATIBLE') {
        // G21
        message.error(`波纹管材料-介质禁忌：${msg}`);
      } else if (code === 'PSV_FLANGE_CLASS_ORIFICE_MISMATCH') {
        // G20
        message.error(`法兰等级-孔口不匹配（${flangeClass}）：${msg}`);
      } else {
        message.error(msg);
      }
      setError(msg);
      setResult(null);
      setAllResults(null);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div data-testid="psv-compute-page">
      <PageHeader
        title="PSV 安全阀计算"
        module="PSV"
        actions={
          <Space>
            <Tag color="blue" data-testid="psv-standard-tag">
              项目标准：{projectStandard}
            </Tag>
            <Radio.Group
              value={designStage}
              onChange={(e) => setDesignStage(e.target.value as DesignStage)}
              data-testid="psv-design-stage"
            >
              <Radio.Button value="BASIC">BASIC（≤25 列）</Radio.Button>
              <Radio.Button value="DETAIL">DETAIL（完整）</Radio.Button>
            </Radio.Group>
          </Space>
        }
      />

      <Tabs
        defaultActiveKey="input"
        data-testid="psv-tabs"
        items={[
          {
            key: 'input',
            label: '输入与计算',
            children: (
              <InputPanel
                streamId={streamId}
                setStreamId={setStreamId}
                scenarios={scenarios}
                setScenarios={setScenarios}
                phase={phase}
                setPhase={setPhase}
                checkedStreams={checkedStreams}
                loading={loading}
                onCalculate={onCalculate}
                error={error}
                valveType={valveType}
                setValveType={setValveType}
                bodyMaterial={bodyMaterial}
                setBodyMaterial={setBodyMaterial}
                medium={medium}
                setMedium={setMedium}
                bellowsMaterial={bellowsMaterial}
                setBellowsMaterial={setBellowsMaterial}
                valveBrand={valveBrand}
                setValveBrand={setValveBrand}
                valveBrandCustom={valveBrandCustom}
                setValveBrandCustom={setValveBrandCustom}
                inletSize={inletSize}
                setInletSize={setInletSize}
                outletSize={outletSize}
                setOutletSize={setOutletSize}
                flangeClass={flangeClass}
                setFlangeClass={setFlangeClass}
                backPressureType={backPressureType}
                setBackPressureType={setBackPressureType}
                backPressurePct={backPressurePct}
                setBackPressurePct={setBackPressurePct}
                overpressurePct={overpressurePct}
                setOverpressurePct={setOverpressurePct}
                orificeOverride={orificeOverride}
                setOrificeOverride={setOrificeOverride}
                ruptureDiscPosition={ruptureDiscPosition}
                setRuptureDiscPosition={setRuptureDiscPosition}
                fireProtection={fireProtection}
                setFireProtection={setFireProtection}
                serviceNote={serviceNote}
                setServiceNote={setServiceNote}
                isUnsupportedValveType={isUnsupportedValveType}
                bellowsConsultWarn={bellowsConsultWarn}
                cdtpActive={cdtpActive}
                firePilotWarn={firePilotWarn}
                scenarioValveWarn={scenarioValveWarn}
                brandUnknown={brandUnknown}
                blowdownRange={blowdownRange}
                candidateOrifices={candidateOrifices}
                orificeMismatch={orificeMismatch}
                tOrificeLowClassWarn={tOrificeLowClassWarn}
              />
            ),
          },
          {
            key: 'result',
            label: '结果',
            children: (
              <ResultPanel
                result={result}
                allResults={allResults}
                designStage={designStage}
                error={error}
              />
            ),
          },
        ]}
      />
    </div>
  );
}

// ---------------------------------------------------------------------------
// 输入面板
// ---------------------------------------------------------------------------

interface InputPanelProps {
  streamId: string | undefined;
  setStreamId: (v: string | undefined) => void;
  scenarios: ReliefScenario[];
  setScenarios: (v: ReliefScenario[]) => void;
  phase: ReliefPhase;
  setPhase: (v: ReliefPhase) => void;
  checkedStreams: StreamLite[];
  loading: boolean;
  onCalculate: (values: Record<string, number | undefined>) => Promise<void>;
  error: string | null;
  // SUP-P5-PSV-002 V1.14 §5.1 安全阀选型全字段
  valveType: PsvValveType;
  setValveType: (v: PsvValveType) => void;
  bodyMaterial: PsvBodyMaterial;
  setBodyMaterial: (v: PsvBodyMaterial) => void;
  medium: PsvMedium;
  setMedium: (v: PsvMedium) => void;
  bellowsMaterial: PsvBellowsMaterial;
  setBellowsMaterial: (v: PsvBellowsMaterial) => void;
  valveBrand: string;
  setValveBrand: (v: string) => void;
  valveBrandCustom: string;
  setValveBrandCustom: (v: string) => void;
  inletSize: string;
  setInletSize: (v: string) => void;
  outletSize: string;
  setOutletSize: (v: string) => void;
  flangeClass: PsvFlangeClass;
  setFlangeClass: (v: PsvFlangeClass) => void;
  backPressureType: PsvBackPressureType;
  setBackPressureType: (v: PsvBackPressureType) => void;
  backPressurePct: number;
  setBackPressurePct: (v: number) => void;
  overpressurePct: number;
  setOverpressurePct: (v: number) => void;
  orificeOverride: OrificeSize | null;
  setOrificeOverride: (v: OrificeSize | null) => void;
  ruptureDiscPosition: PsvRuptureDiscPosition;
  setRuptureDiscPosition: (v: PsvRuptureDiscPosition) => void;
  fireProtection: boolean;
  setFireProtection: (v: boolean) => void;
  serviceNote: string;
  setServiceNote: (v: string) => void;
  // §5.2 联动派生
  isUnsupportedValveType: boolean;
  bellowsConsultWarn: boolean;
  cdtpActive: boolean;
  firePilotWarn: boolean;
  scenarioValveWarn: boolean;
  brandUnknown: boolean;
  blowdownRange: [number, number];
  candidateOrifices: OrificeSize[];
  orificeMismatch: boolean;
  tOrificeLowClassWarn: boolean;
}

function InputPanel({
  streamId,
  setStreamId,
  scenarios,
  setScenarios,
  phase,
  setPhase,
  checkedStreams,
  loading,
  onCalculate,
  error,
  valveType,
  setValveType,
  bodyMaterial,
  setBodyMaterial,
  medium,
  setMedium,
  bellowsMaterial,
  setBellowsMaterial,
  valveBrand,
  setValveBrand,
  valveBrandCustom,
  setValveBrandCustom,
  inletSize,
  setInletSize,
  outletSize,
  setOutletSize,
  flangeClass,
  setFlangeClass,
  backPressureType,
  setBackPressureType,
  backPressurePct,
  setBackPressurePct,
  overpressurePct,
  setOverpressurePct,
  orificeOverride,
  setOrificeOverride,
  ruptureDiscPosition,
  setRuptureDiscPosition,
  fireProtection,
  setFireProtection,
  serviceNote,
  setServiceNote,
  isUnsupportedValveType,
  bellowsConsultWarn,
  cdtpActive,
  firePilotWarn,
  scenarioValveWarn,
  brandUnknown,
  blowdownRange,
  candidateOrifices,
  orificeMismatch,
  tOrificeLowClassWarn,
}: InputPanelProps): JSX.Element {
  const [form] = Form.useForm();
  // §5.2：阀体品牌（其他 → 自由输入）
  const effectiveBrand = valveBrand === '__other__' ? valveBrandCustom : valveBrand;

  const handleSubmit = async () => {
    const values = await form.validateFields();
    await onCalculate(values as Record<string, number | undefined>);
  };

  return (
    <Row gutter={16}>
      <Col span={10}>
        <Card title="输入条件" size="small">
          {error && (
            <Alert
              type="error"
              message={error}
              data-testid="psv-error"
              style={{ marginBottom: 12 }}
            />
          )}
          <Form form={form} layout="vertical" data-testid="psv-form">
            <Form.Item label="物流" required>
              <Select
                data-testid="psv-stream-select"
                placeholder="选择 CHECKED 物流"
                value={streamId}
                onChange={setStreamId}
                options={checkedStreams.map((s) => ({
                  value: s.stream_id,
                  label: s.tag_number,
                }))}
              />
            </Form.Item>
            <Form.Item label="泄放工况（多选）" required>
              <Select
                data-testid="psv-scenario-select"
                mode="multiple"
                maxTagCount="responsive"
                value={scenarios}
                onChange={(v) => setScenarios(v as ReliefScenario[])}
                options={SCENARIO_OPTIONS}
                placeholder="选择至少一个泄放工况"
              />
            </Form.Item>
            <Form.Item label="相态">
              <Select
                data-testid="psv-phase-select"
                value={phase}
                onChange={setPhase}
                options={PHASE_OPTIONS}
              />
            </Form.Item>

            {/* SUP-P5-PSV-002 V1.14 §5.1 安全阀选型 Collapse（16 字段 + 联动） */}
            <Collapse
              data-testid="psv-selection-collapse"
              defaultActiveKey={['selection']}
              items={[
                {
                  key: 'selection',
                  label: <Tag color="cyan">安全阀选型（SUP-P5-PSV-002 V1.14）</Tag>,
                  children: (
                    <>
                      {/* §5.2：先导式 / 爆破膜式 → 黄色提示 */}
                      {isUnsupportedValveType && (
                        <Alert
                          type="warning"
                          showIcon
                          data-testid="psv-unsupported-valve-type-alert"
                          message={`${
                            VALVE_TYPE_OPTIONS.find((o) => o.value === valveType)?.label ?? valveType
                          }：当前 P5 阶段不支持，请选择弹簧载荷式或平衡波纹管式`}
                          style={{ marginBottom: 12 }}
                        />
                      )}
                      {/* §5.2：FIRE + PILOT_OPERATED → 红色警告 */}
                      {firePilotWarn && (
                        <Alert
                          type="error"
                          showIcon
                          data-testid="psv-fire-pilot-alert"
                          message="FIRE + PILOT_OPERATED：需 API 521 专项评估（OPEN-19），当前 P5 不支持"
                          style={{ marginBottom: 12 }}
                        />
                      )}
                      {/* §5.2：Scenario + 阀型 不推荐组合 → 黄色提示 */}
                      {scenarioValveWarn && !firePilotWarn && (
                        <Alert
                          type="warning"
                          showIcon
                          data-testid="psv-scenario-valve-warn-alert"
                          message="当前 Scenario + 阀型组合为不推荐（§3.7 矩阵）：先导式在反应失控 / 小流量下响应特性可能不足"
                          style={{ marginBottom: 12 }}
                        />
                      )}
                      {/* §5.2：平衡波纹管 + 背压 >30% → 黄色提示 */}
                      {bellowsConsultWarn && (
                        <Alert
                          type="warning"
                          showIcon
                          data-testid="psv-bellows-consult-alert"
                          message={`平衡波纹管式背压 ${backPressurePct}% > 30%，须咨询厂商确认 Kb 数据`}
                          style={{ marginBottom: 12 }}
                        />
                      )}
                      {/* §5.2：未知品牌 → 黄色提示 */}
                      {brandUnknown && (
                        <Alert
                          type="warning"
                          showIcon
                          data-testid="psv-brand-unknown-alert"
                          message={`阀体品牌 '${effectiveBrand}' 无 Kb 数据，将使用保守优先策略`}
                          style={{ marginBottom: 12 }}
                        />
                      )}
                      {/* §5.2：T 孔口 + 150# → 黄色提示 */}
                      {tOrificeLowClassWarn && (
                        <Alert
                          type="warning"
                          showIcon
                          data-testid="psv-t-low-class-alert"
                          message="T 孔口在 150# 法兰下最大压力仅 65 psig（API 526 Table 15 / 碳钢 -20~100°F）"
                          style={{ marginBottom: 12 }}
                        />
                      )}
                      {/* §5.2：CDTP 修正提示 */}
                      {cdtpActive && (
                        <Alert
                          type="info"
                          showIcon
                          data-testid="psv-cdtp-alert"
                          message={`CDTP 修正生效：设定压力 = P_set − ${backPressurePct}% 恒定背压`}
                          style={{ marginBottom: 12 }}
                        />
                      )}

                      <Form.Item label="阀体型式" required>
                        <Radio.Group
                          data-testid="psv-valve-type-radio"
                          value={valveType}
                          onChange={(e) => setValveType(e.target.value as PsvValveType)}
                          options={VALVE_TYPE_OPTIONS}
                          optionType="button"
                        />
                      </Form.Item>

                      <Row gutter={16}>
                        <Col span={12}>
                          <Form.Item label="阀体材料">
                            <Select
                              data-testid="psv-body-material-select"
                              value={bodyMaterial}
                              onChange={setBodyMaterial}
                              options={BODY_MATERIAL_OPTIONS}
                            />
                          </Form.Item>
                        </Col>
                        <Col span={12}>
                          <Form.Item label="介质" required>
                            <Select
                              data-testid="psv-medium-select"
                              value={medium}
                              onChange={setMedium}
                              options={MEDIUM_OPTIONS}
                            />
                          </Form.Item>
                        </Col>
                      </Row>

                      {/* §5.1 平衡波纹管式 → 波纹管材料必填 */}
                      {valveType === 'BALANCED_BELLOWS' && (
                        <Form.Item label="波纹管材料" required>
                          <Select
                            data-testid="psv-bellows-material-select"
                            value={bellowsMaterial}
                            onChange={setBellowsMaterial}
                            options={BELLOWS_MATERIAL_OPTIONS}
                          />
                        </Form.Item>
                      )}

                      {/* §5.1 V1.14 P2-4：阀体品牌联动 */}
                      {valveType === 'BALANCED_BELLOWS' && (
                        <Form.Item
                          label="阀体品牌"
                          extra="已选品牌 → Kb 按品牌优先；未指定 → 保守优先；未知品牌 → 警告 + 保守优先"
                        >
                          <Row gutter={8}>
                            <Col span={12}>
                              <Select
                                data-testid="psv-valve-brand-select"
                                value={valveBrand}
                                onChange={setValveBrand}
                                options={VALVE_BRAND_OPTIONS}
                                placeholder="选择品牌"
                              />
                            </Col>
                            {valveBrand === '__other__' && (
                              <Col span={12}>
                                <Input
                                  data-testid="psv-valve-brand-custom"
                                  value={valveBrandCustom}
                                  onChange={(e) => setValveBrandCustom(e.target.value)}
                                  placeholder="自由输入品牌名"
                                />
                              </Col>
                            )}
                          </Row>
                        </Form.Item>
                      )}

                      <Row gutter={16}>
                        <Col span={8}>
                          <Form.Item label="入口尺寸" required>
                            <Select
                              data-testid="psv-inlet-size-select"
                              value={inletSize}
                              onChange={setInletSize}
                              options={SIZE_OPTIONS.map((s) => ({ value: s, label: s }))}
                            />
                          </Form.Item>
                        </Col>
                        <Col span={8}>
                          <Form.Item label="出口尺寸" required>
                            <Select
                              data-testid="psv-outlet-size-select"
                              value={outletSize}
                              onChange={setOutletSize}
                              options={SIZE_OPTIONS.map((s) => ({ value: s, label: s }))}
                            />
                          </Form.Item>
                        </Col>
                        <Col span={8}>
                          <Form.Item label="法兰等级" required>
                            <Select
                              data-testid="psv-flange-class-select"
                              value={flangeClass}
                              onChange={setFlangeClass}
                              options={FLANGE_CLASS_OPTIONS}
                            />
                          </Form.Item>
                        </Col>
                      </Row>

                      {/* §5.2 候选孔口提示（API 526 反查） */}
                      {candidateOrifices.length > 0 ? (
                        <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                          候选孔口（{candidateOrifices.join(' / ')}）
                        </Typography.Text>
                      ) : orificeMismatch ? (
                        <Typography.Text type="danger" style={{ fontSize: 12 }}>
                          警告：{inletSize} × {outletSize} 与 API 526 孔口表无匹配（§5.2）
                        </Typography.Text>
                      ) : null}

                      <Row gutter={16}>
                        <Col span={12}>
                          <Form.Item label="背压类型">
                            <Radio.Group
                              data-testid="psv-bp-type-radio"
                              value={backPressureType}
                              onChange={(e) => setBackPressureType(e.target.value as PsvBackPressureType)}
                              options={BACK_PRESSURE_TYPE_OPTIONS}
                              optionType="button"
                            />
                          </Form.Item>
                        </Col>
                        <Col span={12}>
                          <Form.Item
                            label="背压百分比"
                            extra={`${valveType}：built-up ≤10% / superimposed ≤50%`}
                          >
                            <Space.Compact style={{ width: '100%' }}>
                              <InputNumber
                                data-testid="psv-bp-pct-input"
                                min={0}
                                max={BACK_PRESSURE_MAX_BY_TYPE[backPressureType]}
                                step={0.5}
                                value={backPressurePct}
                                onChange={(v) => setBackPressurePct((v as number) ?? 0)}
                                style={{ width: '100%' }}
                              />
                              <Input
                                value="%"
                                disabled
                                style={{ width: 40, textAlign: 'center' }}
                              />
                            </Space.Compact>
                          </Form.Item>
                        </Col>
                      </Row>

                      <Row gutter={16}>
                        <Col span={12}>
                          <Form.Item
                            label="blowdown 百分比"
                            name="blowdown_fraction"
                            initialValue={BLOWDOWN_DEFAULT_BY_MEDIUM[medium]}
                            extra={`${valveType}/${medium} 范围 ${blowdownRange[0] * 100}% ~ ${blowdownRange[1] * 100}%`}
                            rules={[
                              {
                                validator: (_, v: number | undefined) =>
                                  v === undefined ||
                                  (v >= blowdownRange[0] && v <= blowdownRange[1])
                                    ? Promise.resolve()
                                    : Promise.reject(
                                        new Error(
                                          `${valveType}/${medium} 范围 ${blowdownRange[0] * 100}% ~ ${blowdownRange[1] * 100}%`,
                                        ),
                                      ),
                              },
                            ]}
                          >
                            <InputNumber
                              data-testid="psv-blowdown-input"
                              min={blowdownRange[0]}
                              max={blowdownRange[1]}
                              step={0.01}
                              style={{ width: '100%' }}
                            />
                          </Form.Item>
                        </Col>
                        <Col span={12}>
                          <Form.Item label="超压百分比" required>
                            <Select
                              data-testid="psv-overpressure-select"
                              value={overpressurePct}
                              onChange={(v) => setOverpressurePct(v as number)}
                              options={OVERPRESSURE_OPTIONS}
                            />
                          </Form.Item>
                        </Col>
                      </Row>

                      {/* §5.1 Kb 显示：弹簧式 1.0 / 平衡波纹管式 查表值 / 先导式 不适用 */}
                      <Form.Item label="Kb 修正系数（预估）">
                        <Tag color="cyan" data-testid="psv-kb-display">
                          {valveType === 'SPRING_LOADED' && '(1.0, none)'}
                          {valveType === 'BALANCED_BELLOWS' &&
                            backPressurePct > 0 &&
                            (valveBrand ? `(查表, manufacturer:${effectiveBrand})` : '(查表, 保守优先)')}
                          {valveType === 'BALANCED_BELLOWS' && backPressurePct === 0 && '(1.0, none)'}
                          {valveType === 'PILOT_OPERATED' && '不适用'}
                          {valveType === 'RUPTURE_DISC' && '不适用'}
                        </Tag>
                      </Form.Item>

                      <Form.Item
                        label="孔口手动 override"
                        extra={
                          orificeOverride
                            ? `将跳过自动圆整，使用 ${orificeOverride}（提交后会与计算孔口对比）`
                            : '默认自动选型（API 526 圆整向上）'
                        }
                      >
                        <Select
                          data-testid="psv-orifice-override-select"
                          value={orificeOverride ?? undefined}
                          onChange={(v) => setOrificeOverride((v ?? null) as OrificeSize | null)}
                          allowClear
                          options={ORIFICE_OPTIONS}
                          placeholder="自动（推荐）"
                        />
                      </Form.Item>

                      <Row gutter={16}>
                        <Col span={12}>
                          <Form.Item label="爆破膜位置">
                            <Select
                              data-testid="psv-rupture-disc-select"
                              value={ruptureDiscPosition}
                              onChange={setRuptureDiscPosition}
                              options={RUPTURE_DISC_POSITION_OPTIONS}
                            />
                          </Form.Item>
                        </Col>
                        <Col span={12}>
                          <Form.Item label="防火保护">
                            <Checkbox
                              data-testid="psv-fire-protection-check"
                              checked={fireProtection}
                              onChange={(e) => setFireProtection(e.target.checked)}
                            >
                              已配置防火保护（FIRE 工况建议勾选）
                            </Checkbox>
                          </Form.Item>
                        </Col>
                      </Row>

                      <Form.Item
                        label="服务备注"
                        extra="介质特殊条件（如氯化物 / 湿 H₂S / HF 等）→ 后端 §3.8 波纹管兼容性校验"
                      >
                        <Input.TextArea
                          data-testid="psv-service-note"
                          rows={2}
                          value={serviceNote}
                          onChange={(e) => setServiceNote(e.target.value)}
                          placeholder="例如：500 ppm 氯离子、含水 H₂S、热浓硝酸…"
                        />
                      </Form.Item>
                    </>
                  ),
                },
              ]}
            />

            <ScenarioParamsForms scenarios={scenarios} />
            <SizingParamsForm phase={phase} />

            <Form.Item>
              <Button
                type="primary"
                data-testid="psv-calculate"
                loading={loading}
                disabled={isUnsupportedValveType}
                onClick={handleSubmit}
              >
                计算
              </Button>
            </Form.Item>
          </Form>
        </Card>
      </Col>

      <Col span={14}>
        <Card title="当前选择" size="small">
          <Descriptions size="small" column={1}>
            <Descriptions.Item label="物流">
              {streamId ? (
                <code>{streamId}</code>
              ) : (
                <Typography.Text type="secondary">未选择</Typography.Text>
              )}
            </Descriptions.Item>
            <Descriptions.Item label="工况（多选）">
              {scenarios.length === 0 ? (
                <Typography.Text type="secondary">未选择</Typography.Text>
              ) : (
                <Space wrap>
                  {scenarios.map((s) => (
                    <Tag key={s} color="purple">{SCENARIO_LABELS[s]}</Tag>
                  ))}
                </Space>
              )}
            </Descriptions.Item>
            <Descriptions.Item label="相态">{phase}</Descriptions.Item>
            <Descriptions.Item label="阀体选型（SUP-P5-PSV-002 V1.14）">
              <Space wrap size={4}>
                <Tag color="cyan">
                  {VALVE_TYPE_OPTIONS.find((o) => o.value === valveType)?.label ?? valveType}
                </Tag>
                <Tag color="blue">{medium}</Tag>
                {valveType === 'BALANCED_BELLOWS' && (
                  <Tag color="geekblue">{bellowsMaterial}</Tag>
                )}
                {valveType === 'BALANCED_BELLOWS' && effectiveBrand && (
                  <Tag color="purple">品牌={effectiveBrand}</Tag>
                )}
                <Tag color="blue">{flangeClass}</Tag>
                <Tag>{inletSize} / {outletSize}</Tag>
                <Tag color="orange">
                  背压 {backPressurePct}% ({backPressureType})
                </Tag>
                <Tag color="orange">超压 {overpressurePct * 100}%</Tag>
                {orificeOverride && <Tag color="orange">孔口 override={orificeOverride}</Tag>}
                {fireProtection && <Tag color="red">防火保护</Tag>}
              </Space>
            </Descriptions.Item>
          </Descriptions>
          <Typography.Paragraph type="secondary" style={{ marginTop: 12 }}>
            多工况 → 提交时对每个勾选工况并行 POST /api/v1/psv/calculate →
            取 orifice.actual_area_m2 最大者为主导工况。结果区展示主导详情 + 多工况对比表。
          </Typography.Paragraph>
        </Card>
      </Col>
    </Row>
  );
}

// ---------------------------------------------------------------------------
// 多工况 scenario_params 动态表单（按 selected scenarios 折叠分组）
// ---------------------------------------------------------------------------

interface ScenarioFormsProps {
  scenarios: ReliefScenario[];
}

function ScenarioParamsForms({ scenarios }: ScenarioFormsProps): JSX.Element {
  if (scenarios.length === 0) {
    return (
      <Alert
        type="warning"
        showIcon
        message="请先在上方勾选至少一个泄放工况"
        data-testid="psv-scenario-warning"
        style={{ marginBottom: 12 }}
      />
    );
  }
  return (
    <Collapse
      data-testid="psv-scenario-collapse"
      defaultActiveKey={scenarios}
      items={scenarios.map((s) => ({
        key: s,
        label: <Tag color="purple">{SCENARIO_LABELS[s]}</Tag>,
        children: <ScenarioParamsForm scenario={s} />,
      }))}
    />
  );
}

interface ScenarioFormProps {
  scenario: ReliefScenario;
}

function ScenarioParamsForm({ scenario }: ScenarioFormProps): JSX.Element {
  const prefix = `${scenario}_`;
  if (scenario === 'FIRE') {
    return (
      <>
        <Form.Item label="容器直径 D_m" name={`${prefix}D_m`} initialValue={1.0} rules={[{ required: true }]}>
          <InputNumber min={0.1} step={0.1} style={{ width: '100%' }} />
        </Form.Item>
        <Form.Item label="容器高度 H_m" name={`${prefix}H_m`} initialValue={5.0} rules={[{ required: true }]}>
          <InputNumber min={0.1} step={0.1} style={{ width: '100%' }} />
        </Form.Item>
        <Form.Item label="充液分率" name={`${prefix}liquid_level_fraction`} initialValue={0.5}>
          <InputNumber min={0} max={1} step={0.05} style={{ width: '100%' }} />
        </Form.Item>
        <Form.Item label="环境因子 F" name={`${prefix}environment_factor_F`} initialValue={1.0}>
          <InputNumber min={0} max={2} step={0.1} style={{ width: '100%' }} />
        </Form.Item>
        <Form.Item label="汽化潜热 h_fg (J/kg)" name={`${prefix}h_fg_j_per_kg`} initialValue={350000}>
          <InputNumber min={1} step={1000} style={{ width: '100%' }} />
        </Form.Item>
      </>
    );
  }
  if (scenario === 'CLOSED_VALVE') {
    return (
      <>
        <Form.Item label="管段容积 V_pipe (m³)" name={`${prefix}V_pipe_m3`} initialValue={0.1}>
          <InputNumber min={0.0001} step={0.01} style={{ width: '100%' }} />
        </Form.Item>
        <Form.Item label="液体密度 ρ_L (kg/m³)" name={`${prefix}rho_L_kg_m3`} initialValue={850}>
          <InputNumber min={1} step={10} style={{ width: '100%' }} />
        </Form.Item>
        <Form.Item label="隔离时间 t_isolation (s)" name={`${prefix}t_isolation_s`} initialValue={600}>
          <InputNumber min={1} step={10} style={{ width: '100%' }} />
        </Form.Item>
      </>
    );
  }
  if (scenario === 'REACTION_RUNAWAY') {
    return (
      <>
        <Form.Item label="反应放热 Q_rxn (W)" name={`${prefix}Q_rxn_w`} initialValue={50000}>
          <InputNumber min={1} step={1000} style={{ width: '100%' }} />
        </Form.Item>
        <Form.Item label="分率 fraction_to_valve" name={`${prefix}fraction_to_valve`} initialValue={0.3}>
          <InputNumber min={0} max={1} step={0.05} style={{ width: '100%' }} />
        </Form.Item>
      </>
    );
  }
  return (
    <>
      <Form.Item label="液体体积 V_L (m³)" name={`${prefix}V_L_m3`} initialValue={1.0}>
        <InputNumber min={0.0001} step={0.1} style={{ width: '100%' }} />
      </Form.Item>
      <Form.Item label="液体密度 ρ_L (kg/m³)" name={`${prefix}rho_L_kg_m3`} initialValue={1000}>
        <InputNumber min={1} step={10} style={{ width: '100%' }} />
      </Form.Item>
      <Form.Item label="体膨胀系数 β (1/K)" name={`${prefix}beta_per_k`} initialValue={0.0001}>
        <InputNumber min={0} step={0.0001} style={{ width: '100%' }} />
      </Form.Item>
      <Form.Item label="温升 ΔT (K)" name={`${prefix}delta_T_k`} initialValue={30}>
        <InputNumber min={0} step={1} style={{ width: '100%' }} />
      </Form.Item>
      <Form.Item label="加热时间 t_heat (s)" name={`${prefix}t_heat_s`} initialValue={3600}>
        <InputNumber min={1} step={60} style={{ width: '100%' }} />
      </Form.Item>
    </>
  );
}

// ---------------------------------------------------------------------------
// sizing_params 三相态表单
// ---------------------------------------------------------------------------

interface SizingFormProps {
  phase: ReliefPhase;
}

function SizingParamsForm({ phase }: SizingFormProps): JSX.Element {
  const showGas = phase !== 'LIQUID';
  return (
    <>
      <Form.Item label="所需泄放量 W (kg/s)" name="relief_mass_flow_kgs" initialValue={0.005} rules={[{ required: true }]}>
        <InputNumber min={0.0001} step={0.001} style={{ width: '100%' }} />
      </Form.Item>
      <Form.Item label="背压 P_back (Pa)" name="P_back_pa" initialValue={100000}>
        <InputNumber min={0} step={1000} style={{ width: '100%' }} />
      </Form.Item>
      <Form.Item label="整定压力 P_set (Pa)" name="P_set_pa" initialValue={200000}>
        <InputNumber min={0} step={1000} style={{ width: '100%' }} />
      </Form.Item>
      {showGas && (
        <>
          <Form.Item label="温度 T (K)" name="T_k" initialValue={350}>
            <InputNumber min={0} step={1} style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item label="分子量 M (kg/mol)" name="M_kg_per_mol" initialValue={0.029}>
            <InputNumber min={0.001} step={0.001} style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item label="压缩因子 Z" name="Z" initialValue={1.0}>
            <InputNumber min={0.01} max={5} step={0.01} style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item label="比热容比 k_cp" name="k_cp_ratio" initialValue={1.4}>
            <InputNumber min={1.0} max={2.0} step={0.01} style={{ width: '100%' }} />
          </Form.Item>
        </>
      )}
      {phase === 'LIQUID' && (
        <Form.Item label="液体密度 ρ_L (kg/m³)" name="rho_L_kg_m3" initialValue={850}>
          <InputNumber min={1} step={10} style={{ width: '100%' }} />
        </Form.Item>
      )}
    </>
  );
}

// ---------------------------------------------------------------------------
// 结果面板
// ---------------------------------------------------------------------------

interface ResultPanelProps {
  result: PsvCalculateResponse | null;
  allResults: PsvCalculateResponse[] | null;
  designStage: DesignStage;
  error: string | null;
}

function ResultPanel({ result, allResults, designStage, error }: ResultPanelProps): JSX.Element {
  if (error && !result) {
    return <Alert type="error" message={error} data-testid="psv-result-error" />;
  }
  if (!result) {
    return (
      <Empty description="尚未执行计算；请到「输入与计算」提交" data-testid="psv-result-empty" />
    );
  }

  const r = result.result;
  const detail = designStage === 'DETAIL';
  const dominantScenario = r.aggregate.dominant_scenario;

  return (
    <Space direction="vertical" size={16} style={{ width: '100%' }}>
      <Row gutter={16}>
        <Col span={6}>
          <Statistic
            title="record_hash"
            value={result.record_hash}
            data-testid="psv-record-hash"
          />
        </Col>
        <Col span={6}>
          <Statistic title="lineage 数量" value={result.lineage_ids.length} />
        </Col>
        <Col span={6}>
          <Statistic title="泄放面积 (m²)" value={r.relief_area.area_required_m2} precision={6} />
        </Col>
        <Col span={6}>
          <Statistic title="孔口" value={r.orifice.selected_size} />
        </Col>
      </Row>

      <Card title="出口流（PSV_CALCULATED）" size="small" data-testid="psv-outlet-card">
        {result.outlet_stream_id ? (
          <Descriptions size="small" column={2}>
            <Descriptions.Item label="Stream ID">
              <code>{result.outlet_stream_id}</code>
            </Descriptions.Item>
            <Descriptions.Item label="Name">{result.outlet_stream_name}</Descriptions.Item>
            <Descriptions.Item label="状态">
              <Tag color="default">DRAFT</Tag>
            </Descriptions.Item>
            <Descriptions.Item label="source_type">
              <Tag color="blue">PSV_CALCULATED</Tag>
            </Descriptions.Item>
          </Descriptions>
        ) : (
          <Empty description="未生成出口流" />
        )}
      </Card>

      <Card title="aggregate（主导工况 = 最大喉径）" size="small">
        <Descriptions size="small" column={2}>
          <Descriptions.Item label="dominant_scenario">
            <Tag color="purple">{SCENARIO_LABELS[dominantScenario] ?? dominantScenario}</Tag>
          </Descriptions.Item>
          <Descriptions.Item label="case_count">{r.aggregate.case_count}</Descriptions.Item>
          <Descriptions.Item label="set_pressure_pa">{r.set_pressure_pa}</Descriptions.Item>
          <Descriptions.Item label="blowdown">{r.blowdown_fraction * 100}%</Descriptions.Item>
          <Descriptions.Item label="standard_profile_code">
            <Tag color="cyan">{r.standard_profile_code}</Tag>
          </Descriptions.Item>
        </Descriptions>
      </Card>

      <Card title="relief_area / orifice" size="small">
        <Descriptions size="small" column={2}>
          <Descriptions.Item label="area_required_m2">
            {r.relief_area.area_required_m2}
          </Descriptions.Item>
          <Descriptions.Item label="medium">{r.relief_area.medium}</Descriptions.Item>
          <Descriptions.Item label="orifice.selected_size">
            {r.orifice.selected_size}
          </Descriptions.Item>
          <Descriptions.Item label="actual_area_m2">{r.orifice.actual_area_m2}</Descriptions.Item>
          <Descriptions.Item label="inlet_size">{r.orifice.inlet_size}</Descriptions.Item>
          <Descriptions.Item label="outlet_size">{r.orifice.outlet_size}</Descriptions.Item>
        </Descriptions>
      </Card>

      {detail && r.valve_type !== undefined && (
        <Card title="选型响应（SUP-P5-PSV-002 V1.14）" size="small" data-testid="psv-selection-result-card">
          <Descriptions size="small" column={2}>
            <Descriptions.Item label="阀体型式">
              <Tag color="cyan">{r.valve_type}</Tag>
            </Descriptions.Item>
            <Descriptions.Item label="阀体材料">
              <Tag color="blue">{r.body_material}</Tag>
            </Descriptions.Item>
            {r.bellows_material && (
              <Descriptions.Item label="波纹管材料">
                <Tag color="geekblue">{r.bellows_material}</Tag>
              </Descriptions.Item>
            )}
            <Descriptions.Item label="法兰等级">
              <Tag>{r.flange_class}</Tag>
            </Descriptions.Item>
            <Descriptions.Item label="背压">
              {r.back_pressure_pct}% ({r.back_pressure_type})
            </Descriptions.Item>
            <Descriptions.Item label="超压">
              {(r.overpressure_pct ?? 0) * 100}%
            </Descriptions.Item>
            <Descriptions.Item label="Kb 修正">
              <Tag color="cyan">
                {r.kb_factor?.toFixed(4) ?? '—'} ({r.kb_source ?? '—'})
              </Tag>
            </Descriptions.Item>
            <Descriptions.Item label="CDTP 修正">
              {r.cdtp_applied ? <Tag color="green">已应用</Tag> : <Tag>否</Tag>}
            </Descriptions.Item>
            {r.rupture_disc_kc != null && (
              <Descriptions.Item label="爆破膜 Kc">
                <Tag color="orange">{r.rupture_disc_kc}</Tag>
              </Descriptions.Item>
            )}
            {r.valve_brand && (
              <Descriptions.Item label="阀体品牌">
                <Tag color="purple">{r.valve_brand}</Tag>
              </Descriptions.Item>
            )}
          </Descriptions>
        </Card>
      )}

      {detail && r.warnings && r.warnings.length > 0 && (
        <Card title="V1.14 §6 警告（G18/G19/G22/G23/G24/G25）" size="small" data-testid="psv-warnings-card">
          <Space direction="vertical" size={4} style={{ width: '100%' }}>
            {r.warnings.map((w, i) => (
              <Alert key={i} type="warning" showIcon message={w} />
            ))}
          </Space>
        </Card>
      )}

      {allResults && allResults.length > 1 && (
        <Card
          title={`多工况对比（共 ${allResults.length} 工况，最大喉径 = 主导）`}
          size="small"
          data-testid="psv-multi-scenario-table-card"
        >
          <Table
            size="small"
            rowKey={(r2) => r2.result.relief_scenario}
            pagination={false}
            dataSource={allResults.map((r2) => ({
              ...r2,
              is_dominant: r2.result.orifice.actual_area_m2 === result.result.orifice.actual_area_m2,
            }))}
            columns={[
              {
                title: '工况',
                dataIndex: ['result', 'relief_scenario'],
                render: (s: ReliefScenario) => SCENARIO_LABELS[s] ?? s,
              },
              {
                title: '孔口',
                dataIndex: ['result', 'orifice', 'selected_size'],
                render: (v: string, row: PsvCalculateResponse & { is_dominant: boolean }) => (
                  <Space>
                    <Tag color="cyan">{v}</Tag>
                    {row.is_dominant && <Tag color="gold">最大（主导）</Tag>}
                  </Space>
                ),
              },
              {
                title: 'actual_area_m2',
                dataIndex: ['result', 'orifice', 'actual_area_m2'],
                render: (v: number) => v.toExponential(4),
              },
              {
                title: '泄放面积 m²',
                dataIndex: ['result', 'relief_area', 'area_required_m2'],
                render: (v: number) => v.toExponential(4),
              },
              { title: 'record_hash', dataIndex: 'record_hash' },
            ]}
          />
        </Card>
      )}

      {detail && (
        <Card title="标准溯源（DETAIL 模式）" size="small" data-testid="psv-formula-ref-card">
          <Table
            size="small"
            rowKey="key"
            pagination={false}
            dataSource={Object.entries(r.standard_refs_json).map(([k, v]) => ({
              key: k,
              standard: v.standard,
              version: v.version,
              clause: v.clause,
            }))}
            columns={[
              { title: '子项', dataIndex: 'key', width: 120 },
              { title: 'standard', dataIndex: 'standard' },
              { title: 'version', dataIndex: 'version', width: 100 },
              { title: 'clause', dataIndex: 'clause' },
            ]}
          />
        </Card>
      )}
    </Space>
  );
}

// ---------------------------------------------------------------------------
// scenario_params 构造器（按 4 种 relief_scenario 路由）
// ---------------------------------------------------------------------------

function buildScenarioParams(
  scenario: ReliefScenario,
  values: Record<string, number>,
): ScenarioParams {
  switch (scenario) {
    case 'FIRE': {
      const p: FireScenarioParams = {
        kind: 'FIRE',
        D_m: values.D_m,
        H_m: values.H_m,
        liquid_level_fraction: values.liquid_level_fraction,
        environment_factor_F: values.environment_factor_F,
        h_fg_j_per_kg: values.h_fg_j_per_kg,
      };
      return p;
    }
    case 'CLOSED_VALVE': {
      const p: ClosedValveScenarioParams = {
        kind: 'CLOSED_VALVE',
        V_pipe_m3: values.V_pipe_m3,
        rho_L_kg_m3: values.rho_L_kg_m3,
        t_isolation_s: values.t_isolation_s,
      };
      return p;
    }
    case 'REACTION_RUNAWAY': {
      const p: ReactionRunawayScenarioParams = {
        kind: 'REACTION_RUNAWAY',
        Q_rxn_w: values.Q_rxn_w,
        fraction_to_valve: values.fraction_to_valve,
      };
      return p;
    }
    case 'THERMAL_EXPANSION': {
      const p: ThermalExpansionScenarioParams = {
        kind: 'THERMAL_EXPANSION',
        V_L_m3: values.V_L_m3,
        rho_L_kg_m3: values.rho_L_kg_m3,
        beta_per_k: values.beta_per_k,
        delta_T_k: values.delta_T_k,
        t_heat_s: values.t_heat_s,
      };
      return p;
    }
  }
}