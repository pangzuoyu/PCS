/**
 * 物流手动创建向导（SPEC §7.7.3「手工」分支 · P9B-3 · T7）。
 *
 * ## 为什么是独立页（不塞进 `ImportWizardPage`）
 *
 * 「导入」与「新建」是**两种心智**：导入是「拿现成文件喂进来」，新建是
 * 「一条一条填」。混在一起会让那个页面超 800 行上限，且两边的人都不认对方的流程。
 *
 * ## 步骤与顺序（SPEC §7.7.3「手工」分支 · 用户裁决 2）
 *
 * 1 基本信息 → 2 组成 → 3 状态点 → **4 校验 → 5 写入 DRAFT → 6 物性估算 →
 * 7 提交校对**
 *
 * ⚠️ **估算排在写入之后**（估算要 `stream_id`），且**估算失败不阻塞提交校对**
 * （物性估算是**增强**，不是门禁）⇒ 估算失败只提示，用户仍可提交校对。
 * ⚠️ 「写入 DRAFT」成功后**留在向导**（后面还有估算 / 提交两步）⇒ 跳回列表
 * 发生在**提交校对**成功之后。
 * ⚠️ **校验有红项 ⇒ 「写入 DRAFT」禁用**（阻断项必须先处理）。
 *
 * ## 「来源」不暴露
 *
 * 手工新建 ⇒ 来源固定 `MANUAL`（用户裁决 2）⇒ **不**给用户选来源的入口
 * （后端 `StreamBase.source` 省略 ⇒ 默认 MANUAL）。
 */
import { useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Alert, Button, Input, InputNumber, Select, Space, Steps, Table, Typography } from 'antd';

import { streamApi, type StatePointPayload, type StreamCreatePayload } from '../../api/stream';
import { describePcsError } from '../../api/errors';
import { PROJECT_ID } from '../../constants/env';
import {
  STREAM_CASE_TYPE_LABEL,
  STREAM_PHASE_LABEL,
  type Stream,
} from '../../types/stream';

interface Props {
  /** 项目 id（默认取环境常量）。 */
  projectId?: string;
}

const STEPS = [
  '基本信息',
  '组成',
  '状态点',
  '校验',
  '写入 DRAFT',
  '物性估算',
  '提交校对',
] as const;

/** 状态点工况（后端 `StatePointCaseType` 4 值）。 */
const STATE_POINT_CASE_TYPES = [
  { value: 'NORMAL', label: '正常' },
  { value: 'MIN', label: '最小' },
  { value: 'MAX', label: '最大' },
  { value: 'ALTERNATE', label: '可替' },
];

/** 组成行（前端形态：组分名 + CAS + 摩尔分率）。 */
interface CompositionRow {
  key: string;
  name: string;
  cas: string;
  moleFraction: number;
}

/** 状态点行（前端形态）。 */
interface StatePointRow {
  key: string;
  label: string;
  caseType: StatePointPayload['case_type'];
  temp: number;
  press: number;
  phase: Stream['phase'];
  massFlow: number;
  vaporFraction: number | null;
}

let rowSeq = 0;
function nextKey(prefix: string): string {
  rowSeq += 1;
  return `${prefix}-${rowSeq}`;
}

/**
 * 组成摩尔分率合计 —— **与后端同口径**（SPEC §7.7.2）。
 *
 * ⚠️ 值域是 **0~1 的小数**（不是百分数）⇒ 判定 `|合计 − 1| ≤ 0.005`
 * （≡ SPEC 的「100±0.5%」）。
 */
function compositionTotal(rows: CompositionRow[]): number {
  return rows.reduce((acc, r) => acc + (Number.isFinite(r.moleFraction) ? r.moleFraction : 0), 0);
}

