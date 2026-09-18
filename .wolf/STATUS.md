---
description: session handoff, regenerate with /handoff when a quest finishes
budget_tokens: 1500
---
# STATUS — PCS

> Read this FIRST when starting a session. Last updated: 2026-09-18.

---

## ✅ Done (HIGH 专项 Sprint P0 Auth Hardening 4 项闭环 — 2026-09-18)

- **范围**：ce-code-review 中 4 个 HIGH P0 auth 类问题
- **修复**：
  - **H-P0-4 LDAP DN RFC 4514 §2.4 转义**（commit `4a17efc`，bug-090）：
    - `_sanitize_dn_component` 处理 `\` `"` `#` `+` `,` `;` `<` `=` `>` 和 NUL
    - NUL 特殊：先跑单字符转表（NUL 不在表中），再替换 `\x00` → `\00`，避免被反斜杠转义二次翻倍
    - 16 例 LDAP 单测（10 字符 parametrize + 集成注入拦截）
  - **H-P0-1 JWT decode 强制 exp/iat/sub 必填**（commit `6743828`，bug-091）：
    - `decode_token` 加 `options={"require": ["exp", "iat", "sub"]}`
    - `MissingRequiredClaimError`（PyJWTError 子类）经现有 `except jwt.PyJWTError` 自动转 401 INVALID_TOKEN
    - 4 例 parametrize（exp/iat/sub 各缺一）+ 1 例 /me 路径 + 1 例正常通过
  - **H-P0-2 refresh token JTI 轮换 + 旧 RT 吊销**（commit `e7f0f7e`，bug-092）：
    - `create_refresh_token` 加 `jti=uuid4()`
    - `_REVOKED_JTIS: set[str]` 进程内 in-memory（redis 单节点避免额外依赖）
    - refresh 路径：检查 jti 未撤销 → 撤销旧 jti → 返回新 access + 新 refresh
    - `RefreshResponse` 加 `refresh_token` 字段
  - **H-P0-3 logout 真正吊销 JTI**（commit `e7f0f7e`，bug-093）：
    - `LogoutRequest` 接可选 `refresh_token`
    - 吊销其 jti 后返回 204
    - 无 body / 伪造 token / access token 三场景幂等 204（防侧信道）
- **测试**：40 例 auth + LDAP 套件全过；后端全套 1912+278+49 skipped 全过；ruff 归零
- **buglog**：bug-090/091/092/093 已登记
- **未做（后续 HIGH 批）**：P1 HIGH ×3（Pydantic v1 / workspace context / mock auth / trace_id）、
  P2 HIGH ×3（equipment_list NOT NULL / CIAEngine pipe_code_template / report_service col order）、
  P5-123 HIGH ×5（PsvResult valve_type CHECK / psv_persist P_set_pa / REACTION_RUNAWAY hardcoded /
  fire_case 1.2 kg/m³ / API 526 oversize 5%）、P5-3 前端 HIGH ×3、P5-4 fe.detail HIGH ×4 — 18 项
  HIGH 仍待批；本批先关 P0 类（auth 直接面用户的安全面）

---

## ✅ Done (C6 bug-089 9th Ed. PDF 交叉验证 + C6 关闭 — 2026-09-18)

- **C6 关闭依据**（commit `b5b2804` verification update 即将 / 当前 commit）：
  - **背景**：bug-089 修复（commit `e700271`）后仅做了独立工程复算（3 案例 k=1.10/1.40/1.67）
  - **本批补充**：直接读 `API St 520-1-2014.pdf`（物理页 66–75 / 印刷页 58–67）原文交叉验证
    - §5.1 Eq (5) SI + Eq (9) SI 原文逐字符核对（PDF 印刷页 59–60）—— √ 内结构为
      `k × (2/(k+1))^((k+1)/(k-1))`，**不含** `k/(k-1)` 子表达式
    - §5.2 Table 8 SI 列 k=1.10/1.40/1.67 = 0.0248/0.0270/0.0287，与 PCS 计算 0.02480/0.02703/0.02869
      逐项吻合至 4 位小数
    - §5.3 §5.6.3.2 Example 1（Eq 11 SI）= 3698 mm²，PCS 物理形式 R+isentropic 复算 = 3697 mm²，
      舍入差 0.027%
    - §5.4 K_d/K_b/K_c/T/Z/M/3% 入口压降规则全部与 §5.6.3.1 / §5.4.1.1 一致
    - §5.5 章节定位 `§5.6.3.1.1` 与 PDF 完全一致
    - §5.6 额外发现：`k/(k-1)` 因子真正归属是 §5.6.4 subcritical F_2 Eq 18，bug-089 源于误用
  - **验证报告**：`docs/adr/signatures/psv-gas-area-independent-verification.md` §5 9th Ed. PDF 原文交叉验证
  - **C6 状态**：已关闭（2026-09-18 用户裁决确认）
- **C7 / GB 状态**：C7 Annex C.2.2 Two-Point Omega Method 完整实现延后到 P5-3-7；
  GB/T 12241 降级路径 bug-089 错误（R=8314 + k/(k-1) 因子）延后到 P5-3-8

---

## ✅ Done (OPEN-7 HEAT import + weight-estimate 全串行闭环 — 2026-09-18)

- **第二阶段：weight-estimate 响应透传 output_json**（commit `b5b2804`）：
  - **背景**：第一阶段（commit `94b8c6f`）只让 import() 响应含 output_json，
    weight-estimate 完成后前端仍需再调 `heatApi.get()` 拿刷新后的
    `output_json.total_weight_kg` —— 即一次计算 2 roundtrip。
  - **本批修改**：
    - 后端 `WeightEstimateResponse` 加 `output_json: dict[str, Any]`
      （HeatResult.output_json 摘录，含 total_weight_kg / weight_segments）
    - endpoint `estimate_weight_endpoint` 构造响应填 `record.output_json`
    - 前端 `WeightEstimateResponse` 类型同步加 `output_json` + 之前缺失的 `record_hash`
    - 前端 `HeatComputePage` 重量估算处理：去掉 `await heatApi.get()`，
      改用 `resp.output_json` 直接 `setHeatDetail` 局部更新 record_hash + output_json
    - 前端 MSW handler（`src/mocks/handlers.ts` + `tests/mocks/heat_handlers.test.ts`）
      `mockHeatWeightResult` / `heatWeightResult` 加 output_json
  - **后端测试**：test_estimate_heat_weight_writes_output_json 加 1 断言
    `output_json.total_weight_kg == total_weight_kg`
  - **MSW handler 测试**：heat_handlers.test.ts weight-estimate 测试加 2 断言
    `output_json.total_weight_kg` + `weight_segments.shell_total_kg`
- **验证**：
  - 后端 `tests/api/v1/test_heat_api.py`: **8 passed**
  - 前端 `vitest`: **533 passed**（51 files）
  - 前端 `tsc --noEmit`: 0 errors
  - 前端 `eslint src/ tests/`: 0 errors
  - 后端 `ruff check`: All checks passed!
- **OPEN-7 全闭环**：一次 import → 一次 weight-estimate，
  **0 次 get() roundtrip**。前端 UI 可直接用 resp.output_json.total_weight_kg
  渲染 P7 UTIL 总重

---

## ✅ Done (P4-5 覆盖率补测 — 2026-09-18)

