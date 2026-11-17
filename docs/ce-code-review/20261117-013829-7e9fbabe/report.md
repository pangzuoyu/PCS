# PCS ce-code-review -- P10-B 批（全流程 E2E）

**Scope:** base `d73d1ac` -> head `f3b35e5` on branch `main` (55 files, 8659 changed lines, 974 executable non-test lines => size_band=large => depth=full)
**Intent:** 给 PCS 后端建一条真 PostgreSQL 隔离 schema 的端到端车道, 让 SPEC 的 18 场景 / 5 条 WF-PATH / 权限矩阵跑在真 app + 真库上; 并把「真后端通道」的 5 条前端 UI 流真正跑起来. 硬约束: 隔离 schema (CREATE SCHEMA -> alembic upgrade head -> DROP CASCADE); 默认车道必须跳过 e2e; PG 车道与 E2E 车道共用一个库 => 必须 flock 互斥; 驱动必须与生产一致; 跨项目 => 404 (与「不存在」同形), 角色不够 => 403.
**Plan (specification):** `docs/superpowers/plans/2026-11-13-p10-batch-b-fullflow-e2e.md` (plan_source = **explicit**)
**Criteria:** `/home/pangzy/code_project/PCS/CLAUDE.md` (repository root, governs every changed file)
**Mode:** markdown report-only (no local apply; the working tree was not modified)
**Depth:** full

**Reviewers (9):** correctness, project-standards, testing, maintainability, learnings, security, api-contract, reliability, adversarial
- reliability -- 晚到的一轮, 但已收齐并并入合并集 (9/9 persona artifacts on disk)
- adversarial -- 同时承担跨模型对抗视角 (本机无技能允许的 peer provider CLI, 见 Coverage)
- project-standards -- criteria = 仓库根 CLAUDE.md, 它治理全部改动文件
- api-contract -- 本批改了 OpenAPI schema 与响应载荷形状
- learnings -- 仓库有 learnings 语料 (`docs/solutions/**`) 可交叉核对

---

### 结论摘要

这一批交付的是**一条验证车道**（后端隔离 schema 的 E2E 车道 + 前端真后端通道的 5 条 UI 流）, 不是一个用户直接感知的功能. 按「人用这个软件拿到什么」重新分级, 结论是：**车道本身的存在是本批最大的正收益**（隔离 schema + 真 PG + 驱动与生产一致 + 默认车道 skip 闸门 + 两条车道的 flock 互斥都真的落地了, 也真的抓到了 5 个缺陷）, 但**这一批同时把「验证有效」这件事做成了空转**.

三个具体后果:

1. **车道的绿灯不承载它宣称的信息.** 闸门③只要求输出里出现 `N passed`（`scripts/pytest_pg.sh:83`）=> 30 条 e2e 场景里 29 条被静默跳过也报绿（#16）. E2E-009 用**命令式** `pytest.xfail()` 中止整条用例 => 「下载 200 + 字节数 > 0」这两段断言一次都没跑过（#4）. 前端 5 条 UI 流里有 3 条的断言**结构上不可能失败**: 越权流比的是两个 403（角色闸在项目守卫之前, `check_project_access_or_404` 一次都没执行, #5）、矩阵流断的是全局内置矩阵而不是种子那张（#6, 未决闸门）、路由扫描断的是 `index.html:9` 里恒在的静态 `#root`（#7）.
2. **本批唯一的产品修复是空操作.** `report_tasks._finalize` 新增的 `row.data_version = digest`（`report_tasks.py:118`）位于 `dup` 早退 `return` 之后 => 永远走不到; 活下来的那一行由 `report_service._upsert_report_file` 构造, 从头到尾没有 `data_version` => `GET /report/{id}/hash` 仍恒返空串（#3）; 而 buglog 给 bug-2165 记的根因（对象与被 flush 的行脱钩）也是错的. 同时把文件 sha256 塞进「数据版本」列, 让 `record_hash_digest` 与 `data_version` 从此是同一个值的两个名字（#14）.
3. **本批引入了面向真实用户的新行为.** 计算端点在请求路径上现场往**全局配置主表** `pipe_classes` 插一行 `source="COMPANY_STD"`（`pipe_chain_persist.py:95-138`, 调用点 `:260`）=> 每个用户在公司管级列表里都会看到一条没有版本/审批链的「碳钢标准（链计算占位）」; 且它是**先查后插、无 savepoint** => 两个并发首次计算里输的那个撞主键, 而 `calc_pipe_chain` 只 catch `PcsError` => 整个端点 500（#1）.

车道与种子的**护栏也只立了一半**: 车道只凭 `PCS_E2E_LANE=1` 一个环境变量放行、只查 URL 协议不查库名（#8）; 隔离只覆盖 `get_db` 这一条路, 全局 session factory 仍指向 public schema（#19）; 「不写 public」守卫在种子跑**之后**才取基线、且只数 4 张表（#22）; 两条车道靠 flock 互斥, 但同一个库上的 compose `migrate`/`seed` 两个写者不受锁约束（#15）.

**逐级条数**: P1 x 9 ,  P2 x 16 ,  P3 x 2（primary 27 条）+ pre-existing 1 条（不计入 verdict）.
**校验器已运行**: 单批 21 条（全部 P0/P1 + 全部 actionable）=> 确认 20 ,  否掉 0 ,  未决 1（#6）,  畸形 0 ,  失败 0 ,  捷径跳过 0.
**可执行队列**: 19 条（`gated_auto`/`manual` 且 owner = `downstream-resolver`）; 8 条 report-only（owner = `human` 或 `advisory`）; 其中 #6 是**核实闸门**, 任何修复者都不得在证据到手前把它当已确认缺陷去改.

---

### Actionable Findings

可执行队列 = `gated_auto`/`manual` 且 owner = `downstream-resolver`. 下面是完整 19 条, 每条已带 severity / file:line / 修法类型 / 校验状态.

| # | Severity | File | Issue | Route | Notes |
|---|---|---|---|---|---|
| 1 | P1 | `pcs-backend/app/services/pipe/pipe_chain_persist.py:112` | 占位管级先查后插无 savepoint => 并发首算撞主键 => 整条计算 500 | `gated_auto -> downstream-resolver` | suggested_fix present, validation: confirmed, confidence 100, mechanical, needs targeted verification |
| 3 | P1 | `pcs-backend/app/workers/report_tasks.py:118` | data_version 赋值在 dup 早退之后永不可达 => 审计哈希端点仍恒返空串 | `gated_auto -> downstream-resolver` | suggested_fix present, validation: confirmed, confidence 100, mechanical, needs targeted verification |
| 4 | P1 | `pcs-backend/tests/e2e_flows/test_e2e_report.py:91` | E2E-009 用命令式 pytest.xfail 中止用例 => 车道全绿且下载段从不执行 | `gated_auto -> downstream-resolver` | response stated in the detail line, validation: confirmed, confidence 100, mechanical, needs targeted verification |
| 5 | P1 | `pcs-frontend/e2e/real_backend_flows.spec.ts:144` | 越权 UI 断言恒等：bob 被角色闸挡在项目守卫之前 => 跨项目 404 分支从未执行 | `manual -> downstream-resolver` | response stated in the detail line, validation: confirmed, confidence 100, needs design input, needs targeted verification |
| 7 | P1 | `pcs-frontend/e2e/real_backend_route_sweep.spec.ts:56` | 路由扫描的『渲染出来了』断言恒真，且 console error / 4xx 只打印不断言 | `manual -> downstream-resolver` | response stated in the detail line, validation: confirmed, confidence 100, needs design input, needs targeted verification |
| 8 | P1 | `pcs-backend/tests/e2e_flows/conftest.py:93` | E2E 车道与种子脚本都没有目标库白名单 => 可在开发库上建 schema 并灌种子 | `gated_auto -> downstream-resolver` | response stated in the detail line, validation: confirmed, confidence 75, mechanical, needs targeted verification |
| 9 | P1 | `pcs-frontend/src/pages/routeWrappers.tsx:87` | useFetch 静默吞错且绕过 axios 401 拦截器 => token 过期后永久停在加载中 | `gated_auto -> downstream-resolver` | suggested_fix present, validation: confirmed, confidence 75, mechanical, needs targeted verification |
| 12 | P2 | `pcs-backend/app/api/v1/report.py:494` | 审计哈希端点返回值随行龄不同（老行与复用行恒返空串） | `gated_auto -> downstream-resolver` | suggested_fix present, validation: confirmed, confidence 75, mechanical, needs targeted verification |
| 13 | P2 | `pcs-backend/app/api/v1/sim_imports_query.py:325` | preview-streams 无 response_model，契约未记录本批统一的形状；注释与事实相反 | `gated_auto -> downstream-resolver` | suggested_fix present, validation: confirmed, confidence 75, mechanical, needs targeted verification |
| 16 | P2 | `pcs-backend/scripts/pytest_pg.sh:83` | 闸门③只要求『至少 1 passed』=> 29/30 场景被 skip 也是绿的 | `gated_auto -> downstream-resolver` | response stated in the detail line, validation: confirmed, confidence 75, mechanical, needs targeted verification |
| 17 | P2 | `pcs-backend/scripts/seed_e2e_flows.py:516` | 种子管级违反 PipeClassResponse 契约 => 按 id 查必 500 | `gated_auto -> downstream-resolver` | suggested_fix present, validation: confirmed, confidence 75, mechanical, needs targeted verification |
| 18 | P2 | `pcs-backend/tests/e2e_flows/conftest.py:272` | E2E 车道不跑 lifespan，注释称已补启动 seed 实测 0 处调用 | `manual -> downstream-resolver` | suggested_fix present, validation: confirmed, confidence 75, needs design input, needs targeted verification |
| 19 | P2 | `pcs-backend/tests/e2e_flows/conftest.py:289` | 隔离只覆盖 get_db：全局 session factory 仍指 public schema | `gated_auto -> downstream-resolver` | response stated in the detail line, validation: confirmed, confidence 75, mechanical, needs targeted verification |
| 20 | P2 | `pcs-backend/tests/e2e_flows/test_e2e_schema_parity.py:57` | schema 一致性检查塞进隔离车道且直连开发库 pcs / pcs_test | `manual -> downstream-resolver` | suggested_fix present, validation: confirmed, confidence 75, needs design input, needs targeted verification |
| 21 | P2 | `pcs-backend/tests/e2e_flows/test_e2e_schema_parity.py:73` | 两库 schema 一致闸只比彼此、不与代码 head 比 => 两库都落后也绿 | `gated_auto -> downstream-resolver` | suggested_fix present, validation: confirmed, confidence 75, mechanical, needs targeted verification |
| 22 | P2 | `pcs-backend/tests/e2e_flows/test_lane_smoke.py:240` | 『不写 public』守卫只覆盖 4 张表、只取一次基线 | `gated_auto -> downstream-resolver` | response stated in the detail line, validation: confirmed, confidence 75, mechanical, needs targeted verification |
| 23 | P2 | `pcs-frontend/package.json:20` | 真后端 UI 车道依赖 4 个仓库外环境变量 => 无法从仓库复现 | `gated_auto -> downstream-resolver` | suggested_fix present, validation: confirmed, confidence 75, mechanical, needs targeted verification |
| 24 | P2 | `pcs-frontend/src/pages/DashboardPage.tsx:40` | 仪表盘 404 修复条件不严：工作区无 project_id 时照旧 404 | `gated_auto -> downstream-resolver` | suggested_fix present, validation: confirmed, confidence 75, mechanical, needs targeted verification |
| 27 | P3 | `pcs-backend/tests/scripts/test_pytest_e2e_gate.py:95` | flock 守卫测试用原文子串匹配（含注释）且不校验 -n；唯一入口守卫只数一个字面量 | `gated_auto -> downstream-resolver` | suggested_fix present, validation: confirmed, confidence 75, mechanical, needs targeted verification |

#### Actionable 里必须人先裁的两处（不属于机械队列）

- **#2** (`manual -> human`) -- 占位管级到底归谁：改成一条数据迁移种一行, 还是允许运行时兜底但从公司列表里过滤掉. 这是产品/数据归属决策, 不是实现选择.
- **#6** (`advisory -> human`, validation = unresolved) -- 名字错配已核实, 但「内置 `DEFAULT_RECORD_3_LEVEL` 那行在目标库里到底存不存在」没核实到. 它**不在**可执行队列里.

---

### Triage Groups

| Group | Findings | Context | Preferred Resolution | Why |
|---|---|---|---|---|
| T1 -- 占位管级在运行时写全局配置主表 (decision-gate) | #1, #2 | 本批为了让链计算能落库，在请求路径上现场补一行 pipe_classes（source=COMPANY_STD）=> 同时踩到并发与数据归属两个面。 | 先裁 #2（占位行到底归谁：迁移里种一行，还是允许运行时兜底并从公司列表里过滤掉），再按裁决落 #1（savepoint + 重读赢家 / ON CONFLICT DO NOTHING）；#2 是设计裁决，#1 是可以照抄仓内 house pattern 的机械改。 | 两处同一个函数、同一个根因（运行时兜底代替配置流程）；先裁归属才不会把 #1 的修复做两遍。 |
| T2 -- bug-2165 的审计哈希链路：修复是空操作 (apply-queue) | #3, #4, #12, #14 | 本批自称修好了审计哈希端点，但赋值落在 dup 早退之后不可达，E2E-009 又用命令式 xfail 把用例中止 => 「修好了」今天没有任何证据。 | 一次做完四步：① #3 把 data_version 落到真正存活的那一行（report_service._upsert_report_file 建行时一并写 + _finalize 的 dup 分支补写）；② #4 把命令式 pytest.xfail 换成只标记那一条断言或先红后绿的真断言；③ #12 与 #14 一起裁（data_version 与 record_hash_digest 的语义分开，老行/复用行的空串一并处理）。 | 四条是同一条需求（审计要拿到完整哈希）的四个断点；任何一条单独修，车道仍然全绿。 |
| T3 -- 真后端前端通道的断言恒真 / 断错对象 (apply-queue) | #5, #6, #7 | 5 条真后端 UI 流里 3 条的断言结构上不可能失败：越权流比的是两个 403、矩阵流断的是内置全局矩阵、路由扫描断的是 #root 这个静态 div。 | 先 #5（改断项目守卫真正会走的那个分支）与 #7（断页面具体特征，或把 console error / 4xx 变成断言并把 TODO-159/160 那几个页面列成显式白名单）。#6 在验证阶段是**未决闸门**：名字错配已核实，但「内置那张矩阵在目标库里到底存不存在」没有核实到（迁移 p9_013 未读）=> 先查那一条证据再决定是改断言名字还是改种子名，**不要在证据到手前把它当成已确认的缺陷去改**。 | 三条同属一个通道、同一种失败形状（断言与被测行为脱钩）；修完这条通道才第一次具备「能证明」的资格。#6 需要的是一次证据查询，不是机械改。 |
| T4 -- E2E 车道的隔离与目标库护栏 (apply-queue) | #8, #18, #19, #20 | 计划最硬的一条约束是「开发库 public schema 一个字节不动」，但车道只凭一个环境变量放行，且只隔离了 get_db 这一条路。 | 先 #8（车道与种子脚本都加目标库名白名单，不匹配就非零退出），再 #19（把隔离 session factory 注入全局 session factory 的两个使用点），再 #20（把两库 schema 一致检查移出场景车道、它是发布前检查），最后 #18（补 lifespan 或删掉那句撒谎的注释）。 | 护栏要在最外层先立起来，否则后面三条的修复仍可能在开发库上执行。 |
| T5 -- 前端取数通道与真后端车道可复现性 (apply-queue) | #9, #23, #24 | useFetch 是绕过 axios 拦截器的第二套 HTTP 通道且静默吞错；仪表盘的 404 守卫条件写错；真后端通道的跑法没有落进仓库。 | 先 #9（统一走 src/api/client.ts 的 axios，或至少区分 401 与其它错误并暴露错误态），再 #24（守卫改成「拿到了真 project_id」而不是「选了工作区」），最后 #23（把 4 个环境变量写进 package.json 的 script 或 README，带默认值）。 | 三条都在「前端怎么把数据取回来」这一层；#9 不修，#23 写下的跑法也只会跑出空页面。 |
| T6 -- 契约口径与种子数据不符契约 (apply-queue) | #13, #17, #26 | preview-streams 统一了返回形状却没进 OpenAPI；种子管级那一行违反 PipeClassResponse（按 id 取必 500）；case_type 响应可空但请求仍必填。 | 先 #17（种子行按 PipeClassResponse 改，并加一条「按 id 取不 500」的断言），再 #13（补 response_model 并修那句与事实相反的注释），再 #26（决定请求侧是否也允许省略 case_type，并把结论写进契约）。 | 三条都是「形状与契约不一致」；种子那行是硬故障（500），另两条是契约漂移，先修会炸的那条。 |
| T7 -- E2E / PG 闸门的 fail-closed 不严 (apply-queue) | #16, #21, #22, #27 | 闸门③只要求「至少 1 passed」、两库一致闸只比彼此不与代码 head 比、「不写 public」守卫只盯 4 张表、flock 守卫自身用子串匹配（含注释）。 | 先 #16（闸门改为「无 skip 且 passed 数 >= 场景数」），再 #22（守卫快照覆盖本批写的所有表 + 种子前取基线），再 #21（加「与 alembic head 比」这一条），最后 #27（守卫剥注释后再匹配，入口守卫按命令形状匹配）。 | 这四条是闸门本身不可信；它们全绿时，车道的绿灯不含任何信息。 |

未进组的三条（彼此无关, 单独立组反而是装饰）: #10, #11, #25.

---

以下为**完整发现表**, 按严重度分组; 每条给出证据 / 为什么重要 / 建议修法 / 提出它的 reviewer / 校验状态.

### P1 -- High (9)

| # | File | Issue | Reviewer | Confidence |
|---|---|---|---|---|
| 1 | `pcs-backend/app/services/pipe/pipe_chain_persist.py:112` | 占位管级先查后插无 savepoint => 并发首算撞主键 => 整条计算 500 | reliability, correctness, adversarial | 100 |
| 2 | `pcs-backend/app/services/pipe/pipe_chain_persist.py:95` | 计算端点在运行时往全局配置主表写占位管级（假公司标准 + 两套互斥定义） | maintainability, correctness, api-contract, security, maintainability | 100 |
| 3 | `pcs-backend/app/workers/report_tasks.py:118` | data_version 赋值在 dup 早退之后永不可达 => 审计哈希端点仍恒返空串 | reliability, correctness | 100 |
| 4 | `pcs-backend/tests/e2e_flows/test_e2e_report.py:91` | E2E-009 用命令式 pytest.xfail 中止用例 => 车道全绿且下载段从不执行 | adversarial, testing | 100 |
| 5 | `pcs-frontend/e2e/real_backend_flows.spec.ts:144` | 越权 UI 断言恒等：bob 被角色闸挡在项目守卫之前 => 跨项目 404 分支从未执行 | adversarial, learnings | 100 |
| 6 | `pcs-frontend/e2e/real_backend_flows.spec.ts:41` | 签署矩阵 UI 流断的是全局内置矩阵，不是种子那张 | adversarial, correctness, maintainability | 100 |
| 7 | `pcs-frontend/e2e/real_backend_route_sweep.spec.ts:56` | 路由扫描的『渲染出来了』断言恒真，且 console error / 4xx 只打印不断言 | adversarial, project-standards, learnings, testing | 100 |
| 8 | `pcs-backend/tests/e2e_flows/conftest.py:93` | E2E 车道与种子脚本都没有目标库白名单 => 可在开发库上建 schema 并灌种子 | adversarial, testing, security, security, reliability | 75 |
| 9 | `pcs-frontend/src/pages/routeWrappers.tsx:87` | useFetch 静默吞错且绕过 axios 401 拦截器 => token 过期后永久停在加载中 | reliability, maintainability | 75 |

