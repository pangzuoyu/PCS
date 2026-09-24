# G-03 CEPCI 数据确认（占位；工艺室签字待补）

> **状态**：占位（开发/测试阶段）
> **提交**：P6-2 Task 17（2026-09-24）
> **Gate**：G-03（硬性前置；P6-2 批前必填）
> **数据归属**：CONFIG `cepci_index_series`（成本指数元数据，非业务计算记录）

## 一、当前值（合成数据占位）

| year | cepci_value | source                  |
|------|-------------|-------------------------|
| 2018 | 599.0       | SYNTHETIC_TEST_DATA     |
| 2019 | 607.5       | SYNTHETIC_TEST_DATA     |
| 2020 | 596.2       | SYNTHETIC_TEST_DATA     |
| 2021 | 708.8       | SYNTHETIC_TEST_DATA     |
| 2022 | 816.0       | SYNTHETIC_TEST_DATA     |
| 2023 | 797.9       | SYNTHETIC_TEST_DATA     |
| 2024 | 800.0       | SYNTHETIC_TEST_DATA     |

> 注：以上均为合成数据，仅用于开发 / 测试 / 演示。生产报价 / 工艺设计
> 不可使用。

## 二、数据来源（待工艺室签字后填入）

- **CEPCI 定义**：Chemical Engineering Plant Cost Index，Chemical
  Engineering 杂志每年第 4 季度发布。
- **真实数据获取路径**：工艺工程师订阅 Chemical Engineering 杂志或访问
  [https://www.chemengonline.com/pci](https://www.chemengonline.com/pci)
  获取年度指数。
- **本任务提交时的真实数据状态**：**未获取**（合成数据占位）。

## 三、替换触发条件（TODO）

满足以下任一条件即必须替换为真实数据并同步更新本节：

1. **P6-3 COST_EST 模块投产前**：COST_EST 首次报价用于真实项目时，本表
   `source` 字段必须全部改为 `Chemical Engineering Magazine YYYY-Q4`
   形式，且 `confirmed_by` / `confirmed_at` 由工艺室填写。
2. **工艺室首次签字触发**：工艺室接到 P6-3 投产任务时，统一一次性
   替换全部 7 行。
3. **新年度 CEPCI 发布**（每年 Q4）：追加新年度一行（保持 year
   UNIQUE 索引约束）；旧行不动。

替换操作路径：

```bash
cd pcs-backend
# 1. 修改 scripts/p6_2_gate_03_cepci_seed.py 内 SYNTHETIC_CEPCI 常量：
#    - cepci_value 替换为真实年度指数
#    - source 字段改为 "Chemical Engineering Magazine YYYY-Q4"
# 2. 执行 upsert：
uv run python scripts/p6_2_gate_03_cepci_seed.py
# 3. 在本节追加「工艺室签字」栏（见下方占位）。
```

## 四、工艺室签字（占位）

| 字段         | 值                                 |
|--------------|------------------------------------|
| 签字人       | _（待工艺室指定）_                 |
| 签字日期     | _（YYYY-MM-DD）_                   |
| 签字意见     | _（合成数据 / 真实数据切换声明）_  |
| 数据期间覆盖 | 2018~2024                          |
| 下一年度触发 | _（YYYY-MM；CEPCI 新版发布后）_    |

## 五、相关 SPEC / 占位问题

- **P6-OPEN-004**（保留）："成本指数（CEPCI）数据来源和更新频率？"
  本占位文档即为该问题的具象化答复入口；工艺室首次签字后即可关闭
  P6-OPEN-004。
- **SUP-P5-PSV-002 PSV 安全阀选型说明**（P5 交付物）：未涉及 CEPCI，
  本 gate 与 P5 PSV 选型无耦合。

## 六、相关代码锚点

- ORM：`pcs-backend/app/models/config.py::CepciIndexSeries`
- 迁移：`pcs-backend/alembic/versions/p6_2_gate_03_cepci_seed.py`
- 录入脚本：`pcs-backend/scripts/p6_2_gate_03_cepci_seed.py`
- 测试：`pcs-backend/tests/services/test_cepci_seed.py`
