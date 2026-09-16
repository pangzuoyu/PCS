/**
 * TemplateFilePage — 模板文件管理（P45-2-6 / Task 24）。
 *
 * SPEC §7.10.4：
 * - 上传 .dotx / .xltx（限定扩展名）
 * - 占位符自动解析（{{xxx}} 格式 → 列表）
 * - 缺失映射提示（已知字段未在占位符中出现 → 警告）
 * - 版本列表（每模板多版本）
 *
 * Props（SPEC 锁定）：
 *   templates: TemplateFile[]
 *   onUpload?: (file, ext) => void
 */
import { useState } from 'react';
import {
  Alert,
  Button,
  Empty,
  Space,
  Table,
  Tag,
  Typography,
  Upload,
} from 'antd';
import { UploadOutlined } from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';

/** 模板版本（SPEC §7.10.4）。 */
export interface TemplateVersion {
  version: string;
  uploaded_by: string;
  uploaded_at: string;
  size_bytes: number;
}

/** 模板文件（SPEC §7.10.4）。 */
export interface TemplateFile {
  template_id: string;
  name: string;
  ext: 'dotx' | 'xltx';
  size_bytes: number;
  placeholders: string[];
  /** 项目侧已知字段（用于缺失映射提示）。 */
  known_fields: string[];
  versions: TemplateVersion[];
}

interface Props {
  templates: TemplateFile[];
  onUpload?: (file: File, ext: 'dotx' | 'xltx') => void;
}

const ALLOWED_EXTS: ReadonlySet<string> = new Set(['dotx', 'xltx']);

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
}

function findMissing(template: TemplateFile): string[] {
  const phSet = new Set(template.placeholders.map((p) => p.replace(/[{}]/g, '')));
  return template.known_fields.filter((f) => !phSet.has(f));
}

export function TemplateFilePage({ templates, onUpload }: Props): JSX.Element {
  const [uploadError, setUploadError] = useState<string | null>(null);

  function handleUpload(file: File): boolean {
    setUploadError(null);
    const ext = file.name.split('.').pop()?.toLowerCase() ?? '';
    if (!ALLOWED_EXTS.has(ext)) {
      setUploadError(`不支持的扩展名 .${ext}（仅允许 .dotx / .xltx）`);
      return false;
    }
    onUpload?.(file, ext as 'dotx' | 'xltx');
    return false; // 阻止 Upload 自动 POST
  }

  return (
    <div data-testid="template-page">
      <Typography.Title level={3}>模板文件管理</Typography.Title>

      <Space
        direction="vertical"
        size={12}
        style={{ width: '100%' }}
        data-testid="template-upload-area"
      >
        <Upload
          data-testid="template-upload"
          accept=".dotx,.xltx"
          beforeUpload={handleUpload}
          showUploadList={false}
        >
          <Button icon={<UploadOutlined />} data-testid="template-upload-btn">
            上传 .dotx / .xltx
          </Button>
        </Upload>
        {/* 提供 input 触发 onUpload（测试用） */}
        <input
          type="file"
          accept=".dotx,.xltx"
          data-testid="template-file-input"
          style={{ display: 'none' }}
          onChange={(e) => {
            const f = e.target.files?.[0];
            if (f) handleUpload(f);
            e.target.value = '';
          }}
        />
        {uploadError && (
          <Alert
            type="error"
            showIcon
            message={uploadError}
            data-testid="template-upload-error"
          />
        )}
      </Space>

      {templates.length === 0 ? (
        <Empty description="暂无模板" data-testid="template-empty" />
      ) : (
        <Space
          direction="vertical"
          size={16}
          style={{ width: '100%', marginTop: 24 }}
          data-testid="template-list"
        >
          {templates.map((t) => {
            const missing = findMissing(t);
            const versionColumns: ColumnsType<TemplateVersion> = [
              { title: '版本', dataIndex: 'version', width: 100 },
              { title: '上传人', dataIndex: 'uploaded_by', width: 120 },
              { title: '上传时间', dataIndex: 'uploaded_at', width: 140 },
              {
                title: '大小',
                dataIndex: 'size_bytes',
                width: 100,
                render: (b: number) => formatSize(b),
              },
            ];
            return (
              <div
                key={t.template_id}
                data-testid="template-item"
                data-template-id={t.template_id}
                style={{
                  border: '1px solid var(--color-border, #E5E7EB)',
                  borderRadius: 4,
                  padding: 16,
                }}
              >
                <Space style={{ marginBottom: 8 }}>
                  <Typography.Title level={4} style={{ margin: 0 }}>
                    {t.name}
                  </Typography.Title>
                  <Tag color="blue">{t.ext.toUpperCase()}</Tag>
                  <Typography.Text type="secondary">{formatSize(t.size_bytes)}</Typography.Text>
                </Space>

                <div style={{ marginBottom: 12 }} data-testid="template-placeholders-section">
                  <Typography.Text strong>占位符（{t.placeholders.length}）：</Typography.Text>
                  <Space wrap style={{ marginTop: 4 }}>
                    {t.placeholders.map((p) => (
                      <Tag key={p} color="cyan" data-testid="template-placeholder">
                        {p}
                      </Tag>
                    ))}
                  </Space>
                </div>

                {missing.length > 0 && (
                  <Alert
                    type="warning"
                    showIcon
                    style={{ marginBottom: 12 }}
                    message={
                      <span data-testid="template-missing-mapping">
                        缺失映射：{missing.join(' / ')}（占位符未覆盖 known_fields）
                      </span>
                    }
                  />
                )}

                <Typography.Text strong>版本列表（{t.versions.length}）</Typography.Text>
                <Table<TemplateVersion>
                  rowKey="version"
                  columns={versionColumns}
                  dataSource={t.versions}
                  pagination={false}
                  size="small"
                  style={{ marginTop: 8 }}
                  onRow={(_, idx) =>
                    ({
                      'data-testid': 'template-version-row',
                      'data-version-index': idx,
                    }) as React.HTMLAttributes<HTMLElement>
                  }
                />
              </div>
            );
          })}
        </Space>
      )}
    </div>
  );
}

export default TemplateFilePage;