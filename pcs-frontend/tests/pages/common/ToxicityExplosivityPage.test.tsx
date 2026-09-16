/**
 * ToxicityExplosivityPage 测试（P45-3-3 / Task 30）。
 */
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';

import { ToxicityExplosivityPage } from '../../../src/pages/common/ToxicityExplosivityPage';
import type { ToxicityClass } from '../../../src/types/common';

const classes: ToxicityClass[] = [
  { component_id: 'c-1', name: 'Benzene',   hazard_class: 'HIGH', ld50_mg_kg: 930,   pel_ppm: 1,   explosive_limit_json: { lel: 1.2, uel: 7.8 } },
  { component_id: 'c-2', name: 'Toluene',   hazard_class: 'HIGH', ld50_mg_kg: 636,   pel_ppm: 50,  explosive_limit_json: { lel: 1.1, uel: 7.1 } },
  { component_id: 'c-3', name: 'Methanol',  hazard_class: 'MEDIUM', ld50_mg_kg: 5628, pel_ppm: 200, explosive_limit_json: { lel: 6.0, uel: 36.5 } },
  { component_id: 'c-4', name: 'Water',     hazard_class: 'LOW' },
];

describe('ToxicityExplosivityPage — 渲染 (P45-3-3)', () => {
  it('渲染 3 个危险等级卡片', () => {
    render(<ToxicityExplosivityPage classes={classes} />);
    const cards = document.querySelectorAll('[data-testid="hazard-card"]');
    expect(cards.length).toBe(3);
  });

  it('HIGH 卡片包含 2 项（Benzene + Toluene）', () => {
    render(<ToxicityExplosivityPage classes={classes} />);
    const highCard = document.querySelector('[data-hazard-class="HIGH"]');
    expect(highCard).toBeTruthy();
    expect(highCard!.textContent).toContain('Benzene');
    expect(highCard!.textContent).toContain('Toluene');
    const tags = highCard!.querySelectorAll('[data-testid="hazard-tag"]');
    expect(tags.length).toBe(2);
  });

  it('MEDIUM 卡片：Methanol + 爆炸极限显示', () => {
    render(<ToxicityExplosivityPage classes={classes} />);
    const medCard = document.querySelector('[data-hazard-class="MEDIUM"]');
    expect(medCard!.textContent).toContain('Methanol');
    expect(medCard!.textContent).toContain('6–36.5');
  });

  it('LOW 卡片：Water 显示', () => {
    render(<ToxicityExplosivityPage classes={classes} />);
    const lowCard = document.querySelector('[data-hazard-class="LOW"]');
    expect(lowCard!.textContent).toContain('Water');
  });

  it('显示标题「毒性爆炸分类」', () => {
    render(<ToxicityExplosivityPage classes={classes} />);
    expect(screen.getByTestId('toxicity-explosivity-page')).toBeTruthy();
  });
});