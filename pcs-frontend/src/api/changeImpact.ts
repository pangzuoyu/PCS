/**
 * 变更影响（CIA）客户端（P9B-1 · SPEC §6.7.1 · ADR-0048）。
 *
 * ⚠️ **三个端点，语义各不相同，不可合并**（SPEC §6.7.1 的表格）：
 *
 * | 端点 | 语义 | 谁判定 |
 * |---|---|---|
 * | `POST /change-impact/{rt}/{id}/confirm-recalc` | **传播触发器**（P1 交付） | 无条件跑 CIA 扫描 + 链式传播 |
 * | `POST /change-impact/{rt}/{id}/confirm` | **系统判定分流**（P9A-CIA-001） | 后端按哈希比对 |
 * | `POST /change-impact/{rt}/{id}/manual-adjust` | **人工判定**（P9A-CIA-002） | 人，带 `reason` |
 *
 * 合并会让前端必须传「要不要触发传播」才能区分 ⇒ 一个端点两种语义 ⇒
 * 下次改一个必伤另一个。
 *
 * ⚠️ **`record_type` 用 `RECORD_TYPE_REGISTRY` 的键**（与 `/locks` 同一套，
 * P9A-5 Task A / SPEC V2.0），**不是表名**。
 *
 * ⚠️ **`basis` 在这里有 4 个值**（多 `full_hash` 与 `manual`），
 * 与 409 冲突的 `basis`（3 值）**不是同一个词表** ⇒ 两个类型分开，不复用。
 */
import { api } from './client';
import type { components } from '../types/api';

export type ImpactConfirmResponse = components['schemas']['ImpactConfirmResponse'];
export type ManualAdjustRequest = components['schemas']['ManualAdjustRequest'];

/** 人工判定的两种结论（`decision`）。 */
export type ImpactDecision = 'NO_CHANGE' | 'CHANGED';

export const changeImpactApi = {
  /**
   * **系统判定**：按哈希比对分流。
   *
   * - 结果不变 ⇒ 记录回 CHECKED，**免凭证**（不必重新签署）
   * - 结果变化 ⇒ 进 CHANGE_PENDING，**要求重新签署**
   *
   * ⚠️ 按钮文案随响应的 `decision` 分流（SPEC §6.7.1）⇒ 调用方要读
   * `decision` / `requires_re_approval` 再改文案，**不得**前端自己先判。
   */
  confirm: (recordType: string, recordId: string) =>
    api
      .post<ImpactConfirmResponse>(`/change-impact/${recordType}/${recordId}/confirm`)
      .then((r) => r.data),

  /**
   * **人工判定**：结掉 STALE。
   *
   * ⚠️ `reason` **必填**（后端 `min_length=1`，空 ⇒ 422）—— 人工判定必须有据可查，
   * 审计里要能看出凭什么。
   * ⚠️ 限权由后端把关（`NO_CHANGE` 需 CHECKER/SYSTEM_ADMIN ⇒ DESIGNER 得 403），
   * 前端**不得**只靠角色隐藏按钮当授权（那只是体验层）。
   */
  manualAdjust: (recordType: string, recordId: string, body: ManualAdjustRequest) =>
    api
      .post<ImpactConfirmResponse>(
        `/change-impact/${recordType}/${recordId}/manual-adjust`,
        body,
      )
      .then((r) => r.data),

  /**
   * **传播触发器**（P1 已交付，**没有**哈希判定分流）。
   *
   * ⚠️ 与 `confirm` 是**两个端点**；这里只作为既有能力的转发，不与上面两个混用。
   */
  confirmRecalc: (recordType: string, recordId: string) =>
    api
      .post<components['schemas']['ConfirmRecalcResponse']>(
        `/change-impact/${recordType}/${recordId}/confirm-recalc`,
      )
      .then((r) => r.data),
};

/**
 * 结论一句话（给用户看的），文案取自后端响应的 `message`。
 *
 * ⚠️ 后端已经给了中文结论 ⇒ 前端**原样透传**，不自己改写
 * （与 §6.21 P9A-LCK-004「降级横幅文案取后端原文」同一原则）。
 */
export function impactConclusion(res: ImpactConfirmResponse): string {
  return res.message;
}
