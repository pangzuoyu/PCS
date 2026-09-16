/**
 * SchemaForm — 通用动态表单（P45-1-14 / Task 19）。
 *
 * SPEC §8 + plan P45-1-14：
 * - 驱动：uiSchema 服务（Task 18.5 Pydantic 侧；前端 metaApi.uiSchema）
 * - 9 widget 类型：Input / Select / NumberInput / TextArea / Switch /
 *   DatePicker / AutoComplete / Cascader / TagPicker
 * - 字段属性：path / label / widget / required / readonly / placeholder /
 *   help / unit / order / min_length / max_length / enum_group / visible / hidden_when
 * - onChange(value) 实时回传（immutable 展开新对象）
 *
 * Props：
 *   schema: UiSchemaResponse
 *   value?: Record<string, unknown>
 *   onChange?: (value: Record<string, unknown>) => void
 *   enumOptions?: Record<string, EnumOption[]>  // 可选外部传入 enum 数据
 *   disabled?: boolean
 */
import { useEffect, useMemo } from 'react';
import {
  AutoComplete,
  Cascader,
  DatePicker,
  Form,
  Input,
  InputNumber,
  Select,
  Switch,
  Tag,
} from 'antd';
import type { FormInstance } from 'antd';

export type WidgetName =
  | 'Input'
  | 'Select'
  | 'NumberInput'
  | 'TextArea'
  | 'Switch'
  | 'DatePicker'
  | 'AutoComplete'
  | 'Cascader'
  | 'TagPicker';

export interface UiSchemaField {
  path: string;
  label: string;
  widget: WidgetName;
  required?: boolean;
  readonly?: boolean;
  placeholder?: string;
  help?: string;
  order?: number;
  unit?: string;
  min_length?: number;
  max_length?: number;
  enum_group?: string;
  visible?: boolean;
  hidden_when?: string;
}

export interface UiSchemaResponse {
  schema_version: string;
  resource: string;
  fields: UiSchemaField[];
}

export interface EnumOption {
  value: string;
  label: string;
}

interface Props {
  schema: UiSchemaResponse;
  value?: Record<string, unknown>;
  onChange?: (value: Record<string, unknown>) => void;
  /** enum_group → options 映射（外部提供） */
  enumOptions?: Record<string, EnumOption[]>;
  disabled?: boolean;
}

/** 过滤 visible=false + 按 order 升序 */
function prepareFields(fields: UiSchemaField[]): UiSchemaField[] {
  return [...fields]
    .filter((f) => f.visible !== false)
    .sort((a, b) => (a.order ?? 0) - (b.order ?? 0));
}

export function SchemaForm({
  schema,
  value,
  onChange,
  enumOptions = {},
  disabled,
}: Props): JSX.Element {
  const [form] = Form.useForm<Record<string, any>>();
  const orderedFields = useMemo(() => prepareFields(schema.fields), [schema]);

  // 同步外部 value → form
  useEffect(() => {
    if (value) form.setFieldsValue(value);
  }, [value, form]);

  function handleValuesChange(_: unknown, allValues: Record<string, unknown>): void {
    onChange?.(allValues);
  }

  function renderControl(field: UiSchemaField): JSX.Element {
    const common = {
      disabled: disabled || field.readonly,
      placeholder: field.placeholder,
    };
    switch (field.widget) {
      case 'Input':
        return (
          <Input
            data-testid={`control-${field.path}`}
            data-widget="Input"
            maxLength={field.max_length}
            {...common}
          />
        );
      case 'TextArea':
        return (
          <Input.TextArea
            data-testid={`control-${field.path}`}
            data-widget="TextArea"
            maxLength={field.max_length}
            rows={3}
            {...common}
          />
        );
      case 'NumberInput':
        return (
          <InputNumber
            data-testid={`control-${field.path}`}
            data-widget="NumberInput"
            data-unit={field.unit ?? ''}
            style={{ width: '100%' }}
            {...common}
          />
        );
      case 'Select': {
        const opts = field.enum_group ? (enumOptions[field.enum_group] ?? []) : [];
        return (
          <Select
            data-testid={`control-${field.path}`}
            data-widget="Select"
            data-enum-group={field.enum_group ?? ''}
            options={opts.map((o) => ({ value: o.value, label: o.label }))}
            {...common}
          />
        );
      }
      case 'Switch':
        return (
          <Switch
            data-testid={`control-${field.path}`}
            data-widget="Switch"
            disabled={common.disabled}
          />
        );
      case 'DatePicker':
        return (
          <DatePicker
            data-testid={`control-${field.path}`}
            data-widget="DatePicker"
            style={{ width: '100%' }}
            {...common}
          />
        );
      case 'AutoComplete':
        return (
          <AutoComplete
            data-testid={`control-${field.path}`}
            data-widget="AutoComplete"
            options={optsForGroup(field, enumOptions)}
            {...common}
          />
        );
      case 'Cascader':
        return (
          <Cascader
            data-testid={`control-${field.path}`}
            data-widget="Cascader"
            options={optsForGroup(field, enumOptions) as { value: string; label: string }[]}
            {...common}
          />
        );
      case 'TagPicker':
        return (
          <Select
            data-testid={`control-${field.path}`}
            data-widget="TagPicker"
            mode="tags"
            {...common}
          />
        );
      default:
        return <Input data-testid={`control-${field.path}`} {...common} />;
    }
  }

  return (
    <Form
      form={form}
      data-testid="schema-form"
      data-resource={schema.resource}
      data-schema-version={schema.schema_version}
      layout="vertical"
      disabled={disabled}
      onValuesChange={handleValuesChange}
    >
      {orderedFields.map((f) => (
        <Form.Item
          key={f.path}
          name={f.path}
          label={
            <span>
              {f.label}
              {f.required && (
                <Tag color="red" style={{ marginLeft: 4 }}>
                  必填
                </Tag>
              )}
              {f.unit && (
                <span
                  style={{
                    marginLeft: 4,
                    color: 'var(--text-tertiary, #6E7781)',
                    fontFamily: 'var(--font-mono, monospace)',
                  }}
                >
                  / {f.unit}
                </span>
              )}
            </span>
          }
          rules={
            f.required
              ? [
                  {
                    required: true,
                    message: `${f.label} 必填`,
                  },
                ]
              : []
          }
          help={f.help}
          valuePropName={f.widget === 'Switch' ? 'checked' : 'value'}
        >
          {renderControl(f)}
        </Form.Item>
      ))}
    </Form>
  );
}

function optsForGroup(
  field: UiSchemaField,
  enumOptions: Record<string, EnumOption[]>,
): { value: string; label: string }[] {
  if (!field.enum_group) return [];
  return (enumOptions[field.enum_group] ?? []).map((o) => ({
    value: o.value,
    label: o.label,
  }));
}

export type { FormInstance };
export default SchemaForm;