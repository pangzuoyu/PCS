/**
 * 「待我审核」队列页 —— P10-I · T1 · TODO-197。
 *
 * ## 断什么
 *
 * | # | 断言 | 为什么 |
 * |---|---|---|
 * | ① | 队列渲染后端返回的条目 | 页面**只渲染后端给的**（可见性后端说了算）|
 * | ② | 发布**成功** ⇒ ⇒ 重新拉队列 | 发布完这条就不该还在队列里 |
 * | ③ | 发布**403** ⇒ ⇒ 页面给出可读提示 | 「点了必失败」必须有话说 |
 * | ④ | 发布**404** ⇒ ⇒ 提示「不存在或无权限」 | 404 与 403 的**处置不同**（文案不同）|
 * | ⑤ | 队列里的名称**不是链接** | 人裁约束 1：**只读视图 · 不能进编辑器** |
 * | ⑥ | 「忽略」⇒ ⇒ 行消失 + 落 localStorage；「显示已忽略」⇒ ⇒ 行回来 | 人裁 ④ |
 * | ⑦ | 非审核角色（加载期 403）⇒ ⇒ **不渲染空表** | 空表会被读成「没有待审的」|
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, act, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

const pendingReview = vi.fn();
const publish = vi.fn();
const rejectDef = vi.fn();

vi.mock('../../../src/api/reportBuilder', () => ({
  reportBuilderApi: {
    pendingReview: (...a: unknown[]) => pendingReview(...a),
    publish: (...a: unknown[]) => publish(...a),
    reject: (...a: unknown[]) => rejectDef(...a),
  },
  errorMessage: (err: unknown) => {
    const e = err as { response?: { data?: { message?: string } } };
    return e?.response?.data?.message ?? '未知错误';
  },
}));

import { ReportReviewQueuePage } from '../../../src/pages/report/ReportReviewQueuePage';

function item(defId: string, name: string, updatedAt: string | null = '2026-11-23T10:00:00Z') {
  return {
    def_id: defId,
    name,
    category: '设备类',
    description: '按位号列设备',
    created_by: '00000000-0000-0000-0000-00000000cccc',
    project_id: null,
    created_at: '2026-11-23T09:00:00Z',
    updated_at: updatedAt,
  };
}

async function flush() {
  for (let i = 0; i < 6; i += 1) {
    await act(async () => { await Promise.resolve(); });
  }
}

/** 按钮文案（**去掉空白**）—— antd 给两个汉字的按钮插空格（`发 布`）。 */
function buttonText(b: Element): string {
  return (b.textContent ?? '').replace(/\s/g, '');
}

/** 造一个带状态码 + 错误码的 axios 形状错误。 */
function apiError(status: number, code: string, message: string) {
  return { response: { status, data: { code, message } } };
}

function publishButton(): HTMLButtonElement {
  const btn = [...document.querySelectorAll('button')]
    .find((b) => buttonText(b) === '发布');
  if (!btn) throw new Error('找不到「发布」按钮');
  return btn as HTMLButtonElement;
}

beforeEach(() => {
  pendingReview.mockReset();
  publish.mockReset();
  rejectDef.mockReset();
  window.localStorage.clear();
});

/** 「打回」**行按钮**（antd 会给两个汉字的按钮插空格 ⇒ ⇒ 比对时去空白）。 */
function rejectButton(): HTMLButtonElement {
  const btn = [...document.querySelectorAll('button')]
    .find((b) => buttonText(b) === '打回');
  if (!btn) throw new Error('找不到「打回」按钮');
  return btn as HTMLButtonElement;
}

/** 弹窗里的「确定」按钮。
 *
 * ⚠️ **不能按文案找** —— 页面上的行按钮也叫「打回」⇒ ⇒ ⇒ 两个同名
 * ⇒ ⇒ ⇒ `find` 会拿到**行按钮** ⇒ ⇒ ⇒ 点它只是**再打开一次弹窗**
 * ⇒ ⇒ ⇒ 看起来像「点了没反应」⇒ ⇒ ⇒ **假失败**。
 * ⇒ ⇒ ⇒ 所以**按位置**找：弹窗 footer 里的 primary 按钮。
 */
