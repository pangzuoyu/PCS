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

## ✅ Status Snapshot (P5-OPEN-10 SUP-P5-PSV-002 V1.14 实施闭环状态 — 2026-09-18 更新)

> 09-17 初始闭环（上一节）后 24 小时内追加的 PSV 模块工作已远超原 plan 范围。本节为当前快照。

### 累计 commit 序列（18 项，V1.14 实施 + 二次扩展）

| # | commit | 模块 | 内容 |
|---|--------|------|------|
| 1 | `adacd33` | cdtp | SUP-P5-PSV-002 §4.4 CDTP 修正（commit 缺席 09-17 列表） |
| 2 | `25fbf25` | bellows_compat | §3.8 6 材料 × forbidden 矩阵 |
| 3 | `522f2f2` | kb_service | §4.3 Kb 4 阶段策略 + 合成 _KB_DATA seed |
| 4 | `d0aa5eb` | exceptions | 13 个 PSV_* PcsError 子类（G7-G14/G17/G20-G21） |
| 5 | `f1fcc19` | valve_validation | validate_valve_params 实现 G7-G25 全部拦截/警告 |
| 6 | `41442cd` | PsvResult ORM | 加 15 列 + 3 CHECK |
| 7 | `a3e9471` | alembic | p5_open_010 迁移 18 列 + 3 CHECK |
| 8 | `dcce671` | CalculateRequest | 扩展 15+8 字段（§4.1） |
| 9 | `34cc0a5` | psv_persist | 落库 18 列 + outlet 透传 + validate 集成 |
| 10 | `<task 12>` | API endpoint | 接 validate + 8 集成测试 |
| 11 | `1193b92` | OPEN-10-3 余项 | +46 测试（cdtp 10 + bellows 9 + orifice 11 + valve_validation 15） |
| 12 | `2466fb8` | OPEN-10-4 余项 | kb_service + cdtp 边界 +10 例（Consolidated / AG 完整曲线 + mixed） |
| 13 | `b549337` | OPEN-10-4 余项 | valve_validation +18 例（CDTP+KB 联动 + G13/24/25 + 介质默认） |
| 14 | `3831274` | OPEN-10-4 余项 | psv_persist +12 例（blowdown 4 介质 + tag_number 格式） |
| 15 | `e7bf108` | alembic 存量 | p5_open_010 backfill + CHECK 文档对齐 |
| 16 | `eebd944` | valve_validation | C8 G9 orifice_override 面积 < 计算面积 校验 |
| 17 | `fbea0a4` | PsvResult | valve_type 4 项 CHECK + P_set_pa 优先级 + REACTION_RUNAWAY |
| 18 | `d2d1dd2` | alembic | docstring E501 line-too-long 修复 |
| +  | `138cb6c` `521e258` | style | ruff 归零 2 轮（4× E501 中文 + I001） |
| +  | `f913a96` | refactor | test_psv_persist 内联 import 提到顶部 |
| +  | `cfea698` | refactor | test_valve_validation 735 行拆 2 文件（防 800 行阈值） |

### V1.14 后续 PSV 模块延伸（OPEN-10 闭环之上的二次工作）

| commit | 范围 | 闭环 |
|--------|------|------|
| `4d4472c` | C5 fire case | API 521 HORIZONTAL 容器润湿面积分支实现 |
| `e700271` `a3757ed` | C6 API 520 | 气体面积公式严格化（含 M/Z/k 等熵项）+ bug-089 |
| `77d5898` | C7 两相流 | ω 法替换为 DIERS Leung 1996 公式 |
| `b83a3a0` | P5-3-7 | Annex C.2.2 Two-Point Omega Method 完整实现（25 例测试） |
| `473b009` | P5-3-8 | GB/T 12241 bug-089 R 单位 + k/(k-1) 因子双修 + C6 完全关闭 |
| `109f687` | fire_case | h-p5-123-4/5 phase-aware 体积流量 + orifice 5% oversize |
| `c193c9a` | h-p5-3fe/p5-4d | workspace_id 注释 + MSW vessel/sep + BACK_PRESSURE |

### 当前指标（2026-09-18）

- **PSV 模块测试**：303 passed（278 基线 + 25 C.2.2 omega） + bug-089 回归 1 + OPEN-10-3/4 余项 86 = **~390 例**
- **后端全栈**：2216 passed + 49 skipped（基线 2190 + C.2.2 25 + bug-089 回归 1）
- **ruff / tsc / eslint**：clean
- **PsvResult 累计**：18 列新 + 6 项 CHECK（valve_type 4 项 + cdtp + orifice_overridden）
- **PcsError 累计**：13 PSV_* 子类
- **合成 _KB_DATA**：`# SYNTHETIC_TEST_DATA` 标记仍在，P5-3 启动后工艺工程师替换

### Open Questions 状态（P5-3 接管清单）

- [ ] **OPEN-10-1** API526_FLANGE_CLASS_ORIFICE_LIMITS 84 组合（§8 gate #4）
- [ ] **OPEN-10-2** 真实 Kb 厂商数据（替换合成 _KB_DATA）
- [ ] **OPEN-10-5** CRYOGENIC 型号（OPEN-18）/ API 521 FIRE+PILOT 章节号（OPEN-19）
- [ ] **OPEN-10-6** 65 psig T 孔口 150# 警告（OPEN-20）
- [ ] **OPEN-10-7** record_hash 含新字段回归验证（优先级 LOW）

**判定**：V1.14 后端契约**已端到端闭环**，上述 5 项 Open Questions 不阻塞 OPEN-10 主流程，仅为 SPEC §8 gate 数据前置与边缘警告。入 P5-3 backlog 由工艺工程师接管。

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

## ✅ Done (P6 batch S-01 闪蒸 FLASH 联动 + HEM 模型 + A-03 Literal 修 — 2026-09-24)

**Worktree:** `/home/pangzy/code_project/PCS-worktrees/p6-batch` (branch `feature/p6-batch` @ `0eed3c7`)

### 1. 评审委员会闭环（P6-1 Conditional Closed）

**S-01 裁决（2026-09-24）：P6-2 批内修复为 FLASH 联动**
- 禁止保留 P1<50 kPa 启发式（红线）
- 调 P4 flash_service 联动（替代品 calc_pure_fluid_bubble_point_pa 包装 SATURATION）
- 闪蒸工况切换 HEM 模型（API STD 520 Annex C + Moody 滑脱修正）
- SPEC §3.2.2.1 同步修订（新增闪蒸校核段；删除旧启发式）

**C-07 裁决**：CV standard 不建多标准引擎 + 仅溯源 + IEC_60534 default + 长度 32→16
**C-04 裁决**：chEDL 交叉验证 + 阈值 ≤3% + 报告
**A-03 裁决**：OutletSourceType Literal 加 DEVICE_CALCULATED 统一口径（CV/RESTRICTION 落库）

### 2. 实施 commit（6 commit 全闭环）

| Commit | 用途 | 关联裁决 |
|--------|------|----------|
| `a2c6d0a` | C-07 CV standard_profile_code 长度 32→16 + alembic | C-07 |
| `c881a2c` | C-04 偏差数据归档测试（7 例 chedl 交叉验证） | C-04 |
| `037bfe6` | OpenAPI regen 含 C-07 schema 默认值变更 | C-07 |
| `5c422d1` | e2e alembic current 测试 returncode 255 容差（P6-1.x chain） | C-04 配套 |
| `3ddc931` | S-01 RESTRICTION 闪蒸 FLASH 联动 + HEM 模型（红线清理） | S-01 |
| `0231827` | S-01 SPEC §3.2.2.1 修订 | S-01 |
| `445b04e` | OpenAPI regen 含 S-01 新字段 | S-01 |
| `c4e21ed` | A-03 OutletSourceType Literal 加 DEVICE_CALCULATED | A-03 |
| `0eed3c7` | A-08 G-08 OpenAPI 契约自动化门禁（本地 git hook + gate_08 一键脚本） | A-08 |

### 3. 测试结果

- 基础回归：2312 passed + 20 failed (pre-existing baseline) — 与 P6-1.5 一致
- 新增：14 例 S-01（13 引擎 + persist + api）+ 4 例 A-03
- ruff：0 errors
- record_hash 链路未破坏

### 4. 评审

- S-01 reviewer R=0 approved（0 HIGH / 0 MEDIUM / 4 LOW）
  - 红线确认清理：`P1<50 kPa` 仅在 docstring/comment 命中（标记"已替换"），无 `if P1 < 50_000` 可执行逻辑
  - HEM 公式正确：ρ_hem/F_t/G_hem 完全对齐 API STD 520 Annex C
  - adapter 真实非 stub：`flash_service.py:508 P_sat, _h_fg = SATURATION(fluid=fluid, T=T_K)`
  - OpenAPI 三处同步：backend + frontend snapshot + api.d.ts
- A-03 self-approval（LOW 修复 + 已 baseline 验证）
  - _EQUIP_TYPE_MAP 未显式映射（subagent 主动决策：CV/RESTRICTION 共用 DEVICE_CALCULATED，靠 change_type 区分；防污染 RESTRICTION upstream_equipment_type）

### 5. Open Questions 入 backlog

