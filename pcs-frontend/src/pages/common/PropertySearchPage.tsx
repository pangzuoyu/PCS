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
 *   onFavorite?: (cas: string) => void
 */
import { useMemo, useState } from 'react';
import { Card, Empty, Input, Space, Tag, Typography } from 'antd';
import { StarOutlined } from '@ant-design/icons';

import { NumericCell } from '../../components/common/NumericCell';
import type { ComponentProperty } from '../../types/common';

interface Props {
  components: ComponentProperty[];
  onFavorite?: (cas: string) => void;
}

export function PropertySearchPage({ components, onFavorite }: Props): JSX.Element {
  const [query, setQuery] = useState('');

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return components;
    return components.filter(
      (c) =>
        c.name.toLowerCase().includes(q) ||
        (c.formula ?? '').toLowerCase().includes(q) ||
        (c.cas.toLowerCase().includes(q)),
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
              key={c.cas}
              size="small"
              data-testid="property-card"
              data-component-id={c.cas}
              title={
                <Space>
                  <span style={{ fontFamily: 'var(--font-mono, monospace)' }}>{c.formula}</span>
                  <Typography.Text strong>{c.name}</Typography.Text>
                  <Tag color="default">CAS {c.cas}</Tag>
                </Space>
              }
              extra={
                <StarOutlined
                  data-testid="property-favorite"
                  onClick={() => onFavorite?.(c.cas)}
                  style={{ cursor: 'pointer' }}
                />
              }
            >
              <Space direction="vertical" size={4}>
                <Typography.Text type="secondary">MW</Typography.Text>
                <NumericCell value={c.mw ?? 0} precision={3} precisionType="decimal" />
                {/* ⚠️ Tc / Pc / ω 已砍（2026-10-19，用户裁决）。
                 *
                 * `GET /common/materials/search` 的契约 `MaterialSearchResult`
                 * 只有 5 个字段（cas / name / formula / mw / source）——
                 * 临界参数属于**另一个 schema** `MaterialDetail`。
                 * 此前页面读 `tc_k`/`pc_mpa`/`omega`，真后端下**永远 undefined**。
                 *
                 * 不改成「每行发一次 GET /materials/{cas}」：那是 N+1，
                 * 且滚动列表时 20 个请求同时发出。砍列，用户点进详情看。
                 * 若产品坚持列表里看，正确做法是**扩 `MaterialSearchResult`**
                 * （后端加 3 个字段），不是前端发 N 个请求。 */}
              </Space>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}

export default PropertySearchPage;