# G-06 火炬地面辐射热通量 BEDD 限值数据确认（占位；工艺室签字待补）

> **状态**：占位（开发/测试阶段）
> **提交**：P6-3 Task 29（2026-09-25）
> **Gate**：G-06（硬性前置；P6-3 批前必填）
> **数据归属**：CONFIG `flare_radiation_limits`（BEDD 限值元数据；flare `radiation_check` 读取）

## 一、当前值（API 521 §7.4.2.3 真实公开限值）

| limit_type      | q_kw_m2_limit | source              |
|-----------------|---------------|---------------------|
| PROPERTY_LINE   | 4.73          | API521_§7.4.2.3     |
| PERSONNEL       | 6.31          | API521_§7.4.2.3     |
| EMERGENCY       | 12.6          | API521_§7.4.2.3     |

> 注：本表 3 行 **非合成数据**；BEDD 三档限值直接引自 API 521 §7.4.2.3
> 公开标准（与 Task 22 `radiation_check` 当前硬编码值一致）。`source`
> 字段已写 `API521_§7.4.2.3`；`confirmed_by` / `confirmed_at` 待工艺室
> 签字后填入。

## 二、数据来源

- **API 521** = American Petroleum Institute, *Pressure-relieving and
  Depressuring Systems*，§7.4.2.3 *Radiation*：
  - **PROPERTY_LINE 4.73 kW/m²**（≈ 1500 Btu/hr·ft²）：财产线（持续
    30 min 不引起木材燃烧等财产损失）；
  - **PERSONNEL 6.31 kW/m²**（≈ 2000 Btu/hr·ft²）：人员持续暴露限
    值（穿适当工作服条件下可接受）；
  - **EMERGENCY 12.6 kW/m²**（≈ 4000 Btu/hr·ft²）：紧急疏散限值（短
    时暴露，不引起严重烧伤）。
- **与 Task 22 `radiation_check` 关系**：Task 22 当前在代码内硬编码
  以上 3 档；本表入库后，Task 30 可联动重构为 DB 读取（避免硬编码，
  便于工艺室按项目实际风险评估调整限值）。
- **本任务提交时的真实数据状态**：**已获取**（API 521 公开）；仅
  `confirmed_by` / `confirmed_at` 待工艺室签字。

## 三、替换触发条件（TODO）

满足以下任一条件即必须复核并同步更新本节：

1. **API 521 版本升级**（如 7th → 8th edition）：BEDD 限值变更时，
   工艺工程师复核 `q_kw_m2_limit` 是否变化，更新 `source` 字段加版
   本后缀（如 `API521_§7.4.2.3_Ed8`），并重新签字。
2. **项目特殊要求**：某些项目（海上平台 / 高人口密度区）可能要求更
   严限值；按项目追加新行（覆盖默认），保持 `(limit_type)` UNIQUE
   索引约束——此时需新增 `limit_type` 子类（如 `OFFSHARE_xxx`）或
   在后续批扩展 schema。
3. **国内 GB 标准覆盖**：若需符合 GB/T 31591 / SH/T 3008 等国内标
   准，由工艺室追加新行覆盖默认 BEDD 值。

替换操作路径：

```bash
cd pcs-backend
# 1. 修改 scripts/p6_3_gate_06_flare_radiation_limits_seed.py 内
#    SYNTHETIC_RADIATION_LIMITS 常量：
#    - q_kw_m2_limit 替换为复核后值
#    - source 字段加版本后缀（如 API521_§7.4.2.3_Ed8）
# 2. 执行 upsert：
uv run python scripts/p6_3_gate_06_flare_radiation_limits_seed.py
# 3. 在本节追加「工艺室签字」栏（见下方占位）。
```

## 四、工艺室签字（占位）

| 字段         | 值                                 |
|--------------|------------------------------------|
| 签字人       | _（待工艺室指定）_                 |
| 签字日期     | _（YYYY-MM-DD）_                   |
| 签字意见     | _（API 521 §7.4.2.3 标准值确认）_  |
| 数据期间覆盖 | API 521 现行版本（ED7 / ED8）      |
| 数据源       | API 521 §7.4.2.3                  |
| 下一版本触发 | _（YYYY-MM；API 521 新版发布时）_  |

## 五、相关 SPEC / 占位问题

- **P6-OPEN-007**（保留）："BEDD 限值是否需支持国内 GB 标准覆盖？"
  本占位文档即为该问题的具象化答复入口；工艺室首次签字后即可关闭
  P6-OPEN-007。
- **SUP-P5-PSV-002 PSV 安全阀选型说明**（P5 交付物）：未涉及火炬辐
  射热通量限值，本 gate 与 P5 PSV 选型无耦合。
- **Task 22 `radiation_check`**：当前硬编码 4.73 / 6.31 / 12.6 三档；
  Task 30 flare 模块迁移后，可联动重构为 DB 读取（本表为入口）。

## 六、相关代码锚点

- ORM：`pcs-backend/app/models/config.py::FlareRadiationLimits`
- 迁移：`pcs-backend/alembic/versions/p6_3_001_three_config_tables.py`
- 录入脚本：`pcs-backend/scripts/p6_3_gate_06_flare_radiation_limits_seed.py`
- 测试：
  - `pcs-backend/tests/models/test_p6_3_config_tables.py::test_flare_radiation_limits_init`
  - `pcs-backend/tests/scripts/test_p6_3_gate_06_seed.py`