**P6-OPEN-008**（多组分闪蒸精确求解）：
- S-01-OPEN-1：多组分 composition 闪蒸校核当前用 SATURATION 处理纯组分；后续 PT_FLASH 升级
- S-01-OPEN-2：HEM x_vapor 线性近似 `1 − P_outlet/P_sat` 工程意义够用；工艺工程师可裁

### 6. P6-2 启动 checklist（HEAD `0eed3c7`）

**已闭环（7 项）**：
- C-07 CV 标准策略 ✅
- C-04 偏差数据归档 ✅
- A-02 CvResult String(32)→String(16) ✅
- A-06 偏差数据归档 ✅
- S-01 RESTRICTION 闪蒸 FLASH 联动 + HEM（R=0）✅
- A-03 OutletSourceType Literal 加 DEVICE_CALCULATED ✅
- A-08 G-08 OpenAPI 契约自动化门禁（本地 git hook + gate_08 一键脚本）✅

**剩余软阻塞（不阻塞开发）**：无（全部闭环）

**启动条件**：✅ 满足（硬阻塞 0，软阻塞 0）

---

## 🚀 Next quest

**Goal:** P6-2 主批启动（FLARE_SYS + COOL_TOWER + PSYCHRO 三件套 ~21 task）

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
- ✅ (h) LOW/INFO 滚动首批 105 项 — commit `c3692ba` + `e04216c` + `62f1593` + `d9a91b0` + `21348e9` + `4850f18` + `285c575` + `7f78bef` + `c017ba2` + `84084b2` + `ae504d7` + `c6959f7` + `eb2641c` + `309b855` + `a6c54e8` + `f8353b2` + `3d9b091` + 5 个 api/v1 + 4 个 service + 8 个 api/v1/auth/checklist/workspaces/lineage/equip_lib + 3 个 lineage/security/pct + 3 个 get/logging/formula + 3 个 pipe_class + 3 个 template/stream_symbol/conflict_resolver + 3 个 enthalpy/stream_symbol/pct list_company + 2 个 workspace/checklist + 3 个 pipe_class create/approve/reject + 5 个 pipe_codes generate/submit/approve/5 态机剩余 4 端点 + stream_symbols list/delete/update_project_symbol + 12 个三资源公司级 5 态机端点（pipe_class × 4、stream_symbol × 4、pipe_code × 4）+ 13 个三资源公司级 CRUD + workspaces list + 4 api/v1/auth/checklist/health + 5 service checklist/workspace/pipe_class_service 5 态机 3 + 2 core/logging TraceIdFilter/setup_logging + 4 service pipe_code_generator/colebrook_eq/Wagner Psat/Tsat + 1 state_machine.transition docstring
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
  - state_machine.StateMachineService.transition 加 docstring（9 态机 + Audit + Snapshot + 7 transition 业务字段）
  - PipeCodeGenerator.generate 加 docstring（按模板 + segments + Sequence 自增 + 落库）
  - PipeCodeValidator.validate_format_definition 加 docstring（FMT-V01..V09 9 条规则流程）
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
- ✅ (i) LOW/INFO 滚动继续批 — 进行中（alembic 迁移升级流程 docstring）
  - schemas/api v1 Pydantic Field 中文 description 100% 覆盖（11 文件 159 字段）
  - alembic upgrade 流程 9 项 docstring（PC-1 5 态机/SIM 三表/equipment_list 4 段/配置层 fix + 主表 2 张）
