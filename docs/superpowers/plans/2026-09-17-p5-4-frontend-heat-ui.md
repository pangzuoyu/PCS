# P5-4 HEAT 前端 UI 实施计划（V1.3 对齐）

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans。Steps 用 checkbox（`- [ ]`）追踪。
>
> **Plan scope**：P5-4 HEAT 前端 UI 闭环，对齐 SPEC V1.3 §7.11.6 + 后端 OpenAPI（commit 96165e1）。包含 7 task（0 起点冻结 + 1-6 编码）+ 全栈验证 + gstack-qa 必跑。

**Goal:** 把当前 P5-4 后端闭环的 HEAT 计算 3 端点（POST /import-htri / GET /{heat_id} / POST /{heat_id}/weight-estimate）落地为前端 Page：HTRI 文件上传 + result 展示 + outlet HEAT_EXCHANGE + weight-estimate 表单 + 错误 envelope 解析。

**Architecture:** 严格按 SPEC V1.3 §7.11.6 + 后端 `app/api/v1/heat.py` + `heat_persist.py` 契约。前端 4 类组件：(1) `types/heat.ts` 类型对齐 OpenAPI 字段（带 @migrate-when 标注）；(2) `api/heat.ts` API 客户端（FormData multipart + axios，让浏览器自动设置 Content-Type）；(3) `HeatComputePage.tsx` 主 Page（file upload + exchanger_category radio + source_stream_id 可选 + import 按钮 + result 区 + weight-estimate 19 字段 TEMA 表单）；(4) `mocks/handlers.ts` 补 3 HEAT handler 让 MSW 闭环。StateBadge 提前扩 +HEAT（解决 Task 3/4 循环依赖），路由 + 菜单注册。SPEC §12.4 登记 V1.3 修订。

**Tech Stack:** React 18 / TypeScript / Ant Design 5 / axios / zustand / MSW（dev mock）/ vite / vitest。

**Spec:** `docs/PCS-UI-SPEC.md` V1.2 §7.11.5 PSV（commit 7db5ea5，结构对齐基线）+ V1.3 §7.11.6 HEAT（本计划 Task 0 冻结）+ 后端 OpenAPI（`app/api/v1/heat.py` 96165e1）+ `pcs-backend/app/services/heat/heat_persist.py` 96165e1 + ADR-0027 V1.0。

---

## Global Constraints

- **全程中文**；"继续" = 驱动下一 task 不重议
- **每 task 一 commit + 约定式提交 + Co-Authored-By: Claude Code <noreply@anthropic.com>**
- **SPEC 冻结先行**：Task 0 必须独立完成 SPEC §7.11.6 冻结 + §12.4 登记后再启动 Task 1；不先冻结 SPEC 不写代码
- **字段/枚举/权限/错误码** 以 OpenAPI + meta API 为准（与 SPEC 冲突时 OpenAPI 为准）
- **不动后端**（commit 96165e1 已闭环）：仅前端 + mock 补齐 + SPEC 修订
- **不引新依赖**：复用现有 `api/client.ts`（axios + token + 401 兜底）+ `api/psv.ts` 模板
- **不动 MSW core**：复用 `mocks/handlers.ts` 现有 5 OpenAPI + 17+ dev-only handler 模式
- **axios multipart**：不显式设置 Content-Type，让浏览器自动加 boundary（避免后端 multipart 解析失败）
- **PROJECT_ID / WORKSPACE_ID** 走 `constants/env.ts`（commit 1afa756 收口后统一来源；Task 2 前确认 WORKSPACE_ID 已导出）
- **测试覆盖**：每 task ≥1 条真测试（有有效断言，非空壳）；总计 ≥7 条。Task 1 类型测试为编译期检查，不计入覆盖统计
- **gstack-qa 必跑**：Task 7 全栈验证后必须调用 `/qa` skill，记录到 `.gstack/qa-reports/`；CRITICAL 必修，HIGH 登记 backlog

---

## File Structure

### 创建（4 个）
```
pcs-frontend/src/types/heat.ts                                                  # Task 1
pcs-frontend/src/api/heat.ts                                                    # Task 2
pcs-frontend/src/pages/heat/HeatComputePage.tsx                                 # Task 4
docs/superpowers/plans/2026-09-17-p5-4-frontend-heat-ui.md                      # 本文件（已存）
```

### 修改（5 个）
```
docs/PCS-UI-SPEC.md                                                              # Task 0：§7.11.6 冻结 + §12.4 V1.3 登记
docs/P45-BATCH3-TYPE-MIGRATION.md                                                # Task 1：types 迁移登记（@migrate-when 落地）
pcs-frontend/src/components/common/StateBadge.tsx                                # Task 3：扩 +HEAT 4 态
pcs-frontend/src/mocks/handlers.ts                                               # Task 6：补 3 HEAT handler
pcs-frontend/src/pages/routeWrappers.tsx                                         # Task 5：加 HeatRoute
pcs-frontend/src/App.tsx                                                         # Task 5：路由注册
pcs-frontend/src/layouts/MainLayout.tsx                                          # Task 5：菜单注册
```

### 不动（本批次 scope 外）
- `pcs-backend/`（commit 96165e1 闭环）
- `api/client.ts` / `store/auth.ts` / `components/common/PageHeader.tsx`
- `types/api.d.ts`（V1.4 阶段再 regen，本批次用 `@migrate-when` 标注）
- `MainLayout.tsx` 现有 L41-50 psv 等菜单项

---

## Task 0: 后端验证 + SPEC §7.11.6 HEAT 冻结（独立 commit，不写代码）

**Files:**
- Modify: `docs/PCS-UI-SPEC.md`（追加 §7.11.6 + §12.4 V1.3 修订记录）
- Create: `docs/superpowers/plans/2026-09-17-p5-4-spec-freeze-check.md`（本 task 验证记录）

**Step 1: 后端验证 4 项（冻结 SPEC 前必跑）**

```bash
# 1. HEAT 是否有 design_stage BASIC/DETAIL 字段
grep -i design_stage pcs-backend/app/models/calc.py | grep -i heat
grep -i design_stage pcs-backend/app/api/v1/heat.py

# 2. change_type 枚举值（HEAT_CALCULATED / HEAT_EXCHANGE）
grep -r "HEAT_CALCULATED\|HEAT_EXCHANGE" pcs-backend/app/services/heat/

# 3. outlet_stream_name 命名规则
grep -r "outlet_stream_name\|stream_name" pcs-backend/app/services/heat/

# 4. SPEC §7.11.5 PSV 结构（让 §7.11.6 子节对齐）
grep "^###\|^####" docs/PCS-UI-SPEC.md | grep "7.11.5"
```

**预期**：
1. HEAT 无 design_stage（HTRI 导入 = DETAIL 级，无 BASIC 简化模式）→ 计划 Task 1 SPEC 描述保持「单层（无 BASIC/DETAIL）」
2. change_type = `HEAT_EXCHANGE`，source_type = `HEAT_CALCULATED`（与 plan 描述一致）
3. outlet 命名含 `HEAT_EXCHANGE` 后缀
4. §7.11.5 包含子节：设计阶段 / 输入字段 / 输出字段 / Result Tab / 错误码（§7.11.6 子节对齐）

**若 4 项验证结果与预期不一致**：停止推进，报告用户裁决（不得自行修订 SPEC 草稿或绕过验证）。

**Step 2: 在 SPEC §7.11.5 末尾追加 §7.11.6 HEAT 章节**

`docs/PCS-UI-SPEC.md` 在 §7.11.5 PSV 末（按 §7.11.5 子节对齐）追加：

