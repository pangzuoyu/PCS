增补 SPEC：PSV 多标准（API / GB）项目级配置与计算引擎
Spec 编号：SUP-P5-PSV-001
版本：V1.1
日期：2026-09-16
状态：修订（V1.0 评审反馈整改 + 提交重评）
父 Spec：spec/工艺专用综合计算软件需求规格说明书 Web版 P5.md V1.3 §3.2.3
关联计划：P5 设备计算模块（第二批）实施计划 V1.0 Task 13/14/16/17/18
关联 ADR：ADR-0028（PSV 多标准引擎，accepted 2026-09-15）、ADR-0030（ChEDL 版本锁定，accepted 2026-09-15）
TODOS 关联：TODO-PSV-STD-001
前置依赖：P5-0-1（数据模型扩展）、P5-3-1（火灾工况 API 基线）

修订说明
---
V1.1 相对 V1.0 解决以下问题：

1. **数据模型与门禁规则不一致** — psv_results/relief_results 补充 4 列；§8.2 任务清单补齐
2. **is_default 唯一性约束时间维度不完整** — 引入 `effective_to` + EXCLUDE 约束
3. **GB profile closed_valve 安全计算缺口** — 新增门禁 G8：项目 profile 含 GB/CUSTOM + closed_valve 指向 HG/T 20570.2 → 422 PSV_PROFILE_INSUFFICIENT（按工况拒绝，不整请求拒绝）
4. **GB 两相流 + 孔口选型降级方案缺门禁与验收** — GB + two_phase → 422 PSV_TWO_PHASE_GB_UNSUPPORTED；孔口表缺失 → 响应 `orifice_selection_degraded=true` + 服务端 WARN + 验收基线
5. **覆盖项目默认标准的语义和审计不完整** — 覆盖必须落库 `override_reason` + `override_approval_json`；项目未配置 + 请求任意 code → 422（不绕项目级配置）；新增 G7 门禁
6. **标准标识符和 formula_ref 结构不统一** — 受控词表 `{standard, version, clause}` 拆字段（不用拼接字符串）；canonical JSON 规范：键排序 + ISO 8601 时间戳 + 定点数十进制
7. **验收基准缺失多个关键环节** — §7 补齐 HG/T 20570.2 拒绝路径 / GB/T 12241 孔口 / CUSTOM 混合 / G1-G8 门禁 / migrated_default 复核 / pending_review / record_hash 跨标准 / override 审批
8. **OPEN 项未关闭前无法完整实施** — §9 引用 P5 计划已 D-02/D-03/D-04/D-06/D-07 关闭的决议；新增 P5-OPEN-00U（GB 路径控制阀故障补 P5+）
9. **非阻塞建议** — 加 `GET /api/v1/projects/{id}/standards/psv`；discipline CHECK 约束；JSON Schema 校验；CUSTOM 示例补 closed_valve；API profile 补 pilot_operated；migrated_default 不可作正式默认；pending_review 触发机制；relief_summary 混合记录分组；数据迁移回滚

D 决议来源：
- D1：字段落库方式 — **独立列**（pending_review / migrated_default / override_reason / override_approval_json）
- D2：is_default 唯一性 — **effective_to + EXCLUDE 约束**
- D3：GB closed_valve 处理 — **显式拒绝**（G8 门禁 + 按工况 + CUSTOM 合法路径 + P5-OPEN-00U）

§1 背景与动机
---
1.1 现状
当前 P5 计划的 PSV 模块（Task 13–18）以 API 体系为唯一计算路径：Task 13 火灾工况采用 API 521，Task 16 泄放面积采用 API 520，Task 17 孔口选型采用 API 526。计划中已识别 API 参数取值需修正（C 值 43,200 → 21,000）、ω 法版本需锁定（two_point）等问题。

1.2 需求来源
工艺室在实际项目中面临两套并行标准体系：

| 计算环节 | API 体系 | 中国标准体系 |
|---|---|---|
| 火灾工况泄放量 | API 521 | GB/T 150.1-2024 附录B |
| 控制阀故障/热膨胀等 | API 521 | HG/T 20570.2-1995（**P5 不实现，详 G8**） |
| 泄放面积 | API 520 | GB/T 12241-2021 |
| 孔口选型/尺寸确定 | API 526 | GB/T 12241-2021（**孔口表不完整时降级，详 §4.5**） |
| 先导式安全阀 | — | GB/T 28778-2023（**P5+ 评估**） |

文献研究表明，GB/T 150.1 附录B 与 API 521 在火灾工况下 公式结构、润湿面积计算、容器外壁修正系数取值 三个环节存在实质性差异，同一台容器按两套标准计算的泄放量结果不同。排量系数的定义及取值在 GB/T 12241-2021 与 API 520-2020 之间也存在差异。HG/T 20570.2-1995 作为国内石油化工行业安全阀设置和计算的首选参考规范，对控制阀故障和换热器管破裂工况**未提供完整公式**。

1.3 核心问题
若不在项目级定义标准配置，将导致：

