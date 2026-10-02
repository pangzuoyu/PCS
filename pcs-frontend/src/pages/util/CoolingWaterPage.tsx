/**
 * CoolingWaterPage — P7-6B 冷却水子表 UI（P7 Sprint 2 R1 §7.2）。
 *
 * 按后端 OpenAPI（commit 260f357 BLOCKER-3 集成后）：
 * - 复用 utility_heat_exchange.medium_type 9 类 (per Do-Not-Repeat: 不入新表)
 * - 9 类水: FRESH_WATER / CIRCULATING_WATER / SOFTENED_WATER / DEMINERALIZED_WATER /
 *   LP_DEAERATED_WATER / HP_DEAERATED_WATER / TURBINE_CONDENSATE /
 *   120C_CONDENSATE_TREATED / 120C_CONDENSATE_REUSABLE
 * - CRUD: 列表 (列表 + 9 类聚合) / 新建 (设备位号 + 水类 + 小时 + 操作)
 * - 聚合显示: 按 9 类 water_type 累加年消耗 + 折标油 (toe) + 折标煤 (kg)
 *
 * 页面模式与 SaturationWaterContentPage 同源：PageHeader + 输入 Card + 列表 Card +
 * 9 类汇总 Card + extractPcsError envelope 解析。
 */
import { useEffect, useMemo, useState } from 'react';
import type { JSX } from 'react';
import {
  Alert,
  Button,
  Card,
  Col,
  Form,
  Input,
  InputNumber,
  Row,
  Select,
  Space,
  Statistic,
  Table,
  Tag,
  Typography,
} from 'antd';
import type { ColumnsType } from 'antd/es/table';

import { PageHeader } from '../../components/common/PageHeader';
import { utilApi, WATER_TYPE_OPTIONS } from '../../api/util';
import type { components } from '../../types/api';
import { PROJECT_ID } from '../../constants/env';

type UtilHeatExchangeCreateRequest = components['schemas']['UtilHeatExchangeCreateRequest'];
type UtilHeatExchangeResponse = components['schemas']['UtilHeatExchangeResponse'] & {
  medium_type?: string | null;
  pressure_level?: string | null;
};

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

interface Props {
  workspace_id?: string;
  project_id?: string;
}

