# P7-OPEN-009 — SUP-010 5 表 + catalyst_loading + auxiliary_consumption 4 字段 迁移排期

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development.
> Steps use checkbox (`- [ ]`) syntax for tracking.

**排期日期**: 2026-10-01
**排期方**: 架构委员会（mock 排期，待真实会议确认）
**触发**: P7-REV-02 = 方案 A（纳入 P7 基线 +2-3 人周）
**关联**: P7 SPEC V1.4 §3.2.2（5）+ §4.5 P7-OPEN-009 + SUP-010 V1.1 §3.2.3 + §3.3.4

---

## 1. 迁移范围（6 项）

| # | 项 | 表/字段 | 数据来源 | 验收 |
|---|---|---|---|---|
| 1 | utility_power_items | 新增表（电耗设备清单）| PMS / 手动录入 | motor_power/operating_hours/annual_consumption/load_factor 4 字段 + CHECK 约束 |
| 2 | utility_fuel_gas | 新增表（燃料气）| PMS / 手动录入 | calorific_value/consumption/annual_consumption 3 字段 + 初期/末期/最大工况 |
| 3 | utility_heat_exchange | 新增表（蒸汽/冷凝水）| HEAT 汇总 | steam_pressure/steam_quality/return_condensate 3 字段 + 温度等级分类 |
| 4 | utility_energy_summary | 新增表（综合能耗汇总）| 1+2+3 聚合 | annual_total_energy/toe_conversion_factor/standard_coal_factor 3 字段 + 折标煤系数 from CONFIG |
| 5 | catalyst_loading | 新增表（催化剂装填量）| 蜡油加氢—综合能耗.xlsx + 惠州汽包实例 | volume/weight/density/bed_height 4 字段 + 寿命管理 |
| 6 | auxiliary_consumption | UTIL 主记录新增 4 字段 | SUP-008 §2.5 | electrical_power / fuel_gas_consumption / steam_consumption / cooling_water_consumption |

**数据来源总计**:
- 蜡油加氢—综合能耗.xlsx（已在 sample/，gitignored）
- 惠州汽包计算.xls（已在 sample/，gitignored）
- 工艺室 2026-10-XX 签署（**需提前到 10 月**，原 5D-2 时间窗 2026-11-15 提前）

**验收基准**: 综合能耗汇总与 Excel 偏差 ≤ 2%

---

## 2. 迁移链（alembic 顺序）

```
p7_open_009_001_utility_power_items
    ↓
p7_open_009_002_utility_fuel_gas
    ↓
p7_open_009_003_utility_heat_exchange
    ↓
p7_open_009_004_auxiliary_consumption_4fields (ALTER TABLE)
    ↓
p7_open_009_005_utility_energy_summary
    ↓
p7_open_009_006_catalyst_loading
```

**理由**:
- 1→2→3 顺序：基础数据先落（电耗 → 燃料气 → 热交换）
- 4 ALTER 落在 1+2+3 之后：auxiliary_consumption 字段依赖 1+2+3 聚合值
- 5 综合能耗汇总：依赖 1+2+3+4 完成
- 6 催化剂装填量：独立数据源（蜡油加氢—综合能耗.xlsx），最后落

---

## 3. 工时表（与 P7 SPEC V1.4 §4.6 对齐）

| 迁移项 | 工时 | 子任务 |
|---|---|---|
| 1 utility_power_items | 0.5 天 | ORM + alembic + 4 字段 + CHECK + seed 工艺室签署 |
| 2 utility_fuel_gas | 0.5 天 | 同上（3 字段 + 初期/末期/最大工况枚举）|
| 3 utility_heat_exchange | 0.5 天 | 同上（3 字段 + 温度等级分类）|
| 4 auxiliary_consumption 4 字段 | 0.3 天 | ALTER TABLE + 数据迁移脚本 + backward compat |
| 5 utility_energy_summary | 1.0 天 | ORM + alembic + 聚合 service + 折标煤系数 CONFIG + 验收 fixture |
| 6 catalyst_loading | 0.5 天 | ORM + alembic + 蜡油加氢 fixture + 寿命管理 |
| 工艺室 10 月签署 follow-up | 0.5 天 | 提前 schedule + 对账 |
| 单 commit + pytest + G-08 + ruff + pytest 回归 | 0.2 天 | 单 commit + 验证 |
| **小计** | **~4.0 工作日** | |

