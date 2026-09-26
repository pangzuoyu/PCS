/**
 * PSYCHRO 饱和水含量计算页（P6-5 前端补课 / 3 计算页之二）。
 *
 * SPEC §7.12 设备计算统一页面模式 + OpenAPI：
 * - POST /api/v1/psychro/saturation-water-content/calculate（C-17 / ASHRAE RP-1845 CoolProp）
 * - 输入：temperature_c + pressure_kpa + 酸性气 CO₂/H₂S 摩尔分率（可选）+ units
 * - 输出：3 单位饱和水含量 + 越界 warning + ISO 18453 酸性气校正系数
 *
 * 页面模式与 VesselComputePage 同源：PageHeader + 输入 Card + 结果 Card +
 * extractPcsError envelope 解析 + onCalculate 注入（测试用）。
 */
import { useState } from 'react';
import {
  Alert,
  Button,
  Card,
  Col,
  Form,
  InputNumber,
  Row,
  Statistic,
  Tag,
  Typography,
} from 'antd';

import { PageHeader } from '../../components/common/PageHeader';
import { psychroApi } from '../../api/psychro';
import type {
  SaturationWaterContentRequest,
  SaturationWaterContentResponse,
} from '../../types/psychro';

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

interface Props {
  /**可选：父组件注入时优先用（测试注入）；未注入则走 psychroApi。*/
  onCalculate?: (
    req: SaturationWaterContentRequest,
  ) => SaturationWaterContentResponse | undefined;
}

