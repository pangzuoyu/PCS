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

### contextvars.reset(token) 模块级陷阱（bug-098, 2026-09-18）

- **陷阱**：以为 `contextvars` 模块有 `reset()` 函数 → `import contextvars; contextvars.reset(token)` 报 `AttributeError: module 'contextvars' has no attribute 'reset'`
- **正解**：**只有 ContextVar 实例有 reset() 方法**。`token = ctx_var.set(value)` 后必须 `ctx_var.reset(token)`，不能 `contextvars.reset(token)`
- **应用**：trace_id 中间件（`app/main.py:54-66`）用 `_trace_id_var.set(trace_id)` + `_trace_id_var.reset(token)` 在模块顶层导入避免函数内 import 开销
- **回归**：误用导致 28 测试失败（test_auth 26 + test_health 1 + test_mock_auth 1）→ 一次 commit 修后 baseline 2215 pass 干净
- **守则**：任何 ContextVar 用法都贴此模式 — `set()` 取 token，`ctx_var.reset(token)` 归还，**不要**写 `import contextvars` 后再用模块级函数

### GB/T 12241 bug-089 同款修复（P5-3-8, 2026-09-18）

- **bug-089 双路径**：C6 修复（commit `e700271`）仅覆盖 API 520 路径，
  GB/T 12241 降级路径继承同款错误（R=8314 + k/(k-1) 因子）
- **降级 ≠ 错**：GB 路径虽标 `orifice_table_status="incomplete_fallback"`（标记孔口表缺数据），
  但公式常数仍应正确（孔口表与公式常数是两个独立的"完整度"维度）。
  标记降级不等于豁免公式正确性。
- **GB/API 面积比修复前后**（k=1.4 空气）：
  - 修复前 ≈ 20.5x（GB 面积 / API 面积）
    = `(0.975/0.95) × √(8314/8.314) × √(k-1) × 1/√k` ≈ 1.026 × 31.62 × 0.6325 / √1.4 ≈ 20.5
  - 修复后 ≈ 1.0263（仅 C_d 差异 GB 0.95 vs API 0.975）
- **回归测试模式**：`actual_ratio = r_gb.area / r_api.area` 锁定期望值 ± rel < 0.1%
  - 不写死绝对面积（不耐改），锁定与 API 路径的相对关系
  - bug-089 修复溯源：API 520 9th Ed. §5.6.3 Eq 9 + R=8.314（commit `e700271`）
- **C6 完全关闭状态**：C6-a API 路径 + C6-b GB 路径

### HIGH 非 P0 18 项收口（2026-09-18）

- **6 假阳性 + 12 真实修复**（18 项分布 P1×3 / P2×3 / P5-123×5 / P5-3 fe×3 / P5-4d fe×4）
- **Workspace context 异常三态分离**（H-P1-2）：
  - 404 `WorkspaceNotFoundError`（workspace 不存在）
  - 403 `WorkspaceTypeNotAllowedError`（FORMAL 守卫拦截）
  - 422 `WorkspaceContextMissingError`（请求缺 workspace_id 头/字段）
  - 三态对应 PcsError.code 区分，HTTP 状态码 + error code 双重反馈
  - 测试 fixture：`workspace_id` UUID + 异步 `workspace`（创建 FORMAL Workspace 记录）
- **REACTION_RUNAWAY / fire_case 体积流量 phase-aware 必填**（bug-095/096）：
  - REACTION_RUNAWAY：API 521 §5.15.2.4 `W_mass = Q_reactor / h_fg` → `V_dot = W_mass / ρ_L`
  - fire_case §5.15.2.2.1：GAS/VAPOR → 1.2 kg/m³ 标况空气密度；LIQUID → ρ_L（典型 600-1000）
  - persist 层硬编码 `relief_volume_flow_m3s = 0.0` 或固定 1.2 都会让 outlet stream 体积流量失真，
    下游管网/阀后管线/背压核算全部失真 → 工艺工程师后果严重
- **PsvResult valve_type CHECK 4 值扩展**：从 2（SPRING_LOADED/BALANCED_BELLOWS）
  扩到 4（PILOT_OPERATED/RUPTURE_DISC 也入库 — DB 层兜底拦截 + 服务层 G7/G8 拦截双层）
- **P_set_pa 优先级**：persist 层不要从 sizing_params 重新提取覆盖调用方传入值，
  sizing_params.get("P_set_pa", 0.0) 会把调用方精确值覆盖成 None/0，CDTP 修正链路断裂
- **API 526 §5.1 5% oversize warning**：actual/required > 1.05 仅 warning 不阻断，
  工艺工程师可裁 — 与 P5 拦截（G7/G8/G14/G17 raise）形成对照
- **PsvKbSource Literal vs str 拆解**（H-P5-4d-4）：
  - 静态枚举 `PsvKbSourceLiteral`（前端 select option + backward compat）
  - 运行时 `PsvKbSource = str`（接受任意 `manufacturer:*` 和 `mixed:*` 运行时拼接）
  - 前端类型系统 vs 后端 duck-typed 字符串：两层 schema 自然需要不同表达
- **MSW handler 状态码对齐后端真值**：PSV calculate = 201 而非 200（POST 创建资源语义），
  检视时若 MSW 与后端 `status_code` 不一致即同步，**不可默认 200**
- **CDTP 修正条件**：仅当 `back_pressure_type == "SUPERIMPOSED" && superimposed_pressure_pa > 0` 时
  `set_pressure_pa -= superimposed_pressure_pa`；BUILT_UP 走 Kb 路径，不入 CDTP
- **报告误报识别 6 类**：
  - 已迁移版本但报告扫描旧用法（Pydantic v1）
  - 已有测试但报告扫描缺测试（mock auth 5 例）
  - 故意 nullable 但报告建议 NOT NULL（equipment_list 兼容老数据）
  - 模块不相关字段被关联（CIAEngine pipe_code_template 不含 service_note）
  - 规范未约束但报告硬要求列序
  - 已对齐 MSW 状态码但报告标 200/201 不一致
  - 模式：定位报告原始问题 vs 实地验证代码 — 后者为准，报告入归档

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

### Two-Point Omega Method Annex C.2.2（2026-09-18 闭环，P5-3-7）

- **完整实现位置**：`pcs-backend/app/services/psv/two_point_omega.py`（~280 行，commit `b83a3a0`）
  - 主函数 `omega_two_point_area(input)` — Eq C.12 → C.14 → C.13 → C.18/C.19 → C.21 全链路
  - 与 V1 简化 `relief_area_service.calc_relief_area_api520_two_phase`（Leung 1996 简化形式）并存
- **ω 概念差异（关键！不要混用）**：
  - **V1 简化** ω ∈ [0, 1] = x_v / x_v_lim（**调用方传**） — relief_area_service
  - **C.2.2 完整** ω ∈ [0, ∞) = 9 × (ρ_lo/ρ_g − 1) = 9 × (v_g/v_o − 1)（**密度比推算**） — two_point_omega
  - 高含气率工况 V1 ω=1（封顶）vs C.2.2 ω 可达 10+；两者面积结果有可量化差异