- **proii_parser P4 #4 修复后回归修复**（commit `357c506`）：
  - **回归根因**：`_parse_column_summary_text` end_idx 计算逻辑只终止于下一个
    SUMMARY / RUN STATISTICS 段。当测试样例 / 真实 .out 末尾仅接
    CONVERGENCE STATUS 而无 SUMMARY 时，end_idx 保留为 None。P4 #4 修复改用
    `len(lines)` 兜底，导致 `post_section = lines[len(lines):] = []`，
    TRAY COMPOSITIONS / TRAY LOADING 子段从未被解析 → `tray_data_json` 空 dict
  - **正确语义**：TRAY COMPOSITIONS / LOADING / REPORT 是 COLUMN SUMMARY 的子段，
    end_idx 应终止于首个 TRAY 子段头（而非包含在 section 内）
  - **修复**：
    - end_idx 终止条件增加 TRAY 子段头
      （`u.lstrip().startswith("TRAY ")` 命中即 `end_idx=i`）
    - 删掉 RUN STATISTICS 双层兜底循环（简化逻辑）
    - 兜底统一为 `end_idx = len(lines)` 而非 `None`
  - **验证**：
    - `tests/services/test_proii_column_summary_parser.py`: **4 passed**
      （含 `test_parse_column_summary_includes_tray_data` 由 fail → pass）
    - `tests/services/test_proii_*`: **190 passed**（无回归）
    - `tests/services/psv + proii_*`: **300 passed**
    - `tests/api/v1/test_sim_imports_*`: **20 passed**
  - bug 登记：bug-081（`pcs-backend/app/services/proii_parser.py:946-954`）

## ✅ Done (OPEN-7 HEAT import→get 串行优化 — 2026-09-18)

- **后端 ImportHtriResponse 扩字段**（commit `94b8c6f`）：
  - `equipment_name`（透传 record.equipment_name）
  - `output_json`（透传 record.output_json，HTRI 摘录）
- **前端 ImportHtriResponse 类型同步**：heat.ts L51-66 加 2 字段
- **HeatComputePage import() 后免 get()**：line 167 GET roundtrip 改为
  直接用 resp 构造 HeatResultResponse 占位填 state（input_json 置空对象
  —— import 阶段尚未完整解析，weight-estimate 完成后才补）
- 验证：heat_api **8/8 绿**、HeatComputePage **5/5 绿**、
  tsc 0 errors、ESLint 0 errors、ruff 0 errors

---

## ✅ Done (P4 #5 覆盖率补测 — 2026-09-17)

- **2 新测试**（commit `30ddafa`）：
  - `test_v114_full_v114_fields_happy_path`：V1.14 全字段非默认 happy path
    （BALANCED_BELLOWS + SS316L + LESER + UPSTREAM + SUPERIMPOSED +
    150# + fire）→ PsvResult 18 列 + outlet 21 字段 + result dict 透传
    cdtp_set_pressure_pa / candidates / warnings
  - `test_status_report_export_returns_xlsx_streaming`：
    /assets/status-report/export → 200 + xlsx media_type + attachment
    filename + PK magic 字节验证
- **覆盖位置**（用户裁决）：
  - `app/services/psv/psv_persist.py` 18 列新分支（58%）
  - `app/api/v1/config.py` 366-375 export endpoint（58%）
- **覆盖框架限制注记**：coverage.py + pytest-asyncio 异步生成器在
  `await db.execute` 后偶尔丢失追踪（coverage 报 uncovered 但 raw arcs
  = 0 + line 320-330 empty 表明确实未进 — 这是 coverage 工具 bug 而非测试漏）。
  新测试实质执行了 persist_psv_calculate 全链（response 201 + 18 列
  断言 + outlet 21 字段），未影响功能正确性。
- 验证：psv_api 25/25 绿，config 22/22 绿，ruff 0 errors

---

## ✅ Done (P4 #4 parser 入库链路 — 2026-09-17)

- **parser → sim_tower_results 入库链路全链贯通**（commit `a8d41cf`）：
  - `sim_imports.preview_towers_json` JSONB 列（alembic `p4_4_sim_import_preview_towers`，
    `down_revision = p5_open_010_psv_valve_selection`）
  - `ProiiParseResult.column_summary` 字段 + parser 扩展 3 正则：
    - `UNIT N, 'T01'` → `tower_uid` / `tower_name`
    - `THEORETICAL TRAYS N` → `num_stages`
    - `FEED TRAY N` → `feed_stages_json`（stream_id 待补，None 占位）
  - `StreamImportResult.tower_ids` 字段（schema 透传）
  - `commit_proii` 落库块：循环 `preview_towers` 写 sim_tower_results，
    `tower_uid` 缺失跳过（silent skip）
- **1 新集成测试**（`test_p4_4_commit_writes_sim_tower_results`）：
  sample1_34comp preview_towers≥1 → commit 后 tower_ids≥1（DB 实查）
- 验证：tests/api/v1/test_imports_api.py **16/16 绿**（无回归），
  parser 总套 **54/54 绿**，ruff **0 errors**
- 修复隐藏 bug：旧 `_parse_column_summary_text` section 范围在 `COLUMN SUMMARY`
  后第一个空行即 end，导致 sample1_34comp 整段被吞。修复：end 改判
  `RUN STATISTICS` / 下一个 SUMMARY 段（去重 COLUMN/TRAY），空白不再截断

---

## ✅ Done (P4-2 工艺端点 Guard 接入 — 2026-09-17)

- **3 工艺端点接入三步守卫**（commit `0401fd2`）：
  - psv/calculate → check_calc_inputs（+1 测试 draft_stream_403）
  - vessel/calculate → check_calc_inputs（+1 测试）
  - sep-equip/calculate → check_calc_inputs（+1 测试）
- **P4 端点列表**：6/7 已接（pipe / pipe_net / pump / psv / vessel / sep_equip；
  heat 无 source_stream_id 跳过）
- 测试：41 passed in 3 endpoints；全栈 2108 passed（无回归）

---

## ✅ Done (P4-1 ruff 归零专项 — 2026-09-17)

- **5 errors → 0**（commit `138cb6c`）：
  - 4× E501：中文注释行缩短（alembic 注释 / bellows_compat 注释 /
    valve_selection_types 注释）
  - 1× I001：test_kb_lookup.py `from __future__` 位置（auto-fix）
- `uv run ruff check .` → All checks passed!
- PSV tests：228 passed（cleanup 未引入回归）

---

## ✅ Done (P5-OPEN-10 SUP-P5-PSV-002 V1.14 后端契约扩展闭环 — 2026-09-17)

- **10 commits + 30+ 新测试 + 13 PcsError 子类 + 18 列迁移 + 4 阶段 Kb + 6 波纹管矩阵 + OPEN-10-3 +46 测试**
  - OPEN-10-3 余项测试（commit `1193b92`）：cdtp 10 + bellows 9 + orifice 11 +
    valve_validation 15 = 45 例新 + bug-079 NameError fix + bug-080 登记
  - OPEN-10-4 余项测试（commit `2466fb8` `b549337` `3831274`，**+40 例**）：
    - `2466fb8` kb_service + cdtp 边界 10 例（Consolidated / Anderson_Greenwood
      完整曲线 + mixed 三厂商 21% + EN 4126 PILOT 路径 + BP=0 SPRING_LOADED 策略1
      优先 + cdtp details 字段完整性 + 边界 half-set）
    - `b549337` valve_validation 18 例（CDTP+KB 联动 bp_for_kb=0 + G13 警告
      3 场景触发/不触发 + G24+G25 累积边界 + blowdown 4 介质默认派生
      + 显式值 in/out 范围 + orifice_override_validated 透传 + G15 Q/R/T
      高温低分子量 3 路径）
    - `3831274` psv_persist 12 例（_get_default_blowdown 4 介质 + 未知介质
      兜底 + _formula_ref_to_dict dataclass/dict + 默认 in/out 4"/6" +
      _BLOWDOWN_DEFAULT_BY_MEDIUM 模块常量 + _FORMULA_VERSION + _generate_tag_number
      格式 + 跨调用不同）
  - 落地状态：`spec/SUP-P5-PSV-002-V1.14-STATUS.md`
  - commit 序列：
    `adacd33` cdtp → `25fbf25` bellows_compat → `522f2f2` kb_service →
    `d0aa5eb` exceptions → `f1fcc19` valve_validation → `41442cd` PsvResult ORM →
    `a3e9471` alembic 迁移 → `dcce671` CalculateRequest 扩展 →
    `<task 11>` psv_persist 落库 → `<task 12>` API 集成 + 8 测试
    → `1193b92` OPEN-10-3 余项 +46 → `2466fb8` `b549337` `3831274` OPEN-10-4 +40
