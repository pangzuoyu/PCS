# ROUND-2-ADDENDUM — P10-A 评审的两轮叠加（2026-11-12）

> 本文件记录 **两轮** 的叠加过程、每轮的判定状态、以及**最终修复队列**。
> 权威报告是 `report.md`（第 2 轮渲染）；第 1 轮原文保留在 `report.round1.md`。

## 轮次叠加

| 轮次 | 视角 | 产出 | 独立验证 |
|---|---|---|---|
| **第 1 轮** | 11 个视角（correctness / security / adversarial / api-contract / project-standards / testing / maintainability / data-migration / reliability / performance + learnings-researcher） | 27 条主 finding（12 条主张折进 5 个语义合并组）+ 1 条 pre-existing + 15 条降级到软桶 + 6 条 anchor-50 压制 | 23 条进验证门 ⇒ **22 confirmed · 1 rejected**（#5） |
| **第 2 轮** | **hermes 跨族对抗审查**（`glm-5.2` · Z.AI / GLM · 经本机 CLI 驱动） | 27 条全覆盖判定（**26 confirmed · 1 rejected**，与第 1 轮 validator 对 #5 独立同判）+ **2 条新发现** + 1 次提级提议 + 2 次降级 | 3 条状态有变的（#4 / #28 / #29）进第二轮验证 ⇒ **3 confirmed · 0 rejected** |

⚠️ **hermes 不是本 skill 的 sanctioned peer route**（其 worker 只认 codex/claude/grok/cursor/composer/opencode，
本机一个都没装）⇒ 直接驱动本机 CLI ⇒ **没有 `independence_verified` 回执** ⇒ 它的发现**按署名证据计入**，
**不得用于跨视角一致性加权**。

## 第 2 轮改了 8 处

| # | 改动 | 来源 | 验证 |
|---|---|---|---|
| **#4** | 「quadratic cost was not measured」caveat **撤回**，换成实测表（40 KB ⇒ 1 107 ms · 80 KB ⇒ 4 245 ms · 160 KB ⇒ 17.0 s · 320 KB ⇒ 68.1 s · 对照组含 `@` ⇒ 1.5 ms，**全部落在 1 MiB 哈希窗口内**） | hermes 提出 + **本机走生产函数 `hash_sanitized` 复现** | ✅ 确认 |
| **#4** | **P0 提级被独立验证否决** ⇒ 维持 P1（仅可用性影响，CVSS 7.5；同路径的兄弟项 #3/#18 本就是 P1） | 第 2 轮 validator | ✅ 但仍排修复队列**第一位** |
| **#4** | 两处措辞更正：① 哈希发生在 `finally` 里、**响应之后**（不是「认证之前」）；② 前缀判定在**路由之前** ⇒ 任何 `/api/v1/ai/<任意>`（含未注册路径）都会被读 body + 哈希 | 第 2 轮 validator | ✅ |
| **#7** | 「has never been seen red」**不准确** ⇒ 改为「**仓库里没有随船发布的负控**」（账簿 `progress.md:215-216` 记录过手动负控） | hermes | ✅ |
| **#2** | **P1 → P2**（缺的是断言，不是活缺陷：今天中间件每条路径都传 `request_id`） | hermes 挑战，我复核后接受 | ✅ |
| **#14** | **P2 → P3**（「50 行上限」是全局 coding-style 规则，`standards-paths.md` 指向的 `PCS/CLAUDE.md` 小节**在文件里不存在**） | hermes 挑战，我复核后接受 | ✅ |
| **#28**（新） | 501 信封的 `request_id` 兜底会造一个**查不到审计行**的 id；**今天不可达** ⇒ anchor 50 / advisory | hermes | ✅ 确认「不可达」属实 |
| **#29**（新） | 审计前缀**没有路径边界**；`POST /api/v1/ai-anything`（未注册路由）**今天就会被审计 + 哈希** ⇒ anchor **50 → 75**，进修复队列；且**扩大 #4 的哈希攻击面** | hermes 提出可达性判断，**第 2 轮 validator 更正为「比说的更宽」** | ✅ |

## 编号稳定性

#28 / #29 **追加**在末尾，**没有任何一条被重编号** ⇒ 第 1 轮那 23 条的验证判定**继续有效**，
第 2 轮只需重验状态有变的 3 条（不必全量重跑）。

## 最终状态

| | |
|---|---|
| 主 finding | **29**（P1 × 6 · P2 × 14 · P3 × 3 · pre-existing × 1） |
| 独立验证 | 第 1 轮 **22 confirmed / 1 rejected**（23 条）；第 2 轮 **3 confirmed / 0 rejected**（3 条） |
| 跨族对抗视角 | **已跑** —— hermes `glm-5.2` · Z.AI/GLM；**按署名证据计入，无独立性加权** |
| Verdict | **Ready with fixes**（无 P0） |

## 最终修复队列

**#4 + #3 + #29**（同一条未认证请求路径，一次改动同治：先给 EMAIL 量词加界（RFC 5321 长度上限）、
再把 body 上限改成按设置取值（AI 请求是小 JSON）+ 单个 `bytearray` + 超限 413、
再把前缀改成 `path == prefix or path.startswith(prefix + "/")`）
⇒ **#1**（`--reset` 只删自己造的 + 保住停用账号的 `status`/`roles`）
⇒ **#7**（守卫改成「除唯一出口外禁止网络客户端」+ 随船负控）
⇒ **#8**（E2E 后端指向被 seed 的库 + 数据级断言）
⇒ **#6**（有界 `Retry`，照 `report_tasks`）
⇒ **#17 + #2**（哈希加降级守卫 + 递归深度上限 + 断言 `request_id`）
⇒ **#12 + #13**（契约：声明 501 为成功状态 + 声明 401，重生成契约产物）
⇒ **#15** 再 **#14**
⇒ 其余 P2/P3 按 Triage Groups。

**不进修复队列**：#5（validator rejected，实质转入 residual risk 与 #16/#21）· #21（`release`：compose 的 migrate 依赖 + schema 错误分支）· #25 / #26 / #27 / #28（`human`：需要裁决，不是修 bug）。

## 出口与只读

- **接收方**：`glm-5.2` · Z.AI / GLM（`Ark.cn-beijing.volces.com`）—— 与本轮 11 个视角**不同族**
- **发出内容**：评审报告 + 合成产物 + 计划/规范 + hermes 自行读取的源码片段
- **只读证明**：派发前后 `git status --porcelain` 快照**逐字节一致**
- **调用形式**：`hermes chat -Q --oneshot --in <repo> --query-file <prompt> --reasoning high --max-turns 60 --run-budget 1500`
  ⚠️ `-Q` 是承重开关：没有它会走 gateway，而 gateway **拒绝** `--run-budget`；
  `--usage-file` 只属于顶层 `-z`，`--run-budget` 只属于 `chat` —— 两个入口的 flag **不能混用**。
