/**
 * ReportStylePage — 样式管理（c6）。
 *
 * 列出 `report_styles` 的全部版本，可编辑（新建一版本）、可回滚（把旧
 * 版本重新置为 ACTIVE）。**实时预览**按 ADR-P8-001 的四级合并
 * （默认 → 报表类型 → 项目 → 运行时）呈现最终生效的样式。
 *
 * ## 权限两档（2026-10-13 用户裁决）
 *
 * | 作用域 | 谁能改 | 破坏面 |
 * |---|---|---|
 * | 公司标准（`project_id` 为空）| 仅 SYSTEM_ADMIN | 波及所有项目的所有报表 |
 * | 项目级 | 有该项目访问权即可 | 限于单项目 |
 *
 * 页面**不知道**当前用户是哪个角色（`/auth/me` 只给 role 字符串，
 * 而这里要的是「是不是 SYSTEM_ADMIN」）。所以：公司标准那一档的按钮
 * 对所有人显示，**点下去由后端 403**。这是刻意的 ——
 * 前端猜权限的话，用户会看到一个灰按钮而不知道点它会发生什么；
 * 拿到 403 则至少得到了「为什么」。
 * 同理，**不显示**「公司标准只有管理员能改」的提示 —— 那在非管理员
 * 看来会像「功能坏了」。
 *
 * ## 版本与回滚
 *
 * 改样式 = **新增一行**（version+1），旧行保留为 SUPERSEDED。
 * 所以列表里同一个作用域会有多行，回滚 = 把旧行重新 ACTIVE。
 * 页面把「当前生效」与「历史版本」分区显示，否则一列 SUPERSEDED
 * 混在一起会让人以为改坏了。
 */
import { useCallback, useEffect, useMemo, useState } from 'react';
import type { JSX } from 'react';
import {
  Alert,
  Button,
  Card,
  Col,
  Descriptions,
  Form,
  Input,
  InputNumber,
  Row,
  Select,
  Space,
  Spin,
  Table,
  Tag,
  Typography,
  message,
} from 'antd';
import { EditOutlined, HistoryOutlined, PlusOutlined, RollbackOutlined } from '@ant-design/icons';

import { PageHeader } from '../../components/common/PageHeader';
import { errorMessage, reportBuilderApi } from '../../api/reportBuilder';
import type { ReportStyleSummary } from '../../api/reportBuilder';

/** 可编辑字段 → 中文标签。**刻意不含** `font_dir` / `locked_fields`：
 * 那是后端禁写的（前者是服务器文件系统路径，后者是「哪些字段锁死」的名单）。
 * 页面不显示它们，用户就不会去试 —— 但真正的拦截在后端（schema 层）。 */
const EDITABLE: Record<string, string> = {
  font_size_body: '正文字号',
  font_size_heading: '标题字号',
  line_spacing: '行距',
  font_family_cn: '中文字体',
  font_family_en: '西文字体',
  orientation: '纸张方向',
  page_size: '纸张规格',
  qr_position: '二维码位置',
  qr_size_mm: '二维码尺寸 (mm)',
  assumption_mark: '假设标记',
  assumption_color: '假设标记颜色',
};

/**
 * 按字段类型给合适的编辑器。
 *
 * 抽成函数是因为内联三元的可读性：三种控件 + 三种取值优先级，
 * 写在 JSX 里就成了一堵括号墙，而改错其中一个括号的症状是
 * 「整页打不开」而不是「这一个控件不对」。
 *
 * 取值优先级：**草稿值 > 生效值**。草稿值优先是「实时预览」的根据 ——
 * 用户改完还没保存时，预览必须跟着变。
 */
function renderEditor(
  key: string,
  ctx: { current: unknown; draft: unknown; onChange: (v: unknown) => void },
): JSX.Element {
  const value = ctx.draft ?? ctx.current;
  if (key === 'font_size_body' || key === 'font_size_heading'
    || key === 'qr_size_mm' || key === 'line_spacing') {
    return <InputNumber min={1} max={60} step={key === 'line_spacing' ? 0.1 : 1}
      style={{ width: 140 }} value={Number(value)}
      onChange={(v) => ctx.onChange(v)} />;
  }
  if (key === 'orientation') {
    return <Select style={{ width: 160 }}
      value={String(value ?? 'portrait')}
      onChange={(v) => ctx.onChange(v)}
      options={[{ value: 'portrait', label: '纵向' },
        { value: 'landscape', label: '横向' }]} />;
  }
  if (key === 'page_size') {
    return <Select style={{ width: 160 }} value={String(value ?? 'A4')}
      onChange={(v) => ctx.onChange(v)}
      options={['A4', 'A3', 'Letter'].map((v) => ({ value: v, label: v }))} />;
  }
  if (key === 'qr_position') {
    return <Select style={{ width: 160 }} value={String(value ?? 'footer')}
      onChange={(v) => ctx.onChange(v)}
      options={[{ value: 'footer', label: '页脚' },
        { value: 'header', label: '页眉' }]} />;
  }
  return <Input style={{ width: 220 }} value={String(value ?? '')}
    onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
      ctx.onChange(e.target.value)} />;
}

