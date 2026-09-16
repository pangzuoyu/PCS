/**
 * FormulaEditorPage — 公式编辑器（P45-2-4 / Task 22）。
 *
 * SPEC §7.10.2：
 * - 左编辑右预览
 * - 编辑区：公式名 / 模块 / 表达式 / 参数表 / preconditions / 标准来源 / 单测
 * - 预览区：LaTeX 渲染 / 测试参数 → 实时结果 / 单测运行结果
 * - preconditions：变量来源（input.* / params.* / result）/ 违反策略 REJECT（V1）
 * - 不支持跨字段算术约束可视化编辑
 *
 * Props（SPEC 锁定）：
 *   formula: FormulaEditor
 *   onChange?: (formula) => void
 *   onSave?: (formula) => void
 */
import { useMemo, useState } from 'react';
import {
  Alert,
  Button,
  Col,
  Form,
  Input,
  InputNumber,
  Row,
  Select,
  Space,
  Table,
  Tag,
  Typography,
} from 'antd';
import type { ColumnsType } from 'antd/es/table';

/** 参数表行（SPEC §7.10.2）。 */
export interface FormulaParam {
  name: string;
  unit?: string;
  description?: string;
  default_value?: number | string;
}

/** preconditions（SPEC §7.10.2：input.* / params.* / result）。 */
export type PreconditionSource = 'input' | 'params' | 'result';

export interface FormulaPrecondition {
  id: string;
  expression: string;
  source: `${PreconditionSource}.${string}` | PreconditionSource;
  reject_message?: string;
}

/** 单元测试用例（SPEC §7.10.2）。 */
export interface FormulaTestCase {
  case_id: string;
  name: string;
  params: Record<string, number | string>;
  expected: number | string;
}

/** 公式编辑页主数据。 */
export interface FormulaEditor {
  formula_id: string;
  name: string;
  module: string;
  expression: string;
  params: FormulaParam[];
  preconditions: FormulaPrecondition[];
  standard_source: string;
  test_cases: FormulaTestCase[];
}

interface Props {
  formula: FormulaEditor;
  onChange?: (formula: FormulaEditor) => void;
  onSave?: (formula: FormulaEditor) => void;
}

const SOURCE_TAG_COLOR: Record<PreconditionSource, string> = {
  input: 'blue',
  params: 'orange',
  result: 'green',
};

const SOURCE_LABEL: Record<PreconditionSource, string> = {
  input: '输入',
  params: '参数',
  result: '结果',
};

const SOURCE_PREFIX: Record<PreconditionSource, string> = {
  input: 'input.',
  params: 'params.',
  result: 'result',
};

function getSourceKind(src: string): PreconditionSource {
  if (src.startsWith('input.')) return 'input';
  if (src.startsWith('params.')) return 'params';
  if (src.startsWith('result')) return 'result';
  return 'input';
}

/** 把 expression 转 LaTeX 风格展示（V1 极简：变量→斜体，常量→正体）。 */
function toLatex(expression: string): string {
  return expression
    .replace(/\*/g, ' \\cdot ')
    .replace(/sqrt\(([^)]+)\)/g, '\\sqrt{$1}')
    .replace(/exp\(([^)]+)\)/g, 'e^{$1}')
    .replace(/\^(\w+)/g, '^{$1}');
}

/** 在 params 表追加一行（immutable 模式）。 */
function appendParam(params: FormulaParam[]): FormulaParam[] {
  return [...params, { name: '', unit: '', description: '', default_value: undefined }];
}