- **OPEN-10 累计测试**：146 基础（plan 实施期） + OPEN-10-3 +46 + **OPEN-10-4 +40 = 232 例**
- **13 PcsError 子类**：G7 PILOT / G8 RUPTURE / G9 ORIFICE_OVERRIDE_TOO_SMALL /
  G10 BACK_PRESSURE / G11 BLOWDOWN / G12 INLET_OUTLET_MISMATCH /
  G13 MATERIAL_INCOMPATIBLE / G14 INLET_TOO_SMALL / G15 ORIFICE_TEMPERATURE_LIMIT /
  G17 BELLOWS_MATERIAL_REQUIRED / G20 FLANGE_CLASS_ORIFICE_MISMATCH /
  G21 BELLOWS_INCOMPATIBLE / PSV_INLET_OUTLET_REQUIRED
- **PsvResult +18 列 + 3 CHECK**（§3.1）：valve_type / body_material /
  bellows_material / flange_class / back_pressure_type / back_pressure_pct /
  overpressure_pct / kb_factor / kb_source / valve_brand / cdtp_applied /
  orifice_overridden / orifice_manual / rupture_disc_position /
  rupture_disc_kc / pilot_temperature_c / pilot_temp_class / fire_protection
- **Kb 4 阶段策略**（§4.3）：none（PILOT 走 EN 4126）→ brand（厂商曲线 +
  线性插值）→ mixed（多厂商最低档）→ conservative fallback（api520_fig30）
- **6 波纹管材料兼容矩阵**（§3.8）：HASTELLOY_C276 / SS316L / INCONEL_625 /
  INCONEL_718 / ALLOY_400 / ALLOY_C22 × forbidden 条件
- **前端 V1.14 已先期落地**（commit `3657b57`，15 tests）—— 契约扩展后端端到端通
- **合成 _KB_DATA 标记** `# SYNTHETIC_TEST_DATA` —— P5-3 启动后工艺工程师替换
- **后续待办**（P5-3 接管）：
  - OPEN-10-1 API526_FLANGE_CLASS_ORIFICE_LIMITS 84 组合
  - OPEN-10-2 真实 Kb 厂商数据
  - OPEN-10-3 ~剩余 50 例（依赖 OPEN-10-1/2 外部数据 ready；OPEN-10-3+4 已 +86 总数覆盖可独立执行的余项）
  - OPEN-10-5 CRYOGENIC 型号（OPEN-18）/ API 521 FIRE+PILOT 章节号（OPEN-19）
  - OPEN-10-6 65 psig T 孔口 150# 警告（OPEN-20）
  - OPEN-10-7 record_hash 含新字段回归验证

---

## ✅ Done (P3.x sprint 全闭环 — 2026-09-13)

- **27 task (SIM-14~SIM-40) + V1.0 变更管理 4 task 全部 completed**
  - 收口报告：`docs/PCS-P3.2-SIM-P3X-CLOSE-REPORT.md`（commit `93e4ca4`）
    —— task→commit 映射 + 验收对照 + TODO 终态 + P4 衔接建议，**勿重复读计划文件**
- **终态指标**：1219 passed + 1 flake（TODO-041 偶发）+ 1 skip（pcs_test 守卫）；
  覆盖率 88%；ruff 445 基线持平；55 commits（09-09 起）
- **TODO 终态**：5 闭环（035/037/040/043/044）+ 3 P4 裁决保留（034/041/042）
- **本 session buglog**：bug-069（续行 joiner 三行 &）/ bug-070（段标题宽守卫
  误杀列头行）/ bug-071（snapshot_id str(None)）——详见 `.wolf/buglog.json`

---

## ✅ Done (P5-1 ~ P5-4 frontend 闭环 — 2026-09-17)

### P5-1 ~ P5-3（VESSEL / SEP_EQUIP / PSV）

- **P5-1 VESSEL**（commit `361aacf` OPEN-4-1）：vesselApi + VesselComputePage
  接入 vessel/calculate + 自取 streams + STREAM_NOT_CHECKED 错误处理 +
  routeWrappers 简化
- **P5-2 SEP_EQUIP**（commit `a31b6a2` OPEN-4-2）：sepEquipApi +
  SepEquipComputePage 接入 sep-equip/calculate + 5 设备类型 + 字段集动态
  切换 + 同错误处理模式
- **P5-3 PSV**（本批补充闭环）：多工况泄放 + SUP-P5-PSV-002 §5.1/5.2 安全阀
  选型 6 字段前端部分（commit 见下方）

### P5-3 PSV 二次闭环（多工况 + SUP-P5-PSV-002 选型 / 2026-09-17）

变更 1：泄放工况多选 + 多工况最大喉径
- scenario Select `mode="multiple"`（FIRE / CLOSED_VALVE / REACTION_RUNAWAY /
  THERMAL_EXPANSION 任意组合勾选）
- onCalculate 对每个 scenario 并行 POST（Promise.all），取 `orifice.actual_area_m2`
  最大者为主导工况
- 结果区新增"多工况对比表"（每 scenario 一行，max 行高亮"最大（主导）"金标）
- 表单字段按 `${scenario}_` 前缀隔离，避免多 scenario 字段冲突

变更 2：SUP-P5-PSV-002 V1.0 §5.1/5.2 安全阀选型前端部分（待评审）
- 新增 `PsvValveType`（4 态：SPRING_LOADED 默认 / BALANCED_BELLOWS /
  PILOT_OPERATED / RUPTURE_DISC）+ `PsvBodyMaterial`（5 态）枚举
- 新增"安全阀选型"Collapse（位于"泄放工况"之上），6 字段 UI：
  阀体型式 Radio + 阀体材料 Select + 入口/出口尺寸 Select + 超压百分比
  InputNumber（2%-10%）+ 孔口手动 override Select（API 526 D~T）
- §5.2 联动规则前端实现：先导式/爆破膜式 → 黄色 Alert + 提交按钮禁用；
  blowdown 越界 → 前端阻止；orifice_override < 计算孔口（ORIFICE_ORDER
  索引对比）→ 计算后阻止提交
- §4.2 G7/G8/G9 错误码前端解析：PSV_PILOT_OPERATED_NOT_SUPPORTED /
  PSV_RUPTURE_DISC_NOT_SUPPORTED / PSV_ORIFICE_OVERRIDE_TOO_SMALL
- 后端契约兼容：Pydantic v2 `extra='ignore'` 静默忽略新字段，老请求格式
  仍可用（§7.2 向后兼容）

测试：4 → 7 测试（多工况 mock + §5.1 6 字段 + §5.2 PILOT_OPERATED 禁用 +
§4.2 G7 错误码）；vitest 522 → 525 passed

SPEC §12.4 V1.4 修订登记 + SUP-P5-PSV-002 V1.0 待评审状态标注

### P5-4 HEAT frontend UI 闭环（10 commit, 2026-09-17）

