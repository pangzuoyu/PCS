## 代码审查结果

**范围:** `3e5ae90` -> 工作树（local-aligned，38 个变更文件，`full.diff` 7519 行）
**分支 / HEAD:** `worktree-s4-0-events` @ `cae5bce9e3411ff1199713aca88c83f427a1d089`
**计划:** `docs/sprint4-plan-2026-10-05.md`（`plan_source: explicit`）
**意图:** P7 Sprint 4 交付 PCS 的「供应商实际数据 -> 偏差报告 -> 核算闭环」及其依赖的事件骨架。含 5 个 Task 之外的两项计划外工作：`742215d` 电机额定功率规则改为对轴功率卡 API 610 分档下限（1.25 / 1.15 / 1.10），`cae5bce` 新增 PUMP_DESIGN 并写回 `design_parameters_json`，闭合「设计值无写入方」缺口。
**模式:** `markdown report-only` —— **本次审查未修改被审树的任何文件**（`mode.apply_local=false`，调用未携带 apply 请求）。Stage 5c 完全跳过，下列每一条可执行发现都只作为待决项交给调用方，没有任何一条被自动落盘。

**审查员团队（10 位，全部落地）:**
- `correctness` / `security` / `adversarial` —— always-on；新端点经 `require_roles` + `check_project_access_or_404`（IDOR 边界），DESIGNER/REVIEWER 角色分离
- `project-standards` —— 治理全部 38 个变更文件的唯一标准源（根 `CLAUDE.md`）
- `testing` / `maintainability` / `performance` / `api-contract` / `data-migration` / `reliability` —— 2601 行可执行非测试变更、6 个新端点、2 个 alembic 迁移、事件幂等与 payload 冲突语义

**跨模型通道未运行。** 本机未安装任何异族审查通道（codex / grok / cursor-agent / opencode 均 absent；唯一剩余选项 claude 与宿主同族，无法通过独立性检查），对抗性视角由 in-process `adversarial-reviewer` 承担。因此**没有任何一条发现有经过独立跨模型印证**：`security` / `adversarial` / `reliability` / `correctness` 的相互印证只记入 `reviewers` 名单，不提升置信锚点，也不构成 Stage 5b 的验证跳过依据。

---

### Triage Groups

| Group | Findings | Context | Preferred Resolution | Why |
|-------|----------|---------|----------------------|-----|
| G1 事件总线的事务边界与幂等语义（decision-gate） | #3, #2, #10, #15, #28 | `events.py` 的幂等 claim、派发顺序与事务回滚是同一处设计选择的三种表现；CIA 侧 `cia_engine` 的吞异常与之叠加 | 先定 #3 的 `event_id` 派生口径（它决定 #2/#10 的事务边界怎么切，也决定 P8 反向恢复能否复用原 id），再一次改完 `events.py` 的 `_claim` 与派发顺序（#2 + #10 同一次编辑），最后收 #28 的返回值语义与 #15 的 docstring 路径 | #3 是决策闸：id 口径不定，事务边界就会返工 |
| G2 确认/校核门禁可被绕过（decision-gate） | #8, #5 | 两条同源但修法不同：#8 是产品口径，#5 是状态机守卫 | 先由产品定 #8（确认是否必须要求全部参数都有实测值），再一次落地 #5 的 PENDING_CONFIRM 前置守卫，并同步改那三条把未守卫行为写死的测试 | 若 #5 按错误口径实现，守卫会在正确的确认流程上误拦 |
| G3 导出层的转义与阻塞（apply-queue） | #1, #6, #7, #13 | `entries` 无上限、xlsx 公式注入、PDF markup 崩溃、同步导出堵事件循环，四条落在同两个导出函数上 | 先给 #1 的 `entries` 定上限（同时压住两个导出器的内存放大），再在共享的行构造处一次做完 xlsx 前缀转义（#6）与 PDF markup 转义（#7），最后把两个导出器移出事件循环（#13） | 四条共用一处行构造；先定上限再改转义可避免同一段代码改两遍 |
| G4 偏差引擎的判定与取值（apply-queue） | #29, #31, #24, #19 | 偏差规则表、报告构造与输入取值三处都在本次新增的 supplier 域内；#19 的文档漂移由 `742215d` 引起 | 先修 #29 与 #31 两处取值/派发错误（都在 `evaluate`/`build_report` 的分支上，一次编辑即可），再按 #24 在 schema 层收紧实测值类型，最后统一 #19 的电机规则文档表述 | 前两条改行为、后两条改契约与文档，行为先行，文档随行为一起收口 |
| G5 契约与登记：SPEC / 错误码 / 协议（decision-gate） | #11, #25, #30, #4, #23 | 项目规则要求「与 SPEC 冲突以 OpenAPI 为准并登记修订」，本次多处改了对外契约却没留下登记：端点路径、第 4 档结论、buglog、错误码注册表 | 先补两条 SPEC 登记（#11 端点路径、#25 第 4 档结论），再补 #30 的 buglog 条目与 #4 的错误码注册，然后按 #23 补一份可发现的参数词表 | 登记类动作彼此独立可并行，但都应先于 schema 变更落地，否则登记内容会与最终契约不符 |
| G6 设计值落库与迁移（decision-gate） | #14, #32, #12, #27, #18 | `p7_s4_001`/`p7_s4_002` 迁移、PUMP_DESIGN 回填脚本与 `apply_design_parameters` 落库函数是同一份数据的三条路径 | 先定 #14 回填是否允许覆盖已有非空 `design_parameters_json`（决定要不要 dry-run 与确认闸），随 #32 补上部署后验证 SQL，再修 #12 的 downgrade 幂等与 #27 的 WHERE 重复，最后清 #18 的过期缺口注释 | 覆盖策略未定之前跑回填有数据风险，决策先于执行；#32 与 #14 配套 |
| G7 测试与死代码清理（apply-queue） | #21, #17, #20, #34 | 机械清理项：一处覆盖缺口的用例、两处零调用对象、一处会误导的包 docstring | 按 #21 补 WARNING 不阻断确认的用例，顺手删 #17 的 `_cell()`、#20 的 `_RULE_INDEX` 与 #34 的 `excel_import_service` 宣称，一次提交完成 | 四项都无行为风险，可与任何一批改动并行提交，不阻塞其他组 |
| G8 CIA 状态机解耦的异常与守卫（apply-queue） | #9, #22 | `cia_engine` 的 `except Exception: continue` 与那条已失效的静态守卫测试指向同一个解耦风险 | 先修 #9 的吞异常（收窄 `except` 并按记录包 savepoint），再更新 #22 的守卫匹配串使其真正能失败 | #22 的守卫本来就抓不到 #9，先修守卫会给人虚假的安全感 |
| G9 计划外行为规则登记（decision-gate） | #33, #35 | 两次提交引入了用户可见的判定/落库行为规则，均由用户裁决驱动并已在 ledger 记录，但不在 5 个 Task 之内 | 由维护者决定是否在 `docs/sprint4-plan-2026-10-05.md` 的 Task 2/3 下补追溯行；不改代码 | 两条都是文档追溯决策而非缺陷，合并成一组一次决定即可 |

> 分组只是分诊视角，**不是 apply 队列**。调用方按主题批量处理时，必须先与 Actionable 队列求交集：#3、#8、#14、#23、#28 属人工决策项，自动化修复器应停在这些条目前。
### P1 -- High / 高危（11 条，0 条 P0）

| # | File | Issue | Reviewer | Confidence |
|---|------|-------|----------|------------|
| 1 | `pcs-backend/app/schemas/supplier.py:30` | `entries` 无 `max_length`，单次 PUT 可造出任意大的报告，两个导出器都整体物化进内存 | performance | 100 |
| 2 | `pcs-backend/app/services/events.py:165` | `_claim` 把调用方整个事务回滚，并对外谎报成并发冲突 | reliability, testing | 100 |
| 3 | `pcs-backend/app/services/events.py:96` | 事件幂等结构性不可达：每个 producer 都现生成 `uuid4()`，去重表与 before 快照链永远看不到重投 | adversarial, reliability | 100 |
| 4 | `pcs-backend/app/services/supplier/actual_data_service.py:27` | 两个新端点的错误码未进 `/api/v1/meta/error-codes` 注册表（工厂间接层击穿 AST 扫描） | api-contract | 100 |
| 5 | `pcs-backend/app/services/supplier/confirmation_service.py:98` | `pass_check`/`reject_check` 无状态前置条件，REVIEWER 可把从未录入的设备直推 CONFIRMED | correctness, security | 100 |
| 6 | `pcs-backend/app/services/supplier/deviation_report.py:208` | [A03/CWE-1236] Excel 导出把设计人可控的参数名写进活公式单元格（实测 data_type `f`） | security | 100 |
| 7 | `pcs-backend/app/services/supplier/deviation_report.py:277` | PDF 导出把参数名/单位原样插进 reportlab `Paragraph`，markup 或控制字符即触发未处理 500 | adversarial, reliability, security | 100 |
| 8 | `pcs-backend/app/services/supplier/deviation_report.py:92` | 确认门逐行 fail-closed，但覆盖面 fail-open：只录一个参数就能确认整台设备 | adversarial | 100 |
| 9 | `pcs-backend/app/services/cia_engine.py:173` | 吞掉异常后，半应用的 FSM 转移被提交，无审计行、无快照 | reliability | 75 |
| 10 | `pcs-backend/app/services/events.py:232` | 幂等 claim 先于派发 flush，listener 抛错也留下「已处理」的持久记录，且该路径零测试 | reliability, testing | 75 |
| 11 | `spec/工艺专用综合计算软件需求规格说明书 Web版 P7.md:145` | 五个端点实际发布在 `/api/v1/equipment/...`，冻结 SPEC 记的是 `/api/v1/equipment-list/...`，且未登记修订 | api-contract | 75 |

