/**
 * 物流详情 —— 「组成」Tab（SPEC §7.7.2 · P9B-3 · T8）。
 *
 * ⚠️ **底部合计校验（100±0.5%）** —— 与后端**同口径**（SPEC §7.7.2）：
 * - 值域是 **0~1 的小数**（不是百分数）⇒ 判定 `|合计 − 1| ≤ 0.005`；
 * - `null`（**无组成**）⇒ **跳过**校验；
 * - `{}`（**未填写**）⇒ 合计 0 ⇒ **标红**（未填写 ≠ 无组成）。
 *
 * ⚠️ 组分值**不保证是数字**（契约里是 `unknown`）⇒ 非数值**不计入合计**，
 * 并在底部标出来 —— 不能把非数值当 0 静默算出一个「看起来对」的合计。
 */
import { Card, Table, Typography } from 'antd';

import type { Stream } from '../../../types/stream';

interface CompositionRow {
  component: string;
  mole_fraction: unknown;
}

export function StreamCompositionTab({ stream }: { stream: Stream }): JSX.Element {
  // ⚠️ `composition_json` 可空（契约）⇒ `Object.entries(null)` 会崩
  const rows: CompositionRow[] = Object.entries(stream.composition_json ?? {}).map(
    ([component, mole_fraction]) => ({ component, mole_fraction }),
  );

  const numeric = rows.filter((r) => typeof r.mole_fraction === 'number');
  const nonNumeric = rows.length - numeric.length;
  const total = numeric.reduce((acc, r) => acc + (r.mole_fraction as number), 0);
  // ⚠️ `null`（无组成）⇒ 跳过校验；`{}`（未填写）⇒ 合计 0 ⇒ 标红
  const hasComposition = stream.composition_json !== null && stream.composition_json !== undefined;
  const ok = !hasComposition || Math.abs(total - 1) <= 0.005;

  return (
    <div data-testid="stream-tab-composition">
      <Card title="组成（摩尔分率）" size="small">
        <Table<CompositionRow>
          rowKey="component"
          columns={[
            { title: '组分', dataIndex: 'component', width: 160 },
            {
              title: '摩尔分率',
              dataIndex: 'mole_fraction',
              width: 160,
              render: (v: unknown) => (typeof v === 'number' ? v.toFixed(4) : String(v ?? '—')),
            },
          ]}
          dataSource={rows}
          pagination={false}
          size="small"
          onRow={(_, idx) =>
            ({
              'data-testid': 'stream-composition-row',
              'data-component-index': idx,
            }) as React.HTMLAttributes<HTMLElement>
          }
        />
        {/* ⚠️ 底部合计校验 —— 超出 100±0.5% 标红（与后端送审门禁同口径）*/}
        <Typography.Text
          data-testid="stream-composition-total"
          data-ok={String(ok)}
          type={ok ? undefined : 'danger'}
          style={{ display: 'block', marginTop: 12 }}
        >
          合计 {(total * 100).toFixed(2)}%（应在 100±0.5%）
          {nonNumeric > 0 && ` ⚠ 有 ${nonNumeric} 个组分的值不是数字，未计入合计`}
        </Typography.Text>
      </Card>
    </div>
  );
}

export default StreamCompositionTab;
