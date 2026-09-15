/**
 * SignatureMatrix 测试（P45-1-12 / Task 17）。
 *
 * 覆盖（SPEC §6.19 + plan P45-1-12）：
 * - 渲染 matrix 各列（角色 + 签署状态）
 * - 已签署：姓名 + 时间 + 短哈希
 * - 代录：「（代录：X）」标注
 * - 当前待签列 data-current="true" + 脉冲高亮（animation 包含 pcs-pulse）
 * - 未签列：待签署
 */
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';

import { SignatureMatrix, type SignatureStep, type SignatureRecord } from '../../../src/components/common/SignatureMatrix';

const matrix: SignatureStep[] = [
  { step_index: 0, role: '校核' },
  { step_index: 1, role: '审核' },
  { step_index: 2, role: '审定' },
];

const signatures: SignatureRecord[] = [
  {
    step_index: 0,
    signer_name: '李四',
    signed_at: '2026-09-15 14:00',
    record_hash: 'a3f9b2e1c21ed7a8',
  },
  {
    step_index: 1,
    signer_name: '王五',
    signed_at: '2026-09-15 14:10',
    record_hash: 'b2e1c21ed7a8a3f9',
    delegated_by: '代录人',
  },
];

describe('SignatureMatrix — 渲染 (P45-1-12)', () => {
  it('3 列渲染（grid）', () => {
    const { container } = render(
      <SignatureMatrix matrix={matrix} currentStep={2} />,
    );
    const cols = container.querySelectorAll('[data-testid="signature-column"]');
    expect(cols.length).toBe(3);
  });

  it('每列含角色 label', () => {
    const { container } = render(
      <SignatureMatrix matrix={matrix} currentStep={2} />,
    );
    const cols = container.querySelectorAll('[data-testid="signature-column"]');
    expect(cols[0].textContent).toContain('校核');
    expect(cols[1].textContent).toContain('审核');
    expect(cols[2].textContent).toContain('审定');
  });

  it('已签署列：姓名 + 时间 + 短 hash', () => {
    const { container } = render(
      <SignatureMatrix
        matrix={matrix}
        signatures={signatures}
        currentStep={2}
      />,
    );
    const cols = container.querySelectorAll('[data-testid="signature-column"]');
    expect(cols[0].querySelector('[data-testid="signer-name"]')?.textContent)
      .toBe('李四');
    expect(cols[0].querySelector('[data-testid="signer-time"]')?.textContent)
      .toContain('2026-09-15 14:00');
    expect(cols[0].querySelector('[data-testid="signer-hash"]')?.textContent)
      .toBe('a3f9…d7a8');
  });

  it('代录：「（代录：X）」标注', () => {
    const { container } = render(
      <SignatureMatrix
        matrix={matrix}
        signatures={signatures}
        currentStep={2}
      />,
    );
    const cols = container.querySelectorAll('[data-testid="signature-column"]');
    expect(cols[1].querySelector('[data-testid="delegated-by"]')?.textContent)
      .toBe('（代录：代录人）');
  });

  it('未签列：「待签署」', () => {
    const { container } = render(
      <SignatureMatrix
        matrix={matrix}
        signatures={signatures}
        currentStep={2}
      />,
    );
    const cols = container.querySelectorAll('[data-testid="signature-column"]');
    expect(cols[2].querySelector('[data-testid="unsigned"]')?.textContent)
      .toBe('待签署');
  });
});

describe('SignatureMatrix — 当前列', () => {
  it('currentStep 列 data-current="true" + 「当前」tag', () => {
    const { container } = render(
      <SignatureMatrix
        matrix={matrix}
        signatures={signatures}
        currentStep={2}
      />,
    );
    const cols = container.querySelectorAll('[data-testid="signature-column"]');
    expect(cols[0].getAttribute('data-current')).toBe('false');
    expect(cols[2].getAttribute('data-current')).toBe('true');
    expect(screen.getByTestId('current-tag')).toBeTruthy();
  });

  it('当前列脉冲 animation 包含 pcs-pulse', () => {
    const { container } = render(
      <SignatureMatrix matrix={matrix} currentStep={1} />,
    );
    const cols = container.querySelectorAll('[data-testid="signature-column"]');
    const style = cols[1].getAttribute('style') || '';
    expect(style).toContain('pcs-pulse');
  });

  it('非当前列无 animation', () => {
    const { container } = render(
      <SignatureMatrix matrix={matrix} currentStep={1} />,
    );
    const cols = container.querySelectorAll('[data-testid="signature-column"]');
    const style0 = cols[0].getAttribute('style') || '';
    const style2 = cols[2].getAttribute('style') || '';
    expect(style0).not.toContain('pcs-pulse');
    expect(style2).not.toContain('pcs-pulse');
  });
});

describe('SignatureMatrix — 边界', () => {
  it('空 matrix：不报错', () => {
    render(<SignatureMatrix matrix={[]} currentStep={0} />);
    expect(screen.getByText('签署矩阵')).toBeTruthy();
  });

  it('未传 signatures：全部待签署', () => {
    const { container } = render(
      <SignatureMatrix matrix={matrix} currentStep={0} />,
    );
    const unsigned = container.querySelectorAll('[data-testid="unsigned"]');
    expect(unsigned.length).toBe(3);
  });

  it('short hash：长度 ≤ 12 显示完整', () => {
    const sigs: SignatureRecord[] = [
      {
        step_index: 0,
        signer_name: 'X',
        signed_at: 't',
        record_hash: 'short',
      },
    ];
    const { container } = render(
      <SignatureMatrix
        matrix={matrix}
        signatures={sigs}
        currentStep={1}
      />,
    );
    expect(container.querySelector('[data-testid="signer-hash"]')?.textContent)
      .toBe('short');
  });
});