- **#1** -- `pcs-backend/app/services/pipe/pipe_chain_persist.py:112` -- 占位管级先查后插无 savepoint => 并发首算撞主键 => 整条计算 500
  - Why it matters: 运行时兜底建占位管级用的是「先查后插」，**没有** `begin_nested()` + `IntegrityError` 兜底 ---- 与本仓自己的 house pattern（`docs/solutions/database-issues/get-or-create-default-row-race-savepoint-reread.md`，以及 `report_service._upsert_report_file` 的写法）相反。两个并发的 `POST /api/v1/pipe/calc-chain` 请求同时看到「CS-STD 不存在」=> 都 INSERT => 输家撞 `pipe_classes.class_id` 主键唯一约束 => IntegrityError。而 `calc_pipe_chain` 只 catch `PcsError`（pipe.py:213-216）=> IntegrityError 直接逃出去 => **整个端点 500**，且该事务已被 abort => 同请求后续语句一并失败。窗口虽窄（占位行一旦提交就长期存在），但正是「首次并发」或「上次事务回滚后」会命中，而那恰好是 E2E 车道首跑/重跑的时刻。
  - Evidence:
    - pcs-backend/app/services/pipe/pipe_chain_persist.py:105-111 -- `    exists = (await db.execute(select(PipeClass.class_id).where(PipeClass.class_id == class_id))).scalar_one_or_none()` / `    if exists is not None:` / `        return`
    - pcs-backend/app/services/pipe/pipe_chain_persist.py:112-138 -- `    db.add(` / `        PipeClass(` / `            class_id=class_id,` ... `    )` / `    await db.flush()` => **裸 INSERT，没有 savepoint、没有 IntegrityError 分支**
    - pcs-backend/app/services/pipe/pipe_chain_persist.py:260 -- `    await _ensure_placeholder_pipe_class(db, PLACEHOLDER_MATERIAL_CLASS)`（在 `db.add(row)` + flush 之前）
    - pcs-backend/app/models/config_domain.py:237 -- `    class_id: Mapped[str] = mapped_column(String(50), primary_key=True)` => 撞主键即唯一约束违例
    - pcs-backend/app/api/v1/pipe.py:213-216 -- `    try:` / `        row, outlet = await persist_pipe_chain_result(db, chain_inp, chain_res)` / `    except PcsError as e:` / `        raise _to_http(e) from e` => IntegrityError 不在 catch 范围 => 500
    - pcs-backend/app/services/pipe/pipe_chain_persist.py:105-111 -- `exists = (await db.execute(select(PipeClass.class_id).where(PipeClass.class_id == class_id))).scalar_one_or_none()` / `if exists is not None: return`
    - pcs-backend/app/services/pipe/pipe_chain_persist.py:112-138 -- `db.add(PipeClass(class_id=class_id, ...))` / `await db.flush()`（无 savepoint、无 IntegrityError 兜底）
    - pcs-backend/scripts/seed_e2e_flows.py:257-269 -- 本批新脚本的house pattern：`async with db.begin_nested(): db.add(entity); await db.flush()` / `except IntegrityError: winner = (await db.execute(match)).scalar_one_or_none()`（产品代码这段没照抄）
    - pcs-backend/app/services/pipe/pipe_chain_persist.py:95-133 -- `exists = (await db.execute(select(PipeClass.class_id)...)).scalar_one_or_none(); if exists is not None: return; db.add(PipeClass(...)); await db.flush()`（无 savepoint、无 IntegrityError 处理）
    - pcs-backend/app/models/config_domain.py:237 -- `class_id: Mapped[str] = mapped_column(String(50), primary_key=True)`（唯一约束来源）
    - pcs-backend/scripts/seed_e2e_flows.py:243-270 -- `_get_or_create` 的 house pattern（`async with db.begin_nested()` + IntegrityError 后重读）=> 同仓同批已有正确写法
    - pcs-backend/app/services/pipe/pipe_chain_persist.py:130-134 -- 注释自认 `source="COMPANY_STD"` 是为了『在下游列表里看不见就断不了断言』；而 `app/services/pipe_class_service.py:136-148` 的 `list_company` 固定过滤 `source == 'COMPANY_STD'` => 该假标准会出现在产品列表里
  - Suggested fix / response: 照 house pattern 改成 savepoint + 重读赢家：`try: async with db.begin_nested(): db.add(PipeClass(...)); await db.flush() except IntegrityError: pass`（冲突时复用并发方刚插的那一行即可，不必报错）。假设：`class_id` 相同即视为同一占位管级，复用赢家行是安全的。
  - Validation: confirmed / protected subject: concurrency / incidence NOT measured (code permits it, nobody showed it happens)
  - Reviewers: reliability, correctness, adversarial
  - Route: `gated_auto -> downstream-resolver`

- **#2** -- `pcs-backend/app/services/pipe/pipe_chain_persist.py:95` -- 计算端点在运行时往全局配置主表写占位管级（假公司标准 + 两套互斥定义）
  - Why it matters: 「算一次管道压降」现在会往**配置主表** `pipe_classes` 插一行。三个具体代价：(1) 落库层从「只写业务结果」变成「写业务结果 + 写主数据」，主数据的生命周期被计算请求隐式创建；(2) 这行 `source="COMPANY_STD"` => 它会出现在**公司管级列表 UI** 里，用户看到一条叫「碳钢标准（链计算占位）」的公司标准，而它没有 ConfigAsset / 版本 / 5 态审批 => 与 `PipeClassService.create`（`app/services/pipe_class_service.py:173`）造出来的行形态不同 => 公司管级列表里出现两种来源的、状态语义不同的行；(3) 手写 ORM 构造绕过了 canonical 的创建路径（`PipeClassService.create` / `create_with_config_asset`）=> 这条占位行永远不在配置资产的审批/版本链里。配置数据的正确落点是数据迁移（仓里已有先例：`alembic/versions/p9_013_bind_default_record_matrix.py` 就是插一条矩阵行），不是运行时兜底。
  - Evidence:
    - pcs-backend/app/services/pipe/pipe_chain_persist.py:95-138 -- 新增 `_ensure_placeholder_pipe_class`：手写 `PipeClass(...)` + `db.add` + `await db.flush()`，并写死 `source="COMPANY_STD"` / `dn_series_json={"min": 15.0, "max": 600.0}` / `sch_series_json={"min": "0.5", "max": "1.2"}`
    - pcs-backend/app/services/pipe/pipe_chain_persist.py:260 -- `await _ensure_placeholder_pipe_class(db, PLACEHOLDER_MATERIAL_CLASS)` 位于 `persist_pipe_chain_result` 主路径（每次链计算都走）
    - pcs-backend/app/services/pipe_class_service.py:173-187 -- canonical 创建路径 `PipeClassService.create`（走 `PipeClassCreate` + `ConfigAsset` 版本链 + status=DRAFT），本 diff 的兜底**绕过**了它
    - pcs-backend/app/services/pipe_class_service.py:149 -- `stmt = select(PipeClass).where(PipeClass.source == "COMPANY_STD")` => 占位行必然出现在公司管级列表
    - pcs-backend/app/services/pipe/pipe_chain_persist.py:130-134 -- `# WARNING `source="COMPANY_STD"` ---- 公司级管架列表**只列** `source == 'COMPANY_STD'` 的行` / `source="COMPANY_STD",`
    - pcs-backend/app/services/pipe_class_service.py:149 -- `stmt = select(PipeClass).where(PipeClass.source == "COMPANY_STD")`（status 只在显式传参时过滤）
    - pcs-backend/app/api/v1/pipe_classes.py:112 -- `status: str | None = Query(None), keyword: str | None = Query(None),`（列表端点缺省不过滤状态 => DRAFT 的占位行也在列）
    - pcs-backend/app/models/config_domain.py:262-264 -- `status: Mapped[str] = mapped_column(String(20), default="DRAFT", ...)`（占位行落库即 DRAFT）
    - pcs-backend/app/services/pipe/pipe_chain_persist.py:134 -- source="COMPANY_STD",
    - pcs-backend/app/services/pipe/pipe_chain_persist.py:92 -- PLACEHOLDER_MATERIAL_CLASS = "CS-STD"
    - pcs-backend/app/services/pipe_class_service.py:149 -- stmt = select(PipeClass).where(PipeClass.source == "COMPANY_STD")  => 占位行进公司列表
    - pcs-backend/app/schemas/pipe_class.py:77 -- source: Literal["COMPANY_STD", "PROJECT"] => 契约里没有「占位」这一态
    - pcs-backend/tests/e2e_flows/test_e2e_calc_chains.py:54-59 -- assert after_count == before_count + 1（「管级表多了一行」）而计算结果落在 piping_results => 这条断言实际断的是占位行副作用
    - pcs-backend/app/services/pipe/pipe_chain_persist.py:260 -- `    await _ensure_placeholder_pipe_class(db, PLACEHOLDER_MATERIAL_CLASS)` (call site inside the request-path persist function)
    - pcs-backend/app/services/pipe/pipe_chain_persist.py:134 -- `            source="COMPANY_STD",` (the injected row is deliberately a company-level standard)
    - pcs-backend/app/services/pipe/pipe_chain_persist.py:95 -- `async def _ensure_placeholder_pipe_class(db: AsyncSession, class_id: str) -> None:` (runtime insert of the shared row)
    - pcs-backend/app/models/config_domain.py:237 -- `    class_id: Mapped[str] = mapped_column(String(50), primary_key=True)` / `:238 asset_id ... ForeignKey("config_assets.asset_id")` => `pipe_classes` is global, not project-scoped
    - pcs-backend/app/services/pipe_class_service.py:149 -- `        stmt = select(PipeClass).where(PipeClass.source == "COMPANY_STD")` => the row is listed to every company-standard reader
    - pcs-backend/app/services/pipe/pipe_chain_persist.py:3022-3024 (diff) -- "WARNING 为什么不能靠「迁移里种一行」... 而这里是**运行时占位**" => the choice of a request-time insert is deliberate
    - pcs-backend/scripts/seed_e2e_flows.py:101 `FLOW_PIPE_CLASS_ID = "E2E-SEED-CS"` 与 515-517 `allowable_stress_json={"20#": 137.0}, dn_series_json={"DN150": 1.0}, sch_series_json={"DN150": 40.0}`
    - pcs-backend/app/services/pipe/pipe_chain_persist.py:92 `PLACEHOLDER_MATERIAL_CLASS = "CS-STD"` 与 125-128 `dn_series_json={"min": 15.0, "max": 600.0}` / `sch_series_json={"min": "0.5", "max": "1.2"}`
    - pcs-backend/app/models/config_domain.py:249 `sch_series_json: Mapped[list] = mapped_column(JSONB)`（ORM 说 list）
    - pcs-backend/app/schemas/pipe_class.py:61-63 `sch_series_json: dict[str, str] = Field(..., description="DN -> Sch 壁厚系列映射...")`（schema 说 dict[str,str]）
    - pcs-backend/app/services/pipe_class_service.py:149 `select(PipeClass).where(PipeClass.source == "COMPANY_STD")` => 种子的 E2E_SEED 行从不出现在列表端点 => 其形状错误当前不可见
  - Suggested fix / response: 删掉 `_ensure_placeholder_pipe_class` 与 `PLACEHOLDER_MATERIAL_CLASS`，改成一条**数据迁移**插 `CS-STD` 这行（形状照 `PipeClassService.create` 的 payload 语义：`source="COMPANY_STD"`、`dn_series_json={"min":...,"max":...}`、`sch_series_json` 用仓里既定的 DN->Sch 形状）；`persist_pipe_chain_result` 恢复成纯落库。若坚持运行时兜底，则至少改为调 `PipeClassService.create`（同一套版本/状态语义），而不是手写 ORM 行。
  - Validation: confirmed
  - Reviewers: maintainability, correctness, api-contract, security, maintainability
  - Route: `manual -> human`

- **#3** -- `pcs-backend/app/workers/report_tasks.py:118` -- data_version 赋值在 dup 早退之后永不可达 => 审计哈希端点仍恒返空串
  - Why it matters: 回答「为什么赋值执行了、库里仍是 NULL」：**对象没有与被 flush 的行脱钩** ---- 是这行赋值**根本走不到**。`_finalize` 的 `dup` 守卫在 107-111 行就 `return` 了，而 `dup` **必然存在**：`report_service.generate` -> `store_rendered` -> `_upsert_report_file` 已经在库里有了一行 `content_hash == digest` 且 `report_file_id` **不同于**占位行（report_service.py:612-618，新 uuid4）。于是 dup 分支命中 => 占位行被 `delete` => 活下来的那行是 `_upsert_report_file` 构造的、**从头到尾没有 `data_version` 字段** => 落库仍是 NULL => `GET /api/v1/report/{id}/hash` 的 `_expected_digest(row)`（report.py:308）继续返回 `""` => E2E-009 只能继续 `pytest.xfail`。=> 本批声称修好的「审计要完整哈希」实际没修好，而且 buglog 给 bug-2165 记的根因（对象与被 flush 的行脱钩）是错的，会把后来的人引到错误的方向。
  - Evidence:
    - pcs-backend/app/workers/report_tasks.py:107-111 -- `    if dup is not None:` / `        # 同内容已存在（bug-155 修好后的复用语义）：删掉自己的占位行，返回已有行。` / `        await db.delete(row)` / `        await db.flush()` / `        return str(dup.report_file_id)`
    - pcs-backend/app/workers/report_tasks.py:118 -- `    row.data_version = digest`（本批新增的 `+` 行，位于上面那个 `return` 之后 => 不可达）
    - pcs-backend/app/services/report/report_service.py:612-618 -- 活下来的那行是这么造的、**没有 data_version**：`    row = ReportFile(` / `        report_file_id=kw["report_file_id"],` / `        project_id=kw["project_id"], content_hash=kw["content_hash"],` / `        file_path=kw["relpath"], file_format=kw["fmt"],` / `        size_bytes=kw["size"], status="SUCCEEDED",` / `        has_assumption_page=kw["has_assumption"],` / `    )`
    - pcs-backend/app/workers/report_tasks.py:167-173 -- `            out = await report_service.generate(` ... `            file_id = await _finalize(` => `store_rendered` 的 upsert **先于** `_finalize` => dup 必然命中
    - pcs-backend/app/services/report/report_service.py:606-610 -- `    existing = (await db.execute(select(ReportFile).where(ReportFile.content_hash == kw["content_hash"]))).scalar_one_or_none()` => 即使命中旧行，`content_hash == digest` 的行照样存在 => dup 照样命中
    - pcs-backend/app/api/v1/report.py:308 -- `        record_hash_digest=_expected_digest(row),` => 审计端点读的是 `row.data_version or ""`
    - pcs-backend/tests/e2e_flows/test_e2e_report.py -- E2E-009 仍是 `pytest.xfail`（条件是 `record_hash_digest` 为空）=> 车道自己记录着这条需求仍未满足
    - pcs-backend/app/workers/report_tasks.py:109-111 -- `await db.delete(row)` / `await db.flush()` / `return str(dup.report_file_id)`（dup 分支先于 data_version 赋值 return）
    - pcs-backend/app/workers/report_tasks.py:113-118 -- `row.content_hash = digest` ... `row.data_version = digest`（被上面那条 return 挡住，永不执行）
    - pcs-backend/app/services/report/report_service.py:612-618 -- `row = ReportFile(report_file_id=..., project_id=..., content_hash=kw["content_hash"], file_path=kw["relpath"], file_format=kw["fmt"], size_bytes=kw["size"], status="SUCCEEDED", has_assumption_page=kw["has_assumption"])` ---- 真正存活的那一行没有 data_version
    - pcs-backend/app/api/v1/report.py:494 -- `return row.data_version or ""`（端点读的仍是空串）
    - pcs-backend/tests/e2e_flows/test_e2e_report.py:90-94 -- `if not digest.json().get("record_hash_digest"): pytest.xfail("审计哈希端点在生成的报表上恒返回空串（bug-2165 ... 根因未完全隔离）")`（本批自己的用例仍 xfail）
    - MERGE-LEAF VERIFIED pcs-backend/app/workers/report_tasks.py:101-111 - the dup query runs first and `if dup is not None:` deletes the placeholder row and returns at line 111, so line 118 (`row.data_version = digest`) is unreachable on that path
    - MERGE-LEAF VERIFIED pcs-backend/app/services/report/report_service.py:420 generate -> 428 store_rendered -> 513 _upsert_report_file -> 612-618 builds a ReportFile with content_hash=kw['content_hash'] and NO data_version; report_tasks.py:167-173 calls generate before _finalize, so the dup query always matches that row and the surviving row never gets data_version => GET /report/{id}/hash keeps returning an empty string
  - Suggested fix / response: 把 `data_version` 写到**活下来的那一行**上，而不是写占位行：`report_service._upsert_report_file`（report_service.py:612-618）构造 `ReportFile(...)` 时补 `data_version=kw["content_hash"]`（同一处也修好 `report_builder_tasks.py:227` 那条路径）；同时在 `_finalize` 的 dup 分支里，于 `return str(dup.report_file_id)` 之前补 `dup.data_version = digest` 以覆盖「命中旧行」的情形。假设：`data_version` 的语义就是内容指纹（依 report.py:487-494 的 docstring）。验证：把 E2E-009 的 `pytest.xfail` 去掉并断言 `record_hash_digest == content_hash`。
  - Validation: confirmed / protected subject: public-contract
  - Reviewers: reliability, correctness
  - Route: `gated_auto -> downstream-resolver`

- **#4** -- `pcs-backend/tests/e2e_flows/test_e2e_report.py:91` -- E2E-009 用命令式 pytest.xfail 中止用例 => 车道全绿且下载段从不执行
  - Why it matters: 哈希为空时走的是**命令式** `pytest.xfail()` => 它**抛异常中止整条用例** => 后面『下载 200 + 字节数 > 0』两段断言**一次都不执行** => 车道绿灯里混着一条**没跑完**的场景（报告成品的『可下载且非空』从未被验过）。而闸门③只要求输出里有 `N passed` => xfailed 不算失败 => **本批自己修的 `report_tasks._finalize`（写 `data_version`）一旦回归，这条用例变成 xfailed，车道依旧全绿** => 那条产品修复没有任何回归保护，且『一条 e2e 场景没跑完』在闸门视角里完全看不出来。
  - Evidence:
    - pcs-backend/tests/e2e_flows/test_e2e_report.py:90-94 -- `if not digest.json().get("record_hash_digest"): pytest.xfail("审计哈希端点在生成的报表上恒返回空串（bug-2165...）")`（命令式 xfail => 中止后续语句）
    - pcs-backend/tests/e2e_flows/test_e2e_report.py:96-100 -- `download = await e2e_client.get(...); assert download.status_code == 200; assert len(download.content) > 0`（在 xfail 之后 => 空哈希时永不执行）
    - pcs-backend/scripts/pytest_pg.sh:83-86 -- 闸门只 grep `[1-9][0-9]* passed` => xfailed 不影响闸门结论
    - pcs-backend/app/workers/report_tasks.py:114-118 -- 本批的修复 `row.data_version = digest`（回归 => 回到 xfailed => 车道仍绿）
    - pcs-backend/tests/e2e_flows/test_e2e_report.py:90-94 ---- `if not digest.json().get("record_hash_digest"): pytest.xfail("审计哈希端点在生成的报表上恒返回空串（bug-2165...）")`
    - pcs-backend/app/workers/report_tasks.py:118 ---- `row.data_version = digest`（本批新增的唯一生产修复）
    - .superpowers/sdd/2026-11-13-p10-batch-b-fullflow-e2e/progress.md:365 ---- 「WARNING **根因未完全隔离**（赋值执行、库里仍 NULL）=> E2E-009 标 `xfail` => **TODO-158**」
    - pcs-backend/scripts/pytest_pg.sh:83 ---- 闸门③ 只 grep 「[1-9][0-9]* passed」，xfailed 不计入 => 少一条断言不会让车道变红
    - MERGE-LEAF VERIFIED pcs-backend/tests/e2e_flows/test_e2e_report.py:90-94 - `pytest.xfail(...)` is called imperatively inside the test body, so it raises and aborts the test; the download assertions at lines 96-100 never run when the hash is empty
  - Suggested fix / response: 把命令式 `pytest.xfail()` 拆掉：把 E2E-009 拆成两条用例 ---- (a) `test_e2e_009_audit_hash_present` 对 `record_hash_digest` 做**硬断言**（今天应当是红的，红着才诚实）；(b) `test_e2e_009_download_non_empty` 断 `200` + `len(content) > 0`。这样车道在产品缺陷未修前会红，而不是带着一条没跑完的场景报绿。
  - Validation: confirmed
  - Reviewers: adversarial, testing
  - Route: `gated_auto -> downstream-resolver`

