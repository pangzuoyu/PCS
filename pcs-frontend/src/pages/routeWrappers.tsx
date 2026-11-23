/**
 * 路由层默认 fixtures 包装器（QA fix / ISSUE-002 + 11 组件实例化）
 *
 * P4.5 批 3 的页面以 mock props 形式写就，路由层挂载时会因缺 required data
 * prop 报 TS 错 / 运行时崩溃。本文件提供：
 * 1) 空 fixtures 占位（避免 TS 错）
 * 2) useEffect + MSW fetch 拉 seed 数据后重渲染（让 11 个共享组件实例化）
 *
 * 后续 P5-1 接真接口后由 data loader 替换；当前阶段 MSW devOnlyMockHandlers
 * 已覆盖 13 个端点（QA 11 组件实例化 P1）。
 */
import { useEffect, useRef, useState } from 'react';
import type { JSX } from 'react';
import { Alert, Typography } from 'antd';
import { useParams } from 'react-router-dom';

import { handleSessionOver } from '../api/client';
import { useProjectScope } from '../hooks/useProjectScope';

import type { AllowableStress, ComponentProperty, ToxicityClass } from '../types/common';
import type { Stream } from '../types/stream';
import type { CodeFormatSegment, PipeClass, SymbolMapping } from '../types/pipeClass';
import type { PipeNetGraph } from '../types/pipeNet';
import type { ConfigAsset } from '../types/configAsset';
import type { PipeInput, PipeLineListRow, PipeResult } from '../types/pipe';
import type { FlashInput, FlashResult } from '../types/flash';
import type { PumpInput, PumpResult } from '../types/pump';
import { DEV_BEARER, PROJECT_ID } from '../constants/env';

// 页面本地的辅助类型，从源文件复制定义（路由层仅传空数组，不深耦合）
type StreamLite = {
  stream_id: string;
  tag: string;
  description?: string;
  temperature_k?: number | null;
  pressure_kpa?: number | null;
  mass_flow_kg_s?: number | null;
  sign_status?: string;
};
type PipeClassLite = {
  pipe_class_id: string;
  code: string;
  material?: string;
  schedule?: string;
};

import { BeddPage } from './bedd/BeddPage';
import { AllowableStressPage } from './common/AllowableStressPage';
import { HeatingValuePage } from './common/HeatingValuePage';
import { PropertySearchPage } from './common/PropertySearchPage';
import { ToxicityExplosivityPage } from './common/ToxicityExplosivityPage';
import { CvComputePage } from './cv/CvComputePage';
import { SaturationWaterContentPage } from './psychro/SaturationWaterContentPage';
import { ApprovalPanelPage } from './config/ApprovalPanelPage';
import { AssetListPage } from './config/AssetListPage';
import { CoefficientTableEditorPage } from './config/CoefficientTableEditorPage';
import { FormulaEditor, FormulaEditorPage } from './config/FormulaEditorPage';
import { TemplateFilePage } from './config/TemplateFilePage';
import { FlashComputePage } from './flash/FlashComputePage';
import { EquipmentListPage } from './equip/EquipmentListPage';
import { PipeComputePage } from './pipe/PipeComputePage';
import { PipeLineListPage } from './pipe/PipeLineListPage';
import { CodeFormatDesignerPage } from './pipe_class/CodeFormatDesignerPage';
import { PipeClassListPage } from './pipe_class/PipeClassListPage';
import { SymbolTablePage } from './pipe_class/SymbolTablePage';
import { PipeNetTopologyPage } from './pipe_net/PipeNetTopologyPage';
import { PsvComputePage } from './psv/PsvComputePage';
import { PsvStandardProfilePage } from './psv/PsvStandardProfilePage';
import { PumpComputePage } from './pump/PumpComputePage';
import { PmsPage } from './pms/PmsPage';
import { SepEquipComputePage } from './sep_equip/SepEquipComputePage';
import { ImportWizardPage } from './sim/ImportWizardPage';
import { StreamDetailPage } from './sim/StreamDetailPage';
import { StreamListPage } from './sim/StreamListPage';
import { useAuth } from '../store/auth';
import { VesselComputePage } from './vessel/VesselComputePage';
import { ProjectWizardPage } from './wizard/ProjectWizardPage';

/** `useFetch` 的请求超时（15s）—— 超时后进入**失败态**，不再无限期「加载中…」。 */
const FETCH_TIMEOUT_MS = 15_000;

