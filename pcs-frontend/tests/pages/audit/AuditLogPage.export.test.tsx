/**
 * 审计日志的**筛选 + CSV 导出**（P9B-2 · T7 · SPEC §7.20）。
 *
 * ⚠️ **为什么单独一个文件**：既有的 `AuditLogPage.test.tsx` 把 `api` 模块整个
 * mock 掉了（且把 `useAuth` mock 成常量）⇒ 走不到 audit-logs tab，也测不了
 * 真实的请求参数与下载内容。⇒ 这里用 MSW（mock **服务端**）。
 *
 * ## 守三件事
 *
 * 1. ⚠️ **导出的数据源是「当前筛选条件下的全部行」**（循环拉页），**不是**
 *    当前页 ⇒ 否则用户拿到的是**残缺**的数据（RF-11）。
 * 2. ⚠️ **超限显式提示截断** ⇒ 不得静默截断。
 * 3. ⚠️ **CSV 字段必须转义**（RFC 4180）—— `detail_json` 里可能有逗号 /
 *    引号 / 换行 ⇒ 不转义的话 Excel 拆错列 ⇒ 数据是残缺的。
 */
import { describe, it, expect, vi, beforeAll, afterAll, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';

import { AuditLogPage } from '../../../src/pages/audit/AuditLogPage';
import { useAuth } from '../../../src/store/auth';

type AuditLogItem = {
  audit_id: string;
  user_id?: string;
  action: string;
  resource_type?: string;
  resource_id?: string;
  detail_json?: Record<string, unknown>;
  occurred_at: string;
};

/** 带逗号 / 引号 / 换行的 detail_json —— 导出必须不破行。 */
const TRICKY_ITEM: AuditLogItem = {
  audit_id: 'a-tricky',
  user_id: 'u-1',
  action: 'RECORD_EDITED',
  resource_type: 'cooling_tower_result',
  resource_id: 'r-1',
  detail_json: {
    note: '含"引号", 逗号\n以及换行',
    changed_fields: ['duty_kw'],
  },
  occurred_at: '2026-10-20T10:00:00Z',
};

const ITEMS: AuditLogItem[] = [
  {
    audit_id: 'a-1',
    user_id: 'u-1',
    action: 'RECORD_EDITED',
    resource_type: 'cooling_tower_result',
    resource_id: 'r-1',
    detail_json: { changed_fields: ['duty_kw'] },
    occurred_at: '2026-10-20T10:00:00Z',
  },
  TRICKY_ITEM,
];

let listCalls = 0;
let seenParams: URLSearchParams[] = [];
let totalRows = 2;
/** 403 ⇒ 模拟「无权查看」；200 ⇒ 正常。 */
let auditLogsStatus = 200;
/** ⚠️ 结果集**总行数**（E5：恰好 5000 ⇒ 不该报「已截断」）。 */
let auditRowsTotal = 2;
/** ⚠️ 按需生成行（避免 seed 里放 5000 条）。 */
function makeRows(offset: number, limit: number) {
  return Array.from({ length: Math.max(0, Math.min(limit, auditRowsTotal - offset)) }, (_, i) => ({
    audit_id: `a-${offset + i}`,
    user_id: 'u-1',
    action: 'RECORD_EDITED',
    resource_type: 'cooling_tower_result',
    resource_id: `r-${offset + i}`,
    detail_json: { changed_fields: ['duty_kw'] },
    occurred_at: '2026-10-20T10:00:00Z',
  }));
}

const server = setupServer(
  http.get('/api/v1/audit-logs', ({ request }) => {
    listCalls += 1;
    const url = new URL(request.url);
    seenParams.push(url.searchParams);
    const offset = Number(url.searchParams.get('offset') ?? '0');
    const limit = Number(url.searchParams.get('limit') ?? '50');
    if (auditLogsStatus === 403) {
      // ⚠️ 后端 `require_roles` 抛的 HTTPException ⇒ 全局 handler 渲染成
      //    `{code: 'HTTP_403', message: "需要角色 [...]"}`（app/core/errors.py）。
      return HttpResponse.json(
        {
          code: 'HTTP_403',
          message: "需要角色 ['SYSTEM_ADMIN']",
          detail: null,
          trace_id: 't-403',
        },
        { status: 403 },
      );
    }
    if (auditRowsTotal > ITEMS.length) {
      // ⚠️ 大结果集 ⇒ 按 offset/limit 现生成（E5 的 5000 行场景）
      return HttpResponse.json({
        items: makeRows(offset, limit),
        total: auditRowsTotal,
        limit,
        offset,
      });
    }
    return HttpResponse.json({
      items: offset === 0 ? ITEMS : [],
      total: totalRows,
      limit,
      offset,
    });
  }),
  http.get('/api/v1/config-audit', () =>
    HttpResponse.json({ items: [], total: 0, limit: 50, offset: 0 }),
  ),
);

/** 读 Blob 文本（jsdom 的 Blob 没有 `.text()` ⇒ 走 FileReader）。 */
function readBlobText(blob: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const fr = new FileReader();
    fr.onload = () => resolve(String(fr.result ?? ''));
    fr.onerror = () => reject(fr.error);
    fr.readAsText(blob);
  });
}

