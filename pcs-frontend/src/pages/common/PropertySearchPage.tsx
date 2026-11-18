/**
 * PropertySearchPage — 组分物性查询（P45-3-3 / Task 30 · **P10-C · T1 改：查询驱动**）。
 *
 * SPEC §7.8.1：
 * - 模糊查询：name / formula / CAS
 * - 物性卡片：MW / Tc / Pc / ω
 * - 收藏按钮 → onFavorite（V1 占位）
 *
 * ## ⚠️ **P10-C · T1（TODO-160）**：本页改成「**填条件才查**」
 *
 * 此前首屏就发 `GET /api/v1/common/materials/search`（**无参数**）⇒ ⇒ 后端 **422**
 * （契约里 `keyword` 必填 · `min_length=1`）⇒ ⇒ 页面首屏是错误态。
 *
 * ⇒ ⇒ 现在：**输入关键字才发请求**（300ms 防抖）⇒ 首屏**零请求**。
 *
 * ## ⚠️ 数据来源从「父组件注入」改成「本页自取」
 *
 * 关键字是**页面自己的输入** ⇒ 参数只能由本页决定 ⇒ ⇒ 请求必须由本页发起
 * （父组件拿不到关键字）⇒ ⇒ 这是本页改成自取的原因，**不是**为了「统一风格」。
 *
 * ## ⚠️ 后端**最多命中 1 条**
 *
 * `CommonService.search_material` 走 `chemicals.search_chemical` ⇒ 单命中
 * ⇒ ⇒ 真实后端下卡片网格**只有一张**（mock 通道给的是整表 ⇒ 那条漂移归 TODO-167）。
 * ⇒ 卡片网格保留（契约没规定张数），但别把「网格」当成「列表」来承诺。
 */
import { useEffect, useState } from 'react';
import { Alert, Card, Empty, Input, Space, Spin, Tag, Typography } from 'antd';
import { StarOutlined } from '@ant-design/icons';

import { NumericCell } from '../../components/common/NumericCell';
import { commonQueryApi } from '../../api/common';
import { errorText } from '../../api/errors';
import type { ComponentProperty } from '../../types/common';

/** 输入停止多久才发请求（ms）—— 避免每敲一个字母打一次后端。 */
const QUERY_DEBOUNCE_MS = 300;

interface Props {
  onFavorite?: (cas: string) => void;
}

export function PropertySearchPage({ onFavorite }: Props): JSX.Element {
  const [keyword, setKeyword] = useState('');
  const [components, setComponents] = useState<ComponentProperty[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  /** 是否**已经查过一次**（区分「没查过」与「查了但没命中」）。 */
  const [queried, setQueried] = useState(false);

  useEffect(() => {
    const kw = keyword.trim();
    if (!kw) {
      // ⚠️ **首屏走这条分支** ⇒ 零请求 ⇒ 没有 422。
      setComponents([]);
      setError(null);
      setQueried(false);
      setLoading(false);
      return;
    }
    let cancelled = false;
    setLoading(true);
    const timer = setTimeout(() => {
      commonQueryApi
        .searchMaterials(kw)
        .then((rows) => {
          if (cancelled) return;
          setComponents(rows);
          setError(null);
          setQueried(true);
          setLoading(false);
        })
        .catch((err: unknown) => {
          if (cancelled) return;
          setComponents([]);
          setError(errorText(err, '物性查询失败'));
          setQueried(true);
          setLoading(false);
        });
    }, QUERY_DEBOUNCE_MS);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [keyword]);

  return (
    <div data-testid="property-search-page">
      <Typography.Title level={3}>组分物性查询</Typography.Title>

      <Input.Search
        data-testid="property-search-input"
        placeholder="按 name / formula / CAS 查询"
        allowClear
        value={keyword}
        onChange={(e) => setKeyword(e.target.value)}
        style={{ maxWidth: 360, marginBottom: 16 }}
      />

      {error ? (
        <Alert
          type="error"
          showIcon
          message={error}
          data-testid="property-search-error"
          style={{ marginBottom: 16 }}
        />
      ) : null}

      {loading ? (
        <Spin data-testid="property-search-loading" />
      ) : components.length === 0 ? (
        <Empty
          description={queried ? '无匹配组分' : '输入关键字后查询（name / formula / CAS）'}
          data-testid="property-search-empty"
        />
      ) : (
        <div
          data-testid="property-cards"
          style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: 12 }}
        >
          {components.map((c) => (
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
