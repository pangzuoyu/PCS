/**
 * PsvComputePage — PSV 安全阀计算界面（P5-3-6 / Task 18）。
 *
 * SPEC §7.11.5：
 * - 4 端点对应 4 卡片：relief / area / orifice / standard
 * - relief 多工况叠加 → max_mass_flow 取最大
 * - 标准由项目配置注入（API / GB / CUSTOM）；先导式阀拦截提示
 * - V1：单 Page 内 4 Tab 切换（antd Tabs）
 */
import { useState } from 'react';
import type { JSX } from 'react';
import {
  Alert,
  Button,
  Card,
  Col,
  Descriptions,
  Form,
  InputNumber,
  Row,
  Select,
  Space,
  Statistic,
  Table,
  Tabs,
  Tag,
  Typography,
} from 'antd';

import { PageHeader } from '../../components/common/PageHeader';
import type {
  FireCaseInput,
  FireCaseResult,
  OrificeResult,
  ReliefAggregateResult,
  ReliefAreaInput,
  ReliefAreaResult,
  ReliefScenario,
} from '../../types/psv';

interface StreamLite {
  stream_id: string;
  tag_number: string;
  sign_status: string;
}

interface Props {
  streams: StreamLite[];
  projectStandard?: string;
  onFireCaseCalculate?: (input: FireCaseInput) => FireCaseResult | undefined;
  onReliefAreaCalculate?: (
    input: ReliefAreaInput,
  ) => ReliefAreaResult | undefined;
  onOrificeSelect?: (area_m2: number) => OrificeResult | undefined;
}

const SCENARIO_OPTIONS: { value: ReliefScenario; label: string }[] = [
  { value: 'FIRE', label: '火灾工况' },
  { value: 'CLOSED_VALVE', label: '阀门关闭' },
  { value: 'REACTION_RUNAWAY', label: '反应失控' },
  { value: 'THERMAL_EXPANSION', label: '热膨胀' },
];

export function PsvComputePage({
  streams,
  projectStandard = 'API',
  onFireCaseCalculate,
  onReliefAreaCalculate,
  onOrificeSelect,
}: Props): JSX.Element {
  return (
    <div data-testid="psv-compute-page">
      <PageHeader
        title="PSV 安全阀计算"
        module="PSV"
        actions={
          <Tag color="blue" data-testid="psv-standard-tag">
            项目标准：{projectStandard}
          </Tag>
        }
      />

      <Tabs
        defaultActiveKey="relief"
        data-testid="psv-tabs"
        items={[
          {
            key: 'relief',
            label: '泄放工况',
            children: (
              <ReliefTab
                streams={streams}
                onFireCaseCalculate={onFireCaseCalculate}
              />
            ),
          },
          {
            key: 'area',
            label: '泄放面积',
            children: (
              <AreaTab onReliefAreaCalculate={onReliefAreaCalculate} />
            ),
          },
          {
            key: 'orifice',
            label: '孔口选型',
            children: <OrificeTab onOrificeSelect={onOrificeSelect} />,
          },
        ]}
      />
    </div>
  );
}

// ============================ 泄放工况 Tab ============================

interface ReliefTabProps {
  streams: StreamLite[];
  onFireCaseCalculate?: (input: FireCaseInput) => FireCaseResult | undefined;
}