- **#1**（`manual` -> `downstream-resolver`）—— `ActualDataEntryRequest.entries` 只有 `min_length=1`，`app/main.py` 未装任何 body-size 中间件（`grep add_middleware` 零命中；唯一的 `MAX_UPLOAD_BYTES` 只挂在 `imports.py` 的 multipart 上）。本分支实测：1,000 行 xlsx 197.7 ms / pdf 753.4 ms，5,000 行 xlsx 2,663.6 ms / pdf 5,064.1 ms，成本线性。爆炸半径不止报告本身：`pass_check` 还把同一份无界 `actual_data_json` 深拷贝进 `event_idempotency.before_json`（`confirmation_service.py:101-106`），而该表无保留策略。**需要什么：** 给 schema 加领域上限（`max_length=200` 足够，`PUMP_DESIGN` 单台机泵只有 7 个参数），`normalize_entries` 同步加闸，导出侧防御性截断并打「已截断，共 N 行」标记行；注意 `max_length` 本身不封 body，若前置网关无 body 上限，持久修法是给这个 router 加 `Content-Length` 守卫。
- **#2**（`gated_auto` -> `downstream-resolver`，**protected subject: data-loss**）—— `_claim` 里的 `session.flush()` 冲刷的是**调用方整个待写状态**，不只是新插的 claim 行。调用方自己任何约束冲突（审计行、lineage 插入、设备更新）都会被这里接住，改名成 `EVENT_ID_CONFLICT / 并发 claim 冲突`，然后 `await session.rollback()` 把事务开始以来的一切写入全部丢弃。`pass_check` 恰好在 `emit_event` 前 flush 了 `actual_data_status=CONFIRMED`（`confirmation_service.py:98-99`），而 CIA 扫描的整个循环跑在一个事务里 —— 一次被误判的 IntegrityError 就抹掉本轮已转移的全部记录，外层 `except Exception: continue` 让操作者只看到「部分成功」。**需要什么：** 优先把 `session.rollback()` 换成 savepoint（`session.begin_nested()`），这是设计层面的破坏性；并补 `test_concurrent_claim_collision_rolls_back_and_skips_dispatch`，其中第 (3) 条断言（调用方那笔业务写入确实被回滚）是本发现的核心，现在没有任何测试观察得到它。
- **#3**（`manual` -> `human`，**决策项**）—— 去重表、`payload_hash` 冲突检测、SAVEPOINT-free 竞态处理，全都为「同一个 event_id 被重投」而建；但 `confirmation_service.py:80-81`、`:97-99`、`cia_engine.py:110-112` 三处都现生成 `uuid4()`，没有任何生产调用方能重投。设计人双击「通过」或客户端在丢响应后重试，`pass_check`（本身又无状态前置条件）就会第二次跑并发出第二个 `actual_data_replaces_design`。P8 反向恢复会看到同一台设备两个事件，第二个的 `before` 等于第一个的 `after`，按序恢复会把实际数据写回设计位，原始设计值永久丢失。**需要什么：** 这是一个 id 口径决策，需要人来定：把 `event_id` 改为从业务操作确定性派生（如 `uuid.uuid5(NS_EVENT, f"replaces_design:{equipment_id}:{payload_hash}")`）。定之前不动 #2/#10 的事务边界，否则返工。
- **#4**（`gated_auto` -> `downstream-resolver`，**protected subject: public-contract**）—— `meta_service.py:311` 的扫描器只匹配 call target 字面为 `PcsError` 的 `ast.Raise` 节点；`actual_data_service._validation_error` 与 `confirmation_service._error` 都是**返回**一个 `PcsError`（我已核对 `meta_service.py:305-314`），于是 `ACTUAL_DATA_VALIDATION` 与 `DEVIATION_BLOCKS_CONFIRMATION` 永远进不了注册表（`tests/api/v1/test_supplier_actual_data_api.py:156` 断言前者确实出现在 422 body 里）。项目规则把 meta API 定为错误码权威源，客户端按它建 code -> `ui_behavior` 映射，这两条会直接掉进兜底分支。**需要什么：** 推荐局部修法 —— 在 8 个 `_validation_error`/`_error` 调用点内联 raise，让现有扫描器照常识别（与 160 处既有写法一致）；另一条路是让扫描器额外走 `return PcsError(code=<Constant>)`，能修整类问题但要动共享组件并自带回归测试。无论哪条，都要重跑扫描器确认两个码出现，并加一条断言注册表含新码的测试。
- **#5**（`manual` -> `downstream-resolver`）—— `pass_check` 的第一条语句就是 `equipment.actual_data_status = CONFIRMED`（`confirmation_service.py:98`，我已核对 86-99 行整段无任何 `if`），端点侧唯一闸是 `require_roles(actor, *_CHECK_ROLES)`。持项目访问权的 REVIEWER 可把 `NOT_ENTERED`（没人录过一个值、没生成过偏差报告、没提交过）直推 CONFIRMED，而 `can_confirm` 这道 fail-closed 门只在 `confirm_actual_data` 里，这条路径根本不到。结果状态正是 `record_actual_data` 认定的锁（`ACTUAL_DATA_LOCKED`），本该填数据的设计人被永久冻结。`reject_check` 是镜像缺口：能把 CONFIRMED 无条件退回 PENDING_CONFIRM，重新打开录入通道。**需要什么：** 按仓库既有 guard 形状在服务边界加前置：`if equipment.actual_data_status != PENDING_CONFIRM: raise _error(..., status=409)`，再重跑 `build_report`/`can_confirm`；同形状守卫也加到 `reject_check`。注意这会打红 `test_pass_check_marks_confirmed` 等四条把未守卫行为写死的测试，fixture 需补一次 `confirm_actual_data`。
- **#6**（`gated_auto` -> `downstream-resolver`，**protected subject: injection**）—— `ActualDataEntry.name` 只限 1-100 字符、无字符类限制，`build_report` 按 `for name in actual` 原样带进 `ws.append([...])`；openpyxl 不转义前导 `=`。端到端实测：`name = "=cmd|'/c calc'!A0"` 导出的工作簿回读为 `B2 "=cmd|'/c calc'!A0" f`，`f` 即 openpyxl 的公式数据类型。写入角色（DESIGNER / PROCESS_CONTROLLER）与读取角色（VIEWER 及任何下游收件人）不同，这是一条**跨角色的存储型投递链**。**需要什么：** 在写单元格前统一加 OWASP 前导单引号前缀（前导 `= + - @ \t \r` 命中），应用到 `report.tag_number`、`row.parameter`、`row.unit`；前缀优于拒绝，因为参数名是中文工程术语，收紧校验会无收益地打断既有调用方。
- **#7**（`gated_auto` -> `downstream-resolver`，**protected subject: injection**）—— `reportlab.platypus.Paragraph` 默认解析 mini-HTML markup，而 `row.parameter`、`row.unit`、`report.tag_number` 都来自设计人。实测导出参数名 `<img src="/etc/hostname" width="10"/>` 抛出 `UnidentifiedImageError ... fileName='/etc/hostname'`，即导出路径真的在服务端打开了攻击者命名的路径（CWE-73 本地文件读取原语）；`ImageReader` 也接受 `http://` / `https://`，同一原语即为对内网的 SSRF。现实上限是「必须可解析为图片，否则请求 500」，但对可达/不可达主机返回不同结果仍是一次内网探测。同样的数据经 JSON 与 xlsx 出口正常渲染 —— 只有 PDF 崩。**需要什么：** 对所有 `Paragraph(...)` 实参（含 `blocking_reason`）套 `xml.sax.saxutils.escape`，让 markup 按字面渲染；表头是静态列名，可不动。
- **#8**（`manual` -> `human`，**决策项**）—— `deviation_report.py:84` 的行集合恰好等于设计人敲进去的键集合，`can_confirm`（`:164-167`）唯一的空集守卫是「行数为 0」。所以只录一个 `效率`（95% 带内）-> 报告一行、QUALIFIED、`can_confirm` True -> CONFIRMED 并发出带全量设计值的 `actual_data_replaces_design`。SPEC §3.2.4(2) 其余五条（扬程、NPSHr、电机选型、转速复核、材质）从未录入、从未判定，记录却对所有下游与 P8 反向恢复链显示「已确认」。第 4 档 UNVERDICTABLE 防的是「进了报告但没判」，对「根本没进报告」无能为力。**需要什么：** 产品先定：确认是否要求该设备应检参数集全部有实测值。最省的落法是让 `build_report` 为 `SPEC_RULES` 中每条匹配到该设备设计键的规则都补一行，缺实测值即显式 UNVERDICTABLE（复用现有 fail-closed 档，无需新门禁逻辑）；前提是「应检参数集可从设计值推导」，这对泵成立，对非泵设备需要显式声明。
- **#9**（`manual` -> `downstream-resolver`）—— `StateMachineService.transition` 先在 `state_machine.py:323-329` 改 `sign_status`/`change_pending_since` 并在 `:348` flush，**之后**才做快照与审计（`:349+`）。此后任何异常（快照写失败、审计插入撞约束、连接丢失）都让 ORM 对象已在 session 中被改坏；`cia_engine.py:173` 的裸 `except Exception: continue` 跳到下一条，末尾 `await self.session.flush()`（`:130`）把 STALE 标记连同残缺状态一起提交。本次 diff 之前，被吞掉的调用在抛错前不写任何东西，吞掉是无害的；把它改走 `emit_event`（会插入 claim 并让 FSM 在 `:348` flush）才让半写变得可达。**需要什么：** `except` 收窄为 `(InvalidTransition, RoleForbidden)`，并把每条记录的转移包进 `async with session.begin_nested()`，让失败回滚到该记录转移前的状态。
- **#10**（`manual` -> `downstream-resolver`）—— claim 在 `events.py:162` 就 flush，`for listener in _LISTENERS.get(event_type, []): await listener(event)`（`:231-232`）在其后且无任何补偿。`CIAEngine._scan_one_class` 提供了活的可达路径：`_mark_stale_via_fsm` 调 `fsm.transition`，对已过 CHECKED/CHANGED 的记录抛 `InvalidTransition`，被外层吞掉并让事务提交 —— 数据库里每个被跳过的记录都留下一行断言「`cia_mark_stale` 转移发生过」的 `event_idempotency`，而它根本没发生。P8 的反向恢复或后续审计一旦信任该表就会跳过这些记录。模型 docstring 声称的不变量（`system.py:258-260`「同一 event_id 重复投递时 listener 一次都不再被调用」）在这个顺序下并不成立。**需要什么：** 把提交点移到派发之后（listener 失败时由 savepoint 单独回滚 claim 行）；最低限度把 claim 拆成 `claimed_at` / `dispatched_at`，让表记录派发结果而不是插入。
- **#11**（`manual` -> `downstream-resolver`）—— SPEC 的公开 API 表把整个供应商数据面列在 `/api/v1/equipment-list/` 下，而 `app/api/v1/supplier.py:58` 声明 `APIRouter(prefix="/equipment", tags=["supplier"])`，五个路径全部发在 `/api/v1/equipment/`；`equip_list.py:39` 证明 SPEC 那个前缀是另一个真实挂载的 router，新路径在其下不可达。按 SPEC 写的客户端必然 404，而这里的 404 与「设备不存在」不可区分（`_load_equipment` 故意把 not-found 与 no-access 折叠成同一响应）。`git diff <base> -- spec/` 为空，权威文档与已发布契约不一致且无裁决留痕；SPEC 还列了一条 `actual-data/import`（Excel 批量导入），S4-1 裁决明确不做，同样未登记。**需要什么：** 代码不动，登记修订：把 SPEC 表这五条改成 `/api/v1/equipment/` 前缀，把 `actual-data/import` 行标注为「S4-1 裁决不实现」或删除，并按同文件既有 `SPEC-ADD-001` 体例加可追溯的修订条目。
### P2 -- Moderate / 中等（19 条）

