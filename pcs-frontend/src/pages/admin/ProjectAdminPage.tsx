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
import { useState } from 'react';
import type { JSX } from 'react';
import { Alert, Card, Form, Typography } from 'antd';

import { PageHeader } from '../../components/common/PageHeader';
import { ProjectCreateForm } from '../../components/ProjectCreateForm';
import { projectsApi, type ProjectCreate } from '../../api/projects';
import { describePcsError } from '../../api/errors';

export function ProjectAdminPage(): JSX.Element {
  const [form] = Form.useForm<ProjectCreate>();
  const [submitting, setSubmitting] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

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
        actions={null as unknown as undefined}
      />

      <Typography.Paragraph type="secondary">
        ⚠️ 项目的「工作区」必须已存在（projects.workspace_id 是外键 ⇒ 后端不建孤儿项目）。
        建完项目会自动绑定一份记录级签署矩阵 ⇒ 建完当场就能提交批准。
      </Typography.Paragraph>

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
        {/* ⚠️ **与向导共用一份表单**（P10-K · W-6c）⇒ ⇒ ⇒ 抄两份必漂 */}
        <ProjectCreateForm form={form} submitting={submitting} onFinish={(v) => void submit(v)} />
      </Card>
    </div>
  );
}

export default ProjectAdminPage;
