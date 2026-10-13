/**
 * ReportDefinitionListPage — REPORT_BUILDER 定义管理列表（b12）。
 *
 * 列表列：名称 / 版本 / 状态 / 创建人 / 共享范围（+ 分类、更新时间）。
 *
 * ## 可见性是后端说了算，页面不自己判断
 *
 * DRAFT **仅创建人可见**（SPEC §3.2.2(6)），OBSOLETE 默认不列出。
 * 两条都由后端 `visible_clause()` 统一处理 —— 前端若自己按状态过滤一遍，
 * 就等于把同一条规则写了两份，而两份会漂移（后端加了新状态，页面不知道）。
 * 所以本页**只渲染后端返回的 items**，不做任何本地过滤。
 *
 * 唯一的本地控件是「状态筛选」，它作为查询参数发给后端，不在本地裁剪。
 */
import { useCallback, useEffect, useMemo, useState } from 'react';
import type { JSX } from 'react';
import {
  Alert,
  Button,
  Input,
  Select,
  Space,
  Spin,
  Table,
  Tag,
  Tooltip,
  Typography,
} from 'antd';
import { PlusOutlined, ReloadOutlined } from '@ant-design/icons';
import { Link, useNavigate } from 'react-router-dom';

import { PageHeader } from '../../components/common/PageHeader';
import { errorMessage, reportBuilderApi } from '../../api/reportBuilder';
import type { ReportDefinitionOut } from '../../api/reportBuilder';

/** 定义状态 3 态（不是计划里写的 5 态）。
 *
 * 依据：`definition_service` 的裁决 —— 改已发布的定义自动回到 DRAFT
 * （否则审批会被绕过），所以没有「编辑中」这一态。
 */
const STATUS_LABEL: Record<string, string> = {
  DRAFT: '草稿',
  PUBLISHED: '已发布',
  OBSOLETE: '已作废',
};

const STATUS_COLOR: Record<string, string> = {
  DRAFT: 'default',
  PUBLISHED: 'green',
  OBSOLETE: 'red',
};

const SHARED_LABEL: Record<string, string> = {
  ALL_USERS: '全员可见',
  CREATOR_ONLY: '仅创建人',
};

export function ReportDefinitionListPage(): JSX.Element {
  const navigate = useNavigate();
  const [rows, setRows] = useState<ReportDefinitionOut[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<string | undefined>();
  const [keyword, setKeyword] = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await reportBuilderApi.list(
        statusFilter ? { status: statusFilter } : undefined);
      setRows(data.items);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setLoading(false);
    }
  }, [statusFilter]);

  useEffect(() => { void load(); }, [load]);

  /** 关键字是**纯前端**过滤。
   *
   * ⚠️ 它只筛「已经在后端可见集合里」的行 —— 可见性仍由后端说了算。
   * 把它误当成安全过滤（以为搜索能替后端藏东西）是这类页面最常见的误解。
   */
  const visible = useMemo(() => {
    const kw = keyword.trim().toLowerCase();
    if (!kw) return rows;
    return rows.filter((r) =>
      r.name.toLowerCase().includes(kw)
      || (r.category ?? '').toLowerCase().includes(kw));
  }, [rows, keyword]);

  const columns = useMemo(() => [
    {
      title: '名称',
      dataIndex: 'name',
      key: 'name',
      render: (name: string, row: ReportDefinitionOut) => (
        <Link to={`/report/definitions/${row.def_id}`}>{name}</Link>
      ),
    },
    { title: '分类', dataIndex: 'category', key: 'category', width: 110 },
    {
      title: '版本',
      dataIndex: 'version',
      key: 'version',
      width: 90,
      // ⚠️ 版本号是**内容寻址**的一环（report_files 冻结它保证可复现），
      // 所以它必须显眼：用户改完定义要能一眼看出「版本变了」。
      render: (v: string) => <Typography.Text code>{v}</Typography.Text>,
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 100,
      render: (s: string) => (
        <Tag color={STATUS_COLOR[s]}>{STATUS_LABEL[s] ?? s}</Tag>
      ),
    },
    { title: '创建人', dataIndex: 'created_by', key: 'created_by', width: 130,
      render: (v: string | null) => v ?? '—' },
    {
      title: '共享范围',
      dataIndex: 'shared_with',
      key: 'shared_with',
      width: 110,
      render: (v: string) => SHARED_LABEL[v] ?? v,
    },
    {
      title: '',
      key: 'actions',
      width: 180,
      render: (_: unknown, row: ReportDefinitionOut) => (
        <Space size="small">
          <Button size="small"
            onClick={() => navigate(`/report/definitions/${row.def_id}`)}>
            编辑
          </Button>
          {/* 只有 PUBLISHED 可执行 —— 与后端 409 判定一致。
              按钮置灰而不是报错，是让用户在点之前就知道。 */}
          <Tooltip title={row.status === 'PUBLISHED'
            ? undefined : '只有已发布的定义可执行'}>
            <Button size="small" type="primary" disabled={row.status !== 'PUBLISHED'}
              onClick={() => navigate(`/report/execute/${row.def_id}`)}>
              执行
            </Button>
          </Tooltip>
        </Space>
      ),
    },
  ], [navigate]);

  return (
    <div className="page">
    <PageHeader
      title="报表定义"
      actions={
        <Space>
          <Button icon={<ReloadOutlined />} onClick={() => void load()}>
            刷新
          </Button>
          <Button type="primary" icon={<PlusOutlined />}
            onClick={() => navigate('/report/definitions/new')}>
            新建定义
          </Button>
        </Space>
      }
    />
      <Space style={{ marginBottom: 16 }} wrap>
        <Input.Search placeholder="按名称 / 分类筛选（仅筛后端已可见的行）"
          allowClear onChange={(e) => setKeyword(e.target.value)}
          style={{ width: 320 }} />
        <Select allowClear placeholder="状态" value={statusFilter}
          onChange={setStatusFilter} style={{ width: 140 }}
          options={Object.entries(STATUS_LABEL).map(([value, label]) =>
            ({ value, label }))} />
      </Space>

      {error && <Alert type="error" showIcon message={error}
        style={{ marginBottom: 16 }} />}

      <Spin spinning={loading}>
        <Table<ReportDefinitionOut>
          rowKey="def_id"
          columns={columns}
          dataSource={visible}
          pagination={{ pageSize: 20, showSizeChanger: true }}
          locale={{ emptyText: '还没有报表定义。点「新建定义」开始。' }}
        />
      </Spin>
  </div>
  );
}
