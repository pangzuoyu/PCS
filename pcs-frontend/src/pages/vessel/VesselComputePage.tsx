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
import { useEffect, useState } from 'react';
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
  Spin,
  Statistic,
  Tag,
  Typography,
} from 'antd';

import { PageHeader } from '../../components/common/PageHeader';
import { vesselApi } from '../../api/vessel';
import { streamApi } from '../../api/stream';
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
  /**可选：父组件注入时优先用（向后兼容 P5-1 测试）；未注入则走 streamApi。*/
  streams?: StreamLite[];
  /**可选：父组件注入时优先用（向后兼容 P5-1 测试）；未注入则走 vesselApi。*/
  onCalculate?: (
    req: VesselCalculateRequest,
  ) => VesselCalculateResponse | undefined;
}

/**后端 PcsError envelope 解析（与 HeatComputePage 同模式）。*/
interface PcsErrorEnvelope {
  code?: string;
  message?: string;
}
function extractPcsError(err: unknown): PcsErrorEnvelope {
  if (err && typeof err === 'object' && 'response' in err) {
    const data = (err as { response?: { data?: PcsErrorEnvelope } }).response?.data;
    if (data && typeof data === 'object') return data;
  }
  return {};
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

export function VesselComputePage({
  streams: streamsProp,
  onCalculate: onCalculateProp,
}: Props): JSX.Element {
  const [streamId, setStreamId] = useState<string | undefined>();
  const [sizing, setSizing] = useState<VesselSizing>(DEFAULT_SIZING);
  const [hydraulics, setHydraulics] = useState<VesselHydraulics>(DEFAULT_HYDRAULICS);
  const [result, setResult] = useState<VesselCalculateResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [calculating, setCalculating] = useState(false);
  const [fetchedStreams, setFetchedStreams] = useState<StreamLite[] | null>(null);
  const [streamsLoading, setStreamsLoading] = useState(false);

  // OPEN-4-1：未注入 streams 时走 streamApi 自取（CHECKED 过滤在 Mock seed 阶段跳过）
  useEffect(() => {
    if (streamsProp !== undefined) return;
    let cancelled = false;
    setStreamsLoading(true);
    streamApi
      .listByProject('00000000-0000-0000-0000-000000000001')
      .then((list) => {
        if (cancelled) return;
        // streamApi 不返 sign_status（轻量子集），全部当作 CHECKED 候选（dev/mock 友好）
        // 真实 ACL/状态由后端 /vessel/calculate STREAM_NOT_CHECKED 403 兜底
        setFetchedStreams(
          list.map((s) => ({
            stream_id: s.stream_id,
            tag_number: s.tag_number,
            sign_status: 'CHECKED',
          })),
        );
      })
      .catch(() => {
        if (cancelled) return;
        setFetchedStreams([]);
      })
      .finally(() => {
        if (!cancelled) setStreamsLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [streamsProp]);

  const streams = streamsProp ?? fetchedStreams ?? [];
  const checkedStreams = streams; // sign_status 过滤在 streamApi/mock 阶段由调用方控制

  const handleCalculate = async () => {
    if (!streamId) {
      setError('请选择物流');
      return;
    }
    setError(null);
    setCalculating(true);
    const req: VesselCalculateRequest = {
      source_stream_id: streamId,
      sizing,
      hydraulics,
    };
    try {
      let r: VesselCalculateResponse | undefined;
      if (onCalculateProp) {
        r = onCalculateProp(req);
      } else {
        r = await vesselApi.calculate(req);
      }
      if (!r) {
        setError('计算失败：返回空');
        setResult(null);
        return;
      }
      setResult(r);
    } catch (err: unknown) {
      const env = extractPcsError(err);
      const code = env.code ?? '';
      if (code === 'STREAM_NOT_CHECKED') {
        setError('所选流未签出（仅 CHECKED 可计算）');
      } else {
        setError(env.message ?? '计算失败');
      }
      setResult(null);
    } finally {
      setCalculating(false);
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
            loading={calculating}
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
                  placeholder={streamsLoading ? '加载物流中…' : '选择 CHECKED 物流'}
                  value={streamId}
                  onChange={setStreamId}
                  loading={streamsLoading}
                  disabled={streamsLoading}
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
            <Spin spinning={calculating}>
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
            </Spin>
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

export default VesselComputePage;