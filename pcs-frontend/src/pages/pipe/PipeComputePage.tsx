/**
 * PipeComputePage — PIPE 计算界面（P45-3-5 / Task 32）。
 *
 * SPEC §7.11.2：
 * - 输入分组：物流 / 管道 / 管件 / 设计条件 / 等级 / 绝热 / 其他
 * - 结果 Tab：管径 / 壁厚 / 压降 / 流速 + 两相流子表
 * - 写回状态点按钮
 *
 * Props：
 *   pipeClasses: { pipe_class_id: string; code: string }[]   // 等级下拉
 *   streams: { stream_id: string; tag_number: string; sign_status: string }[]
 *   onCalculate?: (input: PipeInput) => PipeResult | undefined
 *   onWriteBack?: (input: PipeInput, result: PipeResult) => void
 *
 * V1：默认 in-memory mock 计算（恒等/常量）；P5-1 后由真实 calculate 端点替换。
 */
import { useState } from 'react';
import {
  Alert,
  Button,
  Card,
  Checkbox,
  Col,
  Descriptions,
  Form,
  Input,
  InputNumber,
  Row,
  Select,
  Space,
  Statistic,
  Tabs,
  Tag,
  Typography,
} from 'antd';

import { PageHeader } from '../../components/common/PageHeader';
import { STREAM_PHASE_LABEL, type Stream } from '../../types/stream';
import type {
  PipeInput,
  PipeResult,
  TwoPhasePattern,
} from '../../types/pipe';

interface PipeClassLite {
  pipe_class_id: string;
  code: string;
}

interface StreamLite {
  stream_id: string;
  tag_number: string;
  sign_status: string;
  phase?: Stream['phase'];
}

interface Props {
  pipeClasses: PipeClassLite[];
  streams: StreamLite[];
  onCalculate?: (input: PipeInput) => PipeResult | undefined;
  onWriteBack?: (input: PipeInput, result: PipeResult) => void;
}

const FLOW_PATTERN_LABEL: Record<TwoPhasePattern, string> = {
  STRATIFIED: '分层流',
  WAVE: '波浪流',
  ANNULAR: '环状流',
  SLUG: '段塞流',
  MIST: '雾状流',
  NONE: '单相',
};

function defaultMockResult(input: PipeInput): PipeResult {
  const baseDiameter = Math.max(50, Math.sqrt(input.allowable_dp_kpa) * 10);
  const isTwoPhase = (input.design_temperature_c > 200) && (input.length_m > 100);
  return {
    diameter_mm: Math.round(baseDiameter),
    wall_thickness_mm: 6.0,
    dp_kpa: input.allowable_dp_kpa * 0.85,
    velocity_m_s: 1.8,
    flow_pattern: isTwoPhase ? 'ANNULAR' : 'NONE',
    two_phase: isTwoPhase ? { pattern: 'ANNULAR', liquid_holdup: 0.4 } : undefined,
  };
}

