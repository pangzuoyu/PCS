/**
 * CONFIG 资产类型定义（P45-2-3 / Task 21）。
 *
 * SPEC §7.10.1：
 * - 6 类资产（CATEGORY_1~6）：公式 / 系数表 / 模板文件 / 标准数据库 /
 *   项目模板 / 复用设备库
 * - 状态：草稿 / 审批中 / 已发布 / 已作废（V1.1 简化为 4 态）
 */

/** 6 类资产分类（SPEC §7.10.1 / §7.10.2~6）。 */
export type ConfigCategory =
  | 'FORMULA'
  | 'COEFFICIENT'
  | 'TEMPLATE'
  | 'STANDARD_DB'
  | 'PROJECT_TEMPLATE'
  | 'EQUIPMENT_LIB';

/** 资产列表 4 态（SPEC §7.10.1）。 */
export type ConfigAssetStatus =
  | 'DRAFT'
  | 'IN_APPROVAL'
  | 'PUBLISHED'
  | 'OBSOLETE';

export const CONFIG_CATEGORY_LABEL: Record<ConfigCategory, string> = {
  FORMULA: '公式',
  COEFFICIENT: '系数表',
  TEMPLATE: '模板文件',
  STANDARD_DB: '标准数据库',
  PROJECT_TEMPLATE: '项目模板',
  EQUIPMENT_LIB: '复用设备库',
};

export const CONFIG_CATEGORY_ORDER: ConfigCategory[] = [
  'FORMULA',
  'COEFFICIENT',
  'TEMPLATE',
  'STANDARD_DB',
  'PROJECT_TEMPLATE',
  'EQUIPMENT_LIB',
];

export const CONFIG_STATUS_LABEL: Record<ConfigAssetStatus, string> = {
  DRAFT: '草稿',
  IN_APPROVAL: '审批中',
  PUBLISHED: '已发布',
  OBSOLETE: '已作废',
};

/** CONFIG 资产（SPEC §7.10.1）。 */
export interface ConfigAsset {
  asset_id: string;
  name: string;
  category: ConfigCategory;
  current_version: string;
  status: ConfigAssetStatus;
  updated_by: string;
  updated_at: string;
  /** 详情用元数据 */
  description?: string;
  hash?: string;
  tags?: string[];
}