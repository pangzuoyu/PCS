/**
 * ApprovalPanelPage — CONFIG 审批面板（P45-2-7 / Task 25）。
 *
 * SPEC §7.10.7：
 * - 待审批列表
 * - 版本对比（v_prev vs v_current 字段级 diff）
 * - 审批意见（comment 输入）
 * - 双重审批标记（公式：需要 ≥2 名不同审批人确认才能发布）
 *
 * Props（SPEC 锁定）：
 *   items: PendingApproval[]
 *   currentUser?: string     // 当前审批人（双重审批去重）
 *   onApprove?: (id, comment?) => void
 *   onReject?: (id, comment?) => void
 */
import { useState } from 'react';
import {
  Alert,
  Button,
  Collapse,
  Empty,
  Input,
  Space,
  Tag,
  Typography,
} from 'antd';
import { CheckCircleOutlined, CloseCircleOutlined } from '@ant-design/icons';

/** 单条审批记录。 */
export interface ApprovalRecord {
  approver: string;
  approved_at: string;
}

/** 待审批资产（SPEC §7.10.7）。 */
export interface PendingApproval {
  approval_id: string;
  asset_id: string;
  asset_name: string;
  asset_category: 'formula' | 'template' | 'coefficient' | 'standard_db' | 'project_template' | 'equipment_lib';
  module: string;
  submitted_by: string;
  submitted_at: string;
  current_version: string;
  current_content: string;
  previous_version?: string;
  previous_content?: string;
  /** 公式类需要双重审批（SPEC §7.10.7）。 */
  double_approval: boolean;
  /** 已通过的审批记录。 */
  approvals: ApprovalRecord[];
}

interface Props {
  items: PendingApproval[];
  currentUser?: string;
  onApprove?: (id: string, comment?: string) => void;
  onReject?: (id: string, comment?: string) => void;
}

const CATEGORY_LABEL: Record<PendingApproval['asset_category'], string> = {
  formula: '公式',
  template: '模板文件',
  coefficient: '系数表',
  standard_db: '标准数据库',
  project_template: '项目模板',
  equipment_lib: '复用设备库',
};

/** 字段级 diff：按行比较 current vs previous。 */
function buildDiff(prev: string, curr: string): Array<{ key: number; prev: string; curr: string; changed: boolean }> {
  const prevLines = prev.split('\n');
  const currLines = curr.split('\n');
  const maxLen = Math.max(prevLines.length, currLines.length);
  const result: Array<{ key: number; prev: string; curr: string; changed: boolean }> = [];
  for (let i = 0; i < maxLen; i++) {
    const p = prevLines[i] ?? '';
    const c = currLines[i] ?? '';
    result.push({ key: i, prev: p, curr: c, changed: p !== c });
  }
  return result;
}

