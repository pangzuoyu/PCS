/**
 * CV 控制阀 Cv 计算页（P6-5 前端补课 / 3 计算页之三）。
 *
 * SPEC §7.12 设备计算统一页面模式 + OpenAPI：
 * - POST /api/v1/cv/calculate（IEC 60534-2-1 Cv + P6-4 C-24 Masonelian fl）
 * - 输入：phase 分支（LIQUID：SG/ρ + dP_bar + Pv/Pc；GAS：M/Z/γ + dP_pa + xT）
 *   + project_id/workspace_id（PROJECT_ID 同源占位，与 HeatComputePage 同模式）
 *   + source_stream_id（CHECKED 物流锚点）
 * - 输出：Cv_calculated/Cv_selected + choked/cavitation/flashing + 噪音 +
 *   P6-4 三新字段（fl / flash_steam_rate_kg_s / masonelian_model，仅 LIQUID 填充）
 *
 * 页面模式与 VesselComputePage 同源：PageHeader + 输入 Card + 结果 Card +
 * streamApi 自取物流列表 + extractPcsError envelope 解析。
 */
import { useEffect, useState } from 'react';
import {
  Button,
  Card,
  Col,
  Form,
  InputNumber,
  Row,
  Select,
  Statistic,
  Tag,
  Typography,
} from 'antd';

import { PageHeader } from '../../components/common/PageHeader';
import { cvApi } from '../../api/cv';
import { PROJECT_ID } from '../../constants/env';
import { streamApi } from '../../api/stream';
import type {
  CvCalculateRequest,
  CvCalculateResponse,
  CvFluidPhase,
} from '../../types/cv';

/**后端 PcsError envelope 解析（与 VesselComputePage 同模式）。*/
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

/**安全数值化（NaN 兜底，与 VesselComputePage coerceNum 同模式）。*/
function coerceNum(v: unknown, fallback = 0): number {
  const n = typeof v === 'number' ? v : parseFloat(String(v ?? ''));
  return Number.isFinite(n) ? n : fallback;
}

interface StreamLite {
  stream_id: string;
  tag_number: string;
}

interface Props {
  /**可选：测试注入；未注入则走 cvApi。*/
  onCalculate?: (req: CvCalculateRequest) => CvCalculateResponse | undefined;
  /**可选：测试注入物流列表；未注入则走 streamApi。*/
  streams?: StreamLite[];
}

const PHASE_OPTIONS: { value: CvFluidPhase; label: string }[] = [
  { value: 'LIQUID', label: '液体 LIQUID' },
  { value: 'GAS', label: '气体 GAS' },
  { value: 'TWO_PHASE', label: '两相流 TWO_PHASE' },
];

function NumberField({
  label,
  testId,
  value,
  step = 1,
  min,
  onChange,
}: {
  label: string;
  testId: string;
  value: number;
  step?: number;
  min?: number;
  onChange: (v: number) => void;
}): JSX.Element {
  return (
    <Form.Item label={label} style={{ marginBottom: 8 }}>
      <InputNumber
        data-testid={testId}
        value={value}
        step={step}
        min={min}
        style={{ width: '100%' }}
        onChange={(v) => onChange(v ?? 0)}
      />
    </Form.Item>
  );
}

function BoolTag({ value, label }: { value: boolean; label: string }): JSX.Element {
  return value ? <Tag color="red">{label}</Tag> : <Tag>{label} 否</Tag>;
}

