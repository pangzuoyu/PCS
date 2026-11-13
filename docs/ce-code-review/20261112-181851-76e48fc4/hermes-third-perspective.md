# 跨模型第三视角对抗性审查 —— hermes（GLM-5.2 / Z.AI）

> 本文件是**外部异族模型**对 P10-A 批次的独立对抗审查产出 + 本机复核结果。
> ce-code-review 自带的 cross-model worker 只认 codex/claude/grok/cursor/composer/opencode，
> **不认 hermes** ⇒ 直接驱动本机 hermes CLI（与 2026-11-11 那轮同一手法）。
>
> - **模型 / 接收方**：`glm-5.2` · Z.AI / GLM（`Ark.cn-beijing.volces.com`）
> - **调用形式**：`hermes chat -Q --oneshot --in <repo> --query-file <prompt> --reasoning high --max-turns 60 --run-budget 1500`
>   （⚠️ `-Q` 是承重开关：没有它会走 gateway，而 gateway **拒绝** `--run-budget`）
> - **发出内容**：评审报告 + 合成产物 + 计划/规范 + hermes 自行读取的源码片段
> - **只读证明**：派发前后 `git status --porcelain` 快照**逐字节一致**
> - **原始产物**：`hermes-third-perspective.raw.md`（stdout 原文）· `hermes-third-perspective.json`（机器可读）
> - **提示词**：`hermes-third-perspective-brief.md`

---

## 一、hermes 的判定（27 条全覆盖）

| 项 | 结果 |
|---|---|
| verdicts | **27 / 27**（无缺号、无重复） |
| 判定分布 | **confirmed 26 · rejected 1** |
| rejected | **#5**（Redis 故障致审计失明）—— 与本轮 validator 独立得出同一结论：该处已按设计降级并记 warning，所提修复是新增可观测性而非修缺陷 |
| missed_findings | **2 条新发现**（均 P3） |
| overclaimed | **2 条降级建议**（#2 P1→P2 · #14 P2→P3） |
| merge_issues | **4 条**（合并保真度） |
| 对总判定的态度 | **agree**（"Ready with fixes" 成立），但要求把 **#4 提到修复队列最前** |

### 1.1 新发现（报告里没有的）

| # | 级别 | 位置 | 内容 |
|---|------|------|------|
| H1 | P3 | `pcs-backend/app/core/errors.py:318` | 501 信封的 `request_id` 兜底会**造一个不存在于任何审计行的 id**：`getattr(request.state, "request_id", None) or str(uuid.uuid4())` —— 当中间件没写 `state.request_id`（非 `/api/v1/ai` 前缀、或中间件未挂载）时，调用方拿到的 request_id **永远查不到审计行** |
| H2 | P3 | `pcs-backend/app/core/ai_audit_middleware.py:44` | 审计前缀匹配**没有路径边界**：`AI_PATH_PREFIX = "/api/v1/ai"` 用 `startswith` 匹配 ⇒ `/api/v1/ai-anything` 这类邻居路径会被**一并审计**（今天无此路由 ⇒ P3） |

### 1.2 降级建议（hermes 认为报告定级偏高）

| # | 报告级别 | hermes 建议 | 理由 |
|---|---------|-------------|------|
| 2 | P1 | **P2** | 是**缺失的断言**，不是活着的缺陷：今天中间件每条路径都传 `request_id`（`ai_audit_middleware.py:153,182`），写入端的空 id 分支**从生产流量不可达**；要「整张审计表静默变空」需要**再叠加第二个假设回归** |
| 14 | P2 | **P3** | 「~96 行」的事实成立，但「本仓 50 行函数上限」依据的是 `standards-paths.md` 指向的 PCS/CLAUDE.md 小节 —— 而**报告自己的 coverage 注记已承认该小节在文件里不存在** ⇒ 口径未经核实，且后果纯属风格 |

### 1.3 合并保真度（merge_issues）