```markdown
7.11.6 HEAT

按 PCS-PLAN-P5-DEVICE-EQUIPMENT.md §419-517 + ADR-0027 V1.0 + 后端 commit 96165e1。

**设计阶段**：单层（无 BASIC/DETAIL 分级；HTRI 导入本身即 DETAIL 级）

**输入（POST /api/v1/heat/import-htri，multipart/form-data）**：

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| file | UploadFile .txt | 是 | HTRI Xist v6.0 输出 |
| project_id | UUID | 是 | 项目 UUID |
| workspace_id | UUID | 是 | 工作区 UUID |
| equipment_no | string | 是 | 设备位号（如 E-201） |
| tag_number | string | 是 | HeatResult.tag_number（NOT NULL 约束） |
| exchanger_category | enum | 是 | SHELL_TUBE / AIR_COOL / PLATE |
| equipment_name | string | 否 | 默认用 htri.case_name |
| source_stream_id | UUID | 否 | 提供则创建 HEAT_CALCULATED outlet stream |

**输出（ImportHtriResponse, 201）**：

| 字段 | 类型 | 说明 |
|---|---|---|
| calc_id | UUID | HeatResult.heat_exchanger_id |
| calc_type | string | 固定 "HEAT" |
| record_hash | string | 16 hex 数值规范化哈希 |
| project_id | UUID | 项目 UUID |
| equipment_no | string | 设备位号 |
| tag_number | string | 业务 tag |
| exchanger_category | enum | SHELL_TUBE / AIR_COOL / PLATE |
| duty_w | float \| null | 热负荷 W（HTRI） |
| outlet_stream_id | UUID \| null | 出口流 UUID（source_stream_id 提供时存在） |
| outlet_stream_name | string \| null | 出口流名称（HEAT_EXCHANGE 后缀） |

**详情（GET /api/v1/heat/{heat_id}, 200 → HeatResultResponse）**：

| 字段 | 类型 | 说明 |
|---|---|---|
| calc_id | UUID | HeatResult.heat_exchanger_id |
| calc_type | string | 固定 "HEAT" |
| project_id | UUID | 项目 UUID |
| workspace_id | UUID | 工作区 UUID |
| tag_number | string | 业务 tag |
| equipment_no | string \| null | 设备位号 |
| equipment_name | string \| null | 设备名 |
| exchanger_category | enum | SHELL_TUBE / AIR_COOL / PLATE |
| duty | float \| null | 热负荷 W（P7 UTIL 消费） |
| record_hash | string \| null | 16 hex 数值规范化哈希 |
| input_json | dict | 原始 HTRI 字段（input_json 双轨） |
| output_json | dict | 计算输出 + total_weight_kg（P7 UTIL 消费） |

**重量估算（POST /api/v1/heat/{heat_id}/weight-estimate, 200 → WeightEstimateResponse）**：

请求体 19 字段 TEMA 9th 表单（必填：tema_type / shell_id_m / shell_length_m / shell_thickness_m；其他默认）：

| 字段 | 默认 | 说明 |
|---|---|---|
| tema_type | 必填 | BEM / AEM / AEL / NEN / BEM_FIXED / AEM_U_TUBE |
| shell_id_m | 必填 | 壳体内径 m |
| shell_length_m | 必填 | 壳体长度 m |
| shell_thickness_m | 必填 | 壳体壁厚 m |
| material | carbon_steel | carbon_steel / SS304 / SS316 / SS316L |
| head_count | 2 | 封头数 |
| head_straight_m | 0.025 | 椭圆封头直边段 m |
| flange_count | 2 | 法兰数 |
| flange_class | 300# | ASME B16.5 Class |
| flange_size_dn | 600 | 法兰 DN |
| nozzle_count | 4 | 管口数 |
| nozzle_size_dn | 100 | 管口 DN |
| saddle_count | 2 | 鞍座数 |
| saddle_size_dn | 600 | 鞍座 DN |
| tube_count | 0 | 管束数 |
| tube_od_m | 0.0 | 管外径 m |
| tube_thickness_m | 0.0 | 管壁厚 m |
| tube_length_m | 0.0 | 管长 m |
| baffle_count | 0 | 折流板数 |
| baffle_diameter_m | 0.0 | 折流板直径 m |
| baffle_thickness_m | 0.0 | 折流板厚 m |

响应 WeightEstimateResponse 含 total_weight_kg + shell_total_kg + 9 段 segments（shell_cylinder/heads/flanges/nozzles/saddles/tube/baffle/channels/shell_total）+ formula_ref。

**Result Tab**：calc_id / record_hash / 设备位号 / tag / 类型 / 热负荷 duty_w / outlet HEAT_CALCULATED / output_json.total_weight_kg。

**错误码**：
- HEAT_INPUT_ERROR 422 — HTRI 解析失败
- HEAT_NOT_FOUND 404 — heat_id 不存在
- HEAT_PROJECT_MISMATCH 422 — 源流 project_id 与 heat 不一致
- SIM_STREAM_NOT_FOUND 404 — 源流 stream_id 不存在

**ACL**：DESIGNER / PROCESS_CONTROLLER / SYSTEM_ADMIN（与 PSV/VESSEL 一致）。
```

**Step 3: §12.4 修订记录追加 V1.3**

```markdown
| V1.3 | 2026-09-17 | P5-4 HEAT 闭环后追加 §7.11.6 HEAT 详细字段章节：输入字段（multipart file + project_id/workspace_id/equipment_no/tag_number/exchanger_category + equipment_name?/source_stream_id?）；输出字段（ImportHtriResponse calc_id/record_hash/duty_w/outlet_stream_id）；GET /heat/{heat_id} 详情（input_json/output_json 双轨 + total_weight_kg 字段可读 P7 UTIL）；POST /heat/{heat_id}/weight-estimate 19 字段 TEMA 9th 表单 + 9 段 segments 拆分（TEMA 5 段壳体 + tube/baffle/channels）；设计阶段单层（无 BASIC/DETAIL 分级）；出口流 source_type=HEAT_CALCULATED + change_type=HEAT_EXCHANGE；错误码 HEAT_INPUT_ERROR / HEAT_NOT_FOUND / HEAT_PROJECT_MISMATCH / SIM_STREAM_NOT_FOUND；ACL DESIGNER/PROCESS_CONTROLLER/SYSTEM_ADMIN（与 PSV/VESSEL 一致） | Claude Code |
```

**Step 4: 验证**

```bash
grep "7.11.6" docs/PCS-UI-SPEC.md                # 章节有匹配
grep "V1.3.*HEAT" docs/PCS-UI-SPEC.md             # §12.4 V1.3 行有匹配
grep -c "^| V1.3" docs/PCS-UI-SPEC.md             # §12.4 V1.3 行计数 ≥1
git diff docs/PCS-UI-SPEC.md | wc -l              # diff 行数 >0
```

**Step 5: Commit**

```bash
cd /home/pangzy/code_project/PCS
git add docs/PCS-UI-SPEC.md
git commit -m "docs(p5-4): SPEC V1.3 §7.11.6 HEAT 冻结 + §12.4 修订登记"
```

---

## Task 1: 新建 `types/heat.ts` 对齐已冻结 SPEC §7.11.6（带 @migrate-when 标注）

**Files:**
- Create: `pcs-frontend/src/types/heat.ts`
- Modify: `docs/P45-BATCH3-TYPE-MIGRATION.md`（若不存在则新建）

**Step 1: 类型对齐 V1.3 §7.11.6 + 后端 OpenAPI（96165e1）**

`pcs-frontend/src/types/heat.ts`：

```ts
/**P5-4 HEAT 计算 + 重量估算 API 客户端类型（V1.3 SPEC §7.11.6）。

按 SPEC V1.3 §7.11.6 + 后端 OpenAPI（commit 96165e1）：
- POST /api/v1/heat/import-htri（multipart/form-data）→ ImportHtriResponse
- GET /api/v1/heat/{heat_id} → HeatResultResponse
- POST /api/v1/heat/{heat_id}/weight-estimate → WeightEstimateResponse

@migrate-when: P5 全栈收口 + openapi-typescript regen 后
@target: src/types/api.d.ts
@reason: 后端 OpenAPI commit 96165e1 已定义 endpoint，但 api.d.ts 未 regen；
        P5-4 frontend 闭环需要类型对齐，临时手写类型待 V1.4 阶段 regen 替换。
*/

// ====== 枚举 ======
export type ExchangerCategory = 'SHELL_TUBE' | 'AIR_COOL' | 'PLATE';

export type TemaType =
  | 'BEM'
  | 'AEM'
  | 'AEL'
  | 'NEN'
  | 'BEM_FIXED'
  | 'AEM_U_TUBE';

export type Material = 'carbon_steel' | 'SS304' | 'SS316' | 'SS316L';

// ====== POST /heat/import-htri（multipart/form-data）======
export interface ImportHtriResponse {
  calc_id: string;                              // UUID
  calc_type: 'HEAT';
  record_hash: string;                          // 16 hex
  project_id: string;                           // UUID
  equipment_no: string;
  tag_number: string;
  exchanger_category: ExchangerCategory;
  duty_w: number | null;
  outlet_stream_id: string | null;              // source_stream_id 提供时存在
  outlet_stream_name: string | null;            // HEAT_EXCHANGE 后缀
}

// ====== GET /heat/{heat_id} ======
export interface HeatResultResponse {
  calc_id: string;
  calc_type: 'HEAT';
  project_id: string;
  workspace_id: string;
  tag_number: string;
  equipment_no: string | null;
  equipment_name: string | null;
  exchanger_category: ExchangerCategory;
  duty: number | null;                          // 热负荷 W（P7 UTIL 消费）
  record_hash: string | null;
  input_json: Record<string, unknown>;
  output_json: Record<string, unknown>;         // 含 total_weight_kg / weight_segments
}

// ====== POST /heat/{heat_id}/weight-estimate ======
export interface WeightEstimateRequest {
  tema_type: TemaType;
  shell_id_m: number;
  shell_length_m: number;
  shell_thickness_m: number;
  material?: Material;
  head_count?: number;
  head_straight_m?: number;
  flange_count?: number;
  flange_class?: string;
  flange_size_dn?: number;
  nozzle_count?: number;
  nozzle_size_dn?: number;
  saddle_count?: number;
  saddle_size_dn?: number;
  tube_count?: number;
  tube_od_m?: number;
  tube_thickness_m?: number;
  tube_length_m?: number;
  baffle_count?: number;
  baffle_diameter_m?: number;
  baffle_thickness_m?: number;
}

export interface WeightSegmentResponse {
  weight_kg: number;
  formula_ref: string;                          // standard + version + clause
}

export interface WeightEstimateResponse {
  calc_id: string;
  total_weight_kg: number;                      // TEMA 9th 5 段 + tube/baffle/channels
  shell_total_kg: number;                       // 壳体 5 段累加
  segments: {
    shell_cylinder: WeightSegmentResponse;
    shell_heads: WeightSegmentResponse;
    shell_flanges: WeightSegmentResponse;
    shell_nozzles: WeightSegmentResponse;
    shell_saddles: WeightSegmentResponse;
    shell_total: WeightSegmentResponse;
    tube: WeightSegmentResponse;
    baffle: WeightSegmentResponse;
    channels: WeightSegmentResponse;
  };
  formula_ref: Record<string, string>;
  record_hash: string;                          // 刷新后
}
```

