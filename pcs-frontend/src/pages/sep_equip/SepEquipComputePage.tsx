/**
 * SepEquipComputePage — SEP_EQUIP 分离设备计算界面（P5-2-4 / Task 12）。
 *
 * SPEC §7.11.4：
 * - 5 设备类型：Cyclone / MistEliminator / Gravity / Vane / Fiber
 * - 设备类型切换 → 字段集自动切换
 * - 计算按钮触发 → 结果卡片（设备类型对应字段）
 *
 * V1：5 类型统一表格布局（device_type → form fields 映射），结果区按设备类型动态渲染。
 *
 * OPEN-4-2：Props 兼容（streams/onCalculate 可选）+ 未注入时走 streamApi.listByProject
 * 自取 + sepEquipApi.calculate 真接 API + Spin loading + STREAM_NOT_CHECKED 错误处理。
 */
import { useEffect, useState } from 'react';
import type { JSX } from 'react';
import {
  Alert,
  Button,
  Card,
  Col,
  Descriptions,
  Form,
  InputNumber,
  Radio,
  Row,
  Select,
  Space,
  Spin,
  Tag,
  Typography,
} from 'antd';

import { PageHeader } from '../../components/common/PageHeader';
import { PROJECT_ID } from '../../constants/env';
import { sepEquipApi, type SepEquipCalculateResponse } from '../../api/sepEquip';
import { streamApi } from '../../api/stream';
import type {
  CycloneParams,
  GravitySeparatorParams,
  MistEliminatorParams,
  SepEquipDeviceType,
} from '../../types/sepEquip';

interface StreamLite {
  stream_id: string;
  tag_number: string;
  /**可选：父组件注入时携带；streamApi 自取路径不返（后端 403 兜底）。*/
  sign_status?: string;
}

interface Props {
  /**可选：父组件注入时优先用（向后兼容 P5-2 测试）；未注入则走 streamApi。*/
  streams?: StreamLite[];
  /**可选：父组件注入时优先用（向后兼容 P5-2 测试）；未注入则走 sepEquipApi。*/
  onCalculate?: (
    device: SepEquipDeviceType,
    params: CycloneParams | MistEliminatorParams | GravitySeparatorParams,
  ) => SepEquipCalculateResponse | undefined;
}

/**后端 PcsError envelope 解析（与 HeatComputePage / VesselComputePage 同模式）。*/
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

const DEVICE_OPTIONS: { value: SepEquipDeviceType; label: string }[] = [
  { value: 'CYCLONE', label: '旋风分离器' },
  { value: 'MIST_ELIMINATOR', label: '丝网除沫器' },
  { value: 'GRAVITY', label: '重力沉降器' },
  { value: 'VANE', label: '叶片分离器' },
  { value: 'FIBER', label: '纤维分离器' },
];

const DEFAULT_CYCLONE: CycloneParams = {
  D_cylinder_m: 0.5,
  D_exhaust_m: 0.25,
  a_inlet_m: 0.2,
  b_inlet_m: 0.1,
  V_in_ms: 15.0,
  rho_kg_m3: 1.2,
  mu_pa_s: 1.8e-5,
  rho_particle_kg_m3: 1100.0,
  N_effective_turns: 5.0,
  method: 'LAPPLE',
};

const DEFAULT_MIST: MistEliminatorParams = {
  pad_type: 'STANDARD',
  Q_gas_m3_s: 0.5,
  D_cylinder_m: 1.0,
  rho_gas_kg_m3: 1.2,
  mu_gas_pa_s: 1.8e-5,
  liquid_load_kg_m3: 0.5,
};

const DEFAULT_GRAVITY: GravitySeparatorParams = {
  d_particle_m: 100e-6,
  rho_particle_kg_m3: 1100.0,
  rho_fluid_kg_m3: 1.2,
  mu_fluid_pa_s: 1.8e-5,
  height_setting_m: 1.0,
  horizontal_velocity_ms: 0.1,
};