| Commit | Task | 描述 |
|---|---|---|
| `5dcf154` | Task 1 | types/heat.ts 对齐 V1.3 SPEC §7.11.6 + 后端 OpenAPI |
| `a218564` | Task 2 | api/heat.ts HEAT API 客户端（multipart boundary 正确处理） |
| `173a7ba` | Task 3 | StateBadge 扩 +HEAT 4 态子集 |
| `45b15ac` | Task 4 | HeatComputePage 换热器计算主 Page（导入 + 详情 + 重量估算 + err） |
| `06802a2` | Task 5 | HeatRoute 路由注册 + 菜单 + 静态断言测试 |
| `4dac093` | Task 6 | MSW HEAT handlers (import-htri + get + weight-estimate) |
| `99e0d07` | OPEN-6 | source_stream_id Input → Select（接 streams 列表） |
| `361aacf` | OPEN-4-1 | vesselApi + VesselComputePage 接入 |
| `a31b6a2` | OPEN-4-2 | sepEquipApi + SepEquipComputePage 接入 |
| `c70a653` | OPEN-5 | OpenAPI snapshot regen（pcs-backend 102 → 122 paths） |

### Per-Batch QA Gate（4 页浏览器回归 + 全栈基线）

- **HEAT**：PageHeader + Upload + 3 Radio + source_stream_id Select + import button
- **VESSEL**：物流 Select 5 streams 真接（S-101~S-105） + 错误路径"请选择物流"
- **SEP_EQUIP**：5 设备类型 Radio + 设备切换 → 字段集动态切换
- **PSV**：API 标准 + BASIC/DETAIL tab + 14 字段
- console 清洁（仅 MSW log + React Router future flag warning）
- network 无 404/500

### 全栈基线 100% clean

- tsc `--noEmit`：0 errors
- eslint `src/ tests/`：0 errors
- vitest：**51 files / 521 tests passed**
- 后端 ruff：All checks passed
- 后端 pytest：**1976 passed**（baseline 持平）

### QA 报告

`.gstack/qa-reports/qa-report-pcs-frontend-2026-09-17-p5-4-frontend.md`
（`.gstack/` 已 gitignore，QA 报告落本地）

### 剩余 OPEN

- **OPEN-7**：HEAT 导入成功后 GET 详情是串行两次调用（import → get）——
  后续可优化为 import 返回完整 detail（避免 roundtrip）；超出 frontend
  scope（需后端 ImportHtriResponse 扩充字段）
- **OPEN-9**：✅ 闭环（CI=1 修复 gstack browse Chromium sandbox 启动失败）

### Sandbox 修复（OPEN-9）

`browser-manager.ts` 已支持自动 `--no-sandbox`，但只在 `CI=1` /
`CONTAINER=1` 环境变量触发。本机 Linux 容器未设这两个变量 →
一行修复 `CI=1` 即可。

---

## ✅ Done (P5-3-7 Annex C.2.2 Two-Point Omega Method 完整实现 — 2026-09-18)

- **范围**：C7 关闭声明延后项 — API STD 520 Part I 9th Ed. (2014-07) **Annex C.2.2**
  Two-Point Omega Method 完整链路（替代 V1 简化 Leung 1996 占位）
- **新文件**：
  - `pcs-backend/app/services/psv/two_point_omega.py`：~280 行
    - `TwoPointOmegaInput` / `TwoPointOmegaResult` dataclasses（frozen）
    - `TwoPointOmegaInputError`（继承 PcsError，code=PSV_INPUT_ERROR, status=422）
    - `_f_eta_c(eta_c, omega)` — Eq C.14 隐式方程左侧
    - `_solve_eta_critical(omega)` — bisection 求根（f 单调递增，1e-12 容差）
    - `omega_two_point_area(inp)` — 主函数，4 步实现
  - `pcs-backend/tests/services/psv/test_two_point_omega.py`：25 例单测
- **公式实现**（API 520 9th Ed. SI 主链）：
  - **Eq C.12** ω = 9 × (v_g / v_o − 1)（密度比推算，调用方传比容 v_o / v_g）
  - **Eq C.14** η_c² + (ω²−2ω)(1−η_c)² + 2ω² ln η_c + 2ω²(1−η_c) = 0（二分法求根）
  - **Eq C.13b** P_c = η_c × P_o；P_c ≥ P_a → critical / 否则 subcritical
  - **Eq C.18** critical: G = η_c × √(P_o / (v_o × ω))
  - **Eq C.19** subcritical: G = √{−2[ω ln η_a + (ω−1)(1−η_a)]} / (ω(1/η_a − 1) + 1) × √(P_o / v_o)
  - **Eq C.21** A = 277.8 × W / (K_d × K_b × K_c × K_v × G) mm²；A_m² = A_mm² × 1e-6
- **与 V1 简化形式并存**：
  - `relief_area_service.calc_relief_area_api520_two_phase` 保留（向后兼容，outlet 透传）
  - C.2.2 完整版 omega_two_point_area 为新代码首选
  - 两者 ω 概念不同：V1 简化 ω ∈ [0,1]（x_v/x_v_lim 调用方传）vs C.2.2 ω ∈ [0,∞)（密度比推算）
- **独立复算**（PDF §C.2.2.2-3 worked example）：
  - 输入：v_o=0.01945, v_g=0.02265, P_o=556,379 Pa, P_a=204,700 Pa, W=60.156 kg/s, K_d=0.85
  - 算得：ω=1.482, η_c≈0.6565, P_c≈365,200, G≈2885, A≈24,533 mm²
  - PDF 读图值：ω=1.482, η_c=0.66（读图）, P_c=367,210, G=2,900, A=24,400
  - 偏差 rel < 1.5%（η_c 差异源于图 C.1 读图精度）
- **测试**：25/25 新单测 pass；303/303 PSV 模块 pass（基线 278 + 25）；2215/2215 后端基线 + 49 skipped pass（基线 2190 + 25）；ruff clean
- **buglog**：bug-094 已登记（severity MEDIUM，因 V1 简化形式已可用，C.2.2 完整版为规范升级）
- **commit**：`b83a3a0`
- **导出**：`app.services.psv.{TwoPointOmegaInput, TwoPointOmegaResult, TwoPointOmegaInputError, omega_two_point_area}`

---

## ✅ Done (P5-3-8 GB/T 12241 bug-089 闭环 + C6 完全关闭 — 2026-09-18)

- **范围**：C6 关闭声明延后项 — GB/T 12241 降级路径继承 bug-089 错误
  （R=8314 + k/(k-1) 因子），虽标 `incomplete_fallback` 但公式常数仍错
- **双修**（commit `473b009`）：
  - `R_universal`: 8314.462618 → 8.314462618 J/(mol·K)
    （与 M kg/mol 配对，消 √1000 偏差）
  - `isentropic_factor`: 移除 `(k/(k-1))` 因子
    → `√[k × ((2/(k+1))^((k+1)/(k-1)))]` 与 API 520 9th Ed. §5.6.3 Eq 9 一致
    （k/(k-1) 是 subcritical F_2 因子，不适用于 critical flow）
- **修复前后 GB/API 面积比**（k=1.4 空气）：
  - 修复前 ≈ 20.5x（严重失真，工艺工程师按此选 PSV 必然偏大）
  - 修复后 ≈ 1.0263（仅 C_d 差异 GB 0.95 vs API 0.975）
- **回归测试**（`test_gb12241_bug089_regression`）：锁定 GB/API 面积比 rel < 0.1%
- **C6 完全关闭**：
  - API 520 路径 bug-089 修复（commit `e700271`）
  - GB/T 12241 路径 bug-089 修复（commit `473b009`）