**Step 2: 登记到 `docs/P45-BATCH3-TYPE-MIGRATION.md`**

```markdown
# P5 frontend 类型手写迁移登记（@migrate-when 落地清单）

| 模块 | 手写文件 | @migrate-when | 后端 OpenAPI | api.d.ts 现状 | 优先级 |
|---|---|---|---|---|---|
| HEAT | src/types/heat.ts | P5 全栈收口 + openapi-typescript regen 后 | commit 96165e1 | 未 regen | V1.4 |

说明：
- 后端 OpenAPI 已定义 HEAT 3 端点，但前端 `api.d.ts` 未 regen（沿用 V1.x baseline）。
- 临时手写 types/heat.ts 解决 P5-4 闭环需求。
- 后续 V1.4 阶段统一 openapi-typescript regen，删除手写 types/heat.ts。
```

若 `docs/P45-BATCH3-TYPE-MIGRATION.md` 不存在则新建；存在则追加 HEAT 行。

**Step 3: 类型测试（编译期检查，运行期单测不计覆盖；Task 1 仅 1 测试 slot）**

`pcs-frontend/tests/types/test_heat.ts` 新建（happy + 编译期类型验证）：

```ts
import { describe, it, expect } from 'vitest';
import type {
  ExchangerCategory,
  TemaType,
  ImportHtriResponse,
  HeatResultResponse,
  WeightEstimateRequest,
  WeightEstimateResponse,
} from '../../src/types/heat';

// Happy：所有类型可构造（编译期 + 运行期）
describe('types/heat.ts 完整字段映射', () => {
  it('ImportHtriResponse 含全部 SPEC §7.11.6 字段', () => {
    const r: ImportHtriResponse = {
      calc_id: '00000000-0000-0000-0000-000000000001',
      calc_type: 'HEAT',
      record_hash: 'b1c2d3e4f5061728',
      project_id: '00000000-0000-0000-0000-000000000002',
      equipment_no: 'E-201',
      tag_number: 'E-201',
      exchanger_category: 'SHELL_TUBE',
      duty_w: 1_000_000,
      outlet_stream_id: '00000000-0000-0000-0000-000000000003',
      outlet_stream_name: 'S-HEAT-201-HEAT_EXCHANGE-A1B2C3',
    };
    expect(r.duty_w).toBe(1_000_000);
  });

  it('HeatResultResponse 含 output_json 双轨（P7 UTIL 消费）', () => {
    const r: HeatResultResponse = {
      calc_id: '00000000-0000-0000-0000-000000000001',
      calc_type: 'HEAT',
      project_id: '00000000-0000-0000-0000-000000000002',
      workspace_id: '00000000-0000-0000-0000-000000000003',
      tag_number: 'E-201',
      equipment_no: 'E-201',
      equipment_name: 'HEAT-E-201',
      exchanger_category: 'SHELL_TUBE',
      duty: 1_000_000,
      record_hash: 'b1c2d3e4f5061728',
      input_json: { duty: 1_000_000 },
      output_json: {
        total_weight_kg: 3056.75,
        weight_segments: { shell_cylinder_kg: 1479.69 },
        weight_formula_ref: { tema_version: 'TEMA 9th Ed.' },
      },
    };
    expect(r.output_json.total_weight_kg).toBe(3056.75);
  });

  it('WeightEstimateResponse 含 9 段 segments（edge case：tube/baffle/channels 0 kg）', () => {
    const r: WeightEstimateResponse = {
      calc_id: '00000000-0000-0000-0000-000000000001',
      total_weight_kg: 2037.49,
      shell_total_kg: 2037.49,
      segments: {
        shell_cylinder: { weight_kg: 1479.69, formula_ref: 'TEMA 9th §4.1.2' },
        shell_heads: { weight_kg: 0, formula_ref: 'TEMA 9th §4.2.1' },
        shell_flanges: { weight_kg: 0, formula_ref: 'ASME B16.5' },
        shell_nozzles: { weight_kg: 0, formula_ref: 'NB/T 47065' },
        shell_saddles: { weight_kg: 0, formula_ref: 'TEMA 9th §6.1' },
        shell_total: { weight_kg: 1479.69, formula_ref: 'sum' },
        tube: { weight_kg: 0, formula_ref: 'TEMA 9th §5.1' },
        baffle: { weight_kg: 0, formula_ref: 'TEMA 9th §5.2' },
        channels: { weight_kg: 0, formula_ref: 'TEMA 9th §5.3' },
      },
      formula_ref: { tema_version: 'TEMA 9th Ed.' },
      record_hash: 'c2d3e4f5061728b1',
    };
    expect(r.segments.tube.weight_kg).toBe(0);
  });
});
```

**Step 4: 验证**

```bash
cd pcs-frontend
npx tsc --noEmit src/types/heat.ts                                # clean
npx vitest run tests/types/test_heat.ts                           # 3 tests pass
grep "HEAT" docs/P45-BATCH3-TYPE-MIGRATION.md                     # HEAT 行有匹配
grep "@migrate-when" src/types/heat.ts                            # 标注有匹配
```

**Step 5: Commit**

```bash
git add pcs-frontend/src/types/heat.ts \
        pcs-frontend/tests/types/test_heat.ts \
        docs/P45-BATCH3-TYPE-MIGRATION.md
git commit -m "feat(p5-4-frontend): types/heat.ts 对齐 V1.3 SPEC §7.11.6 + 迁移标注"
```

---

## Task 2: 新建 `api/heat.ts`（按 psv.ts 模板 + 删显式 Content-Type）

**Files:**
- Create: `pcs-frontend/src/api/heat.ts`
- Create: `pcs-frontend/tests/api/test_heat_api.ts`

**Step 1: Task 2 前确认 WORKSPACE_ID 已收口**

```bash
grep "WORKSPACE_ID" pcs-frontend/src/constants/env.ts            # 期望 ≥1 匹配
grep "export const WORKSPACE_ID" pets-frontend/src/constants/env.ts   # 期望 export
```

若 `constants/env.ts` 未导出 WORKSPACE_ID：先补常量（commit 1afa756 收口范围），再启动 Task 2。

**Step 2: api/heat.ts 实现**

```ts
/**P5-4 HEAT 计算 + 重量估算 API 客户端（V1.3 SPEC §7.11.6）。

按 SPEC V1.3 §7.11.6 + 后端 OpenAPI（commit 96165e1）：
- POST /api/v1/heat/import-htri（multipart/form-data）→ ImportHtriResponse
- GET /api/v1/heat/{heat_id} → HeatResultResponse
- POST /api/v1/heat/{heat_id}/weight-estimate → WeightEstimateResponse

错误通过 PcsError envelope 抛出（code/message/detail/trace_id），
前端 message.error 显示 message 字段，特殊 code 触发定制 UI
（HEAT_INPUT_ERROR → 表单高亮 / SIM_STREAM_NOT_FOUND → 提示重新选源流）。

注意：importHtri 不显式设置 Content-Type，让浏览器自动添加
multipart/form-data; boundary=----WebKitFormBoundary...；
显式设置会导致 axios 不添加 boundary，后端 multipart 解析失败。
*/
import { client } from './client';
import type {
  ImportHtriResponse,
  HeatResultResponse,
  WeightEstimateRequest,
  WeightEstimateResponse,
} from '../types/heat';

export const heatApi = {
  /**POST /api/v1/heat/import-htri（multipart upload）。*/
  importHtri: async (params: {
    file: File;
    project_id: string;
    workspace_id: string;
    equipment_no: string;
    tag_number: string;
    exchanger_category: string;
    equipment_name?: string;
    source_stream_id?: string;
  }): Promise<ImportHtriResponse> => {
    const fd = new FormData();
    fd.append('file', params.file);
    fd.append('project_id', params.project_id);
    fd.append('workspace_id', params.workspace_id);
    fd.append('equipment_no', params.equipment_no);
    fd.append('tag_number', params.tag_number);
    fd.append('exchanger_category', params.exchanger_category);
    if (params.equipment_name) fd.append('equipment_name', params.equipment_name);
    if (params.source_stream_id) fd.append('source_stream_id', params.source_stream_id);
    // 注意：不显式设置 Content-Type，浏览器自动添加 boundary
    const { data } = await client.post('/api/v1/heat/import-htri', fd);
    return data;
  },

  /**GET /api/v1/heat/{heat_id}。*/
  get: async (heat_id: string): Promise<HeatResultResponse> => {
    const { data } = await client.get(`/api/v1/heat/${heat_id}`);
    return data;
  },

  /**POST /api/v1/heat/{heat_id}/weight-estimate。*/
  estimateWeight: async (
    heat_id: string,
    req: WeightEstimateRequest,
  ): Promise<WeightEstimateResponse> => {
    const { data } = await client.post(`/api/v1/heat/${heat_id}/weight-estimate`, req);
    return data;
  },
};
```