| # | File | Issue | Reviewer | Confidence |
|---|------|-------|----------|------------|
| 12 | `pcs-backend/alembic/versions/p7_s4_001_event_idempotency.py:60` | downgrade 非幂等且与自己的 docstring 矛盾；仓库幂等闸根本不扫 `p7_s4_*` | data-migration | 100 |
| 13 | `pcs-backend/app/api/v1/supplier.py:235` | `export_excel`/`export_pdf` 是 CPU-bound 同步函数，被 `async def` 端点直接调用，堵死整个 worker 事件循环 | performance | 100 |
| 14 | `pcs-backend/app/services/equip_list/pump_design_data.py:138` | 回填无条件覆盖已有非空 `design_parameters_json`，无 dry-run、无确认闸 | data-migration | 100 |
| 15 | `pcs-backend/app/services/events.py:22` | docstring 仍让读者从 `app.core.events` 导入 —— 本 diff 已把该模块移出 `app/core/` | maintainability | 100 |
| 17 | `pcs-backend/app/services/supplier/deviation_report.py:189` | 死助手 `_cell()`，零调用方（Pass-Through Method） | maintainability | 100 |
| 18 | `pcs-backend/app/services/supplier/deviation_report.py:7` | 「已知缺口：design_parameters_json 无写入方」被本 diff 自己新增的写入方推翻 | maintainability | 100 |
| 19 | `pcs-backend/app/services/supplier/deviation_service.py:11` | `742215d` 之后规则表文档漂移两处：docstring 仍写 SYMMETRIC_BAND ±10%，测试 docstring 仍在描述已废止口径 | maintainability, testing | 100 |
| 20 | `pcs-backend/app/services/supplier/deviation_service.py:166` | 死索引 `_RULE_INDEX` 构建一次后从未被读 | maintainability | 100 |
| 21 | `pcs-backend/tests/services/supplier/test_deviation_report.py:90` | `test_can_confirm_when_all_qualified_or_warning` 名不副实：数据实际只产出 QUALIFIED，WARNING 不阻断确认零覆盖 | testing | 100 |
| 22 | `pcs-backend/tests/test_cia_event_decoupling.py:155` | 静态守卫的匹配串 `self.fsm.transition(` 在 `cia_engine.py` 中已不存在，断言不可失败 | testing | 100 |
| 23 | `pcs-backend/app/schemas/supplier.py:22` | 写侧接受任意自由参数名，读侧是封闭规则集，契约里没有任何东西告诉客户端哪些 key 可判 | api-contract | 75 |
| 24 | `pcs-backend/app/schemas/supplier.py:23` | [A03/CWE-20] `value` 的严格数值契约只靠 Pydantic 松散强制，服务层自己的字符串/布尔拒绝在 API 路径上不可达 | security | 75 |
| 25 | `pcs-backend/app/schemas/supplier.py:73` | 第 4 档 UNVERDICTABLE 与 SPEC/UI-SPEC 的 3 档冲突未按项目规则登记 SPEC 修订 | project-standards | 75 |
| 27 | `pcs-backend/app/services/equip_list/pump_design_data.py:124` | 泵记录 WHERE 子句在 `apply_design_parameters` 与其种子脚本间逐字重复 | maintainability | 75 |
| 28 | `pcs-backend/app/services/events.py:238` | 无 listener 时 `emit_event` 仍报派发成功；CIA 扫描的计数与是否真的标记无关 | adversarial | 75 |
| 29 | `pcs-backend/app/services/supplier/deviation_report.py:104` | `design_value is None` 短路抢在 kind 派发之前，MANUAL_CHECK 行丢掉 `requires_manual_check` 并报出误导性 note | correctness | 75 |
| 30 | `pcs-backend/app/services/supplier/deviation_service.py:135` | 规则修订修复（`742215d`）未按 OpenWolf 协议登记 `.wolf/buglog.json` | project-standards | 75 |
| 31 | `pcs-backend/app/services/supplier/deviation_service.py:156` | 叶轮直径解析到转速规则的 `design_key`，报告把叶轮直径与设计转速配成一对 | correctness | 75 |
| 32 | `pcs-backend/scripts/p7_s4_003_seed_pump_design.py:62` | 回填无随附的部署后验证 SQL，无法证明 17 条写入落库、也没有行被漏掉 | data-migration | 75 |

