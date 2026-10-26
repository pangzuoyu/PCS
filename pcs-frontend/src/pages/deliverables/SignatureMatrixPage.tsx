/**
 * SignatureMatrixPage —— 签署矩阵管理面（TODO-079 · P9A-DLV-011 T3 的前端）。
 *
 * ## 页面分两段（对应后端两组端点）
 *
 * 1. **矩阵模板**（全局表）—— 列表 / 新建 / 编辑步骤。建与改只有
 *    **SYSTEM_ADMIN** 能做（模板是全局的 ⇒ 一个项目改了它，别的项目跟着变）。
 * 2. **项目绑定** —— 把某个模板绑到「项目 × 模块」。只有**项目负责人**
 *    （项目内角色 `PROJECT_LEAD`）能绑（用户 2026-10-26 裁决）。
 *
 * ## 三条纪律
 *
 * 1. ⚠️ **步骤是矩阵的主体** —— 矩阵回答的是「这个文档谁该签、签几步」⇒
 *    步骤编辑是页面的核心（不是附表）。步骤写坏了后端 422
 *    （`SIGNATURE_MATRIX_INVALID`）⇒ **不部分入库** ⇒ 前端不做「跳过坏步骤」
 *    的乐观处理。
 * 2. ⚠️ **步骤序号由用户给，但后端会排序** ⇒ 前端**照用户填的序号显示**，
 *    保存后按后端返回的顺序渲染（后端是权威）。
 * 3. ⚠️ **403 要说人话** —— 「你不是项目负责人」这句话后端已经给了
 *    （`PROJECT_ROLE_FORBIDDEN`）⇒ 直接展示，别自己编。
 */
import { useCallback, useEffect, useState } from 'react';
import {
  Alert,
  Button,
  Form,
  Input,
  InputNumber,
  Modal,
  Popconfirm,
  Select,
  Space,
  Switch,
  Table,
  Tag,
} from 'antd';
import type { ColumnsType } from 'antd/es/table';

import { PageHeader } from '../../components/common/PageHeader';
import { extractPcsError } from '../../api/errors';
import {
  MATRIX_MODULES,
  MATRIX_STATUSES,
  signatureMatricesApi,
  type MatrixStepInput,
  type SignatureMatrix,
} from '../../api/signatureMatrices';
import { PROJECT_ID } from '../../constants/env';

/** 可担任签署步骤的角色（= 后端 `sign_role` 是**全局角色**）。 */
const SIGN_ROLES = [
  'DESIGNER',
  'CHECKER',
  'REVIEWER',
  'APPROVER',
  'PROCESS_CONTROLLER',
  'SYSTEM_ADMIN',
];

interface StepFormValue {
  step_order: number;
  sign_role: string;
  required: boolean;
  can_self_check: boolean;
  can_skip: boolean;
}

interface MatrixFormValue {
  matrix_name: string;
  module: (typeof MATRIX_MODULES)[number];
  doc_type: string;
  version_purpose: string;
  status: (typeof MATRIX_STATUSES)[number];
  steps: StepFormValue[];
}

const EMPTY_FORM: MatrixFormValue = {
  matrix_name: '',
  module: '*',
  doc_type: '',
  version_purpose: 'ISSUED_FOR_CONSTRUCTION',
  status: 'DRAFT',
  steps: [
    { step_order: 1, sign_role: 'CHECKER', required: true, can_self_check: true, can_skip: false },
  ],
};