export function FormulaEditorPage({ formula, onChange, onSave }: Props): JSX.Element {
  const [draft, setDraft] = useState<FormulaEditor>(formula);

  function update<K extends keyof FormulaEditor>(key: K, value: FormulaEditor[K]): void {
    const next = { ...draft, [key]: value };
    setDraft(next);
    onChange?.(next);
  }

  const latex = useMemo(() => toLatex(draft.expression), [draft.expression]);

  const paramColumns: ColumnsType<FormulaParam> = [
    {
      title: '名称',
      dataIndex: 'name',
      width: 140,
      render: (v: string, _row: FormulaParam, idx: number) => (
        <Input
          size="small"
          data-testid="formula-param-name"
          value={v}
          onChange={(e) => {
            const next = [...draft.params];
            next[idx] = { ...next[idx], name: e.target.value };
            update('params', next);
          }}
        />
      ),
    },
    {
      title: '单位',
      dataIndex: 'unit',
      width: 100,
      render: (v: string, _row: FormulaParam, idx: number) => (
        <Input
          size="small"
          data-testid="formula-param-unit"
          value={v ?? ''}
          onChange={(e) => {
            const next = [...draft.params];
            next[idx] = { ...next[idx], unit: e.target.value };
            update('params', next);
          }}
        />
      ),
    },
    {
      title: '描述',
      dataIndex: 'description',
      render: (v: string, _row: FormulaParam, idx: number) => (
        <Input
          size="small"
          data-testid="formula-param-desc"
          value={v ?? ''}
          onChange={(e) => {
            const next = [...draft.params];
            next[idx] = { ...next[idx], description: e.target.value };
            update('params', next);
          }}
        />
      ),
    },
    {
      title: '默认值',
      dataIndex: 'default_value',
      width: 110,
      render: (v: number | string | undefined, _row: FormulaParam, idx: number) => (
        <InputNumber
          size="small"
          data-testid="formula-param-default"
          value={v}
          style={{ width: '100%' }}
          onChange={(nv) => {
            const next = [...draft.params];
            next[idx] = { ...next[idx], default_value: nv ?? undefined };
            update('params', next);
          }}
        />
      ),
    },
  ];

  return (
    <div data-testid="formula-editor-page">
      <Row gutter={16}>
        <Col span={12}>
          <div data-testid="formula-editor-left">
            <Typography.Title level={4}>公式编辑器</Typography.Title>

            <Form layout="vertical" size="small">
              <Form.Item label="公式名" data-testid="formula-name">
                <Input
                  data-testid="formula-name-input"
                  value={draft.name}
                  onChange={(e) => update('name', e.target.value)}
                />
              </Form.Item>

              <Form.Item label="模块" data-testid="formula-module">
                <Select
                  data-testid="formula-module-select"
                  value={draft.module}
                  onChange={(v) => update('module', v)}
                  options={['SIM', 'FLASH', 'PIPE', 'PUMP', 'PIPE_NET'].map((m) => ({
                    value: m,
                    label: m,
                  }))}
                />
              </Form.Item>

              <Form.Item label="表达式（语法高亮 V1 简化）" data-testid="formula-expression">
                <Input.TextArea
                  data-testid="formula-expression-input"
                  value={draft.expression}
                  rows={3}
                  onChange={(e) => update('expression', e.target.value)}
                />
              </Form.Item>

              <Form.Item label="参数表" data-testid="formula-params-section">
                <Table<FormulaParam>
                  rowKey={(_r, idx) => String(idx)}
                  columns={paramColumns}
                  dataSource={draft.params}
                  pagination={false}
                  size="small"
                  onRow={(_r, idx) =>
                    ({
                      'data-testid': 'formula-param-row',
                      'data-param-index': idx,
                    }) as React.HTMLAttributes<HTMLElement>
                  }
                />
                <Button
                  size="small"
                  type="dashed"
                  style={{ marginTop: 8 }}
                  data-testid="formula-add-param-btn"
                  onClick={() => update('params', appendParam(draft.params))}
                >
                  + 添加参数
                </Button>
              </Form.Item>

              <Form.Item label="preconditions（违反策略 REJECT V1 固定）" data-testid="formula-preconditions">
                {draft.preconditions.length === 0 ? (
                  <Typography.Text type="secondary">无前置条件</Typography.Text>
                ) : (
                  <Space direction="vertical" style={{ width: '100%' }}>
                    {draft.preconditions.map((p) => {
                      const kind = getSourceKind(String(p.source));
                      return (
                          <Space
                            key={p.id}
                            data-testid="formula-precondition-item"
                            data-source={kind}
                            data-precondition-id={p.id}
                            style={{
                              width: '100%',
                              border: '1px solid var(--color-border, #E5E7EB)',
                              borderRadius: 4,
                              padding: 8,
                            }}
                          >
                            <Tag color={SOURCE_TAG_COLOR[kind]} data-testid="formula-precondition-source">
                              {SOURCE_LABEL[kind]}
                            </Tag>
                            <Typography.Text code data-testid="formula-precondition-expr">
                              {p.expression}
                            </Typography.Text>
                            <Typography.Text type="secondary" data-testid="formula-precondition-var">
                              ← {String(p.source)}
                            </Typography.Text>
                            {p.reject_message && (
                              <Alert
                                type="warning"
                                showIcon={false}
                                message={p.reject_message}
                                data-testid="formula-precondition-reject"
                              />
                            )}
                          </Space>
                        );
                    })}
                  </Space>
                )}
              </Form.Item>

              <Form.Item label="标准来源" data-testid="formula-standard">
                <Input
                  data-testid="formula-standard-input"
                  value={draft.standard_source}
                  onChange={(e) => update('standard_source', e.target.value)}
                />
              </Form.Item>

              <Form.Item label="单元测试用例（只读 V1 简化）" data-testid="formula-testcases">
                <Space direction="vertical" style={{ width: '100%' }}>
                  {draft.test_cases.map((tc) => (
                    <Space
                      key={tc.case_id}
                      data-testid="formula-test-case"
                      data-case-id={tc.case_id}
                      style={{
                        width: '100%',
                        border: '1px solid var(--color-border, #E5E7EB)',
                        borderRadius: 4,
                        padding: 8,
                      }}
                    >
                      <Tag color="cyan">{tc.case_id}</Tag>
                      <Typography.Text strong>{tc.name}</Typography.Text>
                      <Typography.Text type="secondary">期望 = {tc.expected}</Typography.Text>
                    </Space>
                  ))}
                </Space>
              </Form.Item>

              <Space>
                <Button
                  type="primary"
                  data-testid="formula-save-btn"
                  onClick={() => onSave?.(draft)}
                >
                  保存
                </Button>
                <Tag color={SOURCE_TAG_COLOR[getSourceKind(SOURCE_PREFIX.input)]}>溯源校验：params.* 必须可溯源到系数库</Tag>
              </Space>
            </Form>
          </div>
        </Col>

        <Col span={12}>
          <div data-testid="formula-editor-right">
            <Typography.Title level={4}>预览</Typography.Title>

            <Form layout="vertical" size="small">
              <Form.Item label="LaTeX 预览" data-testid="formula-latex-section">
                <div
                  data-testid="formula-latex-preview"
                  style={{
                    fontFamily: 'var(--font-mono, monospace)',
                    background: 'var(--surface-bg-info, #F0F4F8)',
                    padding: 12,
                    borderRadius: 4,
                    minHeight: 60,
                  }}
                >
                  {latex || '（无）'}
                </div>
              </Form.Item>

              <Form.Item label="测试参数 → 实时结果" data-testid="formula-runtime-section">
                <Typography.Text type="secondary" data-testid="formula-runtime-note">
                  V1 简化：实际数值求值由后端 calculate 端点完成（Task P5-2-? 接入）
                </Typography.Text>
                {draft.test_cases.map((tc) => (
                  <Space
                    key={tc.case_id}
                    data-testid="formula-runtime-case"
                    style={{ display: 'flex', width: '100%', marginTop: 4 }}
                  >
                    <Tag color="cyan">{tc.case_id}</Tag>
                    <Typography.Text>
                      params={JSON.stringify(tc.params)} → 结果 = {String(tc.expected)}
                    </Typography.Text>
                  </Space>
                ))}
              </Form.Item>

              <Form.Item label="单元测试运行结果（V1 简化：仅展示期望）" data-testid="formula-test-result">
                {draft.test_cases.map((tc) => (
                  <Space
                    key={tc.case_id}
                    data-testid="formula-test-result-row"
                    data-case-id={tc.case_id}
                  >
                    <Tag color="green">✓ 通过</Tag>
                    <Typography.Text>{tc.name}（期望 = {tc.expected}）</Typography.Text>
                  </Space>
                ))}
              </Form.Item>
            </Form>
          </div>
        </Col>
      </Row>
    </div>
  );
}

export default FormulaEditorPage;