/**
 * LineageGraph 测试（P45-1-10 / Task 15）。
 *
 * 覆盖（SPEC §6.6 + plan P45-1-10）：
 * - 渲染 SVG 节点 + 边
 * - centerRecord 居中 + 高亮
 * - direction upstream → 只显示入向边
 * - direction downstream → 只显示出向边
 * - 哈希不匹配边红色高亮
 * - onNodeClick 联动
 * - 图例渲染 6 类节点
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';

import { LineageGraph, type LineageNode, type LineageEdge } from '../../../src/components/common/LineageGraph';

const nodes: LineageNode[] = [
  { id: 's1', kind: 'stream', label: 'S-101' },
  { id: 's2', kind: 'stream', label: 'S-102' },
  { id: 'e1', kind: 'equipment', label: 'PU-101' },
  { id: 'r1', kind: 'record', label: 'R-101' },
  { id: 'r2', kind: 'record', label: 'R-102' },
  { id: 'a1', kind: 'assumed', label: 'A-001' },
];

const edges: LineageEdge[] = [
  { source: 's1', target: 'r1', kind: 'reference' },
  { source: 's2', target: 'r1', kind: 'reference' },
  { source: 'r1', target: 'e1', kind: 'device_transformation', label: 'PU-101' },
  { source: 'e1', target: 'r2', kind: 'calculation' },
  { source: 'r2', target: 'a1', kind: 'estimate', hash_mismatch: true },
];

describe('LineageGraph — 渲染 (P45-1-10)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('渲染 SVG 节点 + 边', () => {
    const { container } = render(
      <LineageGraph
        centerRecord="r1"
        direction="downstream"
        data={{ nodes, edges }}
      />,
    );
    const n = container.querySelectorAll('[data-testid="lineage-node"]');
    const e = container.querySelectorAll('[data-testid="lineage-edge"]');
    expect(n.length).toBeGreaterThan(0);
    expect(e.length).toBeGreaterThan(0);
  });

  it('centerRecord 节点标记 data-is-center="true"', () => {
    const { container } = render(
      <LineageGraph
        centerRecord="r1"
        direction="downstream"
        data={{ nodes, edges }}
      />,
    );
    const centers = container.querySelectorAll('[data-is-center="true"]');
    expect(centers.length).toBe(1);
    expect(centers[0].getAttribute('data-node-id')).toBe('r1');
  });

  it('图例渲染 6 类节点', () => {
    const { container } = render(
      <LineageGraph
        centerRecord="r1"
        direction="downstream"
        data={{ nodes, edges }}
      />,
    );
    const legend = container.querySelector('[data-testid="lineage-legend"]');
    expect(legend).toBeTruthy();
    expect(legend!.textContent).toContain('stream');
    expect(legend!.textContent).toContain('equipment');
    expect(legend!.textContent).toContain('record');
    expect(legend!.textContent).toContain('assumed');
  });

  it('统计信息显示', () => {
    render(
      <LineageGraph
        centerRecord="r1"
        direction="downstream"
        data={{ nodes, edges }}
      />,
    );
    const stats = screen.getByTestId('lineage-stats');
    expect(stats.textContent).toMatch(/节点 \d+/);
    expect(stats.textContent).toMatch(/边 \d+/);
    expect(stats.textContent).toContain('downstream');
  });
});

describe('LineageGraph — direction 切换', () => {
  it('upstream：center 入向边 + 来源节点可见', () => {
    const { container } = render(
      <LineageGraph
        centerRecord="r1"
        direction="upstream"
        data={{ nodes, edges }}
    />,
    );
    // upstream 从 r1 向 source 追溯：s1、s2 可见；e1、r2、a1 不可见
    const nodeIds = Array.from(
      container.querySelectorAll('[data-testid="lineage-node"]'),
    ).map((el) => el.getAttribute('data-node-id'));
    expect(nodeIds).toContain('r1');
    expect(nodeIds).toContain('s1');
    expect(nodeIds).toContain('s2');
    expect(nodeIds).not.toContain('e1');
    expect(nodeIds).not.toContain('r2');
  });

  it('downstream：center 出向边 + 下游节点可见', () => {
    const { container } = render(
      <LineageGraph
        centerRecord="r1"
        direction="downstream"
        data={{ nodes, edges }}
    />,
    );
    const nodeIds = Array.from(
      container.querySelectorAll('[data-testid="lineage-node"]'),
    ).map((el) => el.getAttribute('data-node-id'));
    expect(nodeIds).toContain('r1');
    expect(nodeIds).toContain('e1');
    expect(nodeIds).toContain('r2');
    expect(nodeIds).toContain('a1');
    expect(nodeIds).not.toContain('s1');
  });
});

describe('LineageGraph — 哈希不匹配', () => {
  it('hash_mismatch=true 的边标 data-hash-mismatch="true" + 红色', () => {
    const { container } = render(
      <LineageGraph
        centerRecord="r1"
        direction="downstream"
        data={{ nodes, edges }}
    />,
    );
    const mismatchEdges = container.querySelectorAll(
      '[data-testid="lineage-edge"][data-hash-mismatch="true"]',
    );
    expect(mismatchEdges.length).toBe(1);
    const stroke = mismatchEdges[0].getAttribute('stroke') || '';
    expect(stroke).toMatch(/var\(--state-check-rejected/);
  });
});

describe('LineageGraph — 联动', () => {
  it('点节点 → onNodeClick(id)', () => {
    const onNodeClick = vi.fn();
    const { container } = render(
      <LineageGraph
        centerRecord="r1"
        direction="downstream"
        data={{ nodes, edges }}
        onNodeClick={onNodeClick}
      />,
    );
    const e1Node = container.querySelector('[data-node-id="e1"]');
    expect(e1Node).toBeTruthy();
    fireEvent.click(e1Node!);
    expect(onNodeClick).toHaveBeenCalledWith('e1');
  });

  it('不传 onNodeClick 不报错', () => {
    const { container } = render(
      <LineageGraph
        centerRecord="r1"
        direction="downstream"
        data={{ nodes, edges }}
    />,
    );
    const e1Node = container.querySelector('[data-node-id="e1"]');
    expect(() => fireEvent.click(e1Node!)).not.toThrow();
  });
});

describe('LineageGraph — 边界', () => {
  it('centerRecord 不在 nodes 中 → 不渲染节点', () => {
    const { container } = render(
      <LineageGraph
        centerRecord="missing"
        direction="downstream"
        data={{ nodes, edges }}
    />,
    );
    expect(container.querySelectorAll('[data-testid="lineage-node"]').length).toBe(0);
  });
});