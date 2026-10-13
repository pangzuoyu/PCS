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
  const [phase, setPhase] = useState<Phase>('idle');
  const [error, setError] = useState<string | null>(null);
  const [taskId, setTaskId] = useState<string | null>(null);
  const [fileId, setFileId] = useState<string | null>(null);
  const [statusText, setStatusText] = useState<string>('');

  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const startedAt = useRef<number>(0);

  const stopPolling = () => {
    if (timer.current) { clearTimeout(timer.current); timer.current = null; }
  };
  useEffect(() => stopPolling, []);

  useEffect(() => {
    void (async () => {
      try {
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
      const accepted = await reportBuilderApi.execute(selected);
      setTaskId(accepted.task_id);
      setPhase('polling');
      poll(accepted.task_id);
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
  const poll = (id: string) => {
    if (Date.now() - startedAt.current > POLL_TIMEOUT_MS) {
      setPhase('timeout');
      stopPolling();
      return;
    }
    timer.current = setTimeout(() => {
      void (async () => {
        try {
          const st = await reportBuilderApi.executionStatus(id);
          if (st.report_file_id) {
            setFileId(st.report_file_id);
            setStatusText('生成完成');
            setPhase('done');
            stopPolling();
            return;
          }
          setStatusText('已提交，正在后台生成…');
        } catch (err) {
          stopPolling();
          setError(errorMessage(err));
          setPhase('failed');
          return;
        }
        poll(id);
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
            loading={phase === 'submitting'} onClick={() => void run()}>
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