export function SignatureMatrixPage(): JSX.Element {
  const [items, setItems] = useState<SignatureMatrix[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [editing, setEditing] = useState<SignatureMatrix | null>(null);
  const [open, setOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [form] = Form.useForm<MatrixFormValue>();
  const [bindForm] = Form.useForm<{ module: string; matrix_id: string }>();

  const reload = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await signatureMatricesApi.list({ limit: 200 });
      setItems(res.items ?? []);
    } catch (err) {
      const env = extractPcsError(err);
      setError(env?.message ?? '矩阵列表加载失败');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void reload();
  }, [reload]);

  function openCreate(): void {
    setEditing(null);
    form.setFieldsValue(EMPTY_FORM);
    setOpen(true);
  }

  function openEdit(row: SignatureMatrix): void {
    setEditing(row);
    form.setFieldsValue({
      matrix_name: row.matrix_name,
      module: row.module as (typeof MATRIX_MODULES)[number],
      doc_type: row.doc_type,
      version_purpose: row.version_purpose,
      status: row.status as (typeof MATRIX_STATUSES)[number],
      steps: row.steps.map((s) => ({
        step_order: s.step_order,
        sign_role: s.sign_role,
        required: s.required,
        can_self_check: s.can_self_check,
        can_skip: s.can_skip,
      })),
    });
    setOpen(true);
  }

  async function save(): Promise<void> {
    const values = await form.validateFields();
    setSaving(true);
    setError(null);
    try {
      const body = {
        ...values,
        steps: values.steps as MatrixStepInput[],
      };
      if (editing) {
        await signatureMatricesApi.update(editing.matrix_id, body);
      } else {
        await signatureMatricesApi.create(body);
      }
      setOpen(false);
      await reload();
    } catch (err) {
      const env = extractPcsError(err);
      // ⚠️ 校验失败（后端 422）时**不关弹窗** ⇒ 用户能改完再提交
      if (!env || env.code === 'VALIDATION_ERROR') {
        setError(env?.message ?? '保存失败');
        return;
      }
      setError(env?.message ?? '保存失败');
    } finally {
      setSaving(false);
    }
  }

  async function bind(): Promise<void> {
    const values = await bindForm.validateFields();
    setError(null);
    try {
      await signatureMatricesApi.bind(PROJECT_ID, values);
      await reload();
    } catch (err) {
      const env = extractPcsError(err);
      setError(env?.message ?? '绑定失败');
    }
  }

  async function unbind(module: string): Promise<void> {
    setError(null);
    try {
      await signatureMatricesApi.unbind(PROJECT_ID, module);
      await reload();
    } catch (err) {
      const env = extractPcsError(err);
      setError(env?.message ?? '解绑失败');
    }
  }

  const columns: ColumnsType<SignatureMatrix> = [
    { title: '名称', dataIndex: 'matrix_name', key: 'matrix_name' },
    { title: '模块', dataIndex: 'module', key: 'module' },
    { title: '文档类型', dataIndex: 'doc_type', key: 'doc_type' },
    { title: '版本目的', dataIndex: 'version_purpose', key: 'version_purpose' },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      render: (v: string) => <Tag color={v === 'ACTIVE' ? 'green' : 'default'}>{v}</Tag>,
    },
    {
      title: '签署步骤',
      key: 'steps',
      render: (_: unknown, row: SignatureMatrix) =>
        row.steps.length === 0 ? (
          '—'
        ) : (
          <span>
            {row.steps
              .slice()
              .sort((a, b) => a.step_order - b.step_order)
              .map((s) => `${s.step_order}.${s.sign_role}`)
              .join(' → ')}
          </span>
        ),
    },
    {
      title: '操作',
      key: '__actions',
      render: (_: unknown, row: SignatureMatrix) => (
        <Space>
          <Button size="small" onClick={() => openEdit(row)}>
            编辑步骤
          </Button>
          <Popconfirm
            title="解绑该模块的矩阵？"
            description="解绑后本项目该模块回落内置默认矩阵。"
            onConfirm={() => void unbind(row.module)}
          >
            <Button size="small" danger>
              解绑本项目
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <div data-testid="signature-matrix-page">
      <PageHeader
        title="签署矩阵"
        actions={
          <Space>
            <Button onClick={() => void reload()}>刷新</Button>
            <Button type="primary" onClick={openCreate}>
              新建矩阵
            </Button>
          </Space>
        }
      />
      {error && (
        <Alert
          type="error"
          showIcon
          message={error}
          data-testid="signature-matrix-error"
          style={{ marginBottom: 16 }}
        />
      )}
      <Table<SignatureMatrix>
        rowKey="matrix_id"
        columns={columns}
        dataSource={items}
        loading={loading}
        scroll={{ x: 'max-content' }}
        pagination={false}
      />

      <Modal
        title={editing ? `编辑矩阵：${editing.matrix_name}` : '新建矩阵'}
        open={open}
        onCancel={() => setOpen(false)}
        onOk={() => void save()}
        confirmLoading={saving}
        width={720}
        // ⚠️ antd 5.29 起 `destroyOnClose` 已弃用（控制台报错）⇒ 用 `destroyOnHidden`
        destroyOnHidden
      >
        <Form form={form} layout="vertical" initialValues={EMPTY_FORM}>
          <Form.Item
            name="matrix_name"
            label="矩阵名称"
            rules={[{ required: true, message: '请填矩阵名称' }]}
          >
            <Input placeholder="例：项目专用 3 级矩阵" />
          </Form.Item>
          <Space size="large" wrap>
            <Form.Item name="module" label="适用模块">
              <Select
                style={{ width: 200 }}
                options={MATRIX_MODULES.map((m) => ({ value: m, label: m }))}
              />
            </Form.Item>
            <Form.Item
              name="doc_type"
              label="文档类型"
              rules={[{ required: true, message: '请填文档类型' }]}
            >
              <Input placeholder="例：CALCULATION_BOOK" style={{ width: 220 }} />
            </Form.Item>
            <Form.Item
              name="version_purpose"
              label="版本目的"
              rules={[{ required: true, message: '请填版本目的' }]}
            >
              <Input placeholder="例：ISSUED_FOR_CONSTRUCTION" style={{ width: 240 }} />
            </Form.Item>
            <Form.Item name="status" label="状态">
              <Select
                style={{ width: 160 }}
                options={MATRIX_STATUSES.map((s) => ({ value: s, label: s }))}
              />
            </Form.Item>
          </Space>

          <Form.List
            name="steps"
            rules={[
              {
                validator: async (_, steps: StepFormValue[]) => {
                  if (!steps || steps.length === 0) {
                    throw new Error('矩阵至少要有一步（否则没有任何人签字）');
                  }
                },
              },
            ]}
          >
            {(fields, { add, remove }) => (
              <>
                <div
                  style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    marginTop: 8,
                  }}
                >
                  <strong>签署步骤</strong>
                  <Button
                    size="small"
                    onClick={() =>
                      add({
                        step_order: fields.length + 1,
                        sign_role: 'APPROVER',
                        required: true,
                        can_self_check: false,
                        can_skip: false,
                      })
                    }
                  >
                    加一步
                  </Button>
                </div>
                {fields.map((field) => (
                  <Space key={field.key} align="baseline" wrap style={{ marginTop: 8 }}>
                    <Form.Item
                      {...field}
                      name={[field.name, 'step_order']}
                      rules={[{ required: true, message: '序号' }]}
                    >
                      <InputNumber min={1} style={{ width: 80 }} placeholder="序号" />
                    </Form.Item>
                    <Form.Item
                      {...field}
                      name={[field.name, 'sign_role']}
                      rules={[{ required: true, message: '角色' }]}
                    >
                      <Select
                        style={{ width: 180 }}
                        placeholder="签署角色"
                        options={SIGN_ROLES.map((r) => ({ value: r, label: r }))}
                      />
                    </Form.Item>
                    <Form.Item {...field} name={[field.name, 'required']} valuePropName="checked">
                      <Switch checkedChildren="必签" unCheckedChildren="可跳过" />
                    </Form.Item>
                    <Form.Item
                      {...field}
                      name={[field.name, 'can_self_check']}
                      valuePropName="checked"
                    >
                      <Switch checkedChildren="可自校" unCheckedChildren="禁自校" />
                    </Form.Item>
                    <Form.Item {...field} name={[field.name, 'can_skip']} valuePropName="checked">
                      <Switch checkedChildren="可跳过" unCheckedChildren="不可跳过" />
                    </Form.Item>
                    <Button size="small" danger onClick={() => remove(field.name)}>
                      删
                    </Button>
                  </Space>
                ))}
              </>
            )}
          </Form.List>
        </Form>
      </Modal>

      <div style={{ marginTop: 24 }}>
        <h3>绑定到当前项目</h3>
        <p style={{ color: 'rgba(0,0,0,0.45)' }}>
          绑定决定「本项目该模块谁该签」⇒ 只有**项目负责人**能绑（后端 403
          `PROJECT_ROLE_FORBIDDEN`）。同一项目同一模块只保留一行绑定（换绑 = 改同一行）。
        </p>
        <Form
          form={bindForm}
          layout="inline"
          initialValues={{ module: 'RECORD' }}
          style={{ marginTop: 8 }}
        >
          <Form.Item name="module" label="模块">
            <Select
              style={{ width: 180 }}
              options={MATRIX_MODULES.filter((m) => m !== '*').map((m) => ({ value: m, label: m }))}
            />
          </Form.Item>
          <Form.Item
            name="matrix_id"
            label="矩阵"
            rules={[{ required: true, message: '请选矩阵' }]}
          >
            <Select
              style={{ width: 280 }}
              placeholder="选择要绑定的矩阵"
              options={items.map((m) => ({ value: m.matrix_id, label: m.matrix_name }))}
            />
          </Form.Item>
          <Form.Item>
            <Button type="primary" onClick={() => void bind()}>
              绑定
            </Button>
          </Form.Item>
        </Form>
      </div>
    </div>
  );
}

export default SignatureMatrixPage;
