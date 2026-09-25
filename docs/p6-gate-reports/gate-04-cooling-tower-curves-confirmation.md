# G-04 冷却塔特性曲线数据确认（占位；工艺室签字待补）

> **状态**：占位（开发/测试阶段）
> **提交**：P6-3 Task 29（2026-09-25）
> **Gate**：G-04（硬性前置；P6-3 批前必填）
> **数据归属**：CONFIG `cooling_tower_curves`（冷却塔特性曲线元数据；OPEN_CHANNEL Merkel 冷却塔读取）

## 一、当前值（合成数据占位）

| tower_model       | curve_source | C    | m    | L/G_min | L/G_max | source              |
|-------------------|--------------|------|------|---------|---------|---------------------|
| MARLEY-MD-STD     | CTI          | 1.85 | 0.50 | 0.5     | 3.0     | SYNTHETIC_TEST_DATA |
| HAMON-FCC-STD     | CTI          | 2.10 | 0.55 | 0.6     | 2.8     | SYNTHETIC_TEST_DATA |
| EVAPCO-LS-STD     | CTI          | 1.95 | 0.52 | 0.7     | 3.5     | SYNTHETIC_TEST_DATA |
| BALTIMORE-TX-STD  | CTI          | 2.05 | 0.48 | 0.5     | 3.2     | SYNTHETIC_TEST_DATA |

> 注：以上均为合成数据，仅用于开发 / 测试 / 演示。生产工艺设计
> 不可使用；OPEN_CHANNEL 模块在生产报价前必须由工艺室替换为 CTI 真实
> 公开参数。

## 二、数据来源（待工艺室签字后填入）

- **CTI ATC-105** = Cooling Technology Institute, *Acceptance Test Code
  for Water-Cooling Towers*，ED7（含 KaV/L = C × (L/G)^(−m) 通用参数）。
- **真实数据获取路径**：
  1. 工艺工程师订阅 CTI 会员资格获取 ATC-105 ED7 PDF；
  2. 或从厂商（Marley / Hamon / Evapco / Baltimore Aircoil 等）官方
     产品 datasheet 提取对应型号的 C/m 系数 + L/G 适用区间；
  3. 在 `source` 字段填写具体期号 / datasheet 名（如
     `CTI_ATC-105_ED7_Table-3` / `Marley_MD-Series_DS-2024`）。
- **本任务提交时的真实数据状态**：**未获取**（合成数据占位）。

## 三、替换触发条件（TODO）

满足以下任一条件即必须替换为真实数据并同步更新本节：

1. **P6-3 OPEN_CHANNEL 模块投产前**：OPEN_CHANNEL 首次用于真实项目冷
   却塔选型时，本表 `source` 字段必须全部改为 `CTI_ATC-105_ED7_Table-3`
   或厂商 datasheet 名称，且 `confirmed_by` / `confirmed_at` 由工艺室
   填写。
2. **新增冷却塔型号**：追加新行（保持 `(tower_model, source)` UNIQUE
   索引约束）；旧行不动。
3. **CTI ATC-105 版本升级**：ED7 → ED8 时，新增版本行（`source` 字
   段加版本后缀）；旧版行保留供历史项目查询。

替换操作路径：

```bash
cd pcs-backend
# 1. 修改 scripts/p6_3_gate_04_cooling_tower_curves_seed.py 内
#    SYNTHETIC_CTI_CURVES 常量：
#    - C / m 系数替换为真实值
#    - L/G_min / L/G_max 替换为真实适用区间
#    - source 字段改为 "CTI_ATC-105_ED7_Table-3" 或厂商 datasheet 名
# 2. 执行 upsert：
uv run python scripts/p6_3_gate_04_cooling_tower_curves_seed.py
# 3. 在本节追加「工艺室签字」栏（见下方占位）。
```

## 四、工艺室签字（占位）

| 字段         | 值                                 |
|--------------|------------------------------------|
| 签字人       | _（待工艺室指定）_                 |
| 签字日期     | _（YYYY-MM-DD）_                   |
| 签字意见     | _（合成数据 / 真实数据切换声明）_  |
| 数据期间覆盖 | 4 个通用 CTI 型号                  |
| 数据源       | CTI ATC-105 ED7 / 厂商 datasheet   |
| 下一版本触发 | _（YYYY-MM；ATC-105 版本升级时）_  |

## 五、相关 SPEC / 占位问题

- **P6-OPEN-005**（保留）："冷却塔特性曲线系数库如何与厂商型号版本绑定？"
  本占位文档即为该问题的具象化答复入口；工艺室首次签字后即可关闭
  P6-OPEN-005。
- **SUP-P5-PSV-002 PSV 安全阀选型说明**（P5 交付物）：未涉及冷却塔特
  性曲线，本 gate 与 P5 PSV 选型无耦合。
- **Task 24 `calc_tower_curve_kav_l`**：本表 `(C, m)` 系数读取入口；
  Task 30 OPEN_CHANNEL 模块迁移后启用。

## 六、相关代码锚点

- ORM：`pcs-backend/app/models/config.py::CoolingTowerCurves`
- 迁移：`pcs-backend/alembic/versions/p6_3_001_three_config_tables.py`
- 录入脚本：`pcs-backend/scripts/p6_3_gate_04_cooling_tower_curves_seed.py`
- 测试：
  - `pcs-backend/tests/models/test_p6_3_config_tables.py::test_cooling_tower_curves_init`
  - `pcs-backend/tests/scripts/test_p6_3_gate_04_seed.py`