增补 SPEC：PSV 多标准（API / GB）项目级配置与计算引擎
Spec 编号：SUP-P5-PSV-001
版本：V1.5.1
日期：2026-09-16
状态：修订（V1.5 评审反馈整改；M1-M5 建议落地；不阻塞实施）
父 Spec：spec/工艺专用综合计算软件需求规格说明书 Web版 P5.md V1.3 §3.2.3
关联计划：P5 设备计算模块（第二批）实施计划 V1.0 Task 13/14/16/17/18
关联 ADR：ADR-0028（PSV 多标准引擎，accepted 2026-09-15）、ADR-0030（ChEDL 版本锁定，accepted 2026-09-15）
TODOS 关联：TODO-PSV-STD-001
前置依赖：P5-0-1（数据模型扩展）、P5-3-1（火灾工况 API 基线）

修订说明
---
V1.5.1 相对 V1.5 处理以下建议（不阻塞实施，落地前一次性补齐）：

- M1：§4.2 "详 §10 P5-OPEN-00U" 引用错误（00U 是 closed_valve，GB 火灾分支无对应 OPEN 项）。V1.5.1 修复：§9 OPEN 项表新增 **P5-OPEN-00T**（GB 火灾分支范围变更，跟踪工艺室签字对账表）；§4.2 引用改为 §9 P5-OPEN-00T
- M2：§5.1 POST 请求体示例缺 `two_phase` 和 `heat_exchanger_tube_rupture`，与 §5.5 JSON Schema 必填规则不一致。V1.5.1 修复：§5.1 GB profile 示例补齐两个字段（与 §2.1 GB profile 定义对齐），并加 `reason` 字段（与示例语义统一）
- M3：§4.1 `insufficient_case` 对 two_phase / pilot_operated 取值未声明（当前返回 "unsupported" 字符串）。V1.5.1 修复：`insufficient_case` 改为按 stage 名输出；§5.5 声明取值范围 `{"closed_valve", "tube_rupture", "two_phase", "pilot_operated", "unsupported"}`；保留 closed_valve / tube_rupture 别名兼容 G8 / G8c 已有约定
- M4：n1（ω/ωs 编号）缺 OPEN 项编号跟踪。V1.5.1 修复：§9 OPEN 项表新增 **P5-OPEN-00R**（API 520 10th Ed. 附录 C ω/ωs 子方法编号确认）
- M5：§11.2 / §11.3 步骤 3 / 步骤 2 措辞混合"列 / 约束 / 索引"。V1.5.1 修复：DDL 分类描述（ADD/DROP 7 列 + ADD/DROP CONSTRAINT × 2 表 + CREATE/DROP INDEX 4 条部分索引）

V1.5 相对 V1.4 解决以下问题：

V1.4 新暴露阻塞项（3）：
- B10：API profile 缺 `heat_exchanger_tube_rupture` 字段，B9 方案 A 在 API 路径下未落地。V1.5 修复：§2.1 API profile 显式增字段 `{"standard": "API_521", "version": "7th", "status": "unsupported_p5"}`；§5.5 JSON Schema 明确"三类 profile 均必填 heat_exchanger_tube_rupture"
- B11：G10/G12 声称的专用错误码（PSV_TWO_PHASE_GB_UNSUPPORTED / PSV_PILOT_UNSUPPORTED）在 check_capability 中全部退化为 PSV_PROFILE_INSUFFICIENT。V1.5 修复（方案 A）：§4.1 check_capability 加 `_STAGE_ERROR_CODE` 映射字典，所有 `raise PsvProfileInsufficientError` 注入 `error_code` 字段：two_phase → PSV_TWO_PHASE_GB_UNSUPPORTED，pilot_operated → PSV_PILOT_UNSUPPORTED，其他 → PSV_PROFILE_INSUFFICIENT；错误码与 G10/G12 声明完全对齐
- B12：§7 验收表 "G1-G12 = 12 测试" 与 §8.5 "门禁类 14 条" 不一致。V1.5 修复：§7 该行改为"G1-G12 + G8b + G8c = 14 测试"，与 §8.5 对齐

残留（2）：
- n5-residual：§7 验收表 GB/T 28778 行未覆盖 G12 三情形。V1.5 修复：§7 该行单元格列三情形 (a)(b)(c)，3 测试
- n2-residual：§7 验收表 GB 火灾行未标注"P5 交付范围外"。V1.5 修复：§7 该行标"**P5 交付范围外**"（E3 范围变更），验收阈值改为"待工艺室签字"

次要（3）：
- c1：§2.2 CUSTOM profile `reason` 字段含"B9 方案 A 锁定"等 SPEC 内部决策编号。V1.5 修复：`reason` 改用户友好"P5 阶段不支持换热器管破裂工况；该工况转 P5+ 评估"，内部决策编号留在 §4.3
- c2：§2.1 GB profile 缺 `two_phase` 字段，G10 实际走 U3 分支而非 unsupported_p5 分支。V1.5 修复：GB profile 显式增 `two_phase: {"standard": "GB_T_12241", "version": "2021", "status": "unsupported_p5"}`，与 B11 共同保证 G10 错误码正确返回
- c3：§2.3 "effective_from 必须 ≤ 当前时刻 + 1 秒" 与 §3.1 `effective_from <= created_at + INTERVAL '1 second'` 表述不一致。V1.5 修复：§2.3 改为"effective_from 必须 ≤ 本行 created_at + INTERVAL '1 second'"，与 §3.1 IMMUTABLE CHECK 对齐

V1.4 相对 V1.3 解决以下问题：

V1.3 新引入阻塞项（2）：
- B8：G8c（换热器管破裂）未集成到标准注册表，门禁无法触发。V1.4 修复：`PSV_OPTIONAL_STAGES` 增加 `heat_exchanger_tube_rupture`（按请求包含，不强制）；§4.1 check_capability 错误响应新增 `insufficient_case` 字段（`closed_valve` / `tube_rupture`），remediation 按 case 分流；§2.1 GB profile + §2.2 CUSTOM profile 示例增字段；§5.5 JSON Schema 同步增声明；G8c 语义真正生效
- B9：§4.3 的 CUSTOM 换热器管破裂"合法路径"会抛 NotImplementedError（500），违反"不隐式回退"。V1.4 修复（B9 方案 A）：**P5 阶段三类 profile（API/GB/CUSTOM）对换热器管破裂一律触发 G8c**，禁止任何 profile 提供"合法路径"，调用入口由 resolver 拦截，不出现 NotImplementedError

残留（1，第三次）：
- S2-residual（第三次）：§8.5 测试计数仍不对账（正文 28 vs 清单 30）。V1.4 修复：明确计数口径为"按断言分组"，清单 30 条（门禁 14 + 标准/环节 9 + 辅助 7），验收基线 1662 + 30 = **≥1692**；§8.4 V1.2 残留基线声明统一指向 §8.5

