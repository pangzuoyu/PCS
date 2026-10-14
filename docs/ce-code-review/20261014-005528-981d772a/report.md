## 代码评审结果

**范围：** base `cfc0f2e` -> head `a9ccb84`（standalone，审查集收窄到 P8 面 46 个文件；该窗口内另含 P7 heat/calc 工作）
**意图：** 审查 PCS 项目 P8（报表与输出）阶段已落地的全部代码 —— 固定 10 类报表（ReportLab 直出 PDF/Excel，样式版本冻结）+ 自定义报表构建器（ARQ 异步执行）。关注面：异步任务生命周期正确性（提交/重试/回收）、项目级数据隔离、迁移与 ORM 一致性。
**模式：** markdown report-only（`mode.apply_local = false`，本次未授权应用任何修复）
**计划：** `docs/superpowers/plans/2026-10-08-p8-report-and-report-builder.md`（explicit）
**深度：** full

**评审团队：** correctness, api-contract, reliability, performance, security, testing, maintainability, julik-frontend-races, data-migration, project-standards, adversarial
- project-standards -- 仓库无 `CODING_STANDARDS.md`，按 instruction-file fallback 取根 `CLAUDE.md` + `.claude/rules/openwolf.md`
- data-migration -- P8 落地了 p8_001..p8_007 共 7 个迁移
- adversarial -- 本机不存在异 provider 的对等通道，跨模型复核未运行，对抗视角由进程内 adversarial reviewer 承担

### Triage Groups

| 组 | 涉及 | 背景 | 首选处置 | 为什么 | 性质 |
|-----|------|------|---------|--------|------|
| 异步任务跨 ARQ 边界不落盘 | #2, #3, #6, #21 | 同一处边界上的四个缺陷：谁来 commit，谁来写终态。#2 掩盖了另外三个 —— 回收器不 commit 时 #6 / #21 不可见 | 一轮做完，#2 先行，但 #6 必须与之同批落地（见下方 Why） | 单独修 #2 会把被掩盖的缺陷变成真实的数据损坏 | apply-queue |
| 固定 10 类导出缺项目隔离 | #1 | `builder_service` 有项目范围（bug-162 只修了那条路），固定 10 类这条从来没有 | 在 `report_service._fetch_join_rows` 与 `_filter_spec` 复刻 builder 的写法，并在端点校验 `record_ids` 归属 | 本轮唯一的数据越权出口，且正确写法就在同一个代码库里 | apply-queue |
| 取数与落盘的契约矛盾 | #5, #20, #22 | 三者都在 collect/store 路径：硬性批量上限与承诺的 10 万行矛盾；分块 IN 循环把各块 AND 成空集；内容寻址的落盘并发冲突后回滚整个事务 | #5 先（用户可见的契约破裂，一行可修），再 #20，#22 的恢复路径需要重做 | 同一子系统、修复路径有重叠；#5 / #20 各只有几行 | apply-queue |
| 执行页轮询与拉取生命周期 | #7, #8, #10, #11 | 一个页面、一个共享 timer ref、没有取消令牌。#7 / #8 是两个 P1，#10 / #11 是拉取侧的后果 | #7 然后 #8，都收敛在 `poll()` 里；#11 需要产品裁决（清空临时过滤应代表什么）之后才能改代码 | 同一个函数、同一个文件，一个守卫同时解掉前两个 | apply-queue（#11 为 decision-gate） |
| 定义语义在保存与执行之间丢失 | #9, #19 | SortBy 的 direction 存了从不读；两份输出格式白名单不一致，csv 在一个端点能跑另一个不能 | 把 direction 透传到排序子句；两个端点读同一份白名单常量 | 都是「保存成功、执行时被忽略」，正是格式白名单 docstring 已经警告过的失败形态 | apply-queue |
| 迁移与数据库不变量 | #14, #15 | `p8_001` 建了一条 Postgres 对 NULL `project_id` 不生效的唯一约束；`downgrade()` 无条件 drop 四张表 | #14 用 `NULLS NOT DISTINCT`（PG 15+）或部分唯一索引，写成新 revision；#15 需要决定降级策略（拒绝，或先归档） | 两者一旦被人执行都不可逆；#15 改变的是运维被允许做什么 | #14 apply-queue；#15 decision-gate |
| 前端样式与过滤编辑器缺口 | #12, #25, #26, #30 | #12 已存在的样式无法修订而后端端点存在；#25 / #30 静默丢弃或改写过滤节点；#26 用数组下标当 key 而旁边就是上下移动按钮 | #26 是机械改动（稳定 key）；#25 / #30 需要裁决「大声拒绝还是静默修复」；#12 需要一个设计判断 | 四条里三条是一文件改动，真正的未决问题是预期行为而非代码 | #26 apply-queue；#12, #25, #30 decision-gate |
| 环境与规范债务 | #13, #16, #17, #18, #23, #24, #27, #28, #29 | 彼此无关的机械项：`pcs_test` 库落后、12 个 P8 修复没有 `docs/solutions/` 回写、同一路由两套错误信封、ACTIVE 样式不变量只在应用层、MSW mock 过期、状态筛选参数被后端忽略、两个小契约 nit | 一轮清完；没有一条阻塞任何东西 | 归在一起只因为它们都是「做完就走」的活，没有共同根因 | apply-queue |

### P0 -- Critical

| # | 文件 | 问题 | Reviewer | Confidence |
|---|------|------|----------|------------|
| 1 | `pcs-backend/app/services/report/report_service.py:163` | 固定 10 类导出无项目隔离：JOIN 行不加项目过滤，`record_ids` 归属从不校验 | adversarial-correctness | 100 |
| 2 | `pcs-backend/app/workers/report_tasks.py:249` | 回收器只 flush 不 commit，cron 每次回收都回滚 —— 回收器完全失效 | adversarial-reliability | 100 |

- **#1** —— `_fetch_join_rows` 没有 `scope` 参数、不加任何项目谓词；`_filter_spec` 唯一的谓词是对请求体里 `record_ids` 的 `IN`，而 `POST /report/generate` 只对 `body.project_id` 跑 `check_project_access_or_404`，随后把 `body.record_ids` 原样入队 —— 被校验的项目 ID 从未进入查询。后果：知道或猜到别的项目记录 UUID 的已认证用户，可以通过一个受支持的端点导出别的项目的行。正确写法就在 40 行外的 `builder_service._fetch_join_rows_with_scope`（bug-162 只修了那条路）。修复：给 `_fetch_join_rows` 与 `collect` 加 `scope` 参数并透传 `project_id`；同时在端点校验每个 `record_ids` UUID 的归属。验证者确认了每一行引用；**发生频率未实测**，代码允许该越权但没有证据表明它已在任何部署中发生。protected subject: authorization-authentication。
- **#2** —— `reclaim_stale_tasks`（:249）与 `reclaim_stale_execution_logs`（:307）都以 `await db.flush()` 结尾、无 commit；全模块最后一次 commit 在 :203（`generate_report_task` 内部）；cron 入口 `reclaim_stale_report_tasks`（:311-328）用 `_ctx_session` 取 session，只开不提交也不关闭。后果：每一次 FAILED 改判和每一条 REPORT_FAILED 审计行都在 session 释放时回滚，ARQ worker 崩溃后 `report_files` 永久停在 PENDING、`report_execution_logs` 永久停在 QUEUED/RUNNING，前端轮询看到的是一个永远不结束的挂起。测试把 fixture session 直接传进去（`tests/workers/test_report_tasks.py:306`），从不走 cron 包装，所以 CI 全绿。修复：在两个回收器末尾补 `await db.commit()`，并把 cron 入口换成 `worker.session_scope`（它保证 close）。protected subject: data-loss。

### P1 -- High

| # | 文件 | 问题 | Reviewer | Confidence |
|---|------|------|----------|------------|
| 3 | `pcs-backend/app/api/v1/report_builder.py:328` | 先入队后 commit 执行日志行，worker 回填丢审计、轮询 404 | api-contract-reliability | 100 |
| 4 | `pcs-backend/app/services/report/qr.py:43` | 二维码 URL 不带签名，`/report/verify` 每次扫码必然 403 | reliability | 100 |
| 5 | `pcs-backend/app/services/report/query_engine.py:297` | `assemble()` 硬编码 `batch_size=10000`，与对外承诺的 100000 行上限矛盾 | performance | 100 |
| 6 | `pcs-backend/app/workers/report_builder_tasks.py:83` | 成功执行从不写 `FINISHED`，回收器把已完成的审计行改判 FAILED | adversarial-reliability | 100 |
| 7 | `pcs-frontend/src/pages/report/ReportExecutePage.tsx:157` | 轮询无取消令牌，重跑或卸载会复活孤儿循环并覆盖新运行的状态 | julik-frontend-races | 100 |
| 8 | `pcs-frontend/src/pages/report/ReportExecutePage.tsx:161` | 轮询从不读 FAILED 终态，失败任务空转到假超时 | api-contract | 100 |

