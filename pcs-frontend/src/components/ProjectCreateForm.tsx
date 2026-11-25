/**
 * 建项目表单（P10-K · W-6c）—— **项目页与向导共用**。
 *
 * ## 为什么抽出来
 *
 * `ProjectAdminPage`（项目页）与 `ProjectWizardPage`（向导第 1 步）
 * **都要**这 8 个必填字段 + 工作区下拉 ⇒ ⇒ ⇒ 抄两份 ⇒ ⇒ ⇒ **必漂**
 * ⇒ ⇒ ⇒（而且漂了以后没人知道哪份是对的）⇒ ⇒ ⇒ 所以**一份**。
 *
 * ## ⚠️ 工作区下拉要**过滤掉已挂项目的工作区**
 *
 * `POST /projects` 的约束：**一个工作区只能挂一个项目**（`projects.py:143-158`
 * ⇒ ⇒ ⇒ 已挂项目的工作区再选一次 ⇒ ⇒ ⇒ **409**）
 * ⇒ ⇒ ⇒ ⇒ 而 `GET /workspaces` **返 `project_id`**（非空 = 已被占用）
 * ⇒ ⇒ ⇒ ⇒ **前端要过滤** ⇒ ⇒ ⇒ 否则用户选到一个**必然 409** 的工作区
 * ⇒ ⇒ ⇒ ⇒ 那就是「点了才知道」——本仓的老毛病。
 *
 * ## ⚠️ `unit_system` 是**下拉**不是自由文本
 *
 * 后端已是词表（`UnitSystem` = SI / US）⇒ ⇒ ⇒ 自由文本框会让用户填
 * 「公制」⇒ ⇒ ⇒ 真后端 422 ⇒ ⇒ ⇒ 词表在**契约**里 ⇒ ⇒ ⇒ 不手写字面量。
 */
import { useCallback, useEffect, useState } from 'react';
import type { JSX } from 'react';
import { Alert, Button, Form, Input, Select, Space } from 'antd';

import {
  PRODUCT_CATEGORIES,
  UNIT_SYSTEMS,
  projectsApi,
  type ProjectCreate,
  type WorkspaceOut,
} from '../api/projects';

export interface ProjectCreateFormProps {
  form: FormInstance<ProjectCreate>;
  onFinish: (values: ProjectCreate) => void | Promise<void>;
  submitting?: boolean;
  /** 额外的表单项（如向导的 `status='DRAFT'` ⇒ ⇒ 隐藏即可，默认不传）。 */
  hiddenValues?: Partial<ProjectCreate>;
  /**
   * **哪些字段被用户动过**（`onValuesChange` 的 `changed` 里出现过的键）。
   *
   * ⚠️ **为什么需要它** —— P10-K · TODO-210 · **D1 裁决**：「用户动没动过
   * 单位制」这个信息**只有表单持有** ⇒ ⇒ ⇒ 后端**猜不出来** ⇒ ⇒ ⇒
   * ⇒ ⇒ ⇒ 调用方**明说**（「单位制由谁决定」）⇒ ⇒ ⇒ 后端照办
   * ⇒ ⇒ ⇒ ⇒ 否则要么**静默覆盖**用户的显式选择（= 本仓最恨的那类事故）
   * ⇒ ⇒ ⇒ ⇒ 要么**永远不覆盖**（模板的默认值形同虚设）。
   */
  onValuesChange?: (changed: Partial<ProjectCreate>) => void;
}

type FormInstance<T> = ReturnType<typeof Form.useForm<T>>[0];

export function ProjectCreateForm({
  form,
  onFinish,
  submitting,
  hiddenValues,
  onValuesChange,
}: ProjectCreateFormProps): JSX.Element {
  const [workspaces, setWorkspaces] = useState<WorkspaceOut[]>([]);
  const [loadingWs, setLoadingWs] = useState(false);
  const [wsError, setWsError] = useState<string | null>(null);

  const loadWorkspaces = useCallback(async () => {
    setLoadingWs(true);
    setWsError(null);
    try {
      const all = await projectsApi.listWorkspaces();
      // ⚠️ **过滤掉已挂项目的工作区**（一个工作区只能挂一个项目 ⇒ ⇒ ⇒
      //   选了必然 409 ⇒ ⇒ ⇒ 那就是「点了才知道」）
      setWorkspaces(all.filter((w) => !w.project_id));
    } catch (err: unknown) {
      setWorkspaces([]);
      setWsError(err instanceof Error ? err.message : '加载工作区列表失败');
    } finally {
      setLoadingWs(false);
    }
  }, []);

  useEffect(() => {
    void loadWorkspaces();
  }, [loadWorkspaces]);

  return (
    <>
      {wsError ? (
        <Alert
          type="error"
          showIcon
          message={wsError}
          data-testid="project-workspace-error"
          style={{ marginBottom: 16 }}
        />
      ) : null}
      <Form<ProjectCreate>
        form={form}
        layout="vertical"
        onFinish={(v) => void onFinish({ ...hiddenValues, ...v })}
        onValuesChange={(changed) => onValuesChange?.(changed)}
        initialValues={{ product_category: 'OTHER', unit_system: 'SI' }}
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
          <Select
            data-testid="project-unit-system"
            options={UNIT_SYSTEMS.map((u) => ({ value: u.value, label: u.label }))}
          />
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
          <Button
            type="primary"
            htmlType="submit"
            loading={submitting}
            data-testid="project-submit"
          >
            建项目
          </Button>
        </Space>
      </Form>
    </>
  );
}

export default ProjectCreateForm;
