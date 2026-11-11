# ce-code-review —— P9B-4 体验批（含 Q7 裁决落地）

- **运行 ID**：`20261111-181548-7b8a5dca`
- **评审范围**：`38c91ac..1c3acb9`（分支 `main` · 52 个文件 · 7132 行变更 · 可执行非测试行 1238）
- **计划**：`docs/superpowers/plans/2026-11-04-p9b-4-ux-batch.md`（`plan_source = explicit`）
- **模式**：markdown report-only（`apply_local = false` ⇒ **未应用任何修复，仓库工作树全程未改动**）
- **结论**：**Ready with fixes** —— 14 条主 finding（1×P1 · 9×P2 · 4×P3）

## 范围基线的修正（重要）

调用方给的基线是 `a5f62c6`，但 **T0-B 的实现落在 `9d10767`**，早于它
⇒ 用 `a5f62c6` 会把 T0-B（actor 层账号状态判定 + `ws.py` 连带 +
`user_status_service.py` + ADR-0046 §⑤ 改写）**整块漏在范围外**。
⇒ 基线修正为 **`38c91ac`**（批次真实起点），范围 = T0-A~T0-F + T1 + T2 + T3
+ 评审修复 + Q7 裁决落地（`74b23fa`）。

## 评审团队与结果

| Reviewer | Tier | 结果 |
|---|---|---|
| correctness | session | 4 条 finding，全部保留或合并 |
| security | session | 2 条 finding，全部并入保留项 |
| adversarial | session | 6 条：4 保留 · 1 合并 · 1 降为 testing gap |
| project-standards | mid-tier | 3 条，全部保留 |
| testing | mid-tier | 4 条：1 伞形项保留 · 3 降为 testing gap |
| maintainability | mid-tier | **迟交**（见下） |
| performance | mid-tier | 2 条：1 条因已裁决方案的偏好被丢弃 · 1 条锚点 50 抑制并转 residual risk |
| api-contract | mid-tier | 2 条，全部并入保留项 |
| reliability | mid-tier | 2 条，全部保留 |
| learnings-researcher | mid-tier | 非结构化返回（扫 `docs/solutions/` 10 个文件），本轮无 pack rule |

**独立验证批次**：选中 10 条 ⇒ **confirmed 10 / rejected 0 / unresolved 0 / malformed 0 / failed 0**。

## 两处覆盖盲区（如实记录）

1. **跨模型对抗视角未运行** —— 本机只装了 Claude 一家 CLI
   （`codex` / `grok` / `cursor-agent` / `composer` / `opencode` 均未安装）
   ⇒ 无可用的异族路由 ⇒ 对抗视角由本地 `adversarial-reviewer` 承担。
2. **maintainability 迟交且未经本轮验证** —— 首次派发被上游 Token Plan 配额
   429 中断；第二次派发最终交卷（9 条 · 5×P2 / 4×P3），但**晚于首轮合成与验证**
   ⇒ 重跑合成 + 验证 + 报告在配额内**未能完成** ⇒ 这 9 条**未走 Stage 5 合并与
   Stage 5b 独立验证**，单独列在 [`maintainability-supplement.md`](maintainability-supplement.md)
   （2 条与已验证项重复已标注，7 条为新增；其中 M4 / M5 已由编排方直接读代码复核成立）。

另：**所有评审子代理只读**（Read/Grep）⇒ **未执行任何测试、未执行 EXPLAIN、
未跑浏览器回归** ⇒ 涉及运行期行为的结论均为静态阅读推导；本批自述的
「后端 5626 passed / 前端 1046 tests / 裸载荷 71 / PG 车道 5」**未经独立复核**。

## 修复顺序（报告原文的 Fix order）

`#1`（P1 前端会话结束）→ `#3` 的角色模型决策（它决定 `#8` / `#9` 的最终形状）
→ `#3` / `#8` / `#4` → `#6` / `#7` / `#9` / `#10` / `#12` / `#16`
→ P3（`#11` 随决策一起改写，`#5` / `#13` 各做一次「实现 or 登记豁免」的决策）
→ `#2` 批末浏览器回归

## 目录内容

| 文件 | 内容 |
|---|---|
| `report.md` | **正式报告**（已验证的一轮；14 主 finding + 需求完整性 + Coverage） |
| `maintainability-supplement.md` | 迟到的 maintainability 9 条（未验证，单独列出） |
| `<reviewer>.json` | 9 位评审员的完整分析（含 `why_it_matters` / `evidence` / `suggested_fix`） |
| `learnings-researcher.md` | 制度性既往教训的非结构化返回 |
| `raw-returns.json` | 9 位评审员的紧凑返回（34 条 finding） |
| `synthesized-findings.json` | Stage 5 合成结果（primary / pre-existing / soft buckets / triage groups / coverage） |
| `validator-input.json` · `validator-verdicts.json` · `validator-outcome.json` | Stage 5b 验证批次与 10 条判定 |
| `finish-input.json` | 派发上下文 → 后续阶段的交接文件（范围 / 意图 / 计划 / 名册 / 覆盖说明） |
| `metadata.json` · `stages.jsonl` | 运行元数据与各阶段耗时 |
| `files.txt` | 52 个改动文件清单 |

⚠️ `full.diff`（541 KB）**未入库**（与上一轮 `20261109-181644-6f6ddca3` 的做法一致：
只留 `files.txt`）⇒ 需要完整 diff 时用 `git diff 38c91ac..1c3acb9` 现场取。