export function StreamManualWizardPage({ projectId = PROJECT_ID }: Props): JSX.Element {
  const navigate = useNavigate();
  const [step, setStep] = useState(0);

  // === 基本信息 ===
  const [streamName, setStreamName] = useState('');
  const [description, setDescription] = useState('');
  const [phase, setPhase] = useState<Stream['phase']>('LIQUID');
  const [caseType, setCaseType] = useState<StreamCreatePayload['case_type']>('NORMAL');
  const [dataMode, setDataMode] = useState<StreamCreatePayload['data_mode']>('CHEMICAL');
  const [temp, setTemp] = useState<number | null>(null);
  const [press, setPress] = useState<number | null>(null);
  const [massFlow, setMassFlow] = useState<number | null>(null);

  // === 组成 ===
  const [composition, setComposition] = useState<CompositionRow[]>([]);
  // === 状态点 ===
  const [statePoints, setStatePoints] = useState<StatePointRow[]>([]);

  // === 校验 / 写入 / 估算 / 提交 ===
  const [validation, setValidation] = useState<Awaited<
    ReturnType<typeof streamApi.validate>
  > | null>(null);
  const [createdId, setCreatedId] = useState<string | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [estimateWarning, setEstimateWarning] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const total = useMemo(() => compositionTotal(composition), [composition]);
  // ⚠️ 与后端门禁同口径：合计不在 100±0.5% ⇒ 标红（写入/提交都会被后端拒）。
  const totalOk = Math.abs(total - 1) <= 0.005;

  const payload: StreamCreatePayload = useMemo(
    () => ({
      stream_name: streamName,
      description: description || null,
      case_type: caseType,
      data_mode: dataMode,
      phase,
      temp,
      press,
      mass_flow: massFlow,
      composition_json:
        composition.length === 0
          ? null
          : Object.fromEntries(
              composition
                .filter((r) => r.cas.trim() !== '')
                .map((r) => [r.cas.trim(), r.moleFraction]),
            ),
    }),
    [streamName, description, caseType, dataMode, phase, temp, press, massFlow, composition],
  );

  function addCompositionRow(): void {
    setComposition((prev) => [
      ...prev,
      { key: nextKey('comp'), name: '', cas: '', moleFraction: 0 },
    ]);
  }

  function updateCompositionRow(key: string, patch: Partial<CompositionRow>): void {
    setComposition((prev) => prev.map((r) => (r.key === key ? { ...r, ...patch } : r)));
  }

  function removeCompositionRow(key: string): void {
    setComposition((prev) => prev.filter((r) => r.key !== key));
  }

  function addStatePointRow(): void {
    setStatePoints((prev) => [
      ...prev,
      {
        key: nextKey('sp'),
        label: '',
        caseType: 'NORMAL',
        temp: temp ?? 0,
        press: press ?? 0,
        phase,
        massFlow: massFlow ?? 0,
        vaporFraction: null,
      },
    ]);
  }

  function updateStatePointRow(key: string, patch: Partial<StatePointRow>): void {
    setStatePoints((prev) => prev.map((r) => (r.key === key ? { ...r, ...patch } : r)));
  }

  function removeStatePointRow(key: string): void {
    setStatePoints((prev) => prev.filter((r) => r.key !== key));
  }

  /** 第 4 步：校验（写入前的门禁）。 */
  async function runValidate(): Promise<void> {
    setBusy(true);
    setErrorMsg(null);
    try {
      setValidation(await streamApi.validate(projectId, payload));
    } catch (err) {
      setErrorMsg(describePcsError(err, '校验失败'));
    } finally {
      setBusy(false);
    }
  }

  /** 第 5 步：写入 DRAFT。 */
  async function writeDraft(): Promise<void> {
    setBusy(true);
    setErrorMsg(null);
    try {
      const created = await streamApi.create(projectId, payload);
      setCreatedId(created.stream_id);
      // 状态点要 `stream_id` ⇒ 写入之后才落（失败**只提示**，不阻塞主流程）
      for (const row of statePoints) {
        if (!row.label.trim()) continue;
        try {
          await streamApi.createStatePoint(created.stream_id, {
            state_label: row.label.trim(),
            case_type: row.caseType,
            temp: row.temp,
            press: row.press,
            phase: row.phase ?? 'LIQUID',
            mass_flow: row.massFlow,
            composition_json: payload.composition_json ?? {},
            vapor_fraction: row.vaporFraction,
            source_type: 'MANUAL_ENTRY',
          });
        } catch (err) {
          setErrorMsg(describePcsError(err, '状态点写入失败'));
        }
      }
    } catch (err) {
      setErrorMsg(describePcsError(err, '写入失败'));
    } finally {
      setBusy(false);
    }
  }

  /** 第 6 步：物性估算 —— ⚠️ **失败不阻塞**（提示后仍可提交校对）。 */
  async function estimate(): Promise<void> {
    if (!createdId) return;
    setBusy(true);
    setEstimateWarning(null);
    try {
      const casList = composition
        .map((r) => r.cas.trim())
        .filter((c) => c !== '');
      await streamApi.estimateProperties(createdId, casList);
    } catch (err) {
      // ⚠️ 只提示，**不**清空后续步骤的可用性（估算不是门禁）
      setEstimateWarning(
        `物性估算失败：${describePcsError(err, '（后端未给出原因）')} —— 可继续提交校对`,
      );
    } finally {
      setBusy(false);
    }
  }

  /** 第 7 步：提交校对（DRAFT → IN_APPROVAL）⇒ 成功跳回列表。 */
  async function submitForReview(): Promise<void> {
    if (!createdId) return;
    setBusy(true);
    setErrorMsg(null);
    try {
      await streamApi.submitForReview(createdId);
      navigate('/sim/streams');
    } catch (err) {
      setErrorMsg(describePcsError(err, '提交校对失败'));
    } finally {
      setBusy(false);
    }
  }

  /** ⚠️ 校验有红项 ⇒ 写入按钮禁用（阻断项必须先处理）。 */
  const writeBlocked = validation !== null && validation.valid === false;

  return (
    <div data-testid="stream-wizard-page">
      <Typography.Title level={3}>新建物流（手工）</Typography.Title>

      <Steps
        data-testid="wizard-steps"
        current={step}
        items={STEPS.map((title) => ({ title }))}
        style={{ marginBottom: 24 }}
      />

      {errorMsg && (
        <Alert
          type="error"
          showIcon
          message={errorMsg}
          data-testid="wizard-error"
          style={{ marginBottom: 16 }}
          closable
          onClose={() => setErrorMsg(null)}
        />
      )}

      {/* ---- 1 基本信息 ---- */}
      {step === 0 && (
        <div data-testid="wizard-step-0">
          <Space direction="vertical" style={{ width: '100%' }} size={12}>
            <Input
              data-testid="wizard-name"
              placeholder="物流号（名称）"
              value={streamName}
              onChange={(e) => setStreamName(e.target.value)}
            />
            <Input
              data-testid="wizard-description"
              placeholder="描述"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
            />
            <Space wrap>
              <Select
                data-testid="wizard-phase"
                style={{ width: 120 }}
                value={phase}
                options={Object.entries(STREAM_PHASE_LABEL).map(([value, label]) => ({ value, label }))}
                onChange={(v) => setPhase(v)}
              />
              <Select
                data-testid="wizard-case-type"
                style={{ width: 120 }}
                value={caseType}
                options={Object.entries(STREAM_CASE_TYPE_LABEL).map(([value, label]) => ({ value, label }))}
                onChange={(v) => setCaseType(v)}
              />
              <Select
                data-testid="wizard-data-mode"
                style={{ width: 120 }}
                value={dataMode}
                options={[
                  { value: 'CHEMICAL', label: '化学品' },
                  { value: 'PETROLEUM', label: '石油' },
                  { value: 'SOLID', label: '固体' },
                ]}
                onChange={(v) => setDataMode(v)}
              />
            </Space>
            <Space wrap>
              <InputNumber
                data-testid="wizard-temp"
                placeholder="温度 °C"
                value={temp}
                onChange={(v) => setTemp(v)}
              />
              <InputNumber
                data-testid="wizard-press"
                placeholder="压力 MPaG"
                value={press}
                onChange={(v) => setPress(v)}
              />
              <InputNumber
                data-testid="wizard-mass-flow"
                placeholder="质量流量 kg/h"
                value={massFlow}
                onChange={(v) => setMassFlow(v)}
              />
            </Space>
          </Space>
        </div>
      )}

      {/* ---- 2 组成 ---- */}
      {step === 1 && (
        <div data-testid="wizard-step-1">
          <Table<CompositionRow>
            rowKey="key"
            size="small"
            pagination={false}
            dataSource={composition}
            columns={[
              {
                title: '组分名',
                dataIndex: 'name',
                render: (v: string, row) => (
                  <Input
                    data-testid={`wizard-comp-name-${row.key}`}
                    value={v}
                    onChange={(e) => updateCompositionRow(row.key, { name: e.target.value })}
                  />
                ),
              },
              {
                title: 'CAS 号',
                dataIndex: 'cas',
                render: (v: string, row) => (
                  <Input
                    data-testid={`wizard-comp-cas-${row.key}`}
                    value={v}
                    onChange={(e) => updateCompositionRow(row.key, { cas: e.target.value })}
                  />
                ),
              },
              {
                title: '摩尔分率',
                dataIndex: 'moleFraction',
                render: (v: number, row) => (
                  <InputNumber
                    data-testid={`wizard-comp-frac-${row.key}`}
                    value={v}
                    step={0.01}
                    onChange={(n) => updateCompositionRow(row.key, { moleFraction: n ?? 0 })}
                  />
                ),
              },
              {
                title: '',
                key: 'op',
                render: (_: unknown, row) => (
                  <Button size="small" onClick={() => removeCompositionRow(row.key)}>
                    删除
                  </Button>
                ),
              },
            ]}
          />
          <Space style={{ marginTop: 12 }} wrap>
            <Button data-testid="wizard-comp-add" onClick={addCompositionRow}>
              添加组分
            </Button>
            {/* ⚠️ 底部合计校验（与后端同口径：100±0.5%）*/}
            <span
              data-testid="wizard-comp-total"
              data-ok={String(totalOk)}
              style={{ color: totalOk ? undefined : 'var(--state-stale, #cf1322)' }}
            >
              合计 {(total * 100).toFixed(2)}%（应在 100±0.5%）
            </span>
          </Space>
        </div>
      )}

      {/* ---- 3 状态点 ---- */}
      {step === 2 && (
        <div data-testid="wizard-step-2">
          <Table<StatePointRow>
            rowKey="key"
            size="small"
            pagination={false}
            dataSource={statePoints}
            columns={[
              {
                title: '标签',
                dataIndex: 'label',
                render: (v: string, row) => (
                  <Input
                    data-testid={`wizard-sp-label-${row.key}`}
                    value={v}
                    onChange={(e) => updateStatePointRow(row.key, { label: e.target.value })}
                  />
                ),
              },
              {
                title: '类型',
                dataIndex: 'caseType',
                render: (v: StatePointRow['caseType'], row) => (
                  <Select
                    data-testid={`wizard-sp-case-${row.key}`}
                    style={{ width: 100 }}
                    value={v}
                    options={STATE_POINT_CASE_TYPES}
                    onChange={(x) => updateStatePointRow(row.key, { caseType: x })}
                  />
                ),
              },
              {
                title: '温度 °C',
                dataIndex: 'temp',
                render: (v: number, row) => (
                  <InputNumber
                    data-testid={`wizard-sp-temp-${row.key}`}
                    value={v}
                    onChange={(n) => updateStatePointRow(row.key, { temp: n ?? 0 })}
                  />
                ),
              },
              {
                title: '压力 MPaG',
                dataIndex: 'press',
                render: (v: number, row) => (
                  <InputNumber
                    data-testid={`wizard-sp-press-${row.key}`}
                    value={v}
                    onChange={(n) => updateStatePointRow(row.key, { press: n ?? 0 })}
                  />
                ),
              },
              {
                title: '相态',
                dataIndex: 'phase',
                render: (v: Stream['phase'], row) => (
                  <Select
                    data-testid={`wizard-sp-phase-${row.key}`}
                    style={{ width: 100 }}
                    value={v ?? undefined}
                    options={Object.entries(STREAM_PHASE_LABEL).map(([value, label]) => ({ value, label }))}
                    onChange={(x) => updateStatePointRow(row.key, { phase: x })}
                  />
                ),
              },
              {
                title: '汽化分率',
                dataIndex: 'vaporFraction',
                render: (v: number | null, row) => (
                  <InputNumber
                    data-testid={`wizard-sp-vf-${row.key}`}
                    value={v}
                    step={0.1}
                    onChange={(n) => updateStatePointRow(row.key, { vaporFraction: n })}
                  />
                ),
              },
              {
                title: '',
                key: 'op',
                render: (_: unknown, row) => (
                  <Button size="small" onClick={() => removeStatePointRow(row.key)}>
                    删除
                  </Button>
                ),
              },
            ]}
          />
          <Button style={{ marginTop: 12 }} data-testid="wizard-sp-add" onClick={addStatePointRow}>
            添加状态点
          </Button>
        </div>
      )}

      {/* ---- 4 校验 ---- */}
      {step === 3 && (
        <div data-testid="wizard-step-3">
          <Button data-testid="wizard-validate" loading={busy} onClick={() => void runValidate()}>
            校验
          </Button>
          {validation && (
            <div style={{ marginTop: 12 }}>
              {(validation.blocks ?? []).map((b, i) => (
                <Alert
                  key={`b-${i}`}
                  type="error"
                  showIcon
                  data-testid={`wizard-block-${i}`}
                  data-level="error"
                  message={String(b.message ?? b.code ?? '阻断项')}
                  style={{ marginBottom: 8 }}
                />
              ))}
              {(validation.warnings ?? []).map((w, i) => (
                <Alert
                  key={`w-${i}`}
                  type="warning"
                  showIcon
                  data-testid={`wizard-warning-${i}`}
                  data-level="warning"
                  message={String(w.message ?? w.code ?? '警告项')}
                  style={{ marginBottom: 8 }}
                />
              ))}
              {(validation.infos ?? []).map((n, i) => (
                <Alert
                  key={`i-${i}`}
                  type="info"
                  showIcon
                  data-testid={`wizard-info-${i}`}
                  data-level="info"
                  message={String(n.message ?? n.code ?? '提示项')}
                  style={{ marginBottom: 8 }}
                />
              ))}
            </div>
          )}
        </div>
      )}

      {/* ---- 5 写入 DRAFT ---- */}
      {step === 4 && (
        <div data-testid="wizard-step-4">
          <Button
            data-testid="wizard-write"
            type="primary"
            loading={busy}
            disabled={writeBlocked}
            onClick={() => void writeDraft()}
          >
            写入 DRAFT
          </Button>
          {createdId && (
            <Alert
              type="success"
              showIcon
              data-testid="wizard-write-result"
              message={`已写入 DRAFT：${createdId}`}
              style={{ marginTop: 12 }}
            />
          )}
        </div>
      )}

      {/* ---- 6 物性估算 ---- */}
      {step === 5 && (
        <div data-testid="wizard-step-5">
          <Button data-testid="wizard-estimate" loading={busy} onClick={() => void estimate()}>
            估算物性
          </Button>
          {estimateWarning && (
            <Alert
              type="warning"
              showIcon
              data-testid="wizard-estimate-warning"
              message={estimateWarning}
              style={{ marginTop: 12 }}
            />
          )}
        </div>
      )}

      {/* ---- 7 提交校对 ---- */}
      {step === 6 && (
        <div data-testid="wizard-step-6">
          <Button
            data-testid="wizard-submit"
            type="primary"
            loading={busy}
            disabled={!createdId}
            onClick={() => void submitForReview()}
          >
            提交校对
          </Button>
        </div>
      )}

      <Space style={{ marginTop: 24 }}>
        <Button
          data-testid="wizard-prev"
          disabled={step === 0}
          onClick={() => setStep((s) => Math.max(0, s - 1))}
        >
          上一步
        </Button>
        {step < STEPS.length - 1 && (
          <Button data-testid="wizard-next" type="primary" onClick={() => setStep((s) => s + 1)}>
            下一步
          </Button>
        )}
      </Space>
    </div>
  );
}

export default StreamManualWizardPage;