- **#3** —— `execute_definition_endpoint` 在 :328 入队、:348 才 `db.add(ReportExecutionLog)`、:368 才 commit。三个窗口：worker 可以先跑完并调用 `_link_report_file`，而那行还不存在，于是 `report_file_id` 回填丢失、`/report-builder/executions/{task_id}` 对一个已经产出文件的任务回答 404；若端点在 :368 前失败，则文件存在而审计行完全没有。`_link_report_file` 的 UPDATE 没有 rowcount 检查，丢得悄无声息。同特性的固定 10 类端点是对的做法（`report.py:157-166` 先建 PENDING 行并 commit，再入队）。修复：把 add+commit 提到入队之前，并把端点选的 task_id 传给 enqueue（`_job_id=task_id`），同时让 `_link_report_file` 在 UPDATE 命中 0 行时报错而不是静默降级。
- **#4** —— `build_qr_payload` 产出的 URL 不带 `sig` 也不带 `exp`，全后端 grep 不到第二个生产者（`hmac` 只出现在校验侧）；`_check_sig` 要求两者齐备，缺失即 `raise HTTPException(403, "签名无效")`。`report_service.py:220` 的渲染调用硬编码 `qr_payload=None`，所以 `renderer_pdf.py:256` 的 `if qr_payload:` 在生产路径永假。后果：印在报表上的二维码用于现场核验这条能力今天无法成功。修复需要两处协同：在 `report_service` 加签名器并把真实 payload 传进渲染，同时因为签名含时间戳、不能参与 `_content_hash`（否则破坏「同内容同哈希」的去重前提），`store_rendered` 的顺序要从「渲染 -> 哈希 -> 落盘 -> upsert」改成「先 upsert PENDING 行 -> 用它的 id 签名 -> 渲染 -> 落盘」。若签名 URL 只是推迟，则应把 `qr.py` 与 verify 路由一并删掉，而不是交付一个必然 403 的端点。protected subject: public-contract。
- **#5** —— `query_engine.assemble` 的 `batch_size` 默认 10000，超过即抛 `REPORT_JOIN_TOO_LARGE`；两个调用点（`builder_service.py:233`、`report_service.py:111`）都不传这个参数。100000 却在四处对外承诺：`schemas/report_builder.py:139/:165`、`definition_service.py:53`、`api/v1/report_builder.py:239`。用户把 `max_rows` 存成 10001..100000 之间，校验通过，执行时确定性 400 —— 正是格式白名单 docstring 警告的「保存成功、执行时才炸」。修复方向要先拍板：要么把 `limit` 透传进 `assemble`（承认构建器路径遵守每定义的 MaxRows，固定 10 类路径仍卡在 `report_service._MAX_ROWS`），要么把两处 `le=100_000` 降到 `le=10000`、让 schema 不再宣传一个无法执行的范围。protected subject: public-contract。
- **#6** —— `report_builder_tasks.py` 只在 :83 写 `RUNNING`、:113 写 `FAILED`，全 `app/` 没有任何地方写 `FINISHED`（模型注释 `models/report.py:211` 把它定义为终态，`api/v1/report_builder.py:296` 只能靠 `report_file_id is not None` 这个启发式倒推）。后果：一次成功出文件的执行 15 分钟后被 `reclaim_stale_execution_logs` 按 `QUEUED/RUNNING + 超时` 改判 FAILED 并在 `condition_snapshot` 里写入 `reclaimed_at` —— 写在一张模块自己声明为审计表、不容篡改的表上；轮询端点对真实产出了文件的工作报失败。**当前这条被 #2 掩盖（回收器不 commit，改判回滚）；只修 #2 不修 #6，就是把被掩盖的缺陷变成活跃的数据损坏。** protected subject: data-loss。
- **#7** —— `poll(id)` 在自己的 async 回调末尾重新武装自己，并写入单一共享的 `timer.current`；`stopPolling` 只清当前那一个句柄。`run()` 先 `stopPolling()` 再起新 `poll`，但若上一轮的 `await executionStatus` 已在飞行中，它随后会恢复、写 `statusText`、再 `poll(oldId)`，接管 `timer.current` —— 页面此后有两个活循环，最后 resolve 的赢 `fileId`，下载按钮可能指向上一轮的文件。卸载清理 `useEffect(() => stopPolling, [])` 有同一个洞：卸载时若状态请求在飞行中，那个回调会为一个已经不存在的组件重新武装定时器。执行按钮在 `phase === 'polling'` 期间没有 disabled，是这个重叠的触发器。修复：加一个 generation token（同一守卫也修 #10），并在轮询期间禁用按钮。
- **#8** —— `poll` 只判断 `st.report_file_id`，从不读 `st.status`；全文件没有一处引用 `st.status`。`p8_007` 迁移专门加了 `status` 列正是为了让「失败」与「运行中」可区分，后端也确实在 `report_builder_tasks.py:113` 写 FAILED。前端因此对一个已失败的任务持续轮询满 `POLL_TIMEOUT_MS`，然后弹出「文件可能仍在生成中」的超时提示 —— 恰好是 p8_007 docstring 要防的那个错误结论。修复：在 `poll` 里先按 `status === 'FAILED'` 分支（停止、报错、进入 failed 相），再走现有的 `report_file_id` 分支。

### P2 -- Moderate

| # | 文件 | 问题 | Reviewer | Confidence |
|---|------|------|----------|------------|
| 9 | `pcs-backend/app/services/report/builder_service.py:216` | 静默丢弃 SortBy 的 direction，永远升序 | correctness | 100 |
| 10 | `pcs-frontend/src/pages/report/ReportExecutePage.tsx:110` | 未取消的定义拉取会渲染错误的定义 | julik-frontend-races | 100 |
| 11 | `pcs-frontend/src/pages/report/ReportExecutePage.tsx:126` | 清空临时过滤会静默回退到定义里的原条件 | julik-frontend-races | 100 |
| 12 | `pcs-frontend/src/pages/report/ReportStylePage.tsx:219` | 已存在的样式无法编辑或修订 | julik-frontend-races | 100 |
| 13 | `docs/solutions/database-issues/alembic-create-table-silently-drops-schema-elements.md:1` | P8 期间 12 个修复没有 `docs/solutions/` 回写 | project-standards | 75 |
| 14 | `pcs-backend/alembic/versions/p8_001_report_tables.py:111` | 可空 `project_id` 让唯一约束在 Postgres 上失效 | data-migration | 75 |
| 15 | `pcs-backend/alembic/versions/p8_001_report_tables.py:136` | `downgrade()` 无条件 drop 四张表，销毁审计历史 | data-migration | 75 |
| 16 | `pcs-backend/alembic/versions/p8_007_execution_log_status.py:30` | `pcs_test` 落后开发库两个 P8 revision | project-standards | 75 |
| 17 | `pcs-backend/app/api/v1/report.py:118` | 同一路由混用 PcsError 与 HTTPException 两套错误信封 | api-contract | 75 |
| 18 | `pcs-backend/app/api/v1/report.py:347` | 项目级报表样式对任何已认证用户可读 | security | 75 |
| 19 | `pcs-backend/app/api/v1/report_builder.py:94` | 两份输出格式白名单不一致：generate 拒 csv，execute 收 csv | api-contract | 75 |
| 20 | `pcs-backend/app/services/report/report_service.py:173` | 分块 IN 循环复用被改写的 statement，各块 AND 成空集 | performance | 75 |
| 21 | `pcs-backend/app/services/report/report_service.py:419` | REPORT_GENERATED 审计写失败被吞，文件存在而无审计记录 | security | 75 |
| 22 | `pcs-backend/app/services/report/report_service.py:444` | 并发同内容导出在落盘处相撞，IntegrityError 恢复回滚整个事务 | reliability-adversarial | 75 |
| 23 | `pcs-backend/app/services/report/style_service.py:151` | revise/activate 的「至多一个 ACTIVE」只在应用层保证 | correctness | 75 |
| 24 | `pcs-frontend/src/mocks/reportBuilder.ts:70` | MSW mock 落后于契约：joins / model / file status 字段都对不上 | api-contract | 75 |
| 25 | `pcs-frontend/src/pages/report/definitionBody.ts:263` | `toFilterTree` 静默丢弃无法解析的过滤节点 | julik-frontend-races | 75 |
| 26 | `pcs-frontend/src/pages/report/FilterTreeEditor.tsx:100` | 用数组下标当 key，而旁边就是上下移动按钮 | julik-frontend-races | 75 |
| 27 | `pcs-frontend/src/pages/report/ReportDefinitionListPage.tsx:70` | 状态筛选参数后端不接收，筛选看起来坏了但无报错 | api-contract | 75 |

