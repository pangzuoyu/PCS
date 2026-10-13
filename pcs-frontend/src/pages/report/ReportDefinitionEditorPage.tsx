/**
 * ReportDefinitionEditorPage — 定义编辑器（b10）。
 *
 * 覆盖：数据源选择、字段树勾选/别名/排序/显隐、过滤条件树、JOIN 选择、存草稿。
 *
 * ## 过滤条件是**树**，不是列表
 *
 * 第一批用「至多一条 EQ」的模型，代价是**打开一份含 AND/OR 分组的定义
 * 一存就把整棵子树抹掉**（TODO-060）。第二批改为递归的 `FilterTreeEditor`，
 * 往返无损 —— 这一点由 `tests/report/definitionBody.test.ts` 的
 * 「round-trips a nested group without losing any node」钉住，
 * 并做过变异验证（退回单条模型 → 该测试转红）。
 *
 * 分批的由来（保留记录）：第一批刻意只做 EQ 单条，为的是把
 * 「202 + task_id + 轮询」这条前后端唯一需要对齐的**时序契约**
 * 提前暴露 —— 它跨 5 个组件，任一环不通，其余 UI 都是空转。
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
import { errorMessage, reportBuilderApi } from '../../api/reportBuilder';
import type { ReportBuilderDatasource } from '../../api/reportBuilder';
import {
  buildBody,
  fieldsAtLevel,
  toFilterTree,
  toRows,
} from './definitionBody';
import type { JoinWhitelistEntry } from './definitionBody';
import { pairKey } from './definitionBody';
import { JoinPicker } from './JoinPicker';
import type { FieldNodeOption, FieldRow, FilterNode } from './definitionBody';
import { FilterTreeEditor } from './FilterTreeEditor';

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
  // 白名单（后端下发）与用户已启用的关联（白名单子集）**分开存**。
  // 合成一个数组的话，取消勾选数据源后残留的那条会留在里面，
  // 而执行引擎会去关联一个根本没被选中的源 → 400。
  const [joinWhitelist, setJoinWhitelist] = useState<JoinWhitelistEntry[]>([]);
  const [activeJoins, setActiveJoins] = useState<string[]>([]);
  const [maxRows, setMaxRows] = useState(10000);
  const [outputFormat, setOutputFormat] = useState('pdf');
  // ⚠️ 用**树**而不是单条。第一批的单条模型读不了 AND/OR 分组，
  // 保存时会把整棵子树抹掉（TODO-060）。
  const [filterTree, setFilterTree] = useState<FilterNode[]>([]);

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
        // ⚠️ 用 `toFilterTree` 而不是「取第一条」—— 后者的模型读不了
        // AND/OR 分组，保存时会把整棵子树抹掉（TODO-060 的成因）。
        setFilterTree(toFilterTree(body.FilterConditions));
        // 白名单随字段树一起下发（b1），**逐字来自注册表** ——
        // 前端不按名称猜关联，猜错的表现是「选得了、跑不了」。
        setJoinWhitelist(ds.joins ?? []);
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

  /** 条件树用的选项 —— 多带 `source`，选字段时能一并定下来源。 */
  const filterFields: FieldNodeOption[] = useMemo(() => {
    const out: FieldNodeOption[] = [];
    for (const ds of sources) {
      for (const f of ds.fields) {
        if (level === 'BASIC' && f.level === 'DETAIL') continue;
        out.push({
          value: f.name, source: ds.key,
          label: `${ds.label} · ${f.label ?? f.name}`,
        });
      }
    }
    return out;
  }, [sources, level]);

  const addRow = () => {
    const first = visibleFields[0];
    if (!first) {
      message.warning('先在右侧选一个数据源');
      return;
    }
    setRows((prev) => [...prev, {
      key: `row-${Date.now()}-${prev.length}`,   // 见 FieldRow.key 的注释
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
      const body = buildBody({
        rows, level, maxRows, outputFormat, filterTree,
        joins: activeJoins
          .map((k) => joinWhitelist.find((j) => pairKey(j.a, j.b) === k))
          .filter((j): j is JoinWhitelistEntry => !!j),
      });
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
            rowKey="key"
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
            <Tooltip title="15 个操作符 + AND/OR 任意嵌套。空值会原样发出去让后端报
              REPORT_FILTER_VALUE_MISSING —— 不会悄悄放行全表。">
              <Tag color="blue">后端 query_engine 契约</Tag>
            </Tooltip>
          }
        >
          <FilterTreeEditor nodes={filterTree} onChange={setFilterTree}
            fields={filterFields} />
          <Typography.Paragraph type="secondary"
            style={{ marginTop: 12, marginBottom: 0 }}>
            ⚠️ 值留空不是「不过滤」—— 后端对空 value 返回
            <strong>报错</strong>（而非全表），避免「忘了填条件」变成全量导出。
            条件组会原样保存，编辑别的字段不会动它。
          </Typography.Paragraph>
        </Card>

        <Card
          title="数据源关联（JOIN）"
          size="small"
          style={{ marginTop: 16 }}
          extra={<Typography.Text type="secondary">
            仅开放后端白名单里的 {joinWhitelist.length} 对（SPEC §1.3 禁止名称模糊 JOIN）
          </Typography.Text>}
        >
          <JoinPicker
            selectedSources={[...new Set(rows.map((r) => r.source))]}
            whitelist={joinWhitelist}
            active={activeJoins}
            onChange={setActiveJoins}
            labelOf={(key) => sources.find((s) => s.key === key)?.label ?? key}
          />
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
