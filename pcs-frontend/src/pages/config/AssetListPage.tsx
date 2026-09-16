/**
 * AssetListPage — CONFIG 资产列表 + 详情（P45-2-3 / Task 21）。
 *
 * SPEC §7.10.1：
 * - 6 类分组的 Tabs（CATEGORY_1~6：公式 / 系数表 / 模板文件 / 标准数据库 /
 *   项目模板 / 复用设备库）
 * - 表格列：名称 / 当前版本 / 状态 / 更新人 / 更新时间 / 操作
 * - 状态：草稿/审批中/已发布/已作废（V1.1 简化 4 态）
 * - 操作：查看/编辑/审批/版本（编辑仅 DRAFT 启用 / 审批仅 IN_APPROVAL 启用）
 * - 行点击 → 详情 Drawer（含 hash + tags）
 *
 * Props（SPEC 锁定）：
 *   assets: ConfigAsset[]
 *   onEdit?: (asset) => void
 *   onApprove?: (asset) => void
 *   onVersion?: (asset) => void
 */
import { useMemo, useState } from 'react';
import {
  Button,
  Descriptions,
  Drawer,
  Empty,
  Space,
  Table,
  Tabs,
  Tag,
  Typography,
} from 'antd';
import type { ColumnsType } from 'antd/es/table';

import { HashBadge } from '../../components/common/HashBadge';
import { RevTimeline, type RevVersion } from '../../components/common/RevTimeline';
import {
  CONFIG_CATEGORY_LABEL,
  CONFIG_CATEGORY_ORDER,
  CONFIG_STATUS_LABEL,
  type ConfigAsset,
  type ConfigCategory,
} from '../../types/configAsset';
import type { RecordSignStatus } from '../../types/records';

interface Props {
  assets: ConfigAsset[];
  onEdit?: (asset: ConfigAsset) => void;
  onApprove?: (asset: ConfigAsset) => void;
  onVersion?: (asset: ConfigAsset) => void;
}

/** CONFIG 列表 4 态 → StateBadge 9 态全集映射（保留语义：草稿=未提交；已发布=已核验；已作废=已弃用）。 */
const STATUS_TO_BADGE: Record<ConfigAsset['status'], RecordSignStatus> = {
  DRAFT: 'DRAFT',
  IN_APPROVAL: 'IN_APPROVAL',
  PUBLISHED: 'CHECKED',
  OBSOLETE: 'OBSOLETE',
};

const STATUS_TAG_COLOR: Record<ConfigAsset['status'], string> = {
  DRAFT: 'default',
  IN_APPROVAL: 'blue',
  PUBLISHED: 'green',
  OBSOLETE: 'default',
};

type CategoryFilter = 'ALL' | ConfigCategory;

