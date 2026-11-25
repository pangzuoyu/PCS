"""单位制换算因子（P10-K · W-1 · SPEC §7.5 单位制切换）。

## 为什么**后端**拥有因子

前端**不该有换算表** ⇒ ⇒ ⇒ 一份表在前端、一份在后端 ⇒ ⇒ ⇒ **迟早漂**
⇒ ⇒ ⇒ 而且「后端新增了一个单位却忘了告诉前端」这件事**前端无从发现**
⇒ ⇒ ⇒ ⇒ 所以因子随 **ui-schema** 下发（`UiSchemaField.unit_display`）。

⚠️ **但这是「约定」不是「类型」** —— `ui_schema_service._FIELDS` 是**手写
dict** ⇒ ⇒ ⇒ 后端**能**新增一个带单位、却忘了填 `unit_display` 的字段
⇒ ⇒ ⇒ ⇒ 前端必须**明确**怎么办（**标灰 + 「该字段无换算」**）⇒ ⇒ ⇒
**不是**静默不换（W-19 的兵底）。

## 换算是**双向视图变换**，存储**恒为 canonical（SI）**

- 读路径：`canonical → display`（`display = canonical × factor + offset`）
- 写路径：`display → canonical`（`canonical = (display − offset) ÷ factor`）

⇒ ⇒ ⇒ **`form state` 保持 canonical** ⇒ ⇒ ⇒ **只在控件边界换算**
⇒ ⇒ ⇒ 否则每次保存时**未被编辑的字段**也会在末位比特上漂移。

## ⚠️ `unit_display` 说的是**哪一个**显示单位

canonical **恒为 SI** ⇒ ⇒ ⇒ 两个显示单位制里，**SI 那一侧是恒等变换**
⇒ ⇒ ⇒ ⇒ 所以 `unit_display` 只描述**非 SI（US）**那一侧：

| 显示单位制 | 变换 | 显示单位名 |
|---|---|---|
| SI | 恒等（`×1 + 0`）| canonical `unit` 本身（如 `kPa`）|
| US | `unit_display.factor / .offset` | `unit_display.display_unit`（如 `psi`）|

⇒ ⇒ ⇒ **缺 `unit_display`** = 这个字段**不可换算** ⇒ ⇒ ⇒ 前端标灰 + 提示。

## 哪些字段**不可换**（10 个）—— 为什么

| 字段 | 为什么不换 |
|---|---|
| 噪声 dB ×2 | **对数刻度** —— 换算是 `20·log10` 的仿射，**不是**线性乘法 ⇒ ⇒ ⇒ 乘个系数就错了 |
| 湿度 % | 百分比**无量纲** ⇒ ⇒ ⇒ 换它没有物理意义 |
| 雷暴 d/a · 雾 d/a · 日照 h/a | **年计数**（不是速率）⇒ ⇒ ⇒ 换的是「每年几次」⇒ ⇒ ⇒ 无意义 |
| 太阳辐射 W/m² · 辐射 kW/m² | 辐射**热流**与单位制无关（英制工程里也用 W/m²）⇒ ⇒ ⇒ 且面积换算会引入力单位问题 |
| 加速度 g | `g` **本身**就是「标准重力加速度」⇒ ⇒ ⇒ 已是量纲无关的相对量 |
| 设计寿命 a | 年 ⇒ ⇒ ⇒ 英制工程也用年 |

⇒ ⇒ ⇒ **35 个无单位字段**（蒸汽 / 水 / 空气 / 介质与类别）**本来就没有数可换**。

## 精度

往返（canonical → display → canonical）的相对误差上界 **≤ 1e-9**
⇒ ⇒ ⇒ ⚠️ 断言**要带容差** ⇒ ⇒ ⇒ 验收例子：**14.5 psi = 99.97 kPa**
（**不是 100** —— `14.5 × 6.894757293168361 = 99.973980746…`）。
"""

from __future__ import annotations

from dataclasses import dataclass

#: 1 psi 的精确定义（磅每平方英寸）= 6894.757293168361 Pa
PSI_IN_KPA = 6.894757293168361
#: 1 ft 的精确定义 = 0.3048 m
FT_IN_M = 0.3048
#: 1 in 的精确定义 = 0.0254 m
IN_IN_M = 0.0254


@dataclass(frozen=True)
class UnitDisplay:
    """canonical(SI) → **US 显示** 的线性变换。

    `display = canonical × factor + offset`
    """

    factor: float
    offset: float
    display_unit: str


#: 字段路径（`分组.字段`）→ US 显示变换。
#:
#: ⚠️ **键是路径而不是单位** ⇒ ⇒ ⇒ 因为「同一个单位是否可换」是**字段级**
#: 的判断（今天的 8 个可换字段的单位互不重复，但那是**巧合**⇒ ⇒ ⇒
#: 按路径写 ⇒ ⇒ ⇒ 将来某个字段与另一个字段共用单位、却只有一边可换
#: ⇒ ⇒ ⇒ **不会**被这张表悄悄连坐）。
US_DISPLAY: dict[str, UnitDisplay] = {
    # 气温：偏移型（℃ → ℉ 要 ×9/5 再 +32 ⇒ ⇒ ⇒ **不是**纯乘法）
    "meteorology.temperature": UnitDisplay(9.0 / 5.0, 32.0, "degF"),
    # 气压 / 背压：kPa → psi（纯比例）
    "meteorology.pressure": UnitDisplay(1.0 / PSI_IN_KPA, 0.0, "psi"),
    "flare.back_pressure": UnitDisplay(1.0 / PSI_IN_KPA, 0.0, "psi"),
    # 风速：m/s → ft/s
    "meteorology.wind": UnitDisplay(1.0 / FT_IN_M, 0.0, "ft/s"),
    # 海拔：m → ft
    "meteorology.altitude": UnitDisplay(1.0 / FT_IN_M, 0.0, "ft"),
    # 降雨 / 雪 / 蒸发：mm/a → in/a（年降水量，线性）
    "meteorology.rainfall": UnitDisplay(1.0 / (IN_IN_M * 1000.0), 0.0, "in/a"),
    "meteorology.snowfall": UnitDisplay(1.0 / (IN_IN_M * 1000.0), 0.0, "in/a"),
    "meteorology.evaporation": UnitDisplay(1.0 / (IN_IN_M * 1000.0), 0.0, "in/a"),
}


def unit_display_for(path: str) -> UnitDisplay | None:
    """字段路径 → US 显示变换；**不可换算** ⇒ ⇒ `None`。"""
    return US_DISPLAY.get(path)


__all__ = [
    "FT_IN_M",
    "IN_IN_M",
    "PSI_IN_KPA",
    "US_DISPLAY",
    "UnitDisplay",
    "unit_display_for",
]