export function SaturationWaterContentPage({
  onCalculate: onCalculateProp,
}: Props): JSX.Element {
  const [temperatureC, setTemperatureC] = useState(25);
  const [pressureKpa, setPressureKpa] = useState(101.325);
  const [co2Frac, setCo2Frac] = useState(0);
  const [h2sFrac, setH2sFrac] = useState(0);
  const [imperial, setImperial] = useState(false);
  const [result, setResult] = useState<SaturationWaterContentResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [calculating, setCalculating] = useState(false);

  const handleCalculate = async () => {
    setError(null);
    setCalculating(true);
    const acidic: Record<string, number> | null =
      co2Frac > 0 || h2sFrac > 0
        ? { ...(co2Frac > 0 ? { CO2: co2Frac } : {}), ...(h2sFrac > 0 ? { H2S: h2sFrac } : {}) }
        : null;
    const req: SaturationWaterContentRequest = {
      temperature_c: temperatureC,
      pressure_kpa: pressureKpa,
      acidic_gas_composition: acidic,
      units: imperial ? 'IMPERIAL' : 'METRIC',
    };
    try {
      const r = onCalculateProp
        ? onCalculateProp(req)
        : await psychroApi.calculateSaturationWaterContent(req);
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
    <div data-testid="saturation-w-page">
      <PageHeader
        title="PSYCHRO 饱和水含量"
        actions={
          <Button
            type="primary"
            data-testid="saturation-w-calculate"
            onClick={handleCalculate}
            loading={calculating}
          >
            计算
          </Button>
        }
      />

      <Row gutter={16}>
        <Col span={10}>
          <Card title="输入条件（C-17 / ASHRAE RP-1845 CoolProp）" size="small">
            <Form layout="vertical">
              <Form.Item label="干球温度（°C；安全范围 -50~100，超界返 WARNING）" required>
                <InputNumber
                  data-testid="saturation-w-temperature"
                  value={temperatureC}
                  step={1}
                  style={{ width: '100%' }}
                  onChange={(v) => setTemperatureC(v ?? 0)}
                />
              </Form.Item>
              <Form.Item label="大气压力（kPa；默认海平面 101.325）" required>
                <InputNumber
                  data-testid="saturation-w-pressure"
                  value={pressureKpa}
                  min={0}
                  step={0.1}
                  style={{ width: '100%' }}
                  onChange={(v) => setPressureKpa(v ?? 0)}
                />
              </Form.Item>
              <Form.Item label="CO₂ 摩尔分率（0 = 不参与酸性气校正）">
                <InputNumber
                  data-testid="saturation-w-co2"
                  value={co2Frac}
                  min={0}
                  max={1}
                  step={0.05}
                  style={{ width: '100%' }}
                  onChange={(v) => setCo2Frac(v ?? 0)}
                />
              </Form.Item>
              <Form.Item label="H₂S 摩尔分率（0 = 不参与酸性气校正）">
                <InputNumber
                  data-testid="saturation-w-h2s"
                  value={h2sFrac}
                  min={0}
                  max={1}
                  step={0.05}
                  style={{ width: '100%' }}
                  onChange={(v) => setH2sFrac(v ?? 0)}
                />
              </Form.Item>
              <Form.Item label="单位制（仅标注，不影响算法）">
                <Row>
                  <Tag.CheckableTag
                    data-testid="saturation-w-unit-metric"
                    checked={!imperial}
                    onChange={() => setImperial(false)}
                  >
                    METRIC 公制
                  </Tag.CheckableTag>
                  <Tag.CheckableTag
                    data-testid="saturation-w-unit-imperial"
                    checked={imperial}
                    onChange={() => setImperial(true)}
                  >
                    IMPERIAL 英制
                  </Tag.CheckableTag>
                </Row>
              </Form.Item>
              <Typography.Text type="secondary">
                酸性气校正在 CO₂+H₂S &gt; 40 mol% 时自动触发（ISO 18453 简式）。
              </Typography.Text>
            </Form>
          </Card>
        </Col>

        <Col span={14}>
          <Card title="结果" size="small" data-testid="saturation-w-result-card">
            {error && (
              <Typography.Text type="danger" data-testid="saturation-w-error">
                {error}
              </Typography.Text>
            )}
            {result ? (
              <>
                {result.temperature_out_of_range && (
                  <Alert
                    type="warning"
                    showIcon
                    data-testid="saturation-w-warning"
                    message={result.warning_message ?? '温度超出安全范围 [-50, 100]°C'}
                    style={{ marginBottom: 12 }}
                  />
                )}
                <Row gutter={16}>
                  <Col span={8}>
                    <Statistic
                      title="饱和 W（kg 水 / kg 干空气）"
                      value={coerceNum(result.saturation_w_kg_kg)}
                      precision={5}
                    />
                  </Col>
                  <Col span={8}>
                    <Statistic
                      title="饱和 W（mg 水 / Sm³ 干空气）"
                      value={coerceNum(result.saturation_w_mg_sm3)}
                      precision={1}
                    />
                  </Col>
                  <Col span={8}>
                    <Statistic
                      title="饱和 W（lb 水 / MMscf 干空气）"
                      value={coerceNum(result.saturation_w_lb_per_mmscf)}
                      precision={2}
                    />
                  </Col>
                </Row>
                <Row gutter={16} style={{ marginTop: 16 }}>
                  <Col span={8}>
                    <Statistic
                      title="计算温度（°C）"
                      value={coerceNum(result.saturation_T_c)}
                      precision={2}
                    />
                  </Col>
                  <Col span={8}>
                    <Statistic
                      title="酸性气校正系数（ISO 18453）"
                      value={coerceNum(result.acidic_gas_correction_factor)}
                      precision={4}
                    />
                  </Col>
                  <Col span={8}>
                    <div style={{ paddingTop: 12 }}>
                      {result.acidic_gas_correction_applied ? (
                        <Tag color="orange">酸性气校正已应用</Tag>
                      ) : (
                        <Tag>无酸性气校正</Tag>
                      )}
                      <Tag>{result.formula_ref}</Tag>
                    </div>
                  </Col>
                </Row>
              </>
            ) : (
              !error && (
                <Typography.Text type="secondary">
                  填写温度 / 压力后点击「计算」。
                </Typography.Text>
              )
            )}
          </Card>
        </Col>
      </Row>
    </div>
  );
}

export default SaturationWaterContentPage;
