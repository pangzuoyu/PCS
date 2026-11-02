/**
 * 状态徽章的**局部**错误边界 —— 一个未知状态**不能打挂整页**。
 *
 * ## 为什么需要它
 *
 * `StateBadge` 对未知状态在 **DEV 下抛错**（bug-180 的 fail-fast 设计：
 * 让问题第一次出现就炸，而不是让用户基于错误信息做决策）。
 * ⇒ 但**没有边界**时，后端新增一个状态就会让**整页**白屏：React 卸载整棵树
 * ⇒ 落到根 `ErrorBoundary` ⇒ 用户只看到「页面渲染异常」，而真相是
 * 「这一行的状态前端不认识」。
 *
 * ⚠️ 生产构建（`import.meta.env.DEV === false`）里 `StateBadge` 自己渲染
 * 「未知状态: X」⇒ 这层边界只影响 **dev / QA / 测试**路径 —— 但那正是
 * 「后端加状态」被发现的**第一现场**（QA 浏览器回归）。
 *
 * ## 兜底**显形**，不回落
 *
 * 绝不回落到 `STATUS_META.DRAFT` —— 那会把未知状态说成「草稿」
 * （语义被静默改写，用户无从察觉；同一族教训，见 `StateBadge.tsx` 文件头）。
 *
 * ## 为什么是**局部**边界（而不是整页一个）
 *
 * 整页一个边界 ⇒ 一行坏数据 ⇒ **整页**变成错误页；局部 ⇒ 只有那一格降级，
 * 其余内容照常可读。
 */
import { Component, type ReactNode } from 'react';

import { StateBadge, type SignModule } from './StateBadge';
import type { RecordSignStatus } from '../../types/records';

interface Props {
  /** 运行时状态值（**可能**在词表之外 ⇒ 这里收 `string`）。 */
  status: string;
  module?: SignModule;
}

interface State {
  failed: boolean;
}

export class StateBadgeBoundary extends Component<Props, State> {
  state: State = { failed: false };

  static getDerivedStateFromError(): State {
    return { failed: true };
  }

  componentDidCatch(error: Error): void {
    // ⚠️ 不静默吞：DEV 下 StateBadge 的 fail-fast 信号要留在控制台
    //    （否则「后端加了一个状态」这件事没人会发现）。
    console.error('[StateBadgeBoundary] StateBadge 渲染失败（未知状态？）', error);
  }

  render(): ReactNode {
    if (this.state.failed) {
      return (
        <span data-testid="state-badge" data-known="false">
          <span data-testid="state-badge-label">未知状态: {this.props.status}</span>
        </span>
      );
    }
    // ⚠️ 这里**必须断言**成词表类型：运行时值可能越界（那正是本组件存在的
    //    理由）⇒ 类型系统拦不住运行时 ⇒ 由边界兜住。
    return (
      <StateBadge
        status={this.props.status as RecordSignStatus}
        module={this.props.module ?? 'CONFIG'}
      />
    );
  }
}

export default StateBadgeBoundary;