export function AssetListPage({ assets, onEdit, onApprove, onVersion }: Props): JSX.Element {
  const [activeCategory, setActiveCategory] = useState<CategoryFilter>('ALL');
  const [detailAsset, setDetailAsset] = useState<ConfigAsset | null>(null);
  const [revAssetId, setRevAssetId] = useState<string | null>(null);
  const [revisions, setRevisions] = useState<RevVersion[]>([]);
  const [revisionsLoading, setRevisionsLoading] = useState(false);

  const filtered = useMemo(() => {
    if (activeCategory === 'ALL') return assets;
    return assets.filter((a) => a.category === activeCategory);
  }, [assets, activeCategory]);

  const columns: ColumnsType<ConfigAsset> = [
    {
      title: '名称',
      dataIndex: 'name',
      key: 'name',
      render: (_: unknown, row: ConfigAsset) => (
        <Typography.Text data-testid="asset-name">{row.name}</Typography.Text>
      ),
    },
    {
      title: '当前版本',
      dataIndex: 'current_version',
      key: 'current_version',
      width: 100,
      render: (v: string) => (
        <Tag data-testid="asset-version" style={{ fontFamily: 'var(--font-mono, monospace)' }}>
          {v}
        </Tag>
      ),
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 100,
      render: (s: ConfigAsset['status']) => (
        <Tag color={STATUS_TAG_COLOR[s]} data-testid="asset-status" data-status={s}>
          {CONFIG_STATUS_LABEL[s]}
        </Tag>
      ),
    },
    {
      title: '更新人',
      dataIndex: 'updated_by',
      key: 'updated_by',
      width: 100,
    },
    {
      title: '更新时间',
      dataIndex: 'updated_at',
      key: 'updated_at',
      width: 160,
    },
    {
      title: '操作',
      key: 'actions',
      width: 240,
      render: (_: unknown, row: ConfigAsset) => (
        <Space>
          <Button
            type="link"
            size="small"
            data-testid="asset-action-view"
            onClick={(e) => {
              e.stopPropagation();
              setDetailAsset(row);
            }}
          >
            查看
          </Button>
          <Button
            type="link"
            size="small"
            data-testid="asset-action-edit"
            disabled={row.status !== 'DRAFT'}
            onClick={(e) => {
              e.stopPropagation();
              onEdit?.(row);
            }}
          >
            编辑
          </Button>
          <Button
            type="link"
            size="small"
            data-testid="asset-action-approve"
            disabled={row.status !== 'IN_APPROVAL'}
            onClick={(e) => {
              e.stopPropagation();
              onApprove?.(row);
            }}
          >
            审批
          </Button>
          <Button
            type="link"
            size="small"
            data-testid="asset-action-version"
            onClick={(e) => {
              e.stopPropagation();
              onVersion?.(row);
              // 拉取 RevTimeline 数据
              setRevAssetId(row.asset_id);
              setRevisionsLoading(true);
              void fetch(`/api/v1/config/assets/${row.asset_id}/revisions`, {
                headers: { Authorization: 'Bearer mock-jwt-token' },
              })
                .then((r) => (r.ok ? r.json() : []))
                .then((j: RevVersion[]) => setRevisions(j))
                .catch(() => {/* network unavailable (jsdom / offline) */})
                .finally(() => setRevisionsLoading(false));
            }}
          >
            版本
          </Button>
        </Space>
      ),
    },
  ];

  const tabItems = [
    {
      key: 'ALL',
      label: '全部',
    },
    ...CONFIG_CATEGORY_ORDER.map((c) => ({
      key: c,
      label: CONFIG_CATEGORY_LABEL[c],
    })),
  ];

  return (
    <div data-testid="config-asset-page">
      <Typography.Title level={3} data-testid="config-asset-title">
        CONFIG 资产
      </Typography.Title>

      <Tabs
        data-testid="config-asset-tabs"
        activeKey={activeCategory}
        onChange={(k) => setActiveCategory(k as CategoryFilter)}
        items={tabItems}
      />

      {filtered.length === 0 ? (
        <Empty description="无资产" data-testid="asset-empty" />
      ) : (
        <Table<ConfigAsset>
          rowKey="asset_id"
          columns={columns}
          dataSource={filtered}
          pagination={false}
          onRow={(record) => ({
            'data-testid': 'asset-row',
            'data-asset-id': record.asset_id,
            'data-category': record.category,
            'data-status': record.status,
            onClick: () => setDetailAsset(record),
          })}
        />
      )}

      <Drawer
        title={detailAsset ? `资产详情：${detailAsset.name}` : '资产详情'}
        placement="right"
        width={520}
        open={!!detailAsset}
        onClose={() => setDetailAsset(null)}
      >
        <Button
          data-testid="asset-detail-open-rev"
          onClick={() => detailAsset && setRevAssetId(detailAsset.asset_id)}
          style={{ marginBottom: 16 }}
        >
          查看版本历史
        </Button>
        {detailAsset && (
          <Descriptions column={1} bordered size="small" data-testid="asset-detail">
            <Descriptions.Item label="名称">{detailAsset.name}</Descriptions.Item>
            <Descriptions.Item label="类别">
              <Tag>{CONFIG_CATEGORY_LABEL[detailAsset.category]}</Tag>
              <Typography.Text type="secondary" style={{ marginLeft: 8 }}>
                {detailAsset.category}
              </Typography.Text>
            </Descriptions.Item>
            <Descriptions.Item label="当前版本">{detailAsset.current_version}</Descriptions.Item>
            <Descriptions.Item label="状态">
              <Tag color={STATUS_TAG_COLOR[detailAsset.status]}>
                {CONFIG_STATUS_LABEL[detailAsset.status]}
              </Tag>
            </Descriptions.Item>
            <Descriptions.Item label="更新人">{detailAsset.updated_by}</Descriptions.Item>
            <Descriptions.Item label="更新时间">{detailAsset.updated_at}</Descriptions.Item>
            {detailAsset.hash && (
              <Descriptions.Item label="哈希">
                <HashBadge hash={detailAsset.hash} />
              </Descriptions.Item>
            )}
            {detailAsset.tags && detailAsset.tags.length > 0 && (
              <Descriptions.Item label="标签">
                <Space>
                  {detailAsset.tags.map((t) => (
                    <Tag key={t} data-testid="asset-detail-tag">
                      {t}
                    </Tag>
                  ))}
                </Space>
              </Descriptions.Item>
            )}
            {detailAsset.description && (
              <Descriptions.Item label="描述">{detailAsset.description}</Descriptions.Item>
            )}
          </Descriptions>
        )}
      </Drawer>

      {/* 版本历史 RevTimeline（P2 8 组件实例化）*/}
      <Drawer
        title="版本历史"
        placement="right"
        width={520}
        open={!!revAssetId}
        onClose={() => setRevAssetId(null)}
        data-testid="asset-rev-drawer"
      >
        {revisionsLoading ? (
          <Typography.Text type="secondary">加载中…</Typography.Text>
        ) : revisions.length === 0 ? (
          <Empty description="无版本记录" />
        ) : (
          <RevTimeline versions={revisions} />
        )}
      </Drawer>
    </div>
  );
}

export default AssetListPage;

// Re-export STATUS_TO_BADGE 仅供其他 CONFIG 页面复用（P45-2-4~8）
export { STATUS_TO_BADGE };