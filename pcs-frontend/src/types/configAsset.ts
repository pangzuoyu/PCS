/**
 * CONFIG 资产类型定义（P45-2-3 / Task 21）。
 *
 * SPEC §7.10.1：
 * - 6 类资产（CATEGORY_1~6）：公式 / 系数表 / 模板文件 / 标准数据库 /
 *   项目模板 / 复用设备库
 * - 状态：见下方 ConfigAssetStatus（**契约的 5 态**，不是本文档曾写的 4 态）
 */
import type { components } from './api';

/** 6 类资产分类（SPEC §7.10.1 / §7.10.2~6）。 */
export type ConfigCategory =
  | 'FORMULA'
  | 'COEFFICIENT'
  | 'TEMPLATE'
  | 'STANDARD_DB'
  | 'PROJECT_TEMPLATE'
  | 'EQUIPMENT_LIB';

/**
 * 资产状态 —— **5 态，直接取契约的 `ConfigStatus`**（2026-10-19，bug-188）。
 *
 * ⚠️ 此前是手写 4 态且含 `IN_APPROVAL` —— 那是**前端凭空造的**：
 * SPEC、`app/`、契约三处都没有 `IN_APPROVAL`。后果不是多一个标签：
 * `AssetListPage` 的「审批」按钮只对 `IN_APPROVAL` 启用，而后端产的是
 * `PENDING` ⇒ **那个按钮永远点不动**。
 *
 * 与 bug-187 同一族，判别标准也相同：**词表必须在类型里（且来自契约），
 * 不能只在散文里**。这里的 description 当时写对了，但没有机器可读。
 */
export type ConfigAssetStatus = components['schemas']['ConfigStatus'];

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
  PENDING: '待审批',
  APPROVED: '已批准',
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