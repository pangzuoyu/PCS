---
status: accepted
date: 2026-09-15
revised: 2026-09-16
accepted_date: 2026-09-16
version: V1.1
supersedes: V1.0 (2026-09-15 proposed，2026-09-16 由 V1.1 修订)
accepted_by: P5 架构评审委员会
---

# PSV 多标准引擎：项目级显式配置 + 双路径隔离 + 公式溯源

PSV 模块（Task 13/14/16/17）同时承担 API 体系（API 521/520/526）与 GB 体系（GB/T 150.1、GB/T 12241、GB/T 28778、HG/T 20570.2）两类工艺室日常计算。若不显式区分标准，将出现同一项目内 API/GB 结果混存、lineage 无法解释、record_hash 无法区分标准差异、P6 FLARE_SYS 拿到混合口径数据等问题。

本 ADR 记录 PSV 多标准引擎的 12 项架构裁决（决策 10 拆分为 10a 门禁 + 10b 校验调用点）。SUP-P5-PSV-001 V1.0（2026-09-15 批准）是其需求侧锚点；本 ADR 是其架构落地侧锚点。两者须同步评审。

决定：**项目级显式配置 + 双路径完全隔离 + 公式条款级溯源 + 禁止隐式回退**。

---

## V1.1 修订说明（2026-09-16）

V1.0 决策 11 中 GB 路径 3 行阈值写"由工艺室确认"，未给具体数字。2026-09-16 经工艺室邮件核验 + 标准对比分析（详见 `docs/adr/signatures/0028-v1.1-标准对比分析.md`），决策 11 修订为分层阈值三表（火灾 / 泄放面积 / 两相流）。其余 11 项决策内容不变。

**V1.1 修订清单**：

| 决策 | V1.0 | V1.1 修订 |
|---|---|---|
| 决策 11 | "由工艺室确认"（无具体数字） | 分层阈值三表（火灾 ≤2%/≤5% + 泄放面积 ≤2%/≤5% + 两相流 ≤5%） |
| 其余 11 项（决策 1-10b） | — | 不变 |

**V1.1 修订落地**：

- 新增归档：`docs/adr/signatures/0028-v1.1-工艺室联签.md`（工艺室 + 标准负责人联签邮件）
- 新增归档：`docs/adr/signatures/0028-v1.1-标准对比分析.md`（API 521 vs GB/T 150.1 附录 B 三处差异数值分析）
- SUP 同步：SUP-P5-PSV-001 §7 验收表 GB 分支行按分层阈值三表展开（与本 ADR 联合评审，详见决策 11 落地路径第 1 条）
- P5 计划同步：Task 13 / Task 14 / Task 16 / Task 17 测试基线按三表分层各自独立写 golden
- 关联：V1.8 计划裁决 #11 中"P5-0-2 完成后追加 heat_results"措辞同步作废（`heat_results` 为 P4 已存在表）

**V1.1 落地核验（2026-09-16 工艺室 + 标准负责人联签）**：

工艺室邮件核验 + 标准对比分析（API 521 vs GB/T 150.1 附录 B 润湿面积 / 修正系数 / 公式结构三处差异的数值分析）→ 决策 11 分层阈值三表签字生效。

---

## 决策

### 决策 1：项目级显式配置标准 profile（D-02 / P5-OPEN-00X 关闭）

PSV 计算标准在项目级定义，不依赖代码隐式默认。

- 三类 `PsvStandardProfileCode = Literal["API", "GB", "CUSTOM"]`
- 同一 `(project_id, discipline)` 在同一时间只能有一个 `is_default = TRUE`
- 项目未配置 PSV 标准 → 计算请求 `422 PSV_STANDARD_NOT_CONFIGURED`，**禁止自动使用 API 作为默认**
- 请求可覆盖项目默认，但需权限校验并记录审批依据 → 无权限 `403 PSV_STANDARD_OVERRIDE_FORBIDDEN`

替代方案：全局默认 API，未配置项目走 API——否决。GB/T 150.1 附录 B 与 API 521 在火灾工况下润湿面积、修正系数、公式结构三处存在实质差异，混存会导致 P6 汇总失真。

### 决策 2：API/GB 双路径完全隔离（StandardResolver 注入）

API 路径和 GB 路径的计算逻辑完全隔离，各自拥有独立的函数与测试基准。

