# G-05 过滤介质物性数据确认（占位；工艺室签字待补）

> **状态**：占位（开发/测试阶段）
> **提交**：P6-3 Task 29（2026-09-25）
> **Gate**：G-05（硬性前置；P6-3 批前必填）
> **数据归属**：CONFIG `filtration_media_library`（过滤介质物性元数据；FILTRATION 模块 Ruth / Ergun 计算读取）

## 一、当前值（合成数据占位）

| medium_type        | grade        | rating_um | alpha       | r0          | k_perm   | eps   | T_max | source              |
|--------------------|--------------|-----------|-------------|-------------|----------|-------|-------|---------------------|
| SAND               | #20-30       | 500.0     | NULL        | NULL        | 5.0e-11  | 0.40  | 80.0  | SYNTHETIC_TEST_DATA |
| ANTHRACITE         | #1.0mm       | 800.0     | NULL        | NULL        | 8.0e-11  | 0.50  | 100.0 | SYNTHETIC_TEST_DATA |
| CARBON             | F-400        | 25.0      | NULL        | NULL        | 2.0e-11  | 0.45  | 60.0  | SYNTHETIC_TEST_DATA |
| RUTH_FILTER_CLOTH  | PE-900       | 25.0      | 1.5e10      | 1.0e10      | NULL     | NULL  | 90.0  | SYNTHETIC_TEST_DATA |
| ERGUN_PACKING      | RASCHIG-25   | NULL      | NULL        | NULL        | 1.5e-9   | NULL  | 200.0 | SYNTHETIC_TEST_DATA |

> 注：以上均为合成数据，仅用于开发 / 测试 / 演示。生产过滤系统设计
> 不可使用；FILTRATION 模块在生产报价前必须由工艺室替换为厂商真实物性。

## 二、数据来源（待工艺室签字后填入）

- **介质大类覆盖**：5 大类 — SAND（砂滤）/ ANTHRACITE（无烟煤）/
  CARBON（活性炭）/ RUTH_FILTER_CLOTH（Ruth 滤饼过滤专用滤布）/
  ERGUN_PACKING（Ergun 深层过滤用 Raschig 环等填料）。
- **真实数据获取路径**：
  1. **SAND / ANTHRACITE / CARBON**：工艺工程师从介质供应商
     （Hydroflow / Culligan / 等）规格表 + 实验测定获取粒径分布 +
     渗透率 / 孔隙率；
  2. **RUTH_FILTER_CLOTH**：从滤布厂商（滤布供应商技术手册）获取
     恒压过滤参数（`alpha` / `r0`）；
  3. **ERGUN_PACKING**：从填料厂商（Raschig / Pall / 等）获取填料
     渗透率 / 孔隙率；
  4. 在 `source` 字段填写 datasheet 名称或内部编号（如
     `Hydroflow_SAND_#20-30_DS-2024` / `PE-900_TechManual-2023`）。
- **本任务提交时的真实数据状态**：**未获取**（合成数据占位）。

## 三、替换触发条件（TODO）

满足以下任一条件即必须替换为真实数据并同步更新本节：

1. **P6-3 FILTRATION 模块投产前**：FILTRATION 首次用于真实项目过滤
   设计时，本表 `source` 字段必须全部改为厂商 datasheet 名称，且
   `confirmed_by` / `confirmed_at` 由工艺室填写。
2. **新增介质型号 / 牌号**：追加新行（保持 `(medium_type, grade)`
   UNIQUE 索引约束）；旧行不动。
3. **介质厂商发布新版 datasheet**：新增版本行（`source` 字段加版本
   后缀）；旧版行保留供历史项目查询。

替换操作路径：

```bash
cd pcs-backend
# 1. 修改 scripts/p6_3_gate_05_filtration_media_library_seed.py 内
#    SYNTHETIC_FILTER_MEDIA 常量：
#    - rating_um / alpha / r0 / k_perm / eps / T_max 替换为真实物性
#    - source 字段改为厂商 datasheet 名称
# 2. 执行 upsert：
uv run python scripts/p6_3_gate_05_filtration_media_library_seed.py
# 3. 在本节追加「工艺室签字」栏（见下方占位）。
```

## 四、工艺室签字（占位）

| 字段         | 值                                 |
|--------------|------------------------------------|
| 签字人       | _（待工艺室指定）_                 |
| 签字日期     | _（YYYY-MM-DD）_                   |
| 签字意见     | _（合成数据 / 真实数据切换声明）_  |
| 数据期间覆盖 | 5 大介质类                         |
| 数据源       | 厂商 datasheet                     |
| 下一版本触发 | _（YYYY-MM；新 datasheet 发布时）_ |

## 五、相关 SPEC / 占位问题

- **P6-OPEN-006**（保留）："过滤介质物性库如何与厂商 datasheet 版本绑定？"
  本占位文档即为该问题的具象化答复入口；工艺室首次签字后即可关闭
  P6-OPEN-006。
- **SUP-P5-PSV-002 PSV 安全阀选型说明**（P5 交付物）：未涉及过滤介质
  物性，本 gate 与 P5 PSV 选型无耦合。
- **Task 33 / Task 34**：FILTRATION 模块 Ruth 恒压/恒速 + Ergun 深层
  过滤介质物性读取入口；Task 30 FILTRATION 模块迁移后启用。

## 六、相关代码锚点

- ORM：`pcs-backend/app/models/config.py::FiltrationMediaLibrary`
- 迁移：`pcs-backend/alembic/versions/p6_3_001_three_config_tables.py`
- 录入脚本：`pcs-backend/scripts/p6_3_gate_05_filtration_media_library_seed.py`
- 测试：
  - `pcs-backend/tests/models/test_p6_3_config_tables.py::test_filtration_media_library_init`
  - `pcs-backend/tests/scripts/test_p6_3_gate_05_seed.py`