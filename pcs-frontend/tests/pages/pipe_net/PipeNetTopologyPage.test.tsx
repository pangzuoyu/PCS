/**
 * PipeNetTopologyPage 测试（P45-3-6 / Task 33）。
 */
import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';

import { PipeNetTopologyPage } from '../../../src/pages/pipe_net/PipeNetTopologyPage';
import type { PipeNetGraph } from '../../../src/types/pipeNet';

const graph: PipeNetGraph = {
  nodes: [
    { node_id: 'n1', tag_number: 'IN-1',  label: '主入口', kind: 'INLET',    x: 10, y: 10 },
    { node_id: 'n2', tag_number: 'E-101', label: '泵 P-101', kind: 'EQUIPMENT', x: 30, y: 30 },
    { node_id: 'n3', tag_number: 'J-1',   label: '三通',     kind: 'JUNCTION',  x: 50, y: 50 },
    { node_id: 'n4', tag_number: 'OUT-1', label: '出口',     kind: 'OUTLET',    x: 80, y: 80 },
    { node_id: 'n5', tag_number: 'ORPHAN', label: '孤立',    kind: 'JUNCTION',  x: 20, y: 80 },
  ],
  edges: [
    { edge_id: 'e1', pipe_no: 'P-101', from_node_id: 'n1', to_node_id: 'n2' },
    { edge_id: 'e2', pipe_no: 'P-102', from_node_id: 'n2', to_node_id: 'n3' },
    { edge_id: 'e3', pipe_no: 'P-103', from_node_id: 'n3', to_node_id: 'n4' },
  ],
};

describe('PipeNetTopologyPage — 渲染 (P45-3-6)', () => {
  it('渲染 PageHeader + 校验 / 导出按钮', () => {
    render(<PipeNetTopologyPage graph={graph} />);
    expect(screen.getByTestId('pipe-net-topology-page')).toBeTruthy();
    expect(screen.getByTestId('pipe-net-validate')).toBeTruthy();
    expect(screen.getByTestId('pipe-net-export')).toBeTruthy();
  });

  it('SVG 画布：节点数 = 5（IN-1 / E-101 / J-1 / OUT-1 / ORPHAN）', () => {
    render(<PipeNetTopologyPage graph={graph} />);
    const nodes = document.querySelectorAll('[data-testid="pipe-net-node"]');
    expect(nodes.length).toBe(5);
  });

  it('SVG 画布：管道边数 = 3', () => {
    render(<PipeNetTopologyPage graph={graph} />);
    const edges = document.querySelectorAll('[data-testid="pipe-net-edge"]');
    expect(edges.length).toBe(3);
  });

  it('节点 Table：5 行', () => {
    render(<PipeNetTopologyPage graph={graph} />);
    const nodeRows = document.querySelectorAll('.ant-table-tbody tr');
    // 节点表 5 + 边表 3 = 8 行
    expect(nodeRows.length).toBe(8);
  });

  it('节点类型 Tag：INLET / EQUIPMENT / JUNCTION / OUTLET 标签', () => {
    render(<PipeNetTopologyPage graph={graph} />);
    expect(document.body.textContent).toContain('入口');
    expect(document.body.textContent).toContain('设备');
    expect(document.body.textContent).toContain('连接点');
    expect(document.body.textContent).toContain('出口');
  });
});

describe('PipeNetTopologyPage — 校验 (P45-3-6)', () => {
  it('孤立节点：ORPHAN (n5) 无任何边 → 显示孤立警告', () => {
    render(<PipeNetTopologyPage graph={graph} />);
    const alert = screen.getByTestId('pipe-net-warning-orphans');
    expect(alert).toBeTruthy();
    expect(alert.textContent).toContain('ORPHAN');
  });

  it('重复 tag 检测：手动构造重复', () => {
    const dupGraph: PipeNetGraph = {
      nodes: [
        { node_id: 'n1', tag_number: 'DUP', label: 'A', kind: 'INLET', x: 10, y: 10 },
        { node_id: 'n2', tag_number: 'DUP', label: 'B', kind: 'OUTLET', x: 80, y: 80 },
      ],
      edges: [{ edge_id: 'e1', pipe_no: 'P-1', from_node_id: 'n1', to_node_id: 'n2' }],
    };
    render(<PipeNetTopologyPage graph={dupGraph} />);
    const alert = screen.getByTestId('pipe-net-warning-dup');
    expect(alert).toBeTruthy();
    expect(alert.textContent).toContain('DUP');
  });

  it('无孤立 + 无重复 → 不显示警告', () => {
    const cleanGraph: PipeNetGraph = {
      nodes: [
        { node_id: 'n1', tag_number: 'A', label: 'A', kind: 'INLET', x: 10, y: 10 },
        { node_id: 'n2', tag_number: 'B', label: 'B', kind: 'OUTLET', x: 80, y: 80 },
      ],
      edges: [{ edge_id: 'e1', pipe_no: 'P-1', from_node_id: 'n1', to_node_id: 'n2' }],
    };
    render(<PipeNetTopologyPage graph={cleanGraph} />);
    expect(screen.queryByTestId('pipe-net-warning-orphans')).toBeNull();
    expect(screen.queryByTestId('pipe-net-warning-dup')).toBeNull();
  });

  it('onValidate 自定义：返回值替代默认', () => {
    const onValidate = vi.fn(() => ({
      orphans: ['CUSTOM'],
      duplicate_tags: [],
      cycles: [['n1', 'n2']],
    }));
    render(<PipeNetTopologyPage graph={graph} onValidate={onValidate} />);
    expect(screen.getByTestId('pipe-net-warning-orphans').textContent).toContain('CUSTOM');
  });
});

describe('PipeNetTopologyPage — 操作 (P45-3-6)', () => {
  it('导出按钮 → onExport 回调', () => {
    const onExport = vi.fn();
    render(<PipeNetTopologyPage graph={graph} onExport={onExport} />);
    const btn = screen.getByTestId('pipe-net-export');
    btn.click();
    expect(onExport).toHaveBeenCalledWith(graph);
  });

  it('空 graph（无节点）→ 显示 Empty', () => {
    render(<PipeNetTopologyPage graph={{ nodes: [], edges: [] }} />);
    expect(document.body.textContent).toContain('无节点');
  });

  it('边 Table：from / to 显示节点 tag_number', () => {
    render(<PipeNetTopologyPage graph={graph} />);
    expect(document.body.textContent).toContain('IN-1');
    expect(document.body.textContent).toContain('E-101');
  });

  it('边 Table：边引用了不存在的节点 → line 不渲染（优雅降级）', () => {
    const brokenGraph: PipeNetGraph = {
      nodes: [{ node_id: 'n1', tag_number: 'A', label: 'A', kind: 'INLET', x: 10, y: 10 }],
      edges: [{ edge_id: 'e1', pipe_no: 'P-1', from_node_id: 'n1', to_node_id: 'NONEXISTENT' }],
    };
    render(<PipeNetTopologyPage graph={brokenGraph} />);
    const edges = document.querySelectorAll('[data-testid="pipe-net-edge"]');
    expect(edges.length).toBe(0);
  });

  it('画布节点 ID 数据属性正确', () => {
    render(<PipeNetTopologyPage graph={graph} />);
    const node = document.querySelector('[data-node-id="n2"]');
    expect(node).toBeTruthy();
    expect(node!.textContent).toContain('E-101');
  });
});