- **#12** —— `check_migration_idempotency.py:60` 硬编码 `checked_prefixes = ("p7_s2_", "p7_s3_")` 并在 `:62-63` 跳过其余文件，因此它对 `p7_s4_001` 报 OK 是空洞成立的；真读了会在 `:59` docstring「删 event_idempotency 表 (if_exists 幂等)」正下方的裸 `op.drop_table(_TABLE)` 上失败。**需要什么：** 两处独立编辑 —— (1) `op.drop_table(_TABLE, if_exists=True)`（pinned alembic 1.19.1 支持）；(2) 把 prefix 白名单补上 `p7_s4_`/`p7_s5_`，或改用 baseline 边界检查。**注意 (2) 会立刻暴露既有 p7_s3_* 的违规，必须与 (1) 同一提交落地**，否则钩子会在无关文件上开始失败。
- **#13** —— 100 行的报告已是 143 ms（excel）/ 112 ms（pdf）纯阻塞，成本随行数线性；`app/main.py` 无 worker pool 也无 offload 中间件。**需要什么：** 改 `content = await run_in_threadpool(export_excel, report)`，两行改动，openpyxl/reportlab 的重活在大部分时间里释放 GIL。与 #1 配套：offload 止住循环停顿但不限内存，上限才限内存。
- **#14** —— 函数 docstring 谨慎处理了一类覆盖（「位号不在设计表内的设备一律跳过, **不写空对象** —— 那会覆盖已有值」），但镜像情形没设防：`tag_number` 命中 `PUMP_DESIGN` 且已有非空 `design_parameters_json` 的行被无条件覆盖。种子脚本甚至**已经把这类行的数量算出来并打印了**（`p7_s4_003_seed_pump_design.py:59`），然后照写不误。且 `apply_design_parameters` 内部 `commit()`（`:142`），调用方没有可回滚的事务边界，17 行要么全落要么全不落，且旧值无快照。**需要什么（决策项）：** 定覆盖策略；代码侧加 `overwrite: bool = False` + `dry_run: bool = False`，脚本加同名开关且默认 dry-run，`already > 0` 未带 `--overwrite` 应直接报错而非打印一行。首次真跑前先备份旧值（快照 SQL 见 `synthesized-findings.json` 的 `suggested_fix`）。
- **#15** —— 全仓 `grep app.core.events` 唯一命中就是这行 `用法::` 里的可复制粘贴示例；其余调用方（`cia_engine.py:38`、`confirmation_service.py:32`、4 个测试模块）都已用新路径。**需要什么：** 改成 `from app.services.events import emit_event, register_listener`。
- **#17 / #20** —— 两处死代码，都是本 diff 新增、零调用。`_cell(container, row)` 的 `container` 参数从未被读；`_RULE_INDEX` 全仓只有自己那一行定义。**需要什么：** 直接删除。#20 附一条约束：若将来真需要 name->rule 查找，必须按 `_normalize` 后的名称**加全部别名**建键，不能只按 `r.parameter` —— 否则不能替掉 `find_rule`，否则会静默破坏所有带别名的参数（扬程/效率/NPSHr 都有别名）。
- **#18** —— 两个生产模块开头的 ⚠️ 声明「所有行都会落到缺设计值（不可判）」、`can_confirm` 恒 False，而本 diff 的 `cae5bce` 恰好新增了 `apply_design_parameters` 这个写入方。留着它，第一个读到这些文件的维护者（或 code-reading agent）会把偏差引擎当成不可测，未来 review 可能把「全行不可判」的回归当成已知基线放过。**需要什么：** 删掉两处 ⚠️ 并改写为当前事实：设计值来自 `pump_design_data.PUMP_DESIGN`；残余缺口是 `PUMP_DESIGN` 只覆盖 18 个蜡油加氢泵位号，tag 集之外的设备仍出不可判行。
- **#19** —— 模块 docstring 被本文件自己定性为「SPEC §3.2.4(2) 的转写表」且文件头警告「勿凭印象改数值」，但第 4 行仍写 电机额定功率 = SYMMETRIC_BAND ±10%，而注册表条目（`:132-133`）是 `MOTOR_TIER_FLOOR`，`evaluate:251` 的 SYMMETRIC_BAND 分支只剩 `test_deviation_service.py:118` 手工构造的 `DeviationRule` 能到达。正确口径记在该规则自己的 `spec_ref`（`:135-139`）。**需要什么：** 改 docstring 第 4 行为 API 610 分档并补轴功率 REFERENCE_ONLY 行使其与 `SPEC_RULES` 一一对应；SYMMETRIC_BAND 分支二选一 —— 若 SPEC 不会有对称带规则，删 `:251-256` 与该测试；若预期后续版本会加，留分支并加一行「为未来对称带规则预留」。
- **#21** —— 实测该用例的 fixture（`DESIGN={'扬程':32.0,'轴功率':55.0}`, `ACTUAL_ALL_OK={'扬程':33.0,'电机额定功率':75.0}`）产出的是「扬程 QUALIFIED」+「电机额定功率 QUALIFIED」，**零 WARNING 行**。若有人把 `can_confirm` 收紧成连 WARNING 一起拦（`RECHECK_ALWAYS` 规则下极可能：转速/叶轮直径只要录入就恒 WARNING），全套 3884 个用例无一会红。**需要什么：** 新增一个真正含 WARNING 行的 fixture（如 `ACTUAL_HAS_WARNING={'转速': {'value': 3000.0, ...}}` 配设计转速 2950.0），先 assert 报告里确有 `verdict == "WARNING"` 的行（防止再次退化成全 QUALIFIED 而测试仍绿），再 assert `can_confirm(r) is True`；同时把原用例改名为 `test_can_confirm_when_all_qualified`。
- **#22** —— 守卫 grep 的字面量 `self.fsm.transition(` 在重构后的 `cia_engine.py` 中一次不出现（唯一调用是局部变量形式 `fsm = StateMachineService(session)` / `await fsm.transition(`，`:84-85`；类本身已不持有 fsm 属性）。有人真把直调加回来时最自然的两种写法都不含该字面量，守卫全漏。同批的 `test_supplier_source_has_no_direct_fsm_transition_calls`（`test_confirmation_service.py:217-245`）已用 AST 正确实现该守卫，其 docstring 明确点名「既有的 cia 守卫就有这个隐患」—— 正确修法已在同一次提交里写好，只是没回用。**需要什么：** 用那份 AST 实现替换 `:140-157`，按 `ast.Call` + `node.func.attr == "transition"` 判定并检查 `state_machine` 的 import，顺带修掉注释声称剥 docstring、实现只剥 `#` 行的不符。
- **#23**（`manual` -> `human`，**决策项**）—— 写侧把任意字符串原样存为 `actual_data_json` 的 key，读侧按封闭规则集解释，不认识的 key 一律 `UNVERDICTABLE`。契约里没有任何地方列出有意义的 key 集合，客户端能成功写入一份永久不可判的数据：写入返 200 并回显该值，失败只在之后以一行 `UNVERDICTABLE` 和 `can_confirm: false` 的形式浮现。响应类型又是裸 `dict`，前端类型渲染为 `{ [key: string]: unknown } | null`，连逐值类型都没有。**需要什么：** 不改服务端行为的最小可行修法是新增 `GET /api/v1/equipment/deviation-rules`（返回每条规则的 `parameter`、`design_key`、`spec_ref`、unit）供客户端填表；若规则已稳定，更强的做法是写时拒绝未知名（新错误码，按 #4 的要求内联 raise 才能被注册）—— 但这取决于设计值来源决策，不要在决策前收紧 key 类型。
- **#24** —— schema docstring（`「value 严格数值 —— 字符串数字在 UI 上是录入错误」`）与服务层 `_coerce_value`（含显式 `isinstance(raw, bool)` 拒绝）都声称拒绝字符串数字与布尔，但 Pydantic v2 先以松散模式跑完并交出已强转的 `float`（实测 `'100' -> 100.0`、`True -> 1.0`、`'NaN' -> nan`、`'Infinity' -> inf`），所以服务层的布尔分支在 `PUT /actual-data` 路径上不可达，字符串规则**根本没有执行**。安全相关的边是非有限浮点：`NaN` 进入 `evaluate` 后所有比较为 false，`ASYMMETRIC_BAND` 落到 `return Evaluation(QUALIFIED, deviation)` —— 我实测整份实测值都是 `{"扬程": {"value": NaN}}` 的泵 `can_confirm` 返回 True，即一个从未被测量的值能过 SPEC §3.2.4(4) 确认门。**今天**到不了生产：PostgreSQL 18.6 拒绝 `'NaN'::jsonb`，写入以 500 失败，实际影响是「客户端可触发的未处理 500」而非已证实的伪造值 —— 这也是本条定 P2/75 而非 P1 的原因。**需要什么：** schema 上加 `strict=True, allow_inf_nan=False`，让两处 docstring 描述的契约真正成立、服务层检查退为纵深防御。这对当前发送字符串数字的客户端是破坏性变更（而那正是两处 docstring 说不可容忍的行为），改前先核对本 diff 内的 `api.d.ts`。
- **#25** —— `CLAUDE.md` 规定枚举与 SPEC 冲突时「以 OpenAPI 为准**并登记 SPEC 修订**」，登记不是可选项。本次 OpenAPI 加了第 4 档结论，代码注释自己承认「SPEC §3.2.4(3) 定 3 档」，`api.d.ts:7145` 也已同步为 4 值 union；但前端开发者按冻结的 `docs/PCS-UI-SPEC.md:1597`（`结论 合格/警告/不合格`，本次 diff 未改，§12.4 修订记录表也无新条目）实现比对结果表，只会渲染 3 色。同批的电机规则修订已按规矩写了 `docs/PCS-NOTE-SPEC-3.2.4-电机功率规则修订-2026-10-06.md`，本条枚举扩展却只登记在计划文档与 SDD ledger（计划文档不构成 SPEC 修订登记件，`grep -rl UNVERDICTABLE docs/` 唯一命中即 `docs/sprint4-plan-2026-10-05.md`）。**需要什么：** 按同项目既有命名体例新增 `docs/PCS-NOTE-SPEC-3.2.4(3)-结论档数修订-2026-10-06.md` 写明 3 档 -> 4 档、fail-closed 裁决依据、V1.0 冻结 SPEC 不改正文；并在 `docs/PCS-UI-SPEC.md` §12.4 追加一行、§7.14 补第 4 档（与 §4.4 修订登记先例一致）。
- **#27** —— 脚本为打印「before」快照自己发了一份逐字相同的查询，而它并排打印的两个数字（`位号匹配 N 台` / `写入设计值: M 台`）读起来像 M 由 N 派生 —— 只在两份 WHERE 一致时成立。任一方加了过滤条件就会静默漂移，而脚本输出是这次回填唯一的可见性来源。**需要什么：** 在 `pump_design_data.py` 暴露一次 `matching_pump_records(session, project_id)`，两处都调它，匹配数与写入数即可证明同源。
- **#28**（`manual` -> `human`）—— 派发循环遍历 `_LISTENERS.get(event_type, [])`，空列表不是错误，然后返回 True（docstring 定义为「已派发」）。`CIAEngine.scan_stale` 在 ADR-0025 分支调完 `_mark_stale` 就无条件 `marked += 1`（`cia_engine.py:280-284`），不检查返回值。若注册表里没有 `cia_mark_stale` 的 listener，FSM 转移不发生、无异常抛出、事件照样在 `event_idempotency` 里被 claim 为已处理，而 `scan_stale` 仍报「已标记 N 台」—— 操作者用来判断隔离了多少陈旧数据的那个数字是错的，且无任何错误提示。docstring 明确认可的 `clear_listeners()`（「模拟进程重启」）是到达该状态的一条路径。**需要什么：** 两处小改 —— (a) 无 listener 时返回可区分的哨兵值或抛错，而不是 True；(b) `scan_stale` 只在 `_mark_stale` 确实完成转移时递增。**注意该检查必须按事件类型区分**：`cia_mark_stale` 无 listener 一定是 bug，但 `actual_data_replaces_design` 在 P8 挂上反向恢复 listener 之前本就是 claim-only。
- **#29** —— `evaluate()` 先按 `rule.kind` 派发（`deviation_service.py:212-231`），MANUAL_CHECK 返回带 `requires_manual_check=True` 与「需人工核对」的 UNVERDICTABLE，REFERENCE_ONLY 与 RECHECK_ALWAYS 根本不需要设计值；但 `build_report` 在 `:104` 先判 `if design_value is None` 就 `continue`。对 材质 —— SPEC §3.2.4(2) 明列的六行之一，按定义在 `design_parameters_json` 里没有数值设计值 —— 结果是一行写着「缺设计值，无法判定」（这句是假的，什么都没缺）、`requires_manual_check=False`、`spec_ref` 却有值的行。丢掉的那个 flag 才是真伤害：它是下游消费者（以及导出报告）把该行路由给人而不是当成录入缺陷的信号，且 `DeviationRowOut` 把它带到了 API。同一顺序也把 REFERENCE_ONLY（轴功率，`deviation_service.py:224-231` 明确「本身不判合格与否」）在设计值尚未回填的设备上静默降级为 UNVERDICTABLE。**需要什么：** 让 kind 决定是否需要设计值 —— 定义 `DESIGN_VALUE_OPTIONAL_KINDS = frozenset({"MANUAL_CHECK", "REFERENCE_ONLY", "RECHECK_ALWAYS"})`，把 `design_value is None` 检查改为 `design_value is None and rule.kind not in DESIGN_VALUE_OPTIONAL_KINDS`。若团队希望转速在无设计值时仍阻断，从 frozenset 里去掉 RECHECK_ALWAYS 即可。
- **#30** —— `.claude/rules/openwolf.md:9` 要求「AFTER fixing one: log it there (... `fix_commit` 必填：修复该 bug 的 git commit 短 SHA 7 位，便于 STATUS 反查单点来源)」。本区间唯一的修复提交 `742215d`（电机额定功率按 ±10% 判错了对象 —— ±10% 量的是电机档位差而非设备偏差，蜡油加氢实测 16 台里 2-3 台假性不合格）性质上就是 bug 修复，而 `git log --name-only 3e5ae90..cae5bce -- .wolf/` **零输出**，`grep -c 742215d .wolf/buglog.json` 为 0。协议要求 `fix_commit` 的理由正是「可反查单点来源」；现在反查只能翻代码注释与那份 SPEC 修订书。**需要什么：** 追加一条 buglog（5 个字段与 tags 建议见 `synthesized-findings.json` 的 `suggested_fix`）。若维护者认为这属于设计期规则裁决而非 bug，退而求其次在 `.wolf/STATUS.md` 留痕。
- **#31** —— 转速规则把 `叶轮直径`/`实际叶轮直径`/`设计叶轮直径` 列为别名（`:152-157`）且未设 `design_parameter`，于是 `design_key`（`design_parameter or parameter`，`:66-69`）解析为「转速」，`build_report:89-91` 就从 `design_parameters_json` 里取出 2982 r/min 当作「叶轮直径」行的设计值，而该行实测值是 320 mm。`PUMP_DESIGN` 与 `_UNITS` 里都没有叶轮直径键，今天不存在正确的配对值。这不只是显示问题：`export_excel`/`export_pdf` 会把错配的设计值写进工艺室收到的合规文件，且 `_extract` 对设计列丢弃了单位（`_`），导出里于是显示「2982 r/min」作为毫米级实测项的设计值且无单位标注。门禁本身未被污染（`evaluate` 对 RECHECK_ALWAYS 返回固定 WARNING、`deviation_pct=None`，不产生假百分比）。**需要什么：** 给叶轮直径独立成一条规则（`parameter="叶轮直径", kind="RECHECK_ALWAYS", aliases=("实际叶轮直径", "设计叶轮直径")`）。届时它自然落入既有的「缺设计值，无法判定」分支并被 `can_confirm` 阻断 —— 在真实设计叶轮直径补录之前这是正确的 fail-closed 结果，且严格优于在直径旁边放一个转速。
- **#32** —— 脚本的返回值是「回填确实干了事」的唯一信号，且只 print 到操作者终端、从不落盘。写入路径靠对硬编码 17 条 dict 的 `tag_number` 精确串匹配，真实失效模式是静默部分匹配（Excel 同步时位号写法有细微差异），产出 `写入设计值: 0 台` 而操作者可能没注意；下游结果恰好是这次改动本来要修的东西 —— 偏差报告与确认继续对生产数据读「缺设计值（不可判）」，而没有任何信号表明回填静默空转。**需要什么：** 脚本内在写入后断言 `n == len(before)` 并以非零码退出（完整 SQL 见 `synthesized-findings.json` 的 `suggested_fix`）。其中 `actual_data_status` 分组那条查询专门用来佐证 `apply_design_parameters` docstring 里那条 SPEC §3.2.4(5) 分流声明，目前它未对真实数据验证过。
### P3 -- Low / 低（3 条）

