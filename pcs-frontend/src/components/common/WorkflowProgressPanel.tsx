/**
 * WorkflowProgressPanel —— 一条工作流的步骤进度（P9B-1 · SPEC §6.24）。
 *
 * 依据 P9A-OBS-001~004（ADR-0047 观测层）。
 *
 * ## 数据源
 *
 * `GET /api/v1/workflow-progress/{workflow_type}/{workflow_id}`
 * - `{workflow_type}` ∈ `SIGN` / `CHANGE_NOTICE` / `CUSTOMER_APPROVAL_PROXY`
 * - `{workflow_id}` **多态**：`SIGN` → **版本 ID**；其余 → **交付物 ID**
 *   ⇒ 前端**不得**假设它一定是交付物 ID（传错 ⇒ 404）。
 *
 * ## 四条纪律
 *
 * 1. **五态不得归并成三态**：`PENDING`（还没开始）与 `SKIPPED`（被跳过）
 *    都是「没完成」，但合并后用户无法区分「还没排到我」和「这一步被跳过」。
 * 2. **不得显示百分比**：`total` 是**节点数**不是工作量 ⇒ 百分比是编造的。
 * 3. **空态措辞**：`items` 为空 ⇒ 「该工作流暂无步骤记录」，
 *    **不是**「0 步已完成」。
 * 4. **CHANGE_NOTICE 的写入点当前不可达**（P9A-DLV-007）⇒ 该类型面板恒为空
 *    ⇒ **不得**把空面板显示成「流程异常」。
 */
import { useEffect, useState } from 'react';
import { Empty, Space, Tabs, Tag, Typography } from 'antd';

import { HashBadge } from './HashBadge';
import { api } from '../../api/client';
import type { components } from '../../types/api';
// ⚠️ 词表独立成文件（eslint `react-refresh/only-export-components` 不允许
// 组件文件导出非组件；仓库既有先例 `src/pages/report/definitionBody.ts`）。
import { WORKFLOW_TABS, type WorkflowType } from './workflowTabs';

type ProgressResponse = components['schemas']['WorkflowProgressResponse'];
type ProgressItem = components['schemas']['WorkflowProgressItemResponse'];

/** 五态配色（SPEC §6.24）。 */
const STEP_STATUS_STYLE: Record<
  string,
  { color: string; dashed?: boolean; pulse?: boolean }
> = {
  PENDING: { color: 'var(--text-secondary, #656D76)' },
  IN_PROGRESS: { color: 'var(--state-in-approval, #2F6FEB)', pulse: true },
  COMPLETED: { color: 'var(--state-checked, #2DA44E)' },
  // ⚠️ SKIPPED 与 PENDING **都是灰**，但一个更浅 + **虚线** ⇒ 可区分
  SKIPPED: { color: 'var(--text-disabled, #BFBFBF)', dashed: true },
  FAILED: { color: 'var(--state-check-rejected, #CF222E)' },
};

interface Props {
  workflowType: WorkflowType;
  workflowId: string;
  /**
   * **受控模式**（R-15）：传了 `data` 面板就**不自己拉**。
   *
   * ⚠️ 为什么需要：聚合端点（TODO-065）一次返回两类工作流的进度 ⇒ 若每段
   * 各渲染一个「自拉」面板 ⇒ 展开一行发 **1 聚合 + 每段 1 次** = 多个请求
   * ⇒ 聚合端点的收益被完全抵消，且两套数据源可能不一致。
   * ⇒ 受控模式 ⇒ 展开一行 = **1 个请求**。
   *
   * ⚠️ **既有自拉用法保持不变**（回归）：不传 `data` ⇒ 面板照旧自己拉。
   */
  data?: {
    total: number;
    pending: number;
    in_progress: number;
    completed: number;
    skipped: number;
    failed: number;
    items?: ProgressItem[];
  };
  /**
   * 空态文案（宿主可定制）。
   *
   * ⚠️ **空态与「请求失败」是两回事**（SPEC §6.24 的宿主三态：
   * ① 尚未签发 ② 签署流程尚未开始 ③ 无权限）⇒ 失败走 `errorDescription`，
   * **不得**也渲染成「暂无步骤记录」（那是**说谎**）。
   */
  emptyDescription?: string;
  /**
   * 请求失败（**网络 / 其它**）时的文案。
   *
   * ⚠️ TODO-067 #7：403 / 404 / 网络错误**不得**映射成同一句 ——
   * **404 被读成「无权限」**会让用户以为自己没权限（其实是不存在）。
   * ⇒ 403 ⇒ 「无权查看」（固定口径）；404 ⇒ 「该工作流不存在」（固定口径）；
   * 其它 ⇒ 本 prop。
   */
  errorDescription?: string;
  /**
   * **不渲染**顶部的 tab 行（聚合端点的宿主用）。
   *
   * ⚠️ 聚合端点一次返回**两段** ⇒ 每段各渲染一个面板 ⇒ 两个面板各带一行
   * tab 会让人以为「可以切换」⇒ 宿主自己给每段起标题，面板只管内容。
   */
  showTabs?: boolean;
}

