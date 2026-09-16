/**
 * PumpComputePage — PUMP 计算界面（P45-3-7 / Task 34）。
 *
 * SPEC §7.11.4：
 * - 输入 4 块：吸入口 / 排出口 / 流量 / 效率
 * - 结果 5 卡：扬程 / NPSH / 功率 / 设计压力 / 控制阀 Kv
 * - 压降分段明细 Table
 * - 出口物流创建提示（V1 mock 占位）
 *
 * Props：
 *   streams: { stream_id: string; tag_number: string; sign_status: string }[]
 *   onCalculate?: (input: PumpInput) => PumpResult | undefined
 *   onCreateOutletStream?: (input: PumpInput, result: PumpResult) => void
 */
import { useState } from 'react';
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
  Typography,
} from 'antd';
import type { ColumnsType } from 'antd/es/table';

import { PageHeader } from '../../components/common/PageHeader';
import type { PumpDpSegment, PumpInput, PumpResult } from '../../types/pump';

interface StreamLite {
  stream_id: string;
  tag_number: string;
  sign_status: string;
}

interface Props {
  streams: StreamLite[];
  onCalculate?: (input: PumpInput) => PumpResult | undefined;
  onCreateOutletStream?: (input: PumpInput, result: PumpResult) => void;
}

const DEFAULT_INPUT: Partial<PumpInput> = {
  suction: { vessel_pressure_mpa: 0.1, liquid_level_m: 2.0, pipe_dn: 100, fittings_json: {} },
  discharge: { vessel_pressure_mpa: 1.0, static_head_m: 15.0, pipe_dn: 80, fittings_json: {} },
  flow: { normal: 100, min: 50, design: 120 },
  efficiency: { pump: 0.7, motor: 0.95 },
  control_valve_dp_kpa: 30,
};

function defaultMockResult(input: PumpInput): PumpResult {
  const head =
    (input.discharge.vessel_pressure_mpa - input.suction.vessel_pressure_mpa) * 100 +
    input.discharge.static_head_m;
  const dp_breakdown: PumpDpSegment[] = [
    { segment: '吸入管路', dp_kpa: 5 },
    { segment: '控制阀', dp_kpa: input.control_valve_dp_kpa },
    { segment: '排出管路', dp_kpa: 8 },
    { segment: '设备内件', dp_kpa: 3 },
  ];
  const sumDp = dp_breakdown.reduce((s, d) => s + d.dp_kpa, 0);
  return {
    head_m: Math.round(head * 10) / 10,
    npsh_m: 3.5,
    power_kw: Math.round(((input.flow.design * 9.81 * head) / (input.efficiency.pump * input.efficiency.motor)) / 100) / 10,
    design_pressure_mpa: input.discharge.vessel_pressure_mpa * 1.1,
    control_valve_kv: Math.round(input.flow.design / Math.sqrt(input.control_valve_dp_kpa) * 10) / 10,
    equivalent_length_m: sumDp * 1.2,
    dp_breakdown,
  };
}

