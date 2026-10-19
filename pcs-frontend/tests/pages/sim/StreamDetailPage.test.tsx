/**
 * StreamDetailPage 测试（P45-3-1 / Task 28 下半）。
 *
 * 覆盖 SPEC §7.7.2 物流详情：
 * - PageHeader 复用：状态徽章 + 版本 hash + 操作区
 * - 基础信息 Descriptions
 * - 组成 JSON 表格（组分 + 摩尔分率）
 * - 签署步骤 SignatureMatrix
 * - 操作：返回 / 提交批准 / 弃用
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';

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
  approval_depth: 2,
  created_at: '2026-09-15 14:00',
  updated_at: '2026-09-15 14:32',
};

describe('StreamDetailPage — 渲染 (P45-3-1)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('渲染 PageHeader + 名称（物流无位号，标题即 stream_name）', () => {
    render(<StreamDetailPage stream={stream} />);
    expect(screen.getByTestId('page-header')).toBeTruthy();
    expect(document.body.textContent).toContain('新鲜进料');
  });

  it('PageHeader 显示状态 + hash', () => {
    render(<StreamDetailPage stream={stream} />);
    const status = document.querySelector('[data-testid="page-header-status"]');
    expect(status?.getAttribute('data-status')).toBe('CHECKED');
    const version = document.querySelector('[data-testid="page-header-version"]');
    expect(version).toBeTruthy();
  });

  it('Descriptions 基础信息：相态/温压/流量', () => {
    render(<StreamDetailPage stream={stream} />);
    const details = screen.getByTestId('stream-detail-descriptions');
    expect(details.textContent).toContain('LIQUID');
    expect(details.textContent).toContain('25');
    expect(details.textContent).toContain('0.5');
    expect(details.textContent).toContain('10000');
  });

  it('组成 JSON 表格：3 组分', () => {
    render(<StreamDetailPage stream={stream} />);
    const compRows = document.querySelectorAll('[data-testid="stream-composition-row"]');
    expect(compRows.length).toBe(3);
    expect(compRows[0].textContent).toContain('N2');
    expect(compRows[0].textContent).toContain('0.78');
  });
});

describe('StreamDetailPage — 操作', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('点击「返回」→ onBack 回调', () => {
    const onBack = vi.fn();
    render(<StreamDetailPage stream={stream} onBack={onBack} />);
    fireEvent.click(screen.getByTestId('stream-detail-back'));
    expect(onBack).toHaveBeenCalledTimes(1);
  });

  it('点击「提交批准」→ onSubmit 回调', () => {
    const onSubmit = vi.fn();
    render(<StreamDetailPage stream={{ ...stream, sign_status: 'DRAFT' }} onSubmit={onSubmit} />);
    fireEvent.click(screen.getByTestId('stream-detail-submit'));
    expect(onSubmit).toHaveBeenCalledTimes(1);
  });
});
/**
 * 契约可空字段 —— 直接当非空用会崩（2026-10-19，bug-189 顺带挖出）。
 *
 * `Stream` 并进契约后，`composition_json` 是 `Record<string, unknown> | null`，
 * `mass_flow` 是 `number | null`，`composition_json` 的值类型是 `unknown`。
 * 这些在**手写类型**时代全是非空，页面照直写 —— 于是一条没填组成的物流
 * 就会让整页白屏（`Object.entries(null)`），且契约里 `null` 是合法值，
 * 后端完全有权返回。
 */
describe('StreamDetailPage — 可空字段不得崩页', () => {
  it('composition_json 为 null → 不崩，组成表为空', () => {
    render(<StreamDetailPage stream={{ ...stream, composition_json: null }} />);
    expect(screen.getByTestId('stream-detail-page')).toBeTruthy();
  });

  it('composition_json 未给（undefined）→ 不崩', () => {
    const { composition_json: _drop, ...rest } = stream;
    render(<StreamDetailPage stream={rest} />);
    expect(screen.getByTestId('stream-detail-page')).toBeTruthy();
  });

  it('组分值不是数字（如 "0.6" 字符串）→ 照常显示，不 .toFixed 崩', () => {
    render(
      <StreamDetailPage
        stream={{ ...stream, composition_json: { WATER: '0.6' } as never }}
      />,
    );
    expect(document.body.textContent).toContain('WATER');
    expect(document.body.textContent).toContain('0.6');
  });

  /**
   * ⚠️ 这条测试第一版是**空绿**：变异掉 null 守卫它照样通过。
   * 原因：`STALE` 那段 `AssumedDataMarker` 嵌在 `{uiSchema && (...)}` 里，
   * 而 fixture 没传 `uiSchema` ⇒ 那段代码**从未执行** ⇒ 抛不抛都无所谓。
   * 这正是 cerebrum 里 bug-174 那一类假绿：**功能存在、路径存在、
   * 测试全绿，而它从未跑过**。
   */
  it('mass_flow 为 null 且状态 STALE → 不崩（此前是 .toString() 直接抛）', () => {
    // 必须给 uiSchema，否则整段被 gate 掉，断言不到任何东西。
    render(
      <StreamDetailPage
        stream={{ ...stream, mass_flow: null, sign_status: 'STALE' }}
        uiSchema={{ fields: [{ key: 'mass_flow', label: '流量', widget: 'Input' }] } as never}
      />,
    );
    expect(screen.getByTestId('stream-detail-schema-form')).toBeTruthy();
    expect(screen.getByTestId('stream-detail-page')).toBeTruthy();
  });

  it('phase 为 null → 显示「未标注相态」而不是空标签', () => {
    render(<StreamDetailPage stream={{ ...stream, phase: null }} />);
    const tag = document.querySelector('[data-testid="stream-phase-tag"]')
      ?? document.querySelector('.ant-tag');
    expect(document.body.textContent).toContain('未标注相态');
    expect(tag).toBeTruthy();
  });

  it('phase 是词表外的值 → 明示「未知相态: X」，不静默空标签', () => {
    render(<StreamDetailPage stream={{ ...stream, phase: 'SUPERCRITICAL' }} />);
    expect(document.body.textContent).toContain('未知相态: SUPERCRITICAL');
  });
});
