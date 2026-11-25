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

import {
  canConvert,
  displayUnit,
  fromDisplay,
  toDisplay,
  type UnitDisplay,
  type UnitSystem,
} from '../../utils/units';

export type { UnitDisplay, UnitSystem };

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
  unit?: string | null;
  /**
   * 显示单位变换（P10-K · W-1b）—— **后端下发**，前端**没有换算表**。
   *
   * ⚠️ **null = 这个字段不可换算**（湿度 % / 噪声 dB …）⇒ ⇒ ⇒ 前端**标灰**
   * ⇒ ⇒ ⇒ 按原值显示（**不是禁用**）。
   */
  unit_display?: UnitDisplay | null;
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
  /**
   * 当前**显示**单位制（P10-K · W-4）—— 默认 SI（= canonical）。
   *
   * ⚠️ **换算只在控件边界发生**（`getValueProps` / `normalize`）
   * ⇒ ⇒ ⇒ **form state 恒为 canonical（SI）** ⇒ ⇒ ⇒ 否则每次保存时
   * ⇒ ⇒ ⇒ **未被编辑的字段**也会在末位比特上漂移。
   */
  unitSystem?: UnitSystem;
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
  unitSystem = 'SI',
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
            data-unit={displayUnit(field, unitSystem) ?? ''}
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
      {orderedFields.map((f) => {
        // ⚠️ **单位后缀按「当前显示单位制」取**（P10-K · W-4）
        // ⇒ ⇒ ⇒ US 模式下标签显示 psi（不是 kPa）⇒ ⇒ ⇒ 否则标签在骗人。
        const shownUnit = displayUnit(f, unitSystem);
        // ⚠️ **不可换算的字段标灰**（有单位但换算没意义）⇒ ⇒ ⇒ **不是禁用**
        // ⇒ ⇒ ⇒ 用户仍可录入、按原值显示。
        const convertible = canConvert(f);
        return (
        <Form.Item
          key={f.path}
          name={f.path}
          // ⚠️ **换算只在控件边界**（P10-K · W-5）⇒ ⇒ ⇒ form state 恒 canonical
          getValueProps={
            f.widget === 'NumberInput'
              ? (v: number | null | undefined) => ({
                  value: toDisplay(v, f, unitSystem),
                })
              : undefined
          }
          normalize={
            f.widget === 'NumberInput'
              ? (v: number | null | undefined) => fromDisplay(v, f, unitSystem)
              : undefined
          }
          label={
            <span>
              {f.label}
              {f.required && (
                <Tag color="red" style={{ marginLeft: 4 }}>
                  必填
                </Tag>
              )}
              {shownUnit && (
                <span
                  data-testid={`unit-${f.path}`}
                  title={
                    convertible
                      ? undefined
                      : '该字段无换算（后端未下发换算因子）⇒ 按原值显示'
                  }
                  style={{
                    marginLeft: 4,
                    color: 'var(--text-tertiary, #6E7781)',
                    fontFamily: 'var(--font-mono, monospace)',
                    opacity: convertible || unitSystem === 'SI' ? 1 : 0.55,
                  }}
                >
                  / {shownUnit}
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
        );
      })}
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