/**
 * 变更单闭环 API 客户端（TODO-083 · P9A-DLV-011 T4 的前端面）。
 *
 * ## 三步是一条**状态机**，不是三个独立按钮
 *
 * ```
 * CHECKED --initiate-change--> CHANGE_PENDING --apply-change--> CHANGED
 *        --change-notice--> 变更单（3 级矩阵）--签完最后一步--> 记录回 CHECKED
 * ```
 *
 * ⇒ 前端**按记录状态只显示当前那一步**的按钮（UI-SPEC §6.3 的状态→按钮表）。
 * ⚠️ 三个端点对**非当前态**都返 409 ⇒ 顺序错了只会得到一句「状态不对」。
 *
 * ## 为什么「变更申请」（initiate）挂在 CHECKED，「关闭凭证」（change-notice）挂在 CHANGED
 *
 * UI-SPEC §6.3 的表：`CHECKED → 变更申请` / `CHANGE_PENDING → 提交变更批准` /
 * `CHANGED → 关闭凭证` ⇒ 与后端三个端点**一一对应**
 * ⇒ ⚠️ 唯一对不上的是**名字**：`提交变更批准` 的后端端点叫 `apply-change`
 * （ CHANGE_PENDING → CHANGED = 「校核完成，等变更单关闭」）⇒ UI-SPEC 的
 * 「批准」二字易读成「批准变更」⇒ 这里用后端语义命名：**提交变更完成**。
 */
import { api } from './client';
import type { components } from '../types/api';

export type RecordActionResponse = components['schemas']['RecordActionResponse'];
export type ChangeNoticeResponse = components['schemas']['ChangeNoticeResponse'];
export type ChangeNoticeRequest = components['schemas']['ChangeNoticeRequest'];

/** 变更类型 7 值（= 后端 `ChangeType`）。 */
export const CHANGE_TYPES = [
  'DATA_CORRECTION',
  'PROCESS_CHANGE',
  'UPSTREAM_CHANGE',
  'CLIENT_COMMENT',
  'RECORD_CANCELLATION',
  'CHANGE_REVERSAL',
  'OTHER',
] as const;

/** 变更类型的**中文标签**（后端只给枚举值 ⇒ 中文只能在前端这张表里）。 */
export const CHANGE_TYPE_LABELS: Record<string, string> = {
  DATA_CORRECTION: '数据修正',
  PROCESS_CHANGE: '工艺变更',
  UPSTREAM_CHANGE: '上游变更',
  CLIENT_COMMENT: '客户意见',
  RECORD_CANCELLATION: '记录作废',
  CHANGE_REVERSAL: '变更撤销',
  OTHER: '其他',
};

export const changeNoticesApi = {
  /** CHECKED → CHANGE_PENDING（发起变更；后端自动写 BEFORE_CHANGE 快照）。 */
  initiate: (
    recordType: string,
    recordId: string,
    reason: string,
  ): Promise<RecordActionResponse> =>
    api
      .post<RecordActionResponse>(
        `/records/${recordType}/${recordId}/initiate-change`,
        { reason },
      )
      .then((r) => r.data),

  /** CHANGE_PENDING → CHANGED（校核完成，等变更单关闭）。 */
  apply: (
    recordType: string,
    recordId: string,
    reason: string,
  ): Promise<RecordActionResponse> =>
    api
      .post<RecordActionResponse>(`/records/${recordType}/${recordId}/apply-change`, {
        reason,
      })
      .then((r) => r.data),

  /**
   * 建变更单（记录须为 CHANGED；FORMAL 工作区才允许）。
   *
   * ⚠️ **多记录变更**（TODO-078）：`body.record_ids` 可带上本次变更影响的
   * **全部**记录（**必须包含**路径里的那条）⇒ 一张单关多条记录。
   * 不给 = 只有路径那条（单记录 = 旧行为）。
   */
  create: (
    recordType: string,
    recordId: string,
    body: ChangeNoticeRequest,
  ): Promise<ChangeNoticeResponse> =>
    api
      .post<ChangeNoticeResponse>(`/records/${recordType}/${recordId}/change-notice`, body)
      .then((r) => r.data),
};
