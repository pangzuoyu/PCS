# 第三方裁决意见（hermes / learnings 人格）—— 6 条人未裁决的发现

> **范围**：`report.md` 中**人未裁决**的 6 条：#9 · #13 · #17 · #22 · #24 · #27
> **裁决者**：hermes（ce-code-review 的 `learnings` 人格）⇒ ⇒ **第三方意见**，非人裁决
> **日期**：2026-11-17
> **取证基准**：`main` @ `64cf54e`（**裁决当时**的代码）
> ⚠️ **hermes 只有 Read/Grep 能力** ⇒ ⇒ 全部结论是**读码**结论 ⇒ ⇒ 凡需运行时的点一律标注「需运行时验证」并给命令。
> ⚠️ **本文件不自动应用**：任何一条落地前，先按 `docs/superpowers/plans/2026-11-17-p10-batch-f-production-readiness.md` 的任务重核「事实基础」。

---

## 0. 摘要表

| # | 标题（缩） | 裁决 | 优先级 | 一句话判据 |
|---|---|---|---|---|
| **#9** | useFetch 静默吞错 · 绕过 axios 401 | **改判**（方向仍「修」，但**理由与范围都要换**：不是「永久卡死」，而是「每 30 分钟一次、每个用户都会撞上、且无任何提示」；且范围从 9 个路由扩到「整个前端第二条 HTTP 通道」——4 文件 5 处裸 `fetch`） | **P2** | `store/auth.ts:25-27`「token 仅存内存 ⇒ 刷新即丢失 ⇒ 重新登录」⇒ 报告的「刷新后 token 仍过期 ⇒ 还是坏的」**是错的** ⇒ 可恢复 ⇒ 降 P1→P2；但 `AssetListPage.tsx:154` 仍写死假 token ⇒ 潜伏陷阱 |
| **#13** | preview-streams 无 response_model | **修** | **P2** | 事实全对且未变；`sim_imports_query.py` 5 个端点**只有这一个**没有 `response_model`（178/260/292/378 都有）⇒ 文件内部口径不一致，不是项目风格；前端**零**消费者 ⇒ 今天只是「契约没记事实」 |
| **#17** | 种子管级违反 PipeClassResponse 契约 | **改判**（方向仍「修」，但「必 500」范围要收窄、修法有副作用） | **P2**（报告给 P3） | `pipe_class_service.py:150` 的 `list_company` **固定过滤 `source=='COMPANY_STD'`** ⇒ **列表端点不 500**（前端管级列表没坏）⇒ 只有「按 id 取」那一族 500；而 `db_guard.py:43` 已把开发库排除 ⇒ 雷只在测试库 ⇒ **真正的危害是 fixture 与契约漂移**（本批已犯 3 次） |
| **#22** | 「不写 public」守卫只覆盖 4 表 · 一次基线 | **改判**（方向仍「修」，但「种子前基线」对车道**已失效**，重心要移） | **P2** | 车道种子现在是 **schema-scoped 引擎**（`conftest.py:253`）⇒ 车道的种子**不写 public** ⇒ 报告的第 ① 条对车道不成立；真问题变成 ③ `count(*)`-only（同表替换/更新看不见）+ ④ `_sync_engine` 是**第三个**未被 #19 覆写的 singleton（`session.py:22,27-39`） |
| **#24** | 仪表盘 404 修复条件不严 | **改判**（方向仍「修」，但**报告的「车道会红」今天不成立**；且报告漏了前置的 `owner_id`） | **P2** | 种子工作区 `owner_id` **也是 NULL**（`seed_e2e_flows.py:340-352`）⇒ 切换器按 `owner_id` 过滤（`workspace_service.py:98-99`）⇒ **真后端下根本选不中它** ⇒ 车道不会红；但 mock 种子里的 PERSONAL/TEMPORARY 工作区 `project_id` **就是 null**（`src/mocks/seed/workspaces.ts:29,43`）⇒ **生产里「个人/临时工作区」一点就 2 条 404** |
| **#27** | flock 守卫用原文子串 · 不校验 -n | **改判**（方向仍「修」，但**原报告的严重度理由已被 #15③ 部分接住**；同时**发现一条更硬的新问题**） | **P2**（报告给 P3） | #15③ 已落地**行为级**互斥实测 ⇒ 「互斥无证据」不成立；但那条测试名叫 `..._on_the_default_path` 却设了 `PCS_PGTEST_LANE_LOCK`（`test_pytest_pg_gate.py:205`）⇒ **它测的不是它命名的东西** ⇒ 默认路径至今只有一条**含注释的原文子串**守卫 |

---

## 1. #9 —— useFetch 静默吞错且绕过 axios 401 拦截器

- **裁决**：**改判**（方向仍「修」；但优先级、理由、范围三项都要改）

- **今天的事实**
  - `pcs-frontend/src/pages/routeWrappers.tsx:76-96` —— `useFetch` **逐字未变**：裸 `fetch`（:87）、`r.ok ? r.json() : null`（:88）、`.catch(() => {})`（:92）、**无 timeout / 无 AbortController**。调用点 9 处（:107/:159/:169/:181/:185/:189/:212/:331/:335）。
  - `pcs-frontend/src/api/client.ts:51-66` —— axios 通道 401 ⇒ `clearSession()` + 跳 `/login`（带 `SESSION_OVER_CODES` 白名单）。`useFetch` 完全绕过 ⇒ 属实。
  - **新证据 1（推翻报告的「永久」）**：`pcs-frontend/src/store/auth.ts:25-27` 明写「**token 仅存内存**（zustand store 不持久化）⇒ 刷新即丢失 → 重新登录」⇒ ⇒ 报告第 283 行「刷新后 token 仍过期 ⇒ 还是坏的」**不成立**：手动刷新 ⇒ session 清空 ⇒ `App.tsx:61-63` 的 `RequireAuth` 弹 `/login` ⇒ 重新登录拿到**新** token ⇒ **可恢复**。
  - **新证据 2（比报告更硬）**：`refreshToken` 存在 store 里（`auth.ts:11,31,38`）但前端**零处**调用 `POST /api/v1/auth/refresh`（`client.ts:85-93` 的 `authApi` 只有 `login`/`mockLogin`/`me`；`src/` 下 grep `auth/refresh` 只命中 `api.d.ts` 与一个类型注释）⇒ ⇒ 后端明明有 `refresh_token_expire_days: int = 7`（`pcs-backend/app/core/config.py:47`）⇒ ⇒ **30分钟后必然要重新登录，而 `useFetch` 那条路连「该重新登录了」都不提示**。
  - **新证据 3（范围比报告大）**：前端 `src/` 下共 **5 处裸 `fetch(`、分布在 4 个文件**（`routeWrappers.tsx:87`、`api/reportBuilder.ts:135`、`pages/results/ResultEditDrawer.tsx:135`、`pages/config/AssetListPage.tsx:153`）。逐个看：
    - `reportBuilder.ts:135` —— **刻意**裸 fetch（:128-132 的注释说明 blob 响应会让 axios 拦截器看不到 401），且**自带** `if (!res.ok) throw`（:138）⇒ 失败可见 ⇒ **不是缺陷**。
    - `ResultEditDrawer.tsx:135` —— **刻意**裸 fetch（`keepalive`，:121-125 注释说明 `sendBeacon` 带不了头），`.catch(() => {})` 注释写明「best-effort：失败一律忽略（锁靠 30min TTL 回收）」⇒ **不是缺陷**。
    - `AssetListPage.tsx:153-154` —— **写死 `DEV_BEARER`**（= `Bearer mock-jwt-token`，`src/constants/env.ts:15-17`）⇒ ⇒ 这是 **bug-2169 的双胞胎，修复批没关掉它**。⚠️ 但 hermes 核过：`GET /api/v1/config/assets/{asset_id}/revisions` 在后端**根本不存在**（`app/api/v1/` 全目录 grep 0 命中）⇒ ⇒ 今天它 404（不是 401）⇒ ⇒ **这是潜伏陷阱，不是现症**。
  - **新证据 4**：`docs/solutions/frontend-issues/raw-fetch-bypasses-axios-token-interceptor.md:52-56` 已经把这条列为「**另一次改动**」：「更彻底的修法是让路由层也走 `src/api/client.ts` 的 axios ⇒ ⇒ 但那是**另一次改动**……本批只做前者」⇒ ⇒ #9 正是那次改动，**解法文档已预告**。