- **#11（需裁决）** —— `!tempFilters?.length ? undefined : ...` 把 `null`（用定义里的条件）与 `[]`（用户删光了所有条件）压成同一个值，于是「显式清空」静默回退到定义自带的过滤。UI 在说谎：`FilterTreeEditor` 对空节点列表渲染「无过滤条件 —— 执行时将导出全量」，而唯一会说明真相的 `tempFilters === null` 提示恰好对 `[]` 不显示。前端往返测试「drops nothing when the tree is emptied deliberately」恰恰把 `[]` 钉成一个有意义的独立状态，执行路径把这个区分丢掉了。**需要 spec owner 一句话裁决**：清空临时过滤到底该表示「不筛选」还是「继承定义」，定了再让三处（:126、FilterTreeEditor 文案、:267 的提示）一致。
- **#12（需裁决）** —— `startEdit` 两个调用点都传 `null`，所以 `editing` 永远是 null，`submit` 的修订分支和「修订（基于 vX）」卡片标题都是死代码；再叠加 `新建样式` 的 `disabled={!!active}`，一旦该作用域已有 ACTIVE 样式，唯一入口被禁用、修订路径不可达 —— 用户无法修改一个已经存在的样式。修复：在版本历史表加一个「基于此版本修订」按钮调用已有的 `startEdit(r)`，并让 `renderEditor` 在 `editing` 有值时从 `editing?.style` 回填。是否把修订放在这一页上，是一个产品判断。
- **#13** —— 根 `CLAUDE.md` 要求「新增解法后回写一份，别只留在提交信息里」，而 `git diff --stat cfc0f2e..HEAD -- docs/solutions/` 为空。P8 这个窗口落了 12 个修复（提交主题点名 bug-150..168），其中至少两类是非显然的框架行为：ARQ 的 cron ctx 与 session 之别、审计表不得删行。成本是具体的：下一个人会再踩一次。缓解证据（因此不是 P0）：同样的解法已带全部五个字段记录在 `.wolf/buglog.json`（bug-157..168，各带 7 位 `fix_commit`）与 `TODOS.md` 里，知识并没有只困在提交信息中。修复：在 `docs/solutions/` 下补一篇 ARQ/worker 家族的文件，合并四条可复用规则（ARQ 只对自己的可重试异常类型重试；enqueue 传函数名字符串；任务必须在 finally 里关 session；CronJob 的 second=None 是每秒而非不限）。
- **#14** —— `report_definitions.project_id` 可空，而表上带 `sa.UniqueConstraint("project_id", "name", ...)`。Postgres 默认认为 NULL 互不相同，于是两个公司级定义（`project_id IS NULL`）可以同名共存，尽管 `builder_service.py:177-180` 把「没有 project_id」当作公司级模板作用域。修复：给该约束加 `postgresql_nulls_not_distinct=True`（PG 15+，仓库跑的是 18），并在 `app/models/report.py` 的镜像约束上加同样的 dialect 选项。**注意**：单测用 SQLite 建表，该 dialect 选项在 SQLite 上不生效，所以这个守卫的测试仍应落在 service 层。
- **#15（需裁决）** —— 合并阶段已修正：`p8_001` 丢弃遗留报表表是 2026-10-08「就地改造、不并存两套报表定义概念」的用户裁决，不是缺陷，不作发现上报。存活下来的是另一半：`downgrade()`（:136-139）无条件 drop 全部四张表，包括代码自己称为审计表的 `report_execution_logs`。降级会无守卫、无备份地销毁合规记录。修复：drop 前加非空守卫（非空则 raise 并报出行数），并在任何非全新库上跑 upgrade 之前先 `\copy` 导出遗留行。降级策略本身（拒绝，还是先归档）是运维决策。
- **#16（需人执行）** —— 开发库 `pcs` 在 p8_007，`pcs_test` 仍停在 p8_005。`CLAUDE.md` 点名这正是漂移困惑的标准来源；单测跑内存 SQLite，`pcs_test` 只在有人刻意验证「迁移在另一个库上也成立」时才用 —— 那时它会骗人。修复是跑 `DATABASE_URL=<pcs_test DSN> uv run alembic upgrade head`。这是数据库状态动作、无仓库改动，必须由人执行，不作为自动修复。
- **#17（需裁决）** —— 一个新路由里错误以两种形状返回：`PcsError` 出 `{code, message}`，11 处 `HTTPException` 出 FastAPI 的 `{"detail": ...}`。前端唯一的错误翻译 `reportBuilder.ts` 的 `errorMessage()` 只读 `data.message` / `data.code`，于是「文件已被清理」「无权读取该样式」这类可操作文案永远到不了屏幕，用户只看到 `Request failed with status code 404`。状态码是一致的，只有响应体形状不同 —— 而这恰恰是客户端最难抽象的那一半。修复是把这些点转成带独立 code 的 `PcsError`，但它会改变已合并端点的响应体，需要一次有意识的发布决策。
- **#18（需裁决）** —— `_style_readable` 对所有 `project_id` 非空的行直接返回 True，只对公司级样式卡 `SYSTEM_ADMIN`；`list_styles` 在 Python 侧逐行过滤。**评审者的严重度已修正**：这是有意的取舍（docstring 明确说明写路径的不对称是刻意的，为避免每行一次 `UserProject` 查询），不是疏忽，所以是 P2 而非 P1。暴露的是样式 JSON（字体、版式、明细档位），不是项目业务数据。修掉它需要一次 join 或一份缓存的可访问 project 集合；另一条路是把「样式配置跨租户非敏感」这个决策写下来，并用一条断言该泄漏的测试钉住。
- **#19** —— `schemas/report.py:28` 的 `SUPPORTED_OUTPUT_FORMATS = ("pdf","xlsx","docx")` 让 `POST /report/generate` 拒掉 csv，而 `_reject_bad_format` 校验的 `watermark.EXPORT_FORMATS` 含 csv；两条路其实都能渲染 csv（`_render_sync` 会分派到 `render_csv`），所以 generate 上的拒绝才是异常项。修复：让 `SUPPORTED_OUTPUT_FORMATS` 从 `watermark.EXPORT_FORMATS` 派生，并给两个请求 schema 声明 `Literal[...]` 让枚举出现在 OpenAPI 里；顺带补上 `report.py:420-422` 的 `_MEDIA` 缺失的 csv 条目（否则 csv 会以 `application/octet-stream` 下载）。
- **#20** —— `_fetch_join_rows`（:171-176）在分块循环里 `stmt = stmt.where(...)`，改写累加器。第 1 块之后 statement 已带 `key IN (chunk1)`，第 2 块把 `key IN (chunk2)` AND 上去，于是返回各块的交集（空集）。跨过 `_BATCH_SIZE` 个 key 的 join 会静默返回零行而不是报错。当前常量下 `len(keys) <= 10000` 恰好只跑一轮，所以是潜伏缺陷。修复：照抄 `builder_service.py:135` 的正确写法，每块把谓词传给 execute 而不改写 `stmt`；测试请 monkeypatch 把 `_BATCH_SIZE` 调小，不要真造几万行。
- **#21** —— `store_rendered` 写文件、upsert `ReportFile` 行，然后把 `REPORT_GENERATED` 审计写包在 `try/except Exception` 里只记 warning。内联注释关于「不回滚」的判断是对的，但漏了另一半：审计写失败时报表存在于 `report_files` 而没有对应的 `REPORT_GENERATED` 行，调用方拿到的是正常成功。对一个审计轨迹就是合规产物的系统，这个缺口至少该入队重试或升级到日志以上的级别。修复：把刚写的文件标记隔离（挪走）并以 5xx 上浮，让调用方对着健康的审计通道重试；配一个启动期金丝雀写入。
- **#22** —— 三件耦合的事实：(1) 文件路径是内容寻址的（`new_file_path(digest, ...)`），两个渲染相同内容的 worker 会指向同一路径与同一临时文件，`_write_file` 又在 `asyncio.to_thread` 里跑，所以交错是真实的；(2) `_upsert_report_file` 的 `IntegrityError` 恢复调用 `await db.rollback()`（:444），回滚的是调用方的整个事务，不只是这条插入；(3) 恢复用的 select 随后跑在一个事务已回滚的 session 上，而磁盘文件可能已写。净效果：磁盘孤儿文件、事务部分丢失、IntegrityError 仍可能上浮。P2 而非更高，因为需要两次同时的相同导出。修复：`tmp` 用 `O_CREAT | O_EXCL` 独占打开，第二写者快速失败，由去重层决定删除还是复用；恢复路径重做为语句级 savepoint。
- **#23（需裁决）** —— `create` / `revise` / `activate` 都用普通 select 读当前 ACTIVE 行再决定是否报错；数据库上没有「每个作用域至多一个 ACTIVE」的部分唯一索引（唯一的只有 scope+version）。两个并发请求都能通过检查并各自插入，于是 docstring 声明为绝对的不变量只在调用方不重叠时成立。修复：加 `CREATE UNIQUE INDEX ... ON report_styles (report_type, COALESCE(project_id, '0000...')) WHERE status = 'ACTIVE'` 并处理 IntegrityError；部分唯一索引同时覆盖 `revise` 与 `activate`，比跨审计写持行锁干净。
- **#24** —— 三处 fixture 与已提交契约不符：(1) `joins` 用 `{left, right, left_key, right_key}`，而 `ReportBuilderJoin` 是 `{a, a_field, b, b_field, degrade_warn}`，`availableJoins` 按 `j.a`/`j.b` 过滤，dev 下 JOIN 选择器永远为空、`JoinPicker.tsx:65` 会渲染 `(undefined = undefined)`；(2) 每个数据源都缺 `model` 这个必填字段；(3) `/report/{id}/status` 返回 `content_hash`、`has_assumption_page`、`created_at`，`ReportFileStatusResponse` 上都没有。由于 dev 登录走 MSW，整个报表 UI 就是对着这些 payload 开发和 QA 的 —— mock 契约漂移会隐藏真实断裂、还会验证一个已不存在的契约。修复：把 fixture 字面量按 OpenAPI 类型标注，让 TypeScript 在编译期就拒绝错误形状；注释不会活过下一次契约变更。
- **#25（需裁决）** —— `toFilterTree` 对任何不是对象、没有 `conditions` 数组、或 `field`/`operator` 不是字符串的节点返回 `[]`，`buildBody` 随后把幸存者持久化。这正是该模块自己声明为硬要求要防的 TODO-060 失败形态（「往返无损是硬要求」，:256）：打开一个含有一条当前前端无法识别的条件的定义，改一个无关字段，保存，那条条件就没了、且无任何提示。邻近代码明确表态静默归一化不可接受（`FilterTreeEditor` 故意放行空值，好让后端抛 `REPORT_FILTER_VALUE_MISSING` 而不是悄悄导出全表）。修复：让丢弃可见 —— 导出 `unparsedFilterNodes(raw)`，页面上渲染一条 Alert「本定义含 N 条本页无法识别的条件，保存时会丢弃」，非空时阻止或确认保存。选「警告」还是「修复」取决于后端当前 schema 是否真能发出这种节点。
- **#26** —— 行与嵌套条件都用 `key={i}` 渲染，而这个编辑器旁边就有「上移 / 下移」按钮 —— 正是 `definitionBody.ts:36-43` 记录为「已经在同族字段表上造成过真实 bug」的组合，也正是 `FieldRow` 带稳定 `key`、`toRows` 生成 `row-${i}-${source}.${field}` 的原因。值都是受控的，可见内容不会错；剩下不受控的是 antd `Select mode="tags"` 的内部搜索文本与展开态：在第 0 行的 tag 输入里打几个字符但不按回车，直接点上移，现在渲染第 1 行的那个组件实例仍持有那些字符。修复：给 `FilterLeaf`/`FilterGroup` 加 `id`，按 `node.id` 作 key，复用 `toRows` 的计数器做法。
- **#27** —— 前端把选中的状态作为查询参数发出，后端 `list_definitions` 根本没有声明任何 Query 参数。FastAPI 静默忽略未知查询参数，于是请求成功（200）并返回全部可见定义；用户选「已发布」看到表格过了一次 loading 又把 DRAFT 和 OBSOLETE 一起列出来 —— 筛选看起来坏了，而任何地方都没有错误。旁边那个关键字框有注释说明是前端过滤，页面已经确立了「部分筛选是本地做的」这个约定，状态下拉静默违反了它。修复：从 `reportBuilderApi.list` 去掉 `params`、在既有 `visible` useMemo 里按 `r.status === statusFilter` 过滤，与关键字一致；另一条路是给端点补 Query 参数加分页，是更大的契约变更且需要重新定义 `total`。

