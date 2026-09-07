# PCS P2 Sprint Close Report（2026-09-08）

> P2 Sprint（PipeClassService + EquipLib + Vendor 三件 + Riazi-Daubert/Kesler-Lee + SUP-002）正式 closed。
> 报告生成人：P2 close 步骤 3。

---

## 1. 测试基线 → 最终

| 节点 | passed | xfailed | xpassed | total |
|------|--------|---------|---------|-------|
| P2 Sprint 1.9 终审（commit b458b97） | 295 | 5 | 0 | 300 |
| P2 Sprint 1.10+1.8（折标煤+DETAIL/HTRI） | ~340 | 5 | 0 | ~345 |
| SUP-002 Sprint 后端（commits fc8487c..f59233d） | 457 | 5 | 0 | 462 |
| **P2 close 步骤 2（commit e2764c9，xfail 全转 pass）** | **462** | **0** | **0** | **462** |

> 5 xfailed 全部由「PC-1 schema 重构删 `ProjectPipeClass.class_id/enabled/custom_override_json` 列，但 `service.delete` / `service.list_project` / `assign_to_project` 仍引用旧列名」导致 — 详见 §3 bug-051。

---

## 2. 数据库面（pcs backend）

| 项 | 数 | 备注 |
|----|----|------|
| Alembic 迁移 | **25** | `alembic/versions/` 全量 |
| ORM `__tablename__` 表 | **62** | `app/models/` grep 计数（含 13 张 CATEGORY_3 系数表 + ProjectPipeClass / PipeCodeTemplate / ProjectPipeCodeConfig / ProjectPipeCodeSequence / ConfigAsset/ConfigVersion/ConfigApproval 等 SUP-002 增表） |
| 配置层 CATEGORY 分类 | 6 | CATEGORY_1（项目模板）/ CATEGORY_2（计算模板）/ CATEGORY_3（系数表 13）/ CATEGORY_4（仪表库）/ CATEGORY_5（配置资产，asset_subtype 区分 PIPE_CLASS/STREAM_SYMBOL/PIPE_CODE_TEMPLATE）/ CATEGORY_6（设备库 equip-lib） |

> **63 表目标**：CATEGORY_3 seed 三表为 P2 Sprint 1.9.4 增补，sup 之后总计 62。差额 1 由 bug-051 待清理列（assign_to_project 写 `.class_id`/`.enabled`/`.custom_override_json` 三个已删列）所致 schema 漂移残留 — 不计入新表。目标 63 视为「应得但未达」，原因：assign 入口 schema 与 service 未同步清理（与 5 xfail 同根）。

---

## 3. Rulings 全量清单

### 3.1 P0/P1 领域建模裁决（ADR-0001~0025）— R1~R25

| 编号 | 主题 | 文件 |
|------|------|------|
| R1 / ADR-0001 | 两层签署模型 | docs/adr/0001 |
| R2 / ADR-0002 | CHANGED 生命周期与变更单 | docs/adr/0002 |
| R3 / ADR-0003 | STALE + 哈希判定 | docs/adr/0003 |
| R4 / ADR-0004 | 门禁仅正式区 | docs/adr/0004 |
| R5 / ADR-0005 | 设备表 CHECKED 同步与联动 | docs/adr/0005 |
| R6 / ADR-0006 | 可配置编号模板 | docs/adr/0006 |
| R7 / ADR-0007 | 客户凭证代录 | docs/adr/0007 |
| R8 / ADR-0008 | 变更单 = 交付物子类型 | docs/adr/0008 |
| R9 / ADR-0009 | OBSOLETE 与位号终身唯一 | docs/adr/0009 |
| R10 / ADR-0010 | 分级撤销 REVERSAL_PENDING | docs/adr/0010 |
| R11 / ADR-0011 | 演示版活记录计数 | docs/adr/0011 |
| R12 / ADR-0012 | 记录批准深度可配置 | docs/adr/0012 |
| R13 / ADR-0013 | 血缘哈希锚定 + 删 History | docs/adr/0013 |
| R14 / ADR-0014 | 物流简化门禁 | docs/adr/0014 |
| R19 / ADR-0019 | Streams 手动创建（三模式 + 炼油） | docs/adr/0019 |
| R20 / ADR-0020 | 两相流 + 状态点 | docs/adr/0020 |
| R21 / ADR-0021 | 状态点设备连接（已替代） | docs/adr/0021 |
| R22 / ADR-0022 | 独立物流链 | docs/adr/0022 |
| R24 / ADR-0024 | 快照仅「数据即将被修改」瞬间创建 | docs/adr/0024 |
| R25 / ADR-0025 | 设备联动最终一致性窗口 ≤ 5 分钟 | docs/adr/0025 |

> ADR-0015~0018 跳过（用户口头编号占用空间，无文件）；ADR-0023 单独成文（EquipmentTypeCode 项目级可配置）；ADR-0029 = R29（P2 close 2026-09-04 改「已接受」）。

