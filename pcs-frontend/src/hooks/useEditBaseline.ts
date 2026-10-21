/**
 * 三档并发基线判定（P9B-1 · SPEC §6.21 P9A-LCK-006 · ADR-0048 §⑥）。
 *
 * ## 为什么是「三档」
 *
 * 后端 `check_conflict` 的实际语义：
 *
 * ```
 * 当前 record_hash 非空   ⇒ 比 hash：不等 ⇒ 409 (basis=record_hash)
 * 当前 record_hash 为空   ⇒ 比 updated_at：不等 ⇒ 409 (basis=updated_at)
 *                         → 无 updated_at / 客户端没给基线 ⇒ 409 (basis=no_baseline)
 * ```
 *
 * ⇒ 前端必须**按同一阶梯**判定：客户端看到的是「我手里这份」的 hash，
 * 后端看到的是「DB 里」的 hash —— 两端只有判出**同一档**才对得上。
 *
 * ⚠️ **第三档是防御性代码**：6 张可编辑结果表里 **5 张**有 `updated_at`，
 * 只有 `cost_est_results` 没有 ⇒ 它的行若 hash 为空 ⇒ **两档皆无**
 * ⇒ 永远 409 ⇒ 前端必须**提前**禁用编辑并说「联系管理员」，
 * 而不是让用户填完一堆数据才被后端拒。
 *
 * ⚠️ **判定在打开抽屉时完成**（调用方算一次并缓存）；
 * **保存路径只透传，不再判断**。
 */
import type { PatchBaseline } from '../api/records';

export type EditBaselineReason =
  | 'ok' // 有可用基线
  | 'no-permission' // 当前状态不可编辑（sign_status 锁定态）
  | 'no-baseline'; // 两档皆无 ⇒ 无法安全编辑

/**
 * ⚠️ **继承 `PatchBaseline` ⇒ 字段名逐字相同（snake_case）** ——
 * 展开即类型兼容，不需要转换函数。
 *
 * ⚠️ 若这里改用 camelCase（`expectedHash`），**TypeScript 不会报错**
 * ⇒ 请求体缺 `expected_hash` ⇒ **每次保存 409 no_baseline** ⇒ 见 RF-13。
 */
export interface EditBaseline extends PatchBaseline {
  disabled: boolean;
  reason: EditBaselineReason;
}

/**
 * 可编辑的签署态 —— **本批 `canEdit` 的判据之一**。
 *
 * ⚠️ 后端只允许 `DRAFT` / `CHANGE_PENDING` 可 PATCH
 * （`cool_tower` / `filtration` / `flare` / `open_channel` / `psychro`
 * 五个 persist service 里的 `*_PERSIST_SIGN_STATUS_LOCKED`）。
 */
export const EDITABLE_SIGN_STATUSES = ['DRAFT', 'CHANGE_PENDING'] as const;

export function isEditableSignStatus(signStatus: string): boolean {
  return (EDITABLE_SIGN_STATUSES as readonly string[]).includes(signStatus);
}

/**
 * 行级可编辑判据。
 *
 * ⚠️ **`sign_status` 为 null/undefined ⇒ 该模块没有状态列**（`cost_est_results`
 * —— 后端「1:1 跟随设备、状态跟设备」）⇒ **后端也没有状态门禁** ⇒ 可编辑。
 *
 * ⚠️ 不能因为「判不出状态」就禁编辑：那会把 `cost_est` 的**全部**行锁死
 * （而它们在后端是**可以** PATCH 的）。
 */
export function isRowEditable(signStatus: string | null | undefined): boolean {
  if (signStatus == null) return true;
  return isEditableSignStatus(signStatus);
}

export interface EditBaselineArgs {
  record_hash?: string | null;
  updated_at?: string | null;
  /**
   * ⚠️ **必填** = `isRowEditable(record.sign_status)`。
   * 忘了传 = **编译错误**（不是运行时默认 true ⇒ 漏判 sign_status）。
   */
  canEdit: boolean;
}

/**
 * 判定这一行能不能安全编辑，以及**用哪一档基线**。
 *
 * ⚠️ **`expected_updated_at` 原样透传**（**不过 `new Date()`**）：
 * PG `TIMESTAMPTZ` 是**微秒**，JS `Date` 只到**毫秒** ⇒ 过一次 `Date`
 * 就**每次假 409**（RF-9）。
 */
export function useEditBaseline({
  record_hash,
  updated_at,
  canEdit,
}: EditBaselineArgs): EditBaseline {
  if (!canEdit) return { disabled: true, reason: 'no-permission' };
  const hash = (record_hash ?? '').trim();
  if (hash) return { disabled: false, reason: 'ok', expected_hash: hash };
  const ts = updated_at ?? null;
  if (ts) return { disabled: false, reason: 'ok', expected_updated_at: ts };
  return { disabled: true, reason: 'no-baseline' };
}
