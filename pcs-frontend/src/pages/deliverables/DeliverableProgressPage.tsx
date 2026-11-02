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
import { WORKFLOW_LABELS } from '../../components/common/workflowTabs';
import { api } from '../../api/client';
import { errorText } from '../../api/errors';
import {
  deliverablesApi,
  type Deliverable as ApiDeliverable,
  type DeliverableActionsListResponse,
  type DeliverableProgressResponse,
  type WorkflowProgressSection,
} from '../../api/deliverables';
import { useAuth } from '../../store/auth';
import { metaApi } from '../../api/meta';
import { signatureMatricesApi } from '../../api/signatureMatrices';
import { PROJECT_ID } from '../../constants/env';
import type { components } from '../../types/api';

/**
 * 列表行类型 —— **从 api 模块的既有 import 拿**（评审 #13）。
 *
 * ⚠️ 此前是 `import('../../api/deliverables').Deliverable` 的**内联 import
 * 类型**，而同一文件上方已经有该模块的 import 块 ⇒ 两处取同一个类型。
 */
type Deliverable = ApiDeliverable;

/**
 * 列表信封 —— **必须从契约派生**（评审 #13）。
 *
 * ⚠️ 此前是**手写**的 `{ items: Deliverable[]; total: number }` ⇒ 与契约
 * **完全脱钩**：后端给 `DeliverableListResponse` 加字段（下一页游标、过滤
 * 回显）⇒ `tsc` 照样绿，前端**静默丢掉**那个字段 —— 正是 bug-2040 记的
 * 漂移根因（「响应体取契约类型；手写自由 dict 是根因」）。
 *
 * ⇒ `Omit` 只摘掉 `items`（行类型要窄化成 `Deliverable`），其余字段
 * **跟着契约走**。
 */
type DeliverableList = Omit<
  components['schemas']['DeliverableListResponse'],
  'items'
> & { items: Deliverable[] };

/** 某个交付物的详情（进度 + 动作时间线 + 各自的错误）。 */
interface DetailState {
  loading: boolean;
  error: string | null;
  progress: DeliverableProgressResponse | null;
  actionList: DeliverableActionsListResponse | null;
  /** 进度**单独**失败（动作时间线仍可用）⇒ 只说那一块。 */
  progressError: string | null;
  /** 动作时间线**单独**失败。 */
  actionsError: string | null;
}

