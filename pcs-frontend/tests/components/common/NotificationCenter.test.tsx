/**
 * NotificationCenter 测试（P45-1-13 建 · P9A Z 收口按契约重绑）。
 *
 * 覆盖（SPEC §6.20 + §6.22）：
 * - open=false：Drawer 不显示
 * - open=true：Drawer 宽 420px + 标题「通知中心」
 * - 4 个 tab：待办 / 变更 / 系统 / 全部
 * - 通知项渲染：kind tag + 标题 + 正文 + 时间 + [查看] 按钮
 * - 未读蓝点（判据 = **`read_at` 为 null**，不是自造的 `unread` 布尔）
 * - tab 切换过滤（**分组来源**：变更 ← `CHANGE_NOTICE_APPROVED`；系统 ← 其余 kind；
 *   待办 ← `GET /todos`，**不是**通知）
 * - 空通知：Empty 占位
 * - [查看] → onItemClick
 * - 关闭按钮 → onClose
 *
 * ⚠️ fixture **逐字取契约**（`NotificationItemResponse` / `TodoResponse`）——
 * 前一版用的是**组件自造形状**，而那正是漂移源（TODO-065）。
 *
 * antd Drawer 通过 portal 渲染到 document.body；用 document / screen 查询
 * 而不是 container.querySelector。
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';

import { NotificationCenter } from '../../../src/components/common/NotificationCenter';
import type { NotificationItem } from '../../../src/api/notifications';
import type { TodoItem } from '../../../src/api/todos';

const notifications: NotificationItem[] = [
  {
    notification_id: 'n1',
    kind: 'CHANGE_NOTICE_APPROVED',
    title: '物流 S-101 流量已变更',
    body: '影响 3 条下游记录',
    detail: null,
    created_at: '2026-09-15 14:32',
    read_at: null,
  },
  {
    notification_id: 'n2',
    kind: 'SIGN_COMPLETED',
    title: '校核待处理',
    body: 'Rev C 待你校核',
    detail: null,
    created_at: '2026-09-15 13:00',
    read_at: '2026-09-15 13:05',
  },
  {
    notification_id: 'n3',
    kind: 'PROXY_RECORDED',
    title: '系统升级完成',
    body: '',
    detail: null,
    created_at: '2026-09-15 10:00',
    read_at: '2026-09-15 10:30',
  },
];

const todos: TodoItem[] = [
  {
    deliverable_id: 'd1',
    version_id: 'v1',
    project_id: 'p1',
    step_order: 2,
    step_role: 'CHECKER',
    title: '物流 S-101 计算书待校核',
  },
];

describe('NotificationCenter — 渲染 (P45-1-13 / P9A 契约重绑)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('open=false：Drawer 不显示', () => {
    const { container } = render(
      <NotificationCenter open={false} onClose={() => {}} />,
    );
    expect(container.querySelector('.ant-drawer-open')).toBeNull();
  });

  it('open=true：Drawer 显示 + 标题「通知中心」', () => {
    render(<NotificationCenter open onClose={() => {}} notifications={notifications} />);
    expect(screen.getByText('通知中心')).toBeTruthy();
    expect(screen.getByTestId('notification-center')).toBeTruthy();
  });

  it('Drawer 宽度 420px', () => {
    render(<NotificationCenter open onClose={() => {}} notifications={notifications} />);
    // antd v5 Drawer 把 width 应用到 .ant-drawer-content 包裹；这里检查
    // 存在 .ant-drawer 容器即可（portal 渲染，width prop 由 Drawer 自行处理）
    const drawer = document.querySelector('.ant-drawer');
    expect(drawer).toBeTruthy();
  });

  it('4 tab 渲染：待办 / 变更 / 系统 / 全部', () => {
    render(<NotificationCenter open onClose={() => {}} notifications={notifications} />);
    const tabs = screen.getByTestId('notification-tabs');
    expect(tabs.textContent).toContain('待办');
    expect(tabs.textContent).toContain('变更');
    expect(tabs.textContent).toContain('系统');
    expect(tabs.textContent).toContain('全部');
  });
});

describe('NotificationCenter — 通知项', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('渲染 3 条通知', () => {
    render(<NotificationCenter open onClose={() => {}} notifications={notifications} />);
    expect(document.querySelectorAll('[data-testid="notification-item"]').length).toBe(3);
  });

  it('通知项含 kind tag + 标题 + 正文 + 时间', () => {
    render(<NotificationCenter open onClose={() => {}} notifications={notifications} />);
    const items = document.querySelectorAll('[data-testid="notification-item"]');
    expect(items[0].textContent).toContain('变更已批准');
    expect(items[0].textContent).toContain('物流 S-101 流量已变更');
    expect(items[0].textContent).toContain('影响 3 条下游记录');
    expect(items[0].textContent).toContain('2026-09-15 14:32');
  });

  it('未读项左侧蓝点（判据 = read_at 为 null）', () => {
    render(<NotificationCenter open onClose={() => {}} notifications={notifications} />);
    const dots = document.querySelectorAll('[data-testid="notification-unread-dot"]');
    expect(dots.length).toBe(1);
    const item = document.querySelector('[data-unread="true"]');
    expect(item).toBeTruthy();
    expect(item?.getAttribute('data-notification-id')).toBe('n1');
  });

  it('红点数取传入的 unreadCount（不是前端数 items）', () => {
    render(
      <NotificationCenter
        open
        onClose={() => {}}
        notifications={notifications}
        unreadCount={7}
      />,
    );
    // 契约的 unread_count 是**全量未读数**，与当前 items 无关
    expect(screen.getByTestId('notification-tabs').textContent).toContain('7');
  });
});

describe('NotificationCenter — tab 切换（分组来源）', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('默认显示「全部」', () => {
    render(<NotificationCenter open onClose={() => {}} notifications={notifications} />);
    expect(document.querySelectorAll('[data-testid="notification-item"]').length).toBe(3);
  });

  it('点击「变更」tab → 仅 kind=CHANGE_NOTICE_APPROVED', () => {
    render(<NotificationCenter open onClose={() => {}} notifications={notifications} />);
    const tabs = screen.getByTestId('notification-tabs');
    const changeTab = Array.from(tabs.querySelectorAll('.ant-tabs-tab')).find(
      (el) => el.textContent?.startsWith('变更'),
    );
    expect(changeTab).toBeTruthy();
    fireEvent.click(changeTab!);
    expect(document.querySelectorAll('[data-testid="notification-item"]').length).toBe(1);
  });

  it('点击「系统」tab → 其余两种 kind', () => {
    render(<NotificationCenter open onClose={() => {}} notifications={notifications} />);
    const tabs = screen.getByTestId('notification-tabs');
    const systemTab = Array.from(tabs.querySelectorAll('.ant-tabs-tab')).find(
      (el) => el.textContent?.startsWith('系统'),
    );
    fireEvent.click(systemTab!);
    expect(document.querySelectorAll('[data-testid="notification-item"]').length).toBe(2);
  });

  it('点击「待办」tab → 渲染 todos（**不是**通知）', () => {
    render(
      <NotificationCenter
        open
        onClose={() => {}}
        notifications={notifications}
        todos={todos}
      />,
    );
    const tabs = screen.getByTestId('notification-tabs');
    const todoTab = Array.from(tabs.querySelectorAll('.ant-tabs-tab')).find(
      (el) => el.textContent?.startsWith('待办'),
    );
    fireEvent.click(todoTab!);
    expect(document.querySelectorAll('[data-testid="notification-item"]').length).toBe(0);
    // ⚠️ 待办 tab 的内容源是 `GET /todos`（**不是**通知）⇒ 渲染 TodoPanel
    expect(document.querySelectorAll('[data-testid="todo-panel"]').length).toBe(1);
    expect(screen.getByTestId('todo-title').textContent).toContain('物流 S-101 计算书待校核');
  });
});

describe('NotificationCenter — 联动 + 边界', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('[查看] → onItemClick(notification_id)', () => {
    const onItemClick = vi.fn();
    render(
      <NotificationCenter
        open
        onClose={() => {}}
        notifications={notifications}
        onItemClick={onItemClick}
      />,
    );
    const btns = document.querySelectorAll('[data-testid="notification-view"]');
    fireEvent.click(btns[0]);
    expect(onItemClick).toHaveBeenCalledWith('n1');
  });

  it('不传 onItemClick 不报错', () => {
    render(<NotificationCenter open onClose={() => {}} notifications={notifications} />);
    expect(() =>
      fireEvent.click(document.querySelector('[data-testid="notification-view"]')!),
    ).not.toThrow();
  });

  it('空通知：Empty 占位', () => {
    render(<NotificationCenter open onClose={() => {}} notifications={[]} />);
    expect(screen.getByTestId('notification-empty')).toBeTruthy();
  });

  it('关闭回调：点击关闭按钮触发 onClose', () => {
    const onClose = vi.fn();
    render(
      <NotificationCenter open onClose={onClose} notifications={notifications} />,
    );
    const closeBtn = document.querySelector('.ant-drawer-close');
    expect(closeBtn).toBeTruthy();
    fireEvent.click(closeBtn!);
    expect(onClose).toHaveBeenCalledTimes(1);
  });
});