**Step 3: 测试 ≥3 条**

`pcs-frontend/tests/api/test_heat_api.ts`：

```ts
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { heatApi } from '../../src/api/heat';

vi.mock('../../src/api/client', () => ({
  client: {
    post: vi.fn(),
    get: vi.fn(),
  },
}));

import { client } from '../../src/api/client';

describe('api/heat.ts 调用契约', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('importHtri 用 FormData 上传，不显式设置 Content-Type（happy）', async () => {
    (client.post as any).mockResolvedValue({
      data: {
        calc_id: '00000000-0000-0000-0000-000000000077',
        calc_type: 'HEAT',
        record_hash: 'b1c2d3e4f5061728',
        project_id: '00000000-0000-0000-0000-000000000001',
        equipment_no: 'E-201',
        tag_number: 'E-201',
        exchanger_category: 'SHELL_TUBE',
        duty_w: 1_000_000,
        outlet_stream_id: '00000000-0000-0000-0000-000000000088',
        outlet_stream_name: 'S-HEAT-201-HEAT_EXCHANGE-A1B2C3',
      },
    });

    const file = new File(['htri content'], 'htri.txt', { type: 'text/plain' });
    const result = await heatApi.importHtri({
      file,
      project_id: '00000000-0000-0000-0000-000000000001',
      workspace_id: '00000000-0000-0000-0000-000000000002',
      equipment_no: 'E-201',
      tag_number: 'E-201',
      exchanger_category: 'SHELL_TUBE',
    });

    expect(client.post).toHaveBeenCalledWith(
      '/api/v1/heat/import-htri',
      expect.any(FormData),
    );
    // 关键断言：第二个参数必须没有显式 headers（即 undefined 或无第三参）
    // 注意：未来 client.post 增加 config 参数时本断言需更新
    expect((client.post as any).mock.calls[0][2]).toBeUndefined();
    expect(result.duty_w).toBe(1_000_000);
  });

  it('get(heat_id) 转发到 GET /api/v1/heat/{heat_id}（happy）', async () => {
    (client.get as any).mockResolvedValue({
      data: { calc_id: 'abc', tag_number: 'E-201' },
    });
    await heatApi.get('abc');
    expect(client.get).toHaveBeenCalledWith('/api/v1/heat/abc');
  });

  it('estimateWeight(heat_id, req) 转发到 POST /api/v1/heat/{heat_id}/weight-estimate（happy）', async () => {
    (client.post as any).mockResolvedValue({
      data: { calc_id: 'abc', total_weight_kg: 3056.75 },
    });
    const req = {
      tema_type: 'BEM' as const,
      shell_id_m: 1.0,
      shell_length_m: 5.0,
      shell_thickness_m: 0.012,
    };
    await heatApi.estimateWeight('abc', req);
    expect(client.post).toHaveBeenCalledWith(
      '/api/v1/heat/abc/weight-estimate',
      req,
    );
  });
});
```

**Step 4: 验证**

```bash
cd pcs-frontend
npx tsc --noEmit src/api/heat.ts                                  # clean
npx vitest run tests/api/test_heat_api.ts                         # 3 tests pass
grep "Content-Type" src/api/heat.ts | grep -i multipart              # 期望 0 匹配（无显式 headers）
```

**Step 5: Commit**

```bash
git add pcs-frontend/src/api/heat.ts pcs-frontend/tests/api/test_heat_api.ts
git commit -m "feat(p5-4-frontend): api/heat.ts HEAT 计算 + 重量估算 API 客户端（axios 让浏览器自动 Content-Type）"
```

---

## Task 3: StateBadge 扩 +HEAT（提前到编码前避免循环依赖）

**Files:**
- Modify: `pcs-frontend/src/components/common/StateBadge.tsx`

**Step 1: 联合类型 + MODULE_ACTIVATED 扩展**

`StateBadge.tsx` L19-22 联合类型加 `'HEAT'`；L59-76 `MODULE_ACTIVATED` Record 加 `HEAT` 4 态子集：

```ts
// L19-22 联合类型
export type ModuleName = 'VESSEL' | 'SEP_EQUIP' | 'PSV' | 'HEAT';

// L59-76 MODULE_ACTIVATED Record
export const MODULE_ACTIVATED = {
  VESSEL: ['DRAFT', 'IN_APPROVAL', 'CHECKED', 'CHECK_REJECTED'],
  SEP_EQUIP: ['DRAFT', 'IN_APPROVAL', 'CHECKED', 'CHECK_REJECTED'],
  PSV: ['DRAFT', 'IN_APPROVAL', 'CHECKED', 'CHECK_REJECTED'],
  HEAT: ['DRAFT', 'IN_APPROVAL', 'CHECKED', 'CHECK_REJECTED'],
} as const;
```

**Step 2: 测试 ≥3 条（happy + error + edge case）**

`pcs-frontend/tests/components/test_state_badge_heat.ts`：

```ts
import { describe, it, expect } from 'vitest';
import { render } from '@testing-library/react';
import { StateBadge, MODULE_ACTIVATED } from '../../src/components/common/StateBadge';

describe('StateBadge HEAT 扩展', () => {
  it('HEAT 模块渲染 DRAFT 状态（happy）', () => {
    const { container } = render(<StateBadge module="HEAT" status="DRAFT" />);
    expect(container.textContent).toContain('DRAFT');
  });

  it('HEAT 模块 4 态子集完整（V1.3 §7.11.6）', () => {
    expect(MODULE_ACTIVATED.HEAT).toEqual([
      'DRAFT', 'IN_APPROVAL', 'CHECKED', 'CHECK_REJECTED',
    ]);
  });

  it('HEAT 模块 CHECKED 状态可渲染（edge case：CHECKED 是最终态）', () => {
    const { container } = render(<StateBadge module="HEAT" status="CHECKED" />);
    expect(container.textContent).toContain('CHECKED');
  });
});
```

**Step 3: 验证**

```bash
cd pcs-frontend
npx tsc --noEmit src/components/common/StateBadge.tsx              # clean
npx vitest run tests/components/test_state_badge_heat.ts            # 3 tests pass
grep -c "HEAT" src/components/common/StateBadge.tsx                # 期望 ≥2（联合类型 + MODULE_ACTIVATED）
```

**Step 4: Commit**

```bash
git add pcs-frontend/src/components/common/StateBadge.tsx \
        pcs-frontend/tests/components/test_state_badge_heat.ts
git commit -m "feat(p5-4-frontend): StateBadge +HEAT 4 态子集（提前扩避免循环依赖）"
```

---

## Task 4: 新建 `HeatComputePage.tsx`（HTRI 文件上传 + result + weight-estimate 表单 + outlet + error）

**Files:**
- Create: `pcs-frontend/src/pages/heat/HeatComputePage.tsx`
- Create: `pcs-frontend/tests/pages/heat/test_heat_compute_page.tsx`

**Step 1: 设计要点**

| 子模块 | 设计 |
|---|---|
| **PageHeader** | `<PageHeader title="换热器计算" module="HEAT" actions={[<刷新>]} />` |
| **Import 区** | Upload .txt + Form（equipment_no/tag_number/exchanger_category radio/source_stream_id Input 可选）+ `<Button type="primary">导入 HTRI</Button>` |
| **Result 区** | 卡片：calc_id / record_hash / duty_w / outlet HEAT_CALCULATED / output_json.total_weight_kg（Alert）/ input_json + output_json |
| **Weight-Estimate 区** | 折叠面板 `<Collapse>`：19 字段 TEMA 9th 表单 + `<Button>估算重量</Button>` + 9 段 segments 表格 + formula_ref |
| **错误处理** | `extractPcsError` 助手 + code 分支：HEAT_INPUT_ERROR / HEAT_NOT_FOUND / SIM_STREAM_NOT_FOUND / HEAT_PROJECT_MISMATCH |
| **Loading** | `Spin` 包整个 Page |

