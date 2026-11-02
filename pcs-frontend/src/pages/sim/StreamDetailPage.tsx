/**
 * StreamDetailPage — SIM 物流详情（SPEC §7.7.2 · P9B-3 · T8）。
 *
 * ## 结构：**Tab 宿主**
 *
 * 7 个 Tab（SPEC §7.7.2）：基本信息 / 组成 / 物性 / 状态点 / 设备连接 / 血缘 /
 * 校核记录 ⇒ 内容全部下沉到 `tabs/` 下 7 个文件（每个 ≤ 150 行）。
 *
 * ⚠️ **只有当前 Tab 会取数**（antd 的 Tabs 默认懒渲染未激活的面板）⇒ 打开
 * 详情页**不会**打 4 个请求 ⇒ 首屏不被拖慢。
 *
 * Props：
 *   stream: Stream
 *   onBack?: () => void
 *   onSubmit?: () => void
 *   onObsolete?: () => void
 */
import { Button, Space, Tabs } from 'antd';

import { PageHeader } from '../../components/common/PageHeader';
import type { ApprovalStep } from '../../components/common/ApprovalStepBar';
import type { Conflict } from '../../components/common/ConflictResolver';
import type { SignatureRecord, SignatureStep } from '../../components/common/SignatureMatrix';
import { ChangeImpactPanel, type ChangeSource, type AffectedRecord } from '../../components/common/ChangeImpactPanel';
import { changeImpactApi } from '../../api/changeImpact';
import type { UiSchemaResponse } from '../../components/common/SchemaForm';
import { StreamBasicTab } from './tabs/StreamBasicTab';
import { StreamCompositionTab } from './tabs/StreamCompositionTab';
import { StreamConnectionsTab } from './tabs/StreamConnectionsTab';
import { StreamLineageTab } from './tabs/StreamLineageTab';
import { StreamPropertiesTab } from './tabs/StreamPropertiesTab';
import { StreamReviewLogTab } from './tabs/StreamReviewLogTab';
import { StreamStatePointsTab } from './tabs/StreamStatePointsTab';
import type { Stream } from '../../types/stream';

interface Props {
  stream: Stream;
  matrix?: SignatureStep[];
  signatures?: SignatureRecord[];
  approvalSteps?: ApprovalStep[];
  currentApprovalStep?: number;
  conflicts?: Conflict[];
  changeImpact?: { source: ChangeSource; records: AffectedRecord[] } | null;
  uiSchema?: UiSchemaResponse;
  onBack?: () => void;
  onSubmit?: () => void;
  onObsolete?: () => void;
}

export function StreamDetailPage({
  stream,
  matrix,
  signatures,
  approvalSteps,
  currentApprovalStep = 0,
  conflicts = [],
  changeImpact,
  uiSchema,
  onBack,
  onSubmit,
  onObsolete,
}: Props): JSX.Element {
  return (
    <div data-testid="stream-detail-page">
      <PageHeader
        title={stream.stream_name}
        status={stream.sign_status}
        module="SIM"
        version={
          stream.record_hash
            ? { hash: stream.record_hash, label: stream.stream_name }
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

      <Tabs
        data-testid="stream-detail-tabs"
        defaultActiveKey="basic"
        items={[
          {
            key: 'basic',
            label: '基本信息',
            children: (
              <StreamBasicTab
                stream={stream}
                matrix={matrix}
                signatures={signatures}
                approvalSteps={approvalSteps}
                currentApprovalStep={currentApprovalStep}
                conflicts={conflicts}
                uiSchema={uiSchema}
              />
            ),
          },
          {
            key: 'composition',
            label: '组成',
            children: <StreamCompositionTab stream={stream} />,
          },
          {
            key: 'properties',
            label: '物性',
            children: <StreamPropertiesTab streamId={stream.stream_id} />,
          },
          {
            key: 'state-points',
            label: '状态点',
            children: <StreamStatePointsTab streamId={stream.stream_id} />,
          },
          {
            key: 'connections',
            label: '设备连接',
            children: <StreamConnectionsTab stream={stream} />,
          },
          {
            key: 'lineage',
            label: '血缘',
            children: <StreamLineageTab streamId={stream.stream_id} />,
          },
          {
            key: 'review-log',
            label: '校核记录',
            children: <StreamReviewLogTab streamId={stream.stream_id} />,
          },
        ]}
      />

      {/* 变更影响：与「血缘」同属「谁受影响」⇒ 放在 Tab 之外的操作区 */}
      {changeImpact && (
        <div data-testid="stream-detail-change-impact">
          <ChangeImpactPanel
            changeSource={changeImpact.source}
            affectedRecords={changeImpact.records}
            // ⚠️ **两个端点，不合并**（SPEC §6.7.1）：系统判定 confirm /
            // 人工判定 manual-adjust。`record_type` 已是注册表键 ⇒ 后端不 404。
            onConfirmSystem={(recordType, recordId) =>
              changeImpactApi.confirm(recordType, recordId)
            }
            onManualAdjust={(recordType, recordId, decision, reason) =>
              changeImpactApi.manualAdjust(recordType, recordId, { decision, reason })
            }
          />
        </div>
      )}
    </div>
  );
}

export default StreamDetailPage;