export function CvComputePage({ onCalculate: onCalculateProp, streams: streamsProp }: Props): JSX.Element {
  const [streamId, setStreamId] = useState<string | undefined>();
  const [fetchedStreams, setFetchedStreams] = useState<StreamLite[] | null>(null);
  const [phase, setPhase] = useState<CvFluidPhase>('LIQUID');

  const [qM3h, setQM3h] = useState(10);
  const [p1Pa, setP1Pa] = useState(600000);
  const [p2Pa, setP2Pa] = useState(400000);
  const [t1K, setT1K] = useState(293.15);

  // LIQUID 分支
  const [sg, setSg] = useState(0.8);
  const [dpBar, setDpBar] = useState(2);
  const [pvPa, setPvPa] = useState(2500);
  const [pcPa, setPcPa] = useState(22048320);
  const [fl, setFl] = useState(0.9);

  // GAS 分支
  const [m, setM] = useState(16.04);
  const [z, setZ] = useState(0.95);
  const [gamma, setGamma] = useState(1.3);
  const [dpPa, setDpPa] = useState(200000);
  const [xT, setXT] = useState(0.7);

  const [result, setResult] = useState<CvCalculateResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [calculating, setCalculating] = useState(false);

  useEffect(() => {
    if (streamsProp !== undefined) return;
    let cancelled = false;
    streamApi
      .listByProject(PROJECT_ID)
      .then((list) => {
        if (cancelled) return;
        setFetchedStreams(list.map((s) => ({ stream_id: s.stream_id, tag_number: s.tag_number })));
      })
      .catch(() => {
        if (!cancelled) setFetchedStreams([]);
      });
    return () => {
      cancelled = true;
    };
  }, [streamsProp]);

  const streams = streamsProp ?? fetchedStreams ?? [];

  const handleCalculate = async () => {
    if (!streamId) {
      setError('请选择源物流');
      return;
    }
    setError(null);
    setCalculating(true);
    const req: CvCalculateRequest = {
      project_id: PROJECT_ID,
      // HEAT-WORKSPACE-ID-INCORRECT 同模式：mock 阶段 PROJECT_ID 同源占位
      workspace_id: PROJECT_ID,
      design_stage: 'BASIC',
      standard_profile_code: 'IEC_60534',
      fluid_phase: phase,
      Q_m3h: qM3h,
      P1_pa: p1Pa,
      P2_pa: p2Pa,
      T1_k: t1K,
      source_stream_id: streamId,
      ...(phase === 'LIQUID' || phase === 'TWO_PHASE'
        ? { SG: sg, dP_bar: dpBar, Pv: pvPa, Pc: pcPa, FL: fl, FF: 0.96, xT: null }
        : { M: m, Z: z, gamma, dP_pa: dpPa, xT, FL: null, FF: null }),
    };
    try {
      const r = onCalculateProp ? onCalculateProp(req) : await cvApi.calculate(req);
      if (!r) {
        setError('计算失败：返回空');
        setResult(null);
        return;
      }
      setResult(r);
    } catch (err: unknown) {
      const env = extractPcsError(err);
      setError(env.message ?? '计算失败');
      setResult(null);
    } finally {
      setCalculating(false);
    }
  };

  return (
    <div data-testid="cv-compute-page">
      <PageHeader
        title="CV 控制阀计算"
        actions={
          <Button
            type="primary"
            data-testid="cv-calculate"
            onClick={handleCalculate}
            loading={calculating}
          >
            计算
          </Button>
        }
      />

      <Row gutter={16}>
        <Col span={10}>
          <Card title="输入条件（IEC 60534-2-1 + C-24 Masonelian fl）" size="small">
            <Form layout="vertical">
              <Form.Item label="源物流（outlet.upstream_stream_id 锚点）" required>
                <Select
                  data-testid="cv-stream-select"
                  placeholder="选择物流"
                  value={streamId}
                  onChange={setStreamId}
                  options={streams.map((s) => ({
                    value: s.stream_id,
                    label: s.tag_number,
                  }))}
                />
              </Form.Item>
              <Form.Item label="流体相态" required>
                <Select
                  data-testid="cv-phase-select"
                  value={phase}
                  onChange={(v) => setPhase(v)}
                  options={PHASE_OPTIONS}
                />
              </Form.Item>
              <NumberField label="体积流量 Q（m³/h）" testId="cv-q" value={qM3h} step={1} min={0} onChange={setQM3h} />
              <NumberField label="阀前绝压 P1（Pa）" testId="cv-p1" value={p1Pa} step={10000} min={0} onChange={setP1Pa} />
              <NumberField label="阀后绝压 P2（Pa）" testId="cv-p2" value={p2Pa} step={10000} min={0} onChange={setP2Pa} />
              <NumberField label="入口温度 T1（K）" testId="cv-t1" value={t1K} step={1} min={0} onChange={setT1K} />

              {(phase === 'LIQUID' || phase === 'TWO_PHASE') && (
                <div data-testid="cv-liquid-fields">
                  <Typography.Title level={5} style={{ marginTop: 8 }}>
                    液相分支（LIQUID）
                  </Typography.Title>
                  <NumberField label="相对密度 SG（ρ/1000）" testId="cv-sg" value={sg} step={0.05} min={0} onChange={setSg} />
                  <NumberField label="压差 dP（bar）" testId="cv-dp-bar" value={dpBar} step={0.1} min={0} onChange={setDpBar} />
                  <NumberField label="蒸汽压 Pv（Pa，阻塞判定）" testId="cv-pv" value={pvPa} step={100} min={0} onChange={setPvPa} />
                  <NumberField label="临界压力 Pc（Pa，阻塞判定）" testId="cv-pc" value={pcPa} step={100000} min={0} onChange={setPcPa} />
                  <NumberField label="FL 压力恢复系数（默认 0.9）" testId="cv-fl" value={fl} step={0.05} min={0} onChange={setFl} />
                </div>
              )}

              {phase === 'GAS' && (
                <div data-testid="cv-gas-fields">
                  <Typography.Title level={5} style={{ marginTop: 8 }}>
                    气相分支（GAS）
                  </Typography.Title>
                  <NumberField label="分子量 M（kg/kmol）" testId="cv-m" value={m} step={0.5} min={0} onChange={setM} />
                  <NumberField label="压缩因子 Z" testId="cv-z" value={z} step={0.01} min={0} onChange={setZ} />
                  <NumberField label="绝热指数 γ（Cp/Cv）" testId="cv-gamma" value={gamma} step={0.05} min={0} onChange={setGamma} />
                  <NumberField label="压差 dP（Pa）" testId="cv-dp-pa" value={dpPa} step={10000} min={0} onChange={setDpPa} />
                  <NumberField label="临界压差比 xT（典型 0.4~0.8）" testId="cv-xt" value={xT} step={0.05} min={0} onChange={setXT} />
                </div>
              )}
            </Form>
          </Card>
        </Col>

        <Col span={14}>
          <Card title="结果" size="small" data-testid="cv-result-card">
            {error && (
              <Typography.Text type="danger" data-testid="cv-error">
                {error}
              </Typography.Text>
            )}
            {result ? (
              <>
                <Row gutter={16}>
                  <Col span={6}>
                    <Statistic title="计算 Cv" value={coerceNum(result.Cv_calculated)} precision={3} />
                  </Col>
                  <Col span={6}>
                    <Statistic
                      title="选定 Cv（标准系列）"
                      value={result.Cv_selected != null ? coerceNum(result.Cv_selected) : '—'}
                      precision={3}
                    />
                  </Col>
                  <Col span={6}>
                    <Statistic
                      title="噪音（dB(A)，IEC 60534-8-3）"
                      value={result.noise_sil_db != null ? coerceNum(result.noise_sil_db) : '—'}
                      precision={1}
                    />
                  </Col>
                  <Col span={6}>
                    <div style={{ paddingTop: 12 }}>
                      <BoolTag value={result.choked} label="阻塞流" />
                      <BoolTag value={result.cavitation} label="空化" />
                      <BoolTag value={result.flashing} label="闪蒸" />
                    </div>
                  </Col>
                </Row>

                <Typography.Title level={5} style={{ marginTop: 16 }}>
                  P6-4 Masonelian fl（C-24；仅 LIQUID 路径填充）
                </Typography.Title>
                <Row gutter={16}>
                  <Col span={8}>
                    <Statistic
                      title="Masonelian fl 修正系数"
                      value={result.fl != null ? coerceNum(result.fl) : '—'}
                      precision={4}
                    />
                  </Col>
                  <Col span={8}>
                    <Statistic
                      title="闪蒸蒸汽量（kg/s）"
                      value={
                        result.flash_steam_rate_kg_s != null
                          ? coerceNum(result.flash_steam_rate_kg_s)
                          : '—'
                      }
                      precision={6}
                    />
                  </Col>
                  <Col span={8}>
                    <div style={{ paddingTop: 12 }}>
                      <Tag data-testid="cv-masonelian-model">
                        {result.masonelian_model ?? 'N/A（GAS 路径无闪蒸修正）'}
                      </Tag>
                    </div>
                  </Col>
                </Row>

                <Typography.Paragraph type="secondary" style={{ marginTop: 12 }}>
                  记录 {result.tag_number} · {result.standard_profile_code} ·{' '}
                  {result.design_stage} · hash {result.record_hash}
                </Typography.Paragraph>
              </>
            ) : (
              !error && (
                <Typography.Text type="secondary">
                  选择物流 + 相态后点击「计算」。
                </Typography.Text>
              )
            )}
          </Card>
        </Col>
      </Row>
    </div>
  );
}

export default CvComputePage;