- 同一项目内 API/GB 结果混存，lineage 无法解释
- record_hash 无法区分标准差异，相同输入不同标准被视为同一记录
- P6 FLARE_SYS 火炬总管汇总时拿到混合口径数据
- 历史项目记录缺少标准字段，无法追溯与复核

1.4 设计目标
- **项目级显式配置**：PSV 计算标准在项目级定义，不依赖代码隐式默认
- **按计算环节细分标准**：不是单一 API/GB 枚举，而是 profile（标准配置集）
- **结果、lineage、record_hash 全记录**：标准 profile、子标准版本、条款级 formula_ref
- **禁止隐式回退**：项目未配置时返回 422，不自动使用 API
- **受控覆盖**：请求可覆盖项目默认，但需权限校验并记录审批依据

§2 项目级 PSV 标准配置模型
---
2.1 标准配置集（Profile）定义

```text
PsvStandardProfileCode = Literal["API", "GB", "CUSTOM"]
```

每个 profile 内部按计算环节映射到具体子标准。所有环节字段统一用受控词表结构 `{standard, version, clause?}`，**禁止拼接字符串**（如 `"GB_T_150.1-2024"`）。`standard` 仅放标准代码，`version` 仅放版本号，`clause` 仅放条款引用（自然语言字符串）。

**API Profile**：

```json
{
  "profile_code": "API",
  "fire_case": { "standard": "API_521", "version": "7th" },
  "closed_valve": { "standard": "API_521", "version": "7th" },
  "relief_area": { "standard": "API_520", "version": "10th" },
  "orifice": { "standard": "API_526", "version": "2017" },
  "two_phase": {
    "standard": "API_520_Appendix_D",
    "version": "10th",
    "omega_method": "two_point"
  },
  "pilot_operated": null
}
```

> 注：API 体系当前无对应先导式安全阀规范，`pilot_operated: null` 表示"该 profile 不覆盖此环节"。

**GB Profile**：

```json
{
  "profile_code": "GB",
  "fire_case": { "standard": "GB_T_150.1", "version": "2024", "clause": "附录B" },
  "closed_valve": {
    "standard": "HG_T_20570.2",
    "version": "1995",
    "status": "unsupported_p5",
    "reason": "原标准未提供控制阀故障液体泄放量的完整计算公式"
  },
  "relief_area": { "standard": "GB_T_12241", "version": "2021" },
  "orifice": { "standard": "GB_T_12241", "version": "2021", "orifice_table_status": "incomplete_fallback" },
  "pilot_operated": { "standard": "GB_T_28778", "version": "2023", "enabled": false }
}
```

> 注 1：`closed_valve.status = "unsupported_p5"` 触发 G8 门禁（详 §6），请求包含此工况时直接 422，不进入计算函数。
> 注 2：`orifice.orifice_table_status = "incomplete_fallback"` 标记降级路径（详 §4.5）。

2.2 CUSTOM Profile

若项目需要"火灾用 GB、泄放面积用 API"等混合配置，必须定义 CUSTOM profile，并记录审批依据：

```json
{
  "profile_code": "CUSTOM",
  "fire_case": { "standard": "GB_T_150.1", "version": "2024", "clause": "附录B" },
  "closed_valve": { "standard": "API_521", "version": "7th" },
  "relief_area": { "standard": "API_520", "version": "10th" },
  "orifice": { "standard": "API_526", "version": "2017" },
  "approval": {
    "approved_by": "标准负责人姓名",
    "reason": "国内项目火灾工况按 GB 计算，泄放面积按 API 保守取值",
    "approved_at": "2026-09-15T00:00:00Z"
  }
}
```

**CUSTOM 合法路径**：若项目需要控制阀故障工况，V1.1 推荐 `closed_valve.standard = "API_521"`（走 API 分支），G8 不触发。**审批不能解锁未实现的能力**——CUSTOM 中 `closed_valve.standard = "HG_T_20570.2"` 即便附完整审批依据，仍触发 G8。

禁止在同一计算内混用未声明的标准。

2.3 GB 版本选择说明

GB/T 150.1 现行有效版本为 2024 版，代替 2011 版（D-03 关闭：项目级可选，新项目默认 2024）。主要变化包括：

- 气体特性系数、最小泄放面积、额定排量等计算方法有修订
- 对球罐设计的安全要求更为严格
- 附录B 为超压泄放装置的设计要求（规范性附录）

项目配置时必须锁定具体版本（2011 或 2024），不得使用"GB/T 150.1"模糊引用。推荐新项目默认使用 2024 版，历史项目迁移时保持原有版本。

GB/T 12241 现行有效版本为 2021 版，代替 2005 版（D-04 关闭：P5 阶段孔口表降级，输出所需流道直径不强制圆整；完整录入转 P5+）。GB/T 28778 现行有效版本为 2023 版（D-07 关闭：先导式阀转 P5+ 评估）。

§3 数据模型
---
3.1 新增表：project_calculation_standard_profiles