- **#5** -- `pcs-frontend/e2e/real_backend_flows.spec.ts:144` -- 越权 UI 断言恒等：bob 被角色闸挡在项目守卫之前 => 跨项目 404 分支从未执行
  - Why it matters: 这条用例自称验证「跨项目 => 与『不存在』同形 => 不泄露资源存在性」，但它比较的两个状态码都是**角色闸**给的 403：`bob` 在 mock 登录里是 CHECKER（mock_auth.py:16），而列表端点先跑 `require_roles(user, "DESIGNER", "PROCESS_CONTROLLER", "SYSTEM_ADMIN")`（streams.py:407），**之后**才跑项目守卫 `check_project_access_or_404`（streams.py:410）=> 两个请求都在 407 就被挡回，项目守卫**一次都没执行** => 断言退化成 `403 === 403` => **把 `check_project_access_or_404` 整段删掉，这条用例照样绿** => 真后端通道对「跨项目 404」零覆盖。真正在验 404 的是后端车道那条 `test_e2e_016`（用 DESIGNER 的 e2e-outsider）=> 前端这条给人的保证是假的。
  - Evidence:
    - pcs-frontend/e2e/real_backend_flows.spec.ts:144-148 -- `expect(unauthorized.status(), ...).toBe(nonexistent.status());`（用例注释自称『抓住泄露存在性』）
    - pcs-backend/app/api/v1/streams.py:407 -- `require_roles(user, "DESIGNER", "PROCESS_CONTROLLER", "SYSTEM_ADMIN")`（在项目守卫之前）
    - pcs-backend/app/api/v1/streams.py:410-413 -- `await check_project_access_or_404(db, user_id=..., project_id=..., actor_roles=...)`（排在角色闸之后 => CHECKER 永远走不到）
    - pcs-backend/app/api/v1/mock_auth.py:14-18 -- `MOCK_USERS = {"alice": "DESIGNER", "bob": "CHECKER", "carol": "APPROVER", "dan": "SYSTEM_ADMIN"}` => bob/carol 过不了角色闸，dan 走 SYSTEM_ADMIN bypass => mock 登录的四个用户**没有一个**能表达『角色够但没授权行』
    - 构造：删掉 streams.py:410 的项目守卫 -> bob 请求 flows 项目仍返回 403（角色闸）-> nonexistent 仍 403 -> 断言仍通过 => 用例对被它命名的缺陷不敏感
    - pcs-frontend/e2e/real_backend_flows.spec.ts:133-134 -- `// WARNING **具体码取决于闸门顺序**（物流列表端点先过**角色闸** => CHECKER => 403）` / `// => => 断「两个码相等」` => 短路被观察到但被接受为合格断言
    - pcs-backend/app/api/v1/streams.py:407 -- `    require_roles(user, "DESIGNER", "PROCESS_CONTROLLER", "SYSTEM_ADMIN")` => CHECKER 在项目守卫之前被 403 拦下
    - pcs-backend/app/api/v1/config.py:96-98 -- `        raise HTTPException(` / `            status_code=403,` => 角色闸的确抛 403
    - pcs-backend/app/api/v1/mock_auth.py:15-18 -- `    "alice": "DESIGNER",` / `    "bob": "CHECKER",` => 被测身份是 CHECKER
    - pcs-backend/app/api/v1/streams.py:410-413 -- `    await check_project_access_or_404(` => 该分支在这条用例里从未执行
    - MERGE-LEAF VERIFIED pcs-frontend/e2e/real_backend_flows.spec.ts:133-134 - the test's own comment says the streams list endpoint runs the ROLE gate first and that a CHECKER gets 403, then line 144-148 compares unauthorized.status() with nonexistent.status() => both are the role gate's 403, so the project guard branch is never exercised
  - Suggested fix / response: 把被测身份换成**角色够、授权行缺**的那个人：用 `alice`(DESIGNER) 且只给 flows 项目授权，跨项目请求就能走到 `check_project_access_or_404`（streams.py:410）并返回 404；断言要断**状态码 + body 形状**（code 与 message 模板逐字相同），不是 `403 === 403`。若 mock 登录四个用户都拿不到这种身份，就在种子里补一个项目内角色为 DESIGNER、但对被访问项目无 `UserProject` 行的用户。
  - Validation: confirmed / protected subject: authorization-authentication
  - Reviewers: adversarial, learnings
  - Route: `manual -> downstream-resolver`

- **#6** -- `pcs-frontend/e2e/real_backend_flows.spec.ts:41` -- 签署矩阵 UI 流断的是全局内置矩阵，不是种子那张
  - Why it matters: 断言用的名字 `DEFAULT_RECORD_3_LEVEL` 是迁移 p9_013 在**任何**已迁移库里都有的**全局内置矩阵**（signature_matrix_service.py:124 / p9_013 的 INSERT），而 P10-B 种子那张叫 `E2E_FLOWS_RECORD_3_LEVEL`（seed_e2e_flows.py:583）且只绑在 flows 项目上 => 断言被内置矩阵满足，三级链的 CHECKER/REVIEWER/APPROVER 也是内置矩阵就有 => **种子没灌进去 / matrix_name 漂了 / 项目绑定没生效，这条用例照样绿** => 这条 UI 流对『P10-B 种子是否到位』的验证力为零（其余 4 条 UI 流断的是种子专有值，所以只有这一条是空壳）。
  - Evidence:
    - pcs-frontend/e2e/real_backend_flows.spec.ts:41 -- `const MATRIX_NAME = 'DEFAULT_RECORD_3_LEVEL';`
    - pcs-backend/scripts/seed_e2e_flows.py:583 -- `matrix_name="E2E_FLOWS_RECORD_3_LEVEL",`（种子那张的真名）
    - pcs-backend/app/services/signature_matrix_service.py:124 -- `DEFAULT_RECORD_MATRIX_NAME = "DEFAULT_RECORD_3_LEVEL"`（全局内置，任何迁移过的库都有）
    - pcs-frontend/e2e/real_backend_flows.spec.ts:118-122 -- 断 `MATRIX_NAME` 可见 + 页面含 CHECKER/REVIEWER/APPROVER => 内置矩阵全部满足
    - pcs-frontend/e2e/real_backend_flows.spec.ts:113-123 -- `@real-backend 签署矩阵：项目绑定的矩阵与三级链可见` ... `await expect(realPage.getByText(MATRIX_NAME, { exact: false })).toBeVisible();`
    - pcs-backend/scripts/seed_e2e_flows.py:583 -- `matrix_name="E2E_FLOWS_RECORD_3_LEVEL",`（种子矩阵的名字不是断言里那个）
    - pcs-backend/alembic/versions/p9_013_bind_default_record_matrix.py:59 -- `_MATRIX_NAME = "DEFAULT_RECORD_3_LEVEL"`（内置全局模板，恒存在）
    - pcs-frontend/e2e/real_backend_flows.spec.ts:32-41 -- `const FLOW_PROJECT_ID = '2488b011-14fc-584b-966e-1e2dfaeb9eb7';` / `const STREAM_NAME = 'E2E-FLOW-S-001';` / `const DELIVERABLE_TITLE = 'E2E 流程级种子计算书';` / `const MATRIX_NAME = 'DEFAULT_RECORD_3_LEVEL';`，注释分别写着「（`scripts/seed_e2e_flows.py::FLOW_STREAM_NAMES`）」「（`_ensure_matrix`）」
    - pcs-backend/scripts/seed_e2e_flows.py:583-584 -- `_ensure_matrix` 造的是 `matrix_name="E2E_FLOWS_RECORD_3_LEVEL"` => 与 spec 的 `MATRIX_NAME` 不一致
    - pcs-backend/alembic/versions/p9_013_bind_default_record_matrix.py:59 -- `_MATRIX_NAME = "DEFAULT_RECORD_3_LEVEL"` => spec 断的其实是迁移插入的内置矩阵，不是 E2E 种子那条
    - pcs-backend/scripts/seed_e2e_flows.py:80-117 -- 种子 id 全部由 `_uid("pcs-e2e-flows-*")` 派生 => 前端那串 uuid 是手工反推出来的，没有生成链路
  - Suggested fix / response: 这是**核实闸门，不是待改缺陷**：先读 `alembic/versions/p9_013_bind_default_record_matrix.py` 并在目标库直查 `DEFAULT_RECORD_3_LEVEL` 是否存在。存在 => 断言被全局内置矩阵满足 => 把断言改成种子那张 `E2E_FLOWS_RECORD_3_LEVEL`（或断种子专有值）；不存在 => 这条流是因为别的原因红 => 修种子/迁移。**证据到手前不要动代码，也不要把它当成已确认的缺陷去修。**
  - Validation: unresolved (verification gate: The name mismatch is verified (real_backend_flows.spec.ts:41 asserts 'DEFAULT_RECORD_3_LEVEL' while scripts/seed_e2e_flows.py:583 creates 'E2E_FLOWS_RECORD_3_LEVEL', and the built-in name is defined at signature_matrix_service.py:124), but whether that built-in row actually exists in the target DB - which decides whether the flow is green-without-the-seed or red - could not be verified within budget (migration p9_013 not read).)
  - Reviewers: adversarial, correctness, maintainability
  - Route: `advisory -> human`

- **#7** -- `pcs-frontend/e2e/real_backend_route_sweep.spec.ts:56` -- 路由扫描的『渲染出来了』断言恒真，且 console error / 4xx 只打印不断言
  - Why it matters: `#root` 是 index.html:9 里的**静态 div**，与 React 是否渲染成功无关 => `locator('#root').count() > 0` **永远为真** => `expect(results.every(r => r.root), '有路由没渲染出来').toBe(true)` **永远通过** => 扫描**证明不了任何一条路由渲染成功**（白屏、渲染异常、错误边界、懒加载失败都照样绿）。再加上控制台 error 与 4xx/5xx 被显式降级为『只打印不断言』（64-69 行），本仓 CLAUDE.md 批末 QA 闸门里的『控制台无 antd/React/TS error』『核心端点无 404』**没有任何自动断言在守** => 真后端车道可以在应用大面积报错时依然全绿。
  - Evidence:
    - pcs-frontend/e2e/real_backend_route_sweep.spec.ts:56 -- `const root = (await realPage.locator('#root').count()) > 0;`
    - pcs-frontend/e2e/real_backend_route_sweep.spec.ts:70 -- `expect(results.every((r) => r.root), '有路由没渲染出来').toBe(true);`
    - pcs-frontend/index.html:9 -- `    <div id="root"></div>`（静态容器 => count 恒为 1）
    - pcs-frontend/e2e/real_backend_route_sweep.spec.ts:64-69 -- 『WARNING **只断「路由可达」**...「控制台无 error / 无 4xx-5xx」**不作为断言**』
    - 构造：让 `/sim/streams` 页面渲染抛错 => React 卸载子树 => `#root` 仍在 DOM => root=true => 断言通过 => 扫描对该路由的失败完全无感
    - CLAUDE.md《Per-Batch QA Gate》流程步骤 2：「浏览器：login 200 + dashboard 渲染 + 各 Page 路由可达」「控制台：无 antd / React / TypeScript error」「网络：核心 mock 端点（mock-login、meta 5 端点）无 404」；步骤 4：「CRITICAL / HIGH 必修完才能开下一批；MEDIUM / LOW 登记到 TODOS.md 延后」
    - pcs-frontend/e2e/real_backend_route_sweep.spec.ts:63-69（新增）----「WARNING **只断「路由可达」**（渲染了 + 没被弹回 /login）---- WARNING 「控制台无 error / 无 4xx-5xx」**不作为断言** => 因为仓里有一批 **前端调用了不存在端点**的页面（`/pipe/line-list` ,  `/pms` ,  `/bedd`）... => 改成**打印出来**（进 QA 报告）=> 等那些端点补齐后，**再把断言加回来**。」，其后仅剩 `expect(results.every((r) => r.root)).toBe(true)` 与「没被弹回 /login」两条断言
    - TODOS.md（新增）TODO-159：「真后端通道（`--project=real-backend`）逐条走完 **44 条路由** => 三处请求 **404**」,  TODO-160：「`/common/properties` ,  `/common/stress` ,  `/common/toxicity` 三个页面**首屏**就发一个**空查询** => 后端 **422**」----两者均标注「归属：P10-C」延后，未按闸门做严重度分类
    - pcs-frontend/e2e/real_backend_route_sweep.spec.ts:64-69 -- `// WARNING **只断「路由可达」**` ... `// => => 改成**打印出来**（进 QA 报告）=>` / `// => => 等那些端点补齐后，**再把断言加回来**。`
    - pcs-frontend/e2e/real_backend_route_sweep.spec.ts:70-73 -- `  expect(results.every((r) => r.root), '有路由没渲染出来').toBe(true);` => 控制台 error / 4xx 只被收集、未被断言
    - pcs-frontend/e2e/real_backend_route_sweep.spec.ts:38-43 -- `  const consoleErrors: string[] = [];` / `  const badResponses: string[] = [];` => 收集了却不用
    - TODOS.md（diff）-- `## TODO-159: 前端调用了**不存在的端点**的 3 个页面（真后端下打不开数据） 🟠` => 「再断言」目前只登记在 TODO，无钉子
    - pcs-frontend/e2e/real_backend_route_sweep.spec.ts:70-74 ---- `expect(results.every((r) => r.root), '有路由没渲染出来').toBe(true); expect(results.filter((r) => r.redirected), ...).toEqual([]);`
    - pcs-frontend/e2e/real_backend_route_sweep.spec.ts:64-69 ---- 注释自陈「『控制台无 error / 无 4xx-5xx』**不作为断言**」
    - TODOS.md TODO-159 / TODO-160 ---- 三个页面调不存在的端点、三个 common 页首屏 422（扫描本该发现的正是这两类）
  - Suggested fix / response: 把 `#root` 换成**页面专有特征**（种子里某个 id/标题出现在页面上），并把收集到的 console error 与 4xx/5xx **变成断言**：除显式白名单（TODO-159 的 3 个页面 + TODO-160 的 3 个 common 页）外，白名单之外必须为空；白名单条目要逐条写清是哪一页、哪个端点。
  - Validation: confirmed
  - Reviewers: adversarial, project-standards, learnings, testing
  - Route: `manual -> downstream-resolver`

- **#8** -- `pcs-backend/tests/e2e_flows/conftest.py:93` -- E2E 车道与种子脚本都没有目标库白名单 => 可在开发库上建 schema 并灌种子
  - Why it matters: `_lane_url()` 只断言 URL 以 `postgres` 开头 => 车道**自己不设防**：『隔离 schema + alembic upgrade head + 灌种子』这三步只由薄封装脚本保证。任何人 export 了 `PCS_E2E_LANE=1`（CI 镜像、开发者 shell、某个 wrapper）且环境里有指向开发库 `pcs` 的 DATABASE_URL，车道就会在**开发库里**建 schema、跑迁移、灌种子（含 alice 的 users 行与授权行）=> 正是这条车道存在的理由（CLAUDE.md「默认车道绝不能打到开发库 pcs」）被绕过，而且症状是『跑得挺快、全绿』。
  - Evidence:
    - pcs-backend/tests/e2e_flows/conftest.py:95-100 -- `url = os.environ.get("DATABASE_URL", ""); if not url.startswith("postgres"): raise RuntimeError(...)` => 只查协议，不查库名
    - pcs-backend/scripts/pytest_e2e.sh:32-35 -- 正确做法只在薄封装里（`export PCS_E2E_LANE=1` + exec pytest_pg.sh，无条件覆写 DATABASE_URL 到 pcs_pgtest）=> 绕过脚本就没有这层保护
    - pcs-backend/tests/e2e_flows/conftest.py:164-187 -- 拿到 URL 就在那个库里 `CREATE SCHEMA` + 子进程 `alembic upgrade head`
    - pcs-backend/tests/e2e_flows/conftest.py:93-101 ---- `url = os.environ.get("DATABASE_URL", "")` / `if not url.startswith("postgres"): raise RuntimeError(...)`（**只查协议，不查库名**）
    - pcs-backend/tests/e2e_flows/conftest.py:168-191 ---- `CREATE SCHEMA` / `alembic upgrade head` / `DROP SCHEMA ... CASCADE` 全部作用在 `_lane_url()` 返回的那个库上
    - pcs-backend/scripts/pytest_pg.sh:64-67 ---- 库名只在脚本层被钉死（`PG_DB_NAME="${PG_DB_NAME:-pcs_pgtest}"`）=> 车道自身无此断言
    - pcs-backend/scripts/seed_e2e_flows.py:751 -- `    factory = get_async_session_factory()` (no database-name check before writing)
    - pcs-backend/scripts/seed_e2e_flows.py:748 -- `async def _main(reset: bool) -> None:` / docstring usage lines 3729-3730 -- `    uv run python scripts/seed_e2e_flows.py            # 幂等灌种子` (the documented invocation)
    - pcs-backend/scripts/seed_e2e_flows.py:342 / 361 / 390 -- `            status="ACTIVE",` (seeded accounts are ACTIVE)
    - pcs-backend/scripts/seed_e2e_flows.py:388-392 -- `AUTHORIZED_USERNAMES` / `USERNAME_TO_PROJECT_ROLE` incl. `"alice": "DESIGNER"` => the seed writes project authorization rows
    - pcs-backend/app/db/session.py:66 -- `            get_settings().database_url,` => the factory resolves the env var, falling back to `.env` (the dev database `pcs` per repo CLAUDE.md)
    - docker-compose.yml:765 -- `       DATABASE_URL: postgresql+psycopg://${POSTGRES_USER:-pcs}:${POSTGRES_PASSWORD:-pcs_dev}@postgres-pgtest:5432/pcs_pgtest` => the URL is pinned only for the compose service, not inside the script
    - pcs-backend/tests/e2e_flows/conftest.py:93-101 -- `def _lane_url() -> str:` ... `    if not url.startswith("postgres"):` / `        raise RuntimeError(` => only the URL scheme is checked; the database name is never inspected
    - pcs-backend/tests/e2e_flows/conftest.py:76 -- `    if os.environ.get(LANE_ENV_VAR) == "1":` => the whole 'don't touch a non-test DB' property is delegated to one env var (`PCS_E2E_LANE`)
    - pcs-backend/tests/e2e_flows/conftest.py:4719-4738 (diff) -- the fixture runs `CREATE SCHEMA` and `subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], ... env={**os.environ, "DATABASE_URL": _scoped_url(url, schema)})` => DDL is executed against whatever database the URL names
    - pcs-backend/tests/e2e_flows/test_lane_smoke.py:7399-7421 -- `def test_e2e_items_are_skipped_without_the_lane_flag():` => the only guard test asserts a skip marker is added; nothing asserts the lane refuses a non-test database
    - pcs-backend/scripts/seed_e2e_flows.py:763 -- `    parser = argparse.ArgumentParser(description="灌流程级 E2E 种子数据（幂等）")` => 参数里没有任何数据库目标约束
    - grep 结果：`DATABASE_URL|pcs_pgtest|pcs_test|current_database` 在 scripts/seed_e2e_flows.py 上 0 命中 => 脚本不检查自己连的是哪个库
    - pcs-backend/scripts/seed_e2e_flows.py:257-269 -- `_get_or_create` 的 savepoint + 重读赢家写法（幂等/并发正确的部分）
    - pcs-backend/scripts/seed_e2e_flows.py:293 -- `    project_ids = [FLOW_PROJECT_ID]` => `--reset` 只删自己那个项目，但**新写**的行照写不误
  - Suggested fix / response: 在车道与种子脚本里都加**目标库名白名单**：进入车道时读 `current_database()`，不在允许清单（默认 `pcs_pgtest`，可用 `PCS_E2E_ALLOWED_DB` 覆盖）里就**非零退出并打印实际库名**；`scripts/seed_e2e_flows.py` 在任何写入前做同一条检查。白名单必须落在**车道自己**里，不能只靠薄封装脚本。
  - Validation: confirmed / protected subject: data-loss / incidence NOT measured (code permits it, nobody showed it happens)
  - Reviewers: adversarial, testing, security, security, reliability
  - Route: `gated_auto -> downstream-resolver`

