---
description: session handoff, regenerate with /handoff when a quest finishes
budget_tokens: 1500
---
# STATUS — PCS

> Read this FIRST when starting a session. Last updated: 2026-09-17.

---

## ✅ Done (P5-OPEN-10 SUP-P5-PSV-002 V1.14 后端契约扩展闭环 — 2026-09-17)

- **10 commits + 30+ 新测试 + 13 PcsError 子类 + 18 列迁移 + 4 阶段 Kb + 6 波纹管矩阵**
  - 落地状态：`spec/SUP-P5-PSV-002-V1.14-STATUS.md`
  - commit 序列：
    `adacd33` cdtp → `25fbf25` bellows_compat → `522f2f2` kb_service →
    `d0aa5eb` exceptions → `f1fcc19` valve_validation → `41442cd` PsvResult ORM →
    `a3e9471` alembic 迁移 → `dcce671` CalculateRequest 扩展 →
    `<task 11>` psv_persist 落库 → `<task 12>` API 集成 + 8 测试
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
  - OPEN-10-3 +50~60 测试余项
  - OPEN-10-4 CRYOGENIC 型号（OPEN-18）/ API 521 FIRE+PILOT 章节号（OPEN-19）
  - OPEN-10-5 65 psig T 孔口 150# 警告（OPEN-20）
  - OPEN-10-6 record_hash 含新字段回归验证

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
1. **ruff 归零专项**：445 → 0（31 fixable + 手工复核），半天
2. **calculate 入口接 Guard**：P4 工艺计算首个端点调
   `UnreliableStreamGuard.check`（422 STREAM_UNRELIABLE_BLOCKED 契约已备 + 测试）
3. **enum 9 态扩展（TODO-036）**：`ALTER TYPE ADD VALUE` 不可逆，迁移前备份
   enum definition
4. **parser 入库链路**：SIM-37b/38b 产出为 dataclass 层，P4 需 import_service
   集成写 sim_tower_results / stream_properties_json
5. 覆盖率 88% → 90%（未覆盖行集中在 api 层 error 分支）

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