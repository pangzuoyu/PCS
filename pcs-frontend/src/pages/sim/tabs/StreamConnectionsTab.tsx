/**
 * 物流详情 —— 「设备连接」Tab（SPEC §7.7.2 · P9B-3 · T8）。
 *
 * 数据源：**物流自身**的上游字段（`upstream_stream_id` /
 * `upstream_equipment_id` / `upstream_equipment_type`）—— 契约里就有
 * ⇒ **不需要**额外端点。
 *
 * ⚠️ **下游**（谁用了我）不在物流自身字段里 ⇒ 要靠血缘图（血缘 Tab）；
 * 本 Tab 只显示**上游**（我来自谁）⇒ 不猜、不编。
 */
import { Card, Descriptions } from 'antd';

import type { Stream } from '../../../types/stream';

export function StreamConnectionsTab({ stream }: { stream: Stream }): JSX.Element {
  return (
    <div data-testid="stream-tab-connections">
      <Card title="设备连接（上游）" size="small">
        <Descriptions
          column={1}
          bordered
          size="small"
          data-testid="stream-connections-descriptions"
        >
          <Descriptions.Item label="上游物流">
            {stream.upstream_stream_id ?? '—'}
          </Descriptions.Item>
          <Descriptions.Item label="上游设备">
            {stream.upstream_equipment_id ?? '—'}
          </Descriptions.Item>
          <Descriptions.Item label="上游设备类型">
            {stream.upstream_equipment_type ?? '—'}
          </Descriptions.Item>
        </Descriptions>
      </Card>
    </div>
  );
}

export default StreamConnectionsTab;
