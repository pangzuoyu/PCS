/**
 * EnergySummaryAggregatePage — 综合能耗聚合 UI（P7 Sprint 2 T5 / R1 §7）。
 *
 * 按后端 OpenAPI（commit 260f357 BLOCKER-3 集成后）：
 * - POST /api/v1/util/energy-summary/aggregate
 *   → UtilEnergySummaryResponse 201
 * - 6 类能源 annual 消耗 + total_toe + total_standard_coal_kg + r1_classification JSON
 *
 * 设计要点：
 * - 9 项 Statistic Card：6 类能源年消耗 + 总能耗 MJ + 折标油 + 折标煤
 * - R1 分类聚合 JSON：3 类 dict (steam_by_pressure_level + fuel_gas_by_source + water_by_type)
 * - 容差 status Tag：OK / EXCEEDED / NA (per P7-OPEN-009 §6 ≤2%)
 * - 电当量值/等价值 select：EQUIVALENT (默认 0.086) / EQUIVALENT_VALUE (0.21)
 *
 * 页面模式与 CoolingWaterPage 同源：PageHeader + 输入 Card + 结果 Card +
 * extractPcsError envelope 解析。
 */
import { useState } from 'react';
import type { JSX } from 'react';
import {
  Alert,
  Button,
  Card,
  Col,
  Form,
  InputNumber,
  Row,
  Select,
  Statistic,
  Table,
  Tag,
  Typography,
} from 'antd';
import type { ColumnsType } from 'antd/es/table';

import { PageHeader } from '../../components/common/PageHeader';
import { utilApi } from '../../api/util';
import type { components } from '../../types/api';
import { PROJECT_ID } from '../../constants/env';

type UtilEnergySummaryAggregateRequest =
  components['schemas']['UtilEnergySummaryAggregateRequest'];
type UtilEnergySummaryResponse =
  components['schemas']['UtilEnergySummaryResponse'];

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

function coerceNum(v: unknown, fallback = 0): number {
  const n = typeof v === 'number' ? v : Number(v);
  return Number.isFinite(n) ? n : fallback;
}

const VALUE_TYPE_OPTIONS = [
  {
    value: 'EQUIVALENT',
    label: '当量值 (0.086 kg标油/kWh - 其他产品用)',
  },
  {
    value: 'EQUIVALENT_VALUE',
    label: '等价值 (0.21 kg标油/kWh - 炼油/乙烯用)',
  },
];

const TOLERANCE_COLOR: Record<string, string> = {
  OK: 'green',
  EXCEEDED: 'red',
  NA: 'default',
};

interface R1ClassRow {
  key: string;
  value: string;
  amount: number;
  contribution_pct: number;
}

function flattenR1Classification(
  cls: Record<string, Record<string, number>> | null | undefined,
  totalAnnualT: number,
): R1ClassRow[] {
  if (!cls) return [];
  const rows: R1ClassRow[] = [];
  for (const [group, items] of Object.entries(cls)) {
    for (const [k, v] of Object.entries(items)) {
      rows.push({
        key: `${group}.${k}`,
        value: `${group}.${k}`,
        amount: coerceNum(v),
        contribution_pct:
          totalAnnualT > 0 ? (coerceNum(v) / totalAnnualT) * 100 : 0,
      });
    }
  }
  return rows.sort((a, b) => b.amount - a.amount);
}

interface Props {
  workspace_id?: string;
  project_id?: string;
}