```sql
CREATE TABLE project_calculation_standard_profiles (
    id                      BIGSERIAL PRIMARY KEY,
    project_id              BIGINT NOT NULL REFERENCES projects(id),
    discipline              VARCHAR(16) NOT NULL,  -- 'PSV' / 'VESSEL' / 'HEAT' ...
    profile_code            VARCHAR(16) NOT NULL,  -- 'API' / 'GB' / 'CUSTOM'
    standard_refs_json      JSONB NOT NULL,         -- 各子标准、版本、条款映射
    approval_json           JSONB,                  -- CUSTOM 时必填，含审批人+依据
    is_default              BOOLEAN NOT NULL DEFAULT FALSE,
    effective_from          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    effective_to            TIMESTAMPTZ,            -- NULL 表示当前生效；非 NULL 表示已失效
    approved_by             BIGINT REFERENCES users(id),
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT discipline_enum_chk CHECK (discipline IN ('PSV', 'VESSEL', 'HEAT', 'PIPE', 'PUMP', 'SEPARATOR')),
    CONSTRAINT profile_code_enum_chk CHECK (profile_code IN ('API', 'GB', 'CUSTOM')),
    CONSTRAINT custom_requires_approval_chk CHECK (
        (profile_code = 'CUSTOM' AND approval_json IS NOT NULL) OR
        (profile_code <> 'CUSTOM')
    ),
    CONSTRAINT project_standard_default_unique
        EXCLUDE USING gist (
            project_id WITH =,
            discipline WITH =,
            tstzrange(effective_from, COALESCE(effective_to, 'infinity'::timestamptz), '[)') WITH &&
        ) WHERE (is_default = TRUE)
);
CREATE INDEX idx_pcs_project_discipline_default
    ON project_calculation_standard_profiles (project_id, discipline)
    WHERE is_default = TRUE AND effective_to IS NULL;
```

约束语义：
- `project_standard_default_unique`（EXCLUDE 约束，D2）：同一 (project_id, discipline) 在任意时刻至多一个 is_default = TRUE；新配置写入时旧行 `effective_to` 必填并小于新行 `effective_from`
- `custom_requires_approval_chk`：CUSTOM profile 必填 approval_json
- `standard_refs_json` 必须覆盖该 discipline 的所有计算环节，JSON Schema 校验在 API 层执行（详 §5.5）

3.2 psv_results 和 relief_results 加列

```sql
ALTER TABLE psv_results ADD COLUMN standard_profile_code VARCHAR(16);
ALTER TABLE psv_results ADD COLUMN standard_refs_json JSONB;
ALTER TABLE psv_results ADD COLUMN formula_ref_json JSONB;
ALTER TABLE psv_results ADD COLUMN pending_review BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE psv_results ADD COLUMN migrated_default BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE psv_results ADD COLUMN override_reason TEXT;
ALTER TABLE psv_results ADD COLUMN override_approval_json JSONB;

ALTER TABLE relief_results ADD COLUMN standard_profile_code VARCHAR(16);
ALTER TABLE relief_results ADD COLUMN standard_refs_json JSONB;
ALTER TABLE relief_results ADD COLUMN formula_ref_json JSONB;
ALTER TABLE relief_results ADD COLUMN pending_review BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE relief_results ADD COLUMN migrated_default BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE relief_results ADD COLUMN override_reason TEXT;
ALTER TABLE relief_results ADD COLUMN override_approval_json JSONB;
```

约束：
- `standard_profile_code` 和 `standard_refs_json` 为 NOT NULL（P5-3 实施后）
- `pending_review = TRUE` 表示标准配置变更后旧记录需复核，**自动触发**（详 §5.6）
- `migrated_default = TRUE` 表示历史项目迁移默认值，**不作为正式默认**（仅作占位），需人工 `pending_review` 流程转为正式默认
- `override_reason` 与 `override_approval_json` 在覆盖项目默认时必填（详 §5.2 + G7）
- record_hash 计算必须包含 `standard_profile_code` + `standard_refs_json`，canonical JSON 规范详 §3.4

3.3 DataLineage formula_ref 条款级记录

formula_ref 统一结构，**禁止字符串拼接**：

```json
{
  "standard_profile": "GB",
  "fire_case": {
    "standard": "GB_T_150.1",
    "version": "2024",
    "clause": "附录B 超压泄放装置的设计要求"
  },
  "relief_area": {
    "standard": "GB_T_12241",
    "version": "2021",
    "clause": "§7.4 排量系数的确定"
  },
  "orifice": {
    "standard": "GB_T_12241",
    "version": "2021",
    "clause": "§8 安全阀尺寸的确定"
  }
}
```

3.4 canonical JSON 规范（record_hash 输入）

为保证 record_hash 在跨项目、跨标准、跨时间稳定可比，所有进入 hash 的 JSON 必须遵守：

