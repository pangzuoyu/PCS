# 收口上下文（给 merge leaf / report leaf）

- **run_dir**: 见本文件所在目录的上一级
- **artifact root（项目内）**: `docs/ce-code-review/20261117-013829-7e9fbabe/`
  （CE 配置里没有 `docs_root` ⇒ 默认 `docs`；子目录 = 技能自己的 `ce-code-review`）
- **scope**: base `d73d1ac` · head `f3b35e5` · branch `main` ·
  diff = `git diff -U10 d73d1ac..f3b35e5`（55 文件 · 8659 行 · 可执行非测试 974 行 ⇒ size_band=large ⇒ **depth=full**）
- **scope facts**: `scope-facts.json`
- **intent**: `shared/intent.md`
- **plan（规格依据）**: `docs/superpowers/plans/2026-11-13-p10-batch-b-fullflow-e2e.md`
  （本批的规格来源 ⇒ Stage 6 的 requirements completeness 对它做）
  ⇒ plan_source: **explicit**（本批就是照它实施 ⇒ 用户要求「审查本批」即以它为规格）
- **criteria（标准文件）**: `/home/pangzy/code_project/PCS/CLAUDE.md`（仓库根 ⇒ 治理全部改动文件）
- **reviewers（9）**: correctness · project-standards · testing · maintainability ·
  learnings · security · api-contract · reliability · adversarial
- **cross-model peer**: **未启动** —— 本机没有技能允许的 peer provider CLI
  （codex / grok / composer / cursor-agent 均不在 PATH；`CROSS_MODEL_PEERS` 未设）
  ⇒ ⇒ 对抗性视角由**进程内** `adversarial-reviewer` 承担 ⇒ 记进 Coverage。
- **未选的人士及理由**（写进 Coverage）：
  performance（生产代码改动极小 · 性能面集中在测试种子，无实质资源影响）·
  data-migration（diff 内**无**迁移/模式产物 ⇒ 无 backfill/迁移脚本）·
  agent-native（无 agent 面向的能力/工具面）·
  julik-frontend-races（前端是 React/TS，非 Stimulus/Turbo）·
  swift-ios（无 Swift/iOS 文件）· previous-comments（standalone 评审 · 无 PR 评论）·
  deployment-verification（无高风险迁移产物）
- **已知的「本批自认的债」（供报告交叉核对，但**不要**当成你的结论）**:
  bug-2165 的根因未闭环（`report_tasks._finalize` 赋值不落库 ⇒ E2E-009 标 xfail）·
  运行时写配置表的占位管级（并发下可能撞唯一约束）·
  前端 3 个页面调不存在的端点 + 3 个页首屏 422（已登记 TODO-159/160）·
  E2E 进 CI 延到 P10-F。