export function EnergySummaryAggregatePage({
  workspace_id,
  project_id,
}: Props): JSX.Element {
  const projId = project_id || PROJECT_ID;
  const wsId = workspace_id || projId;
  const [form] = Form.useForm();
  const [result, setResult] = useState<UtilEnergySummaryResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const handleAggregate = async (
    values: Record<string, unknown>,
  ): Promise<void> => {
    setErrorMsg(null);
    setResult(null);
    const business_year = coerceNum(values.business_year, 2026);
    const electricity_value_type =
      String(values.electricity_value_type ?? 'EQUIVALENT');
    // F-P2-007 fix: 透传 source (CALCULATION / XLS_REFERENCE)
    // 默认 CALCULATION — 走 service 聚合; XLS_REFERENCE 走容差校验对照行
    const source = String(values.source ?? 'CALCULATION') as
      | 'CALCULATION'
      | 'XLS_REFERENCE';
    const body: UtilEnergySummaryAggregateRequest = {
      project_id: projId,
      workspace_id: wsId,
      business_year,
      source,
      electricity_value_type,
    };
    setLoading(true);
    try {
      const r = await utilApi.aggregateEnergySummary(body);
      setResult(r);
    } catch (err: unknown) {
      setErrorMsg(
        `${extractPcsError(err).code ?? 'HTTP_500'}: ${
          extractPcsError(err).message ?? '能耗聚合失败'
        }`,
      );
    } finally {
      setLoading(false);
    }
  };

  // R1 分类聚合 5+3+9 + 9 = 22 dict 行 (P7-6B water_by_type 待 P7-6B 冷却水子表落地)
  const r1Rows: R1ClassRow[] = flattenR1Classification(
    result?.r1_classification as Record<string, Record<string, number>> | undefined,
    coerceNum(result?.steam_t_yr) + coerceNum(result?.fuel_gas_nm3_yr) + coerceNum(result?.water_t_yr),
  );

  const r1Columns: ColumnsType<R1ClassRow> = [
    {
      title: '分类键',
      dataIndex: 'key',
      width: 320,
      render: (v: string) => (
        <span style={{ fontFamily: 'var(--font-mono, monospace)' }}>{v}</span>
      ),
    },
    {
      title: '数量 (t/Nm³/yr)',
      dataIndex: 'amount',
      width: 160,
      align: 'right',
      render: (v: number) => v.toFixed(3),
    },
    {
      title: '占合计 (t/Nm³ 累计) %',
      dataIndex: 'contribution_pct',
      width: 160,
      align: 'right',
      render: (v: number) => `${v.toFixed(2)}%`,
    },
  ];

  return (
    <div>
      <PageHeader
        title="综合能耗聚合（P7 Sprint 2 T5 / R1 §7）"
        actions={
          <Button onClick={() => setResult(null)} disabled={!result}>
            清空结果
          </Button>
        }
      />

      <Alert
        type="info"
        showIcon
        message="R1 §7 分类聚合 (3 类 dict): steam_by_pressure_level (9 档) + fuel_gas_by_source (3 类) + water_by_type (9 类, 待 P7-6B 冷却水子表落地). 总能耗 MJ / 折标油 / 折标煤 / 容差 ≤2% per P7-OPEN-009 §6."
        style={{ marginBottom: 16 }}
      />

      {errorMsg && (
        <Alert
          type="error"
          showIcon
          message={errorMsg}
          style={{ marginBottom: 16 }}
          closable
          onClose={() => setErrorMsg(null)}
        />
      )}

      <Card title="触发综合能耗聚合 (T5)" style={{ marginBottom: 16 }}>
        <Form
          layout="inline"
          form={form}
          onFinish={(v) => {
            void handleAggregate(v);
          }}
          initialValues={{
            business_year: 2026,
            electricity_value_type: 'EQUIVALENT',
            source: 'CALCULATION',
          }}
        >
          <Form.Item label="业务年度" name="business_year">
            <InputNumber min={2020} max={2100} style={{ width: 140 }} />
          </Form.Item>
          <Form.Item label="数据来源" name="source">
            <Select
              options={[
                { value: 'CALCULATION', label: 'CALCULATION (系统聚合)' },
                { value: 'XLS_REFERENCE', label: 'XLS_REFERENCE (XLS 对照)' },
              ]}
              style={{ width: 200 }}
            />
          </Form.Item>
          <Form.Item label="电当量值" name="electricity_value_type">
            <Select
              options={VALUE_TYPE_OPTIONS}
              style={{ width: 360 }}
            />
          </Form.Item>
          <Form.Item>
            <Button type="primary" htmlType="submit" loading={loading}>
              触发聚合
            </Button>
          </Form.Item>
        </Form>
      </Card>

      {result && (
        <>
          <Row gutter={16}>
            <Col span={6}>
              <Card>
                <Statistic
                  title="年用电量"
                  value={coerceNum(result.electricity_kwh_yr)}
                  precision={2}
                  suffix="kWh"
                />
              </Card>
            </Col>
            <Col span={6}>
              <Card>
                <Statistic
                  title="年燃料气"
                  value={coerceNum(result.fuel_gas_nm3_yr)}
                  precision={2}
                  suffix="Nm³"
                />
              </Card>
            </Col>
            <Col span={6}>
              <Card>
                <Statistic
                  title="年蒸汽消耗"
                  value={coerceNum(result.steam_t_yr)}
                  precision={3}
                  suffix="t"
                />
              </Card>
            </Col>
            <Col span={6}>
              <Card>
                <Statistic
                  title="年新鲜水"
                  value={coerceNum(result.water_t_yr)}
                  precision={3}
                  suffix="t"
                />
              </Card>
            </Col>
            <Col span={6}>
              <Card>
                <Statistic
                  title="年工艺气体"
                  value={coerceNum(result.gas_nm3_yr)}
                  precision={3}
                  suffix="Nm³"
                />
              </Card>
            </Col>
            <Col span={6}>
              <Card>
                <Statistic
                  title="年低温余热"
                  value={coerceNum(result.low_temp_heat_gj_yr)}
                  precision={3}
                  suffix="GJ"
                />
              </Card>
            </Col>
            <Col span={6}>
              <Card>
                <Statistic
                  title="年总能耗"
                  value={coerceNum(result.annual_total_energy) / 1000}
                  precision={3}
                  suffix="GJ"
                />
              </Card>
            </Col>
            <Col span={6}>
              <Card>
                <Statistic
                  title="折标油总量"
                  value={coerceNum(result.total_toe)}
                  precision={4}
                  suffix="toe"
                />
              </Card>
            </Col>
          </Row>

          <Row gutter={16} style={{ marginTop: 16 }}>
            <Col span={6}>
              <Card>
                <Statistic
                  title="折标煤总量"
                  value={coerceNum(result.total_standard_coal_kg)}
                  precision={3}
                  suffix="kg 标煤"
                />
              </Card>
            </Col>
            <Col span={6}>
              <Card>
                <Statistic
                  title="容差"
                  value={
                    result.tolerance_pct === null || result.tolerance_pct === undefined
                      ? 'N/A'
                      : `${(coerceNum(result.tolerance_pct) * 100).toFixed(2)}%`
                  }
                />
              </Card>
            </Col>
            <Col span={6}>
              <Card>
                <Tag color={TOLERANCE_COLOR[result.tolerance_status] ?? 'default'}>
                  {result.tolerance_status}
                </Tag>
                <Typography.Text type="secondary">
                  {' '}
                  (≤2% per P7-OPEN-009 §6)
                </Typography.Text>
              </Card>
            </Col>
            <Col span={6}>
              <Card>
                <Typography.Text type="secondary">电当量值: </Typography.Text>
                <Tag color="blue">
                  {result.electricity_value_type ?? 'EQUIVALENT'}
                </Tag>
              </Card>
            </Col>
          </Row>

          <Card title="R1 §7 分类聚合 (3 类 dict)" style={{ marginTop: 16 }}>
            {r1Rows.length === 0 ? (
              <Alert
                type="warning"
                showIcon
                message="R1 分类聚合为空 — 介质记录未填 pressure_level / medium_type / gas_source (P7-6B 冷却水待落地后填 water_by_type)"
              />
            ) : (
              <Table<R1ClassRow>
                rowKey="key"
                dataSource={r1Rows}
                columns={r1Columns}
                size="small"
                pagination={false}
              />
            )}
          </Card>
        </>
      )}
    </div>
  );
}

export default EnergySummaryAggregatePage;