function ReliefTab({ streams, onFireCaseCalculate }: ReliefTabProps): JSX.Element {
  const [scenarios, setScenarios] = useState<ReliefScenario[]>(['FIRE']);
  const [streamId, setStreamId] = useState<string | undefined>();
  const [aggregate, setAggregate] = useState<ReliefAggregateResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const checkedStreams = streams.filter((s) => s.sign_status === 'CHECKED');

  const handleCalculate = () => {
    if (!streamId) {
      setError('请选择物流');
      return;
    }
    setError(null);
    try {
      // V1 mock：仅 FIRE 场景示例
      const fireInput: FireCaseInput = {
        source_stream_id: streamId,
        vessel_type: 'VERTICAL',
        D_m: 3.0,
        H_m: 10.0,
        liquid_level_fraction: 0.5,
        environment_factor_F: 1.0,
        h_fg_input_kj_per_kg: 350,
      };
      const r = onFireCaseCalculate
        ? onFireCaseCalculate(fireInput)
        : mockFireCase(fireInput);
      if (!r) {
        setError('计算失败：返回空');
        setAggregate(null);
        return;
      }
      setAggregate({
        max_mass_flow_kgs: r.relief_mass_flow_kgs,
        max_volume_flow_m3s: r.relief_volume_flow_m3s,
        max_scenario: 'FIRE',
        per_scenario_json: [
          {
            scenario: 'FIRE',
            mass_flow_kgs: r.relief_mass_flow_kgs,
            volume_flow_m3s: r.relief_volume_flow_m3s,
            formula_ref: r.formula_ref as unknown as Record<string, string>,
          },
        ],
      });
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : '未知错误');
      setAggregate(null);
    }
  };

  return (
    <Row gutter={16}>
      <Col span={10}>
        <Card title="输入条件" size="small">
          <Form layout="vertical">
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
            <Form.Item label="工况">
              <Select
                mode="multiple"
                data-testid="psv-scenarios"
                value={scenarios}
                onChange={(v) => setScenarios(v as ReliefScenario[])}
                options={SCENARIO_OPTIONS}
              />
            </Form.Item>
            <Form.Item>
              <Button
                type="primary"
                data-testid="psv-calculate"
                onClick={handleCalculate}
              >
                计算
              </Button>
            </Form.Item>
          </Form>
        </Card>
      </Col>

      <Col span={14}>
        <Card title="结果" size="small" data-testid="psv-result-card">
          {error && (
            <Alert
              type="error"
              message={error}
              data-testid="psv-error"
              style={{ marginBottom: 12 }}
            />
          )}
          {!aggregate && !error && (
            <Typography.Text type="secondary">点击「计算」开始</Typography.Text>
          )}
          {aggregate && (
            <Space direction="vertical" size={16} style={{ width: '100%' }}>
              <Row gutter={16}>
                <Col span={8}>
                  <Statistic
                    title="max mass flow (kg/s)"
                    value={aggregate.max_mass_flow_kgs}
                    precision={3}
                    data-testid="psv-max-mass-flow"
                  />
                </Col>
                <Col span={8}>
                  <Statistic
                    title="max volume flow (m³/s)"
                    value={aggregate.max_volume_flow_m3s}
                    precision={4}
                  />
                </Col>
                <Col span={8}>
                  <Statistic
                    title="max scenario"
                    value={aggregate.max_scenario}
                    data-testid="psv-max-scenario"
                  />
                </Col>
              </Row>

              <Descriptions size="small" column={1}>
                <Descriptions.Item label="工况明细">
                  <Table
                    size="small"
                    rowKey="scenario"
                    pagination={false}
                    data-testid="psv-per-scenario-table"
                    dataSource={aggregate.per_scenario_json}
                    columns={[
                      { title: '工况', dataIndex: 'scenario', width: 100 },
                      {
                        title: 'mass_flow (kg/s)',
                        dataIndex: 'mass_flow_kgs',
                        render: (v: number) => v.toFixed(3),
                      },
                      {
                        title: 'volume_flow (m³/s)',
                        dataIndex: 'volume_flow_m3s',
                        render: (v: number) => v.toFixed(4),
                      },
                    ]}
                  />
                </Descriptions.Item>
              </Descriptions>
            </Space>
          )}
        </Card>
      </Col>
    </Row>
  );
}

// ============================ 泄放面积 Tab ============================

interface AreaTabProps {
  onReliefAreaCalculate?: (input: ReliefAreaInput) => ReliefAreaResult | undefined;
}

