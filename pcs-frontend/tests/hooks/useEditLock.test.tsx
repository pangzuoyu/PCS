/**
 * 编辑锁 hook 的守卫（P9B-1 Task T2 · SPEC §6.21 P9A-LCK-001~005）。
 *
 * ## 这组测试抓的是四个失败模式
 *
 * | 失败模式 | 期望 |
 * |---|---|
 * | **RF-4** 续期 409 ⇒ 自动重试 | **不重试**（重试仍是 409，且把「锁已失效」掩盖成「网络抖动」）⇒ 表单转只读 |
 * | **RF-3** 他人持锁 ⇒ 误写成「无权限」 | `blocked` + **holder 取后端原文**，只禁保存 |
 * | **RF-6** Redis 降级 ⇒ 横幅**阻断**编辑 | 降级**放行**（拦并发的是 DB 层的 hash 比对，不是锁） |
 * | **GAP** `enabled=false` 仍取锁 | **不请求 acquire**（抽屉没打开就不该占锁） |
 *
 * ⚠️ 续期用**假定时器**（60s）—— 真等 60s 的测试没有意义。
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';

import { useEditLock } from '../../src/hooks/useEditLock';
import { editLockApi } from '../../src/api/locks';

const RECORD_ID = '11111111-2222-3333-4444-555555555555';

const HOLDER = {
  user_id: '99999999-8888-7777-6666-555555555555',
  acquired_at: '2026-10-20T10:22:31+08:00',
  username: '张三',
};

function lockResponse(overrides: Record<string, unknown> = {}) {
  return {
    record_type: 'CostEstResult',
    record_id: RECORD_ID,
    operation: 'acquire',
    success: true,
    holder: HOLDER,
    ttl_seconds: 1800,
    degraded: false,
    message: null,
    ...overrides,
  };
}

/**
 * 推进微任务队列（等 acquire 的 promise 落地）。
 *
 * ⚠️ **不能��� testing-library 的轮询等待**：假定时器下它会**自己推进时钟**
 * （内部轮询）⇒ 60s 的心跳会被提前触发 ⇒「续期只调一次」这类断言会被
 * 假时钟污染。
 */
async function flush(): Promise<void> {
  await act(async () => {
    await Promise.resolve();
  });
}