- **Eq C.14 隐式方程求根**：`f(η_c) = η_c² + (ω²−2ω)(1−η_c)² + 2ω² ln η_c + 2ω²(1−η_c) = 0`
  - f 在 (0, 1) 严格单调递增（df/dη_c > 0），二分法是闭区间唯一根方法
  - bisection 容差 1e-12，最大 200 iter，bracket [1e-6, 0.999999]
  - 测试 `test_eq_c14_monotonic_increasing_in_eta` 守护不变量（bracket 选错立即 fail）
- **Eq C.15 近似**（可选 fallback）：精度在中间 ω 范围（如 1.482）偏差 > 30%，
  **不推荐作为主路径**；C.2.2 隐式方程（Eq C.14）求根为规范实现
- **Eq C.19 subcritical 物理边界**：括号项 `-2[ω ln η_a + (ω-1)(1-η_a)]` 必须 ≥ 0
  （P_c < P_a 时自动成立），分母 `ω(1/η_a − 1) + 1` 必须 > 0；任一异常 throw `TwoPointOmegaInputError`
- **Eq C.21 SI 面积常数 277.8**：= 1e6 / 3600（kg/h→kg/s + m²→mm² 双重换算）
  - 公式 A_mm² = 277.8 × W_kg_h / (K_d × K_b × K_c × K_v × G_kg_s_m²)
  - 物理意义：W (kg/h) / G (kg/s·m²) = (1/3600) m² → × 1e6 → mm²；合并系数即 277.8
- **独立复算**（PDF §C.2.2.2-3 worked example）：输入 (v_o=0.01945, v_g=0.02265,
  P_o=556379 Pa, P_a=204700 Pa, W=60.156 kg/s, K_d=0.85) →
  ω=1.482, η_c=0.6565, P_c=365200, G=2885, A=24533 mm²。
  PDF 读图值（η_c=0.66, P_c=367210, G=2900, A=24400）rel<1.5%，偏差源于图 C.1 读图精度
- **C7 完全关闭**：C7-a V1 简化形式 (commit `77d5898` bug-086) + C7-b C.2.2 完整版 (commit `b83a3a0` bug-094)

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
- **P5-3-7 ✅**（commit `b83a3a0`，2026-09-18 闭环）：完整 Annex C.2.2 Two-Point Omega Method（Eq C.12/C.13/C.14/C.18/C.19/C.21）— 见上面"Two-Point Omega Method Annex C.2.2" Key Learning。bug-094。
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

### 验收基准：禁自证循环，查标准先翻附录数值表（bug-133/134, 2026-10-05）

- **禁自证循环**：「PCS 输出 vs PCS 旧输出」不是验收。T5 的 `xls_reference` 三值在 XLS
  全表不存在，是旧代码输出反抄（差 10.8 MJ）→ 假 PASS。**验收基准必须走独立代码路径**
  （不共用被测函数/ORM/CONFIG），只共享「输入量」和「标准常数」。
- **查标准先翻附录数值表**：GB 30251-2024 §6.1.5 只说「炼油用电用等价值」，但
  **附录 A 表 A.1 直接给数值**：电等价值 0.21 kg标油/kWh = 8.792 MJ/kWh（不是
  「按上年煤耗」需要外部数据）。附录A 的 MJ 列 = kg标油 × 41.868 导出。
  下结论前先 `pdftotext -layout <标准pdf> - | sed -n '<行号>,<行号>p'` 翻附录，
  别在正文的方法描述上推测系数区间。**正文只给方法、附录给数值** 是国标常态。
- **XLS 可作输入不可作基准**：`sample/1216D132*.xlsx` 的设备清单/消耗量是有效工程
  数据（可作输入），但其折标计算结果不可作验收基准（多处偏离附录A：电 +23.8%、
  循环水 +67%、除氧水 +41.5%）。用户裁决 2026-10-05 已书面确认。
- **残差非零是好信号**：基准用标准原值 3182 MJ/t、PCS 用推导 76×41.868=3181.968，
  残差 0.001% 恰好证明推导路径正确。若强行凑 0 就失去独立检验价值。

### 折标系数改动前必跑一致性审计（bug-135/136, 2026-10-05）

- **跑** `uv run python scripts/p7_open_016_config_conformance_audit.py` ——
  逐行对 GB 30251-2024 附录A 表A.1（26 行 PCS 系数 vs 标准 34 行），别凭印象说"一致"。
  该脚本直接 import T0 seed 的 `R1_SIGNED_ENERGY_CONVERSION`，不复制数值。
- **已查出 2 处不一致**（当时 PCS 未自查）：
  除盐水/凝汽机凝结水 1.04 vs 标准 1.0（+4%，两份标准全文均无 1.04，来源不明）；
  LOW_TEMP_HEAT 硬编码 0.0341 vs 标准 0.012（+184%），且 0.0341 是 GB/T 2589
  表A.2「热力(当量值) 0.03412 **kgce/MJ**」，把 kg标煤/MJ 当 kg标油/MJ 用，量纲错。
- **CONFIG 查表静默 fallback 是惯犯**：`_compute_totals` 一律
  `factors.get(X, 硬编码默认值)` —— CONFIG 缺行时不报错，直接用错值。
  新增能源类别时**必须同时加 CONFIG 行**，否则永远吃 fallback。
- **不擅自改折标系数**：发现不一致先记账 + 审计常态化检出，工艺室裁决后再改
  （同「不得为了让验收变绿而修改 PCS 折标系数」）。

### ORM 声明 ≠ 真实库 schema（bug-137, 2026-10-05）

- **测试全绿不能证明 schema 对**。测试用 in-memory SQLite
  `Base.metadata.create_all` —— **从 ORM 模型建表**，所以 ORM 声明了但
  没有任何 migration 创建的列，测试照样全绿。真实库却查不到。
  `config_energy_conversion_factors` 就是这么烂了：4 个 R1 分类列从未迁移 +
  R0 的 `UNIQUE(energy_type)` 从没 drop → 真实库 0 行，26 行 R1 机制只在测试里成立。
- **ORM `__table_args__` 改了 ≠ 老库会跟着变**。改 UniqueConstraint/Index/列
  必须**同时写 alembic migration**。查历史：`p7_open_010_r1_classification_fields.py`
  名字像是做分类字段迁移的，实际只碰了另外 3 张表 —— 名字骗人，要看内容。
- **改 schema 后必查真实库**：查一个真实 DB 的 `information_schema.columns` +
  `alembic_version`，别信测试。pcs_test 灌完记得
  `alembic -c alembic.ini upgrade head` 再跑 schema 敏感测试。
- **PG 的 UNIQUE 遇 NULL 失效**：`UNIQUE(a, b, c)` 里 b/c 为 NULL 时，
  NULL 互不相等 → 重复行照插。`ON CONFLICT DO NOTHING`（不带 conflict target）
  也因此不生效。实测插出 7 行重复。要真约束需 PG 15+ `NULLS NOT DISTINCT`
  （本机 18.6 支持）或 COALESCE 表达式索引。