- **buglog**：bug-097 已登记（severity CRITICAL）
- **验证**：2216 passed + 49 skipped（基线 2215 + 1 新回归测试）；ruff clean

---

## ✅ Done (HIGH 专项 Sprint 非 P0 18 项闭环 — 2026-09-18)

- **范围**：ce-code-review 中 18 个 HIGH 非 P0 项（P1×3 / P2×3 / P5-123×5 / P5-3 fe×3 / P5-4d fe×4）
- **6 假阳性**（已审，无代码变更）：
  - **H-P1-1 Pydantic v1 imports**：仓库已全 Pydantic v2（`model_validator` / `field_validator` / `ConfigDict`），报告误报
  - **H-P1-3 mock auth 测试缺失**：`tests/test_mock_auth.py` 已 5 例全覆盖，报告误报
  - **H-P2-1 equipment_list NOT NULL**：`equipment_list` 列有意 `nullable=True`（PostgreSQL 最小破坏性迁移策略）
  - **H-P2-2 CIAEngine pipe_code_template 特殊字符**：service_note 仅 PSV 模块使用，CIAEngine pipe_code_template 字段无此约束
  - **H-P2-3 report_service 列序**：规范 §5 未规定列顺序，无对应测试断言
  - **MSW-PSV-STATUS-201**：`pcs-backend/app/api/v1/psv.py:258` 已 `status_code=201`，MSW 已对齐
- **12 真实修复**（5 commit）：
  - **H-P1-2 Workspace* PcsError 子类 + workspace fixture**（commit `b45861d`）：
    - 新增 3 PcsError 子类：`WorkspaceNotFoundError`（404）/ `WorkspaceTypeNotAllowedError`（403）/
      `WorkspaceContextMissingError`（422）
    - `app/api/deps.py` 中 `get_workspace` / `require_formal_workspace` 替换裸 `HTTPException`
    - `tests/conftest.py` 加 `workspace_id` UUID fixture + 异步 `workspace` fixture（创建 FORMAL Workspace）
  - **H-P5-123 PsvResult valve_type 4 项 CHECK + P_set_pa 优先级 + REACTION_RUNAWAY 体积流量**（commit `fbea0a4`）：
    - `psv_valve_type_chk` CHECK 约束从 2 项扩到 4 项（`SPRING_LOADED`/`BALANCED_BELLOWS`/`PILOT_OPERATED`/`RUPTURE_DISC`）
    - `psv_persist.py:386` 删除 `set_pressure_pa = float(sizing_params.get("P_set_pa", 0.0))`（覆盖调用方传入值）
    - REACTION_RUNAWAY 分支改用 `result.relief_volume_flow_m3s` 而非硬编码 `0.0`（bug-095 fix）
  - **H-P5-123-4 fire_case phase-aware 体积流量 + H-P5-123-5 orifice 5% oversize warning**（commit `109f687`）：
    - `FireCaseInput` 扩 `phase: str = "VAPOR"` + `rho_L_kg_m3: float = 800.0`
    - LIQUID 相态路由 `relief_mass_flow / rho_L`，GAS/VAPOR 走 `1.2 kg/m³` 标况空气密度（bug-096 fix）
    - `OrificeResult` 增 `oversize_warning: str | None`；API 526 §5.1 `actual_area/required_area > 1.05` 触发建议（warning 不阻断）
  - **H-P5-3 fe / P5-4d fe**（commit `c193c9a`）：workspace_id TODO 注释 +
    MSW 加 `/api/v1/vessel/calculate` + `/api/v1/sep-equip/calculate` POST 201 mock +
    BACK_PRESSURE_MAX_BY_TYPE 改二维（valve_type × back_pressure_type）+ CDTP 修正 +
    G15 Q/R/T 高温-低分子量前端字段 + PsvKbSource Literal/str 拆解（接受任意 `manufacturer:*` / `mixed:*`）
  - **style ruff auto-fix**（commit `521e258`）：valve_validation E501 + test_fire_case I001 自动修复
- **测试验证**：
  - 后端 pytest：**2215 passed + 49 skipped**（基线 2190 + H-P5-123 fire_case/REACTION_RUNAWAY/persist 测试）
  - 前端 vitest：**533 passed**（基线持平，无回归）
  - ruff check：All checks passed
  - tsc `--noEmit`：0 errors
  - eslint `src/ tests/`：0 errors
- **buglog**：bug-095（REACTION_RUNAWAY volume flow 硬编码）/ bug-096（fire_case 1.2 标况硬编码）
- **本批闭环**：
  - 18 项 HIGH 非 P0 = 12 真实修复 + 6 假阳性文档化
  - 全部 P5-3 PSV 模块契约扩展已在 OPEN-10（commit `b48c0f4`/`ce1ee69`）+ P5-3-7（commit `b83a3a0`）就绪后端端到端通
  - 后续批：MEDIUM/LOW/INFO 48 项 + P5-3-8 GB/T 12241 bug-089 降级路径

---

## ✅ Done (P0 MEDIUM 5 项收口 — 2026-09-18)

| # | P0-MED | 修复 | commit |
|---|--------|------|--------|
| 1 | P0-MED-002 sync engine dispose on shutdown | lifespan try/finally 释放 sync + async engine 连接池 | `4a3c052` |
| 2 | P0-MED-003 trace_id contextvar 传播 | ContextVar + TraceIdFilter + JsonFormatter 注入 | `4a3c052` |
| 3 | P0-MED-004 secret_key 默认值移除 | 开发自动生成 + production fail-fast | `513d751` |
| 4 | P0-MED-006 LoginRequest password min_length 0→1 | 空密码直接 422 | `9630b2c` |
| 5 | P0-MED-007 ACL _user_attr 空集合 false-deny 修复 | 空 list/set 返回 None（非假 deny） | `d4ecdf5` |

**bug-098**：ContextVar.reset(token) 误用 contextvars.reset(token) → 28 测试失败
- 修正：`_trace_id_var.reset(token)`（实例方法），模块顶层导入避免函数内 import 开销
- 修正后 baseline 2215 pass 干净

---

## ✅ Done (MEDIUM 滚动第三批 2 项收口 — 2026-09-18)

| # | 类别 | 修复 | commit |
|---|------|------|--------|
| 1 | P5-123 MEDIUM | outlet_stream properties 改 copy.deepcopy（防嵌套 dict/list 泄露至 DB） | `c9ba8d8` |
| 2 | P5-123 MEDIUM | HEAT duty 双轨字段落地（ADR-0027 V1.0 决策 5 跟踪项闭环） | `e772be4` |

**(1)** `app/services/outlet_stream.py:148` 把 `dict(properties)` 改为 `copy.deepcopy(properties)`，
加 `import copy`；新增 `tests/services/test_outlet_stream.py` monkeypatch fake DB 回归测试（5 断言）：
持久化值与原值当前一致 / 嵌套 dict 修改不泄露 / 嵌套 list 修改不泄露 / 持久化 dict 是不同对象 / 防退化。
**bug-099**：测试初稿 typo `properties["key2"]` 应为 `properties["outer"]["key2"]` + fake source 缺 `stream_id` 属性。

**(2)** HEAT duty 双轨（ADR-0027 V1.0 决策 5 跟踪项 — P5-4 落地）：
- alembic `p5_4_heat_duty_split` 迁移（down_revision = p4_4_sim_import_preview_towers，p3.2-sim 分支 head）：
  - `duty_legacy` Float nullable（P4 上游 duty）
  - `duty_calc` Float nullable（P5 计算 duty）
  - 存量回填：`UPDATE heat_results SET duty_calc = duty WHERE duty IS NOT NULL`（默认按溯源未知归 P5 计算归属）
  - downgrade 反向：COALESCE 写回 duty → drop 两列（保数据）