/** 极简 CSV 解析（RFC 4180：引号内的逗号 / 换行不作分隔）。 */
function parseCsv(text: string): string[][] {
  const rows: string[][] = [];
  let row: string[] = [];
  let cell = '';
  let inQuotes = false;
  for (let i = 0; i < text.length; i += 1) {
    const ch = text[i];
    if (inQuotes) {
      if (ch === '"') {
        if (text[i + 1] === '"') {
          cell += '"';
          i += 1;
        } else {
          inQuotes = false;
        }
      } else {
        cell += ch;
      }
    } else if (ch === '"') {
      inQuotes = true;
    } else if (ch === ',') {
      row.push(cell);
      cell = '';
    } else if (ch === '\r') {
      // 跳过（\r\n 组合）
    } else if (ch === '\n') {
      row.push(cell);
      rows.push(row);
      row = [];
      cell = '';
    } else {
      cell += ch;
    }
  }
  if (cell !== '' || row.length > 0) {
    row.push(cell);
    rows.push(row);
  }
  return rows;
}

describe('AuditLogPage —— 筛选 + CSV 导出', () => {
  const blobs: Blob[] = [];

  beforeAll(() => {
    server.listen({ onUnhandledRequest: 'error' });
    // ⚠️ jsdom 没有 `URL.createObjectURL` ⇒ 捕获下载的 Blob 以便断言内容
    URL.createObjectURL = vi.fn((blob: Blob) => {
      blobs.push(blob);
      return 'blob:mock';
    }) as unknown as typeof URL.createObjectURL;
    URL.revokeObjectURL = vi.fn();
  });
  afterAll(() => server.close());
  beforeEach(() => {
    blobs.length = 0;
    listCalls = 0;
    seenParams = [];
    totalRows = 2;
    auditLogsStatus = 200;
    auditRowsTotal = 2;
    useAuth.setState({ role: 'SYSTEM_ADMIN', accessToken: 'test-token' });
  });

  async function openAuditLogsTab() {
    render(<AuditLogPage />);
    await waitFor(() => expect(screen.getByText(/通用 audit/)).toBeTruthy());
    fireEvent.click(screen.getByText(/通用 audit/));
    await waitFor(() => expect(screen.getByTestId('audit-export-csv')).toBeTruthy());
  }

  it('⚠️ 导出覆盖**当前筛选条件下的全部行**（循环拉页，不是当前页）（RF-11）', async () => {
    await openAuditLogsTab();
    // ⚠️ 第一页拉 50（表格显示），导出时按 200 一页拉
    fireEvent.click(screen.getByTestId('audit-export-csv'));
    await waitFor(() => expect(blobs.length).toBe(1));

    const exportCall = seenParams.filter((p) => p.get('limit') === '200');
    expect(exportCall.length).toBeGreaterThan(0);
    expect(exportCall[0]?.get('offset')).toBe('0');
  });

  it('⚠️ CSV 字段**转义**（逗号 / 引号 / 换行 ⇒ 不破行）（RFC 4180）', async () => {
    await openAuditLogsTab();
    fireEvent.click(screen.getByTestId('audit-export-csv'));
    await waitFor(() => expect(blobs.length).toBe(1));

    const text = await readBlobText(blobs[0]);
    const rows = parseCsv(text);
    // ⚠️ 2 条数据 + 1 行表头 = **3 条记录**（引号里的换行**不算**断行）
    expect(rows.length).toBe(3);
    // ⚠️ **列数不变** ⇒ 逗号没把单元格拆开（7 列：audit_id + 6）
    expect(rows[2].length).toBe(7);
    // ⚠️ 含逗号 / 引号 / 换行的那个字段**完整**落在**一个**单元格里
    const trickyCell = rows[2][6];
    expect(trickyCell).toContain('引号');
    expect(trickyCell).toContain('逗号');
    expect(trickyCell).toContain('以及换行');
    // ⚠️ 原始 CSV 里引号**成对加倍**（RFC 4180）⇒ Excel 不会提前收尾
    expect(text).toContain('""');
  });

  it('⚠️ 导出后提示行数（范围写明）', async () => {
    await openAuditLogsTab();
    fireEvent.click(screen.getByTestId('audit-export-csv'));
    await waitFor(() => expect(screen.getByTestId('audit-export-notice')).toBeTruthy());
    expect(screen.getByTestId('audit-export-notice').textContent).toContain('2');
    expect(screen.getByTestId('audit-export-notice').textContent).toContain('全部结果');
  });

  it('⚠️ 表格走**服务端分页**（翻页 ⇒ 带 offset；不是前端切 50 条）', async () => {
    // ⚠️ 此前 `limit: 50` 不带 offset + antd **前端**分页 ⇒ 表格**永远只有 50 行**，
    //    标题却写「共 12000 条」⇒ 三处数字互相打架。
    //    ⇒ 服务端分页：页码由**后端的 total** 决定 ⇒ total=120 时有第 2 页。
    totalRows = 120;
    await openAuditLogsTab();
    seenParams = [];
    // ⚠️ 页码 2 存在 ⇔ 分页器知道**后端的 total**（前端分页时 dataSource 只有 2 行
    //    ⇒ 只有一个页 ⇒ 这行先失败 ⇒ 说明还没做服务端分页）。
    await waitFor(() => expect(screen.getByTitle('2')).toBeTruthy());
    fireEvent.click(screen.getByTitle('2'));
    await waitFor(() => expect(seenParams.length).toBeGreaterThan(0));
    const last = seenParams[seenParams.length - 1];
    expect(last?.get('offset')).toBe('50');
    expect(last?.get('limit')).toBe('50');
  });

  it('⚠️ 403（无权）⇒ 错误提示**不可关闭** + **不渲染空表**', async () => {
    // ⚠️ 此前错误 Alert **可关闭** ⇒ 关掉就退化成「共 0 条」的**空表**
    //    ⇒ 用户读成「这个系统没有审计日志」⇒ 真相是「你没权限」（RF-12）。
    auditLogsStatus = 403;
    await openAuditLogsTab();
    await waitFor(() => expect(screen.getByTestId('audit-list-error')).toBeTruthy());
    expect(screen.getByTestId('audit-list-error').textContent).toContain('无权');
    // ⚠️ **关不掉**（关掉 = 假装没有数据）
    expect(document.querySelector('.ant-alert-close-icon')).toBeNull();
    // ⚠️ **不渲染空表**（空表会被读成「没有审计日志」）
    expect(document.querySelector('.ant-table')).toBeNull();
  });

  it('⚠️ 恰好 5000 行 ⇒ **不**误报「已截断」', async () => {
    // ⚠️ 此前 `collected.length >= EXPORT_LIMIT` 就判「已截断」⇒ 结果集**正好**
    //    5000 行时也会说「已截断」⇒ 用户以为少了数据。
    auditRowsTotal = 5000;
    await openAuditLogsTab();
    fireEvent.click(screen.getByTestId('audit-export-csv'));
    await waitFor(() => expect(screen.getByTestId('audit-export-notice')).toBeTruthy(), {
      timeout: 20000,
    });
    const notice = screen.getByTestId('audit-export-notice').textContent ?? '';
    expect(notice).not.toContain('截断');
    expect(notice).toContain('5000');
  });

  it('⚠️ 超过 5000 行 ⇒ 明说「已截断」', async () => {
    auditRowsTotal = 5001;
    await openAuditLogsTab();
    fireEvent.click(screen.getByTestId('audit-export-csv'));
    await waitFor(() => expect(screen.getByTestId('audit-export-notice')).toBeTruthy(), {
      timeout: 20000,
    });
    expect(screen.getByTestId('audit-export-notice').textContent).toContain('截断');
  });

  it('⚠️ 导出用**已应用**的筛选值（输入框改了但没点「查询」⇒ 不生效）', async () => {
    // ⚠️ 此前导出用**输入框的实时值** ⇒ CSV 与屏幕上看到的行**对不上**
    //    ⇒ 用户以为拿到的就是眼前这份数据。
    await openAuditLogsTab();
    fireEvent.change(screen.getByTestId('audit-filter-action'), {
      target: { value: 'NEVER_APPLIED' },
    });
    seenParams = [];
    fireEvent.click(screen.getByTestId('audit-export-csv'));
    await waitFor(() => expect(blobs.length).toBe(1), { timeout: 20000 });
    const exportCall = seenParams.filter((p) => p.get('limit') === '200');
    expect(exportCall.length).toBeGreaterThan(0);
    expect(exportCall[0]?.get('action')).toBeNull();
  });

  it('⚠️ 输入框改了筛选但**没点查询** ⇒ 明说导出仍按**已应用**的条件', async () => {
    // ⚠️ 不给提示的话，用户会以为「我填了条件，导出怎么还是全部？」
    await openAuditLogsTab();
    fireEvent.change(screen.getByTestId('audit-filter-action'), {
      target: { value: 'NEVER_APPLIED' },
    });
    await waitFor(() => expect(screen.getByTestId('audit-filter-pending-hint')).toBeTruthy());
    expect(screen.getByTestId('audit-filter-pending-hint').textContent).toContain('查询');
  });

  it('⚠️ 评审 #10：翻页用**已应用**的筛选（改了没点「查询」⇒ 翻页不得偷换条件）', async () => {
    // ⚠️ `loadAuditLogs` 曾把 `setAppliedFilter(auditFilter)` 写在函数体里 ⇒
    //    effect 在**每次翻页**也调它 ⇒ 改了筛选没点查询、一点第 2 页：
    //    第 2 页用的是**新**条件（第 1 页还是旧的）⇒ 两页数据来自两个结果集，
    //    「未应用」提示条还消失了 —— 冻结只该发生在点「查询」时。
    totalRows = 120;
    await openAuditLogsTab();
    // 应用条件 A（点查询）
    fireEvent.change(screen.getByTestId('audit-filter-action'), {
      target: { value: 'APPLIED_A' },
    });
    fireEvent.click(screen.getByTestId('audit-filter-submit'));
    await waitFor(() => {
      const withA = seenParams.filter((p) => p.get('action') === 'APPLIED_A');
      expect(withA.length).toBeGreaterThan(0);
    });
    // 改成条件 B（**不点查询**）
    fireEvent.change(screen.getByTestId('audit-filter-action'), {
      target: { value: 'EDIT_B' },
    });
    await waitFor(() => expect(screen.getByTestId('audit-filter-pending-hint')).toBeTruthy());
    seenParams = [];
    // 翻到第 2 页 ⇒ 必须仍按 A 查
    fireEvent.click(screen.getByTitle('2'));
    await waitFor(() => expect(seenParams.length).toBeGreaterThan(0));
    const last = seenParams[seenParams.length - 1];
    expect(last?.get('action')).toBe('APPLIED_A');
    // 提示条**还在**（条件仍未应用）
    expect(screen.getByTestId('audit-filter-pending-hint').textContent).toContain('查询');
  });

  it('⚠️ 导出**第一列是 `audit_id`（LogID）** ⇒ 能回指原审计行', async () => {
    // ⚠️ 同一秒的多条记录靠 `occurred_at` **分不开** ⇒ 没有 LogID ⇒ 合规场景
    //    拿这份 CSV 当证据时**无法回指**。
    await openAuditLogsTab();
    fireEvent.click(screen.getByTestId('audit-export-csv'));
    await waitFor(() => expect(blobs.length).toBe(1));
    const text = await readBlobText(blobs[0]);
    const rows = parseCsv(text);
    expect(rows[0][0]).toBe('audit_id');
    expect(rows[1][0]).toBe('a-1');
  });

  it('⚠️ 导出行数与后端 `total` **对不上** ⇒ 明说（可能重复 / 漏行）', async () => {
    // ⚠️ 后端按 `occurred_at DESC` 排序、**无 tiebreaker** ⇒ 并列行的 OFFSET
    //    分页**不稳定** ⇒ 同一行可能跨页出现两次、另一行永远不出现 ⇒ 导出的
    //    CSV 行数 ≠ 结果集行数 ⇒ 文案写「全部结果」就是**骗人**。
    //    ⇒ 收集完与 `total` 核对，对不上就明说。
    totalRows = 5; // ⚠️ 后端说 5 行，但每页只给 2 行 ⇒ 实际只拿到 2 行 ⇒ 对不上
    await openAuditLogsTab();
    fireEvent.click(screen.getByTestId('audit-export-csv'));
    await waitFor(() => expect(screen.getByTestId('audit-export-notice')).toBeTruthy());
    const notice = screen.getByTestId('audit-export-notice').textContent ?? '';
    expect(notice).toContain('不一致');
  });

  it('⚠️ 筛选条件**原样**传给后端（不改参数名）', async () => {
    await openAuditLogsTab();
    fireEvent.change(screen.getByTestId('audit-filter-action'), {
      target: { value: 'RECORD_EDITED' },
    });
    fireEvent.click(screen.getByTestId('audit-filter-submit'));

    await waitFor(() => expect(listCalls).toBeGreaterThan(1));
    const last = seenParams[seenParams.length - 1];
    expect(last?.get('action')).toBe('RECORD_EDITED');
  });
});
