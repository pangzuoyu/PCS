# P9B-2R 修复批 · follow-up 代码评审 · 20261102-004658-08a55f5c

`ce-code-review` skill 的完整产物。**报告本体是 [`report.md`](report.md)** —— 其余文件是它的证据链，
只在需要复核某条结论时才需要打开。

- **范围：** `2bc2398` → `77e3293`（`main`），**仅 P9B-2R 修复批**，52 个文件 / +7296-5411
  （清单见 `files.txt`）。base 用 `2bc2398` 而非调用方给的 `58341eb` —— 后者本身就是 #1 快照修复
  commit，拿它当 base 会把委员会指定的 #1 范围整个排除在 diff 之外。
- **模式：** report-only。`mode.apply_local = false` —— **本轮未修改任何项目文件、未应用任何修复。**
- **结论：** Ready with fixes —— 1 条 P1（已确认）+ 12 条 P2 + 4 条 P3（17 条 primary，
  其中 8 条经独立验证者裁决、8 confirmed / 0 rejected / 0 unresolved）。
- **本轮性质：** **follow-up 验证**。委员会指定的复核范围 =
  (a) 上一轮 cap 尾四条（分页过滤器冻结 / 列表错误恢复 / UI-SPEC V2.3 行 / 代理签章凭据复位）+
  (b) #1 审批链快照语义（submit 冻结快照 → 中间步骤只读快照 → 每步重断言提交人 → 行锁）。
  问题不是「还有没有更多缺陷」，而是「声称修掉这批的批次是否真修掉了、有没有回归」。
- **评审团队：** correctness / project-standards / testing / maintainability / security /
  api-contract / data-migration / adversarial（见各 `<reviewer>.json`）。
  跨模型独立评审未运行（本机只有 claude CLI，同一 serving family）。

## 怎么读

| 文件 | 作用 |
|---|---|
| `report.md` | **报告本体。** Triage Groups / P1-P3 / Requirements Completeness(R1-R17) / Deployment Notes / Coverage |
| `metadata.json` | 运行元数据（reviewer 数、耗时、成本） |
| `synthesized-findings.json` | 合并去重后的 17 条 primary + 软桶（residual_risks / testing_gaps） |
| `validator-verdicts.json` | 验证者逐条裁决：8 selected / 8 confirmed / 0 rejected / 0 unresolved |
| `validator-outcome.json` | 验证批次终态记录 |
| `validator-input.json` | 送验 8 条（#1, #2, #3, #4, #5, #6, #8, #9）全文与选择依据 |
| `<reviewer>.json` | 各 reviewer 完整产物（findings + residual_risks + testing_gaps） |
| `raw-returns.json` | 各 reviewer 的合并层紧凑回执 |
| `finish-input.json` | 派发上下文 → 合并/报告叶的移交契约（scope / intent / roster / coverage） |
| `stages.jsonl` / `files.txt` | 阶段记账 / 变更文件清单 |

注：`full.diff`（906K）及 `reconcile.py` / `synthesize*.py` 未入库，按 `2bc2398` 与 `77e3293` 之间
`git diff` 可完整复现。

## 运行备注（三处）

- **本轮最重要的一条（P1 #1）：行锁只写在注释里，没有任何测试观测它。**
  SQLite 把 `with_for_update()` 编译成空串；`test_record_approval_chain.py` 的 docstring 把 PG 验证
  推给「CI fresh-PG api-drift job」，而那个 job **一条后端测试都不跑**。删掉 `.with_for_update()`，
  整个套件照样全绿。
- **P2 #9：无快照的历史行把 CWE-863 的两条保护全关掉。** 迁移落地时已在 `IN_APPROVAL` 的记录
  `approval_chain_snapshot IS NULL` ⇒ 每步的 `submitted_by` 重断言整段跳过 + 链条回落到**实时**矩阵
  —— 正是委员会裁决要堵的自审绕过。当前 pcs / pcs_test 无此数据，属窗口未打开而非已发生。
- **★ 证据更正（orchestrator 自查，非 reviewer 发现）：** 上一轮 QA 报告声称
  「pcs / pcs_test / 隔离 schema 三目标都在 p9_014 且 `alembic check` exit 0」。直接查库发现
  **pcs_test 当时停在 p9_013、新列不存在** —— 原写法在同一进程里改 `os.environ['DATABASE_URL']` 跑两遍，
  而 alembic 的 pydantic `settings` 是**缓存实例**，第二次改环境变量不生效 ⇒ 第二遍连的仍是 pcs
  （升级幂等 ⇒ 两次都打印 `p9_014 (head)`，看不出来）。已用**每库独立进程**补升并直接查库确认，
  QA 报告已就地更正，教训进 `.wolf/cerebrum.md`。
- **配额降级：** security / adversarial 被 429 截断后重派成功；data-migration 被 429 截断，
  其结论由 testing reviewer 的两份深挖子报告 + orchestrator 直接查库**重建**，在 `finish-input.json`
  的 coverage_notes / `failed_reviewers` 中如实标注为「归因证据」而非独立 persona 回执 ——
  该 persona 不计入 findings #5/#11/#17/#18 的 `independent_reviewers`。
