/**
 * VesselComputePage — VESSEL 容器计算界面（P5-1-4 / Task 5）。
 *
 * SPEC §7.11.3：
 * - 物流选择（仅 CHECKED 状态可计算；DRAFT → 后端 403 STREAM_NOT_CHECKED）
 * - 容器类型 VERTICAL / HORIZONTAL / WITH_DEMISTER
 * - 工艺参数：ρ_L / ρ_V / Q_L / Q_V / 停留时间（0=用默认区间中值）/ K 因子（CONFIG 默认 + 手动覆盖）
 * - 计算按钮触发 → 结果卡片（V_max / D_min / 持液量 / check / confidence）
 * - 卧式容器若 L/D < 3 → 黄色 orientation_warning（工程经验）
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
import type { VesselInput, VesselResult, VesselType } from '../../types/vessel';

interface StreamLite {
  stream_id: string;
  tag_number: string;
  sign_status: string;
}

interface Props {
  streams: StreamLite[];
  onCalculate?: (input: VesselInput) => VesselResult | undefined;
}

const VESSEL_TYPE_OPTIONS: { value: VesselType; label: string }[] = [
  { value: 'VERTICAL', label: '立式容器' },
  { value: 'HORIZONTAL', label: '卧式容器' },
  { value: 'WITH_DEMISTER', label: '带除沫器' },
];

function defaultMockResult(inp: VesselInput): VesselResult {
  // V1 mock：Souders-Brown + D_min + 持液量
  const V_max_ms = inp.K_factor_ms * Math.sqrt(
    (inp.rho_L_kg_m3 - inp.rho_V_kg_m3) / inp.rho_V_kg_m3,
  );
  const D_min_m = Math.sqrt((4 * inp.vapor_flow_m3_s) / (Math.PI * V_max_ms));
  const t = inp.residence_time_min > 0 ? inp.residence_time_min : 4.0;
  const liquid_volume_m3 = inp.liquid_flow_m3_s * t * 60;
  const confidence =
    inp.K_factor_ms >= 0.04 && inp.K_factor_ms <= 0.10 ? 'HIGH' : 'MEDIUM';
  const orientation_warning =
    inp.vessel_type === 'HORIZONTAL' && D_min_m < 1.5
      ? '卧式容器 L/D 偏小，建议复核长度'
      : undefined;
  return {
    V_max_ms,
    D_min_m,
    liquid_volume_m3,
    vessel_type: inp.vessel_type,
    K_factor_ms: inp.K_factor_ms,
    residence_time_min: t,
    check_result: confidence === 'HIGH' ? 'PASS' : 'WARNING',
    confidence,
    orientation_warning,
  };
}

export function VesselComputePage({ streams, onCalculate }: Props): JSX.Element {
  const [input, setInput] = useState<Partial<VesselInput>>({
    vessel_type: 'VERTICAL',
    rho_L_kg_m3: 850,
    rho_V_kg_m3: 1.2,
    liquid_flow_m3_s: 0.005,
    vapor_flow_m3_s: 0.5,
    residence_time_min: 5.0,
    K_factor_ms: 0.10,
  });
  const [result, setResult] = useState<VesselResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const checkedStreams = streams.filter((s) => s.sign_status === 'CHECKED');

  const handleCalculate = () => {
    if (!input.source_stream_id) {
      setError('请选择物流');
      return;
    }
    setError(null);
    const finalInput = input as VesselInput;
    try {
      const r = onCalculate ? onCalculate(finalInput) : defaultMockResult(finalInput);
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
                  value={input.source_stream_id}
                  onChange={(v) => setInput((s) => ({ ...s, source_stream_id: v }))}
                  options={checkedStreams.map((s) => ({
                    value: s.stream_id,
                    label: s.tag_number,
                  }))}
                />
              </Form.Item>

              <Form.Item label="容器类型">
                <Radio.Group
                  data-testid="vessel-type"
                  value={input.vessel_type}
                  onChange={(e) =>
                    setInput((s) => ({ ...s, vessel_type: e.target.value as VesselType }))
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

              <Form.Item label="ρ_L (kg/m³)">
                <InputNumber
                  data-testid="vessel-rho-L"
                  value={input.rho_L_kg_m3}
                  onChange={(v) => setInput((s) => ({ ...s, rho_L_kg_m3: v ?? 0 }))}
                />
              </Form.Item>
              <Form.Item label="ρ_V (kg/m³)">
                <InputNumber
                  data-testid="vessel-rho-V"
                  value={input.rho_V_kg_m3}
                  onChange={(v) => setInput((s) => ({ ...s, rho_V_kg_m3: v ?? 0 }))}
                />
              </Form.Item>
              <Form.Item label="液体流量 (m³/s)">
                <InputNumber
                  data-testid="vessel-q-L"
                  step={0.001}
                  value={input.liquid_flow_m3_s}
                  onChange={(v) => setInput((s) => ({ ...s, liquid_flow_m3_s: v ?? 0 }))}
                />
              </Form.Item>
              <Form.Item label="气体流量 (m³/s)">
                <InputNumber
                  data-testid="vessel-q-V"
                  step={0.01}
                  value={input.vapor_flow_m3_s}
                  onChange={(v) => setInput((s) => ({ ...s, vapor_flow_m3_s: v ?? 0 }))}
                />
              </Form.Item>
              <Form.Item label="停留时间 (min, 0=默认)">
                <InputNumber
                  data-testid="vessel-residence"
                  value={input.residence_time_min}
                  onChange={(v) => setInput((s) => ({ ...s, residence_time_min: v ?? 0 }))}
                />
              </Form.Item>
              <Form.Item label="K 因子 (m/s)">
                <InputNumber
                  data-testid="vessel-K"
                  step={0.01}
                  value={input.K_factor_ms}
                  onChange={(v) => setInput((s) => ({ ...s, K_factor_ms: v ?? 0 }))}
                />
              </Form.Item>
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
                      value={result.V_max_ms}
                      precision={3}
                      data-testid="vessel-v-max"
                    />
                  </Col>
                  <Col span={8}>
                    <Statistic
                      title="D_min (m)"
                      value={result.D_min_m}
                      precision={3}
                      data-testid="vessel-d-min"
                    />
                  </Col>
                  <Col span={8}>
                    <Statistic
                      title="持液量 (m³)"
                      value={result.liquid_volume_m3}
                      precision={2}
                    />
                  </Col>
                </Row>

                <Descriptions size="small" column={2}>
                  <Descriptions.Item label="容器类型">
                    {result.vessel_type}
                  </Descriptions.Item>
                  <Descriptions.Item label="K 因子 (m/s)">
                    {result.K_factor_ms.toFixed(3)}
                  </Descriptions.Item>
                  <Descriptions.Item label="停留时间 (min)">
                    {result.residence_time_min.toFixed(2)}
                  </Descriptions.Item>
                  <Descriptions.Item label="check">
                    {result.check_result === 'PASS' ? (
                      <Tag color="green">PASS</Tag>
                    ) : result.check_result === 'WARNING' ? (
                      <Tag color="orange" data-testid="vessel-warning">
                        WARNING
                      </Tag>
                    ) : (
                      <Tag color="red">FAIL</Tag>
                    )}
                  </Descriptions.Item>
                  <Descriptions.Item label="置信度">
                    <Tag
                      color={
                        result.confidence === 'HIGH'
                          ? 'green'
                          : result.confidence === 'MEDIUM'
                            ? 'blue'
                            : 'default'
                      }
                    >
                      {result.confidence}
                    </Tag>
                  </Descriptions.Item>
                </Descriptions>

                {result.orientation_warning && (
                  <Alert
                    type="warning"
                    message={result.orientation_warning}
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

export default VesselComputePage;