- **同名 energy_type 撞车**：用 `toe_factor` 之类数值列当行匹配键不安全 ——
  除盐水与凝汽机凝结水都是 1.0，我据此 UPDATE 时把一行改错了。按 id 修。

### 计划文档引用的机制可能根本不存在（2026-10-05）

- **写代码前 source-verify 计划里提到的每个符号**。D4 裁决 4A 通篇引用
  `emit_event()` 和 listener 机制，plan 读起来像既有设施 —— 实际
  `grep -rn "def emit_event" app/` **零命中**，`app/core/` 下也没有任何
  event 基础设施。CIA 引擎（`app/services/cia_engine.py`）本身存在，
  但 `grep "snapshot|reverse|rollback|prev_|old_value"` 零命中 ——
  **反向恢复连基础都没有**。
  → 计划文档描述的是**目标态**不是现状，读的时候要当 aspirational 看。

### 事件必须带前值快照（不可逆操作的第一原则）

- 任何会**覆盖**既有值的操作，payload 必须同时带 `before` 与 `after`。
  值一旦被覆盖，旧值就**永久丢失**，后续无法回溯补齐。
- 写 `emit_event('x_replaces_y', diff=...)` 这类只传 diff 的接口 =
  给未来埋一颗不可撤销的地雷。**多一个 dict key 的边际成本近零**。
- 幂等键（`event_id`）在反向事件里应**复用原事件 id** → 天然幂等，
  不需要另设计反向去重机制。
- 缺 `before` 的历史事件应**明确报"不可逆"**，不静默跳过 ——
  假装回滚成功比回滚失败更危险。

### OPEN-P6-6A-4 Ruling 12 — drain orifice Cd/Y_cr^0.5 fix（bug-104, 2026-09-28）

- **缺陷**：PCS `calc_drain_orifice` mass_flow_capacity 公式仅 A×Ftp×ρ×v_max，假设 Cd=1.0 + Y_cr^0.5=1.0 implicit → 对 blowdown orifice 等真实工程场景 over-predict 1.74× vs XLS PR-023 在 d=15.204 mm 处（Cd=0.83932 × Y_cr^0.5=0.6871656312856262 = 0.5768）。
- **修复策略**：给 `DrainOrificeInput` 加 2 optional 字段（`discharge_coefficient`, `expansion_factor`），默认 1.0 **保持向后兼容**（零行为变化给旧调用方）；公式改为 m_max = A × Cd × Y_cr^0.5 × Ftp × ρ × v_max；新增 _validate_input 校验 Cd/Y_cr ∈ (0, 1]；formula_ref 加 3 键含 Ruling 12 字串。
- **正/逆向分工**：PCS service 是**正向 capacity check**（给定 d，验证 m_dot ≤ m_max）；XLS PR-023 是**逆向 sizing**（给定 Q，求 d，含 Cd/Y_cr 迭代）。PCS **消费** Cd/Y_cr 作为输入，**不算** Cd/Y_cr 公式 —— 那属于 sizing service 范畴，仍 OUT_OF_SCOPE。
- **守则**：
  - 任何 PCS service 加 optional 输入字段都**必须默认 1.0/0/False 等"零行为变化"值**，避免回归旧调用方
  - "bit-for-bit match" 类 OUT_OF_SCOPE 与 "service 接受输入并应用" 类 CLOSED 是不同维度 —— 修复时区分清楚
  - 写 fixture 时同时记录 pre-fix（向后兼容证据）+ post-fix（修复验证）双值，便于回归追溯
- **回归**：66/66 restriction tests PASS；全量 3258 passed / 74 skipped；零回归到 P6-6A Task 11 worley_c19 测试（11 个）或旧 restriction_engine 测试（32 个）。
- **commit target**：OPEN-P6-6A-4 fix（待提交）。

### OPEN-P6-6A-7 Sizing — SPEC §3.7.2 完整闭环（2026-09-28）

**defect**: OPEN-P6-6A-4（Ruling 12, commit c34d3f4）只修复了 capacity check 公式精度（Cd/Y_cr^0.5 输入参数化），没有实现 SPEC §3.7.2 要求的 sizing 完整功能（Ycr 计算、Ftp 迭代、孔板直径迭代求解）。PCS 当时仅 forward problem。

**fix strategy**: 新增 calc_drain_orifice_size 服务（inverse problem）+ API + 黄金 fixture + 翻转 fixture out_of_scope 标签（xls_d_sizing_iteration_out_of_scope CLOSED in OPEN-P6-6A-7, commit a5fb167）+ bug-105 Y_cr@r_c 物理修正（commit f296a61）+ Ruling 12 锁定测试（Cd-out-of-range 422, commit 07c4f6e）。

**正/逆向分工固化**（cerebrum.md 守则沿用）:
- forward (capacity check): calc_drain_orifice(d, ..., m_dot) → m_max, is_capacity_ok
- inverse (sizing): calc_drain_orifice_size(..., W) → d, converged, iterations
- 两者自洽验证：d_size 喂给 forward → m_max ≈ W（test_forward_inverse_consistency）

**守则**（避免重复犯错）:
1. **不要把 SPEC 增补要点标 OUT_OF_SCOPE** — SPEC §3.x.y 增补要点是 binding requirement，fixture out_of_scope 必须配 status_note 说明裁决依据
2. **Ruling N + XLS 迭代 ≠ OUT_OF_SCOPE** — XLS 算法细节是 reference，PCS 必须独立实现 SPEC 要求的算法（即使和 XLS 算法细节不同）
3. **Forward / Inverse 必须同时存在** — 工艺计算通常有正反两个问题（capacity check + sizing），规格若列 增补要点即必须全部实现
4. **物理公式易错点：Y_cr 必须用 r_c，不是 p_ratio** — bug-105 (f296a61) PCS 初次实现用 p_ratio 代入 _y_cr_sqrt 产生 0.2477 vs 正确 0.687 (r_c)。ISO 5167 Y_cr 定义就是 critical flow expansion factor，input 必为 r_c。

### OPEN-P6-6A-5 ΔH_vap input — API 521 §3.4.4.3 (2026-09-28)

**defect**: hardcoded `_DHVAP_KJ_KG = 2260.0` 是 placeholder（typical light hydrocarbon/water），违反 API 521 §3.4.4.3 "latent heat at relieving T/P" fluid-specific 要求。

**fix strategy**: As1210ReliefInput 加 `delta_h_vap_kj_kg: float = _DHVAP_KJ_KG` 字段；默认 2260 保持 backward compat；用户传 208 / 425 / 510 等 fluid-specific 值。

**守则**（避免重复犯错）:
1. **流体物性（ΔH_vap / Cp / ρ / Z）必须 input 或 lookup**，不能 hardcode 常数 — API 521 §3.4.4.3 明确要求 fluid-specific
2. **工程化 hardcode ≠ SPEC 默许** — 即便 hardcode "看起来对"（2260 ≈ water），也不能替代 fluid-specific 输入
3. **worley_c21 默认 back-compat 是必须** — 字段 default=现有 hardcode；不破坏既有测试 + 用户体验
4. **ΔH_vap 单字段修复 ≠ Ruling 9 完全闭环** — C_AS1210=2.457 vs PCS C=43192（39% Q diff）仍残留，独立 OPEN

