/**
 * StateBadge 测试（P45-1-1 / Task 6）。
 *
 * 覆盖（plan Step 2）：
 * - 9 态渲染（每个状态 1 例）
 * - P3 模块（SIM）只显 4 态 active（其他 opacity 0.4）
 * - IN_APPROVAL + showStep 显示 "Step N/3"
 * - 颜色取自 tokens.css（断言 inline style 含 `var(--state-<kebab>)`；
 *   jsdom 不解析 CSS var，所以走 inline style 字符串 + data-* 属性断言）
 * - size sm/md 字号差异
 * - showIcon 占位字符
 * - depth v0.2 占位（不渲染）
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen } from '@testing-library/react';

import {
  StateBadge,
  StateBadge as Badge,
  PIPE_CLASS_STATUSES,
} from '../../../src/components/common/StateBadge';
import type { RecordSignStatus } from '../../../src/types/records';

const ALL_NINE: RecordSignStatus[] = [
  'DRAFT', 'IN_APPROVAL', 'CHECKED', 'CHECK_REJECTED', 'STALE',
  'CHANGE_PENDING', 'CHANGED', 'REVERSAL_PENDING', 'OBSOLETE',
];

const FOUR_STATE: RecordSignStatus[] = [
  'DRAFT', 'IN_APPROVAL', 'CHECKED', 'CHECK_REJECTED',
];

describe('StateBadge — 9 态全集 (P45-1-1)', () => {
  it.each(ALL_NINE)('renders %s with token + bg + border', (status) => {
    render(<StateBadge status={status} />);
    const el = screen.getByTestId('state-badge');
    const kebab = status.toLowerCase().replace(/_/g, '-');
    expect(el.getAttribute('data-status')).toBe(status);
    expect(el.getAttribute('data-kebab')).toBe(kebab);
    const style = el.getAttribute('style') || '';
    expect(style).toContain(`var(--state-${kebab})`);
    expect(style).toContain(`var(--state-badge-bg-${status}`);
    expect(style).toContain(`var(--state-${kebab})`);
    expect(screen.getByTestId('state-badge-label').textContent).toBeTruthy();
  });
});

describe('StateBadge — 模块激活子集', () => {
  it('SIM module: 4 态 active + 5 态半透明', () => {
    for (const s of FOUR_STATE) {
      const { unmount } = render(<StateBadge status={s} module="SIM" />);
      const el = screen.getByTestId('state-badge');
      expect(el.getAttribute('data-active')).toBe('true');
      const style = el.getAttribute('style') || '';
      expect(style).toMatch(/opacity:\s*1\b/);
      unmount();
    }
    const inactive: RecordSignStatus[] = [
      'STALE', 'CHANGE_PENDING', 'CHANGED', 'REVERSAL_PENDING', 'OBSOLETE',
    ];
    for (const s of inactive) {
      const { unmount } = render(<StateBadge status={s} module="SIM" />);
      const el = screen.getByTestId('state-badge');
      expect(el.getAttribute('data-active')).toBe('false');
      const style = el.getAttribute('style') || '';
      expect(style).toMatch(/opacity:\s*0\.4/);
      unmount();
    }
  });

  it('PIPE/PUMP/PIPE_NET/FLASH 模块同样 4 态子集', () => {
    for (const mod of ['PIPE', 'PUMP', 'PIPE_NET', 'FLASH'] as const) {
      const { unmount } = render(<StateBadge status="STALE" module={mod} />);
      expect(screen.getByTestId('state-badge').getAttribute('data-active')).toBe('false');
      unmount();
    }
  });

  it('CONFIG/DELIVERABLE 模块 9 态全集 active', () => {
    for (const mod of ['CONFIG', 'DELIVERABLE'] as const) {
      for (const s of ['STALE', 'CHANGE_PENDING', 'CHANGED', 'REVERSAL_PENDING', 'OBSOLETE'] as const) {
        const { unmount } = render(<StateBadge status={s} module={mod} />);
        expect(screen.getByTestId('state-badge').getAttribute('data-active')).toBe('true');
        unmount();
      }
    }
  });

  it('HEAT 模块 4 态子集（P5-4 frontend / Task 3）：DRAFT/IN_APPROVAL/CHECKED/CHECK_REJECTED active，其余半透明', () => {
    const active: Array<RecordSignStatus> = ['DRAFT', 'IN_APPROVAL', 'CHECKED', 'CHECK_REJECTED'];
    const inactive: Array<RecordSignStatus> = ['STALE', 'CHANGE_PENDING', 'CHANGED', 'REVERSAL_PENDING', 'OBSOLETE'];

    for (const s of active) {
      const { unmount } = render(<StateBadge status={s} module="HEAT" />);
      const el = screen.getByTestId('state-badge');
      expect(el.getAttribute('data-module')).toBe('HEAT');
      expect(el.getAttribute('data-active')).toBe('true');
      const style = el.getAttribute('style') || '';
      expect(style).not.toMatch(/opacity:\s*0\.4/);
      unmount();
    }

    for (const s of inactive) {
      const { unmount } = render(<StateBadge status={s} module="HEAT" />);
      const el = screen.getByTestId('state-badge');
      expect(el.getAttribute('data-active')).toBe('false');
      const style = el.getAttribute('style') || '';
      expect(style).toMatch(/opacity:\s*0\.4/);
      unmount();
    }
  });
});

describe('StateBadge — showStep', () => {
  it('IN_APPROVAL + showStep + step=2 显示 "Step 2/3"', () => {
    render(<StateBadge status="IN_APPROVAL" showStep step={2} />);
    expect(screen.getByTestId('state-badge-label').textContent).toContain('Step 2/3');
  });

  it('IN_APPROVAL + showStep 无 step → 默认 Step 1/3', () => {
    render(<StateBadge status="IN_APPROVAL" showStep />);
    expect(screen.getByTestId('state-badge-label').textContent).toContain('Step 1/3');
  });

  it('CHECKED + showStep 不显示 Step 后缀（非 IN_APPROVAL）', () => {
    render(<StateBadge status="CHECKED" showStep step={2} />);
    expect(screen.getByTestId('state-badge-label').textContent).not.toContain('Step');
  });
});

describe('StateBadge — size / icon / depth', () => {
  it('size=sm → 11px', () => {
    render(<StateBadge status="DRAFT" size="sm" />);
    const style = screen.getByTestId('state-badge').getAttribute('style') || '';
    expect(style).toMatch(/font-size:\s*11px/);
  });

  it('size=md → 12px', () => {
    render(<StateBadge status="DRAFT" size="md" />);
    const style = screen.getByTestId('state-badge').getAttribute('style') || '';
    expect(style).toMatch(/font-size:\s*12px/);
  });

  it('showIcon 渲染占位字符', () => {
    render(<StateBadge status="DRAFT" showIcon />);
    expect(screen.getByTestId('state-badge-icon').textContent).toBe('✎');
  });

  it('depth 接受但不渲染（v0.2 占位）', () => {
    const { container } = render(<StateBadge status="DRAFT" depth={3} />);
    expect(container.querySelector('[data-depth]')).toBeNull();
  });
});
/**
 * PIPE_CLASS 独立词表 + 显式兜底（2026-10-19，bug-180 第二症状）。
 *
 * ## 为什么要独立一个 module 而不是往 PIPE 里加 ACTIVE
 *
 * 两套生命周期不同：PIPE 走签署（4 态强调 + 9 态全集），
 * 管子等级走自己的发布态（DRAFT / ACTIVE / OBSOLETE）。
 * 塞进 PIPE 会让 `module="PIPE"` 同时接受 `ACTIVE`（非法）
 * 和 `module="PIPE_CLASS"` 接受 `CHECKED`（非法）—— 类型系统失去保护。
 *
 * ## 兜底为什么必须改
 *
 * 旧代码 `STATUS_META[status] ?? STATUS_META.DRAFT`：
 * 一个**已生效**的管子等级落进去会显示「草稿」。用户不会报 bug
 * （他不知道本该显示什么），他会基于错误信息做决策
 * ——「这个等级还没生效，不能用于设计」。这是数据语义被静默改写，
 * 与 `definitionBody.ts` 给缺 source 的条件伪造 'EQUIP_LIST' 同族。
 */

