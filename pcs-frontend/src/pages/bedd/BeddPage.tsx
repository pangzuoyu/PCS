/**
 * BeddPage — BEDD 文档（P10-H · T2 · TODO-195 · SPEC §7.5）。
 *
 * ## 数据源与形状
 *
 * - 文档：`GET /projects/{project_id}/bedd`（**真端点** ⇒ ⇒ 有写入路径了）
 * - 表单：`GET /meta/ui-schema/bedd`（**分组 Tab 编辑** ⇒ ⇒ SPEC §7.5）
 *
 * ⚠️ **此前本页是占位**（P10-C · T2 · TODO-159）：调的端点**契约里没有**
 * ⇒ ⇒ 真后端 404 ⇒ ⇒ mock 通道一路绿灯。
 *
 * ## 为什么是「9 个分组」而不是「章节列表」
 *
 * 前端原先画的是**章节 + 签名**（P45-3-8 自创）⇒ ⇒ 与 SPEC §7.5
 * **不是同一件事**（TODO-195 已记）⇒ ⇒ 人裁（2026-11-23）：**按 SPEC**
 * ⇒ ⇒ 本页改成**分组 Tab**（uiSchema 的字段路径前缀 = 分组）。
 */
import { useCallback, useEffect, useMemo, useState } from 'react';
import { Alert, Button, Spin, Tabs, message } from 'antd';

import { PageHeader } from '../../components/common/PageHeader';
import { SchemaForm, type UiSchemaField } from '../../components/common/SchemaForm';
import { beddApi, type BeddDocument } from '../../api/pms';
import { metaApi } from '../../api/meta';
import { useProjectScope } from '../../hooks/useProjectScope';
import { projectsApi } from '../../api/projects';
import { UnitSystemSwitch } from './UnitSystemSwitch';
import type { UnitSystem } from '../../utils/units';

/** 分组 key → 中文 Tab 名（与后端 `BEDD_GROUP_LABELS` 一致 ⇒ ⇒ 顺序也一致）。 */
const GROUP_LABELS: Record<string, string> = {
  meteorology: '气象',
  hydrology_geology: '水文地质',
  seismic: '地震',
  utilities: '公用工程',
  emission_limits: '排放限值',
  design_criteria: '设计准则',
  safety_fire: '安全消防',
  flare: '火炬',
  interface_conditions: '界面条件',
};

export function BeddPage(): JSX.Element {
  const { projectId, loading: scopeLoading, error: scopeError } = useProjectScope();
  const [fields, setFields] = useState<UiSchemaField[]>([]);
  /** 分组 key → {字段 key: 值} */
  const [doc, setDoc] = useState<Record<string, Record<string, unknown>>>({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [msg, msgCtx] = message.useMessage();
  // ⚠️ **单位制**（P10-K · W-4）—— 默认取**项目的默认显示单位制**
  // ⇒ ⇒ ⇒ 切换 = **页面临时覆盖**（不写项目）⇒ ⇒ ⇒ 改默认去项目页。
  const [projectUnitSystem, setProjectUnitSystem] = useState<UnitSystem>('SI');
  const [unitSystem, setUnitSystem] = useState<UnitSystem>('SI');

  const reload = useCallback(async () => {
    if (!projectId) return;
    setLoading(true);
    setError(null);
    try {
      const [schema, res, project] = await Promise.all([
        metaApi.uiSchema('bedd'),
        beddApi.get(projectId),
        // ⚠️ **项目默认单位制**（`ProjectOut.unit_system`）⇒ ⇒ ⇒ 缺它 ⇒ ⇒ ⇒
        //   单位制下拉就只能恒为 SI ⇒ ⇒ ⇒ ⇒ 与 SPEC §7.5「默认取项目值」不符。
        //   ⇒ ⇒ ⇒ 拉失败**不阻断**（老后端没有这个字段）⇒ ⇒ ⇒ 退回 SI。
        projectsApi.get(projectId).catch(() => null),
      ]);
      if (project?.unit_system) {
        setProjectUnitSystem(project.unit_system);
        setUnitSystem(project.unit_system);
      }
      setFields(schema.fields ?? []);
      const document = (res.document ?? {}) as Record<string, unknown>;
      const next: Record<string, Record<string, unknown>> = {};
      for (const [group, values] of Object.entries(document)) {
        if (values && typeof values === 'object') {
          next[group] = { ...(values as Record<string, unknown>) };
        }
      }
      setDoc(next);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'BEDD 文档加载失败');
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  useEffect(() => {
    void reload();
  }, [reload]);

  /** 按分组切 uiSchema 字段（路径前缀 = 分组）⇒ ⇒ 一个分组一个 Tab。 */
  const groups = useMemo(() => {
    const byGroup = new Map<string, UiSchemaField[]>();
    for (const field of fields) {
      const [group, ...rest] = field.path.split('.');
      if (rest.length === 0) continue;
      const bare: UiSchemaField = { ...field, path: rest.join('.') };
      byGroup.set(group, [...(byGroup.get(group) ?? []), bare]);
    }
    return [...byGroup.entries()];
  }, [fields]);

  async function handleSave(): Promise<void> {
    if (!projectId) return;
    setSaving(true);
    try {
      const payload: Record<string, unknown> = {};
      for (const [group, values] of Object.entries(doc)) {
        const cleaned = Object.fromEntries(
          Object.entries(values).filter(([, v]) => v !== null && v !== undefined && v !== ''),
        );
        if (Object.keys(cleaned).length > 0) payload[group] = cleaned;
      }
      await beddApi.put(projectId, payload as BeddDocument);
      msg.success('已保存 BEDD 文档');
      await reload();
    } catch (err) {
      msg.error(err instanceof Error ? err.message : '保存失败');
    } finally {
      setSaving(false);
    }
  }

  if (scopeError) {
    return (
      <div data-testid="bedd-page">
        <PageHeader title="BEDD 文档" module="CONFIG" actions={null as unknown as undefined} />
        <Alert
          type="warning"
          showIcon
          data-testid="bedd-scope-error"
          message="没有可用的项目作用域"
          description={scopeError}
        />
      </div>
    );
  }

  return (
    <div data-testid="bedd-page">
      <PageHeader
        title="BEDD 文档"
        module="CONFIG"
        actions={
          <Button
            type="primary"
            data-testid="bedd-save"
            loading={saving}
            disabled={!projectId || scopeLoading}
            onClick={() => void handleSave()}
          >
            保存
          </Button>
        }
      />

      {error ? (
        <Alert
          type="error"
          showIcon
          style={{ marginBottom: 16 }}
          data-testid="bedd-error"
          message="BEDD 文档加载失败"
          description={error}
        />
      ) : null}

      <div style={{ marginBottom: 12 }}>
        <UnitSystemSwitch
          value={unitSystem}
          onChange={setUnitSystem}
          projectDefault={projectUnitSystem}
          fields={fields}
        />
      </div>

      <Spin spinning={loading}>
        <Tabs
          data-testid="bedd-tabs"
          items={groups.map(([group, groupFields]) => ({
            key: group,
            label: GROUP_LABELS[group] ?? group,
            children: (
              <SchemaForm
                schema={{
                  schema_version: '1.0.0',
                  resource: `bedd.${group}`,
                  fields: groupFields,
                }}
                value={doc[group] ?? {}}
                unitSystem={unitSystem}
                onChange={(values) =>
                  setDoc((prev) => ({ ...prev, [group]: values }))
                }
              />
            ),
          }))}
        />
      </Spin>

      {msgCtx}
    </div>
  );
}

export default BeddPage;