/** 取错误体里的 `code`（401 判定要靠它区分「会话结束」与「二次认证失败」）。 */
async function errorCodeOf(r: Response): Promise<string | undefined> {
  try {
    const data = (await r.json()) as { code?: string } | undefined;
    return data?.code;
  } catch {
    return undefined;
  }
}

/** `useFetch` 的返回形状。 */
interface FetchState<T> {
  data: T;
  /** 失败原因（`null` ⇒ 没失败）。 */
  error: string | null;
  loading: boolean;
}

/**
 * 路由层的**第二条 HTTP 通道**（第一条是 axios）。
 *
 * ⚠️ **它与 axios 的差别正是本函数存在的原因**（P10-F · 评审 #9）：
 * - 401 走 **`handleSessionOver`**（`src/api/client.ts`）⇒ ⇒ 与 axios
 *   **同一份真相源**（含 `SESSION_OVER_CODES` 白名单）。
 * - 失败态**与加载态长得不一样** ⇒ 后端 500 / 网络断了 / 超时，都有话说。
 * - 请求带 **`AbortSignal`** + 15s 超时 ⇒ 卸载时能取消，定时器会清。
 */
/**
 * @param enabled 条件未满足时**不发请求**（P10-C · T2）。
 *
 * ⚠️ **为什么需要它**：有些端点的 URL **依赖另一个请求的结果**
 * （如「先解析项目 id ⇒ 再按项目取管道一览表」）⇒ ⇒ 在 id 还没拿到时
 * 发请求 ⇒ 只会拿到 404（占位 id）或空路径 ⇒ ⇒ 不如**不发**。
 */
function useFetch<T>(path: string, initial: T, enabled = true): FetchState<T> {
  const [data, setData] = useState<T>(initial);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  // ⚠️ **`initial` 不进依赖** —— 它多半是内联字面量（`[]` / `null`）
  // ⇒ ⇒ 每次渲染都是新引用 ⇒ ⇒ 进依赖 ⇒ effect 每次渲染都重跑 ⇒ ⇒ 无限请求。
  // ⇒ ⇒ 用 ref 留住**第一次**的那份（重置时也用它）。
  const initialRef = useRef(initial);
  useEffect(() => {
    // ⚠️ **条件不满足 ⇒ 零请求**（且状态回落到「没加载过」的初始态）。
    if (!enabled) {
      setError(null);
      setLoading(false);
      setData(initialRef.current);
      return;
    }
    let cancelled = false;
    let timedOut = false;
    const controller = new AbortController();
    const timer = setTimeout(() => {
      timedOut = true;
      controller.abort();
    }, FETCH_TIMEOUT_MS);
    // ⚠️ **path 变了 ⇒ 状态必须重置**（P10-F · 整支评审 C1）——
    // React Router **复用同一个组件实例**（`/streams/:id` 换 id 时）⇒ ⇒
    // `useState` 不会自动重置 ⇒ ⇒ 上一条请求的失败态 / 旧数据会**粘住**
    // ⇒ ⇒ 详情页停在一个**假的**失败提示上（新数据永远不显示），
    // 或者把**上一条物流的数据**显示在当前 URL 下。
    // ⚠️ 与 bug-2043 同一形状（Router 复用实例 ⇒ state 留着上一页的行）。
    setError(null);
    setLoading(true);
    setData(initialRef.current);
    // ⚠️ **用会话里的真 token**（P10-B · T7 · bug-2169）——
    // `DEV_BEARER` 是**写死的假 token**（`Bearer mock-jwt-token`）
    // ⇒ ⇒ 真后端通道下 **401** ⇒ 物流详情页 / 设备一览页**永远停在「加载中…」**
    // ⇒ ⇒ mock 通道里 MSW **不校验 token** ⇒ 这条缺陷一直隐形。
    // ⇒ 没会话时（未登录）才回退 `DEV_BEARER`（保持既有开发流程不变）。
    const token = useAuth.getState().accessToken;
    const authorization = token ? `Bearer ${token}` : DEV_BEARER;
    void (async () => {
      try {
        const r = await fetch(path, {
          headers: { Authorization: authorization },
          signal: controller.signal,
        });
        if (!r.ok) {
          // ⚠️ 401 ⇒ 取一次错误码（区分「会话结束」与「二次认证失败」）
          const code = r.status === 401 ? await errorCodeOf(r) : undefined;
          // ⚠️ **卸载后不做副作用**（评审 M7）—— 迟到的 401 不该再清会话
          // ⇒ ⇒ 否则「用户刚离开这个页面」就被登出。
          if (cancelled) return;
          // ⚠️ 401 ⇒ **先**走会话结束的同一份真相源，再报失败
          if (r.status === 401) {
            handleSessionOver(r.status, code);
          }
          setError(`HTTP ${r.status}`);
          setLoading(false);
          return;
        }
        const j = (await r.json()) as T;
        if (cancelled) return;
        // ⚠️ 空响应体（`null`）⇒ **不许**静默停在「加载中…」⇒ 显式失败
        if (j === null || j === undefined) {
          setError('响应为空');
        } else {
          setData(j);
        }
        setLoading(false);
      } catch (err) {
        if (cancelled) return;
        // ⚠️ **区分两类失败**：超时 vs 网络异常（不吞）
        if (timedOut) {
          setError(`请求超时（${FETCH_TIMEOUT_MS / 1000}s）`);
        } else {
          setError('网络错误');
        }
        setLoading(false);
      } finally {
        clearTimeout(timer);
      }
    })();
    return () => {
      cancelled = true;
      controller.abort();
      clearTimeout(timer);
    };
  }, [path, enabled]);
  return { data, error, loading };
}

