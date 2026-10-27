/**
 * DeliverableProgressPage —— 交付物的签署进度（P9B-1 · SPEC §6.24 · P9B-2 扩展）。
 *
 * ## 它是「观测面板」的**宿主**
 *
 * `WorkflowProgressPanel`（P9B-1 T5）需要一个宿主才有意义 ⇒ 本页就是它。
 *
 * ## ⚠️ P9B-2 起走**聚合端点**（TODO-065）
 *
 * `GET /deliverables/{id}/progress` ⇒ 一次返回两类工作流的进度：
 * - `SIGN` → **版本 ID**
 * - `CUSTOMER_APPROVAL_PROXY` → **交付物 ID**
 *
 * ⚠️ **没有 `CHANGE_NOTICE` 段**（R-13）：变更单**本身就是交付物** ⇒ 它在
 * 进度页上**自己一行**、自己有 SIGN 进度；而
 * `Deliverable.parent_deliverable_id` 全仓从未被写 ⇒ 靠它反查变更单**永远
 * 查不到** ⇒ 留着一个**永远为假**的段比没有更坏。
 *
 * ## 四条纪律
 *
 * 1. ⚠️ **行展开才拉 progress**（列表加载时**不**预取）⇒ 无 N+1。
 * 2. ⚠️ **关联规则归后端** —— 「哪类工作流用哪个 id」不是前端的拼装活。
 * 3. ⚠️ **面板受控**（R-15）：数据由聚合端点喂 ⇒ 面板**不自己拉** ⇒
 *    展开一行 = 1 个聚合请求（**不是** 1 + 每段 1 个）。
 * 4. ⚠️ **不得自行按项目过滤交付物** —— 后端已做项目守卫
 *    （`check_project_access_or_404`）⇒ 前端过滤会把「无权限」说成「无数据」。
 */
import { useEffect, useState } from 'react';
import { Button, Empty, List, Space, Spin, Table, Tooltip, Typography } from 'antd';
import type { ColumnsType } from 'antd/es/table';

import { PageHeader } from '../../components/common/PageHeader';
import { StateBadge } from '../../components/common/StateBadge';
import { WorkflowProgressPanel } from '../../components/common/WorkflowProgressPanel';
import {
  DeliverableSignDialog,
  type SignDialogMode,
  type SignDialogStep,
  type SignNextStep,
} from '../../components/deliverables/DeliverableSignDialog';
import { api } from '../../api/client';
import {
  deliverablesApi,
  type DeliverableActionsListResponse,
  type DeliverableProgressResponse,
  type WorkflowProgressSection,
} from '../../api/deliverables';
import { useAuth } from '../../store/auth';
import { PROJECT_ID } from '../../constants/env';
import type { components } from '../../types/api';

type Deliverable = components['schemas']['DeliverableResponse'];
type DeliverableList = components['schemas']['DeliverableListResponse'];

/** 段标题（与 `workflowTabs` 的词表一致）。 */
const SECTION_LABELS: Record<string, string> = {
  SIGN: '签署进度',
  CUSTOMER_APPROVAL_PROXY: '客户批准代录',
};