**P7 总工时**（含方案 A）：
- EQUIP_LIST: 2.5–3 人周
- UTIL 基线: 1.5–2 人周
- **UTIL 5 表 + catalyst_loading + auxiliary_consumption 4 字段: +2-3 人周**（本排期）
- EQUIP_LIB: 1–1.5 人周
- 供应商数据: 2–2.5 人周
- **总计**: **10–13 人周**（per P7 SPEC V1.4 §4.6 V1.4 修订 7）

---

## 4. 关键文件路径

- `pcs-backend/app/models/util.py`（新建，5 表 ORM 类）
- `pcs-backend/app/models/mixins.py`（auxiliary_consumption 4 字段追加）
- `pcs-backend/alembic/versions/p7_open_009_001_utility_power_items.py`
- `pcs-backend/alembic/versions/p7_open_009_002_utility_fuel_gas.py`
- `pcs-backend/alembic/versions/p7_open_009_003_utility_heat_exchange.py`
- `pcs-backend/alembic/versions/p7_open_009_004_auxiliary_consumption_4fields.py`
- `pcs-backend/alembic/versions/p7_open_009_005_utility_energy_summary.py`
- `pcs-backend/alembic/versions/p7_open_009_006_catalyst_loading.py`
- `pcs-backend/app/services/util/utility_power_service.py`
- `pcs-backend/app/services/util/utility_fuel_gas_service.py`
- `pcs-backend/app/services/util/utility_heat_exchange_service.py`
- `pcs-backend/app/services/util/utility_energy_summary_service.py`（含折标煤系数 CONFIG 集成）
- `pcs-backend/app/services/util/catalyst_loading_service.py`
- `pcs-backend/app/services/util/auxiliary_consumption_migration_service.py`（数据迁移）
- `pcs-backend/app/seeds/config_energy_conversion_factors.py`（CONFIG 折标煤系数 seed）
- `pcs-backend/app/api/v1/util.py`（扩展 6 端点）
- `pcs-backend/tests/services/util/test_*_service.py`
- `pcs-backend/tests/services/util/fixtures/golden_*.json`

---

## 5. 复用清单

| 现有 | 路径 | 复用任务 | 用法 |
|---|---|---|---|
| util_results 单表 + consumption_json JSONB | `pcs-backend/app/models/util.py`（既有）| 全部 | V1.3 基线已用，方案 A 新增 5 表并行存在；JSONB 容器保留作 backward compat |
| `Class.method` persist 模式 | `pcs-backend/app/services/psv/relief_area_service.py` | 全部 | 仿 P5-0 sibling |
| `APIRouter` + `require_roles` 模式 | `pcs-backend/app/api/v1/util.py` | 全部 | 仿 PRG §3.5 |
| 工艺室签署 fixture 模式 | `pcs-backend/tests/services/util/fixtures/golden_*.json` | 全部 | 类似 P5-0-1b T1 thermosiphon fixture 标注「工艺室 2026-10-XX 签署」|
| CONFIG 折标系数集成模式 | `pcs-backend/app/services/pasquill_sigma_service.py` | 5 utility_energy_summary | 仿 C-22 Pasquill-Gifford 系数 CONFIG 读取 + 缓存 |
| compound_* CONFIG 表 5-min TTL 缓存 | `pcs-backend/app/services/_compound_config_cache.py` | 5 utility_energy_summary | 仿 P6-5+ 折标系数缓存模式 |
| CHECK constraints 风格 | `pcs-backend/app/models/calc.py:586-605` MixerResult | 全部 5 表 | 数值范围 + enum 校验 |

---

## 6. 关键检查点

### 6.1 工艺室签署 schedule 提前

原 P6-9-PICKUP-6 5D-2 时间窗 = 2026-11-15。R-02=A 强制提前到 **2026-10-XX**：

- 2026-10-08: 工艺室初步对账（D + 0.5 天）
- 2026-10-15: 工艺室正式签署（D + 7 天，含工艺室内部 review）
- 2026-10-22: PCS 集成 fixture（D + 14 天）
- 2026-10-29: 收口 + 单 commit（D + 21 天）

**风险**: 工艺室 10 月签署 schedule 可能与既有 OPEN（OPEN-P6-6A-9.x）冲突 — 提前签署意味着工艺室需要并行处理 P6 + P7 两批请求。

### 6.2 验收 fixture 提前生成

