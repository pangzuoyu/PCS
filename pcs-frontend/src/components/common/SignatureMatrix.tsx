/**
 * SignatureMatrix — 签署矩阵渲染（P45-1-12 / Task 17）。
 *
 * SPEC §6.19 + plan P45-1-12：
 * - 列数随 matrix 动态
 * - 每列显示角色 + 签署状态
 * - 已签署：姓名 + 时间 + 哈希
 * - 代录：「（代录：X）」标注
 * - 当前待签列脉冲高亮（currentStep 列）
 *
 * Props（SPEC 锁定）：
 *   matrix: SignatureStep[]
 *   signatures?: SignatureRecord[]  // 已签记录（key by step_index）
 *   currentStep: number             // 高亮当前待签列
 */
import { Card, Space, Tag, Typography } from 'antd';

export interface SignatureStep {
  step_index: number;
  role: string;
}

export interface SignatureRecord {
  step_index: number;
  signer_name: string;
  signed_at: string;
  record_hash?: string;
  /** 是否代录（如「代录：张三」 → 显示「（代录：代录人）」） */
  delegated_by?: string;
}

interface Props {
  matrix: SignatureStep[];
  signatures?: SignatureRecord[];
  currentStep: number;
}

const PULSE_STYLE: React.CSSProperties = {
  animation: 'pcs-pulse 1.6s ease-in-out infinite',
};

function shortHash(hash: string): string {
  if (hash.length <= 12) return hash;
  return `${hash.slice(0, 4)}…${hash.slice(-4)}`;
}

export function SignatureMatrix({ matrix, signatures = [], currentStep }: Props): JSX.Element {
  const byStep = new Map(signatures.map((s) => [s.step_index, s]));
  // 按 step_index 升序
  const sorted = [...matrix].sort((a, b) => a.step_index - b.step_index);

  return (
    <Card title="签署矩阵" data-testid="signature-matrix">
      <div
        data-testid="signature-matrix-grid"
        style={{
          display: 'grid',
          gridTemplateColumns: `repeat(${sorted.length || 1}, minmax(0, 1fr))`,
          gap: 12,
        }}
      >
        {sorted.map((step) => {
          const sig = byStep.get(step.step_index);
          const isCurrent = step.step_index === currentStep;
          const isSigned = !!sig;
          return (
            <div
              key={step.step_index}
              data-testid="signature-column"
              data-step-index={step.step_index}
              data-current={isCurrent ? 'true' : 'false'}
              data-signed={isSigned ? 'true' : 'false'}
              style={{
                border: '1px solid var(--border-subtle, #D0D7DE)',
                borderRadius: 'var(--radius-md, 6px)',
                padding: 12,
                background: isCurrent
                  ? 'var(--surface-bg-info, #F0F6FF)'
                  : 'var(--surface-bg, #FFFFFF)',
                ...(isCurrent ? PULSE_STYLE : {}),
              }}
            >
              <Space direction="vertical" size={4}>
                <Space>
                  <Typography.Text strong>{step.role}</Typography.Text>
                  {isCurrent && (
                    <Tag color="processing" data-testid="current-tag">
                      当前
                    </Tag>
                  )}
                </Space>

                {sig ? (
                  <Space direction="vertical" size={2}>
                    <Typography.Text strong data-testid="signer-name">
                      {sig.signer_name}
                    </Typography.Text>
                    <Typography.Text type="secondary" data-testid="signer-time">
                      {sig.signed_at}
                    </Typography.Text>
                    {sig.record_hash && (
                      <Typography.Text
                        type="secondary"
                        style={{ fontFamily: 'var(--font-mono, monospace)' }}
                        data-testid="signer-hash"
                      >
                        {shortHash(sig.record_hash)}
                      </Typography.Text>
                    )}
                    {sig.delegated_by && (
                      <Typography.Text
                        type="warning"
                        data-testid="delegated-by"
                      >
                        （代录：{sig.delegated_by}）
                      </Typography.Text>
                    )}
                  </Space>
                ) : (
                  <Typography.Text type="secondary" data-testid="unsigned">
                    待签署
                  </Typography.Text>
                )}
              </Space>
            </div>
          );
        })}
      </div>
    </Card>
  );
}

export default SignatureMatrix;