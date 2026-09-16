import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, within } from '@testing-library/react';
import { ConfigProvider } from 'antd';

import { PmsPage } from '../../../src/pages/pms/PmsPage';
import type { PmsItem } from '../../../src/types/pms';

function renderPage(items: PmsItem[], onSelect?: (i: PmsItem) => void) {
  return render(
    <ConfigProvider>
      <PmsPage items={items} onSelect={onSelect} />
    </ConfigProvider>,
  );
}

const SAMPLE: PmsItem[] = [
  {
    item_id: 'i1',
    pms_no: 'PMS-001',
    description: '碳钢 A106',
    pms_class: 'CL1',
    hazard_level: 'HIGH',
    sign_status: 'CHECKED',
  },
  {
    item_id: 'i2',
    pms_no: 'PMS-002',
    description: '不锈钢 304',
    pms_class: 'CL2',
    hazard_level: 'MEDIUM',
    sign_status: 'IN_APPROVAL',
  },
  {
    item_id: 'i3',
    pms_no: 'PMS-003',
    description: '铝',
    pms_class: 'CL3',
    hazard_level: 'LOW',
    sign_status: 'DRAFT',
  },
];

describe('PmsPage', () => {
  it('renders title and all items by default', () => {
    renderPage(SAMPLE);
    expect(screen.getByTestId('pms-page')).toBeInTheDocument();
    expect(screen.getByText('PMS 管道材料规格')).toBeInTheDocument();
    expect(screen.getByTestId('pms-count')).toHaveTextContent('3');
    const rows = screen.getAllByTestId('pms-row');
    expect(rows).toHaveLength(3);
  });

  it('shows hazard tag colors per level', () => {
    renderPage(SAMPLE);
    const hazards = screen.getAllByTestId('pms-hazard');
    expect(hazards[0]).toHaveTextContent('高');
    expect(hazards[1]).toHaveTextContent('中');
    expect(hazards[2]).toHaveTextContent('低');
  });

  it('filters by HIGH when HIGH segmented selected', () => {
    renderPage(SAMPLE);
    const seg = screen.getByTestId('pms-hazard-filter');
    fireEvent.click(within(seg).getByText('HIGH'));
    expect(screen.getByTestId('pms-count')).toHaveTextContent('1');
    expect(screen.getAllByTestId('pms-row')).toHaveLength(1);
  });

  it('filters by LOW', () => {
    renderPage(SAMPLE);
    const seg = screen.getByTestId('pms-hazard-filter');
    fireEvent.click(within(seg).getByText('LOW'));
    expect(screen.getByTestId('pms-count')).toHaveTextContent('1');
  });

  it('returns to all when ALL selected', () => {
    renderPage(SAMPLE);
    const seg = screen.getByTestId('pms-hazard-filter');
    fireEvent.click(within(seg).getByText('HIGH'));
    fireEvent.click(within(seg).getByText('全部'));
    expect(screen.getByTestId('pms-count')).toHaveTextContent('3');
  });

  it('calls onSelect with clicked row', () => {
    const onSelect = vi.fn();
    renderPage(SAMPLE, onSelect);
    const rows = screen.getAllByTestId('pms-row');
    fireEvent.click(rows[0]);
    expect(onSelect).toHaveBeenCalledTimes(1);
    expect(onSelect.mock.calls[0][0].pms_no).toBe('PMS-001');
  });

  it('handles empty items list', () => {
    renderPage([]);
    expect(screen.getByTestId('pms-count')).toHaveTextContent('0');
    expect(screen.queryAllByTestId('pms-row')).toHaveLength(0);
  });

  it('renders pms_no in monospace font', () => {
    renderPage(SAMPLE);
    const firstRow = screen.getAllByTestId('pms-row')[0];
    expect(firstRow).toHaveAttribute('data-pms-no', 'PMS-001');
  });
});