// === 基础配置 ===
export function ApprovalPanelRoute(): JSX.Element {
  return <ApprovalPanelPage items={[]} />;
}
export function AssetListRoute(): JSX.Element {
  // 端点已补上（2026-10-19，TODO-040）：SPEC `…Web版 P2.md §3.1.2` 第一行
  // 就是这个 GET，此前**从未实现**（前端跑在前面）。
  // 支持 `?category=CATEGORY_N` 过滤 —— 但 Tabs 已经在前端按 category 过滤了，
  // 所以这里不带参数（少一次往返，且过滤逻辑只有一处）。
  const { data: assets } = useFetch<ConfigAsset[]>('/api/v1/config/assets', []);
  return <AssetListPage assets={assets} />;
}
export function CoefficientEditorRoute(): JSX.Element {
  return <CoefficientTableEditorPage rows={[]} />;
}
export function FormulaEditorRoute(): JSX.Element {
  // 曾经写 `const stub = {} as FormulaEditor` —— `as` 骗过 TS 编译，但运行时
  // expression 是 undefined，页面渲染时 `.replace` 抛错，整块落进 ErrorBoundary。
  // 这里给一个**形状完整**的空公式：类型诚实，页面也能正常渲染出待填状态。
  const empty: FormulaEditor = {
    formula_id: '',
    name: '',
    module: '',
    expression: '',
    params: [],
    preconditions: [],
    standard_source: '',
    test_cases: [],
  };
  return <FormulaEditorPage formula={empty} />;
}
export function TemplateFileRoute(): JSX.Element {
  return <TemplateFilePage templates={[]} />;
}

// === 物流 ===
import { StreamManualWizardPage } from './sim/StreamManualWizardPage';
export function StreamManualWizardRoute(): JSX.Element {
  return <StreamManualWizardPage projectId={PROJECT_ID} />;
}
export function StreamListRoute(): JSX.Element {
  // ⚠️ 页面**自己取数**（T6 / SPEC §7.7.1）：筛选要带 query 参数**重新请求后端**
  // ⇒ 筛选状态与请求都在页面里（`useFetch` 拿不到「带参数重新取」的口径）。
  return <StreamListPage projectId={PROJECT_ID} />;
}
export function StreamDetailRoute(): JSX.Element {
  // ⚠️ 直接取契约 `StreamResponse`（2026-10-19，bug-189）。
  // 此前取的是 `StreamDetailPayload` —— 一个**前端合成的**东西：
  // {stream, matrix, signatures, approvalSteps, conflicts, lineage,
  //  changeImpact, uiSchema}。而 `GET /api/v1/streams/{id}` 返的是
  // 单个扁平 `StreamResponse`，**没有 `.stream` 这一层** ⇒ 真后端下
  // `payload.stream` 是 undefined ⇒ 详情页生产上是坏的，
  // 一直是 mocks 的 `buildStreamDetail` 在替它遮着（bug-180 同一形态）。
  //
  // 另外那 7 块**后端根本没有端点**（streams 下只有 `/properties`
  // 与 `/state-points` 两个子资源），所以 props 全部留空 —— 页面用
  // 自己的 DEFAULT_* 兜底。要显示真实数据得先补端点，见 TODOS.md。
  const { id } = useParams<{ id: string }>();
  const streamId = id ?? 's-101';
  // initial 传 null（而不是一个空 Stream）—— 缺失的值要显式失败/显示加载态，
  // 不要塞个形状完整的空对象：那会让「还没加载」和「加载完是空」长得一样。
  const { data: stream, loading, error } = useFetch<Stream | null>(
    `/api/v1/streams/${streamId}`,
    null,
  );
  if (loading) return <Typography.Text>加载中…</Typography.Text>;
  if (error) return <Alert type="error" message={`加载失败：${error}`} />;
  if (!stream) return <Alert type="warning" message="该物流不存在或返回为空" />;
  return <StreamDetailPage stream={stream} />;
}
export function ImportWizardRoute(): JSX.Element {
  return <ImportWizardPage />;
}

