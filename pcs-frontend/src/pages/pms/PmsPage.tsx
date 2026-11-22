/**
 * PmsPage — PMS 管道材料规格（P10-H · T2 · TODO-195）。
 *
 * ## 数据源
 *
 * `GET /projects/{project_id}/pms`（**真端点**）⇒ ⇒ 项目作用域来自
 * `useProjectScope`（顶栏的选择器）⇒ ⇒ 换项目 ⇒ 这一页跟着换。
 *
 * ⚠️ **此前本页是占位**（P10-C · T2 · TODO-159）：调的是一个**契约里没有**的
 * 端点 ⇒ ⇒ 真后端 404 ⇒ ⇒ mock 通道有 handler ⇒ 一路绿灯。
 *
 * ## 签署
 *
 * 送审走**通用记录工作流**（`/records/PmsItem/{id}/submit-approval`）
 * ⇒ ⇒ 页面只给 **DRAFT** 行一个「提交审核」按钮 ⇒ ⇒ 状态由后端说了算。
 */
import { useCallback, useEffect, useState } from 'react';
import {
  Alert,
  Button,
  Form,
  Input,
  Modal,
  Select,
  Space,
  Table,
  Tag,
  message,
} from 'antd';

import { PageHeader } from '../../components/common/PageHeader';
import { StateBadge } from '../../components/common/StateBadge';
import { pmsApi, type PmsItem, type PmsItemCreate } from '../../api/pms';
import { recordActionsApi } from '../../api/recordActions';
import { useProjectScope } from '../../hooks/useProjectScope';
import type { RecordSignStatus } from '../../types/records';
import type { StrictColumns } from '../../types/strictColumns';

const HAZARD_OPTIONS = [
  { value: 'LOW', label: '低' },
  { value: 'MEDIUM', label: '中' },
  { value: 'HIGH', label: '高' },
];

const HAZARD_COLOR: Record<string, string> = {
  LOW: 'blue',
  MEDIUM: 'gold',
  HIGH: 'red',
};

export function PmsPage(): JSX.Element {
  const { projectId, loading: scopeLoading, error: scopeError } = useProjectScope();
  const [items, setItems] = useState<PmsItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [editing, setEditing] = useState<PmsItem | null>(null);
  const [creating, setCreating] = useState(false);
  const [form] = Form.useForm<PmsItemCreate>();
  const [msg, msgCtx] = message.useMessage();

  const reload = useCallback(async () => {
    if (!projectId) {
      setItems([]);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const res = await pmsApi.list(projectId);
      setItems(res.items ?? []);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'PMS 列表加载失败');
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  useEffect(() => {
    void reload();
  }, [reload]);

  async function handleSave(): Promise<void> {
    if (!projectId) return;
    const values = await form.validateFields();
    try {
      if (editing) {
        await pmsApi.update(projectId, editing.item_id, values);
        msg.success('已保存');
      } else {
        await pmsApi.create(projectId, values);
        msg.success('已新建（PMS 编号项目内唯一）');
      }
      setEditing(null);
      setCreating(false);
      form.resetFields();
      await reload();
    } catch (err) {
      msg.error(err instanceof Error ? err.message : '保存失败');
    }
  }

  async function handleSubmitApproval(item: PmsItem): Promise<void> {
    try {
      await recordActionsApi.submitApproval('PmsItem', item.item_id, '提交审核');
      msg.success('已提交审核');
      await reload();
    } catch (err) {
      msg.error(err instanceof Error ? err.message : '提交审核失败');
    }
  }

  const columns: StrictColumns<PmsItem> = [
    {
      title: 'pms_no',
      dataIndex: 'pms_no',
      width: 160,
      render: (v: string) => (
        <span style={{ fontFamily: 'var(--font-mono, monospace)' }}>{v}</span>
      ),
    },
    { title: '描述', dataIndex: 'description' },
    { title: 'pms_class', dataIndex: 'pms_class', width: 120 },
    {
      title: 'hazard',
      dataIndex: 'hazard_level',
      width: 100,
      render: (h: string) => (
        <Tag color={HAZARD_COLOR[h] ?? 'default'} data-testid="pms-hazard">
          {h}
        </Tag>
      ),
    },
    {
      title: '状态',
      dataIndex: 'sign_status',
      width: 110,
      // ⚠️ 契约里 `sign_status` 是**裸 string**（OpenAPI 不带词表）
      // ⇒ ⇒ 这里断言成仓内的 9 态 union（`types/records.ts`）。
      render: (s: string) => (
        <StateBadge status={s as RecordSignStatus} module="CONFIG" />
      ),
    },
    {
      title: '操作',
      key: 'actions',
      width: 160,
      render: (_v: unknown, row: PmsItem) =>
        row.sign_status === 'DRAFT' ? (
          <Space>
            <Button
              size="small"
              data-testid="pms-edit"
              onClick={() => {
                setEditing(row);
                form.setFieldsValue({
                  pms_no: row.pms_no,
                  description: row.description,
                  pms_class: row.pms_class,
                  hazard_level: row.hazard_level as PmsItemCreate['hazard_level'],
                });
              }}
            >
              编辑
            </Button>
            <Button
              size="small"
              type="primary"
              data-testid="pms-submit"
              onClick={() => void handleSubmitApproval(row)}
            >
              提交审核
            </Button>
          </Space>
        ) : null,
    },
  ];

  if (scopeError) {
    return (
      <div data-testid="pms-page">
        <PageHeader title="PMS 管道材料规格" module="CONFIG" actions={null as unknown as undefined} />
        <Alert
          type="warning"
          showIcon
          data-testid="pms-scope-error"
          message="没有可用的项目作用域"
          description={scopeError}
        />
      </div>
    );
  }

  return (
    <div data-testid="pms-page">
      <PageHeader
        title="PMS 管道材料规格"
        module="CONFIG"
        actions={
          <Button
            type="primary"
            data-testid="pms-create"
            disabled={!projectId || scopeLoading}
            onClick={() => {
              setCreating(true);
              setEditing(null);
              form.resetFields();
            }}
          >
            新建
          </Button>
        }
      />

      {error ? (
        <Alert
          type="error"
          showIcon
          style={{ marginBottom: 16 }}
          data-testid="pms-error"
          message="PMS 列表加载失败"
          description={error}
        />
      ) : null}

      <Table<PmsItem>
        rowKey="item_id"
        columns={columns}
        dataSource={items}
        loading={loading}
        pagination={false}
        size="small"
        locale={{ emptyText: '本项目还没有 PMS 条目' }}
      />

      <Modal
        open={creating || editing !== null}
        title={editing ? '编辑 PMS 条目' : '新建 PMS 条目'}
        onCancel={() => {
          setCreating(false);
          setEditing(null);
        }}
        onOk={() => void handleSave()}
        destroyOnHidden
      >
        <Form form={form} layout="vertical" preserve={false}>
          <Form.Item
            name="pms_no"
            label="PMS 编号"
            rules={[{ required: true, message: 'PMS 编号必填' }]}
          >
            <Input data-testid="pms-form-no" />
          </Form.Item>
          <Form.Item name="description" label="描述">
            <Input data-testid="pms-form-desc" />
          </Form.Item>
          <Form.Item name="pms_class" label="pms_class">
            <Input data-testid="pms-form-class" />
          </Form.Item>
          <Form.Item name="hazard_level" label="危险等级">
            <Select options={HAZARD_OPTIONS} data-testid="pms-form-hazard" />
          </Form.Item>
        </Form>
      </Modal>

      {msgCtx}
    </div>
  );
}

export default PmsPage;
