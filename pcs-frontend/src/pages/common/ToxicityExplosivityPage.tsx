/**
 * ToxicityExplosivityPage — 毒性爆炸（P45-3-3 / Task 30）。
 *
 * SPEC §7.8.3：
 * - 按 hazard_class（LOW / MEDIUM / HIGH）分组
 * - 每组：组分 + LD50 + PEL + 爆炸极限 LEL/UEL
 * - HIGH 红警 + MEDIUM 黄警 + LOW 蓝标
 *
 * Props：
 *   classes: ToxicityClass[]
 */
import { useMemo } from 'react';
import { Card, Empty, Space, Table, Tag, Typography } from 'antd';
import type { ColumnsType } from 'antd/es/table';

import { NumericCell } from '../../components/common/NumericCell';
import type { HazardClass, ToxicityClass } from '../../types/common';

interface Props {
  classes: ToxicityClass[];
}

const HAZARD_ORDER: HazardClass[] = ['HIGH', 'MEDIUM', 'LOW'];

const HAZARD_LABEL: Record<HazardClass, string> = {
  LOW: '低',
  MEDIUM: '中',
  HIGH: '高',
};

const HAZARD_COLOR: Record<HazardClass, string> = {
  LOW: 'blue',
  MEDIUM: 'gold',
  HIGH: 'red',
};

export function ToxicityExplosivityPage({ classes }: Props): JSX.Element {
  const grouped = useMemo(() => {
    const map = new Map<HazardClass, ToxicityClass[]>();
    for (const c of classes) {
      const list = map.get(c.hazard_class) ?? [];
      list.push(c);
      map.set(c.hazard_class, list);
    }
    return map;
  }, [classes]);

  return (
    <div data-testid="toxicity-explosivity-page">
      <Typography.Title level={3}>毒性爆炸分类</Typography.Title>

      <Space direction="vertical" size={16} style={{ width: '100%' }}>
        {HAZARD_ORDER.map((hc) => {
          const list = grouped.get(hc) ?? [];
          const columns: ColumnsType<ToxicityClass> = [
            {
              title: '组分',
              dataIndex: 'name',
              render: (v: string) => (
                <Space>
                  <span>{v}</span>
                  <Tag color={HAZARD_COLOR[hc]} data-testid="hazard-tag">
                    {HAZARD_LABEL[hc]}
                  </Tag>
                </Space>
              ),
            },
            {
              title: 'LD50 (mg/kg)',
              dataIndex: 'ld50_mg_kg',
              render: (v?: number) =>
                v === undefined ? <Typography.Text type="secondary">—</Typography.Text> : (
                  <NumericCell value={v} precision={1} precisionType="decimal" />
                ),
            },
            {
              title: 'PEL (ppm)',
              dataIndex: 'pel_ppm',
              render: (v?: number) =>
                v === undefined ? <Typography.Text type="secondary">—</Typography.Text> : (
                  <NumericCell value={v} precision={1} precisionType="decimal" unit="ppm" />
                ),
            },
            {
              title: '爆炸极限',
              render: (_: unknown, row: ToxicityClass) => {
                const l = row.explosive_limit_json;
                if (!l) return <Typography.Text type="secondary">—</Typography.Text>;
                return `${l.lel}–${l.uel} %`;
              },
            },
          ];

          return (
            <Card
              key={hc}
              size="small"
              data-testid="hazard-card"
              data-hazard-class={hc}
              title={
                <Space>
                  <Tag color={HAZARD_COLOR[hc]}>{HAZARD_LABEL[hc]}危险</Tag>
                  <Typography.Text type="secondary">{list.length} 项</Typography.Text>
                </Space>
              }
            >
              {list.length === 0 ? (
                <Empty description="无" />
              ) : (
                <Table<ToxicityClass>
                  rowKey="component_id"
                  columns={columns}
                  dataSource={list}
                  pagination={false}
                  size="small"
                />
              )}
            </Card>
          );
        })}
      </Space>
    </div>
  );
}

export default ToxicityExplosivityPage;