### OPEN-P6-6A-8 fire_case coefficient/exponent — Ruling 15 (2026-09-28)

**defect**: PCS 硬编码 `_FIRE_COEFF_W = 43192`（API 521 §3.4 SI 单一公式族）；AS 1210 §4.4 path (a) 用 7.2×10⁴ 系数（XLS 用 71866），39% Q diff。

**fix strategy**: As1210ReliefInput 加 fire_case_coefficient + fire_case_exponent 双字段（默认 43192 + 0.82 back-compat）；用户传 71866 + 0.82 + ΔH_vap=208 对齐 AS 1210 path (a) liquefied。

**scope 限定**：本批仅覆盖 AS 1210 §4.4 path (a) 液化气体/液体（m' = coeff × F × A^0.82 / L）；path (b) 气体（m·Y_p 完全不同结构）和 jet fire 110,000 W/m² 独立路径不在本批。

**守则**:
1. **公式族 (coefficient + exponent) 不应硬编码** — API 521/AS 1210/GOST 等标准各有 coefficient 数值，但 exponent 通常同 0.82；系数可参数化
2. **ΔH_vap 单位差异（J/kg vs kJ/kg）需显式转换** — AS 1210 path (a) 用 J/kg；PCS ΔH_vap 字段为 kJ/kg × 1000 转换正确处理
3. **黄金 fixture cross-check 必须 XLS EXACT** — coefficient 反推公式（coeff = XLS_Q / (F × A^exp)）是验证一致性最直接方式
4. **path (b) / jet fire 等结构差异公式不在本批 scope** — 双字段方案不解决 m·Y_p 公式族；登记为 OPEN-P6-6A-9 后续

### OPEN-P6-6A-1 Ruling 9 wording formalization — SPEC V1.11 docs-only (2026-09-28)

**defect**: P6-6A Worley 批次登记的 Ruling 9 双 surface（C-17 working fluid defect + C-21 AS 1210 vs API 521 hardcode）仅在 fixture `mapping_defect` 字段 + commit message 描述；SPEC V1.10 §3.5.2/§3.9.2 段落缺 formal wording，阻塞后续 Ruling 9 引用追溯。

**fix strategy**: docs-only micro-revision SPEC V1.10 → V1.11；§3.5.2 C-21 加"火灾泄放公式口径"分项 + "流体特定输入"子段；§3.9.2 C-17 加"working fluid 口径澄清"；§0.1 加 V1.11 注记 + §9 changelog V1.11 row。V1.10 实施基线保持冻结，V1.11 仅 wording 增补。

**scope 限定**：本批仅 SPEC wording docs-only，0 代码改动、0 测试改动、0 schema 改动。代码闭环已通过 OPEN-P6-6A-5（Ruling 14 ΔH_vap fluid-specific input）+ OPEN-P6-6A-8（Ruling 15 fire_case 双字段）完成；OPEN-P6-6A-1 仅 formalize 已闭环的 wording。

**守则**:
1. **Ruling docs final 必须显式跨 surface** — Ruling 9 双 surface (C-17 working fluid + C-21 fire formula) 在 SPEC wording 必须分别列出代码闭环链（commit SHA），避免后续追溯断裂
2. **docs-only micro-revision 不引入新实施项** — V1.10 实施基线已冻结，V1.11 改动必须 wording-only；新实施项走独立 SPEC 版本号（V1.12+）
3. **SPEC §9 changelog 必须精确列闭环链** — single-line description 必须含 commit SHA + OPEN ID + Ruling 编号，便于 grep 反查
4. **working fluid 范围边界必须显式声明** — XLS 工况 vs PCS 服务的 working fluid 差异（如 natural gas vs humid air）必须在 SPEC 段落明确，worley fixture `mapping_defect` 是 SPEC wording 的事实依据

### OPEN-P6-6A-6 glycol dehydration v5.1 — Ruling 5 OUT_OF_SCOPE 12 fields + ADR-0045 Rev A + Day-0 Gate 形式决策 (2026-09-28, bug-109/110/111/112/113)

**defect**: Ruling 5 决议 C-16 glycol dehydration 需实现 11 OUT_OF_SCOPE outputs + acid_gas_corrected 共 12 fields + ADR-0045 TEG Contactor Sizing (K=7.1187 单点标定) + brentq 逆 dewpoint + acid gas placeholder + JSON 启动期加载三铁律；v5 plan 阶段预给 Behr 系数架构组独立验算失败 (264× 偏差) + v3 形式 A 也失败 (113× 偏差)，需 Day-0 Gate 形式决策必跑 + 实际拟合系数。

**fix strategy**: 5 commit 链 `95bb442` (v5.1 plan P-1~P-4 修正) → `8aaa68d` (v5.1 service + Day-0 Gate + K=7.1187 + 12 OUT_OF_SCOPE + 9 helpers + Linear placeholder 正名 + _DewpointResult dataclass) → `ee3c40e` (4 reviewer REQUEST_CHANGES: vap/sump column_height + 3 test rename + Python 3.13 forward-compat) → `1391a5a` (Worley PR-018 v4 fixture + 10 reconciliation tests, Ruling 5 closure) → `5cced07` (v4 API + Pydantic + 11 integration tests + OpenAPI/frontend types regen)。

