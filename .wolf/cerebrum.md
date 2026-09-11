# Cerebrum

> OpenWolf 学习记忆。≤2000 token；按主题分组，保留最近 + 关键。
> 旧条目已并入 pcs-backend/docs 历史归档（如需追溯读 .wolf/cerebrum.md git log）。

## User Preferences

- 全程中文；术语中文为主、枚举/代码标识用英文。
- 用户审批风格：每决议指出「卡线/模糊」+ 给建议；接到反馈时**直接采纳可执行建议 + task note 记录边界**，不反复询问。
- 简单确认（"继续"）= 驱动下一 task，不重新讨论已完成项。
- ADR 编号按**文件序列**为准（用户口头编号可能错位）；映射差异回复中一句话说明即可。

## Do-Not-Repeat（按主题）

### 数据库/迁移

- 真库测试第二个起需 `_reset_async_engine` autouse fixture（单例引擎跨 event loop 炸）。
- 外科切割已提交代码后必复跑依赖测试；commit 自持性靠 worktree 验证。
- **写 migration 前必跑 SQLAlchemy reflection** 校核实际 schema（`Model.__table__.columns/constraints` 是 ground truth）。
- ORM `__table_args__` 必须含 `CheckConstraint` 同步 DB 约束（跨 dialect 不丢）。
- Pydantic schema 字段重复（Create+Update）→ Edit fail "Found 2 matches"，先 `grep -n` 再附上下文 unique。

### Alias/Registry

- spec §8.3 「≥50 别名」验收必须用 `group_type` 字段（ALIAS/ALIAS_WITH_FACTOR/ENUM/KEYWORD/FIELD_NAME）显式区分，≥50 只统计前两者。
- PROII 别名 shim 模式：`proii_parser.PROII_COMPONENT_ALIASES = dict(registry["COMPONENT_NAME"]["entries"])` 模块级重建；`map_libid_to_alias` 标 DEPRECATED 转发 `resolve_alias`。

### chemicals/IAPWS（vendor 模块陷阱）

- chemicals 1.5.2 **不导出 Chemical 类**；`search_chemical()` 返回单条 `ChemicalMetadata`，缺失抛 `ValueError`；CAS 是 int 需 `int_to_CAS()` 转字符串。
- `iapws95_Tsat(P)` 是**函数不是常量**（返 373.12 K@101325）；`iapws95_Tt` 是三相点（273.16 K），**不是熔点 Tm**。
- CoolProp 不在 pyproject.toml；水蒸气高精度用 `chemicals.iapws.iapws97_*`（IF97 等价 PropsSI）。
- `vendor/chemicals/` 源码 clone 运行时被 PyPI 同名包遮蔽。

### PropertyAutoCompleter

- `complete(cas, *, target_fields)` 单 CAS API，**无 composition 参数**（SIM-31 物性估算与组成解耦）。

### JSONB vs ORM 列

- JSONB 字段入已有 `stream_properties_json` 容器，避免 alembic 单列迁移开销；除非该字段需独立查询/索引才入 ORM 列。

### ORM 模型必填字段（mixin 强制）

- 写直接 DB 测试 fixture 前必查 model `__table__.columns` + mixin NOT NULL 字段（常见陷阱）：
  - `StreamStatePoint`: **无 workspace_id**；`composition_json` NOT NULL（JSONB 必填占位 `{}` 或实际数据）
  - `FlashResult`（继承 `TaggedRecordMixin`）: `tag_number` NOT NULL（string unique per project）+ `project_id` + `workspace_id`
  - `TaggedRecordMixin` 强制 `tag_number` NOT NULL；`RecordMixin` 提供 `project_id`/`workspace_id` (declared_attr)
- DB 测试 fixture 最简 pattern：POST API 创建（service 层补必填）→ DB UPDATE 状态字段；避免 ORM kwarg 拼装遗漏必填字段。

## Key Learnings

### P3.2 SIM 范围与契约