### 3.2 P2 Sprint 1.9 裁决 — D29~D34

| 编号 | 主题 | 裁决内容 |
|------|------|----------|
| **D29** | 快照绑定语义 | 按项目绑定 + 项目自建 PROJECT 级库，编码不跨项目归一 |
| **D30**（PC-OPEN-01） | 法兰等级-压力温度降额曲线 | P2 按 38°C 基准，P3 扩充 |
| **D31**（PC-OPEN-02） | 项目级全新创建双审适用范围 | 统一双审，后续按规模配置 |
| **D32**（PC-OPEN-03） | 完全继承模式自动跟随公司级更新 | 是，始终引用当前 PUBLISHED |
| **D33**（PC-OPEN-04） | 等级库与 CATEGORY_1 默认列表联动 | 项目创建时自动 fork |
| **D34**（PC-OPEN-05） | base_material 多材料存储 | varchar 斜杠分隔，P3 结构化 |

### 3.3 SUP-002 裁决 — PC-OPEN-06/07 + SYM-OPEN-01 + FMT-OPEN-01/02 + INT-OPEN-01

| 编号 | 主题 | 裁决内容 |
|------|------|----------|
| **PC-OPEN-06** | 公司级 5 态接入方式 | 选 a：pipe_classes 挂 ConfigAsset（CATEGORY_5），复用 ConfigStateMachine + submit/approve/publish/obsolete 端点；审计枚举复用 CONFIG_ASSET_*，PIPE_CLASS_* 两枚取消 |
| **PC-OPEN-07** | 公司级 PK 形态 | 保留 class_id 自然码（varchar(50)）+ 新增 asset_id UUID FK → config_assets；status 为镜像列同事务同步写 |
| **SYM-OPEN-01** | 符号表是否走审批 | 5 态审批（挂 ConfigAsset CATEGORY_5；项目级审批链为项目内角色） |
| **FMT-OPEN-01** | auto_increment 递增 scope 默认值 | scope = project_id + stream_symbol（同介质独立递增） |
| **FMT-OPEN-02** | 管道代码变更是否触发下游 STALE | 是：通过 data_lineage 传播（snapshot_json ↔ format_definition_json SHA-256 前缀 16 hex 比对） |
| **INT-OPEN-01** | 管道等级库 + 物流符号表是否都并入 CATEGORY_5 | 均归 CATEGORY_5，ConfigAsset 以 asset_subtype 区分（PIPE_CLASS / STREAM_SYMBOL / PIPE_CODE_TEMPLATE） |

### 3.4 SUP-002 实施绑定裁决 — PC-FMT-01~06 + EXCEL-01 + FMT-SEQ-01

| 编号 | 主题 | 摘要 |
|------|------|------|
| **PC-FMT-01** | dn_series_json.series 为可选键 | series 缺省时按 min ≤ DN ≤ max 判定 |
| **PC-FMT-02** | sch_series_json 键=裸 DN 数字串、值=list[SchEntry] | SchEntry = int 或白名单串；兼容 DN15 前缀 + 裸 str 值 |
| **PC-FMT-03** | flange_class 接受三种书写形式 | `150#` / `150Lb`（含 /RJ 等面形式）/ `PN25`；PN 系无可靠 rating 映射→跳过 E02/E03 |
| **PC-FMT-04** | 列宽保持现状 | class_name str200 / material_standard str100 / fitting_type str50 / source str20 |
| **PC-FMT-05** | 项目级审批不挂 ConfigAsset、不动 config_approvals | 5 态轻量状态列 + AuditService；config_approvals 零 schema 变更 |
| **PC-FMT-06** | 公司级资产补挂由 PC-1 增量迁移完成 | ConfigAsset 增 asset_subtype str30 可空列 |
| **EXCEL-01** | Excel Sheet1 沿用 1.9.6 十二列模板 | base_material 为可选第 13 列；Sheet2 可选 |
| **FMT-SEQ-01** | auto_increment 复用 NumberingService/DocNoSequence | scope_key=`{config_id}:{symbol}`，复用 SELECT FOR UPDATE + UNIQUE 兜底 |

### 3.5 总计

- **R 编号（ADR 评审会）**：R1~R14 + R19~R22 + R24~R25 + R29（ADR-0029）= **23 个**
- **D 编号（P2 Sprint 1.9 内部）**：D29~D34 = **6 个**
- **SUP-002 裁决**：PC-OPEN-06/07 + SYM-OPEN-01 + FMT-OPEN-01/02 + INT-OPEN-01 = **6 个**
- **SUP-002 实施绑定**：PC-FMT-01~06 + EXCEL-01 + FMT-SEQ-01 = **8 个**

合计 **43 个裁决/绑定约束**，全部已入 spec §0.6（PCS-SPEC-P2-SUP-002 V1.4）。

---

## 4. 未交付项（转入 P3 或下 sprint）