### P3 -- Low

| # | 文件 | 问题 | Reviewer | Confidence |
|---|------|------|----------|------------|
| 28 | `pcs-backend/app/api/v1/report_builder.py:268` | `ReportExecutionStatus.status` 声明为 `str`，docstring 漏掉 FAILED | api-contract | 75 |
| 29 | `pcs-backend/app/core/config.py:169` | `report_verify_secret` 长度未在配置加载时约束 | security | 75 |
| 30 | `pcs-frontend/src/pages/report/definitionBody.ts:275` | `toFilterTree` 给缺 `source` 的条件伪造默认数据源 | api-contract | 75 |

- **#28** —— 已发布的状态词表在字段注释里写作 `QUEUED / RUNNING / FINISHED`，但 FAILED 可达，而且它正是这一列存在的理由（TODO-064）。类型是裸 `str`，OpenAPI 里就没有 enum，生成客户端既无法枚举状态、也无法把新终态与未知值区分开；照三种状态写的客户端会把 FAILED 当成「还在跑」—— 就是上面轮询那条缺陷的上一层。改成 `Literal["QUEUED","RUNNING","FINISHED","FAILED"]` 即可把词表放回契约里。注意 FINISHED 目前只由端点合成、从不写入列（见 #6），所以也要顺带确认终态成功是否应该落库而不是从 `report_file_id` 倒推。
- **#29** —— 启动校验（:169-176）只检查密钥非空，没有最小长度检查。运维设成一个字符的 `REPORT_VERIFY_SECRET` 也能正常启动，HMAC 于是可被暴力穷举。dev 自动填充用 `secrets.token_urlsafe(48)`（约 384 位），但 1 字节密钥能通过同一个检查。这个端点对「缺配置」是 fail-closed，对「弱配置」却是 fail-open。修复：在 dev 自动填充之前加长度下限校验（32 字节是 HMAC-SHA256 的常规下限）。
- **#30** —— 条件节点缺失 `source` 时（旧的已存定义、手工改过的 payload、部分迁移的记录），加载器替换成字面量 `'EQUIP_LIST'` 而不是拒绝或标记。页面于是把该条件显示为属于设备清单，保存又把 `'EQUIP_LIST'` 写回定义体 —— 对已存的查询条件做了一次无声的语义改写，而用户完全不知道这个过滤现在指向另一张表。`asSingleFilter` 在 :312 有同一个兜底。既然模块目标是「与 `toFilterTree` 严格互逆」，伪造 source 破坏的正是那个会改变报表含义的方向。修复：删掉这个默认值 —— 要么丢弃该节点（与 :263、:272 的既有防御风格一致），要么作为显式非法节点呈现给编辑器报错。


### Requirements Completeness

计划：`docs/superpowers/plans/2026-10-08-p8-report-and-report-builder.md`（explicit）。

