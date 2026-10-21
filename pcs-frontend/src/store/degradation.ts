/**
 * 降级横幅的全局状态（P9B-1 · SPEC §6.21 P9A-LCK-004）。
 *
 * ## 为什么是全局的
 *
 * 降级是**服务级**事实（Redis 不可用）⇒ 影响**所有**编辑入口 ⇒ 横幅在顶栏
 * （`MainLayout`）而不是每个抽屉里各画一个。
 *
 * ⚠️ **横幅不阻断任何操作**（SPEC §6.21 P9A-LCK-004）：放行的是**体验**，
 * 拦住并发的是 DB 层的 `record_hash` 比对。
 *
 * ⚠️ **文案取后端 `message` 原文**，前端不拼接、不降级成一句全局提示 ——
 * 「；本次编辑无冲突检测」这半句由后端按**该表的保存路径是否已接上冲突检测**
 * 决定（ADR-0048 §⑤）⇒ 前端自己拼就是**编造**。
 */
import { create } from 'zustand';

export interface DegradationState {
  message: string | null;
  setMessage: (message: string | null) => void;
}

export const useDegradation = create<DegradationState>(() => ({
  message: null,
  setMessage: () => {},
}));