| # | File | Issue | Reviewer | Confidence |
|---|------|-------|----------|------------|
| 33 | `pcs-backend/app/services/equip_list/pump_design_data.py:138` | 计划外行为规则：新增 PUMP_DESIGN 设计值落库路径（登记项，不改代码） | synthesis | 100 |
| 34 | `pcs-backend/app/services/supplier/__init__.py:4` | 包 docstring 宣称 `excel_import_service` —— 该模块不存在，且 S4-1 裁决明确不做 | maintainability | 100 |
| 35 | `pcs-backend/app/services/supplier/deviation_service.py:136` | 计划外行为规则：电机额定功率口径由 ±10% 改为轴功率卡 API 610 分档下限（登记项，不改代码） | synthesis | 100 |

- **#33** —— 这条落库路径决定 design 侧读到的是空还是真实设计值：写之前多数设备上是空列、比对只能产 UNVERDICTABLE，写入之后才可能产 QUALIFIED/WARNING/UNQUALIFIED。它由用户裁决驱动且实现本身已审（另见 #14、#32），登记仅因其不在 5 个 Task 范围内。**需要什么：** 由维护者决定是否在计划文档 Task 2/3 下补追溯行；本条不改代码。
- **#34** —— `ls app/services/supplier/` 只有 `__init__.py / actual_data_service.py / confirmation_service.py / deviation_report.py / deviation_service.py`；而同一 diff 的 `app/api/v1/supplier.py:9-10` 写着「录入入口是**手工 UI 页面**（S4-1 裁决）：要求供应商填统一 Excel 不现实，故无 Excel 批量导入端点」。**需要什么：** 把第 4 行换成实际存在的三个模块。`actual_data_service`（第 3 行）已正确。
- **#35** —— 这条规则改变对用户可见的判定结果：同一台泵在 `742215d` 前后会得出不同的合格/不合格结论（ledger 记载蜡油加氢 16 台里有 2-3 台因旧口径被判假性不合格）。它有 SPEC 修订书与用户裁决背书，因此**不是缺陷**；登记是因为计划文档 Task 3 的规则清单里没有它，反向核对必须把它显式列出，而不是让读者以为 5 个 Task 覆盖了分支的全部行为。**需要什么：** 同 #33，由维护者决定是否补追溯行；本条不要求改代码。

---

### 需求完整性（Requirements Completeness）

计划 `docs/sprint4-plan-2026-10-05.md`（`plan_source: explicit`）**不是统一计划格式**：无 Product Contract / `## Requirements` / `## Implementation Units` / R-ID / U-ID。其 5 个 `## Task N` 小节即实现单元。

| 实现单元 | 状态 | 依据 |
|---------|------|------|
| Task 1 (S4-0) 事件骨架 `emit_event()` + listener + 幂等表 | met | `pcs-backend/app/services/events.py` 全量新增；`EventIdempotency` 模型 + `p7_s4_001` 迁移 |
| Task 2 (S4-1) 供应商实际数据录入（手工 UI 路径） | met | `ActualDataEntry` / `ActualDataEntryRequest` + `record_actual_data` + `PUT /equipment/{id}/actual-data`；Excel 批量按用户裁决撤销 |
| Task 3 (S4-2) 自动比对 + 偏差报告（3+1 档） | met | `deviation_service.SPEC_RULES` 七条规则 / `deviation_report.build_report` / `export_excel` / `export_pdf` |
| Task 4 (S4-3) 核算与更新流程（确认 -> 校核 -> emit_event） | met | `confirmation_service.confirm_actual_data` / `pass_check` / `reject_check` + `POST .../actual-data/confirm` 与 `.../check`；`e731f02` 重生成 OpenAPI 契约 |
| Task 5 (S4-4) 蜡油加氢真实数据端到端验收（6 表全链路） | met | `b3eea4c` 扩类 6 表 |

**5/5 met，无未覆盖的实现单元**，ledger 逐项标记 complete。

**反向核对（计划外行为规则登记）** —— 检出 2 条，均由用户裁决驱动、均有背书、均无 SPEC 登记缺口（#35 有 SPEC 修订书），按契约登记为 P3 / `advisory` / `human`：
1. **#35** —— 电机额定功率偏差口径由「设计电机 vs 实际电机 ±10%」改为对轴功率卡 API 610 分档下限（1.25 / 1.15 / 1.10）。计划 Task 3 的规则清单只列 SPEC §3.2.4(2) 六条允许偏差，无此条。
2. **#33** —— 新增 PUMP_DESIGN 设计值落库路径。计划 Task 3 的 Ruling 原文是「设计值来源暂缺，S4-2 只做偏差引擎」，落库不在 5 个 Task 内。

项目规则「与 SPEC 冲突时以 OpenAPI 为准并登记 SPEC 修订」在本次执行上的缺口是 #11（端点路径）与 #25（第 4 档结论）—— 这两条是**该规则未被遵守**，不是计划外行为，已在 P1/P2 中单列。

---

### Actionable Findings

26 条待调用方处理（`gated_auto` / `manual` + owner `downstream-resolver`）。**本次为 report-only，未对任何一条执行修复**；下表是交回给调用方决定的队列，不是已完成的改动。被审树的任何文件都未被修改。

