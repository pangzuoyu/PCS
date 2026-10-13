/**
 * ReportDefinitionEditorPage — 定义编辑器（b10）。
 *
 * 覆盖：数据源选择、字段树勾选/别名/排序/显隐、**一条 EQ 过滤条件**、保存草稿。
 *
 * ## ⚠️ 过滤只做一条 EQ —— 这是有意的分批，不是没做完
 *
 * 用户 2026-10-13 裁决：第一批只做 **EQ 单条**（不嵌套），
 * 第二批才做 15 操作符全集、AND/OR 嵌套、5 对 JOIN 白名单、临时调整。
 *
 * 理由是把「202 + task_id + 轮询」这条**前后端唯一需要对齐的时序契约**
 * 提前暴露 —— 它跨 5 个组件，任一环不通，其余 UI 都是空转。
 * 过滤不能完全不做是因为：全表执行验证不了「条件 → 后端解析 → 结果集变化」
 * 这条核心契约，EQ 已足够走通 条件序列化 → 传输 → b5 解析 → query_engine
 * 编译 → 结果集变化。
 *
 * **看到只有一个操作符、不能嵌套、不能加第二条 —— 是分批标记。
 *  第二批要做的事都列在 `api/reportBuilder.ts` 的 `OPERATORS_BATCH_1` 旁。**
 *
 * ## 字段树的 level 分组不是过滤，是提示
 *
 * `GET /datasources` 按 `detailLevel` 组织字段。BASIC 下 DETAIL 字段
 * 仍然会返回（只是被标记），因为后端在保存时会再核一次
 * （`validate_definition`），页面提前拦一道只是为了少一次往返。
 * ⚠️ 真正的强制在后端 —— 页面这层拦是**体验**，不是安全边界。
 */
import { useCallback, useEffect, useMemo, useState } from 'react';
import type { JSX } from 'react';
import {
  Alert,
  Button,
  Card,
  Form,
  Input,
  InputNumber,
  Select,
  Space,
  Spin,
  Switch,
  Table,
  Tag,
  Tooltip,
  Typography,
  message,
} from 'antd';
import { ArrowLeftOutlined, SaveOutlined, SendOutlined } from '@ant-design/icons';
import { useNavigate, useParams } from 'react-router-dom';

import { PageHeader } from '../../components/common/PageHeader';
import {
  OPERATORS_BATCH_1,
  errorMessage,
  reportBuilderApi,
} from '../../api/reportBuilder';
import type { ReportBuilderDatasource } from '../../api/reportBuilder';
import {
  asSingleFilter,
  buildBody,
  fieldsAtLevel,
  toRows,
} from './definitionBody';
import type { FieldRow, SingleFilter } from './definitionBody';

const DETAIL_LEVELS = [
  { value: 'BASIC', label: 'BASIC（基本项）' },
  { value: 'DETAIL', label: 'DETAIL（含几何/热阻明细）' },
] as const;

const OUTPUT_FORMATS = [
  { value: 'pdf', label: 'PDF' },
  { value: 'xlsx', label: 'Excel' },
  { value: 'docx', label: 'Word' },
  { value: 'csv', label: 'CSV' },
] as const;

