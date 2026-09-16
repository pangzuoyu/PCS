/**
 * TemplateFilePage 测试（P45-2-6 / Task 24）。
 *
 * 覆盖 SPEC §7.10.4 模板文件管理：
 * - 上传 .dotx / .xltx（限定扩展名 + 大小）
 * - 占位符自动解析（{{xxx}} 格式 → 列表）
 * - 缺失映射提示（已知字段未在占位符中出现 → 提示）
 * - 版本列表（每个模板多版本）
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';

import { TemplateFilePage, type TemplateFile } from '../../../src/pages/config/TemplateFilePage';

const templates: TemplateFile[] = [
  {
    template_id: 't-1',
    name: '工艺自控说明模板',
    ext: 'dotx',
    size_bytes: 102_400,
    placeholders: ['{{project_name}}', '{{stream_no}}', '{{pressure}}'],
    known_fields: ['project_name', 'stream_no', 'pressure', 'temperature', 'flow_rate'],
    versions: [
      { version: 'v1.0', uploaded_by: '张三', uploaded_at: '2026-09-10', size_bytes: 102_400 },
      { version: 'v1.1', uploaded_by: '李四', uploaded_at: '2026-09-15', size_bytes: 105_000 },
    ],
  },
];

describe('TemplateFilePage — 渲染 (P45-2-6)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('渲染标题 + 上传区 + 模板列表', () => {
    render(<TemplateFilePage templates={templates} />);
    expect(screen.getByText('模板文件管理')).toBeTruthy();
    expect(screen.getByTestId('template-upload-area')).toBeTruthy();
    expect(screen.getByTestId('template-list')).toBeTruthy();
  });

  it('渲染每个模板卡片', () => {
    render(<TemplateFilePage templates={templates} />);
    const items = document.querySelectorAll('[data-testid="template-item"]');
    expect(items.length).toBe(1);
    expect(items[0].textContent).toContain('工艺自控说明模板');
  });
});

describe('TemplateFilePage — 占位符解析', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('渲染已解析占位符列表', () => {
    render(<TemplateFilePage templates={templates} />);
    const item = document.querySelector('[data-testid="template-item"]')!;
    expect(item.textContent).toContain('{{project_name}}');
    expect(item.textContent).toContain('{{stream_no}}');
    expect(item.textContent).toContain('{{pressure}}');
  });

  it('提取占位符集合：3 个 unique', () => {
    render(<TemplateFilePage templates={templates} />);
    const phs = document.querySelectorAll('[data-testid="template-placeholder"]');
    expect(phs.length).toBe(3);
  });
});

describe('TemplateFilePage — 缺失映射提示', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('known_fields 未出现在 placeholders 中 → 警告提示', () => {
    render(<TemplateFilePage templates={templates} />);
    // temperature / flow_rate 未在 placeholders 中
    const alerts = document.querySelectorAll('[data-testid="template-missing-mapping"]');
    expect(alerts.length).toBeGreaterThan(0);
    expect(alerts[0].textContent).toContain('temperature');
  });

  it('占位符全部覆盖 known_fields → 无缺失提示', () => {
    const full: TemplateFile = {
      ...templates[0],
      placeholders: ['{{project_name}}', '{{stream_no}}', '{{pressure}}', '{{temperature}}', '{{flow_rate}}'],
      known_fields: ['project_name', 'stream_no', 'pressure', 'temperature', 'flow_rate'],
    };
    render(<TemplateFilePage templates={[full]} />);
    const alerts = document.querySelectorAll('[data-testid="template-missing-mapping"]');
    expect(alerts.length).toBe(0);
  });
});

describe('TemplateFilePage — 版本列表', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('每个模板显示版本表', () => {
    render(<TemplateFilePage templates={templates} />);
    const versions = document.querySelectorAll('[data-testid="template-version-row"]');
    expect(versions.length).toBe(2);
    expect(versions[0].textContent).toContain('v1.0');
    expect(versions[1].textContent).toContain('v1.1');
  });
});

describe('TemplateFilePage — 上传', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('上传 .dotx 文件 → onUpload 收到文件', () => {
    const onUpload = vi.fn();
    render(<TemplateFilePage templates={templates} onUpload={onUpload} />);
    const fileInput = screen.getByTestId('template-file-input') as HTMLInputElement;
    const file = new File(['fake'], 'test.dotx', {
      type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.template',
    });
    fireEvent.change(fileInput, { target: { files: [file] } });
    expect(onUpload).toHaveBeenCalledTimes(1);
    expect(onUpload.mock.calls[0][0].name).toBe('test.dotx');
  });

  it('上传 .xltx 文件 → onUpload 收到', () => {
    const onUpload = vi.fn();
    render(<TemplateFilePage templates={templates} onUpload={onUpload} />);
    const fileInput = screen.getByTestId('template-file-input') as HTMLInputElement;
    const file = new File(['fake'], 'report.xltx', { type: '' });
    fireEvent.change(fileInput, { target: { files: [file] } });
    expect(onUpload).toHaveBeenCalledTimes(1);
  });

  it('上传 .docx（非 dotx/xltx）→ 拒绝 + 错误提示', () => {
    const onUpload = vi.fn();
    render(<TemplateFilePage templates={templates} onUpload={onUpload} />);
    const fileInput = screen.getByTestId('template-file-input') as HTMLInputElement;
    const file = new File(['fake'], 'bad.docx', { type: '' });
    fireEvent.change(fileInput, { target: { files: [file] } });
    expect(onUpload).not.toHaveBeenCalled();
    expect(screen.getByTestId('template-upload-error')).toBeTruthy();
  });
});