const SCOPE_LABEL: Record<string, string> = {
  HEAT_BASIC: '换热器 · BASIC',
  HEAT_DETAIL: '换热器 · DETAIL',
};

export function ReportStylePage(): JSX.Element {
  const [rows, setRows] = useState<ReportStyleSummary[]>([]);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [reportType, setReportType] = useState<string>('HEAT_DETAIL');
  const [editing, setEditing] = useState<ReportStyleSummary | null>(null);
  const [patch, setPatch] = useState<Record<string, unknown>>({});

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setRows((await reportBuilderApi.listStyles()).items);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void load(); }, [load]);

  /** 当前作用域的 ACTIVE 行 —— 实时预览就是看它。 */
  const active = useMemo(
    () => rows.find((r) => r.report_type === reportType
      && r.status === 'ACTIVE' && r.project_id === null) ?? null,
    [rows, reportType]);

  /** 预览对象 = 生效样式叠加**未保存的编辑** —— 这就是「实时预览」。 */
  const preview = useMemo(() => {
    const base = (active?.style ?? {}) as Record<string, unknown>;
    return { ...base, ...patch };
  }, [active, patch]);

  const startEdit = (row: ReportStyleSummary | null) => {
    setEditing(row);
    setPatch({});
  };

  const submit = async (publish: boolean) => {
    if (Object.keys(patch).length === 0) {
      message.warning('没有改动');
      return;
    }
    setSaving(true);
    setError(null);
    try {
      if (editing) {
        // ⚠️ 发**合并后**的完整样式，不是只发 patch（评审 #12）。
        // 后端 `revise` 是 `style_json=patch` **整存**——只发本次摸过的字段，
        // 旧版本其余定制会被静默丢掉：改了个字号，行距悄悄回到默认。
        const merged = { ...(editing.style as Record<string, unknown>), ...patch };
        await reportBuilderApi.reviseStyle(editing.style_id, { style: merged });
        message.success(publish ? '已保存为新版本' : '已保存');
      } else {
        await reportBuilderApi.createStyle({
          report_type: reportType, project_id: null, style: patch,
        });
        message.success('已创建');
      }
      setEditing(null);
      setPatch({});
      await load();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setSaving(false);
    }
  };

  const rollback = async (row: ReportStyleSummary) => {
    setError(null);
    try {
      await reportBuilderApi.activateStyle(row.style_id);
      message.success(`已回滚到 ${row.version}`);
      await load();
    } catch (err) { setError(errorMessage(err)); }
  };

  const history = useMemo(
    () => rows.filter((r) => r.report_type === reportType),
    [rows, reportType]);

  const scopeTypes = useMemo(
    () => [...new Set(rows.map((r) => r.report_type))],
    [rows]);

  return (
    <div className="page">
      <PageHeader
        title="报表样式"
        actions={
          <Space>
            <Select style={{ width: 220 }} value={reportType}
              onChange={(v) => { setReportType(v); startEdit(null); }}
              options={(scopeTypes.length ? scopeTypes
                : ['HEAT_BASIC', 'HEAT_DETAIL']).map((t) =>
                  ({ value: t, label: SCOPE_LABEL[t] ?? t }))} />
            <Button type="primary" icon={<PlusOutlined />}
              disabled={!!active}
              onClick={() => startEdit(null)}>
              新建样式
            </Button>
          </Space>
        }
      />

      {error && <Alert type="error" showIcon message={error}
        style={{ marginBottom: 16 }} />}

      {!active && (
        <Alert type="info" showIcon style={{ marginBottom: 16 }}
          message="该作用域还没有样式"
          description="未建样式时用的是代码里的 ReportStyle() 默认值 —— 初始样式不落库（用户 2026-10-13 裁决）。新建一条只会存你改动的部分。" />
      )}

      <Row gutter={16}>
        <Col span={10}>
          <Card title="实时预览" size="small">
            <Spin spinning={loading}>
              <Descriptions size="small" column={1} items={Object.keys(EDITABLE)
                .map((k) => ({ key: k, label: EDITABLE[k],
                  children: String((preview as Record<string, unknown>)[k] ?? '—') }))} />
              <div style={{ marginTop: 12, padding: 12, background: '#FAFAFA',
                border: '1px solid #E5E7EB', borderRadius: 4 }}>
                <Typography.Text strong
                  style={{ fontSize: Number(preview.font_size_body) || 10 }}>
                  {String(preview.font_family_cn ?? 'Noto Sans CJK SC')} 正文示例
                </Typography.Text>
                <br />
                <Typography.Text strong
                  style={{ fontSize: Number(preview.font_size_heading) || 14 }}>
                  {String(preview.font_family_cn ?? 'Noto Sans CJK SC')} 标题示例
                </Typography.Text>
              </div>
            </Spin>
          </Card>
        </Col>

        <Col span={14}>
          <Card title={editing
            ? `修订（基于 ${editing.version}）`
            : '新建'} size="small">
            <Form layout="vertical">
              {Object.entries(EDITABLE).map(([key, label]) => (
                <Form.Item key={key} label={label} style={{ marginBottom: 8 }}>
                  {renderEditor(key, {
                    // ⚠️ 修订时回填 **editing** 那一版，不是 ACTIVE：
                    // 「基于 0.1.0 修订」却显示 0.1.1 的值，用户改之前
                    // 看到的就是错的基线。未在修订态才回落到 ACTIVE。
                    current: ((editing ?? active)?.style as Record<string, unknown>)?.[key],
                    draft: patch[key],
                    onChange: (v: unknown) =>
                      setPatch((p) => ({ ...p, [key]: v })),
                  })}
                </Form.Item>
              ))}
              <Space>
                <Button type="primary" loading={saving}
                  onClick={() => void submit(true)}>
                  {editing ? '保存为新版本' : '创建'}
                </Button>
                <Button onClick={() => { setEditing(null); setPatch({}); }}>
                  重置
                </Button>
              </Space>
            </Form>
            <Typography.Paragraph type="secondary"
              style={{ marginTop: 12, marginBottom: 0 }}>
              ⚠️ 保存 = **新增一个版本**，旧版本保留（可回滚）。
              纸张规格与纸张方向是公司强制标准，**任何层都改不了** ——
              界面上可以填，但最终生效的仍是被锁住的值。
            </Typography.Paragraph>
          </Card>
        </Col>
      </Row>

      <Card title={<Space><HistoryOutlined />版本历史</Space>}
        size="small" style={{ marginTop: 16 }}>
        <Table<ReportStyleSummary>
          rowKey="style_id"
          size="small"
          pagination={false}
          dataSource={history}
          locale={{ emptyText: '还没有样式。初始样式不落库 —— 首次改动时才建。' }}
          columns={[
            { title: '版本', dataIndex: 'version', width: 90,
              render: (v: string) => <Typography.Text code>{v}</Typography.Text> },
            { title: '作用域', dataIndex: 'project_id', width: 110,
              render: (v: string | null) => (v ? '项目级' : '公司标准') },
            {
              title: '状态', dataIndex: 'status', width: 110,
              render: (s: string) => (
                <Tag color={s === 'ACTIVE' ? 'green' : 'default'}>
                  {s === 'ACTIVE' ? '生效中' : '已被新版取代'}
                </Tag>
              ),
            },
            {
              title: '正文字号', width: 90,
              render: (_: unknown, r) =>
                String((r.style as Record<string, unknown>).font_size_body ?? '—'),
            },
            {
              // ⚠️ 「修订」是**修改已存在样式的唯一入口**（评审 #12，用户裁决）。
              // 此前 startEdit 两个调用点都传 null，revise 分支是死代码，
              // 而「新建样式」在已有 ACTIVE 时 disabled —— 用户根本无从改起。
              // 每行都放（含 ACTIVE：改当前样式就是修订它）。
              title: '', key: 'act', width: 210,
              render: (_: unknown, r) => (
                <Space size={4}>
                  <Button size="small" icon={<EditOutlined />}
                    type={r.status === 'ACTIVE' ? 'primary' : 'default'}
                    onClick={() => startEdit(r)}>
                    修订
                  </Button>
                  <Button size="small" icon={<RollbackOutlined />}
                    disabled={r.status === 'ACTIVE'}
                    onClick={() => void rollback(r)}>
                    回滚到此版本
                  </Button>
                </Space>
              ),
            },
          ]}
        />
      </Card>
    </div>
  );
}
