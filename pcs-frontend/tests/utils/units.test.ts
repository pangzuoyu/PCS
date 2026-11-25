/**
 * 单位制换算（`src/utils/units.ts`）—— P10-K · W-5 / W-19。
 *
 * ## ⚠️ **断言要带容差**
 *
 * 换算是浮点运算 ⇒ ⇒ ⇒ 精确相等会**假红** ⇒ ⇒ ⇒ ⇒ 往返用**相对误差**
 * 断言（上界 1e-9）⇒ ⇒ ⇒ 单点用容差断言。
 *
 * ## ⚠️ **验收例子：14.5 psi = 99.97 kPa**（**不是 100**）
 *
 * `14.5 × 6.894757293168361 = 99.973980746…` ⇒ ⇒ ⇒ 谁写成 100 就是错的。
 */
import { describe, expect, it } from 'vitest';

import {
  canConvert,
  conversionHint,
  displayUnit,
  fromDisplay,
  toDisplay,
  type UnitAwareField,
} from '../../src/utils/units';

/** 气压字段（kPa ⇄ psi）。 */
const pressure: UnitAwareField = {
  path: 'meteorology.pressure',
  unit: 'kPa',
  unit_display: { factor: 1 / 6.894757293168361, offset: 0, display_unit: 'psi' },
};

/** 气温字段（℃ ⇄ ℉，**偏移型**）。 */
const temperature: UnitAwareField = {
  path: 'meteorology.temperature',
  unit: 'degC',
  unit_display: { factor: 9 / 5, offset: 32, display_unit: 'degF' },
};

/** 湿度（**有单位但不可换算**）。 */
const humidity: UnitAwareField = {
  path: 'meteorology.humidity',
  unit: '%',
  unit_display: null,
};

/** 无单位字段。 */
const noUnit: UnitAwareField = { path: 'utilities.steam', unit: null, unit_display: null };

describe('units —— 双向视图变换（canonical 恒 SI）', () => {
  it('SI ⇒ ⇒ 恒等（不换算）', () => {
    expect(toDisplay(100, pressure, 'SI')).toBe(100);
    expect(fromDisplay(100, pressure, 'SI')).toBe(100);
  });

  it('⚠️ **14.5 psi = 99.97 kPa**（不是 100）', () => {
    const kpa = fromDisplay(14.5, pressure, 'US');
    expect(kpa).toBeCloseTo(99.973980746, 6);
    expect(kpa).not.toBeCloseTo(100, 3);
  });

  it('kPa → psi → kPa：**往返相对误差 ≤ 1e-9**', () => {
    const canonical = 99.973980746;
    const shown = toDisplay(canonical, pressure, 'US') as number;
    const back = fromDisplay(shown, pressure, 'US') as number;
    expect(Math.abs(back - canonical) / Math.abs(canonical)).toBeLessThanOrEqual(1e-9);
  });

  it('偏移型（℃ ⇄ ℉）：0 ℃ = 32 ℉ · 100 ℃ = 212 ℉', () => {
    expect(toDisplay(0, temperature, 'US')).toBeCloseTo(32, 9);
    expect(toDisplay(100, temperature, 'US')).toBeCloseTo(212, 9);
    expect(fromDisplay(212, temperature, 'US')).toBeCloseTo(100, 9);
  });

  it('⚠️ **不可换算的字段按原值显示**（不是禁用 · 不是静默换）', () => {
    expect(canConvert(humidity)).toBe(false);
    expect(toDisplay(55, humidity, 'US')).toBe(55);
    expect(fromDisplay(55, humidity, 'US')).toBe(55);
  });

  it('⚠️ **无单位字段** ⇒ ⇒ 不换算、单位名为 null', () => {
    expect(canConvert(noUnit)).toBe(false);
    expect(toDisplay('x' as never, noUnit, 'US')).toBe('x');
    expect(displayUnit(noUnit, 'US')).toBeNull();
  });

  it('⚠️ **后端漏填因子 ⇒ ⇒ 明确不换算**（W-19 的兵底）', () => {
    const missing: UnitAwareField = { path: 'x.y', unit: 'kPa', unit_display: null };
    expect(canConvert(missing)).toBe(false);
    expect(toDisplay(10, missing, 'US')).toBe(10);
    expect(conversionHint(missing, 'US')).toBeNull();
  });

  it('⚠️ **显示单位名跟随单位制**（US 模式标签不能还写 kPa）', () => {
    expect(displayUnit(pressure, 'SI')).toBe('kPa');
    expect(displayUnit(pressure, 'US')).toBe('psi');
    expect(displayUnit(temperature, 'US')).toBe('degF');
  });

  it('⚠️ **提示文案按实际量纲生成**（不是固定的「1 bar = 100 kPa」）', () => {
    const hint = conversionHint(pressure, 'US');
    expect(hint).toContain('psi');
    expect(hint).toContain('kPa');
    expect(hint).not.toContain('bar');
    // ⇒ ⇒ ⇒ SI 侧没有提示（没换算 ⇒ ⇒ ⇒ 不用提示）
    expect(conversionHint(pressure, 'SI')).toBeNull();
  });
});
