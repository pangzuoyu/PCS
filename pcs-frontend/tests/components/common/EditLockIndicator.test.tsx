/**
 * EditLockIndicator 的守卫（P9B-1 Task T2 · SPEC §6.21 P9A-LCK-003）。
 *
 * ## 这组测试抓的是「禁用原因写错」
 *
 * ⚠️ **他人持锁**时，禁用原因必须写「**谁在改**」，**不写「无权限」** ——
 * 这是并发提示，不是权限问题（把两者混同会让用户去找管理员，
 * 而真正该做的是**等一下**）。
 *
 * ⚠️ holder 取**后端原文**，前端不猜、不缓存。
 */
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';

import { EditLockIndicator } from '../../../src/components/common/EditLockIndicator';
import type { EditLockState } from '../../../src/hooks/useEditLock';

const HOLDER = {
  user_id: '99999999-8888-7777-6666-555555555555',
  acquired_at: '2026-10-20T10:22:31+08:00',
  username: '张三',
};

describe('EditLockIndicator —— 锁状态提示', () => {
  it('他人持锁 ⇒ 显示「谁在改」+ 相对时间，**不写「无权限」**（RF-3）', () => {
    const state: EditLockState = { status: 'blocked', holder: HOLDER };
    render(<EditLockIndicator state={state} />);

    const el = screen.getByTestId('edit-lock-indicator');
    expect(el.textContent).toContain('张三');
    expect(el.textContent).toContain('正在编辑');
    expect(el.textContent).not.toContain('无权限');
    expect(el.textContent).not.toContain('没有权限');
  });

  it('holder 没有 username ⇒ 回落到 user_id（后端原文，不猜）', () => {
    const state: EditLockState = {
      status: 'blocked',
      holder: { user_id: 'u-123', acquired_at: '2026-10-20T10:22:31+08:00' },
    };
    render(<EditLockIndicator state={state} />);
    expect(screen.getByTestId('edit-lock-indicator').textContent).toContain('u-123');
  });

  it('锁失效 ⇒ 「编辑锁已失效，请重新进入编辑」', () => {
    const state: EditLockState = { status: 'expired' };
    render(<EditLockIndicator state={state} />);
    expect(screen.getByTestId('edit-lock-indicator').textContent).toContain(
      '编辑锁已失效',
    );
  });

  it('held / degraded / idle ⇒ **不渲染**（降级横幅在顶栏，不在这里）', () => {
    for (const state of [
      { status: 'held', ttlSeconds: 1800 },
      { status: 'degraded', message: '锁服务不可用' },
      { status: 'idle' },
    ] as EditLockState[]) {
      const { container } = render(<EditLockIndicator state={state} />);
      expect(container.querySelector('[data-testid="edit-lock-indicator"]')).toBeNull();
    }
  });
});
