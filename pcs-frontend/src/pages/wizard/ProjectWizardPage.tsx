/**
 * ProjectWizardPage — 项目向导（P10-K · W-6 · SPEC §7.5）。
 *
 * ## 4 步（2026-11-25 人裁）
 *
 * | 步 | 内容 | 端点 |
 * |---|---|---|
 * | 1 | **建项目**（基本信息 + 工作区 + 单位制）⇒ ⇒ **`status='DRAFT'`** | `POST /projects` |
 * | 2 | **项目人员**（加授权 + 项目内角色）| `POST /user-projects/grant` |
 * | 3 | **选模板**（**必选** ⇒ 不选不能继续）| `GET /project-templates` + `POST /projects/{id}/apply-template` |
 * | 4 | **确认** ⇒ ⇒ **`status` → `ACTIVE`** + 摘要 + 「去项目录 BEDD」| `PATCH /projects/{id}/status` |
 *
 * ## ⚠️ **BEDD 必须在项目建完后存**（2026-11-24 人裁）
 *
 * BEDD 是**项目的基本依据文件** ⇒ ⇒ ⇒ 它**必须**在项目建好后才有意义
 * ⇒ ⇒ ⇒ 所以第 4 步给「**去项目录 BEDD**」的入口（**深链**到现有 `BeddPage`）
 * ⇒ ⇒ ⇒ ⇒ **不抽 `BeddForm`**、**不动已工作的 `BeddPage`**。
 *
 * ## ⚠️ **中间态**：第 2/3 步失败 ⇒ ⇒ ⇒ **保留已建项目**（不拆）
 *
 * 拆掉它 ⇒ ⇒ ⇒ 需要**删除能力**（本仓**刻意没有**：`projects` 没有 DELETE 端点）
 * ⇒ ⇒ ⇒ ⇒ 而「建完又删」会**占掉那个工作区**（一个工作区只能挂一个项目）
 * ⇒ ⇒ ⇒ ⇒ ⇒ 所以**保留** + 明确告知 + 给两个出口（去项目页 / 留在本页重试）
 * ⇒ ⇒ ⇒ ⇒ 项目留在 **`DRAFT`** ⇒ ⇒ ⇒ 运维一眼能认出「这是弃单」。
 *
 * ## ⚠️ **向导不可重入**
 *
 * `/wizard` 是「**新建**项目向导」⇒ ⇒ ⇒ 已建的项目**不再走向导**
 * ⇒ ⇒ ⇒ 续做走**项目页**（PMS 页对 DRAFT 项目给「完成配置并激活」入口）。
 */
import { useCallback, useEffect, useState } from 'react';
import type { JSX } from 'react';
import {
  Alert,
  Button,
  Card,
  Descriptions,
  Form,
  Input,
  Select,
  Space,
  Steps,
  Typography,
  message,
} from 'antd';
import { useNavigate } from 'react-router-dom';

import { PageHeader } from '../../components/common/PageHeader';
import { ProjectCreateForm } from '../../components/ProjectCreateForm';
import {
  projectTemplatesApi,
  projectsApi,
  userProjectsApi,
  type ProjectCreate,
  type ProjectRole,
  type ProjectTemplateSummary,
} from '../../api/projects';
import { describePcsError } from '../../api/errors';
import { useProjectScopeStore } from '../../store/projectScope';

const STEPS = [
  { title: '建项目', description: '基本信息 · 工作区 · 单位制' },
  { title: '项目人员', description: '加授权与项目内角色' },
  { title: '选模板', description: '必选 · 决定签署矩阵与清单' },
  { title: '确认', description: '激活 · 去录 BEDD' },
];

/** 项目内角色（契约词表）。 */
const PROJECT_ROLES: { value: ProjectRole; label: string }[] = [
  { value: 'PROJECT_LEAD', label: 'PROJECT_LEAD（项目负责人）' },
  { value: 'DESIGNER', label: 'DESIGNER（设计）' },
  { value: 'CHECKER', label: 'CHECKER（校核）' },
  { value: 'REVIEWER', label: 'REVIEWER（审核）' },
  { value: 'APPROVER', label: 'APPROVER（批准）' },
  { value: 'VIEWER', label: 'VIEWER（查看）' },
];

