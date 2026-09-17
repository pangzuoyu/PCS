/**
 * HeatComputePage — 换热器计算界面（V1.3 SPEC §7.11.6）。
 *
 * 按 SPEC V1.3 §7.11.6 + 后端 OpenAPI（commit 96165e1）：
 * - POST /api/v1/heat/import-htri（multipart/form-data）→ ImportHtriResponse 201
 * - GET /api/v1/heat/{heat_id} → HeatResultResponse 200（详情 + output_json）
 * - POST /api/v1/heat/{heat_id}/weight-estimate → WeightEstimateResponse 200
 *
 * 设计要点：
 * - 设计阶段单层（无 BASIC/DETAIL 分级；HeatResult ORM 无 design_stage 字段）
 * - 出口流 source_type=HEAT_CALCULATED + change_type=HEAT_EXCHANGE
 * - 9 段重量 segments（5 段壳体 + tube/baffle/channels + shell_total）
 * - input_json / output_json 双轨（output_json.total_weight_kg P7 UTIL 消费）
 * - 错误码：HEAT_INPUT_ERROR 422 / HEAT_NOT_FOUND 404 / HEAT_PROJECT_MISMATCH 422 /
 *         SIM_STREAM_NOT_FOUND 404
 * - workspace_id：当前简化由 PROJECT_ID 同源占位（项目级 workspace 上下文）；
 *   V1.5 阶段接入 meta/projects 取真实 workspace_id。
 */
import { useEffect, useState } from 'react';
import type { JSX } from 'react';
import {
  Alert,
  Button,
  Card,
  Collapse,
  Descriptions,
  Form,
  Input,
  InputNumber,
  Radio,
  Select,
  Spin,
  Table,
  Tag,
  Upload,
  message,
} from 'antd';
import { UploadOutlined } from '@ant-design/icons';

import { PageHeader } from '../../components/common/PageHeader';
import { StateBadge } from '../../components/common/StateBadge';
import { heatApi } from '../../api/heat';
import type {
  ExchangerCategory,
  HeatResultResponse,
  ImportHtriResponse,
  Material,
  TemaType,
  WeightEstimateResponse,
} from '../../types/heat';
import { PROJECT_ID } from '../../constants/env';
import { streamApi } from '../../api/stream';

/**streams 列表条目（仅取 Select 所需子集，避免引入全 stream 详情类型）。*/
interface StreamListItem {
  stream_id: string;
  tag_number: string;
  stream_name: string;
  phase?: string;
}

interface PcsErrorEnvelope {
  code?: string;
  message?: string;
  detail?: unknown;
  trace_id?: string;
}

function extractPcsError(err: unknown): PcsErrorEnvelope {
  if (err && typeof err === 'object' && 'response' in err) {
    const data = (err as { response?: { data?: PcsErrorEnvelope } }).response?.data;
    if (data && typeof data === 'object') return data;
  }
  return {};
}

const EXCHANGER_CATEGORY_OPTIONS: { label: string; value: ExchangerCategory }[] = [
  { label: 'SHELL_TUBE（管壳式）', value: 'SHELL_TUBE' },
  { label: 'AIR_COOL（空冷）', value: 'AIR_COOL' },
  { label: 'PLATE（板式）', value: 'PLATE' },
];

const TEMA_TYPE_OPTIONS: { label: string; value: TemaType }[] = [
  { label: 'BEM', value: 'BEM' },
  { label: 'AEM', value: 'AEM' },
  { label: 'AEL', value: 'AEL' },
  { label: 'NEN', value: 'NEN' },
  { label: 'BEM_FIXED', value: 'BEM_FIXED' },
  { label: 'AEM_U_TUBE', value: 'AEM_U_TUBE' },
];

const MATERIAL_OPTIONS: { label: string; value: Material }[] = [
  { label: 'carbon_steel（碳钢）', value: 'carbon_steel' },
  { label: 'SS304', value: 'SS304' },
  { label: 'SS316', value: 'SS316' },
  { label: 'SS316L', value: 'SS316L' },
];

