---
status: proposed
date: 2026-09-15
---

# PSV 多标准引擎：项目级显式配置 + 双路径隔离 + 公式溯源

PSV 模块（Task 13/14/16/17）同时承担 API 体系（API 521/520/526）与 GB 体系（GB/T 150.1、GB/T 12241、GB/T 28778、HG/T 20570.2）两类工艺室日常计算。若不显式区分标准，将出现同一项目内 API/GB 结果混存、lineage 无法解释、record_hash 无法区分标准差异、P6 FLARE_SYS 拿到混合口径数据等问题。

本 ADR 记录 PSV 多标准引擎的 11 项架构裁决。SUP-P5-PSV-001 V1.0（2026-09-15 批准）是其需求侧锚点；本 ADR 是其架构落地侧锚点。两者须同步评审。

决定：**项目级显式配置 + 双路径完全隔离 + 公式条款级溯源 + 禁止隐式回退**。

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

- 字段：`(standard, version, clause)`，外加环节扩展字段（火灾 `drained`、泄放面积 `omega_method` / `two_phase_inherited_from`、孔口 `orifice_table_status`）
- TypedDict 集中定义于 `app/services/psv/formula_ref_types.py`：FireCaseFormulaRef / ClosedValveFormulaRef / ReliefAreaFormulaRef / OrificeFormulaRef
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

GB/T 12241 路径的两相流方法（P5 阶段 API 路径已用 two_point；GB 路径可复用 API 结果）在 P5 阶段可暂缺。

- 接口预留扩展位：`ReliefAreaFormulaRef.two_phase_inherited_from: Optional[str]` 标注"API_520"
- P5 阶段 GB 路径两相流若缺失，则在 formula_ref 中明确 `two_phase_inherited_from="API_520"` + `note="P5 阶段 GB 路径暂缺，引用 API 520 结果"`
- DIERS 积分法完整实现转 P5+

替代方案：P5 阶段同步实现 DIERS 积分法——否决。DIERS 涉及 ω 法多版本、数值积分路径，文献推荐保守取值（如 Omega-1），实现工作量远超单 task 范围。

### 决策 8：GB/T 28778-2023 先导式阀转 P5+（D-07 / P5-OPEN-00V 关闭）

先导式安全阀（GB/T 28778-2023）不纳入 P5 范围。

- `pilot_operated` 配置项保留但 `enabled=false`
- P5 阶段先导式阀计算请求返回 `422 PSV_PILOT_OPERATED_NOT_SUPPORTED`，提示升级至 P5+

替代方案：P5 同步实现——否决。先导式阀涉及导阀 + 主阀分程控制、响应时间、额定排量修正等独立体系，需独立批次专项实施。

### 决策 9：GB/T 12241 孔口表降级（D-04 / P5-OPEN-00Z 关闭）

GB/T 12241-2021 §8 安全阀尺寸的确定所需孔口表完整录入转 P5+。

- P5 阶段 GB 路径孔口选型降级：`orifice_table_status="incomplete_fallback"`
- 按计算面积输出**所需流道直径**（mm），不强制圆整到标准孔口
- `OrificeFormulaRef.note` 标注"P5 阶段降级：按计算面积输出流道直径，未圆整到标准孔口"
- P5+ 完整录入后再做圆整逻辑

替代方案：P5 阶段硬编部分孔口值——否决。工艺室实际项目孔口档位组合多，硬编数据缺乏标准维护流程，遗留技术债。

### 决策 10：6 道门禁规则（G1-G6）

| 编号 | 规则 | 响应 |
|---|---|---|
| G1 | 项目未配置 PSV 标准 → 计算 | 422 `PSV_STANDARD_NOT_CONFIGURED` |
| G2 | 请求覆盖项目默认但无权限 | 403 `PSV_STANDARD_OVERRIDE_FORBIDDEN` |
| G3 | CUSTOM profile 缺少审批依据 | 422 `PSV_CUSTOM_PROFILE_APPROVAL_REQUIRED` |
| G4 | 同一输入跨标准计算 | 两条独立记录，record_hash 不同 |
| G5 | 标准配置变更 | 旧记录不自动重算，标记 `pending_review` |
| G6 | 历史项目迁移 | 写入 API 默认 + `migrated_default=true`，要求复核 |

门禁校验点：
- **Task 16 service 层** `calc_relief_area()` 返回前：调 `validate_relief_area_formula_ref()`
- **Task 18 persist 层** `finalize_calc_record()` 写入 DB 前：再调一次（防止绕过 Task 16 直接构造记录）
- 校验失败：raise `PsvFormulaRefInconsistencyError`，附加 `logger.error(extra={project_id, record_id, ref})` + `PSV_FORMULA_REF_INCONSISTENCY_COUNTER.inc()`（可观测性，F-14-7）

### 决策 11：验收基准——按标准独立 golden，禁止共用阈值

| 标准 | 验收基准 | 阈值 |
|---|---|---|
| API 521 火灾 | API 521 算例 / 商业软件 | ≤2% |
| GB/T 150.1 附录 B 火灾 | GB 标准算例 / 工艺室手算 | 由工艺室确认（建议 ≤5%） |
| API 520 泄放面积 | API 520 算例 / HYSYS | ≤2% |
| GB/T 12241 泄放面积 | 标准算例 | 由工艺室确认 |
| API 520 两相流 | HYSYS / 文献 | ≤5% |
| GB/T 28778 先导式 | 标准算例 | P5+ 再定 |

每个标准必须独立 golden，不能共用阈值。SUP-P5-PSV-001 §7 锁定的 15 例门禁测试须独立存在。

## 影响

- **新表** 1 张：`project_calculation_standard_profiles`
- **加列**：`psv_results` / `relief_results` 各加 `standard_profile_code` / `standard_refs_json` / `formula_ref_json`（P5-3 实施后 NOT NULL）
- **新文件** 5 个：`standard_resolver.py` / `formula_ref_types.py` / `tests/models/test_psv_standard_profile.py` / `tests/services/psv/test_standard_resolver.py` / `tests/services/psv/test_formula_ref_validation.py`
- **新枚举** 1 个：`PsvStandardProfileCode`
- **新异常** ≥4 个：`PsvStandardNotConfiguredError` / `PsvStandardOverrideForbiddenError` / `PsvCustomProfileApprovalRequiredError` / `PsvCustomProfileSelfApprovalForbiddenError` / `PsvFormulaRefInconsistencyError`
- **新 metric** 1 个：`PSV_FORMULA_REF_INCONSISTENCY_COUNTER`
- **RECORD_TYPE_REGISTRY 同步登记** `ProjectCalculationStandardProfile`（P5-0-5 后总注册数 = 13 类）
- **接口签名变更**：Task 13/14/16/17 计算函数增加 `standard` 参数

## 后续

- Task 24（P5-0-5 PSV 标准配置模型）落地本 ADR 全部 11 项决策
- 评审通过后状态行由「proposed」改「accepted」
- ADR-0029（ChEDL 版本锁定）独立评审（D-08），与本 ADR 无耦合
- **评审截止时间**：P5-3 启动前（Task 13 实施前）
- **评审触发**：Task 24 完成后立即提交评审申请
- **评审 SLA**：5 个工作日内给出决议
- **回退预案**：若评审未通过，Task 24 须按评审意见修订后重提；Task 13/14/16/17 在 ADR 通过前**不实施**

supersedes：无。