export function ApprovalPanelPage({
  items,
  currentUser,
  onApprove,
  onReject,
}: Props): JSX.Element {
  const [comments, setComments] = useState<Record<string, string>>({});

  function getComment(id: string): string {
    return comments[id] ?? '';
  }

  function setComment(id: string, value: string): void {
    setComments((prev) => ({ ...prev, [id]: value }));
  }

  return (
    <div data-testid="approval-page">
      <Typography.Title level={3}>审批面板</Typography.Title>

      {items.length === 0 ? (
        <Empty description="暂无待审批" data-testid="approval-empty" />
      ) : (
        <Space direction="vertical" size={12} style={{ width: '100%' }}>
          {items.map((item) => {
            const approverSet = new Set(item.approvals.map((a) => a.approver));
            const currentUserApproved = currentUser ? approverSet.has(currentUser) : false;
            const approverCount = item.approvals.length;
            const readyToPublish =
              item.double_approval && approverCount >= 2 && !currentUserApproved;

            const panel = (
              <Space direction="vertical" size={12} style={{ width: '100%' }}>
                {item.double_approval && (
                  <Alert
                    type="info"
                    showIcon
                    message={
                      <Space data-testid="approval-double-badge">
                        <Tag color="orange">双重审批</Tag>
                        <span>
                          公式类资产需要 ≥2 名不同审批人确认。当前已通过 {approverCount} 人
                        </span>
                      </Space>
                    }
                  />
                )}

                {readyToPublish && (
                  <Alert
                    type="success"
                    showIcon
                    message={
                      <Space data-testid="approval-ready-publish">
                        <CheckCircleOutlined />
                        <span>双重审批达成，可发布</span>
                      </Space>
                    }
                  />
                )}

                {item.previous_content && (
                  <div data-testid="approval-diff-panel">
                    <Typography.Text strong>
                      版本对比：{item.previous_version} → {item.current_version}
                    </Typography.Text>
                    <div
                      style={{
                        fontFamily: 'var(--font-mono, monospace)',
                        background: 'var(--surface-bg-info, #F0F4F8)',
                        padding: 8,
                        borderRadius: 4,
                        marginTop: 8,
                      }}
                    >
                      {buildDiff(item.previous_content, item.current_content).map((d) => (
                        <div
                          key={d.key}
                          data-testid="approval-diff-row"
                          data-changed={String(d.changed)}
                          style={{
                            background: d.changed ? 'var(--surface-bg-warning, #FFF7E6)' : 'transparent',
                            padding: '2px 4px',
                          }}
                        >
                          {d.changed ? (
                            <span>
                              <span style={{ color: 'var(--state-check-rejected)' }}>- {d.prev || '（空）'}</span>
                              <br />
                              <span style={{ color: 'var(--state-checked)' }}>+ {d.curr || '（空）'}</span>
                            </span>
                          ) : (
                            <span>{d.curr}</span>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {item.approvals.length > 0 && (
                  <div>
                    <Typography.Text strong>已通过审批人：</Typography.Text>
                    <Space wrap style={{ marginTop: 4 }}>
                      {item.approvals.map((a, i) => (
                        <Tag key={i} color="green" data-testid="approval-approver">
                          {a.approver} · {a.approved_at}
                        </Tag>
                      ))}
                    </Space>
                  </div>
                )}

                <Input.TextArea
                  placeholder="审批意见（可选）"
                  data-testid="approval-comment-input"
                  rows={2}
                  value={getComment(item.approval_id)}
                  onChange={(e) => setComment(item.approval_id, e.target.value)}
                />

                <Space>
                  <Button
                    type="primary"
                    icon={<CheckCircleOutlined />}
                    data-testid="approval-approve-btn"
                    disabled={currentUserApproved}
                    onClick={() => onApprove?.(item.approval_id, getComment(item.approval_id))}
                  >
                    {currentUserApproved ? '✓ 已通过' : '通过'}
                  </Button>
                  <Button
                    danger
                    icon={<CloseCircleOutlined />}
                    data-testid="approval-reject-btn"
                    onClick={() => onReject?.(item.approval_id, getComment(item.approval_id))}
                  >
                    驳回
                  </Button>
                </Space>
              </Space>
            );

            return (
              <div
                key={item.approval_id}
                data-testid="approval-item"
                data-approval-id={item.approval_id}
                style={{
                  border: '1px solid var(--color-border, #E5E7EB)',
                  borderRadius: 4,
                  padding: 16,
                }}
              >
                <Space style={{ width: '100%', justifyContent: 'space-between' }}>
                  <Space>
                    <Typography.Text strong>{item.asset_name}</Typography.Text>
                    <Tag color="blue">{CATEGORY_LABEL[item.asset_category]}</Tag>
                    <Tag>{item.module}</Tag>
                    {item.double_approval && (
                      <Tag color="orange" data-testid="approval-double-badge">
                        双重审批
                      </Tag>
                    )}
                  </Space>
                  <Typography.Text type="secondary">
                    {item.submitted_by} · {item.submitted_at} · {item.current_version}
                  </Typography.Text>
                </Space>

                <Collapse
                  ghost
                  items={[
                    {
                      key: item.approval_id,
                      label: <span data-testid="approval-toggle">展开审批详情</span>,
                      children: panel,
                    },
                  ]}
                />
              </div>
            );
          })}
        </Space>
      )}
    </div>
  );
}

export default ApprovalPanelPage;