**Step 2: 关键代码（按 VESSEL/SEP_EQUIP Page 风格）**

```tsx
import { useState } from 'react';
import { Upload, Form, Radio, InputNumber, Input, Button, message, Card, Tag, Collapse, Spin, Alert, Descriptions, Table } from 'antd';
import { UploadOutlined } from '@ant-design/icons';
import { heatApi } from '../../api/heat';
import type { ImportHtriResponse, HeatResultResponse, WeightEstimateResponse } from '../../types/heat';
import { PageHeader } from '../../components/common/PageHeader';
import { StateBadge } from '../../components/common/StateBadge';
import { PROJECT_ID, WORKSPACE_ID } from '../../constants/env';

const EXCHANGER_CATEGORY_OPTIONS = [
  { label: 'SHELL_TUBE（管壳式）', value: 'SHELL_TUBE' },
  { label: 'AIR_COOL（空冷）', value: 'AIR_COOL' },
  { label: 'PLATE（板式）', value: 'PLATE' },
];

const TEMA_OPTIONS = [
  { label: 'BEM', value: 'BEM' },
  { label: 'AEM', value: 'AEM' },
  { label: 'AEL', value: 'AEL' },
  { label: 'NEN', value: 'NEN' },
  { label: 'BEM_FIXED', value: 'BEM_FIXED' },
  { label: 'AEM_U_TUBE', value: 'AEM_U_TUBE' },
];

interface PcsError { code: string | null; message: string; }

function extractPcsError(err: unknown): PcsError {
  const ax = err as { response?: { data?: any }; message?: string };
  const data = ax?.response?.data;
  return {
    code: data?.code ?? null,
    message: data?.message ?? ax?.message ?? '未知错误',
  };
}

export function HeatComputePage(): JSX.Element {
  const [importFile, setImportFile] = useState<File | null>(null);
  const [importForm] = Form.useForm();
  const [weightForm] = Form.useForm();
  const [importing, setImporting] = useState(false);
  const [estimating, setEstimating] = useState(false);
  const [importResult, setImportResult] = useState<ImportHtriResponse | null>(null);
  const [heatDetail, setHeatDetail] = useState<HeatResultResponse | null>(null);
  const [weightResult, setWeightResult] = useState<WeightEstimateResponse | null>(null);

  const onImport = async () => {
    if (!importFile) {
      message.warning('请先选择 HTRI 文件');
      return;
    }
    const values = await importForm.validateFields();
    setImporting(true);
    try {
      const resp = await heatApi.importHtri({
        file: importFile,
        project_id: PROJECT_ID,
        workspace_id: WORKSPACE_ID,
        equipment_no: values.equipment_no,
        tag_number: values.tag_number,
        exchanger_category: values.exchanger_category,
        source_stream_id: values.source_stream_id || undefined,
      });
      setImportResult(resp);
      const detail = await heatApi.get(resp.calc_id);
      setHeatDetail(detail);
      message.success(`HEAT 导入完成：record_hash=${resp.record_hash}`);
    } catch (err) {
      const env = extractPcsError(err);
      const code = env.code ?? '';
      if (code === 'HEAT_INPUT_ERROR') message.error(`HTRI 解析失败：${env.message}`);
      else if (code === 'SIM_STREAM_NOT_FOUND') message.error('源流不存在，请重新选择');
      else if (code === 'HEAT_PROJECT_MISMATCH') message.error('源流与项目不一致');
      else message.error(env.message);
    } finally {
      setImporting(false);
    }
  };

  const onEstimateWeight = async () => {
    if (!heatDetail) {
      message.warning('请先导入 HTRI 文件');
      return;
    }
    const values = await weightForm.validateFields();
    setEstimating(true);
    try {
      const resp = await heatApi.estimateWeight(heatDetail.calc_id, values);
      setWeightResult(resp);
      const refreshed = await heatApi.get(heatDetail.calc_id);
      setHeatDetail(refreshed);
      message.success(`重量估算完成：total=${resp.total_weight_kg.toFixed(1)} kg`);
    } catch (err) {
      const env = extractPcsError(err);
      if (env.code === 'HEAT_NOT_FOUND') message.error('换热器记录不存在');
      else message.error(env.message);
    } finally {
      setEstimating(false);
    }
  };

  return (
    <Spin spinning={importing || estimating}>
      <PageHeader title="换热器计算" module="HEAT" />
      <Card title="导入 HTRI 文件" style={{ marginBottom: 16 }}>
        <Upload
          beforeUpload={(f) => { setImportFile(f); return false; }}
          accept=".txt"
          maxCount={1}
          fileList={importFile ? [{ uid: '-1', name: importFile.name, status: 'done' }] : []}
          onRemove={() => setImportFile(null)}
        >
          <Button icon={<UploadOutlined />}>选择 HTRI .txt</Button>
        </Upload>
        <Form form={importForm} layout="inline" style={{ marginTop: 16 }}>
          <Form.Item name="equipment_no" label="设备位号" rules={[{ required: true }]}>
            <Input placeholder="E-201" />
          </Form.Item>
          <Form.Item name="tag_number" label="业务 tag" rules={[{ required: true }]}>
            <Input placeholder="E-201" />
          </Form.Item>
          <Form.Item name="exchanger_category" label="类型" rules={[{ required: true }]}>
            <Radio.Group options={EXCHANGER_CATEGORY_OPTIONS} optionType="button" />
          </Form.Item>
          <Form.Item name="source_stream_id" label="源流（可选）">
            {/* TODO: 接入 streams 列表后改为 Select */}
            <Input placeholder="UUID（可选；提供则创建 HEAT_EXCHANGE outlet）" />
          </Form.Item>
          <Form.Item>
            <Button type="primary" onClick={onImport} loading={importing}>导入 HTRI</Button>
          </Form.Item>
        </Form>
      </Card>

      {heatDetail && (
        <Card
          title="计算结果"
          extra={<StateBadge module="HEAT" status="DRAFT" />}
          style={{ marginBottom: 16 }}
        >
          <Descriptions column={2} bordered size="small">
            <Descriptions.Item label="calc_id"><code>{heatDetail.calc_id}</code></Descriptions.Item>
            <Descriptions.Item label="record_hash"><code>{heatDetail.record_hash}</code></Descriptions.Item>
            <Descriptions.Item label="设备位号">{heatDetail.equipment_no}</Descriptions.Item>
            <Descriptions.Item label="业务 tag">{heatDetail.tag_number}</Descriptions.Item>
            <Descriptions.Item label="类型">{heatDetail.exchanger_category}</Descriptions.Item>
            <Descriptions.Item label="热负荷 duty (W)">
              {heatDetail.duty?.toFixed(0) ?? '—'}
            </Descriptions.Item>
          </Descriptions>
          {heatDetail.output_json && 'total_weight_kg' in heatDetail.output_json && (
            <Alert
              type="info"
              showIcon
              message={`P7 UTIL 总重：${(heatDetail.output_json.total_weight_kg as number).toFixed(1)} kg`}
              style={{ marginTop: 12 }}
            />
          )}
          {importResult?.outlet_stream_id && (
            <Card type="inner" title="出口流（HEAT_CALCULATED）" style={{ marginTop: 12 }}>
              <Tag color="default">DRAFT</Tag>
              <Tag color="blue">source_type: HEAT_CALCULATED</Tag>
              <Tag color="cyan">change_type: HEAT_EXCHANGE</Tag>
              <div>Stream ID: <code>{importResult.outlet_stream_id}</code></div>
              <div>Name: {importResult.outlet_stream_name}</div>
            </Card>
          )}
        </Card>
      )}

      {heatDetail && (
        <Collapse>
          <Collapse.Panel header="TEMA 9th 重量估算（点击展开）" key="weight">
            <Form form={weightForm} layout="vertical">
              <Form.Item name="tema_type" label="TEMA 类型" rules={[{ required: true }]}>
                <Radio.Group optionType="button" options={TEMA_OPTIONS} />
              </Form.Item>
              <Form.Item name="shell_id_m" label="壳体内径 m" rules={[{ required: true }]}>
                <InputNumber min={0} step={0.01} style={{ width: 200 }} />
              </Form.Item>
              <Form.Item name="shell_length_m" label="壳体长度 m" rules={[{ required: true }]}>
                <InputNumber min={0} step={0.01} style={{ width: 200 }} />
              </Form.Item>
              <Form.Item name="shell_thickness_m" label="壳体壁厚 m" rules={[{ required: true }]}>
                <InputNumber min={0} step={0.001} style={{ width: 200 }} />
              </Form.Item>
              <Button type="primary" onClick={onEstimateWeight} loading={estimating}>
                估算重量
              </Button>
            </Form>
            {weightResult && (
              <Card type="inner" title="重量结果" style={{ marginTop: 12 }}>
                <Descriptions column={2} bordered size="small">
                  <Descriptions.Item label="总重 (kg)">
                    {weightResult.total_weight_kg.toFixed(1)}
                  </Descriptions.Item>
                  <Descriptions.Item label="壳体总重 (kg)">
                    {weightResult.shell_total_kg.toFixed(1)}
                  </Descriptions.Item>
                </Descriptions>
                <Table
                  dataSource={Object.entries(weightResult.segments).map(([k, v]) => ({
                    key: k,
                    segment: k,
                    weight_kg: v.weight_kg,
                    formula_ref: v.formula_ref,
                  }))}
                  columns={[
                    { title: '段', dataIndex: 'segment', key: 'segment' },
                    { title: '重量 (kg)', dataIndex: 'weight_kg', key: 'weight_kg',
                      render: (v: number) => v.toFixed(2) },
                    { title: '公式来源', dataIndex: 'formula_ref', key: 'formula_ref' },
                  ]}
                  pagination={false}
                  size="small"
                  style={{ marginTop: 12 }}
                />
                <div style={{ marginTop: 8 }}>
                  <strong>formula_ref:</strong> {JSON.stringify(weightResult.formula_ref)}
                </div>
              </Card>
            )}
          </Collapse.Panel>
        </Collapse>
      )}
    </Spin>
  );
}
```