- **#9** -- `pcs-frontend/src/pages/routeWrappers.tsx:87` -- useFetch 静默吞错且绕过 axios 401 拦截器 => token 过期后永久停在加载中
  - Why it matters: 报错链路**不可靠**：非 2xx 被折叠成 `null`（`r.ok ? r.json() : null`），网络异常被 `.catch(() => {})` 吞掉 => `data` 永远停在 `initial` => `StreamDetailRoute` 永久渲染「加载中...」（routeWrappers.tsx:160），列表页则渲染成「空列表」---- 两者都与「加载中」/「真的没有数据」长得一样，用户没有任何提示。本批把假 token 换成真 token 后引入了一个**新的**静默失败窗口：access token 30 分钟过期（app/core/config.py:46 `access_token_expire_minutes: int = 30`）=> `useFetch` 的请求全部 401 => 而 `useFetch` 用的是裸 `fetch`，**绕过了 axios 的 401 拦截器**（client.ts:54-60：clearSession + 跳 /login）=> 用户既不会被踢回登录页、也看不到任何报错，只能手动刷新（刷新后 token 仍过期 => 还是坏的）。裸 `fetch` 还没有 timeout => 后端挂住时页面同样永远「加载中...」。
  - Evidence:
    - pcs-frontend/src/pages/routeWrappers.tsx:87-92 -- `    void fetch(path, { headers: { Authorization: authorization } })` / `      .then((r) => (r.ok ? r.json() : null))` / `      .then((j: T | null) => {` / `        if (!cancelled && j !== null) setData(j);` / `      })` / `      .catch(() => {/* offline / unhandled: keep empty fixtures */});` => 非 2xx 与网络异常都变成「什么都不发生」
    - pcs-frontend/src/pages/routeWrappers.tsx:159-160 -- `  const stream = useFetch<Stream | null>(`/api/v1/streams/${streamId}`, null);` / `  if (!stream) return <Typography.Text>加载中...</Typography.Text>;` => 失败态与加载态同形
    - pcs-frontend/src/api/client.ts:54-60 -- `    if (err.response?.status === 401) {` ... `        useAuth.getState().clearSession();` ... `          window.location.href = '/login';` => 只有走 axios 的请求才有「401 => 回登录页」，`useFetch` 完全绕过
    - pcs-backend/app/core/config.py:46 -- `    access_token_expire_minutes: int = 30` => 过期是必然事件，不是边缘情况
    - pcs-frontend/src/pages/routeWrappers.tsx:85-86 -- `    const token = useAuth.getState().accessToken;` / `    const authorization = token ? `Bearer ${token}` : DEV_BEARER;` => 过期 token 仍被当作有效 token 发出
    - pcs-frontend/src/pages/routeWrappers.tsx:85-92 -- `const token = useAuth.getState().accessToken; const authorization = token ? `Bearer ${token}` : DEV_BEARER; void fetch(path, { headers: { Authorization: authorization } }).then((r) => (r.ok ? r.json() : null)) ... .catch(() => {/* offline / unhandled: keep empty fixtures */})`
    - pcs-frontend/src/api/client.ts:6-14 -- canonical 通道：`api = axios.create({ baseURL: '/api/v1' })` + 请求拦截器 `config.headers.Authorization = `Bearer ${token}``
    - pcs-frontend/src/api/client.ts:51-66 -- 响应拦截器：会话型 401 => `useAuth.getState().clearSession()` + `window.location.href = '/login'`（裸 fetch 通道完全没有这一段）
    - pcs-frontend/src/pages/routeWrappers.tsx:107,159,169,181,185,189,212,331,335 -- 9 个路由的取数都走这条裸 fetch 通道
    - MERGE-LEAF VERIFIED pcs-frontend/src/pages/routeWrappers.tsx:85-92 - the token comes from the session, the call is a bare `fetch` (no axios interceptor, so no 401 handling and no timeout), a non-2xx response becomes `null` and `.catch(() => {})` swallows network errors => the component stays in its loading state forever with no error surfaced
  - Suggested fix / response: 给 `useFetch` 一个显式的失败态而不是静默：`fetch` 用 `AbortController` + 超时（如 15s，cleanup 里 `clearTimeout` + `abort`），`!r.ok` 与 `catch` 都写入 `error` state；`StreamDetailRoute` 在 `error` 时渲染错误+重试，而不是「加载中...」。401 建议直接复用 `src/api/client.ts` 的 axios 实例（或调用同一套 clearSession + 跳 /login），让 token 过期与用户停用都回到登录页而不是卡死。注意：`.catch` 那行本身是本批未改的上下文行，但本批重写了这个 fetch 调用（同一条表达式链），因此失败路径落在本次改动的作用域内。
  - Validation: confirmed / protected subject: authorization-authentication
  - Reviewers: reliability, maintainability
  - Route: `gated_auto -> downstream-resolver`

### P2 -- Moderate (16)

| # | File | Issue | Reviewer | Confidence |
|---|---|---|---|---|
| 10 | `pcs-backend/app/core/errors.py:45` | RBAC 拒绝的审计写入在车道里被静默跳过 | adversarial | 100 |
| 11 | `.wolf/STATUS.md:88` | 本批 4 条可复用解法没有回写 docs/solutions/，且 STATUS 自称已回写 | project-standards | 75 |
| 12 | `pcs-backend/app/api/v1/report.py:494` | 审计哈希端点返回值随行龄不同（老行与复用行恒返空串） | api-contract | 75 |
| 13 | `pcs-backend/app/api/v1/sim_imports_query.py:325` | preview-streams 无 response_model，契约未记录本批统一的形状；注释与事实相反 | api-contract, maintainability | 75 |
| 14 | `pcs-backend/app/workers/report_tasks.py:118` | data_version 被塞进文件摘要 => 审计端点两字段语义塌陷 | api-contract | 75 |
| 15 | `pcs-backend/scripts/pytest_pg.sh:56` | flock 互斥只覆盖两条 pytest 车道，compose 迁移/种子裸奔 | reliability | 75 |
| 16 | `pcs-backend/scripts/pytest_pg.sh:83` | 闸门③只要求『至少 1 passed』=> 29/30 场景被 skip 也是绿的 | adversarial | 75 |
| 17 | `pcs-backend/scripts/seed_e2e_flows.py:516` | 种子管级违反 PipeClassResponse 契约 => 按 id 查必 500 | correctness, learnings | 75 |
| 18 | `pcs-backend/tests/e2e_flows/conftest.py:272` | E2E 车道不跑 lifespan，注释称已补启动 seed 实测 0 处调用 | reliability | 75 |
| 19 | `pcs-backend/tests/e2e_flows/conftest.py:289` | 隔离只覆盖 get_db：全局 session factory 仍指 public schema | adversarial | 75 |
| 20 | `pcs-backend/tests/e2e_flows/test_e2e_schema_parity.py:57` | schema 一致性检查塞进隔离车道且直连开发库 pcs / pcs_test | maintainability, testing | 75 |
| 21 | `pcs-backend/tests/e2e_flows/test_e2e_schema_parity.py:73` | 两库 schema 一致闸只比彼此、不与代码 head 比 => 两库都落后也绿 | correctness | 75 |
| 22 | `pcs-backend/tests/e2e_flows/test_lane_smoke.py:240` | 『不写 public』守卫只覆盖 4 张表、只取一次基线 | adversarial, testing, security | 75 |
| 23 | `pcs-frontend/package.json:20` | 真后端 UI 车道依赖 4 个仓库外环境变量 => 无法从仓库复现 | testing | 75 |
| 24 | `pcs-frontend/src/pages/DashboardPage.tsx:40` | 仪表盘 404 修复条件不严：工作区无 project_id 时照旧 404 | correctness | 75 |
| 25 | `spec/P10 AI预留与测试部署开发规格说明书.md:666` | 本批偏离登记写进非权威 SPEC 文件，D20 与本批自述互相矛盾 | api-contract, project-standards | 75 |

- **#10** -- `pcs-backend/app/core/errors.py:45` -- RBAC 拒绝的审计写入在车道里被静默跳过
  - Why it matters: `_write_rbac_audit_row` 在 `PYTEST_CURRENT_TEST` 存在时**直接 return** => 真后端车道里，**每一次 403 都不写审计行** => 权限矩阵里所有 403 用例验的是『无副作用』的版本 => 生产上『越权 => 留痕』这条合规语义在车道里是空跑，任何把它改坏/改漏的缺陷（写失败、action 写错、user_id 取错）都不会被车道发现。早退的理由是『防测试写真实 DB』，而车道的库已经是隔离 schema => 这条早退在车道里没有理由。
  - Evidence:
    - pcs-backend/app/core/errors.py:45-46 -- `if os.environ.get("PYTEST_CURRENT_TEST"): return`
    - pcs-backend/app/core/errors.py:105 -- `await _write_rbac_audit_row(_best_effort_user_id(request), detail)`（403 路径的唯一留痕点）
    - pcs-backend/tests/e2e_flows/test_e2e_permission_matrix.py:31-46 -- 矩阵里 5 条 403 用例（submit-approval/approval-step/audit-logs）=> 这些 403 在车道里都不留痕
  - Suggested fix / response: 把 `_write_rbac_audit_row` 的早退条件从 `PYTEST_CURRENT_TEST` 换成**是否本车道隔离库**（例如 `PCS_E2E_LANE=1` 时不早退），并在权限矩阵里补一条断言：403 之后 `ai_audit_log`（或审计表）确实多了一行、action/user_id 正确。
  - Validation: not validated (P2/P3 advisory; outside the validator batch)
  - Reviewers: adversarial
  - Route: `manual -> human`

- **#11** -- `.wolf/STATUS.md:88` -- 本批 4 条可复用解法没有回写 docs/solutions/，且 STATUS 自称已回写
  - Why it matters: CLAUDE.md 的知识库条明确要求「新增解法后回写一份，别只留在提交信息里」----解法要落到 `docs/solutions/`（按 problem_type 分目录、带 YAML frontmatter）。本批修了 9 个真缺陷，其中至少 4 条是**可复用的新解法域**：车道驱动必须与生产一致（asyncpg vs psycopg 的类型严格性）、契约与 DB 可空性对齐（响应枚举必填 -> DB 可空 => 500）、前端两条取数通道（axios 拦截器 vs 裸 fetch）、守门测试必须与被守卫机制隔离（车道锁）。STATUS.md 自己宣称这三条教训「已进 cerebrum / docs/solutions」，但本批的改动文件清单里没有任何 `docs/solutions/**` 文件 => 那句断言不成立。后果：这些坑下一次仍会被踩（仓内既有先例：bug-2162 的修法写成了 `docs/solutions/testing-issues/guard-patched-definition-site-consumer-imported-by-value.md`，bug-2170 与既有 `docs/solutions/testing-issues/guard-test-fooled-by-lying-comment.md` 同形）。
  - Evidence:
    - CLAUDE.md《知识库》：「`docs/solutions/` -- 已记录的问题解法（缺陷、最佳实践、工作流模式），按 `problem_type` 分目录，带 YAML frontmatter（`module` / `tags` / `problem_type` / `severity`）。在已记录领域做实现或排障时相关；**新增解法后回写一份，别只留在提交信息里**。」
    - .wolf/STATUS.md:86-92（新增）----「## 教训（**已进 cerebrum / docs/solutions**，此处只留最新三条）」「- **车道的驱动必须与生产一致** => 否则「int 塞进 VARCHAR」这类缺陷**隐形**（bug-2166）。」「- **前端有两条取数通道**（axios 拦截器 vs 裸 `fetch`）=> 后者**默认没有 token** => 真后端通道才抓到（bug-2169）。」「- **守卫测试必须与被守卫的机制隔离** => 车道锁 => 守门测试抢同一把锁 => 测的不是它声称的东西（bug-2170）。」
    - 本批改动文件清单（files.txt）不含任何 `docs/solutions/**` 条目；对应内容只出现在 .wolf/buglog.json（新增 bug-2163~2170）与代码注释里
    - pcs-backend/tests/e2e_flows/conftest.py:113-124（新增 `_async_url`）----「WARNING **为什么必须换**（2026-11-16 ,  T7 实测）：车道的 `DATABASE_URL` 是 `postgresql+psycopg://` => async 部分若也用 psycopg => => **驱动与生产不一致** => => **asyncpg 的类型严格性看不到**」（同款可复用解法）
    - MERGE-LEAF VERIFIED .wolf/STATUS.md:86 - the section header claims the lessons are already in 'cerebrum / docs/solutions' and lists bug-2166 / bug-2169 / bug-2170, but `git diff d73d1ac..f3b35e5 -- docs/solutions` is empty and no file under docs/solutions/ mentions any of those three bug numbers
    - MERGE-LEAF VERIFIED .wolf/STATUS.md:50-51 - points at .gstack/qa-reports/qa-report-pcs-frontend-2026-11-16-p10b.md and says '本轮还没跑', while the report on disk is qa-report-pcs-frontend-2026-11-17-p10b.md (different date) and it does exist
  - Suggested fix / response: 按 problem_type 各回写一份：① `docs/solutions/testing-issues/test-lane-driver-must-match-production-driver.md`（asyncpg vs psycopg 的类型严格性差异 + 「单测照绿、真库炸」）；② `docs/solutions/database-issues/response-enum-nullable-must-match-db-nullability.md`（bug-2167：DB 可空列 => 响应枚举必填 => ResponseValidationError 500）；③ `docs/solutions/frontend-issues/raw-fetch-bypasses-axios-token-interceptor.md`（bug-2169）；④ `docs/solutions/testing-issues/guard-test-must-use-its-own-lane-lock.md`（bug-2170）。每份带 module / tags / problem_type / severity frontmatter，并让 STATUS.md 的「已进 docs/solutions」变成事实。
  - Validation: not validated (P2/P3 advisory; outside the validator batch)
  - Reviewers: project-standards
  - Route: `manual -> human`

- **#12** -- `pcs-backend/app/api/v1/report.py:494` -- 审计哈希端点返回值随行龄不同（老行与复用行恒返空串）
  - Why it matters: _expected_digest 只读 data_version => 本批之前登记的 report_files 行 data_version 恒 NULL => record_hash_digest 恒 ""；本批之后的新行是 64 位 hex => 同一个端点、同一个字段，返回值形态取决于「这行是什么时候登记的」，审计方无法区分「老数据没有摘要」与「摘要缺失/生成失败」。而且 _finalize 的「同内容复用」分支（dup）直接 return，根本不给被复用的行写 data_version => 走复用路径拿到的文件仍然返回空串。E2E-009 里这条断言至今仍是 xfail（注释写「根因未完全隔离」），等于本批的修复没有被任何真断言钉住。
  - Evidence:
    - pcs-backend/app/api/v1/report.py:494 -- return row.data_version or ""
    - pcs-backend/app/workers/report_tasks.py:107-111 -- if dup is not None: await db.delete(row); await db.flush(); return str(dup.report_file_id) => 被复用的行永远没写过 data_version
    - pcs-backend/tests/e2e_flows/test_e2e_report.py:6784-6788 -- if not digest.json().get("record_hash_digest"): pytest.xfail("审计哈希端点在生成的报表上恒返回空串（bug-2165...）")
  - Suggested fix / response: 让摘要有单一真源：_expected_digest 改为 `return row.data_version or (row.content_hash if not row.content_hash.startswith(PENDING_HASH_PREFIX) else "")`（content_hash 已是文件 sha256），或在 _finalize 的 dup 分支把 dup 的摘要一并补齐；同时把 E2E-009 的 xfail 分支改成硬断言（record_hash_digest 为 64 位 hex），并补一条「同内容复用后仍非空」的用例。
  - Validation: confirmed / protected subject: public-contract
  - Reviewers: api-contract
  - Route: `gated_auto -> downstream-resolver`

- **#13** -- `pcs-backend/app/api/v1/sim_imports_query.py:325` -- preview-streams 无 response_model，契约未记录本批统一的形状；注释与事实相反
  - Why it matters: 本批把 list 归一成 {"streams": [...]}，但端点只有 `-> dict` 注解、没有 response_model => OpenAPI 里 200 仍是 {"type": "object"}（前端生成类型是 {[key: string]: unknown}）=> 消费者无法从契约得知必须读 .streams，只能靠试。另外新增的代码注释说「SIM/Excel 导入存 dict」，与事实相反 ---- 两个写入点（import_service.py:496 PRO/II、:612 EXCEL）存的都存成 list => 归一的影响面比注释写的大（EXCEL 导入以前同样是 500）。
  - Evidence:
    - pcs-backend/app/api/v1/sim_imports_query.py:325-330 -- @router.get("/{import_id}/preview-streams") ... ) -> dict:  （无 response_model => OpenAPI 200 = {"type": "object"}）
    - pcs-backend/app/api/v1/sim_imports_query.py:362-363 -- 「**PRO/II 导入**把 preview 存成 **list**（`preview_streams_json = [...]`），而 SIM/Excel 导入存 **dict**（`{"streams": [...]}`）」=> 与下面两个写入点相反
    - pcs-backend/app/services/import_service.py:496 -- preview_streams_json=preview_dict.get("preview_streams", []), （PRO/II => list）
    - pcs-backend/app/services/import_service.py:612 -- preview_streams_json=preview_dict.get("preview_streams", []), （EXCEL => 也是 list）
    - pcs-frontend/src/types/api.d.ts:32814-32822 -- preview-streams 的 200 content 类型是 `{[key: string]: unknown}` => 生成客户端拿不到键名
    - pcs-backend/app/api/v1/sim_imports_query.py:360-367 -- 注释「**PRO/II 导入**把 preview 存成 **list**... 而 **SIM/Excel 导入存 dict**（`{"streams": [...]}`）」+ `payload = imp.preview_streams_json` / `if isinstance(payload, list): return {"streams": payload}`
    - pcs-backend/app/services/import_service.py:496 -- `preview_streams_json=preview_dict.get("preview_streams", [])` => **list**
    - pcs-backend/app/services/import_service.py:612 -- `preview_streams_json=preview_dict.get("preview_streams", [])` => **list**（两个写入方形状相同）
    - pcs-backend/app/models/sim_import.py:95 -- `preview_streams_json: Mapped[dict] = mapped_column(JSONB, default=dict)` => 注解与实际写入的 list 不符
  - Suggested fix / response: 加 response_model 把形状写进契约（新增 schemas.SimImportPreviewStreamsResponse：streams: list[dict[str, Any]] = []），并把注释改成「PRO/II 与 EXCEL 两个写入点都存 list => 读侧统一归一成 {streams: [...]}」；加 response_model 后必须重跑 scripts/gate_08_openapi_contract.sh，让 openapi.json / 前端 snapshot / api.d.ts 一起滚动。
  - Validation: confirmed / protected subject: public-contract
  - Reviewers: api-contract, maintainability
  - Route: `gated_auto -> downstream-resolver`

- **#14** -- `pcs-backend/app/workers/report_tasks.py:118` -- data_version 被塞进文件摘要 => 审计端点两字段语义塌陷
  - Why it matters: report_tasks._finalize 把生成文件的 sha256 写进 report_files.data_version（该列原义是「登记时冻结的数据版本」）=> GET /report/{id}/hash 的 record_hash_digest 与 data_version 现在返回同一个值，也就是 content_hash（ReportFile 上根本没有「记录哈希」列）=> 审计方无法区分「源数据版本」与「文件内容摘要」，两个字段从此是同一个值的两个名字；而 data_version 这个名字一旦被摘要占用，将来想真填数据版本时旧语义已被占死。
  - Evidence:
    - pcs-backend/app/workers/report_tasks.py:118 -- row.data_version = digest
    - pcs-backend/app/api/v1/report.py:307-310 -- return ReportHashResponse(report_file_id=row.report_file_id, record_hash_digest=_expected_digest(row), data_version=row.data_version) => 两个字段同源
    - pcs-backend/app/api/v1/report.py:487-494 -- 「登记时冻结的数据版本（`data_version`），供审计端点查」=> 字段语义是「数据版本」，不是文件摘要
    - pcs-backend/app/models/report.py:155,166 -- content_hash: Mapped[str]（NOT NULL，文件哈希）vs data_version: Mapped[str | None] => 摘要本来已有专门的列
  - Suggested fix / response: 不要复用 data_version 装文件摘要：_expected_digest 改读 row.content_hash（PENDING 占位以 report_tasks.PENDING_HASH_PREFIX 开头则返回空串），删掉 report_tasks.py:118 的 row.data_version = digest，把 data_version 留给真正的数据版本；若审计确实需要「文件摘要 + 数据版本」两个值，则在 ReportHashResponse 上新增明确命名的字段（如 file_content_hash），而不是复用 data_version。
  - Validation: not validated (P2/P3 advisory; outside the validator batch)
  - Reviewers: api-contract
  - Route: `manual -> human`