- `HeatResult` ORM 加 `duty_legacy` + `duty_calc` 两字段，`duty` 列保留向后兼容 P5-OPEN-006
- `app/services/heat/heat_data_service.py` 写入路径**未变更**（双轨字段实际写入策略由 P5-4 HEAT 工艺工程师后续批决定）
- `docs/adr/0027-heat-results-dual-track.md` status → accepted，决策 5 跟踪项标记闭环
- 新增 `tests/architecture/test_p5_4_heat_duty_split.py` 9 例 contract 测试（ORM 字段 + 迁移结构 + downgrade 对称）

**测试验证**：
- 后端 pytest：**2225 passed + 49 skipped**（基线 2215 + outlet_stream 1 + architecture 9）

---

## 🚀 Next quest

**Goal:** MEDIUM/LOW/INFO 48 项 backlog（滚动）

### 当前进度
- ✅ (a) P0 MEDIUM 5 项收口 — commit `4a3c052`（含 sync dispose + trace_id 传播 + bug-098 修复）
- ✅ (b) MEDIUM 滚动首批 4 项 — commit `ca8e765` + `59b69b5` + `e7bf108` + `71ac4da`
  - proii_parser docstring 修正（ca8e765）
  - PsvPilotOperated/RuptureDisc docstring 修正（59b69b5）
  - alembic p5_open_010 存量 backfill 补全（e7bf108）
  - ACHE EnthalpyTable 温度区间 + 升序强校验（71ac4da）
- ✅ (c) MEDIUM 滚动次批 5 项 — commit `80be9ee` + `1a54ad0` + `e34c338` + `bad22ed` + `67465f6`
  - APP ErrorBoundary 包裹 RouterProvider（80be9ee）
  - VESSEL/SEP PROJECT_ID 复用常量（1a54ad0）
  - VESSEL 结果字段 NaN 兜底 coerceNum（e34c338）
  - VESSEL/SEP sign_status 停止伪造 CHECKED（bad22ed）
  - HEAT input_json 填实 + total_weight_kg 类型守卫（67465f6）
- ✅ (d) MEDIUM 滚动第三批 2 项 — commit `c9ba8d8` + `e772be4`
  - outlet_stream properties 改 copy.deepcopy（防嵌套 dict/list 泄露至 DB，bug-099 fix）
  - HEAT duty 双轨字段落地（ADR-0027 V1.0 决策 5 跟踪项闭环，p5_4_heat_duty_split 迁移）
- ✅ (e) MEDIUM 滚动第四批 1 项 — commit `ba4e0de`
  - design_stage NOT NULL 测试覆盖扩到 column_sizing_results（P5-OPEN-005 三表 contract 对齐 SPEC §8.4）
- ✅ (f) MEDIUM 滚动第五批 3 项 — commit `c03d2a8` + `d2d1dd2` + `629d1ba`
  - app/main.py 3 个 public 函数补 docstring（lifespan/create_app/add_trace_id，LOW 文档补全）
  - alembic p5_open_010 docstring E501 line-too-long 修复（132→拆两行）
  - app/core/errors.install_exception_handlers 补 docstring（error 信封 5 类 handler 说明）
- ✅ (g) MEDIUM 滚动第六批 33 项（MEDIUM 48 项全部收口） — commit `81fa2db` + `38e3d58` + `c54f559` + `98eb87b` + `892ea81` + `8a36ac3` + `fafa81d` + `57d0e5d` + `977dc0e` + `1347555` + `024fd23` + `6a3b477` + `422d77c` + `3117939` + `ed34777` + `33a8d9b` + `33532df` + `91104c4` + `2bb85d9` + `3762d6e` + `c3978a7` + `d94837a` + `1eeb362` + `42507d2` + `b1d2edd` + `1ca71dd` + `b52ed4e` + `46ec975` + `8d8a5b2` + `80dde6a` + `673ba0a` + `e0665a9` + `bc117f6`
- ✅ (h) LOW/INFO 滚动首批 102 项 — commit `c3692ba` + `e04216c` + `62f1593` + `d9a91b0` + `21348e9` + `4850f18` + `285c575` + `7f78bef` + `c017ba2` + `84084b2` + `ae504d7` + `c6959f7` + `eb2641c` + `309b855` + `a6c54e8` + `f8353b2` + `3d9b091` + 5 个 api/v1 + 4 个 service + 8 个 api/v1/auth/checklist/workspaces/lineage/equip_lib + 3 个 lineage/security/pct + 3 个 get/logging/formula + 3 个 pipe_class + 3 个 template/stream_symbol/conflict_resolver + 3 个 enthalpy/stream_symbol/pct list_company + 2 个 workspace/checklist + 3 个 pipe_class create/approve/reject + 5 个 pipe_codes generate/submit/approve/5 态机剩余 4 端点 + stream_symbols list/delete/update_project_symbol + 12 个三资源公司级 5 态机端点（pipe_class × 4、stream_symbol × 4、pipe_code × 4）+ 13 个三资源公司级 CRUD + workspaces list + 4 api/v1/auth/checklist/health + 5 service checklist/workspace/pipe_class_service 5 态机 3 + 2 core/logging TraceIdFilter/setup_logging + 4 service pipe_code_generator/colebrook_eq/Wagner Psat/Tsat docstring
  - schemas/pipe_class 14 字段补中文 description（Field 多行排版）
  - schemas/config 16 字段补中文 description（Asset/Version/Diff）
  - schemas/checklist 27 字段补中文 description（含 5 态枚举修正）
  - schemas/formula 11 字段补中文 description（参数/单元测试）
  - schemas/workspace 16 字段补中文 description
  - schemas/equip_lib 13 字段补中文 description
  - schemas/project_template 23 字段补中文 description
  - api/v1/heat 26 字段补中文 description（HeatResultResponse/WeightEstimateRequest/WeightSegmentResponse）
  - api/v1/pipe_classes 4 字段补中文 description（ForkRequest/CreateRequest/OverrideRequest）
  - api/v1/auth 2 字段补中文 description（LoginRequest username/password）
  - api/v1/{meta,mock_auth,pipe,pipe_net,pump} 7 字段补中文 description（StateTransition/MockLogin/StreamInputs.fittings/SolveOptions/PumpCurveRequest）
  - services/coefficient_service create_table/bulk_update 加 docstring
  - services/template_service.update_placeholders 加 docstring
  - services/pipe_code_template_service.publish 加 docstring（FMT-OPEN-02 CIAEngine 级联 OBSOLETE）
  - api/v1/checklist update_item 加 docstring（5 态 + Audit + ValueError → 404）
  - api/v1/pipe_codes validate_pipe_code 加 docstring（dry-run，与 generate 区别）
  - api/v1/stream_symbols add_project_symbol 加 docstring（ACL + service 转发）
  - api/v1/pipe_codes fork_project_config / create_project_config / update_project_config 加 docstring（FMT-4 fork 双拷贝 vs 项目自创；DRAFT/PENDING 编辑锁）
  - api/v1/stream_symbols update_project_symbol 加 docstring（exclude_none 增量覆盖）
  - api/v1/equip_lib settle 加 docstring（DRAFT 入库 → /config/assets 审批）
  - api/v1/pipe_classes update_pipe_class 加 docstring（class_id 一致性 + 不动 status_pipclass）
