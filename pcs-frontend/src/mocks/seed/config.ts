/**
 * CONFIG 资产 seed — 5 条（QA 11 组件实例化 P1）
 *
 * 覆盖 5 类（公式/系数表/模板/项目模板/标准数据库）+ 4 态（草稿/审批/已发布/作废）
 * 用于触发 HashBadge 显示 record_hash + 状态色。
 */
import type { ConfigAsset } from '../../types/configAsset';

export const seedAssets: ConfigAsset[] = [
  {
    asset_id: 'a-formula-001',
    category: 'CATEGORY_2',
    name: 'Antoine 方程',
    status: 'PUBLISHED',
    current_version: 'v3',
  },
  {
    asset_id: 'a-coeff-002',
    category: 'CATEGORY_3',
    name: '换热器污垢系数表',
    status: 'PUBLISHED',
    current_version: 'v2',
  },
  {
    asset_id: 'a-tmpl-003',
    category: 'CATEGORY_4',
    name: '工艺数据表模板',
    status: 'PENDING',
    current_version: 'v1',
  },
  {
    asset_id: 'a-proj-004',
    category: 'CATEGORY_5',
    name: '乙烯装置项目模板',
    status: 'DRAFT',
    current_version: 'v1',
  },
  {
    asset_id: 'a-std-005',
    category: 'CATEGORY_1',
    name: 'ASME B31.3 标准数据库',
    status: 'OBSOLETE',
    current_version: 'v5',
  },
];