export function PumpComputePage({ streams, onCalculate, onCreateOutletStream }: Props): JSX.Element {
  const [input, setInput] = useState<Partial<PumpInput>>({ ...DEFAULT_INPUT });
  const [result, setResult] = useState<PumpResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const checkedStreams = streams.filter((s) => s.sign_status === 'CHECKED');

  const handleCalculate = () => {
    if (!input.stream_id) {
      setError('请选择物流');
      return;
    }
    setError(null);
    const finalInput = input as PumpInput;
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

  const dpColumns: ColumnsType<PumpDpSegment> = [
    { title: '段', dataIndex: 'segment' },
    {
      title: '压降 (kPa)',
      dataIndex: 'dp_kpa',
      render: (v: number) => v.toFixed(2),
    },
  ];

  return (
    <div data-testid="pump-compute-page">
      <PageHeader
        title="PUMP 计算"
        module="PUMP"
        actions={
          <Space>
            <Button data-testid="pump-calculate" onClick={handleCalculate}>
              计算
            </Button>
            <Button
              type="primary"
              data-testid="pump-create-outlet"
              disabled={!result}
              onClick={() => result && onCreateOutletStream?.(input as PumpInput, result)}
            >
              创建出口物流
            </Button>
          </Space>
        }
      />

      <Row gutter={16}>
        <Col span={10}>
          <Card title="输入条件" size="small">
            <Tabs
              data-testid="pump-input-tabs"
              defaultActiveKey="suction"
              items={[
                {
                  key: 'suction',
                  label: <span data-testid="pump-tab-suction">吸入口</span>,
                  children: (
                    <Form layout="vertical">
                      <Form.Item label="物流" required>
                        <Select
                          data-testid="pump-stream-select"
                          placeholder="选择 CHECKED 物流"
                          value={input.stream_id}
                          onChange={(v) => setInput((s) => ({ ...s, stream_id: v }))}
                          options={checkedStreams.map((s) => ({
                            value: s.stream_id,
                            label: s.tag_number,
                          }))}
                        />
                      </Form.Item>
                      <Form.Item label="容器压力 (MPa)">
                        <InputNumber
                          data-testid="pump-suction-p"
                          value={input.suction?.vessel_pressure_mpa}
                          step={0.05}
                          onChange={(v) =>
                            setInput((s) => ({
                              ...s,
                              suction: { ...s.suction!, vessel_pressure_mpa: v ?? 0 },
                            }))
                          }
                        />
                      </Form.Item>
                      <Form.Item label="液位 (m)">
                        <InputNumber
                          data-testid="pump-suction-level"
                          value={input.suction?.liquid_level_m}
                          step={0.1}
                          onChange={(v) =>
                            setInput((s) => ({
                              ...s,
                              suction: { ...s.suction!, liquid_level_m: v ?? 0 },
                            }))
                          }
                        />
                      </Form.Item>
                      <Form.Item label="管径 DN">
                        <InputNumber
                          data-testid="pump-suction-dn"
                          value={input.suction?.pipe_dn}
                          onChange={(v) =>
                            setInput((s) => ({
                              ...s,
                              suction: { ...s.suction!, pipe_dn: v ?? 0 },
                            }))
                          }
                        />
                      </Form.Item>
                    </Form>
                  ),
                },
                {
                  key: 'discharge',
                  label: <span data-testid="pump-tab-discharge">排出口</span>,
                  children: (
                    <Form layout="vertical">
                      <Form.Item label="容器压力 (MPa)">
                        <InputNumber
                          data-testid="pump-discharge-p"
                          value={input.discharge?.vessel_pressure_mpa}
                          step={0.05}
                          onChange={(v) =>
                            setInput((s) => ({
                              ...s,
                              discharge: { ...s.discharge!, vessel_pressure_mpa: v ?? 0 },
                            }))
                          }
                        />
                      </Form.Item>
                      <Form.Item label="静扬程 (m)">
                        <InputNumber
                          data-testid="pump-discharge-head"
                          value={input.discharge?.static_head_m}
                          step={0.5}
                          onChange={(v) =>
                            setInput((s) => ({
                              ...s,
                              discharge: { ...s.discharge!, static_head_m: v ?? 0 },
                            }))
                          }
                        />
                      </Form.Item>
                      <Form.Item label="管径 DN">
                        <InputNumber
                          data-testid="pump-discharge-dn"
                          value={input.discharge?.pipe_dn}
                          onChange={(v) =>
                            setInput((s) => ({
                              ...s,
                              discharge: { ...s.discharge!, pipe_dn: v ?? 0 },
                            }))
                          }
                        />
                      </Form.Item>
                    </Form>
                  ),
                },
                {
                  key: 'flow',
                  label: <span data-testid="pump-tab-flow">流量 / 效率</span>,
                  children: (
                    <Form layout="vertical">
                      <Form.Item label="流量 normal (m³/h)">
                        <InputNumber
                          data-testid="pump-flow-normal"
                          value={input.flow?.normal}
                          onChange={(v) =>
                            setInput((s) => ({ ...s, flow: { ...s.flow!, normal: v ?? 0 } }))
                          }
                        />
                      </Form.Item>
                      <Form.Item label="流量 min (m³/h)">
                        <InputNumber
                          data-testid="pump-flow-min"
                          value={input.flow?.min}
                          onChange={(v) =>
                            setInput((s) => ({ ...s, flow: { ...s.flow!, min: v ?? 0 } }))
                          }
                        />
                      </Form.Item>
                      <Form.Item label="流量 design (m³/h)">
                        <InputNumber
                          data-testid="pump-flow-design"
                          value={input.flow?.design}
                          onChange={(v) =>
                            setInput((s) => ({ ...s, flow: { ...s.flow!, design: v ?? 0 } }))
                          }
                        />
                      </Form.Item>
                      <Form.Item label="泵效率">
                        <InputNumber
                          data-testid="pump-eff-pump"
                          value={input.efficiency?.pump}
                          min={0}
                          max={1}
                          step={0.05}
                          onChange={(v) =>
                            setInput((s) => ({ ...s, efficiency: { ...s.efficiency!, pump: v ?? 0 } }))
                          }
                        />
                      </Form.Item>
                      <Form.Item label="电机效率">
                        <InputNumber
                          data-testid="pump-eff-motor"
                          value={input.efficiency?.motor}
                          min={0}
                          max={1}
                          step={0.05}
                          onChange={(v) =>
                            setInput((s) => ({ ...s, efficiency: { ...s.efficiency!, motor: v ?? 0 } }))
                          }
                        />
                      </Form.Item>
                      <Form.Item label="控制阀压降 (kPa)">
                        <InputNumber
                          data-testid="pump-cv-dp"
                          value={input.control_valve_dp_kpa}
                          onChange={(v) => setInput((s) => ({ ...s, control_valve_dp_kpa: v ?? 0 }))}
                        />
                      </Form.Item>
                    </Form>
                  ),
                },
              ]}
            />
          </Card>
        </Col>

        <Col span={14}>
          <Card title="结果" size="small" data-testid="pump-result-card">
            {error && (
              <Alert type="error" message={error} data-testid="pump-error" style={{ marginBottom: 12 }} />
            )}
            {!result && !error && (
              <Typography.Text type="secondary">点击「计算」开始</Typography.Text>
            )}
            {result && (
              <Space direction="vertical" size={16} style={{ width: '100%' }}>
                <Row gutter={16}>
                  <Col span={8}>
                    <Statistic
                      title="扬程 (m)"
                      value={result.head_m}
                      precision={2}
                      data-testid="pump-result-head"
                    />
                  </Col>
                  <Col span={8}>
                    <Statistic
                      title="NPSH (m)"
                      value={result.npsh_m}
                      precision={2}
                      data-testid="pump-result-npsh"
                    />
                  </Col>
                  <Col span={8}>
                    <Statistic
                      title="功率 (kW)"
                      value={result.power_kw}
                      precision={2}
                      data-testid="pump-result-power"
                    />
                  </Col>
                </Row>

                <Descriptions size="small" column={2}>
                  <Descriptions.Item label="设计压力 (MPa)">
                    {result.design_pressure_mpa.toFixed(3)}
                  </Descriptions.Item>
                  <Descriptions.Item label="控制阀 Kv">
                    {result.control_valve_kv.toFixed(2)}
                  </Descriptions.Item>
                  <Descriptions.Item label="当量长度 (m)">
                    {result.equivalent_length_m.toFixed(2)}
                  </Descriptions.Item>
                </Descriptions>

                <Table<PumpDpSegment>
                  size="small"
                  rowKey="segment"
                  columns={dpColumns}
                  dataSource={result.dp_breakdown}
                  pagination={false}
                  data-testid="pump-dp-breakdown"
                />
              </Space>
            )}
          </Card>
        </Col>
      </Row>
    </div>
  );
}

export default PumpComputePage;