- 范围：PRO/II + 手工 + Excel 三入口；HYSYS/Aspen/HTRI 解析器后置 P4。
- 启动顺序：P3.3 COMMON → P3.2 SIM → P3.1 PMS 串行（SIM→COMMON 强依赖）。
- case_type 双层语义：streams.case_type（物流级设计工况 NORMAL/END_OF_RUN/...）vs stream_state_points.case_type（状态点级操作边界 NORMAL/MIN/MAX/ALTERNATE）独立存在。
- StreamSignStatus 走 P1 9 态全集；P3 活跃 4 态 PG native enum；P4 扩展走 `ALTER TYPE ADD VALUE`（不可逆）。
- Pydantic v2 `Field(description=...)` 必含中文（spec 本体论 V1.6 §5.3 强制）；测试 `assert any("一" <= c <= "鿿" for c in field.description)`。
- 物流冲突三级：BLOCK（阻止保存）/ WARN（用户值优先标记偏差）/ INFO（计算值优先派生类）。`effective = calculated ⊕ user_provided`，冲突必须可见不静默覆盖。

### P3.x 批 3 完成（2026-09-11）

- 9 task 全部完成：SIM-24 validate / 25 Excel template / 26 properties / 28 8 条 SIM-V / 29 22 条 PR / 30 alias_registry / 31 mass→mole / 32 update 状态限制 / 35 被引用不可删除。
- SIM-30：4 组 70 条（COMPONENT_NAME 33 + UNIT_CONVERSION 15 + EXCEL_COLUMN 11 + VALIDATOR_FIELD 11），55 ALIAS 项 ≥ §8.3 50 验收；Sheet3 4 列 `[Group, Alias, Standard, Factor]` 展示全 4 组。
- SIM-31 液相分层：ORM 列（liquid_fraction/specific_gravity）+ JSONB（3 字段入 stream_properties_json）。
- SIM-35 DELETE 引用检查：`_collect_references` 单次往返多表 count 查询（避免 N+1）；引用表清单 stream_state_points / flash_results；错误格式 `f"{table}={count}条"`。
- ruff 基线 437（443-5 净减），每次 commit ≤ 437 或净减。

### P3.x 批 4 入口（2026-09-11）

- SIM-33（commit 7499224）：液相命名对齐 + 气相 9 字段 + SIM-31 JSONB→ORM 迁移
  - 路径 1（RENAME COLUMN）用户裁决 2026-09-11：个人项目无破坏性；PG RENAME COLUMN 毫秒级无重写数据成本
  - molecular_weight 不重命名（通用 MW，气液相同）
  - SIM-31 JSONB 3 字段回调到 ORM：std_liq_density→liquid_std_density 等，避免气液不对称
  - 气液对称命名规则：liquid_X / vapor_X（spec §3.5 + §3.6）
  - 下游引用调整：excel_parser/conflict_resolver/test_stream_orm 共 4 处 molecular_weight 不变（MW 保留）
  - ruff 净减 2（441 vs baseline 443）

- SIM-34（commit 357fb76）：炼油 5 字段 + 蒸馏曲线 8 种 schema
  - 4 Float 字段（rvp/tvp/watson_k/flash_point）+ 1 JSONB 容器（distillation_curves）
  - 8 种曲线枚举：D86/TBP/EFV/D86_CRACKING/D1160/D2887/D5236/D7169
  - 蒸馏曲线 schema 验证器（curve_type 严格枚举 + points 严格递增 + temp_c 单调 + 减压类型 pressure 必填）
  - property_conflict_resolver 同步 liquid_surface_tension（SIM-33 重命名）
  - ruff 净减 4（445 vs baseline 449）

- SIM-36（commit a28d40c）：PRO/II reaction kinetics 提取（spec §3.3.3）
  - Reaction dataclass 扩展 9 字段：horx_heat/ref_component/ref_temp/ref_phase/kinetics/korder
  - 双格式兼容：sample5 单行（HORX=... CONV MODEL）+ dmc 多行（STOICHIOMETRY + HORX HEAT/REFCOMP/REFTEMP/REFPHASE + KINETICS PEXP(...)/ACTIVATION/TEXPONENT + KORDER）
  - 引用语句排除：CALCULATOR/SET 内 REACTION ID=X,COPTION=... 不解析为定义
  - 括号保护：_split_top_level_commas 保护 PEXP(MIN,G,LIT) 类括号内逗号
  - 测试 17 项：单行/多行/混合格式 + HORX 缺失/兜底 + KINETICS 科学计数法 + dmc.inp 真实 fixture
  - ruff 净减 4（445 vs 上次批 4 入口 449）；全量回归 1044 passed

