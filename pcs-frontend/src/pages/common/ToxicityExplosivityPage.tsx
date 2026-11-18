/**
 * ToxicityExplosivityPage — 毒性爆炸（P45-3-3 / Task 30 · **P10-C · T1 改：查询驱动**）。
 *
 * SPEC §7.8.3：
 * - 按 hazard_class（LOW / MEDIUM / HIGH）分组
 * - 每组：组分 + LD50 + PEL + 爆炸极限 LEL/UEL
 * - HIGH 红警 + MEDIUM 黄警 + LOW 蓝标
 *
 * ## ⚠️ **P10-C · T1（TODO-160）**：本页改成「**填 CAS 才查**」
 *
 * 契约里 `GET /common/safety` 的必填参数是 **`cas`** ⇒ ⇒ 此前首屏发**空查询**
 * ⇒ 后端 **422** ⇒ 首屏是错误态。
 * ⇒ ⇒ 现在：**输入 CAS 才发请求** ⇒ 首屏**零请求**。
 *
 * ## ⚠️ 后端返回的是**单条介质**，不是全部介质
 *
 * `CommonService.safety_data` 查的是内置字典 `_SAFETY_DATA`（~15 种介质）
 * ⇒ **一次只返回一条** ⇒ ⇒ 分组卡片最多 1 张、里面 1 行。
 * ⇒ ⇒ 「按 hazard_class 分组」的形状保留（契约没规定条数），
 * 但**别把它当成「全部介质的总览」**。
 *
 * ⚠️ **SPEC §7.8.3 的语义变了**：原来是「列出全部组分并按毒性分组」，
 * 现在是「查一种介质的毒性」⇒ ⇒ **登记 SPEC 修订**（见本批说明）。
 */
import { useEffect, useMemo, useState } from 'react';
import { Alert, Card, Empty, Input, Space, Spin, Table, Tag, Typography } from 'antd';

import { commonQueryApi } from '../../api/common';
import { errorText } from '../../api/errors';
import type { ToxicityClass, ToxicityClassLevel } from '../../types/common';
import type { StrictColumns } from '../../types/strictColumns';

/** 输入停止多久才发请求（ms）。 */
const QUERY_DEBOUNCE_MS = 300;

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

export function ToxicityExplosivityPage(): JSX.Element {
  const [cas, setCas] = useState('');
  const [classes, setClasses] = useState<ToxicityClass[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [queried, setQueried] = useState(false);

  useEffect(() => {
    const key = cas.trim();
    if (!key) {
      // ⚠️ **首屏走这条分支** ⇒ 零请求 ⇒ 没有 422。
      setClasses([]);
      setError(null);
      setQueried(false);
      setLoading(false);
      return;
    }
    let cancelled = false;
    setLoading(true);
    const timer = setTimeout(() => {
      commonQueryApi
        .safety(key)
        .then((row) => {
          if (cancelled) return;
          // ⚠️ 后端返回**单个对象** ⇒ 包成 1 行喂给分组卡片。
          setClasses([row]);
          setError(null);
          setQueried(true);
          setLoading(false);
        })
        .catch((err: unknown) => {
          if (cancelled) return;
          setClasses([]);
          setError(errorText(err, '介质安全查询失败'));
          setQueried(true);
          setLoading(false);
        });
    }, QUERY_DEBOUNCE_MS);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [cas]);

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

      <Input
        data-testid="toxicity-cas-input"
        placeholder="按 CAS 查询（如 74-82-8）"
        allowClear
        value={cas}
        onChange={(e) => setCas(e.target.value)}
        style={{ width: 280, marginBottom: 16 }}
      />

      {error ? (
        <Alert
          type="error"
          showIcon
          message={error}
          data-testid="toxicity-error"
          style={{ marginBottom: 16 }}
        />
      ) : null}

      <Space direction="vertical" size={16} style={{ width: '100%' }}>
        {loading ? (
          <Spin data-testid="toxicity-loading" />
        ) : classes.length === 0 ? (
          <Empty
            description={queried ? '无记录' : '输入 CAS 后查询'}
            data-testid="toxicity-empty"
          />
        ) : (
          TOX_ORDER.map((hc) => {
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
                render: (_: unknown, row: ToxicityClass) =>
                  row.lel_vol_pct === null || row.lel_vol_pct === undefined
                    ? <Typography.Text type="secondary">—</Typography.Text>
                    : `${row.lel_vol_pct}–${row.uel_vol_pct ?? '?'}`
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
          })
        )}
      </Space>
    </div>
  );
}

export default ToxicityExplosivityPage;
