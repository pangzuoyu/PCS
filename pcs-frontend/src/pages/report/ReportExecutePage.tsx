/**
 * ReportExecutePage — 执行面板（b11）。
 *
 * 链路：选已发布定义 → 看条件摘要 → `POST .../execute` → **202 + task_id**
 *       → 轮询状态 → 下载。
 *
 * ## ⚠️ 这一页是 P8 唯一需要前后端对齐**时序**的地方
 *
 * 别的页面是对普通 CRUD 的包装；这里是 b7 决策（2026-10-08 审查）带来的
 * 异步契约：10k 行 PDF ≈ 10 CPU-秒，同步跑会阻塞整个 event loop。
 *
 * 由此产生三个**必须**做对、且错了不会报错的地方：
 *
 * 1. **202 不带文件**，只有 `task_id`。页面若在 202 之后就去找文件，
 *    会得到 404 —— 而 202 本身是完全成功的响应。
 * 2. **`task_id` 不是 `report_file_id`**。前者是 ARQ 任务，后者在文件
 *    真正生成后才有。拿 task_id 去查 status 永远 404。
 * 3. **轮询要有上限**。ARQ 的 `keep_result` 默认 3600 秒，1 小时后
 *    Redis 里的结果就没了；无上限轮询会永远转圈，用户看不出是死了
 *    还是只是慢。这里显式设超时并把「超时」与「失败」分开报。
 */
import { useEffect, useRef, useState } from 'react';
import type { JSX } from 'react';
import {
  Alert,
  Button,
  Card,
  Descriptions,
  InputNumber,
  Result,
  Select,
  Space,
  Spin,
  Steps,
  Tag,
  Typography,
  message,
} from 'antd';
import { DownloadOutlined, PlayCircleOutlined } from '@ant-design/icons';
import { useNavigate, useParams } from 'react-router-dom';

import { PageHeader } from '../../components/common/PageHeader';
import { errorMessage, reportBuilderApi } from '../../api/reportBuilder';
import type { ReportDefinitionOut } from '../../api/reportBuilder';
import { fromFilterTree, toFilterTree } from './definitionBody';
import type {
  DefNode,
  FieldNodeOption as ReportBuilderFieldOption,
  FilterNode,
} from './definitionBody';
import { FilterTreeEditor } from './FilterTreeEditor';

/** 轮询间隔（ms）与上限。
 *
 * ⚠️ 上限是**用户体验的边界**，不是后端契约：超过 3 分钟仍无结果时
 * 后端可能还在跑，但继续转圈只会让人以为死了。停了之后文件仍会生成，
 * 用户可在列表页重新发起。
 */
const POLL_INTERVAL_MS = 2000;
const POLL_TIMEOUT_MS = 180_000;

type Phase = 'idle' | 'submitting' | 'polling' | 'done' | 'failed' | 'timeout';

