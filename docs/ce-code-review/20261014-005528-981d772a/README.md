# P8 代码评审 · 20261014-005528-981d772a

`ce-code-review` skill 的完整产物。**报告本体是 [`report.md`](report.md)** —— 其余文件是它的证据链，
只在需要复核某条结论时才需要打开。

- **范围：** `cfc0f2e` → `a9ccb84`（`main`），收窄到 P8（报表与输出）面的 46 个文件
  （`files.txt`）。base..HEAD 窗口内还含 P7 heat/calc 的工作，故未按整个 commit 区间审。
- **模式：** report-only。`mode.apply_local = false` —— **本轮未修改任何项目文件、未应用任何修复。**
- **结论：** Not ready —— 2 个 P0、6 个 P1、17 个 P2、3 个 P3。
- **评审团队：** 11 位 reviewer（见各 `<reviewer>.json`），8 条 P0/P1 全部经独立验证批次确认。

## 怎么读

| 文件 | 作用 |
|---|---|
| `report.md` | **报告本体。** Triage Groups / P0-P3 / Requirements Completeness / Deployment Notes / Coverage |
| `metadata.json` | 运行元数据（reviewer 数、耗时、成本）。`cost.status = partial` 是上游记账缺口，非评审失败 |
| `synthesized-findings.json` | 合并去重后的 30 条 primary + 14 条 not-selected |
| `validator-verdicts.json` | 验证者的逐条裁决：8 条 confirmed / 0 rejected / 0 unresolved |
| `validator-outcome.json` | 验证批次的终态记录 |
| `validator-input.json` | 送验的 8 条（原样） |
| `finish-input.json` | dispatch → merge → report 的交接契约，含 scope / intent / standards / 约束 |
| `scope.txt` · `files.txt` · `stages.jsonl` | 范围说明、审查文件清单、各阶段记账 |
| `<reviewer>.json` × 11 | 各 reviewer 的原始产出（findings / residual_risks / testing_gaps） |
| `deployment-verification.md` | 迁移 p8_001..p8_007 的部署清单与回滚注意（散文返回，无结构化 artifact） |

## 两处需要知道的修正

13 位 reviewer 独立工作，结论里有夸大与行号不准。dispatch context 逐条对照源码核验后，
两条断言被证伪并在报告中撤回 —— **不要从 `<reviewer>.json` 里把它们当事实捡回来**：

1. 「15 个过滤算子全部只做编译检查、从不执行」**不成立** —— 15 个在 `tests/` 中逐个有测试。
   保留的只有收窄后的事实：`apply_filters` 从未针对 JSONB 列跑过，`->>` 分支端到端无覆盖。
2. 「JSONB `->>` 路径在 Postgres 上是生产 500」**未证实** —— `->>` 是合法 PG 语法，
   且 `tests/conftest.py:51,101` 有 SQLite JSONB 垫片。

另：`adversarial.json` 初次落盘时两处 `why_it_matters` 字符串内有裸双引号未转义，
导致整文件解析失败。已按转义感知的方式修复，5 条发现全部恢复 —— **非丢弃**。

## 修复顺序（报告结论）

`#2 + #6 同批` → `#1` → `#3` → `#5` → `#4` → `#7 + #8` → 其余 P2/P3。

**#6 必须与 #2 同批落地，或先修 #6。** 现状是 #2 掩盖了 #6 —— 构建器任务从不写 `FINISHED`，
回收器会把已完成的审计行改判 FAILED，但因为 #2 的不 commit 这次改判回滚了、损坏没有落库。
**只修 #2 会把被掩盖的缺陷变成活跃的数据损坏**，且损坏发生在一张声明为审计表的表上。

需人工裁决的 8 条（#11、#12、#15、#16、#17、#18、#23、#25）不阻塞合入，但 #16
（`pcs_test` 停在 p8_005、开发库已在 p8_007）会让下一次针对迁移的验证给出看似真实实则错误的
漂移结果，建议最先做掉。

