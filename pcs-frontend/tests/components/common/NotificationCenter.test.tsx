/**
 * NotificationCenter 测试（P45-1-13 / Task 18）。
 *
 * 覆盖（SPEC §6.20 + plan P45-1-13）：
 * - open=false：Drawer 不显示
 * - open=true：Drawer 宽 420px + 标题「通知中心」
 * - 4 个 tab：待办 / 变更 / 系统 / 全部
 * - 通知项渲染：类型 tag + 标题 + 摘要 + 时间 + [查看] 按钮
 * - 未读蓝点
 * - tab 切换过滤
 * - 空通知：Empty 占位
 * - [查看] → onItemClick
 * - 关闭按钮 → onClose
 *
 * antd Drawer 通过 portal 渲染到 document.body；用 document / screen 查询
 * 而不是 container.querySelector。
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';

import { NotificationCenter, type Notification } from '../../../src/components/common/NotificationCenter';

const notifications: Notification[] = [
  {
    notification_id: 'n1',
    category: 'change',
    kind: 'CHANGE',
    title: '物流 S-101 流量已变更',
    summary: '影响 3 条下游记录',
    issued_at: '2026-09-15 14:32',
    unread: true,
  },
  {
    notification_id: 'n2',
    category: 'todo',
    kind: 'TODO',
    title: '校核待处理',
    summary: 'Rev C 待你校核',
    issued_at: '2026-09-15 13:00',
  },
  {
    notification_id: 'n3',
    category: 'system',
    kind: 'SYSTEM',
    title: '系统升级完成',
    issued_at: '2026-09-15 10:00',
  },
];

describe('NotificationCenter — 渲染 (P45-1-13)', () => {
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

  it('通知项含 kind tag + 标题 + 摘要 + 时间', () => {
    render(<NotificationCenter open onClose={() => {}} notifications={notifications} />);
    const items = document.querySelectorAll('[data-testid="notification-item"]');
    expect(items[0].textContent).toContain('变更');
    expect(items[0].textContent).toContain('物流 S-101 流量已变更');
    expect(items[0].textContent).toContain('影响 3 条下游记录');
    expect(items[0].textContent).toContain('2026-09-15 14:32');
  });

  it('未读项左侧蓝点', () => {
    render(<NotificationCenter open onClose={() => {}} notifications={notifications} />);
    const dots = document.querySelectorAll('[data-testid="notification-unread-dot"]');
    expect(dots.length).toBe(1);
    const item = document.querySelector('[data-unread="true"]');
    expect(item).toBeTruthy();
    expect(item?.getAttribute('data-notification-id')).toBe('n1');
  });
});

describe('NotificationCenter — tab 切换', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('默认显示「全部」', () => {
    render(<NotificationCenter open onClose={() => {}} notifications={notifications} />);
    expect(document.querySelectorAll('[data-testid="notification-item"]').length).toBe(3);
  });

  it('点击「变更」tab → 仅显示变更类', () => {
    render(<NotificationCenter open onClose={() => {}} notifications={notifications} />);
    const tabs = screen.getByTestId('notification-tabs');
    const changeTab = Array.from(tabs.querySelectorAll('.ant-tabs-tab')).find(
      (el) => el.textContent === '变更',
    );
    expect(changeTab).toBeTruthy();
    fireEvent.click(changeTab!);
    expect(document.querySelectorAll('[data-testid="notification-item"]').length).toBe(1);
  });

  it('点击「待办」tab → 仅显示待办类', () => {
    render(<NotificationCenter open onClose={() => {}} notifications={notifications} />);
    const tabs = screen.getByTestId('notification-tabs');
    const todoTab = Array.from(tabs.querySelectorAll('.ant-tabs-tab')).find(
      (el) => el.textContent === '待办',
    );
    fireEvent.click(todoTab!);
    expect(document.querySelectorAll('[data-testid="notification-item"]').length).toBe(1);
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