export function SepEquipComputePage({
  streams: streamsProp,
  onCalculate: onCalculateProp,
}: Props): JSX.Element {
  const [device, setDevice] = useState<SepEquipDeviceType>('CYCLONE');
  const [streamId, setStreamId] = useState<string | undefined>();
  const [params, setParams] = useState<
    CycloneParams | MistEliminatorParams | GravitySeparatorParams
  >(DEFAULT_CYCLONE);
  const [result, setResult] = useState<SepEquipCalculateResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [calculating, setCalculating] = useState(false);
  const [fetchedStreams, setFetchedStreams] = useState<StreamLite[] | null>(null);
  const [streamsLoading, setStreamsLoading] = useState(false);

  // OPEN-4-2：未注入 streams 时走 streamApi 自取
  useEffect(() => {
    if (streamsProp !== undefined) return;
    let cancelled = false;
    setStreamsLoading(true);
    streamApi
      .listByProject(PROJECT_ID)
      .then((list) => {
        if (cancelled) return;
        // streamApi 不返 sign_status（轻量子集）；不伪造 CHECKED，
        // 真实 ACL/状态由后端 /sep-equip/calculate STREAM_NOT_CHECKED 403 兜底
        setFetchedStreams(
          list.map((s) => ({
            stream_id: s.stream_id,
            tag_number: s.tag_number,
          })),
        );
      })
      .catch(() => {
        if (cancelled) return;
        setFetchedStreams([]);
      })
      .finally(() => {
        if (!cancelled) setStreamsLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [streamsProp]);

  const streams = streamsProp ?? fetchedStreams ?? [];
  const checkedStreams = streams; // sign_status 过滤在 streamApi/mock 阶段由调用方控制

  const onDeviceChange = (v: SepEquipDeviceType): void => {
    setDevice(v);
    if (v === 'CYCLONE') setParams(DEFAULT_CYCLONE);
    else if (v === 'MIST_ELIMINATOR') setParams(DEFAULT_MIST);
    else setParams(DEFAULT_GRAVITY);
    setResult(null);
  };

  const handleCalculate = async () => {
    if (!streamId) {
      setError('请选择物流');
      return;
    }
    setError(null);
    setCalculating(true);
    try {
      let r: SepEquipCalculateResponse | undefined;
      if (onCalculateProp) {
        r = onCalculateProp(device, params);
      } else {
        r = await sepEquipApi.calculate({
          source_stream_id: streamId,
          device_type: device,
          params,
        });
      }
      if (!r) {
        setError('计算失败：返回空');
        setResult(null);
        return;
      }
      setResult(r);
    } catch (err: unknown) {
      const env = extractPcsError(err);
      const code = env.code ?? '';
      if (code === 'STREAM_NOT_CHECKED') {
        setError('所选流未签出（仅 CHECKED 可计算）');
      } else {
        setError(env.message ?? '计算失败');
      }
      setResult(null);
    } finally {
      setCalculating(false);
    }
  };

  return (
    <div data-testid="sep-equip-compute-page">
      <PageHeader
        title="SEP_EQUIP 分离设备计算"
        module="SEP_EQUIP"
        actions={
          <Button
            type="primary"
            data-testid="sep-equip-calculate"
            onClick={handleCalculate}
            loading={calculating}
          >
            计算
          </Button>
        }
      />

      <Row gutter={16}>
        <Col span={10}>
          <Card title="输入条件" size="small">
            <Form layout="vertical">
              <Form.Item label="物流" required>
                <Select
                  data-testid="sep-equip-stream-select"
                  placeholder={streamsLoading ? '加载物流中…' : '选择 CHECKED 物流'}
                  value={streamId}
                  onChange={setStreamId}
                  loading={streamsLoading}
                  disabled={streamsLoading}
                  options={checkedStreams.map((s) => ({
                    value: s.stream_id,
                    label: s.tag_number,
                  }))}
                />
              </Form.Item>

              <Form.Item label="设备类型">
                <Radio.Group
                  data-testid="sep-equip-device-type"
                  value={device}
                  onChange={(e) => onDeviceChange(e.target.value as SepEquipDeviceType)}
                >
                  <Space direction="vertical">
                    {DEVICE_OPTIONS.map((o) => (
                      <Radio key={o.value} value={o.value}>
                        {o.label}
                      </Radio>
                    ))}
                  </Space>
                </Radio.Group>
              </Form.Item>

              <DeviceParamsFields
                device={device}
                params={params}
                onChange={setParams}
              />
            </Form>
          </Card>
        </Col>

        <Col span={14}>
          <Card title="结果" size="small" data-testid="sep-equip-result-card">
            <Spin spinning={calculating}>
              {error && (
                <Alert
                  type="error"
                  message={error}
                  data-testid="sep-equip-error"
                  style={{ marginBottom: 12 }}
                />
              )}
              {!result && !error && (
                <Typography.Text type="secondary">点击「计算」开始</Typography.Text>
              )}
              {result && (
                <Descriptions
                  size="small"
                  column={1}
                  data-testid="sep-equip-result-table"
                >
                  {Object.entries(result.result).map(([k, v]) => (
                    <Descriptions.Item key={k} label={k}>
                      {renderResultValue(v)}
                    </Descriptions.Item>
                  ))}
                </Descriptions>
              )}
            </Spin>
          </Card>
        </Col>
      </Row>
    </div>
  );
}

interface DeviceParamsFieldsProps {
  device: SepEquipDeviceType;
  params: CycloneParams | MistEliminatorParams | GravitySeparatorParams;
  onChange: (
    p: CycloneParams | MistEliminatorParams | GravitySeparatorParams,
  ) => void;
}

function DeviceParamsFields({
  device,
  params,
  onChange,
}: DeviceParamsFieldsProps): JSX.Element {
  if (device === 'CYCLONE') {
    const p = params as CycloneParams;
    return (
      <Space direction="vertical" style={{ width: '100%' }}>
        <NumberField
          label="D_cylinder (m)"
          value={p.D_cylinder_m}
          onChange={(v) => onChange({ ...p, D_cylinder_m: v ?? 0 })}
        />
        <NumberField
          label="D_exhaust (m)"
          value={p.D_exhaust_m}
          onChange={(v) => onChange({ ...p, D_exhaust_m: v ?? 0 })}
        />
        <NumberField
          label="a_inlet (m)"
          value={p.a_inlet_m}
          onChange={(v) => onChange({ ...p, a_inlet_m: v ?? 0 })}
        />
        <NumberField
          label="b_inlet (m)"
          value={p.b_inlet_m}
          onChange={(v) => onChange({ ...p, b_inlet_m: v ?? 0 })}
        />
        <NumberField
          label="V_in (m/s)"
          value={p.V_in_ms}
          onChange={(v) => onChange({ ...p, V_in_ms: v ?? 0 })}
        />
        <NumberField
          label="ρ (kg/m³)"
          value={p.rho_kg_m3}
          onChange={(v) => onChange({ ...p, rho_kg_m3: v ?? 0 })}
        />
        <NumberField
          label="μ (Pa·s)"
          step={1e-6}
          value={p.mu_pa_s}
          onChange={(v) => onChange({ ...p, mu_pa_s: v ?? 0 })}
        />
        <NumberField
          label="ρ_p (kg/m³)"
          value={p.rho_particle_kg_m3}
          onChange={(v) => onChange({ ...p, rho_particle_kg_m3: v ?? 0 })}
        />
        <NumberField
          label="N_turns"
          value={p.N_effective_turns}
          onChange={(v) => onChange({ ...p, N_effective_turns: v ?? 0 })}
        />
        <Form.Item label="方法">
          <Radio.Group
            data-testid="sep-equip-cyclone-method"
            value={p.method}
            onChange={(e) =>
              onChange({ ...p, method: e.target.value as CycloneParams['method'] })
            }
          >
            <Radio value="LAPPLE">Lapple (GPSA)</Radio>
            <Radio value="SWIFT">Swift</Radio>
            <Radio value="BARTH">Barth</Radio>
          </Radio.Group>
        </Form.Item>
      </Space>
    );
  }
  if (device === 'MIST_ELIMINATOR') {
    const p = params as MistEliminatorParams;
    return (
      <Space direction="vertical" style={{ width: '100%' }}>
        <Form.Item label="垫层类型">
          <Radio.Group
            data-testid="sep-equip-mist-pad-type"
            value={p.pad_type}
            onChange={(e) =>
              onChange({ ...p, pad_type: e.target.value as MistEliminatorParams['pad_type'] })
            }
          >
            <Radio value="STANDARD">STANDARD</Radio>
            <Radio value="HIGH_EFFICIENCY">HIGH_EFFICIENCY</Radio>
          </Radio.Group>
        </Form.Item>
        <NumberField
          label="Q_gas (m³/s)"
          value={p.Q_gas_m3_s}
          onChange={(v) => onChange({ ...p, Q_gas_m3_s: v ?? 0 })}
        />
        <NumberField
          label="D_cylinder (m)"
          value={p.D_cylinder_m}
          onChange={(v) => onChange({ ...p, D_cylinder_m: v ?? 0 })}
        />
        <NumberField
          label="ρ_gas (kg/m³)"
          value={p.rho_gas_kg_m3}
          onChange={(v) => onChange({ ...p, rho_gas_kg_m3: v ?? 0 })}
        />
        <NumberField
          label="μ_gas (Pa·s)"
          step={1e-6}
          value={p.mu_gas_pa_s}
          onChange={(v) => onChange({ ...p, mu_gas_pa_s: v ?? 0 })}
        />
        <NumberField
          label="liquid_load (kg/m³)"
          value={p.liquid_load_kg_m3}
          onChange={(v) => onChange({ ...p, liquid_load_kg_m3: v ?? 0 })}
        />
      </Space>
    );
  }
  // GRAVITY / VANE / FIBER share GravitySeparatorParams
  const p = params as GravitySeparatorParams;
  return (
    <Space direction="vertical" style={{ width: '100%' }}>
      <NumberField
        label="d_particle (m)"
        step={1e-6}
        value={p.d_particle_m}
        onChange={(v) => onChange({ ...p, d_particle_m: v ?? 0 })}
      />
      <NumberField
        label="ρ_p (kg/m³)"
        value={p.rho_particle_kg_m3}
        onChange={(v) => onChange({ ...p, rho_particle_kg_m3: v ?? 0 })}
      />
      <NumberField
        label="ρ_fluid (kg/m³)"
        value={p.rho_fluid_kg_m3}
        onChange={(v) => onChange({ ...p, rho_fluid_kg_m3: v ?? 0 })}
      />
      <NumberField
        label="μ_fluid (Pa·s)"
        step={1e-6}
        value={p.mu_fluid_pa_s}
        onChange={(v) => onChange({ ...p, mu_fluid_pa_s: v ?? 0 })}
      />
      <NumberField
        label="H_set (m)"
        value={p.height_setting_m}
        onChange={(v) => onChange({ ...p, height_setting_m: v ?? 0 })}
      />
      <NumberField
        label="V_h (m/s)"
        step={0.01}
        value={p.horizontal_velocity_ms}
        onChange={(v) => onChange({ ...p, horizontal_velocity_ms: v ?? 0 })}
      />
    </Space>
  );
}

interface NumberFieldProps {
  label: string;
  value: number;
  step?: number;
  onChange: (v: number | null) => void;
}

function NumberField({
  label,
  value,
  step,
  onChange,
}: NumberFieldProps): JSX.Element {
  return (
    <Form.Item label={label} style={{ marginBottom: 8 }}>
      <InputNumber
        value={value}
        step={step}
        style={{ width: '100%' }}
        onChange={onChange}
      />
    </Form.Item>
  );
}

function renderResultValue(v: unknown): JSX.Element {
  if (typeof v === 'number') return <span>{v.toPrecision(4)}</span>;
  if (typeof v === 'string') {
    if (
      v === 'STOKES' ||
      v === 'INTERMEDIATE' ||
      v === 'NEWTON' ||
      v === 'PLAIN' ||
      v === 'VANE' ||
      v === 'FIBER'
    ) {
      return <Tag color="blue">{v}</Tag>;
    }
    return <span>{v}</span>;
  }
  if (typeof v === 'boolean') {
    return v ? <Tag color="green">true</Tag> : <Tag color="default">false</Tag>;
  }
  return <span>{String(v)}</span>;
}

export default SepEquipComputePage;