**Step 3: 测试 ≥3 条**

`pcs-frontend/tests/pages/heat/test_heat_compute_page.tsx`：

```tsx
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { HeatComputePage } from '../../../src/pages/heat/HeatComputePage';
import { heatApi } from '../../../src/api/heat';

vi.mock('../../../src/api/heat', () => ({
  heatApi: {
    importHtri: vi.fn(),
    get: vi.fn(),
    estimateWeight: vi.fn(),
  },
}));

vi.mock('../../../src/constants/env', () => ({
  PROJECT_ID: '00000000-0000-0000-0000-000000000001',
  WORKSPACE_ID: '00000000-0000-0000-0000-000000000002',
}));

describe('HeatComputePage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('渲染 PageHeader + 导入 HTRI 区（happy）', () => {
    render(<HeatComputePage />);
    expect(screen.getByText('换热器计算')).toBeTruthy();
    expect(screen.getByText('选择 HTRI .txt')).toBeTruthy();
    expect(screen.getByText('导入 HTRI')).toBeTruthy();
  });

  it('heatApi.importHtri 失败 → 错误提示 HEAT_INPUT_ERROR（error）', async () => {
    (heatApi.importHtri as any).mockRejectedValue({
      response: { data: { code: 'HEAT_INPUT_ERROR', message: 'HTRI 解析失败' } },
    });
    const { container } = render(<HeatComputePage />);
    // 选文件：直接调 setImportFile via beforeUpload 回调（Upload 受控）
    const file = new File(['htri'], 'htri.txt', { type: 'text/plain' });
    fireEvent.change(container.querySelector('input[type="file"]')!, { target: { files: [file] } });
    // 填表 + 提交
    fireEvent.click(screen.getByText('导入 HTRI'));
    await waitFor(() => {
      expect(heatApi.importHtri).toHaveBeenCalled();
    });
    // message.error 文案包含「HTRI 解析失败」
    await waitFor(() => {
      expect(document.body.textContent).toContain('HTRI 解析失败');
    });
  });

  it('未选文件提交 → 提示「请先选择 HTRI 文件」（edge case）', async () => {
    render(<HeatComputePage />);
    const button = screen.getByText('导入 HTRI');
    fireEvent.click(button);
    await waitFor(() => {
      expect(heatApi.importHtri).not.toHaveBeenCalled();
    });
  });
});
```

**Step 4: 验证**

```bash
cd pcs-frontend
npx tsc --noEmit src/pages/heat/HeatComputePage.tsx                 # clean
npx vitest run tests/pages/heat/test_heat_compute_page.tsx          # 3 tests pass
npx eslint src/pages/heat/HeatComputePage.tsx                        # clean
```

**Step 5: Commit**

```bash
git add pcs-frontend/src/pages/heat/HeatComputePage.tsx \
        pcs-frontend/tests/pages/heat/test_heat_compute_page.tsx
git commit -m "feat(p5-4-frontend): HeatComputePage 对齐 V1.3 SPEC §7.11.6（3 端点 + outlet + error）"
```

---

## Task 5: 路由注册 + 菜单

**Files:**
- Modify: `pcs-frontend/src/pages/routeWrappers.tsx`
- Modify: `pcs-frontend/src/App.tsx`
- Modify: `pcs-frontend/src/layouts/MainLayout.tsx`

**Step 1: routeWrappers.tsx 加 HeatRoute**

```tsx
import { HeatComputePage } from './heat/HeatComputePage';

export function HeatRoute(): JSX.Element {
  return <HeatComputePage />;
}
```

**Step 2: App.tsx 路由注册**

`<Routes>` 列表加 `{ path: 'heat', element: <HeatRoute /> },`（仿 psv 路由位置）。

**Step 3: MainLayout.tsx 菜单注册**

calc menu group 加 `{ key: '/heat', icon: <... />, label: <Link to="/heat">换热器</Link> },`（仿 psv 菜单项位置）。

**Step 4: 测试 ≥3 条**

`pcs-frontend/tests/test_routing_heat.tsx`：

```tsx
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { HeatRoute } from '../src/pages/routeWrappers';

describe('HEAT 路由注册', () => {
  it('path="/heat" 渲染 HeatComputePage（happy）', () => {
    render(
      <MemoryRouter initialEntries={['/heat']}>
        <Routes>
          <Route path="/heat" element={<HeatRoute />} />
        </Routes>
      </MemoryRouter>,
    );
    expect(screen.getByText('换热器计算')).toBeTruthy();
  });

  it('HeatRoute 不抛出未捕获错误（error：避免崩溃路由）', () => {
    expect(() => render(
      <MemoryRouter initialEntries={['/heat']}>
        <Routes>
          <Route path="/heat" element={<HeatRoute />} />
        </Routes>
      </MemoryRouter>,
    )).not.toThrow();
  });

  it('MainLayout 菜单包含 /heat 项（edge case：避免路由可达但菜单隐藏）', async () => {
    const { default: MainLayout } = await import('../../src/layouts/MainLayout');
    render(
      <MemoryRouter initialEntries={['/dashboard']}>
        <MainLayout />
      </MemoryRouter>,
    );
    // 菜单项含「换热器」+ Link href="/heat"
    await waitFor(() => {
      const link = document.querySelector('a[href="/heat"]');
      expect(link?.textContent).toContain('换热器');
    });
  });
});
```

**Step 5: 验证**

```bash
cd pcs-frontend
npx tsc --noEmit src/App.tsx src/layouts/MainLayout.tsx src/pages/routeWrappers.tsx   # clean
npx vitest run tests/test_routing_heat.tsx                                            # 3 tests pass
grep "'heat'" src/App.tsx                                                              # 路由注册 1 行
grep "'/heat'" src/layouts/MainLayout.tsx                                              # 菜单注册 1 行
grep "HeatRoute" src/pages/routeWrappers.tsx                                           # wrapper 引用
```

**Step 6: Commit**

```bash
git add pcs-frontend/src/pages/routeWrappers.tsx \
        pcs-frontend/src/App.tsx \
        pcs-frontend/src/layouts/MainLayout.tsx \
        pcs-frontend/tests/test_routing_heat.tsx
git commit -m "feat(p5-4-frontend): 路由 + 菜单注册（换热器）"
```

---

## Task 6: `mocks/handlers.ts` 补 HEAT 端点（3 handler）

**Files:**
- Modify: `pcs-frontend/src/mocks/handlers.ts`

**Step 1: 新增 3 handler**

| Method | Path | 返回 |
|---|---|---|
| POST | `/api/v1/heat/import-htri` | 201 + mockHeatImportResult |
| GET | `/api/v1/heat/:heat_id` | 200 + mockHeatDetail 或 404 envelope（HEAT_NOT_FOUND） |
| POST | `/api/v1/heat/:heat_id/weight-estimate` | 200 + mockWeightResult |

**Step 2: 关键 handler 代码**

`handlers.ts` 增在 devOnlyMockHandlers 数组内：

