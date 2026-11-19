# PCS-NOTE — SPEC §7.8 COMMON 物性库：三查询页改为「查询驱动」+ §7.11.2 一览表列清单落地 + §7.13 设备台账页

> **日期**: 2026-11-19
> **触发**: P10-C 子批「前端收口」T1（TODO-160）/ T2（TODO-159）/ T3（TODO-157）
> —— 真后端通道的路由扫描撞出「首屏 422」与「三个页面调不存在的端点」
> ⚠️ **文件名沿用 T1/T2 的**（提交时已入 git ⇒ 改名会断历史）⇒ ⇒ **本文件覆盖
> 三处修订**（§7.8 / §7.11.2 / §7.13）
> **影响范围**: §7.8（三页的**首屏行为**）· §7.11.2（管道一览表的**列清单**）· §7.5（PMS / BEDD 两页的**存废**）
> **状态**: 已落代码并测试（前端 vitest 1082/1082 · 后端 5 例新测试）

按 PCS 项目规则「字段/枚举/权限/错误码以 OpenAPI + meta API 为准；与 SPEC 冲突时以
OpenAPI 为准并登记 SPEC 修订」——本文即该登记。**不修改 `spec/` 下的工艺室原件。**

---

## 1. §7.8 原文

```
7.8 COMMON 物性库
搜索：名称 / CAS / 分子式。
结果表：名称 / CAS / 分子式 / 分子量 / 临界温度 / 临界压力 / 来源
许用应力查询：材料 + 温度 → 插值结果。
毒性/爆炸极限：分类 + 上下限。
```

## 2. 冲突：契约的三个端点**都要求参数** ⇒ 「首屏加载整表 + 前端过滤」走不通

契约（`pcs-backend/docs/openapi.json`）里三个端点的必填参数：

| 端点 | 必填参数 | 返回 |
|---|---|---|
| `GET /common/materials/search` | `keyword`（`min_length=1`） | `list[MaterialSearchResult]`（后端单命中 ⇒ **最多 1 条**） |
| `GET /common/allowable-stress` | `material` + `temp_c` | **单个** `AllowableStressResult`（插值结果） |
| `GET /common/safety` | `cas` | **单个** `SafetyResult` |

⇒ ⇒ 前端此前首屏发**空查询** ⇒ ⇒ **422** ⇒ ⇒ 页面首屏就是错误态
（TODO-160）。⇒ ⇒ **「加载整表再在前端过滤」这条路在契约层不存在**。

## 3. 修订：三个页面改为「**填条件才查**」

| 页 | 查询条件 | 渲染 |
|---|---|---|
| `/common/properties` | 关键字（name / formula / CAS） | 物性卡片（**最多 1 张**） |
| `/common/stress` | 材料牌号 + 温度 | 1 行表 |
| `/common/toxicity` | CAS | 1 张分组卡片 |

- **首屏零请求**（没有条件 ⇒ 不发）。
- ⚠️ **SPEC §7.8「许用应力查询：材料 + 温度 → 插值结果」本来就是查询式**
  ⇒ ⇒ 本次改动与 SPEC **一致**；变的是**物性**与**毒性**两页的取数方式。
- ⚠️ **返回形状纠正**：`allowable-stress` 与 `safety` 返的是**单个对象**
  ⇒ ⇒ 前端此前当**数组**用（此前没暴露，因为请求**从来没成功过**）。

### 3.1 两处**能力边界**（不是 UI 选择 ⇒ 需产品知情）

1. **物性「结果表」最多 1 行** —— 后端 `CommonService.search_material` 走
   `chemicals.search_chemical` ⇒ **单命中**。⇒ ⇒ 若产品要「多行结果表」，
   正确做法是**后端扩一个列表端点**（走 `chemicals` 的列表 API），
   **不是**前端发 N+1。
2. **临界温度 / 临界压力两列早已砍掉**（2026-10-19 用户裁决）⇒ ⇒ 本次复核
   确认仍然成立（契约 `MaterialSearchResult` 只有 5 个字段）⇒ ⇒ **沿用**。

## 4. §7.11.2 管道一览表：列清单**落地为契约**

SPEC §7.11.2 给的「管道一览表列（完整）」= **43 列**（序号 / 管道号 / 尺寸 /
材料等级 / 介质代号 / 介质名称 / 相态 / 流体分类 / 毒性级别 / 管道级别 /
绝热代号 / 绝热厚度 / 涂漆代号 / 伴管类型 / 维持温度 / PID 图号 / 起点 / 终点 /
四项操作条件 / 四项备用工况 / 设计压力 / 真空 / 设计温度 / 设计最小温度 /
压力管道类别 / 试验介质 / 试验压力 / NDT 三项 / 泄漏试验两项 / 检查等级 /
清洗方法 / 应力分析级别 / 备注）。

⇒ ⇒ 后端 `piping_results` 表**这 43 列都有** ⇒ ⇒ 新端点
`GET /projects/{project_id}/pipe-line-list` 按这份清单投影
⇒ ⇒ 前端 `PipeLineListRow` 改成**契约类型**（DETAIL 档 = 完整列 + 审计三列）。