次要（5）：
- n1：§4.4 ω/ωs 描述自相矛盾（"已更正归入" vs 仍保留取值）。V1.4 修复：明确"编号归入但子方法实质仍区分"为工艺室待确认项；实施时两种取值都接受，避免实施期阻塞
- n2：§4.2 E3 的"GB 分支 P5 不实施"是范围变更，未在修订说明中标注。V1.4 修复：显式标注 GB 火灾分支从 P5 交付范围移到 P5 前置条件（工艺室签字对账表），关联 P5-OPEN-00U，Task 13 工期受影响
- n3：§2.1 API profile `two_phase.standard = "API_520_Appendix_D"` 与 §4.4 E6 修正（附录 C）不一致。V1.4 修复：改为 `API_520_Appendix_C`
- n4：§2.1 `orifice.orifice_table_status` 是 profile 级字段，请求级不应出现。V1.4 修复：§2.1 注 2 + §5.5 同步标注"仅 profile 级，请求级由响应 `orifice_selection_degraded=true` 体现"
- n5：§7 验收表"GB/T 28778 先导式拒绝路径"未对齐 G12 三情形 (a)(b)(c)。V1.4 修复：测试项明确覆盖 G12 三情形，每情形 1 断言共 3 断言

V1.3 相对 V1.2 解决以下问题：

阻塞项（3）：
- B5：`future_dated_forbidden_chk` 在 PostgreSQL CHECK 约束中引用 `NOW()` 不合法（NOW() 是 STABLE 而非 IMMUTABLE）。改为 `effective_from <= created_at + INTERVAL '1 second'`，仅引用本表列
- B6：§11.1 迁移脚本引用不存在的 `migrated_at` 列。删除 `migrated_at`，`created_at` 已记录迁移时刻
- B7：§3.2 部分索引引用未声明的 `sign_status` 列。改为 `(project_id)` 单列部分索引（与 D1 拍板建议一致）

不彻底项（3）：
- U1：§8.2 任务清单仍 V1.1 文案。更新为 V1.2 补齐（含 G11/G12 + 词表注册 + 未来日期约束替代）
- U2：§8.4 API 校验清单缺 G11/G12。补齐
- U3：`pilot_operated` 在 API profile 下请求被静默跳过违反"不隐式回退"。G12 泛化为"请求包含 pilot_operated 但当前 profile 未提供可实现路径 → 422"；§4.1 check_capability 区分"未请求" vs "请求但缺失"

残留（1）：
- S2-residual：§8.5 测试计数仍不对账（正文 24 vs 清单 28）。改为清单 28 条 + 验收基线 1662 + 28 = **≥1690**

次要（3）：
- m1：§11.2 步骤编号重复。重新编号
- m2：`P5_UNIMPLEMENTABLE_STANDARDS` 后续需迁配置表。§10 Backlog 加
- m3：`pilot_operated.enabled` JSON Schema 约束未明。§5.5 补

计算程序错误（9 项，V1.2 评审发现，整合到 V1.3 同一批提交）：
- E1（高）：§4.2 API 521 火灾 C 值仅写 21,000，缺无 adequate drainage 的 34,500；公式未强调 wetted surface area（非容器总表面积）
- E2（中）：§4.2 润湿面积计算缺 25 ft 液位上限规则 + 球罐独立公式
- E3（高）：§4.2 GB/T 150.1 附录B 分支只有框架，缺完整公式（吸热量 / 汽化潜热）
- E4（高）：§4.4 API 520 泄放面积缺背压修正系数 Kb + 组合修正系数 Kc
- E5（中）：§4.4 GB/T 12241 减低系数 0.9 缺理论路径（理论排量 × 额定排量系数）
- E6（高）：§4.4 API 520 两相流附录编号 D → C 修正；明确 ω 法 / ωs 法适用条件 + 第十版对子方法编号的更正
- E7（中）：§1.2 + §4.3 + G8 范围遗漏换热器管破裂工况（HG/T 20570.2 同样未提供完整公式）；G8 范围扩展
- E8（中）：§2.1 GB profile `pilot_operated.enabled = false` 时请求 pilot_operated 的行为与 §7 验收表"拒绝路径"矛盾；明确 `enabled = false` + 请求 → 拒绝（与 V1.3 U3 联动）
- E9（低）：§3.4 canonical JSON 固定位数（API ≤6 / GB ≤4）改工程有效数字（泄放量 3 位、比热比 2 位小数、温度 1 位小数）

V1.2 相对 V1.1 解决以下问题：

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
| 换热器管破裂 | API 521 §5.3（管破口径=接管内径×max） | HG/T 20570.2-1995（**P5 不实现，详 G8c**） |
| 泄放面积 | API 520 | GB/T 12241-2021 |
| 孔口选型/尺寸确定 | API 526 | GB/T 12241-2021（**孔口表不完整时降级，详 §4.5**） |
| 先导式安全阀 | — | GB/T 28778-2023（**P5+ 评估**） |