```ts
// ====== P5-4 HEAT handlers（mock）=====

const HEAT_MOCK_HEAT_ID = '00000000-0000-0000-0000-000000000077';
const HEAT_MOCK_OUTLET_ID = '00000000-0000-0000-0000-000000000088';
const HEAT_MOCK_TAG = 'E-201';

const mockHeatImportResult = {
  calc_id: HEAT_MOCK_HEAT_ID,
  calc_type: 'HEAT',
  record_hash: 'b1c2d3e4f5061728',
  project_id: '00000000-0000-0000-0000-000000000001',
  equipment_no: HEAT_MOCK_TAG,
  tag_number: HEAT_MOCK_TAG,
  exchanger_category: 'SHELL_TUBE',
  duty_w: 1_000_000.0,
  outlet_stream_id: HEAT_MOCK_OUTLET_ID,
  outlet_stream_name: 'S-HEAT-201-HEAT_EXCHANGE-A1B2C3',
};

const mockHeatDetail = {
  calc_id: HEAT_MOCK_HEAT_ID,
  calc_type: 'HEAT',
  project_id: '00000000-0000-0000-0000-000000000001',
  workspace_id: '00000000-0000-0000-0000-000000000002',
  tag_number: HEAT_MOCK_TAG,
  equipment_no: HEAT_MOCK_TAG,
  equipment_name: 'HEAT-E-201',
  exchanger_category: 'SHELL_TUBE',
  duty: 1_000_000.0,
  record_hash: 'b1c2d3e4f5061728',
  input_json: { duty: 1_000_000, tube_count: 150, shell_id: 600 },
  output_json: {
    total_weight_kg: 3056.75,
    weight_segments: {
      shell_cylinder_kg: 1479.69,
      shell_heads_kg: 357.80,
      shell_flanges_kg: 50.00,
      shell_nozzles_kg: 50.00,
      shell_saddles_kg: 100.00,
      shell_total_kg: 2037.49,
      tube_kg: 800.00,
      baffle_kg: 150.00,
      channels_kg: 69.26,
    },
    weight_formula_ref: { tema_version: 'TEMA 9th Ed.' },
  },
};

const mockWeightResult = {
  calc_id: HEAT_MOCK_HEAT_ID,
  total_weight_kg: 3056.75,
  shell_total_kg: 2037.49,
  segments: {
    shell_cylinder: { weight_kg: 1479.69, formula_ref: 'TEMA 9th §4.1.2' },
    shell_heads: { weight_kg: 357.80, formula_ref: 'TEMA 9th §4.2.1' },
    shell_flanges: { weight_kg: 50.00, formula_ref: 'ASME B16.5' },
    shell_nozzles: { weight_kg: 50.00, formula_ref: 'NB/T 47065' },
    shell_saddles: { weight_kg: 100.00, formula_ref: 'TEMA 9th §6.1' },
    shell_total: { weight_kg: 2037.49, formula_ref: 'sum' },
    tube: { weight_kg: 800.00, formula_ref: 'TEMA 9th §5.1' },
    baffle: { weight_kg: 150.00, formula_ref: 'TEMA 9th §5.2' },
    channels: { weight_kg: 69.26, formula_ref: 'TEMA 9th §5.3' },
  },
  formula_ref: { tema_version: 'TEMA 9th Ed.' },
  record_hash: 'c2d3e4f5061728b1',
};

http.post('/api/v1/heat/import-htri', async () =>
  HttpResponse.json(mockHeatImportResult, { status: 201 }),
),

http.get('/api/v1/heat/:heat_id', async ({ params }) => {
  if (params.heat_id === HEAT_MOCK_HEAT_ID) {
    return HttpResponse.json(mockHeatDetail, { status: 200 });
  }
  return HttpResponse.json(
    { code: 'HEAT_NOT_FOUND', message: '换热器记录不存在', detail: null, trace_id: '' },
    { status: 404 },
  );
}),

http.post('/api/v1/heat/:heat_id/weight-estimate', async () =>
  HttpResponse.json(mockWeightResult, { status: 200 }),
),
```

**Step 3: 测试 ≥3 条（用 msw/node setupServer 真跑 handler）**

`pcs-frontend/tests/mocks/test_heat_handlers.ts`：

```ts
import { describe, it, expect, beforeAll, afterEach, afterAll } from 'vitest';
import { setupServer } from 'msw/node';

// 直接从 mocks/handlers.ts 拉取 HEAT 3 handler 数组
import { devOnlyMockHandlers } from '../../src/mocks/handlers';

const HEAT_HANDLERS = devOnlyMockHandlers.filter(
  (h: any) => h.info?.path?.includes?.('/heat/') || h.info?.path?.includes?.('/heat'),
);

const server = setupServer(...HEAT_HANDLERS);

describe('HEAT mock handlers (msw/node)', () => {
  beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
  afterEach(() => server.resetHandlers());
  afterAll(() => server.close());

  it('POST /api/v1/heat/import-htri 返回 201 + ImportHtriResponse 字段（happy）', async () => {
    const r = await fetch('http://localhost/api/v1/heat/import-htri', { method: 'POST' });
    expect(r.status).toBe(201);
    const body = await r.json();
    expect(body.calc_type).toBe('HEAT');
    expect(body.record_hash).toMatch(/^[0-9a-f]{16}$/);
    expect(body.exchanger_category).toBe('SHELL_TUBE');
    expect(typeof body.duty_w).toBe('number');
  });

  it('GET /api/v1/heat/{HEAT_MOCK_HEAT_ID} 返回 200 + HeatResultResponse 字段（happy + 已知 heat_id）', async () => {
    const HEAT_MOCK_HEAT_ID = '00000000-0000-0000-0000-000000000077';
    const r = await fetch(`http://localhost/api/v1/heat/${HEAT_MOCK_HEAT_ID}`);
    expect(r.status).toBe(200);
    const body = await r.json();
    expect(body.calc_id).toBe(HEAT_MOCK_HEAT_ID);
    expect(body.exchanger_category).toBe('SHELL_TUBE');
    expect(body.output_json.total_weight_kg).toBeGreaterThan(0);
  });

  it('GET /api/v1/heat/{unknown} 返回 404 envelope code=HEAT_NOT_FOUND（edge case）', async () => {
    const r = await fetch('http://localhost/api/v1/heat/99999999-9999-9999-9999-999999999999');
    expect(r.status).toBe(404);
    const body = await r.json();
    expect(body.code).toBe('HEAT_NOT_FOUND');
  });
});
```

注：msw/node 集成测试需 msw ≥2.0 + setupServer API；filter 逻辑适配实际 handlers 导出结构（按需调整）。

```bash
grep -c "heat/import-htri" src/mocks/handlers.ts       # ≥1
grep -c "heat/:heat_id" src/mocks/handlers.ts            # ≥2（GET + POST）
grep -c "HEAT_NOT_FOUND" src/mocks/handlers.ts           # ≥1
```

**Step 4: 验证**

```bash
cd pcs-frontend
npx tsc --noEmit src/mocks/handlers.ts                          # clean
npx vitest run tests/mocks/test_heat_handlers.ts                # 3 tests pass（或 grep 验证）
grep -c "heat/import-htri" src/mocks/handlers.ts                # ≥1
grep -c "heat/:heat_id" src/mocks/handlers.ts                   # ≥2
```

**Step 5: Commit**

```bash
git add pcs-frontend/src/mocks/handlers.ts \
        pcs-frontend/tests/mocks/test_heat_handlers.ts
git commit -m "feat(p5-4-frontend): MSW handlers 补 HEAT 端点（import-htri + get + weight-estimate）"
```

---

## Task 7: 全栈基线验证 + gstack-qa 必跑

**Files:** 无新增

**Step 1: tsc + eslint + vitest baseline**

```bash
cd pcs-frontend
npx tsc --noEmit                                                # 期望 clean
npx eslint src/ tests/                                          # 期望 clean
npx vitest run                                                  # 期望 ≥ 7 baseline（7 真测试；Task 1 类型测试不计）
```

**Step 2: 手测 dev server**

```bash
cd pcs-frontend && npm run dev   # vite → http://localhost:5173
```

- 浏览器登录 → 菜单"工艺计算" → "换热器" → 上传 HTRI .txt → 提交 → result 展示 calc_id/record_hash/duty_w + outlet HEAT_CALCULATED
- 浏览器 → 折叠面板"TEMA 9th 重量估算" → 填表 → 估算 → result 展示 total_weight_kg + 9 段 segments
- MSW console 无 404

**Step 3: SPEC §12.4 V1.3 修订验证**

```bash
grep "V1.3.*HEAT" docs/PCS-UI-SPEC.md   # §12.4 应有匹配
grep "7.11.6" docs/PCS-UI-SPEC.md       # §7.11.6 HEAT 章节应有匹配
```

**Step 4: 后端 ruff baseline（不动后端）**

```bash
cd pcs-backend && uv run ruff check .   # 0 errors（不动后端）
```

**Step 5: 后端 pytest baseline（不动后端）**

```bash
cd pcs-backend && uv run pytest -q   # ≥ 1976 baseline（不动后端）
```

**Step 6: 静态检查（main 上直接跑，无需 dev server）**

```bash
cd pcs-frontend
npx tsc --noEmit                                                # 期望 clean
npx eslint src/ tests/                                          # 期望 clean
npx vitest run                                                  # 期望 ≥ 7 baseline（7 真测试）
```

**Step 7: dev server 浏览器手测（前台运行；非阻塞流程，由人工执行）**

```bash
cd pcs-frontend && npm run dev
# 前台运行 vite → http://localhost:5173
# 人工手测：
# - 浏览器登录 → 换热器 Page 路由可达
# - 上传 HTRI .txt → 提交 → result 展示 calc_id/record_hash/duty_w + outlet HEAT_CALCULATED
# - 折叠面板"TEMA 9th 重量估算" → 填表 → 估算 → result 展示 total_weight_kg + 9 段 segments
# - MSW console 无 404/500
# 人工 Ctrl+C 结束 dev server
```

**Step 8: gstack-qa 必跑（在 Claude Code 会话内调用 skill，非 shell 命令）**

```
# 直接在 Claude Code 提示符输入：
/qa
```

`/qa` 是 skill 调用，会触发 `~/.claude/skills/gstack/qa` 内置 harness 完成：
- Detached HEAD 切到批末 commit → vite HMR 自动重载
- 浏览器验证（gstack browse）
- 报告写入 `.gstack/qa-reports/qa-report-pcs-frontend-YYYY-MM-DD-p5-4-frontend.md`

报告格式（gstack-qa 自动生成）：

```markdown
# P5-4 HEAT frontend QA 报告