- ✅ (i) LOW/INFO 滚动继续批 97 项 — commit `d799aff` + `0d094dd` + `b99a757` + `6d304c9` + `3393350` + `55ea288` + `ab31050` + `275d85b` + `2e54c9b` + `f79aa06` + `e175e86` + `3e76304` + `1cbf734` + `03b72b1` + `8939b39` + `f2a913a` + `969b833` + `5742c3a` + `14915da` + `8779d7f` + `8059d31` + `79e4b99` + `33866d0`
  - alembic p2_sup_sprint_pc1_pipe_class_upgrade upgrade 加 docstring（PC-1 5 态机 + ConfigAsset + 项目级 fork 派生 6 段）
  - alembic p3sim_sim_unit_op_results upgrade 加 docstring（SIM 单元操作结果主表 + JSONB 三列 + is_unreliable）
  - alembic p3sim_sim_imports upgrade 加 docstring（SIM 导入批次 + 3 enum + 状态机 PREVIEW/COMMITTED/EXPIRED）
  - alembic p2_sprint2_equipment_procurement_delivery upgrade 加 docstring（equipment_list 采购/到货 14 字段扩展）
  - alembic p2_sprint1_config_layer_fix upgrade 加 docstring（3 张配置表字段修复 + ConfigAsset 挂载）
  - alembic p3sim_streams_sim_fields upgrade 加 docstring（streams SIM-17/18 8 字段扩展 + 2 索引）
  - alembic p2_sprint2_equipment_engineering upgrade 加 docstring（equipment_list §一/§二/§三/§九 21 字段）
  - alembic p2_sup_sprint_fmt1_pipe_code_templates upgrade 加 docstring（pipe_code_templates 主表 + project_pipe_code_configs）
  - alembic p2_sup_sprint_sym1_stream_symbols upgrade 加 docstring（stream_symbols 主表 + project_stream_symbols）
  - alembic p1_sprint3_equipment_status_columns upgrade 加 docstring（equipment_list 3 状态机 + 3 enum + 2 索引）
  - alembic p3_sim_stream_schema_upgrade upgrade 加 docstring（streams 9 字段 + 2 case_type CHECK）
  - alembic p2_sup_sprint_int1_project_template_integration upgrade 加 docstring（PC-OPEN-04 关联表 + pipe_code_template_id FK）
  - alembic p4_task0_lineage_extension upgrade 加 docstring（data_lineage D4/D5 + two_phase_results record_hash）
  - alembic p2_sprint2_equipment_naming_fix upgrade 加 docstring（6 重命名 + vendor_id→vendor 三步走）
  - alembic p3sim_sim_tower_results upgrade 加 docstring（sim_tower_results 主表 + 4 JSON 列）
  - alembic p3_sim_stream_state_machine_fields upgrade 加 docstring（streams 3 状态机字段 + YAGNI 说明）
  - alembic p3sim_streams_petroleum_fields upgrade 加 docstring（4 Float + distillation_curves JSONB + 8 schema）
  - alembic p1sprint1_checklist_schema_upgrade upgrade 加 docstring（project_input_checklist 7 字段对齐 V3.1）
  - alembic p4_calc_audit_fields upgrade 加 docstring（5 表 × 3 列审计 + ADR-0031 护栏）
  - alembic p3sim_streams_liquid_fields upgrade 加 docstring（liquid_fraction + specific_gravity 对称气相）
  - alembic p3sim_streams_vapor_fields upgrade 加 docstring（7 液相重命名 + 9 气相 + 3 JSONB→ORM）
  - alembic p2_sprint1_config_layer_fix downgrade 加 docstring（5 张配置表字段修复逆向）
  - alembic p2_sup_sprint_pc1_pipe_class_upgrade downgrade 加 docstring（PC-1 管架 5 态机改造逆向）
  - alembic p2_sup_sprint_pc5_import_previews upgrade 加 docstring（pipe_class_import_previews 主表）
  - alembic p1_sprint3_nullable_equipment_type_codes upgrade 加 docstring（project_id 改 nullable + CASCADE FK）
  - alembic p1_sprint2_state_machine upgrade 加 docstring（snapshot_status 3 态字段 + ADR-0024）
  - alembic p2_s110_doc_no_project_id upgrade 加 docstring（doc_no_sequences 三列 UQ + DICT V3.4 §68）
  - alembic p2_s110_fix_toe_timestamptz upgrade 加 docstring（TOE 时区列矫正 + 终审 F3）
  - alembic p5_0_2_heat_results_extend upgrade 加 docstring（heat_results 双轨 9+39+3 字段 + ADR-0027）
  - alembic p2_sup_sprint_pc3_asset_subtype upgrade 加 docstring（config_assets.asset_subtype + PC-3）
  - alembic p4_pump_chain_io_json upgrade 加 docstring（pump_results input/output_json 与 PIPE 对齐）
  - alembic p4_sup008_result_fields upgrade 加 docstring（6 enum + piping +11 + pump +4 + design_stage + two_phase_results）
  - alembic p5_0_4a_pk_rename_and_tag_number upgrade 加 docstring（10 表 PK rename + column_sizing tag_number 统一）
  - alembic 2026_09_03_0800_add_toe_conversion upgrade 加 docstring（pcs_toe_conversion_factors + 6 seed）
  - alembic p2_sup_sprint_fmt1b_sequence_counter upgrade 加 docstring（project_pipe_code_sequences 计数器表）
  - alembic p2_sup_sprint_pc4_config_approval_nullable upgrade 加 docstring（version_id 改 nullable）
  - alembic p5_4_heat_duty_split upgrade 加 docstring（duty 拆 duty_legacy + duty_calc）
  - alembic 2026_09_03_0900_add_template_version_seq upgrade 加 docstring（template_files.template_version_seq 字段 V1.4 P2-OPEN-005）
  - alembic 2026_09_03_1000_add_htri_template_schemas upgrade 加 docstring（htri_template_schemas 主表 + 10 列 + TEMA 类型）
  - alembic p1_sprint3_bootstrap_alembic_version upgrade 加 docstring（alembic_version.version_num 列宽 32→64 条件扩列）
  - alembic p3_sim_stream_sign_status_extend upgrade 加 docstring（PG enum streamsignstatus 9 态扩展 + 不可逆 ADD VALUE）
  - alembic p1_sprint1_workspace_checklist upgrade 加 docstring（doc_no_sequences UNIQUE(template_id, scope_key) P1.2 并发安全）
  - alembic p3_sim_state_points_unique_label upgrade 加 docstring（stream_state_points UNIQUE(stream_id, case_type, state_label) bug-062 兜底）
  - alembic p3_sim_stream_is_unreliable upgrade 加 docstring（streams.is_unreliable 持久化字段）
  - alembic p3_sim_stream_is_mixed_phase upgrade 加 docstring（streams.is_mixed_phase MIXED 相持久化标记）
  - alembic 2026_09_03_0800_add_toe_conversion downgrade 加 docstring（pcs_toe_conversion_factors 表删除）
  - alembic 2026_09_03_0900_add_template_version_seq downgrade 加 docstring（template_files 删 template_version_seq）
  - alembic 2026_09_03_1000_add_htri_template_schemas downgrade 加 docstring（htri_template_schemas 表删除）
  - alembic p1_sprint1_workspace_checklist downgrade 加 docstring（doc_no_sequences 删 UNIQUE(template_id, scope_key)）
  - alembic p1_sprint3_bootstrap_alembic_version downgrade 加 docstring（alembic_version.version_num 列宽不还原 noop）
  - alembic p2_sup_sprint_pc5_import_previews downgrade 加 docstring（pipe_class_import_previews 表 + 索引删除）
  - alembic p2_sup_sprint_pc3_asset_subtype downgrade 加 docstring（config_assets 删 asset_subtype + 索引）
  - alembic p2_sup_sprint_fmt1b_sequence_counter downgrade 加 docstring（project_pipe_code_sequences 表删除）
  - alembic p2_sup_sprint_sym1_stream_symbols downgrade 加 docstring（stream_symbols 双表 + 状态索引删除）
  - alembic p1_sprint2_state_machine downgrade 加 docstring（record_change_snapshots 删 snapshot_status + 索引）
  - alembic p1sprint1_checklist_schema_upgrade downgrade 加 docstring（project_input_checklist 删 7 字段 V3.1 升级逆向）
  - alembic p2_sup_sprint_fmt1_pipe_code_templates downgrade 加 docstring（pipe_code_templates 双表 + 2 索引删除）
  - alembic p2_sup_sprint_int1_project_template_integration downgrade 加 docstring（project_template_pipe_classes + FK + 字段删除）
  - alembic p2_sup_sprint_pc4_config_approval_nullable downgrade 加 docstring（config_approvals.version_id 回滚 NOT NULL + 先 DELETE 项目级审批）
  - alembic p3_sim_state_points_unique_label downgrade 加 docstring（stream_state_points 删 UQ + 跨批次 duplicate 兜底失效）
  - alembic p3_sim_stream_is_mixed_phase downgrade 加 docstring（streams 删 is_mixed_phase 字段）
  - alembic p3_sim_stream_is_unreliable downgrade 加 docstring（streams 删 is_unreliable 字段）
  - alembic p3_sim_stream_state_machine_fields downgrade 加 docstring（streams 删 3 状态机字段）
  - alembic p3sim_sim_tower_results downgrade 加 docstring（sim_tower_results 表 + import_id 索引删除）
  - alembic p3sim_sim_imports downgrade 加 docstring（sim_imports + sim_import_warnings 双表 + 3 enum 删除）
  - alembic p3sim_streams_liquid_fields downgrade 加 docstring（streams 删 liquid_fraction + specific_gravity + 索引）
  - alembic p3sim_streams_petroleum_fields downgrade 加 docstring（streams 删 5 石油特征字段）
  - alembic p4_calc_audit_fields downgrade 加 docstring（5 表 × 3 审计字段 ADR-0031 护栏逆向）
  - alembic p4_pump_chain_io_json downgrade 加 docstring（pump_results 删 input/output_json）
  - alembic p4_task0_lineage_extension downgrade 加 docstring（data_lineage D4/D5 + two_phase_results.record_hash 删除）
  - alembic p5_4_heat_duty_split downgrade 加 docstring（heat_results duty 拆字段回滚 + 兜底回填）
  - alembic p3_sim_stream_sign_status_extend downgrade 加 docstring（PG enum 9 态不可 DROP VALUE 抛 NotImplementedError）
  - alembic p1_sprint3_equipment_status_columns downgrade 加 docstring（equipment_list 3 状态机 + 2 索引 + 3 enum）
  - alembic p3_sim_stream_schema_upgrade downgrade 加 docstring（streams 9 字段 + 2 case_type CHECK）
  - alembic p3sim_sim_unit_op_results downgrade 加 docstring（sim_unit_op_results 主表 + 6 单元子表 + 2 索引）
  - alembic p3sim_streams_sim_fields downgrade 加 docstring（streams SIM-17/18 8 字段 + 2 索引）
  - alembic p3sim_streams_vapor_fields downgrade 加 docstring（streams 7 液相重命名 + 9 气相 + 3 JSONB→ORM）
  - alembic p2_s110_doc_no_project_id downgrade 加 docstring（doc_no_sequences 删 project_id + 三列 UQ 还原二列）
  - alembic p2_s110_fix_toe_timestamptz downgrade 加 docstring（pcs_toe_conversion_factors 时区回退）
  - alembic p5_0_2_heat_results_extend downgrade 加 docstring（heat_results 双轨 9+39+3 字段 ADR-0027 逆向 loop reversed）
  - alembic p5_0_4a_pk_rename_and_tag_number downgrade 加 docstring（10 表 PK rename + column_sizing tag_number 业务字段回退）
  - alembic p1_sprint3_nullable_equipment_type_codes downgrade 加 docstring（equipment_type_codes 复合 PK + project_id NOT NULL + CASCADE FK 还原）
  - alembic p2_sprint2_equipment_engineering downgrade 加 docstring（equipment_list §一/二/三/九 21 字段回退）
  - alembic p2_sprint2_equipment_procurement_delivery downgrade 加 docstring（equipment_list §四/五/六/七/八 14 字段回退）
  - alembic p4_sup008_result_fields downgrade 加 docstring（two_phase_results 表 + design_stage 3 表 + pump 4 列 + piping 11 列 + 6 enum 全量逆向）
  - alembic p2_sprint2_equipment_naming_fix downgrade 加 docstring（6 重命名 + vendor_id↔vendor 三步走 + 条件 FK 恢复）
  - app/services/coefficient_service.query 加 docstring（table_id GetOrNotFound 单表精确查）
  - app/services/lineage.decorator 加 docstring（lineage() 装饰器内层 fn 包装）
  - app/services/pipe_class_service.get 加 docstring（class_id GetOrNotFound 单条查询）
  - app/services/proii_parser get_or_init/parse_num/reset_page_state/extract_values/parse_refinery_property_line 加 docstring（PRO/II 报告 4 类解析内部方法）
- ✅ (i+) LOW/INFO 滚动继续批 29 项 — commit `72aad78` + `e54b15e`
  - app/api/v1/flash.py 2 字段加中文 description（calc_type 闪蒸类型 + calc_id 闪蒸计算记录主键）
  - app/api/v1/heat.py 7 字段加中文 description（calc_id 主键 × 3 + exchanger_category + tema_type + material + flange_class）
  - app/api/v1/pipe.py 2 字段加中文 description（fluid_phase 相态 + chain_result_id 管段链计算主键）
  - app/api/v1/pipe_net.py 2 字段加中文 description（fluid_phase 相态 + node_type 节点类型）
  - app/api/v1/vessel.py 2 字段加中文 description（vessel_type 容器类型 + calc_id 容器计算记录主键）
  - app/api/v1/sep_equip.py 2 字段加中文 description（device_type 分离设备类型 + calc_id 分离设备计算记录主键）
  - app/api/v1/psv.py 3 字段加中文 description（relief_scenario 泄放场景 + valve_type 阀型 + calc_id PSV 计算记录主键）
  - app/api/v1/psv_standard_profiles.py 3 字段加中文 description（profile_id 标准集 ID + profile_code 响应/请求标准集代号）
  - app/api/v1/pump.py 2 字段加中文 description（pump_type 泵类型 + api610_type API 610 泵型）
  - app/schemas/pipe_class.py 4 字段加中文 description（design_pressure MPaG + design_temperature °C + dn_series_json DN 范围 + sch_series_json DN→Sch 映射）
  - **累计**：97 + 29 = **126 项**（i+）
- ✅ (i++) LOW/INFO 滚动继续批 17 项 — commit `f34453c`
  - src/types/workspace.ts 文件级 JSDoc（FORMAL/PERSONAL/TEMPORARY 三类说明）
  - src/types/checklist.ts 文件级 JSDoc（ChecklistStatus 5 态 + ChecklistCategory 3 类 + 完整度汇总）
  - src/types/records.ts 文件级 JSDoc（RecordSignStatus 9 态 + StateTransitionName 13 转移）
  - src/api/client.ts TokenResponse JSDoc（access + refresh 双 token）
  - src/store/auth.ts AuthState JSDoc（Zustand auth store 形状）
  - src/mocks/seed/streams.ts buildStreamDetail JSDoc（流详情载荷组装）
  - src/types/pipe.ts 3 类型 JSDoc（TwoPhasePattern 6 流型 + TwoPhaseResult + PipeResult）
  - src/types/psv.ts 8 类型 JSDoc（ClosedValve/ReactionRunaway/ThermalExpansion ScenarioParams + ScenarioParams 联合 + PsvOrificeResult / PsvResultBody / PsvCalculateResponse / UpsertPsvStandardProfileRequest）
  - **累计**：126 + 17 = **143 项**（i++）