// === 管道等级 ===
export function PipeClassListRoute(): JSX.Element {
  const { data: classes } = useFetch<PipeClass[]>('/api/v1/pipe-classes', []);
  return <PipeClassListPage classes={classes} />;
}
export function SymbolTableRoute(): JSX.Element {
  return <SymbolTablePage mappings={[]} />;
}
export function CodeFormatRoute(): JSX.Element {
  return <CodeFormatDesignerPage segments={[]} />;
}

// === 物性 / 许用应力 / 毒性爆炸 ===
//
// ⚠️ **P10-C · T1（TODO-160）**：这三页**不再由路由层发请求**。
// 契约里三个端点的必填参数是 `keyword` / `material`+`temp_c` / `cas`
// ⇒ ⇒ 此前路由层发**空查询** ⇒ 后端 **422** ⇒ 首屏错误态。
// ⇒ ⇒ 现在**页面自取**（查询驱动 ⇒ 首屏零请求 ⇒ 没有 422）。
export function PropertySearchRoute(): JSX.Element {
  return <PropertySearchPage />;
}
export function AllowableStressRoute(): JSX.Element {
  return <AllowableStressPage />;
}
export function ToxicityRoute(): JSX.Element {
  return <ToxicityExplosivityPage />;
}

// === 工艺计算 ===
export function FlashRoute(): JSX.Element {
  return (
    <FlashComputePage
      streams={[]}
      onCalculate={(_input: FlashInput): FlashResult | undefined => undefined}
    />
  );
}
export function PipeRoute(): JSX.Element {
  return (
    <PipeComputePage
      pipeClasses={[]}
      streams={[]}
      onCalculate={(_input: PipeInput): PipeResult | undefined => undefined}
    />
  );
}
// === 设备台账（P10-C · T3 · TODO-157）===
//
// ⚠️ **与「设备一览」(`/config/asset-list`) 是两件事**：前者列 `ConfigAsset`
// （配置资产），本页列 `EquipmentList`（设备台账）。
export function EquipmentListRoute(): JSX.Element {
  return <EquipmentListPage />;
}

export function PipeLineListRoute(): JSX.Element {
  // ⚠️ **P10-C · T2（TODO-159）**：此前这里拿**占位** project id 去调
  // `GET /projects/{id}/pipe-line-list` ⇒ ⇒ **那个端点根本不存在** ⇒ ⇒ 404
  // （mock 通道有 MSW handler ⇒ 一路绿灯 ⇒ 只有真后端通道抓得到）。
  //
  // ⇒ ⇒ 现在：① **先解析真项目 id**（`useProjectScope` ⇒ 走 `GET /workspaces`）
  // ⇒ ⇒ ② 再按项目取一览表（端点是 P10-C 补的 `GET /projects/{id}/pipe-line-list`
  // ⇒ ⇒ 数据源 = `piping_results`）。
  const { projectId, error: scopeError } = useProjectScope();
  const { data: rows, error: rowsError } = useFetch<PipeLineListRow[]>(
    projectId ? `/api/v1/projects/${projectId}/pipe-line-list` : '',
    [],
    Boolean(projectId),
  );
  if (scopeError) {
    return (
      <Alert
        type="warning"
        showIcon
        message="没有可用的项目作用域"
        description={scopeError}
        data-testid="pipe-line-list-scope-error"
      />
    );
  }
  if (rowsError) {
    return (
      <Alert
        type="error"
        showIcon
        message="管道一览表加载失败"
        description={rowsError}
        data-testid="pipe-line-list-error"
      />
    );
  }
  return <PipeLineListPage rows={rows} />;
}
export function PipeNetRoute(): JSX.Element {
  const empty: PipeNetGraph = { nodes: [], edges: [] };
  return <PipeNetTopologyPage graph={empty} />;
}
export function PumpRoute(): JSX.Element {
  return (
    <PumpComputePage
      streams={[]}
      onCalculate={(_input: PumpInput): PumpResult | undefined => undefined}
    />
  );
}

