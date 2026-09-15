/**
 * ApprovalStepBar — 批准链进度条（P45-1-2 / Task 7）。
 *
 * 与 SPEC §6.2 + tokens.css --state-* + meta API V1.1 一致：
 * ①校核 ✓ ── ②审核 ● ── ③审定 ○
 *
 * 视觉：
 * - 已完成：绿色圆 + ✓ （var(--state-checked)）
 * - 当前  ：蓝色脉冲圆 + ●  （var(--state-in-approval) + @keyframes pulse）
 * - 未开始：灰色空心圆 + ○  （var(--text-tertiary)）
 * - 退回  ：红色 + ✕       （var(--state-check-rejected)）
 * - 连接线：1px dashed / var(--text-tertiary) 跨步间
 *
 * role 字段：当前用户角色；若 steps[i].role !== role 视觉提示为"未到我"
 * （v0.1 不阻挡权限，v0.2 接 Can 组件）。
 */
import type { CSSProperties } from 'react';

export interface ApprovalStep {
  step: number;
  role: string;
  roleLabel: string;
  approver?: string;
  approvedAt?: string;
  decision?: 'APPROVED' | 'REJECTED';
}

export interface ApprovalStepBarProps {
  currentStep: number;
  totalSteps: number;
  role: string;
  steps: ApprovalStep[];
}

type MarkerKind = 'approved' | 'current' | 'pending' | 'rejected';

function markerKind(step: ApprovalStep, currentStep: number): MarkerKind {
  if (step.decision === 'REJECTED') return 'rejected';
  if (step.decision === 'APPROVED') return 'approved';
  if (step.step === currentStep) return 'current';
  return 'pending';
}

const MARKER_GLYPH: Record<MarkerKind, string> = {
  approved: '✓',
  current: '●',
  pending: '○',
  rejected: '✕',
};

const MARKER_COLOR: Record<MarkerKind, string> = {
  approved: 'var(--state-checked)',
  current: 'var(--state-in-approval)',
  pending: 'var(--text-tertiary)',
  rejected: 'var(--state-check-rejected)',
};

function markerStyle(kind: MarkerKind): CSSProperties {
  const color = MARKER_COLOR[kind];
  return {
    display: 'inline-flex',
    alignItems: 'center',
    justifyContent: 'center',
    width: 24,
    height: 24,
    borderRadius: 'var(--radius-full, 999px)',
    background: kind === 'current' ? color : 'transparent',
    border: `1.5px solid ${color}`,
    color,
    fontSize: 12,
    fontWeight: 600,
    flexShrink: 0,
    animation: kind === 'current' ? 'pcs-pulse 1.6s ease-in-out infinite' : undefined,
  };
}

export function ApprovalStepBar({
  currentStep,
  totalSteps,
  role,
  steps,
}: ApprovalStepBarProps): JSX.Element {
  // totalSteps / role 字段保留兼容（plan Props）；v0.1 不消费但显式标记
  void totalSteps;
  void role;

  const connectorStyle: CSSProperties = {
    flex: 1,
    height: 0,
    borderTop: '1px dashed var(--text-tertiary, #5A6773)',
    marginTop: 12,
    minWidth: 16,
  };

  return (
    <div
      data-testid="approval-step-bar"
      data-current-step={currentStep}
      data-total-steps={steps.length}
      style={{ display: 'flex', alignItems: 'flex-start', gap: 'var(--space-2, 8px)' }}
    >
      {steps.map((s, idx) => {
        const kind = markerKind(s, currentStep);
        const isLast = idx === steps.length - 1;
        const textColor = kind === 'pending'
          ? 'var(--text-tertiary, #5A6773)'
          : 'var(--text-primary)';
        return (
          <div
            key={s.step}
            data-testid="approval-step"
            data-step={s.step}
            data-role={s.role}
            data-kind={kind}
            style={{ display: 'flex', alignItems: 'flex-start', flex: isLast ? '0 0 auto' : 1 }}
          >
            <span
              data-testid="approval-step-marker"
              style={markerStyle(kind)}
              aria-label={`step-${s.step}-${kind}`}
            >
              {MARKER_GLYPH[kind]}
            </span>
            <div
              style={{
                display: 'flex',
                flexDirection: 'column',
                gap: 'var(--space-1, 4px)',
                marginLeft: 'var(--space-2, 8px)',
                marginRight: 'var(--space-2, 8px)',
                color: textColor,
                fontSize: 12,
              }}
            >
              <span data-testid="approval-step-label" style={{ fontWeight: 600 }}>
                {s.roleLabel}
              </span>
              {s.approver && (
                <span data-testid="approval-step-approver" style={{ opacity: 0.85 }}>
                  {s.approver}
                </span>
              )}
              {s.decision && (
                <span
                  data-testid="approval-step-decision"
                  style={{ color: MARKER_COLOR[kind] }}
                >
                  {s.decision === 'APPROVED' ? '已批准' : '已退回'}
                </span>
              )}
            </div>
            {!isLast && (
              <div
                data-testid="approval-step-connector"
                aria-hidden="true"
                style={connectorStyle}
              />
            )}
          </div>
        );
      })}
    </div>
  );
}