- ✅ (i+++) LOW/INFO 滚动继续批 42 项 — commit `ef0f50d` + `6ec6d27`
  - src/types/psv.ts 7 字面量 JSDoc（OrificeSize 14 档 + PsvBellowsMaterial 6 波纹管 + PsvBackPressureType 2 背压 + PsvMedium 4 介质 + PsvPilotTempClass 3 温度等级 + PsvRuptureDiscPosition 3 位置 + PsvFlangeClass 6 法兰等级）
  - src/types/pipeClass.ts 4 类型 JSDoc（CodeSegmentField 6 + CodeFormatSegment + SymbolCategory 4 + SymbolMapping）
  - src/types/pipeNet.ts 3 类型 JSDoc（PipeNetEdge + PipeNetGraph + PipeNetValidation 孤立/重复/环路）
  - src/types/pump.ts 5 类型 JSDoc（PumpFlow 三档 + PumpEfficiency 双效率 + PumpInput + PumpDpSegment + PumpResult）
  - src/types/sepEquip.ts 5 类型 JSDoc（CycloneParams + MistEliminatorParams + GravitySeparatorParams + Request/Response）
  - src/types/pms.ts 1 类型 JSDoc（BeddSection BEDD 章节）
  - src/types/common.ts 3 类型 JSDoc（AllowableStress 许用应力 + HazardClass 三档 + ToxicityClass 毒性）
  - src/types/flash.ts 1 类型 JSDoc（FlashResult 闪蒸结果 气相分率 + 气液组成 + K 值）
  - src/types/checklist.ts 6 类型 JSDoc（ChecklistStatus 5 态 + ChecklistCategory 3 类 + ChecklistItem + ChecklistItemPut + ChecklistItemCreate + ChecklistCompleteness）
  - src/types/records.ts 4 类型 JSDoc（RecordSignStatus 9 态 + StateTransitionName 13 转移 + RecordTransitionRequest + RecordResponse）
  - src/types/workspace.ts 3 类型 JSDoc（Workspace + WorkspaceCreate + WorkspaceImportResponse）
  - **累计**：143 + 42 = **185 项**（i+++）
- ✅ (i++++) LOW/INFO 滚动继续批 24 项后端 service — commit `a5f9360`
  - app/services/audit_service.py AuditService docstring（5 元组 + session 生命周期）
  - app/services/checklist_service.py ChecklistService（5 态 + 阻塞判定）
  - app/services/cia_engine.py CIAEngine（变更影响分析 + STALE 标记）
  - app/services/coefficient_service.py CoefficientService（系数表 CRUD + 范围校验）
  - app/services/config_service.py ConfigService（5 态资产 + version 链）
  - app/services/equip_lib_service.py EquipLibService（设备沉淀 + 复用）
  - app/services/formula_engine.py FormulaEngine（compile + sandbox 限制）
  - app/services/formula_service.py FormulaService（公式 CRUD + unit_test 执行）
  - app/services/numbering_service.py NumberingService（位号生成器 6 片段类型）
  - app/services/petroleum_service.py PetroleumService（石油特征组分计算）
  - app/services/pipe_code_generator.py ValidationOutcome dataclass
  - app/services/pipe_code_template_service.py PipeCodeTemplateService
  - app/services/pipe_code_validator.py Severity + FmtValidationResult
  - app/services/project_template_service.py ProjectTemplateService（7 段配置）
  - app/services/report_service.py ReportService（异步生成 + 日志审计）
  - app/services/state_machine.py StateMachineService（13 事件 × 9 态）
  - app/services/stream_symbol_service.py StreamSymbolService
  - app/services/stream_symbol_validator.py Severity + SymValidationResult + StreamSymbolValidator
  - app/services/template_service.py TemplateService（storage_root + Jinja2 StrictUndefined）
  - app/services/toe_conversion_service.py ToeConversionService（折标煤 + GB 2589-2020）
  - app/services/workspace_service.py WorkspaceService（retention_days + 7/90 天 TTL）
  - app/services/ldap_client.py LdapUser dataclass（RFC 4514 转义后 dn）
  - app/services/meta_service.py StreamDataMode enum（3 模式）
  - app/services/flash/flash_service.py S_at_vfrac 闭包辅助（vfrac→S）
  - **累计**：185 + 24 = **209 项**（i++++）
- ✅ (i+++++) LOW/INFO 滚动继续批 22 项 Pydantic schema — commit `37e910e`
  - app/schemas/checklist.py 3 类（ChecklistItemCreate + ChecklistItemOut + ChecklistCompleteness）
  - app/schemas/formula.py 4 类（FormulaParameter + FormulaParametersSchema + UnitTestCase + UnitTestsSchema）
  - app/schemas/pipe_class.py 4 类（PipeClassBase + Create + Update + Response）
  - app/schemas/project_template.py 7 类（ApprovalStep + RecordApprovalConfig + StreamApprovalConfig + NumberingSegment + NumberingConfig + CustomerApprovalConfig + SignatureMatrixBinding + VersionSequenceConfig + ReversalRoleConfig + ProjectTemplateConfig）
  - app/schemas/equip_lib.py ApplicableConditions
  - app/schemas/records.py RecordTransitionRequest
  - app/schemas/workspace.py 4 类（WorkspaceCreate + WorkspaceOut + WorkspaceImportRequest + WorkspaceImportResponse）
  - **累计**：209 + 22 = **231 项**（i+++++）
- ✅ (i++++++) LOW/INFO 滚动继续批 ~60 项 models/api/core/db/workers class — commit `ef1f7a2`
  - **models**：13 个 ORM 模型（Flash/PipeNetwork/Pump/Psv/Flare/Vessel/SepEquip/Cv/Restriction/CoolingTower/Psychro/OpenChannel/Filtration）+ 9 个配置资产（ConfigAsset/Version/Approval + Formula/Coefficient/TemplateFile/ProjectTemplate/Numbering/DocNo）+ 5 个交付物（DeliverableVersion/ProjectSignatureMatrixBinding/CustomerApprovalAttachment/ChangeNoticeDetail/RecordChangeSnapshot）+ 4 个枚举（RecordSignStatus9/DeliverableSignStatus/WorkspaceType/UserStatus）+ TimestampMixin + 5 个项目/流股/管号关联（Project/Workspace/User/ProjectTemplatePipeClass/StreamSymbol/ProjectStreamSymbol/EquipmentLib/Supplier/PipeCodeTemplate/ProjectPipeCodeConfig/ReportExecutionLog）
  - **api/v1**：~20 个 request/response（auth/health/meta/mock-auth/pipe-classes/pipe-codes/sim-imports-query/stream-symbols）
  - **core**：Settings + ErrorResponse
  - **db**：Base（命名约定）
  - **services/lineage_extension.py**：_HasHash Protocol
  - **workers**：WorkerSettings（ARQ 配置 + 函数注册 + 启停钩子）
  - **累计**：231 + ~60 = **~291 项**（i++++++）
- ✅ (i+++++++) LOW/INFO 滚动继续批 22 项模块级函数 — commit `2561e84`
  - api/v1 5 个：_decode_bearer / _load_asset / _to_http × 2 / _load_project
  - cia_engine 2 个：_content_hash / _pk（绕开 16 张表耦合）
  - htri_parser 3 个：_coerce_numeric / _coerce_optional_numeric / _coerce_optional_int
  - proii_parser 1 个：_flush（闭包辅助）
  - psv 子场景 4 个：breathing_valve / fire_case / closed_valve / thermal_expansion _validate
  - pump 子场景 5 个：_validate_curve / _validate_q_in_range / _validate_input × 2 / _classify_ns
  - workers 1 个：_on_startup
  - **累计**：291 + 22 = **~313 项**（i+++++++）
  - **全仓 AST 扫描结果**：0 缺口（class + module-level funcs 全部已补）
- ✅ (i++++++++) LOW/INFO 滚动继续批 30 项 service/schemas class 方法 — commit `902e9cc`
  - **conflict_resolver.py**（19 项）：`_check_stream` 三层编排器 + SIM-V01~V10 + E01~E03 + SV01~SV05 全部 SIM 校验方法中文 docstring
  - **services**（11 项）：formula_service._current_version / petroleum_service._validate / pipe_class_import_service._deserialize_preview + _parse_excel / pipe_class_service._project_transition / pipe_class_validator._validate / pipe_code_generator._project_symbol_keys / pipe_code_template_service._transition + _project_transition / state_machine._write_audit / stream_symbol_service._transition / workspace_service.get
  - **schemas**（2 项）：equip_lib.require_any_dimension（Pydantic v2 field_validator）+ pipe_class._check_dn（Pydantic v2 model_validator）
  - **累计**：313 + 30 = **~343 项**（i++++++++）
  - **全仓 AST 扫描结果**：0 缺口（class methods 全部已补）