| 单元 | 状态 | 依据 |
|------|------|------|
| Task 1 样式层 `ReportStyle` | met | `app/services/report/style.py` + `tests/services/report/test_style.py` |
| Task 2 迁移 + ORM | met | `p8_001_report_tables.py` + `app/models/report.py` |
| Task 3 PDF 渲染器 | met | `renderer_pdf.py`、`blocks.py`（三渲染器共用的中间表示）+ `test_renderer_pdf.py` |
| Task 4 DOCX / XLSX 渲染器 | met | `renderer_docx.py`、`renderer_xlsx.py` + `test_renderers.py` |
| Task 5a 数据源注册表 | met | `datasource_registry.py` + `test_datasource_registry.py` |
| Task 5b query_engine + 10 类 collector | met | `query_engine.py`、`collector.py` + `test_query_engine.py`、`test_collector.py` |
| Task 6 二维码 + 生成编排 + 文件存储 | partially addressed | 产物都在，但 #4：二维码从不携带签名，现场核验这条验收无法成功 |
| Task 7 ARQ 异步任务 + 状态查询 | partially addressed | #2 / #3 / #6：终态状态机、commit 边界、入队与审计行的先后都未按计划成立 |
| Task 8 API 路由 | partially addressed | #1：`/report/generate` 的项目访问校验未约束到实际读取的行；#17：错误信封两套并存 |
| Task 9 测试 seed + Golden | met | `test_golden.py`（比归一化文本，规避 bug-155 的随机 `/ID`）+ `tests/fixtures/report/seed.py` |
| Task 10 性能基准 | met | `tests/benchmarks/test_report_perf.py`（绝对阈值，非相对基准） |
| b1 数据源注册表 API | met | `GET /report-builder/datasources` 返回字段树 |
| b2 定义 CRUD | met | 4 个定义端点 + `ReportDefinition` 模型 |
| b3 版本与审批 | met | `publish_definition` / `obsolete_definition`，5 态流转 |
| b4 字段选择器后端 | partially addressed | #9：`SortBy.direction` 存进 `definition_json` 后从不读，「往返一致」不成立 |
| b5 过滤条件引擎（15 操作符 / AND-OR 嵌套） | met | 15 个操作符全部实现且逐个有测试；仅 JSONB `->>` 分支缺端到端覆盖（见 Testing gaps） |
| b6 JOIN 引擎（白名单 5 对） | met | 白名单 + `REPORT_BUILDER_JOIN_NOT_SUPPORTED` |
| b7 执行引擎（ARQ 异步，202 + task_id） | partially addressed | 202 + task_id 已成立；#3 / #5 / #6 使「条件快照写 `report_execution_logs`」与临时行上限两项验收在特定情形下不成立 |
| b8 导出 + 水印 + DEMO 限 3 | partially addressed | 水印与 `DEMO_MAX_DEFINITIONS = 3` 成立；#19：csv 在固定 10 类端点被拒 |
| b9 审计 `REPORT_EXECUTED` | met | `report_builder_tasks.py:134` 每次执行写审计，含条件快照 |
| b10-b12 前端三件套 | partially addressed | 定义编辑器 / 执行面板 / 管理列表三个页面均已落地并可达；#7 / #8 / #11 / #24 / #27 是页面内的验收级缺陷 |
| c1 HEAT 字段映射 | met | `test_heat_datasource.py`、`ache_params` JSONB 键测试 |
| c2 BASIC / DETAIL 双样式 | met | `test_detail_level_styles.py` |
| c3 ADR-0028 | met | 计划记录为已完成，见 `docs/adr/HEAT 报表双 detail_level 模板裁决.md` |
| c4 HTRI 兼容测试 | met | `121-A-101.xls` / `131-E-102-EOR.xls` 模板元数据 + parser 测试 |
| c5 覆盖率报告 + 回归闸 | met | `scripts/report_heat_coverage.py` + `tests/scripts/test_report_heat_coverage.py`（基线 + 2pp 容差，按 ADR 修订放弃追覆盖率） |
| c6 样式管理 UI | partially addressed | 页面存在，但 #12：已存在的样式无法编辑或修订，编辑入口与后端端点均不可达 |
| c7 JOIN 扩展 | met | 「按需开放」无固定验收缺口，`JoinPicker.tsx` 已交付 |

**反查（计划未要求、diff 却引入的行为）：**

- `/report/verify` 免登录端点 + 进程内限流（`check_rate_limit`）：计划 Task 6 只写「二维码」，签名校验与限流的具体形态不在计划内。这是加固而非需求，但它也把进程内 dict 的局限一并带进了 P8 面（见 Residual risks 第 11、12 条）。
- `p8_003` / `p8_004` 为 `heat_results` 加的 7 列当前没有写入方 —— 写入随 HTRI 解析器尚未落地，属计划 c1 的提前铺路，不算未请求行为，但部署期需知情（见 Deployment Notes）。
- 计划「尚未解决的问题」第 7 条（JSONB 子键与实际结构的一致性检查）仍开放，TODO-026 展开后才自动获得平铺字段。

### Actionable Findings

以下 22 条归 `downstream-resolver`（`gated_auto` 或 `manual`），全部带 `suggested_fix`。本次调用 `mode.apply_local = false`，**未应用任何修复**。

| # | 文件 | 问题 | Route | 备注 |
|---|------|------|-------|-------|
| 1 | `pcs-backend/app/services/report/report_service.py:163` | 固定 10 类导出缺项目隔离 | `gated_auto -> downstream-resolver` | 唯一 P0 数据越权路径；修复模式已在同库存在 |
| 2 | `pcs-backend/app/workers/report_tasks.py:249` | 回收器不 commit | `gated_auto -> downstream-resolver` | **必须与 #6 同批落地**，单独修会把 #6 变成活跃损坏 |
| 3 | `pcs-backend/app/api/v1/report_builder.py:328` | 入队先于审计行 commit | `gated_auto -> downstream-resolver` | 照抄 `report.py:161-190` 的现成顺序 |
| 4 | `pcs-backend/app/services/report/qr.py:43` | 二维码缺签名，verify 必然 403 | `gated_auto -> downstream-resolver` | 或整体删掉 `qr.py` + verify 路由 |
| 5 | `pcs-backend/app/services/report/query_engine.py:297` | `batch_size=10000` 与 10 万行承诺矛盾 | `gated_auto -> downstream-resolver` | 一行可修，但先要定方向（透传 limit 还是降 schema 上限） |
| 6 | `pcs-backend/app/workers/report_builder_tasks.py:83` | 成功路径从不写 FINISHED | `gated_auto -> downstream-resolver` | 与 #2 同批 |
| 7 | `pcs-frontend/src/pages/report/ReportExecutePage.tsx:157` | 轮询无取消令牌 | `gated_auto -> downstream-resolver` | 与 #10 同一守卫 |
| 8 | `pcs-frontend/src/pages/report/ReportExecutePage.tsx:161` | 轮询从不读 FAILED | `gated_auto -> downstream-resolver` | 与 #7 同函数 |
| 9 | `pcs-backend/app/services/report/builder_service.py:216` | SortBy direction 被丢弃 | `gated_auto -> downstream-resolver` | 建议同时在 validate_definition 拒绝非法方向 |
| 10 | `pcs-frontend/src/pages/report/ReportExecutePage.tsx:110` | 定义拉取未取消 | `gated_auto -> downstream-resolver` | 与 #7 同一守卫 |
| 13 | `docs/solutions/database-issues/alembic-create-table-silently-drops-schema-elements.md:1` | 12 个 P8 修复无 solutions 回写 | `gated_auto -> downstream-resolver` | 一篇 ARQ/worker 家族文件即可 |
| 14 | `pcs-backend/alembic/versions/p8_001_report_tables.py:111` | NULL 下唯一约束失效 | `gated_auto -> downstream-resolver` | 新 revision，`NULLS NOT DISTINCT`（PG 18 在位） |
| 19 | `pcs-backend/app/api/v1/report_builder.py:94` | 两份格式白名单不一致 | `gated_auto -> downstream-resolver` | 顺带补 `_MEDIA` 的 csv |
| 20 | `pcs-backend/app/services/report/report_service.py:173` | 分块 IN 循环 AND 成空集 | `gated_auto -> downstream-resolver` | 照抄 `builder_service.py:135` |
| 21 | `pcs-backend/app/services/report/report_service.py:419` | 审计写失败被吞 | `gated_auto -> downstream-resolver` | 隔离文件 + 5xx 上浮 |
| 22 | `pcs-backend/app/services/report/report_service.py:444` | 并发落盘相撞 + 全事务回滚 | `gated_auto -> downstream-resolver` | 恢复路径需要重做 |
| 24 | `pcs-frontend/src/mocks/reportBuilder.ts:70` | MSW mock 落后于契约 | `gated_auto -> downstream-resolver` | 按 OpenAPI 类型标注，让 TS 编译期拦截 |
| 26 | `pcs-frontend/src/pages/report/FilterTreeEditor.tsx:100` | 下标 key + 移动按钮 | `gated_auto -> downstream-resolver` | 加 `id` 字段，改 key |
| 27 | `pcs-frontend/src/pages/report/ReportDefinitionListPage.tsx:70` | 状态筛选参数被忽略 | `gated_auto -> downstream-resolver` | 与关键字一致，改前端过滤 |
| 28 | `pcs-backend/app/api/v1/report_builder.py:268` | status 无 enum、漏 FAILED | `gated_auto -> downstream-resolver` | 改 `Literal[...]` |
| 29 | `pcs-backend/app/core/config.py:169` | verify secret 无长度校验 | `gated_auto -> downstream-resolver` | 32 字节下限 |
| 30 | `pcs-frontend/src/pages/report/definitionBody.ts:275` | 伪造缺省 source | `gated_auto -> downstream-resolver` | 与 :263 / :272 的丢弃风格对齐 |

