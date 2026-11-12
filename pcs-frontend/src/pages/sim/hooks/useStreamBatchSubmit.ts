/**
 * 批次「提交校对」的状态持有者（P9B-4 · TODO-116）。
 *
 * ## 为什么要有这个 hook（而不是继续用组件局部 state）
 *
 * P9B-3b 的 `batchResult` 是**组件局部 state** ⇒ 关闭摘要弹窗即丢 ⇒
 * 「50 条里 8 条失败，用户要重试得回列表逐条找」⇒ 批量操作最容易劝退人的
 * 地方就是「失败后要手动重来」。
 *
 * ⇒ 失败清单提升到 **hook**（页面唯一的消费者 ⇒ 不需要全局 store）。
 *
 * ## 重试语义（裁决）
 *
 * - **只重试上次的失败项** —— 成功的那些已经提交过了，重发是浪费。
 * - 重试后**失败清单替换**为本次重试的失败清单（最可预测的语义：
 *   「上次失败、这次不再失败」的条目从清单里消失）。
 * - ⚠️ **不需要**后端区分「我重试成功的」与「被别人抢跑的」——
 *   摘要里已有一行「其中 M 条本来就在审批中（幂等命中 · 本次未提交）」
 *   （TODO-124）⇒ 幂等命中会**如实显示** ⇒ 用户不会误以为是自己重试生效的。
 *
 * ## 错误处理（**两个错误域**，评审 #20）
 *
 * ⚠️ **批次提交失败**（网络 / 超限 / 403）⇒ **抛给调用方** ⇒ 页面负责显示
 * （错误文案是页面的事：403 要说「无权**提交**」而不是「无权查看」）。
 * ⇒ hook 只管状态，**不吞异常**。
 *
 * ⚠️ **刷新列表失败**（`onDone`）⇒ **吞掉**：提交**已经成功**了 ⇒ 刷新失败
 * **不是**「提交失败」⇒ 不能清掉刚收到的摘要、也不能 rethrow（否则页面会说
 * 「批量提交校对失败」，而那批其实已经提交成功）。
 *
 * ## 已知限制
 *
 * ⚠️ 刷新页面会**丢失**失败清单（内存态，与本仓 auth store 同款取舍）⇒
 * UI 上如实提示。
 *
 * ⚠️ `onDone` = 刷新列表 ⇒ 重试后**列表内容可能变**（失败项可能已不在
 * 当前筛选结果里）⇒ 这是**期望**的（后端返回的是最新态）。
 * ⚠️ **不会「跳页」** —— 本仓物流列表 `pagination={false}`（无分页）⇒
 * 刷新不涉及页码。（若将来给列表加分页，此处要重新审视。）
 */
import { useCallback, useEffect, useRef, useState } from 'react';

import { streamApi, type StreamBatchSubmitResponse } from '../../../api/stream';

export interface UseStreamBatchSubmit {
  /** 最近一次批次的结果（弹窗用）；null = 还没提交过 / 已清除。 */
  result: StreamBatchSubmitResponse | null;
  /** 上一次**未解决**的失败条目 id（弹窗关闭后仍在 ⇒ 可重试）。 */
  failedIds: string[];
  /** 正在提交（禁用按钮，防重复）。 */
  submitting: boolean;
  /** 提交一批 id（含只重试失败项）。 */
  submit: (streamIds: string[]) => Promise<void>;
  /** **只重试**上次的失败项；没有失败项时是 no-op。 */
  retryFailed: () => Promise<void>;
  /** 关闭摘要弹窗（**不清**失败清单）。 */
  dismissResult: () => void;
  /** 彻底清除失败清单（用户显式点「清除」）。 */
  clearFailures: () => void;
}

export function useStreamBatchSubmit(options?: {
  /** 批次结束后刷新列表。 */
  onDone?: () => Promise<void> | void;
}): UseStreamBatchSubmit {
  const [result, setResult] = useState<StreamBatchSubmitResponse | null>(null);
  const [failedIds, setFailedIds] = useState<string[]>([]);
  const [submitting, setSubmitting] = useState(false);

  // ⚠️ `onDone` 走 ref ⇒ `submit` 的身份**稳定**（调用方多半传内联箭头
  //    ⇒ 放依赖里会让 `submit` 每次渲染都变）。
  const onDoneRef = useRef(options?.onDone);
  useEffect(() => {
    onDoneRef.current = options?.onDone;
  }, [options?.onDone]);

  const submit = useCallback(async (streamIds: string[]): Promise<void> => {
    setSubmitting(true);
    try {
      const res = await streamApi.batchSubmitForReview(streamIds);
      setResult(res);
      // ⚠️ 失败清单 = **本次**的失败条目（替换，不是追加）⇒
      //    「上次失败、这次不再失败」的条目从清单里消失。
      setFailedIds(res.failed.map((f) => f.stream_id));
    } catch (err) {
      // ⚠️ 整批失败 ⇒ 没有新摘要（留着旧的会**误导**用户）
      setResult(null);
      // ⚠️ **不吞异常** ⇒ 页面负责显示（403 要说「无权提交」）
      throw err;
    } finally {
      setSubmitting(false);
    }
    // ⚠️⚠️ **刷新列表是另一个错误域**（评审 #20）
    //    提交**已经成功**了（上面已 `setResult(res)`）⇒ 随后的刷新失败
    //    **不是**「提交失败」⇒ 不能清掉刚收到的摘要、也不能 rethrow
    //    （旧实现把刷新放在提交的同一个 try ⇒ 刷新一失败 ⇒ catch 清摘要 +
    //    rethrow ⇒ 页面显示「批量提交校对失败」⇒ 而那批**其实已经提交成功**）。
    try {
      await onDoneRef.current?.();
    } catch {
      // ⚠️ **吞掉**：刷新失败不该改写「提交成功」这个事实。
      //    列表刷新不出来 ⇒ 用户看到的还是**旧列表** ⇒ 但摘要（弹窗）里
      //    写着一模一样的结果 ⇒ 不算误导。
    }
  }, []);

  const retryFailed = useCallback(async (): Promise<void> => {
    // ⚠️ 没有失败项 ⇒ **不发请求**（不打扰后端）
    if (failedIds.length === 0) return;
    await submit(failedIds);
  }, [failedIds, submit]);

  const dismissResult = useCallback(() => setResult(null), []);
  const clearFailures = useCallback(() => setFailedIds([]), []);

  return {
    result,
    failedIds,
    submitting,
    submit,
    retryFailed,
    dismissResult,
    clearFailures,
  };
}

export default useStreamBatchSubmit;