| # | File | Issue | Route | Notes |
|---|------|-------|-------|-------|
| 1 | `pcs-backend/app/schemas/supplier.py:30` | `entries` 无上限，两个导出器整体物化 | `manual -> downstream-resolver` | `suggested_fix` present（含 max_length=200、normalize 侧同闸、截断标记行）— 上下限口径由调用方定 |
| 2 | `pcs-backend/app/services/events.py:165` | `_claim` 回滚调用方整个事务 | `gated_auto -> downstream-resolver` | `suggested_fix` present（savepoint 替 rollback + 补三条断言的测试）；protected: data-loss |
| 4 | `pcs-backend/app/services/supplier/actual_data_service.py:27` | 两个新错误码未进 meta 注册表 | `gated_auto -> downstream-resolver` | `suggested_fix` present（推荐内联 raise；另一路改共享扫描器需自带回归测试）；protected: public-contract |
| 5 | `pcs-backend/app/services/supplier/confirmation_service.py:98` | 确认/校核无状态前置条件 | `manual -> downstream-resolver` | `suggested_fix` present（409 守卫 + 重跑 can_confirm）；须同步改 4 条把未守卫行为写死的测试 |
| 6 | `pcs-backend/app/services/supplier/deviation_report.py:208` | xlsx 公式注入（实测 data_type `f`） | `gated_auto -> downstream-resolver` | `suggested_fix` present（`_safe_cell` 前缀转义，3 处调用点）；protected: injection |
| 7 | `pcs-backend/app/services/supplier/deviation_report.py:277` | PDF markup 注入 / 未处理 500 | `gated_auto -> downstream-resolver` | `suggested_fix` present（`escape()` 覆盖全部 Paragraph 实参）；protected: injection |
| 9 | `pcs-backend/app/services/cia_engine.py:173` | 吞异常导致半应用转移被提交 | `manual -> downstream-resolver` | `suggested_fix` present（收窄 except + per-record savepoint） |
| 10 | `pcs-backend/app/services/events.py:232` | claim 先于派发持久化 | `manual -> downstream-resolver` | `suggested_fix` present（提交点后移 / 拆 claimed_at+dispatched_at）；须先定 #3 的 id 口径 |
| 11 | `spec/工艺专用综合计算软件需求规格说明书 Web版 P7.md:145` | 端点路径与冻结 SPEC 不一致且未登记 | `manual -> downstream-resolver` | `suggested_fix` present（改 SPEC 表 + 加 SPEC-ADD 条目）；若判定 SPEC 前缀不可动则需先明确决策 |
| 12 | `pcs-backend/alembic/versions/p7_s4_001_event_idempotency.py:60` | downgrade 非幂等 + 幂等闸不扫 p7_s4_* | `manual -> downstream-resolver` | `suggested_fix` present（含验证 SQL）；两处编辑必须同提交落地 |
| 13 | `pcs-backend/app/api/v1/supplier.py:235` | 同步导出堵死事件循环 | `gated_auto -> downstream-resolver` | `suggested_fix` present（`run_in_threadpool`，两行） |
| 15 | `pcs-backend/app/services/events.py:22` | docstring 指向已迁走的模块 | `gated_auto -> downstream-resolver` | `suggested_fix` present（改一行 import 路径） |
| 17 | `pcs-backend/app/services/supplier/deviation_report.py:189` | 死助手 `_cell()` | `gated_auto -> downstream-resolver` | `suggested_fix` present（删 4 行） |
| 18 | `pcs-backend/app/services/supplier/deviation_report.py:7` | 过期缺口注释被本 diff 自己推翻 | `gated_auto -> downstream-resolver` | `suggested_fix` present（改写为 PUMP_DESIGN 只覆盖 18 个位号这一残余缺口） |
| 19 | `pcs-backend/app/services/supplier/deviation_service.py:11` | 电机规则表文档漂移两处 | `gated_auto -> downstream-resolver` | `suggested_fix` present（改 docstring 行 + SYMMETRIC_BAND 分支去留二选一） |
| 20 | `pcs-backend/app/services/supplier/deviation_service.py:166` | 死索引 `_RULE_INDEX` | `gated_auto -> downstream-resolver` | `suggested_fix` present（删 1 行 + 若重建须按别名建键） |
| 21 | `pcs-backend/tests/services/supplier/test_deviation_report.py:90` | WARNING 不阻断确认零覆盖 | `gated_auto -> downstream-resolver` | `suggested_fix` present（真 WARNING fixture + 改名消除误导） |
| 22 | `pcs-backend/tests/test_cia_event_decoupling.py:155` | 静态守卫不可失败 | `gated_auto -> downstream-resolver` | `suggested_fix` present（回用同批已写好的 AST 实现） |
| 24 | `pcs-backend/app/schemas/supplier.py:23` | 实测值严格契约未生效，NaN 可过确认门 | `gated_auto -> downstream-resolver` | `suggested_fix` present（`strict=True, allow_inf_nan=False`）；对现有客户端是破坏性变更 |
| 25 | `pcs-backend/app/schemas/supplier.py:73` | 第 4 档结论未登记 SPEC 修订 | `manual -> downstream-resolver` | `suggested_fix` present（新增修订登记件 + UI-SPEC §7.14/§12.4） |
| 27 | `pcs-backend/app/services/equip_list/pump_design_data.py:124` | WHERE 子句重复两份 | `gated_auto -> downstream-resolver` | `suggested_fix` present（抽 `matching_pump_records`） |
| 29 | `pcs-backend/app/services/supplier/deviation_report.py:104` | 短路抢在 kind 派发前，MANUAL_CHECK 丢 flag | `gated_auto -> downstream-resolver` | `suggested_fix` present（`DESIGN_VALUE_OPTIONAL_KINDS`） |
| 30 | `pcs-backend/app/services/supplier/deviation_service.py:135` | `742215d` 未登记 `.wolf/buglog.json` | `gated_auto -> downstream-resolver` | `suggested_fix` present（含 5 个必填字段与 tags 建议） |
| 31 | `pcs-backend/app/services/supplier/deviation_service.py:156` | 叶轮直径配到转速设计值 | `gated_auto -> downstream-resolver` | `suggested_fix` present（拆成独立规则，落到 fail-closed 分支） |
| 32 | `pcs-backend/scripts/p7_s4_003_seed_pump_design.py:62` | 回填无部署后验证 SQL | `gated_auto -> downstream-resolver` | `suggested_fix` present（脚本内非零码断言 + 4 条只读 SQL） |
| 34 | `pcs-backend/app/services/supplier/__init__.py:4` | 宣称不存在的模块 | `gated_auto -> downstream-resolver` | `suggested_fix` present（换成实际存在的三个模块） |

### 需人工决策项（不在 apply 队列，自动化修复器应停在此处）

6 行覆盖 7 条发现：#3、#8、#14、#23、#28 各一行（需具体产品/契约/数据安全决定），末行合并 #33 与 #35（纯文档追溯决定，不改代码）。这 7 条全部不在上方 26 条 apply 队列内。

| # | File | 待决问题 | 阻塞了什么 | 需要的授权/决定 |
|---|------|---------|-----------|--------------|
| 3 | `pcs-backend/app/services/events.py:96` | `event_id` 是否改为从业务操作确定性派生（如 `uuid.uuid5`）？ | 阻塞 G1 中 #2 / #10 的事务边界改法，也决定 P8 反向恢复能否复用原 id | 跨 sprint 的 id 语义决策 —— 若批准，实现本身是机械工作，交回 `downstream-resolver` |
| 8 | `pcs-backend/app/services/supplier/deviation_report.py:92` | 确认是否必须要求该设备应检参数集全部有实测值？ | 阻塞 #5 的守卫按什么口径实现 | 产品口径决定（fail-closed 覆盖面） |
| 14 | `pcs-backend/app/services/equip_list/pump_design_data.py:138` | 回填是否允许覆盖已有非空 `design_parameters_json`？ | 阻塞 #32 验证 SQL 的期望值；覆盖策略未定前跑回填有数据风险 | 数据安全策略决定（`overwrite` / `dry-run` 默认值） |
| 23 | `pcs-backend/app/schemas/supplier.py:22` | 参数名是否收敛为白名单？规则集是否应作为可发现的读端点？ | 与设计值来源决策耦合 | 产品/契约决定；服务端可先只补规则集读端点 |
| 28 | `pcs-backend/app/services/events.py:238` | 「无 listener 但已 claim」该如何表达？ | 影响 `scan_stale` 计数语义 | 事件语义决定，且必须按事件类型区分（`actual_data_replaces_design` 在 P8 前本就是 claim-only） |
| 33 / 35 | `pump_design_data.py:138` / `deviation_service.py:136` | 两条计划外行为规则是否补写进计划文档的追溯行？ | 无（纯文档追溯） | 维护者决定；本条不改代码 |

### Pre-existing Issues

无。本次 35 条合并发现全部为 primary（直接落在 diff 内的新增/改动行上），`pre_existing` 集合为空。
### Coverage

**范围与深度**
- scope: `local-aligned`（base `3e5ae902945e19274f5be410f0eed31eb48a7627`，branch `worktree-s4-0-events`，HEAD `cae5bce9e3411ff1199713aca88c83f427a1d089`）—— 工作树即受审 head，38 个变更文件全部为 tracked，**untracked 为空**。会话在 git worktree 内运行，workspace 读取即受审树。
- depth: `full` —— `review-scope.py` 判定 `hard_block_full=true`（`hard_block_classes` 含 `migrations`；`size_band=large`；可执行非测试变更 2601 行，changed_lines 6970）。深度闸门为地板，不可下调。

**跨模型与独立性**
- cross-model pass: **not run** —— 本机未安装任何异族通道（codex / grok / cursor-agent / opencode 均 absent；唯一剩余选项 claude 与宿主同族，无法通过独立性检查）。对抗性视角由 in-process `adversarial-reviewer` 承担。宿主自证：`XHOST_HARNESS=claude, XHOST_FAMILY=claude`。checkout 策略：无 `.compound-engineering/config.yaml` 与 `config.local.yaml`，`cross_model_review_mode` 未设 -> 默认 auto（非 skip）。
- **cross-model corroboration: 0。** 没有任何一条发现有经过独立跨模型印证。`security` / `adversarial` / `reliability` / `correctness` 等全部为同族 in-process 审查员，其相互印证只记入 `reviewers`，不提升置信锚点。Stage 5b 的 validator 跳过捷径因此 **0 次适用**（依据：无任何 `adversarial-<provider>` 产物，更无 `independence_verified:true` 记录）。

**审查员状态**
- 10 位审查员全部返回，`failed_reviewers: []`，`bound_exceeded: []`。
- **1 位降级：** `project-standards` 的 artifact（`project-standards.json`）因 `why_it_matters` / `suggested_fix` 内引号未转义而未通过 JSON 校验（第 53 行）；已按 subagent-template「artifact 写失败时紧凑返回仍提供 merge 所需全部信息」采用其合法 in-band 紧凑返回（`project-standards-compact.json`）。合并阶段另将磁盘上无效 JSON 的引号逐行转义后成功还原出完整 `why_it_matters` 与 `evidence`，其 2 条 finding（#25、#30）以完整 detail 进入 finding 集，**未因 artifact 损坏而降级**。
- 标准源：适用标准文件 1 个（仓库根 `CLAUDE.md`，OpenWolf 项目运营文件），治理全部 38 个变更文件；无 `CODING_STANDARDS.md` / `AGENTS.md`，故无双标准源冲突。
- 未运行的审查员及原因：`agent-native`（helper 报 `agent_surface=false`）；`learnings`（`has_learnings_corpus=false`，未声明任何 Compound Pack，`packs.roots=[]`）；`previous-comments`（无 PR，仅分支审，Stage 1 未取 PR 元数据）；`deployment-verification-agent`（两个迁移均为纯增量 `CREATE TABLE` + 可空 `ADD COLUMN`，无 rename/drop/NOT NULL 无默认，非破坏性）；`julik-frontend-races` / `swift-ios`（无对应技术栈变更）。**因此 settlement 抑制不适用**（计划文档不含任何 `session-settled:` KTD；ledger 的「Ruling」行是用户裁决记录，不构成该契约下的 settlement 标注）。
- schema drift 检查不适用：本仓库为 SQLAlchemy + Alembic，diff 内无 `schema.rb` / `structure.sql`。