- **#15** -- `pcs-backend/scripts/pytest_pg.sh:56` -- flock 互斥只覆盖两条 pytest 车道，compose 迁移/种子裸奔
  - Why it matters: 锁本身是对的（放在共享脚本里 => 两条车道都生效；`flock -n` 快速失败而不是排队；fd 9 被子进程继承 => 锁一直持有到 pytest 真正退出；进程退出即释放）。但覆盖面有缺口：**同一个 `pcs_pgtest` 库还有别的写者没进锁** ---- compose 的 `migrate` 服务（`alembic upgrade head`，docker-compose.yml:113，写 public schema）与 `seed` 服务（两个种子脚本，:153）都在这个库上跑 DDL/DML，却完全不受 flock 约束 => 开发者在车道运行时 `docker compose --profile test up` => 隔离 schema 里的 `CREATE SCHEMA`/`alembic upgrade head` 与 public schema 里的 DDL 并发 => 表现是 catalog 锁互相等待（脚本注释自己写的「偶发卡住」），排查成本极高。另有两处保真度问题：锁文件是固定的 `/tmp/pcs-pgtest-lane.lock`（被 tmp 清理删掉后新进程会拿到新 inode => 互斥静默失效；非本用户拥有时 `exec 9>` 直接报错而不是那句清晰的 FAIL），以及守卫测试用 `PCS_PGTEST_LANE_LOCK` 覆盖成 per-PID 临时文件 => **默认路径从未被测过**。
  - Evidence:
    - pcs-backend/scripts/pytest_pg.sh:56-61 -- `LOCK_FILE="${PCS_PGTEST_LANE_LOCK:-/tmp/pcs-pgtest-lane.lock}"` / `exec 9>"$LOCK_FILE"` / `if ! flock -n 9; then` / `  echo "FAIL: 另一条车道（PG 车道 / E2E 车道）正在跑 => 同一个库不能并发建 schema" >&2` / `  exit 1` / `fi` => 只约束走进这个脚本的进程
    - docker-compose.yml:113 -- `    command: ["uv", "run", "--frozen", "alembic", "upgrade", "head"]`（migrate 服务，对 `pcs_pgtest` public schema 做 DDL，无锁）
    - docker-compose.yml:140-145 -- seed 服务 `uv run --frozen python scripts/seed_e2e_data.py && uv run --frozen python scripts/seed_e2e_flows.py`（同一库，无锁）
    - pcs-backend/scripts/pytest_pg.sh:49-51 -- `WARNING **PG 车道与 E2E 车道共用同一个库**（`pcs_pgtest`）... => 并发跑 => DDL 互相等锁 => 表现是「**偶发卡住**」而不是报错` => 同样的症状对 compose 侧依然成立
    - pcs-backend/tests/scripts/test_pytest_pg_gate.py -- 守卫测试把 `PCS_PGTEST_LANE_LOCK` 覆盖成 per-PID 临时文件（bug-2170 的绕法）=> 默认的 `/tmp/pcs-pgtest-lane.lock` 路径没有被任何测试走到
  - Suggested fix / response: 把互斥从「脚本内的 flock」提升到「库级别的互斥」：① 让 compose 的 `migrate`/`seed` 服务也走同一个锁文件（在容器里 `flock` 同一个路径，或改成由 `scripts/pytest_pg.sh` 负责迁移）；② 锁文件移到不会被 tmp 清理的位置（如 `${TMPDIR:-/tmp}/pcs-pgtest-lane.lock` 之外的项目内路径 `.tmp/`），并在 `exec 9>` 失败时给出明确的 FAIL 而不是 shell 重定向错误；③ 守卫测试补一条「默认路径下的两条 lane 互斥」用例（用子进程实测），而不是只测覆盖后的临时路径。
  - Validation: not validated (P2/P3 advisory; outside the validator batch)
  - Reviewers: reliability
  - Route: `manual -> human`

- **#16** -- `pcs-backend/scripts/pytest_pg.sh:83` -- 闸门③只要求『至少 1 passed』=> 29/30 场景被 skip 也是绿的
  - Why it matters: 车道有 30 条 e2e 用例，闸门③只 grep 输出里的 `N passed` => 只要有一条真跑过就算过 => 若某次改动让绝大多数场景被静默跳过（某个 fixture 改成条件 skip、某个依赖没起就 skip），车道照样全绿 => 闸门只覆盖了『全 skip』这个端点，中间态（几乎全 skip）没有闸 => 与『收集到 0 个 => FAIL』的意图不一致。
  - Evidence:
    - pcs-backend/scripts/pytest_pg.sh:81-86 -- `out="$(uv run pytest -m "$PG_PYTEST_MARK" -q 2>&1)" || { echo "$out"; exit 1; }; ... if ! echo "$out" | grep -qE '[1-9][0-9]* passed'; then ... exit 1; fi`
    - pcs-backend/pyproject.toml:99 -- `e2e` marker 的用例共 30 条（各文件 `@pytest.mark.e2e` 计数之和）
    - pcs-backend/tests/e2e_flows/test_lane_smoke.py:90-94 -- 命令式 `pytest.xfail()` 的用例在闸门里既不算 passed 也不算失败（见另一条发现）
    - MERGE-LEAF VERIFIED pcs-backend/scripts/pytest_e2e.sh:32-35 - the E2E lane exports PG_PYTEST_MARK=e2e and PCS_E2E_LANE=1 and then `exec bash scripts/pytest_pg.sh`, so the E2E lane inherits exactly the same gate ③ at pytest_pg.sh:83 that only greps for '[1-9][0-9]* passed'
  - Suggested fix / response: 闸门③改成 fail-closed：解析 pytest 摘要，要求 `passed >= <场景数>` 且 `skipped == 0`（已知 xfail 走显式白名单并单独计数）；E2E 车道的期望场景数从 `pyproject.toml` 的 marker 统计里取，不写死。
  - Validation: confirmed
  - Reviewers: adversarial
  - Route: `gated_auto -> downstream-resolver`

- **#17** -- `pcs-backend/scripts/seed_e2e_flows.py:516` -- 种子管级违反 PipeClassResponse 契约 => 按 id 查必 500
  - Why it matters: 本批新建的种子脚本造的 `pipe_classes` 行有三处违反出参契约：① `source="E2E_SEED"` 不在 `PipeClassBase.source` 的 `Literal["COMPANY_STD","PROJECT"]` 里；② `dn_series_json={"DN150": 1.0}` 没有 min/max => 触发 `_check_dn` 的 ValueError；③ `sch_series_json={"DN150": 40.0}` 的值是 float，而契约是 `dict[str, str]`（pydantic v2 不把数字转字符串）。=> `GET /pipe-classes/E2E-SEED-CS` 必然 ResponseValidationError => 500。这行种子还会经 compose 的 `seed` 服务灌进 pcs_pgtest 的 public schema => 真后端通道的库里也躺着一颗雷。
  - Evidence:
    - pcs-backend/scripts/seed_e2e_flows.py:516-519 -- `dn_series_json={"DN150": 1.0},` / `sch_series_json={"DN150": 40.0},` / `flange_class="PN16",` / `source="E2E_SEED",`
    - pcs-backend/app/schemas/pipe_class.py:77-79 -- `source: Literal["COMPANY_STD", "PROJECT"] = Field(..., description="数据来源：公司标准 / 项目自定义")`
    - pcs-backend/app/schemas/pipe_class.py:62-63 -- `sch_series_json: dict[str, str] = Field(..., description="DN -> Sch 壁厚系列映射（管壁厚对应表，DN->Sch）")`
    - pcs-backend/app/schemas/pipe_class.py:91-93 -- `mn, mx = self.dn_series_json.get("min"), self.dn_series_json.get("max")` / `if mn is None or mx is None or not (0 < mn <= mx): raise ValueError("dn_series_json 需 {min,max} 且 0<min<=max（单口径 min==max 合法）")`
    - pcs-backend/app/api/v1/pipe_classes.py:168-169 -- `@router.get("/pipe-classes/{class_id}", response_model=PipeClassResponse)`
    - pcs-backend/scripts/seed_e2e_flows.py:516-519 -- `            dn_series_json={"DN150": 1.0},` / `            sch_series_json={"DN150": 40.0},` / `            source="E2E_SEED",`
    - pcs-backend/app/schemas/pipe_class.py:77-78 -- `    source: Literal["COMPANY_STD", "PROJECT"] = Field(` => `E2E_SEED` 不在词表内
    - pcs-backend/app/schemas/pipe_class.py:84-93 -- `    @model_validator(mode="after")` / `    def _check_dn(self)` / `        if mn is None or mx is None or not (0 < mn <= max):` => 缺 {min,max} => ValueError
    - pcs-backend/app/schemas/pipe_class.py:65-66 -- `    sch_series_json: dict[str, str] = Field(` => 值必须是字符串
    - pcs-backend/app/api/v1/pipe_classes.py:168 -- `@router.get("/pipe-classes/{class_id}", response_model=PipeClassResponse)` => 按 id 取即序列化该行
    - pcs-backend/app/services/pipe/pipe_chain_persist.py（diff）-- `dn_series_json={"min": 15.0, "max": 600.0},` / `sch_series_json={"min": "0.5", "max": "1.2"},` => 产品代码那一侧刻意守住了契约，种子这一侧没有
    - MERGE-LEAF VERIFIED pcs-backend/app/schemas/pipe_class.py:77 - `source: Literal["COMPANY_STD", "PROJECT"]` while the seeded row uses source="E2E_SEED"
    - MERGE-LEAF VERIFIED pcs-backend/app/schemas/pipe_class.py:85-95 - the _check_dn model_validator raises unless dn_series_json carries {min,max} with 0<min<=max, and line 62 types sch_series_json as dict[str, str]; the seeded row has dn_series_json={"DN150": 1.0} and sch_series_json={"DN150": 40.0} => reading that row through PipeClassResponse raises => 500
  - Suggested fix / response: 把种子那一行改成契约内的形状：`source="COMPANY_STD"`、`dn_series_json={"min": 150, "max": 150}`、`sch_series_json={"DN150": "40"}`（值用字符串）；并在 tests/scripts/test_seed_e2e_flows.py 里加一条断言：种子的 PipeClass 行必须能通过 `PipeClassResponse.model_validate(row)`（这样以后 schema 一改就红）。
  - Validation: confirmed / protected subject: public-contract
  - Reviewers: correctness, learnings
  - Route: `gated_auto -> downstream-resolver`

- **#18** -- `pcs-backend/tests/e2e_flows/conftest.py:272` -- E2E 车道不跑 lifespan，注释称已补启动 seed 实测 0 处调用
  - Why it matters: stand-in guard fidelity 破了：本批的规格是「真 app + 真库」「驱动必须与生产一致」，而生产 app 在 **lifespan** 里 seed 两样东西（`CoefficientService.seed_default_tables` 的 6 张 CATEGORY_3 默认系数表 + `seed_system_setting_defaults` 的 7 个系统参数，app/main.py:159-160）---- 车道刻意不跑 lifespan（httpx.ASGITransport 本来就不跑），而注释说「由 `e2e_seed` 显式补」；实测**两个种子脚本与 conftest 里都没有任何一处调用这两个 seed**（grep `coefficient|system_setting|Coefficient|SystemSetting|seed_default` 在 scripts/seed_e2e_flows.py、scripts/seed_e2e_data.py、tests/e2e_flows/conftest.py 上 0 命中）=> 隔离 schema 里没有系数表、也没有系统参数 => 任何碰到这两处默认值的场景看到的是「空的生产默认集」=> 车道可以在生产形状不同的上下文上绿过去。注释还主动掩盖了这个缺口（后来的人会以为已经补了）。
  - Evidence:
    - pcs-backend/tests/e2e_flows/conftest.py:271-272 -- `    WARNING **不走 lifespan** => `httpx.ASGITransport` 本来就不跑 lifespan =>` / `    「只有 lifespan 才会做的那两处 seed」由 `e2e_seed` 显式补（T2 起）。` => 注释里的承诺
    - pcs-backend/app/main.py:157-160 -- `    factory = get_async_session_factory()` / `    async with factory() as session:` / `        await CoefficientService.seed_default_tables(session)` / `        await seed_system_setting_defaults(session)` => 这两处 seed **只在 lifespan 里**
    - grep 结果：`coefficient|system_setting|Coefficient|SystemSetting|seed_default` 在 scripts/seed_e2e_flows.py、scripts/seed_e2e_data.py、tests/e2e_flows/conftest.py 上 **0 命中** => 「由 `e2e_seed` 显式补」不成立
    - pcs-backend/tests/e2e_flows/conftest.py:271 -- `WARNING **不走 lifespan**`（车道确实不跑生产启动流程 => 上下文与生产不一致）
  - Suggested fix / response: 二选一，别让注释与代码脱节：(a) 让车道跑 lifespan（`async with app.router.lifespan_context(app):` 或 `LifespanManager`），生产启动 seed 就自然落到隔离 schema；(b) 在 `seed_flows` 里显式调用 `CoefficientService.seed_default_tables(session)` 与 `seed_system_setting_defaults(session)`，并把 conftest:272 的注释改成事实描述。无论选哪个，补一条断言：隔离 schema 里 coefficient 表 6 行、system_settings 7 行。
  - Validation: confirmed
  - Reviewers: reliability
  - Route: `manual -> downstream-resolver`

- **#19** -- `pcs-backend/tests/e2e_flows/conftest.py:289` -- 隔离只覆盖 get_db：全局 session factory 仍指 public schema
  - Why it matters: 车道靠 `app.dependency_overrides[get_db]` 把请求路径导向隔离 schema，但 app 里**另有一条不经 get_db 的取库路径**：`app/db/session.py::get_async_session_factory()` 是**进程级单例**，绑定 `settings.database_url` => 在车道里那是 **pcs_pgtest 的 public schema**。`app/api/v1/ws.py:77`（WS 握手鉴权）与 `app/core/errors.py:51`（RBAC 拒绝审计行）都走它 => 这些路径在车道里读/写的是**另一个房间**，与生产（同一个库）行为不同 => 车道的『真 app + 真库 + 同款路径』这句话在这几条路径上不成立；而现有的『不写 public』守卫看不见它们（守卫只跑 POST /projects，且只数 4 张表）。
  - Evidence:
    - pcs-backend/tests/e2e_flows/conftest.py:285-289 -- `async def _get_db(): ...` + `app.dependency_overrides[get_db] = _get_db` => 只有 get_db 被改写
    - pcs-backend/app/db/session.py:76-105 -- `get_async_session_factory()` 是模块级单例，engine 来自 `get_settings().database_url`（车道里 = pcs_pgtest 的 public）
    - pcs-backend/app/api/v1/ws.py:77-79 -- `factory = get_async_session_factory(); async with factory() as session: actor = await current_actor(session, authorization)`
    - pcs-backend/app/core/errors.py:48-53 -- `factory = get_async_session_factory(); ... await AuditService(session).write(action="RBAC_DENDEN", ...)`
  - Suggested fix / response: 把隔离从「只覆盖 get_db」扩到进程级 session factory：车道启动时用 schema-scoped 的 `connect_args={"server_settings": {"search_path": ...}}` 覆写 `app/db/session.py::get_async_session_factory` 的 engine（或让 `ws.py:77` 与 `errors.py:48-53` 改走注入的 session），并加一条断言：这两条路径写入的行出现在隔离 schema、不在 public。
  - Validation: confirmed
  - Reviewers: adversarial
  - Route: `gated_auto -> downstream-resolver`

- **#20** -- `pcs-backend/tests/e2e_flows/test_e2e_schema_parity.py:57` -- schema 一致性检查塞进隔离车道且直连开发库 pcs / pcs_test
  - Why it matters: 这条用例断的是 **`pcs` 与 `pcs_test` 两个开发库的 `alembic_version` 是否相同**----它既不用车道的隔离 schema，也不用车道自己的库（它从 `.env` 派 URL 连开发库）。它被标成 `@pytest.mark.e2e` => **只在 E2E 车道跑** => 而 E2E 车道是「批末跑一次」的 => 这条「两库版本一致」的发布前检查实际上**几乎不会执行**，可它偏偏占了 E2E 车道的一个名额；同时它让这条车道**不再 hermetic**（开发库不可达/未迁移 => 车道红，且红的理由与车道本身无关）。职责错位：这是发布前检查清单里的条目，不是端到端场景。
  - Evidence:
    - pcs-backend/tests/e2e_flows/test_e2e_schema_parity.py:57-76 -- `@pytest.mark.e2e async def test_e2e_018_pcs_and_pcs_test_schema_versions_match()`，URL 来自 `dotenv_values(BACKEND_ROOT / ".env")` => 连的是开发库 `pcs`/`pcs_test`
    - pcs-backend/tests/e2e_flows/conftest.py:1-19 -- 车道的定义是「**隔离 schema** ,  真 PG」，`e2e_schema` fixture 的隔离 schema 与这条用例无关
    - pcs-backend/tests/e2e_flows/test_e2e_schema_parity.py:1-16 -- 文件自己的 docstring 承认这是「两库 schema 版本一致」的发布前性质检查
    - pcs-backend/tests/e2e_flows/test_lane_smoke.py:103-158 -- 同车道里的隔离守卫用例确实用的是隔离 schema => 两条用例的主题并不属于同一层
    - pcs-backend/tests/e2e_flows/test_e2e_schema_parity.py:65-71 ---- `dev_url = dotenv_values(BACKEND_ROOT / ".env").get("DATABASE_URL")` ... `test_url = re.sub(r"/pcs(\?|$)", r"/pcs_test\1", dev_url)` ... `pcs_rev = _revision_of(dev_url)`
    - pcs-backend/tests/e2e_flows/conftest.py:93-101 ---- 车道其余部分只用 `_lane_url()`（= 车道导出的 pcs_pgtest），只有这条用例绕开它去连开发库
    - pcs-backend/CLAUDE.md ---- 「WARNING **验多个库 => 一库一个进程**... `pcs_test` 实际还停在旧 revision」=> 两库 revision 不齐是本仓已发生过的常态
  - Suggested fix / response: 把它从 `tests/e2e_flows/` 挪到 `tests/scripts/`（或发布前检查脚本 `scripts/gate_alembic_check.py` 附近），用**不带 e2e marker** 的方式在默认车道/发布检查里跑；E2E 车道只留「隔离 schema 内部」的用例 => 车道与发布检查各归其位，且这条检查真的会跑。
  - Validation: confirmed
  - Reviewers: maintainability, testing
  - Route: `manual -> downstream-resolver`

- **#21** -- `pcs-backend/tests/e2e_flows/test_e2e_schema_parity.py:73` -- 两库 schema 一致闸只比彼此、不与代码 head 比 => 两库都落后也绿
  - Why it matters: E2E-018 是本批唯一的「两库 schema 一致」闸（CLAUDE.md 发布前检查第 1 条），但它只断言 `pcs_rev == pcs_test_rev` ---- **从不与代码 head 比**。若 pcs 与 pcs_test 一起停在同一个旧 revision（CLAUDE.md 明确记过「pcs_test 长期停在 p7_s4_001 / p9_006」这类事故），该断言照样通过 => 假绿。而且它读的是**开发库**（`.env` 的 DATABASE_URL => pcs/pcs_test），把 E2E 车道的红绿绑在开发机的本地 DB 状态上：pcs_test 没对齐就必红（docstring 自己写了「不一致就登记（本批不修）=> 断言直接红」），pcs_test 与 pcs 都落后就假绿。
  - Evidence:
    - pcs-backend/tests/e2e_flows/test_e2e_schema_parity.py:70-76 -- `pcs_rev = _revision_of(dev_url)` / `pcs_test_rev = _revision_of(test_url)` / `assert pcs_rev == pcs_test_rev, ("两库 schema 版本不一致：pcs={pcs_rev} ,  pcs_test={pcs_test_rev}" "=> 登记偏离（本批不修）")`
    - pcs-backend/tests/e2e_flows/test_e2e_schema_parity.py:30-38 -- `print(conn.execute(text("SELECT version_num FROM alembic_version")).scalar_one())`（只读各库当前 revision，没有 head 的概念）
    - pcs-backend/tests/e2e_flows/test_e2e_schema_parity.py:65-68 -- `dev_url = dotenv_values(BACKEND_ROOT / ".env").get("DATABASE_URL")` / `test_url = re.sub(r"/pcs(\?|$)", r"/pcs_test\1", dev_url)`（断言对象是开发库，不是车道自己的隔离 schema）
  - Suggested fix / response: 再加一条与代码 head 的比较：子进程跑 `alembic heads` 取 head revision，断言 `pcs_rev == head and pcs_test_rev == head`（两条都要，不一致就分别报出是哪一库落后）；并把「pcs/pcs_test 落后」从「断言直接红」改成显式的 known-deviation 清单（现在这样会让 E2E 车道在干净机器上永远红）。
  - Validation: confirmed
  - Reviewers: correctness
  - Route: `gated_auto -> downstream-resolver`

