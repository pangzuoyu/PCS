/**
 * CONFIG 资产类型定义（P45-2-3 / Task 21）。
 *
 * SPEC §7.10.1：
 * - 6 类资产（CATEGORY_1~6）：公式 / 系数表 / 模板文件 / 标准数据库 /
 *   项目模板 / 复用设备库
 * - 状态：见下方 ConfigAssetStatus（**契约的 5 态**，不是本文档曾写的 4 态）
 */
import type { components } from './api';

/**
 * 6 类资产分类 —— **取契约的 `CATEGORY_1~6`**，不是语义名。
 *
 * ⚠️ 此前这里写的是 `FORMULA / COEFFICIENT / TEMPLATE / STANDARD_DB /
 * PROJECT_TEMPLATE / EQUIPMENT_LIB`，**六个值里五个是前端编的**：
 * DB 的 `config_assets.category` 有 CheckConstraint 只允许 CATEGORY_1~6
 * （`app/models/config_domain.py`），真实数据的 category 永远是 CATEGORY_N。
 * 后果：按 category 过滤的 Tabs 在生产上**一档都命中不了**。
 *
 * 标签映射的依据（逐条可追，不是猜的）：
 *
 * | 值 | 标签 | 依据 |
 * |---|---|---|
 * | CATEGORY_1 | 项目模板 | `版本与版次管理增补规格说明书.md` §3.2.7 |
 * | CATEGORY_2 | 公式 | `…开发计划.md` 2.2；`config.py:337`、`DOUBLE_SIGNOFF_CATEGORIES` |
 * | CATEGORY_3 | 系数表 | `coefficient_service.py`（默认 6 张系数表 seed 到 CATEGORY_3） |
 * | CATEGORY_4 | 模板文件 | `…Web版 P8.md:66`（REPORT 复用 CATEGORY_4） |
 * | CATEGORY_5 | 管道等级/符号 | `pipe_class_service:402`、`stream_symbol_service:139`、`pipe_code_template_service:121` |
 * | CATEGORY_6 | 复用设备库 | `equip_lib_service:64`（检索固定过滤 category=CATEGORY_6） |
 *
 * ⚠️ SPEC §7.10.1 列的展示顺序（公式/系数表/模板文件/标准数据库/项目模板/
 * 复用设备库）**不是编号顺序**，且其中「标准数据库」在 CATEGORY_1~6 里
 * **没有对应项** —— 不要照那个顺序生成 `CONFIG_CATEGORY_ORDER`。
 */
export type ConfigCategory =
  | 'CATEGORY_1'
  | 'CATEGORY_2'
  | 'CATEGORY_3'
  | 'CATEGORY_4'
  | 'CATEGORY_5'
  | 'CATEGORY_6';

/**
 * 资产状态 —— **5 态，直接取契约的 `ConfigStatus`**（2026-10-19，bug-188）。
 *
 * ⚠️ 此前是手写 4 态且含 `IN_APPROVAL` —— 那是**前端凭空造的**：
 * SPEC、`app/`、契约三处都没有 `IN_APPROVAL`。后果不是多一个标签：
 * `AssetListPage` 的「审批」按钮只对 `IN_APPROVAL` 启用，而后端产的是
 * `PENDING` ⇒ **那个按钮永远点不动**。
 *
 * 与 bug-187 同一族，判别标准也相同：**词表必须在类型里（且来自契约），
 * 不能只在散文里**。
 */
export type ConfigAssetStatus = components['schemas']['ConfigStatus'];

export const CONFIG_CATEGORY_LABEL: Record<ConfigCategory, string> = {
  CATEGORY_1: '项目模板',
  CATEGORY_2: '公式',
  CATEGORY_3: '系数表',
  CATEGORY_4: '模板文件',
  CATEGORY_5: '管道等级/符号',
  CATEGORY_6: '复用设备库',
};

/** 按数值序（= CATEGORY_N 的 N），不是按 SPEC §7.10.1 的展示顺序。 */
export const CONFIG_CATEGORY_ORDER: ConfigCategory[] = [
  'CATEGORY_1',
  'CATEGORY_2',
  'CATEGORY_3',
  'CATEGORY_4',
  'CATEGORY_5',
  'CATEGORY_6',
];

export const CONFIG_STATUS_LABEL: Record<ConfigAssetStatus, string> = {
  DRAFT: '草稿',
  PENDING: '待审批',
  APPROVED: '已批准',
  PUBLISHED: '已发布',
  OBSOLETE: '已作废',
};

/**
 * CONFIG 资产 —— **就是契约的 `AssetResponse`**，不再手写。
 *
 * ⚠️ 手写副本里的 `updated_by` / `hash` / `tags` 三个字段
 * **`config_assets` 表根本没有**（只有 `created_by` / `created_at` /
 * `updated_at`，见 `TimestampMixin`）。于是「更新人」列恒为空、
 * 详情里的哈希与标签恒不显示 —— 又是「手写副本不会自己变对」。
 */
export type ConfigAsset = components['schemas']['AssetResponse'];
