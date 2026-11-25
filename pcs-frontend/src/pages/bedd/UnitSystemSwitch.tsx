/**
 * 单位制切换（P10-K · W-4 · SPEC §7.5 单位制切换）。
 *
 * ## 为什么在**页面顶部**
 *
 * SPEC §7.5 说「单位制切换（**顶部**下拉 · 切换后所有数值**实时转换**）」
 * ⇒ ⇒ ⇒ ⇒ 而它影响**整页**（9 个分组 Tab）⇒ ⇒ ⇒ ⇒ 放在任何一个 Tab 里
 * ⇒ ⇒ ⇒ ⇒ 都只影响半个页面 ⇒ ⇒ ⇒ ⇒ 用户会以为「只有这个 Tab 变了」。
 *
 * ## ⚠️ **切换 = 页面临时覆盖**，**不写项目**
 *
 * - 默认取 `project.unit_system`（**项目级默认显示单位制**）；
 * - 切换只改**本页**⇒ ⇒ ⇒ **不调** `PATCH /projects/{id}/unit-system`
 *   ⇒ ⇒ ⇒ ⇒ 要改项目默认 ⇒ ⇒ ⇒ 去项目页（PMS）改。
 *
 * ⚠️ **为什么**：切换是**看数据的姿势**（"这组数据按 psi 看一遍"），
 * 不是**改配置**⇒ ⇒ ⇒ 顺手写库 ⇒ ⇒ ⇒ ⇒ 用户下次进来发现默认变了、
 * 却不知道自己改过 ⇒ ⇒ ⇒ ⇒ 那就是「幽灵改动」。
 */
import { Select, Space, Tag, Tooltip, Typography } from 'antd';

import {
  conversionHint,
  type UnitAwareField,
  type UnitSystem,
} from '../../utils/units';

export interface UnitSystemSwitchProps {
  /** 当前生效的单位制（页面 state）。 */
  value: UnitSystem;
  /** 切换（**不写库**）。 */
  onChange: (next: UnitSystem) => void;
  /**
   * 当前页面上**可换算**的字段（用来生成提示文案）。
   *
   * ⚠️ **按实际量纲生成** ⇒ ⇒ ⇒ 不是一句固定的「1 bar = 100 kPa」
   * ⇒ ⇒ ⇒（US 是 psi 不是 bar ⇒ ⇒ ⇒ 那句话在 US 模式下是**错的**）。
   */
  fields?: UnitAwareField[];
  /** 项目默认值（切换过之后显示「项目默认：XX」）。 */
  projectDefault?: UnitSystem;
}

export function UnitSystemSwitch({
  value,
  onChange,
  fields = [],
  projectDefault,
}: UnitSystemSwitchProps): JSX.Element {
  const convertible = fields.filter(
    (f) => f.unit_display && f.unit_display.factor !== 0,
  );
  const hint =
    value === 'SI'
      ? null
      : convertible.length > 0
        ? conversionHint(convertible[0], value)
        : null;
  const nonConvertible = fields.filter(
    (f) => f.unit && (!f.unit_display || f.unit_display.factor === 0),
  );

  return (
    <Space size={12} wrap data-testid="unit-system-switch">
      <Typography.Text type="secondary">显示单位制</Typography.Text>
      <Select
        data-testid="unit-system-select"
        value={value}
        style={{ width: 140 }}
        onChange={(next: UnitSystem) => onChange(next)}
        options={[
          { value: 'SI', label: 'SI（kPa · ℃ · m）' },
          { value: 'US', label: 'US（psi · ℉ · ft）' },
        ]}
      />
      {projectDefault && projectDefault !== value ? (
        <Tag color="blue" data-testid="unit-system-override-tag">
          项目默认：{projectDefault}
        </Tag>
      ) : null}
      {hint ? (
        <Typography.Text type="secondary" data-testid="unit-system-hint">
          {hint}
        </Typography.Text>
      ) : null}
      {value !== 'SI' && nonConvertible.length > 0 ? (
        <Tooltip
          title={`这些字段没有换算因子（后端未下发）⇒ 按原值显示：${nonConvertible
            .map((f) => f.path)
            .join('、')}`}
        >
          <Tag color="default" data-testid="unit-system-no-conversion-tag">
            {nonConvertible.length} 个字段不换算
          </Tag>
        </Tooltip>
      ) : null}
    </Space>
  );
}

export default UnitSystemSwitch;
