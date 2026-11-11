# 第二轮补正（2026-11-12）—— maintainability 迟交并入 + 跨模型对抗审查

第一轮报告（`report.md`）发出后，发生了两件事，使它不再是最新的。本文件记录**补正了什么**、
**现在的验证状态**、以及**修复队列该变成什么样**。

---

## 1. maintainability 视角迟交 ⇒ 已并入，合成重跑

`maintainability` 评审员**首次**派发被上游 Token Plan 配额 429 中断（第一轮报告据此记为
「该视角缺失」）；**第二次派发最终交卷**（9 条：5×P2 / 4×P3），但交卷时刻晚于第一轮合成与验证。

⇒ 已把它并入 `raw-returns.json`（现 9 位评审 / 34 条 finding）并**重跑合成**：
`synthesized-findings.json` 由 **14 条主 finding 变为 15 条**（编号随之重排）。

maintainability 9 条的去向：

| 原条目 | 去向 |
|---|---|
| M1 守卫注册表漏 `PsvResult` | **合并**进 `#9`（原 adversarial 同源项）⇒ `reviewers = [adversarial, maintainability]` |
| M2 守卫返回值被丢弃 | **合并**进 `#15`（原 correctness 同源项）⇒ `reviewers = [correctness, maintainability]` |
| **M4 停用判定在两处各有一份实现、两把键不同** | **新主 finding `#10`（P2）** |
| M8 mock-auth docstring 写了个不存在的设置 | → **pre-existing 分区**（1 条） |
| M3 `current_actor` 位置传参耦合 · M5 失败集两份状态漂移 · M6 三份 `streams` 分支 · M7 `as StreamSource` 断言 · M9 两个引用计数变体 | → residual risks（4 条）/ testing gaps |

## 2. 跨模型对抗视角 ⇒ 补上（hermes）

ce-code-review 自带的 cross-model worker 只认 `codex` / `claude` / `grok` / `cursor` / `composer` /
`opencode` ⇒ 本机只有 Claude 一族 ⇒ 第一轮那个坑位空缺。

⇒ 由**本机 hermes CLI 直驱**补上：**`glm-5.2` · Z.AI / GLM（`Ark.cn-beijing.volces.com`）**
⇒ **唯一异族视角**。完整产出见 [`hermes-adversarial-review.md`](hermes-adversarial-review.md)
（原始 stdout 见 `hermes-adversarial.raw.md`）。

**出口**：报告 + 补充 + 计划 + hermes 自行读取的源码片段发往上述提供方（派发前已告知）。
**只读**：提示词限定只读文件与只读 git 命令；派发前后 `git status` 快照**逐字节一致**
⇒ 工作树未被改动。

### 2.1 hermes 找到的 5 条新发现（编排方已逐条回源码复核，**全部成立**）

| # | 等级 | 一句话 | 复核结论 |
|---|---|---|---|
| H1 | **P2** | **删一条「被下游物流引用」的物流 ⇒ 500** —— `_collect_references` 只查 `stream_state_points` + `flash_results`，**不查** `streams.upstream_stream_id`；该 FK（`project.py:442-444`）**无 `ondelete`** ⇒ PG 默认 NO ACTION；`outlet_stream.py:164` 每次计算出口流都写 `upstream_stream_id=source.stream_id`；端点（`streams.py:484-487`）**只捕 `PcsError`** ⇒ `IntegrityError` 裸穿成 500 | ✅ 成立。⚠️ **本批的 📎 列恰好把这一类引用变成用户可见承诺**（`reference_counts` 第①条聚合数的就是它）⇒ 第一轮只把它记成「两个口径刻意不同」的 residual risk，**这是漏报** |
| H2 | P3 | WS 拒绝信道传输层不可见 —— `ws.py:97` 的 `close()` 在 `accept()`（:100）**之前** ⇒ 真实客户端只见 HTTP 403，1008/reason 只存在于 Starlette TestClient ⇒ 又一个「会绿而现实不同形」 | ✅ 成立 |
| H3 | P3 | 首次真实登录的惰性建行竞态 ⇒ 500 —— `token_issuer.py:105-123` 的 `session.add(User(...))` + `flush()` **不捕 `IntegrityError`**，而 `users.username` 有唯一约束（`project.py:147`）⇒ 同名并发首登 ⇒ 后到者撞约束 ⇒ 500（重试即成功）。`StreamService.create` 对同一形状是捕了的 | ✅ 成立 |
| H4 | P3 | `StreamListPage.tsx:14` docstring 说谎 —— 仍写「引用 📎×N 列本批不渲染」，而同文件 243-253 行真的渲染了它 | ✅ 成立（与报告 `#14` 同族的「注释承诺 A、代码做 B」，但这条在**本批改动文件内部**） |
| H5 | P3 | CSV 导出缺「引用」列 —— `exportCsv`（:168）的 headers 无「引用」⇒ 屏幕上有、导出里没有 | ✅ 成立 |