⚠️ **此前前端手写的是另一份 25 列**（含 `length_m` / `dp_kpa` / `velocity_m_s` /
`pipe_class_detail` 四个**后端根本没有**的列）⇒ ⇒ 真后端下永远是 `undefined`
⇒ ⇒ **幽灵列** ⇒ ⇒ 本次一并作废（**以 SPEC 为准**）。

⇒ ⇒ SPEC §7.11.2 的 `design_stage`（BASIC ≤30 列简化 / DETAIL 完整列）
**保持不变** ⇒ ⇒ 前端 BASIC 取前 10 列 + 设计压力/温度（12 列）。

## 5. §7.5 PMS / BEDD：两页**与 SPEC 对不上**（登记，不代裁）

SPEC §7.5 的 PMS / BEDD 是**项目创建向导**的两步（PMS / BEDD 录入）+ BEDD
「分组 Tab 编辑」⇒ ⇒ **没有**「独立的 PMS 列表页 / BEDD 文档页」。

⇒ ⇒ 前端这两个独立页面（P45-3-8 Task 35）是**超前实现** ⇒ ⇒ 且后端
**确实没有**那两个实体（PMS 无表；`projects.bedd_json` **无任何写入路径**）
⇒ ⇒ 本批**保守处置**：两页**不发请求** + 明写「数据源尚未接入」+ 给出依据。

⇒ ⇒ **存废待人裁**（① 删页并归到向导 / ② 补后端实体 / ③ 保留占位）
⇒ ⇒ 已登记 **TODO-195**。

## 6. §7.13 EQUIP_LIST：补了**设备台账页**（TODO-157）

SPEC §7.13 的列表列：**位号 / 类型 / 描述 / 包号 / 单元 / 来源 /
计算状态 / 签署状态 / 实际数据状态 / 操作**；筛选：**类型 / 来源 / 状态 /
包号 / 单元**。

⇒ ⇒ 后端契约 `EquipListResponse`（18 字段）里**没有**「**包号**」「**单元**」
「**计算状态**」⇒ ⇒ **不编**（编出来 = 幽灵列）⇒ ⇒ 以**契约为准**。

⇒ ⇒ 另两条口径差异（同样登记）：
1. **筛选**：契约支持的过滤维度是 `project_id` / `workspace_id` /
   `source_module` / `sign_status` / `equipment_status` ⇒ ⇒ **没有 `type_code`**
   ⇒ ⇒ 「类型」筛选在前端做（页面上标注「前端过滤」）。
2. **项目作用域**：契约允许**不传** `project_id` ⇒ ⇒ 但那等于「列全部项目的
   设备」⇒ ⇒ **后端补了项目授权**（见下条）。

⇒ ⇒ **连带的两个安全修复**（本批发现 · 建页时撞出来的）：
① **跨项目读**：`GET /api/v1/equipment-list` 此前**只有角色闸**
（`require_roles`）⇒ ⇒ 任何 DESIGNER / PROCESS_CONTROLLER 都能列
**全部项目**的设备台账 ⇒ ⇒ 现在：传 `project_id` ⇒ 该项目必须对我有授权
（否则 **404**，与「不存在」同形）；不传 ⇒ 只返回**我有授权的项目**的设备
（SYSTEM_ADMIN 全局 bypass）。
② ⚠️⚠️ **跨项目写**（更严重）：**sync** 的写入落在**源记录的 `project_id`**
上 ⇒ ⇒ 而单条 sync 此前**只**查了 **equipment 行**的项目 ⇒ ⇒ 源记录在
**别的**项目 ⇒ ⇒ **写进别的项目**；bulk-sync 更是**完全没查**
⇒ ⇒ 现在：单条 ⇒ 无权 ⇒ **404**；bulk ⇒ ⇒ 逐条预检 ⇒ 无权 ⇒ 标 `failed`
且**不写**。
⇒ ⇒ **教训**：写面守卫要判「**行实际落到哪儿**」⇒ ⇒ 不是判「请求里说的那个 id」。

⇒ ⇒ 「设备一览」(`/config/asset-list`) 与「设备台账」(`/equipment-list`)
是**两个页面**：前者列 `ConfigAsset`（配置资产：公式/模板/系数表），
后者列 `EquipmentList`（设备主数据）⇒ ⇒ 菜单里**分开**（P10-C · T3）。

## 7. 关联

- 后端端点：`pcs-backend/app/api/v1/pipe_line_list.py` ·
  `pcs-backend/app/schemas/pipe_line_list.py`
- 前端：`pcs-frontend/src/hooks/useProjectScope.ts` ·
  `pcs-frontend/src/pages/pipe/PipeLineListPage.tsx` ·
  `pcs-frontend/src/pages/common/*.tsx`
- 台账：`TODOS.md` **TODO-159 / TODO-160**（已关闭）· **TODO-193 / 194 / 195**（新登记）
- 计划：`docs/superpowers/plans/2026-11-18-p10-c-frontend-closure.md`
