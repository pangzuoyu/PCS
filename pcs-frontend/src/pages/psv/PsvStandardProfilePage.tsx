/**
 * PsvStandardProfilePage — 项目级 PSV 标准配置（V1.2 SPEC §7.11.5）。
 *
 * 按 SPEC V1.2 + 后端 OpenAPI（commit 93627a7）：
 * - GET /api/v1/projects/{pid}/psv/standard-profile → PsvStandardProfile | null
 * - POST /api/v1/projects/{pid}/psv/standard-profile → PsvStandardProfile（创建/激活）
 * - CUSTOM 必须填 approval_json + approved_by，否则 422 PSV_INPUT_ERROR
 *
 * 复用 api/psv.ts（commit 238f882）+ types/psv.ts（commit 61a3706）。
 */
import { useEffect, useState } from 'react';
import type { JSX } from 'react';
import {
  Alert,
  Button,
  Card,
  Col,
  Descriptions,
  Drawer,
  Empty,
  Form,
  Input,
  Radio,
  Row,
  Space,
  Spin,
  Table,
  Tag,
  Typography,
  message,
} from 'antd';

import { PageHeader } from '../../components/common/PageHeader';
import { psvApi } from '../../api/psv';
import type {
  PsvStandardProfile,
  PsvStandardProfileCode,
  UpsertPsvStandardProfileRequest,
  FormulaRef,
} from '../../types/psv';

interface Props {
  projectId: string;
}

const PROFILE_CODE_OPTIONS: { value: PsvStandardProfileCode; label: string }[] = [
  { value: 'API', label: 'API（默认 API/7th）' },
  { value: 'GB', label: 'GB（GB/T 150.1 2011/2024）' },
  { value: 'CUSTOM', label: 'CUSTOM（需 approval_json）' },
];

const PROFILE_CODE_TAG_COLOR: Record<PsvStandardProfileCode, string> = {
  API: 'blue',
  GB: 'purple',
  CUSTOM: 'orange',
};

interface PcsErrorEnvelope {
  code?: string;
  message?: string;
}

function extractPcsError(err: unknown): PcsErrorEnvelope {
  if (err && typeof err === 'object' && 'response' in err) {
    const data = (err as { response?: { data?: PcsErrorEnvelope } }).response?.data;
    if (data && typeof data === 'object') return data;
  }
  return {};
}