### 2.2 hermes 对第一轮报告的挑战（4 条，编排方已复核）

| 条目 | 挑战 | 复核结论 |
|---|---|---|
| **M5（失败集两份状态漂移）** | 该故障态要求「弹窗开着且 `failedIds` 为空」；但「清除」按钮在失败清单条上（`StreamListPage.tsx:345`），而**弹窗打开时 antd Modal 的 mask 默认开启**、整页被遮罩挡住 ⇒ 点不到；弹窗关闭时 `result` 已为 null ⇒ 陈旧清单与提示都不渲染 ⇒ **今天没有任何点击序列能生产出该故障** | ✅ **hermes 正确** —— 编排方此前说的「用户可见」**说过头了** ⇒ **M5 降 P3**（结构上仍可漂移 ⇒ 保留为「单一真值源」加固项） |
| **`#7`（WS 握手 DB 异常 ⇒ 500）** | 结论对，但**修法错一半**：所有 `PcsError` 拒绝都走 close-before-accept ⇒ 真实客户端一律 HTTP 403 ⇒ 1008 + reason 根本不可达 ⇒ 报告那条「补 1008 + `AUTH_UNAVAILABLE` 兜底」修的是**日志与异常处理卫生**，不是客户端可观测性 | ✅ 成立 ⇒ 建议**降 P3** + 改修法（先 accept 再 close，或同时补日志） |
| **`#9`（PsvResult 永久 404）** | 「仓库内没有调用方」不准确 —— `app/api/v1/psv.py:247` 直接查 `DataLineage.record_type == "PsvResult"` ⇒ 该类型**有活跃消费方** | ✅ 成立 ⇒ 支持维持 P2（甚至提优先级） |
| **`#20`** | 无挑战，仅补精确事实（`load()` 的 try/catch 无 rethrow ⇒ 潜伏成立） | ✅ 定性准确 |

其余 11 条（`#1` `#2` `#3` `#4` `#6` `#8` `#11` `#13` `#14` `#15` `#16`）hermes 逐条到源码核过前提，
**未发现结论错误或假阳性**。

---

## 3. 现在的验证状态（**必须照实说**）

| 项 | 状态 |
|---|---|
| 主 finding 总数 | **15**（重跑合成后） |
| 已过独立验证门 | **10 / 15** —— 第一轮验证批次确认的全部（`confirmed 10 / rejected 0 / unresolved 0`），编号已重排，映射见 `synthesized-findings.json` 与 `validator-verdicts.round1.json` |
| **未送验（本就 report-only）** | `#2`（批末浏览器回归 · 发布动作）· `#6`（WS 投递路径 · 待决策）· `#14`（docstring 口径 · 随决策改写）· `#16`（`current_user` 第二入口 · 待决策） |
| **⚠️ 新条目 · 未过验证门** | **`#10`（停用判定两份实现、两把键不同）** —— 第二轮验证批次已派发，但同样被上游配额饿死（50 分钟未落盘）⇒ **它没经过验证门**。不过它有**两份独立佐证**：① hermes（异族模型）逐行引用 `token_issuer.py:96` 与 `user_status_service.py:53-58` 确认；② 编排方本人回源码核对同样确认（两处键分别是 `username` 与 `user_id`） |
| 全部评审子代理 | 只读（Read/Grep）⇒ **未跑测试 / EXPLAIN / 浏览器回归** ⇒ 运行期结论均为静态阅读推导；本批自述的「后端 5626 passed / 前端 1046 tests / 裸载荷 71 / PG 车道 5」**未经独立复核** |

## 4. 修复队列（合并两轮后的最终版）