- SIM-37（commit 72feed8）：项目级符号/格式模板审批收口
  - 用户裁决（cerebrum 政策）：项目级三域（PipeClass/StreamSymbol/PipeCodeConfig）
    审批**不挂 ConfigAsset**（避免爆炸）+ 仅 PipeClass 项目级保留 ConfigApproval.project_class_id
    （V1.4 §五、#1 历史决议）；其他两类只审计不写 ConfigApproval
  - ProjectStreamSymbolStateMachine 新增（5 态表 + 5 transition 函数 +
    _project_transition 公共实现），与 ProjectPipeClassStateMachine 同模式
  - PipeCodeTemplateService._project_transition 补 audit.write
    （CONFIG_ASSET_SUBMITTED/APPROVED/REJECTED/PUBLISHED/OBSOLETED 5 动作）
  - 测试 14 项：5 态机契约 + 5 transition 路径 + 非法 transition/OBSOLETE 终态
    + project_id 不存在 + 三服务 5 态机对齐
  - ruff 0 错（全量持平 445）；全量回归 1058 passed（+14）

- SIM-38（一键变更单 RECORD_CHANGE 闭环）：ChangeNoticeService + 7 值 change_type + 2 值 triggered_by
  - ChangeType 7 值：DATA_CORRECTION/PROCESS_CHANGE/UPSTREAM_CHANGE/CLIENT_COMMENT/RECORD_CANCELLATION/CHANGE_REVERSAL/OTHER（spec V1.0 §4 字面一致）
  - TriggeredBy 2 值：MANUAL/UPSTREAM_CHANGE
  - AuditAction 新增 3 值：CHANGE_NOTICE_CREATED/APPROVED/CANCELLED
  - create_change_notice：deliverable（deliverable_type=CHANGE_NOTICE + version_purpose=ISSUED_FOR_CHANGE + sign_status=PENDING）+ change_notice_details 1:1 扩展双写；仅 CHANGED 状态记录可发起（其他状态 422）
  - approve_change_notice：PENDING → APPROVED + audit；二次审批 409
  - _apply_record_resolution：CHANGED → CHECKED + change_resolved_by 写入（内部契约，approve 时联动）
  - 测试 20 项：7 值枚举 + 7 种 change_type 入库 + 双表写入 + CHANGED 校验 5 态 + 记录不存在 404 + apply resolve + 二次审批 409 + audit 落库
  - 测试 fake 类模式：`_FakeDeliverable(Deliverable)` / `_FakeChangeNoticeDetail(ChangeNoticeDetail)` 子类继承（兼容 SQLAlchemy select()），通过 `_FakeSession.register_class_map` 做 fake ↔ ORM 真类双向查找
  - ruff 净减 5（18 vs baseline 23）；全量回归 1077 passed（+19, 1 flake=export_service perf budget 偶发，与本 commit 无关）

### PCS 领域核心

- 两层签署（记录 9 态门禁 / 交付物 Rev+签署矩阵）、哈希判实质变更、位号终身唯一。
- 15 项领域决议：docs/adr/0001~0014 + SUP-007。
- 文档体系：增补文件声明修改，不直接改基线；基线升版显式请求才做。
- SUP-002 plan 模式：保留 V1.3 baseline + 文末 V1.4 关键修正段作为执行期 patch 来源。

## Decision Log

- 管道计算等级按项目绑定（source=PROJECT）；class_id 全局唯一 PK，跨项目同码不同值需复合 PK 迁移（P3 复核）。
- `pipe_classes.version` 保留 str50（版本号多为 Rev 0/IFC 文本）；权威版本链在 config_versions。
- 项目级管道等级/符号/格式模板审批**不挂 ConfigAsset**（避免 config_assets 爆炸），走轻量状态列 + ConfigStateMachine；`pipe_classes.status` 是 5 态镜像列，service 层禁止绕过状态机直接 UPDATE。
- SIM-30 scope = 新增单源 alias 表，**不动 P3.2 已落地枚举**（StreamCaseType/StatePointCaseType/StreamSignStatus/RecordSignStatus/ConflictSeverity/ImportSourceType）。
- SIM-31 mass→mole 换算独立于 PropertyAutoCompleter（职责分离）；MW 缺失在归一化层抛 `CompositionMassToMoleError`。
