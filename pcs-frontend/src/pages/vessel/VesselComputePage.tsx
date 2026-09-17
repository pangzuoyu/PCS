/**
 * VesselComputePage — VESSEL 容器计算界面（P5-1-4 / Task 5）。
 *
 * SPEC §7.11.3（V1.0 仅列模块名，详细字段以 plan + 后端 OpenAPI 为准）：
 * - 物流选择（仅 CHECKED 状态可计算；DRAFT → 后端 403 STREAM_NOT_CHECKED）
 * - 容器类型 VERTICAL / HORIZONTAL / WITH_DEMISTER
 * - sizing：ρ_L / ρ_V / Q_L / Q_V / 停留时间（0=默认）/ K 因子
 * - hydraulics：D/L/h0/d_orifice/Cd_orifice/Q_in/d_overflow/h_overflow/Cd_overflow/orientation
 * - 计算按钮触发 → 结果卡片（sizing + hydraulics 合并 result）
 *
 * V1：单 Page 渲染 sizing + hydraulics 两个 Card。
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
  Radio,
  Row,
  Select,
  Space,
  Statistic,
  Tag,
  Typography,
} from 'antd';

import { PageHeader } from '../../components/common/PageHeader';
import type {
  VesselCalculateRequest,
  VesselCalculateResponse,
  VesselHydraulics,
  VesselOrientation,
  VesselSizing,
  VesselType,
} from '../../types/vessel';

interface StreamLite {
  stream_id: string;
  tag_number: string;
  sign_status: string;
}

interface Props {
  streams: StreamLite[];
  onCalculate?: (
    req: VesselCalculateRequest,
  ) => VesselCalculateResponse | undefined;
}

const VESSEL_TYPE_OPTIONS: { value: VesselType; label: string }[] = [
  { value: 'VERTICAL', label: '立式容器' },
  { value: 'HORIZONTAL', label: '卧式容器' },
  { value: 'WITH_DEMISTER', label: '带除沫器' },
];

const DEFAULT_SIZING: VesselSizing = {
  vessel_type: 'VERTICAL',
  rho_L_kg_m3: 850,
  rho_V_kg_m3: 1.2,
  liquid_flow_m3_s: 0.005,
  vapor_flow_m3_s: 0.5,
  residence_time_min: 5.0,
  K_factor_ms: 0.10,
};

const DEFAULT_HYDRAULICS: VesselHydraulics = {
  D_m: 1.0,
  L_m: 3.0,
  h0_m: 1.5,
  d_orifice_m: 0.05,
  Cd_orifice: 0.62,
  Q_in_liquid_m3_s: 0.005,
  d_overflow_m: 0.08,
  h_overflow_m: 1.0,
  Cd_overflow: 0.62,
  orientation: 'vertical',
  thermal_breathing_factor: 1.0,
};

export function VesselComputePage({ streams, onCalculate }: Props): JSX.Element {
  const [streamId, setStreamId] = useState<string | undefined>();
  const [sizing, setSizing] = useState<VesselSizing>(DEFAULT_SIZING);
  const [hydraulics, setHydraulics] = useState<VesselHydraulics>(DEFAULT_HYDRAULICS);
  const [result, setResult] = useState<VesselCalculateResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const checkedStreams = streams.filter((s) => s.sign_status === 'CHECKED');

  const handleCalculate = () => {
    if (!streamId) {
      setError('请选择物流');
      return;
    }
    setError(null);
    const req: VesselCalculateRequest = {
      source_stream_id: streamId,
      sizing,
      hydraulics,
    };
    try {
      const r = onCalculate ? onCalculate(req) : defaultMockResult(req);
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
    <div data-testid="vessel-compute-page">
      <PageHeader
        title="VESSEL 容器计算"
        module="VESSEL"
        actions={
          <Button
            type="primary"
            data-testid="vessel-calculate"
            onClick={handleCalculate}
          >
            计算
          </Button>
        }
      />

      <Row gutter={16}>
        <Col span={10}>
          <Card title="输入条件" size="small">
            <Form layout="vertical">
              <Form.Item label="物流" required>
                <Select
                  data-testid="vessel-stream-select"
                  placeholder="选择 CHECKED 物流"
                  value={streamId}
                  onChange={setStreamId}
                  options={checkedStreams.map((s) => ({
                    value: s.stream_id,
                    label: s.tag_number,
                  }))}
                />
              </Form.Item>

              <Card type="inner" title="Sizing（容器尺寸）" size="small" style={{ marginBottom: 12 }}>
                <Space direction="vertical" style={{ width: '100%' }}>
                  <Form.Item label="容器类型">
                    <Radio.Group
                      data-testid="vessel-type"
                      value={sizing.vessel_type}
                      onChange={(e) =>
                        setSizing((s) => ({
                          ...s,
                          vessel_type: e.target.value as VesselType,
                        }))
                      }
                    >
                      <Space direction="vertical">
                        {VESSEL_TYPE_OPTIONS.map((o) => (
                          <Radio key={o.value} value={o.value}>
                            {o.label}
                          </Radio>
                        ))}
                      </Space>
                    </Radio.Group>
                  </Form.Item>
                  <NumberRow
                    label="ρ_L (kg/m³)"
                    testId="vessel-rho-L"
                    value={sizing.rho_L_kg_m3}
                    onChange={(v) =>
                      setSizing((s) => ({ ...s, rho_L_kg_m3: v ?? 0 }))
                    }
                  />
                  <NumberRow
                    label="ρ_V (kg/m³)"
                    testId="vessel-rho-V"
                    value={sizing.rho_V_kg_m3}
                    onChange={(v) =>
                      setSizing((s) => ({ ...s, rho_V_kg_m3: v ?? 0 }))
                    }
                  />
                  <NumberRow
                    label="Q_L (m³/s)"
                    testId="vessel-q-L"
                    step={0.001}
                    value={sizing.liquid_flow_m3_s}
                    onChange={(v) =>
                      setSizing((s) => ({ ...s, liquid_flow_m3_s: v ?? 0 }))
                    }
                  />
                  <NumberRow
                    label="Q_V (m³/s)"
                    testId="vessel-q-V"
                    step={0.01}
                    value={sizing.vapor_flow_m3_s}
                    onChange={(v) =>
                      setSizing((s) => ({ ...s, vapor_flow_m3_s: v ?? 0 }))
                    }
                  />
                  <NumberRow
                    label="停留时间 (min, 0=默认)"
                    testId="vessel-residence"
                    value={sizing.residence_time_min}
                    onChange={(v) =>
                      setSizing((s) => ({ ...s, residence_time_min: v ?? 0 }))
                    }
                  />
                  <NumberRow
                    label="K 因子 (m/s)"
                    testId="vessel-K"
                    step={0.01}
                    value={sizing.K_factor_ms}
                    onChange={(v) =>
                      setSizing((s) => ({ ...s, K_factor_ms: v ?? 0 }))
                    }
                  />
                </Space>
              </Card>

              <Card type="inner" title="Hydraulics（流体力学）" size="small">
                <Space direction="vertical" style={{ width: '100%' }}>
                  <NumberRow
                    label="D (m)"
                    testId="vessel-D"
                    value={hydraulics.D_m}
                    onChange={(v) =>
                      setHydraulics((s) => ({ ...s, D_m: v ?? 0 }))
                    }
                  />
                  <NumberRow
                    label="L (m)"
                    testId="vessel-L"
                    value={hydraulics.L_m}
                    onChange={(v) =>
                      setHydraulics((s) => ({ ...s, L_m: v ?? 0 }))
                    }
                  />
                  <NumberRow
                    label="h0 (m)"
                    testId="vessel-h0"
                    value={hydraulics.h0_m}
                    onChange={(v) =>
                      setHydraulics((s) => ({ ...s, h0_m: v ?? 0 }))
                    }
                  />
                  <NumberRow
                    label="d_orifice (m)"
                    testId="vessel-d-orifice"
                    step={0.001}
                    value={hydraulics.d_orifice_m}
                    onChange={(v) =>
                      setHydraulics((s) => ({ ...s, d_orifice_m: v ?? 0 }))
                    }
                  />
                  <NumberRow
                    label="Cd_orifice"
                    testId="vessel-Cd-orifice"
                    step={0.01}
                    value={hydraulics.Cd_orifice}
                    onChange={(v) =>
                      setHydraulics((s) => ({ ...s, Cd_orifice: v ?? 0 }))
                    }
                  />
                  <NumberRow
                    label="Q_in (m³/s)"
                    testId="vessel-Q-in"
                    step={0.001}
                    value={hydraulics.Q_in_liquid_m3_s}
                    onChange={(v) =>
                      setHydraulics((s) => ({ ...s, Q_in_liquid_m3_s: v ?? 0 }))
                    }
                  />
                  <NumberRow
                    label="d_overflow (m)"
                    testId="vessel-d-overflow"
                    step={0.001}
                    value={hydraulics.d_overflow_m}
                    onChange={(v) =>
                      setHydraulics((s) => ({ ...s, d_overflow_m: v ?? 0 }))
                    }
                  />
                  <NumberRow
                    label="h_overflow (m)"
                    testId="vessel-h-overflow"
                    value={hydraulics.h_overflow_m}
                    onChange={(v) =>
                      setHydraulics((s) => ({ ...s, h_overflow_m: v ?? 0 }))
                    }
                  />
                  <NumberRow
                    label="Cd_overflow"
                    testId="vessel-Cd-overflow"
                    step={0.01}
                    value={hydraulics.Cd_overflow}
                    onChange={(v) =>
                      setHydraulics((s) => ({ ...s, Cd_overflow: v ?? 0 }))
                    }
                  />
                  <Form.Item label="朝向">
                    <Radio.Group
                      data-testid="vessel-orientation"
                      value={hydraulics.orientation}
                      onChange={(e) =>
                        setHydraulics((s) => ({
                          ...s,
                          orientation: e.target.value as VesselOrientation,
                        }))
                      }
                    >
                      <Radio value="vertical">vertical</Radio>
                      <Radio value="horizontal">horizontal（触发 orientation_warning）</Radio>
                    </Radio.Group>
                  </Form.Item>
                </Space>
              </Card>
            </Form>
          </Card>
        </Col>

        <Col span={14}>
          <Card title="结果" size="small" data-testid="vessel-result-card">
            {error && (
              <Alert
                type="error"
                message={error}
                data-testid="vessel-error"
                style={{ marginBottom: 12 }}
              />
            )}
            {!result && !error && (
              <Typography.Text type="secondary">点击「计算」开始</Typography.Text>
            )}
            {result && (
              <Space direction="vertical" size={16} style={{ width: '100%' }}>
                <Row gutter={16}>
                  <Col span={8}>
                    <Statistic
                      title="V_max (m/s)"
                      value={Number(result.result['V_max_ms'] ?? 0)}
                      precision={3}
                      data-testid="vessel-v-max"
                    />
                  </Col>
                  <Col span={8}>
                    <Statistic
                      title="D_min (m)"
                      value={Number(result.result['D_min_m'] ?? 0)}
                      precision={3}
                      data-testid="vessel-d-min"
                    />
                  </Col>
                  <Col span={8}>
                    <Statistic
                      title="持液量 (m³)"
                      value={Number(result.result['liquid_volume_m3'] ?? 0)}
                      precision={2}
                    />
                  </Col>
                </Row>

                <Descriptions size="small" column={2}>
                  <Descriptions.Item label="check">
                    {renderCheckTag(result.result['check_result'])}
                  </Descriptions.Item>
                  <Descriptions.Item label="置信度">
                    <Tag color="blue">
                      {String(result.result['confidence'] ?? 'MEDIUM')}
                    </Tag>
                  </Descriptions.Item>
                  <Descriptions.Item label="Q_orifice (m³/s)">
                    {Number(result.result['Q_orifice_m3_s'] ?? 0).toPrecision(3)}
                  </Descriptions.Item>
                  <Descriptions.Item label="Q_overflow (m³/s)">
                    {Number(result.result['Q_overflow_m3_s'] ?? 0).toPrecision(3)}
                  </Descriptions.Item>
                  <Descriptions.Item label="t_drainage (min)">
                    {Number(result.result['t_drainage_min'] ?? 0).toFixed(2)}
                  </Descriptions.Item>
                </Descriptions>

                {typeof result.result['orientation_warning'] === 'string' && (
                  <Alert
                    type="warning"
                    message={String(result.result['orientation_warning'])}
                    data-testid="vessel-orientation-warning"
                  />
                )}
              </Space>
            )}
          </Card>
        </Col>
      </Row>
    </div>
  );
}

interface NumberRowProps {
  label: string;
  testId: string;
  value: number;
  step?: number;
  onChange: (v: number | null) => void;
}

function NumberRow({
  label,
  testId,
  value,
  step,
  onChange,
}: NumberRowProps): JSX.Element {
  return (
    <Form.Item label={label} style={{ marginBottom: 8 }}>
      <InputNumber
        data-testid={testId}
        value={value}
        step={step}
        style={{ width: '100%' }}
        onChange={onChange}
      />
    </Form.Item>
  );
}

function renderCheckTag(value: unknown): JSX.Element {
  const v = String(value ?? 'PASS');
  if (v === 'PASS') return <Tag color="green">PASS</Tag>;
  if (v === 'WARNING') return <Tag color="orange" data-testid="vessel-warning">WARNING</Tag>;
  return <Tag color="red">FAIL</Tag>;
}

function defaultMockResult(req: VesselCalculateRequest): VesselCalculateResponse {
  const { sizing, hydraulics } = req;
  // sizing
  const V_max_ms = sizing.K_factor_ms * Math.sqrt(
    (sizing.rho_L_kg_m3 - sizing.rho_V_kg_m3) / sizing.rho_V_kg_m3,
  );
  const D_min_m = Math.sqrt((4 * sizing.vapor_flow_m3_s) / (Math.PI * V_max_ms));
  const t = sizing.residence_time_min > 0 ? sizing.residence_time_min : 4.0;
  const liquid_volume_m3 = sizing.liquid_flow_m3_s * t * 60;
  const confidence =
    sizing.K_factor_ms >= 0.04 && sizing.K_factor_ms <= 0.10 ? 'HIGH' : 'MEDIUM';
  // hydraulics
  const A_orifice = Math.PI * (hydraulics.d_orifice_m / 2) ** 2;
  const Q_orifice_m3_s =
    hydraulics.Cd_orifice * A_orifice * Math.sqrt(2 * 9.81 * hydraulics.h0_m);
  const A_overflow = Math.PI * (hydraulics.d_overflow_m / 2) ** 2;
  const Q_overflow_m3_s =
    hydraulics.Cd_overflow *
    A_overflow *
    Math.sqrt(2 * 9.81 * Math.max(hydraulics.h0_m - hydraulics.h_overflow_m, 0));
  const t_drainage_min = Q_orifice_m3_s > 0 ? hydraulics.h0_m / Q_orifice_m3_s / 60 : 0;
  const orientation_warning =
    hydraulics.orientation === 'horizontal' &&
    hydraulics.D_m > 0 &&
    hydraulics.L_m / hydraulics.D_m < 3
      ? '卧式容器 L/D 偏小，建议复核长度'
      : undefined;
  return {
    calc_id: 'mock-vessel-id',
    calc_type: 'VESSEL',
    record_hash: 'mock-hash',
    stream_id: req.source_stream_id,
    lineage_ids: [],
    result: {
      V_max_ms,
      D_min_m,
      liquid_volume_m3,
      vessel_type: sizing.vessel_type,
      K_factor_ms: sizing.K_factor_ms,
      residence_time_min: t,
      check_result: confidence === 'HIGH' ? 'PASS' : 'WARNING',
      confidence,
      Q_orifice_m3_s,
      Q_overflow_m3_s,
      t_drainage_min,
      orientation_warning,
    },
    outlet_stream_id: 'mock-outlet-id',
    outlet_stream_name: 'OUT-VESSEL-201',
  };
}

export default VesselComputePage;