// === P5-1 VESSEL ===
export function VesselRoute(): JSX.Element {
  // OPEN-4-1：移除 streams={[]} 注入，让 Page 走 streamApi 自取（CHECKED 列表）
  return <VesselComputePage />;
}

// === P6-5 前端补课：3 计算页（heating-value / saturation-water-content / cv）===
export function HeatingValueRoute(): JSX.Element {
  return <HeatingValuePage />;
}
export function SaturationWaterContentRoute(): JSX.Element {
  return <SaturationWaterContentPage />;
}
export function CvRoute(): JSX.Element {
  // 同 VesselRoute：streamApi 自取物流列表
  return <CvComputePage />;
}

// === P5-2 SEP_EQUIP ===
export function SepEquipRoute(): JSX.Element {
  // OPEN-4-2：移除 streams={[]} 注入，让 Page 走 streamApi 自取
  return <SepEquipComputePage />;
}

// === P5-3 PSV ===
export function PsvRoute(): JSX.Element {
  return <PsvComputePage streams={[]} projectStandard="API" />;
}

// === P5-4 HEAT ===
import { HeatComputePage } from './heat/HeatComputePage';
export function HeatRoute(): JSX.Element {
  return <HeatComputePage />;
}

// === P8 REPORT_BUILDER（b10–b12 / c6）===
//
// 直接挂页面，不套 fixture 包装：这四页自己用 `src/api/reportBuilder.ts`
// 取数（真 client），不像 P3/P4 那批组件要靠路由层喂 mock props。
import { ReportDefinitionListPage } from './report/ReportDefinitionListPage';
import { ReportDefinitionEditorPage } from './report/ReportDefinitionEditorPage';
import { ReportReviewQueuePage } from './report/ReportReviewQueuePage';
import { ReportExecutePage } from './report/ReportExecutePage';
import { ReportStylePage } from './report/ReportStylePage';

export function ReportDefinitionListRoute(): JSX.Element {
  return <ReportDefinitionListPage />;
}

export function ReportDefinitionEditorRoute(): JSX.Element {
  return <ReportDefinitionEditorPage />;
}

/** P10-I · T1 · TODO-197：「待我审核」队列（审核者视角）。 */
export function ReportReviewQueueRoute(): JSX.Element {
  return <ReportReviewQueuePage />;
}

export function ReportExecuteRoute(): JSX.Element {
  return <ReportExecutePage />;
}

export function ReportStyleRoute(): JSX.Element {
  return <ReportStylePage />;
}

// === P5-3 PSV 项目标准配置 ===
export function PsvStandardProfileRoute(): JSX.Element {
  return <PsvStandardProfilePage projectId={PROJECT_ID} />;
}

// === P7-6B 冷却水子表 (R1 §7.2 9 类水) ===
import { CoolingWaterPage } from './util/CoolingWaterPage';
export function CoolingWaterRoute(): JSX.Element {
  return <CoolingWaterPage />;
}

// === P7-6B 综合能耗聚合 (R1 §7 分类聚合) ===
import { EnergySummaryAggregatePage } from './util/EnergySummaryAggregatePage';
export function EnergySummaryAggregateRoute(): JSX.Element {
  return <EnergySummaryAggregatePage />;
}

// === F-P2-009 Sprint 3 Audit Query (3 endpoints + 混合 RBAC) ===
import { AuditLogPage } from './audit/AuditLogPage';
export function AuditLogRoute(): JSX.Element {
  return <AuditLogPage />;
}

// === ADMIN 用户管理（P9B-2 · T7 · SPEC §7.20）===
import { UserAdminPage } from './admin/UserAdminPage';
export function UserAdminRoute(): JSX.Element {
  return <UserAdminPage />;
}

