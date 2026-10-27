/**
 * ADMIN 建项目页（P9B-2 · 延后的 minor · Batch F · SPEC §7.20）。
 *
 * ## 为什么必须有这个页面
 *
 * T-1 只交付了**后端**的 `POST /projects` ⇒ 项目**建不出来** ⇒ 签署流程的对象
 * （记录 / 交付物）全都挂在项目下 ⇒ 真实 UI 上**根本走不通**（只能靠 mock
 * 验证）。
 *
 * ## ⚠️ 建完项目**当场就能送审**
 *
 * 后端在**同一事务**里给新项目绑一份 ACTIVE 的 RECORD 签署矩阵（R-17）
 * ⇒ 建完项目就能提交批准 ⇒ 页面要把这句话**说给用户听**（否则用户以为
 * 还要去矩阵页手动绑一次）。
 *
 * ## ⚠️ 工作区**必须已存在**
 *
 * `projects.workspace_id` 是 FK ⇒ 后端不建孤儿项目（不存在 ⇒ 404）
 * ⇒ 这里只能**选**已有的工作区，不能新建。
 */
import { useCallback, useEffect, useState } from 'react';
import type { JSX } from 'react';
import { Alert, Button, Card, Form, Input, Select, Space, Typography } from 'antd';

import { PageHeader } from '../../components/common/PageHeader';
import { projectsApi, type ProjectCreate, type WorkspaceOut } from '../../api/projects';
import { describePcsError } from '../../api/errors';
import type { components } from '../../types/api';

type ProductCategory = components['schemas']['ProductCategory'];

/** 产品类别 3 值（契约枚举 —— 不手写字面量）。 */
const PRODUCT_CATEGORIES: { value: ProductCategory; label: string }[] = [
  { value: 'REFINING', label: '炼油（电折标按「等价值」0.21 kg 标油/kWh）' },
  { value: 'ETHYLENE', label: '乙烯（电折标按「等价值」0.21 kg 标油/kWh）' },
  { value: 'OTHER', label: '其他（电折标按「当量值」0.086 kg 标油/kWh）' },
];

export function ProjectAdminPage(): JSX.Element {
  const [form] = Form.useForm<ProjectCreate>();
  const [workspaces, setWorkspaces] = useState<WorkspaceOut[]>([]);
  const [loadingWs, setLoadingWs] = useState(false);
  const [wsError, setWsError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const loadWorkspaces = useCallback(async () => {
    setLoadingWs(true);
    setWsError(null);
    try {
      setWorkspaces(await projectsApi.listWorkspaces());
    } catch (err: unknown) {
      setWorkspaces([]);
      setWsError(describePcsError(err, '加载工作区列表失败'));
    } finally {
      setLoadingWs(false);
    }
  }, []);

  useEffect(() => {
    void loadWorkspaces();
  }, [loadWorkspaces]);

  async function submit(values: ProjectCreate): Promise<void> {
    setSubmitting(true);
    setErrorMsg(null);
    setNotice(null);
    try {
      const created = await projectsApi.create(values);
      setNotice(
        `已建项目 ${created.project_no}（${created.project_id}）—— 已自动绑定记录级签署矩阵，可以提交批准了。`,
      );
      form.resetFields();
    } catch (err: unknown) {
      setErrorMsg(describePcsError(err, '建项目失败'));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div data-testid="project-admin-page">
      <PageHeader
        title="建项目"
        actions={
          <Button data-testid="project-reload-workspaces" onClick={() => void loadWorkspaces()}>
            刷新工作区
          </Button>
        }
      />

      <Typography.Paragraph type="secondary">
        ⚠️ 项目的「工作区」必须已存在（projects.workspace_id 是外键 ⇒ 后端不建孤儿项目）。
        建完项目会自动绑定一份记录级签署矩阵 ⇒ 建完当场就能提交批准。
      </Typography.Paragraph>

      {wsError && (
        <Alert
          type="error"
          showIcon
          message={wsError}
          data-testid="project-workspace-error"
          style={{ marginBottom: 16 }}
        />
      )}
      {errorMsg && (
        <Alert
          type="error"
          showIcon
          message={errorMsg}
          data-testid="project-error"
          style={{ marginBottom: 16 }}
        />
      )}
      {notice && (
        <Alert
          type="success"
          showIcon
          message={notice}
          data-testid="project-notice"
          style={{ marginBottom: 16 }}
        />
      )}

      <Card>
        <Form<ProjectCreate>
          form={form}
          layout="vertical"
          onFinish={(v) => void submit(v)}
          initialValues={{ product_category: 'OTHER' }}
        >
          <Form.Item
            label="项目编号"
            name="project_no"
            rules={[{ required: true, message: '项目编号必填' }]}
          >
            <Input data-testid="project-no" placeholder="全局唯一" />
          </Form.Item>
          <Form.Item
            label="项目名"
            name="project_name"
            rules={[{ required: true, message: '项目名必填' }]}
          >
            <Input data-testid="project-name" />
          </Form.Item>
          <Form.Item
            label="业主"
            name="owner_company"
            rules={[{ required: true, message: '业主必填' }]}
          >
            <Input data-testid="project-owner-company" />
          </Form.Item>
          <Form.Item
            label="所在地"
            name="location"
            rules={[{ required: true, message: '所在地必填' }]}
          >
            <Input data-testid="project-location" />
          </Form.Item>
          <Form.Item
            label="项目类型"
            name="project_type"
            rules={[{ required: true, message: '项目类型必填' }]}
          >
            <Input data-testid="project-type" placeholder="如 ENGINEERING" />
          </Form.Item>
          <Form.Item
            label="设计阶段"
            name="design_phase"
            rules={[{ required: true, message: '设计阶段必填' }]}
          >
            <Input data-testid="project-design-phase" placeholder="如 FEED" />
          </Form.Item>
          <Form.Item
            label="单位制"
            name="unit_system"
            rules={[{ required: true, message: '单位制必填' }]}
          >
            <Input data-testid="project-unit-system" placeholder="如 SI" />
          </Form.Item>
          <Form.Item
            label="工作区"
            name="workspace_id"
            rules={[{ required: true, message: '必须选一个已存在的工作区' }]}
          >
            <Select
              data-testid="project-workspace"
              loading={loadingWs}
              placeholder="选一个已存在的工作区"
              options={workspaces.map((w) => ({
                value: w.workspace_id,
                label: `${w.name}（${w.workspace_type}）`,
              }))}
            />
          </Form.Item>
          <Form.Item
            label="产品类别"
            name="product_category"
            rules={[{ required: true, message: '产品类别必填' }]}
          >
            <Select
              data-testid="project-product-category"
              options={PRODUCT_CATEGORIES.map((c) => ({ value: c.value, label: c.label }))}
            />
          </Form.Item>
          <Space>
            <Button type="primary" htmlType="submit" loading={submitting} data-testid="project-submit">
              建项目
            </Button>
          </Space>
        </Form>
      </Card>
    </div>
  );
}

export default ProjectAdminPage;