文献研究表明，GB/T 150.1 附录B 与 API 521 在火灾工况下 公式结构、润湿面积计算、容器外壁修正系数取值 三个环节存在实质性差异，同一台容器按两套标准计算的泄放量结果不同。排量系数的定义及取值在 GB/T 12241-2021 与 API 520-2020 之间也存在差异。HG/T 20570.2-1995 作为国内石油化工行业安全阀设置和计算的首选参考规范，对控制阀故障和换热器管破裂工况**未提供完整公式**（控制阀故障无完整液体泄放公式；换热器管破裂按惯例采用 API 521 §5.3 "管破口径 = 接管内径 × max(实际, 设计限值）" + 接管根数 的修正路径，但 HG/T 20570.2-1995 原文未给出系数表 → 触发 G8c 门禁拒绝）。

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
    "standard": "API_520_Appendix_C",
    "version": "10th",
    "omega_method": "two_point"
  },
  "heat_exchanger_tube_rupture": {
    "standard": "API_521",
    "version": "7th",
    "status": "unsupported_p5",
    "reason": "P5 阶段不支持换热器管破裂工况；该工况转 P5+ 评估"
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
  "two_phase": {
    "standard": "GB_T_12241",
    "version": "2021",
    "status": "unsupported_p5",
    "reason": "P5 阶段 GB 路径两相流不实现，DIERS 积分法转 P5+"
  },
  "pilot_operated": { "standard": "GB_T_28778", "version": "2023", "enabled": false },
  "heat_exchanger_tube_rupture": {
    "standard": "HG_T_20570.2",
    "version": "1995",
    "status": "unsupported_p5",
    "reason": "原标准未提供换热器管破裂工况的完整计算公式"
  }
}
```

> 注 1：`closed_valve.status = "unsupported_p5"` 触发 G8 门禁（详 §6），请求包含此工况时直接 422，不进入计算函数。
> 注 2：`orifice.orifice_table_status = "incomplete_fallback"` 标记降级路径（详 §4.5）。n4 标注：`orifice_table_status` 是 **profile 级**配置字段，不出现在请求体；请求级若需要此信息由响应 `orifice_selection_degraded=true` + 服务端 WARN 体现（详 §5.5）。
> 注 3（E8）：`pilot_operated.enabled = FALSE` 时请求包含 `pilot_operated` 工况 → G12 (b) 情形，422 PSV_PILOT_UNSUPPORTED（详 §4.1 check_capability + §6 G12 三种情形 a/b/c）；`enabled` 字段 JSON Schema 约束见 §5.5 m3。

2.2 CUSTOM Profile

若项目需要"火灾用 GB、泄放面积用 API"等混合配置，必须定义 CUSTOM profile，并记录审批依据：

```json
{
  "profile_code": "CUSTOM",
  "fire_case": { "standard": "GB_T_150.1", "version": "2024", "clause": "附录B" },
  "closed_valve": { "standard": "API_521", "version": "7th" },
  "relief_area": { "standard": "API_520", "version": "10th" },
  "orifice": { "standard": "API_526", "version": "2017" },
  "heat_exchanger_tube_rupture": {
    "standard": "API_521",
    "version": "7th",
    "status": "unsupported_p5",
    "reason": "P5 阶段不支持换热器管破裂工况；该工况转 P5+ 评估"
  },
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

**预排程 profile 限制**（S6 + B5 + c3 修复）：P5 阶段不支持预排程 profile 写入（§3.1 `future_dated_forbidden_chk` 约束拦截）。`effective_from` 必须 ≤ **本行 `created_at + INTERVAL '1 second'`**（约束依赖本表列，引用 `NOW()` 会破坏 IMMUTABLE）。新生效配置写入即视为即时生效；若需"未来某日起生效"语义，请走 P5+ 评审 + ADR 复审。

§3 数据模型
---
3.1 新增表：project_calculation_standard_profiles

```sql
-- B4 修复：EXCLUDE 约束需要 btree_gist 支持跨类型 = 运算符
CREATE EXTENSION IF NOT EXISTS btree_gist;

CREATE TABLE project_calculation_standard_profiles (
    id                      BIGSERIAL PRIMARY KEY,
    project_id              BIGINT NOT NULL REFERENCES projects(id),
    discipline              VARCHAR(16) NOT NULL,  -- 'PSV' / 'VESSEL' / 'HEAT' ...
    profile_code            VARCHAR(16) NOT NULL,  -- 'API' / 'GB' / 'CUSTOM'
    standard_refs_json      JSONB NOT NULL,         -- 各子标准、版本、条款映射
    approval_json           JSONB,                  -- CUSTOM 时必填，含审批人+依据
    is_default              BOOLEAN NOT NULL DEFAULT FALSE,
    migrated_default        BOOLEAN NOT NULL DEFAULT FALSE,  -- B1 修复：迁移占位标志，与 psv_results/relief_results 同名同语义
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
    -- S6/B5 修复：P5 不支持预排程 profile（effective_from 必须已生效或即时生效）
    -- 仅引用本表列，避开 NOW() 的 STABLE 语义（CHECK 约束要求 IMMUTABLE）
    CONSTRAINT future_dated_forbidden_chk CHECK (effective_from <= created_at + INTERVAL '1 second'),
    CONSTRAINT project_standard_default_unique
        EXCLUDE USING gist (
            project_id WITH =,
            discipline WITH =,
            tstzrange(effective_from, COALESCE(effective_to, 'infinity'::timestamptz), '[)') WITH &&
        ) WHERE (is_default = TRUE AND migrated_default = FALSE)
);
-- S1 修复：current_default 部分索引已排除 migrated_default
CREATE INDEX idx_pcs_project_discipline_default
    ON project_calculation_standard_profiles (project_id, discipline)
    WHERE is_default = TRUE AND migrated_default = FALSE AND effective_to IS NULL;
-- S1 修复：迁移占位部分索引（供 §11.4 复核队列查询）
CREATE INDEX idx_pcs_profile_migrated_default
    ON project_calculation_standard_profiles (project_id, discipline)
    WHERE migrated_default = TRUE;
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
-- B3 修复：override 字段成对 CHECK（与 G7 + D1 决议对齐；防止后台/迁移/直接 SQL 绕过 API 层）
ALTER TABLE psv_results ADD CONSTRAINT psv_override_paired_chk CHECK (
    (override_reason IS NULL AND override_approval_json IS NULL) OR
    (override_reason IS NOT NULL AND override_approval_json IS NOT NULL)
);
-- S1 修复：复核队列部分索引（项目内绝大多数 FALSE，索引代价极低）
CREATE INDEX idx_psv_results_pending_review
    ON psv_results(project_id) WHERE pending_review = TRUE;
-- S1 修复：迁移清单部分索引
CREATE INDEX idx_psv_results_migrated_default
    ON psv_results(project_id) WHERE migrated_default = TRUE;

ALTER TABLE relief_results ADD COLUMN standard_profile_code VARCHAR(16);
ALTER TABLE relief_results ADD COLUMN standard_refs_json JSONB;
ALTER TABLE relief_results ADD COLUMN formula_ref_json JSONB;
ALTER TABLE relief_results ADD COLUMN pending_review BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE relief_results ADD COLUMN migrated_default BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE relief_results ADD COLUMN override_reason TEXT;
ALTER TABLE relief_results ADD COLUMN override_approval_json JSONB;
-- B3 修复
ALTER TABLE relief_results ADD CONSTRAINT relief_override_paired_chk CHECK (
    (override_reason IS NULL AND override_approval_json IS NULL) OR
    (override_reason IS NOT NULL AND override_approval_json IS NOT NULL)
);
-- S1 修复
CREATE INDEX idx_relief_results_pending_review
    ON relief_results(project_id) WHERE pending_review = TRUE;
CREATE INDEX idx_relief_results_migrated_default
    ON relief_results(project_id) WHERE migrated_default = TRUE;
```

约束：
- `standard_profile_code` 和 `standard_refs_json` 为 NOT NULL（P5-3 实施后）
- `pending_review = TRUE` 表示标准配置变更后旧记录需复核，**自动触发**（详 §5.6）
- `migrated_default = TRUE` 表示历史项目迁移默认值，**不作为正式默认**（仅作占位），需人工 `pending_review` 流程转为正式默认
- `override_reason` 与 `override_approval_json` 必须成对非空或成对空（`override_paired_chk`）；G7 在 API 层校验 422，DB 层兜底防绕过
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
- **数值**：定点数十进制（如 `0.975` 而非浮点 `0.9750000000000001`）；按字段物理意义取**工程有效数字**（E9 修复）：
  - 泄放量 W（kg/h 或 m³/h）：3 位有效数字（如 `12300` 而非 `12345.6789`）
  - 比热比 γ / Cp 比：2 位小数（如 `1.40` 而非 `1.4034567`）
  - 温度 T（℃ 或 K）：1 位小数（如 `425.0` 而非 `424.87`）
  - 面积 A（m²）：3 位有效数字
  - 孔径 d（mm）：2 位小数
  - 其他无量纲系数（C / Kd / Kb / Kc）：保留原始标准表给定的有效位数（API 521 取 0.001 / GB/T 12241 取 0.01）
- **空值语义**：`null` 与字段缺失必须一致（统一 `null`）
- **审批信息**：审批依据（approved_by/approved_at）**不**进入 record_hash（用于权限审计，但避免审批时间变更触发 hash 漂移）
- **覆盖信息**：`override_reason` 与 `override_approval_json` **不**进入 record_hash（用于审计，避免审批变更触发 hash 漂移）

实现位置：utils/canonical_json.py 提供 `canonical_dumps(obj) -> str` 函数，所有 record_hash 输入走该函数。

§4 计算引擎改造
---
4.1 标准解析层（standard_resolver）

在服务层之上增加 standard_resolver 层，由它决定调用哪套底层计算函数。

**P5 阶段不可实现标准词表**（B2 修复：集中判定，散落拒绝与词表漂移隔离）：

```python
# app/services/standard_registry.py
P5_UNIMPLEMENTABLE_STANDARDS: frozenset[str] = frozenset({
    "HG_T_20570.2",   # 控制阀故障 + 换热器管破裂液体泄放量无完整公式（D-01 + G8 + E7/G8c）
})
# 后续 P5+ 补齐时仅追加此集合

# PSV discipline mandatory 阶段（S3 修复：closed_valve 必填，不可静默放行）
PSV_MANDATORY_STAGES: frozenset[str] = frozenset({
    "fire_case", "closed_valve", "relief_area", "orifice",
})
PSV_OPTIONAL_STAGES: frozenset[str] = frozenset({
    "two_phase", "pilot_operated", "heat_exchanger_tube_rupture",   # B8 修复：管破裂按请求包含，不强制
})
```

```python
class StandardResolver:
    def resolve(
        self, project_id: int, discipline: str = "PSV"
    ) -> PsvStandardProfile:
        """
        解析项目当前生效的默认标准配置。
        若项目未配置 → raise PsvStandardNotConfiguredError (422, G1)
        迁移占位（migrated_default=TRUE）经人工复核前不可被 resolve 选中（B1 修复）

        SQL 实现：SELECT ... WHERE project_id=? AND discipline=? AND is_default=TRUE
                       AND migrated_default=FALSE AND effective_to IS NULL
        命中 `idx_pcs_project_discipline_default` 部分索引。
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
        按请求工况级联检查 profile 能力。

        B2 修复：双判定
        (1) ref.standard ∈ P5_UNIMPLEMENTABLE_STANDARDS → 拒绝
        (2) ref.status == "unsupported_p5" → 拒绝
        任一 unsupported 阶段 → 422 PSV_PROFILE_INSUFFICIENT

        S3 修复：mandatory 阶段缺失 → 422 PSV_PROFILE_INSUFFICIENT（不可静默放行）

        U3 修复：区分 optional 阶段的两种缺失语义
        (a) 请求未包含该 optional 阶段 → 不检查（正常跳过，不计算）
        (b) 请求包含该 optional 阶段，但 profile 未覆盖 → 422 PSV_PROFILE_INSUFFICIENT
        (c) 请求包含该 optional 阶段，profile 标 enabled=FALSE / unimplementable → 422

        这样避免"不隐式回退"原则被破坏：用户显式请求的阶段必须被解析或被显式拒绝。

        B11 修复（方案 A）：按 insufficient_stage 映射 error_code：
        - two_phase → PSV_TWO_PHASE_GB_UNSUPPORTED
        - pilot_operated → PSV_PILOT_UNSUPPORTED
        - 其他（closed_valve / heat_exchanger_tube_rupture / mandatory 缺失 / 未定义 stage） → PSV_PROFILE_INSUFFICIENT
        错误码与 G10/G12 声明完全对齐，不再退化为单一 PSV_PROFILE_INSUFFICIENT。
        """
        # B11：错误码按 stage 分发
        _STAGE_ERROR_CODE = {
            "two_phase": "PSV_TWO_PHASE_GB_UNSUPPORTED",
            "pilot_operated": "PSV_PILOT_UNSUPPORTED",
        }
        def _error_code(stage: str) -> str:
            return _STAGE_ERROR_CODE.get(stage, "PSV_PROFILE_INSUFFICIENT")

        all_known = PSV_MANDATORY_STAGES | PSV_OPTIONAL_STAGES
        for stage in requested_stages:
            if stage not in all_known:
                raise PsvProfileInsufficientError(
                    project_id=profile.project_id,
                    discipline=profile.discipline,
                    profile_code=profile.profile_code,
                    insufficient_stage=stage,
                    error_code="PSV_PROFILE_INSUFFICIENT",  # B11：未知 stage 强制通用码
                    standard="(unknown_stage)",
                    version="-",
                    reason=f"未定义的计算阶段 {stage}",
                    remediation=[f"请求阶段必须在 {sorted(all_known)} 之内"]
                )
            ref = profile.standard_refs.get(stage)
            if ref is None:
                # 阶段在 profile 中未配置
                if stage in PSV_MANDATORY_STAGES:
                    raise PsvProfileInsufficientError(
                        project_id=profile.project_id,
                        discipline=profile.discipline,
                        profile_code=profile.profile_code,
                        insufficient_stage=stage,
                        error_code=_error_code(stage),  # B11：mandatory 阶段也按 stage 映射
                        standard="(missing_in_profile)",
                        version="-",
                        reason=f"mandatory 阶段 {stage} 在 profile 中缺失",
                        remediation=[f"为 {stage} 配置标准（GB profile 必带 status=unsupported_p5）"]
                    )
                # U3：optional 阶段在 profile 中未配置，但被显式请求 → 必须拒绝，不静默跳过
                raise PsvProfileInsufficientError(
                    project_id=profile.project_id,
                    discipline=profile.discipline,
                    profile_code=profile.profile_code,
                    insufficient_stage=stage,
                    error_code=_error_code(stage),  # B11：按 stage 映射（G10/G12 走专用错误码）
                    standard="(not_covered_by_profile)",
                    version="-",
                    reason=f"optional 阶段 {stage} 在 profile {profile.profile_code} 中未覆盖，且被请求显式启用",
                    remediation=[
                        f"改用覆盖 {stage} 的 profile 或 CUSTOM profile",
                        f"或从 requested_stages 中移除 {stage}"
                    ]
                )
            # 阶段已配置：检查是否可实现
            if ref.get("enabled") is False:
                # U3：显式标 enabled=FALSE（如 GB profile 的 pilot_operated）
                raise PsvProfileInsufficientError(
                    project_id=profile.project_id,
                    discipline=profile.discipline,
                    profile_code=profile.profile_code,
                    insufficient_stage=stage,
                    error_code=_error_code(stage),  # B11：按 stage 映射
                    standard=ref.get("standard", "-"),
                    version=ref.get("version", "-"),
                    reason=f"阶段 {stage} 在 profile 中显式 enabled=FALSE",
                    remediation=[f"将 {stage}.enabled 改为 TRUE，或从请求中移除该阶段"]
                )
            standard = ref.get("standard")
            if standard in P5_UNIMPLEMENTABLE_STANDARDS or ref.get("status") == "unsupported_p5":
                # B8 + M3 修复：insufficient_case 按 stage 名输出（语义清晰，统一取值范围）
                # 取值范围：{"closed_valve", "tube_rupture", "two_phase", "pilot_operated", "unsupported"}
                # "closed_valve" / "tube_rupture" 保留兼容别名（前端按 insufficient_case 分流 G8 / G8c 时已有约定）
                # 其他 stage 直接用 stage 名（如 "two_phase" / "pilot_operated"），便于前端按 insufficient_case 决定错误码展示
                if stage == "heat_exchanger_tube_rupture":
                    insufficient_case = "tube_rupture"
                elif stage == "closed_valve":
                    insufficient_case = "closed_valve"
                else:
                    insufficient_case = stage   # M3：two_phase / pilot_operated / 其他 → stage 名
                if insufficient_case == "closed_valve":
                    remediation = [
                        "改用 CUSTOM profile，closed_valve 指定 API_521 并附审批依据",
                        "或将 closed_valve 工况排除在本项目 PSV 计算范围外"
                    ]
                elif insufficient_case == "tube_rupture":
                    remediation = [
                        "P5 不实现换热器管破裂计算；m2 扩展项转 P5+ 评估",
                        "将 heat_exchanger_tube_rupture 工况排除在本项目 PSV 计算范围外",
                        "若项目必须包含此工况，整体关闭 PSV 计算并联系工艺室走项目变更"
                    ]
                else:
                    remediation = ["或将此工况排除在本项目 PSV 计算范围外"]
                raise PsvProfileInsufficientError(
                    project_id=profile.project_id,
                    discipline=profile.discipline,
                    profile_code=profile.profile_code,
                    insufficient_stage=stage,
                    error_code=_error_code(stage),  # B11：按 stage 映射（two_phase→PSV_TWO_PHASE_GB_UNSUPPORTED, pilot_operated→PSV_PILOT_UNSUPPORTED）
                    insufficient_case=insufficient_case,   # B8 新增字段，供前端 / OpenAPI 区分
                    standard=standard,
                    version=ref.get("version", "-"),
                    reason=ref.get("reason", "原标准未提供完整计算公式"),
                    remediation=remediation
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
- **公式**：Q = C × F × A^0.82
  - C 值（E1 修复）：adequate drainage + prompt firefighting → **21,000**（BTU/hr·ft²）；其他工况 → **34,500**（含 inadequate drainage）。代码必须按排水条件分支选择 C 值，**不**允许统一使用 21,000 低估无排水工况的泄放量
  - **A 必须为 wetted surface area**（E1 修复），**不**是容器总表面积；F 为容器外壁修正系数
- **润湿面积**（E2 修复）：
  - 立式容器：取液位高度对应的圆柱侧面积，**液位上限 25 ft（约 7.6 m）**，超出按 25 ft 截断
  - 卧式容器：取 75% 的暴露面积，**计算至 30 ft 高度**截断
  - **球形储罐**：API 521 独立公式（按球罐表面积 × 55% 或按球罐实际液位对应球冠面积，详 API 521 7th Ed. §4.4.5）
- 修正系数：API 521 容器外壁修正系数

GB/T 150.1 附录B 分支（E3 修复：补完整公式结构）：
- **公式**：W = Q_abs / r
  - Q_abs：容器吸热量 = C' × A_w^0.82 × F_w（C' 为 GB 燃料系数；A_w 为 GB 润湿面积；F_w 为 GB 容器外壁修正系数）
  - r：液化气体在泄放状态下的汽化潜热
  - 燃料系数、润湿面积、外壁修正系数三个环节**与 API 521 均有实质差异**，不可在底层函数内 if standard == "GB" 分支共享
- 验收基准（E3 整改）：公式细节需工艺室提供具体 GB 标准算例与手算对账（详 §10 Backlog）；SPEC 此处只锁公式结构，参数取值由 Task 13 实施时附工艺室签字对账表

验收基准：
- API 分支：API 521 算例 / 商业软件，≤2%
- GB 分支：GB 标准算例 / 工艺室手算，阈值由工艺室确认（建议 ≤5%）；E3 整改前 P5 不实施 GB 分支，Task 13 启动前须有工艺室签字的 GB 算例对账表

> **范围变更（n2 标注 + M1 V1.5.1 修复）**：E3 修复将 GB 火灾分支从 **P5 交付范围** 移到 **P5 前置条件**（工艺室签字对账表）。Task 13 工期影响：对账表未签字前 P5 不实施 GB 分支；签字后 P5+ 评估补齐或直接纳入 P5 修订版。建议 P5 启动评审会上确认（详 §9 **P5-OPEN-00T**，M1 V1.5.1 新增 OPEN 项；00U 是 closed_valve 项，不可混用）。

4.3 Task 14 改造：其他工况

GB profile 的 `closed_valve` 标记为 `unsupported_p5`（详 §2.1 + G8）。`calc_closed_valve_case_GB()` **不实施**——请求包含此工况时由 §4.1 `check_capability` 在 resolver 层抛 `PsvProfileInsufficientError`，不进入任何计算函数。

CUSTOM profile 的 `closed_valve.standard = "API_521"` 合法路径走 `calc_closed_valve_case_API()`，formula_ref.closed_valve 指向 API 521 7th。

**换热器管破裂工况（E7 + B9 方案 A 扩展）**：GB / CUSTOM / API 三类 profile 在 P5 阶段对 `heat_exchanger_tube_rupture` 工况一律触发 G8c 拒绝（详 §2.1 + §2.2 + G8c）——HG/T 20570.2-1995 未提供完整公式，API 521 §5.3 占位计算（P5 不实现，转 P5+ m2 评估）。请求包含 `heat_exchanger_tube_rupture` 工况时，§4.1 `check_capability` 抛 `PsvProfileInsufficientError`，错误码细分 `insufficient_case = "tube_rupture"`，与 `closed_valve` 共用 PSV_PROFILE_INSUFFICIENT 但 `remediation` 不同（前者推荐"将此工况排除在 PSV 计算范围外 + 联系工艺室走项目变更"；后者推荐改用 API_521 closed_valve）。

**B9 方案 A 落地**：禁止任何 profile 在 P5 阶段为换热器管破裂提供"合法路径"。CUSTOM profile 若声明 `heat_exchanger_tube_rupture.standard = "API_521"` 仍触发 G8c（与 G8 同样：能力缺失与审批解耦，审批齐全不绕过 P5 实施边界）。`calc_heat_exchanger_tube_rupture_*` 计算函数 P5 阶段**不定义**，调用入口由 resolver 拦截；不出现 `NotImplementedError`（后者会映射到 500，违反"不隐式回退"原则）。

4.4 Task 16 改造：泄放面积

```python
calc_relief_area(
    inp: ReliefAreaInput,
    standard: ReliefAreaStandard  # 由 StandardResolver 注入
) -> ReliefAreaResult
```

API 520 分支（E4 + E6 修复）：
- **公式**：A = W / (C × Kd × Kb × Kc × ... )
  - 排量系数 Kd（制造厂试验值，典型 0.975）
  - **背压修正系数 Kb**（E4 修复）：临界流 Kb = 1；亚临界流按 API 520 Figure 30 取值（背压比 Pb/Pdr 的函数）
  - **组合修正系数 Kc**（E4 修复）：安全阀+爆破片组合时按 API 520 §3.6 取值；普通弹簧式安全阀 Kc = 1
- **两相流方法**（E6 修复）：
  - 附录编号：**附录 C**（Part I 第八版起；V1.2 误写为附录 D 已修正）
  - **ω 法**（API 520 附录 C.2.2）：适用于进入安全阀前已存在气相的两相系统
  - **ωs 法**（API 520 附录 C.2.3）：适用于进入安全阀前为液相、进入后可能闪蒸的工况
  - **第十版子方法编号（n1 待工艺室确认）**：第八/九版的 C.2.3 ωs 法在第十版 Errata 中编号归入 C.2.2 ω 法（仅编号合并，子方法实质仍区分）→ `omega_method` 取值 `omega` | `omega_s` 均合法，分别走 C.2.2 主体 / C.2.2 子方法 ωs；若工艺室确认第十版**取消 ωs 独立子方法** → `omega_method` 仅 `omega` 合法，`omega_s` 作为别名等价于 `omega`。**V1.4 锁定待工艺室对照 API 520 10th Ed. Errata 原文确认**；实施时两种取值都接受（避免实施期阻塞）
  - 默认 method：**two_point**（用户请求未指定时），可显式指定 `omega_method = "omega" | "omega_s"`（n1：两种取值都合法，详见上一条工艺室确认）
- D-06 关闭：GB 路径两相流 DIERS 积分法转 P5+

GB/T 12241 分支（E5 修复）：
- 排量系数确定路径与 API 不同：GB/T 12241-2021 §7.4 规定了排量系数的确定方法，§7.5 规定了额定排量系数
- **额定排量三种方式并存**（E5 修复）：
  1. 实测排量 × 减低系数（0.9）
  2. 理论排量 × 排量系数 × 0.9
  3. 理论排量 × 额定排量系数（即排量系数 × 0.9）
  - 路径 1 用于有实测数据场景（认证后）；**路径 2/3 用于初步设计阶段**（SPEC 此前遗漏理论路径）
- **亚临界流动需乘以排量修正系数 Kb**（GB/T 12241 表 4，**E4 修复**：必须从表 4 按背压比 Pb/Pdr 取值，**不**允许固定 1.0）
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
    "closed_valve": { "standard": "HG_T_20570.2", "version": "1995", "status": "unsupported_p5", "reason": "原标准未提供控制阀故障液体泄放量的完整计算公式" },
    "relief_area": { "standard": "GB_T_12241", "version": "2021" },
    "orifice": { "standard": "GB_T_12241", "version": "2021", "orifice_table_status": "incomplete_fallback" },
    "two_phase": { "standard": "GB_T_12241", "version": "2021", "status": "unsupported_p5", "reason": "P5 阶段 GB 路径两相流不实现，DIERS 积分法转 P5+" },
    "pilot_operated": { "standard": "GB_T_28778", "version": "2023", "enabled": false },
    "heat_exchanger_tube_rupture": { "standard": "HG_T_20570.2", "version": "1995", "status": "unsupported_p5", "reason": "原标准未提供换热器管破裂工况的完整计算公式" }
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

**判定顺序**（S5 修复：明确 G2 vs G7 优先级）：
1. **权限检查**（G2）→ 无权限 403 PSV_STANDARD_OVERRIDE_FORBIDDEN（**优先返回**）
2. **审批依据检查**（G7）→ 有权限但缺 `override_reason`/`override_approval` → 422 PSV_OVERRIDE_APPROVAL_REQUIRED
3. **Profile 能力检查**（G8/G8c/G9/G10/G12）→ 422 PSV_PROFILE_INSUFFICIENT（closed_valve + 换热器管破裂共用错误码，`unsupported_case` 区分）/ PSV_TWO_PHASE_GB_UNSUPPORTED / PSV_PILOT_UNSUPPORTED
4. **计算执行**

G2 优先于 G7 的理由：未授权者不应通过错误信息探测系统状态（避免"缺审批依据"等错误提示泄露系统内部能力存在性）。G2 也优先于 G8（capability 检查需要先通过权限），否则无权用户会收到 422 而非 403，泄露存在的能力。

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

- `standard_refs_json` 必填键按 discipline 区分；**S3 修复**：PSV discipline 必填 `fire_case` + `closed_valve` + `relief_area` + `orifice`（与 §4.1 `PSV_MANDATORY_STAGES` 对齐），可选 `two_phase` / `pilot_operated` / `heat_exchanger_tube_rupture`（B8 修复：与 §4.1 `PSV_OPTIONAL_STAGES` 对齐）
- **B10 修复**：三类 profile（API / GB / CUSTOM）**均必填** `heat_exchanger_tube_rupture` 子对象，否则 schema 校验失败。三类示例：
  - API：`{"standard": "API_521", "version": "7th", "status": "unsupported_p5", "reason": "P5 阶段不支持换热器管破裂工况；该工况转 P5+ 评估"}`
  - GB：`{"standard": "HG_T_20570.2", "version": "1995", "status": "unsupported_p5", "reason": "原标准未提供换热器管破裂工况的完整计算公式"}`
  - CUSTOM：同 API（用户友好 reason）
- **GB profile 必须显式写 closed_valve + two_phase + heat_exchanger_tube_rupture**（c2 修复：GB + two_phase 需命中 unsupported_p5 分支而非 U3 分支）：closed_valve 与 heat_exchanger_tube_rupture 走 HG/T 20570.2 unsupported_p5；two_phase 走 GB/T 12241 unsupported_p5
- 每个 `{standard, version, clause?}` 子对象必填 `standard` + `version`，`clause` 可选但 `fire_case`（GB 路径）必填
- `status` 字段仅允许 `unsupported_p5` 或缺省；缺省 = 支持
- `orifice_table_status` 仅允许 `incomplete_fallback` 或缺省；缺省 = 完整（n4：仅 profile 级，请求级不出现）
- m3 修复：`pilot_operated` 子对象可选字段 `enabled: boolean`，缺省 = `true`；`enabled = false` 表示 profile 显式关闭该阶段，请求含 `pilot_operated` 时由 §4.1 check_capability 拒绝（U3 + G12 联动）
- B8 修复：`heat_exchanger_tube_rupture` 子对象与 `closed_valve` 共用 `status: unsupported_p5` 拒绝路径，错误响应含 `insufficient_case: "tube_rupture"`（详 §4.1 check_capability + G8c）
- B11 修复：响应错误码按 stage 映射（详 §4.1 `_STAGE_ERROR_CODE`）：two_phase → PSV_TWO_PHASE_GB_UNSUPPORTED；pilot_operated → PSV_PILOT_UNSUPPORTED；其他 → PSV_PROFILE_INSUFFICIENT
- M3 修复：响应 `insufficient_case` 字段取值范围 `{"closed_valve", "tube_rupture", "two_phase", "pilot_operated", "unsupported"}`——`closed_valve` / `tube_rupture` 保留兼容别名；`two_phase` / `pilot_operated` 直接用 stage 名；其他 mandatory / 未知 stage → `"unsupported"`。前端按 `insufficient_case` 分流 G8 / G8c / G10 / G12 错误展示

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
| **G12**（V1.2 新增，V1.3 泛化） | **请求包含 `pilot_operated` 工况，但当前 profile 未提供可实现路径**（三种情形：(a) profile 无 pilot_operated 字段；(b) `pilot_operated.enabled = FALSE`；(c) `pilot_operated.standard ∈ P5_UNIMPLEMENTABLE_STANDARDS`） | 422 PSV_PILOT_UNSUPPORTED（D-07 转 P5+；**统一 422 不再用 501**） |

禁止隐式回退 API。项目未配置时，计算请求必须返回 422，不得自动使用 API 作为默认。

§7 验收基准
---
| 标准/环节 | 验收基准 | 阈值 |
|---|---|---|
| API 521 火灾 | API 521 算例 / 商业软件 | ≤2% |
| GB/T 150.1 附录B 火灾 | **P5 交付范围外**（n2-residual 标注：E3 范围变更，作为 P5 前置条件跟踪，详 §4.2 范围变更 + §10 P5-OPEN-00U）；验收基准由工艺室签字对账表后补齐 | 待工艺室签字 |
| API 520 泄放面积 | API 520 算例 / HYSYS | ≤2% |
| GB/T 12241 泄放面积 | 标准算例 | 由工艺室确认 |
| API 520 两相流 | HYSYS / 文献 | ≤5% |
| **HG/T 20570.2 控制阀故障（GB profile）** | 拒绝路径：项目 GB profile + closed_valve → 422 PSV_PROFILE_INSUFFICIENT | 响应码与错误码断言 |
| **HG/T 20570.2 控制阀故障（CUSTOM profile，closed_valve=HG_T_20570.2）** | 拒绝路径：审批不能解锁未实现能力 → 422 PSV_PROFILE_INSUFFICIENT | 响应码断言 |
| **GB 路径两相流** | 拒绝路径：项目 GB profile + two_phase → 422 PSV_TWO_PHASE_GB_UNSUPPORTED | 响应码与错误码断言 |
| **GB/T 12241 孔口选型（降级路径）** | 输出 `required_diameter_mm` + `orifice_selection_degraded=true` + 服务端 WARN 日志 | 响应体断言 + 日志断言 |
| **CUSTOM 混合（fire_case=GB + closed_valve=API_521）** | 正常返回，`formula_ref.fire_case` 指向 GB/T 150.1，`formula_ref.closed_valve` 指向 API 521 | formula_ref 字段断言 |
| **GB/T 28778 先导式** | 拒绝路径覆盖 G12 三情形（n5-residual 修复）：(a) API profile + `pilot_operated: null` → 422 PSV_PILOT_UNSUPPORTED；(b) GB profile + `pilot_operated.enabled = FALSE` → 422 PSV_PILOT_UNSUPPORTED；(c) `pilot_operated.standard ∈ P5_UNIMPLEMENTABLE_STANDARDS` → 422 PSV_PILOT_UNSUPPORTED（V1.2 统一 422，**不再用 501**） | 三情形响应码与错误码断言（3 测试） |
| **G1-G12 + G8b + G8c 门禁**（V1.2 更新 + V1.5 扩 G8b/G8c，B12 修复：与 §8.5 门禁类 14 条对齐） | 每条 1 测试 | **14 测试** |
| **历史迁移 migrated_default 复核** | 迁移后既有记录 `migrated_default = TRUE` + `pending_review = TRUE`，**不**作为正式默认 | DB 状态断言 |
| **标准配置变更 pending_review** | 项目级 profile 变更 → 旧记录 `pending_review = TRUE`（自动） | DB 状态断言 |
| **record_hash 跨标准差异** | 同一输入 × API vs GB → 两条独立记录，record_hash 不同 | hash 断言 |
| **override 权限与审批** | 覆盖默认 + 无 `override_reason` → 422 PSV_OVERRIDE_APPROVAL_REQUIRED；无权限 → 403 | 响应码断言 |
| **canonical JSON 规范** | 同标准同输入跨项目 hash 一致；不同 standard 字段 hash 不同 | hash 断言 |

合计新增测试基线（V1.2 基线声明，已被 §8.5 V1.3 覆盖 — **以 §8.5 为准**）：
- V1.2 写：合计 24 个（12 门禁 + 8 标准/环节 + 4 辅助） → ≥1686
- **V1.3 修订**：S2-residual 第三次对账后实际 30 条（14 + 9 + 7） → **≥1692**，详 §8.5

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
| **P5-OPEN-00T**（M1 V1.5.1 新增） | 待 P5 启动评审会确认 | GB/T 150.1 附录B 火灾分支范围变更（从 P5 交付范围移至前置条件，工艺室签字对账表）：签字后 P5+ 评估补齐或直接纳入 P5 修订版；与 §4.2 范围变更标注 + §7 验收表"P5 交付范围外"联动 |
| **P5-OPEN-00R**（M4 V1.5.1 新增） | 待工艺室对照标准原文确认 | API 520 10th Ed. 附录 C ω/ωs 子方法编号（ωs 是否独立保留）：实施期两种取值都接受避免阻塞；签字后回填 §4.4 表述 |

8.2 P5-0 增加前置任务

Task P5-0-5：PSV 标准配置模型（**V1.2 补齐 7 列 + 词表 + 未来日期约束替代 + G11/G12**）

- 建 `project_calculation_standard_profiles` 表（V1.2 完整 schema）：
  - `effective_to` + EXCLUDE 约束 + `discipline` / `profile_code` CHECK
  - `migrated_default` 列（B1）
  - `future_dated_forbidden_chk` 约束（B5 修复：`effective_from <= created_at + INTERVAL '1 second'`）
  - `CREATE EXTENSION IF NOT EXISTS btree_gist;`（B4 修复）
- 给 `psv_results` / `relief_results` 加 `standard_profile_code` + `standard_refs_json` + `formula_ref_json` + `pending_review` + `migrated_default` + `override_reason` + `override_approval_json`（共 7 列）
  - `override_paired_chk` 约束（B3 修复：DB 层兜底）
  - 4 条部分索引：`pending_review` / `migrated_default` × psv_results / relief_results（B7 修复：仅 `project_id`，不引用 `sign_status`）
- 注册 `PsvStandardProfileCode` 枚举
- 注册 `P5_UNIMPLEMENTABLE_STANDARDS` 词表（B2 修复：标准 registry 模块）
- 写 **G1-G12 + G8b + G8c 全 14 门禁测试**（V1.5 升级：含 G11 EXCLUDE 兜底 / G12 pilot_operated 泛化 / G8b 审批不解锁 / G8c 换热器管破裂拒绝；与 §8.5 门禁类 14 条对齐，B12 修复）
- 写 `closed_valve` mandatory 缺失测试（S3 修复）
- 写 `override_paired_chk` DB 兜底测试（B3 修复）
- 写 `migrated_default` resolver 过滤测试（B1 修复）
- 实现 `utils/canonical_json.py` 提供 `canonical_dumps`
- 实现 `app/services/standard_resolver.py` 提供 `resolve` + `check_capability`（含 `enabled` 判定 + U3 修复）

8.3 Task 13/14/16/17 接口增加标准参数

标准由项目配置解析后注入，而非前端随意传递。

8.4 Task 18 API 增加校验

**V1.2 升级（U2 修复：补 G11/G12）**：

- G1：项目未配置 → 422 PSV_STANDARD_NOT_CONFIGURED
- G2：无权限覆盖 → 403 PSV_STANDARD_OVERRIDE_FORBIDDEN（**S5：权限检查优先于审批依据**）
- G7：覆盖默认 + 无审批依据 → 422 PSV_OVERRIDE_APPROVAL_REQUIRED
- G8：GB/CUSTOM closed_valve → 422 PSV_PROFILE_INSUFFICIENT（按工况；B2 词表双判定）
- G9：项目未配置 + 任意 code → 422 PSV_STANDARD_NOT_CONFIGURED
- G10：GB + two_phase → 422 PSV_TWO_PHASE_GB_UNSUPPORTED
- G11：EXCLUDE 约束并发写入 → IntegrityError（兜底）
- G12：请求 pilot_operated 但 profile 未提供可实现路径 → 422 PSV_PILOT_UNSUPPORTED（U3 泛化：覆盖缺字段 / enabled=FALSE / 词表命中三种情形）
- 落库写入 `pending_review` / `migrated_default` / `override_*` 字段
- relief_summary 按 `standard_profile_code` 分组（混合记录）
- `migrated_default = TRUE` 的 profile 行不被 resolver 选中（B1 修复：SQL `WHERE migrated_default=FALSE`）

8.5 测试基线调整

V1.0 估"≥15 个"偏少；V1.1 写 ≥25（清单 21）；V1.2 写 24（清单 28）；V1.3 写 28（清单 30）；**S2-residual 第三次彻底对账**：**清单 30 条 + 验收基线 1662 + 30 = ≥1692**。

> **计数口径声明**（S2-residual 第三次）：本节"测试条数"按 **断言分组** 计——同一用例内的不同断言（错误码、insufficient_case 字段、remediation、normal path、degraded 标记等）分别计入对应分类。这样能保证 100% 的 SPEC 行为有对应测试，避免"测试实体合并后覆盖盲区"。

新增测试（**30 条**，S2-residual 第三次对账）：

**门禁类（14 条）**：

- G1 项目未配置标准 → 422 PSV_STANDARD_NOT_CONFIGURED
- G2 无权限覆盖 → 403 PSV_STANDARD_OVERRIDE_FORBIDDEN
- G3 CUSTOM 缺审批 → 422 PSV_CUSTOM_PROFILE_APPROVAL_REQUIRED
- G4 同一输入跨标准 → 两条独立记录 + record_hash 不同
- G5 标准配置变更 → 旧记录 `pending_review = TRUE`
- G6 历史迁移 → `migrated_default = TRUE` + `pending_review = TRUE`，不可作正式默认
- G7 覆盖无审批 → 422 PSV_OVERRIDE_APPROVAL_REQUIRED
- G8 GB + closed_valve → 422 PSV_PROFILE_INSUFFICIENT（按工况）
- G8b CUSTOM closed_valve=HG_T_20570.2 + 审批齐全 → 仍 G8（审批不解锁能力）
- G8c GB/CUSTOM + heat_exchanger_tube_rupture → 422 PSV_PROFILE_INSUFFICIENT，`insufficient_case="tube_rupture"`（E7 + B8 扩展；HG/T 20570.2 未提供完整公式 + API 521 §5.3 实现转 P5+ m2 评估）
- G9 项目未配置 + 任意 code → 422
- G10 GB + two_phase → 422 PSV_TWO_PHASE_GB_UNSUPPORTED
- G11 EXCLUDE 约束并发写入 → IntegrityError
- G12 pilot_operated 三种情形（缺字段 / enabled=FALSE / 词表命中）→ 422 PSV_PILOT_UNSUPPORTED（V1.3 泛化）

**标准/环节类（9 条）**：

- HG/T 20570.2 拒绝路径：项目 GB profile + 仅 fire_case → 正常；+ closed_valve → 422
- HG/T 20570.2 CUSTOM 拒绝路径：CUSTOM closed_valve=HG_T_20570.2 + 审批齐全 → 仍 422（审批不解锁能力，B2 修复）
- 换热器管破裂拒绝路径：项目 GB/CUSTOM/API profile + 仅 fire_case → 正常；+ heat_exchanger_tube_rupture → 422 PSV_PROFILE_INSUFFICIENT `insufficient_case="tube_rupture"`（B8 + B9 方案 A：三 profile 一律拒绝；不再有"合法路径 + NotImplementedError"）
- GB 两相流拒绝路径：项目 GB profile + relief_area + two_phase → 422
- GB 孔口降级：项目 GB profile + orifice → `orifice_selection_degraded=true` + 服务端 WARN + 不可采购标记
- CUSTOM 合法路径：项目 CUSTOM closed_valve=API_521 + 审批齐全 → 正常
- GB/T 28778 先导式拒绝路径：422 PSV_PILOT_UNSUPPORTED（V1.3 统一 422；n5 修复：覆盖 G12 三情形 (a) profile 无 pilot_operated 字段 / (b) `pilot_operated.enabled = FALSE` / (c) `pilot_operated.standard ∈ P5_UNIMPLEMENTABLE_STANDARDS`，每情形 1 测试共 3 断言；E8 路径同 §2.1 注 3）
- 历史迁移 migrated_default 复核：DB 状态断言
- 标准配置变更 pending_review：项目级 profile 变更后旧记录 `pending_review = TRUE`（自动）

**辅助类（7 条）**：

- closed_valve mandatory 缺失 → 422 PSV_PROFILE_INSUFFICIENT（V1.2 S3 修复）
- btree_gist 扩展存在性 + 标准词表含 HG_T_20570.2 + heat_exchanger_tube_rupture（V1.2 B2 + B4 + B8 修复）
- record_hash canonical JSON 跨项目一致性
- record_hash 跨标准差异
- override 权限：无权限 → 403；有权限 + 无 override_reason → 422
- override 成对 CHECK 兜底：直接 SQL UPDATE 仅写 override_reason 不写 approval → DB IntegrityError（B3 修复）
- migrated_default resolver 过滤：profile 表 migrated_default=TRUE 不被 resolve 选中（B1 修复）

合计 14 + 9 + 7 = **30 条**。

P5 验收基线：P5 启动基线 1662 + 净增 ≥30 = **≥1692**。

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
- m2：`P5_UNIMPLEMENTABLE_STANDARDS` 从代码常量迁配置表（`p5_unimplementable_standards` 表 + API 管理），避免 P5+ 补齐时散落代码
- m2 扩展：HG/T 20570.2 换热器管破裂工况（E7 拓展）— 与 closed_valve 同步转 P5+ 评估

§11 数据迁移策略
---
11.1 迁移范围

历史项目（V1.0 实施前已存在的项目）需迁移 `project_calculation_standard_profiles` 记录（V1.2 明确：migrated_default 写在 profile 表，与 §3.1 schema 对齐）：

- 写入 `profile_code = 'API'` + `is_default = TRUE` + **`migrated_default = TRUE`** + `effective_from = NOW()` + `effective_to = NULL`（B6 修复：删除 V1.2 误引的 `migrated_at` 列；`created_at` 已记录迁移时刻）
- 扫描既有 `psv_results` / `relief_results` 中 `standard_profile_code IS NULL` 的记录 → 标记 `migrated_default = TRUE` + `pending_review = TRUE`
- **resolver 过滤语义**：`migrated_default = TRUE` 的 profile 行 `is_default = TRUE` 仍在 DB 落库（便于人工复核与审计），但 resolver SQL `WHERE migrated_default = FALSE` 排除，经人工复核置 `migrated_default = FALSE` 后方可被 resolve 选中

11.2 迁移脚本

`alembic/versions/p5_psv_standard_profiles_migrate.py`：

1. **CREATE EXTENSION IF NOT EXISTS btree_gist;**（B4 修复：必须在 CREATE TABLE 之前；需 DB 用户有 CREATE EXTENSION 权限）
2. CREATE TABLE `project_calculation_standard_profiles`（含 EXCLUDE 约束 + `migrated_default` 列）
3. ALTER TABLE `psv_results` / `relief_results` 加 7 列（`standard_profile_code` + `standard_refs_json` + `formula_ref_json` + `pending_review` + `migrated_default` + `override_reason` + `override_approval_json`）；ALTER TABLE ... ADD CONSTRAINT `override_paired_chk`（×2 表）；CREATE INDEX 4 条部分索引（`pending_review` / `migrated_default` × psv_results / relief_results，B7 修复：仅 `project_id`，不引用 `sign_status`）—— M5 修复：列 / 约束 / 索引 三类 DDL 分类描述
4. INSERT 默认 API 配置到所有历史项目（`migrated_default = TRUE`）
5. UPDATE 既有 `psv_results` / `relief_results` 记录：`migrated_default = TRUE` + `pending_review = TRUE`
6. 校验：EXCLUDE 约束无冲突；所有历史项目均有默认 profile

11.3 回滚方案

`downgrade()` 步骤：
1. DELETE FROM `project_calculation_standard_profiles` WHERE `migrated_default = TRUE`
2. ALTER TABLE `psv_results` / `relief_results` DROP 7 列（`standard_profile_code` + `standard_refs_json` + `formula_ref_json` + `pending_review` + `migrated_default` + `override_reason` + `override_approval_json`）；DROP CONSTRAINT `override_paired_chk`（×2 表）；DROP INDEX 4 条部分索引—— M5 修复：列 / 约束 / 索引 三类 DDL 分类描述
3. DROP TABLE `project_calculation_standard_profiles`

NOT NULL 约束在迁移完成后**下次 P5-3 启动前**才加（不在本次迁移内），保证 P5-3 实施前回滚窗口。

11.4 人工复核流程

`migrated_default = TRUE` 的默认配置必须经过工艺室复核后转为正式默认（`migrated_default = FALSE` + `pending_review = FALSE`）。UI 层提供"批量复核"入口，复核后写 `reviewed_by` + `reviewed_at`（业务层记录，V1.1 不强制 schema 增列）。