- **键排序**：字典键按字符串升序排序（递归作用于嵌套对象）
- **时间戳**：所有时间字段使用 ISO 8601 UTC（`...Z`），字符串字面量
- **数值**：定点数十进制（如 `0.975` 而非浮点 `0.9750000000000001`），位数由计算结果有效位数决定（API 521 ≤6 位，GB ≤4 位）
- **空值语义**：`null` 与字段缺失必须一致（统一 `null`）
- **审批信息**：审批依据（approved_by/approved_at）**不**进入 record_hash（用于权限审计，但避免审批时间变更触发 hash 漂移）
- **覆盖信息**：`override_reason` 与 `override_approval_json` **不**进入 record_hash（用于审计，避免审批变更触发 hash 漂移）

实现位置：utils/canonical_json.py 提供 `canonical_dumps(obj) -> str` 函数，所有 record_hash 输入走该函数。

§4 计算引擎改造
---
4.1 标准解析层（standard_resolver）

在服务层之上增加 standard_resolver 层，由它决定调用哪套底层计算函数：

```python
class StandardResolver:
    def resolve(
        self, project_id: int, discipline: str = "PSV"
    ) -> PsvStandardProfile:
        """
        解析项目当前生效的默认标准配置。
        若项目未配置 → raise PsvStandardNotConfiguredError (422, G1)
        若 closed_valve.status == 'unsupported_p5' → 不在此处拒绝，按请求工序级联拒绝（G8）
        """
        profile = self._repo.get_current_default(project_id, discipline)
        if profile is None:
            raise PsvStandardNotConfiguredError(
                project_id=project_id, discipline=discipline
            )
        return profile

    def check_capability(
        self, profile: PsvStandardProfile, requested_stages: list[str]
    ) -> None:
        """
        按请求工况级联检查 profile 能力。任一 unsupported 阶段 → 422 PSV_PROFILE_INSUFFICIENT
        """
        for stage in requested_stages:
            ref = profile.standard_refs.get(stage)
            if ref is None:
                continue
            if ref.get("status") == "unsupported_p5":
                raise PsvProfileInsufficientError(
                    project_id=profile.project_id,
                    discipline=profile.discipline,
                    profile_code=profile.profile_code,
                    insufficient_stage=stage,
                    standard=ref["standard"],
                    version=ref["version"],
                    reason=ref.get("reason", "原标准未提供完整计算公式"),
                    remediation=[
                        "改用 CUSTOM profile，closed_valve 指定 API_521 并附审批依据",
                        "或将 closed_valve 工况排除在本项目 PSV 计算范围外"
                    ]
                )
```

核心原则：API 路径和 GB 路径的计算逻辑完全隔离，各自拥有独立的函数和测试基准，不在函数内部用 if standard == "GB" 做分支。

4.2 Task 13 改造：火灾工况

```python
calc_fire_case(
    inp: FireCaseInput,
    standard: FireCaseStandard  # 由 StandardResolver 注入
) -> FireCaseResult
```

API 521 分支（修正后）：
- C 值：adequate drainage + firefighting → 21,000（BTU/hr·ft²，英制链）
- 润湿面积：立式 πDH，卧式按封头曲面 + 圆柱 + 液位修正
- 修正系数：API 521 容器外壁修正系数

GB/T 150.1 附录B 分支：
- 润湿面积按 GB 几何规则计算（与 API 的 πDH 处理不同）
- 修正系数按 GB 取值规则
- 泄放量公式结构按 GB 附录B

验收基准：
- API 分支：API 521 算例 / 商业软件，≤2%
- GB 分支：GB 标准算例 / 工艺室手算，阈值由工艺室确认（建议 ≤5%）

4.3 Task 14 改造：其他工况

GB profile 的 `closed_valve` 标记为 `unsupported_p5`（详 §2.1 + G8）。`calc_closed_valve_case_GB()` **不实施**——请求包含此工况时由 §4.1 `check_capability` 在 resolver 层抛 `PsvProfileInsufficientError`，不进入任何计算函数。

CUSTOM profile 的 `closed_valve.standard = "API_521"` 合法路径走 `calc_closed_valve_case_API()`，formula_ref.closed_valve 指向 API 521 7th。

4.4 Task 16 改造：泄放面积

```python
calc_relief_area(
    inp: ReliefAreaInput,
    standard: ReliefAreaStandard  # 由 StandardResolver 注入
) -> ReliefAreaResult
```

API 520 分支：
- 排量系数：Kd（制造厂试验值，典型 0.975）
- 两相流 ω 法：默认 two_point，API 520 附录D（D-06 关闭：GB 路径两相流 DIERS 积分法转 P5+）

GB/T 12241 分支：
- 排量系数确定路径与 API 不同：GB/T 12241-2021 §7.4 规定了排量系数的确定方法，§7.5 规定了额定排量系数
- 额定排量计算：理论排量 × 额定排量系数，或实测排量 × 减低系数（0.9）
- 亚临界流动需乘以排量修正系数 Kb（GB/T 12241 表4）
- **两相流方法**：P5 阶段 GB 路径不实现，请求 GB + two_phase → 422 PSV_TWO_PHASE_GB_UNSUPPORTED（G10），接口预留扩展（D-06）