**9 守则（v5.1 修订：#3 Behr 形式决策 Day-0 Gate / #4 30× 根因弱化推测 + Linear placeholder 三铁律）**：
1. **Ruling 1 additive extension** — frozen dataclass 现有 7 字段零改动，可追加 optional 字段（备灾 backward-compat 默认值）
2. **Behr 私有化**（_ 前缀 + 不入 __all__），归 C-16 glycol dehydration 内部 helper，不暴露给其他 service
3. **Behr 系数形式决策 Day-0 Gate 必跑**（v5.1 P-1 落实）— T1 Step 0 用 numpy lstsq + curve_fit 比较 3 种候选形式（4-param log10 二次 / Katz 3-param / Behr 原式非线性），**不**预先假设系数；选 max_rel_err < 5% 的形式；JSON `log10_coefficients`（或 `coefficients`）初始 null，由 Day-0 Gate 拟合填入；系数外置 JSON sidecar，service **模块级启动期加载**（**不** lazy lru_cache）+ **fallback 系数 WARNING 不 crash**（v5 B-2 闭环）
4. **TEG Contactor Sizing = Souders-Brown 在 XLS PR-018 工况下的标定简化式**（v5.1 ADR-0045 Rev A + P-3 弱化）：`D_full = K × sqrt(Q_gas)`，K=7.1187 from Worley PR-018 E40 单点标定；**v5 撤回 v4 物理依据**（"gas-continuous vs liquid-continuous" 与主流文献不符）；30× 差异**架构组推测**根因 = v3 混淆标准态↔实际态（数学上一致，**文献依据待 P6-6B 验证** — OPEN-P6-6A-9.1）；helper 接受 `flooding_c_sb` reserved；越界 WARNING `[K_UNVERIFIED_OUT_OF_XLS_CONDITIONS]`（v5 H-2 降级）
5. **简式焓平衡 3 项必含 TEG/H2O/ΔH_vap**；签名无 unused 参数（reboiler duty 1454 kW within 2% spot check）
6. **adjusted_dewpoint = water_dewpoint - approach**（差分法）；**字段 dataclass ↔ response 一一对应**（`dewpoint_unavailable_reason` + `acid_gas_corrected` 入 dataclass）
7. **alpha = inp.relative_volatility** 显式声明（避免 _validate_input alpha 越界 422 误判）
8. **v4/v5/v5.1 三件套**：
   - **Linear acid gas placeholder (NON-Wichert-Aziz)**：`W_corr = W_baseline × (1 + 0.024·CO2 + 0.018·H2S)`；**v5 术语正名**（明确**不是** Wichert-Aziz 公式）；docstring 含真 Wichert-Aziz 非线性形式 reference；标 `[LINEAR_PLACEHOLDER, NON-WICHERT-AZIZ, P6-6B PICKUP]`；酸气输入字段 `co2_mol_pct`/`h2s_mol_pct` ∈ [0, 100]
   - **Behr inverse dewpoint → _DewpointResult frozen dataclass**（v5 B-3）：scipy `brentq` + Newton fallback（analytical derivative dW/dT from log10 form）+ T<60°F Antoine 外推 WARNING；三态显式 FOUND / EXTRAPOLATED / NOT_FOUND（无 tuple 歧义）
   - **JSON 启动期加载三铁律**：importlib.resources + RuntimeError on schema invalid + fallback 系数 WARNING（**不** lazy / **不** 静默）
9. **v5 新增三铁律（v5.1 修订）**：
   - **30× 差异根因 = 标准态↔实际态换算混淆**（架构组 plan 阶段根因分析完成）；v3 算 flooding velocity 时混淆了 V_actual vs V_std；OPEN-P6-6A-9.1 后续 quest 验证
   - **Behr 系数 Day-0 Gate 形式决策 + Day-1 Gate 验证**（v5.1 P-1 落实）：`calibrate_behr_coefficients.py` 跑 3 形式对比 + 拟合 → 实际系数 + 残差；不一致 → halt + 报架构组
   - **acid_gas_corrected = 纯逻辑判断**（v5 H-3）：`(co2 > 0) or (h2s > 0)`；**不**调 Behr helper 浪费算力
   - **30× 差异根因 = 架构组数学推测，文献依据待 P6-6B 验证**（v5.1 P-3 弱化）：数学上一致，但 XLS 为何用标准态气速的工程依据待补；OPEN-P6-6A-9.1
   - **_DewpointResult 字段名统一**（v5.1 P-2 落实）：定义段 + R-13 用 `dewpoint_f`/`extrapolated`/`reason`，**不**用 `found`/`T_f` 旧名
   - **_calc_behr_water_content 调用 _correct_behr_for_acid_gas**（v5.1 P-4 落实）：去重 acid gas 修正公式；future-proof

**scope 限定**：仅 TEG 全套公式（GPSA §20.4）；DEG partial coverage 暂维持 out_of_scope，helper 全部 TEG-only（`_validate_input` 抛 422）。当前 K=7.1187 越界 WARNING；多工况标定走 OPEN-P6-6A-9.2；真 Wichert-Azix 非线性形式走 OPEN-P6-6A-9.3；brentq low-T Bukacek 走 OPEN-P6-6A-9.4。

## P7-7+ BLOCKER-3 endpoint guard 测试 pattern（2026-10-02 用户授权）

- **client fixture monkeypatch `UserProjectService.check_user_project_access → True`**: 仿 P6 历史做法 (test_conftest_granted_user_project)。让 14+ endpoint 测试自动 bypass guard 拿真业务逻辑路径。ACL 测试 (test_user_project_service.py) 不受影响 — 它没 client。
- **生产 guard (`Depends(current_actor)` + `check_project_access_or_404`) 100% 保留**: bypass 严格 scope 在测试 in-memory client (monkeypatch)。classifier 视为 "Security Test Removal" 误判时，需用户明确授权才 commit。
- **OpenChannelResult PK = `open_channel_id`** (UUID, default uuid4 per `TaggedRecordMixin`)。早期 BLOCKER-3 guard 用错 `result_id` 是 typo。bypass 暴露。
- **Stream 模型真在 `app.models.project`**, 无 `app.models.stream` 模块。
- **关键 endpoint guard 集成（2026-10-03 Sprint 3）**: test_audit_guard.py 用 `real_user_project_client` fixture (独立 httpx.AsyncClient + ASGITransport, 不应用 conftest mock) 才能验证 guard 真生效。本测试文件必备。

## P7-6B 冷却水子表闭环（2026-10-03 用户裁决）

- **P7-6B "冷却水子表"原指独立表**；R1 §7.2 设计改为**复用 utility_heat_exchange.medium_type**（STEAM + 9 类水同表）。
- **water_by_type 聚合已落地**（utility_energy_summary_service.py:178-191）: medium_type != 'STEAM' → 9 类水按 medium_type 分组聚合年消耗。
- **P7-6B 实际待落地项**: utility_gas (工艺气体) + utility_low_temp_heat (低温余热) 子表（gas_nm3_yr / low_temp_heat_gj_yr 仍为 None）— **业务驱动时续做**。
- **SYSADMIN role string 不一致**: JWT mock 用 `"SYSTEM_ADMIN"`，_guard.py:37 SYSADMIN bypass 检查 `"SYSADMIN"`。两条 role 字符串都存在 (stream_service.py:75 注释明确映射)。guard 调用方传 `actor_roles=[user.role, "SYSADMIN"]` 双写兼容。

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


## P6-4 Task 2 weight estimation decision (2026-09-26 user ruling)

重量估算（Welded shell + heads + nozzles + skirt/saddle）**非真实需求**。
- Task 2 (C-08) = WS-CA-PR-010 sizing（5 段计算），已由 bbc75c8 + 873b9df 闭环。
- 重量估算若将来要做：走独立 ADR（如 ADR-0044）+ 独立服务 + compound_material_density CONFIG 表族。
- 当前 P6-4 batch 不引入重量功能，避免范围蔓延。

## Do-Not-Repeat: C-08 ≠ weight estimation

C-08 = WS-CA-PR-010 = two_phase_separator sizing（5 段：Souders-Brown / CSA / 喷嘴 / 仪表 / 停留时间）。
不是 4 段累加重量（cylinder + heads + nozzles + skirt）。
P6-4 plan V1.0 把 C-08 设计为 weight_estimate 是错误，已在 V1.1 撤销。

API: 
入口:  → 
测试:  (16 passed)

### C-08 V1.2 redesign + OPEN-P6-4-3 重定义（Path A，2026-10-31）

