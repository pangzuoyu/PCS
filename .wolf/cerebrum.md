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

### Auth hardening 模式（2026-09-18）

- **JWT decode 必传 `options={"require": [...]}`**：默认 PyJWT 不强制必填 claim。
  必传 `["exp", "iat", "sub"]` 至少这三项（与 create_*_token 实际写入对齐）。
  `MissingRequiredClaimError` 是 `PyJWTError` 子类，已被现有 `except jwt.PyJWTError` 自动捕获。
- **Refresh token 必须 JTI + rotation**：每次 `create_refresh_token` 写 `jti=uuid4()`；
  进程内 `_REVOKED_JTIS: set[str]` in-memory 即可，redis 单节点场景避免额外依赖。
  refresh 端点：检查 `is_jti_revoked` → 撤销旧 JTI → 返回新 access + 新 refresh。
  `RefreshResponse` 必须含 `refresh_token`，前端无需另存。
- **Logout 真正生效需要接 refresh_token**：旧实现 `return None` 是 no-op，
  与 refresh 不轮换配套下 logout 名存实亡。
  `LogoutRequest` 接收可选 `refresh_token` 字段，无 body / 伪造 / access 三场景
  全部幂等 204（防侧信道：不通过响应区分 token 状态）。
- **LDAP DN 必须 RFC 4514 §2.4 转义**：`_sanitize_dn_component(value)` 处理
  `\` `"` `#` `+` `,` `;` `<` `=` `>` 和 NUL。
  NUL 特殊：先跑单字符转表（NUL 不在表中保持原样），再单独 `replace("\x00", "\\00")`，
  否则 pre-replace 后反斜杠会被转义二次翻倍成 `\\\\00`。
  测试覆盖：parametrize 10 字符 + 集成（username=`alice,ou=admin` 注入 RDN 边界）。

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

### API 520 Part I 9th Ed.（2014-07）canonical forms（2026-09-18 验证锁定）

- **§5.6.3.1 Eq (9) SI** C = 0.03948 × √[**k** × (2/(k+1))^((k+1)/(k-1))] — √ 内**只有 k**，**没有 k/(k-1)**。
- **`(k/(k-1))` 因子归属**：§5.6.4 subcritical F_2 Eq 18（`√[(k/(k-1)) × r^(2/k) × ((1-r^((k-1)/k))/(1-r))]`），不用于 critical flow。
- **Eq (5) SI** A = W/(C·Kd·P₁·Kb·Kc) × √(TZ/M)，中 M 在 kg/kmol 下，0.03948 常数已隐含 R 维度。PCS 用 M=kg/mol + R=8.314462618 J/(mol·K) 代数等价。
- **Table 8 SI 列** k=1.10/1.40/1.67 = 0.0248/0.0270/0.0287（4 位有效）。
- **§5.6.3.2 Example 1**（Eq 11 SI）= 3698 mm²（输入：W=24270 kg/h, M=51, k=1.11, T=348K, Z=0.90, P₁=670 kPa）。
- **章节定位**：`§5.6.3.1.1`（不是 §5.6.5 — 9th Ed. 没有 §5.6.5）。
- **bug-089 教训**：不能跨章节搬公式因子；critical 与 subcritical 用的 (k/(k-1)) 形式看似相似但语境完全不同——9th Ed. PDF 原文交叉验证是底线。
- **P5-3-7 待办**：完整 Annex C.2.2 Two-Point Omega Method（Eq C.12/C.13/C.16-C.21），C7 当前 Leung 1996 简化形式仅为占位。
- **P5-3-8 待办**：GB/T 12241 bug-089 修复（R=8314 → 8.314462618，移除 k/(k-1) 因子）—— 与 API 520 同步。
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