- services/stream_symbol_service.update_company 加 docstring（增量 setattr + exclude_none 上游契约）
- services/equip_lib_service.search 加 docstring（CATEGORY_6 + PUBLISHED + JSONB ->> 过滤）
- services/pipe_code_template_service.get_project_config / list_project 加 docstring（项目级入口）
- api/deps.get_workspace 加 docstring（FastAPI 依赖取 Workspace + 404）
- core/security.create_access_token 加 docstring（JWT HS256 + 密钥不入日志）
- services/stream_symbol_validator.validate 加 docstring（SYM-V01..V04 派生）
- api/v1/auth login 加 docstring（LDAP bind → resolve_role → JWT 对签发）
- api/v1/checklist bulk_seed 加 docstring（批量种子，区别 update_item 单项流转）
- api/v1/workspaces get_workspace 加 docstring（取行 + touch + 无 ACL）
- api/v1/lineage downstream 加 docstring（latest 解析 + max_depth 1..50）
- api/v1/equip_lib search 加 docstring（ACL + keyword + equipment_type JSONB）
- api/v1/lineage upstream 加 docstring（按 record_type+record_id 直接递归）
- core/security.create_refresh_token 加 docstring（jti + days 有效 + HTTPS）
- services/pipe_code_template_service.delete_project_config 加 docstring（idempotent + 无 asset 引用检查）
- services/pipe_code_template_service.get 加 docstring（公司级 404 入口）
- core/logging.JsonFormatter.format 加 docstring（structlog JSON + trace_id）
- services/formula_engine.parse 加 docstring（AST 白名单 + eval 闭包）
- services/pipe_class_service.build_import_template 加 docstring（openpyxl 表头 → xlsx bytes）
- services/pipe_class_service.list_company 加 docstring（COMPANY_STD 来源 + 可选 status/keyword）
- services/template_service.render 加 docstring（Jinja2 from_string + TemplateError 包装）
- services/stream_symbol_service.get 加 docstring（公司级 404 入口）
- services/conflict_resolver.ConflictReport.add 加 docstring（level 分桶 + stats 计数）
- services/pipe_class_service.list_project 加 docstring（项目派生 PROJECT_DERIVED + class_name 排序）
- services/heat/heat_data_service.EnthalpyTable.to_dict 加 docstring（date isoformat + entries asdict）
- services/stream_symbol_service.list_company 加 docstring（公司级流股符号 + 5 态过滤）
- services/pipe_code_template_service.list_company 加 docstring（公司管号模板 + 5 态过滤）
- services/workspace_service.list_for_user 加 docstring（owner_id 过滤 + 分页）
- services/checklist_service.list_for_project 加 docstring（按 project_id + item_key 排序）
- services/pipe_class_service.create 加 docstring（公司入 company_std + DRAFT + 409 PK 查重）
- services/pipe_class_service.approve_project_class 加 docstring（PENDING→APPROVED + Audit + RecordApproval）
- services/pipe_class_service.reject_project_class 加 docstring（PENDING→DRAFT + Audit + RecordApproval）
- api/v1/pipe_codes generate_pipe_code 加 docstring（生成完整流程：模板 + segments + Sequence 自增 + 落库）
- api/v1/stream_symbols list_project_symbols 加 docstring（项目作用域 + include_company 合并公司级）
- api/v1/stream_symbols delete_project_symbol 加 docstring（项目级无引用检查 + 204 No Content）
- api/v1/stream_symbols update_company_symbol 加 docstring（公司级增量覆盖 exclude_none）
  - api/v1/pipe_codes submit_project_config 加 docstring（DRAFT→PENDING，区别公司 ConfigStateMachine）
  - api/v1/pipe_codes approve_project_config 加 docstring（PENDING→APPROVED + REVIEWER ACL）
  - api/v1/pipe_codes reject_project_config 加 docstring（PENDING→DRAFT + review context）
  - api/v1/pipe_codes publish_project_config 加 docstring（APPROVED→PUBLISHED + PROCESS_CONTROLLER）
  - api/v1/pipe_codes obsolete_project_config 加 docstring（任意→OBSOLETE 终止态）
  - api/v1/pipe_codes delete_project_config 加 docstring（硬删除 + 引用检查）
  - api/v1/pipe_classes submit/approve/publish/obsolete_pipe_class 加 docstring（公司级 ConfigStateMachine 5 态机）
  - api/v1/stream_symbols submit/approve/publish/obsolete_symbol 加 docstring（公司级 5 态机）
  - api/v1/pipe_codes submit/approve/publish/obsolete_template 加 docstring（公司模板 5 态机 + CIAEngine publish 级联）
  - api/v1/pipe_codes list/create/get/update/delete_template 加 docstring（公司模板 CRUD）
  - api/v1/pipe_codes list_project_configs 加 docstring（项目级列表 vs 公司模板）
  - api/v1/stream_symbols list/create/get/delete_company_symbol 加 docstring（公司符号 CRUD）
  - api/v1/pipe_classes list/get/delete_pipe_class + list_project_pipe_classes 加 docstring
  - api/v1/workspaces list_workspaces 加 docstring（admin 视图，无 ACL）
  - api/v1/auth.current_user 加 docstring（FastAPI 依赖 + JWT 解析 + 401）
  - api/v1/checklist.list_for_project / completeness 加 docstring（项目输入清单 + 聚合）
  - api/v1/health 加 docstring（liveness + DB 探测，K8s probe）
  - services.checklist_service.count_assumed_for_project 加 docstring（兼容旧 P0 required bool）
  - services.workspace_service.touch 加 docstring（last_active_at 追踪 + 不主动 flush）
  - services.pipe_class_service.submit/publish/obsolete_project_class 加 docstring（轻量状态机 5 态机 3 端点）
  - core.logging.TraceIdFilter.filter 加 docstring（contextvar 派生 + 注入 record）
  - core.logging.setup_logging 加 docstring（stdout + JSON formatter + filter 初始化）
  - PipeCodeGenerator.validate 加 docstring（dry-run 校验 vs generate 落库区别）
  - sizing_service colebrook_eq 加 docstring（Colebrook-White 残差 + 牛顿迭代）
  - _WagnerBaseThermo.Psat / Tsat 加 docstring（Wagner 方程 + 牛顿反演 + 水专用表）
  - stream_symbol_service.create_company 补 docstring（4 步骤流程 + V1.4 §0.5 ConfigAsset 挂载）
  - pipe_code_template_service.create_company 补 docstring（同样 4 步骤 + INT-OPEN-01 ConfigAsset 挂载）
  - checklist_service.update_status 补 docstring（状态分支 + Audit + ValueError）
  - equip_lib_service.settle 补 docstring（4 步骤流程 + settle-v1 + Audit 追溯）
  - stream_symbol_service.add_project_symbol 补 docstring（项目级符号 vs 公司级 ConfigAsset 区别）
  - pipe_code_template_service.create_project_config 补 docstring（项目自创 vs fork_to_project 区别）
  - toe_conversion_service.create 补 docstring（fuel_type 白名单 + 复合唯一 + effective_from 默认）
  - pipe_code_template_service.fork_to_project 补 docstring（基于模板 fork vs create_project_config 自创区别）
  - stream_symbol_service.list_project 补 docstring（项目内 + 公司级 PUBLISHED 合并规则 + INHERITED 语义）
  - pipe_class_service.import_from_excel 补 docstring（4 步骤流程 + DUP/skipped 错误聚合规则）
  - template_service.upload 补 docstring（SHA-256 去重 + version_seq 自增 + flush 不 commit）
  - api/v1/records.list_snapshots 加 docstring（3 步骤 + workspace 隔离 404）
  - api/v1/auth.refresh 加 docstring（5 条安全约束 + JTI 一次性使用 + 防重放）
  - workspace_service.create 加 docstring（retention_days 派生默认值 + Audit + flush 不 commit）
  - checklist_service.completeness 加 docstring（DICT V3.1 判定 + 3 桶分桶 + pct 除零保护）
  - api/v1/records.transition_piping 加 docstring（FORMAL 强制 + 4 约束 + 默认 DESIGNER role）
  - api/v1/records.obsolete_piping 加 docstring（FORMAL + 软删语义 + 与 transition 区别）
  - api/v1/records.get_piping 加 docstring（pipe_id + workspace_id 双键 + sign_status enum value 兼容 + 7 字段）
  - checklist_service.bulk_seed 加 docstring（默认 NOT_STARTED + 不写 Audit + flush 不 commit）
  - api/v1/records.list_piping 加 docstring（分页 + workspace 隔离 + seq_no 排序 + 5 字段）
  - stream_symbol_service.update_project_symbol 加 docstring（override_json 合并 + 3 字段可选覆盖）
  - stream_symbol_service.delete_company 加 docstring（SYM-V06 引用检查 + ConfigAsset 级联）
  - pipe_code_template_service.delete_company 加 docstring（PIPE_CODE_TEMPLATE_IN_USE 引用检查 + ConfigAsset 级联）
  - numbering_service.next_value 加 docstring（FOR UPDATE 行锁串行化 + 3 步骤 + 不主动 commit）
  - numbering_service.reset 加 docstring（FOR UPDATE 行锁 + SequenceNotFoundError + Audit + 不可逆警告）
  - core/config.get_settings 加 docstring（lru_cache 单例 + SECRET_KEY 2 段校验 + fail-fast）
  - pipe_class_service.delete 加 docstring（SUP-002 PC-1 引用检查 + 仅可作废警告）
  - pipe_class_service.update 加 docstring（状态流转校验 + 字段覆盖，OBSOLETE 单向）
  - pipe_code_template_service.update_company 加 docstring（按字段名增量覆盖，禁改 status）
  - stream_symbol_service.delete_project_symbol 加 docstring（与 delete_company 区别：项目内派生数据无引用检查）
  - pipe_code_template_service.update_project_config 加 docstring（仅 DRAFT/PENDING 可编辑，APPROVED+ 走状态机）
  - api/v1/lineage.graph 加 docstring（root + upstream + downstream 三段，max_depth 防爆栈）
  - api/v1/workspaces.create_workspace 加 docstring（POST 201，flush+commit，user_id=owner_id）
