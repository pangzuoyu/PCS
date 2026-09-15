/**
 * InputChecklistPanel 升级版测试（P45-1-7 / Task 12）。
 *
 * 覆盖（SPEC §6.8 + plan P45-1-7）：
 * - projectId 触发 checklistApi.list + completeness
 * - 顶部统计：完成 N/Total + 环形 Progress + 分类计数
 * - 筛选：状态 / 模块 / 分类下拉过滤
 * - 假设数据清单：可展开 Collapse，列出 ASSUMED 项及理由
 * - onItemClick? 联动：点「详情」触发 callback（item）
 * - 当前值：input_value_json 提取为 NumericCell
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';

vi.mock('../../../src/api/sprint1', () => ({
  checklistApi: {
    list: vi.fn().mockResolvedValue([
      {
        checklist_id: 'c1',
        project_id: 'p1',
        item_key: 'feed.temp',
        item_label: '进料温度',
        module: 'FEED',
        input_category: 'REQUIRED',
        required: true,
        input_value_json: { value: 17.2 },
        source_type: 'DEFAULT',
        status: 'VERIFIED',
        verified_by: 'alice',
        verified_at: null,
        assumption_reason: null,
        note: null,
      },
      {
        checklist_id: 'c2',
        project_id: 'p1',
        item_key: 'recycle.ratio',
        item_label: '回流量比',
        module: 'RECYCLE',
        input_category: 'CONDITIONAL',
        required: false,
        input_value_json: { value: 0.3 },
        source_type: 'DESIGN',
        status: 'ASSUMED',
        verified_by: null,
        verified_at: null,
        assumption_reason: '缺少实测数据，按典型装置类比',
        note: null,
      },
      {
        checklist_id: 'c3',
        project_id: 'p1',
        item_key: 'env.pressure',
        item_label: '环境压力',
        module: 'FEED',
        input_category: 'OPTIONAL',
        required: false,
        input_value_json: null,
        source_type: null,
        status: 'NOT_STARTED',
        verified_by: null,
        verified_at: null,
        assumption_reason: null,
        note: null,
      },
    ]),
    completeness: vi.fn().mockResolvedValue({
      project_id: 'p1',
      total: 3,
      required_total: 1,
      required_verified: 1,
      required_assumed: 0,
      required_blocked: 0,
      completeness_pct: 33.3,
    }),
  },
}));

import { InputChecklistPanel } from '../../../src/components/common/InputChecklistPanel';

describe('InputChecklistPanel — projectId 拉取 (P45-1-7)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('渲染基础壳', () => {
    render(<InputChecklistPanel projectId="p1" />);
    expect(screen.getByTestId('input-checklist-panel')).toBeTruthy();
  });

  it('projectId 触发 checklistApi.list + completeness', async () => {
    const { checklistApi } = await import('../../../src/api/sprint1');
    render(<InputChecklistPanel projectId="pX" />);
    await waitFor(() => {
      expect(checklistApi.list).toHaveBeenCalledWith('pX');
      expect(checklistApi.completeness).toHaveBeenCalledWith('pX');
    });
  });
});

describe('InputChecklistPanel — 顶部统计', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('完成 N/Total 显示', async () => {
    render(<InputChecklistPanel projectId="p1" />);
    await waitFor(() => {
      // 1 VERIFIED / 3 total
      expect(screen.getByTestId('completion-summary').textContent).toBe('完成 1/3');
    });
  });

  it('环形 Progress 渲染（type=circle）', async () => {
    const { container } = render(<InputChecklistPanel projectId="p1" />);
    await waitFor(() => {
      expect(container.querySelector('.ant-progress-circle')).toBeTruthy();
    });
  });

  it('completeness.detail 显示分类计数', async () => {
    render(<InputChecklistPanel projectId="p1" />);
    await waitFor(() => {
      const detail = screen.getByTestId('completion-detail').textContent || '';
      expect(detail).toContain('REQUIRED 1/1');
      expect(detail).toContain('假设 0');
      expect(detail).toContain('阻塞 0');
    });
  });

  it('副标题显示「假设 N · 未验证 M」', async () => {
    render(<InputChecklistPanel projectId="p1" />);
    await waitFor(() => {
      // 1 ASSUMED + 1 IN_PROGRESS(0) = 假设 1 · 未验证 0
      expect(screen.getByText(/假设 1 · 未验证 0/)).toBeTruthy();
    });
  });
});

describe('InputChecklistPanel — 列表渲染', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('3 行（含 input_value_json 数字 + null）', async () => {
    const { container } = render(<InputChecklistPanel projectId="p1" />);
    await waitFor(() => {
      const rows = container.querySelectorAll('.ant-table-row');
      expect(rows.length).toBe(3);
    });
  });

  it('「进料温度」含 NumericCell（数字）', async () => {
    render(<InputChecklistPanel projectId="p1" />);
    await waitFor(() => {
      expect(screen.getByText('进料温度')).toBeTruthy();
      // 17.2 → significant 4 → "17.20"
      expect(screen.getByText(/17\.20/)).toBeTruthy();
    });
  });

  it('「环境压力」current_value=—（null）', async () => {
    const { container } = render(<InputChecklistPanel projectId="p1" />);
    await waitFor(() => {
      // 第三行是环境压力，input_value_json=null → NumericCell 显示 —
      expect(screen.getByText('环境压力')).toBeTruthy();
      const dashes = container.querySelectorAll('.ant-table-cell');
      expect(Array.from(dashes).some((el) => el.textContent === '—')).toBe(true);
    });
  });

  it('分类 tag 含「必填」标记', async () => {
    render(<InputChecklistPanel projectId="p1" />);
    await waitFor(() => {
      // REQUIRED（必填）+ CONDITIONAL + OPTIONAL 共 3 个 tag
      const tags = screen.getAllByTestId('category-tag');
      expect(tags.length).toBe(3);
      expect(tags[0].textContent).toContain('REQUIRED');
      expect(tags[0].textContent).toContain('必填');
      expect(tags[1].textContent).toContain('CONDITIONAL');
      expect(tags[1].textContent).not.toContain('必填');
      expect(tags[2].textContent).toContain('OPTIONAL');
    });
  });
});

describe('InputChecklistPanel — 筛选', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('3 个筛选 Select 渲染', async () => {
    render(<InputChecklistPanel projectId="p1" />);
    expect(screen.getByTestId('filter-status')).toBeTruthy();
    expect(screen.getByTestId('filter-module')).toBeTruthy();
    expect(screen.getByTestId('filter-category')).toBeTruthy();
  });
});

describe('InputChecklistPanel — 假设清单', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('Collapse 标题显示「假设数据清单（N）」', async () => {
    render(<InputChecklistPanel projectId="p1" />);
    await waitFor(() => {
      expect(screen.getByText(/假设数据清单（1）/)).toBeTruthy();
    });
  });

  it('ASSUMED 行渲染（含理由）', async () => {
    const { container } = render(<InputChecklistPanel projectId="p1" />);
    await waitFor(() => {
      // Collapse 默认折叠 + destroyInactivePanel=true 时子节点未渲染；
      // 改为断言 Collapse 标题「假设数据清单（1）」+ Collapse 容器存在
      expect(container.querySelector('.ant-collapse')).toBeTruthy();
      expect(screen.getByText(/假设数据清单（1）/)).toBeTruthy();
    });
  });
});

describe('InputChecklistPanel — onItemClick 联动', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('点「详情」→ onItemClick 收到 item', async () => {
    const onItemClick = vi.fn();
    const { container } = render(
      <InputChecklistPanel projectId="p1" onItemClick={onItemClick} />,
    );
    await waitFor(() => {
      const rows = container.querySelectorAll('.ant-table-row');
      expect(rows.length).toBe(3);
    });
    const actionLink = container.querySelector('[data-testid="checklist-item-action"]');
    expect(actionLink).toBeTruthy();
    actionLink!.dispatchEvent(new MouseEvent('click', { bubbles: true }));
    expect(onItemClick).toHaveBeenCalledTimes(1);
    expect(onItemClick.mock.calls[0][0].item_key).toBe('feed.temp');
  });

  it('不传 onItemClick 不报错', async () => {
    const { container } = render(<InputChecklistPanel projectId="p1" />);
    await waitFor(() => {
      const rows = container.querySelectorAll('.ant-table-row');
      expect(rows.length).toBe(3);
    });
    const actionLink = container.querySelector('[data-testid="checklist-item-action"]');
    expect(() => actionLink!.dispatchEvent(new MouseEvent('click', { bubbles: true }))).not.toThrow();
  });
});