export function WorkflowProgressPanel({
  workflowType,
  workflowId,
  data,
  emptyDescription = '该工作流暂无步骤记录',
  errorDescription = '无法读取该工作流的进度',
  showTabs = true,
}: Props): JSX.Element {
  const [fetched, setFetched] = useState<ProgressResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [failed, setFailed] = useState(false);
  const [errorStatus, setErrorStatus] = useState<number | null>(null);
  const controlled = data !== undefined;

  useEffect(() => {
    // ⚠️ **受控模式**：宿主已经喂了数据 ⇒ **不自己拉**（R-15）
    if (controlled) return;
    let cancelled = false;
    setLoading(true);
    void api
      .get<ProgressResponse>(
        `/workflow-progress/${workflowType}/${encodeURIComponent(workflowId)}`,
      )
      .then((res) => {
        if (!cancelled) {
          setFetched(res.data);
          setErrorStatus(null);
        }
      })
      .catch((err) => {
        // ⚠️ 拿不到就**明说失败**（与「无步骤」是两回事）
        if (!cancelled) {
          setFetched(null);
          setFailed(true);
          const status = (err as { response?: { status?: number } })?.response?.status;
          setErrorStatus(typeof status === 'number' ? status : null);
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [workflowType, workflowId, controlled]);

  const effective = controlled
    ? {
        pending: data.pending,
        in_progress: data.in_progress,
        completed: data.completed,
        skipped: data.skipped,
        failed: data.failed,
        items: data.items ?? [],
      }
    : fetched;

  const items: ProgressItem[] = [...(effective?.items ?? [])].sort(
    (a, b) => a.step_order - b.step_order,
  );

  // ⚠️ TODO-067 #7：403 / 404 / 网络**三种文案**（404 不是「无权限」）
  const errorText =
    errorStatus === 403
      ? '无权查看该工作流的进度'
      : errorStatus === 404
        ? '该工作流不存在'
        : errorDescription;

  return (
    <div data-testid="workflow-progress-panel">
      {showTabs && (
        <Tabs
          size="small"
          activeKey={workflowType}
          // ⚠️ **只渲染 enabled 的 tab**（CHANGE_NOTICE 已被 R-13 删掉）
          items={WORKFLOW_TABS.filter((t) => t.enabled).map((t) => ({
            key: t.type,
            label: t.label,
          }))}
        />
      )}

      {effective && (
        <Space
          size={16}
          wrap
          data-testid="workflow-progress-counts"
          style={{ marginBottom: 12 }}
        >
          <span>待办 {effective.pending}</span>
          <span>进行中 {effective.in_progress}</span>
          <span>完成 {effective.completed}</span>
          <span>跳过 {effective.skipped}</span>
          <span>失败 {effective.failed}</span>
        </Space>
      )}

      {items.length === 0 ? (
        <Empty
          data-testid="workflow-progress-empty"
          description={
            loading ? '加载中…' : failed ? errorText : emptyDescription}
        />
      ) : (
        <Space direction="vertical" size={4} style={{ width: '100%' }}>
          {items.map((item) => {
            const style = STEP_STATUS_STYLE[item.step_status] ?? {
              color: 'var(--text-secondary, #656D76)',
            };
            return (
              <div
                key={item.progress_id}
                data-testid={`progress-node-${item.progress_id}`}
                data-step-order={item.step_order}
                data-step-status={item.step_status}
                data-status-color={style.color}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 8,
                  padding: '4px 8px',
                  borderLeft: `3px ${style.dashed ? 'dashed' : 'solid'} ${style.color}`,
                  opacity: style.pulse ? 0.9 : 1,
                }}
              >
                <span>#{item.step_order}</span>
                <Tag style={{ color: style.color, borderColor: style.color }}>
                  {item.step_status}
                </Tag>
                <span>{item.step_role}</span>
                {item.assignee && <span>· {item.assignee}</span>}
                {item.started_at && (
                  <Typography.Text type="secondary">
                    · 起 {item.started_at}
                  </Typography.Text>
                )}
                {item.completed_at && (
                  <Typography.Text type="secondary">
                    · 止 {item.completed_at}
                  </Typography.Text>
                )}
                {item.result_hash && <HashBadge hash={item.result_hash} />}
              </div>
            );
          })}
        </Space>
      )}
    </div>
  );
}

export default WorkflowProgressPanel;