export function ProjectWizardPage(): JSX.Element {
  const navigate = useNavigate();
  const [form] = Form.useForm<ProjectCreate>();
  const [current, setCurrent] = useState(0);
  const [submitting, setSubmitting] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [msg, msgCtx] = message.useMessage();

  // ---- 第 1 步的产物 -------------------------------------------------
  const [projectId, setProjectId] = useState<string | null>(null);
  const [projectNo, setProjectNo] = useState<string>('');
  // ---- 第 2 步 -------------------------------------------------------
  const [grantUserId, setGrantUserId] = useState<string>('');
  const [grantRole, setGrantRole] = useState<ProjectRole>('DESIGNER');
  // ---- 第 3 步 -------------------------------------------------------
  const [templates, setTemplates] = useState<ProjectTemplateSummary[]>([]);
  const [templateId, setTemplateId] = useState<string | undefined>(undefined);
  const [templatesError, setTemplatesError] = useState<string | null>(null);
  /** 第 2/3 步失败 ⇒ ⇒ ⇒ **保留项目** + 明确告知 + 两个出口。 */
  const [partial, setPartial] = useState<string | null>(null);

  const loadTemplates = useCallback(async () => {
    setTemplatesError(null);
    try {
      const list = await projectTemplatesApi.list();
      setTemplates(list);
      if (list.length === 0) {
        setTemplatesError(
          '没有已发布的项目模板 ⇒ ⇒ ⇒ 向导卡住 ⇒ ⇒ ⇒ 运维需先跑 ' +
            '`uv run python scripts/seed_project_templates.py`（P10-K · W-0）',
        );
      }
    } catch (err: unknown) {
      setTemplates([]);
      setTemplatesError(describePcsError(err, '加载项目模板失败'));
    }
  }, []);

  useEffect(() => {
    if (current === 2) void loadTemplates();
  }, [current, loadTemplates]);

  /** 第 1 步：建项目（**DRAFT**）。 */
  async function createProject(values: ProjectCreate): Promise<void> {
    setSubmitting(true);
    setErrorMsg(null);
    try {
      const created = await projectsApi.create({
        ...values,
        // ⚠️ **向导建的项目一律 DRAFT**（人裁 2026-11-25）⇒ ⇒ ⇒ 第 4 步才转
        // ACTIVE ⇒ ⇒ ⇒ 中途失败的项目**可被识别为弃单**。
        status: 'DRAFT',
      });
      setProjectId(created.project_id);
      setProjectNo(created.project_no);
      // ⚠️ **store 的候选列表要刷新**（P10-K · W-16）⇒ ⇒ ⇒ 否则刚建的项目
      // **不出现在顶栏** ⇒ ⇒ ⇒ 「去项目」没有明确目标。
      await useProjectScopeStore.getState().refresh();
      setCurrent(1);
    } catch (err: unknown) {
      setErrorMsg(describePcsError(err, '建项目失败'));
    } finally {
      setSubmitting(false);
    }
  }

  /** 第 2 步：加项目人员。 */
  async function grantPerson(): Promise<void> {
    if (!projectId) return;
    setSubmitting(true);
    setErrorMsg(null);
    try {
      await userProjectsApi.grant({
        user_id: grantUserId.trim(),
        project_id: projectId,
        role_in_project: grantRole,
      });
      setPartial(null);
      setCurrent(2);
    } catch (err: unknown) {
      setErrorMsg(describePcsError(err, '加项目人员失败'));
      setPartial(
        `项目已创建（编号 ${projectNo}），但「项目人员」未完成 ⇒ ⇒ ⇒ ` +
          '项目保留在 DRAFT ⇒ ⇒ ⇒ 可「去项目页加人员」或「留在本页重试」。',
      );
    } finally {
      setSubmitting(false);
    }
  }

  /** 第 3 步：应用模板（**必选**）。 */
  async function applyTemplate(): Promise<void> {
    if (!projectId || !templateId) return;
    setSubmitting(true);
    setErrorMsg(null);
    try {
      await projectTemplatesApi.apply(projectId, templateId);
      setPartial(null);
      setCurrent(3);
    } catch (err: unknown) {
      setErrorMsg(describePcsError(err, '应用模板失败'));
      setPartial(
        `项目已创建（编号 ${projectNo}），但「选模板」未完成 ⇒ ⇒ ⇒ ` +
          '项目保留在 DRAFT ⇒ ⇒ ⇒ 可「去项目页配置模板」或「留在本页重试」。',
      );
    } finally {
      setSubmitting(false);
    }
  }

  /** 第 4 步：激活 + 去录 BEDD。 */
  async function activate(): Promise<void> {
    if (!projectId) return;
    setSubmitting(true);
    setErrorMsg(null);
    try {
      await projectsApi.setStatus(projectId, 'ACTIVE');
      await useProjectScopeStore.getState().refresh();
      // ⚠️ **「去项目录 BEDD」要有明确目标** ⇒ ⇒ ⇒ 先切当前项目 ⇒ ⇒ ⇒ 再跳。
      useProjectScopeStore.getState().selectProject(projectId);
      msg.success('项目已激活');
      navigate('/bedd');
    } catch (err: unknown) {
      setErrorMsg(describePcsError(err, '激活项目失败'));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div data-testid="project-wizard-page">
      <PageHeader
        title="新建项目向导"
        module="CONFIG"
        actions={null as unknown as undefined}
      />

      <Card size="small" style={{ marginBottom: 16 }}>
        <Steps
          data-testid="wizard-steps"
          current={current}
          items={STEPS.map((s) => ({ title: s.title, description: s.description }))}
        />
      </Card>

      {errorMsg ? (
        <Alert
          type="error"
          showIcon
          message={errorMsg}
          data-testid="wizard-error"
          style={{ marginBottom: 16 }}
        />
      ) : null}
      {partial ? (
        <Alert
          type="warning"
          showIcon
          message="向导未走完"
          description={partial}
          data-testid="wizard-partial"
          style={{ marginBottom: 16 }}
          action={
            <Space>
              <Button
                size="small"
                data-testid="wizard-goto-project"
                onClick={() => navigate('/pms')}
              >
                去项目页继续
              </Button>
              <Button size="small" data-testid="wizard-retry" onClick={() => setErrorMsg(null)}>
                留在本页重试
              </Button>
            </Space>
          }
        />
      ) : null}

      <Card title={`步骤 ${current + 1} / ${STEPS.length} · ${STEPS[current].title}`} size="small">
        {current === 0 ? (
          <ProjectCreateForm
            form={form}
            submitting={submitting}
            hiddenValues={{ status: 'DRAFT' }}
            onFinish={(v) => void createProject(v)}
          />
        ) : null}

        {current === 1 ? (
          <Space direction="vertical" size={12} style={{ width: '100%' }}>
            <Typography.Text type="secondary">
              项目 <b>{projectNo}</b> 已创建（状态 DRAFT）⇒ ⇒ ⇒ 现在给它加人。
            </Typography.Text>
            <Input
              data-testid="wizard-grant-user-id"
              placeholder="目标用户 UUID"
              value={grantUserId}
              onChange={(e) => setGrantUserId(e.target.value)}
            />
            <Select
              data-testid="wizard-grant-role"
              value={grantRole}
              onChange={(v: ProjectRole) => setGrantRole(v)}
              options={PROJECT_ROLES.map((r) => ({ value: r.value, label: r.label }))}
              style={{ width: 280 }}
            />
            <Space>
              <Button
                type="primary"
                data-testid="wizard-grant-submit"
                loading={submitting}
                disabled={!grantUserId.trim()}
                onClick={() => void grantPerson()}
              >
                加人员并继续
              </Button>
              <Button data-testid="wizard-skip-people" onClick={() => setCurrent(2)}>
                跳过（稍后在项目页加）
              </Button>
            </Space>
          </Space>
        ) : null}

        {current === 2 ? (
          <Space direction="vertical" size={12} style={{ width: '100%' }}>
            {templatesError ? (
              <Alert
                type="error"
                showIcon
                message={templatesError}
                data-testid="wizard-templates-error"
              />
            ) : null}
            <Select
              data-testid="wizard-template-select"
              placeholder="选一个模板（必选）"
              value={templateId}
              onChange={(v: string) => setTemplateId(v)}
              options={templates.map((t) => ({
                value: t.template_id,
                label: `${t.name}（v${t.version}）· ${t.checklist_item_count} 项清单`,
              }))}
              style={{ width: 420 }}
            />
            <Space>
              <Button
                type="primary"
                data-testid="wizard-apply-template"
                loading={submitting}
                disabled={!templateId}
                onClick={() => void applyTemplate()}
              >
                应用模板并继续
              </Button>
            </Space>
          </Space>
        ) : null}

        {current === 3 ? (
          <Space direction="vertical" size={12} style={{ width: '100%' }}>
            <Descriptions
              size="small"
              column={1}
              bordered
              items={[
                { key: 'no', label: '项目编号', children: projectNo },
                { key: 'id', label: '项目 ID', children: projectId },
                {
                  key: 'tpl',
                  label: '模板',
                  children: templates.find((t) => t.template_id === templateId)?.name ?? '—',
                },
              ]}
            />
            <Typography.Text type="secondary">
              确认 ⇒ ⇒ ⇒ 项目转 <b>ACTIVE</b> ⇒ ⇒ ⇒ 然后去项目录 BEDD
              （BEDD 是项目的基本依据文件 ⇒ ⇒ ⇒ 必须在项目建好后录）。
            </Typography.Text>
            <Space>
              <Button
                type="primary"
                data-testid="wizard-activate"
                loading={submitting}
                onClick={() => void activate()}
              >
                确认并去录 BEDD
              </Button>
            </Space>
          </Space>
        ) : null}
      </Card>

      {msgCtx}
    </div>
  );
}

export default ProjectWizardPage;
