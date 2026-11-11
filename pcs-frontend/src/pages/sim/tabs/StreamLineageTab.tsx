/**
 * 物流详情 —— 「血缘」Tab（SPEC §7.7.2 · P9B-3 · T8）。
 *
 * 数据源：`GET /lineage/{record_type}/{record_id}/graph`（`record_type=streams`）
 * ⇒ `{root, upstream, downstream}`（**契约派生** · P9B-4 T0-D）。
 *
 * ⚠️ **两套词表**（T0-D）：`source` 在**根节点**上是**物流来源**（录入通道
 *    `MANUAL` / `SIM_IMPORT` / `EXCEL` / `LAB`），在**血缘行**上是**计算来源**
 *    （`CALC` 等）⇒ 同一列会出现两种词 ⇒ 根行加 tooltip 说清是哪一种。
 * ⚠️ 血缘图组件（`LineageGraph`）要的是**前端合成的** `{center, nodes, edges}`
 *    形状 ⇒ 那是前端自己造的（bug-189 同族）⇒ 本 Tab **不**套它，
 *    直接把后端返回的 root/upstream/downstream **如实**列出来。
 */
import { useEffect, useState } from 'react';
import { Alert, Card, Table, Tooltip, Typography } from 'antd';

import { streamApi, type LineageGraph, type LineageNode } from '../../../api/stream';
import { describePcsError } from '../../../api/errors';

interface Row {
  key: string;
  relation: string;
  entry: LineageNode;
}

/**
 * 物流**录入通道**（`StreamSource` 4 值）的中文标签。
 *
 * ⚠️ 与 `StreamSourceType`（13 值 · 数据怎么算出来的）**不是一回事** ⇒
 * 这里只覆盖**录入通道**那 4 个值。
 */
const STREAM_SOURCE_LABEL: Record<string, string> = {
  MANUAL: '手动创建',
  SIM_IMPORT: '模拟软件导出',
  EXCEL: 'Excel 导入',
  LAB: '化验报告',
};

function toRows(graph: LineageGraph | null): Row[] {
  if (!graph) return [];
  const rows: Row[] = [];
  if (graph.root) rows.push({ key: 'root', relation: '当前', entry: graph.root });
  (graph.upstream ?? []).forEach((entry, i) =>
    rows.push({ key: `up-${i}`, relation: '上游', entry }),
  );
  (graph.downstream ?? []).forEach((entry, i) =>
    rows.push({ key: `down-${i}`, relation: '下游', entry }),
  );
  return rows;
}

function text(v: string | null | undefined): string {
  return v === null || v === undefined || v === '' ? '—' : v;
}

export function StreamLineageTab({ streamId }: { streamId: string }): JSX.Element {
  const [graph, setGraph] = useState<LineageGraph | null>(null);
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setErrorMsg(null);
    streamApi
      .lineageGraph('streams', streamId)
      .then((res) => {
        if (!cancelled) setGraph(res);
      })
      .catch((err: unknown) => {
        if (!cancelled) setErrorMsg(describePcsError(err, '加载血缘失败'));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [streamId]);

  const rows = toRows(graph);

  return (
    <div data-testid="stream-tab-lineage">
      {errorMsg && (
        <Alert type="error" showIcon message={errorMsg} data-testid="stream-lineage-error" />
      )}
      <Card title="数据血缘" size="small">
        {rows.length === 0 ? (
          <Typography.Text type="secondary">
            {loading ? '加载中…' : '（无血缘记录）'}
          </Typography.Text>
        ) : (
          <Table<Row>
            size="small"
            rowKey="key"
            loading={loading}
            dataSource={rows}
            pagination={false}
            columns={[
              { title: '关系', dataIndex: 'relation', width: 80 },
              {
                title: '记录',
                dataIndex: ['entry', 'record_type'],
                width: 140,
                render: (_: unknown, row: Row) =>
                  `${text(row.entry.record_type)} / ${text(row.entry.record_id)}`,
              },
              {
                title: '来源',
                dataIndex: ['entry', 'source'],
                width: 140,
                render: (_: unknown, row: Row) => {
                  const value = text(row.entry.source);
                  // ⚠️ 根行是**合成**的 ⇒ 它的 source 是**物流来源**（录入通道），
                  //    其余行的 source 是**计算来源**（CALC 等）⇒ 两套词表 ⇒
                  //    根行加 tooltip 说清是哪一种（SPEC §7.7.2）。
                  if (row.relation !== '当前') return value;
                  const label = STREAM_SOURCE_LABEL[value];
                  return (
                    <Tooltip
                      title={
                        label
                          ? `物流来源（录入通道）：${value} = ${label}`
                          : `物流来源（录入通道）：${value}`
                      }
                    >
                      <span>{value}</span>
                    </Tooltip>
                  );
                },
              },
              {
                title: '变更摘要',
                dataIndex: ['entry', 'change_summary'],
                render: (_: unknown, row: Row) => text(row.entry.change_summary),
              },
              {
                title: '时间',
                dataIndex: ['entry', 'occurred_at'],
                width: 180,
                render: (_: unknown, row: Row) => text(row.entry.occurred_at),
              },
            ]}
          />
        )}
      </Card>
    </div>
  );
}

export default StreamLineageTab;
