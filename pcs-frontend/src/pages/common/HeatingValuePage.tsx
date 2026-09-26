/**
 * COMMON 气体热值计算页（P6-5 前端补课 / 3 计算页之一）。
 *
 * SPEC §7.8（物性组）+ §7.12（设备计算统一页面模式）+ OpenAPI：
 * - POST /api/v1/common/heating-value/calculate（C-06 / GPSA FIG. 23-2 + API 5B6）
 * - 输入：compositions [{cas, mol_frac}]（不要求和 1，service 归一化）+ excess_air_pct
 * - 输出：HHV/LHV 双单位 + 化学计量空气 + 烟气组成/MW + formula_ref 溯源
 *
 * 页面模式与 VesselComputePage 同源：PageHeader + 输入 Card + 结果 Card +
 * extractPcsError envelope 解析 + onCalculate 注入（测试用）。
 */
import { useState } from 'react';
import {
  Button,
  Card,
  Col,
  Form,
  InputNumber,
  Row,
  Select,
  Space,
  Statistic,
  Table,
  Tag,
  Typography,
} from 'antd';
import { MinusCircleOutlined, PlusOutlined } from '@ant-design/icons';

import { PageHeader } from '../../components/common/PageHeader';
import { commonCalcApi } from '../../api/common';
import type {
  HeatingValueCalcRequest,
  HeatingValueCalcResponse,
} from '../../types/common';

/**后端 PcsError envelope 解析（与 VesselComputePage 同模式）。*/
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

/**安全数值化（NaN 兜底，与 VesselComputePage coerceNum 同模式）。*/
function coerceNum(v: unknown, fallback = 0): number {
  const n = typeof v === 'number' ? v : parseFloat(String(v ?? ''));
  return Number.isFinite(n) ? n : fallback;
}

interface Props {
  /**可选：父组件注入时优先用（测试注入）；未注入则走 commonCalcApi。*/
  onCalculate?: (
    req: HeatingValueCalcRequest,
  ) => HeatingValueCalcResponse | undefined;
}

/**典型天然气默认行（甲烷 90 + 乙烷 5 + 丙烷 3 + CO₂ 2；GPSA 对账基准工况）。*/
const DEFAULT_COMPOSITIONS = [
  { cas: '74-82-8', mol_frac: 0.9 },
  { cas: '74-84-0', mol_frac: 0.05 },
  { cas: '74-98-6', mol_frac: 0.03 },
  { cas: '124-38-9', mol_frac: 0.02 },
];

/**CAS 注册号速查（常用燃料气组分；输入框允许任意 CAS）。*/
const CAS_OPTIONS = [
  { value: '74-82-8', label: '74-82-8 甲烷 CH₄' },
  { value: '74-84-0', label: '74-84-0 乙烷 C₂H₆' },
  { value: '74-98-6', label: '74-98-6 丙烷 C₃H₈' },
  { value: '7727-37-9', label: '7727-37-9 氮气 N₂' },
  { value: '124-38-9', label: '124-38-9 二氧化碳 CO₂' },
  { value: '7783-06-4', label: '7783-06-4 硫化氢 H₂S' },
  { value: '1333-74-0', label: '1333-74-0 氢气 H₂' },
];

const FLUE_GAS_LABELS: Record<string, string> = {
  CO2: 'CO₂',
  H2O: 'H₂O',
  SO2: 'SO₂',
  N2: 'N₂',
  O2: 'O₂',
};