function modalOkButton(): HTMLButtonElement {
  const btn = document.querySelector('.ant-modal-footer button.ant-btn-primary');
  if (!btn) throw new Error('找不到弹窗的确定按钮');
  return btn as HTMLButtonElement;
}

describe('ReportReviewQueuePage —— 「待我审核」队列', () => {
  it('① 渲染后端返回的条目（**不本地过滤**）', async () => {
    pendingReview.mockResolvedValue({
      items: [item('d1', '设备一览'), item('d2', '能耗汇总')],
      total: 2,
    });
    render(<MemoryRouter><ReportReviewQueuePage /></MemoryRouter>);
    await flush();

    expect(screen.getByText('设备一览')).toBeTruthy();
    expect(screen.getByText('能耗汇总')).toBeTruthy();
  });

  it('② 发布成功 ⇒ ⇒ 重新拉队列（这条不该还在队列里）', async () => {
    pendingReview.mockResolvedValue({ items: [item('d1', '设备一览')], total: 1 });
    publish.mockResolvedValue({ def_id: 'd1', status: 'PUBLISHED' });
    render(<MemoryRouter><ReportReviewQueuePage /></MemoryRouter>);
    await flush();

    await act(async () => { fireEvent.click(publishButton()); });
    await flush();

    expect(publish).toHaveBeenCalledWith('d1');
    expect(pendingReview).toHaveBeenCalledTimes(2);
  });

  it('③ 发布 403 ⇒ ⇒ 页面给出可读提示（不是静默失败）', async () => {
    pendingReview.mockResolvedValue({ items: [item('d1', '设备一览')], total: 1 });
    publish.mockRejectedValue(apiError(
      403, 'REPORT_DEFINITION_NOT_SHAREABLE', '该定义不能由他人发布'));
    render(<MemoryRouter><ReportReviewQueuePage /></MemoryRouter>);
    await flush();

    await act(async () => { fireEvent.click(publishButton()); });
    await flush();

    expect(document.body.textContent).toContain('该定义不能由他人发布');
    expect(document.body.textContent).toContain('仅创建人可见');
  });

  it('④ 发布 404 ⇒ ⇒ 提示「不存在或没有权限」（与 403 文案不同）', async () => {
    pendingReview.mockResolvedValue({ items: [item('d1', '设备一览')], total: 1 });
    publish.mockRejectedValue(apiError(
      404, 'REPORT_DEFINITION_NOT_FOUND', '报表定义不存在：d1'));
    render(<MemoryRouter><ReportReviewQueuePage /></MemoryRouter>);
    await flush();

    await act(async () => { fireEvent.click(publishButton()); });
    await flush();

    expect(document.body.textContent).toContain('报表定义不存在');
    expect(document.body.textContent).toContain('不存在，或你没有该项目的权限');
  });

  it('⑤ ⚠️ 队列里的名称**不是链接**（只读视图 · 不能进编辑器）', async () => {
    pendingReview.mockResolvedValue({ items: [item('d1', '设备一览')], total: 1 });
    render(<MemoryRouter><ReportReviewQueuePage /></MemoryRouter>);
    await flush();

    const link = document.querySelector('a[href*="/report/definitions/"]');
    expect(link).toBeNull();
  });

  it('⑥ 「忽略」⇒ ⇒ 行消失 + 落 localStorage；「显示已忽略」⇒ ⇒ 行回来', async () => {
    pendingReview.mockResolvedValue({ items: [item('d1', '设备一览')], total: 1 });
    render(<MemoryRouter><ReportReviewQueuePage /></MemoryRouter>);
    await flush();

    const ignoreBtn = [...document.querySelectorAll('button')]
      .find((b) => buttonText(b) === '忽略');
    expect(ignoreBtn).toBeTruthy();
    await act(async () => { fireEvent.click(ignoreBtn as HTMLButtonElement); });
    await flush();

    expect(screen.queryByText('设备一览')).toBeNull();
    expect(window.localStorage.getItem('pcs.review.ignored.v1')).toContain('d1');

    // 打开「显示已忽略」⇒ ⇒ 它回来（且按钮变成「取消忽略」）
    const toggle = document.querySelector('button.ant-switch');
    expect(toggle).toBeTruthy();
    await act(async () => { fireEvent.click(toggle as HTMLButtonElement); });
    await flush();
    expect(screen.getByText('设备一览')).toBeTruthy();
  });

  it('⑧ 「打回」⇒ ⇒ 弹窗要原因 ⇒ ⇒ 提交后**重新拉队列**', async () => {
    pendingReview.mockResolvedValue({ items: [item('d1', '设备一览')], total: 1 });
    rejectDef.mockResolvedValue({ def_id: 'd1', status: 'DRAFT', rejected_at: '2026-11-24T03:00:00Z' });
    render(<MemoryRouter><ReportReviewQueuePage /></MemoryRouter>);
    await flush();

    await act(async () => { fireEvent.click(rejectButton()); });
    await flush();

    // ⚠️ **弹窗里必须能写原因**（创建人要看得懂要改什么）
    const input = document.querySelector('[data-testid="reject-reason-input"]');
    expect(input).toBeTruthy();

    await act(async () => {
      fireEvent.change(input as HTMLTextAreaElement, { target: { value: '字段选错了' } });
    });
    await act(async () => { fireEvent.click(modalOkButton()); });
    await flush();

    expect(rejectDef).toHaveBeenCalledWith('d1', '字段选错了');
    // ⇒ ⇒ 打回完它**不在队列里**了 ⇒ ⇒ ⇒ 页面重新拉一次
    expect(pendingReview).toHaveBeenCalledTimes(2);
  });

  it('⑨ ⚠️ 空原因 ⇒ ⇒ 「打回」按钮**禁用**（不发请求）', async () => {
    pendingReview.mockResolvedValue({ items: [item('d1', '设备一览')], total: 1 });
    render(<MemoryRouter><ReportReviewQueuePage /></MemoryRouter>);
    await flush();

    await act(async () => { fireEvent.click(rejectButton()); });
    await flush();

    expect(modalOkButton().disabled).toBe(true);
    expect(rejectDef).not.toHaveBeenCalled();
  });

  it('⑩ 打回 409（已打过回）⇒ ⇒ 页面给出可读提示', async () => {
    pendingReview.mockResolvedValue({ items: [item('d1', '设备一览')], total: 1 });
    rejectDef.mockRejectedValue(apiError(
      409, 'REPORT_DEFINITION_ALREADY_REJECTED', '该定义已被打回过'));
    render(<MemoryRouter><ReportReviewQueuePage /></MemoryRouter>);
    await flush();

    await act(async () => { fireEvent.click(rejectButton()); });
    await flush();
    const input = document.querySelector('[data-testid="reject-reason-input"]');
    await act(async () => {
      fireEvent.change(input as HTMLTextAreaElement, { target: { value: '再打回一次' } });
    });
    await act(async () => { fireEvent.click(modalOkButton()); });
    await flush();

    expect(document.body.textContent).toContain('该定义已被打回过');
    expect(document.body.textContent).toContain('已经被打回过');
  });

  it('⑦ 非审核角色（加载期 403）⇒ ⇒ **不渲染空表**', async () => {
    pendingReview.mockRejectedValue(apiError(
      403, 'REPORT_DEFINITION_ROLE_REQUIRED', '查看待审队列需要审核角色'));
    render(<MemoryRouter><ReportReviewQueuePage /></MemoryRouter>);
    await flush();

    expect(document.body.textContent).toContain('查看待审队列需要审核角色');
    expect(document.body.textContent).toContain('需要审核角色');
    // ⚠️ **没有表格** ⇒ ⇒ 空表会被读成「没有待审的草稿」（而真相是「你没权限」）
    // ⚠️ **断「table 元素个数」而不是 `table.ant-table`** —— antd v5 的
    // `<table>` **没有** `ant-table` 类（类在包裹 div 上）⇒ ⇒ 用类名断
    // ⇒ ⇒ **恒真**（永远 null）⇒ ⇒ ⇒ 那是一条**假绿**断言（自查时才发现）。
    expect(document.querySelectorAll('table').length).toBe(0);
  });
});
