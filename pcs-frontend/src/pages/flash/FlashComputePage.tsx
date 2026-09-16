/**
 * FlashComputePage — FLASH 计算界面（P45-3-4 / Task 31）。
 *
 * SPEC §7.11.1：
 * - 物流选择（仅 CHECKED 状态可计算）
 * - 热力学方法（PR / SRK / NRTL / IAPWS_IF97）
 * - 计算类型（PT / PH / PS / BUBBLE_POINT / DEW_POINT）
 * - 条件输入：T/P 或 H/S
 * - 计算按钮触发 → 结果卡片（汽化分率 + 双组成 + 焓熵 + K 值）
 * - 不收敛 → 红色警告 + 建议切换方法
 *
 * Props：
 *   streams: { stream_id: string; tag_number: string; sign_status: Stream['sign_status'] }[]
 *   onCalculate?: (input: FlashInput) => FlashResult | undefined
 *
 * V1：默认 in-memory 计算函数 mock（PR 简单分率恒等 / 其他留接口）。
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
  Radio,
  Row,
  Select,
  Space,
  Statistic,
  Table,
  Tag,
  Typography,
} from 'antd';

import { PageHeader } from '../../components/common/PageHeader';
import type {
  FlashCalcType,
  FlashInput,
  FlashResult,
  ThermoMethod,
} from '../../types/flash';

interface StreamLite {
  stream_id: string;
  tag_number: string;
  sign_status: string;
}

interface Props {
  streams: StreamLite[];
  onCalculate?: (input: FlashInput) => FlashResult | undefined;
}

const THERMO_OPTIONS: { value: ThermoMethod; label: string }[] = [
  { value: 'PR', label: 'PR (Peng-Robinson)' },
  { value: 'SRK', label: 'SRK (Soave-Redlich-Kwong)' },
  { value: 'NRTL', label: 'NRTL (活度系数)' },
  { value: 'IAPWS_IF97', label: 'IAPWS-IF97 (水/蒸汽)' },
];

const CALC_OPTIONS: { value: FlashCalcType; label: string }[] = [
  { value: 'PT', label: 'PT 闪蒸' },
  { value: 'PH', label: 'PH 闪蒸' },
  { value: 'PS', label: 'PS 闪蒸' },
  { value: 'BUBBLE_POINT', label: '泡点' },
  { value: 'DEW_POINT', label: '露点' },
];

function defaultMockResult(input: FlashInput): FlashResult {
  // V1 mock：根据输入条件估算一个简单结果
  const vapor_fraction = input.calc_type === 'BUBBLE_POINT' ? 0 :
    input.calc_type === 'DEW_POINT' ? 1 :
    0.5;
  return {
    vapor_fraction,
    liquid_composition: { C1: 0.4, C2: 0.3, C3: 0.3 },
    vapor_composition: { C1: 0.6, C2: 0.3, C3: 0.1 },
    h_kj_kg: 1500,
    s_kj_kg_k: 4.5,
    k_values: { C1: 2.5, C2: 1.0, C3: 0.3 },
    converged: true,
  };
}

export function FlashComputePage({ streams, onCalculate }: Props): JSX.Element {
  const [input, setInput] = useState<Partial<FlashInput>>({
    thermo_method: 'PR',
    calc_type: 'PT',
  });
  const [result, setResult] = useState<FlashResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const checkedStreams = streams.filter((s) => s.sign_status === 'CHECKED');

  const handleCalculate = () => {
    if (!input.stream_id) {
      setError('请选择物流');
      return;
    }
    setError(null);
    const finalInput = input as FlashInput;
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

  const compColumns = [
    {
      title: '组分',
      dataIndex: 'component',
      width: 120,
    },
    {
      title: '液相',
      dataIndex: 'liquid',
      render: (v: number) => v.toFixed(4),
    },
    {
      title: '汽相',
      dataIndex: 'vapor',
      render: (v: number) => v.toFixed(4),
    },
    {
      title: 'K 值',
      dataIndex: 'k',
      render: (v: number) => v.toFixed(3),
    },
  ];

  const compRows = result
    ? Object.keys(result.liquid_composition).map((k) => ({
        key: k,
        component: k,
        liquid: result.liquid_composition[k],
        vapor: result.vapor_composition[k] ?? 0,
        k: result.k_values[k] ?? 0,
      }))
    : [];

  return (
    <div data-testid="flash-compute-page">
      <PageHeader
        title="FLASH 计算"
        module="FLASH"
        actions={
          <Button
            type="primary"
            data-testid="flash-calculate"
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
                  data-testid="flash-stream-select"
                  placeholder="选择 CHECKED 物流"
                  value={input.stream_id}
                  onChange={(v) => setInput((s) => ({ ...s, stream_id: v }))}
                  options={checkedStreams.map((s) => ({
                    value: s.stream_id,
                    label: s.tag_number,
                  }))}
                />
              </Form.Item>

              <Form.Item label="热力学方法">
                <Radio.Group
                  data-testid="flash-thermo"
                  value={input.thermo_method}
                  onChange={(e) =>
                    setInput((s) => ({ ...s, thermo_method: e.target.value as ThermoMethod }))
                  }
                >
                  <Space direction="vertical">
                    {THERMO_OPTIONS.map((o) => (
                      <Radio key={o.value} value={o.value}>
                        {o.label}
                      </Radio>
                    ))}
                  </Space>
                </Radio.Group>
              </Form.Item>

              <Form.Item label="计算类型">
                <Radio.Group
                  data-testid="flash-calc-type"
                  value={input.calc_type}
                  onChange={(e) =>
                    setInput((s) => ({ ...s, calc_type: e.target.value as FlashCalcType }))
                  }
                >
                  <Space direction="vertical">
                    {CALC_OPTIONS.map((o) => (
                      <Radio key={o.value} value={o.value}>
                        {o.label}
                      </Radio>
                    ))}
                  </Space>
                </Radio.Group>
              </Form.Item>

              {(input.calc_type === 'PT' || input.calc_type === 'PH' || input.calc_type === 'PS') && (
                <Space>
                  <Form.Item label="T (K)">
                    <InputNumber
                      data-testid="flash-t-k"
                      value={input.t_k}
                      onChange={(v) => setInput((s) => ({ ...s, t_k: v ?? undefined }))}
                    />
                  </Form.Item>
                  <Form.Item label="P (MPa)">
                    <InputNumber
                      data-testid="flash-p-mpa"
                      value={input.p_mpa}
                      onChange={(v) => setInput((s) => ({ ...s, p_mpa: v ?? undefined }))}
                    />
                  </Form.Item>
                </Space>
              )}
              {input.calc_type === 'PH' && (
                <Form.Item label="H (kJ/kg)">
                  <InputNumber
                    data-testid="flash-h"
                    value={input.h_kj_kg}
                    onChange={(v) => setInput((s) => ({ ...s, h_kj_kg: v ?? undefined }))}
                  />
                </Form.Item>
              )}
              {input.calc_type === 'PS' && (
                <Form.Item label="S (kJ/(kg·K))">
                  <InputNumber
                    data-testid="flash-s"
                    value={input.s_kj_kg_k}
                    onChange={(v) => setInput((s) => ({ ...s, s_kj_kg_k: v ?? undefined }))}
                  />
                </Form.Item>
              )}
            </Form>
          </Card>
        </Col>

        <Col span={14}>
          <Card title="结果" size="small" data-testid="flash-result-card">
            {error && (
              <Alert
                type="error"
                message={error}
                data-testid="flash-error"
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
                      title="汽化分率"
                      value={result.vapor_fraction}
                      precision={4}
                      data-testid="flash-vapor-fraction"
                    />
                  </Col>
                  <Col span={8}>
                    <Statistic
                      title="H (kJ/kg)"
                      value={result.h_kj_kg}
                      precision={2}
                    />
                  </Col>
                  <Col span={8}>
                    <Statistic
                      title="S (kJ/(kg·K))"
                      value={result.s_kj_kg_k}
                      precision={3}
                    />
                  </Col>
                </Row>

                <Descriptions size="small" column={1}>
                  <Descriptions.Item label="收敛">
                    {result.converged ? (
                      <Tag color="green">已收敛</Tag>
                    ) : (
                      <Tag color="red" data-testid="flash-not-converged">
                        未收敛 — 建议切换热力学方法（如改 NRTL / IAPWS-IF97）
                      </Tag>
                    )}
                  </Descriptions.Item>
                </Descriptions>

                <Table
                  size="small"
                  rowKey="key"
                  columns={compColumns}
                  dataSource={compRows}
                  pagination={false}
                  data-testid="flash-composition-table"
                />
              </Space>
            )}
          </Card>
        </Col>
      </Row>
    </div>
  );
}

export default FlashComputePage;