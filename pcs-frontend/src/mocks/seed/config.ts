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
    category: 'FORMULA',
    name: 'Antoine 方程',
    description: '蒸汽压 Antoine 公式',
    status: 'PUBLISHED',
    hash: 'f7a8b9c0d1e2f3a4',
    current_version: 'v3',
    updated_by: 'alice',
    updated_at: '2026-09-10T09:00:00Z',
  },
  {
    asset_id: 'a-coeff-002',
    category: 'COEFFICIENT',
    name: '换热器污垢系数表',
    description: '介质类型 → 污垢热阻',
    status: 'PUBLISHED',
    hash: 'a1b2c3d4e5f67890',
    current_version: 'v2',
    updated_by: 'bob',
    updated_at: '2026-09-12T14:30:00Z',
  },
  {
    asset_id: 'a-tmpl-003',
    category: 'TEMPLATE',
    name: '工艺数据表模板',
    description: '.dotx 工艺数据表模板',
    status: 'IN_APPROVAL',
    hash: 'b2c3d4e5f67890ab',
    current_version: 'v1',
    updated_by: 'alice',
    updated_at: '2026-09-15T16:45:00Z',
  },
  {
    asset_id: 'a-proj-004',
    category: 'PROJECT_TEMPLATE',
    name: '乙烯装置项目模板',
    description: '标准乙烯装置项目骨架',
    status: 'DRAFT',
    hash: 'c3d4e5f67890abc1',
    current_version: 'v1',
    updated_by: 'carol',
    updated_at: '2026-09-16T01:20:00Z',
  },
  {
    asset_id: 'a-std-005',
    category: 'STANDARD_DB',
    name: 'ASME B31.3 标准数据库',
    description: '管道应力计算用标准参数',
    status: 'OBSOLETE',
    hash: 'd4e5f67890abc123',
    current_version: 'v5',
    updated_by: 'dan',
    updated_at: '2026-08-30T10:15:00Z',
  },
];