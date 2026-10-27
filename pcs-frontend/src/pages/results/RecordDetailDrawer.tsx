/**
 * 记录详情抽屉（P9B-2 · T5 · SPEC §7.19.1）。
 *
 * 结构：顶部（状态徽章 + 哈希）→ 操作栏（`<RecordActions>`）→ 批注 → 状态时间线。
 *
 * ⚠️ **`key` 必须带 `recordType + recordId`** —— P9B-1 的 bug-2043
 * （跨模块切换残留上一模块的行）同形：换记录不重建 ⇒ 残留上一条的内容（RF-13）。
 * ⇒ **宿主页**（`ResultListPage`）负责给 `key`。
 */
import { Drawer, Space, Typography } from 'antd';

import { CommentPanel } from '../../components/common/CommentPanel';
import { HashBadge } from '../../components/common/HashBadge';
import { RecordActions } from '../../components/common/RecordActions';
import { RecordTimeline } from '../../components/common/RecordTimeline';
import { StateBadge } from '../../components/common/StateBadge';
import type { EditableRecordType } from '../../api/records';

export interface RecordDetailDrawerProps {
  module: EditableRecordType;
  recordId: string;
  /** 行数据（状态 / 哈希 / 项目 id）。 */
  record: Record<string, unknown>;
  open?: boolean;
  onClose?: () => void;
  /** 动作成功后由宿主页刷新。 */
  onDone?: () => void;
}

export function RecordDetailDrawer({
  module,
  recordId,
  record,
  open = true,
  onClose,
  onDone,
}: RecordDetailDrawerProps): JSX.Element {
  const signStatus = (record['sign_status'] as string | null | undefined) ?? null;
  const recordHash = (record['record_hash'] as string | null | undefined) ?? null;
  const projectId = (record['project_id'] as string | null | undefined) ?? undefined;

  return (
    <Drawer
      open={open}
      onClose={onClose}
      title="记录详情"
      width={720}
      data-testid="record-detail-drawer"
      data-record-id={recordId}
      data-record-type={module}
    >
      <Space direction="vertical" style={{ width: '100%' }}>
        <Space>
          <StateBadge status={(signStatus ?? 'DRAFT') as never} />
          {recordHash ? <HashBadge hash={recordHash} /> : <Typography.Text>—</Typography.Text>}
        </Space>
        <RecordActions
          module={module}
          recordId={recordId}
          signStatus={signStatus}
          projectId={projectId}
          onDone={onDone ?? (() => undefined)}
        />
        <CommentPanel module={module} recordId={recordId} />
        <RecordTimeline module={module} recordId={recordId} />
      </Space>
    </Drawer>
  );
}