4.5 Task 17 改造：孔口选型

API 526 分支：D~T 标准孔口表（D=0.110 in² ... T=26.0 in²），圆整向上。

GB/T 12241 分支：
- 按 GB/T 12241-2021 §8 安全阀尺寸的确定
- 标准孔口系列可能与 API 526 不同
- **降级路径**（D-04 关闭：孔口表完整录入转 P5+）：GB profile 的 `orifice.orifice_table_status = "incomplete_fallback"`，计算时输出 `required_diameter_mm`（所需流道直径），**不强制圆整**到标准孔口
- 降级响应体增加 `orifice_selection_degraded: true`（详 §5.3）
- 服务端记录 WARN 日志：`psv.orifice.degraded project={id} required_diameter={mm} orifice_table_status=incomplete_fallback`
- 降级结果**不可用于正式采购/出图**（UI 层必须显式标记）

§5 接口定义
---
5.1 项目标准配置 API

```http
POST /api/v1/projects/{project_id}/standards/psv
Content-Type: application/json
Authorization: Bearer <token>

{
  "profile_code": "GB",
  "standard_refs": {
    "fire_case": { "standard": "GB_T_150.1", "version": "2024", "clause": "附录B" },
    "closed_valve": { "standard": "HG_T_20570.2", "version": "1995", "status": "unsupported_p5" },
    "relief_area": { "standard": "GB_T_12241", "version": "2021" },
    "orifice": { "standard": "GB_T_12241", "version": "2021", "orifice_table_status": "incomplete_fallback" },
    "pilot_operated": { "standard": "GB_T_28778", "version": "2023", "enabled": false }
  },
  "is_default": true
}
```

**权限**：仅项目标准负责人/管理员可配置。响应 403 若无权限（G2）。**写入新默认时**：将当前默认行 `effective_to = NOW()`，新行 `effective_from = NOW()`、`effective_to = NULL`，EXCLUDE 约束确保不冲突。

**GET 接口**（V1.1 新增）：

```http
GET /api/v1/projects/{project_id}/standards/psv
```

返回项目当前生效默认 + 历史已失效配置列表。供前端和计算前检查项目标准配置使用。

5.2 计算请求

```http
POST /api/v1/psv/calculate-relief
{
  "project_id": "...",
  "standard_profile_code": "GB",   // 可选；与项目默认不一致时需权限 + 覆盖依据
  "override_reason": "工艺室确认本项目采用 GB 路径，标准负责人 2026-09-16 审批",
  "override_approval": {
    "approved_by": "标准负责人姓名",
    "approved_at": "2026-09-16T00:00:00Z"
  },
  "requested_stages": ["fire_case", "closed_valve", "relief_area", "orifice"],
  ...
}
```

**覆盖语义**（G5 + G7）：
- 请求 `standard_profile_code` 与项目默认不一致时**必须**填 `override_reason` + `override_approval`；缺失 → 422 PSV_OVERRIDE_APPROVAL_REQUIRED
- 项目**未配置**任何 profile + 请求任意 code → 422 PSV_STANDARD_NOT_CONFIGURED（**不**绕项目级配置；**不**自动使用 API 默认）
- 覆盖的 `standard_profile_code` 必须是项目**已配置的 profile**（不是内置模板）；内置模板不可绕过项目级审批

5.3 响应与落库

```json
{
  "standard_profile_code": "GB",
  "standard_refs_json": { "...": "..." },
  "formula_ref": {
    "fire_case": { "standard": "GB_T_150.1", "version": "2024", "clause": "附录B" },
    "relief_area": { "standard": "GB_T_12241", "version": "2021", "clause": "§7.4" }
  },
  "pending_review": false,
  "migrated_default": false,
  "override_reason": null,
  "override_approval": null,
  "orifice_selection_degraded": true,
  "required_diameter_mm": 14.3,
  "orifice_table_status": "incomplete_fallback",
  ...
}
```

5.4 relief_summary 接口调整

```http
GET /api/v1/psv/relief-summary?project_id=...
```

按项目标准汇总，避免 P6 FLARE_SYS 拿到混合口径数据。响应中包含 `standard_profile_code`，供 P6 识别数据口径。**混合记录处理**（V1.1 新增）：若项目存在历史混合记录（标准配置变更前后的记录共存），响应按 `standard_profile_code` 分组返回，每组单独汇总 `count` + `total_relief_area`；UI 层显式提示"P5-3 实施前历史记录"。

5.5 JSON Schema 校验

`standard_refs_json` 与 `formula_ref_json` 在 API 层使用 JSON Schema 校验：

- `standard_refs_json` 必填键按 discipline 区分；PSV discipline 必填 `fire_case` + `relief_area` + `orifice`，可选 `closed_valve` / `two_phase` / `pilot_operated`
- 每个 `{standard, version, clause?}` 子对象必填 `standard` + `version`，`clause` 可选但 `fire_case`（GB 路径）必填
- `status` 字段仅允许 `unsupported_p5` 或缺省；缺省 = 支持
- `orifice_table_status` 仅允许 `incomplete_fallback` 或缺省；缺省 = 完整

