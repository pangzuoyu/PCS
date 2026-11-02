/**
 * 物流详情页 7 Tab 测试（SPEC §7.7.2 · P9B-3 · T8）。
 *
 * 守三件事：
 * 1. 7 个 Tab **都在**（label 逐个断言）
 * 2. ⚠️ **校核记录 Tab** 调 `GET /audit-logs` 且带 `resource_type=streams` +
 *    `resource_id=<id>` ⇒ **只显示校对相关**的行（其它 transition 不出现）
 * 3. **组成 Tab** 底部显示合计 + 超出 100±0.5% 时**标红**
 *
 * ⚠️ 只有**当前 Tab** 会取数（antd 的 Tabs 懒渲染未激活面板）⇒ 打开详情页
 * **不会**打 4 个请求 ⇒ 断言 2 必须**先切到「校核记录」Tab**。
 */
import { describe, it, expect, beforeAll, afterAll, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';

import { StreamDetailPage } from '../../../src/pages/sim/StreamDetailPage';
import type { Stream } from '../../../src/types/stream';

const stream: Stream = {
  stream_id: 's-1',
  stream_name: '新鲜进料',
  phase: 'LIQUID',
  temp: 25,
  press: 0.5,
  mass_flow: 10000,
  molar_flow: 100,
  composition_json: { N2: 0.78, O2: 0.21, H2O: 0.01 },
  sign_status: 'CHECKED',
  record_hash: 'a3f9b2e1c21ed7a8',
  case_type: 'NORMAL',
  data_mode: 'CHEMICAL',
  source_type: 'MANUAL_ENTRY',
  source: 'MANUAL',
  approval_depth: 2,
  created_at: '2026-09-15 14:00',
  updated_at: '2026-09-15 14:32',
};

/** 校核记录请求的 URL（断言 query 参数）。 */
let auditUrls: string[] = [];

const server = setupServer(
  http.get('/api/v1/audit-logs', ({ request }) => {
    auditUrls.push(request.url);
    return HttpResponse.json({
      items: [
        {
          audit_id: 'a-1',
          user_id: 'u-1',
          action: 'RECORD_TRANSITION',
          resource_type: 'streams',
          resource_id: 's-1',
          detail_json: { transition: 'SUBMIT_FOR_CHECK' },
          occurred_at: '2026-09-15 14:00',
        },
        {
          audit_id: 'a-2',
          user_id: 'u-2',
          action: 'RECORD_TRANSITION',
          resource_type: 'streams',
          resource_id: 's-1',
          detail_json: { transition: 'PASS_CHECK' },
          occurred_at: '2026-09-15 15:00',
        },
        {
          audit_id: 'a-3',
          user_id: 'u-3',
          action: 'RECORD_TRANSITION',
          resource_type: 'streams',
          resource_id: 's-1',
          // ⚠️ **不是**校对相关的 transition ⇒ 不得显示
          detail_json: { transition: 'MARK_STALE' },
          occurred_at: '2026-09-15 16:00',
        },
      ],
      total: 3,
      limit: 50,
      offset: 0,
    });
  }),
  http.get('/api/v1/streams/:stream_id/properties', () =>
    HttpResponse.json({
      stream_id: 's-1',
      user_provided: { density: 800 },
      calculated: { density: 799.5 },
      effective: { density: 800 },
      conflict_resolutions: {},
    }),
  ),
  http.get('/api/v1/streams/:stream_id/state-points', () =>
    HttpResponse.json([
      {
        state_label: '设计工况',
        case_type: 'NORMAL',
        temp: 25,
        press: 0.5,
        phase: 'LIQUID',
        mass_flow: 10000,
        vapor_fraction: null,
      },
    ]),
  ),
  http.get('/api/v1/lineage/:record_type/:record_id/graph', () =>
    HttpResponse.json({
      root: {
        lineage_id: 'l-1',
        record_type: 'streams',
        record_id: 's-1',
        source: 'MANUAL_ENTRY',
        change_summary: '创建',
        occurred_at: '2026-09-15 14:00',
      },
      upstream: [],
      downstream: [],
    }),
  ),
);

/** 切到某个 Tab（antd 的 tab 标题在 `.ant-tabs-tab` 里）。 */
function clickTab(label: string): void {
  const tab = Array.from(document.querySelectorAll('.ant-tabs-tab')).find((el) =>
    el.textContent?.includes(label),
  );
  if (!tab) throw new Error(`找不到 Tab：${label}`);
  fireEvent.click(tab);
}

describe('StreamDetailPage —— 7 Tab（T8）', () => {
  beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
  afterAll(() => server.close());
  beforeEach(() => {
    auditUrls = [];
  });

  it('7 个 Tab 都在：基本信息 / 组成 / 物性 / 状态点 / 设备连接 / 血缘 / 校核记录', () => {
    render(<StreamDetailPage stream={stream} />);
    const tabs = screen.getByTestId('stream-detail-tabs').textContent ?? '';
    for (const label of [
      '基本信息',
      '组成',
      '物性',
      '状态点',
      '设备连接',
      '血缘',
      '校核记录',
    ]) {
      expect(tabs).toContain(label);
    }
  });

  it('⚠️ 校核记录 Tab ⇒ 带 resource_type/resource_id 请求，且**只显示校对相关**的行', async () => {
    render(<StreamDetailPage stream={stream} />);
    clickTab('校核记录');

    await waitFor(() => expect(auditUrls.length).toBe(1));
    expect(auditUrls[0]).toContain('resource_type=streams');
    expect(auditUrls[0]).toContain('resource_id=s-1');

    await waitFor(() => expect(screen.getByTestId('stream-tab-review-log')).toBeTruthy());
    // ⚠️ 校对相关的两条显示
    expect(document.body.textContent).toContain('提交校对');
    expect(document.body.textContent).toContain('校对通过');
    // ⚠️ **其它 transition 不显示**（MARK_STALE 不在校核记录里）
    expect(document.body.textContent).not.toContain('MARK_STALE');
  });

  it('⚠️ 未知 sign_status ⇒ 详情页**照常渲染**（徽章降级，不整页崩）', () => {
    // ⚠️ 计划 Review Focus #2 要求「钉在 T6（列表）**与 T8（详情）**」——
    //    T6 已钉（列表页有局部边界），详情页此前**整页崩**（StateBadge 在 DEV
    //    对未知状态抛错 ⇒ 整棵树被卸载 ⇒ 用户只看到「页面渲染异常」）。
    render(
      <StreamDetailPage
        stream={{
          ...stream,
          sign_status: 'SOMETHING_NEW' as unknown as Stream['sign_status'],
        }}
      />,
    );

    // 页面其余部分照常渲染
    expect(screen.getByTestId('stream-detail-page')).toBeTruthy();
    expect(screen.getByTestId('stream-detail-descriptions')).toBeTruthy();
    // 徽章**显形**「未知状态: X」（不回落成「草稿」—— 语义被静默改写更危险）
    expect(screen.getByTestId('state-badge-label').textContent).toContain('SOMETHING_NEW');
  });

  it('组成 Tab ⇒ 底部显示合计，超出 100±0.5% 时**标红**', async () => {
    render(<StreamDetailPage stream={stream} />);
    clickTab('组成');

    await waitFor(() => expect(screen.getByTestId('stream-composition-total')).toBeTruthy());
    const total = screen.getByTestId('stream-composition-total');
    // 0.78 + 0.21 + 0.01 = 1.0 ⇒ 在范围内
    expect(total.textContent).toContain('100.00%');
    expect(total.getAttribute('data-ok')).toBe('true');
  });

  it('组成合计超范围 ⇒ 标红（data-ok=false）', async () => {
    render(
      <StreamDetailPage stream={{ ...stream, composition_json: { N2: 0.6, O2: 0.387 } }} />,
    );
    clickTab('组成');

    await waitFor(() => expect(screen.getByTestId('stream-composition-total')).toBeTruthy());
    const total = screen.getByTestId('stream-composition-total');
    expect(total.getAttribute('data-ok')).toBe('false');
    expect(total.textContent).toContain('98.70%');
  });
});
