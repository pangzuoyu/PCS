/**
 * 「忽略」的本地存储 —— P10-I · T1（人裁 ④ · 2026-11-23）。
 *
 * ## 为什么存 `localStorage`（而不是 `sessionStorage`）
 *
 * ⚠️ 本仓 `src/store/auth.ts:27` **成文反对** localStorage（防 XSS / 第三方脚本读取）。
 * ⇒ ⇒ 那条反对**对本模块不适用**，理由必须写在这里，否则下一个人会来「统一风格」把它删掉：
 *
 * | | auth 的令牌 | 本模块的忽略集 |
 * |---|---|---|
 * | 内容 | **访问令牌**（⇒ ⇒ 泄漏即身份泄漏）| 一串 `def_id` + `updated_at`（**不是机密**）|
 * | 泄漏后果 | 账号被接管 | 最多「我忽略过哪些草稿」被读走 |
 *
 * ⇒ ⇒ 且 `sessionStorage`（关标签即失）会让「忽略」**白做**：
 * 审核者「打开队列 → 忽略几条 → 关掉 → 明天继续」⇒ ⇒ 明天全回来了
 * ⇒ ⇒ ⇒ 「忽略」这个动作的价值**恰恰在跨会话**。
 *
 * ## 键里为什么必须有 `updated_at`
 *
 * ⚠️ 改草稿**不动版本号**（`definition_service` 裁决 3）⇒ ⇒ 只按 `def_id` 记忽略
 * ⇒ ⇒ ⇒ 创建人改过的草稿会被**永久静默隐藏** ⇒ ⇒ ⇒ 审核者再也看不到它
 * ⇒ ⇒ ⇒ 键 = `(def_id, updated_at)` ⇒ ⇒ 草稿一改 ⇒ ⇒ `updated_at` 变了
 * ⇒ ⇒ ⇒ 「忽略」自动失效 ⇒ ⇒ 它重新出现（这是对的行为：我忽略的是**那一版**）。
 *
 * ## 形状
 *
 * `{ [def_id]: updated_at }` —— 一条草稿**只有一版**被忽略（重新出现后覆盖）。
 */
const STORAGE_KEY = 'pcs.review.ignored.v1';

/** 忽略集：`def_id` → 被忽略时的 `updated_at`。 */
export type IgnoredMap = Record<string, string>;

function storage(): Storage | null {
  try {
    // ⚠️ localStorage 在隐私模式 / 禁用存储时**会抛** ⇒ ⇒ 不假设它存在。
    return typeof window === 'undefined' ? null : window.localStorage;
  } catch {
    return null;
  }
}

/** 读忽略集（读不出来 ⇒ ⇒ 空集 ⇒ ⇒ 页面照常工作，只是「忽略」不持久）。 */
export function readIgnored(): IgnoredMap {
  const s = storage();
  if (!s) return {};
  try {
    const raw = s.getItem(STORAGE_KEY);
    if (!raw) return {};
    const parsed: unknown = JSON.parse(raw);
    if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) return {};
    return parsed as IgnoredMap;
  } catch {
    return {};
  }
}

/** 写入忽略集（写失败 ⇒ ⇒ 静默 ⇒ ⇒ 忽略只对本次会话生效）。 */
export function writeIgnored(map: IgnoredMap): void {
  const s = storage();
  if (!s) return;
  try {
    s.setItem(STORAGE_KEY, JSON.stringify(map));
  } catch {
    /* 存储不可用（配额满 / 隐私模式）⇒ ⇒ 忽略降级为「本次会话内有效」 */
  }
}

/**
 * 这一条**当前**是不是被忽略了。
 *
 * ⚠️ 比较 `updated_at` ⇒ ⇒ 草稿被改过 ⇒ ⇒ 不再算忽略（它重新出现）。
 */
export function isIgnored(map: IgnoredMap, defId: string, updatedAt: string | null | undefined): boolean {
  const marked = map[defId];
  if (marked === undefined) return false;
  if (!updatedAt) return true;   // ⚠️ 没有 `updated_at` ⇒ ⇒ 按「忽略中」处理
  return marked === updatedAt;
}

/** 忽略一条。 */
export function markIgnored(map: IgnoredMap, defId: string, updatedAt: string | null | undefined): IgnoredMap {
  return { ...map, [defId]: updatedAt ?? '' };
}

/** 取消忽略一条。 */
export function clearIgnored(map: IgnoredMap, defId: string): IgnoredMap {
  const next = { ...map };
  delete next[defId];
  return next;
}