- SIM-39（记录弃用 RECORD_CANCELLATION 闭环）：RecordCancellationService + BoundObsoleteError
  - 弃用路径分支（spec V1.0 §3.4 / ADR-0009）：
    - 未绑定（locked_by_deliverable=False）：直接 OBSOLETE，obsoleted_via=DIRECT
    - 已绑定（locked_by_deliverable=True）：拒绝直接 OBSOLETE（BoundObsoleteError → 409
      RECORD_BOUND_USE_CHANGE_NOTICE），需走 change_type=RECORD_CANCELLATION 变更单
  - bound_obsolete_via_deliverable：变更单 APPROVED 阶段调用，联动 OBSOLETE +
    写 obsoleted_via_deliverable_id 追溯凭证
  - 位号终身唯一契约（ADR-0009）：OBSOLETE 不清空 tag_number，依赖 (project_id, tag_number)
    UNIQUE 约束覆盖含 OBSOLETE 全部记录（DB 层）；服务层契约：tag_number 保留
  - 测试 11 项：未绑定直接 OBSOLETE + 5 态起点均允许 + 已绑定拒绝 + BoundObsoleteError
    code+status + 变更单联动 OBSOLETE + 未绑定拒绝走变更单路径 + 记录不存在 404 +
    已 OBSOLETE 再次弃用 409 + tag_number 保留 + 2 种路径 audit 落库
  - ruff 全量持平 18；全量回归 1084 passed（+11-3 export_service 跳过 flake）

- SIM-40（反向签署 REVERSAL_APPROVAL 闭环）：ReversalApprovalService 三事件封装
  - 状态机事件（已在 state_machine.py 锁定）：CHANGED → REVERSAL_PENDING（REQUEST_REVERSAL）→
    CHECKED（APPROVE_REVERSAL）/ CHANGED（REJECT_REVERSAL）
  - request_reversal：仅 CHANGED 发起 + reason 必填（422）+ locked_by_deliverable=True 拒绝
    （409 REVERSAL_LOCKED_USE_CHANGE_REVERSAL，提示走 CHANGE_REVERSAL 新变更单）
  - approve_reversal：恢复 record_change_snapshots 最新 ACTIVE 快照 + 标记 CONSUMED；
    无快照时仍 resolve（不阻断）
  - reject_reversal：reason 必填 + reversal_rejected_* 字段写入
  - 测试 12 项：request 5 态拒绝 + locked 拒绝 + reason 必填 + 记录不存在 + approve 快照恢复
    + 无快照仍 resolve + approve 4 态拒绝 + reject 字段写入 + reject reason 必填 + reject
    4 态拒绝 + 完整周期 2 条 audit 落库（REQUESTED + APPROVED）
  - ruff 全量持平 18；全量回归 1096 passed（+12）

- SIM-37a（PRO/II 8.x 炼油版 PoC 关键字识别）：RefinerySectionDetector
  - 8 类枚举：ASSAY/D86/TBP/LIGHTEND/REFSTREAM/TRAY_SIZING/REFINERY_PROCESSOR/
    TBP_ASTM_CURVES（PoC 仅关键字识别，深度解析留待 SIM-37b 4d）
  - RefineryReport dataclass：sections（set）/counts（多页 TRAY SIZING 计数）/
    line_numbers（首现 1-based）/source_file + has_refinery + to_dict JSON 序列化
  - 关键字识别策略：大小写不敏感 + 单词边界匹配（避免 AD860 误吃 D86）+
    多词关键字优先（STREAM TBP/ASTM CURVES 先于 TBP；TRAY SIZING 先于单 TRAY；
    REFINERY PROCESSOR 先于 REFINERY）
  - 1 真 fixture：sample/200FlexiCoking1.out 验证 FCC 报告 6 类关键字全识别
    （ASSAY/D86/TBP/TRAY_SIZING/REFINERY_PROCESSOR/TBP_ASTM_CURVES，TRAY_SIZING ≥5 次）
  - 测试 22 项：8 类枚举契约 + 8 类 parametrize 关键字识别 + 去重 + 大小写
    + 空报告 + counts + line_numbers + 3 真 fixture + 2 dataclass 字段契约
  - ruff 0 错（全量持平 445）；全量回归 1123 passed（+27）