5.6 pending_review 触发机制

`pending_review = TRUE` **自动触发**于以下场景：

- **场景 A**：项目级 standard_profile 变更（`is_default` 切换或新配置写入），扫描该项目既有 psv_results/relief_results 中 `standard_profile_code = 旧 profile_code` 的记录 → `pending_review = TRUE`
- **场景 B**：GB profile 的 `orifice_table_status` 从 `incomplete_fallback` 切换到完整（未来 P5+）时，扫描相关历史记录 → `pending_review = TRUE`

人工触发：UI 层"标记待复核"按钮写入 `pending_review = TRUE`。

解除：`pending_review = FALSE` 由用户复核确认后写入，需记录 `reviewed_by` + `reviewed_at`（V1.1 不强制 schema 增列，仅业务层记录）。

§6 门禁规则
---
| 编号 | 规则 | 响应 |
|---|---|---|
| G1 | 项目未配置 PSV 标准 → 计算 | 422 PSV_STANDARD_NOT_CONFIGURED |
| G2 | 请求覆盖项目默认但无权限 | 403 PSV_STANDARD_OVERRIDE_FORBIDDEN |
| G3 | CUSTOM profile 缺少审批依据 | 422 PSV_CUSTOM_PROFILE_APPROVAL_REQUIRED |
| G4 | 同一输入跨标准计算 | 两条独立记录，record_hash 不同 |
| G5 | 标准配置变更 | 旧记录标记 `pending_review = TRUE`（自动） |
| G6 | 历史项目迁移 | 写入 `migrated_default = TRUE`（占位），`pending_review = TRUE`（自动），**不**作为正式默认 |
| **G7** | 覆盖项目默认无审批依据 | 422 PSV_OVERRIDE_APPROVAL_REQUIRED（`override_reason` + `override_approval` 缺一不可） |
| **G8** | 项目 profile 含 GB/CUSTOM + `closed_valve.standard = HG_T_20570.2` + 请求包含 closed_valve 工况 | 422 PSV_PROFILE_INSUFFICIENT（**按工况拒绝**，不整请求拒绝；response 含 `insufficient_stage: "closed_valve"` + `remediation`） |
| **G9** | 项目未配置任何 profile + 请求任意 `standard_profile_code` | 422 PSV_STANDARD_NOT_CONFIGURED（**不**绕项目级配置；**不**自动使用 API 默认） |
| **G10** | GB profile + 请求包含 two_phase 工况 | 422 PSV_TWO_PHASE_GB_UNSUPPORTED（D-06 转 P5+） |
| G11 | 同一 (project_id, discipline) 同时存在多个 `is_default = TRUE` | EXCLUDE 约束报错（写入时拦截） |

禁止隐式回退 API。项目未配置时，计算请求必须返回 422，不得自动使用 API 作为默认。

§7 验收基准
---
| 标准/环节 | 验收基准 | 阈值 |
|---|---|---|
| API 521 火灾 | API 521 算例 / 商业软件 | ≤2% |
| GB/T 150.1 附录B 火灾 | GB 标准算例 / 工艺室手算 | 由工艺室确认（建议 ≤5%） |
| API 520 泄放面积 | API 520 算例 / HYSYS | ≤2% |
| GB/T 12241 泄放面积 | 标准算例 | 由工艺室确认 |
| API 520 两相流 | HYSYS / 文献 | ≤5% |
| **HG/T 20570.2 控制阀故障（GB profile）** | 拒绝路径：项目 GB profile + closed_valve → 422 PSV_PROFILE_INSUFFICIENT | 响应码与错误码断言 |
| **HG/T 20570.2 控制阀故障（CUSTOM profile，closed_valve=HG_T_20570.2）** | 拒绝路径：审批不能解锁未实现能力 → 422 PSV_PROFILE_INSUFFICIENT | 响应码断言 |
| **GB 路径两相流** | 拒绝路径：项目 GB profile + two_phase → 422 PSV_TWO_PHASE_GB_UNSUPPORTED | 响应码与错误码断言 |
| **GB/T 12241 孔口选型（降级路径）** | 输出 `required_diameter_mm` + `orifice_selection_degraded=true` + 服务端 WARN 日志 | 响应体断言 + 日志断言 |
| **CUSTOM 混合（fire_case=GB + closed_valve=API_521）** | 正常返回，`formula_ref.fire_case` 指向 GB/T 150.1，`formula_ref.closed_valve` 指向 API 521 | formula_ref 字段断言 |
| **GB/T 28778 先导式** | 拒绝路径：项目 GB profile + pilot_operated 启用 → 501 PSV_PILOT_UNSUPPORTED | 响应码与错误码断言 |
| **G1-G11 门禁** | 每条 1 测试 | 11 测试 |
| **历史迁移 migrated_default 复核** | 迁移后既有记录 `migrated_default = TRUE` + `pending_review = TRUE`，**不**作为正式默认 | DB 状态断言 |
| **标准配置变更 pending_review** | 项目级 profile 变更 → 旧记录 `pending_review = TRUE`（自动） | DB 状态断言 |
| **record_hash 跨标准差异** | 同一输入 × API vs GB → 两条独立记录，record_hash 不同 | hash 断言 |
| **override 权限与审批** | 覆盖默认 + 无 `override_reason` → 422 PSV_OVERRIDE_APPROVAL_REQUIRED；无权限 → 403 | 响应码断言 |
| **canonical JSON 规范** | 同标准同输入跨项目 hash 一致；不同 standard 字段 hash 不同 | hash 断言 |

