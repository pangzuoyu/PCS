import { RouterProvider, createBrowserRouter } from 'react-router-dom';

import RequireAuth from './components/RequireAuth';
import MainLayout from './layouts/MainLayout';
import DashboardPage from './pages/DashboardPage';
import LoginPage from './pages/LoginPage';

import {
  AllowableStressRoute,
  ApprovalPanelRoute,
  AssetListRoute,
  BeddRoute,
  CodeFormatRoute,
  CoefficientEditorRoute,
  FlashRoute,
  FormulaEditorRoute,
  ImportWizardRoute,
  PipeClassListRoute,
  PipeLineListRoute,
  PipeNetRoute,
  PipeRoute,
  PmsRoute,
  PropertySearchRoute,
  PsvRoute,
  PumpRoute,
  SepEquipRoute,
  StreamDetailRoute,
  StreamListRoute,
  SymbolTableRoute,
  TemplateFileRoute,
  ToxicityRoute,
  VesselRoute,
  WizardRoute,
} from './pages/routeWrappers';

const router = createBrowserRouter([
  { path: '/login', element: <LoginPage /> },
  {
    path: '/',
    element: (
      <RequireAuth>
        <MainLayout />
      </RequireAuth>
    ),
    children: [
      { index: true, element: <DashboardPage /> },

      // 基础配置（P0-P2）
      { path: 'config/asset-list', element: <AssetListRoute /> },
      { path: 'config/approval-panel', element: <ApprovalPanelRoute /> },
      { path: 'config/formula-editor', element: <FormulaEditorRoute /> },
      { path: 'config/template-file', element: <TemplateFileRoute /> },
      { path: 'config/coefficient-editor', element: <CoefficientEditorRoute /> },

      // 物流
      { path: 'sim/streams', element: <StreamListRoute /> },
      { path: 'sim/streams/:id', element: <StreamDetailRoute /> },
      { path: 'sim/import', element: <ImportWizardRoute /> },

      // 管道等级
      { path: 'pipe-class', element: <PipeClassListRoute /> },
      { path: 'pipe-class/symbols', element: <SymbolTableRoute /> },
      { path: 'pipe-class/code-format', element: <CodeFormatRoute /> },

      // 物性 / 许用应力 / 毒性爆炸
      { path: 'common/properties', element: <PropertySearchRoute /> },
      { path: 'common/stress', element: <AllowableStressRoute /> },
      { path: 'common/toxicity', element: <ToxicityRoute /> },

      // 工艺计算
      { path: 'flash', element: <FlashRoute /> },
      { path: 'pipe', element: <PipeRoute /> },
      { path: 'pipe/line-list', element: <PipeLineListRoute /> },
      { path: 'pipe-net', element: <PipeNetRoute /> },
      { path: 'pump', element: <PumpRoute /> },

      // 设备计算（P5）
      { path: 'vessel', element: <VesselRoute /> },
      { path: 'sep-equip', element: <SepEquipRoute /> },
      { path: 'psv', element: <PsvRoute /> },

      // 项目文档 / 向导
      { path: 'pms', element: <PmsRoute /> },
      { path: 'bedd', element: <BeddRoute /> },
      { path: 'wizard', element: <WizardRoute /> },
    ],
  },
]);

export default function App() {
  return <RouterProvider router={router} />;
}