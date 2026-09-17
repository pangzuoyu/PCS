/**
 * PsvComputePage — PSV 安全阀计算界面（V1.2 SPEC §7.11.5）。
 *
 * 按 SPEC V1.2 + 后端 OpenAPI（commit 93627a7）：
 * - 单 Page 单 API 调用（POST /api/v1/psv/calculate）→ aggregate + relief_area + orifice + 标准溯源
 * - 4 种 relief_scenario 路由（FIRE/CLOSED_VALVE/REACTION_RUNAWAY/THERMAL_EXPANSION）
 * - design_stage BASIC ≤25 列 / DETAIL 完整切换
 * - 结果区展示 outlet_stream（PSV_CALCULATED）+ record_hash + lineage_ids + formula_ref_json
 * - 错误 envelope（403/404/422）按 code 分支提示
 *
 * 复用 api/psv.ts（commit 238f882）+ types/psv.ts（commit 61a3706）。
 */
import { useState } from 'react';
import type { JSX } from 'react';
import {
  Alert,
  Button,
  Card,
  Col,
  Descriptions,
  Empty,
  Form,
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

const PHASE_OPTIONS: { value: ReliefPhase; label: string }[] = [
  { value: 'GAS', label: '气体' },
  { value: 'LIQUID', label: '液体' },
  { value: 'TWO_PHASE', label: '两相流' },
];

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

export function PsvComputePage({
  streams,
  projectStandard = 'API',
}: Props): JSX.Element {
  const [streamId, setStreamId] = useState<string | undefined>();
  const [scenario, setScenario] = useState<ReliefScenario>('FIRE');
  const [phase, setPhase] = useState<ReliefPhase>('GAS');
  const [designStage, setDesignStage] = useState<DesignStage>('DETAIL');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<PsvCalculateResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const checkedStreams = streams.filter((s) => s.sign_status === 'CHECKED');

  const onCalculate = async (formValues: Record<string, number>) => {
    if (!streamId) {
      message.error('请先选择 CHECKED 物流');
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const scenario_params = buildScenarioParams(scenario, formValues);
      const req: PsvCalculateRequest = {
        source_stream_id: streamId,
        relief_scenario: scenario,
        scenario_params,
        sizing_params: {
          relief_mass_flow_kgs: formValues.relief_mass_flow_kgs,
          phase,
          P_back_pa: formValues.P_back_pa,
          P_set_pa: formValues.P_set_pa,
          T_k: formValues.T_k,
          M_kg_per_mol: formValues.M_kg_per_mol,
          Z: formValues.Z,
          k_cp_ratio: formValues.k_cp_ratio,
          rho_L_kg_m3: formValues.rho_L_kg_m3,
        },
        design_stage: designStage,
        blowdown_fraction: 0.05,
        inlet_size: '4 inch',
        outlet_size: '6 inch',
      };
      const resp = await psvApi.calculate(req);
      setResult(resp);
      message.success(`PSV 计算完成：record_hash=${resp.record_hash}`);
    } catch (err: unknown) {
      const env = extractPcsError(err);
      const code = env.code ?? '';
      const msg = env.message ?? 'PSV 计算失败';
      if (code === 'STREAM_NOT_CHECKED') {
        message.error('源流未签收，请先在物流一览完成 CHECKED 流程');
      } else if (code === 'SIM_STREAM_NOT_FOUND') {
        message.error('源流不存在，请重新选择');
      } else if (code === 'PSV_INPUT_ERROR') {
        message.error(`输入参数不合法：${msg}`);
      } else {
        message.error(msg);
      }
      setError(msg);
      setResult(null);
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
                scenario={scenario}
                setScenario={setScenario}
                phase={phase}
                setPhase={setPhase}
                checkedStreams={checkedStreams}
                loading={loading}
                onCalculate={onCalculate}
                error={error}
              />
            ),
          },
          {
            key: 'result',
            label: '结果',
            children: (
              <ResultPanel
                result={result}
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
  scenario: ReliefScenario;
  setScenario: (v: ReliefScenario) => void;
  phase: ReliefPhase;
  setPhase: (v: ReliefPhase) => void;
  checkedStreams: StreamLite[];
  loading: boolean;
  onCalculate: (values: Record<string, number>) => Promise<void>;
  error: string | null;
}

function InputPanel({
  streamId,
  setStreamId,
  scenario,
  setScenario,
  phase,
  setPhase,
  checkedStreams,
  loading,
  onCalculate,
  error,
}: InputPanelProps): JSX.Element {
  const [form] = Form.useForm();

  const handleSubmit = async () => {
    const values = await form.validateFields();
    await onCalculate(values as Record<string, number>);
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
            <Form.Item label="泄放工况">
              <Select
                data-testid="psv-scenario-select"
                value={scenario}
                onChange={setScenario}
                options={SCENARIO_OPTIONS}
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

            <ScenarioParamsForm scenario={scenario} />
            <SizingParamsForm phase={phase} />

            <Form.Item>
              <Button
                type="primary"
                data-testid="psv-calculate"
                loading={loading}
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
            <Descriptions.Item label="工况">{scenario}</Descriptions.Item>
            <Descriptions.Item label="相态">{phase}</Descriptions.Item>
          </Descriptions>
          <Typography.Paragraph type="secondary" style={{ marginTop: 12 }}>
            提交后端 → POST /api/v1/psv/calculate → 结果区显示 record_hash +
            outlet_stream + aggregate + relief_area + orifice。
          </Typography.Paragraph>
        </Card>
      </Col>
    </Row>
  );
}

// ---------------------------------------------------------------------------
// 4 种 scenario_params 动态表单
// ---------------------------------------------------------------------------

interface ScenarioFormProps {
  scenario: ReliefScenario;
}

function ScenarioParamsForm({ scenario }: ScenarioFormProps): JSX.Element {
  if (scenario === 'FIRE') {
    return (
      <>
        <Form.Item label="容器直径 D_m" name="D_m" initialValue={1.0} rules={[{ required: true }]}>
          <InputNumber min={0.1} step={0.1} style={{ width: '100%' }} />
        </Form.Item>
        <Form.Item label="容器高度 H_m" name="H_m" initialValue={5.0} rules={[{ required: true }]}>
          <InputNumber min={0.1} step={0.1} style={{ width: '100%' }} />
        </Form.Item>
        <Form.Item label="充液分率" name="liquid_level_fraction" initialValue={0.5}>
          <InputNumber min={0} max={1} step={0.05} style={{ width: '100%' }} />
        </Form.Item>
        <Form.Item label="环境因子 F" name="environment_factor_F" initialValue={1.0}>
          <InputNumber min={0} max={2} step={0.1} style={{ width: '100%' }} />
        </Form.Item>
        <Form.Item label="汽化潜热 h_fg (J/kg)" name="h_fg_j_per_kg" initialValue={350000}>
          <InputNumber min={1} step={1000} style={{ width: '100%' }} />
        </Form.Item>
      </>
    );
  }
  if (scenario === 'CLOSED_VALVE') {
    return (
      <>
        <Form.Item label="管段容积 V_pipe (m³)" name="V_pipe_m3" initialValue={0.1}>
          <InputNumber min={0.0001} step={0.01} style={{ width: '100%' }} />
        </Form.Item>
        <Form.Item label="液体密度 ρ_L (kg/m³)" name="rho_L_kg_m3" initialValue={850}>
          <InputNumber min={1} step={10} style={{ width: '100%' }} />
        </Form.Item>
        <Form.Item label="隔离时间 t_isolation (s)" name="t_isolation_s" initialValue={600}>
          <InputNumber min={1} step={10} style={{ width: '100%' }} />
        </Form.Item>
      </>
    );
  }
  if (scenario === 'REACTION_RUNAWAY') {
    return (
      <>
        <Form.Item label="反应放热 Q_rxn (W)" name="Q_rxn_w" initialValue={50000}>
          <InputNumber min={1} step={1000} style={{ width: '100%' }} />
        </Form.Item>
        <Form.Item label="分率 fraction_to_valve" name="fraction_to_valve" initialValue={0.3}>
          <InputNumber min={0} max={1} step={0.05} style={{ width: '100%' }} />
        </Form.Item>
      </>
    );
  }
  return (
    <>
      <Form.Item label="液体体积 V_L (m³)" name="V_L_m3" initialValue={1.0}>
        <InputNumber min={0.0001} step={0.1} style={{ width: '100%' }} />
      </Form.Item>
      <Form.Item label="液体密度 ρ_L (kg/m³)" name="rho_L_kg_m3" initialValue={1000}>
        <InputNumber min={1} step={10} style={{ width: '100%' }} />
      </Form.Item>
      <Form.Item label="体膨胀系数 β (1/K)" name="beta_per_k" initialValue={0.0001}>
        <InputNumber min={0} step={0.0001} style={{ width: '100%' }} />
      </Form.Item>
      <Form.Item label="温升 ΔT (K)" name="delta_T_k" initialValue={30}>
        <InputNumber min={0} step={1} style={{ width: '100%' }} />
      </Form.Item>
      <Form.Item label="加热时间 t_heat (s)" name="t_heat_s" initialValue={3600}>
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
  designStage: DesignStage;
  error: string | null;
}

function ResultPanel({ result, designStage, error }: ResultPanelProps): JSX.Element {
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

      <Card title="aggregate" size="small">
        <Descriptions size="small" column={2}>
          <Descriptions.Item label="dominant_scenario">
            <Tag color="purple">{r.aggregate.dominant_scenario}</Tag>
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