- **判据**
  - `docs/solutions/frontend-issues/raw-fetch-bypasses-axios-token-interceptor.md` §2/§3：「一个仓里有两条取数通道 ⇒ 拦截器只覆盖其中一条 ⇒ 那一条在 mock 下隐形」；「新增通道时，先问：认证、401、错误信封要不要**再写一遍**？」
  - `.wolf/cerebrum.md:1090-1098`（Do-Not-Repeat · 类型断言不是运行时检查）：「前端已有 `src/api/*.ts` 的一层，**从那里拿**，别在组件里直接 fetch + cast」。
  - `docs/solutions/testing-issues/assertion-must-be-sensitive-to-named-defect.md` §4：修法要用**变异测试**证明对被它命名的缺陷敏感。

- **建议的修法**（最小，两处，不合并）
  1. ⚠️ **不要**直接把 `useFetch` 改成 axios：`api` 的 `baseURL` 已含 `/api/v1`（`client.ts:4,6`），而 9 个 path **也都带 `/api/v1`** ⇒ ⇒ 直接换 axios ⇒ **9 个路径全部 404** ⇒ 这是本条最大的坑。
  2. 改为：把 `client.ts:54-62` 的 401 判定抽成**共享函数**（如 `handleSessionOver(status, code)`），`useFetch` 的 `!r.ok` 分支**调它** ⇒ ⇒ 401/会话过期 ⇒ 与 axios 通道**同一份真相源** ⇒ 跳 `/login`；同时给 `useFetch` 加 `error` state + `AbortController`（超时 15s，cleanup 里 `clearTimeout`+`abort`），`StreamDetailRoute` 在 `error` 时渲染错误+重试而不是「加载中…」。
  3. **顺手**把 `AssetListPage.tsx:154` 的 `DEV_BEARER` 换成会话 token（`useAuth.getState().accessToken`，照 `routeWrappers.tsx:85-86` 的写法）—— 一行，但**要写进提交信息**：端点补齐那天它就是 bug-2169 复发。
  4. **不要**动 `reportBuilder.ts` 与 `ResultEditDrawer.tsx`（两处都是刻意绕过并自带失败语义；动它们会破坏「blob 不能走 axios」这条已被注释记录的理由）。

- **优先级**：**P2**（报告给 P1）
  - 按「一个合理的人用这个软件会拿到什么」：会话满 30 分钟后，用户打开任何走 `useFetch` 的页面（`/config/asset-list`、`/pipe-class`、`/sim/streams/{id}`、3 个 common 页）⇒ **页面空着/永远「加载中…」，零提示、零错误**，而正确操作（刷新）会把他踢回登录页重登 ⇒ ⇒ 「这软件是不是坏了」但**不是被锁在门外** ⇒ P2。
  - **不是 P1 的理由**：P1 那 7 条（#2/#5/#6/#7）的门槛是「守卫从未被执行 / 断言恒真」⇒ 那是**证伪能力**问题；#9 是体验问题。
  - **不是 P3 的理由**：不是边缘情况 ⇒ **每个用户每个会话 30 分钟后必遇**，且前端**根本没有 refresh 通路**。

- **残留风险 / 需运行时验证**
  - 需运行时验证：改完后 9 条路由**没有引入新 404** ⇒ 跑 `pcs-frontend` 的真后端 Playwright 路由扫描（`npm run e2e:real -- --project=real-backend`）⇒ 白名单外的 4xx/5xx 必须为空（`real_backend_route_sweep.spec.ts:208-220`）。
  - 需运行时验证：token 过期路径**今天没有任何用例覆盖** ⇒ 需新增一条（把 `access_token_expire_minutes` 临时调小，或用过期 token 打 `useFetch` 走的那个端点）⇒ 期望「跳 `/login`」。
  - 残留：`refresh` 通路本身仍是空的（见 §8 第 5 条）。

---

## 2. #13 —— preview-streams 无 response_model，注释与事实相反

- **裁决**：**修**

- **今天的事实**
  - `pcs-backend/app/api/v1/sim_imports_query.py:325-330` —— **逐字未变**：`@router.get("/{import_id}/preview-streams")` / `) -> dict:` ⇒ **无 `response_model`**。
  - `pcs-frontend/src/types/api.d.ts:32816-32825` —— 生成类型里 200 的 content 是 `{[key: string]: unknown}` ⇒ 消费者拿不到 `.streams` 键名 ⇒ 与报告一致。
  - **新证据 1（口径不一致，不是项目风格）**：同一文件 **5 个端点，4 个都有 `response_model`** —— `:178` `SimImportListResponse`、`:260` `SimImportListResponse`、`:292` `SimImportDetailResponse`、`:378` `SimImportWarningListResponse` ⇒ ⇒ **只有 `:325` 这一个没有** ⇒ ⇒ 这是**文件内部的不一致**。
  - **新证据 2（注释确实与事实相反）**：`sim_imports_query.py:361-366` 仍写「**PRO/II 导入**把 preview 存成 **list**……而 **SIM/Excel 导入存 dict**（`{"streams": [...]}`）」⇒ 而两个写入点 `app/services/import_service.py:496`（PRO/II）与 `:612`（EXCEL）**都是** `preview_streams_json=preview_dict.get("preview_streams", [])` ⇒ **list** ⇒ ⇒ 注释的后半句**没有任何写入方支持**（读侧的 dict 分支是为兼容已归一化的历史数据）。
  - **新证据 3（影响面比报告说的小）**：前端 `src/` 下**零处**消费 `preview-streams`（只在 `api.d.ts` 里有生成类型）⇒ ⇒ 今天没有任何客户端在按契约读它 ⇒ ⇒ 后果是「契约没记录事实」，不是「现在就有功能坏」。
  - **新证据 4（仓里的闸抓不到它）**：`scripts/check_openapi_payload_coverage.py` 量的是「裸 **object/array** 字段数 ≤ `BASELINE_BARE_FIELDS = 71`」（:46-47）⇒ ⇒ `-&gt; dict` 不是 object/array 声明 ⇒ **这一条不会被那个闸算成裸字段** ⇒ ⇒ 它是「闸的盲区」。