export function CoolingWaterPage({
  workspace_id,
  project_id,
}: Props): JSX.Element {
  const projId = project_id || PROJECT_ID;
  // P7-6B 冷却水子表通过 PROJECT_ID 同源占位 (与 HeatComputePage 同模式);
  // workspace_id 由 meta/projects 取真实值; 当前 batch 简化用 project_id 复用.
  const wsId = workspace_id || projId;
  const [form] = Form.useForm();
  const [data, setData] = useState<UtilHeatExchangeResponse[]>([]);
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [infoMsg, setInfoMsg] = useState<string | null>(null);

  const load = async (): Promise<void> => {
    setLoading(true);
    setErrorMsg(null);
    try {
      const rows = await utilApi.listHeatExchange({
        project_id: projId,
        workspace_id: wsId,
      });
      setData(rows);
    } catch (err: unknown) {
      setErrorMsg(
        `${extractPcsError(err).code ?? 'HTTP_500'}: ${
          extractPcsError(err).message ?? '加载冷却水记录失败'
        }`,
      );
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projId, wsId]);

  // P7-6B 9 类水分类聚合 (复用 R1 §7.2 medium_type 设计; 排除 STEAM 共用表)
  const waterRows = useMemo(
    () => data.filter((r) => r.medium_type && r.medium_type !== 'STEAM'),
    [data],
  );
  const summaryByWaterType = useMemo(() => {
    const map: Record<string, { count: number; annual_t: number; toe_kg: number }> = {};
    for (const r of waterRows) {
      const water_type = r.medium_type as string;
      const annual_t = coerceNum(r.annual_consumption_t);
      const opt = WATER_TYPE_OPTIONS.find((o) => o.value === water_type);
      const toe_factor = opt?.toe_factor ?? 0;
      if (!map[water_type]) {
        map[water_type] = { count: 0, annual_t: 0, toe_kg: 0 };
      }
      map[water_type].count += 1;
      map[water_type].annual_t += annual_t;
      map[water_type].toe_kg += annual_t * toe_factor;
    }
    return map;
  }, [waterRows]);

  const totals = useMemo(() => {
    let annual_t = 0;
    let toe_kg = 0;
    for (const v of Object.values(summaryByWaterType)) {
      annual_t += v.annual_t;
      toe_kg += v.toe_kg;
    }
    return { annual_t, toe_t: toe_kg / 1000, coal_kg: toe_kg / 0.7 };
  }, [summaryByWaterType]);

  const handleCreate = async (
    values: Record<string, unknown>,
  ): Promise<void> => {
    setErrorMsg(null);
    setInfoMsg(null);
    const water_type = String(values.water_type ?? '');
    const equipment_tag = String(values.equipment_tag ?? '').trim();
    const consumption_t_h = coerceNum(values.consumption_t_h);
    const operating_hours = coerceNum(values.operating_hours_per_year, 8000);
    if (!water_type) {
      setErrorMsg('请选择水类');
      return;
    }
    if (!equipment_tag) {
      setErrorMsg('请输入设备位号');
      return;
    }
    if (consumption_t_h <= 0) {
      setErrorMsg('小时消耗必须 > 0');
      return;
    }
    const body: UtilHeatExchangeCreateRequest = {
      project_id: projId,
      workspace_id: wsId,
      equipment_tag,
      steam_pressure_mpa_gauge: 0,
      steam_quality_pct: 0,
      return_condensate_pct: 0,
      temperature_class: 'LP',
      medium_type: water_type,
      pressure_level: null,
      steam_consumption_t_h: consumption_t_h,
      operating_hours_per_year: operating_hours,
      annual_consumption_t: consumption_t_h * operating_hours,
      source: 'MANUAL',
    };
    try {
      const created = await utilApi.createHeatExchange(body);
      setInfoMsg(`已创建 ${created.equipment_tag} (${water_type})`);
      form.resetFields();
      await load();
    } catch (err: unknown) {
      setErrorMsg(
        `${extractPcsError(err).code ?? 'HTTP_500'}: ${
          extractPcsError(err).message ?? '创建失败'
        }`,
      );
    }
  };

  const columns: ColumnsType<UtilHeatExchangeResponse> = [
    {
      title: '设备位号',
      dataIndex: 'equipment_tag',
      width: 160,
      render: (v: string) => (
        <span style={{ fontFamily: 'var(--font-mono, monospace)' }}>{v}</span>
      ),
    },
    {
      title: '水类 (R1 §7.2)',
      dataIndex: 'medium_type',
      width: 200,
      render: (v: string | null) => {
        if (!v) return <Tag color="default">未分类</Tag>;
        const opt = WATER_TYPE_OPTIONS.find((o) => o.value === v);
        return <Tag color="cyan">{opt?.label ?? v}</Tag>;
      },
    },
    {
      title: '小时消耗 (t/h)',
      dataIndex: 'steam_consumption_t_h',
      width: 140,
      align: 'right',
      render: (v: unknown) => coerceNum(v).toFixed(3),
    },
    {
      title: '年操作 (h/yr)',
      dataIndex: 'operating_hours_per_year',
      width: 130,
      align: 'right',
      render: (v: unknown) => coerceNum(v).toFixed(0),
    },
    {
      title: '年消耗 (t/yr)',
      dataIndex: 'annual_consumption_t',
      width: 140,
      align: 'right',
      render: (v: unknown) => coerceNum(v).toFixed(3),
    },
    {
      title: '折标油 (t/yr)',
      key: 'render',
      width: 130,
      align: 'right',
      render: (_: unknown, row: UtilHeatExchangeResponse) => {
        const opt = WATER_TYPE_OPTIONS.find((o) => o.value === row.medium_type);
        const toe = (opt?.toe_factor ?? 0) * coerceNum(row.annual_consumption_t);
        return (toe / 1000).toFixed(4);
      },
    },
  ];

  return (
    <div>
      <PageHeader
        title="冷却水子表（P7-6B / R1 §7.2 9 类水）"
        actions={
          <Button onClick={load} loading={loading}>
            刷新列表
          </Button>
        }
      />

      <Alert
        type="info"
        showIcon
        message="复用 utility_heat_exchange.medium_type 9 类水设计；不新建表。R1 §7.2 折标系数来自 GB 30251-2024 附录 A 工艺室 2026-10-08 签齐。"
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
      {infoMsg && (
        <Alert
          type="success"
          showIcon
          message={infoMsg}
          style={{ marginBottom: 16 }}
          closable
          onClose={() => setInfoMsg(null)}
        />
      )}

      <Row gutter={16}>
        <Col span={6}>
          <Card>
            <Statistic
              title="水类覆盖"
              value={Object.keys(summaryByWaterType).length}
              suffix="类 / 9"
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic
              title="年总消耗"
              value={totals.annual_t}
              precision={3}
              suffix="t"
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic
              title="年折标油"
              value={totals.toe_t}
              precision={4}
              suffix="toe"
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic
              title="年折标煤"
              value={totals.coal_kg}
              precision={3}
              suffix="kg"
            />
          </Card>
        </Col>
      </Row>

      <Card title="新增冷却水记录" style={{ marginTop: 16 }}>
        <Form
          layout="inline"
          form={form}
          onFinish={(v) => {
            void handleCreate(v);
          }}
          initialValues={{ operating_hours_per_year: 8000 }}
        >
          <Form.Item label="设备位号" rules={[{ required: true }]} name="equipment_tag">
            <Input placeholder="CW-001" />
          </Form.Item>
          <Form.Item label="水类" name="water_type" rules={[{ required: true }]}>
            <Select
              placeholder="选择 R1 §7.2 水类"
              options={WATER_TYPE_OPTIONS}
              style={{ width: 220 }}
            />
          </Form.Item>
          <Form.Item label="小时消耗 (t/h)" name="consumption_t_h">
            <InputNumber min={0} step={0.1} style={{ width: 140 }} />
          </Form.Item>
          <Form.Item label="年操作 (h)" name="operating_hours_per_year">
            <InputNumber min={0} step={100} style={{ width: 120 }} />
          </Form.Item>
          <Form.Item>
            <Space>
              <Button type="primary" htmlType="submit">
                新增
              </Button>
            </Space>
          </Form.Item>
        </Form>
      </Card>

      <Card title="9 类水分类聚合" style={{ marginTop: 16 }}>
        <Table<UtilHeatExchangeResponse>
          rowKey="id"
          dataSource={waterRows}
          columns={columns}
          loading={loading}
          size="small"
          pagination={{ pageSize: 20 }}
          summary={(rows) => {
            const list = rows as UtilHeatExchangeResponse[];
            const total = list.reduce(
              (s, r) => s + coerceNum(r.annual_consumption_t),
              0,
            );
            return (
              <Table.Summary fixed>
                <Table.Summary.Row>
                  <Table.Summary.Cell index={0} colSpan={4}>
                    <Typography.Text strong>合计</Typography.Text>
                  </Table.Summary.Cell>
                  <Table.Summary.Cell index={1} align="right">
                    <Typography.Text strong>{total.toFixed(3)}</Typography.Text>
                  </Table.Summary.Cell>
                  <Table.Summary.Cell index={2} />
                </Table.Summary.Row>
              </Table.Summary>
            );
          }}
        />
      </Card>
    </div>
  );
}

export default CoolingWaterPage;