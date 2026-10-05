# catalyst_loading 功能取消 — 该表不建，此功能先不做 (2026-10-05)

**状态**: ✅ **已取消** — `catalyst_loading` 表不建，催化剂装填量/寿命管理不纳入 P7
**裁决人**: 用户
**影响范围**: P7-OPEN-009 (R-02 方案 A) / P7 Sprint 2 T6 / Sprint 4 Task S4-4 / 5 表计划

---

## 一句话结论

用户裁决：**catalyst_loading 表取消，此功能先不做。** P7 的 UTIL 权威表清单从
原计划的 5 张变为 **6 张**（去掉 `catalyst_loading`，加上 P7-6B 收尾新增的
`utility_gas_media` / `utility_low_temp_heat`）。

---

## 被取消的内容

| 项 | 原计划 | 现状 |
|---|---|---|
| `catalyst_loading` 表 | 5 表计划第 5 张，存催化剂装填量 + 寿命管理 | ❌ **不建**（DB 中从未存在过，只在注释与文档中被提及） |
| T6 catalyst_loading fixture | 等工艺室 2026-10-15 签署的 `蜡油加氢—综合能耗.xlsx` 填数值 | ⛔ **随表取消而作废**，不再等待签署 |
| `auxiliary_consumption` 4 字段 | `electrical_power` / `fuel_gas_consumption` / `steam_consumption` / `cooling_water_consumption` | 归属待定（见下） |

**连锁解除的阻塞**：`BLOCKER-2`（`docs/PCS-NOTE-BLOCKER-2-2026-10-01.md`）
原本同时卡两件事 —— ① T6 catalyst_loading fixture ② Sprint 4 综合能耗验收
≤2% 无法判定。① 随本裁决**解除**；② 已由 T5 封版另行关闭（见
`docs/PCS-SIGN-T5-2026-10-05.md`，基准改为 GB 30251-2024 附录A 独立重算，
**不再依赖工艺室 2026-10-15 签署**）。

→ **BLOCKER-2 整体关闭。** 工艺室 2026-10-15 的 XLS 签署不再是任何在办项的前置条件。

---

## 权威表清单（现行 6 张）

| # | 表 | 单位 | 能源类别 | 来源 |
|---|---|---|---|---|
| 1 | `utility_power_items` | kWh | 电 (T1) | Sprint 2 |
| 2 | `utility_fuel_gas` | Nm³ | 燃料气 (T2) | Sprint 2 |
| 3 | `utility_heat_exchange` | t | 蒸汽 9 档 + 水 9 类 (T3) | Sprint 2 |
| 4 | `utility_gas_media` | Nm³ | 工艺气体 / 氮气 / 仪表空气 | **P7-6B 收尾 (e6efb24)** |
| 5 | `utility_low_temp_heat` | GJ | 低温余热回收 | **P7-6B 收尾 (e6efb24)** |
| 6 | `utility_energy_summary` | — | 综合能耗汇总 (T5) | Sprint 2 |

`util_results.consumption_json`（13 类 JSONB）按 D1 裁决 1A 保持 deprecated，
仅 backward compat 读，Sprint 2 起不再更新。

---

## 为什么取消不影响已封版的 T5

T5 验收基准已在 2026-10-05 重构为 **GB 30251-2024 附录A 表A.1 独立重算**
（`_gb30251_reference()`，不走 ORM / 不读 CONFIG 表 / 不调 service），
Case 4 蜡油加氢三项指标 PASS（0.0011% / 0.0000% / 0.0020%）。

原计划中「等工艺室 2026-10-15 签署的 XLS 填 fixture」的前提**已被用户裁决
「XLS 不作为最终依据」推翻**，所以 catalyst_loading 取消对 T5 结论**零影响**。

---

## 与 spec 基线的关系（按项目规则处理）

`spec/工艺专用综合计算软件需求规格说明书 Web版 P7.md` 与
`spec/PCS-REQ-2026-002-SUP-010...md` 仍写着 5 表 + `catalyst_loading`。

**按 `.wolf/cerebrum.md` 的文档规则「增补文件声明修改，不直接改基线；基线升版
显式请求才做」，本裁决以本文件作为增补声明，spec 基线暂不直接改动。**
若后续需要 spec 升版（V1.5），本文件 + `docs/PCS-UI-SPEC.md` §4.4 修订登记
（2026-10-05）应一并纳入升版输入。

---

## 同步更新的位置

| 位置 | 变更 |
|---|---|
| `pcs-backend/app/models/util.py` | 模块 docstring + `UtilResults` docstring 的表清单 5 → 6 张 |
| `pcs-backend/tests/test_schema.py` | `test_table_count` 期望 103（若将来不建 catalyst_loading 则维持） |
| `docs/superpowers/plans/2026-10-01-p7-complete-sprint.md` | R-02 / S4-4 / D1 裁决 1A / 收口项 |
| `.wolf/STATUS.md` | deferred 表 T6 项 + BLOCKER-2 相关项 |
| `docs/P7-NOTE-BLOCKER-2-2026-10-01.md` | 标注关闭 |
| `docs/P7-OPEN-009-SUP-010-5table-migration-schedule.md` | 加取消批注 |

**未改动**：`pcs-backend/alembic/versions/p7_s1_005_util_results.py:19` 的注释
提到 `catalyst_loading` —— migration 是历史记录，不回改。

---

## 遗留

`auxiliary_consumption` 4 字段（`electrical_power` / `fuel_gas_consumption` /
`steam_consumption` / `cooling_water_consumption`）原属 R-02 方案 A 的 6 项迁移
之一。取消 catalyst_loading 后这 4 字段的归属未定 —— 它们本意是把 4 类消耗量
冗余到 summary 行便于查询，而现有 6 张表已能通过聚合算出。**建议不做**，
待真有查询性能需求时再评估。

---

## 复现/验证

```bash
cd pcs-backend
# 确认 catalyst_loading 表从未存在
uv run python -c "
import asyncio,os;from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
async def m():
    e=create_async_engine(os.environ['DATABASE_URL'])
    async with e.connect() as c:
        r=await c.execute(text(\"select table_name from information_schema.tables where table_name like 'catalyst%'\"))
        print([x[0] for x in r] or '不存在 ✅')
    await e.dispose()
asyncio.run(m())"
uv run pytest tests/test_schema.py::test_table_count -q   # 103
```