export function ReportExecutePage(): JSX.Element {
  const { defId } = useParams<{ defId: string }>();
  const navigate = useNavigate();

  const [definitions, setDefinitions] = useState<ReportDefinitionOut[]>([]);
  const [selected, setSelected] = useState<string | undefined>(defId);
  const [def, setDef] = useState<ReportDefinitionOut | null>(null);
  const [fields, setFields] = useState<ReportBuilderFieldOption[]>([]);
  const [phase, setPhase] = useState<Phase>('idle');
  const [error, setError] = useState<string | null>(null);
  const [taskId, setTaskId] = useState<string | null>(null);
  const [fileId, setFileId] = useState<string | null>(null);
  const [statusText, setStatusText] = useState<string>('');
  // 临时调整（SPEC §3.2.2(5)）：**不落库**。`null` = 用定义里的原条件。
  // ⚠️ 用户在这里改的东西回不到定义编辑器 —— 所以界面上必须写明，
  // 否则「我调好了」会被理解成「保存了」。
  const [tempFilters, setTempFilters] = useState<FilterNode[] | null>(null);
  const [tempMaxRows, setTempMaxRows] = useState<number | null>(null);

  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const startedAt = useRef<number>(0);
  /**
   * 轮询世代号。每次「开始一次新的执行」或「停轮询」都 +1。
   *
   * ⚠️ **只清 timer 不够**（2026-10-14 修，评审 P1 #7）。`poll` 在自己的
   * async 回调里递归重武装自己，而**清定时器只能拦住「还没触发」的那一个**：
   * 已经 `await executionStatus(id)` 在飞的那一轮，回调恢复后照样会
   * `setStatusText`、再 `poll(oldId)`、并接管 `timer.current`。
   *
   * 后果是页面上同时有两个活循环：最后 resolve 的赢 `fileId`，
   * 下载按钮可能指向**上一轮**的文件。卸载时同理 —— 那个回调会为一个
   * 已经不存在的组件重新武装定时器。
   *
   * 所以回调里每次醒来都先核对世代号，对不上就整个放弃。
   * 一个守卫同时解掉「重跑」与「卸载」两种情况。
   */
  const generation = useRef(0);

  const stopPolling = () => {
    // ⚠️ 先作废在飞的回调，再清定时器 —— 顺序反过来会有一个窗口：
    // 回调醒来核对世代号时还没作废，随后又把 timer 装回来。
    generation.current += 1;
    if (timer.current) { clearTimeout(timer.current); timer.current = null; }
  };
  useEffect(() => stopPolling, []);

  useEffect(() => {
    void (async () => {
      try {
        const ds = await reportBuilderApi.datasources();
        setFields(ds.datasources.flatMap((d) => d.fields.map((f) => ({
          value: f.name, source: d.key,
          label: `${d.label} · ${f.label ?? f.name}`,
        }))));
        const data = await reportBuilderApi.list({ status: 'PUBLISHED' });
        setDefinitions(data.items);
        const pick = defId ?? data.items[0]?.def_id;
        if (pick) setSelected(pick);
      } catch (err) { setError(errorMessage(err)); }
    })();
  }, [defId]);

  useEffect(() => {
    if (!selected) { setDef(null); return; }
    void (async () => {
      try { setDef(await reportBuilderApi.get(selected)); }
      catch (err) { setError(errorMessage(err)); }
    })();
  }, [selected]);

  const run = async () => {
    if (!selected) { message.warning('先选一个已发布的定义'); return; }
    setPhase('submitting');
    setError(null);
    setFileId(null);
    setTaskId(null);
    stopPolling();
    startedAt.current = Date.now();
    try {
      // 临时条件是**单个节点**（组或叶子），不是数组 —— 后端
      // `ReportExecuteRequest.filters` 的类型是 `Group | Condition | None`。
      const filters: DefNode | undefined = !tempFilters?.length ? undefined
        : (tempFilters.length === 1 && tempFilters[0].kind === 'leaf'
          ? fromFilterTree(tempFilters)[0]
          : { operator: 'AND', conditions: fromFilterTree(tempFilters) });
      const accepted = await reportBuilderApi.execute(selected, {
        filters, max_rows: tempMaxRows ?? undefined,
      });
      setTaskId(accepted.task_id);
      setPhase('polling');
      // ⚠️ 世代号在 `stopPolling()` **之后**取：stopPolling 会 +1 作废
      // 上一轮所有在飞的回调，所以这里拿到的就是本轮自己的号。
      poll(accepted.task_id, generation.current);
    } catch (err) {
      setError(errorMessage(err));
      setPhase('failed');
    }
  };

  /**
   * 按 `task_id` 轮询，直到拿到 `report_file_id`。
   *
   * ⚠️ **404 必须立刻停**。它意味着这个任务不存在（ARQ 队列未接、
   * 或 worker 没跑）—— 继续轮询只会转到超时，而超时那句
   * 「文件可能仍在生成」是**假的**，会把人引到错误的方向去查。
   * 「任务不存在」与「任务还在跑」必须分开报，这正是
   * `ReportExecutionStatus` 不返回占位 PENDING 的原因。
   */
  const poll = (id: string, gen: number) => {
    // ⚠️ 对不上世代 = 这一轮已被新一轮执行（或卸载）取代，整体放弃。
    if (gen !== generation.current) return;
    if (Date.now() - startedAt.current > POLL_TIMEOUT_MS) {
      setPhase('timeout');
      stopPolling();
      return;
    }
    timer.current = setTimeout(() => {
      void (async () => {
        try {
          const st = await reportBuilderApi.executionStatus(id);
          // ⚠️ **await 之后必须再核对一次**：正是这段 await 让上一轮
          // 与这一轮重叠（重跑发生在请求在飞的时候）。
          if (gen !== generation.current) return;
          // ⚠️ 终态失败要先判（评审 P1 #8）。此前这里只看 `report_file_id`，
          // 于是**已经失败**的任务被一路轮询到 `POLL_TIMEOUT_MS`，然后弹
          // 「等待超时 / 文件可能仍在生成中」—— 恰好是 p8_007 加 status 列
          // 要防的那个错误结论。用户等满全程，得到的却是假消息。
          if (st.status === 'FAILED') {
            stopPolling();
            setError('执行失败：后端已把这次执行标记为 FAILED'
              + '（可能是执行器中断后被回收器判定为僵死）。');
            setPhase('failed');
            return;
          }
          if (st.report_file_id) {
            setFileId(st.report_file_id);
            setStatusText('生成完成');
            setPhase('done');
            stopPolling();
            return;
          }
          setStatusText('已提交，正在后台生成…');
        } catch (err) {
          if (gen !== generation.current) return;
          stopPolling();
          setError(errorMessage(err));
          setPhase('failed');
          return;
        }
        poll(id, gen);
      })();
    }, POLL_INTERVAL_MS);
  };

  const download = async () => {
    if (!fileId || !def) return;
    try {
      await reportBuilderApi.download(fileId, `${def.name}_${def.version}`);
    } catch (err) { message.error(errorMessage(err)); }
  };

  const stepIndex = { idle: 0, submitting: 1, polling: 1, done: 2,
    failed: 2, timeout: 2 }[phase];

  return (
    <div className="page">
    <PageHeader
      title="执行报表"
      actions={<Button onClick={() => navigate('/report/definitions')}>返回列表</Button>}
    />
      {error && <Alert type="error" showIcon message={error}
        style={{ marginBottom: 16 }} />}

      <Card size="small" style={{ marginBottom: 16 }}>
        <Space wrap>
          <Select style={{ width: 360 }} placeholder="选一个已发布的定义"
            value={selected} onChange={setSelected}
            options={definitions.map((d) => ({
              value: d.def_id, label: `${d.name}（${d.version}）` }))} />
          <Button type="primary" icon={<PlayCircleOutlined />}
            loading={phase === 'submitting'}
            // ⚠️ 轮询期间也禁用（评审 P1 #7）。世代号守卫已经让重跑**安全**了
            // （旧循环会被作废），但「能安全重跑」不等于「该允许重跑」——
            // 用户在轮询途中点执行，丢掉的正是他刚提交的那一次。
            disabled={phase === 'polling'}
            onClick={() => void run()}>
            执行
          </Button>
        </Space>
      </Card>

      {def && (
        <Card title="条件摘要" size="small" style={{ marginBottom: 16 }}>
          <Descriptions size="small" column={2}
            items={[
              { key: 'n', label: '名称', children: def.name },
              { key: 'v', label: '版本', children: def.version },
              { key: 'l', label: '明细级',
                children: def.definition_json.detailLevel },
              { key: 'f', label: '输出格式', children: def.output_format },
              { key: 'm', label: '最大行数', children: def.max_rows },
              {
                key: 'c',
                label: '过滤条件',
                children: (def.definition_json.FilterConditions ?? []).length === 0
                  ? <Typography.Text type="warning">无（将导出全量）</Typography.Text>
                  : <Space wrap>
                      {(def.definition_json.FilterConditions ?? []).map((c, i) =>
                        <Tag key={i}>{describe(c)}</Tag>)}
                    </Space>,
              },
            ]} />
        </Card>
      )}

      <Card
        title="临时调整（本次执行）"
        size="small"
        style={{ marginBottom: 16 }}
        extra={
          <Space>
            <Button size="small"
              onClick={() => {
                setTempFilters(null);
                setTempMaxRows(null);
              }}>重置为定义里的条件</Button>
            <Button size="small" type="primary"
              disabled={!tempFilters}
              onClick={() => setTempFilters(
                toFilterTree(def?.definition_json.FilterConditions) ?? [])}>
              从定义载入
            </Button>
          </Space>
        }
      >
        <Alert type="warning" showIcon style={{ marginBottom: 12 }}
          message="临时调整**不回写定义**（SPEC §3.2.2(5)）"
          description="这里改的条件只进这一次执行与执行日志的快照。要固化请回定义编辑器改定义。" />
        <InputNumber style={{ width: 160 }} placeholder="最大行数（留空=定义的）"
          min={1} max={100000} value={tempMaxRows ?? undefined}
          onChange={(v: number | null) => setTempMaxRows(v ?? null)} />
        <div style={{ marginTop: 12 }}>
          <FilterTreeEditor
            nodes={tempFilters ?? []}
            onChange={(next) => setTempFilters(next)}
            fields={fields} />
          {tempFilters === null && (
            <Typography.Text type="secondary">
              当前使用<strong>定义里的原条件</strong>（未做临时调整）。
            </Typography.Text>
          )}
        </div>
      </Card>

      <Card size="small">
        <Steps current={stepIndex} size="small" style={{ marginBottom: 16 }}
          items={[
            { title: '选择', description: '已发布的定义' },
            { title: '执行', description: '202 + task_id' },
            { title: '出文件', description: '生成后可下载' },
          ]} />

        {phase === 'idle' && <Typography.Text type="secondary">
          选好定义后点「执行」。
        </Typography.Text>}

        {phase === 'polling' && (
          <Space direction="vertical">
            <Spin />
            <Typography.Text type="secondary">{statusText}</Typography.Text>
            {taskId && <Typography.Text code>task_id: {taskId}</Typography.Text>}
          </Space>
        )}

        {phase === 'done' && fileId && (
          <Result status="success" title="生成完成"
            subTitle={<Typography.Text code>{fileId}</Typography.Text>}
            extra={<Button type="primary" icon={<DownloadOutlined />}
              onClick={() => void download()}>下载</Button>} />
        )}

        {phase === 'failed' && (
          <Result status="error" title="执行失败" subTitle={error ?? ''}
            extra={<Button onClick={() => void run()}>重试</Button>} />
        )}

        {phase === 'timeout' && (
          <Result status="warning" title="等待超时"
            subTitle={`超过 ${POLL_TIMEOUT_MS / 1000} 秒仍未拿到结果。文件可能仍在后台生成（ARQ 队列）—— 可在列表页重新发起。`}
            extra={<Button onClick={() => void run()}>重新执行</Button>} />
        )}
      </Card>
  </div>
  );
}

/** 条件摘要的人类可读写法。分组节点显示「N 个条件组」而不是假装能展开。 */
function describe(c: unknown): string {
  if (!c || typeof c !== 'object') return String(c);
  const n = c as Record<string, unknown>;
  if (Array.isArray(n.children)) return `条件组（${n.children.length} 项）`;
  const val = n.value === '' || n.value == null ? '（空）' : String(n.value);
  return `${String(n.field)} ${String(n.operator)} ${val}`;
}