describe('StateBadge — PIPE_CLASS 独立词表', () => {
  it.each(PIPE_CLASS_STATUSES)('renders %s with its own label', (status) => {
    render(<Badge module="PIPE_CLASS" status={status} />);
    const el = screen.getByTestId('state-badge');
    expect(el.getAttribute('data-status')).toBe(status);
    expect(el.getAttribute('data-module')).toBe('PIPE_CLASS');
    expect(screen.getByTestId('state-badge-label').textContent).toBeTruthy();
  });

  it('五态都有中文文案（bug-187：曾漏 3 态 → 生产显示「未知状态」）', () => {
    for (const s of PIPE_CLASS_STATUSES) {
      const { unmount } = render(<Badge module="PIPE_CLASS" status={s} />);
      const label = screen.getByTestId('state-badge-label').textContent ?? '';
      expect(label, `${s} 不能是空标签`).not.toBe('');
      expect(label, `${s} 不能落进未知兜底`).not.toMatch(/未知状态/);
      unmount();
    }
  });

  it('五态都是 active（不像签署模块那样半透明）', () => {
    for (const s of PIPE_CLASS_STATUSES) {
      const { unmount } = render(<Badge module="PIPE_CLASS" status={s} />);
      const el = screen.getByTestId('state-badge');
      expect(el.getAttribute('data-active')).toBe('true');
      expect(el.getAttribute('style') || '').toMatch(/opacity:\s*1\b/);
      unmount();
    }
  });

  it('OBSOLETE 与签署模块共用「已弃用」——不为管子等级另建一份标签表', () => {
    // DRAFT/OBSOLETE 是通用生命周期词，语义一致 ⇒ 共用。
    // 只有 ACTIVE 必须分开：「已核验」（计算已校核）≠「已生效」（已发布可引用）。
    // 另建第二份标签表就是「第二个真相源」——将来加态要改两处。
    render(<Badge module="PIPE_CLASS" status="OBSOLETE" />);
    expect(screen.getByTestId('state-badge-label').textContent).toBe('已弃用');
  });
});

