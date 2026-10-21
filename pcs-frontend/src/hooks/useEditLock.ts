/**
 * 编辑锁 hook（P9B-1 · SPEC §6.21 P9A-LCK-001~005 · ADR-0048）。
 *
 * ## 锁是**体验层**，不是保护层
 *
 * 「我拿到了锁」**不等于**「保存一定成功」——保存冲突由后端的 `record_hash`
 * 比对裁定（那才是保护层）。锁只解决「谁在改」这个**体验**问题。
 * ⇒ Redis 挂 ⇒ 降级**放行** + 顶栏横幅，**不阻断**编辑。
 *
 * ## 60s 心跳
 *
 * 拿到锁后每 60s 续期一次。⚠️ **续期失败不重试**（RF-4）：重试仍是 409，
 * 且会把「锁已失效」这个事实掩盖成「网络抖动」⇒ 转只读并提示
 * 「编辑锁已失效，请重新进入编辑」。
 */
import { useCallback, useEffect, useRef, useState } from 'react';

import { editLockApi, type LockHolderResponse } from '../api/locks';
import type { EditableRecordType } from '../api/records';

export type EditLockState =
  | { status: 'idle' }
  | { status: 'held'; ttlSeconds: number }
  | { status: 'blocked'; holder: LockHolderResponse | null }
  | { status: 'expired' }
  | { status: 'degraded'; message: string | null };

/** 心跳间隔（SPEC §6.21 P9A-LCK-002）。 */
const RENEW_INTERVAL_MS = 60_000;

export interface UseEditLockArgs {
  recordType: EditableRecordType;
  recordId: string;
  /** 抽屉是否打开（关着就不该占锁）。 */
  enabled: boolean;
  /** 降级回调（顶栏横幅用；文案取后端原文）。 */
  onDegraded?: (message: string | null) => void;
}

export interface UseEditLockResult {
  state: EditLockState;
  /**
   * 是否只读。
   *
   * ⚠️ **只禁保存，不禁浏览**（SPEC §6.21 P9A-LCK-003）：复制 / 查看哈希
   * 都必须照常可用 —— 他人持锁是**并发提示**，不是权限问题。
   */
  readOnly: boolean;
  /**
   * 释放锁（best-effort）。
   *
   * ⚠️ **所有错误一律忽略**（409 / 403 / 404 / 500 / 网络错误）——
   * 不弹窗、不阻断关闭流程；锁靠 30min TTL 回收。
   */
  release: () => Promise<void>;
}

export function useEditLock({
  recordType,
  recordId,
  enabled,
  onDegraded,
}: UseEditLockArgs): UseEditLockResult {
  const [state, setState] = useState<EditLockState>({ status: 'idle' });
  // ⚠️ `onDegraded` 放 ref：它常是父组件的 inline 回调，
  // 若进依赖数组 ⇒ 每次渲染都重跑 effect ⇒ **反复取锁**。
  const degradedRef = useRef(onDegraded);
  degradedRef.current = onDegraded;

  useEffect(() => {
    if (!enabled) return;
    let cancelled = false;
    let timer: ReturnType<typeof setInterval> | null = null;
    // ⚠️ 「我们**确实**持锁」的标志 —— 卸载时据此决定要不要释放。
    // ⚠️ **即使 `cancelled` 也要置位**：StrictMode 的 cleanup 会在 acquire
    // 落地**之前**跑（那时还没持锁 ⇒ 不能释放，否则会与随后的 acquire 抢跑）；
    // 但 acquire 落地后我们**确实**持锁 ⇒ 最终卸载时必须释放。
    let held = false;

    const stopRenew = () => {
      if (timer !== null) {
        clearInterval(timer);
        timer = null;
      }
    };

    const startRenew = () => {
      stopRenew();
      timer = setInterval(() => {
        void editLockApi.renew(recordType, recordId).then((res) => {
          if (cancelled) return;
          // ⚠️ 续期失败 ⇒ 锁已失效（被抢走或已过期）⇒ 转只读，**不重试**。
          // ⚠️ **必须停掉心跳**：继续每 60s 续期就是「自动重试」
          // （重试仍是 409，且把「失效」掩盖成「网络抖动」）。
          if (!res.success) {
            stopRenew();
            setState({ status: 'expired' });
            return;
          }
          if (res.degraded) {
            setState({ status: 'degraded', message: res.message ?? null });
            degradedRef.current?.(res.message ?? null);
          }
        }).catch(() => {
          // ⚠️ 网络错误同样视为「续期失败」⇒ 转只读（**不重试**）。
          if (!cancelled) {
            stopRenew();
            setState({ status: 'expired' });
          }
        });
      }, RENEW_INTERVAL_MS);
    };

    void editLockApi
      .acquire(recordType, recordId)
      .then((res) => {
        // ⚠️ 降级优先于「拿没拿到锁」：Redis 挂了 ⇒ 放行 + 横幅。
        if (res.degraded) {
          if (!cancelled) {
            setState({ status: 'degraded', message: res.message ?? null });
            degradedRef.current?.(res.message ?? null);
          }
          return;
        }
        if (!res.success) {
          // 他人持锁（409，响应体仍是 LockResponse，带 holder）。
          // ⚠️ **不起心跳**：我们没持锁 ⇒ 续期只会 409 ⇒ 把「他人持锁」
          // 冲成「锁已失效」（两种状态的用户可见文案完全不同）。
          if (!cancelled) setState({ status: 'blocked', holder: res.holder ?? null });
          return;
        }
        // ⚠️ **先记「持锁」，再看 cancelled**（见上面 `held` 的注释）。
        held = true;
        if (cancelled) return;
        setState({ status: 'held', ttlSeconds: res.ttl_seconds });
        startRenew();
      })
      .catch(() => {
        // ⚠️ 取锁请求本身失败（网络 / 500）⇒ 降级放行，**不崩、不阻塞编辑**。
        if (!cancelled) setState({ status: 'degraded', message: null });
      });

    return () => {
      cancelled = true;
      stopRenew();
      // ⚠️ **卸载也要释放锁**（RF-10）：SPA 导航（点菜单换页）会让抽屉**静默卸载**
      // ⇒ 只清心跳 ⇒ 锁白占 30min ⇒ 同事看到「张三 正在编辑」而张三 已走
      // （`pagehide` 只在**文档**卸载时触发，覆盖不到 SPA 路由切换）。
      //
      // ⚠️ 只在**确实持锁**时释放：没拿到锁时释放是空操作，而无条件释放会与
      // StrictMode 的「cleanup → 重新 acquire」抢跑（可能把刚拿到的锁放掉）。
      if (held) {
        held = false;
        void editLockApi.release(recordType, recordId).catch(() => {
          // best-effort：失败一律忽略（锁靠 30min TTL 回收）
        });
      }
    };
  }, [recordType, recordId, enabled]);

  const release = useCallback(async () => {
    try {
      await editLockApi.release(recordType, recordId);
    } catch {
      // ⚠️ best-effort：失败**一律忽略**（不弹窗、不阻断关闭流程）。
    }
  }, [recordType, recordId]);

  const readOnly = state.status === 'blocked' || state.status === 'expired';

  return { state, readOnly, release };
}
