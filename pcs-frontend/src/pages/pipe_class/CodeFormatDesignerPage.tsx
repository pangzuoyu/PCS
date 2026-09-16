/**
 * CodeFormatDesignerPage — 代码格式设计器（P45-3-2 / Task 29）。
 *
 * SPEC §7.9.4：
 * - 段（segment）数组：决定管道号拼接规则
 * - 每段：field + 可选 value + 可选 separator
 * - 实时预览生成的 tag_number 样例
 *
 * Props：
 *   segments: CodeFormatSegment[]
 *   sample: { material?: string; schedule?: string; size?: string; service?: string; insulation?: string; custom?: string }
 *   onChange?: (segments: CodeFormatSegment[]) => void
 *
 * 注：V1 极简版段顺序由上下移动按钮实现（避免引入 react-dnd 依赖）；
 * V1.1 计划升级为 react-dnd。
 */
import { Button, Card, Input, List, Space, Tag, Typography } from 'antd';
import { ArrowDownOutlined, ArrowUpOutlined, DeleteOutlined, PlusOutlined } from '@ant-design/icons';

import type { CodeFormatSegment, CodeSegmentField } from '../../types/pipeClass';

interface Props {
  segments: CodeFormatSegment[];
  sample?: Partial<Record<string, string>>;
  onChange?: (segments: CodeFormatSegment[]) => void;
}

const FIELD_LABEL: Record<CodeSegmentField, string> = {
  material: '材料',
  schedule: '等级',
  size: '尺寸',
  service: '介质',
  insulation: '保温',
  custom: '自定义',
};

function updateSegment(
  segments: CodeFormatSegment[],
  idx: number,
  patch: Partial<CodeFormatSegment>,
): CodeFormatSegment[] {
  return segments.map((s, i) => (i === idx ? { ...s, ...patch } : s));
}

function removeSegment(segments: CodeFormatSegment[], idx: number): CodeFormatSegment[] {
  return segments.filter((_, i) => i !== idx);
}

function moveSegment(
  segments: CodeFormatSegment[],
  idx: number,
  dir: -1 | 1,
): CodeFormatSegment[] {
  const target = idx + dir;
  if (target < 0 || target >= segments.length) return segments;
  const copy = [...segments];
  [copy[idx], copy[target]] = [copy[target], copy[idx]];
  return copy.map((s, i) => ({ ...s, order: i }));
}

function addSegment(segments: CodeFormatSegment[]): CodeFormatSegment[] {
  const order = segments.length;
  return [...segments, { order, field: 'material', separator: '-' }];
}

function previewTagNumber(segments: CodeFormatSegment[], sample: Props['sample'] = {}): string {
  return segments
    .map((s) => {
      const value = sample[s.field] ?? s.value ?? '';
      return `${s.separator ?? ''}${value}`;
    })
    .join('');
}

export function CodeFormatDesignerPage({ segments, sample, onChange }: Props): JSX.Element {
  const preview = previewTagNumber(segments, sample);

  return (
    <div data-testid="code-format-designer-page">
      <Typography.Title level={3}>代码格式设计器</Typography.Title>

      <Card title="段序列" size="small" style={{ marginBottom: 16 }}>
        {segments.length === 0 ? (
          <Typography.Text type="secondary">暂无段，请添加</Typography.Text>
        ) : (
          <List
            data-testid="code-format-segments"
            dataSource={segments.map((s, i) => ({ ...s, idx: i }))}
            renderItem={(item) => (
              <List.Item
                data-testid="code-format-segment-row"
                data-segment-index={item.idx}
                actions={[
                  <Button
                    key="up"
                    size="small"
                    icon={<ArrowUpOutlined />}
                    data-testid="code-format-segment-up"
                    onClick={() => onChange?.(moveSegment(segments, item.idx, -1))}
                  />,
                  <Button
                    key="down"
                    size="small"
                    icon={<ArrowDownOutlined />}
                    data-testid="code-format-segment-down"
                    onClick={() => onChange?.(moveSegment(segments, item.idx, 1))}
                  />,
                  <Button
                    key="del"
                    size="small"
                    danger
                    icon={<DeleteOutlined />}
                    data-testid="code-format-segment-delete"
                    onClick={() => onChange?.(removeSegment(segments, item.idx))}
                  />,
                ]}
              >
                <Space>
                  <Tag color="blue">{FIELD_LABEL[item.field]}</Tag>
                  <Input
                    data-testid="code-format-segment-separator"
                    placeholder="分隔符"
                    style={{ width: 80 }}
                    value={item.separator ?? ''}
                    onChange={(e) =>
                      onChange?.(updateSegment(segments, item.idx, { separator: e.target.value }))
                    }
                  />
                  <Input
                    data-testid="code-format-segment-value"
                    placeholder={item.field === 'custom' ? '自定义值' : '由运行时注入'}
                    style={{ width: 200 }}
                    value={item.value ?? ''}
                    onChange={(e) =>
                      onChange?.(updateSegment(segments, item.idx, { value: e.target.value }))
                    }
                  />
                </Space>
              </List.Item>
            )}
          />
        )}

        <Button
          type="dashed"
          icon={<PlusOutlined />}
          data-testid="code-format-segment-add"
          style={{ marginTop: 12 }}
          onClick={() => onChange?.(addSegment(segments))}
        >
          添加段
        </Button>
      </Card>

      <Card title="实时预览" size="small">
        <Typography.Text
          data-testid="code-format-preview"
          style={{ fontFamily: 'var(--font-mono, monospace)', fontSize: 16 }}
        >
          {preview || '（空）'}
        </Typography.Text>
      </Card>
    </div>
  );
}

export default CodeFormatDesignerPage;