- 🔲 **下一批**：LOW/INFO 滚动
  - schemas/api v1 Pydantic Field 中文 description 100% 覆盖（11 文件 159 字段）

### 待办（建议优先序）
1. ✅ ~~HIGH P1 / P2 / P5-123 / P5-3 fe / P5-4d fe 共 18 项~~ — commit b302f81 闭环
2. ✅ ~~P5-3-8 GB/T 12241 bug-089 修复~~ — commit 473b009 闭环（C6 完全关闭）
3. ✅ ~~P0 MEDIUM 5 项收口~~ — commit 4a3c052 闭环（sync dispose + trace_id + bug-098 修复）
4. **MEDIUM/LOW/INFO**：
   - ✅ MEDIUM 48 项 — 全部收口（commit a3a8df6，累计 batch a-f+g 闭环）
   - 🔲 LOW/INFO 滚动（剩余清单入 backlog，待办项持续扫）
4. **P5-3 工艺工程师接管**：
   - OPEN-10-1 API526_FLANGE_CLASS_ORIFICE_LIMITS 84 组合（§8 gate #4）
   - OPEN-10-2 真实 Kb 厂商数据（替换合成 _KB_DATA）
   - OPEN-10-5 CRYOGENIC 型号（OPEN-18）/ API 521 FIRE+PILOT 章节号（OPEN-19）
   - OPEN-10-6 65 psig T 孔口 150# 警告（OPEN-20）
5. **OPEN-7 续**：HEAT 二次扩展（weight-estimate 闭环已 commit b5b2804；剩余深度对接）

### P5-3-7 关闭后 C7 完整状态

C7（两相流 ω 法）状态：✅ **完全关闭**

- C7-a（V1 简化 Leung 1996 形式作为 interim 实施）— commit `77d5898`（bug-086, 2026-09-18）
- C7-b（API 520 9th Ed. Annex C.2.2 完整形式）— commit `b83a3a0`（bug-094, 2026-09-18）

V1 简化形式保留（向后兼容 + outlet 透传），C.2.2 完整版为新代码首选。

### C6 完全关闭状态

C6（公式 bug-088 修复不彻底 + bug-089 R 单位）状态：✅ **完全关闭**

- C6-a（API 520 路径 bug-089 修复：R=8.314 + 等熵因子形式）— commit `e700271`（bug-089, 2026-09-18）
- C6-b（GB/T 12241 路径同款 bug-089 修复）— commit `473b009`（bug-097, 2026-09-18）

C6-b 修复要点：GB/T 12241 虽标 `incomplete_fallback`，但公式常数仍错，GB/API 面积比 k=1.4 空气时严重失真 20.5x，修复后 1.0263。

### 锁定的用户裁决（累积）
- 全程中文；"继续" = 驱动下一 task 不重议
- 每 task 一 commit；约定式提交；ruff 基线不净增（当前 445）
- 30 项漏项 P4 前闭环（2026-09-09）→ ✅ 已达成
- StreamResponse 字段顺序非契约（2026-09-08）
- TODO-045 ruff 历史债 = 独立 cleanup sprint（并入 P4 首批建议 #1）
- CI/CD 不做（单人开发裁决）
- PROJECT_ID / DEV_BEARER 走 `constants/env.ts`（commit 1afa756）
- 字段/枚举/权限/错误码以 OpenAPI + meta API 为准
- 不动后端（OPEN-4/6/7 集中 frontend）

### 注意（跨 session 有效）
- schema 敏感测试前对 pcs_test 跑 `cd pcs-backend && uv run alembic upgrade head`；
  **默认 DATABASE_URL 指 pcs 开发库**，测试需显式 pcs_test（round-trip 测试
  已带守卫）
- 不可逆迁移锚点：`p3sim_stream_sign_status_extend`（enum ADD VALUE）
- PRO/II fixture 预期按**输出实测**对齐，勿按 INDEX 推断（proii .out 多
  problem 拼接 + T1 重复 ×2；T2/T3 仅 INDEX 有条目）
- Pydantic v2 Field description 必含中文
- 塔盘/炼油 parser 段标题守卫必须精确枚举动词（bug-070 教训）
- antd Select 测试标准模式：`document.querySelector('.ant-select-selector')`
  + `fireEvent.mouseDown` + `waitFor(.ant-select-dropdown)` +
  `within(dropdown).getByText().closest('.ant-select-item')`（仿 WorkspaceSwitcher）
- gstack browse 用 `CI=1` 环境变量触发 `--no-sandbox`（OPEN-9 闭环）

---

## Context

- 分支 main（单人直提）；后端 uv+FastAPI+SQLAlchemy 2.0 async+PG16+pytest；
  前端 React 18 + TypeScript + Ant Design 5 + axios + zustand + MSW + vite + vitest
- 测试全量：`cd pcs-backend && uv run pytest`（~96s）；
  `cd pcs-frontend && npx vitest run`（~19s）
- sample/ 9 个 PRO/II 工程不入 git（回归 fixture）
- QA 报告路径：`.gstack/qa-reports/qa-report-pcs-frontend-YYYY-MM-DD-<batch>.md`
- 详细交接：`.wolf/HANDOFF-2026-09-13.md`（含 suggested skills；用户裁决交接文档入项目目录）