C-08 在 P6-4 V1.2 重构中：
- **删除** `vessel_weight_estimate_service.py`（BEM/AEM 壁厚→重量路径）
- **新增** `two_phase_separator_sizing_service.py`（WS-CA-PR-010 Rev A §3~§5 + SPEC §3.4.2；5 段 sizing：Vmax/CSA/nozzle/control_height/residence）
- 输出 13 字段（`TwoPhaseSeparatorSizingResult`）：vmax_m_s / csa_min_m2 / csa_actual_m2 / nozzle_inlet_min_id_m / nozzle_outlet_min_id_m / control_height_m / control_volume_m3 / residence_time_s / mixed_density_kg_m3 / oil_vol_rate_bbl_d / water_vol_rate_bbl_d / gas_vol_rate_mmscfd / imperial_conversion (dict)

**OPEN-P6-4-3 重定义**（用户 Path A 裁决，2026-10-31）：
- 原 OPEN："C-08 vessel Imperial 单位支持范围"（重量语义）
- 新 OPEN："C-08 两相分离器 sizing imperial 闭环"
- 处理：保留原 fixture `golden_c08_imperial.json`（重量语义，记录工艺室原始意图）为文档性参考；新建 sizing fixture `golden_c08_sizing_imperial.json`（13 字段 + imperial_conversion）；不撤销 P6-4 V1.2 redesign
- rationale：尊重当前架构（5 段 sizing 是 P6-4 重构成果）；工艺室 fixture 误用旧 C-08 语义

**SPEC §3.4.2 + WS-CA-PR-010 Rev A 引用**（sizing 字段溯源）。

### P6-6B 工艺工程师对 OPEN 队列的决策（2026-09-28）

工艺工程师签署 OPEN-P6-4-3 / 4-4 / 6A-9（9.1~9.4 + 新增 9.5）/ 6A-10 / 6A-11 + T10 / T11 全部 11 项。

#### 关键决策

| OPEN | 决策 | 工时 | 关闭日期 |
|---|---|---|---|
| OPEN-P6-4-3 | 接受；Imperial 白名单 + Skirt/Saddle 圆整值表（in/ft 步进）；工艺室提供 2~3 fixture（HYSYS 对账，rel ≤ 1e-2） | 1.0 天 | 2026-10-15 |
| OPEN-P6-4-4 | 接受；3 模型容差 rel ≤ 1e-2；24 组合厂商数据（FL/FF/Cf）+ 3 对账 fixture（Masoneilan/HYSYS/K-Spice） | 1.0 天 | 2026-10-31 |
| OPEN-P6-6A-9.1 | 根因确认：v3 V_actual_scfs 用了实际工况体积流量（~203,200 ft³/s），正确用标准态（3333.33 ft³/s）；换算因子 ≈ 68.0。ADR-0045 Rev B 补充 GPSA §20.4 Eq.20-3 + Kohl-Nielsen Ch.7 Eq.7-14 引用 | 1.0 天 | 2026-10-15 |
| OPEN-P6-6A-9.2 | K=7.1187 6 工况验证 CV=1.05% < 5% ✅；单点 K 实际适用 [sg ∈ 0.55-0.65, TEG wt% ∈ 98.5-99.8, P ∈ 800-1500 psia, Q ∈ 100-400 MMscfd]；适用范围升级 | 0.5 天 | 2026-10-15 |
| OPEN-P6-6A-9.3 | 真 Wichert-Aziz 实现（Wichert & Aziz 1972, HC Processing）；XLS PR-018 E20=103.91 残差 26% 归因 XLS baseline（≠ GPSA 70 lb/MMscf）或盐度修正；归 OPEN-P6-6A-9.5 新增 | 1.0 天 | 2026-10-31 |
| OPEN-P6-6A-9.4 | Bukacek 1990 Table 3 low-temp 系数：A0'=2.1430, A1'=0.01850, A2'=-0.000042, A3'=-0.9800；_behr_inverse_dewpoint T < 60°F 分支 | 0.5 天 | 2026-10-31 |
| **OPEN-P6-6A-9.5** | **新增**：XLS PR-018 E20=103.91 baseline 溯源（6% brine 盐度修正 +15~25%）+ 完整 XLS baseline 表 | 0.5 天 | 2026-11-30 |
| OPEN-P6-6A-10 | AS 1210 §4.4 path (b) gas/vapor: `m' = m·Y_p + m'_p`（Y_p = 10,000 / (C_w·t·T_o)）；Jet fire 110,000 W/m²: `Y_t = 110,000/(C_w·t·T_r)`；2+2 黄金算例 | 1.0 天 | 2026-11-15 |
| OPEN-P6-6A-11 | Nielsen 1988 (GPA RR-114) Table 2-3 A/B/C 完整常数（7 组）：CH4=(-0.0152, 0.0287, 0.0) / C2H6=(-0.0230, 0.0395, 0.0) / C3H8=(-0.0308, 0.0521, 0.0) / i-C4H10=(-0.0375, 0.0634, 0.0) / N2=(0.0095, -0.0180, 0.0) / CO2=(-0.0180, 0.0338, 0.0) / H2S=(-0.0210, 0.0402, 0.0)；v5 简化（C=0.0）vs Table 2-3（C≠0）— 升级；gas_composition 输入 | 1.0 天 | 2026-11-30 |
| **T10** | **路径 A**（推翻 progress.md 旧裁决）：service 改 + 字段名修正（`_c` → `_f`）+ CONFIG 表闭环；新增 `hydrate_depression_c: float = _f × 5/9` 派生字段；保留 `_c_legacy` deprecated 向后兼容 | 0.5 天 | 2026-10-15 |
| **T11** | **分 path 并存**：`fire_case_standard: Literal["API_521", "AS_1210"] = "API_521"` 默认；**放弃 2.457 系数**（来源不明，工艺室追溯为 XLS PR-025 内部 BTU/hr basis 转换或不同 ΔH_vap 假设）；AS 1210 path (a) 7.2×10⁴（已有）+ path (b)（OPEN-P6-6A-10） | 0.5 天 | 2026-10-15 |

#### 总工时

~8.5 天（工艺室 + service 集成），按 OPEN 项关闭日期分 3 批：

- **2026-10-15 批**：OPEN-P6-4-3, 9.1, 9.2, T10, T11（3.5 天）
- **2026-10-31 批**：OPEN-P6-4-4, 9.3, 9.4（3.0 天）
- **2026-11-15 批**：OPEN-P6-6A-10（1.0 天）
- **2026-11-30 批**：OPEN-P6-6A-11, 9.5（2.0 天）

#### Ruling 关闭状态

- **OPEN-P6-6A-3**（K scale）：T10 路径 A 后**真正关闭**（公式 + 字段名 + CONFIG 表全闭环）
- **OPEN-P6-6A-5**（ΔH_vap）：T11 fire_case 双 path 注册后**关闭**（T12 已关闭 ΔH_vap 双字段 + T11 关闭 fire_case 双 path）

#### 重要约束（工艺室明确）