- **#22** -- `pcs-backend/tests/e2e_flows/test_lane_smoke.py:240` -- 『不写 public』守卫只覆盖 4 张表、只取一次基线
  - Why it matters: 守卫的 docstring 宣称『E2E 的行**不能**出现在 public schema』，但实现只在**种子跑完之后**取一次 before 快照、只数 users/projects/streams/user_projects 四张表、只跑通 POST /projects 一条写路径 => ① 种子阶段若写进 public，快照已经含它 => before==after => **看不见**；② 泄漏到别的表（audit_logs / pipe_classes / piping_results / config_assets...）看不见；③ 走别的入口（WS 握手、错误处理里的全局 factory、ARQ 任务）看不见 => 车道的『隔离』覆盖面远小于它宣称的范围，而这是唯一一道防污染的闸。
  - Evidence:
    - pcs-backend/tests/e2e_flows/test_lane_smoke.py:132 -- `before = _public_snapshot(public_engine)`（在 `e2e_seed` 之后 => 种子阶段的泄漏已被吸收进基线）
    - pcs-backend/tests/e2e_flows/test_lane_smoke.py:235-245 -- `_public_snapshot` 只数 `for table in ("users", "projects", "streams", "user_projects")`
    - pcs-backend/tests/e2e_flows/test_lane_smoke.py:134-149 -- 被验证的写路径只有 `POST /api/v1/projects` 一条
    - pcs-backend/tests/e2e_flows/test_lane_smoke.py:105-114 -- docstring 自称『**「隔离」这句话必须被验** ---- E2E 的行**不能**出现在 public schema』=> 断言范围与宣称范围不一致
    - pcs-backend/tests/e2e_flows/test_lane_smoke.py:235-244 ---- `for table in ("users", "projects", "streams", "user_projects"): out[table] = int(conn.execute(text(f"SELECT count(*) FROM public.{table}")).scalar_one())`
    - pcs-backend/tests/e2e_flows/conftest.py:283-294 ---- `app = create_app()`，`app.dependency_overrides[get_db] = _get_db` => **app 自己的 engine 仍指向 public**（只有被覆盖的依赖注入层走隔离 schema）
    - pcs-backend/scripts/seed_e2e_flows.py:699-730 ---- 种子写 users/projects/user_projects/streams/signature_matrices/deliverables/piping_results/report_definitions/equipment ...（远多于四张表）
    - pcs-backend/tests/e2e_flows/test_lane_smoke.py:240 -- `        for table in ("users", "projects", "streams", "user_projects"):` => only 4 tables are snapshotted
    - pcs-backend/tests/e2e_flows/test_lane_smoke.py:245-247 -- `            out[table] = int(conn.execute(text(f"SELECT count(*) FROM public.{table}")).scalar_one())` => count(*) only, no `max(id)` (the plan required both)
    - pcs-backend/scripts/pytest_pg.sh:66 -- `  export DATABASE_URL="postgresql+psycopg://${PG_USER}:${PG_PASS}@localhost:${PG_PORT}/${PG_DB_NAME}"` => during the lane the app's global engine resolves to `pcs_pgtest` PUBLIC (no search_path), while only the `get_db` override is schema-scoped
    - pcs-backend/app/services/pipe/pipe_chain_persist.py:260 -- `    await _ensure_placeholder_pipe_class(db, PLACEHOLDER_MATERIAL_CLASS)` => a `pipe_classes` row is inserted on a request path, and `pipe_classes` is not in the guard's table list
  - Suggested fix / response: 把 public schema 基线挪到**种子 fixture 之前**取（调整 fixture 顺序或改成 autouse 的 session 级快照），并按种子实际写的表逐张枚举（users / projects / user_projects / streams / signature_matrices / deliverables / piping_results / report_definitions / equipment / pipe_classes / audit_logs ...），每张同时断 `count(*)` 与 `max(id)`；写路径也要从 1 条扩到种子 + 请求两条。
  - Validation: confirmed
  - Reviewers: adversarial, testing, security
  - Route: `gated_auto -> downstream-resolver`