- 新增 `app/services/psv/standard_resolver.py` 的 `StandardResolver.resolve(project_id, discipline="PSV") -> PsvStandardProfile`
- 解析后的标准由调用方**注入**计算函数签名（`calc_fire_case(inp, standard)` / `calc_relief_area(inp, standard)` / `calc_orifice(inp, standard)`），不在函数内部用 `if standard == "GB"` 做分支
- Task 13/14/16/17 接口同步增加 `standard` 参数

替代方案：在 service 层用 if/else 分支——否决。分支逻辑会让 API 521 修正项（C 值、ω 法）与 GB/T 150.1 附录 B 公式交叉污染，难以独立演进与回归。

### 决策 3：公式溯源条款级记录（formula_ref clause-level）

每条计算记录必须写入 clause 级 formula_ref，记录具体子标准 + 版本 + 条款号。

- 基础字段：`(standard, version, clause)`。`version` 与 `standard` 后缀年份（如 `GB_T_150.1-2024`）冗余——`version` 单列保留是为下游按版本筛选索引方便，权威值以 `standard` 字段后缀为准
- TypedDict 集中定义于 `app/services/psv/formula_ref_types.py`，四个完整定义：
  - `FireCaseFormulaRef`：(standard, version, clause, drained: Optional["adequate"|"inadequate"]) — GB 火灾扩展字段
  - `ClosedValveFormulaRef`：(standard, version, clause, supplement: Optional[str]) — HG/T 20570.2-1995 标注"基于工程经验补充"
  - `ReliefAreaFormulaRef`：(standard, version, clause, omega_method: Optional["single_point"|"two_point"|"direct_integration"], two_phase_inherited_from: Optional[str]) — 两相流继承来源
  - `OrificeFormulaRef`：(standard, version, clause, orifice_table_status: Optional["complete"|"incomplete_fallback"], note: Optional[str]) — 孔口表完整度 + 备注
- 写 `psv_results.formula_ref_json` 与 `DataLineage.payload`，供 P6 FLARE_SYS 跨标准溯源

替代方案：仅写 `standard_refs_json` 整体——否决。条款级缺失时，工艺室复核 PSV 结果无法定位到具体公式段落（如 GB/T 12241-2021 §7.4 排量系数 vs §8 孔口确定）。

### 决策 4：record_hash 必须包含标准字段（跨标准隔离）

record_hash 计算输入必须包含标准 profile + 子标准版本，不同标准的同一输入产生不同 hash。

```python
PSV_RECORD_HASH_FIELDS: tuple[str, ...] = (
    "project_id",
    "standard_profile_code",   # API / GB / CUSTOM 区分
    "standard_refs_json",       # 子标准版本差异（GB_T_12241-2021 vs 2011）
    "input_json",
    "output_json",
)
```

- Task 18 RED 五段独立断言（分别 mutate 每字段验证 hash 各不同）
- 同一容器按 API vs GB 计算 → 两条独立记录 + 互不覆盖

替代方案：record_hash 仅含 input/output——否决。lineage 无法区分标准差异，P6 火炬汇总会把混合口径数据合并。

### 决策 5：CUSTOM profile 审批四眼原则（D-02）

`profile_code = 'CUSTOM'` 时必须满足：

- `approval_json` 必填：含 `approved_by`（用户姓名）+ `reason`（审批依据）+ `approved_at`（ISO 时间戳）
- `approved_by`（DB 列，BIGINT REFERENCES users(id)）：CUSTOM 时 NOT NULL
- **四眼原则**：`approved_by != created_by`，同人提交时 `422 PSV_CUSTOM_PROFILE_SELF_APPROVAL_FORBIDDEN`
- **API 层前置校验**：DB CHECK 仅兜底（IntegrityError → 500），不直接暴露给 API；`StandardResolver` / `psv_persist` 服务层前置校验，违反时 raise `PsvCustomProfileSelfApprovalForbiddenError(422)`

替代方案：仅 DB CHECK，无 API 层校验——否决。DB 层 IntegrityError 返回 500 不暴露业务错误码，前端难以给出可读提示。

### 决策 6：GB/T 150.1 双版本策略（D-03 / P5-OPEN-00Y 关闭）

