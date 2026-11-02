/**
 * 物流详情 —— 「物性」Tab（SPEC §7.7.2 · P9B-3 · T8）。
 *
 * 数据源：`GET /streams/{id}/properties` ⇒ 4 组 JSON 物性
 * （`user_provided` / `calculated` / `effective` / `conflict_resolutions`）。
 *
 * ⚠️ 响应在契约里是**裸 dict**（无结构）⇒ 字段可能缺 ⇒ 全部**防御性**读。
 * ⚠️ 物性值本身是任意 JSON ⇒ 渲染层用「对象 ⇒ 键值表，其它 ⇒ 原样文本」。
 */
import { useEffect, useState } from 'react';
import { Alert, Card, Table, Typography } from 'antd';

import { streamApi, type StreamProperties } from '../../../api/stream';
import { describePcsError } from '../../../api/errors';

/** 物性分组（与后端返回的 4 个键同名）。 */
const GROUPS: { key: string; label: string }[] = [
  { key: 'user_provided', label: '用户提供' },
  { key: 'calculated', label: '计算值' },
  { key: 'effective', label: '生效值' },
  { key: 'conflict_resolutions', label: '冲突消解' },
];

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function renderValue(value: unknown): string {
  if (value === null || value === undefined) return '—';
  if (typeof value === 'object') return JSON.stringify(value);
  return String(value);
}

export function StreamPropertiesTab({ streamId }: { streamId: string }): JSX.Element {
  const [data, setData] = useState<StreamProperties | null>(null);
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setErrorMsg(null);
    streamApi
      .properties(streamId)
      .then((res) => {
        if (!cancelled) setData(res);
      })
      .catch((err: unknown) => {
        if (!cancelled) setErrorMsg(describePcsError(err, '加载物性失败'));
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
      <div data-testid="stream-tab-properties">
        <Alert type="error" showIcon message={errorMsg} data-testid="stream-properties-error" />
      </div>
    );
  }

  return (
    <div data-testid="stream-tab-properties">
      {GROUPS.map((group) => {
        const value = data?.[group.key];
        const entries = isRecord(value) ? Object.entries(value) : [];
        return (
          <Card
            key={group.key}
            title={group.label}
            size="small"
            style={{ marginBottom: 12 }}
            loading={loading}
          >
            {entries.length === 0 ? (
              <Typography.Text type="secondary">
                {loading ? '加载中…' : '（无数据）'}
              </Typography.Text>
            ) : (
              <Table
                size="small"
                pagination={false}
                rowKey={(row) => row.key}
                dataSource={entries.map(([key, v]) => ({ key, value: v }))}
                columns={[
                  { title: '物性', dataIndex: 'key', width: 200 },
                  { title: '值', dataIndex: 'value', render: (v: unknown) => renderValue(v) },
                ]}
              />
            )}
          </Card>
        );
      })}
    </div>
  );
}

export default StreamPropertiesTab;