export function PipeComputePage({
  pipeClasses,
  streams,
  onCalculate,
  onWriteBack,
}: Props): JSX.Element {
  const [input, setInput] = useState<Partial<PipeInput>>({
    roughness_mm: 0.046,
    fittings: [],
    pipe_class_id: pipeClasses[0]?.pipe_class_id,
  });
  const [result, setResult] = useState<PipeResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const checkedStreams = streams.filter((s) => s.sign_status === 'CHECKED');

  const handleCalculate = () => {
    if (!input.stream_id || !input.pipe_no) {
      setError('请选择物流并填写管道号');
      return;
    }
    setError(null);
    const finalInput = input as PipeInput;
    try {
      const r = onCalculate ? onCalculate(finalInput) : defaultMockResult(finalInput);
      if (!r) {
        setError('计算失败：返回空');
        setResult(null);
        return;
      }
      setResult(r);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : '未知错误');
      setResult(null);
    }
  };

  const handleWriteBack = () => {
    if (!result) return;
    onWriteBack?.(input as PipeInput, result);
  };

  return (
    <div data-testid="pipe-compute-page">
      <PageHeader
        title="PIPE 计算"
        module="PIPE"
        actions={
          <Space>
            <Button data-testid="pipe-calculate" onClick={handleCalculate}>
              计算
            </Button>
            <Button
              type="primary"
              data-testid="pipe-writeback"
              disabled={!result}
              onClick={handleWriteBack}
            >
              写回状态点
            </Button>
          </Space>
        }
      />

      <Row gutter={16}>
        <Col span={12}>
          <Card title="输入条件" size="small">
            {error && (
              <Alert
                type="error"
                message={error}
                data-testid="pipe-error"
                style={{ marginBottom: 12 }}
              />
            )}
            <Tabs
              data-testid="pipe-input-tabs"
              defaultActiveKey="stream"
              items={[
                {
                  key: 'stream',
                  label: <span data-testid="pipe-input-tab-stream">物流</span>,
                  children: (
                    <Form layout="vertical">
                      <Form.Item label="物流" required>
                        <Select
                          data-testid="pipe-stream-select"
                          placeholder="选择 CHECKED 物流"
                          value={input.stream_id}
                          onChange={(v) => setInput((s) => ({ ...s, stream_id: v }))}
                          options={checkedStreams.map((s) => ({
                            value: s.stream_id,
                            label: `${s.tag_number}${s.phase ? ` (${STREAM_PHASE_LABEL[s.phase]})` : ''}`,
                          }))}
                        />
                      </Form.Item>
                      <Form.Item label="管道号" required>
                        <Input
                          data-testid="pipe-no-input"
                          value={input.pipe_no ?? ''}
                          onChange={(e) => setInput((s) => ({ ...s, pipe_no: e.target.value }))}
                          placeholder="如 P-101-A"
                        />
                      </Form.Item>
                      <Form.Item label="起点">
                        <Input
                          data-testid="pipe-start"
                          value={input.start_point ?? ''}
                          onChange={(e) => setInput((s) => ({ ...s, start_point: e.target.value }))}
                        />
                      </Form.Item>
                      <Form.Item label="终点">
                        <Input
                          data-testid="pipe-end"
                          value={input.end_point ?? ''}
                          onChange={(e) => setInput((s) => ({ ...s, end_point: e.target.value }))}
                        />
                      </Form.Item>
                      <Form.Item label="P&ID 参考">
                        <Input
                          data-testid="pipe-pid-ref"
                          value={input.pid_ref ?? ''}
                          onChange={(e) => setInput((s) => ({ ...s, pid_ref: e.target.value }))}
                        />
                      </Form.Item>
                    </Form>
                  ),
                },
                {
                  key: 'geometry',
                  label: <span data-testid="pipe-input-tab-geometry">几何</span>,
                  children: (
                    <Form layout="vertical">
                      <Form.Item label="长度 (m)">
                        <InputNumber
                          data-testid="pipe-length"
                          value={input.length_m}
                          onChange={(v) => setInput((s) => ({ ...s, length_m: v ?? undefined }))}
                        />
                      </Form.Item>
                      <Form.Item label="粗糙度 (mm)">
                        <InputNumber
                          data-testid="pipe-roughness"
                          value={input.roughness_mm ?? 0.046}
                          step={0.001}
                          onChange={(v) => setInput((s) => ({ ...s, roughness_mm: v ?? 0.046 }))}
                        />
                      </Form.Item>
                      <Form.Item label="许用压降 (kPa)">
                        <InputNumber
                          data-testid="pipe-allowable-dp"
                          value={input.allowable_dp_kpa}
                          onChange={(v) => setInput((s) => ({ ...s, allowable_dp_kpa: v ?? undefined }))}
                        />
                      </Form.Item>
                    </Form>
                  ),
                },
                {
                  key: 'design',
                  label: <span data-testid="pipe-input-tab-design">设计条件</span>,
                  children: (
                    <Form layout="vertical">
                      <Form.Item label="设计压力 (MPa)">
                        <InputNumber
                          data-testid="pipe-design-p"
                          value={input.design_pressure_mpa}
                          onChange={(v) => setInput((s) => ({ ...s, design_pressure_mpa: v ?? undefined }))}
                        />
                      </Form.Item>
                      <Form.Item label="设计温度 (°C)">
                        <InputNumber
                          data-testid="pipe-design-t"
                          value={input.design_temperature_c}
                          onChange={(v) => setInput((s) => ({ ...s, design_temperature_c: v ?? undefined }))}
                        />
                      </Form.Item>
                      <Form.Item label="腐蚀余量 (mm)">
                        <InputNumber
                          data-testid="pipe-corrosion"
                          value={input.corrosion_allowance_mm}
                          step={0.5}
                          onChange={(v) => setInput((s) => ({ ...s, corrosion_allowance_mm: v ?? undefined }))}
                        />
                      </Form.Item>
                      <Form.Item label="管道等级">
                        <Select
                          data-testid="pipe-class-select"
                          value={input.pipe_class_id}
                          onChange={(v) => setInput((s) => ({ ...s, pipe_class_id: v }))}
                          options={pipeClasses.map((p) => ({ value: p.pipe_class_id, label: p.code }))}
                        />
                      </Form.Item>
                    </Form>
                  ),
                },
                {
                  key: 'insulation',
                  label: <span data-testid="pipe-input-tab-insulation">绝热 / 伴热</span>,
                  children: (
                    <Form layout="vertical">
                      <Form.Item label="绝热代号">
                        <Input
                          data-testid="pipe-insulation-code"
                          value={input.insulation_code ?? ''}
                          onChange={(e) => setInput((s) => ({ ...s, insulation_code: e.target.value }))}
                        />
                      </Form.Item>
                      <Form.Item label="绝热厚度 (mm)">
                        <InputNumber
                          data-testid="pipe-insulation-thickness"
                          value={input.insulation_thickness_mm}
                          onChange={(v) => setInput((s) => ({ ...s, insulation_thickness_mm: v ?? undefined }))}
                        />
                      </Form.Item>
                      <Form.Item>
                        <Checkbox
                          data-testid="pipe-heat-trace"
                          checked={!!input.heat_trace}
                          onChange={(e) => setInput((s) => ({ ...s, heat_trace: e.target.checked }))}
                        >
                          伴热
                        </Checkbox>
                      </Form.Item>
                    </Form>
                  ),
                },
              ]}
            />
          </Card>
        </Col>

        <Col span={12}>
          <Card title="结果" size="small" data-testid="pipe-result-card">
            {!result && !error && (
              <Typography.Text type="secondary">点击「计算」开始</Typography.Text>
            )}
            {result && (
              <Space direction="vertical" size={16} style={{ width: '100%' }}>
                <Row gutter={16}>
                  <Col span={8}>
                    <Statistic
                      title="管径 (mm)"
                      value={result.diameter_mm}
                      data-testid="pipe-result-diameter"
                    />
                  </Col>
                  <Col span={8}>
                    <Statistic
                      title="壁厚 (mm)"
                      value={result.wall_thickness_mm}
                      precision={2}
                    />
                  </Col>
                  <Col span={8}>
                    <Statistic
                      title="流速 (m/s)"
                      value={result.velocity_m_s}
                      precision={2}
                    />
                  </Col>
                </Row>

                <Descriptions size="small" column={1}>
                  <Descriptions.Item label="压降 (kPa)">
                    {result.dp_kpa.toFixed(2)}
                  </Descriptions.Item>
                  <Descriptions.Item label="流型">
                    <Tag color={result.flow_pattern === 'NONE' ? 'blue' : 'orange'}>
                      {FLOW_PATTERN_LABEL[result.flow_pattern]}
                    </Tag>
                  </Descriptions.Item>
                </Descriptions>

                {result.two_phase && (
                  <Card
                    size="small"
                    title="两相流"
                    data-testid="pipe-result-twophase"
                  >
                    <Descriptions size="small" column={1}>
                      <Descriptions.Item label="流型">
                        {FLOW_PATTERN_LABEL[result.two_phase.pattern]}
                      </Descriptions.Item>
                      <Descriptions.Item label="持液率">
                        {result.two_phase.liquid_holdup.toFixed(3)}
                      </Descriptions.Item>
                    </Descriptions>
                  </Card>
                )}
              </Space>
            )}
          </Card>
        </Col>
      </Row>
    </div>
  );
}

export default PipeComputePage;