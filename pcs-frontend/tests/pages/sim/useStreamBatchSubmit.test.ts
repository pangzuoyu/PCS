/**
 * 批次「提交校对」hook 的失败清单语义（P9B-4 · TODO-116）。
 *
 * ## 这个文件在钉什么
 *
 * P9B-3b 的 `batchResult` 是**组件局部 state** ⇒ 关闭摘要弹窗即丢 ⇒
 * 「50 条里 8 条失败，用户要重试得回列表逐条找」⇒ 批量操作最容易劝退人的
 * 地方就是「失败后要手动重来」。
 *
 * ⇒ 失败清单提升到 hook ⇒ 下面七条性质被钉住：
 *
 * | # | 性质 |
 * |---|---|
 * | 1 | 关闭摘要弹窗**不清**失败清单 |
 * | 2 | 「只重试失败项」**只发失败的那几条** |
 * | 3 | 重试后失败清单**替换**为本次重试的失败清单 |
 * | 4 | 重试全部成功 ⇒ 失败清单**清空** |
 * | 5 | 重试命中幂等 ⇒ 摘要**仍**显示「本来就在审批中」那行 |
 * | 6 | 重试成功 ⇒ 刷新列表（`onDone`）+ 失败清单清空 |
 * | 7 | 没有失败项时 `retryFailed()` 是 **no-op**（不发请求） |
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';

import { useStreamBatchSubmit } from '../../../src/pages/sim/hooks/useStreamBatchSubmit';
import { streamApi, type StreamBatchSubmitResponse } from '../../../src/api/stream';

const OK_ID = '11111111-1111-1111-1111-111111111111';
const BAD_ID = '22222222-2222-2222-2222-222222222222';
const BAD2_ID = '33333333-3333-3333-3333-333333333333';

function response(overrides: Partial<StreamBatchSubmitResponse> = {}): StreamBatchSubmitResponse {
  return {
    batch_id: '44444444-4444-4444-4444-444444444444',
    total: 1,
    succeeded: [],
    failed: [],
    dry_run: false,
    warning: null,
    ...overrides,
  };
}

/** 造一份「N 成功 + M 失败」的批次响应。 */
function mixed(okIds: string[], badIds: string[]): StreamBatchSubmitResponse {
  return response({
    total: okIds.length + badIds.length,
    succeeded: okIds.map((id) => ({
      status: 'succeeded' as const,
      stream_id: id,
      from_status: 'DRAFT' as const,
      to_status: 'IN_APPROVAL' as const,
      note: null,
    })),
    failed: badIds.map((id) => ({
      status: 'failed' as const,
      stream_id: id,
      reason: 'SIM_STREAM_NOT_FOUND',
      detail: null,
    })),
  });
}

