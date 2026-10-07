# §3.4 约束①② 的对比契约定义（2026-10-07）

**状态**: ✅ 契约已定义 + 覆盖率闸已落地（**非阻断式**，见下）
**关联**: `spec/PCS 本体论与语义关系研究说明（V1.6）.md` §3.4 约束①②③、
`pcs-backend/scripts/check_payload_model_coverage.py`

---

## 一句话结论

§3.4 约束②（ORM comment ↔ Pydantic `Field(description=...)` 静态对比、漂移即 fail）
**今天无法作为阻断闸落地** —— 因为它比对的两端有一端根本不存在：约束①要求的
「每个 `*_result` 表的 JSONB 载荷有对应的嵌套 Pydantic 模型」，实测 **21/29 张表
（72%）一个都没有**。

先把契约定义清楚，再把闸做成**覆盖率回归防护**（只拦倒退，不报现存欠账）。

---

## 现状实测（2026-10-07）

29 张 `*_result` / `*_results` 表，逐表对照 `app/schemas/` 下 192 个 Pydantic 模型：

| 表 | JSONB 列 | 对应 Pydantic 模型 |
|---|---|---|
| `pump_results` | 15 | ❌ 无 |
| `heat_results` | 9 | ❌ 无 |
| `sim_tower_results` | 6 | ❌ 无 |
| `psv_results` | 5 | ❌ 无 |
| `thermosiphon_circulation_results` | 5 | ❌ 无 |
| `cooling_tower_results` / `flare_system_results` / `flash_results` / `pipe_network_results` / `relief_results` | 各 3~4 | ❌ 无 |
| `mixer_results` / `piping_results` / `sep_equip_results` / `vessel_results` | 各 1~4 | ❌ 无 |
| `sim_*_results`（7 张） | 0~6 | ❌ 无 |
| `psychro_results` | 3 | `PsychroResultCreateRequest` / `Response` / `ListResponse` |
| `cv_results` | 3 | `CvCalculateRequest` / `CvCalculateResponse` |
| `util_results` | 1 | `UtilAggregationRequest` 等 |
| `cost_est_results` / `filtration_results` / `open_channel_results` / `restriction_results` | 1~3 | `*CreateRequest` / `*DeleteResponse` 等 |

### 约束② 的**两端**都没有实质性落地

| 端 | 实测 | 状态 |
|---|---|---|
| 载荷 Pydantic 模型（约束①） | **0 / 25 张表** | ❌ 完全没有 |
| ORM Column comment（约束② 的另一端） | **45 / 88 个 JSONB 列（51.1%）** | 🟡 约一半 |

88 个 JSONB 列里 **43 个 comment 是 `None`** —— 连「被比对方」都不存在。
典型：`heat_results` 的 9 个 JSONB 列中，`input_json` / `output_json` /
`air_side_json` / `design_conditions_json` / `enthalpy_table_json` **五个 comment 全空**，
只有 `shell_params` / `tube_params` / `ache_params` / `changed_fields` 有。

**所以 1b 的真实结论不是「加个检查」，而是「把一项没有落地的工作变成可测量、可回归的数字」。**

**两点必须说清**：

1. **上表「有模型」的 8 张也不是约束①要的东西。** 它们是 API 信封
   （`CreateRequest` / `Response` / `ListResponse` / `DeleteResponse`），
   不是「JSONB 载荷的嵌套模型」。约束①要的是后者 —— 即
   `heat_results.output_json` 该对应一个描述输出结构本身的模型。
2. **§3.4 自己举的例子是虚构的。** 原文写
   「如 `HeatResults.design_parameters → HeatDesignParametersSchema`」，而：
   - `HeatDesignParametersSchema` **全仓 0 命中**
   - `app.schemas.heat` 模块**不存在**（`heat_results` 有 9 个 JSONB 列，
     没有任何一个叫 `design_parameters`；实际叫 `design_conditions_json`）
   - `app/models/` 下也没有 `HeatResults` 这个类名（表模型叫 `HeatResult` 之类）

   → **SPEC 的示例描述的是一个从未存在过的模型。** 落地时不能照它抄。

---

## 对比契约（本次定义）

### 比什么

对 `*_result` / `*_results` 表的**每一个 JSONB 列**，要求存在一个**声明式登记**的
载荷 Pydantic 模型；当该模型存在时，其顶层 `description` 必须与该列的 ORM comment
**逐字相等**。

### 怎么关联 —— 显式登记表，不靠名字猜

模型与列的对应**写在代码里**（`scripts/check_payload_model_coverage.py` 顶部的
`_REGISTRY`），**不做任何命名推断**。

理由：本项目 29 张表的 JSONB 列命名高度不规则 —— 标准是 `input_json`/`output_json`，
但大量模块用专属名（`pump_results` 有 `basic_info_json` / `fluid_properties_json` /
`suction_calculation_json` … 共 15 个；`heat_results` 有 `shell_params` /
`tube_params` / `ache_params` 这些**不带 `_json` 后缀**的）。任何
`{表名驼峰}{列名驼峰}` 的推断规则都会在这里产生大量假阳性。

登记表显式 = 未登记就是欠账，一眼可见，且加模型时只需加一行。

### 阻塞还是 advisory

**只拦倒退，不报现存欠账。**

- 闸的退出码：`coverage >= 基线` → 0；`coverage < 基线`（有人删了已登记的模型，
  或改坏了一个已登记模型的 description）→ 1。
- 未登记的表**不计入违规**，只计入「欠账」并在报告里列出。

理由：本会话已经吃过一次教训 —— 幂等闸门长期用字符串窗口判 guard，恒报 0 violations，
是**假的绿**；反过来，一个从第一天就报几百条红、没人能修的闸，会被整体关掉，
是**狼来了**。两者都不该再犯。所以这里选第三条：**先把欠账量化成可下降的数字，
只保证它不涨。**

**这不等同于 SPEC 说的「漂移即 fail」** —— SPEC 那句的前提（约束①已落地）不成立。
约束①补齐后，本闸自然升级为对已登记项的强阻断。

### 与 alembic COMMENT 比对的关系

本闸**不经 PG**。`COMMENT ON` 是 alembic 管辖的 schema 元数据，与描述文本无关
（2026-10-07 用户裁决：注释不进契约，故已关掉 alembic 的 comment 比对）。
本闸读的是 **ORM Column comment ↔ Pydantic `description`**，两端都是 Python 源码。

---

## 落地物

- `pcs-backend/scripts/check_payload_model_coverage.py` —— 覆盖率闸（可运行）
- `pcs-backend/tests/scripts/test_check_payload_model_coverage.py` —— 回归测试
- 基线：**载荷模型 0/25 表、ORM comment 45/88 列**。每补一个模型，基线 +1；
  闸只允许升不允许降。
- 闸的输出同时报两个数字（后者即约束③ 要的「覆盖情况评审」，现在可测量了）：

  ```
  描述文本覆盖: 0/25 表 (0.0%)，已登记 0 项，欠账 25 张表
  ORM comment 覆盖: 45/88 个 JSONB 列 (51.1%) —— 约束② 的另一端
  ```

## 下一步（不在本项）

补约束① 本身 —— 21 张表的嵌套载荷模型。那是独立的一块工作量，
且需要逐模块确认 JSONB 的实际结构（不能从 ORM 列名反推）。
本闸的作用就是让这项工作的进度变成一个可测量、可回归的数字。