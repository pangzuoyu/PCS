/**
 * 物流详情 —— 「状态点」Tab（SPEC §7.7.2 · P9B-3 · T8）。
 *
 * 数据源：`GET /streams/{id}/state-points` ⇒ 状态点行数组。
 *
 * ⚠️ 契约里是**裸 object 数组** ⇒ 每行字段都可能缺 ⇒ 全部**防御性**读
 * （值类型一律可选）。
 */
import { useEffect, useState } from 'react';
import { Alert, Card, Table } from 'antd';

import { streamApi, type StreamStatePoint } from '../../../api/stream';
import { describePcsError } from '../../../api/errors';

function num(v: number | null | undefined): string {
  return v === null || v === undefined ? '—' : String(v);
}

/** 行 + **稳定 key** —— ⚠️ antd 5.29 弃用 `rowKey` 函数的 `index` 参数。 */
interface StatePointRow extends StreamStatePoint {
  key: string;
}

export function StreamStatePointsTab({ streamId }: { streamId: string }): JSX.Element {
  const [rows, setRows] = useState<StatePointRow[]>([]);
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setErrorMsg(null);
    streamApi
      .statePoints(streamId)
      .then((res) => {
        // ⚠️ key 在**取数时**算好（不用 antd 的 rowKey 回调 —— 它的 index
        //    参数在 antd 5.29 已弃用，且会刷一条**错误级**控制台消息）。
        if (!cancelled) {
          setRows((res ?? []).map((r, i) => ({ ...r, key: r.state_label ?? `sp-${i}` })));
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) setErrorMsg(describePcsError(err, '加载状态点失败'));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [streamId]);

  if (errorMsg) {
    return (
      <div data-testid="stream-tab-state-points">
        <Alert type="error" showIcon message={errorMsg} data-testid="stream-state-points-error" />
      </div>
    );
  }

  return (
    <div data-testid="stream-tab-state-points">
      <Card title="状态点" size="small">
        <Table<StatePointRow>
          size="small"
          rowKey="key"
          loading={loading}
          dataSource={rows}
          pagination={false}
          columns={[
            { title: '标签', dataIndex: 'state_label', width: 160 },
            { title: '类型', dataIndex: 'case_type', width: 100 },
            {
              title: '温度 (°C)',
              dataIndex: 'temp',
              width: 110,
              render: (v: number | null | undefined) => num(v),
            },
            {
              title: '压力 (MPaG)',
              dataIndex: 'press',
              width: 110,
              render: (v: number | null | undefined) => num(v),
            },
            {
              title: '相态',
              dataIndex: 'phase',
              width: 90,
              render: (v: string | null | undefined) => v ?? '—',
            },
            {
              title: '汽化分率',
              dataIndex: 'vapor_fraction',
              width: 100,
              render: (v: number | null | undefined) => num(v),
            },
            {
              title: '质量流量 (kg/h)',
              dataIndex: 'mass_flow',
              width: 130,
              render: (v: number | null | undefined) => num(v),
            },
          ]}
        />
      </Card>
    </div>
  );
}

export default StreamStatePointsTab;