GB/T 150.1 现行有效版本为 2024 版（代替 2011 版）。项目级显式选择：

- 新项目默认 `version="2024"`（推荐，附 B 修订包含球罐更严要求）
- 历史项目迁移可保持 `version="2011"` + `migrated_default=true` 标记，需复核
- 配置时必须锁定具体版本，不得使用"GB/T 150.1"模糊引用

替代方案：仅支持 2024 版，历史项目强制升级——否决。2011 版项目在过渡期仍需保留计算能力，强制迁移会导致历史记录无法复核。

### 决策 7：GB 路径两相流方法转 P5+（D-06 / P5-OPEN-00W 关闭）

P5 阶段 GB 路径两相流**始终委托** API 路径（无"若缺失"条件分支；委托是 P5 显式选择，非 fallback）：

- Task 16 GB 路径 `calc_relief_area_gb12241(inp)` 遇到 `medium="TWO_PHASE"` 时，**显式调用 `calc_relief_area_api520(inp)` 重新计算**（传入相同 ReliefAreaInput；非函数引用，是实际调用以保证 record_hash 输入一致）
- 结果写入 `formula_ref_json.two_phase_inherited_from = "API_520"` 标注计算引擎来源
- `standard_profile_code` 保持为 "GB"（项目配置优先），不写 "API"
- `DataLineage.payload.notes` 明确"计算引擎与 profile 不一致"
- DIERS 积分法完整实现转 P5+

替代方案：P5 阶段同步实现 DIERS 积分法——否决。DIERS 涉及 ω 法多版本、数值积分路径，文献推荐保守取值（如 Omega-1），实现工作量远超单 task 范围。

### 决策 8：GB/T 28778-2023 先导式阀转 P5+（D-07 / P5-OPEN-00V 关闭）+ Task 18 拦截

先导式安全阀（GB/T 28778-2023）不纳入 P5 范围，但必须**显式拦截**避免静默失败：

- `pilot_operated` 配置项保留但 `enabled=false`
- **Task 18 增加前置校验**：所有 `POST /api/v1/psv/calculate-*` 端点在调 StandardResolver 之后、调计算函数之前：
  - 若请求 `valve_type == "PILOT_OPERATED"` 且项目 profile 的 `pilot_operated.enabled == False`
  - → raise `PsvPilotOperatedNotSupportedError(422 PSV_PILOT_OPERATED_NOT_SUPPORTED)`
  - 响应体含 `upgrade_hint: "先导式阀计算 P5+ 实施，请联系标准负责人评估升级路径"`
- **新增测试 2 例**（并入 Task 18 测试套件）：
  - `test_pilot_operated_request_returns_422` — 先导式阀请求 + 项目配置 `enabled=false` → 422 + 错误码断言 + upgrade_hint 存在性
  - `test_spring_loaded_request_passes_through` — 弹簧式阀请求 + 同样配置 → 正常计算（不受拦截）

替代方案：仅保留配置项 enabled=false，无 API 层拦截——否决。无拦截时工艺室调用先导式阀计算会得到"未知设备类型"或"pilot_operated.enabled=false"等隐式错误，无明确错误码与升级指引。显式 422 与 G1/G2/G3 错误码风格一致。

### 决策 9：GB/T 12241 孔口表降级（D-04 / P5-OPEN-00Z 关闭）

GB/T 12241-2021 §8 安全阀尺寸的确定所需孔口表完整录入转 P5+。

- P5 阶段 GB 路径孔口选型降级：`orifice_table_status="incomplete_fallback"`
- 按计算面积输出**所需流道直径**（mm），不强制圆整到标准孔口
- `OrificeFormulaRef.note` 标注"P5 阶段降级：按计算面积输出流道直径，未圆整到标准孔口"
- P5+ 完整录入后再做圆整逻辑

替代方案：P5 阶段硬编部分孔口值——否决。工艺室实际项目孔口档位组合多，硬编数据缺乏标准维护流程，遗留技术债。

### 决策 10a：6 道门禁规则（G1-G6）

