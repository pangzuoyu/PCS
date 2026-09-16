/**
 * PropertySearchPage — 组分物性查询（P45-3-3 / Task 30）。
 *
 * SPEC §7.8.1：
 * - 模糊查询：name / formula / CAS
 * - 物性卡片：MW / Tc / Pc / ω
 * - 收藏按钮 → onFavorite（V1 占位）
 *
 * Props：
 *   components: ComponentProperty[]
 *   onFavorite?: (component_id: string) => void
 */
import { useMemo, useState } from 'react';
import { Card, Empty, Input, Space, Tag, Typography } from 'antd';
import { StarOutlined } from '@ant-design/icons';

import { NumericCell } from '../../components/common/NumericCell';
import type { ComponentProperty } from '../../types/common';

interface Props {
  components: ComponentProperty[];
  onFavorite?: (component_id: string) => void;
}

export function PropertySearchPage({ components, onFavorite }: Props): JSX.Element {
  const [query, setQuery] = useState('');

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return components;
    return components.filter(
      (c) =>
        c.name.toLowerCase().includes(q) ||
        c.formula.toLowerCase().includes(q) ||
        (c.cas_number?.toLowerCase().includes(q) ?? false),
    );
  }, [components, query]);

  return (
    <div data-testid="property-search-page">
      <Typography.Title level={3}>组分物性查询</Typography.Title>

      <Input.Search
        data-testid="property-search-input"
        placeholder="按 name / formula / CAS 过滤"
        allowClear
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        style={{ maxWidth: 360, marginBottom: 16 }}
      />

      {filtered.length === 0 ? (
        <Empty description="无组分" />
      ) : (
        <div
          data-testid="property-cards"
          style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: 12 }}
        >
          {filtered.map((c) => (
            <Card
              key={c.component_id}
              size="small"
              data-testid="property-card"
              data-component-id={c.component_id}
              title={
                <Space>
                  <span style={{ fontFamily: 'var(--font-mono, monospace)' }}>{c.formula}</span>
                  <Typography.Text strong>{c.name}</Typography.Text>
                  {c.cas_number && <Tag color="default">CAS {c.cas_number}</Tag>}
                </Space>
              }
              extra={
                <StarOutlined
                  data-testid="property-favorite"
                  onClick={() => onFavorite?.(c.component_id)}
                  style={{ cursor: 'pointer' }}
                />
              }
            >
              <Space direction="vertical" size={4}>
                <Typography.Text type="secondary">MW</Typography.Text>
                <NumericCell value={c.mw} precision={3} precisionType="decimal" />
                <Typography.Text type="secondary">Tc (K)</Typography.Text>
                <NumericCell value={c.tc_k} precision={2} precisionType="decimal" unit="K" />
                <Typography.Text type="secondary">Pc (MPa)</Typography.Text>
                <NumericCell value={c.pc_mpa} precision={3} precisionType="decimal" unit="MPa" />
                <Typography.Text type="secondary">ω</Typography.Text>
                <NumericCell value={c.omega} precision={3} precisionType="decimal" />
              </Space>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}

export default PropertySearchPage;