const EMPTY_DETAIL: DetailState = {
  loading: false,
  error: null,
  progress: null,
  actionList: null,
  progressError: null,
  actionsError: null,
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
  /**
   * **展开的交付物 id 集合**（多行可同时展开）。
   *
   * ⚠️ 此前是**单个** `expandedId` + `expandedRowRender` **忽略 `record`** ⇒
   *    A、B 两行**同时**展开时，两行渲染的是**同一份** state ⇒ **A 行下面显示的
   *    是 B 的签署进度**（doc_no 都对不上）；收起 B 后 A 行还展开着却显示
   *    「尚无进度信息」⇒ 按 id 索引才治得住。
   */
  const [expandedIds, setExpandedIds] = useState<string[]>([]);
  /** 每个交付物**各自**的详情（按 id 索引 ⇒ 多行不串）。 */
  const [details, setDetails] = useState<Record<string, DetailState>>({});
  /** 列表**加载失败**的原因（403 ⇒ 「无权查看」**不是**空表）。 */
  const [listError, setListError] = useState<string | null>(null);
  // ⚠️ **写面**（P9B-2 · T8）：签发 / 签署 / 代录
  const [dialogMode, setDialogMode] = useState<SignDialogMode | null>(null);
  const [dialogTarget, setDialogTarget] = useState<Deliverable | null>(null);
  const [nextStep, setNextStep] = useState<SignNextStep | null>(null);
  /** 读签署上下文（版本快照 + 进度）失败时的原因 —— **不得**与「没有步骤」混淆。 */
  const [contextError, setContextError] = useState<string | null>(null);
  /** 正在读签署上下文（⇒ 弹窗显示「读取中」，**不是**「没有待签的步骤」）。 */
  const [contextLoading, setContextLoading] = useState(false);
  /** 列表刷新令牌（写操作成功后 ⇒ 重新拉列表，不乐观更新）。 */
  const [reloadToken, setReloadToken] = useState(0);
  /**
   * 签发 / 代录允许的角色（来自 `meta/state-machine` 的 `INITIATE_CHANGE`）。
   *
   * ⚠️ **与后端同源**：后端 `_ISSUE_ROLES` 现在也是从 `TRANSITION_ROLES`
   *    派生的 ⇒ 两边不会分叉（各写一份 ⇒ 后端改了前端不知道 ⇒ 按钮亮着 403）。
   * ⚠️ `null` = **还没取到** ⇒ **不禁用**（不猜）⇒ 后端 403 兜底。
   */
  const [issueRoles, setIssueRoles] = useState<string[] | null>(null);
  /**
   * 项目**绑定的矩阵 id 集合**（`null` = 还没取到 ⇒ 不猜）。
   *
   * ⚠️ 后端 `_assert_matrix_bound`：矩阵没绑到本项目 ⇒ **409**
   *    `DELIVERABLE_MATRIX_UNBOUND` ⇒ 前端知道（它拉过绑定列表）⇒ 门禁前置。
   */
  const [boundMatrixIds, setBoundMatrixIds] = useState<Set<string> | null>(null);
  const role = useAuth((s) => s.role);

  // ⚠️ 门禁数据**各拉一次**（页面级 ⇒ 不是每行一次 ⇒ 无 N+1）。
  useEffect(() => {
    let cancelled = false;
    void metaApi
      .stateMachine()
      .then((r) => {
        if (cancelled) return;
        const t = r.transitions.find((x) => x.action === 'INITIATE_CHANGE');
        setIssueRoles(t ? [...t.allowed_roles] : null);
      })
      .catch(() => {
        // ⚠️ 拉不到 ⇒ **不禁用**（前端不知道 ⇒ 不猜）⇒ 后端 403 兜底
      });
    void signatureMatricesApi
      .listProjectBindings(PROJECT_ID)
      .then((bindings) => {
        if (cancelled) return;
        setBoundMatrixIds(new Set(bindings.map((b) => b.matrix_id)));
      })
      .catch(() => {
        // ⚠️ 拉不到 ⇒ 同上（不猜）
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    // ⚠️ 评审 #11：**先清上一次的错** —— 不清的话一次失败后 `listError` 永远
    //    卡住渲染闸（`!listError && <Table/>`）⇒ 后续成功重拉数据进来了、
    //    表格却**永远不渲染**（配合「重试」按钮才有恢复路径）。
    setListError(null);
    void api
      .get<DeliverableList>('/deliverables', {
        params: { project_id: PROJECT_ID, limit: pageSize, offset: (page - 1) * pageSize },
      })
      .then((res) => {
        if (cancelled) return;
        setItems(res.data.items ?? []);
        setTotal(res.data.total ?? 0);
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setItems([]);
          setTotal(0);
          // ⚠️ **403 ≠ 「没有交付物」** —— 空表会被读成「这个项目没有交付物」
          //    （真相是「你没权限」）⇒ 说清是权限问题（RF-12）。
          setListError(errorText(err, '无法读取该项目的交付物'));
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
  //    ⇒ 每个展开的行**各自**拉一次（互不影响 ⇒ 多行不串）。
  useEffect(() => {
    expandedIds.forEach((id) => {
      if (id in details) return; // 已拉过 ⇒ 不重复拉
      void loadDetail(id);
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [expandedIds]);

  /**
   * 拉某个交付物的详情（进度 + 动作时间线）。
   *
   * ⚠️ **两个数据源各自成败**（不是 `Promise.all`）—— 动作时间线挂掉不该把
   *    **已经取回的签署进度**一起拖下水（用户连进度都看不到）。
   */
  async function loadDetail(id: string): Promise<void> {
    setDetails((prev) => ({
      ...prev,
      [id]: { ...(prev[id] ?? EMPTY_DETAIL), loading: true, error: null },
    }));
    const [p, a] = await Promise.allSettled([
      deliverablesApi.progress(id),
      deliverablesApi.actions(id),
    ]);
    setDetails((prev) => ({
      ...prev,
      [id]: {
        loading: false,
        progress: p.status === 'fulfilled' ? p.value : null,
        actionList: a.status === 'fulfilled' ? a.value : null,
        // ⚠️ 只在**两个都失败**时才算「读不到」；单个失败 ⇒ 那一块显示自己的错
        error:
          p.status === 'rejected' && a.status === 'rejected'
            ? '无法读取该交付物的进度'
            : null,
        progressError: p.status === 'rejected' ? '无法读取该交付物的签署进度' : null,
        actionsError: a.status === 'rejected' ? '无法读取该交付物的动作时间线' : null,
      },
    }));
  }

  /**
   * 写操作成功 ⇒ **重新拉数据**（不乐观更新）。
   *
   * ⚠️ 重新拉**该行的进度 + 动作时间线**（计划 T8 断言 4）⇒ 步骤推进看得见、
   *    刚发生的动作也看得见（只重拉进度 ⇒ 动作时间线停在旧状态 ⇒ 用户签完
   *    **看不到自己签过**）；
   * ⚠️ 重新拉**列表**（`current_version_id` / `sign_status` 变了）。
   */
  function refreshAfterAction(target: Deliverable): void {
    setReloadToken((t) => t + 1);
    void loadDetail(target.deliverable_id);
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
    setContextLoading(true);
    setDialogMode('sign');
    if (!row.current_rev) {
      setContextError('该交付物尚无版本（没有版本就没有可签的步骤）');
      setContextLoading(false);
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
    } finally {
      setContextLoading(false);
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
      render: (v: Deliverable['sign_status']) => <StateBadge status={v} />,
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
        // ⚠️ **角色闸**（后端 `_ISSUE_ROLES` = meta 的 `INITIATE_CHANGE`）
        const roleOk = !issueRoles || !role || issueRoles.includes(role);
        // ⚠️ **矩阵绑定闸**（后端 `_assert_matrix_bound` ⇒ 409）
        const matrixBound =
          !boundMatrixIds || (row.matrix_id ? boundMatrixIds.has(row.matrix_id) : false);
        const issueHint = !matrixBound
          ? '项目未绑定该交付物的签署矩阵 ⇒ 不能签发'
          : !roleOk
            ? `当前角色（${role ?? '未知'}）不可签发（需 ${issueRoles?.join(' / ')}）`
            : !canIssue
              ? '该交付物已在签署中，不能重复签发'
              : '';
        const proxyHint = roleOk
          ? ''
          : `当前角色（${role ?? '未知'}）不可代录（需 ${issueRoles?.join(' / ')}）`;
        return (
          <Space>
            <Tooltip title={issueHint || '签发新版本（送审）'}>
              {/* ⚠️ Tooltip 包 **span**（disabled 按钮不派发鼠标事件） */}
              <span>
                <Button
                  size="small"
                  data-testid={`deliverable-issue-${row.deliverable_id}`}
                  disabled={!canIssue || !roleOk || !matrixBound}
                  onClick={() => openIssue(row)}
                >
                  签发
                </Button>
              </span>
              {/* ⚠️ antd 的 Tooltip **不把 props 转发到 DOM** ⇒ 禁用原因另外
                  渲染一个节点（视觉隐藏）⇒ 断言能读到「为什么禁用」。 */}
              {issueHint && (
                <span
                  style={{ display: 'none' }}
                  data-testid={`deliverable-issue-${row.deliverable_id}-hint`}
                >
                  {issueHint}
                </span>
              )}
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
                proxyHint ||
                (canSign
                  ? '代录客户在系统外的批准（凭证 + 二次认证）'
                  : '该交付物尚无版本，不能代录')
              }
            >
              {/* ⚠️ Tooltip 包 **span**：disabled 的 Button 不派发鼠标事件 ⇒
                  包在 span 里 tooltip 才生效（否则用户只看到灰按钮、不知道为什么）。 */}
              <span>
                <Button
                  size="small"
                  data-testid={`deliverable-proxy-${row.deliverable_id}`}
                  disabled={!canSign || !roleOk}
                  onClick={() => openProxy(row)}
                >
                  代录
                </Button>
              </span>
              {proxyHint && (
                <span
                  style={{ display: 'none' }}
                  data-testid={`deliverable-proxy-${row.deliverable_id}-hint`}
                >
                  {proxyHint}
                </span>
              )}
            </Tooltip>
          </Space>
        );
      },
    },
  ];

  return (
    <div data-testid="deliverable-progress-page">
      <PageHeader title="交付物签署进度" actions={<span />} />
      {/* ⚠️ **列表加载失败 ⇒ 不渲染表格**（渲染空表会被读成「这个项目没有
          交付物」；真相可能是「你没权限」⇒ 403 ≠ 空表，RF-12）。 */}
      {listError && (
        <Space>
          <Typography.Text type="danger" data-testid="deliverable-list-error">
            {listError}
          </Typography.Text>
          {/* ⚠️ 评审 #11：失败后**页内可恢复** —— 分页在 total=0 时死了、
              签署按钮在被隐藏的表里 ⇒ 没有这个按钮用户只能整页刷新。 */}
          <Button
            size="small"
            data-testid="deliverable-list-retry"
            onClick={() => setReloadToken((t) => t + 1)}
          >
            重试
          </Button>
        </Space>
      )}
      {!listError && (
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
            // ⚠️ **行展开才拉**（列表加载时不预取）⇒ 无 N+1。
            //    ⚠️ **多行可同时展开** ⇒ 集合（不是单个 id）⇒ 每行各显示各的。
            const id = String(record.deliverable_id);
            setExpandedIds((prev) =>
              expanded ? [...new Set([...prev, id])] : prev.filter((x) => x !== id),
            );
          },
          expandedRowRender: (record) => {
            // ⚠️ **按行取**（此前忽略 `record` ⇒ 所有展开行渲染同一份 state）
            const detail = details[String(record.deliverable_id)] ?? EMPTY_DETAIL;
            const progress = detail.progress;
            const actionList = detail.actionList;
            if (detail.loading) {
              return <Spin data-testid="deliverable-progress-loading" />;
            }
            if (detail.error) {
              return (
                <Typography.Text type="danger" data-testid="deliverable-progress-error">
                  {detail.error}
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
                {detail.progressError && (
                  <Typography.Text type="danger" data-testid="deliverable-progress-error">
                    {detail.progressError}
                  </Typography.Text>
                )}
                {progress.sections.map((section) => (
                  <SectionBlock key={section.workflow_type} section={section} />
                ))}
                {/* ⚠️ **动作时间线**（数据源 = 审计，**不是**观测层）：
                    两个数据源**不混用** —— 这里回答「谁做了什么」，
                    上面回答「流程到哪一步了」（R-10）。 */}
                <div data-testid="deliverable-actions">
                  <Typography.Text strong>动作时间线</Typography.Text>
                  {/* ⚠️ **被截断 ⇒ 明说**（后端默认 limit=200 ⇒ 超出就**静默**
                      截断 ⇒ 用户以为「就这些」） */}
                  {actionList && actionList.total > actionList.items.length && (
                    <Typography.Text
                      type="secondary"
                      style={{ marginLeft: 8 }}
                      data-testid="deliverable-actions-truncated"
                    >
                      只显示最近 {actionList.items.length} 条（共 {actionList.total} 条）
                    </Typography.Text>
                  )}
                  {detail.actionsError && (
                    <Typography.Text type="danger" data-testid="deliverable-actions-error">
                      {detail.actionsError}
                    </Typography.Text>
                  )}
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
      )}
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
        loading={contextLoading}
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
  // ⚠️ 评审 A-3：段标题词表与 tab **同源**（`WORKFLOW_LABELS` 唯一真相源，
  //    `Record<WorkflowType,…>` 强制穷尽 ⇒ 新增类型漏改 = 编译红）。
  // ⚠️ 评审 #14：**运行期**仍要兜底 —— 契约把 `workflow_type` 生成为裸
  //    `string`，后端加第 4 种工作流时前端 `tsc` **看不见** ⇒ 直接下标会
  //    `TypeError` ⇒ **整页崩**（不是「那一段显示得难看」）。
  //    ⇒ 优雅降级：显示原始 key。
  const label = WORKFLOW_LABELS[section.workflow_type]?.section ?? section.workflow_type;
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
        workflowType={section.workflow_type}
        workflowId={section.workflow_id ?? ''}
        data={section}
        showTabs={false}
        emptyDescription="尚无步骤记录"
      />
    </div>
  );
}

export default DeliverableProgressPage;