- **判据**
  - `.wolf/cerebrum.md:1013-1026`（Do-Not-Repeat · 2026-10-08 用户裁决）：「OpenAPI 里声明了 `object`/`array` 却**没有 `properties`/`items`** ⇒ `openapi-typescript` 只能生成 `object`/`any[]` ⇒ 前端**只能继续手写类型**」⇒ 「**『响应里写 object 最省事』是有下游代价的省事**」⇒ 本条正是这条裁决的教科书案例。
  - `docs/solutions/testing-issues/narrow-declaration-is-not-a-constraint.md`（声明的**形状**不是约束 —— 此处是反向：「泛声明不是契约」）。
  - `CLAUDE.md`《前端 UI 规范》：「字段/枚举/权限/错误码以 OpenAPI + meta API 为准」。

- **建议的修法**（最小）
  1. 新增 `app/schemas/sim_import.py::SimImportPreviewStreamsResponse`（`streams: list[dict[str, Any]] = Field(default_factory=list)`），端点加 `response_model=`。
  2. 注释改成事实：「PRO/II（`import_service.py:496`）与 EXCEL（`:612`）**两个写入点都存 list** ⇒ 读侧统一归一成 `{streams: [...]}`」。
  3. **要滚的 baseline**（一次，顺序固定）：
     - `pcs-backend/scripts/gate_08_openapi_contract.sh` 阶段 1-3 ⇒ 重生成 `pcs-backend/docs/openapi.json` → `pcs-frontend/openapi.snapshot.json` → `pcs-frontend/src/types/api.d.ts`；
     - 批末 `cp openapi.json openapi-baseline.json` + `--check-baseline`（该脚本 :27-79 的四阶段流程）；
     - `check_openapi_payload_coverage.py` 的 `BASELINE_BARE_FIELDS` **只会降不会涨** ⇒ 若降到 71 以下，按脚本 :125-128 的提示**下调基线**（脚本要求在提交里说明）。
  4. **不用滚任何迁移、不用手核 ORM 列**：这是纯响应侧改动 ⇒ `alembic/versions/*` **不动**。⚠️ 但要在注释里记一笔：`app/models/sim_import.py:95` 的 `preview_streams_json: Mapped[dict] = mapped_column(JSONB, default=dict)` 与实际写入的 **list** 不符（既存问题，本条可不改，但**别让下一个人照注解写代码**）。
  5. 读侧那段 `if isinstance(payload, list): return {"streams": payload}` **不能删**（老数据是 list）。

- **优先级**：**P2**（与报告一致）
  - 合理的人拿到的是「按契约读 `.streams` 拿不到 ⇒ 只能靠试/读源码」⇒ 契约债；但**今天没有消费者**，所以不是功能坏 ⇒ P2 恰当（不是 P3：因为 OpenAPI 是对外契约，而 CLAUDE.md 把它定成唯一权威）。

- **残留风险 / 需运行时验证**
  - 需运行时验证：加 `response_model` 后，OpenAPI 里该路径 200 的 schema 真的变成 `{streams: [...]}` 且 `api.d.ts` 同步 ⇒ 命令 `bash pcs-backend/scripts/gate_08_openapi_contract.sh`，然后查 `pcs-frontend/src/types/api.d.ts` 里该路径的 200 content **有没有 `streams`**。
  - 需运行时验证：**老 list 行与已归一的 dict 行两种形状都要能读**（`isinstance` 分支还在 ⇒ 应仍过）⇒ 需要一条覆盖两种历史形状的用例，否则「加了 response_model 反而把老数据 500 了」这类回归没有钉子。

---

## 3. #17 —— 种子管级违反 PipeClassResponse 契约 ⇒ 按 id 查必 500

- **裁决**：**改判**（方向仍「修」；但「必 500」的范围要收窄，修法的副作用报告没提，且**漏了「已种下的老行怎么办」**）

