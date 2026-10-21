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
import { useEffect, useState } from 'react';
import type { JSX } from 'react';
import { Typography } from 'antd';
import { useParams } from 'react-router-dom';

import type { AllowableStress, ComponentProperty, ToxicityClass } from '../types/common';
import type { Stream } from '../types/stream';
import type { CodeFormatSegment, PipeClass, SymbolMapping } from '../types/pipeClass';
import type { PipeNetGraph } from '../types/pipeNet';
import type { BeddSection, PmsItem } from '../types/pms';
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
import { VesselComputePage } from './vessel/VesselComputePage';
import { ProjectWizardPage } from './wizard/ProjectWizardPage';

function useFetch<T>(path: string, initial: T): T {
  const [data, setData] = useState<T>(initial);
  useEffect(() => {
    let cancelled = false;
    void fetch(path, { headers: { Authorization: DEV_BEARER } })
      .then((r) => (r.ok ? r.json() : null))
      .then((j: T | null) => {
        if (!cancelled && j !== null) setData(j);
      })
      .catch(() => {/* offline / unhandled: keep empty fixtures */});
    return () => { cancelled = true; };
  }, [path]);
  return data;
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
  const assets = useFetch<ConfigAsset[]>('/api/v1/config/assets', []);
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
export function StreamListRoute(): JSX.Element {
  const streams = useFetch<Stream[]>(`/api/v1/projects/${PROJECT_ID}/streams`, []);
  return <StreamListPage streams={streams} />;
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
  const stream = useFetch<Stream | null>(`/api/v1/streams/${streamId}`, null);
  if (!stream) return <Typography.Text>加载中…</Typography.Text>;
  return <StreamDetailPage stream={stream} />;
}
export function ImportWizardRoute(): JSX.Element {
  return <ImportWizardPage />;
}

// === 管道等级 ===
export function PipeClassListRoute(): JSX.Element {
  const classes = useFetch<PipeClass[]>('/api/v1/pipe-classes', []);
  return <PipeClassListPage classes={classes} />;
}
export function SymbolTableRoute(): JSX.Element {
  return <SymbolTablePage mappings={[]} />;
}
export function CodeFormatRoute(): JSX.Element {
  return <CodeFormatDesignerPage segments={[]} />;
}

// === 物性 / 许用应力 / 毒性爆炸 ===
export function PropertySearchRoute(): JSX.Element {
  const components = useFetch<ComponentProperty[]>('/api/v1/common/materials/search', []);
  return <PropertySearchPage components={components} />;
}
export function AllowableStressRoute(): JSX.Element {
  const stresses = useFetch<AllowableStress[]>('/api/v1/common/allowable-stress', []);
  return <AllowableStressPage stresses={stresses} />;
}
export function ToxicityRoute(): JSX.Element {
  const classes = useFetch<ToxicityClass[]>('/api/v1/common/safety', []);
  return <ToxicityExplosivityPage classes={classes} />;
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
export function PipeLineListRoute(): JSX.Element {
  const rows = useFetch<PipeLineListRow[]>(`/api/v1/projects/${PROJECT_ID}/pipe-line-list`, []);
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
import { ReportExecutePage } from './report/ReportExecutePage';
import { ReportStylePage } from './report/ReportStylePage';

export function ReportDefinitionListRoute(): JSX.Element {
  return <ReportDefinitionListPage />;
}

export function ReportDefinitionEditorRoute(): JSX.Element {
  return <ReportDefinitionEditorPage />;
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

// === 项目文档 / 向导 ===
export function PmsRoute(): JSX.Element {
  const items = useFetch<PmsItem[]>(`/api/v1/projects/${PROJECT_ID}/pms`, []);
  return <PmsPage items={items} />;
}
export function BeddRoute(): JSX.Element {
  const sections = useFetch<BeddSection[]>(`/api/v1/projects/${PROJECT_ID}/bedd`, []);
  return <BeddPage sections={sections} />;
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
  BeddSection,
  CodeFormatSegment,
  ComponentProperty,
  ConfigAsset,
  PmsItem,
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
  return <ResultListPage module={moduleByRecordType(module)} />;
}

// === P9B-1 交付物进度（SPEC §6.24 · 观测面板的宿主）===
import { DeliverableProgressPage } from './deliverables/DeliverableProgressPage';
export function DeliverableProgressRoute(): JSX.Element {
  return <DeliverableProgressPage />;
}
