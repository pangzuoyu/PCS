/**
 * 单位制换算（P10-K · W-5 / W-19 · SPEC §7.5 单位制切换）。
 *
 * ## 为什么**前端没有换算表**
 *
 * 因子由**后端拥有**，随 ui-schema 下发（`UiSchemaField.unit_display`）
 * ⇒ ⇒ ⇒ 一份表在前端、一份在后端 ⇒ ⇒ ⇒ **迟早漂**
 * ⇒ ⇒ ⇒ 而且「后端新增了一个单位却忘了告诉前端」这件事**前端无从发现**
 * ⇒ ⇒ ⇒ ⇒ 所以因子**必须**由后端下发。
 *
 * ⚠️ **但这是「约定」不是「类型」** —— 后端的字段表是**手写**的
 * ⇒ ⇒ ⇒ 后端**能**新增一个带单位、却忘了填 `unit_display` 的字段
 * ⇒ ⇒ ⇒ ⇒ 前端必须**明确**怎么办（**标灰 + 提示**）⇒ ⇒ ⇒
 * **不是**静默不换（W-19 的兵底）。
 *
 * ## 换算是**双向视图变换**，存储**恒为 canonical（SI）**
 *
 * - 读：`display = canonical × factor + offset`
 * - 写：`canonical = (display − offset) ÷ factor`
 *
 * ⚠️ **form state 保持 canonical**，**只在控件边界换算**
 * ⇒ ⇒ ⇒ 否则每次保存时**未被编辑的字段**也会在末位比特上漂移。
 *
 * ## 精度
 *
 * 往返（canonical → display → canonical）的相对误差上界 **≤ 1e-9**
 * ⇒ ⇒ ⇒ ⚠️ 断言**要带容差** ⇒ ⇒ ⇒ 验收例子：**14.5 psi = 99.97 kPa**
 * （**不是 100** —— `14.5 × 6.894757293168361 = 99.973980746…`）。
 */

/** 单位制（与后端 `app/models/enums.py::UnitSystem` 同词表）。 */
export type UnitSystem = 'SI' | 'US';

/** 后端下发的显示单位变换（契约 `UnitDisplay`）。 */
export interface UnitDisplay {
  factor: number;
  offset: number;
  display_unit: string;
}

/** 一个「带单位信息」的字段（ui-schema 的字段 + 换算信息）。 */
export interface UnitAwareField {
  path?: string;
  unit?: string | null;
  unit_display?: UnitDisplay | null;
}

/**
 * 这个字段在给定单位制下**能不能换算**。
 *
 * ⚠️ **不能换算 ≠ 没有单位** —— 例如湿度（%）与噪声（dB）**有单位**、
 * 但**换算没有物理意义** ⇒ ⇒ ⇒ 前端对它们**标灰**（按原值显示），
 * **不是禁用**（用户仍可录入）。
 */
export function canConvert(field: UnitAwareField | null | undefined): boolean {
  const d = field?.unit_display;
  if (!d) return false;
  if (!Number.isFinite(d.factor) || d.factor === 0) return false;
  return !!field?.unit;
}

/** canonical(SI) → 显示值。 */
export function toDisplay(
  value: number | null | undefined,
  field: UnitAwareField | null | undefined,
  system: UnitSystem,
): number | null | undefined {
  if (value === null || value === undefined) return value;
  if (system === 'SI') return value;
  const d = field?.unit_display;
  if (!d || !canConvert(field)) return value;
  return value * d.factor + d.offset;
}

/** 显示值 → canonical(SI)。 */
export function fromDisplay(
  value: number | null | undefined,
  field: UnitAwareField | null | undefined,
  system: UnitSystem,
): number | null | undefined {
  if (value === null || value === undefined) return value;
  if (system === 'SI') return value;
  const d = field?.unit_display;
  if (!d || !canConvert(field)) return value;
  return (value - d.offset) / d.factor;
}

/**
 * 该字段在给定单位制下的**显示单位名**（标签后缀）。
 *
 * ⚠️ SI 侧显示**canonical 单位本身** ⇒ ⇒ ⇒ US 侧显示 `unit_display.display_unit`
 * ⇒ ⇒ ⇒ ⇒ 否则 US 模式下标签写 kPa、值是 psi ⇒ ⇒ ⇒ **标签在骗人**。
 */
export function displayUnit(
  field: UnitAwareField | null | undefined,
  system: UnitSystem,
): string | null {
  const unit = field?.unit;
  if (!unit) return null;
  if (system === 'SI') return unit;
  return field?.unit_display?.display_unit ?? unit;
}

/** 换算提示文案 —— **按实际量纲生成**（不是一句固定的「1 bar = 100 kPa」）。 */
export function conversionHint(
  field: UnitAwareField | null | undefined,
  system: UnitSystem,
): string | null {
  if (system === 'SI') return null;
  if (!canConvert(field)) return null;
  const d = field!.unit_display!;
  const unit = field!.unit!;
  if (d.offset === 0) {
    const inverse = 1 / d.factor;
    return `已按 1 ${d.display_unit} = ${trim(inverse)} ${unit} 转换`;
  }
  // ⇒ ⇒ ⇒ 偏移型（只有气温：℃ → ℉ 要 +32）
  return (
    `已按 ${trim(d.offset)} ${d.display_unit} = 0 ${unit}、` +
    `每 1 ${unit} = ${trim(d.factor)} ${d.display_unit} 转换`
  );
}

/** 「该字段无换算」的提示（W-19 的兵底）。 */
export const NO_CONVERSION_HINT = '该字段无换算（后端未下发换算因子）⇒ 按原值显示';

/** 数字格式化（去掉多余的尾零；不动有效数字的语义）。 */
function trim(n: number): string {
  if (!Number.isFinite(n)) return String(n);
  const rounded = Number(n.toPrecision(12));
  return String(rounded);
}
