/**
 * 降级 store 的守卫（P9B-1 · T4 / T7 浏览器 QA 实测发现的 bug）。
 *
 * ## 曾经的 bug
 *
 * `create(() => ({ message: null, setMessage: () => {} }))` ⇒ `setMessage`
 * 是个**空函数** ⇒ 降级文案**永远存不进去** ⇒ 顶栏横幅**永远不出现**。
 *
 * ⚠️ **单测若直接 `setState({ message })` 会把这个 bug 彻底掩盖**
 * ⇒ 本文件**只走 `setMessage`** 这条路（生产代码用的正是它）。
 */
import { describe, it, expect, beforeEach } from 'vitest';

import { useDegradation } from '../../src/store/degradation';

describe('useDegradation —— 降级横幅的全局状态', () => {
  beforeEach(() => {
    useDegradation.setState({ message: null });
  });

  it('setMessage 真的写进状态（⛔ 曾经的空函数 bug）', () => {
    useDegradation.getState().setMessage('锁服务不可用，保存时可能冲突');
    expect(useDegradation.getState().message).toBe('锁服务不可用，保存时可能冲突');
  });

  it('setMessage(null) ⇒ 清空（横幅不渲染）', () => {
    useDegradation.getState().setMessage('降级');
    useDegradation.getState().setMessage(null);
    expect(useDegradation.getState().message).toBeNull();
  });

  it('组件订阅能收到变化（zustand 订阅链通）', () => {
    const seen: Array<string | null> = [];
    const unsub = useDegradation.subscribe((s) => seen.push(s.message));
    useDegradation.getState().setMessage('x');
    unsub();
    expect(seen).toContain('x');
  });
});