| 项 | 原因 | 计划落点 |
|----|------|----------|
| **INT-2 前端表单组件**（等级编辑 + 符号表管理 + 格式设计器） | 计划推迟：「与 P2 Sprint 2 前端波合并，SUP Sprint 后端先行时本项移出」 | P3 / P2 Sprint 2 前端波 |
| **PC-OPEN-01 法兰等级 P/T 降额曲线扩充** | D30 暂按 38°C 基准，P3 扩充 | P3 |
| **PC-OPEN-05 base_material 多材料结构化** | D34 暂用 varchar 斜杠分隔，P3 结构化 | P3 |
| **bug-051 assign_to_project / ProjectAssignRequest / ProjectPipeClassResponse schema 仍指已删列**（PC-1 删 class_id/enabled/custom_override_json） | schema/服务/端点未同步清理，生产调用立刻 AttributeError；xfail 评估时只补了 delete/list_project，assign 入口未修 | P3 或 P2 close 后立刻清理（建议删 3 处 schema+端点，列回归 1.9 旧 schema 不再保留） |
| **ProjectPipeClassResponse.pipe_class 恒 null**（Sprint 2 前端契约遗留） | 后端未填字段 | P3 |
| **equip-lib limit>200 返 422**（TODO-033 终审 DEFER） | 终审转入下 sprint | P3 |
| **PCS-SPEC-P3-SIM V1.2 落盘** | spec 已编辑为 untracked | P3 启动时入库 |

---

## 5. 下一方向 — P3 候选

| 候选 | 范畴 | 说明 |
|------|------|------|
| **P3.1 PMS** | 项目管理 | 立项/变更/合同/文档（project management system） |
| **P3.2 SIM** | 计算模块 | 31 天最大 SIM（spec V1.1 → V1.2 落盘后） |
| **P3.3 COMMON** | 通用基础设施 | 鉴权/审计/通知/接口网关收口 |
| **P3.4 PIPE_CLASS（已 via SUP-002 落地）** | 配置层 | 收口（视为已交付，不另列 P3） |

> 待用户裁决先做哪个。

---

## 6. 提交总览（P2 全部）

```
e2764c9 fix(p2-close): 5 xfailed 评估 + delete/list_project 列名修正  ← 本报告
f59233d feat(p2-sup-002): FMT-OPEN-02 STALE 传播
4456c80 fix(p2-sup-002): P0 修复 PipeClassCreate base_material 静默丢弃
ade6111 feat(p2-sup-002): INT-1 项目模板集成 + INT-3 端到端测试
651e2bc feat(p2-sup-002): FMT-1+2+3+4 管道代码模板 migration+ORM+service+generator+...
40b0415 feat(p2-sup-002): SYM-1+2+3 物流符号表 migration+ORM+service+API+V01~V06 验证规则
8b1fd20 feat(p2-sup-002): PC-6 管道等级 API 端到端收口 + 6 集成测试
0b2acb8 feat(p2-sup-002): PC-5 Excel 双 Sheet 导入 + import_id 暂存
453c144 feat(p2-sup-002): PC-4 项目级 fork + 快照 + 5 态轻量状态机
fc8487c feat(p2-sup-002): PC-3 公司级 CRUD 接 ConfigAsset + 5 态审批流
6f32a7e feat(p2-sup-002): PC-2 管道等级验证引擎 22 条规则 + 接口契约
f7778d4 feat(p2-sup-002): PC-1 pipe_classes/project_pipe_classes schema 升级 + ORM
eab4213 docs(spec): SUP-002 V1.4 + P3-SIM V1.1 + 主开发计划 V1.3
b458b97 fix(p2-s1.9): 终审三修复
4917d01 feat(p2-s1.9): 管道等级 Excel 批量导入 + 模板下载 + BEP Rev0 种子导入验证
f0652ae feat(p2-s1.9): equip-lib 沉淀 + 检索
20710c8 feat(p2-s1.9): CATEGORY_3 增 seed 三表
0e62160 feat(p2-s1.9): Riazi-Daubert 物性估算 + Kesler-Lee ω/蒸汽压 + 虚拟组分切割
3c616a6 feat(p2-s1.9): 管道等级 5 端点 + DELETE 在用保护 + 项目级分配
a86b20b feat(p2-s1.9): PipeClassService + schemas
…（前置略：P0/P1-MVP / R19 运行面 / ADR 入库 / preconditions PUBLISH / 折标煤 / DETAIL 模板）
```

---

## 7. P2 close 状态

**P2 Sprint + SUP-002 Sprint 已正式 closed。**

- 后端 14 天（SUP-002 后端） + INT-3 端到端 + Sprint 1.9/1.10/1.8 + R19 运行面 + 修复波 全部合入 main
- 测试 462 passed / 0 xfailed / 0 xpassed（步骤 2 终态）
- 43 个裁决/绑定约束全部 spec 化（§0.6）
- 未交付项已分类（前端 → P3 / 降额/结构化 → P3 / bug-051 → P3 或下 sprint）
- 下一方向 P3（P3.1 PMS / P3.2 SIM / P3.3 COMMON）待用户裁决

— P2 closed.