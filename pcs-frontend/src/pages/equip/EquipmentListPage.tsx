/**
 * EquipmentListPage — 设备台账（SPEC §7.13 · **P10-C · T3 新建**）。
 *
 * ## 为什么此前**没有**这一页
 *
 * 后端有 `GET /api/v1/equipment-list`（`app/api/v1/equip_list.py`）· 种子也造了
 * 设备（`132-P-101A/B`）⇒ ⇒ 但前端**没有任何组件消费它**
 * ⇒ ⇒ 「设备一览」页（`/config/asset-list`）列的是 **`ConfigAsset`（配置资产**
 * —— 公式 / 模板 / 系数表）⇒ ⇒ **不是**设备台账
 * ⇒ ⇒ 两条「设备」概念在 UI 上**只有一条可见** ⇒ ⇒ TODO-157。
 *
 * ⇒ ⇒ 现在：补这一页 ⇒ ⇒ 「设备台账」这条线前端**有入口**了。
 *
 * ## 列清单（**以契约为准**）
 *
 * 契约 `EquipListResponse` 有 18 个字段 ⇒ ⇒ 本页列的是其中**有值的那几个**
 * ⇒ ⇒ ⚠️ SPEC §7.13 的列表里还有「**包号**」「**单元**」「**计算状态**」
 * 三列 ⇒ ⇒ 契约里**没有**这三个字段 ⇒ ⇒ **不编**（编出来 = 幽灵列）
 * ⇒ ⇒ **登记 SPEC 修订**（见本批的 NOTE）。
 */
import { useEffect, useMemo, useState } from 'react';
import { Alert, Empty, Input, Select, Space, Spin, Table, Tag, Typography } from 'antd';

import { StateBadge } from '../../components/common/StateBadge';
import { equipListApi } from '../../api/equipList';
import type { EquipListItem } from '../../api/equipList';
import { errorText } from '../../api/errors';
import { useProjectScope } from '../../hooks/useProjectScope';
import type { RecordSignStatus } from '../../types/records';
import type { StrictColumns } from '../../types/strictColumns';

/** 后端支持的**来源**词表（SPEC §7.13：PUMP/VESSEL/HEAT/PSV/CV/MANUAL）。 */
const SOURCE_OPTIONS = [
  { value: '', label: '全部来源' },
  { value: 'PUMP', label: 'PUMP' },
  { value: 'VESSEL', label: 'VESSEL' },
  { value: 'HEAT', label: 'HEAT' },
  { value: 'PSV', label: 'PSV' },
  { value: 'CV', label: 'CV' },
  { value: 'MANUAL', label: 'MANUAL' },
];

/** 设备状态词表（契约里 `equipment_status` 是 1~2 位短码）。 */
const STATUS_OPTIONS = [
  { value: '', label: '全部状态' },
  { value: 'A', label: 'A' },
  { value: 'B', label: 'B' },
  { value: 'C', label: 'C' },
  { value: 'D', label: 'D' },
];

interface Props {
  /** 行点击回调（设备详情还没做 ⇒ 先把行标识带出去）。 */
  onSelect?: (row: EquipListItem) => void;
}

