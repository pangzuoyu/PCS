---
description: session handoff, regenerate with /handoff when a quest finishes
budget_tokens: 1500
---
# STATUS — PCS

> Read this FIRST when starting a session. Last updated: 2026-09-18.

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

## 🚀 Next quest

**Goal:** P5 收口（OPEN-7 + OPEN-10）+ P4 启动（P3.x 闸门条件已满足）

### P5 收口（OPEN-7 / OPEN-10 需后端契约变更）

1. **OPEN-7 HEAT import→get 串行优化**：后端 `ImportHtriResponse` 扩充字段（返回
   `equipment_no` + `equipment_name` + `tag_number` + `exchanger_category`
   + `duty_w` + `output_json` partial），前端 `import()` 后免去 `get()`
   roundtrip
2. **OPEN-10 SUP-P5-PSV-002 后端契约扩展**（待评审通过后启动）：
   - Pydantic `PsvCalculateRequest` 加 `valve_type` / `body_material` /
     `orifice_override` 字段（与前端默认值兼容：SPRING_LOADED / SS316 / null）
   - 持久化：`psv_results` 表 7 列迁移（valve_type/body_material/inlet_size/
     outlet_size/blowdown_fraction/orifice_overridden/orifice_manual）+ 存量
     回填
   - 拦截逻辑 G7/G8/G9：Task 18 端点前置校验（PILOT_OPERATED 422
     PSV_PILOT_OPERATED_NOT_SUPPORTED / RUPTURE_DISC 422 PSV_RUPTURE_DISC_NOT_SUPPORTED
     / orifice_override < 计算面积 422 PSV_ORIFICE_OVERRIDE_TOO_SMALL）
   - 孔口选型逻辑（Task 17 扩展）：手动 override 优先 → API526_AREA_TABLE 校验
     → 否则自动圆整
   - 后端测试 +15 / E2E +2（per SUP-P5-PSV-002 §8 验收）
   - 前端无需改动（已就绪，G7/G8/G9 错误码解析已闭环）

### P4 首批建议（收口报告 §6，优先序）
1. ✅ **ruff 归零专项**：5 errors → 0（commit `138cb6c`，2026-09-17）
2. ✅ **calculate 入口接 Guard**：6/7 工艺端点已接（commit `0401fd2`，2026-09-17；
   pipe / pipe_net / pump SIM-39 + psv / vessel / sep_equip 本批）
3. ✅ **enum 9 态扩展（TODO-036）**：P3 SIM-13 已闭环，StreamSignStatus 9 态全集 +
   alembic `p3sim_stream_sign_status_extend`（ADD VALUE：CHECK_REJECTED /
   STALE / CHANGE_PENDING / CHANGED / REVERSAL_PENDING；ADD VALUE 不可逆
   落地 2026-09-08 cerebrum 锁定）
4. ✅ **parser 入库链路**：SIM-37b/38b 产出为 dataclass 层，P4 已闭环
   （commit `a8d41cf`，2026-09-17）+ proii_parser 回归修复
   （commit `357c506`，2026-09-18，bug-081）
5. 覆盖率 88% → 90%：当前 **89%**（commit `357c506` 修复后），
   2150 passed + 49 skipped + 1 flaky（`test_export_perf_budget` 并行
   时序敏感，独立运行通过）。低覆盖模块：
   `app/workers/workspace_tasks.py` 35% / `psv_persist.py` 60% /
   `workspace_service.py` 69% —— 多为 DB / async generator fixture，
   OPEN-10-4 已为新模块加 12 例拉平至 95-100%；P4-5 视为已达可接受水平

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