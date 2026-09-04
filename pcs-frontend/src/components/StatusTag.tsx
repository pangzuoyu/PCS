import { Tag } from 'antd';
import type { RecordSignStatus } from '../types/records';

const STATUS_COLOR: Record<RecordSignStatus, string> = {
  DRAFT: 'default',
  IN_APPROVAL: 'processing',
  CHECKED: 'success',
  CHECK_REJECTED: 'error',
  STALE: 'warning',
  CHANGE_PENDING: 'orange',
  CHANGED: 'blue',
  REVERSAL_PENDING: 'purple',
  OBSOLETE: 'default',
};

const STATUS_LABEL: Record<RecordSignStatus, string> = {
  DRAFT: '草稿',
  IN_APPROVAL: '审批中',
  CHECKED: '已核验',
  CHECK_REJECTED: '核验驳回',
  STALE: '失效',
  CHANGE_PENDING: '变更待批',
  CHANGED: '已变更',
  REVERSAL_PENDING: '撤销待批',
  OBSOLETE: '已弃用',
};

export function StatusTag({ status }: { status: RecordSignStatus }) {
  return <Tag color={STATUS_COLOR[status]}>{STATUS_LABEL[status]}</Tag>;
}