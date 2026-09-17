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
import type { ConfigAsset } from '../types/configAsset';
import type { Stream } from '../types/stream';
import type { CodeFormatSegment, PipeClass, SymbolMapping } from '../types/pipeClass';
import type { PipeNetGraph } from '../types/pipeNet';
import type { BeddSection, PmsItem } from '../types/pms';
import type { PipeInput, PipeLineListRow, PipeResult } from '../types/pipe';
import type { FlashInput, FlashResult } from '../types/flash';
import type { PumpInput, PumpResult } from '../types/pump';
import type { StreamDetailPayload } from '../mocks/seed/streams';

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
import { PropertySearchPage } from './common/PropertySearchPage';
import { ToxicityExplosivityPage } from './common/ToxicityExplosivityPage';
import { ApprovalPanelPage } from './config/ApprovalPanelPage';
import { AssetListPage } from './config/AssetListPage';
import { CoefficientTableEditorPage } from './config/CoefficientTableEditorPage';
import { FormulaEditorPage } from './config/FormulaEditorPage';
import { TemplateFilePage } from './config/TemplateFilePage';
import { FlashComputePage } from './flash/FlashComputePage';
import { PipeComputePage } from './pipe/PipeComputePage';
import { PipeLineListPage } from './pipe/PipeLineListPage';
import { CodeFormatDesignerPage } from './pipe_class/CodeFormatDesignerPage';
import { PipeClassListPage } from './pipe_class/PipeClassListPage';
import { SymbolTablePage } from './pipe_class/SymbolTablePage';
import { PipeNetTopologyPage } from './pipe_net/PipeNetTopologyPage';
import { PsvComputePage } from './psv/PsvComputePage';
import { PumpComputePage } from './pump/PumpComputePage';
import { PmsPage } from './pms/PmsPage';
import { SepEquipComputePage } from './sep_equip/SepEquipComputePage';
import { ImportWizardPage } from './sim/ImportWizardPage';
import { StreamDetailPage } from './sim/StreamDetailPage';
import { StreamListPage } from './sim/StreamListPage';
import { VesselComputePage } from './vessel/VesselComputePage';
import { ProjectWizardPage } from './wizard/ProjectWizardPage';

const PROJECT_ID = '00000000-0000-0000-0000-000000000001';
// MSW handlers 只校验 Authorization: Bearer <non-empty> 前缀；真 token 来自
// zustand store（in-memory），路由层只关心格式不关心内容。
const DEV_BEARER = 'Bearer mock-jwt-token';

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
  const assets = useFetch<ConfigAsset[]>('/api/v1/config/assets', []);
  return <AssetListPage assets={assets} />;
}
export function CoefficientEditorRoute(): JSX.Element {
  return <CoefficientTableEditorPage rows={[]} />;
}
export function FormulaEditorRoute(): JSX.Element {
  const stub = {} as Parameters<typeof FormulaEditorPage>[0]['formula'];
  return <FormulaEditorPage formula={stub} />;
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
  // P5-1 接 :stream_id；s-101 / s-104 都有详情 payload，s-104 sign_status=STALE 触发 ChangeImpactPanel
  const { id } = useParams<{ id: string }>();
  const streamId = id ?? 's-101';
  const payload = useFetch<StreamDetailPayload | null>(`/api/v1/streams/${streamId}`, null);
  if (!payload) return <Typography.Text>加载中…</Typography.Text>;
  return (
    <StreamDetailPage
      stream={payload.stream}
      matrix={payload.matrix}
      signatures={payload.signatures}
      approvalSteps={payload.approvalSteps}
      currentApprovalStep={payload.currentApprovalStep}
      conflicts={payload.conflicts}
      lineage={payload.lineage}
      changeImpact={payload.changeImpact}
      uiSchema={payload.uiSchema}
    />
  );
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
  return <VesselComputePage streams={[]} />;
}

// === P5-2 SEP_EQUIP ===
export function SepEquipRoute(): JSX.Element {
  return <SepEquipComputePage streams={[]} />;
}

// === P5-3 PSV ===
export function PsvRoute(): JSX.Element {
  return <PsvComputePage streams={[]} projectStandard="API" />;
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