describe('StateBadge — 未知状态不得静默兜底（bug-180）', () => {
  // 类型层（判别联合）拦得住**字面量**，拦不住**后端返回的裸 string**
  // —— 契约 `PipeClassResponse.status` 没写 Literal。所以运行时这层必须有。
  const raw = 'SOMETHING_NEW' as never;

  it('DEV 下**抛错**，而不是渲染出某个状态', () => {
    // 旧实现 `?? STATUS_META.DRAFT` 在这里静默显示「草稿」。
    // 让问题第一次出现时就炸，而不是等用户拿错误信息做决策。
    expect(() => render(<Badge module="PIPE_CLASS" status={raw} />))
      .toThrow(/未知状态/);
  });

  describe('PROD 下显形而不是猜测', () => {
    beforeEach(() => { vi.stubEnv('DEV', false); });
    afterEach(() => { vi.unstubAllEnvs(); });

    it('渲染出「未知状态: <值>」', () => {
      render(<Badge module="PIPE_CLASS" status={raw} />);
      const label = screen.getByTestId('state-badge-label').textContent ?? '';
      expect(label).toContain('未知状态');
      expect(label).toContain('SOMETHING_NEW');
      expect(label).not.toBe('草稿');
    });

    it('data-status 保留原值，便于定位', () => {
      render(<Badge module="PIPE_CLASS" status={raw} />);
      expect(screen.getByTestId('state-badge').getAttribute('data-status'))
        .toBe('SOMETHING_NEW');
    });

    it('data-known=false —— 可辨，不伪装成正常态', () => {
      render(<Badge module="PIPE_CLASS" status={raw} />);
      expect(screen.getByTestId('state-badge').getAttribute('data-known')).toBe('false');
    });
  });
});
