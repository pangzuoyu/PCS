/**
 * 物流详情 —— 「基本信息」Tab（SPEC §7.7.2 · P9B-3 · T8）。
 *
 * 内容：基础信息（物流号 / 名称 / 描述 / 相态 / 工况 / 来源 / 状态）+
 * 签署矩阵 + 审批链 + 物性冲突 + 只读表单 Schema。
 *
 * ⚠️ **「物流号」不显示** —— 契约里**没有**物流号（`tag_number` 已随「物流没有
 * 位号」的裁决删除）⇒ 名称就是标识（与列表页首列同口径）。
 */
import {
  Card,
  Col,
  Descriptions,
  Row,
  Tag,
  Typography,
} from 'antd';

import { ApprovalStepBar, type ApprovalStep } from '../../../components/common/ApprovalStepBar';
import { AssumedDataMarker } from '../../../components/common/AssumedDataMarker';
import { ConflictResolver, type Conflict } from '../../../components/common/ConflictResolver';
import { SchemaForm, type UiSchemaResponse } from '../../../components/common/SchemaForm';
import { SignatureMatrix, type SignatureRecord, type SignatureStep } from '../../../components/common/SignatureMatrix';
import {
  STREAM_CASE_TYPE_LABEL,
  STREAM_SOURCE_LABEL,
  streamPhaseColor,
  streamPhaseLabel,
  type Stream,
} from '../../../types/stream';

export interface StreamBasicTabProps {
  stream: Stream;
  matrix?: SignatureStep[];
  signatures?: SignatureRecord[];
  approvalSteps?: ApprovalStep[];
  currentApprovalStep?: number;
  conflicts?: Conflict[];
  uiSchema?: UiSchemaResponse;
}

export function StreamBasicTab({
  stream,
  matrix,
  signatures,
  approvalSteps,
  currentApprovalStep = 0,
  conflicts = [],
  uiSchema,
}: StreamBasicTabProps): JSX.Element {
  return (
    <div data-testid="stream-tab-basic">
      <Card title="基础信息" size="small">
        <Descriptions
          column={2}
          bordered
          size="small"
          data-testid="stream-detail-descriptions"
        >
          <Descriptions.Item label="名称">{stream.stream_name}</Descriptions.Item>
          <Descriptions.Item label="描述">{stream.description ?? '—'}</Descriptions.Item>
          <Descriptions.Item label="相态">
            <Tag color={streamPhaseColor(stream.phase)} data-testid="stream-phase-tag">
              {streamPhaseLabel(stream.phase)}
            </Tag>
            <Typography.Text type="secondary" style={{ marginLeft: 8 }}>
              {stream.phase ?? '—'}
            </Typography.Text>
          </Descriptions.Item>
          <Descriptions.Item label="工况">
            {stream.case_type ? STREAM_CASE_TYPE_LABEL[stream.case_type] : '—'}
          </Descriptions.Item>
          {/* ⚠️ 只显示 `source`（4 值 · 录入通道）—— 不是 `source_type`（13 值）*/}
          <Descriptions.Item label="来源">
            {stream.source ? STREAM_SOURCE_LABEL[stream.source] : '—'}
          </Descriptions.Item>
          <Descriptions.Item label="温度">{stream.temp ?? '—'} °C</Descriptions.Item>
          <Descriptions.Item label="压力">{stream.press ?? '—'} MPaG</Descriptions.Item>
          <Descriptions.Item label="质量流量">{stream.mass_flow ?? '—'} kg/h</Descriptions.Item>
          <Descriptions.Item label="摩尔流量">{stream.molar_flow ?? '—'} kmol/h</Descriptions.Item>
          {stream.updated_at && (
            <Descriptions.Item label="更新时间">{stream.updated_at}</Descriptions.Item>
          )}
        </Descriptions>
      </Card>

      <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
        {matrix && (
          <Col span={24}>
            <Card title="签署矩阵" size="small" data-testid="stream-detail-signature-matrix">
              <SignatureMatrix
                matrix={matrix}
                signatures={signatures ?? []}
                currentStep={signatures?.length ?? 0}
              />
            </Card>
          </Col>
        )}
        {approvalSteps && approvalSteps.length > 0 && (
          <Col span={24}>
            <Card title="审批链" size="small" data-testid="stream-detail-approval-bar">
              <ApprovalStepBar
                currentStep={currentApprovalStep}
                totalSteps={approvalSteps.length}
                role="CHECKER"
                steps={approvalSteps}
              />
            </Card>
          </Col>
        )}
        {conflicts.length > 0 && (
          <Col span={24}>
            <Card title="物性冲突" size="small" data-testid="stream-detail-conflict-resolver">
              <ConflictResolver conflicts={conflicts} />
            </Card>
          </Col>
        )}
        {uiSchema && (
          <Col span={24}>
            <Card title="表单 Schema（只读）" size="small" data-testid="stream-detail-schema-form">
              <SchemaForm
                schema={uiSchema}
                value={{
                  stream_name: stream.stream_name,
                  phase: stream.phase,
                  // 键名随数据一起对齐契约 StreamResponse（SchemaForm 的 value
                  // 是自由键值对象，键名应与实际数据同源，否则表单显示空值）
                  temp: stream.temp,
                  press: stream.press,
                  mass_flow: stream.mass_flow,
                }}
              />
              {stream.sign_status === 'STALE' && (
                <div style={{ marginTop: 8 }}>
                  <AssumedDataMarker
                    assumed={true}
                    reason="上游工艺变更"
                    source="S-102 流量调整"
                    value={stream.mass_flow == null ? '—' : String(stream.mass_flow)}
                  />
                  <span style={{ marginLeft: 8 }}>流量为假设值</span>
                </div>
              )}
            </Card>
          </Col>
        )}
      </Row>
    </div>
  );
}

export default StreamBasicTab;