export function PsvStandardProfilePage({ projectId }: Props): JSX.Element {
  const [profile, setProfile] = useState<PsvStandardProfile | null>(null);
  const [loading, setLoading] = useState(false);
  const [editing, setEditing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = async () => {
    setLoading(true);
    setError(null);
    try {
      const p = await psvApi.getStandardProfile(projectId);
      setProfile(p);
    } catch (err: unknown) {
      const env = extractPcsError(err);
      const msg = env.message ?? '查询项目标准配置失败';
      message.error(msg);
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId]);

  return (
    <div data-testid="psv-standard-profile-page">
      <PageHeader
        title="项目 PSV 标准配置"
        module="PSV"
        actions={
          <Space>
            <Button
              data-testid="psv-standard-refresh"
              onClick={() => void refresh()}
              loading={loading}
            >
              刷新
            </Button>
            <Button
              type="primary"
              data-testid="psv-standard-edit"
              onClick={() => setEditing(true)}
            >
              {profile ? '更新配置' : '新增配置'}
            </Button>
          </Space>
        }
      />

      <Spin spinning={loading}>
        {error && (
          <Alert
            type="error"
            message={error}
            data-testid="psv-standard-error"
            style={{ marginBottom: 16 }}
          />
        )}

        {!profile ? (
          <Card>
            <Empty
              description="项目未配置 PSV 标准（按全局默认 API/7th）"
              data-testid="psv-standard-empty"
            />
          </Card>
        ) : (
          <CurrentProfileCard profile={profile} />
        )}
      </Spin>

      <EditDrawer
        open={editing}
        current={profile}
        onClose={() => setEditing(false)}
        onSubmit={async (req) => {
          try {
            const p = await psvApi.upsertStandardProfile(projectId, req);
            setProfile(p);
            setEditing(false);
            message.success(`PSV 标准配置已激活：${req.profile_code}`);
          } catch (err: unknown) {
            const env = extractPcsError(err);
            const code = env.code ?? '';
            const msg = env.message ?? '保存失败';
            if (code === 'PSV_INPUT_ERROR') {
              message.error('CUSTOM 必须填 approval_json + approved_by');
            } else if (code === 'PSV_PROFILE_CONFLICT') {
              message.error(`标准配置冲突：${msg}`);
            } else {
              message.error(msg);
            }
          }
        }}
      />
    </div>
  );
}

// ---------------------------------------------------------------------------
// 当前 profile 卡片
// ---------------------------------------------------------------------------

interface CurrentProfileCardProps {
  profile: PsvStandardProfile;
}

function CurrentProfileCard({ profile }: CurrentProfileCardProps): JSX.Element {
  const refsTable = Object.entries(profile.standard_refs_json).map(([k, v]) => ({
    key: k,
    standard: v.standard,
    version: v.version,
    clause: v.clause,
  }));

  return (
    <Row gutter={16}>
      <Col span={14}>
        <Card title="当前默认配置" size="small" data-testid="psv-standard-card">
          <Descriptions size="small" column={2}>
            <Descriptions.Item label="profile_code">
              <Tag color={PROFILE_CODE_TAG_COLOR[profile.profile_code]}>
                {profile.profile_code}
              </Tag>
            </Descriptions.Item>
            <Descriptions.Item label="discipline">{profile.discipline}</Descriptions.Item>
            <Descriptions.Item label="is_default">
              <Tag color={profile.is_default ? 'green' : 'default'}>
                {profile.is_default ? 'TRUE' : 'FALSE'}
              </Tag>
            </Descriptions.Item>
            <Descriptions.Item label="migrated_default">
              {profile.migrated_default ? 'TRUE' : 'FALSE'}
            </Descriptions.Item>
            <Descriptions.Item label="effective_from">
              {profile.effective_from}
            </Descriptions.Item>
            <Descriptions.Item label="effective_to">
              {profile.effective_to ?? <Typography.Text type="secondary">NULL（当前生效）</Typography.Text>}
            </Descriptions.Item>
            <Descriptions.Item label="approved_by">
              {profile.approved_by ?? <Typography.Text type="secondary">—</Typography.Text>}
            </Descriptions.Item>
            <Descriptions.Item label="profile_id">
              <code>{profile.profile_id}</code>
            </Descriptions.Item>
          </Descriptions>
        </Card>

        <Card title="standard_refs_json" size="small" style={{ marginTop: 16 }}>
          <Table
            size="small"
            rowKey="key"
            pagination={false}
            dataSource={refsTable}
            columns={[
              { title: '子项', dataIndex: 'key', width: 140 },
              { title: 'standard', dataIndex: 'standard' },
              { title: 'version', dataIndex: 'version', width: 100 },
              { title: 'clause', dataIndex: 'clause' },
            ]}
          />
        </Card>
      </Col>

      <Col span={10}>
        <Card title="approval_json" size="small">
          {profile.approval_json ? (
            <pre
              data-testid="psv-approval-json"
              style={{
                background: '#f5f5f5',
                padding: 12,
                borderRadius: 4,
                fontSize: 12,
                overflow: 'auto',
                maxHeight: 320,
              }}
            >
              {JSON.stringify(profile.approval_json, null, 2)}
            </pre>
          ) : (
            <Typography.Text type="secondary">
              未设置（CUSTOM 必填；API / GB 可选）
            </Typography.Text>
          )}
        </Card>
      </Col>
    </Row>
  );
}

// ---------------------------------------------------------------------------
// 编辑 Drawer
// ---------------------------------------------------------------------------

interface EditDrawerProps {
  open: boolean;
  current: PsvStandardProfile | null;
  onClose: () => void;
  onSubmit: (req: UpsertPsvStandardProfileRequest) => Promise<void>;
}

function EditDrawer({ open, current, onClose, onSubmit }: EditDrawerProps): JSX.Element {
  const [form] = Form.useForm();
  const profileCode = Form.useWatch('profile_code', form);
  const isCustom = profileCode === 'CUSTOM';

  const handleSubmit = async () => {
    const values = await form.validateFields();
    const refs: Record<string, FormulaRef> = {
      fire_case: {
        standard: values.fire_case_standard,
        version: values.fire_case_version,
        clause: values.fire_case_clause,
      },
      relief_area: {
        standard: values.relief_area_standard,
        version: values.relief_area_version,
        clause: values.relief_area_clause,
      },
      orifice: {
        standard: values.orifice_standard,
        version: values.orifice_version,
        clause: values.orifice_clause,
      },
    };
    const req: UpsertPsvStandardProfileRequest = {
      profile_code: values.profile_code,
      standard_refs_json: refs,
      approval_json:
        isCustom && values.approval_json
          ? safeJsonParse(values.approval_json)
          : undefined,
      approved_by: isCustom ? values.approved_by : undefined,
    };
    await onSubmit(req);
  };

  return (
    <Drawer
      title={current ? '更新项目 PSV 标准配置' : '新增项目 PSV 标准配置'}
      open={open}
      onClose={onClose}
      width={640}
      data-testid="psv-standard-drawer"
      extra={
        <Space>
          <Button onClick={onClose}>取消</Button>
          <Button type="primary" onClick={() => void handleSubmit()} data-testid="psv-standard-submit">
            提交
          </Button>
        </Space>
      }
    >
      <Form
        form={form}
        layout="vertical"
        initialValues={{
          profile_code: current?.profile_code ?? 'API',
          fire_case_standard: 'API_521',
          fire_case_version: '7th',
          fire_case_clause: '§5.15.2.2.1',
          relief_area_standard: 'API_520',
          relief_area_version: '7th',
          relief_area_clause: '§5.6.3',
          orifice_standard: 'API_526',
          orifice_version: '7th',
          orifice_clause: 'Table 1',
          approved_by: '',
          approval_json: '',
        }}
      >
        <Form.Item label="profile_code" name="profile_code" rules={[{ required: true }]}>
          <Radio.Group options={PROFILE_CODE_OPTIONS} optionType="button" />
        </Form.Item>

        <Typography.Title level={5}>standard_refs_json</Typography.Title>

        <Form.Item label="fire_case.standard" name="fire_case_standard" rules={[{ required: true }]}>
          <Input />
        </Form.Item>
        <Form.Item label="fire_case.version" name="fire_case_version" rules={[{ required: true }]}>
          <Input />
        </Form.Item>
        <Form.Item label="fire_case.clause" name="fire_case_clause" rules={[{ required: true }]}>
          <Input />
        </Form.Item>

        <Form.Item label="relief_area.standard" name="relief_area_standard" rules={[{ required: true }]}>
          <Input />
        </Form.Item>
        <Form.Item label="relief_area.version" name="relief_area_version" rules={[{ required: true }]}>
          <Input />
        </Form.Item>
        <Form.Item label="relief_area.clause" name="relief_area_clause" rules={[{ required: true }]}>
          <Input />
        </Form.Item>

        <Form.Item label="orifice.standard" name="orifice_standard" rules={[{ required: true }]}>
          <Input />
        </Form.Item>
        <Form.Item label="orifice.version" name="orifice_version" rules={[{ required: true }]}>
          <Input />
        </Form.Item>
        <Form.Item label="orifice.clause" name="orifice_clause" rules={[{ required: true }]}>
          <Input />
        </Form.Item>

        {isCustom && (
          <>
            <Typography.Title level={5}>CUSTOM 审批（必填）</Typography.Title>
            <Form.Item
              label="approved_by (UUID)"
              name="approved_by"
              rules={[{ required: true, message: 'CUSTOM 必须填 approved_by' }]}
            >
              <Input placeholder="00000000-0000-0000-0000-000000000099" />
            </Form.Item>
            <Form.Item
              label="approval_json (JSON)"
              name="approval_json"
              rules={[
                { required: true, message: 'CUSTOM 必须填 approval_json' },
                {
                  validator: (_r, v) =>
                    v && safeJsonParse(v)
                      ? Promise.resolve()
                      : Promise.reject(new Error('approval_json 必须是合法 JSON')),
                },
              ]}
            >
              <Input.TextArea rows={6} placeholder='{"approver": "...", "memo": "..."}' />
            </Form.Item>
          </>
        )}
      </Form>
    </Drawer>
  );
}

function safeJsonParse(s: string): Record<string, unknown> | null {
  try {
    const parsed = JSON.parse(s);
    if (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) {
      return parsed as Record<string, unknown>;
    }
  } catch {
    return null;
  }
  return null;
}