/**
 * RevTimeline — 交付物 Rev 历史（P45-1-11 / Task 16）。
 *
 * SPEC §6.18 + plan P45-1-11：
 * - 垂直时间线（最新 Rev 在顶）
 * - 每 Rev：字母 + 时间 + 状态 tag（ISSUED_FOR_* + 可选 AFFECTED）
 * - 签署行：角色 + 签署人 + ✓
 * - 快照行：record_hash + [查看] 按钮 → onVersionClick?(version_id)
 * - AFFECTED 红色标记
 *
 * Props（SPEC 锁定）：
 *   versions: RevVersion[]
 *   onVersionClick?: (version_id: string) => void
 */
import { Timeline, Card, Space, Tag, Typography, Button } from 'antd';
import type { TimelineProps } from 'antd';

export type RevStatus =
  | 'ISSUED_FOR_DESIGN'
  | 'ISSUED_FOR_REVIEW'
  | 'ISSUED_FOR_CONSTRUCTION'
  | 'ISSUED_FOR_USE';

export interface SignatureSummary {
  role: string;
  signer_name: string;
  signed_at?: string;
}

export interface RevVersion {
  version_id: string;
  /** Rev 字母（A/B/C …） */
  rev_letter: string;
  /** ISO 时间字符串 */
  issued_at: string;
  status: RevStatus;
  /** 是否受影响（上游变更 → 红色标记） */
  affected?: boolean;
  signatures?: SignatureSummary[];
  /** 快照 record_hash（前后 8 位即可） */
  snapshot_hash?: string;
  /** 完整 hash（用于复制/查看） */
  snapshot_hash_full?: string;
}

interface Props {
  versions: RevVersion[];
  onVersionClick?: (version_id: string) => void;
}

const STATUS_COLOR: Record<RevStatus, string> = {
  ISSUED_FOR_DESIGN: 'blue',
  ISSUED_FOR_REVIEW: 'cyan',
  ISSUED_FOR_CONSTRUCTION: 'green',
  ISSUED_FOR_USE: 'gold',
};

function shortHash(hash: string): string {
  if (hash.length <= 12) return hash;
  return `${hash.slice(0, 4)}…${hash.slice(-4)}`;
}

export function RevTimeline({ versions, onVersionClick }: Props): JSX.Element {
  if (versions.length === 0) {
    return (
      <Card data-testid="rev-timeline" title="Rev 历史">
        <Typography.Text type="secondary">无 Rev 记录</Typography.Text>
      </Card>
    );
  }

  // 最新 Rev 在顶
  const sorted = [...versions].sort((a, b) =>
    a.issued_at < b.issued_at ? 1 : -1,
  );

  const items: TimelineProps['items'] = sorted.map((v) => ({
    color: v.affected ? 'red' : 'blue',
    dot: v.affected ? (
      <span data-testid="rev-affected-dot" aria-label="AFFECTED">●</span>
    ) : undefined,
    children: (
      <div data-testid="rev-item" data-version-id={v.version_id}>
        <Space>
          <Typography.Text strong>Rev {v.rev_letter}</Typography.Text>
          <Typography.Text type="secondary">{v.issued_at}</Typography.Text>
          <Tag color={STATUS_COLOR[v.status]} data-testid="rev-status">
            {v.status}
          </Tag>
          {v.affected && (
            <Tag color="red" data-testid="rev-affected">
              AFFECTED
            </Tag>
          )}
        </Space>

        {v.signatures && v.signatures.length > 0 && (
          <div data-testid="rev-signatures" style={{ marginTop: 4 }}>
            <Typography.Text type="secondary">签署：</Typography.Text>
            {v.signatures.map((s, idx) => (
              <span
                key={`${s.role}-${idx}`}
                data-testid="rev-signature"
                style={{ marginRight: 12 }}
              >
                {s.role} {s.signer_name} ✓
              </span>
            ))}
          </div>
        )}

        {v.snapshot_hash && (
          <Space style={{ marginTop: 4 }}>
            <Typography.Text type="secondary">快照：</Typography.Text>
            <span
              data-testid="rev-snapshot-hash"
              style={{ fontFamily: 'var(--font-mono, monospace)' }}
            >
              {shortHash(v.snapshot_hash)}
            </span>
            <Button
              type="link"
              size="small"
              data-testid="rev-snapshot-view"
              data-version-id={v.version_id}
              onClick={() => onVersionClick?.(v.version_id)}
            >
              查看
            </Button>
          </Space>
        )}
      </div>
    ),
  }));

  return (
    <Card title="Rev 历史" data-testid="rev-timeline">
      <Timeline
        data-testid="rev-timeline-list"
        items={items}
        style={{ marginTop: 0 }}
      />
    </Card>
  );
}

export default RevTimeline;