export function ReportDefinitionEditorPage(): JSX.Element {
  const { defId } = useParams<{ defId: string }>();
  const navigate = useNavigate();
  const isNew = !defId || defId === 'new';

  const [sources, setSources] = useState<ReportBuilderDatasource[]>([]);
  const [meta, setMeta] = useState<{ name: string; category: string;
    description: string; sharedWith: string;
    projectId: string | null; status: string } | null>(null);
  const [rows, setRows] = useState<FieldRow[]>([]);
  const [level, setLevel] = useState<string>('BASIC');
  const [maxRows, setMaxRows] = useState(10000);
  const [outputFormat, setOutputFormat] = useState('pdf');
  // ⚠️ 第一批固定存**至多一条** EQ 条件。null = 无过滤。
  const [filter, setFilter] = useState<SingleFilter | null>(null);

  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const ds = await reportBuilderApi.datasources();
      setSources(ds.datasources);
      if (!isNew) {
        const d = await reportBuilderApi.get(defId);
        setMeta({
          name: d.name, category: d.category, description: d.description,
          sharedWith: d.shared_with, projectId: d.project_id, status: d.status,
        });
        const body = d.definition_json;
        setLevel(body.detailLevel);
        setMaxRows(d.max_rows);
        setOutputFormat(d.output_format);
        setRows(toRows(body, ds.datasources));
        const first = body.FilterConditions?.[0];
        const c = asSingleFilter(first);
        if (c) setFilter(c);
      }
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setLoading(false);
    }
  }, [defId, isNew]);

  useEffect(() => { void load(); }, [load]);

  /** 当前级别可见的字段（BASIC 看不到 DETAIL 字段）。 */
  const visibleFields = useMemo(
    () => fieldsAtLevel(sources, level), [sources, level]);

  const fieldOptions = useMemo(() => visibleFields.map((f) => ({
    value: f.name,
    label: `${f.name}${f.label && f.label !== f.name ? `（${f.label}）` : ''}`,
  })), [visibleFields]);

  const addRow = () => {
    const first = visibleFields[0];
    if (!first) {
      message.warning('先在右侧选一个数据源');
      return;
    }
    setRows((prev) => [...prev, {
      source: 'EQUIP_LIST', field: first.name, label: first.name,
      alias: '', order: prev.length, visible: true, level: first.level ?? null,
    }]);
  };

  const patch = (idx: number, next: Partial<FieldRow>) =>
    setRows((prev) => prev.map((r, i) => (i === idx ? { ...r, ...next } : r)));

  const removeRow = (idx: number) =>
    setRows((prev) => prev.filter((_, i) => i !== idx));

  const move = (idx: number, delta: number) =>
    setRows((prev) => {
      const target = idx + delta;
      if (target < 0 || target >= prev.length) return prev;
      const next = [...prev];
      const [item] = next.splice(idx, 1);
      next.splice(target, 0, item);
      return next.map((r, i) => ({ ...r, order: i }));
    });

  const save = async (thenPublish: boolean) => {
    if (!meta?.name?.trim()) {
      message.error('名称必填');
      return;
    }
    setSaving(true);
    setError(null);
    try {
      const body = buildBody({ rows, level, maxRows, outputFormat, filter });
      const payload = {
        project_id: meta.projectId,
        name: meta.name,
        category: meta.category || '未分类',
        description: meta.description,
        output_format: outputFormat,
        max_rows: maxRows,
        shared_with: meta.sharedWith,
        definition_json: body,
      };
      const saved = isNew
        ? await reportBuilderApi.create(payload)
        : await reportBuilderApi.update(defId, payload);
      if (thenPublish) {
        await reportBuilderApi.publish(saved.def_id);
        message.success('已发布');
      } else {
        message.success('草稿已保存');
      }
      navigate('/report/definitions');
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="page">
    <PageHeader
      title={isNew ? '新建报表定义' : `编辑：${meta?.name ?? ''}`}
      actions={
        <Space>
          <Button icon={<ArrowLeftOutlined />}
            onClick={() => navigate('/report/definitions')}>返回</Button>
          <Button icon={<SaveOutlined />} loading={saving}
            onClick={() => void save(false)}>存草稿</Button>
          <Button type="primary" icon={<SendOutlined />} loading={saving}
            onClick={() => void save(true)}>保存并发布</Button>
        </Space>
      }
    />
      <Spin spinning={loading}>
        {error && <Alert type="error" showIcon message={error}
          style={{ marginBottom: 16 }} />}

        <Card title="基本信息" size="small" style={{ marginBottom: 16 }}>
          <Form layout="inline" style={{ rowGap: 12 }}>
            <Form.Item label="名称" required>
              <Input style={{ width: 220 }} value={meta?.name ?? ''}
                onChange={(e) => setMeta((m) => ({ ...(m ?? blankMeta()), name: e.target.value }))} />
            </Form.Item>
            <Form.Item label="分类">
              <Input style={{ width: 160 }} value={meta?.category ?? ''}
                onChange={(e) => setMeta((m) => ({ ...(m ?? blankMeta()), category: e.target.value }))} />
            </Form.Item>
            <Form.Item label="共享范围">
              <Select style={{ width: 140 }} value={meta?.sharedWith ?? 'CREATOR_ONLY'}
                onChange={(v) => setMeta((m) => ({ ...(m ?? blankMeta()), sharedWith: v }))}
                options={[
                  { value: 'CREATOR_ONLY', label: '仅创建人' },
                  { value: 'ALL_USERS', label: '全员可见' },
                ]} />
            </Form.Item>
            <Form.Item label="明细级">
              <Select style={{ width: 260 }} value={level}
                onChange={(v) => {
                  setLevel(v);
                  // 切到 BASIC 时把 DETAIL 字段摘掉 —— 后端保存时会拒绝，
                  // 这里先摘只是少一次往返。
                  if (v === 'BASIC') {
                    setRows((prev) => prev.filter((r) => r.level !== 'DETAIL'));
                  }
                }}
                options={[...DETAIL_LEVELS]} />
            </Form.Item>
            <Form.Item label="最大行数">
              <InputNumber style={{ width: 120 }} min={1} max={100000}
                value={maxRows} onChange={(v) => setMaxRows(v ?? 10000)} />
            </Form.Item>
            <Form.Item label="输出格式">
              <Select style={{ width: 120 }} value={outputFormat}
                onChange={setOutputFormat} options={[...OUTPUT_FORMATS]} />
            </Form.Item>
          </Form>
        </Card>

        <Card
          title="字段"
          size="small"
          style={{ marginBottom: 16 }}
          extra={<Button size="small" onClick={addRow}>加一行</Button>}
        >
          <Table<FieldRow>
            rowKey={(_, i) => String(i)}
            size="small"
            pagination={false}
            dataSource={rows}
            locale={{ emptyText: '还没有选字段。点「加一行」。' }}
            columns={[
              {
                title: '数据源', dataIndex: 'source', width: 160,
                render: (v: string, _r, i) => (
                  <Select style={{ width: 150 }} value={v}
                    onChange={(nv) => patch(i, { source: nv })}
                    options={sources.map((s) => ({ value: s.key, label: s.label }))} />
                ),
              },
              {
                title: '字段', dataIndex: 'field',
                render: (v: string, _row, i) => (
                  <Select showSearch style={{ width: 240 }} value={v}
                    onChange={(nv) => {
                      const f = visibleFields.find((x) => x.name === nv);
                      patch(i, { field: nv, label: f?.label ?? nv,
                        level: f?.level ?? null });
                    }}
                    options={fieldOptions} />
                ),
              },
              {
                title: '显示名', dataIndex: 'alias', width: 180,
                render: (v: string, row, i) => (
                  <Input placeholder={row.label} value={v}
                    onChange={(e) => patch(i, { alias: e.target.value })} />
                ),
              },
              {
                title: '显示', dataIndex: 'visible', width: 70,
                render: (v: boolean, _r, i) => (
                  <Switch size="small" checked={v}
                    onChange={(nv) => patch(i, { visible: nv })} />
                ),
              },
              {
                title: '顺序', width: 110,
                render: (_: unknown, _r, i) => (
                  <Space size={4}>
                    <Button size="small" onClick={() => move(i, -1)}>↑</Button>
                    <Button size="small" onClick={() => move(i, 1)}>↓</Button>
                    <Button size="small" danger onClick={() => removeRow(i)}>删</Button>
                  </Space>
                ),
              },
            ]}
          />
        </Card>

        <Card
          title="过滤条件"
          size="small"
          extra={
            <Tooltip title="第二批补：15 个操作符、AND/OR 嵌套、多条条件、临时调整（不落库）">
              <Tag color="gold">第一批：仅 EQ 单条</Tag>
            </Tooltip>
          }
        >
          {!filter ? (
            <Button size="small" onClick={() => setFilter({
              source: rows[0]?.source ?? 'EQUIP_LIST',
              field: rows[0]?.field ?? 'tag_number',
              operator: 'EQ', value: '',
            })}>加一条过滤条件</Button>
          ) : (
            <Space wrap>
              <Select style={{ width: 200 }} value={filter.field}
                onChange={(v) => setFilter((f) => (f ? { ...f, field: v } : f))}
                options={fieldOptions} />
              <Select style={{ width: 100 }} value={filter.operator}
                onChange={(v) => setFilter((f) => (f ? { ...f, operator: v } : f))}
                options={OPERATORS_BATCH_1.map((o) => ({ value: o, label: o }))} />
              <Input style={{ width: 200 }} placeholder="值（留空将得到空结果集）"
                value={filter.value}
                onChange={(e) => setFilter((f) => (f ? { ...f, value: e.target.value } : f))} />
              <Button size="small" danger onClick={() => setFilter(null)}>删</Button>
            </Space>
          )}
          <Typography.Paragraph type="secondary" style={{ marginTop: 12, marginBottom: 0 }}>
            ⚠️ 值留空不是「不过滤」—— 后端对空 value 返回**空结果集**
            （SPEC §3.2.2(4)，避免「忘了填条件」变成全表导出）。
          </Typography.Paragraph>
        </Card>
      </Spin>
  </div>
  );
}

/** 新建时的空 meta。
 *
 * ⚠️ 必须是**工厂**而不是共享常量：`setMeta(m => ({ ...m ?? blankMeta(), name }))`
 * 若返回同一个对象，多次编辑会串改同一个引用。
 */
function blankMeta() {
  return { name: '', category: '', description: '', sharedWith: 'CREATOR_ONLY',
    projectId: null, status: 'DRAFT' };
}
