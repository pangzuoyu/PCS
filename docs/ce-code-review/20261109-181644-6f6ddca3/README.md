# ce-code-review 报告 —— P9B-4 紧急批次（物流面项目守卫 + review-log）

- **run id**：`20261109-181644-6f6ddca3`
- **审查范围**：`3a929b6..cbc701b`（8 个 commit，34 个改动文件），分支 `main`，scope mode `local-aligned`
- **被审对象**：P9B-4 紧急批次 —— 物流面 ~20 个端点/路径补**项目级访问守卫**（`UserProject` 授权行）+
  新增受守卫端点 `GET /streams/{id}/review-log`（TODO-112）+ 前置（`POST /projects` 自动授权创建者、
  `scripts/seed_user_project_access.py`）+ `strict_client` 测试夹具
- **裁决**：**Ready with fixes** —— 无 P0；3 个 P1 + 5 个 P2 待修（8 项 actionable）
- **模式**：report-only（**未**改任何产品代码；本次落库只搬报告与证据）

## 怎么复现这次审查

```bash
git diff 3a929b6..cbc701b          # 被审 diff（full.diff 未入库，可随时重建）
git diff --stat 3a929b6..cbc701b
```

## 本目录里的东西

| 文件 | 是什么 |
|---|---|
| `report.md` | **主交付物** —— 完整审查报告（结论、8 项 actionable、需求完整性、覆盖度） |
| `README.md` | 本文件 |
| `metadata.json` / `stages.jsonl` | 运行元数据与阶段耗时 |
| `finish-input.json` | 调度上下文 → 合并/报告叶子 的交接契约 |
| `raw-returns.json` | 9 个审阅者的紧凑返回（合并前的原始返回） |
| `synthesized-findings.json` | 合并后的 13 条 primary findings（去重/提升/降级后的结果） |
| `validator-input.json` / `validator-verdicts.json` / `validator-outcome.json` | 独立校验批次的输入、13 条裁决（8 confirmed / 5 rejected）与结果记录 |
| `correctness.json` … `reliability.json` | 9 个审阅者的**完整**分析（含 `why_it_matters` 与证据数组） |
| `learnings-researcher.md` | 对 `docs/solutions/` + `.wolf/cerebrum.md` 的既有解法/规则检索结果 |
| `dispatch-context-probe-reviewlog.txt` | **调度上下文自己跑的两个复现之一**：用状态机真实的审计动作值写 4 行，review-log 只回 1 行 |
| `dispatch-context-probe-lineage.txt` | **调度上下文自己跑的两个复现之二**：血缘三端点在「不存在」与「跨项目」下的响应形状对比 |
| `files.txt` | 改动文件清单 |

## 两份「复现」是什么

它们**不是**审阅者的发现，而是调度上下文为了给报告提供**可执行证据**单独写的两个一次性脚本
（跑在仓库之外的 `/tmp`，没有改动仓库任何文件）：

1. **review-log 复现** —— 用 `state_machine.TRANSITION_AUDIT_ACTION` 的**真实**动作值
   （`RECORD_TRANSITION` / `APPROVAL_STEP_PASSED` / `APPROVAL_STEP_REJECTED`）+ `_write_audit`
   的**真实** detail 形状插 4 行审计，再调 `list_review_log`：
   **写入 4 行、返回 1 行**（`SUBMIT_FOR_CHECK`），`PASS_CHECK` 与 `REJECT_CHECK` 被丢弃。
2. **血缘复现** —— 以「只持有项目 A 授权」的用户调三个血缘端点：
   跨项目物流 ⇒ 三端点全 404；不存在的 UUID ⇒ `/upstream` 返 **200 `[]`**、`/graph` 与 `/downstream` 返 404。

⇒ 这两条是报告里 **#1 / #2** 的硬证据；「测试全绿却抓不到」的原因是测试 fixture 与 MSW mock
**伪造了生产中不存在的行形状**（见报告 #2 / #5）。

## 本次审查的覆盖限制

- 跨模型 adversarial **未跑**（本机没有 codex/grok/cursor/composer CLI）⇒ 对抗视角由**同模型**本地
  `adversarial` 审阅者覆盖，其一致性**不提升**任何置信锚点。
- 物流面**之外**的模块（flash / pipe / vessel / pump 结果路由）只做了 grep 级调用点排查，**未审**。
- 后端全量测试在本轮跑到 1800 s 超时 ⇒ **没有**独立全量数字；批次自己记录的是 5528 passed / 0 failed。