**日期**: YYYY-MM-DD
**commit**: <commit hash>
**baseline**: tsc 0 / eslint 0 / vitest ≥ 7 / 后端 ruff 0 / pytest ≥ 1976

## 验证清单
- [ ] tsc clean
- [ ] eslint clean
- [ ] vitest ≥ 7
- [ ] 浏览器：换热器 Page 路由可达
- [ ] 浏览器：上传 HTRI → result 展示
- [ ] 浏览器：重量估算 → 9 段 segments
- [ ] MSW console 无 404
- [ ] 后端 ruff baseline
- [ ] 后端 pytest baseline

## 发现
- CRITICAL：...
- HIGH：...
- MEDIUM：...
- LOW：...

## 结论
[APPROVE / WARNING / BLOCK]
```

**Step 9: 回 main + 兜底 commit（如有 lint 自动修复）**

```bash
git checkout main                                                # vite HMR 自动重载回最新代码
cd pcs-frontend && git add -u
git diff --cached --quiet || git commit -m "style(p5-4-frontend): lint 自动修复"
```

---

## Verification 端到端验证清单（17 + 3 项）

| # | 项 | 命令 / 操作 | 期望 |
|---|---|---|---|
| 1 | Task 0：SPEC §7.11.6 冻结 | `grep "7.11.6" docs/PCS-UI-SPEC.md` | ✅ |
| 2 | Task 0：§12.4 V1.3 登记 | `grep "V1.3.*HEAT" docs/PCS-UI-SPEC.md` | ✅ |
| 3 | Task 0：后端 4 项验证通过 | grep design_stage / HEAT_CALCULATED / outlet 命名 / §7.11.5 结构 | ✅ |
| 4 | Task 1：types/heat.ts | `ls pcs-frontend/src/types/heat.ts` | ✅ |
| 5 | Task 1：@migrate-when 标注 | `grep "@migrate-when" src/types/heat.ts` | ✅ |
| 6 | Task 1：迁移登记 | `grep "HEAT" docs/P45-BATCH3-TYPE-MIGRATION.md` | ✅ |
| 7 | Task 2：api/heat.ts 存在 | `ls src/api/heat.ts` | ✅ |
| 8 | Task 2：无显式 Content-Type | `grep -c "Content-Type.*multipart" src/api/heat.ts` = 0 | ✅ |
| 9 | Task 3：StateBadge +HEAT | `grep -c "HEAT" src/components/common/StateBadge.tsx` ≥ 2 | ✅ |
| 10 | Task 4：HeatComputePage | `ls src/pages/heat/HeatComputePage.tsx` | ✅ |
| 11 | Task 5：路由注册 | `grep "'heat'" src/App.tsx` | ✅ |
| 12 | Task 5：菜单注册 | `grep "'/heat'" src/layouts/MainLayout.tsx` | ✅ |
| 13 | Task 6：MSW handlers | `grep -c "heat/import-htri\|heat/:heat_id" src/mocks/handlers.ts` ≥ 3 | ✅ |
| 14 | tsc clean | `npx tsc --noEmit` | 0 errors |
| 15 | eslint clean | `npx eslint src/ tests/` | 0 errors |
| 16 | vitest baseline | `npx vitest run` | ≥ 7 真测试（Task 1 类型测试不计） |
| 17 | 浏览器手测 | login → 换热器 → 上传 → 提交 → result | ✅ |
| 18 | 重量估算手测 | 折叠面板 → 填表 → 估算 → 9 段 | ✅ |
| 19 | MSW console | 浏览器 console 无 404/500 | ✅ |
| 20 | 后端 ruff baseline | `uv run ruff check .` | 0 errors |
| 21 | 后端 pytest baseline | `uv run pytest -q` | ≥ 1976 baseline |
| 22 | gstack-qa 必跑 | `/qa` + 报告 `.gstack/qa-reports/` | ✅ |

---

## 复用清单

| 文件 | 用途 | 用法 |
|---|---|---|
| `api/client.ts:46` axios 实例 | 复用 | `import { client } from './client'` |
| `api/psv.ts:1-56` 模板 | 仿 | heatApi 同结构（3 方法 + multipart FormData） |
| `components/common/PageHeader.tsx` | 复用 | `<PageHeader title="..." module="HEAT" />` |
| `components/common/StateBadge.tsx` | 复用 | `<StateBadge module="HEAT" status="DRAFT" />`（Task 3 扩 +HEAT 4 态） |
| `pages/routeWrappers.tsx` | 仿 | `HeatRoute` 仿 `PsvRoute` |
| `pages/vessel/VesselComputePage.tsx:492` | 仿 | Page 布局（PageHeader + Card + StateBadge） |
| `pages/sep_equip/SepEquipComputePage.tsx:462` | 仿 | 折叠面板 + 动态表单 |
| `mocks/handlers.ts:42-144 devOnlyMockHandlers` | 仿 | 现有 17+ handler 模式 |
| `constants/env.ts` | 复用 | `import { PROJECT_ID, WORKSPACE_ID } from '../constants/env'` |
| `docs/PCS-UI-SPEC.md §7.11.5 PSV` 模板 | 仿 | §7.11.6 HEAT 章节结构（设计阶段/输入/输出/Result Tab/错误码） |

---

## 未解决问题（OPEN 列表）

- **OPEN-1**：HEAT frontend V1.3 §7.11.6 详细字段（**本批次 Task 0 解决**：SPEC 冻结先行）
- **OPEN-2**：PROJECT_ID / DEV_BEARER 硬编码—— ✅ 已收口（commit 1afa756）；本批次沿用 `constants/env.ts`
- **OPEN-3**：mocks/handlers.ts 缺失 P5-4 端点（**本批次 Task 6 解决**：3 handler）
- **OPEN-4**：api/vessel.ts / api/sep_equip.ts 缺失真 API 客户端（VESSEL/SEP_EQUIP 仍是内联 mock）—— 本批次不动；P5 frontend 全栈收口时统一补
- **OPEN-5**：types/api.d.ts 未自动生成 V1.3 SPEC 端点契约（**本批次 Task 1 解决**：@migrate-when 标注 + 迁移清单）
- **OPEN-6**：HeatComputePage source_stream_id 用 Input 而非 Select（无 streams 列表）—— 本批次接受；后续 P5 frontend 全栈收口时接入 streams Select
- **OPEN-7**：HEAT 导入成功后 GET 详情是串行两次调用（import → get）—— 后续可优化为 import 返回完整 detail（避免 roundtrip）
- **OPEN-8**：gstack-qa 浏览器回归（CLAUDE.md Per-Batch QA Gate）—— **本批次 Task 7 必跑**（不再「按需」）
- **OPEN-9**：HEAT design_stage 后端验证（**本批次 Task 0 解决**：grep design_stage + 在 SPEC §7.11.6 标注「单层无 BASIC/DETAIL」）
- **OPEN-10**：WORKSPACE_ID 常量导出（**本批次 Task 2 解决**：Step 1 先验证 export，否则补常量）

---

## 工时估算（参考）

| Task | 复杂度 | 预估耗时 |
|---|---|---|
| Task 0：冻结 SPEC §7.11.6 + 后端 4 项验证 | 中 | 30 min |
| Task 1：types/heat.ts + @migrate-when + 3 测试 | 中 | 20 min |
| Task 2：api/heat.ts（无显式 Content-Type）+ 3 测试 | 低 | 10 min |
| Task 3：StateBadge +HEAT（提前扩）+ 3 测试 | 低 | 10 min |
| Task 4：HeatComputePage 主 Page + 3 测试 | 中 | 50-60 min |
| Task 5：路由 + 菜单 + 3 测试 | 低 | 15 min |
| Task 6：mocks/handlers.ts 补 3 handler + 3 测试 | 低 | 15 min |
| Task 7：全栈验证 + gstack-qa 必跑 + reports | 中 | 30-40 min |
| **总计** | — | **~3 hours** |

---

**Plan 终止**：P5-4 HEAT frontend UI 闭环 7 task 完成。
**下一步**：用户批准后实施 + gstack-qa 浏览器回归（必跑）。