export function HeatingValuePage({ onCalculate: onCalculateProp }: Props): JSX.Element {
  const [compositions, setCompositions] = useState(DEFAULT_COMPOSITIONS);
  const [excessAirPct, setExcessAirPct] = useState(0);
  const [result, setResult] = useState<HeatingValueCalcResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [calculating, setCalculating] = useState(false);

  const setRow = (i: number, patch: Partial<{ cas: string; mol_frac: number }>) => {
    setCompositions((rows) => rows.map((r, idx) => (idx === i ? { ...r, ...patch } : r)));
  };

  const handleCalculate = async () => {
    const valid = compositions.filter(
      (r) => r.cas?.trim() && Number.isFinite(r.mol_frac) && (r.mol_frac ?? 0) > 0,
    );
    if (valid.length === 0) {
      setError('请至少填写 1 行有效组分（CAS + 摩尔分数 > 0）');
      setResult(null);
      return;
    }
    setError(null);
    setCalculating(true);
    const req: HeatingValueCalcRequest = {
      compositions: valid.map((r) => ({ cas: r.cas.trim(), mol_frac: r.mol_frac })),
      excess_air_pct: excessAirPct,
    };
    try {
      const r = onCalculateProp
        ? onCalculateProp(req)
        : await commonCalcApi.calculateHeatingValue(req);
      if (!r) {
        setError('计算失败：返回空');
        setResult(null);
        return;
      }
      setResult(r);
    } catch (err: unknown) {
      const env = extractPcsError(err);
      setError(env.message ?? '计算失败');
      setResult(null);
    } finally {
      setCalculating(false);
    }
  };

  const flueRows = result
    ? Object.entries(result.flue_gas_composition ?? {}).map(([k, v]) => ({
        key: k,
        species: FLUE_GAS_LABELS[k] ?? k,
        fraction: coerceNum(v),
      }))
    : [];

  return (
    <div data-testid="heating-value-page">
      <PageHeader
        title="COMMON 气体热值"
        actions={
          <Button
            type="primary"
            data-testid="heating-value-calculate"
            onClick={handleCalculate}
            loading={calculating}
          >
            计算
          </Button>
        }
      />

      <Row gutter={16}>
        <Col span={10}>
          <Card title="输入条件（C-06 / GPSA FIG. 23-2 + API 5B6）" size="small">
            <Form layout="vertical">
              {compositions.map((row, i) => (
                <Space key={i} style={{ display: 'flex', marginBottom: 4 }} align="baseline">
                  <Form.Item label={i === 0 ? '组分 CAS' : ''} required style={{ marginBottom: 4 }}>
                    <Select
                      data-testid={`heating-value-cas-${i}`}
                      showSearch
                      value={row.cas}
                      onChange={(v) => setRow(i, { cas: v })}
                      options={CAS_OPTIONS}
                      style={{ width: 220 }}
                      placeholder="CAS 注册号"
                    />
                  </Form.Item>
                  <Form.Item label={i === 0 ? '摩尔分数' : ''} required style={{ marginBottom: 4 }}>
                    <InputNumber
                      data-testid={`heating-value-frac-${i}`}
                      value={row.mol_frac}
                      min={0}
                      step={0.01}
                      style={{ width: 110 }}
                      onChange={(v) => setRow(i, { mol_frac: v ?? 0 })}
                    />
                  </Form.Item>
                  <MinusCircleOutlined
                    data-testid={`heating-value-remove-${i}`}
                    onClick={() =>
                      setCompositions((rows) => rows.filter((_, idx) => idx !== i))
                    }
                  />
                </Space>
              ))}
              <Button
                type="dashed"
                data-testid="heating-value-add"
                onClick={() => setCompositions((rows) => [...rows, { cas: '', mol_frac: 0 }])}
                icon={<PlusOutlined />}
                style={{ width: '100%' }}
              >
                添加组分
              </Button>
              <Form.Item
                label="过量空气百分比（0 = 化学计量）"
                style={{ marginTop: 12, marginBottom: 4 }}
              >
                <InputNumber
                  data-testid="heating-value-excess-air"
                  value={excessAirPct}
                  min={0}
                  max={1000}
                  step={10}
                  style={{ width: '100%' }}
                  onChange={(v) => setExcessAirPct(v ?? 0)}
                />
              </Form.Item>
              <Typography.Text type="secondary">
                摩尔分数不要求和为 1（service 层自动归一化）。
              </Typography.Text>
            </Form>
          </Card>
        </Col>

        <Col span={14}>
          <Card title="结果" size="small" data-testid="heating-value-result-card">
            {error && (
              <Typography.Text type="danger" data-testid="heating-value-error">
                {error}
              </Typography.Text>
            )}
            {result ? (
              <>
                <Row gutter={16}>
                  <Col span={6}>
                    <Statistic
                      title="进料 MW（kg/kmol）"
                      value={coerceNum(result.feed_mw_kg_per_kmol)}
                      precision={2}
                    />
                  </Col>
                  <Col span={6}>
                    <Statistic
                      title="HHV（MJ/sm³）"
                      value={coerceNum(result.hhv_mj_per_sm3)}
                      precision={3}
                    />
                  </Col>
                  <Col span={6}>
                    <Statistic
                      title="HHV（BTU/SCF）"
                      value={coerceNum(result.hhv_btu_per_scf)}
                      precision={1}
                    />
                  </Col>
                  <Col span={6}>
                    <Statistic
                      title="LHV（MJ/sm³）"
                      value={coerceNum(result.lhv_mj_per_sm3)}
                      precision={3}
                    />
                  </Col>
                </Row>
                <Row gutter={16} style={{ marginTop: 16 }}>
                  <Col span={6}>
                    <Statistic
                      title="LHV（BTU/SCF）"
                      value={coerceNum(result.lhv_btu_per_scf)}
                      precision={1}
                    />
                  </Col>
                  <Col span={6}>
                    <Statistic
                      title="化学计量空气（sm³/sm³）"
                      value={coerceNum(result.stoichiometric_air_sm3_per_sm3)}
                      precision={3}
                    />
                  </Col>
                  <Col span={6}>
                    <Statistic
                      title="烟气量（sm³/sm³）"
                      value={coerceNum(result.flue_gas_sm3_per_sm3)}
                      precision={3}
                    />
                  </Col>
                  <Col span={6}>
                    <Statistic
                      title="烟气 MW（kg/kmol）"
                      value={coerceNum(result.flue_gas_mw_kg_per_kmol)}
                      precision={2}
                    />
                  </Col>
                </Row>
                <Typography.Title level={5} style={{ marginTop: 16 }}>
                  烟气组成（体积分数）
                </Typography.Title>
                <Table
                  size="small"
                  pagination={false}
                  dataSource={flueRows}
                  columns={[
                    { title: '组分', dataIndex: 'species', key: 'species' },
                    {
                      title: '体积分数',
                      dataIndex: 'fraction',
                      key: 'fraction',
                      render: (v: number) => v.toFixed(4),
                    },
                  ]}
                />
                <div style={{ marginTop: 8 }} data-testid="heating-value-formula-ref">
                  {Object.entries(result.formula_ref ?? {}).map(([cas, src]) => (
                    <Tag key={cas}>
                      {cas}: {src}
                    </Tag>
                  ))}
                </div>
              </>
            ) : (
              !error && <Typography.Text type="secondary">填写组分后点击「计算」。</Typography.Text>
            )}
          </Card>
        </Col>
      </Row>
    </div>
  );
}

export default HeatingValuePage;