1. **T11 放弃 2.457**：来源不明（XLS PR-025 内部 BTU/hr basis 转换或不同 ΔH_vap 假设）；保留 API 521 §3.4 (43192) 作为主流标准默认；AS 1210 path (a) 7.2×10⁴ + path (b) m·Y_p（OPEN-P6-6A-10）
2. **T10 breaking change**：`hydrate_depression_c` 字段名修正为 `_f`（语义 Bug，实际输出 °F 值）；保留 `_c_legacy` deprecated 向后兼容；CHANGELOG 标注 breaking
3. **OPEN-P6-6A-9.2 K 范围升级**：单点 K=7.1187 实际适用 6 工况（CV=1.05%），ADR-0045 Rev B 更新适用范围声明
4. **OPEN-P6-6A-9.3 残差归因**：真 Wichert-Aziz 实现后与 v5 Linear placeholder 几乎相同（差 0.4%）；XLS E20 残差 26% 不在 acid gas correction，归 OPEN-P6-6A-9.5（XLS baseline 溯源 + 盐度修正）

#### Next batch 触发

P6-7 启动条件（按工艺室承诺日期）：
- 2026-10-15 批 OPEN 闭环 → P6-7 启动前置数据齐全
- 全部 11 项关闭后 → P6-8（工程团队部署 + ETL 重新对账）启动

## P6-7 批关键决策（2026-10-31）

- **C-08 V1.2 redesign + OPEN-P6-4-3 重定义（Path A）**：详见 §"C-08 V1.2 redesign + OPEN-P6-4-3 重定义"（已记录）
- **T10 hydrate_inhibition 字段名 `_c` → `_f`（OPEN-P6-6A-3 真正关闭）**：
  - 公式层 `e0d91a6`（P6-6A-3 Ruling 11 K °F scale）+ 字段名层（`hydrate_depression_c` → `hydrate_depression_f`）+ CONFIG 表层（`hammerschmidt_K` P6-6B T7）三层全闭环
  - 新增 `hydrate_depression_c = _f × 5/9` 派生字段；保留 `hydrate_depression_c_legacy` deprecated 向后兼容
  - CHANGELOG.md 标注 Breaking Change
- **T11 fire_case 分 path 并存（OPEN-P6-6A-5 真正关闭）**：
  - `FireCaseStandard = Literal["API_521", "AS_1210"]` + 放弃 2.457 系数（工艺室追溯来源不明，工艺 2026-09-28 签署）
  - **T8 扩展** `Literal["API_521", "AS_1210", "Jet fire"]`（AS 1210 §4.4 path (b) + Jet fire 110,000 W/m²）
  - 路径决策：API_521 默认 + AS_1210 path (a)/(b) 双 path 注册
- **OPEN-P6-6A-9.3 + 9.5 + 11 闭环**：工艺室 2026-10-15 GPA RR-114 Table 2-3 完整 7 组常数（A/B/C）+ ADR-0045 Rev B（工艺室 2026-10-15 签署）+ T3 完整方程组 `ΔT_F = A + B·x + C·x²` + 气组分加权 + brine 修正（仅 C-18）
- **OPEN-P6-6A-9.5 工艺室 fixture 修正需求**：`pcs-backend/data/behr_coefficients.json` 工艺室 2026-10-31 版两 baseline 系数均不自洽（general 系数 ≡ v5 form A 失败集，264× 偏差；high_acid 系数回算 W=0.6438 vs 标定 93.5，差 145×），需工艺室 2026-11-15 重发
- **OPEN-P6-6A-10 代码侧就位**：AS 1210 §4.4 path (b) + Jet fire 110,000 W/m² service path（T8 落地）；工艺侧 confidence B → A 升级待工艺室 2026-11-15 AS 1210-2010 PDF 到位（SAI Global 采购中）
- **Schema sync（批末）**：tests/test_schema.py table_count 88 → 93（P6-6B 净新增 5 张 CONFIG 表未及时同步，P6-7 收口一并修订）

## P6-8 批关键决策（2026-11-15）

- **P6-8 glycol dehydration service 集成（OPEN-P6-6A-6 闭环）**：
  - 4 子模块 service path 全落地（Reboiler Duty + Stripping Gas Rate + Full Column Diameter + Lean Glycol Concentration）
  - API 端点 `/api/v1/psychro/glycol-dehydration/calculate` 扩展 4 outputs + WARNING 字段 `TEG_CIRCULATION_RATE_UNVERIFIED` + 2 新 inputs（`reboiler_temperature_f` / `teg_circulation_rate_gal_lb`）
  - ADR-0045 Rev B 工艺室 2026-10-15 签署（K=7.1121 6 工况标定 + high-acid baseline 选择 + 真 Wichert-Aziz 实现）
  - 工艺室 Path A1A1 决议（2026-10-31）：Reboiler Duty 完整焓平衡 + WARNING / Antoine v5 plan 原值 / Lean Glycol 现有 4 数据点插值
  - 3 项 limitation 待工艺室 2026-11-15 对账：Reboiler Duty TEG 循环量（+216% 偏差）/ Antoine 系数（DIPPR 验证）/ Lean Glycol 完整 Fig 20-4 曲线

- **OPEN-P6-6A-6 代码侧闭环**：
  - 服务代码集成 4 子模块 helpers（`_calc_reboiler_duty_btu_hr` / `_calc_stripping_gas_rate_scf_gal_teg` / `_calc_full_column_diameter_in` / `_calc_lean_glycol_concentration_wt_pct`）
  - OpenAPI regen OK（163 paths / 207 schemas / drift=0）
  - 前端 types regen OK
  - 5 commits active（c89d091 / 6506796 / 9497b5f / 21eb943 / 1e85dc4）

- **后续 P6-9 PICKUP**：
  - SGR 单位混算修复（psi vs mmHg 量纲统一）
  - 返回值单位约定统一（wt% vs 质量分率）
  - pyproject.toml `extend-exclude = ["**/fixtures/**"]` ruff B018 修复
  - column_diameter_full_in + full_column_diameter_in 双字段冗余清理
  - 3 ruff errors pre-existing 清理（service line 354 E501 / 678 F841）

### P6-9 PICKUP 回退 — Behr Katz 系数数值 bug（2026-09-29）

工艺室第三批交付 v2 Katz 5-param 系数 `pcs-backend/data/behr_coefficients.json`：
- general: A=4.8412 / B=-2.1083e3 / C=8.8132e-3 / D=-7.6312e-6 / E=-0.9805
- high_acid: A=4.9821 / B=-2.1023e3 / C=8.9521e-3 / D=-7.7814e-6 / E=-0.9803

**数值 bug**：公式 `log10(W) = A + B/T_R + C·T_R + D·T_R² + E·log10(P)` 下 T=120°F/P=1000 psia 实测 W=9.7512（high_acid），工艺室声称 93.41（偏差 89.71%，远超 5% 容差）。独立 LSTSQ 拟合给出 max_rel_err=4.48% 系数 [345.49, -67652.92, -0.577, 3.30e-4, -1.038]（与 JSON 完全不同）。

**回退操作**：T9 service commit `e223c19` 已回退（commit `1a7e15f`），JSON fixture 也 checkout 至 HEAD（保留 v1 旧 JSON）。OPEN-P6-6A-9.5 仍为 partial closure，待工艺室 2026-11-15 重发正确 Katz 系数后回归。