合计新增测试 ≥25 个（V1.0 估 ≥15 偏少；现按 G1-G11 11 门禁 + 上表 8 标准/环节 = ≥19，外加 canonical JSON 1 + record_hash 1 + pending_review 1 + migrated_default 1 + override 权限 1 = ≥24，留 1 余量）。P5 验收基线：原 ≥1650（V1.0 误写为 ≥1665）调整为 **净增 ≥25**，对应 P5 启动基线 1662 → ≥1687。

§8 对 P5 计划的修改
---
8.1 P5-OPEN 关闭（V1.1 引用 P5 计划已关闭决议）

| OPEN 编号 | 关闭决议 | 决议内容 |
|---|---|---|
| P5-OPEN-00X | **D-02** | 工艺室 PSV 默认标准：强制项目级显式配置，禁止隐式回退 |
| P5-OPEN-00Y | **D-03** | GB/T 150.1 版本：项目级可选，新项目默认 2024 |
| P5-OPEN-00Z | **D-04** | GB/T 12241 孔口表：P5 降级（输出所需流道直径不强制圆整），完整录入转 P5+ |
| P5-OPEN-00W | **D-06** | GB 路径两相流 DIERS 积分法：转 P5+ |
| P5-OPEN-00V | **D-07** | 先导式阀 GB/T 28778：转 P5+ 评估 |
| **P5-OPEN-00U**（V1.1 新增） | 待 P5 实施后评估 | GB 路径控制阀故障工况（HG/T 20570.2 补充公式）：转 P5+ 评估，需工艺室 + 标准负责人联签，公式需附标准出处与权威基准 |

8.2 P5-0 增加前置任务

Task P5-0-5：PSV 标准配置模型（V1.1 补齐 4 列）

- 建 `project_calculation_standard_profiles` 表（含 `effective_to` + EXCLUDE 约束 + discipline/profile_code CHECK）
- 给 `psv_results` / `relief_results` 加 `standard_profile_code` + `standard_refs_json` + `formula_ref_json` + `pending_review` + `migrated_default` + `override_reason` + `override_approval_json`（共 7 列，V1.0 漏 4 列）
- 注册 `PsvStandardProfileCode` 枚举
- 写 G1 / G7 / G8 / G9 / G10 门禁测试
- 实现 `utils/canonical_json.py` 提供 `canonical_dumps`
- 实现 `app/services/standard_resolver.py` 提供 `resolve` + `check_capability`

8.3 Task 13/14/16/17 接口增加标准参数

标准由项目配置解析后注入，而非前端随意传递。

8.4 Task 18 API 增加校验

- G1：项目未配置 → 422 PSV_STANDARD_NOT_CONFIGURED
- G7：覆盖默认 + 无审批依据 → 422 PSV_OVERRIDE_APPROVAL_REQUIRED
- G8：GB/CUSTOM closed_valve → 422 PSV_PROFILE_INSUFFICIENT（按工况）
- G9：项目未配置 + 任意 code → 422 PSV_STANDARD_NOT_CONFIGURED
- G10：GB + two_phase → 422 PSV_TWO_PHASE_GB_UNSUPPORTED
- 落库写入 `pending_review` / `migrated_default` / `override_*` 字段
- relief_summary 按 `standard_profile_code` 分组（混合记录）

8.5 测试基线调整

V1.0 估"≥15 个"偏少且 V1.0 误写 P5 验收基线为"≥1650 → ≥1665"（实际 P5 启动基线 1662，净增 ≥25 → ≥1687）。V1.1 调整：

新增测试（G1-G11 11 门禁 + §7 验收表 8 标准/环节 + 4 辅助）：