export function EquipmentListPage({ onSelect }: Props = {}): JSX.Element {
  const { projectId, error: scopeError, loading: scopeLoading } = useProjectScope();
  const [typeFilter, setTypeFilter] = useState('');
  const [source, setSource] = useState('');
  const [status, setStatus] = useState('');
  const [rows, setRows] = useState<EquipListItem[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!projectId) return;
    let cancelled = false;
    setLoading(true);
    equipListApi
      .list({ project_id: projectId, source_module: source || undefined, equipment_status: status || undefined, limit: 200 })
      .then((res) => {
        if (cancelled) return;
        setRows(res.items ?? []);
        setTotal(res.total ?? 0);
        setError(null);
        setLoading(false);
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        setRows([]);
        setError(errorText(err, '设备台账加载失败'));
        setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [projectId, source, status]);

  // ⚠️ **类型过滤是前端的** —— 后端 `GET /equipment-list` **没有** type_code 过滤
  // ⇒ ⇒ 不编一个后端不支持的参数 ⇒ ⇒ 客户端过滤（并在 UI 上标出来）。
  const filtered = useMemo(() => {
    const kw = typeFilter.trim().toLowerCase();
    if (!kw) return rows;
    return rows.filter(
      (r) =>
        (r.type_code ?? '').toLowerCase().includes(kw) ||
        (r.equipment_name ?? '').toLowerCase().includes(kw) ||
        (r.tag_number ?? '').toLowerCase().includes(kw),
    );
  }, [rows, typeFilter]);

  const columns: StrictColumns<EquipListItem> = [
    {
      title: '位号',
      dataIndex: 'tag_number',
      width: 140,
      render: (v: string | null | undefined) =>
        v ? (
          <span style={{ fontFamily: 'var(--font-mono, monospace)' }}>{v}</span>
        ) : (
          <Typography.Text type="secondary">—</Typography.Text>
        ),
    },
    { title: '类型', dataIndex: 'type_code', width: 100 },
    { title: '名称', dataIndex: 'equipment_name', width: 180 },
    {
      title: '描述',
      dataIndex: 'equipment_description',
      width: 200,
      render: (v: string | null | undefined) =>
        v ?? <Typography.Text type="secondary">—</Typography.Text>,
    },
    {
      title: '厂家',
      dataIndex: 'vendor',
      width: 140,
      render: (v: string | null | undefined) =>
        v ?? <Typography.Text type="secondary">—</Typography.Text>,
    },
    {
      title: '型号',
      dataIndex: 'vendor_model',
      width: 140,
      render: (v: string | null | undefined) =>
        v ?? <Typography.Text type="secondary">—</Typography.Text>,
    },
    {
      title: '来源',
      dataIndex: 'source_module',
      width: 100,
      render: (v: string | null | undefined) =>
        v ? <Tag color="blue">{v}</Tag> : <Typography.Text type="secondary">—</Typography.Text>,
    },
    {
      title: '采购状态',
      dataIndex: 'procurement_status',
      width: 110,
      render: (v: string | null | undefined) =>
        v ?? <Typography.Text type="secondary">—</Typography.Text>,
    },
    {
      title: '安装位置',
      dataIndex: 'installation_location',
      width: 140,
      render: (v: string | null | undefined) =>
        v ?? <Typography.Text type="secondary">—</Typography.Text>,
    },
    {
      title: '设备状态',
      dataIndex: 'equipment_status',
      width: 100,
      render: (v: string) => <Tag color="default">{v}</Tag>,
    },
    {
      title: '签署状态',
      dataIndex: 'sign_status',
      width: 110,
      // ⚠️ 契约里 `sign_status` 是 `string` ⇒ 需要收窄到 9 态词表
      //    （`RecordSignStatus`）⇒ ⇒ 用**词表类型**而不是随便 3 个字面量。
      render: (s: string) => (
        <StateBadge status={s as RecordSignStatus} module="CONFIG" />
      ),
    },
  ];

  if (scopeError) {
    return (
      <Alert
        type="warning"
        showIcon
        message="没有可用的项目作用域"
        description={scopeError}
        data-testid="equipment-list-scope-error"
      />
    );
  }

  // ⚠️ **作用域还在解析** ⇒ ⇒ 显示加载态（不是「无设备」）⇒ ⇒ 否则用户会
  // 以为「这个项目一台设备都没有」。
  if (scopeLoading) {
    return <Spin data-testid="equipment-list-scope-loading" />;
  }

  return (
    <div data-testid="equipment-list-page">
      <Typography.Title level={3} style={{ marginTop: 0 }}>设备台账</Typography.Title>

      <Space style={{ marginBottom: 16 }} wrap>
        <Input.Search
          data-testid="equipment-filter-type"
          placeholder="按类型 / 名称 / 位号过滤（前端过滤）"
          allowClear
          value={typeFilter}
          onChange={(e) => setTypeFilter(e.target.value)}
          style={{ width: 280 }}
        />
        <Select
          data-testid="equipment-filter-source"
          options={SOURCE_OPTIONS}
          value={source}
          onChange={(v) => setSource(v)}
          style={{ width: 150 }}
        />
        <Select
          data-testid="equipment-filter-status"
          options={STATUS_OPTIONS}
          value={status}
          onChange={(v) => setStatus(v)}
          style={{ width: 140 }}
        />
        <Tag color="blue" data-testid="equipment-count">
          {filtered.length} / {total}
        </Tag>
      </Space>

      {error ? (
        <Alert
          type="error"
          showIcon
          message={error}
          data-testid="equipment-list-error"
          style={{ marginBottom: 16 }}
        />
      ) : null}

      {loading ? (
        <Spin data-testid="equipment-list-loading" />
      ) : filtered.length === 0 ? (
        <Empty description="无设备" data-testid="equipment-list-empty" />
      ) : (
        <Table<EquipListItem>
          rowKey="equipment_id"
          columns={columns}
          dataSource={filtered}
          pagination={false}
          size="small"
          scroll={{ x: 'max-content' }}
          onRow={(record) => ({
            'data-testid': 'equipment-row',
            'data-tag-number': record.tag_number ?? '',
            onClick: () => onSelect?.(record),
          })}
        />
      )}
    </div>
  );
}

export default EquipmentListPage;