export function DeliverableProgressPage(): JSX.Element {
  const [items, setItems] = useState<Deliverable[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  // ⚠️ **分页**（最终评审 Important ⑤）：此前是 `pagination={false}` +
  // 硬编码 `limit: 100` ⇒ 交付物超过 100 个时**只显示前 100 个、没有任何提示**
  // ⇒ 用户以为「就这些」。⇒ 走 limit/offset（后端上限 500）。
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  /** 当前展开的交付物（行展开才拉 ⇒ 不预取）。 */
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [progress, setProgress] = useState<DeliverableProgressResponse | null>(null);
  const [actionList, setActionList] = useState<DeliverableActionsListResponse | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState<string | null>(null);
  // ⚠️ **写面**（P9B-2 · T8）：签发 / 签署 / 代录
  const [dialogMode, setDialogMode] = useState<SignDialogMode | null>(null);
  const [dialogTarget, setDialogTarget] = useState<Deliverable | null>(null);
  const [nextStep, setNextStep] = useState<SignNextStep | null>(null);
  /** 读签署上下文（版本快照 + 进度）失败时的原因 —— **不得**与「没有步骤」混淆。 */
  const [contextError, setContextError] = useState<string | null>(null);
  /** 列表刷新令牌（写操作成功后 ⇒ 重新拉列表，不乐观更新）。 */
  const [reloadToken, setReloadToken] = useState(0);
  const role = useAuth((s) => s.role);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    void api
      .get<DeliverableList>('/deliverables', {
        params: { project_id: PROJECT_ID, limit: pageSize, offset: (page - 1) * pageSize },
      })
      .then((res) => {
        if (cancelled) return;
        setItems(res.data.items ?? []);
        setTotal(res.data.total ?? 0);
      })
      .catch(() => {
        if (!cancelled) {
          setItems([]);
          setTotal(0);
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [page, pageSize, reloadToken]);

  // ⚠️ **行展开才拉**（列表加载时**不**预取）⇒ 无 N+1。
  useEffect(() => {
    if (!expandedId) {
      setProgress(null);
      setActionList(null);
      return;
    }
    let cancelled = false;
    setDetailLoading(true);
    setDetailError(null);
    void Promise.all([
      deliverablesApi.progress(expandedId),
      deliverablesApi.actions(expandedId),
    ])
      .then(([p, a]) => {
        if (cancelled) return;
        setProgress(p);
        setActionList(a);
      })
      .catch(() => {
        if (!cancelled) {
          setProgress(null);
          setActionList(null);
          setDetailError('无法读取该交付物的进度');
        }
      })
      .finally(() => {
        if (!cancelled) setDetailLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [expandedId]);

  /**
   * 写操作成功 ⇒ **重新拉数据**（不乐观更新）。
   *
   * ⚠️ 重新拉**该行的进度**（计划 T8 断言 4）⇒ 步骤推进看得见；
   * ⚠️ 重新拉**列表**（`current_version_id` / `sign_status` 变了）。
   */
  function refreshAfterAction(target: Deliverable): void {
    setReloadToken((t) => t + 1);
    void deliverablesApi
      .progress(target.deliverable_id)
      .then((p) => {
        if (expandedId === target.deliverable_id) setProgress(p);
      })
      .catch(() => {/* 进度拉不到 ⇒ 展开时再拉 */});
  }

  function openIssue(row: Deliverable): void {
    setDialogTarget(row);
    setNextStep(null);
    setContextError(null);
    setDialogMode('issue');
  }

  function openProxy(row: Deliverable): void {
    setDialogTarget(row);
    setNextStep(null);
    setContextError(null);
    setDialogMode('proxy');
  }

  /**
   * 打开签署弹窗 ⇒ 先算出「当前该签哪一步」。
   *
   * ⚠️ 步骤取**版本冻结快照**（`signature_summary_json.steps`）—— 与后端
   * `_steps_for_version` **同源**（bug-2063）；已完成的步骤取**观测行**
   * （`COMPLETED` / `SKIPPED`）—— 与后端 `_assert_step_order` 同口径。
   */
  async function openSign(row: Deliverable): Promise<void> {
    setDialogTarget(row);
    setNextStep(null);
    setContextError(null);
    setDialogMode('sign');
    if (!row.current_rev) {
      setContextError('该交付物尚无版本（没有版本就没有可签的步骤）');
      return;
    }
    try {
      const [snap, prog] = await Promise.all([
        deliverablesApi.versionSnapshot(row.deliverable_id, row.current_rev),
        deliverablesApi.progress(row.deliverable_id),
      ]);
      const steps = (snap.signature_summary_json as { steps?: unknown })?.steps;
      setNextStep(computeNextStep(Array.isArray(steps) ? (steps as SignDialogStep[]) : [], prog));
    } catch {
      setNextStep(null);
      // ⚠️ **读不到 ≠ 没有** —— 说清是「读不到」
      setContextError('无法读取该交付物的签署步骤（网络 / 权限 / 交付物不存在）');
    }
  }

  const columns: ColumnsType<Deliverable> = [
    { title: '编号', dataIndex: 'doc_no', key: 'doc_no' },
    { title: '名称', dataIndex: 'title', key: 'title' },
    {
      title: '当前 Rev',
      dataIndex: 'current_rev',
      key: 'current_rev',
    },
    {
      title: '状态',
      dataIndex: 'sign_status',
      key: 'sign_status',
      render: (v: string) => <StateBadge status={v as never} />,
    },
    {
      title: '操作',
      key: 'actions',
      render: (_v: unknown, row: Deliverable) => {
        // ⚠️ **已有版本且不在 DRAFT ⇒ 签发禁用**（后端会 409
        //    `DELIVERABLE_ALREADY_ISSUED` ⇒ 禁用优先于报错）。
        // ⚠️ **DRAFT 例外**：退回后必须能再签发，否则变更单被驳回一次就
        //    **永久卡死**（后端 `issue` 的幂等判据是「有没有未退回的版本」）。
        const canIssue = !row.current_version_id || row.sign_status === 'DRAFT';
        const canSign = Boolean(row.current_version_id);
        return (
          <Space>
            <Tooltip
              title={
                canIssue
                  ? '签发新版本（送审）'
                  : '该交付物已在签署中，不能重复签发'
              }
            >
              {/* ⚠️ Tooltip 包 **span**（disabled 按钮不派发鼠标事件） */}
              <span>
                <Button
                  size="small"
                  data-testid={`deliverable-issue-${row.deliverable_id}`}
                  disabled={!canIssue}
                  onClick={() => openIssue(row)}
                >
                  签发
                </Button>
              </span>
            </Tooltip>
            <Tooltip title={canSign ? '推进签署矩阵的一步' : '该交付物尚无版本，不能签署'}>
              {/* ⚠️ Tooltip 包 **span**（disabled 按钮不派发鼠标事件） */}
              <span>
                <Button
                  size="small"
                  data-testid={`deliverable-sign-${row.deliverable_id}`}
                  disabled={!canSign}
                  onClick={() => void openSign(row)}
                >
                  签署
                </Button>
              </span>
            </Tooltip>
            <Tooltip
              title={
                canSign
                  ? '代录客户在系统外的批准（凭证 + 二次认证）'
                  : '该交付物尚无版本，不能代录'
              }
            >
              {/* ⚠️ Tooltip 包 **span**：disabled 的 Button 不派发鼠标事件 ⇒
                  包在 span 里 tooltip 才生效（否则用户只看到灰按钮、不知道为什么）。 */}
              <span>
                <Button
                  size="small"
                  data-testid={`deliverable-proxy-${row.deliverable_id}`}
                  disabled={!canSign}
                  onClick={() => openProxy(row)}
                >
                  代录
                </Button>
              </span>
            </Tooltip>
          </Space>
        );
      },
    },
  ];

  return (
    <div data-testid="deliverable-progress-page">
      <PageHeader title="交付物签署进度" actions={<span />} />
      <Table<Deliverable>
        rowKey="deliverable_id"
        columns={columns}
        dataSource={items}
        loading={loading}
        pagination={{
          current: page,
          pageSize,
          total,
          showSizeChanger: true,
          pageSizeOptions: [20, 50, 100, 200],
          onChange: (nextPage: number, nextSize: number) => {
            // ⚠️ 改页长时回到第 1 页（否则会落到一个不存在的页）
            if (nextSize !== pageSize) {
              setPageSize(nextSize);
              setPage(1);
              return;
            }
            setPage(nextPage);
          },
        }}
        scroll={{ x: 'max-content' }}
        // ⚠️ 写面弹窗（P9B-2 · T8）—— 宿主在**页面**里，不在表格里
        //    （antd 的 `Modal` 走 portal ⇒ 放在 Table 外面更稳）
        expandable={{
          onExpand: (expanded, record) => {
            // ⚠️ **行展开才拉**（列表加载时不预取）
            setExpandedId(expanded ? String(record.deliverable_id) : null);
          },
          expandedRowRender: () => {
            if (detailLoading) {
              return <Spin data-testid="deliverable-progress-loading" />;
            }
            if (detailError) {
              return (
                <Typography.Text type="danger" data-testid="deliverable-progress-error">
                  {detailError}
                </Typography.Text>
              );
            }
            if (!progress) {
              return (
                <Empty
                  data-testid="deliverable-no-version"
                  description="该交付物尚无进度信息"
                />
              );
            }
            return (
              <div data-testid="deliverable-progress-panel">
                {progress.sections.map((section) => (
                  <SectionBlock key={section.workflow_type} section={section} />
                ))}
                {/* ⚠️ **动作时间线**（数据源 = 审计，**不是**观测层）：
                    两个数据源**不混用** —— 这里回答「谁做了什么」，
                    上面回答「流程到哪一步了」（R-10）。 */}
                <div data-testid="deliverable-actions">
                  <Typography.Text strong>动作时间线</Typography.Text>
                  {!actionList || actionList.items.length === 0 ? (
                    <Empty
                      data-testid="deliverable-actions-empty"
                      description="尚无动作记录"
                    />
                  ) : (
                    <List
                      dataSource={actionList.items}
                      renderItem={(item) => (
                        <List.Item
                          key={`${item.resource_type}:${item.resource_id}:${item.created_at}`}
                          data-testid="deliverable-action-item"
                        >
                          <Typography.Text>{item.action}</Typography.Text>
                          <Typography.Text type="secondary" style={{ marginLeft: 8 }}>
                            {item.created_at}
                          </Typography.Text>
                          {item.detail_json && (
                            <Typography.Text type="secondary" style={{ marginLeft: 8 }}>
                              {parseDetail(item.detail_json)}
                            </Typography.Text>
                          )}
                        </List.Item>
                      )}
                    />
                  )}
                </div>
              </div>
            );
          },
        }}
      />
      {/* ⚠️ 写面弹窗（P9B-2 · T8）—— 宿主在**页面**里（不在表格里），
          antd `Modal` 走 portal ⇒ 放在 Table 外面更稳。 */}
      <DeliverableSignDialog
        open={dialogMode !== null}
        mode={dialogMode ?? 'sign'}
        deliverable={
          dialogTarget
            ? {
                deliverable_id: dialogTarget.deliverable_id,
                doc_no: dialogTarget.doc_no,
                title: dialogTarget.title,
                current_rev: dialogTarget.current_rev,
                current_version_id: dialogTarget.current_version_id,
              }
            : { deliverable_id: '', doc_no: '', title: '' }
        }
        nextStep={nextStep}
        role={role}
        contextError={contextError}
        onClose={() => {
          setDialogMode(null);
          setDialogTarget(null);
          setNextStep(null);
          setContextError(null);
        }}
        onDone={() => {
          if (dialogTarget) refreshAfterAction(dialogTarget);
        }}
      />
    </div>
  );
}

/**
 * 「当前该签哪一步」—— 与后端 `_assert_step_order` **同口径**。
 *
 * ⚠️ 已完成的步骤 = 观测行里 `COMPLETED` / `SKIPPED` 的那些（**不是**
 * `FAILED` —— 退回是失败态，但退回后整个交付物回 DRAFT，不能继续往下走）。
 * ⚠️ `step_index` = 矩阵步骤列表里的 **1-based 位置**（后端取
 * `steps[step_index - 1]`）—— 不是 `step_order`（两者在坏数据下可能不一致）。
 */
function computeNextStep(
  steps: SignDialogStep[],
  progress: DeliverableProgressResponse,
): SignNextStep | null {
  if (!steps.length) return null;
  const signSection = progress.sections.find((s) => s.workflow_type === 'SIGN');
  const done = new Set(
    (signSection?.items ?? [])
      .filter((i) => i.step_status === 'COMPLETED' || i.step_status === 'SKIPPED')
      .map((i) => i.step_order),
  );
  const idx = steps.findIndex((s) => !done.has(s.step_order));
  if (idx < 0) return null;
  const step = steps[idx];
  return {
    step_index: idx + 1,
    step_order: step.step_order,
    sign_role: step.sign_role,
    can_skip: Boolean(step.can_skip),
  };
}

/** `detail_json` 是 JSON **文本** ⇒ 解析；**畸形时不崩**（显示原文）。 */
function parseDetail(raw: string): string {
  try {
    const parsed = JSON.parse(raw) as unknown;
    if (parsed && typeof parsed === 'object') {
      return Object.entries(parsed as Record<string, unknown>)
        .map(([k, v]) => `${k}=${String(v)}`)
        .join(' ');
    }
    return String(parsed);
  } catch {
    return raw;
  }
}

/** 一段进度（SIGN / CUSTOMER_APPROVAL_PROXY）。 */
function SectionBlock({ section }: { section: WorkflowProgressSection }): JSX.Element {
  const label = SECTION_LABELS[section.workflow_type] ?? section.workflow_type;
  // ⚠️ **不可用** ⇒ 显示**原因**（不是空列表）—— 空数组会被读成
  //    「这条流程一个节点都没有」，而真相是「这类工作流对本交付物不存在」。
  if (!section.available) {
    return (
      <div data-testid={`deliverable-section-${section.workflow_type}`}>
        <Typography.Text strong>{label}</Typography.Text>
        <Typography.Text type="secondary" style={{ marginLeft: 8 }}>
          {section.reason}
        </Typography.Text>
      </div>
    );
  }
  return (
    <div data-testid={`deliverable-section-${section.workflow_type}`}>
      <Typography.Text strong>{label}</Typography.Text>
      {/* ⚠️ **受控模式**（R-15）：数据由聚合端点喂 ⇒ 面板不自己拉 */}
      <WorkflowProgressPanel
        workflowType={section.workflow_type as never}
        workflowId={section.workflow_id ?? ''}
        data={section}
        showTabs={false}
        emptyDescription="尚无步骤记录"
      />
    </div>
  );
}

export default DeliverableProgressPage;