- G1 项目未配置标准 → 422 PSV_STANDARD_NOT_CONFIGURED
- G2 无权限覆盖 → 403 PSV_STANDARD_OVERRIDE_FORBIDDEN
- G3 CUSTOM 缺审批 → 422 PSV_CUSTOM_PROFILE_APPROVAL_REQUIRED
- G4 同一输入跨标准 → 两条独立记录 + record_hash 不同
- G5 标准配置变更 → 旧记录 `pending_review = TRUE`
- G6 历史迁移 → `migrated_default = TRUE` + `pending_review = TRUE`，不可作正式默认
- G7 覆盖无审批 → 422 PSV_OVERRIDE_APPROVAL_REQUIRED
- G8 GB + closed_valve → 422 PSV_PROFILE_INSUFFICIENT（按工况）
- G8b CUSTOM closed_valve=HG_T_20570.2 + 审批齐全 → 仍 G8（审批不解锁能力）
- G9 项目未配置 + 任意 code → 422
- G10 GB + two_phase → 422 PSV_TWO_PHASE_GB_UNSUPPORTED
- G11 EXCLUDE 约束并发写入 → IntegrityError
- HG/T 20570.2 拒绝路径：项目 GB profile + 仅 fire_case → 正常；+ closed_valve → 422
- GB 两相流拒绝路径：项目 GB profile + relief_area + two_phase → 422
- GB 孔口降级：项目 GB profile + orifice → `orifice_selection_degraded=true` + 服务端 WARN + 不可采购标记
- CUSTOM 合法路径：项目 CUSTOM closed_valve=API_521 + 审批齐全 → 正常
- record_hash canonical JSON 跨项目一致性
- record_hash 跨标准差异
- override 权限：无权限 → 403；有权限 + 无 override_reason → 422
- migrated_default 不可作正式默认：扫描 DB 默认查询排除 `migrated_default = TRUE`
- pending_review 自动触发：项目级 profile 变更后旧记录 `pending_review = TRUE`

§9 OPEN 项
---
| 编号 | 内容 | 影响范围 | 决议方式 |
|---|---|---|---|
| P5-OPEN-00X | 工艺室 PSV 默认标准 | Task 13/14/16/17 接口设计 | **D-02 已关闭**（强制项目级显式配置） |
| P5-OPEN-00Y | GB/T 150.1 版本 | GB 火灾工况计算基准 | **D-03 已关闭**（项目级可选，新项目默认 2024） |
| P5-OPEN-00Z | GB/T 12241 孔口表完整录入 | Task 17 GB 分支完整性 | **D-04 已关闭**（P5 降级，完整录入转 P5+） |
| P5-OPEN-00W | GB 路径两相流 DIERS 积分法 | Task 16 GB 分支 | **D-06 已关闭**（转 P5+） |
| P5-OPEN-00V | 先导式阀 GB/T 28778 | Task 17 范围 | **D-07 已关闭**（转 P5+ 评估） |
| **P5-OPEN-00U**（V1.1 新增） | GB 路径控制阀故障工况（HG/T 20570.2 补充公式） | Task 14 GB 分支 | 工艺室 + 标准负责人联签，P5+ 评估 |

§10 Backlog
---
- HG/T 20570.2 控制阀故障补充公式的工程依据、审批流程与验收基线（详 P5-OPEN-00U）
- 相应的 ADR（PSV 多标准引擎 ADR-0028 的子项）
- GB 路径两相流 DIERS 积分法实现（D-06）
- GB/T 28778-2023 先导式安全阀计算模块（D-07）
- GB/T 12241 标准孔口表完整录入（D-04）
- CUSTOM profile 的审批工作流
- 跨标准结果对比报告（同一容器 API vs GB 偏差分析）
- P6 FLARE_SYS 按标准口径汇总接口
- P5+ GB profile `closed_valve` 公式补齐（接 P5-OPEN-00U）

§11 数据迁移策略
---
11.1 迁移范围

历史项目（V1.0 实施前已存在的项目）需迁移 `project_calculation_standard_profiles` 记录：

- 写入 `profile_code = 'API'` + `is_default = TRUE` + `migrated_default = TRUE` + `effective_from = NOW()` + `effective_to = NULL`
- 扫描既有 `psv_results` / `relief_results` 中 `standard_profile_code IS NULL` 的记录 → 标记 `migrated_default = TRUE` + `pending_review = TRUE`

11.2 迁移脚本

`alembic/versions/p5_psv_standard_profiles_migrate.py`：

1. CREATE TABLE `project_calculation_standard_profiles`（含 EXCLUDE 约束）
2. ALTER TABLE `psv_results` / `relief_results` ADD COLUMN 7 列
3. INSERT 默认 API 配置到所有历史项目（`migrated_default = TRUE`）
4. UPDATE 既有 `psv_results` / `relief_results` 记录：`migrated_default = TRUE` + `pending_review = TRUE`
5. 校验：EXCLUDE 约束无冲突；所有历史项目均有默认 profile

11.3 回滚方案

`downgrade()` 步骤：
1. DELETE FROM `project_calculation_standard_profiles` WHERE `migrated_default = TRUE`
2. ALTER TABLE `psv_results` / `relief_results` DROP COLUMN 7 列
3. DROP TABLE `project_calculation_standard_profiles`

NOT NULL 约束在迁移完成后**下次 P5-3 启动前**才加（不在本次迁移内），保证 P5-3 实施前回滚窗口。

11.4 人工复核流程

`migrated_default = TRUE` 的默认配置必须经过工艺室复核后转为正式默认（`migrated_default = FALSE` + `pending_review = FALSE`）。UI 层提供"批量复核"入口，复核后写 `reviewed_by` + `reviewed_at`（业务层记录，V1.1 不强制 schema 增列）。