- **今天的事实**
  - `pcs-backend/scripts/seed_e2e_flows.py:504-531` —— **逐字未变**：`dn_series_json={"DN150": 1.0}`（:525）、`sch_series_json={"DN150": 40.0}`（:526）、`source="E2E_SEED"`（:528）；`class_id = "E2E-SEED-CS"`（:102），且 `:218` 的 `"material_class": FLOW_PIPE_CLASS_ID` 是指向它的 FK。
  - `pcs-backend/app/schemas/pipe_class.py:58-59`（`dn_series_json: dict[str, int]`）、`:62-63`（`sch_series_json: dict[str, str]`）、`:77-78`（`source: Literal["COMPANY_STD","PROJECT"]`）、`:84-93`（`_check_dn` 要求 `{min,max}` 且 `0&lt;min&lt;=max`）—— 全未变 ⇒ **三处违规成立**。
  - **新证据 1（收窄「必 500」的范围）**：`pcs-backend/app/services/pipe_class_service.py:150` —— `list_company` **固定过滤 `source == "COMPANY_STD"`` ⇒ ⇒ **列表端点 `GET /pipe-classes`（`pipe_classes.py:108`，`response_model=list[PipeClassResponse]`）不会 500** ⇒ ⇒ **前端的管级列表页没坏**。真正会 500 的只有**按 id 取**那一族：`pipe_class_service.py:158-170` 的 `get` **不过滤 source** ⇒ ⇒ `GET /pipe-classes/{class_id}`（`pipe_classes.py:168`）+ `PUT`（:188）+ `submit`/`approve`/`publish`/`obsolete`（:249/273/294/315），**且仅限 `class_id = "E2E-SEED-CS"`**。
  - **新证据 2（严重度下调的依据）**：`pcs-backend/app/core/db_guard.py:43` —— `ALLOWED_LANE_DATABASES = frozenset({"pcs_pgtest", "pcs_test"})` ⇒ ⇒ **开发库 `pcs` 已被拒绝**（#8 落地 `c75b505`）⇒ ⇒ 这颗雷**只存在于测试库**（pcs_pgtest 的 public，见 `TODOS.md:3519` TODO-154）⇒ ⇒ **产品用户碰不到**。
  - **新证据 3（修法的副作用，报告没提）**：既然 `list_company` 的过滤键**就是** `source` ⇒ ⇒ 报告建议的 `source="COMPANY_STD"` 会让这行**出现在公司管级列表里**（pcs_pgtest public 会多一行「E2E 种子管级」）⇒ ⇒ 这本身无害（#2 裁决的 `CS-STD` 行本来就是 `COMPANY_STD`），但**必须写进提交信息**，否则会被下一个人当成污染去删。
  - **新证据 4（契约内形状的现成模板）**：`pcs-backend/alembic/versions/p10_002_seed_placeholder_pipe_class.py:41-55` 的 `CS-STD` 行就是标准答案 —— `dn_series_json={"min": 15, "max": 600}`（**int**）、`sch_series_json={"15": "0.5", "600": "1.2"}`（**字符串**）、`source="COMPANY_STD"`、`status="DRAFT"`。
  - **新证据 5（报告漏掉的一步）**：种子是 `_get_or_create`（`seed_e2e_flows.py:513-515` 按 `class_id` 查，**存在就不动**）⇒ ⇒ **改脚本不会修好已经种进 pcs_pgtest public 的老行** ⇒ ⇒ 必须显式订正（`UPDATE pipe_classes SET … WHERE class_id='E2E-SEED-CS'`，或 `--reset` 重灌）⇒ ⇒ 否则「修了」但现象照旧 ⇒ ⇒ 而这正是仓里最熟的一族（cerebrum「事实基础也会错」「症状离病因很远」）。

- **判据**
  - `docs/solutions/testing-issues/guard-test-fooled-by-lying-comment.md` §4（fixture 用一份**契约外**的类型构造 ⇒ 测试再多也是**零信号**）—— 这正是 learnings 人格 `testing_gaps[2]` 自己写下的形状，且**至今没有用例**。
  - `docs/solutions/database-issues/response-enum-nullable-must-match-db-nullability.md`（响应契约必须与实际形状对齐；**放宽响应**而非放宽请求是对的）。
  - `.wolf/cerebrum.md:1004-1011`（mock/seed 契约一致性 = **正确性的一部分**；方向只能 seed → 契约）。
  - **与已落地裁决的边界**：#2 裁决「不扩 `Literal` 加 `SYSTEM_PLACEHOLDER`」⇒ ⇒ **不扩词表**。

- **建议的修法**（最小）
  1. `seed_e2e_flows.py:525-528` 三处改成契约内形状：`dn_series_json={"min": 150, "max": 150}`（int）、`sch_series_json={"DN150": "40"}`（**字符串**）、`source="COMPANY_STD"`。
     ⚠️ 另一条路是把 `material_class` 直接指向 `CS-STD`（`:218`）—— 那会牵动 `FLOW_PIPE_CLASS_ID` 这个导出常量（`:892-893`）⇒ 改动面更大 ⇒ **不取**。
  2. **不动 `alembic/versions/*`** ⇒ 无迁移要滚、无 ORM 列要手核。（理由：这一行是**测试 fixture**，不是产品主数据 ⇒ 不受 #2「配置数据的 canonical 落点是迁移」约束。）
  3. **加契约级断言**（真正堵复发的那一步）：`tests/scripts/test_seed_e2e_flows.py` 里对种子行做 `PipeClassResponse.model_validate(row_dict)` ⇒ 不抛错。⚠️ **不要**手写一份副本比对 —— 要断的是**契约本身**，副本会一起漂。
  4. **补订正已种下的老行**（见「新证据 5」）：一条幂等的 `UPDATE`，或把 `--reset` 写成批末动作。

- **优先级**：**P2**（报告给 P3 ⇒ 上调一级）
  - 合理的人拿到的是「某个管级 id 一查就 500」—— 在**生产库**上这会是一个真 500 端点；在测试库上则是「一颗会引爆的地雷」。
  - 上调理由不是「现在就有人踩」，而是**这类缺陷在本批已经出现过 3 次**（#3/#12 的 `data_version`、#13 的 preview 形状、#17 的种子行）⇒ ⇒ 同族复发率本身就是信号 ⇒ 再不钉住契约断言，下一条种子行还会漂 ⇒ P2 恰当（不是 P1：今天没有生产暴露面）。

- **残留风险 / 需运行时验证**
  - 需运行时验证（**必须**）：修完 + 订正老行后 `GET /api/v1/pipe-classes/E2E-SEED-CS` 应 **200** ⇒ 怎么验：在 pcs_pgtest 上 `uv run python scripts/seed_e2e_flows.py`（脚本自带库名白名单，`seed_e2e_flows.py:850-855`），再用 SYSTEM_ADMIN token 请求该端点 ⇒ 期望 200 + body 满足契约。
  - 需运行时验证：`GET /api/v1/pipe-classes`（列表）必须**仍 200** 且现在**含**这行（因为 `source` 改成 `COMPANY_STD`）⇒ ⇒ 「公司管级列表里出现『E2E 种子管级』」要不要接受，是**产品决定** ⇒ 建议登记 TODO。
  - 残留：`app/models/sim_import.py:95` 那类「ORM 注解 ≠ 实际写入形状」的同族问题仍在（不在本条范围，但同一个洞）。

---

## 4. #22 —— 『不写 public』守卫只覆盖 4 张表、只取一次基线

- **裁决**：**改判**（方向仍「修」；但「种子前基线」这条对车道**已失效**，重心要移到「覆盖面 + count-only + 第三个 singleton」）

- **今天的事实**
  - `pcs-backend/tests/e2e_flows/test_lane_smoke.py:102-157`（守卫）与 `:234-243`（`_public_snapshot`）—— **逐字未变**：只数 `("users", "projects", "streams", "user_projects")` 四张表的 `count(*)`；只跑 `POST /api/v1/projects` 一条写路径。
  - **新证据 1（报告第 ① 条对车道已失效）**：`pcs-backend/tests/e2e_flows/conftest.py:253` —— 车道的种子 fixture 用**自己建的 schema-scoped 引擎**（`_async_engine(_lane_url(), e2e_schema)`）⇒ ⇒ **车道里的种子写的是隔离 schema，不是 public** ⇒ ⇒ 「种子阶段写进 public ⇒ before 快照已含它 ⇒ 看不见」这个具体场景**今天在车道内不成立**。
  - **新证据 2（但 public 里确实有 E2E 数据，来源在车道之外）**：`scripts/seed_e2e_flows.py:842-855` 的**脚本入口**走 `get_async_session_factory()`（全局工厂）⇒ ⇒ 脚本模式（compose 的 `seed` 服务，见 TODO-154）写的是 **pcs_pgtest 的 public schema** ⇒ ⇒ 「public 里有 E2E 数据」是**真的**，但它发生在**另一个进程、另一个时间** ⇒ ⇒ 守卫**结构上就看不见** ⇒ ⇒ 这不是「基线取晚」，是「**守卫的作用域根本不含那条路**」。
  - **新证据 3（#19 只补了一半 —— 第三个 singleton）**：`pcs-backend/app/db/session.py` 有**三个**引擎单例 —— `_sync_engine`/`get_engine()`（:22, :27-39）、`_async_engine`/`get_async_engine()`（:23, :61-73）、`_async_session_factory`/`get_async_session_factory()`（:24, :76）。**#19 的落地只覆写了后两个**（`conftest.py:326-327`）⇒ ⇒ **`_sync_engine` 仍指 public** ⇒ ⇒ 任何走 `get_engine()` 的路径在车道里读写的是 public。
    ⚠️ 今天的实际暴露面：`get_engine()` 只被 `session.py:42 check_database()` 用（无端点调用；health 走 `check_database_async`，`app/api/v1/health.py:58`）⇒ ⇒ **今天没有活的泄漏路径，但闸是敞开的** ⇒ ⇒ 这是**未来泄漏点**，而守卫看不见它。
  - **新证据 4（count-only 的盲区更具体）**：守卫只断 `count(*)` ⇒ ⇒ public 里「删一行 + 加一行」**count 不变** ⇒ 看不见；public 里**改**一行（不增删）**更看不见** ⇒ ⇒ 真正的盲区是「**同表内的替换与更新都看不见**」。
  - **新证据 5（守卫里最扎实的一块，报告没表扬）**：`test_lane_smoke.py:106-113` 的 docstring + `:129-152`（**独立连接** + **断言写路径必须 200/201**，否则「public 不变」只是「没写」的同义反复）⇒ ⇒ 它**已经**符合「断后果不断动作」的纪律。
  - **新证据 6（`public.` 显式限定是对的）**：`.wolf/cerebrum.md:1651-1653` 记着「`information_schema` 不受 `search_path` 约束 ⇒ 隔离 schema 测试查表必须加 `table_schema = current_schema()`」⇒ ⇒ 守卫用 `public.<table>` 显式限定 schema **符合**这条 ⇒ ⇒ 改写时**不要**把它改成 `current_schema()`。

- **判据**
  - **learnings 人格自己写下的局限**（`personas/learnings.json` learnings[3]）：「**隔离类守卫必须枚举车道会写的全部表，且同时断 count 与 max(id)/updated_at**，否则『隔离』只是部分成立」⇒ ⇒ **这条发现就是它自己记下的那条局限，且至今未补** ⇒ ⇒ 这是本条最强的判据。
  - `docs/solutions/testing-issues/sqlite-staticpool-hides-uncommitted.md` / `guard-patched-definition-site-consumer-imported-by-value.md` §5-6：守卫要断言**后果**，不要断言**动作**。
  - `docs/solutions/security-issues/midflight-config-rebind-defeeds-one-shot-guards.md`：判据要具体、要在 submit 时冻结。
  - `.wolf/cerebrum.md:1449`（主键列名不统一 ⇒ `getattr` 恒为默认值）⇒ ⇒ 「加 `max(id)`」这条必须**逐表核 PK 列名**，不能照抄。

- **建议的修法**（最小，两步，别一次做太狠）
  1. **覆盖面**：`_public_snapshot`（`test_lane_smoke.py:234-243`）改成枚举**车道会写的全部表**（照 `scripts/seed_e2e_flows.py` 的写表清单 + 请求路径的写表），每张表**同时断 count 与 max(id)**（`SELECT count(*), coalesce(max(<pk>),0) FROM public.<t>`）。
     ⚠️ **max(id) 那句要逐表核 PK 列名**（`information_schema.columns`）—— 本仓 PK 列名不统一（cerebrum:1449）⇒ ⇒ 照抄 `max(id)` 会**恒为 0** ⇒ 等于没加。
  2. **第三个 singleton**：把 `conftest.py:324-327` 的覆写**扩到 `_sync_engine`**（造一个 schema-scoped 的 sync engine 赋给 `db_session_mod._sync_engine`）⇒ ⇒堵住「将来有人写一条走 `get_engine()` 的路径」。
  3. **基线时机**：**不必**改成「种子前」（车道的种子已 schema-scoped）⇒ ⇒ 改成「**车道启动时取一次 public 基线（session 级，`e2e_schema` fixture 已是 session scope，`conftest.py:166-167`），车道结束再取一次**」⇒ ⇒ 这样「整个车道期间 public 有任何增删改」都看得见 ⇒ 比「单条写路径前后」更强，且能覆盖 #19 之外的新写路径。
  4. **不要**在本条里顺手做「脚本入口的库名白名单」—— 已由 #8 落地（`db_guard.py`）管住 ⇒ 两处别重复。

- **优先级**：**P2**（与报告一致）
  - 合理的人拿到的是「E2E 跑完，共享库/开发库多了一批行，**没人知道**」⇒ 数据污染不可逆 ⇒ P2 合理。
  - **不是 P1 的理由**：当前已知的泄漏路径都已被 #19（async 两条）与 #8（库名）封住 ⇒ ⇒ 不是正在流血；剩下的是「闸不严 ⇒ 下一个新路径会漏」。

- **残留风险 / 需运行时验证**
  - 需运行时验证（**变异测试**）：扩表 + 加 `max(id)` 后，**在 public 里手工插一行 / 删一行 / 改一行**再跑车道 ⇒ 守卫必须红 ⇒ 这正是 `docs/solutions/testing-issues/assertion-must-be-sensitive-to-named-defect.md` §4 要求的动作。
  - 需运行时验证：session 级基线方案要确认 `e2e_schema` 的 session scope 足够（已是，`conftest.py:166-167`）。
  - ⚠️ **两种基线时机不能混**：若改成「种子前基线」，那时 public 里**还没有** compose seed 的数据（TODO-154）⇒ 会与「车道启动时基线」得到完全不同的数字 ⇒ 必须二选一并写进注释。

---

## 5. #24 —— 仪表盘 404 修复条件不严：工作区无 project_id 时照旧 404

- **裁决**：**改判**（方向仍「修」；但报告的**「车道会红」今天不成立**，且报告漏了**前置的一步 `owner_id`**）

- **今天的事实**
  - `pcs-frontend/src/pages/DashboardPage.tsx:8-10`（`workspaceProjectId` → `ws.project_id ?? '00000000-0000-0000-0000-000000000001'`）、`:20`、`:40`（`{selected ? <InputChecklistPanel projectId={projectId} /> : null}`）—— **逐字未变** ⇒ 报告描述属实。
  - `pcs-backend/app/models/project.py:118-119` —— `project_id: Mapped[uuid.UUID | None]` **可空** ⇒ 属实。
  - `pcs-backend/scripts/seed_e2e_flows.py:340-352` —— `_ensure_workspace` **不填 `project_id`** ⇒ 属实。
  - **新证据 1（报告漏掉的另一半 ⇒ 「车道会红」不成立）**：同一个 `_ensure_workspace` **也不填 `owner_id`**（模型：`app/models/project.py:116` `owner_id: Mapped[uuid.UUID | None]`）⇒ ⇒ 而 `list_workspaces`（`app/api/v1/workspaces.py:63-80`）按 `owner_id` 过滤（`app/services/workspace_service.py:98-99`：`stmt.where(Workspace.owner_id == owner_id)`）⇒ ⇒ **种子工作区在任何人（连 SYSTEM_ADMIN 的 `dan`）的切换器里都不出现** ⇒ ⇒ **真后端通道里根本选不中它** ⇒ ⇒ 报告第 516 行「真后端通道『控制台无 error』的断言仍会红」**今天不成立**。
    佐证：`real_backend_route_sweep.spec.ts:37-91` 的 ROUTES 里有 `'/'`（= `DashboardPage`，`App.tsx:66`），但**从不点**切换器（`WorkspaceSwitcher.tsx:60-64` 的 `handleChange` 只由用户点击触发）⇒ ⇒ 面板压根不挂载 ⇒ ⇒ 无 404。
  - **新证据 2（生产里是**真**缺陷，与真后端通道无关）**：mock 通道的种子 `pcs-frontend/src/mocks/seed/workspaces.ts:26-49` 里，`ws-personal-002`（:29）与 `ws-temp-003`（:43）的 **`project_id` 就是 `null`** ⇒ ⇒ 任何真实用户选中一个「个人/临时」工作区（这两类工作区**按设计**就无项目）⇒ ⇒ `workspaceProjectId` 返回占位 id ⇒ ⇒ `InputChecklistPanel`（`src/components/common/InputChecklistPanel.tsx:81-84`）发 **2 个请求**（`checklistApi.list` + `checklistApi.completeness`）⇒ ⇒ **两条 404 + 控制台 error** ⇒ ⇒ 「打开仪表盘 → 选个人工作区 → 面板炸成空」**在生产里可复现**。
  - **新证据 3（mock 通道把这个缺陷遮住了）**：唯一带 `project_id` 的 `ws-formal-001`（`src/mocks/seed/workspaces.ts:16`）用的**就是**占位 id `000...001` ⇒ ⇒ mock 下它「是对的」⇒ ⇒ 缺陷隐形。

- **判据**
  - `docs/solutions/testing-issues/guard-test-fooled-by-lying-comment.md` §4（mock 漂移遮住生产缺陷）。
  - learnings 人格 learnings[0]：「断言要断**具体行内容**，不能断『页面渲染了』」⇒ ⇒ 「仪表盘没 404」这条现在**没有任何断言**。
  - `docs/solutions/testing-issues/narrow-declaration-is-not-a-constraint.md`：`?? '占位 id'` 就是一个**假契约** —— 它让「这个工作区没有项目」与「这个工作区的项目 id 恰好是那个常量」**不可区分**。

- **建议的修法**（最小）
  1. 把 `00000000-0000-0000-0000-000000000001` 收敛成**共享常量**：`src/constants/env.ts:13`（`PROJECT_ID` 的兜底）与 `DashboardPage.tsx:9` 各写了一份 ⇒ ⇒ 放 `env.ts` 导出 `PLACEHOLDER_PROJECT_ID`，两处都引。
  2. `DashboardPage`：**删掉 `workspaceProjectId` 这个函数**（它的兜底本身就是那个假契约）⇒ 改成 `const effectiveProjectId = selected?.project_id ?? null;` ⇒ 渲染条件用 `effectiveProjectId`（不是 `selected`）⇒ 传给 `InputChecklistPanel` 的也是它 ⇒ ⇒ **没有项目 ⇒ 一个请求都不发 ⇒ 没有 404、没有控制台 error**；卡片标题区分「该工作区未归属项目」。
  3. **种子侧**：**先补 `owner_id`**（否则真后端的工作区列表永远是空的，报告建议的「补 `project_id`」根本轮不到）⇒ ⚠️ `owner_id` 要填**派生 id**（`derive_user_id(username)`，与 `conftest.py:273` 同一口径），**不是用户名**。
  4. `project_id` 要不要补是**产品决定**：FORMAL 工作区按设计归属一个项目 ⇒ 但工作区**先于**项目创建（`Project.workspace_id` NOT NULL）⇒ ⇒ 要在 `_ensure_project` **之后**回填 `workspace.project_id = project.project_id` ⇒ ⇒ **这个顺序约束必须写进注释**（否则下一个人会把 `project_id` 提到工作区创建之前 ⇒ 撞 FK）。
  5. **加一条断言**（真正的钉子）：真后端通道里选工作区 ⇒ 断「**没有** 4xx / 没有控制台 error」⇒ 这一条同时钉住 #24 与 #9 的表现面。

- **优先级**：**P2**（与报告一致，但**理由要换**）
  - 合理的人拿到的是「仪表盘选个人/临时工作区 ⇒ 两条 404 ⇒ 面板空白、**且没有任何提示**」⇒ 这不是「打不开」，是「**打开了但内容是错的**」⇒ P2 恰当。

- **残留风险 / 需运行时验证**
  - 需运行时验证：补 `owner_id` 后，`GET /api/v1/workspaces?owner_id=<派生 id>` 必须返回那行 ⇒ 且要确认 `derive_user_id` 与种子里的 user id 完全一致。
  - 需运行时验证：选中工作区后，仪表盘的 2 个请求的 `projectId` 必须是**真项目 id** ⇒ 真后端通道断「控制台无 error」。
  - 残留：前端还有**别的**占位 id 用法（`env.ts:13` 的 `PROJECT_ID` 被 `routeWrappers.tsx:136,212,331,335` 等当**真 id** 用）⇒ ⇒ 同一个「占位常量当真值」的病还有第二处，本条只覆盖仪表盘。

---

## 6. #27 —— flock 守卫测试用原文子串匹配（含注释）且不校验 -n

- **裁决**：**改判**（方向仍「修」；但**原报告的严重度理由已被 #15③ 部分接住**，同时**发现一条比它更硬的新问题**）

- **今天的事实**
  - `pcs-backend/tests/scripts/test_pytest_e2e_gate.py:94-98` —— **逐字未变**：`pg_body = PG_SCRIPT.read_text(encoding="utf-8")`（**含注释**）、`assert "flock" in pg_body`、**不校验 `-n`**、不校验 `exec 9>` ⇒ 报告描述属实。
  - 同文件 `:32-43` 的 `_body()` 确实剥注释 ⇒ **同一文件两套口径** ⇒ 属实。
  - `pcs-backend/scripts/pytest_pg.sh:78-84` —— 真脚本：`exec 9>"$LOCK_FILE"` + `if ! flock -n 9; then` ⇒ **`-n` 与 fd 9 都在可执行部分** ⇒ 报告说的「真正被依赖的是 `-n`」属实。
  - **新证据 1（改变严重度）**：`pcs-backend/tests/scripts/test_pytest_pg_gate.py:165-218` —— **#15③ 已落地一条行为级互斥实测**：起一个占锁进程（`flock -n <lock> sleep 30`）⇒ 跑车道脚本 ⇒ 断言**非零退出**且输出含「另一条车道正在跑」（:209-215）⇒ ⇒ **「两条车道真的被互斥」今天有行为证据了** ⇒ ⇒ 报告第 565 行「守卫证明的是『文件里出现过 flock 这个词』，不是『两条车道真的被互斥』」**只剩一半成立**。
  - **新证据 2（比 #27 更硬的新问题）**：那条行为级测试**名叫 `test_two_lanes_are_mutually_exclusive_on_the_default_path`**，docstring 也写「**默认路径**下两条车道真的互斥」⇒ ⇒ 但它第 205 行设了 `"PCS_PGTEST_LANE_LOCK": str(lock_file)`（`lock_file = tmp_path/"lane.lock"`，:182）⇒ ⇒ **它测的是「覆盖路径」，不是「默认路径」** ⇒ ⇒ **它没测它命名的东西** ⇒ ⇒ 而**默认路径 `.tmp/lane.lock` 至今只有一条「原文子串」守卫**（`test_pytest_pg_gate.py:149-163`，**读原文含注释**）⇒ ⇒ 把可执行行删掉、只留注释，守卫照样绿 ⇒ ⇒ **默认路径可以静默退回 `/tmp`** —— 那正是 `.wolf/cerebrum.md:850-854` 记的「锁文件不能在 `/tmp` ⇒ inode 换新 ⇒ 互斥**静默失效**」。
  - **新证据 3（唯一入口守卫也是原文口径）**：`test_pytest_pg_gate.py:136-146` 断言 `body.count("uv run pytest") == 2`，**读原文** ⇒ 今天原文里恰好 2 处（`pytest_pg.sh:82`、`:91`）⇒ ⇒ **现在恰好过**，但同一处将来在注释里写一句「uv run pytest」就会**假红** ⇒ ⇒ 与「注释骗过断言」是**同一条病的两面**。

- **判据**
  - `docs/solutions/testing-issues/guard-test-must-use-its-own-lane-lock.md` §4：「**同一个文件里两套口径**（一条剥注释、一条不剥）⇒ ⇒至少要**一致**」⇒ ⇒ **这条解法文档已经点名了这个不一致，并要求一致** ⇒ ⇒ 这是本条最直接、最强的仓内判据。
  - `docs/solutions/testing-issues/guard-test-fooled-by-lying-comment.md`（断可执行部分，不是断文本）。
  - `docs/solutions/testing-issues/assertion-must-be-sensitive-to-named-defect.md` §4（用变异测试证明断言对它**命名的**缺陷敏感）⇒ ⇒ 用它自己的标准判那条新测试：**它不合格**。
  - `.wolf/cerebrum.md:850-854`（锁文件不能在 `/tmp`）。

- **建议的修法**（最小）
  1. **把 `_body()` 参数化**（`def _body(path: Path) -> str`），不要复制第二份实现 ⇒ ⇒ `test_pytest_e2e_gate.py:94` 改成剥注释口径，断 **`"flock -n 9" in body`** 且 **`"exec 9>" in body`**。
  2. 同样把 `test_pytest_pg_gate.py:138`（唯一入口）与 `:149-163`（默认锁路径）改成剥注释口径 ⇒ ⇒ 三个守卫三处统一。
  3. **处理那条被命错的互斥测试**：默认路径**无法**在测试里真占锁（会与真车道抢同一把锁 ⇒ 撞上「守门测试与被守机制共享资源」，正是 `guard-test-must-use-its-own-lane-lock.md` 记的病）⇒ ⇒ **不要**改成真占默认路径 ⇒ ⇒ 正确做法是：**改名**为 `..._on_an_overridden_lock_path`（诚实）+ **另写**一条「默认路径」的**静态**守卫（剥注释 + 断 `.tmp/lane.lock` + 断 `flock -n` + 断 `exec 9>`）⇒ ⇒ 默认路径既然只能静态断，**就必须断得严**。
  4. **用变异测试证明新守卫敏感**：把 `flock -n 9` 改成 `flock 9`（阻塞版）、把 `.tmp/lane.lock` 改回 `/tmp/…` ⇒ ⇒ 守卫必须红。

- **优先级**：**P2**（报告给 P3 ⇒ 上调一级，**但不是因为报告给的理由**）
  - 合理的人拿到的是：默认锁路径被静默改回 `/tmp` ⇒ ⇒ 互斥静默失效 ⇒ ⇒ 「两条车道并发建 schema ⇒ DDL 互相等锁 ⇒ **偶发卡住**」⇒ 排查成本极高。
  - **不是 P1 的理由**：默认路径**今天是正确的**（`.tmp/lane.lock`）⇒ ⇒ 不是正在流血；且互斥本身已有行为级证据（只是测的是覆盖路径）。

- **残留风险 / 需运行时验证**
  - 需运行时验证（**变异测试**）：上面第 4 步的两处改动都必须让守卫红。
  - 需运行时验证：**默认路径**的互斥不能只靠静态断 ⇒ ⇒ 需人工在真车道运行时另开终端跑一次脚本 ⇒ 期望输出「另一条车道正在跑」⇒ ⇒ **这是唯一能证明默认路径真互斥的办法**。
  - 残留：`PCS_PGTEST_LANE_LOCK` 覆盖路径**被测过**、默认路径**只被静态断过** —— 这个不对称本身就是 `guard-test-must-use-its-own-lane-lock.md` §3 里已经记账的代价，**至今没销**。

---

## 7. 与既有裁决 / 已落地修复的冲突

| 处 | hermes 的意见 | 冲突点 | 听谁的 & 为什么 |
|---|---|---|---|
| **#9 vs 已落地的 `raw-fetch-bypasses-axios-token-interceptor.md`** | 该解法文档 §3 已把「改走 axios」定为「另一次改动」⇒ ⇒ **#9 就是那次改动** ⇒ 支持现在做 | 报告 #9 建议「直接复用 axios 实例」⇒ ⇒ 但 axios 的 `baseURL` 已含 `/api/v1`，9 个 path 也都带 ⇒ ⇒ **照做会 9 条全 404** | **听已落地解法文档 + 取证**（先抽共享 401 处理），并把「路径前缀坑」写进提交信息 |
| **#13 vs 已落地的「契约回写」纪律** | 修 | 加 `response_model` ⇒ 必须滚 `openapi.json` / `openapi.snapshot.json` / `api.d.ts` / `openapi-baseline.json` 四份 | **听已落地纪律**（`gate_08_openapi_contract.sh` 四阶段）。建议 #13 与 #17 **合进同一批**（都要动契约/种子）⇒ 省一次 baseline 滚动 |
| **#17 vs 已落地裁决 #2（「不扩 `Literal`」）** | **不扩词表** ⇒ 走 `source="COMPANY_STD"` | hermes 新增了一个报告没提的问题：`source` 改成 `COMPANY_STD` ⇒ 该行**会出现在公司管级列表**里 | **听 #2 裁决**（不扩 Literal）。但「公司管级列表里要不要出现『E2E 种子管级』」是**新的产品裁决** ⇒ 登记 TODO |
| **#17 vs 报告的修法** | 保留报告的形状 + **补「订正已种下的老行」** | 报告没提 `_get_or_create` 是「存在就不动」⇒ ⇒ **改脚本不修老行** | 听补遗 |
| **#22 vs 已落地 #19** | #19 把隔离扩到**进程级 async session factory** ⇒ ⇒ 报告第 ③ 条「走别的入口看不见」**大部分已封** | 但 #19 **只覆写了两个 async singleton** ⇒ `_sync_engine` 仍在 public；`count(*)`-only 与 4 表清单**未动** | **对 #19 的补遗**（「隔离扩到进程级」这个说法**不完全成立**：还差一个 sync engine） |
| **#24 vs 已落地 #7（路由扫描改真断言）** | 报告说「车道会红」⇒ **不成立**（种子工作区 `owner_id` 为 NULL ⇒ 选不中；扫描也从不点切换器） | 报告的「Why it matters」与已落地的 #7 断言口径不一致 | **听代码**。但**缺陷本身在生产成立**（mock 种子里 PERSONAL/TEMPORARY 工作区 `project_id` 就是 null）⇒ ⇒ 按「缺陷成立、车道影响不成立」改判 |
| **#27 vs 已落地 #15③** | #15③ 已落地**行为级**互斥实测 ⇒ ⇒ 报告「互斥无证据」**今天不成立** | 但那条测试**名字/docstring 说「默认路径」而实现测的是覆盖路径** ⇒ ⇒ **它没测它命名的东西** | **听代码 + 证据优先**。按本仓新写的 `assertion-must-be-sensitive-to-named-defect.md`，那条新测试**自己不合格** ⇒ ⇒ 这是**新证据**，不是与人裁决冲突 |
| **#27 vs 人裁决「#15 的修法口径」** | 人裁决说 #15 ②③ 已落地 ⇒ ⇒ 不改 #15 的落地，只补「默认路径静态守卫」 | — | 无冲突 |
| **#13/#17 vs 人裁决的「fix_type 分类」** | 人裁决说 actionable 里 17 mechanical + 2 design-input（#2·#10） | hermes 把 #17 判成 mechanical + **一个产品侧小裁决**（列不列）、把 #24 判成 mechanical + **一个产品决定**（`project_id` 补不补） | 这是**对分类的补充**，不是冲突 ⇒ ⇒ 建议这两条合批时**把两个产品决定一并问掉** |

---

## 8. hermes 的 residual_risks（这次裁决之后仍然是空的结构性风险）

1. **「回写 `docs/solutions/`」这个动作本身不产生纪律。** 本批落地了 5 份解法（`b95a463`），其中 `assertion-must-be-sensitive-to-named-defect.md` 明写「断言要断的分支，必须先**到达**那个分支」「删掉被守卫的代码 ⇒ 断言必须红」⇒ ⇒ **而同一批里就出现了一条不敏感的新测试**（`test_pytest_pg_gate.py:165-218` 名为默认路径、实测覆盖路径）⇒ ⇒ **解法文档与同批代码互相打脸** ⇒ ⇒ 纪律只能靠**跨批的检查器**（例如「每份解法文档要有至少一条对应的自动化断言」），不能靠「写下来」。

2. **「隔离」类守卫仍没有全仓清单 ⇒ 抄一次就漂一次。** 车道会写哪些表这件事**只存在于 `scripts/seed_e2e_flows.py` 的代码里**，没有清单文件 ⇒ ⇒ #22 的「枚举全部表」只能靠人手抄 ⇒ ⇒ 每抄一次就漂一次 ⇒ ⇒ 结构性的解法是**从代码/迁移推**（ORM 模型集合 ∪ 迁移建表清单 ∖ 白名单），而不是第二次手抄。

3. **「改 fixture 契约」这类修复**普遍**漏掉「已种下的老行怎么办」**。#17 就是：`_get_or_create` 是「存在就不动」⇒ ⇒ 光改脚本不修 pcs_pgtest public 里那行 ⇒ ⇒ 修完现象照旧 ⇒ ⇒ 而仓里**没有一条规矩**说「改种子脚本必须配一条订正 SQL / `--reset`」⇒ ⇒ 下一条种子改动会同样漏。

4. **前端的「第二条 HTTP 通道」没有闸。** cerebrum:1098 写着「前端已有 `src/api/*.ts` 的一层，从那里拿，别在组件里直接 fetch + cast」，但**没有任何静态守卫**拦裸 `fetch(` ⇒ ⇒ 今天 `src/` 里已经有 5 处裸 fetch（其中 `AssetListPage.tsx:154` 还写死了假 token）⇒ ⇒ 下一个新页面还会写 ⇒ ⇒ 建议加一条 lint/测试级守卫（禁 `src/pages`·`src/components` 里的裸 `fetch(`），否则这条规则只是**写在纸上的**。

5. **access token 30 分钟过期，而前端没有任何 refresh 通路。** 后端有 `POST /auth/refresh` 与 7 天 refresh token（`pcs-backend/app/core/config.py:47`），前端 `refreshToken` 存进 store 却**零处使用**（`src/store/auth.ts:11,31,38`；`src/api/client.ts:85-93` 无 refresh 方法）⇒ ⇒ 「每 30 分钟重新登录」是产品事实，而**这条路径从没有任何用例覆盖** ⇒ ⇒ 这不是 #9 的一部分（#9 是通道问题），是**另一个缺口** ⇒ 建议单开 TODO 并给 refresh 流程加一条真后端通道用例。

6. **闸的总数在增长，但没有一处登记「我改了 X 该跑哪几个闸」。** `tests/scripts/` 下已有多份静态守卫（`test_pytest_pg_gate.py`、`test_pytest_e2e_gate.py`、`test_db_guard.py`…），各自 docstring 自述 ⇒ ⇒ 没有索引 ⇒ ⇒ 下一个维护者改 `pytest_pg.sh` 的锁 ⇒ 不知道该跑哪几条 ⇒ ⇒ 这与 #11（STATUS 自称已回写、`git diff` 为空）是**同一类「账簿与事实脱节」**问题的更轻版本 ⇒ ⇒ 建议在 `pcs-backend/tests/scripts/README.md`（或 `CLAUDE.md` 的「发布前检查」节）列一张「改动 → 该跑哪些守卫」的表。

---

## 未解决的问题（需人裁决，hermes 裁不了）

1. **#17 的产品决定**：`source` 改成 `COMPANY_STD` ⇒ 该行会出现在**公司管级列表**里 ⇒ 「能不能出现 / 要不要过滤」需人定（hermes 建议登记 TODO）。
2. **#24 的产品决定**：FORMAL 工作区**要不要**回填 `project_id`（以及「个人/临时工作区」在仪表盘上的文案）需人定。
3. **#22 与 #15① 的同族债**：compose 的 `migrate`/`seed` 两个写者仍不在车道互斥锁内（TODO-163）⇒ 本次裁决**未裁**（但它是 #22 覆盖面问题的一半来源）。