function AreaTab({ onReliefAreaCalculate }: AreaTabProps): JSX.Element {
  const [input, setInput] = useState<Partial<ReliefAreaInput>>({
    medium: 'GAS',
    omega_method: 'two_point',
  });
  const [result, setResult] = useState<ReliefAreaResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleCalculate = () => {
    setError(null);
    try {
      const r = onReliefAreaCalculate
        ? onReliefAreaCalculate(input as ReliefAreaInput)
        : mockArea(input as ReliefAreaInput);
      if (!r) {
        setError('计算失败：返回空');
        setResult(null);
        return;
      }
      setResult(r);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : '未知错误');
      setResult(null);
    }
  };

  return (
    <Row gutter={16}>
      <Col span={10}>
        <Card title="输入条件" size="small">
          <Form layout="vertical">
            <Form.Item label="介质">
              <Select
                data-testid="psv-area-medium"
                value={input.medium}
                onChange={(v) => setInput((s) => ({ ...s, medium: v }))}
                options={[
                  { value: 'GAS', label: '气体' },
                  { value: 'VAPOR', label: '蒸汽' },
                  { value: 'LIQUID', label: '液体' },
                  { value: 'TWO_PHASE', label: '两相流' },
                ]}
              />
            </Form.Item>
            <Form.Item label="mass_flow (kg/s)">
              <InputNumber
                data-testid="psv-area-mass-flow"
                value={input.mass_flow_kgs}
                onChange={(v) =>
                  setInput((s) => ({ ...s, mass_flow_kgs: v ?? 0 }))
                }
              />
            </Form.Item>
            <Form.Item label="P (Pa)">
              <InputNumber
                value={input.pressure_pa}
                onChange={(v) =>
                  setInput((s) => ({ ...s, pressure_pa: v ?? 0 }))
                }
              />
            </Form.Item>
            <Form.Item label="T (K)">
              <InputNumber
                value={input.temperature_k}
                onChange={(v) =>
                  setInput((s) => ({ ...s, temperature_k: v ?? 0 }))
                }
              />
            </Form.Item>
            <Form.Item label="Z">
              <InputNumber
                step={0.01}
                value={input.Z}
                onChange={(v) => setInput((s) => ({ ...s, Z: v ?? 1 }))}
              />
            </Form.Item>
            <Form.Item label="M (kg/kmol)">
              <InputNumber
                value={input.M_kg_kmol}
                onChange={(v) => setInput((s) => ({ ...s, M_kg_kmol: v ?? 0 }))}
              />
            </Form.Item>
            <Form.Item label="ω 方法 (气体/蒸汽)">
              <Select
                value={input.omega_method}
                onChange={(v) => setInput((s) => ({ ...s, omega_method: v }))}
                options={[
                  { value: 'single_point', label: '单点法' },
                  { value: 'two_point', label: '两点法' },
                  { value: 'direct_integration', label: '直接积分' },
                ]}
              />
            </Form.Item>
            <Form.Item>
              <Button type="primary" onClick={handleCalculate}>
                计算
              </Button>
            </Form.Item>
          </Form>
        </Card>
      </Col>

      <Col span={14}>
        <Card title="结果" size="small">
          {error && <Alert type="error" message={error} />}
          {!result && !error && (
            <Typography.Text type="secondary">点击「计算」开始</Typography.Text>
          )}
          {result && (
            <Descriptions size="small" column={1}>
              <Descriptions.Item label="area (m²)">
                {result.area_m2.toExponential(3)}
              </Descriptions.Item>
              <Descriptions.Item label="medium">
                <Tag color="blue">{result.medium}</Tag>
              </Descriptions.Item>
              <Descriptions.Item label="ω method">
                <Tag color="green">{result.omega_method ?? '-'}</Tag>
              </Descriptions.Item>
            </Descriptions>
          )}
        </Card>
      </Col>
    </Row>
  );
}

// ============================ 孔口选型 Tab ============================

interface OrificeTabProps {
  onOrificeSelect?: (area_m2: number) => OrificeResult | undefined;
}

function OrificeTab({ onOrificeSelect }: OrificeTabProps): JSX.Element {
  const [area, setArea] = useState<number>(0.001);
  const [result, setResult] = useState<OrificeResult | null>(null);

  const handleSelect = () => {
    const r = onOrificeSelect ? onOrificeSelect(area) : mockOrifice(area);
    setResult(r ?? null);
  };

  return (
    <Row gutter={16}>
      <Col span={10}>
        <Card title="输入" size="small">
          <Form layout="vertical">
            <Form.Item label="所需面积 (m²)">
              <InputNumber
                data-testid="psv-orifice-area"
                value={area}
                step={0.001}
                onChange={(v) => setArea(v ?? 0)}
              />
            </Form.Item>
            <Form.Item>
              <Button
                type="primary"
                data-testid="psv-orifice-select"
                onClick={handleSelect}
              >
                选型
              </Button>
            </Form.Item>
          </Form>
        </Card>
      </Col>
      <Col span={14}>
        <Card title="结果" size="small">
          {!result && <Typography.Text type="secondary">点击「选型」开始</Typography.Text>}
          {result && (
            <Descriptions size="small" column={1}>
              <Descriptions.Item label="孔口代号">
                <Tag color="green" data-testid="psv-orifice-designation">
                  {result.selected_orifice}
                </Tag>
              </Descriptions.Item>
              <Descriptions.Item label="实际面积 (m²)">
                {result.orifice_area_m2.toExponential(3)}
              </Descriptions.Item>
              {result.required_diameter_mm !== undefined && (
                <Descriptions.Item label="所需流道直径 (mm)">
                  {result.required_diameter_mm.toFixed(2)}
                </Descriptions.Item>
              )}
            </Descriptions>
          )}
        </Card>
      </Col>
    </Row>
  );
}