| 顺序 | 条目 | 等级 | 动作 |
|---|---|---|---|
| 1 | `#1` 前端 `USER_DISABLED` 不在 `SESSION_OVER_CODES` | **P1** | 机械（一行白名单 + 一条前端测试） |
| 2 | **H1 删除被下游物流引用的物流 ⇒ 500** | **P2** | `_collect_references` 补第三张表 `streams.upstream_stream_id` + `delete()` 把 `IntegrityError` 兜成 409 `SIM_STREAM_REFERENCED`（防御未来新增的引用 FK） |
| 3 | `#3` 血缘面的角色模型 | P2 | **决策**（沿用 streams 白名单，还是改 streams 侧）⇒ 决定 `#9`/`#11` 的最终形状 |
| 4 | `#9` `PsvResult` 血缘永久 404（有活跃消费方 `psv.py:247`） | P2 | 登记 `PsvResult`，或按 `TwoPhaseResult` 方式登记为「不提供」 |
| 5 | `#4` 同一血缘行两种序列化表示 | P2 | 机械（三端点统一 `list[LineageNode]`） |
| 6 | `#7` WS 握手 DB 异常 | **P3（原 P2，hermes 建议降级）** | 补日志 + 异常兜底；**但先想清楚 close-before-accept 的信道问题**（H2）⇒ 或者改成先 accept 再 close |
| 7 | `#8` 部署断言改判 OpenAPI | P2 | 机械（改判路由表 + 回归测试） |
| 8 | `#11` fail-closed「逐字同形 404」无断言 | P2 | 机械（补三条同形断言） |
| 9 | `#13` 账簿写「合并」· 实现是「覆盖」 | P2 | 机械（改两处口径 + 更新 `fix_commit`） |
| 10 | `#15` 守卫返回值被丢弃 | P3 | 机械（传返回值，删 `session.get` 分支） |
| 11 | `#20` 刷新失败被报成「批量提交失败」 | P3 | 机械（`onDone` 移出提交错误域） |
| 12 | `#10` 停用判定两份实现 | P2 | 抽取比较谓词（`is_disabled_status(status)`），两边共用 |
| 13 | **H3** 首次登录建行竞态 ⇒ 500 | P3 | `flush()` 捕 `IntegrityError` ⇒ 收敛为「另一请求已建行」 |
| 14 | **H4 / H5** docstring 说谎 + CSV 导出缺「引用」列 | P3 | 机械 |
| 15 | **M5** 失败集两份状态漂移 | **P3（原 P2，hermes 反驳后降级）** | 单一真值源（当前不可达，属加固） |
| 16 | `#2` 批末浏览器回归跑在非最终 HEAD | P2 · release | 在批末 main 重跑一次回归并改报告「批末 HEAD」 |
| 17 | `#6` / `#16` WS 投递路径 · `current_user` 第二入口 | P2 / P3 · human | 各做一次「实现 or 明确登记为豁免」的决策（写进 ADR-0046 §⑤ / SPEC §7.1） |

⚠️ `#1` → H1 → `#3` 决策 → `#9`/`#4` → … 这条顺序的**理由**：H1 是本批招牌功能 📎 列直接把用户引向的
一条 500（既有 9 视角漏报、hermes 补上）；`#3` 的决策排在 `#9`/`#11` 之前是因为后两条的最终形状由它决定。

---

## 5. 本目录的文件版本说明

| 文件 | 对应哪一轮 |
|---|---|
| `report.md` | **第一轮**（14 条主 finding 的完整报告，含需求完整性与 Coverage） |
| `synthesized-findings.json` | **第二轮**（15 条主 finding，含 maintainability 并入后的降级/软桶/triage 分组） |
| `validator-input.json` | **第二轮**的验证批次（11 条）—— 第二轮验证批次因配额饿死**未产出判定** |
| `validator-verdicts.round1.json` | **第一轮**的 10 条判定（全部 confirmed） |
| `validator-verdicts.json` | 与 `validator-verdicts.round1.json` 内容相同（当前磁盘上的判定文件） |
| `validator-input.round2.json` | 第二轮批次输入的副本 |
| `hermes-adversarial-review.md` | hermes 的跨模型对抗审查（**已复核**版：含编排方逐条回源码的复核结论） |
| `hermes-adversarial.raw.md` | hermes 的原始 stdout（未加工） |
| `maintainability-supplement.md` | maintainability 9 条的**第一轮**补充（部分结论已被本文件 §2.2 修正：M5 降 P3） |