describe('useStreamBatchSubmit —— 失败清单 / 只重试失败项（TODO-116）', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('失败清单在「关闭摘要弹窗」后仍然保留', async () => {
    const spy = vi.spyOn(streamApi, 'batchSubmitForReview');
    spy.mockResolvedValue(mixed([OK_ID], [BAD_ID]));
    const { result } = renderHook(() => useStreamBatchSubmit());

    await act(async () => {
      await result.current.submit([OK_ID, BAD_ID]);
    });
    expect(result.current.failedIds).toEqual([BAD_ID]);

    act(() => result.current.dismissResult());
    expect(result.current.result).toBeNull();
    // ⚠️ 关闭弹窗**不清**失败清单（这就是本任务存在的理由）
    expect(result.current.failedIds).toEqual([BAD_ID]);
  });

  it('「只重试失败项」**只发失败的那几条**（不发成功的）', async () => {
    const spy = vi.spyOn(streamApi, 'batchSubmitForReview');
    spy.mockResolvedValueOnce(mixed([OK_ID], [BAD_ID]));
    const { result } = renderHook(() => useStreamBatchSubmit());

    await act(async () => {
      await result.current.submit([OK_ID, BAD_ID]);
    });
    expect(spy).toHaveBeenCalledTimes(1);

    spy.mockResolvedValueOnce(mixed([BAD_ID], []));
    await act(async () => {
      await result.current.retryFailed();
    });

    // ⚠️ 第二次请求**只带失败的那条**（成功的已经提交过了 ⇒ 重发是浪费）
    expect(spy).toHaveBeenCalledTimes(2);
    expect(spy.mock.calls[1][0]).toEqual([BAD_ID]);
  });

  it('重试后失败清单**替换**为本次重试的失败清单', async () => {
    const spy = vi.spyOn(streamApi, 'batchSubmitForReview');
    spy.mockResolvedValueOnce(mixed([], [BAD_ID, BAD2_ID]));
    const { result } = renderHook(() => useStreamBatchSubmit());

    await act(async () => {
      await result.current.submit([BAD_ID, BAD2_ID]);
    });
    expect(result.current.failedIds).toEqual([BAD_ID, BAD2_ID]);

    // 重试：一条好了、一条仍失败
    spy.mockResolvedValueOnce(mixed([BAD_ID], [BAD2_ID]));
    await act(async () => {
      await result.current.retryFailed();
    });
    expect(result.current.failedIds).toEqual([BAD2_ID]);
  });

  it('重试全部成功 ⇒ 失败清单**清空**', async () => {
    const spy = vi.spyOn(streamApi, 'batchSubmitForReview');
    spy.mockResolvedValueOnce(mixed([], [BAD_ID]));
    const { result } = renderHook(() => useStreamBatchSubmit());

    await act(async () => {
      await result.current.submit([BAD_ID]);
    });
    expect(result.current.failedIds).toEqual([BAD_ID]);

    spy.mockResolvedValueOnce(mixed([BAD_ID], []));
    await act(async () => {
      await result.current.retryFailed();
    });
    expect(result.current.failedIds).toEqual([]);
  });

  it('重试命中幂等 ⇒ 摘要**仍**显示「本来就在审批中」那行', async () => {
    const spy = vi.spyOn(streamApi, 'batchSubmitForReview');
    spy.mockResolvedValueOnce(mixed([], [BAD_ID]));
    const { result } = renderHook(() => useStreamBatchSubmit());

    await act(async () => {
      await result.current.submit([BAD_ID]);
    });

    // ⚠️ 重试命中幂等：后端回 `note='already_in_approval'`（**并没有真的提交**）
    //    ⇒ 摘要必须**如实**显示它 ⇒ 否则用户以为是自己重试生效的。
    spy.mockResolvedValueOnce(
      response({
        total: 1,
        succeeded: [
          {
            status: 'succeeded',
            stream_id: BAD_ID,
            from_status: 'DRAFT',
            to_status: 'IN_APPROVAL',
            note: 'already_in_approval',
          },
        ],
        failed: [],
      }),
    );
    await act(async () => {
      await result.current.retryFailed();
    });

    expect(result.current.result?.succeeded.some((s) => s.note === 'already_in_approval')).toBe(true);
    // ⚠️ 幂等命中**不算**失败 ⇒ 失败清单清空（它没失败）
    expect(result.current.failedIds).toEqual([]);
  });

  it('重试成功后**刷新列表**且失败清单条**消失**', async () => {
    const spy = vi.spyOn(streamApi, 'batchSubmitForReview');
    spy.mockResolvedValueOnce(mixed([], [BAD_ID]));
    const onDone = vi.fn();
    const { result } = renderHook(() => useStreamBatchSubmit({ onDone }));

    await act(async () => {
      await result.current.submit([BAD_ID]);
    });
    expect(onDone).toHaveBeenCalledTimes(1);

    spy.mockResolvedValueOnce(mixed([BAD_ID], []));
    await act(async () => {
      await result.current.retryFailed();
    });
    // ⚠️ 批次结束后**再刷新一次**（重试也算一次批次）
    expect(onDone).toHaveBeenCalledTimes(2);
    expect(result.current.failedIds).toEqual([]);
  });

  it('没有失败项时 retryFailed() 是 no-op（不发请求）', async () => {
    const spy = vi.spyOn(streamApi, 'batchSubmitForReview');
    spy.mockResolvedValue(mixed([OK_ID], []));
    const { result } = renderHook(() => useStreamBatchSubmit());

    await act(async () => {
      await result.current.submit([OK_ID]);
    });
    expect(spy).toHaveBeenCalledTimes(1);

    await act(async () => {
      await result.current.retryFailed();
    });
    // ⚠️ 没有失败项 ⇒ **不发请求**（不打扰后端）
    expect(spy).toHaveBeenCalledTimes(1);
  });

  it('clearFailures() 清空失败清单', async () => {
    const spy = vi.spyOn(streamApi, 'batchSubmitForReview');
    spy.mockResolvedValue(mixed([OK_ID], [BAD_ID]));
    const { result } = renderHook(() => useStreamBatchSubmit());

    await act(async () => {
      await result.current.submit([OK_ID, BAD_ID]);
    });
    expect(result.current.failedIds).toEqual([BAD_ID]);

    act(() => result.current.clearFailures());
    expect(result.current.failedIds).toEqual([]);
  });

  it('⚠️ 刷新列表失败 ⇒ **不算「提交失败」**（评审 #20）', async () => {
    // ⚠️ **提交已经成功了**（后端回了 207 + 摘要）⇒ 只是**随后的列表刷新**失败
    //    ⇒ 旧实现把 `onDone()` 放在**提交请求的同一个 try** 里
    //    ⇒ 刷新一失败 ⇒ catch 跑 `setResult(null)`（把刚收到的摘要关掉）
    //    ⇒ **再 rethrow** ⇒ 页面显示「批量提交校对失败」
    //    ⇒ 用户看到「失败」，实际那批**已经提交成功**（可能还提交了两次）。
    const spy = vi.spyOn(streamApi, 'batchSubmitForReview');
    spy.mockResolvedValue(mixed([OK_ID], []));
    const onDone = vi.fn().mockRejectedValue(new Error('refresh boom'));
    const { result } = renderHook(() => useStreamBatchSubmit({ onDone }));

    await act(async () => {
      // ⚠️ **不抛** —— 刷新失败不属于提交错误域
      await expect(result.current.submit([OK_ID])).resolves.toBeUndefined();
    });

    // ⚠️ 摘要**仍在**（不能被一次刷新失败抹掉）
    expect(result.current.result).not.toBeNull();
    expect(result.current.result?.succeeded.map((s) => s.stream_id)).toEqual([OK_ID]);
    expect(result.current.submitting).toBe(false);
  });

  it('整批失败（网络/超限/403）⇒ 错误**抛给调用方**（页面负责显示）', async () => {
    const spy = vi.spyOn(streamApi, 'batchSubmitForReview');
    spy.mockRejectedValue(new Error('boom'));
    const { result } = renderHook(() => useStreamBatchSubmit());

    await act(async () => {
      await expect(result.current.submit([OK_ID])).rejects.toThrow('boom');
    });
    // ⚠️ 失败 ⇒ 没有新摘要；`submitting` 必须**复位**（否则按钮永久禁用）
    expect(result.current.result).toBeNull();
    expect(result.current.submitting).toBe(false);
  });
});
