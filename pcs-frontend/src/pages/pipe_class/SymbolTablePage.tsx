/**
 * SymbolTablePage — PIPE_CLASS 符号表（P45-3-2 / Task 29）。
 *
 * SPEC §7.9.3：
 * - 按 category（fluid / service / phase / toxicity）分组
 * - 每组：symbol ↔ meaning
 * - 操作：添加 / 编辑 / 删除
 *
 * Props：
 *   mappings: SymbolMapping[]
 *   onAdd?: (m: Omit<SymbolMapping, 'symbol' | 'meaning'>) => void
 *   onDelete?: (symbol: string) => void
 *
 * V1 极简版：删除通过回调；添加由父组件管理；本组件只渲染分组表格 + 删除入口。
 */
import { useMemo } from 'react';
import { Button, Collapse, Empty, Space, Table, Tag, Typography } from 'antd';
import { DeleteOutlined } from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';

import type { SymbolMapping, SymbolCategory } from '../../types/pipeClass';

interface Props {
  mappings: SymbolMapping[];
  onDelete?: (symbol: string) => void;
}

const CATEGORY_LABEL: Record<SymbolCategory, string> = {
  fluid: '介质',
  service: '服务',
  phase: '相态',
  toxicity: '毒性',
};

const CATEGORY_COLOR: Record<SymbolCategory, string> = {
  fluid: 'blue',
  service: 'green',
  phase: 'orange',
  toxicity: 'red',
};

export function SymbolTablePage({ mappings, onDelete }: Props): JSX.Element {
  const grouped = useMemo(() => {
    const map = new Map<SymbolCategory, SymbolMapping[]>();
    for (const m of mappings) {
      const list = map.get(m.category) ?? [];
      list.push(m);
      map.set(m.category, list);
    }
    return map;
  }, [mappings]);

  const items = (Object.keys(CATEGORY_LABEL) as SymbolCategory[]).map((cat) => {
    const list = grouped.get(cat) ?? [];
    const columns: ColumnsType<SymbolMapping> = [
      {
        title: '符号',
        dataIndex: 'symbol',
        width: 120,
        render: (v: string) => (
          <span style={{ fontFamily: 'var(--font-mono, monospace)' }}>{v}</span>
        ),
      },
      { title: '含义', dataIndex: 'meaning' },
      {
        title: '操作',
        width: 100,
        render: (_: unknown, row: SymbolMapping) => (
          <Button
            size="small"
            danger
            icon={<DeleteOutlined />}
            data-testid="symbol-delete"
            data-symbol={row.symbol}
            onClick={() => onDelete?.(row.symbol)}
          />
        ),
      },
    ];

    return {
      key: cat,
      label: (
        <Space>
          <Tag color={CATEGORY_COLOR[cat]}>{CATEGORY_LABEL[cat]}</Tag>
          <Typography.Text type="secondary">{list.length} 项</Typography.Text>
        </Space>
      ),
      children:
        list.length === 0 ? (
          <Empty description="无映射" data-testid="symbol-empty" />
        ) : (
          <Table<SymbolMapping>
            rowKey="symbol"
            columns={columns}
            dataSource={list}
            pagination={false}
            size="small"
            onRow={(record) =>
              ({
                'data-testid': 'symbol-row',
                'data-symbol': record.symbol,
              }) as React.HTMLAttributes<HTMLElement>
            }
          />
        ),
    };
  });

  return (
    <div data-testid="symbol-table-page">
      <Typography.Title level={3}>管路符号表</Typography.Title>
      <Collapse
        data-testid="symbol-table-collapse"
        defaultActiveKey={['fluid', 'service']}
        items={items}
      />
    </div>
  );
}

export default SymbolTablePage;