1. **无漏折的多视角 finding**：56 条原始主张全部对上（27 主 + 1 pre-existing + 15 降级到软桶 + 6 anchor-50 压制）；adversarial 的「reset 重新启用停用账号」折进 #1，reliability 的 README 库不匹配 P1 折进 #8，**没有凭空消失**。
2. **#7 的措辞不准确**（不是漏折，是保留项内部的事实错误）：报告写「has never been seen red / 从未被观测过一次」，但账簿 `progress.md:215-216` **记录过手动负控**（造含 `import openai` + `httpx` 打 `/api/v1/ai` 的探针 ⇒ 两条规则都红，删掉又绿）⇒ **仓库里没有随船发布的负控**，而标记绕过是真的 ⇒ finding 成立，**但那句措辞要改**。
3. **#24 的级别从 P2 降到 P3 且未写理由** —— 是唯一一处「 lenses 提议的级别向下移动」。
4. **读者按编号 1–27 对表会看到缺口**：报告正文说「七条 P1」，但 #5（validator rejected）仍留在编号主集合里 —— Coverage 已如实交代，**但编号表本身会让人以为漏了一条**。

---

## 二、本机复核（逐条回源码 + 实测）

| hermes 的主张 | 复核方式 | 结论 |
|---|---|---|
| **#4 EMAIL 正则在事件循环上二次方爆炸** | ① 独立重测正则；② **走生产函数** `hash_sanitized` | ✅ **成立，且比报告写的更严重** |
| #1 `--reset` 删非自有用户行 | 回读 `seed_e2e_data.py:94` + `token_issuer.py` 派生口径 | ✅ 成立（与 validator 一致） |
| #7 架构守卫被自然绕过 | 回读 `test_no_direct_ai_sdk.py:79-84,141-143` | ✅ 绕过成立；**「从未被观测红」措辞不成立**（见 1.3-2） |
| #8 真后端通道连错库 | 回读 `README.md:151` + `docker-compose.yml:140` | ✅ 成立 |
| #21 未迁移库上审计行被吞 | 回读 `ai_audit_tasks.py:176-179` + compose 库指向 | ✅ 成立 |
| H1 request_id 兜底 | 回读 `errors.py:318` | ✅ 成立（P3） |
| H2 前缀无边界 | 回读 `ai_audit_middleware.py:44` | ✅ 成立（P3） |
| #2 / #14 降级 | 回读代码 + 报告自身 coverage 注记 | ⚠️ **有道理**，采纳（#2→P2、#14→P3） |

### 2.1 #4 的实测（本机复现，非引用 hermes）

正则：`[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}`（`ai_sanitizer.py:46`），对**不含 `@`** 的类字符输入：

| body 长度 | 独立重测 | **走生产函数 `hash_sanitized`** |
|---|---|---|
| 10 KB | 73 ms | — |
| 20 KB | 301 ms | — |
| 40 KB | 1 171 ms | **1 107 ms**（裸文本）/ **1 061 ms**（JSON 字符串值） |
| 80 KB | 4 661 ms | **4 245 ms**（裸文本）/ **4 246 ms**（JSON 字符串值） |
| 160 KB | — | **17.0 s** |
| 320 KB | — | **68.1 s** |
| 80 KB **含 `@`** | 0.1 ms | **1.5 ms**（对照组：命中 `@` 走线性快路） |

⇒ 干净的 O(n²)（尺寸 ×2 ⇒ 时间 ×4），且**全部落在 `MAX_HASH_BYTES = 1 MiB` 之内** ⇒
**一个未认证的 320 KB POST 到 `/api/v1/ai/*` 就能把事件循环钉住 68 秒**
（80 KB ⇒ 4.2 s），期间**整个服务的所有端点一起卡住** —— 因为
`_record_audit` 在中间件的 `finally` 里、且在认证之前执行，`hash_sanitized`
是**同步 CPU** 且**没有 await 点**。

⇒ **报告里 #4 那句「quadratic cost was not measured」应删除**；
**级别应从 P1 提到 P0 级别看待**（未认证、单请求、整站事件循环停摆），
并**排到修复队列第一位**（它与 #3 共用同一条请求路径 ⇒ 一次改动同治）。

---

## 三、对报告的处置建议（尚未执行）

| 动作 | 对象 |
|---|---|
| 措辞修正 | #7 删「从未被观测红」⇒ 改为「仓库内没有随船发布的负控；账簿记录过手动负控」 |
| 措辞修正 | #4 删「not measured」⇒ 换成上表的实测数字 |
| 级别调整 | #2 P1→P2 · #14 P2→P3 · **#4 P1→（建议 P0）** |
| 新增 | H1、H2 两条 P3 |
| 编号表 | #5（validator rejected）要么从编号集合剔除、要么在表头标注「rejected」 |

⚠️ 以上改动若要进正式报告，**必须再走一轮独立验证批次**（像 2026-11-11 那轮一样：
hermes 产出 → 独立验证 → 重跑报告叶子），否则报告与验证记录不一致。