**需人工裁决（`owner: human`，不在 apply 队列内）：** #11（清空临时过滤的语义）、#12（修订是否放在样式页）、#15（降级策略）、#16（`pcs_test` 对齐，需人执行数据库动作）、#17（错误信封统一属发布决策）、#18（样式跨租户可读是有意取舍）、#23（ACTIVE 不变量下沉到 DB 还是加行锁）、#25（无法解析的过滤节点：警告还是修复）。

### Pre-existing Issues

以下问题存在于本 diff 之外，不计入 verdict，但因 P8 契约扩张而依赖它成立。

| # | 文件 | 问题 | Reviewer |
|---|------|------|----------|
| P1 | `pcs-frontend/scripts/check-api-drift.sh:64` | 漂移闸只比较 `required`，不比较属性类型变化与属性删除 | api-contract |

头部注释声称能检测「字段类型变更 / 字段删除（BREAKING）/ 枚举值删除（BREAKING）」三项，实现却只比较 path 增删、schema 名删除与 `required` 数组。一个属性从既有 schema 里被删掉、类型被改窄或枚举成员消失，都能过闸并让 CI 变绿，而 `src/types/api.d.ts` 仍声明旧形状。P8 正是这类漂移已经发生过的地方：`ReportFileStatusResponse` 不再带 `content_hash` / `has_assumption_page` / `created_at`（它们仍在 MSW fixture 里，见 #24），闸门从未报过。

### Deployment Notes

来自 deployment-verification reviewer，目标环境为开发库 `pcs` 的实测状态（2026-10-14）。**这是一次重新执行的部署，不是首次部署** —— 开发库已在 `p8_007`，`alembic check` exit 0 无漂移。

**Go / No-Go 前置检查（阻塞项）：**

- #1 `uv run alembic current && uv run alembic heads` —— 期望 `current = p8_007 (head)`，任何分歧即 STOP。按 `CLAUDE.md`，一个已提交但未应用的迁移会直接堵死 `alembic check`，所以「check 通过」可能意味着「根本没跑」。
- #2（CRITICAL）**验证 p8_007 的 backfill 真的填了行。** `UPDATE ... WHERE status IS NULL` 只在「列由本版迁移新增」的库上正确。若任何环境跑过一个已带 `DEFAULT 'QUEUED'` 的早期 p8_007，已有行非 NULL -> backfill 命中 0 行 -> 已成功的执行永远停在 `QUEUED`，且会被回收器改判 `FAILED`。`ADD COLUMN IF NOT EXISTS` 在这种情况下是静默 no-op，而 `alembic current` 仍读 `p8_007`。**当前开发库 `report_execution_logs` 总数为 0，这个 backfill 在任何环境都从未被真实数据检验过。**
- #4（CRITICAL）**`p8_001` 是破坏性的，确认不会被重跑。** 它是 `drop_table(if_exists=True)` x 4 再 `create_table`。只要它是链首且只跑一次就是安全的；任何人执行 `alembic downgrade p7_s5_008` 再 upgrade，或某个 staging 库被 stamp 到 `p7_s5_008` 而 `report_definitions` 里已有真实 P8 行，就是一次全量数据抹除。**开发库现存 8 行 `report_definitions`（6 PUBLISHED / 2 DRAFT）+ 2 行 `report_styles`。**
- #6 仓库内任何地方都没有设置 `lock_timeout` / `statement_timeout`（`alembic.ini`、`env.py`、`.env` 全部干净）。一个被阻塞的 `ALTER` 会无限等待并把后续查询堵在队列里。
- #7 确认磁盘 / worker / 队列已静默（`redis-cli ping` 应为 PONG；`var/reports` 实测 323 个文件）。**STOP 条件：迁移期间有活着的 worker。**

**最重要的验证查询：** 部署前 #3 保存基线计数（`report_definitions` / `report_styles` / `report_files` / `report_execution_logs` / `heat_results` / `audit_logs`）；部署后跑 G1-G8（`alembic_version` 为 p8_007；`alembic check` 且**退出码为 0 而非 1**；`report_definitions` 有 14 列 —— 看到 `report_id` 或 `query_json` 说明 p8_001 没跑；`report_execution_logs.status` 的 `is_nullable` 必须是 **NO** —— 这是 p8_007 `SET NOT NULL` 已生效的健康态（2026-10-14 在 `pcs` 与 `pcs_test` 双库实测为 `NO | 'QUEUED'::character varying`）；若为 YES 说明某个早期 revision 已加过列却没补上约束，立即 STOP）。

**回滚注意：** **`alembic.ini` 与 `env.py` 都没有设 `transaction_per_migration`**，Alembic 默认是整个 `upgrade head` 一个事务，所以链中任一失败是七个一起回滚 —— 中途失败不是紧急回滚场景。**从部署前 dump 恢复严格优于 `alembic downgrade`** —— 本链的每一个 downgrade 都是破坏性的，p8_001 的 downgrade 直接 drop 四张表。`downgrade p7_s5_008` 之后的重新 upgrade 会重跑 p8_001 的 drop+create，**只有表空了才安全**：若你从 dump 恢复了行但没有 downgrade，那次重新 upgrade 会把它们抹掉。报表子系统还**没有滚动部署窗口**（`report_definitions` 的主键从 `report_id` 变为 `def_id`，任何仍跑旧 ORM 的进程都会报 `column "report_id" does not exist`），静默步骤是强制项而非建议项。

**监控重点（首 24 小时）：** 回收器注册在 `minute={3, 33}`（`worker.py:158-179`），阈值 `STALE_MINUTES = 15`，检测延迟 15-45 分钟。三个告警：(1) `condition_snapshot ? 'reclaimed_at'` 命中即为回收器所写、不是真实渲染失败，修复时要用逐条审核过的 `UPDATE ... SET status='FINISHED' WHERE log_id IN (...)`，不能整体回退；(2) 任何超过 15 分钟的 PENDING `report_files`（`DELETING` 是三步删除的中间态，回收器有意跳过）；(3) `audit_logs` 中 `REPORT_FAILED` 的 `attempt_no > 3` 即意味着 `max_tries` 不等于 3。

**缺失的检查项：** p8_007 的 backfill 在任何环境都没有对非空数据检验过；没有任何测试钉住 p8_007 的部分执行场景；p8_005/006/007 的 `CREATE INDEX` 不是 `CONCURRENTLY`，而 `report_execution_logs` 是不裁剪的审计表（要么改 `CONCURRENTLY` —— 与单事务默认不兼容，需要一次明确的设计决定 —— 要么书面接受一次维护窗口）；没有 `lock_timeout`；报表子系统无滚动部署路径这件事没有写下来；部署后没有验证回收器自身写入是否正确（`reclaim_stale_execution_logs` 会**改写 `condition_snapshot`**，往本应可复现的记录里塞 `reclaimed_at` / `reclaim_reason`）。**两个待部署负责人回答的问题：**(1) 这次到底部署到哪个环境？开发库已干净地在 p8_007，若是某个从未跑过 p8_001 的库，上面第 4 项的数据丢失分支就是活的，dump 是强制的。(2) 有没有环境还带着 p8_001 之前遗留的 `report_definitions` 行？p8_001 的 docstring 断言那些是 0 行空壳 —— **那个断言就是整个破坏性写法的全部安全依据。**

### Coverage