| 编号 | 规则 | 响应 |
|---|---|---|
| G1 | 项目未配置 PSV 标准 → 计算 | 422 `PSV_STANDARD_NOT_CONFIGURED` |
| G2 | 请求覆盖项目默认但无权限 | 403 `PSV_STANDARD_OVERRIDE_FORBIDDEN` |
| G3 | CUSTOM profile 缺少审批依据 | 422 `PSV_CUSTOM_PROFILE_APPROVAL_REQUIRED` |
| G4 | 同一输入跨标准计算 | 两条独立记录，record_hash 不同 |
| G5 | 标准配置变更 | 旧记录不自动重算，标记 `pending_review` |
| G6 | 历史项目迁移 | 写入 API 默认 + `migrated_default=true`，要求复核 |

### 决策 10b：校验调用点（双重防护 + 可观测性）

`validate_relief_area_formula_ref()` 在两处调用，形成双重防护：

- **Task 16 service 层** `calc_relief_area()` 返回前：调 `validate_relief_area_formula_ref()`
- **Task 18 persist 层** `finalize_calc_record()` 写入 DB 前：再调一次（防止绕过 Task 16 直接构造记录）

校验失败行为：

- raise `PsvFormulaRefInconsistencyError`（GB 两相流 standard 错配场景）
- 附加 `logger.error(extra={"project_id", "record_id", "ref"})` —— 持久化定位 + 运维可观测
- 附加 `PSV_FORMULA_REF_INCONSISTENCY_COUNTER.inc()` —— Prometheus 指标，可接入告警

### 决策 11：验收基准——GB 分层阈值 + 独立 golden

每个标准必须独立 golden，不能共用阈值。SUP-P5-PSV-001 §7 锁定的 15 例门禁测试须独立存在。V1.1 修订背景与联签信息见头部 ## V1.1 修订说明（2026-09-16）段；本节给出分层阈值三表正文：

**核心声明（不可推翻）**：

GB/T 150.1 附录 B 与 API 521 在火灾工况下存在三处结构性差异——
1. **润湿面积计算**：GB 对液位高度和封头形状的处理与 API 的 π·D·H 不同
2. **容器外壁修正系数**：反映保温层或防火层对热输入的衰减，GB 与 API 取值规则不同
3. **公式结构**：GB 附录 B 的火灾热输入公式虽与 API 521 同源（均基于汽化潜热法），但推导边界条件不同

→ 同一台容器按两套标准计算的泄放量结果差异**不是单位换算可以消除**，**不应作为验收对比基准**。

**层级 1：火灾工况（GB/T 150.1 附录 B.1.3）**

| 对比基准 | 建议阈值 | 依据 |
|---|---|---|
| GB 标准算例（标准原文例题） | **≤2%** | 标准原文例题是精确复现的基准，偏差应极小 |
| 工艺室手算（有明确计算书） | **≤5%** | 手算存在舍入、查图误差；5% 来自 GB/T 12241-2021 对排量试验重复性 ±5% 的要求 |
| 商业软件 GB 模块（如 HYSYS GB 算法） | **≤5%** | 软件实现细节差异 + 物性数据源差异 |
| 与 API 521 结果对比 | **不设阈值，仅记录偏差** | 两者计算路径不同，偏差是预期内，不应作为验收标准 |

**层级 2：泄放面积（GB/T 12241-2021）**

| 对比基准 | 建议阈值 | 依据 |
|---|---|---|
| GB 标准算例 | **≤2%** | 标准原文例题 |
| 工艺室手算 | **≤5%** | 与火灾工况一致 |
| 安全阀厂家选型报告 | **≤5%** | 厂家选型通常比计算略保守 |

GB/T 12241 对排量试验测量误差要求 ±2% / 排量系数重复性 ±5%，可直接作为 GB 路径验收工程基准。

**层级 3：GB 两相流（复用 API 结果）**

建议 **≤5%**，与 API 路径一致。原因：GB 路径两相流在 P5 阶段是"复用 API 结果"（决策 7：GB 两相流转 P5+），实际计算引擎仍是 API 520，偏差来源与 API 路径相同。

**GB/T 28778 先导式**（保持 V1.0 表述）：P5+ 再定（决策 8：D-07 关闭）。

**修订落地路径**：

1. SUP-P5-PSV-001 §7 验收表 GB 分支行（GB/T 150.1 附录 B 火灾 / GB/T 12241 泄放面积）按分层阈值三表展开
   （SUP 修订由需求负责人同步进行，与 ADR-0028 V1.1 联合评审；ADR 侧不单方面修改 SUP）