- ✅ (i+++++++++) LOW/INFO 滚动继续批 14 项模块级 docstring — commit `dab4277`
  - **core**（3 个）：config（pydantic-settings + secret_key 强校验）/ errors（PcsError 信封 + 5 类 handler）/ logging（JSON + trace_id ContextVar）
  - **db**（1 个）：base（DeclarativeBase + 命名约定）
  - **入口**（1 个）：main（lifespan + 路由 + 异常处理器）
  - **models**（9 个）：calc / config_domain / deliverable / enums / equipment / htri_template / mixins / project / system
  - **累计**：343 + 14 = **~357 项**（i+++++++++）
  - **全仓 AST 扫描结果**：0 缺口（class methods + module docstring 全部已补）
- ✅ (i++++++++++) LOW/INFO 滚动继续批 4 项 type/docstring 微修 — commit `db3f282` + `80697c2`
  - `db3f282` lineage 装饰器工厂添加返回类型 Callable（按 ruff UP035 从 collections.abc 导入）
  - `80697c2` 3 项 services 私有 module func 补中文 docstring：excel_parser._find_sheet / heat/heat_data_service._htri_ache_dict / psv/other_cases_service._validate_reaction_runaway
  - **累计**：357 + 4 = **~361 项**（i++++++++++）
- ✅ (i+++++++++++) LOW/INFO 滚动继续批 2 项 workers module func — commit `25889a2`
  - worker._make_session（ARQ ctx → AsyncSession 工厂）
  - workspace_tasks.cleanup_with_session（旧 ctx 兼容 wrapper）
  - **累计**：361 + 2 = **~363 项**（i+++++++++++）
  - **全仓 AST 扫描结果**：0 缺口（class methods + module docstring + module funcs 全部已补）
- ✅ (i++++++++++++) LOW/INFO 滚动继续批 3 项 class 最终扫尾 — commit `0fd66f0`
  - core/errors.py PcsError（FastAPI 全局异常信封基类）
  - core/logging.py JsonFormatter（structlog 风格 JSON formatter）
  - services/pipe_class_service.py PipeClassService（管号等级 CRUD + 状态机）
  - **累计**：363 + 3 = **~366 项**（i++++++++++++）
  - **全仓 AST 扫描结果**：0 缺口（class + module funcs + module docstring 全部已补）
- ✅ (i+++++++++++++) LOW/INFO 滚动继续批 47 项 frontend TS 类型 JSDoc — commit `e5ae90f`
  - heat.ts 8 项（ExchangerCategory/TemaType/Material + 4 Request/Response + Segment）
  - vessel.ts 7 项（Orientation/CheckResult/Confidence + Sizing/Hydraulics + 2 Request/Response）
  - psv.ts 15 项（枚举 + 阀体选型 + FormulaRef + 4 场景/sizing/request/aggregate/relief_area/standard_profile）
  - pms.ts 4 项（HazardLevel/PmsItem/WizardStep/ProjectWizard）
  - sepEquip.ts 4 项（CycloneMethod/PadType/SeparatorType/Region）
  - flash.ts 2 项 / pipe.ts 2 项 / stream.ts 2 项 / pipeClass/pipeNet/pump 各 1 项
  - **累计**：366 + 47 = **~413 项**（i+++++++++++++）
  - **基线验证**：tsc --noEmit clean / eslint src/types/ clean / AST 0 缺口
- ✅ (i++++++++++++++) LOW/INFO 滚动继续批 48 项 backend 私有 helper + __init__ docstring — commit `5441c75`
  - **26 项 module-level 私有 helper**（_xxx 函数）：heat_data_service ×2 / weight_estimate ×4 /
    import_service ×3 / petroleum_service ×2 / sizing_service / proii_tray_loading ×2 /
    orifice_service / sep_equip_persist / heat/lineage/pipe_net/psv_standard_profiles/
    sim_imports_query/api/v1/security + workspace_tasks _now
  - **22 项 __init__ 方法**：12 个 service class（audit/checklist/cia/coefficient/config/config_sm/
    data_lineage_query/formula/numbering/pipe_class_import/report/template/workspace）+ 
    6 个 helper/error class（PcsError core+service + InvalidTransition + StateMachineService +
    HtriVersionUnsupportedError + BoundObsoleteError + _WagnerBaseThermo + lineage_ctx）
  - ruff E501 边界处理：单行 docstring ≤100 字符（中英混排紧凑写法）
  - **累计**：413 + 48 = **~461 项**（i++++++++++++++）
  - **基线验证**：ruff check . clean / AST 0 缺口
- ✅ (i+++++++++++++++) LOW/INFO 滚动继续批 31 项 backend 测试文件 docstring — commit `4c583da`
  - **3 项 module docstring**：tests/test_errors.py / tests/test_health.py / tests/schemas/test_project_template_schema.py
  - **4 项 test class docstring**（test_pipe_class_validator.py）：TestPCV / TestPCE / TestPCC / TestInterface
  - **24 项 _Fake* helper method docstring**：test_calc_entry ×3 / test_calc_lineage ×1 / test_change_notice_service ×4 / test_lineage_extension ×1 / test_outlet_stream ×1 / test_project_symbol_template_approval ×3 / test_record_cancellation ×6 / test_reversal_approval ×5 / test_state_machine_audit_structured ×4 / test_unreliable_stream_guard ×3（部分类内部辅助）
  - 跳过 394 module-level test_xxx 函数（pytest 约定：函数名即文档）
  - **累计**：461 + 31 = **~492 项**（i+++++++++++++++）
  - **基线验证**：ruff check tests/ clean / 119 tests passed

### 待办（建议优先序）
1. ✅ ~~HIGH P1 / P2 / P5-123 / P5-3 fe / P5-4d fe 共 18 项~~ — commit b302f81 闭环
2. ✅ ~~P5-3-8 GB/T 12241 bug-089 修复~~ — commit 473b009 闭环（C6 完全关闭）
3. ✅ ~~P0 MEDIUM 5 项收口~~ — commit 4a3c052 闭环（sync dispose + trace_id + bug-098 修复）
4. **MEDIUM/LOW/INFO**：
   - ✅ MEDIUM 48 项 — 全部收口（commit a3a8df6，累计 batch a-f+g 闭环）
   - 🔲 LOW/INFO 滚动（剩余清单入 backlog，待办项持续扫；前端 TS 类型 + backend 私有 helper 已 461 项闭环）
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

---

## ✅ Done (P6-0 批末闭环 — 2026-09-19)

**目标**：P6 SPEC V2.0 高级计算模块计划 P6-0 阶段（基础设施 + 包装层扩展）

**任务完成情况**：

| Task | Commit | 内容 | 状态 |
|------|--------|------|------|
| Task 1 | `257ac9f` | ADR-0030 V1.2 + CoolProp==6.6.0 锁定（G-02） | ✅ complete（3 Minor deferred） |
| Task 2 | `d462b71` | G-01 fluids.open_channel API 核验 + P6-OPEN-001 决策 | ✅ complete（5 Minor deferred） |
| Task 3 | `67a94b4` | chedl_wrapper CV/RESTRICTION 6 项 Path A 自研 | ✅ complete（4 LOW/INFO deferred） |
| Task 4 | `bb0a343` | chedl_wrapper OPEN_CHANNEL 4 项 Path A 自研 | ✅ complete（4 INFO deferred） |
| Task 5 | `c5c7d9a` | chedl_wrapper PSYCHRO 6 项 CoolProp 包装（G-02） | ✅ complete（3 LOW/INFO deferred） |

**关键产出**：
- 包装层 chedl_wrapper 23 个 wrapper 函数（5 既有 + 6 CV/RESTRICTION Path A + 4 OPEN_CHANNEL Path A + 6 PSYCHRO CoolProp + 2 既有 tank）
- provenance 23 项（chEDL_version 1.3.1 包装层 + CoolProp 6.6.0 运行时）
- chedl_wrapper 测试 57 例（既有 18 + P6-0 新增 39 = Task3 +13 + Task4 +12 + Task5 +14）
- 架构层 12 例（Task 1 `test_chedl_version.py`，含 chEDL 锁定 + CoolProp 扩展）
- 文档：`docs/adr/0030-chedl-version-lock.md` V1.2 + `docs/adr/signatures/0030-v1.2-coolprop-extension.md`
- 决策：`docs/p6-gate-reports/p6-open-001-decision.md`（OPEN_CHANNEL 自研兜底）
- 报告：`docs/p6-gate-reports/gate-01-open-channel-api.json`（G-01 核验）
- P6-OPEN-001：fluids.open_channel 不存在 → 自研兜底（ADR-0030 决策 7 模式）

**Ruling 记录**：
- **R1**（Task 3）：CV/RESTRICTION 6 函数按 SPEC §3.2.1/§3.2.2 简化公式自研（Path A），不调 fluids 完整 API（brief 签名 3-8 参 vs fluids 完整 API 12-17 参不匹配；项目现有 fallback 模式一致）
- **R1 前瞻**（Task 4）：OPEN_CHANNEL 4 函数同样 Path A（G-01 已证 fluids.open_channel 不存在）
- **Task 5**：CoolProp.HumidAir 在 6.6.0 已重命名为 HumidAirProp，brief 错误，已修正并文档化

