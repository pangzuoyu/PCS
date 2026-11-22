/**
 * `ProjectSelector` —— 顶栏的**项目切换**（P10-H · T1 · TODO-194）。
 *
 * ## SPEC 依据
 *
 * `docs/PCS-UI-SPEC.md` §3.2 TopBar：
 * 「**项目切换** | 下拉，显示最近项目 + 搜索」
 *
 * ⇒ ⇒ antd `Select` + `showSearch`（可搜项目名）。
 *
 * ## 为什么在顶栏而不是页面里
 *
 * 项目作用域是**全局**的（管道一览表 / 设备台账 / PMS / BEDD 都按它取数）
 * ⇒ ⇒ 放在顶栏 ⇒ ⇒ 换项目 = 换全局上下文 ⇒ ⇒ 不用每页各选一次。
 *
 * ⚠️ **选不中时**（没有授权项目）⇒ ⇒ 显示**原因**（store 把「没有候选」
 * 也算成 error ⇒ ⇒ 页面与顶栏**说的是同一句话**）⇒ ⇒ **不静默**。
 */
import { Select, Space, Tag, Typography } from 'antd';

import { useProjectScope } from '../../hooks/useProjectScope';

export function ProjectSelector(): JSX.Element {
  const { projects, projectId, loading, error, selectProject } = useProjectScope();

  if (error) {
    return (
      <Typography.Text style={{ color: '#fff' }} data-testid="project-selector-error">
        {error}
      </Typography.Text>
    );
  }

  const current = projects.find((p) => p.projectId === projectId) ?? null;

  return (
    <Space size={8} data-testid="project-selector-wrap">
      <Select
        data-testid="project-selector"
        showSearch
        size="middle"
        loading={loading}
        style={{ minWidth: 220 }}
        placeholder="选择项目"
        value={projectId ?? undefined}
        onChange={(v: string) => selectProject(v)}
        options={projects.map((p) => ({
          value: p.projectId,
          label: p.name,
        }))}
        optionFilterProp="label"
      />
      {current?.roleInProject ? (
        <Tag color="blue" data-testid="project-selector-role">
          {current.roleInProject}
        </Tag>
      ) : null}
    </Space>
  );
}

export default ProjectSelector;