**Stage 5 机械统计**
- 输入 10 位审查员的 51 条紧凑 finding -> 合并为 35 条 primary。
- `first_evidence_backfilled = 44`（另 6 条自带引用；重跑保持该计数不因已归一化而清零）。
- quote-the-line 降级：**0**（最终轮）。第一次运行有 1 条因缺可用引用被判 malformed —— `adversarial` 的 `events.py:178` `_claim` IntegrityError 回滚（P2/50）；该条与其 P1 版本描述同一缺陷同一修法，已并入 #2，不再单列。
- `suppressed_by_confidence: {}` —— 0 条按置信阈值被抑制。
- malformed：首轮 1 条、终轮 0 条。
- **mode-aware demotion（Stage 5 step 4）：10 条** —— testing_gaps 5 条（#19 `clear_listeners` 测试专用接缝、#40 `evaluate()` REFERENCE_ONLY 分支无覆盖、#43 规则表外 kind 兜底分支无覆盖、#45 测试文件内 `_dev` 死助手、#46 两文件重复断言）；residual_risks 5 条（#37 四档结论词汇在 6 处复述、#50 参数名词表三处维护、#47 `event_idempotency` 无界增长、#48 `with_variant(sqlite)` 与 ORM 类型分歧、#16 `build_report` 重复构造 frozen dataclass）。testing-only 覆盖缺失按「每个变更子系统最多保留一个 umbrella」处理：偏差判定子系统保留 #21 为唯一覆盖类主 finding，#40/#43 降入 testing_gaps。

**fast-pass 初筛的核对（按 dispatch-reviewers 要求显式对账）**
- **1 条初步候选已撤下：** `events.py:165` `_claim` 回滚调用方事务。该项由编排者内联 fast-pass 产出，锚点封顶 50，`fast-pass` 伪审查员**从不计入跨审查员提升**。它自身并未独立存续为发现 —— 后续由 `reliability`（P1/75）、`testing`（P1 覆盖零测试）、`adversarial`（P2/50）独立提出同一缺陷，去重合并为 **#2**，而 #2 的置信来自那些独立审查员，不来自 fast-pass。本报告不以该初步项作为独立 P1 呈现。
- **1 处 fast-pass 分析错误已在合并阶段纠正，且未压制任何发现：** fast-pass 曾断言「新错误码因 AST 派生会自动注册」，此断言**错误** —— `meta_service.py:305-314` 只走 `ast.Raise` 节点且要求 call target 字面为 `PcsError`，而 3 个新错误码经工厂函数 *返回* `PcsError` 产出，故取不到。该误判当场更正并由 `api-contract` 独立报出，validator 确认为 **#4（P1/c100，protected: public-contract）**。它是本次审查中一条真实的确证发现。

**Stage 5b 验证（单批）**
- 批次：1 批，入选 **30** 条（P0/P1 全部 + 全部 actionable；P2/P3 advisory 项已在 Stage 5 step 4 降入软桶，不再为保留 primary 身份而验证）。排序为 severity（P0->P3）后稳定 `#` 升序；**11 条 P1 超过 8 条常规上限，按契约在同一批内扩容至全部 P1，未拆第二批**。
- 跳过捷径：**0 次**（依据如上：无跨模型独立性记录）。因此没有基于 quote-anchor 的免验证 finding。
- 等待上限内的结果：**verdicts 落盘**（`validator-outcome.json` 为 `verdicts`，30 条对 30 条输入编号一一对应，等待上限未被突破）。
- 裁决结果：**confirmed 28 / rejected 2 / unresolved 0 / malformed 0 / failed 0 / shortcut-skipped 0**。
- **2 条被 validator 驳回，已从 actionable 队列中移除**（均非 protected subject，无需引用式证据门槛即可成立）：
  - **#26**（原 P2/c75，`DeviationRowOut.design_value` 三路联合无判别字段）—— 驳回理由：该字段本 diff 新增、无既有消费方；项目规则只把枚举锚定在 SPEC 与 OpenAPI 上，不要求判别字段；引擎已在 `deviation_service.py:239-240` 把非数值设计值路由到 UNVERDICTABLE，客户端读同级 `verdict` 不会遇到歧义。
  - **#36**（原 P3/c75，`actual_data_status` 无描述、未列四态）—— 驳回理由：`:43` 与 `:100` 确为裸 `str` 无 description，但无任何项目规则或 SPEC 条款要求响应字段枚举四态；所引同族文件（`config.py:36`、`checklist.py:76`、`cool_tower.py:284`）是惯例而非约束标准；无消费方被破坏。
- protected-subject reclassification：**0**。4 条 protected 发现（#2 data-loss、#4 public-contract、#6 injection、#7 injection）**全部 confirmed**，无一被驳回。
- 裁决中显式说明「发生率未实测」的 confirmed 发现（缺陷成立，但没人证明它在生产中发生；`validation_status: "confirmed"` + `validation_reason` 随条目与 `review.json` 一并记录）：**#1**（真实大 payload 的发生率未测）、**#5**（可达性由代码检查确认，未实跑）、**#9**（本批未观测到该后 flush 异常）、**#12**（downgrade 往返未执行，环境只读）、**#13**（审查员引用的耗时数字未复测）。
- 其余 23 条 confirmed 均为文件与行号级别的确证。
- **未降为 unresolved 的项**：0。所有 30 条裁决均结构完整、编号可映射，无 malformed、无基础设施失败。

**残余风险（residual risks，共记录 65 条；下列为最具决策影响者，完整清单见 `synthesized-findings.json`）**
- **只读环境，本轮未执行任何测试、迁移或数据库命令。** 所有结论均来自源码静态追踪与对生产函数的单次 `python -c` 直接调用，不是跑测试文件得到的。#1/#13 的耗时数字是在本分支用真实开发树实测的。
- **#2 的因果链（rollback 丢弃 `pass_check` 已 flush 的 CONFIRMED）未构造真实并发双 session 场景复现** —— 由 `confirmation_service.py:98-99` 与 `events.py:161-179` 推出。补测试时优先验证这一条：若实测发现 AsyncSession 在此处有自动重放或 savepoint 语义使数据不丢，#2 的严重级别应下调。
- **#10 的锚点为 75 而非 100** —— 已确认 `cia_engine.py:167-173` 的 `except Exception: continue` 与 `events.py:231-232` 的裸 `await` 构成该状态，但未实跑一条真实异常路径确认该行确实会被 commit。
- **callsite completeness: grep-only。** `emit_event` / `register_listener` 的调用方用文本搜索枚举，未审计本 diff 之外的消费方；P8 反向恢复尚未编写，今天不存在会被打破的反向事件路径。
- **`pcs_test` 库是否已应用 `p7_s4_001` / `p7_s4_002` 未验证** —— `project-standards` 试图查询被凭据权限拦截。跑 schema 敏感测试前必须先 `cd pcs-backend && uv run alembic upgrade head` 对齐，否则 `tests/test_schema.py` 与 API 用例会因缺表/缺列失败（仓库 CLAUDE.md 的「测试前检查」规则）。
- **本次 diff 无跨模型 peer 通道，对抗视角全部由同族 in-process 审查员承担** —— security / adversarial / reliability 的交叉印证不等于独立性证明。
- **未审查的面**：前端 `pcs-frontend/`（除 `src/types/api.d.ts` 已随契约更新外）；`tests/api/v1/` 下三个 API 测试文件（618 行）仅抽样看了前半部分；`tests/scripts/test_t5_case4_gas_media.py`（113 行，扩类 6 表）完全未读；OpenAPI 重生成 diff（已独立校验：后端 `openapi.json` 与前端 `openapi.snapshot.json` 逐字节相同、sha256 均为 `30910d7b53586004`，含全部 5 条新路径与 196 个 path）。
- **已核清、未报 finding 的项**（避免让读者误以为漏看）：导出端点的 `format` 由 `Query(pattern="^(excel|pdf)")` 约束，非法值走标准 422 信封而非 500；`Content-Disposition` 文件名经 `quote(tag_number, safe="")` 百分号编码，无头注入或路径穿越；`_load_equipment` 六个调用点全部先过 `check_project_access_or_404`；两个 Alembic 迁移均为 expand-only，旧代码对新 schema 安全；`actual_data_json` / `actual_data_status` 无查询过滤或连接，无需建索引；`if_not_exists=True` 在 pinned alembic 1.19.1 上是真参数而非被方言前缀吞掉；`SYSTEM_ADMIN` 旁路与角色分离实现正确（`_CHECK_ROLES` 不含 DESIGNER / PROCESS_CONTROLLER）。

