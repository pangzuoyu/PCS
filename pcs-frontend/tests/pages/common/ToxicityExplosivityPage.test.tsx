/**
 * ToxicityExplosivityPage 测试（P45-3-3 / Task 30）。
 */
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';

import { ToxicityExplosivityPage } from '../../../src/pages/common/ToxicityExplosivityPage';
import type { ToxicityClass } from '../../../src/types/common';

// ⚠️ 字段名对齐契约 `SafetyResult`（2026-10-19）。
// LD50 / PEL 已砍：后端 `_SAFETY_DATA` 每条只有 `{name, tox, lfl, ufl}`，
// 没有任何 LD50/PEL 数据，也没有对应的 DB 表（用户裁决：先查后端再决定）。
// 毒性等级改用后端 `tox` 的真实词表 —— 比旧的 HazardClass 多一个 `NONE`。
const classes: ToxicityClass[] = [
  { cas: '71-43-2',   name: 'Benzene',  toxicity_class: 'HIGH',   lel_vol_pct: 1.2, uel_vol_pct: 7.8 },
  { cas: '108-88-3',  name: 'Toluene',  toxicity_class: 'MEDIUM', lel_vol_pct: 1.1, uel_vol_pct: 7.1 },
  { cas: '67-56-1',   name: 'Methanol', toxicity_class: 'MEDIUM', lel_vol_pct: 6.0, uel_vol_pct: 36.5 },
  { cas: '7732-18-5', name: 'Water',    toxicity_class: 'NONE',   lel_vol_pct: null, uel_vol_pct: null },
];

describe('ToxicityExplosivityPage — 渲染 (P45-3-3)', () => {
  it('渲染 3 个毒性等级卡片（含后端的 NONE 档）', () => {
    render(<ToxicityExplosivityPage classes={classes} />);
    const cards = document.querySelectorAll('[data-testid="toxicity-card"]');
    expect(cards.length).toBe(3);
  });

  it('HIGH 卡片：只有 Benzene（Toluene 按后端 tox=MEDIUM 归到 MEDIUM 档）', () => {
    render(<ToxicityExplosivityPage classes={classes} />);
    const highCard = document.querySelector('[data-toxicity-class="HIGH"]');
    expect(highCard).toBeTruthy();
    expect(highCard!.textContent).toContain('Benzene');
    expect(highCard!.textContent).not.toContain('Toluene');
    const tags = highCard!.querySelectorAll('[data-testid="toxicity-tag"]');
    expect(tags.length).toBe(1);
  });

  it('MEDIUM 卡片：Methanol + Toluene，爆炸极限按契约的拍平字段显示', () => {
    render(<ToxicityExplosivityPage classes={classes} />);
    const medCard = document.querySelector('[data-toxicity-class="MEDIUM"]');
    expect(medCard!.textContent).toContain('Methanol');
    expect(medCard!.textContent).toContain('Toluene');
    expect(medCard!.textContent).toContain('6–36.5');
  });

  it('NONE 卡片：Water（后端 tox=NONE，旧的三档词表里没有这一档）', () => {
    render(<ToxicityExplosivityPage classes={classes} />);
    const noneCard = document.querySelector('[data-toxicity-class="NONE"]');
    expect(noneCard).toBeTruthy();
    expect(noneCard!.textContent).toContain('Water');
    // 无爆炸极限 → 「—」而不是 "null–null"
    expect(noneCard!.textContent).toContain('—');
  });

  it('显示标题「毒性爆炸分类」', () => {
    render(<ToxicityExplosivityPage classes={classes} />);
    expect(screen.getByTestId('toxicity-explosivity-page')).toBeTruthy();
  });
});