- **模式：** markdown report-only。`mode.apply_local = false`，Stage 5c 未授权，**本轮未修改任何文件、未应用任何修复**（Applied 数量 0）。
- **深度：** full。11 位 reviewer 独立工作（roster 见头部），无 reviewer 失败或超时。
- **标准来源：** instruction-file fallback —— 仓库无 `CODING_STANDARDS.md`，取根 `CLAUDE.md`（92 行）+ `.claude/rules/openwolf.md`。仓库亦未解析到任何 Compound Pack（`packs.roots` 为空）。
- **跨模型对抗复核：未运行。** 本机 host family 自报 claude，唯一已安装的同级 CLI 同样是 claude，不存在异 provider 的对等通道。对抗视角由进程内 `adversarial` reviewer 承担，其 5 条发现已全部并入本次评审（落在 #1、#2、#6、#22）。无遗留 peer job 目录。
- **范围收窄：** base `cfc0f2e`..head `a9ccb84` 的窗口内还含 P7 heat/calc 的工作，审查集收窄到 `files.txt` 的 46 个 P8 文件。未跟踪文件已排除；工作树即被审 head。
- **验证批次（Stage 5b）：** 一个批次，8 条选中（#1-#8，即全部 P0/P1），verdicts 在等待上限内落盘（`outcome = verdicts`）。**confirmed 8 / rejected 0 / unresolved 0 / malformed 0 / failed 0 / shortcut-skipped 0。** 没有任何发现满足 shortcut 条件（peer 未运行，同模型互相印证不构成 shortcut 依据），8 条全部送验。逐条验证者复核了全部引用行号，无一处偏差。
- **受保护主题：** #1 `authorization-authentication`、#2 `data-loss`、#6 `data-loss`、#4 与 #5 `public-contract`。因为没有拒绝，不存在「受保护主题重新分类」的情形。
- **confirmed 但发生频率未实测：** #1（验证者原话：代码允许该越权，但没有证据表明它在任何部署中发生过）—— 报告中标为「代码允许、无人证明已发生」。
- **被上游修正、不得复活的两条 reviewer 断言：** (a)「15 个过滤算子全部只做编译检查、从不执行」**不成立** —— 15 个在 `tests/` 中逐个出现（IN 26、GT 14、EQ 12、LT 6、IS_NULL 5、BETWEEN 3、IS_NOT_NULL 3、NEQ 2、NOT_IN 2、CONTAINS 2、LIKE 2、STARTS_WITH 1、ENDS_WITH 1、GTE 1、LTE 1），保留下来的只有收窄后的形式；(b)「JSONB `->>` 路径在 Postgres 上是生产 500」**未证实** —— `->>` 是合法 PG 语法，且 `tests/conftest.py:51,101` 有 SQLite 垫片。
- **合并阶段的其他修正：** 项目级样式可读性已从 P1 降为 P2 并作为设计取舍陈述；PDF 渲染器并未 import 它所复制的那份 helper，而是定义了一份私有副本；前端操作符分类法出现在 4 处而非 6 处；「p8_001 丢弃遗留报表表」属 2026-10-08 就地改造的已裁决事项，只有破坏性的 `downgrade()` 作为发现存活。
- **置信度抑制：** 首轮 helper pass 有 7 条在 anchor 50 被抑制（其中 report_builder 入队顺序的重复项已合并进 #3 的 anchor 100，其余 6 条降级为 residual risks）。按锚点：`50 -> 7`。
- **mode-aware 降级：** 17 条来自 maintainability/testing/security/correctness 的单人条目，在没有可证明的用户可见缺陷时被移入软桶而非留在 primary。
- **quote-the-line 降级：** 0（无 75/100 因缺 `first_evidence` 被降）。`first_evidence_backfilled = 39`（首次 helper run 前从各 reviewer artifact 的 `evidence[0]` 恢复），reconciled pass 另回填 31 条，初始计数按引用规则保留。
- **Removable surface：** 约 45 行 / 4 文件，全部在已降级为 residual risks 的维护性条目里（无调用者的 `asSingleFilter` 兼容层与随之的 `SingleFilter` 串联、`definitionBody.ts` 中与函数失位的孤儿 docstring、report_builder_tasks 里那份无人引用的 `PENDING_HASH_PREFIX` 副本、以及 #2 修复时应顺手删掉的 `_ctx_session`）。这是死重信号，不是削减目标。
- **Residual risks（16 条，信息性）：**
  1. `validate_definition` 不校验 FilterConditions / SortBy 的字段名，拼错的定义能存、执行时才 400 —— 失败延迟到执行，且那时 PENDING 行已建、任务已入队。
  2. `renderer_pdf._fill_placeholders` 是 `blocks.fill_placeholders` 的私有副本；占位符白名单因此可在两处独立编辑，加一个占位符后 PDF 会静默继续拒绝而 DOCX/XLSX 接受，差异直到各格式页脚渲染不同才可见。
  3. 前端操作符分类法手抄在 4 处（`api/reportBuilder.ts:50/:65`、`FilterTreeEditor.tsx:45-46`、`definitionBody.ts:247`）；`BINARY_OPERATORS` 与 `LIST_OPERATORS` 是同一集合的两个名字，增删一个操作符需要多处同步改动，与后端列表之间没有编译期约束。
  4. 两个 ARQ 任务体在失败路径上高度重复，且「为什么 ARQ 0.28 需要显式 `Retry`」的 10 行注释被逐字复制了两份（两份已在周边叙述上分叉过一次）。
  5. `PENDING_HASH_PREFIX` 被声明三次，其中 `report_builder_tasks.py` 那份在本模块内零引用；只改 `report_service.py` 那份会让回收器静默停止解析 `task_id`，且没有任何东西会报错。
  6. 「数据源 key -> ORM 类」的解析循环写了三遍（`query_engine._model_for`、`datasource_registry._add_primary_keys`、`datasource_registry.primary_key_field`），其中两处在同一文件相隔 25 行。
  7. `builder_service._attr` 是伸进 `query_engine` 私有 helper 的薄包装（需要 `# noqa: SLF001`），且跳过了 registry 的字段校验 —— join 规则里一个拼错的字段名会以 `AttributeError` 而非 registry 的 400 冒出来。
  8. `asSingleFilter` 兼容层已无调用者，但它连同 `SingleFilter` 仍从 `buildBody` 的公共签名可达，三个死概念还留在模块表面。
  9. `definitionBody.ts:119-127` 是一段与所属函数失位的 docstring（描述的是 40 行之后的 `buildBody`），且其内容已经过时（第二批已交付、15 个算子已全部提供）。
  10. `_ctx_session` 复制了 `worker.session_scope` 且从不关闭它打开的 session —— 已折进 P0 #2（同一个函数），此处仅为重复记录。
  11. `/verify/{id}` 是 P8 面唯一的免登录路由，其唯一防滥用手段 `check_rate_limit` 是进程内 dict + 模块级 `asyncio.Lock`。若以多 worker 部署，有效限额是 N 倍且状态不共享；仓库内没有任何部署拓扑证据（未发现 uvicorn `--workers` 设置），故记录而非断言。另外 `_WINDOW_STATE.setdefault` 从不删 key，逐 IP 轮换的攻击者会让 dict 在进程生命周期内无界增长。
  12. HMAC 签名不绑定客户端 IP。这是有意的：URL 印在二维码上、由现场人员在另一个网络上扫描。从一份 PDF 里提取的签名可在 15 分钟 TTL 内从任意 IP 重放，唯一的闸门是每 IP 30/min 的节流。
  13. IP 限流信任 `request.client.host`，在反向代理后拿到的是代理地址 —— 与上一条同属未确立的部署拓扑：站点扫描会被塌进同一个桶，一个人超限会让其他人的合法扫描一起 429。
  14. 样式 patch 被原样写入 `style_json`。API 边界的 Pydantic schema 是 `extra='forbid'`，但任何绕过 schema 直接读 `style_json` 的未来读取者（后台任务、临时端点）看到的是未过滤的原始 JSON。当前是整洁性问题而非缺陷。
  15. `definition_json.OutputFormat` / `MaxRows` 在每次写入时被顶层列无条件覆盖，客户端设的值会静默丢弃而响应里显示的是顶层列的值。docstring 把顶层列定为权威，但契约本身并列了这两个位置。
  16. `update_definition` 允许静默改变定义的 `project_id`，且不检查 actor 对新项目的访问权；同时编辑会把状态回滚到 DRAFT，于是定义可以被悄悄搬到另一个项目。另：`_check_demo_limit` 无 `WHERE`，把 OBSOLETE 定义也算进上限，废弃之后计数不降。