**测试缺口（testing gaps，共记录 44 条；下列为与上述发现直接对应的，完整清单见 `synthesized-findings.json`）**
- 无测试断言 `pass_check`（或 `POST /equipment/{id}/actual-data/check`）会拒绝非 PENDING_CONFIRM 的设备。现存三条 `pass_check` 测试都从全新 NOT_ENTERED fixture 直推 CONFIRMED —— 缺失的守卫是被测试固化了的，不是被测试抓住的。这就是本该抓住 #5 的那条测试。补两例：NOT_ENTERED 记录 check-pass -> 409，CONFIRMED 记录 check-reject -> 409。
- 无测试覆盖「提交 -> 重新录入 -> 校核」序列（`confirm_actual_data` 之后、`pass_check` 之前经 `PUT actual-data` 替换数据）。补上它才能证明 #5 的 TOCTOU 那一半。
- 无测试把 材质 或 厂家型号 录入 `actual_data_json`，所以 MANUAL_CHECK 分支的 `requires_manual_check=True` 以及它与 `build_report` 短路的交互（#29）两个方向都未被触发。
- 无测试把 叶轮直径 作为实测值录入，别名到 `design_key` 的错配（#31）对测试套件不可见。
- 无测试用敌意的 `ActualDataEntry.name`（现有 supplier 服务测试只用扬程/效率这类工程参数名），所以公式注入与 markup 注入两条路径都抓不到。补一条断言 `=1+1` 从工作簿回读为文本单元格（data_type `s` 而非 `f`）的导出测试，再补一条断言含 `<img src=...>` 的参数名时 `export_pdf` 成功。
- 无断言 `emit_event` 的 payload dict 不会被同一事件类型的多个 listener 破坏性共享（`_mark_stale_via_fsm` 会 `event.pop("_session", None)`）。
- #2 涉及的 `IntegrityError` 分支零覆盖：`tests/services/test_events.py` 覆盖了重复 id、不同 id、模块重载、相同 payload 四种情形，但没有一条构造真实的主键碰撞；同文件 `tests/test_cia_event_decoupling.py` 与 `tests/services/supplier/` 下 grep `IntegrityError` 均无命中。

**Removable surface**：约 20 行 / 2 处 —— #17 的 `_cell()` 死助手与 #20 的 `_RULE_INDEX` 死索引（均为本 diff 新增、零调用）。**这是死重信号，不是削减目标**：不因它降低任何发现的准入门槛，也不为凑数虚构删除。

**模式**：`markdown report-only`（`apply_local=false`）—— 本次审查**无任何 apply 权限，未修改被审树的任何文件**，Stage 5c 未执行；所有 finding 均交回调用方决定。

**阶段日志**：`stages.jsonl` 记录 `scope` / `select` / `dispatch` / `merge` / `validate` / `report` 各阶段边界与事实，`cost.status: complete`（累计 2723.969 s，10 位审查员，51 条候选，运行目录 1,852,005 字节）。

---

### Verdict

> **Verdict:** Ready with fixes（可合并，但须先修完 11 条 P1）
>
> **Reasoning:** 无 P0，但有 **11 条 P1**，其中 4 条是安全/数据边界问题且全部通过独立验证：#6 的 Excel 公式注入与 #7 的 PDF 本地文件读取 + SSRF 原语（均已实测复现）、#2 的事务回滚会静默丢弃调用方已 flush 的 CONFIRMED 状态（data-loss）、#4 的两个新错误码进不了项目自定的错误码权威源（public-contract）。另有 #5 的确认门无状态前置条件，使本路由存在的四眼控制在单个 REVIEWER 手上即可绕过，并把设备永久锁死给本该填数的设计人 —— 按 SPEC §3.2.4(4) 的意图衡量，这是本 sprint 最需要先修的功能性缺陷。计划完整性为 5/5 met，无未覆盖的实现单元，两条计划外行为规则（#33、#35）已单独登记且都有用户裁决背书，不构成合并阻塞。
>
> **本次审查的能力边界：** 跨模型通道未运行，**没有任何一条发现有经过独立跨模型印证**；同族审查员之间的一致只记为 reviewer 署名。`project-standards` 一位降级但其 2 条发现已完整恢复。环境只读，测试套件、迁移与数据库命令一次都没跑过；#1 / #13 的耗时是本分支真实实测，其余均为源码静态追踪。#2 的并发因果链与 #10 的 commit 路径是两条 P1 中最值得先补测试的，因为它们后果最重而实测证据最薄。
>
> **Fix order:**
> 1. **安全与数据边界先行**（三条 protected subject，互相独立，可并行）：#6 xlsx 公式注入 -> #7 PDF markup / SSRF -> #2 事务回滚（先补那条断言调用方写入被回滚的测试，再动 rollback -> savepoint）
> 2. **确认门与覆盖面**：先由产品定 #8 的口径，再落 #5 的 PENDING_CONFIRM 前置守卫（守卫按 #8 的口径实现）
> 3. **事件总线**：先定 #3 的 `event_id` 派生口径（决策闸），再一次改完 #2 的事务边界与 #10 的提交点（若第 1 步已改 #2，此处只需收 #10）
> 4. **导出层其余项**：#1 定上限 -> #13 移出事件循环
> 5. **偏差引擎取值**：#29 与 #31 一次编辑 -> #24 收紧 schema -> #19 收文档
> 6. **契约登记**（互不阻塞，可并行）：#11 SPEC 端点路径 -> #25 第 4 档结论 -> #30 buglog -> #4 错误码注册
> 7. **数据迁移**：先定 #14 覆盖策略 -> 随 #32 补验证 SQL -> #12 幂等（两处编辑必须同提交）-> #27 去重 -> #18 清过期注释
> 8. **机械清理**（无行为风险，可随时单独提交）：G7 的 #21 / #17 / #20 / #34，以及 #15、#28 的实现部分

### Actionable Findings

26 条，全部 `gated_auto` / `manual` + `downstream-resolver`，全部已由 validator 确证（28 条 confirmed 中的 26 条；另 2 条 confirmed 但归 `human`：`#3`、`#8`）。**本次为 report-only：未应用任何修复**，下表是交回调用方决定的队列。7 条 `human` 决策项（#3、#8、#14、#23、#28、#33、#35）不在其中，自动化修复器应停在这七条之前。

| # | Sev | File:line | What | Class | Fix | Conf |
|---|-----|-----------|------|-------|-----|------|
| 2 | P1 | `pcs-backend/app/services/events.py:165` | `_claim` 回滚调用方整个事务 | `gated_auto` | yes | 100 |
| 6 | P1 | `pcs-backend/app/services/supplier/deviation_report.py:208` | xlsx 公式注入（实测 `f`） | `gated_auto` | yes | 100 |
| 7 | P1 | `pcs-backend/app/services/supplier/deviation_report.py:277` | PDF markup / SSRF，未处理 500 | `gated_auto` | yes | 100 |
| 4 | P1 | `pcs-backend/app/services/supplier/actual_data_service.py:27` | 两个新错误码未进 meta 注册表 | `gated_auto` | yes | 100 |
| 1 | P1 | `pcs-backend/app/schemas/supplier.py:30` | `entries` 无上限，导出整体物化 | `manual` | yes | 100 |
| 5 | P1 | `pcs-backend/app/services/supplier/confirmation_service.py:98` | 确认/校核无状态前置条件 | `manual` | yes | 100 |
| 9 | P1 | `pcs-backend/app/services/cia_engine.py:173` | 吞异常，半应用转移被提交 | `manual` | yes | 75 |
| 10 | P1 | `pcs-backend/app/services/events.py:232` | claim 先于派发持久化 | `manual` | yes | 75 |
| 11 | P1 | `spec/工艺专用综合计算软件需求规格说明书 Web版 P7.md:145` | 端点路径与冻结 SPEC 不一致 | `manual` | yes | 75 |
| 12 | P2 | `pcs-backend/alembic/versions/p7_s4_001_event_idempotency.py:60` | downgrade 非幂等；闸不扫 `p7_s4_*` | `manual` | yes | 100 |
| 25 | P2 | `pcs-backend/app/schemas/supplier.py:73` | 第 4 档结论未登记 SPEC 修订 | `manual` | yes | 75 |
| 13 | P2 | `pcs-backend/app/api/v1/supplier.py:235` | 同步导出堵死事件循环 | `gated_auto` | yes | 100 |
| 24 | P2 | `pcs-backend/app/schemas/supplier.py:23` | 严格数值契约未生效，NaN 可过门 | `gated_auto` | yes | 75 |
| 29 | P2 | `pcs-backend/app/services/supplier/deviation_report.py:104` | 短路抢在 kind 派发前，丢 `requires_manual_check` | `gated_auto` | yes | 75 |
| 30 | P2 | `pcs-backend/app/services/supplier/deviation_service.py:135` | `742215d` 未登记 buglog | `gated_auto` | yes | 75 |
| 31 | P2 | `pcs-backend/app/services/supplier/deviation_service.py:156` | 叶轮直径配到转速设计值 | `gated_auto` | yes | 75 |
| 32 | P2 | `pcs-backend/scripts/p7_s4_003_seed_pump_design.py:62` | 回填无部署后验证 SQL | `gated_auto` | yes | 75 |
| 27 | P2 | `pcs-backend/app/services/equip_list/pump_design_data.py:124` | WHERE 子句重复两份 | `gated_auto` | yes | 75 |
| 19 | P2 | `pcs-backend/app/services/supplier/deviation_service.py:11` | 电机规则表文档漂移两处 | `gated_auto` | yes | 100 |
| 21 | P2 | `pcs-backend/tests/services/supplier/test_deviation_report.py:90` | WARNING 不阻断确认零覆盖 | `gated_auto` | yes | 100 |
| 22 | P2 | `pcs-backend/tests/test_cia_event_decoupling.py:155` | 静态守卫不可失败 | `gated_auto` | yes | 100 |
| 18 | P2 | `pcs-backend/app/services/supplier/deviation_report.py:7` | 过期缺口注释被本 diff 推翻 | `gated_auto` | yes | 100 |
| 15 | P2 | `pcs-backend/app/services/events.py:22` | docstring 指向已迁走的模块 | `gated_auto` | yes | 100 |
| 17 | P2 | `pcs-backend/app/services/supplier/deviation_report.py:189` | 死助手 `_cell()` | `gated_auto` | yes | 100 |
| 20 | P2 | `pcs-backend/app/services/supplier/deviation_service.py:166` | 死索引 `_RULE_INDEX` | `gated_auto` | yes | 100 |
| 34 | P3 | `pcs-backend/app/services/supplier/__init__.py:4` | 宣称不存在的模块 | `gated_auto` | yes | 100 |

**Run artifact:** `docs/ce-code-review/20261006-sprint4/`（`metadata.json` 与 `stages.jsonl` 已落盘，`cost.status: complete`）。`report.md` 由编排者在本会话补写 —— 报告页 agent 的 harness 禁止其写报告类 `.md`，但运行目录已复制到项目内，故报告在编排上下文完成落盘。
