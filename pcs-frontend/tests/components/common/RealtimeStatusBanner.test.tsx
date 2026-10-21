/**
 * RealtimeStatusBanner 的守卫（P9B-1 Task T5 · SPEC §6.23）。
 *
 * ## 三条不能省的
 *
 * - ⚠️ **降级的是「及时性」，不是「可达性」** ⇒ 降级文案必须说
 *   「**仍可收到通知**」，且**不得**显示「通知已关闭」这类断言。
 * - ⚠️ **横幅不阻断任何操作**。
 * - ⚠️ `realtime_reason` 走**枚举映射**（`redis_unavailable` /
 *   `redis_timeout` / `pubsub_error`）⇒ 不把原始英文码当用户文案。
 */
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';

import { RealtimeStatusBanner } from '../../../src/components/common/RealtimeStatusBanner';

describe('RealtimeStatusBanner — 实时推送状态（SPEC §6.23）', () => {
  it('degraded ⇒ 文案含「仍可收到通知」且**不阻断**', () => {
    render(<RealtimeStatusBanner realtime="degraded" reason="redis_unavailable" />);
    const banner = screen.getByTestId('realtime-status-banner');
    expect(banner.textContent).toContain('仍可收到通知');
    // ⚠️ 不得说「通知已关闭」（降级的是及时性，不是可达性）
    expect(banner.textContent).not.toContain('已关闭');
  });

  it('realtime_reason 走**枚举映射**（不显示原始英文码当文案）', () => {
    render(<RealtimeStatusBanner realtime="degraded" reason="redis_unavailable" />);
    const banner = screen.getByTestId('realtime-status-banner');
    expect(banner.textContent).not.toContain('redis_unavailable');
  });

  it('reason 为 null ⇒ 仍给出一句可读文案（不显示 null / undefined）', () => {
    render(<RealtimeStatusBanner realtime="degraded" reason={null} />);
    const banner = screen.getByTestId('realtime-status-banner');
    expect(banner.textContent).not.toContain('null');
    expect(banner.textContent).not.toContain('undefined');
    expect(banner.textContent).toContain('仍可收到通知');
  });

  it('ok ⇒ **不渲染**横幅（没有降级就没有横幅）', () => {
    render(<RealtimeStatusBanner realtime="ok" reason={null} />);
    expect(screen.queryByTestId('realtime-status-banner')).toBeNull();
  });
});