// === ADMIN 建项目（P9B-2 · Batch F）===
import { ProjectAdminPage } from './admin/ProjectAdminPage';
export function ProjectAdminRoute(): JSX.Element {
  return <ProjectAdminPage />;
}

// === ADMIN 系统参数（P9B-3 · T5 · SPEC §7.20.1）===
import { SystemSettingsPage } from './admin/SystemSettingsPage';
export function SystemSettingsRoute(): JSX.Element {
  return <SystemSettingsPage />;
}

// === 项目文档 / 向导 ===
//
// ⚠️ **P10-C · T2（TODO-159）**：PMS / BEDD 两页此前调**不存在**的端点
// （`GET /projects/{id}/pms` · `GET /projects/{id}/bedd`）⇒ ⇒ 真后端 404。
//
// ⇒ ⇒ 现在：**不发请求**，页面**明说数据源尚未接入**（占位页）。
// ⇒ ⇒ 理由（不是「懒得做」，是**后端确实没有那两个实体**）：
//   · **PMS**（管道材料规格）：后端**没有**对应表/端点；最接近的是
//     `pipe_classes`（管道等级）⇒ ⇒ 那是**另一个东西**，不能拿来冒充。
//   · **BEDD**：`projects.bedd_json` 这一列**存在**，但**没有任何写入路径**
//     （全仓只有建表迁移提到它）⇒ ⇒ 没有数据可读 ⇒ ⇒ 补一个端点也只能
//     永远返回空 ⇒ ⇒ **不补**（免得造一个「看起来有、其实永远空」的端点）。
// ⚠️ **PMS / BEDD 页面自己取数**（P10-H · T2 · TODO-195）⇒ ⇒
//   项目作用域来自顶栏的选择器（`useProjectScope`）⇒ ⇒ 换项目 ⇒ 页面跟着换。
export function PmsRoute(): JSX.Element {
  return <PmsPage />;
}
export function BeddRoute(): JSX.Element {
  return <BeddPage />;
}
export function WizardRoute(): JSX.Element {
  return (
    <ProjectWizardPage
      initialSteps={[
        { step_index: 0, title: '项目', description: '基础信息', done: false },
        { step_index: 1, title: 'PMS', description: '材料规格', done: false },
        { step_index: 2, title: 'BEDD', description: '基础数据', done: false },
      ]}
    />
  );
}

// 类型导出（防止被 tree-shake 误删其它用得上的 page 子集）
export type {
  AllowableStress,
  CodeFormatSegment,
  ComponentProperty,
  ConfigAsset,
  PipeClass,
  PipeClassLite,
  PipeInput,
  PipeLineListRow,
  PipeResult,
  Stream,
  StreamLite,
  SymbolMapping,
  ToxicityClass,
};

// === P9B-1 结果记录（SPEC §6.21 · 通用页 + 6 个模块描述符） ===
import { ResultListPage } from './results/ResultListPage';
import { moduleByRecordType } from './results/resultModules';
import type { EditableRecordType } from '../api/records';

/**
 * 6 类结果记录共用**一个**页面 ⇒ 路由只传 `recordType`，
 * 其余（路径 / 主键 / 字段清单）由 `resultModules.ts` 的描述符决定。
 */
export function ResultListRoute({ module }: { module: EditableRecordType }): JSX.Element {
  // ⚠️ **`key` 必须带**：React Router 复用同类型的组件实例 ⇒ 从一个结果页
  // 切到另一个时，`records` state 会**留着上一页的行**，而新页面的
  // `module.pk`（主键名）不同 ⇒ 旧行的主键取不到 ⇒ **一排 undefined 主键**
  // ⇒ React 报「two children with the same key」⇒ 表格还短暂显示**别的模块的行**。
  // ⇒ `key` 让换模块 = 整页重建（state 干净）。
  return <ResultListPage key={module} module={moduleByRecordType(module)} />;
}

// === P9B-1 交付物进度（SPEC §6.24 · 观测面板的宿主）===
import { DeliverableProgressPage } from './deliverables/DeliverableProgressPage';
export function DeliverableProgressRoute(): JSX.Element {
  return <DeliverableProgressPage />;
}

// === TODO-079 签署矩阵管理面（P9A-DLV-011 T3 的前端）===
import { SignatureMatrixPage } from './deliverables/SignatureMatrixPage';
export function SignatureMatrixRoute(): JSX.Element {
  return <SignatureMatrixPage />;
}
