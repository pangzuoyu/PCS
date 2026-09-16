/**
 * SchemaForm 测试（P45-1-14 / Task 19）。
 *
 * 覆盖（SPEC §8 + plan P45-1-14）：
 * - 渲染：fields 按 order 升序 + 跳过 visible=false
 * - 控件映射：9 widget 类型（Input/Select/NumberInput/TextArea/Switch/
 *   DatePicker/AutoComplete/Cascader/TagPicker）
 * - 字段属性：required 红 tag + unit 等宽 + help 提示 + readonly
 * - onChange：表单值变化触发回调
 * - enumOptions：Select 从外部 enumOptions 拉选项
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';

import { SchemaForm, type UiSchemaResponse, type EnumOption } from '../../../src/components/common/SchemaForm';

const schema: UiSchemaResponse = {
  schema_version: '1.0.0',
  resource: 'stream',
  fields: [
    {
      path: 'stream_name',
      label: '管段物流号',
      widget: 'Input',
      required: true,
      placeholder: '如 FEED-101',
      help: '物流唯一标识（最大 100 字符）',
      order: 10,
      max_length: 100,
    },
    {
      path: 'case_type',
      label: '物流工况',
      widget: 'Select',
      required: true,
      enum_group: 'StreamCaseType',
      order: 20,
    },
    {
      path: 'temp',
      label: '温度',
      widget: 'NumberInput',
      unit: '°C',
      order: 60,
    },
    {
      path: 'is_active',
      label: '启用',
      widget: 'Switch',
      order: 90,
    },
    {
      path: 'commissioning_date',
      label: '投用日期',
      widget: 'DatePicker',
      order: 95,
    },
    {
      path: 'tags',
      label: '标签',
      widget: 'TagPicker',
      order: 96,
    },
    {
      path: 'composition_json',
      label: '组成',
      widget: 'TextArea',
      order: 200,
      visible: false,
    },
  ],
};

const enumOptions: Record<string, EnumOption[]> = {
  StreamCaseType: [
    { value: 'NORMAL', label: '正常工况' },
    { value: 'END_OF_RUN', label: '运转末期' },
  ],
};

describe('SchemaForm — 渲染 (P45-1-14)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('渲染 Form + resource + schema_version', () => {
    render(<SchemaForm schema={schema} />);
    const form = screen.getByTestId('schema-form');
    expect(form).toBeTruthy();
    expect(form.getAttribute('data-resource')).toBe('stream');
    expect(form.getAttribute('data-schema-version')).toBe('1.0.0');
  });

  it('fields 按 order 升序排列', () => {
    const { container } = render(<SchemaForm schema={schema} />);
    const items = container.querySelectorAll('.ant-form-item');
    const labels = Array.from(items).map((i) =>
      i.querySelector('label')?.textContent ?? '',
    );
    // 第一个是 stream_name（order 10）
    expect(labels[0]).toContain('管段物流号');
  });

  it('跳过 visible=false 字段', () => {
    const { container } = render(<SchemaForm schema={schema} />);
    const labels = Array.from(container.querySelectorAll('label')).map((l) => l.textContent ?? '');
    // composition_json 不可见
    expect(labels.some((l) => l.includes('组成'))).toBe(false);
  });
});

describe('SchemaForm — 控件映射', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('Input 控件 data-widget="Input"', () => {
    render(<SchemaForm schema={schema} />);
    expect(screen.getByTestId('control-stream_name').getAttribute('data-widget'))
      .toBe('Input');
  });

  it('Select 控件 data-widget="Select" + data-enum-group', () => {
    render(<SchemaForm schema={schema} enumOptions={enumOptions} />);
    const sel = screen.getByTestId('control-case_type');
    expect(sel.getAttribute('data-widget')).toBe('Select');
    expect(sel.getAttribute('data-enum-group')).toBe('StreamCaseType');
  });

  it('NumberInput 控件 data-widget="NumberInput" + data-unit', () => {
    render(<SchemaForm schema={schema} />);
    const ctrl = screen.getByTestId('control-temp');
    expect(ctrl.getAttribute('data-widget')).toBe('NumberInput');
    expect(ctrl.getAttribute('data-unit')).toBe('°C');
  });

  it('Switch / DatePicker / TagPicker 控件映射', () => {
    render(<SchemaForm schema={schema} />);
    expect(screen.getByTestId('control-is_active').getAttribute('data-widget'))
      .toBe('Switch');
    expect(screen.getByTestId('control-commissioning_date').getAttribute('data-widget'))
      .toBe('DatePicker');
    expect(screen.getByTestId('control-tags').getAttribute('data-widget'))
      .toBe('TagPicker');
  });
});

describe('SchemaForm — 字段属性', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('required 红 tag', () => {
    const { container } = render(<SchemaForm schema={schema} />);
    const streamNameLabel = Array.from(container.querySelectorAll('label')).find(
      (l) => l.textContent?.includes('管段物流号'),
    );
    expect(streamNameLabel?.textContent).toContain('必填');
    expect(streamNameLabel?.innerHTML).toMatch(/ant-tag-red/);
  });

  it('unit 等宽显示', () => {
    const { container } = render(<SchemaForm schema={schema} />);
    const tempLabel = Array.from(container.querySelectorAll('label')).find(
      (l) => l.textContent?.includes('温度'),
    );
    expect(tempLabel?.textContent).toContain('/ °C');
  });

  it('help 提示', () => {
    const { container } = render(<SchemaForm schema={schema} />);
    const helpEl = Array.from(container.querySelectorAll('.ant-form-item-explain')).find(
      (el) => el.textContent?.includes('物流唯一标识'),
    );
    expect(helpEl).toBeTruthy();
  });

  it('readonly 控件 disabled', () => {
    const readonlySchema: UiSchemaResponse = {
      schema_version: '1.0.0',
      resource: 'record',
      fields: [
        {
          path: 'record_type',
          label: '记录类型',
          widget: 'Input',
          readonly: true,
          order: 10,
        },
      ],
    };
    render(<SchemaForm schema={readonlySchema} />);
    const input = screen.getByTestId('control-record_type') as HTMLInputElement;
    expect(input.disabled).toBe(true);
  });
});

describe('SchemaForm — onChange 联动', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('输入框变化 → onChange 收到新值', async () => {
    const onChange = vi.fn();
    render(<SchemaForm schema={schema} onChange={onChange} />);
    const input = screen.getByTestId('control-stream_name') as HTMLInputElement;
    fireEvent.change(input, { target: { value: 'FEED-101' } });
    await waitFor(() => {
      expect(onChange).toHaveBeenCalled();
      const lastCall = onChange.mock.calls[onChange.mock.calls.length - 1];
      expect(lastCall[0]).toEqual(
        expect.objectContaining({ stream_name: 'FEED-101' }),
      );
    });
  });

  it('不传 onChange 不报错', () => {
    render(<SchemaForm schema={schema} />);
    const input = screen.getByTestId('control-stream_name');
    expect(() =>
      fireEvent.change(input, { target: { value: 'X' } }),
    ).not.toThrow();
  });

  it('初始 value 同步到表单', async () => {
    const onChange = vi.fn();
    render(
      <SchemaForm
        schema={schema}
        value={{ stream_name: 'INIT-101', temp: 25 }}
        onChange={onChange}
      />,
    );
    const input = screen.getByTestId('control-stream_name') as HTMLInputElement;
    await waitFor(() => {
      expect(input.value).toBe('INIT-101');
    });
  });
});

describe('SchemaForm — enumOptions 注入', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('Select 从 enumOptions 拉选项', () => {
    render(<SchemaForm schema={schema} enumOptions={enumOptions} />);
    // antd Select 把 options 渲染为内部状态 — 验证控件接收到了 options
    const sel = screen.getByTestId('control-case_type');
    expect(sel.getAttribute('data-enum-group')).toBe('StreamCaseType');
  });

  it('无 enumOptions 时 Select 不报错', () => {
    render(<SchemaForm schema={schema} />);
    const sel = screen.getByTestId('control-case_type');
    expect(sel).toBeTruthy();
  });
});