/**
 * StreamDetailPage — SIM 物流详情（P45-3-1 / Task 28）。
 *
 * SPEC §7.7.2：
 * - PageHeader（标题 = tag_number + 名称；状态徽章；版本 hash；操作）
 * - 基础信息 Descriptions（相态/温压/流量/更新人/时间）
 * - 组成 JSON 表格（组分 + 摩尔分率）
 * - 复用 SignatureMatrix（签署矩阵）
 *
 * Props：
 *   stream: Stream
 *   onBack?: () => void
 *   onSubmit?: () => void
 *   onObsolete?: () => void
 */
import {
  Button,
  Card,
  Col,
  Descriptions,
  Row,
  Space,
  Table,
  Tag,
  Typography,
} from 'antd';
import type { ColumnsType } from 'antd/es/table';

import { ModuleLayout } from '../../components/common/ModuleLayout';
import { PageHeader } from '../../components/common/PageHeader';
import { SignatureMatrix, type SignatureRecord, type SignatureStep } from '../../components/common/SignatureMatrix';
import { STREAM_PHASE_LABEL, STREAM_SUBPHASE_LABEL, type Stream } from '../../types/stream';

interface Props {
  stream: Stream;
  matrix?: SignatureStep[];
  signatures?: SignatureRecord[];
  onBack?: () => void;
  onSubmit?: () => void;
  onObsolete?: () => void;
}

const DEFAULT_MATRIX: SignatureStep[] = [
  { step_index: 1, role: '设计' },
  { step_index: 2, role: '校核' },
  { step_index: 3, role: '审核' },
];

const DEFAULT_SIGNATURES: SignatureRecord[] = [
  { step_index: 1, signer_name: '张三', signed_at: '2026-09-10' },
  { step_index: 2, signer_name: '李四', signed_at: '2026-09-12' },
  { step_index: 3, signer_name: '王五', signed_at: '2026-09-15' },
];

export function StreamDetailPage({
  stream,
  matrix = DEFAULT_MATRIX,
  signatures = DEFAULT_SIGNATURES,
  onBack,
  onSubmit,
  onObsolete,
}: Props): JSX.Element {
  const composition = Object.entries(stream.composition_json).map(([component, mole_fraction]) => ({
    component,
    mole_fraction,
  }));

  const compositionColumns: ColumnsType<{ component: string; mole_fraction: number }> = [
    {
      title: '组分',
      dataIndex: 'component',
      width: 120,
    },
    {
      title: '摩尔分率',
      dataIndex: 'mole_fraction',
      width: 160,
      render: (v: number) => v.toFixed(4),
    },
  ];

  return (
    <div data-testid="stream-detail-page">
      <PageHeader
        title={`${stream.tag_number} · ${stream.stream_name}`}
        status={stream.sign_status}
        module="SIM"
        version={
          stream.approved_hash
            ? { hash: stream.approved_hash, label: stream.tag_number }
            : undefined
        }
        actions={
          <Space>
            <Button data-testid="stream-detail-back" onClick={onBack}>
              返回
            </Button>
            <Button
              type="primary"
              data-testid="stream-detail-submit"
              disabled={stream.sign_status !== 'DRAFT'}
              onClick={onSubmit}
            >
              提交批准
            </Button>
            <Button danger data-testid="stream-detail-obsolete" onClick={onObsolete}>
              弃用
            </Button>
          </Space>
        }
      />

      <ModuleLayout
        input={
          <Card title="基础信息" size="small">
            <Descriptions
              column={2}
              bordered
              size="small"
              data-testid="stream-detail-descriptions"
            >
              <Descriptions.Item label="tag_number">
                <span style={{ fontFamily: 'var(--font-mono, monospace)' }}>{stream.tag_number}</span>
              </Descriptions.Item>
              <Descriptions.Item label="名称">{stream.stream_name}</Descriptions.Item>
              <Descriptions.Item label="相态">
                <Tag color="blue">{STREAM_PHASE_LABEL[stream.phase]}</Tag>
                <Typography.Text type="secondary" style={{ marginLeft: 8 }}>
                  {stream.phase}
                </Typography.Text>
              </Descriptions.Item>
              <Descriptions.Item label="子相态">
                {stream.subphase ? (
                  <Tag>{STREAM_SUBPHASE_LABEL[stream.subphase]}</Tag>
                ) : (
                  <Typography.Text type="secondary">—</Typography.Text>
                )}
              </Descriptions.Item>
              <Descriptions.Item label="温度">{stream.temperature_c} °C</Descriptions.Item>
              <Descriptions.Item label="压力">{stream.pressure_mpa} MPa</Descriptions.Item>
              <Descriptions.Item label="质量流量">{stream.total_mass_flow_kg_h} kg/h</Descriptions.Item>
              <Descriptions.Item label="摩尔流量">{stream.total_molar_flow_kmol_h} kmol/h</Descriptions.Item>
              {stream.updated_by && (
                <Descriptions.Item label="更新人">{stream.updated_by}</Descriptions.Item>
              )}
              {stream.updated_at && (
                <Descriptions.Item label="更新时间">{stream.updated_at}</Descriptions.Item>
              )}
            </Descriptions>
          </Card>
        }
        result={
          <Card title="组成（摩尔分率）" size="small">
            <Table
              rowKey="component"
              columns={compositionColumns}
              dataSource={composition}
              pagination={false}
              size="small"
              onRow={(_, idx) =>
                ({
                  'data-testid': 'stream-composition-row',
                  'data-component-index': idx,
                }) as React.HTMLAttributes<HTMLElement>
              }
            />
          </Card>
        }
        lineage={
          <Row gutter={[16, 16]}>
            <Col span={24}>
              <Card title="签署矩阵" size="small">
                <SignatureMatrix matrix={matrix} signatures={signatures} currentStep={signatures.length} />
              </Card>
            </Col>
          </Row>
        }
      />
    </div>
  );
}

export default StreamDetailPage;