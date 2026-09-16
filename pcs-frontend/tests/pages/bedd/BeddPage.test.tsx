import { describe, expect, it } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { ConfigProvider } from 'antd';

import { BeddPage } from '../../../src/pages/bedd/BeddPage';
import type { BeddSection } from '../../../src/types/pms';

function renderPage(sections: BeddSection[]) {
  return render(
    <ConfigProvider>
      <BeddPage sections={sections} />
    </ConfigProvider>,
  );
}

const SAMPLE: BeddSection[] = [
  {
    section_id: 's1',
    title: '设计基础',
    content: '设计压力 0.5 MPaG',
    sign_status: 'CHECKED',
    signatures: [
      { step_index: 1, signer: '张三', signed_at: '2026-09-01' },
      { step_index: 2, signer: '李四', signed_at: '2026-09-05' },
    ],
  },
  {
    section_id: 's2',
    title: '材料选用',
    content: 'A106 Gr.B',
    sign_status: 'IN_APPROVAL',
  },
];

describe('BeddPage', () => {
  it('renders page header and section list', () => {
    renderPage(SAMPLE);
    expect(screen.getByTestId('bedd-page')).toBeInTheDocument();
    expect(screen.getByText('BEDD 文档')).toBeInTheDocument();
    expect(screen.getByTestId('bedd-section-list')).toBeInTheDocument();
  });

  it('shows section count in card title', () => {
    renderPage(SAMPLE);
    expect(screen.getByText('章节 (2)')).toBeInTheDocument();
  });

  it('selects first section by default and shows its content', () => {
    renderPage(SAMPLE);
    const content = screen.getByTestId('bedd-content');
    expect(content.textContent).toContain('设计基础');
    expect(content.textContent).toContain('设计压力 0.5 MPaG');
  });

  it('switches active section on click', () => {
    renderPage(SAMPLE);
    const items = screen.getAllByTestId('bedd-section-item');
    fireEvent.click(items[1]);
    expect(screen.getByTestId('bedd-content').textContent).toContain('材料选用');
  });

  it('shows signatures card with signers', () => {
    renderPage(SAMPLE);
    const sig = screen.getByTestId('bedd-signatures');
    expect(sig.textContent).toContain('张三');
    expect(sig.textContent).toContain('李四');
    expect(sig.textContent).toContain('2026-09-01');
  });

  it('shows fallback when section has no signatures', () => {
    const single: BeddSection[] = [SAMPLE[1]];
    renderPage(single);
    expect(screen.getByTestId('bedd-signatures').textContent).toContain('暂无签名');
  });

  it('shows empty state when no sections', () => {
    renderPage([]);
    expect(screen.getByText('无章节')).toBeInTheDocument();
    expect(screen.getByText('请选择左侧章节')).toBeInTheDocument();
  });

  it('renders section items with data-section-id', () => {
    renderPage(SAMPLE);
    const items = screen.getAllByTestId('bedd-section-item');
    expect(items[0]).toHaveAttribute('data-section-id', 's1');
    expect(items[1]).toHaveAttribute('data-section-id', 's2');
  });

  it('highlights active section title with bold', () => {
    renderPage(SAMPLE);
    const items = screen.getAllByTestId('bedd-section-item');
    const firstTitleSpan = items[0].querySelector('span')!;
    expect(firstTitleSpan.style.fontWeight).toBe('600');
  });
});