describe('useEditLock —— 取锁 / 心跳 / 只读化', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.restoreAllMocks();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('取锁成功后进入 held，readOnly=false', async () => {
    const acquire = vi
      .spyOn(editLockApi, 'acquire')
      .mockResolvedValue(lockResponse() as never);
    const renew = vi.spyOn(editLockApi, 'renew').mockResolvedValue(lockResponse() as never);

    const { result } = renderHook(() =>
      useEditLock({
        recordType: 'CostEstResult',
        recordId: RECORD_ID,
        enabled: true,
      }),
    );

    await flush();
    expect(result.current.state.status).toBe('held');
    expect(result.current.readOnly).toBe(false);
    expect(acquire).toHaveBeenCalledTimes(1);
    expect(renew).not.toHaveBeenCalled();
  });

  it('⚠️ enabled=false ⇒ **不取锁**（不请求 acquire）', async () => {
    const acquire = vi
      .spyOn(editLockApi, 'acquire')
      .mockResolvedValue(lockResponse() as never);

    const { result } = renderHook(() =>
      useEditLock({
        recordType: 'CostEstResult',
        recordId: RECORD_ID,
        enabled: false,
      }),
    );

    await act(async () => {
      await Promise.resolve();
    });
    expect(acquire).not.toHaveBeenCalled();
    expect(result.current.state.status).toBe('idle');
    expect(result.current.readOnly).toBe(false);
  });

  it('取锁 409（他人持锁）⇒ blocked + readOnly，holder 取后端原文（RF-3）', async () => {
    vi.spyOn(editLockApi, 'acquire').mockResolvedValue(
      lockResponse({ success: false, holder: HOLDER }) as never,
    );
    const renew = vi.spyOn(editLockApi, 'renew').mockResolvedValue(lockResponse() as never);

    const { result } = renderHook(() =>
      useEditLock({
        recordType: 'CostEstResult',
        recordId: RECORD_ID,
        enabled: true,
      }),
    );

    await flush();
    expect(result.current.state.status).toBe('blocked');
    expect(result.current.readOnly).toBe(true);
    if (result.current.state.status === 'blocked') {
      expect(result.current.state.holder?.username).toBe('张三');
    }
    // ⚠️ 没拿到锁就**不该**起心跳（起了也只会 409 ⇒ 把「他人持锁」冲成「锁失效」）
    expect(renew).not.toHaveBeenCalled();
  });

  it('⚠️ 续期 409 ⇒ 转只读，且**不重试**（RF-4）', async () => {
    vi.spyOn(editLockApi, 'acquire').mockResolvedValue(lockResponse() as never);
    const renew = vi
      .spyOn(editLockApi, 'renew')
      .mockResolvedValue(lockResponse({ success: false }) as never);

    const { result } = renderHook(() =>
      useEditLock({
        recordType: 'CostEstResult',
        recordId: RECORD_ID,
        enabled: true,
      }),
    );
    await flush();
    expect(result.current.state.status).toBe('held');

    await act(async () => {
      await vi.advanceTimersByTimeAsync(60_000);
    });
    expect(result.current.state.status).toBe('expired');
    expect(result.current.readOnly).toBe(true);

    // ⚠️ 再等两分钟 ⇒ 仍然**没有**第二次续期（不重试）
    await act(async () => {
      await vi.advanceTimersByTimeAsync(120_000);
    });
    expect(renew).toHaveBeenCalledTimes(1);
  });

  it('取锁成功后每 60s 续期一次', async () => {
    vi.spyOn(editLockApi, 'acquire').mockResolvedValue(lockResponse() as never);
    const renew = vi.spyOn(editLockApi, 'renew').mockResolvedValue(lockResponse() as never);

    renderHook(() =>
      useEditLock({
        recordType: 'CostEstResult',
        recordId: RECORD_ID,
        enabled: true,
      }),
    );
    await flush();
    expect(renew).not.toHaveBeenCalled();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(60_000);
    });
    expect(renew).toHaveBeenCalledTimes(1);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(60_000);
    });
    expect(renew).toHaveBeenCalledTimes(2);
  });

  it('⚠️ degraded=true ⇒ **可编辑**（体验层失效，不是保护层）（RF-6）', async () => {
    vi.spyOn(editLockApi, 'acquire').mockResolvedValue(
      lockResponse({ degraded: true, message: '锁服务不可用，保存时可能冲突' }) as never,
    );
    const onDegraded = vi.fn();

    const { result } = renderHook(() =>
      useEditLock({
        recordType: 'CostEstResult',
        recordId: RECORD_ID,
        enabled: true,
        onDegraded,
      }),
    );

    await flush();
    expect(result.current.state.status).toBe('degraded');
    expect(result.current.readOnly).toBe(false);
    // 降级横幅的文案取后端原文
    expect(onDegraded).toHaveBeenCalledWith('锁服务不可用，保存时可能冲突');
  });

  it('acquire 网络失败 ⇒ degraded（不崩、不阻塞编辑）', async () => {
    vi.spyOn(editLockApi, 'acquire').mockRejectedValue(new Error('network down'));

    const { result } = renderHook(() =>
      useEditLock({
        recordType: 'CostEstResult',
        recordId: RECORD_ID,
        enabled: true,
      }),
    );

    await flush();
    expect(result.current.state.status).toBe('degraded');
    expect(result.current.readOnly).toBe(false);
  });

  it('release 的所有错误一律忽略（best-effort：不弹窗、不阻断关闭）', async () => {
    vi.spyOn(editLockApi, 'acquire').mockResolvedValue(lockResponse() as never);
    vi.spyOn(editLockApi, 'release').mockRejectedValue(new Error('boom'));

    const { result } = renderHook(() =>
      useEditLock({
        recordType: 'CostEstResult',
        recordId: RECORD_ID,
        enabled: true,
      }),
    );
    await flush();
    expect(result.current.state.status).toBe('held');

    await expect(result.current.release()).resolves.toBeUndefined();
  });
});