- **#23** -- `pcs-frontend/package.json:20` -- 真后端 UI 车道依赖 4 个仓库外环境变量 => 无法从仓库复现
  - Why it matters: 本批第二个主交付物（真后端通道的 5 条 UI 流）依赖四个**仓库里没有任何地方写出**的环境变量：后端的 `DATABASE_URL` 必须指向 pcs_pgtest（:5433）+ `PCS_ENABLE_MOCK_LOGIN=true`，前端的 `VITE_PROJECT_ID` 必须是 flows 项目 id + `VITE_API_PROXY_TARGET` 必须指向那个后端。`npm run e2e:real` 只设了后两个里的一个（`VITE_API_PROXY_TARGET`，默认还是 :8000 的**开发后端**）；`playwright.config.ts` 的真后端 webServer 只设了 `VITE_ENABLE_MOCK=false`。而 `src/constants/env.ts:13` 的 `PROJECT_ID` 默认值是占位 id `00000000-0000-0000-0000-000000000001` => 不显式注入时物流/交付物/签署矩阵三页查的是**另一个项目** => 空表。完整复现步骤只写在 `.gstack/qa-reports/qa-report-pcs-frontend-2026-11-17-p10b.md`，而 `.gstack/` 是 gitignored（CLAUDE.md 自己承认「报告无法随仓库分发给同事或后续会话」）=> 换个机器/换个会话就再也跑不起来这条验收。更糟的是「路由扫描」与「越权用户看不到别人的项目」这两条在项目 id 错掉时**照样绿**（前者只断言 `#root` 存在，后者比较两个响应的状态码 => 两边都 404/403 就相等）=> 假绿。
  - Evidence:
    - pcs-frontend/package.json:20 ---- `"e2e:real": "VITE_ENABLE_MOCK=false VITE_API_PROXY_TARGET=${VITE_API_PROXY_TARGET:-http://localhost:8000} playwright test --project=real-backend"`（无 VITE_PROJECT_ID）
    - pcs-frontend/playwright.config.ts 真后端 webServer ---- `command: `VITE_ENABLE_MOCK=false npm run dev -- --port ${REAL_PORT}``（无 VITE_PROJECT_ID）
    - pcs-frontend/src/constants/env.ts:13 ---- `import.meta.env.VITE_PROJECT_ID ?? '00000000-0000-0000-0000-000000000001'`（占位 id => 页面查错项目）
    - .gstack/qa-reports/qa-report-pcs-frontend-2026-11-17-p10b.md「8. 复现方式」---- 唯一写出这四个变量与 flows 项目 id 的地方，而该目录被 gitignore
    - MERGE-LEAF VERIFIED pcs-frontend/src/constants/env.ts:12-13 - `import.meta.env.VITE_PROJECT_ID ?? '00000000-0000-0000-0000-000000000001'` => without an injected VITE_PROJECT_ID the pages query the placeholder project
    - MERGE-LEAF VERIFIED pcs-frontend/playwright.config.ts real-backend webServer - sets only VITE_ENABLE_MOCK=false (no VITE_PROJECT_ID); package.json:20 sets VITE_ENABLE_MOCK=false and VITE_API_PROXY_TARGET (default http://localhost:8000). Neither spec file reads any env var: the flow spec hardcodes FLOW_PROJECT_ID = '2488b011-14fc-584b-966e-1e2dfaeb9eb7', so the page under test and the seeded project can diverge
  - Suggested fix / response: 把复现条件写进仓库而不是 gitignored 报告：(a) 在 `pcs-frontend/playwright.config.ts` 的真后端 `webServer` 里加 `env: { VITE_PROJECT_ID: '<flows 项目 id>' }`（该 id 由 `scripts/seed_e2e_flows.py::FLOW_PROJECT_ID` 的 uuid5 派生，`uuid5(NAMESPACE_DNS,'pcs-e2e-flows-project')` 固定不变）；(b) 在 `pcs-frontend/package.json` 加 `e2e:real` 的完整前置（或新增 `pcs-backend/scripts/serve_e2e_backend.sh` 统一导出 DATABASE_URL=pcs_pgtest / PCS_ENABLE_MOCK_LOGIN=true / 端口）；(c) 加一条**可执行**的守卫：真后端通道启动时断言 `import.meta.env.VITE_PROJECT_ID` 非占位值，不等就 fail-fast，避免「查错项目 => 空表 => 假绿」。
  - Validation: confirmed
  - Reviewers: testing
  - Route: `gated_auto -> downstream-resolver`

- **#24** -- `pcs-frontend/src/pages/DashboardPage.tsx:40` -- 仪表盘 404 修复条件不严：工作区无 project_id 时照旧 404
  - Why it matters: bug-2168 的成因是面板拿到**占位 projectId** `00000000-0000-0000-0000-000000000001` 去取数（2 个 404 + 控制台 error），本批改成「没选工作区就不渲染面板」。但真正的触发条件是「拿到的 projectId 是占位值」，而不是「没选工作区」：`workspaceProjectId(ws)` 在 `ws.project_id` 为 null 时**仍然**返回占位 id。而 `Workspace.project_id` 是可空的，两个种子脚本造的工作区都**没填** project_id => 选中它们之后面板照旧用占位 id 取数 => 404 与控制台 error 照旧出现 => 真后端通道「控制台无 error」的断言仍会红。
  - Evidence:
    - pcs-frontend/src/pages/DashboardPage.tsx:40 -- `{selected ? <InputChecklistPanel projectId={projectId} /> : null}`
    - pcs-frontend/src/pages/DashboardPage.tsx:8-10 -- `function workspaceProjectId(ws: Workspace): string { return ws.project_id ?? '00000000-0000-0000-0000-000000000001'; }`（project_id 为 null 时仍给占位 id）
    - pcs-backend/app/models/project.py:118-119 -- `project_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("projects.project_id"), index=True)`（可空）
    - pcs-backend/scripts/seed_e2e_flows.py:338-343 -- `lambda: Workspace(workspace_id=FLOW_WORKSPACE_ID, workspace_type="FORMAL", name="E2E Flows Workspace", status="ACTIVE",)`（无 project_id => 前端选中后仍拿占位 id）
  - Suggested fix / response: 把渲染条件从「选了工作区」改成「拿到了真 project id」：抽一个 `const PLACEHOLDER_PROJECT_ID = '00000000-0000-0000-0000-000000000001'`，`const effectiveProjectId = selected?.project_id ?? null`，渲染条件用 `effectiveProjectId`（并在卡片标题里区分「该工作区未归属项目」）；同时给种子工作区补上 project_id（`seed_e2e_flows.py::_ensure_workspace` 与 `seed_e2e_data.py`），否则真后端通道的工作区列表里就有一个无项目的工作区。
  - Validation: confirmed
  - Reviewers: correctness
  - Route: `gated_auto -> downstream-resolver`

- **#25** -- `spec/P10 AI预留与测试部署开发规格说明书.md:666` -- 本批偏离登记写进非权威 SPEC 文件，D20 与本批自述互相矛盾
  - Why it matters: 本批按 PCS-SPEC-P10 V1.3.1 的编号与口径实现（E2E-011 交付物 Rev / E2E-012 签署矩阵与代录 / E2E-013 上游变更影响 / E2E-015 自定义报表 / E2E-017 AI / E2E-018 schema 一致），却把 D23~D38 这批 §3.2.2 口径修订登记在 V1.0 那份文件里 ---- 而计划自己的文件清单写的是 Modify: spec/PCS-SPEC-P10 V1.3.1 ...（第五部分「偏离登记」）。同时仓库里对「哪份 SPEC 是准」有两条互相矛盾的裁决：V1.0 文件的 D20 说「PCS-SPEC-P10 V1.3.1 在仓库中不存在 => 以 V1.0 为准」，本批计划说「两个文件都在 => 本批以 V1.3.1 为准」。结果：权威那份的 §3.2.2 一条都没被修订（D26/D29/D33/D34/D35/D37/D38 都在另一份文件里），下一个按权威文件读 SPEC 的人拿到的是过期口径。
  - Evidence:
    - spec/P10 AI预留与测试部署开发规格说明书.md:666-681 -- D23...D38（P10-B 批末增补）全部登记在这份 V1.0 文件里
    - spec/P10 AI预留与测试部署开发规格说明书.md:662 -- D20（文档治理）...「开发计划里引用的「PCS-SPEC-P10 V1.3.1」在仓库中**不存在**」...「以**仓库里这份 V1.0** 为准」
    - docs/superpowers/plans/2026-11-13-p10-batch-b-fullflow-e2e.md:956 -- "Modify: `spec/PCS-SPEC-P10 V1.3.1 P10 AI预留与测试部署开发规格说明书.md`（第五部分「偏离登记」）" => 计划要求改的是 V1.3.1 那份
    - docs/superpowers/plans/2026-11-13-p10-batch-b-fullflow-e2e.md:11 -- "**Spec:** `spec/PCS-SPEC-P10 V1.3.1 P10 AI预留与测试部署开发规格说明书.md` §3.2.2"
    - spec/PCS-SPEC-P10 V1.3.1 P10 AI预留与测试部署开发规格说明书.md:718-725 -- E2E-011 交付物 Rev / E2E-012 签署矩阵与代录 / E2E-013 上游变更影响分析 / E2E-015 自定义报表执行 / E2E-016 用户权限验证 / E2E-017 AI 占位与审计 / E2E-018 Schema 一致性 => 实现口径来自这份
    - CLAUDE.md《前端 UI 规范》：「字段/枚举/权限/错误码以 OpenAPI + meta API 为准；与 SPEC 冲突时以 OpenAPI 为准并登记 SPEC 修订。」
    - docs/superpowers/plans/2026-11-04-p10-master-plan.md:216-220（新增）----「=> WARNING **D20 的事实前提已变（2026-11-13 实测）**：**`spec/PCS-SPEC-P10 V1.3.1 ...md` 在仓库里存在**（59.3K ,  §3.2.2 有 18 场景 + WF-PATH 五类 + AUTH-E2E 12 条）=> => 「V1.3.1 不存在」**不成立** => => **以 V1.3.1 为准**... => 另一份 `spec/P10 AI预留与测试部署开发规格说明书.md`（29.3K）是 **V1.0**（只有 14 场景）=> => **别拿 V1.0 那份当准**。」
    - spec/P10 AI预留与测试部署开发规格说明书.md:662（未改动的上下文行）----「D20 （文档治理）本 SPEC 的文件名与版本 ... 开发计划里引用的「PCS-SPEC-P10 V1.3.1」在仓库中**不存在** ...」
    - spec/P10 AI预留与测试部署开发规格说明书.md:666-681（新增 D23~D38，每条末列引用 §3.2.2 / §3.2.0(2)，如 D26「18 场景「全部通过」」、D24「AUTH-E2E-11/12（`TEST_VIEWER` ...）」）
    - .wolf/STATUS.md:41（新增）----「**SPEC 偏离登记 D23~D38 已回写**（该 SPEC 实际是 **V1.0** => D20）。」（与 master-plan 新写的「以 V1.3.1 为准」互相打架）
  - Suggested fix / response: 把 D23~D38 同步到权威文件 spec/PCS-SPEC-P10 V1.3.1 ...md 的第五部分（或把两份合并成一份并把 D20 的裁决改掉），并在两份文件顶部互相标注「本批以 V1.3.1 为准」，避免下批继续按 V1.0 口径写。
  - Validation: not validated (P2/P3 advisory; outside the validator batch)
  - Reviewers: api-contract, project-standards
  - Route: `manual -> human`

### P3 -- Low (2)

| # | File | Issue | Reviewer | Confidence |
|---|---|---|---|---|
| 26 | `pcs-backend/app/schemas/stream.py:318` | 响应可空但请求仍必填：case_type 读写不对称 | api-contract | 75 |
| 27 | `pcs-backend/tests/scripts/test_pytest_e2e_gate.py:95` | flock 守卫测试用原文子串匹配（含注释）且不校验 -n；唯一入口守卫只数一个字面量 | learnings, testing, testing | 75 |

- **#26** -- `pcs-backend/app/schemas/stream.py:318` -- 响应可空但请求仍必填：case_type 读写不对称
  - Why it matters: StreamResponse.case_type 改成可空（对齐 DB 的 Mapped[str | None]），但请求侧 StreamBase.case_type 仍必填 => 读到的 null 值无法原样写回（GET->POST 回写会 422），「拿响应当入参」的客户端会踩空。前端既有消费点（StreamBasicTab / StreamListPage）已全部加空值保护，本批不破坏任何现有消费者，契约侧只是同一字段的读写要求不一致。
  - Evidence:
    - pcs-backend/app/schemas/stream.py:318-320 -- case_type: StreamCaseType | None = Field(None, description="物流级工况：NORMAL/END_OF_RUN/START_OF_RUN/TURN_DOWN（DB 可空）")
    - pcs-backend/app/schemas/stream.py:58-61 -- class StreamBase: case_type: StreamCaseType = Field(..., description=...) => 请求侧仍必填
    - pcs-frontend/src/pages/sim/StreamListPage.tsx:175 -- s.case_type ? STREAM_CASE_TYPE_LABEL[s.case_type] : '' => 前端消费点已空值安全（无破坏）
    - pcs-frontend/src/pages/sim/tabs/StreamBasicTab.tsx:71 -- stream.case_type ? STREAM_CASE_TYPE_LABEL[stream.case_type] : '--' => 同上
  - Suggested fix / response: 若 DB 可空是事实，请求侧也应允许省略（StreamBase.case_type 改 Optional，service 层决定补 NORMAL 或存 NULL）；否则在契约文档里明确登记「响应可空 => 入参必填，读-改-写不走 POST/create」，避免客户端拿响应当入参。
  - Validation: not validated (P2/P3 advisory; outside the validator batch)
  - Reviewers: api-contract
  - Route: `advisory -> human`

- **#27** -- `pcs-backend/tests/scripts/test_pytest_e2e_gate.py:95` -- flock 守卫测试用原文子串匹配（含注释）且不校验 -n；唯一入口守卫只数一个字面量
  - Why it matters: 同一文件里的另一个守卫专门写了 `_body()` 来剥掉注释，理由是「注释里提到 `uv run pytest` 是说明 => 断『脚本有没有做这件事』必须断可执行部分 => 否则注释就足以让守卫误红」----这正是 docs/solutions/testing-issues/guard-test-fooled-by-lying-comment.md 的教训。但同一个文件里的 flock 守卫却直接读**含注释的原文**做子串判断，且只断 `flock` 这个词存在，不断 `-n`（非阻塞）：`flock 9`（阻塞版）也能过，删掉 flock 代码而把这个词留在注释里也能过。=> 守卫证明的是「文件里出现过 flock 这个词」，不是「两条车道真的被互斥」。
  - Evidence:
    - pcs-backend/tests/scripts/test_pytest_e2e_gate.py:95-96 -- `    assert "flock" in pg_body, (` => 对**原文**（含注释）做子串判断
    - pcs-backend/tests/scripts/test_pytest_e2e_gate.py:93 -- `    pg_body = PG_SCRIPT.read_text(encoding="utf-8")` => 未剥注释（与同文件 `_body()` 的做法相反）
    - pcs-backend/tests/scripts/test_pytest_e2e_gate.py:49-50 -- `    WARNING 注释里提到 `uv run pytest` / `DATABASE_URL` 是**说明** => 断「脚本有没有做这件事」必须断**可执行部分**` => 同族教训已在本文件内
    - pcs-backend/scripts/pytest_pg.sh（diff）-- `if ! flock -n 9; then` => 真正被依赖的是 `-n`（抢不到就退出），守卫并不验证这一点
    - pcs-backend/tests/scripts/test_pytest_e2e_gate.py:94-98 ---- `pg_body = PG_SCRIPT.read_text(encoding="utf-8")` / `assert "flock" in pg_body` / `assert "pytest_pg.sh" in _body()`（**未剥注释**，且只断子串）
    - pcs-backend/tests/scripts/test_pytest_e2e_gate.py:32-43 ---- 同文件的 `_body()` 会剥掉注释 => 同一文件两套口径
    - pcs-backend/scripts/pytest_pg.sh:56-61 ---- `exec 9>"$LOCK_FILE"` / `if ! flock -n 9; then ... exit 1; fi`（真正要守的是 `-n` 与 fd 持有）
    - pcs-backend/tests/scripts/test_pytest_pg_gate.py:106-114 ---- `assert "pytest -m pg" in body` / `assert body.count("uv run pytest") == 2, "脚本里应只有「收集计数」与「正式执行」两次 pytest 调用；多出来的说明有人加了第二条路径"`（只匹配 `uv run pytest` 一个字面量）
    - pcs-backend/scripts/pytest_pg.sh:4-5 ---- 「WARNING **不得**在 README/CLAUDE.md 里教『也可以直接 DATABASE_URL=... pytest』---- 那会重新引入『多条路径做同一件事』的分叉」=> 该分叉是被承认的真实风险
  - Suggested fix / response: 给 pytest_pg.sh 也写一个剥注释的 `_body()`，把断言改成 `assert "flock -n" in body`（并在同一条里断言 `exec 9>` 存在，即锁确实落在 fd 9 上）。
  - Validation: confirmed
  - Reviewers: learnings, testing, testing
  - Route: `gated_auto -> downstream-resolver`

---

### Requirements Completeness

对照 `docs/superpowers/plans/2026-11-13-p10-batch-b-fullflow-e2e.md` (explicit). 判定口径是**实质达成**, 不是文件存在.

| Req | Plan 要求 | 判定 | 依据 |
|---|---|---|---|
| R1 | E2E 车道跑在隔离 schema 的真 PG (CREATE SCHEMA -> alembic upgrade head -> DROP CASCADE); 默认车道跳过全部 e2e, 绝不写开发库 pcs/pcs_test | partially addressed | 车道形态与 skip 闸门都在 (`tests/e2e_flows/conftest.py`, `scripts/pytest_e2e.sh`, `pyproject.toml`); 但车道只查 URL 协议不查库名 (#8), skip 闸门只在 pytest 收集到 `tests/e2e_flows/` 时才注册 (testing gap #1), 「不写 public」守卫取基线太晚且只数 4 张表 (#22) |
| R2 | 18 个 SPEC 场景 E2E-001..018 全部通过 (case count >= 18) | partially addressed | 场景文件齐备, `@pytest.mark.e2e` 共 30 条, 编号覆盖 E2E-001..018; 但 E2E-009 是 xfail (#4) 且闸门只要 1 条 passed 就算过 (#16) => 「全部通过」这个结论今天拿不到 |
| R3 | 五类 WF-PATH 路由类 (01A..01E / 02 / 03 / 04) 覆盖 | met | `test_e2e_record_workflow.py` (01A/01B/01D/01E + E2E-010) ,  `test_e2e_change_impact.py` (01C) ,  `test_e2e_deliverable_rev.py` (02/03) ,  `test_e2e_permission_matrix.py` (04) |
| R4 | 权限矩阵 AUTH-E2E-01..10 通过; 跨项目 => 404 且 body 与「不存在」同形; 角色不够 => 403 | partially addressed | 后端车道矩阵是四元组（角色 x 操作 x 状态码 x 错误码）, 钉住了 `APPROVAL_ROLE_MISMATCH` 这类真因, 是本批最扎实的一条断言纪律; 但同形只比到 code 不比 message 模板 (testing gap #3); 前端那条越权流被角色闸短路 (#5); 车道里 403 走的是「不留痕」分支 (#10) |
| R5 | AI 审计 E2E-017: AI 关 => 零副作用; AI 开 => 审计行**真的**落进 ai_audit_log | met | `tests/e2e_flows/test_e2e_ai_audit.py` 直接断言审计行落库（不是只入队）; AI 关的副作用另有车道 smoke 覆盖 |
| R6 | 两库 schema 一致 E2E-018: 比对 pcs 与 pcs_test 的 alembic_version, 不一致就登记不修 | partially addressed | 比对确实存在, 但它被塞进 E2E 车道并直连开发库 (#20), 且只比彼此、从不与代码 head 比 => 两库一起落后也是绿 (#21) |
| R7 | 前端真后端通道 6 条 UI 流通过 (5 新 + 1 smoke); mock 通道 23 条不回归 | partially addressed | 文件在 (`real_backend_flows.spec.ts`, `real_backend_route_sweep.spec.ts`), mock 通道本批未动; 但 3 条新流的断言结构上不可能失败 (#5/#6/#7), 且跑法依赖 4 个仓库外环境变量、只写在被 gitignore 的 QA 报告里 (#23) |
| R8 | 契约回写 (滚 OpenAPI baseline + 重生成前端类型) + SPEC 偏离登记 D23..D38 + 账簿更新 (STATUS/TODOS/buglog) + 批末 QA 收口 | partially addressed | 契约与账簿都动了 (`openapi-baseline.json` / `openapi.json` / `openapi.snapshot.json` / `api.d.ts` / STATUS / TODOS / buglog); 但 D23..D38 登记在**非权威**的 V1.0 那份 SPEC 里, 权威的 V1.3.1 一条没改 (#25); 本批 4 条可复用解法没回写 `docs/solutions/`, 而 STATUS 自称已回写 (#11); 批末 QA 报告在 gitignored 的 `.gstack/` 里, 仓库内不可复现 (#23) |
| R9 | PG 车道仍是唯一入口; E2E 是独立车道; 两条车道由共享 flock 互斥 | partially addressed | `scripts/pytest_pg.sh` + `scripts/pytest_e2e.sh` + `flock -n` 都在; 但 flock 只约束走进脚本的进程, compose 的 migrate/seed 两个写者不在锁内 (#15); 锁路径固定在 `/tmp` 且守卫测试只断 `flock` 这个词 (#27) |

#### 实施单元

| Unit | 判定 | 依据 |
|---|---|---|
| T1 E2E 车道 + 隔离 schema + e2e_client + lane smoke + 默认车道 skip 闸门 | partially addressed | 文件齐备 (`tests/e2e_flows/conftest.py`, `test_lane_smoke.py`, `tests/scripts/test_pytest_e2e_gate.py`, `scripts/pytest_e2e.sh`); 车道与种子无目标库白名单 (#8), 隔离只覆盖 get_db (#19), 守卫覆盖面过窄 (#22) |
| T2 进程级种子: 角色矩阵 / 起点态 / 幂等 | partially addressed | `scripts/seed_e2e_flows.py` 在; 幂等的 savepoint+重读赢家写法是对的; 但种子管级违反 `PipeClassResponse` 契约 => 按 id 查必 500 (#17); 车道不跑 lifespan, 注释承诺的启动 seed 实测 0 处调用 (#18) |
| T3 记录与计算链 (E2E-001..006) | met | `test_e2e_project_config.py` (001) ,  `test_e2e_sim_import.py` (002) ,  `test_e2e_calc_chains.py` (003..006) 齐备; 计算链那条断言实际断的是占位行副作用（#2 的同一根因） |
| T4 汇总/报表/供应商 (E2E-007/008/009/014/015) | partially addressed | 用例齐备; E2E-009 被命令式 xfail 中止 (#4), 而它背后的产品修复是空操作 (#3) |
| T5 记录层状态机 + 交付物 Rev (E2E-010..013 + WF-PATH) | met | `test_e2e_record_workflow.py` + `test_e2e_deliverable_rev.py` + `test_e2e_change_impact.py` 覆盖 01A..01E/02/03 与 010..013 |
| T6 权限矩阵 + AI 审计 + schema 一致 (E2E-016/017/018 + AUTH-E2E) | partially addressed | 三块都有; 矩阵的 403 分支在车道里不留痕 (#10), schema 一致检查错位 (#20) 且只比彼此 (#21) |
| T7 5 条真后端前端 UI 流 | partially addressed | 文件在; 3 条断言恒真 (#5/#6/#7), 跑法不可从仓库复现 (#23) |
| T8 契约/SPEC 偏离回写 + 账簿 + QA 收口 | partially addressed | 契约与账簿都动了; 偏离登记写错文件 (#25), 解法没回写 docs/solutions (#11) |

#### 反向检查（diff 里存在、但计划没有授权的行为规则）

逐条对照被评审的 diff 与计划正文, 发现 5 条**计划未授权**的行为:

1. **运行时往全局配置主表写主数据** (`pipe_chain_persist.py:95-138`). 计划的模型是「数据由种子造, schema 由迁移管」, 且已裁「本批不改 `alembic/versions/*`」=> 配置数据的落点被计划事实上关在迁移门外, 这一条是在请求路径上开的第三条路. 见 #2.
2. **把文件 sha256 写进 `report_files.data_version`** (`report_tasks.py:118`). 计划只要求「审计端点能拿到完整哈希」, 没要求占用「数据版本」这一列的语义. 见 #14.
3. **`preview-streams` 响应体由 list 归一成 `{"streams": [...]}`** (`sim_imports_query.py:325-330`). 计划没有登记这是一次对外契约变更, 且端点没有 `response_model` => 契约里仍是泛型 object. 见 #13 与 pre-existing #1.
4. **docker-compose 的 `seed` 服务被改成跑两个种子脚本** (`docker-compose.yml:140-153`). 这给共享库 `pcs_pgtest` 增加了一个**不持锁**的写者, 而计划把「两条车道不并发」写成硬约束. 见 #15.
5. **前端保留了第二条不经 axios 的 HTTP 通道** (`routeWrappers.tsx:85-92`). 计划授权改这个文件, 没授权引入一条绕过 401 拦截器、且静默吞错的取数路径. 见 #9.

---

### Coverage

**深度与范围**

- depth = **full** (size_band = large: 974 executable non-test lines); scope = `d73d1ac -> f3b35e5` on `main`, 55 files / 8659 changed lines (unclassified: json 1978, md 1869, txt 282, yml 15).
- scope mode = `local-aligned`; `tree_is_reviewed_head` = true (head 之后只有三个只碰 `docs/ce-code-review/` 的文档提交, 没有被评审的源路径变动).

**评审者 (9/9 全部收齐)**

correctness ,  project-standards ,  testing ,  maintainability ,  learnings ,  security ,  api-contract ,  **reliability** ,  adversarial.
reliability 是晚到的一份, 已并入合并集; 本轮 9 份 persona artifact 全部在盘上, 无失败/超时的评审者.

**跨模型 peer: 未启动**

本机没有技能允许的 peer provider CLI（codex / grok / composer / cursor-agent 均不在 PATH, `CROSS_MODEL_PEERS` 未设）=> 对抗性视角只能由**进程内**的 `adversarial` persona 承担. 后果: 本轮**每一条结论背后只有同一个 serving model**, 没有跨模型互证; 交叉评审者一致（`reviewers` 列表）因此**不提升置信锚**, 校验器的 21 条独立复核是本轮唯一的独立证据源.

**未选人士及理由**

performance（生产代码改动极小, 性能面集中在测试种子, 无实质资源影响）,  data-migration（diff 内无迁移/模式产物, 无 backfill 可审）,  agent-native（diff 未暴露 agent 面向的能力或工具面）,  julik-frontend-races（前端是 React/TypeScript, 非 Stimulus/Turbo）,  swift-ios（diff 内无 Swift/iOS 文件）,  previous-comments（standalone 评审, 无 PR 与历史评论）,  deployment-verification（无高风险迁移产物需要上线前核验）.

**合并机制**

- 68 条原始 persona 发现 -> 28 条合并候选（27 primary + 1 pre-existing）.
- 5 条原始发现（security persona 整体）因缺 `pre_existing` 字段被判畸形, 已按引用的行重建并合并, 未丢弃.
- `first_evidence` 回填 **61** 条（第一遍 helper 从 `evidence[0]` 回填）, 调和那一遍需回填 0 条.
- 引用行闸门（quote-the-line）因缺 `first_evidence` 而降级的条数: **0**.
- 置信锚 50 被压制: 第一遍 1 条, 最终遍 0 条. 被压制的候选经软分桶后保留计数, 其余丢弃.
- 模式感知降级（mode-aware demotion）**12** 条: 9 条进 `residual_risks`, 3 条进 `testing_gaps`; 另有 **1** 条因前提在盘上被推翻而整体丢弃.
- 计划已发现（explicit）=> 已评估 settled decisions. 计划的 8 条已裁决策没有被本次发现挑战; **0** 条因「偏好与已裁决策冲突」被丢弃. 「E2E 进 CI」延到 P10-F 是既有裁决, 不计为本批缺陷.

**校验器: 已运行**

| Outcome | Count |
|---|---|
| confirmed | 20 |
| rejected | 0 |
| unresolved | 1 |
| malformed | 0 |
| failed | 0 |
| shortcut-skipped | 0 |
| 未进批次 (P2/P3 advisory, 批次外) | 6 |

- 批次形态: **单批 21 条**（全部 P0/P1 + 全部 actionable）, 按严重度再按稳定 `#` 排序; 没有拆第二批, 没有跳过任何一条 => 捷径跳过数 = 0.
- 唯一未决项 **#6**: 名字错配已核实, 但「内置 `DEFAULT_RECORD_3_LEVEL` 行在目标库是否存在」在预算内没核实到（迁移 p9_013 未读）=> 它留在报告里作为**核实闸门**（`validation_status: unresolved`, `owner: human`, `autofix_class: advisory`, `requires_verification: true`), **不在**可执行队列, 任何修复者都不得把它当已确认缺陷去改.
- protected subject 复核: 合并 leaf 独立核对了 21 条的 `protected_subject`（8 个策略键）=> 全部是合法键或 null; 7 条带 protected subject（#1 concurrency ,  #3/#12/#13/#17 public-contract ,  #5/#9 authorization-authentication ,  #8 data-loss）. **没有任何一条被否掉**, 因此没有 protected-subject 重分类.
- #1 与 #8 的确认附注「incidence not measured」: 代码允许该失败, 但没有测试或查询证明它真的发生过. 这两条在报告里按「已确认但发生率未知」呈现.
- 没有任何 P0/P1 因校验器故障而处于 degraded 状态.

**本批自认的债 与 本次发现的关系**

| 本批自认的债 | 本次评审的结论 |
|---|---|
| bug-2165 根因未闭环（`report_tasks._finalize` 赋值不落库 => E2E-009 标 xfail） | **根因被定位且被记错了**: 不是「对象与被 flush 的行脱钩」, 而是那行赋值位于 `dup` 早退 `return` 之后 => 永不可达 (#3). TODO-158 可以对着 #3 关, 而不是继续挂着. |
| 运行时写配置表的占位管级, 并发下可能撞唯一约束 | **两条都成立且被确认**: 并发首算 500 是真的 (#1), 而且比自认的更重 ---- 它还让每个用户在公司管级列表里看到一条假公司标准 (#2). |
| 3 个前端页面调不存在的端点 + 3 个页面首屏 422 (TODO-159/160) | 这正是路由扫描该抓的, 而扫描只把它打印不断言 (#7); 两类问题在真后端通道里**没有守卫**. |
| E2E 进 CI 延到 P10-F | 已裁决策, 不计为本批缺陷; 但「E2E 用例存在」与「E2E 被验过」之间仍有空转, 已登记为 residual risk. |

**Removable surface:** 约 44 行 / 1 个文件（`pipe_chain_persist.py:95-138`, 来自 #2 的建议）---- 这是死重量信号, **不是**削减目标, 不为凑数而放大.

---

### Testing Gaps

（模式感知降级进来的 3 条 absence-of-coverage 关注点, 均**未**升级为 primary 发现）

1. [testing] e2e 跳过闸门只随 e2e_flows 目录注册 (pcs-backend/tests/e2e_flows/conftest.py:84) - `pytest_collection_modifyitems` 定义在 `tests/e2e_flows/conftest.py` 里 => 它只有在 pytest 真的收集了 `tests/e2e_flows/` 时才会被注册。目前所有 `@pytest.mark.e2e` 用例都在这个目录里（已核对：仓库内 e2e marker 只出现在 `tests/e2e_flows/`），所以默认车道 `uv run pytest` 是安全的。但这个保证是**巧合式的**：把一条 e2e 用例放到 `tests/api/v1/` 之类的地方，再有人用 `pytest tests/api` 跑（不经过 e2e_flows 目录），闸门就不存在 => 该用例直接打到开发库。守门测试 `test_e2e_items_are_skipped_without_the_lane_flag` 只用一个假 item

2. [testing] case_type 可空的修复没有后端回归测试 (pcs-backend/app/schemas/stream.py:318) - 本批把 `StreamResponse.case_type` 改成可空（bug-2167：不改则 `GET /projects/{id}/streams` 因枚举校验失败整体 500）。这条修复的**唯一**覆盖在 Playwright 真后端通道（「物流一览」页看得到种子物流）。后端两侧都没有：快车道 `tests/schemas/test_stream_vocabulary.py` 只断言词表四项与 `raw_phase`，从不断言 `case_type` 可选；E2E 车道的隔离 schema 里**正好躺着会触发这个 bug 的数据**（`scripts/seed_e2e_flows.py:428-448` 建 Stream 时根本没给 case_type => NULL），却没有任何一条 e2e 用例去 GET `/projects/{id}/streams`（已 grep 全目录

3. [learnings] 同形断言只比状态码与 code，不比 message 模板 (pcs-backend/tests/e2e_flows/test_e2e_permission_matrix.py:147) - 仓库已记录的死法是「无权」与「不存在」必须**逐字同形**（含 code 与 message），否则攻击者靠响应差异枚举 UUID；同一条记录还写了「同形测试必须用同一个 uuid 测两次......消息里本来就带着请求的 id => 拿两个不同的 uuid 比测不出同形性」。本批的两条同形断言都停在「状态码 + code」：后端比 `missing.json().get("code") == resp.json().get("code")`（uuid 还不一样：一个是种子项目 id，一个是 `uuid.uuid4()`），前端只比状态码。=> 只要有人把无权分支的 message 改成不同措辞（例如「无权访问项目 X」而「不存在」是「Project not found: X」），两条用例都仍绿，而枚举向量已经打开。守卫断的是**动作的投影**（两个字段相等），不是**逐字同形**这个后果。

---

### Residual Risks

（9 条, 供知情, 不是待修队列）

1. [maintainability] seed_e2e_flows 逐字复制了 seed_e2e_data 的 get-or-create (pcs-backend/scripts/seed_e2e_flows.py:243) - 两个种子脚本现在各自持有一份**逐字相同**的 `_get_or_create`（含 savepoint + IntegrityError + 重读赢家的三步竞态处理），以及各自一份 `_delete_own_rows`（两份互不相同的 FK 删序清单）、`_ensure_workspace` / `_ensure_project` / `_ensure_users` / `_ensure_grants` / `_ensure_streams`（同构不同参）。两份真相源意味着：竞态处理被修好（这正是该 helper 存在的理由）时只改得了一边 => 另一边的种子在并发下仍会炸；新增实体时两份删序清单都要记得改 => 漏一份 => `--reset` 撞 FK。这不是「两个脚本各管一段业务」，而是同一个「幂等种子」的 house pattern 被抄了两遍。

2. [maintainability] 批准链角色在 helpers 与种子之间有两份未钉住的副本 (pcs-backend/tests/e2e_flows/helpers.py:206) - `CHAIN_ROLES = ("CHECKER", "REVIEWER", "APPROVER")` 是种子里 `FLOW_MATRIX_STEPS` 的 `sign_role` 序列的**第二份副本**，注释还明说「与种子的签署矩阵一致」----但一致性**没有任何机制保证**：全仓 `FLOW_MATRIX_STEPS` 只出现在种子脚本里，`CHAIN_ROLES` 只出现在 helpers 与一个断言里，两边**没有一处比对**。矩阵一改（加一级、改角色、换顺序），`approve_record_steps` 仍按旧角色发请求 => 端点返 403 `APPROVAL_ROLE_MISMATCH` => 症状是「端点坏了 / 批准链卡住」，排查方向会跑到业务代码上。仓里已经有正确做法的样板：`ALLOWED_ROLES` 那份 copy 就被 `test_lane_smoke.py::t

3. [maintainability] bump_record 在测试文件里被逐字重写了一遍 (pcs-backend/tests/e2e_flows/test_e2e_record_workflow.py:48) - `helpers.py:353 bump_record` 已经存在并且被 `test_e2e_change_impact.py` 正常使用；`test_e2e_record_workflow.py:48 _bump_record` 把它**逐字抄了一份**（同样的 `design_press + 0.1`、同样的 `compute_record_hash`、同样的 `await db.flush()` 后算哈希）。两份实现意味着「哈希怎么算、什么时候算」这条规则有两处；将来 CIA 的哈希判据变了（例如改成含更多列），改了 helpers 那份，record_workflow 的变更流仍按旧规则 => 那条用例会绿着验证一个已失效的判据。

4. [maintainability] 会话工厂挂在 client 的私有属性上（14 处 type: ignore） (pcs-backend/tests/e2e_flows/conftest.py:294) - 车道把 `session_factory` 藏进 `httpx.AsyncClient` 实例的私有属性 `_e2e_session_factory`，于是「直查隔离 schema」这件事在 7 个文件里靠 `# type: ignore[attr-defined]` 维持（helpers.py 5 处 + 4 个测试文件 + conftest 1 处）。这是把 fixture 契约藏进一个约定俗成的私有属性里：类型检查器永远看不见它，属性名一改要靠全仓 grep 才能找齐 14 个点；更根本的是**「要一个 DB session」被迫先造一个 HTTP client**----这正是 Feature Envy：helpers 的 `make_record` / `bump_record` / `link_lineage` / `get_record_state` 只需要 session，却都

5. [maintainability] scripts/ 被当成测试 fixture 的公共库 (pcs-backend/tests/e2e_flows/helpers.py:228) - 测试层的 fixture 数据住在**CLI 脚本**里：`helpers.py` 从 `scripts.seed_e2e_flows` 取 `PIPING_RECORD_PAYLOAD`（造记录的 21 字段模板），`conftest.py` 从同一个脚本取全部 id 与角色映射。`scripts/` 是个装着 CLI 入口的目录，不是包（靠 namespace package 被 import 进来），现在却被当公共库用 => 后果是「测试夹具的真相源」与「一个运维脚本」耦合：这个脚本为了当库用而不断加 `__all__`（scripts/seed_e2e_flows.py:773-794 已经列了 20 个常量），脚本的重构会牵动测试，测试想加一个 fixture 字段就得改一个 CLI 脚本。分层上，生产/运维脚本是上层，测试夹具是下层----依赖方向反了。

6. [maintainability] test_lane_smoke 里的 text_ 辅助函数是死代码 (pcs-backend/tests/e2e_flows/test_lane_smoke.py:247) - `text_()` 定义后全文件零引用（同文件的 SQL 都在函数体内直接 `from sqlalchemy import text`）----新文件里的死代码，读者会以为有一条「统一走 text_ 短别名」的约定。顺手删掉即可。

7. [reliability] 隔离 schema 清理只在 finally，进程被杀就永久留垃圾 (pcs-backend/tests/e2e_flows/conftest.py:191) - schema 生命周期是「建 -> 迁移 -> DROP CASCADE」，但**清理只挂在 fixture 的 `finally` 上**：SIGKILL / 容器被强杀 / DB 断连 / 机器重启 => `finally` 不跑 => 隔离 schema（含一整套被迁移过的表）永久留在共享的 `pcs_pgtest` 库里，而**没有任何 janitor/reaper**；下一轮跑的「起手 DROP」只针对**本轮那个随机名**（`e2e_<8hex>`，conftest.py:164）=> 旧残留一个都清不掉 => 垃圾无声累积（每轮一份全量 schema）。另外 `finally` 里的 `DROP SCHEMA ... CASCADE` 自己也可能抛（连接已断）=> 会**顶替掉真正的失败原因**，让排障看到的是一个无关的连接错误而不是真正的失败。

8. [security] Predictable /tmp lock path opened with truncation (pcs-backend/scripts/pytest_pg.sh:57) - `exec 9>"$LOCK_FILE"` truncates the target path. The default is a fixed, world-writable-directory name (`/tmp/pcs-pgtest-lane.lock`), so on a shared host another local user can pre-create that path as a symlink to any file the developer can write; the next lane run then truncates that file (shell redirection follows symlinks) -- silent destruction of e.g. a source file or a shell rc, with the lane

9. [learnings] 默认车道 skip 闸门只有「假 item」的动作断言 (pcs-backend/tests/e2e_flows/test_lane_smoke.py:194) - conftest 自己写明「这是本批最危险的一条：不加它，批末那句 `uv run pytest` 会把 E2E 场景跑到开发库 `pcs` 上」。守卫却只用一个 `_FakeItem` 断言 `add_marker` 被调过----断的是**动作**，不是**后果**（已记录的通则：守卫要断言后果，不要断言动作；动作可以空转，后果不会）。真正的后果是「默认车道里一个 e2e 用例都没被执行」：只要有人给 tests/e2e_flows/ 加一条忘了 `@pytest.mark.e2e` 的用例（或把 marker 改名），它就会在默认车道**真的连上开发库**跑隔离 schema + alembic + 种子，而当前守卫仍然绿（它只测闸门函数本身，对新用例零感知）。今天 13 个文件里 marker 是齐的（lane_smoke 的 7 条里有 2 条是故意不标 marker 的默认车道守卫

---

### Pre-existing Issues

（不计入 verdict; 1 条）

| # | File | Issue | Reviewer |
|---|---|---|---|
| P1 | `pcs-backend/docs/openapi-baseline.json:1` | 契约基线只是『与当前一致』的同步锁，没有已发布契约锚点 | api-contract |

- **P1** -- `pcs-backend/docs/openapi-baseline.json:1` -- 契约基线只是『与当前一致』的同步锁，没有已发布契约锚点
  - Why it matters: 核实结论：基线漂移的主体确实是上一批的 AI 端点契约 ---- openapi.json 在 6292ca2（AI 契约去掉死分支 200 + 补 401/503）时更新而基线没跟，本批把基线滚到与 openapi.json 逐字相同（三个文件 blob 哈希同为 6663086）。但 gate_08 的第 4 阶段只是 `diff -q baseline openapi.json` => 基线必须永远等于当前规格 => 它不是「已发布/对外承诺过」的契约锚点 => 任何破坏性变更（如本批 StreamResponse.case_type 由必填改为可空）都能无版本、无弃用期、无迁移说明地进契约，客户端只能事后发现。
  - Evidence:
    - pcs-backend/scripts/gate_08_openapi_contract.sh:71-80 -- if diff -q pcs-backend/docs/openapi-baseline.json pcs-backend/docs/openapi.json > /dev/null; then echo "OK baseline 与当前一致（无漂移）" => 基线是同步锁，不是发布锚点
    - pcs-backend/docs/openapi.json:41978-41985 -- "required": [ "stream_name", -"case_type", "data_mode", ... ] => 响应字段由必填变可空（对 1.0 契约是破坏性变更），全仓无版本号/弃用标记
    - git 6292ca2 fix(P10-A): 评审 #12/#13/#19 ---- AI 契约去掉死分支 200 + 补 401/503 + 运行时出口守卫 => openapi.json 变了而 openapi-baseline.json 未变（基线漂移主体 = 上一批的 AI 契约）
  - Suggested fix / response: 若要真正的契约稳定性闸门，另存一份「上次发布/对外承诺」的契约（例如 docs/openapi-released.json）并在批末用 openapi-diff 跑出 breaking 清单；当前 openapi-baseline.json 只能证明「后端规格 / 前端 snapshot / 前端类型三份同步」，不能证明「对外契约没破」。本批的 case_type 破坏性变更至少应在批末账簿里显式登记一条「响应字段放宽为可空」的对外说明。
  - Route: `advisory -> release` (pre-existing, 不计入 verdict)

---

### Learnings & Past Solutions

#### Known Pattern（diff 遵守的既有解法, 无违反行 => 不构成发现）

- [Known Pattern] `docs/solutions/database-issues/get-or-create-default-row-race-savepoint-reread.md` -- get-or-create 的竞态三步（savepoint -> IntegrityError -> 重读赢家）。本批的**种子脚本**照抄了这个写法（`scripts/seed_e2e_flows.py:243-270`），**产品代码那一段没有照抄**（#1）。
- [Known Pattern] `docs/solutions/testing-issues/engine-level-migration-tests-skipif-pg.md` -- 隔离 schema + 子进程 alembic + 清理要响亮。本批的车道沿用了这个形状（`conftest.py` 里 `CREATE SCHEMA` -> 子进程 `alembic upgrade head` -> `DROP CASCADE`），并补齐了 asyncpg 驱动与 `search_path` 两个校准点。
- [Known Pattern] `docs/solutions/testing-issues/sqlite-staticpool-hides-uncommitted.md` -- 守卫要断言后果, 不要断言动作。本批在 public schema 前后快照上**部分**遵守（覆盖面与基线时机仍不足, #22）。
- [Known Pattern] `docs/solutions/testing-issues/guard-patched-definition-site-consumer-imported-by-value.md` -- 守卫要断可执行部分、要看消费者。本批的隔离只覆盖 `get_db` 一个消费者, 全局 session factory 另走一路（#19）；守卫测试用 per-PID 临时锁绕开了默认锁路径（#15）。
- [Known Pattern] `docs/solutions/testing-issues/guard-test-fooled-by-lying-comment.md` -- 注释里提到某个词不等于脚本做了那件事。同一个文件里的 flock 守卫却直接读含注释的原文做子串判断（#27）。
- [Known Pattern] `docs/solutions/security-issues/midflight-config-rebind-defeeds-one-shot-guards.md` -- 守卫判据要具体（错误码, 不是状态码）。本批的权限矩阵用了四元组并钉住 `APPROVAL_ROLE_MISMATCH`, 是本批最扎实的一条; 但同形断言只比到 code 不比 message 模板（testing gap #3）。
- [Known Pattern] `docs/solutions/testing-issues/narrow-declaration-is-not-a-constraint.md` -- 窄声明不是约束。本批的 `case_type` 响应可空 / 请求仍必填就是这条的近亲（#26）。

#### 本批沉淀出的可复用形状（尚未回写 `docs/solutions/`）

1. **给前端建第二个 Playwright project + tag 隔离, 断言必须断具体内容.** mock 的 MSW 不校验 token => 写死的假 token 与占位 projectId 这两类缺陷在 mock 通道永远隐形; 真后端通道一次性抓到 5 个. 配套纪律: 「页面渲染了」证明不了连的是被 seed 的库（因为 mock 登录不落 users 表, 后端回 404 不产生 console error）=> 必须断具体行内容. 延伸到 `docs/solutions/testing-issues/guard-test-fooled-by-lying-comment.md` §4.
2. **带互斥锁的测试车道, 守卫测试必须自带一份锁实例.** 否则守卫被真实车道挡在门外, 测的不是它声称的那几条闸门. 本批用 `PCS_PGTEST_LANE_LOCK` 解决, 代价是默认锁路径从未被测过（#15/#27）. 延伸到 `docs/solutions/testing-issues/guard-patched-definition-site-consumer-imported-by-value.md` §6.
3. **隔离 schema 车道的四个必做校准**: async 引擎必须换成生产驱动（asyncpg, 否则 VARCHAR 塞 int 被 psycopg 悄悄转换而绿）,  asyncpg 不认 `options=-csearch_path=`（要用 `server_settings`）,  alembic 必须在子进程跑（pydantic-settings 缓存）,  两条车道共用一个库时锁要放在**共享**脚本里. 延伸到 `docs/solutions/testing-issues/engine-level-migration-tests-skipif-pg.md`.
4. **把「隔离」从注释变成可断的事实**: 写下「我会写哪些表」的清单, 守卫照单全收, 并且在种子**之前**取基线、同时断 `count(*)` 与 `max(id)`. 延伸到 `docs/solutions/sqlite-staticpool-hides-uncommitted.md`.
5. **权限矩阵用四元组, 并给每条用例配一根「分支可达」的钉子.** 四元组（角色 x 操作 x 状态码 x 错误码）防的是「换个原因照样绿」, 但它**不**防「压根没走到那个分支」---- 本批的前端越权流就是四元组退化成「两个码相等」的实例（#5）. 延伸到 `docs/solutions/security-issues/midflight-config-rebind-defeeds-one-shot-guards.md`.
6. **目录级东西（conftest / marker 注册 / addopts）落笔前先 ls 住客.** 本批正确避开了 `tests/e2e/`（已被 12 条无 skip 用例占用）, 并把这个泛化写进了 conftest docstring.

> 这 6 条**都没有**回写进 `docs/solutions/`, 而 `.wolf/STATUS.md` 自己写着「已进 cerebrum / docs/solutions」=> #11. 计划与仓库的规则要求「新增解法后回写一份」, 这条债是本批自己欠的.

---

### 尚未解决的问题（需人裁决）

以下 7 条需要人做决定, 评审侧无法自行裁定; 另有 1 条需要一次证据查询（不是决策）.

1. **占位管级的归属（#2, P1, `manual -> human`）** -- 改成一条数据迁移种一行 `CS-STD`, 还是允许运行时兜底并把它从公司管级列表里过滤掉? 这条决定同时决定 #1 的修法（savepoint 重读赢家 vs `ON CONFLICT DO NOTHING`）与 T1 组的顺序. **注意计划已裁「本批不改 `alembic/versions/*`」**, 选迁移路线等于改写那条裁决, 需要明示.
2. **`data_version` 与 `record_hash_digest` 的语义（#14, P2, `manual -> human`）** -- 文件摘要到底放在哪: 读 `content_hash`（占位前缀时返空串）, 还是新增一个明确命名的列/字段? `data_version` 这个名字一旦被摘要占死, 将来想真填数据版本就没位置了. 与 #3 / #12 同组, 但**语义归属**要人裁.
3. **RBAC 拒绝的审计留痕要不要在车道里放开（#10, P2, `manual -> human`）** -- 早退的理由是「防测试写真实 DB」, 而车道已经是隔离 schema; 放开它会让 403 语义在车道里被真验, 代价是错误处理路径多一条写者. 这是「生产语义」与「测试隔离」之间的取舍.
4. **4 条可复用解法要不要现在回写 `docs/solutions/`（#11, P2, `manual -> human`）** -- 仓库规则要求回写, STATUS 已经声称回写过. 要么补上 4 份, 要么改掉 STATUS 那句话. 不能两者都不做.
5. **车道互斥要不要提升到库级别（#15, P2, `manual -> human`）** -- 锁现在只约束走进脚本的进程, compose 的 migrate/seed 两个写者不在锁内; 锁路径又固定在 `/tmp`（可被清理 => inode 换新 => 互斥静默失效）且 `exec 9>` 会截断目标路径. 提升到库级别意味着要动 compose 的服务定义, 属于跨栈决定.
6. **哪一份 SPEC 是权威, D23..D38 登记到哪里（#25, P2, `manual -> human`）** -- 仓库里有两条互相矛盾的裁决（V1.0 文件的 D20 说「V1.3.1 不存在」, master plan 说「两个文件都在, 以 V1.3.1 为准」）, 而本批把偏离登记写进了 V1.0 那份 => 权威文件的 §3.2.2 一条都没被修订. 这条不裁, 下一批会继续按过期口径写.
7. **`case_type` 请求侧要不要允许省略（#26, P3, `advisory -> human`）** -- 响应可空而请求必填 => 「拿响应当入参」的客户端会 422. 要么两边都放开, 要么在契约里明确登记「读-改-写不走 POST/create」.

**需要一次证据查询（不是决策）:**

- **#6（P1, validation = unresolved）** -- 先读 `alembic/versions/p9_013_bind_default_record_matrix.py` 并在目标库直查 `DEFAULT_RECORD_3_LEVEL` 是否存在. 存在 => 断言被内置矩阵满足 => 改断言名; 不存在 => 这条流是因为别的原因红 => 修种子/迁移. **证据到手前不要动代码.**

---

### Verdict

> **Verdict:** Not ready
>
> **Reasoning:** 按「人用这个软件拿到什么」重新分级 ---- 本批交付的是一条**验证车道**, 所以真正的验收标准是「这条车道能不能证明它声称的东西」. 答案今天是否定的, 而且**失败得安静**: 闸门只要 1 条 passed 就算过 (#16), E2E-009 用命令式 xfail 中止 (#4), 前端 5 条流里 3 条的断言结构上不可能失败 (#5/#6/#7) => 车道的绿灯不承载信息. 与此同时本批的显式计划要求 R2（18 场景全部通过）与 R7（6 条真后端 UI 流）**实质未达成**, 而计划是 explicit => 按规矩这已经不是「代码干净但少做」, 而是「验收本身没成立」. 再叠上 9 条未闭的 P1: 其中 #2 会让每个用户在公司管级列表里看到一条假的公司标准, #1 会让并发首次计算整条端点 500, #3 让本批唯一的生产修复变成空操作且 buglog 的根因记录是错的, #8/#19/#22 让「绝不碰开发库」这条本批最硬的约束只立了一半. 没有 P0, 所以问题不在于有东西被攻破, 而在于**这一批交付的东西不能被信任**. 1 条 P1 (#6) 还是未决核实闸门, 需要一次证据查询而不是一次改代码.
>
> **Fix order:** ① **T1 裁决 + #1**（先裁占位管级归属, 再按裁决上 savepoint）-> ② **T2 全组 #3/#4/#12/#14**（审计哈希这条需求一次做完四步, 含 `data_version` 语义裁决）-> ③ **T4 护栏 #8/#19/#20/#18**（车道与种子的目标库白名单、隔离覆盖 session factory、把 schema 一致检查挪出场景车道、lifespan 或改注释）-> ④ **T3 前端断言 #5/#7**（#6 先查证再动）-> ⑤ **T7 闸门 #16/#22/#21/#27**（闸门本身先 fail-closed, 否则前面几条修完仍然测不出来）-> ⑥ **T5 #9/#23/#24 与 T6 #17/#13/#26**（种子那行按契约改是硬故障, 优先于契约漂移）-> ⑦ 决策项 #10/#11/#15/#25 与 pre-existing 的契约锚点登记.

---

### Actionable Findings Recap（按优先级, 供直接消费）

| # | Sev | File:line | What | Response |
|---|---|---|---|---|
| 3 | P1 | `pcs-backend/app/workers/report_tasks.py:118` | data_version 赋值在 dup 早退之后永不可达 => 审计哈希端点仍恒返空串 | mechanical fix, validator confirmed |
| 4 | P1 | `pcs-backend/tests/e2e_flows/test_e2e_report.py:91` | E2E-009 用命令式 pytest.xfail 中止用例 => 车道全绿且下载段从不执行 | mechanical fix, validator confirmed |
| 1 | P1 | `pcs-backend/app/services/pipe/pipe_chain_persist.py:112` | 占位管级先查后插无 savepoint => 并发首算撞主键 => 整条计算 500 | mechanical fix, validator confirmed |
| 8 | P1 | `pcs-backend/tests/e2e_flows/conftest.py:93` | E2E 车道与种子脚本都没有目标库白名单 => 可在开发库上建 schema 并灌种子 | mechanical fix, validator confirmed |
| 19 | P2 | `pcs-backend/tests/e2e_flows/conftest.py:289` | 隔离只覆盖 get_db：全局 session factory 仍指 public schema | mechanical fix, validator confirmed |
| 22 | P2 | `pcs-backend/tests/e2e_flows/test_lane_smoke.py:240` | 『不写 public』守卫只覆盖 4 张表、只取一次基线 | mechanical fix, validator confirmed |
| 16 | P2 | `pcs-backend/scripts/pytest_pg.sh:83` | 闸门③只要求『至少 1 passed』=> 29/30 场景被 skip 也是绿的 | mechanical fix, validator confirmed |
| 5 | P1 | `pcs-frontend/e2e/real_backend_flows.spec.ts:144` | 越权 UI 断言恒等：bob 被角色闸挡在项目守卫之前 => 跨项目 404 分支从未执行 | design input needed, validator confirmed |
| 7 | P1 | `pcs-frontend/e2e/real_backend_route_sweep.spec.ts:56` | 路由扫描的『渲染出来了』断言恒真，且 console error / 4xx 只打印不断言 | design input needed, validator confirmed |
| 17 | P2 | `pcs-backend/scripts/seed_e2e_flows.py:516` | 种子管级违反 PipeClassResponse 契约 => 按 id 查必 500 | mechanical fix, validator confirmed |
| 9 | P1 | `pcs-frontend/src/pages/routeWrappers.tsx:87` | useFetch 静默吞错且绕过 axios 401 拦截器 => token 过期后永久停在加载中 | mechanical fix, validator confirmed |
| 13 | P2 | `pcs-backend/app/api/v1/sim_imports_query.py:325` | preview-streams 无 response_model，契约未记录本批统一的形状；注释与事实相反 | mechanical fix, validator confirmed |
| 18 | P2 | `pcs-backend/tests/e2e_flows/conftest.py:272` | E2E 车道不跑 lifespan，注释称已补启动 seed 实测 0 处调用 | design input needed, validator confirmed |
| 20 | P2 | `pcs-backend/tests/e2e_flows/test_e2e_schema_parity.py:57` | schema 一致性检查塞进隔离车道且直连开发库 pcs / pcs_test | design input needed, validator confirmed |
| 21 | P2 | `pcs-backend/tests/e2e_flows/test_e2e_schema_parity.py:73` | 两库 schema 一致闸只比彼此、不与代码 head 比 => 两库都落后也绿 | mechanical fix, validator confirmed |
| 23 | P2 | `pcs-frontend/package.json:20` | 真后端 UI 车道依赖 4 个仓库外环境变量 => 无法从仓库复现 | mechanical fix, validator confirmed |
| 24 | P2 | `pcs-frontend/src/pages/DashboardPage.tsx:40` | 仪表盘 404 修复条件不严：工作区无 project_id 时照旧 404 | mechanical fix, validator confirmed |
| 12 | P2 | `pcs-backend/app/api/v1/report.py:494` | 审计哈希端点返回值随行龄不同（老行与复用行恒返空串） | mechanical fix, validator confirmed |
| 27 | P3 | `pcs-backend/tests/scripts/test_pytest_e2e_gate.py:95` | flock 守卫测试用原文子串匹配（含注释）且不校验 -n；唯一入口守卫只数一个字面量 | mechanical fix, validator confirmed |

> Actionable 队列共 **19** 条（#1, #3, #4, #5, #7, #8, #9, #12, #13, #16, #17, #18, #19, #20, #21, #22, #23, #24, #27）; 另有 8 条 report-only（#2, #6, #10, #11, #14, #15, #25, #26）, 其中 **#2 / #10 / #11 / #14 / #15 / #25 / #26** 需要人先裁决, **#6** 需要一次证据查询. 报告路径: `docs/ce-code-review/20261117-013829-7e9fbabe/report.md`.