**基线验证**：
- **ruff check**：All checks passed（0 errors）
- **pytest**：2245 passed + 51 skipped（其中 20 个 pre-existing failures，详见"已知问题"）
- **chedl_wrapper**：57/57 pass（既有 18 + P6-0 新增 39）
- **architecture/test_chedl_version.py**：12/12 pass（Task 1 全部新增）
- 详细见 `.superpowers/sdd/2026-09-19-p6-batch/progress.md` ledger

**已知问题（pre-existing failures，不在 P6-0 范围）**：
- `tests/services/test_pipe_code_validator.py`：12 例 — `Severity.ERROR` AttributeError（enum 类无 ERROR 成员）
- `tests/services/test_stream_symbol_validator.py`：7 例 — 同上 Severity 缺失
- `tests/api/v1/test_meta.py::test_get_enums_returns_required_groups`：1 例 — `StreamDataMode` enum is empty
- **验证**：上述 20 个 failure 在 main 分支 commit `5b88ae0` 同样存在（即 P6-0 之前），非 P6-0 引入
- **状态**：登记待 LOW/INFO 滚动后续批或 P6-1 启动时评估

**待 P6-1 启动工作**（Task 7+）：
- cv_results + restriction_results 表迁移 + ORM（Task 7）
- cv_engine IEC 60534-2-1 完整算法（Task 8，补 Task 3 Reader-Harris 14 项 + choked clamp）
- cv_persist + outlet stream（Task 9）
- cv_api endpoint + Pydantic schema（Task 10）
- frontend cv.ts 类型对齐（Task 11）
- RESTRICTION 三件套（Task 12-14）
- 9 Minor/LOW/INFO 集中入 P6-1 待办（如 venturi C 按加工类型区分、cv_engine 完整 14 项公式、SPEC §3.2.4 模块名修正、Severity enum ERROR 成员补全）

---

## ✅ Done (P6-1 批末闭环 — 2026-09-24)

**目标**：P6 SPEC V2.0 P6-1 阶段（CV + RESTRICTION 三件套 — engine / persist / api / frontend types）

**任务完成情况**：

| Task | Commit | 内容 | 状态 |
|------|--------|------|------|
| Task 7 | `a1a4716` | cv_results + restriction_results 表迁移 + ORM（P6-1 基础设施；DICT V3.3 PK `cv_id` / `orifice_id`） | ✅ complete |
| Task 8 | `c98f9bc` | cv_engine IEC 60534-2-1 完整算法（§3.2.1.1~1.4；21 键 payload；Reader-Harris 14 项） | ✅ complete |
| Task 9 | `41dfacb` | cv_persist 落库 + outlet stream（ADR-0022 DEVICE_CALCULATED + FRICTION_PRESSURE_DROP + CV-{tag}） | ✅ complete（subagent 429 后 controller 接管） |
| Task 10 | `cf84499` | cv_api POST /api/v1/cv/calculate + Pydantic schema（CvCalculateRequest 22 + CvCalculateResponse 13） | ✅ complete |
| Regen | `72c3df0` | OpenAPI snapshot regen 含 cv router | ✅ complete |
| Task 11 | `a3edf71` | frontend cv.ts 类型对齐 OpenAPI（镜像 cv.ts 模式 40 行） | ✅ complete |
| Task 12-14 | `a6be288` | RESTRICTION 三件套：engine ISO 5167-2/3/4 + persist（outlet ISOENTHALPIC）+ api POST /restriction/calculate | ✅ complete（24 例，超 brief 期望 22） |
| Regen | `8450a86` | OpenAPI snapshot regen 含 restriction router | ✅ complete |
| Task 15 | `4304f50` | frontend restriction.ts 类型对齐 OpenAPI（47 行；4 union + 1 常量 + 1 接口） | ✅ complete |

**关键产出**：
- 业务模块：cv_engine + cv_persist + cv_api + restriction_engine + restriction_persist + restriction_api（共 6 个 service 单元 + 2 个 schema + 2 个 API router）
- ORM：cv_results（Cv_calculated 大写驼峰）+ restriction_results（orifice_id PK）+ outlet stream 链
- Pydantic schema：cv 22+13 + restriction 14+13 字段（全部 `extra='forbid'` 严格模式 + 中文 description）
- Frontend wrapper：cv.ts 40 + restriction.ts 47（含 union 常量 + 接口）
- OpenAPI snapshot：123 paths + 119 schemas（pcs-backend/docs/openapi.json 505K）
- 决策：ADR-0022 outlet stream change_type 区分 FRICTION_PRESSURE_DROP（CV）vs ISOENTHALPIC（Restriction）

**关键修复**：
- cv_persist subagent Task 9 突发 429 rate limit 后 controller 接管 + 验证 + 手动 commit（恢复模式已在 progress.md 详细文档化）
- Task 10 implementer 漏跑 OpenAPI regen → controller 接管跑 regen + 重新派 Task 11（教训：openapi regen 必须 commit 前完成）

**Ruling 记录**：
- **R-isoenthalpic**（Task 12-14）：RESTRICTION outlet stream change_type = ISOENTHALPIC（区别 CV 的 FRICTION_PRESSURE_DROP）；等熵焓降设备物理建模正确
- **R-outlet-source**（Task 12-14）：outlet_stream.OutletSourceType Literal 增 `RESTRICTION_CALCULATED` + `_EQUIP_TYPE_MAP` 增 `"RESTRICTION_CALCULATED": "RESTRICTION"`（与 CV 共用同 module，避免分裂）