export function HeatComputePage(): JSX.Element {
  const [importFile, setImportFile] = useState<File | null>(null);
  const [importForm] = Form.useForm();
  const [weightForm] = Form.useForm();
  const [importing, setImporting] = useState(false);
  const [estimating, setEstimating] = useState(false);
  const [importResult, setImportResult] = useState<ImportHtriResponse | null>(null);
  const [heatDetail, setHeatDetail] = useState<HeatResultResponse | null>(null);
  const [weightResult, setWeightResult] = useState<WeightEstimateResponse | null>(null);
  const [streamOptions, setStreamOptions] = useState<{ value: string; label: JSX.Element }[]>([]);
  const [streamsLoading, setStreamsLoading] = useState(false);

  // OPEN-6：源流从 Input 改为 Select（按 V1.5 接 streams 列表）
  useEffect(() => {
    let cancelled = false;
    setStreamsLoading(true);
    streamApi
      .listByProject(PROJECT_ID)
      .then((streams) => {
        if (cancelled) return;
        const opts = (streams as StreamListItem[]).map((s) => ({
          value: s.stream_id,
          label: (
            <span>
              <code>{s.stream_id}</code> {s.tag_number} — {s.stream_name}
              {s.phase ? ` (${s.phase})` : ''}
            </span>
          ),
        }));
        setStreamOptions(opts);
      })
      .catch(() => {
        if (cancelled) return;
        // 加载失败不阻塞表单（OPEN-6 接受：可手动输入 UUID）
        setStreamOptions([]);
      })
      .finally(() => {
        if (!cancelled) setStreamsLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const onImport = async () => {
    if (!importFile) {
      message.warning('请先选择 HTRI .txt 文件');
      return;
    }
    let values;
    try {
      values = await importForm.validateFields();
    } catch {
      return;
    }
    setImporting(true);
    try {
      const resp = await heatApi.importHtri({
        file: importFile,
        project_id: PROJECT_ID,
        workspace_id: PROJECT_ID, // 项目级 workspace 占位；V1.5 接 meta/projects
        equipment_no: values.equipment_no,
        tag_number: values.tag_number,
        exchanger_category: values.exchanger_category,
        source_stream_id: values.source_stream_id || undefined,
      });
      setImportResult(resp);
      // OPEN-7：import() 透传 equipment_name + output_json，免去 get() roundtrip
      // 直接用 resp 构造 HeatResultResponse 占位（input_json 在 import 阶段尚未完整解析，置空对象）
      setHeatDetail({
        calc_id: resp.calc_id,
        calc_type: resp.calc_type,
        project_id: resp.project_id,
        workspace_id: PROJECT_ID, // 占位：V1.5 接 meta 后真值
        tag_number: resp.tag_number,
        equipment_no: resp.equipment_no,
        equipment_name: resp.equipment_name,
        exchanger_category: resp.exchanger_category,
        duty: resp.duty_w,
        record_hash: resp.record_hash,
        input_json: {},
        output_json: resp.output_json,
      });
      message.success(`HEAT 导入完成：record_hash=${resp.record_hash}`);
    } catch (err: unknown) {
      const env = extractPcsError(err);
      const code = env.code ?? '';
      if (code === 'HEAT_INPUT_ERROR') {
        message.error(`HTRI 解析失败：${env.message ?? '请检查文件格式'}`);
      } else if (code === 'SIM_STREAM_NOT_FOUND') {
        message.error('源流不存在，请重新选择');
      } else if (code === 'HEAT_PROJECT_MISMATCH') {
        message.error('源流与项目不一致，请重新选择');
      } else {
        message.error(env.message ?? '导入失败');
      }
    } finally {
      setImporting(false);
    }
  };

  const onEstimateWeight = async () => {
    if (!heatDetail) {
      message.warning('请先导入 HTRI 文件');
      return;
    }
    let values;
    try {
      values = await weightForm.validateFields();
    } catch {
      return;
    }
    setEstimating(true);
    try {
      const resp = await heatApi.estimateWeight(heatDetail.calc_id, values);
      setWeightResult(resp);
      // OPEN-7 闭环：resp.output_json 直接含刷新后的 output_json，免去 get() roundtrip
      setHeatDetail((prev) =>
        prev
          ? {
              ...prev,
              record_hash: resp.record_hash,
              output_json: resp.output_json,
            }
          : prev,
      );
      message.success(`重量估算完成：total=${resp.total_weight_kg.toFixed(1)} kg`);
    } catch (err: unknown) {
      const env = extractPcsError(err);
      if (env.code === 'HEAT_NOT_FOUND') {
        message.error('换热器记录不存在');
      } else {
        message.error(env.message ?? '重量估算失败');
      }
    } finally {
      setEstimating(false);
    }
  };

  const segmentRows = weightResult
    ? Object.entries(weightResult.segments).map(([k, v]) => ({
        key: k,
        segment: k,
        weight_kg: v.weight_kg,
        formula_ref: v.formula_ref,
      }))
    : [];

  return (
    <Spin spinning={importing || estimating}>
      <div data-testid="heat-compute-page">
        <PageHeader
          title="换热器计算"
          module="HEAT"
        actions={
          <Button
            onClick={() => {
              setImportResult(null);
              setHeatDetail(null);
              setWeightResult(null);
              setImportFile(null);
              importForm.resetFields();
              weightForm.resetFields();
            }}
          >
            重置
          </Button>
        }
      />

      <Card title="导入 HTRI 文件" style={{ marginBottom: 16 }}>
        <Upload
          beforeUpload={(f) => {
            setImportFile(f);
            return false; // 阻止自动上传
          }}
          accept=".txt"
          maxCount={1}
          onRemove={() => setImportFile(null)}
        >
          <Button icon={<UploadOutlined />}>选择 HTRI .txt 文件</Button>
        </Upload>
        {importFile && (
          <Alert
            type="success"
            showIcon
            style={{ marginTop: 8 }}
            message={`已选择：${importFile.name}（${importFile.size} bytes）`}
          />
        )}
        <Form form={importForm} layout="vertical" style={{ marginTop: 16 }}>
          <Form.Item
            name="equipment_no"
            label="设备位号"
            rules={[{ required: true, message: '请输入设备位号（如 E-201）' }]}
          >
            <Input placeholder="E-201" />
          </Form.Item>
          <Form.Item
            name="tag_number"
            label="业务 tag"
            rules={[{ required: true, message: '请输入业务 tag' }]}
          >
            <Input placeholder="E-201" />
          </Form.Item>
          <Form.Item
            name="exchanger_category"
            label="换热器类型"
            rules={[{ required: true, message: '请选择换热器类型' }]}
          >
            <Radio.Group options={EXCHANGER_CATEGORY_OPTIONS} optionType="button" />
          </Form.Item>
          <Form.Item
            name="source_stream_id"
            label="源流（可选；提供则创建 HEAT_EXCHANGE outlet）"
            tooltip="从项目 SIM 流列表选择；可清空表示不创建 outlet"
          >
            <Select
              allowClear
              showSearch
              loading={streamsLoading}
              placeholder="选择源流（可选；不选则不创建 HEAT_EXCHANGE outlet）"
              options={streamOptions}
              optionFilterProp="label"
              notFoundContent={streamsLoading ? '加载中…' : '该项目下无 SIM 流'}
            />
          </Form.Item>
          <Form.Item>
            <Button type="primary" onClick={onImport} disabled={!importFile}>
              导入 HTRI
            </Button>
          </Form.Item>
        </Form>
      </Card>

      {heatDetail && (
        <Card
          title="计算结果"
          extra={<StateBadge module="HEAT" status="DRAFT" />}
          style={{ marginBottom: 16 }}
        >
          <Descriptions column={2} bordered size="small">
            <Descriptions.Item label="calc_id">
              <code>{heatDetail.calc_id}</code>
            </Descriptions.Item>
            <Descriptions.Item label="record_hash">
              <code>{heatDetail.record_hash ?? '—'}</code>
            </Descriptions.Item>
            <Descriptions.Item label="设备位号">{heatDetail.equipment_no ?? '—'}</Descriptions.Item>
            <Descriptions.Item label="业务 tag">{heatDetail.tag_number}</Descriptions.Item>
            <Descriptions.Item label="类型">{heatDetail.exchanger_category}</Descriptions.Item>
            <Descriptions.Item label="热负荷 duty (W)">
              {heatDetail.duty !== null ? heatDetail.duty.toFixed(0) : '—'}
            </Descriptions.Item>
          </Descriptions>

          {heatDetail.output_json &&
            'total_weight_kg' in heatDetail.output_json && (
              <Alert
                type="info"
                showIcon
                message={`P7 UTIL 总重：${(heatDetail.output_json.total_weight_kg as number).toFixed(1)} kg`}
                style={{ marginTop: 12 }}
              />
            )}

          {importResult?.outlet_stream_id && (
            <Card type="inner" title="出口流（HEAT_CALCULATED）" style={{ marginTop: 12 }}>
              <Tag color="default">DRAFT</Tag>
              <Tag color="blue">source_type: HEAT_CALCULATED</Tag>
              <Tag color="cyan">change_type: HEAT_EXCHANGE</Tag>
              <div style={{ marginTop: 8 }}>
                Stream ID: <code>{importResult.outlet_stream_id}</code>
              </div>
              <div>Name: {importResult.outlet_stream_name}</div>
            </Card>
          )}
        </Card>
      )}

      {heatDetail && (
        <Collapse style={{ marginBottom: 16 }}>
          <Collapse.Panel header="TEMA 9th 重量估算（点击展开）" key="weight">
            <Form form={weightForm} layout="vertical">
              <Form.Item
                name="tema_type"
                label="TEMA 类型"
                rules={[{ required: true, message: '请选择 TEMA 类型' }]}
              >
                <Radio.Group options={TEMA_TYPE_OPTIONS} optionType="button" />
              </Form.Item>
              <Form.Item
                name="material"
                label="材料"
                initialValue="carbon_steel"
              >
                <Radio.Group options={MATERIAL_OPTIONS} optionType="button" />
              </Form.Item>
              <Form.Item
                name="shell_id_m"
                label="壳体内径 (m)"
                rules={[{ required: true, type: 'number', min: 0 }]}
              >
                <InputNumber step={0.001} style={{ width: 200 }} />
              </Form.Item>
              <Form.Item
                name="shell_length_m"
                label="壳体长度 (m)"
                rules={[{ required: true, type: 'number', min: 0 }]}
              >
                <InputNumber step={0.001} style={{ width: 200 }} />
              </Form.Item>
              <Form.Item
                name="shell_thickness_m"
                label="壳体壁厚 (m)"
                rules={[{ required: true, type: 'number', min: 0 }]}
              >
                <InputNumber step={0.0001} style={{ width: 200 }} />
              </Form.Item>
              <Form.Item>
                <Button type="primary" onClick={onEstimateWeight}>
                  估算重量
                </Button>
              </Form.Item>
            </Form>

            {weightResult && (
              <Card type="inner" title="重量结果" style={{ marginTop: 12 }}>
                <Descriptions column={2} bordered size="small">
                  <Descriptions.Item label="总重 (kg)">
                    {weightResult.total_weight_kg.toFixed(1)}
                  </Descriptions.Item>
                  <Descriptions.Item label="壳体总重 (kg)">
                    {weightResult.shell_total_kg.toFixed(1)}
                  </Descriptions.Item>
                  <Descriptions.Item label="record_hash" span={2}>
                    <code>{weightResult.record_hash}</code>
                  </Descriptions.Item>
                </Descriptions>

                <Table
                  dataSource={segmentRows}
                  columns={[
                    { title: '段', dataIndex: 'segment', key: 'segment' },
                    {
                      title: '重量 (kg)',
                      dataIndex: 'weight_kg',
                      key: 'weight_kg',
                      render: (v: number) => v.toFixed(2),
                    },
                    {
                      title: '公式来源',
                      dataIndex: 'formula_ref',
                      key: 'formula_ref',
                      ellipsis: true,
                    },
                  ]}
                  pagination={false}
                  size="small"
                  style={{ marginTop: 12 }}
                />

                <div style={{ marginTop: 12 }}>
                  <strong>formula_ref:</strong>{' '}
                  <code>{JSON.stringify(weightResult.formula_ref)}</code>
                </div>
              </Card>
            )}
          </Collapse.Panel>
        </Collapse>
      )}
      </div>
    </Spin>
  );
}

export default HeatComputePage;