- **Testing gaps（5 条）：**
  1. `apply_filters` 从未针对 JSONB 列跑过，`->>` 分支端到端无覆盖。（原 P1「15 个算子从未执行」已证伪并撤回；保留的只有这一条收窄事实。15 个算子本身逐个有测试。）
  2. `tests/services/report/test_join_project_scope.py` 的 4 个用例全部只调 `builder_service.execute_definition`，固定 10 类那条 `collect` 路径零覆盖 —— 这正是 P0 #1 没被捕获的原因。
  3. 「最后一次尝试重抛原始异常」的断言用 `pytest.raises(RuntimeError)`，而 `arq.Retry` 继承自 `RuntimeError`（`arq/worker.py:97`），因此即使有人删掉 `if attempt_no < MAX_TRIES:` 无条件抛 `Retry`（正是那条 docstring 说要防的 bug：ARQ 无限重入、任务永远拿不到终态），断言仍会绿。两侧都应改成能区分异常类型。
  4. `tests/services/report/test_renderer_visual.py` 存在只为防「PDF 文本层字符正确但页面上什么都没画」这一类回归，而 `pyproject.toml` 的 `addopts = "-m 'not visual'"` 让它在每次默认 `pytest` 里都被 deselect；文档与模块 docstring 都把补偿控制推给 CI，但仓库唯一的 workflow（`.github/workflows/check-api-drift.yml`）跑的是 alembic + OpenAPI 漂移 + 迁移幂等，从不调 pytest。手动跑过 `pytest -m visual`：4 passed —— 测试没坏，只是完全惰性。（本项目已裁决不做 CI/CD 流水线，故此处只登记覆盖缺口，不建议补流水线。）
  5. `test_collector.py` 把 10 类报表的 SPEC 源契约拆出来又丢掉：源那一半绑到 `_expected_source` 后从未被断言，因此 10 类里只有 1 类的源映射被强制。若泵数据表的数据源被改成公用工程结果，两个一致性测试仍会绿，用户会在泵数据表里拿到公用工程数据。
- **结算抑制评估：** 已执行 —— 计划为 explicit，且 `plan.settled_decisions` 带 4 条已裁决事项（ADR-P8-001 全直接生成路线、ADR-P8-004 三步删除、重试上限 3 次、2026-10-09「JOIN 分批 IN 查询 + 每次失败尝试都写审计」）。与这些裁决相抵触的候选已丢弃，见 #15。
- **意图置信度：** explicit（用户明确指名 P8 与关注面），无推断不确定项。

---

> **Verdict:** Not ready
>
> **Reasoning:** 两个 P0 都是数据边界问题，且都被独立验证逐行复核过。#1 是本轮唯一的数据越权出口：固定 10 类报表的导出路径上，项目访问校验查的是一个从未进入查询的项目 ID，`record_ids` 的归属全程不校验，JOIN 行也不带项目谓词 —— 知道别的项目记录 UUID 的已认证用户可以导出那些行。#2 让整个僵死任务回收机制完全失效：两个回收器只 flush 不 commit，cron 入口连 close 都没有，所以每一次 FAILED 改判和每一条 REPORT_FAILED 审计行都在 session 释放时回滚，ARQ worker 崩溃后任务状态永远停在 PENDING / RUNNING。两者都必须修复才能继续。
>
> **最重要的一件事（修复顺序）：** **#6 与 #2 必须同批落地，或先修 #6 再修 #2。** 现状是 #2 掩盖了 #6 —— 构建器任务从不写 `FINISHED`，于是回收器 15 分钟后把一条已经出了文件的完成态审计行改判为 FAILED；但因为 #2 的不 commit，这次改判回滚了，所以损坏没有落库。**只修 #2 会把这个被掩盖的缺陷变成活跃的数据损坏**，而且损坏发生在一张模块自己声明为审计表、不容篡改的表上。
>
> **Fix order:** #2 + #6 同批 -> #1 -> #3 -> #5 -> #4 -> #7 + #8 -> #9 / #14 / #20（都是几行的机械修复）-> 其余 P2/P3。需要人先拍板的八条（#11、#12、#15、#16、#17、#18、#23、#25）不阻塞合入，但 #16（`pcs_test` 落后两个 P8 revision）会让下一次针对迁移的验证给出看似真实实则错误的漂移结果，建议最先做掉。

---

## Actionable Findings

以下 22 条归 `downstream-resolver`（`gated_auto` 或 `manual`），全部带 `suggested_fix`。本轮为 report-only（`mode.apply_local = false`），未应用任何修复。

| # | 级别 | 位置 | 问题 | 类型 |
|---|------|------|------|------|
| 2 | P0 | `pcs-backend/app/workers/report_tasks.py:249` | 回收器只 flush 不 commit，僵死任务永远收不了尾 | gated_auto（**与 #6 同批**） |
| 6 | P1 | `pcs-backend/app/workers/report_builder_tasks.py:83` | 成功执行从不写 `FINISHED`，回收器把已完成审计行改判 FAILED | gated_auto（**与 #2 同批**） |
| 1 | P0 | `pcs-backend/app/services/report/report_service.py:163` | 固定 10 类导出无项目隔离，`record_ids` 归属不校验 | gated_auto |
| 3 | P1 | `pcs-backend/app/api/v1/report_builder.py:328` | 入队先于审计行 commit，worker 回填丢审计、轮询 404 | gated_auto |
| 5 | P1 | `pcs-backend/app/services/report/query_engine.py:297` | `batch_size=10000` 与对外承诺的 100000 行矛盾 | gated_auto（先定方向） |
| 4 | P1 | `pcs-backend/app/services/report/qr.py:43` | 二维码不带签名，`/report/verify` 必然 403 | gated_auto（或整体删除该能力） |
| 7 | P1 | `pcs-frontend/src/pages/report/ReportExecutePage.tsx:157` | 轮询无取消令牌，重跑/卸载复活孤儿循环 | gated_auto |
| 8 | P1 | `pcs-frontend/src/pages/report/ReportExecutePage.tsx:161` | 轮询从不读 FAILED 终态，空转到假超时 | gated_auto |
| 9 | P2 | `pcs-backend/app/services/report/builder_service.py:216` | SortBy 的 direction 被静默丢弃 | gated_auto |
| 14 | P2 | `pcs-backend/alembic/versions/p8_001_report_tables.py:111` | NULL `project_id` 下唯一约束在 Postgres 失效 | gated_auto（新 revision） |
| 20 | P2 | `pcs-backend/app/services/report/report_service.py:173` | 分块 IN 循环把各块 AND 成空集 | gated_auto |
| 22 | P2 | `pcs-backend/app/services/report/report_service.py:444` | 并发同内容导出落盘相撞 + 全事务回滚 | gated_auto |
| 21 | P2 | `pcs-backend/app/services/report/report_service.py:419` | 审计写失败被吞，文件存在而无审计行 | gated_auto |
| 19 | P2 | `pcs-backend/app/api/v1/report_builder.py:94` | 两份输出格式白名单不一致（csv 一收一拒） | gated_auto |
| 27 | P2 | `pcs-frontend/src/pages/report/ReportDefinitionListPage.tsx:70` | 状态筛选参数后端不接收，筛选静默失效 | gated_auto |
| 24 | P2 | `pcs-frontend/src/mocks/reportBuilder.ts:70` | MSW mock 落后于契约三处 | gated_auto |
| 26 | P2 | `pcs-frontend/src/pages/report/FilterTreeEditor.tsx:100` | 下标 key 配移动按钮 | gated_auto |
| 10 | P2 | `pcs-frontend/src/pages/report/ReportExecutePage.tsx:110` | 定义拉取未取消，可渲染错误的定义 | gated_auto |
| 30 | P3 | `pcs-frontend/src/pages/report/definitionBody.ts:275` | 给缺 `source` 的条件伪造默认数据源 | gated_auto |
| 28 | P3 | `pcs-backend/app/api/v1/report_builder.py:268` | `status` 无 enum、docstring 漏 FAILED | gated_auto |
| 29 | P3 | `pcs-backend/app/core/config.py:169` | `report_verify_secret` 无最小长度约束 | gated_auto |
| 13 | P2 | `docs/solutions/database-issues/alembic-create-table-silently-drops-schema-elements.md:1` | 12 个 P8 修复无 `docs/solutions/` 回写 | gated_auto |

置信度：#1-#8 为 100（validator confirmed）；#9、#10 为 100（未送验，单源但引用逐行核实）；#13-#30 为 75（未送验）。全部带 `suggested_fix`，`requires_verification` 按各自理由标记。

运行产物目录：`/tmp/compound-engineering-1000/ce-code-review/20261014-005528-981d772a`（`report.md`、`metadata.json`、`synthesized-findings.json`、`validator-verdicts.json`、`validator-outcome.json`、`full.diff`、`files.txt`）