// ============================ Mocks ============================

function mockFireCase(inp: FireCaseInput): FireCaseResult {
  const wetted_area_m2 = Math.PI * inp.D_m * inp.H_m;
  const A_pow_082 = Math.pow(wetted_area_m2, 0.82);
  const heat_input_w = 63600 * A_pow_082 * inp.environment_factor_F;
  const h_fg = inp.h_fg_input_kj_per_kg * 1000;
  const relief_mass_flow_kgs = heat_input_w / h_fg;
  return {
    wetted_area_m2,
    heat_input_w,
    relief_mass_flow_kgs,
    relief_volume_flow_m3s: relief_mass_flow_kgs / 1.2,
    h_fg_j_per_kg: h_fg,
    c_factor: 21000,
    F_factor: inp.environment_factor_F,
    formula_ref: {
      standard: 'API_521',
      version: '7th',
      clause: '§5.15.2.2.1 / Table 5',
    },
  };
}

function mockArea(inp: ReliefAreaInput): ReliefAreaResult {
  // API 520 气体 A = W / (C·Kd·P1·Kb) × √(T·Z/M)
  const C = 0.85;
  const Kd = 0.95;
  const Kb = 1.0;
  const denom = C * Kd * inp.pressure_pa * Kb;
  const num = inp.mass_flow_kgs * Math.sqrt(inp.temperature_k * inp.Z / inp.M_kg_kmol);
  const area_m2 = num / denom;
  return {
    area_m2,
    medium: inp.medium,
    omega_method: inp.omega_method,
    formula_ref: {
      standard: 'API_520',
      version: '10th',
      clause: '§5.5.3',
    },
  };
}

// API 526 标准孔口表（D~T，in² → m²）
const API526_ORIFICES: Array<{ designation: string; area_in2: number }> = [
  { designation: 'D', area_in2: 0.110 },
  { designation: 'E', area_in2: 0.196 },
  { designation: 'F', area_in2: 0.307 },
  { designation: 'G', area_in2: 0.503 },
  { designation: 'H', area_in2: 0.785 },
  { designation: 'J', area_in2: 1.287 },
  { designation: 'K', area_in2: 1.838 },
  { designation: 'L', area_in2: 2.853 },
  { designation: 'M', area_in2: 3.600 },
  { designation: 'N', area_in2: 4.340 },
  { designation: 'P', area_in2: 6.380 },
  { designation: 'Q', area_in2: 11.05 },
  { designation: 'R', area_in2: 16.00 },
  { designation: 'T', area_in2: 26.00 },
];

const IN2_TO_M2 = 6.4516e-4;

function mockOrifice(area_m2: number): OrificeResult {
  const target_in2 = area_m2 / IN2_TO_M2;
  for (const o of API526_ORIFICES) {
    if (o.area_in2 >= target_in2) {
      return {
        selected_orifice: o.designation,
        orifice_area_m2: o.area_in2 * IN2_TO_M2,
        formula_ref: {
          standard: 'API_526',
          version: 'latest',
          clause: 'Table 1',
        },
      };
    }
  }
  const last = API526_ORIFICES[API526_ORIFICES.length - 1];
  return {
    selected_orifice: last.designation,
    orifice_area_m2: last.area_in2 * IN2_TO_M2,
    formula_ref: {
      standard: 'API_526',
      version: 'latest',
      clause: 'Table 1',
    },
  };
}

export default PsvComputePage;