`full.diff`（442K）与 `raw-returns.json`（后者是 11 个 `<reviewer>.json` 的精确拼接）**未收录** ——
两者都可由 `finish-input.json` 与 `<reviewer>.json` 重建。

---

# 修复落地状态（2026-10-19 更新）

**30 条 primary findings 全部处理完毕。** 报告本身的结论不再代表当前状态。

| 批次 | 条目 | commit |
|---|---|---|
| 首轮（8 条 P0/P1 + 8 条裁决 P2/P3） | #1 #2 #3 #4 #5 #6 #7 #8 #9 #11 #12 #13 #14 #15 #16 #17 #18 #20 #23 #25 #28 | `211f3c6`..`c9d937f` |
| #24 MSW 契约冻结 | #24 | `346c257` |
| #19 输出格式白名单 | #19 | `c142014` |
| #22 #21 #29 后端失败路径 | #22 #21 #29 | `2a23d2e` |
| #27 状态筛选查询参数 | #27（后端 + 前端 + MSW） | `81947bd` |
| #10 #30 #26 前端正确性 | #10 #30 #26 | `e35ecfc` |

## 修的过程中推翻/修正了评审的五处前提

- **#4 / #7 / #17** —— 首轮已证伪并撤回（见上节）。
- **#19 「两份白名单」** —— 实际是**四份**，且其中 `report_service.SUPPORTED_FORMATS`
  的注释写着「取自 `watermark.EXPORT_FORMATS`」而代码是硬编码字面量。另有第五处漏网：
  `report.py` 的 `_MEDIA` 缺 csv 条目且**静默兜底**成 `application/octet-stream`。
- **#21「审计写失败被吞」** —— 吞是**刻意且已被测试钉住**的（`test_audit_failure_does_not_rollback_the_file`，
  理由是孤儿文件比有记录的文件更难排查）。该裁决保留。评审成立的是另一半：
  此前记 `logger.warning` 且**不带 report_file_id** ⇒ 合规缺口不可发现、不可查询。已改 ERROR + 点名。
- **#27 「后端不接收 status」** —— 后端确实不接，但**前端还多发了一个虚构的 `report_type`**
  （`ReportDefinition` 无此列）。两条一起处理。
- **#24「mock 落后于契约」** —— 落后的是 mock，但**漂移的后果不止于 mock**：见下。

## #24 引出的新发现（未修，已登记 bug-180）

`mocks/seed/pipe-classes.ts` 返 `{pipe_class_id, code, ...}`，而契约
`PipeClassResponse` 是 `{class_id, class_name, material_standard, corrosion_allowance, ...}`
—— **字段名整组不同**。

后果不是 mock 脏，是**生产缺陷**：`PipeClassListPage` 读 `record.pipe_class_id`
（`rowKey` 也用它），`PipeComputePage` 下拉用 `{value: p.pipe_class_id, label: p.code}`
—— 真后端下全是 `undefined`。**管道等级页在生产上就是坏的，是这份 mock 一直在替它遮着。**

未修的原因：改它要动页面 + `types/pipeClass.ts`，属 **TODO-039 前端类型唯一性**。
已在 `mocks/seed/pipe-classes.ts` 留注释指向本节。

发现手法值得记：**给 seed 加一条编译期一致性断言**
（`const _x: ContractType[] = seedX`）后 tsc 立刻报出 5 处真漂移
（checklist completeness 字段整组不同、vessel/sep-equip 返回契约里一个都没有的字段、
`formula_ref` 塞 boolean、Workspace 手写类型缺必填 `status`）。断言在本轮是**探针** ——
只在 workspaces 成立处保留，pipe-classes 处换成文档注释。

## 守门本身的缺口（本轮未修）

`scripts/check-api-drift.sh:64` 的 docstring 声称能检出属性类型变更/删除，
实际只比 `required` 数组 —— **改名与改类型都照过**。
本轮 5 处漂移里 1、2、3、5 都是它结构上看不见的。建议单独立项。