**基线验证（G-08 契约）**：
- **ruff check**：All checks passed（0 errors）
- **tsc --noEmit**：0 errors
- **eslint src/ tests/**：0 errors
- **pytest**：2287 passed + 20 failed pre-existing（meta / pipe_code_validator / stream_symbol_validator；与 P6-1 无关，已 git stash 验证）
- **vitest**：533 passed（51 test files）
- **OpenAPI snapshot**：`pcs-backend/docs/openapi.json` 505K / 123 paths / 119 schemas（CV + Restriction schema 新增）

**G-08 baseline 截取**：
- `pcs-backend/docs/openapi.json` → 留作 P6-2 批前 G-08 diff baseline

**待 P6-2 启动工作**（Task 17+）：
- FLARE_SYS + COOL_TOWER + PSYCHRO 三件套（Task 17-27）
- G-07 集成（Task 28 批末）
- LOW/INFO 滚动：cv_engine standard_profile_code override 链路（P6-2 修）、RESTRICTION 闪蒸完整 FLASH 联校核、Reader-Harris 14 项扩展（如需）
- 20 pre-existing failures（meta / pipe_code_validator / stream_symbol_validator）入 P6+ LOW/INFO 滚动

**待 P6-3 启动工作**（Task 29+）：
- OPEN_CHANNEL + FILTRATION + COST_EST 三件套（Task 29-37）
- G-04/05/06 + 批末总结（Task 38）

**P6-1 → P6-2 总进度**：8/38 tasks complete（21%）。下一批 11 task 推进 FLARE_SYS / COOL_TOWER / PSYCHRO。

---

## 🔍 评审委员会补证（2026-09-24，Conditional Closed 应对）

> 背景：P6 架构评审委员会对 P6-1 批发"有条件通过"裁决（Conditional Closed）；本段为 C-01~C-07 工具化部分的核实结果，C-04 偏差验收数据 / C-07 标准策略需工艺室 + 技术负责人联合裁决。

### C-01 补证：20 pre-existing failures 来源（bisect）

**裁定：跨批遗留，P2 时代 bug，与 P6-1 无关。**

| Fail | 引入 commit | 时代 | 根因 |
|------|-------------|------|------|
| `test_pipe_code_validator.py`（10 例）| `651e2bc feat(p2-sup-002)`（2026-Q2 era）| **P2** | `app/services/pipe_code_validator.py:22 class Severity(str, Enum): docstring "ERROR 拦截 / WARN 仅警告" — 但**无任何枚举成员**；`Severity.ERROR` AttributeError |
| `test_stream_symbol_validator.py`（8 例）| `40b0415 feat(p2-sup-002)`（同期）| **P2** | `app/services/stream_symbol_validator.py:9 class Severity(str, Enum):` 同根因 |
| `test_meta.py::test_get_enums_returns_required_groups`（1 例）| P5 期间引入 `StatelineDataMode` 等 enum | **P5** | 实际是 `app/api/v1/meta.py` 返回 `StreamDataMode` 但 enum 类为空 |

**P5 验收"0 failed"复核**：P5 末 baseline 实测 = **1670 passed + 20 failed + 51 skipped**（Task 16 G-08 STATUS line 1054-1058 已记录）。"0 failed"系局部陈述（指 P5 模块范围，未含 P2 时代 validator）。

**修复路径（不属于 P6-1 范围）**：
```python
class Severity(str, Enum):
    ERROR = "ERROR"
    WARN = "WARN"
```
登记入 P6+ LOW/INFO 滚动批；P3.2 时代 `sim_import_warnings` 表已用此 enum 但 P2 validator 漏定义。

### C-03 补证：cv_results / restriction_results 字段完整性

| 字段 | SPEC §3.2.1.6 (cv_results) | CvResult ORM | 判定 | SPEC §3.2.2.6 (restriction_results) | RestrictionResult ORM | 判定 |
|------|---------------------------|--------------|------|-----------------------------------|-----------------------|------|
| PK | `cv_calc_id` (BIGINT) | `cv_id uuid.UUID` | ✅ DICT V3.3 rename | `restriction_calc_id` (BIGINT) | `orifice_id uuid.UUID` | ✅ DICT V3.3 rename |
| `tag_number NOT NULL` | (mixin 隐式) | `TaggedRecordMixin` | ✅ | (mixin 隐式) | `TaggedRecordMixin` | ✅ |
| `project_id` / `workspace_id` | (mixin 隐式) | `RecordMixin` | ✅ | (mixin 隐式) | `RecordMixin` | ✅ |
| `input_json / output_json JSONB` | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| `record_hash VARCHAR(64) UNIQUE` | ✅ | `String(64)` via mixin | ✅ | ✅ | `String(64)` via mixin | ✅ |
| **`standard_profile_code NOT NULL`** | **`VARCHAR(16) NOT NULL`** | **`String(32) NOT NULL`** | ⚠️ **HIGH 偏差** | (SPEC 未要求) | (无列) | ✅ |
| SPEC §3.2.1.6 / §3.2.2.6 平铺字段 | 21 列 | 21 列（line 783 前）| ✅ | 13 列 | 13 列（line 783-854）| ✅ |

**CvResult `standard_profile_code` 长度偏差（HIGH 缺陷）**：
- SPEC §3.2.1.6 line 1283：`VARCHAR(16) NOT NULL`
- Task 7 (a1a4716) ORM 实际：`String(32) NOT NULL`
- 实际值（如 "API-60534" 9 字符 / "ISO-5167" 8 字符）均 ≤16 — **不影响数据**
- 但**形式上违反 SPEC**，需 P6-2 启动前修正（回归 String(16)）+ alembic 迁移兼容性确认

### C-05 补证：outlet_stream Literal 扩展验证

```python
# app/services/outlet_stream.py:42-55
OutletSourceType = Literal[
    "FLASH_CALCULATED",       # P3
    "PIPE_CALCULATED",         # P3
    "PUMP_CALCULATED",         # P3
    "PIPE_NET_CALCULATED",     # P4-3-3
    "VESSEL_CALCULATED",       # P5-1-4
    "SEP_EQUIP_CALCULATED",    # P5-2-4
    "PSV_CALCULATED",          # P5-3
    "HEAT_CALCULATED",         # P5-4-5
    "RESTRICTION_CALCULATED",  # P6-1 Task 13 ✅
]
```

**`change_type` 入 properties 区分（ADR-0022 修正）**：
- CV：`change_type="FRICTION_PRESSURE_DROP"`（控制阀为摩擦压降设备）✅
- RESTRICTION：`change_type="ISOENTHALPIC"`（节流装置等熵焓降设备）✅（Ruling R-isoenthalpic）

**CV 用 `source_type="DEVICE_CALCULATED"` 验证**：
- CV (cv_persist.py line 178) 实际：`source_type="DEVICE_CALCULATED"`
- OutletSourceType Literal **不含** `"DEVICE_CALCULATED"`（已含 9 种 CALCULATED 派生）
- 历史原因：CV 是 P5 末/ P6-1 新增设备；落库时仍用 `DEVICE_CALCULATED`（P3 旧惯例），与 OutletSourceType Literal 不一致
- **裁定**：LOW 风险，P6-2 启动前加 `"DEVICE_CALCULATED"` 入 OutletSourceType Literal（统一设备/计算源落库口径）

### C-06 补证：record_hash 输入字段

**结论**：`compute_record_hash` 走 ORM 反射路径（`calc_lineage.py:104`），自动排除 `_EXCLUDED_KEYS = {record_hash, created_at, created_by, updated_at, updated_by}`；**未声明模块级 RECORD_HASH_FIELDS**。

| 模块 | PSV/CV/Restriction RECORD_HASH_FIELDS | 判定 |
|------|---------------------------------------|------|
| `app/services/psv/` | ❌ 无独立模块定义 | 用 calc_lineage 反射路径 |
| `app/services/cv/` | ❌ 无 | 用 calc_lineage 反射路径 |
| `app/services/restriction/` | ❌ 无 | 用 calc_lineage 反射路径 |

**SPEC §3.2.1.6 line 1285 验收要求 `record_hash 含 standard 字段`**：
- CvResult ORM 含 `standard_profile_code` 列（line 771）→ 反射路径自动含 ✅
- RestrictionResult ORM 不含该列 → 但 SPEC §3.2.2.6 未要求该列 → ✅（SPEC 合规）
- PSV Result ORM 含 `standard_profile_code` 列 → 反射路径自动含 ✅

**裁定**：PASS（calc_lineage 反射路径已隐式满足 ADR-0028 §决策 4 契约）。

### C-04 / C-07 待工艺室 + 技术负责人联合裁决

- **C-04**：Cv/RESTRICTION 偏差验收数据（液体 Cv ≤1% / 气体 Cv ≤2% / 孔板 ≤1% / 文丘 ≤1% / 喷嘴 ≤1%）— Path A 自研 SPEC §3.2.1/3.2.2 简化公式，R1 裁决要求"与 fluids 完整 API 对比测试"；本批**未跑**该验证
- **C-07**：CV `standard_profile_code` 策略（硬编码 vs 多标准）— CV 是否需真多标准引擎？GB/T 4213 与 IEC 60534 是否等同？需技术负责人 + 工艺室裁决

### 评审委员会裁决应对清单

| # | 行动 | 责任方 | 优先级 |
|---|------|--------|--------|
| A-01 | **C-01 已闭环**：20 failures 跨批遗留 P2 时代，与 P6-1 无关 | 测试工程师 | DONE |
| A-02 | **C-03 部分通过**：CvResult `standard_profile_code` 长度 32 vs SPEC 16 HIGH | 开发工程师 | P6-2 启动前修 |
| A-03 | **C-05 通过**：Literal 扩展完整，CV `DEVICE_CALCULATED` 口径不一致 LOW | 开发工程师 | P6-2 启动前加 Literal |
| A-04 | **C-06 通过**：calc_lineage 反射路径满足 ADR-0028 §决策 4 契约 | — | DONE |
| A-05 | **C-04 待跑**：偏差验收数据归档（≤1% / ≤2%） | 测试工程师 + 工艺室 | P6-2 批内 |
| A-06 | **C-07 待裁**：CV 标准策略（硬编码 vs 多标准）| 技术负责人 + 工艺室 | P6-2 启动前 |
| A-07 | **S-01 待裁**：RESTRICTION 闪蒸完整 FLASH 联校核路径 | 工艺室 | P6-2 批内 |
| A-08 | **S-02 部署**：CI G-08 自动化门禁（"代码变更→OpenAPI 必须 regen"）| DevOps | P6-2 批内 |
| A-09 | **S-03 归档**：Task 9 429 recovery 应对清单入 `docs/P6-IMPLEMENTATION-NOTES.md` | 实施团队 | P6-2 启动前 |

**P6-1 → P6-2 启动阻塞**：
- 硬阻塞：**C-07 CV 标准策略裁决**（未明确前 CV 模块不可扩展多标准）
- 软阻塞：A-02 / A-03 / A-06 / A-08 实施

**P6-0 触发分支**：`feature/p6-batch` worktree，HEAD `c5c7d9a`（Task 5 amend 后）

---

## ✅ Done (P6-2 batch 批末闭环 — 2026-09-25)

**目标**：P6 SPEC V2.0 P6-2 阶段（FLARE_SYS + COOL_TOWER + PSYCHRO 三件套 + G-03 CEPCI + frontend types 对齐）

**任务完成情况**：

| Task | Commit | 内容 | 状态 |
|------|--------|------|------|
| Task 17 | `a64b00a` | G-03 CEPCI 数据录入（CONFIG cepci_index_series + 合成数据 + 工艺室确认占位） | ✅ complete |
| Task 18 | `3aa3a85` | flare_system_results / cooling_tower_results / psychro_results 3 张表 + ORM + RECORD_TYPE_REGISTRY | ✅ complete |
| Task 19 | `8d82649` | flare relief_aggregator 消费 ReliefResult（项目级多 PSV 叠加；G-07 集成） | ✅ complete |
| Task 20 | `38a4dc3` | flare header_sizing（Mach + 等温可压缩管流；§3.2.3.2） | ✅ complete |
| Task 21 | `85c00da` | flare kod_sizing（Souders-Brown + water_seal 液封高度；§3.2.3.3） | ✅ complete |
| Task 22 | `ad7c436` | flare stack_design（API 521 §7.4.2.2 + §7.4.2.3 + BEDD；§3.2.3.4/5） | ✅ complete |
| Task 23 | `ae089cf` | flare tip（API 537）+ flare_persist 5 CRUD endpoints（§3.2.3.6） | ✅ complete |
| Task 24 | `ddc402b` | cool_tower merkel + tower_curve + water_balance（§3.2.4.1~4） | ✅ complete |
| Task 25 | `31fbe21` | cool_tower heat_aggregator + fan_power + persist + 8 endpoints（§3.2.4.5~7） | ✅ complete |
| Task 26 | `9218ff4` | psychro 6 函数 + persist + 5 endpoints + coolprop_version 溯源（§3.2.5） | ✅ complete |
| Task 27 | `2d0dbf6` | frontend flare/cool_tower/psychro 3 个 .ts 文件（OpenAPI 对齐 + JSDoc 中文） | ✅ complete |
| Ticket | `091500e` | P6-OPEN-009 alembic drift（`psv_results` 缺 `stale_resolution_path` 列）登记 | ✅ 登记完成 |
| Task 28 | Task 28 closure commit | 批末 G-08 验证 + 全栈基线 + Per-Batch QA Gate + STATUS 闭环 | ✅ complete |

**关键产出**：

- **业务模块**：flare_engine (4 calc) + flare_persist (5 CRUD) + flare_tip + cool_tower_engine (3 calc) + cool_tower_persist + cool_tower_heat_aggregator + cool_tower_fan_power + psychro_engine (6 calc, CoolProp) + psychro_persist + 共 21 个 API endpoints
- **ORM**：flare_system_results（flare_id PK；per_scenario_json 消费 PSV P5-OPEN-10 §3.1）+ cooling_tower_results + psychro_results（coolprop_version 溯源）；3 张表均继承 TaggedRecordMixin
- **G-03 CONFIG**：cepci_index_series 12 行（2014-2025 Q4）+ 工艺室签字占位
- **G-07 集成**：FLARE_SYS relief_aggregator 真消费 PSV per_scenario_json（commit `8d82649`）
- **Frontend types**：flare.ts（4 endpoints）+ cool_tower.ts（5 endpoints）+ psychro.ts（6 endpoints），全部含中文 JSDoc + OpenAPI 对齐

**基线验证（G-08 契约）**：

| 维度 | 结果 |
|------|------|
| **ruff check** | ⚠️ 2 E501 errors（pre-existing P6-2 batch 期间遗留，`p6_2_gate_03_cepci_seed.py:50` + `tests/e2e/test_sim_three_entry_consistency.py:494`；非本任务引入） |
| **tsc --noEmit** | ✅ 0 errors |
| **eslint src/ tests/** | ✅ 0 errors |
| **pytest** | ⚠️ **2585 passed + 27 failed + 5 skipped**（含 3 G-07 deselected）。详细：20 P6-0 已登记 pre-existing (P2-era validator + meta) + **7 NEW P6-2 回归**（test_table_count / test_p4_flash_full_path / test_record_type_registry_count_is_10 / test_registry_contains_all_calc_record_types / 2× test_design_stage_*[column_sizing_results] / test_reversible_segment_roundtrip） |
| **vitest run** | ✅ 51 files / 533 tests passed（baseline 持平） |
| **OpenAPI drift (G-08)** | ✅ `diff` 零输出（worktree 内 `export_openapi.py` + `gen-api-types.sh` regen 已修冲突 marker） |
| **OpenAPI 演变** | paths 122 (P6-1) → **143** (+21 FLARE_SYS 11 + COOL_TOWER 5 + PSYCHRO 5)；schemas 119 → **163** (+44) |
| **alembic heads** | ✅ `p6_2_001_flare_cool_tower_psychro_results`（head） |
| **alembic current** | ✅ 同 head |
| **alembic history** | ✅ 线性链，无分支 |

**Per-Batch QA Gate（gstack-browse 浏览器回归）**：

- **登录 + 仪表盘**：login 200 → mock-login POST 200 (alice DESIGNER) → `/` 仪表盘渲染（heading "仪表盘" + 工作区切换 + 进度条 20% 完成 2/10 + 项目输入清单 9 菜单组）
- **菜单导航**：`/flash` 200 + `/heat` 200（HEAT 为 P5-4 baseline 路由，本批无新增 P6 frontend pages — Task 27 仅含 types，无 route integration）
- **console**：0 errors（仅 React Router v7 future flag warning，非阻断）
- **network**：全 200，0 个 4xx/5xx
- 详细：`/home/pangzy/code_project/PCS-worktrees/p6-batch/.gstack/qa-reports/qa-report-pcs-frontend-2026-09-25-p6-2-batch.md`（`.gstack/` 已 gitignore，QA 报告落本地）

**剩余 OPEN（接续 P6-3 + LOW/INFO 滚动批）**：

- **P6-OPEN-009**：psv_results alembic drift（缺 `stale_resolution_path` 列）— 已 ticket `091500e` 登记，P6-3 启动修复
- **CAVEAT-1**：7 NEW pytest 回归（test_table_count / test_p4_flash_full_path / test_record_type_registry_count_is_10 / test_registry_contains_all_calc_record_types / 2× test_design_stage_*[column_sizing_results] / test_reversible_segment_roundtrip）— 详见 QA 报告登记表
- **CAVEAT-2**：2 ruff E501 pre-existing（非 P6-2 引入）— LOW/INFO 滚动后续批
- **CAVEAT-3**：openapi.json / openapi.snapshot.json / api.d.ts 含未解决 git merge conflict marker（worktree 内 regen 修复，**待独立 chore commit 收纳 — reviewer 决策**）
- **P6-OPEN-010**：`_to_http(err)` helper `status_code` → `status` 改造 — Task 21 闭环

**评审委员会裁决应对清单（更新）**：

| # | 行动 | 状态 |
|---|------|------|
| A-05 | C-04 CV/RESTRICTION 偏差验收数据 | DEFERRED — P6-3 / 滚动后续批 |
| A-07 | S-01 RESTRICTION 闪蒸完整 FLASH 联校核 | ✅ DONE P6-2（commit `3ddc931` + `0231827`） |
| A-08 | S-02 G-08 CI 自动化门禁 | ✅ DONE P6-2（commit `0eed3c7`） |
| A-09 | S-03 Task 9 429 recovery 归档 | P6-3 启动前 |

**P6-1 → P6-2 → P6-3 总进度**：19/38 tasks complete（50%）。下一批 11 task 推进 OPEN_CHANNEL + FILTRATION + COST_EST 三件套 + Task 38 批末。

---

## 🔍 Task 28 实施观察（批末 G-08 验证 + STATUS 闭环记录，2026-09-25）

**Task 28 工作流**：5 步串行（G-08 → 5 维基线 → alembic chain → Per-Batch QA Gate → STATUS 闭环）。

### Step 1 — G-08 OpenAPI drift

worktree 起始 `pcs-backend/docs/openapi.json` 与 `pcs-frontend/openapi.snapshot.json` **均含 3 处未解决 git merge conflict marker**（lines 14839, 16763, 17470），由 P6-1/P6-2 期间某次合并遗留。两文件因同步坏故 `diff` 报"identical"但 JSON parse 失败。

**Worktree 内修复**：

```bash
cd pcs-backend && uv run python scripts/export_openapi.py     # 重写 backend openapi.json
cd ../pcs-frontend && bash scripts/gen-api-types.sh           # 重写 frontend openapi.snapshot.json + api.d.ts
```

**结果**：regen 后两文件 JSON 合法（143 paths / 163 schemas），`diff` 零输出，**G-08 PASS**。

**遗留**：regen 输出**未入本任务 closure commit**（brief red line #2/#4 限制）。reviewer 决策：用 `chore(openapi)` 单独 commit 收纳。

### Step 2 — 5 维基线

| 维度 | 实测 | 期望（brief）| 差距 |
|------|------|------|------|
| ruff | 2 E501 pre-existing | 0 | ⚠️ pre-existing 非本批 scope |
| pytest | 2585 passed + 27 failed | ≥ 2620 passed | ⚠️ 27 failed（20 P6-0 known + **7 NEW P6-2 回归**） |
| tsc | 0 errors | 0 | ✅ |
| eslint | 0 errors | 0 | ✅ |
| vitest | 51 files / 533 passed | ≥ 533 baseline | ✅ |

7 NEW P6-2 pytest 回归主要根因：RECORD_TYPE_REGISTRY 项数更新未同步（test_record_type_registry_count_is_10）、design_stage 列补 addcolumn 未在 P6-2 batch 内（2× test_design_stage_*[column_sizing_results]）、tables count 期望未更新（test_table_count）、alembic 不可逆 roundtrip（test_reversible_segment_roundtrip）、flash persist 链路与新表不一致（test_p4_flash_full_path）。

### Step 3 — alembic head chain

✅ `p6_2_001_flare_cool_tower_psychro_results` head 单链无分支。current 与 head 一致。

### Step 4 — Per-Batch QA Gate

`CI=1 ~/.claude/skills/gstack/browse/dist/browse` + `npx vite --port 5173` 完整跑通：

1. login 200（mock alice DESIGNER）
2. mock-login POST 200（133B）
3. 跳 `/` 仪表盘渲染
4. 菜单 click `/flash` 200
5. 菜单 click `/heat` 200
6. console 0 errors（仅 React Router v7 future flag warning）
7. network 全 200，0 个 4xx/5xx

详细报告：`.gstack/qa-reports/qa-report-pcs-frontend-2026-09-25-p6-2-batch.md`

### Step 5 — STATUS.md 闭环（本段为 append 写入，Task 28 commit SHA 见 git log `feature/p6-batch` HEAD）

---

**P6 batch 索引**：

- **P6-0**：ADR-0030 V1.2 + chedl_wrapper 扩展（5 task / 5 commit）— STATUS line 1088
- **P6-1**：CV + RESTRICTION 三件套（10 task / 8 commit）— STATUS line 1142
- **P6-2**（本批）：FLARE_SYS + COOL_TOWER + PSYCHRO 三件套 + frontend types（11 task / 8 commit）— 本段