- SIM-37b/1（PRO/II 炼油版全量 3 commit 拆分第 1 批）：ASSAY + D86 parser
  - 用户裁决拆 3 commit（每组 2 parser）：① ASSAY+D86 ② TBP+LIGHTEND
    ③ REFSTREAM+TRAY_SIZING
  - AssayDeclaration：CUTPOINTS TBPCUTS= 独立行挂靠前一 ASSAY 声明（pending
    模式）；TBPCUTS 末尾 DEFAULT 关键字 → cut_points_default=True
  - D86 regex 陷阱：DATA 段内含多逗号（temp/vol 对分隔），必须用非贪婪
    \`.+?\` 匹配到行尾可选 TEMP，\`[^,]+\` 首逗号截断全挂（RED 阶段实测）
  - D86Curve points 解析：首 token 跳过（起始 vol% 恒 0）+ temp/vol 对 +
    末尾孤立 temp → (temp, 100.0) 末点
  - fixture：1NAPHTHA 13 点 + 1LCO 2 条 D86 + ASSAY API94/IMPROVED/TAILS
  - 测试 18 项；ruff 持平 445；全量 1141 passed（+18）

- SIM-37b/2（TBP + LIGHTEND parser，commit 6b04bb8）
  - TBP 与 D86 同构：复用 parse_distillation_points（从 assay_d86 提取
    公共 helper + __all__ 导出）；DATA 首 token 起始 vol% 可非 0
    （huafeng FO1 DATA=5,322/...）
  - LightendComposition：COMPOSITION(WT|M)= 组件对（/ 分隔 comp_id,value）
    + 可选 PERCENT(WT)= + NORMALIZE 关键字
  - **续行 joiner 三行 bug（bug-069）**：_join_continued_lines_simple 的
    if buf: 中间续行分支未剥行尾 &；两行续行（首行 else 分支剥 &）不触发，
    三行续行 LIGHTEND 首次暴露（丢末对组件 + PERCENT 漏捕）——
    多行续行场景必须显式测试
  - fixture：FCC 1SLURRYR TBP 8 点 + huafeng LIGHTEND 1C 8 组件/17.51/NORMALIZE
  - 测试 18 项；ruff 持平 445；全量 1159 passed（+18）

- SIM-37b/3（REFSTREAM + TRAY SIZING parser，commit 5fcdf6b，SIM-37b 闭环）
  - RefStreamDeclaration：PROPERTY 行内 REFSTREAM= + 可选 TEMPERATURE=/
    RATE(M|WT)= 覆盖；无 REFSTREAM 的 PROPERTY 行不产出
  - UnitTraySizing 状态机：UNIT 头归属 + MECHANICAL/RESULTS 表标记 +
    段标题守卫精确枚举；MECHANICAL 行尾 5 列布局 [passes, spacing,
    factor, type, min_dia] 锚定（tray_numbers 取中间 tokens 重组）
  - **段标题守卫陷阱（bug-070，SIM-38b 必再遇）**：宽守卫 r'^TRAY\s'
    会误杀 RESULTS 表自身列头行（TRAY VAPOR LIQUID...）→ mode 清空
    数据全丢；守卫必须精确枚举段标题动词（SIZING DOWNCOMER/RATING/
    SELECTION/COMPOSITIONS/LOADING）
  - FCC fixture：10 块 = 5 塔 × 主/备单位系两遍；T204B 9 层塔板
  - SIM-37b 三批合计：6 parser 54 测试，4d 估时实际半天
  - 测试 18 项；ruff 持平 445；全量 1177 passed（+18）

- SIM-38a（塔盘数据 PoC，commit 174a82d）：TRAY COMPOSITIONS 单 Section
  - 块结构：TRAY 头行开块（1 塔板 2 列/2 塔板 4 列）+ 组件行 + RATE 行收尾
  - **块边界契约**：空行仅结束组件行区，RATE 行仍属本块（RED 实测：
    空行当块结束 → RATE 行丢）；RATE 行处理完才置 current=None
  - 列对齐：dashes 段起点 = 值列起点；_detect_column_starts 硬编码 8 列
    不可复用，PoC 内联扫描（SIM-38b 可提取公共）
  - X/Y 按奇偶列分液/汽（values[0::2] 液 values[1::2] 汽）
  - fixture 跨版本：dmc 5.01 T102 14 组件 + proii .out 4.17 T1 2 组件
  - 测试 9 项；ruff 持平 445；全量 1186 passed（+9）

- SIM-38b（塔盘数据全量 3 commit，0723577/e8b8e43/a533765，闭环）
  - /1 LOADING：双子表（VAPOR TO/FROM TRAY + LIQUID FROM/TO TRAY）各 12 列；
    REBOILER（无 vapor）/CONDENSER（无 liquid）8 token 行按关键字识别
  - /2 RATING：双版本 9 列（4.17 RESULTS）/10 列（8.x AT SELECTED DESIGN
    TRAY，FF 后多 NP）；单位不同不区分仅取数值
  - /3 COMPOSITIONS 全量：UnitTrayCompositions（UNIT 归属+MOLAR/WEIGHT
    basis）；翻页 (CONT) UNIT 头不切断 section；真实文件 marker 翻页不重复
    （合成测试先写重复 marker 是错的——对齐真实格式后绿）
  - **fixture 事实**：proii .out 是多 problem 拼接 + T1 报告重复 ×2
    （LOADING 2 次、COMPOSITIONS 4 section）；T2/T3 在 INDEX 有条目但
    输出无 section —— 测试预期必须按实际输出对齐
  - 测试 22 项（8+7+7）；ruff 持平 445；全量 1208 passed（+22 累计）
  - 2.5d 估时实际半天

- SIM-39（TODO 收口，commit 6a7b075）：TODO-037/040/044 三项闭环
  - TODO-037（提前 P4）：UnreliableStreamGuard.check → 422
    STREAM_UNRELIABLE_BLOCKED + 流名 sorted；P4 /calculate 入口调用
  - TODO-044：audit detail 增 snapshot_id/snapshot_action（additive 五键
    保留）；SNAPSHOT_TRIGGERS 实为 {INITIATE_CHANGE, RESOLVE_STALE_CHANGED}
    —— 快照在**发起**变更时创建（BEFORE_CHANGE），非 APPLY_CHANGE
  - **bug-071**：快照在 flush 后 add，python-side PK default 不补值，
    audit 读 snapshot_id 得 str(None)；构造时显式 snapshot_id=uuid.uuid4()
  - TODO-040：round-trip 限**可逆段**（head ↔ 不可逆锚点
    p3sim_stream_sign_status_extend，enum ADD VALUE 不可 DROP VALUE）；
    守卫仅 pcs_test URL（默认 URL 是 pcs 开发库——防误降）
  - 测试 13 项；ruff 持平 445；全量 1220 passed + 1 skipped（守卫生效）

- SIM-40（P3.x 收口报告 V1.0，commit 93e4ca4）：**P3.x sprint 闭环**
  - 报告：docs/PCS-P3.2-SIM-P3X-CLOSE-REPORT.md（27 task→commit 映射 +
    验收对照 + TODO 终态 + P4 衔接 5 项）
  - 终态指标：1219 passed + 1 flake(TODO-041) + 1 skip；覆盖率 88%；
    ruff 445 基线制；55 commits
  - TODO 终态：5 闭环（035/037/040/043/044）+ 3 P4 裁决保留（034/041/042）
  - **编号冲突记录**：commit 前缀 p3x-38/39/40 是 V1.0 变更管理系列；
    V1.1 的 38a/38b/39/40 是炼油塔盘/TODO/报告系列——两系列全闭环
  - P4 首批建议：ruff 归零专项 + calculate 入口接 UnreliableStreamGuard

- TODO-045 ruff 归零专项（commit 572cef3，2026-09-13）：**445 → 0，基线制终结**
  - 33 auto-fix + stream_service 常量移位（E402 根因：常量插 import 块中间）
  - + 10 处 E501 手工折行 + 3 处 per-file 豁免（冻结迁移×2 + 一次性脚本）
  - **此后 lint 0 errors 恢复为 commit 前提**（plan §6 原验收）
  - 交接文档入项目目录：.wolf/HANDOFF-2026-09-13.md（用户裁决，不再写 /tmp）
  - 早年遗留 4 个未提交 import 排序文件一并收编（formula_engine 等）

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

## P5 frontend 闭环 / 2026-09-17

- **P5-4 HEAT frontend UI 闭环**（10 commit：5dcf154 / a218564 / 173a7ba
  / 45b15ac / 06802a2 / 4dac093 / 99e0d07 / 361aacf / a31b6a2 / c70a653）
  - types/heat.ts 对齐 V1.3 SPEC §7.11.6 + 后端 OpenAPI 96165e1
  - api/heat.ts HEAT 3 端点（import-htri multipart + get + weight-estimate）
  - HeatComputePage：Upload + 3 Radio（SHELL_TUBE/AIR_COOL/PLATE）+
    source_stream_id Select（OPEN-6）+ result + weight Collapse + extractPcsError
  - StateBadge 扩 4 态子集（DRAFT/IN_APPROVAL/CHECKED/CHECK_REJECTED）
  - MSW HEAT 3 handler（import-htri 201 + get 200/404 + weight-estimate 9 segments）
  - OPEN-4-1 vesselApi + OPEN-4-2 sepEquipApi + routeWrappers 简化
  - OPEN-5 OpenAPI snapshot regen（pcs-backend 102 → 122 paths；drift check pass）
  - 终态指标：51 files / 521 tests passed（vs 上批 48/513）
- **OPEN-9**（gstack browse sandbox 阻断）：`browser-manager.ts` 已支持自动
  `--no-sandbox`，但只在 `CI=1` / `CONTAINER=1` 环境变量触发；本机 Linux 容器
  未设这两个变量 → 一行修复 `CI=1` 即可
- **antd Select 测试标准模式**（PC 前端固定模板，仿 WorkspaceSwitcher）：
  ```tsx
  const selector = document.querySelector('.ant-select-selector') as HTMLElement;
  fireEvent.mouseDown(selector);
  await waitFor(() => { expect(document.querySelector('.ant-select-dropdown')).toBeTruthy(); });
  const dropdown = document.querySelector('.ant-select-dropdown') as HTMLElement;
  expect(within(dropdown).getByText('FEED-101')).toBeTruthy();
  // 选中点击：
  const option = within(dropdown).getByText('FEED-101').closest('.ant-select-item') as HTMLElement;
  fireEvent.click(option);
  ```
  - antd Select 不是原生 `<select>`，`fireEvent.change` 不生效
  - `select.textContent` 不含 dropdown options（dropdown 默认关闭，DOM 外）
  - 必须先 mouseDown → 打开 dropdown → waitFor → within
- **Per-Batch QA Gate（CLAUDE.md 强制）**：每批 sprint 落地后必须跑浏览器
  回归（login + 各 Page 路由 + console 清洁 + 网络无 404）。4 页全跑通
  + 截图入 `.gstack/qa-reports/`（已 gitignore，本地路径）
- **MSW handlers 测试策略**：直接用 `setupServer` + 本地 fetch（不走
  `@mswjs/interceptors`），让 handler 真跑（参数校验 + 响应序列化 + 错误
  envelope 一致性都覆盖）
- **OPEN-7（HEAT import→get 串行优化）**：需后端 `ImportHtriResponse`
  扩充字段（equipment_no + equipment_name + tag_number + exchanger_category +
  duty_w + output_json partial），前端 import() 后免去 get() roundtrip；
  超出 frontend scope，留待下批后端契约变更

## P5 frontend 决策（累积）

- PROJECT_ID / DEV_BEARER 走 `constants/env.ts`（commit 1afa756）；不留 hardcode
- 不动后端（OPEN-4/6/7 集中 frontend；后端契约 96165e1 已闭环）
- 不引新依赖（复用 `api/client.ts` + `api/psv.ts` 模板 + `pages/routeWrappers.tsx`）
- 不动 MSW core（复用现有 17+ handler 模式 + devOnlyMockHandlers 数组追加）
- 字段/枚举/权限/错误码以 OpenAPI + meta API 为准；与 SPEC 冲突时 OpenAPI
  为准并登记 SPEC 修订（V1.3 §12.4）

## P5-3 PSV 二次闭环（2026-09-17）

- **多工况泄放设计**：后端 `PsvCalculateRequest` 是单 scenario 入参
  （types/psv.ts L106-115）；前端通过 `Promise.all(scenarios.map(s =>
  psvApi.calculate({ ...baseReq, relief_scenario: s })))` 并行调用 +
  `responses.reduce((max, r) => r.result.orifice.actual_area_m2 > max... ? r : max)`
  取最大喉径为主导。**前端层聚合**等价于"后端多 scenario 聚合"，不动
  后端契约
- **多 scenario 表单字段隔离**：用 `${scenario}_` 前缀避免 FIRE_D_m
  与 CLOSED_VALVE_D_m 等同名字段冲突；运行时通过 `extractScenarioValues`
  函数按前缀拆分
- **多工况结果对比表**：antd Table 列 `dataIndex: ['result', 'relief_scenario']`
  用数组路径访问嵌套字段（不在 `PsvCalculateResponse` 顶层），高亮 max
  行用 `<Tag color="gold">最大（主导）</Tag>` 金标
- **SUP-P5-PSV-002 安全阀选型前端部分**（V1.0 待评审）：
  - 新增 PsvValveType 4 态 + PsvBodyMaterial 5 态 + OrificeSize 14 态
  - 6 字段 UI 全部在 PsvComputePage 一个 Collapse 分组里（位于"泄放工况"
    之上，按 SPEC §5.1 要求）
  - 联动规则前端实现：先导式/爆破膜式 → 黄色 Alert + 提交按钮 disabled
    （antd Button `disabled` 属性）；blowdown_fraction 越界 → form rules
    validator；orifice_override < 计算孔口 → ORIFICE_ORDER 数组索引对比
  - **后端契约兼容**：3 新字段（valve_type/body_material/orifice_override）
    Pydantic v2 `extra='ignore'` 静默忽略，**老请求格式仍可用**（SUP-P5-PSV-002
    §7.2 向后兼容）；前端不引 break change
- **antd Tabs role-based 查询**：测试中 `screen.getByText(/结果/)` 在
  antd Tabs 里因多匹配失败；改用 `screen.getByRole('tab', { name: '结果' })`
  准确定位（antd Tabs 内 role="tab" 属性）
- **antd Form.Item name 必须**：之前误用 `<InputNumber name="...">` 直
  接放在 Form.Item 里（不绑 form），`form.validateFields()` 拿不到值
  → handleSubmit 提前返回。修正：必须用 `<Form.Item name="blowdown_fraction"
  rules={...}>` 包裹，InputNumber 不带 name
- **测试 timeout 局部调整**：复杂 antd Select dropdown + form 提交流程
  在 5s 默认 timeout 下偶发超时（vitest 全套并发跑慢），用 `it('...',
  async () => {...}, 15000)` 局部扩展 timeout

## SUP-P5-PSV-002 OPEN 项（待评审通过后启动）

- OPEN-10 后端契约扩展：Pydantic `PsvCalculateRequest` 加 3 字段 +
  psv_results 7 列迁移 + Task 18 端点 G7/G8/G9 拦截 + Task 17 孔口
  override 逻辑；后端测试 +15 / E2E +2；前端无需改动（G7/G8/G9 错误码
  解析已闭环）