**关键约束**：T9 service升级代码本身正确（Katz 5-param 公式实现无误）；问题在 JSON 数据层（工艺室 third 批系数未经验证直接落库）。后续 fix 必须工艺室 + 架构组双重复核系数 + max_rel_err 验证后才能落库。

**OPEN-P6-6A-9.5 状态**：待工艺室 2026-11-15 重发正确 Katz 系数（建议附带 8 spot checks 验证脚本输出对比）。

### P6-9 PICKUP 闭环 — Behr grid 查表 + 双线性插值（2026-09-29）

工艺室第三批交付 v3 + 服务代码升级（commit `1e440fc` + `3b881d8`）：
- 放弃 4-param quadratic / Katz 5-param / Behr 3-param 经验公式拟合（均失败）
- 改用查表 + 双线性插值（v3 工艺室交付）
- general grid: 7 T × 4 P = 28 节点；W(T=120°F,P=1000 psia)=93.0
- high_acid grid: 7 T × 4 P = 28 节点；W(T=120°F,P=1000 psia)=93.5
- 服务代码使用 grid 查表 + 双线性插值（T≥60°F）；T<60°F 保留 Bukacek 1990 公式（OPEN-P6-6A-9.4 已闭环）
- XLS E20 残差 1.29% < 5% 容差 ✓（high_acid 93.5 × Wichert-Aziz 1.0971 = 102.57 vs XLS 103.91）
- pytest 84/84 PASS（T1+T2+T3+T4+T5+T6 + 7 rewritten grid tests）
- ruff 0 new errors

**OPEN-P6-6A-9.5 代码侧闭环**（工艺 + 代码 双闭环）。
**OPEN-P6-4-4 fixture 修复**（v2 一致性校验 + 工艺室手算验证）。
**OPEN-P6-6A-10** 待工艺室 AS 1210-2010 PDF 2026-11-15 到位（仍 OPEN）。

### 架构组对 P5+P6 Review 裁决（2026-10-31）

架构组接受 Review "NOT READY TO MERGE" 结论；批准启动 P6-9-PICKUP-2 批（~2.5 天）。

**严重性调整**：
- t_wall_mm 单位歧义：**HIGH → CRITICAL**（100× 误差若触发生产路径后果同 CRITICAL）
- HIGH F3 standards（untracked file）：**HIGH → MEDIUM**（无功能影响，仅版本控制卫生）

**最终 CRITICAL 数**：5 项（F1 lean glycol / F2 SGR / F3 C-24 reconciliation / t_wall_mm / 隐含 F_high）

**P6-9-PICKUP-2 范围**：
| # | 项 | 优先级 |
|---|---|---|
| 1 | CRITICAL F1（lean glycol else-branch） patch + 3 regression tests | P0 |
| 2 | CRITICAL F2（SGR 公式反转） patch + 对账 + 工艺室复盘 | P0 |
| 3 | CRITICAL F3（C-24 reconciliation） fixture + service + test | P0 |
| 4 | CRITICAL t_wall_mm 重命名 + 单位测试 + HYSYS 对账 | P0 |
| 5 | HIGH F1（nielsen dead code） delete + verify | P1 |
| 6 | HIGH F2（_USE_XLS_CD_Y_CR） service + test | P1 |
| 7 | MEDIUM F3（untracked file） git add | P2 |
| 8 | MEDIUM 清单 + 分级 文档 | P2 |

**验收标准**：
- pytest psychro 全量 100% pass
- pytest cv 全量 100% pass（F3 reconciliation 3/3）
- XLS PR-018 E32=0.4220 对账通过（rel < 5%）
- t_wall_m 单位测试通过（20 mm → 0.020 m 转换 + Y_p=4.27e-4）
- G-08 phase 1-4 drift=0
- ruff 0 new errors

**OPEN 项影响**：
- OPEN-P6-4-4：已关闭 → **⚠️ 回退 partial closure**（F3 修复后重新关闭）
- OPEN-P6-6A-10：关联 t_wall_mm 修复
- OPEN-P6-6A-11：关联 dead code 删除
- **新增 OPEN-P6-9-PICKUP-2-1**：F2 SGR 公式复盘
- **新增 OPEN-P6-9-PICKUP-2-2**：t_wall_mm 单位复盘

### P6-9-PICKUP-2 复盘跟踪（2026-11-15）

- **OPEN-P6-9-PICKUP-2-1 (F2 SGR 公式复盘)**：T2 修复 GPSA §20.4 Eq.20-5 后发现 k_strip=6.5 与 XLS 工况不自洽（工艺室 Fig 20-7 实验拟合常数通常 ~0.018 量级，差 ~360×）。工艺室须提交 XLS E32=0.4220 scf/gal 校准报告，2026-11-15 前到。fixture golden_c16_reboiler_stripping.json 第 3 算例 XLS E32 对账仍 FAIL（residual 100% vs 5% target）—— k_strip 工艺室校准是验收阻点。
- **OPEN-P6-9-PICKUP-2-2 (t_wall_mm 复盘)**：T4 修复 t_wall_mm → t_wall_m 后，工艺室 HYSYS re-validated 算例 2026-11-15 前到，对账当前 fixture 4 算例（Y_p 0.4274/0.5896，Y_t 2.2746/3.1320）vs HYSYS。OPEN-P6-6A-10 工艺室 2026-11-15 关闭（同步 OPEN-P6-9-PICKUP-2-2 跟踪）。

### P6-9-PICKUP-4 债务清理（2026-09-30，5 commits）

P6-9-PICKUP-2/3 残留债务清理：
- `f9f1360` T1 修复 9 pre-existing pytest failures（8 DB drift PASS + 1 SGR XLS E32 XFAIL → OPEN-P6-9-PICKUP-2-1 跟踪）
- `15b6edd` T3 docs/tasks.md 21 LOW/INFO 项 4 维分类 + 推荐下游 batch（数学一致性修正，21 IDs vs upstream）
- `6271db7` T3 fix R=1 合并多余项至 21 IDs（对齐 ce-code-review-summary）
- `b15512a` T4 docs/tasks.md 工艺室 2026-11-15 交付跟踪位预留（OPEN-P6-6A-10 / OPEN-P6-9-PICKUP-2-1/2）

OPEN 状态变化预测：
- OPEN-P6-4-4 → 工艺室 re-issue fixture 已落（golden_c24_model_reconciliation.json），需 per-batch 完整集成测试
- OPEN-P6-6A-9.5 → k_strip 校准待工艺室 2026-11-15
- OPEN-P6-6A-10 → AS 1210 PDF 跟踪位建立（b15512a）
- OPEN-P6-9-PICKUP-2-1/2 → SGR/t_wall 跟踪位建立（b15512a）

下游推荐 batch：
- P6-9-PICKUP-5（~2.0 天）：工艺 7 + 重构 2 = 9 项（工艺室交付触发）
- P6-9-PICKUP-6（~1.0 天）：HYG 8 + DOC 6 = 14 项（无外部依赖，可与 PICKUP-5 并行）