2. P5 计划中以下 task 的 GB 阈值引用同步更新：
   - Task 13（火灾工况）测试基线
   - Task 14（其他工况）GB 路径测试
   - Task 16（泄放面积）GB 路径测试
   - Task 17（孔口选型）GB 降级路径测试
3. Task 13 / Task 14 / Task 16 / Task 17 测试基线按三表分层各自独立写 golden
4. 工艺室 + 标准负责人联签邮件归档至 `docs/adr/signatures/0028-v1.1-工艺室联签.md`

## 影响

- **新表** 1 张：`project_calculation_standard_profiles`
- **加列**：`psv_results` / `relief_results` 各加 `standard_profile_code` / `standard_refs_json` / `formula_ref_json`（P5-3 实施后 NOT NULL）
- **新文件** 9 个（含迁移 + ADR + 校验测试 + 决策 11 联签归档）：
  - `alembic/versions/p5_psv_standard_profiles.py` — 新表迁移（仅加列 + 默认值，NOT NULL 由 Task 18 强制）
  - `app/services/psv/standard_resolver.py` — 标准解析层
  - `app/services/psv/formula_ref_types.py` — TypedDict 集中定义 + 校验函数
  - `tests/models/test_psv_standard_profile.py` — 模型层测试
  - `tests/services/psv/test_standard_resolver.py` — 解析层测试
  - `tests/services/psv/test_relief_area.py` — 含 formula_ref 校验测试（不单独建 test_formula_ref_validation.py，避免碎片化）
  - `docs/adr/0028-psv-multi-standard-engine.md` — 本 ADR 本身
  - `docs/adr/signatures/0028-v1.1-工艺室联签.md` — 决策 11 GB 分层阈值工艺室 + 标准负责人联签邮件归档
  - `docs/adr/signatures/0028-v1.1-标准对比分析.md` — 决策 11 修订依据：API 521 vs GB/T 150.1 附录 B 润湿面积 / 修正系数 / 公式结构三处差异的数值分析工作底稿
- **新枚举** 1 个：`PsvStandardProfileCode`
- **新异常** 6 个：`PsvStandardNotConfiguredError` / `PsvStandardOverrideForbiddenError` / `PsvCustomProfileApprovalRequiredError` / `PsvCustomProfileSelfApprovalForbiddenError` / `PsvFormulaRefInconsistencyError` / `PsvPilotOperatedNotSupportedError`
- **新 metric** 1 个：`PSV_FORMULA_REF_INCONSISTENCY_COUNTER`
- **RECORD_TYPE_REGISTRY 同步登记** `ProjectCalculationStandardProfile`
  - **注册类数口径**（明确 GSTACK P1）：
    - Task 1 (P5-0-1) 后：**12 类**（7 新表 + 现有 5 表，`heat_results` 已含在 5 表内）
    - Task 24 (P5-0-5) 后：**13 类**（+ `ProjectCalculationStandardProfile`）
  - V1.8 裁决 #11 中"P5-0-2 完成后追加 heat_results"表述作废；`heat_results` 为 P4 已存在表，P5-0-2 仅扩展字段，不新增 registry 条目
- **接口签名变更**：Task 13/14/16/17 计算函数增加 `standard` 参数；Task 18 端点增加 `valve_type` 前置校验（决策 8）

## 后续

- Task 24（P5-0-5 PSV 标准配置模型）落地本 ADR 全部 12 项决策
- **V1.8 计划同步**（本次审查发现）：裁决 #11 中"P5-0-2 完成后追加 heat_results"措辞需改为"P5-0-2 仅扩展字段，不新增 registry 条目"；Task 18 Steps 增加决策 8 拦截逻辑 + 2 例测试
- 评审通过后状态行由「proposed」改「accepted」
- ADR-0030（ChEDL 版本锁定，独立评审 D-08）与本 ADR 无耦合
- **评审截止时间**：P5-3 启动前（Task 13 实施前）
- **评审触发**：Task 24 完成后立即提交评审申请
- **评审 SLA**：5 个工作日内给出决议
- **回退预案**：若评审未通过，Task 24 须按评审意见修订后重提；Task 13/14/16/17 在 ADR 通过前**不实施**

supersedes：V1.0（2026-09-15 proposed，2026-09-16 由 V1.1 覆盖）
