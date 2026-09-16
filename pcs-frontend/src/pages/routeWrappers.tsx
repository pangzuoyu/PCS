/**
 * 路由层默认 fixtures 包装器（QA fix / ISSUE-002）。
 *
 * P4.5 批 3 的页面都以 mock props 形式写就，路由层直接挂载会因
 * 缺 required data prop 报 TS 错 / 运行时崩溃。本文件提供最小空
 * 默认值包装；后续接 MSW / 真接口后由 data loader 替换为真数据。
 */
import type { JSX } from 'react';

import type { AllowableStress, ComponentProperty, ToxicityClass } from '../types/common';
import type { ConfigAsset } from '../types/configAsset';
import type { Stream } from '../types/stream';
import type { CodeFormatSegment, PipeClass, SymbolMapping } from '../types/pipeClass';
import type { PipeNetGraph } from '../types/pipeNet';
import type { BeddSection, PmsItem } from '../types/pms';
import type { PipeInput, PipeLineListRow, PipeResult } from '../types/pipe';
import type { FlashInput, FlashResult } from '../types/flash';
import type { PumpInput, PumpResult } from '../types/pump';

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
import { CodeFormatDesignerPage } from './pipe_class/CodeFormatDesignerPage';
import { PipeClassListPage } from './pipe_class/PipeClassListPage';
import { SymbolTablePage } from './pipe_class/SymbolTablePage';
import { PipeComputePage } from './pipe/PipeComputePage';
import { PipeLineListPage } from './pipe/PipeLineListPage';
import { PipeNetTopologyPage } from './pipe_net/PipeNetTopologyPage';
import { PumpComputePage } from './pump/PumpComputePage';
import { PmsPage } from './pms/PmsPage';
import { ImportWizardPage } from './sim/ImportWizardPage';
import { StreamDetailPage } from './sim/StreamDetailPage';
import { StreamListPage } from './sim/StreamListPage';
import { ProjectWizardPage } from './wizard/ProjectWizardPage';

// === 基础配置 ===
export function ApprovalPanelRoute(): JSX.Element {
  return <ApprovalPanelPage items={[]} />;
}
export function AssetListRoute(): JSX.Element {
  return <AssetListPage assets={[]} />;
}
export function CoefficientEditorRoute(): JSX.Element {
  return <CoefficientTableEditorPage rows={[]} />;
}
export function FormulaEditorRoute(): JSX.Element {
  // 最小可渲染占位 formula；onChange/onSave 留路由层后续接真接口
  const stub = {} as Parameters<typeof FormulaEditorPage>[0]['formula'];
  return <FormulaEditorPage formula={stub} />;
}
export function TemplateFileRoute(): JSX.Element {
  return <TemplateFilePage templates={[]} />;
}

// === 物流 ===
export function StreamListRoute(): JSX.Element {
  return <StreamListPage streams={[]} />;
}
export function StreamDetailRoute(): JSX.Element {
  // 占位 Stream：路由层缺真数据；用户实际编辑流应从 /sim/streams 列表进
  const stub = {} as Stream;
  return <StreamDetailPage stream={stub} />;
}
export function ImportWizardRoute(): JSX.Element {
  return <ImportWizardPage />;
}

// === 管道等级 ===
export function PipeClassListRoute(): JSX.Element {
  return <PipeClassListPage classes={[]} />;
}
export function SymbolTableRoute(): JSX.Element {
  return <SymbolTablePage mappings={[]} />;
}
export function CodeFormatRoute(): JSX.Element {
  return <CodeFormatDesignerPage segments={[]} />;
}

// === 物性 / 许用应力 / 毒性爆炸 ===
export function PropertySearchRoute(): JSX.Element {
  return <PropertySearchPage components={[]} />;
}
export function AllowableStressRoute(): JSX.Element {
  return <AllowableStressPage stresses={[]} />;
}
export function ToxicityRoute(): JSX.Element {
  return <ToxicityExplosivityPage classes={[]} />;
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
  return <PipeLineListPage rows={[]} />;
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

// === 项目文档 / 向导 ===
export function PmsRoute(): JSX.Element {
  return <PmsPage items={[]} />;
}
export function BeddRoute(): JSX.Element {
  return <BeddPage sections={[]} />;
}
export function WizardRoute(): JSX.Element {
  // minimal initial steps for routing preview; real init from /pms or store
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