蜡油加氢—综合能耗.xlsx + 惠州汽包计算.xls 数据需在迁移前导入 fixture：

- `pcs-backend/tests/services/util/fixtures/golden_utility_power_items.json`（≥10 算例）
- `pcs-backend/tests/services/util/fixtures/golden_utility_fuel_gas.json`（≥5 算例）
- `pcs-backend/tests/services/util/fixtures/golden_utility_heat_exchange.json`（≥5 算例）
- `pcs-backend/tests/services/util/fixtures/golden_utility_energy_summary.json`（≥3 算例，覆盖电/燃料/蒸汽/水/气体/低温余热六类）
- `pcs-backend/tests/services/util/fixtures/golden_catalyst_loading.json`（≥5 算例）

**验证**: 综合能耗汇总与 Excel 偏差 ≤ 2%（per SPEC-P7 §3.2.2（3）验收标准）

### 6.3 CONFIG 折标煤系数 seed

`pcs-backend/app/seeds/config_energy_conversion_factors.py`：

```python
# 伪代码 — 等工艺室签署后落实数值
SEED_DATA = [
    {
        "source": "GB_T_50441_APPENDIX",
        "energy_type": "ELECTRICITY",
        "toe_factor": 0.1229,  # kWh → kg 标油
        "standard_coal_factor": 0.1229,  # kWh → kg 标煤
        "confirmed_by": "工艺室 2026-10-XX",  # P7 启动前工艺负责人签字
    },
    # ... 6 类能源（电/燃料/蒸汽/水/气体/低温余热）
]
```

---

## 7. 验收矩阵

| # | 项 | 命令 | 期望 |
|---|---|---|---|
| M1 | utility_power_items ORM | `python -c "from app.models.util import UtilityPowerItem; print(len([f for f in UtilityPowerItem.__table__.columns]))"` | ≥ 13（含 RecordMixin）|
| M2 | alembic upgrade | `cd pcs-backend && DATABASE_URL=... uv run alembic upgrade head` | OK |
| M3 | utility_energy_summary 聚合 | `pytest tests/services/util/test_utility_energy_summary_service.py -q` | 偏差 ≤ 2% |
| M4 | CONFIG 折标煤系数 seed | `python -c "from app.seeds.config_energy_conversion_factors import SEED_DATA; print(len(SEED_DATA))"` | ≥ 6 |
| M5 | ruff + pytest | `cd pcs-backend && uv run ruff check .` + `pytest -q` | 0 errors + 全量 3515+ passed |
| M6 | G-08 phase 1-4 | `bash pcs-backend/scripts/gate_08_openapi_contract.sh --check-baseline` | baseline diff = 0 |

---

## 8. 风险 + 缓解

| 风险 | 等级 | 缓解 |
|---|---|---|
| 工艺室 2026-10-XX 签署 schedule 冲突 | 高 | T0 + T1 与 P6-9-PICKUP-6 5D-2 时间窗错开（D + 0/7/14/21 vs 11-15）；mock 排期给工艺室 14 天 review 缓冲 |
| 蜡油加氢 fixture 数值未签署 | 高 | 工艺室 2026-10-08 初步对账时同步提交；fixture 标注「工艺室 2026-10-XX 签署」 |
| CONFIG 折标煤系数 source = GB/T 50441 附录需工艺室确认 | 中 | seed 脚本中 `confirmed_by=NULL` 起步，工艺室签署后 fill |
| 综合能耗汇总 ≤2% 偏差 | 中 | utility_energy_summary service 内置容差校验，超差抛 `EnergyConsumptionToleranceError` |
| aux_consumption 4 字段 ALTER 现有 util_results 表 | 中 | 数据迁移脚本 + backward compat 默认值（NULL 起步；service 层 fallback）|

---

## 9. 后续

P7-OPEN-009 落地后：
- P7 Sprint 1 启动（5 表 service + API）
- P7 Sprint 2 启动（综合能耗验收 + 工艺室 review）

---

## 10. 关联

- 上游：P7 SPEC V1.4 §3.2.2（5）+ §4.5 P7-OPEN-009（裁决后状态）
- 下游：P7 Sprint 1+2 实施任务
- 关联 OPEN：OPEN-P6-6A-10（AS 1210 PDF 2026-11-15 — 不阻塞 5 表迁移，但同步对账）
- 兄弟决策：P7-REV-02 mock decisions（`docs/P7-REV-01-04-mock-decisions.md`）
