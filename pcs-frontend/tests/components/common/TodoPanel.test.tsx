/**
 * TodoPanel 的守卫（P9B-1 Task T5 · SPEC §6.22）。
 *
 * ## 两条不能省的
 *
 * - ⚠️ **`total` 与 `items.length` 可能不等**（分页 / 上限）⇒ 计数用 `total`。
 * - ⚠️ **待办为空 ≠ 没有待办** —— 也可能是「当前用户在该项目内**无签署职责**」
 *   ⇒ 空态文案**不得**断言「你没有待办」以外的任何事实。
 */
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';

import { TodoPanel } from '../../../src/components/common/TodoPanel';
import type { TodoItem } from '../../../src/api/todos';

const TODOS: TodoItem[] = [
  {
    deliverable_id: 'd-1',
    version_id: 'v-1',
    project_id: 'p-1',
    step_order: 2,
    step_role: 'CHECKER',
    title: '校核 泵计算书 Rev A',
  },
];

describe('TodoPanel — 我的待办（SPEC §6.22）', () => {
  it('渲染列：交付物 / 版本 / 步骤 / 签署职责 / 标题', () => {
    render(<TodoPanel items={TODOS} />);
    expect(screen.getByText('交付物')).toBeTruthy();
    expect(screen.getByText('版本')).toBeTruthy();
    expect(screen.getByText('步骤')).toBeTruthy();
    expect(screen.getByText('签署职责')).toBeTruthy();
    expect(screen.getByText('标题')).toBeTruthy();
    expect(screen.getByText('校核 泵计算书 Rev A')).toBeTruthy();
    expect(screen.getByText('CHECKER')).toBeTruthy();
  });

  it('compact ⇒ 只渲染标题 + 职责（抽屉用）', () => {
    render(<TodoPanel items={TODOS} compact />);
    expect(screen.getByText('校核 泵计算书 Rev A')).toBeTruthy();
    expect(screen.getByText('CHECKER')).toBeTruthy();
    // ⚠️ compact 下不渲染列头
    expect(screen.queryByText('交付物')).toBeNull();
  });

  it('⚠️ 空态**不得**断言「你没有待办」（可能是「无签署职责」）', () => {
    render(<TodoPanel items={[]} />);
    const empty = screen.getByTestId('todo-panel-empty');
    expect(empty.textContent).toBeTruthy();
    expect(empty.textContent).not.toContain('你没有待办');
  });

  it('onOpen 回调收到被点的待办', () => {
    const onOpen = vi.fn();
    render(<TodoPanel items={TODOS} onOpen={onOpen} />);
    fireEvent.click(screen.getByTestId('todo-open-d-1'));
    expect(onOpen).toHaveBeenCalledTimes(1);
    expect(onOpen.mock.calls[0][0]).toMatchObject({ deliverable_id: 'd-1' });
  });
});
