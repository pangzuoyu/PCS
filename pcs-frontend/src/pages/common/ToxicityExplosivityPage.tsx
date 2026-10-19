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

import type { ToxicityClass, ToxicityClassLevel } from '../../types/common';
import type { StrictColumns } from '../../types/strictColumns';

interface Props {
  classes: ToxicityClass[];
}

// ⚠️ 词表改成后端 `_SAFETY_DATA[...]["tox"]` 的真实取值 —— 旧的前端
// `HazardClass` 只有 LOW/MEDIUM/HIGH，而后端还有 `NONE`（水、CO2 等）。
// 后端返回 `NONE` 时旧映射是 undefined ⇒ 分组标签与颜色都是空的。
const TOX_ORDER: ToxicityClassLevel[] = ['HIGH', 'MEDIUM', 'LOW', 'NONE'];

const TOX_LABEL: Record<ToxicityClassLevel, string> = {
  NONE: '无毒',
  LOW: '低毒',
  MEDIUM: '中等毒',
  HIGH: '高毒',
};

const TOX_COLOR: Record<ToxicityClassLevel, string> = {
  NONE: 'default',
  LOW: 'blue',
  MEDIUM: 'gold',
  HIGH: 'red',
};

export function ToxicityExplosivityPage({ classes }: Props): JSX.Element {
  const grouped = useMemo(() => {
    const map = new Map<ToxicityClassLevel, ToxicityClass[]>();
    for (const c of classes) {
      const list = map.get(c.toxicity_class as ToxicityClassLevel) ?? [];
      list.push(c);
      map.set(c.toxicity_class as ToxicityClassLevel, list);
    }
    return map;
  }, [classes]);

  return (
    <div data-testid="toxicity-explosivity-page">
      <Typography.Title level={3}>毒性爆炸分类</Typography.Title>

      <Space direction="vertical" size={16} style={{ width: '100%' }}>
        {TOX_ORDER.map((hc) => {
          const list = grouped.get(hc) ?? [];
          // ⚠️ 空的档不渲染。此前 `TOX_ORDER`（旧 `HAZARD_ORDER`）恰好每档
          // 都有数据，所以看不出来；加了后端真实词表里的 `NONE` 之后，
          // 没有 LOW 数据就会渲染出一张**空的「低毒」卡片**。
          if (list.length === 0) return null;
          const columns: StrictColumns<ToxicityClass> = [
            {
              title: '组分',
              dataIndex: 'name',
              render: (v: string) => (
                <Space>
                  <span>{v}</span>
                  <Tag color={TOX_COLOR[hc]} data-testid="toxicity-tag">
                    {TOX_LABEL[hc]}
                  </Tag>
                </Space>
              ),
            },

            {
              // 契约把爆炸极限拍平成 lel_vol_pct / uel_vol_pct 两个标量
              // （手写侧的 `explosive_limit_json: {lel, uel}` 契约里没有）。
              title: '爆炸极限 (%vol)',
              render: (_: unknown, row: ToxicityClass) => (
                row.lel_vol_pct === null || row.lel_vol_pct === undefined
                  ? <Typography.Text type="secondary">—</Typography.Text>
                  : `${row.lel_vol_pct}–${row.uel_vol_pct ?? '?'}`
              ),
            },
          ];

          return (
            <Card
              key={hc}
              size="small"
              data-testid="toxicity-card"
              data-toxicity-class={hc}
              title={
                <Space>
                  <Tag color={TOX_COLOR[hc]}>{TOX_LABEL[hc]}危险</Tag>
                  <Typography.Text type="secondary">{list.length} 项</Typography.Text>
                </Space>
              }
            >
              {list.length === 0 ? (
                <Empty description="无" />
              ) : (
                <Table<ToxicityClass>
                  rowKey="cas"
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